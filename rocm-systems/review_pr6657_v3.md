# Review: PR #6657 — rocjitsu: Daemon mode, multi-process, ISA fixes (v3)

**Date reviewed**: 2026-06-04
**PR**: https://github.com/ROCm/rocm-systems/pull/6657

> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**Build environment**:
- clang 22.1.3 (ROCm 7.2.0 LLVM toolchain)
- cmake 4.2.3, Ninja generator
- No explicit build type (default)
- AMD EPYC 9575F, Linux 6.14.0-1018-oem

**Build**: Clean — all 352 targets compile. Zero errors, zero warnings.

**Command**: `ctest --test-dir $BUILD_DIR -j6 --output-on-failure -E "DaemonTest|RcclDaemon|Large_2048|RocblasGemm|Rocminfo"`

**Result**: 385/385 pass (8.5s wall)

At `-j$(nproc)` (128 threads), 10–13 tests fail per run with "Subprocess killed"
(timeouts). The failing tests vary between runs — `MatmulStressTest.*`,
`SimulatedDriverTest.*`, `KfdIoctlTest.*`, `VectorAddStressTest.*`. All pass
at `-j6`. These are resource contention issues under extreme parallelism, not
correctness bugs — the test fixture's simulated driver + engine is heavy
enough that 128 concurrent instances exhaust the machine. Prior reviews ran
at `-j64` and `-j128` and saw similar patterns.

**Test count**: 426 registered tests (excluding nothing). This is 7 more than
the v2 review's 419, accounted for by the final commit adding
`BfeRegressionTest.ThreadIdxY` and CDNA3 GEMM fuzz variants.

RCCL daemon and rocBLAS GEMM tests were excluded from this run at the
developer's request.

## Summary

This PR (9.4k additions, 138 files) adds four major capabilities to the
rocjitsu GPU emulator:

**1. Daemon mode and multi-process support.** A Unix-domain socket RPC
transport (`rpc.h`, `transport.h/cpp`) enables multiple HIP processes to
share a single simulated GPU. The monolithic `SimulatedDriver` is decomposed:
per-process state (allocations, queues, events, doorbells, page tables) moves
into `KfdProcess`, while `SimulatedDriver` becomes a process-table manager
with both local-mode (interposer) and daemon-mode (per-process-id) overloads
for `ioctl`/`mmap`/`munmap`. `RemoteDriver` is the client-side RPC stub.
A CLI launcher (`tools/rocjitsu/main.cpp`) provides `--daemon`, `--attach`,
and local modes.

**2. Interposer overhaul.** The LD_PRELOAD interposer is restructured around
`InterposerContext` (a placement-new singleton to avoid `__cxa_finalize`
destruction races with the detached engine thread). `LibcPassthrough` resolves
real libc function pointers via `RTLD_NEXT` (replacing raw `syscall()` calls).
Fork safety resets all mutable state via `reset_after_fork()`. New
interposition points: `fork`, `stat`, `lstat`, `access`, `madvise`,
`mprotect`, `dup3`, `fcntl`, `opendir`, `freopen`, and the glibc fortified
variants (`__open_2`, `__open64_2`, `__openat_2`, `__openat64_2`).

**3. Command processor and completion tracker overhaul.** The dispatch path
moves to a two-phase model with backpressure. Completion tracking moves from
a `dispatch_queue_map_` O(1) lookup to a linear scan across all queues.
`CompletionTracker` gains `fire_queue_idle_signal` which writes the HQD
status and fires the per-queue KFD interrupt — matching real CP firmware
behavior needed for ROCR's `DynamicQueueEventsHandler`. The `on_cu_idle`
callback path now respects the AQL barrier bit.

**4. ISA correctness fixes and VMID threading.** DS CMPSWAP data0→data1
across all 10 arch targets, F64 atomic elem_size 4→8, buffer cache
instruction remapping, `s_memrealtime` implementation, CDNA4 scratch
addressing (stop clobbering user SGPRs s102:s103), `s_call_b64` offset
calculation (`+4`), FLAT_SCRATCH register routing through
`wf.scratch_base()`/`wf.set_scratch_base()`, scratch address SVE bit
interpretation. All memory interfaces gain explicit `uint32_t vmid`
parameters, replacing the ambient `set_active_vmid()` pattern.

