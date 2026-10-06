This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13005](https://github.com/ROCm/rocm-libraries/pull/13005)

**Reviewed head:** [`c6ec02e372e5a3452f83c9e8e6d943406bfdc22c`](https://github.com/ROCm/rocm-libraries/commit/c6ec02e372e5a3452f83c9e8e6d943406bfdc22c) (2026-10-06), relative to #12960. Public repository and head; existing reviews/comments were not consulted.

**Published suggestion branch:** [`review/pr13005-suggestions-20261006`](https://github.com/newling/rocm-libraries/tree/review/pr13005-suggestions-20261006), based on that head. Commit [`6503895955f7`](https://github.com/newling/rocm-libraries/commit/6503895955f74e3780b395c4ebea5b89a6601f2b) moves the existing #13022 Stream-K coverage guard into the layer that first needs it.

## Tests

Built the submitted checker and passed its 38 host/device self-tests on gfx1201/ROCm 7.1. The modified matmul header compiles in benchmark and GOOGLE_TEST modes; whitespace checks pass. The full GEMM repeat/injection cases and actual Stream-K selection were not rerun locally.

## Summary

The solution loop now checks each solution repeatedly, clearing D and workspace before each launch, restoring C for C/D aliasing and retaining one expected fingerprint per unchanged input. The failure log records the library index, kernel and iteration. The injected corruption case tests attribution to a particular launch, while the existing numerical fault tests cover the probe arithmetic.

## Actionable items

### Put the actual Stream-K coverage guard in this layer

At `projects/hipblaslt/clients/common/include/testing_matmul.hpp:1138`, the startup environment check permits any process started with selection method 2. That does not establish that the selected library offers Stream-K kernels. The description records that gfx90a passed these cases without running any Stream-K kernel until the guard added in #13022.

Commit [`6503895955f7`](https://github.com/newling/rocm-libraries/commit/6503895955f74e3780b395c4ebea5b89a6601f2b) moves that guard, unchanged, to immediately after `CHECK_SOLUTION_FOUND`: require at least one selected kernel name containing `_TPSSK_`, otherwise skip with a reason. When restacking, drop its duplicate from #13022. This is a relocation of the author's existing stack fix, with local compilation validation; actual selection on gfx90a was not reproduced here.

## Suggestions

No further change requested. The default repeat count retains the prior loop behavior. Keep the tracked, time-boxed known-bug cases separate from injection tests: deliberate corruption must not become a way to accept failures in ordinary runs.

## Commentary

Direct log/corruption tests and the client injection case are the appropriate levels. A full architecture sweep is not needed for the log helper, but representative C/D aliasing and Stream-K launches matter for reset ordering. The description explicitly records the gfx942 manual-run requirement and the known numerical defects; those remain limitations rather than a reason to hold unrelated verifier infrastructure indefinitely. No test waiver is needed for the repeated-launch feature.

The published branch contains the one relocation commit linked above.
