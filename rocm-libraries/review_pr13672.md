This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13672](https://github.com/ROCm/rocm-libraries/pull/13672)

Reviewed head: `99992d7cf35c38130aadaaccccd63bcaa3c47b9f`. Suggestion branch: [`review/pr13672-suggestions`](https://github.com/newling/rocm-libraries/tree/review/pr13672-suggestions), based on that exact head. Both commits can be inspected or cherry-picked independently; [the complete suggestion diff](https://github.com/newling/rocm-libraries/compare/99992d7cf35c38130aadaaccccd63bcaa3c47b9f...91e0b25d6c2327cc84b2d38c476da72fdf2c1e6f) contains only those two commits.

| Commit | Review item |
| --- | --- |
| [`0b2341d7d32`](https://github.com/newling/rocm-libraries/commit/0b2341d7d32bbae5b678bd6d602cf088eb97a8b9) | Remove the unused native NoOptItem wrapper |
| [`91e0b25d6c2`](https://github.com/newling/rocm-libraries/commit/91e0b25d6c2327cc84b2d38c476da72fdf2c1e6f) | Test a NoOpt write between matching assignments; extend register and wait boundaries |

## Tests

Submitted head: rocisa 312 passed, 4 skipped; suggestion branch: rocisa 320 passed, 4 skipped and 10 focused TensileLite occupancy tests passed. All 2,433 deterministic comparisons matched the merge-base assembly and `maxVgpr` results. The expanded direct tests also pass on the merge base. Root pre-commit, changed-test Black 24.4, Python undefined-name checks and whitespace checks pass.

The builds used Python 3.12, Clang 23 and Ninja. The full rocisa suite initially had one failure with the ROCm 7.1 assembler: `test_async_store_high_vgpr_emits_msb_window` expected `s_set_vgpr_msb`, but received `global_store_async_from_lds_b128 v[300:303], v320, s[10:11]`. The same failure occurs on the merge base. Selecting the LLVM 23 assembler through the tests' `ROCM_PATH` lookup makes it pass on both versions. This is an assembler-capability difference, unrelated to the changed graph. Reproduce with the older assembler using `ROCM_PATH="$ROCM_71" PYTHONPATH="$BUILD_DIR" python -m pytest projects/hipblaslt/tensilelite/rocisa/test/test_async_store.py::test_async_store_high_vgpr_emits_msb_window`.

The comparison cases cover mixed resetting and non-resetting barriers, scalar register reads and writes, covering ranges, execution-mask operands, NoOpt and nested modules, comments, invalid registers, absent vector-register references and lowered waits on gfx942/gfx1201. They verify preservation of existing behavior, including its existing limitations.

As checked on October 28, the rocisa Linux/Windows/shared/static lanes, Math CI, hipBLASLt ASAN, replacement Multi-Arch run and gfx942/gfx950 race checks pass. The earlier Multi-Arch run was cancelled during external checkout. The gfx1250 FFM check still reports 3 failures and 10 timeouts, coverage checks remain below their thresholds, and the gfx1250 strict check is pending. I have not established whether those FFM results differ from the baseline, so they remain unresolved validation evidence rather than a demonstrated defect in this PR.

## Summary

The duplicate-assignment pass remembers scalar general-purpose register (SGPR) values and removes redundant moves. This PR retains only the scalar-register entries it consumes. It represents barriers with sequence counters, classifies entries once and checks destination ranges while constructing them. Vector and special-register operands still receive bounds checks, and the highest vector general-purpose register (VGPR) remains available to the caller.

The single caller builds, consumes and discards the graph within one pass. That makes dropping unused register lists and the rebuilt scalar lists appropriate. The resetting-barrier prefix counts and per-entry destination flags preserve the old traversal in the cases inspected and tested; I found no introduced assembly or register-count defect.

Direct pass tests are the appropriate local level for this internal representation change. They exercise observable instruction removal and retained comments, while existing device builds and tests cover generated-code integration. No new public interface, saved format, selection rule or default requires a feature flag. The adjacent path worth checking is TensileLite's occupancy update, which consumes `maxVgpr`; its focused tests pass. Full device-library regeneration and physical-GPU runs were not repeated locally, and the reported build-time improvement was not independently timed.

## Actionable items

### Test a NoOpt write between matching assignments

[`projects/hipblaslt/tensilelite/rocisa/test/test_remove_dup_assign.py:138–143`](https://github.com/ROCm/rocm-libraries/blob/99992d7cf35c38130aadaaccccd63bcaa3c47b9f/projects/hipblaslt/tensilelite/rocisa/test/test_remove_dup_assign.py#L138-L143)

The reset test starts with the NoOpt module, so there is no previously remembered value to invalidate. The other NoOpt test only checks that the module's own instruction remains. Together they miss a consequential failure: if graph construction ignores NoOpt instructions, a later move can be removed even though it needs to restore the preceding value.

I tested this by adding an early `if(noOpt) return;` to `_addRegToGraph`. All 19 submitted tests still pass. The needed example is `s4 = 7`, then a NoOpt module containing `s4 = 8`, then `s4 = 7`; all three items must remain. Commit [`91e0b25d6c2`](https://github.com/newling/rocm-libraries/commit/91e0b25d6c2327cc84b2d38c476da72fdf2c1e6f) changes the reset test to that example. It fails under the temporary mutation and passes with the submitted implementation and the merge-base implementation.

The same commit adds `_SWaitCntVscnt`, register ranges whose first element is valid but whose last element exceeds the bound, negative scalar/vector indices, special-register bounds and the no-VGPR fallback. These cover the classifications and bounds logic changed by this PR without expanding into GPU integration tests.

## Suggestions

### Remove the unused native NoOptItem wrapper

[`projects/hipblaslt/tensilelite/rocisa/rocisa/include/pass.hpp:95–111`](https://github.com/ROCm/rocm-libraries/blob/99992d7cf35c38130aadaaccccd63bcaa3c47b9f/projects/hipblaslt/tensilelite/rocisa/rocisa/include/pass.hpp#L95-L111)

The graph now represents NoOpt instructions through `Entry::noOpt` and `Kind::Reset`; the native `NoOptItem` class has no remaining construction or use. Remove it and update the two nearby comments referring to it. Commit [`0b2341d7d32`](https://github.com/newling/rocm-libraries/commit/0b2341d7d32bbae5b678bd6d602cf088eb97a8b9) does that. The Python adaptor has its own used `_NoOptItem` implementation, which does not depend on the native class and retains its behavior.

## Commentary

The deliberate preservation of the existing barrier policy keeps this performance change focused. In particular, the gfx12 wait behavior mentioned in the description also exists in the merge-base comparison; correcting that policy would require separate behavior tests and device evidence.

The review branch contains the two commits mapped above. Final build and focused validation pass, and the temporary mutation has been removed. The principal local omissions are physical-GPU/device-library regeneration, independent performance measurement and reproduction of the outstanding gfx1250 FFM results.

## Appendix: NoOpt mutation

This temporary patch checks whether the tests detect ignoring writes inside a NoOpt module. Apply it to the reviewed implementation, rebuild rocisa and run `rocisa/test/test_remove_dup_assign.py`: the submitted tests pass, while the expanded test in `91e0b25d6c2` fails. Remove the patch before further validation.

```diff
diff --git a/projects/hipblaslt/tensilelite/rocisa/rocisa/src/pass/graph.cpp b/projects/hipblaslt/tensilelite/rocisa/rocisa/src/pass/graph.cpp
--- a/projects/hipblaslt/tensilelite/rocisa/rocisa/src/pass/graph.cpp
+++ b/projects/hipblaslt/tensilelite/rocisa/rocisa/src/pass/graph.cpp
@@ -144,6 +144,8 @@
                         Graph&                               graph,
                         bool                                 noOpt)
     {
+        if(noOpt)
+            return;
         bool                               classified = false;
         Graph::Kind                        kind       = Graph::Kind::Other;
         std::shared_ptr<RegisterContainer> dst;
```
