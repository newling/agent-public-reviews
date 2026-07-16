This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8695

**Commit reviewed:** `b5a9c94de3` (`Keep DRM layout checks warning-clean with Clang`).

**Public/repo status:** the repository and #8695 are public. The PR is open, not draft, mergeable, has its head branch in the same public repository, and targets a public non-default feature branch (`<base-ref>`).

**GitHub checks:**

```bash
gh pr checks 8695 --repo ROCm/rocm-systems
```

Result: visible checks were passing for `pre-commit`, release tests, asan/ubsan tests, asan/ubsan GCC tests, Linux package builds, TheRock summary, HIP NVIDIA summary, setup, and labeler. Several hardware/platform lanes were skipped.

**Whitespace check:**

```bash
git diff --check 107ea843f98dce583ee9fc0d2975f8cda26abd03..origin/pr/8695
```

Result: passed with no whitespace errors.

**Build command:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

Result: passed on the PR head. The first PR-head build reconfigured after switching branches and rebuilt/linked `rocjitsu_tests`: 120.85s real, 900.54s user, 43.07s sys. After a base-commit comparison and switching back to the PR head, the final incremental PR-head rebuild also passed: 2.16s real, 2.47s user, 0.73s sys.

**Focused test command:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R 'DrmInfoLayoutTest' \
  --output-on-failure
```

Result: passed. CTest selected 2 tests: 2 passed, 0 failed, 0 skipped, 0 errored. Timing: 0.06s real, 0.05s user, 0.01s sys.

**Base-commit comparison:**

```bash
git switch --detach 107ea843f98dce583ee9fc0d2975f8cda26abd03
time -p cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

Result: passed locally in 2.14s real, 2.46s user, 0.73s sys. This host did not reproduce the unsuppressed warning from the base commit, presumably because the installed libdrm header here does not have the newer nested anonymous type shape that triggered the CI failure.

## Summary

This PR makes `emulation/rocjitsu/tests/drm_info_layout_test.cpp` warning-clean with Clang when the system `libdrm/amdgpu_drm.h` header contains nested anonymous types. The test now pushes Clang diagnostics, ignores only `-Wnested-anon-types`, includes the external libdrm header, and then pops diagnostics before the file's own layout assertions.

That keeps the suppression source-local and include-local: project code after the include still gets normal diagnostics, non-Clang compilers do not see a Clang-specific pragma, and the layout test still checks the local `LocalDevInfo` offsets, size relationship, and HBM constant against the system kernel UAPI shape.

The related rocm-libraries PR uses a broader CI bridge workaround:

```bash
-DCMAKE_CXX_FLAGS="-Wno-error=unknown-warning-option -Wno-error=nested-anon-types"
```

That is the same warning family, but the scope is different. In that bridge script, keeping the warning visible while making it non-fatal is useful for a temporary external-source build. In this PR, the narrow pragma around a single external header is more precise for a unit test whose purpose is to include that header and assert ABI layout.

## Actionable items

No blocking code issues found.

## Suggestions

No non-blocking suggestions for the current diff.

## Commentary

The implementation is deliberately small and matches the problem surface. I considered whether this should be expressed through the existing `rj_compiler.h` diagnostic helpers, but that header does not currently have a `-Wnested-anon-types` macro and adding one for a single test include would be more code than the local pragma. If this warning suppression starts appearing in several files, promoting it to a named diagnostic helper would become worthwhile.

There is a broader warning-policy tradeoff here. Normal `-Werror` builds generally should not fail on warnings from external dependency headers, because those diagnostics are often caused by dependency/compiler skew that this project cannot fix directly. It can still be useful to surface external-header warnings in deliberate audit contexts, such as compiler or SDK upgrades, include-order investigations, macro/packing interactions caused by project code, or vendored headers that are effectively part of the supported source surface.

A CMake-centered alternative would be to model the dependency headers as `SYSTEM` include directories, preferably through a small interface target such as a `rocjitsu_system_libdrm_headers` target that is linked only by targets intentionally including `<libdrm/amdgpu_drm.h>`. That would move the policy out of source and let the compiler treat the dependency include path as system-owned. The caveat is that this only helps when CMake owns the include path passed to the compiler; in the local compile command for this test, the host libdrm header came from the compiler's default system search path rather than an explicit libdrm include directory. The existing `DRM_INCLUDE_DIR` in the rocjitsu CMake configuration is also the vendored kernel UAPI header path, not the host `libdrm/amdgpu_drm.h` path used by this layout test, so a CMake solution would need to model those two header sources separately.
