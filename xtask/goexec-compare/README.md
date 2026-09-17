# Native compiler: Tokio and goexec

[中文说明](README.zh-CN.md)

This experimental feature runs native Rust compiler tasks on
[goexec at `2faaeec15d1dd90fb7a25d9de58f29274cbeacbc`](https://github.com/dudykr/ddbase/commit/2faaeec15d1dd90fb7a25d9de58f29274cbeacbc).
It includes the worker-local queues, batch work stealing and sharded task
registries from the latest optimization. The dependency and its transitive
versions are pinned in Cargo.lock; no local dependency override is required.
The port is based on Rspack `d4cd073db21483ed7c524dedf59ad1d8bf400b8e`.

## Scope

The benchmark's `goexec` feature selects the executor for compiler-context tasks,
`rspack_parallel` joins, source reads, and native filesystem operations. Source
reads use the same synchronous filesystem implementation inside a tracked
blocking region. CPU-heavy deferred destruction stays within the executor's CPU
permit budget. Rayon and Tokio's task-local/synchronization primitives remain.
Without the feature, the Tokio path remains selected.

This is a native Rust Compiler API experiment. It does not migrate the Node/NAPI
runtime, JavaScript plugins/loaders, watch timers, networking, or persistent-cache
background runtimes. Do not enable this feature globally for the Node bindings.
Persistent cache is disabled in the benchmark.

## Build and run

Use the repository's pinned Rust toolchain, Python 3, and pnpm 10.11.0 for the
fixtures. Run from the repository root:

```sh
python3 xtask/goexec-compare/prepare-fixtures.py
cargo build --locked --profile executor-bench -p rspack_goexec_compare
cp target/executor-bench/rspack_goexec_compare target/goexec-compare/rspack-tokio
cargo build --locked --profile executor-bench -p rspack_goexec_compare --features goexec
cp target/executor-bench/rspack_goexec_compare target/goexec-compare/rspack-goexec

target/goexec-compare/rspack-tokio target/goexec-compare/fixtures threejs-10x development 16 2 3
target/goexec-compare/rspack-goexec target/goexec-compare/fixtures threejs-10x development 16 2 3
```

Arguments are `FIXTURE_ROOT PROJECT MODE WORKERS WARMUPS SAMPLES`.
Projects: `basic-react`, `threejs`, `threejs-10x`.
Modes: `development`, `production-sourcemap` (minification off),
`production-minify` (source maps off). Executor and Rayon worker counts match.
Tokio allows 512 additional blocking threads; goexec caps workers at
`WORKERS + 512`, plus its monitor, with a 100 microsecond handoff observation delay.

The optimized profile uses opt-level 3, LTO off, 16 codegen units, and mimalloc.
The primary timer covers `Compiler::run()`, including output writes with
compare-before-emit disabled. Each iteration uses a fresh Compiler with no
persistent cache and a warm OS filesystem cache. Runtime/Compiler construction,
asset verification, shutdown and destruction are outside the primary timer.
Both executors dispatch the root future to a worker. A 100 ms quiet interval
follows cleanup. Every iteration checks diagnostics and disk versus memory
assets, records per-asset SHA-256, and requires goexec shutdown to complete.

For the macOS scheduling profile used in the archived results, compile the
benchmark-only startup library and apply it to **both** binaries:

```sh
clang -dynamiclib -O2 -Wall -Wextra -Werror xtask/goexec-compare/qos.c -o target/goexec-compare/bench-qos.dylib
DYLD_INSERT_LIBRARIES="$PWD/target/goexec-compare/bench-qos.dylib" target/goexec-compare/rspack-tokio target/goexec-compare/fixtures threejs-10x development 16 2 3
DYLD_INSERT_LIBRARIES="$PWD/target/goexec-compare/bench-qos.dylib" target/goexec-compare/rspack-goexec target/goexec-compare/fixtures threejs-10x development 16 2 3
```

This sets main and newly created pthreads to USER_INITIATED (25), adding one small
allocation and QoS-setting call per thread. Lazy thread startup remains inside
the timer. It changes no system settings and fails the process if setting QoS
fails. It does not isolate the machine from background load. Do not compare a
QoS-controlled variant against one using default QoS, and do not compile while
timing builds. For a repeat comparison, alternate binary order across seven fresh
process pairs, discard two warmups per process, and retain three samples each.
Compare asset hashes, module counts, and byte counts across every run.

## Recorded results

These are archived measurements from 2026-09-17 on an Apple M5 Max, not a new
benchmark run performed when publishing this branch. All three historical
variants used the same explicit QoS. The measured v2 used a local Cargo patch;
its production Rust source matches the git dependency pinned here. Binary hashes
can change with source checkout paths and dependency source identity.

Three.js-10x, 16 workers, median of 21 measured builds per variant:

| Mode | Tokio | Previous goexec (v1) | Current goexec (v2) |
|---|---:|---:|---:|
| Development | 104.91 ms | 155.70 ms | 98.24 ms |
| Source maps | 197.85 ms | 239.55 ms | 189.52 ms |
| Minification | 830.73 ms | 874.94 ms | 828.67 ms |

Development time fell 36.9% versus v1 and 6.4% versus Tokio in this condition.
The paired seven-block bootstrap interval for v2/Tokio development time change
was -6.6% to -3.8%; minification's interval includes no difference. This is not
a universal speedup: one-worker Three.js-10x development remains 12% slower
than Tokio, and 16-worker ordinary Three.js development remains 8.5% slower.
Earlier default-QoS runs experienced abrupt slowdowns even in unchanged baseline
binaries. The precise OS cause was not established; shared-host scheduling and
background-load effects remain limitations of these measurements.

The archive contains all 1,365 builds (819 measured, 546 warmups), across 273
processes and 13 conditions. All output hashes, module counts and byte counts
matched, and goexec reported no thread-creation failures. Each condition used
seven blocks with three variants, rotating/reversing their order. Intervals use
10,000 bootstrap resamples of paired block-median ratios, not independent
resampling of builds within a process.

- [All conditions, confidence intervals and p95](results/summary.json)
- [16-worker raw results](results/final-p16.jsonl)
- [1/4-worker raw results](results/final-scaling.jsonl)
- [Output validation and input hashes](results/validation.json)
- [Historical environment, revisions and binary hashes](results/environment.json)

The historical environment file records the original PR revision plus the local
optimization patch hash; it is preserved as provenance, not a description of
this branch's dependency source. Current source validation should use the git
revision in `crates/rspack_tasks/Cargo.toml` and Cargo.lock. Referenced exploratory
artifacts are not part of this compact archive. The historical v1 is not selected
by this branch's feature; this branch builds Tokio and optimized v2.
