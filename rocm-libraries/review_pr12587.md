This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12587](https://github.com/ROCm/rocm-libraries/pull/12587)

Reviewed head: [4313b77c4df](https://github.com/ROCm/rocm-libraries/commit/4313b77c4df2fd2f12c9f69d22a86891eab3f0f8). Incremental base: [ce54ac0b7db](https://github.com/ROCm/rocm-libraries/commit/ce54ac0b7db8c845d943ac48f69afb40f19d429c), the embedded [#12586](https://github.com/ROCm/rocm-libraries/pull/12586). This review covers cache replay; [#12588](https://github.com/ROCm/rocm-libraries/pull/12588) adds the runtime search afterward.

Suggestion branch: [review/pr12587-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12587-v2-suggestions), based on that exact head ([suggestion diff](https://github.com/newling/rocm-libraries/compare/4313b77c4df2fd2f12c9f69d22a86891eab3f0f8...1666def8a5a362416921279165655c48223caca1)). Its sole additional commit is [1666def8a5a](https://github.com/newling/rocm-libraries/commit/1666def8a5a362416921279165655c48223caca1), which fixes the profile names described below. The implementation and previously validated tree are unchanged in this review revision.

## Tests

The submitted host library and clients build and all 20 store tests pass; the suggestion branch passes 26 cache GPU cases on MI300X, and the profiling counterexample fails before the fix and passes afterward.

Testing used a matching, scoped gfx942 device library. One matching-build-stamp case was skipped because this build had no Git stamp; native Windows and multi-device execution were omitted. These results are retained from the unchanged revisions.

CI remains red. Linux cannot find the packaged store-test executable, and Windows fails on private parser imports; both originate in the embedded [#12586](https://github.com/ROCm/rocm-libraries/pull/12586) and are corrected in its current head. The ASAN smoke job times out before the test banner without a sanitizer diagnostic. The race job's hipBLASLt benchmark step passes, while its TensileLite-client step lacks `joblib`. Those results do not establish broad CI or sanitizer coverage.

## Summary

This PR makes [#12586](https://github.com/ROCm/rocm-libraries/pull/12586)'s tuning store an opt-in runtime input. `HIPBLASLT_TUNING_MODE=cache` loads entries, checks their identity and support for the current problem, and falls back to ordinary selection when none is usable. It also serves matmul calls with `algo=nullptr`, which otherwise bypass the public heuristic-query entry point. This layer reads the store; [#12588](https://github.com/ROCm/rocm-libraries/pull/12588) introduces measurement and writing.

Preserving an explicitly supplied algorithm is a useful API boundary. The non-mutating support probe also protects fallback: rejecting a cached entry must leave the problem ready for ordinary execution. The tests distinguish the cached kernel from the default and check nonzero numerical output.

## Actionable items

### Resolve profile names from the kernel that actually launched

At [`tensile_host.cpp:3724`](https://github.com/ROCm/rocm-libraries/blob/4313b77c4df2fd2f12c9f69d22a86891eab3f0f8/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L3724), extended profiling obtains names from `*algo`. In the null-algorithm path, that object still contains the default selection after a cache hit changes `solutionIndex`. The profile therefore combines the cached index with the default kernel's names.

The existing named-entry and null-algorithm replay tests both launch the same cached index, but together produce two different profile names. This can misdirect a tuning or performance investigation. The numerical launch remains correct, so the scope of the defect is diagnostic accuracy.

Commit [1666def8a5a](https://github.com/newling/rocm-libraries/commit/1666def8a5a362416921279165655c48223caca1) resolves both names from a local algorithm copy containing the actual launch index. It preserves the caller's object. The same check then produces one matching entry with `call_count: 2`; the exact check is below.

## Suggestions

No further implementation suggestions from this pass.

## Commentary

An existing cache file is loaded once per process; a missing file is retried. The design does not promise to notice later edits to an already loaded file. The lookup, fallback and lifetime paths did not reveal another concrete defect in this pass.

Restacking on current [#12586](https://github.com/ROCm/rocm-libraries/pull/12586) is needed to pick up its Windows and packaging corrections. The [separate persistence review](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12586_v2_with_fixes.md) remains relevant when the later layer adds writing. Legacy compatibility, schema naming and stronger solution fingerprints belong to that earlier contract; they do not justify additional change requests in this replay layer.

## Reproducing the profiling check

Use a build with at least two supported FP16 candidates and its matching device library:

```bash
env -u HIPBLASLT_LOG_LEVEL HIPBLASLT_LOG_MASK=128 \
  "$BUILD_DIR/clients/hipblaslt-test" \
  --gtest_filter=TuningCache_pre_checkin.NamedEntryReplays:TuningCache_pre_checkin.NullAlgoLaunchesTheCachedKernel \
  > profile.log 2>&1
python3 - <<'PY'
import re
from pathlib import Path
text = Path('profile.log').read_text()
assert '[  PASSED  ] 2 tests.' in text
rows = re.findall(r'solution_index: (\d+), solution_Name: (.*?), kernel_name: ([^,]+), call_count: (\d+)', text)
assert rows and sum(int(row[3]) for row in rows) == 2
assert len({row[0] for row in rows}) == 1
assert len({(row[1], row[2]) for row in rows}) == 1
PY
```

The final assertion fails on the submitted implementation and passes with [1666def8a5a](https://github.com/newling/rocm-libraries/commit/1666def8a5a362416921279165655c48223caca1). The branch contains only the logging fix; it does not add a shared-CI regression or incorporate predecessor fixes.
