This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12588](https://github.com/ROCm/rocm-libraries/pull/12588)

Reviewed head: [bb3a59b8adc](https://github.com/ROCm/rocm-libraries/commit/bb3a59b8adc6c41f1129ad075c6b0dba005329a3), unchanged when checked on October 22. This follow-up checks the previous combined review's items and the current implementation. It was revised in place at the reviewer's request after further source inspection and focused experiments. Existing GitHub review threads and comments were not read.

Suggestion branch: [review/pr12588-followup-20261022](https://github.com/newling/rocm-libraries/tree/review%2Fpr12588-followup-20261022), based directly on the reviewed head. All four commits below are published. [Compare all four commits](https://github.com/newling/rocm-libraries/compare/bb3a59b8adc6c41f1129ad075c6b0dba005329a3...8104f7a3424241ba7a51ac769a7eeaf29295144d).

| Commit | Review item |
| --- | --- |
| [f18d43963fb](https://github.com/newling/rocm-libraries/commit/f18d43963fbf94a2af5d94a1223488eb6e28c26c) | Keep the XCC preparation test off a private TensileLite template. |
| [76eb0415f05](https://github.com/newling/rocm-libraries/commit/76eb0415f05960087f8ab8a118977b0583db50bf) | Decline only descriptors carrying an all-to-all prefix. |
| [2aad22ce71e](https://github.com/newling/rocm-libraries/commit/2aad22ce71e1a71a6dcda519308de38a606e56c8) | Qualify the runtime rotation comment and test name without changing arithmetic. |
| [8104f7a3424](https://github.com/newling/rocm-libraries/commit/8104f7a3424241ba7a51ac769a7eeaf29295144d) | Distinguish failed-attempt latching from successful retuning in the how-to. |

The additions preserve the published commits and require no history rewrite. No cache precedence, workspace, locking or winner-policy change is included.

## Tests

Initial submitted-head and two-commit suggestion-branch validation on gfx1201: the focused tuning/cache/store, candidate and rotation suites gave 133 passed, 3 skipped and 0 failed; numerical tune/cache benchmark runs also passed. Subsequent audit validation built the submitted targets and passed 47 focused tests without skips on both the submitted and audit-suggestion trees. The updated four-commit linked branch at [8104f7a3424](https://github.com/newling/rocm-libraries/commit/8104f7a3424241ba7a51ac769a7eeaf29295144d) also builds and passes the same 47 focused tests without skips.

The initial skips were FP8 FNUZ, grouped GEMM and XF32 cases without solutions in the reduced fp16/fp32 device library. The Windows link error was confirmed independently from the hosted build log; no local Windows build was run. The replacement XCC test passes on Linux and fails when its assignment is removed. The original all-to-all suggestion compiled with fusion enabled; fusion-enabled execution and multi-rank behavior remain untested. Numerical gradient dispatch, block-scaled GPU behavior and broad performance parity were not tested.

A submitted benchmark run confirms the nonzero-beta rotation discrepancy below. A host probe using the real store writer, loader and map confirms live-versus-reloaded row ordering, with synthetic entries rather than actual GPU winners.

At the current head, the [Windows gfx110X math-libs build](https://github.com/ROCm/rocm-libraries/actions/runs/39723423880/job/119676485777), Multi-Arch summary, project hipBLASLt coverage and FFM gfx1250/TensileLite status fail. [gfx1250-strict](https://github.com/ROCm/rocm-libraries/actions/runs/39723422556/job/119641943456) has now passed. Linux builds, pre-commit, clang-tidy and ASAN lanes pass. Only the Windows failure was investigated.

## Summary

This head adds opt-in first-call tuning on the shared measurement loop, with owned scratch outputs/workspace, a latch for failed attempts and cache replay. An explicit algorithm remains authoritative, including on the call that tunes. A null-algorithm call can launch the freshly selected winner or the winner produced by a thread it waited for.

The shared candidate preparation, heuristic top-up and measurement/search helpers are substantive reuse. The scratch tests check readable extents, auxiliary copies, capacity boundaries and failure handling. Shared formulas do not establish identical benchmark/runtime measurements when callers supply different workspace, tensor accounting or buffer residency.

The merged foundations are [#12585](https://github.com/ROCm/rocm-libraries/pull/12585), [#12586](https://github.com/ROCm/rocm-libraries/pull/12586), [#12587](https://github.com/ROCm/rocm-libraries/pull/12587) and [#13568](https://github.com/ROCm/rocm-libraries/pull/13568). This PR deliberately records nothing after a budget stop. Open [#12589](https://github.com/ROCm/rocm-libraries/pull/12589), at [64e07374b0ee](https://github.com/ROCm/rocm-libraries/commit/64e07374b0ee367458ce97b4fe4fe18f869f9863), contains this exact head and adds partial-search persistence, coverage/workspace metadata, retuning and row precedence. Those policy changes belong to that layer.

Status of the previous review's items:

| Earlier item | Status at this head |
| --- | --- |
| Copy gradient auxiliary input into every scratch block | Addressed; expanded readable layouts are declined. Numerical dispatch remains a coverage suggestion. |
| Prepare candidate XCC arguments through the normal launch path | Addressed in the library; the regression test breaks the Windows link. |
| Exclude fused communication from isolated tuning | Addressed before locking/tuning; the predicate also excludes an empty descriptor. |
| Stop the search after a failure reported while measuring | Addressed; shared-search cases pass. |
| Make budget tests deterministic | Addressed through injection and a multi-candidate condition. Both selected cases executed here; a one-candidate library skips the post-measurement case. |
| Let cache diagnostics run with one algorithm | Addressed. |
| Share heuristic candidate fallback and order | Addressed; direct tests compare ordered lists at caps 1, 16 and 256. |
| Share benchmark rotation rules | Shared helpers preserve benchmark arithmetic; runtime inputs still differ for non-32-bit C and resident block-scaled scales. |
| Share workspace and timer choices | Shared timing, deliberately different workspace adapters. GPU events versus the benchmark's optional CPU timer are already documented. |

## Actionable items

### Keep the XCC preparation test off a private TensileLite template

[candidate_preparation_gtest.cpp:25](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/clients/tests/src/candidate_preparation_gtest.cpp#L25) calls `ContractionSolution::calculateInternalArgs<false>` to read the packed XCC value. That template is instantiated inside the library but not exported from its Windows DLL. The hosted linker reports this exact undefined symbol from this test's object, breaking `hipblaslt-test.exe` and the Multi-Arch summary. The test originated in an earlier review suggestion, not the author's original implementation.

[f18d43963fb](https://github.com/newling/rocm-libraries/commit/f18d43963fbf94a2af5d94a1223488eb6e28c26c) checks the parameter `prepareCandidateXcc` sets: fallback requests 1; zero restores automatic mapping. It retains a stale starting value and alternates fallback/ordinary candidates. Removing the assignment fails the test. This fix avoids expanding the library's exported interface solely for a test; its Windows link still needs hosted confirmation.

### Correct the unconditional once-per-shape claim

At [how-to:244](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/docs/how-to/how-to-use-hipblaslt-offline-tuning.rst#L244), “at most once in any case” incorrectly includes successful searches. The key omits workspace, and replay [rechecks support for each call](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp#L648). A lower allowance can invalidate the saved winner and trigger another search. Only failed attempts after `tuning-start` are latched. [8104f7a3424](https://github.com/newling/rocm-libraries/commit/8104f7a3424241ba7a51ac769a7eeaf29295144d) corrects the wording.

This distinction also affects persistence. At [tensile_host.cpp:5660](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L5660), a successful retune removes old live entries with `replaceAll`, then appends the new row to the file. Restarting reloads both in file order and can select the older winner again.

The host probe installs a 4096-byte-workspace winner (index 7), then replaces it with a zero-workspace winner (index 9) while appending both. With zero allowance, both live and reloaded maps choose 9. With 4096 bytes, the live map chooses 9 but the reloaded map chooses 7. This establishes storage/order differences, not actual GPU performance. The reproducer is below.

A claim that the shape “settles after two searches” is therefore process-local and assumes both kernels otherwise support later calls. Beta and C/D aliasing are outside the key too. No row-policy fix is included here: #12589 already [retains entries and orders them complete-first/newest-first](https://github.com/ROCm/rocm-libraries/blob/64e07374b0ee367458ce97b4fe4fe18f869f9863/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/TuningCacheStore.hpp#L492). Whether to bring that behavior into this layer is a sequencing decision.

## Suggestions

### Qualify rotation equality without changing benchmark behavior

At [tensile_host.cpp:4484](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L4484), the comment claims the callers plan the same rotation and that block-scaled scales count in neither footprint. Both statements need qualification.

For fp16 1024³, distinct C/D, 512 MiB rotation and at least 100 launches, beta zero gives 6 MiB and 86 blocks in both callers. Beta one gives runtime 8 MiB/64 blocks but benchmark **10 MiB/52 blocks**, confirmed by a benchmark run. At [testing_matmul.hpp:2286](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/clients/common/include/testing_matmul.hpp#L2286), the benchmark counts C with `sizeof(To)`, the 4-byte datatype enum, rather than the element size. The [runtime test](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/clients/tests/src/tuning_tune_test.cpp#L2299) checks runtime twice, not benchmark equality.

The PR body acknowledges this preserved benchmark arithmetic. Its “non-32-bit C is counted larger” wording applies to smaller element types; 64-bit C is counted smaller. [2aad22ce71e](https://github.com/newling/rocm-libraries/commit/2aad22ce71e1a71a6dcda519308de38a606e56c8) corrects the source comment and renames the test to `BlockCountUsesActualTensorBytes`, preserving assertions and both algorithms. Fixing the benchmark's estimate is a separate behavior change.

The benchmark also [sizes block-scaled scale buffers](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/clients/common/include/testing_matmul.hpp#L2224), counts and rotates them. Runtime leaves block-scaled/w4a16 scales resident and out of its footprint. Counting them without rotation would not reproduce the benchmark's memory behavior. Scope any parity follow-up to affected Tensile calls: many default block-scaled calls use rocRoller and bypass this tuner. No performance or winner effect was measured.

### Compare workspace-dependent launches before claiming parity

Runtime prepares candidates with [the caller's full workspace allowance](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L5093). The ordinary benchmark path [takes the maximum requirement over eligible candidates](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/clients/common/include/testing_matmul.hpp#L5178) and passes that common allocation size to each candidate; special placement checks can use candidate-specific sizes.

Workspace can affect Stream-K, which distributes reduction work across GPU workgroups, so identical solution indexes need not mean identical launches. No changed launch or winner was demonstrated. If strict parity is claimed, compare prepared arguments with matched workspace. Do not require the runtime to ignore the application's actual allowance without establishing why.

The GPU-event versus synchronized CPU timer distinction is already explicit in the [how-to](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/docs/how-to/how-to-use-hipblaslt-offline-tuning.rst#L250) and PR body. There is no outstanding timer-documentation request.

### Use the existing all-to-all predicate for an empty descriptor

[tensile_host.cpp:4639](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L4639) returns true for any non-null fused descriptor. Normal problem setup instead resolves it and checks `hasA2APrefix`. [76eb0415f05](https://github.com/newling/rocm-libraries/commit/76eb0415f05960087f8ab8a118977b0583db50bf) follows that established predicate.

This is a minor eligibility improvement. The descriptor [currently recognizes only the A2A prefix stage](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/hipblaslt.cpp#L114), so a descriptor without it is empty, not another supported noncollective fusion operation. A fusion-enabled empty-descriptor test can validate the distinction without coordinated peer ranks. The published fix was compile-checked with fusion enabled, not executed.

### Add a numerical gradient case

The [auxiliary-copy test](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/clients/tests/src/tuning_scratch_gtest.cpp#L13) checks every gradient input block, padding and caller preservation. Scratch-plan tests check expanded readable layouts are declined while writable forward layouts remain usable. These are meaningful checks.

A small DGELU derivative-epilogue case through tune mode, compared against a numerical reference, would test the kernel result after preparation. This is a coverage suggestion; no wrong gradient output has been demonstrated.

## Commentary

The current [single-writer documentation](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/docs/how-to/how-to-use-hipblaslt-offline-tuning.rst#L166) already describes unsynchronized processes and a single-rank warm-up followed by multi-process replay. Concurrent writers remain unsupported; adding file coordination or comparing recorded times across runs/devices would be a separate feature, not missing documentation.

Runtime chooses the lowest average from one timed batch: [fixed-count timing sets mean, median and minimum to that same value](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/benchmark/hipblaslt_benchmark/benchmark_timing.hpp#L321). It does not enable the optional benchmark skip-slow screen. Near-tie instability and the no-minimum-margin policy are [already documented](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/docs/how-to/how-to-use-hipblaslt-offline-tuning.rst#L221). Requiring a minimum improvement would change winner policy, not repair an established defect.

The global tuning lock also protects [one retained scratch allocation per device and its slot map](https://github.com/ROCm/rocm-libraries/blob/bb3a59b8adc6c41f1129ad075c6b0dba005329a3/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L4010). Per-key locks alone could let same-device shapes overwrite or free each other's scratch, and simultaneous searches would contaminate timings. Per-device serialization is more plausible for independent GPUs, but needs separate map/lifetime protection. Treat it as future concurrency design work. Fused all-to-all is excluded before locking; in-place-beta and cap checks happen inside. Ordinary cached calls can still compete with measurements, which is why the docs advise a quiet GPU.

The per-shape budget excludes time waiting for that lock and is checked between candidates, not during an already-submitted batch. The default five minutes is therefore not a hard bound on the application's first-call latency. Budget-stopped searches intentionally record nothing in this layer.

The published branch handoff remains [review/pr12588-followup-20261022](https://github.com/newling/rocm-libraries/tree/review%2Fpr12588-followup-20261022), with the four item-to-commit mappings above. The branch and this revised file were published at the reviewer's request. No broad benchmark-default, row-precedence, locking or winner-policy change was made. No PR-description rewrite or GitHub review/comment was performed.

## Appendix: counterexamples

### Nonzero-beta rotation

Set `DEVICE_PATH` to a compatible device-library directory. Omit the boolean `--c_equal_d` switch so C and D are distinct:

```bash
HIPBLASLT_TENSILE_LIBPATH="$DEVICE_PATH" "$BUILD_DIR/clients/hipblaslt-bench" \
  -m 1024 -n 1024 -k 1024 --precision f16_r --beta 1 \
  --rotating 512 --iters 100 --cold_iters 100 --use_gpu_timer
```

The submitted benchmark prints:

```text
Rotating buffer 512 MiB. Needed Size: 10 MiB. Needed block count: 52
```

The submitted `TuningScratchPlan_pre_checkin.BlockCountFollowsTheBenchFootprint` instead passes its 86/64 runtime assertions. The suggestion renames the same test without changing its results.

### Live map versus reloaded file

Save the source below as `store_restart_probe.cpp`. Build the submitted `hipblaslt-tuning-store` target, and set `NEW_CACHE_FILE` to a path that does not yet exist:

```bash
"$ROCM_PATH/bin/amdclang++" -std=c++20 -O2 \
  -I"$SRC_DIR/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include" \
  -I"$SRC_DIR/projects/hipblaslt/tensilelite/include" \
  -I"$SRC_DIR/projects/hipblaslt/tensilelite/rocisa" \
  -I"$BUILD_DIR/tensilelite/include" store_restart_probe.cpp \
  "$BUILD_DIR/library/src/amd_detail/rocblaslt/src/libhipblaslt-tuning-store.a" \
  -o "$BUILD_DIR/store_restart_probe"
"$BUILD_DIR/store_restart_probe" "$NEW_CACHE_FILE"
```

Expected output:

```text
allowance=0 live=9 reloaded=9
allowance=4096 live=9 reloaded=7
```

The fake entries isolate writer/loader/map ordering and workspace-only eligibility; their names do not resolve to GPU kernels and their times are incidental.

```cpp
// Copyright Advanced Micro Devices, Inc., or its affiliates.
// SPDX-License-Identifier: MIT

#include "TuningCacheStore.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>

using namespace TensileLite;

int main(int argc, char** argv)
{
    if(argc != 2 || std::ifstream(argv[1]).good())
        throw std::runtime_error("Supply a new cache-file path");
    const std::string stamp = "abc1234";
    const TuningRowTypes types{"f16_r", "f16_r", "f16_r", "f16_r", "f32_r"};
    ProblemOverride key;
    key.m = key.n = key.k = 1024;
    key.batchSize = 1;
    key.inputTypeA = key.inputTypeB = key.outputTypeC = key.outputTypeD = rocisa::DataType::Half;
    key.computeType = rocisa::DataType::Float;
    key.colStrideA = key.colStrideB = key.colStrideC = key.colStrideD = 1024;
    key.archName = "gfx950:sramecc+:xnack-";
    key.cuCount = 256;

    TunedEntry high;
    high.solutionIndex = 7;
    high.kernelName = "high_workspace";
    high.schemaVersion = kCurrentTuningSchemaVersion;
    high.buildStamp = stamp;
    high.requiredWorkspaceBytes = 4096;
    high.winnerTimeUs = 1.0;
    TunedEntry low = high;
    low.solutionIndex = 9;
    low.kernelName = "low_workspace";
    low.requiredWorkspaceBytes = 0;
    low.winnerTimeUs = 2.0;

    OverrideMap live;
    live.replaceAll(key, high);
    if(!appendTuningRow(argv[1], formatTuningRow(key, types, high, stamp), stamp))
        throw std::runtime_error("First append failed");
    live.replaceAll(key, low);
    if(!appendTuningRow(argv[1], formatTuningRow(key, types, low, stamp), stamp))
        throw std::runtime_error("Second append failed");

    OverrideMap reloaded;
    std::ifstream in(argv[1]);
    if(loadTuningRows(in, reloaded, stamp).accepted != 2)
        throw std::runtime_error("Expected two distinct rows");
    // Model only workspace eligibility; these names do not resolve to GPU kernels.
    auto pick = [&](const OverrideMap& map, size_t allowance) {
        for(const auto& entry : map.find(key))
            if(entry.requiredWorkspaceBytes <= allowance)
                return entry.solutionIndex;
        return int32_t(-1);
    };
    for(size_t allowance : {size_t(0), size_t(4096)})
        std::cout << "allowance=" << allowance << " live=" << pick(live, allowance)
                  << " reloaded=" << pick(reloaded, allowance) << '\n';
    return pick(live, 4096) == 9 && pick(reloaded, 4096) == 7 ? 0 : 1;
}
```
