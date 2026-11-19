This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#16265](https://github.com/ROCm/rocm-libraries/pull/16265)

Reviewed head: `a67e8636f4f729bbe0439b95fb2c8afc204c4590`. Independent review of all 20 changed files, including packaging, native bindings, library selection, tests, documentation, invoke integration, and formatting configuration. Merge base: `602c8b16a2a85db2f386a0384734c5bff338cc11`; inspected develop: `5c498cb8278d161bb4306ed0b3e4aa7216788de6`, with no subsequent changes to the affected files. Existing PR discussion was not an input.

Suggestion branch: [review/pr16265-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr16265-suggestions), based directly on the reviewed head. Its two commits map to actionable item 2 ([c0c2308af892](https://github.com/newling/rocm-libraries/commit/c0c2308af8922332c91da4d0a541c2a4274b5f57)) and item 3 ([55f5d85ca216](https://github.com/newling/rocm-libraries/commit/55f5d85ca216af2ee1bad6f25fb3dad9ff00706d)). Item 1 remains unimplemented.

## Tests

Linux, Python 3.12, Clang 23, scikit-build-core 1.1.2, nanobind 3.1.0. The submitted package built against ROCm 7.1.0 / hipBLASLt 1.1.0 and separately against SDK 10.1.0a20260812 / hipBLASLt 1.4.1. The submitted default suite passed 67 tests and skipped the two optional second-install cases. Enabling those cases exposed the dependency-loading failure below. The suggestion revision ran all cases: **69 passed, 1 failed**, with that same failure remaining.

The new hard-link regression fails on the submitted loader and passes with the fix; the actual SDK import reproducer also changes from failure to success. Consecutive default wheel builds against the two installations fail on the second build before the cache fix and both pass afterward, with the expected paths in each wheel's `_build_info.py`. Root and component pre-commit checks, whitespace checks, and `invoke --help build` pass.

Native Windows execution, a complete `invoke build --python` library build, and GEMM execution were not validated. The existing device/version test executed, but it does not exercise GEMMs. The required GitHub formatting/component summaries were passing when checked; Math CI's required summary was pending. This PR's CI does not build or run the new Python package.

## Summary

The default native build remains independent of the Python package. The extension is small; most of the added behavior is library selection and checks intended to prevent incompatible hipBLASLt builds sharing a process. Delaying handle creation until actual use is useful because import otherwise allocates device memory. The explicit missing-override error and status-name tests also enforce meaningful behavior.

The main remaining issue is at the boundary between choosing a library pathname and resolving that library's dependencies. The pure-function tests cover decisions over an existing module list, but they cannot establish what the operating-system loader will bring in during the next `dlopen`.

## Actionable items

### 1. Handle conflicting dependency search paths before loading hipBLASLt

[`hipblaslt/_loader.py:453–470`](https://github.com/ROCm/rocm-libraries/blob/a67e8636f4f729bbe0439b95fb2c8afc204c4590/projects/hipblaslt/python/hipblaslt/_loader.py#L453-L470)

`check_companions()` checks only modules already loaded. Passing a full pathname to `ctypes.CDLL()` selects hipBLASLt itself, but a library with `DT_RUNPATH` still resolves its dependencies through `LD_LIBRARY_PATH` first. If that path contains another ROCm's `librocroller.so.1`, the preload can fail before either companion check can diagnose the mix.

This is reproducible with the submitted `test_another_rocm_on_ld_library_path_doesnt_leak_in`: build against ROCm 7.1.0, then set `HIPBLASLT_PY_TEST_OTHER_ROCM_LIB` to the SDK 10.1.0a20260812 devel library directory. The test fails with an `OSError` for an undefined `rocRoller::Expression::conditional` symbol while opening the selected hipBLASLt. Dependency inspection confirms that rocRoller comes from the other installation. The same failure remains on the suggestion branch.

Resolve the required companion libraries from the selected installation before opening hipBLASLt, or explicitly reject this configuration with the promised `HipblasLtLoadError` and adjust the documented support boundary and test expectation. Merely inspecting the loaded-module list earlier cannot catch dependencies that have not loaded yet. No fix is included: choosing deterministic companion preloading versus rejecting conflicting search paths changes the loader's supported behavior, and indiscriminately preloading every similarly named sibling would introduce additional dependencies. The existing integration test is the regression case.

### 2. Avoid reusing CMake package selections across different ROCm builds

[`pyproject.toml:26`](https://github.com/ROCm/rocm-libraries/blob/a67e8636f4f729bbe0439b95fb2c8afc204c4590/projects/hipblaslt/python/pyproject.toml#L26)

The persistent `build/{wheel_tag}` directory is shared by builds using the same Python ABI, even when `ROCM_PATH` changes. CMake keeps the previous `hipblaslt_DIR` and HIP package paths in its cache. The metadata provider reads the newly requested installation, so the next ordinary source build fails with “package version (1.4.1) ... doesn't match ... CMake found (1.1.0)” despite the caller selecting a single valid installation. A fresh build against that same installation succeeds.

Commit [c0c2308af892](https://github.com/newling/rocm-libraries/commit/c0c2308af8922332c91da4d0a541c2a4274b5f57) removes the default persistent build-directory setting and uses scikit-build-core's temporary build directory. Both installations then build successfully in sequence. This also avoids silently retaining an old package selection when two installations happen to report the same version. Explicitly requested persistent build directories still have ordinary CMake cache semantics.

### 3. Compare existing library files by identity as well as pathname

[`hipblaslt/_loader.py:150–151`](https://github.com/ROCm/rocm-libraries/blob/a67e8636f4f729bbe0439b95fb2c8afc204c4590/projects/hipblaslt/python/hipblaslt/_loader.py#L150-L151)

`_same_file()` compares normalized paths, which resolves symbolic links but does not recognize hard links. The SDK used above installs `libhipblaslt.so.1` and `libhipblaslt.so.1.4` as hard links. Preloading the latter, then selecting the former through `HIPBLASLT_PY_LIBRARY`, raises “can't take effect” even though `os.path.samefile()` confirms they are one file and the native loader can reuse it.

Commit [55f5d85ca216](https://github.com/newling/rocm-libraries/commit/55f5d85ca216af2ee1bad6f25fb3dad9ff00706d) uses `os.path.samefile()` for accessible files on the host platform, retaining pathname comparison for unavailable paths and cross-platform test inputs. A compact regression covers override acceptance, the single-library check, and deduplication. Both it and the real SDK preload/import sequence fail before the change and pass afterward.

## Suggestions

None.

## Reproduction appendix

Use an isolated Python environment with Python 3.12, scikit-build-core 1.1.2, nanobind 3.1.0, NumPy, and pytest installed, plus CMake and Ninja. Set `CXX` to the selected Clang compiler. `ROCM_A` is a ROCm 7.1.0 development installation; `ROCM_B` is the SDK 10.1.0a20260812 development root. Neither build requires generating hipBLASLt kernels.

For item 2, extract the submitted package into an empty scratch directory named by `PROBE_DIR`, then use the default build-directory behavior:

```sh
git archive a67e8636f4f729bbe0439b95fb2c8afc204c4590 projects/hipblaslt/python | tar -x -C "$PROBE_DIR"
PKG="$PROBE_DIR/projects/hipblaslt/python"
export CMAKE_BUILD_PARALLEL_LEVEL=8
ROCM_PATH="$ROCM_A" python -m pip wheel --no-build-isolation --no-deps "$PKG" -w "$PROBE_DIR/wheels-a"
ROCM_PATH="$ROCM_B" python -m pip wheel --no-build-isolation --no-deps "$PKG" -w "$PROBE_DIR/wheels-b"
```

The second command fails at the CMake version comparison. Removing `build-dir = "build/{wheel_tag}"` from the copied `pyproject.toml` makes both commands succeed, without changing either ROCm installation.

For item 1, install the package built against `ROCM_A` in an environment without the `rocm_sdk` Python package, then run the existing test from the repository root:

```sh
HIPBLASLT_PY_TEST_OTHER_ROCM_LIB="$ROCM_B/lib" python -m pytest \
  projects/hipblaslt/python/tests/test_library_loading.py::test_another_rocm_on_ld_library_path_doesnt_leak_in
```

For item 3, the committed regression is `test_hardlinked_library_names_are_the_same_loaded_file`. The actual SDK sequence is:

```python
import ctypes
import os
from pathlib import Path

lib = Path(os.environ["ROCM_B"]) / "lib"
loaded = lib / "libhipblaslt.so.1.4"
override = lib / "libhipblaslt.so.1"
assert os.path.samefile(loaded, override)
ctypes.CDLL(str(loaded), mode=ctypes.RTLD_GLOBAL)
os.environ["HIPBLASLT_PY_LIBRARY"] = str(override)
import hipblaslt
```

Handoff: [suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr16265-suggestions) ends at [c0c2308af892](https://github.com/newling/rocm-libraries/commit/c0c2308af8922332c91da4d0a541c2a4274b5f57). Its two commits address items 2 and 3; item 1 remains open with a failing existing integration test. Validation is limited to Linux.
