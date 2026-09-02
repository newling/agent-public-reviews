This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#10030](https://github.com/ROCm/rocm-systems/pull/10030)

**Revision reviewed:** local rebased candidate `e11a382c70aa`, a five-commit
stack based directly on `origin/develop@60c29efb3903`.

**Review mode:** fresh, comment-aware review. I independently evaluated the
change and then checked every existing review concern against the rebased
candidate.

**Public/repository status:** the repository, PR, base branch, and head
repository are public. The PR is open and non-draft. GitHub still reports the
published head as conflicting because the rebased history has not been pushed.

**Rebase and stack shape:**

The published five-commit stack was rebased onto current `origin/develop`.
The only textual conflict was in `register_access.h`, where the newly merged
lazy-VGPR implementation removed the assumption that adjacent VGPRs have
contiguous backing. The resolution retained the new logical traversal/copy API
and made denied regions return bounded zero spans and zero-filled copies.

`git range-diff` reports four commits patch-equivalent. The register-access
commit differs only where it was adapted to the new lazy storage API. The
rebased stack still has four hand-maintained commits followed by exactly one
generated-only top commit.

**Focused build:**

```bash
cmake --build $BUILD_DIR \
  --target rocjitsu_tests rocjitsu_plugin_race_so \
           rocjitsu_plugin_logging_so --parallel 8
```

The first build after the rebase rebuilt and linked all 645 required steps.
After removing temporary review probes, the final incremental build of the
exact reviewed source passed in 6.22s real, 8.85s user, and 0.97s sys.

**Register/plugin/race coverage excluding the known aborting test:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterAccessTest.*:ExecutionPluginTest.*:HookOrderingTest.*:PluginLoaderTest.*:RaceDetector.*-RegisterAccessTest.FreeWavefrontClearsPhysicalOwnerMaps'
```

Result: 160/161 passed, 0 failed, 1 skipped, and 0 errored in 0.22s real.
`ExecutionPluginTest.MfmaFastPathReadHookReportsRace` was skipped because this
host does not provide the required 16-lane native-float SIMD capability.

**Released-storage regression on the exact reviewed source:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterAccessTest.FreeWavefrontClearsPhysicalOwnerMaps'
```

Result: 0 tests completed. The process aborted after 1.10s with:

```text
Assertion `is_allocated(idx) && "const access to a free register block"' failed.
```

This is a genuine rebase integration failure. The test directly reads SGPR and
VGPR storage after `free_wavefront_resources()`. The lazy register-file change
merged into `develop` now correctly rejects access to a freed block.

**Wide conversion coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Cdna4CvtScaleTest.WideFp6ToF16ConsumesFp16OvflMode:Gfx1250CvtScaleTest.WideUnpackRejectsDestinationRangeBeforeWriting'
```

Result: 2/2 passed, 0 failed, 0 skipped, and 0 errored in 0.04s real.

**Compiler-backed callable-SGPR evidence:**

```bash
time -p $BUILD_DIR/tests/probe_fixture_test \
  --gtest_filter='ProbeFixture.*'
```

Result: 4/4 passed, 0 failed, 0 skipped, and 0 errored in 0.01s real. This
includes the real gfx950 code object whose entry-kernel descriptor grants
`s0..s39` while a separately callable function uses `s40`.

**Focused generator tests:**

```bash
time -p env MRISA_PATH=$MRISA_XML_DIR \
  .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_profile_properties.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_sema_derive.py
```

Result: 832 passed, 0 failed, 2 skipped, and 0 errored in 13.07s real.

**All-ISA generation:**

```bash
ALLOW_DIRTY=1 BUILD_JOBS=8 FORMAT_JOBS=8 \
  $ISA_GENERATION_WRAPPER --repo $SRC_DIR --skip-build
```

All-ten-ISA generation completed and was content-idempotent. It left no
tracked source changes.

**Formatting and diff hygiene:**

