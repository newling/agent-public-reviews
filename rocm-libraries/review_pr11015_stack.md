This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#11015](https://github.com/ROCm/rocm-libraries/pull/11015), [#11016](https://github.com/ROCm/rocm-libraries/pull/11016), and [#11017](https://github.com/ROCm/rocm-libraries/pull/11017).

Independent review, November 6, 2026. Scope: each PR's own changes and their combined effects on TensileLite imports, wheel contents and dependencies, command dispatch, and hipBLASLt code-generation commands. Existing discussion and review bodies were not used. Approval metadata confirms an approval of #11015 on November 4 at [de0a4ad1bce3628494f4ac7c9f0de4901e6407fe](https://github.com/ROCm/rocm-libraries/commit/de0a4ad1bce3628494f4ac7c9f0de4901e6407fe); the reviewed head differs.

| PR | Change | Reviewed head | Diff base |
| --- | --- | --- | --- |
| #11015 | Lower-case internal module paths | [f4390599b02efaad9131ab040d7bf34f68d60b8a](https://github.com/ROCm/rocm-libraries/commit/f4390599b02efaad9131ab040d7bf34f68d60b8a) | [b84d397c8d533812e0e2dff403c527861e511226](https://github.com/ROCm/rocm-libraries/commit/b84d397c8d533812e0e2dff403c527861e511226) (merge base with develop) |
| #11016 | Wheel packaging and in-process library creation | [106e966b3cfd7bd49d866333b15d12cf7627c577](https://github.com/ROCm/rocm-libraries/commit/106e966b3cfd7bd49d866333b15d12cf7627c577) | #11015's head |
| #11017 | Unified package command and validation filter | [7f57091d08bf0cc5cc631d9bfffa3efc52a4eb5b](https://github.com/ROCm/rocm-libraries/commit/7f57091d08bf0cc5cc631d9bfffa3efc52a4eb5b) | #11016's head |

All three heads were unchanged at the final check. GitHub reported #11015's target-base SHA as [97abc0b1b38fda88b2a95da56d92104021c36ef1](https://github.com/ROCm/rocm-libraries/commit/97abc0b1b38fda88b2a95da56d92104021c36ef1); the table identifies the merge base used to isolate its patch. The suggestion branch is [review/pr11015-11017-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr11015-11017-suggestions), based on #11017's exact head, ending at [911ae84269f1a4f563ac9e82b4ea65d0c8a0b162](https://github.com/newling/rocm-libraries/commit/911ae84269f1a4f563ac9e82b4ea65d0c8a0b162).

## Tests

The submitted combined stack passed 1,242 focused pytest cases, with 16 skips and 70 passing snapshots. This covered command dispatch, architecture splitting, logic validation, client orchestration, experimental-library commands, and packaging. The source archive and wheel built; the wheel built from the archive had the same file list as the directly built wheel, including 260 assembly kernels. All nine installed subcommands displayed help successfully, and all three relocated ext-op generators produced gfx942 assembly from the installed wheel.

The suggestion branch passed the 38 affected CLI and packaging tests. The installed-version regression fails on the submitted implementation and passes with the fix. Disabling CMake's validation-filter forwarding leaves the original source-string test passing but makes the replacement execution test fail. `uv lock --check` fails on the submitted lockfile and passes after regeneration. The applicable root hooks, focused Flake8 checks, and whitespace checks pass on the suggestions.

These were Linux/Python 3.12 checks, using packaged rocisa bindings from an existing CI artifact and ROCm 7.1 for the ext-op assembly generation. No fresh native-library build, GPU execution, Windows validation, or complete benchmark-to-LibraryClient run was performed. The full unit suite was not run, and architecture-dependent cases remain among the skips. Passing orchestration tests do not establish that the new in-process library call preserves every benchmark setting.

CI remained incomplete at the final check. #11017's [policy failure](https://github.com/ROCm/rocm-libraries/actions/runs/42273824491/job/128084911188) reports `pre-commit=cancelled`; its [Multi-Arch summary](https://github.com/ROCm/rocm-libraries/actions/runs/42272069055/job/128079048131) also belongs to a run with cancelled jobs. These results do not establish a source defect, and pending replacement runs are not counted as passing validation.

## Summary

The split makes the large import rename separable from the packaging and command changes. The rename appears consistent across the inspected callers, resource lookups, entry points, and moved ext-op generators; no actionable finding was identified in #11015 itself. Explicit wheel data and argument lists are useful improvements over implicit manifest contents and shell command strings.

