> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#12515](https://github.com/ROCm/rocm-systems/pull/12515)

**Reviewed head:** `80ae56b791ca91447306d685eb08b5abadb0870a`

**Local suggestion branch:** `review/pr12515-suggestions`, based on that exact head.

| Local commit | Review item |
| --- | --- |
| `ef9c4b23f4db56c88478c14deff538d996e7b912` | Item 1: reuse pinned VM generations |
| `86272b51462c540c8896518557bef8dc3da7390a` | Item 2: document and test shared fault-reporter concurrency |

The callback documentation and test can be evaluated independently of the pinned-state optimization. The commits are local and have not been published.

## Tests

Clang 23 Release builds and focused VM, cache, scheduling, and register tests passed on the submitted head and suggestion branch; focused VM generation/callback probes passed under ASan/UBSan on both and TSan on the suggestion branch, and changed-file pre-commit hooks passed.

The standalone sanitizer probes compile the VM implementation with the relevant fixture and tests from `gpu_vm_service_test.cpp`. Their initial build with `-fuse-ld=lld` failed because the bundled linker could not load `libicui18n.so.70`; removing that linker override resolved the local setup error. The completed probes reported no sanitizer failures.

The PR's release, ASan/UBSan, GCC UBSan, and TSan corpus jobs and the latest multi-architecture summary are green. The remaining failed check is the policy bot's “Enforce policy” step. The larger corpus runs were left to CI. Application throughput was not measured; the timings below measure the cost of VM operations.

## Summary

The change reduces ownership updates and repeated scans in the functional executor. VM snapshots share one immutable backing generation, instruction-fetch snapshots live for a quantum, and maintained wave/register counts replace repeated occupancy scans. Queue service snapshots have a different lifetime: they remain usable across root replacement so a partially committed transaction can finish on its original backing.

Several boundaries are handled carefully. The MTYPE cache retains copied policy and a weak generation identity, translators without mutation tokens continue to refresh their policy, and nested instruction callbacks cannot replace the snapshot borrowed by their caller. The atomic batch keeps completed lane effects and return values across retries while preparing cache coherence once per attempt. The focused functional checks found these paths consistent with their intended behavior, and the ordinary snapshot path shows a measurable reduction in local API cost.

## Actionable items

### 1. Avoid a new access generation for every pinned snapshot

**Locations:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/gpu_vm.cpp:1009–1027`, with the queue service caller at `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:4385–4390`.

`snapshot_pinned()` still takes the registry mutex exclusively and allocates a new `GpuVmAccessState` for every call. This PR changes both locks to `DistributedSharedMutex`: the registry write lock now acquires all 128 shards, and each allocated access state contains another 128-shard mutex. On the tested non-TSan build, the state grows from 64 to 8,320 bytes. This is on a recurring execution path: `fetch_from_queue()` takes a pinned snapshot before reading the queue indices, including service attempts that discover an empty queue.

A focused comparison against the PR's parent shows the cost moving in opposite directions for the two snapshot APIs:

| Operation | Parent `b51b043dd724` | Submitted head | Suggestion `ef9c4b23f4` |
| --- | ---: | ---: | ---: |
| Ordinary snapshot | 47 ns | 21 ns | 21 ns |
| Pinned snapshot | 65 ns | 1,888 ns | 22 ns |

These are medians of seven process runs, each taking 100,000 snapshots of one existing binding, compiled with Clang 23 at `-O3`, with one CPU selected and revision order rotated. Each process first creates and joins a thread to exercise the multithreaded reference counting path used by the emulator. The repeated pinned call is about 29 times more expensive in the submitted code. The appendix preserves the exact probe; it performs no backing I/O or kernel execution.

**Change:** share the pinned access state for all operations admitted under the same translation epoch. Repeated calls can then take a shared registry lock and retain that state. Release the cached reference on root replacement, leaving outstanding operations to retain the old backing, and continue revoking every surviving pinned generation on invalidation or teardown. Each returned snapshot must still capture current binding metadata under the registry lock.

**Implemented in `ef9c4b23f4db56c88478c14deff538d996e7b912`.** The commit adds a recheck under the exclusive lock before creating the shared pinned state and a regression test showing that replaced backing survives until the last old operation releases it, then expires while the replacement remains usable. Existing concurrent replacement and revocation tests also pass. Root publication and explicit invalidation retain their sharded writer cost; the timing improvement above applies to repeated pinned snapshots within a generation.

### 2. Document concurrent invocation of the shared fault reporter

**Locations:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/gpu_vm.h:559–577` and `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/gpu_vm.cpp:24–39`.

The fault reporter changes from a callable copied into each snapshot to one callable shared by ordinary snapshots, pinned snapshots, and replacement generations. Access leases are shared, so faults from two CUs can invoke that same target concurrently. A `shared_ptr<const std::function<...>>` does not make the callable's mutable state thread-safe: a mutable lambda can still change a value capture through `std::function::operator() const`.

The registration APIs describe backing ownership and cache compatibility but leave this new caller obligation undocumented. A frontend that keeps an unsynchronized counter or scratch state inside its callback can therefore acquire a data race after this change. This is an API contract issue; the review did not establish a race in the current KFD reporter.

