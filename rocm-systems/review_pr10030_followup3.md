This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#10030](https://github.com/ROCm/rocm-systems/pull/10030)

**Revision reviewed:** rebased candidate `ddf9937351d`, based directly on
`origin/develop` commit `c1dba564e7e` after the merged gfx1250 wave-ABI
change.

**Review mode:** comment-aware self-review after rebasing. Existing review
concerns were independently rechecked against the rebased source.

**Rebase and stack shape:**

The branch rebased cleanly onto the current base. It retains five
hand-maintained commits followed by exactly one generated-only top commit.
`git diff --check` passes, and the source checkout has no tracked
modifications.

**Focused build:**

```bash
cmake --build $BUILD_DIR \
  --target rocjitsu_tests rocjitsu_plugin_race_so \
           rocjitsu_plugin_logging_so --parallel 8
```

Result: all 659 requested build steps passed.

**Focused C++ tests:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterAccessTest.*:ExecutionPluginTest.SgprWriteObservationUsesExplicitWavePhysicalBlock:Gfx1250AddrCalcTest.DescriptorCannotMixAdjacentWaveSgprs:Gfx1250CvtScaleTest.WideUnpackRejectsDestinationRangeBeforeWriting:Gfx1250CvtScaleTest.WideRegionsRejectSourceAndPackBoundariesBeforeWriting:Gfx1250SimulationTest.TtmpWorkgroupIdsUseGridCoordinatesFor2DDispatch:Gfx1250SimulationTest.Ttmp8EncodesWaveIdWithinWorkgroup'
```

Result: 42/42 passed, 0 failed, 0 skipped, and 0 errored in 0.46s real.

**Focused generator tests:**

```bash
time -p env MRISA_PATH=$MRISA_PATH \
  .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_profile_properties.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_sema_derive.py
```

Result: 833 passed, 0 failed, 2 skipped, and 0 errored in 16.35s real.

The first attempt without `MRISA_PATH` had 17 XML-dependent failures because
the sparse checkout intentionally omits the machine-readable ISA repository.
Those failures disappeared when rerun with the canonical shared XML corpus.

**Formatting and diff hygiene:**

```bash
git diff --name-only -z origin/develop...HEAD |
  xargs -0 .venv/bin/pre-commit run --files
