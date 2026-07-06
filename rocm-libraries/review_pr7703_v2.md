> This is a review from an agent with an automatic prompt from the reviewer

# Review: PR #7703 -- Add unit test for TensileLogic_Run, TensileMergeLibrary, TensileRetuneLibrary and TensileUpdateLibrary (v2)

**Date reviewed**: 2026-06-02
**PR**: https://github.com/ROCm/rocm-libraries/pull/7703
**Commit reviewed**: 18fd91b0a89 (tip of `<pr-head-ref>`)

## Tests

**Command** (from `projects/hipblaslt/tensilelite/`):
```
source .venv/bin/activate
python -m pytest Tensile/Tests/unit/test_TensileLogic_Run.py \
  Tensile/Tests/unit/test_TensileMergeLibrary.py \
  Tensile/Tests/unit/test_TensileRetuneLibrary.py \
  Tensile/Tests/unit/test_TensileUpdateLibrary.py -v
```

**Result**: 67 collected, 0 passed, 26 failed (25 from `test_TensileRetuneLibrary.py` + `test_TensileUpdateLibrary.py`), 1 collection error (`test_TensileLogic_Run.py` + `test_TensileMergeLibrary.py`). Total time: < 1 second.

**Root cause**: All failures trace to the same `ImportError`:
```
ImportError: cannot import name 'SAtomicInc' from 'rocisa._rocisa.instruction'
```
The tests import directly from production modules (`from Tensile.TensileLogic.Run import ...`, `from Tensile.TensileMergeLibrary import ...`, etc.), which trigger the full Tensile import chain including `Tensile/Components/StreamK.py`, which requires `SAtomicInc` from `rocisa`. The locally installed `rocisa` does not yet expose this symbol; it was recently added to the `StreamK` module on `develop`.

This is an **environment mismatch**, not a test bug per se -- the tests likely pass in CI where `rocisa` is built from the same commit. However, other unit tests in this codebase (e.g., `test_KnownBugs.py`) use `importlib.util.spec_from_file_location` to import the module under test without triggering the full Tensile import chain, specifically to avoid this class of fragility. The new tests do not follow this pattern, which makes them brittle when `rocisa` and Tensile are not built from exactly the same tree. See Actionable item 1.

**CI status**: `pre-commit` passes. `mci/rocm-libraries/preliminary(hipblaslt)` failed in the Test stage. Several gfx94X hardware test shards pass; some shards and the `tensilelite-unit-codecov` job are still pending/running.

## Summary

This PR adds 4 new test files (2316 lines added, 0 deleted, no production code changes) providing pytest suites for:

- `TensileLogic/Run.py` -- validates the `_runChecks`, `_setup`, `_progress_loop`, `Check`, and `main` functions
- `TensileMergeLibrary.py` -- covers utility functions (`ensurePath`, `allFiles`, `fixSizeInconsistencies`, `addKernel`, `sanitizeSolutions`, etc.) and higher-level merge logic
- `TensileRetuneLibrary.py` -- covers working path management, library parsing, benchmarking setup, and the main `TensileRetuneLibrary` entry point
- `TensileUpdateLibrary.py` -- covers `UpdateLogic`, `TensileUpdateLibrary` entry point, and CLI argument parsing

The production code changes originally bundled in this PR (import refactoring, dead code removal, and `GlobalParameters.globalParameters` bug fix in `TensileRetuneLibrary.py`) have been moved to the companion PR #7849, as the reviewer requested. The PR description still describes these product code changes, which is now misleading since they are no longer part of the diff.

The tests heavily rely on `unittest.mock` for all external dependencies. The utility-level tests (e.g., `TestEnsurePath`, `TestAllFiles`, `TestAddKernel`, `TestSanitizeSolutions`, `TestFindSolutionWithIndex`) operate on real data structures and provide genuine correctness verification. The higher-level tests mock out all interesting logic and primarily verify call wiring, with assertions too weak to catch behavioral bugs.

## Actionable items

### 1. Tests are fragile due to direct Tensile imports

**Files**: All four test files.
**Issue**: The tests do top-level or in-method imports like `from Tensile.TensileLogic.Run import _runChecks, _setup, _progress_loop, Check` and `from Tensile.TensileMergeLibrary import (ensurePath, allFiles, ...)`. These trigger the full Tensile import chain (via `TensileLogic/__init__.py`, `LibraryIO`, `SolutionLibrary`, `Component`, `StreamK.py`) which requires a matching `rocisa` build.

