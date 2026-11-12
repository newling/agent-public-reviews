This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15277](https://github.com/ROCm/rocm-libraries/pull/15277)

**Submitted head:** `46ce0b0c3a676b3878f652e4dbf136bdb1f30f9f`. **Incremental base:** `5b4f85f05f2977d06f67cf5405eff41da6800f93`.

Independent review of the incremental change and its interaction with the CPU-reference stack, emphasizing test adequacy, runtime, overlap, design reuse, and unsupported cases. Inputs were the public descriptions, code, repository guidance and CI status/logs; target-PR discussions and existing reviews were not read.

**Suggestion branch:** [review/pr15277-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15277-suggestions), based on the submitted head above; final head [26f8f56cec2a4517b7edef1ade0da921334d228a](https://github.com/newling/rocm-libraries/commit/26f8f56cec2a4517b7edef1ade0da921334d228a).

## Tests

Submitted head: `cpu-gemm-driver`, `tensilelite-tests`, and `tensilelite-client` built successfully; **770 driver CTests and 40 focused reference gtests passed**. The driver suite took 5.10 s with four CTest workers. Suggestion implementation: the same targets built; **770 driver CTests and 42 focused reference gtests passed**. Later comment-only commits, where present, do not change that execution result.

Validation used a Release ROCm compiler build. Controlled runs set `OMP_THREAD_LIMIT=8`, `OMP_NUM_THREADS=4`, and `KMP_BLOCKTIME=0`; the original stack-tip driver timing predates the thread-limit setting. These are host numerical tests, not GPU-kernel performance measurements. Root/component hook invocations and full-stack whitespace checks were clean; the formatting hooks opt out of these C++/CMake paths, and no Python tests were selected by the component hook. No local GPU or sanitizer run is claimed.

The gtests were run directly with `--gtest_filter=ReferenceFastPath.*:ReferenceMX*.*:*ReferenceMX*/*`. In the category-based build, a CTest name regex containing `ReferenceFastPath` does not select them. Driver CTests are build-tree tests and are not installed into the TheRock test package; Math CI's unfiltered `coverage-cpp` lane runs them but is informational. The gtest categories include standard/comprehensive/full, not quick.

## Summary

E storage and gradient execution fit naturally into the existing epilogue. Reusing the reference's cast and reduction code is preferable to introducing another numerical implementation. The 70 added driver cases and five new gtests cover E ordering, E padding, activation-gradient use, A/B/D reduction sources, transpose, batching without bias reduction, and sampled validation.

Two material gaps remain despite those tests: the driver rejects unsupported batched bias gradients before exercising the reference's fallback, and the driver uses HPA so it does not reveal non-HPA reduction changes.

## Actionable items

### Report unsupported reduction shapes without double-freeing the workspace

[client/src/Reference.cpp:1398](https://github.com/ROCm/rocm-libraries/blob/46ce0b0c3a676b3878f652e4dbf136bdb1f30f9f/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1398) explicitly routes unsupported reduction shapes to the slow path. At [client/src/Reference.cpp:2801](https://github.com/ROCm/rocm-libraries/blob/46ce0b0c3a676b3878f652e4dbf136bdb1f30f9f/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L2801), that existing slow code frees the workspace and constructs, but does not throw, a `runtime_error`; it later frees the workspace again.

A 1×1×1 Float GEMM with two batches, gradient enabled, and bias reduced from D aborts with a double-free both when requesting fast execution and when explicitly requesting slow execution. This is an inherited defect carried by the fallback, not a claim that this PR introduced the original free.

Suggestion commit [66106f99d91](https://github.com/newling/rocm-libraries/commit/66106f99d916da886beecc39e464681596074b6d) makes the slow path use the same `reduceBiasGradient` helper, gives workspace ownership to `std::vector`, and consumes the reduction error. The diagnostic now states the 2-D/single-batch requirement and actual batch count. `BatchedBiasGradientReportsUnsupportedShape` covers A, B and D sources through both requested paths and verifies the message and unchanged bias. Commit [26f8f56cec2](https://github.com/newling/rocm-libraries/commit/26f8f56cec2a4517b7edef1ade0da921334d228a) updates the shared helper's comment.

### Preserve non-HPA reduction rounding or explicitly define a different reference policy

[client/src/Reference.cpp:1642](https://github.com/ROCm/rocm-libraries/blob/46ce0b0c3a676b3878f652e4dbf136bdb1f30f9f/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1642) reduces in fast-path `AccumT`, which is float for non-HPA Half/BFloat16 cases that the slow path reduces in their narrow type. This is not bounded to last-bit variation.

With an all-one Half GEMM, M=K=1 and N=4097, every D value is 1 on both paths, but the bias gradient is **2048** on slow and **4096** on fast. Repeated narrow additions stop changing at 2048; a float reduction followed by a Half conversion behaves differently.

Suggestion commit [de7815c2e50](https://github.com/newling/rocm-libraries/commit/de7815c2e5066f6b2ff76e589732a3b8a671e402) retains the slow path for non-HPA `H_H_H` and `B_B_S` gradient+bias problems. `NonHpaBiasGradientKeepsNarrowAccumulation` covers the Half and BFloat16 rounding boundaries. If wider accumulation is desired instead, it needs an explicit numerical-policy decision and corresponding tests rather than a general “last bits” explanation.

## Suggestions

Use the shared negative-test helper from #15278 ([66ef187d435](https://github.com/newling/rocm-libraries/commit/66ef187d43535cacaba49a328b77b0388909291e)) for the driver's unsupported gradient cases. The direct reference regression is still necessary: driver argument rejection alone cannot test fallback cleanup.

## Scope decisions

The suggested fix preserves the existing one-batch reduction limitation and the selected source's reduction semantics. It adds no batched bias-gradient implementation. The allocation/error fix was checked with the deterministic reproducer and normal native tests; an instrumented sanitizer build was not run locally.

The exact native probe source and build recipe for the numerical counterexamples are preserved in the [cross-PR appendix](review_cpu_reference_stack_15259_15278.md#appendix-native-counterexample-source-and-setup). Committed regressions cover the corresponding contracts.

## Suggestion branch handoff

| Suggestion commit | Item |
| --- | --- |
| [66106f99d91](https://github.com/newling/rocm-libraries/commit/66106f99d916da886beecc39e464681596074b6d) | share bias reduction and report unsupported shapes |
| [de7815c2e50](https://github.com/newling/rocm-libraries/commit/de7815c2e5066f6b2ff76e589732a3b8a671e402) | preserve non-HPA bias-gradient accumulation |
| [26f8f56cec2](https://github.com/newling/rocm-libraries/commit/26f8f56cec2a4517b7edef1ade0da921334d228a) | describe the shared bias-gradient reduction |

The suggestion branches are published. Each branch contains its own corrections on its own submitted head, not the other review branches' fixes. Integrate shared changes in stack order, including the alias fix once and later `TypeInfo` call sites. PR-description corrections are reported for the author to make; none were published. See [the cross-PR assessment](review_cpu_reference_stack_15259_15278.md) for test overlap, CI limits and integration notes.
