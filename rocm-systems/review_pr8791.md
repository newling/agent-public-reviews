This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8791

**Commit reviewed:** `977e716383fe` (`rocjitsu: address decoder review feedback`),
the fifth commit in the PR's five-commit stack.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, not draft, targets `develop`, and its head branch is in
the same public repository.

**C++ build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: passed. The initial full PR-head rebuild took 207.24s real, 1578.28s
user, 50.23s sys. After the final review-feedback commit was pushed, the
incremental final-head rebuild also passed in 6.88s real, 17.80s user, 1.78s
sys. The broad initial rebuild was expected because the PR regenerates
instruction sources across multiple CDNA and RDNA architectures.

**New Python generator tests:**

```bash
python3 -m venv $PYTEST_ENV
$PYTEST_ENV/bin/pip install -q -e emulation/rocjitsu/lib/python pytest
time -p $PYTEST_ENV/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_semantic_operand_codegen.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_smem_sbase_operand.py
```

Result on the final head: 15/15 passed, 0 failed, 0 skipped, 0 errored. Pytest
reported 0.15s; `time -p` reported 0.30s real, 2.17s user, 0.03s sys.

**All new C++ decode/operand tests:**

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure -j8 \
  -R 'LegacyBufferFamilies/BufferOperandTest|Cdna3DecodeTest\.(DsRead2st64AccDestinationUsesAccumulatorRegisterClass|MfmaAccCdUsesAccumulatorRegisterClassForCAndD|MfmaAccBitsSelectIndependentMultiplicandBanks|MfmaAccCdPreservesInlineConstantSrc2)|Cdna2DecodeTest\.MemoryAccBitSelectsAccumulatorDestination'
```

Result on the final head: 21/21 passed, 0 failed, 0 skipped, 0 errored. CTest
and `time -p` reported 0.08s real.

**Neighboring execution tests:**

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure -j8 \
  -R 'InstructionExecutionHarness\.(Cdna2|Cdna3|Cdna4)|MfmaExecTest\.(ResolveAccConstant|ResolveAccVgpr|ResolveAccAccVgpr)|MfmaF64Cdna[34]Test|DsTransposeTest\.ReadB64TrB16_AccBit'
```

Result on the final head: 10/10 passed, 0 failed, 0 skipped, 0 errored. CTest
and `time -p` reported 0.07s real. These checks matter because the PR changes
semantic values stored in decoded operands and those values also feed MFMA
execution helpers.

**Race-detector/plugin regression tests:**

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure -j2 \
  -R 'ExecutionPluginTest\.Mfma|RaceDetector\.|RaceTest\.gfx950'
```

Result on the final head: 98/98 passed, 0 failed, 0 skipped, 0 errored. CTest
reported 1.64s total test time; `time -p` reported 1.63s real, 1.35s user,
1.30s sys.

**Diff hygiene:**

```bash
git diff --check origin/develop...HEAD
```

Result: passed with no whitespace errors.

**Pre-commit:**

```bash
time -p .venv/bin/pre-commit run --files $(find emulation/rocjitsu -type f)
```

Result on the final head: passed. Timing: 11.03s real, 107.01s user, 9.22s
sys.

I could not independently regenerate all ISA outputs because the assigned
sparse worktree does not contain the shared MR ISA XML files or the out-of-tree
gfx1250 XML. The committed generated sources compiled successfully, the focused
generator tests passed, and public CI passed release, Clang sanitizer, GCC
sanitizer, focused TSan, pre-commit, CodeQL, and current package-build summary
checks. `therock-pr-bot` was the only current red check.

## Summary

This PR fixes a split between two representations of an AMDGPU instruction:

1. the raw bitfields decoded from the machine instruction; and
2. the semantic `Operand` objects used to describe which physical registers the
   instruction reads and writes.

Rocjitsu often executes an instruction directly from the raw machine fields,
while disassembly and static analyses use the `Operand` objects. Before this PR,
several execution paths interpreted the raw fields correctly, but the operands
still described the unscaled selector, wrong register-bank class, or wrong
register width. That means a kernel could execute correctly in the emulator
while tools inspecting the decoded instruction saw incorrect dependencies.

That description applies directly to the legacy MUBUF/MTBUF fixes and most
memory-instruction `acc` fixes. MFMA A/B bank selection is an important
exception: MFMA execution passes `src0.encoding_value_` and
`src1.encoding_value_` into `src_base()`. Before this PR those operand values
did not include the instruction's `acc[0:1]` bank selectors, so the emulator
could read ordinary VGPRs when the instruction selected AccVGPRs. The PR
therefore fixes runtime numerical behavior for that MFMA case as well as its
decoded metadata.

The important data path is:

```text
MR ISA XML + Python generator
              |
              v
