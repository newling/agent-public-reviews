This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8075
**Commit reviewed:** `d7961030920` (`Merge branch 'develop' into mfma-plugin-read-observation`)

**Build command:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

**Build result:** passed. The target rebuilt 410 steps and completed in 117.50s
real time.

**Focused test command:**

```bash
time -p ctest --test-dir $BUILD_DIR -R 'ExecutionPluginTest|RaceDetector|MfmaExecTest|Vop2FmaF64SimdCorrectness' --output-on-failure --timeout 60
```

**Focused test result:** 89/90 passed, 0 failed, 1 skipped, 0 errored. CTest
reported 1.57s real time. The skipped test was
`ExecutionPluginTest.MfmaFastPathReadHookReportsRace`, which requires a
16-lane `native<float>` SIMD path that is not available on this host. The run
covered the new lane-mask execution-plugin hook tests, the new masked VGPR
race-detector unit test, existing MFMA location tests, and nearby f64 SIMD lane
layout coverage.

**Additional checks:**

```bash
git diff --check origin/develop...HEAD
```

passed with no whitespace errors.

**CI status at review time:** `pre-commit`, `test (release)`, `test
(asan-ubsan)`, TheRock CI summary, package build jobs, and `therock-pr-bot`
were passing. Several matrix jobs were intentionally skipped.

## Summary

This PR makes instruction-visible SIMD VGPR reads observable to execution
plugins when the emulator takes raw/fast storage paths. It changes the VGPR-read
plugin callback from a contiguous lane range to an arbitrary lane mask, renames
the raw VGPR storage accessors to make hook-bypassing explicit, and adds MFMA
fast-path read observation before the SIMD kernels load A, B, and accumulator
register regions through raw pointers.

The race detector is updated to consume lane masks directly, so bulk MFMA reads
can report a representative conflicting lane without expanding every lane into a
separate callback. The tests cover the new callback shape, a masked race
detector conflict, direct MFMA observation helper behavior, and the actual MFMA
fast path when the host SIMD width supports it.

## Actionable items

None.

## Suggestions

### 1. Clean up a duplicated word in the benchmark comment

**File:** `emulation/rocjitsu/tests/mfma_simd_benchmark.cpp:541`

The comment now says `raw raw_vgpr_data`. This is harmless, but it is a
copy-edit artifact from the accessor rename. Consider changing it to
`raw_vgpr_data` or "raw VGPR data" while touching the branch.

## Commentary

The lane-mask callback is a better API for the SIMD paths than the old
`lane_begin`/`lane_end` pair. Existing SIMD helpers can report partial and
non-contiguous active lane sets without forcing plugins to infer them, and the
MFMA helpers can report each dense source region with one callback per physical
VGPR rather than one callback per lane.

The raw accessor rename is also useful. The code now makes the important
distinction explicit: `read_vgpr()` is observed, while `raw_vgpr_data()` and
`raw_vgpr_reg()` deliberately bypass plugin hooks and require the caller to
notify plugins separately when the access is instruction-visible.

The one residual local test gap is host-dependent: the actual
`exec_f32_mfma_f16_spec` fast-path race test skipped here because this machine
does not expose the required 16-lane native float SIMD shape. The helper-level
tests and green CI cover the portable part of the change, but a host with that
SIMD width remains the best place to exercise the end-to-end fast path.
