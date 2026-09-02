This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#6962](https://github.com/ROCm/rocm-systems/pull/6962)

**Commit reviewed:** `3ef710089f72` (`feat(rocjitsu): add functional CU dispatch pool`).

**Review mode:** follow-up architecture and correctness review. The reviewer
explicitly asked that the current review consider the previous review history
and live review discussion, with particular attention to conceptual clarity,
modularity, and whether each added synchronization or execution path is
justified.

**Public/repository status:** the repository, PR, base branch, and head branch
are public. The PR is open, not a draft, and targets `develop`.

**Focused rebuild after restoring the submitted source:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: the incremental rebuild passed in 5.91s real time. The initial
branch-switch rebuild also completed all 645 build steps successfully; its
wall-clock time was not captured.

**Submitted dispatch, exception, yield, queue-lifetime, plugin-policy, and
output-invariance coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='CpuDispatchPoolTest.*:AqlDispatchTest.WorkerExceptionPropagatesThroughEngineStep:AqlDispatchTest.WorkerYieldReturnsToEventLoopBeforeResuming:AqlDispatchTest.QueueMutationWaitsForDispatchWorkerWindow:AqlDispatchTest.DeferredRescanFiresLateCompletionSignal*:AqlDispatchTest.SerialCompletionUnblocksCoResidentSignalWaiter:ExecutionPluginTest.PluginCapabilitiesSetCpuDispatchPolicy:ConfigLoaderTest.DispatchPlacementDoesNotFollowHostThreadCount:VectorAddStressTest.CpuDispatchThreadsPreserveOutputBytes'
```

Result: 13/13 passed, 0 failed, 0 skipped, and 0 errored in 0.81s real
time. GoogleTest reported 0.741s.

**Focused TSan build and test selection:**

```bash
cmake -S emulation/rocjitsu -B $TSAN_BUILD_DIR -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_COMPILER=$ROCM_PATH/lib/llvm/bin/clang \
  -DCMAKE_CXX_COMPILER=$ROCM_PATH/lib/llvm/bin/clang++ \
  -DRJ_ENABLE_TSAN=ON \
  -DBUILD_TESTING=ON
cmake --build $TSAN_BUILD_DIR \
  --target rocjitsu_tests --parallel 8
time -p $TSAN_BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='CpuDispatchPoolTest.*:AqlDispatchTest.WorkerExceptionPropagatesThroughEngineStep:AqlDispatchTest.WorkerYieldReturnsToEventLoopBeforeResuming:AqlDispatchTest.QueueMutationWaitsForDispatchWorkerWindow:AqlDispatchTest.DeferredRescanFiresLateCompletionSignal*:AqlDispatchTest.SerialCompletionUnblocksCoResidentSignalWaiter:ExecutionPluginTest.PluginCapabilitiesSetCpuDispatchPolicy:ConfigLoaderTest.DispatchPlacementDoesNotFollowHostThreadCount'
```

Result: the TSan build passed. The selected tests passed 12/12, with no
sanitizer report, in 0.37s real time. GoogleTest reported 0.324s.

**Functional-quantum and clocked-mode counterexamples:**

I temporarily added the two regressions in Appendices A and B:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='AqlDispatchTest.ReviewProbeQuantumExhaustionReturnsToEventLoop:AqlDispatchTest.ReviewProbeClockedDispatchThreadsStayEventDriven'
```

Result: 0/2 passed in 0.07s real time.

- A program containing exactly `kFunctionalQuantum` NOPs followed by
  `s_endpgm` completed and halted both CUs during the first doorbell event.
  Reaching the ordinary quantum limit did not return to the event loop.
- A clocked VM with `dispatch_threads=2` also completed and halted its CUs
  during the first doorbell event, proving that the worker path directly
  executed clocked CUs.

**Thread-count-dependent exception counterexample:**

I temporarily added the regression in Appendix C:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='CpuDispatchPoolTest.ReviewProbeSerialExceptionFinishesTheBatchBeforeRethrow'
```

Result: 0/1 passed in 0.07s real time. With `threads=1`, the first CU's
exception escaped immediately and the second CU did not execute. The
multi-worker path instead catches the first exception, completes the batch,
and rethrows afterward.

All temporary regressions were removed, the submitted source was rebuilt, and
the 13-test focused selection above passed again.

**Formatting and diff hygiene:**

```bash
git diff --check <pr-base>...HEAD
git diff --name-only <pr-base>...HEAD |
  xargs .venv/bin/pre-commit run --files
