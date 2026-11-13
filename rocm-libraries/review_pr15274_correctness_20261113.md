This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15274](https://github.com/ROCm/rocm-libraries/pull/15274)

**Submitted head:** `f58bbb3388853e13cdf85bda0917485d590c4ddc`. **Incremental diff base:** `4554dab796dee28e4e640b7f688c4d0f12d5b375`.

**Scope:** Focused follow-up on consequential CPU-reference errors and regression-test failures, including the existing review discussion. Head and discussion were unchanged at the 2026-11-13 23:09 UTC check. Earlier validation is reused where the tested code is unchanged.

**Suggestion branch:** [review/pr15274-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15274-correctness-20261113), based on the submitted head; final head [a20ddeb0e6f](https://github.com/newling/rocm-libraries/commit/a20ddeb0e6f2e7b9e0af960d8b96730f8b3441f4). Commit-to-item mapping is given below.

## Tests

Earlier validation at the unchanged submitted head passed 440 driver CTests and 30 reference tests. The new suggestion branch rebuilt the driver, tests and client and passed all 440 driver CTests and 32 reference tests.

Fresh checks linked the same new regressions against submitted and fixed `Reference.cpp` implementations. The submitted code returned 12 in the alias test and triggered the signed-overflow sanitizer at line 1421; the fixed implementation passed both. Sanitizer instrumentation covered `Reference.cpp`, with the rest of the build uninstrumented. This is CPU correctness evidence, with no new GPU or performance comparison.

## Summary

An integer dot-product accumulator avoids losing Int8 products through float rounding before the epilogue applies alpha, beta and output conversion. That separation is useful. The implementation still needs to preserve the original C input and define what happens when the dot product exceeds signed 32-bit range.

## Actionable items

### Read the original C before writing an aliased D

At [client/src/Reference.cpp:1816](https://github.com/ROCm/rocm-libraries/blob/f58bbb3388853e13cdf85bda0917485d590c4ddc/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1816), the intermediate dot-product tile is copied to D before the epilogue reads C. For Int32 C/D and an Int32 epilogue, the C shadow buffer can directly reference that storage. Supplying the same buffer for C and D therefore destroys the beta input.

A 1×1 GEMM with A=2, B=3, initial C=D=5 and alpha=beta=1 must give **11**. The submitted implementation gives **12**. Fix [1024648658c](https://github.com/newling/rocm-libraries/commit/1024648658c17b9f3dfafb3aa41929817081c84f) reads the dot product directly from the tile, reads C, then writes the final D. `Int8InPlaceCDPreservesBetaInput` checks the independently known answer.

### Define wrapping arithmetic for overflowing Int8 dot products

[client/src/Reference.cpp:1420](https://github.com/ROCm/rocm-libraries/blob/f58bbb3388853e13cdf85bda0917485d590c4ddc/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1420) adds into signed `int32_t`. A supported 1×1×140,000 problem with A=B=-128 and alpha=1, beta=0 exceeds its range. The sanitizer reports `2147467264 + 16384 cannot be represented in type 'int'`. Ordinary compiler wraparound does not make that C++ operation defined, so the reference can depend on optimization behavior.

Fix [a20ddeb0e6f](https://github.com/newling/rocm-libraries/commit/a20ddeb0e6f2e7b9e0af960d8b96730f8b3441f4) performs the multiply-add through `uint32_t` and preserves the resulting signed bits before the epilogue. This follows the wrapping approach in [HostNumerics](https://github.com/ROCm/rocm-libraries/blob/064a46fc55678f21bc71588c112df6a7836a94dc/shared/hostnumerics/src/detail/reference_arithmetic.hpp#L31) and the policy proposed in #15765. It keeps the change inside the existing reduction rather than adding another numerical backend.

`Int8DotProductWrapsAtInt32Boundary` checks both overflow directions and both Int32 and float scalar types. Its independent expected results are -2,001,207,296 and 2,019,127,296. The [standalone sanitizer recipe](review_pr15274_overflow_reproducer_20261113.py) reproduces the submitted failure and fixed pass using that committed test.

## Suggestions

None in this focused review.

## Scope decisions

[#15765](https://github.com/ROCm/rocm-libraries/pull/15765) is still a sibling of this stack. Until its slow float-alpha reduction fix is integrated, large sums can produce different reference answers when eligibility or validation density selects the slow path. Keep the independent integer oracle; comparing only fast and slow answers would conceal which result is correct. The new fix covers dot-product overflow; inherited integer epilogue arithmetic is retained.

The alias correction also applies to complex GEMMs in #15276. Integrate the common production fix once and retain both type-specific regressions.

**Suggestion summary:** [review/pr15274-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15274-correctness-20261113) contains [1024648658c](https://github.com/newling/rocm-libraries/commit/1024648658c17b9f3dfafb3aa41929817081c84f) for C/D aliasing and [a20ddeb0e6f](https://github.com/newling/rocm-libraries/commit/a20ddeb0e6f2e7b9e0af960d8b96730f8b3441f4) for dot-product overflow. The slow-path fix in #15765 has not been incorporated or certified by this review.
