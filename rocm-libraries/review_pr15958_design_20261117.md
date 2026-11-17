This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15958](https://github.com/ROCm/rocm-libraries/pull/15958)

**Reviewed head:** [5a5326702711f4375e5a263fa85776015047c0e0](https://github.com/ROCm/rocm-libraries/commit/5a5326702711f4375e5a263fa85776015047c0e0). **Comparison base:** [ed456253fbc4eebacb12ed0254e3650cbde4521e](https://github.com/ROCm/rocm-libraries/commit/ed456253fbc4eebacb12ed0254e3650cbde4521e).

**Scope:** Follow-up review of kernel submission order, result association, scheduling tradeoffs and the latest motivation, considering the earlier published review, discussion on the accepted sampler prerequisite #15954, and the author's responses. This review covers the PR's own layer and its interactions with #15955–#15958. The sampler's accepted design is not reopened.

## Tests

The submitted stack at [5a5326702711](https://github.com/ROCm/rocm-libraries/commit/5a5326702711f4375e5a263fa85776015047c0e0) passed 300 focused tests covering representations, compile groups, driver orchestration, and library parsing/serialization. The final combined suggestions at [0d196f6a03ad](https://github.com/newling/rocm-libraries/commit/0d196f6a03ad5bc05736e7343c1fb710e6c09b3b) pass 302 tests with 103 saved-result comparisons. Four checked-in gfx942 Equality inputs, four assembly kernels and 14 helper objects, using two workers, compressed MessagePack and disabled helper caching, produce 11 byte-identical library files between submitted and suggested code. Both builds use the same output path and report zero compact-solution fallback reads in the parent. This is a small correctness comparison, not a performance measurement.

Applicable root pre-commit hooks pass. Flake8 reports the same seven pre-existing diagnostics in the driver on both revisions. Live checks are mixed: the latest normal Multi-Arch summary passes, while Math CI and the policy bot report failures and component coverage/ASAN work remains incomplete. This review does not establish a cause for every CI failure or claim merge readiness.

The small build exercises the actual shuffled generation queue and metadata association. It does not measure whether the permutation lowers peak memory or improves load balance on the full architecture workload.

## Summary

The fixed-seed shuffle is a small, understandable heuristic for breaking up clusters of expensive kernels inherited from logic-file order. The driver returns the same shuffled list alongside ordered results, associates metadata by kernel identity, and links sorted object inputs. Those relationships preserve output association.

The author's new CU-subset experiment answers the earlier tail question for that workload: with 1,449 kernels and 96 workers, the generation phase changes from 15.5 to 10.4 seconds and the reported first-idle-worker-to-last-completion tail changes from 3.7 to 1.1 seconds. The fixed seed repeats the input permutation; it does not make worker completion timing deterministic.

I would keep this simple heuristic rather than require a new duration estimator or memory-aware scheduler. The earlier ordering was based on library/source files, so it had no established longest-job-first property to preserve.

## Actionable items

None newly demonstrated in ordering or result association.

## Suggestions

### Shuffle the list already constructed by the driver

**Location:** [the shuffle](https://github.com/ROCm/rocm-libraries/blob/5a5326702711f4375e5a263fa85776015047c0e0/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L1000).

`uniqueAsmKernels` is already a new list comprehension containing the group representatives. No caller owns that list yet. Commit [482000d02bf2](https://github.com/newling/rocm-libraries/commit/482000d02bf21f4e9e06624ec91f3d5bacae016a) removes the redundant `list(uniqueAsmKernels)` before shuffling; it preserves the permutation and group list.

### Measure the shuffle's memory effect separately

The new timing/tail result improves the motivation, but the PR still lacks an isolated peak-memory comparison. Compare #15957 with #15958 using identical inputs, concurrency, cache settings and sampler revision. Show individual repeated peaks/timings and run order; include a lower-concurrency run if the intended tradeoff is meeting a memory limit.

The whole-stack 97.1-to-29.8 GiB PSS result cannot establish this shuffle's contribution. The one reported timing pair is exploratory, and a shuffled queue is not a memory bound: a workload dominated by large kernels can still run a large kernel on every worker.

**Suggestion branch:** [review/pr15958-design-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15958-design-20261117), based on the reviewed head, contains [482000d02bf2](https://github.com/newling/rocm-libraries/commit/482000d02bf21f4e9e06624ec91f3d5bacae016a) (remove redundant list copy). It is included in combined branch [review/pr15955-stack-design-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15955-stack-design-20261117) at [0d196f6a03ad](https://github.com/newling/rocm-libraries/commit/0d196f6a03ad5bc05736e7343c1fb710e6c09b3b). No new scheduling policy or repeated performance benchmark was implemented.
