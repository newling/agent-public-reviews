This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15412](https://github.com/ROCm/rocm-libraries/pull/15412)

Reviewed head: `414d43c50c00b0a747a2fd8042882efa47540eb9` (merge base `02433ce8085a16a882f8b2332abfc977057f0678`). The head merges cleanly with develop `207bc1a58e9`; the only target develop has added under hipBLASLt since the merge base is a sample, which the check excludes. This is an independent review of all eight changed files, plus the ROCm clang toolchain whose stated contract the PR changes. Existing PR discussion was not an input.

Suggestion branch: [review/pr15412-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15412-suggestions), based directly on the reviewed head. Its commits are independent of the PR's correctness and fall into two groups. The first five are recommended. The last one is experimental: it shows what the idiomatic approach costs, so the author can decide whether it is worth taking. Suggestions 6 and 7 are not implemented.

| Commit | Suggestion | Status |
|---|---|---|
| [d617db2c21e2](https://github.com/newling/rocm-libraries/commit/d617db2c21e2b237224f6fab9ed1091c9e420ec6) | 1. Stamp the checkout's commit | Recommended |
| [adf41dbc66c5](https://github.com/newling/rocm-libraries/commit/adf41dbc66c568b0945c329c9397ff44ea1f28a1) | 2. Toolchain comment | Recommended |
| [7294c8a79103](https://github.com/newling/rocm-libraries/commit/7294c8a79103d7845ff63fe1534264b61495e771) | 3. Check documentation | Recommended |
| [d51fc79d643a](https://github.com/newling/rocm-libraries/commit/d51fc79d643ae39c1095d211b0d963921b7d46d2) | 4. `.rc` template with `configure_file` | Recommended |
| [53a6f912c1df](https://github.com/newling/rocm-libraries/commit/53a6f912c1df747071a92b4364b4ab5df28345fc) | 5. Explicit `VERSION` argument | Recommended |
| [8fe8092e7fc4](https://github.com/newling/rocm-libraries/commit/8fe8092e7fc4538287d9d93113eb8eddbd5b6e86) | 8. `OriginalFilename` from `$<TARGET_FILE_NAME>` | Experimental |

The commits apply in this order, and each one builds on the previous. Taking only the recommended ones means taking the branch up to [53a6f912c1df](https://github.com/newling/rocm-libraries/commit/53a6f912c1df747071a92b4364b4ab5df28345fc).

## Tests

Linux only, with CMake 4.4 and TheRock SDK 10.1.0a20260812. A configure-only run of hipBLASLt with clients, samples and tests enabled passes the completeness check at the submitted head. So do runs with the device library, `HIPBLASLT_ENABLE_YAML`, `HIPBLASLT_ENABLE_ROCROLLER`, and origami's Python bindings and tests enabled. Deleting the `hipblaslt-bench` line makes configure fail with a message naming that target, so the check sees real targets. (Deleting the `hipblaslt-sequence` line does not, because that target exists only with `HIPBLASLT_ENABLE_YAML`; see Commentary.) A static-library configure fails at generate time with an unrelated `install(EXPORT)` error about `hipblaslt-rocroller-selection`, which this PR does not touch.

A standalone CMake project that forces `WIN32` and enables RC with a placeholder compiler confirms several helper behaviors: the generated `.rc` escapes quotes and backslashes, a `;` stays inside the value, and `OriginalFilename` follows `OUTPUT_NAME`, `PREFIX` and `SUFFIX`. Reconfiguring leaves an unchanged `.rc` file's timestamp alone, and the check reports an unmarked executable. Root pre-commit, including cmake-lint, passes on the changed files at both revisions.

On the suggestion branch, after suggestion 4 the same project's resources differ only by the template's comment header and a blank line where no `Comments` value is given, and an unchanged file still keeps its timestamp. Suggestion 5 leaves them byte-identical and rejects `VERSION "1.2"`. Suggestion 8 leaves them unchanged for targets named before the call, and a target renamed and given a `DEBUG_POSTFIX` after the call gets its final name under both Ninja and Ninja Multi-Config. hipBLASLt with clients, samples, tests and the device library, and standalone origami with its tests, configure at the branch tip.

Not validated: compiling the `.rc` (no resource compiler on this host), a Windows configure or build, and inspection of linked binaries. CI at the reviewed head has no failure attributable to the PR. The failing `FFM gfx1250 / tensilelite` check reports "No results — run timed out or was killed", and the two Codecov project checks also fail.

## Summary

The PR replaces two hand-written `version.rc.in` templates and their per-library resource-compiler guards with one generated resource. It moves hipBLASLt and origami onto it and adds a configure-time check that every DLL and EXE target defined in the project either carries a resource or is explicitly excluded. The check carries the design. It runs from target properties on every platform, so ordinary Linux builds catch a forgotten binary without a Windows CI scan, and the exclusions are listed in one place with reasons. The helper's details are careful: it writes the `.rc` only when its content changes, derives `OriginalFilename` from the target's properties, and uses `PARSE_ARGV` so a value containing `;` survives.

The behavior change worth noting is that a Windows configure with no usable resource compiler now fails by default instead of warning. The description states this, and `ROCM_LIBRARIES_REQUIRE_VERSION_RESOURCE=OFF` restores the old outcome; suggestion 2 updates the toolchain comment that still promises the old outcome.

## Actionable items

None.

## Suggestions

### Recommended

#### 1. Stamp hipBLASLt binaries with the checkout's commit

[`hipblaslt_version_resource.cmake:16-30`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/projects/hipblaslt/cmake/hipblaslt_version_resource.cmake#L16-L30)

The `Comments` value comes from `git log -1 --format=%H .` in `projects/hipblaslt`, which is the last commit that touched hipBLASLt, not the commit being built. The `ProductName` tag in the same resource comes from `rocm_get_git_commit_tag`, which runs `git describe --always` and therefore describes HEAD. At develop `207bc1a58e9`, for example, a build would stamp `ProductName` with `207bc1a58e9` but `Comments` with `7300a9df430`, and `origami.dll` from the same build would carry `207bc1a58e9` because origami already uses `rev-parse HEAD`. The binaries can also contain shared code from outside `projects/hipblaslt`, such as origami and rocroller when they are bundled into the build, so a change there produces a different `libhipblaslt.dll` with the same `Comments` commit. That works against the PR's stated goal of telling which build a binary came from. The previous template had the same behavior for `libhipblaslt.dll`; this PR extends it to fourteen more targets. [d617db2c21e2](https://github.com/newling/rocm-libraries/commit/d617db2c21e2b237224f6fab9ed1091c9e420ec6) switches to `rev-parse HEAD`.

#### 2. Update the toolchain comment that promises a warning

[`cmake/toolchains/rocm-clang.cmake:74-77`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/cmake/toolchains/rocm-clang.cmake#L74-L77)

When no resource compiler is found, the toolchain sets `CMAKE_RC_COMPILER-NOTREQUIRED` and explains that components "guard their .rc sources on a real compiler and warn when version metadata will be omitted". hipBLASLt and origami now fail configuration in that case unless `ROCM_LIBRARIES_REQUIRE_VERSION_RESOURCE=OFF`. [adf41dbc66c5](https://github.com/newling/rocm-libraries/commit/adf41dbc66c568b0945c329c9397ff44ea1f28a1) rewrites the comment to say each component decides, and names the components that fail.

#### 3. Describe the check's skips and coverage precisely

[`rocm_libraries_version_resource.cmake:32-34`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/cmake/modules/rocm_libraries_version_resource.cmake#L32-L34), [`TESTING.md:679`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/projects/hipblaslt/TESTING.md?plain=1#L679)

The module header says targets "from the build tree (e.g. FetchContent dependencies)" are skipped, but the code skips only `FETCHCONTENT_BASE_DIR` (by default `<build>/_deps`). That narrower rule is the right one, because skipping the whole build tree would disable the check for in-source builds. The `TESTING.md` row names only `hipblaslt_add_version_resource`, though origami calls the shared function directly. It also says "any build" catches a new binary, though a build checks only the targets its options enable. [7294c8a79103](https://github.com/newling/rocm-libraries/commit/7294c8a79103d7845ff63fe1534264b61495e771) corrects both.

#### 4. Generate the resource from a template with `configure_file`

[`rocm_libraries_version_resource.cmake:82-91`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/cmake/modules/rocm_libraries_version_resource.cmake#L82-L91), [`rocm_libraries_version_resource.cmake:141-176`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/cmake/modules/rocm_libraries_version_resource.cmake#L141-L176)

`_rocm_libraries_version_resource_write` exists so a reconfigure does not touch an unchanged `.rc` file and relink the target. `configure_file` already behaves that way, and the conventional CMake form of a version resource is an `.rc.in` template filled in by `configure_file`. [d51fc79d643a](https://github.com/newling/rocm-libraries/commit/d51fc79d643ae39c1095d211b0d963921b7d46d2) moves the resource into `rocm_libraries_version_resource.rc.in` next to the module, which removes the helper and the escaped 35-line string literal. The function locates the template with `CMAKE_CURRENT_FUNCTION_LIST_DIR`, not a module-scope variable: under `include_guard(GLOBAL)`, origami's subdirectory includes the module before hipBLASLt's top level does, so a module-scope variable would be missing in hipBLASLt's scope. origami's sparse checkout and its optional include already cover the new file, since it is in `cmake/modules`. All of this works with the existing CMake 3.25.2 minimum.

#### 5. Pass the version explicitly

[`rocm_libraries_version_resource.cmake:12-13`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/cmake/modules/rocm_libraries_version_resource.cmake#L12-L13), [`rocm_libraries_version_resource.cmake:138-139`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/cmake/modules/rocm_libraries_version_resource.cmake#L138-L139)

The helper takes the file version from `PROJECT_VERSION_*` in whatever scope calls it. That is correct for every call in this PR, because each is made at the owning project's top level. A call from a subdirectory that has its own `project()`, such as TensileLite's, would silently stamp that project's version. The hipBLASLt wrapper also builds `ProductName` from `hipblaslt_VERSION_*`, so the same fact comes from two places. As the helper sits in the shared `cmake/modules` for other libraries to adopt, [53a6f912c1df](https://github.com/newling/rocm-libraries/commit/53a6f912c1df747071a92b4364b4ab5df28345fc) makes `VERSION <major>.<minor>.<patch>` a required argument. It checks the argument's form on every platform, so a Linux build also catches a bad value. hipBLASLt and origami pass the same numbers as before.

### For the author to decide

#### 6. Include `cmake/modules` in hipBLASLt's sparse checkout

[`hipblaslt_version_resource.cmake:14`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/projects/hipblaslt/cmake/hipblaslt_version_resource.cmake#L14), [`projects/hipblaslt/README.md:55`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/projects/hipblaslt/README.md?plain=1#L55)

origami includes the shared module with `OPTIONAL` and its README adds `cmake/modules` to its sparse checkout. hipBLASLt includes it unconditionally, but its README still documents `git sparse-checkout set projects/hipblaslt`. A default hipBLASLt configure already needs `shared/origami`, so this matters only for configurations that take dependencies from an installation, such as `HIPBLASLT_ENABLE_THEROCK`. Adding `cmake/modules` to that command would keep it working there. Not implemented, because I could not establish whether a hipBLASLt-only sparse checkout is still a supported setup.

#### 7. Correct the description's risk statement

The description's risk section says "on Linux the CMake changes do nothing", but the completeness check runs and can fail configure on Linux, which is the point of the design. Saying that the Linux effect is limited to the configure-time check, and that it can fail a PR that adds an unlisted DLL or EXE, would match the change.

### Experimental

#### 8. Take `OriginalFilename` from `$<TARGET_FILE_NAME>`

[`rocm_libraries_version_resource.cmake:47-80`](https://github.com/ROCm/rocm-libraries/blob/414d43c50c00b0a747a2fd8042882efa47540eb9/cmake/modules/rocm_libraries_version_resource.cmake#L47-L80)

This one is offered for evaluation, not as a recommendation. The helper rebuilds the file name from `OUTPUT_NAME`, `PREFIX` and `SUFFIX` at the time of the call. That is right for every target in this PR, but it misses properties set after the call, per-configuration names and postfixes. For example, a Windows build configured with `-DCMAKE_DEBUG_POSTFIX=d` would produce `libhipblasltd.dll` while the resource says `libhipblaslt.dll`. CMake's own answer is the generator expression `$<TARGET_FILE_NAME:tgt>`, which [8fe8092e7fc4](https://github.com/newling/rocm-libraries/commit/8fe8092e7fc4538287d9d93113eb8eddbd5b6e86) uses: `configure_file` fills in the values, then `file(GENERATE)` resolves the name, and the commit deletes the manual derivation.

The cost is why this is experimental. Each target gets two generated files instead of one, and the resource's source path depends on `$<CONFIG>`, because a multi-config generator can give each configuration a different name. Resource strings must also not contain generator-expression syntax (`$<...>`). The case it fixes is real but uncommon, so whether it is worth that complexity is a judgment call. It needs no newer CMake than 3.25.2.

## Commentary

The check covers only the targets that exist in a given configuration. `hipblaslt-sequence` is defined only with `HIPBLASLT_ENABLE_YAML`, and `hipblaslt-cotenant-kernel` only off Windows, so a new conditional binary is caught only by a CI configuration that enables it. That seems like the right trade for a configure-time check, and the exclusion list makes the intended scope explicit.

Two further idioms were considered and not implemented. The documented way to probe for an optional language is `include(CheckLanguage)` followed by `check_language(RC)`. Here, though, the repository toolchain deliberately sets `CMAKE_RC_COMPILER` to a `NOTREQUIRED` placeholder, and as far as I know `check_language` treats an already-set compiler as found, so the PR's direct check is the safer choice without a Windows test. The trailing `"\0"` on each string value is an old habit from Microsoft samples. Resource compilers terminate the strings themselves and the replaced templates did not use it; it should be harmless, but I could not compile a resource here to confirm that removing it changes nothing.
