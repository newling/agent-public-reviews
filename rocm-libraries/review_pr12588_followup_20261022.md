This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12588](https://github.com/ROCm/rocm-libraries/pull/12588)

Reviewed head: [bb3a59b8adc](https://github.com/ROCm/rocm-libraries/commit/bb3a59b8adc6c41f1129ad075c6b0dba005329a3), still the submitted head when checked. This is a new review, independent of the previous ones, with one added step: it first checks whether the previous combined review's items were addressed. Existing GitHub review threads and comments were not read.

Suggestion branch [review/pr12588-followup-20261022](https://github.com/newling/rocm-libraries/tree/review%2Fpr12588-followup-20261022), based directly on the reviewed head. [Compare both commits](https://github.com/newling/rocm-libraries/compare/bb3a59b8adc6c41f1129ad075c6b0dba005329a3...76eb0415f05960087f8ab8a118977b0583db50bf).

| Commit | Review item |
| --- | --- |
| [f18d43963fb](https://github.com/newling/rocm-libraries/commit/f18d43963fbf94a2af5d94a1223488eb6e28c26c) | Keep the XCC preparation test off a private tensilelite template (Windows link failure). |
| [76eb0415f05](https://github.com/newling/rocm-libraries/commit/76eb0415f05960087f8ab8a118977b0583db50bf) | Decline only fused calls that carry an all-to-all prefix. |

## Tests

On gfx1201, with a device library generated from this tree's gfx1201 fp16 and fp32 logic files, the focused host and GPU suites (`TuningTune*`, `TuningScratch*`, `TuningCache*`, `TuningStore*`, `CandidateSearch*`, `CandidatePreparation*`, `RotatingFootprint*`, `RotatingBuffer*`) give 133 passed, 3 skipped and 0 failed, both on the submitted head and on the suggestion branch. The skips are the FP8 FNUZ case, the grouped-GEMM case and an XF32 case, none of which has a solution in that reduced library. `hipblaslt-bench` in tune mode and then cache mode with a bias on fp16 1024×512×1024 tunes once over the default exhaustive candidate list (about 45 seconds) and replays as a cache hit on the next run.

The new Windows-lane link failure described below is reproduced from the CI log only; no Windows build was run locally. The mutation check for the replacement test (removing the XCC assignment) fails it as intended. Whitespace and clang-format checks pass on the branch. `tensile_host.cpp` was also compiled with fused all-to-all enabled to check the second commit. Fusion-enabled execution, multi-rank behavior, block-scaled (MX) problems and FP8 were not run.

CI at this head: the [Windows gfx110X math-libs build](https://github.com/ROCm/rocm-libraries/actions/runs/39723423880/job/119676485777) fails, the hipBLASLt project coverage check fails, the FFM gfx1250 tensilelite status fails, and the [gfx1250-strict job](https://github.com/ROCm/rocm-libraries/actions/runs/39723422556/job/119641943456) was still pending. The Linux builds, pre-commit, clang-tidy and the ASAN lanes pass. Only the Windows failure was investigated; its cause is the first item below.

## Summary

This head adds first-call tuning on the shared measurement loop, with scratch isolation, a latch for failed attempts and replay through the cache. Since the previous combined review it has taken in most of that review's fixes and made several design changes on its own: candidate enumeration now includes the heuristic's size-independent top-up, the rotation block count comes from rules moved into the shared benchmark header, and fused all-to-all calls are declined. The benchmark entry point is now edited only to call those shared rules. I checked that the move preserves its arithmetic: for 2,000,000 random strided-tensor and block-footprint cases (single-batch strides set as the benchmark sets them), the shared helpers matched the former expressions exactly, and a before/after benchmark run planned the same 86 blocks.

Status of the previous review's items:

| Earlier item | Status at this head |
| --- | --- |
| Copy the gradient auxiliary input into every scratch block | Addressed. Seeded in every block and overlapping layouts are declined. An end-to-end numerical gradient dispatch case is still absent. |
| Prepare candidate XCC arguments through the normal launch path | Addressed in the library, but its regression test breaks the Windows link (first item below). |
| Exclude fused communication from isolated tuning | Addressed by declining before tuning. The predicate is broader than its name (second commit); the default build cannot execute the decline. |
| Stop the search after a failure reported while measuring | Addressed. The shared search ends and the new cases pass. |
| Make the budget tests deterministic | Addressed. The first test reads the budget as spent through an injection stage, and the second skips when the heuristic offers one algorithm. Both executed and passed here on a multi-candidate library; on a one-candidate device the second is skipped, so it exercises nothing there. |
| Let the cache diagnostics test run with one algorithm | Addressed. |
| Share the heuristic's candidate fallback and order | Addressed. The top-up moved unchanged into a helper that both entry points call, and the test compares the lists at caps of 1, 16 and 256. |
| Share the benchmark's rotation footprint | Addressed for the block count and for bias, scales and the alpha vector (see the first suggestion for block-scaled scales). |
| Share the benchmark's workspace and timer choices | Not addressed (second suggestion). |

## Actionable items

### Keep the XCC preparation test off a private tensilelite template

[candidate_preparation_gtest.cpp:25](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/clients/tests/src/candidate_preparation_gtest.cpp#L25) calls `ContractionSolution::calculateInternalArgs<false>` to read back the packed XCC value. That member template is instantiated inside the tensilelite library and is not exported, so on Windows `hipblaslt-test.exe` fails to link with `undefined symbol: ContractionSolution::calculateInternalArgs<0>`, referenced from this test. This is what fails the [Windows gfx110X math-libs build](https://github.com/ROCm/rocm-libraries/actions/runs/39723423880/job/119676485777) and, through it, the multi-arch summary. The test originates in the previous review's XCC change, so the defect came from that suggestion rather than from the author's code.

[f18d43963fb](https://github.com/newling/rocm-libraries/commit/f18d43963fbf94a2af5d94a1223488eb6e28c26c) checks the parameter that `prepareCandidateXcc` sets instead of packing arguments: a nonzero value is the mapping and zero is the candidate's own, so the parameter carries the choice. The test still starts from a stale value, alternates fallback and ordinary candidates, and fails if the assignment is removed (checked by removing it; the value stays 4 and 1 instead of 1 and 0). The test is renamed because it no longer packs arguments. It links on Linux and passes; the Windows link itself needs the hosted build to confirm.

## Suggestions

### Use the existing all-to-all predicate for the tune-mode decline

[tensile_host.cpp:4639](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L4639) returns true for any non-null fused epilogue descriptor. Every other site that acts on the descriptor, such as the [Tensile problem setup](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L2331), resolves it and checks `hasA2APrefix`. A descriptor without the prefix would be declined from tuning even though it never talks to a peer. [76eb0415f05](https://github.com/newling/rocm-libraries/commit/76eb0415f05960087f8ab8a118977b0583db50bf) uses the established test. It was checked by compiling with fusion enabled only; the default build has no way to execute the decline, so a fusion-enabled lane with a coordinated multi-rank check would be the first real coverage.

### Make the benchmark's workspace and timer choices explicit for tune mode

Tune mode allocates and prepares each candidate with [the caller's full workspace allowance](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L5093) and times with [GPU events](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L5013). The benchmark's ordinary path sizes measurement workspace from each candidate's requirement and, unless `--use_gpu_timer` is passed, [uses synchronized CPU timing](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/clients/bench/src/client.cpp#L685). The PR text now says tune mode matches the explicit GPU-timer option, which is accurate, but "measures as `hipblaslt-bench` does" reads as the default. Workspace size can change Stream-K work distribution, so equal solution indexes do not by themselves mean equal launches. No winner change was measured. Either state both choices as deliberate differences in the how-to, or add them to the shared measurement settings so both callers read one preset without changing the benchmark's defaults.

### Count block-scaled scale buffers in the rotation footprint

The comment at [tensile_host.cpp:4487](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L4487) says a block-scaled scale is "in neither" the benchmark's footprint nor tune mode's. The benchmark does count it: [size_scaleAVec is set from blockScaleBufferSize](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/clients/common/include/testing_matmul.hpp#L2224) and flows into [the footprint](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/clients/common/include/testing_matmul.hpp#L2291), and the benchmark also rotates those buffers. For block-scaled (MX) problems tune mode therefore plans a different block count from the benchmark, which is the mismatch the rotation change set out to remove. Only the sizes are needed for the footprint, not the caller's layout, so tune mode could count them without rotating them. This is established from the source; no block-scaled problem was run, because the test device does not support those formats.

### Add a numerical gradient case

The gradient epilogue's auxiliary input is now seeded and its layouts are covered by scratch-plan and copy tests, but no test runs a gradient epilogue through tune mode and compares the output. The copy tests establish that the input is prepared, not that the derivative kernel produces the right result from it. A small DGELU case in a device lane would close that.

## Commentary

The decision to share candidate preparation, the heuristic's top-up and the rotation rules rather than reimplement them is working: the 86-versus-64 block example from the description is reproduced by a direct test, and the shared formulas can be compared against the benchmark's own sizing without a GPU. The remaining differences (workspace, timer default, block-scaled footprint) are all places where the two callers still choose independently.

The budget tests now depend on an injection stage and a skip. That keeps them from flaking, but a CI device whose library offers one algorithm for the fixture shape silently skips the second one. Choosing a shape with several eligible algorithms on the gfx1250 lanes would keep the post-measurement stop covered there.

Exhaustive tune mode finished the bench problem on this device in about 45 seconds, inside the default five-minute budget; larger libraries or slower devices will reach the budget stop, which records nothing by design, so the first call for a shape can block for the full budget and then leave the shape untuned for the process.
