This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#10424](https://github.com/ROCm/rocm-libraries/pull/10424)

**Revision reviewed:** `2de5d9dcef73b1cc1e08a289170503b8b812e6cc`

## Tests

`git diff --check` passed. Default-off and feature-enabled host builds completed for gfx1201, feature-enabled host and client-test builds completed for gfx942, and a filtered gfx942 device library generated successfully. Under gfx942 rocJITsu emulation, the off-mode, missing-path, in-place/nonzero-beta, and exact-shape tune/write paths passed. A host-only map probe reproduced the completed-row ordering problem below. I did not run the full `TuningCache` fixture because the filtered emulated library does not contain every shape and FP8 path that fixture needs.

All required GitHub checks currently pass. The separate hipBLASLt coverage check fails with 6.61% patch coverage and 791 changed lines uncovered. More importantly, the repository's automated builds leave `HIPBLASLT_ENABLE_TUNING_CACHE` off, so those green checks do not compile or execute most of this feature or `tuning_cache_test.cpp`.

## Summary

The reviewed head has not changed since the earlier request-changes review, so the requests to split the work, make concurrent tuning deterministic, share the benchmark implementation, define an identity that includes launch settings, repair the C++ build-version behavior, and avoid a long-lived CMake variant still apply. This follow-up concentrates on additional correctness and security findings from tracing cache lookup through the real execution path and testing the persistent-map behavior.

There are useful pieces here. In particular, the current-schema parser validates key columns more strictly than the legacy parser, candidate measurements use library-owned output and workspace storage, and the execution path restores the caller's problem after benchmarking. However, a cache hit does not reliably select the cached winner, and the persistence rules below can make an incomplete or differently scoped search permanent. Those issues affect the central behavior the feature is meant to provide.

## Actionable items

### Use the cached solution for the actual launch

`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp:4970-4997,5128-5146,5287-5292` leaves `solutionIndex` pointing at the algorithm supplied by the caller, or at the ordinary default selected for `algo == nullptr`. `tuning_cache_has_valid_entry()` in `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp:414-503` returns only a boolean. Therefore, an existing cache entry can close the tuning gate without ever replacing the index used by the launch. `solutionIndex` changes only when this call itself benchmarks a new winner.

This is broader than the acknowledged `algo == nullptr` limitation. The documented usage is to query a heuristic once and reuse that algorithm. If a caller queries before the first tune, the first matmul benchmarks and launches the new winner, but every later matmul using the same algorithm object returns to the original algorithm while the cache reports a match. An explicitly supplied algorithm behaves the same way. The replay tests cannot detect this: `runGemm()` queries a fresh heuristic immediately before every matmul at `projects/hipblaslt/clients/tests/src/tuning_cache_test.cpp:229-265`, and the assertions at lines 790-805 and 847-859 check numerical output plus a hit counter. The execution-side availability probe itself increments that counter even when the cached index is not launched.

Make execution-time lookup return the selected entry or algorithm and use its index for the launch. If an explicit algorithm is intended to override the cache, apply that rule consistently—the first call must not silently override it through tuning, and telemetry must not report that the cache served the call. Add tests that query once and reuse the same algorithm object, plus an `algo == nullptr` case, and assert the index that reaches dispatch rather than only counters and numerical output.

### Ignore tuning environment variables in privileged processes

`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/UserDrivenTuningParser.cpp:61-94` reads the mode and writable cache path with plain `getenv()`. The measurement and allocation controls do the same at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp:3547-3668,3885-3896`. A set-user-ID, set-group-ID, or otherwise security-sensitive consumer can therefore inherit `HIPBLASLT_TUNING_MODE=tune` and an attacker-selected `HIPBLASLT_TUNING_CACHE_PATH`; `appendTunedEntry()` opens that path for append at `UserDrivenTuningParser.cpp:985-1002`. This permits an untrusted environment to make a privileged process perform long GPU work and write through attacker-selected paths, including symbolic links and special files.

The repository already centralizes this policy in `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/rocblaslt_secure_env.hpp:49-97`, with direct policy tests in `projects/hipblaslt/clients/tests/src/secure_env_gtest.cpp:118-155`. Use that privilege check to force the new tuning mode off before honoring the path or resource controls, and add a direct test showing that a forced privileged context cannot activate cache or tune mode even when every variable is present.

### Measure the algorithm the caller would otherwise run before saving a partial result

`benchmarkAndSelectWinner()` does not receive the selected algorithm (`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp:4325-4335`). Instead, it recomputes a baseline with `getBestRawSolutions()` at lines 4507-4515 and assumes `candidates.front()` is the untuned result at lines 4860-4885. That is not necessarily the algorithm this call was about to launch. The caller can supply an explicit algorithm, and the public heuristic can obtain a result from its `getAllSolutions()` fallback at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp:2619-2656` when the raw top-solution query is empty.

