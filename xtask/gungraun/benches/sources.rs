#![allow(clippy::exit)] // Gungraun's main! macro exits its runner process.

use std::hint::black_box;

use gungraun::{LibraryBenchmarkConfig, library_benchmark, library_benchmark_group, main};
use rspack_sources::{
  BoxSource, ConcatSource, MapOptions, OriginalSource, RawStringSource, Source, SourceExt,
  SourceMap, SourceMapSource, SourceMapSourceOptions,
};

#[path = "generated/react.rs"]
mod react_fixture;
#[path = "generated/replace.rs"]
mod replace_fixture;

// Reuse the existing source-map fixture and concat workloads from rspack_benchmark.
const SOURCE_MAP: &str =
  include_str!("../../benchmark/benches/fixtures/rspack_sources/antd-mini/antd.min.js.map");
const EMPTY_MAP: &str = r#"{"version":3,"sources":[],"names":[],"mappings":""}"#;
const SMALL_MAP: &str = r#"{"version":3,"sources":["input.js"],"sourcesContent":["const answer = 42;\n"],"names":["answer"],"mappings":"AAAA,MAAMA"}"#;
const UNICODE_MAP: &str = r#"{"version":3,"sources":["한글.js"],"sourcesContent":["const text = \"😀\";\n"],"names":["text"],"mappings":"AAAA,MAAMA"}"#;

fn escaped_map(bytes: usize) -> String {
  let pattern = "\t\"\\\n한😀";
  let mut content = pattern.repeat(bytes / pattern.len());
  content.extend(std::iter::repeat_n('x', bytes - content.len()));
  serde_json::json!({
    "version": 3,
    "sources": ["escaped.js"],
    "sourcesContent": [content],
    "names": [],
    "mappings": "AAAA"
  })
  .to_string()
}

fn parsed(json: &str) -> SourceMap<'static> {
  SourceMap::from_json(json.to_owned()).expect("valid fixture")
}

fn repeated(json: &str, count: usize) -> Vec<String> {
  (0..count).map(|_| json.to_owned()).collect()
}

fn pieces(count: usize) -> Vec<BoxSource> {
  (0..count)
    .map(|i| RawStringSource::from(format!("// piece {i}\n")).boxed())
    .collect()
}

#[library_benchmark]
#[bench::few(pieces(16))]
#[bench::many(pieces(500))]
fn concat_add(pieces: Vec<BoxSource>) -> (ConcatSource, Vec<BoxSource>) {
  let mut source = ConcatSource::default();
  for piece in black_box(&pieces) {
    source.add(piece.clone());
  }
  black_box((source, pieces))
}

#[library_benchmark]
#[bench::antd(SOURCE_MAP.to_owned())]
#[bench::small(SMALL_MAP.to_owned())]
#[bench::unicode(UNICODE_MAP.to_owned())]
fn parse_source_map(json: String) -> SourceMap<'static> {
  black_box(SourceMap::from_json(black_box(json)).expect("valid fixture"))
}

#[library_benchmark]
#[bench::antd(SourceMap::from_json(SOURCE_MAP.to_owned()).expect("valid fixture"))]
#[bench::empty(parsed(EMPTY_MAP))]
#[bench::small(parsed(SMALL_MAP))]
#[bench::escaped_8k(parsed(&escaped_map(8192)))]
#[bench::escaped_64k(parsed(&escaped_map(65536)))]
fn serialize_source_map(map: SourceMap<'static>) -> (String, SourceMap<'static>) {
  let json = black_box(&map).to_json();
  black_box((json, map))
}

#[library_benchmark]
#[bench::antd_four(repeated(SOURCE_MAP, 4))]
#[bench::small_32(repeated(SMALL_MAP, 32))]
fn parse_source_map_batch(inputs: Vec<String>) -> Vec<SourceMap<'static>> {
  black_box(inputs)
    .into_iter()
    .map(|json| SourceMap::from_json(json).expect("valid fixture"))
    .collect()
}

