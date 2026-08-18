This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#9578

**Revision reviewed:** local rebased head `0abdea5dfd`, a five-commit stack
based directly on `origin/develop@d5ea34c9a0`. The local rebased head has not
been pushed.

**Review mode:** comment-aware full review. I independently reviewed the
complete PR diff and the scalar-selector, address-calculation, memory-pipeline,
checkpoint, plugin, and generated-code contracts, then evaluated every current
top-level review and inline thread against the rebased source.

**Public/repository status:** the upstream repository, source fork, PR, base
branch, and head branch are public. The PR is open and non-draft. GitHub reports
the old published head `39832a6e455c` as conflicting; the local stack is based
directly on current `origin/develop`.

**Submitted-head build before rebase:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests rocjitsu_plugin_race_so --parallel 8
```

Result: all 403 build steps passed in 110.16s real, 796.09s user, and
40.84s sys.

**Canonical generation after rebase:**

```bash
$ISA_GENERATION_WRAPPER --repo $SRC_DIR
```

All ten ISAs regenerated successfully and produced no tracked generated-file
change. The build phase exposed one rebase-only source adaptation: a PR-added
test still referred to the old `gfx1250::` namespace after upstream renamed it
to `cdna5::`. After folding that namespace update into the original
hand-maintained commit, the generated-only top commit remained unchanged and
contains exactly 11 generated files. No generated file appears in the four
lower commits.

**Final rebased build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests rocjitsu_plugin_race_so --parallel 8
```

Result: all 309 rebuild steps passed in 111.30s real, 804.26s user, and
39.58s sys.

**Submitted trap-storage, checkpoint, address, memory, and control-flow
coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterAccessTest.SgprOrTrapSelectorRoutesPerWaveStorage:RegisterAccessTest.TtmpAccessDoesNotAliasAdjacentWaveSgprs:CheckpointTest.SaveAndRestoreHwregState:CheckpointTest.RejectsCheckpointWithoutTrapRegisterState:RdnaAddrCalcTest.Rdna3SmemSoffsetHandlesNullM0AndSgprSelectors:RdnaAddrCalcTest.Rdna3MubufWrapsOffsetPartBeforeBoundsCheck:RdnaAddrCalcTest.Rdna4AddressSelectorsUsePerWaveTrapStorage:RdnaAddrCalcTest.Rdna4SmemSoffsetHandlesNullM0AndSgprSelectors:RdnaAddrCalcTest.Rdna4VbufferUsesDecodedRsrcAndOptionalSoffset:Gfx1250AddrCalcTest.SmemTtmpOffsetUsesPerWaveTrapStorage:CdnaAddrCalcTest.Cdna4SmemOffsetsUsePerWaveTrapStorage:CdnaAddrCalcTest.Cdna4BufferSelectorsUsePerWaveTrapStorage:CdnaMemoryTest.SmemLoadWritesTtmpDestination:TrapRegisterPcTest.SetpcPrecheckReadsDecodedTtmpPair:ConfigLoaderTest.Gfx1250ComputeUnitDefaultsCoverTtmpAndHighVgprs'
```

Result: 15/15 passed, 0 failed, 0 skipped, and 0 errored in 0.09s real.
GoogleTest reported 0.059s.

**Generator/profile coverage:**

```bash
time -p env MRISA_PATH=$MRISA_XML_DIR \
  .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py
```

Result: 255 passed, 0 failed, 1 skipped, and 0 errored in 9.42s real.
Pytest reported 9.28s.

The rebase required updating the PR-added source-shape test to use the
current two-argument `_execution_source_path()` helper and the current
`gfx1250` generated-directory mapping. That adaptation is folded into the
hand-maintained commit that owns the final test shape.

**Special-selector and allocation-boundary counterexamples:**

I temporarily added the five tests in Appendix A:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterAccessTest.ReviewProbeSgprOrTrapUsesPhysicalAllocationBlock:RdnaSelectorReviewProbe.*:CdnaMemoryReviewProbe.*'
```

Result: 0/5 passed in 0.05s real.

- RDNA3 buffer SOFFSET selector 102 read `scratch_base` (`0x80`) instead of
  ordinary `s102` (`0x40`), producing an address 64 bytes too high.
- RDNA1 NULL selector 125 threw
  `Unsupported encoding value for scalar read: 125`.
- RDNA4 SMEM with VCC as SBASE threw
  `Scalar selector 106 is neither an allocated ordinary SGPR nor a trap register`.