```

Result: `git diff --check` passed. All applicable pre-commit hooks passed.

At final review time, the public release, Clang ASan/UBSan, GCC ASan/UBSan,
TSan, pre-commit, gfx94X package-build, and gfx950 package-build checks pass.
One gfx94X package sanity test remains queued. I did not repeat the full local
test binary because the focused normal and TSan selections cover the changed
contracts and the full required CI jobs that have completed are green.

## Summary

The intended core is understandable: execute one functional quantum on each
active CU, use a bounded set of host workers, fan back into the command
processor, then perform completion side effects on the engine thread.

The submitted implementation does not yet isolate that core into one
well-defined execution service. Functional work has two drivers:

```text
dispatch_wf()
  -> schedules the existing CU tick event

handle_doorbell_sync(), when dispatch_threads > 1
  -> directly calls run_quantum() through SPI-owned host pools
```

The direct path may repeatedly execute to kernel completion inside one
doorbell event; the already-scheduled CU event remains queued and becomes the
resume path only after an explicit `request_functional_yield()`. At one
dispatch thread, the direct path is not used at all. Thus changing the thread
count selects a different execution and event-interleaving model, not merely a
different executor for the same model.

That split ownership explains much of the surrounding complexity:

- the CP needs a second dispatch/execute/complete loop;
- completion delivery needs serial and worker-specific paths;
- ordinary quantum expiration and explicit yield have different behavior;
- clocked mode can accidentally enter the functional driver;
- queue structure must remain pinned while the queue mutex is dropped;
- plugin callback policy changes which execution driver is used; and
- every SPI owns persistent host threads even though the CP visits SPIs
  sequentially.

This review does not require the PR to be split again. The same conceptual
boundaries are still useful for evaluating the submitted implementation:

1. serial queue/completion behavior;
2. the host executor contract; and
3. CP/SPI integration and queue lifetime.

The actionable items below can all be addressed within #6962. The default
quantum increase and cache-flush/topology preparation remain scope concerns,
but they are suggestions rather than a request to reorganize the PR stack.

## Actionable items

### 1. Return to the event loop when the ordinary functional quantum expires

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:172-189`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:1963-2003`

`run_quantum()` reports `yielded=true` only when an instruction calls
`request_functional_yield()`. Reaching `functional_quantum()` with resident
waves leaves `yielded=false`. The CP treats `ran=true` as progress and
immediately invokes another worker round, so ordinary quantum expiration does
not yield to the simulation event loop.

The Appendix A regression used two CUs and a program containing
`kFunctionalQuantum` NOPs followed by `s_endpgm`. Both CUs halted in the first
`engine.step()`. Under the existing `execute_quantum()` contract, the first
quantum should finish after the NOPs and the event loop should run before
`s_endpgm`.

This can starve peer events, SDMA work, new doorbell handling, and structural
queue writers for the complete duration of a kernel. It also makes
`functional_quantum` cease to be the normal event-interleaving boundary on the
worker path.

Replace the two ambiguous booleans with an explicit stop reason, for example:

```text
idle
quantum_expired
yield_requested
```

Return from the doorbell handler after a worker batch reports
`quantum_expired` or `yield_requested`. Add the Appendix A regression, and add
a stalled/no-instruction case so "ran" cannot mean merely "a resident wave
existed."

### 2. Make functional execution mode an invariant of the core executor

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:284-293,1880-1897`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:172-189`

`CommandProcessor` does not retain or validate the execution mode.
`set_dispatch_threads(2)` therefore enables direct `run_quantum()` calls for a
clocked CU. The base `ComputeUnitCore::run_quantum()` method is also callable
for both template modes and directly loops over `step()`.

The Appendix B clocked regression observed both waves halt during the first
doorbell event. Their instructions retired synchronously rather than through
the clocked event path.

Do not rely on the later configuration PR to clamp this setting. The core API
is public and must be safe independently. Carry execution mode into the CP or
the executor, reject or clamp worker execution for non-functional modes, and
defensively prevent `run_quantum()` from being used on a clocked CU. Add the
Appendix B regression.

### 3. Give the host executor one owner and one truthful concurrency budget

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/spi.h:139-170,308-310`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:284-293,1888-1891`

The CP exposes one `dispatch_threads` value, but every SPI lazily creates and
retains a complete pool sized from that value. The CP then calls those SPI
pools sequentially. Only one SPI pool per CP can do useful work at a time,
while all pools created by earlier SPIs retain parked workers.

For the production-shaped topology used by the submitted vector test, the
eventual upper bound is:

```text
8 XCD CPs * 4 SPIs per CP * (8 requested threads - 1 caller) = 224 workers
```

That is not a bounded per-CP budget. It also keeps the actual parallelism of
one CP limited to one SPI's active CUs despite calling the setting a CP
dispatch-thread count.

The SPI should own simulated workgroup placement and CU resource accounting.
Host execution resources should be owned by the selected host dispatch domain.
Use one pool per CP for the current public contract, gather active CUs from its
SPIs into one batch, and reuse that pool. If a later design intentionally uses
a VM- or SoC-wide budget, make that a separate explicit policy.

Add a production-shaped multi-SPI regression that activates more than one SPI,
checks the aggregate retained worker count, and covers teardown. The current
placement and vector tests activate too narrow a subset to catch pool
multiplication.

### 4. Make the pool's complete failure contract independent of thread count

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/cpu_dispatch_pool.h:39-57,62-107,140-160`

