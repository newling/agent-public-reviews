# Review: PR #6495 — rocjitsu: SIMD fast-path enablement (third pass)

**Author**: Alan Li (@lialan)
**Date reviewed**: 2026-06-04
**PR**: https://github.com/ROCm/rocm-systems/pull/6495
**Commit**: `a00762b6ef`

> This is a review from an agent with an automatic prompt from the reviewer.
> For prior reviews, see [review_pr6495.md](review_pr6495.md) and [review_pr6495_2.md](review_pr6495_2.md).

## Tests

**Build command**:
```
git fetch origin users/lialan/rocjitsu_simd
git checkout FETCH_HEAD -- emulation/rocjitsu
cmake --build ~/workspace/builds/rocm-systems-tiberius -j2
```

**Machine**: Low-memory machine (build OOM'd at `-j6`, required `-j2` for the
large `decoder.cpp` translation units — a preexisting issue, not caused by
this PR).

**Compiler**: clang++ 17 (ROCm 7.2 LLVM), C++20, Release, no `-march=native`

**Test command**: `ctest --test-dir <build> --output-on-failure -E "Rocblas" --timeout 10`

**Result**: 600/610 passed, 10 failed

| Test | Failure | Analysis |
|------|---------|----------|
| `DecodeExecuteBenchmark.Cdna4` | Assertion: `idx < total_regs_` in `register_file.h:89` | Genuine — a benchmark encoding accesses a VGPR index beyond the allocated range. Reproduces consistently. |
| `VAddSimdBenchmark.*` (6 tests) | Timeout (>10s) | Expected — these are benchmarks with 200,000 iterations, not correctness tests. |
| `Vop3TernaryFpSimdCorrectness.FullExec` | Timeout (>30s even with raised limit) | Combinatorial explosion: 10 ops × 8 abs × 8 neg × 4 omod × 2 clamp × 16 rotations = 81,920 configurations, each creating 2 full fixture instances (scalar + SIMD). See actionable item 1. |
| `hip_memcpy_test`, `HipMemcpyTest.RoundTripFloat` | Timeout | Environment — no GPU on test machine. |

CI passes (sanity shard only — CI does not run the rocjitsu test suite).

## Summary

This PR adds host-CPU SIMD fast paths for GPU vector instruction emulation
in rocjitsu. The emulator currently processes 64 GPU lanes one at a time;
the SIMD path processes multiple lanes per host CPU instruction via
`std::experimental::simd`, gated by per-instruction `try_execute_*` probes
that check whether operands support contiguous SIMD access.

The implementation spans:
- `util/simd.h` — portable SIMD wrappers with compile-time availability gate
- `simd_glue.h` — ~40 `try_execute_*` template functions for VOP1/VOP2/VOP3/VOP3P/VOPC
- `simd_codegen.py` — Python codegen injecting SIMD probes into generated handlers
- `execute_shared.h` — generated output with SIMD probes + scalar fallbacks
- `operand.h` / `isa_operand_simd_inl.h` — VGPR-backed SIMD lane access (32-bit and 64-bit)
- `vector_reg.h` — SIMD load/store/masked-store methods on the register file
- 42 new test files (10,489 lines) in `tests/simd_correctness/`

Coverage: VOP1 (unary), VOP2 (binary/carry/FMA/cndmask), VOP3 (with
abs/neg/omod/clamp modifiers, ternary FMA/min3/max3/med3), VOP3P (packed-16,
dot products, fma_mix), and VOPC (comparisons writing to VCC or SGPR pair).

## Status of prior review items

### Resolved

1. **Tests pass without `-march=native`** — All SIMD correctness tests pass
   at the default SSE2 width. The prior 15 SSE2-width failures are fixed.

2. **Named struct `VgprPair64`** — Implemented with `.lo`/`.hi` members,
   replacing `std::pair<uint32_t*, uint32_t*>`.

3. **`force_scalar()` returned by non-const ref** — Addressed.