- CDNA4 `s_load_dword` with VCC_LO as SDATA failed with the same selector-106
  exception during deferred writeback.
- An ordinary `s40` read on a wave with a 104-register physical block but a
  40-SGPR dispatch declaration was rejected as neither SGPR nor trap state.

All probes were removed after validation. The reviewed source was rebuilt
without them and the submitted 15-test selection above passed.

**Formatting and diff hygiene:**

```bash
time -p .venv/bin/pre-commit run --files \
  $(git diff --name-only origin/develop..HEAD)
git diff --check origin/develop..HEAD
```

Result: every applicable hook passed in 5.61s real, `git diff --check`
passed, and the final source checkout has no tracked modifications.

On the old published head, release, Clang ASan/UBSan, GCC ASan/UBSan, TSan,
pre-commit, CodeQL, HIP NVIDIA, multi-architecture ASan, and repository-policy
checks pass. The broad TheRock gfx94X package build failed and its summary is
red; no completed focused rocJITsu check reports a product failure.

## Summary

The PR fixes a real storage-corruption boundary. Scalar selectors 108 through
123 no longer index the ordinary physical SGPR file. Every resident wave owns
a separate sixteen-dword trap-register array, so a 104-entry wave block cannot
map wave 0 TTMP0 onto wave 1 `s4`, a 106-entry block cannot map it onto wave 1
`s2`, and the final wave cannot index past the scalar file.

The storage lifecycle is coherent. Dispatch and reset clear the array, GFX12
launch setup writes workgroup and cluster payloads into it, halt snapshots and
checkpoints preserve it, and restore rejects a checkpoint without complete
trap-register state. Strict rejection is justified for common old 104/106-SGPR
checkpoints: their serialized per-wave SGPR vector does not contain selectors
108 through 123, so those values cannot be reconstructed reliably.

The submitted routing work covers the original review misses:

- generated scalar operands read and write trap storage;
- architecture address paths use the new selector boundary for TTMP bases,
  offsets, descriptors, and direct resources;
- SMEM stores read TTMP source data;
- deferred SMEM loads write TTMP destinations;
- `s_memtime` and `s_memrealtime` write TTMP pairs;
- the `s_setpc`/`s_swappc` pre-check reads decoded TTMP pairs; and
- the race detector explicitly documents that TTMP hazards remain outside its
  ordinary-SGPR model.

Those changes, their focused 104/106/128-entry regressions, and the
generated-only commit organization are useful and should be retained.

However, the PR currently has two different notions of a scalar selector:

1. `resolve_src_scalar()` / `resolve_dst_write()` model special scalar state,
   but hard-code one architecture's 102/103 and 124/125 layout; and
2. `RegisterAccess::read_sgpr_or_trap_register*()` understands only ordinary
   SGPRs and selectors 108 through 123.

The address and SMEM changes send assembler-valid VCC, EXEC, M0, NULL,
flat-scratch, XNACK, and ordinary high-SGPR encodings through those incomplete
boundaries. The five counterexamples demonstrate wrong values and runtime
exceptions in active paths. This is not merely missing optional coverage: the
PR changes these consumers from permissive raw physical indexing to a stricter
API, so the new API must represent the complete accepted selector contract or
explicitly reject unsupported encodings with an architectural exception.

I found two actionable correctness issues. The earlier checkpoint,
write-side-TTMP, address-path, and race-detector documentation comments are
otherwise addressed in the current code.

## Actionable items