In either case, the caller's algorithm can differ from `baselineIndex`, or `baselineIndex` can remain `-1`. A budget-truncated search can then persist a winner slower than the algorithm it replaced, despite the code and documentation promising that a partial result is never slower than untuned execution. Pass the actual `*solutionIndex` selected for this call into the benchmarker, place that exact configuration first, and persist a partial row only after it has been measured successfully. This also needs a regression using a caller-selected non-default algorithm and a case where the public heuristic reaches its all-solutions fallback.

### Build and compare the key from the concrete execution problem

The key declared at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/UserDrivenTuningParser.hpp:231-385` collapses transpose and conjugate-transpose and omits `col_stride_e`, `batch_stride_e`, and `uniform_summation_order`, although those values are present on the execution problem at `projects/hipblaslt/library/src/amd_detail/rocblaslt/include/rocblaslt-types.h:506-619`. It also deliberately omits alpha, beta, and C/D aliasing even though the tuner measures with their real values. The C heuristic path cannot represent those values because it constructs a synthetic problem before the execution arguments exist.

The C++ path has a second consistency failure. It saves `tuningKey` when the GEMM object is created at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp:5514-5536`. `applyStreamKTileSchedulingMode()` and `applyUniformSummationOrder()` later change the Tensile problem at lines 3348-3403, immediately before cache lookup at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp:2834-2855`, but they never update the saved key.

These collisions can make one problem variant suppress tuning for another, make cache behavior depend on which variant ran first, and validate a cached algorithm against a synthetic problem that differs from the actual launch. Resolve the managed cache where the concrete execution problem and scalar categories are available, or explicitly exclude variants the lookup cannot represent. Version and store every remaining selection-relevant field, and rebuild the C++ key after any preference mutates the problem.

### Reject truncated current-schema value rows

`zipRow()` accepts only `min(header cells, value cells)` at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/UserDrivenTuningParser.cpp:538-555`. The current-schema validator at lines 700-776 requires columns only through `required_workspace`, while `complete` and `budget_ms` are appended at the end of a value row at lines 1082-1092 and default to complete/unknown at lines 914-924. If a process dies after writing the winner fields but before those final cells, `std::getline()` still returns the unterminated prefix and the parser accepts an incomplete search as a completed result. Tune mode then has no reason to finish it.

Require equal header/value cardinality for current-schema records and parse `complete` and `budget_ms` strictly. Since this schema has not shipped on `develop`, they can be mandatory in version 1; otherwise bump the schema. A record terminator or checksum would give stronger crash detection. Extend `tuning_cache_test.cpp:1008-1028`, which covers an orphan header only, with value rows truncated immediately before and within the completion fields.

### Prefer a completed row over the older partial row it supersedes

`OverrideMap::find()` returns equal-key rows in insertion order at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/UserDrivenTuningParser.hpp:774-793`, and the validity loop in `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp:423-480` stops at the first usable row. In contrast, `needsFinishing()` returns false as soon as it sees any complete row at `UserDrivenTuningParser.hpp:854-883`. An append-only file containing an older partial winner A followed by a completed winner B therefore replays A but refuses to tune again because B proves the search is complete.

The host-only probe in the appendix reproduces this state: replay sees index 11 while `needsFinishing()` returns false. Define one precedence rule and use it for both replay and retuning. For a managed append-only cache, prefer the newest valid complete row, followed by the newest valid partial row; preserve historical file order only for legacy override rows. Add a direct map/parser test that asserts the selected index, rather than only checking that another row was not appended. The current test at `projects/hipblaslt/clients/tests/src/tuning_cache_test.cpp:1389-1419` checks only the latter.

### Persist the search policy, not only its elapsed-time budget

`TunedEntry` stores only `complete` and `budgetMs` for search state (`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/UserDrivenTuningParser.hpp:446-469`), and `needsFinishing()` compares only those values at lines 854-883. Yet the candidate universe also depends on exhaustive versus ranked-prefix mode, the candidate cap, and the caller's workspace limit; measurement quality depends on cold/hot iterations, rotation, and instruction-cache flushing. For example, a completed 2-candidate ranked search permanently suppresses a later exhaustive run, and a complete result found with zero workspace prevents retuning when a larger workspace makes faster candidates available.

The same-budget shortcut is not sound for the default exhaustive mode either. `SolutionSet` is `std::set<std::shared_ptr<...>>` at `projects/hipblaslt/tensilelite/include/Tensile/SolutionLibrary.hpp:131-134`, and `getAllSolutions()` preserves that order at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp:6604-6641`. Ordering candidates by shared-pointer ownership is not a stable cross-process frontier, so the same wall-clock budget does not imply that the next process would measure the same prefix.

