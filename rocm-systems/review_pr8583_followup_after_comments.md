This is a follow-up note after checking the live PR conversation for PR #8583.

## Posted comment

The review link comment is visible on the PR. One small wording note: the PR's
main mutex is per simulated `KfdProcess`, not one global daemon mutex. The
question is still fair if read as "single per-process mutex for most ioctls,
minus WAIT_EVENTS."

## Other reviewer comments

### Still unresolved

1. **Close / shared_ptr lifetime gap**

Copilot originally noted that `close()` needs to exclude in-flight ioctls.
The current head takes `op_mutex_` in `close()`, but another reviewer correctly
points out that this is still incomplete: operations can snapshot
`std::shared_ptr<KfdProcess>` before close erases the process table entry, then
run after teardown. The gap also applies to `mmap()` and `munmap()`, which are
not under `op_mutex_`.

This matches the main issue in the agent review.

2. **`dispatch_munmap()` uses caller length for doorbell CPU unmap**

Copilot notes that `dispatch_munmap()` captures the tracked
`doorbell_page_size` for GPU unmap, but passes the caller-provided `length` to
`munmap()`. If the caller length differs from the tracked mapping size, CPU and
GPU-side unmap behavior can diverge.

This is a separate cleanup not covered in the original agent review.

3. **Destructor only calls `close(pid)` once per snapshotted process**

Another reviewer notes that the new destructor snapshots process IDs and calls
`close(pid)` once. If a process has `open_ref_count_ > 1`, `close()` decrements
the refcount and returns without full cleanup. The old `while (!processes_.empty())`
shape would keep closing until the process was removed. The destructor should
force teardown or keep closing each snapshotted PID until it disappears.

This is also separate from the original agent review and looks valid.

4. **Need an in-process multithreaded regression**

Another reviewer explicitly asks for a multithreaded `SimulatedKfd` regression.
The existing `SimulatedKfdTest` cases are single-threaded and do not exercise
the new locking/lifetime invariants. Suggested coverage: race doorbell `mmap`
or queue operations with `close()`.

This aligns with the agent review and the policy bot's failed unit-test check.

### Resolved / outdated

1. **`fd_to_import_handle_` stale on close**

Copilot noted that `close()` cleared `imported_dmabufs_` but left
`fd_to_import_handle_` populated. The current code clears both maps, and the
thread is marked resolved/outdated.

## Net State

The live reviewer feedback strengthens the same conclusion as the agent review:
the PR is heading in the right direction, but it needs a sharper process-lifetime
boundary around final close plus focused multithreaded regression coverage before
it is ready.
