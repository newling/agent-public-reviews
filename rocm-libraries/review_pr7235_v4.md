> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#7235](https://github.com/ROCm/rocm-libraries/pull/7235)

## Tests

Focused local validation passed 59/59 changed ToolchainComponent and ToolchainValidators characterization tests, the nightly version probe, shell/Python syntax checks, diff-whitespace checks, and an AMD CMake configure; public CI ran all 6,997 TensileLite characterization/unit tests successfully and passes the AMD hipBLAS precheckin, but the exact current head fails the CUDA hipBLAS precheckin.

The public CUDA job fails during CMake generation because `hip::host` is undefined for the library and clients, and it warns that `CUDA_TOOLKIT_ROOT_DIR` is unused. An isolated configure with the supported CMake 3.16.8 fails earlier at `projects/hipblas/CMakeLists.txt:91` because that CMake release has no `FindCUDAToolkit` module. A CMake probe against the installed HIP config reports `HIP_VERSION=7.1.25424` and `hip_VERSION=`, confirming the shared-Tensile handoff below. On the same installation, the new filesystem fallback returns `7.1.0` while `hipconfig --version` returns `7.1.25424-4179531dcd`, so the fallback does not preserve the old patch/build-number semantics.

The local AMD target build stopped because the installed rocBLAS headers do not declare APIs used by the current hipBLAS source. Those source lines are unchanged by this PR, configuration succeeded, and the exact head's public AMD precheckin passes, so this is a local dependency-version mismatch rather than evidence of a PR regression. The public TensileLite coverage run completed all tests but failed an unrelated `LdsPadding.py` ratchet; Codecov separately reports 57.14% patch coverage for the changed `Toolchain/Component.py` resolver.

## Summary

The Tensile and TensileLite portion moves ROCm version discovery away from an executable toolchain component, fixes prerelease strings such as `10.1.0a20260813`, and removes `hipconfig` from validation tuples. Removing the executable dependency is a sound direction, and the current code reflects the early review decisions to leave Python-SDK discovery to the dedicated installation-model work and to update the hipBLAS build documentation. The fallback still needs an explicit version-semantics decision because `.info/version` is a ROCm release version, not the HIP compiler build version that existing consumers receive from `hipconfig` and CMake.

The current head does not, however, satisfy the reviewers' requested separation of the hipBLAS CUDA migration from the version cleanup. The author chose to move only the CMake bump to a later PR, then force-dropped all four corrective changes from the prior head—CMake 3.17, unconditional HIP discovery, `CUDAToolkit_ROOT`, and the exported CUDAToolkit dependency—while retaining `USE_CUDA`, `FindCUDAToolkit`, and the target-based CUDA implementation here. This recreates the known CUDA configuration failures and leaves the PR spanning three independently testable contracts. The version cleanup can be made reviewable on its own, but the current combined head should not land as written.

## Actionable items

1. **Complete the agreed split instead of reverting only the CUDA prerequisites — `projects/hipblas/CMakeLists.txt:22-95`, `projects/hipblas/library/src/CMakeLists.txt:68-72,188-194`, `projects/hipblas/rmake.py:343-355`, and the hipBLAS client CMake files.**

   The latest author replies move the CMake bump to a separate PR while retaining the CUDA migration here, but head `ce1d619c495` backs out the fixes that make that retained migration internally consistent. It advertises CMake 3.5 while line 91 requires a module introduced in 3.17, skips `find_package(hip)` for CUDA while the library and every client link `hip::host`, passes the legacy `CUDA_TOOLKIT_ROOT_DIR` spelling that `FindCUDAToolkit` ignores, and exports `CUDA::cublas`/`CUDA::cudart` without declaring CUDAToolkit as a package dependency. The first two failures are reproduced by CMake 3.16.8 and the current public CUDA precheckin respectively.

   Follow through on the discussion by removing the hipBLAS backend migration from this PR. Land the CMake floor as its own prerequisite, keep the Tensile/TensileLite version cleanup independently based on `develop`, and put the `USE_CUDA`/CUDAToolkit migration in a third PR based on the CMake-floor change. If the split is declined, restore all four prerequisite fixes together, update both installers and both platform guides to the actual CMake floor, and validate configure/build/install plus an installed-package consumer on CUDA. In that later backend PR, also decide whether `USE_CUDA` is supported or deprecated: the current option, command help, and guide promote it as the only selector, contrary to the author's latest reply that it remains deprecated.

