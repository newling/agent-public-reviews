This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8703

**Commit reviewed:** `663b0e94a578` (`fix(rocjitsu): close GPU concurrency gaps`),
the fifth commit in the PR's five-commit stack.

**Review mode:** follow-up review after reading all existing review bodies,
inline threads, and discussion comments. The findings below are intentionally
independent of the already-raised translation-lifetime, generation-publication,
L1/LDS confinement, L1 raw-line pointer, L2 maintenance-lock, IPC-generation,
atomic-alias, and fast-path/range-test comments.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, not draft, and targets `develop`.

**Normal build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: passed. Timing: 125.96s real, 929.37s user, 45.06s sys.

**Affected cache, memory, and LDS test families:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='GpuMemoryTest.*:GpuMemoryThreadingTest.*:L2CacheTest.*:L2CacheThreadingTest.*:L1VectorCacheTest.*:LdsVectorAccessTest.*'
```

Result: 46/46 passed, 0 failed, 0 skipped, 0 errored. GoogleTest reported
164ms; `time -p` reported 0.18s real, 0.19s user, 0.11s sys.

**Focused TSan build and the workflow's memory-threading gate:**

```bash
cmake -S emulation/rocjitsu -B $TSAN_BUILD_DIR -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_FLAGS_RELWITHDEBINFO='-O2 -g' \
  -DCMAKE_CXX_FLAGS_RELWITHDEBINFO='-O2 -g' \
  -DCMAKE_CXX_FLAGS='-Wno-error=unknown-warning-option -Wno-error=nested-anon-types' \
  -DRJ_ENABLE_TSAN=ON
cmake --build $TSAN_BUILD_DIR --target rocjitsu_tests --parallel 8
time -p $TSAN_BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='SparseMemoryTest.*:SparseMemoryThreadingTest.*:GpuMemoryThreadingTest.*:L2CacheThreadingTest.*'
```

Result: the TSan build passed. The selected gate ran 11 tests: 11 passed,
0 failed, 0 skipped, 0 errored, with no sanitizer report. Timing for the test
run: 0.29s real, 0.34s user, 0.15s sys.

**Release-CI failure comparison:**

GitHub's release job failed five tests:

```text
Cdna4ToCdna3SimulatedDispatchTest.TritonBufferAsyncMatmulDispatchAndRun
Cdna4ToCdna3SimulatedDispatchTest.TritonBufferAsyncMatmulConservativeLivenessDispatchAndRun
Cdna4ToCdna3DbtGuestTest.TritonBufferAsyncMatmulDispatchAndRun
RaceTest.gfx950_scratch_vmcnt
RaceTest.gfx950_scratch_vmcnt_race
```

I reproduced the same five failures locally on the PR head:

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure -j1 \
  -R '^(Cdna4ToCdna3SimulatedDispatchTest\.TritonBufferAsyncMatmulDispatchAndRun|Cdna4ToCdna3SimulatedDispatchTest\.TritonBufferAsyncMatmulConservativeLivenessDispatchAndRun|Cdna4ToCdna3DbtGuestTest\.TritonBufferAsyncMatmulDispatchAndRun|RaceTest\.gfx950_scratch_vmcnt|RaceTest\.gfx950_scratch_vmcnt_race)$'
```

Result: 0/5 passed. Timing: 40.44s real, 38.41s user, 1.46s sys.

I rebuilt the exact merge base, `f08edb8c7cad`, and ran the same selection.
The three buffer-async dispatch tests still timed out there, matching the
existing runner/contention failure class, but both scratch tests passed:
2 passed and 3 failed in 41.70s real. The scratch failures are therefore a PR
regression, while the three buffer-async failures are not attributable to this
change from this comparison.

GDB showed the scratch crash in `GpuMemory::read_mapped()` copying 128 bytes
from address zero. The source was `with_host_ptr()` treating passthrough address
zero as a successful mapping and invoking the callback with a null pointer.
The same helper also treats a present PTE with `host_ptr == nullptr` as a
successful mapping. I temporarily changed the helper to distinguish backed
PTEs, present null-backed PTEs, and true misses, and to reject a null
passthrough page. With that change both scratch tests passed, 2/2, in 0.45s
real. The temporary fix was removed after validation.

**Mapped-memory concurrency counterexample:**

