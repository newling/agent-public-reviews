This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#13623](https://github.com/ROCm/rocm-systems/pull/13623)

**Reviewed head:** `0d399d9e610` on `<pr-head-ref>`, based on `origin/develop` at `6e6db1702450`. The upstream repository, fork, PR and base branch are public.

**Suggestion branch:** [`review/pr13623-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr13623-suggestions), two commits on top of the reviewed head.

| Commit | Item |
| --- | --- |
| [`ea7233bfd86e`](https://github.com/newling/rocm-systems/commit/ea7233bfd86e7a16d9ff5c06d10b82fabf22bb89) | Test lazily backed caches against the eager cache (item 1) |
| [`c9b0b73c6427`](https://github.com/newling/rocm-systems/commit/c9b0b73c6427986b5c781f7aed18410aa1948d10) | Document first-use allocation failure for lazily backed caches (item 2) |

## Tests

Built `rocjitsu_tests` and `cache_allocation_failure_test` with Clang 23 (Release, Ninja, x86-64-v3). The full test binary passes except one environment-dependent case (`EffectiveConfigTest.ReadsNativeLaunchConfigHandoff`, which needs a launcher-provided invocation directory and is excluded from default CTest discovery). The 22 `cache_allocation_failure_test` cases, the cache, L1, policy-cache and GPU-VM service suites, and the new test from item 1 pass on the suggestion branch. The new test also passes under ASan and UBSan with assertions enabled.

- **Differential check:** a throwaway version of item 1's test drove 300 random operation sequences through an eager and a lazy cache. Observable results matched in every sequence. Making the lazy gate stop skipping untouched sets makes the committed test abort on a failed storage assertion.
- **Race-detector integration cases:** 62 of 63 gfx950 and 21 of 21 gfx1151 HIP race cases from the corpus pass against this PR's build. `global_to_lds_buffer_race` fails with "expected at least one race, got none"; it fails identically on a build of an unmodified earlier develop commit, so it is not caused by this change, and it is the buffer-to-LDS case that needs a newer corpus revision.
- **CI:** the PR's check list contains the handbook job but no rocjitsu test job, so the local runs above are the rocjitsu test evidence for this head.
- **Not measured:** the performance and memory numbers in the description were not reproduced. A standalone microbenchmark of hit lookups on an eager and a lazy cache measured the same cost (about 4.5 ns each).

## Summary

The PR defers two per-CU allocations until first use. The L1 scalar and vector caches opt into a new `LazyStorage` mode of `simdojo::Cache`, in which the tag and byte stores are null until the first `allocate_with_data()`. Every query path first checks the existing per-set `touched_sets_` marker and reports a miss for a set that has never been allocated, so no query touches the unallocated storage. The marker is set only after both stores exist, and the first-use allocation runs before any tag becomes valid, so a failed allocation leaves the cache empty and retryable. Copy assignment for the lazy mode builds the replacement first and then moves it in, so a failed copy leaves the destination unchanged. `VmMtypeCache` likewise holds its 64 policy snapshots behind a pointer that is created on the first query. Its copy and move operations preserve value semantics, `clear()` replaces the former `= {}` reset, and the new table is created before the cache publishes its generation.

Shared caches (the L2 and the memory-side cache) keep the eager default, and the PR states why: their separate per-set locks do not serialize a first allocation. I checked every public `Cache` operation for an ungated storage access and found none. Every L1 caller of the `read_line`, `write_line`, `fill_line` and `fill_missing_bytes` operations reaches them only for a resident line, so the new "called on a miss" assertions on untouched sets cannot fire for existing callers; eager caches already assert in the same situation.

## Actionable items

### 1. Test lazily backed caches against the eager cache

`simdojo_sim_test.cpp`, end of file. The PR's new tests cover allocation failure, copies and a few residency cases. They do not drive the lazy cache through the untouched-set gating of each public operation (`lookup`, `peek`, `invalidate`, `invalidate_all_vmids`, `invalidate_all`, `read_line`, `write_line`, `line_data_for_*`, `for_each_dirty`) in combination with eviction, full invalidation, copies and moves. A missed gate would read null storage, which the storage assertion catches only in builds with assertions. Commit [`ea7233bfd86e`](https://github.com/newling/rocm-systems/commit/ea7233bfd86e7a16d9ff5c06d10b82fabf22bb89) adds `CacheLazyStorageTest.RandomOperationsMatchEagerCache`: 100 seeds of 300 random operations run against an eager and a lazy cache of the same geometry, requiring identical hits, evictions, line bytes and dirty lines. It runs in tens of milliseconds.

### 2. Document the first-use allocation contract

`cache.h`, `allocate_with_data()`, and the `LazyStorage` template parameter documentation. With `LazyStorage`, `allocate_with_data()` (and so `allocate()`) can now run the new handler or throw `std::bad_alloc` on the first allocation of a cache, where an eager cache did so at construction. The behavior is correct and tested, and the comment on `materialize()` explains the ordering, but the public documentation says only that backing is deferred. Callers of the L1 fill paths, which run inside CU execution, need to know that the first fill can throw and that the cache stays empty and usable afterwards. Commit [`c9b0b73c6427`](https://github.com/newling/rocm-systems/commit/c9b0b73c6427986b5c781f7aed18410aa1948d10) documents this on `allocate_with_data()`.

## Suggestions

### State the exclusivity requirement where the lazy mode is used

`l1_scalar_cache.h:33` and `l1_vector_cache.h:32`, and `cache.h` at the `LazyStorage` parameter. First-use allocation writes a plain pointer, so a lazy cache requires exclusive access for its first allocation. The template comment says so. As far as I traced, the L1 caches are used only from the owning CU's step or from maintenance paths that run while CU workers have rejoined or under the wave-state lock, so the requirement appears to hold today. A short note beside the `CacheStore` alias in each L1 header would keep a future caller that touches an L1 from another thread from silently relying on the eager behavior.

### Explain the single-thread Tensile result

The description reports a 7.0% slower median for the gfx1250 single-thread Tensile smoke test over seven pairs. The added gate on hit lookups is not the likely cause; a hit-lookup microbenchmark of an eager and a lazy cache showed no difference. Whole-process instruction and cycle counts for that case, on the head and its base, would show whether the difference is noise or a real cost such as repeated allocation after a VM rebind.

## Commentary

- The two deferrals are independent and each is small. The policy-cache change keeps the former invariant that a generation change drops every old mutation token, and reuses the existing table instead of reallocating it.
- Copy assignment of a lazy cache always allocates a fresh replacement, so it does not reuse existing backing as the eager cache does. That is the price of the strong failure guarantee and does not matter unless a lazy cache is copy-assigned on a hot path, which nothing does today.
- The gain is at process startup and in resident memory. The description says no warm-kernel gain is established, and the review agrees with that framing.
