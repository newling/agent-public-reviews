This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13619](https://github.com/ROCm/rocm-libraries/pull/13619)

**Reviewed head:** `f1887b392bf3baba504dfc8a8d914f4e7c222edc`

**Suggestion branch:** [review/pr13619-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr13619-suggestions), based on that exact head.

| Commit | Review item |
| --- | --- |
| [81f961d03f5](https://github.com/newling/rocm-libraries/commit/81f961d03f5c5dea042783c445308e1604ef374b) | Reject an extent larger than M before constructing the reference receive data |
| [a4289ae8caf](https://github.com/newling/rocm-libraries/commit/a4289ae8cafe0a4431bc23b68f8ebac61e642f12) | Update allocation metadata when rotating the receive buffer |

The commits are independent and can be inspected or cherry-picked separately. Both have been pushed to the public fork; the reviewed PR branch is unchanged.

## Tests

The submitted head passed 164 focused Python tests, including 19 snapshots, and 36 focused C++ tests; the SDMA-enabled TensileLite client and tests built, and the suggestion branch passed 43 focused C++ tests, including the new regressions.

The Python selection covered fused problem parsing, client configuration, world filters, logic analysis, matching keys, merge normalization, and conversion back to tuning YAML. Both new regression tests failed against the submitted production code and passed with the fixes. Edited C++ regions were formatted and `git diff --check` passed; root pre-commit hooks select no files for these C++ paths.

The local build used ROCm 7.1. The receive-buffer regression uses small Float tensors, HIP memory transfers, and the CPU reference on a gfx1201 device; it does not launch a fused kernel. Physical gfx950 multi-GPU execution and tuning performance were not repeated locally. Those need the architecture-specific runs described in the PR, since the new selection data and communication behavior cannot be established by host tests alone.

All four required checks passed at the reviewed head. The optional [gfx1250-strict job](https://github.com/ROCm/rocm-libraries/actions/runs/40441964932/job/121984330597) failed during container initialization, before checkout or compilation. The FFM check requires action, and the patch, TensileLite C++, and hipBLASLt codecov checks are red; these do not change the successful required-check results or establish a code failure in this diff.

## Summary

The tuning flow now distinguishes problems by participating GPU count and the leading M extent sent through all-to-all communication. Both values survive benchmark output, winner selection, logic serialization, and client regeneration. The runtime uses corresponding matching properties and restricts eligible shapes to the output layout and transfer sizes the copy engine supports.

Keeping the two selection values explicit throughout that flow is useful, as is replacing comparison against an already-computed GPU output with independently constructed receive data from the CPU reference. The remaining issues concern when that reference can safely be constructed and which allocation its validator reads.

## Actionable items

### Reject an extent larger than M before constructing the reference receive data

Location: [`projects/hipblaslt/tensilelite/client/src/ClientProblemFactory.cpp:493–495`](https://github.com/ROCm/rocm-libraries/blob/f1887b392bf3baba504dfc8a8d914f4e7c222edc/projects/hipblaslt/tensilelite/client/src/ClientProblemFactory.cpp#L493-L495), with the read in [`client/src/ReferenceValidator.cpp:303–306`](https://github.com/ROCm/rocm-libraries/blob/f1887b392bf3baba504dfc8a8d914f4e7c222edc/projects/hipblaslt/tensilelite/client/src/ReferenceValidator.cpp#L303-L306).

The client checks that each extent is positive but accepts an extent larger than M. The new `referenceRecvs()` copies that many feature elements from reference D during `preProblem()`, before the solution's `FusedA2AShape` predicate can reject the shape. The Python YAML parser rejects this input, but the direct client configuration path does not.

For sizes `[3072, 512, 1, 2048]`, world 2, and extent 4096, the last destination shard reads feature indices through 4095 from a column containing 3072 elements. With contiguous D and validation enabled, the final column reads 1024 elements beyond the allocation. An invalid client input can therefore read unrelated host memory or crash instead of reporting an unsupported shape.

Validate `extent <= freeSizeA(0)` in the problem factory before setting up the receive tensor. Commit `81f961d03f5` adds that check and extends `FusedA2AClientProblemFactory.InvalidWorldOrExtentThrows` with extents 3073 and 4096. The submitted factory did not throw; the fixed factory does.

### Update allocation metadata when rotating the receive buffer

Location: [`projects/hipblaslt/tensilelite/client/src/DataInitialization.cpp:3600–3609`](https://github.com/ROCm/rocm-libraries/blob/f1887b392bf3baba504dfc8a8d914f4e7c222edc/projects/hipblaslt/tensilelite/client/src/DataInitialization.cpp#L3600-L3609).

`createRotatingInput()` copies `A2A_RECV` into a buffer sized for the current problem, but leaves its `maxElements` copied from the original input. That value includes the original allocation's extra bounds-check padding and can also reflect a larger problem. D, E, and bias already reset this metadata after rotation; the receive tensor needs the same treatment.

With NaN bounds checking enabled, the new receive validation uses the stale size to infer padding before and after the rotated buffer. It reads neighboring memory as padding and shifts the apparent start of the result. A valid 64×64 receive buffer reproduced a `FAILED` verdict with 512 spurious errors on each side.

Add `A2A_RECV` to the allocation-size reset. Commit `a4289ae8caf` does this and adds `ReferenceValidatorFusedA2A.RotatedReceiveBufferUsesItsOwnAllocationSize`. The test creates an original padded buffer and a rotated buffer, supplies the correct reference result, and expects `PASSED`; it then corrupts the last receive element and expects `FAILED`. It failed on the submitted code and passes with the fix.

## Suggestions

None beyond the two concrete fixes above.

## Commentary

The schema and lookup changes warrant direct Python tests and C++ selection tests, while communication and tuning need gfx950 integration runs. The PR includes both categories and keeps fusion behind its existing build option, which defaults off. Relevant adjacent paths are ordinary GEMM client validation, benchmark timing, and synchronizer reporting; these were included in the focused checks. No unrelated subsystem test suite was needed.

The local branch contains both proposed fixes and their reproductions. No implementation is omitted for the findings; the validation omission is repeating the full physical gfx950 multi-GPU and performance campaign.
