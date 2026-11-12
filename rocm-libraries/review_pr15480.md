This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15480](https://github.com/ROCm/rocm-libraries/pull/15480)

**Reviewed:** 2026-11-12, head `78d3e052900d9f65553d450ee84e6a55aac7e737`

**Diff base:** `fdf330811bb5b6e03af1b457b2a4c8efd36860d8`, the prerequisite in [#15672](https://github.com/ROCm/rocm-libraries/pull/15672).

**Mode and scope:** Independent review of the five assembly kernels, their registration and dispatch restrictions, numerical tests, documentation, and CI coverage. Prerequisite code was traced where it supplies predicates, layouts, and launch arguments. Existing PR discussion was not read.

**Suggestion branch:** [review/pr15480-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15480-suggestions), based on the reviewed head. Commit [bf83785e160](https://github.com/newling/rocm-libraries/commit/bf83785e160fb8c933c9d3f7b6ff3b8d4e29a560) implements suggestion 1. [Compare the reviewed head with the suggestion](https://github.com/newling/rocm-libraries/compare/78d3e052900d9f65553d450ee84e6a55aac7e737...bf83785e160fb8c933c9d3f7b6ff3b8d4e29a560).

## Tests

On the submitted head, all five kernels assemble for gfx950 with ROCm 7.1's compiler; the hipBLASLt test binary and rocISA bindings build. Strict metadata validation reports 265 kernels with no errors or warnings. The three focused Python suites (`test_CustomKernels_mx_scale_128x4.py`, `test_CustomKernels_buffer_oob.py`, and `test_custom_kernel_mx_scale_format.py`) pass all 402 cases, including eight logic-corpus cases with none skipped. Nine native layout/predicate tests pass. All five new GPU tests register but skip on the available gfx1201 device.

The suggestion commit also builds and passes those 402 Python and nine native tests; the five GPU cases still skip. Root pre-commit hooks pass their configured checks; root formatting hooks exclude hipBLASLt. Focused Black 24.4 (100 columns) and clang-format 18 checks exposed two small formatting differences in added test code, included in the suggestion commit. Whole-file formatting also reports inherited differences outside this PR's additions.

MI355X execution, numerical stress, synchronization hazards, and performance were not independently validated. The PR description reports manual MI355X tests, including exact-reference and negative-selection checks; those results are distinct from this review's local evidence.

## Summary

This adds five specialized MXFP6 matrix-multiplication kernels: two input encodings and two long K dimensions with both operands tiled, plus one E2M3 case with ordinary packed B. Their safety depends on exact problem predicates because the assembly uses fixed buffer bounds. The parsed solutions retain the fixed dimensions, A/B/D strides, alpha value, scale layout, and operand-order restrictions. The custom argument list matches the assembly's five pointers, including its reversed A/B naming, and its flattened grid gives 256 workgroups for the admitted shape.

The long-K variants have exactly the 23 instruction changes documented in their headers. At either K, the E2M3/E3M2 instruction streams differ only in the matrix instruction's input-format selectors. The row-uniformity test checks that every output row agrees when inputs represent the same values, then separately checks sampled results against an exact integer sum. That second check is useful because uniform output alone does not establish correctness. No kernel or dispatch defect was demonstrated by the completed checks; automated execution coverage remains the material concern.

## Actionable items

### 1. Demonstrate CI execution on the registered chip

**Location:** [row_uniformity_gtest.cpp:1234](https://github.com/ROCm/rocm-libraries/blob/78d3e052900d9f65553d450ee84e6a55aac7e737/projects/hipblaslt/clients/tests/src/row_uniformity_gtest.cpp#L1234), together with the new `allow_no_solution: 1` entries in [matmul_gtest.yaml:3174](https://github.com/ROCm/rocm-libraries/blob/78d3e052900d9f65553d450ee84e6a55aac7e737/projects/hipblaslt/clients/tests/data/matmul_gtest.yaml#L3174).

The row-uniformity tests skip unless the PCI chip ID is `0x75a3` (MI355X). The new YAML cases permit no solution, so they also do not require kernel execution on another gfx950 chip. [TESTING.md's device-coverage table](https://github.com/ROCm/rocm-libraries/blob/78d3e052900d9f65553d450ee84e6a55aac7e737/projects/hipblaslt/TESTING.md#L1488) identifies MI350X as the gfx950 CI runner and explicitly notes the MI355X coverage gap. The completed [gfx950 local-kernel job](https://github.com/ROCm/rocm-libraries/actions/runs/43286192770/job/131420885202) confirms MI350X, chip `0x75a0`, and runs only `LocalKernel*:HipSolutionAdapter*`. Its success therefore provides no execution evidence for these kernels.

A kernel-body regression could pass metadata checks and the currently demonstrated automation. Provide a shared CI run on MI355X selecting `*RowUniformityMXFp6_pre_checkin*`, with all five cases executed and zero skips; the dedicated run should fail if that selection executes no cases or skips them. Retain the chip guard in ordinary multi-device runs. If an existing lane already supplies this coverage, its runner identity and executed-test result are sufficient evidence. The reported manual MI355X runs are useful, but do not establish the affected-device CI coverage required by the component review guidance.

**Implementation:** No CI change was made locally. Routing to MI355X requires a verified runner configuration; changing the guard or broadening kernel registration would not resolve that infrastructure question.

## Suggestions

### 1. Include the standard headers used by the new test

**Location:** [row_uniformity_gtest.cpp:54](https://github.com/ROCm/rocm-libraries/blob/78d3e052900d9f65553d450ee84e6a55aac7e737/projects/hipblaslt/clients/tests/src/row_uniformity_gtest.cpp#L54).

The added test uses `ptrdiff_t`, `std::hex`, and `std::dec` through transitive includes. Commit [bf83785e160](https://github.com/newling/rocm-libraries/commit/bf83785e160fb8c933c9d3f7b6ff3b8d4e29a560) adds `<cstddef>` and `<ios>`, qualifies `std::ptrdiff_t`, and applies the two formatter changes confined to added test code. This is optional source maintenance; the submitted build succeeds.

## Commentary

At the final status check, the reviewed head was unchanged and broader CI was still pending. The failing PR-bot job reports `pre-commit=cancelled`, while another pre-commit run for the head succeeded. That bot failure is not evidence of a kernel defect.

The [suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr15480-suggestions) contains [one optional test-source cleanup commit](https://github.com/newling/rocm-libraries/commit/bf83785e160fb8c933c9d3f7b6ff3b8d4e29a560). The MI355X CI item remains unimplemented, and GPU execution remains outside the independently completed validation.
