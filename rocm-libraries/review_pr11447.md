> This is a review from an agent with an automatic prompt from the reviewer

# Review: PR #11447 — fold logic-corpus consistency checks into `TensileLogic --check-all`

Date reviewed: 2026-09-01  
PR: https://github.com/ROCm/rocm-libraries/pull/11447  
Commit reviewed: `b2975777f2dfb262a998df04f6905444df17381f` (tip of `<pr-head-ref>`)  
Overall assessment: **Changes requested**

## Tests

Local tests: 30/30 new unit tests and 82/82 affected tests passed; real gfx1250 `TensileLogic --check-all` runs accepted 1,842/1,842 hipBLASLt solutions and 64/64 hipSPARSELt solutions; syntax and diff checks also passed. The new unit tests took 0.13 seconds, so their runtime is negligible.

Three deliberate counterexample tests failed with `AssertionError: [] is not true`. These expose
the PR defects explained in Actionable items 1–3; the exact temporary harness is included in the
appendix.

The PR's public checks show the focused TensileLite coverage job and Math CI checks passing. The
failed Windows multi-architecture job is unrelated to this diff: its log ends in hipSOLVER's
OpenBLAS C test executables failing to link (`cc2chke_`, `link_xerbla`, and related symbols are
undefined). The three project-wide Codecov statuses are also red, although `codecov/patch` and Math
CI's hipBLASLt and hipSPARSELt coverage checks pass.

## Summary

This PR moves three cross-file checks from corpus-dependent pytest tests into the production
`TensileLogic --check-all` path. The new module compares `DeviceNames` among same-basename logic
files, locks chip-ID-aware dispatch to gfx950, and validates metadata in the gfx1250 v0 logic tree.
It runs these checks before the existing per-solution validation and makes any reported violation
terminate the command.

The appropriate minimum level is hermetic Python unit coverage plus a real `TensileLogic
--check-all` invocation for each affected build target. No new feature flag or general corpus
profile is needed. The existing architecture selection already expresses which artifact is being
built, and the existing gfx1250v0 invocation identifies when the v0 overlay is required. The
adjacent paths are the CMake invocation, both consumer corpora, YAML list and mapping formats, and
the `Run.main()` tests on the current target branch.

The approach is sensible, and sharing the production finders with the convenience tests removes
useful duplication. The new tests are focused and fast, and running the checks before
kernel-library generation gives developers an earlier, more useful error than a later merge or
packaging failure. I recommend changes before merge because some inputs still bypass the checks. I
assess the risk as 3/5: no runtime code changes, but this becomes a hard build gate shared by two
projects.

## Actionable items

### 1. Scope the build check to the requested architecture and cover every selected file

`projects/hipblaslt/tensilelite/Tensile/TensileLogic/Run.py:266` and
`projects/hipblaslt/tensilelite/Tensile/TensileLogic/ValidCorpusConsistency.py:77`

`_setup()` has already selected the YAML files for the requested architecture, but `main()`
discards that scope for the new checks and scans `logicPath` again. Consequently, a gfx942-only
build can fail because of unrelated gfx1250 data. There is no dedicated opt-out: avoiding this
behavior requires avoiding `--check-all`, which also disables the existing validation used by the
normal device-library build.

`iter_arch_dirs()` yields only directories shaped as `<root>/<codename>/<gfx*>`. The repositories
also contain supported layouts where the first directory is the architecture or schedule and the
next directory is a category or compute-unit variant. Examples include
`gfx1201/Equality`, `navi31/GridBased`, and `aldebaran/110CU/Equality` in hipBLASLt, plus
`gfx950/Equality` and `gfx1250/Gridbased` in hipSPARSELt.

The consequence is measurable: the walker reaches 1,936 of 2,789 hipBLASLt YAML files and 162 of
355 hipSPARSELt YAML files. Both `find_sibling_device_names_violations()` and
`find_chip_id_arch_lock_violations()` therefore describe themselves as whole-corpus checks while
silently excluding 853 and 193 files respectively. The direct-layout counterexample in the
appendix reproduces the false success.

The simplest fix is to pass the already-selected `files` into the cross-file checks rather than
adding a new profile, mode, or ignore flag. Group those files using their YAML architecture and
relative schedule path instead of assuming one directory depth. `--architecture all` naturally
remains the whole-corpus mode. Add fixtures matching a direct `gfx1201/Equality` tree, a codename
tree such as `navi31/Equality`, and the `aldebaran/<CU-count>/...` shape. Also assert that every
selected YAML belongs to an understood group so a new layout cannot silently reduce coverage.

The chip-ID architecture lock is different: it guards a future source-code policy change rather
than the artifact selected for this build. Keep that as a hermetic unit test over the supported
architecture registry instead of running it during every device-library build.

### 2. Require the hipBLASLt v0 overlay when the build requests it

`projects/hipblaslt/tensilelite/Tensile/TensileLogic/ValidCorpusConsistency.py:201`

