This is a review from an agent with an automatic prompt from the reviewer

## Tests

A dependency-light production harness passed the current non-experimental corpora (2,773 hipBLASLt YAML files and 355 hipSPARSELt YAML files, zero invariant violations). The focused pytest suite was not run locally because pytest is unavailable in the existing environment and no dependencies were installed. CI currently fails five characterization tests and the gfx125X shared-consumer build; the failures are described below.

## Summary

The follow-up substantially improves the first revision. The sibling check now receives the caller's selected files, handles the direct architecture layout, and distinguishes CU and chip-ID variants. Moving `DeviceNames` parsing to the event-based YAML reader also covers mapping-form and multiline headers, while a missing field participates in comparison rather than being dropped. The regular `Run.main()` tests were updated after the rebase.

The remaining problems are at the boundary between that generic logic and its consumers: a requested `gfx1250v0` target does not uniquely identify a corpus that owns the v0 overlay, and the new mandatory argument was not propagated to the characterization test harness. The overlay pass also still reaches data explicitly excluded from the normal validation path.

## Actionable items

### 1. Do not infer overlay ownership from the requested architecture

`projects/hipblaslt/tensilelite/Tensile/TensileLogic/ValidCorpusConsistency.py:319-322`

`overlay_required` is derived solely from whether `gfx1250v0` appears in `archs`. That assumption is false for the shared hipSPARSELt code-generation path: its gfx125X CI build invokes TensileLogic with `--architecture gfx1250v0` against the hipSPARSELt corpus, which intentionally has no `gfx1250v0` directory. The resulting hard failure is already present in CI: `gfx1250v0 overlay required ... but missing ...`, and it stops the hipSPARSELt build before the library artifacts are made.

Keep the missing-overlay requirement for the hipBLASLt corpus that owns the split, but make it an explicit caller policy rather than an implication of the architecture spelling. For example, have the hipBLASLt device-library CMake path opt in to a dedicated overlay-required argument, while the shared hipSPARSELt invocation continues to validate an existing overlay if one is present without requiring one. Add a regression test for a `gfx1250v0` request against a no-split corpus, as well as the required-overlay case.

### 2. Update the characterization `Run.main()` fixture for the new argument

`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/TensileLogic/test_run_char.py:262-270`

`_stub_main()` still creates `SimpleNamespace(KnownBugs=None, Verbose=verbose)`, but `Run.main()` now unconditionally evaluates `args.Architecture.split(";")` whenever these `All=True` tests run. Consequently, the five characterization tests that use this fixture all fail in CI with `AttributeError: 'types.SimpleNamespace' object has no attribute 'Architecture'`; the coverage job stops before the regular unit half runs.

Set `Architecture` in this shared fixture (normally `"all"`) and rerun the characterization and unit coverage halves. The regular unit-test fixtures were updated in this PR, so the characterization fixture needs the same treatment.

### 3. Respect the selected non-experimental file set in the overlay pass

`projects/hipblaslt/tensilelite/Tensile/TensileLogic/ValidCorpusConsistency.py:272-279`

`Run.main()` intentionally removes paths containing `Experimental` before calling `check_corpus_invariants()`, matching `_runChecks()`'s normal exclusion. The sibling finder receives that filtered set, but `find_gfx1250v0_overlay_violations()` ignores it and re-walks `logic_root`. An excluded experimental YAML outside the overlay whose header says `ScheduleName: gfx1250v0` therefore fails an otherwise valid `--check-all` build, contrary to both the `Run.py` comment and this module's selected-file contract.

Pass the selected files to the overlay finder (or otherwise apply the same filter there) for both the overlay contents and the outside-overlay scan. Preserve the directory-exists requirement independently when the explicit hipBLASLt policy requests it. Add the regression case from the appendix.

## Suggestions

### 1. Correct the outdated enforcement comment

`projects/hipblaslt/tensilelite/Tensile/Tests/unit/test_PlaceholderMerge.py:30-37`

This comment says both the sibling check and the chip-ID architecture lock run unconditionally inside `TensileLogic --check-all`. The implementation intentionally removed the chip-ID lock from `check_corpus_invariants()` and leaves it as a corpus-backed pytest check. Update the comment so that the documented enforcement model matches the code and does not imply that installed-artifact builds run the source-policy check.

## Commentary

The selected-file design is the right abstraction for the sibling consistency rule, and its real-corpus result is encouraging. The key remaining distinction is ownership: a generator target can request an architecture while consuming another project's logic corpus. That policy belongs at the CMake-to-validator boundary, not in a generic interpretation of the requested architecture.

### Appendix: experimental-file scope reproducer

The following temporary probe was run and removed. It shows that `check_corpus_invariants()` receives a selected file list without `Experimental`, then reports the excluded file because the overlay finder performs a fresh recursive walk.

```python
import importlib.util
import os
import tempfile
from pathlib import Path


source = (
    Path(os.environ["SRC_DIR"])
    / "projects/hipblaslt/tensilelite/Tensile/TensileLogic/ValidCorpusConsistency.py"
)
spec = importlib.util.spec_from_file_location("vcc_probe", source)
vcc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vcc)


with tempfile.TemporaryDirectory() as td:
    root = Path(td)

    def write(path, schedule, arch="gfx1250"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"- MinimumRequiredVersion: 4.33.0\\n"
            f"- {schedule}\\n"
            f"- {arch}\\n"
            f"- [Device 73f0]\\n"
        )

    write(root / "gfx1250v0" / "Equality" / "ship.yaml", "gfx1250v0")
    write(root / "gfx1250" / "Equality" / "ship.yaml", "gfx1250")
    write(root / "gfx1250" / "Experimental" / "probe.yaml", "gfx1250v0")

    selected = [p for p in root.rglob("*.yaml") if "Experimental" not in p.parts]
    violations = vcc.check_corpus_invariants(root, selected, ["all"])
    assert any("outside the gfx1250v0 overlay" in v for v in violations)
```
