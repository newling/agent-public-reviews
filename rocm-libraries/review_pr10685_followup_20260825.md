> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#10685 — `test(tensilelite): add mutation execution safety core`](https://github.com/ROCm/rocm-libraries/pull/10685)

**Scope:** latest #10685 head `62ec407ab3e`, plus the published descendant
stack through #10858 head `df9d99e308d`

**Assessment:** REQUEST CHANGES

**Risk:** 4/5 — the ordinary tests are useful, and the latest mutation helpers
are much safer than the previously reviewed version, but there is currently no
single integrated stack head. The coverage wave also makes strong
characterization and coverage-policy claims that its assertions do not yet
support.

**Review mode:** final follow-up. At the reviewer's request, this pass considered
all review threads, reviews, discussion comments, and author replies on #10685,
plus the non-bot discussion on the descendant documentation PRs.

## Tests

The latest #10685 head is not an ancestor of any published descendant. I
therefore tested the latest root and the published terminal stack separately.

### Latest #10685 safety core

```bash
PATH="$VENV/bin:$PATH" \
  bash projects/hipblaslt/skills/tensilelite-mutation-rerun/scripts/tests/run-selftests.sh
```

Result in 19.03 seconds:

- 17 preflight checks passed;
- 233 verifier checks passed;
- 21 configuration-transaction pytest checks passed;
- 0 failed, skipped, or errored.

The direct command requires pytest on `PATH`; without the project environment,
the shell checks pass and the Python section stops with
`No module named pytest`. The added `tox -e mutation-safety` environment
provisioned successfully in 1.93 seconds.

```bash
bash -n \
  projects/hipblaslt/skills/tensilelite-mutation-rerun/scripts/{slice-preflight.sh,pyproject-mutmut.sh,mutmut-verify.sh} \
  projects/hipblaslt/skills/tensilelite-mutation-rerun/scripts/tests/{preflight-selftest.sh,mutmut-verify-selftest.sh,run-selftests.sh}
```

All six shell files passed syntax checking. ShellCheck reports style and
intentional generated-script diagnostics, including two `SC2209` warnings in
the verifier self-test; I did not find a production-script failure in those
diagnostics.

The mount-binding probe in Appendix A modeled a running container whose `/work`
belongs to another checkout. Preflight succeeded, wrote `env.json`, and never
queried the container mounts:

```text
preflight_rc=0 env_written=yes mount_queried=no
```

The pytest-result probe in Appendix B produced:

```text
clean_rc=0 mutant_setup_error_rc=1 verdict=KILLED base_rc=0 mut_rc=1
```

The changed run failed during fixture setup with `RuntimeError`, not an
assertion, but the verifier's return-code-only classifier called it an
assertion-proven kill.

### Published terminal stack

The focused mutation-driven tests passed:

```bash
$VENV/bin/python -m pytest -q \
  Tensile/Tests/unit/Common/test_Utilities.py \
  Tensile/Tests/unit/characterization/LibraryIO/test_logiccontract_char.py \
  Tensile/Tests/unit/characterization/LibraryIO/test_parse_integration_char.py \
  Tensile/Tests/unit/characterization/LibraryIO/test_readwrite_char.py \
  Tensile/Tests/unit/characterization/LibraryIO/test_writesolutions_char.py \
  Tensile/Tests/unit/test_Configuration.py \
  Tensile/Tests/unit/characterization/Naming/test_naming_char.py \
  Tensile/Tests/unit/test_BenchmarkSplitter.py \
  Tensile/Tests/unit/characterization/ProblemType/test_problemsizes_char.py \
  Tensile/Tests/unit/characterization/SolutionDerivation/test_derivation_char.py
```

Result: 348 passed, 116 skipped, 0 failed, and 0 errored in 32.12 seconds.

The focused coverage-harvest and code-generation tests also passed:

```bash
$VENV/bin/python -m pytest -q \
  Tensile/Tests/unit/Ductile/test_ductile_crossover.py \
  Tensile/Tests/unit/characterization/_codegen/test_r8_subtile_iterate_char.py \
  Tensile/Tests/unit/characterization/_codegen/test_setcover_gemm_char.py \
  Tensile/Tests/unit/characterization/_codegen/test_setcover_sparse_char.py \
  Tensile/Tests/unit/characterization/_codegen/test_setcover_streamk_char.py \
  Tensile/Tests/unit/characterization/SolutionDerivationSweep/test_setcover_reject_char.py \
  Tensile/Tests/unit/characterization/SolutionDerivationSweep/test_setcover_reject_other_char.py \
  Tensile/Tests/unit/characterization/_codegen/test_r6_subtile3_char.py \
  Tensile/Tests/unit/characterization/_codegen/test_mx_umlds0_char.py \
  Tensile/Tests/unit/characterization/_codegen/test_s*_char.py
```

