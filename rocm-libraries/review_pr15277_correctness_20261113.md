This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15277](https://github.com/ROCm/rocm-libraries/pull/15277)

**Submitted head:** `46ce0b0c3a676b3878f652e4dbf136bdb1f30f9f`. **Incremental diff base:** `5b4f85f05f2977d06f67cf5405eff41da6800f93`.

**Scope:** Focused follow-up on consequential CPU-reference errors and regression-test failures, including the existing review discussion. Head and discussion were unchanged at the 2026-11-13 23:09 UTC check. Earlier validation is reused where the tested code is unchanged.

**Suggestion branch:** [review/pr15277-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15277-correctness-20261113), based on the submitted head; final head [de7815c2e50](https://github.com/newling/rocm-libraries/commit/de7815c2e5066f6b2ff76e589732a3b8a671e402). Commit-to-item mapping is given below.

## Tests

Reused validation for the unchanged implementations: submitted head, 770 driver CTests and 40 reference tests passed; retained fixes, 770 driver CTests and 42 reference tests passed. The driver, tests and client built. Direct CPU probes demonstrated the double-free and the non-HPA reduction difference below. The cleanup fix was checked by its regression and ordinary execution, without an AddressSanitizer run.

## Summary

Writing the auxiliary E output and computing gradients fit into the existing epilogue. The important risks are the fallback used for unsupported bias reductions and a change in the precision of long bias-gradient sums. Both need to be distinguished from the newly supported, ordinary E-output cases.

## Actionable items

### Make unsupported bias reductions report an error without freeing twice

[client/src/Reference.cpp:1398](https://github.com/ROCm/rocm-libraries/blob/46ce0b0c3a676b3878f652e4dbf136bdb1f30f9f/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1398) sends unsupported reduction shapes to the slow reference. At [client/src/Reference.cpp:2801](https://github.com/ROCm/rocm-libraries/blob/46ce0b0c3a676b3878f652e4dbf136bdb1f30f9f/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L2801), that slow path frees its workspace and constructs a `runtime_error` without throwing it, then reaches a second free. A 1×1×1 float GEMM with two batches, gradients enabled and bias reduced from D aborts with `double free detected` for either path preference. Driver argument rejection does not exercise this reference fallback.

This is an **inherited memory-management defect**, not a new free introduced by this PR. It is relevant because the new path deliberately relies on this fallback. Fix [66106f99d91](https://github.com/newling/rocm-libraries/commit/66106f99d916da886beecc39e464681596074b6d) gives the workspace automatic ownership, reuses the reduction helper and propagates its error. `BatchedBiasGradientReportsUnsupportedShape` checks A, B and D reduction sources through both preferences, including the diagnostic and unchanged bias.

### Preserve narrow bias-gradient accumulation unless a wider policy is deliberate

At [client/src/Reference.cpp:1642](https://github.com/ROCm/rocm-libraries/blob/46ce0b0c3a676b3878f652e4dbf136bdb1f30f9f/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1642), the fast reduction uses float for non-HPA Half/BFloat16 configurations whose slow reduction accumulates in the narrow type. Here non-HPA means higher-precision accumulation is disabled.

For all-one Half inputs with M=K=1 and N=4097, every D element is 1 on both paths, but the bias gradient is **2048 on slow and 4096 on fast**. Repeated Half additions stop changing at 2048; reducing in float and converting once produces a different answer. This can change the validation target by a factor of two.

The conservative fix [de7815c2e50](https://github.com/newling/rocm-libraries/commit/de7815c2e5066f6b2ff76e589732a3b8a671e402) keeps the affected non-HPA gradient+bias configurations on the slow path. `NonHpaBiasGradientKeepsNarrowAccumulation` covers Half and BFloat16 boundaries. An intentional move to float accumulation is an alternative, but it needs an explicit numerical-policy decision and tests for that result.

## Suggestions

None in this focused review.

## Scope decisions

The cleanup correction retains the existing single-batch reduction limitation and makes rejection safe; it adds no batched reduction support. Since the memory error predates this PR, it can also be fixed in a separate dependency. It remains a real failure until that fix is integrated.

No current common configuration is known to exercise the non-HPA case. The retained guard offers behavior preservation for supported inputs; the existing discussion allows a deliberate wider-sum policy instead. This review does not claim that choice has been settled. Both original numerical probes and their setup are preserved in the [native counterexample source and setup](review_cpu_reference_stack_15259_15278.md#appendix-native-counterexample-source-and-setup).

**Suggestion summary:** [review/pr15277-correctness-20261113](https://github.com/newling/rocm-libraries/tree/review/pr15277-correctness-20261113) contains [66106f99d91](https://github.com/newling/rocm-libraries/commit/66106f99d916da886beecc39e464681596074b6d) for reduction cleanup and [de7815c2e50](https://github.com/newling/rocm-libraries/commit/de7815c2e5066f6b2ff76e589732a3b8a671e402) for the conservative accumulation guard. The author may choose a documented wider-accumulation policy instead of the second commit.
