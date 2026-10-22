This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13504](https://github.com/ROCm/rocm-libraries/pull/13504)

Reviewed head: [d62ad84b8c170aad1e7f68fa8bcba46944a5276a](https://github.com/ROCm/rocm-libraries/commit/d62ad84b8c170aad1e7f68fa8bcba46944a5276a). Comparison base: [b9bbd022c08ad7e30d00dc6c98e6e923d486d8a9](https://github.com/ROCm/rocm-libraries/commit/b9bbd022c08ad7e30d00dc6c98e6e923d486d8a9). Review date: 2026-10-22.

Suggestion branch: [review/pr13504-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr13504-suggestions), based on the reviewed head. The two published commits are independent.

| Commit | Review item |
| --- | --- |
| [03022a5d74e](https://github.com/newling/rocm-libraries/commit/03022a5d74edc2059a0bb3f457fd80d7bf48e215) | Run the generator boundary tests in shared CI and exercise the command-line path |
| [2bf8d8227df](https://github.com/newling/rocm-libraries/commit/2bf8d8227dfa496f6bb6eae86c85e76632cc9a31) | Update the architecture-testing documentation to match the workflow and byte limit |

## Tests

Submitted generator tests, full-corpus generation/comparison, and a compiled C++ Arguments/layout/filter probe pass; suggestion-branch generator tests, mutation checks, and full-diff root pre-commit checks pass.

Local validation covers serialization and filtering, without a full client/device build or GPU execution. The [strict hardware job](https://github.com/ROCm/rocm-libraries/actions/runs/39456105586/job/118743481625) builds this head from source, verifies `gfx1250-strict`, and passes its hipBLASLt and TensileLite runs. Math precheckin, Linux/Windows multi-architecture, and the dedicated ASAN job also pass. The complete check set is not green: [hipBLASLt project coverage](https://github.com/ROCm/rocm-libraries/runs/118811928636) reports 64.35% against an 80% target, and [FFM gfx1250](https://github.com/ROCm/rocm-libraries/runs/119492463655) reports 158 passes and eight timeouts. Those timeout fixtures are outside this diff; this review does not establish their cause.

The three newly enabled `matmul_fast_check_threshold_custom_kernel_ROCM31258` cases are a material coverage exception. The strict job skips them at [`matmul_gtest.cpp:293`](https://github.com/ROCm/rocm-libraries/blob/d62ad84b8c170aad1e7f68fa8bcba46944a5276a/projects/hipblaslt/clients/tests/src/matmul_gtest.cpp#L293), because stress cases require an explicit filter. They were not run locally either. To validate that group on gfx1250, use the matching client and device library with `hipblaslt-test --gtest_filter='*stress_matmul_fast_check_threshold_custom_kernel_ROCM31258*'`.

## Summary

This change admits existing matrix-multiplication tests on gfx1250 by widening their architecture expressions, including four grouped-GEMM exclusions that previously also excluded that device. It also enlarges the two architecture fields in the serialized test record and rejects strings that leave no space for a terminating zero byte.

The coordinated C++ and YAML layout changes are sound: all 117 field offsets and sizes agree, and records grow from 4,232 to 4,264 bytes. Comparing the complete generated corpus preserves the other argument values and known-bug platform sets. At this head, 35 YAML entries change and 749 additional records become architecture-eligible on both gfx1250 names; gfx942/gfx950 eligibility is unchanged. The other architecture expressions tested also preserve their previous behavior. These are eligibility counts, before runtime exclusions and known-bug filtering.

The length check uses encoded bytes and correctly rejects an exactly full array. I found no functional defect in that implementation or the changed filters. The main remaining issue is retaining automated regression coverage for the generator fix.

## Actionable items

### Run the generator boundary tests in shared CI and exercise the command-line path

At [`test_hipblaslt_gentest.py:15`](https://github.com/ROCm/rocm-libraries/blob/d62ad84b8c170aad1e7f68fa8bcba46944a5276a/projects/hipblaslt/clients/tests/test_hipblaslt_gentest.py#L15), all four tests call `char_array_bytes` directly, and no shared test runner invokes this file. Normal build-time generation uses only valid inputs, so it cannot detect loss of the rejection behavior.

For a concrete counterexample, replacing [`hipblaslt_gentest.py:356`](https://github.com/ROCm/rocm-libraries/blob/d62ad84b8c170aad1e7f68fa8bcba46944a5276a/projects/hipblaslt/clients/tests/hipblaslt_gentest.py#L356) with the former `arg.append(bytes(test[name], 'utf_8'))` leaves all four tests passing while the actual generator again accepts a 32-byte `gpu_arch` without a terminator. Changing the helper's comparison to count characters also leaves these tests green, despite accepting a 32-byte UTF-8 value made from 16 characters.

Commit [03022a5d74e](https://github.com/newling/rocm-libraries/commit/03022a5d74edc2059a0bb3f457fd80d7bf48e215) registers the suite in the existing shared pre-commit workflow using an isolated PyYAML dependency, and adds command-line tests using the real YAML schema. They cover empty strings, the last valid byte length, exactly full fields, and multibyte input. The new tests pass on the submitted implementation and fail for both counterexamples; they also catch changing `>=` to `>`. The hook was exercised locally through pre-commit. These regression sources are committed with the suggestion, so no temporary reproducer is needed.

## Suggestions

### Update the architecture-testing documentation to match the workflow and byte limit

The new row at [`TESTING.md:820`](https://github.com/ROCm/rocm-libraries/blob/d62ad84b8c170aad1e7f68fa8bcba46944a5276a/projects/hipblaslt/TESTING.md#L820) describes a manual-only gfx1250/gfx1250-strict lane. The [workflow in this same head](https://github.com/ROCm/rocm-libraries/blob/d62ad84b8c170aad1e7f68fa8bcba46944a5276a/.github/workflows/gfx1250_hipblaslt_tensilelite_test.yml#L24) also runs on eligible non-draft PRs and nightly on develop, and verifies strict mode. The row therefore understates automatic coverage and suggests ordinary gfx1250 is exercised by that lane too.

The new filtering explanation also calls the field limit 31 characters, although the implementation measures UTF-8 bytes. Its claim that any pattern containing `1250` matches both names is too broad: anchoring or a required suffix changes that result.

Commit [2bf8d8227df](https://github.com/newling/rocm-libraries/commit/2bf8d8227dfa496f6bb6eae86c85e76632cc9a31) documents the actual workflow triggers and strict target, states the byte limit, and describes the unanchored `|1250` alternative used by this patch. The workflow/source comparison and the C++ filter and UTF-8 tests support those corrections.

## Commentary

### Keep the proposed 32-byte architecture fields

The two fields, `gpu_arch` and `gpu_arch_exclude`, occupy their full capacity in every generated test record, even when their text is short. The [reader loads each complete record](https://github.com/ROCm/rocm-libraries/blob/d62ad84b8c170aad1e7f68fa8bcba46944a5276a/projects/hipblaslt/clients/common/src/hipblaslt_arguments.cpp#L206), so extra capacity increases file size and the bytes read and copied during test setup.

| Capacity of each field | Complete record | Growth over 16-byte fields | Extra data across 143,206 records |
| --- | ---: | ---: | ---: |
| 16 bytes | 4,232 bytes | — | — |
| 32 bytes | 4,264 bytes | 0.76% | 4.37 MiB |
| 64 bytes | 4,328 bytes | 2.27% | 13.11 MiB |
| 128 bytes | 4,456 bytes | 5.29% | 30.59 MiB |

The proposed 32 bytes fit the current patterns and keep this repeated storage cost small. Moving from 16 to 64 would add three times as much data as moving from 16 to 32, without a demonstrated need for that capacity. This supports keeping 32. These are calculated storage costs; startup time was not benchmarked, so they do not establish a noticeable slowdown. GPU calculations do not use these fields, and matching a GPU name examines the actual text rather than the unused capacity.

Using `std::string` would require changing how records are written and read. A string object contains bookkeeping and may point to separately allocated text, so Python cannot write its bytes into the current fixed record for C++ to load directly. An explicit string encoding and reconstruction step could support it, but that is a broader change than these architecture patterns require.

### Validation scope

CPU tests are the appropriate level for the string boundary and serialized layout. The existing hardware tests are appropriate for the expanded architecture selection; no production feature flag is needed. The benchmark's YAML path consumes the same generator and Arguments format, which is why testing actual command-line generation matters. No TensileLite code-generation behavior changes here, so additional local code-generation suites would not address the generator-test gap.

The suggestion branch contains only the two mapped commits. The stress group's hardware execution, FFM timeout diagnosis, and coverage-threshold investigation remain outside this local review. No review was posted to the PR and its description was not changed.
