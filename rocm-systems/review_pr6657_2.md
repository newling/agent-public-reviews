# Re-review: PR #6657 -- rocjitsu: Add daemon and initial support for multiple processes

**Author**: Tony Gutierrez (@atgutier)
**Date reviewed**: 2026-06-04
**PR**: https://github.com/ROCm/rocm-systems/pull/6657
**Previous review**: review_pr6657.md (2026-06-01)

> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**Build environment**:
- g++ 13.3.0 (Ubuntu 24.04)
- cmake 4.3.1
- Release build, no extra CXX flags
- AMD EPYC 9575F, 128 HW threads, Linux 6.8.0-38-generic

**Command**: `ctest --test-dir ~/workspace/builds/rocm-systems-augustus -j$(nproc) --output-on-failure`
**Timing**: ~107s wall
**Result**: Flaky failures persist under parallel execution (`-j128`)

Four runs of the full suite:

| Run | Total | Failed | Failing tests |
|-----|-------|--------|---------------|
| 1   | 425   | 1      | HipVectorAddTest.CorrectResult (SEGFAULT) |
| 2   | 425   | 2      | RocblasGemmTest.Rect_64x1x64, RocblasGemmFuzz.Iter3 |
| 3   | 425   | 0      | (clean) |
| 4   | 425   | 0      | (clean) |

All failing tests pass 5/5 in isolation. The failures span HIP vector_add and GEMM tests of different sizes and types, confirming this is a systemic concurrency issue in shared infrastructure, not a bug in any individual test.

**Improvement from previous review**: The PR now has 425 tests, including 5 RCCL daemon tests and 5 new daemon tests. All daemon tests pass. The RCCL tests take ~35s each. The flakiness rate appears reduced (2/4 runs failing vs 4/5 in the previous review), though it persists.

**Daemon tests**: All 10 daemon/RCCL tests pass reliably, including multi-client (TwoIndependentClients) and RCCL collectives (AllReduce, Broadcast, AllGather, ReduceScatter, SendRecv). This is a significant improvement from the previous review where daemon tests hung from interactive terminals.

**MADV_POPULATE_WRITE CI fix**: The `#ifdef MADV_POPULATE_WRITE` guard is present in interposer.cpp (line 809). However, three other files use `MADV_POPULATE_WRITE` via `syscall(SYS_madvise, ..., MADV_POPULATE_WRITE)` without the guard -- see finding #2 below.

## Summary

This is a re-review of a 14-commit force-push that builds on the original daemon/multi-process PR. The core architecture is unchanged from the previous review: daemon mode via Unix socket RPC, per-process KFD state in KfdProcess, VMID-threaded memory hierarchy, ISA correctness fixes, and command processor overhaul. The new commits address several issues from the previous review and add RCCL collective test support:

- Doorbell monitor join deadlock fixed (the CP no longer joins the doorbell thread in unregister_queue; it defers to destructor)
- Queue-inactive signal firing on HQD idle, fixing RCCL persistent kernel hangs
- CDNA4 scratch addressing fix (stop clobbering user SGPRs s102:s103)
- Null indirect jump fault handling for RCCL daemon mode
- RCCL socket bind fix and 2-GPU daemon config
- ScratchAddrCalcTest updated to use wavefront scratch base register
- Removed unused owner_process_id from HwQueueState

## Actionable items

### 1. Flaky test failures under parallel execution (regression, persists from previous review)

**Severity**: Bug
**Status**: Persists from previous review

The full test suite fails 0-2 tests per run under `-j128`, with different tests failing each time. All pass in isolation. The failing tests span HIP vector_add (SEGFAULT in one run) and GEMM, pointing to shared infrastructure. The SEGFAULT in HipVectorAddTest is new compared to the previous review where failures were wrong-answer/assertion failures. A segfault under parallel execution is more concerning than a wrong answer -- it suggests memory corruption or use-after-free in the interposer, driver, or command processor.

### 2. MADV_POPULATE_WRITE unguarded in three files (persists from previous review, partially fixed)

**Severity**: Bug (CI build failure)
**Status**: Partially fixed -- interposer.cpp is guarded, but three other call sites are not

**File**: `remote_driver.cpp`, lines 448 and 550
**File**: `simulated_driver.cpp`, line 782

