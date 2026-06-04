# Re-review #2: PR #6657 -- rocjitsu: Add daemon and initial support for multiple processes

**Author**: Tony Gutierrez (@atgutier)
**Date reviewed**: 2026-06-04
**PR**: https://github.com/ROCm/rocm-systems/pull/6657
**Previous reviews**: review_pr6657.md (2026-06-01), review_pr6657_2.md (2026-06-04)

> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**Build environment**:
- g++ 13.3.0 (Ubuntu 24.04)
- cmake 4.3.1
- Release build, no extra CXX flags
- AMD EPYC 9575F, 128 HW threads, Linux 6.8.0-38-generic

**Command**: `ctest --test-dir ~/workspace/builds/rocm-systems-augustus -j128 --output-on-failure`
**Timing**: ~108s wall (PR) vs ~93s wall (develop)
**Result**: Flaky failures persist under parallel execution

Three runs on PR branch (`-j128`):

| Run | Total | Failed | Failing tests |
|-----|-------|--------|---------------|
| 1   | 425   | 1      | RocblasGemmFuzz.Iter4 |
| 2   | 425   | 1      | HipVectorAddTest.CorrectResult (SEGFAULT) |
| 3   | 425   | 1      | RocblasGemmTest.Square_4x4 |

Develop baseline: 451 tests, 0 failures in 3 runs at `-j128`.

All PR-failing tests pass 5/5 in isolation. A different test fails each run, spanning GEMM, HIP vector_add, and fuzz tests, confirming a systemic concurrency issue in shared infrastructure.

**GEMM performance**: RocblasGemmTest.Square_4x4 takes ~2.4s on PR vs ~1.6s on develop (1.5x slower). This is an improvement from the ~2x regression observed in the first review.

**Daemon/RCCL tests**: All 10 daemon and RCCL tests pass reliably. This is a significant improvement from the first review where daemon tests hung from interactive terminals.

## Summary

This is a review of the force-pushed PR that adds four major features: (1) daemon mode with Unix socket RPC, (2) command processor overhaul with per-dispatch completion tracking, (3) ISA correctness fixes across 10 architecture targets, and (4) VMID-aware memory subsystem. The 14 new commits since the first review add doorbell deadlock fixes, CDNA4 scratch addressing, queue-inactive signal firing, RCCL daemon test support, and cleanup of stale fields.

## Actionable items

### 1. Flaky test failures under parallel execution (regression, persists from review 1)

**Severity**: Bug
**Status**: Persists

Different tests segfault or fail under `-j128` each run. The SEGFAULT in run 2 (HipVectorAddTest) is particularly concerning -- this suggests memory corruption or use-after-free rather than a logic error. The tests all pass in isolation. Develop has zero failures under the same conditions.

The most likely source is the interposer's shared state: multiple test processes run concurrently and each one LD_PRELOADs the same interposer .so. The `InterposerContext` singleton is per-process (static storage), but if the interposer's `get_or_create()` path races with fork() from another test's daemon fixture, or if stale `config_path` files from a daemon test leak into a non-daemon test's environment, the VM initialization can corrupt state. Worth checking whether the daemon tests' `XDG_RUNTIME_DIR` cleanup is airtight.

### 2. MADV_POPULATE_WRITE unguarded in remote_driver and simulated_driver (persists from review 1)

**Severity**: Bug (CI build failure)
**File**: `remote_driver.cpp`, lines 448 and 550
**File**: `simulated_driver.cpp`, line 782

The interposer.cpp correctly guards `MADV_POPULATE_WRITE` with `#ifdef` (line 809), but these three other call sites use the constant without any guard. They will fail to compile on systems with older kernel headers, which is exactly the CI environment that originally triggered the build failure.

### 3. S_CALL_B64 offset calculation change -- needs ISA spec verification

**Severity**: Concern (new)
**File**: all sopk.cpp files across all 10 architectures (cdna1-4, rdna1-4)