```bash
time -p bash -lc \
  'git diff --name-only origin/develop...HEAD -z |
   xargs -0 .venv/bin/pre-commit run --files'
git diff --check origin/develop...HEAD
```

Every applicable hook passed in 7.51s real, and `git diff --check` passed.
The reviewed checkout has no tracked modifications.

**Temporary denied-region probe:**

Appendix B's two-register VGPR straddle passed. The denied read region returned
two bounded zero spans and filled a `2 * wave_size` destination with zeros.
This confirms that the rebase conflict resolution closes the stale raw-pointer
hazard raised against the published head.

**Temporary instruction-side SGPR counterexample:**

Appendix A's gfx1250 buffer-descriptor test failed as expected. A four-dword
descriptor beginning in the final two SGPRs of the executing wave consumed its
upper two dwords from the adjacent wave. Address calculation retained lane 0
and produced `0x200001000`; the expected behavior is to reject the complete
descriptor before consuming any part of it.

**Published-head CI context:**

The completed rocJITsu release, Clang/GCC sanitizer, TSan, formatting, policy,
and multi-architecture checks on the published head passed. The red TheRock
summary came from a gfx94X self-hosted runner/container failure during source
fetch. Its later report and upload steps failed only because no build artifacts
had been produced. This is infrastructure noise rather than a product failure.

## Summary

The PR is trying to establish a single architectural boundary for
instruction-visible register access:

1. an access belongs to one live wavefront;
2. the complete multi-register range is validated before callbacks or storage
   effects;
3. plugin callbacks occur before storage is exposed or modified;
4. physical block capacity, rather than the entry kernel's requested register
   count, defines the ordinary register-observation domain; and
5. ownership ends when wave resources are released.

That is the right objective. The physical-block decision is supported by the
compiler-backed callable-SGPR fixture: valid callable code can use a register
beyond the entry kernel's descriptor count. Treating descriptor counts as
resource metadata while treating the reserved physical block as the ordinary
instruction-access domain is coherent.

The decomposition is also good. This patch extracts the observation and
ownership foundation from the closed SGPR write-after-write detector PR rather
than combining register attribution, hazard policy, wait-counter semantics, and
trap-register storage in one review. The future detector should consume a
stable SGPR-write callback without having to defend against partial or
cross-wave architectural operations.

The implementation now handles several difficult cases correctly:

- SGPR64 and VGPR64 accesses validate the complete range before callbacks or
  storage changes;
- wave-bound SGPR/VGPR operations keep the explicit wave authoritative;
- denied operand write views no longer fall through to scalar/raw writes;
- split-profile generated writes validate ownership and retain the executing
  wave;
- wide gfx1250 conversion loops acquire complete source and destination
  regions;
- released waves cannot claim block zero after their allocation is cleared;
- reverse ownership maps are cleared at resource release; and
- raw runtime/memory-completion writes remain outside instruction observation.

However, the implementation does not yet satisfy its own top-level invariant.
Instruction code still constructs `RegisterAccess` from a compute unit. That
compatibility path resolves ownership from the requested physical index, so an
out-of-range index from wave A is accepted as a valid access belonging to wave
B. The temporary buffer-descriptor test demonstrates a single instruction
assembling one logical operand from two waves. This is not merely incomplete
migration or imperfect callback attribution; it changes the instruction's
computed address.

The trap-selector boundary is also unresolved. Selectors 108-123 remain mapped
to ordinary physical SGPR indices. The new wave-bound checks make some of those
accepted operands silently read as zero or drop writes on CDNA configurations
whose physical block ends before selector 123. The focused TTMP PR contains the
right storage model, but it is currently conflicting with `develop` and
materially overlaps the broader debugger stack. This PR therefore needs either
an explicit landing dependency on the reconciled TTMP work or a temporary
fail-closed policy for unbacked selectors.

Finally, the rebase onto lazy VGPR allocation invalidated one submitted test.
The branch builds, but its focused register suite aborts because the test reads
freed storage directly.

