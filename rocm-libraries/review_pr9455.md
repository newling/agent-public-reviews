> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#9455 — `fix: replace unsafe yaml.load with safe loaders and add bandit B506 gate`](https://github.com/ROCm/rocm-libraries/pull/9455)
**Base:** `develop`
**Files:** 27 changed (+76/-48)
**Assessment:** APPROVED
**Risk:** 2/5 — test/utility YAML parsing and static-analysis configuration, with no
kernel or runtime-library behavior change.

## Tests

Commands run against PR head `260c3fbf5cf8`:

```bash
cd shared/tensile
$VENV/bin/bandit -q -r -t B506 Tensile HostLibraryTests tuning
$VENV/bin/python -m pytest Tensile/Tests/unit/test_mergeLogic.py -q

cd projects/hipblaslt/tensilelite
$VENV/bin/bandit -q -r -t B506 Tensile tests

PYTHONPYCACHEPREFIX=$TMP_PYCACHE \
  git diff --name-only origin/develop...HEAD -- '*.py' |
  xargs -r $VENV/bin/python -m py_compile

git diff --check origin/develop...HEAD
```

Results:

- Shared Tensile Bandit B506 scan: passed with zero findings in 2.89s.
- TensileLite Bandit B506 scan: passed with zero findings in 8.24s.
- `test_mergeLogic.py`: 11 passed in 0.16s.
- All changed Python files byte-compiled successfully. One pre-existing invalid-escape
  `SyntaxWarning` was emitted from `test_TensileCreateLibrary.py`.
- `git diff --check`: passed.

Current CI has the relevant Tensile/TensileLite static-analysis, unit-codecov,
precheckin, integration, pre-commit, and TheRock lanes passing. The overall Math CI
summary is red because two unrelated jobs were aborted.

## Summary

The PR replaces five loader-less `yaml.load()` calls in conversion utilities with
`yaml.safe_load()`. It also documents existing calls that use verified-safe aliases or
safe-loader subclasses, and adds Bandit B506 environments to the shared Tensile and
TensileLite static-analysis labels.

The appropriate regression level is a source-level security scan in shared CI, backed by
focused Python tests for the touched YAML paths. No device or architecture-specific testing
is required, and no test/flag waiver is needed.

## Actionable items

None.

## Suggestions

1. **`projects/hipblaslt/tensilelite/tox.ini:104-110` — include top-level hipBLASLt
   Python utilities in the CI security scan.**

   This PR reviews and suppresses the safe aliased load in
   `projects/hipblaslt/utilities/find_exact.py:103`, but the shared CI tox command scans
   only `tensilelite/Tensile` and `tensilelite/tests`. The added
   `projects/hipblaslt/.pre-commit-config.yaml` hook covers staged Python files only when a
   developer explicitly installs that nested config; the repository GitHub pre-commit job
   uses the root config. Expanding the CI scan to cover `projects/hipblaslt/utilities` would
   make the regression guarantee match the reviewed scope.

2. **The `# nosec B506 - explanation` annotations — move the explanation before the
   statement and leave only `# nosec B506` inline.**

   Bandit interprets every word after `B506` as another test identifier and emits hundreds
   of warnings such as `Test in comment: safe is not a test name or id`. A preceding
   explanatory comment plus a minimal inline suppression would keep the audit rationale
   while producing a clean security-lane log and avoiding many `# fmt: skip` additions.

## Commentary

The actual unsafe-load fixes are straightforward and correct: `safe_load()` accepts the
plain mappings/lists used by these conversion scripts while rejecting Python object
constructors. The reviewed aliases are also safe: they resolve to `CSafeLoader` or
`SafeLoader`, and `StrictTypeLoader` subclasses that safe base.

The PR head is from July 17, 2026, while `develop` has advanced through July 28, 2026 and
changed both `projects/hipblaslt/tensilelite/Tensile/LibraryIO.py` and the TensileLite
`tox.ini`. A current three-way merge is clean and retains the security environment, but
rerunning CI after rebasing would refresh the evidence against the current base.
