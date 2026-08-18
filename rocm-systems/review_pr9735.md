This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9735](https://github.com/ROCm/rocm-systems/pull/9735)

**Commit reviewed:** `dc44f025a6b3` (`test(rocjitsu): strengthen same-wave
LDS coverage`), the current PR head.

**Review mode:** second comment-aware follow-up. I independently reviewed the
complete three-commit diff and evaluated all current GitHub feedback against
the current head: seven inline review threads containing nine comments, plus
one top-level review comment.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, and GitHub reports it as mergeable with
review still required.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests tests/race-detector/hip_race_tests_gfx950 \
  --parallel 8
```

Result: all 56 build steps passed in 27.25s real, 184.45s user, and 9.32s
sys.

**Race-detector core tests:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RaceDetector.*'
```

Result: 79/79 passed, 0 failed, 0 skipped, and 0 errored in 0.02s real.
This includes the submitted same-lane and cross-lane ordinary-DS ordering
cases, missing/full/partial direct-to-LDS `vmcnt` cases, exec-mask interval
coverage, cross-wave barrier cases, and LDS-read destination-VGPR hazards.

**Focused gfx950 integration tests:**

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure \
  -R '^RaceTest\.gfx950_(lds_same_wave_order|lds_cross_wave|lds_cross_wave_race|global_to_lds_buffer|global_to_lds_buffer_race|partial_vmcnt_race)$'
```

Result: 6/6 passed, 0 failed, 0 skipped, and 0 errored in 1.26s real.

**Generated gfx950 code inspection:**

I extracted and disassembled the submitted HIP test executable. The
write/read kernel uses distinct registers for the outstanding write source and
read destination:

```asm
ds_write_b8 v0, v1
ds_read_u8 v3, v2
s_waitcnt lgkmcnt(0)
```

The read/write kernel likewise keeps the read destination distinct from the
later write's address and data inputs:

```asm
ds_read_u8 v2, v3
ds_write_b8 v0, v4
s_waitcnt lgkmcnt(0)
```

This confirms that the two `=&v` fixes requested in review are effective in the
generated test and that register aliasing no longer weakens the intended
ordering coverage.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files <all six changed files>
git diff --check <pr-base>..HEAD
```

Result: all applicable pre-commit hooks passed in 0.45s real,
`git diff --check` passed, and the reviewed source checkout has no tracked
modifications.

**Temporary test-helper cleanup:**

I temporarily removed the unused `exec` parameters and dead defaulting logic
from `RaceTestBuilder::ldsWrite()` and `RaceTestBuilder::ldsRead()`, rebuilt
`rocjitsu_tests`, and reran `RaceDetector.*`. The incremental build passed in
3.31s real and all 79 tests passed in 0.02s real. I then removed the temporary
change. This confirms that the cleanup requested in the latest review is
self-contained and has no current caller impact.

**GitHub CI:**

The release, Clang ASan/UBSan, TSan, formatting, policy, and setup checks pass
on this head. The GCC ASan/UBSan corpus job failed because one unrelated
gfx1250 DBT translation exceeded its 180-second timeout. The same job's
preceding unit run passed 2,878/2,878 tests, and the timeout occurred in a
DBT corpus hash with no connection to the race-detector files changed here.
Several broad packaging jobs were still queued or running at review time.

## Summary

The PR corrects the race detector's ordering model for ordinary LDS
instructions issued by one wave. A later ordinary DS read now ignores an
active same-wave ordinary DS write because the read cannot overtake that write
in the LDS pipeline. A later ordinary DS write similarly ignores an active
same-wave DS read. The events remain live for other waves until a workgroup
barrier, so cross-wave RAW and WAR checks retain their existing behavior.

The change does not weaken the separate destination-register contract of an
LDS read. `LDS_TO_VGPR` events remain attached to their destination VGPRs until
`lgkmcnt` drains them, so consuming or overwriting the destination too early is
still reported.

Direct-to-LDS VMEM writes retain a distinct contract. A same-wave ordinary DS
read still reports while an overlapping `GLOBAL_TO_LDS` event is active and
becomes safe only when `vmcnt` retires that event for the owning wave. A
different wave continues to require the workgroup barrier even after the
owner's `vmcnt` wait. The new partial-`vmcnt` test also pins the in-order drain:
after two direct-to-LDS events and `vmcnt(1)`, the older range is readable and
the newer range remains hazardous.

The documentation correctly narrows the same-wave direct-to-LDS requirement to
**reading** destination bytes rather than broadly claiming that every access is
checked. However, its general LDS summary still says that a byte may be "read
or written" while another wave has an outstanding write. The implementation
does not check an incoming LDS write against `ldsWriteEvents`, so the "or
written" claim incorrectly advertises cross-wave LDS write/write detection.

The gfx950 integration test covers both cross-lane write-then-read and
read-then-write ordering and verifies the observed values as well as the lack
of a detector report. The early-clobber constraints make the inline assembly
contract valid, and the generated code confirms that the relevant operands do
not alias.

I found one actionable documentation issue and one lower-priority test-helper
cleanup.

## Actionable items

### 1. Do not claim LDS write/write detection that is not implemented

**Files:**

- `emulation/rocjitsu/docs/race-detector.md:153-156`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp:111-115`

The guide says the plugin reports when an LDS byte is "read or written" while
another wave has an outstanding write. `validateWrite()` only scans
`ldsReadEvents`; it never compares an incoming write with either an ordinary
DS or direct-to-LDS event in `ldsWriteEvents`. The nearby source comment also
says the WAR check does not cover write/write ordering "against
`GLOBAL_TO_LDS` events", which implies ordinary-DS write/write ordering is
covered even though it is not.

Remove "or written" from the guide's outstanding-write case. Change the source
comment to state that LDS write/write ordering is not checked, without
restricting that limitation to `GLOBAL_TO_LDS`. This keeps the public contract
and implementation comment aligned with the detector's actual RAW/WAR scope.

## Suggestions

### 1. Remove the ignored `exec` parameters from the single-lane test helpers

**File:**

- `emulation/rocjitsu/tests/race-detector/race_test_builder.h:77-105`

`ldsWrite()` and `ldsRead()` accept an optional `exec`, replace zero with
`defaultExec_`, and then ignore the result by always registering
`1ULL << lane`. No current caller supplies either parameter after this PR
replaces the misleading single-wave `Exec_*` cases.

Remove both parameters and their dead defaulting blocks. Tests that need a
wave-level mask should continue using `globalToLds()`, whose `exec` argument is
actually forwarded. The temporary cleanup described above compiled and passed
all 79 `RaceDetector.*` tests.

## Commentary

### Existing review comments

All earlier requested code and test changes are present at the current head:

- Both inline-assembly read destinations use early-clobber `=&v`, and the
  generated gfx950 code keeps them distinct from later-used inputs.
- The direct-to-LDS documentation is narrowed to same-wave reads and the
  detected same-wave case is included in the summary.
- Both successful read/write core tests use `EXPECT_FALSE(b.hasRace())`.
- `EventStatus` comments describe lifecycle state rather than embedding the
  ordinary-DS ordering policy.
- The direct-to-LDS tests include two disjoint events and a partial
  `vmcnt(1)` drain.
- The four ineffective single-wave `Exec_*` tests are replaced by a
  direct-to-LDS active-lane interval test using an explicit one-lane mask.

GitHub marks the four first-round threads resolved. Three second-round threads
remain unresolved in the interface, but their requested early-clobber,
partial-`vmcnt`, and exec-mask changes are all implemented. They appear to
need only reviewer-facing replies and thread resolution, not further source
changes.

The latest review added two valid follow-ups:

- A new reply on the already-resolved documentation thread identifies the
  overclaim about LDS write/write detection. This requires the documentation
  and source-comment correction listed above even though GitHub still marks
  the containing thread resolved.
- A top-level review comment asks to remove the ignored `exec` parameters from
  the two single-lane test helpers. That cleanup is valid and self-contained.

### Scope boundaries

The implementation intentionally does not perform same-wave
direct-to-LDS-versus-DS write/write detection, general cross-wave LDS
write/write detection, or same-instruction cross-lane collision detection.
Those are separate access categories. The general cross-wave write/write
limitation needs the documentation correction above; the unsupported
categories themselves do not need to be implemented by this focused ordering
PR.

### Current base

At review time the head was two commits behind current `origin/develop`.
Neither intervening commit touches any of the six files changed here, and a
synthetic merge with current `origin/develop` completed cleanly.