## Actionable items

### 1. Sockets created without SOCK_CLOEXEC — fd leak across exec

**Files**: `transport.cpp:20,48`

Both `UnixTransport::listen()` and `UnixTransport::connect()` call
`socket(AF_UNIX, SOCK_STREAM, 0)` without `SOCK_CLOEXEC`. The `accept()`
at line 41 also lacks `SOCK_CLOEXEC` (should use `accept4`). If the process
forks+execs (common with MPI), these sockets leak into child processes. The
interposer's `connect_to_daemon()` at `interposer.cpp:46` does use
`SOCK_CLOEXEC`, so this is an inconsistency rather than a universal problem.

*Fix*: Add `SOCK_CLOEXEC` to `socket()` flags and use `accept4` with
`SOCK_CLOEXEC`.

### 2. Unbounded allocation from daemon response payload

**File**: `remote_driver.cpp:364`

When receiving an ioctl response, `std::vector<uint8_t> payload(resp->payload_bytes)`
uses the daemon's response value without any upper bound check. A misbehaving
daemon could trigger an OOM. The `handle_client` server side in `main.cpp:160`
has a `kMaxPayloadBytes = 16MB` cap on the request path, but the client has no
corresponding cap on the response path.

*Fix*: Add a sanity cap (e.g., 16MB) before the allocation.

### 3. `promote_userptr` does not check `safe_mmap` return before `madvise`

**File**: `remote_driver.cpp:449-451`

The `MAP_FIXED` mmap at line 449 replaces the user's existing mapping. If
`safe_mmap` returns `MAP_FAILED`, the code still calls `madvise` on the
`MAP_FAILED` address (line 451). The function does not report the error —
the original userptr mapping is left in an ambiguous state.

*Fix*: Check the return value and propagate the error.

### 4. `rpc_recv_msg` does not retry on EINTR

**File**: `rpc.h:161`

`rpc_recv_msg` uses `recvmsg` with `MSG_WAITALL`, but `MSG_WAITALL` does not
guarantee EINTR retry. If a signal interrupts the receive, the function returns
a short read or -1 without retrying. This differs from `rpc_recv_exact` and
`rpc_send_exact` which both handle EINTR explicitly. Since the daemon forks
and uses signals (SIGINT, SIGTERM), this is a realistic scenario.

*Fix*: Add an EINTR retry loop, consistent with `rpc_recv_exact`.

### 5. `alloc_ranges_` grows monotonically — stale entries on handle reuse

**File**: `remote_driver.cpp:415-418,482-483`

`register_allocation` appends to `alloc_ranges_` unconditionally. If the same
memfd number is reused by the OS after a free+realloc cycle, the erase in
`FREE_MEMORY_OF_GPU` (line 482) matches by memfd value, potentially finding a
stale entry from a prior allocation. For long-running daemon clients this is a
latent correctness issue.

*Fix*: Match by handle or VA rather than memfd, or remove stale entries during
registration.

### 6. `close()`/`connect()` inconsistent syscall vs libc usage in transport

**File**: `transport.cpp:57,79`

`UnixTransport::connect()` uses `syscall(SYS_close, sock)` on the failure path
(presumably to avoid interposer interception), while `UnixTransport::close()`
uses `::close(fd_)`. If the libc `close()` is interposed, the destructor goes
through the interposer but connect's cleanup does not. Similarly, `listen` at
line 33 uses `::close(sock)`. The choice should be consistent — either always
use the raw syscall (to stay below the interposer) or always use libc.

*Fix*: Use `syscall(SYS_close, ...)` consistently in transport.cpp, since this
code is loaded via the interposer.

### 7. Barrier/vendor packets never set `barrier_bit` in DispatchEntry

**File**: `command_processor.cpp:851-861,867-877`

When creating `DispatchEntry` for `BARRIER_AND`, `BARRIER_OR`, and
`VENDOR_SPECIFIC` packets, `dp.barrier_bit` is left at its default `false`.
The kernel dispatch path correctly extracts it from the AQL header at line 661.
Per HSA spec, the barrier bit on any packet type means "wait for all preceding
packets to complete before processing this one." Missing this for non-kernel
entries means a barrier packet with its barrier bit set will not wait for prior
dispatches before its signal fires.

