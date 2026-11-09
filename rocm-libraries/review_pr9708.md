This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#9708](https://github.com/ROCm/rocm-libraries/pull/9708)

**Reviewed head:** `9f658769910ffae218d72ea2b931a903abb13768`. **Base/merge base:** `8f13da7013dd64909c560e4823d5793bd57535a4`.

**Scope:** Independent review of the occupancy calculations, register-pool enforcement, global split-U store path, regression tests, and tuning-file changes. All six source/test files were inspected; all 290 YAML diffs were checked to contain only `MaxOccupancy` changes. Kernel generation was sampled.

**Local suggestion branch:** `review/pr9708-suggestions`, based on the reviewed head. Commit `8bc11102b2c3bc5841975073cd3a60aaafbe7883` implements the optional capacity cleanup below. The architecture-scope item remains an author decision.

## Tests

- **Submitted head:** native `_rocisa` built; the four occupancy/custom-kernel suites passed **256 tests, with 11 skipped**. Eighteen checks using the real register allocator enforced the computed limits across gfx1100/gfx1150/gfx1151, both wave sizes, and 128/256/512-thread workgroups. Five shipped kernels generated and assembled with AMD clang 23: gfx1100/gfx1150/gfx1151 wave32, plus gfx1100/gfx1151 wave64.
- **Suggestion commit:** native rebuild and **215 occupancy/build-time tests passed**. Every register-capability value matched the submitted head across 24 supported architecture entries.
- Applicable root pre-commit checks and whitespace checks passed. The changed Python files have 117 flake8 diagnostics, identical to the base.

The submitted suites were `test_occupancy.py`, `test_occupancy_buildtime.py`, `test_occupancy_hip.py`, and `test_custom_kernel_occupancy.py`; the suggestion rerun used the first two. No gfx11 GPU execution or performance comparison was performed locally. The description's 12,874-solution occupancy comparison was not independently reproduced.