**Change:** document that all snapshots and root generations share the callback target and that its provider must synchronize mutable target/captured state. Cover overlapping callbacks from an old pinned generation and the current generation using mutable state protected by the caller.

**Implemented in `86272b51462c540c8896518557bef8dc3da7390a`.** The added test lets both callbacks enter before updating a counter stored in the callback target, confirming the shared callable behavior without an unsynchronized access. It passes on the submitted implementation under ASan/UBSan and on the suggestion branch under ASan/UBSan and TSan.

## Suggestions

No additional suggestions.

## Commentary

Keeping resident and runnable wave counts distinct preserves the behavior needed by overlapping debugger/runtime pause reasons: a paused wave occupies a slot while allowing the execution driver to quiesce. The packed atomic update and the tests covering repeated pause assignments, failed allocation, sparse restored slots, and reuse are useful safeguards for this optimization.

The vector atomic boundary also has a sensible scope. It excludes the device cache hierarchy for the attempt while each backing mutation retains its own atomicity relative to host accesses. The checks for another domain or a moved boundary protect the new overload's ownership requirement, and the retry cursor avoids replaying already committed lanes.

## Appendix: snapshot cost probe

Use a checkout of the reviewed head for `$SRC_DIR`, an out-of-tree directory for `$BUILD_DIR`, and Clang 23 for the comparison. The probe includes `gpu_vm.cpp` so it can also report the size of the private generation type. Its snapshot loop is identical for the compared revisions.

```cpp
#include "rocjitsu/vm/amdgpu/gpu_vm.cpp"

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <string_view>
#include <thread>

using namespace rocjitsu::amdgpu;

class Backing final : public AddressSpaceTranslator, public PhysicalMemoryAccess {
public:
  VmTranslationResult translate(uint64_t address, std::size_t, VmAccessKind) const override {
    return {.outcome = VmAccessOutcome::Complete,
            .translation = {.domain = VmMemoryDomain::Local,
                            .address = address,
                            .contiguous_bytes = 4096}};
  }
  VmAccessOutcome read(VmMemoryDomain, uint64_t, std::span<std::byte>) override {
    return VmAccessOutcome::Complete;
  }
  VmAccessOutcome write(VmMemoryDomain, uint64_t, std::span<const std::byte>) override {
    return VmAccessOutcome::Complete;
  }
};

int main(int argc, char **argv) {
  // Exercise the same shared_ptr reference-counting path as an emulator that
  // has created workers or its doorbell monitor, even for this one-thread probe.
  std::thread([] {}).join();
  const std::string_view mode = argc > 1 ? argv[1] : "snapshot";
  constexpr unsigned iterations = 100000;
  GpuVm vm;
  auto backing = std::make_shared<Backing>();
  const auto handle = vm.register_translated(7, backing, backing);
  uint64_t checksum = 0;
  const auto start = std::chrono::steady_clock::now();
  for (unsigned i = 0; i < iterations; ++i) {
    if (mode == "invalidate") {
      checksum += vm.invalidate(handle);
    } else {
      auto access = mode == "pinned" ? vm.snapshot_pinned(handle) : vm.snapshot(handle);
      asm volatile("" : : "g"(&access) : "memory");
      checksum += access->info().translation_epoch;
    }
  }
  const auto elapsed = std::chrono::duration<double, std::nano>(
      std::chrono::steady_clock::now() - start).count();
  std::cout << mode << " ns/op=" << elapsed / iterations
            << " state_bytes=" << sizeof(GpuVmAccessState)
            << " vm_bytes=" << sizeof(GpuVm) << " checksum=" << checksum << '\n';
}
```

Save the source as `vm_snapshot_bench.cpp`, then build the two public revisions:

```bash
for revision in b51b043dd724c41196ca2e2c0c2eef815a6a92fd 80ae56b791ca91447306d685eb08b5abadb0870a; do
  mkdir -p "$BUILD_DIR/$revision/rocjitsu/vm/amdgpu"
  for extension in h cpp; do
    git -C "$SRC_DIR" show "$revision:emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/gpu_vm.$extension" > "$BUILD_DIR/$revision/rocjitsu/vm/amdgpu/gpu_vm.$extension"
  done
  clang++ -std=c++20 -O3 -DNDEBUG -pthread \
    -I"$BUILD_DIR/$revision" \
    -I"$SRC_DIR/emulation/rocjitsu/lib/rocjitsu/src" \
    -I"$SRC_DIR/emulation/rocjitsu/lib/util/include" \
    vm_snapshot_bench.cpp -o "$BUILD_DIR/bench-$revision"
done
```

Run `taskset -c "$CPU" "$BUILD_DIR/bench-$revision" snapshot` and `taskset -c "$CPU" "$BUILD_DIR/bench-$revision" pinned` with an allowed CPU. Rotate revision order and take the median of seven runs. The suggestion column uses the same source and flags against the local suggestion commit.

## Local handoff

`review/pr12515-suggestions` contains `ef9c4b23f4` for item 1 and `86272b5146` for item 2. Both items are implemented and validated by the focused Release checks, VM sanitizer probes, and pre-commit hooks described above. The branch remains local. Full corpus execution was left to green CI, and application performance remains unmeasured.
