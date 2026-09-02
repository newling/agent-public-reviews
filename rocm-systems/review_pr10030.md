This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#10030](https://github.com/ROCm/rocm-systems/pull/10030)

**Commit reviewed:** `b966170b7522` (`refactor(rocjitsu): unify explicit-wave
register observation`), the current PR head.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is a draft, and GitHub reports it as mergeable with
review still required.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests rocjitsu_plugin_race_so \
           rocjitsu_plugin_logging_so --parallel 8
```

Result: the final incremental build passed in 4.64s real, 4.92s user, and
0.85s sys.

**Register/plugin/lifecycle/race coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterAccessTest.*:ExecutionPluginTest.*:HookOrderingTest.*:PluginLoaderTest.*:RaceDetector.*'
```

Result: 153/154 passed, 0 failed, 1 skipped, and 0 errored in 0.19s real.
`ExecutionPluginTest.MfmaFastPathReadHookReportsRace` was skipped because this
host does not provide the required 16-lane native-float SIMD capability.

**Compiled callable-SGPR probe:**

I compiled the tiny gfx950 HIP source in Appendix B, extracted the device code,
and inspected its metadata and disassembly:

```bash
$ROCM_PATH/bin/hipcc --genco --offload-arch=gfx950 -O2 \
  -o $TMP_DIR/sgpr_call_probe.o $TMP_DIR/sgpr_call_probe.hip

$ROCM_PATH/lib/llvm/bin/clang-offload-bundler \
  --type=o --unbundle \
  --input=$TMP_DIR/sgpr_call_probe.o \
  --targets=hipv4-amdgcn-amd-amdhsa--gfx950 \
  --output=$TMP_DIR/sgpr_call_probe.hsaco

$ROCM_PATH/lib/llvm/bin/llvm-readelf --notes \
  $TMP_DIR/sgpr_call_probe.hsaco

$ROCM_PATH/lib/llvm/bin/llvm-objdump --disassemble \
  $TMP_DIR/sgpr_call_probe.hsaco
```

Compilation passed in 0.29s real. The kernel metadata reported
`.sgpr_count: 39`; the kernel called a separate device function, and that
function's disassembly contained `s_mov_b32 s40, 1`. This supports the PR's
central design decision: descriptor resource metadata is not a complete
instruction-observation boundary once callable device code is present. The
reserved physical block is the appropriate ownership domain for ordinary
register observation.

**Temporary complete-range SGPR probe:**

I added Appendix A's first regression locally, rebuilt, ran only that test, and
removed it. A 64-bit SGPR write beginning at the final register of one wave's
physical block produced one callback for the low dword and overwrote the
adjacent wave's first SGPR with the high dword.

Result: 0/1 passed. The callback vector was nonempty, and the adjacent value
changed from `0x11112222` to `0x33334444`. This is a genuine ownership/storage
bug, not an environment artifact.

**Temporary complete-range VGPR probe:**

I added Appendix A's second regression locally, rebuilt, ran only that test,
and removed it. A `RegisterAccess` constructed from the first wave performed a
64-bit VGPR write beginning at the final register of its block.

Result: 0/1 passed. The low-dword callback was attributed to the first wave,
the high-dword callback was attributed to the adjacent wave, and the adjacent
wave's first VGPR changed from `0x11112222` to `0x33334444`. This confirms that
the physical VGPR region path still resolves ownership one register at a time,
even when the `RegisterAccess` object has an explicit wave.

**Formatting and diff hygiene:**

```bash
time -p .venv/bin/pre-commit run --files \
  $(git diff --name-only <pr-base>..HEAD)
git diff --check <pr-base>..HEAD
```

Result: all applicable hooks passed in 0.28s real, `git diff --check` passed,
and the reviewed source checkout has no tracked modifications.

At review time, formatting, policy, setup, HIP NVIDIA summary, TSan, and the
completed multi-architecture summary checks pass. The original TheRock Linux
matrix was cancelled before its package jobs started, so its summary is red
only because it treats the cancelled matrix as a failure; a replacement
TheRock run for the same head is queued/running. The rocJitsu release,
Clang/GCC ASan/UBSan, replacement packaging, and compiler-runtime jobs are
still running or queued. No completed test reports a product failure.