Result: 93 passed, 148 skipped, 0 failed, and 0 errored in 52.45 seconds.
Many skips are expected architecture/toolchain selections.

```bash
$VENV/bin/python -m pytest -q \
  Tensile/Tests/unit/characterization/tools/test_coverage_ratchet.py
```

Result: 22 passed, 0 failed, 0 skipped, and 0 errored in 0.05 seconds.

`git diff --check` and a three-way merge-tree check against the current
`origin/develop` passed for the old terminal head. A merge-tree check between
the latest #10685 head and that terminal head failed with conflicts in the
skill metadata and the old mutation-tool paths.

As of August 25, 2026, CI is not green. The latest #10685 head has a failed
TensileLite coverage job, failed Codecov project checks, failed Math CI summary
and preliminary checks, and a failing hipBLASLt multi-architecture test job.
The unchanged #10856 and #10858 heads still show their August 21 policy and Math
CI failures.

## Summary

The stack has three materially different parts:

- **#10685:** optional offline mutation-analysis tooling. The latest revision
  moves it under the agent skill, explicitly says ordinary builds and CI do not
  use it, and adds substantial Docker-free safety tests.
- **#10686–#10692:** agent guidance for selecting tests, slicing mutation work,
  reviewing survivors, reporting, comparing runs, and choosing future targets.
- **#10693–#10707:** focused unit and characterization tests added after
  mutation campaigns over Utilities, LibraryIO, Configuration, Naming,
  BenchmarkSplitter, Problem, and Solution derivation.
- **#10852–#10858:** a coverage campaign over solution derivation and large
  code-generation files, including one production guard in #10856.

The latest #10685 revision is a substantial improvement. It addresses the
previous review's clean-baseline, empty-manifest, wrong-target restoration,
backup ownership, atomic-write, truthful-summary, and missing-self-test
findings. Moving the optional helpers under the skill also makes their
non-CI role much clearer.

The current publication state is nevertheless not reviewable as one stack:
#10685 gained two commits, but #10686 through #10858 still descend from the old
`44bf80a9de2` root. The terminal head contains neither the moved tools nor their
new tests, and directly combining the two published heads conflicts.

## Actionable items

1. **Stack topology — restack #10686 through #10858 onto the latest #10685
   before requesting final approval.**

   Latest #10685 is `62ec407ab3e`; the terminal #10858 head still contains
   `44bf80a9de2` as its root and does not contain the two new #10685 commits.
   The latest root is therefore not an ancestor of any descendant.

   This is not a cosmetic ancestry issue. #10685 now adds the skill metadata,
   moves the scripts out of `Tensile/Tests/unit/mutation`, and adds
   `references/execution.md`. #10686 independently adds older versions of the
   same skill files and edits the paths that #10685 removed. A direct
   merge-tree reports add/add and modify/delete conflicts.

   Rebase or restack every descendant, resolve the skill into one coherent
   version, rerun the focused tests and CI at the new terminal head, and update
   each PR's declared base. Until then there is no submitted revision that
   represents the proposed final stack.

2. **`projects/hipblaslt/skills/tensilelite-mutation-rerun/scripts/slice-preflight.sh:182-245`
   and `references/execution.md:61-89,161-180` — verify the container's `/work`
   mount during preflight, before the primary mutmut run.**

   Preflight verifies that the host source belongs to its Git worktree and that
   the named container exists, then records container status, image, and mutmut
   version. It never inspects `.Mounts`. The workflow subsequently edits the
   host checkout and runs mutmut under `/work/...` inside that container.

   A stale container can therefore point `/work` at checkout B while preflight
   records checkout A's commit and the configuration helper edits checkout A.
   The main campaign then runs against B under an `env.json` that claims A. The
   verifier checks its mount later, but that does not repair or invalidate the
   already-completed primary mutation run.

   Apply the verifier's canonical read-write mount check in preflight too, and
   add missing, read-only, and mismatched-mount self-tests. Appendix A
   demonstrates that the current preflight succeeds without ever querying
   mounts.

3. **`projects/hipblaslt/skills/tensilelite-mutation-rerun/scripts/mutmut-verify.sh:24,32-65,855-866`
   and `references/execution.md:276-319` — either stop calling pytest status 1
   assertion-only evidence, or inspect structured pytest outcomes.**

   The implementation sees only pytest's process status. Pytest status 1 means
   that collected tests failed, and includes fixture setup or teardown errors;
   it does not prove that an assertion failed. Appendix B has a test that passes
   clean, raises `RuntimeError` during fixture setup in the changed run, exits
   with status 1, and is classified `KILLED`.

   If any mutation-induced pytest failure is accepted as a kill, document and
   report it as a generic test failure rather than claiming the helper
   distinguishes assertion failures from other test errors. If the intended
   contract really is assertion-only evidence, emit and inspect a structured
   pytest report that distinguishes failed calls from setup/teardown errors.
   Add direct cases for all three phases.

