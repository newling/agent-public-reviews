This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#16265](https://github.com/ROCm/rocm-libraries/pull/16265)

Reviewed head: `c65fb3722189504cc037a8310017941a876bbf21` (merge base `725652af92a0af8db6a4c391e316e325741f21df`; develop `507cf00bf7cc1e42b4896a887b6b4b9ca1de2bf9` has no later changes to the affected files). This is a second independent review of all 20 changed files. It also checks the three items from the [first review](https://github.com/newling/agent-public-reviews/blob/8b116c066ac2808b34bb0307b597df883f1d93b7/rocm-libraries/review_pr16265.md) of `a67e8636f4f`. Existing PR discussion was not an input.

Suggestion branch: [review/pr16265-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr16265-v2-suggestions), based directly on the reviewed head, with one commit: [2ad2c8f8e1f0](https://github.com/newling/rocm-libraries/commit/2ad2c8f8e1f0f46ea86544461f8b3d95a8d1f004) (suggestion 1). The actionable item is not implemented because it needs a policy decision.

## Tests

Linux, Python 3.12, Clang 23, scikit-build-core 1.1.2, nanobind 3.1.0, on a gfx1201 device. The submitted package was built against ROCm 7.1.0 (hipBLASLt 1.1.0) and, separately, against TheRock SDK 10.1.0a20260812 (hipBLASLt 1.4.1). Each suite was run with `HIPBLASLT_PY_REQUIRE_GPU=1` and with both optional second-install cases enabled, using the other installation as the alternate: **75 passed** in each direction. Root pre-commit passes on all changed files. The suggestion revision rebuilds and passes the same 75 tests.

Not validated: native Windows, a complete `invoke build --python`, and GEMM execution (this PR has no GEMM path). Math CI and the HOST_ASAN builds were pending when checked; nothing had failed.

## Summary

The three items from the first review are resolved at this head. A RUNPATH-governed library's dependencies are now preloaded from its own directory when `LD_LIBRARY_PATH` is set, and the previously failing `test_another_rocm_on_ld_library_path_doesnt_leak_in` now passes against a second ROCm in both directions. The persistent `build-dir` is gone, and `_same_file()` uses `os.path.samefile()`.

The loader is now carefully bounded. The checks are pure functions over the loaded-module list, and the side effects are confined to `load()`, which keeps the many cases testable without a second ROCm. The checks also cover the realistic ways two hipBLASLt builds end up in one process. The status-name test parsing the checkout's `hipblas-common.h` is a good guard for a new status added by a later PR.

The remaining concern is about which library the import chooses by default, not about mixing builds: an ambient `ROCM_PATH` outranks the library the bindings were compiled against.

## Actionable items

### 1. An exported `ROCM_PATH` silently replaces the hipBLASLt the bindings were built against

[`hipblaslt/_loader.py:107–114`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/hipblaslt/_loader.py#L107-L114), [`DESIGN.md:21–25`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/DESIGN.md#L21-L25), [`tasks.py:814–824`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/tasks.py#L814-L824)

`candidate_libraries()` tries `ROCM_PATH` and `ROCM_HOME` before the build-time library. `ROCM_PATH` usually names the base ROCm installation, not a particular hipBLASLt. In the workflow `invoke build --python` advertises, building "against the hipBLASLt just built", those two differ. The non-relocatable build installs hipBLASLt into `hipblaslt-install/` and passes `ROCM_PATH=<base ROCm>` and `hipblaslt_ROOT=<hipblaslt-install>` to pip. `tasks.py` itself takes the base ROCm from an exported `ROCM_PATH`. If that variable is still exported when the user imports the package, and the base ROCm ships its own hipBLASLt, the import loads the base ROCm's hipBLASLt instead of the developer's build.

I reproduced this without a full invoke build by using the same configuration: HIP from ROCm 7.1.0 and hipBLASLt 1.4.1 from a separate prefix, given via `hipblaslt_ROOT` (see the appendix). The bindings build as 1.4.1 and record the 1.4.1 library in `_build_info.py`. Then:

| `ROCM_PATH` at import | `hipblaslt.library.source` | Loaded hipBLASLt (`_loaded_library_version()`) |
|---|---|---|
| unset | `build` | 1.4.1, `67811f1e` |
| `/opt/rocm` | `ROCM_PATH` | 1.1.0, `de5c1aebb6` |

Neither import issues a warning or an error. At this revision nothing reports the mismatch. The planned first-`Handle()` warning would report it later, but only after the user has started working with a library they did not choose. Unlike `HIPBLASLT_PY_LIBRARY`, `ROCM_PATH` is not an explicit request for a particular hipBLASLt build.

Two bounded resolutions, which need the author's choice:

1. Rank the build-time library before `ROCM_PATH`/`ROCM_HOME`, keeping the override and rocm-sdk first (rocm-sdk stays first so the bindings share torch's copy). `ROCM_PATH` then applies only when the recorded library no longer exists, and `HIPBLASLT_PY_LIBRARY` remains the supported way to pick another build. This changes the documented lookup order and the corresponding `test_lookup_order_on_linux` expectation.
2. Keep the order, but warn at import when an environment-root candidate is chosen while the recorded build-time library exists and is a different file. This needs no handle: `_same_file()` already compares file identity. Also state in the `--python` help text and README that `ROCM_PATH` must be unset, or `HIPBLASLT_PY_LIBRARY` set, to load the invoke-built library.

The rocm-sdk candidate has the same effect when the wheels are installed. That precedence has the stated torch-sharing rationale, so the item does not ask to change it. On Windows, `invoke build` finds its base ROCm through the rocm-sdk wheels installed in the invoking Python, so if their libraries package is installed, the wheel's `libhipblaslt.dll` would likewise be chosen over the build. This is inferred from the code; I did not run it on Windows.

## Suggestions

### 1. Keep the `_build_info` template out of the installed package

[`CMakeLists.txt:94`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/CMakeLists.txt#L94)

`wheel.packages = ["hipblaslt"]` ships every file under `hipblaslt/`, so `_build_info.py.in` is installed into site-packages next to the generated `_build_info.py`. Commit [2ad2c8f8e1f0](https://github.com/newling/rocm-libraries/commit/2ad2c8f8e1f0f46ea86544461f8b3d95a8d1f004) moves the template to `src/` and updates `configure_file`. The installed package then contains only `__init__.py`, `_loader.py`, `_build_info.py` and `_core`.

### 2. Describe only behavior this revision has

[`README.md:46`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/README.md#L46), [`DESIGN.md:15`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/DESIGN.md#L15)

Both files say the first `Handle()` warns about a mismatched build, but this PR has no `Handle()`. `check_loaded_version()` has no caller, and `test_import_does_not_check_the_loaded_version` is vacuous until one exists. The `HIP_CHECK` macro and the `gfx950`/`large_mem` pytest markers are also unused here. Either phrase the version check as coming with handle support, or move these pieces into the PR that adds `Handle()`, so that this landing's documentation matches its code. Not implemented, because how the stack is split is the author's choice.

## Reproduction appendix

Use an isolated Python 3.12 environment without the `rocm_sdk` package, with scikit-build-core 1.1.2, nanobind 3.1.0, NumPy and pytest installed, plus CMake and Ninja. `ROCM_A` is a ROCm 7.1.0 installation that includes hipBLASLt. `HIPBLASLT_B` is a different hipBLASLt development prefix (here, the `_rocm_sdk_devel` root of SDK 10.1.0a20260812), standing in for `hipblaslt-install/`. From the repository root:

```sh
ROCM_PATH="$ROCM_A" hipblaslt_ROOT="$HIPBLASLT_B" \
  python -m pip install --no-build-isolation --no-deps projects/hipblaslt/python
cd "$(mktemp -d)"
P='import hipblaslt as h; print(h.library.source, h.library.path, h._core._loaded_library_version())'
env -u ROCM_PATH python -W always -c "$P"          # build: the 1.4.1 library
ROCM_PATH="$ROCM_A" python -W always -c "$P"       # ROCM_PATH: ROCM_A's 1.1.0 library, no warning
```

Handoff: [review/pr16265-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr16265-v2-suggestions) ends at [2ad2c8f8e1f0](https://github.com/newling/rocm-libraries/commit/2ad2c8f8e1f0f46ea86544461f8b3d95a8d1f004), which implements suggestion 1. Actionable item 1 needs a lookup-policy decision and is not implemented. Validation is Linux only.