There are two separate exception-safety gaps.

First, `worker_goal == 0` calls `run_quantum()` directly and lets the first
exception escape. The multi-worker path catches the first exception, finishes
all claimed tasks and worker bookkeeping, then rethrows. Appendix C showed that
a later CU executes at `threads=2` but not at `threads=1`. This contradicts the
pool's stated complete-batch contract and makes thread count change observable
failure semantics.

Second, if construction of a later `std::jthread` throws after earlier workers
have started, the `CpuDispatchPool` destructor body never runs. Member
unwinding requests stop and joins existing `jthread`s, but those workers are
parked on a plain `std::condition_variable`; requesting stop does not wake it.
Construction failure can therefore hang while unwinding.

Use one task-draining/first-exception protocol for both serial and parallel
runs. Add constructor rollback that requests stop, notifies, and joins all
created workers before rethrowing, or use a stop-token-aware wait. Add the
Appendix C regression and fault-injected thread-creation failure coverage.

### 5. Do not reinterpret callback serialization as whole-execution serialization

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:284-293`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/soc.cpp:81-86`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/execution_plugin.h:62-70`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/execution_plugin_group.h:120-122,271-285`

`requires_serial_hot_hooks()` is documented as a callback-lock policy. The
group implements that policy by routing hot and infrequent callbacks through
one recursive mutex. It does not say that CU execution itself must become
single-threaded.

This PR uses that callback capability to clamp `dispatch_threads` to one. The
SoC setter repeats the same clamp even though each XCD has already passed the
group to its CP. Besides being redundant, this changes the entire execution
driver and event interleaving merely because a plugin asked for callback
serialization. It also overwrites the configured/requested count, so replacing
a serial-hook group with a parallel-safe group cannot restore the earlier
budget without a second explicit setter call.

Either rely on the callback lock and remove the execution clamp, or introduce a
separate, explicitly motivated `requires_serial_execution()` capability for a
plugin that truly cannot operate while unrelated simulator work runs in
parallel. If such a capability is necessary, keep requested and effective
thread counts separate and document when policy is sampled. Remove the
duplicate SoC-level enforcement and test plugin-group replacement order.

## Suggestions

