> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#10074](https://github.com/ROCm/rocm-systems/pull/10074)

## Tests

The Clang 23 Release `rocjitsu_tests` target built successfully at `8b9d8efdb73f`. Thirty focused tests covering budget resolution, configuration propagation, CU-capacity clamping, multi-GPU allocation, CLOCKED mode, legacy and current checkpoints, XCD partitioning/fan-out, plugin policy, and pooled scheduling passed. The new active-CU due-tick regression passed 100 repeated runs. Changed-file pre-commit hooks and `git diff --check` passed. All visible substantive GitHub checks are green, including Release, sanitizers, pre-commit, package builds, and TheRock summaries.

The PR is public, targets public `develop`, and is mergeable. Its two commits are based on `1508be5e76`; current `develop` is one unrelated commit ahead and merges cleanly.

## Summary

This PR exposes the functional CU pool from #6962 as a JSON configuration control without changing modeled GPU ownership. `num_threads` continues to partition whole XCDs across Simdojo engine threads. The new `cpu_dispatch_threads` value instead controls the host executor that advances runnable CUs: an explicit nonzero value is requested for every SoC, while zero derives one host-wide budget, caps it at 32, and divides it across the simulated SoCs. Each SoC then clamps its effective width to the largest CU batch one of its command processors can supply. CLOCKED mode remains on the serial event-driven path.

The change preserves current queue ownership and XCD-local fan-out. It also makes the execution controls checkpoint-safe: the effective pool width is serialized, per-CU functional quanta are retained even when CUs differ, an explicit unbounded zero is distinguished from an absent legacy field, and restored pool-driven waves are scheduled after engine attachment. The command-processor adjustment keeps an active CU's established due tick when a newly dispatched wave joins it, preserving serial and pooled timing parity.

The automatic-budget policy is bounded, deterministic for a supplied host width, and directly covered at its boundary cases. The checkpoint additions append fields compatibly and explicitly test old omitted fields, explicit zero, and heterogeneous values. I found no actionable correctness issue.

## Actionable items

None.

## Suggestions

### 1. Show lower-level config-loader callers how to apply the new control

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.h:48-97`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/rj_vm.cpp:27-52,70-93`

The high-level C API resolves and applies `cpu_dispatch_threads`, but the documented `load_config()` construction example does not. The resolver is declared in the internal VM implementation header, so a lower-level embedding must ignore the field or duplicate its automatic-budget policy.

Consider exposing one configuration-layer helper for resolving and applying runtime controls and using it in both `create_from_loaded()` and the example. Alternatively, state explicitly that direct `LoadedConfig` consumers own this step. The current C API behavior is correct; this would clarify the lower-level caller contract.

### 2. Add concrete JSON examples for the effective parallelism

**Files:** `emulation/rocjitsu/docs/configuration.md:117-127`, `emulation/rocjitsu/docs/sphinx/conceptual/json-configuration.md:50-59`

The guides accurately separate engine partitions from the CU worker pool, but a few small JSON examples would communicate the effective limits more directly than prose alone. Add an examples table or subsections along these lines:

```json
{"num_threads": 1, "cpu_dispatch_threads": 1, "exec_mode": "functional"}
```

This is fully serial: one engine execution thread and no retained CU-pool worker.

```json
{"num_threads": 8, "cpu_dispatch_threads": 16, "exec_mode": "functional"}
```

For one eight-XCD SoC whose CPs each own at least 16 CUs, this creates eight XCD partitions and one shared SoC pool of width 16. Same-SoC CP batches serialize, so the upper bound is 16 concurrently executing CU tasks, not `8 * 16`.

```json
{"num_threads": 16, "cpu_dispatch_threads": 0, "exec_mode": "functional"}
```

For four SoCs on a host whose automatic budget reaches the cap of 32, this requests width 8 per SoC. With at least four suitably distributed engine partitions, up to four SoC pools can run for an aggregate upper bound of 32 CU tasks; with `num_threads: 1`, only one pool can be entered at a time and the bound is 8.

Also include the CLOCKED case, where `cpu_dispatch_threads` is ignored and the effective width is always one. State the assumed SoC/XCD/CU geometry beside every numeric result so users can substitute their own topology. Finally, note that a checkpoint stores the effective pool width, so an automatic request is not re-evaluated against a different host when restored.

## Commentary

The separation of responsibilities is the strongest part of the design. XCDs, command processors, queues, caches, and completion remain simulator state; the new setting controls only the host machinery used to execute functional CU quanta. The shared per-SoC pool avoids multiplying retained workers by XCD count, while the multi-SoC automatic policy prevents simulated GPU count from multiplying the default host budget.

The two-GPU RCCL configuration's explicit serial override is a sensible narrow exception to the automatic default. It preserves the known-correct collective path without weakening the default acceleration available to other functional configurations.
