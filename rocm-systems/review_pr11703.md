> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#11703](https://github.com/ROCm/rocm-systems/pull/11703)

**Revision reviewed:** `1f8d4ef1e53e779594833ec4a9fe0ae930d0a3ef`

## Tests

The Clang 23 Release `rocjitsu_tests` target built successfully. Sixty-five focused pool, allocation-policy, checkpoint, XCD fan-out/barrier, and output-invariance tests passed; six concurrency-sensitive tests also passed 100 repeated runs each. `git diff --check` passed. The Mirage Rust tests could not be run locally because `cargo` is not installed. The PR merges cleanly with current `develop`, and all visible substantive CI test/build jobs are green, including Release, ASan/UBSan, GCC UBSan, and TSan; the remaining failed `therock-pr-bot` job is the repository policy gate while review is required.

## Summary

There are two distinct useful grains of host parallelism in rocJITsu. A Simdojo engine thread advances a whole XCD's event and command-processor path; after that command processor has identified the CUs that are due, a CPU-pool lane advances one complete functional quantum on one CU. The former is the coarsest safe unit because an XCD owns its command processor, queues, CUs, and L2. The latter is still needed for a one-XCD GPU and for a busy XCD with many runnable CUs.

Before this change, all command processors in one SoC shared a pool whose `run_mutex_` covered submission, execution, and join. XCD engine threads could therefore reach the pool concurrently but only one could use it. This PR moves task/result/index/exception/completion state into a stack-owned `Submission`, keeps only an intrusive queue of unclaimed worker assignments under the pool mutex, and makes every engine caller drain its own submission. The retained topology remains one pool per SoC rather than one pool per XCD. That is a good concurrency boundary: it removes the whole-submission lock without multiplying pools, keeps each CU quantum as the unit of work, and keeps queue advancement and completion effects on the owning engine thread after join. The tests cover the important lifetime, isolation, exception, width, and fan-out ordering contracts.

The pool implementation is not the source of most of this patch's complexity. The larger addition is a policy language: a process-wide budget, two explicit overrides, target-specific `(engine, dispatch)` choices, per-SoC effective widths, a topology pre-scan, a CLI inspector, checkpoint persistence, and Mirage propagation. The measured results justify using both grains rather than mechanically maximizing engine count: at small budgets, allocating some threads within an XCD is faster, while the larger server entries use one engine per XCD. I would keep the concurrent-caller pool. The main concern is that adopting the table silently changes the behavior of every table-less configuration; the other policy layers can be simplified or better isolated without changing the core scheduler.

## Actionable items

