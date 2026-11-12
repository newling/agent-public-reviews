This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15278](https://github.com/ROCm/rocm-libraries/pull/15278)

**Submitted head:** `e24bb5950c6eacb30a5eb2e201d7e5fba9af6848`. **Incremental base:** `46ce0b0c3a676b3878f652e4dbf136bdb1f30f9f`.

Independent review of the incremental change and its interaction with the CPU-reference stack, emphasizing test adequacy, runtime, overlap, design reuse, and unsupported cases. Inputs were the public descriptions, code, repository guidance and CI status/logs; target-PR discussions and existing reviews were not read.

**Suggestion branch:** [review/pr15278-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15278-suggestions), based on the submitted head above; final head [c7540acfc31bd3bfc502810669d0e598c14e3c57](https://github.com/newling/rocm-libraries/commit/c7540acfc31bd3bfc502810669d0e598c14e3c57).

## Tests

Submitted head: `cpu-gemm-driver`, `tensilelite-tests`, and `tensilelite-client` built successfully; **788 driver CTests and 42 focused reference gtests passed**. The driver suite took 5.21 s with four CTest workers. Suggestion implementation: the same targets built; **790 driver CTests and 42 focused reference gtests passed**. Later comment-only commits, where present, do not change that execution result.

Validation used a Release ROCm compiler build. Controlled runs set `OMP_THREAD_LIMIT=8`, `OMP_NUM_THREADS=4`, and `KMP_BLOCKTIME=0`; the original stack-tip driver timing predates the thread-limit setting. These are host numerical tests, not GPU-kernel performance measurements. Root/component hook invocations and full-stack whitespace checks were clean; the formatting hooks opt out of these C++/CMake paths, and no Python tests were selected by the component hook. No local GPU or sanitizer run is claimed.

The gtests were run directly with `--gtest_filter=ReferenceFastPath.*:ReferenceMX*.*:*ReferenceMX*/*`. In the category-based build, a CTest name regex containing `ReferenceFastPath` does not select them. Driver CTests are build-tree tests and are not installed into the TheRock test package; Math CI's unfiltered `coverage-cpp` lane runs them but is informational. The gtest categories include standard/comprehensive/full, not quick.

## Summary

The eligibility relaxation follows the tile invariant: MX blocks remain multiples of the eight-element K tile, and loads beyond logical K are zero-filled. The 18 added driver cases cover short K, tails on one or both scale-block sides, transpose, batching and epilogue features. The exact poisoned-padding gtest is the right kind of independent arithmetic check, but its comparison has a false-negative hole.

This PR also needs to describe the current slow implementation. Its base already contains a K-clamped MX loop, so the retained driver rejection and over-read narrative are stale for equal block sizes.

## Actionable items

### Make the exact MX-tail test reject NaNs

At [tests/ReferenceMXFastPath_test.cpp:274](https://github.com/ROCm/rocm-libraries/blob/e24bb5950c6eacb30a5eb2e201d7e5fba9af6848/projects/hipblaslt/tensilelite/tests/ReferenceMXFastPath_test.cpp#L274), `maxAbsDiff` feeds `fabs(a-b)` to `std::max`. A NaN difference is ignored, leaving a reported maximum of zero. Replacing every computed D element with NaN still lets `PartialLastMXBlockSumsOnlyElementsBelowK` pass.

Suggestion commit [f15ee4aacee](https://github.com/newling/rocm-libraries/commit/f15ee4aacee6031017b93c151ab6f2b3bb618a91) directly compares the finite expected vector with D and retains per-case context. The same all-NaN mutation fails with the fixed assertion. See the appendix for the exact negative control.

### Remove the obsolete equal-block slow-tail rejection

[client/cpu_gemm_driver.cpp:672](https://github.com/ROCm/rocm-libraries/blob/e24bb5950c6eacb30a5eb2e201d7e5fba9af6848/projects/hipblaslt/tensilelite/client/cpu_gemm_driver.cpp#L672) rejects K below or not divisible by an MX block and points users to `--tryFastPath`. The reviewed base already includes [#13630](https://github.com/ROCm/rocm-libraries/pull/13630), which clamps the slow segment to remaining K.

Suggestion commit [b5d8bb5f9a5](https://github.com/newling/rocm-libraries/commit/b5d8bb5f9a552f26384ff3202fc100c608c10014) removes the obsolete K restriction and its help text, and converts the two old BadK tests into positive slow-path tail tests. The corresponding CMake commentary is corrected in [66ef187d435](https://github.com/newling/rocm-libraries/commit/66ef187d43535cacaba49a328b77b0388909291e). Update the PR description's slow-path over-read and before/after claims against the current base; no replacement description was drafted.

## Suggestions

### Share negative-test checking across the stack

[tests/CMakeLists.txt:1158](https://github.com/ROCm/rocm-libraries/blob/e24bb5950c6eacb30a5eb2e201d7e5fba9af6848/projects/hipblaslt/tensilelite/tests/CMakeLists.txt#L1158) and the earlier injected-failure/MX tests accept any nonzero result through `WILL_FAIL`. Suggestion commit [66ef187d435](https://github.com/newling/rocm-libraries/commit/66ef187d43535cacaba49a328b77b0388909291e) introduces one small CMake helper that requires exit code 1 and the intended diagnostic. All 36 existing negative cases pass it; a control with an unrelated expected error correctly fails. This improves error-path coverage without multiplying the feature matrix.

### Expose the eligibility reason to the driver

The existing `rejectFast` reasons are hidden behind `if(false)`, while `--tryFastPath` reports only generic ineligibility. The suggestion adds an optional diagnostic output to the existing predicate and replaces the disabled logger with readable reasons. Two driver cases verify the actual messages for AMAX-D and MX blocks smaller than the fast K tile. The commit mapping below identifies this change.

## Scope decisions

Asymmetric MX blocks remain rejected by the slow driver: that loop still uses the maximum block length, so the equal-block tail correction does not establish asymmetric support. One-sided MX, misaligned fast blocks and non-E8 fast scales retain their eligibility restrictions.

The older approximate `maxAbsDiff` callers are not all rewritten by the new exact-vector assertion. Their general NaN handling can be hardened separately; the newly added exact tail test now catches the demonstrated failure.

## Appendix: exact NaN negative control

At the submitted head, add `<algorithm>` and `<limits>` to `ReferenceMXFastPath_test.cpp`, then insert this line immediately before the assertion at line 274, after `SolveGemmCPU`:

```cpp
std::fill(d.begin(), d.end(), std::numeric_limits<float>::quiet_NaN());
```

Build and run only that test:

```sh
cmake --build "$BUILD_DIR" --target tensilelite-tests -j 4
OMP_THREAD_LIMIT=8 OMP_NUM_THREADS=4 KMP_BLOCKTIME=0 \
  "$BUILD_DIR/tensilelite/tests/tensilelite-tests" \
  --gtest_filter=ReferenceMXFastPath.PartialLastMXBlockSumsOnlyElementsBelowK
```

The submitted assertion passes. With [f15ee4aacee](https://github.com/newling/rocm-libraries/commit/f15ee4aacee6031017b93c151ab6f2b3bb618a91) it fails. The mutation is a temporary control and is not part of the suggestion branch.

## Suggestion branch handoff

| Suggestion commit | Item |
| --- | --- |
| [f15ee4aacee](https://github.com/newling/rocm-libraries/commit/f15ee4aacee6031017b93c151ab6f2b3bb618a91) | reject NaNs in the MX tail reference check |
| [b5d8bb5f9a5](https://github.com/newling/rocm-libraries/commit/b5d8bb5f9a552f26384ff3202fc100c608c10014) | allow supported MX tails in the slow driver path |
| [66ef187d435](https://github.com/newling/rocm-libraries/commit/66ef187d43535cacaba49a328b77b0388909291e) | require the intended CPU driver failure diagnostic |
| [c7540acfc31](https://github.com/newling/rocm-libraries/commit/c7540acfc31bd3bfc502810669d0e598c14e3c57) | explain CPU fast-path ineligibility in the driver |

The suggestion branches are published. Each branch contains its own corrections on its own submitted head, not the other review branches' fixes. Integrate shared changes in stack order, including the alias fix once and later `TypeInfo` call sites. PR-description corrections are reported for the author to make; none were published. See [the cross-PR assessment](review_cpu_reference_stack_15259_15278.md) for test overlap, CI limits and integration notes.
