This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#9470](https://github.com/ROCm/rocm-systems/pull/9470)

**Revision reviewed:** local revival candidate `d20e3a461a`, one commit based directly on `origin/develop@1c1419a943`.

**Review mode:** fresh review of the rebased, policy-only revival. I did not read the closed PR's existing GitHub review threads or comments. The repository, original PR, base branch, and surviving fork branch are public; the reviewed rebased commit has not been published.

## Tests

The focused Release/Ninja build passed for `rocjitsu_tests`, `rocjitsu_plugin_race_so`, and the gfx950 HIP race binary; 103/103 race-detector and scalar plugin-path tests and 39/39 gfx950 race integration tests passed, as did changed-file pre-commit and `git diff --check`.

The generated gfx950 code preserves the intended instruction boundaries: the safe load-to-move and load-to-load kernels contain an intervening `s_waitcnt lgkmcnt(0)`, while their `_race` counterparts contain the conflicting `s_mov_b32` or second `s_load_dword` before the wait.

Two temporary core probes also passed and were removed: a two-dword scalar read reported one finding for one pending wide event, while a two-dword write reported both distinct pending events spanning its range.

The closed PR's GitHub checks apply to its obsolete seven-commit head, not this unpublished revival candidate, so fresh CI will still be required after publication.

## Summary

The revived change adds the missing scalar-register write-after-write policy to the race detector without reviving the obsolete register-access implementation from the original PR.

The data flow is now narrow and coherent:

1. Merged register-access infrastructure emits one typed `onAmdgpuWriteScalarRegister` callback before an instruction modifies an SGPR or TTMP.
2. A routed scalar load records its typed SGPR or TTMP destination as an outstanding memory event.
3. `checkScalarAccess` compares a later scalar read or write with those pending events. A wide access is deduplicated by event, while distinct pending events are preserved.
4. `registerScalarLoad` performs the same write check before adding the new event, which detects scalar-load-over-scalar-load WAW hazards.
5. Existing wait-counter retirement removes completed destinations, so the same accesses become clean after the appropriate zero wait.

This is the right decomposition. The original seven-commit PR combined detector policy with callback ownership, generated ISA changes, plugin infrastructure, and mixed-wait handling. Those lower layers now live in `develop` through the merged register-access work. The revival is therefore one focused ten-file commit: detector policy, its plugin adapter, documentation, and tests.

The implementation handles the important contract boundaries directly: SGPR and TTMP identity remain distinct, invalid register ranges remain inert, raw memory-completion writes remain unobserved, wide accesses do not duplicate one pending event, and multiple genuinely distinct pending events are not collapsed.

The HIP tests conform to the current race-test design. Expectations live beside the protected kernels, positive cases use structured `RaceExpectation` values and `ExpectRace`, negative cases use `ExpectNoRace`, CTest names follow the safe/`_race` pairing convention, and the shared parser continues to fail closed on absent or malformed output. Both new behaviors now have a safe/racy boundary: load-to-instruction-write and load-to-load.

I found no correctness issue that should block reopening or publication of this rebased candidate.

## Actionable items

None.

## Suggestions

### 1. Pin the read side of wide scalar-event deduplication

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp:302-345`
- `emulation/rocjitsu/tests/race-detector/race_detector_tests.cpp:233-366`

The new shared `checkScalarAccess` helper deduplicates both reads and writes by pending event. Permanent tests directly cover wide-write deduplication, wide load-over-load deduplication, and preservation of distinct events, but none directly pins the changed wide-read cardinality.

Add a small core test with one pending two-dword scalar load followed by a two-dword scalar read, asserting exactly one violation referring to the original event. The temporary version of that test passed. This is not a correctness problem in the current implementation, but it would make the shared helper's full contract explicit.

## Commentary

### Big picture

This feature is the scalar analogue of the existing VGPR WAW detector. It catches an architectural write that can be overwritten later by an older asynchronous scalar-memory result. It also covers two scalar loads targeting the same destination because scalar-memory results are not guaranteed to complete in issue order.

The feature depends on, but no longer duplicates, the merged wave-owned register-access layer. It also reuses the existing typed wait-counter model rather than changing wait semantics. That makes the branch substantially easier to reason about and review than the original closed stack.

The open counter-capacity work is conceptually orthogonal: it governs when hardware backpressure proves events complete, while this change governs what happens when a still-pending scalar destination is written again. Both touch race-state tests and retirement code, so whichever lands second should be rebased and rerun against the first.

### Scope boundaries

The supported scalar spaces are ordinary SGPRs and TTMPs. The change does not claim WAW coverage for VCC, EXEC, M0, FLAT_SCRATCH, architecture-specific XNACK-mask selectors, asynchronous VGPR-writer pairs, or LDS WAW. Those remain separate modeling problems.

### Reopening hygiene

The current GitHub description still explains the historical seven-commit stack and presents mixed-`LGKMCNT`, callback ownership, and generated-code work as part of this PR. Before reopening, rewrite it around the one-commit policy layer, state that the register-access and wait-counter foundations are already in `develop`, update the test counts, and remove claims about files no longer changed by the revival.
