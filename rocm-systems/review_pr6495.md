# Review: PR #6495 — rocjitsu: SIMD fast-path enablement

**Author**: Alan Li (@lialan)
**Date reviewed**: 2026-06-01
**PR**: https://github.com/ROCm/rocm-systems/pull/6495

> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**Command**: `ctest --test-dir ~/workspace/builds/rocm-systems-claudius -j$(nproc) --output-on-failure`
**Build**: g++-13, Release, no `-march=native` (project default)
**Timing**: 94s wall (dominated by `RocblasGemmTest.Large_2048x2048` at 94s; the 187 new SIMD tests complete in 0.36s)
**Result**: 596/611 passed, 15 failed

The 15 failures are all in new SIMD correctness tests:

| Test | Failure pattern |
|------|----------------|
| `Vop2SimdCorrectness` (2 tests) | `v_mul_hi_i32_i24`: all lanes = `0xcafef00d` sentinel |
| `Vop1SimdCorrectness` (2 tests) | `v_floor_f32`: negative-zero and NaN payload divergence |
| `Vop1F64SimdCorrectness` (2 tests) | `v_rndne_f64`: bit-level rounding mismatch |
| `Vop3UnarySimdCorrectness` (2 tests) | Same `v_floor_f32` issues as VOP1 |
| `Vop3IntWideningTernarySimdCorrectness` (2 tests) | `v_mul_hi_i32_vop3`: all lanes = `0xcdcdcdcd` sentinel |
| `Vop3Fp64SimdCorrectness` (1 test) | `v_rndne_f64` rounding mismatch |
| `Vop3Fp16UnarySimdCorrectness` (1 test) | `v_ceil_f16` divergence |
| `VAddSimdBenchmark` (2 tests) | Same `v_ceil_f16` issue |
| `UtilSimd.RndneF64_VectorMatchesScalar_BitExact` (1 test) | `rndne_f64_simd` bit mismatch |

**Root cause**: The PR description states testing was done with `g++-13 -march=native`.
The project's CMakeLists does not include `-march=native`, so the default build
targets SSE2 (`native_simd<uint32_t>::size() = 4` instead of 16). The test
failures are width-dependent — they pass at width 16 on the author's machine
but fail at width 4 in the default build.

Furthermore, attempting to build with `-march=native` on our AVX-512 machine
(g++-13) produces a **compile error** in libstdc++'s `<experimental/simd>`:
```
simd_x86.h:4232: static assertion failed: is_same_v<long long, long>
```
This is triggered by `fixed_size_simd<int64_t, 16>` (used by `v_mul_hi_*`
lambdas). The PR cannot currently be compiled with AVX-512 on g++-13. This
needs investigation — it may be a libstdc++ version issue or may require
a workaround in the code.

CI passes but does not run the rocjitsu test suite (only "Sanity Check" shard).

## Summary

This PR adds host-CPU SIMD fast paths for GPU vector instruction emulation.
The emulator currently executes each GPU instruction by looping over 64 lanes
one at a time. This PR adds an optional SIMD path that processes multiple
lanes per host CPU instruction (4–16 lanes depending on ISA target), gated by
a `try_execute_*` probe that checks whether all operands support contiguous
SIMD access.

The implementation spans four layers:
- `util/simd.h` — portable `std::experimental::simd` wrappers with fallback stubs
- `simd_glue.h` — ~40 `try_execute_*` template functions bridging operand semantics to SIMD primitives
- `simd_codegen.py` — Python codegen that injects SIMD probe lines into generated instruction handlers
- `execute_shared.h` — the generated output containing SIMD probes + scalar fallbacks

Coverage: VOP1 (unary), VOP2 (binary/carry/FMA/cndmask), VOP3 (with
abs/neg/omod/clamp modifiers), VOP3P (packed-16, dot products, fma_mix),
and VOPC (comparisons writing to VCC or SGPR pair).

The PR also includes `_generator.py` changes replacing fragile name-based
width heuristics (`endswith('_f64')`) with per-operand `op.size` from the ISA
spec, and a force-sharing mechanism for arch-portable SIMD probes.

43 new test source files (all compiled into the existing `rocjitsu_tests`
binary) provide scalar-vs-SIMD bit-identity checks.

## Actionable items

### 1. Tests must pass without `-march=native`

The project does not set `-march=native` in CMakeLists, and there is no plan
to add it. The 15 test failures demonstrate that the SIMD paths produce wrong
results at the default SSE2 width (4 lanes). All tests must pass with the
project's default build configuration, or the tests must be gated on
`native_width >= N` if certain ops genuinely require wider vectors.

Additionally, the g++-13 + AVX-512 compile failure
(`is_same_v<long long, long>` in `fixed_size_simd<int64_t>`) needs
investigation. If the PR cannot be built with `-march=native` on common
toolchains, the benchmarks reported in the PR description are not
reproducible by other developers.

### 2. `std::pair<uint32_t*, uint32_t*>` return type for 64-bit VGPR pointers

