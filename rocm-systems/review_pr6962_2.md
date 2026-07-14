This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#6962
**Commit reviewed:** `782b5a436b` (`fix(rocjitsu): resolve rebase integration`)
**Previously reviewed head used for comparison:** `7b70cba829`

**Diff hygiene:**

```bash
git diff --check origin/develop...782b5a436bbfa3d1861022097f4bf54212a01688 -- emulation/rocjitsu
```

Result: passed with no whitespace errors.

I did not run a local checkout/build for this second-pass review because the
current PR head already fails required GitHub CI at compile time. Relevant CI
status at review time:

- `test (release)`: passed.
- `test (asan-ubsan)`: passed.
- `test (asan-ubsan-gcc)`: failed in the `Build rocjitsu` step.
- TheRock Linux package builds for gfx94X, gfx950, and gfx125X: failed. The
  gfx950 package log shows the same rocjitsu compile error described below.

The failing GCC build reports:

```text
emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:742:27:
error: left shift count >= width of type [-Werror=shift-count-overflow]
```

## Summary

Since the previous review, the PR was rebased and the DBT executable-range
helper was removed from this diff. The current PR no longer changes
`kernel_descriptor_translator.cpp` or `tests/dbt/translate_test.cpp` relative
to `develop`, so the earlier split-out request appears to be addressed.

The plugin serialization behavior is now documented in both
`execution_plugin_group.h` and `docs/plugins.md`: non-empty plugin groups clamp
each command processor's CU-dispatch worker pool to one thread by default, and
the race detector keeps that serial default because its full per-workgroup hook
path has not been validated with concurrent CU callbacks in one Simdojo
partition.

The dispatch-placement clarification was also addressed. The docs now explain
that `cpu_dispatch_threads` controls host-side execution of already accepted CU
work, not which SPI or CU accepts the next workgroup. The code now iterates SPIs
for placement independently of the host worker-pool size, and a regression test
checks that dispatch placement does not follow host thread count.

## Actionable items

### 1. Fix the GCC build failure in the new full-lane-mask helper

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:742`

The latest integration commit tries to avoid instantiating `1 << 64` by putting
the full-lane-mask calculation in an `if constexpr` lambda:

```cpp
constexpr uint64_t full_lane_mask = [] {
  if constexpr (Isa::WF_SIZE >= 64)
    return ~uint64_t{0};
  return (uint64_t{1} << Isa::WF_SIZE) - 1;
}();
```

This still fails under the GCC ASAN/UBSAN build because the shift expression is
a separate statement after the `if constexpr`, not the discarded `else`
substatement. For wave64 ISAs GCC diagnoses `uint64_t{1} << 64` and the build
stops under `-Werror=shift-count-overflow`.

Please put the shift path in an `else` branch, or move the calculation to a
helper with the same `else` structure, so the invalid shift expression is not
formed for wave64 instantiations:

```cpp
constexpr uint64_t full_lane_mask = [] {
  if constexpr (Isa::WF_SIZE >= 64) {
    return ~uint64_t{0};
  } else {
    return (uint64_t{1} << Isa::WF_SIZE) - 1;
  }
}();
```

## Suggestions

None.

## Commentary

The earlier review discussion about splitting orthogonal DBT work and
documenting plugin serialization looks addressed in the current diff.

One process blocker remains outside this PR's code: the separate TSAN CI support
PR referenced by another reviewer is still open, so that earlier request to land
TSAN support first is not resolved yet.
