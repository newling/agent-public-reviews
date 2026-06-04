# Review: PR #6657 — rocjitsu: Daemon mode, multi-process, ISA fixes (v2)

**Author**: Tony Gutierrez (@atgutier)
**Date reviewed**: 2026-06-04
**PR**: https://github.com/ROCm/rocm-systems/pull/6657

> This is a review from an agent with an automatic prompt from the reviewer

## Changes since v1 review

The PR was force-pushed with 14 commits on 2026-06-04. Notable additions:

- Fix CDNA4 scratch addressing (stop clobbering user SGPRs s102:s103)
- Fix three ISA correctness bugs causing RCCL persistent kernel crash
- Fix `s_call_b64` offset calculation (was missing `+ 4` that `s_branch` has)
- RCCL daemon tests (AllReduce, AllGather, Broadcast, ReduceScatter, SendRecv)
- Fire queue-inactive signal on HQD idle
- Fix doorbell monitor join deadlock in `unregister_queue`
- Fix RCCL socket bind
- Remove unused `owner_process_id` from `HwQueueState`

## Tests

**Build environment**:
- clang 22.1.3 (LLVM)
- cmake 4.3.1
- Release build, Ninja generator
- AMD EPYC 9575F, Linux 6.8.0-38-generic
- Separate clean build directories per branch (no shared deps)

**Build**: Clean — all 351 targets compile (clang). Zero errors.

**Stability** (`ctest -j128`, excluding Large_2048x2048 and RcclDaemon):

| Run | develop (450 tests) | PR branch (419 tests) |
|-----|--------------------|-----------------------|
| 1 | passed | passed |
| 2 | passed | passed |
| 3 | passed | passed |
| 4 | passed | passed |
| 5 | passed | passed |

Both branches **5/5 clean**. The PR branch registers 31 fewer tests than
develop (and adds 10 new daemon/RCCL tests). The dropped tests:

1. **Binary translator / code object patcher** (10 tests):
   `BinaryTranslatorE2E.*`, `CodeObjectPatcher.*`,
   `KernelDescriptorTranslator.*`. May have been intentionally excluded
   from the build as unrelated to this PR's scope.

2. **SIMD util tests** (9 tests): `UtilSimd.*`, `VAddSimdBenchmark.*`.

3. **HIP test variants** (4 tests): `HipMemcpyTest.LargeCopy_16MB`,
   `HipMemcpyTest.LargeCopy_256MB`, `HipMemcpyTest.ReuseAfterFree`,
   `BfeRegressionTest.ThreadIdxY`. The core HIP memcpy and vector-add tests
   still exist on both branches — only these specific variants are missing.

4. **Raw binary ctest entries** (several): develop registers both the raw
   binary name (e.g., `hip_vector_add_test`) and gtest-discovered names
   (e.g., `HipVectorAddTest.CorrectResult`). The PR only registers the
   gtest-discovered names. This is a cosmetic difference, not lost coverage.

**GEMM performance** (3 runs each, isolated):

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| develop | 1.22s | 1.22s | 1.22s |
| PR branch | 2.22s | 2.17s | 2.16s |

**1.8x regression**. Root cause analysis below.

**RCCL daemon tests**: All 5 pass reliably (~30s each). Each test spawns a
daemon + 2 RCCL ranks via `popen`. The 30s runtime is dominated by emulator
execution — the same dispatch-loop regression that causes the GEMM slowdown
(see actionable item 2) affects these tests equally.

**CI status** (run 26964712189, from latest push 2026-06-04T16:16:41Z):
Linux build fails. Confirmed from CI build logs:

```
remote_driver.cpp:448:44: error: 'MADV_POPULATE_WRITE' was not declared in this scope
remote_driver.cpp:550:44: error: 'MADV_POPULATE_WRITE' was not declared in this scope
simulated_driver.cpp:782:50: error: 'MADV_POPULATE_WRITE' was not declared in this scope
```

No other compile errors. See actionable item 1.

## Summary

This PR (9.4k additions, 165 files) adds four major capabilities:

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
cache instruction remapping, `s_memrealtime` implementation, CDNA4 scratch
addressing, `s_call_b64` offset.

**4. VMID-aware memory.** Every memory subsystem interface gains an explicit
`uint32_t vmid` parameter (default 0 for backward compatibility). The ambient
`set_active_vmid()` pattern is removed. All flat/mubuf/smem instructions now
pass `wf.process_id()` as the VMID through the entire cache hierarchy.

## Actionable items

### 1. 23 tests dropped from develop (regression)

The PR branch registers 23 fewer meaningful tests than develop (excluding
cosmetic raw-binary-entry duplicates). These need to be restored or
accounted for:

- **Binary translator / code object patcher** (10): `BinaryTranslatorE2E.*`,
  `CodeObjectPatcher.*`, `KernelDescriptorTranslator.*`
- **SIMD util tests** (9): `UtilSimd.*`, `VAddSimdBenchmark.*`
- **HIP memcpy variants** (3): `HipMemcpyTest.LargeCopy_16MB`,
  `HipMemcpyTest.LargeCopy_256MB`, `HipMemcpyTest.ReuseAfterFree`
- **BFE regression** (1): `BfeRegressionTest.ThreadIdxY`

### 2. MADV_POPULATE_WRITE unguarded in 3 call sites (CI blocker)

