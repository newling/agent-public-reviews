> This is a review from an agent with an automatic prompt from the reviewer

## Tests

Clang 23 Release build passed; the complete `rocjitsu_tests` binary passed 3,800 tests with 2 expected skips and 1 disabled test, the focused pool/fan-out selection passed 55/55, the GCC 13 ThreadSanitizer selection passed 24/24 with no report, a temporary eight-partition plus eight-thread-pool fan-out regression passed 1/1, and branch-diff pre-commit plus `git diff --check` passed.

Three temporary counterexamples failed against the submitted head and were removed after validation. A two-CU/one-slot dispatch with three one-instruction workgroups left the third workgroup undispatched and its completion signal unchanged. A debugger-paused pool-driven wave kept generating continuation events. A direct one-thread `CpuDispatchPool::run()` stopped at the first failing task while the parallel path completed the rest of the batch before rethrowing. Exact regressions are in the appendix.

At review time the focused GitHub Release, ASan/UBSan, GCC UBSan, TSan, and pre-commit checks were green. One broad gfx950 package job failed before build in its `Fetch sources` step; its workflow was still running, so the failure log was not yet available. The gfx125 package build was still running.

## Summary

This revision has converged on a sound core architecture. Functional execution is parallelized at the CU boundary, which matches the ownership of wave scheduling, registers, and L1 state better than the issue's initially suggested workgroup boundary. One pool belongs to the SoC, its thread count includes the calling CP thread, and a mutex serializes submissions from different CPs so the configured CU-execution budget does not multiply across XCDs. SPIs remain placement/resource-accounting objects rather than thread owners. The CP remains the sole owner of queue progression, cache publication, completion signals, and cold plugin callbacks; pool workers only advance one quantum of independent CU state and append compact completion records. CLOCKED mode remains on the existing event-driven path. Those are good, understandable boundaries.

The integration with the newer XCD fan-out design also looks coherent. A queue still has one ring-owning CP, peer CPs retain their local CUs and L2s, and the pool does not reintroduce the earlier primary-CP consolidation model. A temporary combined test with eight XCD partitions and the shared eight-thread pool completed correctly.

I am nevertheless requesting changes. The fork/join boundary itself makes sense, but the surrounding scheduling state is split between the CP continuation, per-CU serial drivers, queue progression, and debugger resume. That split currently causes two reproducible liveness failures, including an ordinary kernel whose grid exceeds simultaneous CU capacity. The policy API also still conflates callback locking with whole-CU execution policy. I would keep the core design, repair the scheduling ownership, and simplify the policy/state surfaces before merging.

## Actionable items

### 1. Must address before merge: refill CUs after a batch drains all current residents

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:2786-2801,2890-2894,2993-2998`

The pooled path runs at most one CU batch and deliberately sets `yield_to_event_loop` afterward. Once that batch rejoins, completions are drained, but queue placement is not run again before the outer loop breaks. The only continuation decision at the end is based on `next_pooled_due_tick()`, which considers resident CUs only.

If a dispatch has more workgroups than can be resident simultaneously and every resident workgroup finishes in that batch, the due-tick map becomes empty even though the queue still has undispatched workgroups. No continuation is armed, `on_cu_idle()` is not called by `run_quantum()`, and the remaining grid is stranded. The appendix's two-CU/one-slot, three-workgroup test reaches `max_ticks` with its completion signal still equal to one.

After draining a completed worker batch, run one placement-only queue pass before returning to the event loop, or make the continuation condition represent both runnable resident CUs and dispatchable queued work. Do not execute a second quantum in the same event; preserve the current one-batch-per-event timing contract. Add a regression where the grid is larger than aggregate CU residency and every workgroup completes within one quantum. A local prototype that called the existing `process_queues()` once after the final drain fixed the reproducer while retaining the submitted timing/yield tests, but centralizing that transition as suggested below would be clearer.

### 2. Must address before merge: paused waves keep the pooled driver permanently runnable

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:1957-2027`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:205-224,1206-1224`

The serial CU driver schedules according to `has_runnable_wfs()`, so a CU containing only debugger- or runtime-paused waves quiesces. The pooled driver instead builds and retains its due-tick map with `has_active_wfs()`. `run_quantum()` sees the resident paused wave, sets `ran = true`, calls `step()` once, receives false because there is no runnable wave, and returns zero iterations. The CP then advances that CU's due tick by one and schedules another continuation. This repeats until `max_ticks` (or indefinitely when no maximum is configured), consuming host CPU and advancing simulated time while execution is supposed to be stopped.

The fix needs both halves of the scheduling contract. Pool work selection should exclude CUs with no runnable waves, and resume must explicitly wake the CP-owned pool driver. Today `schedule_work_async()` queues the CU's `resume_event_`, whose handler calls `schedule_work()`; `schedule_work_at()` intentionally does nothing when `pool_driven_` is true, so merely changing `has_active_wfs()` to `has_runnable_wfs()` would make a paused pooled CU sleep forever after resume. Route pool-mode readiness/resume to a CP continuation (or introduce a small driver callback/interface shared by serial and pooled execution), then add pause/resume coverage with dispatch threads greater than one.

### 3. Important: make `CpuDispatchPool::run()` failure semantics independent of the requested thread count

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/cpu_dispatch_pool.h:76-87,141-160`

