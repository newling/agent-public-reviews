> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#6962](https://github.com/ROCm/rocm-systems/pull/6962) — `feat(rocjitsu): add functional CU dispatch pool`

**Commit reviewed:** `66879c9a3d5a17c31b5a68dbc9ef93e3ea1da2ea` (`fix(rocjitsu): harden pooled dispatch`)

**Review mode:** Comment-aware final follow-up. I reviewed the changes since previously reviewed head `61042636cf9b`, rechecked every prior actionable item, independently evaluated the latest reviewer concern about cross-CP pool serialization, and performed a fresh contract pass over every changed production file.

Clang 23 Release build passed; the complete `rocjitsu_tests` binary passed 3,804 tests with 2 expected skips and 1 disabled test, the focused pool/fan-out selection passed 59/59, its concurrency-sensitive subset passed 2,500/2,500 executions over 100 repetitions, the GCC 13 ThreadSanitizer selection passed 33/33 with no report, and branch-diff pre-commit plus `git diff --check` passed.

At review time every visible non-skipped GitHub check was green, including Release, ASan/UBSan, GCC UBSan, TSan, pre-commit, and the gfx94X, gfx950, and gfx125X package builds.

## Summary

The new commit addresses all four actionable findings from the previous review. A completed worker batch now refills CU capacity before yielding, paused waves are excluded from the pooled runnable set and have an explicit path back to the CP-owned driver on resume, the one-thread pool path now uses the same complete-batch exception machinery as the worker path, and plugin callback serialization no longer changes CU execution concurrency. Each fix is narrow and accompanied by a direct regression.

At a high level, the PR now has a coherent ownership model. The SoC owns one bounded host-thread pool; each command processor decides which of its CUs are due; each pool task advances exactly one CU for at most one functional quantum; and the command-processor thread applies queue, completion, cache-publication, and cross-CU effects after the batch rejoins. SPIs remain responsible for placement rather than owning host threads, CLOCKED mode remains on its existing driver, and XCD fan-out retains XCD-local command processors and caches.

For the production gfx950 topology, one SoC contains eight XCDs; each XCD has one CP, four SE/SPI placement domains, and 36 CUs. The pool does not execute SEs or SPIs: a CP gathers runnable CUs across all four of its SEs and submits CU-quantum tasks. This is the important improvement over the earlier per-SPI version, which limited one batch to one SE and retained a separate pool for every SPI.

```text
Modeled GPU hierarchy:    SoC -> XCD -> CP -> SE/SPI -> CU -> wavefronts
Host execution overlay:  SoC -> shared CPU pool -------> CU quantum
```

This passes the central reasonableness test for the design: changing the host execution width does not change who owns simulator state or where global state transitions occur. The worker pool is an execution mechanism below the existing semantic scheduler, rather than a second scheduler competing with it. I did not find a remaining issue that should block this PR.

## Actionable items

None.

## Suggestions

### 1. Remove the remaining plugin-to-pool lifecycle coupling

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/soc.cpp:83-110`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.h:214-220`

Now that `requires_serial_hot_hooks()` no longer changes dispatch concurrency, replacing the plugin group does not require recomputing dispatch policy. `SoC::set_plugin_group()` nevertheless calls `apply_dispatch_threads()`, which constructs a replacement pool whenever the configured count exceeds one, and `CommandProcessor::set_plugin_group()` calls a now-idempotent `set_dispatch_threads(dispatch_threads_)`. Removing those calls would finish separating callback policy from executor lifetime and would make the `LivePluginReplacementPreservesPoolDuringActiveDispatch` name literally true rather than preserving only the configured count and scheduling state.

### 2. Continue consolidating queue advancement

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:1865-1955,2823-3002`

Using the existing `process_queues()` helper for the post-batch refill is a good improvement and directly fixes the lost-work case. Queue advancement is still partly duplicated between `on_cu_idle()`, `process_queues()`, and the main doorbell loop. A later cleanup could express dispatch, backpressure, non-kernel completion, and predecessor blocking through one transition helper so future packet types and execution drivers cannot drift apart.

### 3. Make the host-acceleration boundary explicit

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/cpu_dispatch_pool.h:29-42`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:109-121,188-224`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/soc.h:196-220`

The topology objects model GPU structure—XCDs, CPs, SEs/SPIs, CUs, caches, wavefronts—whereas `CpuDispatchPool`, `dispatch_threads`, `pool_driven`, and functional quanta are host execution machinery. The names partly communicate that distinction, but placing the pool on `SoC` and the driver flag on `ComputeUnitCore` can make the knobs look like modeled hardware properties.

Add an explicit contract near the pool and configuration documentation: these controls affect host scheduling and performance only; they are not GPU resources, do not model hardware dispatch width or timing, and should preserve the observable result for race-free workloads. Also describe `functional_quantum` as a number of CU `step()` iterations, not “instructions”: one `step()` can issue one instruction for every runnable wavefront resident on that CU.

### 4. Document the two concurrency layers and their non-multiplicative composition

