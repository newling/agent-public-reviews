> This is a review from an agent with an automatic prompt from the reviewer

## Tests

Unable to run the `coverage-cpp` target locally (requires GPU build with
coverage instrumentation and system tools `lcov`/`genhtml`). Validated
instead that:

- `tox -a` lists `coverage-cpp` as an available environment.
- `tasks.py` imports cleanly (`python -c "import tasks"` succeeds).
- The `coverage-cpp` tox configuration parses without errors.

Existing unit tests (`Tensile/Tests/unit/`) are not affected by this PR
(no changes to production code or test code).

All CI checks pass except an unrelated gfx950-dcgpu build failure.

## Summary

This PR adds C++ code coverage support for tensilelite and rocisa via a
new `tox -e coverage-cpp` environment and a corresponding
`invoke build-coverage` task. The coverage pipeline:

1. Builds tensilelite-host and rocisa with LLVM profiling instrumentation
   (`-fprofile-instr-generate -fcoverage-mapping`) via two new CMake
   options (`TENSILELITE_ENABLE_COVERAGE`, `ROCISA_ENABLE_COVERAGE`).
2. Runs C++ gtests (tensilelite-tests) and rocisa Python tests (which
   exercise the C++ rocisa module through its Python bindings).
3. Merges `.profraw` files via `llvm-profdata`, exports to LCOV format
   via `llvm-cov`, and generates HTML + Cobertura XML reports.

This is the revised version after talumbau requested dropping the
combined Python+C++ merge approach. The current PR keeps C++ coverage
entirely separate from the existing Python coverage pipeline.

## Actionable items

1. **`CMakeLists.txt:7-8` — `add_compile_options` has overly broad
   scope.** The coverage flags are applied at directory scope, which
   means they propagate to `add_subdirectory(rocisa)` (line 4 of the
   original, line 12 after the addition) and transitively to all
   FetchContent dependencies (nanobind, stinkytofu, origami). When both
   `TENSILELITE_ENABLE_COVERAGE=ON` and `ROCISA_ENABLE_COVERAGE=ON`
   (as `build_coverage` sets), rocisa gets the flags twice. Third-party
   code gets instrumented unnecessarily, inflating profraw files and
   build times. The rocisa CMakeLists uses properly-scoped
   `target_compile_options(_rocisa PRIVATE ...)` — the tensilelite side
   should do the same, applying flags to `tensilelite-host` inside the
   `if(TENSILELITE_ENABLE_HOST)` block.

2. **`tox.ini:226` — `|| true` silently swallows rocisa test failures.**
   The rocisa pytest command ends with `2>&1 || true`, which means any
   test failure is silently ignored. Unlike the C++ tests which defer
   error checking via the exit-code file, there is no mechanism to
   surface rocisa test failures at the end of the run. Either add the
   same exit-code-file pattern used for ctest, or check the rocisa
   exit code alongside the C++ one in the final `python -c` block.

3. **`tasks.py:192-193` — stale docstring references deleted file.**
   The docstring says "use merge_coverage.py to combine with Python
   coverage" but `merge_coverage.py` was removed in a previous revision
   of this PR.

4. **`tox.ini:198` — hardcoded `/opt/rocm/lib/llvm/lib` in
   `LD_LIBRARY_PATH`.** The path assumes the default ROCm installation
   location, but `build_coverage` (in `tasks.py`) uses `_detect_rocm()`
   which can find ROCm elsewhere. If someone has ROCm at a non-default
   path, the tox environment will break even though the build step
   succeeds. Consider using `{env:ROCM_PATH:/opt/rocm}/lib/llvm/lib`.

## Suggestions

1. **`tox.ini:229-230` — no validation that LLVM tools exist.** If
   `llvm-profdata` or `llvm-cov` are not on `PATH`, `$(which ...)` returns
   empty and subsequent commands fail with unhelpful errors. A guard like
   `command -v llvm-profdata >/dev/null || { echo "llvm-profdata not found"; exit 1; }`
   would improve debuggability.

2. **`tox.ini:197` — dead `LLVM_PROFILE_FILE` in `setenv`.** The value
   set in `setenv` is overridden by explicit `export` commands in both
   test execution blocks (lines 217 and 223). The `setenv` value is
   never actually used. Either remove it or keep it as the sole source
   of truth (and drop the `export` lines).

3. **`tox.ini:246` — unusual regex `'.*\\.hp*$'`.** This matches `.h`,
   `.hp`, `.hpp`, `.hppp`, etc. — it works for the intent (exclude
   header files) but reads oddly. `'.*\\.(h|hpp)$'` or two separate
   patterns would be clearer.

4. **`CMakeLists.txt:9` — unnecessary `-fcoverage-mapping` in link
   options.** The `-fcoverage-mapping` flag is only meaningful at
   compile time. Compare with rocisa's more precise
   `target_link_options(_rocisa PRIVATE -fprofile-instr-generate)` which
   correctly omits it. Harmless but inconsistent.

