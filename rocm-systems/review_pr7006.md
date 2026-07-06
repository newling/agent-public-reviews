This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#7006
**Commit reviewed:** `74e5f93166` (`fix: adress pr comments`)

**PR metadata:** public PR against public `ROCm/rocm-systems`, base `develop`,
head `ROCm:<pr-head-ref>`. GitHub currently reports the PR as
merge-conflicting.

**Configure command:**

```bash
cmake -S $SRC_DIR/emulation/rocjitsu \
  -B $BUILD_DIR \
  -DBUILD_TESTING=ON -DRJ_ENABLE_TOOLS=ON
```

Configure succeeded. CMake reported `RJ_ENABLE_TOOLS` was unused. CMake found
`rocminfo`, `libhsa-runtime64.so`, `librccl.so`, `librocblas.so`, and
`hipcc`, but did not register the HSA translate or CDNA4-to-CDNA3 dispatch
tests because this host does not have the required GPUs.

**Focused build command:**

```bash
time -p cmake --build $BUILD_DIR \
  --parallel 8 \
  --target rocjitsu_tests rocjitsu_bin rocjitsu_kmd_shim \
           rocjitsu_plugin_logging_so rocjitsu_plugin_race_so \
           hip_logging_test_target hip_profiled_plugin_test_target \
           hip_race_tests_target
```

Build passed in 129.88s real time.

**Focused test command:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R 'PluginConfigResolver|LoggingTest|ProfiledPluginTest|RaceTest' \
  --output-on-failure --timeout 60
```

Result: 43/43 passed, 0 failed, 0 skipped, 0 errored. CTest reported 6.69s
real time. This covered the new plugin config resolver tests, the dynamic
logging plugin integration test, the profiled plugin group integration test,
and the race-detector HIP tests running through the new config-selected
`race` plugin shared object.

**Additional compatibility reproduction:**

I tried a daemon-mode logging smoke:

```bash
env ROCJITSU_RUNTIME_DIR=$BUILD_DIR/tests/logging_test_output/daemon_runtime \
  RJ_SINK_DIR=$BUILD_DIR/tests/logging_test_output \
  $BUILD_DIR/tools/rocjitsu/rocjitsu --daemon \
  --config $BUILD_DIR/tests/logging_test_output/config.json \
  -- $BUILD_DIR/tests/hip_logging_test \
     --gtest_filter=LoggingTest.dispatch_logged
```

Result: 0/1 passed. The app failed because no `logging.log` was created. The
run also printed `rocjitsu: unhandled ioctl 0xc0484b20`, which appears to come
from the older remote-driver daemon path truncating/sign-changing KFD ioctl
numbers before dispatch. I did not classify this as a PR-owned plugin-loader
bug, but it means the daemon-mode plugin path is not currently covered by the
green local-mode tests.

**Other checks:**

```bash
git diff --check origin/develop...HEAD
```

passed with no whitespace errors.

**CI status at review time:** `labeler` passed. `therock-pr-bot` failed. I did
not see broader build/test jobs reported by `gh pr checks` at review time,
likely because the PR is currently merge-conflicting.

## Summary

This PR converts rocjitsu execution plugins from in-process, environment
variable selected objects into runtime-loaded shared objects. It adds a small
C-shaped plugin ABI, exports the existing logging and race-detector plugins as
`librocjitsu_plugin_logging.so` and `librocjitsu_plugin_race.so`, and adds a
host-side `PluginLoader` that reads the top-level `plugins`, `sinks`, and
`profiled` config entries.

The local launcher now prepends the interposer/plugin directory to
`LD_LIBRARY_PATH` before `execvp`, and the interposer reads the full simulator
config to construct the plugin group. The daemon server path also attempts to
load plugins from the interposer directory by explicit path. Tests and docs are
updated to drive plugin selection through config JSON rather than `RJ_RACE`,
`RJ_LOG`, `RJ_SINKS`, and `RJ_SINK_DIR`.

## Actionable items

### 1. Fix the docs so plugin snippets are shown as additions to a full simulator config

**Files:** `emulation/rocjitsu/docs/race-detector.md:71`,
`emulation/rocjitsu/docs/race-detector.md:80`,
`emulation/rocjitsu/docs/plugins.md:120`,
`emulation/rocjitsu/docs/plugins.md:124`

The updated quick-start examples tell users to create `my_config.json` with
only:

```json
{ "plugins": { "race": {} } }
```

and then run:

```bash
$BUILD_DIR/tools/rocjitsu/rocjitsu --config my_config.json -- $TMP_EXAMPLE/race_example
```

That config is not a complete rocjitsu simulator config. It lacks the `vm` and
`topology` sections required by `rj_vm_create`, so it fails once the launched
program actually opens KFD. I reproduced the shape with the logging HIP test:
using a config that contained only `{ "plugins": { "logging": {} } }` caused
`rocjitsu: failed to create VM`, followed by HIP `invalid device ordinal`.

Please rewrite these examples to say "add this top-level `plugins` section to
an existing/full rocjitsu config" and show either:

1. a patch-style snippet against an existing config such as
   `configs/amdgpu_cdna4_kmd.json`, or
2. a command that copies an existing config to `$TMP_CONFIG` and then
   inserts the `plugins` / `sinks` keys.

The standalone JSON snippets are useful for explaining the schema, but they
should not be presented as complete files passed directly to `--config`.

### 2. Clean up stale environment-variable comments in the tests

**Files:** `emulation/rocjitsu/tests/logging/hip_logging_test.hip:4`,
`emulation/rocjitsu/tests/race-detector/hip_race_tests.hip:7`

The tests now use config-file plugin selection, but their file headers still
refer to `RJ_LOG=1` / `RJ_RACE=1`. The nearby CMake comments correctly explain
that `RJ_SINK_DIR` is now only used by the test binary to find its output file.
Please update the stale headers so the codebase consistently documents the new
config-driven plugin selection model.

## Suggestions

### 1. Add a daemon-mode plugin test once the remote ioctl path is usable

**File:** `emulation/rocjitsu/tests/CMakeLists.txt:775`

The PR adds daemon-mode plugin loading in `run_daemon_server`, but the new
green integration tests exercise only local launcher mode. My daemon-mode
logging smoke did not create `logging.log`; the run hit an older
remote-driver ioctl dispatch issue (`unhandled ioctl 0xc0484b20`) before it
could prove plugin behavior. Once the remote ioctl issue is fixed, please add a
daemon variant of `LoggingTest.dispatch_logged` or another small plugin smoke
so the explicit-path `plugin_dir` path in `run_daemon_server` stays covered.

## Commentary

The C ABI boundary is a reasonable direction for the plugin system. Keeping
plugin allocation and destruction on the plugin side, validating an ABI
version, and limiting exported symbols to the three entry points are all good
choices. The local-mode loader path is also exercised well by the new tests:
the logging test proves dynamic loading and file sinks, the profiled test
proves the top-level `profiled` selection, and the race HIP tests prove the
race detector can run through the new `plugins` config.
