> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#7235](https://github.com/ROCm/rocm-libraries/pull/7235)

**Assessment:** Changes requested

**Scope:** head `793d9cffdaa`

## Tests

Local smoke validation reproduced the hipBLAS `rmake.py` failure and the empty shared-Tensile CMake version handoff; `git diff --check` passed. Public CI passed 7,124 TensileLite Python tests, but both AMD and CUDA hipBLAS precheckin builds stop at the same `NameError`; the TensileLite C++ run passed 726 of 727 enabled tests, with one unrelated Stream-K expectation failure.

No CUDA build was attempted locally because this host has no CUDA toolkit. The public CUDA job also cannot reach CMake until the `rmake.py` failure below is fixed, so the new CUDAToolkit path currently has no successful build evidence.

## Summary

The Tensile and TensileLite part of the change removes `hipconfig` from toolchain validation and replaces its version query with an explicit CMake-provided version plus installation-file fallbacks. That is a good direction: the version is configuration data, not an executable toolchain component, and the four remaining compiler/bundler components form a clearer validation contract.

The hipBLAS portion is broader. In addition to eliminating `hipconfig --platform`, it promotes `USE_CUDA` to the backend-selection interface and replaces the legacy `FindCUDA` flow with `FindCUDAToolkit`. Making the backend a first-class CMake option is preferable to an ambient environment switch, but the new interface is not yet propagated consistently through the Python driver or CUDA target usage requirements.

## Actionable items

1. **Must address before merge — `projects/hipblas/rmake.py:343-345,404`: pass the backend choice into `config_cmd`.**

   `main()` assigns `use_cuda_backend` as a local variable, while `config_cmd()` reads that name without receiving it or declaring it global. Consequently every normal AMD and CUDA invocation reaches line 345 and raises `NameError: name 'use_cuda_backend' is not defined` before CMake starts. This is reproduced locally and is the cause recorded by both hipBLAS precheckin jobs. Pass `args.use_cuda` or an explicit boolean parameter into `config_cmd`, and add a smoke test that exercises command construction for both backends.

2. **Must address before merge — `shared/tensile/Tensile/cmake/TensileConfig.cmake:235`: inject the version variable produced by this package lookup.**

   Shared Tensile calls `find_package(HIP ...)` in `Tensile/Source/CMakeLists.txt`, which defines `HIP_VERSION`; it does not define lowercase `hip_VERSION`. A focused configure probe against the installed HIP package reported `HIP_VERSION=7.1.25424` and an empty `hip_VERSION`, so this command currently exports `ROCM_VERSION=`. Standard `/opt/rocm` installations happen to fall through to `.info/version`, but relocatable installations found through `CMAKE_PREFIX_PATH` can fail version discovery entirely, and the fallback can report a different patch/build version than the HIP package. Use `HIP_VERSION` here (or normalize the package version once under an intentionally named project variable), and cover the generated command in a CMake-level regression test.

3. **Must address before merge — `projects/hipblas/CMakeLists.txt:84-91`, `projects/hipblas/library/src/CMakeLists.txt:114-128`, `projects/hipblas/clients/benchmarks/CMakeLists.txt:91-97`, `projects/hipblas/clients/gtest/CMakeLists.txt:176-182`, and `projects/hipblas/clients/samples/CMakeLists.txt:109-117`: complete the CUDAToolkit target migration before removing HIP/FindCUDA discovery.**

   `find_package(CUDAToolkit)` provides `CUDAToolkit_INCLUDE_DIRS` and imported targets such as `CUDA::cublas`; it does not populate the legacy `CUDA_INCLUDE_DIRS` or `CUDA_LIBRARIES` variables that the three client CMake files still consume. The new CUDA branch also skips `find_package(hip)`, leaving `HIP_INCLUDE_DIRS` empty even though `hipblas.h` publicly includes `hip/hip_runtime_api.h` and, under `__HIP_PLATFORM_NVCC__`, `cublas_v2.h`. `CUDA::cublas` is linked privately only to the library, so its include usage requirements do not repair client compilation. Discover the HIP headers explicitly, replace the remaining legacy CUDA variables with the appropriate CUDAToolkit imported targets or result variables, and ensure the public header's requirements reach every client target. Rerun the CUDA precheckin after item 1 so this path is actually configured and compiled.

4. **Important — `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/ToolchainComponent/test_toolchain_component_char.py:82-114` and `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/coverage-baseline.json`: test the new version-source contract instead of lowering its coverage baseline.**

   The environment test removes both filesystem roots, so despite its docstring it does not prove that `ROCM_VERSION` wins over conflicting file values. The file test covers only `ROCM_PATH`; it does not cover fallback ordering, unreadable/missing files, the documented error, or the newly added alpha/RC parsing. Those are the boundary cases of the new low-level resolver, and the patch simultaneously lowers `Component.py`'s baseline from 99.19% to 94.63%. Add direct precedence, fallback/error, and pre-release-format cases and retain the existing coverage expectation rather than accepting the uncovered configuration paths.

## Suggestions

1. **PR scope — split this into two orthogonal PRs.**

   The first PR should contain the Tensile and TensileLite version/toolchain cleanup: replace the `hipconfig --version` query, remove `HIP_CONFIG` and `supportedHip` from validation, update the corresponding Python tests and mocks, and make the straightforward hipSOLVER AMD default change. Its validation boundary is version-source precedence and parsing in both Python implementations, plus CMake command construction for standard and relocatable ROCm installations.

   The second PR should contain the hipBLAS backend migration: replace `HIP_PLATFORM` with the `USE_CUDA` option, move package discovery and linkage from legacy `FindCUDA` variables to `FindCUDAToolkit` targets, update `rmake.py` and `install.sh`, and update the CUDA documentation. Its validation boundary is an independently green configure, library build, client build, and install/package path for both AMD and CUDA.

   These changes share the broad goal of retiring legacy HIP tooling, but neither implementation depends on the other. Splitting them would allow the version/toolchain removal to land after focused Tensile validation while the CUDA backend contract is reviewed and tested separately.

## Commentary

This change is adjacent to the recent hipBLASLt/TensileLite preprocessor-removal PRs, but it is not just another dead-branch deletion. Those PRs classified conditions before removing them: compile-time-dead alternatives were deleted, genuine architecture/device selectors were retained, and the one changed device predicate received a focused compile probe. This PR makes a similarly useful move by replacing ambient `HIP_PLATFORM` selection with a CMake option, but then crosses a configuration boundary: package discovery, Python command construction, and target usage requirements all have to agree on that option and its derived values.

The version resolver also appears twice, in shared Tensile and TensileLite. If keeping the implementations separate is necessary for packaging, keep their source priority, parsing behavior, exception contract, and tests deliberately parallel. Otherwise this cleanup trades one external query for two copies of configuration policy that can drift.
