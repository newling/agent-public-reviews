> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#10696](https://github.com/ROCm/rocm-libraries/pull/10696)

**Scope:** mutation stack #10685–#10693, #10695, and #10696; separately based #8788  
**Assessment:** REQUEST CHANGES  
**Risk:** 4/5 — the stack's core helper temporarily changes tracked source, and
its current cleanup and accounting behavior can destroy unrelated edits or
report invalid evidence as successful.
**Review mode:** Follow-up review. At the reviewer's request, this revision
considers existing PR feedback, but retains only concerns independently
confirmed against the current heads.

## Tests

I reviewed the full stack at #10696's head and the separate #8788 head.

Focused tests run against the stack head:

```bash
PYTHONPATH="$SRC_DIR" "$VENV/bin/python" -m pytest -q \
  "$SRC_DIR/Tensile/Tests/unit/Common/test_Utilities.py"

PYTHONPATH="$SRC_DIR" "$VENV/bin/python" -m pytest -q \
  "$SRC_DIR/Tensile/Tests/unit/characterization/CommonUtilities/test_common_utilities_char.py" \
  "$SRC_DIR/Tensile/Tests/unit/characterization/LibraryIO/test_logiccontract_char.py" \
  "$SRC_DIR/Tensile/Tests/unit/characterization/LibraryIO/test_parse_integration_char.py" \
  "$SRC_DIR/Tensile/Tests/unit/characterization/LibraryIO/test_readwrite_char.py" \
  "$SRC_DIR/Tensile/Tests/unit/characterization/LibraryIO/test_writesolutions_char.py"

bash -n Tensile/Tests/unit/mutation/slice-preflight.sh
bash -n Tensile/Tests/unit/mutation/pyproject-mutmut.sh
bash -n Tensile/Tests/unit/mutation/mutmut-verify.sh
```

Results:

- `test_Utilities.py`: 81 passed in 0.10s.
- The CommonUtilities and LibraryIO characterization selection: 55 passed, 47
  skipped in 35.99s.
- All three shell helpers passed `bash -n`.
- Direct verifier classification checks correctly distinguished assertion
  failure (`KILLED`), success under mutation (`BAD`), collection/internal
  failure (`INCONCLUSIVE`), and explicit expected-pass mode (`OK`).
- Follow-up source inspection confirmed that `--root` selects a host source
  tree while container mutation always uses `/work/$SRC_REL`, with no mount
  validation. It also confirmed that the documented 32-worker cap is absent
  from the `mutation-unit` tox invocation.
- The #8788 snapshot directly includes a generated kernel basename/hash. The
  existing CI failure report for that PR says this field changed while the
  semantic tail-reset markers were unchanged.

The #8788 code-generation test could not be run in the available environment:
the compiled rocisa binding did not match that PR's Python source and conftest
import stopped with an `ImportError` for `SMulLOU32`. That is an environment
compatibility issue rather than evidence about the PR's behavior.

At review time, public CI was not green for either terminal head. #10696 had
failing TensileLite project-coverage checks and a failing TheRock summary; #8788
also had failing project-coverage checks and a failing TheRock summary. The
local focused Python tests above passed, but neither PR currently has clean CI
evidence.

## Summary

The eleven-PR stack is mostly a documentation and workflow package for
reproducible mutation testing: it describes selecting coverage sets, recording
provenance, triaging non-killed mutations, comparing reports, and choosing the
next target. Its executable core is #10685's three Bash helpers:

- preflight provenance capture;
- temporary `pyproject.toml` mutation configuration; and
- serial clean/mutated/reverted test verification.

#10693, #10695, and #10696 add ordinary Python tests for `clusterEnabled` and
LibraryIO contracts. #8788 is independent of that stack: it adds a CPU-only
SIA0/PGR2 code-generation characterization configuration and snapshot.