I would not land the current rebased candidate. The core design should be
retained, but the instruction-side CU-bound path, TTMP dependency, and
freed-storage test need resolution first.

## Actionable items

### 1. Require the executing wave for instruction-side physical register access

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:1054-1070`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/cdna5/addr_calc.cpp:153-163`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/cdna5/addr_calc.cpp:226-249`
- corresponding generated/shared AMDGPU instruction helpers that construct
  `RegisterAccess` from a compute unit

The CU-bound read path asks the reverse ownership map who owns the requested
physical index. It has no executing-wave identity to compare against. A
physical index that escaped wave A's block can therefore be accepted as wave
B's valid register.

Appendix A starts a four-dword gfx1250 buffer descriptor in wave A's final two
SGPRs. `mubuf_calculate_addresses()` reads the first two words under wave A and
the final two words under wave B, then produces a usable address. A descriptor
is one architectural operand and must be accepted or rejected as one range
owned by the executing wave.

Thread `Wavefront&` through instruction-side address, data, and matrix helpers.
Acquire each SGPR/VGPR range once against that wave before reading any dword.
Keep CU-bound lookup only for genuinely CU-oriented diagnostics or
compatibility code that has no executing wave.

Add the Appendix A regression and a repository-level check that instruction
implementation code does not construct CU-bound `RegisterAccess` when a
`Wavefront` is available. The same audit should cover generated VGPR paths:
one-register reverse lookup has the same adjacent-wave attribution failure
mode even when the first demonstrated counterexample is an SGPR descriptor.

### 2. Stop reading register storage after wave resources are freed

**File:**

- `emulation/rocjitsu/tests/register_access_test.cpp:700-723`

`FreeWavefrontClearsPhysicalOwnerMaps` calls raw CU SGPR/VGPR reads after
`free_wavefront_resources()`. The newly merged lazy register file rejects
const access to a free block, so the focused suite aborts before making the
ownership-map assertions.

Exercise the reverse lookup through `RegisterAccess(*fx.cu)` after release and
ignore the returned values. Retain only the assertions that no SGPR/VGPR
callback was emitted. This tests the intended ownership-map contract without
requiring freed storage to remain readable or retain its old contents.

### 3. Establish a safe landing contract for scalar selectors 108-123

**File:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h:28-40`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h:141-149`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h:204-215`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h:240-249`

These selectors represent per-wave TTMP/TBA/TMA state, but they are still
formed as `wf.sgpr_alloc().base + selector`. With a 112-register CDNA block,
TTMP4-TTMP15 fall outside the wave's ordinary block. The new wave-owned checks
then return zero or drop the write while the decoder still treats the operand
as supported.

Do not add the full debugger stack to this PR. Instead, choose one explicit
landing contract:

- land and reconcile the focused per-wave TTMP storage work first, then rebase
  this PR onto it; or
- make unbacked special selectors fail closed explicitly until that storage
  lands.

Add a CDNA regression covering selector 112 or later so accepted TTMP operands
cannot silently degrade into zero/no-op behavior.

## Suggestions

### 1. Complete runtime boundary coverage for every wide conversion region

**Files:**

- `emulation/rocjitsu/lib/python/amdisa/codegen/execute/vector_special.py:1527-1598`
- `emulation/rocjitsu/tests/instruction_execution_harness_test.cpp:5135-5178`

The implementation now acquires complete regions, but the permanent runtime
test covers only an unpack destination straddle. Add:

- a 16x6 unpack source straddle; and
- one pack case that exercises both source and destination width calculations.

Generated-text assertions are useful, but they do not prove that denied views
remain inert through the decoded instruction path.

### 2. Pin the SDWA scalar-destination emission in a generator or instruction test

**Files:**

- `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:9141-9148`
- `emulation/rocjitsu/tests/register_access_test.cpp:536-549`

The generator correctly emits one `write_sgpr64()` call, but the current C++
boundary test calls `resolve_dst_write64()` directly. Replacing the generated
SDWA cleanup with two `write_sgpr()` calls would not fail that test.

Add either a focused generator assertion for the emitted call or a decoded SDWA
compare boundary test.

### 3. Keep a permanent denied multi-register region regression after the lazy-VGPR rebase

**File:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:671-760`
- `emulation/rocjitsu/tests/register_access_test.cpp`