The main functional gap is in #11017: exposing an existing helper as a supported command also exposes its obsolete calls. The packaging changes otherwise need the lockfile and reported version brought into agreement, plus corrections to two tests that currently verify weaker substitutes for the shipped behavior.

## Actionable items

### Make the new summation command complete a nonempty input

**#11017**, [GenerateSummations.py:208](https://github.com/ROCm/rocm-libraries/blob/7f57091d08bf0cc5cc631d9bfffa3efc52a4eb5b/projects/hipblaslt/tensilelite/tensilelite/GenerateSummations.py#L208), reaching [line 117](https://github.com/ROCm/rocm-libraries/blob/7f57091d08bf0cc5cc631d9bfffa3efc52a4eb5b/projects/hipblaslt/tensilelite/tensilelite/GenerateSummations.py#L117) and [line 61](https://github.com/ROCm/rocm-libraries/blob/7f57091d08bf0cc5cc631d9bfffa3efc52a4eb5b/projects/hipblaslt/tensilelite/tensilelite/GenerateSummations.py#L61).

`tensilelite generate-summations` reaches `parseLibraryLogicFile(logicFileName, cxxCompiler, isaInfoMap)` for the first matching input. The current reader requires seven arguments, so this raises `TypeError` before reading the file. Independently, `createLibraryForBenchmark` supplies `--new-client-only` and `--no-short-file-names`, which the current create-library parser rejects. The next raw-logic call also passes a filename where `rawLibraryLogic` expects decoded YAML data.

These obsolete calls predate the new CLI, but #11017 now advertises the workflow as supported. The new tests exercise help and mocked dispatch, so they all pass despite the command being unable to process a matching file. The appendix reproduces the first two failures without GPU execution.

Update the workflow's calls to the current interfaces and add a test that takes nonempty logic through model generation. **No fix commit:** this requires a coherent repair and validation of the downstream benchmark/model pipeline. Fixing only the first exception would leave the advertised command broken.

### Regenerate the dependency lock from the final package metadata

**#11016**, [uv.lock:833](https://github.com/ROCm/rocm-libraries/blob/106e966b3cfd7bd49d866333b15d12cf7627c577/projects/hipblaslt/tensilelite/uv.lock#L833).

The edited lockfile still lists `rocisa` as a runtime dependency, omits required `pandas`, and omits the `profile` and `hip-query` extras. Those entries disagree with `setup.py` and `pyproject.toml`. With `ROCM_VERSION=7.2.4`, `uv lock --check` exits 1 with “The lockfile at `uv.lock` needs to be updated.” Frozen consumers would also use the stale dependency graph.

