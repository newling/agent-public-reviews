This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15956](https://github.com/ROCm/rocm-libraries/pull/15956)

**Reviewed head:** [56eb1f717cd6222f46b7e4355ac0d17bce6fe308](https://github.com/ROCm/rocm-libraries/commit/56eb1f717cd6222f46b7e4355ac0d17bce6fe308). **Comparison base:** [1e7247af13fc20cd2ec7c64b996925fa53348996](https://github.com/ROCm/rocm-libraries/commit/1e7247af13fc20cd2ec7c64b996925fa53348996).

**Scope:** Follow-up review of compressed solution ownership, mapping/equality behavior, and unnecessary compatibility state, considering the earlier published review, discussion on the accepted sampler prerequisite #15954, and the author's responses. This review covers the PR's own layer and its interactions with #15955–#15958. The sampler's accepted design is not reopened.

## Tests

The submitted stack at [5a5326702711](https://github.com/ROCm/rocm-libraries/commit/5a5326702711f4375e5a263fa85776015047c0e0) passed 300 focused tests covering representations, compile groups, driver orchestration, and library parsing/serialization. The final combined suggestions at [0d196f6a03ad](https://github.com/newling/rocm-libraries/commit/0d196f6a03ad5bc05736e7343c1fb710e6c09b3b) pass 302 tests with 103 saved-result comparisons. Four checked-in gfx942 Equality inputs, four assembly kernels and 14 helper objects, using two workers, compressed MessagePack and disabled helper caching, produce 11 byte-identical library files between submitted and suggested code. Both builds use the same output path and report zero compact-solution fallback reads in the parent. This is a small correctness comparison, not a performance measurement.

Applicable root pre-commit hooks pass. Flake8 reports the same seven pre-existing diagnostics in the driver on both revisions. Live checks are mixed: the latest normal Multi-Arch summary passes, while Math CI and the policy bot report failures and component coverage/ASAN work remains incomplete. This review does not establish a cause for every CI failure or claim merge readiness.

The added mapping-cache and comparison assertions each fail with their corresponding fix absent and pass with it present. The per-PR suggestion branch also passes 121 compact-solution, compile-group and driver tests. Tests exercise the production naming dispatchers after removing their test-only duplicates.

## Summary

Keeping compressed generator state while the parent works with a small summary directly addresses retained memory. The most useful design boundary is already present: generation, helper construction and library naming explicitly expand a record when they need a full Solution.

The generic Mapping facade extends beyond that boundary. It promises arbitrary field reads, automatic promotion to a full object, iteration, equality with another representation, and synchronization between the summary, overlay and expanded state. Two reproducible inconsistencies below arise in that extra interface. Neither occurred in the small build, which reported zero fallback reads and used homogeneous compact records.

## Actionable items

### Reuse the promoted object for every mapping operation

**Location:** [_fallback](https://github.com/ROCm/rocm-libraries/blob/56eb1f717cd6222f46b7e4355ac0d17bce6fe308/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L219) and [iteration, length and keys](https://github.com/ROCm/rocm-libraries/blob/56eb1f717cd6222f46b7e4355ac0d17bce6fe308/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L254).

`__getitem__` checks `_hydrated`, but `__len__`, `__iter__` and `keys()` call `_fallback` directly. Once the promotion threshold is reached, `_fallback` still decompresses and replaces the full object every time. Ten length queries cause ten decompressions, contrary to the stated bounded-cost purpose of promotion, and a caller holding the previously returned hydrated object stops sharing the cached object.

Commit [2111567eb804](https://github.com/newling/rocm-libraries/commit/2111567eb8042c9a29bacc15567f499c4d7d2608) makes `_fallback` return the existing promoted object first. The existing promotion test now verifies length, iteration, key enumeration, object identity and unchanged fallback count after promotion. It fails on the submitted behavior. This fixes the advertised interface; it is not evidence of a slowdown in the currently observed zero-fallback parent path.

### Make full/compact comparison symmetric

**Location:** [CompactSolution.__eq__](https://github.com/ROCm/rocm-libraries/blob/56eb1f717cd6222f46b7e4355ac0d17bce6fe308/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L288) and [Solution.__eq__](https://github.com/ROCm/rocm-libraries/blob/56eb1f717cd6222f46b7e4355ac0d17bce6fe308/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/Solution.py#L8270).

A compact record accepts a full Solution as equal, but the full Solution rejects the compact type. With the checked-in fixture, `compact == full` is true and `full == compact` is false. Because their hashes agree, `dict.fromkeys([compact, full])` keeps one record while the reversed list keeps two.

Commit [b6070a9d6da3](https://github.com/newling/rocm-libraries/commit/b6070a9d6da367dd2419671c912dda419e93106d) removes the asymmetric cross-type acceptance: compact records compare with compact records, matching the full type's existing refusal to compare across representations. Existing tests now assert symmetry and order-independent deduplication. The production loader compacts all of its records, so this preserves its homogeneous deduplication behavior. Supporting cross-type equality instead would require a coordinated change to the full type, for which no caller was found.

## Suggestions

### Keep only state and helpers with production consumers

**Location:** [the compact attributes](https://github.com/ROCm/rocm-libraries/blob/56eb1f717cd6222f46b7e4355ac0d17bce6fe308/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L87) and [duplicate naming dispatchers](https://github.com/ROCm/rocm-libraries/blob/56eb1f717cd6222f46b7e4355ac0d17bce6fe308/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L343).

The compact `srcName` and `duplicate` attributes have no production consumers. The source filename already resides in the compressed Solution payload; the duplicate flag is introduced, propagated and checked only by this wrapper and its new test. Commit [fd81d609a9a3](https://github.com/newling/rocm-libraries/commit/fd81d609a9a33426be31bf81179b66423ff7ef74) removes both wrapper attributes and their pickle plumbing while checking that expansion retains the original source filename.

Commit [ee4e09d5ccb7](https://github.com/newling/rocm-libraries/commit/ee4e09d5ccb73db3796e6c949cc2f876996fb33d) carries forward the earlier removal of `kernelFileBase` and `kernelDedupeKey` from this module. Only tests used those copies. Their assertions now exercise the driver's actual dispatchers, preserving the comparison against full-solution naming.

### Make expensive expansion an explicit operation

**Location:** [SUMMARY_KEYS](https://github.com/ROCm/rocm-libraries/blob/56eb1f717cd6222f46b7e4355ac0d17bce6fe308/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L37) and [the mapping facade](https://github.com/ROCm/rocm-libraries/blob/56eb1f717cd6222f46b7e4355ac0d17bce6fe308/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L229).

Prefer a parent build record that exposes the required metadata and the existing explicit `hydrate()` operation. Unknown metadata reads can then fail at their call site, while callers needing full state explicitly expand once. That would remove fallback promotion, its threshold, counters and cache synchronization, and prevent an innocuous query from silently retaining a full object beside its compressed copy.

This does not require replacing compression or redesigning the YAML-to-object pipeline. The current generator already expands explicitly at its expensive consumers, and both the reported full build and the local small build show zero parent fallback reads. Those observations support investigating deletion of this compatibility behavior; they do not prove that every supported caller can already omit it. The suggestion branch repairs the promised behavior rather than changing that API policy silently.

## Scope decisions

A worker pipeline that takes YAML through assembly/object generation could avoid retaining full configurations in the parent, but must preserve global solution indexing, duplicate representatives, library placement and post-generation metadata. It remains a broader alternative. Do not make it a prerequisite for this memory representation change.

An isolated #15955-to-#15956 comparison is still missing. Record parent retained memory, total peak, parse/compression time, naming time and total elapsed time on the same workload. Naming currently expands every solution again, so compression size alone does not describe the total cost.

**Suggestion branch:** [review/pr15956-design-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15956-design-20261117), based on the reviewed head, contains [ee4e09d5ccb7](https://github.com/newling/rocm-libraries/commit/ee4e09d5ccb73db3796e6c949cc2f876996fb33d) (production dispatchers), [2111567eb804](https://github.com/newling/rocm-libraries/commit/2111567eb8042c9a29bacc15567f499c4d7d2608) (mapping cache), [b6070a9d6da3](https://github.com/newling/rocm-libraries/commit/b6070a9d6da367dd2419671c912dda419e93106d) (symmetric equality), and [fd81d609a9a3](https://github.com/newling/rocm-libraries/commit/fd81d609a9a33426be31bf81179b66423ff7ef74) (unused attributes). All four are included in combined branch [review/pr15955-stack-design-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15955-stack-design-20261117) at [0d196f6a03ad](https://github.com/newling/rocm-libraries/commit/0d196f6a03ad5bc05736e7343c1fb710e6c09b3b). Explicit-record/pipeline redesign and full-build performance validation were not implemented.
