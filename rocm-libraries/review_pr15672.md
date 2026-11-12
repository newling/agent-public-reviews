This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15672](https://github.com/ROCm/rocm-libraries/pull/15672)

Reviewed head: `1f60ba5b717ec6706c7846270696dccc8ac9c6fd`, against base `d2a09c984a9c4e2d438d92c0906d26d3706f1d29` from #15671. Independent review considering the existing reviews and author replies. Scope: descriptors, FP6 validation across C and extension APIs, scale-format dispatch, client packing, explicit algorithm reuse, and tests. The prerequisite is reviewed [separately](review_pr15671.md).

[Suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr15672-recheck), based on the reviewed head. Commit [0164234aefa](https://github.com/newling/rocm-libraries/commit/0164234aefac6713c58982bd6ce667f03ed0e9a8) carries forward the previously proposed direct test includes; [8764f13e72f](https://github.com/newling/rocm-libraries/commit/8764f13e72fae27ec296e5d5e15b550f63a3e997) fixes indentation in the MX scale dispatch block. Both are optional cleanups, not correctness fixes.

## Tests

The host library rebuilds with ROCm 7.1. The standalone API executable compiles the submitted argument tests, the earlier review regressions, and the new handwritten-algorithm tests: 64 pass and two skip. The skipped tests require the gfx950 skinny kernel; the local device is gfx1201. The optional cleanup branch rebuilds and produces the same result.

The 64 executed cases use a complete empty solution library and cover descriptor round trips, FP6 argument validation, both FP6 types, and single/grouped extension overloads, including an invalid second group member. They launch no numerical GPU kernels. The two new tests have been inspected and compiled, but their gfx950 execution and failure with the guard removed were not verified locally. No full client build or performance claim is made.

Earlier validation of the unchanged packing and generator code passed 21 layout/format cases and a varied-scale FP6 generator probe. The MX data-generator suite had 34 passes, one existing skip, and an FP4 zero-frequency failure (13.134765625% versus a bound below 13%). Compiling the base generator reproduced that failure, so it was not attributed to this PR.

Applicable root hooks pass. The complete submitted diff has four mixed-indentation warnings in the existing MX dispatch change; the optional indentation commit clears them. Most root formatting hooks exclude these paths. The CI snapshot has no failed checks, with jobs still queued or running.

## Summary

This PR exposes the 128-by-4 scale mode and tiled FP6 data order, validates their representation constraints, routes them to TensileLite, and prepares the corresponding client buffers. Complete tiles and `lda=ldb=K` are required. Format-3 matching from #15671 prevents selection of kernels that expect older scale layouts. Valid configurations can return no solution until a consuming kernel is registered.

It also revalidates a handwritten kernel's problem predicates when the caller supplies an algorithm to the C API or calls `hipblaslt_ext::Gemm::initialize`. Selection-time checks alone do not protect those paths: a caller can query an algorithm for one problem and then reuse it after changing a size or scalar. The new guard evaluates the current problem before packing and launching the selected kernel, returning `HIPBLAS_STATUS_INVALID_VALUE` on a mismatch.

The alpha cache-key fix protects cached selection, while this guard protects explicit algorithm reuse. The new tests query the existing handwritten bf16 skinny kernel for `N=1`, verify the original problem is accepted, and attempt reuse for `N=2` through both APIs. The C test also checks that the rejected operation leaves a sentinel output buffer untouched.

The previously verified descriptor, unsupported-order, and tile-dimension fixes remain present and pass the API regressions. The inherited installed-test issue is now [resolved in #15671](review_pr15671.md).

## Actionable items

None found in this PR's own diff. The inherited installed-test issue is resolved in #15671.

## Suggestions

### Reuse the HostNumerics scale-layout machinery

[mx_tile128x4.hpp:94](https://github.com/ROCm/rocm-libraries/blob/1f60ba5b717ec6706c7846270696dccc8ac9c6fd/projects/hipblaslt/clients/common/include/mx_tile128x4.hpp#L94)

Consider implementing this scale shuffle through [HostNumerics #15181](https://github.com/ROCm/rocm-libraries/pull/15181), which remains open at `b9cabcbc3290b643502cad205207d158688be6d4`. Its existing `ReshapePermutation` can express the scale shuffle with natural and padded shape `[R,S]`, reshape `[R/128,8,16,S/4,4]`, and permutation `[3,0,4,2,1]`, preserving `R%128==0` and `S%4==0`.

A comparison matched every index and byte across 16 shapes and 272,384 scales. A `tile128x4` preset plus client-adapter wiring can reuse the generic copier without changing its core. This is an integration suggestion involving an open prerequisite, so it is not implemented on the suggestion branch. The comparison covers the scale shuffle; FP6's separate 16-byte/8-byte plane split needs its own treatment.

### Include direct dependencies and normalize dispatch indentation

[fp6_tile128x4_args_gtest.cpp:9](https://github.com/ROCm/rocm-libraries/blob/1f60ba5b717ec6706c7846270696dccc8ac9c6fd/projects/hipblaslt/clients/tests/src/fp6_tile128x4_args_gtest.cpp#L9) still uses HIP runtime calls, `int64_t`, and `std::string` through transitive includes. Commit [0164234aefa](https://github.com/newling/rocm-libraries/commit/0164234aefac6713c58982bd6ce667f03ed0e9a8) adds the direct `<hip/hip_runtime.h>`, `<cstdint>`, and `<string>` includes.

[tensile_host.cpp:2836](https://github.com/ROCm/rocm-libraries/blob/1f60ba5b717ec6706c7846270696dccc8ac9c6fd/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L2836) mixes tabs and spaces in the scale dispatch block. Commit [8764f13e72f](https://github.com/newling/rocm-libraries/commit/8764f13e72fae27ec296e5d5e15b550f63a3e997) normalizes that block's indentation without changing its expressions.

## Scope decisions

The new predicate guard covers handwritten kernels in the single-GEMM C and extension initialization paths. Generated kernels and grouped launches retain their existing checks; this review does not claim that the new guard validates those paths. Grouped argument validation for the new FP6 layout remains covered by the executed API tests.

The suggestion branch contains only the two cleanups above. The material remaining validation limit is execution of the two new gfx950 tests. HostNumerics integration remains optional and unimplemented; neither PR adds a consuming FP6 GPU kernel.
