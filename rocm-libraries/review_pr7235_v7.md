> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#7235](https://github.com/ROCm/rocm-libraries/pull/7235)

**Scope:** head `a5b426357866`

**Status refreshed:** 2026-09-21; the reviewed head and diff are unchanged.

**Proposed fixes:** [ROCm/rocm-libraries#12379](https://github.com/ROCm/rocm-libraries/pull/12379) is a draft stacked on this PR's head. Its two commits address the version-discovery and CUDA backend findings below independently.

## Tests

The 76 focused TensileLite resolver/validator tests and 5 shared-Tensile tests pass locally, as do Python/shell syntax and diff-whitespace checks. Focused CMake probes reproduce the hipSOLVER and hipFFT selection failures below, the HIP package reports `HIP_VERSION=7.1.25424` while `hip_VERSION` is empty, and the shared-Tensile lint command fails on the new unused `tempfile` import.

The hipBLAS, hipSOLVER, and hipFFT AMD precheckins pass on the current head, as does a gfx1250 hipBLASLt hardware job. The [hipBLAS CUDA job](https://math-ci.amd.com/job/rocm-libraries/job/precheckin-cuda/job/hipblas/job/PR-7235/22/stages/) fails because `hip::host` is undefined, the [hipSOLVER CUDA job](https://math-ci.amd.com/job/rocm-libraries/job/precheckin-cuda/job/hipsolver/job/PR-7235/20/stages/) fails after mixing the old and new backend selectors, and the [hipFFT CUDA job](https://math-ci.amd.com/job/rocm-libraries/job/precheckin-cuda/job/hipfft/job/PR-7235/10/stages/) fails during configuration. The shared-Tensile static-analysis job reports the same unused import. The gfx950 preliminary run also has one missing-code-object failure, the gfx90a AddressSanitizer test job is red, and the gfx1250 functional simulation reports 134 passes and 2 timeouts; those three results remain unresolved rather than serving as evidence for the findings below. The repository policy check also remains red because the PR body does not contain an accepted Jira or issue field.

## Summary

This pull request removes `hipconfig` from the shared-Tensile and TensileLite toolchain tuples, replaces the version query with environment/file/executable-path discovery, and changes backend selection in hipBLAS, hipSOLVER, and hipFFT. The two new tests for TheRock's `dist/bin` and `dist/lib/llvm/bin` layouts exercise the new path walk directly. The latest commit also uses the CMake 3.17 floor already merged through [ROCm/rocm-libraries#11988](https://github.com/ROCm/rocm-libraries/pull/11988) and restores imported CUDA targets in hipBLAS.

The current head is not ready to merge. Each CUDA build path still has a concrete selection or dependency failure, and standalone version discovery can still substitute a ROCm release number for the HIP compiler build number consumed by TensileLite. The added tests do not cover that behavior change, and one updated test file now fails the project's lint gate.

## Actionable items

### Discover and export hipBLAS' public CUDA dependencies

`projects/hipblas/CMakeLists.txt:88-94`, `projects/hipblas/library/src/CMakeLists.txt:68-72,116-125,183-197`, `projects/hipblas/rmake.py:343-355`, and the CUDA branches in `projects/hipblas/clients/{benchmarks,gtest,samples}/CMakeLists.txt`

The CUDA branch finds only CUDAToolkit, but the library and every CUDA client link `hip::host`. The current public CUDA job reaches generation and fails for exactly that reason. The installed target also exposes `CUDA::cublas` and `CUDA::cudart` publicly, while its export declares `HIP` and `hipblas-common` but not CUDAToolkit, so an installed consumer cannot recreate the public target graph.

Load the HIP config package for both backends, declare CUDAToolkit as a CUDA package dependency in the export, and validate an installed-package consumer. Update `rmake.py` to pass `CUDAToolkit_ROOT`: the current `CUDA_TOOLKIT_ROOT_DIR` spelling belongs to the removed `FindCUDA` path and is reported as unused by the CUDA job. The script should derive that root from the selected PATH `nvcc` rather than combining a PATH executable with the default `/usr/local/cuda` root.

### Use one backend selector throughout hipSOLVER

`projects/hipsolver/CMakeLists.txt:121-131`, `projects/hipsolver/install.sh:628-629`, `projects/hipsolver/library/CMakeLists.txt:49-53`, `projects/hipsolver/library/src/CMakeLists.txt:43-67,140-213,261-274`, and the remaining `HIP_PLATFORM` conditionals under `projects/hipsolver/clients`

The top level now uses `USE_CUDA`, but the library, source list, clients, compile definitions, dependencies, and export still use `HIP_PLATFORM`. In a clean local configure, `-DUSE_CUDA=ON` finds CUDA and then generates AMD sources with `__HIP_PLATFORM_AMD__`. The supported `install.sh --cuda` path does not add `-DUSE_CUDA=ON`; its new comment says `rmake.py` does this, but hipSOLVER has no such handoff.

The existing CUDA job demonstrates the inverse mismatch: it supplies `HIP_PLATFORM=nvidia` while `USE_CUDA` remains off, so the nested build selects NVIDIA sources but the top level never finds CUDA, and compilation cannot find `cusolver_common.h`. Replace the remaining backend conditionals with one selector, pass it from `install.sh`, and add configure assertions that the CUDA option selects NVIDIA sources, definitions, dependencies, clients, and export metadata.

### Make `USE_CUDA` select CUDA in hipFFT

`projects/hipfft/CMakeLists.txt:113-145`

The compiler-name branch runs before the new option. With an ordinary C++ compiler or `nvcc`, `-DUSE_CUDA=ON` selects `HOST-DEFAULT` and leaves the default library backend at ROCm; a local configure reproduces that result. The repository's current CUDA job uses `hipcc`, `HIP_PLATFORM=nvidia`, and `BUILD_WITH_LIB=CUDA` without `USE_CUDA`; the removed environment check therefore selects `HIP-CLANG` and terminates with `Detected HIP_COMPILER=clang, but BUILD_WITH_LIB is not ROCM!`.

Make the explicit backend option take precedence and connect it to the compiler/toolchain path that actually builds CUDA, or retain the existing selector until a direct-nvcc path is complete. Update the supported driver and CUDA job together, then test default host, project-toolchain, and CUDA configurations with assertions over `BUILD_WITH_COMPILER` and `BUILD_WITH_LIB`.

### Preserve the HIP build version used by Tensile consumers

`projects/hipblaslt/tensilelite/Tensile/Toolchain/Component.py:82-149`, `shared/tensile/Tensile/Common.py:2413-2467`, `shared/tensile/Tensile/cmake/TensileConfig.cmake:234-236`, `projects/hipblaslt/tensilelite/Tensile/CustomKernels.py:109-125`, and `projects/hipblaslt/tensilelite/Tensile/Toolchain/HelperKernelCache.py:45-56`

The old query and the HIP CMake package expose the compiler build number in the patch field. On a representative installation, those sources report `7.1.25424`, while `.info/version` reports the ROCm release `7.1.0`. The new resolver prefers `.info/version` for every explicit prefix. This is observable behavior: the same `6.4` toolchain represented as `6.4.3` fails the user-SGPR preload threshold, while `6.4.43482` passes, and the full value also contributes to the helper-kernel cache key.

Shared Tensile has an additional handoff error. Its uppercase `find_package(HIP)` call defines `HIP_VERSION`, but line 235 exports the empty lowercase `${hip_VERSION}`; the local package probe reproduced this exact casing difference. Use `${HIP_VERSION}` there. For standalone prefixes, parse `share/hip/version` or `include/hip/hip_version.h` before the release-level `.info/version`, or fail explicitly if the build-version meaning cannot be preserved. Apply the same ordering and error behavior in both implementations, and add direct tests for conflicting sources, `HIP_PATH`, unreadable/malformed/no-source cases, prerelease strings, and the downstream patch-sensitive decision.

### Keep the changed test models and gates truthful

`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/PublicInputSurfaceDeep/test_pchaos_Validators_L226_char.py:6-19,48-64,167-183`, `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/coverage-baseline.json:136-139`, and `shared/tensile/Tensile/Tests/unit/test_Common.py:27-29`

Production removes `supportedHip`, so `hipcc` and `hipconfig` are rejected by `_validateExecutable`, but the characterization model still lists both as supported and still describes five predicates. Its four comparison inputs avoid the changed names. A focused counterexample reports `model_rejected=False` and `actual_rejected=True` for both names even though all 76 selected tests pass. Remove the stale entries and wording, then include both removed names in the model-versus-production inputs.

The coverage file also lowers four per-file thresholds, including three files with no production change in this PR, and drops `Component.py` from 99.19% to 94.63% while the new resolver branches remain incompletely tested. Restore the unrelated thresholds and cover the resolver behavior described above instead of weakening the ratchet. Finally, remove the unused `tempfile` import; `flake8 Tensile/Tests/unit/test_Common.py` and the public static-analysis job both fail with `F401` at line 28.

## Suggestions

### Make the PR metadata describe the current change and pass repository policy

The title does not use the required Conventional Commits form. The body uses `JIRA:` instead of the machine-accepted `JIRA ID:` field, omits the required Test Result and Risk level sections, presents planned checks as completed results, and claims repository-wide removal even though active `hipconfig` discovery remains in MIOpen, hipDNN, and dnn-providers. The policy bot currently fails on the Jira field. A current-state rewrite is below; update the failed results after the code and jobs are fixed.

Suggested title:

```text
build: remove hipconfig from selected library build paths
```

Suggested description:

```markdown
JIRA ID : LCOMPILER-876

## Motivation

`hipconfig` and `hipcc` are legacy HIP build tools. Shared Tensile and TensileLite currently query `hipconfig` for the HIP compiler version, while hipBLAS, hipSOLVER, and hipFFT use `HIP_PLATFORM` to choose selected AMD or CUDA build paths. This change removes those dependencies from the components modified here; other `hipconfig` users in rocm-libraries remain outside this pull request.

## Technical Details

- Shared Tensile and TensileLite accept a version supplied by CMake and fall back to files under a ROCm installation or a root derived from tools on `PATH`.
- TensileLite removes `hipconfig` from its validated toolchain tuple and updates the affected tests.
- hipBLAS, hipSOLVER, and hipFFT add `USE_CUDA` as an explicit backend selector instead of consulting `HIP_PLATFORM`.
- hipBLAS uses CMake's `CUDAToolkit` imported targets on the CUDA backend. This depends on the CMake 3.17 minimum merged in [#11988](https://github.com/ROCm/rocm-libraries/pull/11988).
- Python-package ROCm discovery remains in the separate installation-model work in [#11023](https://github.com/ROCm/rocm-libraries/pull/11023).

## Test Plan

- Run the shared-Tensile and TensileLite unit and lint suites for version discovery and toolchain validation.
- Configure and build hipBLAS, hipSOLVER, and hipFFT on their AMD paths.
- Configure, build, install, and test each CUDA backend through its supported command-line driver.
- Configure a minimal consumer against the installed CUDA hipBLAS package.

## Test Result

- The current hipBLAS and hipSOLVER AMD precheckins pass; hipFFT remains pending.
- The TensileLite unit-coverage job and GitHub coverage workflow pass; project-level Codecov gates remain red.
- The current hipBLAS, hipSOLVER, and hipFFT CUDA precheckins fail in their changed backend-selection paths.
- Shared-Tensile static analysis fails on an unused import added by this pull request.
- Additional hipBLASLt preliminary and AddressSanitizer jobs are failing and require triage.

## Submission Checklist

- [x] Look over the contributing guidelines at https://github.com/ROCm/TheRock/blob/main/GOVERNANCE.md#pull-requests.

## Risk level

High (5/5): this pull request changes version discovery and backend selection across five components, and the three affected CUDA build lanes currently fail.
```

## Commentary

One additional approval was submitted on 2026-09-21 against the same unchanged head. GitHub still reports `CHANGES_REQUESTED` and applies the `Not ready to Review` label; the approval does not alter the code evidence or the findings above.

The latest commit resolves one important point from earlier reviews: hipBLAS now inherits the merged CMake 3.17 floor and can use `FindCUDAToolkit`. The branch has no changed-file overlap with the 26 commits added to `develop` since its merge base, so there is no high-coupling stale-base conflict under the hipBLASLt review rules.

The two new PATH-layout tests are useful and pass. They verify that the walk reaches `include/hip/hip_version.h` in both supported TheRock layouts. They do not resolve which version source has priority when several exist, and that decision matters because downstream code interprets the patch field as a compiler build number.

The branch still combines independent version-discovery work with three CUDA backend migrations. Splitting those units remains the lowest-risk route, but a combined change can be reviewed if each backend uses one selector and its CUDA configure/build/install tests pass.

## Appendix: focused counterexamples

Version behavior and validator-model checks, run from the TensileLite root with its task-owned Python environment:

```python
import os
import runpy
import tempfile
from pathlib import Path

from Tensile.Common import SemanticVersion
from Tensile.CustomKernels import supportsUserSgprKernargPreload
from Tensile.Toolchain.Component import get_rocm_version
from Tensile.Toolchain.Validators import (
    supportedCCompiler,
    supportedCxxCompiler,
    supportedDeviceEnumerator,
    supportedOffloadBundler,
)

with tempfile.TemporaryDirectory() as root:
    info = Path(root, ".info")
    info.mkdir()
    (info / "version").write_text("6.4.3")
    os.environ.pop("ROCM_VERSION", None)
    os.environ.pop("HIP_PATH", None)
    os.environ["ROCM_PATH"] = root
    release = get_rocm_version()
    assert not supportsUserSgprKernargPreload(release)
    assert supportsUserSgprKernargPreload(SemanticVersion(6, 4, 43482))

model = runpy.run_path(
    "Tensile/Tests/unit/characterization/PublicInputSurfaceDeep/"
    "test_pchaos_Validators_L226_char.py"
)
for component in ("hipcc", "hipconfig"):
    modeled = model["toolchain_component_rejected"](component)
    actual = not any((
        supportedCxxCompiler(component),
        supportedCCompiler(component),
        supportedOffloadBundler(component),
        supportedDeviceEnumerator(component),
    ))
    assert modeled == actual
```

The first pair of assertions passes and demonstrates the changed feature decision. The final assertion fails for both removed tool names.

The shared-Tensile package-variable probe is:

```cmake
cmake_minimum_required(VERSION 3.17)
project(tensile_version_probe LANGUAGES CXX)
find_package(HIP REQUIRED CONFIG)
message(STATUS "HIP_VERSION=${HIP_VERSION}")
message(STATUS "hip_VERSION=${hip_VERSION}")
```

The installed package reports a populated uppercase value and an empty lowercase value.

For hipSOLVER, place this configure-only module at `$BUILD_DIR/cmake-modules/FindCUDA.cmake`:

```cmake
set(CUDA_FOUND TRUE)
set(CUDA_VERSION_STRING "12.0")
set(CUDA_INCLUDE_DIRS "${CMAKE_CURRENT_LIST_DIR}/include")
set(CUDA_cusolver_LIBRARY "cusolver")
set(CUDA_LIBRARIES "cudart")
```

Then configure with `-DUSE_CUDA=ON -DBUILD_FORTRAN_BINDINGS=OFF -DBUILD_WITH_SPARSE=OFF -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_MODULE_PATH=$BUILD_DIR/cmake-modules`. The generated compile database contains `amd_detail` sources and `__HIP_PLATFORM_AMD__`.

For hipFFT, configure with `-DUSE_CUDA=ON -DBUILD_CLIENTS=OFF -DCMAKE_CXX_COMPILER=g++`. The configure output reports `BUILD_WITH_COMPILER = HOST-DEFAULT`, and the cache retains the default `BUILD_WITH_LIB=ROCM`.
