This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12960](https://github.com/ROCm/rocm-libraries/pull/12960)

**Reviewed head:** [`8351692d684bd9a3ad55b6d0e44a8fae913aedc1`](https://github.com/ROCm/rocm-libraries/commit/8351692d684bd9a3ad55b6d0e44a8fae913aedc1) (2026-10-06), compared with #12876. Public repository and head; existing reviews/comments were not consulted.

**Published suggestion branch:** [`review/pr12960-suggestions-20261006`](https://github.com/newling/rocm-libraries/tree/review/pr12960-suggestions-20261006), based on that exact head. Commit [`81db14636ea`](https://github.com/newling/rocm-libraries/commit/81db14636ea8f61a3291b59e0d0a5cd1d288c591) implements the workspace cleanup item below.

## Tests

Built the submitted checker and passed all 35 host/device self-tests on gfx1201 with ROCm 7.1, including actual virtual-memory placement and injected dropped-carry accesses. The modified matmul header compiles in both benchmark and GOOGLE_TEST configurations; whitespace checks pass.

Full GEMM solution sweeps and gfx1250 execution were not repeated locally. At the October 6 refresh, Math CI, multi-architecture and replacement ASAN build/test checks pass. The earlier ASAN failure occurred while fetching DVC inputs, before configuration/compilation, as recorded in the preserved root review. Old cancelled duplicates remain visible, and hipBLASLt project coverage is still failed; that coverage result needs attribution before landing.

## Summary

This makes an address-boundary defect reproducible using small allocations: map the operand across a 4 GiB boundary and map poison where an uncarried access would land. Mapping ownership tracks partial construction, and the changed move operations transfer the buffer pointer rather than leaving a moved-from object to inspect memory it no longer owns. Direct tests exercise dropped-carry reads/writes, mapped-tail corruption and vector growth.

The workspace subrange calculation accounts for the full workspace size supplied to a solution, not just the heuristic's reported requirement. That is an important contract to retain.

## Actionable items

### Release workspace when placement skips or fails

At `projects/hipblaslt/clients/common/include/testing_matmul.hpp:5114`, `dWorkspace` is allocated before the new `CHECK_PLACEMENT` at line 5143 can return. If no selected solution needs workspace, or placement fails, the final delete at lines 6709–6710 is bypassed. The zero-length device vector still owns a host object and, in GOOGLE_TEST mode, guard storage. Repeated skipped tests retain those resources.

Commit [`81db14636ea`](https://github.com/newling/rocm-libraries/commit/81db14636ea8f61a3291b59e0d0a5cd1d288c591) gives `dWorkspace` a `std::unique_ptr`, constructs it with `make_unique` and removes the manual delete. Existing dereferences, including timing paths, are preserved. This fixes the new workspace lifetime issue without refactoring all of the function's older raw stream/event/descriptor ownership. Validation was control-flow inspection plus compilation of both consumers; no test merely restating standard smart-pointer destruction was added.

## Suggestions

No additional source suggestion. Preserve the explicit unsupported-platform skip and invalid-request failure distinction.

## Commentary

The new behavior is opt-in client tooling. Device helper tests establish the VMM and poison contract; representative client GEMMs establish pointer wiring. The broader existing client lane matters because the move fix also affects ordinary buffers. Direct tests and the placement flag cover the new behavior without an omitted-test waiver. The motivating gfx1250 MX kernel remains outside this layer's local coverage.

The published branch contains the one commit linked above. The original PR has not been changed.
