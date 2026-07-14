> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8232
**Commit reviewed:** `d2671c016c` (`fix(rocjitsu): Harden interposer concurrency`)

Local validation:

```bash
time -p cmake --build $BUILD_DIR --parallel 8 \
  --target interposer_dup_test daemon_test rocjitsu_bin rocjitsu_shared

time -p ctest --test-dir $BUILD_DIR \
  -R 'InterposerDupTest|DaemonTest\.InterposerDup' \
  --output-on-failure --timeout 120

git diff --check origin/develop...HEAD
```

Results: build passed in 180.81s; focused CTest passed 11/11 in 5.23s;
`git diff --check` passed.

CI status at review time was not fully green: `pre-commit`, `therock-pr-bot`,
and `test (asan-ubsan)` passed, while `test (release)`, `test (asan-ubsan-gcc)`,
and `Linux ( | gfx125X-dcgpu) / Build Linux Packages` were reported failed. The
GitHub run logs were not available via `gh run view --log-failed` when checked,
so I did not classify those CI failures.

## Summary

This PR hardens rocjitsu's KFD interposer fd/lifetime handling around `open`,
`close`, `dup`, `dup2`, `dup3`, `fcntl(F_DUPFD*)`, `ioctl`, `mmap`, `munmap`,
and `fork`. The important changes are backend-tagged KFD dup tracking,
primary-fd invalidation/re-minting, `std::shared_ptr` snapshots for daemon-mode
`RemoteDriver` lifetime, caller-owned dup memfds for remote mmap, and local
tests plus daemon-backed tests for the new fd state machine.

## Actionable Items

### 1. Decide whether the GuestKfd hidden real fd needs the same primary invalidation story

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/kmd/linux/guest_kfd.cpp:595`

The current local/remote primary invalidation work does not extend cleanly to
`GuestKfd`. `GuestKfd::open()` returns an app-facing dup, but the driver keeps a
hidden real `/dev/kfd` fd in `real_kfd_fd_`. `GuestKfd::fd()` and `owns_fd()`
still classify that hidden fd number as KFD, and `GuestKfd` does not override
`LinuxKfd::invalidate_primary_fd()`.

If some unrelated `dup2`/`dup3` target reuses that hidden real fd number, the
interposer can keep treating the reused number as GuestKfd-owned. This appears
preexisting and DBT-guest-specific, but it is the remaining gap relative to this
PR's "overwritten primary fd numbers stop being KFD" invariant.

A naive `GuestKfd::invalidate_primary_fd()` may not be enough because
`invalidate_overwritten_kfd_fd()` calls `d->close()` after a successful local
primary invalidation, while GuestKfd's hidden real fd is not represented as an
app-facing `open_refs_` reference. This likely needs either a GuestKfd-specific
hidden-fd invalidation path or a sharper base-class contract that separates
"clear primary fd identity" from "drop app-facing primary open reference".

## Suggestions

Add a DBT/GuestKfd regression only if that mode is expected to tolerate arbitrary
fd reuse of its hidden real KFD fd. The current PR already has good local and
daemon-mode coverage for the main fd/backend state machine.

## Commentary

The major concurrency issues raised in earlier review rounds look addressed in
the current head. Two new GitHub reviews on this head are approvals; one of them
calls out the GuestKfd caveat above as a remaining preexisting edge case rather
than a reason to block the PR.
