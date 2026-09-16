This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#10424](https://github.com/ROCm/rocm-libraries/pull/10424)

## Tests

Current PR CI checks passed. A feature-enabled `hipblaslt` build compiled the changed cache sources, including the parser, replay code, and tuning path, but the local build could not complete because its YAML configuration lacks `msgpack.hpp`; the GPU `TuningCache` suite was not runnable because this host lacks the client build's BLIS dependency.

## Summary

This adds an opt-in runtime tuning cache to hipBLASLt, with a widened semantic cache key, per-entry kernel-name validation, guarded replay, bounded tuning work, and a scratch-backed measurement path. The replay path does a careful support check rather than trusting an index alone, and the cache parser preserves legacy rows separately from the new schema so old offline files do not acquire accidental matches. The new tests also cover several important failure boundaries, including malformed rows, stale names, incomplete searches, and in-place nonzero-beta calls.

The implementation needs one CI configuration that actually enables the feature. Otherwise the newly added code and its tests are not part of any default build or test lane.

## Actionable items

### Exercise the feature-enabled configuration in CI

`projects/hipblaslt/CMakeLists.txt:72` declares `HIPBLASLT_ENABLE_TUNING_CACHE` with a default of `OFF`, while `projects/hipblaslt/clients/tests/src/CMakeLists.txt:25` adds `tuning_cache_test.cpp` only when that option is enabled. This PR changes neither a CI preset nor a CI invocation to turn the option on, so the existing CI jobs compile the cache out and never compile or run the 18 new `TuningCache` tests. Add a focused hipBLASLt CI configure/test lane (or enable the option in an appropriate existing lane) with `-DHIPBLASLT_ENABLE_TUNING_CACHE=ON`, and run the standard category there. That gives the new compile-time branch and its GPU behavior a regression signal.

## Suggestions

None.

## Commentary

The separate legacy and current-key maps are a sound compatibility boundary: they preserve historical replay behavior without weakening the richer cache key for rows written by this feature.
