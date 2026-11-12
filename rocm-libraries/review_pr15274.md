This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15274](https://github.com/ROCm/rocm-libraries/pull/15274)

**Submitted head:** `f58bbb3388853e13cdf85bda0917485d590c4ddc`. **Incremental base:** `4554dab796dee28e4e640b7f688c4d0f12d5b375`.

Independent review of the incremental change and its interaction with the CPU-reference stack, emphasizing test adequacy, runtime, overlap, design reuse, and unsupported cases. Inputs were the public descriptions, code, repository guidance and CI status/logs; target-PR discussions and existing reviews were not read.

**Suggestion branch:** [review/pr15274-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15274-suggestions), based on the submitted head above; final head [8886ad2d584b154fc7d986ce49f7b20e56661d7d](https://github.com/newling/rocm-libraries/commit/8886ad2d584b154fc7d986ce49f7b20e56661d7d).

## Tests

Submitted head: `cpu-gemm-driver`, `tensilelite-tests`, and `tensilelite-client` built successfully; **440 driver CTests and 30 focused reference gtests passed**. The driver suite took 2.74 s with four CTest workers. Suggestion implementation: the same targets built; **440 driver CTests and 31 focused reference gtests passed**. Later comment-only commits, where present, do not change that execution result.

Validation used a Release ROCm compiler build. Controlled runs set `OMP_THREAD_LIMIT=8`, `OMP_NUM_THREADS=4`, and `KMP_BLOCKTIME=0`; the original stack-tip driver timing predates the thread-limit setting. These are host numerical tests, not GPU-kernel performance measurements. Root/component hook invocations and full-stack whitespace checks were clean; the formatting hooks opt out of these C++/CMake paths, and no Python tests were selected by the component hook. No local GPU or sanitizer run is claimed.

The gtests were run directly with `--gtest_filter=ReferenceFastPath.*:ReferenceMX*.*:*ReferenceMX*/*`. In the category-based build, a CTest name regex containing `ReferenceFastPath` does not select them. Driver CTests are build-tree tests and are not installed into the TheRock test package; Math CI's unfiltered `coverage-cpp` lane runs them but is informational. The gtest categories include standard/comprehensive/full, not quick.

## Summary

Separating the integer K-loop accumulator from the epilogue type is a sound way to reuse the tiled implementation. It avoids forcing Int8 multiplication through float and retains the slow epilogue's operation order and saturating casts. The six type-ID gate keeps dispatch explicit.

The 79 added driver cases complement the earlier slow baseline. The narrow-range tests are especially valuable because saturation otherwise hides many arithmetic errors. The six new gtests target rounding, large sums and edge conditions; those are worth keeping alongside the broader dispatch matrix. The missing aliasing case is a correctness gap.

## Actionable items

### Read the original C before writing an aliased D

At [client/src/Reference.cpp:1816](https://github.com/ROCm/rocm-libraries/blob/f58bbb3388853e13cdf85bda0917485d590c4ddc/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1816), the tile sum is copied to D before the epilogue reads C. With Int32 C/D, the shadow buffer can refer directly to C. If C and D share storage, the copy destroys the beta input.

A 1×1 Int8 GEMM with A=2, B=3, C=D initially 5 and alpha=beta=1 returns **12** on the submitted fast path instead of **11** on the slow path. The counterexample was reproduced against the submitted stack tip; this PR first admits the affected Int8 types.

Suggestion commit [1024648658c](https://github.com/newling/rocm-libraries/commit/1024648658c17b9f3dfafb3aa41929817081c84f) removes the intermediate tile-to-D copy, takes the epilogue input directly from `cReg`, and writes only the final result. `Int8InPlaceCDPreservesBetaInput` is a compact regression with an independently known answer. This fixes the alias and eliminates redundant memory work.

## Suggestions

### Bound the claim of exact integer accumulation

[tests/CMakeLists.txt:737](https://github.com/ROCm/rocm-libraries/blob/f58bbb3388853e13cdf85bda0917485d590c4ddc/projects/hipblaslt/tensilelite/tests/CMakeLists.txt#L737) says int32 accumulation is exact at any K. Every intermediate sum must fit in Int32, and the float slow path can lose precision once sums exceed 2^24. Suggestion commits [3b524a30398](https://github.com/newling/rocm-libraries/commit/3b524a30398c6e136a3d049dc78fae2053ce3d97) and [8886ad2d584](https://github.com/newling/rocm-libraries/commit/8886ad2d584b154fc7d986ce49f7b20e56661d7d) state those boundaries in the solver and test comments. No overflow policy is changed.

## Scope decisions

The slow/fast driver pairs intentionally exercise different implementations. Do not replace the integer golden oracle with a fast-versus-slow-only comparison: above 2^24, the more precise fast result is intentionally different from the float slow result.

#15276 exposes the same intermediate-write defect for complex C/D. Its suggestion contains the same production correction plus a complex regression. Apply the production change once across the stack and retain both regressions.

The exact native probe source and build recipe for the numerical counterexamples are preserved in the [cross-PR appendix](review_cpu_reference_stack_15259_15278.md#appendix-native-counterexample-source-and-setup). Committed regressions cover the corresponding contracts.

## Suggestion branch handoff

| Suggestion commit | Item |
| --- | --- |
| [1024648658c](https://github.com/newling/rocm-libraries/commit/1024648658c17b9f3dfafb3aa41929817081c84f) | apply the Int8 epilogue before writing aliased D |
| [3b524a30398](https://github.com/newling/rocm-libraries/commit/3b524a30398c6e136a3d049dc78fae2053ce3d97) | state the limits of exact Int8 accumulation |
| [8886ad2d584](https://github.com/newling/rocm-libraries/commit/8886ad2d584b154fc7d986ce49f7b20e56661d7d) | bound the integer reference test claim |

The suggestion branches are published. Each branch contains its own corrections on its own submitted head, not the other review branches' fixes. Integrate shared changes in stack order, including the alias fix once and later `TypeInfo` call sites. PR-description corrections are reported for the author to make; none were published. See [the cross-PR assessment](review_cpu_reference_stack_15259_15278.md) for test overlap, CI limits and integration notes.
