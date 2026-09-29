This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#12467](https://github.com/ROCm/rocm-systems/pull/12467)

**Reviewed head / suggestion base:** [`f3e748b38041647d85f68f2a02bb77217948ea31`](https://github.com/ROCm/rocm-systems/commit/f3e748b38041647d85f68f2a02bb77217948ea31)

**Suggestion branch:** [`review/pr12467-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr12467-suggestions)

**Commit mapping:** [`992494b5f25bb4d3e4726ff3ee31844b0cec1ca9`](https://github.com/newling/rocm-systems/commit/992494b5f25bb4d3e4726ff3ee31844b0cec1ca9) — item 1, update the sparse-WMMA NaN expectation. The commit message links back to this review.

## Tests

The Clang 23 Release build, focused native and forced-scalar instruction tests, changed Python generator tests, and an independent exact-rational mixed-FMA rounding check passed. The submitted head fails the expensive sparse-WMMA test described in item 1; after the suggestion, that test and the related F16 conversion/K64 NaN tests pass, as do changed-file pre-commit hooks and the diff check.

The floating-point selection covered guest rounding and denormal modes, exceptional values, modifiers, packed operations, cube instructions, and conversions. Operand and memory checks covered DPP half-register observations, true16 execution, image-extension decoding, inline buffer offsets, direct LDS broadcasts, and translated atomics. The Python tests used machine-readable ISA inputs extracted from the reviewed commit. The separate rational-arithmetic experiment compared finite F32-source FMA results directly rounded to F16 against both new implementations in all four rounding modes, without using either implementation as its reference.

No physical-GPU differential or performance campaign was run. Full ISA regeneration and the exhaustive matrix suites were not run; the relevant sparse-WMMA cases were selected because they consume the changed F16 narrowing helper. Unsupported instruction/architecture combinations account for the focused tests' skips.

## Summary

The change moves F32 arithmetic toward explicit architectural NaN selection and tininess handling, retains the addition residual when rounding F16 and mixed FMA results, and makes scalar and SIMD paths share those policies. It also corrects cube-axis selection, floating source modifiers, packed half-register resolution, image instruction sizing, inline buffer offsets, and several memory-operation behaviors.

The strongest aspects are the explicit bit-level treatment of exceptional values and the decoded regressions that distinguish guest MODE from the host floating-point environment. The mixed-FMA implementation retains information that an intermediate F32 result would lose, and the independent arithmetic check supports that design. Register-observation tests also check physical halves and source lanes, rather than only final arithmetic values. I found one missed downstream test update and no further runtime defect in the inspected and exercised paths.

## Actionable items

### 1. Update the sparse-WMMA NaN expectation for the new narrowing policy

**Location:** [`emulation/rocjitsu/tests/simd_correctness/wmma_simd_exact_test.cpp:520`](https://github.com/ROCm/rocm-systems/blob/f3e748b38041647d85f68f2a02bb77217948ea31/emulation/rocjitsu/tests/simd_correctness/wmma_simd_exact_test.cpp#L520), following the policy change in [`emulation/rocjitsu/lib/util/include/util/data_types.h:103`](https://github.com/ROCm/rocm-systems/blob/f3e748b38041647d85f68f2a02bb77217948ea31/emulation/rocjitsu/lib/util/include/util/data_types.h#L103).

`WmmaSimdExact.SparseK128NaNPayloadsMatchScalar` still expects `0x7e01` for the packed F16 result. Its BF8 source expands to the F32 NaN `0x7fc00000`. Under the new `f32_to_f16` contract, that narrows to `0x7e00`: the retained quiet bit already keeps the result distinct from infinity, so there is no reason to add payload bit zero. The scalar/SIMD equality check passes; the stale final constant fails.

This is the sole failing test reported by both the [ASan/UBSan job](https://github.com/ROCm/rocm-systems/actions/runs/36594414530/job/109495549999) and the [GCC UBSan job](https://github.com/ROCm/rocm-systems/actions/runs/36594414530/job/109495550096). It also reproduces in the local unsanitized Release build, with actual decimal `32256` and expected `32257`. The test is compiled only with `RJ_ENABLE_EXPENSIVE_CHECKS=ON`, which explains why the default local selection does not catch it.

Change the expectation to `0x7e00` and retain the scalar/SIMD equality assertion. This follows the same payload-preservation policy already reflected in the PR's K64 sparse-WMMA regression updates. [Fix commit `992494b5f2`](https://github.com/newling/rocm-systems/commit/992494b5f25bb4d3e4726ff3ee31844b0cec1ca9) changes only this expectation and adds a short explanation. The previously failing test and the related F16 conversion/K64 NaN selection pass with this change; publication only amended the commit message to link back to the review, leaving the tested source tree unchanged.

To reproduce on an otherwise configured build:

```sh
cmake -S "$SRC_DIR/emulation/rocjitsu" -B "$BUILD_DIR" -DRJ_ENABLE_EXPENSIVE_CHECKS=ON
cmake --build "$BUILD_DIR" --target rocjitsu_tests --parallel 8
"$BUILD_DIR/tests/rocjitsu_tests" --gtest_filter=WmmaSimdExact.SparseK128NaNPayloadsMatchScalar
```

## Suggestions

None beyond the concrete test correction above.

## Commentary

The changed ownership and fallback paths have useful direct coverage: packed operands resolve storage and observations to the same physical register, image decoding owns the extension word and preserves the next instruction boundary, and translated packed atomics retain the existing compare-exchange retry mechanism. The numerical helpers are also tested independently of decoded execution. These checks address the main cross-module risks without requiring unrelated subsystem suites.

Handoff: [branch `review/pr12467-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr12467-suggestions), with [commit `992494b5f2`](https://github.com/newling/rocm-systems/commit/992494b5f25bb4d3e4726ff3ee31844b0cec1ca9) implementing item 1 and passing the focused validation above. The branch and this review are published with reciprocal links. No actionable item was omitted from implementation; hardware qualification and broader performance measurements remain outside this review.
