This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#13622](https://github.com/ROCm/rocm-systems/pull/13622)

**Reviewed head:** `c0361600145` on `<pr-head-ref>`, based on `origin/develop`. The upstream repository, fork, PR and base branch are public.

**Suggestion branch:** [`review/pr13622-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr13622-suggestions), two commits on top of the reviewed head.

| Commit | Item |
| --- | --- |
| [`60e05ac00c6d`](https://github.com/newling/rocm-systems/commit/60e05ac00c6d8c9d3352fe45b62e0c14afd754d9) | Document the wave-state lock requirement on halting transitions (item 1) |
| [`5a2c390c357a`](https://github.com/newling/rocm-systems/commit/5a2c390c357a3c82f69516ea5246644ea794b282) | Test slot range regrowth after out-of-order wave retirement (item 2) |

## Tests

Built `rocjitsu_tests`, the CLI, interposer and race plugin with Clang 23 (Release, Ninja, x86-64-v3). The full test binary passes except one environment-dependent case (`EffectiveConfigTest.ReadsNativeLaunchConfigHandoff`, which needs a launcher-provided invocation directory and is already excluded from default CTest discovery). The focused CU, command-processor, debugger and wavefront-slot suites pass on the submitted head and on the suggestion branch, as do the two new `WavefrontSlotTest` cases and the checks below.

- **Invariant check:** temporarily making the slot-range update ignore the slot index fails both new PR tests on every architecture; making it grow only from an empty range fails the barrier test and the test added in item 2. The checkout was restored afterwards.
- **Race-detector integration cases:** 62 of 63 gfx950 and 21 of 21 gfx1151 HIP race cases from the corpus pass against this PR's build. `global_to_lds_buffer_race` fails with "expected at least one race, got none", identically on this PR's parent commit, so it is not caused by this change. It is the buffer-to-LDS case that needs a newer corpus revision.
- **CI:** the PR's check list contains the handbook job and generic sanity/summary/bot failures, but no rocjitsu test job. The local runs above are therefore the only rocjitsu test evidence for this head.
- **Not measured:** the performance numbers in the description were not reproduced.

## Summary

The PR removes fixed per-step overhead from the CU loop, which matters for short dispatches where most wave slots are empty or retired. It adds `active_slot_limit_`, one past the highest non-halted slot, and bounds the wave-state, barrier-release and issue loops by it. It also skips work that cannot affect the result: ticking empty memory pipelines, flushing command-processor notifications when none are pending, the `s_setpc`/`s_swappc` null-target check for instructions without an indirect-branch or indirect-call flag, and the ALU trap-enable read when no new exception cause is pending.

The slot-range bookkeeping is sound. `Wavefront::set_state()` is the only writer of `state_`, and every change of `is_halted()` goes through `update_activity_counts()`, which raises the limit when a wave becomes active and walks it down past halted or empty slots when the top slot retires. Waits, barrier waits and debugger stops stay active, so they remain in range. Halted slots excluded by the limit cannot affect the skipped scans, because those scans already ignore halted waves. The remaining skips are conservative: `MemoryPipeline::tick()` only walks `issued_`, `empty()` also checks `returned_`, and the indirect-branch flag gate admits every `s_setpc_b64`/`s_swappc_b64` encoding in the generated CDNA1–4 and RDNA1–4 tables. The flush decision is made under the lock, and a producer that enqueues afterwards holds its own guard and flushes its notifications. The new tests exercise sparse placement, debugger stops, waits, barrier release and reuse, and the debug-build assertion in `update_wf_states` guards the same invariant.

## Actionable items

### 1. Document the lock requirement on `Wavefront::set_state` and `halt`

`wavefront.h:713` (`set_state`) and `wavefront.h:973` (`halt`). `update_activity_counts()` now writes `ComputeUnitCore::active_slot_limit_`, a plain integer read by the CU's per-step loops. That is safe only if every transition into or out of HALTED runs with `wave_state_mutex_` held. Every caller I found does (`step_impl` through `WaveStateGuard`, the command processor through `with_wave_state_locked`, `dispatch_wf_at` internally). The requirement is stated only on the CU's field, while `set_state` and `halt` are public on `Wavefront` and give no hint of it, and the mutex is private to the CU. A caller that halts a wave without the lock would race with the scan and could leave a live wave outside the range, so its dispatch would never complete. Commit [`60e05ac00c6d`](https://github.com/newling/rocm-systems/commit/60e05ac00c6d8c9d3352fe45b62e0c14afd754d9) documents the contract on both functions.

### 2. Cover regrowth of the slot range after out-of-order retirement

`amdgpu_vm_test.cpp`, after `LowerBarrierWaiterResumesAfterSparseHigherSlotRetires`. The two submitted tests exercise retirement with a debugger stop, wait and barrier, and reuse from an empty CU. They do not exercise the range growing again while it is non-empty: a hole below a live wave, and a retired top slot that is redispatched while a lower wave is still running. Commit [`5a2c390c357a`](https://github.com/newling/rocm-systems/commit/5a2c390c357a3c82f69516ea5246644ea794b282) adds `SlotRangeFollowsOutOfOrderRetirementAndRegrowth` for CDNA3, CDNA4 and CDNA5. It starts waves at different entry points so the top slot retires first, redispatches into the hole and into the retired slot, and checks that both execute. The barrier test already catches the grow-only-from-empty mutation described above; this test adds the hole and retired-slot cases, so it is a modest addition.

## Suggestions

### Null-target jump check on gfx1250

`compute_unit.cpp:2017`, with the generated `cdna5/sop1.cpp` constructors for `s_set_pc_i64` and `s_swap_pc_i64`. The null-target halt matches the substrings `s_setpc` and `s_swappc`. The gfx1250 instructions are named `s_set_pc_i64` and `s_swap_pc_i64`, so neither substring matches and the check has never applied there. This predates the PR, and the new flag gate is behavior-preserving. It is worth a separate change that keys the check on the indirect flags and the PC operand rather than on the mnemonic text, with a gfx1250 test. A flag-only gate would also include relative `s_call_b64`, so the operand shape has to be part of the condition.

### Description and measurements

The description says its measurements predate the latest rebase and reports a 6.5% slower median for the gfx1250 single-thread Tensile smoke test over seven pairs, without saying whether that is noise. Re-running the headline measurements on the rebased head, and stating whether the Tensile result is noise or a real cost, would make the performance case easier to evaluate.

### Release-build coverage of the invariant

`compute_unit.cpp:1525`. The assertion that every excluded slot is halted or empty compiles out in Release builds. The behavior tests above catch a stale limit, so this is residual risk only for configurations that run no tests.

## Commentary

- Skipping the flush when nothing is pending moves the decision under the lock. Producers that enqueue notifications without a wave-state guard rely on the next outermost guard exit, as they did before. No new path loses a notification, but a latent producer that enqueues without a guard would see the same delay as before.
- The per-step wins grow with how sparse the slots are, so the speedup will be largest on small dispatches and nearly absent on full CUs. The description's numbers are consistent with that.
- The race-detector plugin runs inside this loop. The PR does not change its hook sites or the waves passed to barrier completion, and the corpus cases above pass, but those cases have limited timing coverage. Running the full pinned corpus once the updated pin lands would extend that evidence.