There is real executable code in this set, but the highest-risk code is the
verifier that intentionally edits tracked source. Its claimed fail-closed,
single-worktree, reproducible-restoration contract is not currently met.

## Actionable items

1. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/mutmut-verify.sh:100-105,120-131` — validate that the container and host source paths name the same worktree before mutating either.**

   `--root` changes the host target to `$ROOT/$SRC_REL`, but the container-side
   test and `mutmut apply` commands always operate on `/work/$SRC_REL`. The
   comment calling those paths equivalent is not a validation. If `/work` is
   mounted from another checkout, mutation can change that other checkout while
   restoration and the final clean check run against `$ROOT/$SRC_REL`. The
   report can then declare a clean host tree while leaving the container-mounted
   source mutated.

   Inspect the selected container's mount source and reject a mismatch with the
   requested root, or make all mutation, test, restoration, and cleanliness
   checks operate on one explicitly identified source tree. Add a test that
   models a distinct `--root` and container mount, and asserts the verifier
   refuses the invocation before a mutation is applied.

2. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/mutmut-verify.sh:115-117,152-175` — never reset a file that was already dirty when verification began.**

   The loop notices a dirty manifest target at lines 152-157 and correctly
   records `BAD: dirty-before-apply`. However, the unconditional EXIT trap at
   lines 115-117 subsequently runs `git checkout -- <target>` for every
   manifest target, including that pre-existing dirty file. The verifier exits
   unsuccessfully but has silently discarded the unrelated edit it was meant to
   protect.

   Reject a manifest before installing a restoring trap if any target is dirty,
   or snapshot only files proven clean before mutation and restore only those
   files that the verifier actually changed. Do not use `git checkout` as a
   blanket cleanup operation over unverified manifest paths. Add a hermetic
   regression test that leaves a tracked target modified before invocation and
   asserts the same diff remains after the verifier fails.

3. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/mutmut-verify.sh:146-197` — validate the manifest and make the final result match the recorded verdicts.**

   The first line is discarded without validating the required header, and an
   empty manifest therefore leaves `overall_ok=1` and exits zero with
   `RESULT: ALL KILLED`. The same false headline is emitted for a manifest row
   whose `expect_mutant_rc_nonzero=false`: `classify_verdict()` deliberately
   returns `OK` and says that outcome is not a kill, but lines 179-195 accept
   it as success and still print `ALL KILLED`. The parsed `revert_assert`
   column is likewise never consulted, so its documented true/false value
   currently has no effect.

   Require the exact header, reject an empty/malformed manifest, validate every
   field that controls classification, and emit distinct counts/results for
   killed and expected-pass rows. A zero-row run must be invalid evidence, and
   a run containing an `OK` row must not claim every mutant was killed. Either
   remove `revert_assert` from the format because restoration is mandatory, or
   implement and test its documented semantics. Add focused tests for an empty
   file, a missing header, an expected-pass row, and both `revert_assert`
   values.

4. **`projects/hipblaslt/tensilelite/pyproject.toml:187-196` and `projects/hipblaslt/tensilelite/tox.ini:78-88` — enforce the documented mutation-worker cap through the supported entry point.**

   The committed configuration explains that mutation runs must use
   `--max-children 32` to avoid self-contention and spurious timeouts. The
   `mutation-unit` tox environment nevertheless executes plain `mutmut run
   {posargs}`, leaving a documented entry point to use mutmut's
   machine-dependent default worker count.

   Put the bounded default in the tox environment or in one shared wrapper,
   with an explicit reviewed override when a slice needs a different limit.
   Test the rendered command or an equivalent invocation contract so a future
   edit cannot silently restore unbounded concurrency.

5. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/test_r7_sia0_pgr2_placement_char.py:84-97` and `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/__snapshots__/test_r7_sia0_pgr2_placement_char.ambr:5` — remove the unstable basename projection and assert the advertised PGR2 global-read placement.**

   The new characterization says it covers SIA0/PGR2 global-read placement and
   tail reset, but the snapshot contains only `tail_lr_reset_a` and
   `tail_lr_reset_b` plus a generated basename/hash. The basename has already
   changed in shared CI without a change to either tail-reset marker, so it
   produces unrelated golden failures. Conversely, the earlier PGR2 change
   moved `Global Read IncA/B` from iteration zero to the local-write iteration in
   `Components/SIA.py:noSchedGlobalRead`; it independently changed the
   tail-reset condition in `KernelWriter.py`. Reverting only the placement
   choice while retaining the tail-reset condition leaves this test's digest
   unchanged, so the stated placement regression can return without a signal.

   Exclude or normalize the non-semantic basename. Add a stable code-generation
   projection for `Global Read IncA/B` placement/order relative to the
   local-write iteration, alongside the tail-reset markers. A deliberately
   reverted placement decision should fail the new projection, while naming
   churn should not.

