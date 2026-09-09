> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#7235](https://github.com/ROCm/rocm-libraries/pull/7235)

**Review focus:** Proposed division of updated head `e257fdc9eb5` into independently reviewable changes.

## Tests

This scope review uses the current diff, new public review threads, focused local configuration probes, and public CI. The focused ToolchainComponent tests pass locally (24/24), AMD and CUDA `rmake.py` command construction passes, AMD CMake configuration passes, and public hipBLAS AMD and CUDA precheckin pass. No additional broad tests were run solely to determine PR boundaries.

## Summary

Requiring CMake 3.17 is a reasonable modernization because the new hipBLAS CUDA implementation uses `FindCUDAToolkit`, which first appeared in CMake 3.17. That does not make the version bump part of the Tensile/TensileLite version-detection change: it is a compatibility consequence of the separate hipBLAS backend migration.

The current PR contains three contracts with different consumers and validation requirements:

| Proposed PR | Contract | Main scope | Validation boundary |
|---|---|---|---|
| 1. Raise the hipBLAS CMake floor | hipBLAS requires and provisions CMake 3.17 consistently | Top-level and client CMake declarations, `install.sh`, Linux and Windows install guides | Supported-OS dependency installation plus AMD and CUDA configure smoke tests using the new minimum |
| 2. Remove the Tensile/TensileLite `hipconfig` version dependency | Version discovery no longer treats `hipconfig` as a toolchain component | `shared/tensile`, `projects/hipblaslt/tensilelite`, their CMake version handoffs and direct tests; the simple AMD-only hipSOLVER script change can remain here | Version-source precedence, prerelease parsing, missing/fallback behavior, relocatable installs, and rocBLAS/hipBLASLt consumers |
| 3. Modernize the hipBLAS backend selector | `USE_CUDA` selects the CUDA implementation and CUDAToolkit target graph without relying on ambient `HIP_PLATFORM` | The remaining `projects/hipblas` CMake, driver, install, client, export, packaging, and backend documentation changes | AMD and CUDA configure/build/install, CUDA with `HIP_PLATFORM` unset, and minimal installed-package consumers |

PR 1 is a prerequisite for PR 3. PR 2 is independent and can be reviewed and merged without either hipBLAS change. This ordering makes the accepted CMake modernization explicit while keeping it out of the ROCm-version behavior review.

## Actionable items

1. **Split the change by contract — `projects/hipblas/CMakeLists.txt:22-92`, `projects/hipblas/clients/CMakeLists.txt:22-23`, `projects/hipblas/install.sh:209,529-542`, the hipBLAS install guides, `shared/tensile/Tensile/cmake/TensileConfig.cmake:235`, and the associated Tensile/TensileLite sources and tests.**

   Start the CMake-floor PR from `develop` and update every declaration, installer threshold/download, and documented minimum together. Start the version/toolchain PR independently from `develop` and omit all hipBLAS backend and CMake-floor changes. Base the hipBLAS backend PR on the CMake-floor PR and omit the Tensile/TensileLite version changes. Give each PR its own motivation and test results instead of describing all three as one repository-wide `hipconfig` removal.

2. **Keep each resulting PR internally complete.**

   The version PR should include the shared-Tensile `HIP_VERSION` handoff and direct precedence/fallback/prerelease tests, because those establish whether replacing `hipconfig --version` is correct. The backend PR should make `USE_CUDA` sufficient when `HIP_PLATFORM` is absent and should carry the CUDAToolkit export/consumer requirements. The CMake-floor PR should update `projects/hipblas/docs/install/Linux_Install_Guide.rst:150`, `projects/hipblas/docs/install/Windows_Install_Guide.rst:159`, and both 3.16.8 installer checks rather than changing only `cmake_minimum_required`.

## Suggestions

1. **Two-PR alternative — combine PRs 1 and 3 when a three-PR sequence is not practical.**

   The two-PR division is:

   - a Tensile/TensileLite version-and-toolchain PR, including the simple hipSOLVER AMD default; and
   - a hipBLAS backend PR containing `USE_CUDA`, CUDAToolkit, the accepted CMake 3.17 floor, installer/documentation updates, exports, clients, and AMD/CUDA validation.

   Do not combine the CMake floor with the version PR: no version-resolution code requires CMake 3.17.

2. **Existing follow-up work — use [ROCm/rocm-libraries#11808](https://github.com/ROCm/rocm-libraries/pull/11808) as a source of commits, not as the final review unit.**

   Its three commits already approximate the seams: version handoff/tests, CUDA package discovery, and the CMake floor. They can be transplanted into the independently based PRs above after resolving the remaining backend-selection and installer consistency issues.

## Commentary

The new public review threads support this division. One identifies the CMake bump and CUDA work as unrelated to ROCm version reading; another points out that the installer still provisions 3.16.8 and recommends handling the supported CMake floor before the CUDA migration. Accepting CMake 3.17 resolves the product decision, but it does not collapse the contracts: dependency provisioning, version-source behavior, and backend selection still have different owners, failure modes, and test matrices.

This organization also matches the approach used by [ROCm/rocm-libraries#11377](https://github.com/ROCm/rocm-libraries/pull/11377) and [ROCm/rocm-libraries#11380](https://github.com/ROCm/rocm-libraries/pull/11380): isolate one class of conditional or configuration behavior, retain genuine selectors, and attach focused evidence to the boundary being changed.
