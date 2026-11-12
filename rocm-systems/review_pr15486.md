This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#15486](https://github.com/ROCm/rocm-systems/pull/15486)

Reviewed head: `7c488f66a6ab67276ec27740e215edd4b54ccf8d`, rechecked against GitHub after review. Diff base: `0da24b180d1ddf6c6079b1f916d1d6f279ee8a70`. This is an implementation review of all 13 changed files, incorporating the explicitly requested earlier feedback and companion-test discussion. Particular attention went to preserving register-access plugin hooks, counter participation and ordering, and test/build cost.

Suggestion branch: [`review/pr15486-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr15486-suggestions), based on the reviewed head. The [combined diff](https://github.com/newling/rocm-systems/compare/7c488f66a6ab67276ec27740e215edd4b54ccf8d...2ea1e48937b287ec1a4e386668c4f8c1f13d73f3) contains the two requested coverage fixes and optional wording changes. Register-access API hardening is deferred to a separate follow-up and is not included in this branch.

| Item | Disposition | Commits |
| --- | --- | --- |
| Exercise retained slots for masked ASYNC and FLAT | Requested here | [`7e154de1726`](https://github.com/newling/rocm-systems/commit/7e154de1726b96839a381d334b84f153e752e5f7) |
| Exercise actual STOREcnt overflow | Requested here | [`0518efd1908`](https://github.com/newling/rocm-systems/commit/0518efd19080c971a6db21b17cb465a93602e838) |
| Clarify capacity/completion wording | Optional suggestion | [`2ea1e48937b`](https://github.com/newling/rocm-systems/commit/2ea1e48937b287ec1a4e386668c4f8c1f13d73f3) |

## Tests

The submitted revision built successfully with Clang 23.1.0 in Release mode. The selected race, wait, register-access and buffer suites passed **1,385 tests**, with **107 skips**. The published suggestion head `2ea1e48937b287ec1a4e386668c4f8c1f13d73f3` was rebuilt and passed **1,480 tests**, with **108 skips**, after adding the full `ExecutionPluginTest` suite to the selection. All 63 gfx1250 capacity tests passed. Skips are architecture/qualification conditions in the existing tests, plus one host-SIMD requirement; none is a failed capacity test. The final Release run took 9.954 seconds.

An earlier prototype that also included the deferred register-boundary changes passed **1,480 tests**, with **108 skips**, in an assertion-enabled Clang 23.1.0 build with ASan and UBSan (`-O2 -UNDEBUG`, leak detection enabled and UBSan configured to halt on errors). No sanitizer diagnostic was reported. That configuration disabled the optional Perfsim plugin. This sanitizer result applies to the earlier prototype; the published three-commit branch was revalidated in Release.

The 63 gfx1250 plugin capacity cases took 17 ms on the submitted revision. The changes reuse existing native targets and fixtures; they add no HIP compilation target. The two requested coverage fixes change existing test sequences without adding cases. I found no test-removal or build restructuring justified by these costs. I did not measure a clean-build or application-throughput delta for this Systems PR.

The companion review already ran **218/218 corpus cases** against this exact submitted Systems head: gfx1250 102, gfx942 8, gfx950 79 and gfx1151 29. Those results are reused evidence for the submitted revision, not a fresh corpus run of the suggestion branch. Temporary mutation tests below demonstrate the coverage gaps. All mutations were removed. Changed-file pre-commit hooks and whitespace checks pass. No GPU hardware execution was performed.

## Summary

The capacity implementation reuses the existing partial-wait inference: after admission establishes an upper bound on outstanding tokens, an independently ordered class can retire only its provable oldest prefix. This preserves the distinction between shared capacity and shared completion order. Scalar KMcnt loads remain unordered; ASYNC loads and stores share capacity but retain separate completion classes. gfx1250 FLAT acquires both domains before operand reads and retains empty events for unused domains. Tensor admission occurs before checking its LDS accesses.

The main expectations agree with the public [CDNA5 ISA, revision 27 July 2026](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf), especially §§3.2.2.1, 5.7.1, 10.8 and 10.11.1. The earlier ignored-resource, masked-arrive, ordinary masked-slot, cache-operation, lane-permute, DS_NOP and adjacent-wave fixture concerns are addressed at this head. I found no additional demonstrated defect in the current execution paths. The two requests below address reproducible test gaps. Register-access API hardening belongs in a separate follow-up covering the existing boundary weaknesses; it is not a requested change or blocker for this PR.

## Actionable items

### Make the masked ASYNC and FLAT tests depend on retaining their slot

Locations: [`execution_plugin_race_test.cpp:1242`](https://github.com/ROCm/rocm-systems/blob/7c488f66a6ab67276ec27740e215edd4b54ccf8d/emulation/rocjitsu/tests/execution_plugin_race_test.cpp#L1242), [line 1250](https://github.com/ROCm/rocm-systems/blob/7c488f66a6ab67276ec27740e215edd4b54ccf8d/emulation/rocjitsu/tests/execution_plugin_race_test.cpp#L1250), and [line 1483](https://github.com/ROCm/rocm-systems/blob/7c488f66a6ab67276ec27740e215edd4b54ccf8d/emulation/rocjitsu/tests/execution_plugin_race_test.cpp#L1483).

Both `FlatWithNoActiveLanesAdvances*` tests and `ExecZeroAsyncLoadFillsAsynccnt` put the masked instruction at issue 64. Admission already proves the oldest operation complete, so these cases pass even if the detector then discards the masked instruction's slot. A mutation that removes only those retained slots passes all three submitted tests.

Place the masked instruction at issue 63, then issue an active operation on the same domain at 64. Commit [`7e154de1726`](https://github.com/newling/rocm-systems/commit/7e154de1726b96839a381d334b84f153e752e5f7) makes that change and names the tests for slot retention. All three then reject the mutation through their intended VGPR/LDS race probes, while ordinary masked LOAD/DS controls still pass. The restored detector passes all cases. This is the native counterpart of the companion corpus finding; no extra test cases or total issues are needed. Keep the masked barrier-arrive negative control unchanged because its admission may be skipped.

### Cross the STOREcnt capacity boundary before probing LOADcnt isolation

Location: [`execution_plugin_race_test.cpp:1148`](https://github.com/ROCm/rocm-systems/blob/7c488f66a6ab67276ec27740e215edd4b54ccf8d/emulation/rocjitsu/tests/execution_plugin_race_test.cpp#L1148).

`StorecntPressureDoesNotCompleteALoad` issues 63 stores. The counter reaches capacity, but none of those stores requires backpressure. A mutation that incorrectly drains LOADcnt only when STOREcnt overflows therefore passes this test.

Issue `kCapacity + 1` stores. Commit [`0518efd1908`](https://github.com/newling/rocm-systems/commit/0518efd19080c971a6db21b17cb465a93602e838) adds the missing boundary crossing. With the mutation, the strengthened test fails because the expected load race disappears; with the correct detector, it passes. This costs one synthetic issue and no additional fixture or test.

## Suggestions

- At [`execution_plugin_race_test.cpp:860`](https://github.com/ROCm/rocm-systems/blob/7c488f66a6ab67276ec27740e215edd4b54ccf8d/emulation/rocjitsu/tests/execution_plugin_race_test.cpp#L860) and [`docs/race-detector.md:206`](https://github.com/ROCm/rocm-systems/blob/7c488f66a6ab67276ec27740e215edd4b54ccf8d/emulation/rocjitsu/docs/race-detector.md#L206), distinguish reaching capacity from issuing the next operation, and enough completions from an identifiable oldest completion. Commit [`2ea1e48937b`](https://github.com/newling/rocm-systems/commit/2ea1e48937b287ec1a4e386668c4f8c1f13d73f3) implements the wording changes, including the mixed-ASYNC case.
- Refresh the PR description's companion coverage from 34 additions / 96 gfx1250 cases to 40 / 102, and label its older validation pin clearly. Its “mixed backlog retires nothing” statement should be limited to a single overflow of a mixed 63-token backlog: further issues can eventually establish a completion within one class. No description rewrite or publication was made.

## Follow-up: harden the register-access boundary

The new public [`read_scalar_unobserved()`](https://github.com/ROCm/rocm-systems/blob/7c488f66a6ab67276ec27740e215edd4b54ccf8d/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h#L1571) permits silent scalar reads, but the surrounding API already exposes public `write_scalar_unobserved()`, `OperandExecutionAccess::raw_compute_unit()`, and raw wavefront TTMP access. Read-region access also relies on callers respecting the notified lane mask. Temporary probes confirmed that these existing APIs can obtain or change register values without corresponding notifications; they did not establish misuse by an existing instruction. Address these access restrictions together in a focused follow-up. **No register-access API change is requested for this PR.**

I found no instruction newly skipping its operand hooks through the added helper. In particular, [`mubuf_calculate_addresses():315`](https://github.com/ROCm/rocm-systems/blob/7c488f66a6ab67276ec27740e215edd4b54ccf8d/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/cdna5/addr_calc.cpp#L315) still reads all four descriptor words through `read_scalar_selector()`, including before the ignored-TYPE return. Ordinary address and store-data reads remain observed. The new silent descriptor inspection is legitimate bookkeeping, and memory-result writeback also legitimately accesses storage without reporting a new instruction write. Preserve those distinctions in the follow-up. This audit does not establish that every pre-existing emulator instruction is free of bypasses.

## Scope decisions

NULL tensor descriptors and NOP tiles still count by a documented emulator assumption. The general tensor completion rule does not independently establish their hardware behavior; hardware qualification remains necessary. Messages and returning message results, KMcnt barrier operations, and functional/core-wait FLAT accounting retain the documented limitations. The synthetic ordered KMcnt tests exercise the capacity mechanism without claiming scalar loads are ordered.

A broader counter-domain abstraction, cross-architecture test consolidation, and full LDS barrier-cell synchronization support also remain **follow-up ideas**. No structural redesign is requested here.

## Appendix: reproduce the test gaps

Apply each following mutation independently to the reviewed head. Rebuild `rocjitsu_tests`, run the named tests, then remove the mutation before trying the next one. These changes are deliberately incorrect and are not part of the suggestion branch.

```diff
--- a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp
+++ b/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp
@@ -226,6 +226,8 @@
 void register_unused_flat_domains(WaveRaceState &race, const InstructionSnapshot &instruction,
                                   const amdgpu::MemoryIssueInfo &decoded,
                                   const amdgpu::MemoryIssueInfo &routed, bool is_load) {
+  if (routed.counter_obligations().empty())
+    return; // Probe: omit masked FLAT retained slots after admission.
   for (const auto obligation : decoded.counter_obligations()) {
     const bool used = std::ranges::any_of(routed.counter_obligations(), [&](const auto routed_one) {
       return routed_one.wait_counter_type() == obligation.wait_counter_type();
@@ -566,6 +568,8 @@
   // access whose lanes are all cleared while EXEC is active records none, and
   // neither does an ignored buffer instruction (see ignored_memory_issue()).
   const auto record_exec_zero_slot = [&](bool is_load) {
+    if (inst.mnemonic() == "global_load_async_to_lds_b32")
+      return; // Probe: admit masked async loads, but omit their retained slot.
     if (!exec_zero_memory_issue_counts(wf.cu().arch()) || wf.exec() != 0 ||
         ignored_memory_issue(inst, wf))
       return;
```

```diff
--- a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp
+++ b/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp
@@ -198,4 +198,6 @@
   // finite counter. Once participation is known, admission establishes the
   // same upper bound as an implicit partial wait.
   applyCounterConstraint(type, capacity - increment, /*includeUnordered=*/false);
+  if (type == amdgpu::WaitCounterType::STORECNT)
+    applyCounterConstraint(amdgpu::WaitCounterType::LOADCNT, 0, /*includeUnordered=*/false);
 }
```

For the masked-slot mutation:

```bash
cmake --build "$BUILD_DIR" --target rocjitsu_tests --parallel 8
"$BUILD_DIR/tests/rocjitsu_tests" \
  --gtest_filter='Gfx1250CounterCapacityRaceTest.*NoActiveLanes*:Gfx1250CounterCapacityRaceTest.ExecZeroAsyncLoad*:Gfx1250CounterCapacityRaceTest.ExecZeroLoadHolds*:Gfx1250CounterCapacityRaceTest.ExecZeroDsReadHolds*'
```

The submitted tests pass 5/5. With the strengthened tests, exactly the three masked ASYNC/FLAT cases fail and the two ordinary masked LOAD/DS controls pass.

For the STOREcnt mutation, use `--gtest_filter=Gfx1250CounterCapacityRaceTest.StorecntPressureDoesNotCompleteALoad`. The submitted test passes; the strengthened test fails at its expected-race assertion. Both failures are diagnostic changes, not build/setup failures.

The suggestion branch ends at [`2ea1e48937b`](https://github.com/newling/rocm-systems/commit/2ea1e48937b287ec1a4e386668c4f8c1f13d73f3). Both requested coverage fixes and the optional comment corrections are implemented in the commits mapped above. The PR-description refresh and follow-ups are written suggestions only. Validation is limited to the native builds/tests, mutation checks and previously recorded corpus execution stated above.
