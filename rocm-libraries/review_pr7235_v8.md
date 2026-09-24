> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#7235](https://github.com/ROCm/rocm-libraries/pull/7235)

**Revision reviewed:** `0310ef3152cf`

**History reviewed:** all conversation comments, submitted reviews, and inline threads on the pull request; the earlier local reviews through `review_pr7235_v7.md`; and the related corrective work in [#11634](https://github.com/ROCm/rocm-libraries/pull/11634), [#11808](https://github.com/ROCm/rocm-libraries/pull/11808), [#11988](https://github.com/ROCm/rocm-libraries/pull/11988), and [#12379](https://github.com/ROCm/rocm-libraries/pull/12379).

**Proposed fixes:** [`users/newling/pr7235-v8-review-fixes`](https://github.com/newling/rocm-libraries/tree/users/newling/pr7235-v8-review-fixes) is stacked directly on the reviewed head. Each code concern below links to its independent commit.

## Tests

On the reviewed head, the directly affected TensileLite selections passed locally with 185 tests passed and 14 skipped. The adjacent `Common/GlobalParameters.py` tests passed 12 tests, and the shared-Tensile `test_Common.py` suite passed 5 tests. On the proposed-fix branch, the expanded focused selection passed 208 tests with 14 skipped, and the expanded shared-Tensile suite passed 14 tests. Python compilation, shell syntax, the root security hook, and `git diff --check` also passed.

Focused configuration probes reproduced the backend and version failures below. With `USE_CUDA=ON` and `g++`, hipFFT configured `BUILD_WITH_LIB=ROCM`, generated AMD sources, and linked rocFFT. The resulting AMD build stopped on APIs absent from the installed rocFFT; that final compiler error is a local dependency-version mismatch, but the generated AMD build graph is the selector failure under review. Configure-only hipBLAS and hipSOLVER probes showed that their CUDA branches still execute `hipconfig` and inherit `__HIP_PLATFORM_AMD__` from `hip::host`; the same targets also receive the pull request's NVIDIA definition. A shared-Tensile package probe generated `ROCM_VERSION=`. A hipSOLVER driver probe showed that `install.sh --cuda` omits `-DUSE_CUDA=ON`.

The same probes pass on the proposed-fix branch: hipBLAS and hipSOLVER CUDA sources receive only NVIDIA definitions, hipFFT selects CUDA from either `USE_CUDA=ON` or the legacy `BUILD_WITH_LIB=CUDA`, the hipSOLVER driver forwards `USE_CUDA`, and shared Tensile emits `ROCM_VERSION=7.1.25424`. Combined local coverage data measured 97.00% for `Assembly.py`, 99.53% for `Component.py`, 99.16% for `HelperKernelCache.py`, and 97.75% for `Source.py`, satisfying the restored floors within the checker tolerance.

A broader run of all five touched TensileLite test files reported 210 passed, 14 skipped, 3 failed, and 3 setup errors. The six unsuccessful cases are unchanged real-solution fixtures that rejected a gfx942 matrix instruction under this host's compiler capability report. The current public TensileLite lane passes the corresponding source suites, so I do not attribute those six local results to this pull request.

The current public AMD and CUDA precheckins for hipBLAS, hipSOLVER, and hipFFT pass, as do the shared-Tensile and TensileLite unit lanes and the five-architecture hipBLASLt preliminary run. The CUDA logs matter here: [hipBLAS](https://math-ci.amd.com/job/rocm-libraries/job/precheckin-cuda/job/hipblas/job/PR-7235/27/stages/) still receives `HIP_PLATFORM=nvidia` from its container, [hipSOLVER](https://math-ci.amd.com/job/rocm-libraries/job/precheckin-cuda/job/hipsolver/job/PR-7235/25/stages/) receives `-DHIP_PLATFORM=nvidia`, and [hipFFT](https://math-ci.amd.com/job/rocm-libraries/job/precheckin-cuda/job/hipfft/job/PR-7235/15/stages/) receives `BUILD_WITH_LIB=CUDA` while reporting `USE_CUDA=OFF`. Those jobs do not test the new selector in a clean environment. The [gfx90a AddressSanitizer build](https://github.com/ROCm/rocm-libraries/actions/runs/35785127514/job/107348099848) passed, but its [test runner](https://github.com/ROCm/rocm-libraries/actions/runs/35785127514/job/107358603516) died after three hours without producing test output. The [rocJITsu sidecar](https://github.com/ROCm/rocm-libraries/actions/runs/35785129239/job/107348131810) fails before its TensileLite run because `joblib` is absent, which is tracked separately by [#12425](https://github.com/ROCm/rocm-libraries/pull/12425). The [hipBLASLt C++ coverage run](https://math-ci.amd.com/job/rocm-libraries/job/codecov/job/hipblaslt/job/PR-7235/38/stages/) passes all 22,091 tests and then aborts while writing LLVM profile data.

## Summary

This pull request changes version discovery in shared Tensile and TensileLite, removes `hipconfig` from their validated tool lists, and replaces backend selection in hipBLAS, hipSOLVER, and hipFFT. The four commits added after the previous review fix six concrete problems: they use the merged CMake 3.17 floor, restore hipBLAS' HIP package lookup, prefer HIP build metadata, correct the validator model, remove the lint failure, and restore the public CUDA lanes.

The implementation is still not ready to merge. The public CUDA jobs pass through legacy environment or cache settings rather than the new interface, and clean uses of that interface select the wrong backend or conflicting compile definitions. The installed hipBLAS target also omits a package dependency. Both version implementations still have reachable paths that discard or ignore the HIP build version they claim to preserve.

**Risk:** High (4/5). The change spans five components and changes build selection, package exports, and the compiler version used while generating GPU kernels. The default AMD jobs are healthy, but the new CUDA entry points and two standalone version paths lack passing evidence.

## Actionable items

### Make `USE_CUDA` determine the HIP backend before package discovery

`projects/hipblas/CMakeLists.txt:80-97`, `projects/hipsolver/CMakeLists.txt:121-136`, `projects/hipfft/CMakeLists.txt:113-149`, `projects/hipfft/cmake/dependencies.cmake:24-65`, and `projects/hipfft/library/CMakeLists.txt:34-35`

**Proposed fixes:** [hipBLAS `3989fb1`](https://github.com/newling/rocm-libraries/commit/3989fb1b64076fda97e696f703139c199fffe21a), [hipSOLVER `6c3b6dc`](https://github.com/newling/rocm-libraries/commit/6c3b6dce519b305c6140d6a7bbd40152eaafea2f), and [hipFFT `7e09c50`](https://github.com/newling/rocm-libraries/commit/7e09c50bb48b83e17840a3c523d4b06d73e95465)

The new option does not define the platform consumed by HIP's CMake package. The ROCm 7.1 HIP package used for local validation runs `hipconfig --platform` whenever the CMake variable `HIP_PLATFORM` is undefined. A clean `USE_CUDA=ON` configure therefore still executes the deprecated program and can load the AMD form of `hip::host`. Configure-only probes for hipBLAS and hipSOLVER produced both `__HIP_PLATFORM_AMD__=1` and the pull request's `__HIP_PLATFORM_NVIDIA__` definition on each CUDA source.

hipFFT has an additional selection error. `USE_CUDA` changes `BUILD_WITH_COMPILER` only when the compiler name ends in `nvcc` or `hipcc`; with the normal `g++` compiler, it selects `HOST-DEFAULT` and leaves the cached `BUILD_WITH_LIB` value at `ROCM`. A clean local configure with only `-DUSE_CUDA=ON -DCMAKE_CXX_COMPILER=g++` generated `amd_detail/hipfft.cpp` and linked rocFFT. The passing public CUDA job does not cover this input: its log shows `BUILD_WITH_LIB=CUDA` and `USE_CUDA=OFF`.

Derive `HIP_PLATFORM` from `USE_CUDA` before any HIP package lookup in each component, and make hipFFT normalize `BUILD_WITH_LIB` from the explicit option before it classifies the compiler. Keep any legacy translation one-way into `USE_CUDA`; downstream source, package, and compiler choices should read only the normalized result. Add configure tests with `HIP_PLATFORM` unset that assert the chosen source tree, compile definitions, and dependencies for `g++`, `hipcc`, and `nvcc` where supported.

### Export hipBLAS' public CUDA dependencies

`projects/hipblas/library/src/CMakeLists.txt:68-72,116-125,183-197`

**Proposed fix:** [`935f483`](https://github.com/newling/rocm-libraries/commit/935f483aba1fa2ee08de74c5d31b5f551e016103)

The CUDA target now exposes `hip::host`, `CUDA::cublas`, and `CUDA::cudart` through `PUBLIC` linkage. The generated `hipblas-config.cmake` calls `find_dependency(HIP)` and `find_dependency(hipblas-common)`, but it never calls `find_dependency(CUDAToolkit)`. A consumer that has not already loaded CUDAToolkit therefore imports a target whose interface names two undefined targets.

Add CUDAToolkit to the CUDA export dependencies and make the installed config select the NVIDIA form of the HIP package before importing `hip::host`. Validate an install followed by a separate minimal consumer that calls only `find_package(hipblas CONFIG REQUIRED)` and links `roc::hipblas`; the consumer must not need to discover HIP or CUDAToolkit itself.

### Forward hipSOLVER's documented `--cuda` option

`projects/hipsolver/install.sh:438-444,606-629,687-697`

**Proposed fix:** [`0565315`](https://github.com/newling/rocm-libraries/commit/05653158e4cdb7eb14b5f1c08846385f4150c708)

The parser sets `build_cuda=true`, but the configure command never receives that value. Lines 628-629 say that `rmake.py` passes `USE_CUDA`, but this script invokes CMake directly and hipSOLVER's `rmake.py` has no CUDA option. A configure-command probe for `install.sh --cuda` emitted only the build type, package prefix, and ROCm path; it contained neither `-DUSE_CUDA=ON` nor the old platform setting. The documented driver therefore builds the default AMD backend after installing CUDA dependencies.

Append `-DUSE_CUDA=ON` to `cmake_common_options` when `build_cuda` is true, and add a command-construction test for both values. Exercise the driver in the CUDA precheckin instead of passing `-DHIP_PLATFORM=nvidia` directly, because the current job bypasses the broken path.

### Keep the HIP version in shared Tensile's package scope

`shared/tensile/Tensile/Source/CMakeLists.txt:67-69` and `shared/tensile/Tensile/cmake/TensileConfig.cmake:223-236`

**Proposed fix:** [`8cbb672`](https://github.com/newling/rocm-libraries/commit/8cbb672001779f1f42f75b9de4aa2910aba2c4cc)

Changing `hip_VERSION` to `HIP_VERSION` fixes the spelling but not the scope. `find_package(HIP)` runs inside the `Source` subdirectory, so its normal `HIP_VERSION` variable does not return to the parent scope where `TensileCreateLibraryFiles()` is defined and called. A minimal consumer using only `find_package(Tensile ... HIP)` reported a populated version in the child and an empty value in the caller, then generated `ROCM_VERSION=`.

This is masked when a parent project separately finds HIP or when the Python fallback sees a system installation. A relocatable consumer that selects HIP through `CMAKE_PREFIX_PATH`, keeps its compiler off `PATH`, and relies on the Tensile package still receives no version. Capture the package version in the same scope as `TensileCreateLibraryFiles()`, pass it explicitly out of the child, or make the function accept the selected version. Add a CMake-level test that inspects the generated command without requiring the caller to invoke `find_package(HIP)` a second time.

### Use the same HIP build version in every TensileLite entry point

`projects/hipblaslt/tensilelite/Tensile/Common/GlobalParameters.py:942-967`, `projects/hipblaslt/tensilelite/Tensile/TensileCreateLibrary/Run.py:62,1129`, `projects/hipblaslt/tensilelite/Tensile/Toolchain/Component.py:115-170`, `projects/hipblaslt/tensilelite/Tensile/CustomKernels.py:109-125`, and `projects/hipblaslt/tensilelite/Tensile/Toolchain/HelperKernelCache.py:45-56`

**Proposed fix:** [`1296903`](https://github.com/newling/rocm-libraries/commit/1296903d9ea89f6e38e548d8dfce35a79419ea4a)

The main TensileLite library-generation path still calls `assignGlobalParameters()`, whose independent version block executes `hipcc --version`. With `ROCM_VERSION=6.4.43482` and `hipcc` absent from `PATH`, a direct call logs the missing-program warning and leaves `globalParameters["HipClangVersion"]` at `0.0.0`. The pull request therefore removes one validated tool tuple but does not remove the active version query from the same component.

The new resolver has a second representation problem. When only `.info/version` exists, it returns a ROCm release such as `6.4.3` while its return value is documented and consumed as a HIP compiler build version. `supportsUserSgprKernargPreload()` rejects `6.4.3` but accepts the corresponding HIP build `6.4.43482`, and the value also contributes to the helper-kernel cache key. The new source ordering protects normal prefixes that contain `share/hip/version` or `hip_version.h`, but the release-file fallback still changes behavior instead of reporting that the required build number is unavailable.

Route one resolved HIP build version through `Component` and `GlobalParameters`, remove the remaining `hipcc` subprocess, and either reject a release-only `.info/version` value or change the downstream decisions so they do not interpret its patch field as a compiler build number. Add direct tests for conflicting sources, `HIP_PATH`, the `share/hip/version` format, prerelease strings, a missing `hipcc`, and the ROCm 6 preload decision. The current environment-priority test removes the competing roots, so it does not test the documented priority order.

### Restore the unrelated coverage floors

`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/coverage-baseline.json:136-139`

**Proposed fix:** [`a1b76cd`](https://github.com/newling/rocm-libraries/commit/a1b76cd39fd7fec73a64f67d4a7c9db4264a4855)

The pull request raises `Component.py` to 99.54%, but it still lowers `Assembly.py` from 96.97% to 95.38%, `HelperKernelCache.py` from 99.16% to 99.14%, and `Source.py` from 97.75% to 97.73%. None of those three production files changes in this pull request, and current `develop` retains the higher values. Restore those thresholds. Lowering unrelated test gates to absorb changed suite behavior violates the repository rule against weakening tests to obtain a passing run.

## Suggestions

### Keep the selected CUDA executable and root consistent

`projects/hipblas/rmake.py:343-355`

**Proposed fix:** [`7dbddaa`](https://github.com/newling/rocm-libraries/commit/7dbddaafe7d9dfe5b11969bb02786990fec56a1c)

When `/usr/local/cuda/bin/nvcc` is absent, the script accepts `nvcc` from `PATH` but continues to pass `CUDAToolkit_ROOT=/usr/local/cuda`. A command-construction probe with `$CUDA_ROOT/bin/nvcc` on `PATH` produced `CMAKE_CUDA_COMPILER=$CUDA_ROOT/bin/nvcc` alongside `CUDAToolkit_ROOT=/usr/local/cuda`. Derive the root from the selected executable when the fallback wins. Also remove the stale legacy-`FindCUDA` comment at `projects/hipblas/library/src/CMakeLists.txt:121-123` now that the target uses `FindCUDAToolkit`.

### Update the title and description to match the current evidence

The title is not in the component's required Conventional Commits form. The body now has the required sections and a valid Jira field, but it says that `USE_CUDA` takes effect in hipFFT with any compiler and that the affected paths no longer depend on `hipcc` or `hipconfig`; the probes above show otherwise. It also reports the local CUDA limitation without recording that the public CUDA jobs use legacy selectors. A pasteable current-state replacement follows; update the failure lines after correcting and rerunning those paths.

Suggested title:

```text
build: remove hipconfig from selected library paths (LCOMPILER-876)
```

Suggested description:

```markdown
JIRA ID : LCOMPILER-876

## Motivation

Shared Tensile, TensileLite, hipBLAS, hipSOLVER, and hipFFT still use legacy HIP tools to discover a compiler version or choose the AMD and CUDA backends. This change replaces those direct queries with CMake inputs and version metadata while preserving each component's existing backend behavior.

## Technical Details

- Shared Tensile and TensileLite accept the HIP build version from CMake, then search `share/hip/version` and `include/hip/hip_version.h` for standalone use.
- TensileLite removes `hipconfig` from its validated tool list.
- hipBLAS, hipSOLVER, and hipFFT use `USE_CUDA` as the explicit backend choice.
- hipBLAS uses CMake's CUDAToolkit targets. The required CMake 3.17 minimum landed separately in [#11988](https://github.com/ROCm/rocm-libraries/pull/11988).
- Python-package installation selection remains in [#11023](https://github.com/ROCm/rocm-libraries/pull/11023).
- Review follow-up work is tracked in [#12379](https://github.com/ROCm/rocm-libraries/pull/12379).

## Device / Architecture Coverage

The backend changes require AMD and CUDA configure, build, and test lanes for hipBLAS, hipSOLVER, and hipFFT. Version discovery can change custom-kernel metadata on gfx942 and gfx950, so those architectures require shared automated coverage after the final version change.

## Test Plan

- Test version parsing, source priority, missing-source behavior, and the ROCm 6 patch-sensitive decision in both Tensile implementations.
- Configure each library with `HIP_PLATFORM` unset and `USE_CUDA` both off and on.
- Run the supported hipBLAS and hipSOLVER build drivers with their CUDA options.
- Install CUDA hipBLAS and configure a separate consumer using only `find_package(hipblas)`.
- Run the AMD and CUDA component precheckins and the affected hipBLASLt architecture lanes.

## Test Result

- The current AMD and CUDA component precheckins pass.
- The current CUDA jobs still provide `HIP_PLATFORM=nvidia` or `BUILD_WITH_LIB=CUDA`; clean `USE_CUDA` validation is pending.
- The TensileLite unit/coverage lane and the shared-Tensile unit, integration, and static-analysis lanes pass.
- The hipBLASLt preliminary lane passes on gfx90a, gfx942, gfx950, gfx12, and the two-device gfx950 configuration.
- The gfx90a AddressSanitizer test needs a rerun after its runner stopped without producing a test result.
- The rocJITsu sidecar dependency failure is tracked in [#12425](https://github.com/ROCm/rocm-libraries/pull/12425).

## Adjacent Tests Considered

The final change needs configure assertions with the legacy environment unset, command-construction tests for the supported build drivers, a CUDA hipBLAS installed-package consumer, a standalone `find_package(Tensile)` consumer, and a ROCm 6 release-only version case. These cases distinguish the new interface from the legacy settings that current automation still supplies.

## Flags / Guardrails

`USE_CUDA` defaults to `OFF`. The default selects AMD; `ON` must select CUDA without relying on `HIP_PLATFORM` from the environment.

## Related

- Work tracking: LCOMPILER-876
- Version-dependent custom-kernel behavior: [#10230](https://github.com/ROCm/rocm-libraries/pull/10230)
- Python installation model: [#11023](https://github.com/ROCm/rocm-libraries/pull/11023)
- CMake 3.17 prerequisite: [#11988](https://github.com/ROCm/rocm-libraries/pull/11988)
- Review fixes: [#12379](https://github.com/ROCm/rocm-libraries/pull/12379)

## Submission Checklist

- [x] Look over the contributing guidelines at https://github.com/ROCm/TheRock/blob/main/GOVERNANCE.md#pull-requests.

## Risk level

High (4/5): this changes version discovery and AMD/CUDA build selection across five components. The affected component lanes must pass using the new inputs rather than legacy environment values before merge.
```

## Commentary

The prior discussion materially changed the branch. The CMake minimum was isolated and merged through #11988; Python-SDK discovery stayed in #11023; the validator model and lint failure were corrected; and all 12 inline threads are now marked resolved. The current head was then force-updated and gained four additional fix commits after the revision covered by the previous review. The most recent approval targets that earlier revision, while the current GitHub state remains changes requested.

The change classes are build/CI, defect fix, and version-dependent kernel-generation behavior. Host unit tests are the right level for parsing and source ordering; configure, driver, install-consumer, and CUDA component jobs are required for backend changes; and shared gfx942/gfx950 coverage is appropriate because the version can control emitted custom-kernel metadata. No waiver is declared, and the missing clean-selector and package-consumer coverage is not safe to waive. The adjacent cases that matter are an unset legacy environment, each supported build driver, an installed CUDA package, a relocatable Tensile consumer, and a ROCm 6 installation that exposes only its release version.

The branch is 26 commits behind current `develop`. The only changed-file overlap is the TensileLite coverage-baseline file, not a high-coupling generator file, so the component's mandatory stale-base rule does not apply. Rebasing before the next test cycle is still useful because it will expose the current baseline values directly.

## Appendix: focused probes

### HIP package backend selection

The installed HIP config package executes `hipconfig` if the CMake variable `HIP_PLATFORM` is absent:

```cmake
cmake_minimum_required(VERSION 3.17)
project(hip_package_probe LANGUAGES CXX)
find_package(hip CONFIG REQUIRED PATHS "$ENV{ROCM_PATH}")
get_target_property(HIP_HOST_DEFINITIONS hip::host INTERFACE_COMPILE_DEFINITIONS)
message(STATUS "HIP_PLATFORM=${HIP_PLATFORM}")
message(STATUS "HIP_HOST_DEFINITIONS=${HIP_HOST_DEFINITIONS}")
```

Configure it with:

```bash
env -u HIP_PLATFORM strace -f -e trace=execve \
  cmake -S "$BUILD_DIR/hip-package-probe" -B "$BUILD_DIR/hip-package-probe/build" -G Ninja
```

The trace contains `hipconfig --platform`; on the tested AMD installation the messages are `HIP_PLATFORM=amd` and `HIP_HOST_DEFINITIONS=__HIP_PLATFORM_AMD__=1`. Passing `-DHIP_PLATFORM=nvidia` removes the `hipconfig` execution.

For configure-only hipBLAS and hipSOLVER probes without a CUDA installation, these minimal find modules were used:

```cmake
# modules/FindCUDAToolkit.cmake
set(CUDAToolkit_FOUND TRUE)
foreach(component IN ITEMS cublas cudart)
  if(NOT TARGET CUDA::${component})
    add_library(CUDA::${component} INTERFACE IMPORTED)
  endif()
endforeach()

# modules/FindCUDA.cmake
set(CUDA_FOUND TRUE)
set(CUDA_VERSION_STRING "12.0")
set(CUDA_INCLUDE_DIRS "$ENV{ROCM_PATH}/include")
set(CUDA_cusolver_LIBRARY "m")
set(CUDA_LIBRARIES "m")

# hipblas-common/hipblas-common-config.cmake
if(NOT TARGET roc::hipblas-common)
  add_library(roc::hipblas-common INTERFACE IMPORTED)
endif()
set(HIPBLAS-COMMON_INCLUDE_DIRS "")
```

Configure with `HIP_PLATFORM` unset:

```bash
env -u HIP_PLATFORM cmake -S "$SRC_DIR/projects/hipblas" -B "$BUILD_DIR/hipblas" -G Ninja \
  -DUSE_CUDA=ON -DBUILD_WITH_SOLVER=OFF -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_MODULE_PATH="$BUILD_DIR/modules" \
  -Dhipblas-common_DIR="$BUILD_DIR/hipblas-common"

env -u HIP_PLATFORM cmake -S "$SRC_DIR/projects/hipsolver" -B "$BUILD_DIR/hipsolver" -G Ninja \
  -DUSE_CUDA=ON -DBUILD_FORTRAN_BINDINGS=OFF -DBUILD_HIPSPARSE_TESTS=OFF \
  -DBUILD_WITH_SPARSE=OFF -DHIPSOLVER_INTERNAL_LAPACK_BUILD=OFF \
  -DCMAKE_CXX_COMPILER=g++ -DCMAKE_MODULE_PATH="$BUILD_DIR/modules"
```

The generated hipBLAS and hipSOLVER compile rules contain both AMD and NVIDIA platform definitions. The generated CUDA `hipblas-config.cmake` contains `find_dependency(HIP)` and `find_dependency(hipblas-common)`, while `hipblas-targets.cmake` names `CUDA::cublas` and `CUDA::cudart`.

### hipFFT selector

```bash
env -u HIP_PLATFORM cmake -S "$SRC_DIR/projects/hipfft" -B "$BUILD_DIR/hipfft" -G Ninja \
  -DUSE_CUDA=ON -DBUILD_CLIENTS=OFF -DCMAKE_CXX_COMPILER=g++
grep -E '^(USE_CUDA|BUILD_WITH_LIB|BUILD_WITH_COMPILER):' "$BUILD_DIR/hipfft/CMakeCache.txt"
```

Observed values:

```text
BUILD_WITH_LIB:STRING=ROCM
USE_CUDA:BOOL=ON
BUILD_WITH_COMPILER:INTERNAL=HOST-default
```

### hipSOLVER driver

Run the driver from an empty directory with shell functions that record CMake arguments and suppress the build:

```bash
function cmake { printf 'CMAKE_ARGS'; printf ' <%s>' "$@"; printf '\n'; }
function make { return 0; }
export -f cmake make
bash "$SRC_DIR/projects/hipsolver/install.sh" --cuda
```

The emitted argument list contains no `-DUSE_CUDA=ON`.

### Shared-Tensile CMake scope

```cmake
cmake_minimum_required(VERSION 3.17)
project(tensile_scope_probe LANGUAGES CXX)
set(HIP_PLATFORM amd)
find_package(Tensile 4.48.0 EXACT REQUIRED HIP LLVM
             PATHS "${Tensile_ROOT}/cmake" NO_DEFAULT_PATH)
message(STATUS "CALLER_HIP_VERSION=${HIP_VERSION}")
TensileCreateLibraryFiles(
  "${CMAKE_CURRENT_SOURCE_DIR}/logic"
  "${CMAKE_CURRENT_BINARY_DIR}/output"
  ARCHITECTURE gfx942)
```

Configure with `TENSILE_SKIP_LIBRARY=1` and `-DTensile_ROOT=$SRC_DIR/shared/tensile/Tensile`. The output contains `CALLER_HIP_VERSION=` and a `Tensile_CREATE_COMMAND` element of `ROCM_VERSION=`.

### TensileLite version paths

Run from the TensileLite root:

```bash
PATH=/nonexistent ROCM_VERSION=6.4.43482 PYTHONPATH=. "$VENV/bin/python" - <<'PY'
from Tensile.Common.GlobalParameters import assignGlobalParameters, globalParameters

assignGlobalParameters({}, {})
print(globalParameters["HipClangVersion"])
PY
```

This prints a missing-`hipcc` warning followed by `0.0.0`.

The release-versus-build fallback is reproduced by:

```python
import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as root:
    info = Path(root, ".info")
    info.mkdir()
    (info / "version").write_text("6.4.3")
    os.environ.pop("ROCM_VERSION", None)
    os.environ.pop("HIP_PATH", None)
    os.environ["ROCM_PATH"] = root

    from Tensile.Common import SemanticVersion
    from Tensile.CustomKernels import supportsUserSgprKernargPreload
    from Tensile.Toolchain.Component import get_rocm_version

    release = get_rocm_version()
    assert not supportsUserSgprKernargPreload(release)
    assert supportsUserSgprKernargPreload(SemanticVersion(6, 4, 43482))
```
