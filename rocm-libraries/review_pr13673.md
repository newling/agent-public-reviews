This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13673](https://github.com/ROCm/rocm-libraries/pull/13673)

**Reviewed head:** `9a1792bb463f0758b65c118660d56d689636a78a` (2026-11-03).
**Suggestion branch:** [review/pr13673-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr13673-suggestions), based on that exact head.
**Commit mapping:** [e730f48b08b](https://github.com/newling/rocm-libraries/commit/e730f48b08b7383e598c4b9068054a3f8dcc0b53) → suggestion S1 below.

## Tests

On the submitted head, the rocisa dependency built and all 265 focused logic-loading, SolutionLibrary, LibraryIO, and TensileCreateLibraryRun tests passed; six additional serialization and multiprocessing probes passed. On the suggestion branch, all 39 affected logic-loading and SolutionLibrary tests passed, along with applicable root pre-commit and whitespace checks.

The local environment used Python 3.12, joblib 1.6, and ROCm 7.1/AMD clang 20. The additional probes exercised pickle identity followed by merging and reindexing for Equality, GridBased, and Range tables. Real logic-file loads produced equal library state through two worker processes, through serial execution, and through the original full-result parser, with both lazy and non-lazy loading. A 1,000-row synthetic table had identical serialized library state with shared and separate wrappers; sharing reduced its pickle from 41,082 to 30,093 bytes. These probes validate the mechanism, not the PR's full-build timing claims.

At review time, the required checks passed, including Component CI, Math CI, Multi-Arch CI, and pre-commit. Optional checks were not all green:

- The [gfx1250-strict job](https://github.com/ROCm/rocm-libraries/actions/runs/41609243691/job/125826814626) built successfully, but all four main hipBLASLt test processes were killed before completion. The log does not establish why they were killed. Its subsequent TensileLite common stage passed. The [latest completed develop run](https://github.com/ROCm/rocm-libraries/actions/runs/41569784845) passed, so this is not asserted to be an established baseline failure.
- The FFM gfx1250 check reports failures in `gsuasb_fp32_atomic_gfx1250`, `sk_bf16gemm_tdm_subtile`, and `subtile_bf16_gfx1250_cluster`, plus ten timeouts. No local reproduction established a connection to this diff.
- The advisory C++ Codecov checks report 50.96% for TensileLite-CPP and 68.77% for hipBLASLt, below their 80% targets. TensileLite-Unit passes at 84.14%.

No full device-library rebuild or GPU execution was repeated locally. The change concerns Python object allocation and transport; focused object-state comparisons and the passing required build/test lanes provide the relevant evidence. The optional GPU failures remain unresolved.

## Summary

The change reduces the object graph transferred from each logic-loading worker. Matching-table rows that select the same solution share one index wrapper, and the library-creation worker omits the standalone solutions list and raw exact-logic data that its caller ignores.

The sharing boundary is appropriate: keys and speed values remain per-row, and the cache is local to each table construction, so identical indices in different input libraries are not conflated. Wrappers retain the solution object rather than copying its index, allowing the existing merge and reindex operations to remain effective. Final library serialization reads values from those objects and does not expose wrapper identity.

I found no actionable correctness defect in the submitted changes. The new unit tests directly check sharing, reindexing, missing solution lookup, argument forwarding, and preservation of the retained parser fields. Unit tests and focused parsing/serialization checks are the appropriate level here; a feature flag or waiver is unnecessary. Adjacent library merging and parsing tests were exercised because they consume the changed objects. No public interface, saved library format, selection policy, or ownership transfer requires a migration.

## Actionable items

None identified.

## Suggestions

### S1. Exercise reindexing after the worker's pickle round trip

Location: [`projects/hipblaslt/tensilelite/tensilelite/Tests/unit/test_tcl_logic_loading.py:36`](https://github.com/ROCm/rocm-libraries/blob/9a1792bb463f0758b65c118660d56d689636a78a/projects/hipblaslt/tensilelite/tensilelite/Tests/unit/test_tcl_logic_loading.py#L36).

The submitted reindexing test changes the original solution's index directly. It does not exercise the serialization boundary that motivates the optimization, or confirm that the reconstructed matching rows still reference the solution held by the reconstructed master library. This is an optional coverage improvement, not a reproduced production failure.

Commit [e730f48b08b](https://github.com/newling/rocm-libraries/commit/e730f48b08b7383e598c4b9068054a3f8dcc0b53) extends that existing test: pickle and restore a `MasterSolutionLibrary`, call its real `remapSolutionIndicesStartingFrom`, and check that both rows share a wrapper pointing to the reindexed master solution. The resulting test passes on the PR implementation. It adds no production changes or commit dependencies.

## Commentary

The worker-specific helper keeps the full parser available to other consumers that need its solutions and exact-logic fields. That is a useful boundary to retain. The small tests exercise observable behavior without relying on timing thresholds, while the PR's external build measurements address the performance claim separately.

Handoff: `review/pr13673-suggestions` contains only the S1 test commit above the reviewed head. The submitted implementation and the suggested test were validated separately. The original PR was not modified. Full local GPU validation and root-cause analysis of the optional GPU CI failures were omitted for the reasons above.
