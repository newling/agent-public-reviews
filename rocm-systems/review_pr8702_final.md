This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8702
**Commit reviewed:** `ad9074409721` (`refactor(simdojo): add concurrent memory`)

**PR metadata:** public PR against public `ROCm/rocm-systems`, base `develop`,
head `ROCm:<pr-head-ref>`.

This is a final follow-up review after reading later review discussion and after
creating a reference POC in #8726.

**Original focused build command for #8702:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

Result: build passed in 203.69s real time.

**Original new PR test for #8702:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='SparseMemoryThreadingTest.ConcurrentDifferentPageWritesArePreserved'
```

Result: 1/1 passed, 0 failed, 0 skipped, 0 errored. GoogleTest reported 1 ms
test time; `time -p` reported 0.00s real time.

**Original diff hygiene for #8702:**

```bash
git diff --check origin/develop...HEAD
```

Result: passed with no whitespace errors.

**Additional reference POC validation:** I created draft POC #8726 to test
whether `SparseMemory::host_page_map_` can be removed and VMID-aware host-range
lookup can live in `GpuMemory` instead. That POC built `rocjitsu_tests`, passed
29 focused `GpuMemory`, checkpoint, L1/L2 cache tests, passed 19 focused
dispatch/vector-add tests, and passed `git diff --check`. This validation is
not a substitute for fixing #8702, but it informs the host-map recommendation
below.

**CI status at final review time:** GitHub checks for #8702 reported release,
ASAN/UBSAN, GCC ASAN/UBSAN, pre-commit, package builds, policy checks, and the
TheRock summary passing. Hardware/platform-specific jobs were skipped.

## Summary

This PR adds bottom-layer concurrency primitives to Simdojo. `SparseMemory`
changes from one global sparse-page map protected by one lock to 1024 page
stripes, each with its own map and lock. It also adds public `read_block()` and
`write_block()` helpers and routes scalar reads/writes plus image loading
through page-chunked paths.

The PR also adds small generic cache helpers:
`allocate_with_data()`, `invalidate_all_vmids()`, and `line_data_for_read()`.
The only new test is a multithreaded sparse-memory test where eight threads
write disjoint page-aligned pages and the test checks that all pages were
preserved.

After the later review discussion, I no longer think "no actionable items" is
the right conclusion. The diff is small, but it introduces shared low-level
primitives and leaves several important contracts either undocumented or
untested.

## Actionable items

### 1. Document or implement the atomicity contract for multi-page block operations

**File:** `emulation/rocjitsu/lib/simdojo/include/simdojo/components/sparse_memory.h:85`

`read_block()` and `write_block()` process a request one page chunk at a time.
Each sparse chunk independently acquires and releases one stripe lock through
`read_sparse_chunk()` or `write_sparse_chunk()`. That means a multi-page
`write_block()` is not atomic as one block: two overlapping multi-page writes
can interleave page by page and leave memory containing a mix of both writes.

That may be the correct contract. Sparse memory probably only needs
thread-safe, per-page protected access, not block-level transaction semantics.
But this is a new shared primitive intended to support later parallel execution,
so the contract needs to be explicit.

Please either document the contract on `read_block()` / `write_block()` as
per-page atomic only, or change the implementation to acquire all relevant
stripe locks in a stable order before touching the block if callers require
whole-block atomicity. If the contract is per-page only, add a test that makes
the expected multi-page behavior clear.

### 2. Resolve the `SparseMemory` host-page map direction before adding the fast path

**File:** `emulation/rocjitsu/lib/simdojo/include/simdojo/components/sparse_memory.h:190`

This PR adds `host_pages_mapped_` as an empty-map fast path for the existing
VMID-less `SparseMemory::host_page_map_`, but current tree usage raises a larger
question: I do not see live callers of `SparseMemory::map_host_pages()` outside
`SparseMemory` itself. Current KFD/HIP mappings appear to go through
`KfdProcess::page_table_` and `GpuMemory::translate()`.

Please decide whether `SparseMemory::host_page_map_` is still a supported
Simdojo feature. If it is needed for this stack or for intended generic Simdojo
users, keep it but add direct host-map tests and remove the early
`host_pages_mapped_.store(true)` before the map is populated. If it is legacy,
prefer deleting the host-map path instead of optimizing it; reference POC #8726
shows this appears mechanically viable inside the current tree.

### 3. Bring test coverage in line with the PR's new primitives

**File:** `emulation/rocjitsu/tests/l2_cache_test.cpp:17`

The new test covers only disjoint, page-aligned sparse writes. That is a useful
smoke test, but it does not cover the more important behavior boundaries added
by this PR:

- unaligned `read_block()` / `write_block()` crossing a page boundary;
- overlapping multi-page block operations and their documented atomicity
  contract;
- same-page concurrent access, which is the actual stripe-contention case;
- host-mapped access if `SparseMemory::host_page_map_` remains supported;
- the new `cache.h` helpers: `allocate_with_data()`, `invalidate_all_vmids()`,
  and `line_data_for_read()`.

Please add focused tests for these behaviors, or remove/defer helpers that are
only needed by later layers and test them where they are first used. Also rename
`l2_cache_test.cpp` if it continues to contain only `SparseMemory` coverage.

## Suggestions

### 1. Prefer `std::span` for the new block API

**File:** `emulation/rocjitsu/lib/simdojo/include/simdojo/components/sparse_memory.h:85`

`GpuMemory` already exposes span-based block methods. The new
`SparseMemory::read_block(uint64_t, uint8_t *, size_t)` and
`write_block(uint64_t, const uint8_t *, size_t)` signatures are usable, but they
diverge from the derived API and make same-name overload hiding easier to miss.
Consider span-based overloads for consistency and safer call sites.

### 2. Revisit the stripe hash

**File:** `emulation/rocjitsu/lib/simdojo/include/simdojo/components/sparse_memory.h:241`

The stripe index multiplies the page number by a large odd constant and then
masks the low bits. With 1024 stripes, this still depends only on the low 10
page-number bits, so pages separated by 1024 pages land in the same stripe. This
is not a correctness issue, but it may reduce the practical value of striping
for large power-of-two strides. If distribution matters, mix high bits before
masking or use the high bits of the multiplicative hash.

## Commentary

The PR is correctly scoped as a bottom layer of the parallel CPU simulation
stack, but it should not land as-is unless the contracts are tightened. The
strongest issue is not that the current code obviously corrupts memory; it is
that the PR creates shared low-level primitives whose atomicity, host-map
ownership, and coverage story are unclear.

The later review comments were right to treat those as higher priority than my
initial review did. In particular, "thread-safe" is not a complete contract for
`read_block()` / `write_block()`; the review needs to say what is safe with
respect to overlapping operations and at what granularity.