2. **Pass the version variable that shared Tensile's package lookup actually defines — `shared/tensile/Tensile/cmake/TensileConfig.cmake:235`.**

   Shared Tensile calls `find_package(HIP ...)`, which defines `HIP_VERSION`; the added command exports lowercase `hip_VERSION`, which is empty. The local package probe reports exactly that casing difference. A standard `/opt/rocm` installation masks the mistake through the filesystem fallback, but a relocatable HIP package found through `CMAKE_PREFIX_PATH` can fail version discovery or silently report the unrelated system installation's version. Export `ROCM_VERSION=${HIP_VERSION}` here and add a CMake-level assertion over the generated command.

3. **Preserve the meaning of the version supplied to patch-sensitive consumers — `projects/hipblaslt/tensilelite/Tensile/Toolchain/Component.py:83-111`, `projects/hipblaslt/tensilelite/Tensile/CustomKernels.py:36-52`, `projects/hipblaslt/tensilelite/Tensile/Toolchain/HelperKernelCache.py:45-57`, and `shared/tensile/Tensile/Common.py:2413-2432`.**

   The old query and CMake's `HIP_VERSION` expose the HIP compiler build number in the patch field, while `.info/version` exposes the ROCm release patch. On the tested installation those are `7.1.25424-4179531dcd`, `7.1.25424`, and `7.1.0` respectively. This is observable beyond display: `supportsUserSgprKernargPreload` makes a ROCm-6 decision at patch `32650`, and the helper-kernel cache hashes this version. A direct standalone invocation on an official-style `6.4.3` version therefore takes the unsupported branch that a build-style `6.4.43482` version does not, and multiple compiler builds can collapse onto one cache key.

   Define whether these consumers need the ROCm release version or HIP compiler build version, then use a source that preserves that contract on standalone paths (or require an explicit `ROCM_VERSION` rather than silently substituting a different kind of version). Cover the two representations and their downstream decisions. Also extend `test_toolchain_component_char.py:82-116` with precedence against conflicting files, `HIP_PATH`, missing/unreadable fallthrough, the no-source error, and prerelease cases; add direct tests for the duplicated shared implementation; and retain the prior `coverage-baseline.json:129` expectation rather than lowering 99.19% to 94.63% while Codecov reports only 57.14% patch coverage.

4. **Make the characterization model match the validator it claims to mirror — `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/PublicInputSurfaceDeep/test_pchaos_Validators_L226_char.py:6-19,48-64,167-183`.**

   Production removed `supportedHip`, so `hipcc` and `hipconfig` are now rejected by `_validateExecutable`, but `POSIX_SUPPORTED` still contains both names and the comments still describe five predicates. The four chosen differential witnesses avoid those names, which lets the test continue claiming zero mismatches despite modeling both changed inputs incorrectly. Remove the stale entries and wording, and add `hipcc` and `hipconfig` to the real-versus-model witnesses so this API change is actually pinned.

## Suggestions

1. **Update the PR title and description after establishing the final scope.**

   The body still advertises a `rocm_sdk.__version__` fallback that was removed, describes platform hardcoding instead of the retained `USE_CUDA`/CUDAToolkit migration, says CUDA builds are unaffected despite the failing CUDA precheckin, and claims all functional repository dependencies are gone while other projects still invoke `hipconfig`. It also does not satisfy the repository bot's accepted `JIRA ID:` format. Describe only the components left after the split, their actual version-source order, and current validation.

