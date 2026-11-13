This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14788](https://github.com/ROCm/rocm-libraries/pull/14788), “perf(tensilelite): wave-parallel group search in grouped GEMM kernels”

**Reviewed head:** [578a8adc142a](https://github.com/ROCm/rocm-libraries/commit/578a8adc142a3b3a97a1d786b8a168afa372495a)

**Diff base:** [2db5a46d36e0](https://github.com/ROCm/rocm-libraries/commit/2db5a46d36e0110d3b2eaa7ef57dc7575413d244)

**Suggestion branch:** [review/pr14788-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14788-suggestions), based directly on the reviewed head.

**Scope:** Independent review of the six changed files, the grouped GEMM launch and selection paths, and emitted search code. The PR's discussion and reviews were not consulted. The published head was unchanged at the final check.

## Tests

The submitted chunk-budget suite passed (27 tests). After the suggested fix, those 27 tests still passed; the two new GPU tests skipped on the local gfx1201 host, which is outside the search's supported architectures. Black, the root pre-commit hooks, new-test flake8, and whitespace checks passed. The large generator file has 103 existing flake8 diagnostics, with the same diagnostic set before and after the fix.

On physical gfx942, a small HIP driver executed the **actual emitted search** with the regression test's headers and queries. Across 18 cases and 3,522 queries for each of one and six chunks per load, the submitted code produced 44 mismatching output words per variant; the fix produced zero. Ordinary 2–1,000-group boundary cases passed on both revisions. This executes the test payload, not the Python pytest wrapper, and does not allocate or run a full large GEMM.

Full grouped GEMM kernels from both new configurations emitted and assembled for gfx942 and gfx950 on both revisions. Their reported VGPR, SGPR, and LDS usage did not change. Published CI also shows the new [gfx950 65/400-group and pre-swizzled cases](https://github.com/ROCm/rocm-libraries/actions/runs/43486438436/job/132124111221) and [gfx942 grouped configurations](https://github.com/ROCm/rocm-libraries/actions/runs/43486438436/job/132127495458) passing. Separate [gfx950](https://github.com/ROCm/rocm-libraries/actions/runs/43486435347/job/132197568183) and [gfx942](https://github.com/ROCm/rocm-libraries/actions/runs/43486435347/job/132197567684) ASAN jobs stopped at allocator checks in other test bodies; this review did not establish their baseline behavior or attribute those failures to this PR.

## Summary

The optimization replaces a serialized load-and-wait loop with independent header loads across a wave's lanes. Each lane computes one group's tile count; a prefix scan identifies the owning group, whose metadata is then copied into scalar registers. Each wave still repeats the lookup, but up to six chunks of 64 headers can be loaded before waiting. The existing argument layout and the state expected by the remainder of the kernel are preserved.

This targets launches with many groups and little useful work per group, including empty groups and surplus workgroups. The benefit comes from overlapping memory requests, not merely reducing arithmetic. The implementation retains the existing scalar behavior where its architecture, division, GSU, or register assumptions do not apply. I found one correctness defect in the new tile-count arithmetic, described below.

## Actionable items

### Preserve the full tile count when a dimension approaches `UINT32_MAX`

At [KernelWriterAssembly.py:3503](https://github.com/ROCm/rocm-libraries/blob/578a8adc142a3b3a97a1d786b8a168afa372495a/projects/hipblaslt/tensilelite/tensilelite/KernelWriterAssembly.py#L3503), `ceil(N / MT1)` is computed by adding `MT1 - 1` in 32 bits before shifting. For `N = 0xfffffff1` and `MT1 = 16`, that sum wraps to zero, although the correct tile count is 268,435,456. The [public `UserArguments` layout](https://github.com/ROCm/rocm-libraries/blob/578a8adc142a3b3a97a1d786b8a168afa372495a/projects/hipblaslt/library/include/hipblaslt/hipblaslt-ext.hpp#L397) stores N as `uint32_t`, and [the host argument limit](https://github.com/ROCm/rocm-libraries/blob/578a8adc142a3b3a97a1d786b8a168afa372495a/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/rocblaslt_mat_utils.hpp#L298) permits values through `UINT32_MAX`.

A concrete search case has 66 groups, all initially `(M,N,batch,K) = (1,1,1,0)`, with group 64's N changed to `0xfffffff1`, 16×16 tiles, and GSU 1. Workgroup 64 belongs to group 64, whose inclusive tile prefix is 268,435,520. The submitted search reports group 65 with tile count 1 and prefix 65. A valid workgroup can therefore use another group's arguments and leave its intended output tile unwritten.

Compute the quotient first and add one only when the low tile bits are nonzero. [Commit 79d36d56a49b](https://github.com/newling/rocm-libraries/commit/79d36d56a49bdb58f41fbedb3a680df7dc0e92ab) implements that fix with existing scratch registers and adds a GPU regression for chunk boundaries, GSU, empty dimensions, and both overflow edges. It is available on the suggestion branch based directly on the reviewed head.

## Suggestions

### Make the headline timing reproducible on the corrected code

For the PR description's 384-group, one-token down projection on MI355X (2,313 µs to 129 µs), provide the harness command, selected kernel and tile/GSU configuration, actual launch workgroup count, and repeated timing samples. The stated 0.4 µs per serialized header step gives about 154 µs for one complete 384-group search; the launch grid and scheduling determine how that cost becomes milliseconds across the kernel. The timing table alone does not establish that breakdown, and this review did not independently reproduce it.

Re-run that case with the suggested correction to the [tile-count arithmetic](https://github.com/ROCm/rocm-libraries/blob/578a8adc142a3b3a97a1d786b8a168afa372495a/projects/hipblaslt/tensilelite/tensilelite/KernelWriterAssembly.py#L3501). The suggestion adds four VALU instructions per 64-header search chunk without changing reported register or LDS usage. Keep the separate host heuristic timing improvement distinct from GPU execution time.

## Scope decisions

**Retain the scalar fallback within the stated coverage.** The [generation-time selector](https://github.com/ROCm/rocm-libraries/blob/578a8adc142a3b3a97a1d786b8a168afa372495a/projects/hipblaslt/tensilelite/tensilelite/KernelWriterAssembly.py#L3412) requires gfx942/gfx950, wave64, power-of-two macro tiles, and enough temporary VGPRs without lowering estimated occupancy. It excludes active GSU modes requiring per-group `MultipleBufferSingleKernel` or `AdaptiveGemmGSUA` bookkeeping. Other configurations keep the scalar loop. Eligible kernels use the wave search for every group count above one; a single group uses direct scalar setup. The power-of-two restriction comes from shift-based division, not from prefix searching itself. Broadening division support, porting the excluded GSU behavior, and extending architecture coverage are separate work; the description states no plan to retire the fallback. Removing it is not necessary to fix the demonstrated defect.

**Precomputed intervals remain a viable design alternative.** For host-known shapes, [launch preparation already writes a `wgTable` of group starting indices](https://github.com/ROCm/rocm-libraries/blob/578a8adc142a3b3a97a1d786b8a168afa372495a/projects/hipblaslt/tensilelite/src/ContractionSolution.cpp#L4139), which the generated search skips. The [device-shape C API](https://github.com/ROCm/rocm-libraries/blob/578a8adc142a3b3a97a1d786b8a168afa372495a/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_grouped_matmul.cpp#L4) instead sizes the grid from host bounds and packs actual headers on the GPU. Its interval table would need to reflect the current device shapes and selected tile/GSU configuration. A prefix scan during preparation could produce that table once, allowing cheaper lookup and immediate rejection of surplus workgroups. A conservatively sized grid does not prevent this approach. Reusing the existing table where valid and producing equivalent device metadata deserve an end-to-end timing comparison; neither replacement is implemented here because this is an unmeasured design alternative, not a demonstrated requirement for this patch.

The hardware probe establishes search behavior without allocating a multi-gigabyte output matrix; full GEMM execution at the extreme dimension and throughput remain unverified. `develop` has advanced in overlapping generator and GSU code since the reviewed base, so integration should rebase and rerun the targeted validation.

**Suggestion handoff:** The published [suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr14788-suggestions) contains [one commit implementing the overflow fix and regression](https://github.com/newling/rocm-libraries/commit/79d36d56a49bdb58f41fbedb3a680df7dc0e92ab). The [comparison from the reviewed head](https://github.com/newling/rocm-libraries/compare/578a8adc142a3b3a97a1d786b8a168afa372495a...79d36d56a49bdb58f41fbedb3a680df7dc0e92ab) shows only that suggestion. The timing and preprocessing proposals remain suggestions; their validation limits are described above.
