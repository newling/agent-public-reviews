This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15956](https://github.com/ROCm/rocm-libraries/pull/15956)

**Reviewed head:** [a8d525055a79](https://github.com/ROCm/rocm-libraries/commit/a8d525055a79df0cad857f82f0c03791d7e85d05). **Comparison base:** [#15955](https://github.com/ROCm/rocm-libraries/pull/15955) at [2c0dca1cadae](https://github.com/ROCm/rocm-libraries/commit/2c0dca1cadae2b1edeb0a9faae6de03fc829ad3b).

**Scope:** Follow-up review of compressed solution ownership, mapping/equality behavior, unnecessary compatibility state, and the measured memory and time effect, considering the earlier published review, the discussion on the accepted sampler prerequisite [#15954](https://github.com/ROCm/rocm-libraries/pull/15954), and the author's responses. This review covers the PR's own layer and its interactions with [#15955](https://github.com/ROCm/rocm-libraries/pull/15955)–[#15958](https://github.com/ROCm/rocm-libraries/pull/15958). The sampler's accepted design is not reopened. It was first written for [56eb1f717cd6](https://github.com/ROCm/rocm-libraries/commit/56eb1f717cd6222f46b7e4355ac0d17bce6fe308); this PR's layer diff is byte-identical at the current head.

## Tests

At the current stack tip ([#15958](https://github.com/ROCm/rocm-libraries/pull/15958) at [6380ad270e8f](https://github.com/ROCm/rocm-libraries/commit/6380ad270e8f8cefbf58a0babfb0226069e914c7)), 217 focused compact-solution, matching-table, worker-pool, library-IO and driver characterization tests pass. This PR's suggestion branch passes the 205 such tests present at this layer. The mapping-cache and comparison assertions each fail without their fix and pass with it. The tests exercise the production naming dispatchers after their test-only duplicates are removed.

An earlier revision of this review compared a small gfx942 build: four Equality logic files at two jobs produced 11 byte-identical library files between submitted and suggested code, with zero compact-solution fallback reads in the parent.

For the memory and time effect, logic loading was measured at [#15955](https://github.com/ROCm/rocm-libraries/pull/15955), this PR, [#15957](https://github.com/ROCm/rocm-libraries/pull/15957), and with the shared-objects suggestion below. The appendix gives the method. Two inputs were used:

- All 843 non-experimental gfx942 logic files (356,190 solutions, 38.5 million matching rows) at 32 jobs, one run per revision.
- A 109-file subset (25,663 solutions, 3.3 million rows) at 24 jobs, three interleaved runs per revision. The subset is all 72 [`gfx942/Equality`](https://github.com/ROCm/rocm-libraries/tree/6380ad270e8f8cefbf58a0babfb0226069e914c7/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full/aquavanjaram/gfx942/Equality) files, every twelfth [`gfx942/GridBased`](https://github.com/ROCm/rocm-libraries/tree/6380ad270e8f8cefbf58a0babfb0226069e914c7/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full/aquavanjaram/gfx942/GridBased) file and every fourth [`gfx942_80cu/GridBased`](https://github.com/ROCm/rocm-libraries/tree/6380ad270e8f8cefbf58a0babfb0226069e914c7/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full/aquavanjaram/gfx942_80cu/GridBased) file.

The subset's serialized master and lazy library state, after naming, has the same SHA-256 at [#15955](https://github.com/ROCm/rocm-libraries/pull/15955), at [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) and with all suggestions applied.

## Summary

Keeping compressed generator state while the parent works with a small summary directly reduces retained memory. The most useful design boundary is already present: generation, helper construction and library naming explicitly expand a record when they need a full Solution.

The generic Mapping facade extends beyond that boundary. It promises arbitrary field reads, automatic promotion to a full object, iteration, equality with another representation, and synchronization between the summary, overlay and expanded state. Two reproducible inconsistencies below come from that extra interface. Neither occurred in the small build, which reported zero fallback reads and used only compact records.

Measured, the saving is real but smaller than the PR states:

| Revision | Parent after loading, full set | Load time, full set | Parent after loading, subset (3 runs) |
| --- | ---: | ---: | --- |
| [#15955](https://github.com/ROCm/rocm-libraries/pull/15955) | 32.7 GiB | 86 s | 2.74, 2.75, 2.75 GiB |
| This PR | 25.3 GiB | 58 s | 2.26, 2.25, 2.23 GiB |
| [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) | 11.9 GiB | 53 s | 1.06, 1.06, 1.07 GiB |
| [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) plus shared problem types and predicates | 8.6 GiB | 53 s | 0.79, 0.80, 0.80 GiB |

This PR saves 7.4 GiB and makes loading 28 seconds faster, because the parent unpickles much less. Expanding a compact solution costs about 0.1 ms. Expanding every solution again for codegen and naming therefore costs about a minute of CPU time, spread across the workers. That settles the earlier request for the cost of compression and expansion, for loading and expansion.

## Actionable items

### Reuse the promoted object for every mapping operation

**Location:** [_fallback](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L219) and [iteration, length and keys](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L254).

[`__getitem__`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L229) checks [`_hydrated`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L91), but [`__len__`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L257), [`__iter__`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L254) and [`keys()`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L260) call [`_fallback`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L219) directly. Once the promotion threshold is reached, [`_fallback`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L219) still decompresses and replaces the full object every time. Ten length queries cause ten decompressions, contrary to the stated purpose of promotion, and a caller holding the previously returned object stops sharing the cached one.

Commit [062e9f9c3e05](https://github.com/newling/rocm-libraries/commit/062e9f9c3e05933eece6088d061cef8cb28ed953) makes [`_fallback`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L219) return the existing promoted object first. The promotion test now checks length, iteration, key enumeration, object identity and an unchanged fallback count after promotion; it fails on the submitted code. This fixes the advertised interface; the currently observed parent path makes no fallback reads.

### Make full/compact comparison symmetric

**Location:** [CompactSolution.__eq__](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L288) and [Solution.__eq__](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/Solution.py#L8270).

A compact record accepts a full Solution as equal, but the full Solution rejects the compact type. With the checked-in fixture, `compact == full` is true and `full == compact` is false. Because their hashes agree, [`dict.fromkeys([compact, full])`](https://docs.python.org/3/library/stdtypes.html#dict.fromkeys) keeps one record while the reversed list keeps two.

Commit [53b195a507e4](https://github.com/newling/rocm-libraries/commit/53b195a507e4057120550fc823c61b15a9f6ccbf) removes the one-sided cross-type acceptance: compact records compare with compact records, matching the full type's existing refusal to compare across representations. The tests now assert symmetry and order-independent deduplication. The production loader compacts all of its records, so its deduplication is unchanged. Supporting cross-type equality instead would need a matching change to the full type, and no caller needs it.

### Correct the size and ranking claims

**Location:** [the CompactSolution module docstring](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L8) and [the comment where the parse worker compacts](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L111).

The docstring says each full [`Solution`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/Solution.py#L928) costs about 140 KB once unpickled, so 350k solutions would cost the parent 50 GiB. The description calls them "tens of GiB" and "the largest single contributor to the build's memory peak". Measured in the parent, counting each object once across all solutions, 25,663 full solutions hold 778 MiB, about 31 KB each. Their compact records hold 261 MiB, about 10.4 KB each. The full-set measurement agrees: this PR lowers the parent by 7.4 GiB, while the matching rows converted by [#15957](https://github.com/ROCm/rocm-libraries/pull/15957) account for 13.4 GiB.

This matters for evaluating the design. The Mapping facade, overlay, fallback counter and promotion are justified against a 50 GiB problem; the actual saving is 7.4 GiB plus faster loading. Commit [b4cd23aa1912](https://github.com/newling/rocm-libraries/commit/b4cd23aa1912f2f4c62033b67d27d58dc7b5fc0b) corrects both comments with the measured figures. The description's motivation should be corrected the same way.

## Suggestions

### Keep only state and helpers with production consumers

**Location:** [the compact attributes](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L94) and [duplicate naming dispatchers](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L343).

The compact [`srcName`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L94) and [`duplicate`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L95) attributes have no production consumers. The source filename already resides in the compressed Solution payload; the duplicate flag is introduced, propagated and checked only by this wrapper and its new test. Commit [5f54c2eca5fc](https://github.com/newling/rocm-libraries/commit/5f54c2eca5fc05fb898e532bfe03f3ecb578121f) removes both wrapper attributes and their pickle plumbing while checking that expansion keeps the original source filename.

Commit [34222377ceca](https://github.com/newling/rocm-libraries/commit/34222377ceca916683163fc356101165ed4cfed7) removes [`kernelFileBase`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L343) and [`kernelDedupeKey`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L350) from this module; only tests used them. Their assertions now exercise the driver's actual dispatchers, keeping the comparison against full-solution naming.

### Make expensive expansion an explicit operation

**Location:** [SUMMARY_KEYS](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L37) and [the mapping facade](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L229).

Prefer a parent build record that exposes the required metadata and the existing explicit [`hydrate()`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L198) operation. Unknown metadata reads would then fail at their call site, while callers needing full state expand once. That would remove fallback promotion, its threshold, counters and cache synchronization, and prevent an innocuous query from silently keeping a full object beside its compressed copy.

This does not require replacing compression or redesigning the YAML-to-object pipeline. The generator already expands explicitly at its expensive consumers, and both the reported full build and the local small build show zero parent fallback reads. Those observations support removing this compatibility behavior; they do not prove every supported caller can already do without it. The suggestion branch repairs the promised behavior rather than changing that API policy silently.

### Share equal problem types and predicates

**Location:** [_parseLogicFileForLibrary](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L103).

After compaction, the largest remaining part of a parsed solution is its [`Contractions.Solution`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/Contractions.py#L1070) wrapper. On the subset the wrappers hold 435 MiB, more than the compact records' 261 MiB. [`problemPredicate`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/Contractions.py#L1140) accounts for 183 MiB of that and [`problemType`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/Contractions.py#L1131) for 132 MiB. Every wrapper builds its own copy of both, yet the 26,431 wrappers contain only 101 distinct problem types and 10,472 distinct problem predicates. Nothing in the create-library path modifies either object after construction; the only write, [`mxScaleFormat`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/Contractions.py#L1138), happens inside the constructor.

Commit [0c803ef030eb](https://github.com/newling/rocm-libraries/commit/0c803ef030eb31a572284eee7c3f079a3cef729f) lets equal values share one object within each parse worker's library, before the library is pickled to the parent; pickling preserves the sharing. On top of [#15957](https://github.com/ROCm/rocm-libraries/pull/15957), it lowers the full-set parent from 11.9 to 8.6 GiB, a further 28%, with unchanged load time and an unchanged serialized-state hash. It is independent of compaction, so it could also land separately.

It also bears on the previous suggestion. Sharing these objects saves 3.3 GiB with one small function; compaction saves 7.4 GiB with a mapping facade. A record with explicit [`hydrate()`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L198) calls would keep those 7.4 GiB without the facade.

## Scope decisions

A worker pipeline that takes YAML through assembly/object generation could avoid keeping full configurations in the parent, but must preserve global solution indexing, duplicate representatives, library placement and post-generation metadata. It remains a broader alternative, not a prerequisite for this change.

## Commentary

Further reductions of compact records should target the precomputed strings rather than compression. Of a compact record's 10.4 KB, the compressed blob is 46%. The full name, symbol name and dedupe-key prefix together are 31%, helper names 11%, and the summary tuple 8%.

**Suggestion branch:** [review/pr15956-design-20261118](https://github.com/newling/rocm-libraries/tree/review/pr15956-design-20261118), based on the reviewed head, contains [34222377ceca](https://github.com/newling/rocm-libraries/commit/34222377ceca916683163fc356101165ed4cfed7) (production dispatchers), [062e9f9c3e05](https://github.com/newling/rocm-libraries/commit/062e9f9c3e05933eece6088d061cef8cb28ed953) (mapping cache), [53b195a507e4](https://github.com/newling/rocm-libraries/commit/53b195a507e4057120550fc823c61b15a9f6ccbf) (symmetric equality), [5f54c2eca5fc](https://github.com/newling/rocm-libraries/commit/5f54c2eca5fc05fb898e532bfe03f3ecb578121f) (unused attributes), [b4cd23aa1912](https://github.com/newling/rocm-libraries/commit/b4cd23aa1912f2f4c62033b67d27d58dc7b5fc0b) (size claims) and [0c803ef030eb](https://github.com/newling/rocm-libraries/commit/0c803ef030eb31a572284eee7c3f079a3cef729f) (shared problem types and predicates). The suggestions for all four PRs are combined on [review/pr15955-stack-deep-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15955-stack-deep-20261117); [compare it with the current stack tip](https://github.com/newling/rocm-libraries/compare/6380ad270e8f8cefbf58a0babfb0226069e914c7...6c5211fb9c646ef6bc6c90a0ed93cb74832edb50). The explicit-record and pipeline redesigns were not implemented. The shared-objects commit was validated by the state hash, memory and load-time measurements and the focused tests; a complete device-library build with byte comparison was not repeated for it.

## Appendix: parent-memory measurement

The measurement wraps the driver's loading function and stops before code generation:

```python
import gc
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

The hook wraps [`generateLogicDataAndSolutions`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L1189). VmHWM equaled VmRSS at that point in every run. Per-object sizes come from a traversal that sums [`sys.getsizeof`](https://docs.python.org/3/library/sys.html#sys.getsizeof) over dicts, sequences, [`__dict__`](https://docs.python.org/3/reference/datamodel.html#object.__dict__) and [`__slots__`](https://docs.python.org/3/reference/datamodel.html#slots). It counts each object once across all solutions and skips the shared [`assembler`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/Solution.py#L953) and [`isaInfoMap`](https://github.com/ROCm/rocm-libraries/blob/a8d525055a79df0cad857f82f0c03791d7e85d05/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/Solution.py#L954). ROCm 7.1 tools were used.
