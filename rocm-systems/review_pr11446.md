This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#11446](https://github.com/ROCm/rocm-systems/pull/11446)

## Tests

The Clang 23 `rocjitsu_tests` target built successfully; 104 focused C++ tests covering gfx1250 simulation, BF16 FMA environment handling, and BF16 overflow policy passed, as did all 28 packed-instruction generator tests and the changed-file pre-commit hooks. Full ten-ISA regeneration produced no diff, and `git diff --check` passed.

The current rocJITsu release, ASan/UBSan, TSan, and GCC UBSan corpus jobs pass. The gfx125X TheRock package job fails in `Fetch sources`, before the workflow patches in this repository, so it does not provide evidence of a regression in this change.

## Summary

This PR replaces the packed-BF16 add, multiply, and fused-multiply-add path that performed F32 arithmetic and then truncated the result. The generated CDNA5 callbacks now route those operations through small shared helpers that use the existing exact F32-source-to-BF16 primitive, force one round-to-nearest-even step, preserve input and output denormals independently of MODE, preserve a negative-zero product, and apply `FP16_OVFL` only when finite operands produce a result that rounds to BF16 infinity. Packed minimum-number and maximum-number now use the explicit RNE conversion as well; because these operations select an already representable BF16 operand, this does not introduce an additional ordinary-value rounding step.

The implementation keeps the policy in the shared floating-point layer and the generator remains the source of the emitted execution bodies. The runtime coverage distinguishes midpoint ties, a fused residual that would be lost by intermediate F32 rounding, positive and negative overflow, true infinity, signed zero, subnormals, independent packed halves, every MODE rounding encoding, both overflow settings, and inactive lanes. I found no actionable issue in the changed contracts or their coverage.

## Actionable items

None.

## Suggestions

None.

## Commentary

The exact helper is a good fit for BF16 operands: widening is exact, their product is exactly representable in F64, and the existing error-free sum retains the residual needed to choose the correct BF16 neighbor at a midpoint. The finite-input guard around overflow saturation also avoids incorrectly clamping infinities or NaNs supplied by the program.

The remaining qualification is architectural rather than a defect in this patch: the public CDNA5 machine-readable description identifies these operations but does not spell out all rounding, denormal, and exceptional-value details. The new behavior matches the compiler-facing RNE expectation and the reported Triton result, but a future physical-gfx1250 differential sweep would provide stronger confirmation for NaN payload selection and other underspecified exceptional cases.