## Summary

The PR extracts a coherent register-observation foundation from the closed
write-after-write detector PR. It adds instruction-visible SGPR write
callbacks, makes wave-bound SGPR access use the explicit wave rather than a
physical-index lookup, expands SGPR reverse ownership to the complete reserved
block, reports physical SGPR and VGPR capacities consistently to workgroup
callbacks, and clears both reverse maps when a wave releases its resources.

The split is the right architectural direction. SGPR WAW policy, mixed-LGKM
wait semantics, trap-register storage, generated ISA changes, and the base
observation contract are separate review units. Keeping this PR focused on the
last of those makes the later detector work substantially easier to reason
about.

The physical-block ownership choice is also justified. The compiled probe
shows a real callable-code shape where the kernel metadata does not cover a
callee's `s40` use. Treating `Wavefront::num_sgprs()` as the callback boundary
would therefore drop a legitimate instruction access. Retaining the descriptor
count as resource metadata while using the reserved block as the ordinary
storage/observation domain is a useful distinction.

The workgroup callback change follows from that distinction. The race detector
indexes logical register state derived from physical callbacks, so it needs
capacity for every register that can be observed. Passing the physical SGPR
block size removes the old asymmetry with VGPR capacity, while the wavefront
still retains its per-dispatch descriptor count.

The lifecycle change is likewise correct. Reverse maps are usable while
`onAmdgpuWavefrontHalted()` runs, then are cleared before the register blocks
become free. CU-only diagnostic/read paths can no longer attribute a freed
physical register to stale wave state.

The remaining blocker is that ownership is checked one dword at a time rather
than once for the complete architectural operation. The newly added
`RegAllocation::contains(base, count)` can express a region contract, but all
notification paths currently pass a count of one. SGPR64 and VGPR64 operations
can therefore cross into an adjacent wave, partially notify plugins, and
partially modify foreign storage. The VGPR path additionally loses its explicit
owner and re-resolves each physical register through the reverse map.

## Actionable items