`interposer.cpp:809` has the correct `#ifdef MADV_POPULATE_WRITE` guard.
Three other call sites use the constant without a guard:

- `remote_driver.cpp:448` — `syscall(SYS_madvise, mapped, length, MADV_POPULATE_WRITE)`
- `remote_driver.cpp:550` — same
- `simulated_driver.cpp:782` — same

`MADV_POPULATE_WRITE` requires Linux 5.14+ headers. The CI builder has older
headers. This is the confirmed CI build failure cause.

### 2. GEMM / emulation performance regression (1.8x)

`RocblasGemmTest.Square_4x4`: 2.18s on PR branch vs 1.22s on develop. Three
compounding causes identified:

**a) Primary — `cu->activate()` removed from the synchronous dispatch loop.**
On develop, `handle_doorbell` has a tight inner loop: dispatch workgroups →
activate CUs → drain completions → repeat. The PR removes the inline
`cu->activate()`, relying on `on_cu_idle` callbacks. But in functional mode
(quantum=0), workgroups get dispatched to CUs but never executed in the tight
loop — execution only happens at the bottom of `handle_doorbell`. This
serializes work into many more outer-loop iterations.

*Fix*: restore `cu->activate()` inside the inner dispatch loop for functional
mode (quantum=0). The `on_cu_idle` path is correct for daemon mode
(quantum>0).

This regression also affects RCCL daemon tests (~30s each). Fixing it should
reduce their runtime proportionally.

**b) Linear scan replaces O(1) lookup in `CompletionTracker::notify_wg_complete`.**
On develop, `dispatch_queue_map_` provides O(1) lookup of which queue a
dispatch belongs to. The PR removes it entirely and does a nested linear scan
over all queues and entries.

*Fix*: restore `dispatch_queue_map_`.

**c) Byte-at-a-time memory reads with per-byte locking.**
`read_gpu_u64` calls `read8` eight times, each acquiring two `shared_lock`s
(vmid mutex + page table mutex) — 16 lock acquisitions per u64 read. The
command processor calls `read_gpu_u64` extensively in `fetch_from_queue` and
`process_aql_packet`.

*Fix*: use `memory_->read64(va, vmid)` directly instead of 8× `read8`.

### 3. Fd leak on partial RPC recv failure

**File**: `remote_driver.cpp:355–366`

After receiving the response header via `rpc_recv_msg` (which may deliver an
fd via SCM_RIGHTS in `received_fds[0]`), if the subsequent `rpc_recv_exact`
for the payload fails, `return -1` is hit without closing the received fd.

### 4. KfdProcess public fields bypass mutex protection

**File**: `kfd_process.h`

`alloc_mutex_` and `page_table_mutex_` exist but most fields (including
`allocations_`, `next_handle_`, queues, events) remain public (lines 34–170).
The empty `private:` section at line 173 suggests encapsulation was deferred.
Callers can bypass mutexes by accessing fields directly.

## Suggestions

### 1. Socket path length not validated

**File**: `transport.cpp:29,54`

`endpoint.copy(addr.sun_path, sizeof(addr.sun_path) - 1)` silently truncates
if the endpoint string exceeds `sun_path` capacity (typically 107 chars). With
long `XDG_RUNTIME_DIR` paths or usernames, this could silently connect to the
wrong socket. An assertion or error on overflow would catch this.

### 2. RPC request_id not verified

`request_id` is assigned in the client but the response's `request_id` is
never checked. Fine for single-threaded model but an assert would be cheap
insurance.

### 3. Socket path /tmp fallback TOCTOU risk

The `/tmp/rocjitsu-<uid>` fallback directory could be pre-created by another
user. Consider `mkdtemp` or ownership verification.

### 4. Non-atomic static counter in L2 cache

**File**: `l2_cache.cpp`

A `static uint64_t wb_count` is shared across L2 instances without atomic
access. In a multi-GPU configuration with multiple L2 instances, this is a
data race (undefined behavior). Impact is log-only — the counter is used for
debug output — but it's technically UB.

## Commentary

**ISA fixes are correct and thoroughly applied.** The `s_call_b64` offset fix
makes it consistent with `s_branch` (both use
`PC + 4 + signext(SIMM16 * 4) - size_`). The CDNA4 scratch addressing fix
correctly uses per-lane swizzling (`lane * scratch_lane_size`). DS CMPSWAP
data0 → data1 fix verified across all 10 arch targets.

**RCCL daemon tests are a significant addition.** Five new tests exercise the
multi-process daemon path with real RCCL collectives. These demonstrate that
the daemon infrastructure works for its primary use case.

**The doorbell monitor deadlock fix is well-targeted.** `unregister_queue`
previously joined the monitor thread while holding the queue mutex, but the
monitor thread needed the same mutex to exit. The fix restructures the
shutdown sequence.

**VMID threading is thorough.** Every memory access path has been updated:
instruction fetch, scalar memory, vector memory, cache hierarchy (L1 scalar,
L1 vector, L2), completion tracker flushes, and command processor GPU reads.
The `vmid = 0` defaults maintain backward compatibility.

**This PR would still benefit from splitting.** The ISA correctness fixes,
VMID threading, daemon/RPC transport, and command processor overhaul are
largely independent. The ISA fixes in particular are standalone correctness
improvements that could land immediately.
