This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15480](https://github.com/ROCm/rocm-libraries/pull/15480)

**Reviewed:** 2026-11-12, head `747326d1985356fb6751f21fbcd1174492712d53`.

**Diff base:** `d462573cb8e3539fc3730d9a8c43f9d3a462e9de`, the prerequisite in [#15672](https://github.com/ROCm/rocm-libraries/pull/15672).

**Mode and scope:** Follow-up review incorporating existing reviews and author replies. Focus: numerical-test design, kernel selection and algorithm reuse, and actual CI selection. Earlier assembly and registration checks are retained where the sources are unchanged; this follow-up does not claim a fresh instruction-by-instruction assembly or synchronization audit.

**Suggestion branch:** [review/pr15480-followup-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15480-followup-suggestions), based on the reviewed head. Commits [c955b465e1a](https://github.com/newling/rocm-libraries/commit/c955b465e1aab54969da19a3c982b40862a68774) and [33a4f3f365b](https://github.com/newling/rocm-libraries/commit/33a4f3f365bd6b114db28b91c527a4c2b4ed0546) implement suggestion 1. [Compare the reviewed head with the suggestions](https://github.com/newling/rocm-libraries/compare/747326d1985356fb6751f21fbcd1174492712d53...33a4f3f365bd6b114db28b91c527a4c2b4ed0546). The numerical-test redesign in actionable item 1 remains unimplemented.

## Tests

The current suggestion branch builds `hipblaslt-test` and `tensilelite-tests` with ROCm 7.1. The focused Python run passes 410 tests, including all nine selected logic-corpus cases with zero skips. The client run passes 52 API/layout checks; 28 cases skip on the available gfx1201 hardware, including all 14 MXFP6 GPU cases added here. The latest prerequisite deliberately adds architecture skips for valid C-API cases that reach kernel selection. Root pre-commit hooks and the complete own-PR whitespace check pass; root formatting hooks exclude hipBLASLt. The optional cleanup retains the previously checked formatting changes.

Earlier checks assembled all five kernels for gfx950, passed strict metadata validation, and passed 96 native scale-layout/predicate tests. The relevant sources are unchanged. Since the previously tested submitted head `b8de8dd093e`, the sole source change is the prerequisite's API-test adjustment; the kernels, registrations, numerical fixture, and YAML cases are unchanged.

No gfx950 numerical execution or performance measurement was independently performed. The author reports MI355X numerical and mutation results in the PR; these remain separate evidence. At the current-head CI snapshot, the logic-corpus job passed and GPU work was pending. Test selection below is not a claim that those GPU cases have completed successfully.

## Summary

This adds five fixed-shape MXFP6 GEMM kernels for M = N = 4096: E2M3 and E3M2 at K = 65536 and 131584 with tiled B, plus E2M3 at K = 65536 with plain packed B. The prerequisite PRs provide the scale-format predicates, layouts, API validation, and launch-time eligibility checks. This PR supplies the kernels, registrations, and workload tests.

Exact size, stride, layout, and scalar predicates are essential because the assembly performs no buffer-bounds checks. The added selection and explicit-algorithm-reuse tests protect that boundary and should survive any numerical-test simplification. No kernel or dispatch defect was demonstrated by the completed checks. The outstanding design request concerns the amount of custom numerical-test machinery.

## Actionable items

### 1. Simplify the custom numerical test

**Location:** [row_uniformity_gtest.cpp:1236](https://github.com/ROCm/rocm-libraries/blob/747326d1985356fb6751f21fbcd1174492712d53/projects/hipblaslt/clients/tests/src/row_uniformity_gtest.cpp#L1236), its [BF16 reference helper](https://github.com/ROCm/rocm-libraries/blob/747326d1985356fb6751f21fbcd1174492712d53/projects/hipblaslt/clients/tests/src/row_uniformity_gtest.cpp#L1209), and the existing [full-reference GEMM cases](https://github.com/ROCm/rocm-libraries/blob/747326d1985356fb6751f21fbcd1174492712d53/projects/hipblaslt/clients/tests/data/matmul_gtest.yaml#L3156).

The fixture combines two responsibilities. Its cancellation-sensitive first run checks the advertised uniform-summation property: equal logical rows must produce bitwise equal output rows, despite different equivalent FP6/scale encodings. That is distinct coverage worth preserving. Its second run lowers the scales and implements a separate exact integer reference and BF16 rounding path, checking eight columns at eight rows. Those assertions are exact at the sampled positions; they do not validate every output numerically.

The file gains 835 lines, roughly 500 of which implement the numerical fixture and helpers. The remainder largely serves the separate selection/reuse tests. The numerical portion carries its own packing, input generation, allocation/launch setup, exactness bounds, and reference calculation while full-reference GEMM tests already coexist with it. The [reported whole-test timings](https://github.com/ROCm/rocm-libraries/pull/15480#issuecomment-6837009208) are about 5–6 seconds versus 1 second at K = 65536, and 11–14 seconds versus 2–3 seconds at K = 131584. Those savings alone do not establish that another numerical-validation mechanism is worth maintaining.

Please consolidate numerical correctness coverage around the existing GEMM test path and reduce this fixture to the distinct uniformity check. Start by reassessing the second sampled-reference run and its custom oracle, then remove setup duplication where existing helpers fit. Retain all five workload cases, required-solution checks, and selection/reuse regressions. This does not call for a new generic testing framework.

Two constraints need an explicit disposition before deleting coverage. First, the [long-K E3M2 YAML case](https://github.com/ROCm/rocm-libraries/blob/747326d1985356fb6751f21fbcd1174492712d53/projects/hipblaslt/clients/tests/data/matmul_gtest.yaml#L3221) uses `trig_float` with only a norm check; the standard integer fill at that K can exceed FP32's exact integer range. It is not a drop-in replacement for the sampled exact assertions. Preserve any required exactness guarantee through suitable input/reference coverage, or explain why the norm check suffices. Second, full-reference cases currently run in higher tiers, so removing the sampled run also changes what quick CI verifies. Choose the tier coverage together with the simplification.

**Implementation:** No numerical-test rewrite is included. This requires settling those validation guarantees and checking the replacement on gfx950. Removing the second run alone would leave much of the setup, and the existing row-uniformity harness does not already support FP6/scales or this extension-API selection path. A small mechanical deletion would not complete the requested simplification.

## Suggestions

### 1. Make test dependencies explicit and tidy the touched code

**Location:** [row_uniformity_gtest.cpp:54](https://github.com/ROCm/rocm-libraries/blob/747326d1985356fb6751f21fbcd1174492712d53/projects/hipblaslt/clients/tests/src/row_uniformity_gtest.cpp#L54) and [api-reference.rst:221](https://github.com/ROCm/rocm-libraries/blob/747326d1985356fb6751f21fbcd1174492712d53/projects/hipblaslt/docs/reference/api-reference.rst#L221).

Commit [c955b465e1a](https://github.com/newling/rocm-libraries/commit/c955b465e1aab54969da19a3c982b40862a68774) adds the direct `<cstddef>` and `<ios>` dependencies, qualifies `std::ptrdiff_t`, and formats touched test code. Commit [33a4f3f365b](https://github.com/newling/rocm-libraries/commit/33a4f3f365bd6b114db28b91c527a4c2b4ed0546) formats the later test additions and spells out “batch count” where the documentation's `B` could be read as the matrix operand. These are optional maintenance changes; they do not alter kernel behavior or test coverage.

## Scope decisions

**Existing review requests.** The original broad change has been split into this kernel PR and prerequisites [#15671](https://github.com/ROCm/rocm-libraries/pull/15671) and [#15672](https://github.com/ROCm/rocm-libraries/pull/15672). The prerequisite now rechecks handwritten-kernel predicates for explicit algorithms, and this PR tests wrong K and alpha through both C and extension APIs while checking that D remains unwritten. Required-solution checks name both `0x75a0` and `0x75a3`, and negative selection cases are committed. Format-ID parity, public argument validation, and the leading-dimension contract are addressed in the prerequisites. `GroupedGemm: false` excludes the device UserArgs path despite the general ProblemType default. These earlier requests are not repeated as unresolved findings.

**Chip coverage.** MI350X and MI355X now have matching registrations, retiring the earlier MI355X-only CI concern. Other gfx950 chips may reach the MI350X entries through the existing device fallback, as the current description explains; the new GPU tests explicitly require one of the two named chip IDs. Independent execution evidence remains limited as stated above.

**CI tiers.** The [hipBLASLt presubmit override](https://github.com/ROCm/rocm-libraries/blob/747326d1985356fb6751f21fbcd1174492712d53/.github/workflows/therock-multi-arch-ci.yml#L156) selects quick for gfx950. The tiers are cumulative:

| Tier | Additional coverage from this PR |
| --- | --- |
| Quick | Two E2M3 K = 65536 numerical/uniformity cases, one per B order |
| Standard | The other three kernel cases, selection/reuse tests, and three K = 65536 full-reference cases |
| Comprehensive | The two K = 131584 full-reference cases |

Consequently, quick exercises two of the five distinct kernels. The dedicated HOST_ASAN nightly selects standard; it does not include the two nightly-category full-reference cases. The inspected [main nightly gfx950 matrix](https://github.com/ROCm/rocm-libraries/actions/runs/43172998162/job/131070857285) excluded hipBLASLt because no GPU runner was configured for that trigger. Scheduled runs also test develop rather than an unmerged PR. These are current lane limitations: full premerge coverage needs an explicitly selected suitable lane, and the nightly trigger configuration is a separate CI follow-up. This review does not require provisioning MI355X hardware when MI350X can execute the registered kernels.

**Fixed-shape scope.** The author's explanation of a bounded set of workload-specific releases is consistent with this change. Runtime dimensions or JIT compilation would require a separate design; neither is requested here.

The suggestion branch contains only the two optional cleanup commits mapped above. Numerical-test simplification and CI-tier changes remain open; no new gfx950 execution evidence is claimed.
