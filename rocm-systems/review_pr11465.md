This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#11465](https://github.com/ROCm/rocm-systems/pull/11465)

**Revision reviewed:** rebased candidate `36cbaea271`, stacked on the rebased #11473 candidate `b00b53553b`.

**Review mode:** independent review followed by evaluation of the live review discussion.

## Tests

The isolated `rocjitsu_tests` target built successfully; 186 focused execution-plugin and race-detector tests passed, as did all 6 new gfx950 generic-FLAT integration cases and the changed-file hooks. Two temporary counterexamples exposed the issues below: the out-of-range VGPR case terminated with signal 139, and both same-wave unordered FLAT-to-LDS cases produced no race. The probes were removed after validation.

## Summary

The central design is good. A generic FLAT operation now retains both counter obligations independently of the emulator pipeline selected from its resolved address. The memory pipeline increments and releases the pair together, while the race detector records satisfaction of each obligation separately. The revised partial-wait algorithm also correctly separates counter membership from FIFO completion classes, so an unordered scalar or generic-FLAT event is not guessed complete from a nonzero threshold.

Moving the routing callback after shared-aperture translation is also the right boundary: plugins see the actual memory space and translated LDS addresses, while decoded counter obligations remain unchanged. Unit tests and real gfx950 kernels cover both routes and each one-counter-only negative case.

Two correctness gaps remain in the integration. One can crash the host on an out-of-range multi-register destination; the other makes the newly introduced `UNORDERED` contract ineffective for same-wave LDS address hazards.

## Actionable items

### Validate the complete VGPR destination before the WAW loop

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp:365-376`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp:299-301`

The new route-time WAW loop calls `checkVgprWrite(logicalBase + i, ...)` before `registerEventWithIntervals()` performs its existing full-span bounds check. A two-register load beginning at the final allocated VGPR therefore indexes `vgprMemoryEvents` one past the end. The minimal probe in Appendix A terminates with signal 139 in the normal optimized test build.

Validate `logicalBase` plus `d.num_elems` against the wave's tracked VGPR count before entering either new WAW loop. Prefer one shared full-span predicate used by both the pre-check and registration so those paths cannot drift. An invalid destination should produce neither a WAW lookup nor an event, matching the later pipeline writeback guard.

This is the same defect identified in the existing unresolved inline review comment; the local reproducer confirms it.

### Apply completion ordering to same-wave LDS address hazards

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp:87-96`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp:119-126`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/plugin.cpp:303-315`

Generic FLAT operations routed to LDS are registered as `LDS_TO_VGPR` or `VGPR_TO_LDS`, but retain `MemoryOrderClass::UNORDERED`. The LDS overlap checks ignore that class: `validateRead()` exempts every same-wave `VGPR_TO_LDS` event, and `validateWrite()` exempts every same-wave LDS-read event. Consequently, the two Appendix B sequences report no race even though the PR's own metadata says the pending operation cannot use the ordinary LDS FIFO guarantee.

Pass the current operation's completion class into the LDS read/write validation and suppress a same-wave conflict only when the pending and current operations share the same non-`UNORDERED` class, or represent routed generic FLAT with a distinct event type and an equivalent rule. Preserve the existing exemption for an event already made `WAVE_COMPLETE` by its waits. Cover both directions and both orderings: generic pending versus ordinary current, and ordinary pending versus generic current.

If the intended architectural model is instead that a generic FLAT operation regains LDS FIFO ordering once its route is known, encode that route-specific transition explicitly and update the metadata contract. The current mixture—`UNORDERED` for register hazards but ordinary-DS treatment for LDS addresses—is internally inconsistent.

## Suggestions

None.

## Commentary

The live PR has one approval and one unresolved inline thread. The thread reports the out-of-range VGPR issue above and is correct. No existing comment mentions the same-wave LDS-ordering mismatch.

The published CI jobs are green, but they exercise the old remote head and neither boundary case is represented in the submitted tests. The rebased local patch is otherwise commit-for-commit equivalent to the published #11465 layer.

## Appendix A: out-of-range load destination reaches the WAW lookup

Add this to `race_detector_tests.cpp`:

```cpp
TEST(RaceDetector, RejectsOutOfRangeMultiRegisterLoadBeforeWawCheck) {
  RaceTestBuilder b(/*numWaves=*/1, /*vgprs=*/8, /*sgprs=*/8);
  b.globalLoad(/*wave=*/0, /*vgprBase=*/7, /*numRegs=*/2);
  EXPECT_FALSE(b.hasRace());
}
```

The call reaches `checkVgprWrite(8, ...)`, and iterating `vgprMemoryEvents[8]` is out of bounds.

## Appendix B: unordered routed-FLAT events bypass same-wave LDS checks

The load direction uses the helper already present in the PR:

```cpp
TEST(RaceDetector, UnorderedFlatLdsLoadConflictsWithSameWaveLdsWrite) {
  RaceTestBuilder b(/*numWaves=*/1, /*vgprs=*/8, /*sgprs=*/8);
  b.flatLdsLoad(/*wave=*/0, /*lane=*/0, /*addr=*/0, /*bytes=*/4, /*vgprDst=*/1);

  b.checkLdsWrite(/*wave=*/0, /*lane=*/0, /*addr=*/0, /*bytes=*/4);

  EXPECT_TRUE(b.hasLdsRace(0));
}
```

For the store direction, add this sibling helper to `RaceTestBuilder`:

```cpp
void flatLdsStore(int wave, int lane, int addr, int bytes) {
  detector_->validateWrite(addr, WaveId{wave}, lane, bytes);
  std::vector<uint32_t> ldsAddrs(waveSize_, 0);
  ldsAddrs[lane] = addr;
  const uint64_t laneMask = 1ULL << lane;
  waves_[wave]->registerLdsEvent(
      pc_++, MemoryEventType::VGPR_TO_LDS, /*registers=*/{}, laneMask, waveSize_, ldsAddrs,
      bytes, /*byteMask=*/0xF, amdgpu::WaitCounterType::VMCNT,
      MemoryOrderClass::UNORDERED, amdgpu::WaitCounterType::LGKMCNT);
}
```

Then add:

```cpp
TEST(RaceDetector, UnorderedFlatLdsStoreConflictsWithSameWaveLdsRead) {
  RaceTestBuilder b(/*numWaves=*/1, /*vgprs=*/8, /*sgprs=*/8);
  b.flatLdsStore(/*wave=*/0, /*lane=*/0, /*addr=*/0, /*bytes=*/4);

  b.checkLdsRead(/*wave=*/0, /*lane=*/0, /*addr=*/0, /*bytes=*/4);

  EXPECT_TRUE(b.hasLdsRace(0));
}
```
