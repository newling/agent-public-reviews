This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15276](https://github.com/ROCm/rocm-libraries/pull/15276)

**Submitted head:** `5b4f85f05f2977d06f67cf5405eff41da6800f93`. **Incremental base:** `b6828c46316720641f2e3f15a1320201d4f1c34b`.

Independent review of the incremental change and its interaction with the CPU-reference stack, emphasizing test adequacy, runtime, overlap, design reuse, and unsupported cases. Inputs were the public descriptions, code, repository guidance and CI status/logs; target-PR discussions and existing reviews were not read.

**Suggestion branch:** [review/pr15276-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15276-suggestions), based on the submitted head above; final head [7c3393ef929f82a8f899ded5a245816265954a1d](https://github.com/newling/rocm-libraries/commit/7c3393ef929f82a8f899ded5a245816265954a1d).

## Tests

Submitted head: `cpu-gemm-driver`, `tensilelite-tests`, and `tensilelite-client` built successfully; **700 driver CTests and 35 focused reference gtests passed**. The driver suite took 4.54 s with four CTest workers. Suggestion implementation: the same targets built; **700 driver CTests and 36 focused reference gtests passed**. Later comment-only commits, where present, do not change that execution result.

Validation used a Release ROCm compiler build. Controlled runs set `OMP_THREAD_LIMIT=8`, `OMP_NUM_THREADS=4`, and `KMP_BLOCKTIME=0`; the original stack-tip driver timing predates the thread-limit setting. These are host numerical tests, not GPU-kernel performance measurements. Root/component hook invocations and full-stack whitespace checks were clean; the formatting hooks opt out of these C++/CMake paths, and no Python tests were selected by the component hook. No local GPU or sanitizer run is claimed.

The gtests were run directly with `--gtest_filter=ReferenceFastPath.*:ReferenceMX*.*:*ReferenceMX*/*`. In the category-based build, a CTest name regex containing `ReferenceFastPath` does not select them. Driver CTests are build-tree tests and are not installed into the TheRock test package; Math CI's unfiltered `coverage-cpp` lane runs them but is informational. The gtest categories include standard/comprehensive/full, not quick.

## Summary

Using the existing tiled solver with complex accumulator types and applying conjugation during shadow-buffer loading is a coherent extension. The eligibility exclusions correctly avoid claiming support for complex epilogues whose slow helpers do not implement the corresponding values.

The 53 added driver cases cover both widths, transpose, conjugation, alpha/beta and batching. The three new gtests supply direct complex arithmetic/conjugation checks and a finite-data comparison. These are complementary; an in-place beta test is the important omission.

## Actionable items

### Preserve aliased complex C through the epilogue

[client/src/Reference.cpp:1958](https://github.com/ROCm/rocm-libraries/blob/5b4f85f05f2977d06f67cf5405eff41da6800f93/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1958) writes the tile sums into D before using C. When complex C and D share storage, the complex shadow buffer aliases C and the beta input is overwritten.

A 1×1 complex-float example with A=(2,0), B=(3,0), C=D initially (5,1), and alpha=beta=(1,0) gives **(12,0)** on the submitted fast path rather than **(11,1)**. The probe ran against the submitted stack tip; the complex path is introduced here.

Suggestion commit [7c3393ef929](https://github.com/newling/rocm-libraries/commit/7c3393ef929f82a8f899ded5a245816265954a1d) reads the sum directly from `cReg` and writes D after reading C. `ComplexInPlaceCDPreservesBetaInput` checks both complex float and complex double with nonzero imaginary components.

## Suggestions

### Correct the stale alpha-zero description

The PR description says the fast path computes `0 * sum` while the slow path skips contraction. The reviewed base already contains the effective-alpha-zero guard from [#13482](https://github.com/ROCm/rocm-libraries/pull/13482). Update that claim to describe the current base. No replacement description was drafted or published.

The generic driver rejection checks would benefit from the shared diagnostic helper implemented in #15278 ([66ef187d435](https://github.com/newling/rocm-libraries/commit/66ef187d43535cacaba49a328b77b0388909291e)). Complex bias/scaling/E/gradient rejections should continue identifying the unsupported feature, not just returning failure.

## Scope decisions

This suggestion repeats #15274's common epilogue correction because each review branch is independently based on its own submitted head. When combining them, keep that production correction once and both type-specific regressions.

Non-finite complex multiplication remains a documented compatibility boundary. The finite-data comparison does not establish identical behavior for overflow, NaNs, or every compiler/platform. No GPU execution or platform-wide complex-arithmetic qualification was performed locally.

The exact native probe source and build recipe for the numerical counterexamples are preserved in the [cross-PR appendix](review_cpu_reference_stack_15259_15278.md#appendix-native-counterexample-source-and-setup). Committed regressions cover the corresponding contracts.

## Suggestion branch handoff

| Suggestion commit | Item |
| --- | --- |
| [7c3393ef929](https://github.com/newling/rocm-libraries/commit/7c3393ef929f82a8f899ded5a245816265954a1d) | preserve aliased complex C before writing D |

The suggestion branches are published. Each branch contains its own corrections on its own submitted head, not the other review branches' fixes. Integrate shared changes in stack order, including the alias fix once and later `TypeInfo` call sites. PR-description corrections are reported for the author to make; none were published. See [the cross-PR assessment](review_cpu_reference_stack_15259_15278.md) for test overlap, CI limits and integration notes.