Captured automated checks include passing [Windows gfx110X hipBLASLt tests](https://github.com/ROCm/rocm-libraries/actions/runs/39961723671/job/120603302953) and [rocISA/TensileLite component checks](https://github.com/ROCm/rocm-libraries/actions/runs/39961720377). The rollup also contains an [FFM gfx1250 failure](https://github.com/ROCm/rocm-libraries/runs/120467882780) with 252 passes, 2 failures and 7 timeouts; the failures are `lds_segment_interleave_2` and `mx_tdm_scales`. [TensileLite-CPP coverage](https://github.com/ROCm/rocm-libraries/runs/121178387791) is 48.93% and [hipBLASLt coverage](https://github.com/ROCm/rocm-libraries/runs/121178378682) is 64.43%, each below its 80% target. The [strict gfx1250 check](https://github.com/ROCm/rocm-libraries/actions/runs/39961720199/job/121535619073) was cancelled. These failures were not attributed to this PR.

## Summary

The fix uses the physical vector-register (VGPR) capacity to estimate how many workgroups fit on the GPU. It also accounts for groups of 32 or 64 threads when calculating each workgroup's register cost. Passing the resulting per-wave budget into a shared `setOccupancyLimits()` keeps ordinary stores and the global split-U path, which divides a matrix reduction among workgroups, on the same policy.

The new tests distinguish the larger register files, allocation granularity, and pool-growth limit. The real allocator checks support that last invariant. The gfx12 workgroup divisor and gfx1250 capacity/allocation exceptions preserve the explicitly deferred models.

## Actionable items

### Account for gfx10 and gfx117x in the validation scope

Locations: [KernelWriterAssembly.py:244](https://github.com/ROCm/rocm-libraries/blob/9f658769910ffae218d72ea2b931a903abb13768/projects/hipblaslt/tensilelite/tensilelite/KernelWriterAssembly.py#L244) and [hardware_caps.hpp:690](https://github.com/ROCm/rocm-libraries/blob/9f658769910ffae218d72ea2b931a903abb13768/projects/hipblaslt/tensilelite/rocisa/rocisa/include/hardware_caps.hpp#L690).

The wave-size-dependent divisor applies to gfx10, and the new gfx11 capacity applies to gfx117x. Both change the register budget used by production store batching, outside the eight targets covered by the reported rebuild and tuning-file edits. With wave32, 40 scalar registers, and no accumulator registers, `getMaxRegsForOccupancy()` returns:

| Target | Threads | Initial VGPRs | LDS bytes | Base: (budget, workgroups) | PR: (budget, workgroups) |
| --- | ---: | ---: | ---: | --- | --- |
| gfx1030 | 256 | 96 | 0 | (96, 5) | (128, 2) |
| gfx1170 | 128 | 64 | 16384 | (64, 8) | (128, 8) |

Wave32 is supported and automatically selected on gfx10. Shipped gfx1170/gfx1171 logic exists but is not repinned here. The gfx117x guard in `setOccupancyLimits()` only skips pool-limit installation; it does not preserve the previous budget calculation. The appendix reproduces the table using the actual base method and native capabilities.

Please either retain the previous model on these targets or explicitly include them in this change and provide regression and representative kernel-generation/occupancy evidence. If gfx117x is included, check its shipped solutions for any necessary `MaxOccupancy` adjustments. This is a demonstrated expansion of behavior and coverage, not evidence that the new numbers are mathematically wrong or that performance regresses.

No policy change was implemented locally because both scope choices are reasonable and require the author's decision.

## Suggestions

### Derive the gfx11 CU capacity from its per-SIMD capacity

At [hardware_caps.hpp:703](https://github.com/ROCm/rocm-libraries/blob/9f658769910ffae218d72ea2b931a903abb13768/projects/hipblaslt/tensilelite/rocisa/rocisa/include/hardware_caps.hpp#L703), the gfx11 architecture list and 1536/1024 capacities are duplicated. Derive `PhysicalMaxVgprCU` as `2 * PhysicalMaxVgpr * 32` so the compute-unit total follows the per-SIMD value already selected above.

Implemented in local commit `8bc11102b2c3bc5841975073cd3a60aaafbe7883`. The same cleanup limits the wave32-units comment to gfx11 and directly includes `<algorithm>` for the existing `std::transform` use. This is optional maintenance cleanup; the capability comparison found no behavior change.

## Scope decisions

Copy-ready question for the unresolved architecture choice:

> Should gfx10 and gfx117x adopt this model in this PR with corresponding generation and occupancy checks, or retain their previous behavior until that validation is available?

## Commentary

The tested head predates changes on `develop` in both `KernelWriterAssembly.py` and `Components/GSU.py`. For example, [the store-remap buffer change](https://github.com/ROCm/rocm-libraries/commit/9b4b2dcd30d) affects adjacent store code. Rebase and rerun the affected generation/tests before integration, as required by the component's guidance for these shared generator files. The local suggestion branch deliberately remains based on the reviewed head.

## Appendix: reproduce the architecture-scope examples

Use a checkout of the reviewed head with the base commit available in Git. Build its native rocISA module and install the TensileLite runtime/development requirements. In the command below, `$PYTHON` is that environment's interpreter, `$SRC_DIR` is the repository root, and `$BUILD_DIR` is the hipBLASLt CMake build directory. Put `amdclang++` on `PATH`.

Save this exact program as `scope_probe.py`:

```python
import ast
from math import ceil
import shutil
import subprocess
from types import SimpleNamespace

from rocisa import rocIsa
from tensilelite.KernelWriterAssembly import KernelWriterAssembly

path = "projects/hipblaslt/tensilelite/tensilelite/KernelWriterAssembly.py"
base = "8f13da7013dd64909c560e4823d5793bd57535a4"
source = subprocess.check_output(["git", "show", f"{base}:{path}"], text=True)
cls = next(n for n in ast.parse(source).body
           if isinstance(n, ast.ClassDef) and n.name == "KernelWriterAssembly")
method = next(n for n in cls.body
              if isinstance(n, ast.FunctionDef) and n.name == "getVgprOccupancy")
namespace = {"ceil": ceil}
exec(compile(ast.Module(body=[method], type_ignores=[]), path, "exec"), namespace)


class BaseModel(KernelWriterAssembly):
    getVgprOccupancy = namespace["getVgprOccupancy"]


compiler = shutil.which("amdclang++")
assert compiler
for isa, threads, vgprs, lds in [((10, 3, 0), 256, 96, 0),
                                ((11, 7, 0), 128, 64, 16384)]:
    ri = rocIsa.getInstance()
    ri.init(isa, compiler)
    ri.setKernel(isa, 32)
    results = []
    for model in (BaseModel, KernelWriterAssembly):
        kw = object.__new__(model)
        kw.states = SimpleNamespace(version=isa, kernel={"WavefrontSize": 32},
                                    regCaps=ri.getRegCaps(), archCaps=ri.getArchCaps())
        results.append(kw.getMaxRegsForOccupancy(threads, vgprs, 40, lds, 0, True))
    print(isa, "base, PR (maxVgprs, occupancy):", results)
```

The other calculation methods are unchanged in this PR. The base VGPR method uses `MaxVgpr`, whose values are unchanged for these two targets; it does not use their updated `PhysicalMaxVgpr`.

```bash
cd "$SRC_DIR"
export PYTHONPATH="$BUILD_DIR/tensilelite/rocisa:$SRC_DIR/projects/hipblaslt/tensilelite"
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" scope_probe.py
```

Observed output:

```text
(10, 3, 0) base, PR (maxVgprs, occupancy): [(96, 5), (128, 2)]
(11, 7, 0) base, PR (maxVgprs, occupancy): [(64, 8), (128, 8)]
```