**Implemented in [351267e8321](https://github.com/newling/rocm-libraries/commit/351267e8321398bb7dd681dc50d6679f196f359b):** regenerate the lock from the final metadata. This adds pandas and its dependencies, records the extras, keeps rocisa in the development group, and removes unused runtime packages. The checked-lock command then passes.

### Report the installed wheel's ROCm-qualified version

**#11017**, [cli.py:104](https://github.com/ROCm/rocm-libraries/blob/7f57091d08bf0cc5cc631d9bfffa3efc52a4eb5b/projects/hipblaslt/tensilelite/tensilelite/cli.py#L104).

The wheel metadata reports `5.0.0+rocm7.2.4`, but `python -m tensilelite --version` prints the source constant `5.0.0`. The command therefore hides the ROCm release that #11016 adds to identify installed builds. The existing test replaces that source constant with a qualified string, so it does not test the real relationship between wheel metadata and command output.

**Implemented in [6fb4d906885](https://github.com/newling/rocm-libraries/commit/6fb4d906885daf916e49a406a82e673c1670145c):** read the installed distribution version, with the source constant as a fallback for source and CMake installs lacking distribution metadata. An extracted-wheel subprocess test checks the real output without access to the source tree or third-party site packages. It fails before the fix and passes afterward.

### Include the new build inputs in the wheel-exclusion test

**#11016**, [test_canonical_imports.py:260](https://github.com/ROCm/rocm-libraries/blob/106e966b3cfd7bd49d866333b15d12cf7627c577/projects/hipblaslt/tensilelite/tensilelite/Tests/unit/source_only/test_canonical_imports.py#L260).

`test_wheel_excludes_source_only_tests` copies `pyproject.toml`, `MANIFEST.in`, and `requirements.txt` into its temporary build, but omits the newly required `setup.py` and `release_metadata.py`. It passes while producing `tensilelite-0.0.0`, without the declared runtime dependencies or custom `CleanBuildPy` behavior. Its exclusion result consequently describes a different build from the shipped wheel.

**Implemented in [4034bd1ac88](https://github.com/newling/rocm-libraries/commit/4034bd1ac887e45098deb9992d33ea36712ab30a):** copy both build inputs, set a fixed ROCm release for the test, and verify the resulting metadata includes the release suffix and a runtime dependency. The corrected wheel-exclusion test passes.

### Execute the generated CMake commands in the forwarding test

**#11017**, [test_packaging_metadata.py:74](https://github.com/ROCm/rocm-libraries/blob/7f57091d08bf0cc5cc631d9bfffa3efc52a4eb5b/projects/hipblaslt/tensilelite/tensilelite/Tests/unit/source_only/test_packaging_metadata.py#L74).

The two new CMake tests search source text for expected statements. They cannot establish that the configured build executes those statements, forwards the filter, or rejects a missing module. Wrapping the validation-filter append in `if(FALSE)` leaves the original test passing while removing the filter from the command.

**Implemented in [0e73c2b1460](https://github.com/newling/rocm-libraries/commit/0e73c2b146077690c612e10e71a03da75ef22d76):** replace those checks with a small CMake/Ninja build using a recording package. It checks the executed validation and generation commands, the nondefault filters, paths containing spaces, and configure failure when a required module is removed. The replacement catches the disabled-forwarding mutation. It records invocation behavior without compiling kernels.

## Suggestions

At [cli.py:40](https://github.com/ROCm/rocm-libraries/blob/7f57091d08bf0cc5cc631d9bfffa3efc52a4eb5b/projects/hipblaslt/tensilelite/tensilelite/cli.py#L40), bind the legacy entry point with `functools.partial`. The repeated imported name captured by lambdas produces Flake8 `F811` at the next import. **Implemented in [911ae84269f](https://github.com/newling/rocm-libraries/commit/911ae84269f1a4f563ac9e82b4ea65d0c8a0b162)**; the existing argument-forwarding, exception-restoration, and command-help tests pass.

## Handoff

The five suggestion commits are published on [review/pr11015-11017-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr11015-11017-suggestions). [351267e8321](https://github.com/newling/rocm-libraries/commit/351267e8321398bb7dd681dc50d6679f196f359b) and [4034bd1ac88](https://github.com/newling/rocm-libraries/commit/4034bd1ac887e45098deb9992d33ea36712ab30a) belong with #11016. [6fb4d906885](https://github.com/newling/rocm-libraries/commit/6fb4d906885daf916e49a406a82e673c1670145c), [0e73c2b1460](https://github.com/newling/rocm-libraries/commit/0e73c2b146077690c612e10e71a03da75ef22d76), and [911ae84269f](https://github.com/newling/rocm-libraries/commit/911ae84269f1a4f563ac9e82b4ea65d0c8a0b162) belong with #11017. The commits are ordered on the combined stack; the CMake-test commit follows the version-test addition in the same test file. The summation workflow remains unmodified and unresolved. No PR descriptions, comments, reviews, or review-thread states were changed.

## Appendix: summation-command counterexample

Run with the reviewed TensileLite package, its runtime dependencies, and rocisa importable. The setup substitutes hardware discovery and capability initialization. The dispatcher, summation workflow, logic-reader call, and create-library argument parser are real. The placeholder file's contents are immaterial because argument binding fails before the reader opens it.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tensilelite import GenerateSummations as summations, cli
from tensilelite.Common.Architectures import gfxToSwCodename

with TemporaryDirectory() as temporary:
    root = Path(temporary)
    logic = root / "logic"
    logic.mkdir()
    (logic / f'{gfxToSwCodename("gfx942")}_sample.yaml').write_text("{}\n")
    with (
        patch.object(summations, "validateToolchain", return_value=("cxx", "cc", "enum")),
        patch.object(summations, "detectGlobalCurrentArch", return_value="gfx942"),
        patch.object(summations, "makeIsaInfoMap", return_value={}),
        patch.object(summations, "assignGlobalParameters"),
    ):
        try:
            cli.main(["generate-summations", str(logic), str(root / "output")])
        except TypeError as error:
            print(error)
        else:
            raise AssertionError("Expected the obsolete reader signature to fail")

    try:
        summations.createLibraryForBenchmark(str(logic), str(root / "lib"), str(root), "gfx942")
    except SystemExit as error:
        print("Library creation exited:", error.code)
    else:
        raise AssertionError("Expected obsolete library options to be rejected")
```

The first call reports four missing arguments to `parseLibraryLogicFile`. The second reports `unrecognized arguments: --new-client-only --no-short-file-names` and exits through `printExit`.
