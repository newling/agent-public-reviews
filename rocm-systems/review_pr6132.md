# Review: PR #6132 — [rocjitsu][WIP] Plugin directory structure proposal

**Author**: James Newling (@newling)
**Date reviewed**: 2026-06-05
**PR**: https://github.com/ROCm/rocm-systems/pull/6132

> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**Build environment**:
- clang 22.1.3 (ROCm 7.2.0 LLVM toolchain)
- cmake 4.2.3, Ninja generator
- No explicit build type (default)
- AMD EPYC 9575F, Linux 6.14.0-1018-oem

**Build**: Clean — all 328 targets compile. Zero errors, zero warnings.

**Command**: `ctest --test-dir ~/workspace/builds/rocm-systems-claudius -j6 --output-on-failure -E "DaemonTest|RcclDaemon|Large_2048|RocblasGemm|Rocminfo"`

**Result**: 497/498 pass (5.6s wall)

**Test count**: 540 registered tests total (excluding nothing). Of the 498
run, 497 pass. One test fails:

**`HookOrderingTest.FiveDispatchLifecycle`**: The test expects exactly one
`DISPATCH_EXECUTION_BEGIN` per dispatch and strictly ordered dispatch
lifecycles (dispatch N ends before dispatch N+1 begins). Both assumptions
are violated:
- Dispatch 5 fires `DISPATCH_EXECUTION_BEGIN` 6 times (10 total across
  5 dispatches instead of the expected 5). The hook at
  `command_processor.cpp:970` fires inside the `handle_doorbell` loop,
  which re-enters for the same dispatch_id each time a CU becomes
  available and yields backpressure. It fires once per re-entry, not
  once per dispatch lifecycle.
- Dispatches 2–5 begin execution before dispatch 1 ends, because
  `handle_doorbell` can start multiple dispatches within the same
  doorbell batch before any complete. The test's DAG edge assertions
  (`DISPATCH_EXECUTION_END(d=N) < DISPATCH_EXECUTION_BEGIN(d=N+1)`)
  fail for all sequential pairs.

This is a real bug: the `onAmdgpuDispatchExecutionBegin` hook fires at
the wrong granularity. It should fire exactly once per dispatch — when
the dispatch transitions from "parsed but waiting" to "workgroups being
placed." The current placement is inside a loop that re-enters on
backpressure, causing duplicate firings. The test correctly encodes the
expected contract.

## Summary

This PR (6.7k additions, 56 files) adds three capabilities to the
rocjitsu GPU emulator:

**1. Execution plugin system.** The existing `ExecutionPlugin` /
`ExecutionPluginGroup` interface (introduced in the develop branch with
a handful of hooks) is substantially expanded and relocated from
`vm/execution_plugin.h` to `vm/plugins/`. The new plugin API adds 14
hooks covering the full kernel dispatch lifecycle: packet processed,
dispatch execution begin/end, workgroup dispatched/completed, wavefront
dispatched/halted, before/after instruction execution, memory instruction
routing, VGPR/SGPR read notifications, and barrier resolution.

Per-wavefront plugin state is supported via `WavefrontState` (a virtual
base stored in a `mutable` vector on `Wavefront`). Each plugin gets a
slot index, assigned by the group on `add()`, for O(1) state lookup.

A sink system (`PluginSink`) decouples plugin output from stderr:
`StderrSink`, `StdoutSink`, `FileSink`, `StringSink` (for tests), and
`CompositeSink` (fan-out). Environment variables (`RJ_SINKS`,
`RJ_SINK_DIR`) configure output in production. Sink assignment is
managed by `ExecutionPluginGroup`, which builds a per-plugin composite
sink combining external sinks with optional per-plugin file sinks.

A `ProfiledExecutionPluginGroup` subclass adds adaptive-sampling hook
profiling with `sqrt(count/1000)` interval scaling.

**2. Race detection plugin.** A GPU data race detector that hooks into
the plugin system. The core detection algorithm lives in
`race_detector/core/` with no dependency on rocjitsu types, making it
testable in isolation. The rocjitsu adapter in `race_detector/plugin.cpp`
translates CU/wavefront events into the core API.

