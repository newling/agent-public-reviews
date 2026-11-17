This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15954](https://github.com/ROCm/rocm-libraries/pull/15954) and its four dependent PRs, #15955–#15958.

**Scope:** Independent review of the stack's architecture, memory ownership, worker lifetime, measurement, compatibility, and alternatives. Existing PR reviews, inline threads, and discussion were not used. Individual reviews below own the detailed findings.

| PR | Purpose | Reviewed head | Review |
| --- | --- | --- | --- |
| [#15954](https://github.com/ROCm/rocm-libraries/pull/15954) | Memory sampler | `f79ae667a7004e7b9544e91568cc8c6da643a6ff` | [Individual review](review_pr15954.md) |
| [#15955](https://github.com/ROCm/rocm-libraries/pull/15955) | Worker reclamation | `ce77601f65f3fc6822a5a1165e1eb3112528f954` | [Individual review](review_pr15955.md) |
| [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) | Compressed solutions | `de6d67095491a77bbea99799a0b2ec740093cd91` | [Individual review](review_pr15956.md) |
| [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) | Column matching tables | `983ec8196de2be42c1cc55a014e578481c7f8cc2` | [Individual review](review_pr15957.md) |
| [#15958](https://github.com/ROCm/rocm-libraries/pull/15958) | Kernel shuffle | `038ff8c7adc12889f5fc1cf70eed61aa4cc9391f` | [Individual review](review_pr15958.md) |

The stack merge base is `02e193968b5183d447706cacce65c14e70452098`. Each subsequent PR was compared with the preceding head above. Develop was checked at `589cc4657e0ddf1539763c9367311102d07479f5`; its changes since the merge base do not overlap the stack's changed paths.

## Tests

On the submitted stack, the updated sampler passed 34 tests and the examined representation/consumer paths passed 324 tests. After integrating the suggestions, all 359 focused tests passed, including the new sampler regression. Relevant root pre-commit hooks pass. Targeted flake8 reports seven inherited driver diagnostics, versus eight at the merge base; the suggestions add none.

A real two-worker experiment confirmed that phase shutdown ends the existing workers and the next phase creates different workers. The sampler's output-error regression failed on the submitted code and passed with the fix.

A correctness build used four checked-in gfx942 Equality logic files, two jobs, lazy libraries, compressed MessagePack metadata, ROCm 7.1.0/AMD Clang 20, and disabled helper caching. The baseline generator and submitted stack produced 11 byte-identical files: four assembly code objects, one helper code object, and six metadata files. The parent fallback counter was zero. Both runs used the same output path to avoid the compiler's path-derived helper identifier. The baseline generator was run on the sampler suggestion branch, whose changes do not alter generation.

No full-architecture build, repeated large-build memory comparison, pipeline prototype, or GPU execution was performed locally. The small build checks output preservation, not the claimed memory reduction. Current component checks included queued builds; earlier builds demonstrate the NumPy integration failure described below. A refreshed policy failure cited a cancelled pre-commit check, not a new source failure.

## Summary

The goal is to reduce the host RAM needed to build a device library while preserving kernels and selection metadata. Three different costs matter: live data retained by the parent, allocator pages retained by workers, and simultaneous temporary allocations during generation. The stack addresses each separately.

A generator Solution is an in-memory kernel configuration with derived state. A matching table connects problem sizes to the solutions selected at runtime. They have different memory costs and can be represented independently.

```text
YAML files
  → parsing workers construct solutions and matching tables
  → parent collects, merges, assigns indices, and deduplicates
  → stop parsing workers                         [PR 2]
  → prepare kernel jobs
      main kernels: fresh workers → assembly → object files
                    trim after each kernel        [PR 2]
                    stop the generation pool      [PR 2]
                    link/bundle objects → .co
      helpers: compile C++ concurrently → .hsaco
  → wait for both paths
  → update and write selection metadata
      lazy-library files can use another worker pool

PR 3 reduces retained generator state in the parent.
PR 4 reduces retained matching-table state in the parent.
PR 5 changes the order of the per-kernel generation jobs.
PR 1 observes the run when explicitly used as a wrapper.
```

Phase-boundary worker shutdown and compact numeric tables have clear ownership and purpose. Compressed solutions are a plausible incremental approach, but their compatibility facade deserves closer design scrutiny. Shuffling is a useful baseline for reducing clusters of large tasks; it provides no hard memory bound.

The author reports the following full gfx942 comparison, using 843 logic files, 356,190 solutions, 214,059 kernels, 96 jobs, and disabled helper caching:

| Metric | Develop | Entire stack |
| --- | ---: | ---: |
| Peak summed PSS | 97.1 GiB | 29.8 GiB |
| Peak summed RSS | 101.5 GiB | 34.2 GiB |
| Elapsed time | 1,506 s | 1,070 s |

These are reported observations from the whole stack, not independently reproduced results or measurements of each PR. The full comparison predates compatibility refinements and the newer sampler fixes. The description reports subset checks after the compatibility refinements. Independent process-class peaks occur at potentially different times and cannot be added to reconstruct the total peak.

## Actionable items

### Resolve the matching-table dependency in source builds

PR 4 activates NumPy during source-build logic validation. Earlier gfx942 and gfx950 jobs failed because their build interpreter lacked it. TensileLite already declares the package, so the fix must reach the interpreter used by the consuming build or change the representation's dependency policy. Current source still contains the same unconditional import. See the [PR 4 review](review_pr15957.md) for the exact paths, job evidence, and disposition.

### Clean up the monitored build after a sampler output failure

PR 1 can exit on a log-write failure while its command continues in a separate process group. The suggestion terminates that group before propagating the exception and includes a regression that fails without the fix. See the [PR 1 review](review_pr15954.md).

## Suggestions

### Establish the contribution of each mechanism

Use identical inputs and a common sampler for staged comparisons. Record individual repeated peaks and timings with run order. The useful comparisons are:

| Comparison | Question answered |
| --- | --- |
| Baseline → phase shutdown only | How much idle worker memory does process exit reclaim, and what does restarting cost? |
| Phase shutdown → shutdown plus trim | Does per-kernel allocator work justify its cost? |
| PR 2 → PR 3 | How much parent memory does compaction save, at what compression/expansion cost? |
| PR 3 → PR 4 | How much do column tables save, including conversion and serialization peaks? |
| PR 4 → PR 5 | Does the shuffle reduce the peak without an unacceptable completion-time tradeoff? |
| Fixed implementation, lower job count | How much of the goal can be met by the existing concurrency control? |

PR 4's several-hundred-bytes → under-50-bytes estimate per row is not an isolated build measurement. PR 5's whole-stack result does not establish the shuffle's benefit. Include a different expensive-kernel mix, and verify outputs at the measured heads.

### Keep expansion and temporary representations explicit

A small parent record with explicit expansion is an alternative to a general mapping wrapper that can silently retain a full Solution after four fallback reads. The current parent count was zero on the small local build, so this is a design tradeoff rather than a demonstrated current-path regression.

For matching tables, construct columns directly before considering a larger serializer redesign. The current implementation builds and sorts the old rows, converts and sorts again, and expands dictionaries during writing. Those temporary allocations matter to the peak even when retained storage is compact.

### Evaluate the sampler as a measurement instrument

The 0.5-second interval is configurable but lacks a documented sensitivity study. Measure collection overhead and compare shorter intervals. Existing psutil/mprof collection can serve as a comparator; dedicated cgroup accounting better answers whether the CI job fits its enforced memory limit. The reported PSS figure is a sampled maximum, not an integral over time.

## Scope decisions

### Consider a bounded YAML-to-object pipeline as a separate ownership design

The parent currently waits for all parsing, then generates kernels. The inspected paths show global organization requirements, but do not establish a fundamental need to retain every full generator Solution before any kernel can be emitted.

Workers could keep full generator state while producing object files, returning compact runtime metadata and artifact references. Such a design must preserve deterministic indices, fallback handling, selection tables, code-object placement, and metadata returned by code generation.

Duplicate selection is particularly important. The driver chooses a first representative, and distinct register-allocation configurations can share an emitted name. Independent workers must preserve that choice and avoid writing colliding artifact paths, or stage alternatives and select deterministically later. Moving generation into workers does not remove retained table memory or simultaneous worker peaks.

This alternative is recorded for evaluation, not presented as a validated replacement or a prerequisite for every incremental saving.

### Treat YAML splitting and kernel scheduling as different changes

Splitting large YAMLs upstream could reduce per-file parsing memory and improve parsing load balance. Generation already queues individual kernels, so file splitting does not divide a single memory-heavy generation task. It also needs care where source filenames influence indices and library placement. A separate parsing/pipeline PR is a reasonable place to investigate it.

Starting long jobs early can reduce a slow tail, while starting memory-heavy jobs together can increase the peak. The current pre-shuffle order follows library/source filenames; it is not an explicit longest-job-first scheduler. Measure duration and memory separately before choosing a more elaborate scheduler. Keep the fixed-seed shuffle as a comparator.

### Keep the dependency choices separate from the Git stack

The sampler is optional. Worker cleanup and shuffling can be evaluated independently of the two representations, and column tables do not conceptually depend on compressed solutions. Their current Git order need not force a single decision about all five mechanisms.

## Suggestions and handoff

| PR | Individual suggestion branch | Commit and purpose |
| --- | --- | --- |
| #15954 | [review/pr15954-20261116](https://github.com/newling/rocm-libraries/tree/review/pr15954-20261116) | [bb41321189a](https://github.com/newling/rocm-libraries/commit/bb41321189ae55ce260a0710d06a3f29015eea0d): stop the command after an output-handling failure |
| #15955 | [review/pr15955-20261116](https://github.com/newling/rocm-libraries/tree/review/pr15955-20261116) | [8548fab3f6b](https://github.com/newling/rocm-libraries/commit/8548fab3f6bc3513d26b33cf4293a3569701cf21): correct allocator-reclamation comments |
| #15956 | [review/pr15956-20261116](https://github.com/newling/rocm-libraries/tree/review/pr15956-20261116) | [9eef4dd50a7](https://github.com/newling/rocm-libraries/commit/9eef4dd50a729cabf115edd63a2d3130a6f9a8c7): remove duplicate test-only naming helpers |
| #15957 | — | No commits; dependency/integration choice remains open |
| #15958 | — | No commits; individual performance evidence remains missing |

The combined branch [review/pr15954-stack-20261116](https://github.com/newling/rocm-libraries/tree/review/pr15954-stack-20261116) is based on submitted stack head `038ff8c7adc12889f5fc1cf70eed61aa4cc9391f`. It contains corresponding cherry-picks [d004315f4c0](https://github.com/newling/rocm-libraries/commit/d004315f4c0d91030db7bdf7aa3906204ca1ee80), [fe23bcaad5c](https://github.com/newling/rocm-libraries/commit/fe23bcaad5ca0055d32e13c854b7e34e483c7e8a), and [51bb9ad4889](https://github.com/newling/rocm-libraries/commit/51bb9ad488918557e3c75371451465433e7a520f), in that order.

[Compare the combined suggestions with the submitted stack](https://github.com/newling/rocm-libraries/compare/038ff8c7adc12889f5fc1cf70eed61aa4cc9391f...51bb9ad488918557e3c75371451465433e7a520f).

This review is complete for the scope above. Full-build performance attribution, consuming-environment provisioning, and the larger pipeline alternative remain explicit review requests or design choices; no corresponding implementation or benchmark claim is made.
