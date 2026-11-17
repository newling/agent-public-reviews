This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15954](https://github.com/ROCm/rocm-libraries/pull/15954)

**Reviewed head:** `f79ae667a7004e7b9544e91568cc8c6da643a6ff`. **Comparison base:** `02e193968b5183d447706cacce65c14e70452098` (merge base with develop).

**Scope:** Independent review of the optional process-tree memory sampler, its measurement limits, and command lifetime. Existing PR reviews, inline threads, and discussion were not used. The [stack review](review_pr15954_stack.md) covers combined behavior and shared alternatives.

## Tests

The submitted sampler passed 34 tests covering phase labels, process classes, PID reuse, accounting, exit status, and signal forwarding. A new regression reproduced an output-error cleanup failure on this head; all 35 sampler tests pass with the suggested fix. Relevant root pre-commit hooks and Python lint pass for the sampler and its tests.

No full-build sampling-overhead or interval-sensitivity experiment was performed.

## Summary

This script runs a command and samples the memory of its live descendants. It is an optional diagnostic wrapper; normal library generation does not invoke it or consume its results.

The central metric is the maximum sampled sum of proportional set size (PSS), which apportions shared resident pages among the processes mapping them. It is a peak, not a memory-time integral. The CSV could support a separate time-integrated metric.

Phase and process-class attribution are useful for distinguishing parent data from worker and compiler memory. The updated implementation addresses PID reuse and forwards signals to the command's process group. One failure path still leaves the command running.

## Actionable items

### Stop the monitored command when output handling fails

**Location:** [memwatch.py:458](https://github.com/ROCm/rocm-libraries/blob/f79ae667a7004e7b9544e91568cc8c6da643a6ff/projects/hipblaslt/tensilelite/scripts/memwatch.py#L458).

If `log.write()` or forwarding stdout raises, execution bypasses `proc.wait()`, sampler shutdown, and cleanup of the new process group. The wrapper exits while the monitored build continues consuming resources.

A child that prints one 64 KiB line and then sleeps reproduces this with `--quiet --log /dev/full`: memwatch exits with ENOSPC, but the child remains alive in the sleeping state. This models a full log filesystem without filling the test filesystem.

**Suggested fix:** Commit [bb41321189a](https://github.com/newling/rocm-libraries/commit/bb41321189ae55ce260a0710d06a3f29015eea0d) terminates the owned process group and waits for the command before propagating an output-handling exception; sampler shutdown and log closing run in `finally`. Its subprocess regression fails on the submitted implementation and passes with the fix.

## Suggestions

### Establish the sampling interval and collection overhead

**Location:** [the 0.5-second default](https://github.com/ROCm/rocm-libraries/blob/f79ae667a7004e7b9544e91568cc8c6da643a6ff/projects/hipblaslt/tensilelite/scripts/memwatch.py#L407) and [sample()](https://github.com/ROCm/rocm-libraries/blob/f79ae667a7004e7b9544e91568cc8c6da643a6ff/projects/hipblaslt/tensilelite/scripts/memwatch.py#L208).

The default is configurable, but the description supplies no interval-selection or sensitivity evidence. Compare progressively shorter intervals on a representative build and report both sampled peaks and the wrapper's effect on elapsed time. Mean collection time alone does not show whether short peaks were missed or whether monitoring slowed the workload.

### Compare existing collection tools and state the accounting boundary

Compare this collector with a small `psutil` wrapper or `mprof --include-children --backend psutil_pss`. The latter already offers recursive PSS collection, although its upstream project is no longer actively maintained. A standard-library-only script with local phase reporting may still be the preferable choice; make that tradeoff explicit.

For CI memory-limit decisions, complement process PSS with a dedicated job cgroup's accounting. PSS apportions pages shared outside the tree too, and it excludes unmapped file cache and other cgroup charges. Individual processes are sampled at different instants. Also preserve the class breakdown at the total-peak sample: independent per-class maxima cannot be added to reconstruct that instant.

## Scope decisions

The sampler is independently useful and is not a production prerequisite for the four memory optimizations. Replacing its collector or adding cgroup support remains a design choice; neither was implemented in this review.

**Suggestion branch:** [review/pr15954-20261116](https://github.com/newling/rocm-libraries/tree/review/pr15954-20261116), based on the reviewed head, contains the one cleanup-fix commit above. Sampling sensitivity and full-build overhead remain unmeasured.
