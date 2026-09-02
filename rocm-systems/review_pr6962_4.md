This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#6962](https://github.com/ROCm/rocm-systems/pull/6962)

**Commit reviewed:** `b043ffda82f5` (`fix(rocjitsu): defer cluster barrier
completion`).

**Review mode:** follow-up review. I read the three previous agent reviews, the
complete current PR discussion and inline-review history, the reviews of the
four merged prerequisite PRs, and the current cross-XCD fan-out stack. I then
independently checked the submitted code and the changes since the previous
review.

**Public/repository status:** the repository, PR, base branch, and head branch
are public. The PR is open and non-draft. GitHub reports
`CHANGES_REQUESTED`, `DIRTY`, and `CONFLICTING`.

The current PR head is based on `89c1a2b17c2c`. The `develop` head observed on
August 24, 2026 was `f7a97ca94121`. A synthetic merge reports content conflicts
in:

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp`
- `emulation/rocjitsu/tests/config_test.cpp`

Merging the current XCD fan-out stack with this PR adds conflicts in
`command_processor.h` and `completion_tracker.cpp` as well.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: all 389 build steps passed in 242.59s real, 1795.28s user, and
55.67s sys.

**Focused submitted regressions:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='CpuDispatchPoolTest.*:AqlDispatchTest.HeaderClearBarrierUnblocksPriorPollingKernelBeforeLaterDispatch:AqlDispatchTest.DeferredRescanFiresLateCompletionSignalSerialWorker:AqlDispatchTest.DeferredRescanFiresLateCompletionSignalParallelWorkers:AqlDispatchTest.SerialCompletionUnblocksCoResidentSignalWaiter:AqlDispatchTest.PoolContinuationLetsPeerQueueSatisfyPollingWave:AqlDispatchTest.PoolContinuationLetsPeerCommandProcessorSatisfyPollingWave:AqlDispatchTest.ActiveDispatchSurvivesSerialToPoolTransition:AqlDispatchTest.ActiveDispatchSurvivesPoolToSerialTransition:AqlDispatchTest.LivePluginReplacementRestoresPoolDuringActiveDispatch:AqlDispatchTest.PoolPreservesSerialQuantumSpacingAroundPeerEvent:AqlDispatchTest.PoolTracksIndependentCuDueTicks:AqlDispatchTest.WorkerExceptionPropagatesThroughEngineStep:AqlDispatchTest.WorkerYieldReturnsToEventLoopBeforeResuming:AqlDispatchTest.QueueMutationWaitsForDispatchWorkerWindow:ClusterDispatchTest.ParallelCdna5RetiresClusterAfterWorkersRejoin:Gfx1250SimulationTest.ParallelClusterBarrierSynchronizesWorkgroupsAcrossComputeUnits:ConfigLoaderTest.DispatchPoolBudgetIsSharedAcrossProductionTopology:ConfigLoaderTest.SerialPluginRemovesSharedPoolAcrossProductionTopology:ConfigLoaderTest.DispatchPlacementDoesNotFollowHostThreadCount:CApiTest.ClockedDispatchStaysEventDriven:HookOrderingTest.ParallelWorkgroupLifecycleRunsOnCommandProcessorAfterWorkersRejoin:VectorAddStressTest.CpuDispatchThreadsPreserveOutputBytes'
```

Result: 28/28 passed, 0 failed, 0 skipped, and 0 errored in 0.60s real.

**Repeated concurrency-sensitive selection:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='CpuDispatchPoolTest.*:AqlDispatchTest.PoolContinuationLetsPeerQueueSatisfyPollingWave:AqlDispatchTest.PoolContinuationLetsPeerCommandProcessorSatisfyPollingWave:AqlDispatchTest.ActiveDispatchSurvivesSerialToPoolTransition:AqlDispatchTest.ActiveDispatchSurvivesPoolToSerialTransition:AqlDispatchTest.PoolPreservesSerialQuantumSpacingAroundPeerEvent:AqlDispatchTest.PoolTracksIndependentCuDueTicks:AqlDispatchTest.WorkerExceptionPropagatesThroughEngineStep:AqlDispatchTest.WorkerYieldReturnsToEventLoopBeforeResuming:ClusterDispatchTest.ParallelCdna5RetiresClusterAfterWorkersRejoin:Gfx1250SimulationTest.ParallelClusterBarrierSynchronizesWorkgroupsAcrossComputeUnits:HookOrderingTest.ParallelWorkgroupLifecycleRunsOnCommandProcessorAfterWorkersRejoin' \
  --gtest_repeat=100 --gtest_break_on_failure
```

Result: 1,700/1,700 test executions passed, with no failures, skips, or
errors, in 3.85s real.

**Formatting and diff hygiene:**

```bash
git diff --check $(git merge-base origin/develop HEAD)..HEAD
git diff --name-only $(git merge-base origin/develop HEAD)..HEAD -z |
  xargs -0 .venv/bin/pre-commit run --files
