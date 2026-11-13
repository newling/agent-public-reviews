This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#9708](https://github.com/ROCm/rocm-libraries/pull/9708)

**Reviewed head:** `c2e1546802f900e2b7b14070721570380dcaa60b`. **Diff base / merge base:** `b81c8a355813716134ec5ae33c2d2935af865edc`. **Fetched develop inspected:** `f65195cf63c927df0025b35342ce99f3e9e70b1f`.

**Scope:** Second review, including all available earlier review bodies, inline comments and replies, discussion, and the [first review](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr9708.md). Rechecked all six changed source/test files, the occupancy and store-batching consumers, and all 285 tuning-file diffs. Kernel generation was sampled.

**Suggestion branch:** [review/pr9708-followup-20261113](https://github.com/newling/rocm-libraries/tree/review/pr9708-followup-20261113), based on the exact reviewed head. No new suggestion commits: the previous bounded cleanup is already included, and this review found no further code changes to implement.

## Tests

The submitted head built native rocISA and passed **259 tests, with 11 skipped**, across `test_occupancy.py`, `test_occupancy_buildtime.py`, `test_occupancy_hip.py`, and `test_custom_kernel_occupancy.py`. Eight skips require unavailable gfx9 hardware; three refer to an unavailable custom-kernel source. The CPU checks for the HIP writer fixture ran.

A comparison against the base calculation found identical register budgets and occupancy in **2,880 input combinations** across gfx9, gfx10, gfx1170/gfx1171, and gfx12, including both supported wave sizes. Eighteen checks with the real register allocator confirmed that gfx1100/gfx1150/gfx1151 preserve modeled occupancy up to the register budget and reject growth past it when that budget is below the addressable-register ceiling. Restoring the pre-follow-up calculation made all three new gfx10/gfx117x regression cases fail.

Five shipped kernels generated and assembled with AMD clang 23: gfx1100/gfx1150/gfx1151 wave32 and gfx1100/gfx1151 wave64. The initial assembly attempt used ROCm 7.1's clang 20, which rejected the existing `-Xclangas` option; using the newer compiler resolved this toolchain mismatch. The assembler wrapper is unchanged from the diff base.

All **285 YAML diffs contain only `MaxOccupancy` edits**, covering 3,158 changed values. Applicable root pre-commit checks and whitespace checks passed. Changed-file Python lint reports the same 119 diagnostics as the base, with no added or removed diagnostics.

No local gfx11 GPU execution or performance comparison was performed. The description's full 12,874-solution occupancy comparison was not independently reproduced.

## Summary

The occupancy model budgets vector registers using the physical capacity shared by waves, while the allocator limits each wave's register growth. Both ordinary stores and global split-U stores now use that same calculated budget. The follow-up keeps the behavioral occupancy change within the validated gfx11 targets; the earlier architecture-scope and capacity-duplication findings are closed.

The earlier comments have these dispositions:

| Earlier request | Status at the reviewed head |
| --- | --- |
| [Clarify wave32/wave64 capacity units](https://github.com/ROCm/rocm-libraries/pull/9708#discussion_r3631996848) | Addressed in [hardware_caps.hpp:704](https://github.com/ROCm/rocm-libraries/blob/c2e1546802f900e2b7b14070721570380dcaa60b/projects/hipblaslt/tensilelite/rocisa/rocisa/include/hardware_caps.hpp#L704). |
| [Fix gfx12 as well, or narrow the stated scope](https://github.com/ROCm/rocm-libraries/pull/9708#discussion_r4332185021) | The author chose the offered scope alternative. The description explicitly defers gfx12 and says the linked issue is only partially addressed. The local model comparison found no gfx12 change. |
| [Initialize the HIP test writer's wavefront size](https://github.com/ROCm/rocm-libraries/pull/9708#discussion_r4332185029) | Addressed. The writer carries `WavefrontSize`, and its CPU fixture checks execute the occupancy calculation without requiring the matching GPU. |
| [Use the modeled register budget at both pool-limit sites](https://github.com/ROCm/rocm-libraries/pull/9708#discussion_r4349431607) | Addressed through `setOccupancyLimits()`, called by `setOccupancy()` and the global split-U path. The real-allocator checks passed. |
| [Account for gfx10/gfx117x and remove duplicate capacity data](https://github.com/ROCm/rocm-libraries/pull/9708#pullrequestreview-5828649779) | Both addressed: legacy occupancy behavior is restored and regression-tested; the suggested capacity derivation and direct `<algorithm>` include are present. |
| [Add gfx11 cases to the HIP occupancy suite](https://github.com/ROCm/rocm-libraries/pull/9708#issuecomment-6326612020) | Still unimplemented. This was an optional validation suggestion; its remaining scope is described below. |
| Refresh reviews and revalidate after rebasing | The branch was rebased and its tuning values regenerated. This review supplies another assessment; it does not establish acceptance by the previously requested reviewers. A newer upstream import change remains to integrate, as noted below. |

## Actionable items

None in the reviewed code. The first review's architecture-scope item is resolved.

## Suggestions

No new suggestions.

## Scope decisions

Retaining the old gfx10/gfx117x/gfx12 models is a reasonable boundary for this gfx11 correction. Their existing estimation limitations remain; this review does not validate those legacy models against hardware.

The earlier optional gfx11 HIP-occupancy test remains useful follow-up work. The current fixture builds gfx9 wave64 kernels; extending it requires RDNA wave-size handling and accounting for the HIP-versus-LLVM allocation-granule differences reported in that discussion. I have not added unverified hardware expectations. The model regressions, reported earlier gfx1151 measurements, and current gfx110X client-test result provide evidence for this PR, while a maintained gfx11 hardware regression remains a coverage gap.

## Commentary

At the captured head, all four checks required by the repository rules passed: Math CI Summary, pre-commit, Multi-Arch CI Summary, and Component CI Summary. The [Windows gfx110X hipBLASLt tests](https://github.com/ROCm/rocm-libraries/actions/runs/43312929361/job/131561641123), [TensileLite coverage lane](https://github.com/ROCm/rocm-libraries/actions/runs/43312926222/job/131513593956), and [gfx1250-strict check](https://github.com/ROCm/rocm-libraries/actions/runs/43312925971/job/131513616264) passed.

The CI rollup is not entirely green. Both host-ASan jobs failed on `sanitizer_allocator_device.h:185`, comparing an allocator address against `0xaaaaaaaaaaaaaaaa`: [gfx950](https://github.com/ROCm/rocm-libraries/actions/runs/43312925981/job/131643673048) during `hipMemcpy` in the undersized-workspace test, and [gfx942](https://github.com/ROCm/rocm-libraries/actions/runs/43312925981/job/131643673085) during device-memory cleanup after the tests. Their summary and two codecov project checks failed; FFM gfx1250 reports `ACTION_REQUIRED`. These statuses are not required checks in the captured ruleset. The logs do not establish a cause attributable to this PR, and no base ASan reproduction was run here.

Fetched `develop` contains a newer migration of instruction imports in `KernelWriterAssembly.py` from `rocisa.instruction` to `.ir`. The component guidance requires rebasing and rerunning affected validation after overlap in this generator. Complete that integration step before merging; the suggestion branch intentionally remains at the reviewed head.
