This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#16040](https://github.com/ROCm/rocm-libraries/pull/16040)

Reviewed head: `ccfc7f7e6e753b07b7f81981003052b6e4fbc372`. Base: `1a117bfbedf573f7b519592fe3f6f771a1709bd5`, the head of prerequisite [#16037](https://github.com/ROCm/rocm-libraries/pull/16037). Independent review of all four changed files: the test-policy header, two native-test files, and testing guide. Allocation/preflight callers and the prerequisite's allocation-outcome handling were inspected where they interact with this change.

Suggestion branch: [review/pr16040-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr16040-suggestions), based on the reviewed head, ending at [5f351d6faa8](https://github.com/newling/rocm-libraries/commit/5f351d6faa8cae381feba15cf1aef142cde470f3). The two optional items below map to its two commits.

## Tests

Both the submitted and suggestion trees built `hipblaslt-test` and `hipblaslt-bench` with AMD Clang 20, ROCm 7.1, and device-library generation disabled. On Linux/gfx1201, all 155 selected tests passed without skips on each tree, including all four additions. The filter was:

```text
HostMemory_pre_checkin.*:MatmulMemory_pre_checkin.preflight_stops*:MatmulMemory_pre_checkin.failed_allocation*:*HostUnit*
```

A separate native probe against the submitted header passed all 36 combinations of preflight/host/device stops, smoke/nightly categories, and six environment settings. It checked fatal versus skipped results, the diagnostic prefix, early return, and destruction of local objects. Compiling the three submitted policy tests with the preflight rule removed failed `preflight_stop_skips_by_default`; disabling category matching failed `allocation_stop_fails_the_tests_the_pr_tiers_run`.

Root and component pre-commit completed successfully, as did whitespace checks. The root formatting hooks exclude hipBLASLt; Clang-format 18.1.4 separately found no changes needed on the suggestion lines.

At review time on November 18, 2026, the [gfx1250 job](https://github.com/ROCm/rocm-libraries/actions/runs/44196339563/job/134438860835) passed, and its log records each of the four added tests running and passing. Dedicated gfx942/gfx950 ASAN jobs and Math CI report success. The Multi-Arch workflows for that head skipped their build/test lanes. [Codecov](https://app.codecov.io/gh/ROCm/rocm-libraries/pull/16040) reports project coverage of 71.14% against 80%; its patch check reports coverage unaffected.

Local validation did not execute GEMM kernels, the host-estimate accuracy test, or Windows/ASAN builds. The architecture-independent policy and native macro behavior are covered locally; hardware-suite evidence comes from the existing CI runs.

## Summary

The change puts the failure policy at the common allocation checks, so ordinary test callers receive the new default without individual edits. Both preflight call sites retain their separate skip policy. The full test name is matched using the same loose substrings as the CI category filters, and explicit nonempty environment settings take precedence over both defaults. The non-GTest benchmark path is unchanged.

The native policy tests distinguish the intended behavior, and the impossible-host-allocation test exercises the actual buffer outcome through `CHECK_HOST_ALLOCATION`. These are appropriate tests for a reporting-policy change; the existing preflight tests and memory-pool tests cover the adjacent paths. Tests and an explicit override are both present. No actionable correctness finding was identified.

## Actionable items

None.

## Suggestions

1. **Document the empty setting explicitly.** At `projects/hipblaslt/TESTING.md:366`, “any other value” appears to include an empty value, but an empty value selects the category/preflight defaults. State that unset and empty use the defaults, `0` always skips, and any other nonempty value always fails. Implemented in [ebf229a610c](https://github.com/newling/rocm-libraries/commit/ebf229a610c286de14a731ddb1732cf06c1e2bce).

2. **Make the new dependencies and loop diagnostics explicit.** The new braced-list loops in `clients/common/include/hipblaslt_test.hpp:89` and `clients/tests/src/host_memory_gtest.cpp:292` should directly include `<initializer_list>`. The new `HipHostBuffer` use in `clients/tests/src/matmul_gtest.cpp:671` should directly include `hipBuffer.hpp`. Add `SCOPED_TRACE(preflight)` to the override loop so a failed assertion identifies which stop kind failed. These paths are relative to `projects/hipblaslt`; the observations are optional code-quality improvements, not demonstrated build failures. Implemented in [5f351d6faa8](https://github.com/newling/rocm-libraries/commit/5f351d6faa8cae381feba15cf1aef142cde470f3).

## Scope decisions

A passed preflight does not reserve memory. Another process can consume the remaining budget and cause a later allocation to fail the test. That is the explicit policy choice described by this PR, and it is retained. `HIPBLASLT_TEST_FAIL_ON_MEMORY_SKIP=0` remains the escape hatch for a lane that needs memory stops to skip. No reservation or cross-process scheduling mechanism was added to the suggestions.

The suggestion branch contains the documentation correction followed by the include/diagnostic cleanup. Both are optional, both are validated, and no identified required fix remains unimplemented. [Compare both suggestions with the reviewed head](https://github.com/newling/rocm-libraries/compare/ccfc7f7e6e753b07b7f81981003052b6e4fbc372...5f351d6faa8cae381feba15cf1aef142cde470f3).
