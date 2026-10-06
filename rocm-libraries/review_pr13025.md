This is a review from an agent with an automatic prompt from the reviewer

> Superseded by the [audited review](review_pr13025_audit_20261006.md), which adds the long-command filename fix and updated validation. The original draft is preserved below.

**PR reviewed:** [ROCm/rocm-libraries#13025](https://github.com/ROCm/rocm-libraries/pull/13025)

**Reviewed head:** [`f0d1510b27bc3c7fc158bb628b319c5bf6a80694`](https://github.com/ROCm/rocm-libraries/commit/f0d1510b27bc3c7fc158bb628b319c5bf6a80694) (2026-10-06), relative to #13022. Public repository and head; existing reviews/comments were not consulted.

**Local review branch:** `review/pr13025-suggestions-20261006`, based on that head. Commits in order: [`7d157cff873`](https://github.com/newling/rocm-libraries/commit/7d157cff87351b74188b731f6533cf54d587c091) cleans up surviving descendants; [`7c584f1d0f7`](https://github.com/newling/rocm-libraries/commit/7c584f1d0f70d359564dabf896b9e4950f9933e8) validates binary paths and load commands; [`b404ad9f4ce`](https://github.com/newling/rocm-libraries/commit/b404ad9f4ced00bd28b845f57ced4f8a9235bf65) preserves logs between invocations; [`9ac33a5a429`](https://github.com/newling/rocm-libraries/commit/9ac33a5a429a71472836c33a0266a78671df8c8e) registers the CPU tests in CI and clarifies interpretation of boundary correlations.

## Tests

Six CPU tests pass, using actual subprocesses and fake test binaries; the four failure scenarios below were reproduced before their fixes. The checker builds and its category-filter test passes; all 25 hunt records generate. Black, actionlint 1.7.12 and whitespace checks pass. The new CI workflow has been validated locally, not dispatched.

No GPU hunt, cotenant kernel, XNACK change or driver change was performed. CPU process tests establish orchestration behavior rather than GPU contention or a corruption rate.

## Summary

The runner varies requested load/XNACK combinations, records environment and outcomes, and distinguishes failed loads, skipped tests and no-test runs from clean results. Saving raw failure output alongside structured records is useful for reproducibility. The dedicated category keeps long hunts out of ordinary tiers.

## Actionable items

### Clean up descendants even after the load leader exits

In `projects/hipblaslt/clients/scripts/sdc_hunt/fast_check_sdc_hunt.py:288`, `stop` breaks as soon as `process.wait` returns after SIGTERM. A command can exit while a child in its process group ignores SIGTERM. That child survives the run and can contaminate subsequent load combinations.

Commit [`7d157cff873`](https://github.com/newling/rocm-libraries/commit/7d157cff87351b74188b731f6533cf54d587c091) still sends SIGKILL to any remaining process-group members. The regression starts a real child that ignores SIGTERM, verifies it survives the submitted cleanup, and verifies the fix stops it.

### Validate binary paths and nonempty load commands

In `main` (submitted line 389) and `load_command` (line 120) in the same file, `Path('./hipblaslt-test')` loses its `./` prefix and is executed as a PATH lookup, which fails even when the requested local executable exists. Separately, `--load command:` becomes an empty argument list; `run_once` treats it as no background load and can record a passing run under that load label.

Commit [`7c584f1d0f7`](https://github.com/newling/rocm-libraries/commit/7c584f1d0f70d359564dabf896b9e4950f9933e8) resolves and validates the test binary and validates load commands before starting a run. The tests reproduce both cases and retain the existing no-tests/skip failure behavior.

### Give each invocation a unique log identity

At submitted line 404 in the same file, invocation names have only second resolution. Two quick invocations appending to one results file use identical failure-log paths; the second overwrites the first record's evidence.

Commit [`b404ad9f4ce`](https://github.com/newling/rocm-libraries/commit/b404ad9f4ced00bd28b845f57ced4f8a9235bf65) adds a UUID to the timestamp. Its regression fixes the clock to one instant, runs twice, and checks that both records still point to their original distinct output.

### Keep the orchestration regressions in shared CPU CI

The submitted script has no automated tests for its lifecycle, parsing or persistence contracts. Commit [`9ac33a5a429`](https://github.com/newling/rocm-libraries/commit/9ac33a5a429a71472836c33a0266a78671df8c8e) adds the scoped `.github/workflows/hipblaslt-sdc-hunt-unit.yml:1` job, running the standard-library suite in `clients/scripts/sdc_hunt/test_fast_check_sdc_hunt.py`. It needs Python only and never launches a GPU workload. This protects the fixes without using a GPU lane.

## Suggestions

The introductory text in `projects/hipblaslt/clients/scripts/sdc_hunt/README.md:1` and `fast_check_sdc_hunt.py:1` equated correlation with a 4 GiB crossing to a carry-drop cause. Commit [`9ac33a5a429`](https://github.com/newling/rocm-libraries/commit/9ac33a5a429a71472836c33a0266a78671df8c8e) changes that to an investigation hypothesis, confirmed with controlled placement and inspection of the failing address arithmetic. A crossing can correlate with other aspects of a workload.

## Commentary

These are developer tools, so process/CLI tests are the lowest useful level for the identified defects. Dedicated hardware runs remain necessary to show that GEMM/cotenant loads create the intended contention and to investigate an actual numerical failure. The explicit hunt command is an appropriate opt-in boundary; routine CI should test the runner with fake workloads.

All reproducers are committed. The branch has the four commits above; nothing was pushed or posted.
