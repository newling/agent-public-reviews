> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12281](https://github.com/ROCm/rocm-libraries/pull/12281)

Reviewed on 2026-09-25 at head `9d4542f57846d4e36317472c26b04924bdf943fa`. The repository, PR, and head branch are public.

Published suggestion branch: [review/pr12281-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12281-suggestions), based on that exact head. The submitted branch is preserved.

| Commit | Review item |
| --- | --- |
| Not implemented | Actionable item 1: automate the GPU output-completeness regression |
| [df28f4d00b9](https://github.com/newling/rocm-libraries/commit/df28f4d00b938d97b53a4f5820ba7736d7f1f2e5) | Suggestion 1: retain solutions when the output is wider than one tile |
| [72c7ccfaa3b](https://github.com/newling/rocm-libraries/commit/72c7ccfaa3b8cb14da706dd4986ac6205191544a) | Suggestion 2: verify the clamped extent in diagnostic output |

These are test-only commits. The second is recorded after the first but has no semantic dependency on it. Both were pushed to the linked branch on 2026-09-25.

## Tests

The submitted TensileLite host library and `tensilelite-tests` built successfully; all submitted `Predicates.*` tests passed, and the suggestion branch rebuilt and passed the expanded predicate suite. Focused deliberate-regression checks and `git diff --check` also produced the expected results. The build and predicate suite were rechecked before publishing the branch; root pre-commit completed with no applicable hooks for this C++ file.

Local validation used ROCm 7.1's `amdclang++`, Ninja, MessagePack, and the required Python dependencies. No local GPU GEMM was run: the changed operation is a CPU-side selection predicate, and these tests construct tensor descriptors without allocating their large tensors. The device measurements in the PR description remain author-reported evidence.

The [public gfx94X TensileLite job](https://github.com/ROCm/rocm-libraries/actions/runs/36064083770/job/107878943275) explicitly ran and passed all five new boundary tests. CI is nevertheless mixed. The [hipBLASLt shard 2 failure](https://github.com/ROCm/rocm-libraries/actions/runs/36064083770/job/107878943415) contains small-matrix failures, including `APIAlgoIndex` cases reporting `Received Segmentation fault signal` and `NO solution found!`. Their 127/129-sized outputs cannot reach the changed threshold. The [race-check job](https://github.com/ROCm/rocm-libraries/actions/runs/36064083770/job/107901300214) fails with `ModuleNotFoundError: No module named 'joblib'`. Those logs do not establish a regression from this patch. Other red gfx1250 and coverage-related statuses were not diagnosed here; this review does not establish an all-green CI result.

## Summary

This changes which GEMM solutions the host considers usable. The output-store predicate now rejects a solution when its estimated per-workgroup output extent reaches the same `0xfffff000` bound that the assembly generator writes into the store descriptor. Previously the predicate admitted the final 4,096-byte interval below `2^32`, although the descriptor could discard stores there. The strict comparison is retained and explicitly tested.

The important design choice is preserving the per-workgroup extent. `computeStoreSrdStart` advances the descriptor base along the output's column dimension, so a large output can remain usable with a sufficiently narrow tile. Sharing the extent helper between evaluation and diagnostics also removes their previous disagreement for outputs narrower than a tile.

I found no correctness defect introduced by the submitted change. Restoring the old threshold in a temporary header copy makes the submitted past-sentinel and exact-sentinel tests fail, which confirms that the tests detect the actual threshold change. CPU predicate tests are useful lowest-level coverage, but the regression strategy should also preserve the observed GPU behavior. An opt-in flag would not help this correction to an existing safety check.

## Actionable items

### 1. Automate the GPU output-completeness regression

`projects/hipblaslt/tensilelite/tests/Predicates_test.cpp:181–261` tests selection decisions without executing a kernel. The output-completeness experiment remains manual, so the automated regressions do not verify that the host limit agrees with the generated descriptor or that the normal dispatch path actually excludes kernels that drop stores. Add a GPU regression alongside the existing large-address cases in `projects/hipblaslt/clients/tests/data/matmul_gtest.yaml:3007`, with a shape definition in `matmul_common.yaml` and a focused validation helper if needed.

Use the reproduced bf16 shape, `M = ldd = 8,388,607`, `N = 256`, `K = 48`, and verify that the affected trailing output elements are written. For example, with A and B filled with ones, alpha 1, and beta 0, the expected result is exactly 48; prefill the checked output region with NaNs and compare it after execution. This avoids a full CPU reference calculation. Confirm failure on the unpatched library and success on the patched one, and require a nonempty set of usable solutions. Exercise the relevant generated-kernel family through normal selection, with coverage that cannot silently disappear when tuning changes the top heuristic choice. An all-supported-solutions sweep is one option; a stable, explicitly checked selection of affected kernel properties may be cheaper. A below-boundary control should retain usable solutions.

[PR #12332](https://github.com/ROCm/rocm-libraries/pull/12332) provides a concrete model: it adds a GPU numerical regression with `integer_exact`, `unit_check: 1`, and all-supported-solutions selection, placed in the nightly suite because of its large allocation. Its [test comments](https://github.com/ROCm/rocm-libraries/blob/9031ffd062a444930add55a6af2cd159bd5c6ba7/projects/hipblaslt/clients/tests/data/matmul_gtest.yaml#L3057) report about 7 seconds for 17 solutions versus 4.3 seconds for one. These are reported measurements for that different defect, not timings for #12281. Here the reproduced shape needs approximately 4 GiB for D and 0.75 GiB for A before C/workspace, and the offered solution pool is much larger. Measure allocation, launch, and validation time before choosing a bounded per-PR test or a nightly sweep; checking the tail itself requires only a small transfer. Runtime expense has not been established as a reason to leave this regression manual.

This recommendation has no implementation commit. Selecting and verifying stable kernel coverage and a suitable CI budget requires a GPU experiment; the completed local changes only add host-side tests.

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

The accompanying implementation is on [review/pr12281-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12281-suggestions): [df28f4d00b9](https://github.com/newling/rocm-libraries/commit/df28f4d00b938d97b53a4f5820ba7736d7f1f2e5) adds the wide-output test and [72c7ccfaa3b](https://github.com/newling/rocm-libraries/commit/72c7ccfaa3b8cb14da706dd4986ac6205191544a) adds the diagnostic test. Both were validated against the submitted code and against the corresponding deliberate regression. The reproducing tests are retained in those commits. No production-code fix, GPU rebuild, exhaustive suite, or custom-kernel change was made. The suggestion branch is published; no review was posted to the PR.
