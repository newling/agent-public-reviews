> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#11377 — `refactor(hipblaslt): remove obsolete preprocessor branches`](https://github.com/ROCm/rocm-libraries/pull/11377)

**Scope:** head `b381ff749abe`

**Review mode:** independent focused review; existing PR discussion was not
used as review evidence.

**Assessment:** APPROVE

**Risk:** 3/5 — most changes remove compile-time-dead alternatives, but the PR
also updates public low-precision headers and relies on the documented ROCm 7
minimum to remove compatibility branches.

## Tests

From the hipBLASLt build configured for gfx942:

```bash
/usr/bin/time -p env PATH="$VENV/bin:$PATH" \
  cmake --build "$BUILD_DIR" --target hipblaslt-test --parallel 8
```

Result: the target built successfully in 96.54 seconds. This rebuilt the
changed host library, public datatype code, client support, and
`auxiliary_gtest.cpp`, including the new device-side BF8-FNUZ conversion
compile probe.

```bash
/usr/bin/time -p "$BUILD_DIR/clients/hipblaslt-test" --gtest_list_tests
```

Result: exit code 0 in 1.33 seconds.

```bash
git diff --check fa14a73b817c8d7bdf6edd8bd075db8805279881..HEAD
```

Result: passed.

I also attempted the focused Python test currently failing in CI:

```bash
$VENV/bin/python -m pytest -q \
  projects/hipblaslt/tensilelite/Tensile/Tests/unit/test_PlaceholderMerge.py::test_logic_yaml_sibling_device_names_consistent
```

The repository-local environment does not contain `pytest`, so this did not
run locally. CI executes that test and reports a sibling-logic `DeviceNames`
inconsistency. Neither the test nor the affected logic files are changed by
this PR, so that failure does not appear to be caused by this patch.

At review time on August 28, 2026, hipBLASLt and hipSPARSELt precheckin and
static-analysis jobs pass. An initial gfx90a host-ASAN build and quick test
also pass. The later duplicate ASAN run stopped while fetching dependencies
before configuration or compilation.

## Summary

The PR removes preprocessor branches that cannot select a distinct supported
behavior anymore. That includes disabled diagnostic blocks, identical
alternatives, an FP6x16 implementation whose referenced HIP types and
intrinsics are unavailable, unused internal-API definitions, and compatibility
paths older than the project's ROCm 7 support floor.

It also makes nearby predicates accurately describe the platform or datatype
they guard. In particular, the BF8-FNUZ conversion operator now follows the
FNUZ capability macro rather than the unrelated OCP macro, and Windows checks
consistently use the compiler-provided `_WIN32` definition.

The changed contracts are narrow and supported by the gfx942 build, targeted
device-compilation coverage, and existing CI. Current `develop` has advanced
since the branch was created, but its intervening hipBLASLt changes do not
overlap the files changed here and GitHub reports the PR as mergeable.

## Actionable items

None.

## Suggestions

1. **`projects/hipblaslt/tensilelite/tools/gpu_revision_probe.cpp:19-22` —
   remove the obsolete old-HIP fallback description.**

   The implementation now reads `properties.asicRevision` unconditionally,
   but the comment still says the probe prints `-1` when HIP is too old to
   expose that field. Under the newly stated ROCm 7 minimum, that path no
   longer exists. Keeping the general caller rule that an unknown negative
   revision falls back safely is reasonable, but the probe-specific claim
   should be updated in a later cleanup.

## Commentary

The PR has a coherent boundary: it removes branches only where the supported
toolchain or current source graph makes one side unreachable, while retaining
the architecture and device-pass predicates that still select real behavior.
The small compile-only kernel is useful regression coverage for a property that
ordinary host compilation would otherwise miss.