4. **`projects/hipblaslt/skills/tensilelite-mutation-rerun/references/covering-set.md:1-7,50-89`
   and `SKILL.md:44-87,122-133` — do not certify a reduced test set merely
   because it reaches 80% of the target file.**

   Line coverage proves that selected tests execute source lines; it does not
   prove that all relevant assertions were selected. Two sets can reach the
   same lines while only one detects a mutant. The stack's own
   ValidParameters history demonstrates this: adding existing dedicated unit
   tests changed the mutation result materially after the initial
   characterization-only selection.

   Start from the complete unit-test candidate set, or compare every reduced
   selection against it on the same mutants. Record runtime and result
   differences before calling a slice `Certified`. A coverage threshold can be
   a scheduling heuristic, but it is not evidence that the mutation score is
   complete.

5. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/test_setcover_gemm_char.py:77-88`
   and analogous emit tests in #10854, #10857, and #10858 — assert the emitter
   behavior named by each test instead of discarding the emitted assembly.**

   `emit_kernels_from_config()` returns `(basename, source, err)`, but the
   snapshots intentionally use only `{basename, err}`. The companion smoke
   assertions generally check successful emission, a target directive, and an
   architecture string. A change to scheduling, offsets, loads, stores,
   conversions, or prologue order can therefore preserve every asserted value.

   These tests produce real execution coverage, but most do not characterize
   the code-generation branch named in the file or docstring. Capture a stable
   semantic projection of the relevant emitted instructions or marker ordering,
   and demonstrate sensitivity by perturbing the targeted emitter decision.
   Otherwise describe these as coverage/smoke cases rather than behavioral
   characterization.

6. **`projects/hipblaslt/tensilelite/Tensile/Components/LocalRead.py:611-632`
   and `Tensile/Tests/unit/characterization/_codegen/test_mx_umlds0_char.py:54-66`
   — reject the unsupported MX layout during solution validation.**

   The test documents that its gfx1250 configuration derives a `VALID` solution
   even though the M-major MX local-read layout is unimplemented and cannot emit
   a kernel. The production change converts the later `ZeroDivisionError` into
   a descriptive generic exception inside `localReadMX`, but invalid state can
   still reach code that assumes a derived solution is emit-capable.

   Add the unsupported-layout predicate to solution validation alongside the
   existing MX and `UnrollMajorLDS` constraints. The configuration should
   produce no valid solution with a specific rejection reason. A typed
   defensive invariant may remain in `localReadMX`, but it should not be the
   normal rejection path.

7. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/coverage-baseline.json:2,73,102`
   — do not lower the documented one-way floors merely because the rebased base
   contains additional uncovered code.**

   The terminal stack lowers:

   ```text
   Configuration.py  99.25% -> 92.53%
   Solution.py       76.77% -> 73.02%
   ```

   The baseline says coverage may rise but not fall. The recorded rationale is
   that source added on the base branch changed the denominator. That is still a
   coverage loss over the expanded source surface, and lowering the committed
   floor makes it permanently acceptable.

   Restack onto the final base, run the combined lane once, and add coverage for
   newly uncovered behavior before ratcheting. If floors are intended to be
   denominator-relative across base changes, change the policy and enforcement
   model explicitly instead of describing them as one-way.

## Suggestions

1. **The three set-cover emit tests and two derivation-rejection tests — commit
   or remove the claimed selection provenance.**

   Their docstrings cite uncommitted paths such as
   `work/mutcov-evidence/feature_setcover.py` and
   `work/mutcov-evidence/sol_reject_probe.py`. The committed tests preserve the
   selected inputs and expected outputs, but not how “highest marginal” or
   line-by-line target coverage was established. Commit a deterministic
   selector and compact evidence, or describe the corpus as manually curated.

2. **`projects/hipblaslt/skills/tensilelite-mutation-rerun/references/execution.md:326-335`
   — make the self-test command self-provisioning.**

   The documented direct Bash command fails when `python3` lacks pytest, even
   if the repository's project environment has it. Prefer
   `tox -e mutation-safety`, or explicitly require activating the project
   environment before running `run-selftests.sh`.

3. **`projects/hipblaslt/skills/tensilelite-mutation-rerun/scripts/Dockerfile:17-24`
   and `references/execution.md:61-84` — answer the two open provisioning
   questions in the text.**

   The Dockerfile installs tox, while the subsequent `tox --notest` command is
   intended to install mutmut and the inherited TensileLite dependencies into
   `/opt/tl-mut/mutation-unit`. State that division explicitly and add a quick
   post-provision check for the mutmut package and rocisa import.

