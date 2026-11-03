> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14891](https://github.com/ROCm/rocm-libraries/pull/14891)

**Reviewed head:** `82fd6cc5bcd` (merge base with `develop`: `3efc824f672`)

**Suggestion branch:** [`review/pr14891-suggestions`](https://github.com/newling/rocm-libraries/tree/review/pr14891-suggestions), based on `82fd6cc5bcd`

| Commit | Item |
| --- | --- |
| [`e63ebcfc4dc`](https://github.com/newling/rocm-libraries/commit/e63ebcfc4dc59eab7e11db538eb43696fa5f4159) | 1. The `--changed-files` scoping has no direct tests |
| [`fdf122dcd05`](https://github.com/newling/rocm-libraries/commit/fdf122dcd05ccf214c2a4ef90e3d568f6045192e) | 2. The Range sibling check does not compare `PerfMetric` |
| [`3e3e626627b`](https://github.com/newling/rocm-libraries/commit/3e3e626627bbaf4aa7928ae2e7746d4f8c6e3afe) | 3. The lane's timeout leaves little room over a whole-corpus run |

The commits are independent and can be cherry-picked separately.

## Tests

On the PR head, the six touched or adjacent unit modules (`test_valid_corpus_consistency`, `test_PlaceholderMerge`, `test_no_logic_corpus_paths`, `test_custom_kernel_staggeru_metadata`, `test_solution_uid_uniqueness`, `test_CustomKernelMetadata`) pass (791 passed, `needs_logic_corpus: 3 ran, 0 skipped`). `tox -e logic-corpus` scoped to one gfx1151 file passes (gfx1151 only, 0 rejected). On the suggestion branch the same modules plus the new script tests pass (806), and the scoped `tox -e logic-corpus` run passes, including its new step.

- With an older ROCm 7.1 assembler, `test_custom_kernel_staggeru_metadata.py` fails broadly (`operands are not valid for this GPU or mode`, `unknown directive .amdhsa_exception_fp_*`). This comes from the local toolchain being older than the shipped custom kernels, not from the PR, and all of those tests pass with a current ROCm SDK. The counts above use the current SDK.
- Corpus-absent behavior checked by pointing `HIPBLASLT_LOGIC_ROOT` at a missing directory: `-m needs_logic_corpus` reports `0 ran, 3 skipped` with the hint, and with `HIPBLASLT_REQUIRE_LOGIC_CORPUS=1` all three fail (two failures, one setup error).
- #14281's regression reproduced: with that change's `gfx950_Cijk_Alik_Bljk_BBS_BH_UserArgs.yaml` Equality file beside the shipped Range file, the serialized `ProblemType`s differ by 14 explicit default keys, and `find_range_sibling_violations` reports nothing, as intended.
- The whole-corpus Range sibling and corpus-invariant checks over the 3309 non-Experimental shipped files are clean on the suggestion branch and take under a second.
- Not run locally: the whole-corpus `TensileLogic --check-all`. This PR's own CI run of the new lane did the full sweep and passed (705,190 solutions, 0 rejected, 46 minutes total).
- CI: three of the four required checks pass (`Component CI Summary`, `Math CI Summary`, `pre-commit`). `Multi-Arch CI Summary` fails on `FFM gfx1250 / tensilelite` and a Windows rocFFT test, and two hipBLASLt C++ codecov statuses are also red. This PR changes no C++ or rocFFT code. The FFM failure was not triaged.

## Summary

The PR moves each check that used to read the shipped logic corpus from inside a unit test to where the corpus actually is. The cross-file fact that broke after #14281, that a Range file shares its Equality sibling's placeholder, becomes `find_range_sibling_violations` in `TensileLogic --check-all`. It compares the *effective* `ProblemType`, so writing defaults out explicitly no longer looks like a divergence. The StaggerU code-generation test now reads byte-identical fixture copies. The chip-ID arch lock walks `SUPPORTED_GFX`, so it runs everywhere. The three tests that still need the corpus go through one resolver, carry a marker, and are counted in every session summary. A source-scanning guard keeps new tests from building their own corpus path. On the CI side, the old SolutionUID-uniqueness lane becomes a logic-corpus lane that runs `--check-all --strict-known-bugs` on every architecture a PR's logic touches, which closes the gap that let a logic-only PR merge with no TensileLite check at all.

Several choices are worth keeping. A file that is renamed away fails instead of skipping (`require_logic_file`). The `needs_logic_corpus: N ran, M skipped` line makes a lane without the corpus visible. A deleted logic file is resolved through its directory, and a missing directory widens the check to everything. Strict known-bugs mode only counts entries for solutions it actually visited, so architecture scoping cannot produce false "stale entry" failures. The tests that still read the corpus now run, with the corpus required, in the lane that triggers when the corpus changes.

## Actionable items

### 1. The `--changed-files` scoping has no direct tests

`projects/hipblaslt/scripts/run_tensile_logic_check.py:133` (`_changed_architectures`) and `:183` decide which architectures the new lane validates. A non-empty change list that resolves to no architectures prints "nothing to check" and exits 0. So a regression in path resolution, the validator list, or deleted-file handling would make the merge-gating lane pass without checking anything, which is the failure this PR exists to prevent. The PR description lists manual negative checks, but nothing in the tree pins this contract, and a change to the script alone triggers only the logic-corpus lane, whose pytest step selects `-m needs_logic_corpus` (`tensilelite/tox.ini:136`) and so would not run such tests anyway.

Implemented in [`e63ebcfc4dc`](https://github.com/newling/rocm-libraries/commit/e63ebcfc4dc59eab7e11db538eb43696fa5f4159). It adds `Tests/unit/test_run_tensile_logic_check.py`, which loads the script the same way `test_analyze_timing.py` loads its script, and skips when `scripts/` is absent, as in the installed-artifact layout. Logic-file cases use a synthetic tree under `tmp_path`. The tests cover declared architectures across two trees, absolute paths, a deleted file resolved through its directory, a deleted directory widening the check to everything, unrelated paths selecting nothing, each validator path (`TensileLogic/` sources, `known_bugs.yaml`, `CustomYamlLoader.py`, the script) widening the check to everything, and the three `--changed-files` argument forms. `tox -e logic-corpus` now runs this file before the check, so a script-only change exercises it.

### 2. The Range sibling check does not compare `PerfMetric`

`projects/hipblaslt/tensilelite/tensilelite/TensileLogic/ValidCorpusConsistency.py:220` (`_placeholder_identity`) compares the header, `DeviceNames` and effective `ProblemType`, and the docstring at `:246` says those decide the placeholder. `MasterSolutionLibrary.FromOriginalState` also appends any `PerfMetric` other than `DeviceEfficiency` to the placeholder name (`SolutionLibrary.py:438`). So a Range file and an Equality sibling that differ only in `PerfMetric` load into different placeholders, and the check reports nothing (probe in the appendix: `violations: []`). Every shipped Range file currently uses the default, so this does not fail today, but it is the check's stated contract.

Implemented in [`fdf122dcd05`](https://github.com/newling/rocm-libraries/commit/fdf122dcd05ccf214c2a4ef90e3d568f6045192e). It adds `CustomYamlLoader.load_logic_perf_metric`, which reads list index 10 in the positional dialect or the `PerfMetric` key in the mapping dialect, the same positions `LibraryIO` reads. The identity then compares `PerfMetric or "DeviceEfficiency"`, matching `LibraryIO`'s handling of a missing or empty value. A new parameter of `test_range_sibling_flags_a_different_header` covers a differing metric, and `test_range_sibling_ignores_a_default_perf_metric_written_out` covers an explicit default. The new parameter fails without the source change. The field comes after `Solutions`, so the read parses each compared file in full. The comparison runs only for Range/Equality pairs, and the shipped files involved are 17–46 KB.

### 3. The lane's timeout leaves little room over a whole-corpus run

`.github/workflows/component-ci-logic-corpus.yml:37` sets `timeout-minutes: 60`, and the comment at `:20` says the whole corpus takes about half an hour. This PR's own run took that whole-corpus path and used 46 minutes: about 2 for checkout, 1 for ROCm, 6 for the rocisa build, 35 for `--check-all` and 1.5 for the tests. Every PR that touches a `TensileLogic` source or `known_bugs.yaml` takes that path, as does any `develop` push that does, and the job gates through `Component CI Summary`. Hosted-runner variance or corpus growth of about 30% would turn those into timeout failures that block the merge.

Implemented in [`3e3e626627b`](https://github.com/newling/rocm-libraries/commit/3e3e626627bbaf4aa7928ae2e7746d4f8c6e3afe): `timeout-minutes: 90`, with the runtime note corrected to the measured figures. A longer-term option is to shard the whole-corpus path by architecture with a matrix. That is a larger design choice, so it is not on the branch.

## Suggestions

### `test_skinny_tn_range_logic` still hard-codes shipped header values

`projects/hipblaslt/tensilelite/tensilelite/Tests/unit/test_CustomKernelMetadata.py:1490` defines `_GFX950_HEADER` with `CUCount: 256` and `DeviceNames: ["Device 75a0"]`, and `:1556` requires both Range files to match it exactly. For the BF16 file, the new `--check-all` rule already requires agreement with the Equality sibling. If tuning legitimately adds a device to that pair, the corpus passes the gate but this test fails over a value it copied from the corpus. That is the brittleness the PR removes elsewhere. Consider asserting only `ArchitectureName` here, which is the single-file fact the custom kernels need, and leaving cross-file agreement to the gate. Not implemented: the FP16 file has no Equality sibling, so whether its `DeviceNames` should be pinned is the feature owner's call.

### The identity is stricter than the placeholder name

`_placeholder_identity` also compares `ScheduleName`, which the placeholder name never includes, and every effective `ProblemType` field, not only those `placeholderStr` and the selection level read. This is clean on today's corpus, and stricter is a defensible policy for Range/Equality siblings. If it is intended, the docstring at `ValidCorpusConsistency.py:246` should say these fields must match, not that they decide the placeholder, so the next reader does not take the list as a description of `SolutionLibrary`.

## Commentary

The "validator" set that widens the check to the whole corpus (`TensileLogic/`, `CustomYamlLoader.py`, the script) is narrower than what `--check-all` depends on. Solution validation in `SolutionStructs`, ProblemType defaults (which the new Range check now uses), `Common/Architectures` and rocisa capabilities all change the outcome, but changing them triggers only the TensileLite coverage lane, which does not run `--check-all`. The build-wired gate still covers the architectures PR builds target, so the exposure is the same set the PR description names (gfx1151, gfx90a, gfx120X and others), now on the code side instead of the data side. Widening the trigger to all of `tensilelite/**` would put a 46-minute job on every TensileLite PR. A cheaper middle ground would be a scoped sweep of one representative file per architecture on those changes.

A `known_bugs.yaml` change also sends the lane down the whole-corpus path. Its entries are keyed by logic-relative path, so the affected architectures can be derived from the changed entries, the same way the changed logic files are handled. Whether that is worth the extra code depends on how often tuning PRs edit the list.

The checkout uses `fetch-depth: 2` and diffs `HEAD^..HEAD`. That matches `component_ci.py` and is right for `pull_request` merge refs and squash-merged `develop` pushes. A multi-commit fast-forward push to a `release/therock-*` branch would only see its last commit. Component CI has the same limitation, so this lane inherits it rather than introducing it.

## Appendix: `PerfMetric` probe

Run from `projects/hipblaslt/tensilelite` with that directory on `PYTHONPATH` and rocisa installed. On the PR head it prints `violations: []` and exits 1; with `fdf122dcd05` it reports the `PerfMetric` divergence and exits 0.

```python
import sys
import tempfile
from pathlib import Path

import yaml

from tensilelite.TensileLogic import ValidCorpusConsistency as vcc

PT = {
    "OperationType": "GEMM", "DataType": "b", "DestDataType": "b",
    "ComputeDataType": "s", "HighPrecisionAccumulate": True,
    "TransposeA": True, "TransposeB": False, "UseBeta": True, "Batched": True,
}


def write(path, libraryType, perfMetric=None):
    doc = {
        "MinimumRequiredVersion": "5.0.0", "ScheduleName": "gfx950",
        "ArchitectureName": "gfx950", "CUCount": 256,
        "DeviceNames": ["Device 75a0"], "ProblemType": PT, "Solutions": [],
        "LibraryType": libraryType,
    }
    if perfMetric is not None:
        doc["PerfMetric"] = perfMetric
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


root = Path(tempfile.mkdtemp())
name = "gfx950_Cijk_Alik_Bljk_BBS_BH_UserArgs.yaml"
files = [
    write(root / "gfx950/gfx950/Range" / name, "Range"),
    write(root / "gfx950/gfx950/Equality" / name, "Equality", perfMetric="CUEfficiency"),
]
violations = vcc.find_range_sibling_violations(files, root)
print("violations:", violations)
sys.exit(0 if violations else 1)
```

## Branch handoff

[`review/pr14891-suggestions`](https://github.com/newling/rocm-libraries/tree/review/pr14891-suggestions) is based on `82fd6cc5bcd` and holds `e63ebcfc4dc` (item 1), `fdf122dcd05` (item 2) and `3e3e626627b` (item 3). Validation for each is listed under Tests. Both suggestions and the commentary are not implemented, for the reasons given in each. The branch is published on a fork; no comment or change has been made on the PR itself.
