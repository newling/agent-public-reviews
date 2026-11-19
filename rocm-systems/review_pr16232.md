This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#16232](https://github.com/ROCm/rocm-systems/pull/16232)

**Reviewed head:** `dd32baab7d8acd15fd18abae7326d2d8341fa60e`

**Base:** `0ca1de96e985ca956a012aa5131ee53bf236c081`

**Mode and scope:** Independent review of all 12 changed files, including the simulator transitions, callback contracts and locking, tests, documentation, and the interface consumed by the dependent race-detector change. Existing discussion on this PR was not read. The dependent PRs were inspected for context and interface compatibility, not given a separate full review.

**Suggestion branch:** [review/pr16232-suggestions](https://github.com/newling/rocm-systems/tree/review/pr16232-suggestions), based on the reviewed head. Commits: [a38fe4935b0](https://github.com/newling/rocm-systems/commit/a38fe4935b0b57ce6d0a8b31671131863ab69953) → suggestion 1; [f5b7483ae67](https://github.com/newling/rocm-systems/commit/f5b7483ae67bbc077199a641f8a757680eb62569) → suggestion 2.

## Tests

Submitted head and final suggestion head each passed **724 native tests, with five existing async-MMA skips**, using Clang 23.1, Release/NDEBUG, Ninja and the same focused executable. This includes all added simulator/plugin tests, existing race-detector core and plugin tests, serial and parallel cluster execution, legacy barrier hook ordering, RDNA4 scalar barriers, and checkpoint validation. All changed-file pre-commit hooks and whitespace checks passed on the suggestion branch.

The ordinary `cmake --build "$BUILD_DIR" --target rocjitsu_tests -j48` attempt failed on Clang 23's `-Werror,-Wunused-template` in three unchanged files: `util_intrusive_shared_ptr_test.cpp` (`CatchAllValue`), `mfma_simd_benchmark.cpp` (unused seed helpers), and `wmma_simd_benchmark.cpp` (unused seed helpers). The files are identical to the base. To validate this PR without changing warning policy, I built and linked the relevant test translation units against the normal production objects and dependencies. This is focused validation, not a passing full `rocjitsu_tests` build. The exact-head CI TSan job passed; other CI work was still incomplete when inspected. No local sanitizer, HIP corpus, hardware or performance run is claimed, and no dependent-PR binary was tested.

## Summary

This is the simulator observation layer for [split-barrier issue #15037](https://github.com/ROCm/rocm-systems/issues/15037), within the [gfx1250 race-detector work #15034](https://github.com/ROCm/rocm-systems/issues/15034). The broader progression matters: knowing that a wave completed an LDS access does not establish that another wave may use it. The earlier work records the access and its completion; this stack adds the separate inter-wave ordering step.

| Stage | Changes | Responsibility |
| --- | --- | --- |
| Already in the reviewed base | [#14687](https://github.com/ROCm/rocm-systems/pull/14687), [#15796](https://github.com/ROCm/rocm-systems/pull/15796), [#15486](https://github.com/ROCm/rocm-systems/pull/15486) | Track tensor-DMA and async-copy LDS accesses, and recognize completion established by counter-capacity backpressure. |
| This PR | #16232 | Report counted signals, completed rounds, and individual passed waits, including the round associated with a wave's completion bit. Existing race-detector behavior remains in place. |
| Direct dependent | [#16020](https://github.com/ROCm/rocm-systems/pull/16020), inspected at `eeaaa00894b7b47b2869437d68604a5b47ec51ab` | Consume these hooks to release/acquire per-wave ordering and retain completed LDS history until every relevant live wave has acquired it. Its actual base is this PR's exact head. |
| Integration coverage | [ROCm/rocjitsu-test-corpus#96](https://github.com/ROCm/rocjitsu-test-corpus/pull/96), inspected at `67e0ab9a15dcbc941d320811ae2dda4f398d7391` | Add gfx1250 programs exercising accesses on either side of signal and wait. The systems workflow still pins corpus `f7f6818f7a5965830124d54897ef4bc0329fa505`, so these cases are not enabled by either systems diff alone. |

The split is useful. The simulator owns ignored-signal decisions, named membership, completion bits, and wakeups; putting those facts into callbacks avoids duplicating the barrier state machine in each plugin. In particular, an instruction-before/after hook cannot alone report when a previously parked wait actually passes. The detector owns the ordering policy and event history; no vector clocks or retirement policy are introduced here.

The distinction between *notified* and *armed* is necessary for #16020. If round 0 leaves a wave's bit set and round 1 completes before that wave waits, round 1 still notifies the wave but must not replace its recorded round. The new tests distinguish that case from ordinary completion and verify that a second wait parks. I checked the completion-bit and INIT/JOIN semantics against the [CDNA5 ISA, 27 July 2026](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf), §5.6.1 and Table 22.

The callback placement also respects the existing execution model: cluster signals call plugins outside the placement mutex, queued cluster completions are delivered after the worker batch rejoins, and old/new completion callbacks share one callback-lock acquisition. The unchanged detector continues to receive the original notified membership.

## Actionable items

None. I found no demonstrated correctness defect in the reviewed hook implementation within the tested scope.

## Suggestions

### 1. Reuse the member list for legacy barriers

At `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:2671`, the new legacy path copies `members` into both `armed` and `woken`, although all three sets are identical. That adds two vector allocations and copies to every resolved legacy barrier, including runs with no plugins. The existing span interface can use the same member vector for both completion arguments and for the wait loop.

Implemented in [a38fe4935b0](https://github.com/newling/rocm-systems/commit/a38fe4935b0b57ce6d0a8b31671131863ab69953). Signal/completion/wait ordering and the point at which waves become runnable are preserved; the existing legacy hook-ordering test passes. This removes concrete redundant work; it is not a measured speedup claim.

### 2. Document the actual architecture scope and round identity

At `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/execution_plugin.h:79`, explain that `BarrierRound` is local to its owning workgroup or cluster: consumers sharing state across workgroups need that ownership and dispatch identity in addition to the fields in the value. The dependent detector already achieves this by keeping round state per workgroup.

The conceptual documentation at `emulation/rocjitsu/docs/sphinx/conceptual/execution-plugins.md:44` should name the signal hook and describe both completion spans. Also, RDNA4 already reaches the shared split signal/wait implementation in the reviewed base: `generated/rdna4/sop1_exec.cpp:1123` and `generated/rdna4/sopp_exec.cpp:90` route through `generated/shared/execute_shared.h:421`. The claim in #16020's description that its RDNA4 model treats the wait as a single-instruction barrier is stale. #16232's “Scope is gfx1250” similarly should distinguish the motivating target from the actual shared-code effect. Existing RDNA4 barrier tests pass, but the newly added callback tests are gfx1250-specific.

Implemented the source/API documentation clarification in [f5b7483ae67](https://github.com/newling/rocm-systems/commit/f5b7483ae67bbc077199a641f8a757680eb62569). That commit also corrects the test comment at `cdna5_instruction_test.cpp:1065`: JOIN clears a wave's bit; INIT advances the barrier generation. It adds the direct `<span>` dependency for the new declaration in `command_processor.h:1042`. The PR descriptions were not rewritten or edited.

### 3. Point the description to the split-barrier issue

The motivation and tracking sections link #15036, which is the closed counter-capacity issue implemented by #15486. The matching open split-barrier issue is **#15037**; the broader gfx1250 tracker is **#15034**. Correct those references in this PR and the dependent description. No description edit was made as part of this review.

## Scope decisions

**Completion caused by LEAVE is not a release observation for the leaving wave.** This PR correctly reports the round completed by `S_BARRIER_LEAVE`, but its signal hook deliberately represents counted signals. It does not carry the leaving wave's completed accesses through the threshold reduction. [#16237](https://github.com/ROCm/rocm-systems/issues/16237) tracks that additional ordering. Keep it separate from this hook contract; a future observation of LEAVE must identify its actual participation rather than pretending it was a counted signal. Likewise, [#15039](https://github.com/ROCm/rocm-systems/issues/15039) covers LDS barrier cells, whose address/phase protocol is different from these scalar barrier counters. This stack does not complete all gfx1250 synchronization support.

**Qualify the companion corpus evidence.** The current corpus source uses notification flags to force the execution order in `split_barrier_ds_write_wait_after_signal_race` and `split_barrier_reader_in_window_race`. Those flags introduce a separate ordering path. [#16236](https://github.com/ROCm/rocm-systems/issues/16236) already records the resulting detector false positives and the missing polling/flag-handoff support. I checked the current source but did not independently re-qualify its emitted ISA. Treat those expected reports as evidence of the explicit signal/wait model's current coverage boundary, not independent proof that both complete programs contain races. That limitation does not require changing the simulator's signal/completion/wait observations.

The intended landing sequence is hooks → detector consumer → companion corpus coverage and the systems workflow pin. Keep old-callback compatibility in the hook step, and validate the combined consumer/corpus revisions before claiming the new integration coverage. The descriptions' combined-stack benchmark results do not isolate this PR's callback overhead.

The two suggestion commits are published on [review/pr16232-suggestions](https://github.com/newling/rocm-systems/tree/review/pr16232-suggestions); no runtime finding was left unimplemented. Description corrections and the existing follow-up issues remain separate. Validation limits are recorded above.
