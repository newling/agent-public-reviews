This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14768](https://github.com/ROCm/rocm-libraries/pull/14768)

**Reviewed head:** `907555fae14`

**Suggestion branch:** [newling/rocm-libraries:review/pr14768-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14768-suggestions), based on `907555fae14`

| Commit | Item |
|---|---|
| [`978aebed1b0`](https://github.com/newling/rocm-libraries/commit/978aebed1b0e068fedb3e1b0ad6dc470b4f1f135) | A swizzled or unrecognized order on C or D is still computed as column-major |

## Tests

On gfx1201 (host-only build with a develop gfx1201 kernel library): the focused tests (`AlgoErrors.*`, `GroupedMatmul.smoke_RejectsUnsupportedSetups`, `*aux_mat*`) passed 43/43 at the PR head and 44/44 on the suggestion branch. Without its library change, the new test in `978aebed1b0` fails 48 checks. `*smoke*:*aux_test*` on the suggestion branch passed 3434 tests, with 12 `GroupedMatmul` tests skipped because the kernel library has no grouped solutions. Standalone probes (below and in the appendix) exercised orders on C and D, status precedence, and a `k = 0` call with null A and B.

Neither CI failure comes from this change. `codecov(hipblaslt)` segfaults in `AlgoErrors.smoke_MatmulRejectsUnknownIndex`, a develop test. It reproduces locally with `HIPBLASLT_LOG_MASK=255` and column-major layouts: with extended-profile logging, `getKernelNameFromAlgoIndex` in `rocblaslt/src/tensile_host.cpp` dereferences the null solution returned for the unknown index. The `FFM gfx1250 / tensilelite` failures (3 failed, 9 timed out) are TensileLite kernel tests, and this PR touches no TensileLite code.

## Summary

Matmul read a layout's order only to decide whether A or B was swizzled. A row-major layout was therefore multiplied as column-major, and every call returned `HIPBLAS_STATUS_SUCCESS`. This PR refuses `HIPBLASLT_ORDER_ROW` in the API layer: `hipblasLtMatmul`, `hipblasLtMatmulAlgoGetHeuristic` (which also reports 0 algorithms) and the extension `Gemm`/`GroupedGemm` `setProblem`, `matmulIsAlgoSupported` and `isSolutionSupported` return `HIPBLAS_STATUS_NOT_SUPPORTED`, and `matmulIsTuned` returns `-1`. The log names the offending matrix. The PR also makes `hipblasLtMatrixLayoutGetAttribute` read back `TYPE`, `ORDER`, `ROWS`, `COLS` and `LD`, and corrects the documentation that claimed row-major support.

The change fixes the reported defect on its own: wrong results with a success status become an explicit error, with no change to kernel selection or device code. Placing the check in the API layer is well argued: rocblaslt has no status that maps to `NOT_SUPPORTED`, and its heuristic reports invalid arguments as success with no algorithms. The tests pair every refusal with a column-major control that must still get an algorithm and succeed, so a check that over-refuses would fail as well. The getter cases match the setter's sizes, and their tests cover buffers one byte too small.

## Actionable items

### A swizzled or unrecognized order on C or D is still computed as column-major

`projects/hipblaslt/library/src/amd_detail/hipblaslt.cpp:82-103` (`refuse_row_order`). The kernels read C and write D column-major only; swizzled orders exist only for A and B. rocblaslt reads the order of A and B to choose a swizzled kernel and validates it there (`isValidOrderForDatatype`), but it never reads the order of C or D. The setter stores any `int32_t`. The result is the same silent defect for C and D with any non-row, non-column order. At the PR head on gfx1201, an fp16 64×64×64 GEMM behaves as follows:

| Order on C and D | Heuristic | `hipblasLtMatmul` |
|---|---|---|
| `HIPBLASLT_ORDER_COL` (0) | success, 1 algorithm | success |
| `HIPBLASLT_ORDER_COL16_4R8` (101) | success, 1 algorithm | success |
| `HIPBLASLT_ORDER_COL16_4R16` (100) | success, 1 algorithm | success |
| 7 (no enumerator) | success, 1 algorithm | success |

For comparison, the same orders on A and B (fp32, op A = T) get no algorithms, and matmul returns an error.

Commit [`978aebed1b0`](https://github.com/newling/rocm-libraries/commit/978aebed1b0e068fedb3e1b0ad6dc470b4f1f135) renames the helper to `refuse_unsupported_order` and additionally refuses any C or D order other than `HIPBLASLT_ORDER_COL`. Every entry point that already refuses row order gets the new check, and the grouped exemption is unchanged. The commit updates the internal comment, the `HIPBLASLT_MATRIX_LAYOUT_ORDER` doc comment, `what-is-hipBLASLt.rst` and the CHANGELOG entry. It adds `AlgoErrors.smoke_OutputOrderOtherThanColIsRefused`, which checks the heuristic, matmul, extension `Gemm::setProblem`, `matmulIsAlgoSupported` and `matmulIsTuned` for each swizzled order and for 7, on C and on D separately. No client sets an order on C or D (`testing_matmul.hpp` sets it only on A and B).

#14769, which is stacked on this PR, needs the same rule. Its rewrite refuses only a row-major C or D, so a column-major A and B beside a swizzled D still skip the rewrite and reach the kernels. Its calls to `refuse_row_order` would also need the new name.

## Suggestions

### Reconsider keeping the original status for calls that are invalid twice

`projects/hipblaslt/library/src/amd_detail/hipblaslt.cpp:119-235` (`gemm_pointers_missing`, `matmul_arguments_present`, `heuristic_arguments_present`), the four `gemm_pointers_missing` guards in `hipblaslt-ext.cpp` (around lines 1156, 1221, 1416 and 1501), their declarations in `hipblaslt_internal.hpp`, and `AlgoErrors.smoke_RowOrderKeepsArgumentValidationFirst` (`algo_errors_gtest.cpp:475`, about 380 lines).

Roughly 570 of the PR's 1,280 added lines exist so that a call with a missing pointer still reports the missing pointer when it is also row-major. To do this, the API layer copies the null-pointer rules of `validateMatmulArgs`, `gemmCreate`/`groupedGemmCreate` and `rocblaslt_matmul`. I checked the copies against the originals, and they currently agree. That includes a subtle point: `rocblaslt_matmul` rejects a null A or B with a nonzero alpha even when `k = 0`, although `validateMatmulArgs` would accept it, and `matmul_arguments_present` follows `rocblaslt_matmul`. The copies still have to track every future change to those rules.

The precedence they buy is also partial. Only missing pointers keep their status. Every other argument error that rocblaslt detects after the order check becomes `NOT_SUPPORTED` once a layout is row-major (appendix probe, `hipblasLtMatmul` at the PR head):

| Invalid call | Column-major A | Row-major A |
|---|---|---|
| Batch count of A is 2, others 1 | 3 (`INVALID_VALUE`) | 7 (`NOT_SUPPORTED`) |
| op A = `HIPBLASLT_OPERATION_INVALID` | 6 | 7 (`NOT_SUPPORTED`) |

A call that is both malformed and row-major is an error under either status. A simpler contract is to refuse an unsupported order as soon as the layouts are present, keeping only the guards that memory safety requires: the null-layout skip already in the layout form of the helper, and a null `returnAlgoCount` in the heuristic, which the refusal path writes to. That would remove `gemm_pointers_missing`, `matmul_arguments_present` and most of `smoke_RowOrderKeepsArgumentValidationFirst`.

I did not implement this. It reverses a deliberate choice (commits `4de8a193fb1` and `1ca2bce03ef`), so it needs the author's and maintainers' agreement on the status policy. It would also conflict with #14769, which reuses `matmul_arguments_present`.

## Commentary

This PR is a complete fix for ROCM-29960 by itself. #14769 adds row-major A and B support on top as a separate feature; this PR neither depends on it nor needs it.

The workaround in the `HIPBLASLT_ORDER_ROW` comment ("swap A and B, swap `m` and `n`, and describe each matrix as its column-major transpose") is correct for the all-row-major case. A caller using it with a bias, an alpha vector or per-operand scales also has to move those to the other axis or operand. A sentence noting that would save someone a debugging session, but it isn't required for this fix.

## Appendix: status precedence probe

Built against the library at the PR head and linked with `-lhipblaslt`; run with `HIPBLASLT_TENSILE_LIBPATH` pointing at a kernel library for the local GPU.

```cpp
#include <hip/hip_runtime.h>
#include <hipblaslt/hipblaslt.h>

#include <cstdio>

static hipblasLtMatrixLayout_t layout(int32_t order, int32_t batch)
{
    hipblasLtMatrixLayout_t l;
    hipblasLtMatrixLayoutCreate(&l, HIP_R_32F, 64, 64, 64);
    hipblasLtMatrixLayoutSetAttribute(l, HIPBLASLT_MATRIX_LAYOUT_ORDER, &order, sizeof(order));
    hipblasLtMatrixLayoutSetAttribute(l, HIPBLASLT_MATRIX_LAYOUT_BATCH_COUNT, &batch, sizeof(batch));
    int64_t stride = 64 * 64;
    hipblasLtMatrixLayoutSetAttribute(
        l, HIPBLASLT_MATRIX_LAYOUT_STRIDED_BATCH_OFFSET, &stride, sizeof(stride));
    return l;
}

int main()
{
    hipblasLtHandle_t handle;
    hipblasLtCreate(&handle);
    void* buf;
    hipMalloc(&buf, 2 * 64 * 64 * 4);
    const float alpha = 1, beta = 0;

    struct Case
    {
        const char*        name;
        int32_t            batchA;
        hipblasOperation_t opA;
    } cases[] = {{"A batch 2, others 1", 2, HIPBLAS_OP_N},
                 {"op A = HIPBLASLT_OPERATION_INVALID", 1, hipblasOperation_t(HIPBLASLT_OPERATION_INVALID)}};

    for(const Case& c : cases)
        for(int32_t order : {int32_t(HIPBLASLT_ORDER_COL), int32_t(HIPBLASLT_ORDER_ROW)})
        {
            hipblasLtMatmulDesc_t desc;
            hipblasLtMatmulDescCreate(&desc, HIPBLAS_COMPUTE_32F, HIP_R_32F);
            hipblasLtMatmulDescSetAttribute(desc, HIPBLASLT_MATMUL_DESC_TRANSA, &c.opA, sizeof(c.opA));
            auto lA = layout(order, c.batchA), lB = layout(0, 1), lC = layout(0, 1), lD = layout(0, 1);
            hipblasStatus_t s = hipblasLtMatmul(
                handle, desc, &alpha, buf, lA, buf, lB, &beta, buf, lC, buf, lD, nullptr, nullptr, 0, nullptr);
            std::printf("%-36s A %s: matmul status %d\n", c.name, order ? "row" : "col", int(s));
            hipblasLtMatrixLayoutDestroy(lA);
            hipblasLtMatrixLayoutDestroy(lB);
            hipblasLtMatrixLayoutDestroy(lC);
            hipblasLtMatrixLayoutDestroy(lD);
            hipblasLtMatmulDescDestroy(desc);
        }
    return 0;
}
```
