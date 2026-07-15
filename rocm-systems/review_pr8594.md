This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8594

**Commit reviewed:** `070723e0c4` (`perf(rocjitsu): Optimize MFMA/WMMA execution`).

**Public/repo status:** the repository and #8594 are public. The PR is open, not draft, targets `develop`, and the head branch is in the same public repository. The related #8417 PR is also public, open, and targets `develop`.

**GitHub checks:**

```bash
gh pr checks 8594 --repo ROCm/rocm-systems
```

Result: the repository policy bot failed because source files changed without a file matching the unit-test naming policy. The visible build, sanitizer, package, pre-commit, and summary checks passed; several hardware/platform lanes were skipped.

**Build command:**

```bash
cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

Result: passed. Timing: 119.36s real, 890.64s user, 42.63s sys.

**Focused correctness CTest command:**

```bash
ctest --test-dir $BUILD_DIR \
  -R 'MfmaExecTest|MfmaF64|Gfx1250Wmma|Wmma|Swmmac|MfmaF16Accumulation|InstructionExecutionHarnessTest|ExecutionPluginTest' \
  --output-on-failure --timeout 60
```

Result: passed. CTest selected 33 tests: 33 passed, 0 failed, 0 skipped, 0 errored. Timing: 0.71s real, 0.52s user, 0.19s sys.

**New benchmark test command:**

```bash
$BUILD_DIR/tests/rocjitsu_tests --gtest_filter='MfmaBenchmark.*'
```

Result: failed. GoogleTest ran 4 tests from `MfmaBenchmark`: 1 passed, 3 failed, 0 skipped. Timing: 1.99s real, 1.98s user, 0.01s sys.

The failing cases were:

```text
MfmaBenchmark.F32_32x32x8_F16:  0.005967 MIPS vs EXPECT_GT(s.mips, 0.01)
MfmaBenchmark.F32_16x16x32_F16: 0.008623 MIPS vs EXPECT_GT(s.mips, 0.01)
MfmaBenchmark.I32_32x32x8_I8:   0.005318 MIPS vs EXPECT_GT(s.mips, 0.01)
```

Note that these benchmark tests are intentionally excluded from default CTest registration by `rj_add_gtest_tests(rocjitsu_tests TEST_FILTER -*Benchmark*)`, so the direct benchmark invocation is the relevant local validation for the new file.

**Relation-to-#8417 check:**

```bash
git merge-tree \
  $(git merge-base refs/remotes/pull/8417/head refs/remotes/pull/8594/head) \
  refs/remotes/pull/8417/head \
  refs/remotes/pull/8594/head
```

Result: #8594 does not merge cleanly with #8417. The main conflict is in `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h`, where #8417 routes matrix-helper VGPR access through `RegisterAccess` and #8594 rewrites the same helpers against raw `ComputeUnitCore::read_vgpr` / `write_vgpr`.

## Summary

This PR changes the shared AMDGPU MMA execution helpers to reduce per-instruction overhead. In several MFMA/WMMA paths it replaces `std::vector<Result>` result staging with fixed-size stack arrays, adds explicit capacity checks before writing those arrays, and preloads A/B matrix operands into dense stack-local buffers before the output loop so repeated operand extraction is avoided.

The PR also adds `emulation/rocjitsu/tests/mfma_benchmark.cpp`, a CDNA4 wave64 timing tool for four MFMA shapes. That source is compiled into `rocjitsu_tests`, but benchmark cases remain filtered out of default CTest, matching the existing benchmark policy in `emulation/rocjitsu/tests/CMakeLists.txt`.

Relative to #8417, this PR is a direct overlap rather than an independent change. #8417 tightens register access observation by making instruction code go through `RegisterAccess`; #8594 optimizes a hot file touched by that boundary. The right combined result is presumably #8594's operand/result staging expressed through #8417's observed register-access facade or region helpers.

## Actionable Items

### 1. Make the new benchmark pass when invoked directly

**File:** `emulation/rocjitsu/tests/mfma_benchmark.cpp:141`

The new benchmark file is intended to be run manually because `emulation/rocjitsu/tests/CMakeLists.txt:446` excludes `*Benchmark*` tests from default CTest. On this host, direct invocation of `MfmaBenchmark.*` fails 3 of 4 tests because the fixed throughput threshold is machine-sensitive: the observed MIPS values for the larger shapes were about 0.0053-0.0086, below the `0.01` assertions at lines 141, 158, and 189. This makes the benchmark unreliable as a timing tool on slower or loaded hosts even though the focused correctness CTest slice passes.

Please remove the fixed `EXPECT_GT(s.mips, 0.01)` checks from this benchmark, or replace them with a non-throughput sanity check that is not host-speed dependent. If the intent is only to prevent dead-code elimination or zero-duration runs, assert on something like nonzero elapsed time / positive iteration count and leave throughput as printed output.

### 2. Finish the result-staging conversion or narrow the PR's scope

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:1444`

The PR removes several `std::vector<Result>` allocations, but `mma_exec.h` still has result vectors in the same file and instruction family:

```text
1444 exec_gfx11_wmma_f32_mixed
1490 exec_gfx11_wmma_packed16
1583 exec_wmma_f32_scaled_mixed
2224 exec_wmma_bf16f32_16x16x32_bf16
3154 exec_gfx11_wmma_i32
```

For `exec_gfx11_wmma_packed16`, the `words` and `masks` buffers were converted to fixed arrays, but result staging still heap-allocates before packing. This leaves part of the advertised allocation removal undone and keeps a per-call allocation in matrix execution helpers.

Please either convert these remaining `std::vector<Result>` paths to the same bounded stack-array pattern used elsewhere in this PR, or adjust the PR description and benchmark claims so they do not imply all `mma_exec.h` result-staging allocations have been removed.

## Suggestions

### 1. Add a non-benchmark regression test if this needs policy-bot coverage

**File:** `emulation/rocjitsu/tests/CMakeLists.txt:446`

The new source is named `mfma_benchmark.cpp` and the benchmark suite is filtered out of normal CTest discovery. That matches the local benchmark convention, but it also explains the policy-bot failure and means the new benchmark does not provide CI-style regression coverage. If this PR needs a policy-compliant test addition, add or extend a correctness-focused `*_test.cpp` file for the touched helper behavior, and keep the benchmark as a manual performance tool.

### 2. Rebase carefully if #8417 lands first

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:1037`

If #8417 lands before this PR, do not resolve the conflict by restoring raw `cu.read_vgpr` / `cu.write_vgpr` calls. The combined implementation should preserve #8417's observed register-access boundary, likely by using `RegisterAccess` and the region read/write helpers around #8594's dense operand buffers. Otherwise this optimization can reintroduce the exact unobserved matrix-helper register-access path that #8417 is closing.

## Commentary

I did not find a functional correctness failure in the focused MFMA/WMMA CTest slice on #8594 itself. The implementation risk is mostly around reviewability and integration order: #8594 is based on the pre-#8417 raw-register API shape, while #8417 changes the same file to make plugin-observed register access the instruction-facing boundary.

The performance direction looks reasonable for MFMA paths that repeatedly read the same A/B operands inside the output loop. The remaining question is how broadly the fixed-capacity stack buffers should be applied. The current patch already uses large generic capacities, so it would be worth keeping MFMA and WMMA capacity choices tied to actual decoded shape bounds when the #8417 port happens.