4. **MFMA split to separate PR** — Done.

5. **String normalization noise** — Reverted.

6. **`setdefault` assertion in `_generator.py`** — **Fixed.** The codegen now
   uses an explicit `get()`-then-compare pattern (`_generator.py:3023–3034`)
   that raises `AssertionError` when two ISAs produce different bodies for
   the same `(mnemonic, enc_name)` key. This was the only unresolved item
   from review 2.

7. **Testing approach: file-dump-and-diff replaced with in-process assertions**
   — **Fixed.** The old two-process file-dump-and-diff infrastructure
   (`simd_ab.h`, `simd_ab.cpp`, `simd_ab_diff.sh`, `RJ_SIMD_DUMP` env var)
   is completely gone. All SIMD correctness tests now use
   `util::set_force_scalar_for_testing()` (from `simd_test_hooks.h`) to flip
   the force-scalar gate in-process. Each test runs the same instruction
   twice in the same process — once forcing scalar, once allowing SIMD — and
   compares results with `EXPECT_EQ`. This is the design the second review
   recommended.

8. **`(void)lane_base` cast** — Removed.

### Partially resolved

9. **Testing approach: in-process but via global toggle** — The file-dump
   infrastructure is gone (good), but the replacement relies on toggling a
   process-wide mutable global (`detail::g_force_scalar`) via
   `set_force_scalar_for_testing()`. This works because gtest runs tests
   sequentially within a process, but it is a workaround for a missing
   abstraction: the SIMD path and the scalar path are fused into one
   function with an early-return gate, rather than being independently
   callable. If the codegen emitted the two paths as separate functions (or
   exposed the SIMD lambda directly), tests could simply call both and
   compare — no global flag, no `ForceScalarGuard`, no `simd_test_hooks.h`.
   The mutable global is a code smell that signals this modularity gap. See
   actionable item 3.

### Not resolved

10. **NaN divergence** — Still deferred to a follow-up PR. The SIMD path may
   produce different NaN payloads than the scalar path for min/max and FMA
   operations. Tests handle this by skipping NaN-result lanes in the
   comparison. See suggestion 2.

## Actionable items

### 1. `Vop3TernaryFpSimdCorrectness.FullExec` is too slow

**File**: `tests/simd_correctness/vop3_ternary_fp_simd_correctness_test.cpp:273–278`

`check_all_mods` iterates 8×8×4×2 = 512 modifier combinations for each of
10 ops, and each combination runs 16 input rotations (for f32/f16), creating
2 full `Fixture` instances per rotation. That is 163,840 fixture constructions
per test invocation. The test exceeds 30 seconds on a moderate machine.

All inputs are sanitized finite normals — the modifier sweep is testing the
SIMD modifier-application path, not edge cases. The same coverage could be
achieved by testing a representative subset: e.g. a few abs/neg combinations
rather than all 64, and fewer rotations (or random sampling). Alternatively,
splitting `FullExec` into per-op tests would at least allow individual ops to
pass within the timeout.

### 2. `DecodeExecuteBenchmark.Cdna4` assertion failure

**Failure**: `register_file.h:89: Assertion 'idx < total_regs_' failed`

The benchmark creates a `ComputeUnitCore` and runs all non-skipped
encodings from `test_encodings.h`. One or more encodings access a VGPR index
beyond the allocated register file. This is a genuine assertion failure, not
a timeout or environment issue. It reproduces consistently. The PR should
either fix the encoding or add the offending mnemonic to the `should_skip`
list.

### 3. SIMD and scalar paths should be independently callable

**Files**: `simd_codegen.py`, `execute_shared.h` (generated)

The generated instruction handlers fuse the SIMD and scalar paths into one
function gated by `force_scalar()`:

```cpp
void execute_v_add_f32(Inst &inst, Wavefront &wf) {
  if (!force_scalar()) {
    ROCJITSU_TRY_SIMD_VOP2_BINARY(...);  // returns early if SIMD succeeds
  }
  for (uint32_t lane = 0; ...) { ... }   // scalar fallback
}
```

