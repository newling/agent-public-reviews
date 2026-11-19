This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#16266](https://github.com/ROCm/rocm-libraries/pull/16266)

**Reviewed head:** `84e65d5e25bd89e6437d7261ab3b6493136ff845`

**Stack base:** `a67e8636f4f729bbe0439b95fb2c8afc204c4590` ([#16265](https://github.com/ROCm/rocm-libraries/pull/16265))

**Mode and scope:** Independent review of all 11 changed files: CI selection, workflows, lane script, path test, and documentation. The prerequisite's binding build and tests were inspected where these lanes consume them; this is not a full review of the prerequisite. Existing PR discussion was not consulted.

**Suggestion branch:** [review/pr16266-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr16266-suggestions), based on the reviewed head. [Commit 1d681b8797e](https://github.com/newling/rocm-libraries/commit/1d681b8797eb73ba92828abd6ebd255eeed6b58e) implements actionable item 1. [Suggested changes](https://github.com/newling/rocm-libraries/compare/84e65d5e25bd89e6437d7261ab3b6493136ff845...1d681b8797eb73ba92828abd6ebd255eeed6b58e).

## Tests

The submitted bindings built locally with Clang 23 and Python 3.12 against the available ROCm SDK `10.1.0a20260812`. The submitted and suggested CPU suites each passed 66 tests, with three expected skips: one device test and two tests requiring another ROCm installation. The injected source-header status described below went undetected on the submitted revision and failed with the expected unmapped-status diagnostic after the fix.

The component path test, seven component-selection cases, manual dispatch, and five executions of the workflow's Bash planning step passed. The planning cases covered an absent label, the exact gfx950 label, a similar nonmatching label, and all-lane selection. Root pre-commit and shell syntax checks passed. Actionlint reported custom runner labels and the pre-existing `needs.changes` reference in the summary job; no additional workflow error was found.

The submitted head's [hosted Component CI run](https://github.com/ROCm/rocm-libraries/actions/runs/44417778485) passed all five binding lanes against `10.3.0a20261116`: Linux CPU 66 passed/3 skipped, both Linux GPU lanes 67/2, Windows CPU 61/8, and Windows GPU 62/7. The device test executed on all three GPU lanes. Those jobs tested merge commit `deea803`, whose base at run time differs from the current stack base recorded above. The suggestion was validated locally; its full wheel-install driver, Windows execution, and physical GPU execution were not rerun. Some unrelated CI jobs remained unfinished at inspection. The policy bot's failure log reports a cancelled pre-commit check; the current pre-commit check passes.

## Summary

The change gives the opt-in bindings their own Component CI lanes and avoids rebuilding the library for binding-only changes. Sparse checkout, a small Linux CPU runner, a shared lane script, and explicit failure when a required GPU is absent fit that purpose. The path exclusions retain heavy CI when a PR also changes library files. The documentation correctly identifies the new lanes as informational during their initial qualification period.

For this CI change, lane execution, path selection, and failure propagation are the relevant validation levels. A kernel correctness or performance sweep is unnecessary because this PR changes no library or generated-kernel implementation. The main coverage gap is the mismatch between the headers the workflow checks out and the header the test actually reads.

## Actionable items

### 1. Read status values from the checked-out header

**Location:** [ci_lane.sh:59–63](https://github.com/ROCm/rocm-libraries/blob/84e65d5e25bd89e6437d7261ab3b6493136ff845/projects/hipblaslt/python/scripts/ci_lane.sh#L59), interacting with [test_errors.py:17](https://github.com/ROCm/rocm-libraries/blob/84e65d5e25bd89e6437d7261ab3b6493136ff845/projects/hipblaslt/python/tests/test_errors.py#L17).

The lane builds against the installed nightly and then invokes pytest without selecting the checkout's headers. `test_errors.py` obtains its header from `_build_info.HIPBLAS_COMMON_INCLUDE_DIR`, which CMake records from that installation. Checking out the public headers and triggering on their changes therefore does not deliver the promised status-enum coverage.

Adding `HIPBLAS_STATUS_REVIEW_PROBE = 1234` to the checkout's `hipblasStatus_t` leaves all 15 submitted status tests passing. The new value is never collected, even though the binding reports it as unmapped. This means a public-header PR can receive green binding checks without testing its new status value.

Select the source header explicitly for CI while preserving installed-header checks for ordinary local testing. [Commit 1d681b8797e](https://github.com/newling/rocm-libraries/commit/1d681b8797eb73ba92828abd6ebd255eeed6b58e) sets `HIPBLASLT_PY_TEST_SOURCE_HEADERS=1` in the lane and makes the existing test resolve the source header from its own location. The same probe then produces one failure and 15 passes, with `HIPBLAS_STATUS_<unmapped> (1234)` as the reason. It also narrows `DESIGN.md` and `TESTING.md`: this test covers status mapping, while other declaration changes still require updating the installed nightly.

## Suggestions

None.

## Scope decisions

The installed-nightly build remains the intended behavior. This review does not replace it with an in-tree library build or claim that the status test covers all public API changes. The deferred torch tests and initial informational status of the lanes are documented choices and do not prevent this CI setup from running the existing scaffold tests.

The testing-document cross-read covered hipBLASLt and TensileLite. Other components' test implementations were not re-reviewed: the shared workflow additions preserve their existing job inputs and selection behavior.

The published suggestion branch contains one commit for item 1. No finding was left unimplemented. The suggestion still needs hosted Windows/GPU validation if adopted. Publishing this report does not submit a GitHub PR review.

## Appendix: reproduce the missed source status

Use a clean checkout at either revision and a Python interpreter with that checkout's bindings and pytest installed. Set `SRC_DIR` to the checkout and `PYTHON` to that interpreter. Run from outside the package directory. The probe restores the header even when pytest fails. Expected result: submitted revision exits 0 with 15 passes; suggestion exits 1 with the added status reported as unmapped.

```bash
"$PYTHON" - "$SRC_DIR" <<'PY'
import os
from pathlib import Path
import subprocess
import sys

source = Path(sys.argv[1]).resolve()
header = source / "projects/hipblas-common/library/include/hipblas-common/hipblas-common.h"
test = source / "projects/hipblaslt/python/tests/test_errors.py"
original = header.read_text()
marker = "} hipblasStatus_t;"
assert original.count(marker) == 1
modified = original.replace(marker, "    HIPBLAS_STATUS_REVIEW_PROBE = 1234,\n" + marker)
env = dict(os.environ, HIP_VISIBLE_DEVICES="-1", PYTHONDONTWRITEBYTECODE="1",
           HIPBLASLT_PY_TEST_SOURCE_HEADERS="1")
try:
    header.write_text(modified)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", str(test), "-q"],
        env=env,
        cwd=Path.cwd(),
    )
finally:
    header.write_text(original)
sys.exit(result.returncode)
PY
```
