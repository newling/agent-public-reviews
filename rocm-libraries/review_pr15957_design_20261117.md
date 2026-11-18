This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15957](https://github.com/ROCm/rocm-libraries/pull/15957)

**Reviewed head:** [d203c9964aa2](https://github.com/ROCm/rocm-libraries/commit/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9). **Comparison base:** [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) at [a8d525055a79](https://github.com/ROCm/rocm-libraries/commit/a8d525055a79df0cad857f82f0c03791d7e85d05).

**Scope:** Follow-up review of matching-table construction, merge ownership, serialization, and the measured benefit of each representation, considering the earlier published review, the discussion on the accepted sampler prerequisite [#15954](https://github.com/ROCm/rocm-libraries/pull/15954), and the author's responses. This review covers the PR's own layer and its interactions with [#15955](https://github.com/ROCm/rocm-libraries/pull/15955)–[#15958](https://github.com/ROCm/rocm-libraries/pull/15958). The sampler's accepted design is not reopened. It was first written for [ed456253fbc4](https://github.com/ROCm/rocm-libraries/commit/ed456253fbc4eebacb12ed0254e3650cbde4521e); this PR's layer diff is byte-identical at the current head.

## Tests

At the current stack tip ([#15958](https://github.com/ROCm/rocm-libraries/pull/15958) at [6380ad270e8f](https://github.com/ROCm/rocm-libraries/commit/6380ad270e8f8cefbf58a0babfb0226069e914c7)), 217 focused compact-solution, matching-table, worker-pool, library-IO and driver characterization tests pass. This PR's suggestion branch passes 219. The new empty-receiver regression fails with column storage on the submitted code and passes with the fix; its missing-NumPy variant keeps the legacy behavior. The regression exercises the real MatchingLibrary factory and merge operations, not a mock.

An earlier revision of this review compared a small gfx942 build: four Equality logic files at two jobs produced 11 byte-identical library files between submitted and suggested code. Memory was measured as described in the [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) [review](review_pr15956_design_20261117.md#appendix-parent-memory-measurement): parent memory right after logic loading, on all 843 non-experimental gfx942 logic files (one run per revision) and on a 109-file subset (three interleaved runs). On the subset, the serialized master and lazy library state after naming has the same SHA-256 before this PR's tables, with them, and with all suggestions applied.

## Summary

Column storage has a direct justification: the parent keeps many more matching rows than solutions, and repeated Python dictionaries and boxed numbers consume memory throughout generation. The current code builds columns without first building row dictionaries, sorts once at construction, and keeps source-only environments working when NumPy is unavailable. Those earlier review concerns are addressed.

The measurement confirms the description. On the full set, this PR lowers the parent after loading from 25.3 to 11.9 GiB: 13.4 GiB for 38.5 million rows, about 370 bytes per row. It is the largest single saving in the stack, nearly twice that of [#15956](https://github.com/ROCm/rocm-libraries/pull/15956). On the subset, three runs each gave 2.26, 2.25 and 2.23 GiB before and 1.06, 1.06 and 1.07 GiB after. Loading also gets faster, from 58 to 53 seconds on the full set. The description's statement that rows keep the parent "above 30 GiB" after [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) should match the measured 25.3 GiB.

The remaining ownership mistake is in the empty-table merge shortcut. A representation change must preserve which library owns its row container, even when the underlying solution objects intentionally stay shared.

## Actionable items

### Give an empty merge receiver its own table

**Location:** [MatchingLibrary.merge](https://github.com/ROCm/rocm-libraries/blob/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9/projects/hipblaslt/tensilelite/tensilelite/SolutionLibrary.py#L187).

[`self.table = other.table`](https://github.com/ROCm/rocm-libraries/blob/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9/projects/hipblaslt/tensilelite/tensilelite/SolutionLibrary.py#L187) aliases the entire column container. A later column merge uses the in-place [`MatchingTable.__iadd__`](https://github.com/ROCm/rocm-libraries/blob/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9/projects/hipblaslt/tensilelite/tensilelite/MatchingTable.py#L169), so it adds rows to both libraries. Before the representation change, extending an empty list created an independent row container.

The committed regression builds source rows `[0]`, merges them into an empty receiver, adds `[1]` to the receiver, then adds `[2]` to the source. Expected source and receiver indices are `[0, 2]` and `[1, 0]` after key sorting. The submitted column implementation gives both `[1, 0, 2]`. The legacy path keeps the tables independent, as expected.

Commit [44dd7f80440c](https://github.com/newling/rocm-libraries/commit/44dd7f80440cb7b46b3f6f69fbebcb337a515627) shallow-copies the table when an empty receiver adopts it. A shallow copy is enough: column concatenation and sorting assign new arrays/lists, and solution references must stay shared so later solution reindexing is reflected in the serialized rows. Deep-copying the solutions would change that behavior.

This is a demonstrated merge-contract regression. The small build did not contain an empty matching library, so it does not show that a shipped logic set currently triggers it.

## Suggestions

### Keep the table interface aligned with its consumers

**Location:** [fromRows](https://github.com/ROCm/rocm-libraries/blob/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9/projects/hipblaslt/tensilelite/tensilelite/MatchingTable.py#L114) and [the sequence facade](https://github.com/ROCm/rocm-libraries/blob/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9/projects/hipblaslt/tensilelite/tensilelite/MatchingTable.py#L155).

With direct column construction, [`fromRows`](https://github.com/ROCm/rocm-libraries/blob/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9/projects/hipblaslt/tensilelite/tensilelite/MatchingTable.py#L114) has only test callers. Integer/slice indexing is also only used by tests; production merging needs length, concatenation, sorting, legacy conversion and serialization. A smaller table interface could move the row adapter into test setup and build legacy rows only in [`toRows`](https://github.com/ROCm/rocm-libraries/blob/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9/projects/hipblaslt/tensilelite/tensilelite/MatchingTable.py#L164), avoiding a persistent wrapper cache and some custom pickle plumbing.

The shared-wrapper behavior of actual legacy conversion is useful and must be kept. This interface reduction is not part of the fix; its value is removing production machinery that has no production caller.

### Provision NumPy where the source build runs

The missing-NumPy fallback fixes the observed build failure but disables the 13.4 GiB saving in that environment. Installing the already-declared dependency in the source-build interpreter would let those builds benefit too. No external build-environment change was made in this review.

## Commentary

Column tables also change how lazy libraries reach the library-writing pool. loky passes NumPy arrays larger than 1 MB to workers as read-only memory maps under `/dev/shm`. A probe confirmed that a 100,000-row [`MatchingTable`](https://github.com/ROCm/rocm-libraries/blob/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9/projects/hipblaslt/tensilelite/tensilelite/MatchingTable.py#L43) reaches the worker as [`np.memmap`](https://numpy.org/doc/stable/reference/generated/numpy.memmap.html). On the full set this covers 1.13 GiB of arrays in 137 of 601 lazy libraries, at most 13.4 MiB per library. Writing only reads the arrays, and sorting creates new arrays, so nothing fails. The note is here because shared-memory use in constrained CI containers counts toward the job's memory.

**Suggestion branch:** [review/pr15957-design-20261118](https://github.com/newling/rocm-libraries/tree/review/pr15957-design-20261118), based on the reviewed head, contains [44dd7f80440c](https://github.com/newling/rocm-libraries/commit/44dd7f80440cb7b46b3f6f69fbebcb337a515627) (independent table ownership and its regression). The suggestions for all four PRs are combined on [review/pr15955-stack-deep-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15955-stack-deep-20261117); [compare it with the current stack tip](https://github.com/newling/rocm-libraries/compare/6380ad270e8f8cefbf58a0babfb0226069e914c7...6c5211fb9c646ef6bc6c90a0ed93cb74832edb50). The interface reduction and dependency provisioning remain proposals.
