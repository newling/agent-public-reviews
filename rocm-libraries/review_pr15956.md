This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15956](https://github.com/ROCm/rocm-libraries/pull/15956)

**Reviewed head:** `de6d67095491a77bbea99799a0b2ec740093cd91`. **Comparison base:** `ce77601f65f3fc6822a5a1165e1eb3112528f954` (#15955).

**Scope:** Independent review of compressed generator configurations, their consumers, and the complexity of the compatibility wrapper. Existing PR reviews, inline threads, and discussion were not used. The [stack review](review_pr15954_stack.md) covers combined behavior and shared alternatives.

## Tests

The submitted combined stack passed 324 focused tests covering representation, naming, deduplication, library parsing/writing, and driver consumers. A four-file gfx942 build produced all 11 output files byte-identical to the baseline and reported zero compact-solution fallback reads in the parent.

After the bounded helper cleanup below, 27 compact-solution and compile-group tests passed on this PR's suggestion branch. The integrated suggestions passed 359 focused tests. No full-architecture memory comparison was reproduced.

## Summary

The parent keeps generator configurations long after parsing, although it needs only a small subset of their state until compilation or naming. This PR replaces each full generator `Solution` with a compressed pickle, a 26-field summary, cached names and keys, and an overlay for parent-side writes. Workers reconstruct the full object for generation. The compressed payload stays in memory.

Compression is a plausible incremental reduction in retained state. Explicit expansion for generation and naming, and removal of the unused `solDict` computation, are useful changes. The larger design question is whether a general `Mapping` facade is worth the additional state and implicit expansion behavior.

## Actionable items

No production-path correctness regression was demonstrated in the examined consumers.

## Suggestions

### Prefer explicit expansion boundaries over implicit promotion

**Location:** [SUMMARY_KEYS](https://github.com/ROCm/rocm-libraries/blob/de6d67095491a77bbea99799a0b2ec740093cd91/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L37), [PROMOTE_AFTER](https://github.com/ROCm/rocm-libraries/blob/de6d67095491a77bbea99799a0b2ec740093cd91/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L80), and [fallback access](https://github.com/ROCm/rocm-libraries/blob/de6d67095491a77bbea99799a0b2ec740093cd91/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L219).

An unlisted field read reconstructs a solution; after four fallback reads the wrapper retains a full copy. Iteration and length queries also enter the fallback path. A new parent consumer can therefore retain both the compressed payload and the expanded object, weakening the memory-saving property without an explicit expansion call.

Compare this with a small parent record containing the required metadata and a named expansion operation. That would make the expensive operation and ownership visible to callers. If the facade is retained, justify its promotion threshold and validate the parent fallback count on representative builds. The local count was zero; this is a design concern, not evidence that the current generation path already promotes all solutions.

### Remove duplicate helpers that only tests exercise

**Location:** [kernelFileBase() and kernelDedupeKey()](https://github.com/ROCm/rocm-libraries/blob/de6d67095491a77bbea99799a0b2ec740093cd91/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L343) and the production [naming dispatchers](https://github.com/ROCm/rocm-libraries/blob/de6d67095491a77bbea99799a0b2ec740093cd91/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L591).

The new module duplicates two dispatchers already used by the build driver. Only tests call the module copies, so those assertions do not exercise the actual dispatchers.

Commit [9eef4dd50a7](https://github.com/newling/rocm-libraries/commit/9eef4dd50a729cabf115edd63a2d3130a6f9a8c7) removes the unused production copies and redirects the existing naming-equivalence assertions to the driver's helpers. It preserves the independent comparison against names computed from full solutions.

### Report the compression step's own cost and benefit

Compare #15955 with this PR using the same workload and sampler. Include parent retained memory, peak memory, elapsed time, and fallback counts. The whole-stack improvement cannot establish this representation's individual contribution or its compression/expansion cost.

## Scope decisions

A bounded worker pipeline from YAML through object generation is a larger alternative worth evaluating. It could keep full generator state out of the parent, but it must coordinate deterministic indices, duplicate representatives, returned codegen metadata, and code-object placement. The [stack review](review_pr15954_stack.md) explains those obligations. No pipeline prototype or replacement representation was implemented.

**Suggestion branch:** [review/pr15956-20261116](https://github.com/newling/rocm-libraries/tree/review/pr15956-20261116) contains the helper-cleanup commit above. The representation-policy decision remains open; the focused tests and small build do not establish equivalence for every architecture or custom-kernel path.
