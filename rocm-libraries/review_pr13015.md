This is a review from an agent with an automatic prompt from the reviewer

> Superseded by the [audited review](review_pr13015_audit_20261006.md). The fractional-clamp finding below is withdrawn; the corrected branch retains gradient bounds and amax initialization. The original draft is preserved below.

**PR reviewed:** [ROCm/rocm-libraries#13015](https://github.com/ROCm/rocm-libraries/pull/13015)

**Reviewed head:** `396f1c5175913d0ddd19eb48d12e948ad6cad96c` (2026-10-06), relative to #13013. Public repository and head; existing reviews/comments were not consulted.

**Local review branch:** `review/pr13015-suggestions-20261006`, based on that head. `7cafd4076b0` bounds bias-gradient reductions; `5f453a7453bd` rejects fractional clamp bounds and initializes the optional amax result to NaN until a valid check completes.

## Tests

Built the submitted checker and passed its 48 self-tests on gfx1201/ROCm 7.1. The two new regressions fail before the corresponding fixes; all 50 tests pass on the final branch. The matmul header compiles in benchmark and GOOGLE_TEST modes; whitespace checks pass.

Real side-epilogue GEMMs were not run locally. The PR documents unavailable amaxD configurations and tracked reference/E-scale defects; direct helper tests do not replace those missing integration cases.

## Summary

The verifier folds integer scales into its projections, verifies E as another linear output, and uses verified E to check nonlinear activation output. It checks amaxD only when the stored result retains enough information, and bias gradients against input reductions. Resetting E, gradient output and amaxD before each launch prevents a skipped store from reusing an earlier result.

Keeping fast_check-only variants active where the legacy CPU reference is broken preserves useful coverage while those reference defects are tracked.

## Actionable items

### Bound bias-gradient accumulation separately from GEMM

In `projects/hipblaslt/clients/common/src/fast_check.cpp`, `fast_check_bias_gradient` (submitted line 1937) sums values into int64 without checking whether the GPU reduction is exact. The GEMM bound cannot provide that guarantee: if B is zero, its bound is zero even when a row of A is {2^24, 1, -2^24}. In f32, the BGRADA sum then depends on reduction order. The submitted helper accepts an exact sum of 1, and would call a legitimate differently ordered result wrong. Sufficiently large reductions can also overflow its int64 accumulator.

Commit `7cafd4076b0` independently bounds the absolute sum of each gradient vector before accumulating it, and refuses non-integer or inexact inputs with a configuration explanation. Its regression covers both gradient sources with a zero opposite operand. Existing small exact reductions still pass.

### Refuse fractional clamp bounds in the integer checker

In `fast_check_activation_device` in the same file (submitted line 1837), clamp bounds are applied as doubles before output rounding, while the kernel receives compute-type arguments. With an upper bound of 0.1 and scaleD=9, f32 clamp then multiplication produces a different value from rounding the double product once. The submitted verifier reports correct f32 arithmetic as an output mismatch, printing expected 0.9 and got 0.9.

Commit `5f453a7453bd` rejects non-integer clamp bounds in both matmul preflight (`clients/common/include/testing_matmul.hpp`, `fast_check_unsupported_reason`) and the direct helper, consistent with the integer-only contract. The regression reconstructs the two-stage f32 result and requires a configuration refusal. The optional amax value starts as NaN so an early refusal or copy failure cannot leave a stale numeric result.

## Suggestions

No additional feature expansion requested. Supporting arbitrary fractional activations would require modelling compute-type argument conversion and intermediate rounding; that is separate from this exact-integer path.

## Commentary

Direct arithmetic/device-helper tests plus small client epilogue cases are the appropriate levels. New tests use the existing pre_checkin suite. The capability remains opt-in, with explicit refusals where E or D loses the information needed to check activation/amax. Preserve the issue-linked, time-boxed known-bug entries and their independent fast_check-only coverage. The branch has the two commits above; no push or review post was made.
