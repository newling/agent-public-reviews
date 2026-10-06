This is a review from an agent with an automatic prompt from the reviewer

**Publication update, 2026-10-06:** The [suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr13031-followup-20261006) and its fix [`c7a5b39e5f2`](https://github.com/newling/rocm-libraries/commit/c7a5b39e5f280774ee1071f5b431cb1b628347c1) are published. The original review below is preserved; the [audited index](review_fast_check_stack_audit_20261006.md) contains the completed stack review and current handoff.

**PR reviewed:** [ROCm/rocm-libraries#13031](https://github.com/ROCm/rocm-libraries/pull/13031)

**Reviewed head:** [a84d460b8a651810ce9e0ce29f74af1bb4940da3](https://github.com/ROCm/rocm-libraries/commit/a84d460b8a651810ce9e0ce29f74af1bb4940da3)

**Scope, 2026-10-06:** Follow-up on the previous checker finding and numerical failure, inspection of changes since the October 5 stack snapshot, and current dependency/CI verification. This is not a complete code review of the eight layers following #12876, or of the independent #13027 and #13060. The repository and all checked PR heads are public. PR descriptions, source, existing local notes and CI were consulted; GitHub review bodies and discussion comments were not.

**Local suggestion branch:** `review/pr13031-followup-20261006`, based directly on the reviewed head. The submitted branch is preserved.

| Item | Local commit | Change |
| --- | --- | --- |
| Empty-output verifier crash | [`c7a5b39e5f280774ee1071f5b431cb1b628347c1`](https://github.com/newling/rocm-libraries/commit/c7a5b39e5f280774ee1071f5b431cb1b628347c1) | Port the previous empty-output fix and regression onto the current stack tip, preserving the expanded scale documentation. |
| gfx950 f32 numerical failure | None | The submitted stack now quarantines it under ROCM-32277; diagnosis and a kernel repair remain separate work. |

## Tests

The submitted checker passed all 50 self-tests in a focused ROCm 7.1/gfx1201 build; the suggestion branch passed those tests plus the empty-result regression. `git diff --check` passed.

The build compiles the submitted checker, device initializer and `fast_check_gtest.cpp`. MX data generation is disabled in this standalone configuration, so its conditional self-test is excluded. The tests exercise host arithmetic, small GPU verifier operations, placement, repeated-check bookkeeping and side-output helpers. They do not run hipBLASLt GEMM kernels or establish gfx950 correctness.

Separate processes calling `fast_check_expected` followed by `fast_check_result_device` with default types, null unused operands, K=0, and (M,N) equal to (0,5), (5,0), or (0,0) all terminated with SIGFPE on the submitted tip. All pass with the fix. The committed regression also covers zero batch count, nonzero K and preservation of an existing error status.

Current #13031 Math CI, multi-architecture, hipBLASLt ASAN, multi-architecture ASAN, pre-commit and clang-tidy summaries pass. The [Math CI precheckin status](https://math-ci.amd.com/job/rocm-libraries/job/precheckin/job/hipblaslt/job/PR-13031/10/stages/) is successful for build 10. Its full console could not be retrieved locally because the request timed out; that status was verified through GitHub.

Two project-coverage checks remain failed. The [PR-bot failure](https://github.com/ROCm/rocm-libraries/actions/runs/37386759870/job/112021797917) explicitly reports `pre-commit=cancelled`; a later pre-commit check on this head passed. Cancelled duplicate workflow jobs remain in the rollup alongside successful replacements. The coverage failures were not diagnosed in this pass.

## Summary

The stack adds an optional verifier for integer-valued GEMMs, using random modular projections to avoid a full CPU matrix multiplication. Later layers add controlled buffer placement, repeated per-solution checks, exactness bounds, side outputs, large-size and configuration coverage, an on-demand stress runner, and MX block-scale data.

The direct tests are valuable: they inject corruptions and check that the verifier detects them. Separating expected input projections from repeated output scans also makes checking many solutions practical. Appropriate validation combines these small helper tests with representative real GEMMs on the affected hardware; neither alone covers the whole stack.

Although three PR heads changed, the combined source differs from the previous tip [`3364b793ac111427a0aa2a8891ca7dcd157ef561`](https://github.com/ROCm/rocm-libraries/commit/3364b793ac111427a0aa2a8891ca7dcd157ef561) only by five added lines in `known_bugs.yaml`. There are no new checker or kernel changes in that comparison.

## Actionable items

### Handle empty output before sizing device work

At [`projects/hipblaslt/clients/common/src/fast_check.cpp:1390`](https://github.com/ROCm/rocm-libraries/blob/a84d460b8a651810ce9e0ce29f74af1bb4940da3/projects/hipblaslt/clients/common/src/fast_check.cpp#L1390), chunk sizing divides by M; the corresponding column calculation divides by N. The helper still lacks an empty-output return. A valid empty output can therefore terminate the test process, even with no device data to verify. This is the previously identified helper issue, reproduced on the current tip, rather than a newly discovered failure in the positive-dimension YAML cases.

Commit [`c7a5b39e5f280774ee1071f5b431cb1b628347c1`](https://github.com/newling/rocm-libraries/commit/c7a5b39e5f280774ee1071f5b431cb1b628347c1) returns before operand reads and device sizing when M, N or batch count is zero. It preserves earlier input-validation failures, documents the behavior, and adds `FastCheckDevice_pre_checkin.empty_results_launch_nothing`. This is the current-tip equivalent of the previous root-level suggestion [`67ca40766d0896f69c15361a6f4856c4bd216152`](https://github.com/newling/rocm-libraries/commit/67ca40766d0896f69c15361a6f4856c4bd216152); use the version appropriate to the landing point rather than applying both.

## Suggestions

No additional implementation suggestions from this follow-up scope.

## Commentary

The previous numerical failure now has a recorded disposition. At [`projects/hipblaslt/clients/tests/data/known_bugs.yaml:66`](https://github.com/ROCm/rocm-libraries/blob/a84d460b8a651810ce9e0ce29f74af1bb4940da3/projects/hipblaslt/clients/tests/data/known_bugs.yaml#L66), the stack quarantines `matmul_fast_check_streamk_batches` for f32 on gfx950 under ROCM-32277, with a November 1 review date and removal tied to its fix. This follows the repository's tracked-quarantine convention. It excludes the whole named f32/gfx950 configuration, including both listed matrix shapes and every solution, because the entry does not narrow dimensions or solution identity.

The updated [#13022 description](https://github.com/ROCm/rocm-libraries/pull/13022) reports failures in 4 of 30 test runs and independent reproduction in 4 of 80 single `hipblaslt-bench` launches, through two Stream-K solutions. That is useful evidence beyond the original checker report, but those reproductions were not repeated in this review. The passing CI result after quarantine does not establish a kernel repair. No speculative kernel change is supplied.

All nine current heads contain their predecessor:

| PR | Addition | Current head |
| --- | --- | --- |
| [#12876](https://github.com/ROCm/rocm-libraries/pull/12876) | Base verifier | [`9ea6be093cc8`](https://github.com/ROCm/rocm-libraries/commit/9ea6be093cc8ef21e7b4a6b62431e0d2206c0035) |
| [#12960](https://github.com/ROCm/rocm-libraries/pull/12960) | Placement across 4 GiB boundaries | [`8351692d684b`](https://github.com/ROCm/rocm-libraries/commit/8351692d684bd9a3ad55b6d0e44a8fae913aedc1) |
| [#13005](https://github.com/ROCm/rocm-libraries/pull/13005) | Every solution and iteration | [`c6ec02e372e5`](https://github.com/ROCm/rocm-libraries/commit/c6ec02e372e5a3452f83c9e8e6d943406bfdc22c) |
| [#13013](https://github.com/ROCm/rocm-libraries/pull/13013) | Large-K exactness | [`de8179d56d3d`](https://github.com/ROCm/rocm-libraries/commit/de8179d56d3dc8c790668eb505ec74028050a720) |
| [#13015](https://github.com/ROCm/rocm-libraries/pull/13015) | Scales and side outputs | [`396f1c517591`](https://github.com/ROCm/rocm-libraries/commit/396f1c5175913d0ddd19eb48d12e948ad6cad96c) |
| [#13021](https://github.com/ROCm/rocm-libraries/pull/13021) | Size thresholds | [`c8d9134aa913`](https://github.com/ROCm/rocm-libraries/commit/c8d9134aa913d7cc2039c272545e463d9c1107d9) |
| [#13022](https://github.com/ROCm/rocm-libraries/pull/13022) | Edge configurations | [`97e1481b4512`](https://github.com/ROCm/rocm-libraries/commit/97e1481b451214c125b22a7b5b9274d1d3cb0f7f) |
| [#13025](https://github.com/ROCm/rocm-libraries/pull/13025) | On-demand stress runner | [`f0d1510b27bc`](https://github.com/ROCm/rocm-libraries/commit/f0d1510b27bc3c7fc158bb628b319c5bf6a80694) |
| [#13031](https://github.com/ROCm/rocm-libraries/pull/13031) | MX block scales | [`a84d460b8a65`](https://github.com/ROCm/rocm-libraries/commit/a84d460b8a651810ce9e0ce29f74af1bb4940da3) |

The first six heads are unchanged from the previous snapshot. The last three were restacked with the quarantine. Independent [#13027](https://github.com/ROCm/rocm-libraries/pull/13027), the rocisa immediate-lowering fix, and [#13060](https://github.com/ROCm/rocm-libraries/pull/13060), the address-carry lint, target develop directly and do not depend on this stack. The extracted FNUZ client-negation fix [#13119](https://github.com/ROCm/rocm-libraries/pull/13119) remains open and is now ready for review rather than a draft.

The suggestion branch contains one validated commit. Full reviews of later-layer ownership, integration, runner behavior and MX generation remain outstanding. No branch was pushed, review posted or PR changed.
