This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#10424](https://github.com/ROCm/rocm-libraries/pull/10424)

**Review companion:** [PR #1](https://github.com/newling/agent-public-reviews/pull/1)

## Tests

Current PR CI checks passed. A feature-enabled local build compiled the changed cache sources, but the GPU `TuningCache` suite was not runnable because this host lacks the client build's BLIS dependency.

## Summary

This adds an opt-in runtime tuning cache with per-entry validation and a separate legacy-key path. The cache/replay boundary is thoughtfully guarded, but the feature-enabled configuration needs CI coverage.

## Actionable items

### Exercise the feature-enabled configuration in CI

`projects/hipblaslt/CMakeLists.txt:72` defaults `HIPBLASLT_ENABLE_TUNING_CACHE` to `OFF`, and `projects/hipblaslt/clients/tests/src/CMakeLists.txt:25` adds `tuning_cache_test.cpp` only when it is enabled. No CI configuration enables it, so current CI compiles the feature out and never runs the new tests. Add a focused hipBLASLt lane with `-DHIPBLASLT_ENABLE_TUNING_CACHE=ON` and the standard test category.

## Suggestions

None.

## Commentary

The separate legacy and current-key maps preserve compatibility without weakening the new key.
