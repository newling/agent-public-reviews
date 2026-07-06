> This is a review from Claude Code with an automatic prompt from the reviewer

# Review: PR #6607 — added check to report warning for ProblemType mismatch during build time

**Date reviewed**: 2026-05-27
**PR**: https://github.com/ROCm/rocm-libraries/pull/6607
**Status**: OPEN

## Tests

All 16 new tests pass in 0.17s. Command (from `projects/hipblaslt/tensilelite/`):

```
python -m pytest Tensile/Tests/unit/test_validateParameterTypes.py::TestValidateProblemTypeParameterTypes -v
```

The full test file (60 tests including pre-existing ones) passes in 0.21s.
No failures, no environment-specific issues.

## Summary

Extends the existing Solution-level parameter type validation (int vs bool
mismatches) to also cover ProblemType parameters. Previously, only Solution
parameters were checked via `validateParameterTypes` in `Solution.py`. This
PR adds `validateProblemTypeParameterTypes` in `Problem.py` that validates
ProblemType parameters against the types implied by `_defaultProblemType`.

The PR also changes YAML loading to distinguish 0/1 (int) from true/false
(bool) — without this, the validation would never see a mismatch because
the YAML parser would silently convert 0/1 to booleans. Two changes
accomplish this:
1. A new `StrictTypeLoader` in `LibraryIO.py` that strips the default YAML
   bool resolver (which treats 0/1/yes/no as booleans) and replaces it with
   one that only matches `true`/`false`/`True`/`False`.
2. The custom event-based parser in `CustomYamlLoader.py` is updated to
   match: `yes`/`no` no longer parse as booleans.

Both parsers now agree on behavior: true/false → bool, 0/1 → int, yes/no →
string.

The `resetTypeMismatchCollector()` call was moved from just before Solution
parsing to the top of `parseLibraryLogicData`. This is correct: it now
clears before both ProblemType and Solution validation for each file, and
the per-file reset-then-snapshot pattern for parallel workers is preserved.

## Actionable items

### 1. `readYAML` globally changed — PR description should note this

`Tensile/LibraryIO.py:355-358` — `readYAML` now uses `StrictTypeLoader`
instead of `yamlLoader`. This is the general-purpose YAML reader used by
`TensileLogic/Run.py`, `TensileLibLogicToYaml.py`,
`TensileUpdateLibrary.py`, and others. The change means `yes`/`no` will now
parse as strings instead of booleans everywhere, and `0`/`1` will always be
int, never bool.

I verified no existing YAML files in the repo use `yes`/`no` as boolean
values, so this is likely safe. But it's a behavioral change to a
widely-used function that should be called out in the PR description.

**Fix:** Add a note to the PR description stating that `readYAML` now uses
`StrictTypeLoader` globally, and that `yes`/`no` are no longer parsed as
booleans anywhere in Tensile.

### 2. `StrictTypeLoader` passed to `load_yaml_stream` has no effect

`Tensile/LibraryIO.py:348` — the `customizedLoader=True` path calls
`load_yaml_stream(filename, StrictTypeLoader)`. But `load_yaml_stream`
(in `CustomYamlLoader.py:77`) uses the event API with its own
`parse_scalar` function — it doesn't use the loader's implicit resolvers.
The loader type only matters for tokenization. So passing
`StrictTypeLoader` vs `yamlLoader` here is a no-op. The actual behavioral
change for this path comes from the `CustomYamlLoader.py` changes (removing
`yes`/`no` from `parse_scalar`), not from `StrictTypeLoader`.

**Fix:** Add a comment at `LibraryIO.py:348` noting that `load_yaml_stream`
uses its own scalar parsing and the loader type does not affect bool/int
resolution on this path.

### 3. `printTypeMismatchSummary()` call missing `numFiles`

`Tensile/BenchmarkProblems.py:737` — `printTypeMismatchSummary()` is called
without `numFiles`, so the clean-path message ("Checked N YAML logic
files — no type mismatches found") will never appear on this code path.
The library-build path in `TensileCreateLibrary/Run.py:734` does pass
`numFiles`.

**Fix:** Pass the number of processed files as `numFiles`, or remove the
parameter from `printTypeMismatchSummary`'s signature if the clean-path
message isn't wanted here.

## Suggestions

### 4. Add a YAML round-trip integration test

`Tensile/Tests/unit/test_validateParameterTypes.py` — the new tests
exercise `validateProblemTypeParameterTypes` with hand-crafted dicts.
There's no test that loads a YAML string through `StrictTypeLoader` (or
`CustomYamlLoader`) and confirms that 0/1 are preserved as ints all the way
through to ProblemType validation. This would be the most valuable test to
add — it's the exact scenario the PR is designed to catch.

### 5. Add a `printTypeMismatchSummary` test with ProblemType mismatches

`Tensile/Tests/unit/test_validateParameterTypes.py` — the existing
`TestPrintTypeMismatchSummary` tests only exercise Solution mismatches. A
test confirming that ProblemType mismatches appear in the summary output
would verify the user-visible output of this feature.

### 6. Extract the common validation loop

`Tensile/SolutionStructs/Problem.py:752-791`
(`validateProblemTypeParameterTypes`) is nearly identical to
`Tensile/SolutionStructs/Solution.py:136-173` (`validateParameterTypes`).
The only differences are the source of expected types and a function-level
import to avoid circular deps. Extracting the shared loop into a helper
that takes the expected-types dict as a parameter would eliminate the
duplication.

## Commentary

The `StrictTypeLoader` approach (stripping the default YAML bool resolver
and adding back a narrower one) is a clean solution. I verified it doesn't
mutate the parent `yamlLoader` class — the dict comprehension at
`LibraryIO.py:94-97` creates a new dict. The `CustomYamlLoader.py` changes
are consistent: both parsers now agree that `true`/`false` are bool,
`0`/`1` are int, and `yes`/`no` are strings.

The PR's verbose docstrings and multi-line comments (e.g., 4-line docstring
+ 4 lines of comments for `StrictTypeLoader` at lines 81-105, 11-line
docstring for `validateProblemTypeParameterTypes` at lines 752-766) are
heavier than the codebase norm. A one-liner per block would be cleaner.
