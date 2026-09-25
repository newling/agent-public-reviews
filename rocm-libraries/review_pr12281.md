> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12281](https://github.com/ROCm/rocm-libraries/pull/12281)

Reviewed on 2026-09-25 at head `9d4542f57846d4e36317472c26b04924bdf943fa`. The repository, PR, and head branch are public.

Published suggestion branch: [review/pr12281-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12281-suggestions), based on that exact head. The submitted branch is preserved.

| Commit | Review item |
| --- | --- |
| [8f189b6d5bd](https://github.com/newling/rocm-libraries/commit/8f189b6d5bd55404bbb37bcb8a42af4ed6d82807) | Actionable item 1: automate the GPU output-completeness regression |
| [df28f4d00b9](https://github.com/newling/rocm-libraries/commit/df28f4d00b938d97b53a4f5820ba7736d7f1f2e5) | Suggestion 1: retain solutions when the output is wider than one tile |
| [72c7ccfaa3b](https://github.com/newling/rocm-libraries/commit/72c7ccfaa3b8cb14da706dd4986ac6205191544a) | Suggestion 2: verify the clamped extent in diagnostic output |

These are test-only commits. The three tests have no semantic dependency on one another. All three are on the linked suggestion branch.

## Tests

The submitted host library and predicate tests passed; the suggestion branch builds and passes all 13 `Predicates.*` tests and the new GPU regression on MI300X. Focused deliberate-regression checks behaved as expected. Formatting, root/component pre-commit, and whitespace checks completed; the root hooks have no applicable checks for these files.

GPU validation used ROCm 7.1's `amdclang++` for the host/client and freshly generated gfx942 bf16 NN kernels, with execution on ROCm 7.2 and MI300X. Generation covered the 18 non-experimental logic files selected by `gfx942*/*/*Ailk_Bljk_BBS*`. The test executed 1,092 supported solutions below the boundary and 922 above it, within its 128 MiB workspace cap. Both shapes passed in 19.7 seconds (23.5 seconds including process startup), using approximately 4.9 GiB of explicitly allocated device memory. This is targeted bf16 NN coverage, not a full-library numerical sweep. No gfx950 machine was available; that hardware validation remains outstanding.

For the negative control, only `BufferStoreOffsetLimitCheck::BufferOOBBytes` was restored to `0x100000000ull`; the generated code objects and test were identical. The below-boundary control passed, then the larger shape failed on a `MT160x256x64` solution: row 8,388,480 in the last column still contained the NaN poison `0x7fc0`, instead of bf16 48 (`0x4240`). The launch and stream synchronization both reported success. This establishes that the test detects dropped stores, independently of HIP error reporting. The production header was restored after this experiment.

The committed regression runs with `hipblaslt-test --gtest_filter='nightly_BufferStoreBoundary.*'`. Its suite name is included by the existing shared comprehensive/full category filters; it is enabled for gfx942 and gfx950 and skips other architectures or insufficient device memory. The evidence above is a completed GPU run, not a skip.

The [public gfx94X TensileLite job](https://github.com/ROCm/rocm-libraries/actions/runs/36064083770/job/107878943275) explicitly ran and passed all five new boundary tests. CI is nevertheless mixed. The [hipBLASLt shard 2 failure](https://github.com/ROCm/rocm-libraries/actions/runs/36064083770/job/107878943415) contains small-matrix failures, including `APIAlgoIndex` cases reporting `Received Segmentation fault signal` and `NO solution found!`. Their 127/129-sized outputs cannot reach the changed threshold. The [race-check job](https://github.com/ROCm/rocm-libraries/actions/runs/36064083770/job/107901300214) fails with `ModuleNotFoundError: No module named 'joblib'`. Those logs do not establish a regression from this patch. Other red gfx1250 and coverage-related statuses were not diagnosed here; this review does not establish an all-green CI result.

## Summary

This changes which GEMM solutions the host considers usable. The output-store predicate now rejects a solution when its estimated per-workgroup output extent reaches the same `0xfffff000` bound that the assembly generator writes into the store descriptor. Previously the predicate admitted the final 4,096-byte interval below `2^32`, although the descriptor could discard stores there. The strict comparison is retained and explicitly tested.

The important design choice is preserving the per-workgroup extent. `computeStoreSrdStart` advances the descriptor base along the output's column dimension, so a large output can remain usable with a sufficiently narrow tile. Sharing the extent helper between evaluation and diagnostics also removes their previous disagreement for outputs narrower than a tile.

I found no correctness defect introduced by the submitted change. Restoring the old threshold in a temporary header copy makes the submitted past-sentinel and exact-sentinel tests fail, which confirms that the tests detect the actual threshold change. CPU predicate tests cover the selection formula; the additional GPU test on the suggestion branch preserves the observed missing-store behavior. An opt-in flag would not help this correction to an existing safety check.

## Actionable items

### 1. Automate the GPU output-completeness regression

`projects/hipblaslt/tensilelite/tests/Predicates_test.cpp:181–261` tests selection decisions without executing a kernel. The submitted PR leaves the output-completeness experiment manual, so its automated regressions do not verify that the host limit agrees with the generated descriptor or that normal dispatch excludes kernels that drop stores.

Implemented in [8f189b6d5bd](https://github.com/newling/rocm-libraries/commit/8f189b6d5bd55404bbb37bcb8a42af4ed6d82807), in `projects/hipblaslt/clients/tests/src/buffer_store_boundary_gtest.cpp:151`, with registration in `clients/tests/src/CMakeLists.txt:15`. The test uses bf16 NN `M = ldd = 8,388,607`, `N = 256`, `K = 48`, plus a below-boundary control with `M = 8,388,599`. It enumerates algorithms and applies the normal support check, then runs every supported candidate within a 128 MiB workspace budget. A and B contain exact ones, alpha is 1, and beta is 0. Before every launch it poisons the last 4,096 output elements with NaNs, then copies back 8 KiB and checks that every value is exactly 48. C aliases D to avoid another 4 GiB allocation. The constant expected value avoids a full CPU GEMM.

Both shapes must execute at least one solution, and at least one control-supported solution must be excluded for the larger shape. That assertion prevents tuning from silently removing the boundary-sensitive coverage. Algorithm indices appear only in diagnostics and comparisons within one run; the test does not pin an index across library rebuilds. The failure identifies the solution, row, expected bits, and observed bits.

[PR #12332](https://github.com/ROCm/rocm-libraries/pull/12332) provided the model of a nightly GPU regression sweeping supported solutions. This implementation uses a dedicated gtest helper so validation reads only the affected tail. The before/after MI300X experiment and measured cost are recorded above. The remaining handoff is to include this commit and confirm the gfx950 nightly run; no gfx950 result is claimed here.

## Suggestions

### 1. Exercise outputs wider than the solution's tile

In `projects/hipblaslt/tensilelite/tests/Predicates_test.cpp:180–261`, every new case has `N <= MacroTile1`. Consequently, replacing `min(MacroTile1, N)` with `N` in `storeExtentBytes` still passes all five submitted tests. That replacement would reject usable solutions for outputs larger than the descriptor bound, precisely the behavior the per-workgroup calculation is meant to preserve.

Add a case with bf16 `M = ldd = 12,667,846`, `N = 256`, and compare tiles of width 128 and 256. The first solution should remain selectable and the second should be rejected. Implemented in [df28f4d00b9](https://github.com/newling/rocm-libraries/commit/df28f4d00b938d97b53a4f5820ba7736d7f1f2e5) as `BufferStoreOffsetLimitCheck_WideOutputUsesTileWidth`. It passes against the submitted implementation and fails when the helper uses the entire output width. This is additional protection for an existing correct formula, not a defect in that formula.

### 2. Check the changed diagnostic text

`projects/hipblaslt/tensilelite/include/Tensile/ContractionProblemPredicates.hpp:1594–1605` corrects `debugEval`, but the submitted tests only call `operator()`. An evaluation-only suite cannot detect a return to the wrong extent or threshold in the explanation presented to a developer.

Add a failing narrow-output case and check both the return value and the reported byte extent. Implemented in [72c7ccfaa3b](https://github.com/newling/rocm-libraries/commit/72c7ccfaa3b8cb14da706dd4986ac6205191544a) as `BufferStoreOffsetLimitCheck_DebugReportsClampedExtent`: bf16 `M = ldd = 300,000,000`, `N = 8`, and `MacroTile1 = 256` must report `D:4800000000<0xfffff000`. Using a rejected case ensures the diagnostic is printed without relying on verbose-debug environment settings. The test passes on the submitted implementation and fails if the diagnostic multiplies by the unclamped tile width, producing `153600000000` instead.

### 3. Shorten the description and qualify its hardware claims

The PR description's Technical Details and Risk level sections repeat the per-workgroup explanation and the same candidate-count evidence. The sentence claiming that every removed solution would return a partially unwritten result is also broader than the measurements: the exact-sentinel case is deliberately excluded conservatively, and the evidence covers specific shapes and devices. Its statement that automated checks are pending is now stale.

The repository prose guide asks for current evidence, bounded claims, and removal of repetition. A concrete [recommended description](review_pr12281_description.md) preserves the required headings, issue reference, measured example, and custom-kernel limitation while addressing those points. This is a local draft, with no PR edit performed.

## Commentary

The predicate retains its existing serialized type and `value` field; the threshold is not added to the stored library format. Registration and mapping still construct the same predicate, so a rebuilt host applies the revised limit when loading existing solution libraries. No new ownership or lifetime behavior is introduced, and the helper retains the existing tensor-layout and arithmetic assumptions.

The global threshold remains an assumption about generated kernels. Hand-written kernels with `BufferOOB = 0x80000000` are still too permissive under this predicate. That is a pre-existing limitation, explicitly excluded in the PR description and tracked there as ROCM-31258; changing their metadata or descriptors would be a separate implementation decision. The strict equality rejection is likewise an explicit conservative choice, not an unnoticed off-by-one.

The accompanying implementation is on [review/pr12281-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12281-suggestions): [8f189b6d5bd](https://github.com/newling/rocm-libraries/commit/8f189b6d5bd55404bbb37bcb8a42af4ed6d82807) adds the GPU output test, [df28f4d00b9](https://github.com/newling/rocm-libraries/commit/df28f4d00b938d97b53a4f5820ba7736d7f1f2e5) adds the wide-output predicate test, and [72c7ccfaa3b](https://github.com/newling/rocm-libraries/commit/72c7ccfaa3b8cb14da706dd4986ac6205191544a) adds the diagnostic test. Each was validated against the submitted implementation and its corresponding deliberate regression. All reproducers are retained in those commits. No production-code or custom-kernel change was made, and exhaustive testing and gfx950 execution remain outside the completed validation. The suggestion branch and this review are published; no review was posted to the PR.
