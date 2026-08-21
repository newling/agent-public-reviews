This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#9578

**Revision reviewed:** local rebased head `34e6e5113cb3`, a six-commit stack
based directly on `origin/develop@c1dba564e7e3`. The local rebased head has not
been pushed.

**Review mode:** comment-aware self-review. I first reconstructed the storage,
selector, checkpoint, generated-code, and memory-writeback contracts, then
independently evaluated every top-level review, inline thread, and discussion
comment against the rebased source. I also compared the design with overlapping
open rocJITsu PRs.

**Public/repository status:** the upstream repository, source fork, PR, base
branch, and head branch are public. The PR is open and non-draft.

**Rebase:**

```bash
git fetch origin develop pull/9578/head:refs/remotes/origin/pr/9578
git rebase origin/develop
```

The six commits rebased successfully after resolving three conflicts. Current
`develop` added GFX12 TTMP8 queue-packet and wave-in-workgroup launch state after
the PR was written. The resolution preserves that newer ABI behavior and routes
TTMP6, TTMP7, TTMP8, and TTMP9 through the PR's per-wave trap-register storage.
The corresponding TTMP8 snapshot tests were retained and adapted to inspect the
trap-register file.

**Build:**

```bash
cmake --build $BUILD_DIR \
  --target rocjitsu_tests rocjitsu_plugin_race_so --parallel 8
```

Result: the clean rebased build passed all 635 build steps. The final incremental
verification reported no work and completed in 0.03s real, 0.02s user, and
0.01s sys. The initial full-build wall time was not captured.

**Submitted focused regressions:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterAccessTest.SgprOrTrapSelectorRoutesPerWaveStorage:RegisterAccessTest.SgprOrTrapUsesReservedPhysicalAllocationBlock:RegisterAccessTest.TtmpAccessDoesNotAliasAdjacentWaveSgprs:CheckpointTest.SaveAndRestoreHwregState:CheckpointTest.RejectsCheckpointWithoutTrapRegisterState:RdnaAddrCalcTest.Rdna3SmemSoffsetHandlesNullM0AndSgprSelectors:RdnaAddrCalcTest.Rdna4SmemSoffsetHandlesNullM0AndSgprSelectors:RdnaScalarSelectorTest.*:CdnaScalarSelectorTest.*:Gfx1250SimulationTest.Ttmp8EncodesWaveIdWithinWorkgroup:Gfx1250SimulationTest.Ttmp8EncodesQueuePacketId'
```

Result: 13/13 passed, 0 failed, 0 skipped, and 0 errored in 0.38s real,
0.19s user, and 0.18s sys. This includes the rebased TTMP8 launch-state
coverage.

**Generator/profile coverage:**

```bash
time -p env MRISA_PATH=$MRISA_XML_DIR \
  .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_profile_properties.py
```

Result: 404 passed, 0 failed, 2 skipped, and 0 errored in 12.60s real.
Pytest reported 12.42s.

**Formatting and diff hygiene:**

```bash
time -p .venv/bin/pre-commit run --files \
  $(git diff --name-only origin/develop...HEAD)
git diff --check origin/develop...HEAD
```

Result: every applicable hook passed in 6.15s real, and `git diff --check`
passed. The checkout has no tracked modification after removing the temporary
review probes.

**Four new review-comment counterexamples:**

I temporarily added the four tests in Appendix A:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='ScalarSelectorReviewProbe.*'
```

Result: 0/4 passed in 0.06s real.

- A four-dword load to RDNA NULL wrote the second word to M0 and the next two
  words to EXEC.
- An RDNA3 wave using the checked-in 104-dword physical SGPR block rejected
  valid ordinary selectors 104 and 105.
- `can_resolve_src_scalar()` returned true for selector 239, while
  `resolve_src_scalar()` threw.
- RDNA1 selectors 104 and 105 read and wrote `scratch_base` instead of ordinary
  SGPR storage.

