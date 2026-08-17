> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#9969 — `ci(hipblaslt): reland rocjitsu race detection`](https://github.com/ROCm/rocm-libraries/pull/9969)
**Base:** `develop`
**Files:** 8 changed (+670/-0)
**Assessment:** APPROVED
**Risk:** 2/5 — advisory CI only. The current burn-in policy explicitly accepts
possible detector false negatives, and the sidecar remains scoped to rows
selected by the hipBLASLt subtree marker.

## Tests

Code inspection and local tests used the rebased nine-commit branch at
`fd91d7f99629`, directly atop `develop` at `692ef3f227fd`. Public end-to-end CI
results below are from the pre-rebase PR head `6e544a87baf4`; the range-diff
shows that the rebase changed only conflict resolutions needed to retain the
new `gfx125X` default and test gate from current `develop`.

Commands:

```bash
PYTHONPATH=$THEROCK_SRC/build_tools/github_actions \
  $VENV/bin/python -m unittest discover \
    -s .github/scripts/tests \
    -p 'therock_*_test.py' \
    -v

shellcheck .github/scripts/run_rocjitsu_hipblaslt_race_check.sh

$VENV/bin/pre-commit run check-yaml --files \
  .github/workflows/therock-ci-linux.yml \
  .github/workflows/therock-ci.yml \
  .github/workflows/therock-rocjitsu-race-check-linux.yml

git diff --check origin/develop..HEAD
```

Results:

- TheRock matrix/configuration tests: 34 passed, 0 failed, 0 skipped, 0
  errors in 0.007 seconds (0.12 seconds wall time).
- `shellcheck`: passed in 0.08 seconds.
- YAML validation: passed in 0.16 seconds.
- `git diff --check`: passed.

The prior public CI run exercised both complete sidecars:

- `gfx94X-dcgpu`: passed in 1 minute 40 seconds. The internal stages reported
  2 seconds configure, 29 seconds build, 5 seconds for `hipblaslt-bench`, and
  11 seconds for TensileLite. Both workloads validated successfully and the
  uploaded race sinks contained no `RACE` record.
- `gfx950-dcgpu`: passed in 1 minute 47 seconds. The internal stages reported
  3 seconds configure, 28 seconds build, 5 seconds for `hipblaslt-bench`, and
  9 seconds for TensileLite. Both workloads validated successfully and the
  uploaded race sinks contained no `RACE` record.

The overall public TheRock run was red for unrelated infrastructure failures:
one Linux FFT producer failed during post-build upload because its generated
tree lacked `therock_manifest.json`; two Windows producers timed out while
fetching sources; and several Windows tests stopped at the three-minute driver
sanity timeout. The rocjitsu sidecars and the merged Linux BLAS build/test row
passed.

## Summary

The PR restores the hipBLASLt rocjitsu sidecar as an advisory CPU-emulation
consumer of the normal TheRock build artifacts. It runs two validated f32
workloads for `gfx942` and `gfx950`: a 128-cubed `hipblaslt-bench` GEMM and a
small generated TensileLite client workload. Rocjitsu is built from one pinned
rocm-systems revision, and logs, generated inputs, detector sinks, and timings
are uploaded even when a workload fails.

The matrix change records whether the original changed subtree was
`projects/hipblaslt` before optional projects and dependencies are folded
together. That provenance bit is attached only to the final row containing the
exact `tensilelite` token. This avoids launching the sidecar for rocBLAS-only
changes or provider rows such as `hipblasltprovider`. The tests cover those
cases, merged BLAS/MIOpen rows, workflow-wide matrix expansion, and an explicit
`test:hipblaslt` label.

## Actionable items

None.

## Suggestions

1. **`.github/scripts/run_rocjitsu_hipblaslt_race_check.sh:263-270,389-396` —
   consider requiring the race-detector sink after the initial burn-in.**

   Both checks use `if [[ -f race.log ]] && grep ...`; when `race.log` does not
   exist, the condition is false and the function returns success. The
   application validation can still pass if the race plugin failed to
   initialize, `RJ_RACE` stopped being honored, the sink path contract changed,
   or the file sink was otherwise disabled. That would turn the detector into a
   silent no-op while keeping this advisory check green.

   This is acceptable for the current advisory phase, where false negatives are
   an acknowledged tradeoff. The successful public artifacts demonstrate the
   expected stronger no-race contract:
   both workloads create a nonempty `race.log` containing kernel-dispatch
   records even though neither contains a `RACE` record. Require each expected
   sink to exist and be nonempty before checking for `^RACE ` once the check is
   promoted beyond burn-in. Prefer a shared helper so both workloads use the
   same validation, with missing-sink, clean-sink, and race-containing tests.

2. **`.github/workflows/therock-ci.yml:3-28,165` — describe the event policy as
   hipBLASLt-triggered rather than presubmit-only.**

   The provenance marker depends only on the selected subtrees, and
   `therock-ci.yml` forwards it without checking the event. A hipBLASLt change
   therefore sets `run_rocjitsu_race_check=true` for `push` events on `develop`
   and release branches, not only for pull requests. A manual
   `workflow_dispatch` selecting `projects/hipblaslt` does the same. Removing
   the marker from the separate nightly workflow prevents scheduled runs, but
   it does not make this sidecar presubmit-only.

   Running on those events is reasonable: the sidecar remains limited to the
   hipBLASLt-selected row and is advisory. Update the PR description and any
   presubmit-only wording to say that scheduled nightly use is disabled while
   hipBLASLt pull requests, pushes, and explicit dispatches may run it.

3. **`.github/workflows/therock-rocjitsu-race-check-linux.yml:73-90` — use the
   current checkout action version consistently.**

   The new workflow uses the repository's current `actions/checkout` v6 pin for
   TheRock but the older v5 pin for the rocm-libraries and rocm-systems
   checkouts. Align all three checkouts with the current v6 pin unless there is
   a documented compatibility reason not to.

## Commentary

The matrix provenance design is substantially safer than matching
`projects_to_test` by the `hipblaslt` substring. The exact marker survives
dependency folding, and the old public run confirms that unrelated project rows
skip the sidecar while the single merged BLAS row launches it for both target
families.

Before force-pushing the rebased stack, the final commit named `cosmetic`
should be folded into the relevant workflow commit or given a descriptive
message. Its comments explain the advisory workflow contract and are useful,
but the current subject obscures that purpose.
