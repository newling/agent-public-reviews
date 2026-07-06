> This is a review from an agent with an automatic prompt from the reviewer

# Review: PR #7722 (v2) -- Added test for ParseArguments, ValidMatrixInstruction, ValidWorkGroup, TensileClientConfig and Activation

**Date reviewed**: 2026-06-02
**PR**: https://github.com/ROCm/rocm-libraries/pull/7722
**Status**: OPEN

## Tests

All 216 tests pass (2 skipped) in 1.23s. Command (from
`projects/hipblaslt/tensilelite/`):

```
python -m pytest Tensile/Tests/unit/test_Activation.py \
  Tensile/Tests/unit/test_Activation_fusion.py \
  Tensile/Tests/unit/test_Activation_implementations.py \
  Tensile/Tests/unit/test_Activation_postprocess.py \
  Tensile/Tests/unit/test_ParseArguments.py \
  Tensile/Tests/unit/test_Problem.py \
  Tensile/Tests/unit/test_TensileClientConfig.py \
  Tensile/Tests/unit/test_ValidMatrixInstruction.py \
  Tensile/Tests/unit/test_ValidWorkGroup.py -v
```

The 2 skipped tests are `test_get_exp_module_half` and
`test_get_silu_module_half`, both marked with
`@pytest.mark.skip(reason="SelectBit not imported in Activation.py - code issue")`.
CI (hipblaslt pre-checkin, codecov, static-analysis) passes. The CI
failures are in unrelated rocblas/rocroller test shards.

## Summary

This PR adds pytest suites covering five Tensile modules
(`Activation`, `ParseArguments`, `ValidMatrixInstruction`,
`ValidWorkGroup`, `TensileClientConfig`) plus `Problem.py`, spread
across 9 new test files. It also adds one production-code change: a
re-export line in `Tensile/Common/__init__.py` that makes
`globalParameters`, `assignGlobalParameters`,
`restoreDefaultGlobalParameters`, and `__version__` importable via
`from Tensile.Common import ...`. The PR description states this
pairs with PR #7703.

Compared to the first version of this PR (reviewed on 2026-05-27),
this version addresses many of the issues raised in review: empty
`pass`-only tests, hallucinated method tests, vacuous
`test_module_exists`, `hasattr` guards, and several requests from
prior review feedback to improve correctness checking. The current version is
substantially better.

The test quality still varies by file. `test_TensileClientConfig.py`
and `test_Problem.py` remain the strongest: they exercise real code
with meaningful inputs and edge cases. The Activation suite now
covers many more methods with real assertions. However,
`test_ValidMatrixInstruction.py` and `test_ValidWorkGroup.py` still
mock away the actual validation logic and only test the try/except
wrapper.

## Actionable items

### 1. `test_ParseArguments.py` mutates `sys.argv` without cleanup

`Tensile/Tests/unit/test_ParseArguments.py`, lines 39, 51, 60, 71,
81, 91, 100, 117 -- Every test directly assigns to `sys.argv` but
never restores it. This leaks state into any test that runs later in
the same session and also reads `sys.argv`. While the tests currently
run in an order where this doesn't cause failures, it is fragile and
can break if test collection order changes or new tests are added.

**Fix:** Add a fixture that saves and restores `sys.argv`:
```python
@pytest.fixture(autouse=True)
def restore_sys_argv():
    original = sys.argv[:]
    yield
    sys.argv = original
```

### 2. `test_ParseArguments.py` documents a bug instead of fixing it

`Tensile/Tests/unit/test_ParseArguments.py`, lines 64-66 -- The test
asserts `args.Jobs == "16"` (string) and comments that this is
"inconsistent with default" (which is `int 48`). Line 123 asserts
`args.Jobs == "32"` (also string). This was raised in the v1 review
and by another reviewer. The author replied "fixed" but the code
is unchanged.

The root cause is in `ParseArguments.py` line 55-58: the `--jobs`
argument has `default=48` (int) but no `type=int`, so argparse
leaves CLI-provided values as strings.

**Fix:** Add `type=int` to the `--jobs` argument definition in
`Tensile/TensileLogic/ParseArguments.py` line 55. Then update the
test assertions to `assert args.Jobs == 16` and
`assert args.Jobs == 32` (integers). Remove the apologetic comment.

### 3. `test_ValidMatrixInstruction.py` and `test_ValidWorkGroup.py` only test the try/except wrapper

`Tensile/Tests/unit/test_ValidMatrixInstruction.py`, all tests --
Every "valid" test case patches `validateMIParameters` with a no-op
mock, then asserts the wrapper returns True. The "invalid" cases set
`Valid=False` or make the mock raise `AssertionError`. No test
actually calls the real validator. Same pattern in
`test_ValidWorkGroup.py`.