### 1. Define one architecture-complete scalar-selector contract and use it for every SMEM/address source and destination

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h:24-269`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/addr_calc_buffer.h:40-76,169-182`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/addr_calc_scalar.h:28-47`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/rdna4/addr_calc.cpp:28-41,56-61,73-74,105-106,133-135`
- `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:5176-5181,5360-5400`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/mem_state.h:70-82`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_pipeline.cpp:219-228`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp:318-333`

`resolve_src_scalar()` assumes selectors 102/103 are flat scratch on every
architecture and recognizes NULL only when M0 is 125. That matches CDNA's
flat-scratch placement and RDNA3+'s NULL/M0 order, but not the complete family:

- RDNA3 MUBUF accepts ordinary `s102`, yet buffer SOFFSET resolution reads
  `scratch_base`;
- RDNA1/2 use M0=124 and NULL=125, so NULL throws;
- CDNA exposes XNACK_MASK at 104/105, which is neither ordinary SGPR state nor
  modeled special state; and
- SMEM SBASE, SOFFSET, SDATA, and deferred destinations can encode VCC, EXEC,
  M0, NULL, flat scratch, and trap registers.

Define a small shared selector-layout contract containing at least:

```text
ordinary SGPR range
flat-scratch pair, if present
XNACK pair, if present
VCC pair
trap-register window
NULL selector, if present
M0 selector
EXEC pair
```

Make 32- and 64-bit read/write resolution consume that contract. Generate or
select the correct layout for each ISA, and use the same resolver in operand
execution, SMEM address calculation, buffer SOFFSET, SMEM store collection,
`s_memtime`/`s_memrealtime`, and deferred load completion.

Remove the buffer-only `null_selector` branch once NULL is part of the shared
layout. This addresses the current request that NULL behave consistently for
both buffer instructions and ordinary scalar operands.

For assembler-reachable state that is not modeled, such as XNACK if no
Wavefront state exists for it, throw `util::UnimplementedInst` with the
instruction/selector context rather than `std::logic_error` or a physical
SGPR fallback.

The race detector should create `GLOBAL_TO_SGPR` events only for selectors
that the same layout classifies as ordinary SGPR destinations. VCC, EXEC, M0,
NULL, flat scratch, XNACK, and trap state do not participate in the current
ordinary-SGPR hazard model.

Add the first four Appendix A regressions permanently, plus one explicit
unsupported-XNACK case if XNACK remains unmodeled.

### 2. Validate ordinary SGPR selectors against the physical allocation block, not dispatch metadata

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:939-973,1049-1074`
- `emulation/rocjitsu/tests/register_access_test.cpp:432-462`

`validate_sgpr_or_trap_register_range()` requires an ordinary selector to be
below both `wf.max_sgprs()` and `wf.num_sgprs()`. `num_sgprs()` is the
per-dispatch metadata request, while the CU allocator reserves and zeroes the
complete `sgprs_per_wf` physical block.

That metadata count is not an instruction-observation boundary once callable
device code is present. A kernel can declare fewer than 41 SGPRs while a
separate device function uses `s40`. The new helper rejects that ordinary
instruction-visible register even though it lies inside the wave's owned
physical block.

Validate ordinary access against the wave's actual physical allocation block,
capped by the ISA's addressable SGPR range, while continuing to treat
architecture-defined special selectors through the selector layout from item
1. Do not use descriptor metadata as the storage boundary.

Add the fifth Appendix A regression permanently. It should dispatch with
`num_sgprs=40`, retain a 104-register physical block, and successfully access
ordinary `s40` without crossing into another wave.

## Suggestions

