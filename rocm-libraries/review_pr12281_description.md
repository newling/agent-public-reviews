JIRA ID : ROCM-31016

## Motivation

hipBLASLt selects a GPU kernel for each matrix multiplication using host-side compatibility checks. The output-store check allowed some shapes whose writes exceed the kernel's buffer descriptor limit, so a call could return success with part of the output unwritten. This addresses the generated-kernel limit mismatch investigated from [ROCm/hipBLASLt#2299](https://github.com/ROCm/hipBLASLt/issues/2299).

## Technical Details

`BufferStoreOffsetLimitCheck` now compares the required output extent against `0xfffff000`, matching the `BufferOOB` value emitted by the assembly generator, instead of `2^32`. It retains the extent formula `ldd * min(MacroTile1, N) * elementBytes`: each workgroup advances its descriptor base along N, so only its tile's column range must fit. The strict comparison deliberately rejects equality as a conservative boundary choice.

The diagnostic now reports the same clamped extent used by the predicate. Generated instructions and the stored solution-library format are unchanged; rebuilding the host library applies the new check to existing libraries. Hand-written kernels with their own smaller sentinel remain outside this fix and are tracked in ROCM-31258.

## Test Plan

Run the C++ predicate regressions in `tensilelite-tests` for extents below, at, and above the sentinel, the originally reported shape, and output narrower than a tile. Compare selection and output completeness on the measured gfx950 boundary shapes.

## Test Result

The five regressions pass locally and in the public gfx94X TensileLite job. Restoring the old threshold makes the past-sentinel and exact-sentinel tests fail. Broader automated checks have mixed results; see the current checks for details.

The reported gfx950 measurement, using the same tuned library for both builds, tested the first 64 offered algorithms at bf16 `M = ldd = 8,388,607`, `N = 256`, `K = 48`. Partly unwritten outputs fell from 22 to zero. At `M = 8,388,599`, all tested algorithms remained clean and the candidate count was unchanged.

## Submission Checklist

- [ ] Look over the contributing guidelines at https://github.com/ROCm/TheRock/blob/main/GOVERNANCE.md#pull-requests.

## Risk level

Low (2/5). Host selection becomes stricter only for extents in the 4,096-byte interval from `0xfffff000` through `2^32 - 1`. This can remove candidates, including the deliberately conservative equality case; shapes outside that interval retain the same result from this predicate.
