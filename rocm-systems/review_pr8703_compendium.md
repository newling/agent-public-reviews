This is a review from an agent with an automatic prompt from the reviewer

# Compendium review: ROCm/rocm-systems#8703

**Commit reviewed:** `3a0f2c45118a` (`fix(rocjitsu): harden L2 atomic
arbitration`), the tenth commit in the current stack.

This review treats the PR as four conceptual changes and reviews each one
independently:

1. Page-table and translation lifetime safety.
2. Local L2 thread safety.
3. Device-wide atomic semantics.
4. External-write cache maintenance.

## Shared validation

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: passed in 135.19s real, 1011.81s user, 50.00s sys.

**Changed GPU-memory and L2 contracts:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='GpuMemoryTest.*:GpuMemoryThreadingTest.*:L2CacheTest.*:L2CacheThreadingTest.*'
```

Result: 38/38 passed, 0 failed, 0 skipped, 0 errored. GoogleTest
reported 163ms; `time -p` reported 0.18s real, 0.17s user, 0.11s sys.

The temporary counterexample in Part 3 failed in 11/11 runs and passed
pre-commit. It was removed after validation.

The current release and both ASan/UBSan CI jobs failed during `apt` package
downloads because Ubuntu mirrors were unreachable; those jobs did not build or
run tests. The focused TSan job passes.

---

# Part 1: Page-table and translation lifetime safety

## Tests

Relevant passing coverage includes:

- VMID unregister and re-register invalidating thread-local translations.
- PTE host-pointer and memory-type mutations invalidating cached entries.
- Reconstructing `GpuMemory` at the same C++ address.
- Readers remaining safe while pages are repeatedly mapped and unmapped.
- Atomic fallback retaining the page-table lock through its complete RMW.
- Null passthrough and present null-backed PTE behavior.

## Summary

Each `KfdProcess` owns a page table mapping GPU virtual pages to host backing
pages. `GpuMemory` registers those page tables by VMID and keeps small
thread-local PTE caches.

The PR now uses two separate mutex-protected versions:

```text
VMID registry generation:
    Did VMID → page-table binding change?

Page-table generation:
    Did a PTE inside that page table change?
```

Mapped reads and writes execute while holding the selected page-table shared
lock. A map, unmap, host-pointer remap, or MTYPE update requires the exclusive
side of the same lock and increments the page-table generation before
publication. This prevents a translated host pointer from being retired while
a worker is copying through it.

The latest update also makes the generation values plain mutex-protected
integers, exposes the process generation read-only, removes the unrelated
page-table bump from VMID unregister, and names the VMID-binding generation
according to its actual role.

## Actionable items

None.

## Suggestions

`register_process()` still allows the page-table generation pointer to be
omitted, silently disabling PTE reuse for that registration. This is safe, but
an explicitly named uncached registration path would make accidental omission
less likely. This is an API clarity issue, not a correctness blocker.

## Commentary

This part now has a coherent ownership and lifetime model:

```text
GpuMemory owns VMID registration lifetime
KfdProcess owns page-table content lifetime
shared locks protect active users
generations validate reusable cached copies
```

I consider this portion ready independently of the remaining cache-coherence
issue in Part 3.

---

# Part 2: Local L2 thread safety

## Tests

Relevant passing coverage includes:

- Concurrent writes to different sets.
- Concurrent accesses to the same set.
- Same-L2 atomic serialization.
- Concurrent `flush_all()` with dirty writers.
- Small multi-set invalidation.
- A 129-line invalidation in the focused TSan gate.

## Summary

Before this PR, ordinary operations on one XCD-local L2 depended on topology
partitioning to ensure that only one host thread entered the cache. The PR
makes the L2 controller internally thread-safe:

```text
ordinary line operation:
    shared maintenance lock → one set mutex

small range maintenance:
    shared maintenance lock → ordered set mutexes