A temporary 0-through-255 cross-check repeated the predicate-versus-runtime
comparison on all ten AMDGPU profiles. The only predicate mismatch was selector
239, reproduced on every profile; the probe was removed after validation.

**Assembler cross-checks:**

```bash
printf '%s\n' 's_mov_b32 s0, s104' |
  $LLVM_MC -triple=amdgcn-amd-amdhsa -mcpu=gfx1010 -show-encoding

printf '%s\n' 's_mov_b32 s0, flat_scratch_lo' |
  $LLVM_MC -triple=amdgcn-amd-amdhsa -mcpu=gfx1010 -show-encoding

printf '%s\n' 's_load_b64 null, s[0:1], 0x0' |
  $LLVM_MC -triple=amdgcn-amd-amdhsa -mcpu=gfx1100 -show-encoding

printf '%s\n' 's_mov_b32 s0, src_pops_exiting_wave_id' |
  $LLVM_MC -triple=amdgcn-amd-amdhsa -mcpu=gfx1010 -show-encoding
```

Results:

- gfx1010 accepts `s104` with selector encoding 104.
- gfx1010 rejects `flat_scratch_lo` as unavailable.
- gfx1100 accepts the 64-bit NULL destination.
- gfx1010 accepts `src_pops_exiting_wave_id` with selector encoding 239.

**Published-head CI and the link comment:**

The published head's release, Clang ASan/UBSan, GCC ASan/UBSan, TSan,
pre-commit, CodeQL, HIP NVIDIA, multi-architecture ASan, gfx94X package, and
MI455 package jobs pass.

The red gfx950 TheRock job did not reach configure, compile, or link. It spent
30 minutes fetching TheRock submodules and was terminated while cloning source;
the later report and upload steps then failed because no build directory or
manifest existed. That CI failure is not evidence of a product link defect.

The discussion comment that the PR did not link did not include a command or
diagnostic. I could not reproduce it after the rebase: the complete local
`rocjitsu_tests` and race-plugin build links successfully. A concrete command
and linker diagnostic would still be useful if the reviewer sees a distinct
configuration-specific failure.

## Summary

The core correction is valid and should not be discarded. Scalar selectors
108 through 123 are architectural per-wave state, not offsets into the
ordinary SGPR allocation. Giving each wave a separate sixteen-dword
trap-register file prevents wave 0 TTMP0 from aliasing wave 1 ordinary SGPRs
under 104- or 106-dword physical blocks and prevents the final resident wave
from indexing beyond the scalar register file.

The storage lifecycle is coherent:

- dispatch/reset clears the file;
- GFX12 launch setup initializes TTMP6 through TTMP9, including current
  `develop`'s TTMP8 queue-packet and wave-ID fields;
- generated operands and active address paths route TTMP selectors to the
  per-wave file;
- halt snapshots and checkpoints preserve the state; and
- checkpoint restore rejects records without complete trap-register state.

The PR also correctly addresses the earlier review misses around buffer
descriptors, SOFFSET, SMEM bases and data, deferred scalar-memory destinations,
`s_memtime`, `s_memrealtime`, and the indirect-PC pre-check.

The problem is the second layer added around that storage. The PR grew from a
focused trap-register ownership fix into a repository-wide scalar-selector
policy used by generated operands, address calculation, scalar-memory
collection and writeback, race-event classification, and physical register
validation. That abstraction is a reasonable direction, but it is not yet a
closed contract:

- a selector is classified one dword at a time even when the instruction
  destination is a multi-dword sink;
- one generated profile maps valid ordinary registers onto nonexistent special
  state;
- valid ordinary selector windows are larger than some configured physical
  blocks; and
- the SIMD capability predicate disagrees with runtime resolution.

These are not reasons to restore the old raw `sgpr_base + selector` behavior.
They are reasons to finish the selector boundary before landing it.

