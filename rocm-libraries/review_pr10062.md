> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#10062](https://github.com/ROCm/rocm-libraries/pull/10062)

Reviewed 2026-09-10 at head `ed5bc2ed67a1a0c19de10817fb1b09c7fd761344`. Its merge base is `develop` at `e178da1f5adfce6a95a4443c8b30c224e87d8cf5`; current `develop` is `76ae32ea3805208bc234758c569146297420710e`.

## Tests

The focused GC lifecycle test passes locally: 1 test and 4 subtests passed. `git diff --check` and a merge-tree check against current `develop` also pass.

On the current public CI run, all 3,012 characterization tests and all 4,008 unit tests pass. The coverage report measures `Tensile/TensileCreateLibrary/Run.py` at 89.46%, above its committed 88.53% floor. The host-ASAN hipBLASLt build and quick test pass, as do pre-commit, clang-tidy, and the complete Linux and Windows multi-architecture build summaries.

The Component CI failure is the post-test coverage ratchet for `Tensile/SolutionStructs/LdsPadding.py`: the committed floor is 99.35%, while the merged PR checkout measures 98.27%. `Component CI Summary` is a duplicate summary failure caused by that one job.

The external gfx1250 FFM check reports 96 passed, 31 failed, and 3 timed out. The detailed job log shows that all 31 sparse cases fail during solution construction rather than numerical validation: every candidate is rejected and each subprocess exits with `Tensile::FATAL: Your parameters resulted in 0 valid solutions.` The complete set of failures and timeouts exactly matches the gfx1250 FFM result on the head of [#11758](https://github.com/ROCm/rocm-libraries/pull/11758), whose sparse test-YAML changes are present in this PR's base. Those YAML changes were subsequently reverted by [#11930](https://github.com/ROCm/rocm-libraries/pull/11930), now on `develop` but not yet in this PR's head. The separate `HW gfx1250 / hipblaslt` check remains in progress.

## Summary

This PR suspends cyclic garbage collection while `TensileCreateLibrary` consumes and merges parsed library logic, then freezes the retained object graph so later collections do not repeatedly scan it. It restores the caller's prior enabled/disabled collector state in a `finally` block and registers an exit hook to unfreeze the graph before interpreter teardown. The change is confined to the library-logic loading phase and does not alter generated solutions or kernels.

The new direct unit test covers normal and exceptional exit with GC initially enabled and disabled, verifies the state restoration and freeze ordering, and invokes the registered unfreeze callback. It resolves the lifecycle-test gap identified in the earlier review of this PR.

I found no actionable issue in the current PR diff. Both completed red test checks are real, but the evidence attributes them to changes inherited from `develop`, not to this PR's two-file diff.

## Actionable items

None.

## Suggestions

None.

## Commentary

The CI history makes the attribution unusually clear:

- This PR's Component CI was green on September 2, before the newer `LdsPadding.py` implementation entered `develop`.
- The source PR for that implementation, #11409, already reported the same `LdsPadding.py` 99.35% to 98.27% ratchet failure on September 4. It was merged into `develop` on September 7 without changing the stale floor.
- After #10062 updated onto that base, its Component CI failed with the identical percentage on four consecutive heads on September 8, 9, and 10. The tests themselves passed in every run.
- `LdsPadding.py` and `coverage-baseline.json` are byte-for-byte unchanged by #10062. Its two changed files are `TensileCreateLibrary/Run.py` and `test_defer_cyclic_gc.py`.

Rerunning the current coverage job is therefore unlikely to help. The repository-level fix should cover the three missed `LdsPadding.py` paths or deliberately update that file's floor on `develop`; #10062 can then update to the repaired base. Current `develop` still has the same `LdsPadding.py` and 99.35% baseline, so updating the branch today will not by itself clear this check. Folding an unrelated baseline reduction into this PR would obscure ownership of the regression.

The gfx1250 result has a similarly direct source:

- #10062's FFM check and #11758's FFM check have identical sets: the same 31 sparse tests fail and `subtile_bf16_gfx1250_bench`, `gsu_gfx1250`, and `sk_sgemm_quick` time out.
- The detailed log records 31 `0 valid solutions` fatal errors. Across those cases the candidates are rejected because tile-major TDM requires `LDSTrInst=True`, while the remaining `LDSTrInst` candidates conflict with `ExpandPointerSwap` and `1LDSBuffer=0`. #11758 changed the sparse grids to `ScheduleIterAlg: [4]`, `TDMInst: [3]`, and `1LDSBuffer: [0]`, creating exactly these invalid combinations. #10062 does not touch the grids or solution validation.
- #11930 specifically reverts the 36 affected sparse YAMLs and merged into `develop` after #10062's FFM run. #10062 does not yet contain that revert. Updating onto current `develop` and rerunning FFM is the appropriate next step for these 31 failures. #11930's own external FFM check was still running when this review was updated.
- The three remaining failures are genuine per-test `pytest-timeout` expirations at 2,700 seconds, not runner or job-level cancellations. Each was still producing passing client validation records: `subtile_bf16_gfx1250_bench` completed the first of 12 solutions over all four sizes, `gsu_gfx1250` completed the first of 1,056 generated solutions, and `sk_sgemm_quick` reached solution 1,118 of 1,295 on its final size. They are oversized FFM workloads rather than correctness failures. The FFM path calls the benchmark driver and never invokes the changed `generateLogicDataAndSolutions` function, so the GC deferral cannot account for their duration. #11930 does not touch these three configurations; they need separate FFM test-selection, workload-size, sharding, or timeout treatment.

The other recent red job was unrelated as well. On the first September 8 head, the host-ASAN job exited with status 137 while building LLVM and emitted runner-container follow-on errors; subsequent heads pass the same build and quick test. Older August multi-architecture failures were in rocThrust's rocRAND benchmark build because `primbench.hpp` was missing, outside this PR's two-file diff.
