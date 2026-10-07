> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#13019](https://github.com/ROCm/rocm-systems/pull/13019)

**Reviewed head and suggestion-branch base:** [`463cdbb5cb1f49da808041cfa9ffe2bc8f13c583`](https://github.com/ROCm/rocm-systems/commit/463cdbb5cb1f49da808041cfa9ffe2bc8f13c583)

**Suggestion branch:** [`review/pr13019-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr13019-suggestions), ending at [`e64dd9fbd9c4c9c2fd249fbaf892517cab5969c2`](https://github.com/newling/rocm-systems/commit/e64dd9fbd9c4c9c2fd249fbaf892517cab5969c2).

| Review item | Commit |
| --- | --- |
| Numerical coverage for inactive DS swizzle lanes | [`1835bb4898379d032e396faee495a264407883ae`](https://github.com/newling/rocm-systems/commit/1835bb4898379d032e396faee495a264407883ae) |
| Expose scalar-memory register offsets to dependency consumers | [`fcdf68925ba0ab41c33d5a8d55f7b8f7f35e6140`](https://github.com/newling/rocm-systems/commit/fcdf68925ba0ab41c33d5a8d55f7b8f7f35e6140) |
| Resolve scalar-buffer descriptor dependencies across register files | [`37fd06b4c1146e200173c4f0a911544bfc49dc9f`](https://github.com/newling/rocm-systems/commit/37fd06b4c1146e200173c4f0a911544bfc49dc9f) |
| Apply wave width to explicit special-register mask destinations | [`e64dd9fbd9c4c9c2fd249fbaf892517cab5969c2`](https://github.com/newling/rocm-systems/commit/e64dd9fbd9c4c9c2fd249fbaf892517cab5969c2) |

The published suggestion branch contains the commits in table order. Validation of the fixes refers to the complete stack. Source links below refer to the submitted head. This review assumes the instruction-issue approach will be retained and supplies concrete corrections. Existing GitHub reviews and discussions were not consulted.

## Tests

On the suggestion branch, Clang 23.1.0 Release test/CLI/shared-runtime builds, focused native memory-wait/XCNT/register-access/scalar-memory tests, Python generator/profile checks, changed-file pre-commit hooks, and the supplementary hipBLASLt CPU-reference checks all pass.

The scalar-offset and descriptor counterexamples below were first reproduced against submitted production code. The wave32 counterexample was reproduced after the two scalar fixes, in resolver code unchanged from the submitted head. Their reproducing cases are retained and expanded in `emulation/rocjitsu/tests/memory_wait_scoreboard_test.cpp`. On the suggestion branch, the principal regressions can be selected with:

```sh
"$BUILD_DIR/tests/rocjitsu_tests" --gtest_filter='MemoryWaitExecutionTest.ScalarMemoryRegisterOffsetIsCheckedBeforeAddressCalculation:MemoryWaitExecutionTest.ScalarBufferDescriptorChecksItsConsumedVccWords:MemoryWaitExecutionTest.ExplicitVccMaskDestinationUsesWaveWidth'
```

The [submitted-head rocjitsu CI](https://github.com/ROCm/rocm-systems/actions/runs/37659234003) passes Release, ASan/UBSan, GCC UBSan, and TSan. Repository-wide checks still include pending hardware jobs and the previously observed policy-bot failure. The local fix stack was validated in Release; sanitizer CI results apply to the submitted head. The application sample below uses gfx942 and one simulator worker, so CDNA5 replay-source behavior and other architectures are covered by focused native tests rather than these application runs.

## Summary

The PR moves logical register-readiness checks from individual register accesses into instruction issue. This lets the simulator reject irrelevant work early and check an instruction before publishing asynchronous matrix execution. The ownership boundary is useful: the issuing thread maintains the wait scoreboard while execution helpers perform the numerical work.

The necessary contract is that the decoded operands and dynamic planning describe every register the instruction actually consumes or overwrites, with the right physical identity and width. The review found concrete gaps in that contract that can be corrected within the proposed design. The changes below retain the fast path and repair the shared operand or register-resolution rules on which it depends.

## Actionable items

### Include the independent scalar-memory offset register

Locations: [`_generator.py:13812`](https://github.com/ROCm/rocm-systems/blob/463cdbb5cb1f49da808041cfa9ffe2bc8f13c583/emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py#L13812), [`rdna3/addr_calc.cpp:52`](https://github.com/ROCm/rocm-systems/blob/463cdbb5cb1f49da808041cfa9ffe2bc8f13c583/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/rdna3/addr_calc.cpp#L52), and [`cdna5/addr_calc.cpp:199`](https://github.com/ROCm/rocm-systems/blob/463cdbb5cb1f49da808041cfa9ffe2bc8f13c583/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/cdna5/addr_calc.cpp#L199).

For RDNA/CDNA5, generated `make_smem_offset` always describes the immediate field, although address execution also reads the independent `soffset` register. For example, a scalar load can leave `s4` pending, and the next scalar load can use `s4` to calculate its address without the required wait. The instruction checker sees only the immediate and misses the dependency. The initial CDNA5 probe reported zero warnings instead of one; the numerical address and waited control were correct. The same missing source also escapes XCNT protection against overwriting a register needed for replay.

Expose `OPR_SMEM_OFFSET` through the existing operand when a register is selected, rendering any simultaneous immediate as an `offset:` modifier. Preserve the immediate-only representation for the architecture's no-offset selectors. This repairs the decoded operand model for all its consumers, without adding a second offset operand or special-casing this dependency only in the wait checker.

**Implemented:** [`fcdf68925ba0ab41c33d5a8d55f7b8f7f35e6140`](https://github.com/newling/rocm-systems/commit/fcdf68925ba0ab41c33d5a8d55f7b8f7f35e6140) changes the generator/profile documentation and regenerates the affected ISA files. `ScalarMemoryRegisterOffsetIsCheckedBeforeAddressCalculation` checks register/null offsets, combined immediates, waited/unwaited consumers, numerical addresses, and disassembly across CDNA4 and representative RDNA/CDNA5 targets. `ScalarRegisterOffsetOverwriteNeedsTranslationOrCompletionWait` checks replay protection for ordinary and special scalar selectors with X/completion-wait controls.

### Resolve the scalar-buffer descriptor as the words execution consumes

Locations: [`_generator.py:10637`](https://github.com/ROCm/rocm-systems/blob/463cdbb5cb1f49da808041cfa9ffe2bc8f13c583/emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py#L10637), [`memory_wait_scoreboard.cpp:226`](https://github.com/ROCm/rocm-systems/blob/463cdbb5cb1f49da808041cfa9ffe2bc8f13c583/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_wait_scoreboard.cpp#L226), and [`cdna5/addr_calc.cpp:206`](https://github.com/ROCm/rocm-systems/blob/463cdbb5cb1f49da808041cfa9ffe2bc8f13c583/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/cdna5/addr_calc.cpp#L206).

Scalar-buffer loads do not identify their descriptor through `RegisterModifiers::buffer_resource`, so they fall through to the generic contiguous-SGPR source path. A valid descriptor starting at scalar selector 104 uses `s104`, `s105`, `VCC_LO`, and, on CDNA5, `VCC_HI`. Execution resolves those selectors individually, but the checker looks for an SGPR range and misses pending VCC words. The submitted-head CDNA5 probe missed both consumed VCC dependencies while address calculation and waited controls passed. XCNT replay-source registration has the corresponding omission.

Annotate scalar-buffer descriptor operands and share consumed-word resolution between instruction checking and replay-source registration. Match the existing execution contracts: vector descriptors require complete backing; scalar loads validate the base pair, then consume subsequent words independently. Older scalar-buffer implementations consume three words, while CDNA5 consumes four. Checking an unused fourth word would introduce a false warning, and rejecting an entire partially backed scalar descriptor would lose valid source dependencies.

**Implemented:** [`37fd06b4c1146e200173c4f0a911544bfc49dc9f`](https://github.com/newling/rocm-systems/commit/37fd06b4c1146e200173c4f0a911544bfc49dc9f) adds the metadata and a non-observing `RegisterAccess::buffer_resource_registers` helper, replacing the duplicated descriptor loops in the two diagnostic paths. The committed tests cover VCC aliases, consumed versus unused descriptor words, backing boundaries, replay protection, and wait controls; numerical address and load-mask checks independently verify the execution result.

### Let explicit VCC destinations reach the wave-width adjustment

Location: [`memory_wait_scoreboard.cpp:333`](https://github.com/ROCm/rocm-systems/blob/463cdbb5cb1f49da808041cfa9ffe2bc8f13c583/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_wait_scoreboard.cpp#L333).

The `resolve` lambda resolves special selectors twice. Its second resolution returns immediately, skipping the subsequent adjustment for wave-sized vector mask results. A wave32 VOP3 comparison with explicit destination VCC therefore appears to overwrite both VCC halves, although execution writes only `VCC_LO` and preserves `VCC_HI`.

With a pending scalar load into `VCC_HI`, `ExplicitVccMaskDestinationUsesWaveWidth` reports one warning instead of zero on both RDNA3 and RDNA4. The numerical check confirms that the high-half sentinel is preserved. Wave64, low-half, and waited controls distinguish the false warning from a real dependency.

**Implemented:** [`e64dd9fbd9c4c9c2fd249fbaf892517cab5969c2`](https://github.com/newling/rocm-systems/commit/e64dd9fbd9c4c9c2fd249fbaf892517cab5969c2) removes the redundant four-line early-return block, allowing the already-resolved register to reach the existing width adjustment, and commits that regression.

## Suggestions

### Retain independent numerical coverage for DS swizzle lanes

Locations: [`_generator.py:7745`](https://github.com/ROCm/rocm-systems/blob/463cdbb5cb1f49da808041cfa9ffe2bc8f13c583/emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py#L7745) and [`instruction_execution_harness_test.cpp:7223`](https://github.com/ROCm/rocm-systems/blob/463cdbb5cb1f49da808041cfa9ffe2bc8f13c583/emulation/rocjitsu/tests/instruction_execution_harness_test.cpp#L7223).

Independent numerical coverage remains useful because access planning and execution can agree while sharing an incorrect numerical rule. Commit [`1835bb4898379d032e396faee495a264407883ae`](https://github.com/newling/rocm-systems/commit/1835bb4898379d032e396faee495a264407883ae) independently checks zero results for inactive sources, preserved inactive destinations, and aliased operands across CDNA4, RDNA3, RDNA4, and CDNA5. It passes on submitted production code and is a coverage addition. A separate physical gfx1201 probe returned `2` for an active lane-1 source and `0` when only destination lane 0 was active, supporting the zero result on RDNA4. Hardware evidence is limited to gfx1201; the exact probe is retained below.

## Commentary

Plugin reuse should center on a shared description of physical register identities, read/write roles, and lane/byte masks. The operand repair benefits decoded def/use consumers, and the descriptor helper demonstrates a bounded way to share resolution without emitting execution observations. A later plugin migration should compare the union of described effects with the existing accessor callbacks before relying on it.

The current wait checker filters work using its own pending state, so its output is not a complete access list that another plugin can consume directly. `RegisterAccess` still supplies register storage, values, and masked writes. Race detection additionally needs routed memory and synchronization events. These fixes do not require a broader plugin redesign.

The supplementary application experiment used matching hipBLASLt client/library assets from [rocm-libraries CI run 36631153514](https://github.com/ROCm/rocm-libraries/actions/runs/36631153514), the suggestion branch's shared runtime, simulated gfx942, `trig_float` input initialization, and `--verify`. Each workload ran with `memory_wait_diagnostics` and `xcnt_diagnostics` both `off`, then both `warn`; XCNT checking is architecture-gated and is inactive on gfx942. No execution plugins were enabled.

| Workload, M × N × K | Additional coverage | Selected solution | Reported norm error in both modes |
| --- | --- | --- | --- |
| FP16, 128 × 128 × 256 | Aligned tiles | 244253 | `1.6408e-05` |
| FP16, 67 × 71 × 131 | Partial tiles and K tail | 243273 | `3.76808e-06` |
| BF16, 96 × 80 × 192 | Transposed A, beta 0.5 | 82640 | `9.39726e-05` |
| FP32, 33 × 35 × 65 | Transposed B, two batches, beta 1 | 295163 | `4.6192e-07` |

All eight processes succeeded, selected the same algorithm within each pair, produced finite norm errors within the reported tolerances, and emitted no rocjitsu warnings. These runs provide application robustness evidence for the fixed branch. They do not establish that the submitted PR causes a particular speedup, exhaust the library's algorithms, or replace the focused missing-wait counterexamples.

The suggestion branch [`review/pr13019-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr13019-suggestions) retains all four mapped commits. Every concrete finding in this review has an implemented and tested fix; the broader plugin migration and exhaustive application sweep were left outside this review's scope.

<details>
<summary>Hardware probe source and reproduction</summary>

Save this as `ds_swizzle_inactive.hip`. It was compiled for and run on physical gfx1201:

```cpp
#include <hip/hip_runtime.h>

#include <cstdio>

__global__ void probe(unsigned *output) {
  const unsigned source = threadIdx.x + 1;
  unsigned active_result;
  asm volatile("ds_swizzle_b32 %0, %1 offset:0x8055\n\t"
               "s_wait_dscnt 0"
               : "=&v"(active_result)
               : "v"(source)
               : "memory");

  unsigned saved_exec, inactive_result;
  asm volatile("s_mov_b32 %0, exec_lo\n\t"
               "s_mov_b32 exec_lo, 1\n\t"
               "ds_swizzle_b32 %1, %2 offset:0x8055\n\t"
               "s_wait_dscnt 0\n\t"
               "s_mov_b32 exec_lo, %0"
               : "=&s"(saved_exec), "=&v"(inactive_result)
               : "v"(source)
               : "memory");
  if (threadIdx.x == 0) {
    output[0] = active_result;
    output[1] = inactive_result;
  }
}

int main() {
  unsigned *device = nullptr;
  unsigned output[2]{};
  auto check = [](hipError_t status) {
    if (status != hipSuccess)
      std::fprintf(stderr, "%s\n", hipGetErrorString(status));
    return status == hipSuccess;
  };
  if (!check(hipMalloc(&device, sizeof(output))))
    return 1;
  probe<<<1, 32>>>(device);
  if (!check(hipGetLastError()) ||
      !check(hipMemcpy(output, device, sizeof(output), hipMemcpyDeviceToHost)))
    return 1;
  if (!check(hipFree(device)))
    return 1;
  std::printf("active source: %u; inactive source: %u\n", output[0], output[1]);
  return output[0] == 2 && output[1] == 0 ? 0 : 2;
}
```

With `$ROCM_PATH`, `$SRC_DIR`, and `$BUILD_DIR` set to the ROCm installation and existing source/build directories:

```sh
"$ROCM_PATH/lib/llvm/bin/amdclang++" -x hip --offload-arch=gfx1201 -O2 \
  "$SRC_DIR/ds_swizzle_inactive.hip" -o "$BUILD_DIR/ds_swizzle_inactive"
"$BUILD_DIR/ds_swizzle_inactive"
```

Observed output, with exit status zero:

```text
active source: 2; inactive source: 0
```

</details>
