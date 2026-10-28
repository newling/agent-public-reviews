This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13360](https://github.com/ROCm/rocm-libraries/pull/13360)

**Reviewed head:** `69d20968d2a637b35254a38b2e869e3f45a5ec25`

**Review date:** 2026-10-28

**Review mode:** Follow-up explicitly considering every preceding GitHub review, inline discussion, author response, discussion comment, and the [previous agent review](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr13360.md). Each disposition below was checked against the current code or test evidence.

**Suggestion branch:** [review/pr13360-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr13360-v2-suggestions), based on the exact reviewed head. The PR branch and previous review branch are preserved.

| Commit | Review item |
| --- | --- |
| [ad5c24b1e7d8](https://github.com/newling/rocm-libraries/commit/ad5c24b1e7d882dee460322c81add31089fdcb4e) | Reject an indexed payload if any solution fails to parse; includes a registration regression |
| [403be6451dca](https://github.com/newling/rocm-libraries/commit/403be6451dca17102a2e0bd215812ee08759b7e9) | Reject exact mappings when the index cannot serve the handle's device; includes negative and positive regression checks |

The commits are separate and suitable for individual inspection. The second extends the first commit's valid-payload test to check successful mapping; that positive test hunk depends on the first commit.

## Tests

The submitted head and suggestion branch build with local kernels enabled; focused registry, master, adapter, cache and public-name tests pass. Both new regressions fail before their respective fixes and pass afterward, including valid indexed registration and same-device mapping. Module-allocation, changed-range clang-format 18.1.4 across the full merge-base diff, root pre-commit and whitespace checks pass. The component pre-commit hook succeeds; no Python files changed, so its Python tests and Bandit checks have no applicable scope.

Local validation used ROCm 7.1 and its HIP compiler. An initial rebuild lacked `cblas.h` because a cached OpenBLAS include directory had been removed; correcting that build-cache path resolved it. The indexed-payload tests ran with both legacy and indexed source fixtures containing accepted metadata and a compiled empty GPU function. They exercise parsing, module loading, registration, counts and mapping, without claiming GEMM numerical validation. The foreign-processor regression uses synthetic metadata in the real shared registry, so it requires no mixed-architecture node. Its pre-fix run included only the unrelated indexed-payload fix.

At this head, the [local-kernel workflow](https://github.com/ROCm/rocm-libraries/actions/runs/40550340440) passes on gfx942 and gfx950. Each job passes 46 tests and skips `TwoDevices` and `RegistersOnTheHandlesDevice`. I checked the earlier [shared two-GPU run](https://github.com/ROCm/rocm-libraries/actions/runs/40367424528): both device tests ran and passed at `cf8f6b7275ef4c23937e16b4b0212d2d35af09bb`, with no skipped tests. That is evidence for the preceding implementation; there is no corresponding two-GPU result for the seven newer commits.

The current check rollup is not wholly green. The gfx1250 FFM check reports `sk_bf16gemm_tdm_subtile` failing and nine workloads timing out. [Coverage](https://app.codecov.io/gh/ROCm/rocm-libraries/pull/13360) fails the TensileLite C++ and hipBLASLt project thresholds and the patch threshold. Four other component test jobs also fail; the inspected gfx942 hipkernelprovider failure concerns its two differential golden tests. No registration-related cause was established for those failures. The hipBLASLt Math CI, gfx942 runtime tests, strict gfx1250 build/test check and ASan lane pass.

An additional C11 include-only check fails in the unchanged `hipblaslt.h:53` because it includes the C++ header `<memory>`. Including that existing header directly produces the same failure; it is unchanged from the merge base. To reproduce the new-header check:

```sh
"$ROCM_PATH/bin/amdclang" -std=c11 -x c -fsyntax-only \
  -I"$SRC_DIR/projects/hipblaslt/library/include" \
  -I"$BUILD_DIR/library/include" -I"$ROCM_PATH/include" \
  -include hipblaslt/hipblaslt-local-kernel.h /dev/null
```

The C++ client build succeeds, but this review does not establish compatibility with C translation units. I did not generate fresh numerical payloads, repeat the full GPU registration suite locally, perform a feature-disabled rebuild, or rebuild the full sanitizer suite. Current automated jobs supply the numerical and disabled-option evidence; local tests target the changed host behavior and counterexamples.

## Summary

This PR exposes process-local registration of compiled GPU functions through hipBLASLt. A payload supplies solution metadata and its code object. Registration assigns indices without changing heuristic selection; a separate mapping makes a suitable registered solution preferred for one exact problem shape and type.

The separation between registration and mapping is useful. Module and function caches retain code-object identity when kernel names collide, processor restrictions protect selection and algorithm lookup, and local loads avoid the shipped-module recovery path. The default-off option and dedicated GPU workflow give the experimental path explicit coverage. Host tests suit registry, lookup and bookkeeping behavior, while actual registration and GEMM execution need the GPU tests supplied here. No omitted-test or omitted-flag waiver is needed. Cache selection is a direct consumer of the changed master-library behavior, which is why focused cache tests were included.

The five items from the previous agent review are addressed:

| Previous item | Current disposition |
| --- | --- |
| Unavailable algorithm-name dereference | Fixed in `0c564d344c8d`; the public-name regression passes |
| Module ownership during map allocation | Fixed in `f43f77e980c6`; the allocation probe balances every successful load with an unload |
| Join the launcher on assertion failure | Fixed in `ea40d2b61592`; scope cleanup joins on early return |
| Optional outputs and range-only classification | Documented in `368e792e7b03` |
| Tuning-file precedence | Documented in `ee008acfc489` |

The other preceding discussions are also reflected in the code: device switching covers initialization and registration; code objects load once per path; unrelated paths have separate load locks; function lookup uses both path and name; hardware predicates restrict registered solutions; and hiprtc is required for the enabled test configuration. The tests directly check failure isolation, symbol collisions and concurrent loads. The persistence, replay and journal-write concerns belong to code moved to #13508 and are absent from this PR; their fixes were not reassessed here.

The reviewer considers all six preceding inline comments addressed. The latest layering change removes duplicate exception handling and leaves public status translation in the established wrappers. The new shard helper rejects top-level conversion errors. The POSIX first-character check and Windows filesystem check both identify absolute paths, with the fast POSIX check justified by its use on every launch. The feature guards remain consistent with the experimental option.

## Actionable items

### Reject the whole indexed payload when one solution cannot be parsed

**Location:** [`tensile_host.cpp:8244`](https://github.com/ROCm/rocm-libraries/blob/69d20968d2a637b35254a38b2e869e3f45a5ec25/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L8244), in `loadPayloadShard`.

An indexed shard stores each solution as a separately parsed record. Its cache returns null when a record is malformed or its embedded index disagrees with the index table. `materializeAllSolutions()` skips those records rather than throwing. The new helper therefore returns a shard containing only the surviving solutions, and registration publishes that subset with `HIPBLAS_STATUS_SUCCESS`.

A two-entry payload with one valid solution and one mistyped record returns success with `numIndices == 1` and registered count 1. Replacing the bad record with a valid solution under an inconsistent table index produces the same result. This silently changes the payload's contents instead of rejecting it, unlike the eager format's parse failure and the public registration error contract.

Validate every indexed record before returning the shard. Commit [ad5c24b1e7d8](https://github.com/newling/rocm-libraries/commit/ad5c24b1e7d882dee460322c81add31089fdcb4e) checks each cache entry and rejects the payload before publishing any solution. `LocalKernelRegister.RejectsIncompleteIndexedPayloads` covers both failures, unchanged registration counts, and a valid indexed control. Its source is included in that commit, so no temporary reproducer is needed to reconstruct the finding.

### Apply device restrictions before publishing an exact mapping

**Locations:** [`tensile_host.cpp:8374`](https://github.com/ROCm/rocm-libraries/blob/69d20968d2a637b35254a38b2e869e3f45a5ec25/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L8374) and the [public index contract at `hipblaslt-local-kernel.h:33`](https://github.com/ROCm/rocm-libraries/blob/69d20968d2a637b35254a38b2e869e3f45a5ec25/projects/hipblaslt/library/include/hipblaslt/hipblaslt-local-kernel.h#L33).

The header says an index registered for another architecture is unknown to every index-taking call. Algorithm lookup now enforces this, but `rocblaslt_local_kernel_set_exact_match` checks only the reserved range and whether the process-global registry contains the index. It never evaluates the solution's hardware predicate.

Using the same synthetic foreign-processor solution as the public-name regression, name lookup returns empty while exact mapping returns success and increases the selectable count to 1. Selection still filters the incompatible solution, so this does not demonstrate a wrong-architecture launch. It does demonstrate an accepted state-changing call where the documented result is rejection.

Commit [403be6451dca](https://github.com/newling/rocm-libraries/commit/403be6451dca17102a2e0bd215812ee08759b7e9) applies the hardware predicate before mapping and documents the invalid-value result. The extended `ForeignProcessorMetadata` regression checks rejection and unchanged mapping count; the indexed-payload control checks that a supported index still maps successfully.

## Suggestions

### Link the runtime defect behind the code-object file check

**Location:** [`HipSolutionAdapter.cpp:321–329`](https://github.com/ROCm/rocm-libraries/blob/69d20968d2a637b35254a38b2e869e3f45a5ec25/projects/hipblaslt/tensilelite/src/hip/HipSolutionAdapter.cpp#L321).

The adapter checks ELF and offload-bundle headers because a truncated file can crash the HIP loader. A preceding [response](https://github.com/ROCm/rocm-libraries/pull/13360#discussion_r4297142646) promised a HIP issue and a link in the comment, but the current comment still contains no tracker link. Add the verified public issue reference so maintainers can follow the runtime fix and know when this duplicate format inspection can be retired. The existing valid-file and truncated-file tests are useful and remain worth keeping.

No issue was created and no link was guessed; implementing this suggestion requires the actual tracker reference.

## Commentary

The published branch `review/pr13360-v2-suggestions` has two commits based on the reviewed head: `ad5c24b1e7d` for indexed-payload rejection and `403be6451dc` for device-aware mapping. Both corresponding regressions reproduce the original behavior and pass fixed, with successful-path controls. The fixes stay within runtime registration and preserve the shared loader's enumeration behavior. Wider GPU, C-source compatibility and sanitizer limits are recorded under Tests. No PR-description rewrite accompanies this review.

The suggestion branch was pushed to the fork with explicit authorization. Local, tracking and remote tips match at `403be6451dca17102a2e0bd215812ee08759b7e9`. The fork has no check runs, commit statuses or workflow runs for that tip at the publication snapshot; this is not a CI pass.
