This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9803](https://github.com/ROCm/rocm-systems/pull/9803)

**Revision reviewed:** published head `df0e081916b`, one commit based directly
on `origin/develop@25fa67c5b35`.

**Review mode:** implementation follow-up to
`review_pr9803_self_review.md`. I rechecked the original actionable item,
reviewed the complete resulting diff, and reran the directly affected unit and
HIP integration coverage.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 \
  --target rocjitsu_tests \
           hip_race_tests_gfx950_target \
           hip_race_tests_gfx1151_target \
           rocjitsu_plugin_race_so
```

Result: all 700 steps passed in 158.06s real, 1168.21s user, and 61.52s sys.
This was effectively a clean focused rebuild because the latest upstream
decoder-result and barrier-model changes invalidated most of the previous
object cache.

**Direct parser and matcher contract:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  --output-on-failure \
  -R '^RaceLogExpectationTest\.'
```

Result: 12/12 passed, 0 failed, 0 skipped, and 0 errored in 0.33s real,
0.25s user, and 0.07s sys.

Coverage includes:

- valid zero-finding and one-finding logs;
- empty and unrecognized logs;
- missing `RJ_SINK_DIR` and missing files;
- unterminated records;
- malformed integer, missing, and duplicate fields;
- complete structured expectation matching; and
- missing expected trace markers.

**Complete directly affected HIP race-test surface:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  --output-on-failure --parallel 4 \
  -R '^RaceTest\.(gfx950|gfx1151)_'
```

Result: 42/42 passed, 0 failed, 0 skipped, and 0 errored in 2.22s real,
6.04s user, and 2.06s sys.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files <changed source files>
git diff --check
```

Every applicable hook passed, and `git diff --check` passed.

**Coordination checks:**

`git merge-tree --write-tree` found no textual conflict between the complete
staged candidate and the exact current same-wave LDS ordering head.

The explicit-wave register-observation branch has one conflict in
`execution_plugin.h`, but the same conflict occurs when merging that branch
directly with current `origin/develop`. The #9803 candidate does not touch that
file and introduces no additional conflict.

## Summary

The original actionable item is resolved.

The implementation now separates the support code into two layers:

- `race_log_expectation.hpp` is a pure C++ parser and matcher with no HIP or
  GoogleTest dependency.
- `race_test_support.hpp` is a small HIP/GoogleTest adapter that provides
  allocation, synchronization, diagnostics, and assertion translation.

The parser returns an explicit result rather than using an empty vector for
both success and failure. It now rejects:

- an unset or empty sink directory;
- an unreadable log file;
- empty or unrelated file contents with no recognizable race-plugin output;
- malformed, missing, or duplicate required header fields;
- invalid numeric fields;
- unexpected or nested record delimiters; and
- EOF before `END_RACE`.

A valid zero-finding log must still contain evidence from the race plugin,
normally the immediately flushed kernel-dispatch line. This preserves the
current integration-test timing: tests inspect the log before plugin teardown,
so they do not depend on the destructor-written summary.

The matcher is also pure C++ and returns all expectation mismatches as data.
The HIP fixture converts parser failures into fatal GoogleTest assertions and
matcher failures into one consolidated diagnostic. Existing test call sites
and their exact-one versus one-or-more semantics are unchanged.

The result is the intended durable boundary: missing or truncated evidence can
no longer become a false no-race success, the format contract is fast to test
without launching the simulator, and the eventual move to a versioned
machine-readable diagnostic can happen behind one interface.

## Actionable items

None.

## Suggestions

None.

## Commentary

The PR remains appropriately narrow. It does not change race detection,
plugin output, or runtime semantics; it strengthens only the test consumer of
that output. The future structured-output work discussed in the original
self-review remains useful, but it should be a separate plugin-format change
rather than an expansion of this refactor.

### Published GitHub metadata

The rebased commit and fail-closed parser changes were published on August 19,
2026. The PR title and description now read:

Title:

```text
test(rocjitsu): structure and validate HIP race expectations
```

Description:

```text
## Summary

Centralize the gfx950 and gfx1151 HIP race-test expectations so finding counts,
normalized fields, dispatch context, wave/lane identity, and marked trace
instructions live beside the kernels they protect.

Split the shared support into:

- a pure C++ race-log parser and expectation matcher; and
- a small HIP/GoogleTest fixture for allocation, synchronization, and assertion
  reporting.

Make the parser fail closed when the sink directory or log is missing, when the
log contains no recognizable race-plugin output, or when a RACE block has
malformed, missing, duplicate, or unterminated fields. This prevents missing or
truncated diagnostic evidence from being interpreted as a passing no-race
test.

Existing HIP race scenarios and their exact-one versus one-or-more semantics
are preserved.

## Testing

- 12/12 direct race-log parser and matcher tests passed.
- 42/42 gfx950 and gfx1151 HIP race integration tests passed.
- Focused rocJITsu build and pre-commit passed.

## Issue Tracking

Related: #9577
```

The PR remains draft; converting it to ready for review was intentionally
outside the authorized publication steps.
