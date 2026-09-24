> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#11943](https://github.com/ROCm/rocm-systems/pull/11943)

**Revision reviewed:** `c0877515b28bdf310a85b49f3c7ec7b9792f5367`

## Tests

Clang 23 Release builds of the core tests, Waitcheck tests, and normal register-observer ABI test succeeded. Seventy focused MemoryWait/XCNT/observer tests and all 68 Waitcheck target/state tests passed. The full amdisa Python suite passed 2,196 tests with 46 skips; full ten-ISA regeneration and `git diff --check` were clean. All 53 registered gfx950/gfx1151 HIP race-detector cases ran successfully with both diagnostics enabled: the core warned in 20 of 29 plugin-positive cases and in none of the 24 negative/control cases. A second run without the plugin produced the same core-warning set; the plugin-specific test assertions then fail by construction. In particular, the seven LDS-address-positive cases produce no core warning, as expected for the revised scope. Three focused counterexamples reproduce the remaining admission, checkpoint, and duplicate-report issues described below; the two earlier WAW counterexamples now pass.

The GCC 13 UBSan register-observer ABI test fails locally and in the current CI run with an undefined `ComputeUnitCore` typeinfo symbol. The completed substantive CI jobs pass; refreshed Release, Clang ASan/UBSan, and final platform-validation jobs are still running. The policy job separately fails because the PR description has no issue reference.

## Summary

This PR adds an optional dynamic missing-wait diagnostic to the core simulator. rocJITsu still writes memory results eagerly for functional execution, but a per-wave scoreboard separately records when those register results are architecturally ready. Executed reads and overwrites are compared against that state; explicit and embedded waits, ordered completion, finite counter capacity, and gfx1250 XCNT rules retire dependencies.

The latest discussion materially clarifies the design. This is not a same-wave LDS race detector: the fourth commit removes LDS-address tracking, and the documentation now explicitly excludes memory visibility, address overlap, barriers, and communication between lanes or waves. It checks register-result readiness and qualified replay-source lifetimes. The fifth commit updates that narrower model for formatted/packed-D16 buffer results and the separate pointer result of LDS-stack instructions. The sixth and seventh commits preserve unordered and unmapped replay dependencies and make WAW decisions from the actual pair of completion classes; the previous false-positive and false-negative WAW probes now pass.

The current diff against its rebased parent is:

| Area | Files | Additions | Deletions | Churn |
|---|---:|---:|---:|---:|
| Generated ISA | 150 | 6,012 | 417 | 6,429 |
| Handwritten implementation | 30 | 1,467 | 144 | 1,611 |
| Tests | 10 | 2,543 | 22 | 2,565 |
| Documentation | 3 | 266 | 0 | 266 |
| Total | 193 | 10,288 | 583 | 10,871 |

About 59% of the churn and 78% of the files are generated. The authored production change is nevertheless substantial: about 1,323 net handwritten lines, including a 620-line scoreboard and roughly 398 net lines of compute-unit/header integration. The complexity is concentrated in four interacting concerns: counter accounting, completion-order proofs, fine-grained register observation, and XCNT replay lifetimes. Seventy-five newly named C++ tests give the machinery unusually good direct coverage.

The narrower scope makes the design considerably easier to justify. Keeping architectural readiness separate from eager data availability is the right abstraction; lane and byte masks are retained; special scalar state is covered; observer snapshots and helper execution are kept from consuming dependencies; and the default-off policy is appropriate. I would keep the overall approach. The three items in the next section should be resolved in this PR; the later suggestions are suitable follow-up work and should not hold up this change.

## Actionable items for this PR

### Use the incoming producer's actual counter increment during admission

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_wait_scoreboard.cpp:129-143,303-322`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:1098-1103`

`before()` applies finite-counter backpressure as though every incoming producer needs one slot. It enters the admission path only when an ordered class already exceeds the largest encodable wait value, and `backpressure()` always leaves `capacity - 1` old units. After execution, however, `track_memory_wait()` records two units for wide scalar-memory operations and returning messages. The decoded `MemoryCounterObligation::counter_increment()` already expresses the same two-unit rule for pipeline-backed instructions.

On legacy CDNA, put 14 ordered DS units in the 15-unit LGKMCNT domain and then admit `s_load_dwordx2`. The incoming operation needs two units, so one old DS result must complete before the scalar load reads its operands. The current pre-execution check sees only 14 old units, retires nothing, and later diagnoses a false missing wait on the oldest DS result. The first appendix test reproduces this on the reviewed head.

Determine the increment before operand reads and leave at most `capacity - incoming_units` entries in each qualifying ordered class. Prefer carrying this through the same decoded event description used after execution rather than adding another manual mnemonic rule. Add capacity-boundary tests for both wide SMEM and returning messages.

