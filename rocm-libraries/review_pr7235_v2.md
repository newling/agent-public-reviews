> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#7235](https://github.com/ROCm/rocm-libraries/pull/7235)

**Proposed fixes:** [ROCm/rocm-libraries#11634](https://github.com/ROCm/rocm-libraries/pull/11634) is a draft follow-up targeting this PR's branch. The PR has incorporated the Python scope fix and part of its target-based CUDA linkage, but the backend discovery/export and version-resolution fixes described below remain there for reference.

**Assessment:** Changes requested

**Scope:** follow-up review of head `7444925cb6b`

## Tests

Local `rmake.py --help`, shell syntax, and diff-whitespace checks passed; a focused CMake probe reported `HIP_VERSION=7.1.25424` and an empty `hip_VERSION`. Public CI passed the AMD hipBLAS precheckin and all 6,997 TensileLite Python tests, while the CUDA hipBLAS precheckin fails during CMake generation because `hip::host` is undefined. The TensileLite coverage job's tests pass, but its ratchet currently fails on an unrelated `LdsPadding.py` baseline change. No local CUDA build was attempted because this host has no CUDA toolkit.

## Summary

The two commits added since the first review fix the unconditional `rmake.py` `NameError` and replace the remaining legacy `FindCUDA` variables with imported targets. Those are useful corrections: the AMD hipBLAS precheckin now reaches a successful build, and expressing CUDA include/link requirements through targets is the right direction.

The CUDA target migration is still incomplete, however. The latest commit makes HIP and CUDA targets part of hipBLAS' usage requirements without arranging for all of those targets to exist at build and package-consumer time. Public CUDA CI confirms the first failure. The shared-Tensile version handoff and the direct tests for the new version-source policy are unchanged from the first review.

## Actionable items

1. **Must address before merge — `projects/hipblas/CMakeLists.txt:84-92`, `projects/hipblas/rmake.py:343-355`, and `projects/hipblas/library/src/CMakeLists.txt:69-72,116-121,180-194`: complete the target-based CUDA package contract.**

   The CUDA branch calls only `find_package(CUDAToolkit)`, but the library and every CUDA client now link `hip::host`. Public CUDA precheckin therefore stops during generation with `Target "hipblas" links to: hip::host but the target was not found`, followed by the same error for the clients. Load the HIP config package on both backends and set the CMake `HIP_PLATFORM` variable from `USE_CUDA` before doing so; otherwise HIP's config package can itself invoke `hipconfig` to select a backend. Because `CUDA::cublas` and `CUDA::cudart` are public requirements of the exported library, also add `CUDAToolkit` to the CUDA export dependencies so an installed consumer recreates those targets. Finally, pass `CUDAToolkit_ROOT` rather than the obsolete `FindCUDA` spelling `CUDA_TOOLKIT_ROOT_DIR`; the current CUDA job explicitly warns that the latter is unused. Validate configure, build, install, and a minimal installed-package consumer on the CUDA lane.

2. **Must address before merge — `projects/hipblas/CMakeLists.txt:23,87`, `projects/hipblas/install.sh:209,529-541`, and `projects/hipblas/docs/install/Linux_Install_Guide.rst:150-151`: raise the supported CMake version or avoid `FindCUDAToolkit`.**

   `FindCUDAToolkit` was added in CMake 3.17, but hipBLAS still declares 3.5, documents 3.16.8, and its `--cmake_install` path installs exactly 3.16.8. A user following that supported path cannot configure the new CUDA branch because the requested module does not exist. Make the declared, documented, and installer-enforced minimum at least 3.17 (preferably the repository's actual supported floor), or retain a compatible discovery mechanism for older CMake.

3. **Must address before merge — `shared/tensile/Tensile/cmake/TensileConfig.cmake:235`: inject the version variable produced by this package lookup.**

   Shared Tensile calls `find_package(HIP ...)` in `Tensile/Source/CMakeLists.txt`, which defines `HIP_VERSION`; it does not define lowercase `hip_VERSION`. A focused configure probe against the installed HIP package reports `HIP_VERSION=7.1.25424` and `hip_VERSION=`. The generated command therefore exports an empty `ROCM_VERSION`. Standard `/opt/rocm` installations happen to fall through to `.info/version`, but relocatable installations found through `CMAKE_PREFIX_PATH` can fail version discovery entirely, and the fallback can report a different patch/build version than the selected HIP package. Use `HIP_VERSION` here and cover the generated command in a CMake-level regression test.

4. **Important — `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/ToolchainComponent/test_toolchain_component_char.py:82-114` and `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/coverage-baseline.json:129`: test the new version-source contract instead of lowering its coverage baseline.**

   The environment test removes both filesystem roots, so despite its docstring it does not prove that `ROCM_VERSION` wins over conflicting file values. The file test covers only `ROCM_PATH`; it does not cover `ROCM_PATH`/`HIP_PATH` ordering, fallback after a missing or unreadable file, the documented no-source error, or the newly added alpha/RC parsing. Those are the boundaries of the new low-level resolver, and the patch simultaneously lowers `Component.py`'s baseline from 99.19% to 94.63%; Codecov reports only 57.14% patch coverage for that file. Add direct precedence, fallback/error, and pre-release-format cases and retain the prior coverage expectation.

## Suggestions

1. **PR title and description — update the narrative to match the final diff and current validation.**

   The description still claims a `rocm_sdk.__version__` fallback even though that code was removed, says all functional `hipconfig` dependencies in rocm-libraries are gone even though hipRAND and rocRAND still execute `hipconfig --cpp_config`, and reports the CUDA build as unaffected despite the current failing CUDA precheckin. It also describes platform hardcoding rather than the final `USE_CUDA`/`FindCUDAToolkit` migration. Narrow the repository-wide claim, describe both actual change sets, and update the test plan/results.

2. **PR scope — consider separating the version/toolchain cleanup from the hipBLAS backend migration.**

   Removing `hipconfig` from Tensile/TensileLite has a version-source and parsing validation boundary; replacing hipBLAS backend selection has a configure, usage-requirement, packaging, and AMD/CUDA build boundary. Neither implementation depends on the other, and the current cross-project PR makes it harder to distinguish successful version cleanup from a failing backend migration.

## Commentary

The follow-up correctly uses `args.use_cuda` where the previous patch referenced an out-of-scope local, and public AMD CI verifies that ordinary `rmake.py` configuration is no longer blocked. Moving away from `${CUDA_INCLUDE_DIRS}` and `${CUDA_LIBRARIES}` is also the right architectural choice; imported targets just need to be discovered and exported consistently across the entire build/install boundary.

The version resolver still appears twice, in shared Tensile and TensileLite. If keeping the implementations separate is necessary for packaging, keep their source priority, parsing behavior, exception contract, and tests deliberately parallel. Otherwise this cleanup trades one external query for two copies of configuration policy that can drift.