The rebase conflict resolution safely adapts denied regions to the new
non-contiguous VGPR storage API, and Appendix B passes. Preserve that test so a
future change cannot reintroduce an undersized shared zero buffer, traverse
foreign storage, or make `copy_to()` assert on a denied multi-register range.

## Commentary

### Existing review feedback

| Review concern | Rebased-candidate status |
| --- | --- |
| Complete-range SGPR64/VGPR64 ownership | Addressed with atomic range validation and direct boundary tests. |
| Denied operand views falling through to raw/scalar writes | Addressed with explicit denied state and inert stores. |
| Split-profile generated VGPR writes using CU-bound/raw access | Addressed for the originally identified operand path. |
| SDWA 64-bit scalar destination written as two dwords | Implementation addressed; direct generator/instruction coverage is still missing. |
| Wide scale conversions touching words one at a time | Implementation addressed; runtime boundary coverage remains partial. |
| Released wave appearing to own block zero | Addressed with nonempty allocation checks and `ReleasedWaveCannotOwnReallocatedRegisterBlock`. |
| Denied `VgprReadRegion` exposing an undersized raw zero pointer | Superseded by the merged lazy-VGPR API; the rebase resolution safely uses bounded spans/copies. Permanent coverage is still advisable. |
| TTMP selectors mapped into ordinary SGPR storage | Open; requires a landing dependency or explicit fail-closed policy. |
| Instruction-side CU-bound SGPR reads | Open and reproduced as a cross-wave descriptor correctness failure. |

The unresolved GitHub thread about released-wave ownership can be considered
implemented even though the thread itself remains open. The two ownership
predicates require nonempty SGPR/VGPR allocations, and the permanent regression
checks both storage and callback isolation.

### Relationship to surrounding work

- The closed SGPR write-after-write detector PR is a downstream consumer of
  this infrastructure. Its detector policy should remain separate until this
  ownership boundary is stable.
- The AMDGPU model/execution source split has already landed. This stack follows
  the new generated execution layout and retains one generated-only top commit.
- The lazy-VGPR allocation change landed after the published PR head. It removes
  contiguous multi-register storage assumptions and is the source of both the
  rebase conflict and the freed-storage test failure.
- The focused TTMP storage PR has the correct per-wave storage direction but is
  currently conflicting and overlaps the much broader debugger PR. Those two
  implementations should be reconciled before this PR relies on TTMP storage.

### Recommended landing sequence

1. Fix the freed-storage regression so the rebased branch passes its focused
   suite.
2. Remove instruction-side CU-bound register access for the affected paths and
   add the cross-wave descriptor regression.
3. Decide the TTMP landing dependency or temporary fail-closed behavior.
4. Add the narrow generator/conversion/denied-region tests.
5. Re-run all-ISA generation, focused tests, and changed-file pre-commit.
6. Publish the rebased branch only after explicit approval; no GitHub comments,
   thread resolutions, or force-pushes were performed during this review.

## Appendix A: instruction descriptor must not mix adjacent waves

The temporary test was added beside the existing gfx1250 address-calculation
tests:

