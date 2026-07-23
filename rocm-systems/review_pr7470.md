This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#7470

**Commit reviewed:** `636b11a22c0b` (`fixed exec state tracking
distinguishing between exec_lo vs exec_hi`), the third commit in the current
PR stack.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, not a draft, targets `develop`, and GitHub reports it
as mergeable. All visible current CI checks are passing, neutral, or skipped
as expected, including release, Clang sanitizer, GCC sanitizer, focused TSan,
pre-commit, CodeQL, package builds, and policy checks.

The active development checkout contained unrelated changes, so I exported the
public PR commit into a disposable source snapshot instead of switching that
checkout.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: passed in 133.72s real, 1003.09s user, 49.47s sys.

**Checked-in EXEC, liveness, and partial-destination coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='ExecMaskAnalysis.*:ExecFlagsRealDecode.*:LivenessAnalysis.Exec*:GeneratedInstDefUse.WritelaneReadsDestination*'
```

Result: 18/18 passed, 0 failed, 0 skipped, 0 errored. Timing: 0.02s
real.

**New generator metadata tests:**

```bash
time -p env PYTHONPATH=$SRC_DIR/lib/python $PYTHON -m pytest -q \
  $SRC_DIR/lib/python/amdisa/tests/test_exec_mask_flags.py
```

Result: 21/21 passed, 0 failed, 0 skipped, 0 errored. Pytest reported
0.29s; `time -p` reported 0.47s real.

**Changed shared scalar-resolver assertion:**

```bash
time -p env PYTHONPATH=$SRC_DIR/lib/python $PYTHON -m pytest -q \
  $SRC_DIR/lib/python/amdisa/tests/test_generator_profile_gates.py \
  -k 'ev124_125_arch_gating_in_generated_operand'
```

Result: 1/1 passed, 0 failed, 0 skipped, 0 errored, with 131 tests
deselected. Timing: 0.50s real.

**Diff hygiene:**

```bash
git diff --check <pr-base>..HEAD
```

Result: passed.

**Wave32 active-mask counterexample:**

I temporarily added one test with two cases:

```text
Wave32 Full -> s_mov_b32 exec_hi, 0 -> expected Full
Wave32 Unknown -> s_mov_b64 exec, 0x00000000ffffffff -> expected Full
```

The first write touches no active EXEC bit. The second writes all active Wave32
bits to one even though the inactive high half is zero.

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='ExecMaskAnalysisReviewProbe.*'
```

Result on the submitted code: 0/1 passed in 0.01s real. Both assertions
reported `ExecState::Unknown` instead of `ExecState::Full`.

I then prototyped an extent calculation that positions the destination by
`RegisterRef::index`, intersects it with the active wave mask, preserves writes
with no active overlap, and tests constants only over the source bits that map
to active EXEC. The probe and all 18 checked-in focused tests then passed:
19/19 passed, 0 failed, 0 skipped, 0 errored in 0.02s real. The
temporary test and prototype were confined to the disposable review snapshot.

**Unreadable-kernel-descriptor fallback counterexample:**

I temporarily constructed a valid RDNA code object with two `.kd` symbols. One
descriptor was readable and selected Wave32; the other symbol pointed outside
every section and was therefore unreadable.

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='AmdGpuCodeObjectWaveSizeReviewProbe.*'
```

Result on the submitted code: 0/1 passed in 0.01s real. Despite the API
contract's safe-fallback requirement, `kernel_wavefront_size()` returned 32
rather than 64.

I prototyped returning 64 as soon as any advertised descriptor cannot be read.
With both prototypes applied, the two review probes and all focused checked-in
tests passed: 20/20 passed, 0 failed, 0 skipped, 0 errored in 0.02s
real. The probe and prototype were removed with the disposable snapshot.

I did not run the broad emulation, HIP, or corpus suites locally. The changed
contracts are covered by the focused tests above, and the current public
release and sanitizer corpus jobs are green.

## Summary

The PR makes physical-register liveness less pessimistic around EXEC-masked
vector definitions. Previously, liveness suppressed every VGPR and AccVGPR
kill because an inactive lane can preserve its old destination value. This is
safe, but it keeps values live long before their effective definitions and
reduces the usefulness of liveness-driven scratch allocation.

The PR adds a forward, kernel-scoped `ExecMaskAnalysis` with a two-state
lattice:

```text
Full:
    every active wave lane is definitely enabled

