> This is a review from an agent with an automatic prompt from the reviewer

## Tests

The PR adds no tests. There are no test files in the diff.

The existing script at `projects/hipblaslt/utilities/fix_yaml_types.py` has a companion test file (`test_fix_yaml_types.py`) with thorough coverage. This new script has none.

I manually tested the script by creating synthetic YAML files and running it:

```
python projects/hipblaslt/tensilelite/scripts/fix_yaml_types.py $TMP_YAML_FIXTURE --verbose
```

The script runs without errors and performs the conversions it claims to. I also tested `--list-parameters` and `--dry-run`, both of which work.

CI status: The one failing check (`rocblas shard 4 of 6`) is unrelated to this PR.

## Summary

This PR adds a new Python script (`projects/hipblaslt/tensilelite/scripts/fix_yaml_types.py`) that scans Tensile YAML configuration files and fixes type mismatches for ProblemType-level parameters. It uses `yaml.safe_load` to parse files, walks the data structure recursively to find parameters whose Python types don't match a hardcoded expected-type dictionary, converts them, and writes the result back with `yaml.dump`.

The script targets 34 parameters: 19 that should be `bool` (e.g. `TransposeA`, `UseBeta`, `Gradient`) and 15 that should be `int` (e.g. `UseBias`, `DataType`, `Sparse`). These are distinct from the parameters handled by the existing script at `projects/hipblaslt/utilities/fix_yaml_types.py`, which targets solution-level parameters like `DirectToLds`, `ExpandPointerSwap`, etc.

## Actionable items

### 1. yaml.dump destroys YAML formatting

**File:** `projects/hipblaslt/tensilelite/scripts/fix_yaml_types.py`, lines 275-292

The script uses `yaml.safe_load()` to parse and `yaml.dump()` to write. This destroys:
- All comments in the file
- Flow-style mappings (e.g. `{MinimumRequiredVersion: 4.33.0}` becomes `MinimumRequiredVersion: 4.33.0`)
- Flow-style sequences (e.g. `[Device 0049, Device 0050]` becomes a multi-line block sequence)
- Any custom formatting, indentation, or quoting

I verified this by running the script on a YAML file resembling the actual Tensile format. The existing script at `projects/hipblaslt/utilities/fix_yaml_types.py` avoids this problem entirely by using regex substitution on the raw text, which preserves all formatting. This new script should use the same approach: operate on the text content with regex rather than parsing and re-serializing the YAML. This is the most important issue in the PR.

### 2. Duplication with existing script

**File:** `projects/hipblaslt/tensilelite/scripts/fix_yaml_types.py` (entire file) vs `projects/hipblaslt/utilities/fix_yaml_types.py`

There is already a `fix_yaml_types.py` at `projects/hipblaslt/utilities/fix_yaml_types.py` that solves the same class of problem (YAML type mismatches) using a correct approach (regex). Rather than creating a second script with a different approach in a different location, extend the existing script by adding the new parameters to its parameter lists. The existing script already has well-organized groups (BOOL_TO_INT_PARAMS, INT_TO_BOOL_PARAMS, INT_TO_FLOAT_PARAMS) and a companion test suite. The new parameters would slot in naturally:
- The 19 bool parameters from this PR where the YAML has `0`/`1` instead of `false`/`true` would go into `INT_TO_BOOL_PARAMS`
- The 15 int parameters from this PR where the YAML has `false`/`true` instead of `0`/`1` would go into `BOOL_TO_INT_PARAMS`

### 3. `DataTypeC` and `DataTypeD` do not exist in Tensile

**File:** `projects/hipblaslt/tensilelite/scripts/fix_yaml_types.py`, lines 95-96

`DataTypeC` and `DataTypeD` are listed in the `PARAMETER_TYPES` dictionary but do not appear anywhere in the Tensile Python source (`Tensile/SolutionStructs/Problem.py`, `Tensile/Contractions.py`, etc.). The valid parameters are `DataType`, `DataTypeA`, `DataTypeB`, `DataTypeE`, `DestDataType`, and `ComputeDataType`. Including nonexistent parameters is misleading and suggests the list was not verified against the source. Remove `DataTypeC` and `DataTypeD`, or provide evidence that they exist.