## Commentary

The discussion resolves several early points coherently: prerelease parsing is fixed; Python-SDK selection is intentionally deferred to the dedicated installation-model stack; and the Linux guide no longer tells users that `hipconfig --platform` selects the backend. The earliest top-level question about how returned version numbers change remains unanswered, however: accepting `10.1.0a...` fixes parsing but does not preserve the patch/build-number meaning described in item 3. The remaining four inline threads are also unresolved for good reason. Reviewers asked to isolate both the CMake floor and CUDA migration from this version-focused PR. The author agreed to move the floor but explicitly kept the migration here; the current code demonstrates why those two hipBLAS changes cannot be separated in that order, because the retained migration requires the removed CMake and package-discovery prerequisites.

The clean dependency order remains:

| Review unit | Contents | Dependency |
|---|---|---|
| CMake floor | hipBLAS declarations, installer thresholds/downloads, Linux and Windows guides | none |
| Version cleanup | shared Tensile and TensileLite version handoffs, resolver tests, toolchain tuple cleanup; optionally the simple hipSOLVER AMD default | none |
| hipBLAS backend | `USE_CUDA`, CUDAToolkit discovery/export, drivers, clients, packaging, and backend documentation | CMake-floor PR |

The referenced follow-up PR already separates the corrective commits along roughly these seams and is useful as a source of changes, but it is based on this combined branch and is not itself an independently reviewable final unit.

## Appendix: version-semantics counterexample

Run from `projects/hipblaslt/tensilelite`:

```python
import os
import tempfile
from pathlib import Path

os.environ["ROCM_VERSION"] = "7.1.0"

from Tensile.Common import SemanticVersion
from Tensile.CustomKernels import supportsUserSgprKernargPreload
from Tensile.Toolchain.Component import get_rocm_version

with tempfile.TemporaryDirectory() as root:
    info = Path(root, ".info")
    info.mkdir()
    Path(info, "version").write_text("6.4.3")
    os.environ.pop("ROCM_VERSION", None)
    os.environ["ROCM_PATH"] = root
    os.environ.pop("HIP_PATH", None)
    release_version = get_rocm_version()

assert supportsUserSgprKernargPreload(release_version)
assert supportsUserSgprKernargPreload(SemanticVersion(6, 4, 43482))
```

The first assertion fails while the second passes, even though the values represent the release-style and build-style forms of the same ROCm 6.4 family.

## Appendix: validator-model counterexample

Run from `projects/hipblaslt/tensilelite` with that package available on `PYTHONPATH`:

```python
import runpy

from Tensile.Toolchain.Validators import (
    supportedCCompiler,
    supportedCxxCompiler,
    supportedDeviceEnumerator,
    supportedOffloadBundler,
)

tests = runpy.run_path(
    "Tensile/Tests/unit/characterization/PublicInputSurfaceDeep/"
    "test_pchaos_Validators_L226_char.py"
)

component = "hipcc"
model_rejected = tests["toolchain_component_rejected"](component)
actual_rejected = not any(
    (
        supportedCxxCompiler(component),
        supportedCCompiler(component),
        supportedOffloadBundler(component),
        supportedDeviceEnumerator(component),
    )
)
assert model_rejected == actual_rejected
```

This fails with `model_rejected == False` and `actual_rejected == True`; `hipconfig` produces the same mismatch.

## Appendix: CMake package-version probe

```cmake
cmake_minimum_required(VERSION 3.13)
project(tensile_version_probe LANGUAGES CXX)

find_package(HIP REQUIRED CONFIG)
message(STATUS "HIP_VERSION=${HIP_VERSION}")
message(STATUS "hip_VERSION=${hip_VERSION}")
```

Configure with the same HIP package used by shared Tensile. The tested ROCm package reports a populated uppercase variable and an empty lowercase variable.
