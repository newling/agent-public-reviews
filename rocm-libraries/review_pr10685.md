> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#10685](https://github.com/ROCm/rocm-libraries/pull/10685)

**Scope:** the complete mutation-testing stack rooted at #10685 through the
current #10858 head  
**Assessment:** REQUEST CHANGES  
**Risk:** 4/5 — most product changes are tests and documentation, but the stack
contains safety-critical helpers that edit tracked files, a production
code-generation guard, and a large coverage campaign whose main emit oracle does
not inspect emitted assembly.

This is a follow-up review. I independently rechecked the current code, and also
audited whether the earlier review findings were addressed.

## Tests

I reviewed the stacked PRs individually against their declared base branches,
then tested the terminal stack head with a sparse checkout containing the
hipBLASLt/TensileLite paths.

### Mutation helper checks

```bash
bash -n \
  projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/slice-preflight.sh \
  projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/pyproject-mutmut.sh \
  projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/mutmut-verify.sh

shellcheck \
  projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/slice-preflight.sh \
  projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/pyproject-mutmut.sh \
  projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/mutmut-verify.sh
```

`bash -n` passed for all three files. ShellCheck reported only two informational
`SC2317` diagnostics for the source-or-execute library-mode idiom.

The focused classification probe in Appendix A produced:

```text
clean-fails-same-mutant: KILLED base_rc=1 mut_rc=1
clean-passes-mutant-fails: KILLED base_rc=0 mut_rc=1
```

The first result is invalid: a test that already fails before mutation cannot
prove that the mutant was killed.

The mismatched-target probe in Appendix B exited unsuccessfully after detecting
the leak, but left the actual mutated source file modified:

```text
verifier_rc=1
other_file_after=mutated other
git_status= M src/Tensile/other.py
```

The repeated-backup probe in Appendix C showed that running `backup` again after
`set` overwrites the only clean recovery copy. `restore` then restores the
already-modified configuration, and `assert-clean` fails:

```text
assert_clean_after_repeated_backup_rc=1
1 file changed, 9 deletions(-)
```

### Mutation-driven unit and characterization tests

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

Result: 348 passed, 116 skipped, 0 failed, and 0 errored in 38.81 seconds.

### Coverage-harvest and code-generation tests

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

Result: 93 passed, 148 skipped, 0 failed, and 0 errored in 55.53 seconds.
Many skips are expected architecture/toolchain selections. The new MX local-read
guard test passed in this group.

```bash
$VENV/bin/python -m pytest -q \
  Tensile/Tests/unit/characterization/tools/test_coverage_ratchet.py
```

Result: 22 passed, 0 failed, 0 skipped, and 0 errored in 0.07 seconds.

Passing the emit tests confirms that the current `{basename, err}` snapshots
match. It does not prove that those tests detect changes to emitted assembly,
because the tests deliberately discard the assembly string.

At review time on August 21, 2026, the terminal #10858 head and the production
fix #10856 do not have green public summary checks. Their lower-level
precheckin, static-analysis, Codecov, and TensileLite-unit jobs pass, but the
Math CI summaries and PR policy checks report failure. #10685 remains blocked
with changes requested.

## Summary

This is not one feature-sized change. It is a mutation-testing campaign split
across several layers:

- **#10685:** three Bash helpers and mutmut/tox configuration for environment
  recording, temporary configuration editing, per-mutant verification, and
  cleanup.
- **#10686–#10692:** an AI-agent skill describing target selection, focused
  test selection, slicing, survivor triage, test authoring, reporting,
  comparison, and prioritization.
- **#10693–#10707:** ordinary unit and characterization tests added after
  mutation campaigns over Utilities, LibraryIO, Configuration, Naming,
  BenchmarkSplitter, Problem, and Solution derivation. The currently closed
  intermediate PRs have no remaining diff; their retained work has been folded
  into adjacent open PRs.
- **#10852–#10855:** coverage-lane changes and a large configuration corpus used
  to execute previously uncovered derivation and emitter paths.
- **#10856:** the stack's one production change, converting a zero-width MX
  local read from a `ZeroDivisionError` into a descriptive exception.
