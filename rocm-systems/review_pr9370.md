This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9370](https://github.com/ROCm/rocm-systems/pull/9370)

**Commit reviewed:** `d2d5031a32d8` (current PR head). The intermediate
Simdojo change and its immediate revert are net-zero; the final diff changes
only checkpoint restoration and its tests.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, targets `develop`, and GitHub reports
it as mergeable with review still required. The release, Clang ASan/UBSan,
GCC ASan/UBSan, TSan, pre-commit, and HIP NVIDIA checks pass. The TheRock
gfx94X package job fails in its `Fetch sources` step before applying or
building this PR; its summary consequently fails as well.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: all 344 build steps passed in 159.35s real, 1189.66s user, 52.73s
sys.

**Submitted checkpoint and C API coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='CheckpointTest.*:CApiTest.CheckpointRoundTrip'
```

Result: 5/5 passed, 0 failed, 0 skipped, 0 errored. Timing: 0.72s real,
0.17s user, 0.54s sys.

**Active-wavefront resume counterexample:**

I temporarily added a public-restore regression that built a minimal CDNA3
SoC, placed `s_endpgm` at PC zero, dispatched one resident wavefront, saved
the checkpoint, restored it through `rj_vm_restore_checkpoint()`, and called:

```cpp
int active = 0;
ASSERT_EQ(rj_vm_step(restored.get(), &active), ROCJITSU_STATUS_SUCCESS);
EXPECT_EQ(active, 1);
```

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='CApiTest.RestoredResidentWavefrontResumesExecution'
```

Result on the submitted code: 0/1 passed in 0.02s real. `rj_vm_step()`
returned success but set `active` to `0`, so the restored resident wave never
executed.

I then prototyped scheduling every non-idle CU after `engine->create()`. The
counterexample and all five submitted focused tests passed: 6/6 passed,
0 failed, 0 skipped, 0 errored in 0.70s real. The temporary regression and
prototype were removed, and the submitted source was rebuilt and retested.

**Diff hygiene and formatting:**

```bash
git diff --check <pr-base>..HEAD
$SRC_DIR/.venv/bin/pre-commit run --files \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/checkpoint.cpp \
  emulation/rocjitsu/tests/config_test.cpp
```

Result: passed.

## Summary

Checkpoint loading previously returned a `VirtualMachine` as
`LoadedConfig::build_result.root`, but `LoadedConfig::soc()` accepts only a
root-level `SoC`. The public restore path therefore failed before it could
hand the reconstructed topology to the simulation engine.

This PR reconstructs a `SoC` directly, restores memory and wavefront state
into it, and returns the same root shape as the JSON configuration loader.
`create_from_loaded()` can then wrap that SoC in the runtime
`VirtualMachine`, attach it to an engine, and create the topology. The
existing state tests are updated to navigate the root-level SoC, and the new
C API test verifies that saving and restoring an idle VM returns success.

The root-shape correction is appropriate and fixes the immediate
`LoadedConfig::soc()` mismatch. However, an active checkpoint still cannot
resume: wavefront restoration occurs before engine attachment, and the
execution event discarded at that boundary is never recreated.

## Actionable items

### 1. Schedule restored resident wavefronts after engine attachment

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/checkpoint.cpp:224-249`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/rj_vm.cpp:93-102`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:709-726`,
`emulation/rocjitsu/tests/config_test.cpp:986-1004`

`restore_checkpoint()` recreates every saved resident wave by calling
`cu->dispatch_wf()` while the new SoC is still a detached component tree.
`dispatch_wf()` calls `schedule_work()`, but `schedule_work()` deliberately
returns when `engine() == nullptr`. Later, `create_from_loaded()` attaches the
tree and calls `engine->create()`, but no path revisits those non-idle CUs.
Their wavefronts remain `RUNNING` in storage without any CU timer event, so
`rj_vm_step()` or `rj_vm_run()` can terminate or advance only to unrelated
events without executing the restored program.

The temporary CDNA3 regression above reproduced this with a resident
`s_endpgm` wave: restore returned success, but the first step reported no
activity. Explicitly scheduling non-idle CUs after `engine->create()` made the
regression pass. A lifecycle-oriented implementation, such as having CU
startup schedule already-resident work, would also avoid coupling generic VM
creation directly to checkpoint details.

Ensure that every restored non-idle CU gets an initial work event only after
its engine and partition are assigned. Add a regression that checkpoints a
resident wave with a known instruction, restores through the public C API,
and verifies actual progress or termination of that wave. The current test
saves an idle VM and ignores the `active` result, so it cannot distinguish a
resumed simulation from an inert restored topology.

## Suggestions

None.

## Commentary

Matching the JSON loader's root shape is cleaner than teaching
`LoadedConfig::soc()` about a second ownership shape. It keeps
`create_from_loaded()` as the single place that introduces the runtime
`VirtualMachine` wrapper.

The failing TheRock package check does not exercise this diff: the job stops
while fetching sources, before its patch and build steps. The focused release
and sanitizer corpus jobs that do build the PR are green.
