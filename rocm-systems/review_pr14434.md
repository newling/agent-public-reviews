This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#14434](https://github.com/ROCm/rocm-systems/pull/14434)

**Reviewed head:** [`85d45c3fce0684d14582449aa42c46fb865120f3`](https://github.com/ROCm/rocm-systems/pull/14434/commits/85d45c3fce0684d14582449aa42c46fb865120f3) (base [`daf7ef33e4d`](https://github.com/ROCm/rocm-systems/commit/daf7ef33e4d8cc27ffdce08e13f495aa26371c49)). The repository and PR branch are public.  
**Suggestion branch:** [`review/pr14434-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr14434-suggestions), based on the reviewed head ([compare](https://github.com/newling/rocm-systems/compare/85d45c3fce0684d14582449aa42c46fb865120f3...c24aa9acb28c69406f71484851bb2c6d656705da)). No comment or review has been posted on the PR.

| Commit | Review item |
| --- | --- |
| [`c24aa9acb28`](https://github.com/newling/rocm-systems/commit/c24aa9acb28c69406f71484851bb2c6d656705da) | Keep the raw carrier for F16 pseudo-scalar inline sources; regenerate; assert the measured CDNA5 inline results. |

The LDS allocation-granule item and the suggestions have no commits; the reasons are given with each item.

## Tests

Clang 23.1 Release build: the PR's changed and added native suites (scalar F16, vector16 and BF16 inline constants, packed saturation, fork/join, PC fetch, RDNA4/CDNA4/gfx1250 memory harnesses, routed memory observation, execution-plugin and race-detector tests, CDNA4-to-CDNA3 BF16 translation, FP-mode and VOP3 conversion tests) pass on both the reviewed head and the suggestion branch, as do 2,891 generator tests (45 skipped). Full ISA regeneration at the reviewed head reproduces every checked-in generated file.

`hsa_init_test` does not link locally because the host's ROCm 7.1 runtime lacks `hsa_amd_queue_create`; this is unrelated to the PR.

Hosted `rocjitsu-test-corpus` Release, ASan/UBSan and GCC UBSan jobs are red. Every failure belongs to a class that also fails on develop at [`36e81d84`](https://github.com/ROCm/rocm-systems/commit/36e81d848446fd869f055a42ea60b9d9901843d2), although the affected case names vary between runs. The classes are concurrent CTS configure races (googletest clones), IREE runs that load empty `module.vmfb` cache files, a missing executable after a failed shared configure, and the known GCC-UBSan timeout of gfx1201 `large_2048x2048`. None reports an emulator result mismatch.

Beyond the unit tests, I ran one set of HIP probes on a physical gfx1201 and under rocjitsu's `gfx1201_r9700.json` configuration, using identical binaries for the PR head and its develop base. The probes cover 30 scalar F16 cases, 11 VALU 16-bit inline cases, 20 FLAT-to-LDS boundary cases, 9 OPSEL cases and the LDS allocation granule. They are summarized in the summary and items below; sources are in the appendix.

## Summary

The PR fixes four independent classes of emulator defects. Scalar F16 consumers now format float inline selectors as half values, including the high-half conversion. Decoded 16-bit VALU sources record whether their float inlines use F16, FP32 or BF16 bit patterns. RDNA1/2 16-bit VALU results preserve the destination's upper half. RDNA4 FLAT accesses to the LDS aperture use unsigned 17-bit offsets and clip to complete in-range elements of the workgroup allocation. Finally, `s_setpc`/`s_swappc` and CDNA `s_cbranch_g_fork` share one PC-target decoder that no longer misreads sign-filled GETPC exports as rel32 tags.

The hardware comparison strongly supports the core of the PR. The PR head fixes 21 scalar, 8 VALU and 9 FLAT-LDS probes in which develop disagrees with gfx1201. The remaining mismatches are pre-existing and described below. The fixed cases include:

- `s_cvt_hi_f32_f16` with float inlines, which the manual's wording would predict reads zero;
- the FP32 inline pattern for 16-bit integer sources (`v_add_nc_u16 v, 0.15915494, 0` yields `0xF983`), with OPSEL selecting `0x3F80` from `1.0`;
- complete-DWORD FLAT clipping for unaligned loads and stores, U17 wraparound (`aperture + 0x20008` reads LDS offset 8), and no per-DWORD wraparound at `0x1FFFC`.

LLVM agrees on the 16-bit integer inline table (`isInlinableLiteralI16` delegates to the 32-bit table) and on GFX10 high-half preservation. A sweep over every RDNA1/2 VOP1/VOP2/VOP3 opcode whose decoded destination is marked preserving (85 per target) found no SIMD or scalar executor that loses the upper half; only `v_sat_pk_u8_i16` is excluded, as intended.

The construction-time operand flags are a good design choice: they keep the format decision with the decoder, and lane, chunk and delegated reads now agree. Two consequences need attention: one generator rule reaches the pseudo-scalar transcendentals, which hardware treats differently, and the new FLAT bound inherits an allocation size that does not match hardware.

## Actionable items

### Keep the raw carrier for F16 pseudo-scalar inline sources

Location: [`emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:6757`](https://github.com/ROCm/rocm-systems/blob/85d45c3fce0684d14582449aa42c46fb865120f3/emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py#L6757), which reaches `v_s_{exp,log,rcp,rsq,sqrt}_f16` in the generated RDNA4 `vop3_exec.cpp` and CDNA5 `vop3_exec_alu.cpp`, and [`emulation/rocjitsu/tests/scalar_f16_constant_test.cpp:269`](https://github.com/ROCm/rocm-systems/blob/85d45c3fce0684d14582449aa42c46fb865120f3/emulation/rocjitsu/tests/scalar_f16_constant_test.cpp#L269).

The `scalar_f16_inline_high` mapping applies to every `FMT_NUM_F16` SGPR-class source, including the VOP3 pseudo-scalar transcendentals. These now read float inline selectors through `read_scalar_f16_carrier`, as numeric half values. The new test asserts that CDNA5 "permits numeric float inlines here" (selector 246 yields `exp2(4.0)`) and that RDNA4 excludes the selectors.

gfx1201 contradicts both premises. It accepts these encodings and executes the float selector as the low half of the FP32 constant:

| Instruction | gfx1201 | Numeric half would give |
| --- | --- | --- |
| `v_s_sqrt_f16 s, 4.0` | `0x0000` | `0x4000` |
| `v_s_rcp_f16 s, 2.0` | `0x7C00` | `0x3800` |
| `v_s_exp_f16 s, 0.5` / `1.0` / `-4.0` | `0x3C00` | `0x3DA8` / `0x4000` / `0x2C00` |
| `v_s_exp_f16 s, 0.15915494` | `0x0000` (from `0xF983`) | `0x3C77` |

The same selectors in the VALU forms behave numerically (`v_exp_f16 v, 1.0` = `0x4000`; `v_exp_f16 v, 0.15915494` = `0x3C77`), so the difference is specific to the pseudo-scalar forms. LLVM encodes this as `FeatureNoF16PseudoScalarTransInlineConstants` for gfx12, gfx1250 and gfx1170 ([llvm/llvm-project#104395](https://github.com/llvm/llvm-project/pull/104395)), and codegen never folds inline constants into these instructions.

In rocjitsu's RDNA4 decoder these selectors are rejected (`OPR_SREG_LITERAL`), so the change is currently unreachable there. CDNA5 decodes them, and the PR changes its result from the raw carrier, which matches the only hardware evidence, to the numeric half. Exclude `pseudo_scalar_unary` from the mapping and assert the raw-carrier results. Commit [`c24aa9acb28`](https://github.com/newling/rocm-systems/commit/c24aa9acb28c69406f71484851bb2c6d656705da) does this: regeneration touches only the ten pseudo-scalar bodies and two includes, and the updated CDNA5 assertions fail against the submitted generator.

### Derive the RDNA4 FLAT allocation bound from the hardware LDS granule

Location: [`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:1013`](https://github.com/ROCm/rocm-systems/blob/85d45c3fce0684d14582449aa42c46fb865120f3/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp#L1013) and lines 1025–1026, which use `wf.lds_size()`. That value comes from [`command_processor.cpp:286`](https://github.com/ROCm/rocm-systems/blob/85d45c3fce0684d14582449aa42c46fb865120f3/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp#L286); the same 256-byte granule is repeated at `compute_unit.h:727` and `compute_unit.cpp:923`.

The PR makes the workgroup allocation size architecturally visible to FLAT for the first time: bytes beyond it read zero and stores are discarded. The emulator rounds the allocation to 256 bytes, but gfx1201 rounds to 512. With a 4,100-byte static allocation, a FLAT or DS store/load round trip on gfx1201 returns data through offset 4604 and zero from 4608. Under the PR, FLAT returns zero from 4352, so it rejects 256 bytes that hardware allocates. Develop never bounded FLAT by the allocation, so this disagreement is new.

The PR's harness tests pack 256-byte allocations back to back. That mirrors the emulator's layout rather than the hardware's, so these tests cannot detect the difference.

Widening only this bound to 512 bytes is not a fix. The emulator packs workgroups at 256-byte granularity, so the extra bytes can belong to a neighbouring workgroup. The allocation granule needs to be per architecture where LDS is allocated and admitted, so that `wf.lds_size()` matches the hardware's `LDS_SIZE`. Add a test with a group segment that is not a multiple of 512. Because this changes LDS occupancy, I have not implemented it. If it is deferred, document in the bound's comment that it is the emulator's allocation, not hardware's.

## Suggestions

### Replicate inline src2 for DOT2 OPSEL high selection

Location: generated RDNA4 `vop3_exec.cpp` lines 7967 and 8047 (`v_dot2_f16_f16` and `v_dot2_bf16_bf16`), where `acc_bits` comes from `read_vop3_true16_src(src2, wf, lane, opsel, 2)`; the generator emits these bodies.

The RDNA4 manual says that, for these instructions, "for source2, the OPSEL bit is used to control replication". With `op_sel:[0,0,1,0]` and zero multiplicands, gfx1201 returns the inline value: `v_dot2_bf16_bf16` gives `0x3F80` for `1.0` and `0xC080` for `-4.0`, and `v_dot2_f16_f16` gives `0x3C00` for `1.0`. Both the base and the PR emulators return 0. This defect predates the PR, but the PR now owns the BF16 inline-format table for this operand and claims gfx1201 qualification for it. Applying `dot2_src_needs_half_replication` to an inline src2 before the OPSEL selection would close the gap; `v_fma_f16` with the same OPSEL correctly reads zero on hardware and in the PR, so this must stay DOT2-specific.

## Commentary

Three pre-existing emulator gaps surfaced in the probes; none is introduced by this PR.

- **Rejected pseudo-scalar inlines.** RDNA4 `v_s_*_f16` with any inline-constant source raises `HSA_STATUS_ERROR_ILLEGAL_INSTRUCTION`, although gfx1201 executes it. LLVM codegen avoids the form, but hand-written assembly does not. The ROCm 7.1 assembler even folds `v_s_exp_f16 s4, 0x3c00` into selector 242, which gfx1201 then executes as `exp2(0)`.
- **Negative IOFFSET hang.** `flat_load_b32 v, v[base:base+1] offset:-4` with the VGPR at the start of the shared aperture returns 0 on hardware, because classification uses the VGPR address and U17 gives `0x1FFFC`. Both emulators hang silently until killed. The PR already lists aperture classification before IOFFSET as follow-up work; the observed failure mode is a hang rather than a fault.
- **Unbounded DS.** DS accesses are not bounded by the workgroup allocation in either emulator: offsets up to 8 KiB return data where gfx1201 returns zero beyond 4,608 bytes. With this PR, FLAT is therefore stricter than DS in the same kernel. A follow-up that fixes the allocation granule could bound both paths together.

The `MemoryAccessObservation` contract additions are well specified. They say that rejected lanes keep nominal request and counter participation, and that the new fields make no timing statement. Perfsim, the other consumer of routed observations, uses them only for timing, which matches that contract.

## Appendix: probes

Build with `hipcc --offload-arch=gfx1201 -O2 -w <file>.hip -o <name>`. Run natively, then as `rocjitsu --config configs/gfx1201_r9700.json --cpu-thread-budget 4 -- ./<name> [args]`. The assembler syntax is that of the ROCm 7.1 LLVM, which uses non-true16 operands for gfx1201.

### Pseudo-scalar inline constants

```cpp
#include <hip/hip_runtime.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>

#define P(idx, asmtxt)                                                                    \
  if (only < 0 || only == idx) {                                                          \
    uint32_t r;                                                                           \
    asm volatile(asmtxt : "=s"(r));                                                       \
    out[idx] = r;                                                                         \
  }

__global__ void probe(uint32_t *out, int only) {
  if (threadIdx.x != 0)
    return;
  P(0, "v_s_exp_f32 %0, 1.0");                          // 0x40000000
  P(1, "s_mov_b32 %0, 0x3c00\n v_s_exp_f16 %0, %0");    // 0x00004000 (register source)
  P(2, "v_s_exp_f16 %0, 1.0");                          // gfx1201: 0x00003c00
  P(3, "v_s_exp_f16 %0, 0.5");                          // gfx1201: 0x00003c00
  P(4, "v_s_exp_f16 %0, 0.15915494");                   // gfx1201: 0x00000000
  P(5, "v_s_sqrt_f16 %0, 4.0");                         // gfx1201: 0x00000000
  P(6, "v_s_exp_f16 %0, -4.0");                         // gfx1201: 0x00003c00
  P(9, "v_s_rcp_f16 %0, 2.0");                          // gfx1201: 0x00007c00
}

// Pass one index per process under the emulator: inline forms abort the queue.
int main(int argc, char **argv) {
  const int only = argc > 1 ? std::atoi(argv[1]) : -1;
  uint32_t *d, h[16];
  if (hipMalloc(&d, 64) != hipSuccess || hipMemset(d, 0xEE, 64) != hipSuccess)
    return 1;
  probe<<<1, 32>>>(d, only);
  if (hipDeviceSynchronize() != hipSuccess)
    return 2;
  if (hipMemcpy(h, d, 64, hipMemcpyDeviceToHost) != hipSuccess)
    return 3;
  for (int i : {0, 1, 2, 3, 4, 5, 6, 9})
    if (only < 0 || only == i)
      std::printf("pseudo[%2d] = 0x%08x\n", i, h[i]);
}
```

### LDS allocation granule

```cpp
#include <hip/hip_runtime.h>
#include <cstdint>
#include <cstdio>

constexpr uint32_t kOffs[] = {4096, 4100, 4348, 4352, 4604, 4608, 5116, 5120, 6140, 6144, 8188, 8192};
constexpr int kN = sizeof(kOffs) / sizeof(kOffs[0]);

// The static array is the kernel's only LDS object, so it starts at LDS offset 0.
__global__ void k(uint32_t *o, int use_ds) {
  __shared__ uint8_t lds[4100];
  if (threadIdx.x < kN) {
    uint32_t off = kOffs[threadIdx.x];
    uint32_t v = 0x5A000000u | off, r;
    if (use_ds) {
      asm volatile("ds_store_b32 %0, %1\n s_wait_dscnt 0" : : "v"(off), "v"(v) : "memory");
      asm volatile("ds_load_b32 %0, %1\n s_wait_dscnt 0" : "=v"(r) : "v"(off) : "memory");
    } else {
      uint64_t addr = reinterpret_cast<uint64_t>(static_cast<void *>(&lds[0])) + off;
      asm volatile("flat_store_b32 %0, %1\n s_wait_storecnt_dscnt 0" ::"v"(addr), "v"(v) : "memory");
      asm volatile("flat_load_b32 %0, %1\n s_wait_loadcnt_dscnt 0" : "=v"(r) : "v"(addr) : "memory");
    }
    o[threadIdx.x] = r;
  }
  if (threadIdx.x == 63)
    o[63] = lds[0];
}

int main(int argc, char **argv) {
  const int use_ds = argc > 1;
  uint32_t *d, h[64];
  if (hipMalloc(&d, 256) != hipSuccess || hipMemset(d, 0xEE, 256) != hipSuccess)
    return 1;
  k<<<1, 64>>>(d, use_ds);
  if (hipDeviceSynchronize() != hipSuccess)
    return 2;
  if (hipMemcpy(h, d, 256, hipMemcpyDeviceToHost) != hipSuccess)
    return 3;
  std::printf("%s:", use_ds ? "ds" : "flat");
  for (int i = 0; i < kN; ++i)
    std::printf(" %u:%s", kOffs[i],
                h[i] == (0x5A000000u | kOffs[i]) ? "data" : (h[i] == 0 ? "zero" : "other"));
  std::printf("\n");
}
```

Observed: gfx1201 FLAT and DS return `data` through 4604 and `zero` from 4608. The PR emulator's FLAT returns `zero` from 4352. Both emulators' DS, and the base emulator's FLAT, return `data` at every offset.

### DOT2 src2 OPSEL replication

```cpp
#include <hip/hip_runtime.h>
#include <cstdint>
#include <cstdio>

#define V(i, txt)                                                                         \
  {                                                                                       \
    uint32_t r = 0xdead0000u, z = 0;                                                      \
    asm volatile(txt : "+v"(r) : "v"(z));                                                 \
    o[i] = r;                                                                             \
  }

__global__ void k(uint32_t *o) {
  if (threadIdx.x)
    return;
  V(0, "v_dot2_f16_f16 %0, %1, %1, 1.0 op_sel:[0,0,1,0]");      // gfx1201: 0xdead3c00
  V(1, "v_dot2_bf16_bf16 %0, %1, %1, 1.0 op_sel:[0,0,1,0]");    // gfx1201: 0xdead3f80
  V(2, "v_dot2_bf16_bf16 %0, %1, %1, -4.0 op_sel:[0,0,1,0]");   // gfx1201: 0xdeadc080
  V(3, "v_fma_f16 %0, %1, %1, 1.0 op_sel:[0,0,1,0]");           // gfx1201: 0xdead0000
}

int main() {
  uint32_t *d, h[4];
  if (hipMalloc(&d, 16) != hipSuccess)
    return 1;
  k<<<1, 32>>>(d);
  if (hipDeviceSynchronize() != hipSuccess || hipMemcpy(h, d, 16, hipMemcpyDeviceToHost) != hipSuccess)
    return 2;
  for (int i = 0; i < 4; ++i)
    std::printf("dot2[%d] = 0x%08x\n", i, h[i]);
}
```

The broader 61-case scalar, VALU and FLAT-LDS boundary probe has the same structure. Its cases are listed in the summary; it is too long to reproduce usefully here.