Unknown:
    Full has not been proven
```

Entries begin `Unknown`; a CFG join is `Full` only when every incoming state is
`Full`. A whole-mask copy or pure OR with a compile-time all-ones operand can
establish `Full`. Other EXEC writes conservatively produce `Unknown`, while a
partial all-ones write preserves an already-full mask without establishing it
from `Unknown`.

`LivenessAnalysis` now consumes the EXEC state before each instruction. An
EXEC-masked vector definition kills its old VGPR/AccVGPR value only where EXEC
is proven full. Predicated definitions remain non-kills. The DBT path supplies
the same scoped call and return edges to both analyses, so their graph models
agree.

The supporting generator changes provide the facts needed by the analysis:

- `WRITES_EXEC` and `IGNORES_EXEC` come from the semantic AST.
- `RESULT_COPY` and `RESULT_OR` identify scalar result combinators that can
  prove an all-ones EXEC write.
- `exec`, `exec_lo`, and `exec_hi` operands resolve to `RegisterRef`.
- `Operand::const_value()` exposes inline and literal constants without a
  runtime wavefront.

The PR also moves scalar operand resolution into shared headers, corrects M0
encoding selection, passes actual Wave32/Wave64 information into EXEC analysis,
and models `v_writelane_b32` as reading its destination because it preserves
all but one lane. Most of the 106-file diff is regenerated ISA output from
these generator policies.

The overall decomposition is sound: EXEC state is a reusable forward analysis,
while liveness remains a backward register analysis and asks only whether an
EXEC-masked definition is a complete overwrite. The focused tests cover joins,
loops, call/return edges, Wave32 versus Wave64, constant recognition, and the
lane-partial `v_writelane` case.

## Actionable items

### 1. Classify explicit EXEC writes against the active wave mask

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/analysis/exec_state.cpp:54-140`

`exec_write_extent()` describes `exec_lo` and `exec_hi` as positioned
subregisters, but the returned `mask` is only an unshifted width mask:

```cpp
const uint64_t mask = (w >= 64) ? ~0ULL : ((1ULL << w) - 1ULL);
```

`classify()` then treats every non-all-ones write as `Narrowing`, without first
checking whether the destination overlaps the active Wave32 mask. This produces
two incorrect conservative transitions:

```text
Wave32 Full
  -> s_mov_b32 exec_hi, 0
  -> Unknown
```

`exec_hi` is outside Wave32's active mask, so this write must preserve `Full`
regardless of the value written.

```text
Wave32 Unknown
  -> s_mov_b64 exec, 0x00000000ffffffff
  -> Unknown
```

All active low 32 bits are one, so this write establishes `Full`; the inactive
high bits are irrelevant. The submitted code instead checks the source against
the full 64-bit destination width.

Calculate the written architectural bit positions using `RegisterRef::index`,
intersect that extent with `full_exec_mask(wave_size)`, and classify only the
overlap:

- no active overlap: `Preserve`;
- all active bits covered and written as one: `AllOnes`;
- a proper active subset written as one: `Preserve`;
- any other write to active bits: `Narrowing`.

Keep separate masks for destination positions and corresponding source-value
bits so an `exec_hi` source is tested at source bit zero while its destination
is positioned at architectural bit 32. Add both Wave32 regressions above.

This does not currently create an unsafe kill; it loses valid full-EXEC proofs.
It should nevertheless be fixed before merging because it violates the new
analysis's Wave32 transfer contract and leaves the latest subregister handling
incomplete.

