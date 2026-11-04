This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14769](https://github.com/ROCm/rocm-libraries/pull/14769)

**Reviewed head:** `a166d061104ff19f5c197cb656cfaaf183948b1b`, stacked on #14768 at `711ad850e0af9c45c272db28b795b93393f73294`.

**Review mode:** Follow-up design review, explicitly considering the existing discussion. All four reviews, two inline comments and four discussion comments were read. The head and comments were unchanged when checked again at completion. The [earlier review](review_pr14769.md) remains unchanged.

**Suggestion branch:** [review/pr14769-design-followup-20261103](https://github.com/newling/rocm-libraries/tree/review/pr14769-design-followup-20261103), based on the reviewed head.

| Commit | Review item |
|---|---|
| [`66dd4892854`](https://github.com/newling/rocm-libraries/commit/66dd4892854ae9b0aef2bc639e7fd45ceb32bf48) | Carry forward the earlier public status-documentation correction |
| [`98df689c5e4`](https://github.com/newling/rocm-libraries/commit/98df689c5e4984693ffe828946c94a420fb3ebeb) | Carry forward the earlier extension diagnostic correction |
| [`8b72410f2d3`](https://github.com/newling/rocm-libraries/commit/8b72410f2d37c8a3df355cb4c3c67d5d8c87c1aa) | Carry forward the earlier numerical bias/alpha-vector test |
| [`b7a1f0e806a`](https://github.com/newling/rocm-libraries/commit/b7a1f0e806a08d9e28b69df4a8be5a32c54cf849) | Add pointer-array batch coverage with matrix offsets |

The first three commits are cherry-picks of the earlier review's `d6e488cb702`, `bae9326601d` and `a7b6c495f2d`. Their changes remain applicable; they are not new discoveries. Each patch is independently applicable to the reviewed head. The output-layout alternatives below are design proposals, not implemented library features.

## Tests

On gfx1201 with ROCm 7.1, a Release host build using an existing gfx1201 device library passed all 19 focused tests on the submitted head and all 21 on the final suggestion branch (`RowOrderMatmul.*`, `AlgoErrors.*`, and `GroupedMatmul.smoke_RejectsUnsupportedSetups`). The new pointer-array test exercises 16 op/order combinations, three matrices per batch, padded leading dimensions, reversed device pointer arrays, distinct nonzero matrix offsets and an exact host reference. A separate FP32 experiment using the existing matrix-transform API passed both bias and alpha-vector cases with row-major A/B/C/D and nonzero beta; its source is preserved below.

Initial local setup attempts lacked the OpenBLAS `cblas.h` include directory and pointed `HIPBLASLT_TENSILE_LIBPATH` at the parent of the architecture directory. The latter produced `Cannot read .../TensileLibrary_lazy_gfx1201.dat` and downstream missing-algorithm failures. Setting `CPATH` to the OpenBLAS include directory and the library override to the directory containing that file resolved both without a source change. The reported results are from the corrected setup. Whitespace checks passed; repository pre-commit hooks reported no applicable checks for these hipBLASLt C++ files. Added test regions were formatted with the component style.

This is not a new device-library build or a validation on every GPU. The new batching test covers FP32; the output-conversion experiment covers unbatched, finite FP32 inputs. It does not qualify every output type, exceptional floating-point value, epilogue, graph-capture mode or batch representation. See the CI discussion below for the remaining failures.

## Summary

Keep the PR's A/B normalization. I did not find a better replacement within its current scope or a new numerical defect in the supported path. Accepting multiple public descriptions need not create multiple backend implementations: this PR already lowers ROW A/B into the existing column-major representation before both selection and execution. Calling that normalization a new alternative would misdescribe the submitted code.

Two useful output-layout options were absent from the reviewed discussion: use the existing C/D order attributes to request future native row-major loads/stores, rather than add a separate public `tC`; and compose ordinary GEMM with a layout-conversion pass when temporary storage and extra traffic are acceptable. The latter works in the limited experiment above. Neither option makes the inexpensive A/B adapter unnecessary, and neither is ready to become an unrestricted automatic fallback. These output-layout options are future work; the current PR can keep its A/B-only scope.

## Actionable items

### Keep the earlier status-documentation correction

The current `HIPBLASLT_ORDER_ROW` comment still says “Matmul also returns it” immediately after naming `HIPBLAS_STATUS_INVALID_VALUE` for the fused all-to-all exception. The subsequent operation/scale/int4 refusals actually return `HIPBLAS_STATUS_NOT_SUPPORTED`. Commit [`66dd4892854`](https://github.com/newling/rocm-libraries/commit/66dd4892854ae9b0aef2bc639e7fd45ceb32bf48) carries the earlier explicit-status correction onto this head. This is the same finding as in the earlier review.

No additional source correctness finding emerged from the contract pass. The two C entry points share the same rewrite; caller descriptors are copied rather than mutated; the descriptor's selection data remains shared; and grouped calls retain their existing validation path. The new tests exercise the previously untested pointer-array contract. Extension APIs still refuse ROW intentionally, so their behavior is not evidence that the C adapter failed.

## Suggestions

### Preserve one internal representation at the API boundary

The [single-basis concern](https://github.com/ROCm/rocm-libraries/pull/14769#pullrequestreview-5758974753) is a good constraint on the backend. Applying it to the public interface has a separate compatibility cost, as the [author's response](https://github.com/ROCm/rocm-libraries/pull/14769#issuecomment-6616835866) explains: the existing ROW enum is used by cuBLASLt ports. The NVIDIA documentation does define ROW and restrict some combinations; compatibility does not imply that every combination must be supported here.

For each operand, the present conversion is:

```text
ROW(r, c, ld), op=N  ->  COL(c, r, ld), op=T
ROW(r, c, ld), op=T  ->  COL(c, r, ld), op=N
```

There is no matrix-data copy, extra GPU launch, operand exchange or output transpose. The logical contraction and the side of the product to which each operand belongs remain unchanged. Batch pointers, offsets and strides remain attached to the same operand. Bias and alpha-vector indexing still follows the rows of the original D.

A broader internal representation based on logical dimensions and element strides could eventually serve more APIs. Moving this adapter into shared problem construction now would also cross extension and grouped paths that deliberately do not accept ROW, and would require preserving their contracts. I found no concrete simplification that justifies that refactor for this change. Keep one shared adapter for the two affected entry points, and require future accepted combinations to lower through it consistently.

### Exercise pointer-array batches and row vectors numerically

The author explicitly identified pointer-array batches as untested. Commit [`b7a1f0e806a`](https://github.com/newling/rocm-libraries/commit/b7a1f0e806a08d9e28b69df4a8be5a32c54cf849) closes that specific gap using the existing reference helper. Reversing the pointer arrays prevents an accidental strided interpretation from passing, and distinct matrix offsets exercise another field the rewrite must preserve. All 16 cases passed on gfx1201. This supports the A/B conversion's batching contract; it does not extend support to grouped layouts.

Commit [`8b72410f2d3`](https://github.com/newling/rocm-libraries/commit/8b72410f2d37c8a3df355cb4c3c67d5d8c87c1aa) also retains the earlier numerical bias and alpha-vector test. The submitted refusal table only checks that these configurations obtain an algorithm; numerical checks protect their row semantics against a future operand-swap rewrite. Commit [`98df689c5e4`](https://github.com/newling/rocm-libraries/commit/98df689c5e4984693ffe828946c94a420fb3ebeb) retains the earlier diagnostic improvement: the extension rejection now says that `hipblasLtMatmul` accepts ROW **for A and B**, so it does not direct a caller with row-major C/D to another unsupported call.

### Use the existing C/D order attributes for native output support

The proposed `tC` describes a physical storage choice. C and D already have independent layout descriptors with an order attribute. A future implementation can accept `ORDER_ROW` there while keeping logical `m`, `n`, the A/B roles and every epilogue axis fixed. This provides the intended native-transposed-storage behavior without introducing another public flag that can disagree with the layouts. An internal kernel property for the store orientation may still be useful.

The backend provides part of the machinery, but this is not a flag-only change. `RocblasltContractionProblem` currently [initializes row strides to one](https://github.com/ROCm/rocm-libraries/blob/a166d061104ff19f5c197cb656cfaaf183948b1b/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L199), and passes row/column strides into the C/D tensor descriptors. Those fields alone do not establish kernel support. In particular:

- [gfx1250 solution generation rejects `UseInitialStridesCD=True`](https://github.com/ROCm/rocm-libraries/blob/a166d061104ff19f5c197cb656cfaaf183948b1b/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/Solution.py#L1178).
- [The conversion generator has an unimplemented beta-clear path for it](https://github.com/ROCm/rocm-libraries/blob/a166d061104ff19f5c197cb656cfaaf183948b1b/projects/hipblaslt/tensilelite/tensilelite/KernelWriterConversion.py#L238).
- [StreamK uniform-summation validation refuses it](https://github.com/ROCm/rocm-libraries/blob/a166d061104ff19f5c197cb656cfaaf183948b1b/projects/hipblaslt/tensilelite/src/ContractionSolution.cpp#L6897), because the existing addressing proof does not cover that configuration.

Native support therefore needs suitable kernels, selection predicates and validation of the epilogue and summation contracts. I did not implement it on the suggestion branch: its supported combinations and kernel work require a separate design decision.

### Consider a temporary output plus layout conversion as an explicit fallback

There is another way to keep the original logical axes without native row-major output kernels:

```text
row-major C -> column-major C temporary, when C contributes
A/B -> ordinary GEMM and its epilogue -> column-major D temporary
column-major D temporary -> row-major D
```

The GEMM never computes `D^T`, so its reduction orientation, bias axis and alpha-vector axis remain unchanged. The existing `hipblasLtMatrixTransform` API can demonstrate this composition. The experiment below uses all-row-major external matrices, nonzero beta, unequal padded dimensions, and separately checks bias and alpha-vector results against the logical reference. It passed without changing the matmul implementation.

This costs temporary matrix storage and an output-conversion launch; packing C adds another launch when needed. For a dense D with element size `s`, the output conversion adds approximately `2*m*n*s` bytes of traffic relative to a direct store, excluding padding. That is a poor default for small or bandwidth-bound GEMMs, but can be a reasonable explicit compatibility path when the GEMM dominates. No performance claim was benchmarked here.

The current transform kernel [evaluates `alpha*A + beta*B`](https://github.com/ROCm/rocm-libraries/blob/a166d061104ff19f5c197cb656cfaaf183948b1b/projects/hipblaslt/device-library/matrix-transform/matrix_transform.cpp#L243); it is not specified as a bit-preserving reorder. A general automatic fallback would need a pure layout-copy kernel or qualification of numerical corner cases, plus workspace accounting and clear batching/aliasing behavior. Aux outputs need their own layout contract. I would document or prototype this composition before proposing it as an automatic matmul path. The suggestion branch deliberately does not add that policy or implementation.

## Commentary

### Existing comments and their current status

| Existing feedback | Assessment at the reviewed head |
|---|---|
| The FP8 helper returned after its first supported output type | Fixed in `fb67accf3a9`: the loop now visits FP32 and FP16. The scale change also keeps the FP16 reference exact. The inline thread is resolved; it is not a remaining finding. |
| Approval of CMakeLists changes | Its stated scope is build-file changes. It does not resolve the API-design question. |
| Prefer COL-only public matmul and let callers perform the algebra | This reduces the advertised support surface, but transfers the same conversion to every affected caller. The current A/B adapter preserves one backend representation without the output-axis problems of operand swapping. |
| Compatibility, batched behavior and possible `tC` | The compatibility argument is supported by the existing public API. Strided coverage is present; this follow-up adds successful pointer-array coverage. Native output support remains separate, and the existing C/D order attributes can express it. |

The earlier suggestion to restrict operand swapping to configurations without row-bound features is still possible, but it creates another support matrix and depends on explicitly relaxing the uniform-summation requirement. It is less attractive than native output stores or an explicit conversion when preserving those semantics matters.

### CI has not fully passed

The [gfx90a ASAN job](https://github.com/ROCm/rocm-libraries/actions/runs/41729405081/job/126259766509) ran 1,129 passing tests and skipped 10, then failed LeakSanitizer with 224 bytes in two allocations. Its reported allocation frame is in `libamdhip64.so.7`; there is no row-major numerical test failure in that log. The stack does not establish the allocation's complete origin, so this review does not claim to have proved the leak unrelated to the PR. The FP8 test skipped there because the loaded library lacked a supported control.

The check snapshot also contains emulation and policy failures and pending broader math jobs. Those were not diagnosed or awaited in this design review. The earlier full-logging invalid-algorithm crash is separately tracked as ROCM-33916 and is not a new finding here.

## Appendix: output-conversion experiment

The following standalone gtest translation unit includes the PR's existing fixture and helpers. Compile with the hipBLASLt public/generated include directories, `clients/tests/src`, HIP and gtest headers; link the reviewed hipBLASLt library, HIP runtime, gtest and gtest_main. Run only `--gtest_filter=RowOrderMatmul.probe_RowOutputViaTransform`. The matching `hipblasltTransform_<arch>.hsaco` must be installed in the library's normal per-architecture location, in addition to the GEMM device library. This source was compiled and run with the suggestion branch; its production matmul computation is unchanged from the reviewed head.

```cpp
// Copyright Advanced Micro Devices, Inc., or its affiliates.
// SPDX-License-Identifier: MIT

#include "row_order_matmul_gtest.cpp"

namespace
{
    TEST_F(RowOrderMatmul, probe_RowOutputViaTransform)
    {
        const Stored sA = stored(kM, kK, 1, HIPBLASLT_ORDER_ROW);
        const Stored sB = stored(kK, kN, 1, HIPBLASLT_ORDER_ROW);
        const Stored sC = stored(kM, kN, 1, HIPBLASLT_ORDER_COL);
        const Stored sR = stored(kM, kN, 1, HIPBLASLT_ORDER_ROW);

        std::vector<float> rowValues(kM);
        for(int64_t i = 0; i < kM; i++)
            rowValues[i] = float(i % 5 - 2);
        const float        alpha = 2.0f, beta = 3.0f;
        const DeviceBuffer dA       = upload(fill<float>(sA, valueA));
        const DeviceBuffer dB       = upload(fill<float>(sB, valueB));
        const DeviceBuffer dC       = upload(std::vector<float>(sC.elements(), 0.0f));
        const DeviceBuffer dRowC = upload(fill<float>(sR, valueC));
        const DeviceBuffer dRowD(sR.elements() * sizeof(float));
        const DeviceBuffer dRowData = upload(rowValues);
        const DeviceBuffer work(kWorkspace);
        const LayoutPtr    lA = makeLayout(HIP_R_32F, sA), lB = makeLayout(HIP_R_32F, sB);
        const LayoutPtr    lC = makeLayout(HIP_R_32F, sC), lD = makeLayout(HIP_R_32F, sC);
        const PrefPtr      pref = makePref(kWorkspace);
        const LayoutPtr lRow = makeLayout(HIP_R_32F, sR);
        hipblasLtMatrixTransformDesc_t transform = nullptr;
        ASSERT_EQ(hipblasLtMatrixTransformDescCreate(&transform, HIP_R_32F),
                  HIPBLAS_STATUS_SUCCESS);
        const std::unique_ptr<hipblasLtMatrixTransformDescOpaque_t,
                              decltype(&hipblasLtMatrixTransformDescDestroy)>
            transformOwner(transform, &hipblasLtMatrixTransformDescDestroy);
        const float one = 1.0f, zero = 0.0f;
        ASSERT_EQ(hipblasLtMatrixTransform(handle, transform, &one, dRowC.get(), lRow.get(),
                                          &zero, nullptr, nullptr, dC.get(), lC.get(), nullptr),
                  HIPBLAS_STATUS_SUCCESS);

        for(const bool alphaVector : {false, true})
        {
            SCOPED_TRACE(alphaVector ? "alpha vector" : "bias");
            const DescPtr desc     = makeDesc();
            const void*   alphaPtr = &alpha;
            if(alphaVector)
            {
                setAttribute(desc.get(),
                             HIPBLASLT_MATMUL_DESC_POINTER_MODE,
                             HIPBLASLT_POINTER_MODE_ALPHA_DEVICE_VECTOR_BETA_HOST);
                alphaPtr = dRowData.get();
            }
            else
            {
                setAttribute(desc.get(), HIPBLASLT_MATMUL_DESC_EPILOGUE, HIPBLASLT_EPILOGUE_BIAS);
                setAttribute(desc.get(), HIPBLASLT_MATMUL_DESC_BIAS_DATA_TYPE, HIP_R_32F);
                setAttribute(desc.get(), HIPBLASLT_MATMUL_DESC_BIAS_POINTER, dRowData.get());
            }
            const DeviceBuffer dD = upload(std::vector<float>(sC.elements(), 0.0f));

            hipblasLtMatmulHeuristicResult_t result{};
            int                              returned = 0;
            ASSERT_EQ(hipblasLtMatmulAlgoGetHeuristic(handle,
                                                      desc.get(),
                                                      lA.get(),
                                                      lB.get(),
                                                      lC.get(),
                                                      lD.get(),
                                                      pref.get(),
                                                      1,
                                                      &result,
                                                      &returned),
                      HIPBLAS_STATUS_SUCCESS);
            ASSERT_GT(returned, 0);
            ASSERT_EQ(hipblasLtMatmul(handle,
                                      desc.get(),
                                      alphaPtr,
                                      dA.get(),
                                      lA.get(),
                                      dB.get(),
                                      lB.get(),
                                      &beta,
                                      dC.get(),
                                      lC.get(),
                                      dD.get(),
                                      lD.get(),
                                      &result.algo,
                                      work.get(),
                                      kWorkspace,
                                      nullptr),
                      HIPBLAS_STATUS_SUCCESS);
            ASSERT_EQ(hipblasLtMatrixTransform(handle, transform, &one, dD.get(), lD.get(),
                                              &zero, nullptr, nullptr, dRowD.get(), lRow.get(), nullptr),
                      HIPBLAS_STATUS_SUCCESS);
            ASSERT_EQ(hipDeviceSynchronize(), hipSuccess);
            std::vector<float> hD(sR.elements());
            ASSERT_EQ(
                hipMemcpy(hD.data(), dRowD.get(), hD.size() * sizeof(float), hipMemcpyDeviceToHost),
                hipSuccess);

            int mismatches = 0;
            for(int64_t i = 0; i < kM; i++)
                for(int64_t j = 0; j < kN; j++)
                {
                    float sum = 0;
                    for(int64_t l = 0; l < kK; l++)
                        sum += valueA(0, i, l) * valueB(0, l, j);
                    const float expected
                        = alphaVector ? rowValues[i] * sum + beta * valueC(0, i, j)
                                      : alpha * sum + beta * valueC(0, i, j) + rowValues[i];
                    const float actual = hD[sR.index(0, i, j)];
                    if(actual != expected && mismatches++ < 3)
                        ADD_FAILURE() << "D(" << i << ", " << j << ") is " << actual
                                      << ", expected " << expected;
                }
            EXPECT_EQ(mismatches, 0);
        }
    }
}
```
