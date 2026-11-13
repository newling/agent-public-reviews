This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15278](https://github.com/ROCm/rocm-libraries/pull/15278)

**Submitted head:** `e24bb5950c6eacb30a5eb2e201d7e5fba9af6848`. **Incremental diff base:** `46ce0b0c3a676b3878f652e4dbf136bdb1f30f9f`.

**Scope:** Focused follow-up on consequential CPU-reference errors and regression-test failures, including the existing review discussion. Head and discussion were unchanged at the 2026-11-13 23:09 UTC check. Earlier validation is reused where the tested code is unchanged.

**Suggestion branch:** [review/pr15278-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15278-correctness-20261113), based on the submitted head; final head [f15ee4aacee](https://github.com/newling/rocm-libraries/commit/f15ee4aacee6031017b93c151ab6f2b3bb618a91). Commit-to-item mapping is given below.

## Tests

Reused submitted-head validation: 788 driver CTests and 42 reference tests passed, and the driver, tests and client built. For the retained assertion change, the seven `ReferenceMXFastPath` tests passed. Replacing all computed outputs with NaN still passed the submitted tail test and failed the fixed assertion. This is a demonstrated test blind spot, with no new GPU or performance result claimed.

## Summary

The fast path loads zero beyond logical K, so an eight-element tile can cover a partial final MX scale block without summing padding. The test's nonzero padding and independent per-K expected sum are useful. Its comparison currently lets completely invalid output escape detection.

## Actionable items

### Make the exact tail test fail when any output is NaN

At [tests/ReferenceMXFastPath_test.cpp:274](https://github.com/ROCm/rocm-libraries/blob/e24bb5950c6eacb30a5eb2e201d7e5fba9af6848/projects/hipblaslt/tensilelite/tests/ReferenceMXFastPath_test.cpp#L274), the test compares `maxAbsDiff(expected, d)` with zero. That helper folds `fabs(a-b)` through `std::max`; NaN differences are ignored. Filling every output element with NaN leaves the reported maximum at zero, and `PartialLastMXBlockSumsOnlyElementsBelowK` passes.

The expected values in this test are finite and exact, so compare the vectors directly. Fix [f15ee4aacee](https://github.com/newling/rocm-libraries/commit/f15ee4aacee6031017b93c151ab6f2b3bb618a91) makes that change and preserves the case context. It catches the all-NaN negative control below without widening the test matrix.

## Suggestions

None in this focused review.

## Scope decisions

The production slow path already clamps its final segment at K, from [#13630](https://github.com/ROCm/rocm-libraries/pull/13630). I found no production over-read for equal MX block sizes in this change. The driver's inherited equal-block tail rejection and stale over-read explanation are excluded from this serious-defect list. Asymmetric slow-path block sizes remain a separate limitation.

## Appendix: assertion negative control

With `<algorithm>` and `<limits>` included, insert this immediately before the tail test's final comparison, after `SolveGemmCPU`:

```cpp
std::fill(d.begin(), d.end(), std::numeric_limits<float>::quiet_NaN());
```

```sh
cmake --build "$BUILD_DIR" --target tensilelite-tests -j 4
OMP_THREAD_LIMIT=8 OMP_NUM_THREADS=4 KMP_BLOCKTIME=0 \
  "$BUILD_DIR/tensilelite/tests/tensilelite-tests" \
  --gtest_filter=ReferenceMXFastPath.PartialLastMXBlockSumsOnlyElementsBelowK
```

The submitted comparison passes; the fixed comparison fails. The temporary mutation is not included in the suggestion commit.

**Suggestion summary:** [review/pr15278-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15278-correctness-20261113) contains only [f15ee4aacee](https://github.com/newling/rocm-libraries/commit/f15ee4aacee6031017b93c151ab6f2b3bb618a91), the exact assertion correction. No new production tail-bounds defect was established.