- **#10857–#10858:** dozens of designed configurations and snapshots intended to
  cover large kernel-generation files.

The focused ordinary tests are generally readable and passed locally. The
blocking issues are concentrated in the infrastructure and in the meaning of
the later coverage results:

1. the verifier can certify a test that already fails;
2. it can leave the actual mutated source file changed;
3. the configuration backup can overwrite its own recovery point;
4. the safety-critical helpers still have no committed regression tests;
5. the selected-test “covering set” is not demonstrated to be complete;
6. the large emit harvest raises coverage without asserting the emitted
   instructions; and
7. the unsupported MX solution is rejected too late, during emission.

## Actionable items

1. **Stack ordering:
   `projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/mutmut-verify.sh:145-179,227-305`
   — move the verifier-evidence fix from #10858 into #10685 and restack all
   descendants.**

   The final commit in #10858 adds the header-only-manifest rejection and
   separates `KILLED` from expected-pass accounting. Those changes directly
   answer earlier feedback on #10685, but they are not present in #10685's
   current head. The bottom PR therefore remains independently unsafe and
   unapprovable; merging the stack bottom-up would not receive the correction
   until the final coverage PR.

   Put every #10685 fix on the #10685 branch, then rebase or restack all
   descendants. Each PR must be reviewable and safe at its own head. Do not use
   an unrelated final coverage PR as the delivery vehicle for foundational
   mutation-runner corrections.

2. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/mutmut-verify.sh:19-30,49-65,148-169,258-285`
   — require the clean test to pass; an arbitrary expected clean status can
   certify an already-failing test as a kill.**

   The manifest accepts any integer in `expect_clean_rc`. Classification first
   checks only that `base_rc == expect_clean_rc`, then reports `KILLED` whenever
   `mut_rc == 1`. Consequently:

   ```text
   base_rc=1, expect_clean_rc=1, mut_rc=1, revert=ok -> KILLED
   ```

   The mutation made no observable difference: the test failed both before and
   after application. This contradicts the skill's explicit rule that a claimed
   kill requires a passing unchanged-source test.

   For kill-verification rows, remove `expect_clean_rc` or require it and the
   observed clean status to be exactly zero. If a separate workflow genuinely
   needs an expected-failure baseline, give it a different record type and
   never classify it as a mutation kill. Add direct classification tests for
   clean statuses 0 and 1, equal clean/mutant statuses, setup errors, teardown
   errors, and restoration failures.

3. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/mutmut-verify.sh:181-201,209-216,261-275,292-298`
   — validate and restore the files actually changed by mutation application,
   not only the manifest's claimed file.**

   For `mutmut_apply`, the manifest's `file` column is not passed to mutmut;
   `mutmut apply <id>` chooses the real file from the mutant ID. A malformed or
   stale manifest can therefore name `Tensile/victim.py` while the ID changes
   `Tensile/other.py`. The cleanup trap restores only `victim.py`. The final
   status check notices `other.py` but does not restore it, leaving the worktree
   mutated after the verifier exits. The same problem is broader for
   `diff:<path>`, because one patch may modify, delete, or rename several files.

   The final check is also hard-coded to modified `Tensile/**/*.py` entries,
   ignores deletion/rename statuses, and explicitly filters
   `config_helpers.py`, despite the script claiming to be generic over any
   survivor.

   Snapshot the complete tracked state before application. Immediately after
   application, determine which paths changed and require them to match the
   manifest's reviewed declaration. Restore every path the operation changed,
   including deletions and renames, and verify the complete tracked state
   matches the pre-application snapshot. A mismatch should be rejected and
   cleaned before any test runs. Add the Appendix B counterexample as a
   hermetic regression test.

4. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/pyproject-mutmut.sh:83-98,100-222`
   — make backup ownership and restoration fail closed.**

   `backup` unconditionally overwrites its destination. If an operator repeats
   `backup` after `set`—a natural retry after an interrupted run—the clean copy
   is replaced by the edited `pyproject.toml`. `restore` then successfully
   copies the edited backup over the tracked file and has no way to recover the
   original. Appendix C reproduces this with the current script.

   Refuse to overwrite an existing backup unless an explicit replacement mode
   verifies that the source file is still equal to `HEAD`. Store the source
   commit and content hash beside the backup, and require them to match before
   restoration. Before overwriting the live file, verify that its current
   content is either the expected generated configuration or the original
   content; do not discard an unrelated edit made after backup. Write the
   generated TOML through a temporary file plus atomic replacement so an
   interruption or full filesystem cannot truncate the tracked configuration.

5. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/README.md:1-231`
   and the three files in `Tensile/Tests/unit/mutation/` — add committed,
   hermetic tests for the mutation safety core before treating it as reusable
   infrastructure.**

   The previous review asked for automated coverage of these scripts. The
   current stack still contains only the README and the three executable
   helpers; the comments about “library mode” and “selftested” functions refer
   to tests that are not committed. The final PR adds another 64 lines of
   manifest validation and result accounting without tests.

   This is not incidental command-line glue: the helpers overwrite tracked
   configuration, apply changes to tracked source, restore files on abnormal
   exits, parse a result manifest, and issue the evidence used to claim mutants
   were killed. Add a Docker-free test suite with a fake `docker` command and
   isolated temporary Git repositories. At minimum cover:

   - dirty and clean source;
   - mismatched and read-only mounts;
   - stopped/missing containers;
   - malformed, empty, duplicate, and mismatched manifests;
   - clean-pass/mutant-fail, clean-fail/mutant-fail, survivor, and tool-error
     classifications;
   - a mutant or diff changing a different or additional file;
   - interruption and restoration failure;
   - repeated backup, stale backup, and edits made after backup; and
   - byte-identical restoration after every failure point.

6. **`projects/hipblaslt/skills/tensilelite-mutation-rerun/references/covering-set.md:1-7,9-24,50-60`
   and `SKILL.md:44-72,107-120` — do not certify a manually selected test subset
   merely because it reaches 80% of the target file.**

   Line coverage proves that code executed; it does not prove that all relevant
   tests or assertions were selected. Two test subsets can cover the same lines
   while only one kills a given mutant. The stack's own ValidParameters history
   demonstrates this failure mode: adding existing dedicated unit tests to the
   initial characterization-only selection changed killed mutants from 191 to
   231 and changed “no coverage” from 22 to zero.

   Despite that evidence, the skill's certification gate remains “selected
   tests pass and target-file coverage is at least 80%.” That can produce a
   reproducible but incomplete mutation score.

   Start from the complete unit suite, or use mutmut's measured test-to-function
   association with a reviewed low `max_stack_depth` to identify direct unit
   tests. A reduced set should be accepted only after its per-mutant results are
   compared with the complete unit-test candidate set. Record false exclusions,
   runtime, mutant count, and total compute cost. Do not institutionalize
   file-based slices until the same campaign has been measured sliced and
   unsliced; slicing the same mutants and relevant tests mainly changes
   scheduling and resumability, not theoretical work.

7. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/test_setcover_gemm_char.py:77-88`
   and the analogous emit tests added by #10854, #10857, and #10858 — assert a
   stable projection of emitted assembly instead of discarding it.**

   `emit_kernels_from_config()` returns `(basename, source, err)`, but 53 emit
   tests construct snapshots as:

   ```python
   {"basename": b, "err": e} for (b, _s, e) in results
   ```

   The assembly is intentionally discarded. The companion assertions check
   only successful emission, a generic target directive, and architecture
   text. A mutation can change scheduling, offsets, loads, stores, conversion
   instructions, or prologue order while preserving the kernel configuration,
   basename, and `err == 0`; these tests will still pass.

   This is especially serious because the test names and docstrings identify
   precise emitter branches, and the PR descriptions say the generated output
   is recorded. The current goldens record configuration-derived names, not the
   behavior of those branches.

   For each target, capture a stable semantic projection of the canonical
   assembly: the relevant instruction sequence, marker ordering, operand
   calculation, or a reviewed canonical-source digest when a narrow projection
   is not feasible. Prove each test's sensitivity by temporarily reversing or
   changing its target emitter decision and showing the test fails. Avoid
   snapshotting only a generated basename hash, which is both sensitive to
   naming churn and insensitive to many emitted-instruction changes.

8. **`projects/hipblaslt/tensilelite/Tensile/Components/LocalRead.py:623-633`
   and `Tensile/Tests/unit/characterization/_codegen/test_mx_umlds0_char.py:54-66`
   — reject the unsupported MX layout during solution validation, before an
   invalid solution reaches kernel emission.**

   #10856 documents that the gfx1250 configuration derives a “VALID solution”
   even though its M-major MX local-read layout is unimplemented and cannot
   generate a kernel. The patch changes the eventual failure from
   `ZeroDivisionError` to a generic `Exception` inside `localReadMX`, but the
   invalid solution can still pass derivation and enter any path that assumes a
   derived solution is emit-capable.

   Add the corresponding predicate to `Solution.py` alongside the existing MX,
   `UnrollMajorLDS`, and local-read-width rejection rules. The configuration
   should produce zero valid solutions with a specific rejection reason. A
   defensive assertion or typed internal error may remain in `localReadMX`, but
   it should represent an unreachable invariant failure rather than the normal
   rejection mechanism. Update the test to exercise both early rejection and
   the defensive invariant directly if the latter is retained.

9. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/coverage-baseline.json:2,73,102`
   and `Tensile/Tests/unit/characterization/README.md:69-73,178-188` — do not
   lower committed “one-way” floors to accommodate uncovered base changes.**

   #10858 lowers:

   ```text
   Configuration.py  99.25% -> 92.53%
   Solution.py       76.77% -> 73.02%
   ```

   The committed baseline says coverage may rise but not fall, and the README
   says a floor should be reset only for an intentional code removal after
   review. The stated reason here is instead that the rebased source contains
   additional code not represented by the old measurement. That is precisely a
   coverage loss relative to the expanded source surface; lowering the floor
   makes the ratchet accept it permanently.

   Rebase the full stack onto its final develop revision, rerun the combined
   coverage lane once, and add tests for the newly uncovered source before
   updating floors. If the project wants floors to be automatically
   denominator-relative across base changes, change the documented policy and
   enforcement model explicitly rather than describing the baseline as a
   one-way ratchet.

## Suggestions

1. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/test_setcover_gemm_char.py:3-13`
   — commit the set-cover selection method and evidence.**

   The test cites `work/mutcov-evidence/feature_setcover.py`, but that path is
   not part of the stack. Commit a small deterministic selector, its input
   coverage data, and the selected output—or describe the corpus as a manually
   curated coverage set. Without the selection artifact, reviewers cannot
   reproduce the “highest marginal” claim or determine whether many near-
   duplicate configurations can be removed.

2. **`projects/hipblaslt/tensilelite/pyproject.toml:197-198` — evaluate and
   enable a lower `max_stack_depth` for the unit-test campaign.**

   The configuration mentions `max_stack_depth = 8` but leaves it disabled.
   Since the stated goal is to strengthen direct unit contracts rather than
   rely on broad integration tests, measure several thresholds and prefer
   direct tests first. Deeper tests can remain a fallback for survivors instead
   of being treated as equivalent evidence from the start.

3. **`projects/hipblaslt/tensilelite/pyproject.toml:138-141` — remove the
   reference to an internal evidence archive.**

   The stack now contains substantial public rerun guidance. Replace the
   inaccessible internal-repository reference with the committed skill and
   README so a public contributor can follow the complete supported workflow.

## Commentary

### Earlier review audit

The previous safety review was useful and several findings are addressed:

- the verifier now checks that `/work` names the requested read-write worktree;
- every manifest target is checked for pre-existing edits before the cleanup
  trap is installed;
- the unused restoration-control column was removed;
- all new shell files have the repository SPDX header;
- the tox entry point now defaults to 32 mutation workers; and
- the README explains how the user-provisioned container is constructed.

The empty-manifest and expected-pass accounting correction exists only at the
top #10858 branch and must be moved into #10685. The request for direct tests of
the safety helpers remains unaddressed.

### Per-PR disposition

- **#10685:** not ready because of Actionable items 1–5.
- **#10686–#10692:** the skill structure has repository precedent, but its
  selected-test certification and file-slicing model need Actionable item 6.
- **#10693, #10695, #10696, #10698, #10699, #10702, #10703, #10706, and
  #10707:** the submitted focused tests passed locally. I found no additional
  blocking implementation defect in these individual diffs beyond the campaign
  methodology issue.
- **Closed zero-diff intermediate PRs:** #10694, #10697, #10700, #10701,
  #10704, and #10705 currently contribute no independent reviewable change.
- **#10852–#10855:** useful coverage plumbing and configurations, but the
  set-cover provenance and floor policy need clarification.
- **#10856:** the failure is made more descriptive, but rejection belongs in
  solution validation rather than the emitter.
- **#10857–#10858:** the volume of configurations produces real line-coverage
  gains, but most emitted behavior remains unasserted because assembly is
  discarded.

The central distinction for this stack is between *executing code* and
*protecting behavior*. Mutation testing is intended to test the strength of
assertions. The final coverage wave largely returns to execution coverage:
thousands of lines are reached, while the oracle checks only that emission
returned a kernel name and status. That can be useful exploration data, but it
should not be presented as behavioral characterization until the relevant
output is actually asserted.

## Appendix A: clean-failure classification counterexample

Run from the repository root:

```bash
MUTMUT_VERIFY_LIB_ONLY=1 \
  source projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/mutmut-verify.sh