### 1. Justify or revert the quantum policy change

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:84-93`

The PR changes the default from 1,024 to 16,384 and adds a configurable field.
That changes serial event interleaving even when the worker pool is disabled.
It is a scheduling/tuning decision, not an inherent requirement of the pool.

Either retain the established default, or document the workload evidence and
event-latency/fairness tradeoff for 16,384. Directly test the chosen boundary
for both serial and worker execution. Public/declarative control may still be
added by the controls PR without requiring this PR to be split.

### 2. Keep the late-packet and completion contracts explicit within the PR

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:1194-1209,1904-2069`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/completion_tracker.cpp:26-43`

The late-packet rescan comment explicitly says the race exists at every thread
count. Centralizing completion side effects on the CP thread is a useful
prerequisite for workers, but it must preserve the existing serial path.

If these changes remain in the same PR, keep them as clearly separated helpers
and tests rather than allowing their invariants to be implicit in the large
doorbell loop. The existing serial and parallel regressions are useful; add
short contract comments identifying which behavior is independent of worker
execution.

### 3. Use one canonical L2 inventory for completion flushing

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/completion_tracker.h:32-34,63-65`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/completion_tracker.cpp:139-149`

Deduplicating repeated L2 flushes is reasonable, but the tracker now receives
an explicit L2 list and also rediscovers L2s through every CU, reconciling both
at runtime with a `std::set`. The core requirement is only that cache
maintenance runs after workers join.

If this remains in #6962, establish one canonical CP/CompletionTracker L2
inventory and use it directly. Avoid maintaining two sources of truth whose
consistency has to be repaired on every dispatch retirement.

## Commentary

Several pieces of added complexity are justified and worth retaining:

- decoded instructions need RAII ownership because worker exceptions can leave
  `issue_instruction()`;
- worker completion callbacks must record state without flushing caches or
  firing signals concurrently with active CUs;
- the pool must explicitly join workers while its state remains alive; and
- queue shape must remain stable while the CP releases the queue mutex.

The current queue-structure shared mutex fixes the immediate dangling-reference
bug, but it also blocks queue registration and removal for the complete direct
execution interval. Once ordinary quantum expiration correctly returns to the
event loop, that interval becomes bounded. A longer-term queue model with
stable heap-owned queue/state objects and deferred removal would avoid tying
queue-management liveness to kernel execution and remove the need to pin two
parallel vectors.

The central architectural recommendation is to choose one owner for functional
execution. The SPI is a good place to select or expose runnable CUs; it is not
a natural owner for persistent host thread resources when the CP defines the
dispatch domain and calls SPIs sequentially. A mode-aware executor owned by
that domain would make the control PR's thread-count contract, the pool's
lifetime, and the event-loop boundary all describe the same concept.

## Appendix A: quantum-expiration regression

The temporary regression added beside the submitted worker-yield test was:

```cpp
TEST(AqlDispatchTest, ReviewProbeQuantumExhaustionReturnsToEventLoop) {
  VmFixture f("cdna4", /*num_cus=*/2);
  auto *snapshots = f.capture_halts();
  f.cp()->set_dispatch_threads(2);

  std::vector<uint32_t> code(amdgpu::ComputeUnitCore::kFunctionalQuantum + 1,
                             SOPP_S_NOP);
  code.back() = SOPP_S_ENDPGM;
  uint64_t kernel =
      f.write_kernel(0x1000, code.data(), code.size() * sizeof(uint32_t));
  test::AqlQueue queue(f.mem(), f.cp());
  queue.dispatch(kernel, /*grid_size=*/128, /*workgroup_size=*/64);

  ASSERT_TRUE(f.engine->step());
  EXPECT_TRUE(snapshots->snapshots().empty())
      << "the doorbell event should return after one functional quantum";
  EXPECT_TRUE(f.cu(0)->has_active_wfs());
  EXPECT_TRUE(f.cu(1)->has_active_wfs());
}
```

The submitted code instead halted both waves during that first
`engine.step()`.

## Appendix B: clocked-mode regression

The probe made this exact change to the existing `VmFixture` constructor; the
rest of the fixture was unchanged:

```diff
-  VmFixture(std::string_view arch = "cdna3", uint32_t num_cus = 1,
-            uint32_t num_wf_slots = 10, uint32_t lds_size_kb = 64,
-            uint32_t sgprs_per_wf = 104) {
+  VmFixture(std::string_view arch = "cdna3", uint32_t num_cus = 1,
+            uint32_t num_wf_slots = 10, uint32_t lds_size_kb = 64,
+            uint32_t sgprs_per_wf = 104,
+            std::string_view exec_mode = "functional") {
...
-    std::string json =
-        R"({"max_ticks":10000,"num_threads":1,"vm":{"arch":")" +
-        std::string(arch) + R"("},)" +
+    std::string json =
+        R"({"max_ticks":10000,"num_threads":1,"exec_mode":")" +
+        std::string(exec_mode) + R"(","vm":{"arch":")" +
+        std::string(arch) + R"("},)" +
         R"("topology":{"root":{"name":"soc","type":"soc","children":[)"
```
```

The temporary test was:

```cpp
TEST(AqlDispatchTest, ReviewProbeClockedDispatchThreadsStayEventDriven) {
  VmFixture f("cdna4", /*num_cus=*/2, /*num_wf_slots=*/10,
              /*lds_size_kb=*/64, /*sgprs_per_wf=*/104,
              /*exec_mode=*/"clocked");
  auto *snapshots = f.capture_halts();
  f.cp()->set_dispatch_threads(2);

  const uint32_t code[] = {SOPP_S_NOP, SOPP_S_ENDPGM};
  uint64_t kernel = f.write_kernel(0x1000, code, sizeof(code));
  test::AqlQueue queue(f.mem(), f.cp());
  queue.dispatch(kernel, /*grid_size=*/128, /*workgroup_size=*/64);

  ASSERT_TRUE(f.engine->step());
  EXPECT_TRUE(snapshots->snapshots().empty())
      << "clocked instructions must not retire inside the doorbell event";
}
```

The submitted code produced halt snapshots during the first step.

## Appendix C: serial exception-semantics regression

The temporary pool regression was:

```cpp
TEST(CpuDispatchPoolTest,
     ReviewProbeSerialExceptionFinishesTheBatchBeforeRethrow) {
  DispatchPoolFixture fixture(/*cu_count=*/2);
  amdgpu::CpuDispatchPool pool(/*threads=*/2);

  fixture.memory.write32(kProgramBase, kSSetvskip);
  fixture.wfs[0]->pc = kProgramBase;
  fixture.wfs[1]->pc = kProgramBase + sizeof(uint32_t);

  EXPECT_THROW(
      pool.run(std::span<amdgpu::ComputeUnitCore *>(fixture.tasks),
               /*threads=*/1),
      std::exception);
  EXPECT_EQ(fixture.wfs[1]->trace_inst_count_, 1u)
      << "thread count should not change whether later tasks in the batch execute";
}
```

The second CU's instruction count remained zero.
