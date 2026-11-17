This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15957](https://github.com/ROCm/rocm-libraries/pull/15957)

**Reviewed head:** `983ec8196de2be42c1cc55a014e578481c7f8cc2`. **Comparison base:** `de6d67095491a77bbea99799a0b2ec740093cd91` (#15956).

**Scope:** Independent review of matching-table storage, serialization compatibility, and source-build dependencies. Existing PR reviews, inline threads, and discussion were not used. The [stack review](review_pr15954_stack.md) covers combined behavior and shared alternatives.

## Tests

The matching-table tests pass on the submitted stack, including numeric-type preservation, fallback for values that cannot be represented exactly, stable ordering, merging, and pickling. Together with the examined consumers, 324 focused tests passed. A four-file gfx942 build produced all 11 files byte-identical to the baseline.

Earlier submitted-head CI builds failed on the NumPy import described below. The matching-table and import code is unchanged at this reviewed head; the refreshed gfx942 host-ASAN job was still queued when checked. The small local build used an environment with NumPy installed.

## Summary

A matching table records problem-size keys, selected solutions, and sometimes measured speeds. The parent retains these tables throughout generation. Replacing millions of Python dictionaries with numeric columns is a well-motivated representation change.

The implementation preserves details that matter to the serialized library: solution references follow reindexing, duplicate-key ordering stays stable, and integer speeds such as `0` keep their distinction from floating-point values. Values that cannot be stored exactly retain the legacy representation.

## Actionable items

### Provision NumPy in the interpreter that runs source builds

**Location:** [the unconditional NumPy import](https://github.com/ROCm/rocm-libraries/blob/983ec8196de2be42c1cc55a014e578481c7f8cc2/projects/hipblaslt/tensilelite/tensilelite/MatchingTable.py#L25) and [the new import from SolutionLibrary](https://github.com/ROCm/rocm-libraries/blob/983ec8196de2be42c1cc55a014e578481c7f8cc2/projects/hipblaslt/tensilelite/tensilelite/SolutionLibrary.py#L34).

The source-build logic-validation command now imports `logic.run → LibraryIO → SolutionLibrary → MatchingTable → numpy` before generation. The TheRock build interpreter in the observed jobs did not have NumPy, and the build failed with `ModuleNotFoundError: No module named 'numpy'`.

This is recorded in [the gfx942 build for #15957](https://github.com/ROCm/rocm-libraries/actions/runs/43773971951/job/132995940391) and [the gfx950 build for #15958](https://github.com/ROCm/rocm-libraries/actions/runs/43773976456/job/132995958450). The failing invocation was `python -m tensilelite logic <library-source> --architecture gfx942 --use-bundled-known-bugs --check-all`.

Install NumPy in the actual interpreter used by those source-build commands, including the consuming TheRock environment, or choose a representation that does not require it. TensileLite already lists NumPy in `requirements.txt`; adding it there again will not fix builds that import the source through `PYTHONPATH`. Delaying the import would only postpone the dependency failure until table construction.

**Disposition:** No dependency patch was selected. Provisioning the consuming build environment and choosing a dependency-free representation are different integration decisions. The demonstrated build failure needs resolution in that integration, rather than a duplicate package declaration.

## Suggestions

### Construct columns directly and avoid sorting twice

**Location:** [conversion after row construction](https://github.com/ROCm/rocm-libraries/blob/983ec8196de2be42c1cc55a014e578481c7f8cc2/projects/hipblaslt/tensilelite/tensilelite/SolutionLibrary.py#L159), [fromRows()](https://github.com/ROCm/rocm-libraries/blob/983ec8196de2be42c1cc55a014e578481c7f8cc2/projects/hipblaslt/tensilelite/tensilelite/MatchingTable.py#L51), and [state()](https://github.com/ROCm/rocm-libraries/blob/983ec8196de2be42c1cc55a014e578481c7f8cc2/projects/hipblaslt/tensilelite/tensilelite/MatchingTable.py#L187).

The loader still constructs and sorts the old dictionaries before converting and sorting the columns. Serialization later expands all rows back into dictionaries. Direct column construction would remove duplicated allocation and sorting work while retaining the legacy fallback. Streaming serialization is a further option if measurements show that expansion determines the peak.

### Provide an isolated before/after memory measurement

The description estimates several hundred bytes per row becoming under 50, across about 42 million gfx942 rows. It supplies no isolated build measurement. Compare #15956 with this PR, recording retained table memory, parent peak, total peak, and elapsed time, including conversion and serialization temporaries.

PR 5 reports the parent's peak falling from 36.0 to 15.0 GiB for the entire stack. That number cannot be attributed solely to these tables.

## Scope decisions

Column storage does not conceptually require compressed solutions. A standard-library array representation could avoid activating NumPy, but would need its own ordering and performance evaluation; it was not implemented here.

**Handoff:** There are no suggestion commits for this PR. Dependency provisioning and isolated memory evidence remain unresolved; local validation does not replace the failing source-build environment.