whole-cache or wide-range maintenance:
    exclusive maintenance lock
```

The per-set locks allow independent cache sets to make progress concurrently.
The maintenance lock prevents `flush_all()`, `invalidate_all()`, and broad
range operations from racing with line operations.

The latest update caps the number of simultaneously acquired set mutexes.
Ranges covering more than 64 lines use the exclusive maintenance lock, avoiding
TSan's fixed 128-lock tracking limit.

## Actionable items

None within the state owned by a single L2 instance.

## Suggestions

The hardcoded cache geometry remains a separate modeling concern:

```text
128-byte lines × 2,048 sets × 16 ways = 4 MiB
```

The runtime topology chooses the number and placement of L2 instances, but the
architecture JSON does not configure this geometry. That should be handled as
a separate architecture/configuration improvement rather than expanding this
concurrency PR.

## Commentary

The lock ordering is consistent:

```text
maintenance lock → set lock → backing operation
```

Multi-line requests remain intentionally line-atomic rather than one atomic
snapshot of the entire range. That limitation is documented and reasonable for
the current functional model.

I consider the local-L2 synchronization portion ready.

---

# Part 3: Device-wide atomic semantics

## Tests

The checked-in tests pass for:

- Same-address atomics through one L2.
- Same-address atomics through separate L2 instances.
- Different virtual addresses mapping to the same host pointer.
- Distinct `MAP_SHARED` mappings of one memfd.
- Caller-local dirty writeback followed by atomics through another mapping.
- Unmapped-to-mapped storage transition during an RMW.

The following additional production-path counterexample fails:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='L2CacheReviewProbe.ScalarWritebackDoesNotClobberAtomicAtDisjointAddress'
```

Result: 0/1 passed in 0.02s real. The atomic result was expected to remain `1`
but was restored to `0`. The failure reproduced in 10/10 additional runs.

## Summary

The PR moves atomic RMW to backing storage and now protects it at two levels:

```text
L2 process-wide atomic mutex:
    serializes L2 atomic operations across XCDs and distinct host mappings

GpuMemory backing stripe:
    serializes the final mapped or fallback storage operation
```

The mapping-transition fix keeps VMID registration, page-table identity, and
storage classification stable through fallback RMW. The latest L2 change also
holds one process-wide mutex across caller-local dirty-line publication, the
backing RMW, and local tag cleanup.

This fixes the reported concurrent atomic and host-alias failures. It does not
establish coherence with dirty scalar K$ lines owned by other CUs or XCDs.

## Actionable items

### Prevent scalar K$ writeback from clobbering an atomic in another XCD

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/l1_scalar_cache.cpp:37`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/l2_cache.h:148`

The scalar cache read-allocates a 64-byte line, modifies individual dwords, and
later publishes the complete dirty line through `L2Cache::write()`.
`L2Cache::atomic_rmw()` flushes only the caller's local L2 line and cannot see
a dirty K$ line retained by another CU/XCD.

The counterexample is:

```text
K$ on XCD A reads a line whose dword 0 is 0
K$ stores 0x5a5a5a5a to dword 1, leaving its line dirty
XCD B atomically increments dword 0 from 0 to 1
K$ A writes back its complete stale line
backing dword 0 becomes 0 again
```

The guest accesses target different dwords, so this is not a guest data race.
The new atomic mutex cannot prevent a stale full-line writeback that happens
after the atomic completes.

Establish a coherence boundary before enabling the worker layers. Possible
designs include:

- Functional-mode byte-granular or write-through scalar stores.
- Dirty-byte tracking with merge-on-writeback.
- Device-wide scalar-cache publication/invalidation around atomics.

## Suggestions

The single process-wide L2 atomic mutex is deliberately conservative and
serializes independent atomic addresses. The submitted benchmarks show no
material regression in the sampled workloads, but this should remain visible
as the functional worker count increases.

## Commentary

