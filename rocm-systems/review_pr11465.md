This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#11465](https://github.com/ROCm/rocm-systems/pull/11465)

**Revision reviewed:** restacked candidate `9a90e88c05`, based on `origin/develop` commit `1c314781d7` and the merged #11473 change.

## Tests

The final release `rocjitsu_tests` target built successfully. All 261 focused execution-plugin, hook-ordering, instruction-metadata, memory-pipeline, and race-detector tests passed, as did 44 focused generator/property tests and all 72 rebuilt gfx950/gfx1151 race integration cases. Full ten-ISA regeneration produced no residual diff, all branch-diff pre-commit hooks passed, and `git diff --check` passed. A patch-identical candidate also passed the full C++ suite with 4,421 tests passed and 23 skipped.

Published CI belongs to the old pre-restack head. Its Clang ASan/UBSan, TSan, GCC UBSan, formatting, and current TheRock jobs passed. The release corpus failure was timeout-only: three of five initially timed-out gfx1250 FPSAN cases passed on rerun, while `fpsan_cvt_fp8_e5m3_gfx1250_test` and `fpsan_amdgcn_math_test` timed out again at 60 seconds. There was no assertion failure, and the internal C++ suite passed. The remaining red summary jobs include cancelled runs caused by the dependency PR being squash-merged and this PR being retargeted with the old dependency commits still present; the restack removes that condition.

## Summary

This layer makes the runtime consume all decoded memory obligations. The memory pipeline acquires and releases every token, and the race detector keeps an event active until every counter domain attached to it has been satisfied. Partial waits retire only prefixes proven complete within the relevant completion class, while event-level WAW ordering is derived conservatively from the full obligation set.

The routing boundary is also sound: the established pre-routing callback contract is preserved, while the race detector uses a context-preserving post-routing observation. The implementation validates complete load-destination ranges before indexing register state, uses effective issue masks, records the full LDS byte span, and checks both ranges of dual-offset LDS operations.

The current code addresses the remaining maintainer feedback. The obsolete single-counter accessors and stale wording are gone. A decoded RDNA4 generic-FLAT store test exercises the store-only path and verifies that either STORECNT or DSCNT alone leaves the event active, with completion occurring only after both waits.

I found no actionable correctness issue in this layer.

## Actionable items

None.

## Suggestions

None.

## Commentary

The seven commits were replayed directly onto the current `origin/develop`; range-diff reports every patch as identical to the reviewed pre-restack series. The published PR will need its rewritten head pushed before GitHub can run meaningful CI against this candidate.
