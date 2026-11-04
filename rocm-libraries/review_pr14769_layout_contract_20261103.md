This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14769](https://github.com/ROCm/rocm-libraries/pull/14769)

**Reviewed head:** `a166d061104ff19f5c197cb656cfaaf183948b1b`, unchanged when checked for this extension.

**Scope:** Addendum to the [published design review](review_pr14769_design_followup_20261103.md), addressing execution-cost transparency, the compatibility argument and the history of the order API. Both published reviews remain unchanged. This addendum narrows the policy implications of the earlier recommendation; it does not replace its numerical assessment.

**Suggestion branch:** [review/pr14769-layout-contract-20261103](https://github.com/newling/rocm-libraries/tree/review/pr14769-layout-contract-20261103). It builds on the four published suggestions at [`b7a1f0e806a`](https://github.com/newling/rocm-libraries/commit/b7a1f0e806a08d9e28b69df4a8be5a32c54cf849), which are based on the reviewed PR head.

| New commit | Item |
|---|---|
| [`aab732214d1`](https://github.com/newling/rocm-libraries/commit/aab732214d10d5348c10d48097d8469193710366) | Explain descriptor normalization, its GPU cost and the distinction between equivalent descriptions and different physical layouts |

The new commit changes documentation only. Its public-header edit builds on the earlier status-documentation correction already present on the branch. No conversion policy or additional layout support is implemented.

## Tests

The documentation was checked against `rewrite_row_major` and both callers; the public header outside block comments is byte-for-byte unchanged, and `git diff --check` passes. The preceding review's 19 passing tests on the submitted head and 21 on the published suggestion branch remain the runtime evidence. No new GPU tests, performance measurements or full documentation-site build were run for this prose-only extension.

## Summary

The author's current A/B approach remains a reasonable bounded implementation: it rewrites descriptors into the backend's existing representation without moving matrix data. That technical assessment does not settle the broader API policy. Users should be able to distinguish a different description of the same bytes from a request that causes the library to rearrange those bytes, and to understand which physical arrangements perform well.

The case for accepting ROW here should rest on the implementation, its maintenance cost and the library's intended contract. Neither cuBLAS's public interface nor the age of this enum establishes that contract for hipBLASLt. The history below makes maintainer input more relevant: the enum was introduced alongside explicit matrix transformation, without a corresponding change to the matmul wrapper.

## Actionable items

### Document what the row-major rewrite costs

At the reviewed head, `projects/hipblaslt/library/include/hipblaslt/hipblaslt.h:493` and `projects/hipblaslt/docs/what-is-hipBLASLt.rst:116` describe computing row-major A/B as column-major transposes. That wording leaves room for a reader to infer a GPU transpose or packing pass. The code performs neither as part of this rewrite.

Commit [`aab732214d1`](https://github.com/newling/rocm-libraries/commit/aab732214d10d5348c10d48097d8469193710366) changes the public comment and guide to explain that the library rewrites internal layout copies and transpose flags, with no matrix-data copy or separate transpose kernel. The guide also explains that layout normalization needs no conversion workspace, although the selected GEMM algorithm can still need workspace, and that logs describe the normalized problem.

The guide distinguishes GPU work from total call cost: the ROW path adds host-side descriptor handling. An equivalent COL description of the same bytes reaches the same backend problem, but that observation is not a claim of identical total call latency. Different physical arrangements can have different performance depending on the GPU, data type, transpose choices, dimensions and available kernels. A default order enum is insufficient performance guidance by itself.

## Suggestions

The earlier numerical vector and pointer-array batch tests remain useful and are retained on the accompanying branch. They support the accepted A/B transformation; they do not justify broadening the support matrix or silently introducing materialized conversions. No further runtime change is proposed in this addendum.

## Commentary

### Keep future materialized conversions under explicit caller control

Exposing only the backend's accepted representations can make an API easier to reason about. Accepting more representations creates an obligation to explain their cost and maintain their support boundaries. That concern remains valid even when the current adapter is small.

For this PR, the distinction is concrete: changing ROW/N to the equivalent COL/T description changes metadata, while physically repacking a matrix changes memory traffic, workspace requirements and potentially launch count. The output-conversion experiment in the preceding review belongs to the latter category. Its successful numerical result establishes feasibility for the tested cases, not permission to make it an invisible default.

If future support requires materializing a different layout, I recommend an explicit conversion operation or an opt-in whose workspace and extra GPU work are visible to the caller. This is a proposed policy for maintainers to decide, rather than a claim about an existing project-wide guarantee. The documentation commit describes only the current A/B rewrite. Future native C/D support and conversion fallbacks remain separate work.

### Compatibility is a use case, not an architectural justification

The public cuBLASLt API shows that ported callers may request ROW. It does not reveal how cuBLAS implements that request, whether it pays for conversion, or whether its kernels accommodate the layout more naturally. Matching its surface cannot establish that a feature is a good fit for hipBLASLt.

Compatibility can still be a deliberate product benefit. It should be weighed against concrete porting needs, implementation complexity, testing obligations and the desired performance contract. The current A/B rewrite has a technical case independent of cuBLAS: it preserves the logical contraction, uses the same normalization for selection and execution, and adds no GPU layout conversion. That is the basis of the recommendation here. It is not an argument for matching every order combination or future fallback behavior.

### The historical enum does not establish a matmul promise

In the standalone repository's public history, [commit `b580680cbb51`](https://github.com/ROCm/hipBLASLt/commit/b580680cbb51b83376498970b7391fd8418e1f9e), dated August 22, 2023 and titled “First draft of transform kernel integration,” introduced `hipblasLtOrder_t`, `HIPBLASLT_ORDER_ROW` and the layout-order attribute alongside the matrix-transform API and a transform sample. Its changes to the public API implementation add transform entry points; they leave the matmul wrapper unchanged.

[PR #326](https://github.com/ROCm/hipBLASLt/pull/326), merged December 2, 2023, subsequently refined `hipblasLtMatrixTransform`, its validation and its documentation. Its description concerns transform support. These records show that the order enum had a purpose independent of row-major matmul. Its presence alone is therefore insufficient evidence that every matmul order was historically promised.

This is a bounded history check, not a reconstruction of the project's roadmap. It does not prove that ROW matmul was intentionally excluded, that normalization was previously rejected, or that no broader support was planned. Those are questions for maintainers with the relevant design context:

- What support contract was intended when the shared order API was introduced, and which consumers relied on it?
- Was the absence of ROW matmul deliberate or an implementation gap, and was this normalization approach previously considered?
- What cost guarantees should accompany layout support, and where should callers find guidance on preferred physical layouts for the supported kernel families?

Answers grounded in earlier design decisions and current consumers would be more informative than inferring policy from another library's API or from the enum's existence. The present implementation can be assessed on its own merits while that context informs the longer-term contract.
