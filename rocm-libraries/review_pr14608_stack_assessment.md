> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14608](https://github.com/ROCm/rocm-libraries/pull/14608), [#14609](https://github.com/ROCm/rocm-libraries/pull/14609), and [#14610](https://github.com/ROCm/rocm-libraries/pull/14610).

Reviewed heads, checked on 2026-11-02: #14608 `e738f6100ce`, #14609 `b7648aa97dc`, and #14610 `876b837dbc4`.

Accompanying branches contain the proposed fixes, each based on the corresponding PR head:

| Branch | Base | Commits |
| --- | --- | --- |
| [review/pr14609-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14609-suggestions) | `b7648aa97dc` | [e8a05bf78ac](https://github.com/newling/rocm-libraries/commit/e8a05bf78acfc412b251009a3b4733189ed03d58) (zero versus unavailable memory), followed by [5b2051dd795](https://github.com/newling/rocm-libraries/commit/5b2051dd795438162e70e3b372f13e24a9f49456) (host-memory test environment) |
| [review/pr14610-memory-fixes](https://github.com/newling/rocm-libraries/tree/review/pr14610-memory-fixes) | `876b837dbc4` | [3afe2cb098f](https://github.com/newling/rocm-libraries/commit/3afe2cb098f50889560e40f2d3f0accb216b1d20) (matmul test environment) |

The swizzle allocation checks and their regression test are not yet implemented on a review branch.

## Tests

This revision uses source inspection and the existing validation logs; no tests were rerun for the wording update. The saved submitted-head run with `HIPBLASLT_CLIENT_HOST_MEMORY_LIMIT=4G` shows four failing host-memory tests; the corresponding combined-review run passes all 19. The saved matmul-memory run passes both tests. The earlier intermittent failure in `FastCheckDevice_pre_checkin.placed_workspace_straddles_for_every_size` remains unresolved.

## Summary

Overall, I’m happy with the direction of this stack. It addresses an immediate issue, and the requests below are small, local fixes and improvements. Controlling idle pinned memory, respecting the container’s remaining memory, and checking a whole case before allocation each address part of the problem. The consistent memory-skip reporting also makes lost test coverage visible.

The submitted retention policy has performance evidence behind it. I’m happy to keep that approach while addressing the defects below; a broader revisit of allocation and caching belongs in follow-up work.

## Actionable items

### Preserve the environment across the memory tests

In `projects/hipblaslt/clients/tests/src/host_memory_gtest.cpp:306` and `projects/hipblaslt/clients/tests/src/matmul_gtest.cpp:381`, the scope helpers unset their variables on destruction instead of restoring the previous values. This can remove the run's memory budget, its requirement to fail on memory skips, or its estimate-check setting. The fake-host queries also inherit an external limit and therefore produce false failures. Restore the previous values and isolate the fake-host queries from the caller’s environment, as in `5b2051dd795` and `3afe2cb098f`. Verify preservation with the variables preset.

### Distinguish zero available memory from an unavailable query

`projects/hipblaslt/clients/common/src/host_memory.cpp:168` returns zero for both states. At `projects/hipblaslt/clients/common/src/fast_check.cpp:2007`, zero bypasses the preflight; at `projects/hipblaslt/clients/common/include/d_vector.hpp:90`, it produces a misleading query-error message and prevents a fresh pinned allocation. For example, under `HIPBLASLT_CLIENT_HOST_MEMORY_LIMIT=0`, the preflight permits a case with a positive host-memory requirement. Use an explicit unavailable result, as in `e8a05bf78ac`, so a known zero budget makes the preflight skip and only an unreadable query produces the query-error message.

### Check the swizzle temporary allocations

At `projects/hipblaslt/clients/common/include/testing_matmul.hpp:3657`, `3665`, `4144`, and `4152` on the stack head, a temporary `HipHostBuffer` is used without checking allocation success. `swizzle_tensor` ultimately copies into that pointer at line 400. A failed allocation can still reach a null destination after the new main-buffer check has succeeded. Extend the allocation-failure handling to these four sites and add a focused failure-path test. This completes the handling of the same failure mode #14608 addresses.

## Suggestions

Document in `projects/hipblaslt/clients/common/include/host_memory.hpp:25` and `projects/hipblaslt/TESTING.md:346` that `HIPBLASLT_CLIENT_HOST_MEMORY_LIMIT` caps the query/preflight budget. It is not a cumulative process-memory limit or a reservation shared between processes. Clarifying that meaning is sufficient for this stack.

## Commentary

Which gfx1250 hardware run validates this stack’s large-memory behavior, and is its success required for merge? The [hardware workflow](https://github.com/ROCm/rocm-libraries/blob/develop/.github/workflows/gfx1250_hipblaslt_tensilelite_test.yml) is configured to run automatically for eligible non-draft PRs with relevant changes and an accepted organization label. #14608 already has `organization: ROCm`; this workflow needs no additional GPU opt-in label. The dedicated hardware job is not among the required checks reported by `gh pr checks 14608 --required` on 2026-11-02. The ordinary gfx1250 multi-architecture build alone does not establish hardware test coverage.

The hardware workflow still runs the large cases under the existing host-wide lock, and #14610’s description says the several-process container run is pending. Passing under the current scheduling protection would validate that configuration. Removing the lock or increasing concurrency needs separate evidence, since a free-memory check does not reserve memory against another process.

For follow-up CI coverage, the estimate check would be useful on representative large and swizzled cases. In `projects/hipblaslt/clients/common/include/memory_estimate_check.hpp:59`, it clears the host pool before measuring, so assess the runtime cost in a diagnostic or periodic run before enabling it routinely.

Separately, I’d like a deeper revisit of host-memory allocation and caching in this part of the client, including where pinning and buffer reuse are worthwhile and how allocation and estimation can share more of their logic. That is follow-up work. A later simplification should preserve container awareness and be assessed against representative runtime, peak-memory, and test-coverage measurements; it is not a request to redesign this stack.
