This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#14687](https://github.com/ROCm/rocm-systems/pull/14687)

**Reviewed head:** `7e586005f1c5b5b478ab3a9d5cc00397b4491d2c`.

**Scope:** Follow-up informed by all preceding reviews, including [the latest submitted review](https://github.com/ROCm/rocm-systems/pull/14687#pullrequestreview-5758419128), and the issue-hook rewrite. The items below add test findings and a simplification; they do not repeat the existing design, documentation, naming, or corpus-test proposals.

**Suggestion branch:** [review/pr14687-followup-20261103](https://github.com/newling/rocm-systems/tree/review/pr14687-followup-20261103), based on the reviewed head. These are test-only commits; each applies independently to that head. The three commits are published separately from the PR.

| Commit | Item |
| --- | --- |
| [a029fcadb97](https://github.com/newling/rocm-systems/commit/a029fcadb97) | Separate retirement assertions from already-reported races |
| [28957eef9d0](https://github.com/newling/rocm-systems/commit/28957eef9d0) | Cover validation of a newly issued tensor store against earlier LDS writes |
| [901f85e1ee7](https://github.com/newling/rocm-systems/commit/901f85e1ee7) | Consolidate saved-PC coverage in the decoded retry test |

## Tests

Clang 23.1 Release: the submitted head's earlier focused tensor/race/perfsim run passed 340 tests; the final suggestion branch passes 343, with the same one external-perfsim-backend skip. The CLI, shared runtime, race module, and tests build successfully; changed-file pre-commit hooks pass.

The external backend comparison is unconfigured. No new HIP corpus, hardware, or sanitizer campaign was run. The reviewed head's Release, ASan/UBSan, TSan, and GCC UBSan CI jobs are passing. The deliberately broken variants below are test-sensitivity experiments, not failures of the submitted implementation; all mutations were removed.

## Summary

The new issue hook gives race bookkeeping its own notification point while preserving the separate completion observer. The tests exercise the producer's footprint, the plugin's translation into events, and the core's ordering rules. Those layers are useful, but similar scenarios at different layers do not necessarily protect the same implementation branch. This pass found two specific weaknesses in the plugin tests and one opportunity to remove duplicate pipeline-test setup. It did not identify a new production correctness defect.

Paths and line numbers below refer to the reviewed head, relative to `emulation/rocjitsu/`.

## Actionable items

### Keep retirement assertions independent of report suppression

**Locations:** `tests/execution_plugin_race_test.cpp:563` and `:571`; report suppression in `lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp:314`.

The load and store retirement tests first cause a race involving the tensor instruction, then wait, synchronize, and require a later DS access to produce no report. However, the logger suppresses subsequent reports involving either instruction from a previously reported race. Changing the consumer PC is insufficient because the tensor instruction's PC is already recorded. Silence at the end of these tests therefore does not establish retirement.

Replacing the fixture's barrier helper with `void barrier() {}` leaves all nine submitted `TensorDmaRaceTest` cases passing, including both tests claiming to cover retirement. With `a029fcadb97`, the same mutation fails both retirement tests. Restoring the helper makes them pass.

The commit puts the unwaited and synchronized probes in separate test fixtures. This preserves the negative controls while ensuring the synchronized checks use a tensor instruction that has not already participated in a reported race. No change to production deduplication is needed.

### Cover the store side of issue-time validation at the plugin boundary

**Locations:** `tests/execution_plugin_race_test.cpp:586`; store validation in `lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp:539`; the separate core-test implementation in `tests/race-detector/race_test_builder.h:343`.

The plugin tests check a new tensor load against an older pending DS read. Their store cases instead register the tensor store first and probe it later with a DS write. Those store cases establish event registration, not validation of the store's own LDS read when it issues.

The core suite covers the latter ordering, but `RaceTestBuilder::tensorTransfer` calls `validateRead` itself. It bypasses the plugin branch that needs protection. Deleting the store-side `detector->validateRead(...)` call from `onAmdgpuTensorDmaIssued` leaves the existing tensor core and plugin tests green. The companion HIP suite has a related scenario, but it does not replace this missing native adapter check.

`28957eef9d0` adds a pair differing by a DScnt wait: an earlier same-wave DS write followed by a tensor store must report an LDS read race; completing that DS write first must be accepted. The negative case also checks the tensor-store instruction and lane-less attribution. Under the mutation, the new negative fails because no race is reported, while the waited control passes. Both pass with the submitted implementation restored.

## Suggestions

### Keep the decoded saved-PC regression and remove the manually seeded duplicate

**Locations:** `tests/gpu_vm_pipeline_test.cpp:2541` and `:2601`.

`DeferredTensorLoadReportsInstructionPcAtCompletion` builds internal transfer state and sets its saved PC directly. The newer `DeferredTensorLoadIssuesOnceAndCompletesAtItsInstructionPc` executes a decoded instruction through `ComputeUnitCore::step`, forces unavailability, and checks the eventual completion PC. It covers the real saved-PC assignment as well as delivery.

`901f85e1ee7` adds explicit checks that the architectural PC advances past the tensor instruction while the wave is in `VM_RETRY`, and that the wave returns to `RUNNING`. It then removes the older manually seeded test and its private observer. The independent partial-load/barrier and store-snapshot retry tests remain intact.

As a sensitivity check, deleting `state->pc = wf.pc` from `execute_tensor_dma` makes the retained decoded test fail with completion PC `0` instead of `0x1000`. Restoring the assignment passes. This simplifies the tests without dropping the saved-PC fix or its regression coverage.

## Commentary and handoff

I would keep the separate core, observation, and plugin test layers. The second finding demonstrates why a core test is not redundant with its adapter counterpart: the core helper can remain correct while the production adapter loses a call. The simplification above removes duplicate coverage within the pipeline layer instead.

All three suggestions are implemented on `review/pr14687-followup-20261103`, ending at `901f85e1ee7`. The final diff touches only the two test files. No production behavior, previously published review, or corpus proposal was changed. Existing limitations and previously proposed broader retry/footprint cases remain separate follow-up work rather than being presented again as new findings here.
