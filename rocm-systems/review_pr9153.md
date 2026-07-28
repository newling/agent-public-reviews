This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#9153

**Commit reviewed:** `00dd2cc473a0` (`perf(rocjitsu): avoid repeated race
trace disassembly`).

**Public/repo status:** the repository, PR, base branch, and fork containing
the head branch are public. The PR is open, is not a draft, targets `develop`,
and GitHub reports it as mergeable. The latest visible CI run is green,
including release, Clang and GCC sanitizer, TSan, focused TSan sparse-memory,
formatting, and package/sanity checks. An older TheRock run was cancelled and
reported a failed summary, but its replacement completed successfully.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: passed; the target was already up to date. Timing: 0.03s real, 0.01s
user, 0.01s sys.

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
git diff --check <pr-base>..HEAD
$SRC_DIR/.venv/bin/pre-commit run --files \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.h \
  emulation/rocjitsu/tests/execution_plugin_test.cpp
```

Result: passed.

I did not run broad emulation, HIP, or corpus suites locally. The changed
contract is covered directly by the focused unit tests, and the current public
release and sanitizer corpus jobs are green.

## Summary

The race detector keeps one PC-to-disassembly cache per dispatch and records
each instruction from the before-execute hook. A decoded `Instruction` is a
short-lived object, so the old implementation called its lazy
`disassemble()` method on every execution before attempting
`try_emplace()`. The map rejected duplicate PCs, but the formatting work had
already happened.

This PR moves the cache lookup ahead of formatting while holding the existing
per-dispatch mutex:

```text
lock cache
  PC already present -> return
  first PC encounter -> disassemble and insert
unlock cache
```

The first disassembly observed for a PC remains authoritative, matching the
existing `try_emplace()` behavior. Concurrent first encounters are serialized,
cache snapshots cannot observe a partially inserted string, and the decoded
instruction remains alive for the complete call. The regression test uses two
separate instruction objects at one synthetic PC and verifies that only the
first object is disassembled.

The lock ordering is also safe in the concrete downstream path. Instruction
recording takes only the disassembly-cache mutex. Race reporting copies the
cache under that mutex, releases it, and later takes the report mutex, so this
change does not introduce a mutex-order cycle.

## Actionable items

None.

## Suggestions

None.

## Commentary

Holding the cache mutex across a first-time disassembly makes misses a slightly
longer critical section, but misses occur once per PC while the repeated-hit
path is the workload this change targets. Avoiding a more elaborate
placeholder or in-progress-entry state also preserves the useful invariant
that every visible cache entry contains complete disassembly text. The
submitted implementation is a good fit for the current cache contract.
