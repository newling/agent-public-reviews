This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8702
**Commit reviewed:** `ad9074409721` (`refactor(simdojo): add concurrent memory`)

**PR metadata:** public PR against public `ROCm/rocm-systems`, base `develop`,
head `ROCm:<pr-head-ref>`.

I followed the split-stack links from the PR description. This is the first
layer of the reduced parallel CPU simulation stack, split out from the larger
functional CU dispatch pool PR. The later linked layers build on this one for
GPU-state concurrency, XCD partitioning, plugin threading policy, and finally
the dispatch pool. The larger-PR notes and prior reviews mostly concerned
scope, plugin policy, TSAN support, and unrelated DBT/sanitizer work; those are
not part of this bottom Simdojo-memory slice.

**Focused build command:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

Result: build passed in 203.69s real time. CMake regenerated the build system,
then rebuilt and linked `rocjitsu_tests`.

**New PR test:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='SparseMemoryThreadingTest.ConcurrentDifferentPageWritesArePreserved'
```

Result: 1/1 passed, 0 failed, 0 skipped, 0 errored. GoogleTest reported 1 ms
test time; `time -p` reported 0.00s real time.

**Diff hygiene:**

```bash
git diff --check origin/develop...HEAD
```

Result: passed with no whitespace errors.

**CI status at review time:** GitHub checks reported `test (release)`,
`test (asan-ubsan)`, `test (asan-ubsan-gcc)`, `pre-commit`,
`therock-pr-bot`, TheRock summary, Linux package builds, and the gfx94X sanity
test passing. Hardware/platform-specific jobs were skipped.

## Summary

This PR makes Simdojo sparse memory more suitable as a shared backing store for
later parallel rocjitsu execution work. `SparseMemory` now stores sparse pages
behind 1024 page stripes instead of one global page map lock, adds page-chunked
`read_block()` and `write_block()` helpers, and routes the scalar read/write
helpers and image loading through those block paths. Host-backed page mappings
remain protected by their own shared mutex, but the lookup is now factored into
the same page-chunked helpers, with an atomic fast path for the common
no-host-pages case.

The PR also adds small cache data-structure helpers needed by later cache
controllers: allocation that returns both tag and data pointers, invalidation
of all VMID aliases for one line address, and a const line-data lookup helper.
The new regression test exercises concurrent sparse writes to different pages
and verifies the preserved page contents afterward.

## Actionable items

None. I did not find a blocking correctness issue in this layer.

## Suggestions

### 1. Add coverage for page-boundary and host-mapped block accesses

**File:** `emulation/rocjitsu/tests/l2_cache_test.cpp:17`

The new test is useful for the page-stripe insertion path, but every
`write_block()` call starts at a page-aligned address and writes exactly one
page. That leaves the new chunking logic in `SparseMemory::read_block()` and
`SparseMemory::write_block()` mostly untested for the cases it explicitly
handles: unaligned ranges that cross from one sparse page to the next,
cross-page scalar accesses now implemented through the block helpers, and
host-mapped/sparse fallback across a page boundary.

Please consider adding focused tests that:

- write a small buffer starting near `PAGE_SIZE - 2`, read it back, verify both
  sparse pages were allocated/updated, and check that cross-page scalar
  `read32()`/`write32()` observe the expected little-endian bytes;
- map one or two host pages, perform a block or scalar access that crosses the
  mapped page boundary, and verify bytes are read from or written to the host
  backing rather than the sparse fallback.

The host-mapped case is especially worth covering because this PR changes the
path shape: old scalar accessors only used a host mapping when the whole scalar
fit inside one mapped page, while the new block helpers handle host mappings one
page chunk at a time.

### 2. Consider mixing high page-number bits in the stripe index

**File:** `emulation/rocjitsu/lib/simdojo/include/simdojo/components/sparse_memory.h:241`

`stripe_index()` multiplies the page number by a large odd constant, then masks
off the low `log2(NUM_PAGE_STRIPES)` bits. With a power-of-two stripe count,
that still depends only on the low page-number bits, so addresses separated by
1024 pages, or 4 MiB with 4 KiB pages, always share a stripe. That is not a
correctness problem, but it may reduce the benefit of striping for aligned GPU
VA regions or allocation patterns that stride by large powers of two.

If the intent is to distribute arbitrary page numbers across stripes, consider
using the high bits of the multiplied value, or another small integer-mixing
step, before applying the stripe mask.

## Commentary

The PR is now scoped the way the earlier large-review feedback asked for: this
layer stays in generic Simdojo data structures plus a focused sparse-memory
regression, without pulling in Rocjitsu dispatch policy, plugin behavior, or
DBT/sanitizer changes. That makes it much easier to reason about independently
from the rest of the parallel CPU simulation stack.

`for_each_page()` now locks and walks all page stripes, but the only visible
production use is checkpoint serialization, which already performs a global
state walk over sparse backing pages. I do not see that as a performance concern
for this PR. Host-mapped pages are not included in that sparse-page iteration,
which appears to be an existing checkpointing boundary rather than a regression
introduced by this change.
