This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15275](https://github.com/ROCm/rocm-libraries/pull/15275)

**Reviewed head:** `388533cd163ca0977324e6ec76dbec19bc11378d`. **Base:** `6d3fbe2101d868de5b04b0e6916fb7bbb1dde6fd` (#16149).

**Scope:** Independent review of all four changed files: `client/src/Reference.cpp`, `client/cpu_gemm_driver.cpp`, `tests/CMakeLists.txt`, and `tests/ReferenceFastPath_test.cpp`, all under `projects/hipblaslt/tensilelite`. Checked type selection, output conversion, the driver's expected-result calculation, test registration and the preceding scaling fix. Later stack features are outside this review.

**Assessment:** The Float8-output implementation looks sound. One small test-registration correction is needed so the standard tier and installed package run both added saturation-corruption checks. Required CI remains incomplete after the restack.

**Suggestion branch:** [review/pr15275-readiness-20261120](https://github.com/newling/rocm-libraries/tree/review/pr15275-readiness-20261120), based on the reviewed head ([exact comparison](https://github.com/newling/rocm-libraries/compare/388533cd163ca0977324e6ec76dbec19bc11378d...20d9480395f26e608bc3ef47f07df4a92c321ee7)). Commit [d5fdc1f2440b](https://github.com/newling/rocm-libraries/commit/d5fdc1f2440b493e604118c7548cf4073adeae22) fixes test registration and checks the expected failure diagnostic. Optional commit [20d9480395f2](https://github.com/newling/rocm-libraries/commit/20d9480395f26e608bc3ef47f07df4a92c321ee7) adds direct test includes and formats the new test blocks. Neither changes production code.

## Tests

The submitted head built `tensilelite-tests`, `cpu-gemm-driver`, and `tensilelite-client` in Release mode with ROCm C++20 and OpenMP. All **742 standard CPU-driver CTests** and **63 focused reference/conversion gtests** passed. On the suggestion branch, all three targets rebuilt and **744 standard driver CTests** plus the same **63 gtests** passed. The two newly registered checks also passed through the installed standard tier with `LD_LIBRARY_PATH` unset and the local SDK runtime dependencies available. This was a focused installed-run check, not a full package qualification.

The regression checks distinguish the intended behavior. Restoring the parent's reference implementation failed three of the four new Float8-output gtests; the Scalar fallback control continued to pass. Separately disabling the driver's scale-before-narrowing predicate failed all four small Scalar driver cases, with numerical mismatches of 0.125–0.375. All temporary changes were removed before suggestion validation.

Root and component hooks completed successfully; their selectors do not run C++ formatting or Python tests for this patch. Scoped formatting and full-diff whitespace checks pass. No GPU, Windows, sanitizer or full gtest-suite run was performed locally.

The November 20 CI snapshot contains unfinished Component/Multi-Arch/Math checks after the restack. The [policy-bot failure](https://github.com/ROCm/rocm-libraries/actions/runs/44826172848/job/136599235821) cites a cancelled pre-commit run; the snapshot also contains a successful replacement pre-commit. Cancelled duplicate runs are not evidence of a numerical regression, and the new required runs still need to complete.

An exploratory host timing check compared the retained slow path with the new fast path on the same build, whose production code matches the submitted head. Workload: Float8 A/B/C/D, M=1023, N=1025, K=1021, no transposes or scales, alpha=1, beta=0; Ryzen Threadripper PRO 9995WX, eight OpenMP threads, dynamic threading disabled and `KMP_BLOCKTIME=0`. Each entry is one fresh driver launch, with no warm-up launches; validation was disabled for timing. The reported execution time includes the reference call and fast-eligibility check, excluding input setup and process startup.

| Measurement | Pair 1 | Pair 2 | Pair 3 |
| --- | ---: | ---: | ---: |
| Slow first (1=yes) | 1 | 0 | 1 |
| Slow time, ms | 547.441 | 549.865 | 546.295 |
| Fast time, ms | **35.7513** | **42.3153** | **38.6316** |

The observed speedup is approximately 13–15× for this workload. Three pairs on a shared host establish a useful local check, not a general speedup guarantee or a reproduction of the description's GPU-host campaign.

## Summary

The change admits 24 existing Float8/BFloat8 output type combinations to the blocked reference. It retains float accumulation and uses the same final `SaturateCast` as the slow reference. The explicit type whitelist prevents unsupported combinations from acquiring a fast-only implementation. The existing logical-element write-back loop also preserves stride padding for the four newly handled output types.

Scalar Half-to-Float8 narrowing still falls back through #16149; Vector narrowing becomes fast-eligible. The previously missing driver correction is now published: it scales a consumed Scalar operand before quantization and excludes that scale from the final multiplier, preserving the original input arrays. Independent expected literals exercise rounding, saturation, nonfinite outputs and the Scalar/Vector distinction. Matching NaNs are accepted while a NaN on only one side fails validation.

## Actionable items

### Register the saturation-corruption checks in the standard and installed suites

[`tests/CMakeLists.txt:998`](https://github.com/ROCm/rocm-libraries/blob/388533cd163ca0977324e6ec76dbec19bc11378d/projects/hipblaslt/tensilelite/tests/CMakeLists.txt#L998) registers the two `F8_F8_S_InjectedFailure_Rejected` cases with raw `add_test`, bypassing `add_cpu_gemm_test`. Consequently they have no standard-tier labels, OpenMP limits, timeout or installed registration. They appear in an unfiltered build-tree run but disappear from both validation routes named in the test plan. These cases check that deliberately changing a saturated Float8 result is detected.

Use the existing helper and require the numerical-mismatch diagnostic. Commit [d5fdc1f2440b](https://github.com/newling/rocm-libraries/commit/d5fdc1f2440b493e604118c7548cf4073adeae22) does that without changing the input cases. Both checks now inherit the eight-thread limit and timeout, run under the standard label in both locations, and require `Mismatch at 0:` as well as a failing driver exit. An unrelated option-parsing or dispatch error can no longer satisfy a bare `WILL_FAIL` test.

## Suggestions

### Make the new test dependencies explicit

Optional commit [20d9480395f2](https://github.com/newling/rocm-libraries/commit/20d9480395f26e608bc3ef47f07df4a92c321ee7) adds `<cstddef>` and `<initializer_list>` near `tests/ReferenceFastPath_test.cpp:9` and formats the new Float8 test blocks. The test tokens are otherwise unchanged. This is not a condition for accepting the numerical change.

### Refresh the publication status in the description

The Test Result section still says the driver correction awaits a stack push and identifies `87e708e694d0` as the published head. The reviewed `388533cd163c` contains that correction. Keep historical test results tied to their original revisions, but remove the obsolete unpublished-state claims. No replacement description was requested or prepared.

## Scope decisions

The two reference implementations can round differently because their summation and scale-folding order differs; this change retains the client's existing Float8/BFloat8 tolerances. Exact driver comparisons are justified for the controlled test inputs, not as a promise of bitwise agreement for arbitrary GEMMs.

This layer changes CPU validation, not GPU kernels. The preceding input-scaling PR's device-qualification requirement remains separate. No production-code fix was omitted from the suggestion branch; the test-registration finding is implemented and validated.