### 1. Validate one owner for the complete register operation before observation or storage

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:401-476`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:936-1013`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:1036-1048`
- `emulation/rocjitsu/tests/register_access_test.cpp:419-493`

`owns_sgpr_range()` and `owns_vgpr_range()` accept a register count, but the
notification helpers always validate one register. `read_sgpr64()` and
`write_sgpr64()` then perform two independent 32-bit operations.
`read_vgpr_region()` and `write_vgpr_region()` likewise notify one register at
a time; their private observation helpers always use reverse lookup and ignore
the explicit `wf_` stored by a wave-bound `RegisterAccess`.

Appendix A demonstrates both consequences:

- an SGPR64 write can notify/write the low dword and then silently write the
  high dword into the adjacent wave; and
- a wave-bound VGPR64 write can report one dword for each of two different
  waves and modify the adjacent wave's VGPR.

Resolve the owner and validate the complete `[physical_base,
physical_base + reg_count)` range before firing any callback, constructing a
storage view, reading a value, or writing a value.

For wave-bound access, the stored `wf_`/`mutable_wf_` must remain authoritative
for the whole operation. Notify every register with that same wave only after
the complete range passes `owns_*_range()`. For CU-bound observed access,
require the complete region to map to one non-null owner; otherwise reject the
whole observed operation rather than splitting it across owners.

Follow the existing nonfatal policy for rejected accesses, but make it
operation-atomic: a rejected read must not expose foreign storage, and a
rejected write must produce no callback and modify no register. Add both
two-wave boundary regressions from Appendix A, plus corresponding read cases.

This is distinct from trap-selector storage. PR #9578 or the overlapping
debugger work still needs to route selectors 108-123 to dedicated per-wave
state. The requirement here is that every ordinary multi-register operation
has one owner and cannot partially cross a physical block boundary.

## Suggestions

### 1. Pin the callable-code reason for physical-block ownership with compiled coverage

**Files:**

- `emulation/rocjitsu/tests/execution_plugin_test.cpp:1834-1862`
- `emulation/rocjitsu/tests/CMakeLists.txt`

The submitted `s40` test manually combines a 40-SGPR dispatch with a decoded
`s_mov_b32 s40, 1`. It correctly pins the desired runtime behavior, but by
itself it does not show why that descriptor/instruction combination is valid.

Add a small optional compiler-backed test or a checked-in minimal gfx950 code
object based on Appendix B. Assert that the kernel metadata is below the
callee's `s40` use, then run or inspect the callee access through the plugin.
This converts the PR's most important design rationale from a comment into
durable evidence and prevents a future reviewer from incorrectly restoring the
descriptor count as the observation boundary.

### 2. Do not make ownership-map coverage depend on freed storage retaining its value

**File:**

- `emulation/rocjitsu/tests/register_access_test.cpp:470-493`

`FreeWavefrontClearsPhysicalOwnerMaps` asserts that SGPR and VGPR values remain
unchanged after `free_wavefront_resources()`. Value retention is unrelated to
the ownership-map contract and can change if register release starts clearing,
discarding, or lazily resetting storage.

After clearing the recorded callbacks, perform the two reads only to exercise
the reverse lookup and ignore their returned values. Keep the assertions that
no SGPR/VGPR callback fired. This preserves the intended lifecycle coverage
without constraining register-file reclamation policy.

### 3. Describe CU-bound observation as a transitional compatibility path

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:431-457`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:936-958`

The PR improves wave-bound SGPR access, but instruction code still contains
many CU-bound SGPR/VGPR accesses that infer ownership through reverse maps.
CU-bound `RegisterAccess` is also asymmetric: physical reads may be observed by
lookup, while physical writes are raw because no mutable wave is present.

Document this as a transitional compatibility path rather than the completed
explicit-wave model. Track the remaining migration separately: instruction
helpers should eventually carry a wave-bound `RegisterAccess`, while CU-only
access becomes clearly raw VM/storage access. That follow-up is broad enough
that it should not be folded into this focused PR.

## Commentary

### General direction

The general direction makes sense. The original combined PR mixed five
different contracts:

1. who owns an instruction-visible register access;
2. what physical capacity plugins may index;
3. how register ownership ends;
4. how SGPR WAW races are diagnosed and retired; and
5. where trap selectors are stored.

This PR isolates the first three and is small enough to review as infrastructure.
I would keep that decomposition rather than restoring the detector, wait-counter,
trap-register, generated-source, or documentation churn from the closed PR.

The complete-range issue above belongs here because it defines the ownership
primitive itself. The later WAW detector should not need to defend against a
single architectural access being split across two waves.

### Recommended landing sequence

After the complete-range fix:

1. land this observation/lifecycle foundation;
2. reconcile PR #9578 with the overlapping trap-storage implementation in
   PR #9844 and choose one per-wave selector/checkpoint contract;
3. reintroduce SGPR WAW detection from closed PR #9470 as a focused consumer of
   the now-stable SGPR write callback;
4. keep mixed-LGKM wait-counter precision in its own change unless that focused
   detector demonstrably requires it; and
5. migrate remaining CU-bound instruction register accesses to explicit-wave
   access as a separate mechanical/API cleanup.

PR #9577 is an appropriate umbrella tracking issue for this foundation, but
the trap-storage reconciliation and explicit-wave migration are concrete
enough to retain their narrower tracking.

### Plugin compatibility

Adding a virtual hook changes the C++ plugin interface, but the current loader
contract explicitly supports only repository-owned plugins rebuilt and shipped
with the host. It intentionally has no compatibility version for independently
built plugins. Under that current contract, this PR does not need to restore or
bump a plugin ABI version.

### Residual risk

Until trap storage lands, selectors 108-123 can still alias ordinary SGPR
storage on configurations whose physical block is smaller than 124 entries.
This PR improves observation attribution but does not fix that storage bug, as
its description states. The complete-range fix prevents ordinary operations
from crossing a block; it does not replace the dedicated trap-register work.

## Appendix A: complete-range ownership regressions

The temporary tests used the existing `Fixture`, constants, and
`RecordingPlugin` from `register_access_test.cpp`.

First, allow the fixture to create two wavefront slots:

```cpp
explicit Fixture(rj_code_arch_t arch = ROCJITSU_CODE_ARCH_CDNA4,
                 uint32_t requested_sgprs = kSgprsPerWave,
                 uint32_t wavefront_slots = 1) {
  ComputeUnitCore::Config cfg{};
  cfg.arch = arch;
  cfg.num_wf_slots = wavefront_slots;
  // Keep the rest of the submitted constructor unchanged.
}
```

The SGPR regression:

```cpp
TEST(RegisterAccessTest, Sgpr64WriteRejectsWholeRangeAtPhysicalBlockBoundary) {
  Fixture fx(ROCJITSU_CODE_ARCH_CDNA4, kSgprsPerWave,
             /*wavefront_slots=*/2);
  ASSERT_NE(fx.wf, nullptr);
  auto *adjacent_wave =
      fx.cu->dispatch_wf(/*wg_id=*/1, /*pc=*/0,
                         kSgprsPerWave, kVgprsPerWave);
  ASSERT_NE(adjacent_wave, nullptr);
  ASSERT_EQ(adjacent_wave->sgpr_alloc().base,
            fx.sgpr_base() + fx.cu->sgpr_allocation_block_size());

  const uint32_t boundary = adjacent_wave->sgpr_alloc().base - 1;
  constexpr uint32_t kSentinel = 0x11112222u;
  fx.cu->write_sgpr(adjacent_wave->sgpr_alloc().base, kSentinel);

  RegisterAccess(*fx.wf).write_sgpr64(
      boundary, 0x3333444455556666ull);

  EXPECT_TRUE(fx.plugin->sgpr_writes.empty());
  EXPECT_EQ(
      fx.cu->read_sgpr_storage(adjacent_wave->sgpr_alloc().base),
      kSentinel);
}
```

For the VGPR regression, retain the callback wave in `RecordingPlugin`:

```cpp
void onAmdgpuWriteVgprLanes(const Wavefront *wf,
                            uint32_t physical_reg,
                            uint64_t lane_mask,
                            uint8_t byte_mask) override {
  writes.push_back({physical_reg, lane_mask, byte_mask});
  write_wavefronts.push_back(wf);
}