*Fix*: Extract the barrier bit from the AQL header for all packet types, not
just kernel dispatch.

### 8. `DaemonTest::run_hip_test` has no subprocess timeout

**File**: `daemon_test.cpp:94-118`

The `run_hip_test` method uses `popen` without a `timeout` wrapper. If a HIP
subprocess hangs, `popen` blocks indefinitely. The ctest TIMEOUT sends SIGKILL
to the `daemon_test` process, but children spawned via `popen`/`sh -c` may
survive as orphans (no process group management). `RcclDaemonTest::run_rccl_rank`
correctly uses `timeout 150`, but this protection is absent from `DaemonTest`.

*Fix*: Add `timeout` to the `run_hip_test` command string.

### 9. PEP 701 f-strings require Python 3.12+ but pyproject.toml allows 3.10+

**File**: `_generator.py`

The codegen uses nested same-quote f-strings (PEP 701 syntax), e.g.,
`f'{{{''.join(ctor_body_parts)}}}'`. This raises `SyntaxError` on Python
3.10/3.11. `pyproject.toml` declares `requires-python = ">=3.10"`.

*Fix*: Either bump `requires-python` to `>=3.12` or use double-quoted inner
strings for backwards compatibility.

## Suggestions

### 1. CompletionTracker linear scan is O(queues × entries) per workgroup

**File**: `completion_tracker.cpp:6-15`

`notify_wg_complete` iterates over all queues and all entries to find the
matching `dispatch_id`, replacing the previous O(1) `dispatch_queue_map_`
lookup. For typical workloads with 1–2 queues and a handful of active
dispatches this is fine. For workloads with many concurrent dispatches
(RCCL with 8 ranks × 2 queues each), the scan runs on every workgroup
completion — potentially thousands of times per dispatch.

The v2 review noted a 1.8x GEMM performance regression with compounding
causes. Restoring the `dispatch_queue_map_` would help.

### 2. `fire_queue_idle_signal` page-crossing reads are unguarded

**File**: `completion_tracker.cpp:88-90`

The function reads multi-byte values from resolved host pages using
`sig_handle_va & 0xFFF` offsets. The cross-page check at line 88 only
covers the initial `sig_handle` read. The subsequent reads of `sig_addr`
(8 bytes at offset 8, 16, 24 from the signal base) assume the entire
`amd_signal_t` structure fits in one page. Since `amd_signal_t` is 64-byte
aligned (checked at line 96) and much smaller than 4KB, this assumption
holds in practice, but an assert would make it explicit.

### 3. Verbose debug logging in `fire_signal` production path

**File**: `completion_tracker.cpp:148-188`

`fire_signal` now contains a `SIGNAL_DUMP` logging lambda that reads 4
separate memory values (kind, val, mailbox, event_id) through
`resolve_host_ptr` or `read64`/`read32`, formats them into a string,
and constructs it inside a `Logger::cp` lambda. Even though the lambda
is only evaluated when CP logging is enabled, the two-path logic
(host_ptr vs memory read) adds code complexity to a hot path. Consider
extracting to a dedicated debug helper or removing once the signal
firing is verified stable.

### 4. `InterposerContext::get_or_create` reads config via raw syscalls with fixed buffer

**File**: `interposer.cpp:133-142` (in the diff)

The embedded VM creation path reads the config file path using
`syscall(SYS_read, cfg_fd, cfg_buf, sizeof(cfg_buf) - 1)` with a 4096-byte
buffer. If the config path is longer than 4095 bytes, it is silently
truncated. While this is unlikely in practice, a check-and-fail would be
more defensive.

### 5. `SoC::all_cus()` cache is not thread-safe

**File**: `soc.cpp:161-167`

`all_cus()` lazily populates `all_cus_cache_` with no synchronization. If two
threads call this concurrently before the cache is populated, both would append
to the vector. In the current codebase this appears to be called only during
initialization, but the non-const return-by-reference signature invites misuse.

### 6. Dead code in `DaemonTest` class

