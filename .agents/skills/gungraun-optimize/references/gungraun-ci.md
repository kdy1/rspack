# Gungraun CI on the fork

Read this when creating, auditing, or repairing the measurement harness. All workflow runs and artifacts for this workflow belong to `kdy1/rspack`. The included workflow and schema-7 parser support only Callgrind `Ir`; Cachegrind and DHAT comparisons are not implemented.

## Dispatch prerequisite

GitHub requires a `workflow_dispatch` workflow to exist on the default branch before manual dispatch is available. Check the fork's actual workflows first. Adding a dispatch file only to an experiment branch does not establish this prerequisite.

If missing, prepare a minimal permanent dispatch entry point for a separate fork PR through `$create-pr`, within the user's authorization. Report that it must land before measurements can start. Do not push or merge the default branch, open an upstream setup PR, or create experiment PRs to work around the prerequisite. This repository includes `.github/workflows/gungraun.yml`; it becomes manually dispatchable after the infrastructure PR lands on the fork default branch. Infrastructure PR runs compare the same head SHA twice to validate the harness, not to accept an optimization.

Once a dispatch entry point exists, run its measurement implementation from a task-owned branch with `--ref`. Prefer an existing valid Gungraun workflow. Otherwise use a separate temporary branch for the harness, fixture/configuration changes, reporting, and Actions implementation. Record its commit, files, and manifest hunks. Keep this infrastructure out of upstream production branches.

## Harness contract

- Use a separate non-published benchmark crate or dedicated target with `harness = false`. The existing Criterion/CodSpeed targets are workload references, not Gungraun targets. Adapt the smallest realistic workload without replacing the existing suite.
- Pin equal `gungraun` and `gungraun-runner` versions. Check version-matched official documentation before writing macros or parsing summaries. Use Linux with Valgrind; do not assume the upstream's self-hosted runners or secrets are available to the fork.
- Use the repository Rust toolchain, code generation, allocator, and required build features. Inspect `xtask/benchmark/README.md`, `.github/workflows/bench-rust.yml`, and the chosen workload for fixture/setup requirements. Pin external fixture revisions and retain their hashes. Use the same fixture content for base and head.
- Put setup/teardown outside the measured function and protect inputs/results with `std::hint::black_box`. Fix random seeds, cache state, thread counts, and environment. Preserve a correct runtime and task completion boundary for async or parallel work.
- Use the same harness source, inputs, toolchain, build profile, features, allocator settings, and runner environment on both sides. Measure base then head on the same runner. Fix any environment drift before applying thresholds.
- If base lacks the harness, overlay only recorded benchmark plumbing onto unchanged base production code, or create a harness-only counterpart of base. Record original and effective SHAs plus the harness hash. Never copy head production files onto base. Stop if base lacks an API needed to execute the same workload.
- Check a same-SHA comparison before using a new harness. Verify stable case identities, measured boundaries, nonzero counts, and relevant thread/process coverage. Investigate differing same-SHA counts before evaluating optimizations.

Consult the official [CI setup](https://gungraun.github.io/gungraun/latest/html/installation/ci.html), [library benchmarks](https://gungraun.github.io/gungraun/latest/html/benchmarks/library_benchmarks/structure.html), [baselines](https://gungraun.github.io/gungraun/latest/html/cli_and_env/baselines.html), and [machine-readable output](https://gungraun.github.io/gungraun/latest/html/cli_and_env/output/machine_readable.html). Select documentation for the installed version; do not silently upgrade the harness during a comparison series.

## Exact revision comparisons

The included `gungraun.yml` accepts required full-SHA `base_ref` and `head_ref` inputs and an optional `filter`. See `xtask/gungraun/README.md` for the initial source workloads. Confirm the workflow has landed before dispatch.

```bash
gh workflow run gungraun.yml --repo kdy1/rspack --ref "$WORKFLOW_BRANCH" \
  -f base_ref="$BASE_SHA" -f head_ref="$HEAD_SHA" -f filter="$BENCH_FILTER"
gh run list --repo kdy1/rspack --workflow gungraun.yml \
  --event workflow_dispatch --branch "$WORKFLOW_BRANCH" \
  --json databaseId,headSha,createdAt,status,url
```

Resolve base and head to immutable commit SHAs available to the fork. Freeze the dispatch branch SHA for both incremental and cumulative comparisons. Record dispatch time and match event, workflow revision, run ID, and artifact metadata; never select a run solely because it is latest. If concurrent runs match, inspect artifacts to identify the requested comparison.

Wait only for the matching task-owned run. Use bounded waits and report progress. Download its evidence explicitly from the fork:

```bash
gh run view "$RUN_ID" --repo kdy1/rspack --json status,conclusion,url,headSha
gh run download "$RUN_ID" --repo kdy1/rspack --dir "$RESULT_DIR"
```

In the Actions job, preserve reporting code from the workflow checkout before checking out benchmark revisions. Use a shared Gungraun home outside the checkout. With the selected version's supported CLI, the baseline sequence is:

```bash
# Execute in the prepared base checkout.
cargo bench -p "$BENCH_PACKAGE" --bench "$BENCH_TARGET" -- \
  --home="$RUNNER_TEMP/gungraun" --save-baseline=base "$BENCH_FILTER"
# Execute in the prepared head checkout, with identical harness and fixtures.
cargo bench -p "$BENCH_PACKAGE" --bench "$BENCH_TARGET" -- \
  --home="$RUNNER_TEMP/gungraun" --baseline=base \
  --save-summary=json "$BENCH_FILTER"
```

Keep shell values quoted and pass workflow inputs through environment variables instead of interpolating them into executable shell text. Validate requested revisions and filters. Keep the original benchmark failure status after rendering/uploading diagnostic output.

## Evidence and permissions

Upload machine-readable summaries, raw Callgrind profiles, logs, and optional regular/differential flamegraphs with `if: always()`. Retain enough metadata to verify:

- repository, run ID/URL, workflow revision, original/effective base and head SHAs;
- harness and fixture hashes, exact filter and complete case identities;
- tool versions, runner architecture, build profile/features, allocator and environment;
- summary schema version, metric names, raw base/head counts, and any failed cases.

Reject incomplete or mismatched metadata before interpreting percentages. Parse the recorded summary schema rather than guessing fields. Preserve raw artifacts beyond temporary-branch cleanup; copy them to task storage if retention would otherwise lose evidence.

Use `contents: read` and job summaries/artifacts; no CodSpeed token or PR-comment permission is needed. Follow repository action-pinning conventions. Never execute candidate code under `pull_request_target`. Key manual-run concurrency by run ID so incremental and cumulative runs cannot cancel each other. New reporting workflows must not add regression-limit flags; distinguish benchmark execution failure from the skill's publication gate.