git diff --check origin/develop...HEAD
```

All applicable hooks and `git diff --check` passed.

**Temporary descriptor-boundary counterexample:**

Appendix A changes one value in the submitted
`Gfx1250AddrCalcTest.DescriptorCannotMixAdjacentWaveSgprs` setup, rebuilds
`rocjitsu_tests`, and runs only that test. The modified test fails as expected:
the rejected descriptor produces `lane_mask == 1` and address
`0x200001000`. The source was restored and the original test was rebuilt and
rerun successfully afterward.

**Published CI context:**

The published head's rocjitsu release, Clang/GCC sanitizer, TSan, formatting,
policy, CodeQL, and supported package jobs pass. The visible failure is the
MI455 package build and its aggregate TheRock summary; this review did not
find a source-level failure corresponding to that job.

## Summary

The central design is good. `RegisterAccess` gives instruction execution one
place to establish three related contracts:

1. an instruction-visible access has an explicit owning wavefront;
2. the complete physical register range is validated before plugin callbacks
   expose storage or make it writable; and
3. runtime initialization and memory completion remain deliberately raw,
   unobserved storage operations.

The important API choice is the `InstructionComputeUnitView`. Existing
instruction helpers can continue to receive a CU-shaped service object, but
that object now retains the executing wave. Consequently,
`RegisterAccess(wf.cu())` is wave-bound rather than a reverse-map lookup. This
addresses the earlier concern about address and matrix helpers silently
attributing escaped physical indices to an adjacent wave without requiring a
large mechanical rewrite of their signatures.

The physical-block policy also remains justified. The compiler-backed callable
fixture demonstrates that a callable function may use SGPRs outside the entry
kernel descriptor's reported count. Observation must therefore cover the
reserved physical block, while descriptor counts remain resource metadata.

The PR correctly fixes several difficult cases:

- SGPR64 and VGPR64 APIs validate their full ranges before callbacks or storage
  effects;
- denied logical operand views no longer fall through into raw or scalar
  writes;
- split generated execution paths retain the executing wave;
- denied lazy-VGPR regions return bounded zero views and copies;
- released waves cannot claim physical block zero; and
- wide conversion source and destination boundary coverage now exercises
  unpack-source, unpack-destination, pack-source, and pack-destination
  cases.

However, the PR does not yet apply its atomicity principle to compound scalar
operands. Address calculation still acquires descriptor dwords and scalar
pairs separately. A descriptor can therefore have valid low words, invalid
high words, valid callbacks for the former, and a functional partial value.
This is a correctness problem for memory instructions, not merely incomplete
instrumentation.

I would retain the architecture and decomposition, but would not land this
revision until the compound-SGPR range boundary is made explicit and used by
address calculation.

## Actionable items

### 1. Make compound scalar operands operation-atomic before address calculation

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/cdna5/addr_calc.cpp:141-147`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/cdna5/addr_calc.cpp:219-267`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/addr_calc_scalar.h:32-39`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/addr_calc_buffer.h:58-67`
- corresponding CDNA4 and RDNA address-calculation helpers

`mubuf_calculate_addresses()` obtains a four-dword buffer descriptor through
four individual `read_sgpr()` calls. Each call is correctly wave-bound, so the
two words beyond the executing wave's allocation return zero rather than
reading another wave. But the first two words have already been observed and
remain usable. `srd1` contains both base-address bits and low record-count
bits; setting only bit 25 preserves the base address while making
`num_records` nonzero. The partially read descriptor then passes the
out-of-bounds check and generates an address.

The same structural issue appears in two-dword SMEM and flat-address bases:
using two independent reads permits a low word to be observed and used when
the high word is denied. Replacing those pairs with `read_sgpr64()` improves
callback atomicity, but the caller still needs an explicit validity result so
that an all-zero denied read cannot be mistaken for a valid base address.

Add a scalar-region acquisition API, or an equivalent `try_read_sgpr*` API,
that:

1. checks the complete requested range against the executing wave before any
   callback;
2. distinguishes denial from a valid zero-valued register region; and
3. lets an address helper fail closed before it creates a usable memory
   address.

Use that API for four-dword descriptors and scalar pairs throughout the
address-calculation surface. For a denied descriptor, clear the affected
`VectorMemState` lane mask and addresses, with no SGPR callbacks. For scalar
memory bases, choose an explicit invalid-address or instruction-failure path;
do not silently treat a denied pair as address zero.

Extend the existing descriptor regression with Appendix A's record-count bit
and a plugin recorder assertion that no descriptor-word callback was emitted.
Add equivalent pair-boundary tests for SMEM and a shared helper so the
operation-level rule cannot regress through another ISA path.

## Suggestions

### 1. Specify the callback contract when one wide-conversion region is denied

**Files:**

- `emulation/rocjitsu/lib/python/amdisa/codegen/execute/vector_special.py:1521-1610`
- `emulation/rocjitsu/tests/instruction_execution_harness_test.cpp:5136-5248`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp:182-193`

The new conversion code acquires the valid source region before discovering
that a destination region is denied. It therefore reports source reads but no
destination write. The race detector immediately checks those source reads
against pending global-to-VGPR events, so an invalid-destination conversion can
still report a missing wait on its valid source.

This is defensible if the model defines the source read as an architectural
effect even when the destination range is rejected. It is not defensible if a
denied destination means the conversion is fully suppressed. Choose one
contract, state it near the region API or generator, and add a race-detector
regression that pins the intended behavior. Preflighting both ranges before
acquisition is the alternative if the desired contract is full-instruction
suppression.

## Commentary

### Existing review feedback

| Review concern | Status in this rebased candidate |
| --- | --- |
| Denied operand views falling through to raw/scalar writes | Addressed. Denied state is explicit and stores are inert. |
| Split-profile generated paths using raw/CU ownership | Addressed. `InstructionComputeUnitView` retains the executing wave, and the generated paths use that wave-bound view. |
| SGPR64/VGPR64 accesses crossing a physical block | Addressed by whole-range validation and direct regressions. |
| SDWA 64-bit scalar destination torn into two writes | Addressed. The generator emits `write_sgpr64()`, and a generator assertion now pins it. |
| Wide conversion words accessed one at a time | Addressed for the identified conversion paths. Runtime tests now cover the unpack source/destination and pack source/destination boundaries. The callback semantics for mixed-validity source/destination remain a contract choice. |
| Released wave appears to own block zero | Addressed by requiring a nonempty allocation and testing released-wave isolation. |
| Denied multi-register VGPR view exposes an undersized zero buffer | Addressed by bounded spans/copies and a denied-region regression compatible with lazy storage. |
| Trap selectors 108-123 access ordinary SGPR storage | Partially addressed: unbacked selectors now fail closed and have direct coverage, but the durable storage design remains separate work. |
| Instruction-side CU-shaped helpers can escape the executing wave | Addressed. Those helpers receive `InstructionComputeUnitView`, whose `RegisterAccess` constructor binds the executing wave. |
| Four-dword descriptor can remain partially functional | Still open; Appendix A reproduces it. |