The better design is narrower than replacing the whole PR:

1. Keep `Wavefront`'s separate selector-108-through-123 storage and the strict
   checkpoint contract.
2. Keep operand-specific legality in the generated decoder, now that merged PR
   #9894 validates selector encodings.
3. Make runtime resolution responsible only for mapping an already-valid
   scalar selector to architectural storage/value.
4. Make destination resolution range-aware: classify the base destination and
   width once, validate the whole operation, then apply it atomically.

A small API shaped like the following would make that boundary explicit:

```text
read_scalar_source(wave, selector) -> value
read_scalar_source_pair(wave, selector) -> value
write_scalar_destination(wave, selector, span<dwords>)
classify_scalar_storage(arch, selector) -> ordinary / flat-scratch /
    xnack / vcc / trap / null / m0 / exec / special-source
```

`write_scalar_destination()` should discard the complete span for NULL, reject
an unsupported width before producing any partial side effect, and validate an
ordinary/trap range before writing its first dword. This avoids teaching the
memory pipeline that the next numeric selector after NULL is M0 or EXEC.

I found four actionable issues. The per-wave storage approach itself remains
the right foundation.

## Actionable items

### 1. Resolve scalar-memory destinations as one range so a wide NULL write is a complete sink

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_pipeline.cpp:226-234`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h:203-282`

`ScalarMemPipeline::complete_access()` resolves each returned dword as an
independent selector:

```cpp
resolve_dst_write(wf, d.dst_selector + i, d.response_data[i]);
```

That is incorrect for a multi-dword NULL destination. On RDNA3+, selector 124
is NULL, 125 is M0, and 126/127 are EXEC. An accepted
`s_load_b64 null, ...` therefore discards the first dword and writes the second
to M0. A four-dword load also overwrites EXEC.

Classify the destination base and transfer width once before the loop. NULL
must discard the whole transfer. Ordinary SGPR and trap-register spans should
be validated as complete ranges before any write. Special pairs such as VCC,
EXEC, and flat scratch should accept only widths with defined semantics; an
unsupported width should fail before changing the first register.

Add permanent behavior coverage for at least `s_load_b64 null` and
`s_load_b128 null`, seeding M0 and EXEC and verifying both remain unchanged.

### 2. Remove the RDNA1 flat-scratch override and cover s104/s105 reads and writes

**Files:**

- `emulation/rocjitsu/lib/python/amdisa/isa_profile.py:1344-1346`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/generated/shared/isa_properties.h:106-122`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_selector_layout.h:18-24`

The RDNA1 profile marks selectors 104/105 as flat scratch. That causes
`resolve_src_scalar()` and `resolve_dst_write()` to redirect ordinary s104/s105
accesses to `Wavefront::scratch_base`.

The canonical assembler accepts s104 on gfx1010 and rejects
`flat_scratch_lo` as unavailable. The temporary regression confirms that both
reads and writes use the wrong storage.

Return `None` for RDNA1's `scalar_flat_scratch_base_selector`, as RDNA2 already
does, regenerate the properties/output, and add direct read/write coverage for
s104 and s105 with a distinct scratch-base value.

### 3. Require every configured SGPR block to cover the architecture's ordinary selector window

**Files:**

- `emulation/rocjitsu/configs/gfx1100_w7900.json:69`
- `emulation/rocjitsu/configs/gfx1151.json:69`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.cpp:426-435`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:1077-1087`

The generated layout permits ordinary selectors through s105 for RDNA3 and
RDNA3.5, while the checked-in gfx1100 and gfx1151 configurations reserve only
104 dwords per wave. The new checked resolver consequently rejects valid s104
and s105 accesses.

Increase those blocks to at least 106 and reject any future configuration where
`sgprs_per_wf <= scalar_sgpr_max_selector`. The diagnostic should distinguish
an architecturally invalid selector from a valid selector that the topology
failed to allocate.

