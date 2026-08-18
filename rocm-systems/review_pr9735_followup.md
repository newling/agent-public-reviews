This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9735](https://github.com/ROCm/rocm-systems/pull/9735)

**Revision reviewed:** local rebased head `ac30e3bc1f`, a four-commit stack
based directly on `origin/develop@59ffe1b933`. The top commit addresses the
latest documentation and test-helper feedback.

**Review mode:** fresh full review after the latest requested changes. I
re-read the complete seven-file PR diff, all current GitHub review feedback,
the production call paths, event lifecycle and wait-counter handling, the
public guide, and the directly affected tests. I did not rely on the earlier
review's conclusions.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The published PR head is open, non-draft, mergeable, and still requires
review. The rebased head reviewed here has not been pushed.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests tests/race-detector/hip_race_tests_gfx950 \
  --parallel 8
```

Result: all 23 rebuild steps passed in 16.25s real, 74.52s user, and 10.89s
sys.

**Race-detector core tests:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RaceDetector.*'
```

Result: 79/79 passed, 0 failed, 0 skipped, and 0 errored in 0.03s real.

The selection covers the changed same-wave ordinary-DS ordering contract,
LDS-read destination-VGPR completion, cross-wave RAW and WAR barrier behavior,
direct-to-LDS missing/full/partial `vmcnt` behavior, active-lane interval
tracking, event retirement, and mixed wait counters.

**Focused gfx950 integration tests:**

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure \
  -R '^RaceTest\.gfx950_(lds_same_wave_order|lds_cross_wave|lds_cross_wave_race|global_to_lds_buffer|global_to_lds_buffer_race|partial_vmcnt_race)$'
```

Result: 6/6 passed, 0 failed, 0 skipped, and 0 errored in 1.27s real.

**Generated gfx950 code inspection:**

The submitted write/read kernel keeps the outstanding write source distinct
from the later read destination:

```asm
ds_write_b8 v0, v1
ds_read_u8 v3, v2
s_waitcnt lgkmcnt(0)
```

The submitted read/write kernel likewise keeps the read destination distinct
from the later write address and data:

```asm
ds_read_u8 v2, v3
ds_write_b8 v0, v4
s_waitcnt lgkmcnt(0)
```

This confirms that the early-clobber constraints requested in the earlier
review are effective and that the integration test still exercises the
intended operations.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files <all seven changed files>
git diff --check <pr-base>
```

Result: all applicable hooks passed in 0.46s real, and `git diff --check`
passed.

**GitHub CI:**

On the previously published head, release, Clang ASan/UBSan, TSan, formatting, policy,
setup, and the completed Windows compiler-runtime stage pass. The GCC
ASan/UBSan corpus job failed because one unrelated gfx1250 DBT translation
exceeded its 180-second timeout after the same job's 2,878-test unit run
passed. Several broad packaging stages were still queued at review time.

I did not rerun the broad simulator or corpus suites locally. The follow-up
changes one documentation summary, one implementation comment, and two
test-helper signatures; the focused unit and gfx950 tests exercise the
affected contracts directly, while the published CI supplies broader evidence
for the unchanged production implementation.

## Summary

The PR corrects the detector's treatment of ordinary LDS operations issued by
one wave. `validateRead()` now recognizes that a later ordinary DS read cannot
overtake an earlier ordinary DS write from the same wave. It continues to
report an overlapping same-wave direct-to-LDS write until the owning wave's
`vmcnt` wait completes. Another wave continues to see either write event as
live until a workgroup barrier retires it.

`validateWrite()` similarly recognizes that a later ordinary DS write cannot
overtake an earlier ordinary DS read from the same wave. This suppression is
limited to the LDS WAR check. The LDS read's destination VGPR remains tracked
independently until `lgkmcnt` permits it to be consumed or overwritten.

The event lifecycle remains coherent across those cases. An owning-wave wait
marks the matching event `WAVE_COMPLETE`; LDS-touching events remain in the
workgroup's live LDS lists until barrier retirement. The direct-to-LDS partial
wait test pins in-order VMEM draining: after two events and `vmcnt(1)`, the
older destination range is readable by the owning wave while the newer range
still reports.

The follow-up documentation now describes the implemented LDS categories
without conflating them:

- cross-wave RAW: read versus an outstanding write;
- cross-wave WAR: write versus an outstanding read;
- same-wave RAW against an active direct-to-LDS operation; and
- no current LDS WAW detection.

The production comment beside `validateWrite()` states the same WAW
limitation. This agrees with the API documentation and the guide's existing
limitations section.

The test helper now has an honest single-lane contract. `ldsWrite()` and
`ldsRead()` no longer accept an `exec` argument that they silently replace
with `1ULL << lane`. Callers needing a real wave mask continue to use
`globalToLds()`, which forwards its mask into interval construction. A
repository-wide search found no caller that depended on the removed
parameters.

The HIP integration test covers cross-lane write/read and read/write ordering,
checks the resulting values, and requires no race report. The generated code
retains distinct early-clobber destinations, so the test does not accidentally
overwrite an outstanding DS source operand.

I found no remaining actionable correctness, test, documentation, or
maintainability issue in the post-fix PR.

## Actionable items

None.

## Suggestions

None.

## Commentary

### Contract and counterexample pass

The important boundaries all have direct evidence:

- An active ordinary same-wave DS write followed by a DS read is accepted for
  both same-lane and cross-lane overlap.
- An active ordinary same-wave DS read followed by a DS write is accepted for
  both same-lane and cross-lane overlap.
- Consuming an LDS read's destination VGPR without `lgkmcnt` still reports.
- Reading an active same-wave direct-to-LDS destination without `vmcnt`
  reports, while `vmcnt(0)` makes it safe for the owner.
- `vmcnt(1)` over two direct-to-LDS events retires only the older event.
- Another wave still reports against an LDS event after its owner's wait and
  becomes safe only after barrier retirement.
- Cross-wave RAW and WAR are documented and tested independently.
- LDS WAW is explicitly documented as unsupported rather than accidentally
  advertised.
- Inactive direct-to-LDS lanes do not create intervals at the helper's padded
  zero addresses.

### Existing review feedback

All current review requests are reflected in the post-fix diff:

- both multi-instruction HIP output operands are early-clobber;
- successful same-wave read/write tests check the complete violation set;
- event-status comments remain lifecycle-oriented;
- direct-to-LDS behavior is documented as a read-side `vmcnt` requirement;
- partial-`vmcnt` and active-lane interval tests are present;
- ineffective single-wave exec-mask tests were replaced;
- the guide and production comment no longer claim LDS WAW detection; and
- the two ignored single-lane helper `exec` parameters were removed.

Three older GitHub threads remain unresolved even though their requested source
changes are present. The newest documentation feedback was added to a thread
that GitHub still marks resolved. Those interface states require reviewer
communication but do not indicate missing code in the reviewed patch.

### Scope boundaries

The PR does not add LDS WAW detection, same-instruction lane-collision
detection, or general inter-workgroup race detection. Those are existing,
documented limitations and do not need to be implemented by this focused
same-wave ordering correction.

### Current base

The reviewed four-commit stack is based directly on
`origin/develop@59ffe1b933`. `git range-diff` reports all four patches
identical to the pre-rebase stack.
