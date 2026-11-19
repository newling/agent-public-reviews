This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15956](https://github.com/ROCm/rocm-libraries/pull/15956)

**Reviewed head:** [21d8312ac107](https://github.com/ROCm/rocm-libraries/commit/21d8312ac107b7d8a3fc970b87261f5ba4666b62). **Comparison base:** [#15955](https://github.com/ROCm/rocm-libraries/pull/15955) at [3ba68730e6ba](https://github.com/ROCm/rocm-libraries/commit/3ba68730e6bacb316214b46e271ce82e1b26e141).

**Scope:** New follow-up review of all four changed files, compressed-state ownership, naming, deduplication, library writing and the memory justification. This includes the [original review](review_pr15956.md), the [previous design and measurement review](review_pr15956_design_20261117.md), all available discussion on [#15954](https://github.com/ROCm/rocm-libraries/pull/15954)–[#15958](https://github.com/ROCm/rocm-libraries/pull/15958), and both new inline comments on this head. The head and base were rechecked before handoff.

**Suggestion branch:** [review/pr15956-followup-20261118](https://github.com/newling/rocm-libraries/tree/review/pr15956-followup-20261118), based on the reviewed head, with seven commits ending at [ec2b5c95450e](https://github.com/newling/rocm-libraries/commit/ec2b5c95450ec493f902cff099eb47c7377fb698). [Compare all seven suggestions with the reviewed head](https://github.com/newling/rocm-libraries/compare/21d8312ac107b7d8a3fc970b87261f5ba4666b62...ec2b5c95450ec493f902cff099eb47c7377fb698); each implemented item links to its commit below. Previously linked reviews are preserved.

## Tests

The submitted head passed **316 focused tests and 112 snapshots**; the final suggestion branch passed **320 tests and the same 112 snapshots**. Coverage included compact solutions, compile grouping, split-GSU naming, custom-kernel library IO, worker cleanup, and driver, helper-naming, library-IO and solution-library characterization. The two earlier cache/equality regressions fail on the submitted head. All four cases of the new naming-mode regression fail before the mode check and pass afterward, including pickle round trips.

A four-file gfx942 Equality build at two jobs produced **11 byte-identical library files** on the submitted and final suggestion revisions: four assembly code objects, one helper code object and six metadata files. Both reported zero parent fallback reads. Runs used Python 3.12, ROCm 7.1/AMD Clang 20, lazy MessagePack libraries, disabled helper caching and the same output directory. The native rocisa dependency was rebuilt for the reviewed source. This checks actual parsing, worker transport, generation, metadata propagation and writing; it is not a full-architecture memory benchmark or a GPU execution test.

Applicable root pre-commit checks pass. Focused flake8 reports the same seven inherited diagnostics in `create_library/run.py` on both revisions; neither new compact code nor its tests adds one. GitHub's exact-head pre-commit run passed, while the [policy bot](https://github.com/ROCm/rocm-libraries/actions/runs/44412073514/job/135182595929) failed after selecting a cancelled pre-commit result. The CI snapshot also contains queued component/Math CI work and skipped lanes, so it does not establish a completed CI gate.

## Summary

The compact representation still saves parent memory by retaining compressed generator state while the parent organizes jobs using a small summary. Full expansion is explicit at kernel generation, helper construction and library naming. Removing the unused `solDict` pass also avoids reconstructing every solution for a result nobody consumes.

The new head incorporates prerequisite and upstream updates, but this PR's own change is unchanged from [a8d525055a79](https://github.com/ROCm/rocm-libraries/commit/a8d525055a79df0cad857f82f0c03791d7e85d05). The previous cache, equality and size-accounting findings therefore remain open. The latest inline comments identify two further bounded improvements; both were checked against the current consumers below.

The small build continues to preserve output. The remaining interface defects concern operations the current driver avoids: mapping-wide fallback queries, mixed full/compact comparisons, and requests using a different naming mode. They are reproducible, but this review does not claim they currently corrupt the tested build.

## Actionable items

### Reuse the promoted solution for mapping-wide queries

**Location:** [CompactSolution._fallback, line 219](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L219).

`__len__`, `__iter__` and `keys()` call `_fallback()` without first checking the promoted object. After the threshold, it still rebuilds and replaces that object on every call. Ten length queries produce ten decompressions; calling `keys()` after retaining `hydrate()` also changes the cached object's identity. This contradicts the promise that promotion bounds repeated expansion.

Commit [c2443af2830b](https://github.com/newling/rocm-libraries/commit/c2443af2830b7a2162bf6a69a611df7dacbab069) returns the existing object before counting another miss. The committed regression checks all three mapping operations, retained identity and the fallback count. This carries forward the earlier finding and fix.

### Keep full/compact equality symmetric

**Location:** [CompactSolution.__eq__, line 288](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L288), and [Solution.__eq__, line 8307](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/Solution.py#L8307).

For an equivalent fixture, `compact == full` is true and `full == compact` is false. Their hashes agree, so `dict.fromkeys([compact, full])` retains one entry and reversing the input retains two. The full representation already refuses cross-type equality.

Commit [b6ab3982689f](https://github.com/newling/rocm-libraries/commit/b6ab3982689f7bfc60c4a6e4ec29c6e65dbee10c) makes compact records follow that same boundary. The existing test now checks symmetry and order-independent deduplication. Supporting cross-type equality instead would require a matching change to `Solution`; the current all-compact loader does not need it. This finding is unchanged from the previous review.

### Correct the memory explanation

**Location:** [CompactSolution module documentation, line 8](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L8), [parse-worker comment, line 112](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L112), and the PR's Motivation.

The source still claims roughly 140 KB per full solution and 50 GiB for 350,000 solutions; the description calls this the largest single contributor. The [previous measurement](review_pr15956_design_20261117.md#appendix-parent-memory-measurement) counted shared objects once across 25,663 solutions: 778.5 MiB for full objects, about 31 KiB each, versus 261 MiB for compact records, about 10.4 KiB each. Its full gfx942 loading run changed parent RSS from 32.72 to 25.34 GiB, a 7.38 GiB saving. Column tables in the next PR saved another 13.43 GiB. These are historical measurements at the earlier heads, not new measurements of this revision.

Commit [d4d94998fa3b](https://github.com/newling/rocm-libraries/commit/d4d94998fa3b1fe9ddcf2b8501e1392df8b8dda3) removes the inflated figures from source comments and describes the ownership and expansion boundaries directly. The PR motivation still needs the corresponding correction, with the earlier workload and measurement scope attached to any figures retained. No PR-description edit was made.

### Check the mode used for cached names

**Location:** [naming dispatchers, lines 578–603](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L578). This confirms the [new inline concern](https://github.com/ROCm/rocm-libraries/pull/15956#discussion_r4622624381).

The compact dispatchers ignore the requested `splitGSU` and return names cached at compaction. With `GlobalSplitU=2`, compacting with `True` and querying with `False` returns a different compile/symbol name from the full solution. With `GlobalSplitU=1`, the dedupe key differs. The current driver uses `False` consistently, which explains why the build comparison passes.

Commit [ec2b5c95450e](https://github.com/newling/rocm-libraries/commit/ec2b5c95450ec493f902cff099eb47c7377fb698) stores the compaction mode, preserves it through pickling, and raises `ValueError` when a dispatcher or repeated compaction requests another mode. It also uses the stored mode in the existing dedupe-key fallback, which previously hardcoded `False`. The regression compares matching-mode results with the full naming functions and rejects both mismatch directions. An exception keeps the check active under optimized Python.

## Suggestions

### Retain only metadata and helpers the parent uses

**Location:** [SUMMARY_KEYS, line 37](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L37), [compact attributes, line 94](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L94), and [duplicate naming helpers, line 343](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L343).

The [new summary-field comment](https://github.com/ROCm/rocm-libraries/pull/15956#discussion_r4622624377) is supported by the current call sites. Six codegen-output fields are read on the hydrated worker copy, and `SolutionIndex`/`SolutionNameMin` are unnecessary in the TCL parent's summary. Actual occupancy and clock results reach `sizeMapping` through the worker result. Removing these entries reduces the summary from 26 fields to 18; it does not make a subsequently hydrated parse-time field contain post-codegen data. Future parent consumers must use the returned worker result for those values.

Commit [91b0df0502d4](https://github.com/newling/rocm-libraries/commit/91b0df0502d4edea8dbb29bcd9d79efc06ec96b8) removes the eight entries and corrects the source-path comment. Two carried-forward commits remove the unused `srcName`/`duplicate` wrapper state ([12e72c9b3c59](https://github.com/newling/rocm-libraries/commit/12e72c9b3c5927ebf4a80c3ac4f4796f4eaef9d8)) and test-only duplicate naming dispatchers ([c27a42743eeb](https://github.com/newling/rocm-libraries/commit/c27a42743eeb27aabd1e7876d30222d037f7cd81)). The tests call the production dispatchers and still check the source filename after expansion.

### Keep explicit expansion as the smaller interface option

**Location:** [Mapping facade, line 229](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/SolutionStructs/CompactSolution.py#L229).

The earlier option remains useful: expose the parent metadata and `hydrate()` explicitly, rather than silently expanding and eventually retaining a full object after unknown-key queries. The observed zero fallback count supports considering that reduction. It does not establish that every caller can already drop the compatibility behavior. This branch repairs the existing interface; replacing it remains a design choice, not an additional implementation hidden in these fixes.

### Consider sharing equal problem types and predicates separately

**Location:** [parse worker, line 104](https://github.com/ROCm/rocm-libraries/blob/21d8312ac107b7d8a3fc970b87261f5ba4666b62/projects/hipblaslt/tensilelite/tensilelite/create_library/run.py#L104).

The previous review's [shared-object suggestion](https://github.com/newling/rocm-libraries/commit/0c803ef030eb31a572284eee7c3f079a3cef729f) remains independent of compact storage. It reported [another 3.34 GiB reduction](review_pr15956_design_20261117.md#share-equal-problem-types-and-predicates) after the column-table change by sharing equal `Contractions.Solution` problem types and predicates. It changes a different ownership boundary and already has its own implementation and measurements. It is not included in this branch or required to fix this PR's interface defects.

## Scope decisions

The earlier YAML-to-object worker-pipeline question remains open. Such a pipeline must coordinate global indices, first duplicate representatives, code-object placement and returned metadata. It is a broader alternative, not a prerequisite for this incremental representation change.

The previous compression-cost request has useful loading/expansion evidence in the linked measurement review. This pass preserves that evidence and corrects the overstatement; it does not substitute the whole stack's peak-memory result for this PR's contribution or claim a new full-build benchmark.

Related-PR feedback was used to assess interactions. The sampler's accepted design is settled. The worker-cleanup replies and new tests are reflected in this PR's base and were exercised in the focused suite. The column-table ownership/dependency questions and shuffle measurements remain with their respective PRs. This report is not a fresh full review of those three implementations.

All suitable bounded fixes are on [review/pr15956-followup-20261118](https://github.com/newling/rocm-libraries/tree/review/pr15956-followup-20261118); the item paragraphs give the seven-commit mapping. The larger interface, shared-object and pipeline proposals remain separate. Validation is limited to the focused suites and the small generated-library comparison above.