**File**: `operand.h:220` and `isa_operand_simd_inl.h:103`

`simd_dst_ptr64` and `simd_lane_ptr64` return `std::pair<uint32_t*, uint32_t*>`.
Callers use `.first` and `.second` with no indication which is the low register
and which is the high register. A named struct would make every call site
self-documenting:

```cpp
struct VgprPair64 {
  uint32_t *lo;
  uint32_t *hi;
};
```

### 3. `_shared_execute_bodies.setdefault` silently discards mismatches

**File**: `_generator.py:3014`

When two ISAs produce different bodies for the same `(mnemonic, enc_name)` key,
`setdefault` silently keeps whichever ISA was processed first. The comment says
"the body is arch-independent, so whichever ISA writes first is correct and
identical" — but there is no assertion verifying this. Adding an assert that
checks `existing_body == new_body` on duplicate writes would catch silent
regressions at codegen time with zero runtime cost.

## Reviewer comments assessment

The reviewer (@newling) left several inline comments. Assessment of each:

### Agree

- **MFMA in separate PR**: Correctly identified that the MFMA changes in
  `mfma_exec.h` bypass plugin hooks (`onAmdgpuReadVgprs`) by replacing
  `cu.read_vgpr()` with direct `vgpr_words()` pointer access. Splitting MFMA
  out was the right call — it needs its own plugin-compatibility story.
  Author has addressed this: MFMA is now in a separate PR.

- **`vgpr_data` raw pointer concern**: The reviewer flagged that raw pointer
  access to VGPRs will break plugins. This is correct — the VALU SIMD path
  handles it via `SimdAccess::notify_read`, but raw `vgpr_data`/`vgpr_words`
  has no hook. The reviewer's preference for a better public/private contract
  is well-founded. The author's suggestion to "do `onAmdgpuReadVgpr` where we
  actually access raw pointers" is a tactical fix; the reviewer's instinct
  that it's not sustainable long-term is correct.

- **Named struct for `std::pair<uint32_t*, uint32_t*>`**: Agree — `.first`
  and `.second` give no indication of lo vs hi semantics.

- **`force_scalar()` returned by non-const ref**: Reasonable question. The
  return-by-ref is intentional (allows `force_scalar() = true` in tests), but
  it's unusual — a setter method would be more conventional.

- **Testing on different architectures**: Important observation. The test
  failures on our machine confirm this concern — the SIMD paths behave
  differently at different native widths.

### Partially agree

- **Benchmark iteration counts causing CI timeouts**: The 187 SIMD tests
  complete in 0.36s total — negligible. The benchmarks (`VAddSimdBenchmark`)
  take ~150ms each. Not a CI timeout risk in practice, but gating behind
  a label/filter for large suites is still good practice.

### No opinion

- **"How is this new code generated/created?"**: Legitimate question about
  the codegen pipeline — the answer is `simd_codegen.py` generates probe
  lines that get injected into `execute_shared.h` by `_generator.py`.

## Suggestions

### 1. Missing fallback stubs in `util/simd.h`

`flush_denorm_f32_simd` has a fallback stub for when `std::experimental::simd`
is unavailable, but most other new functions (`f16_to_f32_simd`,
`rcp_f32_simd`, `sqrt_f32_simd`, `popcount_u32_simd`, `frexp_*`, etc.) do
not. Adding stubs would be defensive against future compile failures on
platforms without `<experimental/simd>`.

### 2. `kQNaN` as file-scope `inline` variable

**File**: `util/simd.h`

`kQNaN` constructs a `native_simd<float>` at static initialization time. If
`native_simd`'s constructor isn't `constexpr`, this is a dynamic initializer
with SIOF risk. A function-local static would avoid this.

### 3. Test redundancy

43 new test files with an identical pattern (fill registers, run scalar, run
SIMD, compare). A parameterized test fixture could cover multiple instruction
categories in fewer files, reducing compilation cost.

## Commentary

**Exec mask handling** is consistently correct across all ~40 `try_execute_*`
functions — inactive lanes are never written, VCC/SGPR-pair outputs preserve
inactive bits via merge patterns. This is the most important correctness
property and it holds throughout.

**Source modifier handling** (abs/neg/omod/clamp for VOP3) is applied
correctly across float/int/f16/f64 paths. The fmac variants correctly skip
modifiers on the accumulator.

The **codegen approach** — Python generating C++ SIMD probes that gate
optional fast paths before a scalar fallback — is sound. It keeps SIMD
opt-in per instruction, maintains the scalar path as the correctness
reference, and avoids per-ISA duplication.

The **`v_cmp_class_f16` rewrite** in `cdna4/vop3.cpp` (moving from
float-domain `std::isinf`/`std::isnormal` to bit-level f16 field extraction)
is a correctness improvement independent of SIMD — it avoids misclassification
of f16 denorms after conversion to f32.

The **`op_widths` refactor** in `_generator.py` replacing name heuristics
with per-operand ISA-spec widths is a clean improvement that will reduce
maintenance as new mixed-width instructions are added.