## Suggestions

1. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/mutation/README.md:23-33` — document the supported container build/discovery path and its required `/work` mount contract.**

   The README assumes an already-created container but does not say where it
   comes from or how to verify the required repository mount. The verifier
   should enforce that contract, but the human workflow should still link to
   the supported setup procedure.

2. **The three new `Tensile/Tests/unit/mutation/*.sh` files — use the repository's short SPDX header directly after the shebang.**

   This is a source-hygiene fix rather than a behavioral issue, but adding it
   now keeps the new executable files consistent with the repository's normal
   file-header convention.

## Commentary

The mutation-testing workflow documents an appropriately strict model:
infrastructure failures are not kills, a target module needs measured coverage,
and a report must preserve every input mutant. The verifier findings are
especially important because they undermine that model at the point where the
workflow selects, mutates, restores, and reports on source.

The ordinary LibraryIO and utility tests are focused and passed locally. The
SIA0 characterization also has a useful narrow configuration, but its
projection is currently both too sensitive to unrelated naming churn and too
insensitive to the placement behavior it claims to guard.

## Appendix: verifier counterexamples

Run this from a #10685 checkout with `$SRC_DIR` set to
`projects/hipblaslt/tensilelite`. It creates an isolated Git repository and a
fake Docker command; no real container or source mutation is required.

```bash
#!/usr/bin/env bash
set -euo pipefail

verifier="$SRC_DIR/Tensile/Tests/unit/mutation/mutmut-verify.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
src="$tmp/root/src"

git init -q "$src"
git -C "$src" config user.name reviewer
git -C "$src" config user.email reviewer@example.invalid
printf 'original\n' >"$src/victim.py"
printf '%s\n' \
  $'mutant_id\tfile\tapply_method\ttest_node\texpect_clean_rc\texpect_mutant_rc_nonzero\trevert_assert' \
  $'mutant_1\tvictim.py\tmutmut_apply\ttest.py::test_case\t0\ttrue\ttrue' \
  >"$src/manifest.tsv"
git -C "$src" add victim.py manifest.tsv
git -C "$src" commit -qm seed

# The verifier should reject this edit without changing it.
printf 'unrelated edit\n' >"$src/victim.py"
docker() { return 0; }
export -f docker
set +e
bash "$verifier" --container fake --manifest "$src/manifest.tsv" \
  --out "$tmp/out" --root "$tmp/root" --src src
rc=$?
set -e
test "$rc" -ne 0
git -C "$src" diff --quiet -- victim.py
```

The final `git diff --quiet` succeeds with the PR: the verifier reports
`dirty-before-apply`, then its EXIT trap resets the unrelated edit.

For the accounting defect, replace `manifest.tsv` with only the header line and
run the same command: the PR exits zero with `RESULT: ALL KILLED`. Restoring
the one data row but changing its sixth column from `true` to `false` also exits
zero and prints `RESULT: ALL KILLED`, even though the row is printed as `OK`
with “expected pass; not a kill.”
