This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15275](https://github.com/ROCm/rocm-libraries/pull/15275)

**Submitted head:** `b6828c46316720641f2e3f15a1320201d4f1c34b`. **Incremental diff base:** `f58bbb3388853e13cdf85bda0917485d590c4ddc`.

**Scope:** Focused follow-up on consequential CPU-reference errors and regression-test failures, including the existing review discussion. Head and discussion were unchanged at the 2026-11-13 23:09 UTC check. Earlier validation is reused where the tested code is unchanged.

**Suggestion branch:** [review/pr15275-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15275-correctness-20261113), based on the submitted head; final head [d930b5107f1](https://github.com/newling/rocm-libraries/commit/d930b5107f10b667c55bfe4a9454e4f4fa8f9d4b). Commit-to-item mapping is given below.

## Tests

Reused validation for the unchanged implementations: submitted head, 647 driver CTests and 32 reference tests passed; retained fix, 647 driver CTests and 33 reference tests passed. The driver, tests and client built. A direct CPU probe demonstrated the scaling discrepancy below; the regression checks both operand directions and scalar/vector scaling. No new GPU or performance run was made.

## Summary

Float accumulation followed by the existing Float8 output conversion is a small extension of the tiled reference. The material exception is a stored Half operand that is first narrowed to Float8 for multiplication: moving its scale across that conversion changes the numerical operation.

## Actionable items

### Keep scaled Half-to-Float8 inputs out of the fast path until the formulas agree

[client/src/Reference.cpp:1354](https://github.com/ROCm/rocm-libraries/blob/b6828c46316720641f2e3f15a1320201d4f1c34b/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1354) admits Float8-output configurations with a Half input narrowed to Float8 and ScaleAB enabled. The corresponding driver tests explicitly omit scaling at [tests/CMakeLists.txt:837](https://github.com/ROCm/rocm-libraries/blob/b6828c46316720641f2e3f15a1320201d4f1c34b/projects/hipblaslt/tensilelite/tests/CMakeLists.txt#L837).

For a 1×1 GEMM with Half A=0.9, Float8 B=1, scaleA=3, scaleB=1, alpha=1 and beta=0, the slow reference returns **2.75**, while the fast reference returns **2.5**. The slow path scales before quantizing A; the fast path quantizes before scaling. Vector scaling exposes a larger semantic difference: the legacy slow path omits the narrowed operand's scale while the fast path applies it. The expected reference result can therefore change with path selection, beyond ordinary last-bit reassociation.

Fix [d930b5107f1](https://github.com/newling/rocm-libraries/commit/d930b5107f10b667c55bfe4a9454e4f4fa8f9d4b) excludes these combinations from fast eligibility. `ScaledHalfToFloat8KeepsSlowPathConversionOrder` checks fallback through the normal solver, using both operand directions and both scale modes. The original probe is preserved in the [native counterexample source and setup](review_cpu_reference_stack_15259_15278.md#appendix-native-counterexample-source-and-setup).

## Suggestions

None in this focused review.

## Scope decisions

The guard preserves current behavior, including the legacy vector-scale omission. Correcting that formula requires an explicit change shared by both paths; it should not happen implicitly in a performance extension. Current common configurations use ScaleCD, which already excludes fast execution, so this is a demonstrated supported-case defect rather than an observed failure in those configurations.

The existing requested-change review raises this same discrepancy. It remains unaddressed at the submitted head.

**Suggestion summary:** [review/pr15275-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15275-correctness-20261113) contains only [d930b5107f1](https://github.com/newling/rocm-libraries/commit/d930b5107f10b667c55bfe4a9454e4f4fa8f9d4b), the eligibility guard and regression. A broader scaling-policy change is left open.
