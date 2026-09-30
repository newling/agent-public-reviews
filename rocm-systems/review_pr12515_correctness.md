> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#12515](https://github.com/ROCm/rocm-systems/pull/12515)

**Reviewed head:** [`80ae56b791ca`](https://github.com/ROCm/rocm-systems/commit/80ae56b791ca91447306d685eb08b5abadb0870a)

**Scope:** Fresh correctness-only review. Performance is excluded.

**Review branch:** [`review/pr12515-correctness`](https://github.com/newling/rocm-systems/tree/review/pr12515-correctness), based directly on the reviewed head.

| Commit | Review item |
| --- | --- |
| [`89b6612516c6`](https://github.com/newling/rocm-systems/commit/89b6612516c6a0f66cdc3485a7352c86214fccfd) | Serialize shared VM fault reporters, document their contract, and test concurrency, reentry, and exceptions. |

## Tests

Clang 23 Release builds and focused VM, instruction-cache, cache-policy, register, and dispatch tests pass on the submitted head and suggestion branch; the suggestion branch also passes the new callback tests, selected checkpoint/debug-resume tests, and focused ThreadSanitizer checks.

`GpuVmService.FaultReporterSerializesDistinctSnapshotsAndGenerations` fails on the submitted implementation for both routed and unrouted registrations. The standalone mutable-callback reproducer below reports `WARNING: ThreadSanitizer: data race` and exits with status 66 on the submitted head. The same reproducer exits successfully without a sanitizer report on parent [`b51b043dd724`](https://github.com/ROCm/rocm-systems/commit/b51b043dd724c41196ca2e2c0c2eef815a6a92fd) and on the suggestion branch. The new callback tests also pass under ThreadSanitizer after the fix, including nested reporting and callback exceptions.

The restore checks cover lazy SGPRs, accumulator VGPRs, Wave64 state, functional-dispatch configuration, debugger detach/resume, and CWSR restoration. These paths consume the changed register storage, activity counts, or readiness notifications. The full corpus and hardware suites were not rerun locally. The PR's release, ASan/UBSan, TSan, and GCC UBSan CI jobs pass; a separate policy-enforcement check is failed. Changed-file pre-commit hooks pass.

## Summary

VM access snapshots now retain a shared generation object containing the translator, memory backing, and fault reporter. Instruction-fetch snapshots live within a functional quantum. Wave activity and free register counts are maintained alongside lifecycle transitions, and pooled dispatch relies on admission/resume notifications. Vector atomics retain completed-lane progress across retries while sharing a coherence boundary.

The review covered every changed implementation file, its direct tests, and relevant callers. The submitted tests provide useful coverage for root replacement and retirement, overlapping pause reasons, register reuse, and atomic retry results. In particular, preserving the ownership tag when splitting mapped extents prevents a surviving extent from silently changing ownership.

## Actionable items

### Serialize invocations of the shared fault-reporter target

**Location:** [`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/gpu_vm.cpp:36–39`](https://github.com/ROCm/rocm-systems/blob/80ae56b791ca91447306d685eb08b5abadb0870a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/gpu_vm.cpp#L36-L39), with invocation at [lines 341–345](https://github.com/ROCm/rocm-systems/blob/80ae56b791ca91447306d685eb08b5abadb0870a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/gpu_vm.cpp#L341-L345) and in `access_translated`.

Previously, separately captured snapshots copied the fault callable. This change makes snapshots and pinned generations invoke the same callable object. A `const std::function` can still invoke a mutable target, and the shared access lease permits simultaneous readers. Consequently, a reporter with a mutable by-value capture now races when two distinct snapshots report faults concurrently. That is undefined behavior and can corrupt the reporter's state. Neither registration API declares a requirement that the callable synchronize its own internal state. The reproducer uses exactly this API boundary; its only unprotected state is the lambda's internal counter.

Serialize invocation in an object shared with the reporter across all generations. **Implemented in [`89b6612516c6`](https://github.com/newling/rocm-systems/commit/89b6612516c6a0f66cdc3485a7352c86214fccfd).** The commit wraps the callable with a shared recursive mutex, covering both terminal-fault and translated-transfer reporting. It preserves same-thread nested faults and releases the guard when a callback throws. The header documents serialization per registration, the restriction against waiting for another thread to fault through that registration, and the existing need to defer retiring a binding whose access lease is held by the callback's caller.

The committed tests exercise distinct ordinary and pinned snapshots across root replacement, both registration APIs, probe/read/write/malformed-atomic reporting, nested snapshot acquisition and reporting, and cross-thread entry after an exception.

## Suggestions

None within the requested correctness scope.

## Commentary

The paired activity counters retain the distinction between a resident wave and a runnable wave. Keeping the overlapping debugger/runtime-pause tests is useful because clearing only one pause reason must leave the wave stopped. The atomic retry test likewise checks architectural return values and backing updates, which directly establishes that completed lanes are not replayed.

## Standalone race reproducer

Save the following as `fault_reporter_probe.cpp`. It includes the VM implementation directly to build a small executable without the complete simulator test target. The backing is never accessed: zero-length probes report `Malformed` through the fault callback. Each worker owns a distinct snapshot.

```cpp
#include "rocjitsu/vm/amdgpu/gpu_vm.cpp"
#include <barrier>
#include <thread>
using namespace rocjitsu::amdgpu;
class Memory final : public PhysicalMemoryAccess {
  VmAccessOutcome read(VmMemoryDomain, uint64_t, std::span<std::byte>) override {
    return VmAccessOutcome::Faulted;
  }
  VmAccessOutcome write(VmMemoryDomain, uint64_t, std::span<const std::byte>) override {
    return VmAccessOutcome::Faulted;
  }
};
int main() {
  GpuVm vm;
  std::atomic<unsigned> observed{0};
  const auto handle = vm.register_address_space(
      7, std::make_shared<IdentityAddressSpaceTranslator>(), std::make_shared<Memory>(),
      [count = 0u, &observed](uint64_t, VmAccessKind) mutable {
        const auto next = count + 1;
        std::this_thread::yield();
        count = next;
        observed.store(next, std::memory_order_relaxed);
      });
  const auto first = *vm.snapshot(handle);
  const auto second = *vm.snapshot(handle);
  std::barrier start(2);
  auto run = [&](const GpuVmAccess &access) {
    for (unsigned i = 0; i < 128; ++i) {
      start.arrive_and_wait();
      (void)access.probe(0, 0, VmAccessKind::Read);
    }
  };
  std::jthread worker([&] { run(first); });
  run(second);
}
```

Compile and run against the desired checkout, with `$SRC_DIR` naming the repository root and `$BUILD_DIR` an existing build directory:

```sh
clang++ -std=c++20 -O1 -g -pthread -fsanitize=thread \
  -I"$SRC_DIR/emulation/rocjitsu/lib/rocjitsu/src" \
  -I"$SRC_DIR/emulation/rocjitsu/lib/util/include" \
  fault_reporter_probe.cpp -o "$BUILD_DIR/fault-reporter-probe"
"$BUILD_DIR/fault-reporter-probe"
```

## Branch handoff

[`review/pr12515-correctness`](https://github.com/newling/rocm-systems/tree/review/pr12515-correctness) contains one additional commit, [`89b6612516c6`](https://github.com/newling/rocm-systems/commit/89b6612516c6a0f66cdc3485a7352c86214fccfd), implementing the actionable item above. The focused build, tests, ThreadSanitizer checks, and changed-file hooks pass. No finding was left without an implementation. The proposed fix is published on the linked branch. No PR comment or GitHub review was posted.