**Related stacked PR:** [ROCm/rocm-systems#10074](https://github.com/ROCm/rocm-systems/pull/10074), `emulation/rocjitsu/docs/configuration.md`

The current checked-in documentation accurately explains that `num_threads` creates Simdojo/XCD partitions, but the public `cpu_dispatch_threads` documentation lives in #10074 and describes the two controls independently. It should state that `cpu_dispatch_threads=N` means one SoC pool with `N-1` retained workers plus the currently calling CP thread; actual width is bounded by runnable CUs in that CP's batch. Same-SoC CP batches are serialized by `CpuDispatchPool::run_mutex_`, so `num_threads * cpu_dispatch_threads` is not the CU-execution width. Different SoCs own different pools and can multiply the total host-worker budget. A short four-case table for `(num_threads, cpu_dispatch_threads) = (1,1), (1,N), (X,1), (X,N)` would prevent the most likely misunderstanding.

| `num_threads` | `cpu_dispatch_threads` | Effective behavior |
|---:|---:|---|
| 1 | 1 | One engine partition and serial CU execution. |
| 1 | N | One CP event at a time; up to N runnable CUs from that CP execute concurrently. |
| X | 1 | Whole-XCD engine partitions can execute concurrently; CU work within each partition remains serial. |
| X | N | CP control paths can run on X partitions, but one same-SoC CP batch at a time uses up to N CU execution threads. |

The same stacked documentation still describes the older `soc_dispatch` design that moved foreign-XCD SPIs/CUs under a primary CP. Current `develop` uses ordered XCD-local fan-out instead, so #10074 needs to be rebased and that section rewritten or removed before the controls are exposed.

### 5. Track concurrent CP submissions to the shared pool as follow-up work

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/cpu_dispatch_pool.h:66-112,184-200`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:1995-2039`

The latest reviewer comment correctly identifies the remaining performance boundary. The shared pool has one set of current-batch pointers, counters, results, and exception state, so `run_mutex_` serializes whole calls. With `num_threads > 1`, CP control paths can run on separate XCD partitions, but only one same-SoC CP's CU batch can execute through the pool at a time. Sparse fan-out—such as eight CPs each holding one runnable CU—can therefore use one CU execution thread where a multi-producer pool could use eight.

This is not a correctness objection to the bounded first implementation, and it should not be expanded in this already-large PR. Add a TODO explaining the limitation and track a follow-up that moves batch state into per-submission objects and lets one shared worker queue consume CU tasks from multiple CPs fairly while preserving each CP's independent join, results, and exception propagation.

### 6. Remove or activate unused scheduling state

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:75-84`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/dispatch_entry.h:178-183,455-470`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/spi.h:147-161`

`FunctionalQuantumResult::yielded` remains write-only outside its direct unit assertions, `DispatchEntry::blocks_following` is not a scheduler input, `HwQueueState::implicit_barrier_next` is read but never written, and `ShaderProcessorInput::has_active_cus()` has no caller. Removing these fields/helpers or making them part of the centralized scheduling transition would make the state model easier to extend.

### 7. Keep one canonical L2 inventory for completion publication

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/completion_tracker.h:31-65`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/completion_tracker.cpp:162-173`

`CompletionTracker` receives an explicit CP L2 list and also rediscovers L2s through every CU, deduplicating their union with a `std::set` on every completion. The safety goal—publish every local cache only after worker rejoin—is correct. A single immutable topology-owned L2 inventory would remove the runtime reconciliation and avoid two sources of truth as new topology paths are added.

## Commentary

The new resume callback is the right shape for the pooled ownership boundary: the CU receives the thread-safe external wakeup, but the callback hands scheduling back to the CP instead of attempting to revive the disabled per-CU driver. Using `has_runnable_wfs()` consistently also restores the serial path's quiescence semantics without losing resume events.

The plugin policy is now aligned with merged PR #8706. Hot hooks may run concurrently and can opt into the plugin group's callback mutex; that callback choice no longer silently disables the worker pool. The worker/CP callback placement remains appropriate: instruction-level hooks execute where the instruction executes, while workgroup completion and cluster-barrier resolution are deferred until the CP has rejoined the batch.

The PR description should be refreshed before merge: it still says that the change preserves a “serial plugin policy” and that unsafe plugin combinations clamp execution to one dispatch thread, which is no longer true after `66879c9a`.

The shared pool's `run_mutex_` continues to serialize batches submitted by different XCD command processors. That is a reasonable first implementation because it enforces one SoC-wide host-thread budget and keeps CP ownership intact. It may leave performance on the table for small fan-out shards, but that is a measurement-driven follow-up rather than a correctness objection to this core PR.

The concrete reason for the mutex is visible in the pool layout: `tasks_`, `task_data_`, `result_data_`, `task_count_`, `next_task_`, `remaining_`, `worker_tickets_`, and `first_exception_` all describe one current batch. Removing the mutex without first making that state batch-local would mix CP submissions and be incorrect. A separate pool per CP would recover concurrency but could retain `num_xcds * (N-1)` workers, recreating the oversubscription problem fixed by `a78dedf95b`. A shared multi-producer pool is the appropriate follow-up shape.

The practical acceptance test for this PR is semantic invariance across host execution widths: one versus many dispatch threads must preserve queue ordering, completion delivery, event-loop yields, debugger pause/resume, exception behavior, plugin callback contracts, and race-free output bytes. The submitted regressions, repeated local runs, sanitizer coverage, and full suite now cover those boundaries well enough for this core layer. The separate performance stack should establish where the mechanism speeds up real workloads and where cross-CP serialization limits scaling.
