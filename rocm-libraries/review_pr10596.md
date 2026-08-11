> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#10596 — `fix(tensilelite): stop coverage ratchet update from lowering floors`](https://github.com/ROCm/rocm-libraries/pull/10596)
**Base:** `develop`
**Files:** 3 changed (+325/-37)
**Assessment:** REQUEST CHANGES
**Risk:** 2/5 — manual CI-maintenance tooling only, but the command printed as
the safe remediation can reject its own file list, and unquoted paths make the
advertised copy/paste command incorrect or unsafe for valid repository names.

## Tests

I reviewed and tested PR head `4f3a7501aff` and verified that it merges cleanly
with current `develop` at `cb5fbee6f3d`.

The focused unit suite was run without the characterization suite's top-level
conftest, because this tool and its tests do not require the compiled `rocisa`
extension:

```bash
$VENV/bin/python -m pytest \
  projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/tools/test_coverage_ratchet.py \
  --noconftest -q
```

Result: 36 passed, 0 failed, 0 skipped, 0 errors in 0.08 seconds
(0.21 seconds wall time).

I also ran two direct counterexample probes:

- With floors `{a.py: 90, b.py: 80}`, current coverage
  `{a.py: 88, b.py: 79.5}`, and tolerance `1.0`, `check` reports only `a.py`
  and therefore suggests only `--allow-lower a.py`. Passing that authorization
  to `ratchet_floors()` still refuses `b.py`, because `update` does not apply the
  tolerance.
- `remediation()` renders `pkg/a b.py` as two shell arguments, renders a path
  containing `$(...)` with active command-substitution syntax, and renders
  `-leading.py` in a form that `argparse` rejects as a missing option value.

I tested a minimal implementation that:

1. holds an unapproved, in-tolerance dip at its existing floor without
   refusing the update; and
2. renders paths with `shlex.quote()` using
   `--allow-lower=<quoted-path>`.

After adding one tolerance regression test, three path-rendering cases, and
updating the existing string expectations for the `--option=value` form, the
focused suite passed: 40 passed, 0 failed, 0 skipped, 0 errors in 0.08 seconds
(0.20 seconds wall time). The first experimental run had 37 passes and 3
failures solely because three existing assertions hard-coded the prior
`--allow-lower path` spelling; those passed after being updated to the
shell-safe spelling. All experimental changes were removed, and the clean PR
suite was rerun successfully.

Additional checks:

```bash
git diff --check origin/develop...HEAD
git merge-tree --write-tree origin/develop HEAD
```

Both passed.

In public CI, `pre-commit` and the Codecov patch check pass. The TensileLite
coverage job's measurement step passes and its floor-enforcement step fails;
the PR does not change the currently stale `SubtileGREmit.py` baseline that is
handled by the sibling baseline PR.

## Summary

The PR changes `update` from an unconditional snapshot of `coverage.json` into
an asymmetric baseline operation. Existing floors rise to current coverage and
new files are pinned automatically. A measured decrease is held and causes the
entire update to fail unless that path was explicitly supplied through the
repeatable `--allow-lower` option. On refusal, the baseline is left unchanged.

The same path list is added to the remediation printed by `check`, and the
README now describes the explicit authorization workflow. The implementation
is compact and the main atomicity and per-file authorization behavior have
direct tests.

## Actionable items

1. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/tools/coverage_ratchet.py:234-252,256-284`
   — make the command printed by `check` sufficient for `update`.**

   `check` calls `find_regressions()` with the configured tolerance and prints
   `--allow-lower` only for drops beyond that tolerance. `update` then calls
   `ratchet_floors()` without the tolerance and refuses every representable
   decrease, including values that `check` deliberately classified as noise.

   For example:

   ```text
                 floor   current   delta
   a.py           90.0      88.0    -2.0   # regression
   b.py           80.0      79.5    -0.5   # within 1 pp tolerance
   ```

   `check` prints a command containing only `--allow-lower a.py`. Running that
   command refuses `b.py` and writes nothing. The developer must then authorize
   `b.py` too, which lowers its floor to 79.5 even though the documented
   tolerance says this variation should be absorbed rather than treated as a
   reviewed regression. This contradicts the new helper's “exact command” and
   “copy-pasted” contract.

   Pass the active tolerance into the update decision. For an unapproved
   current value between `floor - tolerance` and `floor`, retain the existing
   floor without adding a refusal. Continue to refuse a larger drop, and
   continue to lower any explicitly named path regardless of magnitude. Add an
   end-to-end test with one real regression plus one in-tolerance dip, asserting
   that the command printed by `check` succeeds, lowers only the named
   regression, and preserves the noisy file's existing floor.

2. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/tools/coverage_ratchet.py:73-86`
   — shell-quote every path inserted into the remediation command.**

   `remediation()` currently interpolates coverage paths directly into a shell
   program. A path containing whitespace is split into multiple arguments; a
   path beginning with `-` makes `argparse` report that `--allow-lower` has no
   value; and shell syntax such as `$(...)` is evaluated if a developer follows
   the explicit copy/paste guidance. Git and coverage reports permit all of
   these names.

   Render each entry in an option-assignment form such as
   `--allow-lower=<shell-quoted-path>`, using `shlex.quote()` for the value. The
   assignment form is needed in addition to quoting so a leading-hyphen path is
   not parsed as another option. Add direct tests for a space, a leading
   hyphen, and shell metacharacters, and update the existing remediation
   assertions to accept the safe spelling.

## Suggestions

None.

## Commentary

Existing PR discussion already covers the broader design question of coupling a
targeted accepted reduction with opportunistic increases to every other floor,
as well as the separate float-rounding concern. I intentionally did not repeat
those points here.

The PR explicitly leaves deletion of floors absent from the current report as a
follow-up. That remains the other way an `update` can weaken the baseline
without `--allow-lower`; it is worth resolving before this advisory gate becomes
required, but it does not overlap the two defects above.

## Appendix: counterexample probes

Run from the repository root:

```bash
$VENV/bin/python - <<'PY'
import importlib.util
from pathlib import Path

path = Path(
    "projects/hipblaslt/tensilelite/Tensile/Tests/unit/"
    "characterization/tools/coverage_ratchet.py"
)
spec = importlib.util.spec_from_file_location("coverage_ratchet", path)
ratchet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ratchet)

existing = {"a.py": 90.0, "b.py": 80.0}
current = {"a.py": 88.0, "b.py": 79.5}

regressions = ratchet.find_regressions(existing, current, tolerance=1.0)
assert regressions == [("a.py", 90.0, 88.0)]

floors, refused = ratchet.ratchet_floors(
    existing, current, allow_lower=["a.py"]
)
assert floors == {"a.py": 88.0, "b.py": 80.0}
assert refused == [("b.py", 80.0, 79.5)]

for filename in ("pkg/a b.py", "pkg/$(echo injected).py", "-leading.py"):
    print(ratchet.remediation([filename]).splitlines()[-2])
PY
```

The final three lines produced by the PR are:

```text
        --allow-lower pkg/a b.py
        --allow-lower pkg/$(echo injected).py
        --allow-lower -leading.py
```
