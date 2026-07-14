This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8499
**Commit reviewed:** `86cc4f3d10c56e6edd3370ac13dc5949cac983f2` (`rocjitsu: fix RDNA WGP and wave32 EXEC semantics`)

**Public/repo status:** the repository is public, and the PR head is in the same public repository.

**Build command:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

Result: passed. The build reran CMake, rebuilt and linked `rocjitsu_tests`, and completed in 117.74s real time.

**Focused CTest command:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R 'RdnaDispatchTest|CheckpointTest\.SaveAndRestoreWave32ExecScratch|CodeObjectPatcher\.AppliesArchSpecificWgpModeBit|ExecMaskTest|Rdna4ExecMaskTest|DppPermuteTest\.(RdnaGeneratedVcmpxDppWave32WriteMaskPreservesExec|Gfx1250GeneratedVcmpxDppWave32WriteMaskPreservesExec)|Gfx1250ExecutionTest\.(DsAtomicAsyncBarrierArriveFlipsRawBarrierPhase|LocalMemPipelineUsesInjectedBarrierDecrementPayload)|InstructionExecutionHarness\.Rdna4' \
  --output-on-failure --timeout 120
```

Result: passed. CTest selected 19 tests: 19 passed, 0 failed, 0 skipped, 0 errored. CTest reported 2.05s real time.

**AMD ISA profile/property tests:**

```bash
time -p .venv/bin/python -m pytest \
  emulation/rocjitsu/lib/python/amdisa/tests/test_profile_properties.py -q
```

Result: passed. Pytest reported 77 passed, 0 failed, 0 skipped, 0 errored. The command completed in 0.42s real time.

**Whitespace check:**

```bash
git diff --check origin/develop...HEAD
```

Result: passed with no whitespace errors.

**CI status at review time:** `pre-commit`, `test (release)`, `test (asan-ubsan)`, `test (asan-ubsan-gcc)`, CodeQL analysis, and HIP NVIDIA summary were passing. `therock-pr-bot` was failing in the "Enforce policy" step; see actionable item 1. The three TheRock Linux package builds were also failing, but the failing compile was in `projects/rocr-runtime/libhsakmt/src/hsakmtmodel.c` with `secure_getenv` undeclared, and that file is outside this PR's current 31-file diff. I did not treat that package failure as a rocjitsu PR code finding.

## Summary

The current revision keeps the two core changes from the earlier review: RDNA WGP-mode workgroups reserve a sibling-CU pair and route LDS through the selected shared WGP backing, and wave32 EXEC now has separate lane-masked and raw architectural views so `EXEC_HI` can survive scalar use and checkpoint/restore.

The latest revision also addresses the earlier runtime-ISA-property concern by replacing the handwritten `arch_supports_wgp_mode()` switch with generated ISA profile properties. The generated `isa_properties.h` is emitted from the amdisa profiles, tested by `test_profile_properties.py`, and used by both the command processor and code object patcher.

The previous runtime-exception concern around WGP-mode clusters is not carried forward here. The cluster and WGP paths are intentionally disjoint in the modeled architectures: workgroup clusters are a gfx1250 path, and gfx1250 does not support WGP mode. Treating the combined state as an internal invariant rather than a user-facing packet validation case is reasonable.

## Actionable items

### 1. Fix the PR title policy failure

**Location:** PR metadata

The live PR title is:

```text
[rocjitsu] Support RDNA WGP mode and fix wave32 EXEC semantics
```

The repository policy requires Conventional Commits style:

```text
type(optional-scope): short description
```

Change the title to a policy-compliant form, for example:

```text
fix(rocjitsu): support RDNA WGP mode and preserve wave32 EXEC_HI
```

or another title that satisfies the policy and length limit. This appears to be the remaining PR-specific policy blocker.

## Suggestions

None.

## Commentary

I did not find remaining code issues in the current rocjitsu diff. The WGP reservation release in `CommandProcessor::notify_wg_complete()` is part of the core resource lifetime: the WGP reservation map and shared LDS bump allocator live in the SPI, so they need a workgroup-completion signal from the command processor.

The `exec()` / `exec_raw()` contract remains clear in the current revision. The generated operand code uses raw EXEC where scalar selector access needs the architectural pair, while vector execution, address calculation, DPP/SDWA, memory masks, and `EXECZ` continue to use the lane-masked view.
