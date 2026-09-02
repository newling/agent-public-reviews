This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#10346](https://github.com/ROCm/rocm-systems/pull/10346)

**Revision reviewed:** published head `c2e885bfd50a`, one commit based on
merge-base `a659172a31d4`. The current `develop` head observed during review was
`dfd3f592c67a`.

**Public/repository status:** the repository, PR, base branch, head repository,
and head branch are public. The PR is open, non-draft, and GitHub reports it as
mergeable, although required checks and review still block merging.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: all 632 required steps passed in 175.01s real, 1283.89s user, and
66.43s sys. After removing the temporary review probe, the final incremental
build of the exact published source passed in 5.26s real, 5.57s user, and
0.83s sys.

**Submitted barrier and raw LDS-barrier coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Gfx1250SimulationTest.*Barrier*:Gfx1250ExecutionTest.*Barrier*'
```

Result: 19/19 passed, 0 failed, 0 skipped, and 0 errored in 1.42s real.
This selection covers named, workgroup, trap, and cluster barrier transitions,
early termination, descriptor allocation, plugin synchronization spans, and
the raw LDS barrier-cell changes consumed by tensor DMA.

**Focused generator tests:**

```bash
time -p env MRISA_PATH=$MRISA_XML_DIR \
  .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_sema_derive.py
```

Result: 713 passed, 0 failed, 2 skipped, and 0 errored in 12.19s real.

An initial invocation incorrectly set `MRISA_PATH` to the single gfx1250 XML
file instead of the directory containing the ordinary ISA XML set. It produced
17 `NotADirectoryError` failures before reaching the affected generator paths.
The command above corrects that review-environment error; none of those initial
failures were caused by the PR.

**All-ISA regeneration:**

```bash
time -p env ALLOW_DIRTY=1 BUILD_JOBS=8 FORMAT_JOBS=8 \
  $ISA_GENERATION_WRAPPER --repo $SRC_DIR --skip-build
```

All-ten-ISA generation and formatting completed in 60.17s real and was
content-idempotent. It left no tracked source changes.

**Formatting and diff hygiene:**

```bash
time -p bash -lc \
  'git diff --name-only $MERGE_BASE..HEAD -z |
   xargs -0 .venv/bin/pre-commit run --files'
git diff --check $MERGE_BASE..HEAD
```

Every applicable hook passed in 6.16s real, and `git diff --check` passed.
The reviewed checkout has no tracked modifications.

**Temporary immediate-init counterexample:**

I added Appendix A's test, rebuilt, ran only that test, and removed it:

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8

time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Gfx1250SimulationTest.ReviewProbeNamedBarrierInitImmediateUsesImplicitM0MemberCount'
```

The incremental build passed in 5.51s real. The probe produced 0/1 passes in
0.21s real:

```text
wf0->barrier_state(1): 0x01000001
expected:              0x01000021
```

This is a genuine instruction-model failure. The immediate barrier ID is
decoded correctly, but the separate implicit M0 member-count input is ignored.

**Published-head CI context:**

The release, Clang ASan/UBSan, TSan, formatting, CodeQL, HIP NVIDIA summary,
and latest multi-architecture summary checks had passed when observed.
GCC ASan/UBSan and current TheRock package builds were still running.
The repository policy check failed because the PR description has no
recognized issue or ticket reference.

## Summary

This PR replaces the old gfx1250 approximation in which
`s_barrier_signal` was inert and `s_barrier_wait` reused the whole-workgroup
`s_barrier` rendezvous. It introduces persistent split-barrier state at the
right ownership levels:

- per-workgroup named, user, and trap counters in the compute unit;
- per-wave joined-barrier and completion state;
- per-cluster workgroup arrival state in the command processor;
- descriptor-driven named-barrier allocation;
- barrier-domain plugin callbacks that include every synchronized live wave;
  and
- CDNA5-specific generated execution while retaining the RDNA4 behavior.

