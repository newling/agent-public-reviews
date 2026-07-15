This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8177

**Commit reviewed:** `ce48044c9cb3f05edbf03fe22c361b463ba6665e` (`test(rocjitsu): validate decoded mnemonics`)

**Public/repo status:** the repository and PR are public. The PR is open, not draft, and targets `develop`.

**Build command:**

```bash
cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: passed. Switching to the PR head caused a broad incremental rebuild of
generated ISA and rocjitsu test objects, then linked `rocjitsu_tests`.

**Focused test command:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='InstructionExecutionHarness.*:Gfx1250MemoryExecutionHarness.*'
```

Result: passed. GoogleTest ran 11 tests from 2 suites: 11 passed, 0 failed, 0
skipped, 0 errored. Runtime was 0.01s real time. The instruction harness
reported the expected unimplemented scalar instructions by architecture:

- CDNA1/2/3/4: `s_setvskip`
- RDNA1: `s_subvector_loop_begin`, `s_subvector_loop_end`, `s_get_waveid_in_workgroup`
- RDNA2: `s_subvector_loop_begin`, `s_subvector_loop_end`
- RDNA3/RDNA3.5/RDNA4/gfx1250: no unimplemented scalar instructions

**Whitespace check:**

```bash
git diff --check origin/develop...refs/remotes/origin/pr/8177
```

Result: passed with no whitespace errors.

**CI status at review time:** `pre-commit`, `test (release)`,
`test (asan-ubsan)`, `test (asan-ubsan-gcc)`, TheRock summary, and HIP NVIDIA
summary were all passing.

## Summary

The current PR is much narrower than the earlier version. It now changes only:

- `emulation/rocjitsu/tests/instruction_execution_harness_test.cpp`
- `emulation/rocjitsu/docs/configuration.md`

The point of the PR is to turn the instruction execution harness from a loose
coverage smoke test into a real quality gate for generated scalar instruction
encodings across every supported AMDGPU architecture.

Before this PR, the harness iterated generated test encodings and printed a
coverage percentage, while tolerating decode misses and any non-`UnimplementedInst`
exception from executed instructions. That made the test useful as a status
report, but weak as a regression gate.

After this PR, the harness enforces several explicit contracts:

1. Every non-skipped generated sample must decode.
2. The decoded instruction mnemonic must match the mnemonic paired with the
   sample words in the generated table.
3. Implemented scalar instructions must execute without throwing.
4. The exact set of still-unimplemented scalar instructions must match a
   per-architecture allowlist.

The harness intentionally remains scoped to "safe scalar encodings" because the
generated tables include memory, vector, control-flow, wait, and trap
instructions that need realistic wavefront state or valid memory addresses.
Those are skipped by mnemonic prefix. To cover one important class outside that
scalar-only gate, the PR adds a focused gfx1250 memory harness test that decodes
and executes representative valid-address `global_store_b32` and
`buffer_store_b32` instructions.

The documentation change is small: it clarifies that `num_threads` is the number
of PDES engine partitions / worker threads, and that the example config is
intentionally minimal and single-threaded.

The earlier branch history appears to have included broader D16/race-detector
and generated-ISA changes. Those are no longer in the current diff. The current
PR is now a test-quality-gate PR, not a runtime semantic change PR.

## Actionable items

No blocking issues found.

## Suggestions

No non-blocking suggestions for the current diff.

## Commentary

This PR is useful because it makes generated-ISA test data self-policing. In
particular, the decoded-mnemonic check is important: without it, a generated
sample word that decodes to a different instruction can accidentally count as
coverage for the claimed mnemonic. The exact unimplemented allowlists are also
more actionable than a percentage threshold, because a failure tells the
developer which instruction changed status.

The scope is intentionally modest. It does not prove vector or memory instruction
execution coverage broadly; it prevents regressions in scalar decode/execute
coverage and adds one concrete gfx1250 valid-address memory execution check.
That matches the current diff and makes the PR easier to reason about than the
older 31-file version.