generated Instruction constructors
              |
machine words -> raw MachineInst fields
              |
              +--> execute_impl / address calculation
              |
              +--> semantic Operand objects
                         |
                         +--> disassembly
                         +--> Operand::to_register_ref()
                                      |
                                      v
                                  InstDefUse
                                      |
                                      v
                            liveness / clobber planning /
                            external wait-state checking
```

The PR makes the generated instruction constructors normalize the semantic
operand view so it agrees with execution.

### Legacy MUBUF/MTBUF buffer operands

MUBUF and MTBUF are older buffer-memory instruction formats. Their `srsrc`
field does not directly name one SGPR. It names a four-SGPR buffer resource
descriptor in units of four: raw `srsrc = N` means `s[4N:4N+3]`. Execution
already used `inst.srsrc * 4`; decoded operands previously reported the raw
index. The generator now applies the same multiplication when constructing the
semantic operand.

Their vector address is also conditional. The `idxen` and `offen` bits select
whether the instruction consumes no vector address, one VGPR, or two
consecutive VGPRs:

```text
idxen=0 offen=0 -> no VADDR register
idxen=1 offen=0 -> one VGPR containing the index
idxen=0 offen=1 -> one VGPR containing the offset
idxen=1 offen=1 -> two VGPRs: index and offset
```

The generated `vaddr` operand now has 0, 32, or 64 bits accordingly instead of
being fixed at 64 bits. This prevents def/use analysis from inventing a second
VGPR dependency when only one address component is enabled.

### AccVGPR bank selectors

CDNA GPUs expose accumulator vector registers used heavily by matrix
instructions. Several encodings store an ordinary 8- or 9-bit register number
and use separate `acc` or `acc_cd` bits to choose whether that number refers to
the normal VGPR bank or the accumulator bank.

The generated operand model represents those banks through distinct selector
ranges. This PR folds the sideband bits into the semantic operand value:

- memory instruction `acc` selects the AccVGPR bank for eligible data/result
  operands;
- MFMA `acc[0]` and `acc[1]` independently select the A and B multiplicand
  banks;
- MFMA `acc_cd` selects the accumulator C input and D destination banks.

This changes disassembly from forms such as `v136` to `acc136` where appropriate
and, more importantly, makes `InstDefUse` track `RegClass::ACC_VGPR` instead of
`RegClass::VGPR`.

For memory and DS instructions, execution generally already used raw
`inst_.acc` fields to calculate the physical register offset, so those changes
primarily repair decode metadata. MFMA A/B sources instead use the constructed
operand values in execution; folding `acc[0:1]` into those values also changes
which physical register bank the emulator reads.

### MFMA inline constants

MFMA's third source can be a register or an inline constant. A naive
implementation of `acc_cd` would add the accumulator-bank offset to every
`src2` selector, turning constants such as zero into unrelated register
selectors. The PR guards the conversion so it only remaps values in the encoded
VGPR selector range; inline constants remain constants.

### Why this matters

`InstDefUse` is the bridge from decoded operands to liveness analysis. Incorrect
register classes or widths can lead to false dependency reports, missed
dependencies, or instrumentation/probe planning that believes a live register
is free. The PR therefore primarily fixes decoder metadata and static-analysis
correctness, even though the emulator's raw execution path was already correct
for many of these instructions. It also fixes MFMA numerical execution when A
or B is selected from the accumulator bank.

The runtime race-detector plugin consumes physical execution events rather than
`InstDefUse`: memory destinations come from `VectorMemState::dst_reg_base`, and
register reads are reported from `ComputeUnit::read_vgpr()` /
`ComputeUnit::read_sgpr()`. Consequently, the legacy buffer fixes do not change
the plugin's underlying detection behavior because the runtime address path was
already correct, although race traces now get more accurate disassembly. The
MFMA source-bank fix can affect detection: a pending memory result in an
AccVGPR is now followed by a runtime read of that same physical AccVGPR, so the
plugin can observe a dependency that was previously read from the wrong VGPR
bank.

## Actionable items

No blocking code issues found.

I specifically checked for accidental double application of the `acc` selectors.
MFMA's `dst_base`, `src_base`, and `resolve_acc` helpers accept the normalized
semantic selector ranges, while DS and legacy buffer execution continue to use
the raw `inst_` fields. The final review-feedback commit also gates MFMA A/B
folding on the presence of `acc_cd`, preserving CDNA1's different encoding
shape, and extracts the inline-constant-sensitive `src2` conversion into a
generated helper. The focused execution and race-plugin suites passed.

## Suggestions

### 1. Retitle the PR in the repository's conventional style

**Location:** PR title

The public policy check is red, and the current title uses a bracketed
`[rocjitsu]` prefix rather than the repository's conventional-commit style.
Consider:

```text
fix(rocjitsu): decode buffer and AccVGPR operands
```

### 2. Add a decoded MFMA numerical/plugin consistency regression

**File:** `emulation/rocjitsu/tests/decode_smoke_test.cpp:825`

`MfmaAccBitsSelectIndependentMultiplicandBanks` verifies the decoded
`InstDefUse` register classes, but the same normalized `src0`/`src1` values also
feed MFMA execution. Consider a test that seeds `v84` and `acc84` (and the
corresponding B source) with deliberately different values, decodes an MFMA
whose `acc` bits select one bank, executes it, and checks either the numerical
result or the execution plugin's physical read events. Such a test would tie
the static and runtime interpretations together and would have failed before
this PR.

This is particularly useful for the race-detector plugin: the plugin tracks
runtime physical register reads, not `InstDefUse`, so a consistency test can
prove that the decoded register class and the plugin-observed physical register
refer to the same bank.

### 3. Add one source-side memory AccVGPR regression

**File:** `emulation/rocjitsu/tests/buffer_operand_test.cpp:79`

The generator applies the memory `acc` bit to every
`OPR_VGPR_OR_ACCVGPR` operand, including store data and read-modify-write atomic
operands. The current buffer test exercises an AccVGPR load destination, and the
other decode tests also emphasize destinations. Consider adding a
`buffer_store_dword` or buffer-atomic case asserting that the data source appears
as `RegClass::ACC_VGPR` in `InstDefUse::uses`. This is not evidence of a current
bug; it would directly cover the source side of the shared generator rule.

## Commentary

This PR is a useful example of rocjitsu's generated-ISA architecture. The
thousands of changed C++ lines are mostly generated consequences of a small
policy change in `_generator.py`. Reviewing such a change is more effective when
starting from the generator and tests, then sampling generated constructors and
their execution helpers, rather than reviewing every generated line
individually.

The final review-feedback commit improves this structure: it introduces an
`_OperandCtx` value object, centralizes generation of the buffer VADDR helper,
extracts MFMA `src2` remapping into a generated helper, and adds a direct test
for the zero/one/two-register buffer address-mode mapping. Those changes make
the generator policy easier to audit and reduce repeated generated expressions.

The architectural boundary to remember is that `MachineInst` represents encoded
bits, while `Operand` should represent semantic values. Grouped SGPR selectors,
conditional operand widths, register-bank selector bits, and inline constants
all need normalization at that boundary. Keeping raw fields raw and semantic
operands semantic lets execution, disassembly, liveness, instrumentation, and
external analysis tools agree without duplicating ISA quirks in each consumer.

Numerical tests and decode tests catch different portions of this PR. Numerical
tests would not catch the legacy `srsrc` or VADDR metadata bugs because runtime
execution was already correct. A numerical test with different values in the
VGPR and AccVGPR source banks would catch the MFMA A/B selector bug. Decode and
`InstDefUse` tests remain necessary for errors that affect static analysis but
not emulator output.
