This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15672](https://github.com/ROCm/rocm-libraries/pull/15672)

Reviewed head: `d724b2b975c9253bde4847d72cc288e545e5fb68`, against base `98a705600c1bc005f2b9e9b3ae2574afb5d5d53c` from #15671. Independent review considering all existing threads and the author's follow-ups. Scope: descriptors, FP6 validation across C and extension APIs, scale-format dispatch, client packing, and tests. The prerequisite predicates and installed-test issue are reviewed separately in [#15671](review_pr15671.md).

[Suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr15672-final-suggestions), based on the reviewed head: [cc936c53fa7](https://github.com/newling/rocm-libraries/commit/cc936c53fa7fdd2127e733e96292e730d8b76e3c) supplies the optional direct-include cleanup below. Earlier local validation fixes against `fdf330811bb` have been superseded by the author's changes.

## Tests

The current host library rebuilt with ROCm 7.1. All 64 focused public API checks passed: the 54 newly committed argument cases and ten review regression cases covering descriptor round trips, both FP6 types, and descriptor/dimension overloads of single and grouped calls. The latter also put an invalid shape second in a group. The only suggestion-branch change adds explicit test includes; the same executable validates that final source.

The test sources were compiled into a standalone gtest executable against the rebuilt library. Tests initialized HIP on gfx1201 and used a complete empty solution library to exercise validation and valid no-solution behavior. No numerical GPU kernels were launched, and the full client executable was not built. The final CI snapshot has no failed checks, with several checks still queued or running. Whitespace checks pass; root formatting hooks exclude these C++ paths.

Earlier validation of the unchanged packing/generator code passed all 21 layout and format cases and the FP6 generator probe. The MX data-generator suite had 34 passes, one existing skip, and an FP4 zero-frequency failure (13.134765625% versus a bound below 13%). Compiling the base generator reproduced that same failure. It was not attributed to this PR.

## Summary

This PR exposes the new scale mode and FP6 data order, validates their representation constraints, and prepares the corresponding client buffers. Format-3 matching from #15671 keeps kernels that expect older layouts away from these inputs. A valid configuration can return no solution until a consuming kernel is registered.

The three original review requests are addressed. The author added committed API tests and descriptor round trips, moved unsupported-FP6-order rejection into the shared validator, and passed dimensions and leading dimensions through every affected entry point. The current documentation and validation require complete tiles and `lda=ldb=K` for the new format. The review regressions pass against these changes.

## Actionable items

None in this PR's own diff. The inherited installed-test issue is recorded, with its fix, in the #15671 review.

## Suggestions

### Reuse the HostNumerics scale-layout machinery

[mx_tile128x4.hpp:94](https://github.com/ROCm/rocm-libraries/blob/d724b2b975c9253bde4847d72cc288e545e5fb68/projects/hipblaslt/clients/common/include/mx_tile128x4.hpp#L94)

Consider implementing the 128-by-4 scale shuffle through the generic descriptor and copier in [HostNumerics #15181](https://github.com/ROCm/rocm-libraries/pull/15181). For natural scales `[R,S]`, its existing API represents this mapping with natural and padded shape `[R,S]`, reshaped factors `[R/128,8,16,S/4,4]`, and axis order `[3,0,4,2,1]`. Preserve the current whole-tile restrictions: `R%128==0` and `S%4==0`.

A new `tile128x4` preset and client-adapter selection could share that implementation. The generic copier needs no change. A comparison using HostNumerics `b9cabcbc329` and this helper matched every physical index and copied byte across 16 shapes and 272,384 scales. This gives a concrete reuse path alongside the consumer migration in #10553.

This integration involves the open HostNumerics prerequisite and client dependency wiring; it has not been implemented on the suggestion branch. The FP6 data transform also splits each packed 24-byte group into 16-byte and 8-byte planes, so the scale-copy comparison does not establish a generic replacement for that whole transform.

### Include the API test's direct dependencies

[fp6_tile128x4_args_gtest.cpp:9](https://github.com/ROCm/rocm-libraries/blob/d724b2b975c9253bde4847d72cc288e545e5fb68/projects/hipblaslt/clients/tests/src/fp6_tile128x4_args_gtest.cpp#L9)

The test uses HIP runtime calls, `int64_t`, and `std::string` through transitive includes. Commit [cc936c53fa7](https://github.com/newling/rocm-libraries/commit/cc936c53fa7fdd2127e733e96292e730d8b76e3c) adds `<hip/hip_runtime.h>`, `<cstdint>`, and `<string>`. This is optional dependency hygiene; no build failure was observed before it.

## Scope decisions

The original [API coverage](https://github.com/ROCm/rocm-libraries/pull/15672#discussion_r4555241068), [unsupported-order](https://github.com/ROCm/rocm-libraries/pull/15672#discussion_r4555241075), and [tile-dimension](https://github.com/ROCm/rocm-libraries/pull/15672#discussion_r4555241082) requests are addressed in the reviewed head. They are not outstanding recommendations to cherry-pick from the earlier local branch.

The new representation has separate host-copy and runtime-selection responsibilities: HostNumerics can supply the scale transformation, while #15671 retains kernel matching and cache identity. Neither PR adds a consuming GPU kernel, so this review makes no GEMM numerical or throughput claim. The suggestion branch contains only the include cleanup; HostNumerics integration remains the explicit design suggestion above.
