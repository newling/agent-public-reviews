This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#13705](https://github.com/ROCm/rocm-systems/pull/13705)

**Reviewed head:** [`3c71219ee8e043155f3954824b7f55a498c02e5e`](https://github.com/ROCm/rocm-systems/commit/3c71219ee8e043155f3954824b7f55a498c02e5e).

**Suggestion branch:** [review/pr13705-suggestions](https://github.com/newling/rocm-systems/tree/review/pr13705-suggestions), based on the reviewed head. The commits are independent and can be inspected or cherry-picked separately:

| Commit | Review item | Included regression |
|---|---|---|
| [a0de7b3a484](https://github.com/newling/rocm-systems/commit/a0de7b3a4846032c3a36c1b261ad6a9f46aeceb6) | Validate the tensor DMA barrier cell | `Gfx1250ExecutionTest.TensorDmaBarrierMustFitOwnedLds` |
| [60fdf5b4865](https://github.com/newling/rocm-systems/commit/60fdf5b486555a62980e70ed3eb54567bf0e8aa6) | Decode each floating DOT4 input with its declared format | `Rdna4DotDppTest.FloatingDot4UsesEachOperandFormat` and generator format cases |

## Tests

Clang 23.1 Release build and focused native/Python checks pass; both new counterexamples fail on submitted production code and pass with the corresponding fixes. All ten ISA families regenerate to the suggestion branch's checked-in output after formatting; changed-file hooks and whitespace checks pass.

The submitted head passed its existing focused execution, tensor DMA, conversion, buffer-format, transpose-diagnostic and DPP tests. Added regressions then demonstrated the two issues below without changing production code. The suggestion branch also passes queue-owner failure routing, engine failure propagation, async register-lifetime and ownership checks, representative instruction execution harnesses, and the remaining changed execution tests. Architecture-specific diagnostic skips cover parameters for which the test deliberately does not apply.

Rocjitsu CI passes Release, ASan/UBSan, TSan and GCC UBSan. Repository-wide hardware sanity and policy jobs are failing; these are not local rocjitsu failures, and their causes were not established by this review. No fresh hardware workload, full HIP corpus, or local sanitizer rebuild was run; existing sanitizer CI supplies broader coverage while local checks exercise the changed contracts and concrete counterexamples. The PR head was rechecked and remained unchanged at completion.

## Summary

The change brings several malformed-guest cases into the existing wave-owned failure path, including legacy unimplemented callbacks and unsupported operands resolved before instruction execution. It records the issuing PC for helper failures and joins outstanding matrix work before terminal memory faults can release wave storage. Tensor DMA preparation now proves reachable transfer ranges before allocating and walking element metadata, while integer conversions avoid undefined host casts and integer min/max keeps integer comparisons.

The tensor DMA proof distinguishes reachable tile addresses from the entire tensor extent, which preserves small valid transfers in large tensors. The controlled async tests are also useful: they establish that failure publication waits for register users to finish instead of depending on helper timing. The two independent additions for CDNA4 transpose diagnostics and RDNA4 floating DOT DPP support have targeted decode and execution coverage. Two concrete gaps remain in the barrier completion range and floating DOT4 numeric coverage.

## Actionable items

### Validate the tensor DMA barrier cell before materialization

**Location:** [`tensor_dma.h:479–486`](https://github.com/ROCm/rocm-systems/blob/3c71219ee8e043155f3954824b7f55a498c02e5e/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h#L479), `validate_materialization_address_ranges`; completion uses `arrive_atomic_barrier` in the same file.

The new range proof checks the transfer destinations against the wave's LDS allocation, but it never checks `atomic_barrier_addr`. Completion computes `wf.lds_base() + desc.atomic_barrier_addr` and updates an eight-byte cell. A valid one-element transfer with a 256-byte allocation and barrier offset 256 passes preparation and changes the next allocation's barrier word. An offset beyond physical LDS also reports success after the LDS helper drops the write. The early return for zero transfer elements likewise permits barrier-only completion without an address check.

Check the entire eight-byte cell against both the wave allocation and physical LDS before the zero-element return or any transfer work. Use checked address/end arithmetic so failure occurs before copying or publishing completion. This extends the same allocation boundary the PR already enforces for transfer data.

**Implemented in [a0de7b3a484](https://github.com/newling/rocm-systems/commit/a0de7b3a4846032c3a36c1b261ad6a9f46aeceb6).** The regression covers decoded loads and stores with a barrier in the next allocation and beyond physical LDS, verifies that rejection preserves global/LDS data and the neighboring cell, and retains a cell ending exactly at the allocation boundary as a valid control. It also checks active zero-element barrier completion. The original decoded cases fail on submitted production code and pass with the fix.

### Decode each floating DOT4 input with its declared format

**Location:** [`rdna4/vop3p_exec.cpp:1479–1480`](https://github.com/ROCm/rocm-systems/blob/3c71219ee8e043155f3954824b7f55a498c02e5e/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/generated/rdna4/vop3p_exec.cpp#L1479), the newly generated floating DOT4 modifier bodies; [`rdna4_dot_dpp_test.cpp:88`](https://github.com/ROCm/rocm-systems/blob/3c71219ee8e043155f3954824b7f55a498c02e5e/emulation/rocjitsu/tests/rdna4_dot_dpp_test.cpp#L88).

The newly enabled FP8/BF8, BF8/FP8 and BF8/BF8 DPP bodies use `fp8_e4m3_to_f32` for both sources. BF8 uses E5M2. For example, packed `0x38383838` represents four FP8 ones and `0x3c3c3c3c` represents four BF8 ones. With an accumulator of 0.5, FP8/BF8 should produce 4.5; submitted DPP16 and DPP8 execution produce 6.5. BF8/BF8 produces 9.5. The ordinary path already shares this error, so the PR's comparison against unpermuted execution passes while both outputs are numerically wrong.

Preserve each input format at the generator boundary and select its corresponding decode helper. Regenerate the ordinary and modifier bodies together, then add independent numeric expectations rather than using the ordinary path as the sole oracle. The in-tree RDNA4 XML explicitly declares the two packed operand formats, so this is a bounded format-selection correction.

**Implemented in [60fdf5b4865](https://github.com/newling/rocm-systems/commit/60fdf5b486555a62980e70ed3eb54567bf0e8aa6).** The generator selects each format from the instruction mnemonic; generated BF8 source reads use the existing `bf8_e5m2_to_f32` helper. Native golden-result coverage checks all four format pairs in ordinary, DPP16 and DPP8 forms with scalar forcing enabled and disabled; generator cases pin both source helper selections. The new native regression fails on submitted production code and passes with the fix. Full ISA regeneration matches the resulting checked-in sources after formatting.

## Suggestions

No additional suggestions beyond the regressions included with the two fixes.

## Commentary

The async failure translation intentionally catches `UnimplementedInst`; other host failures continue to propagate as documented by `execute_instruction`. This review does not establish complete containment for every arbitrary instruction stream. The shared pool/window ownership and terminal-fault draining paths were checked, including direct downstream queue notification, and no additional reproducible issue was found there.

The eager tensor DMA element cap is explicitly a simulator resource limit. Its separate check preserves legal overlapping iteration destinations, while its diagnostic makes the limit visible. This review does not propose changing that resource policy.

Both actionable items have complete local fixes and retained regressions. No implementation was omitted. [review/pr13705-suggestions](https://github.com/newling/rocm-systems/tree/review/pr13705-suggestions) contains [a0de7b3a484](https://github.com/newling/rocm-systems/commit/a0de7b3a4846032c3a36c1b261ad6a9f46aeceb6) and [60fdf5b4865](https://github.com/newling/rocm-systems/commit/60fdf5b486555a62980e70ed3eb54567bf0e8aa6) above the reviewed head; the branch and commits are published in the linked fork.
