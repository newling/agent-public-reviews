This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#10997](https://github.com/ROCm/rocm-systems/pull/10997)

**Review scope:** Combined architectural review of the author's 16 ROCm/rocm-systems PRs opened from August 14 through September 2, 2026, with #10997 as the focal PR and #11131 as the cumulative tip of the open gfx1251 stack.

## Tests

The cumulative #11131 stack built successfully as the full `rocjitsu_tests` target. All 74 tests whose names contain `Gfx1251` passed, including target gating, packed U64 and FP64 execution, F64 WMMA, SETREG behavior, code-object identity, DBT identity/refusal behavior, and all nine end-to-end simulator dispatch cases. Another 18 focused tests covering widened integer arithmetic, gfx1250 SETREG execution and dataflow, checkpoint restoration, and shared WMMA register observation passed. `git diff --check` passed across the open stack.

The focused Python generator tests were not run because `pytest` is absent from the review environment and no dependency was installed. A direct attempt to compile an existing HIP kernel with the installed `amdclang++ --offload-arch=gfx1251` failed with `invalid target ID 'gfx1251'`, so compiler-produced gfx1251 coverage requires a newer toolchain than the one available in this environment.

The current #10997, #11124, and cumulative #11131 CI runs are green. The only failing build jobs on #10871 and #11125 failed in their `Fetch sources` step; the same cumulative changes subsequently passed those package builds on child PRs. PR #10833's test and package jobs pass, but its repository-policy job fails.

## Summary

The principal body of work is a staged functional bring-up of gfx1251 in rocJITsu. The series updates the public machine-readable ISA source, adds a validated mechanism for auditable target-specific ISA additions, distinguishes gfx1250 and gfx1251 legality within the shared CDNA5 architecture, implements the nine public gfx1251-only instructions, models their target-specific SETREG difference, and finally enables a synthetic gfx1251 simulator configuration.

PR #10997 is the packed-FP64 fused-multiply-add slice. It gives `V_PK_FMA_F64` a generated execution callback that evaluates both F64 elements through the existing MODE-aware fused primitive, applies independent low/high source modifiers and clamp, observes EXEC, snapshots inputs before overlapping destination writes, and resolves tuples through physical VGPR indices so an aligned tuple beginning at v254 may cross the encoded v0-v255 window. Its tests cover public source forms, fused-versus-unfused results, register boundaries, overlap, modifiers, rounding, denormals, exceptional values, and invalid layouts.

The overall design is coherent: target differences are represented as immutable capabilities rather than a copied CDNA5 decoder; incomplete execution remains fail-closed until the final stack change; and public LLVM encodings plus checked-in provenance are used where the machine-readable snapshot lacks gfx1251-specific material. The cumulative end-to-end tests prove that hand-constructed gfx1251 ELFs travel through config loading, AQL dispatch, the command processor, decode and execution, and simulated memory. I found no combined-stack correctness issue that should block the incremental PRs.

The main residual qualification is also stated honestly in the series: the source-derived F64 WMMA mapping, floating-point corner behavior, and SETREG semantics have not been compared with physical gfx1251 hardware. The final result is functional simulation, not timing or cycle fidelity.

## Actionable items

### 1. Resolve the repository-policy failure on PR #10833

**Location:** PR #10833 description

The `therock-pr-bot` policy check is currently the only failing check on #10833. Its description has no issue-tracking section or recognized issue/ticket reference. Add the appropriate tracking reference, or otherwise resolve the policy requirement, before merging the base of the open execution stack.

## Suggestions

### 1. Add a compiler-produced gfx1251 HIP integration fixture

**Files:**

- `emulation/rocjitsu/tests/config_test.cpp:1236`
- `emulation/rocjitsu/tests/kernels/`
- `emulation/rocjitsu/cmake/rj_add_device_kernel.cmake:21`

The #11131 end-to-end tests are strong at the runtime boundary, but they construct a minimal code object from instruction words copied from public LLVM MC tests. They therefore do not cover Clang/HIP compilation, offload bundling, code-object selection, or the compiler's operand allocation around the new instructions.

When CI has an `amdclang++` that recognizes gfx1251, add a small HIP kernel compiled with `--offload-arch=gfx1251`, ideally using inline assembly for one packed arithmetic operation and checking exact output through the simulator. The existing `cvt_pk_bf16_f32.hip` fixture and `rj_add_device_kernel()` helper provide a close pattern. If mnemonic support lags target support, an inline `.inst` form can still exercise compiler-produced ELF metadata and the complete loading path.

