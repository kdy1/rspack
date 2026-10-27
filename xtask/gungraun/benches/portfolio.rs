#![allow(clippy::exit)] // Gungraun's main! macro exits its runner process.

use gungraun::{
  Bench, BinaryBenchmark, BinaryBenchmarkConfig, Callgrind, Command, binary_benchmark_group, main,
};

binary_benchmark_group!(
  name = portfolio;
  benchmarks = |group: &mut BinaryBenchmarkGroup| {
    let catalog = std::fs::read_to_string(std::env::var("RSPACK_GUNGRAUN_CATALOG").expect("catalog path"))
      .expect("read benchmark catalog");
    let cases: Vec<(String, String)> = serde_json::from_str(&catalog).expect("valid catalog");
    let driver = std::env::var("RSPACK_GUNGRAUN_DRIVER").expect("driver path");
    let mut benchmarks = std::collections::BTreeMap::new();
    let mut identities = std::collections::BTreeSet::new();
    for (entry, name) in cases {
      let id: String = name.chars().map(|c| if c.is_ascii_alphanumeric() { c } else { '_' }).collect();
      assert!(identities.insert((entry.clone(), id.clone())), "case ID collision");
      let benchmark = benchmarks.entry(entry.clone()).or_insert_with(|| {
        BinaryBenchmark::new(entry.chars().map(|c| if c == '/' { '_' } else { c }).collect::<String>())
      });
      benchmark.bench(Bench::new(id).command(Command::new(&driver).args([&entry, &name])));
    }
    for benchmark in benchmarks.into_values() {
      group.binary_benchmark(benchmark);
    }
  }
);
main!(
  config = BinaryBenchmarkConfig::default()
    .tool(Callgrind::with_args([
      "instr-atstart=no",
      "collect-atstart=yes"
    ]))
    .pass_through_envs([
      "RSPACK_BENCHCASES_DIR",
      "BENCH_MODE",
      "GLIBC_TUNABLES",
      "MIMALLOC_PURGE_DELAY",
      "RAYON_NUM_THREADS"
    ]),
  binary_benchmark_groups = portfolio
);