Persist a search-policy/version identifier, candidate mode and limit, workspace limit, and the measurement settings that determine whether an old result is final. Sort exhaustive candidates by a stable property such as solution index and record the frontier reached, or provide explicit force-retune semantics instead of inferring equivalence from elapsed-time budget alone.

### Do not repeat a costly failed search without reporting it

Only `SkippedBudget`, `FallbackNoWinner`, and `TunedPartial` enter the process-lifetime attempt set at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp:5223-5238`. `FallbackSetup`, `FallbackEnumeration`, and `FallbackException` can occur after the start message and after expensive setup or candidate work, but the next matmul retries them. At the default logging level, `shouldLogTuningStart()` and `shouldLogTuningTerminal()` suppress the second start and failure at `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/UserDrivenTuningParser.cpp:419-454`. The application can therefore pause for the same failed search repeatedly with no further explanation. This also contradicts the statement at `projects/hipblaslt/docs/how-to/how-to-use-hipblaslt-offline-tuning.rst:230-234` that a shape is benchmarked at most once per process.

Either latch every attempt that progressed past `tuning-start`, or keep a bounded retry policy and emit a lifecycle pair for every retry that can block. Add failure-injection tests for setup, enumeration, and an exception after at least one candidate has run.

### Run feature-enabled tests in automated checks and prove which index launches

`projects/hipblaslt/CMakeLists.txt:70-76,400-404` defaults the implementation off, and `projects/hipblaslt/clients/tests/src/CMakeLists.txt:24-31` omits the entire test source in that configuration. No repository workflow enables the option. Consequently, the current required checks can pass without compiling most of the added runtime code or any of the 34 `TuningCache` cases. The failing coverage report—6.61% patch coverage, including 403 uncovered lines in `UserDrivenTuningParser.cpp`—is consistent with that gap.

Add a feature-enabled automated lane before treating the feature as tested. Put parser, row-ordering, policy, and privileged-environment behavior in a host-only target that runs in ordinary builds; reserve device tests for tuning and dispatch. The GPU cases must cover query-once algorithm reuse, `algo == nullptr`, scalar/C-D-alias/E-stride/uniform-summation key pairs, truncated value rows, concurrent calls, and injected failures. At least one test must observe the index that reaches dispatch, because correctness plus the current counters does not prove cache replay.

## Suggestions

### Keep test controls out of the installed library

`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp:3179-3245` exports three functions that reset global cache state and expose counters solely for `tuning_cache_test.cpp`. `projects/hipblaslt/CMakeLists.txt:400-404` also propagates the internal feature macro as a `PUBLIC` usage requirement even though only the library and the conditionally added test source need this configuration. Move the pure cache/store code into an internal host-testable target, or compile reset hooks only in a test build, so a production library does not expose process-wide mutation entry points as ABI.

### Use the required header on the new test source

`projects/hipblaslt/clients/tests/src/tuning_cache_test.cpp:1-6` is the only new file and uses a banner-style copyright block. Replace it with the component's required two-line SPDX header.

## Commentary

The appropriate validation level is a combination of host-only unit tests for parsing and cache-state transitions, then feature-enabled GPU integration tests for candidate measurement and the selected dispatch index. A default-off flag is a reasonable temporary guard while the feature is being developed, but it is not a substitute for compiling that guarded code in an automated lane. No waiver is documented for the current coverage gap.

The current PR description also fails the repository template and is stale: it says 18 `TuningCache` tests while the source defines 34, calls the key complete despite documented omissions, and presents green checks without explaining that the feature is compiled out. A concrete replacement follows.

## Suggested replacement PR description

```markdown
JIRA ID : AIHPBLAS-3751

## Motivation