The worker path catches the first task exception, continues draining the batch, waits for every claimed task, and rethrows afterward. The `worker_goal == 0` path calls each task directly and lets the first exception escape immediately. Consequently the same task span advances later CUs when called with two or more threads but leaves them untouched when called with one thread. This contradicts the class-level description that `run()` executes one quantum per supplied CU and makes fallback or throttling alter observable simulator state.

Use the same catch-record-continue operation for calling-thread tasks in both branches, then rethrow after the batch is complete. Add the appendix regression (or an equivalent one) for a failing first task followed by normal tasks at `threads == 1`.

### 4. Important: separate plugin callback serialization from simulator execution policy

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/soc.cpp:95-110`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:302-317`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/execution_plugin.h:63-71`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/execution_plugin_group.h:298-304`

`requires_serial_hot_hooks()` has a precise existing contract: high-frequency callbacks participate in the plugin group's callback mutex. `ExecutionPluginGroup` already implements that contract. This PR additionally interprets the same flag as a request to reduce all CU dispatch to one thread, in both SoC and CP policy code.

Those are different guarantees. The extra clamp is unnecessary for callback serialization, silently changes simulation performance and interleaving, and still does not mean whole-simulator serialization because separate XCD engine partitions can execute concurrently. Rely on the callback mutex and remove the pool clamp. If a plugin genuinely needs all simulator execution serialized, add a separately named capability, define its interaction with Simdojo partition count as well as the CU pool, and keep requested and effective concurrency visible as distinct values. The current `SerialPluginRemovesSharedPoolAcrossProductionTopology` test should be replaced with coverage for the selected contract.

## Suggestions

### 1. Centralize queue advancement around the fork/join boundary

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:1854-1955,2743-3008`

Queue advancement is currently implemented in three similar but non-identical loops: `on_cu_idle()`, `process_queues()`, and the large Phase 1 block in `handle_doorbell_sync()`. Each separately handles predecessor barriers, non-kernel completion, workgroup placement, index advancement, and completion draining. The missed post-batch refill is a direct example of those copies drifting apart.

Extract one placement/retirement transition that advances each queue until it reaches backpressure, an unsatisfied dependency, or a defined execution boundary. Let the serial idle callback and pooled continuation invoke that same transition with different execution policies. This would make future packet kinds and scheduling modes substantially easier to extend without adding another near-copy of the queue state machine.

### 2. Remove or give behavior to state that currently advertises unused contracts

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:75-84`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/dispatch_entry.h:178-183,455-470`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:2576-2595`

`FunctionalQuantumResult::yielded` is set and merged but never consumed. `DispatchEntry::blocks_following` is described as scheduler state but is only copied into a local variable in the BARRIER_AND/OR fetch branch; the barrier-value case sets it without reading it. `HwQueueState::implicit_barrier_next` is read but never written anywhere in the tree. These fields make the state model look more general than it is and invite future code to rely on behavior they do not implement. Either make them inputs to one centralized scheduler transition or remove them and express the existing behavior directly.

### 3. Keep one canonical L2 inventory for completion publication

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/completion_tracker.h:31-65`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/completion_tracker.cpp:159-170`

`CompletionTracker` now receives an explicit CP L2 list but also rediscovers L2s through every CU, deduplicating the union with a `std::set` on every completion. The safety goal—flush every local L2 only after workers join—is correct. Prefer one topology-owned, immutable L2 inventory so adding a new CU or cache attachment path cannot silently create two sources of truth.

## Commentary

The important high-level choices are worth keeping: CU-granularity tasks, a single SoC-owned resource budget, bounded fork/join quanta, CP-thread retirement, explicit serial/pool driver transfer, and preservation of XCD-local ownership. The implementation also has unusually good focused coverage for teardown, partial construction, queue mutation during worker execution, timing parity, late packet arrival, cluster barriers, cold-hook affinity, byte-for-byte output, and XCD fan-out.

