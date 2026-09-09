> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#10074](https://github.com/ROCm/rocm-systems/pull/10074)

## Tests

The submitted head `b316a764899a` built successfully with Clang 23 in Release mode. The seven focused configuration, C API, checkpoint, CLOCKED-mode, partitioning, and SoC-dispatch tests passed. Branch-delta pre-commit hooks and `git diff --check` passed. A temporary checkpoint-policy regression failed as described below and was removed afterward.

The PR is public and currently a draft. GitHub reports it as conflicting with the current #6962 base; a local merge-tree check found conflicts in 16 files. The only current CI jobs are a passing label job and a failing repository-policy job, so there is no current GitHub build or sanitizer result for this head.

## Summary

The useful part of this PR is a public `cpu_dispatch_threads` configuration control for #6962's SoC-owned functional CU executor. It parses an explicit width or resolves zero to a hardware-derived default capped at 32, applies one shared budget to each SoC, keeps CLOCKED execution serial, pins the known-sensitive two-GPU RCCL configuration to one thread, and carries dispatch and functional-quantum settings through checkpoint reconstruction. The explicit/automatic and CLOCKED-mode tests cover the main C API path well.

The branch predates the final #6962 architecture and the merged XCD fan-out work. Its second feature, `soc_dispatch`, moves every XCD's CUs, SPIs, and L2s under one primary command processor and forbids multiple Simdojo partitions. Current #6962 instead preserves XCD-local ownership, divides an ordered queue entry into XCD-local shards, aggregates completion once, and supports whole-XCD partitions. The submitted branch therefore cannot be merged or mechanically conflict-resolved as-is; it needs to be reduced to the configuration/checkpoint layer and rebased onto the current core.

## Actionable items

### 1. Must address before merge: rebase onto the current core and remove `soc_dispatch`

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/soc.cpp:15-50,170-172`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/soc.h:107-133,199-201`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/rj_vm.cpp:87-88,140-155`, `emulation/rocjitsu/schemas/simulation_config.fbs:247-249`, `emulation/rocjitsu/docs/configuration.md:60,83-89`

The base branch has advanced from `d0da6e85b6` to `9a9ea84dd4`, and GitHub now reports this PR as conflicting. More importantly, current #6962 contains the newer XCD-local fan-out contract: one ring-owning CP replicates ordered entries to peer CPs, each CP retains its own CUs and L2, and completion is aggregated across shards. `consolidate_dispatch_to_primary()` restores the superseded design by registering foreign CUs and L2s on the primary CP, repointing CU completion ownership, replacing the primary CP's SPI set, and requiring `num_threads == 1`.

Rebase the two controls commits onto the current #6962 head, retain the `cpu_dispatch_threads` and functional-quantum checkpoint work, and remove `soc_dispatch` from the schema, loader, SoC/CP APIs, checkpoint format, documentation, and tests. Preserve current `HwQueue::xcd_fanout` as the only cross-XCD dispatch mechanism. Add one C API configuration regression combining `num_threads > 1`, `cpu_dispatch_threads > 1`, and the current KFD/XCD-fan-out path so the two supported concurrency layers are tested together. Move the serial pin to the current `gfx950_mi355x_kmd_2gpu.json` filename.

### 2. Preserve the requested automatic policy across checkpoint round trips

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/rj_vm.cpp:64-76`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/checkpoint.cpp:56-58,278-286`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.h:47-81`

The public value `cpu_dispatch_threads: 0` means “choose automatically on this host.” `create_from_loaded()` resolves zero to a concrete number before calling `SoC::set_dispatch_threads()`, so the SoC retains only the effective width. `serialize_config()` then writes `soc.dispatch_threads()` into the checkpoint. On this host, a source configured with zero restored as an explicit value of 32 rather than zero. Restoring that checkpoint on a host with fewer CPUs would retain 32 workers instead of re-evaluating the documented automatic policy.

Keep the requested policy distinct from the effective pool width and serialize the requested value. Centralize zero-to-auto resolution in a reusable API rather than the anonymous C API construction helper: the documented `LoadedConfig` C++ construction example currently neither applies `cpu_dispatch_threads` nor has access to the private cap policy, while passing its raw zero directly to `SoC::set_dispatch_threads()` selects one thread. Update that example and add round-trip coverage for both zero and an explicit count.

## Suggestions

### 1. Document how the two thread controls compose

**File:** `emulation/rocjitsu/docs/configuration.md:58-81`

The new documentation describes `num_threads` and `cpu_dispatch_threads` independently, which invites the assumption that their widths multiply. After rebasing, document that `num_threads` creates whole-XCD Simdojo partitions, while `cpu_dispatch_threads=N` creates one SoC pool with `N-1` retained workers plus the CP thread participating in the active batch. Same-SoC CP batches currently serialize through the pool, so `num_threads * cpu_dispatch_threads` is not the CU-execution width; different SoCs own independent pools. Also describe `functional_quantum` as CU `step()` iterations rather than individual instructions, because one step can issue for every runnable wavefront resident on a CU.

## Commentary

After removing `soc_dispatch`, this becomes a well-scoped controls PR: add one schema value, define its requested/effective semantics, apply it consistently to each SoC, preserve it across checkpoints, and document its interaction with the already-merged partition and fan-out mechanisms. The parent PR's shared-pool ownership is the right foundation, and pinning the two-GPU RCCL configuration to the serial path preserves the known-correct behavior while other functional configurations use the automatic default.

## Appendix: automatic-policy checkpoint regression

The following temporary test was added after `CheckpointRoundTripPreservesFunctionalDispatchControls`, run against the submitted head, and then removed:

```cpp
TEST(CApiTest, ReviewProbeCheckpointPreservesAutomaticDispatchSelection) {
  const std::string json = functional_dispatch_threads_config(/*threads=*/0);
  rj_vm_t *raw_source = nullptr;
  ASSERT_EQ(rj_vm_create_from_string(json.c_str(), RJ_VM_MODE_DEFAULT, &raw_source),
            ROCJITSU_STATUS_SUCCESS);
  ASSERT_NE(raw_source, nullptr);
  std::unique_ptr<rj_vm_t, decltype(&rj_vm_destroy)> source(raw_source, &rj_vm_destroy);

  test::ScopedTempFile checkpoint("rocjitsu-c-api-checkpoint-auto-dispatch-");
  ASSERT_EQ(rj_vm_save_checkpoint(source.get(), checkpoint.path().c_str(), 42),
            ROCJITSU_STATUS_SUCCESS);

  auto restored = config::restore_checkpoint(checkpoint.path());
  EXPECT_EQ(restored.cpu_dispatch_threads, 0u)
      << "the checkpoint replaced the configured auto policy with this host's resolved width";
}
```

The assertion failed with `restored.cpu_dispatch_threads == 32`.
