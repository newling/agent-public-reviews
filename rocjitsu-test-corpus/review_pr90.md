This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocjitsu-test-corpus#90](https://github.com/ROCm/rocjitsu-test-corpus/pull/90)

Reviewed head: `7d71596dae6e16eafc1d1d7c07b8e7cd38020320`. Diff base: `d2fb14fdd23738b14ac6a340c4c2e94e60fbb43b`.

Deep review of all four changed files and all 40 added cases, including existing reviews and responses, correctness, build/test cost, nearby reuse, and shared-header consumers. Relevant paths in companion [ROCm/rocm-systems#15486](https://github.com/ROCm/rocm-systems/pull/15486) were inspected and exercised at `7c488f66a6ab67276ec27740e215edd4b54ccf8d`; this is not a separate full review of that implementation PR.

Suggestion branch: [review/pr90-current-suggestions](https://github.com/newling/rocjitsu-test-corpus/tree/review/pr90-current-suggestions), based on the reviewed corpus head ([combined diff](https://github.com/newling/rocjitsu-test-corpus/compare/7d71596dae6e16eafc1d1d7c07b8e7cd38020320...review/pr90-current-suggestions)). The tested diffs are included below as patches without author metadata; apply them in numeric order to that head with `git apply`.

| Commit | Patch | Item |
| --- | --- | --- |
| [1b50c21](https://github.com/newling/rocjitsu-test-corpus/commit/1b50c21e220d57f3c797d422dbae19d53c9433ff) | [01](pr90/01-retain-exec-zero-slots.patch) | Make the three remaining masked-load cases depend on retaining the masked slot |
| [2ab4553](https://github.com/newling/rocjitsu-test-corpus/commit/2ab45535650d3b32b571a729c1d41e6bfe1cf0b2) | [02](pr90/02-trigger-storecnt-backpressure.patch) | Exercise STOREcnt backpressure before testing LOADcnt isolation |
| [4adf856](https://github.com/newling/rocjitsu-test-corpus/commit/4adf856db31dd115effebed2a9279f845eee065f) | [03](pr90/03-clarify-comments.patch) | Clarify capacity and instruction-skipping comments |

## Tests

The submitted head passed **218/218 corpus cases** through the production race adapter API: gfx1250 102, gfx942 8, gfx950 79, and gfx1151 29. This includes all 40 additions and all affected shared-header consumers. The native matcher/fixture checks, **65 Python adapter tests**, and **128 focused companion counter-capacity/register-access tests** also passed. The final suggestion branch passed all **102 gfx1250 cases** after removing the temporary detector mutations. The diff passes whitespace checks; the corpus has no applicable pre-commit configuration.

The two findings below were confirmed with deliberate detector mutations, then checked again with the detector restored. Separately, removing counter-only instruction accounting caused the new invalidate partial-wait, bpermute boundary, and DS_NOP boundary tests to fail with the expected VGPR races; all three negative controls continued to pass.

Builds used ROCm SDK `10.1.0a20260812` and a Release simulator built with upstream Clang 23.1.0. Emitted instructions were inspected for issue counts, masked-operation placement, probe-before-wait ordering, and scratch spills. The final code has the masked load at issue 63 in each clean case, an active issue at 64, and 64 stores before the STOREcnt probe. There are no scratch spills. These are emulator and specification checks, not GPU hardware measurements.

| Cost | Base | Submitted head |
| --- | ---: | ---: |
| Compile and link gfx1250 test binary, median of three forced builds with ccache disabled | 3.91 s | 4.41 s |
| Full gfx1250 suite, two processes with four emulator CPU threads each | 12.02 s / 62 cases | 18.69 s / 102 cases |

The build measurement reuses configured dependencies and excludes configuration/downloads. Runtime measurements are indicative results from a shared host; the final suggestion run took 21.25 s. The 40 additions account for 14.65 s of summed per-case elapsed time in the submitted run, about 7.3 s with two workers. Their median elapsed time is 366 ms, versus 47 ms reported inside GoogleTest. Most elapsed time is outside the test body. The measured cost does not justify dropping boundary controls or restructuring the build in this PR.

## Summary

I found two gaps where existing tests can pass despite the detector being broken. Both can be closed by changing the current instruction sequences, without adding tests. I found no incorrect expected result in the added cases.

The main expectations agree with the public [CDNA5 ISA, revision 27 July 2026](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf): finite counters and ordered completion (§5.7.1), unordered scalar loads (§5.7.1.1), FLAT participation in both domains (§5.7.1.3), separate async completion classes (§10.8), and tensor instruction completion (§10.11.1). The invalidate's ordering with VMEM reads is also explicit in [LLVM's wait insertion](https://github.com/llvm/llvm-project/blob/1ac93e094347b45208f215c98038606432c87d60/llvm/lib/Target/AMDGPU/SIInsertWaitcnts.cpp#L1602-L1605). For DS_NOP, the general “every LDS instruction” rule and ordered LDS completion support the model; its individual opcode entry only says “Do nothing,” so it does not independently explain the counter behavior.

The tests already reuse the shared DS probes, allocation/checking fixture, tensor descriptors, and LDS helpers. The older shared VMEM probe cannot be substituted unchanged: its younger loads repeatedly write one VGPR, whereas these gfx1250 tests use distinct destinations to avoid the ISA's permitted out-of-order VGPR writeback. I found no further immediate extraction worth requiring. The precise one-finding expectations and the unconstrained raced values should be preserved.

## Actionable items

### Make the remaining masked cases test retention of the counter slot

Locations: [`asynccnt_exec_zero_kernel`, line 1931](https://github.com/ROCm/rocjitsu-test-corpus/blob/7d71596dae6e16eafc1d1d7c07b8e7cd38020320/corpus/race/integration/hip_race_gfx1250_test.hip#L1931), [`flat_dscnt_capacity_kernel`, line 2083](https://github.com/ROCm/rocjitsu-test-corpus/blob/7d71596dae6e16eafc1d1d7c07b8e7cd38020320/corpus/race/integration/hip_race_gfx1250_test.hip#L2083), and [`flat_loadcnt_capacity_kernel`, line 2238](https://github.com/ROCm/rocjitsu-test-corpus/blob/7d71596dae6e16eafc1d1d7c07b8e7cd38020320/corpus/race/integration/hip_race_gfx1250_test.hip#L2238).

The earlier review's request still applies to these three clean cases. The masked instruction is currently issue 64: admitting it already completes the oldest operation. The detector can then discard its slot and the test still passes. I reproduced that with a mutation that preserves admission but drops EXEC-zero slots: all three clean cases passed, while the already-corrected ordinary LOADcnt case failed.

Move the masked operation to issue 63, restore EXEC, and issue an active async/DS/global load at 64 before probing the oldest result. Keep the masked barrier-arrive control at issue 64, because that case tests whether the instruction may be skipped. Commit [1b50c21](https://github.com/newling/rocjitsu-test-corpus/commit/1b50c21e220d57f3c797d422dbae19d53c9433ff) ([patch](pr90/01-retain-exec-zero-slots.patch)) makes this change without altering test counts or total issue counts. All three cases then reject the dropped-slot mutation with their intended LDS/VGPR race, and all 14 affected cases pass with the detector restored. The barrier-arrive control and one-short controls remain valid.

### Attempt a STOREcnt overflow before checking LOADcnt isolation

Location: [`storecnt_pressure_kernel`, line 1766](https://github.com/ROCm/rocjitsu-test-corpus/blob/7d71596dae6e16eafc1d1d7c07b8e7cd38020320/corpus/race/integration/hip_race_gfx1250_test.hip#L1766).

The kernel issues one load and 63 stores before reading the load result. STOREcnt is full, but none of those stores requires backpressure. The later output store follows the explicit counter drains, so it does not exercise that boundary either.

Change the store repetition count to `kCounterCapacity + 1`. I tested a mutation that incorrectly drains LOADcnt specifically when STOREcnt overflows: the submitted test passed, while the 64-store version failed with “expected exactly one race, got 0.” With the correct detector, the revised test passes and still reports the intended load-to-`v_mov_b32` race. Commit [2ab4553](https://github.com/newling/rocjitsu-test-corpus/commit/2ab45535650d3b32b571a729c1d41e6bfe1cf0b2) ([patch](pr90/02-trigger-storecnt-backpressure.patch)) implements this one-instruction strengthening, with no added test or allocation.

## Suggestions

- At [`hip_race_gfx1250_test.hip:1524`](https://github.com/ROCm/rocjitsu-test-corpus/blob/7d71596dae6e16eafc1d1d7c07b8e7cd38020320/corpus/race/integration/hip_race_gfx1250_test.hip#L1524), say that the stall waits for enough operations to complete; “the oldest operation” only follows for an ordered class. Commit [4adf856](https://github.com/newling/rocjitsu-test-corpus/commit/4adf856db31dd115effebed2a9279f845eee065f) ([patch](pr90/03-clarify-comments.patch)) corrects this, makes the LOADcnt skipping argument conditional on an older load remaining pending, and narrows the allocation comment in [`race_test_support.hpp:37`](https://github.com/ROCm/rocjitsu-test-corpus/blob/7d71596dae6e16eafc1d1d7c07b8e7cd38020320/corpus/race/integration/race_test_support.hpp#L37) to the LDS probes. Commit [1b50c21](https://github.com/newling/rocjitsu-test-corpus/commit/1b50c21e220d57f3c797d422dbae19d53c9433ff) also corrects “is skipped whenever” to “may be skipped” in the async-arrive explanation.
- Refresh the PR description's counts from 34 additions / 96 gfx1250 cases to **40 / 102**, identify which companion revision its validation covers, and make the same “may be skipped” correction. No description edit was made.

## Scope decisions

The companion now addresses the earlier invalidate, ignored-buffer, lane-permute, DS_NOP, and neighboring-wave fixture requests in code and focused tests. Its approval does not resolve the corpus's remaining masked-sequence gap above. There is no need to duplicate every decoded counter-only opcode in HIP: the companion already iterates the lane-permute and write-back families and tests their retained slots and partial waits.

Cross-architecture probe consolidation remains a **follow-up idea**, as previously discussed. A separate runtime follow-up could investigate amortizing process setup, but batching these cases would first need per-test race-log isolation: the current fixture reads the cumulative sink. Neither change is requested here. The full LDS barrier-cell synchronization feature remains separate from this test of an EXEC-zero arrival.

## Appendix: reproduce the coverage gaps

At the pinned companion revision, apply the following temporary mutations independently. Restore the source and rebuild between them. The first removes retained slots while preserving admission; the second introduces an incorrect cross-domain completion only on actual STOREcnt overflow.

```diff
diff --git a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp b/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp
index fb98d2ed8b1..8e0fc2e309f 100644
--- a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp
+++ b/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp
@@ -226,6 +226,8 @@ bool flat_counts_on_both_domains(rj_code_arch_t arch) { return arch == ROCJITSU_
 void register_unused_flat_domains(WaveRaceState &race, const InstructionSnapshot &instruction,
                                   const amdgpu::MemoryIssueInfo &decoded,
                                   const amdgpu::MemoryIssueInfo &routed, bool is_load) {
+  if (routed.counter_obligations().empty())
+    return; // Review mutation: drop the slots of an EXEC-zero FLAT.
   for (const auto obligation : decoded.counter_obligations()) {
     const bool used = std::ranges::any_of(routed.counter_obligations(), [&](const auto routed_one) {
       return routed_one.wait_counter_type() == obligation.wait_counter_type();
@@ -566,6 +568,7 @@ void RaceDetectorPlugin::onAmdgpuMemoryAccessRouted(const amdgpu::MemoryAccessOb
   // access whose lanes are all cleared while EXEC is active records none, and
   // neither does an ignored buffer instruction (see ignored_memory_issue()).
   const auto record_exec_zero_slot = [&](bool is_load) {
+    return; // Review mutation: admit the issue but drop the retained slot.
     if (!exec_zero_memory_issue_counts(wf.cu().arch()) || wf.exec() != 0 ||
         ignored_memory_issue(inst, wf))
       return;
```

```diff
diff --git a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp b/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp
index 52e5a13b725..ff00e991e45 100644
--- a/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp
+++ b/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp
@@ -198,6 +198,8 @@ void WaveRaceState::prepareForCounterIncrement(amdgpu::WaitCounterType type, uin
   // finite counter. Once participation is known, admission establishes the
   // same upper bound as an implicit partial wait.
   applyCounterConstraint(type, capacity - increment, /*includeUnordered=*/false);
+  if (type == amdgpu::WaitCounterType::STORECNT)
+    applyCounterConstraint(amdgpu::WaitCounterType::LOADCNT, 0, /*includeUnordered=*/false);
 }
 
 void WaveRaceState::prepareForMemoryIssue(const amdgpu::MemoryIssueInfo &info) {
```

The local validation runner calls the adapter API directly to keep all generated artifacts outside the checkout. The unified pytest entrypoint requires `$ARTIFACTS` to resolve inside the corpus checkout; an attempted external directory is rejected during fixture setup, before any kernel runs. This pre-existing entrypoint restriction is not changed by this PR.

Rebuild the companion's race plugin with `cmake --build "$ROCJITSU_BUILD" --target rocjitsu_plugin_race_so --parallel 8`. With the normal ROCm SDK environment and `ROCJITSU_SOURCE` pointing to `emulation/rocjitsu`, the corpus's documented adapter can run the relevant cases from the corpus checkout:

```bash
ROCJITSU_RACE_CONFIG="$ROCJITSU_SOURCE/configs/gfx1250_mi455x.json" \
ROCJITSU_RACE_BUILD_ROOT="$CORPUS_BUILD" \
pytest tests/test_corpus.py --target gfx1250 --suite race \
  --artifact-directory "$ARTIFACTS" \
  --run-wrapper "$ROCJITSU_BUILD/tools/rocjitsu/rocjitsu --config {config} --cpu-thread-budget 4 --" \
  -k 'loadcnt_exec_zero or asynccnt_exec_zero or flat_exec_zero or storecnt_pressure'
```

On the submitted corpus, the first mutation is missed by the three named clean cases; the ordinary LOADcnt control detects it. The second mutation is missed by the STOREcnt isolation case. On the corresponding suggestion commits, those cases fail for the diagnostic changes described above. After both mutations are removed, all cases pass.

The suggestion branch and all three commits are published at the links above; their exact diffs are also provided in the linked patches. Both requested code fixes and the comment suggestions are implemented and validated there; the PR-description refresh is a written suggestion only. GPU hardware execution and a full independent review of the companion remain outside the validation reported here.
