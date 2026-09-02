This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9470](https://github.com/ROCm/rocm-systems/pull/9470)

**Commit reviewed:** `b769b2f6dd63`, the current PR head.

**Review mode:** comment-aware follow-up review. I read every current top-level
comment, submitted review, inline thread, response, and resolution state, then
independently checked the current code and tests rather than treating a resolved
thread as proof.

**Public/repo status:** the base repository, fork, base branch, and head branch
are public. The PR is open, is not a draft, and GitHub reports it as mergeable,
but it remains blocked on review. At the time of this review, release,
Clang/GCC ASan/UBSan, TSan, pre-commit, package, policy, and the completed
analysis checks pass. Several multi-architecture stages and one gfx94X sanity
job are still pending; no completed product check is failing.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests rocjitsu_plugin_race_so \
           hip_race_tests_gfx950_target \
  --parallel 8
```

Result: all 467 build steps passed in 152.36s real, 1128.54s user, and
55.77s sys.

**Register/plugin/race/ABI coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterAccessTest.*:ExecutionPluginTest.*:ExecutionPluginGroupTest.*:RaceDetector.*:RaceDetectorPluginCallbackTest.*:PluginLoaderTest.*'
```

Result: 162/163 passed, 0 failed, 1 skipped, and 0 errored in 0.13s real.
`ExecutionPluginTest.MfmaFastPathReadHookReportsRace` was skipped because this
host does not provide the required 16-lane native-float SIMD capability. The
ABI mismatch fixture reports version 4 versus expected version 3, confirming
that the bumped host/plugin contract rejects a stale plugin before creation.

**Submitted SGPR and mixed-LGKM end-to-end tests:**

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure \
  -R '^RaceTest\.gfx950_(sgpr|mixed_lgkm)'
```

Result: 8/8 passed, 0 failed, 0 skipped, and 0 errored in 1.54s real. This
includes the scalar partial-wait regression requested in the first review, both
SGPR WAW race cases, and the three mixed scalar/DS boundary cases.

**Adjacent-wave SGPR storage counterexample:**

I temporarily added Appendix A to `register_access_test.cpp`, rebuilt
`rocjitsu_tests`, ran only that test, and removed the probe. The test seeds the
adjacent wave's `s4`, then performs the first wave's selector-108 write.

Result: 0/1 passed in 0.02s. The adjacent value changed from `0x11112222` to
`0x33334444`. The current helper suppresses the first wave's plugin callback
but still writes through to the neighboring physical allocation.

**gfx1250 GPR-index storage counterexample:**

I temporarily extended the existing test fixture as shown in Appendix B,
rebuilt `rocjitsu_tests`, ran only the new test, and removed the probe. It uses
the submitted gfx1250 configuration width of 1,024 VGPRs, destination high bank
3, and M0 GPR index 255. Destination `v1` therefore resolves exactly to the
adjacent wave's `v0`.

Result: 0/1 passed in 0.02s. The adjacent value changed from `0x11112222` to
`0x33334444`. Returning early from `notify_vgpr_write()` did not stop the
CU-only `RegisterAccess` storage write; reverse lookup instead treated the
physical index as belonging to the adjacent wave.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files \
  $(git diff --name-only origin/develop...HEAD)

git diff --check origin/develop...HEAD
```

Result: every applicable pre-commit hook passed in 2.01s, and
`git diff --check` passed. The source checkout has no tracked modifications.

I could not rerun the focused Python generator test because neither the system
Python nor the worktree virtual environment has pytest installed. The public
Python analysis check passes, and the changed generator output was also covered
by the successful C++ build. I did not run broad rocJitsu, HIP, or corpus
suites; the focused tests cover the changed callback, wait, ABI, and race paths,
while public sanitizer/release jobs provide the broader evidence.

## Summary

The PR adds instruction-visible SGPR write observation to the execution-plugin
interface and bumps the in-tree plugin contract from version 2 to 3. SGPR
instruction writes now carry an explicit owning wavefront, while scalar-memory
completion and runtime initialization remain raw storage writes that do not
fire the new callback.

The race detector uses that hook to report an instruction overwriting a pending
scalar-load destination. Registering a second scalar load also checks the new
destination against older pending scalar loads, preserving each exact
conflicting event. Scalar destinations remain live across nonzero partial
`lgkmcnt` waits because scalar reads can complete out of order. In the same
combined counter, older DS operations can still retire when their in-order
completion is proven by the remaining counter bound.

Most previous review feedback is correctly reflected in the current head:

- SGPR observation uses the writing wave and final-file overruns no longer
  throw or index the register file;
- the scalar partial-`lgkmcnt` behavior has an end-to-end gfx950 regression;
- the two positive SGPR WAW tests use the `_race` suffix;
- the plugin contract version is 3 and the stale-plugin fixture is rejected;
- the generator and checked-in gfx1250 notification calls both pass
  `Wavefront&`; and
- the redundant preliminary scalar-event scan is gone even though that GitHub
  thread remains unresolved.

The remaining problem is that the adopted nonfatal range policy currently
applies only to observation. Invalid instruction accesses can still modify raw
register storage. The existing open SGPR thread demonstrates this for TTMP
selectors, and the same split between notification and storage leaves a
gfx1250 GPR-indexed VGPR access able to cross into an adjacent wave.

## Actionable items

### 1. Reject the complete wave-relative SGPR range before reading or modifying storage

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:407-423`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:945-962`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h:222-264`
- `emulation/rocjitsu/tests/register_access_test.cpp:463-525`

The private wave-aware helpers check only the physical file boundary. If an
index is inside the file but outside `wf.sgpr_alloc()`, reads return another
wave's value and writes modify that storage without firing a callback. Appendix
A reproduced selector 108 from a 104-SGPR wave overwriting the adjacent wave's
`s4`.

The 64-bit path compounds this because `write_sgpr64()` performs two independent
32-bit writes. A range starting at the final allocated SGPR can commit its low
dword and reject only the high dword, producing a torn architectural write.

Validate the full requested range against the explicit wave allocation before
any read, callback, or write. A rejected 32-bit access should return zero or
perform no write according to the chosen nonfatal policy. A rejected 64-bit
access must be atomic with respect to validation: either both dwords are valid
and written, or neither is modified. Update the existing adjacent-wave test to
assert that the neighboring value remains unchanged, and add a final-allocation
64-bit straddle regression.

This does not require solving permanent TTMP storage in this PR. Until special
selectors have dedicated wave state, safely rejecting an out-of-allocation
instruction access is sufficient and keeps the plugin-observation policy
separate from physical storage ownership.

### 2. Make VGPR range validation guard storage access, not only plugin notification

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:457-484`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:968-984`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/gfx1250/operand_exec.cpp:225-245,317-410`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/isa_operand_simd_inl.h:123-241`

The review-response change makes `notify_vgpr_read/write()` return for an
out-of-allocation physical register, but operand value and SIMD paths obtain or
write raw storage independently. The scalar gfx1250 destination path constructs
`RegisterAccess(wf.cu())`, so reverse lookup can assign the crossed physical
index to the adjacent wave. The SIMD paths can form raw pointers before their
separate notification call.

Appendix B reproduced this with a normal 1,024-register gfx1250 block:
destination bank 3, `v1`, and GPR index 255 resolve to the next block's `v0`;
the adjacent wave's value was overwritten. A final wave can analogously form an
out-of-file pointer.

Carry the explicit wave through the storage operation and validate the complete
one- or two-register range before returning a view, pointer, or write region.
The selected nonfatal policy can silently skip the access; no rate-limited
warning is required. What matters is that an ignored callback must also imply
no storage read/write. Add an adjacent-wave gfx1250 regression based on
Appendix B and a final-wave multi-register boundary case.

## Suggestions

### 1. Add a direct end-to-end safe counterpart for the SGPR WAW move case

**Files:**

- `emulation/rocjitsu/tests/race-detector/hip_race_gfx950_test.hip:368-405`
- `emulation/rocjitsu/tests/race-detector/CMakeLists.txt:124-133`

Add an unsuffixed `sgpr_waw_load_then_mov` kernel/test that inserts
`s_waitcnt lgkmcnt(0)` before `s_mov_b32` and calls `ExpectNoRace()`.

The existing `sgpr_waitcnt` case already gives end-to-end no-race evidence for
a waited scalar load followed by `s_add_u32`, so I do not treat this as a
correctness blocker. The direct pair would nevertheless protect the exact
user-facing WAW example and make the positive/negative naming convention
complete.

## Commentary

The private `RegisterAccess` friendship called out in the discussion is an API
asymmetry, but it is not by itself a blocker for this focused feature. Keeping
the explicit-wave ownership invariant and cleaning up the SGPR/VGPR facade in a
follow-up is reasonable once the range and storage semantics above are made
safe.

The unresolved partial-LGKM GitHub thread is already addressed in code:
nonzero waits call `resolveWaitCnt(lgkmcnt, isLdsEvent)` directly, while zero
retires all LGKM event classes. It needs thread bookkeeping, not another code
change.

The generator, ABI, scalar partial-wait, naming, and final-file observation
threads are also substantively addressed. The current blockers are the two
storage effects that remain after observation is skipped.

## Appendix A: adjacent-wave SGPR storage regression

This test uses the existing `Fixture` and constants from
`register_access_test.cpp`.

```cpp
TEST(RegisterAccessTest, OutOfAllocationSgprWriteDoesNotOverwriteAdjacentWave) {
  Fixture fx(ROCJITSU_CODE_ARCH_CDNA4, /*wavefront_slots=*/2);
  ASSERT_NE(fx.wf, nullptr);
  auto *adjacent_wave = fx.cu->dispatch_wf(
      /*wg_id=*/1, /*pc=*/0, kSgprsPerWave, kVgprsPerWave);
  ASSERT_NE(adjacent_wave, nullptr);
  ASSERT_EQ(adjacent_wave->sgpr_alloc().base,
            fx.wf->sgpr_alloc().base + kSgprsPerWave);

  constexpr uint32_t kAdjacentS4 = 4;
  constexpr uint32_t kTtmp0Selector = 108;
  constexpr uint32_t kSentinel = 0x11112222u;
  fx.cu->write_sgpr(adjacent_wave->sgpr_alloc().base + kAdjacentS4,
                    kSentinel);

  RegisterAccess(*fx.wf).write_sgpr(
      fx.wf->sgpr_alloc().base + kTtmp0Selector, 0x33334444u);

  EXPECT_EQ(fx.cu->read_sgpr(
                adjacent_wave->sgpr_alloc().base + kAdjacentS4),
            kSentinel);
}
```

## Appendix B: gfx1250 GPR-index adjacent-wave regression

Add these includes to `register_access_test.cpp`:

```cpp
#include "rocjitsu/isa/arch/amdgpu/gfx1250/execution_backend.h"
#include "rocjitsu/isa/arch/amdgpu/gfx1250/operand.h"
```

For this probe, extend the existing `Fixture` constructor with an optional
`vgprs_per_wave` argument, use it for `cfg.vgprs_per_wf`, and pass it to the
initial `dispatch_wf()` call. Then add:

```cpp
TEST(RegisterAccessTest, GprIdxWriteDoesNotCrossIntoAdjacentWaveAllocation) {
  ScopedIsaExecutionBackend execution_backend_scope{
      &gfx1250::execution_backend()};
  constexpr uint32_t kGfx1250VgprsPerWave = 1024;
  Fixture fx(ROCJITSU_CODE_ARCH_GFX1250, /*wavefront_slots=*/2,
             kGfx1250VgprsPerWave);
  ASSERT_NE(fx.wf, nullptr);
  auto *adjacent_wave = fx.cu->dispatch_wf(
      /*wg_id=*/1, /*pc=*/0, kSgprsPerWave, kGfx1250VgprsPerWave);
  ASSERT_NE(adjacent_wave, nullptr);
  ASSERT_EQ(adjacent_wave->vgpr_alloc().base,
            fx.wf->vgpr_alloc().base +
                fx.cu->vgpr_allocation_block_size());

  constexpr uint32_t kLane = 0;
  constexpr uint32_t kSentinel = 0x11112222u;
  constexpr uint32_t kAttemptedWrite = 0x33334444u;
  fx.cu->write_vgpr(adjacent_wave->vgpr_alloc().base, kLane, kSentinel);

  fx.wf->set_vgpr_msb_mode(0xC0u); // Destination bank 3.
  fx.wf->set_mode_raw(
      fx.wf->mode_raw() | amdgpu::Wavefront::GPR_IDX_EN_BIT);
  fx.wf->set_m0((0x8u << 8u) | 0xFFu); // Index destination by +255.
  gfx1250::Operand destination(
      32, gfx1250::OperandType::OPR_VGPR, 1);
  destination.set_vgpr_msb_role(amdgpu::VgprMsbRole::Dst);
  RegisterAccess(*fx.wf).write_lane(
      destination, kLane, kAttemptedWrite);

  EXPECT_EQ(fx.cu->read_vgpr_storage(
                adjacent_wave->vgpr_alloc().base, kLane),
            kSentinel);
}
```
