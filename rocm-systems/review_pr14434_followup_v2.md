This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#14434](https://github.com/ROCm/rocm-systems/pull/14434)

**Reviewed head:** [`b819930a0c2d43f3e9f5bad71a1deeabd4d0677b`](https://github.com/ROCm/rocm-systems/commit/b819930a0c2d43f3e9f5bad71a1deeabd4d0677b), reverified on 2026-10-28. The repository and PR branch are public.

**Scope:** Follow-up on the [original review](https://github.com/newling/agent-public-reviews/blob/main/rocm-systems/review_pr14434.md) and the subsequent requested comments. This includes independently checking the live review discussion and affected implementation; it does not repeat the full original review.

**Local suggestion branch:** `review/pr14434-followup-v2`, based on the exact reviewed head. It has no additional commits: the bounded fixes are already incorporated, and the remaining LDS allocation policy is explicitly deferred. The previous review files and suggestion branches are preserved.

## Tests

Clang 23.1 Release builds `rocjitsu_tests`; focused scalar F16, vector16/BF16 inline, DOT2, RDNA4 FLAT bounds, routed observation/race interval and CDNA4-to-CDNA3 BF16 execution-oracle checks pass, as do the selected generator, lowering and ISA-profile regressions.

The RDNA4 pseudo-scalar inline case skips because its decoder still rejects those selectors, an existing documented gap. Legacy RDNA1/2 OPSEL cases also skip; the CDNA5-specific BF16 contract test skips on other architectures. No fresh physical-GPU qualification or broad corpus run was performed. The prior hardware evidence remains the basis for the expected results; CDNA5 pseudo-scalar behavior remains an extrapolation.

At the final CI check, TSan, GCC UBSan, pre-commit and presubmit fuzz passed. Release was in progress and ASan/UBSan was queued. The PR policy bot still reports a missing issue/JIRA reference. These are separate from whether the code review comments were addressed.

## Summary

The original review feedback is addressed at this head: the two behavior issues are fixed, and the allocation-granule issue uses the explicitly offered documentation fallback. The added regressions check decoded operand reads as well as execution, and distinguish inline DOT2 accumulators from register/literal carriers and ordinary FMA behavior.

## Actionable items

No outstanding actionable items from the reviewed comments remain within this follow-up's scope.

## Suggestions

No additional suggestions from this follow-up.

## Commentary

### Original review status

Paths below are relative to `emulation/rocjitsu/` and refer to the reviewed head.

| Original item | Status and evidence |
| --- | --- |
| Keep raw F16 pseudo-scalar inline carriers | Fixed. `lib/python/amdisa/codegen/_generator.py:1367`, `:6793` and `:12895` share a pseudo-scalar policy between scalar lowering and decoded source metadata. Generated CDNA5 execution reads the raw scalar carrier; `tests/scalar_f16_constant_test.cpp:291` covers all nine floating selectors and both denormal modes. Its helper at `:165` also checks F32 metadata and scalar/lane/chunk agreement. |
| Derive the RDNA4 FLAT bound from the hardware LDS granule, or document the limitation if deferred | Documentation fallback implemented. `lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:1012` explicitly describes current 256-byte scheduler rounding and unmodeled target granules. `docs/plugins.md:500`, `docs/race-detector.md:231` and `lib/rocjitsu/src/rocjitsu/vm/plugins/memory_access_observation.h:225` explain the modeled bound, possible prior PM4 rounding, complete-element clipping and nominal masks/counters. Hardware allocation/admission granules are still deferred; the measured 4,100-byte group-segment case is not claimed fixed. |
| Replicate inline DOT2 src2 before high-half OPSEL | Fixed. `lib/python/amdisa/codegen/execute/packed.py:1385` replicates inline accumulator halves before selection, and the generated RDNA3/RDNA3.5/RDNA4 executors contain that rule. `tests/vector16_inline_constant_test.cpp:510` covers all floating selectors, both OPSEL settings and empty/sparse/full EXEC; later tests cover integer inlines, register/literal controls, DPP and unchanged FMA high-half behavior. |

### Subsequent comment status

The later requested cleanups are also present: the unused delegated inline-resolution hook is removed; F16/BF16 resolvers document their selector and raw-carrier contracts and share `is_inline_float_src`; `resolve_src_scalar16` requires its format argument; the enum uses `F32`; fixture members and the restoration guard follow the requested conventions; and execution/race clipping shares `whole_element_bytes_in_range`.

The new VALU16 destination and BF16 carrier policies live on `IsaProfile` and have direct profile tests. CDNA4-to-CDNA3 conversion reuses `resolve_inline_bfloat16_statically`, retaining the independent execution oracle. CDNA5 VOP1 BF16 behavior cites the chosen LLVM interpretation and has execution coverage for VOP1 and both VOP3 halves, including inverse-two-pi. The scalar F16 lowering map is renamed and documents that membership enables numeric formatting while the boolean selects the carrier half.

The local branch contains no proposed changes or commit mapping. Architecture-specific LDS allocation/encoding granules, DS bounds, RDNA4 pseudo-scalar inline decoding and aperture classification before IOFFSET remain the documented separate work; none was silently treated as implemented. No GitHub PR review, comment, description or thread state was changed.