I temporarily added a TSan test with two separate L2 instances writing through
the same VMID and virtual address to one mapped backing page. The normal test
completed, but TSan reported a data race between `GpuMemory::read_mapped()` at
`gpu_memory.h:448` and `GpuMemory::write_mapped()` at `gpu_memory.h:455`.

```bash
time -p $TSAN_BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='L2CacheThreadingReviewProbe.CrossL2OrdinaryWritesShareBackingSafely'
```

Result: the GoogleTest assertion passed, but TSan reported one race and exited
with code 66. Timing: 0.30s real, 0.04s user, 0.03s sys. The temporary test was
removed.

**L2 state/range counterexamples:**

I temporarily added two non-TSan tests:

1. Install a dirty RW line with `writeback_line()`, replace it through the CC
   branch, then call `flush_all()`. The CC write issued one backing write, but
   `flush_all()` issued a second because the dirty bit remained set.
2. Map the same VA in VMID A and VMID B to different backing pages, install a
   dirty VMID-A line, externally update VMID B, call the new VMID-less
   `invalidate_range()`, and finally flush. The range invalidation discarded
   VMID A's dirty line; its backing byte remained `0x00` instead of `0x5a`.

Result: both tests failed with those expected counterexamples. The three-probe
binary ran in 7ms total; the unrelated ordinary non-TSan concurrency probe
passed. All temporary tests were removed.

**Pre-commit and diff hygiene:**

```bash
time -p .venv/bin/pre-commit run --files \
  $(git diff --name-only f08edb8c7cad...HEAD)
git diff --check f08edb8c7cad...HEAD
```

Result: passed. Pre-commit timing: 0.75s real, 0.91s user, 0.19s sys.

**Current CI:** pre-commit, Clang sanitizer, GCC sanitizer, focused TSan,
CodeQL, and visible package checks pass. The release job is red with the five
failures described above.

**Finding priority:** the null/unbacked translation crash and the new
`invalidate_range()` contract are introduced by this PR and are the blocking
items in this review. The mapped-backing data race and
`writeback_line(CC)` dirty-bit inconsistency predate this PR. They remain
important because this layer claims shared-state safety and builds new locking
on top of those contracts, but they can reasonably be handled as explicit
follow-ups if this PR narrows its guarantee and records them.

## Summary

The PR changes three different concurrency boundaries.

First, it turns `GpuMemory` page-table lookup into a generation-keyed,
thread-local PTE cache. VMID-table and page-table generations invalidate cached
pointers, and normal mapped copies now run while the selected page-table shared
lock is held. This closes the prior translation-to-copy lifetime window and
makes remapping wait for active copies.

Second, it changes the XCD-local L2 from partition-confined mutable state into a
thread-safe controller. Ordinary operations take a shared maintenance lock and
one set lock; whole-cache maintenance takes the maintenance lock exclusively.
Atomics invalidate the local L2 line and delegate mapped read-modify-write to
`GpuMemory`, where aliases rendezvous on a lock chosen from resolved backing
identity.

Third, it adds performance-adjacent work: contiguous lane runs are combined
into larger L1 operations, and full-wave contiguous LDS accesses use one bulk
copy. L1 and LDS remain thread-confined rather than internally synchronized.

There is also a pre-existing concurrency gap below the page-table lookup.
Holding a page-table shared lock protects the lifetime of a mapped host pointer,
but it does not serialize accesses to the bytes behind that pointer. Two
XCD-local L2 instances have different maintenance and set locks, and both
mapped reads and writes acquire the page-table lock in shared mode. Ordinary
conflicting GPU accesses can therefore become host-language data races even
though the PR's selected TSan gate passes. This was possible under earlier
multi-XCD execution, so it should not be described as a regression introduced
here; it is a foundation issue exposed by the PR's broader safety claim.

The new L2 maintenance surface also lacks a stable VMID/dirty-data contract.
`invalidate_range()` removes every VMID with the same virtual-line tag and does
not write back dirty data, while `writeback_line()` can still create dirty
entries and is used throughout the tests. Those two contracts compose into
silent data loss for unrelated process mappings.

## Actionable items