```

Result: `git diff --check` passed and all applicable pre-commit hooks passed.

The PR's focused release, Clang ASan/UBSan, GCC ASan/UBSan, TSan,
pre-commit, and repository-policy checks pass. The broad monorepo
multi-architecture workflow has failures outside the focused rocjitsu jobs.

I did not test a merged `develop` result because the current head has unresolved
textual conflicts. I also did not test the combined #6962 plus #10286-#10290
fan-out stack because those branches conflict in the core command-processor and
completion paths; any hand resolution would be a speculative implementation,
not the submitted PR.

## Summary

The current head is substantially better than the version covered by the
previous review. It now:

- owns one bounded CPU worker pool per SoC instead of one pool per SPI;
- gives each CP access to that shared budget and gathers active CUs across all
  of its SPIs;
- keeps CLOCKED mode on the event-driven CU path;
- executes at most one due quantum per CU and preserves each CU's next simulated
  due tick;
- safely transfers an active CU between serial and pool ownership;
- drains workgroup and cluster-barrier side effects on the CP thread after
  worker fan-out rejoins;
- gives serial and parallel pool paths the same complete-batch exception
  behavior;
- makes partial pool construction stop-aware; and
- restores the 1,024-instruction default functional quantum.

Those changes resolve the previous review's event-loop starvation,
clocked-mode execution, multiplied per-SPI worker count, exception-contract,
constructor-unwind, cluster-barrier, and timing-equivalence findings. The
submitted regressions are direct and passed repeatedly.

The one earlier architectural finding that remains is the plugin-policy
contract. The merged plugin layer defines `requires_serial_hot_hooks()` as a
request to serialize callbacks through the group's mutex. This PR also treats
that flag as a request to disable parallel CU execution. Those are different
contracts.

The requested cross-XCD behavior is still sensible, but its motivation and
implementation are now clearer than they were in the original PR:

- The modeled CDNA4 SoC exposes eight XCDs with 36 CUs each. A queue owned by
  one XCD currently reaches only that XCD's 36 CUs, despite the guest seeing
  one 288-CU GPU agent.
- A large dispatch should therefore be able to use all XCDs, and the
  workgroup-to-XCD permutation matters to kernels that swizzle workgroup IDs
  for cache locality.
- The old `soc_dispatch` proposal in #10074 accomplishes this by registering
  every XCD's CUs, SPIs, and L2s with one primary CP and requires
  `num_threads=1`.
- The newer #10284/#10285/#10286-#10290 direction keeps one owning CP for the
  ring but shards each dispatch across the XCD-local CPs, preserving XCD
  ownership, local L2s, and the ability to use XCD engine partitions.

The feature should therefore be described as **dispatch fan-out from one
queue**, not as several CPs independently consuming one queue. The queue has
one owner; peer CPs receive ordered packet replicas or grid shards. That
behavior is justified. The primary-CP consolidation implementation is no
longer the right mechanism.

## Actionable items

### 1. Rebase onto current `develop` and preserve both the dispatch-pool and XCD-shard contracts

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:1371-1510,2240-2310,2396-2638`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/dispatch_entry.h:43-124`
- `emulation/rocjitsu/tests/config_test.cpp`

PRs #10284 and #10285 landed after this head's merge base. They add explicit
kernel/non-kernel packet identity and make `dispatch_workgroups()` walk an
entry's `XcdShard`; those are prerequisites for the separate cross-XCD fan-out
stack. This PR independently changes the same packet construction,
barrier-ordering, dispatch loop, and tests, and Git currently reports conflicts.

The resolution must preserve all of these independent contracts:

- a zero-workgroup XCD share is still a kernel, not a non-kernel packet;
- unclustered and clustered entries walk their shard's grid-wide ordinals;
- `wait_for_predecessors` remains distinct from `blocks_following`;
- pooled execution runs at most one due quantum per CU per continuation;
- workgroup and cluster completion side effects remain deferred until workers
  rejoin; and
- serial completion remains prompt enough to unblock a co-resident waiter.

Please rebase, resolve those semantics explicitly rather than choosing one side
of the textual conflicts, and run the dispatch-pool tests together with
`XcdShardTest.*` and the XCD distribution tests. The current head cannot be
approved or tested as an integration candidate until this is done.

### 2. Do not use callback serialization as a whole-execution policy

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/soc.cpp:94-110`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:307-310`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/execution_plugin.h:62-70`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/execution_plugin_group.h:120-122,271-285`

`requires_serial_hot_hooks()` says that high-frequency plugin callbacks must
take the group's callback mutex. `ExecutionPluginGroup` implements exactly that
contract. The new SoC and CP checks additionally clamp the complete CU-dispatch
worker pool to one thread whenever the flag is true.

That makes a callback-locking choice silently select a different simulator
execution policy. It is also not sufficient as a whole-execution guarantee:
XCDs may still execute concurrently through the Simdojo partitions introduced
by #8705. No bundled production plugin currently overrides the flag, so the
present behavior is mainly a contradictory public contract and a future
performance trap rather than a demonstrated current-plugin failure.

Please either:

- rely on the callback mutex and remove the pool clamp; or
- add a separately named and documented capability such as
  `requires_serial_execution()`, define whether it also constrains Simdojo
  partitions, and keep requested versus effective worker counts distinct.

The current `SerialPluginRemovesSharedPoolAcrossProductionTopology` test locks
in the over-broad interpretation. Replace it with coverage for the chosen
contract.

## Suggestions

### 1. Retire the `soc_dispatch` consolidation design from the upper stack

**Related PR:** #10074

Keep #10074's declarative `cpu_dispatch_threads`, checkpoint persistence, and
documentation work, but remove or redesign its `soc_dispatch` control after the
current fan-out stack lands.

Primary-CP consolidation duplicates CP ownership, makes one CP directly own
foreign-XCD SPIs/CUs/L2s, and rejects `num_threads > 1`. The newer fan-out
design preserves the hardware hierarchy and has already landed its
observability and sharding primitives in #10283-#10285. Maintaining both modes
would create two implementations of the same user-visible goal with different
ordering, completion, and partitioning semantics.

If retaining an opt-out is useful for debugging, make the switch control
whether compute queues fan out while leaving queue ownership and the XCD-local
CP topology unchanged.

### 2. Test and document how the shared SoC pool composes with XCD fan-out

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/soc.cpp:94-110`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/cpu_dispatch_pool.h:66-121`
- `emulation/rocjitsu/tests/vector_add_test.cpp:180-263`

The SoC-wide pool has one `run_mutex_`, so CPs on separate XCD partitions
submit batches through it serially. This correctly enforces one host-worker
budget, but it means `num_threads > 1` and `cpu_dispatch_threads > 1` are not
multiplicative and can be counterproductive for small fanned-out grids: eight
one-CU shards can become eight serial one-task pool calls.

Before both features are enabled together, add a combined
fan-out-plus-dispatch-pool regression and benchmark at small and large grid
sizes. Document whether the intended policy is:

- XCD partitions with serial CU execution;
- one shared CU pool with CP batches serialized; or
- a future SoC scheduler that combines ready CUs from multiple CPs into one
  bounded batch.

The current correctness tests cover multi-XCD partitions and the shared pool
separately, but not their composition.

## Commentary

### Previous review and discussion status

The PR has accumulated 34 discussion comments, 78 review submissions, and 57
inline threads; all inline threads are marked resolved. The resolved threads
cover several generations of a heavily restacked change, so their resolution
state is not by itself evidence that the current architecture is ready.

The main historical concerns now break down as follows:

- **Scope:** addressed. Generic memory concurrency, shared GPU-state safety,
  XCD partitioning, plugin policy, configuration controls, and hot-path
  optimizations were split into separate PRs.
- **Memory/cache safety:** addressed by merged #8702 and #8703, including
  VMID/page-table lifetime, cross-L2 atomic arbitration, scalar-cache
  write-through, and cache alias handling.
- **XCD partitioning:** addressed by merged #8705. Whole XCDs are the static
  Simdojo partition unit.
- **Plugin callback policy:** #8706 landed a coherent callback-locking
  contract, but #6962 still interprets its flag as whole-execution
  serialization.
- **Queue lifetime and completion:** addressed through the structural queue
  lock and CP-side deferred completion records.
- **Pool ownership and teardown:** addressed by the shared SoC pool,
  stop-aware construction, and explicit teardown.
- **Functional scheduling:** addressed by one-batch-per-event execution,
  per-CU due ticks, and tested serial/pool transitions.
- **Orthogonal DBT and sanitizer work:** removed from this PR.
- **TSan coverage:** the originally referenced standalone TSan PR was closed,
  but the rocjitsu corpus workflow now has a passing TSan job on this head.

### Preceding stack relevance

- **#8702, concurrent Simdojo memory primitives:** still relevant and required.
  It supplies the block and synchronization primitives consumed by the worker
  layers.
- **#8703, shared GPU-state concurrency:** still relevant and the most important
  safety prerequisite. Its final changes close cross-XCD cache/atomic gaps that
  would otherwise make worker execution unsound.
- **#8705, XCD execution partitioning:** still relevant, but orthogonal to the
  pool. It provides static event-engine parallelism at whole-XCD granularity.
- **#8706, plugin policy:** still relevant. Its callback contract should be
  consumed literally rather than repurposed as a CU-execution switch.

### Changes landed after the latest rebase

The most important landed work is #10283-#10285: per-XCD dispatch
observability, the `XcdShard` primitive, and shard-aware dispatch walking. It
establishes a repository direction that directly affects this PR's merge and
the upper stack's cross-XCD design.

Other recent ISA and barrier changes merge automatically or are already
represented in this head's tests. They remain reasons to rerun the focused
suite after rebasing, but I did not find another architectural replacement for
the core CU pool itself.

### Recommendation

Keep the core idea and most of the current implementation. Rebase it onto the
landed shard-aware dispatch model, separate callback serialization from
execution serialization, and then validate the combined fan-out/pool
composition before exposing the controls. I would continue to request changes
until those two actionable items are resolved.