Keep the runtime range check as defense in depth; configuration validation
prevents a shipped topology from creating the mismatch in the first place.

### 4. Restore the exact `can_resolve_src_scalar()` contract for selector 239

**File:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h:84-102,133-144`

`can_resolve_src_scalar()` returns true for every selector in 235 through 253,
but runtime resolution handles 235 through 238 and then incorrectly labels
selector 249 as `SRC_POPS_EXITING_WAVE_ID`. The generated operand tables and
the assembler place that source at selector 239.

Handle selector 239, remove the incorrect 249 interpretation unless a separate
architecture-specific source proves it valid, and express the predicate with
the exact supported set rather than the broad 235-through-253 interval.

Add a 0-through-255 invariant test for every generated architecture profile:
when `can_resolve_src_scalar()` returns true, `resolve_src_scalar()` must not
throw for a valid wave with a sufficiently large physical SGPR block.

## Suggestions

### 1. Separate generated operand legality from runtime storage classification

**Files:**

- `emulation/rocjitsu/lib/python/amdisa/isa_profile.py`
- `emulation/rocjitsu/lib/python/amdisa/isa_properties_codegen.py`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_selector_layout.h`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h`

Merged PR #9894 now rejects operand-type-specific reserved selector encodings at
decode time. The runtime selector layer should not attempt to reproduce every
operand type's admissible set. It should map valid selectors to architectural
state and fail clearly when the emulator does not model that state.

Keep the generated properties small and storage-oriented: ordinary SGPR
window, flat-scratch pair, XNACK pair, NULL, M0, VCC, trap window, and EXEC.
Use direct cross-checks against generated operand constants and a few canonical
assembler probes for profile overrides where the machine-readable source is
known to be misleading.

### 2. Preserve strict checkpoint fallback when reconciling the debugger stack

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/checkpoint.cpp`
- `emulation/rocjitsu/schemas/checkpoint.fbs`

Open PR #9844 independently adds an index-based `ttmp_[16]` file and checkpoint
field inside a much larger debugger stack. Its old-checkpoint migration copies
whatever portion of `sgprs[108..123]` happens to exist.

When that stack rebases, it should drop the duplicate storage and consume this
PR's selector-based API. Migration is safe only if an old record contains the
complete legacy selector window needed by the architecture. Common 104- and
106-dword records do not, so the strict rejection in this PR must remain the
fallback rather than silently restoring a partial or zeroed launch identity.

## Commentary

### Existing review feedback

The current source addresses these earlier requests:

- checkpoints without complete trap-register state are rejected;
- the direct `<algorithm>` dependency is present;
- RDNA/CDNA address paths, buffer descriptors, SOFFSET, SMEM SBASE, and direct
  resources route TTMP selectors through per-wave storage;
- scalar-memory stores read TTMP sources;
- scalar-memory loads carry decoded destinations into deferred completion;
- `s_memtime` and `s_memrealtime` route decoded destinations;
- the indirect-PC pre-check handles TTMP pairs; and
- the race detector documents that trap-register hazards remain outside the
  ordinary-SGPR model.

The shared architecture-aware resolver also substantially addresses the
earlier non-TTMP-special-selector and buffer-only-NULL concerns.

The four August 18 comments all remain valid:

- wide NULL writeback crosses into M0/EXEC;
- checked-in RDNA blocks do not cover s104/s105;
- selector 239 violates the predicate/runtime invariant; and
- RDNA1 incorrectly classifies s104/s105 as flat scratch.

The no-diagnostic link comment is not reproduced after the rebase. The only red
published TheRock job failed while fetching sources, before compilation.

### Related open rocJITsu work

**PR #9844 — ROCgdb debugger stack**

This open, approved stack changes 119 files and overlaps 36 paths with this PR.
It independently owns TTMP storage, checkpointing, scalar operand resolution,
address calculation, memory writeback, and command-processor launch state.

