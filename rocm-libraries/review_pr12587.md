This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12587](https://github.com/ROCm/rocm-libraries/pull/12587)

Reviewed head: `4313b77c4df2fd2f12c9f69d22a86891eab3f0f8`. Incremental base: `ce54ac0b7db8c845d943ac48f69afb40f19d429c`, the embedded version of #12586. This review covers the cache-mode layer, independently of the later tuner.

Suggestion branch: [review/pr12587-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12587-suggestions), based on that exact head. Its one additional commit is [1666def8a5a — report the selected kernel in extended profiling](https://github.com/newling/rocm-libraries/commit/1666def8a5a362416921279165655c48223caca1).

## Tests

The submitted host library and clients build and all 20 store tests pass; the suggestion branch passes 26 cache GPU tests on MI300X, with one revision-dependent test skipped, and the profiling counterexample fails before the fix and passes afterward.

The source mirror has no Git revision, so `UnnamedEntryFromThisBuildIsUsed` cannot test a matching nonempty build stamp. Testing used six matching gfx942 logic files covering FP16, FP32, XF32 and grouped selection. The installed ROCm 7.2 metadata was incompatible with this newer loader; an initial four-file generated library also lacked the grouped/XF32 cases. Those environment gaps were resolved by generating the matching additional files, without changing the product tests.

CI is not green. The Linux job cannot find `hipblaslt-tuning-store-test`; Windows imports the private datatype parsers incorrectly. Both originate in the embedded #12586 and are fixed in its current head. The ASAN smoke job times out before a test banner, without a sanitizer diagnostic. The race job's hipBLASLt benchmark check passes; its TensileLite-client step fails because `joblib` is missing. These results do not establish broad GPU or sanitizer coverage for this PR.

## Summary

#12586 supplies keys, rows and storage. This PR makes that store an opt-in runtime input: `HIPBLASLT_TUNING_MODE=cache` selects a cache path, validates entries against the running library and problem, and falls back to normal selection when none is usable. It also connects cache lookup to a matmul with `algo=nullptr`, which otherwise bypasses the public heuristic-query entry point. #12588 subsequently adds measurement and writing; this layer only reads.

Keeping an explicitly supplied algorithm authoritative is a useful API boundary. The non-mutating support probe also matters: an unsuccessful cache lookup must not leave the problem changed for the ordinary launch. The tests distinguish a real cache choice from the default and check a nonzero product, rather than relying only on counters.

## Actionable items

### Extended profiling names a different kernel from the one launched

At [`tensile_host.cpp:3724`](https://github.com/ROCm/rocm-libraries/blob/4313b77c4df2fd2f12c9f69d22a86891eab3f0f8/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L3724), the extended profile obtains kernel and solution names from `*algo`. The null-algorithm path has already filled that with the default selection; a cache hit changes only `solutionIndex`. The resulting profile combines the cached index with the default kernel's names.

I reproduced this by running the existing named-entry and null-algorithm replay tests with extended profiling. Both launched the same cached index, but the profile produced two different kernel names. This can misidentify the kernel when investigating tuning or reproducing a performance result; the numerical launch itself remained correct.

[1666def8a5a](https://github.com/newling/rocm-libraries/commit/1666def8a5a362416921279165655c48223caca1) copies the algorithm locally and puts the actual launch index into it before resolving both names. After rebuilding, the two calls produce one matching profile entry with `call_count: 2`. The caller's algorithm remains unchanged.

## Suggestions

No additional implementation suggestions from this pass.

## Commentary

Restack this and the descendants on the current #12586 before assessing their combined CI. Its Windows/test-packaging corrections are absent here. The [separate store review and persistence fixes](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12586_v2_with_fixes.md) also remain relevant when #12588 introduces the production writer.

The name-validation policy, legacy-row compatibility and omissions from the problem key are inherited contracts. This review does not reopen stronger solution fingerprints as a prerequisite. Runtime support validation is still necessary even with an exact key, because values such as beta and C/D aliasing are deliberately outside it.

The process remembers which files and problem keys it has seen. A missing file is retried, but an existing file is loaded once; this is not a live cache-file watcher. The added per-key diagnostic state likewise lasts for the process. Those are reasonable boundaries if kept explicit in the documentation.

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

The final assertion fails on the submitted implementation and passes with the linked commit. The branch contains only the logging fix; it does not incorporate the predecessor fixes or change the public tests. Full-device-library, native Windows and multi-device execution were omitted.
