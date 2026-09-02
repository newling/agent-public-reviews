This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9578](https://github.com/ROCm/rocm-systems/pull/9578)

**Revision reviewed:** local head `456f82bda2`, a six-commit stack based
directly on `origin/develop@d5ea34c9a0`. The local head has not been pushed.

**Review mode:** comment-aware implementation follow-up. This review rechecks
the two actionable items from the earlier review and the still-live selector
policy threads.

**Build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests rocjitsu_plugin_race_so --parallel 8
```

Result: the final formatted build passed all 620 steps in 139.78s real,
1035.49s user, and 54.42s sys.

**Selector, trap-storage, checkpoint, address, and memory regressions:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterAccessTest.SgprOrTrapSelectorRoutesPerWaveStorage:RegisterAccessTest.SgprOrTrapUsesReservedPhysicalAllocationBlock:RegisterAccessTest.TtmpAccessDoesNotAliasAdjacentWaveSgprs:CheckpointTest.SaveAndRestoreHwregState:CheckpointTest.RejectsCheckpointWithoutTrapRegisterState:RdnaAddrCalcTest.Rdna3SmemSoffsetHandlesNullM0AndSgprSelectors:RdnaAddrCalcTest.Rdna3MubufWrapsOffsetPartBeforeBoundsCheck:RdnaAddrCalcTest.Rdna4AddressSelectorsUsePerWaveTrapStorage:RdnaAddrCalcTest.Rdna4SmemSoffsetHandlesNullM0AndSgprSelectors:RdnaAddrCalcTest.Rdna4VbufferUsesDecodedRsrcAndOptionalSoffset:Gfx1250AddrCalcTest.SmemTtmpOffsetUsesPerWaveTrapStorage:CdnaAddrCalcTest.Cdna4SmemOffsetsUsePerWaveTrapStorage:CdnaAddrCalcTest.Cdna4BufferSelectorsUsePerWaveTrapStorage:CdnaMemoryTest.SmemLoadWritesTtmpDestination:CdnaMemoryTest.SmemLoadWritesVccDestination:TrapRegisterPcTest.SetpcPrecheckReadsDecodedTtmpPair:ConfigLoaderTest.Gfx1250ComputeUnitDefaultsCoverTtmpAndHighVgprs:RdnaScalarSelectorTest.*:CdnaScalarSelectorTest.*'
```

Result: 21/21 passed, 0 failed, 0 skipped, and 0 errored in 0.09s real.
This includes permanent versions of all five earlier counterexamples plus an
explicit CDNA XNACK fail-closed case.

**Race-detector core coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RaceDetector.*'
```

Result: 77/77 passed, 0 failed, 0 skipped, and 0 errored in 0.02s real.

**Complete rocJITsu unit binary:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests --gtest_brief=1
```

Result: 2,819 passed, 0 failed, 1 skipped, and 0 errored in 486.49s real.
The skip is the existing native-float SIMD capability check.

**Complete AMDISA Python suite:**

```bash
time -p env MRISA_PATH=$MRISA_XML_DIR \
  .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests
```

Result: 1,328 passed, 0 failed, 45 skipped, and 0 errored in 26.68s real.

**Generation:**

```bash
before=$(git diff | sha256sum | cut -d' ' -f1)
ALLOW_DIRTY=1 $ISA_GENERATION_WRAPPER --repo $SRC_DIR --skip-build
after=$(git diff | sha256sum | cut -d' ' -f1)
test "$before" = "$after"
```

Result: all-ten-ISA regeneration was content-idempotent. Both diffs had
SHA-256 `7fdf769b9d5d02368ccc15527f5c8301a459230c593835110ff16eb7574256b5`.

The incremental selector fix regenerates 16 files: ten ISA operand execution
files, four CDNA SMEM execution files, `generated/shared/execute_shared.h`, and
`generated/shared/isa_properties.h`. The final combined generated-only top
commit contains 22 files because it also retains the submitted PR's earlier
SMEM regeneration.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files <all changed files>
git diff --check
```

Result: every applicable hook passed and `git diff --check` passed.

## Summary

The implementation now has one scalar-selector policy rather than separate
buffer, SMEM, operand, and trap-only interpretations.

AMDISA profiles define the architecture differences:

- the largest ordinary SGPR selector;
- the flat-scratch pair, when present;
- the XNACK pair, when present;
- NULL, when present; and
- M0.

Those values are emitted into the shared runtime `IsaProperties` table.
`scalar_selector_layout.h` provides pure classification helpers, while
`scalar_operand_resolve.h` owns architectural reads and writes. Generated
operands, hand-maintained address calculation, generated SMEM stores,
`s_memtime`/`s_memrealtime`, and deferred SMEM load completion all use that
same boundary.

This resolves the concrete architecture mismatches:

- RDNA3 selector 102 remains ordinary `s102`, not flat scratch.
- RDNA1/2 selector 125 resolves as NULL while selector 124 remains M0.
- CDNA selector 102/103 resolves as flat scratch.
- CDNA selector 104/105 is recognized as XNACK and throws
  `util::UnimplementedInst` because Wavefront does not model XNACK state.
- VCC, EXEC, M0, NULL, trap state, and ordinary SGPRs use their architectural
  storage for both immediate and deferred memory paths.

`RegisterAccess::read_sgpr_or_trap_register*()` now validates ordinary SGPRs
against the reserved physical register block and the generated architecture
layout, not `Wavefront::num_sgprs()`. This matches the open register-observation
work: descriptor metadata is resource accounting, while callable instruction
code may use any ordinary register in the reserved block.

The race detector uses the same classification and creates
`GLOBAL_TO_SGPR` events only for ordinary physical SGPR destinations. Special
scalar state remains intentionally outside its current hazard model.

I found no remaining actionable correctness, test, generated-output, or
maintainability issue in the post-fix stack.

## Actionable items

None.

## Suggestions

None.

## Commentary

### Existing review feedback

The previously unresolved feedback is addressed:

- NULL handling is shared across ordinary operands and buffer SOFFSET rather
  than remaining a buffer-only policy.
- SMEM SBASE, SOFFSET, SDATA, and deferred destinations use the
  architecture-complete resolver.
- Assembler-valid VCC, EXEC, M0, NULL, flat-scratch, ordinary SGPR, and trap
  selectors no longer reach the trap-only helper.
- Unsupported XNACK state fails with an architectural unimplemented exception.
- Ordinary SGPR validation uses the physical allocation block rather than
  dispatch metadata.

Suggested reply text for the selector-policy threads:

```text
Addressed with one profile-generated scalar-selector layout shared by
generated operands, SMEM, buffer/address calculation, deferred writeback, and
race-event classification. Permanent regressions cover RDNA3 s102, RDNA1 NULL,
RDNA4 VCC SBASE, CDNA4 VCC destination, and CDNA XNACK.
```

```text
Addressed: NULL and M0 are now architecture properties consumed by the shared
resolver. Buffer SOFFSET no longer carries a separate NULL policy, so ordinary
scalar operands and memory operands use the same behavior.
```

### Coordination with ongoing work

The physical-block validation deliberately matches the open wave-owned
register-observation change. If that PR lands first, this branch should rebase
onto its `sgpr_allocation_block_size()` helper rather than retain duplicate
range logic.

The broader debugger PR should continue to consume the selector-based
trap-register API and strict checkpoint fallback from this focused change.
It should drop its duplicate TTMP storage during rebase. Migration of legacy
TTMP values is safe only when the old checkpoint actually serialized the
complete selector window; common 104/106-entry records still require rejection.