```cpp
TEST(Gfx1250AddrCalcTest, DescriptorCannotMixAdjacentWaveSgprs) {
  amdgpu::GpuMemory mem("gfx1250_vbuffer_cross_wave_sgpr_mem");
  amdgpu::L2Cache l2("gfx1250_vbuffer_cross_wave_sgpr_l2");
  amdgpu::ComputeUnitCore::Config cfg{};
  cfg.arch = ROCJITSU_CODE_ARCH_GFX1250;
  cfg.num_wf_slots = 2;
  cfg.sgprs_per_wf = 106;
  cfg.vgprs_per_wf = 16;
  cfg.lds_size_kb = 64;
  auto cu = amdgpu::ComputeUnitCore::create(
      "gfx1250_vbuffer_cross_wave_sgpr_cu", cfg, &mem, &l2);
  ASSERT_NE(cu, nullptr);

  auto *executing_wave =
      cu->dispatch_wf(0, 0, cfg.sgprs_per_wf, cfg.vgprs_per_wf);
  auto *adjacent_wave =
      cu->dispatch_wf(1, 0, cfg.sgprs_per_wf, cfg.vgprs_per_wf);
  ASSERT_NE(executing_wave, nullptr);
  ASSERT_NE(adjacent_wave, nullptr);
  executing_wave->set_exec(1ULL);
  ASSERT_EQ(adjacent_wave->sgpr_alloc().base,
            executing_wave->sgpr_alloc().base + cfg.sgprs_per_wf);

  constexpr uint64_t kBase = 0x2'0000'1000ULL;
  const uint32_t descriptor =
      executing_wave->sgpr_alloc().base + cfg.sgprs_per_wf - 2;
  cu->write_sgpr(descriptor, static_cast<uint32_t>(kBase));
  cu->write_sgpr(descriptor + 1, static_cast<uint32_t>(kBase >> 32));
  cu->write_sgpr(adjacent_wave->sgpr_alloc().base, 1u);
  cu->write_sgpr(adjacent_wave->sgpr_alloc().base + 1, 0u);

  cdna5::VbufferMachineInst inst{};
  inst.rsrc = cfg.sgprs_per_wf - 2;
  inst.soffset = cdna5::OPR_SREG_NULL;

  amdgpu::VectorMemState d(amdgpu::GLOBAL_MEM);
  cdna5::mubuf_calculate_addresses(inst, *executing_wave, d);
  EXPECT_EQ(d.lane_mask, 0ULL);
  EXPECT_EQ(d.per_lane_addr[0], 0ULL);
}
```

Observed result:

```text
d.lane_mask       = 1
d.per_lane_addr[0] = 8589938688 (0x200001000)
```

## Appendix B: denied lazy-VGPR region returns bounded zeros

The temporary probe used the existing `Fixture` and constants from
`register_access_test.cpp`:

```cpp
TEST(RegisterAccessTest, DeniedMultiRegisterReadRegionReturnsBoundedZeros) {
  Fixture fx(ROCJITSU_CODE_ARCH_CDNA4, kSgprsPerWave,
             /*wavefront_slots=*/2);
  ASSERT_NE(fx.wf, nullptr);
  auto *adjacent_wave =
      fx.cu->dispatch_wf(/*wg_id=*/1, /*pc=*/0,
                         kSgprsPerWave, kVgprsPerWave);
  ASSERT_NE(adjacent_wave, nullptr);

  const uint32_t boundary = adjacent_wave->vgpr_alloc().base - 1;
  auto region = RegisterAccess(*fx.wf).read_vgpr_region(
      boundary, /*reg_count=*/2, /*lane_mask=*/1);
  EXPECT_TRUE(region.empty());

  std::vector<uint32_t> copied(2 * fx.wf->wf_size(), 0xA5A5A5A5u);
  region.copy_to(copied);
  for (uint32_t value : copied)
    EXPECT_EQ(value, 0u);

  uint32_t visited = 0;
  region.for_each([&](std::span<const uint32_t> lanes) {
    ++visited;
    ASSERT_EQ(lanes.size(), fx.wf->wf_size());
    for (uint32_t value : lanes)
      EXPECT_EQ(value, 0u);
  });
  EXPECT_EQ(visited, 2u);
}
```

Result: 1/1 passed in 0.02s real.
