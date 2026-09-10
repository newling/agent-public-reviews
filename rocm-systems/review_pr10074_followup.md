> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#10074](https://github.com/ROCm/rocm-systems/pull/10074)

## Tests

The Clang 23 Release `rocjitsu_tests` target built successfully at `8b9d8efdb73f`. Thirty focused tests covering dispatch-budget resolution, explicit and automatic C API propagation, CU-capacity clamping, multi-GPU allocation, CLOCKED mode, checkpoint compatibility, XCD partitioning/fan-out, plugin policy, and pooled-CU timing passed. The new due-tick regression also passed 100 repeated executions. Changed-file pre-commit hooks and `git diff --check` passed. All visible substantive GitHub checks are green, including Release, ASan/UBSan, GCC UBSan, TSan, pre-commit, package builds, and TheRock summaries.

The branch was rebased onto `develop` at `1508be5e76`. Current `develop` is one unrelated commit ahead, and a merge-tree check reports no conflict.

## Summary

This is now a focused controls layer over the merged functional CU pool. It adds one public `cpu_dispatch_threads` value, applies explicit values per SoC, divides an automatic host-wide budget across SoCs, and clamps each effective width to the largest CU batch one of that SoC's command processors can submit. CLOCKED mode remains serial, and the two-GPU RCCL configuration retains its known-correct serial override.

The rebase preserves the current XCD-local queue fan-out and removes the old `soc_dispatch` consolidation design completely. It also strengthens checkpoint handling beyond the previous head: the checkpoint records the effective pool width, retains heterogeneous raw per-CU functional quanta, distinguishes explicit zero from an absent legacy field, and wakes restored pool-driven CUs. The accompanying due-tick fix prevents a newly dispatched wave from pulling an active CU's existing continuation forward.

Both prior review blockers are resolved. The checkpoint behavior deliberately preserves the effective width rather than the original automatic request; that is a coherent snapshot policy because thread width is specified not to affect results. I found no remaining actionable correctness issue in the revised code.

## Actionable items

None.

## Suggestions

### 1. Complete the direct `LoadedConfig` construction example

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.h:48-97`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/rj_vm.cpp:27-52,70-93`

The C API applies `cpu_dispatch_threads`, but the documented lower-level `load_config()` example constructs an engine without applying the new field. Its zero-to-automatic resolver is declared in the internal VM implementation header, so a lower-level caller must either ignore the setting or duplicate the host-budget policy.

Consider exposing a configuration-layer helper that resolves and applies runtime controls, then use it from both `create_from_loaded()` and the documented example. At minimum, document that direct `LoadedConfig` consumers must apply `cpu_dispatch_threads` themselves. This is not a defect in the tested C API path, but it would keep the JSON setting's behavior consistent across supported construction paths.

### 2. State the serialized-batch and checkpoint policies in the public configuration guide

**Files:** `emulation/rocjitsu/docs/configuration.md:117-127`, `emulation/rocjitsu/docs/sphinx/conceptual/json-configuration.md:50-59`

The documentation now distinguishes the two concurrency layers and accurately describes the shared per-SoC budget. Add that same-SoC CP batches currently serialize through the shared pool, so `num_threads * cpu_dispatch_threads` is not the effective CU-execution width. Also state that checkpoints materialize an automatic request into the effective width present at save time rather than re-running automatic host detection on restore. Both are useful performance and portability expectations, even though neither changes architectural results.

## Commentary

Dropping `soc_dispatch` was the important architectural correction. Queue ownership, XCD-local caches, fan-out ordering, and aggregated completion remain with the current model, while this PR controls only the host executor layered beneath it.

The automatic-budget policy is substantially clearer than the prior version. It prevents simulated GPU count from multiplying the default worker budget, avoids retaining workers beyond a CP's usable CU batch size, and still permits an explicit per-SoC override. The field-presence handling for `functional_quantum` is also careful: it preserves new explicit-zero checkpoints without reinterpreting old omitted-zero fields.
