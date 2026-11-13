This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15276](https://github.com/ROCm/rocm-libraries/pull/15276)

**Submitted head:** `5b4f85f05f2977d06f67cf5405eff41da6800f93`. **Incremental diff base:** `b6828c46316720641f2e3f15a1320201d4f1c34b`.

**Scope:** Focused follow-up on consequential CPU-reference errors and regression-test failures, including the existing review discussion. Head and discussion were unchanged at the 2026-11-13 23:09 UTC check. Earlier validation is reused where the tested code is unchanged.

**Suggestion branch:** [review/pr15276-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15276-correctness-20261113), based on the submitted head; final head [7c3393ef929](https://github.com/newling/rocm-libraries/commit/7c3393ef929f82a8f899ded5a245816265954a1d). Commit-to-item mapping is given below.

## Tests

Reused validation for the unchanged code: submitted head, 700 driver CTests and 35 reference tests passed; retained fix, 700 driver CTests and 36 reference tests passed. The driver, tests and client built. A direct probe against the submitted stack reproduced the alias error; the committed regression covers complex float and complex double. No new GPU or performance run was made.

## Summary

The tiled solver can perform complex multiplication and conjugate operands while loading them. The central correctness gap is ordinary GEMM input preservation: the result buffer is written before a potentially aliased beta input is read.

## Actionable items

### Preserve complex C until the epilogue has consumed it

At [client/src/Reference.cpp:1958](https://github.com/ROCm/rocm-libraries/blob/5b4f85f05f2977d06f67cf5405eff41da6800f93/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1958), intermediate tile sums are written to D before reading C. When C and D share storage, the complex shadow buffer refers directly to C, so this overwrites the beta input.

With A=(2,0), B=(3,0), initial C=D=(5,1), and alpha=beta=(1,0), the reference should return **(11,1)**. The submitted fast path returns **(12,0)**. This changes both the real result and the preserved imaginary component.

Fix [7c3393ef929](https://github.com/newling/rocm-libraries/commit/7c3393ef929f82a8f899ded5a245816265954a1d) consumes the tile sum directly and writes D only after reading C. `ComplexInPlaceCDPreservesBetaInput` uses nonzero imaginary components in A, B and C and checks both complex widths. The original probe is preserved in the [native counterexample source and setup](review_cpu_reference_stack_15259_15278.md#appendix-native-counterexample-source-and-setup).

## Suggestions

None in this focused review.

## Scope decisions

This is the same shared epilogue defect exposed by the Int8 extension in #15274. Once that production correction is integrated, keep the complex regression without applying the correction twice. This review does not change the documented non-finite complex-arithmetic boundary.

**Suggestion summary:** [review/pr15276-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15276-correctness-20261113) contains [7c3393ef929](https://github.com/newling/rocm-libraries/commit/7c3393ef929f82a8f899ded5a245816265954a1d), the common alias fix and complex regression. The existing approving review does not establish that the alias counterexample is fixed; the submitted code is unchanged.
