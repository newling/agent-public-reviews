This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#16148](https://github.com/ROCm/rocm-systems/pull/16148)

**Reviewed head:** `4d612756ff5461bd22e1df47165ce0300db86e7c`.
**Recorded base:** `7c9e64779ad85c4bff50dd4d1cab65e873b55588`; Git merge base `7703e76e31af41d3562c9ba50b58c09f11bad4da`.
**Mode and scope:** independent correctness/design review of all 26 changed files, including hooks, detector state and retirement, mixed FLAT/tensor interactions, tests, and documentation. The cell-specific change was isolated against `3008f3661007b5c02b364863e34b5e17195480de`, the last split-barrier prerequisite commit from [#16020](https://github.com/ROCm/rocm-systems/pull/16020). Historical discussions and reviews were considered as requested; this PR's existing discussion was not read. The remote head was unchanged at the final metadata check.

**Suggestion branch:** [review/pr16148-suggestions](https://github.com/newling/rocm-systems/tree/review/pr16148-suggestions), based directly on the reviewed head. [Compare both suggestions against that head](https://github.com/newling/rocm-systems/compare/4d612756ff5461bd22e1df47165ce0300db86e7c...bc8e282e0f8f2d73f1a7bfd94047e31aa725c231).

| Commit | Review item |
| --- | --- |
| [6c6cdebc8d9](https://github.com/newling/rocm-systems/commit/6c6cdebc8d9508db10854babc01e7a0d6ff466a6) | Suggestion 1: arrival documentation |
| [bc8e282e0f8](https://github.com/newling/rocm-systems/commit/bc8e282e0f8f2d73f1a7bfd94047e31aa725c231) | Suggestion 2: test-helper conventions and include |

The actionable ordering finding remains unimplemented; its reproducer and implementation boundary are below.

## Tests

The submitted head builds the native tests, launcher, static/shared runtime, CLI library, and dynamic race plugin. **1,088 focused native tests and all 22 companion HIP cell cases pass.** Twelve additional native cases and twelve HIP cases each pass eight controls and fail four cases that expose the same missed race. The suggestion branch rebuilds the native tests and passes the same 1,088-test selection; changed files pass pre-commit and whitespace checks. Suggestions change documentation and test declarations, with no detector behavior change.

Native validation used Clang 23.1, Release/NDEBUG, Ninja, and the existing `-Wno-error=unused-template` configuration. HIP used ROCm SDK `10.1.0a20260812`, `-O2`, gfx1250 functional emulation, and the matching submitted runtime/plugin. [Sources, commands, controls, and limits](pr16148/reproduce.md) are preserved. Hardware, sanitizers, performance, and exhaustive schedules were not tested. The final policy check [timed out waiting for required checks](https://github.com/ROCm/rocm-systems/actions/runs/44834209797); there was no native CI result for this head to add to the local evidence.

## Summary

This extends the split-barrier clock model to a memory-resident synchronization object. The simulator owns actual arrivals and phase completion; the plugin decides which completed or pending accesses an arrival can publish. Separate handoff components for DS, async loads, and tensor transfers let a consumer acquire an access while preserving the producer's outstanding counter and register dependencies.

The issue/completion separation established in [#14687](https://github.com/ROCm/rocm-systems/pull/14687), [#14688](https://github.com/ROCm/rocm-systems/pull/14688), [#14689](https://github.com/ROCm/rocm-systems/pull/14689), and [#15391](https://github.com/ROCm/rocm-systems/pull/15391) remains useful here: tensor arrivals attach to their transfer's event and share its one counter slot, including transfers with no payload bytes. The new observation also follows the ownership boundary from [#16232](https://github.com/ROCm/rocm-systems/pull/16232). Hook tests exercise per-lane arrivals, EXEC zero, tensor loads/stores, and deferred transfers.

One granularity mismatch remains: the simulator reports an arrival per lane, while the detector hands off the entire arriving instruction at the first lane's callback. Different cells touched by sibling lanes need independent ordering.

## Actionable items

### 1. Keep sibling lanes' cell arrivals independent

At [`core/wave_race_state.cpp:523`](https://github.com/ROCm/rocm-systems/blob/4d612756ff5461bd22e1df47165ce0300db86e7c/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp#L523), `handOffPending()` stamps an entire instruction event. [`barrierCellArrived()`](https://github.com/ROCm/rocm-systems/blob/4d612756ff5461bd22e1df47165ce0300db86e7c/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp#L369) invokes it for each lane's callback. The current arrive event already contains every active lane's cell interval, so its first arrival publishes all of those intervals through that lane's cell.

A two-wave counterexample is:

```text
setup: C0 and C1 each require one arrival; synchronize initialization

producer, one arrive instruction:       consumer:
    lane 0 -> C0                           poll C0 until its phase changes
    lane 1 -> C1                           plain store to C1
```

The plain store can overwrite the arrival at C1. Observing C0 establishes completion of its own arrival, without establishing completion of the sibling lane's arrival at C1. CDNA5 ISA revision 27 July 2026, §§11.2.1–11.2.2, defines per-lane atomic updates and does not order those siblings. Section 5.7.1.4's LDS instruction ordering supports publishing earlier instructions, but supplies no such dependency between lanes of the current instruction. See the [authoritative ISA](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf).

Both the decoded-instruction probe and full HIP emulation miss this race for **both DS arrival forms and both lane-to-cell assignments**. All four failures are specifically an absent LDS race report. The controls establish the boundary:

| Consumer action before overwriting C1 | Expected | Observed |
| --- | --- | --- |
| No poll | Race | Race |
| Poll only C0 | Race | No race |
| Poll C1 | Clean | Clean |

The suppression occurs in [`handedOffTo()`](https://github.com/ROCm/rocm-systems/blob/4d612756ff5461bd22e1df47165ce0300db86e7c/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp#L350): acquiring C0 satisfies the single handoff stamp of the whole event, so validation skips its C1 bytes too. The submitted multi-lane hook tests verify callback delivery; the detector assertions do not combine distinct cells in one instruction with polling only one of them.

**Needed change:** distinguish the ordered prefix of earlier instructions from the current instruction's independent per-cell arrivals. Acquiring one cell must cover only the arrivals ordered through that cell, while preserving one wait-counter token per instruction. Retain both safe-cell and no-poll controls, and exercise both lane assignments; assigning increasing prefix epochs to sibling lanes would still over-acquire when the consumer observes the later sibling.

**Implementation omitted:** the existing per-event `handoffKind`/`handoffEpoch` cannot express a partial handoff of an instruction's cell intervals. Excluding the whole current instruction would instead report false conflicts when the consumer overwrites the cell it actually polled. A sound fix needs a decision about per-cell ordering state and its event lifetime, so no speculative functional change is included. The exact [native source](pr16148/multicell_probe.cpp), [HIP source](pr16148/multicell_probe.hip), and [reproduction setup](pr16148/reproduce.md) remain available independently of the suggestion commits.

## Suggestions

### 1. Align the arrival documentation with both tensor directions

[`execution_plugin.h:318`](https://github.com/ROCm/rocm-systems/blob/4d612756ff5461bd22e1df47165ce0300db86e7c/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/execution_plugin.h#L318) and [`docs/plugins.md:630`](https://github.com/ROCm/rocm-systems/blob/4d612756ff5461bd22e1df47165ce0300db86e7c/emulation/rocjitsu/docs/plugins.md#L630) describe the tensor arrival as following LDS writes. Tensor stores read LDS and also emit this hook. **Implemented in [6c6cdebc8d9](https://github.com/newling/rocm-systems/commit/6c6cdebc8d9508db10854babc01e7a0d6ff466a6):** describe the transfer's LDS accesses in both API documents and the corresponding test comment. The same documentation cleanup moves the `anyCheckedAttachedRead()` comment back onto that declaration in [`core/race_detector.h:317`](https://github.com/ROCm/rocm-systems/blob/4d612756ff5461bd22e1df47165ce0300db86e7c/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.h#L317); it was attached to the intervening `attachLdsRead()` declaration.

### 2. Follow the test fixture convention and declare the stream dependency

[`tests/cdna5_tensor_dma_test.cpp:3664`](https://github.com/ROCm/rocm-systems/blob/4d612756ff5461bd22e1df47165ce0300db86e7c/emulation/rocjitsu/tests/cdna5_tensor_dma_test.cpp#L3664) introduces a fixture with methods as a `struct`; the local contribution guide uses `class` for such types. The new printer in [`tests/cdna5_sim_test_common.h:368`](https://github.com/ROCm/rocm-systems/blob/4d612756ff5461bd22e1df47165ce0300db86e7c/emulation/rocjitsu/tests/cdna5_sim_test_common.h#L368) uses `std::ostream` through transitive includes. **Implemented in [bc8e282e0f8](https://github.com/newling/rocm-systems/commit/bc8e282e0f8f2d73f1a7bfd94047e31aa725c231):** use a class fixture with protected helpers and include `<ostream>` directly. This is optional source hygiene; the submitted build already succeeds.

## Scope decisions

The accepted 32-bit epoch representation and scheduling-dependent counted-barrier model from [#16020](https://github.com/ROCm/rocm-systems/pull/16020) are retained. In that model, scheduling can select which signals contribute to a round. In the counterexample above, C0 always has the same sole contributing lane; the erroneous acquisition extends beyond that phase to C1's independent arrival.

The documented value-insensitive cell acquisition policy and conservative same-wave/tensor-versus-async rules are also retained. The counterexample actually waits for the completed phase, so it works within those stated policies. The multi-wave retention and empty-versus-ignored instruction decisions from [#15419](https://github.com/ROCm/rocm-systems/pull/15419) and [#15486](https://github.com/ROCm/rocm-systems/pull/15486) remain intact.

[Cell support (#15039)](https://github.com/ROCm/rocm-systems/issues/15039) is the scope of this change. The existing [barrier-state/flag polling issue (#16236)](https://github.com/ROCm/rocm-systems/issues/16236) and [LEAVE ordering issue (#16237)](https://github.com/ROCm/rocm-systems/issues/16237) continue to track their separate synchronization protocols.

The published suggestion branch contains the two optional commits mapped above. The functional finding remains open, with native and HIP sources and reproduction instructions published alongside this review. Validation and its limits are recorded in Tests above; the suggestion commits do not implement the ordering fix.
