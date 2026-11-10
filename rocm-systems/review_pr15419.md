This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#15419](https://github.com/ROCm/rocm-systems/pull/15419)

**Reviewed head:** [`8d32b85223ab5e8afb28efba07847f7e76687abe`](https://github.com/ROCm/rocm-systems/commit/8d32b85223ab5e8afb28efba07847f7e76687abe). **Diff base:** [`bd1130f9f838cfffd24f41fd3052968fb7cae4e0`](https://github.com/ROCm/rocm-systems/commit/bd1130f9f838cfffd24f41fd3052968fb7cae4e0), the merge base with `develop` at `cf75f8d0a2452a5d8f73da7349ea8e41c18cf278`.

**Mode and scope:** Independent review of all seven changed files, including counter completion, LDS event retirement and trimming, workgroup wave-count construction, plugin dispatch/termination paths, documentation, and regression coverage. Existing PR reviews and discussion were not consulted.

**Suggestion branch:** [review/pr15419-suggestions](https://github.com/newling/rocm-systems/tree/review/pr15419-suggestions), based directly on the reviewed head. Commit [`55e02a665c9`](https://github.com/newling/rocm-systems/commit/55e02a665c96ec808ab191ab636e1716d1c9f04b) implements suggestion 1 below and changes comments/documentation only.

## Tests

The submitted head and suggestion commit both build with Clang 23.1 in Release mode and pass all 396 focused race-detector, wait-hazard, registry, interval, and diagnostic tests. The selection includes all five new tests and the modified plugin tests. Pre-commit passes across the PR and suggestion files. The reused build has `-Wno-error=unused-template` for an existing warning in the unchanged `util_intrusive_shared_ptr_test.cpp`.

Two temporary mutations verify that the new tests distinguish the intended behavior: disabling early retirement fails four of the five new tests; applying it to every workgroup fails three, including the cross-wave hazard test. Both mutations were removed before the final build and test run.

No HIP corpus, full CTest suite, sanitizer run, or independent timing benchmark was performed. The loop test verifies bounded live history directly; this review does not independently establish the motivation's timing figures. At the review-time CI snapshot on 2026-11-09, formatting, handbook, and policy checks passed; the rocjitsu release and sanitizer jobs were queued.

## Summary

The change removes LDS history at a point where the existing same-wave validator already considers the event safe. `satisfyEventWaitCounter` still requires every counter obligation to complete before register references are removed and the event can be retired. Thus the optimization retains pending async and mixed-counter dependencies while avoiding repeated scans of completed events in long single-wave loops.

The wave count comes from the complete workgroup dispatch and remains fixed when waves halt. A multi-wave workgroup therefore cannot accidentally enter this path after a peer exits. Immediate retirement uses the existing list removal and byte-count bookkeeping, and avoids placing retired event IDs in the barrier queue before registry trimming. The tests cover both LDS read and write events, partial waits, capacity backpressure, trimming, and cross-wave visibility until a barrier.

## Actionable items

None. No correctness defect was found in the reviewed change.

## Suggestions

### 1. Update the remaining barrier-only lifecycle descriptions

In [`event_registry.h:25`](https://github.com/ROCm/rocm-systems/blob/8d32b85223ab5e8afb28efba07847f7e76687abe/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/event_registry.h#L25) and its `markRetired` comment at line 96, retirement is still described as occurring at `s_barrier`. The `EventId` lifecycle comment repeats that restriction, and the handbook's **RETIRED** entry starts by asserting that a barrier has occurred before describing the new exception. These descriptions can mislead someone tracing why a single-wave event has disappeared without a barrier.

Commit [`55e02a665c9`](https://github.com/newling/rocm-systems/commit/55e02a665c96ec808ab191ab636e1716d1c9f04b) describes retirement by its effect and distinguishes the single-wave and multi-wave paths. It also removes the redundant decorative banner above the new tests, following the project's comment guide. This is optional documentation cleanup; runtime behavior and test assertions are unchanged.

The published suggestion branch contains one commit, mapped to suggestion 1. No implementation findings remain unaddressed. The validation limits are recorded above. A complete [patch](patches/pr15419-55e02a665c9.patch) also accompanies this review and applies from the repository root at the reviewed head.
