This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15259](https://github.com/ROCm/rocm-libraries/pull/15259)

**Submitted head:** `571ecae3fc4814ff951461d1d14e48f780975511`. **Incremental base:** `e8b44f8b6b0e8d9ffffc294203d6ef063a85f40d`.

Independent review of the incremental change and its interaction with the CPU-reference stack, emphasizing test adequacy, runtime, overlap, design reuse, and unsupported cases. Inputs were the public descriptions, code, repository guidance and CI status/logs; target-PR discussions and existing reviews were not read.

**Suggestion branch:** [review/pr15259-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15259-suggestions), based on the submitted head above; final head [f8ae33f65755293d932e7066102d1b3378d71146](https://github.com/newling/rocm-libraries/commit/f8ae33f65755293d932e7066102d1b3378d71146).

## Tests

Submitted head: `cpu-gemm-driver`, `tensilelite-tests`, and `tensilelite-client` built successfully; **297 driver CTests and 24 focused reference gtests passed**. The driver suite took 2.29 s with four CTest workers. Suggestion implementation: the same targets built; **297 driver CTests and 24 focused reference gtests passed**. Later comment-only commits, where present, do not change that execution result.

Validation used a Release ROCm compiler build. Controlled runs set `OMP_THREAD_LIMIT=8`, `OMP_NUM_THREADS=4`, and `KMP_BLOCKTIME=0`; the original stack-tip driver timing predates the thread-limit setting. These are host numerical tests, not GPU-kernel performance measurements. Root/component hook invocations and full-stack whitespace checks were clean; the formatting hooks opt out of these C++/CMake paths, and no Python tests were selected by the component hook. No local GPU or sanitizer run is claimed.

The gtests were run directly with `--gtest_filter=ReferenceFastPath.*:ReferenceMX*.*:*ReferenceMX*/*`. In the category-based build, a CTest name regex containing `ReferenceFastPath` does not select them. Driver CTests are build-tree tests and are not installed into the TheRock test package; Math CI's unfiltered `coverage-cpp` lane runs them but is informational. The gtest categories include standard/comprehensive/full, not quick.

## Summary

The important optimization is removing synchronization from ordinary slow-path output writes. Per-thread AMAX-D maxima retain one small merge per participating thread and work with class accumulator types that do not support OpenMP's built-in max reduction. I found no correctness defect in that change.

The 14 added tests are appropriately scoped: ordinary and combined epilogues, several accumulator/storage types, batching, zero alpha, and a negative 1×1 value. The driver's independent GEMM and the initial AMAX-D sentinel help detect a missing write. These tests exercise a distinct output contract and are not duplicated by the later fast-path tests.

## Actionable items

None for the lock/max restructuring.

## Suggestions

### Remove the redundant OpenMP policy update inside the output loop

[client/src/Reference.cpp:2256](https://github.com/ROCm/rocm-libraries/blob/571ecae3fc4814ff951461d1d14e48f780975511/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L2256) calls `omp_set_num_threads(64)` for every output after the parallel region has already started. It cannot resize that region and is unrelated to computing the maximum. Suggestion commit [f8ae33f6575](https://github.com/newling/rocm-libraries/commit/f8ae33f65755293d932e7066102d1b3378d71146) removes it; the outer thread policy is retained.

The test descriptions' `OMP_NUM_THREADS=1/3/32` runs do not establish those team sizes: the outer call overrides that setting. Use `OMP_THREAD_LIMIT` or record the observed team size. All 14 AMAX-D cases passed locally with limits of 1, 3, and 8. This strengthens the merge-coverage evidence without adding a permanent test matrix.

## Scope decisions

The published performance numbers refer to earlier unsplit work and common-test replay. I did not reproduce those GPU-workload timings. The source change removes the identified serialization, and local test runtimes are reported separately from performance claims. A broader redesign of the fixed 64-thread policy is independent of this optimization.

## Suggestion branch handoff

| Suggestion commit | Item |
| --- | --- |
| [f8ae33f6575](https://github.com/newling/rocm-libraries/commit/f8ae33f65755293d932e7066102d1b3378d71146) | avoid resetting OpenMP policy for every output |

The suggestion branches are published. Each branch contains its own corrections on its own submitted head, not the other review branches' fixes. Integrate shared changes in stack order, including the alias fix once and later `TypeInfo` call sites. PR-description corrections are reported for the author to make; none were published. See [the cross-PR assessment](review_cpu_reference_stack_15259_15278.md) for test overlap, CI limits and integration notes.