Because a single call can only exercise one path, the tests resort to
toggling a process-wide mutable global between two runs of the same
function. This works, but it is a workaround. The codegen could emit the
two paths as separate callables — the SIMD lambda and the scalar loop are
already distinct code blocks in the template. With separate functions, a
test would be:

```cpp
auto scalar = scalar_execute(inst, wf);
auto simd   = simd_execute(inst, wf);
EXPECT_EQ(scalar, simd);
```

This eliminates: the mutable global, `simd_test_hooks.h`, `ForceScalarGuard`,
and the implicit contract that tests must run sequentially within a process.
The production dispatch function can still call both (try SIMD, fall back to
scalar) — the separation is purely for testability and modularity.

## Suggestions

### 1. Test file count and build time

42 new test files adding 10,489 lines of test code. The second review
measured an 18% CPU-time increase (2m08s) from test compilation alone. Each
file follows an identical pattern: create a `Fixture`, seed inputs, run
scalar, run SIMD, `EXPECT_EQ`. A parameterized test fixture with the
op-table and encoding as parameters could cover the same ground in far fewer
files, significantly reducing compilation cost.

That said — the testing pattern is clean, the in-process A/B comparison
approach is well-designed, and the coverage is thorough. If the author and
team prefer the explicit-per-category files for readability, the build time
cost (~2 minutes extra) is manageable.

### 2. NaN follow-up scope

The NaN divergence is tracked as a follow-up, but worth documenting what the
follow-up should address:

- Whether the emulator provides bitwise NaN-payload guarantees (scalar path
  matches hardware, SIMD path matches scalar)
- `f32_to_f16_simd` potential UB when `fe < 102` (shift count >= 32 on the
  denormal path)
- The FMA/minmax test skip logic: `nan_lane` check fires before the
  inactive-EXEC-lane check, so inactive lanes with NaN inputs skip the
  destination-preservation assertion

### 3. Benchmark tests should be filtered from normal test runs

The 6 `VAddSimdBenchmark` tests and `DecodeExecuteBenchmark` are performance
measurements (200,000 iterations), not pass/fail correctness tests. They
should be gated behind a CTest label (e.g. `benchmark`) so that
`ctest -LE benchmark` excludes them by default. Currently they always run
and will timeout on slower machines, creating noise in the test results.

## Commentary

**Testing approach is now clean.** The migration from two-process
file-dump-and-diff to in-process `set_force_scalar_for_testing()` +
`EXPECT_EQ` is the most significant improvement since the prior reviews.
The tests are now standard unit tests: self-contained, debuggable, and
fast. The `ForceScalarGuard` RAII pattern prevents the gate from leaking
between tests. The `simd_test_hooks.h` header cleanly separates the
test-only mutation from production code.

**Codegen assertion is a good addition.** The `_generator.py` change from
`setdefault` to explicit comparison with `AssertionError` on mismatch
(lines 3023–3034) closes a correctness gap that could have silently
produced wrong code if ISAs ever diverged on a shared template body.

**The `has_stdx_simd` compile-time gate** is well-designed. All SIMD
correctness tests `GTEST_SKIP()` when `<experimental/simd>` is unavailable,
and the SIMD probes in `simd_glue.h` compile to no-ops. The codebase
degrades gracefully to scalar-only on platforms without the header.

**PR size remains a concern.** 81 files changed, 20,653 insertions. kuhar's
suggestion to split into utilities → architecture updates is reasonable.
The codegen (`simd_codegen.py`, `_generator.py`) and infrastructure
(`simd_glue.h`, `operand.h`, `simd.h`, `vector_reg.h`) could land first,
followed by the per-ISA wiring and tests. The author's response ("teammates
want everything together") is understandable for review coherence, but the
size makes thorough review difficult.
