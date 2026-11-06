This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14725](https://github.com/ROCm/rocm-libraries/pull/14725)

Reviewed head: `4d2d837b9f8bb7a4b03e37db2b864584864f9e99`. Diff base: `e378005d4746f108443614203e58eeef34e596c1`; fetched develop: `d38d6b661e09473aa8ce04fc89a83f3e0b05db62`.

Independent review focused on MX input reuse, scale storage, and interaction with [HostNumerics prototype #10553](https://github.com/ROCm/rocm-libraries/pull/10553) at `1bdacfb62e690481cd9f83c89cbf86adf1c9ac43`. This is not a full review of the prototype. Existing PR discussion was not consulted.

Suggestion branch: [review/pr14725-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14725-suggestions), based on the reviewed head. Commits: [513612eb2db](https://github.com/newling/rocm-libraries/commit/513612eb2db0289b3bcf4681872dc4e61753a112) adds direct standard-library includes; [fa8212eda37](https://github.com/newling/rocm-libraries/commit/fa8212eda37dda7309d59bd5cb761efb510f761c) clarifies the remaining per-run work. Neither changes numerical behavior.

## Tests

Built `tensilelite-client` and `tensilelite-tests` with ROCm 7.1 AMDClang, Release, OpenMP enabled. The focused DataInit selection passes **100 tests**, including all 34 new scale-conversion tests, on both the submitted head and the include-fix commit. Four architecture-gated cases skip locally: two existing reference-policy tests and the two new gfx950 cache-transition tests. The final commit changes comments only. A translation unit including `DataInitializationHelpers.hpp` alone also compiles with the client target's flags. Whitespace checks pass; the root pre-commit configuration skips these hipBLASLt files.

The swizzle tests compare the new helper against the existing `generateMXInput` path, check unchanged data bytes, and use a sentinel to check the output length. The inverse-restride test fills padding with a distinct value and proves a direct prefix copy differs from the expected result. These assertions exercise meaningful layout errors.

No local MX-capable GPU execution, sanitizer run, or reproduction of the launch-time benchmark was performed. The PR description reports MI355X execution and matched before/after timings; those are author-provided evidence. The four required checks pass at the reviewed head. The broader check set includes an FFM gfx1250 failure (one failed case, `gsuasb_fp32_atomic_gfx1250`, and seven timeouts) and three Codecov failures. Their cause was not established by this focused review; a passing required summary does not make the complete check set green.

## Summary

The change fits HostNumerics' intended division of responsibility. MX inputs contain packed low-precision values and separate block scales. Generating those values, arranging scales for a particular GPU, and deciding when buffers need refreshing are distinct operations. This PR separates more of that work in the existing client. HostNumerics already provides separate generation and physical-layout operations, while the client adapter owns buffer lifetime, solution selection, and uploads.

The cache invalidation when a solution requests ordinary scales is important: that upload overwrites the cached GPU layout, so a later solution requiring reordered scales must rebuild it. The new transition test deliberately uses varying scales, avoiding a false pass from constant scales whose layouts look identical.

I found no numerical correctness defect in the inspected paths. The important qualification is that this PR reduces repeated preparation without eliminating every per-candidate copy or reference computation.

### How it fits #10553

| Concern | #14725 | Current #10553 | Integration consequence |
| --- | --- | --- | --- |
| Generate canonical data and scales | Keeps them when descriptors match, even when a GPU scale layout must be built | Has descriptor/layout cache hits, but a missing gfx950 layout still reaches `generateMxData` again | Preserve canonical inputs separately from the cached GPU layout |
| Prepare the first gfx950 scale layout | Recovers scales from the existing CPU buffer and reorders them without regenerating A/B | Generates once in the initialization call and derives its physical scale from that result; the first layout-changing call still regenerates | Reconstruct a scale tensor from retained canonical storage and call the existing layout API |
| Consecutive solutions | Skips the extra `preSolution` refresh for an unchanged MFMA K, the instruction's reduction dimension | Still refreshes and copies buffers for every eligible solution | Carry over the client lifecycle gate and ordinary-scale invalidation |
| Validation disabled | Avoids repeated `initializeCPUInputs` after initialization for the problem | Still invokes that path on each GPU preparation when CPU reference buffers are absent | Carry over the readiness state, including reset at each problem |
| Physical scale conversion | Uses legacy mxDataGenerator helpers | Uses `MxScaleStoragePlan` and `copyMxScaleStorageToPhysicalLayout` | Keep the HostNumerics implementation of the permutation |

The relevant prototype code is [`initializeMXData`](https://github.com/ROCm/rocm-libraries/blob/1bdacfb62e690481cd9f83c89cbf86adf1c9ac43/projects/hipblaslt/tensilelite/client/src/DataInitialization.cpp#L1850), including generation at line 2006 and scale conversion at line 2047, and [`preSolution`](https://github.com/ROCm/rocm-libraries/blob/1bdacfb62e690481cd9f83c89cbf86adf1c9ac43/projects/hipblaslt/tensilelite/client/include/DataInitialization.hpp#L522). The shared [physical-layout API](https://github.com/ROCm/rocm-libraries/blob/1bdacfb62e690481cd9f83c89cbf86adf1c9ac43/shared/hostnumerics/include/roc/hostnumerics/amd_gpu_layout/mx.hpp#L34) already handles padding and the GPU permutation. The prototype also already transposes the gfx950 free-dimension-contiguous scale tensor into `[MN, K blocks]` before that operation.

A dry merge of the two reviewed heads reports conflicts in **all four files** changed by #14725, including deletion/modification of the legacy `DataInitializationHelpers.hpp`. This calls for adapting the optimization to the HostNumerics adapter, preserving its generation policies and seeds. Restoring the deleted legacy helpers would undo that migration.

There is no architectural reason for this client optimization to wait for the complete HostNumerics prototype. When integrating it, retain the two lifecycle regressions and adapt the byte-layout coverage to the shared APIs. Benchmark the resulting prototype on the same workload and CPU allocation: [`generateMx`](https://github.com/ROCm/rocm-libraries/blob/1bdacfb62e690481cd9f83c89cbf86adf1c9ac43/shared/hostnumerics/src/mx_generation.cpp#L422) also constructs per-element scale-index and decoded-reference tensors. The current adapter generates those even with client validation disabled. That is a separate preparation cost, and this PR's timings do not measure it. Cache the existing canonical data/scales without retaining those extra tensors merely to enable reuse.

## Actionable items

### Clarify which repeated work remains

[`DataInitialization.hpp:923`](https://github.com/ROCm/rocm-libraries/blob/4d2d837b9f8bb7a4b03e37db2b864584864f9e99/projects/hipblaslt/tensilelite/client/include/DataInitialization.hpp#L923) describes consecutive solutions as reusing uploaded data. The new gate skips the additional refresh in this callback. However, `main.cpp:1238` still calls `prepareGPUInputs` during run reset, and `DataInitialization.hpp:406` still calls `copyValidToGPUBuffer` for problem-dependent inputs. MX enables that condition. Ordinary, non-swizzled A/B buffers therefore still undergo host-to-device copies on this path.

Likewise, `DataInitialization.hpp:183` describes the CPU reference policy, but its predicate continues to return true for eligible gfx950 HostPreSwizzle solutions even on a cache hit. `ReferenceValidator.cpp:166` consequently still invokes `SolveCPU` for each such solution.

Describe this as removing duplicate preparation and retaining regular reset/reference work. Commit **[fa8212eda37](https://github.com/newling/rocm-libraries/commit/fa8212eda37dda7309d59bd5cb761efb510f761c)** corrects the two comments. It deliberately preserves the existing reset and reference behavior.

## Suggestions

When carrying the change into HostNumerics, add a small lifecycle check of generation/upload counts alongside the existing byte checks. The present tests establish correct results and invalidation, but would not detect all regressions that restore unnecessary generation or copies. Cover repeated equal-layout candidates, an ordinary-scale candidate between two reordered-scale candidates, and a subsequent problem. Use the client boundary to observe work; keep the numerical oracle independent.

### Include the standard-library dependencies directly

[`DataInitializationHelpers.hpp:18`](https://github.com/ROCm/rocm-libraries/blob/4d2d837b9f8bb7a4b03e37db2b864584864f9e99/projects/hipblaslt/tensilelite/client/include/DataInitializationHelpers.hpp#L18) adds vector-returning helpers while obtaining `<vector>` transitively. The new test helpers also use `std::shared_ptr` and `std::pair` without their owning headers.

Commit **[513612eb2db](https://github.com/newling/rocm-libraries/commit/513612eb2db0289b3bcf4681872dc4e61753a112)** adds `<cstddef>` and `<vector>` to the helper header, and `<memory>` and `<utility>` to the tests. Both direct consumers rebuild successfully. This is a dependency declaration correction, not an observed build failure.

## Scope decisions

Removing the remaining uploads and reference solves is separable from preserving this PR's improvement. Output buffers, bounds checks, and rotating buffers still need their existing reset behavior, so deleting the broad reset path would require a separate correctness argument. Copy-ready scope text:

> This change avoids repeated canonical MX generation and skips the extra input refresh for consecutive solutions with the same MFMA K. Regular per-run buffer resets and per-solution CPU reference computation remain unchanged. Further reuse requires separating immutable input uploads from output reset and tying reference recomputation to changes in canonical input values.

The handoff is [review/pr14725-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14725-suggestions) at **[fa8212eda37](https://github.com/newling/rocm-libraries/commit/fa8212eda37dda7309d59bd5cb761efb510f761c)**, with the two commits mapped above. The suggestion commits accompany this report; no integration changes were made to #10553.
