This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#8706](https://github.com/ROCm/rocm-systems/pull/8706)

**Commit reviewed:** `65e72e4a8c98` (`fix(rocjitsu): clarify plugin
concurrency contract`), the current PR head.

**Review mode:** standalone review. I evaluated this PR against its `develop`
base without assuming
[ROCm/rocm-systems#9731](https://github.com/ROCm/rocm-systems/pull/9731)
lands first. I compared the code changes in
[#9731](https://github.com/ROCm/rocm-systems/pull/9731) for cleanup that this
PR could use, but did not read GitHub review threads or discussion comments
on either PR.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, and GitHub currently reports it as
mergeable but blocked by the existing review decision. No checks are attached
to the current head yet, so the local results below are the available
validation for this exact commit.

**Release test build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: all 365 build steps passed in 200.68s real, 1500.62s user, and
47.90s sys.

**Runtime, launcher, and bundled plugin modules:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_bin rocjitsu_shared \
           rocjitsu_plugin_logging_so rocjitsu_plugin_race_so \
  --parallel 8
```

Result: all targets built successfully. The two plugin modules took 1.01s real,
and the launcher/shared-runtime rebuild took 3.30s real.

**Submitted plugin policy and loader tests:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='ExecutionPluginTest.*:ExecutionPluginDeathTest.*:PluginLoaderTest.*'
```

Result: 47 passed, 0 failed, 1 skipped, and 0 errored in 0.09s real. The skip
is `ExecutionPluginTest.MfmaFastPathReadHookReportsRace`, because the build
lacks 16-lane `native<float>` support.

**Repeated serialization, concurrency, cross-class overlap, and re-entry
regressions:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='ExecutionPluginTest.InfrequentHooksSerializeAtGroupBoundary:ExecutionPluginTest.HighFrequencyHooksRunConcurrentlyByDefault:ExecutionPluginTest.HighFrequencyHooksHonorSerialOptIn:ExecutionPluginTest.InfrequentAndHighFrequencyHooksMayOverlapByDefault:ExecutionPluginTest.SerialHotHookOptInPreventsInfrequentAndHighFrequencyOverlap:ExecutionPluginDeathTest.SerialHotHooksAllowRegisterReadsFromHaltHook' \
  --gtest_repeat=100 --gtest_break_on_failure
```

Result: all 600 test executions passed, with 0 failures, skips, or errors, in
6.70s real.

**Sink lifetime and race-plugin output tests:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RaceDetectorPluginOutputTest.*:ExecutionPluginGroupTest.*'
```

Result: 5/5 passed, 0 failed, 0 skipped, and 0 errored in less than 0.01s real.

**Representative bundled-plugin integration tests:**

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure \
  -R '^(LoggingTest\.dispatch_logged|RaceTest\.gfx950_vgpr_waitcnt|RaceTest\.gfx950_vgpr_waitcnt_race)$'
```

The first attempt used a stale pre-PR `librocjitsu.so` with the newly rebuilt
plugin modules. The logging test and race-enabled test failed because that old
host still expected numeric plugin ABI version 2; the control race test passed.
After rebuilding `rocjitsu_bin`, `rocjitsu_shared`, and both bundled plugin
modules with the command above, the exact same selection passed 3/3 in 0.53s
real. This was an incremental local-build mismatch, not a failure of the
reviewed source.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files <all changed rocJitsu files>
git diff --check <pr-base>..HEAD
```

Result: all applicable pre-commit hooks passed, `git diff --check` passed, and
the reviewed source checkout has no tracked modifications.

I did not run the broad simulator or corpus suites. The changed contracts are
plugin callback concurrency, re-entry, loader behavior, and profiling removal;
the focused unit tests, repeated concurrency cases, and representative logging
and race-plugin integrations exercise those paths directly.

## Summary

This PR is self-contained without
[ROCm/rocm-systems#9731](https://github.com/ROCm/rocm-systems/pull/9731). It
adds a plugin-derived callback policy, removes profiled plugin execution,
removes numeric plugin-contract versioning, and keeps the execution plugin
group final and immutable after publication.

Lifecycle, dispatch, workgroup, wavefront, and barrier hooks share one
recursive group mutex. Instruction, memory-routing, and register hooks bypass
that mutex by default, but any contained plugin can opt the whole group into
using the same lock for hot hooks through `requires_serial_hot_hooks()`. The
policy is sampled once when each plugin is added, so hot dispatch does not scan
the plugin list merely to choose a locking mode. Empty groups return before
locking or iterating.

The recursive lock is justified by a real supported re-entry path:
`onAmdgpuWavefrontHalted()` can read live registers, and those reads fire hot
register-observation callbacks. The focused death test covers this path when a
plugin requests serial hot hooks. The new cross-class tests also pin the less
obvious default contract: infrequent and hot callbacks may overlap unless a
plugin opts into the shared serialization domain.

The bundled plugins appear consistent with the parallel default. The logging
plugin protects its shared state with its own mutex. The race plugin keeps hot
state per wavefront/workgroup and protects shared disassembly, dispatch, and
reporting structures. The representative bundled-plugin tests pass after all
runtime pieces are rebuilt from the same source.

I found no code correctness blocker in the standalone PR. The remaining work is
to make the public description match the code and, optionally, carry over a
small amount of repository-owned loader cleanup that
[ROCm/rocm-systems#9731](https://github.com/ROCm/rocm-systems/pull/9731)
performs more completely.

## Actionable items

### 1. Update the PR description to match the current head

**Location:** PR description, `Technical Details` and `Test Result` sections.

The description still says the loader rejects stale runtime plugins through a
generated same-build identity. That mechanism was removed from the current
head; the code and documentation now state that plugins and host must be built
together and that the loader provides no compatibility detection or
versioning.

The reported test counts are stale as well. The submitted filter now runs 48
tests: 47 pass and one is skipped on this build. The current concurrency
selection also includes explicit infrequent/hot overlap tests that were added
after the description's result was written.

Remove the same-build-identity bullet, describe the repository-owned
matching-build contract instead, and refresh the test counts or identify the
exact smaller subset that produced the recorded result.

## Suggestions

### 1. Finish renaming and trimming the repository-owned loader boundary

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/plugin_abi.h:4-11,63-81,112-145`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/plugin_loader.cpp:149-151`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/logging/plugin_export.cpp:4-15`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin_export.cpp:4-15`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/CMakeLists.txt:75-89`

Now that the code explicitly provides no independently versioned plugin ABI,
the remaining `plugin_abi.h` filename and “ABI exports” comments suggest a
stronger compatibility boundary than exists. The `contact` metadata field is
unused, and `version` only prints the same hard-coded value for the two bundled
plugins; neither field controls supported behavior.

Use a loader-oriented name such as `plugin_exports.h`, update the export and
CMake comments, and consider reducing metadata to the operational fields:
plugin name and configuration schema. This is the main useful cleanup present
in [ROCm/rocm-systems#9731](https://github.com/ROCm/rocm-systems/pull/9731)
that the standalone PR does not yet carry.

### 2. Remove the remaining profiling and sink-helper debris

**Files:**

- `.github/workflows/rocjitsu-corpus-tests.yml:230`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/plugin_sink.h:72-80,114-118`

The sanitizer exclusion list still names
`ProfiledPluginTest.hook_profile_output`, even though this PR deletes that
test. `StdoutSink::instance()` and `StringSink::clear()` also have no callers.

Remove the stale test exclusion and the two unused helpers while the profiling
surface is already being deleted. These are small hygiene improvements from
[ROCm/rocm-systems#9731](https://github.com/ROCm/rocm-systems/pull/9731), not
standalone correctness requirements.

## Commentary

### Standalone assessment versus [ROCm/rocm-systems#9731](https://github.com/ROCm/rocm-systems/pull/9731)

The major functional overlap is already present here: profiled execution is
removed, the loader no longer takes engine configuration merely for profiling,
numeric contract-version rejection is removed, and the group is final.

The useful pieces still unique to
[#9731](https://github.com/ROCm/rocm-systems/pull/9731) are primarily cleanup:

- renaming the loader contract away from `plugin_abi.h`;
- removing unused contact/version metadata and their macro arguments;
- removing the stale profiled-test CI exclusion; and
- deleting two unused sink helper methods.

None of those omissions changes the callback-policy correctness of this PR.
They would, however, make the repository-owned plugin model more internally
consistent and leave less misleading terminology behind.
