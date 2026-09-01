> This is a review from an agent with an automatic prompt from the reviewer

# Review: PR #10062 — defer cyclic GC while loading Tensile library logic

Date reviewed: 2026-09-01  
PR: https://github.com/ROCm/rocm-libraries/pull/10062  
Commit reviewed: `2abc468236537f08c24cb6c0470089704bd3c002` (tip of `<pr-head-ref>`)  
Overall assessment: **Changes requested**

## Tests

Local performance verification compared the exact PR merge base (`9cc55c9ec5d`) with the reviewed head (`2abc46823653`) using the same 297-file `gfx942/GridBased/*` corpus, prepared rocisa build, Python 3.12.3 environment, joblib 1.6.0, warmed file cache, `PYTHONHASHSEED=0`, and 48-CPU affinity. The harness ran the normal `TensileCreateLibrary` setup and stopped immediately after `generateLogicDataAndSolutions()` so that the measurement isolates the changed parse/merge phase rather than diluting it with unchanged kernel compilation.

| Variant | Run 1 | Run 2 | Mean | Mean parent peak RSS | Cyclic collections |
|---|---:|---:|---:|---:|---:|
| Merge base | 497.98 s | 538.79 s | 518.39 s | 25.81 GiB | 75,488 |
| PR | 83.85 s | 81.05 s | 82.45 s | 28.89 GiB | 1,609 |

The independently measured speed-up is **6.29x**, saving 435.93 seconds (7.27 minutes, 84.1%) in the changed phase. All four runs selected 297 files, parsed 161,292 solutions, produced 157,710 unique solutions and 260 mapping entries, and had identical solution and mapping signatures. Their 40.9 MB `MatchTable.yaml` files were byte-identical with SHA-256 `561188273224deea05f2ca9601de23641c8e6a147b814941d2ab4ee274a6233d`.

The isolated load-phase parent peak was reproducibly 3.08 GiB (11.9%) higher with the PR. This does not contradict the PR's full-process VmHWM measurement if a later kernel-generation phase establishes the overall peak, but this review did not reproduce that full generation run and therefore does not independently verify the memory-neutral claim or the extrapolated 11-minute full-build saving. The concrete lifecycle regression proposed in the appendix passed as one table-driven unittest with four subcases. No local pytest run was performed because the prepared runtime environment did not include pytest; no dependencies were installed. Local `git diff --check` and a merge-tree check against current `develop` passed.

The public TensileLite coverage job passed 2,945 characterization tests and 3,287 unit tests on Python 3.12. Its report leaves branch `849->856` in `TensileCreateLibrary/Run.py` uncovered, which is the new path that must keep collection disabled when the caller already had it disabled. The three failed Linux builds are unrelated to this diff: all fail in rocThrust's rocRAND benchmark build because `primbench.hpp` is missing. The Windows build, host-ASAN job, pre-commit job, and focused coverage job passed.

## Summary

This PR removes a main-process bottleneck from `TensileCreateLibrary`. While parsed logic libraries arrive from worker processes, the parent retains and merges a steadily growing Python object graph. Automatic cyclic-GC collections repeatedly traverse that live graph even though there is nothing to reclaim. The change disables only cyclic collection while that generator is drained, freezes the resulting graph so later collections skip it, restores the caller's enabled/disabled state, and unfreezes at interpreter shutdown for clean extension teardown. Python reference counting remains active, so ordinary acyclic temporaries are still reclaimed.

The placement is appropriately narrow: it covers creation and consumption of the results generator and the serial merge, while `try/finally` restores automatic collection after normal or exceptional exit. It does not intentionally change generated libraries, kernels, or runtime performance. The independent phase measurement above slightly exceeds the published 5.3x result and directly confirms that the claimed bottleneck and optimization are real. It verifies a 7.27-minute mean saving for this 297-file workload. The published full-command result (925 to 552 seconds) and roughly 11-minute extrapolation to the full gfx94X device-library build remain plausible, but were not independently rerun here.

The current branch merges cleanly with `develop`, including the subsequent changes in the same file. I recommend one focused test addition before merge because this helper owns process-wide interpreter state and its most important preservation branch is demonstrably absent from the committed test coverage. Risk is 3/5: the behavior is build-time only and narrowly placed, but a restoration or shutdown regression could affect every later Python phase in the generator process.

## Actionable items

### 1. Add direct regression tests for the GC lifecycle contract

`projects/hipblaslt/tensilelite/Tensile/TensileCreateLibrary/Run.py:816-856`