Detection covers three race classes:
- VGPR races: register read before pending global/LDS load completes
  (`s_waitcnt` insufficient)
- SGPR races: scalar register read before pending scalar load completes
- LDS races: cross-wave LDS access without intervening `s_barrier`

The detector uses per-byte counters for O(1) fast-path LDS validation,
with interval-based binary search as a fallback. VGPR tracking uses exec
mask awareness and byte-granularity masks for D16 instruction support.

Race reports include instruction traces with `==>` markers and wave/lane
annotations, using a per-wavefront 256-entry PC ring buffer and a
per-dispatch disassembly cache indexed by `(pc - base) / 4`.

**3. SIMD read notification and register-to-wave mapping.** To support
race detection on VGPR reads (which happen in bulk via `read_simd`), the
SIMD operand path gains a `notify_read` callback through
`SimdAccess::notify_read` → `simd_notify_read` (virtual on `Operand`).
Physical-to-wave reverse lookup arrays (`sgpr_to_wave_`,
`vgpr_to_wave_`) are populated at `dispatch_wf` time.

Additionally: DS transpose instruction AccVGPR fix (4 instructions),
CDNA4 device_id config correction, `amdgpu_get_marketing_name`
interposition, sparse checkout README note, and a performance benchmark
script (`run_perf_matrix.sh`).

## Actionable items

### 1. `onAmdgpuDispatchExecutionBegin` fires multiple times per dispatch

**File**: `command_processor.cpp:970`

The hook is placed inside the `handle_doorbell` dispatch loop, which
re-enters for the same `dispatch_id` on CU backpressure. Dispatch 5 in
the `FiveDispatchLifecycle` test fires it 6 times. The test at
`execution_plugin_test.cpp:562` correctly expects exactly 1.

*Fix*: Track whether the hook has already fired for the current
dispatch_id (e.g., a `bool execution_begun` on `DispatchEntry`) and
only fire on the first entry.

### 2. `detectors_` and `dispatch_disasm_` grow monotonically — no cleanup

**Files**: `race_detector/plugin.h:124-125`, `plugin.cpp:226-231`

`onAmdgpuWorkgroupDispatched` allocates a `RaceDetector` per workgroup
and a `DisasmCache` per dispatch. Neither is ever freed — no
`onAmdgpuDispatchExecutionEnd` or `onAmdgpuWorkgroupCompleted` override
cleans them up. For long-running daemon sessions with many kernel
dispatches, this leaks memory proportional to the number of dispatches ×
workgroups.

*Fix*: Override `onAmdgpuWorkgroupCompleted` to erase from `detectors_`
and override `onAmdgpuDispatchExecutionEnd` to erase from
`dispatch_disasm_`.

### 3. `DisasmCache::record` has a data race on the fast path

**File**: `race_detector/plugin.h:70-71`

The unlocked fast path reads `entries_[idx]` (calling `.empty()` on a
`std::string`) without holding the mutex, while another thread may be
concurrently writing to the same index at line 80. The `size_` atomic
protects against out-of-bounds access, but not against concurrent
string mutation. `std::string::empty()` is not atomic.

Additionally, `to_map()` (line 84) reads the entire `entries_` vector
without synchronization, racing with concurrent `record()` calls from
other CU threads.

*Fix*: Use `std::atomic<bool>` flags per entry, or move the `.empty()`
check inside the mutex, or use a concurrent data structure. For
`to_map()`, take the mutex or document that it's only safe to call
after all CU threads have stopped (which is the case in the race
handler, since it runs synchronously on the offending CU's thread —
but other CUs are still running).

### 4. `read_sgpr` hook fires unconditionally on every SGPR read

**File**: `compute_unit.h:326-330`

