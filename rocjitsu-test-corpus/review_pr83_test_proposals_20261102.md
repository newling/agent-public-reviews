This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocjitsu-test-corpus#83](https://github.com/ROCm/rocjitsu-test-corpus/pull/83)

**Reviewed head:** `63cddb8286da969f802878dbddecb99f5a48c925`.

**Proposal branch:** [review/corpus83-test-proposals-20261102](https://github.com/newling/rocjitsu-test-corpus/tree/review/corpus83-test-proposals-20261102), based directly on that head. Each commit below can be cherry-picked independently onto the reviewed head; the three-way application check succeeds for all thirteen. Test helpers use only the original PR's infrastructure. This document and branch are review artifacts; they do not modify the PR.

## Tests

With Systems `8305decbe0a` (the updated tensor stack), all 53 gfx1250 cases and the four focused gfx950 DTL cases pass under emulation; the combined diff passes whitespace checks. These totals include four explicit known-gap trackers, not fixes for those gaps. Hardware qualification remains outstanding. The PR's published checks cover security scanning, not these local HIP runs.

## Summary

The existing tests cover the basic tensor wait, cross-wave sharing, partial waits, empty transfers, and LDS footprints. The additions below exercise interactions between instruction families and longer sequences. The one existing oracle I would tighten is zero-fill: a race on an ordinary copied element can currently satisfy the test intended to check the zero-filled bytes.

The known detector limitations are included as TODO-marked tracking tests only. No emulator fixes are requested as part of this corpus review.

Locations below refer to `corpus/race/integration/hip_race_gfx1250_test.hip` on the proposal branch, unless a different file is named. Each new test group includes its entries in `corpus/race/integration/configs/gfx1250.json`.

## Actionable item

### Isolate the zero-filled bytes

**Commit:** [886c70c](https://github.com/newling/rocjitsu-test-corpus/commit/886c70c07eee575c8ab22665bb7a3915314d250b) — **location:** line 918 onward (original PR line 560 onward).

Restrict the consumer to the zero-filled half in both `tensor_load_zero_fill` and `tensor_load_zero_fill_cross_wave_race`. Otherwise an ordinary copied element can supply the expected race even if zero-filled writes are never registered. The synchronized control checks zeros. The earlier mutation experiment confirmed that the original oracle accepts omitted zero-fill footprints and this strengthened oracle rejects them.

## Additional coverage proposals

These are separate test ideas, not prerequisites for one another. They preserve the explicit-assembly style and keep safe controls paired with relevant missing-synchronization cases.

| Commit | Location | Test idea |
| --- | --- | --- |
| [0b45be4](https://github.com/newling/rocjitsu-test-corpus/commit/0b45be4792c2b9f962756ab3866d8d4712c6d120) | line 685 | Tensor load followed by tensor store from the same LDS bytes, with no intervening wait. Check the final global values; this complements the existing store→load case. |
| [b418c36](https://github.com/newling/rocjitsu-test-corpus/commit/b418c369dc48623fc6768c6d70a7153d84829a36) | line 516 | Two tensor loads to the same LDS destination. After draining, the newer data must win. A no-race assertion alone cannot establish this because LDS WAW checking is absent. |
| [72976c1](https://github.com/newling/rocjitsu-test-corpus/commit/72976c19bef06b9cd984047fa8c42df42871eee5) | line 739 | Older tensor store A, younger tensor load B, then `s_wait_tensorcnt 1`. DS may overwrite A, but reading B must still race. This tests a mixed load/store FIFO. |
| [5266850](https://github.com/newling/rocjitsu-test-corpus/commit/5266850e2272dac151df8a49bb995e51b3769fe1) | line 587 | Ordinary async load to LDS followed by tensor store. ASYNCcnt wait makes it safe; a TENSORcnt wait must not retire the ordinary async transfer. |
| [ae3d8a3](https://github.com/newling/rocjitsu-test-corpus/commit/ae3d8a3c744d060992394f1831cc5182119d97d8) | line 432 | A tensor store reads two partially in-bounds rows, leaving LDS holes. Concurrent DS writes into a hole must be accepted; writes into adjacent real source data must race. |
| [c4096a1](https://github.com/newling/rocjitsu-test-corpus/commit/c4096a1158188fa7d44d8b8704cbab2cb36ff8a3) | line 1133 | One tensor instruction has two iterations and disjoint LDS ranges. Combine it with another instruction and partial waits to check whole-instruction retirement and prevent extra counter tokens per iteration/range. |
| [80fb61e](https://github.com/newling/rocjitsu-test-corpus/commit/80fb61e320529b62d21bbb770fb37edd9fffccd2) | line 229 | Ordinary global-load→DS-store producer with split workgroup barriers. Delay either wave, execute ALU work between signal and wait, and reuse LDS across three rounds. Missing-DScnt and missing-rendezvous controls must race. |
| [60be4d8](https://github.com/newling/rocjitsu-test-corpus/commit/60be4d8640069950d2a8d17e77028e98f1404f3d) | line 872 | Tensor-load producer and tensor-store consumer in different waves. Exercise either delayed wave and separately omit the tensor wait or workgroup barrier. |

## TODO-marked issue trackers

Each tracker has a synchronized control with data assertions. The tracker checks the specific current limitation, not any failure: HIP errors, malformed logs, and unexpected diagnostics still fail the test. If the limitation disappears, the tracker fails so its TODO and expectation can be updated.

| Commit | Location | Tracked issue and eventual expectation |
| --- | --- | --- |
| [08f4a0e](https://github.com/newling/rocjitsu-test-corpus/commit/08f4a0e423de63abfdc59ffa4f7fedf092a42cbd) | line 1253 | `tensor_load_then_async_store_known_false_negative`: an ordinary `global_store_async_from_lds_b32` consumes an unwaited tensor load. The existing async-store path does not expose its LDS read. The test retains the required race description and checks that the matcher currently fails specifically with no race. TODO: use `ExpectRace(required)` when the LDS source is tracked. |
| [fb979aa](https://github.com/newling/rocjitsu-test-corpus/commit/fb979aa95003860582d71c4ff471c8aeaa04b667) | line 1025 | `tensor_load_lds_barrier_phase_known_false_positive`: the consumer observes an LDS-barrier phase and gets correct data, but the detector reports one tensor→DS-read race. Require exactly that report for now. TODO: use `ExpectNoRace()` once phase synchronization is understood. Workgroup-barrier and unsynchronized controls are included. |
| [63396c8](https://github.com/newling/rocjitsu-test-corpus/commit/63396c89e019e523c63646ca970ec0989e61688c) | line 346 | `tensor_load_then_ds_write_known_false_negative`: tensor load and DS write overlap, with only a final drain. The required WAW report is currently absent. TODO: use the retained race expectation when LDS WAW detection exists. |
| [ea5cb52](https://github.com/newling/rocjitsu-test-corpus/commit/ea5cb52927a28ba5a27caea38cf9030e5324a629) | `corpus/race/integration/hip_race_gfx950_test.hip:1034` | Independent gfx950 DTL-buffer-load→DS-write WAW tracker, with entries in `configs/gfx950.json`. The same missing report was reproduced on plain Systems develop, independently of the tensor stack. This commit is optional for gfx1250 bring-up and can also be taken separately. |

The false-negative trackers compare the existing matcher's failure message against `expected at least one race, got none`; they do not require new expected-failure machinery or skip execution. The false-positive tracker requires exactly one report with the expected kernel, wave, lane, and producer/consumer instructions. Racy output values are deliberately not asserted.

## Commentary

The split-barrier delays perturb scheduling and exercise both schedules in the emulator; they are not a hardware guarantee about which wave arrives first. These tests cover the built-in workgroup barrier, not named or cluster barriers.

The earlier partial-byte implementation defect is already fixed in the updated Systems stack and is not re-raised here. Counter-capacity ideas are excluded until there is an independently established architectural bound. Genuine deferred-hook tests belong in Systems and depend on the new hook contract; they are not part of this HIP series.

The full proposal branch is a convenient combined view. The commit table is the cherry-pick menu; no production change, shared harness refactor, or other proposal commit is required by any entry.