### 1. Preserve strict checkpoint fallback when reconciling the overlapping debugger PR

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/checkpoint.cpp:104-121`
- `emulation/rocjitsu/schemas/checkpoint.fbs`

The broader debugger PR independently adds sixteen TTMP values and attempts to
migrate an old checkpoint from serialized `sgprs[108..123]` when those entries
exist. That migration can be useful for old 128-entry records, but common
104/106-entry records do not contain the complete legacy window.

When the two implementations are reconciled, preserve this PR's rejection as
the fallback. Migration is safe only when the old checkpoint contains every
value needed by the architecture; otherwise restore must fail rather than
silently zero workgroup IDs or partial trap state.

The selector-based API in this PR is also the clearer contract for RDNA1:
selectors 108 through 111 are TBA/TMA, not TTMP0 through TTMP3. The broader
debugger branch should adapt to the chosen selector/storage contract rather
than landing an independent second trap-register file.

## Commentary

### Review-thread status

The current source addresses these requests:

- Old checkpoints without complete trap-register state are rejected, and
  `<algorithm>` is included directly.
- The original RDNA/CDNA address-calculation omissions are routed through
  per-wave trap storage.
- MUBUF/MTBUF descriptors, SOFFSET, and SMEM SBASE paths have focused TTMP
  cross-wave coverage.
- Deferred SMEM loads write TTMP destinations, and SMEM stores read TTMP
  sources.
- The `s_setpc`/`s_swappc` pre-check reads a decoded TTMP pair.
- The race detector now explains why TTMP load/use hazards are intentionally
  unmodeled.

Two live requests remain valid and are covered by actionable item 1:

- non-TTMP special selectors still need one architecture-aware source and
  destination boundary; and
- NULL should move out of the buffer-only policy and into that shared
  boundary.

The developer can handle the already-addressed thread replies and resolutions.
Suggested local reply text:

```text
Addressed: scalar-memory load/store routing now carries the decoded selector
through deferred completion, so TTMP destinations and sources use per-wave
storage. Focused cross-wave coverage verifies the loaded value round-trips
without modifying the former physical alias.
```

```text
Addressed: the race-detector route now documents that trap-register hazards
are outside the ordinary-SGPR model, so TTMP loads intentionally create no
GLOBAL_TO_SGPR event until dedicated trap-register hazard tracking exists.
```

For the remaining selector-policy threads, the appropriate response after a
future fix is to point to the permanent versions of the Appendix A
counterexamples and the shared architecture-layout resolver.

### Scope and landing coordination

The storage separation itself is focused and valuable. The broader debugger
PR is still open and has grown into a large trap/CWSR execution stack. The
clean landing sequence is:

1. complete the scalar-selector contract in this focused PR;
2. land this storage/checkpoint boundary with its allocation regressions; and
3. rebase the debugger stack, dropping its duplicate trap-storage changes and
   adapting its debugger-specific state to the chosen Wavefront API.

Landing both storage implementations independently would create conflicting
Wavefront and checkpoint contracts.

## Appendix A: temporary counterexamples

The following tests used existing includes, namespace aliases, and the
`Cdna4MemoryTestCu` helper in the repository tests.

```cpp
TEST(RegisterAccessTest, ReviewProbeSgprOrTrapUsesPhysicalAllocationBlock) {
  ScopedIsaExecutionBackend execution_backend_scope{&cdna4::execution_backend()};
  GpuMemory gpu_mem{"review_sgpr_block_mem"};
  L2Cache l2{"review_sgpr_block_l2"};
  ComputeUnitCore::Config cfg{};
  cfg.arch = ROCJITSU_CODE_ARCH_CDNA4;
  cfg.num_wf_slots = 1;
  cfg.sgprs_per_wf = 104;
  cfg.vgprs_per_wf = 16;
  cfg.lds_size_kb = 64;
  auto cu = ComputeUnitCore::create("review_sgpr_block_cu", cfg, &gpu_mem, &l2);
  ASSERT_NE(cu, nullptr);

  auto *wf = cu->dispatch_wf(0, 0, /*num_sgprs=*/40, cfg.vgprs_per_wf);
  ASSERT_NE(wf, nullptr);
  cu->write_sgpr(wf->sgpr_alloc().base + 40, 0x12345678u);

  EXPECT_EQ(RegisterAccess(*wf).read_sgpr_or_trap_register(40), 0x12345678u);
}
```

```cpp
TEST(RdnaSelectorReviewProbe, Rdna3BufferSoffsetS102ReadsOrdinarySgpr) {
  amdgpu::GpuMemory mem("review_rdna3_s102_mem");
  amdgpu::L2Cache l2("review_rdna3_s102_l2");
  amdgpu::ComputeUnitCore::Config cfg{};
  cfg.arch = ROCJITSU_CODE_ARCH_RDNA3;
  cfg.num_wf_slots = 1;
  cfg.sgprs_per_wf = 106;
  cfg.vgprs_per_wf = 16;
  cfg.lds_size_kb = 64;
  auto cu = amdgpu::ComputeUnitCore::create("review_rdna3_s102_cu", cfg, &mem, &l2);
  ASSERT_NE(cu, nullptr);
  auto *wf = cu->dispatch_wf(0, 0, cfg.sgprs_per_wf, cfg.vgprs_per_wf);
  ASSERT_NE(wf, nullptr);
  wf->set_exec(1);

  constexpr uint64_t kBase = 0x1'0000'1000ULL;
  uint32_t sbase = wf->sgpr_alloc().base;
  cu->write_sgpr(sbase, static_cast<uint32_t>(kBase));
  cu->write_sgpr(sbase + 1, static_cast<uint32_t>(kBase >> 32));
  cu->write_sgpr(sbase + 2, 0x1000u);
  cu->write_sgpr(sbase + 3, 1u << 31);
  cu->write_sgpr(sbase + 102, 0x40u);
  wf->set_scratch_base(0x80u);

  rdna3::MubufMachineInst inst{};
  inst.srsrc = 0;
  inst.soffset = 102;
  amdgpu::VectorMemState d(amdgpu::GLOBAL_MEM);
  rdna3::mubuf_calculate_addresses(inst, *wf, d);

  EXPECT_EQ(d.per_lane_addr[0], kBase + 0x40u);
}
```

```cpp
TEST(RdnaSelectorReviewProbe, Rdna1NullSourceResolvesToZero) {
  amdgpu::GpuMemory mem("review_rdna1_null_mem");
  amdgpu::L2Cache l2("review_rdna1_null_l2");
  amdgpu::ComputeUnitCore::Config cfg{};
  cfg.arch = ROCJITSU_CODE_ARCH_RDNA1;
  cfg.num_wf_slots = 1;
  cfg.sgprs_per_wf = 106;
  cfg.vgprs_per_wf = 16;
  cfg.lds_size_kb = 64;
  auto cu = amdgpu::ComputeUnitCore::create("review_rdna1_null_cu", cfg, &mem, &l2);
  ASSERT_NE(cu, nullptr);
  auto *wf = cu->dispatch_wf(0, 0, cfg.sgprs_per_wf, cfg.vgprs_per_wf);
  ASSERT_NE(wf, nullptr);

  EXPECT_EQ(amdgpu::resolve_src_scalar(*wf, rdna1::OPR_SRC_NULL,
                                       rdna1::OPR_SRC_M0),
            0u);
}
```

```cpp
TEST(RdnaSelectorReviewProbe, Rdna4SmemVccBaseIsResolved) {
  amdgpu::GpuMemory mem("review_rdna4_vcc_sbase_mem");
  amdgpu::L2Cache l2("review_rdna4_vcc_sbase_l2");
  amdgpu::ComputeUnitCore::Config cfg{};
  cfg.arch = ROCJITSU_CODE_ARCH_RDNA4;
  cfg.num_wf_slots = 1;
  cfg.sgprs_per_wf = 106;
  cfg.vgprs_per_wf = 16;
  cfg.lds_size_kb = 64;
  auto cu = amdgpu::ComputeUnitCore::create("review_rdna4_vcc_sbase_cu", cfg, &mem, &l2);
  ASSERT_NE(cu, nullptr);
  auto *wf = cu->dispatch_wf(0, 0, cfg.sgprs_per_wf, cfg.vgprs_per_wf);
  ASSERT_NE(wf, nullptr);

  constexpr uint64_t kBase = 0x2'0000'2000ULL;
  wf->set_vcc(kBase);
  rdna4::SmemMachineInst inst{};
  inst.sbase = rdna4::OPR_SMEM_OFFSET_VCC_LO / 2;
  inst.soffset = rdna4::OPR_SMEM_OFFSET_NULL;

  EXPECT_EQ(rdna4::smem_calculate_address(inst, *wf), kBase);
}
```

```cpp
TEST(CdnaMemoryReviewProbe, SmemLoadWritesVccDestination) {
  amdgpu::GpuMemory mem("review_cdna4_smem_vcc_destination_mem");
  amdgpu::L2Cache l2("review_cdna4_smem_vcc_destination_l2");
  amdgpu::ComputeUnitCore::Config cfg{};
  cfg.arch = ROCJITSU_CODE_ARCH_CDNA4;
  cfg.num_wf_slots = 1;
  cfg.sgprs_per_wf = 104;
  cfg.vgprs_per_wf = 16;
  cfg.lds_size_kb = 64;
  auto cu = std::make_unique<Cdna4MemoryTestCu>(
      "review_cdna4_smem_vcc_destination_cu", cfg, &mem, &l2);
  auto *wf = cu->dispatch_wf(0, 0, cfg.sgprs_per_wf, cfg.vgprs_per_wf);
  ASSERT_NE(wf, nullptr);

  constexpr uint64_t kAddress = 0x7100;
  constexpr uint32_t kValue = 0x89ABCDEFu;
  cu->write_sgpr(wf->sgpr_alloc().base, static_cast<uint32_t>(kAddress));
  cu->write_sgpr(wf->sgpr_alloc().base + 1,
                 static_cast<uint32_t>(kAddress >> 32));
  mem.write32(kAddress, kValue);

  const auto words = cdna4::build_smem(
      cdna4::kSLoadDwordSmem,
      {.sbase = 0, .sdata = cdna4::OPR_SDST_VCC_LO});
  auto decoder = Decoder::create(ROCJITSU_CODE_ARCH_CDNA4);
  ASSERT_NE(decoder, nullptr);
  std::unique_ptr<Instruction> inst(decoder->decode(words.data()));
  ASSERT_NE(inst, nullptr);
  cu->execute_and_route(inst.release(), *wf);

  EXPECT_EQ(static_cast<uint32_t>(wf->vcc()), kValue);
}
```
