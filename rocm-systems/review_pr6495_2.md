# Review: PR #6495 — rocjitsu: SIMD fast-path enablement (second pass)

**Author**: lialan
**Date reviewed**: 2026-06-02
**PR**: https://github.com/ROCm/rocm-systems/pull/6495
**Commit**: `6f8223a801`

> This is a review from an agent with an automatic prompt from the reviewer.
> For the first review, see [review_pr6495.md](review_pr6495.md).

## Build and Tests

**Build command**:
```
cmake -S emulation/rocjitsu -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build --target rocjitsu_tests -j8
```

**Machine**: AMD Ryzen Threadripper PRO 7975WX, g++-13, default flags (no `-march=native`)

**In-process tests**: 590/590 passed (0 failures)

**A/B scalar-vs-SIMD equivalence** (`simd_ab_diff.sh`): PASS across 185,888 recorded cases.
This runs the test binary twice (once with `RJ_FORCE_SCALAR=1`, once without),
dumps per-lane results to files, and diffs them. Bit-identical.

The 15 SSE2-width failures from the first review (2026-06-01) are all fixed.

### Build time comparison (clean build, `-j8`)

| | Baseline (`develop`) | SIMD branch | Delta |
|---|---|---|---|
| **Wall** | 1m38s | 1m51s | +13s (+13%) |
| **CPU** | 11m37s | 13m45s | +2m08s (+18%) |
| **Test count** | 390 | 590 | +200 |
| **Test wall time** | 6.2s | 7.5s | +1.3s |

The build time increase is almost entirely from ~40 new test source files.
Library/runtime code compiles in approximately the same time. Test runtime
overhead is negligible (1.3s for 200 additional tests).

## Status of first review items

### Resolved

1. **Tests must pass without `-march=native`** — Fixed. All 590 tests pass
   at the default SSE2 width (4 lanes). The g++-13 / AVX-512
   `fixed_size_simd<int64_t>` static assertion failure is also addressed
   with workarounds noted in code comments.

2. **Named struct for `std::pair<uint32_t*, uint32_t*>`** — Fixed.
   `VgprPair64` (with `.lo`/`.hi`) and `ConstVgprPair64` replace all raw
   `std::pair` usage for 64-bit VGPR pointer returns.

3. **`force_scalar()` returned by non-const ref** — Fixed per inline
   discussion.

4. **MFMA split to separate PR** — Done.

5. **String normalization noise (`'` to `"`)** — Reverted.

### Not resolved

6. **`setdefault` assertion in `_generator.py`** — Still missing. When two
   ISAs produce different bodies for the same `(mnemonic, enc_name)` key,
   `setdefault` silently keeps whichever was processed first. An
   `assert existing == new` on duplicate writes would catch silent
   regressions at codegen time with zero runtime cost. lialan's response
   did not address this item.

## New findings

### 1. Testing infrastructure: the two paths should be independently callable

The generated code in `execute_shared.h` already contains both the SIMD
path and the scalar path in every instruction handler:

```cpp
// Generated pattern in execute_shared.h:
template <typename Inst>
inline void execute_v_add_f32(Inst &inst, Wavefront &wf) {
  ROCJITSU_TRY_SIMD_VOP2_BINARY(uint32_t, [](auto a, auto b) { ... });
  // ↑ if SIMD succeeds, returns early

  // scalar fallback:
  for (uint32_t lane = 0; lane < wf.wf_size(); ++lane) { ... }
}
```

The SIMD and scalar paths are fused into one function with an early-return
gate controlled by `force_scalar()`, which is a process-wide immutable flag
read from `RJ_FORCE_SCALAR` at static init. Because a single process can
only exercise one path, the test suite resorts to:

1. Running the test binary twice (once per mode) via `simd_ab_diff.sh`
2. Each run dumping per-lane results to a text file (`RJ_SIMD_DUMP=...`)
3. Externally diffing the two files

This is a significant amount of infrastructure (`simd_ab.h`, `simd_ab.cpp`,
`simd_ab_diff.sh`, `RJ_SIMD_DUMP` env var, `RJ_FORCE_SCALAR` env var) to
work around a design choice. The two code paths are right there in the same
translation unit — they should be independently callable so that a test can
simply do:

```cpp
auto simd_result = simd_v_add_f32(inst, wf);
auto scalar_result = scalar_v_add_f32(inst, wf);
EXPECT_EQ(simd_result, scalar_result);
```

The codegen could emit the SIMD lambda and the scalar loop as separate
functions (or expose the SIMD lambda directly), eliminating the need for
the process-wide flag, the env vars, the file dumps, the diff script, and
the two-process invocation. The tests would become normal unit tests with
in-process assertions — simpler, faster, and easier to debug when they fail.

This also affects the NaN handling (item 2 below): the current tests skip
NaN-input lanes by overwriting them with a sentinel *in the dump output*.
With in-process comparison, the skip logic would be a simple `if` in the
`EXPECT_EQ` loop — no sentinel, no masking, no worry about the skip
ordering relative to inactive-lane checks.

### 2. NaN divergence deferred

The SIMD path produces different NaN payloads than the scalar path for
certain operations (min/max, FMA). The tests handle this by marking
NaN-input lanes with a sentinel before the A/B comparison, effectively
skipping them. This is documented as an "accepted divergence" in the test
file headers.

lialan commented "let's do a follow up for the NaN relevant stuffs."
The NaN follow-up should track:

- Whether SIMD NaN payloads need to match scalar (and thus real HW) exactly
- `f32_to_f16_simd` potential UB: shift counts >= 32 on the denormal path
  when `fe < 102` (Copilot flagged this)
- `kEdges` f16 table doesn't exercise f16 NaN corners — the low 16 bits of
  the f32 edge patterns are all `0x0000` (+0 in f16)
- Test loop order in FMA/minmax: the `nan_lane` skip fires before the
  inactive-EXEC-lane check, so inactive lanes with NaN inputs skip the
  destination-preservation assertion

### 3. Unnecessary `(void)lane_base` cast

**File**: `operand.h:228`

In `simd_lane_ptr64`, `lane_base` is already used on line 227
(`delegate_->simd_lane_ptr64(wf, lane_base)`). The `(void)lane_base` on
line 228 is unreachable when the delegate path is taken, and unnecessary
when it falls through since the parameter was already referenced. The cast
can be removed.

### 4. Wave32 (RDNA) support

The SIMD path correctly handles Wave32 wavefronts. The loop in
`simd_glue.h` uses `wf.wf_size()` (not a hardcoded 64), and EXEC mask
extraction scales to the actual wavefront size. An RDNA3 Wave32 test
exists (`vop3_b16_rdna_simd_correctness_test.cpp` with `WF_SIZE = 32`).

The PR description says "Other ISAs share the same generated probes
opportunistically" — this means the SIMD probes are emitted into the
shared `execute_shared.h`, so RDNA instructions that use the same generated
handler get the SIMD path automatically. However, only CDNA4 has been
systematically validated; RDNA coverage rides along where encodings match
but is not the focus of this PR.

## Commentary

The core SIMD infrastructure is correct: exec mask handling preserves
inactive lanes consistently, source modifier handling (abs/neg/omod/clamp)
is applied correctly, and the codegen approach (Python-generated probes
with scalar fallback) is clean.

The A/B equivalence check (185,888 cases, bit-identical) provides strong
confidence in correctness for non-NaN inputs. However, the testing
infrastructure built around it (two-process file-dump-and-diff) is more
complex than necessary and should be simplified as described in item 1.
