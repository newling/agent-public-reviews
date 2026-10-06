This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13013](https://github.com/ROCm/rocm-libraries/pull/13013)

**Reviewed head:** [`de8179d56d3dc8c790668eb505ec74028050a720`](https://github.com/ROCm/rocm-libraries/commit/de8179d56d3dc8c790668eb505ec74028050a720) (2026-10-06), relative to #13005. Public repository and head; existing reviews/comments were not consulted.

**Published suggestion branch:** [`review/pr13013-suggestions-20261006`](https://github.com/newling/rocm-libraries/tree/review/pr13013-suggestions-20261006), based on that head. [`623e6805825`](https://github.com/newling/rocm-libraries/commit/623e680582533f213a6a67713eb5ab56c77af970) makes retained sparse values nonzero and checks actual coverage; [`6e3d7b8a7eef`](https://github.com/newling/rocm-libraries/commit/6e3d7b8a7eef6bedc0af5b3bde6f76fabfe3eb1a) isolates pattern state between test threads.

## Tests

Built the submitted checker and passed its 43 self-tests on gfx1201/ROCm 7.1. Both new regressions fail before their corresponding fixes; all 44 tests pass on the final branch. Whitespace checks pass. Full GEMM and FNUZ architecture suites were not rerun locally.

## Summary

This adds a conservative bound on arbitrary partial sums before GEMM launches, so exact modular verification is used only where accumulation order cannot change the integer result. Ternary and sparse inputs reduce output magnitudes and avoid expensive rounded-output recomputation. Direct bounds, data-pattern and rejection tests are the appropriate level, with client cases checking both input storage orders and agreement with the existing reference.

## Actionable items

### Test actual nonzero coverage of K

In `projects/hipblaslt/clients/common/src/hipblaslt_init_device.cpp:1068`, a retained sparse position receives `small_int_positive`, which can be zero. Thus even with enough rows to cover the position mask, some K indices have no nonzero A value. In `clients/tests/src/fast_check_gtest.cpp`, `integer_exact_patterns_keep_their_ranges` marks a K index covered from the mask alone. It passes even if every retained value is zero.

Commit [`623e6805825`](https://github.com/newling/rocm-libraries/commit/623e680582533f213a6a67713eb5ab56c77af970) gives retained positions values in {1, 2}, retaining the existing worst-case bound, and counts coverage from the generated values. The strengthened test fails on the submitted fill and passes after the fix. Shapes with fewer than ceil(K/16) rows still intentionally cover only part of K, as the description records.

### Keep pattern state local to each test thread

In `projects/hipblaslt/clients/common/src/hipblaslt_init_device.cpp:88`, `integer_exact_pattern_state` holds one mutable process-wide object. The client supports running tests on multiple threads. When one worker's `IntegerExactPatternScope` ends, it resets another worker's selected pattern; unsynchronized reads/writes also constitute a data race.

Commit [`6e3d7b8a7eef`](https://github.com/newling/rocm-libraries/commit/6e3d7b8a7eef6bedc0af5b3bde6f76fabfe3eb1a) makes the state `thread_local` and documents that scope. The regression selects ternary on one thread, completes a sparse-pattern scope on another, then verifies the first thread still generates ternary values. The submitted code instead generates a value of 2. Device fills capture a copy of the state, so kernel execution does not require thread-local device access.

## Suggestions

When [#13119](https://github.com/ROCm/rocm-libraries/pull/13119) lands, retain its standalone FNUZ negation fix and tests while restacking this layer. The shared helper fix should not need to wait for the verifier stack.

## Commentary

The numerical bound is deliberately conservative; rejection near the limit is preferable to labelling a summation-order difference as a kernel defect. Existing default initialization remains standard, and the new patterns are selected explicitly. The two added regressions belong to the existing pre_checkin self-test suite. No feature flag or omitted-test waiver is needed beyond those explicit selectors.

The published branch contains the two commits linked above. Architecture-specific GEMM replay remains covered by CI and the author's reported runs, rather than the local self-test result.
