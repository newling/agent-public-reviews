This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15955](https://github.com/ROCm/rocm-libraries/pull/15955)

**Reviewed head:** [2c0dca1cadae](https://github.com/ROCm/rocm-libraries/commit/2c0dca1cadae2b1edeb0a9faae6de03fc829ad3b). **Comparison base:** [#15954](https://github.com/ROCm/rocm-libraries/pull/15954) at [c58a28ab7985](https://github.com/ROCm/rocm-libraries/commit/c58a28ab7985b71a033d61ec2c3d0c4687c1448b).

**Scope:** Follow-up review of worker lifetime, allocator reclamation and their measured motivation, considering the earlier published review, the discussion on the accepted sampler prerequisite [#15954](https://github.com/ROCm/rocm-libraries/pull/15954), and the author's responses. This review covers the PR's own layer and its interactions with [#15956](https://github.com/ROCm/rocm-libraries/pull/15956)–[#15958](https://github.com/ROCm/rocm-libraries/pull/15958). The sampler's accepted design is not reopened. It was first written for [1e7247af13fc](https://github.com/ROCm/rocm-libraries/commit/1e7247af13fc20cd2ec7c64b996925fa53348996) and has been rechecked at the current head, which adds a warning for a missing loky attribute and a test file.

## Tests

At the current stack tip ([#15958](https://github.com/ROCm/rocm-libraries/pull/15958) at [6380ad270e8f](https://github.com/ROCm/rocm-libraries/commit/6380ad270e8f8cefbf58a0babfb0226069e914c7)), 217 focused compact-solution, matching-table, worker-pool, library-IO and driver characterization tests pass. On this PR's suggestion branch, the 197 such tests present at this layer pass, including the five new worker-pool tests.

An earlier revision of this review compared a small gfx942 build: four Equality logic files at two jobs produced 11 byte-identical library files between submitted and suggested code. A real-process check ran two phases of eight tasks through a two-worker pool. Every first-phase worker exited at shutdown, and the second phase used fresh worker PIDs. Linux/glibc was exercised; Windows and alternate allocators were inspected only at the helper boundary. Those runs predate the current head, whose additional changes do not affect generation.

## Summary

Ending the parse pool and the generation pool releases memory after those workers have finished their jobs. Per-kernel trimming addresses a different interval: allocator pages retained while a worker continues generating kernels. The helper compilation thread does not use the pool being shut down. The new check for loky's private [`_executor`](https://github.com/ROCm/rocm-libraries/blob/2c0dca1cadae2b1edeb0a9faae6de03fc829ad3b/projects/hipblaslt/tensilelite/tensilelite/Common/Parallel.py#L68) attribute in [shutdownWorkerPool](https://github.com/ROCm/rocm-libraries/blob/2c0dca1cadae2b1edeb0a9faae6de03fc829ad3b/projects/hipblaslt/tensilelite/tensilelite/Common/Parallel.py#L44) turns a silent loss of recycling after a joblib upgrade into a visible warning.

The author's comparison motivates both mechanisms. On the Equality subset, trimming plus phase shutdown lowers reported peak proportional set size (PSS, which apportions shared pages) from 12.62 to 10.60 GiB; the post-generation plateau falls from 11.99 to 3.05 GiB. Replacing the whole pool every 1,000 kernels leaves the peak at 12.60 GiB and takes 28.9 seconds versus 23.0 seconds for the baseline. These are author-reported observations, not independently reproduced here.

I would keep both cleanup operations. The tested bulk-replacement alternative adds batch barriers and leaves a batch's peak unchanged, so it is not a simpler, equally effective replacement. It does not rule out every staggered-recycling policy, but another scheduler is not required to justify this bounded change.

## Actionable items

None found in the inspected worker lifecycle.

## Suggestions

### Describe the actual allocator and platform boundaries

**Location:** [shutdownWorkerPool](https://github.com/ROCm/rocm-libraries/blob/2c0dca1cadae2b1edeb0a9faae6de03fc829ad3b/projects/hipblaslt/tensilelite/tensilelite/Common/Parallel.py#L44), [releaseFreedMemory](https://github.com/ROCm/rocm-libraries/blob/2c0dca1cadae2b1edeb0a9faae6de03fc829ad3b/projects/hipblaslt/tensilelite/tensilelite/Common/Parallel.py#L77) and [the per-kernel release](https://github.com/ROCm/rocm-libraries/blob/2c0dca1cadae2b1edeb0a9faae6de03fc829ad3b/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L924).

The comments promise more than glibc guarantees: workers do not necessarily retain every page they touched, and trimming does not guarantee resident memory close to live-object size. The new per-kernel comment also says that trimming in the parent "costs well under a millisecond"; with [`CpuThreads`](https://github.com/ROCm/rocm-libraries/blob/2c0dca1cadae2b1edeb0a9faae6de03fc829ad3b/projects/hipblaslt/tensilelite/tensilelite/Common/Parallel.py#L102) 1 the parent holds the whole parsed library, so that cost is unmeasured. Commit [8bc39ae2a751](https://github.com/newling/rocm-libraries/commit/8bc39ae2a75173376e2e93750efd68562bed86d7) explains free pages versus live objects and keeps the note that the parent trims beside the compile thread, without the cost claim. Execution is unchanged.

The description also overstates the no-op cases. A one-worker Linux run still calls [`malloc_trim`](https://man7.org/linux/man-pages/man3/malloc_trim.3.html) in the parent, and pool shutdown is not inherently a Windows no-op. Absence of a pool and absence of glibc are separate conditions.

### Keep the measured cost alongside the memory saving

The Equality comparison takes 24.2 seconds with both changes versus 23.0 seconds for the baseline. The CU subset takes 29.0 versus 29.2 seconds. Keep those timings next to the memory benefit. The table gives one observation per variant; repeated individual timings and peaks would separate the cost from run-to-run variation.

**Suggestion branch:** [review/pr15955-design-20261118](https://github.com/newling/rocm-libraries/tree/review/pr15955-design-20261118), based on the reviewed head, contains documentation commit [8bc39ae2a751](https://github.com/newling/rocm-libraries/commit/8bc39ae2a75173376e2e93750efd68562bed86d7). Runtime behavior is unchanged. The suggestions for all four PRs are combined on [review/pr15955-stack-deep-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15955-stack-deep-20261117); [compare it with the current stack tip](https://github.com/newling/rocm-libraries/compare/6380ad270e8f8cefbf58a0babfb0226069e914c7...6c5211fb9c646ef6bc6c90a0ed93cb74832edb50).