hipBLASLt selects a GPU kernel for each matrix-multiplication problem. The existing offline tuning workflow can override that choice with a numeric solution index, but users must run `hipblaslt-bench`, manage the file themselves, and regenerate entries when indexes change between library builds.

This change adds an experimental, opt-in cache that can benchmark a problem on its first execution and save the selected kernel for later heuristic queries. It also adds per-row identity checks so a saved index is accepted only when it still resolves to the recorded kernel name.

## Technical Details

The feature is compiled only with `-DHIPBLASLT_ENABLE_TUNING_CACHE=ON`; the option currently defaults to `OFF`. A feature-enabled build recognizes `HIPBLASLT_TUNING_MODE=off|cache|tune` and `HIPBLASLT_TUNING_CACHE_PATH=<file>`. `tune` measures either all supported candidates or a configured ranked prefix on library-owned scratch, appends the fastest measured candidate, and marks a budget-limited search as incomplete. `cache` reads and validates saved rows but does not benchmark or write.

Each managed row contains a schema version, a widened problem key, device architecture and compute-unit count, solution index, kernel name, workspace requirement, measured time, and partial-search metadata. The parser retains compatibility with older `HIPBLASLT_TUNING_OVERRIDE_FILE` rows. This PR also repairs six existing override-path errors involving unlocked iterators, repeated vector contents, solution index 0, repeated empty-file parsing, uninitialized result counts, and null solution-name lookup.

Current limitations are part of the interface being reviewed: online tuning is limited to the C execution path and excludes grouped GEMM, pointer-array batches, RocRoller, graph capture, and in-place nonzero-beta problems. Cache lookup cannot represent alpha, beta, or C/D aliasing. An `algo == nullptr` execution does not use an existing cached winner. The cache is append-only and supports one writer process per file. Runtime measurement and `hipblaslt-bench` use separate implementations and can select different winners.

## Test Plan

- Build hipBLASLt with the feature both disabled and enabled on Linux and Windows.
- Run host-only parser and cache-state tests for strict schema validation, row precedence, partial-search policy, build changes, and privileged-process environment suppression.
- Run feature-enabled GPU tests on each supported architecture for tune/write/load/use, query-once algorithm reuse, `algo == nullptr`, scalar and layout key variants, invalid entries, allocation and launch failures, and concurrent calls.
- Run the existing hipBLASLt smoke and standard client suites with the feature disabled to detect regressions in normal dispatch and the legacy override file.

## Test Result

The pull-request discussion reports 34 feature-specific `TuningCache` cases and 3,108 smoke cases passing in manual runs. The current required automated checks pass, but their builds leave `HIPBLASLT_ENABLE_TUNING_CACHE=OFF` and therefore do not compile or run the feature-specific test source. The hipBLASLt coverage check fails with 6.61% patch coverage and 791 changed lines uncovered. Feature-enabled automated coverage remains pending.

## Submission Checklist

- [ ] Look over the contributing guidelines at https://github.com/ROCm/TheRock/blob/main/GOVERNANCE.md#pull-requests.

## Risk level

High (4/5): the change adds a persistent file format and a new multi-minute benchmarking path inside `hipblasLtMatmul`, affects kernel selection, and currently lacks feature-enabled automated coverage. The build option defaults off, which limits exposure in standard packages but also leaves the new path unvalidated by the required checks.
```

## Appendix: completed-row ordering probe

Compile this against the feature-enabled PR host build with the same include paths used by the `hipblaslt` target:

```cpp
#include "UserDrivenTuningParser.hpp"

#include <iostream>

int main()
{
    using namespace TensileLite;

    auto& map = OverrideMap::getMap();
    map.resetForTest();

    ProblemOverride key;

    TunedEntry partial;
    partial.solutionIndex = 11;
    partial.kernelName = "partial";
    partial.complete = false;
    partial.budgetMs = 1000;

    TunedEntry complete;
    complete.solutionIndex = 22;
    complete.kernelName = "complete";
    complete.complete = true;
    complete.budgetMs = 0;

    map.add(key, partial);
    map.add(key, complete);

    const auto entries = map.find(key);
    std::cout << "replay_first=" << entries.at(0).solutionIndex << '\n';
    std::cout << "needs_finishing=" << map.needsFinishing(key, 0) << '\n';
    return entries.at(0).solutionIndex == 11 && !map.needsFinishing(key, 0) ? 0 : 1;
}
```

Observed output:

```text
replay_first=11
needs_finishing=0
```