### 4. Broad exception handling silently swallows errors

**File:** `projects/hipblaslt/tensilelite/scripts/fix_yaml_types.py`, lines 203-206

The `convert_value` method catches all exceptions and silently continues (only printing in verbose mode). If a conversion fails, the error is hidden and the parameter keeps its wrong type. This masks bugs in the conversion rules and in the parameter list. At minimum, the error should always be printed (not gated on `--verbose`). Better: let the exception propagate so the user knows something is wrong.

Similarly, `fix_yaml_file` (lines 306-308) catches all exceptions at the file level. A corrupt or unreadable file silently reports `False` instead of signaling an error.

### 5. Unused import

**File:** `projects/hipblaslt/tensilelite/scripts/fix_yaml_types.py`, line 47

`import os` is unused. Remove it.

## Suggestions

### 1. Add tests

The existing script has a companion `test_fix_yaml_types.py` with parameterized tests for each group, idempotency checks, CLI tests, etc. This new script should have equivalent coverage. If the recommendation to merge into the existing script is followed, the existing test suite should be extended with the new parameters.

### 2. Derive the parameter list from the source of truth

**File:** `projects/hipblaslt/tensilelite/scripts/fix_yaml_types.py`, lines 66-107

The hardcoded `PARAMETER_TYPES` dictionary duplicates information from `Tensile/SolutionStructs/Problem.py`'s `defaultProblemType` dictionary. The expected types could be derived programmatically from that dict (e.g. `{k: type(v) for k, v in defaultProblemType.items() if type(v) in (bool, int)}`). This would eliminate the risk of the list getting out of sync and would have caught the `DataTypeC`/`DataTypeD` error.

### 3. Support single-file mode

The script only accepts a directory argument. Adding support for a single file argument (or a glob pattern) would make it easier to use in targeted fixes and CI hooks.

## Commentary

The core problem this script solves is real: Tensile YAML files contain type mismatches where `yaml.safe_load` returns `int` for values that should be `bool` (or vice versa), and this causes issues downstream (e.g. msgpack serialization produces different wire types for `bool` vs `int`). The parameter list in this PR targets ProblemType-level parameters, which is complementary to the existing script's solution-level parameters.

However, the approach of using `yaml.safe_load` + `yaml.dump` is fundamentally wrong for this use case. YAML round-tripping through Python's `yaml` library is lossy: it destroys comments, flow-style formatting, and custom indentation. The existing script's regex approach is correct because type fixes for these parameters are simple text substitutions (e.g. `TransposeA: 0` to `TransposeA: false`) that don't require understanding the YAML structure.

The overall architecture of this PR -- a separate class with configurable type maps and conversion rules -- is over-engineered for what amounts to adding ~34 entries to an existing parameter list. The extensibility framework (conversion rules dict, skip parameters set) adds complexity without clear benefit over the existing script's simpler design.

## Previous review context

A reviewer requested changes and raised four points:

1. **"How did you assemble this list?"** (comment on lines 66-107, the PARAMETER_TYPES dictionary) -- Asking for the provenance of the parameter list. This overlaps with my actionable item #3 (DataTypeC/DataTypeD don't exist) and my suggestion #2 (derive the list from source). The question is unaddressed in the current code.

2. **"What is the difference between this and `projects/hipblaslt/utilities/fix_yaml_types.py`?"** (comment on line 1) -- Asking about duplication with the existing script. This directly overlaps with my actionable item #2. The question is unaddressed in the current code.

3. **"Why is this catching all errors?"** (comment on lines 203-206, the broad exception handler in `convert_value`) -- Asking why conversion errors are silently swallowed. This directly overlaps with my actionable item #4. The question is unaddressed in the current code.

4. **"This will strip all comments out of the files."** (comment on lines 275-276, the yaml.safe_load/yaml.dump approach) -- Flagging the formatting destruction issue. This directly overlaps with my actionable item #1, which is the most critical issue. The question is unaddressed in the current code.

All four of the reviewer's points are valid and remain unaddressed. My review independently identified the same issues and provides additional detail (e.g. the nonexistent `DataTypeC`/`DataTypeD` parameters, the unused `os` import, and the concrete recommendation to extend the existing script rather than creating a new one).