Keep this conditional on a positive compiler capability probe. The toolchain used for this review rejects gfx1251 as a target, so making it unconditional would reduce portability without testing the intended path.

### 2. Pin plugin-visible register regions for the newly enabled wide operations

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:3774`
- `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:5314`
- `emulation/rocjitsu/tests/execution_plugin_test.cpp:3309`

The F64 WMMA path uses the established region API, and the packed operations route their physical-register accesses through `RegisterAccess`, so the implementation appears to preserve instrumentation. The existing plugin tests cover generic Wave32 WMMA regions but not the new four-register F64 inputs, 16-register F64 accumulator/destination, packed tuple spanning v254-v257, or partial EXEC write masks.

Now that #11131 enables normal gfx1251 execution, add a decoded gfx1251 plugin test that pins these exact read/write regions. This would protect race detection and other instrumentation consumers from a future arithmetic implementation that remains numerically correct while bypassing or under-reporting register accesses.

### 3. Explore gfx1251 DBT execution on available hardware

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/dbt/binary_translator.cpp:101`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/dbt/binary_translator.cpp:530`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/dbt/semantic/`
- `emulation/rocjitsu/docs/rocjitsu_dbt_guest.md`

rocJITsu's DBT guest mode can already expose one GPU identity to an unmodified application, translate its code objects, and execute the result on a real host GPU. Current cross-architecture profiles accept CDNA4 input and target CDNA3, RDNA3, or RDNA4; the CDNA5 path is limited to gfx1250 revision legalization. This stack correctly preserves gfx1251 decoder identity and explicitly rejects gfx1250/gfx1251 cross-target copying because their legality and SETREG contracts differ.

A separate follow-up could turn that safe refusal into an explicit gfx1251-to-gfx1250 or gfx1251-to-gfx942 translation profile. Start with one packed-U64 instruction whose semantics can be expanded into established host instructions, then extend the profile instruction by instruction. Packed FP64 is likely tractable; F64 WMMA is the difficult boundary because lowering must preserve lane mapping, accumulator layout, rounding, denormal, and exceptional-value behavior while managing register pressure.

This would permit compiler-produced gfx1251 programs to run through the existing hardware-backed DBT path and would provide a useful numerical cross-check against simulation. It would not validate native gfx1251 encodings, hazards, or timing, because the hardware would execute translated sequences rather than the gfx1251 instructions themselves.

## Commentary

### Gfx1251 bring-up history

