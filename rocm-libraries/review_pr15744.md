This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15744](https://github.com/ROCm/rocm-libraries/pull/15744)

Reviewed head: `d702b46374a779c5f748a9a88245b13b8b30521c`. Target-base snapshot: `f65195cf63c927df0025b35342ce99f3e9e70b1f`; merge base: `84c6e7ced46a654eff0a668d9aecf568bb42de1d`.

Independent review of FP6 integer encodings and packing, exact-reference generation, numerical bounds, client consumers, and test selection. Suggestion branch: [review/pr15744-current-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15744-current-suggestions), based on the reviewed head. Item 1 is implemented in commit [af2d7168d40](https://github.com/newling/rocm-libraries/commit/af2d7168d403ac047c065522333228ba089aa174).

## Tests

The reviewed head builds `hipblaslt-test`, `hipblaslt-test-hostunit`, and `tensilelite-tests`. All 128 submitted host client tests pass, including partial-block FP6/FP8 coverage; the focused TensileLite MXDataGen run passes 17 tests with one existing, tracked FP4 skip. The additional padding regression fails against the submitted implementation: it returns 256 floats for 384 storage elements. With the suggestion, all 129 host client tests pass, the same TensileLite tests pass with the same skip, and both client targets build.

CI for the reviewed head is still in progress at the review snapshot. The [earlier head's gfx950 quick job](https://github.com/ROCm/rocm-libraries/actions/runs/43464264341/job/132049805041) passed its four new host tests and five row-uniformity cases; that run does not establish validation of the reviewed head. Full-matrix exact YAML tests remain at pre_checkin/nightly tiers and were absent from that quick job. The author-reported full numerical and mutation runs were not independently executed in this review. Local hardware is gfx1201, and the installed device library does not match these PRs; no local GPU result is claimed for these kernels.

## Summary

The generated FP6 values and E8M0 scales make each dequantized operand an integer of magnitude at most 8. A product is therefore bounded by 64, and bounding the sum of absolute products by `K * 64` proves that every FP32 partial sum is exact in any accumulation order for the registered K values. The host tests check independently decoded packed FP6 bytes and compare forward and reverse summation with an integer oracle at the largest K.

The current head uses the generator's scale-index helper and tests partial blocks for FP6 and FP8. It also retains the existing quick test's sampled exact numerical control alongside order-sensitive row uniformity; relative to the merge base, that GPU test changes only its explanatory comment. The reference still needs to preserve the generator's padded storage extent.

## Actionable items

### 1. Preserve the storage extent when rebuilding exact references

At [mxDataGen.cpp:546](https://github.com/ROCm/rocm-libraries/blob/d702b46374a779c5f748a9a88245b13b8b30521c/projects/hipblaslt/clients/common/src/mxDataGen.cpp#L546), the K-contiguous integer-exact path allocates `sizes[0] * sizes[1]` floats. The generator instead stores `stride * columns` elements, including leading-dimension padding.

For 64 stored rows, four columns, and leading dimension 96, the generator stores 384 elements, but this path returns only 256 floats. The matmul client passes the returned vector to the CPU GEMM with the original leading dimension: the fourth column starts at element 288, already beyond the vector. The non-integer path preserves the full storage extent through `getReferenceFloat()`. This counterexample uses `MXScaleLayout::None` and requires no GPU or architecture-specific swizzle.

Commit [af2d7168d40](https://github.com/newling/rocm-libraries/commit/af2d7168d403ac047c065522333228ba089aa174) preserves `stride * columns`, retaining the submitted scale-index helper. A host regression covers both FP6 formats, both FP8 formats, and both K-contiguous A/B orientations. It decodes the packed bytes independently and checks the reference over the full storage extent. The commit also removes a stale fast-check comment describing the former linear scale-index calculation. Run the regression with `hipblaslt-test-hostunit --gtest_filter='HostUnitMXIntegerExact.smoke_KContiguousReferenceIncludesStridePadding'`.

## Suggestions

None.

Handoff: [review/pr15744-current-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15744-current-suggestions), commit [af2d7168d40](https://github.com/newling/rocm-libraries/commit/af2d7168d403ac047c065522333228ba089aa174) for item 1. The storage fix has host regression and consumer-build validation. Full-matrix GPU execution remains unverified locally.
