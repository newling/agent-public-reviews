> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8583

**Commit reviewed:** `b9b71492f848973a0ffb281ba2166e9a0dd88cbf` (`fix(rocjitsu): Harden SimulatedKfd concurrency for daemon mode`)

**Public/repo status:** the repository and PR are public. The PR is open, not draft, and targets `develop`.

**Build command:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 \
  --target rocjitsu_tests daemon_test rocjitsu_bin rocjitsu_shared
```

Result: passed. The build reran CMake, rebuilt the changed rocjitsu KMD code,
linked `librocjitsu.so`, `rocjitsu`, `rocjitsu_tests`, and `daemon_test`, and
completed in 131.47s real time.

**Focused CTest command:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R 'SimulatedKfdTest|KfdIoctlTest|DaemonTest\.(HipVectorAdd|HipMemcpy|TwoIndependentClients|InterposerDup)|InterposerDupTest' \
  --output-on-failure --timeout 120
```

Result: passed. CTest selected 28 tests: 28 passed, 0 failed, 0 skipped,
0 errored. CTest reported 13.85s real time.

**Whitespace check:**

```bash
git diff --check origin/develop...HEAD
```

Result: passed with no whitespace errors.

**CI status at review time:** `pre-commit`, `test (asan-ubsan)`, the HIP NVIDIA
summary, setup, and labeler checks were passing. `test (release)`,
`test (asan-ubsan-gcc)`, and the TheRock package builds were still pending.
`therock-pr-bot` was failing because source files changed without any test file
changed:

```text
Source/code files changed without an accompanying unit test.
Expected: add at least one test file named like `test_<name>.py` /
`test_<name>.cpp` (or `<name>_test.*`).
```

## Summary

This PR hardens the daemon-mode `SimulatedKfd` process model. The main design is
a new per-process `op_mutex_` around most KFD ioctls, with `WAIT_EVENTS`
excluded so waits do not block the `SET_EVENT` / `RESET_EVENT` operations that
must wake them. The PR also documents the intended lock order, moves command
processor callback initialization under `process_mutex_`, avoids holding
`alloc_mutex_` across `CommandProcessor::register_queue()`, protects doorbell
state with `alloc_mutex_`, protects scratch/trap writes against the scratch
resolver, and moves imported-dmabuf bookkeeping under `alloc_mutex_`.

The direction matches the earlier interposer concurrency hardening: make fd and
process state transitions explicit, avoid ABBA lock inversions with command
processor callbacks, and keep daemon-client process state consistent when ROCR
uses multiple host threads or multiple client connections.

## Actionable Items

### 1. Prevent already-snapshotted operations from running after final close teardown

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/kmd/linux/simulated_kfd.cpp:455`

The new `close()` comment says taking `proc.op_mutex_` prevents teardown from
overlapping an active ioctl, but the actual sequencing still allows a
pre-snapshotted operation to run after teardown.

`ioctl()` first obtains a `std::shared_ptr<KfdProcess>` from `find_process()` and
only later enters `dispatch_ioctl()`, where non-wait ioctls take `op_mutex_`
(`simulated_kfd.cpp:568`). If a thread snapshots the process and is preempted
before taking `op_mutex_`, a concurrent last `close()` can erase the process
from `processes_`, acquire `op_mutex_`, clear allocations, unregister queues,
close fds, and release the mutex. The pre-snapshotted ioctl can then acquire
`op_mutex_` and run against a `KfdProcess` that has already been torn down.

The same pattern applies to other entry points that snapshot the shared process
before dispatching, such as `mmap()`, `munmap()`, and `get_mmap_memfd()`. Erasing
the process table blocks new lookups, but it does not block operations that
already hold a shared pointer.

Add an explicit per-process closing state, set it while holding the appropriate
process operation lock before teardown becomes visible, and make all dispatch
entry points reject work after that state is set. Alternatively, restructure the
operation accounting so close waits for both the currently running operation and
any already-snapshotted-but-not-yet-dispatched operation before it clears
allocations, unregisters VMIDs, unregisters queues, or closes backing fds.

### 2. Do not use a doorbell memfd after dropping the lock that protects it

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/kmd/linux/simulated_kfd.cpp:705`

The doorbell `dispatch_mmap()` path finds `alloc.memfd` under
`proc.alloc_mutex_`, stores it in `doorbell_fd`, drops the mutex, and then calls
`fstat()`, `ftruncate()`, and `safe_mmap()` on that raw fd. `mmap()` is not
serialized by `op_mutex_`, while `FREE_MEMORY_OF_GPU` and final `close()` both
take `alloc_mutex_` and can close allocation memfds. That means a concurrent
free/close can close `doorbell_fd` after line 714 and before the later fd
operations. In the best case the mmap fails with `EBADF`; in the worse case the
fd number has already been reused and rocjitsu maps or truncates an unrelated
file descriptor.

Take a caller-owned duplicate of the doorbell memfd while still holding
`alloc_mutex_`, use the duplicate for `fstat()` / `ftruncate()` / `safe_mmap()`,
and close the duplicate before returning. This is the same lifetime pattern the
related interposer hardening needed for memfd lookups: once an fd escapes the
lock that protects the stored descriptor, the caller should own an independent
reference.

### 3. Add focused regression tests for the new concurrency contract

**File:** `emulation/rocjitsu/tests/simulated_kfd_test.cpp:66`

The PR changes several synchronization contracts but does not change any test
file, and the live policy bot is blocking the PR for that reason. The existing
focused tests passed locally, but they do not exercise the new close-versus-
already-snapshotted-operation race or the doorbell memfd lifetime race described
above.

Add focused tests that force these interleavings. One useful unit-level shape is
a `SimulatedKfd` test that holds or delays an operation after it has found the
process but before it takes the operation lock, then performs the final close and
verifies the delayed operation is rejected rather than mutating torn-down state.
For the fd lifetime issue, a test should drive doorbell mmap/free or mmap/close
contention and verify the mmap path either owns a duplicated descriptor or
returns a controlled failure without touching a reused fd.

## Suggestions

### 1. Align the PR title with the class being changed

**Location:** PR metadata

The commit title says `SimulatedKfd`, while the live PR title says
`SimulatedDriver`. Consider using `SimulatedKfd` in the PR title as well, since
that is the class and file-level surface this patch changes.

## Commentary

The lock-order cleanup around `create_queue_ioctl()` is a real improvement. The
old `alloc_mutex_`-while-registering shape was exactly the kind of ABBA risk that
daemon mode makes easy to hit, because the command processor thread can call
back into the driver while it holds `hw_queue_mutex_`.

The current patch is still incomplete as a concurrency hardening step because it
serializes ioctl handler bodies without defining the lifetime boundary for
operations that have already captured a process object. The earlier interposer
work had to solve the same kind of problem by making ownership snapshots
explicit; `SimulatedKfd` needs that same sharp boundary for process and fd
lifetime before this PR is safe to merge.