| PR | Status at review | Role in the series |
| --- | --- | --- |
| [#10499](https://github.com/ROCm/rocm-systems/pull/10499) | Merged | Updates the public machine-readable ISA snapshot and parser support for newer schemas. |
| [#10431](https://github.com/ROCm/rocm-systems/pull/10431) | Merged | Aligns gfx1250 configuration and generation with the public CDNA5 ISA source. |
| [#10587](https://github.com/ROCm/rocm-systems/pull/10587) | Merged | Adds validated, provenance-preserving ISA additions instead of editing the public base XML. |
| [#10661](https://github.com/ROCm/rocm-systems/pull/10661) | Merged | Introduces concrete gfx1251 identity, target feature masks, nine model-only instructions, DPP legality, and fail-closed execution gating. |
| [#10665](https://github.com/ROCm/rocm-systems/pull/10665) | Merged | Implements `V_PK_LSHL_ADD_U64`, establishing the packed-U64 generation and execution path. |
| [#10850](https://github.com/ROCm/rocm-systems/pull/10850) | Merged | Stabilizes the public GPU-target enum ABI so adding targets does not renumber `INVALID`. |
| [#10833](https://github.com/ROCm/rocm-systems/pull/10833) | Open | Implements packed U64 add and subtract with modifiers, clamp, overlap safety, and fail-closed operand validation. |
| [#10871](https://github.com/ROCm/rocm-systems/pull/10871) | Open | Implements packed F64 add, multiply, minimum-number, and maximum-number with MODE-aware behavior. |
| [#10997](https://github.com/ROCm/rocm-systems/pull/10997) | Open | Implements packed F64 fused multiply-add. |
| [#11124](https://github.com/ROCm/rocm-systems/pull/11124) | Open | Implements wave32 `V_WMMA_F64_16X16X4_F64` execution while keeping normal gfx1251 simulation disabled. |
| [#11125](https://github.com/ROCm/rocm-systems/pull/11125) | Draft | Models the gfx1250/gfx1251 SETREG and VGPR-MSB difference across execution, checkpointing, analysis, DBT, and fuzzing. |
| [#11131](https://github.com/ROCm/rocm-systems/pull/11131) | Draft | Enables functional gfx1251 simulation and dispatches all nine new instructions through a synthetic one-CU configuration. |

The open execution work is intentionally stacked in this order:

```text
#10833 -> #10871 -> #10997 -> #11124 -> #11125 -> #11131
```

That organization makes the distinction between decode support, direct instruction execution, target-specific machine state, and complete simulator enablement unusually clear.

### Detailed assessment of the open stack

| PR | Highest-risk contract | Assessment |
| --- | --- | --- |
| [#10833](https://github.com/ROCm/rocm-systems/pull/10833) | Packed U64 modifier ordering, saturation versus modulo arithmetic, and legality of wide source tuples | The signed 128-bit intermediate is sufficient for every combination of two optionally negated U64 inputs, including the fallback implementation on toolchains without native `__int128`. Active-lane results are staged before writes where validation can fail, and the tests cover both native and fallback widened arithmetic. No code issue found; the repository-policy failure remains. |
| [#10871](https://github.com/ROCm/rocm-systems/pull/10871) | Host implementation of architectural F64 rounding, denormals, NaNs, and signed-zero min/max behavior | The shared helper contains the policy in one place, restores the host floating-point environment, and directly tests all four rounding and denormal modes plus exceptional inputs. Later commits deliberately canonicalize the both-NaN result instead of depending on host payload selection. No code issue found; hardware differential evidence remains absent. |
| [#10997](https://github.com/ROCm/rocm-systems/pull/10997) | Fused rather than decomposed arithmetic, destructive overlap, and tuples crossing the encoded VGPR window | The callback uses `fma_f64`, snapshots all three operands before writing, resolves the high packed element from the physical VGPR base, and directly distinguishes fused from unfused output. The boundary tests exercise a tuple beginning at v254. No issue found. |
| [#11124](https://github.com/ROCm/rocm-systems/pull/11124) | Source-derived F64 WMMA lane/register mapping and 16-register accumulator ownership | The fixed-shape helper stages A, B, and C, uses four mode-aware fused reductions per output, and masks only the final writes by EXEC. Mapping, overlap, modifiers, tuple bounds, wave-size rejection, FP modes, and exceptional values have direct tests. No correctness issue found, but physical gfx1251 qualification and the plugin-observation suggestion above remain. |
| [#11125](https://github.com/ROCm/rocm-systems/pull/11125) | A one-instruction adjacency hazard that must agree across execution, checkpoints, CFG joins, liveness, indirect-branch analysis, DBT, and fuzz replay | The capability is attached to the concrete GPU target rather than CDNA5 globally. Runtime consumption, trap bypass, checkpoint persistence, conservative CFG joins, and concrete-target DBT decoding are all represented and tested. Cross-target CDNA5 DBT fails closed. No issue found in the reviewed paths. |
| [#11131](https://github.com/ROCm/rocm-systems/pull/11131) | Turning a previously model-only target into an executable simulator target | The change is intentionally small at the capability boundary and pairs it with a synthetic configuration, target/version mismatch tests, all-nine callback checks, and real AQL-to-memory execution. The remaining gap is outside its manually constructed ELF boundary: no compiler-produced gfx1251 HIP object is exercised. |

### Other recent rocJITsu work

| PR | Status at review | Scope |
| --- | --- | --- |
| [#10186](https://github.com/ROCm/rocm-systems/pull/10186) | Merged | Corrects the documented execution-mode name from `cycle` to `clocked`. |
| [#10274](https://github.com/ROCm/rocm-systems/pull/10274) | Merged | Aligns MI350X topology with captured KFD data, including physical versus active CU counts. |
| [#10449](https://github.com/ROCm/rocm-systems/pull/10449) | Merged | Requires explicit SDMA queue counts instead of silently materializing a default topology. |
| [#10511](https://github.com/ROCm/rocm-systems/pull/10511) | Closed unmerged | Proposed a narrowly scoped suppression for an external ROCr TSan report in HIP memcpy tests. |

Across both groups, the consistent theme is making rocJITsu's architectural claims explicit and testable: topology comes from captures, target features come from traceable public sources, unsupported combinations fail closed, and execution is enabled only after its modeled surface has direct coverage.
