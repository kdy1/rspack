#![allow(clippy::exit)] // Gungraun's main! macro exits its runner process.

use std::hint::black_box;

use gungraun::{LibraryBenchmarkConfig, library_benchmark, library_benchmark_group, main};
use rspack_sources::{BoxSource, ConcatSource, RawStringSource, SourceExt, SourceMap};

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

library_benchmark_group!(
    name = sources;
    benchmarks = concat_add, parse_source_map, serialize_source_map, parse_source_map_batch
);
main!(
  config = LibraryBenchmarkConfig::default().pass_through_env("GLIBC_TUNABLES"),
  library_benchmark_groups = sources
);
