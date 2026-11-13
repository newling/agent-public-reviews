This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14741](https://github.com/ROCm/rocm-libraries/pull/14741)

Reviewed head: `79ae2814251fc91b5ff13894967d5bd669eb0477`. Base and merge base: `eb9b307c4d56d5df63bd3bc60603d33aaa3abbc5`. The repository and PR head are public; the published head was rechecked on 2026-11-13.

Mode: follow-up review of the [previous review](https://github.com/newling/agent-public-reviews/blob/242ec2398929d40b64b8534defb8c224bd041d8e/rocm-libraries/review_pr14741.md), its incorporated suggestions, and the current batching/subprocess diff. Scope includes capability equivalence, failure handling, concurrent initialization, probing cost, and relevant automated checks. Suggestion branch: [review/pr14741-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14741-v2-suggestions), based on the reviewed head, ending at [3ec2732b68c](https://github.com/newling/rocm-libraries/commit/3ec2732b68ce4b6e385939ef97bf15e866221a1a). The [suggestion diff](https://github.com/newling/rocm-libraries/compare/79ae2814251fc91b5ff13894967d5bd669eb0477...3ec2732b68ce4b6e385939ef97bf15e866221a1a) contains only the optional formatting change.

## Tests

Completed validation of the exact submitted head on 2026-11-13: the Release `_rocisa` build succeeded with ROCm 7.1's compiler, Python 3.12, Ninja and ccache. With LLVM 23 as the probed assembler, the full rocisa suite passed **324 tests, with four optional-plugin skips**. With ROCm 7.1 as the probed assembler, all 13 focused probing/initialization tests passed. Assembly-capability maps for all 24 supported ISAs matched the exact base in three paired runs per assembler. A missing executable raised the expected Python `RuntimeError`.

The suggestion branch changes only Python formatting. Its test syntax tree is identical to the submitted version, and all runtime sources are byte-identical. Black 24.4, Pyflakes, root pre-commit hooks, and the complete branch's whitespace checks pass. The runtime results above are reused; the suite was not rerun for formatting alone. Root formatting hooks exclude hipBLASLt, so Black was run directly.

The deterministic [Windows output reproduction](review_pr14741_windows_tail_repro.py) captures both diagnostics at the submitted head. This runs the Windows implementation against a controlled Win32 API shim on Linux. Native Windows evidence comes from the [rocisa Windows job](https://github.com/ROCm/rocm-libraries/actions/runs/43376042247/job/131722787718): **315 passed, 13 skipped**, including execution of the batch-versus-individual comparison. The [Windows hipBLASLt build](https://github.com/ROCm/rocm-libraries/actions/runs/43376044117/job/131778632996) and [tests](https://github.com/ROCm/rocm-libraries/actions/runs/43376044117/job/131778637793) also pass.

The automated-check snapshot at 19:45 UTC on 2026-11-13 remains mixed. The hipSPARSELt discrepancy is described under Actionable items. Other unsuccessful results have these limits:

- The hipBLASLt HOST_ASAN jobs on [gfx942](https://github.com/ROCm/rocm-libraries/actions/runs/43376042231/job/131783652395) and [gfx950](https://github.com/ROCm/rocm-libraries/actions/runs/43376042231/job/131783652359) fail at `sanitizer_allocator_device.h:185`, involving `0xaaaaaaaaaaaaaaaa` allocator metadata. The exact base's [gfx942](https://github.com/ROCm/rocm-libraries/actions/runs/43382941440/job/131797705290) and [gfx950](https://github.com/ROCm/rocm-libraries/actions/runs/43382941440/job/131797705091) jobs show the same signature. This establishes a baseline failure, without diagnosing its cause.
- [`FFM gfx1250 / tensilelite`](https://github.com/ROCm/rocm-libraries/pull/14741/checks?check_run_id=131749808889) reports 252 passes and ten timeouts. Their cause was not established.
- [Codecov](https://app.codecov.io/gh/ROCm/rocm-libraries/pull/14741) reports patch coverage of 54.84% against 78.07%, TensileLite-CPP of 52.98% against 80%, and hipBLASLt of 71.03% against 80%. Passing Math CI and Component CI summaries do not make these results successful.

## Summary

rocisa learns which instructions an assembler accepts by compiling short sources. Batching groups sources sharing a command line and attributes errors to their source lines, removing most process launches. Repeated passes discover probes behind conditional expressions; commands with different wave-size options remain separate. An initialization now owns its command lines and answers in one local object, without a persistent cache or thread-local reset protocol.

The current diff incorporates all six code suggestions from the previous review. The Windows output-loss defect is fixed, and the additional `execFailedExitCode` constant gives the child and caller one definition of execution failure. I found no additional functional defect in the reviewed batching implementation. The local measurements below support reduced probing cost while preserving the tested capability maps.

## Actionable items

### Account for the hipSPARSELt gfx950 failure

The [PR's hipSPARSELt HOST_ASAN job](https://github.com/ROCm/rocm-libraries/actions/runs/43376042231/job/131783652384) fails the integer equality check at [unit.hpp:368](https://github.com/ROCm/rocm-libraries/blob/79ae2814251fc91b5ff13894967d5bd669eb0477/projects/hipsparselt/clients/include/unit.hpp#L368). Both affected cases pass in the [exact base job](https://github.com/ROCm/rocm-libraries/actions/runs/43382941440/job/131797705245).

The cases use sparse A, int8 inputs, int32 output, M=N=128, K=384, three strided batches, bias, and alpha-vector scaling. With bias stride -1, the CPU result is `-1289` and the GPU result is `-1360647`. The subsequent bias-stride-256 case times out after ten minutes. The scalar alpha of zero in the test name does not eliminate the matrix product: [vector-alpha mode sets the host scalar to one](https://github.com/ROCm/rocm-libraries/blob/79ae2814251fc91b5ff13894967d5bd669eb0477/projects/hipsparselt/clients/include/spmm/testing_spmm.hpp#L699).

This is an unresolved validation discrepancy, not an established batching regression. The local capability comparisons cannot establish what happened in that job. Replay these two cases with the same ASAN artifacts on gfx950, comparing the PR and base. If they pass in isolation, retain the original smoke-test order when checking for interference from preceding tests. No source fix is proposed without a cause.

The following selects the two observed cases; run it with the job's library paths and sanitizer environment:

```sh
spmm_case_prefix='*/spmm_test.spmm/smoke_spmm_strided_batched_smoke_i8_ri8_ri32_ri32_ri32_r_SA'
spmm_case_suffix='f32_r_avs_NN_128_128_384_0_128_384_1_128_128_CCCC_3_49152_49152_16384'
hipsparselt-test --gtest_filter="${spmm_case_prefix}_bias_n1_${spmm_case_suffix}:${spmm_case_prefix}_bias_256_${spmm_case_suffix}"
```

## Suggestions

### Format the new probing test consistently

[test_asm_caps_probing.py:56](https://github.com/ROCm/rocm-libraries/blob/79ae2814251fc91b5ff13894967d5bd669eb0477/projects/hipblaslt/tensilelite/rocisa/test/test_asm_caps_probing.py#L56) and the wrapper construction at line 97 differ from the component's Black 24.4 formatting. Optional commit **[3ec2732b68c](https://github.com/newling/rocm-libraries/commit/3ec2732b68ce4b6e385939ef97bf15e866221a1a)** applies Black with line length 100. It changes wrapping and string-quote spelling only; the Python syntax tree is unchanged. This is the suggestion branch's sole commit.

## Scope decisions

Diagnostic completeness remains an explicit compatibility assumption. [hardware_caps.hpp:184](https://github.com/ROCm/rocm-libraries/blob/79ae2814251fc91b5ff13894967d5bd669eb0477/projects/hipblaslt/tensilelite/rocisa/rocisa/include/hardware_caps.hpp#L184) falls back for unattributable errors or abnormal exit status, but cannot detect an exit-1 result containing only some rejected lines. The current description states this limitation. The real-assembler comparisons on Linux and Windows support retaining the approach for the tested probes and toolchains; they do not establish completeness for every future assembler. An exit-status-only subdivision design would remove this dependence but needs its own process-count and timing comparison before replacement is justified.

This changes host-side discovery while retaining the instruction probes and their consumers. The appropriate local checks are the rocisa build, real-assembler equivalence, subprocess failure cases, and existing `initMany` concurrency tests; all are covered by the recorded validation. No additional feature flag or duplicate tests are warranted for the formatting suggestion. A full local device-library build and GPU numerical replay were not performed. Linux and the public Windows jobs define the platform evidence; the inherited `pipe2` dependency does not establish support for every Unix-like host.

## Commentary

### Disposition of the previous review

| Earlier concern | Verified disposition at the reviewed head |
| --- | --- |
| Windows tail diagnostics and skipped comparison | The reader drains after observing exit; the deterministic reproduction captures both messages, and the real-assembler comparison executes in Windows CI. |
| Thread-local ownership and duplicated pending state | `AssemblerProbes` owns one optional-answer map and two command lines within `initAsmCaps`. |
| Signal termination after partial diagnostics | The stronger SIGHUP case is present and passes; the redundant plain-SIGKILL case was removed. |
| Stale comments, direct includes, ineffective compiler guard | The accepted changes are present. The newer execution-failure constant is shared by `run()` and its assembler caller. |
| Home-directory cache and workload motivation | The cache is gone. The description identifies Windows ExtOp generation as a build bottleneck and provides individual CI timings with defined columns. |
| Timing baselines and diagnostic assumptions | The description separates toolchains and revisions, gives individual local runs, and explicitly records the incomplete-diagnostics limitation. |

### Individual probing measurements

These completed measurements compare the exact base and submitted head. A C++ driver calls `initAsmCaps` for all 24 supported ISAs with four workers, compiled with `-O2`. Runs used low priority on a shared Linux host, with no separate warm-up, alternating order as shown. Every pair produced identical `asmCaps` maps. This measures assembler discovery, not GPU execution or complete build time.

| Assembler | Pair | Order | Base seconds | Submitted seconds |
| --- | ---: | --- | ---: | ---: |
| ROCm 7.1 / AMD clang 20 | 1 | Base, submitted | 4.476070 | 0.144196 |
| ROCm 7.1 / AMD clang 20 | 2 | Submitted, base | 4.515050 | 0.150258 |
| ROCm 7.1 / AMD clang 20 | 3 | Base, submitted | 4.417890 | 0.141132 |
| LLVM 23.1 | 1 | Base, submitted | 2.958380 | 0.095841 |
| LLVM 23.1 | 2 | Submitted, base | 2.949770 | 0.104804 |
| LLVM 23.1 | 3 | Base, submitted | 2.998360 | 0.099704 |

The observed paired savings are 4.28–4.36 seconds with ROCm 7.1 and 2.84–2.90 seconds with LLVM 23.1 per 24-ISA initialization. Three pairs on a shared host support the reduction under these conditions, without a precise general speedup estimate. The author's Windows CI build timings are separate evidence and were not remeasured locally.

The suggestion branch [review/pr14741-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14741-v2-suggestions) contains [3ec2732b68c](https://github.com/newling/rocm-libraries/commit/3ec2732b68ce4b6e385939ef97bf15e866221a1a) for the optional formatting item. The GPU replay remains outstanding; native Windows evidence comes from the published job. The earlier posted review is preserved unchanged.