The checker reports an empty `gfx1250v0` directory but returns success when that directory is
absent. This avoids rejecting hipSPARSELt, which does not split gfx1250 by silicon revision, but the
function does not receive the architecture already selected by the caller. It therefore also
accepts removal or renaming of hipBLASLt's required overlay. A normal hipBLASLt gfx1250 build
creates both v1 and v0 libraries, and the runtime selects between them from `asicRevision`;
accepting a missing v0 source tree defeats the failure this check is intended to prevent.

No new corpus-profile mechanism is necessary. The existing build already invokes the generator
with architecture `gfx1250v0` precisely when it is producing the v0 library; hipSPARSELt requests
`gfx1250` instead. Run this overlay check only for the existing `gfx1250v0` selection and require
the directory in that case. Add tests proving that absence fails when v0 is requested and remains
irrelevant for other architecture selections. If the PR description's promise to verify that the
two trees mirror each other is intentional, also compare normalized directory/file sets; the
current implementation only requires one v0 YAML.

### 3. Treat valid multiline or missing `DeviceNames` headers consistently

`projects/hipblaslt/tensilelite/Tensile/TensileLogic/ValidCorpusConsistency.py:96` and line 139

`read_device_names()` accepts only a one-line flow list and returns `None` for every other case;
the caller then skips that file. This is another fail-open path in a checker whose purpose is to
stop inconsistent data. The checked-in hipBLASLt corpus already contains 103 valid multiline
headers, such as the aldebaran files whose device list wraps onto the next line. The existing
event-based YAML reader parses those headers successfully, but this regex does not. A mapping-form
file that omits `DeviceNames` is also accepted by normal library parsing as `None`, so a listed
sibling and an omitted sibling can still diverge without a violation.

Use the existing partial YAML parsing helpers to read list index 3 or the mapping key without
loading all solutions. Treat a missing or unreadable header as a violation, or at minimum as a
distinct comparable value instead of dropping the file. Replace
`test_sibling_device_names_skips_a_file_with_no_parseable_device_names` at
`projects/hipblaslt/tensilelite/Tensile/Tests/unit/test_valid_corpus_consistency.py:314` with
fail-closed cases for a missing key and a valid multiline list.

### 4. Rebase and update the new `Run.main()` test from `develop`

`projects/hipblaslt/tensilelite/Tensile/TensileLogic/Run.py:270` and
`projects/hipblaslt/tensilelite/Tensile/Tests/unit/test_TensileLogic_Run.py:329` on current
`develop`

The branch has fallen behind the current target, and both files above changed after its merge
base. A three-way merge still has no textual conflict, but current `develop` adds
`test_main_loads_bundled_known_bugs_only_when_requested()`. That test mocks `_setup()` with a
directory containing `logic.yaml` whose contents are `dummy`; unlike the older `TestMain` cases
updated by this PR, it does not mock `check_corpus_invariants()`. The merged `main()` calls the new
checker first, `load_logic_schedule_name()` rejects the scalar YAML as neither a sequence nor a
mapping, and the test errors before exercising bundled known-bug loading.

Rebase onto current `develop`, update the new test to use valid minimal logic or isolate the corpus
checker, and rerun the focused `test_TensileLogic_Run.py` and corpus-consistency suites on the
rebased result. The target branch also converted additional gfx950 YAMLs to mapping form after this
PR diverged, so the real-corpus invocation must be repeated after the rebase.

## Suggestions

### 1. Make the aggregate test exercise all three finders

`projects/hipblaslt/tensilelite/Tensile/Tests/unit/test_valid_corpus_consistency.py:441`

The test says it plants one violation from each finder, but it creates and asserts only sibling and
overlay violations. Deleting the `find_chip_id_arch_lock_violations()` expansion at production line
249 would leave the suite green. Monkeypatch the predicate for one discovered architecture and
assert that all three diagnostic classes are present.

### 2. Replace the PR description after the correctness fixes

The current description fails the prose gate because two central claims are not true of the diff:
the code does not scan the whole corpus, and it does not verify that the gfx1250v0 tree mirrors the
gfx1250 tree. It also repeats development history that obscures the current behavior. After fixing
the items above, the following is a paste-ready replacement; update the pending result counts after
the rebase.

