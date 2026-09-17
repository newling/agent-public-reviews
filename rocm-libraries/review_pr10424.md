This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#10424](https://github.com/ROCm/rocm-libraries/pull/10424)

**Proposed fixes:** Prepared locally on `followup/pr10424-cache-contract` at `1c6965ba652`; add the draft PR link when publication is authorized.

## Tests

`git diff --check` passed, and feature-enabled plus default-off gfx1201 host builds completed. The proposed fix's three host-only `TuningCacheMap` tests pass, and its modified integration sources compile. GPU integration execution was not completed because the installed gfx1201 artifacts do not provide the mapping layout expected by this checkout. The current public CI checks pass, but the default-off feature is not enabled by those jobs.

## Summary

This is 6,410 added lines across 18 files and contains at least five independently reviewable contracts: fixes to the existing override path, a new persistent format and cache identity, execution-time benchmarking, partial-search recovery, and custom lifecycle diagnostics. The strict parser, copied map results, and scratch isolation address real failure modes, but combining all of them makes both compatibility and runtime behavior difficult to establish.

The cache contract is not ready to carry the benchmarking machinery yet. A completed result can be hidden by an older partial row, the cross-build identity deliberately omits launch-shaping defaults, and the purported semantic key cannot represent several values that affect selection. I recommend splitting the change and landing the existing correctness fixes before the runtime tuner.

## Actionable items

### Prefer the completed result over an older partial row

`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/UserDrivenTuningParser.hpp:783-790,825-828,870-883` preserves distinct entries for one key in file order, and `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp:330-348` stops at the first valid entry. If an incomplete row selects kernel A and a later finishing run appends a different kernel B, a fresh process loads `[A incomplete, B complete]` and always replays A. `needsFinishing()` sees B and suppresses any further tune, so the completed winner is permanently unreachable. The test at `projects/hipblaslt/clients/tests/src/tuning_cache_test.cpp:1393-1419` checks only that another row is not appended; it never checks which row is selected.

Define precedence for current-schema rows and test it directly. For an append-only managed cache, replay should try the newest complete entry first, then newer partial entries, while legacy override rows can retain their historical ordering. Add a regression where A and B have different indexes/names and assert that B is the replayed result after reload.

### Validate the launch configuration that was measured

