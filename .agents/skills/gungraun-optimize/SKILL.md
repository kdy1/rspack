---
name: gungraun-optimize
description: Optimize Rspack with Gungraun profiles and exact base/head comparisons in kdy1/rspack GitHub Actions, then obtain human approval for each passing change before publishing it as a draft PR to web-infra-dev/rspack. Use for CI-based instruction-count optimization; excludes cache-miss or allocation-metric optimization and the local Docker/Valgrind workflow.
---

# Gungraun optimize

Adapted from [swc-next's Gungraun optimization workflow](https://github.com/swc-project/swc-next/tree/main/.agents/skills/gungraun-optimize). Measure before accepting an optimization. Keep provisional experiments PR-free, and obtain human approval for each proposed upstream PR before publishing it through `$create-pr`.

## Repository routing

- **Measurement repository:** `kdy1/rspack`. Push experiment branches here and run all Gungraun Actions comparisons here. Pass `--repo kdy1/rspack` explicitly to workflow, run, and artifact commands.
- **Optimization PR repository:** `web-infra-dev/rspack`. Use a clean head branch in `kdy1/rspack`, based on the upstream default branch, and request a **draft** PR through `$create-pr` only after the performance gate passes and the user explicitly approves that individual PR.
- Discover the upstream default branch and resolve its exact SHA. Verify the fork's parent and remote URLs instead of assuming that `origin` or the checkout's default PR target is upstream.
- Never push a default branch. Do not publish experiment PRs to trigger benchmarks. Do not include fork-only commits, this fork's skill configuration, or temporary measurement infrastructure in an upstream optimization PR.
- Loading or editing this skill does not authorize remote actions. Confirm that the task authorizes fork branch pushes and Actions comparisons before performing them; reuse authorization already given for this CI-based workflow. A local-only optimization request does not authorize them. Upstream PR creation always requires the separate per-PR approval below; a request to optimize or run CI is not that approval.

Use separate measurement and publication branches. A measurement branch can include temporary harness commits; a publication branch contains only the accepted production change and relevant correctness tests. Preserve unrelated work and PRs.

## Establish the target and evidence

1. Read `AGENTS.md` and applicable subsystem guidance. In particular, read `.agents/ARCHITECTURE.md` before scheduling changes, `.agents/CACHE_AND_INCREMENTAL.md` before cache changes, `.agents/RSPACK_SOURCES.md` before source changes, and `.agents/BINDING.md` before ownership or hook bridging changes.
2. Locate the requested workload and its production implementation. Start with `xtask/benchmark/README.md`, `xtask/benchmark/Cargo.toml`, `xtask/benchmark/benches/groups/`, `xtask/benchmark/cases/`, and `xtask/benchmark/stages/`. Inspect the current files; paths and benchmark names can change.
3. The existing `.github/workflows/bench-rust.yml` uses CodSpeed and `workflow_call`. It is not a Gungraun manual comparison workflow. The local `rspack-perf-valgrind-goal` skill also uses a different measurement contract. Neither result substitutes for this skill's CI evidence.
4. Use `.github/workflows/gungraun.yml` and the isolated `xtask/gungraun` harness for supported source workloads. Read `xtask/gungraun/README.md` for cases, inputs, and measurement limits; add relevant cases before optimizing other workloads. Verify authenticated GitHub access and Actions runner availability on `kdy1/rspack`. Inspect available workflows and their trigger/input schemas. Read [Gungraun CI](references/gungraun-ci.md) when establishing or repairing the measurement harness.
5. Freeze the starting upstream SHA, requested scope, exact primary tool/metric and improvement direction, benchmark identities/filter, target portfolio, related cases, protected cases, and case frequencies before editing. Protected cases are user-designated or workload-critical cases. Use documented production frequencies when available; otherwise give each case frequency one and disclose that assumption. Record the primary metric and direction explicitly (default: Callgrind `Ir`, lower is better). Do not select a different counter, reclassify cases, or change weights after seeing results to pass the gate. A requested metric change starts a new comparison series with a fresh baseline.
6. Record the Rust toolchain, Gungraun library/runner versions, Valgrind version, runner architecture, fixtures, features, allocator, thread configuration, and relevant environment. Keep them identical across each comparison.

This implementation supports only Callgrind `Ir` (executed instructions), with lower counts indicating improvement. The workflow and parser do not support Cachegrind or DHAT metrics. If the requested goal is cache misses or allocations, report that measurement is unsupported and stop this workflow; do not substitute `Ir` or claim those goals passed. Supporting another metric requires a separate harness, reporting, and gate extension before optimization. Instruction counts do not establish wall-clock speedups. Local commands can check correctness and harness startup, but only matching fork Actions runs establish performance.

For Rspack stage benchmarks, preserve the stage boundary. Compiler creation, graph preparation, fixture copying, and cache warmup belong outside the measured body unless they are the requested target. For cache cases, specify cold/warm state and reset writable fixtures consistently. Verify whether totals include worker threads or subprocesses before claiming a whole-compilation improvement. A Rust-only benchmark does not measure the `@rspack/core` JavaScript API or N-API overhead.

## Optimize one hypothesis

- Inspect the baseline's retained profiles or flamegraphs. Choose a hot path supported by that evidence, such as repeated graph traversal, allocation, hashing, source-map work, or conversion. Locate shared helpers and their callers before changing them; optimize the original helper instead of duplicating it.
- Preserve semantics, webpack compatibility, output ordering, diagnostics, cache lifetimes, and ownership. Keep changes target-independent unless the user explicitly requests a named architecture. The runner architecture alone does not authorize production specialization.
- Keep one focused optimization per candidate commit. Follow the repository's test placement rules; do not add inline Rust tests or new top-level JS runners.
- Build the artifacts consumed by tests using `.agents/DEVELOPMENT.md`, then run the relevant correctness checks. Review affected callers and fast/fallback paths. A lower instruction count is not correctness evidence.
- Commit only the intended candidate and push its task-owned measurement branch to the fork. Record the exact SHA. Dispatch the same workflow revision against both the previous accepted revision and the frozen starting revision. One run suffices when the two bases are identical.
- Verify run identity and artifact metadata as described in the CI reference. Retain raw counts, profiles, run URLs, benchmark IDs, and exact base/head SHAs. Missing, failed, renamed, duplicated, or different workloads are non-comparable, not wins or regressions.

## Performance gate

Apply the gate to both the incremental comparison and the cumulative comparison. Earlier wins cannot justify a harmful new change. For lower-is-better metrics, calculate:

```text
portfolio ratio = sum(frequency * head) / sum(frequency * base)
portfolio improvement = 100 * (1 - portfolio ratio)
case regression = 100 * (head / base - 1)
```

Use the frozen target portfolio for the primary score. Also inspect related cases, the frequency-weighted absolute delta, the distribution of changes, and the equal-weight geometric mean of case ratios as a secondary statistic.

- Require passing correctness checks and valid comparisons.
- Accept when both portfolio improvements are at least 1%, with every target and related case regression below 1% in both comparisons.
- An isolated non-protected regression from 1% to below 3% can pass only when both portfolio improvements are at least 5%, neither comparison reaches 3% regression, no related workload family repeatedly regresses, and profiles explain the tradeoff.
- A positive improvement below 1% can pass only when the implementation is equally simple or simpler and every individual regression remains below 1% in both comparisons.
- A protected-case regression of at least 1%, or any individual regression of at least 3%, requires the user's explicit tradeoff decision before publication. Keep the candidate unpublished while that decision is pending.
- Reject a worsening incremental target portfolio or broad regressions that make the overall effect negative. Do not hide them with a secondary aggregate.
- Repeat a matching CI comparison once for near-threshold or conflicting evidence. Treat unresolved variability as inconclusive. Fix deterministic harness failures; retry a clearly transient Actions failure once, then report the blocker if it repeats.

Keep this gate in the optimization decision process. New benchmark workflows should report results without adding performance-failure thresholds. Preserve existing CI limits.

## Publish accepted changes

1. Create a clean publication branch from the frozen upstream base and transfer only the accepted optimization. Inspect its full diff and ancestry against upstream. Require one focused optimization commit and no temporary harness or fork-only ancestry.
2. Verify the measured and published production diffs match and record both SHAs. Run required correctness checks on the publication branch before handing off. If transfer, rebase, or conflict resolution changes production code or its base, remeasure that resulting revision with the same harness before publication.
3. Prepare the complete proposed PR before requesting approval: show the upstream repository and base branch, fork head branch and exact commit SHA, intended diff, draft title/body, correctness results, performance counts and run links, and any tradeoffs. Explain that this skill requires human approval for each upstream PR.
4. Wait for the user's explicit approval of this individual proposal. A passing performance gate, approval of another PR, or general permission to optimize is insufficient. If the proposed diff, base, head SHA, or material evidence changes before publication, present the revised proposal and obtain approval again. If approval is withheld or pending, keep the change unpublished. Record the approval with the proposed PR identity and revision.
5. After approval, invoke `$create-pr` with explicit target `web-infra-dev/rspack`, head repository `kdy1/rspack`, the verified push remote and head branch, upstream base branch, and `draft: true`. Supply the recorded per-PR approval, template, validation results and coverage, incremental and cumulative run URLs, exact metric tables, regression details, and measured-to-published SHA mapping. Resolve the installed skill; if unavailable, report the missing publication dependency instead of bypassing it.
6. Verify the resulting PR's base repository, head repository, branch, SHA, and draft state. Register it with T3's `link_pull_request` and verify it with `list_thread_pull_requests` when available.

Default to independent upstream PRs: start the next optimization from upstream and establish its own baseline. Do not put a second change on top of an unmerged fork head and then open it against upstream trunk; that would include the first change in the second PR. If the user requests a dependent stack, establish supported cross-repository stack routing first and use the applicable stack skill; never create base branches in upstream without authorization.

Before the first dispatch, record a finite attempt limit and Actions-run budget. Use the user's explicit limits; otherwise default to at most three candidate hypotheses and eight workflow dispatches per invocation, stopping at whichever limit is reached first. Count baseline, incremental, cumulative, repeated, and failed runs against that budget. Do not reset it when changing hot paths. Reserve enough remaining runs to validate a candidate before starting it. At the limit, report the evidence and obtain explicit approval for a new finite budget before continuing. Continue within these limits and the user's scope while profiles support another safe hypothesis. Report a gain of at least 5% with exact counts and its run link before continuing. After two failed hypotheses for one hot path, consider another supported target. Stop when the requested work is complete, no supported hypothesis remains, or a correctness, measurement, or permission blocker prevents progress.

## Cleanup and report

Preserve evidence before removing task-owned temporary measurement branches. Never delete publication branches or unrelated branches. Verify published diffs and ancestry exclude temporary infrastructure. Do not remove a permanent fork workflow installed in a separately authorized task.

Report accepted draft PRs, exact base/head metrics and percentages, comparison SHAs and run links, correctness coverage, rejected attempts, pending tradeoffs, and cleanup status. State any runner, dispatch, artifact, or publication blocker without substituting local or CodSpeed results.