The overall decomposition is sensible. In particular, workgroup barriers count
waves, cluster barriers count one arrival per workgroup, trap domains are
separate and privilege-gated, cluster callbacks are made outside the internal
state lock, and the descriptor field is converted from allocation blocks to
the architectural named-barrier range.

The PR also revises the raw LDS tensor-barrier layout introduced in #7361 from
the earlier 16-bit pending/phase interpretation to the CDNA5 WIDTH=29 form.
The submitted tensor-DMA and raw-cell tests pass, and all-ISA regeneration is
idempotent.

Two named-barrier contracts are incorrect, however:

1. `s_barrier_init` has two independent inputs. SSRC0 chooses the barrier
   object, while implicit M0 supplies the member count. The generated execution
   reads the count only when SSRC0 itself names M0, so the legal immediate-ID
   form initializes a zero-member barrier.
2. Wave termination automatically drops workgroup and cluster barriers, but
   does not drop a joined named barrier. The implementation decrements named
   membership on every joined wave halt, allowing a barrier to complete without
   the required `s_barrier_leave`.

Both affect the state machine that this PR is introducing, and the second is
currently asserted as desired behavior by a submitted test. I would not land
the current head until both are corrected.

## Actionable items

### 1. Read `s_barrier_init`'s member count from its implicit M0 operand

**Files:**