## Commentary

The separate `coverage-cpp` environment addresses talumbau's core
feedback: the C++ coverage pipeline no longer touches the Python coverage
infrastructure. The CMakeLists changes and `build_coverage` task are
clean building blocks.

The exit-code-file workaround for ctest (write `$?` to a file, check
it at the end with Python) is somewhat awkward but is a standard pattern
for tox environments that need to continue after a test failure to
generate reports. The concern is that the same pattern is not applied
consistently to the rocisa tests.

The LCOV filtering has belt-and-suspenders redundancy: patterns are
applied both in `llvm-cov export` (via `--ignore-filename-regex`) and
again in `lcov --remove`. This is not wrong — the lcov filter acts as a
safety net — but it suggests uncertainty about which layer's filtering
is effective. In practice, the `llvm-cov export` patterns should be
sufficient; the `lcov --remove` could be dropped or justified with a
comment.

The overall approach (LLVM instrumentation, profdata merge, lcov export)
is the standard way to get C++ coverage into codecov-compatible formats.
The remaining question from talumbau's review — whether this should
upload to codecov as a separate `TensileLiteCPP` flag — is a CI/CD
configuration choice outside the scope of this diff.

## Previous review context

**talumbau (CHANGES_REQUESTED):** Asked to drop `merge_coverage.py` and
the combined Python+C++ coverage approach, suggesting instead a separate
codecov flag (`TensileLiteCPP`) with the LLVM pipeline kept independent.
**Status: addressed.** The merge script is gone and `coverage-cpp` is
now a separate tox environment that does not touch the Python pipeline.
The codecov upload as a separate `TensileLite-CPP` flag is handled by a
companion PR (rocJenkins #1826), which adds a presubmit CI job that runs
`tox -e coverage-cpp` whenever files under `tensilelite/` change. This
follows the same pattern as the existing `TensileLite` Python coverage
flag.

**Alex-Vasile (COMMENTED):** Asked about a `DataInitialization.hpp`
change that was included to fix a build error with coverage
instrumentation (`isMXProblem` undefined). The author explained the test
was calling a removed function. **Status: addressed.** The C++ test
fixes have been reverted out of this PR into a separate PR, per the
author's comment.

**newling (COMMENTED):** Asked several clarifying questions:

- *`tox.ini:198` — what is `/opt/rocm/lib/llvm/lib`?* This is the LLVM
  runtime library directory shipped with ROCm (contains `libclang_rt`
  profiling runtime, needed for instrumented binaries). **Overlaps with
  actionable item #4 above** — the path is hardcoded and should use
  `ROCM_PATH`.

- *`tox.ini:216` — are there Python tests that hit C++ tensilelite
  code?* Good question. The rocisa Python tests exercise the rocisa C++
  module through its Nanobind bindings, but there do not appear to be
  Python tests that exercise the tensilelite-host C++ library. The
  tensilelite-host coverage comes entirely from the C++ gtests. This
  means the coverage numbers for tensilelite-host reflect only gtest
  coverage, not the Python-driven integration paths that are the primary
  usage of the library.

- *`tox.ini:273` — what are the 3 report files?* `combined.lcov` is the
  filtered LCOV coverage data, `coverage_cpp/html/` is a browsable HTML
  report (generated by `genhtml`), and `coverage.xml` is Cobertura XML
  (for CI upload to codecov).

- *`tasks.py:198` — exception vs print+return.* **Overlaps with our
  commentary:** the `print+return` pattern is consistent with the
  existing `build_client` task. Raising an exception would be better
  practice (invoke catches and displays them cleanly), but changing it
  would be a style improvement across the file, not specific to this PR.

- *CMakeLists — `add_compile_options` vs `target_compile_options`.*
  **Directly overlaps with actionable item #1 above.** newling asked
  whether the difference is intentional; our independent analysis
  confirms it is not — `add_compile_options` at directory scope is
  overly broad and should be `target_compile_options` on
  `tensilelite-host`.

- *CMakeLists — could `HIPBLASLT_ENABLE_COVERAGE`,
  `TENSILELITE_ENABLE_COVERAGE`, and `ROCISA_ENABLE_COVERAGE` be
  unified?* The existing `HIPBLASLT_ENABLE_COVERAGE` in
  `projects/hipblaslt/CMakeLists.txt` already `--ignore-filename-regex`
  excludes Tensile and origami paths. Having separate options is
  reasonable since tensilelite and rocisa can be built standalone
  (outside the hipBLASLt superbuild), but the overlap should at minimum
  be documented. A single `HIPBLASLT_ENABLE_COVERAGE` that also
  instruments tensilelite-host and rocisa when they are subdirectories
  would be simpler if standalone coverage is not a requirement.