Every `read_sgpr` call checks `sgpr_to_wave_[reg_idx]` and fires
`onAmdgpuReadSgpr` if non-null. SGPR reads happen at very high
frequency — every scalar instruction reads 1-2 SGPRs, plus base
address computations, descriptor reads, etc. When plugins are empty,
the group loop is zero iterations, but `sgpr_to_wave_` is populated
for all allocated registers regardless of whether any plugin cares
about SGPR reads. The lookup and null check happen on every read.

*Fix*: Guard with `if (!plugin_group_->empty())` before the lookup,
or make the hook firing conditional on whether any plugin has overridden
`onAmdgpuReadSgpr`. The VGPR `notify_vgpr_read` path has the same
issue but is less hot because it only fires from `read_simd` (bulk
reads), not every individual lane read.

### 5. `amdgpu_get_marketing_name` returns empty string on driver lookup failure

**File**: `interposer.cpp:925-930`

When `drv` is null (driver lookup fails), the function returns `""`.
The real libdrm function returns `NULL` on failure. Callers that check
for NULL will incorrectly treat this as a valid (empty) name. While
the emulator controls all paths and presumably always has a valid
driver, returning `nullptr` would be more correct for library
interposition.

*Fix*: Return `nullptr` instead of `""` in the fallback path.

### 6. Plugin constructor uses `extern "C"` raw `new` without matching `delete`

**Files**: `logging/plugin.cpp:42`, `race_detector/plugin.cpp:362`

Both `createKernelLoggingPlugin()` and `createRaceDetectorPlugin()`
allocate with `new` and return a raw pointer. The caller wraps in
`std::unique_ptr` at `interposer.cpp:273-277`. This is fragile — the
`extern "C"` factory signature encourages callers to forget ownership.
If the factory were ever called from C code or without the unique_ptr
wrapping, the allocation leaks.

*Fix*: Return `std::unique_ptr<ExecutionPlugin>` from the factory
functions (dropping the `extern "C"`) or document the ownership
contract prominently.

## Suggestions

### 1. `ProfiledExecutionPluginGroup` is not thread-safe but lacks runtime enforcement

**File**: `profiled_execution_plugin_group.h:43`

The file comment says "NOT thread-safe: use only with num_threads=1"
but there is no runtime check. If someone enables profiling with
multiple CU threads, the `HookProfile` counters produce silently wrong
results (torn reads/writes on `count`, `total_ns`, etc.).

Consider adding `assert(num_threads == 1)` in `onInit()` or using
relaxed atomics for the counters.

### 2. `RaceDetectorPlugin` destructor writes to sink

**File**: `race_detector/plugin.cpp:145`

The destructor calls `sink().write(getSummary())`. During shutdown,
the sink may already be destroyed (the `ExecutionPluginGroup` owns
sinks via `owned_sinks_` and destroys them when the group is destroyed,
which may happen before or after individual plugin destruction
depending on `unique_ptr` destruction order within the `plugins_`
vector). Consider moving the summary output to `onShutdown()` instead.

### 3. `forEachActiveLane` could use `std::countr_zero` for sparse masks

**File**: `race_detector/core/dim3d.h:18-31`

The current implementation always iterates all 64 lanes, checking each
bit. For sparse exec masks (common during warp divergence), a
`popcount`/`countr_zero` loop would be faster. The full-mask fast path
only helps when every lane is active.

### 4. `Dim3d` constructor deletes default, but workgroup IDs are 1D in practice

**File**: `race_detector/core/dim3d.h:6-12`

`Dim3d` requires at least one argument (`Dim3d() = delete`), but all
call sites pass a single `wg_id` int: `Dim3d(static_cast<int>(wg_id))`.
The y and z components are always 0. This suggests the workgroup ID
should be a plain `uint32_t` in the detection API, with 3D coordinates
only in the reporting/formatting layer.

### 5. `RingBuffer` wraps at compile-time size but stores runtime `len`

**File**: `race_detector/plugin.h:23-36`

The ring buffer is fixed at 256 entries (template parameter). If a
kernel has more than 256 instructions between the memory operation and
the racy read, the conflict falls outside the trace window. This is
documented and handled (the "before trace window" message), but the
fixed size is invisible to the user. Consider making the size
configurable via environment variable for debugging complex kernels.

