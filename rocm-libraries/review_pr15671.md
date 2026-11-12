This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15671](https://github.com/ROCm/rocm-libraries/pull/15671)

Reviewed head: `d2a09c984a9c4e2d438d92c0906d26d3706f1d29`, against merge base `b4eb007c2c2c4a2e7617e2215a5e9026cd0bafc9`. Independent review considering the complete existing review threads and author updates. Scope: predicate generation and serialization, scale-layout validation, cache identity, and checkout/installed tests. The companion's API changes are reviewed [separately](review_pr15672.md).

[Suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr15671-recheck), based on and still at the reviewed head. No fix commits are needed; the author has implemented the earlier actionable suggestions.

## Tests

All 28 focused Python cases pass without the tuning corpus. Copying the tests with `source_only` excluded leaves 27 passing cases without the C++ headers. The rebuilt TensileLite host library passes all four C++ predicate/cache cases. The TensileLite sources and predicate test used in the combined stack build are identical to this PR's reviewed head.

The copied-test check uses the existing Python runtime, not a complete installed product. No numerical GPU execution or full unit-suite run was performed. The applicable root hooks and whitespace checks pass; most root formatting hooks exclude these paths. The CI snapshot has no failed checks, with jobs still queued or running.

## Summary

This PR adds scale format 3 (`HostPreSwizzle128x4`) and the predicates needed to select a kernel that requires that layout and alpha equal to 1. The format and alpha restriction participate in problem comparison and hashing, so cached selections respect both constraints. Format 3 is limited to handwritten gfx950 kernels because generated kernels have no corresponding load path. Nothing in this PR selects format 3 for a caller or adds a consuming kernel.

The installed-test finding is fixed. The header-reading parity test now lives in `Tests/unit/source_only/test_mx_scale_format_ids_cpp.py`, with its path adjusted for the extra directory. The existing install rule excludes that directory while retaining the Python behavior tests. Both checkout and copied-test execution confirm the intended separation.

The author also adopted the requested name `MXScaleFormatEquals`. Python predicate emission, C++ registration and mapping traits, the predicate's serialized type, and the behavioral tests agree on the new name. The enum and solution parameter retain `MXScaleFormat`. This is a naming change; formats 0–2 still match each other, and format 3 requires an exact match. Host and serialized solution libraries must still be rebuilt together.

## Actionable items

None. The [source-header dependency finding](https://github.com/ROCm/rocm-libraries/pull/15671#discussion_r4556522800) is resolved. The earlier pre-derived-state validation, corpus-independent fixtures, and alpha-restriction cache fixes remain present.

## Suggestions

None.

## Scope decisions

The integer payload continues to match the serialized format IDs. Restricting `AssertAlphaValue` to 1 remains consistent with the consuming kernels in this stack; the existing discussion does not establish a need for additional values.

[HostNumerics #15181](https://github.com/ROCm/rocm-libraries/pull/15181) supplies layout descriptions and host copies. It does not replace this PR's runtime matching or cache identity. The concrete scale-shuffle reuse recommendation remains in the [companion review](review_pr15672.md#reuse-the-hostnumerics-scale-layout-machinery).

The suggestion branch contains no changes beyond the reviewed head. All earlier actionable items are resolved within this review's host-side scope.
