This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13568](https://github.com/ROCm/rocm-libraries/pull/13568)

Reviewed head: [1767aa28170](https://github.com/ROCm/rocm-libraries/commit/1767aa28170fe34d860806417db901711eabd977). Comparison base: [fbe2cd0a51b](https://github.com/ROCm/rocm-libraries/commit/fbe2cd0a51ba6c987582f2019e060121e097b0f8). The PR, repository, and reviewed branch are public. This review includes the earlier review comments and dependent PRs, as requested.

Suggestion branch: [review/pr13568-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr13568-suggestions), based on that exact head. The [complete suggestion diff](https://github.com/newling/rocm-libraries/compare/1767aa28170fe34d860806417db901711eabd977...11a6fa196ef598e34064e5fa406e9fc497fc5b02) contains the two commits below.

| Fix commit | Review item |
| --- | --- |
| [f41d274f0a9](https://github.com/newling/rocm-libraries/commit/f41d274f0a9d99700cfb940b1a17408c53803eaf) | Stop the search after a fatal cold-launch failure. |
| [11a6fa196ef](https://github.com/newling/rocm-libraries/commit/11a6fa196ef598e34064e5fa406e9fc497fc5b02) | Keep each translation unit's benchmark hooks separate in static builds. |

The second commit follows the first because both extend the same regression-test file; the fixes address separate behaviors.

## Tests

Submitted host library, benchmark, and test builds pass; the submitted focused suites pass, both added regressions fail before their fixes and pass afterward, and the suggestion branch passes the focused helper/statistics/collective suites and dependent search-helper tests.

Before/after GPU runs used gfx1201, a matching reduced fp16 device library, 256³ matrices, three candidates, rotation, and numerical verification. The C, C++, mixed, pointer-array, GPU-timer, skip-screen, and C-with-flush runs have identical dispatch sequences and geometry after sorting the trace by dispatch ID, allowing the intentional flush-kernel rename. The flush case includes all 200,000 calibration launches. Adaptive timing also executes and verifies on both versions. Candidate output fields match after excluding measured times, rates, and adaptive sample counts; problem settings and numerical-error fields remain in the comparison. These short runs do not establish performance equivalence or identical winners under timing noise. The skip-screen run did not establish an actual skipped GPU candidate; the direct helper test exercises that boundary.

Both benchmark binaries used the same runtime and device library. The baseline compiled the submitted, unchanged `client.cpp` against all client headers from the comparison base. This isolates the moved benchmark code. Grouped and grouped-user-argument runs reported `NO solution found!`, including with all-solution enumeration, so they did not exercise measurement. Those paths were inspected in source. Full runtime-tuning builds and GPU tests for #12588/#12589 were not run locally; their changed helper tests were compiled and run with the proposed fixes.

Linux/Windows component builds and GPU tests and the Math preliminary/pre-checkin lanes pass. Automation is not wholly green: the [gfx90a AddressSanitizer job](https://github.com/ROCm/rocm-libraries/actions/runs/38463494133/job/115555654468) times out after 20 minutes, before the main test binary prints its test banner; it supplies no sanitizer diagnostic. Coverage checks fail, FFM gfx1250 requires action, and Math static analysis remains pending. The timeout is unresolved and has not been attributed to this extraction. Root hooks have no applicable checks for these files; formatting passes on the suggested changes. A whole-file scan still reports existing formatting violations in the larger client files, also present on the comparison base.

## Summary

This PR makes the benchmark's timing engine and candidate comparison callable from library code without introducing a dependency on the clients. It moves statistics, collective helpers, instruction-cache flushing and calibration, and the candidate loop into a private, uninstalled header target. Each benchmark launch path supplies its own preparation and launch callbacks; validation and result printing remain in the client.

The extraction provides substantial reuse. The moved measurement engine is token-identical after restoring the original hook names and relocated diagnostic. The successful launch paths preserve their rotation indexes, scalar pointers, initial result copies, timed launches, and reporting. The source retains the existing grouped-GEMM flush behavior as well. The remaining difference from the original reuse request is described below.

## Actionable items

### Stop the search after a fatal cold-launch failure

At [`candidate_search.hpp:200`](https://github.com/ROCm/rocm-libraries/blob/1767aa28170fe34d860806417db901711eabd977/projects/hipblaslt/library/src/benchmark/hipblaslt_benchmark/candidate_search.hpp#L200), the cold loop calls the callback without checking for a new fatal failure afterward. Before extraction, cold-launch `CHECK_HIPBLASLT_ERROR` and `EXPECT_HIPBLAS_STATUS` failures under Google Test returned from `testing_matmul_with_bias`. They now return from the callback, allowing the remaining cold launches, measurement, and later candidates to run. The existing abort check protects preparation but misses this boundary.

Check for a newly raised failure after each cold callback, set `SearchResult.aborted`, and return immediately. The client already returns when that field is set. Commit [f41d274f0a9](https://github.com/newling/rocm-libraries/commit/f41d274f0a9d99700cfb940b1a17408c53803eaf) implements this and adds `CandidateSearch_pre_checkin.AFailureDuringAColdLaunchEndsTheSearch`. With three requested cold launches, the regression expects only preparation and the first cold callback. The submitted helper continues through the rest of the search; the fix stops at that callback.

### Keep consumer-specific hooks out of externally linked inline bodies

At [`benchmark_timing.hpp:18`](https://github.com/ROCm/rocm-libraries/blob/1767aa28170fe34d860806417db901711eabd977/projects/hipblaslt/library/src/benchmark/hipblaslt_benchmark/benchmark_timing.hpp#L18) and [`candidate_search.hpp:68`](https://github.com/ROCm/rocm-libraries/blob/1767aa28170fe34d860806417db901711eabd977/projects/hipblaslt/library/src/benchmark/hipblaslt_benchmark/candidate_search.hpp#L68), consumer-defined macros change externally linked inline function bodies. The clients use `CHECK_HIP_ERROR` and their CPU timer; #12588 supplies a different hook that sets its runtime measurement-failure flag. A static library and its client put these definitions into one executable, violating C++'s requirement that such definitions agree. The linker can retain either body, routing a timer failure through the wrong consumer's policy.

This matters for the supported `HIPBLASLT_BUILD_SHARED_LIBS=OFF` configuration. The default shared library's hidden visibility separates the consumers, so ordinary shared builds do not demonstrate the collision. A two-consumer probe with hidden visibility reports two library failures and zero client failures in one link order, then the reverse in the other.

Give hook-dependent functions internal linkage, or pass hook policies explicitly as types/arguments. Commit [11a6fa196ef](https://github.com/newling/rocm-libraries/commit/11a6fa196ef598e34064e5fa406e9fc497fc5b02) uses internal linkage throughout the affected call chain while preserving shared flush-cache storage in a macro-independent helper. It adds separate library/client test translation units and `CandidateSearch_pre_checkin.SeparateTranslationUnitsKeepTheirOwnHooks`. The test takes a volatile function pointer so optimized inlining cannot hide the collision. It fails against the submitted headers at `-O3` and passes with the fix, retaining one call to each consumer's hook.

## Suggestions

No additional bounded implementation is proposed. The remaining search-policy work needs a decision about which caller differences are intentional.

## Commentary

The current stack is visible, and its reuse is real:

| PR | Current role and state |
| --- | --- |
| [#12585](https://github.com/ROCm/rocm-libraries/pull/12585) | Override validation; merged October 1. |
| [#12586](https://github.com/ROCm/rocm-libraries/pull/12586) | Versioned tuning store; merged October 8. |
| [#12587](https://github.com/ROCm/rocm-libraries/pull/12587) | Cache replay; merged October 13. |
| [#13568](https://github.com/ROCm/rocm-libraries/pull/13568) | Shared measurement and candidate comparison; this review. |
| [#12588](https://github.com/ROCm/rocm-libraries/pull/12588) | Runtime tuning; open at `715e53880ba`, containing this PR's exact head. |
| [#12589](https://github.com/ROCm/rocm-libraries/pull/12589) | Partial-search persistence/revisit policy; open at `8fa50372211`, containing current #12588. |
| [#12590](https://github.com/ROCm/rocm-libraries/pull/12590) | Bench-through-tune-mode approach; closed unmerged and explicitly replaced by #13568. |

#12588 calls `search_candidates` and extends it with preparation/measurement vetoes and a stop check between candidates. It also uses the shared rotation planner. #12589 inherits this path. The old independent runtime measurement loop has been replaced in these heads; this extraction is already consumed downstream.

The [original reuse request](https://github.com/ROCm/rocm-libraries/pull/10424#pullrequestreview-5271755706) included candidate enumeration as well as benchmarking. #13568 leaves the existing benchmark enumeration unchanged; its 896-line candidate-construction region is byte-identical to the comparison base. The separate runtime enumeration is introduced by #12588, so that remaining duplication belongs to review of #12588 rather than being an additional issue for #13568.

The benchmark constructs algorithms and C++ split-K/workgroup-mapping combinations before calling the shared helper. #12588's runtime separately chooses all solutions or a ranked prefix, moves the baseline first, resolves candidates through replay's lookup, and checks support against owned scratch. Both use existing library discovery routines, but the search-level policy remains separate.

The common helper therefore completes measurement and comparison reuse. Candidate-policy reuse remains a follow-up for #12588 against the original request. Establish the common ordering, limits, support filtering, and execution-setting policy there, then share those decisions where applicable while retaining caller-specific buffer ownership and launch adapters. This is outside #13568's two bounded fixes and is not implemented on the suggestion branch.

The current callers also use different settings: ordinary bench defaults to CPU timing, while runtime tuning uses HIP events; runtime tuning selects fixed iteration counts and its own rotation/flush defaults. Shared implementation alone does not guarantee the same winner for different candidates, launch overhead, settings, data, or GPU interference. Claims of equivalent searches need an explicit common policy and a comparison that holds those inputs constant. This review verifies the current stack's ancestry and helper use, without certifying the full runtime tuner or its persistence policies.
