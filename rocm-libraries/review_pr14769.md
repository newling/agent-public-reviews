This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14769](https://github.com/ROCm/rocm-libraries/pull/14769)

**Reviewed head:** `2f604252b96` (stacked on #14768 at `907555fae14`)

**Suggestion branch:** [newling/rocm-libraries:review/pr14769-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14769-suggestions), based on `2f604252b96`

| Commit | Item |
|---|---|
| [`d6e488cb702`](https://github.com/newling/rocm-libraries/commit/d6e488cb702fdbad1727b32746ed193e2db7c60b) | The `HIPBLASLT_ORDER_ROW` comment names the wrong status for three refusals |
| [`bae9326601d`](https://github.com/newling/rocm-libraries/commit/bae9326601db430e3b12de3ed4d2091813275c02) | The extension API's refusal message overstates what `hipblasLtMatmul` accepts |
| [`a7b6c495f2d`](https://github.com/newling/rocm-libraries/commit/a7b6c495f2dfc370dc7bc71e662c6b7667bdbb61) | Check the bias and alpha vectors numerically with row-major A and B |

The commits are independent of each other.

## Tests

On gfx1201 (host-only build with a develop gfx1201 kernel library): the PR's focused tests (`RowOrderMatmul.*`, `AlgoErrors.*`, `GroupedMatmul.smoke_RejectsUnsupportedSetups`) passed 18/18 at the PR head and 19/19 on the suggestion branch, including the scalar-scaled FP8 test. `*smoke*:*aux_test*` on the suggestion branch passed 3439 tests, with 12 `GroupedMatmul` tests skipped. A standalone probe ran every algorithm the heuristic returned (64 each) for all 16 combinations of op A, op B, order of A and order of B (fp16, m=37 n=19 k=11, padded leading dimensions). Every algorithm produced the exact reference D.

The `codecov(hipblaslt)` failure on this PR does not come from this change; see the commentary. The FP8 test's comment names only gfx942 and gfx950, but the gfx1201 library also has scalar-scaled FP8 kernels, so the test ran rather than skipped. The probe could not exercise `HIPBLASLT_EPILOGUE_BGRADA`/`BGRADB`: the gfx1201 library has no kernels for them, even with column-major inputs.

## Summary

The PR makes `hipblasLtMatmul` and `hipblasLtMatmulAlgoGetHeuristic` accept a row-major A or B. Before calling `rocblaslt`, a shared helper (`rewrite_row_major`) builds per-call copies of the descriptor and the A/B layouts. In those copies, each row-major operand's rows and columns are swapped, its order becomes column-major and its op is flipped between N and T. A row-major C or D, and combinations whose auxiliary data has a fixed storage layout (block/vector scales, int4, ops other than N/T), are refused with `HIPBLAS_STATUS_NOT_SUPPORTED`. The existing argument checks and the grouped path keep their own statuses.

The central design choice is sound. Transposing each operand in place leaves the operands, D and m/n/k unchanged. The common row-major trick swaps A and B and computes D^T, but this rewrite never does that. As a result, everything bound to D or to a specific operand stays correct without special handling: the bias, the alpha vector, the aux output, the scalar A/B scales, the compute input types and the uniform-summation guarantee. The descriptor copy uses the same `_rocblaslt_matmul_desc::copy()` that backs the public descriptor-copy API and the grouped path. I checked that rocblaslt writes to a descriptor only for grouped calls, which the rewrite skips. The heuristic's temporary bias substitution lands on the copy. So nothing the library records is lost when it is written to the copy. Because both entry points use the same rewrite, an algorithm returned for a row-major problem is valid for the matching matmul, and the all-algorithms probe confirms this on gfx1201.

The tests are well chosen. Odd, unequal sizes and padded leading dimensions make a swapped dimension or leading dimension change the result. Small integer inputs make `==` comparison valid. The refusal table pairs each refusal with a control that differs in one setting. The remaining findings concern documentation accuracy and one gap in numerical coverage.

## Actionable items

### The `HIPBLASLT_ORDER_ROW` comment names the wrong status for three refusals

`projects/hipblaslt/library/include/hipblaslt/hipblaslt.h:490-496`. The sentence that lists the operation, scale-mode and int4 refusals starts "Matmul also returns it…". It directly follows a sentence that ends with `HIPBLAS_STATUS_INVALID_VALUE` (the fused all-to-all exception), so readers will take those refusals to return `INVALID_VALUE`. The code returns `HIPBLAS_STATUS_NOT_SUPPORTED`, as the tests and the CHANGELOG say. Line 494 also runs well past the width of the surrounding comment.

Commit [`d6e488cb702`](https://github.com/newling/rocm-libraries/commit/d6e488cb702fdbad1727b32746ed193e2db7c60b) names `HIPBLAS_STATUS_NOT_SUPPORTED` once for every refusal (row-major C or D; row-major A or B with another op, a block or vector scale or `HIP_R_4I`). It then states the all-to-all `INVALID_VALUE` exception last, with its reason, and rewraps the paragraph.

## Suggestions

### The extension API's refusal message overstates what `hipblasLtMatmul` accepts

`projects/hipblaslt/library/src/amd_detail/hipblaslt.cpp:95-96`. The extension APIs now log "HIPBLASLT_ORDER_ROW is not supported by this API; hipblasLtMatmul and hipblasLtMatrixTransform accept it". A caller with a row-major C or D who follows that pointer gets another refusal. Commit [`bae9326601d`](https://github.com/newling/rocm-libraries/commit/bae9326601db430e3b12de3ed4d2091813275c02) changes the message to say that `hipblasLtMatmul` accepts it for A and B. No test matches the message text.

### Check the bias and alpha vectors numerically with row-major A and B

`projects/hipblaslt/clients/tests/src/row_order_matmul_gtest.cpp:552-553, 585`. The bias and alpha-vector controls only assert that the heuristic returns an algorithm. These are the two pieces of state most likely to break if the rewrite ever moves to the operand-swap form, because each has one value per row of D. A future change that computes D^T would still find algorithms, and the controls would still pass.

Commit [`a7b6c495f2d`](https://github.com/newling/rocm-libraries/commit/a7b6c495f2dfc370dc7bc71e662c6b7667bdbb61) adds `RowOrderMatmul.smoke_RowVectorsFollowD`. It runs a `HIPBLASLT_EPILOGUE_BIAS` GEMM and a `HIPBLASLT_POINTER_MODE_ALPHA_DEVICE_VECTOR_BETA_HOST` GEMM with row-major A and B, using the file's existing helpers and padded odd sizes. The per-row values vary with the row, and D is compared with `==` against `alpha·op(A)·op(B) + beta·C + bias[i]` and `alphaVec[i]·op(A)·op(B) + beta·C` respectively. The test passes on gfx1201.

## Commentary

**The `codecov(hipblaslt)` failure is pre-existing.** The coverage job's log shows a segfault in the `AlgoErrors` suite during a run with full API logging. It reproduces locally with column-major layouts only:

```
HIPBLASLT_LOG_MASK=255 hipblaslt-test --gtest_filter=AlgoErrors.smoke_MatmulRejectsUnknownIndex
```

The backtrace runs `hipblasLtMatmul → rocblaslt_matmul_impl → runContractionProblem → getKernelNameFromAlgoIndex`. With the extended-profile log bit set, `runContractionProblem` asks for the kernel name of the caller's algorithm before the unknown index is rejected. `getKernelNameFromAlgoIndex` (`rocblaslt/src/tensile_host.cpp:8456`) and `getSolutionNameFromAlgoIndex` (`:8483`) then dereference the null result of `getSolutionByIndex`. The test comes from develop (#12787), and neither this PR nor #14768 touches `tensile_host.cpp`. #14768's coverage job also fails in its Test stage. The failure needs a separate fix, but until it lands it will keep this PR's coverage gate red.

**Logs and replay commands describe the rewritten problem.** The PR description says this, but the public documentation does not. Someone reading a trace from a row-major NN call sees column-major layouts with ops TN. That is a correct and replayable description of the same GEMM, and tuning-override entries match it consistently. Still, the mismatch with the caller's own descriptor may surprise people. A single trace line at the `hipblaslt.cpp` layer recording that a rewrite happened (for example "A row-major, computed as its column-major transpose") would make such logs self-explanatory. This is optional.

**Residual risk: BGRADA/BGRADB.** These epilogues reduce over op(A) or op(B). The client reference defines them on the logical matrices, so the rewrite should preserve them, provided that kernels exist for the flipped op. gfx1201 has no kernels for them, so they were not exercised here. A run on gfx942/gfx950, where the PR already plans on-device validation, would cover them.

**Row-major D.** The PR's reasoning for deferring row-major D (computing D^T moves the uniform-summation guarantee from rows to columns) is convincing. When that follow-up is designed, the operand-swap form could be limited to calls where uniform summation is off and no D-bound vector or operand-specific scale is set. The refusal table here is a good template for listing what that path must exclude.