These tests confirm only that `_validateMatrixInstruction` and
`_validateWorkGroup` return True when the inner call succeeds, and
False when it raises. This is trivially visible from the 10-line
source. The tests add no value for catching regressions in the
validation logic itself.

**Fix:** Add at least a few tests that call the real
`validateMIParameters`/`validateWorkGroup` with known-good and
known-bad solution dicts (without patching). This is where the
coverage value would come from.

### 4. `test_Activation_fusion.py` uses runtime signature inspection

`Tensile/Tests/unit/test_Activation_fusion.py`, lines 232-238 --
`test_convert_coeff_to_hex_basic` uses `inspect.signature` at
runtime to decide how many arguments to pass to
`ConvertCoeffToHex`. This means the test adapts to whatever
signature it finds rather than verifying a specific contract. If
the signature changes in a breaking way, this test will silently
accommodate it instead of catching the regression.

**Fix:** Remove the `inspect.signature` check and call
`ConvertCoeffToHex` with the expected arguments directly. If the
function has a known signature, test that signature. If it is
genuinely polymorphic, write two tests -- one for each variant.

### 5. Unused imports across multiple files

The following imports are present but never used:

- `test_Activation.py:26` -- `MagicMock` (only `Mock` and `patch` are used)
- `test_Activation_fusion.py:26` -- `MagicMock` (never used)
- `test_Activation_fusion.py:28` -- `SNop` (never used)
- `test_Activation_implementations.py:26` -- `MagicMock` (never used)
- `test_Activation_postprocess.py:26` -- `MagicMock` and `PropertyMock` (never used)
- `test_TensileClientConfig.py:26` -- `MagicMock` and `mock_open` (never used)
- `test_Problem.py:27` -- `MagicMock` (never used)

**Fix:** Remove unused imports from each file.

### 6. `Common/__init__.py` re-export needs coordination with PR #7703

`Tensile/Common/__init__.py`, line 2 -- This adds:
```python
from .GlobalParameters import globalParameters, assignGlobalParameters, restoreDefaultGlobalParameters, __version__
```

On `develop`, `Common/__init__.py` only has star-imports from
Constants, Parallel, Types, and Utilities. None of those modules
export `globalParameters` or `assignGlobalParameters`. So this
re-export is genuinely new. The PR description says it pairs with
#7703, but #7703 is still open. If this PR merges first, the
re-export works standalone. If #7703 merges first and changes the
import structure, merge conflicts or double-definitions could arise.

**Fix:** Confirm the merge order with the #7703 author. If this PR
must stand alone, add a brief comment on the line explaining why the
explicit re-export is needed (e.g., "# Preserve historical import
path; see PR #7703").

## Suggestions

### 7. Move shared fixtures to `conftest.py`

The `Activation` fixture (lazy import of `Tensile.Activation`) is
defined identically in four files:
- `test_Activation.py:30-33`
- `test_Activation_fusion.py:31-34`
- `test_Activation_postprocess.py:30-33`

The `DataType` fixture is duplicated in
`test_Activation_postprocess.py:37-40`.

A `conftest.py` already exists for the unit test directory. Moving
these shared fixtures there would eliminate the duplication. (Note:
`test_Activation_implementations.py` uses a top-level import instead
of a fixture, which is also fine -- the inconsistency itself is
minor.)

### 8. Several "not None" assertions could be more specific

Many tests across the Activation files assert only `result is not
None` after calling real code. Examples:
- `test_Activation_implementations.py:1012` (`test_get_abs_module_single`)
- `test_Activation_implementations.py:1024` (`test_get_abs_module_half`)
- Many others with the same pattern.

While these are better than the v1 tests (which sometimes asserted
nothing), they only verify the function didn't crash. Where possible,
assert something about the returned Module -- e.g., that it is a
`Module` instance (`assert isinstance(result, Module)`), that it
contains at least one instruction, or that specific register counts
changed as expected. Some tests already do this well (e.g., checking
`module.vgprCounter > 0` or `module.needCombine == True`); apply that
standard more consistently.

### 9. `test_Activation_postprocess.py` test class `TestReplaceAndRemoveInstFunctions` is empty

`Tensile/Tests/unit/test_Activation_postprocess.py` (in the diff,
around line 213) -- `TestReplaceAndRemoveInstFunctions` has a
class-level comment "These functions are internal helpers -- no need
to test existence" but contains no test methods. An empty test class
is noise.

**Fix:** Delete the empty class, or add at least one test for
`replaceInst` or `removeOldInst` if coverage is the goal.

### 10. `test_Activation_fusion.py` has a `TestFuseInstructionHelpers` class in `test_Activation_postprocess.py`

Tests for `FuseInstruction` and `CombineInstructionsBetweenModules`
appear in both `test_Activation_fusion.py` (lines 293-325) and
`test_Activation_postprocess.py` (lines 233-249). The postprocess
file's versions are weaker (one just checks `hasattr`, the other
passes empty inputs and asserts nothing beyond no-crash). Having the
same functions tested in two files with different quality levels is
confusing.

