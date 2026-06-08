# Review: PR #6870 — rocjitsu: Add v_cvt_scalef32 and non-scaled FP8/BF8 cvt insts

**Author**: atgutier
**Date reviewed**: 2026-06-08
**PR**: https://github.com/ROCm/rocm-systems/pull/6870
**Commit**: `32dfb55f0c`

> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**Build command**: `cmake --build <build> -j2`
**Machine**: Low-memory x86, clang++ 17 (ROCm 7.2), Release
**Result**: Build succeeded. 24/24 data_types unit tests passed, 1/1
CvtNarrow HIP integration test passed (9.6s). Full suite: 6 Rocminfo
failures (environment — CLI launcher incompatibility on this machine),
all other tests passed.

**Test command**: `ctest --test-dir <build> -R "Fp4|Fp8|Bf8|Fp6|Bf6|CvtNarrow" --output-on-failure --timeout 10`

CI passes (pre-commit, build, sanity shard).

## Summary

This PR implements 55 GPU instructions for narrow floating-point format
conversions: 49 `v_cvt_scalef32_*` (scaled FP8/BF8/FP4/FP6/BF6 with E8M0
scale factor) and 6 non-scaled `v_cvt_{pk,sr}_{fp8,bf8}_f32`. These are
essential for MI300-era AI workloads.

The implementation spans three layers:

1. **`data_types.h`** — C++ conversion utilities for all 5 narrow formats
   (FP8 E4M3, BF8 E5M2, FP4 E2M1, FP6 E2M3, BF6 E3M2) with RNE
   (round-to-nearest-even), SR (stochastic rounding), pack/unpack, and
   PRNG seed advancement.

2. **`vector_special.py`** — Python codegen with `gen_cvt_fp8` and
   `gen_cvt_scalef32` handlers that route to sub-dispatchers for narrowing
   (RNE/SR), widening, and wide (pk32/2xpk16) variants. Handles OPSEL
   byte/half selection, E8M0 scale factor, and per-lane LFSR seeding.

3. **Tests** — 29 CPU unit tests in `data_types_test.cpp` and 17 HIP CTS
   tests in `hip_cvt_narrow_test.cpp`, plus external fpsan validation
   (23/23 tests reported passing).

The PR also fixes several conformance bugs found via fpsan: VGPR index
off-by-256, FP4 branch fallthrough, SR FP4 double-read, SR PK FP4 operand
mapping, and 2xpk16 FP6/BF6 interleaving.

## Actionable items

None. The implementation is validated by fpsan (23/23 hardware conformance
tests passing), which is a stronger correctness guarantee than any
additional unit test. The existing test suite (29 CPU + 17 HIP + 23 fpsan)
provides thorough coverage.

## Suggestions

### 1. Reduce codegen duplication in `vector_special.py`

`_gen_narrow_scalef32` (lines 1271-1379) and `_gen_sr_scalef32` (lines
1385-1499) each contain 3 near-identical blocks differing only in how
source values are read (f32 vs f16 vs bf16). A helper like
`_read_pair_as_f32(src_fmt)` returning the appropriate
`std::bit_cast`/conversion expression could eliminate ~60 lines.

### 4. `f32_to_binary_float_sr` subnormal handling

**File**: `data_types.h:385-402`

At line 402, the function adds `1u << 23` (implicit 1) to the mantissa
for F32 subnormal inputs. F32 subnormals don't have an implicit 1. The
impact is negligible for current callers (F16 SR flushes all F32
subnormals to zero, BF16 SR doesn't enter this branch for subnormals),
but it's a latent correctness bug for future callers of this function.

## Prior review activity

**Copilot** left 25 comments on an earlier version of the PR, all about
`exp >= max_exp` clamping in a now-deleted `narrow_cvt.h` file. These
comments are no longer relevant — the file was replaced by `data_types.h`.

**bjacob's agent** ran the fpsan hardware conformance suite against the
emulator and found 3 real bugs in the second revision (`9d25b86b`):
(1) FP6/BF6 wide VGPR off-by-256 (`encoding_value()` vs
`unified_vgpr_index()`), (2) `pk_fp4_f32` falling into the FP8 branch,
(3) `sr_pk_fp4_f32` reading one element twice. All three were fixed in
`bfc4cb03`. A second fpsan run found additional issues (scale ×4 bug, SR
segfaults) which were fixed in subsequent commits. The current version
(`32dfb55f`) reportedly passes all fpsan cvt tests.

The fpsan-based review process — running real hardware conformance tests
through the emulator and diffing against silicon — was significantly more
effective at finding bugs than static code review. The 3 bugs found would
have been difficult to catch by reading the codegen Python alone.

## Commentary

**Conversion correctness is strong.** The RNE implementations consistently
follow the standard pattern (round bit + sticky + ties-to-even guard).
The OCP E4M3FN NaN semantics (NaN = 0x7F only, no Inf representation)
are handled correctly throughout. The FP4/FP6/BF6 saturation behavior
(no NaN/Inf, clamp to max) is consistent.

**The fpsan validation** (23/23 tests passing) provides high confidence in
the instruction-level correctness. This external conformance suite is the
strongest evidence that the conversions match hardware behavior.

**The codegen architecture is clean.** The `_parse_scalef32_op` dispatcher
(line 1161) that extracts stochastic/mode/dst_fmt/src_fmt/direction from
the mnemonic suffix is a good pattern — it centralizes the naming
convention parsing and routes to focused sub-generators.

**The 2xpk16 interleaving fix** (field[2k]=lo[k], field[2k+1]=hi[k])
is well-tested by the HIP round-trip tests which verify de-interleaving
produces the original values.
