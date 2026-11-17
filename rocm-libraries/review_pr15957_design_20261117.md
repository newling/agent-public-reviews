This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15957](https://github.com/ROCm/rocm-libraries/pull/15957)

**Reviewed head:** [ed456253fbc4eebacb12ed0254e3650cbde4521e](https://github.com/ROCm/rocm-libraries/commit/ed456253fbc4eebacb12ed0254e3650cbde4521e). **Comparison base:** [56eb1f717cd6222f46b7e4355ac0d17bce6fe308](https://github.com/ROCm/rocm-libraries/commit/56eb1f717cd6222f46b7e4355ac0d17bce6fe308).

**Publication note:** The PR has advanced to [e508cb375e5f548174a380d48d9a8319b6845104](https://github.com/ROCm/rocm-libraries/commit/e508cb375e5f548174a380d48d9a8319b6845104) since this review. The findings and suggestion branch below apply to the reviewed head; the later revision has not been reviewed here.

**Scope:** Follow-up review of matching-table construction, merge ownership, serialization, and the reason for each representation, considering the earlier published review, discussion on the accepted sampler prerequisite #15954, and the author's responses. This review covers the PR's own layer and its interactions with #15955–#15958. The sampler's accepted design is not reopened.

## Tests

The submitted stack at [5a5326702711](https://github.com/ROCm/rocm-libraries/commit/5a5326702711f4375e5a263fa85776015047c0e0) passed 300 focused tests covering representations, compile groups, driver orchestration, and library parsing/serialization. The final combined suggestions at [0d196f6a03ad](https://github.com/newling/rocm-libraries/commit/0d196f6a03ad5bc05736e7343c1fb710e6c09b3b) pass 302 tests with 103 saved-result comparisons. Four checked-in gfx942 Equality inputs, four assembly kernels and 14 helper objects, using two workers, compressed MessagePack and disabled helper caching, produce 11 byte-identical library files between submitted and suggested code. Both builds use the same output path and report zero compact-solution fallback reads in the parent. This is a small correctness comparison, not a performance measurement.

Applicable root pre-commit hooks pass. Flake8 reports the same seven pre-existing diagnostics in the driver on both revisions. Live checks are mixed: the latest normal Multi-Arch summary passes, while Math CI and the policy bot report failures and component coverage/ASAN work remains incomplete. This review does not establish a cause for every CI failure or claim merge readiness.

The new empty-receiver regression fails with column storage on the submitted code and passes with the fix; its missing-NumPy variant preserves the existing legacy behavior. The isolated suggestion branch passes 181 table and library tests with 103 saved-result comparisons. The regression exercises the real MatchingLibrary factory and merge operations, not a mock.

## Summary

Column storage has a direct justification: the parent retains many more matching rows than solutions, and repeated Python dictionaries and boxed numeric values consume memory throughout generation. The follow-up now builds columns without first building row dictionaries, sorts once at construction, and keeps source-only environments working when NumPy is unavailable. Those earlier review concerns are addressed.

The remaining ownership mistake is in the empty-table merge shortcut. A representation change must preserve which library owns its row container, even when the underlying solution objects intentionally remain shared.

## Actionable items

### Give an empty merge receiver its own table

**Location:** [MatchingLibrary.merge](https://github.com/ROCm/rocm-libraries/blob/ed456253fbc4eebacb12ed0254e3650cbde4521e/projects/hipblaslt/tensilelite/tensilelite/SolutionLibrary.py#L186).

`self.table = other.table` aliases the entire column container. A later column merge uses the in-place `MatchingTable.__iadd__`, so it adds rows to both libraries. Before the representation change, extending an empty list created an independent row container.

The committed regression constructs source rows `[0]`, merges them into an empty receiver, adds `[1]` to the receiver, then adds `[2]` to the source. Expected source and receiver indices are `[0, 2]` and `[1, 0]` after key sorting. The submitted column implementation gives both `[1, 0, 2]`. The legacy path preserves the expected independent tables.

Commit [85a60fd5a635](https://github.com/newling/rocm-libraries/commit/85a60fd5a635920de157fcd15aec170bd7405ae5) shallow-copies the table when an empty receiver adopts it. A shallow copy is sufficient: column concatenation and sorting assign new arrays/lists, and solution references must remain shared so later solution reindexing is reflected in the serialized rows. Deep-copying the solutions would change that behavior.

This is a demonstrated merge-contract regression. The small generation comparison did not contain an empty matching library, so it does not establish that a shipped corpus currently triggers it.

## Suggestions

### Keep the table interface aligned with its consumers

**Location:** [fromRows and the sequence facade](https://github.com/ROCm/rocm-libraries/blob/ed456253fbc4eebacb12ed0254e3650cbde4521e/projects/hipblaslt/tensilelite/tensilelite/MatchingTable.py#L119).

After direct column construction was added, `fromRows` has only test callers. Integer/slice indexing is also only exercised by tests; production merging needs length, concatenation, sorting, legacy conversion and serialization. A smaller table interface could move the row adapter into test setup and materialize legacy rows only in `toRows`, avoiding a persistent wrapper cache and some custom pickle plumbing.

The shared-wrapper behavior of actual legacy conversion remains useful and must be preserved. This broader interface reduction is not included in the fix; its value is removal of production machinery without a production caller, not deletion of useful conversion behavior.

### Show the benefit in the environment that performs the build

The missing-NumPy fallback fixes the observed build failure but disables the memory saving in that environment. Provisioning the already-declared dependency in the source-build interpreter would let those builds benefit too. No external build-environment change was made in this review.

The author reports an earlier isolated parent reduction from roughly 34 to 14 GiB, but has not repeated the #15956-to-#15957 comparison on the current base. Record that comparison with conversion and serialization included. `state()` still materializes all serialized rows, so retained column size alone does not establish the peak during library writing. The optional dependency and exact-value fallback are reasonable compatibility boundaries while that evidence is gathered.

**Suggestion branch:** [review/pr15957-design-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15957-design-20261117), based on the reviewed head, contains [85a60fd5a635](https://github.com/newling/rocm-libraries/commit/85a60fd5a635920de157fcd15aec170bd7405ae5) (independent table ownership and its regression). It is included in combined branch [review/pr15955-stack-design-20261117](https://github.com/newling/rocm-libraries/tree/review/pr15955-stack-design-20261117) at [0d196f6a03ad](https://github.com/newling/rocm-libraries/commit/0d196f6a03ad5bc05736e7343c1fb710e6c09b3b). The sequence-interface reduction, dependency provisioning and full-build performance comparison remain proposals, not completed changes.
