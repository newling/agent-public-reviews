This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15597](https://github.com/ROCm/rocm-libraries/pull/15597)

Reviewed head: `9647782990afa106cb809e949f330041294a5eb9`. Diff base: `932e90c1e33434697bfbae59633bff698b05762e`; fetched `develop`: `fb2bd975368e9ec5369eec26afaf00d2c80877f2`. Independent review of the two YAML changes, their pytest selection, and the hardware workflow. Existing PR discussion was not consulted. Suggestion branch: [review/pr15597-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15597-suggestions), based on the reviewed head and unchanged. Commit-to-item mapping: none.

## Tests

On the submitted head, 80 base/head selection comparisons passed using the repository's `configMarks` helper: two configs, 20 registered architecture skip markers, and hardware/functional-model environments. Parsed benchmark data is unchanged. Collection through `test_config.py` confirmed both items are skipped on `gfx1250-strict`; the decoupled-prefetch item remains enabled on `gfx1250`. A targeted pytest invocation with the strict target reported two skips before either test body ran. These checks used Python 3.12, pytest 9.2, and a previously built rocisa package for imports; they do not establish GPU execution or runtime. Root pre-commit had no applicable hooks for these YAMLs; `git diff --check` passed.

The reviewed head's [hardware job](https://github.com/ROCm/rocm-libraries/actions/runs/43960301545/job/133625738978) was still queued on 2026-11-16. Its pre-commit and PR-policy checks passed. No new hardware run was performed for this review.

## Summary

No production correctness defect or incorrect skip-marker behavior was found in this change. The material finding is the deliberate reduction in strict-target test coverage. The architecture-naming concern is inherited and belongs to a separate design follow-up.

The PR changes test selection without changing generated-kernel inputs or the workflow's 1200-second timeout. The [skip-marker construction and exact match in config_helpers.py:168](https://github.com/ROCm/rocm-libraries/blob/9647782990afa106cb809e949f330041294a5eb9/projects/hipblaslt/tensilelite/tensilelite/Tests/common/config_helpers.py#L168-L170) preserve plain `gfx1250` selection as described. The tradeoff is loss of strict-mode regression checks: the strict scheduler config becomes disabled on every supported target, while `stinky_sia4.yaml` retains identical benchmark groups for plain `gfx1250`. The description acknowledges the strict-target coverage loss, but the change provides no replacement strict-target execution path.

## Actionable items

### Preserve executable coverage when addressing the timeouts

At [stinky_sia4_gfx1250-strict.yaml:3](https://github.com/ROCm/rocm-libraries/blob/9647782990afa106cb809e949f330041294a5eb9/projects/hipblaslt/tensilelite/tensilelite/Tests/common/gemm/gfx12/stinky_sia4_gfx1250-strict.yaml#L3), adding the last architecture skip disables all 30 benchmark groups. Those groups exercise scheduler algorithm 4 across BF16, FP16, FP32 and narrow floating-point inputs, including four matrix transpose combinations. The same change in [decouple_pgr_tdm_fuse_gfx1250.yaml:3](https://github.com/ROCm/rocm-libraries/blob/9647782990afa106cb809e949f330041294a5eb9/projects/hipblaslt/tensilelite/tensilelite/Tests/common/gemm/gfx12/decouple_pgr_tdm_fuse_gfx1250.yaml#L3) removes that sweep's strict-mode execution while preserving its plain-target execution.

These tests still provide successful hardware validation. In [develop run 43795829142](https://github.com/ROCm/rocm-libraries/actions/runs/43795829142/job/133064363393), both named configs passed; their YAML contents match this PR's base. In [develop run 43549496237](https://github.com/ROCm/rocm-libraries/actions/runs/43549496237/job/132308465937), the decoupled-prefetch config exceeded 1200 seconds while the strict scheduler config passed. This supports the timeout concern, but also shows that wholesale skipping discards functioning checks. The markers apply to every invocation on the strict target, including nightly runs and build-only collection, rather than to the affected pull-request job alone.

Keep these checks executable on the strict target while fixing their test budget: partition the slow sweeps into independently scheduled configs, or retain a measured representative subset in pull-request CI and execute the remainder in a configured slower lane. The strict scheduler file's independent `BenchmarkProblems` groups provide a natural starting point for partitioning; the much larger first group in the decoupled-prefetch file needs a cut within its parameter sweep. Verify completion on the strict hardware runner before choosing the partition sizes.

The matching [stinky_sia4.yaml](https://github.com/ROCm/rocm-libraries/blob/9647782990afa106cb809e949f330041294a5eb9/projects/hipblaslt/tensilelite/tensilelite/Tests/common/gemm/gfx12/stinky_sia4.yaml) remains enabled on plain `gfx1250`. Its parsed `BenchmarkProblems` are identical, and its global parameters differ only in `Architecture`. The coverage loss is specifically execution with the strict target's compiler/runtime configuration and capability restrictions. These workloads remain represented in the non-strict test suite.

The tracking references and removal comments explain the intended follow-up, but they do not preserve an execution path in the meantime. This also conflicts with the repository's [instruction against disabling tests solely to make CI pass](https://github.com/ROCm/rocm-libraries/blob/9647782990afa106cb809e949f330041294a5eb9/AGENTS.md#working-rules). No fix commit was made: selecting and validating replacement partitions requires hardware timings and changes the PR's chosen approach.

## Suggestions

None.

## Scope decisions

New permanent unit tests are unnecessary for these two uses of an existing marker. The relevant validation is pytest selection on both target names and execution of any replacement configs under the real hardware timeout. The existing 1200-second workflow limit is unchanged. The reported aggregate timeout frequencies and the Jira follow-up details were not independently verified; the public CI examples above establish a narrower result.

The naming also exposes a broader design concern: test selection uses the complete compiler/runtime target string as the architecture identity, so a rule intended for the gfx1250 family must enumerate both variants. Adding a variant can bypass an existing family-wide exclusion. A separate design change could represent the architecture family, target variant and capabilities explicitly, and distinguish family-wide selectors from exact-target selectors. The exact compiler/runtime target must remain available because it determines compatible code objects and capability restrictions; stripping `-strict` globally would erase that distinction. This PR uses the existing convention, so redesigning target selection is separate from its timeout fix.

The suggestion branch remains at the submitted head with no commits. The review is complete; partitioning and target-hardware validation remain implementation work for the coverage finding.

## Appendix: reproduce the selection result

Use a TensileLite development environment with its documented Python dependencies and rocisa installed. Check out the reviewed head and run from `projects/hipblaslt/tensilelite`:

```bash
PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, str(Path('tensilelite/Tests/common').resolve()))
from config_helpers import configMarks

root = Path('tensilelite/Tests').resolve()
for name, expected in (
    ('decouple_pgr_tdm_fuse_gfx1250.yaml', (False, True)),
    ('stinky_sia4_gfx1250-strict.yaml', (True, True)),
):
    path = root / 'common/gemm/gfx12' / name
    for arch, skipped in zip(('gfx1250', 'gfx1250-strict'), expected):
        marks = configMarks(str(path), str(root), [arch], deviceTags=())
        actual = any(mark.name == 'skip' for mark in marks)
        assert actual == skipped, (name, arch, actual)
        print(name, arch, 'SKIPPED' if actual else 'ENABLED')
```

To observe pytest itself skipping the submitted configs without GPU execution, run the following from that same directory. Set `REVIEW_TMP` to an empty directory outside the source tree:

```bash
TENSILE_TEST_DEVICE_TAGS='' PYTHONDONTWRITEBYTECODE=1 \
python -m pytest -p no:cacheprovider --basetemp "$REVIEW_TMP" \
  tensilelite/Tests/common/test_config.py --gpu-targets gfx1250-strict \
  -k 'decouple_pgr_tdm_fuse_gfx1250 or stinky_sia4_gfx1250-strict' -q -rs
```