The S_CALL_B64 instruction implementation changes from:
```cpp
wf.pc = wf.pc + static_cast<int64_t>(offset) * 4 - size_;
```
to:
```cpp
wf.pc = wf.pc + 4 + static_cast<int64_t>(offset) * 4 - size_;
```

The added `+ 4` is applied uniformly across all 10 architectures. The ISA spec says the offset is relative to the PC of the next instruction, and `issue_instruction` already adds `inst_size` to pc after execution (compute_unit.cpp line 315: `active->pc += inst_size`). So the old formula `pc + offset*4 - size_` would compute `(pc + offset*4 - size_) + size_ = pc + offset*4` after the caller advances PC. The new formula computes `pc + 4 + offset*4` after caller advance, which adds an extra 4 bytes.

For GFX9 (CDNA1-4), S_CALL_B64 is a 4-byte instruction so `size_ == 4` and the old formula gives `pc + offset*4`, while the new formula gives `pc + 4 + offset*4 = pc + offset*4 + 4`. For GFX10+ (RDNA1+), this instruction is also 4 bytes. The `+ 4` seems to intend "from the start of the next instruction", which would make the formula `(pc_of_next_inst) + offset*4 = (pc + 4) + offset*4`. Whether this is correct depends on whether the ISA spec's `simm16` offset is relative to the S_CALL instruction itself or the following instruction. Since the return address stored in `sdst` is `pc + size_` (the next instruction), and the AMD ISA docs say "PC = PC + signext(SIMM16 * 4)", the offset is typically relative to the current instruction's PC. If so, the old formula (without `+ 4`) was correct, and this change introduces a bug in function call offsets. This needs ISA spec verification.

### 4. fire_signal: non-atomic read-modify-write on signal value via separate load + store

**Severity**: Concern (new)
**File**: `completion_tracker.cpp`, `fire_signal`, lines 187-193

```cpp
old = static_cast<int64_t>(std::atomic_ref<uint64_t>(*sig_ptr).load(std::memory_order_relaxed));
new_val = static_cast<uint64_t>(old - 1);
std::atomic_ref<uint64_t>(*sig_ptr).store(new_val, std::memory_order_release);
```

This is a load-compute-store sequence, not an atomic decrement. If two dispatches for the same signal fire concurrently (theoretically possible in multi-queue scenarios), one decrement would be lost. The code should use `fetch_sub(1)` instead. In practice, completion signals fire in submission order per queue and the CP holds `hw_queue_mutex_` during this path, so concurrent fires on the same signal would require two different queues dispatching to the same signal (unlikely but not impossible).

### 5. Fd leak on partial RPC recv failure (persists from review 1)

**Severity**: Bug (resource leak)
**File**: `remote_driver.cpp`, `send_ioctl` method

After `rpc_recv_msg` receives a response header with an `SCM_RIGHTS` fd, if the subsequent `rpc_recv_exact` for the payload fails, the received fd leaks.

### 6. flush_all passes single vmid for all dirty lines (persists from review 1)

**Severity**: Concern
**File**: `l2_cache.cpp`, `flush_all` and `ensure_line` eviction

The L2 `flush_all(vmid)` writes back all dirty lines using the caller's vmid for page table translation. In a multi-process scenario, dirty L2 lines could belong to different processes (different VMIDs). The code comment at line 62 notes this is correct because dirty lines only come from K$ writeback (same process), but this invariant is fragile. The `writeback_line` method (line 143) can set `dirty = true` for non-CC mtypes, so K$ writebacks to non-CC pages do accumulate dirty lines. If two processes have overlapping GPU VAs mapped to different physical pages, flushing with the wrong vmid would translate through the wrong page table and corrupt the wrong physical page. Consider storing the originating vmid in the cache tag.

## Suggestions

### 1. CompletionTracker linear scan (persists from review 1)

**File**: `completion_tracker.cpp`, `notify_wg_complete`, lines 23-36

