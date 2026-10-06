This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12589](https://github.com/ROCm/rocm-libraries/pull/12589)

Reviewed head: `8130bddadb638a841a24c7f4ab020ec3a1d39a35`. Incremental base: #12588 at `1d38aaf48da6878c8dcd285963a3ab7873a8cbaa`. #12590 is a sibling, not this PR's prerequisite.

Suggestion branch: [review/pr12589-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12589-suggestions), based on that exact head.

| Commit | Review item |
| --- | --- |
| [7262078933b](https://github.com/newling/rocm-libraries/commit/7262078933b) | Validate rows before allowing their metadata to suppress retuning; includes a GPU regression. |
| [cbf2f2637b7](https://github.com/newling/rocm-libraries/commit/cbf2f2637b7d6425839ca43cabbfdc7551068812) | Retune when flush/rotation conditions change; includes a host regression and documentation. |

The second change is a policy suggestion and can be considered separately. Neither commit resolves the live-versus-reloaded precedence decision described below.

## Tests

The submitted library and clients build, its 31 store tests and 31 available tuner GPU cases pass, and both new regressions fail before their fixes; the suggestion branch passes all 32 store tests under ASAN+UBSAN and 58 cache/tuner GPU cases on MI300X.

Three cases in the combined GPU run are skipped: matching an unnamed row to a nonempty Git build stamp, FP8 FNUZ selection unavailable in the scoped device library, and scratch allocation across two visible GPUs. The GPU regression for a stale completed row fails on the submitted implementation with zero tuning attempts and two unchanged file rows; the fix produces one attempt and appends the third row. The standalone reopen counterexample below still fails after these two commits, as expected: that policy issue is deliberately left unresolved.

Current CI is red, and this head still embeds the old #12586 rather than its current Windows/test-packaging corrections. See the [cache-layer review](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12587.md) for diagnosed inherited failures. These focused runs do not establish full-device-library, native Windows or multi-device coverage.

## Summary

#12588 either completes a search or discards its measurements. This PR keeps a winner from a budget-stopped search, provided the untuned algorithm was measured too. Schema version 2 records completion, budget, candidate search, workspace and measurement settings so later processes can decide whether another search is worthwhile.

The useful design distinction is between a kernel being usable and its search being final. A partial winner can serve calls immediately while a larger later budget permits more work. Measuring the baseline first also gives the partial result a meaningful comparison, subject to ordinary timing noise. Keeping this policy separate from the runtime tuner makes it possible to review and adjust those rules without changing the measurement loop.

## Actionable items

### Rejected rows must not suppress retuning

At [`TuningCacheStore.hpp:563`](https://github.com/ROCm/rocm-libraries/blob/8130bddadb638a841a24c7f4ab020ec3a1d39a35/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/TuningCacheStore.hpp#L563), `needsRetune` considers every stored row's metadata. The caller separately asks whether *some* row is usable. Those two questions can be answered by different rows.

For example, a file contains a completed search whose kernel name no longer matches and a valid partial search with a one-second budget. Replay rejects the completed row and uses the partial one. An unlimited tune-mode run should finish the valid partial search, but `needsRetune` sees the rejected completed row and returns false. The cache never repairs this state.

[7262078933b](https://github.com/newling/rocm-libraries/commit/7262078933b) shares the existing identity, problem-support and workspace probe with the retune decision. The store applies that predicate to copied rows outside its lock. The regression `StaleCompletedRowDoesNotFinalizeAValidPartial` creates exactly this mixed file and checks that the unlimited run tunes and appends a replacement. Existing valid completed and same-budget partial cases still pass.

### Make live and reloaded selection agree after a wider search is truncated

[`OverrideMap::find` at `TuningCacheStore.hpp:508`](https://github.com/ROCm/rocm-libraries/blob/8130bddadb638a841a24c7f4ab020ec3a1d39a35/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/TuningCacheStore.hpp#L508) unconditionally puts completed rows before partial ones. Meanwhile, [`tensile_host.cpp:5296`](https://github.com/ROCm/rocm-libraries/blob/8130bddadb638a841a24c7f4ab020ec3a1d39a35/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L5296) replaces all in-memory rows with the newly measured winner but only appends it to the file.

Suppose a completed two-candidate search selected A. A later sixteen-candidate search is interrupted after finding B. The current process replaces A with B and uses B. On restart, both rows are loaded, and the unconditional completed-first ordering selects A again. Under the same sixteen-candidate settings and budget, the partial row also suppresses another search. Thus B can remain in the file without being used, despite having been the active winner before exit.

Make precedence consistent between memory and reload. Completion needs to be interpreted relative to what was searched; alternatively, if the intended policy is always to prefer the old completed row, preserve that choice in the live process too. Add a reopen test for a widened search that is truncated. I have not implemented this item because those alternatives imply different selection policies. The exact host counterexample is below; it reproduces the mismatch with indexes 2 and 1 and does not depend on noisy GPU timings.

## Suggestions

### Treat cache conditions as measurement choices, not an ordered quality scale

At [`TuningCacheStore.hpp:315`](https://github.com/ROCm/rocm-libraries/blob/8130bddadb638a841a24c7f4ab020ec3a1d39a35/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/TuningCacheStore.hpp#L315), `tuningSearchCovers` treats flushing as covering no flushing, and a larger rotating-memory setting as covering a smaller one. More candidates and more samples can reasonably count as more search work. Different cache conditions change what is measured: #12588's own motivation is that warm and cold inputs can reorder the candidates.

With the current rule, a user who switches from rotating buffers to `HIPBLASLT_TUNING_ROTATING_MB=0` can silently keep a winner measured for the other regime. The same asymmetry applies to turning instruction-cache flushing off.

[cbf2f2637b7](https://github.com/newling/rocm-libraries/commit/cbf2f2637b7d6425839ca43cabbfdc7551068812) requires the same flush setting and rotation size before a completed search covers a later run. It retains the ordering for candidate count, workspace and iteration counts. Its host regression verifies both directions of each cache-condition change. This intentionally trades additional tuning for honoring the requested measurement conditions.

## Commentary

A partial result is not a guarantee of better production performance. The comparison is to the measured baseline under the tuning conditions. Moving the baseline first prevents an arbitrary measured prefix from excluding it, but does not remove measurement noise or differences between tuning and normal execution.

The attempt latch is process-wide per problem key, so a shape whose partial search is already latched will not adapt to changed settings in that same process. The documented model is to change settings for a later run. #12590's benchmark integration should preserve this distinction when describing widening behavior.

Version 1 rows remain final without search metadata, while version 2 rows require the new fields. That compatibility choice means old files cannot express whether a newer requested measurement regime was covered. It is deliberate compatibility behavior, distinct from the rejected-row bug above. The inherited store persistence findings remain in the [#12586 review](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12586_v2_with_fixes.md).

## Reopen counterexample

Append this test to `clients/tests/src/tuning_store_test.cpp`; it uses that file's existing fixture and row helpers. Run `hipblaslt-tuning-store-test --gtest_filter=TuningStore.WiderPartialWinnerChangesAfterReload` (or the renamed store-test executable after restacking #12586):

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

The first expectation fails: live selection is 2, reloaded selection is 1. The second passes, showing that the reloaded partial row closes the retune gate under the same budget. This reproducer is preserved here rather than committed as a failing product test. The branch contains the two mapped changes and their passing regressions; resolving this precedence policy and restacking the earlier layers remain separate work.
