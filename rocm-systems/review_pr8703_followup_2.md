This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8703

**Commit reviewed:** `7b3402ff2016` (`fix(rocjitsu): preserve invalidated
memory state`), the seventh commit in the current stack.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: passed in 198.53s real, 1495.90s user, 65.35s sys.

**Atomic mapping-transition regression:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='GpuMemoryThreadingTest.AtomicRmwKeepsStorageIdentityAcrossConcurrentMap'
```

Result: 0/1 passed in 0.01s real. Two atomic increments should leave the
target at `2`, but the current implementation leaves it at `1`. The test
pauses an unmapped fallback RMW after its read, maps the VA to the same host
storage, completes a mapped RMW under the host-address lock, and then resumes
the fallback RMW under its different lock. The failure reproduced in 20/20
additional runs. The temporary regression passed pre-commit and was removed
after validation.

The current release, Clang-sanitizer, GCC-sanitizer, focused TSan, pre-commit,
CodeQL, and visible package checks pass. Both of these source checks also
passed:

```bash
git diff --check $(git merge-base origin/develop 7b3402ff2016)..7b3402ff2016
git diff --check e8e416a28d58..7b3402ff2016
```

The latest update fixes the two blockers from the previous reviews: null and
null-backed translations no longer reach `memcpy`, and range invalidation is
now VMID-scoped and preserves dirty bytes outside a partial external write.
The unrelated L1/LDS performance work and the temporary design note have also
been removed from this PR.

## Summary

The PR makes page-table translation and one XCD-local L2 safe for concurrent
workers, and moves atomic arbitration into `GpuMemory` so mapped aliases and
different L2 instances rendezvous by resolved backing address.

The remaining blocking issue is in the unmapped atomic fallback. It decides
that an address is unmapped, releases the page-table lock, chooses a fallback
lock, and then calls ordinary read/write helpers that resolve the address
again. A concurrent map can therefore change both the selected storage and
the required atomic lock during one RMW.

## Actionable items

### 1. Keep storage resolution stable for the complete fallback atomic RMW

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/gpu_memory.h:164`

At lines 167-173, `with_host_ptr()` reports that the address is not mapped and
releases the VMID/page-table shared locks. The fallback then selects a lock from
`(client_pid, VA)` or `(GpuMemory, VA)` at lines 175-183, but `read_block()` and
`write_block()` at lines 185 and 187 perform translation again.

If `map_pages()` installs a PTE in that gap, the fallback RMW accesses the new
mapped host page while holding the fallback lock. A second atomic that starts
after the map resolves the same page directly and holds the host-address lock
instead. The two RMWs can therefore operate on the same bytes under different
mutexes. A mapping change between `read_block()` and `write_block()` can also
make the two halves of one RMW use different storage.

Keep the mapped/client/sparse classification stable through the complete
read-modify-write, or detect a changed classification and retry before touching
storage. Add a regression that pauses an atomic after an unmapped lookup,
installs the mapping, and then verifies that concurrent atomics still use one
arbitration identity.

## Suggestions

None beyond the questions already raised in the current inline review.

## Commentary

The remaining ordinary cross-L2 backing-memory concern is already documented
in the previous agent reviews and is not repeated here.

## Appendix: atomic mapping-transition regression

The temporary regression used to validate the actionable item was:

```cpp
TEST(GpuMemoryThreadingTest, AtomicRmwKeepsStorageIdentityAcrossConcurrentMap) {
  amdgpu::GpuMemory memory("memory");
  constexpr uint32_t kVmid = 17;

  void *raw_mapping = mmap(nullptr, KfdProcess::kPageSize, PROT_READ | PROT_WRITE,
                           MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  ASSERT_NE(raw_mapping, MAP_FAILED);
  struct Mapping {
    uint8_t *data;
    ~Mapping() { munmap(data, KfdProcess::kPageSize); }
  } mapping{static_cast<uint8_t *>(raw_mapping)};

  KfdProcess process(kVmid);
  memory.register_process(kVmid, &process.page_table_, &process.page_table_mutex_,
                          process.page_table_generation());
  memory.set_process_client_pid(kVmid, getpid());

  auto atomic_stripe = [](uintptr_t key) {
    key >>= 3;
    key ^= key >> 17;
    key ^= key >> 31;
    return key & (4096 - 1);
  };

  uint32_t *target = nullptr;
  for (size_t offset = 64; offset + sizeof(uint32_t) <= KfdProcess::kPageSize; offset += 8) {
    auto *candidate = reinterpret_cast<uint32_t *>(mapping.data + offset);
    const uintptr_t mapped_key = reinterpret_cast<uintptr_t>(candidate);
    uintptr_t fallback_key = mapped_key ^ (mapped_key >> 32);
    fallback_key ^=
        static_cast<uintptr_t>(getpid()) * static_cast<uintptr_t>(0x9e3779b97f4a7c15ULL);
    if (atomic_stripe(mapped_key) != atomic_stripe(fallback_key)) {
      target = candidate;
      break;
    }
  }
  ASSERT_NE(target, nullptr);
  *target = 0;

  std::barrier first_atomic_has_read(2);
  std::barrier allow_first_atomic_to_write(2);
  std::thread first_atomic([&] {
    memory.atomic_rmw(
        reinterpret_cast<uint64_t>(target), sizeof(*target),
        [&](uint8_t *storage) {
          uint32_t value = 0;
          std::memcpy(&value, storage, sizeof(value));
          ++value;
          std::memcpy(storage, &value, sizeof(value));
          first_atomic_has_read.arrive_and_wait();
          allow_first_atomic_to_write.arrive_and_wait();
        },
        kVmid);
  });

  first_atomic_has_read.arrive_and_wait();

  // A fix may keep the page-table shared lock through the fallback RMW. In
  // that case, finish the first atomic before mapping. The current
  // implementation releases the lock before the callback, allowing the
  // mapping and a differently locked mapped atomic to overtake its write.
  const bool mapping_can_proceed = process.page_table_mutex_.try_lock();
  if (mapping_can_proceed)
    process.page_table_mutex_.unlock();

  if (mapping_can_proceed) {
    process.map_pages(reinterpret_cast<uint64_t>(mapping.data), mapping.data,
                      KfdProcess::kPageSize);
    memory.atomic_rmw(
        reinterpret_cast<uint64_t>(target), sizeof(*target),
        [](uint8_t *storage) {
          uint32_t value = 0;
          std::memcpy(&value, storage, sizeof(value));
          ++value;
          std::memcpy(storage, &value, sizeof(value));
        },
        kVmid);
    allow_first_atomic_to_write.arrive_and_wait();
    first_atomic.join();
  } else {
    allow_first_atomic_to_write.arrive_and_wait();
    first_atomic.join();
    process.map_pages(reinterpret_cast<uint64_t>(mapping.data), mapping.data,
                      KfdProcess::kPageSize);
    memory.atomic_rmw(
        reinterpret_cast<uint64_t>(target), sizeof(*target),
        [](uint8_t *storage) {
          uint32_t value = 0;
          std::memcpy(&value, storage, sizeof(value));
          ++value;
          std::memcpy(storage, &value, sizeof(value));
        },
        kVmid);
  }

  EXPECT_EQ(*target, 2u);
}
```