**Fix:** Consolidate these tests into `test_Activation_fusion.py`
and remove the duplicates from `test_Activation_postprocess.py`.

## Commentary

The overall test suite has improved meaningfully since v1. The
Activation tests now exercise real `ActivationModule` methods
(`getAbsModule`, `getReluModule`, `getGeluModule`, etc.) across
multiple data types, checking return values and side effects like
register counter updates. The fusion tests for `FindUseIter` and
`FindAssignAndUseIter` use real `rocisa` instructions, which makes
them genuinely useful for catching regressions.

`test_TensileClientConfig.py` remains the strongest file, with
thorough edge-case coverage of `getGlobalParams`, `getProblemDict`,
`getSizeList`, and `parseConfig`. `test_Problem.py` is also solid,
testing `ProblemType.assignDerivedParameters` and
`ExactList.convertLeadingDims` with real inputs.

The weakest files remain `test_ValidMatrixInstruction.py` and
`test_ValidWorkGroup.py`. Their source modules are 10-line wrappers,
and the tests mock away the only interesting call. If the goal is
coverage of the validation logic, the tests should call the real
validators.

## Previous review context

### Our previous review (2026-05-27)

Our v1 review raised 8 items:

1. **Empty `pass`-only tests** (`test_activation_has_args_function`,
   `test_activation_arg_names_function`) -- **Addressed.** These
   tests are removed in v2.

2. **Vacuous `test_module_exists`** -- **Addressed.** Removed.

3. **`test_parse_arguments_with_jobs` type inconsistency** (Jobs is
   `str` vs `int`) -- **Not addressed.** The test still asserts
   `args.Jobs == "16"` (string) and the comment documents the
   inconsistency. The source-level fix (`type=int` on the argparser)
   was not applied.

4. **Unused `MagicMock` import in `test_Activation_fusion.py`** --
   **Not addressed.** `MagicMock` is still imported but unused in
   this file and in several others.

5. **Mock parameter names swapped in
   `test_post_process_with_combine`** -- **This was incorrect in the
   v1 review.** Re-examining the decorator stacking order, the names
   `mock_convert` and `mock_combine` correctly match the patched
   targets (`ConvertCoeffToHex` and `CombineInstructions`
   respectively). The v1 review was wrong on this point.

6. **Move shared fixtures to `conftest.py`** -- **Not addressed.**
   The `Activation` fixture is still duplicated across files.

7. **Replace `hasattr` guards with direct assertions** -- **Mostly
   addressed.** The v2 code has removed most of the `if hasattr`
   guards. A few `hasattr` checks remain (e.g., in
   `test_Activation_postprocess.py` `test_fuse_instruction_exists`)
   but these are now in dedicated existence-check tests rather than
   guarding functional tests.

8. **`test_ValidMatrixInstruction` and `test_ValidWorkGroup` mock
   away the validators** -- **Not addressed.** The tests are
   unchanged and still only test the try/except wrapper.

### Prior review (2026-05-26, CHANGES_REQUESTED)

The reviewer's top-level comment: "Most of the tests do not appear to check
the correctness of the code they exercise beyond checking that it
doesn't crash/return the correct datatype. The tests need to be
expanded significantly to test correctness."

Specific inline comments from the reviewer:

- **Empty/vacuous tests and hallucinated methods** (multiple items
  in `test_Activation.py`) -- **Addressed.** The empty `pass` tests,
  hallucinated method tests, and vacuous existence checks are removed.

- **Tests not checking correctness** (in `test_Activation_fusion.py`,
  `test_Activation_postprocess.py`) -- **Partially addressed.** Some
  tests now include real assertions (e.g., `FindUseIter` tests with
  real instructions, `postProcess` tests with mock call verification).
  However, many implementation tests still only assert
  `result is not None`.

- **Why imports as fixtures?** (in
  `test_Activation_implementations.py`) -- **Addressed.** That file
  now uses top-level imports instead of fixtures.

- **`test_Problem.py` import pattern** ("Why is this needed?") --
  **Not changed**, but the `import_module` pattern is defensible for
  avoiding circular import issues through `__init__.py`.

### New issues in this review not raised previously

- `sys.argv` mutation without cleanup in `test_ParseArguments.py`
  (actionable item 1).
- Runtime `inspect.signature` usage in `test_Activation_fusion.py`
  (actionable item 4).
- Unused `PropertyMock`, `mock_open`, `SNop` imports (actionable
  item 5 -- expanded beyond the single `MagicMock` case in v1).
- `Common/__init__.py` re-export coordination with PR #7703
  (actionable item 6).
- Empty `TestReplaceAndRemoveInstFunctions` class (suggestion 9).
- Duplicate `FuseInstruction` tests across two files (suggestion 10).
