This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15955](https://github.com/ROCm/rocm-libraries/pull/15955), with the stacked [#15956](https://github.com/ROCm/rocm-libraries/pull/15956), [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) and [#15958](https://github.com/ROCm/rocm-libraries/pull/15958).

**Reviewed heads:** [#15955](https://github.com/ROCm/rocm-libraries/pull/15955) [2c0dca1cadae](https://github.com/ROCm/rocm-libraries/commit/2c0dca1cadae2b1edeb0a9faae6de03fc829ad3b), [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) [a8d525055a79](https://github.com/ROCm/rocm-libraries/commit/a8d525055a79df0cad857f82f0c03791d7e85d05), [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) [d203c9964aa2](https://github.com/ROCm/rocm-libraries/commit/d203c9964aa2eaf3e636b8bf5cafe530b3b5aab9), [#15958](https://github.com/ROCm/rocm-libraries/pull/15958) [6380ad270e8f](https://github.com/ROCm/rocm-libraries/commit/6380ad270e8f8cefbf58a0babfb0226069e914c7). The stack sits on the approved sampler, [#15954](https://github.com/ROCm/rocm-libraries/pull/15954) at `c58a28ab7985`.

**Scope:** Follow-up to the [#15955](https://github.com/ROCm/rocm-libraries/pull/15955) ([review](review_pr15955_design_20261117.md)), [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) ([review](review_pr15956_design_20261117.md)), [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) ([review](review_pr15957_design_20261117.md)) and [#15958](https://github.com/ROCm/rocm-libraries/pull/15958) ([review](review_pr15958_design_20261117.md)) design reviews, focused on measuring what each layer actually saves. Since those reviews, the [#15956](https://github.com/ROCm/rocm-libraries/pull/15956)–[#15958](https://github.com/ROCm/rocm-libraries/pull/15958) layer diffs are byte-identical; [#15955](https://github.com/ROCm/rocm-libraries/pull/15955) only adds a warning for a missing loky attribute and its tests. The earlier findings therefore still apply, and their commits are carried onto the current heads below. This review does not repeat them.

## Tests

The submitted stack tip and the suggestion branch pass the focused compact-solution, matching-table, worker-pool, library-IO and driver characterization tests (217 and 219 tests). On a 109-file gfx942 subset, the serialized master and lazy library state (after naming) has the same SHA-256 at [#15955](https://github.com/ROCm/rocm-libraries/pull/15955), at [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) and on the suggestion branch.

All measurements ran on one machine at low priority, with ROCm 7.1 tools and gfx942 logic from the reviewed revision:

- Parent memory is the parent's RSS right after `generateLogicDataAndSolutions` returns, after a `gc.collect()`; VmHWM equals VmRSS at that point. The method is in the appendix.
- The 109-file subset is all 72 `gfx942/Equality` files, every twelfth `gfx942/GridBased` file and every fourth `gfx942_80cu/GridBased` file: 25,663 unique solutions and 3.3 million rows, at 24 jobs.
- The full set is all 843 non-experimental gfx942 files: 356,190 solutions and 38.5 million rows, at 32 jobs.
- The codegen comparison uses the description's six-file CU subset under `scripts/memwatch.py`, with the helper cache disabled, at 32 jobs.

No GPU execution or complete device-library build of the full set was performed.

## Summary

Measured directly, the parent's memory falls in two unequal steps:

| Revision | Parent after loading, full set | Load time, full set | Parent after loading, subset (3 runs) |
| --- | ---: | ---: | --- |
| [#15955](https://github.com/ROCm/rocm-libraries/pull/15955) (develop representation) | 32.7 GiB | 86 s | 2.74, 2.75, 2.75 GiB |
| [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) compact solutions | 25.3 GiB | 58 s | 2.26, 2.25, 2.23 GiB |
| [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) column tables | 11.9 GiB | 53 s | 1.06, 1.06, 1.07 GiB |
| [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) plus shared problem types and predicates (suggestion below) | 8.6 GiB | 53 s | 0.79, 0.80, 0.80 GiB |

The full-set figures are one run each; the subset runs were interleaved and agree within 2%. The column tables are the largest saving, at 13.4 GiB, or about 370 bytes per row, in line with the [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) description. Compact solutions save 7.4 GiB, much less than [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) claims (next section). Both layers also make loading faster, because the parent unpickles less. Expanding a compact solution costs 0.1 ms, so expanding every solution again for codegen and naming costs about a minute of CPU time in total across the workers. That answers the earlier request for the cost of compression and expansion, at least for loading and expansion.

For [#15958](https://github.com/ROCm/rocm-libraries/pull/15958), the shuffle lowered peak summed PSS in all five pairs, alternating which variant ran first:

| Pair | 1 | 2 | 3 | 4 | 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| File order first | 1 | 0 | 1 | 0 | 1 |
| File order peak PSS (GiB) | 5.304 | 5.279 | 5.313 | 5.321 | 5.245 |
| Shuffled peak PSS (GiB) | **4.898** | **5.115** | **5.211** | **5.048** | **5.136** |
| File order codegen (s) | 16.1 | 16.0 | 16.1 | 15.8 | 16.0 |
| Shuffled codegen (s) | **14.5** | **14.5** | **14.5** | **14.3** | **14.2** |

The mean peak reduction is 0.21 GiB, about 4% (paired t = 3.66 with 4 degrees of freedom; 95% interval 0.05–0.37 GiB). Codegen is 1.6 s shorter in every pair. This supports keeping the shuffle and settles the earlier request for an isolated memory comparison on this subset and concurrency. It also calibrates the description: here the shuffle trims the codegen spike modestly and mainly shortens the tail. It does not remove the spike.

## Actionable items

### Correct the size and ranking claims for compact solutions

**Location:** [the CompactSolution module docstring](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L8) and [the comment where the parse worker compacts](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L111).

The docstring says each full `Solution` costs about 140 KB once unpickled, so 350k solutions would cost the parent 50 GiB. The PR description calls them "tens of GiB" and "the largest single contributor to the build's memory peak". Measured in the parent, counting each object once across all solutions, 25,663 full solutions hold 778 MiB, or about 31 KB each. Their compact records hold 261 MiB, or about 10.4 KB each. The full-set measurement agrees: [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) lowers the parent by 7.4 GiB, while the matching rows that [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) converts account for 13.4 GiB.

This matters for evaluating the PR. Its Mapping facade, overlay, fallback counter and promotion are justified against a 50 GiB problem; the actual saving is 7.4 GiB, plus 28 seconds of faster loading. Commit [d75ce1f8165](https://github.com/newling/rocm-libraries/commit/d75ce1f8165343bffa968efa194d37c3b7c86aaf) corrects both comments with the measured figures. The description's motivation paragraph should be corrected the same way, and [#15957](https://github.com/ROCm/rocm-libraries/pull/15957)'s statement that rows keep the parent "above 30 GiB" after [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) should match the measured 25.3 GiB.

## Suggestions

### Share equal problem types and predicates across a logic file's solutions

**Location:** [_parseLogicFileForLibrary](https://github.com/ROCm/rocm-libraries/blob/6380ad270e8f8cefbf58a0babfb0226069e914c7/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L104).

At the stack tip, the largest remaining part of a parsed solution is its `Contractions.Solution` wrapper, which no PR in the stack changes. On the subset the wrappers hold 435 MiB, more than the compact records' 261 MiB. Of that, `problemPredicate` accounts for 183 MiB and `problemType` for 132 MiB. Every wrapper builds its own copy of both, yet the 26,431 wrappers contain only 101 distinct problem types and 10,472 distinct problem predicates. Nothing in the create-library path modifies either object after construction; the only write, `mxScaleFormat`, happens inside the constructor.

Commit [6c5211fb9c6](https://github.com/newling/rocm-libraries/commit/6c5211fb9c646ef6bc6c90a0ed93cb74832edb50) lets equal values share one object within each parse worker's library, before the library is pickled to the parent. Pickling preserves the sharing. It lowers the full-set parent from 11.9 to 8.6 GiB, a further 28%, with unchanged load time and an unchanged serialized-state hash on the subset. It is independent of [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) and [#15957](https://github.com/ROCm/rocm-libraries/pull/15957), so it could go into whichever PR the author prefers or land separately.

Its size also bears on the open design question for [#15956](https://github.com/ROCm/rocm-libraries/pull/15956). This change saves 3.3 GiB with one small function, while compaction saves 7.4 GiB with a mapping facade. The earlier proposal to replace that facade with required metadata and explicit `hydrate()` calls would keep the 7.4 GiB.

## Commentary

Further reductions of compact records should target the precomputed strings rather than compression. Of a compact record's 10.4 KB, the compressed blob is 46%. The full name, symbol name and dedupe-key prefix together are 31%, helper names 11%, and the summary tuple 8%.

Column tables also change how lazy libraries reach the library-writing pool. loky passes NumPy arrays larger than 1 MB to workers as read-only memory maps under `/dev/shm`. A probe confirmed that a 100,000-row `MatchingTable` reaches the worker as `np.memmap`. On the full set, this covers 1.13 GiB of arrays in 137 of 601 lazy libraries, at most 13.4 MiB per library. Writing only reads the arrays, and sorting creates new arrays, so nothing fails. The note is here because shared-memory use in constrained CI containers counts toward the job's memory.

## Suggestion branch

Branch [review/pr15955-stack-deep-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15955-stack-deep-20261117), based on the [#15958](https://github.com/ROCm/rocm-libraries/pull/15958) head [6380ad270e8f](https://github.com/ROCm/rocm-libraries/commit/6380ad270e8f8cefbf58a0babfb0226069e914c7). It carries the earlier design-review commits onto the current heads, followed by the two new items. [All suggestions relative to the reviewed stack tip](https://github.com/newling/rocm-libraries/compare/6380ad270e8f8cefbf58a0babfb0226069e914c7...6c5211fb9c646ef6bc6c90a0ed93cb74832edb50):

| PR | Commit | Item |
| --- | --- | --- |
| [#15955](https://github.com/ROCm/rocm-libraries/pull/15955) | [91673841a25](https://github.com/newling/rocm-libraries/commit/91673841a25944e807f8c000795886e216d1e85f) | Earlier review: allocator comments. The conflict with the new CpuThreads note keeps that note, minus its unmeasured cost claim. |
| [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) | [2bd25d4efa1](https://github.com/newling/rocm-libraries/commit/2bd25d4efa1ae541377ed036b360ce051e6638d0), [fcd250e468e](https://github.com/newling/rocm-libraries/commit/fcd250e468e0a25f44436a7d932d9bbf4f76201d), [16ef2345ed6](https://github.com/newling/rocm-libraries/commit/16ef2345ed6eccaad2e322695785257060182c40), [1718480a00f](https://github.com/newling/rocm-libraries/commit/1718480a00f6f9dc35a620a28fdfc6b46bc68a07) | Earlier review: production naming dispatchers, promoted-object reuse, symmetric equality, unused attributes |
| [#15956](https://github.com/ROCm/rocm-libraries/pull/15956) | [d75ce1f8165](https://github.com/newling/rocm-libraries/commit/d75ce1f8165343bffa968efa194d37c3b7c86aaf) | Measured size claims (this review) |
| [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) | [cb9fcc63912](https://github.com/newling/rocm-libraries/commit/cb9fcc63912c60f6def3cf22ad38b55a49806083) | Earlier review: independent table after an empty-receiver merge |
| [#15958](https://github.com/ROCm/rocm-libraries/pull/15958) | [c01add81180](https://github.com/newling/rocm-libraries/commit/c01add81180c7d7381e30e019b6c043375214a5b) | Earlier review: shuffle the existing list |
| Stack | [6c5211fb9c6](https://github.com/newling/rocm-libraries/commit/6c5211fb9c646ef6bc6c90a0ed93cb74832edb50) | Shared problem types and predicates (this review) |

The sharing commit was validated by the state hash, memory and load-time measurements and the focused tests. A complete device-library build with byte comparison was not repeated for it.

## Appendix: parent-memory measurement

The measurement wraps the driver's loading function and stops before code generation:

```python
import gc, sys
from tensilelite.create_library import run

class Stop(Exception):
    pass

realGenerate = run.generateLogicDataAndSolutions

def hook(*args, **kwargs):
    solutions, masterLibraries, _ = realGenerate(*args, **kwargs)
    gc.collect()
    print([l for l in open("/proc/self/status") if l.startswith(("VmRSS", "VmHWM"))])
    raise Stop

run.generateLogicDataAndSolutions = hook
try:
    run.main(["--cxx-compiler", "$ROCM_PATH/llvm/bin/amdclang++",
              "--c-compiler", "$ROCM_PATH/llvm/bin/amdclang",
              "--offload-bundler", "$ROCM_PATH/llvm/bin/clang-offload-bundler",
              "--assembler", "$ROCM_PATH/llvm/bin/amdclang++",
              "--architecture", "gfx942", "--jobs", "32", "--library-format", "msgpack",
              "--no-generate-solution-table", "$LOGIC_DIR", "$OUT_DIR", "HIP"])
except Stop:
    pass
```

Per-object sizes come from a traversal that sums `sys.getsizeof` over dicts, sequences, `__dict__` and `__slots__`. It counts each object once across all solutions and skips the shared `assembler` and `isaInfoMap`.