std::vector<const Wavefront *> write_wavefronts;
```

Then add:

```cpp
TEST(RegisterAccessTest, WaveBoundVgpr64WriteKeepsOneOwnerAtBlockBoundary) {
  Fixture fx(ROCJITSU_CODE_ARCH_CDNA4, kSgprsPerWave,
             /*wavefront_slots=*/2);
  ASSERT_NE(fx.wf, nullptr);
  auto *adjacent_wave =
      fx.cu->dispatch_wf(/*wg_id=*/1, /*pc=*/0,
                         kSgprsPerWave, kVgprsPerWave);
  ASSERT_NE(adjacent_wave, nullptr);
  ASSERT_EQ(adjacent_wave->vgpr_alloc().base,
            fx.vgpr_base() + fx.cu->vgpr_allocation_block_size());

  const uint32_t boundary = adjacent_wave->vgpr_alloc().base - 1;
  constexpr uint32_t kLane = 0;
  constexpr uint32_t kSentinel = 0x11112222u;
  fx.cu->write_vgpr(adjacent_wave->vgpr_alloc().base,
                    kLane, kSentinel);

  RegisterAccess(*fx.wf).write_vgpr64(
      boundary, kLane, 0x3333444455556666ull);

  ASSERT_EQ(fx.plugin->write_wavefronts.size(), 2u);
  EXPECT_EQ(fx.plugin->write_wavefronts[0], fx.wf);
  EXPECT_EQ(fx.plugin->write_wavefronts[1], fx.wf);
  EXPECT_EQ(fx.cu->read_vgpr(
                adjacent_wave->vgpr_alloc().base, kLane),
            kSentinel);
}
```

## Appendix B: callable SGPR metadata probe

```cpp
__device__ __attribute__((noinline)) void use_s40() {
  asm volatile("s_mov_b32 s40, 1" ::: "memory");
}

extern "C" __global__ void kernel_uses_s40() {
  use_s40();
}
```