### Keep generic FLAT results pending until both architectural counters retire

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:1036-1052,1112-1118`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/memory_issue.h:72-86`; `emulation/rocjitsu/docs/memory-wait-counter-coverage.md:21-36,52-57`; `emulation/rocjitsu/tests/race-detector/hip_race_gfx950_test.hip:86-168`

The core checker refines a generic FLAT result using the executed route: global lanes remain pending only on VMEM, while shared-aperture lanes remain pending only on LDS. That conflicts with the architectural contract already recorded in [ROCm/rocm-systems#11456](https://github.com/ROCm/rocm-systems/issues/11456): generic FLAT increments both applicable counter domains, its two portions complete independently, and the instruction is not complete until both obligations retire, even when all executed lanes happen to resolve to one memory space. The issue cites the CDNA4 and RDNA4 ISA descriptions and LLVM's independent dual-event model. `MemoryIssueInfo` and the race detector's committed tests encode the same rule.

The observable difference is:

| Case | Core warnings | Plugin warnings |
|---|---:|---:|
| `flat_global_vmcnt_only_race` | 0 | 1 |
| `flat_global_lgkmcnt_only_race` | 1 | 1 |
| `flat_lds_vmcnt_only_race` | 1 | 1 |
| `flat_lds_lgkmcnt_only_race` | 0 | 1 |

These are two false negatives in the core diagnostic under the project's existing contract. Retain one logical result dependency until both counter obligations have been satisfied. If that is represented by two scoreboard entries, share report/recovery state so one access produces one warning. This PR does not need to solve #11456's larger mixed-memory-space functional-execution problem, but it should not weaken the conservative architectural readiness rule while that limitation remains.

### Fix the GCC/UBSan register-observer DSO boundary

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:118`; `emulation/rocjitsu/tests/CMakeLists.txt:1702-1722`; `emulation/rocjitsu/tests/register_observer_probe.cpp:1-16`

The new loadable-observer test passes in the normal Clang build but fails under GCC 13 UBSan before its assertions run:

```text
libregister_observer_probe.so: undefined symbol: _ZTIN8rocjitsu6amdgpu15ComputeUnitCoreE
```

The probe DSO's sanitized inline register-access code references `typeinfo for ComputeUnitCore`, while `librocjitsu.so` contains that typeinfo only as a local symbol. A temporary prototype marking the class declaration `class RJ_API_EXPORT ComputeUnitCore ...` made the test pass, confirming the visibility boundary. Export the required RTTI/class ABI, or move the observer bridge that needs it out of the module and expose a narrower exported entry point. Exporting the entire class is mechanically simple but unnecessarily broadens the shared-library ABI.

The earlier GCC source-warning review comments and the no-`experimental/simd` carry fallback have been addressed; this is the remaining GCC failure on the current head.

## Follow-up suggestions

The items in this section would improve maintainability, coverage, or polish, but I would not require them before this PR lands.

### Give the shared wait policy a neutral owner

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/CMakeLists.txt:39-45`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_wait_scoreboard.h:6-8`; `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:11660-11665`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:919-1121`

The VM now imports and links a component named for the offline Waitcheck analyzer. Producer truth is divided among the generator's `MEMORY_WAIT_PRODUCER` flag, `WaitcheckTarget::classify_events()`, pre-existing `MemoryIssueInfo` obligations, and manual unit-count rules in `track_memory_wait()`. The multi-unit admission bug is a concrete symptom of those parallel representations.

Move target-independent counter decoding, event classification, completion classes, and increment counts into a neutral AMDGPU ISA policy layer consumed by Waitcheck and the VM. The race detector already consumes `MemoryIssueInfo`, so this PR does not yet give it a drop-in replacement for its own state machine; a neutral authoritative policy is the useful reuse boundary.

### Make checkpoint behavior explicit

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/checkpoint.cpp:114-121,168-184`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.cpp:572-578`; `emulation/rocjitsu/schemas/simulation_config.fbs:10-17`

Saving and restoring a VM configured with `memory_wait_diagnostics=warn` reconstructs the setting as `Off`. The documentation says pending dependency state is not serialized, but it does not say the diagnostic itself is silently disabled. A temporary round-trip test confirmed the change in policy.

Either persist the flag and clearly state that only dependencies created after restore are checked, or explicitly document/report that restore disables the diagnostic because pre-checkpoint scoreboard state is unavailable. I would not require serializing the pending scoreboard in this PR.

### Coalesce aliased results before reporting

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:994-1024,1112-1118`; `emulation/rocjitsu/tests/memory_wait_scoreboard_test.cpp:672-712`

The fifth commit correctly tracks the two-VGPR result and independent pointer result of `ds_bvh_stack_push8_pop2_rtn_b64`. If `ADDR` aliases `VDST` or `VDST+1`, however, the same instruction/completion creates overlapping pending records and one later access produces two identical warnings. Extending the new test's pointer cases from `{16, 31}` to `{12, 16, 31}` reproduced a count of two for `pointer=12, register=12`.

Coalescing overlapping destinations from the same issue, or deduplicating reports while retaining the union of lane/byte coverage, would keep one architectural dependency from appearing as two findings.

### Build a shared differential suite from both test corpora

**Files:** `emulation/rocjitsu/tests/memory_wait_scoreboard_test.cpp:500-1574`; `emulation/rocjitsu/tests/race-detector/CMakeLists.txt:19-148`; `emulation/rocjitsu/tests/race-detector/race_test_support.hpp:16-55`; `emulation/rocjitsu/tests/race-detector/hip_race_gfx950_test.hip`; `emulation/rocjitsu/tests/race-detector/hip_race_gfx1151_test.hip`

The existing HIP corpus gives a useful scope map. The core diagnoses all 18 ordinary same-wave register RAW/WAW/counter cases and two of the four generic-FLAT cases. The seven LDS-address cases—one same-wave direct-to-LDS case and six cross-wave cases—are intentionally plugin-only. They also produced no core warning on the earlier LDS-enabled revision: the six cross-wave cases were outside that per-wave model, and the direct-to-LDS case was filtered because the wave's LDS allocation size was unavailable. Removing the LDS shadow therefore did not change the measured 20-of-29 overlap. The core also warns in zero of 24 negative/control cases.

This PR also adds 24 `MemoryWaitExecutionTest` cases whose decoded instruction sequences are useful inputs for the plugin: scalar/vector RAW and WAW, partial waits, counter admission, counter-only operations, routed FLAT, and exact lane/byte footprints. They currently assert the core's diagnostic counter, and some directly manipulate the core scoreboard, so they cannot simply be rerun against the plugin. Separate reusable scenario construction from detector-specific observation, then run applicable scenarios through a core-count adapter and a plugin-finding adapter. The 32 lower-level scoreboard tests should remain implementation tests, while XCNT, TLS/shadow lifecycle, special-register gaps, and LDS-address cases should be capability-tagged rather than forced to agree. Once the FLAT issue above is fixed, both one-counter HIP cases should be common positive cases. Add a real gfx1250 HIP case for XCNT if that path later becomes available in the plugin.

### Keep the enabled-cost claim workload-specific

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/wavefront.h`; `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_wait_scoreboard.cpp`

I could not reproduce an approximately 2% enabled overhead. Using Clang 23 Release builds of the exact rebased parent and reviewed head, LTO disabled, one warm-up, six balanced paired rounds, and one physical core's two SMT CPUs, I measured:

| Workload | Core diagnostic vs PR-off | Race plugin vs PR-off | PR-off vs parent |
|---|---:|---:|---:|
| gfx1250 hipBLASLt f32 128x128x128, 100 iterations | +10.9% [+10.1%, +13.3%] | +42.7% [+40.0%, +45.1%] | +0.1% |
| gfx1250 hipBLASLt f32 256x256x3072 | +14.2% [+13.5%, +15.0%] | +58.8% [+58.1%, +59.7%] | +0.4% |
| gfx950 `stress_wavefront_reuse`, 50 repetitions | +8.6% [+7.7%, +8.6%] | +148.3% [+143.1%, +152.6%] | +0.9% |

Process CPU time corroborated the direction: +11.0%, +14.4%, and +9.1% for the core, versus +42.8%, +58.0%, and +151.4% for the plugin. The two hipBLASLt runs were numerically correct and had no core warnings; the plugin produced two existing findings per process. The stress case was clean under both diagnostics. Default-off showed no material regression.

The core checker is substantially cheaper than the plugin on these workloads, but its enabled cost is not approximately 2% and is not workload-independent. Keeping it off by default is appropriate. The always-present `MemoryWaitShadow` also costs 1,280 bytes per materialized wave slot even while disabled; consider folding it into the optional allocation if large topologies make that footprint material.

## Commentary

After the LDS-address code was removed, I no longer view this as an attempted replacement for the race-detector plugin. The division is coherent: the core catches missing waits at actual register-consumption points, including implicit and awkward scalar state, while the plugin retains address-level LDS/global visibility and cross-wave reasoning. The plugin should not reduce its scope merely because the tools overlap on ordinary register-result hazards.

The instruction-spacing false-positive class raised in the discussion remains, but it is now documented explicitly. With no known kernel intentionally relying on a worst-case latency proof, and with contention making such a proof difficult, I would treat this as a declared limitation rather than a blocker.

XCNT is the only obvious semantic seam in the patch, but I would not ask the author to restack the current work merely to extract it. It shares the scoreboard, shadow, register hooks, configuration, and much of the test setup, so splitting it now would create substantial churn without making the remaining review dramatically smaller. It is a reasonable boundary only if later work naturally needs an independently staged rollout.

## Appendix: temporary regression probes

The following test was added temporarily to `memory_wait_scoreboard_test.cpp` with the CDNA4 builders header, failed on the reviewed revision, and was removed:

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
