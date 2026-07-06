This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#7383
**Commit reviewed:** `62ae2e2502` (`rocjitsu: kmd emulation + hsa hooks`)

**PR metadata:** public PR against public `ROCm/rocm-systems`, base `develop`, head
`ROCm:<pr-head-ref>`.

**Configure command:**

```bash
cmake -S $SRC_DIR/emulation/rocjitsu \
  -B $BUILD_DIR \
  -DBUILD_TESTING=ON -DRJ_ENABLE_TOOLS=ON
```

Configure succeeded. CMake reported `RJ_ENABLE_TOOLS` was unused. CMake found
`rocminfo` and `libhsa-runtime64.so`, but reported no RDNA4 GPU, so the
hardware HSA translation test was not registered.

**Focused hook-unit build and test:**

```bash
cmake --build $BUILD_DIR --target hsa_hooks_unit_test -j 8
ctest --test-dir $BUILD_DIR \
  -R 'HsaHooksUnitTest' --output-on-failure
```

Result: build passed. `HsaHooksUnitTest`: 5/5 passed, 0 failed, 0 skipped, 0
errored. CTest reported 0.08s real time.

**Guest KFD build and test:**

```bash
cmake --build $BUILD_DIR --target guest_kfd_test -j 8
ctest --test-dir $BUILD_DIR \
  -R 'GuestKfd' --output-on-failure
```

Result: build passed. `GuestKfd*`: 0/3 passed, 3 failed, 0 skipped, 0 errored.
CTest reported 0.09s real time. All three failures stop at the first
`open("<kfd-device>")` assertion:

```text
Expected: (parent_fd) >= (0), actual: -1 vs 0
Expected: (probe_fd) >= (0), actual: -1 vs 0
```

I verified the local KFD topology before classifying this failure:

```bash
for p in $KFD_TOPOLOGY/nodes/*/properties; do
  awk '/gfx_target_version|vendor_id/ {print FILENAME, $1, $2}' "$p"
done
```

This machine has one real GPU node with `gfx_target_version=110501` and
`gpu_id=65504`; it is not a gfx1201 host. However, `ctest -N -R
'GuestKfd|DbtGuestRocminfoTest'` still registers all 9 DBT guest runtime tests,
and the `GuestKfd*` CTest entries always launch with
`configs/guest_gfx950_on_gfx1201.json`.

The failure is therefore a test-gating problem in the PR rather than evidence
that the DBT guest implementation is wrong on a supported gfx1201 host. The
test code only skips when `<kfd-device>` is inaccessible or when the guest overlay
is not visible after a successful open; it does not skip when the configured
DBT guest host device is unavailable.

**DBT guest rocminfo build and test:**

```bash
time -p cmake --build $BUILD_DIR \
  --target dbt_guest_rocminfo_test -j 8
time -p ctest --test-dir $BUILD_DIR \
  -R 'DbtGuestRocminfoTest' --output-on-failure
```

Result: build passed in 1.01s real time. `DbtGuestRocminfoTest`: 0/6 passed, 6
failed, 0 skipped, 0 errored. CTest reported 0.28s real time. Each case failed
because `rocminfo` exited 1 with:

```text
ROCk module is loaded
Unable to open <kfd-device> read-write: No such device
current user is member of render group
```

This is the same host-gating issue as the `GuestKfd*` failures. The
`DbtGuestRocminfoTest.*` entries are registered whenever `rocminfo` exists, but
they also use `guest_gfx950_on_gfx1201.json`, so the presence of `rocminfo` is
not a sufficient capability check for these tests.

**Portable config/KFD focused tests:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests -j 8
time -p ctest --test-dir $BUILD_DIR \
  -R 'Config|SimulatedKfd|KfdIoctl' --output-on-failure
