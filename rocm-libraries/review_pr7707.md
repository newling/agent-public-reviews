> This is a review from Claude Code with an automatic prompt from the reviewer

# Review: PR #7707 — Added unit test for KernelWriterBetaOnly, ShiftVectorComponents and WorkGroupMappingAlgos

**Author**: pdhirajkumarprasad
**Date reviewed**: 2026-05-27
**PR**: https://github.com/ROCm/rocm-libraries/pull/7707
**Status**: OPEN

## Tests

When targeting the three new test files directly,
`test_ShiftVectorComponents.py` fails to collect due to a circular import:

```
python -m pytest Tensile/Tests/unit/test_KernelWriterBetaOnly.py Tensile/Tests/unit/test_ShiftVectorComponents.py Tensile/Tests/unit/test_WorkGroupMappingAlgos.py -v
```

```
AttributeError: cannot access submodule 'ShiftVectorComponents' of
module 'Tensile.Components' (most likely due to a circular import)
```

However, when running the full unit test directory (`python -m pytest
Tensile/Tests/unit/ -v`), all 8 ShiftVectorComponents tests pass (910
total passed, 6 skipped, 0 errors, 40.52s). The circular import only
triggers when `test_ShiftVectorComponents.py` is the first file to import
`Tensile.Components.ShiftVectorComponents`. When other test files are
collected first, they import `Tensile.Component` which resolves the
`from .Components import *` before `ShiftVectorComponents` is accessed as a
submodule, breaking the cycle. CI passes for the same reason — it runs the
full directory.

This is an import-order fragility, not a real test failure. But it means
`test_ShiftVectorComponents.py` cannot be run in isolation, which is a
problem for development workflows.

The remaining tests alone:

```
python -m pytest Tensile/Tests/unit/test_KernelWriterBetaOnly.py Tensile/Tests/unit/test_WorkGroupMappingAlgos.py -v
```

58 passed, 1 skipped, 0.14s.

## Summary

Adds pytest suites for three code-generator modules that emit GPU assembly
instruction sequences (rocisa `Module` objects). No product code changes.

`test_KernelWriterBetaOnly.py` is the strongest file — it uses real
`DataType` objects and real state dicts, and checks the content of
generated C++ code. The other two files rely more heavily on mocking.

## Actionable items

### 1. `test_ShiftVectorComponents.py` cannot be collected in isolation

`Tensile/Tests/unit/test_ShiftVectorComponents.py:34` — the module-level
import `from Tensile.Components.ShiftVectorComponents import ...` triggers
a circular import chain: `ShiftVectorComponents.py:36` →
`Component.py:295` (`from .Components import *`) → back to
`ShiftVectorComponents`.

**Fix:** Move the import into a module-scoped fixture:
```python
@pytest.fixture(scope="module")
def SVC():
    from Tensile.Components.ShiftVectorComponents import (
        ShiftVectorComponentsVALU, ShiftVectorComponentsMFMA
    )
    return SimpleNamespace(VALU=ShiftVectorComponentsVALU, MFMA=ShiftVectorComponentsMFMA)
```
Then use `SVC.VALU` / `SVC.MFMA` in test methods.

### 2. `test_init_float8_fnuz` is a permanent skip

`Tensile/Tests/unit/test_KernelWriterBetaOnly.py:99` — calls
`pytest.skip("DataType code for float8_fnuz not straightforward to mock")`.
But the other tests use real `DataType` objects, not mocks. The skip
message is misleading.

**Fix:** Either implement the test with the correct DataType code for
fnuz, or delete the test method entirely.

### 3. Four `assert callable(...)` tests are vacuous

`Tensile/Tests/unit/test_WorkGroupMappingAlgos.py:317,326,335` — three
tests in `TestSpaceFillingCurveWalk` only assert
`callable(SpaceFillingCurveWalk)`. Line 136 — `test_with_streamk_and_wgmxcc_neg1`
only asserts `callable(wgmXCC)`. These are proven by the import at the top
of the file and can never fail.

**Fix:** Delete all four test methods. If the intent is to test these
functions, add real assertions on their return values.

### 4. `len(source) > 200` / `len(header) > 100` assertions are meaningless

`Tensile/Tests/unit/test_KernelWriterBetaOnly.py:480,490` —
`test_source_file_grouped_gemm_toggle` and
`test_header_file_grouped_gemm_toggle` assert only that the output is
longer than a threshold. These pass for any non-trivial output.

**Fix:** Assert that both `"_GG"` and non-`"_GG"` kernel names appear in
the output, since `getSourceFileString` iterates over `[True, False]` for
GroupedGemm.

## Suggestions

### 5. Extract `create_basic_state` into a shared fixture

`Tensile/Tests/unit/test_KernelWriterBetaOnly.py` — `create_basic_state`
is defined at lines 36, 128, 221, and 427 with near-identical bodies.
Extract into a module-level `@pytest.fixture` or factory function. Callers
can add extra keys as needed.

### 6. Extract `create_mock_writer` into a shared fixture

`Tensile/Tests/unit/test_WorkGroupMappingAlgos.py` — `create_mock_writer`
appears at lines 96, 160, 217, 254, 286, 342, 459, 515, 575. All return
10 for sgpr and 20 for vgpr checkouts. Extract to a module-level helper.

### 7. Strengthen `test_KernelWriterBetaOnly` assertions

Several tests assert content present in all kernel bodies regardless of
configuration:
- Line 242: `test_kernel_body_global_accumulation` asserts
  `"GLOBAL_D" in body` — present in all bodies.
- Line 325: `test_kernel_body_high_precision_accumulate` asserts
  `"SCALAR_ZERO" in body` — present in all bodies.
- Line 207: `test_function_signature_global_accumulation` checks
  `writer.kernelName in sig` — true for any config.

Instead, assert something specific to the configuration axis (e.g., that
global accumulation uses `ComputeDataType` for the D pointer, or that HPA
uses `DataType('s')` for the cast type).

## Commentary

The `test_ShiftVectorComponents.py` mocking strategy replaces
`vgprPool.checkOut` with a function that always returns 10 (same register
for every allocation), `accVgprReadWriteFunction` with `SMovB32`, and all
three `vectorStatic*` functions with dummy instructions. The generated
assembly is therefore nonsensical, and the assertions (`assert result is
not None`, `checkOut.call_count > 0`) only verify the function didn't
crash. These are crash-tests rather than correctness tests. They won't
catch bugs in register allocation, instruction selection, or the shift
algorithm.
