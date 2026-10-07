This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12876](https://github.com/ROCm/rocm-libraries/pull/12876)

**Reviewed head and suggestion base:** `d31e13119312f69634d35684200860e0ef496986`

**Review mode:** Follow-up on the prior requested repair, with a fresh source and contract review of this PR. Later PRs in the stack are outside this review.

**Publication check, 2026-10-07:** The PR rebased to [`6b4c50e0513`](https://github.com/ROCm/rocm-libraries/commit/6b4c50e0513cc12b7097c5d542a7a03e65c525a1). Both files changed by the suggestion are byte-identical to the reviewed head, and the fix applies cleanly. The newer base was not rebuilt; the test and CI results below refer to the recorded reviewed head.

**Published suggestion branch:** [review/pr12876-followup-20261007](https://github.com/newling/rocm-libraries/tree/review/pr12876-followup-20261007)

| Published commit | Review item |
| --- | --- |
| [`fe4edad3077`](https://github.com/newling/rocm-libraries/commit/fe4edad30770f4227de812d0426076545680013c) | Correct real conjugate-transpose mapping and add the caller regression. |

## Tests

On gfx1201 with ROCm 7.1, the submitted host/device helper tests passed 30/30; the new caller regression passed 8/18 on the submitted caller and 18/18 with the fix, using both CPU `unit_check` and `fast_check`. The matching host/client build, four-kernel device subset, test-data generation and `git diff --check` succeeded.

The ten submitted-caller failures are explained and reproduced in the actionable item below. Both executables use the same library, kernels and test data; their caller headers differ only in the two transpose assignments. The submitted header was checked against the recorded PR head.

Local setup required matching device metadata: the installed ROCm 7.1 library first failed to load the mapping, and an overlay then failed in `PlaceholderLibrary::loadPlaceholderLibrary` before reaching GEMM. A four-solution f32 subset generated from this PR's gfx1201 logic resolved that incompatibility. Clang 20 also rejects the generator's newer `-Xclangas` spelling; a local compiler wrapper forwarded the requested `-target-feature +real-true16` directly to `cc1as`. Kernel tuning and the requested target feature were retained. These runs cover the caller with a small kernel subset, not the complete solution catalog. Root pre-commit was invoked but skipped these files under its configured exclusions.

CI at 2026-10-07 19:39 UTC still referred to the reviewed head: 27 successful, 27 skipped, two running and five pending checks, with no failures. [hipBLASLt gfx90a ASAN](https://github.com/ROCm/rocm-libraries/actions/runs/37670721950) and the gfx950 Math Libs stage passed. Linux gfx942 and Windows gfx110X stages were running; Math CI gates remained pending.

## Summary

This PR adds opt-in verification for large integer-exact GEMMs. It computes expected modular fingerprints from the inputs, checks each solution's output on the GPU, and combines that with sentinels and finite padding poison. Keeping input fingerprints separate from per-solution checks is useful, and direct corruption tests exercise failures that simple checksums would miss.

The previously requested empty-output repair is incorporated. Zero M, N or batch count now requires no operand access or device work, while prior validation errors are preserved. The submitted [`empty_results_launch_nothing` regression](https://github.com/ROCm/rocm-libraries/blob/d31e13119312f69634d35684200860e0ef496986/projects/hipblaslt/clients/tests/src/fast_check_gtest.cpp#L1007) passes. No part of that requested repair remains outstanding.

## Actionable items

### Treat conjugate transpose as transpose for real inputs

At [`projects/hipblaslt/clients/common/include/testing_matmul.hpp:5690–5691`](https://github.com/ROCm/rocm-libraries/blob/d31e13119312f69634d35684200860e0ef496986/projects/hipblaslt/clients/common/include/testing_matmul.hpp#L5690), `transA == HIPBLAS_OP_T` and the corresponding B expression map `HIPBLAS_OP_C` to false. Real-valued conjugate transpose has the same layout and values as transpose. The caller's stored-dimension calculations already handle it that way, and the library supports it.

The verifier consequently interprets valid compact input copies with the wrong layout and rejects correct GEMMs. Rectangular inputs can also make it index past the host allocation: with conjugate-transposed A, M=13 and K=17, each compact batch contains 221 elements, but the incorrect untransposed view can request offset `12 + 16 * 17 = 284`. This also crosses the end of the allocation for the final batch.

Set both flags using `transA != HIPBLAS_OP_N` and `transB != HIPBLAS_OP_N`, consistent with the existing dimension logic. Commit [`fe4edad3077`](https://github.com/newling/rocm-libraries/commit/fe4edad30770f4227de812d0426076545680013c) implements that change and adds [`matmul_fast_check_conjugate_transpose` at `projects/hipblaslt/clients/tests/data/matmul_gtest.yaml:3152`](https://github.com/newling/rocm-libraries/blob/fe4edad30770f4227de812d0426076545680013c/projects/hipblaslt/clients/tests/data/matmul_gtest.yaml#L3152). It covers all N/T/C pairs on two rectangular f32 problems, with padded leading dimensions, three batches, alpha=2, beta=-2 and both verification paths enabled.

To reproduce, add only that YAML regression to the submitted head and rebuild the caller and generated test data. With `$TEST_BIN` naming the test executable, `$GTEST_DATA` its generated data and `$DEVICE_LIB_DIR` a matching device library, run:

```sh
HIP_VISIBLE_DEVICES=0 OMP_NUM_THREADS=8 \
HIPBLASLT_TENSILE_LIBPATH="$DEVICE_LIB_DIR" \
  "$TEST_BIN" --data "$GTEST_DATA" \
  --gtest_filter='*matmul_fast_check_conjugate_transpose*'
```

Every case involving C fails in the submitted caller, while the N/T controls pass. Diagnostics include `Probe sums disagree` and `fast_check found a non-integer value in A, B or C; it requires integer_exact initialization`, despite integer-exact inputs. Applying the two-line caller fix makes the complete regression pass. The committed regression preserves the reproducer.

## Suggestions

No additional suggestions.

## Commentary

The separately tracked gfx950 Stream-K defect, ROCM-32277, belongs to the later-stack work in #13022. The [prior scope clarification](https://github.com/ROCm/rocm-libraries/pull/12876#issuecomment-6026410431) asked for empty-output handling on this root PR; this review retains that scope.

The [suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr12876-followup-20261007) contains one commit, [`fe4edad3077`](https://github.com/newling/rocm-libraries/commit/fe4edad30770f4227de812d0426076545680013c), for the sole actionable item. Its focused regression passes. The complete pre-check-in matrix, Windows execution and other GPU architectures were omitted locally; broader CI was incomplete at review time. No implementation is omitted for this finding. The review and fix are published for inspection and cherry-picking; no PR comment or formal GitHub review was posted.