#### Suggested regressions

Add a table-driven or equivalent set of transfer tests to
`tests/analysis/liveness_test.cpp`:

| Initial state | Wave size | Write | Expected state |
|---|---:|---|---|
| `Full` | 32 | `exec_hi = 0` | `Full` |
| `Full` | 32 | `exec_hi = unknown SGPR` | `Full` |
| `Unknown` | 32 | `exec = 0x00000000ffffffff` | `Full` |
| `Full` | 64 | `exec_hi = 0` | `Unknown` |
| `Unknown` | 64 | `exec = 0x00000000ffffffff` | `Unknown` |

The Wave64 contrast cases prevent a fix from treating every `exec_hi` write as
irrelevant. The existing synthetic instruction fixture can add:

```cpp
case TestOpcode::WriteExecHiZero:
  return new TestInstruction(
      "test_write_exec_hi_zero",
      {{RegClass::EXEC, 1, 1}},
      {},
      RESULT_COPY,
      std::nullopt,
      {},
      std::nullopt,
      0ULL);

case TestOpcode::WriteExecWideLowOnes:
  return new TestInstruction(
      "test_write_exec_wide_low_ones",
      {{RegClass::EXEC, 0, 2}},
      {},
      RESULT_COPY,
      std::nullopt,
      {},
      0x00000000ffffffffULL);
```

Exercise the Wave32/Wave64 distinction directly:

```cpp
TEST(ExecMaskAnalysis, ClassifiesWritesAgainstActiveWaveMask) {
  {
    auto blocks = build_test_blocks({
        TestOpcode::WriteExecFull,
        TestOpcode::WriteExecHiZero,
        TestOpcode::DefVgpr0,
        TestOpcode::End,
    });
    auto scope = block_scope(blocks);
    ExecMaskAnalysis exec{KernelBlockScope(scope), 32};
    auto insts = insts_of(*blocks[0]);

    ASSERT_GE(insts.size(), 3u);
    EXPECT_EQ(exec.before(*insts[2]), ExecState::Full);
  }

  {
    auto blocks = build_test_blocks({
        TestOpcode::WriteExecFull,
        TestOpcode::WriteExecHiZero,
        TestOpcode::DefVgpr0,
        TestOpcode::End,
    });
    auto scope = block_scope(blocks);
    ExecMaskAnalysis exec{KernelBlockScope(scope), 64};
    auto insts = insts_of(*blocks[0]);

    ASSERT_GE(insts.size(), 3u);
    EXPECT_EQ(exec.before(*insts[2]), ExecState::Unknown);
  }
}

TEST(ExecMaskAnalysis, Wave32WideWriteOnlyRequiresActiveBitsToBeOne) {
  auto blocks = build_test_blocks({
      TestOpcode::WriteExecWideLowOnes,
      TestOpcode::DefVgpr0,
      TestOpcode::End,
  });
  auto scope = block_scope(blocks);
  auto insts = insts_of(*blocks[0]);
  ASSERT_GE(insts.size(), 2u);

  ExecMaskAnalysis wave32{KernelBlockScope(scope), 32};
  EXPECT_EQ(wave32.before(*insts[1]), ExecState::Full);

  ExecMaskAnalysis wave64{KernelBlockScope(scope), 64};
  EXPECT_EQ(wave64.before(*insts[1]), ExecState::Unknown);
}
```

Also add one liveness integration regression to pin the downstream consequence:

```cpp
TEST(LivenessAnalysis, Wave32ExecHiWriteDoesNotDisableFullExecKill) {
  auto blocks = build_test_blocks({
      TestOpcode::WriteExecFull,
      TestOpcode::WriteExecHiZero,
      TestOpcode::DefVgpr0,
      TestOpcode::UseVgpr0,
      TestOpcode::End,
  });

  auto scope = block_scope(blocks);
  ExecMaskAnalysis exec{KernelBlockScope(scope), 32};
  LivenessAnalysis liveness{KernelBlockScope(scope), exec};
  const Instruction &def = *insts_of(*blocks[0])[2];

  EXPECT_EQ(exec.before(def), ExecState::Full);
  EXPECT_FALSE(liveness.is_live_before(def, {RegClass::VGPR, 0, 1}));
}
```

