This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13526](https://github.com/ROCm/rocm-libraries/pull/13526)

Reviewed head: `e504d2409ea3ae360e463d19aa7955146d6459e9`. Date: 2026-10-22. The repository and PR head branch are public. This review used the description, diff, repository context, local experiments and automated checks; it did not read existing PR reviews or discussion.

Local suggestion branch: `review/pr13526-suggestions`, based directly on the reviewed head. The submitted PR branch is preserved. The [fix and regression patch](patches/pr13526-offset-fix.patch) contains the complete suggestion and can be applied from the repository root with `git apply pr13526-offset-fix.patch`.

| Local commit | Review item |
| --- | --- |
| `d33adb27114161a70e3e76f6e7344287a1cf13b8` | Include the output layout offset in the pointer-array scan; add C and C++ extension regressions |

## Tests

The submitted library and test binary build, and the submitted `aux_check_numerics_gemm` passes on gfx1201; the offset regression fails against the submitted implementation and passes with the suggestion, which also passes the existing pointer-array smoke cases with numerics enabled, changed-code clang-format 18 checks and whitespace checks.

The regression produces four failed assertions against the submitted implementation: each of the C and C++ extension paths misses a NaN in the actual output and reports a NaN confined to the unused prefix. Before checking the reported call, the test copies back the last batch's output and verifies a finite result and the expected NaN at its final element. Both GEMMs therefore execute and write the intended region. The reproducer is retained in the commit's `clients/common/include/testing_aux_check_numerics_gemm.hpp` changes; there is no dependency on a removed temporary probe.

Local validation used ROCm 7.1 for the host library and scanner, and a matching fp32 device library generated from the submitted source with a newer ROCm compiler. The installed device library lacked `TensileLiteLibrary_lazy_gfx1201_Mapping.dat`, causing an initial loader failure. Generating matching kernels with the older compiler then failed with `unknown argument: '-Xclangas'`. Using the newer compiler resolved generation; neither setup failure is a PR defect. Local validation covers gfx1201 and fp32 pointer arrays, not Windows or all output formats. All scanner type specializations compile in the library build. Root pre-commit excludes these C++ files; formatting was checked separately on the changed code.

At the unchanged head, Math CI precheckin, the main Linux gfx94X and Windows hipBLASLt lanes, and the hipBLASLt ASAN lane pass. The [gfx1250 job](https://github.com/ROCm/rocm-libraries/actions/runs/39460819607/job/118759678828) builds hipBLASLt and passes its tests, including `aux_check_numerics_gemm`; its later TensileLite common-test step fails on a 600-second timeout while generating `decouple_pgr_tdm_fuse_gfx1250.yaml`. That generator does not consume the changed scanner. Project coverage is red while patch coverage passes; the separate FFM check requires action. These are distinct from the reproduced scan defect, and no claim is made that every hosted check is green.

## Summary

hipBLASLt's optional numerics mode launches a GPU function after matrix multiplication to look for NaNs in output D. The PR makes that function distinguish a strided buffer from a device array of matrix pointers, and propagates the choice through both the C entry point and the C++ extension adapter.

The address change is small and leaves sampling, call numbering, graph-capture skipping and the strided calculation intact. The new test deliberately places the NaN in the last batch and includes a finite-output control, so it detects a scan that reads only batch zero and a scan that flags finite results. This is appropriate direct integration coverage for the reported memory fault. The remaining output-address issue has a focused repair on the suggestion branch.

## Actionable items

### Include the output layout offset in the pointer-array scan

At the reviewed head, `projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/check_numerics_matrix.hpp:99` reads from `D[batch]`, but pointer-array layouts can select a submatrix with `HIPBLASLT_MATRIX_LAYOUT_OFFSET`. Its public documentation in `library/include/hipblaslt/hipblaslt.h:296` defines an element offset from each matrix's base address. The matmul honors it; the scanner does not receive it from `rocblaslt_mat.cpp:280` or `tensile_host.cpp:595`.

For a concrete case, allocate each 128×128 fp32 output after a 16,384-element prefix and set D's layout offset to 16,384. With a NaN in the last batch's A, the last row of the actual output contains NaNs, yet `hipblasLtCheckNumericsDrain` returns 0. With finite A and NaNs only in the prefix, it returns 1 even though the actual output is finite. Both cases reproduce through `hipblasLtMatmul` and `hipblaslt_ext::Gemm::run`.

Pass an element offset through the scan helpers and add it after loading each matrix pointer. The C entry point has `batch_offset_d`; the extension path has `ContractionInputs::batchOffsetD` in bytes and must convert that to elements using D's type. Keep the default offset zero for existing helper callers.

Local commit `d33adb27114161a70e3e76f6e7344287a1cf13b8`, included in the [fix and regression patch](patches/pr13526-offset-fix.patch), implements this. The extension adapter receives the whole input record so it can use the same output pointer-array choice as the matmul and access the offset. The commit also extends the existing precheckin numerics scenario with both offset cases through both APIs. Run `hipblaslt-test --gtest_filter='*aux_check_numerics_gemm*'` against a matching fp32 device library. Restoring the three runtime files to the reviewed head while retaining that test reproduces all four assertion failures; restoring the commit makes them pass.

## Suggestions

None beyond the implemented item.

## Commentary

The pointer array and every referenced matrix remain caller-owned device allocations. The existing stream sequencing runs the scan after the matmul; callers must keep those allocations alive until the stream completes. The new flag documents the pointer representation and ignores the batch stride in pointer-array mode. No public signature, serialization format or ownership transition is introduced.

The fp32 regression is enough to demonstrate this address calculation without requiring another architecture sweep beyond the submitted shared lanes. Additional direct helper cases for padded rectangular matrices, row order and batch counts crossing the grid-z limit would test more boundaries, but those mechanisms are unchanged and inspection found no separate defect introduced here. Broad TensileLite, rocRoller and unrelated host-unit suites were omitted because they do not exercise the changed scanner.

The handoff is local branch `review/pr13526-suggestions` with the single offset-fix/regression commit mapped above and the accompanying downloadable patch. Submitted and suggestion results are distinguished in Tests. No finding was left unimplemented. The suggestion branch remains local.