- `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:4884-4920`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/generated/cdna5/sop1_exec.cpp:355-361`
- `emulation/rocjitsu/tests/cdna5_instruction_test.cpp:275-355`

The generated `scalar_barrier_init` body derives both `barrier_id` and
`member_count` from `src_ops[0]`. It only extracts bits `[22:16]` when that
explicit operand is M0.

CDNA5 models `s_barrier_init` with an explicit SSRC0 barrier-ID operand and a
separate implicit M0 operand. LLVM likewise represents the immediate form as
`S_BARRIER_INIT_IMM <id>, implicit $m0`. Therefore:

```text
m0 = 2 << 16
s_barrier_init 1
```

must initialize named barrier 1 with two members. Appendix A demonstrates that
the current generated code instead leaves the member count at zero.

Special-case `scalar_barrier_init` in the generator:

- continue deriving the barrier ID from `src_ops[0]`;
- always read the member count from the instruction's implicit M0 source
  (`src_ops[1]`), regardless of whether SSRC0 is immediate or M0; and
- regenerate the checked-in CDNA5 execution source.

Add direct execution coverage for both `s_barrier_init 1` and
`s_barrier_init m0`. The immediate test should initialize, join, signal, and
read state so it proves that the member count participates in completion, not
only that one packed state value changed.

### 2. Do not implicitly drop a named barrier when a wave terminates

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/wavefront.cpp:45-59`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:422-441`
- `emulation/rocjitsu/tests/cdna5_instruction_test.cpp:396-415`

`Wavefront::halt()` preserves `named_barrier_id_` across reset and passes it to
`release_wf()`. `release_wf()` then decrements that named barrier's member
count and resolves it when the reduced count meets the existing signal count.

The GFX12 barrier execution contract distinguishes automatic barriers from
named barriers:

- ending a wave automatically drops the workgroup barriers;
- ending a clustered workgroup reduces the cluster barrier domain; but
- ending a wave does not implicitly drop a named barrier that it joined.

Named membership changes through `s_barrier_leave` (or an explicit
reinitialization/update), not through `s_endpgm`.

Remove the named-barrier decrement from the halt/release path. Keep the
workgroup and trap counter retirement, and keep command-processor cluster
retirement when an entire workgroup terminates.

Replace `NamedBarrierCompletesAfterJoinedWaveTerminates` with a regression that
initializes two members, records one signal, halts the other joined wave, and
then verifies:

```text
member count = 2
signal count = 1
waiting wave remains blocked
```

That test should avoid driving the intentionally incomplete barrier to a
full-dispatch hang; direct state and wave-state assertions are sufficient.

## Suggestions

### 1. Separate generated output into the top commit

**Files:**

- hand-maintained generator/runtime changes under
  `emulation/rocjitsu/lib/python/amdisa/` and
  `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/`
- generated output under
  `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/generated/`

The published branch is one commit that mixes hand-maintained generator,
runtime, schema-facing, and test changes with generated CDNA5/RDNA4 output.
Restack it as hand-maintained commits followed by one generated-only top
commit. That will also make the required regeneration after Actionable item 1
easy to audit.

## Commentary

### Related rocJITsu work

- **#8026 (merged)** introduced the previous stopgap: split-barrier wait parked
  a wave in the ordinary workgroup barrier state while signal remained a
  no-op. PR 10346 is the intended replacement with independent phase state.
- **#7361 (merged)** introduced raw LDS barrier-cell completion for gfx1250
  tensor DMA. PR 10346 changes that cell's bit layout, so it is a behavioral
  continuation of that work rather than an unrelated cleanup.
- **#10345 (open)** models gfx1250 wave ABI state and overlaps
  `command_processor.*`, `dispatch_entry.h`, and `wavefront.h`. A synthetic
  merge of the two published heads completed without conflicts. They are
  natural companion changes, but whichever lands second should rerun the
  dispatch/barrier tests because both alter wave launch and persistent state.
- **#6962 (open)** adds parallel functional CU dispatch and conflicts in
  `command_processor.*` and `compute_unit.h`. PR 10346 currently resolves a
  cluster barrier by directly calling `complete_barrier()` on peer CUs. The
  #6962 reconciliation must preserve ownership of each worker's wave state,
  likely by delivering completion onto the peer CU's execution context rather
  than allowing one CU worker to mutate another CU's waves directly.
- **#10137 (open)** continues the gfx1250-to-CDNA5 identity migration and
  conflicts broadly with this PR's generator and generated files. If it lands
  first, PR 10346 should be rebased and regenerated rather than resolving the
  generated conflicts manually.
- **#9415 (open)** is the DBT-side barrier-state field splice for gfx1250 A0.
  It consumes the same packed member/signal state concept but is on a separate
  translation stack. Its current head conflicts with this branch's older DBT
  ancestry; it is context for the packed-state contract, not a direct merge
  dependency.

### Remaining modeled surface

The machine-readable ISA marks `s_get_barrier_state` and `s_barrier_leave` as
KMCNT operations, while this functional implementation completes them
synchronously without changing KMCNT. It also leaves `s_wakeup_barrier` as a
true no-op even though that instruction wakes sleeping waves associated with a
named barrier. Neither gap invalidates the submitted signal/wait path, but both
should be recorded as explicit follow-up boundaries before describing the
named-barrier model as complete.

### Repository policy

The PR description needs a recognized GitHub issue or ticket reference before
the repository policy check can pass.

## Appendix A: immediate `s_barrier_init` regression

```cpp
TEST(Gfx1250SimulationTest, ReviewProbeNamedBarrierInitImmediateUsesImplicitM0MemberCount) {
  Gfx1250Sim sim;
  auto *cu = sim.cu();
  auto *wf0 = cu->dispatch_wf(0, 0, kGfx1250ScalarSlots, 32);
  auto *wf1 = cu->dispatch_wf(0, 0, kGfx1250ScalarSlots, 32);
  ASSERT_NE(wf0, nullptr);
  ASSERT_NE(wf1, nullptr);
  cu->begin_workgroup(0, 0, 2, 4);

  auto decoder = Decoder::create(ROCJITSU_CODE_ARCH_GFX1250);
  ASSERT_NE(decoder, nullptr);
  const std::array<uint32_t, 1> init_words = {0xBE805181u}; // s_barrier_init 1
  std::unique_ptr<Instruction> init(decoder->decode(init_words.data()));
  ASSERT_NE(init, nullptr);
  ASSERT_EQ(std::string_view(init->mnemonic()), "s_barrier_init");

  wf0->set_m0(2u << 16);
  cu->execute_instruction(init.get(), *wf0);
  EXPECT_EQ(wf0->barrier_state(1), 0x01000021u);
}
```
