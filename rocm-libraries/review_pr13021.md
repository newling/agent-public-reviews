This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13021](https://github.com/ROCm/rocm-libraries/pull/13021)

**Reviewed head:** [`c8d9134aa913d7cc2039c272545e463d9c1107d9`](https://github.com/ROCm/rocm-libraries/commit/c8d9134aa913d7cc2039c272545e463d9c1107d9) (2026-10-06), relative to #13015. Public repository and head; existing reviews/comments were not consulted.

**Published suggestion branch:** [`review/pr13021-suggestions-20261006`](https://github.com/newling/rocm-libraries/tree/review/pr13021-suggestions-20261006), based on that exact head, with no additional commits.

## Tests

Built the submitted checker and passed all 50 host/device self-tests on gfx1201/ROCm 7.1, including filter selection and memory-shortfall diagnostics. Both matmul-header modes compile. Generated all 67 threshold records from the 14 new definitions and checked the leading-dimension brackets around 2^31 and 2^32. Whitespace checks pass.

The multi-GiB GEMM sweeps were not executed locally; that would require suitable hardware and substantial allocations. Passing small helper tests does not establish that those kernel boundaries work.

## Summary

The new stress category separates expensive size-boundary cases from ordinary test runs. An explicit positive gtest filter opts into fast_check stress cases, memory preflight reports required and available memory, and an explicit per-case flag allows a library to decline an unsupported size. The YAML brackets element-index, byte-count, batch-stride and launch-grid boundaries instead of choosing large sizes without a numerical reason.

## Actionable items

No additional source defect identified in this incremental layer. The memory helper's query-failure fallback, filter behavior, argument serialization/defaults, no-solution exits and category registration were inspected. The stress category is picked up by generic test instantiation, and its CTest tier supplies the selecting filter.

## Suggestions

No local code suggestion. Treat the memory calculation as preflight guidance: free memory can change before allocation, and it is not a reservation. Record actual executed/skipped counts for the stress tier on a suitable runner; the tier name alone does not schedule a weekly job.

## Commentary

The appropriate levels are helper tests, YAML generation and targeted large-memory kernel runs. New large tests are explicitly selected, and known defects have issue-linked, time-boxed entries. This diff introduces stress cases rather than removing an established test family from its old tier. It does not justify claiming routine CI exercises those new boundaries.

The review branch has no additional commits. Full large-memory runs were omitted intentionally. The published branch records the reviewed head.