```markdown
ISSUE ID : #11397

## Motivation

`TensileLogic --check-all` validates each library-logic YAML file before device-library
generation. Three relationships span multiple files or directories, so per-file validation cannot
enforce them. The existing pytest checks may also skip when source logic files are absent from an
installed test artifact, which allowed inconsistent logic data to merge without a failing build.

## Technical Details

- Add a cross-file pass that compares `DeviceNames` among same-basename logic files selected by
  the existing `--architecture` option.
- Keep the gfx950-only chip-ID rule as a hermetic source-policy test rather than making every
  device-library build re-check unrelated architectures.
- Require and validate the gfx1250v0 tree when the existing build path requests architecture
  `gfx1250v0`; other architecture selections do not run that check.
- Resolve a `library/` input to its nested `Logic/asm_full` directory and run these checks before
  per-solution validation whenever `--check-all` is selected.
- Reuse the production finders in the corpus-backed pytest tests; the hermetic unit tests build
  small temporary corpora for each accepted layout and failure mode.

## Test Plan

Run the new corpus-consistency unit tests, the affected `TensileLogic` entry-point tests, the two
refactored corpus-backed tests, and `TensileLogic --check-all` against both hipBLASLt and
hipSPARSELt logic roots. Repeat these tests after rebasing onto current `develop`.

## Test Result

Pending after the review findings and rebase are addressed.

## Submission Checklist

- [x] Look over the contributing guidelines at https://github.com/ROCm/ROCm/blob/develop/CONTRIBUTING.md#pull-requests.

## Risk level

Medium (3/5): runtime dispatch and generated kernels do not change, but the new checks are hard
build failures shared by hipBLASLt and hipSPARSELt.
```

## Commentary

The architectural direction is good: cross-file facts that affect the requested artifact belong
in its validation pass, and having the convenience tests call the production finders reduces
drift. The simplest correction is to reuse the existing architecture selection and v0 build
invocation. A general profile system or new family of bypass flags would add more complexity than
this change needs.

No GPU execution is required for this change. The strongest validation is a fresh source build for
both consumers because that proves the CMake entry point supplies the intended corpus and policy;
the hermetic unit tests should provide the faster regression signal for every boundary case.

### Appendix: exact temporary test harness

The harness below was saved as `$BUILD_DIR/probe.py` for the two commands in the Tests section and
removed after use.

```python
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


repo = Path(os.environ["SRC_DIR"])
tensile_src = repo / "projects/hipblaslt/tensilelite/Tensile"

tensile = types.ModuleType("Tensile")
tensile.__path__ = [str(tensile_src)]
common = types.ModuleType("Tensile.Common")
common.__path__ = [str(tensile_src / "Common")]
architectures = types.ModuleType("Tensile.Common.Architectures")
architectures.supportsChipIdPredicate = lambda gfx: gfx == "gfx950"
sys.modules.update(
    {
        "Tensile": tensile,
        "Tensile.Common": common,
        "Tensile.Common.Architectures": architectures,
    }
)

loader_spec = importlib.util.spec_from_file_location(
    "Tensile.CustomYamlLoader", tensile_src / "CustomYamlLoader.py"
)
loader = importlib.util.module_from_spec(loader_spec)
sys.modules[loader_spec.name] = loader
loader_spec.loader.exec_module(loader)

vcc_spec = importlib.util.spec_from_file_location(
    "Tensile.TensileLogic.ValidCorpusConsistency",
    tensile_src / "TensileLogic/ValidCorpusConsistency.py",
)
vcc = importlib.util.module_from_spec(vcc_spec)
sys.modules[vcc_spec.name] = vcc
vcc_spec.loader.exec_module(vcc)


def write_header(path, schedule="schedule", gfx="gfx1201", devices=("- [Device 1111]",)):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["- MinimumRequiredVersion: 4.33.0", f"- {schedule}", f"- {gfx}"]
    lines.extend(devices)
    path.write_text("\n".join(lines) + "\n")


class CheckedInCorpora(unittest.TestCase):
    def test_hipblaslt(self):
        root = repo / "projects/hipblaslt/library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full"
        self.assertEqual(vcc.check_corpus_invariants(root), [])

    def test_hipsparselt(self):
        root = repo / "projects/hipsparselt/library/src/hcc_detail/rocsparselt/src/spmm/Tensile/Logic/asm_full"
        self.assertEqual(vcc.check_corpus_invariants(root), [])


class Counterexamples(unittest.TestCase):
    def test_direct_arch_layout_is_checked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_header(root / "gfx1201/Equality/logic.yaml", devices=["- [Device 1111]"])
            write_header(root / "gfx1201/GridBased/logic.yaml", devices=["- [Device 2222]"])
            self.assertTrue(vcc.find_sibling_device_names_violations(root))

    def test_multiline_device_names_are_checked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_header(root / "codename/gfx1201/Equality/logic.yaml", devices=["- [Device 1111]"])
            write_header(
                root / "codename/gfx1201/GridBased/logic.yaml",
                devices=["- [Device 2222, Device", "    3333]"],
            )
            self.assertTrue(vcc.find_sibling_device_names_violations(root))

    def test_hipblaslt_overlay_cannot_disappear_silently(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full"
            write_header(
                root / "gfx1250/gfx1250/Equality/logic.yaml",
                schedule="gfx1250",
                gfx="gfx1250",
                devices=["- [Device 73f0]"],
            )
            self.assertTrue(vcc.find_gfx1250v0_overlay_violations(root))


if __name__ == "__main__":
    unittest.main(verbosity=2)
```
