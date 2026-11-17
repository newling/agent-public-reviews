This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15958](https://github.com/ROCm/rocm-libraries/pull/15958)

**Reviewed head:** `038ff8c7adc12889f5fc1cf70eed61aa4cc9391f`. **Comparison base:** `983ec8196de2be42c1cc55a014e578481c7f8cc2` (#15957).

**Scope:** Independent review of kernel submission order, result association, and the evidence for a scheduling heuristic. Existing PR reviews, inline threads, and discussion were not used. The [stack review](review_pr15954_stack.md) covers combined behavior and shared alternatives.

## Tests

The examined generation, compile-group, and linking consumers are covered by the 324 passing focused tests on the submitted combined stack. A four-file gfx942 build with two jobs generated all 11 files byte-identical to the baseline, including the helper code object and selection metadata.

The build included four unique kernels and exercised a shuffled kernel list. No repeated performance comparison isolating this PR was run. The description's full-build results compare develop with all five PRs.

## Summary

The change at [the kernel submission list](https://github.com/ROCm/rocm-libraries/blob/038ff8c7adc12889f5fc1cf70eed61aa4cc9391f/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L1000) shuffles unique assembly kernels with a fixed seed. Given the same input list, the permutation repeats; actual worker completion order still depends on execution timing.

Kernels previously followed library/source-file ordering, which can put many memory-heavy kernels together. Shuffling is an inexpensive way to reduce those clusters. Results remain paired with the shuffled list, downstream metadata is associated by kernel name, and linking sorts object-file inputs.

This is a reasonable heuristic. It does not bound memory, and a workload dominated by large kernels can still occupy every worker with a large task.

## Actionable items

None identified in the examined ordering and result-association paths.

## Suggestions

### Record the shuffle's individual effect

Compare #15957 with this PR using identical inputs, worker count, cache settings, and sampler revision. Report each repeated run's peak summed PSS and elapsed time, together with run order. Compare a lower worker count as a simple alternative.

The reported 97.1 → 29.8 GiB PSS and 1,506 → 1,070 seconds are whole-stack observations. They do not isolate the shuffle. Include a workload with a different mixture of expensive kernels so the conclusion does not depend on one favorable ordering.

### Check the tradeoff with starting long jobs early

Starting long-running jobs early can reduce the final period when most workers are idle and a few jobs remain. Starting memory-heavy jobs together can instead increase peak RAM. Generation duration and peak memory are distinct scheduling costs, so measure both outcomes.

The inspected original ordering follows library/source filenames; it does not implement an explicit longest-job-first policy. Shuffling therefore replaces that inherited grouping, not a demonstrated duration-based scheduler.

## Scope decisions

Splitting large YAML inputs is a separate parsing/pipeline candidate. Parsing tasks operate per file, so smaller files could reduce parse memory and improve load balance. At this stage, however, each generation task already handles one kernel. Splitting files does not split a large kernel-generation task.

A scheduler that considers memory, or an ownership redesign that processes bounded batches through the pipeline, would be broader work. Keep the fixed shuffle as a comparator; do not treat it as proof that a stated RAM budget will be met.

**Handoff:** There are no suggestion commits for this PR. The ordering change passed the scoped correctness checks; its individual performance benefit remains unmeasured.
