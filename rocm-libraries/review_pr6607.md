> This is a review from Claude Code with an automatic prompt from the reviewer

# Review: PR #6607 — added check to report warning for ProblemType mismatch during build time

**Author**: pdhirajkumarprasad
**Date reviewed**: 2026-05-27
**PR**: https://github.com/ROCm/rocm-libraries/pull/6607
**Status**: OPEN

## Tests

All 16 new tests pass in 0.17s. Command (from `projects/hipblaslt/tensilelite/`):

```
python -m pytest Tensile/Tests/unit/test_validateParameterTypes.py::TestValidateProblemTypeParameterTypes -v
```

The full test file (60 tests including pre-existing ones) passes in 0.21s.

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

Both parsers now agree on behavior: true/false → bool, 0/1 → int, yes/no → string.

## Correctness

### 1. `readYAML` now uses `StrictTypeLoader` globally — broader than necessary

`readYAML` is the general-purpose YAML reader used by `TensileLogic/Run.py`,
`TensileLibLogicToYaml.py`, `TensileUpdateLibrary.py`, and others. The
change from `yamlLoader` to `StrictTypeLoader` affects *all* YAML loading
throughout Tensile, not just the library logic path. This means:

- `yes`/`no` values will now parse as strings instead of booleans everywhere.
- `0`/`1` will always be int, never bool.

I verified no existing YAML files in the repo use `yes`/`no` as boolean
values, so this is likely safe in practice. But the change is silent and
broad — any downstream tool or script that writes YAML with `yes`/`no`
booleans and feeds it to Tensile will break.

This is the right thing to do (the old behavior was a footgun), but it
should be called out explicitly in the PR description since it's a
behavioral change to a widely-used function.

### 2. `StrictTypeLoader` passed to `load_yaml_stream` has no effect

In `LibraryIO.read()`, the `customizedLoader=True` path calls
`load_yaml_stream(filename, StrictTypeLoader)`. But `load_yaml_stream`
uses the event API with `CustomYamlLoader.parse_scalar`, which does its
own scalar parsing — it doesn't use the loader's implicit resolvers at all.
The loader type only matters for tokenization. So passing `StrictTypeLoader`
vs `yamlLoader` to `load_yaml_stream` is a no-op. The actual behavioral
change for the `customizedLoader=True` path comes from the
`CustomYamlLoader.py` changes (removing `yes`/`no`), not from
`StrictTypeLoader`.

Not a bug — just misleading. Consider a comment noting that
`load_yaml_stream` uses its own scalar parsing and doesn't rely on the
loader's implicit resolvers.

### 3. `resetTypeMismatchCollector()` move is correct

The `resetTypeMismatchCollector()` call was moved from just before Solution
parsing to the top of `parseLibraryLogicData`. This is correct: it now
clears before both ProblemType and Solution validation for each file.
Since `parseLibraryLogicData` is called per-file (including in parallel via
`ParallelMap2`), and each call ends with `getTypeMismatchCollector()` which
snapshots and returns the data, the per-file reset-then-snapshot pattern
is preserved. The main process merges all snapshots via
`mergeTypeMismatchCollector`.

## Design

### 4. Near-duplicate validation functions

`validateProblemTypeParameterTypes` in `Problem.py` is nearly identical to
`validateParameterTypes` in `Solution.py`. The only differences are:
- The source of expected types (`_expectedProblemTypeParamTypes` vs
  `_expectedParamTypes`).
- A function-level import of `_typeMismatchCollector` and `_skipTypeCheck`
  to avoid circular imports.

Consider extracting the common validation loop into a shared helper that
takes the expected-types dict as a parameter. This would eliminate the
duplication and make future changes (e.g., upgrading from warning to error)
simpler.

### 5. Comments are verbose

The PR adds multi-line comments and docstrings throughout. The
`StrictTypeLoader` class has a 4-line docstring plus 4 lines of comments
above the resolver manipulation. The `validateProblemTypeParameterTypes`
docstring is 11 lines for a function whose behavior is identical to its
sibling. A one-liner per block would be cleaner, especially if the common
pattern were extracted per point 4.

## Testing gaps

### 6. No integration test with actual YAML round-trip

The unit tests exercise `validateProblemTypeParameterTypes` with
hand-crafted dicts. There's no test that loads a YAML string through
`StrictTypeLoader` (or `CustomYamlLoader`) and confirms that 0/1 are
preserved as ints all the way through to ProblemType validation.
This would be the most valuable test to add — it's the exact scenario
the PR is designed to catch, and it would catch regressions if either
parser changes.

### 7. No test for `printTypeMismatchSummary` with ProblemType mismatches

The existing `TestPrintTypeMismatchSummary` tests only exercise Solution
mismatches. A test confirming that ProblemType mismatches appear in the
summary output would round things out — especially since the summary is
the user-visible output of this feature.

## Anything else

### 8. `BenchmarkProblems.py` summary call

The `printTypeMismatchSummary()` call added at the end of
`BenchmarkProblems.main()` doesn't pass `numFiles`, so the clean-path
message ("Checked N YAML logic files — no type mismatches found") won't
appear. Minor — the library-build path in `TensileCreateLibrary/Run.py`
does pass `numFiles`.
