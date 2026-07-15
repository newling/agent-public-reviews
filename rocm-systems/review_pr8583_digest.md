This is a review from an agent with an automatic prompt from the reviewer

## Summary

PR #8583 is the right kind of hardening for daemon-mode `SimulatedKfd`: it adds
a per-process operation mutex, fixes an `alloc_mutex_` / command-processor lock
ordering problem in queue creation, and makes several pieces of process state
use explicit locks. That direction matches the concurrency work from PR #8232.

I think the PR still needs a follow-up before merge because the current locking
does not fully define the lifetime boundary for a `KfdProcess` once a thread has
already snapped a `shared_ptr` to it.

## Main Issues To Fix

### 1. Final close can still race already-snapshotted operations

`SimulatedKfd::ioctl()`, `mmap()`, `munmap()`, and `get_mmap_memfd()` first look
up a `std::shared_ptr<KfdProcess>` and then dispatch work. `close(process_id)`
erases the process from `processes_`, then takes `proc.op_mutex_`, tears down
allocations, unregisters queues, closes fds, and returns.

That blocks new lookups, but it does not stop a thread that already captured the
shared pointer before `close()` erased the table entry. Such a thread can run
after teardown and operate on a `KfdProcess` whose allocations, queues, and fds
have already been cleared.

Suggested fix: add a per-process closing state or operation accounting. Set the
closing state before teardown and make every dispatch entry point reject work
after it has been set. The important detail is that the check must happen after
the operation has synchronized with close, not only at process-table lookup time.

### 2. Doorbell mmap uses a raw memfd after dropping `alloc_mutex_`

In the doorbell `dispatch_mmap()` path, the code finds `alloc.memfd` under
`proc.alloc_mutex_`, stores it in `doorbell_fd`, drops the mutex, and then calls
`fstat()`, `ftruncate()`, and `safe_mmap()` on that fd.

Because `mmap()` is not under `op_mutex_`, a concurrent `FREE_MEMORY_OF_GPU` or
final `close()` can take `alloc_mutex_` and close that stored memfd before the
mmap path uses it. At best the mmap sees `EBADF`; at worst the fd number is
reused and rocjitsu operates on the wrong file descriptor.

Suggested fix: duplicate the doorbell memfd while holding `alloc_mutex_`, use
the duplicate outside the lock, and close the duplicate before returning. This is
the same ownership pattern used in the related interposer hardening: when an fd
must outlive the lock protecting the stored descriptor, the caller should own its
own fd reference.

### 3. Add focused tests

The live policy bot is failing because source files changed without a test file
change. The existing local focused tests pass, but they do not force the two
interleavings above.

Useful tests would cover:

- an operation that has already snapped a process pointer before final close;
- doorbell mmap racing with free/close, verifying the mmap path owns a stable fd
  or fails cleanly without using a reused descriptor.

## Local Validation

Build passed:

```bash
time -p cmake --build $BUILD_DIR --parallel 8 \
  --target rocjitsu_tests daemon_test rocjitsu_bin rocjitsu_shared
```

Focused tests passed:

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R 'SimulatedKfdTest|KfdIoctlTest|DaemonTest\.(HipVectorAdd|HipMemcpy|TwoIndependentClients|InterposerDup)|InterposerDupTest' \
  --output-on-failure --timeout 120
```

Result: 28/28 passed. `git diff --check origin/develop...HEAD` also passed.

## Smaller Suggestion

The commit title says `SimulatedKfd`, while the live PR title says
`SimulatedDriver`. Consider renaming the PR title to match the class being
changed.
