This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9803](https://github.com/ROCm/rocm-systems/pull/9803)

**Revision reviewed:** local rebased head `b47211331a0`, one commit based
directly on `origin/develop@c1dba564e7e`. The published PR head remains
`8ddca414a465`; the local rebase has not been pushed.

**Review mode:** comment-aware self-review with a fresh architectural pass.
GitHub has no human review submissions, inline review threads, or discussion
comments on this PR, so there were no PR-specific reviewer requests to
re-evaluate. I independently checked the complete diff, the previous
assertions, the race-plugin output contract, related open rocJITsu work, and
the local history of earlier designs.

**Public/repository status:** the upstream repository, source fork, PR, base
branch, and head branch are public. The PR is open and draft. GitHub reports
the published head as mergeable, with review required.

**Rebase:**

The one-commit branch was rebased cleanly onto current `origin/develop`. A
dated local backup ref preserves the exact pre-rebase head. Merge-tree checks
also found no textual conflict with the current same-wave LDS ordering branch
or the explicit-wave register-observation branch.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 \
  --target hip_race_tests_gfx950_target \
           hip_race_tests_gfx1151_target \
           rocjitsu_plugin_race_so
```

Result: all 551 steps passed in 187.85s real, 1371.16s user, and 62.21s sys.

**Complete directly affected HIP race-test surface:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  --output-on-failure --parallel 4 \
  -R '^RaceTest\.(gfx950|gfx1151)_'
```

Result: 42/42 passed, 0 failed, 0 skipped, and 0 errored in 3.26s real,
9.55s user, and 3.58s sys.

**Parser failure-mode probe:**

I compiled and ran the host-only probe in Appendix A against the submitted
header. It produced:

```text
unset=0
missing=0
truncated=1 body_bytes=150
```

The first two results show that an unset `RJ_SINK_DIR` and an unreadable
`race.log` are both represented as a valid empty finding set. The third shows
that EOF before `END_RACE` is accepted as a complete record. This is a genuine
test-infrastructure failure mode: `ExpectNoRace()` treats the first two cases
as success, while a sufficiently populated truncated block can satisfy
`ExpectRace()`.

**Formatting and diff hygiene:**

```bash
time -p .venv/bin/pre-commit run --files \
  $(git diff --name-only origin/develop...HEAD)
git diff --check origin/develop...HEAD
```

Every applicable hook passed in 0.60s, and `git diff --check` passed. The
source worktree has no tracked or untracked modifications.

**Published-head CI context:**

The rocJITsu release, Clang ASan/UBSan, GCC ASan/UBSan, TSan, formatting,
policy, HIP NVIDIA summary, and focused TheRock summary checks passed on the
published head. The broad multi-architecture summary was red because of
unrelated package, Python-wheel, rocprofiler-systems, and Windows sanity jobs.
Those failures do not exercise the five files changed here, but the published
CI is also based on the old pre-rebase head.

## Summary

The PR replaces two independently maintained race-log parsers and many
open-coded assertions with one declarative expectation model shared by the
gfx950 and gfx1151 HIP integration tests. Each racy kernel now has a nearby
`RaceExpectation` describing the relevant finding count, normalized fields,
wave/lane context, and marked trace instructions. The existing two-binary,
one-process-per-test execution model remains intact, and CMake now tracks the
shared header as an explicit custom-command dependency.

The assertion migration is faithful. Exact-one versus one-or-more behavior,
dispatch identity, race type/access, wave/lane, and producer/intervening/
consumer trace checks match the pre-PR tests. The complete 42-case selection
passes after rebasing over the substantial recent rocJITsu changes.

At the architectural level, the approach is reasonable as an incremental
step. Earlier local experiments split the suite into many per-case source
files and introduced a larger runner/CMake framework; the submitted design
keeps the current build topology and centralizes only the duplicated policy.
It also creates one place to migrate away from text scraping later.

The new shared layer is nevertheless a real test API, not just moved code.
Its parser currently conflates “valid log with no findings” with “no readable
log” and accepts an incomplete final record. That can turn configuration,
plugin-loading, sink, or output-truncation failures into false greens. Because
the helper has no direct contract tests, the end-to-end happy-path suite does
not expose those cases. I would keep the overall design, but fix this boundary
before declaring the refactor ready.

## Actionable items

### 1. Make the shared log parser fail closed and test its format contract directly

**File:**

- `emulation/rocjitsu/tests/race-detector/race_test_support.hpp:69-121,198-216`

`parseRaceLog()` returns an empty vector when `RJ_SINK_DIR` is unset or when
`race.log` cannot be opened. `ExpectNoRace()` interprets that empty vector as a
passing no-race result. The parser also appends a record after EOF without
checking that `END_RACE` was observed.

Appendix A demonstrates all three cases. A sink configuration regression or
plugin startup failure can therefore make a safe test pass without producing
any evidence, and a terminated process can leave a partial race report that
the matcher accepts as complete.

Change the parser boundary so it distinguishes a valid finding set from a
format/input error. For example, return a result containing either parsed
records or an error string, then require:

- `RJ_SINK_DIR` to be set;
- `race.log` to open successfully;
- every `RACE` block to end with `END_RACE`;
- numeric fields to parse without exceptions; and
- fields required by an expectation to be present.

Make both `ExpectNoRace()` and `ExpectRace()` fail on parser/input errors.
Add fast host-side tests for at least:

- a valid zero-finding log;
- a valid one-finding log;
- an unset sink directory;
- a missing log file;
- an unterminated block;
- malformed integer fields; and
- missing producer/consumer markers when those fields are expected.

These tests should exercise the support code directly rather than requiring a
simulated HIP dispatch.

## Suggestions

### 1. Separate the pure log/matcher layer from the HIP fixture

**File:**

- `emulation/rocjitsu/tests/race-detector/race_test_support.hpp:6-7,69-177,179-196`

The same header contains pure text parsing, GoogleTest matchers, and HIP
allocation/synchronization helpers. A host-only parser probe therefore still
needs HIP headers and a platform macro.

Consider splitting it into:

1. a pure C++ race-log/expectation component with direct unit tests; and
2. a small HIP `RaceTestBase` wrapper for allocation, copies, and
   synchronization.

This keeps the format contract cheap to test and prevents HIP toolchain details
from becoming part of the parser API.

### 2. Rebase once more after the approved same-wave LDS fix lands

**Files:**

- `emulation/rocjitsu/tests/race-detector/CMakeLists.txt`
- `emulation/rocjitsu/tests/race-detector/hip_race_gfx950_test.hip`

The approved same-wave LDS ordering PR adds a new end-to-end case to these
files. Correctness work should not wait for this draft refactor. Let that fix
land first if it is ready, then rebase this branch and ensure its new case uses
the shared fixture consistently. The current branches merge textually, so this
is coordination and coverage hygiene rather than a conflict blocker.

## Commentary

### Big-picture design

The shared expectation object is useful, but it should not become the
long-term serialization format for race diagnostics. The plugin already emits
a partly structured `RACE` header, while producer/consumer instruction checks
still reverse-parse `==>` markers from the human-readable trace. The header
even carries `conflict=unknown` despite the plugin knowing the conflicting
event PC.

A stronger eventual boundary would emit a versioned machine-readable record
containing normalized race fields and producer/consumer PCs or mnemonics,
while keeping the formatted trace as presentation. The test helper would then
match structured data and reserve text assertions for a small set of rendering
tests. This should be follow-up work rather than an expansion of this focused
refactor; centralizing the current parser makes that future migration easier.

### Relationship to ongoing rocJITsu work

- The approved same-wave LDS ordering PR is a correctness change in the same
  test file and should take priority over this draft test-only refactor.
- The explicit-wave register-observation PR changes plugin callback ownership
  and race-detector integration but merges textually with this branch. Keeping
  this PR confined to test infrastructure limits coordination cost.
- The open sanitizer-corpus work increases the value of fail-closed test
  infrastructure: broader execution is useful only when missing or truncated
  diagnostic artifacts cannot be mistaken for success.
- The older sanitizer-corpus proposal overlaps the newer, more complete
  sanitizer work and is currently conflicting. It does not justify broadening
  this PR.

### Existing review feedback

There are no human reviewer comments or review threads on PR #9803. The only
GitHub discussion is automated policy output. No GitHub replies, review
comments, or thread-state changes are needed.

## Appendix A: missing and truncated race-log probe

Compile from the repository root:

```bash
c++ -x c++ -std=c++20 -O0 -D__HIP_PLATFORM_AMD__ \
  -Iemulation/rocjitsu/tests/race-detector \
  -I$BUILD_DIR/_deps/googletest-src/googletest/include \
  -I$ROCM_PATH/include \
  -o /tmp/pr9803_parser_probe - <<'EOF'
#include "race_test_support.hpp"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>

int main() {
  using rocjitsu::test::parseRaceLog;

  unsetenv("RJ_SINK_DIR");
  std::cout << "unset=" << parseRaceLog().size() << '\n';

  setenv("RJ_SINK_DIR", "/tmp/pr9803-does-not-exist", 1);
  std::cout << "missing=" << parseRaceLog().size() << '\n';

  const std::filesystem::path dir = "/tmp/pr9803-truncated-log";
  std::filesystem::create_directories(dir);
  std::ofstream file(dir / "race.log");
  file << "RACE kernel=k symbol=s dispatch=1 type=VGPR access=read "
          "reg=2 wave=0 lane=0 wg=0,0,0 conflict=unknown\n"
          "Race on VGPR v2 [workgroup (0, 0, 0), wave 0, lane 0]\n"
          "  ==>  0x100  global_load_dword v2, v[0:1], off\n"
          "  ==>  0x104  global_store_dword v[0:1], v2, off\n";
  file.close();

  setenv("RJ_SINK_DIR", dir.c_str(), 1);
  const auto truncated = parseRaceLog();
  std::cout << "truncated=" << truncated.size()
            << " body_bytes="
            << (truncated.empty() ? 0 : truncated.front().message.size())
            << '\n';
}
EOF

/tmp/pr9803_parser_probe
```
