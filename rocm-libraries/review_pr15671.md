This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15671](https://github.com/ROCm/rocm-libraries/pull/15671)

Reviewed head: `98a705600c1bc005f2b9e9b3ae2574afb5d5d53c`, against merge base `b4eb007c2c2c4a2e7617e2215a5e9026cd0bafc9`. Independent review considering existing threads and the author's follow-ups. Scope: predicate generation and serialization, scale-layout validation, cache identity, and tests. API and client integration are reviewed separately in [#15672](review_pr15672.md).

[Suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr15671-final-suggestions), based on the reviewed head: [f94a1651cbc](https://github.com/newling/rocm-libraries/commit/f94a1651cbc4b098a6b380e15fc955dc0e8f0e3c) addresses the remaining installed-test issue below. Earlier local suggestions against `fa01a43c554` have been superseded by the author's fixes.

## Tests

The current submitted head passes 28 focused Python cases without the tuning corpus, and the rebuilt TensileLite host library passes all four C++ predicate/cache tests, including the new alpha-restriction case. Copying the tests without the C++ source headers reproduces one failure and 27 passes. On the suggestion branch, all 28 checkout cases pass, and the 27 cases intended for installed execution pass without those headers. The affected security hook and whitespace checks pass.

This is focused host validation. No numerical GPU execution or full unit-suite run was performed. The final CI snapshot has no failed checks, with several checks still queued or running. The earlier review's combined pool/ValidParameters run exposed an existing global-ISA test-isolation failure; isolated characterization passed, and no snapshots were changed.

## Summary

The new predicate separates scale format 3 from the existing formats while preserving their matching behavior. Format and alpha restriction now participate in problem comparison and hashing, so cached selections respect both constraints. The 128-by-4 layout remains limited to handwritten gfx950 kernels because generated kernels have no corresponding load path.

The author addressed both original requests: the constructor validates pre-derived generated states, and predicate-emission tests use checked-in fixtures. The new constructor regression and corpus-independent test run confirm these changes. One later review concern remains: the added Python/C++ identifier check assumes source headers are available in installed test artifacts.

## Actionable items

### Keep the header-reading parity check out of installed test artifacts

[test_CustomKernels_mx_scale_128x4.py:60](https://github.com/ROCm/rocm-libraries/blob/98a705600c1bc005f2b9e9b3ae2574afb5d5d53c/projects/hipblaslt/tensilelite/tensilelite/Tests/unit/test_CustomKernels_mx_scale_128x4.py#L60)

`test_scale_format_ids_match_cpp` reads `include/Tensile/MXScaleFormat.hpp` and `ContractionProblemPredicates.hpp` relative to the test file. The installed test artifact copies the Python tests without those headers. In that layout, this test fails with `FileNotFoundError`; the other 27 cases pass. This independently confirms the [existing installed-artifact finding](https://github.com/ROCm/rocm-libraries/pull/15671#discussion_r4556522800).

Commit [f94a1651cbc](https://github.com/newling/rocm-libraries/commit/f94a1651cbc4b098a6b380e15fc955dc0e8f0e3c) moves just this check into `Tests/unit/source_only/test_mx_scale_format_cpp_ids.py` and adjusts the relative header path. The existing CMake install rule already excludes `source_only`. Checkout testing retains the parity assertion; installed testing retains every Python behavior check.

## Suggestions

None.

## Scope decisions

The original [pre-derived-state request](https://github.com/ROCm/rocm-libraries/pull/15671#discussion_r4555248670) and [corpus-independence request](https://github.com/ROCm/rocm-libraries/pull/15671#discussion_r4555248676) are addressed in the reviewed head. The author's later cache fix also includes the alpha restriction in equality and hashing. Restricting `AssertAlphaValue` to 1 matches the consuming kernels in this stack; adding other values requires a concrete consumer.

The comments about an enum-typed predicate payload and a more explicit predicate class name concern interface clarity. The current integer payload matches serialized IDs, and the predicate and enum occupy distinct namespaces. I have no additional change request for those choices.

[HostNumerics #15181](https://github.com/ROCm/rocm-libraries/pull/15181) supplies layout descriptors and copies that can express the new scale shuffle. This PR still owns kernel matching and cache identity. The [companion review](review_pr15672.md#reuse-the-hostnumerics-scale-layout-machinery) recommends the concrete HostNumerics preset and client integration, with an exact byte-layout comparison.

The suggestion branch implements the remaining installed-test fix. The absence of a consuming kernel in this PR is consistent with its role in the stack; no throughput claim is assessed.
