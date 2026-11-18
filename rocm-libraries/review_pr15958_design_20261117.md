This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15958](https://github.com/ROCm/rocm-libraries/pull/15958)

**Reviewed head:** [6380ad270e8f](https://github.com/ROCm/rocm-libraries/commit/6380ad270e8f8cefbf58a0babfb0226069e914c7). **Comparison base:** [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) at [d203c9964aa2](https://github.com/ROCm/rocm-libraries/commit/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9).

**Scope:** Follow-up review of kernel submission order, result association, scheduling tradeoffs and the measured effect on memory and time, considering the earlier published review, the discussion on the accepted sampler prerequisite [#15954](https://github.com/ROCm/rocm-libraries/pull/15954), and the author's responses. This review covers the PR's own layer and its interactions with [#15955](https://github.com/ROCm/rocm-libraries/pull/15955)–[#15957](https://github.com/ROCm/rocm-libraries/pull/15957). The sampler's accepted design is not reopened. It was first written for [5a5326702711](https://github.com/ROCm/rocm-libraries/commit/5a5326702711f4375e5a263fa85776015047c0e0); this PR's layer diff is byte-identical at the current head.

## Tests

At the reviewed head, 217 focused compact-solution, matching-table, worker-pool, library-IO and driver characterization tests pass, as they do on this PR's suggestion branch. An earlier revision of this review compared a small gfx942 build: four Equality logic files at two jobs produced 11 byte-identical library files between submitted and suggested code, exercising the actual shuffled generation queue and metadata association.

The shuffle's memory effect was measured on the description's six-file CU subset ([`gfx942*/GridBased/aquavanjaram_Cijk_Ailk_Bjlk_BBS_BH_Bias_HAS_SAV_UserArgs`](https://github.com/ROCm/rocm-libraries/tree/6380ad270e8f8cefbf58a0babfb0226069e914c7/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full/aquavanjaram), 1,449 kernels). Each run was a complete library generation under [`scripts/memwatch.py`](https://github.com/ROCm/rocm-libraries/blob/6380ad270e8f8cefbf58a0babfb0226069e914c7/projects/hipblaslt/tensilelite/scripts/memwatch.py) at 32 jobs, with the helper cache disabled and ROCm 7.1 tools. There were five pairs of [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) (file order) and this PR (shuffled), alternating which ran first.

## Summary

The fixed-seed shuffle is a small, understandable heuristic for breaking up clusters of expensive kernels inherited from logic-file order. The driver returns the same shuffled list alongside ordered results, associates metadata by kernel identity, and links sorted object inputs. Those relationships preserve output association.

The author's CU-subset experiment at 96 workers answers the tail question for that workload. The generation phase changes from 15.5 to 10.4 seconds, and the reported time from the first idle worker to the last completion changes from 3.7 to 1.1 seconds. The fixed seed repeats the input permutation; it does not make worker completion timing deterministic.

The paired measurement shows a consistent but modest memory effect at 32 workers:

| Pair | 1 | 2 | 3 | 4 | 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| File order first | 1 | 0 | 1 | 0 | 1 |
| File order peak summed PSS (GiB) | 5.304 | 5.279 | 5.313 | 5.321 | 5.245 |
| Shuffled peak summed PSS (GiB) | **4.898** | **5.115** | **5.211** | **5.048** | **5.136** |
| File order codegen (s) | 16.1 | 16.0 | 16.1 | 15.8 | 16.0 |
| Shuffled codegen (s) | **14.5** | **14.5** | **14.5** | **14.3** | **14.2** |

The shuffle lowered the peak in every pair, by 0.21 GiB on average, about 4% (paired t = 3.66 with 4 degrees of freedom; 95% interval 0.05–0.37 GiB). Codegen was 1.6 seconds shorter in every pair. I would keep the shuffle. The description should present it as trimming the codegen spike and mainly shortening the tail. On this subset, it does not remove the spike that the description identifies as the build's peak. A workload dominated by large kernels can still run a large kernel on every worker.

I would not require a duration estimator or memory-aware scheduler. The earlier ordering followed library/source files, so it had no established longest-job-first property to preserve.

## Actionable items

None found in ordering or result association.

## Suggestions

### Shuffle the list already constructed by the driver

**Location:** [the shuffle](https://github.com/ROCm/rocm-libraries/blob/6380ad270e8f8cefbf58a0babfb0226069e914c7/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L1003).

[`uniqueAsmKernels`](https://github.com/ROCm/rocm-libraries/blob/6380ad270e8f8cefbf58a0babfb0226069e914c7/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L926) is already a new list comprehension containing the group representatives, and no caller owns it yet. Commit [9b5109841d35](https://github.com/newling/rocm-libraries/commit/9b5109841d352d830ce0c4cf394fc0ab7f9f0305) removes the redundant [`list(uniqueAsmKernels)`](https://github.com/ROCm/rocm-libraries/blob/6380ad270e8f8cefbf58a0babfb0226069e914c7/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L1002) before shuffling; it preserves the permutation and group list.

### Report the measured memory effect at the build's concurrency

The pairs above settle the earlier request for an isolated memory comparison at 32 workers on the CU subset. The description's whole-stack 97.1-to-29.8 GiB result cannot show this PR's contribution. Repeating the pairs at the 96 jobs used in the description, on the same subset, would show whether the effect grows with concurrency. That is where clustering large kernels should matter most.

**Suggestion branch:** [review/pr15958-design-20261118](https://github.com/newling/rocm-libraries/tree/review/pr15958-design-20261118), based on the reviewed head, contains [9b5109841d35](https://github.com/newling/rocm-libraries/commit/9b5109841d352d830ce0c4cf394fc0ab7f9f0305) (remove redundant list copy). The suggestions for all four PRs are combined on [review/pr15955-stack-deep-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15955-stack-deep-20261117); [compare it with the current stack tip](https://github.com/newling/rocm-libraries/compare/6380ad270e8f8cefbf58a0babfb0226069e914c7...6c5211fb9c646ef6bc6c90a0ed93cb74832edb50). No new scheduling policy was implemented.
