use std::{
  collections::BTreeMap,
  path::PathBuf,
  sync::Arc,
  time::{Duration, Instant},
};

use rspack::builder::{Builder, Devtool};
use rspack_core::{
  Compiler, Experiments, Mode, ModuleOptions, ModuleRule, ModuleRuleEffect, ModuleRuleUse,
  ModuleRuleUseLoader, Optimization, OutputOptions, Resolve, RuleSetCondition,
};
use rspack_fs::NativeFileSystem;
use rspack_regex::RspackRegex;
use rspack_tasks::{CompilerContext, within_compiler_context, within_compiler_context_sync};
use serde_json::json;
use sha2::{Digest, Sha256};

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

fn main() {
  let args: Vec<String> = std::env::args().collect();
  let root = PathBuf::from(&args[1]).canonicalize().unwrap();
  let project = &args[2];
  let mode = &args[3];
  let threads: usize = args[4].parse().unwrap();
  let warmup: usize = args[5].parse().unwrap();
  let samples: usize = args[6].parse().unwrap();
  let dir = root.join(project);
  assert!(dir.is_dir());
  rayon::ThreadPoolBuilder::new()
    .num_threads(threads)
    .build_global()
    .unwrap();
  let init = Instant::now();
  #[cfg(feature = "goexec")]
  let rt = rspack_tasks::runtime::Runtime::builder()
    .parallelism(threads)
    .max_threads(threads + 512)
    .handoff_delay(Duration::from_micros(100))
    .build()
    .unwrap();
  #[cfg(not(feature = "goexec"))]
  let rt = tokio::runtime::Builder::new_multi_thread()
    .worker_threads(threads)
    .max_blocking_threads(512)
    .enable_all()
    .build()
    .unwrap();
  let init_ms = init.elapsed().as_secs_f64() * 1000.;
  let engine = if cfg!(feature = "goexec") {
    "goexec"
  } else {
    "tokio"
  };
  eprintln!("{engine}: {project}/{mode}, {threads} workers, runtime init {init_ms:.3} ms");
  for sample in 0..warmup + samples {
    let compiler_context = Arc::new(CompilerContext::new());
    let compiler = within_compiler_context_sync(compiler_context.clone(), || {
      let mut builder = Compiler::builder();
      builder
        .context(dir.to_string_lossy().to_string())
        .entry(
          "main",
          match project.as_str() {
            "basic-react" => "./src/index.jsx",
            "threejs" => "./src/Three.js",
            _ => "./src/index.js",
          },
        )
        .mode(if mode == "development" {
          Mode::Development
        } else {
          Mode::Production
        })
        .cache(rspack_core::CacheOptions::Disabled)
        .optimization(Optimization::builder().minimize(mode == "production-minify"))
        .resolve(Resolve {
          extensions: Some(vec!["...".into(), ".jsx".into()]),
          ..Default::default()
        })
        .experiments(Experiments::builder().css(true))
        .input_filesystem(Arc::new(NativeFileSystem::new(false)))
        .output_filesystem(Arc::new(NativeFileSystem::new(false)))
        .output(OutputOptions::builder().compare_before_emit(false));
      if mode == "production-sourcemap" {
        builder.devtool(Devtool::SourceMap);
      }
      if project == "basic-react" {
        builder.module(ModuleOptions::builder().rule(ModuleRule {
          test: Some(RuleSetCondition::Regexp(RspackRegex::new("\\.(j|t)s(x)?$").unwrap())),
          effect: ModuleRuleEffect {
            r#use: ModuleRuleUse::Array(vec![ModuleRuleUseLoader {
              loader: "builtin:swc-loader".into(),
              options: Some(json!({"jsc":{"parser":{"syntax":"typescript","tsx":true},"transform":{"react":{"runtime":"automatic"}}}}).to_string()),
              cache: false, options_cache_key: String::new(),
            }]), ..Default::default()
          }, ..Default::default()
        })).enable_loader_swc();
      }
      builder.build().unwrap()
    });
    #[cfg(feature = "goexec")]
    let before = rt.metrics();
    // Same scheduling boundary: submit the owning root future to a worker in
    // both engines. Runtime/Compiler construction and output hashing excluded.
    let wall = Instant::now();
    let task = rt.spawn(within_compiler_context(compiler_context, async move {
      let mut compiler = compiler;
      let start = Instant::now();
      compiler.run().await.unwrap();
      let build_ms = start.elapsed().as_secs_f64() * 1000.;
      (compiler, build_ms)
    }));
    #[cfg(feature = "goexec")]
    let (compiler, build_ms) = futures_block(task);
    #[cfg(not(feature = "goexec"))]
    let (compiler, build_ms) = rt.block_on(task).unwrap();
    let wall_ms = wall.elapsed().as_secs_f64() * 1000.;
    let errors: Vec<_> = compiler
      .compilation
      .get_errors()
      .map(|e| e.render_report(false).unwrap())
      .collect();
    assert!(errors.is_empty(), "{}", errors.join("\n"));
    let modules = compiler.compilation.get_module_graph().modules().count();
    let mut assets = BTreeMap::new();
    let mut bytes = 0usize;
    for (name, asset) in compiler.compilation.assets() {
      if let Some(source) = &asset.source {
        let content = source.buffer();
        assert_eq!(
          std::fs::read(dir.join("dist").join(name)).unwrap(),
          content.as_ref(),
          "emitted output differs: {name}"
        );
        bytes += content.len();
        assets.insert(
          name.clone(),
          format!("{:x}", Sha256::digest(content.as_ref())),
        );
      }
    }
    #[cfg(feature = "goexec")]
    let metrics = {
      let after = rt.metrics();
      json!({"handoffs": after.handoffs - before.handoffs, "threads": after.spawned_threads, "polls": after.polls - before.polls, "capacity_delays": after.capacity_delays - before.capacity_delays, "spawn_failures": after.thread_spawn_failures})
    };
    #[cfg(not(feature = "goexec"))]
    let metrics = json!({});
    let record = json!({"engine":engine,"project":project,"mode":mode,"threads":threads,"sample":sample.saturating_sub(warmup),"warmup":sample < warmup,"init_ms":init_ms,"build_ms":build_ms,"wall_ms":wall_ms,"bytes":bytes,"modules":modules,"assets":assets,"metrics":metrics});
    println!("{record}");
    // Finish compiler lifecycle outside measured build time in both engines.
    let task = rt.spawn(async move {
      compiler.close().await.unwrap();
      drop(compiler);
    });
    #[cfg(feature = "goexec")]
    futures_block(task);
    #[cfg(not(feature = "goexec"))]
    rt.block_on(task).unwrap();
    std::thread::sleep(Duration::from_millis(100));
  }
  #[cfg(feature = "goexec")]
  assert!(
    rt.shutdown_timeout(Duration::from_secs(30)),
    "goexec cleanup timed out"
  );
  #[cfg(not(feature = "goexec"))]
  rt.shutdown_timeout(Duration::from_secs(30));
}

#[cfg(feature = "goexec")]
fn futures_block<T>(handle: rspack_tasks::JoinHandle<T>) -> T {
  futures::executor::block_on(handle).unwrap()
}
