This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9396](https://github.com/ROCm/rocm-systems/pull/9396)

**Commit reviewed:** `1ba4b466d9ea` (`addressing review comments`), the current
third commit in the PR stack.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, and GitHub reports the head as cleanly
mergeable into its public feature-branch base. The visible release, Clang
ASan/UBSan, GCC ASan/UBSan, TSan, pre-commit, gfx94X/gfx950 package-build, and
TheRock summary checks pass.

The active development checkout contained unrelated files, so I exported the
public PR head into a disposable source snapshot instead of switching that
checkout.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: all 571 build steps passed in 151.63s real, 1138.04s user, and
55.01s sys.

**New Python operand-generator coverage:**

```bash
time -p env PYTHONPATH=$SRC_DIR/lib/python $PYTHON -m pytest -q \
  $SRC_DIR/lib/python/amdisa/tests/test_semantic_operand_codegen.py
```

Result: 14/14 passed, 0 failed, 0 skipped, 0 errored. Pytest reported
0.20s; `time -p` reported 0.35s real.

**Submitted AccVGPR builder, planner, patch, and simulator coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='MfmaExecTest.DstBase*:\
InstructionBuilder.BuildScratch*AccVgpr:\
InstrumentorSpill.PlanAcc*:\
InstrumentorSpill.PlanSgprSpillsBridgeStaysBelowAccumBase:\
InstrumentorProbeSpill.Cdna3SpillsLiveClobberedAccVgpr:\
InstrumentorProbeSpill.Cdna4SpillsLiveClobberedAccVgpr:\
InstrumentorProbeSpill.Cdna4RejectsAccVgprPastAccumOffsetWindow:\
InstrumentorProbeSpill.Cdna4SpillsLiveClobberedVgprSgprAndAccVgpr:\
DbiCdna3AccVgprSpillSimFixture.*:\
DbiCdna4AccVgprSpillSimFixture.*:\
DbiCdna3CombinedSpillSimFixture.*:\
DbiCdna4CombinedSpillSimFixture.*'
```

Result: 22/22 passed, 0 failed, 0 skipped, 0 errored in 0.12s real.
This includes the simulator negative controls that remove the restore and
confirm that the probe leaves the accumulator value corrupted.

**Neighboring decoded-operand and CDNA execution coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Cdna3DecodeTest.*:Cdna2DecodeTest.*:\
MfmaExecTest.DstBase*:MfmaExecTest.ResolveAcc*:\
InstructionExecutionHarness.Cdna1:InstructionExecutionHarness.Cdna2:\
InstructionExecutionHarness.Cdna3:InstructionExecutionHarness.Cdna4'
```

Result: 14/14 passed, 0 failed, 0 skipped, 0 errored in 0.06s real. Each
CDNA instruction harness completed with zero decode or execution failures; its
single reported unimplemented instruction was the pre-existing `s_setvskip`.

**Malformed-source analysis/execution counterexample:**

I temporarily decoded:

```text
v_accvgpr_read_b32 v3, <raw src0 = 0>
```

`OPR_SRC_ACCVGPR` execution explicitly accepts this raw low form and maps it to
physical AccVGPR index 256 (`acc0`). The review regression therefore required
the semantic operand to produce:

```cpp
RegisterRef{RegClass::ACC_VGPR, 0, 1}
```

On the submitted code the regression failed:

```text
Value of: ref.has_value()
  Actual: false
Expected: true
```

Result: 0/1 passed in 0.02s real.

I then prototyped canonicalizing a raw low source `N` as
`OPR_SRC_ACCVGPR_ACC_MIN + N`, while retaining the submitted mapping for the
well-formed `256 + N` form. The counterexample, the submitted CDNA3 AccVGPR
patch test, and both CDNA3 AccVGPR simulator tests passed: 4/4 passed,
0 failed, 0 skipped, 0 errored in 0.04s real. The 14 Python generator tests
also passed in 0.27s real after updating their expected expression. The
temporary regression and prototype were removed, and the submitted source was
rebuilt and used for the final focused test run.

**Diff hygiene:**

```bash
git diff --check <pr-base>..HEAD
```

Result: passed.

I did not run the full corpus locally. The focused tests above cover the
changed operand, planner, emitter, descriptor-boundary, and simulator
contracts; current public release and sanitizer corpus jobs provide broader
coverage.

## Summary

This PR extends the stacked DBI spill implementation so a copied probe can
clobber live AccVGPRs on CDNA3/CDNA4 without corrupting the interrupted kernel.
It completes two connected paths.

First, it canonicalizes dedicated `OPR_ACCVGPR` and
`OPR_SRC_ACCVGPR` operands. Their encoded fields are not already in the
selector ranges consumed by `Operand::to_register_ref()`. Moving valid fields
into those ranges lets the shared `InstDefUse` chain identify `accN` in both:

```text
target instructions -> liveness live-before set
probe instructions  -> probe clobber set
```

The Instrumentor intersects those sets and sends any live-and-clobbered
AccVGPR lanes to the new planner.

Second, `plan_acc_spills()` validates the register class, architecture,
descriptor-derived AccVGPR window, and scratch offset before assigning a
stable `SpillManager` slot. The trampoline emits CDNA scratch stores and loads
with the FLAT `acc` bit set, so AccVGPRs move directly to per-lane scratch
without the `v_writelane`/`v_readlane` bridge required by SGPRs.

The save/restore runs under full EXEC so inactive lanes are also preserved if
the probe widens EXEC. The original anchor mask is restored for the probe call,
EXEC is widened again for the fills, and the saved special state is restored
before the relocated original instruction runs. Store and load waits protect
the asynchronous scratch operations from probe clobbers and subsequent uses.

The final commit also corrects the ordinary-VGPR bound used for SGPR spill
bridges. On CDNA, `ACCUM_OFFSET` splits the descriptor's unified allocation
into an ordinary prefix and an AccVGPR window; a bridge must remain below that
split. The updated test descriptors make this allocation explicit, add an
empty-window failure case, and exercise a combined VGPR/SGPR/AccVGPR spill.

The decomposition generally matches the project's intended DBI/DBT boundary:
decoded register identity, def/use, liveness, scratch builders, range
allocation, and byte-level descriptor mutation are reusable mechanisms, while
the decision to preserve an interrupted probe call remains DBI policy.

## Actionable items

### 1. Keep malformed AccVGPR source semantics consistent with execution

**Files:** `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:6415-6422`,
`emulation/rocjitsu/lib/python/amdisa/tests/test_semantic_operand_codegen.py:202-218`,
generated examples including
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/cdna3/vop3p.cpp:693-715`

The new `OPR_SRC_ACCVGPR` expression canonicalizes a well-formed raw source
`256 + N`, but deliberately leaves a raw value below 256 unchanged:

```cpp
raw >= 256 ? raw + (ACC_MIN - 256) : raw
```

That leaves the semantic and execution paths inconsistent. For CDNA3,
`Operand::to_register_ref()` recognizes only the canonical
`OPR_SRC_ACCVGPR` range at 768-1023, so raw zero yields no register reference.
However, `vgpr_index(OPR_SRC_ACCVGPR, 0)` explicitly returns physical index
256, meaning execution reads `acc0`. `unified_vgpr_index()` likewise reports
ordinary index zero for the uncanonicalized operand rather than accumulator
index 256.

This is a concrete missed-spill path for malformed or hand-authored code:
liveness or probe-clobber analysis can omit `accN` while the instruction
actually reads it. That is the same class of analysis/execution split the PR
is intended to remove.

Make both paths agree. One working approach is:

```cpp
raw >= 256 ? raw + (ACC_MIN - 256) : raw + ACC_MIN
```

which preserves the submitted well-formed mapping and maps the low form to the
same AccVGPR execution already uses. Alternatively, reject the low form during
decode and execution rather than continuing to execute it without an analysis
dependency.

Add a decoded regression using `v_accvgpr_read_b32` with raw `src0 = 0` and
assert the chosen contract. If execution continues to accept the instruction,
the operand should name `RegClass::ACC_VGPR`, index zero, and unified vector
index 256. The prototype described in Tests made that regression and the
neighboring submitted tests pass.

## Suggestions

### 1. Derive AccVGPR and descriptor properties from the existing ISA traits

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/instrumentor.cpp:129-160`,
`emulation/rocjitsu/lib/python/amdisa/isa_profile.py:1095-1115`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/dbt/kernel_descriptor_translator.cpp:142-166`

The new local `arch_has_accvgpr()` returns true for every CDNA generation,
including CDNA1. The ISA profile explicitly describes CDNA1 as having no
AccVGPR file, and the DBT path obtains this fact from `HasAccVgpr<Isa>`.
The local helper also serves two distinct questions: whether an architecture
has AccVGPRs, and whether its descriptor uses the gfx90a `ACCUM_OFFSET` split.

This does not currently produce a bad AccVGPR spill because CDNA1/CDNA2 are
rejected by the missing scratch emitter before descriptor interpretation is
reached. It nevertheless makes the new descriptor contract fragile and would
become observable if support expands.

Use the existing generated trait/property, or introduce separately named
predicates for:

- an addressable AccVGPR file;
- the gfx90a `ACCUM_OFFSET` descriptor layout; and
- an available DBI AccVGPR scratch emitter.

The neighboring local `vgpr_encoding_granule()` table is another candidate for
the generated ISA-property path, especially because wave-size-dependent
descriptor granules are being centralized separately.

## Commentary

The test structure is a strong part of this PR. Direct generator and builder
tests establish the encoded contracts; planner tests cover class, architecture,
offset, and descriptor bounds; static patch tests inspect the emitted bracket;
simulator tests prove the value survives; and sabotage tests prove the restore
is causally necessary. The combined three-register-class simulator test is
particularly useful because it exercises slot identity, bridge selection,
EXEC handling, wait ordering, and descriptor growth together.

The PR is also a useful example of why rocJITsu distinguishes raw
`MachineInst` fields from semantic `Operand` values. Execution can remain
numerically functional through permissive resolver fallbacks while liveness
and instrumentation silently lose the same dependency. Generator changes in
this area should continue to be checked in both directions:

```text
raw encoding -> semantic RegisterRef
raw encoding -> runtime physical register
```

Those mappings should either agree or reject the same input.

PR 9219's shared-design document will need a refresh after the stacked spill
work lands: it currently describes `SpillManager` as not yet wired into the
Instrumentor and non-empty spill sets as failing closed. The implementation
still supports the document's larger architectural point, however: share the
neutral facts and emitters without merging DBI's probe-preservation policy
with DBT's semantic-lowering spill policy.