The focused storage PR should land first after the four issues above are fixed.
The debugger stack should then rebase, drop its duplicate `ttmp_[16]` and
checkpoint field, and adapt its CWSR/trap-handler code to the selector-based
Wavefront API. Landing both implementations independently would create two
incompatible trap-register and checkpoint contracts.

**PR #10030 — wave-owned register observation**

This open stack overlaps 23 paths. It hardens physical SGPR/VGPR ownership,
range atomicity, and plugin observation, while deliberately leaving selectors
108 through 123 for this PR.

After this PR lands, #10030 should rebase and make its physical ownership APIs
the implementation beneath ordinary SGPR access. Trap state should remain
Wavefront-owned and should not be folded back into the physical SGPR file.

**PR #10250 — CDNA IMM=0 SMEM SGPR offsets**

This open PR overlaps the generator and `addr_calc_scalar.h`. Its current
implementation reads the decoded OFFSET selector as a raw physical SGPR index.
The same encoding table also permits M0, so rebasing it unchanged would
reintroduce the class of selector/storage bug this PR is trying to eliminate.

That PR should use the completed architecture-aware scalar-source resolver for
the register-offset form and retain its decode/def-use improvements.

**Merged PR #9894 — operand selector validation**

This work is now in `develop` and rejects operand-specific reserved encodings
before execution. It complements this PR: decoder validation answers whether a
selector is legal for that operand, while this PR should answer where a legal
selector's state lives.

### Landing recommendation

Do not abandon the separate trap-register storage and do not merge the current
head unchanged.

Recommended sequence:

1. fix the four selector/range issues in this PR;
2. retain the generated-only top commit and rerun all-ISA generation;
3. land this focused storage and checkpoint boundary;
4. rebase #10030 onto it and use its physical ownership APIs for ordinary
   registers;
5. rebase #9844, dropping duplicate TTMP/checkpoint ownership; and
6. rebase #10250 so its new SMEM offset form uses the shared selector resolver.

## Appendix A: temporary counterexamples

```cpp
TEST(ScalarSelectorReviewProbe, WideNullWritebackLeavesSpecialStateUnchanged) {
  amdgpu::GpuMemory mem("review_wide_null_mem");
  amdgpu::L2Cache l2("review_wide_null_l2");
  amdgpu::ComputeUnitCore::Config cfg{};
  cfg.arch = ROCJITSU_CODE_ARCH_RDNA3;
  cfg.num_wf_slots = 1;
  cfg.sgprs_per_wf = 128;
  cfg.vgprs_per_wf = 16;
  cfg.lds_size_kb = 64;
  auto cu = amdgpu::ComputeUnitCore::create("review_wide_null_cu", cfg, &mem, &l2);
  ASSERT_NE(cu, nullptr);
  auto *wf = cu->dispatch_wf(0, 0, cfg.sgprs_per_wf, cfg.vgprs_per_wf);
  ASSERT_NE(wf, nullptr);

  constexpr uint32_t kM0 = 0xA5A5A5A5u;
  constexpr uint64_t kExec = 0x0123456789ABCDEFULL;
  wf->set_m0(kM0);
  wf->set_exec_raw(kExec);
  for (uint32_t i = 0; i < 4; ++i)
    amdgpu::resolve_dst_write(*wf, rdna3::OPR_SDST_NULL + i, 0x11111111u * (i + 1));

  EXPECT_EQ(wf->m0(), kM0);
  EXPECT_EQ(wf->exec_raw(), kExec);
}
```

