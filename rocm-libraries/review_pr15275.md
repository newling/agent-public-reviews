This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15275](https://github.com/ROCm/rocm-libraries/pull/15275)

**Submitted head:** `b6828c46316720641f2e3f15a1320201d4f1c34b`. **Incremental base:** `f58bbb3388853e13cdf85bda0917485d590c4ddc`.

Independent review of the incremental change and its interaction with the CPU-reference stack, emphasizing test adequacy, runtime, overlap, design reuse, and unsupported cases. Inputs were the public descriptions, code, repository guidance and CI status/logs; target-PR discussions and existing reviews were not read.

**Suggestion branch:** [review/pr15275-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15275-suggestions), based on the submitted head above; final head [aef34bafaad8296981db27b07f6f2fe96bd6258e](https://github.com/newling/rocm-libraries/commit/aef34bafaad8296981db27b07f6f2fe96bd6258e).

## Tests

Submitted head: `cpu-gemm-driver`, `tensilelite-tests`, and `tensilelite-client` built successfully; **647 driver CTests and 32 focused reference gtests passed**. The driver suite took 4.18 s with four CTest workers. Suggestion implementation: the same targets built; **647 driver CTests and 33 focused reference gtests passed**. Later comment-only commits, where present, do not change that execution result.

Validation used a Release ROCm compiler build. Controlled runs set `OMP_THREAD_LIMIT=8`, `OMP_NUM_THREADS=4`, and `KMP_BLOCKTIME=0`; the original stack-tip driver timing predates the thread-limit setting. These are host numerical tests, not GPU-kernel performance measurements. Root/component hook invocations and full-stack whitespace checks were clean; the formatting hooks opt out of these C++/CMake paths, and no Python tests were selected by the component hook. No local GPU or sanitizer run is claimed.

The gtests were run directly with `--gtest_filter=ReferenceFastPath.*:ReferenceMX*.*:*ReferenceMX*/*`. In the category-based build, a CTest name regex containing `ReferenceFastPath` does not select them. Driver CTests are build-tree tests and are not installed into the TheRock test package; Math CI's unfiltered `coverage-cpp` lane runs them but is informational. The gtest categories include standard/comprehensive/full, not quick.

## Summary

Reusing the float accumulator and the existing saturating output cast keeps the fast implementation small. The 207 added driver cases are already reduced by responsibility: four homogeneous IDs get the full feature matrix; hybrid/cross-output IDs get a smaller matrix. The two new gtests exercise eligibility and conversion limits. This is useful coverage at a reasonable runtime.

However, the `noscale` subset deliberately avoids a combination that the production eligibility check still accepts. The resulting gap is about conversion semantics, not merely the number of tests.

## Actionable items

### Keep scaled Half-to-Float8 narrowing out of the fast path until its semantics match

[client/src/Reference.cpp:1354](https://github.com/ROCm/rocm-libraries/blob/b6828c46316720641f2e3f15a1320201d4f1c34b/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1354) admits Float8 outputs with a Half storage operand narrowed to Float8 and Scalar/Vector ScaleAB. [tests/CMakeLists.txt:837](https://github.com/ROCm/rocm-libraries/blob/b6828c46316720641f2e3f15a1320201d4f1c34b/projects/hipblaslt/tensilelite/tests/CMakeLists.txt#L837) explicitly omits scaling tests for these IDs because the paths handle it differently.

For a 1×1 problem with Half A=0.9, Float8 B=1, scaleA=3, scaleB=1, alpha=1 and beta=0, the scalar slow path gives **2.75** while the fast path gives **2.5**: scaling occurs on opposite sides of the narrowing conversion. Vector scaling is more substantial: the slow path omits that operand's scale while the fast path applies it. This is not covered by an explanation limited to last-bit reassociation.

Suggestion commit [d930b5107f1](https://github.com/newling/rocm-libraries/commit/d930b5107f10b667c55bfe4a9454e4f4fa8f9d4b) rejects these combinations from fast eligibility and adds `ScaledHalfToFloat8KeepsSlowPathConversionOrder`, covering both operand directions and both scale modes. The ordinary solver request then preserves the slow behavior. The driver, when explicitly forced to use fast, reports ineligibility.

## Suggestions

### Include the failing type configuration in runtime errors

At [client/cpu_gemm_driver.cpp:1585](https://github.com/ROCm/rocm-libraries/blob/b6828c46316720641f2e3f15a1320201d4f1c34b/projects/hipblaslt/tensilelite/client/cpu_gemm_driver.cpp#L1585), `--typeA f8 --typeB f16 --typeCD f8` reaches the reference and prints only `Data type not implemented.` The missing piece is the compute-input combination. Suggestion commit [aef34bafaad](https://github.com/newling/rocm-libraries/commit/aef34bafaad8296981db27b07f6f2fe96bd6258e) appends storage, compute-input, output, and scalar selectors to runtime errors without duplicating the reference's type-ID allowlist. This command now identifies `computeInputA=f8, computeInputB=f16`; choosing both compute inputs as Half or both as the matching Float8 encoding gives the supported alternatives.

The shared negative-test helper in #15278 ([66ef187d435](https://github.com/newling/rocm-libraries/commit/66ef187d43535cacaba49a328b77b0388909291e)) strengthens the existing rejection and injected-failure cases. Its additional eligibility-diagnostic change exposes the fast-path reason to the driver.

## Scope decisions

The suggestion deliberately retains the pre-existing Vector ScaleAB omission on the slow path; it does not claim to correct that formula. A separate change can define and align scaling/conversion semantics across output types. Until then, enabling those cases on the fast path changes reference behavior substantially.

No wholesale expansion of the 24-ID matrix is needed. A compact conversion-order regression is more useful than repeating all transpose and feature combinations for this boundary.

The exact native probe source and build recipe for the numerical counterexamples are preserved in the [cross-PR appendix](review_cpu_reference_stack_15259_15278.md#appendix-native-counterexample-source-and-setup). Committed regressions cover the corresponding contracts.

## Suggestion branch handoff

| Suggestion commit | Item |
| --- | --- |
| [d930b5107f1](https://github.com/newling/rocm-libraries/commit/d930b5107f10b667c55bfe4a9454e4f4fa8f9d4b) | retain scaled narrow-input Float8 reference semantics |
| [aef34bafaad](https://github.com/newling/rocm-libraries/commit/aef34bafaad8296981db27b07f6f2fe96bd6258e) | identify the type combination in driver runtime errors |

The suggestion branches are published. Each branch contains its own corrections on its own submitted head, not the other review branches' fixes. Integrate shared changes in stack order, including the alias fix once and later `TypeInfo` call sites. PR-description corrections are reported for the author to make; none were published. See [the cross-PR assessment](review_cpu_reference_stack_15259_15278.md) for test overlap, CI limits and integration notes.
