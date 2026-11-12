This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#15391](https://github.com/ROCm/rocm-systems/pull/15391)

Reviewed head: `825174324a8f57c2a333fa361b0514aaf3eda11a`. Diff merge base: `296511f76c8281c6adcfd1c35ef5682cac62c591`; target branch at review time: `903cda0155fde050c1c40cdfb007a4e4753faa68`. Independent review of all 13 changed files and the affected generation, memory-observation, event-registration, wait and barrier paths. No existing PR reviews or discussion were consulted for this review. Earlier companion-corpus investigation informed the scope.

Suggestion branch: [review/pr15391-suggestions](https://github.com/newling/rocm-systems/tree/review/pr15391-suggestions), based directly on the reviewed head. [The complete suggestion diff](https://github.com/newling/rocm-systems/compare/825174324a8f57c2a333fa361b0514aaf3eda11a...b65a4eb4ac4a3035c1e8ee1db7dbbb521ce3cefa) contains three commits: [1fa7cbbb4c02](https://github.com/newling/rocm-systems/commit/1fa7cbbb4c02b911542625ee1a261bbbaf4feecd) implements actionable item 1; [8d6ecd645464](https://github.com/newling/rocm-systems/commit/8d6ecd645464e48d5c0fec44f14b33d5aedd778e) implements actionable item 2; [b65a4eb4ac4a](https://github.com/newling/rocm-systems/commit/b65a4eb4ac4a3035c1e8ee1db7dbbb521ce3cefa) implements the optional test cleanup. The PR head and target revision were confirmed unchanged before publication on 2026-11-12.

## Tests

Clang 23.1.0 Release builds of the native tests, race plugin, executable and shared library succeeded. The submitted head and first suggestion commit (`1fa7cbbb4c02`) each passed 1,430 selected native tests, with nine skips and no failures. These covered race detection, waits, register access, gfx1250 execution/simulation, instruction metadata, plugin execution and routed memory observations. No newly added async-copy test skipped. After the second-pass test edits, the final suggestion branch passed all 76 selected event-registry and tensor/async plugin tests, with no skips. Both coverage requests were verified by targeted mutations, described below; production mutations were fully restored.

The generator profile suite passed 938 tests with three skips. Regenerating CDNA5 from the matching XML, gfx1251 delta and variants manifest, then formatting with clang-format 18.1.4, reproduced the changed `generated/cdna5/vglobal_exec.cpp` exactly. This was a comparison of that generated file, not a full regeneration check across every architecture.

A temporary decoded-instruction probe passed 48 configurations: global async loads, cluster async loads and global async stores at all four widths, each with SGPR-base and full VGPR-address modes, and with EXEC zero or lanes 0 and 2 active. Required address-register reads remained observable to plugins, with the expected wave, lane and byte masks, and no spurious register-write callbacks.

Fresh companion HIP corpus execution against the first suggestion build (`1fa7cbbb4c02`) passed 211/211 cases: gfx1250 103, gfx950 79 and gfx1151 29. Corpus revision: `ef908e7e2497070d8977082ae256f45250032603`, the final head of [rocjitsu-test-corpus#89](https://github.com/ROCm/rocjitsu-test-corpus/pull/89). Production code is unchanged by the later suggestions. Changed-file pre-commit hooks and whitespace checks passed, including after the second-pass edits. No GPU hardware or sanitizer run was performed for this review.

## Summary

The implementation records the actual LDS source bytes of async stores and carries them into race detection as pending reads. The address helper handles the signed immediate with 32-bit wrapping before checking the allocation, and records the valid byte prefix. The plugin registers all active lanes together as one instruction event, including an empty event when the instruction accesses no LDS bytes. It also counts EXEC-zero async copies in both directions. This keeps byte-level hazards separate from counter accounting.

The completion model also preserves the distinction between ASYNC_LOAD and ASYNC_STORE within the ASYNCcnt counter domain. Completion in issue order within a class does not establish LDS access order between instructions, so the separate unordered access checks matter. I found no demonstrated implementation correctness defect or new register-hook bypass. The concrete requests below strengthen coverage of one-event-per-instruction accounting and empty-event cleanup.

## Actionable items

### 1. Use a multi-lane store in the one-slot accounting test

Location: [`emulation/rocjitsu/tests/execution_plugin_race_test.cpp:1000`](https://github.com/ROCm/rocm-systems/blob/825174324a8f57c2a333fa361b0514aaf3eda11a/emulation/rocjitsu/tests/execution_plugin_race_test.cpp#L1000), `TensorDmaRaceTest.AsyncStoreTakesOneAsynccntSlot`.

All three stores in this test currently have one active lane. Consequently, it cannot distinguish one ASYNCcnt event per instruction from one event per lane. This is a test-coverage gap; the submitted implementation correctly registers one event per instruction.

Make the middle store use two distinct LDS source ranges through the existing `async_store_lanes` helper. After three stores and `wait_asynccnt(0, 2)`, the first store's source is safe to overwrite, while both lanes of the middle store remain potentially pending. The existing assertion at byte 64 then checks the intended distinction:

```cpp
async_store(0, 0);
const std::array<uint32_t, 2> lanes{64, 80};
async_store_lanes(0, lanes);
async_store(0, 128);
wait_asynccnt(0, 2);
EXPECT_FALSE(ds_write(0, 0));
EXPECT_TRUE(ds_write(0, 64));
```

I temporarily changed registration to create one event per lane/range, while retaining one event for an empty instruction. All 71 tests in the selected tensor/async plugin suite still passed. With the strengthened test, the mutation fails at `EXPECT_TRUE(ds_write(0, 64))`: it counts four events, so waiting for at most two incorrectly retires both the first store and the middle store's first lane. The correct implementation passes the strengthened test. The exact mutation and test change are included below.

Implemented in commit [1fa7cbbb4c02](https://github.com/newling/rocm-systems/commit/1fa7cbbb4c02b911542625ee1a261bbbaf4feecd). This reuses the existing helper and assertions and adds no test case, fixture or build target.

### 2. Use two waves in the empty-LDS-event cleanup test

Location: [`emulation/rocjitsu/tests/race-detector/race_detector_event_registry_test.cpp:59`](https://github.com/ROCm/rocm-systems/blob/825174324a8f57c2a333fa361b0514aaf3eda11a/emulation/rocjitsu/tests/race-detector/race_detector_event_registry_test.cpp#L59), `RaceDetector.EventRegistry_LdsEventsWithoutBytesAreTrimmedOnceComplete`.

The new test constructs a one-wave workgroup. In that configuration, `WaveRaceState::satisfyOldestCounterObligations` retires completed LDS events immediately even if the registry does not recognize an empty event as trimmable. This alternate path lets the test pass when the empty-event cleanup rule is broken.

Change `nWaves` from 1 to 2. The existing assertions then verify that completed events without LDS bytes can be trimmed without being held for a workgroup barrier. This uses the same test body and adds no cases or build targets.

For a discriminating check, I removed only `|| e.ldsIntervals.empty()` from `EventRegistry::isEntryTrimmable`. The submitted one-wave test still passed. With two waves, it failed because the trimmed count remained zero and the barrier-pending list was nonempty. Restoring the correct production rule made all five event-registry tests pass, including the strengthened case. The final combined selection of 76 tests also passed. The exact temporary mutation is retained in the appendix.

Implemented in commit [8d6ecd645464](https://github.com/newling/rocm-systems/commit/8d6ecd645464e48d5c0fec44f14b33d5aedd778e). The cleanup implementation already exists in the base and is correct; this request strengthens the new test that covers its use by async stores.

## Suggestions

### Clarify the new test's ordering premise and include its dependency

Location: [`emulation/rocjitsu/tests/execution_plugin_race_test.cpp:914`](https://github.com/ROCm/rocm-systems/blob/825174324a8f57c2a333fa361b0514aaf3eda11a/emulation/rocjitsu/tests/execution_plugin_race_test.cpp#L914), and the new `async_store_lanes` helper at line 626.

The comment above `SameWaveDsWriteOverAPendingAsyncStoreSourceRaces` describes DS/async access reordering as hardware behavior. Match the implementation's more precise explanation: the ISA does not establish that ordering, so the detector conservatively reports an overlapping write until an ASYNCcnt wait completes the store. Also include `<optional>` directly for the new helper's `std::optional` and `std::nullopt` uses, which currently rely on the fixture header. No build failure was observed; these are optional clarity and dependency cleanups.

Implemented in commit [b65a4eb4ac4a](https://github.com/newling/rocm-systems/commit/b65a4eb4ac4a3035c1e8ee1db7dbbb521ce3cefa).

## Scope decisions

The public [CDNA5 ISA](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf), revision 27 July 2026, §§3.2.2.1, 3.3.3 and 10.7–10.8.1, supports the relevant EXEC-zero and completion-accounting rules. It does not establish all LDS access ordering relative to DS instructions and tensor DMA. The PR explicitly documents its conservative treatment of these interactions; a compiler-generated DS-write → async-store sequence can therefore be reported without proving a hardware race. The alignment and out-of-allocation behavior are likewise documented emulator modeling choices.

The detector still does not check global-memory hazards or synchronize waves through LDS barrier cells. Those are separate capabilities; adding LDS source tracking does not claim to implement them. Counter backpressure is handled separately in [#15486](https://github.com/ROCm/rocm-systems/pull/15486). Broader register-boundary hardening, counter-domain abstractions and cross-architecture test consolidation remain follow-up work, not requests for this PR. The register-hook checks here concern the changed instruction paths.

The selected 71 tensor/async plugin cases took 13 ms on the submitted code and 15 ms with the first suggestion, within the broader native runs. The final 76-case selection, including event-registry tests, took 22 ms. These are single-run observations, not a performance comparison. There is no measured reason here to reduce coverage or split build targets, and the suggestions add no translation unit or test invocation. Compilation speed was not benchmarked.

## Follow-up work

The following work is separate from the requested test improvements. It concerns existing coverage limits or unresolved hardware ordering; none of it is a request to expand this PR, and none is implemented on the suggestion branch.

### Track VMEM source reuse by RDNA direct LDS loads

On RDNA3, RDNA3.5 and RDNA4, a direct LDS load can overwrite a VGPR before an earlier VMEM instruction reads it. For example, a global store using `v4` followed by a direct LDS load into `v4` needs the source-read ordering prescribed by the ISA. Section 12.2.1.2 of the [RDNA3](https://docs.amd.com/api/khub/documents/UkT_UPQL21KfKAMUBFnZTw/content), [RDNA3.5](https://gpuopen.com/download/rdna35_instruction_set_architecture.pdf) and [RDNA4](https://docs.amd.com/api/khub/documents/uQpkEvk3pv~kfAb2x~j4uw/content) manuals describes this hazard. An intervening independent VALU or export establishes the VMEM source read; RDNA4 also provides `wait_vm_vsrc=0`. Ordinary ALU overwrites have a hardware interlock, so a model must preserve their safe behavior.

At the reviewed revision, all three architectures execute direct loads through [`shared/lds_direct.h`](https://github.com/ROCm/rocm-systems/blob/825174324a8f57c2a333fa361b0514aaf3eda11a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/lds_direct.h), while ordinary stores retain no pending source VGPRs in the race plugin. The direct-load path does not model this source lifetime or RDNA4's source-read wait field. A focused follow-up should add paired unsynchronized and synchronized direct-load cases, then implement the missing source-read tracking. This is a gap established from the source and ISA; no new hardware or runtime reproduction was performed for this follow-up discussion.

Begin with direct loads, which have functional execution support. Parameter loads have the same ISA hazard rules but remain functional no-ops at this revision: RDNA3/3.5 use an empty shared helper, and RDNA4 has an explicit no-op implementation. Their execution support is a separate prerequisite, not merely another instance of the detector fix.

### Assess the older CDNA wide-store source-reuse delays

The CDNA1–4 manuals' §4.5 tables prescribe short software-inserted delays before overwriting the source VGPRs of certain wide stores. For example, the [CDNA4 table](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna4-instruction-set-architecture.pdf#page=28) lists one wait state for specified VGPR overwrites and two for VALU overwrites, with exceptions for some buffer addressing modes. The detector does not model these instruction-spacing hazards. A separate investigation should select the exact affected instruction pairs and determine an appropriate diagnostic model; retaining every ordinary store's sources until memory completion would incorrectly reject hardware-supported reuse.

### Establish the gfx950 DS-read to DTL access-order guarantee

For an LDS read followed by a direct-to-LDS write to the same bytes, the required ordering is that the read consumes the old bytes before the write overwrites them. The global fetch need not necessarily wait for full DS completion. A preceding `s_waitcnt lgkmcnt(0)` is sufficient, but the CDNA4 manual sections examined do not establish that instruction issue order alone guarantees the required LDS access order.

The merge base already implements, tests and documents a conservative policy: report the overlap while the DS read remains pending. This PR does not introduce that check. A hardware/specification follow-up could establish whether the existing policy can be relaxed on gfx950. Passing hardware stress tests alone would not establish a guarantee. Until stronger evidence exists, retain the documented distinction between a conservative diagnostic and a demonstrated hardware race.

## Appendix: reproduce the counter-slot coverage gap

Use a disposable checkout of the reviewed head and a configured native test build. Save the following as `$MUTATION_PATCH` and apply it with `git -C "$SRC_DIR" apply "$MUTATION_PATCH"`:

```diff
--- a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp
+++ b/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp
@@ -637,8 +637,15 @@
         return;
       // One event per instruction, so the store takes one ASYNCcnt slot, also
       // when no lane reads LDS.
-      rs->registerLdsRangeEvent(instruction, MemoryEventType::LDS_TO_GLOBAL, ranges, obligations,
-                                memoryOrder);
+      if (ranges.empty()) {
+        rs->registerLdsRangeEvent(instruction, MemoryEventType::LDS_TO_GLOBAL, {}, obligations,
+                                 memoryOrder);
+      } else {
+        for (const auto &range : ranges)
+          rs->registerLdsRangeEvent(instruction, MemoryEventType::LDS_TO_GLOBAL,
+                                   std::span<const LdsByteRange>(&range, 1), obligations,
+                                   memoryOrder);
+      }
     } else if (d.is_load) {
       auto destinations = validated_load_destinations(d, wf);
       if (!destinations)
```

The submitted suite still passes with this deliberately incorrect implementation:

```bash
cmake --build "$BUILD_DIR" --target rocjitsu_tests --parallel 8
"$BUILD_DIR/tests/rocjitsu_tests" \
  --gtest_filter='TensorDmaRaceTest.*:*AsyncStoreOtherCounterWaitTest*'
```

Save the following as `$TEST_PATCH` and apply it with `git -C "$SRC_DIR" apply "$TEST_PATCH"`:

```diff
--- a/emulation/rocjitsu/tests/execution_plugin_race_test.cpp
+++ b/emulation/rocjitsu/tests/execution_plugin_race_test.cpp
@@ -997,10 +997,11 @@ TEST_F(TensorDmaRaceTest, AsyncPartialWaitRetiresTheOlderLoadButNotTheStore) {
 }
 
 // Each store is one ASYNCcnt entry: of three stores, waiting for all but two
-// completes only the first.
+// completes only the first, even when the middle store has multiple lanes.
 TEST_F(TensorDmaRaceTest, AsyncStoreTakesOneAsynccntSlot) {
   async_store(0, 0);
-  async_store(0, 64);
+  const std::array<uint32_t, 2> lanes{64, 80};
+  async_store_lanes(0, lanes);
   async_store(0, 128);
   wait_asynccnt(0, 2);
   EXPECT_FALSE(ds_write(0, 0));
```

Rebuild and run the focused test; it now fails at the byte-64 race assertion:

```bash
cmake --build "$BUILD_DIR" --target rocjitsu_tests --parallel 8
"$BUILD_DIR/tests/rocjitsu_tests" \
  --gtest_filter=TensorDmaRaceTest.AsyncStoreTakesOneAsynccntSlot
```

Reverse only `$MUTATION_PATCH`, rebuild, and rerun the focused test to confirm that the strengthened test passes with the submitted implementation. The review's temporary mutation was fully restored; the local suggestion branch contains only test changes.


## Appendix: reproduce the empty-event cleanup coverage gap

In a disposable checkout of the reviewed head, save this as `$EMPTY_MUTATION_PATCH`:

```diff
--- a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/event_registry.h
+++ b/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/event_registry.h
@@ -203,7 +203,7 @@
     if (e.status == EventStatus::RETIRED)
       return true;
     return e.status == EventStatus::WAVE_COMPLETE &&
-           (isWaveLocal(e.type) || e.ldsIntervals.empty());
+           isWaveLocal(e.type);
   }
 
   void tryTrimEvents() {
```

Save this test change as `$TWO_WAVE_TEST_PATCH`:

```diff
--- a/emulation/rocjitsu/tests/race-detector/race_detector_event_registry_test.cpp
+++ b/emulation/rocjitsu/tests/race-detector/race_detector_event_registry_test.cpp
@@ -63,7 +63,7 @@
   // like a wave-local event, and must not be queued for barrier retirement.
   int N = EventRegistry::kTrimAttemptInterval;
   RaceDetector detector(/*nWaves=*/
-                        1, /*vgprCount=*/2, /*sgprCount=*/2, Dim3d(0), [](RaceViolation) {},
+                        2, /*vgprCount=*/2, /*sgprCount=*/2, Dim3d(0), [](RaceViolation) {},
                         counterCapacitiesForArch(ROCJITSU_CODE_ARCH_CDNA5),
                         /*ldsSizeBytes=*/64 * 1024);
   auto &wave = detector.getWaveRaceState(0);
```

Apply only the production mutation, rebuild, and run the original test; it passes:

```bash
git -C "$SRC_DIR" apply "$EMPTY_MUTATION_PATCH"
cmake --build "$BUILD_DIR" --target rocjitsu_tests --parallel 8
"$BUILD_DIR/tests/rocjitsu_tests" \
  --gtest_filter=RaceDetector.EventRegistry_LdsEventsWithoutBytesAreTrimmedOnceComplete
```

Apply `$TWO_WAVE_TEST_PATCH`, rebuild, and rerun the same command. It fails on both `trimmedCount() > 0` and `getBarrierPendingEvents().empty()`. Reverse only the production mutation, rebuild, and rerun; the strengthened test passes:

```bash
git -C "$SRC_DIR" apply -R "$EMPTY_MUTATION_PATCH"
cmake --build "$BUILD_DIR" --target rocjitsu_tests --parallel 8
"$BUILD_DIR/tests/rocjitsu_tests" \
  --gtest_filter=RaceDetector.EventRegistry_LdsEventsWithoutBytesAreTrimmedOnceComplete
```

Both temporary production mutations were restored. No event-registry implementation change is proposed.
