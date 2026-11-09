This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#15345](https://github.com/ROCm/rocm-systems/pull/15345)

**Reviewed head:** `95bbe164a44429306eab63b7fb12d64e42c4f62b`

**Diff base:** `a421bbf67239360c4aa9862a76e6c5ad6da160ef`

**Mode and scope:** Independent review of instruction execution, generated semantics and operand metadata, memory-wait footprints, CDNA4-to-RDNA translation, and the changed tests. The corpus pin change was inspected, but the corpus and physical-GPU experiments were not repeated. Existing PR discussion was not used.

**Suggestion branch:** [review/pr15345-suggestions](https://github.com/newling/rocm-systems/tree/review/pr15345-suggestions), based on the exact reviewed head. Commits: [1c121ea6bda](https://github.com/newling/rocm-systems/commit/1c121ea6bdaf64071eddcf09e33e338edd678f1e) for the overlap fix and regression coverage; [31cd621e8a6](https://github.com/newling/rocm-systems/commit/31cd621e8a6ea29a299907197ccd22aae664642e) for generated-output and comment cleanup.

## Tests

At the submitted head, the generator suite passed 3,531 tests with 46 skips; the focused native selection passed 1,263 tests with 33 skips, and all 169 selected FP conversion tests passed. An added partial-overlap regression failed on both RDNA3 and RDNA4. On the suggestion tree, all 72 focused translation, liveness, and packed-integer tests passed, including the regression and a case that forces scratch storage to overlap the destination. Full ISA/DBT regeneration matched the submitted output except for one unused helper described below; three checks of generated shared calls and image metadata passed. Changed-file pre-commit checks passed.

The local Clang 23 release build initially failed with `-Werror,-Wunused-template` in the unchanged `util_intrusive_shared_ptr_test.cpp:68`. Validation used a temporary, build-only `-Wno-unused-template` for that translation unit. The relevant rocjitsu release and sanitizer CI jobs were passing at inspection; the PR's overall checks were not all green. No new physical-GPU results are claimed.

## Summary

The execution fixes address several independent ISA details: lane selection at permutation boundaries, routing and masking of DPP results, selected source/destination halves, integer sign bits, and conversion rounding. Keeping permutation execution and memory-wait footprints on the same source-lane helper helps those consumers agree. The new tests use distinct lane values and preserved destination sentinels to distinguish the intended behavior.

The translator also normalizes the three-bit shift count and improves scratch-register selection and carry waits. Its partial-addend-overlap case still loses an input half, as detailed below.

## Actionable items

### Preserve the addend's high half through the carry addition

Location: [`cdna4_to_rdna_common.cpp:342`](https://github.com/ROCm/rocm-systems/blob/95bbe164a44429306eab63b7fb12d64e42c4f62b/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/dbt/semantic/cdna4_to_rdna_common.cpp#L342).

For `v_lshl_add_u64 v[3:4], v[0:1], s2, v[2:3]`, the shift uses scratch, but the low add still writes `v3`. The following high add then reads that new low result as the high half of the original addend. With `v[0:1] = 0x12345678ffffffff`, `v[2:3] = 0x3141592600000001`, and `s2 = 12` (decoded shift 4), both target simulators produce `0x23456780fffffff1` instead of `0x5486c0b5fffffff1`.

This is a pre-existing hole in the lowering's overlap handling, within the path and scope modified by this PR. The tests added by the PR cover exact overlap but miss this one-register displacement.

Commit **[1c121ea6bda](https://github.com/newling/rocm-systems/commit/1c121ea6bdaf64071eddcf09e33e338edd678f1e)** finishes both halves of the addition in the existing scratch pair before copying them to the destination. Keeping both halves in scratch also handles a site-dead scratch pair whose low register is the destination's high register. Regression coverage extends `BinaryTranslatorE2E.LshlAddU64ForRdnaNormalizesInlineAndRegisterCounts` with inline and register counts, partial input overlap, and forced scratch reuse. Run it with:

```sh
"$BUILD_DIR/tests/rocjitsu_tests" --gtest_filter=BinaryTranslatorE2E.LshlAddU64ForRdnaNormalizesInlineAndRegisterCounts
```

## Suggestions

### Refresh nearby comments and generated output

At [`simd_glue.h:4412`](https://github.com/ROCm/rocm-systems/blob/95bbe164a44429306eab63b7fb12d64e42c4f62b/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/simd_glue.h#L4412), the comment still says packed integer MAD ignores `neg/neg_hi`. The introduction to `tests/simd_correctness/vop3p_pk_binary_int_simd_correctness_test.cpp` also says non-default half selectors force scalar execution. Both descriptions conflict with the paths exercised here.

Full regeneration removes the unused `execute_image_bvh_intersect_ray_mimg` stub from `generated/shared/execute_shared.h:212`; no generated consumer calls it. Commit **[31cd621e8a6](https://github.com/newling/rocm-systems/commit/31cd621e8a6ea29a299907197ccd22aae664642e)** retains that generated cleanup and updates the two comments. The overlap-fix commit also adds the lowering's directly used standard-library headers; that include cleanup is optional polish.

## Scope decisions

### Treat gfx1201 conversion results as a provisional CDNA5 policy

The source and tests explicitly acknowledge conflicting CDNA5 manual passages for infinity under `FP16_OVFL`. Using gfx1201 as the proxy is visible and testable, but these checks establish the implemented policy rather than physical gfx1250 behavior. A gfx1250 capture is needed to resolve that hardware question; no policy change is proposed here.

Copy-ready scope text:

> Common, non-scaled CDNA5 F32-to-OCP FP8/BF8 narrowing follows measured gfx1201 results, including true-infinity handling under FP16_OVFL. CDNA5 manual passages disagree on this boundary, so the behavior remains provisional until measured on gfx1250. E5M3, scaled conversions, and widening retain their separate policies.

The suggestion branch retains the exact reviewed head plus the two commits linked above. The bounded overlap fix and cleanup are implemented and tested locally. Physical-GPU qualification and rerunning the full corpus remain unverified. The review and suggestion branch are published separately from the PR under review.