The `CpuDispatchPool::run_mutex_` intentionally serializes batches submitted by different XCD CPs. That is a simple way to enforce one SoC budget, and the combined eight-partition/eight-thread correctness probe passed. It can still underutilize the pool for small XCD shards because each CP submits separately. I would accept that as an explicit first implementation, provided the upper configuration PR documents that engine threads and dispatch threads do not multiply. If measurements later show this boundary matters, the natural extension is a SoC scheduler that combines due CUs from multiple CPs into one batch while leaving queue ownership and retirement on each CP; it is not a reason to move foreign CUs under one CP.

The current head successfully resolves the stale-base/XCD-shard conflict from the previous review and preserves the important kernel-versus-non-kernel and predecessor-versus-following ordering distinctions. The earlier pool ownership, clocked-mode, quantum-yield, construction teardown, worker exception propagation, and cluster-barrier concerns are also substantially improved. The remaining blockers are now localized to scheduling transitions rather than a reason to discard the overall design.

## Appendix: temporary regressions

The following tests were added only for review, run against the submitted head, and then removed.

### A. A completed pool batch must refill newly idle CUs

Add within the existing anonymous namespace in `amdgpu_vm_test.cpp`; it uses that file's existing `VmFixture`, `init_completion_signal()`, `make_dispatch_packet()`, and `completion_signal_value()` helpers.

```cpp
TEST(AqlDispatchPoolReviewProbe, CompletedBatchRefillsIdleComputeUnits) {
  VmFixture f("cdna4", /*num_cus=*/2, /*num_wf_slots=*/1);
  f.cp()->set_dispatch_threads(2);
  const uint32_t code[] = {SOPP_S_ENDPGM};
  const uint64_t kernel = f.write_kernel(0x1000, code, sizeof(code));
  constexpr uint64_t signal = 0xF0030000;
  init_completion_signal(f.mem(), signal);
  test::AqlQueue queue(f.mem(), f.cp());
  queue.submit(make_dispatch_packet(kernel, signal, /*grid_size_x=*/192));

  while (f.engine->step()) {
  }

  EXPECT_EQ(completion_signal_value(f.mem(), signal), 0);
}
```

Submitted-head result: failed; the completion signal remained `1`. A local placement-only `process_queues()` pass after the final worker-completion drain made this regression and the existing quantum-spacing/due-tick/yield tests pass.

### B. A paused pool-driven wave must not schedule an endless continuation chain

Add within the existing anonymous namespace in `amdgpu_vm_test.cpp`; it uses that file's existing `VmFixture`, `make_multi_quantum_nop_kernel()`, and `step_until_first_quantum()` helpers.

```cpp
TEST(AqlDispatchPoolReviewProbe, DebugPausedWaveDoesNotKeepSchedulingContinuations) {
  VmFixture f("cdna4", /*num_cus=*/1, /*num_wf_slots=*/1);
  f.cp()->set_dispatch_threads(2);
  auto code = make_multi_quantum_nop_kernel();
  const uint64_t kernel = f.write_kernel(0x1000, code.data(), code.size() * sizeof(uint32_t));
  test::AqlQueue queue(f.mem(), f.cp());
  queue.dispatch(kernel, /*grid_size=*/64, /*workgroup_size=*/64);

  step_until_first_quantum(f, f.cu());
  auto *wave = f.cu()->wf(0);
  ASSERT_NE(wave, nullptr);
  wave->set_debug_suspended(true);

  ASSERT_TRUE(f.engine->step()); // Consume the already-armed continuation.
  EXPECT_FALSE(f.engine->step())
      << "a debug-paused wave kept the pool continuation chain alive";
}
```

Submitted-head result: failed; a new CP continuation remained scheduled after the already-armed continuation observed only the paused wave.

### C. One-thread pool execution must preserve batch exception semantics

Add within the existing anonymous namespace in `cpu_dispatch_pool_test.cpp`; it uses that file's existing `DispatchPoolFixture`, `kProgramBase`, and `kSSetvskip` definitions.

```cpp
TEST(CpuDispatchPoolReviewProbe, OneThreadStillFinishesTheBatchBeforeRethrowing) {
  constexpr uint64_t kBadProgramBase = kProgramBase + 0x2000;
  DispatchPoolFixture fixture(/*cu_count=*/4);
  amdgpu::CpuDispatchPool pool(/*threads=*/4);
  fixture.memory.write32(kBadProgramBase, kSSetvskip);
  fixture.wfs[0]->pc = kBadProgramBase;

  EXPECT_THROW(pool.run(std::span<amdgpu::ComputeUnitCore *>(fixture.tasks), /*threads=*/1),
               std::exception);
  for (size_t i = 1; i < fixture.wfs.size(); ++i)
    EXPECT_EQ(fixture.wfs[i]->pc, kProgramBase + sizeof(uint32_t));
}
```

Submitted-head result: failed; all three normal tasks remained at `kProgramBase` after the first task threw.