### Relationship to current rocjitsu work

- The merged gfx1250 wave-ABI change in the base actively initializes TTMP6-9
  through padded physical SGPR slots. This candidate safely rejects unbacked
  selectors, but padded ordinary SGPR storage remains a temporary model.
- Open PRs #9578 and #9844 both contain overlapping per-wave trap-register
  storage. Reconcile one selector-aware storage boundary before treating the
  padded representation as permanent. The focused storage direction is the
  better dependency for this PR; the broader debugger stack should consume
  that result rather than establish a third representation.
- Open PR #10250 changes shared SMEM address calculation and generated SMEM
  paths. It should use the same compound-SGPR validity API rather than add
  another pair-read convention.
- Open PR #10362 changes CDNA5 out-of-bounds behavior in the same address
  calculator and test file. Rebase it after the descriptor contract is fixed
  so its OOB model does not accidentally bless partially acquired descriptors.
- Open PR #10347 changes `mma_exec.h`, generator code, generated output, and
  execution tests. Its helpers already receive the wave-carrying CU view, so
  the ownership model composes, but it should be regenerated and retested on
  the final register-access base.
- Open PR #10346 also changes execution-plugin, wavefront, compute-unit, and
  generator surfaces. Its barrier state benefits from the explicit
  instruction-versus-runtime boundary here, but it should be rebased and
  focused-tested once this foundation is settled.

### Recommended landing sequence

1. Add a validity-bearing compound-SGPR read primitive and migrate address
   calculation to it, including the descriptor and scalar-pair regressions.
2. Rebase and reconcile the overlapping SMEM/OOB work from #10250 and #10362.
3. Land or otherwise select the dedicated per-wave TTMP/TBA/TMA storage model
   from #9578 and #9844; keep it separate from register-observation policy.
4. Regenerate after the final hand-maintained stack and keep one generated-only
   top commit.
5. Re-run focused register/plugin/address/generator tests and changed-file
   formatting before publishing the rebased branch.

## Appendix A: a partially acquired descriptor must not yield an address

The temporary counterexample changes only the existing two-wave descriptor
fixture. The high record-count bit is not part of `buffer_base_addr()`, so the
base remains `0x200001000`, while `buffer_num_records()` becomes one:

```cpp
constexpr uint64_t kBase = 0x2'0000'1000ULL;
const uint32_t descriptor =
    executing_wave->sgpr_alloc().base + cfg.sgprs_per_wf - 2;

cu->write_sgpr(descriptor, static_cast<uint32_t>(kBase));
cu->write_sgpr(descriptor + 1,
               static_cast<uint32_t>(kBase >> 32) | (1u << 25));
cu->write_sgpr(adjacent_wave->sgpr_alloc().base, 1u);
cu->write_sgpr(adjacent_wave->sgpr_alloc().base + 1, 0u);

cdna5::VbufferMachineInst inst{};
inst.rsrc = cfg.sgprs_per_wf - 2;
inst.soffset = cdna5::OPR_SREG_NULL;

amdgpu::VectorMemState d(amdgpu::GLOBAL_MEM);
cdna5::mubuf_calculate_addresses(inst, *executing_wave, d);
EXPECT_EQ(d.lane_mask, 0ULL);
EXPECT_EQ(d.per_lane_addr[0], 0ULL);
```

Observed result on the reviewed revision:

```text
d.lane_mask       = 1
d.per_lane_addr[0] = 8589938688 (0x200001000)
```

The current implementation read and observed the valid low words, replaced the
out-of-range high words with zero, and then treated the resulting descriptor as
an in-bounds one-record buffer. A complete descriptor ownership check must
reject it before any of those reads or callbacks occur.