The interposer correctly guards `MADV_POPULATE_WRITE` with `#ifdef` (line 809). However, three other call sites use `MADV_POPULATE_WRITE` directly via `syscall(SYS_madvise, ..., MADV_POPULATE_WRITE)` without any guard. These will fail to compile on systems where the constant is not defined in kernel headers (the same CI environment that originally triggered the build failure). The `syscall()` approach bypasses the library-level check but still needs the constant defined.

### 3. Fd leak on partial RPC recv failure in send_ioctl (persists from previous review)

**Severity**: Bug
**File**: `remote_driver.cpp`, `send_ioctl` method, around line 354-362

After `rpc_recv_msg` receives the response header (which may include an `SCM_RIGHTS` fd in `received_fds[0]`), if the subsequent `rpc_recv_exact` for the payload fails (line 362 `return -1`), any received fd is leaked. The fd is only consumed in the ALLOC_MEMORY / IPC_IMPORT handler paths later in the function. A simple fix: close `received_fds[0]` on the payload-recv error path.

### 4. KfdProcess fields still public (persists from previous review)

**Severity**: Concern
**File**: `kfd_process.h`, lines 140-174

KfdProcess has `alloc_mutex_` and `page_table_mutex_`, but nearly all data members (allocations_, next_handle_, active_queue_ids_, queue_doorbell_map_, etc.) are public. The `private:` section at line 173 is empty. Code in simulated_driver.cpp correctly acquires `alloc_mutex_` before accessing `allocations_`, but nothing prevents a future caller from bypassing the lock. This is a maintainability concern rather than a current bug, since the current callers are disciplined.

### 5. Non-atomic static counters in L2 cache (log throttling)

**Severity**: Concern
**File**: `l2_cache.cpp`, line 23

```cpp
static uint64_t wb_count = 0;
```

This `static uint64_t` in `send_backing` is shared across all L2Cache instances within a process. L2Cache's non-atomic paths are documented as requiring single-partition assignment (all CUs on the same thread), so this is safe within a single L2 instance. However, if multiple L2 instances (from different XCDs or GPUs) call `send_backing` concurrently (which can happen in the 2-GPU daemon config), this is a data race. Only affects log output, not correctness, but technically UB. The evict_count in `ensure_line` (line 69) is correctly `thread_local`.

### 6. L2 flush_all vmid assumption (persists from previous review, acknowledged in comment)

**Severity**: Concern
**File**: `l2_cache.cpp`, `flush_all` (line 160) and `ensure_line` eviction path (line 63)

The L2 eviction and flush paths use the requesting vmid to translate the evicted dirty line's address through the page table. The code comment at line 62 acknowledges this: "correct because the only source of dirty L2 lines is K$ writeback." This assumption is valid today because L2 writes are write-through (line 101 in l2_cache.cpp), but the `dirty` flag is still set in the `writeback_line` method for non-CC mtypes (line 143). If the write-through policy were ever removed, evictions would translate through the wrong page table. Consider storing the originating vmid in the cache tag metadata.

### 7. Socket leak in get_or_create_remote on open() retry

**Severity**: Bug (resource leak)
**Status**: New
**File**: `interposer.cpp`, `InterposerContext::get_or_create_remote()`, lines 201-214

If `connect_to_daemon()` succeeds but `remote_->open()` fails (returns fd < 0), the function returns nullptr. The RemoteDriver is left allocated (`remote_` is non-null) with the first socket. On the next call, line 202's early-return check fails (because `remote_kfd_fd_ < 0`), so `connect_to_daemon()` runs again creating a second socket. But line 207 sees `remote_` is non-null and skips allocation -- the second socket is never given to anything and is leaked. Each subsequent retry leaks another socket. Fix: close `sock` when `remote_` is already set, or pass the new socket to the existing RemoteDriver.

### 8. Socket path silently truncated when longer than sun_path

**Severity**: Concern
**Status**: New
**File**: `transport.cpp`, lines 29 and 54; `main.cpp`, line 222

`endpoint.copy(addr.sun_path, sizeof(addr.sun_path) - 1)` silently truncates paths longer than 107 characters. With deeply nested `XDG_RUNTIME_DIR` or `ROCJITSU_RUNTIME_DIR` paths (common in test infrastructure with mkdtemp), the daemon could bind to a truncated path while the client attempts to connect to a different truncated form, or the bind could succeed on a different path than intended. There is no length check or error reporting. Either validate `endpoint.size() < sizeof(addr.sun_path)` and return an error, or use abstract sockets (`\0` prefix) which are not path-limited.

