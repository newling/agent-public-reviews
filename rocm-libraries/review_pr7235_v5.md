> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#7235](https://github.com/ROCm/rocm-libraries/pull/7235)

**Scope:** head `72ed87b06b7`

## Tests

The 71 focused ToolchainComponent, ToolchainValidators, and validator-surface characterization tests pass locally, as does `git diff --check`; two focused resolver probes reproduce a version-contract change and a failure in the new PATH-derived-root fallback. Current public status reports failing CUDA precheckins for hipBLAS, hipFFT, and hipSOLVER, failing TensileLite coverage checks, and several pending Math CI jobs.

## Summary

Removing `hipconfig` from TensileLite's toolchain tuple remains a useful and independently mergeable cleanup. The current PR is moving away from that reviewable unit: its latest commits retain the hipBLAS backend migration, add parallel hipFFT and hipSOLVER backend migrations, and add another untested version-discovery heuristic. The PR now changes 32 files across several projects and has requested changes outstanding.

The latest fallback also uses the wrong version source for the existing TensileLite contract. On a standard installation, `.info/version` reports the ROCm release `7.1.0`, while both `hipconfig --version` and the installed HIP package report the HIP build version `7.1.25424`. TensileLite consumes that patch field in compatibility decisions and cache identity. The installed `hipconfig` binary identifies `share/hip/version` and its `HIP_VERSION_MAJOR`, `HIP_VERSION_MINOR`, and `HIP_VERSION_PATCH` fields as its source, so the behavior can be preserved without executing `hipconfig`.

A fresh, hipBLASLt-owned PR based on current `develop` is the shortest route to landing the TensileLite cleanup. It should not copy the current resolver verbatim, and it should leave Python-SDK installation selection to the existing dedicated stack.

## Actionable items

1. **Extract the TensileLite change from the cross-project backend migrations — `projects/hipblaslt/cmake/hipblaslt_python.cmake:38-46`, `projects/hipblaslt/tensilelite/Tensile/Toolchain/Component.py:82-128`, `projects/hipblaslt/tensilelite/Tensile/Toolchain/Validators.py`, and `projects/hipblaslt/tensilelite/Tensile/TensileCreateLibrary/Run.py:1019-1025`.**

   Base an independent PR on current `develop` containing the hipBLASLt CMake handoff, removal of `HIP_CONFIG`/`supportedHip`, the four-component `validateToolchain` call, and their direct tests. Leave the hipBLAS, hipFFT, hipSOLVER, and shared-Tensile changes out of that hipBLASLt-owned unit. Those projects have separate consumers, owners, and validation matrices; the three current CUDA precheckin failures reinforce that they are not prerequisites for TensileLite's cleanup.

2. **Preserve the HIP build-version contract — `projects/hipblaslt/tensilelite/Tensile/Toolchain/Component.py:82-128`.**

   Do not use `<prefix>/.info/version` as a substitute for `hipconfig --version`. The former is a ROCm release version and can collapse `7.1.25424` to `7.1.0`. Use the CMake-provided `hip_VERSION` for configured builds and, for conventional standalone installations, parse `<prefix>/share/hip/version`'s `HIP_VERSION_MAJOR`, `HIP_VERSION_MINOR`, and `HIP_VERSION_PATCH`. Add direct tests proving source precedence, exact patch preservation, malformed/missing-file behavior, and prerelease handling. Keep Python-SDK selection out of this PR because [ROCm/rocm-libraries#11023](https://github.com/ROCm/rocm-libraries/pull/11023) owns that installation model.

3. **Remove or correct the new executable-path heuristic — `projects/hipblaslt/tensilelite/Tensile/Toolchain/Component.py:107-124` and `shared/tensile/Tensile/Common.py:2424-2437`.**

   `Path(executable).parent.parent` assumes every tool is exactly `<root>/bin/<tool>`. It looks under `<root>/lib/llvm/.info/version` for the common `<root>/lib/llvm/bin/amdclang++` layout and fails even when `<root>/.info/version` exists. The focused counterexample reproduces the documented failure. The minimal TensileLite PR can omit this heuristic: CMake provides the version for configured builds, conventional standalone prefixes provide `share/hip/version`, and the Python distribution layout belongs to the dedicated installation-model work.

4. **Make the tests describe the changed contract — `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/PublicInputSurfaceDeep/test_pchaos_Validators_L226_char.py:6-19,48-64,170-183`, `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/ToolchainComponent/test_toolchain_component_char.py:82-116`, and `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/coverage-baseline.json:129`.**

   Remove `hipcc` and `hipconfig` from the validator model and add them to the model-versus-production witnesses; production now rejects both, while the test helper still says both are supported. Add direct resolver cases instead of lowering `Component.py`'s coverage floor from 99.19% to 94.63%. The existing green tests do not cover either counterexample above.

## Commentary

Switching hipBLAS back from `FindCUDAToolkit` to legacy `FindCUDA` removes the immediate CMake-3.17 dependency but does not make the combined PR small or low risk. The current head simultaneously changes backend selection in three libraries and all three CUDA precheckins report failure. That work can proceed independently after its CUDA-support policy is decided; it should not hold the TensileLite cleanup hostage.

For shared Tensile, the analogous removal should be a separate owner-reviewed change. If it retains the current CMake route, `shared/tensile/Tensile/cmake/TensileConfig.cmake:235` must pass uppercase `HIP_VERSION`, which is what its `find_package(HIP)` call defines, and its fallback should preserve the HIP build version for the same reason as TensileLite.
