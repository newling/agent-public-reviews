# Review: PR #6657 — rocjitsu: Add daemon and initial support for multiple processes

**Author**: atgutier
**Date reviewed**: 2026-06-01
**PR**: https://github.com/ROCm/rocm-systems/pull/6657

> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**Build environment**:
- g++ 13.3.0 (Ubuntu 24.04)
- cmake 4.3.1
- Release build, no extra CXX flags
- AMD EPYC 9575F, Linux 6.8.0-38-generic

**Command**: `ctest --test-dir ~/workspace/builds/rocm-systems-claudius -j$(nproc) --output-on-failure`
**Timing**: 103s wall
**Result**: Flaky failures under parallel execution — **introduced by this PR**

Ran the full test suite (`-j64`) 5 times on the PR branch and 3 times on
develop:

| Branch | Runs | Failures |
|--------|------|----------|
| PR branch | 5 | 4/5 had 1–2 failures |
| develop | 3 | 0/3 failures |

The failing tests vary between runs — `Square_4x4`, `Square_16x16`,
`Tiny_2x2x3`, `HipVectorAddTest.CorrectResult`, `RocblasGemmFuzz.Iter0`.
All pass reliably in isolation (5/5). This is a systemic issue under parallel
execution introduced by this PR, not a specific test bug. The failures
span HIP tests and GEMM tests of various sizes, pointing to shared
infrastructure (command processor, completion tracker, or interposer) rather
than any individual test.

Additionally, GEMM tests take ~2.4s on the PR branch vs ~1.2s on develop (2x
slower), which may make them more susceptible to contention under parallel
execution.

**Daemon tests**: 5 new daemon tests (`DaemonTest.*`) pass from a non-tty
session (2.6s total) but **hang reliably from an interactive terminal**. The
test fixture forks a daemon, then launches the HIP client via `popen("sh -c
-- XDG_RUNTIME_DIR=... LD_PRELOAD=... hip_vector_add_test ...")`. From an
interactive pts, the `sh -c` child process gets stuck (state `S+`, 0% CPU)
before exec'ing the test binary. From a non-tty subprocess on the same
machine, same user, same build, the test passes in ~440ms. The root cause
is unknown but is likely related to controlling terminal inheritance in the
forked daemon or popen'd client.

Additionally, failed or interrupted daemon test runs leave stale processes
and socket directories under `XDG_RUNTIME_DIR/rocjitsu-test-*/` that are not
cleaned up. These accumulate and can interfere with subsequent runs. The
daemon also ignores `SIGTERM` during shutdown (requires `SIGKILL`), and the
`config_path` file written to `XDG_RUNTIME_DIR/rocjitsu/` persists after
daemon exit, causing non-daemon HIP tests to unexpectedly spin up an embedded
VM via the interposer's `get_or_create()` path.

**CI status**: Linux build fails due to `MADV_POPULATE_WRITE` not being
declared on the CI builder's kernel headers. The PR description mentions a
`#ifndef` guard — this may not have been pushed yet or may be incomplete.

## Summary

This is a large, multi-topic PR (11k additions, 127 files) that adds four
major capabilities:

**1. Daemon mode and multi-process support.** A Unix-domain socket RPC
transport enables multiple HIP processes to share a single simulated GPU.
The monolithic `SimulatedDriver` is decomposed into per-process `KfdProcess`
state containers and a daemon-side driver. A CLI launcher provides `--daemon`
and `--attach` modes. File descriptors for shared memory (memfd) are passed
via `SCM_RIGHTS`.

**2. Command processor overhaul.** The dispatch path moves to a two-phase
model: Phase 1 fills CU wavefront slots, Phase 2 activates CUs asynchronously.
A backpressure mechanism prevents infinite spin when all CUs are full.
Completion tracking moves from "all CUs idle" to per-dispatch workgroup
refcounts (`CompletionTracker`).

**3. ISA correctness fixes.** DS CMPSWAP register source (data0 → data1 for
compare operand, all 10 arch targets), F64 atomic elem_size (4 → 8), buffer
cache instruction remapping, `s_memrealtime` implementation.

**4. VMID-aware memory.** Every memory subsystem interface gains an explicit
`uint32_t vmid` parameter (default 0 for backward compatibility). The ambient
`set_active_vmid()` pattern is removed. All flat/mubuf/smem instructions now
pass `wf.process_id()` as the VMID through the entire cache hierarchy.

## Actionable items

### 1. Flaky test failures under parallel execution (regression)

The full test suite fails 4 out of 5 times under `-j64` on this branch, with
different tests failing each run. Develop is 0/3 failures under the same
conditions. This is a concurrency bug introduced by this PR — likely in the
command processor, completion tracker, or interposer. Must be investigated
before merge.

### 2. CI build failure — MADV_POPULATE_WRITE

