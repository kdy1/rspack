use std::hint::black_box;

use gungraun::{LibraryBenchmarkConfig, library_benchmark, library_benchmark_group, main};
use rspack_sources::{BoxSource, ConcatSource, RawStringSource, SourceExt, SourceMap};

// Reuse the existing source-map fixture and concat workloads from rspack_benchmark.
const SOURCE_MAP: &str =
  include_str!("../../benchmark/benches/fixtures/rspack_sources/antd-mini/antd.min.js.map");

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
fn parse_source_map(json: String) -> SourceMap<'static> {
  black_box(SourceMap::from_json(black_box(json)).expect("valid fixture"))
}

#[library_benchmark]
#[bench::antd(SourceMap::from_json(SOURCE_MAP.to_owned()).expect("valid fixture"))]
fn serialize_source_map(map: SourceMap<'static>) -> (String, SourceMap<'static>) {
  let json = black_box(&map).to_json();
  black_box((json, map))
}

library_benchmark_group!(
    name = sources;
    benchmarks = concat_add, parse_source_map, serialize_source_map
);
main!(
  config = LibraryBenchmarkConfig::default().pass_through_env("GLIBC_TUNABLES"),
  library_benchmark_groups = sources
);
