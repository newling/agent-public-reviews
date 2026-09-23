> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#11943](https://github.com/ROCm/rocm-systems/pull/11943)

**Revision reviewed:** `f2d905dc3748deb9e7136c0bda7dd9b1818f55b9`

## Tests

Clang 23 Release builds of `rocjitsu_tests`, `waitcheck_target_test`, and the separate register-observer ABI test succeeded; 138 focused C++ scoreboard, execution, XCNT, wait-model, state, and observer tests passed; 1,144 focused Python generator tests passed with one skip; full ten-ISA regeneration and `git diff --check` were clean. Two temporary regression probes failed as described below. The head merges cleanly with current `develop`. In public CI, pre-commit and TSan pass, but both the GCC UBSan job and TheRock's emulation stage fail while compiling the new test file; Release and ASan/UBSan remain in progress, and the policy check separately fails because the PR description has no issue reference.

## Summary

This adds an optional dynamic memory-wait checker to the core simulator. The checker keeps eager functional writeback unchanged while separately retaining per-wave completion-counter positions, ordered completion classes, register lane/byte footprints, LDS byte ranges, and gfx1250 XCNT replay-source lifetimes. Register accessors consult a compact shadow before entering the detailed checker, explicit and embedded waits retire proven prefixes, and diagnostics report rather than stop execution.

The raw GitHub size makes the change look somewhat larger than the authored design surface:

| Area | Files | Additions | Deletions | Churn |
|---|---:|---:|---:|---:|
| Generated ISA | 150 | 6,020 | 417 | 6,437 |
| Handwritten implementation | 26 | 1,552 | 122 | 1,674 |
| Tests | 15 | 2,428 | 41 | 2,469 |
| Documentation | 3 | 263 | 0 | 263 |
| Total | 194 | 10,263 | 580 | 10,843 |

Thus roughly 59% of the churn and 77% of the files are generated. The substantive production change is still large: about 1,430 net handwritten lines, including a new 656-line scoreboard and about 600 lines of compute-unit/wavefront integration. Conceptually it combines completion accounting, completion-order proofs, fine-grained register observation, same-wave LDS conflict detection, and XCNT replay lifetime tracking. I would call that high state-machine complexity even though the implementation is fairly localized and the 73 newly named tests are unusually thorough.

Several design decisions are worth retaining. Readiness is correctly kept separate from eager data availability; counter membership is kept separate from completion order; lane and byte masks survive into the dynamic check; and observer snapshots and helper-thread execution are deliberately prevented from consuming dependencies. The current revision also responds substantively to the prior discussion by documenting incomplete coverage, adding finite-counter progress and LDS checks, and defaulting the diagnostic off. The implementation should not land unchanged because of the issues below, but none requires abandoning the overall approach.

## Actionable items

### Keep the new tests warning-clean under GCC

**File:** `emulation/rocjitsu/tests/memory_wait_scoreboard_test.cpp:1417-1425`

Both the GCC UBSan job and TheRock's emulation build fail under `-Werror`. GCC 13 reports `-Wdangling-else` for the unbraced outer `if` at line 1417 because `EXPECT_EQ` expands to control flow, and `-Wrange-loop-construct` because the structured binding at line 1425 copies each tuple. Add braces around the first body and bind the tuple as `const auto &`. These are mechanical changes, but the required GCC build cannot reach any tests until they are made.

### Reserve all counter units before a multi-unit producer executes

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_wait_scoreboard.cpp:111-126,323-342`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:1162-1167`

`before()` decides whether the incoming instruction forces progress as though every producer needs one counter slot: it enters the backpressure path only when an ordered class already has `maximum + 1` entries, and `backpressure()` always leaves `capacity - 1` old entries. After execution, however, `track_memory_wait()` records two units for a wide scalar-memory operation and for a returning message. The existing decoded `MemoryCounterObligation::counter_increment()` also records this two-unit contract.

