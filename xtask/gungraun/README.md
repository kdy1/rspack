# Gungraun CI benchmarks

`.github/workflows/gungraun.yml` compares exact commits in `kdy1/rspack` on one
Ubuntu runner. It uses Gungraun and its runner at version 0.20.0 with Valgrind.
The harness explicitly passes `GLIBC_TUNABLES` from the job into each measured
process; Gungraun clears other process environment variables by default.
No CodSpeed token or upstream runner is required. The workflow reports counts;
the optimization skill applies the performance gate before upstream publication.

## Run a comparison

After this workflow lands on the fork's default branch:

```bash
gh workflow run gungraun.yml --repo kdy1/rspack --ref main \
  -f base_ref=<full-base-sha> -f head_ref=<full-head-sha> -f filter=''
```

Both inputs must be full lowercase commit SHAs available in the fork. Use the
same workflow revision for a series of comparisons. The workflow overlays its
own harness, lockfile, and source-map fixture onto each revision. It preserves
production code and uses the workflow's Rust toolchain. Different Cargo build
configuration or dependencies incompatible with the harness lockfile cause a
failure instead of an uncontrolled comparison.

PR changes to this infrastructure run the head SHA twice to validate the
harness before it lands. This is a same-revision check, not evidence of an
optimization against the PR base. Other PRs do not trigger this workflow.

## Cases and measurement boundary

The initial suite adapts existing `rspack_benchmark` source workloads:

- `concat_add::few`: append 16 prebuilt children.
- `concat_add::many`: append 500 prebuilt children.
- `parse_source_map::antd`: parse the existing Ant Design source-map fixture.
- `serialize_source_map::antd`: serialize that parsed map.

Input preparation and returned-value destruction occur outside the measured
function. The concat cases include cloning each shared source handle. The suite
uses the system allocator and measures synchronous source operations only; it
does not measure bundling, worker threads, or the JavaScript API. Add relevant
cases before using the optimization skill for other workloads. A nonempty
`filter` uses Gungraun's filter syntax; an unmatched filter fails the comparison.

## Results and validation

The workflow and comparison parser support only Callgrind `Ir`. Cachegrind and
DHAT metrics are not supported. The job summary contains base/head `Ir` counts
and percentage changes. Negative
change means fewer executed instructions, not a wall-time speedup. Download the
`gungraun-<run-id>-<attempt>` artifact for `metadata.json`, `comparison.json`,
base/head summaries, logs, and raw Callgrind profiles. Metadata records exact
SHAs, tool versions, architecture, environment, and harness/fixture hashes.
Artifacts expire after 30 days; retain evidence needed by an optimization PR.

Build the isolated harness without executing Valgrind:

```bash
cargo bench --manifest-path xtask/gungraun/Cargo.toml --bench sources --locked --no-run
```

Validate the reporting code and workflow with Python 3.11 or newer and actionlint:

```bash
python3 -m unittest discover -s .github/scripts -p test_gungraun.py
actionlint .github/workflows/gungraun.yml
```

On Linux with the matching runner and Valgrind installed, the workflow's Python
entry point can also exercise the full comparison. Local counts validate the
harness only; the optimization skill requires fork Actions evidence.