### 1. Preserve the established fallback for configurations without an allocation table

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.cpp:43-78`, `emulation/rocjitsu/schemas/simulation_config.fbs:277-297`, `emulation/rocjitsu/tests/partitioning_test.cpp:211-225`

`resolve_execution_threads()` seeds its result from the default `{1, 1}` choice and changes it only while iterating `thread_allocations`. Consequently, a config with no table and no explicit controls now resolves to one engine and serial CU dispatch. Before this PR, an omitted `num_threads` resolved to `min(available host threads, total XCDs)`, so an ordinary table-less eight-XCD config used up to eight coarse XCD partitions. The old explicit `cpu_dispatch_threads: 0` contract also selected an automatic host-wide dispatch budget; it now collapses to one when there is no table. The new test at lines 220-222 makes the new serial fallback intentional, but it does not remove the compatibility/performance regression for external rocJITsu configs.

Keep table-driven selection as an opt-in extension while retaining the previous fallback when `thread_allocations` is absent. That requires preserving the distinction between an omitted dispatch field and an explicit zero instead of mapping both to `ExecutionThreadRequest::dispatch == 0`. Alternatively, add an explicit policy/version field and a documented migration rather than changing omission semantics. Add a loader-level regression using a table-less multi-XCD JSON config, covering both omitted controls and explicit `cpu_dispatch_threads: 0`.

## Suggestions

### 1. Keep rocJITsu scheduling policy out of Mirage's hardware agent model

**Files:** `emulation/mirage/core/src/agent.rs:1-16,254-269`, `emulation/mirage/builtin/build.rs:1-16,72-100`, `emulation/mirage/rocjitsu/src/lib.rs:773-801`

`AgentDef` is documented as a hardware-level, emulator-independent description, but it now contains `ExecutionThreadChoice` with fields named after rocJITsu's `num_threads` and `cpu_dispatch_threads`. These values are host-executor tuning derived from rocJITsu workload measurements, not GPU properties. This makes every Mirage backend and every serialized agent aware of one backend's scheduler, and a future scheduler change becomes an agent-format change.

Keep the table in the rocJITsu backend or in backend-specific profile metadata. The existing build-time extraction can still prevent drift, but it can generate a rocJITsu-local lookup keyed by the builtin agent/target instead of adding the field to `mirage_core::agent::AgentDef`. This removes an entire cross-project propagation layer while leaving user overrides and synthesized rocJITsu JSON unchanged.

### 2. Do not make checkpoints carry an obsolete tuning algorithm forever

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/checkpoint.cpp:130-140,332-351`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/rj_vm.cpp:356-366`

The pool width and allocation table are host-performance policy, explicitly not modeled GPU state. A new checkpoint stores the whole current table and restore re-evaluates that stored table against the receiving host. This is an awkward midpoint: restore does not reproduce the source allocation, but it also does not benefit from improved target defaults in a newer runtime. Old checkpoints will retain benchmark choices for an old executor indefinitely.

Choose one contract explicitly. If exact execution-resource reproducibility matters, store only the resolved E/D allocation. If portability and future tuning matter, persist explicit user overrides and enough target identity to let the receiving runtime apply its current defaults. The latter fits the stated host-acceleration contract and avoids making a heuristic table part of checkpoint state.

### 3. Converge the two automatic-dispatch resolvers

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.h:189-204`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.cpp:81-136`, `emulation/rocjitsu/tests/config_test.cpp:2310-2326`

The no-argument `apply_cpu_dispatch_threads()` applies the new joint engine/worker allocation, while the overload taking a host width still invokes the old dispatch-only budget splitter and deliberately ignores the table and engine allocation. For example, restoring an E=2 plan and applying a dispatch cap of five can retain six execution threads (`E + D - 1`), even though the new API otherwise presents five as a total budget. Two functions with the same name now implement different meanings of “automatic,” and the checkpoint test codifies that split.

If compatibility requires retaining this entry point, rename or deprecate it as a dispatch-only override. Prefer one resolver taking the complete request, topology, and host width for new callers, and have tests exercise host-width changes through that path. This would remove the remaining parallel policy implementation and make the total-budget invariant easier to maintain.

## Commentary

The submitted pool is already simpler than the lane-vector alternative in the dimension that matters most: one intrusive node and a ticket count represent a submission, workers remain shared, and every XCD caller provides useful execution instead of waiting for a global caller token. Restricting participation to one caller would make a single width bound easier to explain, but it would reintroduce idle engine threads and discard the cross-XCD concurrency this PR is intended to unlock. The benchmark evidence supports the submitted choice.

The scheduling is also at appropriately coarse units in the implementation. Engine partitions own whole XCDs, pool workers take whole submission assignments, and their atomic work claims execute a complete CU quantum; the design does not fragment work at wave or instruction granularity. The preset policy is intentionally not “maximize XCD engines first”: the measured small-budget server cases favor mixed E/D allocations, and the 16-thread and larger entries reach all eight XCDs. That is a reasonable empirical policy, but it strengthens the case for treating the table as replaceable backend tuning rather than durable hardware or checkpoint state.

The remaining risk is workload sensitivity. The tables are based on three synchronous matrix workloads, while the documentation itself notes that smaller grids plateau much earlier. The explicit overrides and inspection command provide an escape hatch. Longer term, keeping the selector pure and the policy centralized will make it possible to replace static target tables with workload-aware or scheduler-aware choices without changing the pool, generic Mirage agents, and checkpoint format together.
