> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#14584](https://github.com/ROCm/rocm-systems/pull/14584)

Reviewed head: `285183b47df2` (one commit on `develop` at `e85f435eb190`).

Suggestion branch: `review/pr14584-suggestions` in the reviewer's fork, based on `285183b47df2`. The two commits are independent and can be cherry-picked separately.

| Commit | Item |
|---|---|
| [`cd85b997742`](https://github.com/ROCm/rocm-systems/commit/cd85b99774232e1170d7b37eba6f30a48a6b5848) | Actionable item 1: command-processor regression test |
| [`0b09c931f92`](https://github.com/ROCm/rocm-systems/commit/0b09c931f9235036c105c20530cb18e2c238b465) | Actionable item 2: primary-stall counter in the fuzz stats |

This review covers only points that the existing review threads do not raise. I agree with the open threads on fault-state sampling before peer-XCD notifications drain, the obsolete `older_work_may_remain` exemption, the regression preconditions, and the termination docs, and I don't repeat them here.

## Tests

On the submitted head, the 29 concurrent-dispatch and multiplexer fuzz tests and 29 focused simdojo termination and dispatch-fault unit tests pass. On the suggestion branch, 28 fuzz tests (after merging two duplicates) and 46 termination, command-processor, and fault unit tests pass. A random campaign over seeds 0–59999 produced one cross-mode report (suggestion 1).

## Summary

The PR adds `rj_concurrent_dispatch_fuzz` and registers it as multiplexer selector 3. The fuzzer runs input-carried kernels through an emulated AQL queue in serial, per-XCD-partition, and pooled CPU-dispatch modes. It gives a canonical atomic kernel an exact image oracle and checks arbitrary kernels with weaker cross-mode invariants. The PR also gives simdojo a typed `ExitCause` and makes finite runs stop consistently across worker modes when a primary is active but nothing is queued. Finally, a local dispatch fault now reschedules the command processor's doorbell.

Several choices are worth keeping:

- The exit cause is typed, so callers no longer match exit-message text.
- The tick-99 and tick-100 tests pin exactly where a finite run's stall becomes tick exhaustion.
- The bounded wave address space keeps raw kernels away from the AQL ring and the completion signal.
- The canonical suffixes are pinned to independently assembled LLVM encodings.

Serving modes force `max_ticks = 0`, so the interposer and daemon keep waiting for host doorbells.

## Actionable items

### 1. The command-processor change fixes an existing hang but has no direct test

`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:2753-2758` reschedules the doorbell after a local dispatch fault. This fixes a bug that already exists on `develop`. An internal queue releases its engine primary only from the doorbell handler (`:4976`). A fault that removes the last entry outside that handler leaves the primary registered, so a run with no tick limit never ends. The PR description doesn't mention this, which matters to anyone deciding whether the change is needed outside the fuzzer.

The fix is covered only indirectly. With the two lines removed, 7 of the 20 concurrent-dispatch fuzz tests fail, while no `rocjitsu_tests` case fails. Commit `cd85b997742` adds `CommandProcessorTest.DispatchFaultReleasesInternalQueuePrimary` to `tests/amdgpu_vm_test.cpp`. The test faults a running dispatch through the CU notification hook under `max_ticks = 10000` and `max_ticks = 0`, using a bounded step loop. It expects `ALL_PRIMARIES_COMPLETED`. Without the fix, the finite run reports `ACTIVE_PRIMARY_STALL` and the unlimited run never releases its primary.

### 2. Count primary stalls in `RunStats`

The fuzzer can detect a primary stall only through the exception in `validate_mode`. `RunStats` (`fuzz/concurrent_dispatch/concurrent_dispatch_fuzz_core.h:27`) has no stall count, so neither tests nor campaign JSON can observe stalls directly. The existing requests to assert "no primary stall" in the fault regressions need such a counter.

Commit `0b09c931f92` adds `primary_stalled_modes` to `RunStats`, the JSON output, and the CLI field check. It asserts zero stalls in the two fault tests and a stall in every mode in the halted-wave test, and it merges `TerminallyFaultedPacketDoesNotPublishCompletion` into the test that runs the same input.

### 3. The PR description needs a tracking reference

`therock-pr-bot` fails because the description has no `ISSUE ID:` or `JIRA ID:` line.

## Suggestions

### 1. Name LDS contents in the README's triage guidance

Seed 15358, on gfx1250, produces a cross-mode report. The kernel is the canonical prefix followed by `ds_consume v0` and `v_cmpx_le_i64 s[0:1], v[0:1]`, and then a FLAT load that either faults or lets the wave run into padding and fail decode. Which happens depends on the value `ds_consume` returns, most likely from LDS contents left by earlier workgroups on the same CU. Replacing that instruction with `v_mov_b32 v0, 0` makes 20 of 20 replays agree. The report reproduced on 16 and 18 of 20 replays, so the README's advice to replay repeatedly cannot separate it from a real defect.

`fuzz/concurrent_dispatch/README.md:68-72` names only shared global data as a source of scheduling dependence. Please add LDS and other on-chip state. The reproducer, as 64 hex-encoded bytes:

```text
0aea1dc9222a1366a4aabe5a24bb3067
0002007e0102027e8102047e7c400dec
00000801000000000000c9bf0000f4d8
000000000000a67d028008ec00000000
```

Incidentally, rocjitsu decodes the words `028008ec 00000000` plus the appended `s_endpgm` as `flat_load_d16_hi_i8 v0, v0, s[2:3]`, but LLVM 23 rejects that encoding for gfx1250.

### 2. Print exit reasons and causes by name

`describe_mode` (`concurrent_dispatch_fuzz_core.cpp:777`) prints `exit=1:1 cause=2`, and a failed `EXPECT_EQ` on `ExitCause` prints `1-byte object <04>`. A `to_string` for `ExitReason` and `ExitCause`, placed in `lib/simdojo/include/simdojo/sim/sim_types.h`, would make fuzz reports and test failures readable. simdojo has no naming helpers yet, so the API choice is left to the author.

## Commentary

A finite `max_ticks` now means something different. Drained finite runs report the last processed tick instead of `max_ticks`, so `rj_vm_run`'s `ticks_executed` is smaller than before. Finite multi-partition runs also no longer wait for publications from foreign threads. `rj_vm_run` and `rj_vm_step` still return `ROCJITSU_STATUS_SUCCESS` for an active-primary stall, and the C API cannot expose `ExitCause`. If C API callers need to tell unfinished work from finished work, that will need a separate addition; nothing in the tree depends on it today.
