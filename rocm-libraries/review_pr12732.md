> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12732](https://github.com/ROCm/rocm-libraries/pull/12732)

**Reviewed head:** [92c4c836f8a884204b2b60303a18ba488a8a2db8](https://github.com/ROCm/rocm-libraries/commit/92c4c836f8a884204b2b60303a18ba488a8a2db8)

**Review date:** 2026-09-29

**Suggestion branch:** [review/pr12732-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12732-suggestions)

**Branch base:** the reviewed head above.

| Commit | Suggestion |
| --- | --- |
| [5c0d8e21f56](https://github.com/newling/rocm-libraries/commit/5c0d8e21f5674013df8e248062540a2fe25ed540) | Separate configuration helpers and add a standalone host test target |
| [5aa5d8059b3](https://github.com/newling/rocm-libraries/commit/5aa5d8059b34568527eb9fdbd9d8d8218b369537) | Dispatch to a collective-specific rank runner |

Both commits are optional design suggestions. They are ordered as listed on the branch and were validated together.

## Tests

On the submitted PR, the fusion-enabled `hipblaslt-test` build and `FusedA2A*smoke.*` host tests passed with ROCm 7.1; the child rejected an unknown collective, and the YAML's unchanged data and revised divisibility claims checked out.

On the suggestion branch, the standalone Clang 23 configuration tests, fusion-enabled and fusion-disabled host targets, installed host executable, rebuilt `hipblaslt-test` smoke tests, and rank-entry checks all passed. The standalone executable links no HIP libraries and ran with GPUs hidden. Default, empty, recognized and unrecognized collective names, plus an oversized world, produced identical exit codes and diagnostics before and after the dispatch refactor. Accepted names reached the GEMM runner's device setup; GPU launch behavior was not retested.

The local multi-process run used two gfx1201 GPUs:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  "$BUILD_DIR/clients/hipblaslt-test" \
  --gtest_filter='World/FusedA2AMultiProcess_multi_gpu.*'
```

Worlds 3–8 skipped because only two devices were visible. The 2-GPU case failed before the launch loop: this build had no gfx1201 device library, so loading `TensileLibrary_lazy_gfx1201.dat` failed and `hipblasLtMatmulAlgoGetHeuristic` returned status 3. This is a local setup limitation, not evidence against the new barrier. The reported 8-GPU gfx950 run and delayed-clear experiment were not independently reproduced.

The [TensileLite CI job](https://github.com/ROCm/rocm-libraries/actions/runs/36610883735/job/109551744225) passed its tests, then failed the coverage ratchet for unchanged `Tensile/Components/Subtile/SubtileGREmit.py` (88.23% versus 90.31%). The [ASAN test job](https://github.com/ROCm/rocm-libraries/actions/runs/36610882901/job/109562208091) lost its container hook during artifact download, before tests. The initial Windows stage was cancelled without test steps. These results do not identify a regression in this diff.

## Summary

The PR expands the separate-process all-to-all test from two ranks to seven world sizes. Each rank exports a fixed 1024-feature shard to every rank and retains a 2048-feature local tail. This preserves the original two-rank problem and satisfies the production tile-divisibility predicate for both supported tile widths, 128 and 256. The parameterized names continue to match the existing `multi_gpu` test category.

The receive-buffer fix establishes the necessary ordering: each rank completes its clear on its own stream before contributing to the rendezvous, and no rank launches until all contributions report success. The existing post-launch synchronization, receive checks and group verdict then finish before the next iteration can clear. Reusing that group-verdict helper is a good fit for this test. I found no actionable defects in the changed code.

## Actionable items

None.

## Suggestions

### Separate configuration helpers from GPU execution

**Submitted locations:** `projects/hipblaslt/clients/common/include/a2a_rank_child.hpp:27–78` and `projects/hipblaslt/clients/tests/src/fused_a2a_multiprocess_gtest.cpp:189–218`.

The shape calculation and name parser are ordinary C++ but reside in the HIP/SDMA rank header. Their tests are compiled only with fusion enabled and run through a main function that initializes a GPU. Moving these helpers into a small independent header lets their tests run without that setup.

Commit [5c0d8e21f56](https://github.com/newling/rocm-libraries/commit/5c0d8e21f5674013df8e248062540a2fe25ed540) adds `a2a_test_config.hpp` and relocates the existing checks into one source used by both the regular `hipblaslt-test` and the new `hipblaslt-a2a-config-test`. The latter links only Google Test, supports a standalone CMake build, and is installed with the test component. Both targets include the checks when fusion is disabled. The shared world list keeps the host checks aligned with the multi-process sweep. Build instructions are in `projects/hipblaslt/clients/tests/a2a_config/README.md`.

### Dispatch to a collective-specific rank runner

**Submitted location:** `projects/hipblaslt/clients/common/include/a2a_rank_child.hpp:124–234`.

The new collective value validates a name but does not yet select an implementation. This works for the sole supported operation. An explicit dispatch makes the intended extension point clearer before adding the reverse operation, A2A followed by GEMM.

Commit [5aa5d8059b3](https://github.com/newling/rocm-libraries/commit/5aa5d8059b34568527eb9fdbd9d8d8218b369537) keeps launcher parsing and world-size bounds in `run_rank_child()`, then switches on the parsed collective. `GemmA2A` selects `run_gemm_a2a_rank()`, which owns its argument setup, launch and validation. Unknown names retain their failure behavior. The GEMM runner body matches the submitted code apart from the renamed argument helper; no second collective or generic callback framework is introduced.

## Commentary

Is there a plan to run this fused GEMM+A2A multi-process test in shared CI with fusion enabled? The existing two-GPU test was already behind the build guard in `projects/hipblaslt/clients/tests/src/CMakeLists.txt:34–38`, and the inspected [Math CI precheckin builds](https://math-ci.amd.com/job/rocm-libraries/job/precheckin/job/hipblaslt/job/PR-12732/1/console) set `HIPBLASLT_ENABLE_GEMM_A2A_FUSION=OFF`. This PR expands that existing test without changing its CI configuration. The coverage gap predates the PR; this is a non-blocking question about follow-up plans.

The 2–8 sweep is the C++ test in `fused_a2a_multiprocess_gtest.cpp`; it does not load `fused_a2a.yaml`. That YAML belongs to TensileLite's separate single-process, multi-GPU client test, available through `tox -e comm`. This PR changes only its comment. The [Math CI preliminary log](https://math-ci.amd.com/job/rocm-libraries/job/preliminary/job/hipblaslt/job/PR-12732/1/console) lists the YAML's `test_config` case as skipped. The normal `py3` environment uses pytest workers, and `Tensile/Tests/conftest.py:263–276` explicitly skips communication tests in those workers because each is restricted to one GPU. Its passing YAML-schema check is not a GPU execution of that configuration.

The new helpers are internal to the rank harness. Their callers bound the world size before using the shape, and the collective parser's default and rejection behavior have direct tests. There is no new serialization or resource-ownership contract to resolve. Host checks are appropriate for those helpers; the author reports multi-process GPU validation of the clear/copy ordering. The YAML edit changes only explanatory comments, so a separate TensileLite kernel-generation run was unnecessary.

The published suggestion branch is based on the reviewed head with the two mapped commits. The suggestions are implemented and locally validated; eight-GPU execution remains outside the available local hardware. The original PR is unchanged.
