> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#10953 — `test(hipblaslt): stop characterization tests from reading library/src tuning data`](https://github.com/ROCm/rocm-libraries/pull/10953)

**Scope:** updated head `7104e12d523`

**Review mode:** independent updated-head refresh; existing PR discussion was
not used as review evidence.

**Assessment:** REQUEST CHANGES

**Risk:** 2/5 — this is test-only isolation work, but the updated head fails its
own focused snapshots, carries unrelated catalog changes from conflict
resolution, and adds a standing regression guard that does not implement the
path-construction contract it claims.

## Tests

From `projects/hipblaslt/tensilelite`, after installing the repository-local
`rocisa` package and `syrupy` into the project virtual environment:

```bash
/usr/bin/time -p $VENV/bin/python -m pytest -q -rs \
  Tensile/Tests/unit/characterization/_codegen/test_no_library_src_dependency_char.py \
  Tensile/Tests/unit/characterization/_codegen/test_emit_bigfiles_char.py
```

Result: 8 passed, 3 failed, 0 skipped, and 0 errored in 55.30 seconds
(56.16 seconds wall time). The failing snapshot cases are:

- `equality_gfx950_HSS_big`;
- `gfx950_origami_MX`; and
- `gfx1201_I8II`.

Every kernel still emitted with error code zero; the failures are basename
snapshot mismatches.

I parsed each vendored fixture and its corresponding production tuning file
with the repository's `solutions_from_logic()` helper, generated kernel objects
with `generateKernelObjectsFromSolutions()`, sorted their
`getKernelFileBase(False, kernel)` values, and checked:

```python
fixture_names == production_names[:cap]
```

Seven comparisons passed. The same three cases that fail their snapshots no
longer equal the current production files' capped prefixes:

```text
equality_gfx950_HSS_big: exact_prefix=False
gfx950_origami_MX: exact_prefix=False
gfx1201_I8II: exact_prefix=False
```

The comparison probe completed in 33.59 seconds. A separate YAML structural
probe found contiguous remapped `SolutionIndex` values and no matching-table
references outside those values.

The focused counterexample probe in Appendix A completed in 0.09 seconds and
produced:

```text
legitimate_tool_name ['rocblaslt']
split_old_path []
```

Thus the guard flags a harmless executable name while missing a path that
reconstructs all three forbidden production-tree segments.

`git diff --check` passed for the PR diff.

At review time on August 26, 2026, pre-commit passes on the updated head, but
TensileLite coverage and the Math CI TensileLite unit/codecov status fail.
Several broader jobs are still running. GitHub now reports the branch as
mergeable.

## Summary

The PR removes `test_emit_bigfiles_char.py`'s dependency on ten mutable
production tuning files. It adds ten trimmed YAML fixtures containing the
solutions needed for the existing capped-and-sorted kernel sets, points the
test at those local fixtures, and removes the missing-product-tree skip.

Each fixture still parses and emits successfully. However, after current
`develop` was merged into the branch, three fixtures no longer reproduce the
corresponding current capped kernel set and no longer match the inherited
snapshots.

The PR also adds an AST-based policy test intended to prevent any
characterization test from reconstructing the old `library/src/...` path. That
guard checks individual string constants for any occurrence of `amd_detail`,
`rocblaslt`, or `asm_full`; it does not determine whether a string participates
in a path. That mismatch creates both false positives and false negatives.

## Actionable items

1. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/test_emit_bigfiles_char.py:47-54`,
   `_codegen/__snapshots__/test_emit_bigfiles_char.ambr:30-57,86-113,158-185`,
   and the corresponding three files under `_codegen/data/bigfiles/` — update
   the fixtures for the merged base and restore a passing focused test.**

   The updated head fails `equality_gfx950_HSS_big`, `gfx950_origami_MX`, and
   `gfx1201_I8II`. All three still emit successfully, but their generated
   basenames differ from the snapshots inherited from current `develop`.
   Independently comparing each fixture with its current production source
   shows that these are also exactly the three fixtures that no longer
   reproduce the source file's sorted `[:cap]` kernel prefix.

   Regenerate these trimmed fixtures from the current production inputs,
   including solution-index and matching-table remapping, and confirm that the
   resulting fixture output matches the existing base snapshots. If retaining
   the older fixture configurations is intentional instead, update and review
   only the three affected snapshot nodes and document why the PR now changes
   behavior relative to its base. Do not merge the current revision with its
   directly targeted test failing.

2. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/test_no_library_src_dependency_char.py:35-59,62-84`
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

3. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/DECISIONS.md:281-309`
   — preserve current `develop`'s D20 cleanup instead of restoring the removed
   historical prose during conflict resolution.**

   Relative to current `develop`, the merge resolution expands D20 from its
   canonical one-sentence summary back into the older multi-paragraph version,
   including a stale note about tests that still needed confirmation. That
   cleanup was already merged as part of the ADR/catalog split and is unrelated
   to D21.

   Restore D20 exactly as it appears on current `develop`, then append only the
   new D21 entry. This keeps the PR scoped to its own decision and avoids
   reversing an already-merged documentation cleanup.

## Suggestions

1. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/DECISIONS.md:305-309`
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
right boundary. At the originally reviewed revision, all fixtures matched both
their production source prefixes and the snapshots. The merge with current
`develop` invalidated that result for three cases, so the fixture extraction
needs to be refreshed before the intended boundary is established on the
actual merge candidate.

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
