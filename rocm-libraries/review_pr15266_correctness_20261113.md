This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15266](https://github.com/ROCm/rocm-libraries/pull/15266)

**Submitted head:** `4554dab796dee28e4e640b7f688c4d0f12d5b375`. **Incremental diff base:** `571ecae3fc4814ff951461d1d14e48f780975511`.

**Scope:** Focused follow-up on consequential CPU-reference errors and regression-test failures, including the existing review discussion. Head and discussion were unchanged at the 2026-11-13 23:09 UTC check. Earlier validation is reused where the tested code is unchanged.

**Suggestion branch:** [review/pr15266-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15266-correctness-20261113), based on the submitted head; final head [2fcafc2eee3](https://github.com/newling/rocm-libraries/commit/2fcafc2eee3f322abd349beeda112823931c8591). Commit-to-item mapping is given below.

## Tests

Reused validation for the unchanged code: submitted head, 361 driver CTests and 24 reference tests passed; scalar-fix commit, 362 driver CTests and 24 reference tests passed. The driver, tests and client built in both cases. The boundary command below failed on the submitted implementation and passed with the fix. No GPU execution is needed for this CLI parsing defect.

## Summary

The driver can now choose Int8 input storage, C/D storage, and alpha/beta types separately. Its integer oracle is useful for checking the supported combinations. The remaining consequential issue is that the command line can lose the requested integer scalar before either the reference or the oracle sees it.

## Actionable items

### Preserve Int32 scalars before validating or using them

[client/cpu_gemm_driver.cpp:1145](https://github.com/ROCm/rocm-libraries/blob/4554dab796dee28e4e640b7f688c4d0f12d5b375/projects/hipblaslt/tensilelite/client/cpu_gemm_driver.cpp#L1145) parses alpha and beta as float, and [client/cpu_gemm_driver.cpp:1292](https://github.com/ROCm/rocm-libraries/blob/4554dab796dee28e4e640b7f688c4d0f12d5b375/projects/hipblaslt/tensilelite/client/cpu_gemm_driver.cpp#L1292) checks the already-rounded values. For example, valid Int32 beta `2147483647` becomes `2147483648` and is rejected. Other integers above `2^24` can silently become a neighboring integer; both the calculation and its oracle then receive the changed value, so validation cannot detect the parsing error.

```sh
"$BUILD_DIR/tensilelite/client/cpu-gemm-driver" -M 1 -N 1 -K 0 \
  --type i8 --typeCD i32 --typeAlpha i32 --alpha 0 --beta 2147483647 --validate
```

Carry parsed scalars in a type that represents the Int32 range exactly until converting to the selected scalar type. Fix [2fcafc2eee3](https://github.com/newling/rocm-libraries/commit/2fcafc2eee3f322abd349beeda112823931c8591) uses double and adds the boundary regression. This is a defect in test-driver input handling; it does not change GPU arithmetic.

## Suggestions

None in this focused review.

## Scope decisions

The legacy float-alpha Int8 reduction loses precision above `2^24`; that separate numerical issue is tracked by [#15764](https://github.com/ROCm/rocm-libraries/issues/15764) and [#15765](https://github.com/ROCm/rocm-libraries/pull/15765). The latter remains outside this stack. It does not address the CLI scalar conversion above.

**Suggestion summary:** [review/pr15266-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15266-correctness-20261113) contains only [2fcafc2eee3](https://github.com/newling/rocm-libraries/commit/2fcafc2eee3f322abd349beeda112823931c8591) for scalar parsing and its regression. The broader naming and diagnostic changes from earlier reviews are omitted from this review.
