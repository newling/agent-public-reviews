> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#10953 — `test(hipblaslt): stop characterization tests from reading library/src tuning data`](https://github.com/ROCm/rocm-libraries/pull/10953)

**Scope:** submitted head `708b6b3f7ee`

**Assessment:** REQUEST CHANGES

**Risk:** 2/5 — this is test-only isolation work, and the vendored fixtures
reproduce the intended kernels, but the new standing regression guard does not
actually implement the path-construction contract it claims.

## Tests

From `projects/hipblaslt/tensilelite`, after installing the repository-local
`rocisa` package and `syrupy` into the project virtual environment:

```bash
/usr/bin/time -p $VENV/bin/python -m pytest -q -rs \
  Tensile/Tests/unit/characterization/_codegen/test_no_library_src_dependency_char.py \
  Tensile/Tests/unit/characterization/_codegen/test_emit_bigfiles_char.py
```

Result: 11 passed, 0 failed, 0 skipped, and 0 errored in 50.97 seconds
(51.64 seconds wall time). All 10 existing snapshots passed without an update.

I also parsed each vendored fixture and its corresponding production tuning
file with the repository's `solutions_from_logic()` helper, generated kernel
objects with `generateKernelObjectsFromSolutions()`, sorted their
`getKernelFileBase(False, kernel)` values, and checked:

```python
fixture_names == production_names[:cap]
```

All 10 comparisons passed. The production files contained between 3 and 212
kernels; the fixtures contained exactly the capped prefix (3, 4, or 6 kernels,
as applicable). A separate YAML structural probe found contiguous remapped
`SolutionIndex` values and no matching-table references outside those values.

The focused counterexample probe in Appendix A completed in 0.09 seconds and
produced:

```text
legitimate_tool_name ['rocblaslt']
split_old_path []
```

Thus the guard flags a harmless executable name while missing a path that
reconstructs all three forbidden production-tree segments.

`git diff --check` passed for the PR diff.

At review time on August 26, 2026, the directly relevant public checks are
green: pre-commit, TensileLite coverage, the TensileLite unit/codecov job, the
gfx942 TensileLite test shard, and hipBLASLt precheckin/static analysis all
pass. The overall PR is not green: aggregate Math CI, preliminary hipBLASLt,
project Codecov, and several release jobs report failure. The PR is also
currently merge-conflicted with `develop`.

## Summary

The PR removes `test_emit_bigfiles_char.py`'s dependency on ten mutable
production tuning files. It adds ten trimmed YAML fixtures containing the
solutions needed for the existing capped-and-sorted kernel sets, points the
test at those local fixtures, and removes the missing-product-tree skip.

The fixture portion works as intended at the submitted head. Each fixture
parses and emits successfully, preserves the existing golden, and reproduces
the exact sorted kernel prefix from its production source.

The PR also adds an AST-based policy test intended to prevent any
characterization test from reconstructing the old `library/src/...` path. That
guard checks individual string constants for any occurrence of `amd_detail`,
`rocblaslt`, or `asm_full`; it does not determine whether a string participates
in a path. That mismatch creates both false positives and false negatives.

## Actionable items

1. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/test_no_library_src_dependency_char.py:35-59,62-84`
   — make the guard recognize product-tree paths rather than unrelated string
   tokens.**

   `_forbidden_literals_in_file()` reports any string constant containing one
   forbidden substring. A perfectly legitimate characterization assertion or
   docstring mentioning `"rocblaslt-bench"` is therefore rejected even though
   it constructs no path. Conversely, the exact forbidden path can be rebuilt
   from ordinary constant expressions such as `"amd_" + "detail"`,
   `"roc" + "blaslt"`, and `"asm_" + "full"`; the AST walk sees only the split
   operands and reports nothing. Appendix A demonstrates both behaviors.

   This recreates the class of unrelated-test failures the PR is intended to
   remove, while providing only a syntactic convention—not the stated
   guarantee that the suite cannot read the production tree.

   Evaluate literal path expressions as a unit, including `os.path.join`,
   `pathlib.Path` `/`, concatenation, and f-strings, then reject only a resolved
   path containing the relevant `library/src` production-tree structure.
   Alternatively, narrow the documented contract to the precise syntax the
   guard enforces. Add direct tests for the original path, joined and
   concatenated variants, harmless product/tool names, docstrings, and
   unrelated `library` paths.

2. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/DECISIONS.md:475-485`
   — rebase onto current `develop` and resolve the existing catalog conflict
   before this can merge.**

   A three-way merge against current `develop` reports a content conflict in
   this file. The base has accumulated additional characterization decisions,
   so resolving this by accepting either complete side would lose entries.
   Rebase, preserve the current catalog, append D21 at the next valid position,
   and rerun the focused snapshot tests on the rebased code. The current
   `develop` bigfile snapshot has changed since this PR's merge base, so the
   unchanged-golden claim must be revalidated after the rebase rather than
   assumed from the submitted head.

## Suggestions

1. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/DECISIONS.md:481-485`
   — remove the stale “Open item.”**

   It says a full ADR is probably unnecessary and should be added only after
   review confirmation, but this PR already adds accepted ADR 0012 and links it
   immediately above. Keep the catalog entry to the ADR link and concise
   decision summary, consistent with `adr/README.md`.

2. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/adr/0012-decouple-bigfile-tests-from-library-src.md:23-41`
   and `_codegen/data/bigfiles/*.yaml` — preserve reproducible fixture
   provenance.**

   The ADR says the 358 KiB fixture set was selected and remapped
   programmatically, but neither the extractor nor a source-path mapping is
   committed. Add a small deterministic extraction/check script, or at least a
   table of each fixture's original relative path plus the exact selection and
   remapping command. This would let a future reviewer audit or intentionally
   refresh the fixtures without reconstructing the removed `_BIG` mapping from
   Git history.

## Commentary

Decoupling characterization tests from mutable production tuning data is the
right boundary. The local emit run and independent name comparison support the
fixture selection: I did not find a mismatch, stale solution reference, or
snapshot change in the submitted revision.

The remaining concern is precision of the permanent policy check. A guard
against test-data coupling should itself be resistant to ordinary refactors and
should not ban legitimate terminology throughout an entire Python subtree.

## Appendix A: token scanning is both over- and under-inclusive

Run from `projects/hipblaslt/tensilelite`:

```bash
$VENV/bin/python - <<'PY'
import importlib.util
import tempfile
from pathlib import Path

module_path = Path(
    "Tensile/Tests/unit/characterization/_codegen/"
    "test_no_library_src_dependency_char.py"
)
spec = importlib.util.spec_from_file_location("guard", module_path)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

cases = {
    "legitimate_tool_name": 'TOOL = "rocblaslt-bench"\n',
    "split_old_path": (
        'import os\n'
        'PATH = os.path.join("library", "src", "amd_" + "detail", '
        '"roc" + "blaslt", "asm_" + "full")\n'
    ),
}

with tempfile.TemporaryDirectory() as directory:
    for name, source in cases.items():
        path = Path(directory) / f"{name}.py"
        path.write_text(source, encoding="utf-8")
        print(name, sorted(guard._forbidden_literals_in_file(path)))
PY
```

Observed output:

```text
legitimate_tool_name ['rocblaslt']
split_old_path []
```