`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/UserDrivenTuningParser.hpp:429-440` explicitly chooses `kernelName` because it omits solution defaults such as GSU, stagger-U, and WGM. Replay at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp:207-223` therefore accepts an entry when the solution index and bare kernel name still match even if a new build changed those defaults. The tuner measured the old launch configuration, but replay runs the new one; the per-entry check no longer establishes that the cached choice is what was tuned.

Persist and validate a durable launch signature containing every solution parameter that affects dispatch, or retain the build-stamp gate until such an identity exists. The offline writer should not strip custom GSU/WGM information unless the replacement identity records it elsewhere.

### Build the managed-cache key where the real problem is available

`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/UserDrivenTuningParser.hpp:239-267,325-385` calls `ProblemOverride` a complete semantic key, but it deliberately collapses transpose and conjugate-transpose, omits alpha, beta, and C/D aliasing, and also misses `col_stride_e`, `batch_stride_e`, and `uniform_summation_order`. The latter fields exist on `RocblasltContractionProblem` at `projects/hipblaslt/library/src/amd_detail/rocblaslt/include/rocblaslt-types.h:556-560,612-616`, and uniform summation order directly changes solution eligibility. The heuristic path cannot recover the first set because it constructs null C/D pointers and fabricated alpha/beta values before lookup.

This creates collisions between calls that were tuned under different predicates. A support check prevents some invalid launches, but the result is still unstable cache behavior: an entry can be rejected at heuristic time despite being valid for the real call, or one variant can replace another variant under the same key. Either move managed-cache replay to the execution path, where the actual scalar values and aliases exist, or explicitly exclude these cases and add every remaining selection-relevant field to the schema and key. Do not describe the key as semantic while known selection inputs are absent.

### Exercise the feature-enabled configuration in CI

`projects/hipblaslt/CMakeLists.txt:70-76` defaults `HIPBLASLT_ENABLE_TUNING_CACHE` to `OFF`, while `projects/hipblaslt/clients/tests/src/CMakeLists.txt:24-31` adds `tuning_cache_test.cpp` only when it is enabled. No changed CI configuration turns it on, so passing default jobs neither compile this branch of the library nor run its tests. Add a focused hipBLASLt lane configured with `-DHIPBLASLT_ENABLE_TUNING_CACHE=ON` and run the standard category there.

### Keep test controls out of the production ABI

`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp:3150-3224` adds three `HIPBLASLT_EXPORT` functions described as test-only. They are globally visible in a feature-enabled production object, can reset process-wide maps and singleton state, and are not guarded by a testing build option. `projects/hipblaslt/CMakeLists.txt:386-389` also propagates the internal feature macro publicly solely to support the tests.

Test the parser/store through an internal test target or run mode-dependent integration cases in separate processes. If reset hooks remain necessary, compile them only under `HIPBLASLT_BUILD_TESTING`; keep the feature definition private and set it explicitly on the test target.

## Suggestions

### Split the change along behavior boundaries

The current non-merge history already exposes useful seams. I suggest this order:

| Review unit | Scope | Focused validation |
|---|---|---|
| 1. Existing override correctness | Lock-safe lookup copies, per-entry result clearing, solution index zero, empty-file load latching, initialized result counts, and null-safe name lookup | Small regressions for each existing bug; no new mode, format, or benchmarking |
| 2. Versioned cache identity and replay | Add `kernel_name`, the current-schema key, strict parsing, entry precedence, and replay validation | Host-only parser/map tests plus a small GPU replay test |
| 3. Minimal online tuner | Add `tune` mode, scratch isolation, candidate measurement, and persistence of complete winners | Correct output, one tune/replay round trip, allocation/error fallback, and concurrency smoke tests |
| 4. Measurement policy | Exhaustive enumeration, rotating buffers, instruction-cache flushing, and their tuning controls | Comparisons against `hipblaslt-bench` on representative shapes |
| 5. Partial results and observability | Budgeted partial entries, top-up semantics, counters, bounded lifecycle logs, and exit summary | Deterministic store-order tests and focused logging tests |

Units 1 and 2 provide useful fixes without accepting an in-process benchmarker. Unit 3 can use fixed internal measurement defaults; units 4 and 5 can then change quality and operations without reopening the cache correctness contract.

### Reduce the initial configuration surface

`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp:3491-3614` introduces controls for enumeration, candidate count, cold iterations, hot iterations, rotation size, instruction-cache flushing, per-shape budget, and scratch capacity in addition to mode and path. Each variable is a lasting user-facing behavior with parsing, interaction, documentation, and test costs. Start with mode, path, and one effort/budget control; keep measurement constants internal until evidence shows users need each independent knob.

### Remove state that has no consumer

`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/UserDrivenTuningParser.hpp:139,224-230,443-485` includes an unused `reads()` method, an entry `source` that is written but never read, and persisted `requiredWorkspaceBytes`/`winnerTimeUs` values that replay does not consume. Remove unused state before making it part of the file format, or add the concrete consumer and tests that justify it.

### Separate cache, tuner, and diagnostics implementations

The PR adds roughly 2,300 lines to `UserDrivenTuningParser.*` and 1,900 lines to `tensile_host.cpp`. Put the versioned store/key in a `TuningCache` component, the scratch benchmarker in a `RuntimeTuner` component, and optional telemetry in a diagnostics component. This does not replace the behavioral split above, but it will keep the execution path and legacy override parser reviewable as those pieces evolve.

## Commentary

The safest parts are the independent fixes to the old override path and the decision to copy matching entries while holding the map lock. Those should not be held behind the larger product decision. The new strict row parser and separate legacy-key map are also reasonable foundations once row precedence and the actual key/identity contracts are settled.
