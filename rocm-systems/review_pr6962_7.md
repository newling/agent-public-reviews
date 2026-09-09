> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#6962](https://github.com/ROCm/rocm-systems/pull/6962)

## Tests

Clang 23 Release configuration and the `rocjitsu_tests` target built successfully. The seven focused regressions covering post-batch CU refill, debugger pause/resume, one-thread exception behavior, live plugin replacement, and plugin callback serialization passed 7/7. `git diff --check` passed, and every visible non-skipped GitHub check is green, including Release, ASan/UBSan, GCC UBSan, TSan, pre-commit, and all three package builds.

## Summary

This comment-aware follow-up reviewed head `9a9ea84dd4cda08da1b8acd37a288787bc2f5650`. Its patch is byte-for-byte patch-equivalent to the pre-rebase fix commit identified in the discussion.

All four change requests from the September 2 review are implemented and directly tested: a completed pool batch refills newly idle CUs, debugger-paused waves quiesce without losing the resume wakeup, the one-thread pool path drains the batch before rethrowing, and `requires_serial_hot_hooks()` no longer clamps CU execution concurrency. The reviewer's final merge-blocking plugin concern is therefore resolved. I found no remaining correctness issue from that review that should block this PR.

The three latest discussion replies do not, however, literally address every request and suggestion from September 2. The reply about cross-command-processor serialization accurately explains why `run_mutex_` exists and agrees that a shared multi-producer pool is the right follow-up, but the requested source TODO was not added. The final reply acknowledges three deferred cleanups—queue advancement, unused scheduling state, and L2 inventory—but does not explicitly address the other non-blocking suggestions concerning plugin-to-pool lifecycle coupling, documentation of the host-acceleration boundary, or documentation of how engine partitions and dispatch threads compose. None of those omissions invalidates the core fix, but they remain follow-up/documentation work rather than completed items.

## Actionable items

None for correctness or merge readiness. The blocking findings from the prior review are resolved.

## Suggestions

### 1. Add the requested cross-command-processor serialization TODO

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/cpu_dispatch_pool.h:73,175-183`

`run_mutex_` still serializes complete submissions because task, result, counter, and exception state describe one global current batch. The latest discussion agrees that sparse work spread across several XCD-local command processors can underutilize the shared pool and that per-submission state in a multi-producer pool is the appropriate follow-up. Add the short TODO requested in the discussion next to `run_mutex_`, with the essential constraint that independent submissions need independent join, result, and exception state before the mutex can be relaxed.

### 2. Finish documenting the host scheduling contract in the controls PR

**Related PR/file:** `ROCm/rocm-systems#10074`, `emulation/rocjitsu/docs/configuration.md`

The core PR description now correctly says that serialized hot-hook callbacks do not reduce CU dispatch concurrency, but #6962 does not change the configuration documentation. The controls PR should state that the pool is host acceleration rather than modeled GPU hardware, that a functional quantum counts CU `step()` iterations rather than individual instructions, and that same-SoC command-processor submissions currently serialize through the shared pool. In particular, `num_threads` and `cpu_dispatch_threads` do not simply multiply into the effective same-SoC CU execution width.

### 3. Remove the residual plugin-to-pool lifecycle coupling in a cleanup

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/soc.cpp:83-110`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.h:214-220`

Replacing the plugin group still invokes `apply_dispatch_threads()` and reconstructs the SoC pool even though plugin capabilities no longer affect dispatch width. The command processor similarly reapplies an unchanged dispatch count. This is non-blocking, but removing those calls would complete the separation between callback locking policy and executor lifetime.

## Commentary

The author's deferral of queue-state consolidation, removal of unused scheduling fields, and canonical L2 inventory is reasonable for this already-large core PR. Those items were suggestions rather than conditions of acceptance. The current public review decision remains “changes requested” only because the reviewer has not yet submitted a replacement approval after the fixes; the code no longer reproduces the four findings that supported that review state.