**File**: `daemon_test.cpp:121-175`

`DaemonTest` contains `run_rccl_rank()` and `run_collective()` methods that
are never called by any `DaemonTest` test case. These are only used by the
separate `RcclDaemonTest` class (which has its own copies). The
`DaemonTest::run_rccl_rank` also has a latent bug: it uses `RJ_DAEMON_CONFIG`
(1-GPU) instead of `RJ_DAEMON_CONFIG_2GPU`.

### 7. `on_cu_idle` dispatches only one entry per queue

**File**: `command_processor.cpp:509-520`

Unlike `process_queues` which loops through entries with `while`, `on_cu_idle`
only dispatches from the first pending entry per queue (no inner loop). If a
queue has many small dispatches queued, only one advances per CU-idle event,
potentially causing a stall-dispatch-activate-stall cycle.

### 8. `S_GL1_INV` and `BUFFER_WBINVL1` now also flush L2

**Files**: `execute_shared.h`, `_generator.py`

On real hardware, `S_GL1_INV` only invalidates GL1 (L1 data cache), not GL2.
The PR adds `l2->flush_all(vmid)` to these handlers. This is functionally safe
and conservative, but could mask missing `S_GL2_WB` instructions in test
kernels. Worth documenting the divergence from hardware semantics.

## Commentary

**The InterposerContext refactoring is a significant improvement.** Consolidating
all mutable state into a single placement-new singleton with explicit fork-reset
is much cleaner than the previous scattered global mutexes. The `LibcPassthrough`
pattern with RTLD_NEXT resolution eliminates the recursion risk from the old
`dlsym(RTLD_DEFAULT)` approach. The new glibc fortified-open interposition
(`__open_2`, `__open64_2`, etc.) now correctly routes through the full `open()`
logic rather than falling through to the kernel.

**The driver decomposition into KfdProcess is architecturally sound.** The
SimulatedDriver now has a clear process table with mutex-protected access,
and all ioctl handlers take a `KfdProcess&` parameter — mirroring the real
kernel's `kfd_chardev_ioctl` which resolves the process from `filp->private_data`.
The dual interface (local-mode single-process vs daemon-mode multi-process) is
cleanly separated. The IPC handle store with Boost-style hash combining is
a nice addition for cross-process memory sharing.

**The `fire_queue_idle_signal` implementation is impressive.** Reading the
`amd_queue_t` descriptor from GPU memory, extracting the signal handle, CAS-ing
the idle status with care to avoid clobbering ROCR's destructor sentinel, and
then firing the event interrupt — this is a faithful emulation of real CP
firmware behavior. The comment explaining the CAS rationale is particularly
valuable.

**The barrier bit fix in `on_cu_idle` is critical.** Without it, the
asynchronous dispatch path could overlap packets that the AQL barrier bit
requires to be serialized, causing cache invalidation races and scratch
memory collisions. The fix correctly applies the same `barrier_satisfied`
check that `handle_doorbell` already performs.

**ISA fixes continue to be correct and thorough.** The CDNA4 scratch addressing
fix (stop using s102:s103, use dedicated FLAT_SCRATCH register) and the SVE bit
fix (don't read VGPR when SVE=0) are both well-motivated by the RCCL persistent
kernel crash analysis. The `s_call_b64` offset fix (`PC + 4 + simm16*4` instead
of `PC + simm16*4`) is subtle — it matches `s_branch` behavior where the offset
is relative to the next instruction, not the current one.

**VMID threading is comprehensive — no missed paths found.** Checked the full
memory hierarchy: GpuMemory, L2Cache, L1VectorCache, L1ScalarCache,
ScalarMemPipeline, GlobalMemPipeline, ComputeUnitCore, CompletionTracker, and
CommandProcessor. All paths correctly thread vmid/process_id. The wavefront
stores `process_id_` set at dispatch time, and all instruction handlers access
it via `wf.process_id()`.

**This PR would still benefit from splitting for future changes of this scope.**
The ISA correctness fixes, VMID threading, daemon/RPC transport, and command
processor overhaul are largely independent concerns. The ISA fixes in particular
are standalone correctness improvements with zero risk of regression from the
daemon infrastructure.
