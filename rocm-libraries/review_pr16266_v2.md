This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#16266](https://github.com/ROCm/rocm-libraries/pull/16266)

**Reviewed head:** `dac39a22e107e0108cdd89a1d4a99aaca6ab0ede`

**Stack base:** `18c504ac1736f0925b42c512560f99ac0ed7a5e0` ([#16265](https://github.com/ROCm/rocm-libraries/pull/16265))

**Mode and scope:** Full independent review of all 11 changed files, with the requested review of previous comments: component selection and its test, four workflows, the TheRock skip configuration, the lane driver, and three documentation files. The prerequisite's build, loader, and tests were inspected where the lanes consume them. All 13 review submissions, nine inline threads containing 18 comments, and three issue comments were considered. The head, base, and discussion were unchanged at the final refresh.

**Suggestion branch:** [review/pr16266-suggestions-20261120](https://github.com/newling/rocm-libraries/tree/review/pr16266-suggestions-20261120), based on the reviewed head. Four commits implement the bounded changes below; the TheRock part of actionable item 2 remains unimplemented. [Suggested changes](https://github.com/newling/rocm-libraries/compare/dac39a22e107e0108cdd89a1d4a99aaca6ab0ede...7ccfb7498b334ed18d3f89147f1ecaeb897c58f4).

## Tests

The submitted bindings built with Clang 23.1.0 and Python 3.12 against hipBLASLt 1.4.1 from the available ROCm SDK `10.1.0a20260812`. The submitted and suggested CPU suites each passed **72 tests**, with three expected skips: the device test and two alternate-installation tests. The device was hidden for these local runs.

Eight component-path unit tests, 23 checks of the actual selector and workflow planning/filtering scripts, and 20 lane-driver checks covering success and failures in venv creation, ROCm installation, build, and test passed on the suggestion branch. Both actionable failures were reproduced on the submitted code. The safe appendix reproducers were run against both revisions. Root pre-commit, Bash syntax, diff whitespace, and Actionlint 1.7.12 passed after the final change. Actionlint used the existing custom runner label; its optional ShellCheck and pyflakes integrations were unavailable.

The reviewed head's [Component CI run](https://github.com/ROCm/rocm-libraries/actions/runs/44830932729) passed all five bindings lanes against pinned SDK `10.3.0a20261116`:

| Lane | Result | Job log |
| --- | --- | --- |
| Linux CPU | 72 passed, 3 skipped | [136615844451](https://github.com/ROCm/rocm-libraries/actions/runs/44830932729/job/136615844451) |
| Linux gfx942 | 73 passed, 2 skipped | [136615844468](https://github.com/ROCm/rocm-libraries/actions/runs/44830932729/job/136615844468) |
| Linux gfx950 | 73 passed, 2 skipped | [136615844531](https://github.com/ROCm/rocm-libraries/actions/runs/44830932729/job/136615844531) |
| Windows CPU | 66 passed, 9 skipped | [136615844674](https://github.com/ROCm/rocm-libraries/actions/runs/44830932729/job/136615844674) |
| Windows gfx1151 | 67 passed, 8 skipped | [136615844446](https://github.com/ROCm/rocm-libraries/actions/runs/44830932729/job/136615844446) |

The device test executed on all three GPU lanes, and their cleanup steps succeeded. The tested merge commit `8d92a5d0a86b13e79db7c47c338a9a8c4a238785` has the same tree as the reviewed head. Historical binding jobs were also inspected: the two failed GPU jobs were intentional no-device controls, with the corrected fixture reporting `HIPBLASLT_PY_REQUIRE_GPU=1, but no HIP device is visible`.

The suggestion branch has not run on hosted Windows or physical GPUs, and the complete pinned wheel-download driver was not rerun locally. Other Component CI jobs remained queued at the CI snapshot; Math CI and Multi-Arch summaries were deliberate skips under the PR's skip labels. These results establish bindings-lane coverage, not completion of all repository CI.

## Summary

The lanes test the bindings as an installed package against a deliberately pinned ROCm build. Sparse checkout and a hosted CPU runner keep that check small. The matrix refactor preserves the distinct Linux container and Windows environments while making download, build, pytest, and cleanup failures visible as separate steps. Required-device mode prevents a GPU lane from silently becoming a CPU-only check.

Ordinary mixed changes retain the existing heavy CI, and the new lanes remain outside the required Component CI Summary during qualification. Those choices fit the documented rollout.

## Actionable items

### 1. Resolve relative work directories before test and cleanup

**Location:** [ci_lane.sh:37–51](https://github.com/ROCm/rocm-libraries/blob/dac39a22e107e0108cdd89a1d4a99aaca6ab0ede/projects/hipblaslt/python/scripts/ci_lane.sh#L37), [test and cleanup:99–108](https://github.com/ROCm/rocm-libraries/blob/dac39a22e107e0108cdd89a1d4a99aaca6ab0ede/projects/hipblaslt/python/scripts/ci_lane.sh#L99).

`HIPBLASLT_PY_WORK_DIR` accepts a relative directory, but `venv` retains that relative path after `step_test` enters it. With a prepared venv and `HIPBLASLT_PY_WORK_DIR=tmp`, the test step exits 127 looking for `tmp/venv/Scripts/python.exe` beneath the directory it just entered.

Cleanup has a more serious consequence: both `step_clean` and the all-in-one EXIT trap change to `/` before using the relative path. The same override therefore targets **`/tmp`**, rather than the caller's `tmp` directory. This was verified with a stand-in for `rm`; no unrelated directory was removed. The default hosted lanes use an absolute `RUNNER_TEMP`, so the observed hosted successes do not exercise this case.

Normalize a relative work directory against the invocation directory, after Windows path conversion and before deriving `venv`. Commit [1967902c5756](https://github.com/newling/rocm-libraries/commit/1967902c5756d1601dd53104c913952c464d4121) does that. The test then reaches pytest, and cleanup receives the intended absolute path. Absolute and relative paths, spaces, whole-lane execution, separate steps, and failure cleanup were checked.

### 2. Preserve rename source paths before applying the Python exclusions

**Locations:** [gfx1250 gate:99–103](https://github.com/ROCm/rocm-libraries/blob/dac39a22e107e0108cdd89a1d4a99aaca6ab0ede/.github/workflows/gfx1250_hipblaslt_tensilelite_test.yml#L99), [skip-ci-config.toml:59–60](https://github.com/ROCm/rocm-libraries/blob/dac39a22e107e0108cdd89a1d4a99aaca6ab0ede/.github/skip-ci-config.toml#L59).

The new exclusions can classify a library-source removal as a bindings-only change. For example, the PR-files API reports a move from `projects/hipblaslt/library/src/amd_detail/hipblaslt.cpp` to `projects/hipblaslt/python/csrc/hipblaslt.cpp` as one renamed entry, with the old path in `previous_filename`. Readers that retain only `filename` lose the library change.

Executing the gfx1250 gate with that API response gives `run=true` before this PR's exclusion and `run=false` on the submitted head. The binding tests use an installed library, so they cannot replace the skipped test of the library source. Commit [7ccfb7498b33](https://github.com/newling/rocm-libraries/commit/7ccfb7498b334ed18d3f89147f1ecaeb897c58f4) retains `filename` and `previous_filename` in the existing jq query; the same gate then returns `run=true`. The ordinary Python-only and mixed-edit cases still behave as intended.

The global TheRock exemption has the same failure through its consumer. The pinned revision `11621df52cb7e5790ab7a37515098cde8faed4ab` discards the old path in both the [PR-files reader](https://github.com/ROCm/TheRock/blob/11621df52cb7e5790ab7a37515098cde8faed4ab/build_tools/github_actions/configure_ci_path_filters.py#L597) and [compare reader](https://github.com/ROCm/TheRock/blob/11621df52cb7e5790ab7a37515098cde8faed4ab/build_tools/github_actions/configure_ci_path_filters.py#L524). Executing those readers and the real skip predicate with the API boundary mocked changes the decision from “run” to “skip” when this PR's `projects/hipblaslt/python/*` pattern is added. Preserving both paths restores “run.” The newer develop pin, `ddecad3a9050c0ed1136de8b68af1781307bd1c4`, reproduces the same failure.

**The TheRock portion remains open.** Fix its affected path readers and consume a corrected pin, or defer the new global Python exemption until that dependency is available. The suggestion branch does not modify TheRock or remove the intended exemption. This finding establishes the gfx1250 and TheRock failures; it does not assume that GitHub's native ASAN path filter has identical rename semantics.

## Suggestions

### Describe the status coverage present in this stack position

**Locations:** [DESIGN.md:73](https://github.com/ROCm/rocm-libraries/blob/dac39a22e107e0108cdd89a1d4a99aaca6ab0ede/projects/hipblaslt/python/DESIGN.md#L73), [TESTING.md:1922](https://github.com/ROCm/rocm-libraries/blob/dac39a22e107e0108cdd89a1d4a99aaca6ab0ede/projects/hipblaslt/TESTING.md#L1922), and the matching selector/checkout comments.

The current suite reads the checkout's `hipblasStatus_t` values. Adding an unmapped status to that header produces the expected one failure and 15 passes. Adding a value to `hipblasLtEpilogue_t` leaves the full suite at 72 passes and three skips: the broader enum checks arrive in companion [#16269](https://github.com/ROCm/rocm-libraries/pull/16269). The documentation currently attributes both checks to this PR. Commit [f961ac04cbc8](https://github.com/newling/rocm-libraries/commit/f961ac04cbc85dd7884fc7828119e7192f33cc75) narrows those claims to status coverage without pulling the companion implementation into scope.

### Disable unused checkout credentials

**Location:** The three [checkout steps in component-ci-hipblaslt-python.yml](https://github.com/ROCm/rocm-libraries/blob/dac39a22e107e0108cdd89a1d4a99aaca6ab0ede/.github/workflows/component-ci-hipblaslt-python.yml#L97).

No later step needs authenticated Git operations. Commit [3141b91d2a35](https://github.com/newling/rocm-libraries/commit/3141b91d2a35ad638dea5271c387907838df94e5) sets `persist-credentials: false` on those checkouts, following the TheRock style guide's [“Disable checkout credential persistence” section](https://github.com/ROCm/TheRock/blob/main/docs/development/style_guides/github_actions_style_guide.md#security---disable-checkout-credential-persistence).

## Scope decisions

The installed-nightly strategy remains intentional. Source-status checks catch new status values promptly; other declaration or library-behavior changes require a newer installed library and a pin update. This review does not replace that strategy with an in-tree library build or add the later enum/torch functionality.

The existing request to move the gfx1250 gate into Python explicitly permits a follow-up. The rename correction fits in its current query and does not require that refactor. The resource-capacity discussion remains an author/DevOps coordination question: the author supplied an estimate, but no DevOps acknowledgement was present.

The upstream-overlap check against develop `be0f4f6e28a390dd9fd12a52abfc1a6cc5a1b147` found direct overlap only in `TESTING.md`. The newer TheRock pin was also checked as an indirect dependency, as noted in item 2. The suggestion branch stays on the reviewed stack head.

The testing-document cross-read covered hipBLASLt and TensileLite. Other components' suites were not rerun: the additions leave their existing Component CI inputs and selection behavior intact. No library or kernel implementation changes justify a numerical or performance sweep for this PR.

## Commentary

Previous requests were checked against the current code and execution evidence, independently of thread resolution. Three inline threads are marked resolved; six remain open.

| Previous request | Disposition at the reviewed head |
| --- | --- |
| [Use a small CPU runner](https://github.com/ROCm/rocm-libraries/pull/16266#discussion_r4621043141) | Implemented: Linux CPU uses `ubuntu-24.04`; the unused production-runner input is removed. |
| [Keep the qualification period informational](https://github.com/ROCm/rocm-libraries/pull/16266#discussion_r4621043189) | Implemented: bindings are omitted from Component CI Summary until the documented 20 green Linux runs. Individual lanes still report failures. |
| [Remove temporary SDK installations](https://github.com/ROCm/rocm-libraries/pull/16266#discussion_r4621899212) | Implemented for the normal absolute CI directory: an always-run clean step and the local all-in-one EXIT trap. The subsequently added relative override needs actionable item 1. |
| [Read the PR's source status header](https://github.com/ROCm/rocm-libraries/pull/16266#pullrequestreview-5967885046), with the [author's explanation](https://github.com/ROCm/rocm-libraries/pull/16266#issuecomment-7025751360) | Verified fixed in the prerequisite: the test automatically finds the checkout header, and numeric mapping permits a status absent from the nightly. The original unmapped-status probe now fails as intended. |
| [Consolidate repeated lanes into matrices](https://github.com/ROCm/rocm-libraries/pull/16266#discussion_r4636490127) | Implemented for Linux GPU and Windows lanes; Linux CPU keeps its distinct container setup. |
| [Coordinate GPU-pool capacity](https://github.com/ROCm/rocm-libraries/pull/16266#discussion_r4636497056) | Author supplied 19 merged header PRs/month and about 2.5 minutes per lane as the estimate's basis. No DevOps acknowledgement observed; acceptance is not inferred. |
| [Limit scarce gfx950 use](https://github.com/ROCm/rocm-libraries/pull/16266#discussion_r4636500902) | Verified: selected by the exact `ci:run-gfx950` label, lane-definition changes, or manual dispatch. A similar label does not select it. |
| [Move gfx1250 gate logic to Python](https://github.com/ROCm/rocm-libraries/pull/16266#discussion_r4636509678) | Explicitly deferred in the existing discussion; that decision is preserved. |
| [Split download/build/test into steps](https://github.com/ROCm/rocm-libraries/pull/16266#discussion_r4636514962), including [pytest separately](https://github.com/ROCm/rocm-libraries/pull/16266#discussion_r4636515997) | Implemented: venv, ROCm, build, test, and always-run cleanup have separate workflow steps. |

The remaining two issue comments are policy-bot status reports with no additional requested change. The earlier review's posted file is preserved; this report records the current assessment.

## Appendix: safe work-directory reproducer

Requires Bash and Python 3. Set `SRC_DIR` to a checkout and `REVISION` to the submitted head or a revision containing the suggested fix. No ROCm installation is needed. The script replaces `rm` with a logger; it never executes the lane's deletion command. Python removes only the temporary probe directory it creates.

Submitted result: test exits 127; cleanup logs working directory `/` and argument `tmp`, which would target `/tmp`. Suggested result: test exits 0; cleanup logs the absolute path to the probe's own `tmp` directory.

```bash
python3 - "$SRC_DIR" "$REVISION" <<'PY'
import os
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
revision = sys.argv[2]
lane = subprocess.check_output(
    ["git", "show", revision + ":projects/hipblaslt/python/scripts/ci_lane.sh"],
    cwd=source, text=True,
)
with tempfile.TemporaryDirectory() as temporary:
    parent = Path(temporary)
    script = parent / "scripts/ci_lane.sh"
    script.parent.mkdir()
    script.write_text(lane)
    tools = parent / "tmp/venv/bin"
    tools.mkdir(parents=True)
    replacements = {
        tools / "rocm-sdk": "#!/bin/sh\nprintf '/unused-sdk\\n'\n",
        tools / "python": "#!/bin/sh\nprintf 'pytest command reached\\n'\n",
        parent / "bin/rm": (
            "#!/bin/sh\n"
            "printf 'cleanup cwd=%s\\n' \"$PWD\"\n"
            "printf 'cleanup argument=%s\\n' \"$@\"\n"
        ),
    }
    for path, body in replacements.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        path.chmod(0o755)
    env = dict(os.environ, HIPBLASLT_PY_WORK_DIR="tmp",
               PATH=str(parent / "bin") + os.pathsep + os.environ["PATH"])
    for step in ("test", "clean"):
        result = subprocess.run(
            ["bash", str(script), step], cwd=parent, env=env,
            text=True, capture_output=True, timeout=10,
        )
        print(step, "exit", result.returncode)
        print(result.stdout + result.stderr, end="")
PY
```

## Appendix: rename selection reproducer

Requires Python 3.11+, PyYAML, Bash, jq, and Git. Set `SRC_DIR` and `THEROCK_DIR` to the two repository checkouts; the TheRock checkout must contain commit `11621df52cb7e5790ab7a37515098cde8faed4ab`. Set `REVISION` to the Libraries revision under test. Only the API boundary is replaced; the workflow's Bash/jq and TheRock's reader/predicate execute from their source.

Submitted result: `gfx1250: run=false`; suggested result: `gfx1250: run=true`. Both report TheRock's before/after/both-path decisions as `True False True`, because its reader is not fixed by the local suggestion.

```bash
python3 - "$SRC_DIR" "$THEROCK_DIR" "$REVISION" <<'PY'
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
from unittest.mock import patch

import yaml

source, therock = (Path(p).resolve() for p in sys.argv[1:3])
revision = sys.argv[3]
pin = "11621df52cb7e5790ab7a37515098cde8faed4ab"
old = "projects/hipblaslt/library/src/amd_detail/hipblaslt.cpp"
new = "projects/hipblaslt/python/csrc/hipblaslt.cpp"
payload = [{"status": "renamed", "filename": new, "previous_filename": old}]

def show(repo, ref, path):
    return subprocess.check_output(["git", "show", ref + ":" + path],
                                   cwd=repo, text=True)

workflow = yaml.safe_load(show(source, revision,
    ".github/workflows/gfx1250_hipblaslt_tensilelite_test.yml"))
gate = workflow["jobs"]["gate"]["steps"][0]["run"]
patterns = tomllib.loads(show(source, revision,
    ".github/skip-ci-config.toml"))["skip_ci"]["common"]
with tempfile.TemporaryDirectory() as temporary:
    parent = Path(temporary)
    gh = parent / "gh"
    gh.write_text("#!" + sys.executable + "\n" +
        "import os, subprocess, sys\n"
        "query = sys.argv[sys.argv.index('--jq') + 1]\n"
        "r = subprocess.run(['jq', '-r', query], text=True, "
        "input=os.environ['PROBE_PAYLOAD'])\n"
        "sys.exit(r.returncode)\n")
    gh.chmod(0o755)
    output = parent / "output"
    env = dict(os.environ, PATH=str(parent) + os.pathsep + os.environ["PATH"],
        PROBE_PAYLOAD=json.dumps(payload), GITHUB_OUTPUT=str(output),
        REPO="ROCm/rocm-libraries", PR="1", EVENT="pull_request",
        ACTION="synchronize", LABEL="", DRAFT="false",
        LABELS='["organization: ROCm"]')
    subprocess.run(["bash", "-c", gate], cwd=parent, env=env, check=True)
    print("gfx1250:", output.read_text().strip())

    module = parent / "filters.py"
    module.write_text(show(therock, pin,
        "build_tools/github_actions/configure_ci_path_filters.py"))
    spec = importlib.util.spec_from_file_location("filters", module)
    filters = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(filters)
    with contextlib.redirect_stdout(io.StringIO()):
        with patch.object(filters.subprocess, "run", return_value=
                subprocess.CompletedProcess(["gh"], 0, json.dumps(payload), "")):
            paths = filters.get_changed_files_for_external_repo({
                "repository": "ROCm/rocm-libraries",
                "event_name": "pull_request", "pr_number": 1})
        before = filters.is_ci_run_required(paths, skip_patterns=[
            p for p in patterns if p != "projects/hipblaslt/python/*"])
        after = filters.is_ci_run_required(paths, skip_patterns=patterns)
        both = filters.is_ci_run_required([old, new], skip_patterns=patterns)
    print("TheRock paths:", paths)
    print("CI required before exemption / after / with both paths:",
          before, after, both)
PY
```

The [suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr16266-suggestions-20261120) ends at [7ccfb7498b33](https://github.com/newling/rocm-libraries/commit/7ccfb7498b334ed18d3f89147f1ecaeb897c58f4). Its commit mapping is:

| Commit | Review item |
| --- | --- |
| [1967902c5756](https://github.com/newling/rocm-libraries/commit/1967902c5756d1601dd53104c913952c464d4121) | Actionable 1: resolve work paths |
| [f961ac04cbc8](https://github.com/newling/rocm-libraries/commit/f961ac04cbc85dd7884fc7828119e7192f33cc75) | Suggestion: describe current status coverage |
| [3141b91d2a35](https://github.com/newling/rocm-libraries/commit/3141b91d2a35ad638dea5271c387907838df94e5) | Suggestion: disable unused checkout credentials |
| [7ccfb7498b33](https://github.com/newling/rocm-libraries/commit/7ccfb7498b334ed18d3f89147f1ecaeb897c58f4) | Actionable 2: preserve gfx1250 rename sources |

Local validation is complete. The remaining implementation is the TheRock reader/pin change or deferral of its exemption; hosted Windows/GPU validation of the suggestion branch also remains.