The CI build fails because `MADV_POPULATE_WRITE` is not defined on the CI
system's kernel headers. The PR description mentions a `#ifndef` guard but CI
is still failing, so either the fix hasn't been pushed or it's incomplete.

### 3. GEMM test performance regression (2x slower)

`RocblasGemmTest.Square_4x4` takes ~2.4s on this branch vs ~1.2s on develop.
This could be overhead from the new completion tracker linear scan (replacing
an O(1) hash lookup), the two-phase dispatch model, or the recursive mutex.
Worth investigating whether this is expected.

### 4. Fd leak on partial RPC recv failure

**File**: `remote_driver.cpp`, `send_ioctl` method

After receiving the response header via `rpc_recv_msg`, if the subsequent
`rpc_recv_exact` for the payload fails, any file descriptor received with the
header (stored in `received_fds[0]`) is leaked — there is no cleanup on the
payload-recv failure path.

### 5. KfdProcess public fields bypass mutex protection

**File**: `kfd_process.h`

`KfdProcess` has `alloc_mutex_` and `page_table_mutex_`, but most fields
(including `allocations_`, `next_handle_`, queues, events) are public.
Callers can bypass `alloc_mutex_` when accessing `allocations_` directly.
The empty `private:` section at line 173 suggests encapsulation was deferred.

### 6. CompletionTracker linear scan replaces O(1) lookup

**File**: `completion_tracker.cpp`

`notify_wg_complete` now does a linear scan across all queues and entries to
find the matching `dispatch_id`, replacing the previous `dispatch_queue_map_`
hash lookup. For typical workloads with few queues this is fine, but could
degrade with many concurrent dispatches.

## Suggestions

### 1. RPC request_id is generated but never verified

`request_id` is assigned in the client but the response's `request_id` is
never checked against the sent value. Fine for the current single-threaded
model, but would silently corrupt if pipelining were ever added. An assert
would be cheap insurance.

### 2. Socket path /tmp fallback has TOCTOU risk

The `XDG_RUNTIME_DIR/rocjitsu` path has correct per-user permissions. The
`/tmp/rocjitsu-<uid>` fallback is riskier — another user could create that
directory first. Consider using `mkdtemp` or verifying ownership after
`create_directories`.

### 3. L2 eviction vmid assumption

The L2 eviction path uses the requesting vmid to translate the evicted dirty
line's address. The comment notes this is correct because "the only source of
dirty L2 lines is K$ writeback." If that invariant ever changes (e.g., L2
becomes write-back for V$ stores), this would silently translate through the
wrong page table. Consider storing vmid in the cache tag metadata or adding
an assert.

### 4. recursive_mutex design note

The `std::mutex` → `std::recursive_mutex` change for `hw_queue_mutex_` is
necessary given the call chain `handle_doorbell` → `dispatch_workgroups` →
`halt()` → `notify_wg_complete`. However, since `notify_wg_complete` is
always called from paths that already hold the lock, the `lock_guard` inside
`notify_wg_complete` is redundant (it succeeds trivially due to recursion).
If it can be guaranteed that `notify_wg_complete` is never called without the
lock held, the inner lock_guard could be removed and the mutex kept as a
regular `std::mutex`.

## Commentary

**ISA fixes are correct and consistently applied.** The DS CMPSWAP data0 →
data1 fix is verified across all 10 arch targets. The F64 atomic elem_size
fix properly catches all cases (X2 suffix, 64-bit type suffix, and ≥2 dword
operations). The buffer cache remapping now correctly targets L1 vector + L2
instead of L1 scalar.

**VMID threading is thorough.** Every memory access path from instruction
execution has been updated: instruction fetch, scalar memory, vector memory,
cache hierarchy (L1 scalar, L1 vector, L2), completion tracker flushes, and
command processor GPU reads. No remaining ambient vmid-less paths were found
in the updated code. The `vmid = 0` defaults maintain backward compatibility.

**Interposer hardening is well done.** The `RTLD_NEXT` change (replacing raw
`syscall()` calls with saved libc function pointers) is a significant
improvement. The fork safety implementation (placement-new on mutexes,
clearing fd tracking, nullifying VM pointers) is correct. The aligned-storage
singleton pattern avoids `__cxa_finalize` destruction race with the detached
engine thread.

**The RPC protocol is clean** — fixed 16-byte header, versioned handshake,
`SCM_RIGHTS` fd passing with a 4-fd cap. Error handling for partial
reads/writes and `EINTR` is solid. The main gap is the missing `request_id`
verification noted above.

**This PR would benefit from splitting.** The ISA correctness fixes, VMID
threading, daemon/RPC transport, and command processor overhaul are largely
independent topics. Reviewing them as a single 11k-line PR makes it harder
to verify each concern in isolation. The ISA fixes in particular could land
immediately as they fix silent wrong-answer bugs.
