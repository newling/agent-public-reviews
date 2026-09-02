This is a review from an agent with an automatic prompt from the reviewer

## Tests

The `rocjitsu_tests` target built successfully; all 9 `Gfx1251F64WmmaExecutionTest.*` cases and 3 related WMMA register-observation tests passed. Changed-file pre-commit hooks and `git diff --check` passed. The focused Python tests could not be collected because `cgen` is absent from the review environment; no dependency was installed.

The visible release and TSan CI jobs pass. The ASan stack-buffer-overflow in `Gfx1251PackedF64ExecutionTest.RejectsUndefinedLayoutsAndOutOfRangeRegisterTuples` and the GCC UBSan `maybe-uninitialized` build diagnostic in `fp_mode::binary_f64` both reproduce in CI on the exact stack base, before this PR. The TheRock failures occur while fetching sources on the self-hosted runner. These red jobs therefore do not identify a regression in this diff, although the stack needs the base failures resolved before it can be green.

## Summary

This PR promotes the gfx1251-only `v_wmma_f64_16x16x4_f64` model from decode-only status to an executable callback while leaving normal gfx1251 simulator selection disabled. The generated decoder validates the public LLVM operand widths, legal modifiers, tuple bounds and alignment, and wave32-only form. The new fixed-shape helper maps the F64 A/B and C/D tuples, snapshots all matrix inputs and accumulators before any write, evaluates four MODE-aware fused reductions per output, and applies EXEC only when publishing the 16-register destination.

The implementation is unusually well covered for a source-derived instruction model: the runtime tests independently spell out the lane/register mapping and cover tuple boundaries, destructive overlap, partial EXEC, public modifiers and inline C, all rounding and denormal modes, exceptional values, invalid encodings, and wave64 rejection. I found no PR-specific correctness issue that should block this incremental, still-disabled implementation.

## Actionable items

None.

## Suggestions

### 1. Keep the fixed F64 mapping helper fixed-shape in its interface

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:455`

`wmma_output_loc_64()` is justified and tested only for the gfx1251 16x16 F64 layout, but its `M` and `N` parameters make it look like a general WMMA mapping function. Either remove those parameters and encode the 16x16 constants, add an assertion for that shape, or give it a gfx1251/F64-specific name. That would prevent a future caller from assuming that doubling `wmma_output_loc_32()` is valid for another F64 shape or architecture.

### 2. Add direct plugin-observation coverage when gfx1251 execution is enabled

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:3800`
- `emulation/rocjitsu/tests/execution_plugin_test.cpp:3309`

The helper correctly uses the existing matrix read regions and an EXEC-masked write region, and the shared region machinery has focused tests. Before `execution_implemented` is enabled for gfx1251, add one decoded F64 WMMA test that checks the four-register A/B reads, optional 16-register accumulator read, and 16-register destination writes with the active-lane mask. This would pin the complete generated-callback-to-plugin contract for the new path.

## Commentary

### Relationship to the matrix-performance work

This PR is based on revisions that already contain #10702, #10706, and #10710. It is complementary to those changes rather than a replacement for them:

- Like #10706, the new helper snapshots A and B once instead of rediscovering and rereading them for every output. It also snapshots C and retains all results until every source read is complete, preserving destructive-overlap behavior.
- Like the optimized paths used by #10702 and #10710, it acquires contiguous `RegisterAccess` regions instead of issuing per-element virtual VGPR accesses. This preserves plugin visibility while reducing register-access overhead.
- Unlike #10702 and #10710, it does not call the native-width matrix core. Every one of the 256 outputs performs four scalar `fp_mode::fma_f64()` calls. That choice preserves directed rounding, input/output denormal handling, and NaN behavior, but each call currently saves, changes, and restores the host floating-point environment. Thus the PR inherits the staging half of the earlier performance strategy, not its host-SIMD arithmetic speedup.
- #10898 is not in this PR's ancestry. A merge-tree check shows it auto-merges with #11124 despite both touching `mma_exec.h`; it changes f16/bf16 f32-accumulating MFMA width selection and does not overlap the new F64 helper semantically.

If this instruction becomes important in real workloads, a natural follow-up is a MODE-aware `native<double>` row path analogous to #10710. `simd_glue.h` already has `fma_f64_mode_simd()`, including scalar NaN fallback, so the main design question is how to share that primitive without coupling the matrix header to the operand SIMD layer. Such optimization should remain separate from this PR's source-derived correctness work and should be benchmarked on an actual F64 WMMA workload.

The remaining correctness uncertainty is the one already recorded in the source: the lane mapping and numerical behavior have not been compared with physical gfx1251 hardware. Keeping normal gfx1251 simulation disabled makes that an explicit qualification task rather than an unguarded correctness claim in this PR.