### 1. Preserve null/unbacked translation semantics in `with_host_ptr()`

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/gpu_memory.h:422`

`with_host_ptr()` currently invokes the callback and returns `true` for two
cases where the old pointer-returning translation path returned null:

- VMID 0 passthrough at address zero computes a null page pointer;
- a present PTE whose `host_ptr` is null passes a null pointer to the callback.

The new `read_mapped()` / `write_mapped()` callers then perform `memcpy` through
that pointer. Both gfx950 scratch-vmcnt release tests crash in
`read_mapped()` for this reason; they pass on the merge base. GDB showed the
128-byte L2 line fill reading from address zero.

Keep three outcomes distinct:

```text
PTE present with non-null backing -> invoke the scoped callback
PTE present with null backing     -> report unmapped without enabling passthrough
PTE absent                        -> permit non-null passthrough below the ceiling
```

The VMID-0 path likewise needs to reject a null aligned passthrough pointer.
Add direct tests for address-zero passthrough and a present null-backed PTE,
and keep the two scratch-vmcnt release tests in the validation set. A temporary
implementation of this distinction made both failing tests pass locally.

### 2. Give `invalidate_range()` a VMID and dirty-line contract before exposing it

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/l2_cache.h:181`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/l2_cache.cpp:259`

The new API accepts only a virtual address and size, then calls
`invalidate_all_vmids()` for every covered line. The header says it is intended
for host/SDMA writes and deliberately performs no writeback because backing is
already current.

That is not sufficient when VMIDs can map the same VA to different backing
pages. Invalidating after a write for VMID B also discards VMID A's entry at the
same VA. If A's line is dirty, its unrelated data is lost. A temporary test
reproduced exactly that result.

There is also a same-process partial-line version of the problem: if an
external agent updates a few bytes while the L2 owns newer dirty bytes elsewhere
in the same 128-byte line, dropping the whole line loses those other bytes.
"Backing has latest data" must therefore apply to the complete invalidated
lines, not merely the externally written range.

No production caller exists in this PR, so resolve the contract before a later
layer starts using the helper. For process-scoped writes, accept a VMID and
invalidate only that VMID after first publishing any dirty bytes that must
survive. If the intended contract is physical-backing invalidation across
aliases, key the operation by resolved backing identity instead of invalidating
unrelated entries that happen to share a virtual tag. Add dirty-line,
same-VA/different-VMID, and partial-line regressions.

## Suggestions

### 1. Track mapped-backing synchronization as a high-priority foundation follow-up

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/gpu_memory.h:444`

`read_mapped()` and `write_mapped()` keep the page-table shared lock held, which
correctly protects mapping lifetime, but both then perform unsynchronized
`memcpy` on the resolved backing page. Per-L2 set locks cannot protect this
storage because different XCDs use different L2 instances. The page-table lock
also cannot protect it because every reader and writer holds that lock in
shared mode.

A TSan counterexample with two L2s accessing the same `(VMID, VA)` reported a
race between `read_mapped()` and `write_mapped()`. This does not require
different virtual aliases; it is the ordinary case of two XCDs reaching the
same global address. Guest code may intentionally contain such races—the race
detector exists to observe them—but the emulator must not turn them into C++
undefined behavior.

This race appears to predate the PR because separate XCD partitions could
already enter the shared `GpuMemory`. If this PR continues to claim that shared
GPU state is concurrency-safe, addressing it here would match that claim. If
the PR is narrowed to same-L2 synchronization plus page-table lifetime safety,
record it as a blocking prerequisite for the later worker-enablement layer
instead. The eventual fix should add backing-page or backing-line
synchronization shared by ordinary accesses and `atomic_rmw()`, plus a
cross-L2 ordinary-access TSan test.

