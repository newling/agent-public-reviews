> This is a review from an agent with an automatic prompt from the reviewer

**PR:** #9363 — `ci(hipblaslt): explore CPU rocjitsu race checks for gfx942/gfx950/gfx1151`
**Base:** develop
**Files:** 3 changed (+629/-3)

## Tests

Local checks run against the current PR head:

```bash
bash -n .github/scripts/run_rocjitsu_hipblaslt_race_check.sh
shellcheck .github/scripts/run_rocjitsu_hipblaslt_race_check.sh
python3 .github/scripts/tests/therock_matrix_test.py
git diff --check origin/develop...HEAD
```

Results:

- `bash -n`: passed.
- `shellcheck`: passed with no diagnostics.
- `python3 .github/scripts/tests/therock_matrix_test.py`: 6 tests passed in
  0.001s.
- `git diff --check origin/develop...HEAD`: passed.

I did not run the new end-to-end rocjitsu race check locally. It depends on a
TheRock artifact run, downloaded BLAS test payloads, and a rocm-systems rocjitsu
checkout matching the workflow layout. Current public CI still has TheRock jobs
running/failing; the relevant symptom for the actionable item below is visible in
the current check list: `gfx1151` package test jobs are still being scheduled
even though this PR's comment says they should be disabled while the CPU-side
rocjitsu sidecar is being validated.

## Summary

This PR adds a Linux TheRock post-build sidecar job that runs small hipBLASLt and
TensileLite workloads under rocjitsu race detection. The job fetches the BLAS
runtime/test artifacts from the just-finished TheRock build, checks out
rocm-systems, builds the rocjitsu CLI locally, verifies the packaged TensileLite
Python import path, then runs:

- `hipblaslt-bench` with a small zero-initialized f32 GEMM.
- The Tensile frontend with a small embedded YAML problem and the packaged
  `tensilelite-client`.

Both workload paths enable `RJ_RACE=1`, collect rocjitsu sink files under
`race-reports/`, and explicitly fail if a generated `race.log` contains `RACE`
records. The workflow uploads `race-reports/` even on failure.

The PR also adds `gfx1151` to the default Linux TheRock package target list and
tries to avoid consuming normal `gfx1151` GPU test capacity by passing an empty
`test_runs_on` value for that target.

## Actionable Items

1. **`.github/workflows/therock-ci.yml:167` — the `gfx1151` package-test skip
   expression does not actually produce an empty runner value.**

   The expression:

   ```yaml
   test_runs_on: ${{ matrix.target_bundle.amdgpu_family == 'gfx1151' && '' || matrix.target_bundle.test_machine }}
   ```

   uses the common `cond && a || b` pattern, but the intended true branch is the
   empty string. In GitHub Actions expressions, the empty string is falsy, so the
   expression falls through to `matrix.target_bundle.test_machine`. As a result,
   the callee still receives a real runner label, and `.github/workflows/therock-ci-linux.yml:164`
   does not skip the normal `gfx1151` package tests.

   This is visible in the current CI check list: `Linux (... | gfx1151) / Test
   (gfx1151)` jobs are being configured and run, including unrelated groups such
   as `rocfft,hipfft`, `hipcub,rocthrust,rocprim`, and `hipkernelprovider`. That
   contradicts the comment at `.github/workflows/therock-ci.yml:164-166`, and
   some of those newly scheduled `gfx1151` tests are failing.

   Fix this by moving the skip decision into a place that does not rely on a
   falsy true branch. For example, add `inputs.amdgpu_families != 'gfx1151'` to
   the `therock-test-linux` job condition in `.github/workflows/therock-ci-linux.yml`,
   or add an explicit boolean/string input such as `run_package_tests` and gate
   the reusable test workflow on that. If normal `gfx1151` package tests are
   meant to keep running, then remove the misleading comment and do not try to
   blank `test_runs_on`.

2. **`.github/workflows/therock-ci.yml:129` — adding `gfx1151` to the default
   Linux target list broadens every TheRock Linux matrix entry, not just the new
   hipBLASLt race check.**

   Because the default target list is now `gfx94X, gfx950, gfx1151`, any PR that
   triggers TheRock Linux CI will create `gfx1151` package build entries for all
   selected project groups. The rocjitsu sidecar itself is gated to groups whose
   `projects_to_test` contains `hipblaslt`, so non-BLAS groups get the extra
   `gfx1151` build/test matrix expansion without getting any race-check signal.

   If the intent is only to validate the new hipBLASLt rocjitsu sidecar for
   `gfx1151`, keep the broad package matrix defaults unchanged and add a
   narrower hipBLASLt-only path for producing the `gfx1151` artifact needed by
   the sidecar. If the intent is to add default Linux `gfx1151` coverage for
   every TheRock project, call that out explicitly in the PR because it is a
   much larger CI capacity and signal change than the race-check job itself.

## Suggestions

1. **`.github/workflows/therock-ci-linux.yml:176` — consider simplifying the
   skipped check name.**

   The public check list currently shows skipped sidecar entries with the literal
   suffix `rocjitsu race check (${{ inputs.amdgpu_families }})`, while the parent
   reusable-workflow job name already includes the target family. This is only a
   readability issue, but for a job that is skipped for most non-BLAS matrix
   rows, a shorter name such as `rocjitsu race check` would make the check list
   easier to scan.

2. **`.github/scripts/run_rocjitsu_hipblaslt_race_check.sh:443` — make the
   TensileLite validation-success grep a little more specific.**

   The script currently accepts any `PASSED` substring in the combined
   stdout/stderr log. That is probably fine for this reduced driver path, but a
   more specific pattern from Tensile's validation summary would reduce the
   chance that an unrelated diagnostic satisfies the check later.

## Commentary

The race-check driver script is otherwise careful about failure reporting: it
validates artifact layout before launching workloads, records per-stage timing,
runs both workloads even if the first one fails, checks application success and
race-report success separately, and uploads the generated report directory.

Building rocjitsu from rocm-systems inside the job is a reasonable bridge while
rocjitsu packaging is still incomplete. The script also keeps the bridge fairly
contained by building only the CLI and optional runtime/shim targets it needs.
