This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#15346](https://github.com/ROCm/rocm-systems/pull/15346)

**Reviewed head:** `39deee0e1fafda416d99f6f583496644b8742019`.
**Base:** PR base snapshot `b21309d8249bacf94ebb2d8c1ebc51316314432c`; diff merge base `16ad3db387ae21d3618bf15293c4ab7b700dbb19`.
**Scope:** Independent review of descriptor parsing, dense-transfer iteration, LDS barrier arithmetic, their execution and observation paths, and regression coverage. Existing PR discussion was not consulted.
**Suggestion branch:** [`review/pr15346-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr15346-suggestions), based directly on the reviewed head. Its only commit, [`b35cce9d018`](https://github.com/newling/rocm-systems/commit/b35cce9d018ab177e4e1d8d91bdd45b022a09940), implements suggestion S1 below.

## Tests

The Release `rocjitsu_tests` target built with Clang 23, and all 363 tests selected by `--gtest_filter='*TensorDma*:*Barrier*'` passed on both the submitted head and the suggestion branch. Pre-commit and whitespace checks passed for the optional cleanup.

As a negative control, I restored the three changed implementation files from the merge base while retaining the submitted tests. All three new/replaced regressions failed: the two descriptor tests rejected their loads, and the returning barrier test disagreed with all six expected updated cells. The submitted sources were restored before final validation. This establishes that the regressions distinguish the preceding behavior; it was not a full base-branch test run.

The PR's Release and sanitizer CI jobs were passing when checked. I did not reproduce the description's separate probe matrix or full CTest comparison, and did not run on physical gfx1250 hardware.

## Summary

No actionable correctness defect found in the reviewed change. The active-dimension list preserves original dimension numbers, so skipping an unused axis also consistently excludes its extent and stride from element counts, address-range validation, and transfer traversal. The overlapping-row exception is deliberately limited to whole-row steps whose complete sequence stays in bounds; other ambiguous advancing layouts remain rejected.

The packed barrier subtraction follows the instruction pseudocode in the [CDNA5 ISA](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf), section 15.15: subtract `UPDATE_VAL.b32`, retain the resulting phase, and reload the initial pending count when its sign bit is set. The shared helper serves both DS arrivals and tensor completion. The new instruction-level test checks distinct underflow cases, ignores the upper update word, and verifies the returned pre-update cell independently of that helper. The descriptor tests check loads and stores, including untouched global locations.

## Actionable items

None.

## Suggestions

### S1. Make the standard-library dependencies and dimension view explicit

At [cdna5_tensor_dma_test.cpp:11](https://github.com/ROCm/rocm-systems/blob/39deee0e1fafda416d99f6f583496644b8742019/emulation/rocjitsu/tests/cdna5_tensor_dma_test.cpp#L11), add the owning headers for the standard-library facilities used in the file. In particular, the new `std::size(cases)` use needs `<iterator>`, and the arrays need `<array>`; these currently arrive through other headers. The cleanup also completes the existing string, span, initializer-list, stream-manipulator, and move dependencies.

At [tensor_dma.h:672](https://github.com/ROCm/rocm-systems/blob/39deee0e1fafda416d99f6f583496644b8742019/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h#L672), spell out `std::span<const uint32_t>` for `dimensions` so the borrowed view is visible at the call site, consistent with the local explicit-type convention.

Implemented together in [`b35cce9d018`](https://github.com/newling/rocm-systems/commit/b35cce9d018ab177e4e1d8d91bdd45b022a09940). These are optional code-quality changes; no build failure or behavioral defect is attributed to them.

The suggestion branch contains only S1. No required fixes were omitted.
