> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12332](https://github.com/ROCm/rocm-libraries/pull/12332)

**Reviewed head:** [`9031ffd062a444930add55a6af2cd159bd5c6ba7`](https://github.com/ROCm/rocm-libraries/commit/9031ffd062a444930add55a6af2cd159bd5c6ba7), unchanged when rechecked on 2026-09-25. The repository and PR head branch are public.

**Follow-up review:** At the reviewer's request, this revision considers the [posted human review](https://github.com/ROCm/rocm-libraries/pull/12332#pullrequestreview-5320597858). The suggestions below cover additional points and retain the independently obtained source and test evidence.

**Published suggestion branch:** [review/pr12332-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12332-suggestions), based on the reviewed head. These two optional commits are independent:

| Commit | Review item | Change |
| --- | --- | --- |
| [ad069345a58](https://github.com/newling/rocm-libraries/commit/ad069345a58ec616fdbb69227a878fbda754f4e2) | Suggestion 1 | Test widening for forward and mirrored traversal across all tensor names and both sparse operands. |
| [f700f1f66dd](https://github.com/newling/rocm-libraries/commit/f700f1f66dd8bea9f8a630edde542c8e053be6bc) | Suggestion 2 | Remove two unused imports from the sparse regression test. |

## Tests

The submitted stagger tests, rocISA build, gfx1201/gfx942 assembly builds, and client test-data generation passed; the suggestion branch's combined stagger tests, focused test-file lint, and applicable root pre-commit checks also passed.

These results are retained from the initial review: neither the PR head nor the suggestion commits changed. The CPU tests inspect generated dense WMMA and sparse SMFMA assembly. I additionally assembled both outputs, but did not execute their GPU instructions, repeat the large dense hardware regression, or measure performance. Local ROCm 7.1 required direct `amdclang++ -cc1as` invocation, with `-target-feature +real-true16` for gfx1201, because its driver rejects the generator's `-Xclangas` option.

CI was rechecked. Math CI preliminary, hipBLASLt precheckin, TensileLite unit/coverage, public gfx942 TensileLite, and pre-commit report success. The [gfx942 hipBLASLt shard that previously hung now passes on rerun](https://github.com/ROCm/rocm-libraries/actions/runs/36064001456/job/108160793307). The [gfx90a ASAN job](https://github.com/ROCm/rocm-libraries/actions/runs/36063999282/job/107857786831) and [rocJITsu sidecar](https://github.com/ROCm/rocm-libraries/actions/runs/36064001456/job/108163544083) still report container-runner errors; gfx1250 and some coverage statuses remain red. These results do not establish a regression from this change, but they do not support a claim that all CI is green either.

## Summary

The kernel advances its input-read address by a byte increment each main-loop iteration. For ordinary non-transposed dense A, that increment is `lda * DepthU * bytes_per_element`, where `DepthU` is the number of reduction elements processed per iteration. Staggered traversal multiplies the increment by a starting iteration and by the total iteration count; both products already have 64-bit results.

This PR corrects how those multiplications interpret their 32-bit operands. Forward increments use unsigned multiplication, preserving positive values with bit 31 set. Mirrored traversal retains signed multiplication for negative increments. The same correction also applies to the sparse-metadata products. For the ordinary forward buffer-load path discussed here, the host offset check already permits values above the signed boundary and below the unsigned boundary, so correcting the multiplication preserves that existing range.

This is a small arithmetic correction in widely used generator code. Reusing the existing helpers preserves the instruction structure and temporary-register lifecycle, and the submitted tests detect restoration of the original signed operations. I found no production correctness defect introduced by the diff.

## Actionable items

None requiring a production-code change.

## Suggestions

### 1. Add regression protection for the mirrored branch

**Locations:** `projects/hipblaslt/tensilelite/Tensile/KernelWriterAssembly.py:6760–6780, 6818–6835`.

Both submitted test configurations leave the mirror lists empty. They therefore do not protect the signed choice for mirrored traversal: unconditional unsigned widening would change an increment of `0xffffffe0` from a backward step of 32 bytes into a large forward step.

**Implemented in [ad069345a58](https://github.com/newling/rocm-libraries/commit/ad069345a58ec616fdbb69227a878fbda754f4e2):** `projects/hipblaslt/tensilelite/Tensile/Tests/unit/test_stagger_widening.py` checks both products for `A`, `B`, `Metadata`, `MXSA`, and `MXSB`, plus the metadata arm through sparse A and sparse B. It includes forward traversal, a mirrored reduction dimension, and a mirrored free dimension that must leave the reduction increment unsigned.

The tests pass against the submitted production code. With unconditional unsigned widening, the seven mirrored cases fail while the four submitted tests continue to pass. This is useful regression protection, not a reason by itself to hold the arithmetic fix. It checks the real emitter and its helpers; it does not claim numerical validation of complete mirrored GEMM execution. The exact mutation probe is retained below.

### 2. Remove the unused sparse-test imports

**Location:** `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/test_r3_stagger_incs_unsigned_sparse_gfx942_char.py:33–34`.

`codegen_harness as _ch` and `config_harness as _cfgh` are unused. The imported `_emit_asm` helper already loads its own dependencies. Remove these two imports to eliminate the new `F401` diagnostics.

**Implemented in [f700f1f66dd](https://github.com/newling/rocm-libraries/commit/f700f1f66dd8bea9f8a630edde542c8e053be6bc).** The combined stagger tests and focused test-file lint pass after removal. To reproduce the original lint errors, run `python -m flake8 Tensile/Tests/unit/characterization/_codegen/test_r3_stagger_incs_unsigned_sparse_gfx942_char.py` from `projects/hipblaslt/tensilelite` at the submitted head. The generator's other lint diagnostics match the merge base and are outside this suggestion.

## Commentary

The change retains a 32-bit per-iteration increment. Supporting steps outside that representation would require changes to increment generation and kernel eligibility; it is outside this fix.

Handoff: [review/pr12332-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12332-suggestions) is published with the two optional commits mapped above. The remote tip was verified as `f700f1f66dd8bea9f8a630edde542c8e053be6bc`, and the local working tree is clean. Before pushing, the target was fetched and the complete branch diff passed whitespace and applicable root pre-commit checks; focused test-file lint also passed. No new GitHub Actions runs or commit checks were reported for this branch after publication. Full hardware execution, performance measurements, and diagnosis of the remaining upstream CI failures are omitted as described above. No review was posted to GitHub.

## Appendix: reproduce the signedness mutation check

The added regression tests are committed in [ad069345a58](https://github.com/newling/rocm-libraries/commit/ad069345a58ec616fdbb69227a878fbda754f4e2). To reproduce the coverage comparison without editing production files, save the following as `$BUILD_DIR/check_stagger_mutant.py`. Run it from `projects/hipblaslt/tensilelite` with the same interpreter used for the unit tests. Use argument `u` for unconditional unsigned widening, or `i` for unconditional signed widening, followed by the relevant pytest file paths.

```python
import inspect
from pathlib import Path
import sys
import textwrap

sys.path.insert(0, str(Path.cwd()))
import Tensile.KernelWriterAssembly as kwa
import pytest

source = textwrap.dedent(inspect.getsource(kwa.KernelWriterAssembly.calculateStagger))
mode = sys.argv.pop(1)
assert mode in ("i", "u")
for name, condition in (("widenIncs", "unrollMirrored"),
                        ("widenMetaIncs", "metadataMirrored")):
    old = f"{name} = self.s_mul_i64_i32 if {condition} else self.s_mul_u64_u32"
    assert old in source
    source = source.replace(old, f"{name} = self.s_mul_{mode}64_{mode}32")
namespace = {}
exec(compile(source, "<stagger-widening-mutant>", "exec"), kwa.__dict__, namespace)
kwa.KernelWriterAssembly.calculateStagger = namespace["calculateStagger"]
raise SystemExit(pytest.main(sys.argv[1:]))
```

```bash
python "$BUILD_DIR/check_stagger_mutant.py" u -q \
  Tensile/Tests/unit/test_stagger_widening.py \
  Tensile/Tests/unit/characterization/_codegen/test_r3_stagger_incs_unsigned_gfx1201_char.py \
  Tensile/Tests/unit/characterization/_codegen/test_r3_stagger_incs_unsigned_sparse_gfx942_char.py
```