The O(n) scan across all queues and entries is correct and adequate for current workloads. If dispatch throughput becomes a concern (many concurrent dispatches across many queues), restoring a dispatch_id-indexed map would help.

### 2. s_memrealtime / s_memtime use thread_local static counters

**File**: `execute_shared.h`, `execute_s_memrealtime_smem` and `execute_s_memtime_smem`

```cpp
static thread_local uint64_t counter = 0;
counter += 100;
```

These thread_local counters increment by 100 per call. This works for unblocking code that polls these instructions but doesn't correlate with actual simulation time. If the CU's `cycle_counter_` were accessible from the instruction execute body, it would provide a more realistic approximation. Not a correctness issue, just a quality-of-implementation note.

### 3. recursive_mutex inner lock_guard in notify_wg_complete (persists from review 1)

`notify_wg_complete` in command_processor.cpp acquires `hw_queue_mutex_` (line 477), then calls `completion_->notify_wg_complete()` which calls `drain_completions()`. The `on_cu_idle` path (line 486) also acquires the same mutex. Since `notify_wg_complete` is only called from paths that hold the lock, the inner `lock_guard` succeeds trivially due to the recursive mutex. If the design can guarantee that `notify_wg_complete` is never called without the lock held, the mutex could remain as a regular `std::mutex` and the inner lock_guard could be removed.

### 4. DaemonTest uses SIGKILL (persists from review 2)

**File**: `daemon_test.cpp`

The daemon is killed with `SIGKILL` in TearDown, preventing graceful shutdown. A SIGTERM with timeout would exercise the daemon's shutdown path.

## Commentary

**ISA correctness fixes are correctly and consistently applied across all architectures.** The DS CMPSWAP data0->data1 fix is verified in CDNA1-4 and RDNA1-4 + RDNA4 VDS variants (10 targets total). The F64 atomic elem_size fix in semantics.py now correctly detects 64-bit types via suffix matching (`is_64bit = '64' in tsuf`) in addition to the `is_x2` flag, catching cases like `FLAT_ATOMIC_ADD_F64` which previously used elem_size=4. The buffer cache instruction remapping from `dcache_inv` to `gl1_inv` (and `BUFFER_WBL2` to `gl2_wb`) is correct -- the old mapping routed these through the scalar cache path instead of the vector + L2 path.

**VMID threading is thorough.** Every memory access path now carries explicit vmid: instruction fetch (compute_unit.cpp issue_instruction), scalar memory pipeline (memory_pipeline.cpp), vector memory pipeline (memory_pipeline.cpp), L1 scalar cache (l1_scalar_cache.cpp), L1 vector cache (l1_vector_cache.cpp), L2 cache (l2_cache.cpp), HBM controller (hbm_controller.h), and GPU memory (gpu_memory.h). The `GpuMemory::translate` method uses `std::shared_lock` on both the vmid table and per-process page table mutexes, allowing concurrent reads. The `effective_mtype` function correctly combines instruction and PTE mtypes with the "most restrictive wins" rule matching real hardware behavior.

**CDNA4 scratch addressing fix is correct.** The old formula `scratch_base + vaddr + saddr + offset` did not account for per-lane swizzling. The new formula `scratch_base + lane * scratch_lane_size + vaddr + saddr + offset` correctly gives each lane its own private segment region, matching the architected flat scratch model on GFX940/CDNA4. The `sve` (scratch VGPR enable) field is checked via `if constexpr (requires { inst.sve; })` which is a clean way to handle the CDNA4-only field without breaking other architectures.

**Queue-inactive signal mechanism is well-designed.** The `fire_queue_idle_signal` correctly uses CAS to write the idle status only when the current value is 0, preventing clobbering of ROCR's destructor sentinel (0x8000000000000000). The periodic re-broadcast of HQD idle every ~10ms in the doorbell poll loop (lines 350-358) handles the race where a process creates an event after the non-empty to empty transition.
