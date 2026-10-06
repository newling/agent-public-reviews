This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12589](https://github.com/ROCm/rocm-libraries/pull/12589)

Reviewed head: [8130bddadb6](https://github.com/ROCm/rocm-libraries/commit/8130bddadb638a841a24c7f4ab020ec3a1d39a35). Incremental base: [#12588](https://github.com/ROCm/rocm-libraries/pull/12588) at [1d38aaf48da](https://github.com/ROCm/rocm-libraries/commit/1d38aaf48da6878c8dcd285963a3ab7873a8cbaa). [#12590](https://github.com/ROCm/rocm-libraries/pull/12590) is a sibling, not a prerequisite.

Suggestion branch: [review/pr12589-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12589-v2-suggestions), based on that exact head ([suggestion diff](https://github.com/newling/rocm-libraries/compare/8130bddadb638a841a24c7f4ab020ec3a1d39a35...cbf2f2637b7d6425839ca43cabbfdc7551068812)). Both implementations and the previously validated tree are unchanged.

| Commit | Review item |
| --- | --- |
| [7262078933b](https://github.com/newling/rocm-libraries/commit/7262078933b4d3424eefb7d40ff82c02bc75397c) | Validate retune-blocking rows; includes the GPU regression. |
| [cbf2f2637b7](https://github.com/newling/rocm-libraries/commit/cbf2f2637b7d6425839ca43cabbfdc7551068812) | Optional equality policy for flush/rotation conditions; includes host regression and documentation. |

The second commit can be considered independently. Neither resolves the selection-precedence decision below.

## Tests

The submitted library and clients build, its 31 store tests and 31 available tuner GPU cases pass, and both added regressions fail before their fixes; the suggestion branch passes all 32 store tests under ASAN+UBSAN and 58 cache/tuner GPU cases on MI300X.

The stale-row regression produces zero attempts and leaves two rows on the submitted code; the fix makes one attempt and appends the third row. The separate reopen counterexample below still fails after both commits, as expected for the unresolved policy issue.

Three GPU cases were skipped: matching an unnamed row to a nonempty build stamp, FP8 FNUZ selection unavailable in the scoped device library, and scratch across two visible GPUs. Native Windows and full-device-library coverage were omitted. These results are retained from the unchanged revisions. CI remains red, including inherited failures from old [#12586](https://github.com/ROCm/rocm-libraries/pull/12586); see the [cache-layer review](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12587.md).

## Summary

This PR lets a budget-stopped search retain its fastest measured candidate when the untuned algorithm was measured too. Schema version 2 records completion, budget, candidate search, workspace and measurement settings so a later process can decide whether another search is worthwhile.

Separating a usable kernel from a finished search is useful: a partial result can serve calls while a later, larger search remains possible. Measuring the baseline first avoids choosing from a prefix that omitted the algorithm the call would otherwise use. The new persistence and retuning rules need to agree about which measurements remain authoritative across process restarts.

## Actionable items

### Rejected rows must not suppress retuning

At [`TuningCacheStore.hpp:563`](https://github.com/ROCm/rocm-libraries/blob/8130bddadb638a841a24c7f4ab020ec3a1d39a35/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/TuningCacheStore.hpp#L563), `needsRetune` considers every row's metadata. Its caller separately checks whether some row is usable. Different rows can satisfy those two checks.

For example, a file contains a completed search whose kernel name no longer matches and a valid partial search with a one-second budget. Replay rejects the completed row and uses the partial one. An unlimited run should finish the valid search, but the rejected completed row makes `needsRetune` return false. The cache cannot repair this state.

Commit [7262078933b](https://github.com/newling/rocm-libraries/commit/7262078933b4d3424eefb7d40ff82c02bc75397c) shares the identity, support and workspace validation between replay and the retune decision. The store applies that predicate to copied rows outside its lock. [StaleCompletedRowDoesNotFinalizeAValidPartial](https://github.com/newling/rocm-libraries/blob/7262078933b4d3424eefb7d40ff82c02bc75397c/projects/hipblaslt/clients/tests/src/tuning_tune_test.cpp#L1537) creates this mixed file and checks that an unlimited run tunes and appends a replacement. Existing valid-completed and same-budget-partial cases continue to pass.

### Preserve the same selection before and after reopening the file

[`OverrideMap::find` at `TuningCacheStore.hpp:508`](https://github.com/ROCm/rocm-libraries/blob/8130bddadb638a841a24c7f4ab020ec3a1d39a35/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/TuningCacheStore.hpp#L508) puts completed rows before partial ones. Meanwhile, [`tensile_host.cpp:5296`](https://github.com/ROCm/rocm-libraries/blob/8130bddadb638a841a24c7f4ab020ec3a1d39a35/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L5296) replaces all in-memory rows with the new winner but only appends it to the file.

A completed two-candidate search selects A. A later sixteen-candidate search is interrupted after selecting B. The current process replaces A with B and uses B. After restart, completed-first ordering selects A again. With the same sixteen-candidate settings and budget, the partial row also suppresses another attempt. B can remain unused in the file despite having been the active winner before exit.

Choose one precedence policy and apply it to both live state and reload. Completion can be interpreted relative to the search it describes; alternatively, a policy that always prefers the old completed row should retain that winner in the live process too. Add a reopen regression for a widened, truncated search. No fix is supplied because these alternatives require a selection-policy decision. The exact host counterexample below demonstrates the mismatch without depending on GPU timing noise.

## Suggestions

### Consider requiring matching cache conditions before reusing a search

At [`TuningCacheStore.hpp:315`](https://github.com/ROCm/rocm-libraries/blob/8130bddadb638a841a24c7f4ab020ec3a1d39a35/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/TuningCacheStore.hpp#L315), a completed search with flushing covers one without it, and a larger rotating-memory setting covers a smaller one. Those settings change the measured workload. A winner with cold inputs need not win with cache-resident inputs, so turning rotation or flushing off can keep a winner measured under different conditions.

Optional commit [cbf2f2637b7](https://github.com/newling/rocm-libraries/commit/cbf2f2637b7d6425839ca43cabbfdc7551068812) requires equal flush and rotation settings while preserving the existing ordering for candidate count, workspace and iteration counts. Its host regression checks both directions of each cache-setting change.

This is a policy choice, not an established numerical defect. Equality honors explicit measurement choices, but can cause expensive retuning when different requested rotation sizes produce the same effective layout after memory-cap trimming. Consider that cost before adopting the commit; normalizing effective conditions would require a larger design change.

## Commentary

The baseline comparison holds under the tuning conditions and their measurement noise. It does not guarantee improved production performance. The attempt latch also remains process-wide per problem key: changing settings is intended to affect a later process, rather than repeatedly triggering work within one process.

Version-1 rows remain final without search metadata. That is an explicit compatibility tradeoff; schema naming and the legacy-reader lifetime are not additional blockers for this layer. The [earlier persistence fixes](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12586_v2_with_fixes.md) and current [#12586](https://github.com/ROCm/rocm-libraries/pull/12586) still need to be carried into the stack.

## Reopen counterexample

Append this test to [clients/tests/src/tuning_store_test.cpp](https://github.com/ROCm/rocm-libraries/blob/8130bddadb638a841a24c7f4ab020ec3a1d39a35/projects/hipblaslt/clients/tests/src/tuning_store_test.cpp); it uses that file's existing fixture and row helpers. Run `hipblaslt-tuning-store-test --gtest_filter=TuningStore.WiderPartialWinnerChangesAfterReload` (or the renamed store-test executable after restacking [#12586](https://github.com/ROCm/rocm-libraries/pull/12586)):

```cpp
namespace
{
    TEST_F(TuningStore, WiderPartialWinnerChangesAfterReload)
    {
        const auto key = halfKey();
        const auto narrow = tunedEntry(1, "narrow", true, 0, rankedSearch(2));
        const auto widerPartial = tunedEntry(2, "wider-partial", false, 1000, rankedSearch(16));
        OverrideMap live;
        live.add(key, narrow);
        live.replaceAll(key, widerPartial);
        OverrideMap reopened;
        ASSERT_EQ(loadInto(reopened, fileOf({tunedRow(key, narrow), tunedRow(key, widerPartial)})).accepted, 2u);
        EXPECT_EQ(live.find(key).front().solutionIndex, reopened.find(key).front().solutionIndex);
        EXPECT_FALSE(reopened.needsRetune(key, rankedSearch(16), 1000));
    }
}
```

The first expectation fails: live selection is 2, reloaded selection is 1. The second passes, showing that the partial row suppresses another equal-budget attempt after reload. The failing policy probe is preserved here rather than committed as a failing product test. The branch contains the two mapped changes and their passing regressions; precedence and restacking remain unresolved.