On legacy CDNA, start with 14 ordered DS entries in the 15-entry LGKMCNT domain and admit an `s_load_dwordx2`. The incoming instruction needs two entries, so at least one old DS operation must complete before admission. The current pre-execution check sees only 14 entries and retires nothing; a later read of the oldest DS destination produces a false warning. The temporary decoded-instruction test in the appendix reproduces this on the reviewed head.

Determine each incoming counter increment before operand reads, pass that reservation size into the admission calculation, and leave at most `capacity - incoming_units` entries in a qualifying ordered class. The generated `MemoryIssueInfo` already provides the value for pipeline-backed instructions; the shared event description should carry the same information for inline two-unit producers. Add boundary tests for both wide SMEM and message returns so the pre-execution and post-execution models cannot diverge again.

### Preserve the diagnostic policy when restoring a checkpoint

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.cpp:562-580`; `emulation/rocjitsu/schemas/simulation_config.fbs:10-17`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/checkpoint.cpp:114-121,168-184`

The JSON loader puts `memory_wait_diagnostics=warn` into `ComputeUnitCore::Config`, but neither checkpoint schema nor `serialize_config()` stores it, and `config_from_checkpoint()` consequently reconstructs the default `Off` value. A save/restore therefore silently disables a user-requested diagnostic for every subsequent instruction. This is separate from the documented choice not to serialize already-pending scoreboard entries: even new dependencies created after restore are no longer checked.

Append a backward-compatible field and restore it, using absence to mean `Off`. If compute-unit settings may differ, preserve it per CU as is already done for heterogeneous `functional_quantum`; otherwise validate and document the uniformity requirement. Add a round-trip test like the one in the appendix. If deliberately disabling diagnostics on restore is the intended policy because pending state is dropped, make that transition explicit to the caller rather than silently changing the configuration.

## Suggestions