## Commentary

### Existing feedback audit

The latest #10685 revision addresses the earlier review well:

- optional mutation analysis is now clearly separated from normal CI and
  ordinary builds;
- the helpers and Dockerfile live under the agent skill rather than the unit
  test tree;
- backup/set/restore is transaction-bound, hash-checked, and atomic;
- clean tests must return zero;
- empty, malformed, and duplicate manifests are rejected;
- changed paths are discovered from Git state and fully restored;
- expected-pass results no longer claim every mutant was killed;
- output and interruption handling fail closed; and
- substantial hermetic self-tests are committed.

The two newest root-PR comments ask where mutmut and the TensileLite
dependencies are installed. The documented tox-provisioning step appears
intended to provide both, but the explanation should be made explicit.

The descendant documentation PRs still contain unresolved reviewer questions:
four in #10686, one in #10687, and one in #10691. #10692 also has an answered
but unresolved design suggestion to use a deterministic dependency graph for
target prioritization. Restacking will rewrite overlapping skill text, so these
threads should be revisited against the new lines rather than mechanically
resolved.

### Per-PR disposition

- **#10685:** much improved; remaining issues are Actionable items 2 and 3,
  current CI failures, and the open Docker provisioning clarification.
- **#10686–#10692:** must be restacked; Actionable item 4 remains a methodology
  concern.
- **#10693, #10695, #10696, #10698, #10699, #10702, #10703, #10706, and
  #10707:** focused tests pass locally; no additional blocking implementation
  defect found in their submitted diffs.
- **Closed zero-diff intermediate PRs:** #10694, #10697, #10700, #10701,
  #10704, and #10705 contribute no independent current diff.
- **#10852–#10855:** useful coverage infrastructure and execution cases, but
  Actionable items 5 and 7 and the missing selection provenance remain.
- **#10856:** Actionable item 6 remains.
- **#10857–#10858:** substantial line-coverage gains, but the assertions mostly
  prove emission reached a configuration-derived name and status rather than
  protecting the targeted generated instructions.

The central distinction remains execution versus protection. Mutation testing
is useful precisely because reaching a line does not show that assertions
observe its behavior. The later stack should preserve that distinction rather
than treating broad emitter execution as complete characterization.

## Appendix A: preflight accepts a mismatched container checkout

Run from the repository root at the latest #10685 head:

```bash
#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
preflight="$root/projects/hipblaslt/skills/tensilelite-mutation-rerun/scripts/slice-preflight.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export calls="$tmp/docker.calls"

docker() {
  printf '%s\n' "$*" >>"$calls"
  case "$*" in
    version) return 0 ;;
    "inspect --type container fake") return 0 ;;
    *'--format {{.State.Status}}'*) printf 'running\n'; return 0 ;;
    *'--format {{.Config.Image}}'*) printf 'fake:image\n'; return 0 ;;
    *'--format {{.Image}}'*) printf 'sha256:fake\n'; return 0 ;;
    *'.Mounts'*) printf '/different/worktree\ttrue\n'; return 0 ;;
    "image inspect "*) printf 'fake:image@sha256:digest\n'; return 0 ;;
    "exec "*) printf '3.6.0\n'; return 0 ;;
  esac
  return 0
}
export -f docker

bash "$preflight" \
  --slice probe \
  --module Tensile/Common/Utilities.py \
  --container fake \
  --src projects/hipblaslt/tensilelite \
  --out "$tmp/out"

test -f "$tmp/out/env.json"
! grep -q '\.Mounts' "$calls"
```

Preflight exits zero and writes the artifact without asking which checkout is
mounted at `/work`.

## Appendix B: pytest setup errors receive the assertion-kill verdict

Save as `test_setup_error.py`:

```python
import os
import pytest

@pytest.fixture
def guarded_setup():
    if os.environ.get("REVIEW_MUTANT") == "1":
        raise RuntimeError("mutant broke fixture setup")

def test_case(guarded_setup):
    assert True
```

Then run:

```bash
REVIEW_MUTANT=0 python -m pytest -q test_setup_error.py
clean_rc=$?

REVIEW_MUTANT=1 python -m pytest -q test_setup_error.py
mutant_rc=$?

MUTMUT_VERIFY_LIB_ONLY=1 \
  source projects/hipblaslt/skills/tensilelite-mutation-rerun/scripts/mutmut-verify.sh
classify_verdict "$clean_rc" 0 "$mutant_rc" true ok
```

The changed run reports a fixture setup error and exits 1. The classifier
prints:

```text
KILLED	base_rc=0 mut_rc=1
```