### 2. Treat every unreadable advertised kernel descriptor as Wave64

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/amdgpu_code_object.cpp:339-368`

**Contract:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/amdgpu_code_object.h:77-82`

`kernel_wavefront_size()` returns 32 when every descriptor it successfully
reads is Wave32:

```cpp
return (saw_kernel && all_wave32) ? 32 : 64;
```

An entry in `kd_offsets_` that does not resolve into any loaded section is
silently skipped. Therefore a code object with one readable Wave32 descriptor
and one unreadable descriptor returns 32. The header describes 64 as the safe
fallback, but the function does not apply that fallback when only some
descriptors are readable.

The instrumentor applies this one result to whole-object EXEC analysis. If the
unreadable descriptor belongs to Wave64 code, analyzing that code as Wave32 can
promote `exec_lo = -1` to `Full` and permit an unsafe full-register kill.

Track whether each `.kd` entry was decoded. Return 64 immediately, or mark
`all_wave32 = false`, when any entry cannot be resolved. Add direct unit
coverage in `tests/code/amdgpu_code_object_test.cpp` for:

- one Wave32 descriptor;
- one Wave64 descriptor;
- mixed Wave32/Wave64 descriptors;
- no descriptors;
- one readable Wave32 descriptor plus one unreadable descriptor.

The temporary mixed-readable/unreadable probe failed on the submitted code and
passed after the per-entry fallback was added.

#### Suggested regressions

Extend the existing code-object fixture in
`tests/code/amdgpu_code_object_test.cpp` so a descriptor can select Wave32:

```cpp
struct KernelSpec {
  std::string name;
  uint32_t granulated;
  bool wave32;
};

KD make_kd(uint32_t granulated, bool wave32) {
  KD desc{};
  AMDHSA_BITS_SET(
      desc.compute_pgm_rsrc1,
      kd::COMPUTE_PGM_RSRC1_GRANULATED_WAVEFRONT_SGPR_COUNT,
      granulated);
  AMDHSA_BITS_SET(
      desc.kernel_code_properties,
      kd::KERNEL_CODE_PROPERTY_ENABLE_WAVEFRONT_SIZE32,
      wave32 ? 1 : 0);
  return desc;
}

std::vector<uint8_t>
make_elf_with_kds(std::initializer_list<KernelSpec> kernels);
```

Cover the complete fallback contract:

```text
CdnaAlwaysReturnsWave64
SingleRdnaWave32ReturnsWave32
SingleRdnaWave64ReturnsWave64
MixedRdnaWaveSizesReturnWave64
NoDescriptorsReturnsWave64
UnreadableDescriptorReturnsWave64
ReadableWave32AndUnreadableDescriptorReturnsWave64
```

The final case is the critical regression. An object containing only an
unreadable descriptor already returns 64 because `saw_kernel` remains false.
The bug requires at least one readable Wave32 descriptor alongside an
unreadable one.

```cpp
TEST(AmdGpuCodeObjectWaveSize,
     ReadableWave32AndUnreadableDescriptorReturnsWave64) {
  auto image = make_elf_with_kds({
      {.name = "wave32", .granulated = 0, .wave32 = true},
      {.name = "unknown", .granulated = 0, .wave32 = false},
  });

  make_kernel_descriptor_symbol_unreadable(image, 1);

  AmdGpuCodeObject obj(image.data(), image.size());
  ASSERT_TRUE(obj.is_valid());
  EXPECT_EQ(obj.kernel_wavefront_size(ROCJITSU_CODE_ARCH_RDNA4), 64);
}
```

The helper should keep the ELF structurally valid while moving the selected
`.kd` symbol outside every loaded section:

```cpp
void make_kernel_descriptor_symbol_unreadable(
    std::vector<uint8_t> &image,
    size_t kernel_index) {
  Elf64_Ehdr ehdr{};
  std::memcpy(&ehdr, image.data(), sizeof(ehdr));

  std::array<Elf64_Shdr, 6> shdrs{};
  std::memcpy(shdrs.data(), image.data() + ehdr.e_shoff, sizeof(shdrs));

  Elf64_Sym symbol{};
  const uint64_t symbol_offset =
      shdrs[4].sh_offset + (kernel_index + 1) * sizeof(Elf64_Sym);
  std::memcpy(&symbol, image.data() + symbol_offset, sizeof(symbol));

  symbol.st_value = 0xdead0000;
  std::memcpy(image.data() + symbol_offset, &symbol, sizeof(symbol));
}
```

The expected policy pinned by these tests is:

```text
all advertised descriptors readable and Wave32 -> 32
anything else                                  -> 64
```

## Suggestions

### 1. Restore direct EXEC operand-access coverage after the shared resolver move

**Files:** `emulation/rocjitsu/lib/python/amdisa/tests/test_profile_properties.py`,
`emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py`

The PR removes `test_operand_exec_register_access_is_wave32_gated` while moving
the generated `exec_lo`, `exec_hi`, and 64-bit EXEC read/write paths into
`shared/scalar_operand_resolve.h`. The replacement profile-gating test checks
the per-architecture M0 constant and shared M0 branch, but not the EXEC
branches.

Add shared-header assertions or, preferably, focused C++ operand tests that
cover:

- `exec_lo` reads and writes the active low half;
- Wave32 `exec_hi` reads and writes raw architectural state without changing
  active EXEC;
- 64-bit EXEC access uses the intended raw-versus-active semantics;
- Wave64 behavior remains unchanged.

This boundary is directly consumed by the new `RegisterRef::index` logic, and
the first actionable item demonstrates why the Wave32 split benefits from
explicit regression coverage.

### 2. Derive result combinators from the semantic AST

**File:** `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:151-171`

`WRITES_EXEC` and `IGNORES_EXEC` are derived by walking the semantic AST, while
`RESULT_COPY` and `RESULT_OR` are inferred from hand-selected
`semantic_class`/`operation` strings. Missing a future class or operation is
conservative, but it silently loses full-EXEC proofs and allows the two
metadata paths to drift.

Consider deriving the combinator from the same semantic block used for EXEC
properties, or centralize the classification in the semantic-property layer.
Keep the current negative tests for vector operations and non-pure OR forms.

### 3. Make graph agreement harder to violate at the API boundary

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/analysis/exec_state.h:32-55`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/analysis/liveness.h:129-140`

The implementation correctly supplies the same block scope and scoped
call/return edges to `ExecMaskAnalysis` and `LivenessAnalysis`, and the tests
show that disagreement can enable an unsafe kill. The API still requires every
caller to construct the two analyses separately and repeat the edge span.

Consider a shared scoped-CFG value object, or a liveness construction helper
that accepts an already-bound EXEC analysis and its graph description. This is
not required for the current callers, but it would turn an important caller
obligation into a structural invariant.

## Commentary

The two-state lattice is a reasonable first implementation for the PR's
immediate consumer: liveness needs only a proof that every active lane is
enabled. Every state other than proven `Full` has the same safe whole-register
kill result.

A richer per-bit EXEC domain could recognize additional `Full` points after
multiple partial writes, while true per-lane VGPR liveness could combine
complementary partial definitions even when EXEC is never full at one
instruction. Those are distinct extensions with different costs and benefits.
They are discussed separately in
[PR 7470: EXEC and liveness granularity](discussion_pr7470_exec_liveness_granularity.md).

I would keep that exploration out of this PR. First fix the active-mask and
descriptor-fallback contracts above, then measure real kernels to determine
whether richer EXEC state or per-lane liveness would materially improve scratch
allocation.
