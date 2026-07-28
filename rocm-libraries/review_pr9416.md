> This is a review from an agent with an automatic prompt from the reviewer

**PR:** #9416 — `fix(tensile): replace eval() with ast.literal_eval in CLI key=value parsers`
**Assessment:** APPROVED
**Risk:** 2/5 — host-side CLI parsing only, with direct regression coverage.

## Tests

Commands run against PR head `c8392e5ef191`:

```bash
cd shared/tensile
$VENV/bin/python -m pytest Tensile/Tests/unit/test_splitExtraParameters_security.py -q

cd projects/hipblaslt/tensilelite
$VENV/bin/python -m pytest \
  Tensile/Tests/unit/test_global_parameters_security.py \
  Tensile/Tests/unit/test_TensileBenchmarkCluster.py::TestBenchmarkParametersSecurity -q

git diff --check origin/develop...HEAD
```

Results:

- Shared Tensile: 6 passed in 1.59s (2.85s wall time).
- TensileLite: 4 passed in 0.10s (0.81s wall time).
- `git diff --check`: passed.

The TensileLite test environment required building the local `rocisa` package before
pytest collection. No GPU or client build is needed for this host-only parser change.

## Summary

The PR replaces executable `eval()` calls in five `--global-parameters` /
`--benchmark-parameters` parsers with `ast.literal_eval()`, converts invalid expressions
into normal `argparse` errors, and splits each assignment only at the first `=`. The tests
exercise both sides of the contract: literal values retain their Python types, while a
payload that would create a file under `eval()` is rejected without executing.

The appropriate level is a Python unit test in the shared CI lanes; architecture-specific
or GPU testing is not required. No test or feature-flag waiver is needed.

## Actionable items

None.

## Suggestions

None.

## Commentary

The tests are substantive: restoring `eval()` makes the marker-file assertions fail, while
returning raw strings makes the typed-literal assertions fail.

The relevant TensileLite unit/codecov, Tensile codecov/integration, and hipBLASLt precheckin
statuses passed. The overall PR rollup is still red because of a rocBLAS shard failure and
an aborted Tensile precheckin status. Also, the PR head is from July 15, 2026, while
`develop` has advanced through July 28, 2026 and changed
`projects/hipblaslt/tensilelite/Tensile/Tensile.py`. A three-way merge check is clean, but
rebasing and rerunning CI before merge would refresh the evidence against the current base.
