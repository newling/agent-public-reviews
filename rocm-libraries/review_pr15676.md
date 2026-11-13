This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15676](https://github.com/ROCm/rocm-libraries/pull/15676)

**Reviewed head:** `df06b32ac4594db4bf05dcece343c33b66320d54` (merge base with `develop`: `4a8020a4df1db472f755dd67d36f3967db3898e0`). Independent review of the whole change; existing PR discussion was not read.

**Suggestion branch:** [review/pr15676-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15676-suggestions), based on the reviewed head.

| Commit | Item |
|---|---|
| [`44cd59afae3`](https://github.com/newling/rocm-libraries/commit/44cd59afae3b75d4efc3c28e44ea464a6ebe0749) | [Name the failing public function in the log line](#name-the-failing-public-function-in-the-log-line) |
| [`fafe8211a63`](https://github.com/newling/rocm-libraries/commit/fafe8211a63bc28edee50514511f5f9dd5f424f0) | [Log the exceptions that the extension-API Tensile helpers swallow](#log-the-exceptions-that-the-extension-api-tensile-helpers-swallow) |

## Tests

Built `hipblaslt-test-hostunit` (Release, host-only library, ROCm `amdclang++`) at the reviewed head and at the suggestion branch. Both pass all 124 HostUnit tests, including the new `HostUnitExceptionLoggingDeathTest.smoke_ExceptionMessageIsLogged`. The new test also passes with GPUs hidden (`HIP_VISIBLE_DEVICES=-1`), as the CPU-only lane would run it. That covers the two unchecked items in the description's testing checklist: with the `log_error` call removed from `exceptions.hpp` and the library rebuilt, the test fails with the expected regex unmatched and empty child output. CI was still running at the time of review, with no failures reported.

## Summary

Every public C entry point and the extension-API methods end in `catch(...) { return exception_to_hipblas_status(); }`, so logging `what()` in that one handler covers all of them without touching call sites. The returned statuses are unchanged, and the cost when logging is off is one load of the logger's layer mask. The `noexcept` wrapper around the log call is needed rather than defensive: the handler is a function-try-block, and an exception thrown from one of its `catch` clauses would leave `exception_to_hipblas_status` and then escape the `extern "C"` function through the caller's `catch(...)`. The test uses a real production path (the `HIPBLASLT_OVERRIDE_COMPUTE_TYPE_XF32` parse in `hipblasLtMatmulDescCreate`) instead of a test-only hook, and runs in a re-executed child because the logger reads its environment once per process.

## Actionable items

None.

## Suggestions

### Name the failing public function in the log line

At [exceptions.hpp:40](https://github.com/ROCm/rocm-libraries/blob/df06b32ac4594db4bf05dcece343c33b66320d54/projects/hipblaslt/library/src/amd_detail/include/exceptions.hpp#L40), the logger's `func` argument is the literal `"exception_to_hipblas_status"`. The logger prints that argument as the caller field of its prefix, so every logged failure looks like this:

```text
[2026-11-13 12:49:49][HIPBLASLT][<pid>][Error][exception_to_hipblas_status] exception=stoi
```

At `HIPBLASLT_LOG_LEVEL=1` there is no API trace beside it, so the line gives the reason but not which call failed. Commit [`44cd59afae3`](https://github.com/newling/rocm-libraries/commit/44cd59afae3b75d4efc3c28e44ea464a6ebe0749) adds a trailing parameter `const char* func = __builtin_FUNCTION()` to `exception_to_hipblas_status` and passes it to the logger. The default is evaluated at each call site, so none of the existing `exception_to_hipblas_status()` calls change, and the same failure now logs as:

```text
[...][Error][hipblasLtMatmulDescCreate] exception=stoi
```

The extension-API sites in `hipblaslt-ext.cpp` report the unqualified method name (for example `initialize` or `run`), which still identifies the call. `__builtin_FUNCTION()` is supported by Clang and GCC; `std::source_location` would have given Clang's full decorated signature instead. The commit also tightens the test regex to `\[hipblasLtMatmulDescCreate\] exception=.*stoi` and updates the CHANGELOG wording.

### Log the exceptions that the extension-API Tensile helpers swallow

Five functions in `tensile_host.cpp` catch every exception with empty handlers and return `rocblaslt_status_internal_error`: `gemmCreate` ([6656](https://github.com/ROCm/rocm-libraries/blob/df06b32ac4594db4bf05dcece343c33b66320d54/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L6656)), `groupedGemmCreate` ([6745](https://github.com/ROCm/rocm-libraries/blob/df06b32ac4594db4bf05dcece343c33b66320d54/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L6745)), `runKernelFromInvocation` ([7212](https://github.com/ROCm/rocm-libraries/blob/df06b32ac4594db4bf05dcece343c33b66320d54/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L7212)), `getDeviceUserArgumentsValuesFromContractionProblem` ([7265](https://github.com/ROCm/rocm-libraries/blob/df06b32ac4594db4bf05dcece343c33b66320d54/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L7265)) and `runKernelFromNewDeviceUserArguments` ([7379](https://github.com/ROCm/rocm-libraries/blob/df06b32ac4594db4bf05dcece343c33b66320d54/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L7379)). They back the extension API's `setProblem`, grouped-GEMM creation, `run` and default user arguments. Because the exception never reaches `exception_to_hipblas_status()`, these calls still return internal error without any message after this PR, which is the problem the PR sets out to fix. Expected rejections in these functions return a status without throwing, so only abnormal failures would be logged.

Commit [`fafe8211a63`](https://github.com/newling/rocm-libraries/commit/fafe8211a63bc28edee50514511f5f9dd5f424f0) adds `log_error(__func__, e.what())` and `log_error(__func__, "unknown exception")` to those handlers, matching what `runContractionProblem` and `getBestSolutions` in the same file already do. It has no dedicated test; making one of these helpers throw from a host-only test would need a test hook, which this small change doesn't justify. If the author prefers to keep this PR to the single handler named in the issue, this commit can become a short follow-up instead.

## Commentary

`exception_to_rocblaslt_status()` in `rocblaslt/src/include/utility.hpp` has no callers, so it doesn't need the same logging; it could be deleted separately. The `catch(...)` branch for non-`std::exception` values still returns internal error without logging. The non-standard values thrown in hipBLASLt's library sources (`hipblasStatus_t`, and `rocblaslt_status` in `rocblaslt_matmul_desc_create`) are already caught before reaching it. #15593 is still open, so its one-off `TENSILE_DB` print can only be dropped from whichever of the two PRs lands second.
