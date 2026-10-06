This is a review from an agent with an automatic prompt from the reviewer

**Publication update, 2026-10-06:** The [suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr12876-suggestions) and its fix [`67ca40766d0`](https://github.com/newling/rocm-libraries/commit/67ca40766d0896f69c15361a6f4856c4bd216152) are published. The original review below is preserved; the [audited index](review_fast_check_stack_audit_20261006.md) contains the completed stack review and current handoff.

**PR reviewed:** [ROCm/rocm-libraries#12876](https://github.com/ROCm/rocm-libraries/pull/12876)

**Reviewed head:** [9ea6be093cc8ef21e7b4a6b62431e0d2206c0035](https://github.com/ROCm/rocm-libraries/commit/9ea6be093cc8ef21e7b4a6b62431e0d2206c0035)

**Scope:** Initial review of the base verifier, its matmul integration and tests, plus dependency mapping and CI triage for the nine-PR stack. The later layers have not received complete code reviews. Repository and PR heads are public. Existing PR reviews and discussion comments were not consulted.

**Local suggestion branch:** `review/pr12876-suggestions`, based directly on the reviewed head. The original PR branch is unchanged.

| Item | Local commit | Change |
| --- | --- | --- |
| Empty results | `67ca40766d0896f69c15361a6f4856c4bd216152` | Handle empty outputs before reading operands or sizing device work; document the behavior and add a regression test. |
| Stack CI numerical failure | None | Requires diagnosis on gfx950 before choosing a source change. |

## Tests

The focused verifier build and submitted host/device self-tests passed on gfx1201 with ROCm 7.1; the suggestion branch also passed the new empty-result regression and all existing verifier tests. `git diff --check` passed.

This build compiled the actual `fast_check.cpp` and `fast_check_gtest.cpp` sources into a standalone gtest executable. It did not rebuild the complete client or generate GEMM device libraries. Local validation covers the verifier's GPU kernels, not the large GEMMs or gfx950 solution reported below. The same empty-result probe was also compiled against the checker sources at stack tip [3364b793ac111427a0aa2a8891ca7dcd157ef561](https://github.com/ROCm/rocm-libraries/commit/3364b793ac111427a0aa2a8891ca7dcd157ef561).

CI observed on 2026-10-05: #12876 has successful Math CI and Multi-Arch summaries, with failed gfx1250 FFM and project-coverage checks and an action-required gfx1250 hardware check. Several later layers have failed bot, clang-tidy or ASAN summaries. In [#12960's ASAN job](https://github.com/ROCm/rocm-libraries/actions/runs/37237342635/job/111539122651), the failure occurred during `Pull DVC files for rocm-libraries`; configuration and compilation were skipped. That failure does not establish a source defect. The remaining bot, clang-tidy and coverage failures have not been attributed in this pass.

## Summary

The verifier compares random linear combinations of the output with combinations calculated from the inputs, using exact modular arithmetic. This replaces the cubic-cost CPU reference with matrix-sized passes for ordinary cases. A second set of combinations helps locate incorrect elements. Padding checks and output sentinels test a different property: whether a kernel writes outside the output or leaves elements unwritten.

Keeping expected fingerprints separate from each solution's output scan is useful for tests that exercise many solutions. The direct corruption tests also provide meaningful evidence: they check single-element faults, cancelling errors, shifted rows, duplicated columns, sentinels, and output rounding, rather than accepting agreement on correct results alone.

For this test-infrastructure change, direct host arithmetic tests, small device-helper tests and representative GEMMs are the appropriate levels. The new behavior is opt-in and has direct tests, so no missing-test waiver is needed for the base functionality. Adjacent validation should concentrate on the changed matmul paths: simultaneous `unit_check`, C/D aliasing, multiple solutions, and zero-work cases. Unrelated TensileLite suites would not establish these properties.

## Actionable items

### Handle an empty result before constructing GPU work

At [`clients/common/src/fast_check.cpp:1222`](https://github.com/ROCm/rocm-libraries/blob/9ea6be093cc8ef21e7b4a6b62431e0d2206c0035/projects/hipblaslt/clients/common/src/fast_check.cpp#L1222), chunk sizing divides by `M`; the corresponding calculation at line 1227 divides by `N`. Neither the expected-value pass nor the device entry point rejects or handles zero output dimensions first. Calling the new helper with `M=0, N=5, K=0`, supported default types, and null unused operands terminates the process with SIGFPE. Separate probes for zero N and both zero dimensions fail the same way at the stack tip.

The existing `empty_buffers_launch_nothing` test covers zero-length fill/scan helpers, but never calls the result verifier with an empty output. This is a contract gap in the new helper, not evidence that one of the submitted positive-dimension YAML cases crashes.

Local commit `67ca40766d0896f69c15361a6f4856c4bd216152` makes empty outputs require no operand reads or device work while preserving an existing error from the expected-value pass. Its test covers zero M, zero N and zero batch count, each with zero and nonzero K and null unused operands. The regression failed on the submitted implementation and passes with the fix. It runs in the existing pre_checkin suite.

### Diagnose the numerical failure in the stack's batched f32 case

The case introduced at [`clients/tests/data/matmul_gtest.yaml:4595` in #13022](https://github.com/ROCm/rocm-libraries/blob/8207be763cfcac83fa9b7310676b775fa381bb3a/projects/hipblaslt/clients/tests/data/matmul_gtest.yaml#L4595) fails in [#13031's Math CI build 9, gfx950 test stage](https://math-ci.amd.com/job/rocm-libraries/job/precheckin/job/hipblaslt/job/PR-13031/9/execution/node/1624/log/?consoleFull). This is a numerical test failure, separate from the earlier DVC failure.

The failing configuration is `matmul_fast_check_streamk_batches`, f32 NT, M=4099, N=2053, K=1025, three batches, alpha=2, beta=-2 and `sparse_k` input. The report names solution 213 of 1167, library index 73267, on iteration 2 of 3. Its kernel name contains `MT64x64x32`, `DTLA1` and `DTLB1`. The probes disagree in three rows and twelve columns. For batch 0, row 4096, column 3, the report gives expected −32 and actual −2; column 7 gives expected −28 and actual 0. Only this solution and iteration appear in the aggregate failure report.

Replay the same solution with the same CI artifacts on gfx950, preserve the operands and output on a failing launch, and compare the reported elements against an independent reference. Use that evidence to determine whether the kernel or the harness is wrong, then fix the cause or record a narrowly scoped, tracked known-bug plan. A passing rerun alone would not explain this result. No implementation is supplied for this item because the failing log does not establish the root cause.

## Suggestions

No additional suggestions from this initial scope.

## Commentary

The current heads form a contiguous stack: every later head contains the previous head. The merge order and division of work are:

| PR | Main addition |
| --- | --- |
| [#12876](https://github.com/ROCm/rocm-libraries/pull/12876) | Modular GEMM verification and padding checks |
| [#12960](https://github.com/ROCm/rocm-libraries/pull/12960) | Controlled placement across 4 GiB address boundaries |
| [#13005](https://github.com/ROCm/rocm-libraries/pull/13005) | Repeated checks of every solution |
| [#13013](https://github.com/ROCm/rocm-libraries/pull/13013) | Accumulator bounds and data patterns for large K |
| [#13015](https://github.com/ROCm/rocm-libraries/pull/13015) | Scales, E, amaxD and bias gradients |
| [#13021](https://github.com/ROCm/rocm-libraries/pull/13021) | Size thresholds, memory checks and a stress tier |
| [#13022](https://github.com/ROCm/rocm-libraries/pull/13022) | Edge shapes, batches and specific kernel configurations |
| [#13025](https://github.com/ROCm/rocm-libraries/pull/13025) | An on-demand corruption-hunt runner |
| [#13031](https://github.com/ROCm/rocm-libraries/pull/13031) | MX block scales |

The accumulator-range guard arrives in #13013. It should be considered when evaluating the combined stack's exactness assumptions; the base verifier alone does not have that preflight guard. The root description lists #13027 and #13060 separately from this stack, so they are outside this review's scope.

The local branch contains one focused commit for the empty-output item. Full reviews of placement lifetime, repeated-launch state, side-output verification, the on-demand runner and MX data generation remain outstanding. No branch was pushed, review posted or PR changed.