### 2. Clear the pre-existing dirty bit when `writeback_line(CC)` publishes a line

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/l2_cache.cpp:207`

If the target entry is already dirty, the CC branch writes the replacement data
to backing and sets its coherence label to `SHARED`, but never clears
`tag->dirty`. A later flush writes the already-published line again. A temporary
test observed the backing-write counter increase from one to two after
`flush_all()`.

This behavior predates the PR; the current change mainly adds synchronization
around it. It should therefore not block this layer by itself, but it is a
small, well-defined cleanup that would strengthen the dirty-line assumptions
used by the new maintenance code. Set `tag->dirty = false` after the successful
CC backing write and add the regression from Appendix D.

### 3. Describe the implemented cache model without claiming MOESI

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/l2_cache.h:37`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/mtype.h:27`,
`emulation/rocjitsu/lib/simdojo/include/simdojo/components/cache.h:60`

The comments call CC behavior "MOESI coherence state tracking," but the
controller has no sharer/owner directory or peer state-transition protocol;
`OWNED` is never assigned, and cache behavior does not branch on
`CoherenceState`. Normal L2 writes are also intentionally written through and
labelled `EXCLUSIVE`, while some fallback atomic paths can label a clean
backing-published line `MODIFIED`.

Document these values as local descriptive metadata unless and until a global
protocol uses them. This matters for the concurrency review because a
thread-safe local cache is not the same guarantee as a coherent multi-XCD cache
hierarchy.

### 4. Split the L1/LDS performance changes from the shared-state safety layer

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/l1_vector_cache.cpp:21`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/lds.h:143`

Contiguous lane-run coalescing and the full-wave LDS bulk-copy path are
performance changes to thread-confined state. They have useful focused tests,
but they are not required to establish the page-table and shared-L2 concurrency
contracts. Moving them to the stack's functional-performance layer would make
this PR easier to reason about and reduce the number of semantic changes that
must be disentangled when concurrency tests fail.

### 5. Reconcile the new public helpers with their actual callers

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/l2_cache.h:121`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/l2_cache.h:181`

`writeback_line()` is documented as an L1-eviction interface, but its direct
callers are tests; the live L1 paths use partial write-through `write()`.
`invalidate_range()` likewise has only test callers in this PR despite its
host/SDMA documentation.

Either defer these helpers until their production caller lands or document the
intended supported contract now. Test-only construction of dirty state is
useful, but it should not silently define a public production API whose VMID,
partial-line, and writeback behavior remains unsettled.

## Commentary

The per-set plus maintenance-lock structure is a clear improvement over one
coarse L2 lock, and the current range-lock ordering avoids set-lock deadlocks.
The generation-keyed PTE cache also addresses the earlier stale-pointer
lifetime problem in a reasonably contained way.

The chronology matters when describing the remaining work. Multi-partition
`num_threads > 1` execution predates this stack, so separate XCD-local L2s could
already enter shared `GpuMemory` concurrently. The genuinely new requirement
from the later CU pool is multiple workers entering one L2 instance; mapped
backing synchronization and cross-L2 ordinary access safety are also latent
shared-memory requirements, not merely optional preparation for the later
dispatch layer.

The strongest recommendation is to define the sequential functional cache
contract before adding more concurrency or performance layers. This need not
mean implementing hardware MOESI, nor does every pre-existing inconsistency
need to be repaired in this PR. It does mean stating which backing copy is
authoritative, how VMID-scoped invalidation works, when dirty data may be
dropped, and what synchronization protects mapped bytes. Otherwise later
layers will continue building increasingly sophisticated synchronization on a
foundation whose observable behavior is not yet stable enough to review.

## Appendix A: direct regression for null passthrough

This test is directly related to the PR. It fails by dereferencing a null
passthrough page in the current `with_host_ptr()` implementation.

```cpp
TEST(GpuMemoryTest, ZeroPassthroughAddressUsesFallbackStorage) {
  GpuMemory memory("memory");
  memory.set_passthrough(true);

  std::array<uint8_t, 16> actual{};
  std::array<uint8_t, 16> expected{};
  memory.read_block(/*addr=*/0, std::span<uint8_t>(actual));

  EXPECT_EQ(actual, expected);
}
```

A second direct test should install a present PTE with `host_ptr == nullptr`
before registration, then verify that access falls back rather than enabling
passthrough or invoking a callback with null:

```cpp
TEST(GpuMemoryTest, NullBackedPteDoesNotInvokeMappedCallback) {
  constexpr uint32_t kVmid = 7;
  constexpr uint64_t kVa = 0x400000;

  GpuMemory memory("memory");
  memory.set_passthrough(true);
  KfdProcess process(kVmid);
  process.page_table_[kVa >> KfdProcess::kPageShift] = {
      nullptr, Mtype::RW};
  memory.register_process(kVmid, &process.page_table_,
                          &process.page_table_mutex_,
                          process.page_table_generation());

  memory.write32(kVa, 0x12345678u, kVmid);
  EXPECT_EQ(memory.read32(kVa, kVmid), 0x12345678u);
}
```

## Appendix B: direct regression for VMID-less range invalidation

This test is directly related to the PR because `invalidate_range()` is new.
It demonstrates that invalidating VMID B's virtual range can discard unrelated
dirty data owned by VMID A at the same VA.

```cpp
TEST(L2CacheTest, InvalidateRangeDoesNotDropAnotherVmidsDirtyLine) {
  constexpr uint32_t kVmidA = 7;
  constexpr uint32_t kVmidB = 8;
  constexpr uint64_t kVa = 0x700000;

  GpuMemory memory("memory");
  L2Cache l2("l2");
  l2.set_backing_memory(&memory);
  KfdProcess process_a(kVmidA);
  KfdProcess process_b(kVmidB);
  std::array<uint8_t, GpuMemory::PAGE_SIZE> backing_a{};
  std::array<uint8_t, GpuMemory::PAGE_SIZE> backing_b{};
  process_a.map_pages(kVa, backing_a.data(), backing_a.size());
  process_b.map_pages(kVa, backing_b.data(), backing_b.size());
  memory.register_process(kVmidA, &process_a.page_table_,
                          &process_a.page_table_mutex_,
                          process_a.page_table_generation());
  memory.register_process(kVmidB, &process_b.page_table_,
                          &process_b.page_table_mutex_,
                          process_b.page_table_generation());

  std::array<uint8_t, L2Cache::LINE_SIZE> dirty_a{};
  dirty_a.fill(0x5a);
  l2.writeback_line(kVa, dirty_a.data(), Mtype::RW, kVmidA);

  backing_b[0] = 0xa5;
  l2.invalidate_range(kVa, 1);
  l2.flush_all();

  EXPECT_EQ(backing_a[0], 0x5a);
  EXPECT_EQ(backing_b[0], 0xa5);
}
```

## Appendix C: optional TSan follow-up for mapped backing

This test demonstrates a pre-existing foundation issue rather than a regression
introduced by the PR. It is included for reproducibility, but can live in a
follow-up if this PR narrows its shared-state safety claim.

```cpp
TEST(L2CacheThreadingTest, CrossL2OrdinaryAccessesAreHostRaceFree) {
  constexpr uint32_t kVmid = 7;
  constexpr uint64_t kVa = 0x800000;
  constexpr uint32_t kIterations = 10000;

  GpuMemory memory("memory");
  L2Cache l2a("l2a");
  L2Cache l2b("l2b");
  l2a.set_backing_memory(&memory);
  l2b.set_backing_memory(&memory);
  KfdProcess process(kVmid);
  std::array<uint8_t, GpuMemory::PAGE_SIZE> backing{};
  process.map_pages(kVa, backing.data(), backing.size());
  memory.register_process(kVmid, &process.page_table_,
                          &process.page_table_mutex_,
                          process.page_table_generation());

  std::barrier start(2);
  auto writer = [&](L2Cache &l2, uint32_t value) {
    start.arrive_and_wait();
    for (uint32_t i = 0; i < kIterations; ++i) {
      l2.write(kVa, reinterpret_cast<const uint8_t *>(&value),
               sizeof(value), Mtype::RW, kVmid);
    }
  };

  std::thread first(writer, std::ref(l2a), 0x11111111u);
  std::thread second(writer, std::ref(l2b), 0x22222222u);
  first.join();
  second.join();
}
```

## Appendix D: optional dirty-state follow-up

This test covers a pre-existing inconsistency in `writeback_line(CC)`. It is a
small follow-up rather than a required regression for this PR.

```cpp
TEST(L2CacheTest, CcWritebackClearsExistingDirtyState) {
  constexpr uint64_t kAddr = 0x600000;

  GpuMemory memory("memory");
  L2Cache l2("l2");
  l2.set_backing_memory(&memory);
  std::array<uint8_t, L2Cache::LINE_SIZE> dirty{};
  std::array<uint8_t, L2Cache::LINE_SIZE> coherent{};
  dirty.fill(0x11);
  coherent.fill(0x22);

  l2.writeback_line(kAddr, dirty.data(), Mtype::RW);
  EXPECT_EQ(l2.backing_write_transactions(), 0u);

  l2.writeback_line(kAddr, coherent.data(), Mtype::CC);
  EXPECT_EQ(l2.backing_write_transactions(), 1u);

  l2.flush_all();
  EXPECT_EQ(l2.backing_write_transactions(), 1u);
}
```