Other unit tests in this directory (e.g., `test_KnownBugs.py`) avoid this by using `importlib.util.spec_from_file_location` to load only the specific module under test. The `test_TensileMergeLibrary.py` file even has a comment at line 14 saying "# rocisa is mocked in the root conftest.py" -- but no such root conftest exists and no such mocking is set up.

**Fix**: Either (a) set up proper `rocisa` mocking in a conftest (as the comment implies should exist), or (b) use the `importlib.util` pattern to isolate modules under test from the full Tensile import chain.

### 2. `test_finds_and_processes_logic_files` uses wrong filenames

**File**: `Tensile/Tests/unit/test_TensileUpdateLibrary.py`, lines 236-237.
**Issue**: The test creates files named `logic_gfx908.yaml` and `logic_gfx90a.yaml`, then asserts they are found by `TensileUpdateLibrary`. However, the production code at `TensileUpdateLibrary.py:142-150` searches for architecture **names** (values of `architectureMap` like "arcturus", "aldebaran") in filenames, not for gfx keys like "gfx908" or "gfx90a". So files named `logic_gfx908.yaml` would NOT be found by the file search logic, and the assertion `assert len(file_paths) >= 2` would fail.

Additionally, line 157 of the production code has `print("# LibraryLogicFiles:" % logicFiles)` which is a format-string bug (no `%s` placeholder, so `% logicFiles` raises `TypeError` when `logicFiles` is non-empty). Since `print` is not mocked in the test, this would also crash. If `logicFiles` happened to be empty (which it would be, since the filenames don't match), the `%` operator with an empty list still raises `TypeError`.

**Fix**: Name the test files using architecture names: e.g., `logic_arcturus.yaml` and `logic_aldebaran.yaml`. Also, consider noting the `print` format-string bug in the production code (though fixing it is out of scope for this PR).

### 3. `test_main_basic_execution` can pass vacuously

**File**: `Tensile/Tests/unit/test_TensileLogic_Run.py`, lines 635-645.
**Issue**: Uses `try: main() except SystemExit as e: assert e.code in (None, 0)`. If `main()` completes without raising `SystemExit` (possible since `ParallelMap2` is mocked), the assertion is never reached and the test passes without checking anything.

**Fix**: Use `with pytest.raises(SystemExit) as exc_info:` then `assert exc_info.value.code in (None, 0)`, consistent with the pattern used by `test_main_with_rejects` and `test_main_with_chip_id_failures` in the same class.

### 4. `test_handles_known_bugs` mocks away the logic it should test

**File**: `Tensile/Tests/unit/test_TensileLogic_Run.py`, lines 176-211.
**Issue**: The test mocks `is_known_bug` to always return `True`, regardless of what is passed to `known_bugs`. This means the test verifies that _when `is_known_bug` returns True_, the solution is kept and `mock_matrix` is not called -- but it doesn't verify that the correct `known_bugs` data reaches `is_known_bug`. The test would pass even if `_runChecks` passed an empty set to `is_known_bug`.

**Fix**: Instead of mocking `is_known_bug`, construct a real `known_bugs` frozenset that matches the test file's relative path and solution index, then let `is_known_bug` run with real logic. If `is_known_bug` itself is too complex to use, at minimum assert on the arguments passed to the mock.

### 5. `TestMergeLogic` assertions are too weak -- all four tests

**File**: `Tensile/Tests/unit/test_TensileMergeLibrary.py`, lines 1300-1423.
**Issue**: All four `mergeLogic` tests (`test_merge_with_new_sizes`, `test_merge_with_better_efficiency`, `test_merge_with_force_merge`, `test_merge_with_no_eff`) mock out `findSolutionWithIndex`, `removeUnusedSolutions`, and `fixSizeInconsistencies`, then assert only `isinstance(result, list)` and `num_sizes >= 0`. These assertions would pass for nearly any implementation. The tests do not verify: the actual return values, whether the merge policy was correctly applied, whether the solution pool was correctly updated, or whether efficiency comparisons worked.

**Fix**: Either remove the mocks and test with small real data structures (the function is pure logic over lists/dicts, no I/O needed), or at minimum assert the specific return values (`num_sizes`, `num_solutions`, `num_removed`) match expected values for each test scenario.

### 6. `fixSizeInconsistencies` tests do not verify correctness

**File**: `Tensile/Tests/unit/test_TensileMergeLibrary.py`, lines 920-940.
**Issue**: `test_remove_duplicates` asserts only `count == len(result)`, which is tautologically true since `fixSizeInconsistencies` always returns `(newSizes, len(newSizes))`. It does not verify that duplicates were actually removed or that the result contains the correct sizes. Furthermore, the production function `fixSizeInconsistencies` has a bug: it indexes a dict by a generator object (`sizesDict[(value for value in size)]`), which means every entry gets a unique key (generators are unique objects) and no dedup actually occurs. The test should expose this.

**Fix**: Write tests with known duplicate inputs and assert specific expected outputs. Separately, file a bug for the generator-as-dict-key issue in the production code.

### 7. Tests mutate `globalParameters` without cleanup

**File**: `Tensile/Tests/unit/test_TensileRetuneLibrary.py`, lines 1638, 1757 (multiple test classes). Also `Tensile/Tests/unit/test_TensileUpdateLibrary.py`, line 354.
**Issue**: Several tests patch `globalParameters` with `@patch('Tensile.TensileRetuneLibrary.globalParameters', {...})` or directly modify `globalParameters["TestParam"] = "TestValue"` without restoring the original state after the test. Since `globalParameters` is a real module-level dict, mutations persist across tests and can cause ordering-dependent failures.

**Fix**: For tests that directly modify the dict (like `test_applies_global_parameter_overrides`), save and restore the original value in a fixture or use `addCleanup`. For `@patch` decorators replacing the entire dict, ensure the original dict is restored (which `@patch` does automatically, so those are fine). The issue is specifically `test_applies_global_parameter_overrides` which inserts into the real `globalParameters` dict via the production code.

### 8. `test_sanitize_without_stagger_u` does not verify unchanged state

**File**: `Tensile/Tests/unit/test_TensileMergeLibrary.py`, lines 1014-1018.
**Issue**: The test calls `sanitizeSolutions` on a list without `StaggerU` and asserts "Should not crash" (via a comment). It does not verify that the solution remains unchanged. The function could incorrectly modify the input and the test would not detect it.

**Fix**: Assert that `solList[0]` is unchanged after the call (compare to a `deepcopy` of the input).

## Suggestions

### 9. Extract duplicated `create_mock_problem_type` helper

**File**: `Tensile/Tests/unit/test_TensileUpdateLibrary.py`.
**Issue**: The `create_mock_problem_type` helper (with its 13-key state dict) is defined as a method on `TestUpdateLogic` and implicitly used by `create_mock_solution`. If `TestTensileUpdateLibrary` or `TestMain` needed similar mocks, they'd have to duplicate it. A module-level fixture or helper function would be cleaner.

### 10. Parameterize the `TestMessageFunctions` tests

**File**: `Tensile/Tests/unit/test_TensileMergeLibrary.py`, lines 1224-1260.
**Issue**: The five test methods for `msg`, `verbose`, and `debug` follow the same pattern (patch `builtins.print`, call function, check `call_count`). These could be parameterized with `@pytest.mark.parametrize` over `(verbosity_level, function, expected_calls)`.

### 11. `TestCheckNamedTuple` tests Python stdlib

**File**: `Tensile/Tests/unit/test_TensileLogic_Run.py`, lines 583-597.
**Issue**: `test_check_creation` and `test_check_default_values` verify that a `NamedTuple` has fields and supports `hasattr`. This tests Python's `typing.NamedTuple`, not application logic. These add noise without catching regressions.

### 12. `removeDuplicatedSolutions` tests should verify post-state

**File**: `Tensile/Tests/unit/test_TensileMergeLibrary.py`, lines 1087-1127.
**Issue**: `test_remove_duplicates_by_solution_name` verifies `num_removed == 1` and `num_solutions == 2`, but does not check that the `size_map` references were correctly reindexed or that the correct solutions remain. `test_no_duplicates` verifies counts but not that the data is unchanged.

### 13. Update the PR description

The PR description still describes three product-code changes (granular import refactor, dead-code removal, bug fix) that were moved to #7849 and are no longer in this PR's diff. The description should be updated to reflect that this is now a test-only PR.

## Commentary

The strongest tests in this PR are the utility-level ones in `test_TensileMergeLibrary.py` -- `TestEnsurePath`, `TestAllFiles`, `TestAddKernel`, `TestSanitizeSolutions`, `TestRemoveUnusedSolutions`, and `TestFindSolutionWithIndex`. These operate on real data, make meaningful assertions, and would catch regressions.

The higher-level tests (everything in `test_TensileLogic_Run.py`, the `TestMergeLogic` and `TestAvoidRegressions` classes, and most of `test_TensileRetuneLibrary.py`) mock out all interesting logic and primarily verify call wiring. They confirm that function A calls function B with the right arguments, but they don't verify that the composition of those calls produces correct outputs. This pattern is fragile: if the production code's internal structure changes (e.g., function renamed, argument order changed), these tests break even though behavior is preserved. Conversely, if the production code has a logic bug that respects the existing call structure, these tests won't catch it.

The `fixSizeInconsistencies` function in `TensileMergeLibrary.py` appears to have a genuine bug (generator-as-dict-key at line 61, and wrong sign in the diagnostic at line 66-67). The test for this function does not expose either issue because it only checks `count == len(result)`.

## Previous review context

### Our previous review (May 27, review_pr7703.md)

Our previous review found all 88 tests passing (we had a compatible rocisa at that time). We identified:

1. **Unused import alias** `ensurePath as ensurePathUtil` in `TensileRetuneLibrary.py` -- this was a product-code issue that has since been moved out to #7849, so it's no longer applicable to this PR.
2. **Duplicate `from pathlib import Path`** in `TensileRetuneLibrary.py` -- same, moved to #7849.
3. **`test_main_basic_execution` vacuous pass** -- still present, unchanged. (Actionable item 3 above.)
4. **`TestCheckNamedTuple` tests Python stdlib** -- still present, unchanged. (Suggestion 11 above.)
5. **Extract duplicated mock state dict** suggestion -- still applicable. (Suggestion 9 above.)
6. **`TestMergeLogic` assertions too weak** -- still present, unchanged. (Actionable item 5 above.)

### Prior reviews

**May 26 (CHANGES_REQUESTED)**: The reviewer flagged that the product-code changes (import refactoring and bug fix) should be in their own PR. The author responded by creating #7849 to separate them. This has been **addressed** -- the production code changes are no longer in this PR's diff.

**June 2 (CHANGES_REQUESTED)**: The reviewer left a comprehensive round of 20+ comments. Key themes:

- **`fixSizeInconsistencies` is broken**: The production function uses a generator as a dict key, making dedup a no-op. The test doesn't expose this. (Our Actionable item 6 covers this.)
- **Weak assertions throughout**: Multiple tests assert only `isinstance(result, list)` or use `>=` instead of `==`. The reviewer specifically flagged `TestMergeLogic` (all four tests), `fixSizeInconsistencies` tests, and `removeDuplicatedSolutions` tests. (Our Actionable items 5 and 6, and Suggestions 12 cover these.)
- **Global state mutation**: Tests modify `globalParameters` without cleanup. (Our Actionable item 7.)
- **Wrong filenames in `test_finds_and_processes_logic_files`**: Files named `logic_gfx908.yaml` don't match the architecture-name search logic. (Our Actionable item 2.)
- **Mocking defeats purpose**: Several tests mock everything and then check only that mocks were called. The reviewer specifically called out `test_avoid_regressions_basic` and `test_handles_known_bugs`. (Our Actionable item 4.)
- **Tests should verify post-state, not just counts**: `test_sanitize_without_stagger_u` and `removeDuplicatedSolutions` tests don't check data integrity. (Our Actionable item 8, Suggestion 12.)
- **Parameterize repetitive tests**: The message function tests and similar patterns should use `@pytest.mark.parametrize`. (Our Suggestion 10.)

### Prior approval (May 26)

A reviewer approved the PR and verified the dead-code removal (byte-identical bodies) and the `GlobalParameters.globalParameters` bug fix (latent `NameError`). Both of those changes have since been moved to #7849.

### Items from previous reviews: addressed vs. still present

| Item | Status |
|------|--------|
| Product code changes in own PR (reviewer feedback) | **Addressed** -- moved to #7849 |
| `test_main_basic_execution` vacuous pass (our review) | **Still present** |
| `TestCheckNamedTuple` tests stdlib (our review) | **Still present** |
| Weak `TestMergeLogic` assertions (this review plus prior reviewer feedback, June 2) | **Still present** |
| `fixSizeInconsistencies` test doesn't expose production bug (the reviewer, June 2) | **Still present** |
| Wrong filenames in `test_finds_and_processes_logic_files` (the reviewer, June 2) | **Still present** |
| Global state mutation without cleanup (the reviewer, June 2) | **Still present** |
| `test_handles_known_bugs` mocks away tested logic (the reviewer, June 2) | **Still present** |
| Weak post-state assertions (the reviewer, June 2) | **Still present** |

### New issues in this review not previously raised

- **Import fragility** (Actionable item 1): The tests trigger the full Tensile import chain requiring a matching `rocisa` build. The comment "# rocisa is mocked in the root conftest.py" in `test_TensileMergeLibrary.py` references mocking that does not exist. Previous reviews did not flag this because they had a compatible rocisa build.
- **Production `print` format-string bug**: `TensileUpdateLibrary.py:157` has `print("# LibraryLogicFiles:" % logicFiles)` which is a format-string error (no `%s` placeholder). The test does not catch this because it mocks `print1` but not `print`.
