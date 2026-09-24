> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12372](https://github.com/ROCm/rocm-libraries/pull/12372)

Reviewed commit: `91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54`

Date: 2026-09-24

This follow-up incorporates the existing reviewer comments at the reviewer's request; the original review was independent of them.

**Accompanying branch:** [review/pr12372-packaging-fixes](https://github.com/newling/rocm-libraries/tree/review/pr12372-packaging-fixes), based on the reviewed commit above.

| Review item | Commit | Change |
| --- | --- | --- |
| Debian version dependency | [fa220204b93](https://github.com/newling/rocm-libraries/commit/fa220204b93733797a9edc0d7100b52dd8600817) | Use CPack's full-version component dependency; add native-package tests and a targeted CI workflow. |
| ASAN package contents | [edefdcb6725](https://github.com/newling/rocm-libraries/commit/edefdcb67252f9a96045f86b6d97fb99afadcc5a) | Retain the host library in the ASAN runtime component, with content checks. |
| Debian file-ownership transfer | Omitted | Requires the actual first split release to set the upgrade boundary; see the finding. |
| Static install arguments | [125339c2e72](https://github.com/newling/rocm-libraries/commit/125339c2e72b0d6a0e2a31a713eac3998c3ec4ac) | Select existing package files and reject missing required packages, with install-command tests. |
| RPM SONAME requirement | [d381aa299af](https://github.com/newling/rocm-libraries/commit/d381aa299afe863e5034fbd7e65671babf164d13) | Derive the requirement from the target's SOVERSION; test against a changed ELF SONAME. |
| Packaging comment length | [aab9878a0aa](https://github.com/newling/rocm-libraries/commit/aab9878a0aaaf4fd9b51d948d73021dbd7b47a71) | Remove repeated motivation and implementation narration, including comments added on this branch. |

The commits form an ordered series; later regression tests extend the fixture introduced by the first commit. Inspect an individual change with `git show <commit>`. The suggested PR-description rewrite remains in Appendix B because it changes GitHub metadata rather than repository source.

## Tests

The original four package findings reproduced in compiled CPack fixtures; on the accompanying branch, native-package and install-command tests pass with CMake 3.28 and 4.4, both hipBLASLt and TensileLite host libraries build with ROCm 7.1, and root pre-commit, workflow `actionlint`, and whitespace checks pass.

The new regression tests failed before their respective changes and pass afterward. They cover sanitized Git releases, explicit release/ROCm patch/epoch settings, shared versus ASAN package contents, static/shared install arguments, and an SOVERSION change from 1 to 2. A targeted GitHub workflow runs them when these packaging files change; that new workflow has not run remotely. Reproduce the branch checks from the repository root with Invoke installed in the selected Python environment:

```bash
TMPDIR="$BUILD_DIR" ROCM_CMAKE_DIR="$ROCM_CMAKE_DIR" python3 -B -m unittest discover \
  -s projects/hipblaslt/tools/scripts/tests -p 'test_*packages.py'
```

The upgrade finding remains open on the accompanying branch; the fixture-only remedy used an illustrative version boundary.

The fixture executes the PR's new packaging block and library install rules with two minimal compiled libraries and the exact rocm-cmake revision pinned by `fetch_rocm_cmake.cmake`. It isolates package-manager behavior without rebuilding GPU kernels. The SONAME test compares the compiled ELF library with the generated CPack RPM requirement. The host-library build used device-library generation, clients, and rocRoller disabled; it verifies compilation and linking, not GPU execution. RPM automatic dependency scanning and Windows installers were not tested; `rpmbuild` is unavailable locally. The complete reproducer is in Appendix A.

Public hipBLASLt/hipSPARSELt precheckin checks and TheRock's hipBLASLt Linux/Windows tests passed. The red [ASAN test job](https://github.com/ROCm/rocm-libraries/actions/runs/35933257190/job/107431149268) ended after a runner shutdown, while the [rocBLAS shard](https://github.com/ROCm/rocm-libraries/actions/runs/35933258876/job/107479371331) passed its tests and then timed out during cleanup. The [race-check job](https://github.com/ROCm/rocm-libraries/actions/runs/35933258876/job/107626729918) failed importing `joblib`. Those results do not validate or explain the package defects reproduced here. Coverage checks are also red, and the gfx1250 checks require action; this review does not claim an entirely green CI run.

## Summary

The PR moves the TensileLite host shared library into a separate CPack component, adds hipBLASLt runtime dependencies on the resulting package, and extends the developer install command to install it. Static archives and headers retain their existing development component. This creates the package boundary needed for another library to consume the host runtime separately from hipBLASLt's GPU kernel data.

Checking the target's actual library type is a useful choice because hipBLASLt and TensileLite have independent shared/static options. Preserving the global dependencies when adding component-specific dependencies also matters: the fixture retained both `roctracer` and `rocm-core`. The remaining problems concern how native packages resolve versions, transfer ownership of installed files, and select components under alternate build options.

## Actionable items

### Use the complete Debian version in the exact dependency

**Location:** [`projects/hipblaslt/CMakeLists.txt:994–995`](https://github.com/ROCm/rocm-libraries/blob/91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54/projects/hipblaslt/CMakeLists.txt#L994-L995).

Debian's `=` operator compares the complete version, including the release suffix. `rocm_create_package()` sets `CPACK_DEBIAN_PACKAGE_RELEASE` from the release environment override or the sanitized Git-derived `PROJECT_VERSION_TWEAK`. The new dependency omits that suffix.

With `PROJECT_VERSION_TWEAK=42`, the generated host package has `Version: 1.5.0-42`, but hipBLASLt has `Depends: tensilelite-host (= 1.5.0)`. `dpkg --compare-versions 1.5.0-42 eq 1.5.0` returns 1. Installing both packages from the same build therefore does not satisfy the new dependency. Adding a ROCm patch component to both versions does not remove this mismatch.

**Proposed change: [fa220204b93](https://github.com/newling/rocm-libraries/commit/fa220204b93733797a9edc0d7100b52dd8600817).** Enable `CPACK_DEBIAN_ENABLE_COMPONENT_DEPENDS` and declare that `runtime` depends on the `tensilelite` component. CPack generates the equality from its final package version, so this uses the existing generator rather than duplicating rocm-cmake's release and epoch logic. The RPM requirement retains its existing version-only policy. The commit includes tests with both sanitized Git releases and explicit release/patch/epoch settings. If accepting every packaging revision of one upstream version is preferred, that needs a different Debian version-range policy.

### Keep the host library available in ASAN packages

**Location:** [`projects/hipblaslt/tensilelite/CMakeLists.txt:204–205`](https://github.com/ROCm/rocm-libraries/blob/91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54/projects/hipblaslt/tensilelite/CMakeLists.txt#L204-L205), together with [`projects/hipblaslt/CMakeLists.txt:910–916`](https://github.com/ROCm/rocm-libraries/blob/91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54/projects/hipblaslt/CMakeLists.txt#L910-L916).

The pinned rocm-cmake implementation clears its non-runtime component list when `ENABLE_ASAN_PACKAGING=ON`. Registering `tensilelite` does not override that behavior. Moving the shared library out of `runtime` consequently removes it from the ASAN package output.

The fixture generated only `hipblaslt-asan_1.5.0-42_amd64.deb`. It contained `libhipblaslt.so`, omitted `libtensilelite-host.so` and its versioned files, and still required the separate `tensilelite-host` package. No such package was generated. This also risks resolving an ASAN build against an ordinary host package from a repository after the Debian version problem is fixed.

**Proposed change: [edefdcb6725](https://github.com/newling/rocm-libraries/commit/edefdcb67252f9a96045f86b6d97fb99afadcc5a).** Retain the host library in `runtime` for ASAN packaging and omit the split-package registration and dependencies in that mode. The committed checks verify that the ASAN package contains both libraries without a separate host dependency, while an ordinary shared build still produces a separate host package. A successful ASAN compilation or test against a plain install tree does not exercise CPack's component filtering.

### Declare the Debian transfer of file ownership

**Location:** [`projects/hipblaslt/CMakeLists.txt:913–916`](https://github.com/ROCm/rocm-libraries/blob/91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54/projects/hipblaslt/CMakeLists.txt#L913-L916) and [`projects/hipblaslt/tensilelite/CMakeLists.txt:205`](https://github.com/ROCm/rocm-libraries/blob/91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54/projects/hipblaslt/tensilelite/CMakeLists.txt#L205).

The new package takes ownership of files previously owned by `hipblaslt`, but it declares no Debian `Replaces` or `Breaks` relationship. An existing installation at the same prefix can therefore reject the new dependency when it is unpacked before the updated hipBLASLt package.

A rootless test first unpacked the old combined package, then unpacked the new host package. The second command failed with:

```text
trying to overwrite '/opt/rocm/lib/libtensilelite-host.so.1.0',
which is also in package hipblaslt 1.5.0-41
```

Add version-bounded `CPACK_DEBIAN_TENSILELITE_PACKAGE_REPLACES` and `CPACK_DEBIAN_TENSILELITE_PACKAGE_BREAKS` metadata for the hipBLASLt versions that owned those files. Choose the boundary from the actual first split release. Verify an upgrade at the same installation prefix, including unpacking the new dependency first. The fixture's bounded `Replaces`/`Breaks` pair allowed the file transfer without forcing overwrite or removing the existing package first.

**No implementation commit.** The PR does not establish the first published split-package version. Choosing a `Breaks` cutoff from a fixture's `41`/`42` values or from the current Git hash would invent release policy and could reject valid package combinations. The exact ownership-transfer reproducer and successful illustrative remedy remain in Appendix A for the author to apply once that boundary is known.

### Only pass generated packages to the static install command

**Location:** [`projects/hipblaslt/tasks.py:871–878`](https://github.com/ROCm/rocm-libraries/blob/91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54/projects/hipblaslt/tasks.py#L871-L878).

`invoke build --static` sets both hipBLASLt and TensileLite to static libraries. The new CMake guard correctly omits the separate host package in that configuration, but every native install command now unconditionally includes its glob.

On a fresh static build, Bash leaves `tensilelite-host[-_]*.deb` unexpanded because no file matches it. The package manager receives that literal nonexistent filename and the install command fails. Executing the actual Python install block with a recording context against the generated static packages confirmed that argument; the RPM branches have the same unconditional-glob problem.

**Proposed change: [125339c2e72](https://github.com/newling/rocm-libraries/commit/125339c2e72b0d6a0e2a31a713eac3998c3ec4ac).** Collect existing package files with `Path.glob()`, omit the separate host package for `--static`, and quote the resulting filenames. Missing hipBLASLt packages, or a missing host package in a shared build, raise an explicit error before invoking the installer. The committed tests execute the actual install block with a recording context and check DEB/RPM static arguments, shared arguments, paths containing spaces, and missing required packages.

### Derive the RPM library requirement from the target's SOVERSION

**Location:** [`projects/hipblaslt/CMakeLists.txt:950–955`](https://github.com/ROCm/rocm-libraries/blob/91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54/projects/hipblaslt/CMakeLists.txt#L950-L955).

The existing reviewer [identified the literal `.1`](https://github.com/ROCm/rocm-libraries/pull/12372#discussion_r4088362547). The host package publishes a library name derived from its binary, but hipBLASLt's requirement is fixed at `libtensilelite-host.so.1()(64bit)`. The current library uses SOVERSION 1, so the values match today. Changing the fixture's library version to `2.7` produced an ELF SONAME of `libtensilelite-host.so.2`, while CPack still required `.so.1`. The comment claiming both sides follow a version bump is therefore incorrect.

**Proposed change: [d381aa299af](https://github.com/newling/rocm-libraries/commit/d381aa299afe863e5034fbd7e65671babf164d13).** Read the target's `SOVERSION` when constructing the Linux RPM requirement. The new test changes the library version, reads the compiled binary's SONAME with `readelf`, and checks that the generated requirement names the same library. It failed with the literal and passes with the target property.

## Suggestions

### Keep packaging comments focused on non-obvious constraints

**Location:** [`projects/hipblaslt/CMakeLists.txt:902–995`](https://github.com/ROCm/rocm-libraries/blob/91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54/projects/hipblaslt/CMakeLists.txt#L902-L995), [`projects/hipblaslt/tensilelite/CMakeLists.txt:195–201`](https://github.com/ROCm/rocm-libraries/blob/91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54/projects/hipblaslt/tensilelite/CMakeLists.txt#L195-L201), and `projects/hipblaslt/tasks.py:866–870`.

I agree with the [request to remove nonessential comments](https://github.com/ROCm/rocm-libraries/pull/12372#discussion_r4088322073). Repeated size estimates, change history, ticket references, and line numbers in helper implementations obscure the packaging rules. Some explanations added on the accompanying branch were also longer than necessary.

**Proposed change: [aab9878a0aa](https://github.com/newling/rocm-libraries/commit/aab9878a0aaaf4fd9b51d948d73021dbd7b47a71).** Remove that narration and shorten the branch's comments. Retain brief explanations of independent library-type options, component dependencies replacing global dependencies, rocm-cmake's RPM defaults, and ASAN's runtime-only packaging. The fixture now selects the relevant CMake statements without relying on the deleted comment text.

### Shorten the PR description and use recognized tracking syntax

The PR description can be shorter and should use the repository's recognized tracking syntax. The [policy job](https://github.com/ROCm/rocm-libraries/actions/runs/35933254200/job/107424690274) specifically reports that the description must reference a JIRA ID, ISSUE ID, or GitHub closing keyword; the current bare references were not accepted. Appendix B supplies a pasteable rewrite with the required headings and `JIRA ID` line. It also addresses the prose guide's requirements to describe the current change, support claims with evidence, and avoid undefined references: the existing text includes commit-by-commit narration, “D7,” and a “linked plan” without a link.

## Commentary

The [target-gating comment](https://github.com/ROCm/rocm-libraries/pull/12372#discussion_r4088333163) does not establish nondeterminism. `add_subdirectory(tensilelite)` executes before the packaging block, and the same file already inspects target types when constructing its exports. Gating on `TENSILELITE_ENABLE_HOST` and `TENSILELITE_BUILD_SHARED_LIBS` would be a reasonable style choice, but the target check is deterministic and reflects the created library. The accompanying branch retains it.

The [question about `ROCM_DEP_ROCMCORE`](https://github.com/ROCm/rocm-libraries/pull/12372#discussion_r4088345904) is answered by [`ROCMCreatePackage.cmake`](https://github.com/ROCm/rocm-cmake/blob/c01b4f1fd36a94d26c76e7f617b57577b3b84275/share/rocmcmakebuildtools/cmake/ROCMCreatePackage.cmake#L19-L23), loaded through `fetch_rocm_cmake.cmake`. It defines the cache option before this use, defaulting on except for detected ROCm platform versions below 4.5. This needs no source fix.

Package generation, dependency resolution, upgrades, and package-content checks are the appropriate test level for this change. Additional matrix-multiplication tests would not detect these failures. The submitted PR adds no direct automated package tests; the accompanying branch adds focused checks and a CI workflow for the implemented findings without requiring more GPU coverage. A downstream `find_package(hipblaslt)` check after installing the generated package set would also exercise the reason for changing `install-pkg`.

The diff creates a package that hipSPARSELt can depend on; it does not change hipSPARSELt's own dependency declarations. Describe that consumer migration as separate work. Plain installation paths are preserved, which explains why successful TheRock artifact tests can coexist with native-package failures.

## Appendix A: Reproducer

This appendix reproduces the original findings at `91ba6b0fa1fcf058f095f7fed2d85e00ba34fa54`; use the branch tests above for the proposed fixes. Use the original reviewed checkout as `$SRC_DIR`, a fresh directory outside it as `$BUILD_DIR`, and the `share/rocmcmakebuildtools/cmake` directory from public rocm-cmake commit `c01b4f1fd36a94d26c76e7f617b57577b3b84275` as `$ROCM_CMAKE_DIR`. The script needs Python 3, CMake, Ninja, Clang, Bash, `dpkg`, and `dpkg-deb`. Use a build path without shell metacharacters or whitespace because the existing install command interpolates it into shell text.

Save the source below as `reproduce.py` and run:

```bash
export SRC_DIR BUILD_DIR ROCM_CMAKE_DIR
python3 reproduce.py
```

All package unpacking uses private roots under `$BUILD_DIR`; the fixture has no maintainer scripts. Only the minimal fixture is modified when checking remedies. Its release values `41` and `42`, and corresponding replacement boundary, are test inputs rather than proposed production versioning policy. The fixture's version remedy covers those inputs; production code also needs to honor rocm-cmake's release overrides and sanitization.

```python
# Copyright Advanced Micro Devices, Inc., or its affiliates.
# SPDX-License-Identifier: MIT
import ast
import contextlib
import os
from pathlib import Path
import re
import subprocess

src = Path(os.environ["SRC_DIR"]) / "projects/hipblaslt"
out = Path(os.environ["BUILD_DIR"])
modules = Path(os.environ["ROCM_CMAKE_DIR"])
out.mkdir(parents=True, exist_ok=True)


def run(*args, ok=True):
    result = subprocess.run([str(x) for x in args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if ok and result.returncode:
        raise RuntimeError(result.stdout)
    return result


top = (src / "CMakeLists.txt").read_text()
start = top.index("if(TARGET tensilelite-host)",
                  top.index("# libtensilelite-host.so ships"))
end = top.index("\nif(ROCM_LIBS_SUPERBUILD OR NOT HIPBLASLT_IS_SUBPROJECT)", start)
block = top[start:end]
install = (src / "tensilelite/CMakeLists.txt").read_text()
install = install.split("    install(TARGETS tensilelite-host", 1)[1]
install = "install(TARGETS tensilelite-host" + install.split("        FILE_SET", 1)[0] + ")\n"
prefix = '''cmake_minimum_required(VERSION 3.25.2)
project(hipblaslt VERSION 1.5.0 LANGUAGES C)
list(APPEND CMAKE_MODULE_PATH "${ROCM_CMAKE_DIR}")
include(ROCMCreatePackage)
include(ROCMSetupVersion)
set(PROJECT_VERSION_TWEAK "42")
set(ROCM_USE_DEV_COMPONENT ON)
set(CPACK_GENERATOR DEB)
set(CPACK_THREADS 2)
option(BUILD_SHARED_LIBS "Shared hipblaslt" ON)
option(TENSILELITE_BUILD_SHARED_LIBS "Shared TensileLite" ON)
if(TENSILELITE_BUILD_SHARED_LIBS)
  add_library(tensilelite-host SHARED host.c)
else()
  add_library(tensilelite-host STATIC host.c)
endif()
rocm_set_soversion(tensilelite-host "1.0")
add_library(hipblaslt hipblaslt.c)
target_link_libraries(hipblaslt PRIVATE tensilelite-host)
install(TARGETS hipblaslt LIBRARY DESTINATION lib COMPONENT runtime
        ARCHIVE DESTINATION lib COMPONENT devel)
rocm_package_add_dependencies(DEPENDS "roctracer >= 1.0.0")
'''
suffix = '\nrocm_create_package(NAME hipblaslt DESCRIPTION "Packaging probe" MAINTAINER "Package maintainer")\n'
head = prefix + install + block + suffix
old = (prefix.replace('"42"', '"41"')
       + install.replace("COMPONENT tensilelite", "COMPONENT runtime") + suffix)
# These fixture-only changes validate possible remedies, not a proposed patch.
fixed = head.replace("install(TARGETS tensilelite-host", '''set(_tl_component tensilelite)
if(ENABLE_ASAN_PACKAGING)
  set(_tl_component runtime)
endif()
install(TARGETS tensilelite-host''')
fixed = fixed.replace("COMPONENT tensilelite", "COMPONENT ${_tl_component}")
fixed = fixed.replace("if(TARGET tensilelite-host)",
                      "if(TARGET tensilelite-host AND NOT ENABLE_ASAN_PACKAGING)")
fixed = fixed.replace('DEPENDS "tensilelite-host (= ${_tensilelite_pkg_version})"',
                      'DEPENDS "tensilelite-host (= ${_tensilelite_pkg_version}-${PROJECT_VERSION_TWEAK})"')
fixed = fixed.replace("rocm_create_package(NAME", '''set(CPACK_DEBIAN_TENSILELITE_PACKAGE_REPLACES "hipblaslt (<< 1.5.0-42)")
set(CPACK_DEBIAN_TENSILELITE_PACKAGE_BREAKS "hipblaslt (<< 1.5.0-42)")
rocm_create_package(NAME''')
for mode, code, options in [
    ("shared", head, []),
    ("asan", head, ["-DENABLE_ASAN_PACKAGING=ON"]),
    ("static", head, ["-DBUILD_SHARED_LIBS=OFF", "-DTENSILELITE_BUILD_SHARED_LIBS=OFF"]),
    ("old", old, []),
    ("fixed-shared", fixed, []),
    ("fixed-asan", fixed, ["-DENABLE_ASAN_PACKAGING=ON"]),
]:
    fixture = out / (mode + "-src")
    fixture.mkdir(exist_ok=True)
    (fixture / "CMakeLists.txt").write_text(code)
    (fixture / "host.c").write_text("int tensilelite_probe(void) { return 1; }\n")
    (fixture / "hipblaslt.c").write_text(
        "extern int tensilelite_probe(void); int hipblaslt_probe(void) { return tensilelite_probe(); }\n")
    run("cmake", "-S", fixture, "-B", out / mode, "-G", "Ninja",
        "-DCMAKE_C_COMPILER=clang", "-DCMAKE_INSTALL_PREFIX=/opt/rocm",
        "-DROCM_CMAKE_DIR=" + str(modules), *options)
    run("cmake", "--build", out / mode, "--target", "package", "-j2")


def package(mode, pattern):
    return next((out / mode).glob(pattern))


for mode, expected in [("shared", 1), ("fixed-shared", 0)]:
    runtime = package(mode, "hipblaslt_*.deb")
    host = package(mode, "tensilelite-host_*.deb")
    depends = run("dpkg-deb", "-f", runtime, "Depends").stdout
    required = re.search(r"tensilelite-host \(= ([^)]+)\)", depends)[1]
    version = run("dpkg-deb", "-f", host, "Version").stdout.strip()
    status = run("dpkg", "--compare-versions", version, "eq", required, ok=False).returncode
    assert status == expected
    print(mode, "package version:", version, "dependency:", required, "equal:", status == 0)

for mode, expected in [("asan", False), ("fixed-asan", True)]:
    contents = run("dpkg-deb", "-c", package(mode, "*.deb")).stdout
    present = "libtensilelite-host.so.1.0" in contents
    assert present == expected
    print(mode, "contains host library:", present)

for mode, expected in [("shared", 1), ("fixed-shared", 0)]:
    dest = out / ("upgrade-" + mode)
    dest.mkdir()  # Use a fresh BUILD_DIR for each run.
    dpkg = ["dpkg", "--root=" + str(dest), "--log=" + str(dest / "dpkg.log"),
            "--force-not-root", "--unpack"]
    run(*dpkg, package("old", "hipblaslt_*.deb"))
    result = run(*dpkg, package(mode, "tensilelite-host_*.deb"), ok=False)
    assert result.returncode == expected
    if expected:
        assert "trying to overwrite" in result.stdout
    print(mode, "upgrade unpack exit:", result.returncode)

# Execute only the changed install-command block; never invoke a package manager.
tree = ast.parse((src / "tasks.py").read_text())
node = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
            and isinstance(n.test, ast.Name) and n.test.id == "install_pkg")


class Context:
    def cd(self, path):
        return contextlib.nullcontext()

    def run(self, command):
        pass


commands = []
static = out / "static"
exec(compile(ast.Module(body=[node], type_ignores=[]), "tasks.py", "exec"),
     {"install_pkg": True, "c": Context(), "build_subdir": static,
      "distro": "ubuntu", "_elevate": lambda c, cmd: commands.append(cmd)})
arguments = run("bash", "-c", 'printf "%s\\n" ' + commands[0].split(" ", 2)[2]).stdout.splitlines()
missing = [p for p in arguments if not Path(p).exists()]
assert len(missing) == 1 and "tensilelite-host" in missing[0]
print("Static install passes nonexistent argument:", Path(missing[0]).name)
matched = list(static.glob("hipblaslt[-_]*.deb")) + list(static.glob("tensilelite-host[-_]*.deb"))
assert matched and all(p.exists() for p in matched)
print("Python glob candidate includes only existing static packages")
```

## Appendix B: Suggested PR description

Suggested title: `build(hipblaslt): package the TensileLite host library separately`

```markdown
JIRA ID : AIHPBLAS-4434

## Motivation

hipBLASLt performs matrix multiplication using GPU kernels selected by its TensileLite host runtime. hipSPARSELt also needs that host runtime, but distributing it inside the hipBLASLt runtime package makes consumers install hipBLASLt's kernel data with it. A separate host package allows consumers to depend on the smaller shared library.

## Technical Details

Move the TensileLite shared library into a `tensilelite-host` package and retain static archives and headers in the development component. Register the new component when the target is a shared library, add hipBLASLt runtime package dependencies, and include the new package in the developer install command.

Enable RPM dependency scanning for the host component so its provided shared-library name follows the binary. Keep existing runtime package dependencies when adding the new requirements. Plain CMake installation paths remain unchanged. This PR does not update hipSPARSELt's dependency declarations.

## Test Plan

Inspect generated DEB and RPM dependencies and contents, verify installation and upgrades, and check shared, static, and ASAN packaging. After installation, check that downstream CMake can load the exported hipBLASLt targets.

## Test Result

The reported gfx942 smoke run on RHEL 9.5 passed. TheRock's Linux and Windows hipBLASLt tests and Math CI precheckin passed. Local DEB package checks identified failures that still need correction; ASAN CI was interrupted by a runner shutdown. Native-package validation is not complete.

## Submission Checklist

- [ ] Look over the contributing guidelines at https://github.com/ROCm/TheRock/blob/main/GOVERNANCE.md#pull-requests.

## Risk level

Medium: changes package dependencies and ownership of an installed shared library. Installation and upgrades can fail even when compilation and GPU tests pass.
```