```cpp
TEST(ScalarSelectorReviewProbe, Rdna3ConfiguredBlockCoversOrdinaryS104S105) {
  amdgpu::GpuMemory mem("review_rdna3_block_mem");
  amdgpu::L2Cache l2("review_rdna3_block_l2");
  amdgpu::ComputeUnitCore::Config cfg{};
  cfg.arch = ROCJITSU_CODE_ARCH_RDNA3;
  cfg.num_wf_slots = 1;
  cfg.sgprs_per_wf = 104;
  cfg.vgprs_per_wf = 16;
  cfg.lds_size_kb = 64;
  auto cu = amdgpu::ComputeUnitCore::create("review_rdna3_block_cu", cfg, &mem, &l2);
  ASSERT_NE(cu, nullptr);
  auto *wf = cu->dispatch_wf(0, 0, cfg.sgprs_per_wf, cfg.vgprs_per_wf);
  ASSERT_NE(wf, nullptr);

  EXPECT_NO_THROW(static_cast<void>(amdgpu::resolve_src_scalar(*wf, 104)));
  EXPECT_NO_THROW(static_cast<void>(amdgpu::resolve_src_scalar(*wf, 105)));
}
```

```cpp
TEST(ScalarSelectorReviewProbe, CanResolveMatchesSelector239RuntimeResolution) {
  amdgpu::GpuMemory mem("review_selector_239_mem");
  amdgpu::L2Cache l2("review_selector_239_l2");
  amdgpu::ComputeUnitCore::Config cfg{};
  cfg.arch = ROCJITSU_CODE_ARCH_RDNA1;
  cfg.num_wf_slots = 1;
  cfg.sgprs_per_wf = 106;
  cfg.vgprs_per_wf = 16;
  cfg.lds_size_kb = 64;
  auto cu = amdgpu::ComputeUnitCore::create("review_selector_239_cu", cfg, &mem, &l2);
  ASSERT_NE(cu, nullptr);
  auto *wf = cu->dispatch_wf(0, 0, cfg.sgprs_per_wf, cfg.vgprs_per_wf);
  ASSERT_NE(wf, nullptr);

  ASSERT_TRUE(amdgpu::can_resolve_src_scalar(cfg.arch, 239));
  EXPECT_EQ(amdgpu::resolve_src_scalar(*wf, 239), 0u);
}
```

```cpp
TEST(ScalarSelectorReviewProbe, Rdna1S104S105UseOrdinarySgprStorage) {
  amdgpu::GpuMemory mem("review_rdna1_s104_mem");
  amdgpu::L2Cache l2("review_rdna1_s104_l2");
  amdgpu::ComputeUnitCore::Config cfg{};
  cfg.arch = ROCJITSU_CODE_ARCH_RDNA1;
  cfg.num_wf_slots = 1;
  cfg.sgprs_per_wf = 106;
  cfg.vgprs_per_wf = 16;
  cfg.lds_size_kb = 64;
  auto cu = amdgpu::ComputeUnitCore::create("review_rdna1_s104_cu", cfg, &mem, &l2);
  ASSERT_NE(cu, nullptr);
  auto *wf = cu->dispatch_wf(0, 0, cfg.sgprs_per_wf, cfg.vgprs_per_wf);
  ASSERT_NE(wf, nullptr);

  const uint32_t sbase = wf->sgpr_alloc().base;
  cu->write_sgpr(sbase + 104, 0x11111111u);
  cu->write_sgpr(sbase + 105, 0x22222222u);
  wf->set_scratch_base(0xAABBCCDDEEFF0011ULL);

  EXPECT_EQ(amdgpu::resolve_src_scalar(*wf, 104), 0x11111111u);
  EXPECT_EQ(amdgpu::resolve_src_scalar(*wf, 105), 0x22222222u);
  amdgpu::resolve_dst_write(*wf, 104, 0x33333333u);
  amdgpu::resolve_dst_write(*wf, 105, 0x44444444u);
  EXPECT_EQ(cu->read_sgpr(sbase + 104), 0x33333333u);
  EXPECT_EQ(cu->read_sgpr(sbase + 105), 0x44444444u);
  EXPECT_EQ(wf->scratch_base(), 0xAABBCCDDEEFF0011ULL);
}
```
