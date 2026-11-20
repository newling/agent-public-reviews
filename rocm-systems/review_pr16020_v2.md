This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#16020](https://github.com/ROCm/rocm-systems/pull/16020)

**Reviewed head:** `a8ddb735d6d7f702c89b52e701536c10d90496d2`

**Exact prerequisite/base:** `be6967726f0b572094068793a6ed9e0586ec1c7e`, from [#16232](https://github.com/ROCm/rocm-systems/pull/16232). This review uses the submitted stack; the prerequisite's subsequently added instruction tests are not silently substituted for that base.

**Mode and scope:** Follow-up independent review of all 13 changed files, with explicit permission to consider prior reviews. Focus: unusual signal/wait protocols, schedule-dependent ordering, wave termination, finite counter boundaries, and the core algorithm. No production simulator file changes in this PR.

**Suggestion branch:** [review/pr16020-v2-suggestions](https://github.com/newling/rocm-systems/tree/review/pr16020-v2-suggestions), based directly on the reviewed head. Commits: [e6494e3c86e](https://github.com/newling/rocm-systems/commit/e6494e3c86e9c3a96e076a43f220c87809351d28) implements actionable item 1; [d6d6845216a](https://github.com/newling/rocm-systems/commit/d6d6845216a2df7623635e0934dca1446bd11257) implements suggestion 1. [Complete suggestion diff](https://github.com/newling/rocm-systems/compare/a8ddb735d6d7f702c89b52e701536c10d90496d2...d6d6845216a2df7623635e0934dca1446bd11257).

This supplements the [previous posted agent review](https://github.com/newling/agent-public-reviews/blob/7bc00b1ad7add698d2f5f39be52e6f7a470e74e0/rocm-systems/review_pr16020.md), which is preserved unchanged. Its address-range optimization, documentation corrections, and include suggestion are not repeated here. Those suggestions have not been incorporated into this head. The detector core is unchanged from the earlier reviewed `ce03b0dc1913a03e31b7040029476d119510a6f3`; the rebase's relevant plugin difference is the upstream conversion from mnemonic comparisons to operation enums. Earlier requests concerning rejoined waves retaining old rounds, skipping acquired history, and armed versus merely notified waves remain addressed in the submitted implementation. Simulator callback/duplicate-cluster-signal concerns belong to the prerequisite.

## Tests

The submitted head passed **886 relevant native tests**. The suggestion branch passed **891**, including two new tests and three existing registry/history tests added to the selection. All **50 tests added by this PR** ran and passed. The native executable, launcher, shared runtime, hooks, and dynamic race plugin build with Clang 23.1, Release/NDEBUG, and Ninja. The existing local `-Wno-error=unused-template` configuration remains in use for unrelated compiler warnings. Changed files pass pre-commit and whitespace checks.

New independent experiments:

- **Actual 32-bit epoch boundary:** `UINT32_MAX` signals followed by one completed LDS write and an unsynchronized cross-wave read. The submitted detector misses the race; the suggestion reports it. No private state modification or reduced-width substitute was used.
- **534 exhaustive schedules of five small producer/consumer programs:** both implementations agree with an independent access-token oracle on all 1,968 memory checks. The threshold-1, one-output program has both clean and racing schedules; the two-output program always reports a race. Correct thresholds, including two signals from A plus three from B, are clean.
- **Termination and interleaved workgroup rounds:** the submitted detector agrees with **7,784,726 access checks**, across 2, 3, 4, 16, and 32 waves, with 200 seeds and 800 actions per seed. Unlike the prior review's oracle, workgroup signals and waits are separate actions here. The 4- and 32-wave configurations also pass with assertions and ASan/UBSan at both submitted and suggested revisions: 3,491,592 checks per revision.
- **12 fresh-process gfx1250 HIP cases**, at both submitted and suggested runtime revisions, produce the expected reports and defined outputs: threshold selection, an exit-mediated A → B → C relay and two negative controls, and 32 buffer reuses with ready threshold 5 / acknowledgment threshold 1. These are functional-emulation results, not hardware measurements.

The exact sources, commands, case table, and validation limits are in [the experiment appendix](pr16020-v2/reproduce.md). The portable HIP runner was also exercised against the final build. A preliminary run with an older shared runtime beside the rebuilt plugin was discarded and is excluded from these results. The exact-head ASan/UBSan, GCC UBSan, TSan, and pre-commit CI checks passed when inspected; unrelated multi-architecture MIOpen failures are not findings against this change.

## Summary

The vector-clock approach holds up under the noncanonical protocols explored here. Signals can contribute repeatedly to a counted round; different waves can acquire different generations; and an exiting wave can carry ordering that it acquired from another producer. The detector's result matched a reference model that retains individual access tokens rather than implementing the same epoch/retirement algorithm.

The new correctness problem is the finite representation of those epochs. The algorithm needs a monotonically increasing value, but a wave can advance its 32-bit value independently of memory-event allocation. A signal-only loop can therefore break ordering without exhausting the event registry or accumulating a large history. Widening the common epoch representation is a small change that preserves the algorithm.

A separate coverage boundary deserves an explicit explanation: counted barriers can make **which producer was acquired** depend on scheduling. The current algorithm records that choice accurately for the observed execution. A clean result does not check the other possible choices.

## Actionable items

### 1. Preserve epoch ordering beyond the 32-bit signal boundary

At [`core/race_detector.cpp:171`](https://github.com/ROCm/rocm-systems/blob/a8ddb735d6d7f702c89b52e701536c10d90496d2/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp#L171), every counted signal increments the wave's current epoch. The matrix entries, round clocks, coverage values, and event stamps are `uint32_t`. Epoch zero is reserved, and [`forEachUnacquiredLdsEvent()`](https://github.com/ROCm/rocm-systems/blob/a8ddb735d6d7f702c89b52e701536c10d90496d2/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp#L357) assumes the completed history is monotonically ordered by epoch.

A two-wave counterexample is:

```text
A: signal a named barrier UINT32_MAX times
   // threshold 127, no joined listeners; no memory events in this loop
   ds_store_b32 [64], value
   s_wait_dscnt 0

B: ds_load_b32 value, [64]  // no barrier acquisition at all
```

Starting from epoch 1, A reaches zero after those signals. Its LDS write completes with epoch zero. `stampReleaseEpoch()` removes the event from the in-flight write list; the completed-history scan then stops because `0 > B.acquired[A]` is false. The conflicting read receives **no race report**.

The [minimal probe](pr16020-v2/epoch_wrap_probe.cpp) executes all 4,294,967,295 signals through the real detector API. At the submitted head it prints:

```text
completion_epoch=0 expected_races=1 actual_races=0
```

This is introduced by the new epoch representation. It does not rely on the pre-existing event-ID limit: the reproducer allocates just one memory event. It requires an unusually long signaling lifetime, so it is not evidence that ordinary short kernels are affected. The optimized core reproducer took 18.473 seconds; that is not a full-kernel emulation timing.

**Implemented in [e6494e3c86e](https://github.com/newling/rocm-systems/commit/e6494e3c86e9c3a96e076a43f220c87809351d28):** introduce a shared `BarrierEpoch = uint64_t` and use it consistently for event stamps, acquisitions, round clocks, coverage, retirement arguments, and sentinels. The original probe now prints epoch 4,294,967,296 and one race. A compact native regression verifies that an epoch above the 32-bit boundary survives both dense storage and transfer to retained sparse history. The full signal-to-acquisition boundary remains in the standalone probe, avoiding billions of iterations in routine debug test runs.

At 32 waves, the acquired matrix grows from 4 KiB to 8 KiB; round clocks, coverage, exit clocks, and event metadata also grow. This is a practical widening, not a proof that a finite counter supports an unlimited execution. Saturating the existing counter would be unsafe: an acquired saturated epoch could incorrectly cover later work. Modular comparison would require a bound on how far unacquired histories and old rounds can lag, which this design does not provide. Renormalizing every retained clock and event would add more machinery than the bounded widening.

## Suggestions

### 1. Explain that counted-barrier race coverage can depend on signal order

At [`docs/race-detector.md:400`](https://github.com/ROCm/rocm-systems/blob/a8ddb735d6d7f702c89b52e701536c10d90496d2/emulation/rocjitsu/docs/race-detector.md#L400), the new release/acquire explanation would benefit from distinguishing ordering in the observed execution from ordering across other legal schedules.

Consider two independent producers. A completes a write to X and signals Ready; B completes a write to Y and signals Ready. C joined Ready before either could complete it, waits once, and reads only X. Ready has threshold 1. Its first completion can carry A or B:

| Program | Legal schedules enumerated | Clean | Race reported |
| --- | ---: | ---: | ---: |
| Threshold 1, C reads only X | 148 | 74 | 74 |
| Threshold 1, C reads X and Y | 220 | 0 | 220 |
| Threshold 2, C reads only X | 20 | 20 | 0 |
| Threshold 2, C reads X and Y | 20 | 20 | 0 |
| Threshold 5, A signals twice and B three times, C reads both | 126 | 126 | 0 |

These counts enumerate issue-order traces of the specified small programs; they are not probabilities. The oracle records individual released access tokens. It also preserves the first completion bit when another round completes before C waits.

The HIP counterpart uses a delay before either producer's signal, with no flag handoff and unchanged LDS accesses. Delaying A produces a race on X; delaying B produces a clean read of X. Reading both tiles reports one race under either perturbation. Raising the threshold to 2 makes all four variants clean.

This is a different phenomenon from reversing a fixed unordered read/write pair under ordinary workgroup barriers: there, reversing execution order changes RAW to WAR while the synchronization relationship remains the same. Here the contributing producer itself changes. The claim is limited to those fixed paths and addresses, not a universal determinism statement about gfx950.

**Implemented in [d6d6845216a](https://github.com/newling/rocm-systems/commit/d6d6845216a2df7623635e0934dca1446bd11257):** add the concrete example and coverage limit to the barrier documentation, with a small native test that reverses producer order and checks both thresholds. This is an optional clarification of the supported model, not a demonstrated trace-ordering defect or a requirement to add a schedule explorer in this PR.

## Scope decisions

[Polling/flag handoffs (#16236)](https://github.com/ROCm/rocm-systems/issues/16236) and [LEAVE ordering (#16237)](https://github.com/ROCm/rocm-systems/issues/16237) remain separate follow-ups. Neither is a new requirement here. The new scheduling example uses ordinary counted signals and waits, so it does not depend on either limitation. The previous review's history-scan performance finding also remains separate; no general history-compression or richer address-summary implementation is added in this follow-up.

A schedule explorer could expose alternate contributing signal sets, but that would change the detector's analysis contract and involve the simulator. Joining every possible producer into one optimistic clock would hide races. Requiring every hypothetical producer in the current trace would instead report some valid, deliberately selective protocols. The bounded change here documents what the existing trace analysis establishes. Future exploration should preserve that distinction.

## Commentary

### Wave termination carries acquired ordering, without retiring it for everyone immediately

The most useful additional HIP case is this three-wave protocol, after initialization and an initial setup barrier:

```text
A                                  B                       C
s_barrier_signal -1                wait named AB            s_barrier_signal -1
write X                            s_endpgm                  s_barrier_wait -1
s_wait_dscnt 0                                              read X
signal named AB                                             signal named Ack
wait named Ack
s_barrier_wait -1
```

A joins Ack; B joins AB. Both named barriers have threshold 1. A's workgroup signal precedes its write, so that signal cannot release X. B's successful named wait acquires X, and B's termination substitutes for its workgroup signal. C's workgroup wait therefore acquires the ordering carried by B's exit. Ack keeps A alive until after C's read, ruling out an accidental release through A's own termination.

The submitted PR reports no race and produces the expected data. Moving A's drain after its named signal, or removing B's named wait, produces an LDS RAW report. The generated ISA confirms the intended placement of the drain, signal, wait, and `s_endpgm` instructions. This supports retaining the **whole acquired row** in the exit clock, rather than recording only the exiting wave's own epoch.

The independent termination oracle also checks reads before and after individual waits while other waves end. It found no mismatch in the live-wave coverage/retirement bookkeeping. It deliberately avoids using signal-then-exit as a valid workgroup protocol: the local [CDNA5 ISA, 27 July 2026, §5.6](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf) explicitly warns against that pattern. Existing defensive handling of it is not used to manufacture a new requirement.

### Keep the compact vector-clock representation

The alternative access-token model is useful as an independent oracle, but each signal/wait union grows with the number of retained accesses. The current per-wave clock instead summarizes a completed prefix of each producer's timeline. Given the supported maximum of 32 waves, the dense matrix is small, and max-based acquisition preserves the transitive relationships exercised above. A single global epoch would lose the distinction between independently acquired producers. Per-round event lists would duplicate references across repeated signals and relays and complicate retirement.

The minimum-coverage bookkeeping is an optimization over scanning all live observers; the token oracle avoids it and still agrees. I found no experimentally supported replacement that is both simpler and preserves these cases. The counter-width fix fits the existing representation without adding a second ordering mechanism.

### File coverage and handoff

| Changed area | Files inspected | Main follow-up checks |
| --- | --- | --- |
| Detector core | `event_registry.h`, `race_detector.cpp`, `race_detector.h`, `types.h`, `wave_race_state.cpp`, `wave_race_state.h` | Epoch representation, signal/wait joins, old snapshots, completed-history scans, source-read retention, exit coverage, registry lifetime |
| Plugin | `plugin.cpp`, `plugin.h` | Counted callback wiring, tracked-wave filtering, halt/drain ordering, per-workgroup handling of cluster callbacks, enum conversion after rebase |
| Tests | `execution_plugin_race_test.cpp`, `race_detector_event_registry_test.cpp`, `race_detector_tests.cpp`, `race_test_builder.h` | Existing expectations and all 50 additions, test-builder versus simulator responsibilities, independent new probes |
| Documentation | `docs/race-detector.md` | New model's guarantees and the scheduling coverage boundary; earlier documentation findings left in the first review |

The [suggestion branch](https://github.com/newling/rocm-systems/tree/review/pr16020-v2-suggestions) is published at [d6d6845216a](https://github.com/newling/rocm-systems/commit/d6d6845216a2df7623635e0934dca1446bd11257), with one commit for the epoch fix and one for the scheduling explanation/test. The new [experiment sources and portable commands](pr16020-v2/reproduce.md) accompany the report. No simulator change, exhaustive scheduler, hardware validation, or new implementation of the existing follow-up issues is claimed. All bounded changes proposed in this review are implemented in the linked commits.
