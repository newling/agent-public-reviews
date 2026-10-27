This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14024](https://github.com/ROCm/rocm-libraries/pull/14024)

Reviewed head: [f535f709eee0f7b9e11cce93562f2f0d578ec84f](https://github.com/ROCm/rocm-libraries/commit/f535f709eee0f7b9e11cce93562f2f0d578ec84f). Incremental base: [53e3c5cf8349134bdeeb8dade4780c6288fbf3d6](https://github.com/ROCm/rocm-libraries/commit/53e3c5cf8349134bdeeb8dade4780c6288fbf3d6), the current head of stacked [#14023](https://github.com/ROCm/rocm-libraries/pull/14023).

This is a follow-up review that considers the earlier review, its linked agent review, all submitted reviews, all 17 inline comments and replies in 11 threads, and all four discussion comments. The comments were checked against the current implementation and local experiments; resolved threads were not treated as proof that their fixes work.

Suggestion branch: [review/pr14024-suggestions-v2-20261026](https://github.com/newling/rocm-libraries/tree/review/pr14024-suggestions-v2-20261026), based on the exact reviewed head. The [complete suggestion diff](https://github.com/newling/rocm-libraries/compare/f535f709eee0f7b9e11cce93562f2f0d578ec84f...811569ecc9faf1c1f129754a9eb864afee470f85) contains four focused commits. The earlier suggestion branch and review artifacts are preserved.

| Commit | Review item |
| --- | --- |
| [48825677e5f](https://github.com/newling/rocm-libraries/commit/48825677e5f591ab75912463238cbae41d363863) | Avoid Windows macros in the half-output test |
| [10c4f6cc3ce](https://github.com/newling/rocm-libraries/commit/10c4f6cc3ce359213a9517aacbe4f51210ae200d) | Keep the shared options source independent of Arguments |
| [c66a2af938c](https://github.com/newling/rocm-libraries/commit/c66a2af938c254dbd95a38074fd3bf5abf451d39) | Check norm support before traversing D |
| [811569ecc9f](https://github.com/newling/rocm-libraries/commit/811569ecc9faf1c1f129754a9eb864afee470f85) | Explain the host work added by strict verification |

## Tests

Submitted and suggestion-branch hipBLASLt benchmark/test targets build; HostUnit and BenchVerify pass on both trees, including the added regressions on the suggestion branch. The suggestion branch also builds the full `tensilelite-tests` target and passes its six hybrid-policy tests. The Windows macro compile probe and isolated options-source compile fail on the submitted tree and pass with their fixes; the unsupported-output probes fail on the submitted tree and pass with the guard.

Full-branch whitespace checks and root/component pre-commit gates pass. The root hooks exclude the affected hipBLASLt files; the component hook selects no Python tests because this diff changes client C++ and documentation.

The Windows probe adds `-Dfar=` and `--offload-host-only` to the build's actual `matmul_gtest.cpp` compile command and replaces compilation with `-fsyntax-only`. This reproduces the two errors in public Windows CI; it is not a native Windows build. The options-source probe is a C++17 syntax check of `clients/common/src/hipblaslt_bench_options.cpp` with only `clients/common/include` on its include path. It checks that the shared implementation remains usable without the hipBLASLt Arguments headers. A further check compiles the submitted options source with the actual `tensilelite-tests` flags; it fails at another header in the Arguments chain, `auxiliary.hpp`. The final consumer build uses `TENSILELITE_BUILD_TESTING=ON`, `TENSILELITE_ENABLE_CLIENT=ON` and the required mxDataGenerator dependency enabled.

BenchVerify exercises `check()` on host buffers, including mixed precision, half output, batching, and unsupported output types. It does not run a GPU GEMM. Full device-library generation, GPU solution sweeps, native Windows execution, and a broad TensileLite suite were omitted. The local ROCm 7.1 installation has the older non-architecture-specific mapping file, while this source expects an architecture-specific device-library mapping. It is unsuitable for qualifying a real GEMM from this head. TensileLite validation focuses on the actual consumer of the shared options source; unrelated kernel-generation tests would not strengthen these client findings.

The current CI result is red. The [Windows build](https://github.com/ROCm/rocm-libraries/actions/runs/40383236095/job/121898818331) and [gfx942 build](https://github.com/ROCm/rocm-libraries/actions/runs/40383236095/job/121898818624) fail for the concrete reasons in actionable items 1 and 2. Other Linux math-library builds also fail. The [gfx90a ASAN build](https://github.com/ROCm/rocm-libraries/actions/runs/40383233717/job/121784916956) fails, but its downloaded log ends without the compiler diagnostic, so its cause is not established here. At publication, Math CI preliminary/precheckin and the gfx942 rocJITsu check are red; coverage and the gfx1250-strict lane remain pending. The additional failed statuses were read, but their causes were not independently established. Earlier green GPU runs should not be presented as validation of this current head.

## Summary

The benchmark collects failed norm and allclose checks of D and gives a previously successful run exit status 2 when strict verification is enabled. Applying option setup in the common dispatch path repairs the earlier datafile bypass. The existing error-code precedence and YAML Arguments layout remain intact.

The batch norm decision preserves a useful distinction between a reporting sum and an acceptance threshold: each batch must meet the GEMM tolerance, while the reported norm error sums the batches. The pointer-array reporting correction counts each batch once. Mixed-precision and half-output tests now exercise the actual tolerance policy, and failing checks are associated with the solution that produced them. Those changes address substantive earlier feedback.

The numerical policy is coherent for this slice. The current landing still has build regressions, and the new unsupported-type fallback needs its guard to run before the work that assumes a supported type.

## Actionable items

### Avoid Windows macros in the half-output test

At [`clients/tests/src/matmul_gtest.cpp:218`](https://github.com/ROCm/rocm-libraries/blob/f535f709eee0f7b9e11cce93562f2f0d578ec84f/projects/hipblaslt/clients/tests/src/matmul_gtest.cpp#L218), the new half-output test names its second fixture `far`. Windows SDK headers define `far` as an empty macro. The preprocessor removes the identifier, leaving invalid expressions at lines 223 and 227. Public Windows CI reports `error: expected expression` at both lines, and the local macro probe reproduces them. This is a build regression in the submitted test, confirming the pending Windows review comment.

Rename the two fixtures to describe their expected outcomes, such as `within_limit` and `beyond_limit`. Commit [48825677e5f](https://github.com/newling/rocm-libraries/commit/48825677e5f591ab75912463238cbae41d363863) does this. The macro probe compiles after the rename, and the half-output test passes in the focused suite.

### Keep the shared options source independent of Arguments

At [`clients/common/src/hipblaslt_bench_options.cpp:8`](https://github.com/ROCm/rocm-libraries/blob/f535f709eee0f7b9e11cce93562f2f0d578ec84f/projects/hipblaslt/clients/common/src/hipblaslt_bench_options.cpp#L8) and [line 111](https://github.com/ROCm/rocm-libraries/blob/f535f709eee0f7b9e11cce93562f2f0d578ec84f/projects/hipblaslt/clients/common/src/hipblaslt_bench_options.cpp#L111), the datafile fix adds an Arguments include and implementation to a source also compiled directly by [`tensilelite-tests`](https://github.com/ROCm/rocm-libraries/blob/f535f709eee0f7b9e11cce93562f2f0d578ec84f/projects/hipblaslt/tensilelite/tests/CMakeLists.txt#L32). That consumer previously needed the independent option accessors and hybrid-policy parser, and does not provide the new include chain's hipblas-common dependency.

The current gfx942 CI build fails while compiling this source for `tensilelite-tests`, through `hipblaslt_arguments.hpp` and `datatype_interface.hpp`, with `fatal error: 'hipblas-common/hipblas-common.h' file not found`. A client-only build can pass because its targets carry the required headers. The datafile setup logic is correct; its placement introduces the cross-target regression.

Move `apply_strict_verification(Arguments&)` into the existing client-only `hipblaslt_arguments.cpp`, which already owns Arguments implementation and is compiled into `hipblaslt-clients-common`. Keep its declaration in the options header and leave the shared options implementation independent of Arguments. This avoids adding an unnecessary hipBLASLt dependency to the TensileLite test target. Commit [10c4f6cc3ce](https://github.com/newling/rocm-libraries/commit/10c4f6cc3ce359213a9517aacbe4f51210ae200d) makes that move. The independent source compile, full TensileLite test-target build and focused hybrid-policy tests pass, as do the rebuilt client/HostUnit targets and existing strict-datafile option tests.

### Check norm support before traversing D

At [`clients/common/include/testing_matmul.hpp:1476`](https://github.com/ROCm/rocm-libraries/blob/f535f709eee0f7b9e11cce93562f2f0d578ec84f/projects/hipblaslt/clients/common/include/testing_matmul.hpp#L1476), the batch loop still executes before the new support/limit check at [line 1499](https://github.com/ROCm/rocm-libraries/blob/f535f709eee0f7b9e11cce93562f2f0d578ec84f/projects/hipblaslt/clients/common/include/testing_matmul.hpp#L1499). An unsupported FP4 output therefore prints `Error type in norm_check_general` once per batch before the useful summary. With an unknown output type in strided mode, `realDataTypeSize(To)` throws `map::at` before the unsupported-type diagnostic and failure increment. Both were reproduced with the existing host-buffer fixture and three batches. This confirms the pending support-check comment; the earlier change that added failure counting only partially repaired the fallback.

Look up the tolerance and comparison support before the loop and skip D's norm traversal when either is unavailable. Hoist the batch mode and byte stride into the supported branch. Preserve serial accumulation and worst-batch selection for supported types. Commit [c66a2af938c](https://github.com/newling/rocm-libraries/commit/c66a2af938c254dbd95a38074fd3bf5abf451d39) implements this, strengthens the FP4 test to reject dispatcher spam, and adds an unknown-output regression that requires one failed check rather than an exception. Both cases pass, along with the existing batch and tolerance tests.

This is a defect in the newly introduced defensive path, not evidence that a currently supported GPU GEMM can produce FP4 D. The current benchmark's output combinations do not establish that reachability. The added API behavior and its tests nevertheless should handle an uncomparable output consistently.

## Suggestions

### Explain the host work added by strict verification

At [`clients/bench/src/client.cpp:489`](https://github.com/ROCm/rocm-libraries/blob/f535f709eee0f7b9e11cce93562f2f0d578ec84f/projects/hipblaslt/clients/bench/src/client.cpp#L489) and [`clients/bench/README.md:137`](https://github.com/ROCm/rocm-libraries/blob/f535f709eee0f7b9e11cce93562f2f0d578ec84f/projects/hipblaslt/clients/bench/README.md#L137), saying the option implies verification explains which checks run but gives little indication of total runtime cost. It enables CPU-reference computation per problem and D transfers/comparisons for the solutions being verified, including selected datafile records. This matters when adding the option to a performance script or solution sweep.

Add a concise statement of that work to the help and user documentation, distinguishing total runtime from the timed GEMM launches. Commit [811569ecc9f](https://github.com/newling/rocm-libraries/commit/811569ecc9faf1c1f129754a9eb864afee470f85) updates the help, README and client documentation. The rebuilt `--help` output contains the explanation. No unverified benchmark numbers are used.

## Commentary

The earlier discussions have the following dispositions. Entries that remain actionable are explained above rather than repeated here.

| Earlier discussion | Current disposition |
| --- | --- |
| Make verification failures nonzero by default | The author acknowledges that direction and tracks it together with broader output checking in the follow-up identified in the [author’s reply to the earlier review](https://github.com/ROCm/rocm-libraries/pull/14024#issuecomment-6424873675). This PR still deliberately keeps strict mode optional. Changing that product policy was not included in the suggestion branch. |
| Strict datafile setup and immediate norm assertions | Addressed: `run_bench_test()` applies strict setup for each loaded record, enabling both D checks and disabling the immediate assertion. The HostUnit setup cases pass. The new placement problem is actionable item 2. |
| Describe mixed-precision tolerances accurately | Addressed: README, conceptual documentation and diagnostic describe a GEMM tolerance, including input types and the fast-BF16 compute allowance. Mixed-precision tests pass. |
| State that strict mode checks D only | Addressed: help and both documents state D-only scope and identify excluded E, bias-gradient, amaxD and ULP checks. The broader check/default change is tracked in the author's reply. |
| Explain benchmark versus gtest batch limits | Addressed as an explicit policy choice: the docs distinguish a per-batch benchmark decision from the summed gtest assertion. The author identifies the gtest policy change separately in the [reply](https://github.com/ROCm/rocm-libraries/pull/14024#discussion_r4381328083). |
| Pointer-array sum assertion and architecture coverage | The shared assertion now uses the same sum policy as strided mode, and the direct host-buffer sum case passes. The cited batch-offset tests use a separate validation routine in `testing_matmul_batch_offset.hpp`; their aggregate count does not directly validate this changed assertion. Cross-architecture numerical qualification of the current head remains unconfirmed because its latest GPU lanes fail before testing. |
| Unsupported output types must not silently pass | Partially addressed in the submitted head; actionable item 3 completes the guard. |
| Count failures from every verified solution and identify that solution | Addressed as an explicit choice: the counter covers each D check across verified solutions and the bench prints the corresponding library index/kernel. The shared gtest path also updates the counter, but only the bench reads it for process exit. The inspected streamk5 tests capture their own heuristic/matmul diagnostics, outside this `check()` path. |
| Add mixed-precision and half-output test coverage | Addressed numerically: both cases pass. The new Windows naming problem is actionable item 1. |
| Windows build failure in the new fixture | Actionable item 1. |
| Parallelize the batch norm loop while preserving ordered results | Optional optimization. The previous strided norm helper also traversed batches serially, so this is not an established regression from this PR. A useful implementation would retain batch-order summation, first-worst/NaN selection and reasonable temporary-memory use. No OpenMP change or performance experiment was added to this review branch; the comment's host-only timings were not independently repeated. |
| Hoist batch mode and datatype-size lookup | Included with actionable item 3 because the supported branch needs the byte stride once and unsupported types must avoid the lookup. |
| Move support/limit checks before the loop | Actionable item 3. |
| Explain strict verification cost | Implemented as the documentation suggestion above. |
| Automated coverage and PR-metadata comments | Read as well. The coverage report reflects the earlier reviewed base/head, including carried-forward component data. It does not establish coverage or a numerical regression on the current head; current coverage CI is pending. |

The finite-data contract and counterexample pass did not establish another numerical defect. Supported types retain their earlier tolerance values, serial sum order and NaN-rejecting worst-error decision. The auxiliary checks and strict-by-default policy remain the explicitly stated scope decisions, rather than additional changes to this landing.

The published suggestion branch is [review/pr14024-suggestions-v2-20261026](https://github.com/newling/rocm-libraries/tree/review/pr14024-suggestions-v2-20261026) at [811569ecc9f](https://github.com/newling/rocm-libraries/commit/811569ecc9faf1c1f129754a9eb864afee470f85), with the four item-to-commit mappings above. Its client builds, focused suites and compiler probes pass. Native Windows, matching-device-library GPU qualification, the broad TensileLite suite and batch-parallel performance measurements remain unperformed for the reasons stated above. This fresh review and its suggestion branch are published as separate artifacts. No GitHub review/comment was submitted and no PR description was rewritten.

## Appendix: unsupported-output counterexamples

These are the exact temporary tests used for the submitted-tree probes, added beside the existing `BenchVerifyD` fixture from `clients/tests/src/matmul_gtest.cpp` and run with `--gtest_filter='BenchVerifyRegression.*'`. The first fails because the captured text contains the norm dispatcher's error; the second throws `map::at`. The committed regression uses scoped capture of the library's error stream so it also works after another test has initialized that stream's duplicated error descriptor.

```cpp
TEST(BenchVerifyRegression, UnsupportedOutputSkipsBatchDispatcher)
{
    BenchVerifyD d(8, 4, 3, HIPBLASLT_BATCH_MODE_STRIDED);
    testing::internal::CaptureStderr();
    const auto failures = d.run(HIP_R_4F_E2M1, HIP_R_4F_E2M1, false);
    const auto diagnostic = testing::internal::GetCapturedStderr();
    EXPECT_EQ(failures, 1);
    EXPECT_EQ(diagnostic.find("Error type in norm_check_general"), std::string::npos);
    EXPECT_NE(diagnostic.find("so D was not verified"), std::string::npos);
}

TEST(BenchVerifyRegression, UnknownOutputCountsFailureWithoutThrowing)
{
    BenchVerifyD d(8, 4, 3, HIPBLASLT_BATCH_MODE_STRIDED);
    EXPECT_EQ(d.run(HIP_R_32F, static_cast<hipDataType>(-1), false), 1);
}
```