The PR adds no test file or direct test of `deferCyclicGC()`. Existing broad tests happen to execute the normal enabled-GC path through `generateLogicDataAndSolutions()`, but they assert generated data rather than the global state transition. The public coverage report confirms that branch `849->856` is not taken, so the explicit promise that an already-disabled caller remains disabled is currently unverified. Those tests also do not establish that the shutdown hook is registered with `gc.unfreeze` or that state restoration still happens when the wrapped body raises.

Add the focused unit test from the appendix (or an equivalent pytest-style version). It replaces the module's `gc` object and `atexit.register` with recording fakes, exercises enabled/disabled collector state across normal/exceptional exit, asserts exact call order, verifies that `gc.enable()` is conditional on the prior state, and verifies that the registered callback is `gc.unfreeze`. Keeping the test isolated from the test runner's real collector avoids freezing pytest's own object graph. The proposed test passes against the reviewed head and directly protects the safety properties that make the optimization acceptable.

## Suggestions

None.

## Commentary

This is a useful optimization because it attacks serial bookkeeping rather than parser parallelism: adding workers cannot remove repeated main-process scans of an ever-larger live heap. Freezing the retained graph after the load is the key part; merely re-enabling collection over the graph would surrender a material fraction of the gain.

The phase-isolated RSS increase is consistent with the implementation retaining every tracked object until shutdown. It was stable across both samples, so memory-constrained builders should treat the published full-process VmHWM result—not an assumption that deferring GC is intrinsically memory-neutral—as the relevant capacity evidence. A full command benchmark on the current build image would usefully confirm which later phase establishes the true process peak.

The one substantive existing human review thread asked for the term “load-bearing” to be removed and for the second `gc.freeze()` to be explained in terms of the state on entry to `finally`. Commit `5dc1f94fef69` rewrites that docstring, removes the term, and explains that objects created inside the context are frozen before automatic collection is restored. The thread is still formally unresolved on GitHub but is outdated and addressed in substance. The automated policy warning that a production file changed without a test file remains unaddressed; the appendix test would resolve that warning as well as the actionable item above.

The failed Linux checks should still be refreshed before merge. Their identical `primbench.hpp` failure is outside the changed TensileLite file, and current `develop` contains subsequent rocThrust/rocRAND build fixes, so updating the branch is the practical way to obtain current green evidence rather than changing this PR for those failures.

### Appendix: exact proposed GC lifecycle test

Add this as `projects/hipblaslt/tensilelite/Tensile/Tests/unit/test_defer_cyclic_gc.py`. It ran successfully against the reviewed head with all four subcases passing.

```python
import unittest
from unittest.mock import patch

import Tensile.TensileCreateLibrary.Run as run_module


class RecordingGC:
    def __init__(self, enabled):
        self.enabled = enabled
        self.events = []
        self.unfreeze = lambda: self.events.append("unfreeze")

    def isenabled(self):
        self.events.append("isenabled")
        return self.enabled

    def freeze(self):
        self.events.append("freeze")

    def disable(self):
        self.events.append("disable")
        self.enabled = False

    def enable(self):
        self.events.append("enable")
        self.enabled = True


class TestDeferCyclicGC(unittest.TestCase):
    def exercise(self, initially_enabled, raises):
        fake_gc = RecordingGC(initially_enabled)
        registered = []

        def register(callback):
            fake_gc.events.append("register")
            registered.append(callback)
            return callback

        with (
            patch.object(run_module, "gc", fake_gc),
            patch.object(run_module.atexit, "register", side_effect=register),
        ):
            if raises:
                with self.assertRaisesRegex(RuntimeError, "parse failed"):
                    with run_module.deferCyclicGC():
                        fake_gc.events.append("body")
                        self.assertFalse(fake_gc.enabled)
                        raise RuntimeError("parse failed")
            else:
                with run_module.deferCyclicGC():
                    fake_gc.events.append("body")
                    self.assertFalse(fake_gc.enabled)

        expected = ["isenabled", "freeze", "disable", "body", "freeze"]
        if initially_enabled:
            expected.append("enable")
        expected.append("register")

        self.assertEqual(fake_gc.events, expected)
        self.assertEqual(fake_gc.enabled, initially_enabled)
        self.assertEqual(registered, [fake_gc.unfreeze])

    def test_restores_prior_gc_state_on_normal_and_exceptional_exit(self):
        for initially_enabled in (True, False):
            for raises in (False, True):
                with self.subTest(initially_enabled=initially_enabled, raises=raises):
                    self.exercise(initially_enabled=initially_enabled, raises=raises)
```
