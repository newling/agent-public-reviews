This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#9578

**Revision reviewed:** published head `a2ef19ecd42`, based directly on
`origin/develop@9dcf7d5f244`.

The final rebase includes the newly merged result-based decoder API and
switch-dispatched operand validation. The PR's generated selector routing was
preserved, and its three valid-decode tests now use the repository's
`decode_valid()` helper.

**Build:**

```bash
cmake --build $BUILD_DIR \
  --target rocjitsu_tests rocjitsu_plugin_race_so --parallel 8
```

Result: the canonical post-generation rebuild passed all 658 steps.

**Focused selector, storage, topology, and memory-writeback coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RdnaScalarSelectorTest.Rdna1S104S105UseOrdinarySgprStorage:ScalarSelectorTest.*:RdnaMemoryTest.WideSmemLoadToNullLeavesM0AndExecUnchanged:ConfigLoaderTest.LoadRdnaKmdConfigs:ConfigLoaderTest.RejectsSgprBlockSmallerThanOrdinarySelectorWindow:RegisterAccessTest.SgprOrTrapSelectorRoutesPerWaveStorage:RegisterAccessTest.TtmpAccessDoesNotAliasAdjacentWaveSgprs:CdnaMemoryTest.SmemLoadWritesTtmpDestination:CdnaMemoryTest.SmemLoadWritesVccDestination:FunctionalSchedulingTest.SleepVarYieldsBeforeQuantumExpires:RdnaAddrCalcTest.Rdna4AddressSelectorsUsePerWaveTrapStorage:Gfx1250AddrCalcTest.SmemTtmpOffsetUsesPerWaveTrapStorage:RegisterAccessTest.ReadRegionTraversesAndCopiesLogicalRegisterRange:RegisterAccessTest.Packed16ReadsAndWritesObserveSelectedByteHalves:RegisterAccessTest.OperandReadViewFallbackUsesLaneSemantics:AllIsas/CuFactoryTest.CreatesSuccessfully/*' \
  --gtest_brief=1
```

Result: 26/26 passed, 0 failed, 0 skipped, and 0 errored in 0.11s real.

**Complete non-benchmark C++ suite:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='-*Benchmark*' --gtest_brief=1
```

Result: 2,925 passed, 0 failed, 2 skipped, and 0 errored in 133.34s real.
The skips are existing environment-dependent SIMD tests.

**Complete AMDISA Python suite:**

```bash
time -p env MRISA_PATH=$MRISA_XML_DIR \
  .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests
```

Result: 1,358 passed, 0 failed, 46 skipped, and 0 errored in 28.58s real.

**All-ISA generation:**

```bash
ALLOW_DIRTY=1 $ISA_GENERATION_WRAPPER \
  --repo $SRC_DIR --skip-build
```

Result: all ten AMDGPU ISAs regenerated successfully. Only
`generated/shared/isa_properties.h` changed. A second generation pass was
content-idempotent; the complete working diff had the same SHA-256 before and
after generation.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files $(git diff --name-only)
git diff --check
```

Result: every applicable hook passed and `git diff --check` passed.

## Summary

The four actionable findings from the self-review are addressed with one
coherent runtime contract.

Scalar-memory completion now resolves a destination as a range:

- a NULL base discards the complete transfer;
- one-dword writes use the existing scalar resolver;
- two-dword writes use the existing architecture-aware pair resolver; and
- wider writes must be either a completely ordinary-SGPR range or a completely
  trap-register range.

Unsupported wide destinations are rejected before their first side effect.
`RegisterAccess` validates the full ordinary/trap range before writing any
dword.

The architecture selector model is corrected:

- RDNA1 s104/s105 use ordinary physical SGPR storage rather than
  `scratch_base`;
- `SRC_POPS_EXITING_WAVE_ID` resolves at selector 239;
- reserved selectors 249/250 are no longer claimed by the runtime resolver;
  and
- a permanent 0-through-255 cross-check keeps
  `can_resolve_src_scalar()` consistent with runtime resolution on all ten
  profiles.

The physical topology invariant is now enforced at
`ComputeUnitCore::create()`, not only in the JSON loader. Every construction
path therefore requires enough ordinary physical SGPR slots for the
architecture's selector window. The checked-in gfx1100 and gfx1151 topologies
now reserve 106 slots, and test fixtures use 106 or the architecture's normal
128-slot block as appropriate.

The separate per-wave trap-register storage remains unchanged and is still the
correct core design.

## Actionable items

None.

## Suggestions

None.

## Commentary

### Review feedback status

All current review feedback is now addressed:

- wide NULL scalar loads preserve M0 and EXEC;
- RDNA1 s104/s105 read and write ordinary SGPR storage;
- every shipped and directly constructed CU covers the ordinary selector
  window;
- selector 239 agrees between capability testing and runtime resolution;
- TTMP, VCC, ordinary SGPR, NULL, M0, EXEC, flat-scratch, and unsupported
  XNACK paths retain the architecture-aware boundary from the original PR; and
- range validation prevents a rejected wide destination from producing a
  partial write.

### Landing split

Keep the hand-maintained changes below a generated-only top commit. The only
new generated file is:

```text
emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/generated/shared/isa_properties.h
```

The focused trap-register PR can now land before the overlapping debugger and
wave-owned register-observation stacks. Those branches should rebase onto this
storage and selector contract rather than retain duplicate TTMP/checkpoint
ownership.
