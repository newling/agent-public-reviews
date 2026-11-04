> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#15009](https://github.com/ROCm/rocm-systems/pull/15009)

**Reviewed head:** `997b9a8fb50297ce6f320739a938fbb26666f5ce`

**Suggestion branch:** [`review/pr15009-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr15009-suggestions), based on the reviewed head.

| Commit | Item |
| --- | --- |
| [`8d4d147eeb8`](https://github.com/newling/rocm-systems/commit/8d4d147eeb8f6f0f9b22d7d2a56d9555443b8e41) | Actionable item 1: test that the harness bits preserve the initial guest state |
| [`451ec97b923`](https://github.com/newling/rocm-systems/commit/451ec97b923347618b2ea0cfb26d70f04b999e39) | Suggestion 1: say in the README that wait diagnostics only warn |

## Tests

On an ASan/UBSan build, the execution and multiplexer fuzz suites (GTest plus the execution and multiplexer CLI tests) passed on the submitted head (31/31) and on the suggestion branch (32/32). In CI, every rocjitsu build and test lane passed; `therock-pr-bot` fails, as described in item 2.

As an exploratory check beyond the PR's own tests, a temporary probe ran 200 generated kernels per target at the 256-byte and 1024-byte sizes, 4,800 kernels in all. Every kernel halted normally with no budget exhaustion and no `memory-wait:` or `xcnt-wait:` diagnostics. The source is in the appendix.

## Summary

The PR adds a third input family to the execution fuzzer: bounded, structured kernels assembled from each target's generated encodings. Each kernel mixes VALU, SALU, FLAT loads and stores, scalar loads, `v_cmpx`, EXEC restores, and forward conditional branches, with at most one counted backward loop. Byte one of the input gains two harness bits. `0x10` turns on runtime wait checking, and `0x20` routes data through the L2-backed memory path instead of direct translation. The random mix, the AFL seed corpus (one kernel per target), and the multiplexer seed corpus now include generated kernels.

The generator's termination argument is easy to check, which I think is the strongest part of the design. Only one backward edge exists, and its counter is stored in a register no other operation writes. Forward targets are recorded as operation indices and clamped to the final `s_endpgm`, and each memory access emits its own waits, so a branch target never lands between an access and its wait. Generated code never overwrites the address pairs in `s0`–`s15` and `v0`–`v15`, so every memory access stays inside the mapped data island. The probe above agrees with this argument: across 4,800 kernels and every target, none exhausted the step budget or reported a wait diagnostic. Masking the two harness bits out of the initial-state seed is also a good choice, because it lets a saved input be replayed with wait checking or the cache path toggled without changing the program it exercises.

## Actionable items

### 1. Test that the new harness bits do not change the initial guest state

`emulation/rocjitsu/fuzz/execution/execution_fuzz_core.h:77` and `README.md:16` promise that flipping the wait-checking and cache bits preserves the initial register and memory contents. The behavior depends on the masking at `execution_fuzz_core.cpp:345`. No test checks this directly. `WaitCheckingBitEnablesDiagnosticsOnReplay` and the updated `InitialAddressPairsReachMappedMemory` both toggle the bits, but their programs do not depend on seeded state, so they still pass after the masking is removed. A refactor of the seed loop could quietly break replay of saved inputs, the reason the contract exists.

Commit [`8d4d147eeb8`](https://github.com/newling/rocm-systems/commit/8d4d147eeb8f6f0f9b22d7d2a56d9555443b8e41) adds `HarnessBitsPreserveInitialScalarCondition`, which follows the pattern of the existing `AsyncOverridePreservesInitialScalarCondition`. It branches on the seeded SCC, varies a trailing marker byte to change the seed, and requires all four bit combinations to execute the same number of instructions. It passes on the PR. With the masking removed (`const uint8_t byte = input[i];`), it fails 98 times across the 64 markers.

### 2. Add a tracking reference to the PR description

`therock-pr-bot` fails with "PR description must reference a JIRA ID, ISSUE ID, or a GitHub closing keyword." Add an `ISSUE ID:` or `JIRA ID:` line naming the issue or ticket this work belongs to. The PR changes test files, so the bot's test-file rule should already be met.

## Suggestions

### 1. Say that wait diagnostics only warn

`emulation/rocjitsu/fuzz/execution/README.md:16` says bit `0x10` "enables runtime memory-wait diagnostics." `ComputeUnitCore` reports a hazard through `util::Logger::warn` and suppresses further reports after 16 per compute unit. The input outcome stays the same, so neither AFL nor `--random` treats a wait hazard as a finding. A reader may expect the opposite. Commit [`451ec97b923`](https://github.com/newling/rocm-systems/commit/451ec97b923347618b2ea0cfb26d70f04b999e39) adds one sentence to make this explicit. See also the commentary below about whether this signal should eventually be reported.

### 2. Avoid hard-coded seeds that depend on the target count in `RandomMixRunsGeneratedKernelsAcrossTargets`

`tests/fuzz/execution/execution_fuzz_test.cpp:85` uses seeds `25`, `26`, `73`, and `121` because `random_input` chooses the generated-kernel family when `(seed / kTargets.size()) % 4 == 2` (`execution_fuzz_core.cpp:548`). This applies even with an explicit target. Adding a thirteenth target changes that division, and the test's `EXPECT_EQ(input, generated_kernel_input(...))` would fail for reasons unrelated to the change being made. The test could search for the first few seeds where `random_input` equals `generated_kernel_input`. Alternatively, the family choice could use seed bits that do not depend on `kTargets.size()`; the multiplexer already protects its selector IDs from this kind of churn with `SelectorIdsRemainStableAsTargetsAreAdded`. I left this unimplemented because whether the family selection should depend on the target count is the author's design choice.

### 3. Run the structural generator check on every target

`GeneratedKernelBranchTargetsAndFlatWaits` (`execution_fuzz_test.cpp:113`) decodes generated kernels and checks branch targets, termination, and the FLAT wait sequences for gfx1100 and gfx1250 only. The CDNA FLAT layout with `saddr = 0x7f`, RDNA1/2, and RDNA4 depend on the runtime test, which would detect a misaligned target only as a stopped wave. The decode, termination, and branch-target checks do not depend on the architecture, so they could run for all twelve targets, with wait-word checks kept for the cases that list them. I left this unimplemented because the runtime test and the probe already cover these targets indirectly. This change would make a failure easier to locate.

## Commentary

The PR description says a three-hour sanitizer campaign found "no failures." That covers host memory errors and undefined behavior. It says nothing about wait-checker results, since wait diagnostics never fail an input. Generated kernels are wait-correct by construction, so any wait diagnostic on an unmutated generated kernel means a checker false positive or a generator bug. Both would be useful to find. In the `--random` campaign, generated kernels are not mutated. The harness could count wait diagnostics for that family and report the count in the JSON summary, or treat them as failures. That would turn this part of the change from exercising the checker code into testing the checker. It probably needs a structured hazard callback rather than parsing log output, so it seems better as a follow-up.

Because generated kernels never write the address-pair registers, they never reach the translation-fault path. That fits the goal of bounded programs that reach execution, and raw-byte inputs still cover faults. A small, explicit share of generated kernels with an out-of-island address could add fault coverage for the cache-backed route specifically, which the fuzzer first exercises in this PR.

## Appendix: generated-kernel outcome probe

This temporary GTest case was added to `tests/fuzz/execution/execution_fuzz_test.cpp`, with `#include <cstdio>`, and then removed. On the submitted head, every line reported `exhausted=0 stopped=0 warned=0`.

```cpp
TEST(ExecutionFuzzProbe, GeneratedKernelOutcomes) {
  for (size_t size : {kGeneratedKernelSeedSize, kMaxInputSize}) {
    for (uint8_t index = 0; index < static_cast<uint8_t>(FuzzTarget::Count); ++index) {
      const FuzzTarget target = *indexed_target(index);
      uint64_t exhausted = 0, stopped = 0, warned = 0;
      for (uint64_t seed = 0; seed < 200; ++seed) {
        const std::vector<uint8_t> input = generated_kernel_input(seed, size, target);
        testing::internal::CaptureStderr();
        const RunStats stats = run_input(input, std::nullopt, nullptr, AsyncMode::Disabled, 1);
        const std::string diagnostics = testing::internal::GetCapturedStderr();
        warned += diagnostics.find("-wait:") != std::string::npos;
        exhausted += stats.budget_exhausted;
        stopped += stats.inputs_stopped;
      }
      std::printf("size=%zu target=%s exhausted=%lu stopped=%lu warned=%lu\n", size,
                  std::string(target_name(target)).c_str(), exhausted, stopped, warned);
    }
  }
}
```

## Branch handoff

The branch is [`review/pr15009-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr15009-suggestions), based on `997b9a8fb50`. [`8d4d147eeb8`](https://github.com/newling/rocm-systems/commit/8d4d147eeb8f6f0f9b22d7d2a56d9555443b8e41) implements actionable item 1, and [`451ec97b923`](https://github.com/newling/rocm-systems/commit/451ec97b923347618b2ea0cfb26d70f04b999e39) implements suggestion 1. Both commits pass pre-commit and the fuzz suites listed above. Actionable item 2 and suggestions 2 and 3 have no commits. Item 2 is a PR-description edit, and suggestions 2 and 3 are left to the author for the reasons given in each item.
