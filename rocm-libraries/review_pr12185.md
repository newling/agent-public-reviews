> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12185](https://github.com/ROCm/rocm-libraries/pull/12185)

**Reviewed head:** `a2258880cd9044c06b0005c09ff9a462830932df`

**Diff base:** `18dbfa5ea659767f749857eec2b9a857639f1084`

**Review branch:** [review/pr12185-suggestions-20261008](https://github.com/newling/rocm-libraries/tree/review/pr12185-suggestions-20261008), based directly on the reviewed head.

| Item | Fix commit |
| --- | --- |
| Read solution identities from YAML structure | [b09a4e1dbd9](https://github.com/newling/rocm-libraries/commit/b09a4e1dbd9aed89fe5ca8e74ad2ea1565b57964) |
| Forward the UID settings through tox | [92372633557](https://github.com/newling/rocm-libraries/commit/92372633557b73d90af16b26b6cf8840213e2be7) |
| Preserve UID placement when writing the file | [8c7517d3334](https://github.com/newling/rocm-libraries/commit/8c7517d33345385d6bde2037abe822064214160b) |
| Clarify the documented decoding and migration behavior (suggestion) | [767a09ac916](https://github.com/newling/rocm-libraries/commit/767a09ac916a12c46f3a6429cf4e6643d4b1cb09) |

The commits address independent items and can be inspected or cherry-picked individually. All source references below point to the submitted head.

## Tests

Submitted PR: focused UID/LibraryIO/TensileMergeLibrary tests and the corpus gate pass. Suggestion branch: those checks, added regressions, and tox/CLI probes pass. A fresh rocisa build, root pre-commit/Bandit, and scoped Python lint also pass.

A broader Python 3.12 `python -m flake8 Tensile` run from `projects/hipblaslt/tensilelite` reports existing findings, such as `F401 'typing.List' imported but unused` in `LibraryIO.py`. All reported diagnostics are present at the diff base under the same lint configuration; none are introduced by the PR or the suggestion commits.

The [uniqueness CI job](https://github.com/ROCm/rocm-libraries/actions/runs/37805607146/job/113409341093) passes at the reviewed head. CI still reports [TensileLite C++ coverage](https://github.com/ROCm/rocm-libraries/runs/113507232736) at 49.33% and [hipBLASLt coverage](https://github.com/ROCm/rocm-libraries/runs/113507212787) at 39.34%, against 80% targets; the C++ result matches the merge base. The [gfx1250 FFM check](https://github.com/ROCm/rocm-libraries/runs/113449159077) reports failures in `gsuaad_gfx1250` and `tdm_multicast_gfx1250`, plus six timeouts. These GPU/emulator failures remain unattributed by this CPU-focused review.

## Summary

This introduces a stored 64-bit identifier and its base62 encoding, plus generation helpers, a command to replace one solution's ID, and a repository uniqueness check. Keeping numeric identity separate from its text representation is a useful boundary; the codec tests cover range limits and alternate prefixes. CPU tests are appropriate for this metadata step, and the LibraryIO and merge suites cover the affected serialization callers. Missing IDs remain allowed for the staged migration.

## Actionable items

### Read solution identities from YAML structure

At [`Tensile/Tests/unit/test_solution_uid_uniqueness.py:164–169`](https://github.com/ROCm/rocm-libraries/blob/a2258880cd9044c06b0005c09ff9a462830932df/projects/hipblaslt/tensilelite/Tensile/Tests/unit/test_solution_uid_uniqueness.py#L164-L169), the scanner recognizes line prefixes and accepts a UID only after encountering an index. This valid YAML passes the submitted gate even though both IDs decode to 1:

```yaml
Solutions:
- SolutionUID: 0u1
  SolutionIndex: 0
- SolutionUID: 0U1
  SolutionIndex: 1
```

Inline mappings also hide duplicates when another entry supplies a recognized index. A malformed decimal UID before its index is silently treated as missing. Conversely, an ordinary comment such as `SolutionUID: 0u1 # persistent ID` produces a false failure because the comment reaches the base62 decoder. The check therefore depends on formatting that it neither validates nor reliably recognizes.

Use YAML parsing to locate actual solution mappings and decode their values. Commit [b09a4e1dbd9](https://github.com/newling/rocm-libraries/commit/b09a4e1dbd9aed89fe5ca8e74ad2ea1565b57964) implements this with streaming parsing, retains YAML alias/merge semantics, and adds format, malformed-value, and cross-file duplicate regressions. The counterexamples were reproduced against the submitted implementation before applying the fix.

The fix constructs only identity fields and referenced anchors, avoiding allocation of the large tuning tables. Across the 2,905-file corpus, the tox gate took approximately 69 seconds versus 5 seconds for the submitted scanner on the same host; reported maximum RSS was about 44 MiB per process. It adds PyYAML to the CPU gate's dependencies.

### Forward the UID settings through tox

At [`tensilelite/tox.ini:88–97`](https://github.com/ROCm/rocm-libraries/blob/a2258880cd9044c06b0005c09ff9a462830932df/projects/hipblaslt/tensilelite/tox.ini#L88-L97), `library-uniqueness` inherits an environment allowlist that omits `HIPBLASLT_REQUIRE_SOLUTION_UID`, `HIPBLASLT_LOGIC_ROOT`, and `HIPBLASLT_UID_TEST_PROCESSES`. Setting any of them in the calling shell has no effect on the test process.

For example, from `projects/hipblaslt/tensilelite` at the reviewed head:

```bash
HIPBLASLT_REQUIRE_SOLUTION_UID=1 python -m tox -e library-uniqueness
```

This exits successfully despite shipped solutions lacking a UID. A custom corpus path is likewise discarded, so a developer can believe a different dataset was checked.

Add the three variables to this environment's `passenv`, preserving the inherited entries. Commit [92372633557](https://github.com/newling/rocm-libraries/commit/92372633557b73d90af16b26b6cf8840213e2be7) does that. Tox probes verify that a small corpus with a missing UID passes in permissive mode and fails in strict mode, while a valid UID passes strict mode. Duplicate and malformed fixtures are rejected through the actual tox entry point. The default migration behavior remains permissive.

### Preserve UID placement when writing the file

At [`Tensile/TensileGenerateUID.py:78–81`](https://github.com/ROCm/rocm-libraries/blob/a2258880cd9044c06b0005c09ff9a462830932df/projects/hipblaslt/tensilelite/Tensile/TensileGenerateUID.py#L78-L81), `reorderSolutionsParams` arranges the in-memory dictionary, but `writeYAML` uses PyYAML's default `sort_keys=True`. Saving the file undoes that ordering: `SolutionNameMin` appears between `SolutionIndex` and `SolutionUID`, and other parameters move ahead of the naming fields. Thus the documented regeneration command does not preserve the field placement this PR introduces.

Pass `sort_keys=False`, following the existing `TensileMergeLibrary` writer convention. Commit [8c7517d3334](https://github.com/newling/rocm-libraries/commit/8c7517d33345385d6bde2037abe822064214160b) applies those writer options and adds disk round-trip tests for both inline and block mappings. Both new cases fail on the submitted implementation and pass with the fix. Running the command on a copy of a shipped logic file also preserves its other parsed values, and the corrected checker finds the generated UID.

## Suggestions

### Clarify the documented decoding and migration behavior

At [`docs/solution-uid.md:33–34`](https://github.com/ROCm/rocm-libraries/blob/a2258880cd9044c06b0005c09ff9a462830932df/projects/hipblaslt/docs/solution-uid.md#L33-L34), distinguish loading the encoded string from decoding it: `LibraryIO.readYAML` preserves the string, and `read_solution_uid` returns its integer value. At [lines 49–50](https://github.com/ROCm/rocm-libraries/blob/a2258880cd9044c06b0005c09ff9a462830932df/projects/hipblaslt/docs/solution-uid.md#L49-L50), describe the later step as requiring UID presence; uniqueness checks for present IDs already exist in this PR. Commit [767a09ac916](https://github.com/newling/rocm-libraries/commit/767a09ac916a12c46f3a6429cf4e6643d4b1cb09) corrects both statements to match the behavior exercised by the codec, CLI, and tox checks.

## Commentary

A UID becomes stable when it is stored. `read_solution_uid` generates a fresh transient value when the dictionary has no UID field; later matching or caching integrations will need an explicit assignment and persistence step before using those values as identities.

All three actionable items and the documentation suggestion are implemented on [review/pr12185-suggestions-20261008](https://github.com/newling/rocm-libraries/tree/review/pr12185-suggestions-20261008), whose tip is [767a09ac916](https://github.com/newling/rocm-libraries/commit/767a09ac916a12c46f3a6429cf4e6643d4b1cb09). The commit mapping and validation are recorded above. No finding implementation was omitted; broader GPU and emulator suites were outside the local validation of these CPU metadata paths.
