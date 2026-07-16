This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8691

**Commit reviewed:** `d4b81d234aff` (`rocjitsu: preserve non-kernel AQL barrier ordering`).

**Public/repo status:** the repository and #8691 are public. The PR is open, not draft, targets `develop`, and the head branch is in the same public repository.

**GitHub checks:**

```bash
gh pr checks 8691 --repo ROCm/rocm-systems
```

Result: the rocjitsu `pre-commit` check passed; `rocjitsu-test-corpus` passed in the release, asan-ubsan, and asan-ubsan-gcc configurations; TheRock and HIP NVIDIA summaries passed. Several hardware/platform lanes were skipped. The only failed check was `therock-pr-bot`, whose log reported that the PR title does not follow Conventional Commits style.

**Build command:**

```bash
cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

Result: passed. The first build reconfigured after a generated-file glob update and rebuilt/linked `rocjitsu_tests`. I did not capture a wall-clock time for that initial rebuild. A follow-up incremental no-op build also passed and took 0.02s real, 0.01s user, 0.01s sys.

**New barrier-value tests:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R 'Cdna/IsaTest\.(VendorSpecificBarrierValue|NonKernelBarrierPacketsOrderQueueEntries)' \
  --output-on-failure
```

Result: passed. CTest selected 10 tests: 10 passed, 0 failed, 0 skipped, 0 errored. Timing: 0.13s real, 0.07s user, 0.05s sys.

**Neighboring vendor-specific packet tests:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R 'Cdna/IsaTest\.VendorSpecific' \
  --output-on-failure
```

Result: passed. CTest selected 12 tests: 12 passed, 0 failed, 0 skipped, 0 errored. Timing: 0.13s real, 0.07s user, 0.06s sys.

**Whitespace check:**

```bash
git diff --check origin/develop...HEAD
```

Result: passed with no whitespace errors.

I did not run the full IREE `static_pack_vnni_lhs_large_with_pad` flake loop locally because the assigned worktree's virtual environment does not currently have `iree-compile` or `iree-run-module` installed. The public CI corpus checks listed above did run and pass for this PR.

## Summary

This PR adds rocjitsu handling for AMD vendor-specific barrier-value AQL packets. The new local `AmdBarrierValuePacket` layout mirrors the public ROCr `hsa_amd_barrier_value_packet_t` ABI without requiring a newer extension header, and the command processor now recognizes AMD vendor format `2` as a barrier-value packet.

When a barrier-value packet's dependency signal is not ready, rocjitsu now leaves the compute queue read pointer on that packet and schedules another doorbell event, so other queues can still run and potentially satisfy the dependency. Once the condition is satisfied, rocjitsu creates a zero-work dispatch entry with the packet's completion signal, letting the existing completion tracker fire that signal through the normal path.

The PR also preserves the AQL barrier bit on non-kernel entries, including standard barrier packets and unknown vendor-specific non-kernel packets. That is important because a zero-work barrier entry should not be retired ahead of earlier in-flight dispatches when the packet carries the barrier bit.

This matches the public #8642 failure shape: an asynchronous SDMA copy can complete on a different queue while a compute queue uses a barrier-value packet to connect that SDMA completion to the HIP event observed by the client.

## Actionable items

No blocking code issues found.

## Suggestions

### 1. Retitle the PR to satisfy the policy bot

**Location:** PR metadata, title

The only failed GitHub check is `therock-pr-bot`, and its log says the PR title is not Conventional Commits style. Please retitle the PR to something like:

```text
fix(rocjitsu): handle barrier-value AQL packets
```

The commit subjects already use a conventional-enough style for the repository history; this is just the PR title policy gate.

### 2. Consider adding an SDMA-backed regression for the issue path

**File:** `emulation/rocjitsu/tests/amdgpu_vm_test.cpp:685`

The new `VendorSpecificBarrierValueConditionsWaitAndResume` test directly mutates the dependency signal from the test between engine steps. That covers the barrier-value wait/resume logic, but it does not exercise the exact #8642 path where a stalled compute queue must leave SDMA queue processing free to satisfy the dependency. A future regression that registers both a compute queue and an SDMA queue, submits an SDMA copy/completion, then submits a compute-queue barrier-value packet waiting on that completion signal would lock down the cross-queue behavior more directly.

## Commentary

The implementation is intentionally small and fits the existing command-processor model. It reuses the existing zero-work dispatch entry and completion tracker machinery instead of inventing a separate completion path for barrier-value packets, which keeps completion-signal behavior consistent with standard barriers and unknown vendor non-kernel packets.

The local ROCr header on this system defines `HSA_AMD_PACKET_TYPE_BARRIER_VALUE = 2` and documents null dependency signal handles as satisfied, which matches the PR's format selector and null-signal handling.