classify_verdict 1 1 1 true ok
```

Current result:

```text
KILLED	base_rc=1 mut_rc=1
```

The clean and mutated executions are indistinguishable and must not be
classified as a kill.

## Appendix B: mismatched mutant target leaves source changed

```bash
#!/usr/bin/env bash
set -euo pipefail

verifier="$SRC_DIR/projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/mutmut-verify.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

root="$tmp/root"
src="$root/src"
mkdir -p "$src/Tensile"
git -C "$root" init -q
git -C "$root" config user.name reviewer
git -C "$root" config user.email reviewer@example.invalid

printf 'original victim\n' >"$src/Tensile/victim.py"
printf 'original other\n' >"$src/Tensile/other.py"
printf '%s\n' \
  $'mutant_id\tfile\tapply_method\ttest_node\texpect_clean_rc\texpect_mutant_rc_nonzero' \
  $'m1\tTensile/victim.py\tmutmut_apply\ttest_x.py::test_x\t0\ttrue' \
  >"$tmp/manifest.tsv"

git -C "$root" add src
git -C "$root" commit -qm seed

export PROBE_ROOT="$root" PROBE_SRC="$src" PROBE_COUNT="$tmp/count"
docker() {
  if [[ "$1" == inspect && "$*" == *--format* ]]; then
    printf '%s\ttrue\n' "$PROBE_ROOT"
    return 0
  fi
  if [[ "$1" == inspect ]]; then
    return 0
  fi
  if [[ "$1" == exec && "$*" == *'mutmut apply'* ]]; then
    printf 'mutated other\n' >"$PROBE_SRC/Tensile/other.py"
    return 0
  fi
  if [[ "$1" == exec && "$*" == *pytest* ]]; then
    n=0
    [[ -f "$PROBE_COUNT" ]] && n=$(<"$PROBE_COUNT")
    n=$((n + 1))
    printf '%s' "$n" >"$PROBE_COUNT"
    [[ "$n" -eq 1 ]] && return 0 || return 1
  fi
  return 0
}
export -f docker

set +e
bash "$verifier" \
  --container fake \
  --manifest "$tmp/manifest.tsv" \
  --out "$tmp/out" \
  --root "$root" \
  --src src
rc=$?
set -e

test "$rc" -ne 0
test "$(cat "$src/Tensile/other.py")" = "mutated other"
git -C "$root" status --short -- src
```

The verifier reports a leak but does not restore `other.py`.

## Appendix C: repeated backup destroys the clean recovery copy

Run in a disposable checkout:

```bash
script=projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/pyproject-mutmut.sh
backup=$(mktemp)
rm -f "$backup"

bash "$script" backup --backup "$backup"
bash "$script" set --backup "$backup" \
  --only-mutate Tensile/Common/Utilities.py

# An operator retries "backup" after configuration was already changed.
bash "$script" backup --backup "$backup"
bash "$script" restore --backup "$backup"

# This fails because the backup now contains the edited file.
bash "$script" assert-clean
```
