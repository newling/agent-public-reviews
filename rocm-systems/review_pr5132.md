# Review: PR #5132 — rocjitsu: Add rocBLAS GEMM test suite and fix ISA bugs

**Date reviewed**: 2026-04-20
**PR**: https://github.com/ROCm/rocm-systems/pull/5132

## Summary

Large PR (+4715/-3071, 86 files) that adds an end-to-end rocBLAS SGEMM test
suite and fixes 5 critical ISA execution bugs discovered while bringing up
real Tensile GEMM kernels. Also includes a VMEM address calculation refactor
and CDNA3 config additions.

Most of the file count comes from auto-generated ISA instruction files
(ds.cpp, mubuf.cpp, flat.cpp, vop3p.cpp across 9 ISA backends). The
hand-written changes are concentrated in ~15 files.

## Overall assessment

High-quality work. The ISA fixes are well-motivated (each discovered by
running real GEMM kernels), the test suite is thorough, and the address
calculation refactor is a welcome consolidation. The PR description is
excellent — clearly explains each fix with context.

## ISA correctness fixes (all look correct)

1. **MFMA output layout** — row/col swap fix. Verified against AMD Matrix
   Instruction Calculator convention.
2. **MUBUF OOB check** — soffset exclusion in structured mode. Correct per ISA spec.
3. **ds_read_b64 vgpr_count** — elem_size=8 now correctly writes 2 VGPRs.
   Critical fix for Tensile LDS staging.
4. **DS write2/read2** — new dual-access implementation with ds2_active path.
   Clean integration into VectorMemState and LocalMemPipeline.
5. **MFMA blgp/cbsz/abid** — lane permutation tables match ISA spec Table 29.

## Issues found

### 1. `addr_calc_buffer.h` — idxen+offen handling (latent bug)

When both `offen` and `idxen` are set:
```cpp
if (inst.offen)
    voffset = cu.read_vgpr(wf.vgpr_alloc().base + inst.vaddr, lane);
if (inst.idxen)
    voffset = cu.read_vgpr(wf.vgpr_alloc().base + inst.vaddr, lane);
```
Both branches read the same VGPR (`inst.vaddr`) and `idxen` overwrites
`offen`'s value. Per the ISA spec, when both are set, `vaddr` provides the
index and `vaddr+1` provides the offset. The `mtbuf_calculate_addresses`
function has `assert(!inst.idxen)` acknowledging the limitation, but the
MUBUF path doesn't. This won't affect current Tensile kernels (which don't
use structured indexing with stride), but is a bug waiting to happen.

From [LLVM's test suite](https://github.com/llvm/llvm-project/blob/main/llvm/test/MC/AMDGPU/mubuf.s#L137):
```
buffer_load_dword v1, v[2:3], s[4:7], s1 idxen offen
; v2 = buffer index (selects record, multiplied by stride in descriptor)
; v3 = byte offset within the record
; vaddr=2 encodes the index, vaddr+1=3 encodes the offset
```

The current code reads `inst.vaddr` for both, so the index overwrites the
offset. It should read `inst.vaddr` for the index and `inst.vaddr + 1` for
the offset (or vice versa, per the ISA spec encoding).

**Suggestion**: Add an assert or comment in the MUBUF path too, or implement
the correct dual-register behavior.

### 2. `mfma_exec.h` — f64 output_loc row/col ordering

`exec_f32` calls `output_loc_32(M, N, row, col, b)` but `exec_f64` calls
`output_loc_64(M, N, col, row, b)`. The row/col swap in f64 should be
verified against the AMD spec — it may be intentional due to f64 layout
differences, but the inconsistency is easy to get wrong.

### 3. `memory_pipeline.cpp` — non-thread-safe static counter

```cpp
static uint64_t oob_count = 0;  // NOT thread_local
```

Other nearby counters correctly use `static thread_local`. This one is a
data race in multi-threaded simulation. The impact is benign (just trace
throttling), but it's inconsistent and would trigger TSAN.

### 4. Static thread_local counters generally

Multiple files use `static thread_local uint64_t` for trace throttling
(retire_count, oob_count, etc.). These accumulate across the thread's
lifetime with no reset between kernel dispatches or test cases. A counter
on the CU or pipeline object would be scoped to the right lifetime and
resettable. Acceptable for debug logging, but worth noting as a pattern
that doesn't scale.

### 5. Hard-coded debug PC addresses in compute_unit.cpp

```cpp
if (util::trace::enabled() && active->pc == 0x4d00249258ULL) {
```

Several hard-coded PC addresses appear in trace logging. These are clearly
debug artifacts from GEMM bring-up and will be meaningless for any other
kernel. Should be removed before merging, or gated behind a debug define.

## Question: rocblas-bench as an alternative to custom test

rocBLAS ships a command-line client (`rocblas-bench`) at
`projects/rocblas/clients/benchmarks/` that takes GEMM parameters directly:
```
rocblas-bench -f gemm -r s -m 128 -n 128 -k 64 --alpha 1.0 --beta 0.0
```

Could this be used under the KMD interposer instead of writing a custom
218-line test?
```
LD_PRELOAD=librocjitsu_kmd.so rocblas-bench -f gemm -r s -m 64 -n 64 -k 64 --verify
```

Advantages: no custom test to maintain, validates through the full rocBLAS
stack (same code path as production), easy to sweep problem sizes.

Trade-offs: heavier build dependency (needs rocBLAS built with clients),
the `_exit()` workaround for comgr hang may not be possible in an external
binary. But worth considering if the comgr issue gets fixed.

## Minor observations

- **`hip_gemm_test.cpp` uses `_exit(rc)`** to avoid `hsa_shut_down()` hang.
  Pragmatic workaround, well-documented. Note that this prevents sanitizer
  leak detection.

- **Fuzz test coverage**: 5 iterations with dimensions 1-64. Good starting
  point, could expand over time.

- **`vector_complete` complexity**: This function now handles regular loads,
  atomics, LDS-dst, OOB zeroing, and dual-access DS. Consider splitting
  into sub-functions per path.

- **Config corrections**: L2 size, LDS size, and WF slot corrections for
  CDNA4 look well-researched (references architecture whitepapers). CDNA3
  config addition is welcome.

## Verdict

**Approve with comments.** The ISA fixes are important and correct. The
addr_calc idxen+offen issue (#1) is latent and should at least get an
assert. The non-thread-safe static (#3) should be trivially fixable.
The hard-coded PCs (#5) should ideally be cleaned up before merge.
