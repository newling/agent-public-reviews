This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8417

**Commit reviewed:** `4ccffa76d9` (`chore(rocjitsu): refresh generated AMDGPU ISA files`), with implementation commit `4cbbfc035b` underneath it.

**Public/repo status:** the repository and PR are public. The PR is open, not draft, and targets `develop`. The prior review's title/pushed-head concerns appear resolved in the current PR state.

**GitHub checks:**

```bash
gh pr checks 8417 --repo ROCm/rocm-systems
```

Result: required lanes were green at the time of review. The output showed the expected skipped platform/test lanes, and passing entries for pre-commit, release, sanitizer, package build, TheRock, and PR-bot checks.

**Build command:**

```bash
cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

Result: passed. The build regenerated CMake files, compiled the regenerated ISA sources and tests, and linked `rocjitsu_tests`.

Timing: 211.35s real, 1607.51s user, 49.62s sys.

**Focused CTest command:**

```bash
ctest --test-dir $BUILD_DIR \
  -R 'RegisterAccessTest|ExecutionPluginTest|SharedInfraTest|InstructionExecutionHarnessTest|MfmaExecTest|Gfx1250WmmaTest|SimdCorrectness|RaceDetector|Rdna4True16Vop3Test|Vop3FmacSimdCorrectness' \
  --output-on-failure --timeout 60
```

Result: passed. CTest selected 241 tests: 240 passed, 0 failed, 1 skipped, 0 errored. The skipped test was `ExecutionPluginTest.MfmaFastPathReadHookReportsRace`; running it alone with `-V` showed the skip reason was `MFMA fast path requires 16-lane native<float>`.

**AMD ISA Python tests:**

```bash
.venv/bin/python -m pytest emulation/rocjitsu/lib/python/amdisa/tests \
  -k 'not rdna4_parser_injects_s_waitcnt_compat and not shared_execute_preflight_detects_cdna3_fp8_cvt_divergence and not multi_isa_regen_keeps_divergent_fp8_cvt_bodies_isa_local'
```

Result: not run locally. The command failed immediately with `No module named pytest`; `python3 -m pytest --version` failed the same way, and `.venv/bin/python -m pip show pytest` reported that `pytest` was not installed. I did not install packages into the review environment.

**Static boundary scans:**

```bash
rg -n -P '\.(read|write)_vgpr\(|\.(read|write)_sgpr\(' \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu \
  emulation/rocjitsu/lib/python/amdisa/codegen \
  -g'*.h' -g'*.cpp' -g'*.py' | rg -v 'RegisterAccess'

rg -n -P 'raw_cu\(|raw_vgpr_(data|reg)|\bSimdAccess::' \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu \
  emulation/rocjitsu/lib/python/amdisa/codegen \
  -g'*.h' -g'*.cpp' -g'*.py'

rg -n -P '\.(read_scalar|read_lane|write_scalar|write_lane|read_scalar64|read_lane64|write_scalar64|write_lane64|read_lane_chunk|write_lane_chunk)\(' \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu \
  emulation/rocjitsu/lib/python/amdisa/codegen \
  -g'*.h' -g'*.cpp' -g'*.py' | \
  rg -v 'RegisterAccess|AmdgpuIsaOperand|Operand::|override|void read_lane_chunk|void write_lane_chunk'

rg -n -P 'simd_vgpr_storage|simd_notify_read|simd_vgpr_base' \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu \
  emulation/rocjitsu/lib/python/amdisa/codegen \
  -g'*.h' -g'*.cpp' -g'*.py' | rg -v '_impl|RegisterAccess|operand\.h|operand\.cpp'

rg -n -P '\bwf\.cu\(\)\.(read|write)_sgpr|\bwf\.cu\(\)\.(read|write)_vgpr|\bcu\.(read|write)_sgpr\(|\bcu\.(read|write)_vgpr\(' \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu \
  emulation/rocjitsu/lib/python/amdisa/codegen \
  -g'*.h' -g'*.cpp' -g'*.py'
```

Result: passed. Each scan produced no matches after the intended filters.

## Summary

The PR now has the shape the earlier review asked for. The pushed branch is a two-commit stack: the first commit changes the hand-written facade, generator, plugin, and test code; the second commit refreshes generated AMDGPU ISA output.

The core design is coherent. Public `Wavefront::cu()` now returns `InstructionComputeUnitView`, a deliberately narrow service view instead of the full `ComputeUnitCore` (`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/wavefront.h:192`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/instruction_compute_unit_view.h:32`). The view omits raw VGPR access, and its private raw-CU escape hatch is friend-gated to `RegisterAccess` and the ISA operand backend.

`RegisterAccess` is now the instruction-facing register facade (`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:41`). It covers logical operand reads/writes, SIMD operand views, physical SGPR access, and physical VGPR region access. Reads and read-write acquisitions observe plugin-visible register reads before exposing values or storage; write-only views do not synthesize reads.

The operand layer also closes the previous public backend gap. Operand value hooks are private and friend-only behind `RegisterAccess` (`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/operand.h:59`). Public chunk reads are no longer an unobserved side channel: the AMDGPU operand chunk implementation builds the exact lane window and reads through `RegisterAccess::read_vgpr_region` (`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/isa_operand_simd_inl.h:47`).

The test coverage is targeted at the right risks. `RegisterAccessTest` pins region read observation, write-only behavior, read-write behavior, 64-bit VGPR and SGPR observation, public chunk-read observation, and lane-oriented fallback semantics (`emulation/rocjitsu/tests/register_access_test.cpp:85`). The focused CTest run also covered the plugin read-observation tests, race detector lane-mask tests, true16 regressions, MFMA/WMMA helpers, and SIMD correctness suites touched by the generator churn.

## Actionable Items

None.

## Suggestions

### 1. Keep the dedicated instruction-context cleanup as a future design step

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/wavefront.h:192`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/instruction_compute_unit_view.h:32`

The narrow `Wavefront::cu()` view is a good low-disruption enforcement layer for this PR. The cleaner long-term API is still a dedicated instruction context passed to instruction bodies instead of `Wavefront&`, because a method named `cu()` returning a deliberately narrowed view remains a little surprising.

### 2. Consider making the Python test dependency available in the standard review environment

**Files:** `emulation/rocjitsu/lib/python/amdisa/tests/test_sema_lower.py:1`, `emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py:1`

This PR changes the generator, and CI is green, but I could not run the AMD ISA Python tests locally because `pytest` was absent from both the venv and system Python. This is not a PR code issue, but it does leave a local review gap for generator-heavy changes.

## Commentary

I did not find a code issue that should block this PR. The earlier concerns about title policy and stale unpushed follow-up commits are resolved, the current CI state is green, the C++ focused validation passed locally, and the static scans did not find remaining direct register-access bypasses in generated/shared AMDGPU instruction code.

The remaining risk is mostly blast radius: this PR intentionally refreshes a large generated ISA surface. The reviewable hand-written contract is now tight enough that the generated churn is understandable: instruction code uses `RegisterAccess`, privileged raw access is limited to VM/storage paths and the private operand backend, and the race/plugin path observes lane masks rather than scalarized lane ranges.