### 6. `run_perf_matrix.sh` uses `declare -A` (bash 4+) without version check

**File**: `scripts/run_perf_matrix.sh:67-68`

Associative arrays require bash 4.0+. The shebang is `#!/usr/bin/env bash`
which may resolve to bash 3.x on some systems (notably older macOS).
Adding `if ((BASH_VERSINFO[0] < 4)); then echo "bash 4+ required"; exit 1; fi`
would prevent confusing failures.

### 7. DS transpose AccVGPR fix is mechanically correct but untested

**File**: `isa/arch/amdgpu/cdna4/ds.cpp:4283,4308,4333,4358`

All four DS transpose read instructions (`DsReadB64TrB4Ds`,
`DsReadB96TrB6Ds`, `DsReadB64TrB8Ds`, `DsReadB64TrB16Ds`) gain
`(inst_.acc ? 256u : 0u)` to route AccVGPR destinations. This is the
same pattern used elsewhere for AccVGPR addressing. No test covers
the `acc=true` path for these specific instructions.

## Commentary

**The plugin architecture is well-structured.** The separation between
the abstract `ExecutionPlugin` interface, the group delegation layer,
and concrete plugin implementations follows a clean extension pattern.
The slot-index-based per-wavefront state avoids dynamic casts and gives
O(1) access. The sink system is a genuine improvement over direct stderr
writes — `StringSink` makes plugin output testable without stderr
scraping, which is notoriously fragile.

**The race detector's core algorithm is cleanly decoupled from rocjitsu.**
The `race_detector/core/` directory has zero rocjitsu `#include`s. The
`plugin.cpp` adapter translates between rocjitsu types (physical
register indices, `VectorMemState`, `ScalarMemState`) and the core's
abstract events. This means the core can be tested with `RaceTestBuilder`
without spinning up the full simulation, which is reflected in the
thorough unit test suite (78 test cases covering VGPR, SGPR, LDS, D16,
DTL, exec mask, multi-workgroup, and mixed counter scenarios).

**The SIMD read notification pathway is the most invasive change.** Adding
`notify_read` to the SIMD operand hot path means every vector instruction
that reads VGPRs goes through an additional virtual call and
`sgpr_to_wave_`/`vgpr_to_wave_` lookup. The `notify_vgpr_read` call in
`read_simd` (simd_glue.h:44) fires on every bulk VGPR read — this is
the inner loop of instruction execution. The no-plugin case iterates an
empty vector (zero work), but the virtual dispatch and lookup overhead
remains. For production workloads without race detection, this is dead
weight in the hottest path.

**The `DisasmCache` concurrency model is fragile.** The lock-free fast
path is a performance optimization (avoid mutex on every instruction),
but the correctness argument relies on `std::string` assignment being
atomic with respect to `.empty()` checks, which it is not. The
multi-CU case (where two CUs execute the same kernel and both call
`record()` on the same DisasmCache) is the realistic scenario where
this matters. The consequence is benign in practice (at worst, the
disassembly string is read in a partially-constructed state and the
trace output is garbled), but it's a latent UB that sanitizers will flag.

**The `FiveDispatchLifecycle` test failure reveals a real hook placement
issue.** The dispatch execution begin/end hooks are meant to bracket the
active execution of a dispatch (from first workgroup placement to last
workgroup completion). But `handle_doorbell` can re-enter the dispatch
loop for the same dispatch_id multiple times as CUs become available.
Placing the hook inside this loop means it fires per re-entry, not per
lifecycle transition. This is the kind of bug that the test was designed
to catch — the test's DAG assertions encode the intended lifecycle
contract, and the implementation doesn't meet it.

**The PR description says `[NEEDS UPDATING]` and `[WIP]`.** The commit
message and code are production-quality, but the PR body still contains
the original proposal text. The mismatch between the WIP label and the
substantial, tested implementation is confusing for reviewers. Either
update the description to reflect the actual content or split into a
non-WIP PR.
