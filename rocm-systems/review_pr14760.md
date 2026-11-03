This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#14760](https://github.com/ROCm/rocm-systems/pull/14760)

**Reviewed head:** `38ed97b12bc6cb87dff2ad44e03a8d4451730a27` (verified unchanged on 2026-11-03).

**Scope:** The delta from feature base `9ca3fe3f2f75abab0db5a58149f842c6aba7b43e` to the reviewed head. The underlying image-copy PR is not independently re-reviewed here.

**Suggestion branch:** [review/pr14760-suggestions](https://github.com/newling/rocm-systems/tree/review/pr14760-suggestions), based directly on the reviewed head.

| Commit | Review item | Change |
| --- | --- | --- |
| [a90a57a6035307c460e4ae620fba4ee82ff2a9cf](https://github.com/newling/rocm-systems/commit/a90a57a6035307c460e4ae620fba4ee82ff2a9cf) | Suggestion 1 | Extend the existing mixed FLAT/buffer test to cover the last private lane, nonzero offsets, byte-boundary crossings and untouched neighboring storage. |

## Tests

Release/Clang 23.1 builds of `rocjitsu_tests` and `rocjitsu_analysis_tests` succeeded; all 95 selected submitted-head tests passed (35 directly relevant checks, 56 consumer follow-ups and four incidentally selected packed-instruction tests); all four focused FLAT/buffer tests passed on the suggestion branch, and changed-file pre-commit hooks passed.

Primary checks cover scratch dispatch ABI, workgroup info, GFX10 buffer addresses and bounds, scratch hardware registers, mixed private/global FLAT access, linear image-array layer stride and kernel-descriptor scanning. The separate consumer follow-ups cover descriptor translation, DBI register preservation, PM4 scratch dispatch, scratch fault handling and memory-wait planning. These are local native tests; no GPU hardware, sanitizer configuration or end-to-end HIP surface workload was run for this review.

The [inspected failing release CI job](https://github.com/ROCm/rocm-systems/actions/runs/41566512841/job/125689274600) reports an undeclared `admission_diagnostic` in `xcd_distribution_test.cpp`. It built merge `629e92941bb9df1a20b9ca1c43046d62f63768da` against an earlier base, `31e474e5415d108f0eaccba6c6460f326fbb00be`. That result does not describe the submitted head on its current feature base, which built successfully here. The replacement GitHub merge commit was not separately built.

## Summary

The change makes legacy private-memory launch state agree with the layout used by compiler spills. It supplies a queue scratch base and a separate per-wave byte offset on CDNA1/2 and RDNA1/2, includes that extra system SGPR in descriptor accounting, translates RDNA1/2 generic private pointers into interleaved storage, and corrects GFX10 buffer swizzling and bounds checks. It also exposes workgroup-info state to AQL launches and implements the legacy RDNA flat-scratch register accesses that kernel prologues use.

Sharing the private-layout classification between execution and memory-wait planning is useful: both paths must classify the same lane addresses. The tests also check consequences beyond address arithmetic, including distinct scratch offsets across waves, mixed private/global memory transfers and the different bounds behavior of raw versus formatted buffer accesses. I did not reproduce a correctness defect in the reviewed changes.

## Actionable items

No confirmed correctness issue to report.

## Suggestions

### 1. Exercise nonzero private lanes and byte offsets in the mixed-layout test

**Location:** [`emulation/rocjitsu/tests/instruction_execution_harness_test.cpp:11043`](https://github.com/ROCm/rocm-systems/blob/38ed97b12bc6cb87dff2ad44e03a8d4451730a27/emulation/rocjitsu/tests/instruction_execution_harness_test.cpp#L11043), `LegacyRdnaFlatTest.PrivateAndGlobalLanesKeepDistinctMultiwordLayouts`.

The submitted test accesses private lane 0 at offset 0. It catches an incorrect stride between payload dwords, but those inputs do not exercise the private lane contribution, upper EXEC bits, a nonzero starting dword or a transfer crossing a dword boundary. Retain the existing direct storage checks when adding those cases: a FLAT store followed by a buffer load could agree if both paths made the same addressing mistake.

Extend this test with private lane 0 and the last lane of each wave, and byte offsets 0, 3 and 8. Check a lane-local expected byte image against physical scratch storage, including sentinel values in every neighboring lane; retain the mixed global lane and read the private payload back through the buffer path after clearing its destination VGPRs.

**Implemented in:** [a90a57a6035307c460e4ae620fba4ee82ff2a9cf](https://github.com/newling/rocm-systems/commit/a90a57a6035307c460e4ae620fba4ee82ff2a9cf). Its 24 architecture/wave-size/lane/offset combinations pass against the submitted production implementation. This is additional regression coverage, with no production fix. Run it with:

```sh
"$BUILD_DIR/tests/rocjitsu_tests" \
  --gtest_filter='LegacyRdnaFlatTest.*:LegacyRdnaBufferTest.*'
```

## Commentary

The GFX10 address equation and mode-3 range rules agree with the [RDNA1 ISA](https://gpuopen.com/download/RDNA_Shader_ISA_25September2020.pdf) and [RDNA2 ISA](https://gpuopen.com/download/rdna2-shader-instruction-set-architecture.pdf), §8.1.5. The code explicitly records that `IDXEN + ADD_TID` has not been qualified on GFX10 hardware; the compiler spill path uses `IDXEN=0`. Keep that qualification visible when extending this helper to other buffer users.

The CDNA3/4 workgroup-info wave-ID position remains an interpretation of an inconsistent manual concatenation, as the source comment states. The tests establish consistency with that interpretation; they cannot resolve the hardware contract. This is a stated validation limit, rather than evidence that a different bit position is correct.

The suggestion branch contains only the test commit mapped above. No production correction was justified by the observed results, and no hardware-dependent behavior was changed speculatively.