This appears to be a pre-existing cache-coherence gap, not a regression from
the latest atomic fixes. It is nevertheless the blocking issue in this
compendium because Part 3 claims device-wide atomic arbitration and is a
prerequisite for enabling workers on separate XCDs.

## Regression

```cpp
TEST(L2CacheReviewProbe, ScalarWritebackDoesNotClobberAtomicAtDisjointAddress) {
  amdgpu::GpuMemory memory("memory");
  amdgpu::L2Cache l2a("l2a");
  amdgpu::L2Cache l2b("l2b");
  l2a.set_backing_memory(&memory);
  l2b.set_backing_memory(&memory);
  amdgpu::L1ScalarCache scalar_cache(&l2a);
  scalar_cache.set_memory(&memory);

  constexpr uint32_t kVmid = 17;
  constexpr uint64_t kVa = 0x500000;
  std::array<uint8_t, KfdProcess::kPageSize> backing{};
  KfdProcess process(kVmid);
  process.map_pages(kVa, backing.data(), backing.size());
  memory.register_process(kVmid, &process.page_table_, &process.page_table_mutex_,
                          process.page_table_generation());

  constexpr uint32_t kScalarValue = 0x5a5a5a5a;
  scalar_cache.store(kVa + sizeof(uint32_t), 1, &kScalarValue, kVmid);

  l2b.atomic_rmw(
      kVa, sizeof(uint32_t),
      [](uint8_t *storage, uint32_t offset) {
        uint32_t value = 0;
        std::memcpy(&value, storage + offset, sizeof(value));
        ++value;
        std::memcpy(storage + offset, &value, sizeof(value));
      },
      kVmid);

  scalar_cache.writeback_all(kVmid);

  uint32_t atomic_value = 0;
  uint32_t scalar_value = 0;
  std::memcpy(&atomic_value, backing.data(), sizeof(atomic_value));
  std::memcpy(&scalar_value, backing.data() + sizeof(uint32_t), sizeof(scalar_value));
  EXPECT_EQ(atomic_value, 1u);
  EXPECT_EQ(scalar_value, kScalarValue);
}
```

---

# Part 4: External-write cache maintenance

## Tests

Relevant passing coverage includes:

- Zero-sized invalidation.
- Normal multi-line and multi-set ranges.
- Address-space-end clamping.
- Same virtual address in different VMIDs.
- Partial external writes overlapping dirty lines.
- Wide invalidation covering 129 lines under TSan.

## Summary

`invalidate_range(addr, size, vmid)` models cache maintenance after a host or
SDMA write has completed. Its contract is process-scoped:

```text
bytes inside the range:
    authoritative in backing memory

dirty bytes outside a partially covered line:
    must be preserved

same virtual address in another VMID:
    unrelated and must not be invalidated
```

For a partially covered dirty line, the implementation copies the cached line,
refreshes the externally written subrange from backing memory, writes the
merged line back under its owning VMID, and invalidates the line.

For broad ranges, it now uses exclusive maintenance instead of simultaneously
locking too many sets.

## Actionable items

None.

## Suggestions

There is no production caller of `invalidate_range()` in this PR. When the
host/SDMA integration begins using it, add caller-level tests that establish:

- The external write completes before invalidation.
- The supplied VMID is the owner of the affected virtual range.
- Partial-line authoritative bytes match the range passed to invalidation.

## Commentary

The API deliberately does not find every virtual alias of the same backing
object. Ordinary aliases retain separate cached copies and require an explicit
coherence boundary. That is a broader cache-model contract, not an
`invalidate_range()` implementation bug.

I consider this portion ready as an internal maintenance primitive.

---

# Overall recommendation

Parts 1, 2, and 4 are ready on their own.

Part 3 still has one blocking coherence issue: a stale full-line scalar K$
writeback can erase an atomic result at a different dword. Resolve or explicitly
defer that prerequisite before using this PR as the foundation for concurrent
XCD/CU worker execution.
