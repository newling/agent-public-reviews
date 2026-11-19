This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocjitsu-test-corpus#96](https://github.com/ROCm/rocjitsu-test-corpus/pull/96)

Reviewed head: `67e0ab9a15dcbc941d320811ae2dda4f398d7391`. Base: `671ddbf427a5bf20cfc1b0d48f2042ac57448b92`.

Mode: full review of the four-file corpus change, following an earlier kernel walkthrough and discussion of the flag-ordering concern. This includes the kernels, assertions, case registration, documentation, relevant harness behavior, and generated gfx1250 instructions. It is not a full review of the companion detector implementation.

Suggestion branch: [review/pr96-suggestions](https://github.com/ROCm/rocjitsu-test-corpus/tree/review/pr96-suggestions), based directly on the reviewed head and ending at [aadfa3e](https://github.com/ROCm/rocjitsu-test-corpus/commit/aadfa3e1a559693690ffb027902383ac2b6b1156). [Compare the two suggestion commits against the reviewed head](https://github.com/ROCm/rocjitsu-test-corpus/compare/67e0ab9a15dcbc941d320811ae2dda4f398d7391...aadfa3e1a559693690ffb027902383ac2b6b1156).

| Commit | Review item |
| --- | --- |
| [bb34747](https://github.com/ROCm/rocjitsu-test-corpus/commit/bb34747679ee9865ae47a610383850297c4ec40e) | Move both flag handshakes before the completion they must not communicate; update names, comments, and the reader-window race direction assertion. |
| [aadfa3e](https://github.com/ROCm/rocjitsu-test-corpus/commit/aadfa3e1a559693690ffb027902383ac2b6b1156) | Clarify counter-wait placement, workgroup termination, and the scope of the signal-then-exit case. Documentation/comments only. |

## Tests

All 22 added cases passed their programmed expectations at the submitted head and with the suggested executable changes: 10 clean cases and 12 expected-race cases. All 65 tests in `tests/test_race_suite.py` passed at the submitted and final suggestion revisions. Configuration discovery matches all 175 registered gfx1250 cases. The final comment-only commit does not change the tested instructions.

Execution used the race plugin and runtime from [ROCm/rocm-systems#16020](https://github.com/ROCm/rocm-systems/pull/16020), revision `7743ed6ebc3609c465daaf42aa5b3c1c5dfa58e3`, the shipped `gfx1250_mi455x.json` configuration, two CPU workers, and one filtered GoogleTest per process. Device code was built at the corpus's required `-O2` with ROCm SDK `10.1.0a20260812`; the runtime used Clang 23. Generated ISA was inspected before and after the flag changes.

Two independent detector mutations checked whether the tests reject the mistakes they are intended to cover. Each mutation was applied to the detector alone; simulator barrier behavior was unchanged.

| Deliberate detector mistake | Submitted corpus | Suggested corpus |
| --- | --- | --- |
| Sample each live wave's releases again at round completion | `split_barrier_ds_write_wait_after_signal_race` fails: expected one report, got zero. Other 21 cases pass. | Same result. |
| Acquire the released clock for all members at round completion, before their own waits | `split_barrier_reader_in_window_race` fails: expected one report, got zero. Other 21 cases pass. | Same result. |

These are targeted mutations of the companion PR, not runs of the entire old detector. They demonstrate regression sensitivity with the tested configuration; they do not establish behavior for every possible wave schedule. The appendix gives the exact mutations and launch setup.

Validation is through rocjitsu emulation, not physical gfx1250 hardware. Visible PR checks were security scans, not functional race-suite results. Passing an expected-race test does not independently validate its race expectation; the submitted flag cases illustrate that distinction.

## Summary

The change exercises both sides of split-barrier ordering: completing a memory operation before a signal, and issuing a dependent operation after a wait. It covers ordinary LDS reads/writes, tensor and async transfers, private work between signal and wait, later rounds, early wave termination, and buffer reuse. The paired transfer templates avoid repeating the same synchronization logic across instruction families. Clean cases validate output data; negative cases constrain the report count and relevant instruction/wave fields without prescribing values from raced accesses.

The principal correctness issue is that two negative tests publish a flag after the completion that makes their later read safe, then require the detector to report that read as racing. The suggestions move those publications earlier. This retains both targeted mutation failures in the tested configuration while removing the independent proof that the reads are safe.

All changed files were reviewed:

| File | Assessment |
| --- | --- |
| `corpus/race/integration/hip_race_gfx1250_test.hip` | 12 kernel definitions/templates and 22 cases checked against the local ISA and emitted instructions; flag issue and comment corrections below. |
| `corpus/race/integration/configs/gfx1250.json` | All 22 additions correspond to executable test names, with no duplicate or missing registration. |
| `tests/test_race_suite.py` | The 153-to-175 count change agrees with both source discovery and the configuration. |
| `README.md` | Coverage description matches the cases; the suggestion clarifies that signal-then-exit is an explicitly discouraged sequence. |

## Actionable items

### Keep flag publication ahead of the completion whose ordering is being tested

Locations at the reviewed head: [the writer's flag publication](https://github.com/ROCm/rocjitsu-test-corpus/blob/67e0ab9a15dcbc941d320811ae2dda4f398d7391/corpus/race/integration/hip_race_gfx1250_test.hip#L3447), [the middle wave's publication after its wait](https://github.com/ROCm/rocjitsu-test-corpus/blob/67e0ab9a15dcbc941d320811ae2dda4f398d7391/corpus/race/integration/hip_race_gfx1250_test.hip#L3586), and the shared claim that a flag orders nothing in LDS at line 3415.

In `split_barrier_ds_write_wait_after_signal_race`, the producer executes its LDS store, signals, executes `s_wait_dscnt 0`, and only then publishes `write_complete`. The consumer observes that flag before issuing its LDS read. The write is therefore complete before the read on every execution that gets past the polling loop. There is no later overwrite.

In `split_barrier_reader_in_window_race`, the ordering chain is:

```text
Wave 0: LDS write completes → signal
Wave 1: barrier wait passes → publish round_complete
Wave 2: observe round_complete → LDS read
```

Wave 2 has not executed its own barrier wait, but this flag protocol already ensures that its read follows the completed write. Requiring a RAW report here encodes the detector's inability to model that handoff as an actual race.

This conclusion is about the emitted ISA, not a claim that relaxed C++ atomics form a release/acquire pair. The inspected instructions preserve the explicit LDS completion, flag store, completed polling load, and branch guarding the read. [CDNA5 ISA, 27 July 2026, §5.7.1.4](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf) defines a completed LDS write as data having been written into LDS. Section 5.6 supplies the barrier completion rule used in the second chain.

**Implemented in [bb34747](https://github.com/ROCm/rocjitsu-test-corpus/commit/bb34747679ee9865ae47a610383850297c4ec40e):**

- Publish `writer_signaled` immediately after the writer's signal, before the late `s_wait_dscnt 0` in the race specialization. The clean specialization still completes the write before signalling.
- Publish `reader_signaled` after wave 1's signal and before its barrier wait. Observing this flag no longer proves that wave 0 has completed its write.
- Let the reader-window test accept either RAW in wave 2 or WAR in wave 0, since wave 2 can now read before the writer issues. The count remains exactly one, and wave 1's safe output remains checked.
- Remove the claim that the flags force completion-before-round or read-after-round on every schedule. Rename the flags to describe what they actually establish.

Compiled ISA confirms these placements. The revised tests pass with the unmodified detector and still reject the corresponding early-release/early-acquire mutations. All case names and the 22-case count are preserved.

## Suggestions

### Describe guaranteed wait placement and termination precisely

Several new comments say an operation “completes after” a signal when the code only puts its completion wait after the signal. The hardware operation may finish earlier; the missing guarantee is what makes the negative case unsafe. The exited-writer comment also says the barrier completes when wave 0 signals, although wave 1 may not have terminated yet.

**Implemented in [aadfa3e](https://github.com/ROCm/rocjitsu-test-corpus/commit/aadfa3e1a559693690ffb027902383ac2b6b1156):** describe the explicit waits, state that the workgroup barrier needs both the surviving wave's signal and the writer's termination in either order, and avoid describing LDS visibility as something that only begins after a barrier. The source and README also identify signal-then-exit as a detector regression for a sequence §5.6 explicitly discourages. No executable behavior changes.

### Refresh the PR description's counts and scheduling claims

The description still says the configuration grows from 113 to 135 cases; the reviewed diff grows from 153 to 175. Its every-interleaving wording should also distinguish a report required by the detector's conservative ordering model from evidence about hardware executions. If the suggested flag changes are adopted, describe the observed mutation failures and the earlier flag publication without claiming that either flag forces a particular relationship to round completion on every schedule.

This is a description-only suggestion; no replacement description or remote edit was made.

## Scope decisions

**Named/group barriers remain a follow-up.** Every addition in this PR uses the workgroup barrier `-1`. Named-barrier thresholds, join/leave behavior, signals from nonmembers, multiple groups, and transitive ordering between groups are not exercised by these additions. The current change can stay focused on workgroup split barriers; it should not be presented as validating those named-barrier semantics.

**Signal-then-exit is retained with an explicit limitation.** §5.6 permits termination instead of signalling but warns that signalling and then exiting can leave the barrier unusable. The expected detector report is useful regression coverage. Successful emulation does not establish reliable termination on hardware, so this case should retain that qualification if used in a hardware suite.

**The flag fix changes what is forced on every schedule.** It restores the possibility of a real conflicting access but stops forcing the original completed-round window. Mutation testing establishes that both intended detector mistakes are still caught with the tested build/configuration. A future requirement to force those exact callback windows on every schedule needs a separate test design; an ordering flag published after the relevant completion cannot supply that guarantee while preserving the claimed hardware race.

## Appendix: reproducing the detector mutation checks

Use the revisions and device build settings listed above. Build the corpus from either the submitted head or the suggestion branch. In a clean copy of the companion systems revision, apply one of the following insertions immediately before `state.completed = true;` in `RaceDetector::barrierRoundCompleted`, in `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp`. Restore it before trying the other insertion.

Release-at-completion mutation:

```cpp
if (wholeWorkgroup) {
  for (int owner = 0; owner < waveCount(); ++owner)
    if (!ended_[owner])
      barrierSignaled(WaveId{owner}, round);
}
```

Acquire-at-completion mutation:

```cpp
if (wholeWorkgroup) {
  for (WaveId member : members)
    if (!ended_[member.value])
      acquire(member, state.clock);
}
```

Rebuild the plugin:

```sh
cmake --build "$RJ_BUILD" --target rocjitsu_plugin_race_so --parallel 4
```

Set `SYSTEMS_SRC`, `RJ_BUILD`, `CORPUS_BUILD`, and a fresh absolute `CASE_DIR` to the corresponding checkout/build/artifact directories. Export `SYSTEMS_SRC` and `CASE_DIR`, then create the per-case configuration:

```python
import json
import os
from pathlib import Path

source = Path(os.environ["SYSTEMS_SRC"])
case = Path(os.environ["CASE_DIR"])
(case / "plugins").mkdir(parents=True)
config = json.loads(
    (source / "emulation/rocjitsu/configs/gfx1250_mi455x.json").read_text()
)
config.update(
    require_all_plugins=True,
    plugins={"race": {}},
    sinks={"types": ["file"], "dir": str(case / "plugins")},
)
(case / "config.json").write_text(json.dumps(config))
```

Run the relevant case, using `split_barrier_ds_write_wait_after_signal_race` for the release mutation or `split_barrier_reader_in_window_race` for the acquire mutation:

```sh
RJ_SINK_DIR="$CASE_DIR/plugins" ROCJITSU_RUNTIME_DIR="$CASE_DIR/runtime" \
  timeout --kill-after=5s 50s "$RJ_BUILD/tools/rocjitsu/rocjitsu" \
  --cpu-thread-budget 2 --config "$CASE_DIR/config.json" -- \
  "$CORPUS_BUILD/hip_race_tests_gfx1250" \
  --gtest_filter="Gfx1250RaceTest.$CASE" \
  --gtest_output="xml:$CASE_DIR/gtest.xml"
```

Both mutations yield a GoogleTest failure containing `expected exactly one race, got 0`. Without the mutation, each case passes with one report. The local checks additionally ran the other 21 added cases under each mutation to verify that they continued passing.
