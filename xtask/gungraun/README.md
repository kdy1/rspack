# Gungraun CI benchmarks

`.github/workflows/gungraun.yml` compares exact commits in `kdy1/rspack` on one
Ubuntu runner. Gungraun and its runner are pinned to 0.20.0. Results report
Callgrind `Ir` (executed instructions); they do not establish wall-time speedups.
The workflow reports counts without performance-failure thresholds.

## Select a suite

The manual workflow accepts these `suite` values:

| Suite | Cases |
| --- | --- |
| `all` (manual default) | All existing Rust benchmarks below, including the large bundle cases |
| `benches` | Graph construction and APIs, dependency scanning, JavaScript compiler source maps, bundles, compilation stages, and persistent-cache restore |
| `rspack_sources` | All cases registered by the existing isolated `rspack_sources` Criterion target |
| `walltime` | Both `threejs-10x` bundle cases, measured as instructions |
| `sources` | Original lightweight smoke suite: concat with 16/500 children and Ant Design source-map parsing/serialization |

The full suites reuse registrations from `xtask/benchmark/benches/benches.rs`,
`rspack_sources.rs`, and `walltime.rs`. An adapter executes the existing routines
once under Callgrind. Discovery records the original entry point and Criterion
case name in `base-catalog.json` and `head-catalog.json`. Different catalogs,
missing summaries, duplicate IDs, empty filters, and failed cases invalidate a
comparison. The workflow does not silently skip unsupported cases.

`filter` selects a substring of the original Criterion name for full suites.
An empty filter selects the entire chosen suite. `sources` retains the original
native Gungraun filter syntax for compatibility.

```bash
gh workflow run gungraun.yml --repo kdy1/rspack --ref <workflow-branch> \
  -f base_ref=<full-base-sha> -f head_ref=<full-head-sha> \
  -f suite=all -f filter=''

# Measure one stage, preserving graph preparation outside the measurement.
gh workflow run gungraun.yml --repo kdy1/rspack --ref <workflow-branch> \
  -f base_ref=<full-base-sha> -f head_ref=<full-head-sha> \
  -f suite=benches -f filter='rust@create_module_hashes'
```

Both revisions must be full lowercase commit SHAs available in the fork. Freeze
the workflow branch revision for a comparison series. The workflow overlays its
harness, benchmark registrations, fixtures, lockfiles, and Rust toolchain onto
both revisions. Production implementations remain at their requested revision.
Cargo dependency or configuration incompatibility fails the comparison.

Full suites build the Rust compiler and can take substantially longer than the
smoke suite. The job allows up to six hours. Infrastructure PRs run the original
smoke suite with the head SHA twice; manually dispatch full-suite validation
before accepting a harness change. Other production PRs do not trigger profiling.

## Measurement boundary

The full adapter preserves the existing Criterion routine boundaries:

- `iter` runs one unmeasured preparation iteration, then measures one iteration,
  including destruction of the routine result. This warms lazy source caches and
  matches the repeated-call behavior of the original benchmarks.
- `iter_batched` and `iter_batched_ref` prepare fresh inputs outside the measured
  region. They stop instrumentation before destroying returned results and, for
  the reference variant, the prepared input. Destruction inside the routine
  remains part of that routine.
- Compiler creation, graph preparation, fixture copying, and persistent-cache
  seeding remain where the existing benchmark places them. Persistent-cache
  cases retain their isolated workspace and fresh-compiler restore semantics.

Callgrind instrumentation starts and stops around the measured routine globally,
so work on Tokio blocking threads is included. The adapter does not use a
thread-local collection toggle. Simulation uses Tokio's current-thread runtime,
eight blocking threads, and one Rayon thread. The large `walltime` fixtures also
use this simulation configuration in Gungraun; this does not reproduce their
multi-thread wall-time configuration. Asynchronous work must complete before the
existing measured routine returns. The harness does not measure the JavaScript
API or N-API overhead.

Full suites use `rspack_benchmark`'s existing mimalloc allocator wrapper and the
`codspeed` build profile without running CodSpeed. The original `sources` smoke
suite retains its system allocator and isolated `bench` profile. Counts from
different suites or measurement boundaries must not be combined as one baseline.

## Fixtures and reproducibility

The full suites pin `rstackjs/rspack-benchcases` to the SHA recorded in the
workflow, install its frozen pnpm lockfile with scripts disabled, and use the
existing fixture setup script for CSS and scaled threejs inputs. Base and head
share these immutable inputs; writable cache workspaces are sample-local.
Metadata records the fixture revision and lockfile hash, exact benchmark and
harness file hashes, toolchain, architecture, allocator, features, thread
configuration, and environment. The job explicitly passes benchmark environment
variables into measured processes because Gungraun clears other variables.

## Results and validation

Download `gungraun-<run-id>-<attempt>` from the fork. It contains `metadata.json`,
`comparison.json`, base/head catalogs for full suites, summaries, build and
measurement logs, and raw Callgrind profiles, including per-thread output. Counts
are summed over the recorded profiles by Gungraun. Metadata and catalogs must
match the intended workload before interpreting the result. Artifacts expire
after 30 days; retain evidence needed for optimization decisions.

[Full-suite same-revision validation](https://github.com/kdy1/rspack/actions/runs/39928018690)
passed at `7c7255aafc05d7c8380eccd7d11f307c0e2e7528`: 44 compiler/stage cases,
13 source cases, and two large bundle cases. Downloaded artifacts contain all
59 comparisons and matching catalogs, 138 verified harness file hashes, and
matching Cargo feature configurations. Worker-thread counts are included in the
totals. Forty-one cases produced identical counts; the largest absolute change
was 0.108% in persistent-cache restore. This establishes harness coverage and
records same-revision variability; it is not an optimization result. Later
registration and feature-validation guards were checked locally against these
artifacts, with ten Python checks and Clippy on the changed Rust targets.

```bash
gh run download <run-id> --repo kdy1/rspack --dir <result-directory>

# Build the isolated harness without executing Valgrind.
cargo bench --manifest-path xtask/gungraun/Cargo.toml --locked --no-run

# Check reporting and overlay behavior; Python 3.11 or newer is required.
python3 -m unittest discover -s .github/scripts -p test_gungraun.py
actionlint .github/workflows/gungraun.yml
```

`prepare.py` generates the full driver only in the temporary benchmark checkout.
Its overlay changes benchmark plumbing and adds a benchmark-only runtime feature;
those changes must not be transferred to an upstream production PR. The root
workspace remains unchanged. Local builds check correctness and harness startup;
only matching fork Actions comparisons provide optimization evidence.
