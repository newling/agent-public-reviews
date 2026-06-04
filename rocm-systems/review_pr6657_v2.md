# Review: PR #6657 — rocjitsu: Daemon mode, multi-process, ISA fixes (v2)

**Author**: Tony Gutierrez (@atgutier)
**Date reviewed**: 2026-06-04
**Previous review**: 2026-06-01
**PR**: https://github.com/ROCm/rocm-systems/pull/6657

> This is a review from an agent with an automatic prompt from the reviewer

## Changes since first review

The PR was force-pushed with 14 commits on 2026-06-04. Notable new commits
since our June 1 review:

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
- g++ 13.3.0 (Ubuntu 24.04)
- cmake 4.3.1
- Release build, no extra CXX flags
- AMD EPYC 9575F, Linux 6.8.0-38-generic

**Build**: Clean — all 316 targets compile, zero warnings.

**Command**: `ctest -j$(nproc) --output-on-failure`
**Test count**: 425 (up from ~400 in first review; 5 new RCCL daemon tests)
**Timing**: ~106s wall

**Stability**: Ran the full test suite 5 times on the PR branch:

| Run | Result |
|-----|--------|
| 1 | 425/425 passed |
| 2 | 423/425 — `HipVectorAddTest.CorrectResult` (SEGFAULT), `RocblasGemmTest.Rect_16x32x8` (Failed) |
| 3 | 425/425 passed |
| 4 | 425/425 passed |
| 5 | 425/425 passed |

**Develop baseline**: 0 failures (451 tests, 1 run completed; consistent with
first review's 0/3).

**Improvement from first review**: Failure rate dropped from 80% (4/5 runs) to
20% (1/5 runs). The remaining failure is the same pattern — different tests
fail each run, all pass in isolation. The SEGFAULT in `HipVectorAddTest`
points to memory corruption under parallel execution.

**GEMM performance**: `RocblasGemmTest.Square_4x4` takes **2.6s** on this
branch vs **1.2s** on develop (2.2x regression, unchanged from first review).

**RCCL daemon tests**: All 5 new tests pass reliably. They take ~37–41s each.
The interactive terminal hang from the first review appears resolved.

**CI status**: Linux build still fails. The detailed build error is not
surfaced in `gh run view --log-failed` (only the summary job is shown), but
likely caused by `MADV_POPULATE_WRITE` being used without `#ifdef` guards in
two files (see actionable item 2).

## Summary

Same four major capabilities as the first review. The new commits add RCCL
daemon test coverage, fix several ISA correctness bugs that were blocking RCCL
persistent kernels (scratch addressing, null indirect jump, `s_call_b64`
offset), and fix a deadlock in doorbell monitor shutdown.

## Actionable items

### 1. Flaky test failures under parallel execution (regression, improved)

The concurrency bug from the first review persists but is less frequent (1/5
vs 4/5). The SEGFAULT in `HipVectorAddTest` on one run suggests memory
corruption. All failing tests pass in isolation. Develop has 0 failures.

### 2. MADV_POPULATE_WRITE unguarded in 3 call sites (CI blocker)

`interposer.cpp:809` has the correct `#ifdef MADV_POPULATE_WRITE` guard.
Three other call sites use the constant without a guard:

- `remote_driver.cpp:448` — `syscall(SYS_madvise, mapped, length, MADV_POPULATE_WRITE)`
- `remote_driver.cpp:550` — same
- `simulated_driver.cpp:782` — same

`MADV_POPULATE_WRITE` requires Linux 5.14+ headers. The CI builder likely has
older headers. This is probably the CI build failure cause.

### 3. Fd leak on partial RPC recv failure (persists from v1)

**File**: `remote_driver.cpp:355–366`

After receiving the response header via `rpc_recv_msg` (which may deliver an
fd via SCM_RIGHTS in `received_fds[0]`), if the subsequent `rpc_recv_exact`
for the payload fails, `return -1` is hit without closing the received fd.

### 4. GEMM test performance regression (2.2x, persists from v1)

`RocblasGemmTest.Square_4x4`: 2.6s on PR branch vs 1.2s on develop. Likely
caused by the new two-phase dispatch model, completion tracker changes, or the
recursive mutex. Worth investigating whether this is expected overhead from
daemon infrastructure or an unintended regression.

### 5. KfdProcess public fields bypass mutex protection (persists from v1)

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

### 2. RPC request_id still not verified (persists from v1)

`request_id` is assigned in the client but the response's `request_id` is
never checked. Fine for single-threaded model but an assert would be cheap
insurance.

### 3. Socket path /tmp fallback TOCTOU risk (persists from v1)

The `/tmp/rocjitsu-<uid>` fallback directory could be pre-created by another
user. Consider `mkdtemp` or ownership verification.

### 4. Non-atomic static counter in L2 cache (new)

**File**: `l2_cache.cpp`

A `static uint64_t wb_count` is shared across L2 instances without atomic
access. In a multi-GPU configuration with multiple L2 instances, this is a
data race (undefined behavior). Impact is log-only — the counter is used for
debug output — but it's technically UB.

## Commentary

**RCCL daemon tests are a significant addition.** Five new tests
(AllReduce, AllGather, Broadcast, ReduceScatter, SendRecv) exercise the
multi-process daemon path with real RCCL collectives. These all pass reliably,
demonstrating that the daemon infrastructure works for its primary use case.

**ISA fixes are correct and thorough.** The `s_call_b64` offset fix makes it
consistent with `s_branch` (both use `PC + 4 + signext(SIMM16 * 4) - size_`).
The CDNA4 scratch addressing fix correctly uses per-lane swizzling
(`lane * scratch_lane_size`). DS CMPSWAP data0 → data1 fix verified across
all 10 arch targets.

**The doorbell monitor deadlock fix is well-targeted.** `unregister_queue`
previously joined the monitor thread while holding the queue mutex, but the
monitor thread needed the same mutex to exit. The fix restructures the
shutdown sequence.

**The interactive terminal hang from the first review is resolved.** Daemon
tests now pass from both interactive and non-interactive terminals.

**This PR would still benefit from splitting.** The ISA correctness fixes,
VMID threading, daemon/RPC transport, and command processor overhaul are
largely independent. The ISA fixes in particular are standalone correctness
improvements that could land immediately.

## Status of first-review findings

| Finding | Status |
|---------|--------|
| Flaky test failures (regression) | **Improved** — 1/5 vs 4/5 failure rate |
| CI build failure (MADV_POPULATE_WRITE) | **Persists** — 3 unguarded call sites |
| GEMM performance regression (2x) | **Persists** — 2.2x slower |
| Fd leak on partial RPC recv | **Persists** |
| KfdProcess public fields | **Persists** |
| CompletionTracker linear scan | **Persists** (not verified if changed) |
| request_id not verified | **Persists** (demoted to suggestion) |
| /tmp TOCTOU risk | **Persists** (demoted to suggestion) |
| L2 eviction vmid assumption | **Persists** (acknowledged in code comments) |
| recursive_mutex design | **Persists** (not re-investigated) |
| Daemon test terminal hang | **Resolved** |
| Stale processes/sockets | **Improved** (mkdtemp isolation, cleanup in TearDown) |
