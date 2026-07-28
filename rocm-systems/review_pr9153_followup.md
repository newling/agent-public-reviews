This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#9153

**Commits reviewed:**

- `00dd2cc473a0` (`perf(rocjitsu): avoid repeated race trace disassembly`)
- `c7aaee391746` (`remove api used only in test`)

**Follow-up mode:** this review considers the inline comment asking whether
the `DisasmCache::record(uint64_t, std::string)` overload is still used. The
follow-up commit removes the overload and updates its sole test caller.

**Full configured build:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8
```

Result: all 71 build steps passed in 10.25s real, 70.33s user, 6.35s sys.

**Changed disassembly-cache behavior:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='DisasmCacheTest.*'
```

Result: 2/2 passed, 0 failed, 0 skipped, 0 errored. Timing: less than 0.01s
real.

**Direct trace-formatting and race-plugin output consumers:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='FormatTraceTest.*:RaceDetectorPluginOutputTest.*'
```

Result: 5/5 passed, 0 failed, 0 skipped, 0 errored. Timing: less than 0.01s
real.

**Diff hygiene and formatting:**

```bash
git diff --check
$SRC_DIR/.venv/bin/pre-commit run --files \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.h \
  emulation/rocjitsu/tests/execution_plugin_test.cpp
```

Result: passed.

## Summary

The inline comment is correct. After the PR stops forwarding the
`Instruction` overload through `record(uint64_t, std::string)`, the string
overload has no production callers. Its only remaining caller is
`DisasmCacheTest.HandlesNonMonotonicPcOrder`, which predates this PR and used
the overload as a convenient way to populate the cache.

The follow-up commit removes the unused overload and changes that test to
construct two ordinary `Instruction` objects. The test still verifies that
widely separated, decreasing absolute PCs are retained, but it now exercises
the same `Instruction` API used by the race detector. The new lazy-disassembly
regression remains unchanged.

## Actionable items

None.

## Suggestions

None.

## Commentary

Removing the overload is preferable to retaining a test-only API. It also
makes both `DisasmCacheTest` cases cover the production path, so the original
non-monotonic-PC regression now verifies insertion through the same lazy
disassembly and mutex boundary changed by this PR.