```

Result: `rocjitsu_tests` built in 23.35s real time. Focused CTest result:
24/24 passed, 0 failed, 0 skipped, 0 errored. CTest reported 5.85s real time.
This covered the DBT guest config parser tests, renamed `SimulatedKfdTest`
coverage, and touched KFD ioctl tests.

**CI status at review time:** `test (release)` passed in 15m6s and
`test (asan-ubsan)` passed in 19m42s. `test (asan-ubsan-gcc)` failed after
53m6s, but `gh run view --log` did not return useful failed-step output in this
environment, so I did not diagnose that failure. `pre-commit` failed because
black reformatted
`.github/actions/rocprofiler-sdk-util/resolve-ci-config/resolve_ci_config.py`;
that file was not in the `gh pr diff --name-only` output I reviewed for this
PR, so this appears to be a CI merge-base/sparse-checkout artifact or an
unrelated formatting failure. `therock-pr-bot` failed because the PR title is
not Conventional-Commits-style and the PR description does not contain a valid
JIRA/issue/closing-keyword reference.

The rocjitsu corpus CI does not catch the local DBT guest runtime failures
above for two reasons. First, `.github/workflows/rocjitsu-corpus-tests.yml`
sets `ROCMINFO=RocminfoTest` and runs `ctest -E "${EXCLUDED_TESTS}"`, so the
regex excludes both the existing `RocminfoTest.*` entries and the new
`DbtGuestRocminfoTest.*` entries. I verified locally that
`ctest -N -R 'DbtGuestRocminfoTest|RocminfoTest' -E 'RocminfoTest'` reports
`Total Tests: 0`. Second, the `GuestKfd*` tests skip when `<kfd-device>` is
unavailable; the CI job runs in a `no_rocm_image_ubuntu24_04` container, so it
likely exercises that skip path rather than the "KFD exists but configured host
ISA is absent" path that fails locally.

## Summary

This PR adds rocjitsu DBT guest mode: a launcher path where an unmodified ROCm
process sees a synthetic guest GPU, selects guest code objects, and then runs
translated code on a real host GPU.

The implementation is split across:

- `GuestKfd`, which appends a synthetic guest node to a temporary KFD/sysfs
  topology overlay while forwarding host-facing KFD ioctls to real `<kfd-device>`.
- HSA tools hooks, which replace public host-agent enumeration with a guest
  agent while mapping execution-facing calls back to the selected host agent.
- Code-object load hooks, which track memory-backed HSA code-object readers,
  translate guest ELF bytes, create a hidden translated reader, and load that on
  the host agent.
- CLI/config/schema support for `dbt_guest`, including sample
  `guest_gfx950_on_gfx1201.json` and `guest_gfx950_on_gfx942.json` configs.

The design boundary is clear and helpful: discovery remains guest-facing, while
actual queues, code-object loads, memory pools, copies, profiling, and symbol
queries are remapped to host handles where needed.

## Actionable items

### 1. DBT guest tests are registered on machines that cannot run the selected host config

**Files:** `emulation/rocjitsu/tests/CMakeLists.txt:453-480`,
`emulation/rocjitsu/tests/CMakeLists.txt:590-646`,
`emulation/rocjitsu/tests/guest_kfd_test.cpp:127-202`

The new `GuestKfd*` and `DbtGuestRocminfoTest.*` CTest entries are registered
whenever the test binaries can be built, and the rocminfo tests are registered
whenever `rocminfo` exists. They are all hard-wired to
`configs/guest_gfx950_on_gfx1201.json`. On a machine with `<kfd-device>` and ROCm
installed but no matching gfx1201 host GPU, the launcher cannot create the DBT
guest driver, `open("<kfd-device>")` returns `-1`/`ENODEV`, and the tests fail
instead of skipping. That happened locally for all 3 `GuestKfd*` tests and all
6 `DbtGuestRocminfoTest.*` tests.

Please make the host capability check match the DBT guest config used by the
test. A few concrete ways to do that, in order of preference:

1. Add a CMake helper that inspects KFD topology and returns available host ISA
   names or `gfx_target_version` values. Register the gfx1201 DBT guest tests
   only when a gfx1201 host is present. Register an equivalent set using
   `guest_gfx950_on_gfx942.json` only when a gfx942 host is present. If neither
   supported host is present, do not register these runtime tests.
2. If CMake-time hardware detection is too brittle, keep the CTest entries but
   wrap them in a small launcher or add a test fixture precheck that verifies
   the configured `host_isa` is discoverable before calling `open("<kfd-device>")`.
   When the host is absent, report `GTEST_SKIP()` with a message such as
   `DBT guest host ISA gfx1201 is not present on this machine`.
3. At minimum, change the `guest_kfd_test` hard assertions after `open()` into
   a skip for the specific `ENODEV`/missing-host case, while preserving failures
   for unexpected errors once a matching host exists.

The key point is that "ROCm exists", "`rocminfo` exists", or "CI happens to
skip/exclude the current tests" is not enough to prove this test can run. The
predicate needs to be "the real host GPU named by the selected DBT guest config
exists and is usable."

## Suggestions

### 1. Mirror `<kfd-device>` handling in `openat()`

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/kmd/linux/interposer.cpp:650-735`

The interposer special-cases `open("<kfd-device>")`, but direct
`openat(AT_FDCWD, "<kfd-device>", ...)` falls through to the real libc `openat`
path. This appears to predate the PR, but DBT guest mode raises the cost of
that gap because the feature depends on unmodified ROCm processes consistently
entering `GuestKfd` for KFD discovery. Consider routing the KFD device path
through the same helper from both `open()` and `openat()`, or add a regression
test showing the supported ROCm runtime paths do not call direct `openat` for
KFD.

### 2. Consider installing the new DBT guest test binaries when `RJ_INSTALL_TESTS` is enabled

**File:** `emulation/rocjitsu/tests/CMakeLists.txt:445-512`,
`emulation/rocjitsu/tests/CMakeLists.txt:590-646`

The new `guest_kfd_test`, `hsa_hooks_unit_test`, and
`dbt_guest_rocminfo_test` targets are useful coverage for this feature, but
they are build-tree-only in the current CMake. If rocjitsu installed-test
packages are expected to preserve feature coverage, wire these through the same
installed-test path used by the existing rocjitsu tests.

## Commentary

The HSA hook layer has good internal structure for a large interception table:
the table patch list is centralized, saved originals are restored cautiously,
and the unit tests exercise the most important mapping invariants
(agent-shadow enumeration, batch-copy agent-list mapping, uninstall while pool
mapping is in progress, and guest shutdown behavior).

The `CodeObjectReaderRegistry` and `ExecutableAgentRegistry` are the right
places to make load-time translation understandable. The load hook has a clear
fail-closed path: if translation fails, it refuses to pass the original guest
code object to the host agent.

The `GuestKfd` split between synthetic discovery and real host forwarding is
also easy to reason about. The risky areas are the expected ones: fd lifetime,
fork reset, mmap offsets, and guest/host GPU-id rewriting. The added
multiprocess and concurrency tests are aimed at the right risks; they just need
host-capability gating so they do not fail on unrelated ROCm machines.