### Make instruction wait semantics a neutral shared layer

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/CMakeLists.txt:39-45`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_wait_scoreboard.h:6-8`; `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:224-263`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:990-1188`

Reusing wait decoding is the right goal, but the dependency direction is backwards: the VM now imports `code/analysis/waitcheck/target.h` and links an object library named for the offline analyzer. Producer truth is also spread over the generator's prefix-based `MEMORY_WAIT_PRODUCER` flag, `WaitcheckTarget::classify_events()`, existing `MemoryIssueInfo` obligations, and two manual unit-count rules in `track_memory_wait()`. The multi-unit admission defect is one concrete consequence of those parallel representations.

Move the target-independent counter enums, wait decoding, producer classification, completion class, and increment count into a neutral AMDGPU ISA policy module consumed by both Waitcheck and the VM. Prefer making one decoded obligation representation authoritative, extending it for inline producers rather than adding another name-based gate. That would preserve the valuable sharing while making the layer boundary and consistency tests much clearer.

### Keep architectural register consumption explicit

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/wavefront.h:359-436,525-539,1078-1090`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_wait_scoreboard.h:202-269`; `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:11868-11869`

Ordinary-looking `Wavefront` getters and setters now mutate diagnostic state through ambient thread-local scope. Internal inspection consequently has to know when to install `SuspendedMemoryWaitCheck`, and legacy SDWA compare generation needs a second thread-local suppression specifically for temporary VCC writes. The current exceptions are thoughtfully tested, but this is a fragile extension point: a future bookkeeping read inside instruction scope can emit a false warning and erase the pending record, hiding the later architectural consumer.

Longer term, extend `RegisterAccess` to cover explicit EXEC/VCC/SCC/M0/FLAT_SCRATCH semantic reads and writes, and keep raw `Wavefront` state access side-effect-free for logging, snapshots, preservation, and completion. If TLS remains necessary for helper execution, confine it to that bridge rather than making it the meaning of otherwise general accessors.

## Commentary

I would not reject the core placement merely because an execution plugin overlaps this functionality. Correctly checking pre-execution admission, implicit scalar state, routed FLAT lanes, and asynchronously submitted MMA operands needs information at the execution boundary; keeping a lightweight core mechanism can be justified. The callback-shaped scoreboard and default-off policy are also good foundations. The main long-term cost is maintaining another dynamic hazard engine beside the race detector, so the shared event/obligation model matters more than whether the final reporter is called a plugin.

The default-off fast path avoids allocating the detailed scoreboard, but it does not eliminate all disabled-state cost: `MemoryWaitShadow` contributes 1,280 bytes to every materialized wave slot. At the maximum shape of the checked-in four-GPU gfx1250 topology, that is about 80 MiB if all 65,536 slots have been materialized. This is not a blocker at that scale, and the documentation discloses it, but moving the shadow and scoreboard into one optional allocation would make the disabled-by-default contract cleaner if the topology grows.

There is a natural, non-fussy way to split the work:

1. Land a prerequisite that extracts the shared wait policy, carries the producer/obligation metadata, and includes the independent Waitcheck corrections and register-access plumbing. Keep each generator change together with its generated output.
2. Land the basic core completion checker: ordered/unordered counter state, register RAW/WAW detection, waits/backpressure, configuration, and its direct tests.
3. Add LDS byte-range hazards and gfx1250 XCNT replay-source lifetimes as follow-ups. They are independent semantic domains with distinct assumptions and tests; XCNT in particular can stand alone if a third PR is still too broad.

The current three commits do not provide that separation: the first commit contains 192 of the 194 changed files and almost 94% of the additions, while the later commits add the backpressure/LDS extension and change the default. I would prefer the split above for review and bisectability, but I would not insist on separating small generated or test-only pieces merely to reduce the displayed line count.

## Appendix: temporary regression probes

The following test was added temporarily to `memory_wait_scoreboard_test.cpp` (with the CDNA4 builders header included), failed on the reviewed revision, and was removed:

```cpp
TEST_F(MemoryWaitScoreboardTest, WideProducerReservesBothCounterUnitsBeforeReadingOperands) {
  load(5, WaitCounterKind::Ds);
  for (uint32_t i = 1; i < 14; ++i)
    state.issue(WaitCounterKind::Ds);

  auto decoder = Decoder::create(ROCJITSU_CODE_ARCH_CDNA4);
  const auto words =
      cdna4::build_smem(cdna4::kSLoadDwordx2Smem, {.sbase = 0, .sdata = 4, .imm = 1});
  util::StringDiagnostic error;
  auto incoming = decoder->decode_window(words, 0, error.emitter());
  ASSERT_TRUE(incoming.succeeded()) << error.message();
  ASSERT_EQ(incoming.value()->amdgpu_memory_issue_info()
                ->counter_obligations()
                .front()
                .counter_increment(),
            2u);

  state.before(*incoming.value(), ROCJITSU_CODE_ARCH_CDNA4);
  EXPECT_FALSE(shadow.test(5));
}
```

The following test was added temporarily to `config_test.cpp`, failed because the restored value was `Off`, and was removed:

```cpp
TEST(CheckpointTest, RoundTripsMemoryWaitDiagnostics) {
  std::string json = functional_quantum_checkpoint_config(1, 1);
  const auto first_cu_config = json.find(R"({"key":"functional_quantum")");
  ASSERT_NE(first_cu_config, std::string::npos);
  json.insert(first_cu_config,
              R"({"key":"memory_wait_diagnostics","value":"warn"},)");

  auto source = config::load_config_from_string(json, rocjitsu::kEmbeddedSchema);
  auto *source_cu = source.soc()->xcd(0)->shader_engine(0)->compute_unit(0);
  ASSERT_EQ(source_cu->config().memory_wait_diagnostics,
            amdgpu::MemoryWaitDiagnostics::Warn);

  test::ScopedTempFile checkpoint_file("rocjitsu-memory-wait-checkpoint-");
  config::save_checkpoint(checkpoint_file.path(), *source.soc(), 0, source.engine_config,
                          source.cpu_dispatch_threads);

  auto restored = config::restore_checkpoint(checkpoint_file.path());
  auto *restored_cu = restored.soc()->xcd(0)->shader_engine(0)->compute_unit(0);
  EXPECT_EQ(restored_cu->config().memory_wait_diagnostics,
            amdgpu::MemoryWaitDiagnostics::Warn);
}
```
