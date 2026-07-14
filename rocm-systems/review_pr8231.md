This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8231
**Commit reviewed:** `82da156c32` (`test(rocjitsu): update RegisterAccess codegen expectations`)

**Register-access boundary check:**

```bash
python3 emulation/rocjitsu/scripts/check_register_access.py
```

passed with no violations.

**Whitespace check:**

```bash
git diff --check origin/develop...HEAD
```

passed with no whitespace errors.

**Build command:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

passed. The target rebuilt 437 steps and completed in 122.03s real time.

**Focused CTest command:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R 'RegisterAccessTest|ExecutionPluginTest|SharedInfraTest|InstructionExecutionHarnessTest|MfmaExecTest|Gfx1250WmmaTest|SimdCorrectness' \
  --output-on-failure --timeout 60
```

passed: 151/153 passed, 0 failed, 2 skipped, 0 errored. CTest reported 59.46s real time. The skipped tests were `Gfx1250WmmaTest.F8SpecK128UsesPairAwareInputLocators` and `ExecutionPluginTest.MfmaFastPathReadHookReportsRace`. The latter requires a 16-lane native float SIMD shape that is not available on this host.

**Python codegen tests:**

```bash
.venv/bin/python -m pytest emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py emulation/rocjitsu/lib/python/amdisa/tests/test_sema_derive.py emulation/rocjitsu/lib/python/amdisa/tests/test_sema_lower.py
python3 -m pytest --version
```

could not run locally because neither the worktree virtualenv nor system Python has `pytest` installed. The project docs expect `cd lib/python && python -m pytest amdisa/tests/ -x`, so this is a local environment gap rather than a test failure.

**CI status at review time:** release, asan-ubsan, asan-ubsan-gcc, pre-commit, package builds, and TheRock CI summary were passing. The `therock-pr-bot` check was failing on PR title/description policy.

## Summary

This PR builds on the lane-mask VGPR read hook work and introduces `RegisterAccess` as the AMDGPU instruction-facing boundary for VGPR access. The new facade provides physical VGPR read, write, and read-write regions, plus logical operand views for SIMD helpers. Read and read-write acquisition reports plugin-visible VGPR reads before exposing storage; write-only views deliberately do not report reads.

The branch migrates MFMA/WMMA fast paths, common SIMD helper families, shared helpers, hand-maintained gfx1250 address calculation, generated operand backends, and generated AMDGPU instruction code through that boundary. It also adds a pre-commit checker that rejects direct raw VGPR storage, direct CU physical VGPR reads/writes, and direct `SimdAccess` use under AMDGPU instruction implementation code.

The generated-output commits are large, but the sampled pattern is consistent with the intended architecture: generated code either uses operand APIs for operand semantics or `RegisterAccess` for physical VGPR access. The focused SIMD and register-observation tests passed locally.

## Actionable items

### 1. Fix the PR title/body policy failure before marking the PR ready

**Location:** PR metadata

The TheRock policy bot is currently failing because the PR title is not conventional-commit formatted and the body has no accepted issue/JIRA/closing reference. This blocks review readiness even though the code/test CI is otherwise green.

Change the title to a conventional-commit form such as:

```text
refactor(rocjitsu): route AMDGPU instruction VGPR access through RegisterAccess
```

and add an accepted issue reference to the body, for example:

```text
Fixes #8040
```

or the appropriate issue/JIRA reference if this PR should not close #8040.

## Suggestions

### 1. Remove stale wording from the checker failure message

**File:** `emulation/rocjitsu/scripts/check_register_access.py:55`

The checker message still says "non-gfx1250 AMDGPU instruction helpers", but the current script scans all AMDGPU instruction implementation code under `isa/arch/amdgpu`. Consider changing the message to "AMDGPU instruction helpers" so failures describe the current scope accurately.

## Commentary

The architecture direction is coherent. `RegisterAccess` centralizes the current social contract around observed reads without trying to make raw VM storage inaccessible everywhere at once. The temporary checker is a pragmatic guardrail while instruction bodies still receive `Wavefront&` and can technically reach `wf.cu()`.

The operand-view tests are mostly indirect rather than isolated in `RegisterAccessTest`: the direct unit tests cover physical regions, and the execution-plugin/SIMD correctness tests cover the operand-backed paths. Given the size of this migration, that split is reasonable, but a future small unit test for `read_operand`, `read_operand64`, and `readwrite_operand` would make the facade contract easier to verify without decoding an instruction.