// Fixture-only encoder. Production encoders must not determine the comparison inputs.
fn fixture_vlq(output: &mut String, delta: i32) {
  const BASE64: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  let mut value = (delta.unsigned_abs() << 1) | u32::from(delta < 0);
  loop {
    let digit = value & 31;
    value >>= 5;
    output.push(BASE64[(digit | if value != 0 { 32 } else { 0 }) as usize] as char);
    if value == 0 {
      break;
    }
  }
}

fn composition(order: &str, columns: bool) -> (BoxSource, bool) {
  let count = 4096;
  let code = "x".repeat(count);
  let mut inner = String::from("AAAA");
  for _ in 1..count / 4 {
    inner.push_str(",IAAI");
  }
  let mut outer = String::new();
  let mut previous = 0;
  for index in 0..count {
    let column = match order {
      "forward" => index,
      "reverse" => count - index - 1,
      "mixed" if index % 2 == 0 => index / 2,
      "mixed" => count - index / 2 - 1,
      _ => panic!("unknown query order"),
    } as i32;
    if index != 0 {
      outer.push(',');
    }
    fixture_vlq(&mut outer, i32::from(index != 0));
    outer.push_str("AA");
    fixture_vlq(&mut outer, column - previous);
    previous = column;
  }
  let source = SourceMapSource::new(SourceMapSourceOptions {
    value: code.clone(),
    name: "middle.js",
    source_map: SourceMap::new(
      outer,
      vec!["middle.js".into()],
      vec![code.clone().into()],
      vec![],
    ),
    original_source: Some(code.clone().into()),
    inner_source_map: Some(SourceMap::new(
      inner,
      vec!["original.js".into()],
      vec![code.into()],
      vec![],
    )),
    remove_original_source: false,
  })
  .boxed();
  warm_graph(source, columns)
}

fn warm_graph(source: BoxSource, columns: bool) -> (BoxSource, bool) {
  let map = source
    .map(&MapOptions::new(columns))
    .expect("mapped fixture");
  assert!(!map.mappings().is_empty());
  drop(map);
  (source, columns)
}

fn original_graph(unicode: bool, columns: bool) -> (BoxSource, bool) {
  let line = if unicode {
    "const 한글 = '😀';\n"
  } else {
    "const answer = foo(42);\n"
  };
  warm_graph(
    OriginalSource::new(line.repeat(4096), "input.js").boxed(),
    columns,
  )
}

#[library_benchmark]
#[bench::antd(parsed(SOURCE_MAP))]
#[bench::small(parsed(SMALL_MAP))]
fn decode_mappings(map: SourceMap<'static>) -> (usize, SourceMap<'static>) {
  let count = black_box(&map)
    .decoded_mappings()
    .fold(0, |count, mapping| {
      black_box(mapping);
      count + 1
    });
  black_box((count, map))
}

#[library_benchmark]
#[bench::react_full(warm_graph(react_fixture::source(), true))]
#[bench::react_lines(warm_graph(react_fixture::source(), false))]
#[bench::replace_full(warm_graph(replace_fixture::source(), true))]
#[bench::replace_lines(warm_graph(replace_fixture::source(), false))]
#[bench::original_ascii(original_graph(false, true))]
#[bench::original_unicode(original_graph(true, true))]
#[bench::original_lines(original_graph(false, false))]
#[bench::compose_forward(composition("forward", true))]
#[bench::compose_reverse(composition("reverse", true))]
#[bench::compose_mixed(composition("mixed", true))]
#[bench::compose_lines(composition("forward", false))]
fn map_graph((source, columns): (BoxSource, bool)) -> (usize, BoxSource) {
  let options = MapOptions::new(columns);
  let map = black_box(&source).map(&options).expect("mapped fixture");
  let length = map.mappings().len();
  black_box(map);
  black_box((length, source))
}

library_benchmark_group!(
    name = sources;
    benchmarks = concat_add, parse_source_map, serialize_source_map, parse_source_map_batch,
      decode_mappings, map_graph
);
main!(
  config = LibraryBenchmarkConfig::default().pass_through_env("GLIBC_TUNABLES"),
  library_benchmark_groups = sources
);