### 9. Daemon non-IOCTL RPC response path does not set resp.opcode

**Severity**: Concern
**Status**: New
**File**: `main.cpp`, lines 68, 90, 143

For RPC_HANDSHAKE, RPC_CLOSE, and RPC_MUNMAP handlers, the response `RpcHeader` is zero-initialized (opcode = 0, which is RPC_HANDSHAKE). The client does not check the response opcode, so this is not a correctness bug today, but it means a desynchronized stream could silently misparse responses. The RPC_IOCTL handler (line 169) correctly sets `resp.opcode = RPC_IOCTL`. The other handlers should do the same for consistency and debuggability.

## Suggestions

### 1. CompletionTracker linear scan (persists from previous review)

**File**: `completion_tracker.cpp`, `notify_wg_complete`, lines 23-36

The linear scan across all queues and entries to find the matching `dispatch_id` is functionally correct. For typical workloads with few concurrent dispatches this is fine. If dispatch throughput becomes a concern, a dispatch_id-to-queue-entry index would restore O(1) lookup.

### 2. RPC request_id still not verified (persists from previous review)

**File**: `remote_driver.cpp`

`request_id` is assigned in the client but never checked in the response. Fine for the current single-connection model, but an assert would be cheap insurance against future pipelining bugs.

### 3. open_process duplicates open's CP initialization block

**File**: `simulated_driver.cpp`, lines 261-335 (open) and 337-406 (open_process)

The CP initialization block (setting up interrupt callbacks, scratch resolvers, apertures) is duplicated verbatim between `open()` and `open_process()`. If either is updated without the other, they will diverge. Consider extracting to a shared method.

### 4. /tmp fallback path TOCTOU risk (persists from previous review)

**File**: `rpc.h`, line 242

The `rpc_default_runtime_dir()` falls back to `/tmp/rocjitsu-<uid>`. This is created by `create_directories` in `transport.cpp` (line 24) without verifying ownership. Another user could pre-create `/tmp/rocjitsu-<uid>` as a symlink or directory with different permissions. Consider using `mkdtemp` for the fallback, or verifying ownership after creation.

### 5. DaemonTest fixture uses SIGKILL for teardown

**File**: `daemon_test.cpp`, line 77

The daemon is killed with `SIGKILL` in TearDown. This prevents the daemon from cleaning up its socket file and any state. While the test fixture does `remove_all(tmp_dir_)` afterward, a more graceful shutdown (SIGTERM with a timeout, falling back to SIGKILL) would exercise the daemon's shutdown path and catch shutdown bugs.

## Commentary

**Interposer fork handling is correct.** The `reset_after_fork` method (line 146-159 of interposer.cpp) placement-news the mutexes (destroying any poison state from the parent's locked mutexes in dead threads), clears fd tracking, and nullifies the VM pointer. The fork() interposition at line 1053-1058 calls this in the child process. The `in_construction` flag is also cleared, preventing the child from seeing a half-initialized VM.

**Interposer singleton pattern is sound.** The aligned-storage singleton with explicit placement-new construction (lines 362-372) avoids the `__cxa_finalize` destruction race noted in the previous review. The `in_construction` atomic flag (line 136) prevents re-entrant calls to `get_or_create()` during VM construction from triggering infinite recursion through the interposed `open()`.

**VMID threading remains thorough.** All memory paths from instruction execution through the cache hierarchy carry the explicit vmid parameter. The `GpuMemory::translate` method (line 197 of gpu_memory.h) correctly uses shared_lock on both the vmid_table_mutex_ and the per-process page_table_mutex_, allowing concurrent reads from different CU threads.

**The new RCCL daemon tests are well-structured.** The `RcclDaemonTest` fixture (daemon_test.cpp lines 216-328) starts a 2-GPU daemon, runs ranks as separate attach processes, and validates collective results. The per-test mkdtemp isolation prevents socket conflicts under parallel execution.

**ISA fixes from the previous review are unchanged and remain correct.**

**Previous review items resolved:**
- Daemon test terminal hang: appears to be resolved (all daemon tests pass reliably from the test harness)
- MADV_POPULATE_WRITE: partially fixed (interposer guarded, remote_driver and simulated_driver still unguarded)
- GEMM performance regression: not directly measurable without develop baseline in this worktree, but GEMM tests complete in ~3.6s each which is in line with prior measurements
