This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9779](https://github.com/ROCm/rocm-systems/pull/9779)

**Commit reviewed:** `8e0a2596ba52` (`Lazy vgpr allocation system`), the
current PR head.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, and GitHub currently reports it as
mergeable but blocked by required checks/review.

**Release build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_bin rocjitsu_shared rocjitsu_tests --parallel 8
```

Result: all 335 build steps passed in 190.10s real, 1412.91s user, and
46.20s sys.

**Submitted register-storage and redispatch tests:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterFileTest.*:WaveSizes/VgprRedispatchTest.*'
```

Result: 7/7 passed, 0 failed, 0 skipped, and 0 errored in 0.01s real.

**Checkpoint boundary:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='CheckpointTest.*:CApiTest.CheckpointRoundTrip'
```

Result: 5/5 passed, 0 failed, 0 skipped, and 0 errored in 0.42s real.
This exercises saving active VGPR storage and restoring it into newly allocated
register blocks.

**Existing gfx1250 execution coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Gfx1250ExecutionTest.*:Gfx1250SimulationTest.*'
```

Result: 111/111 passed, 0 failed, 0 skipped, and 0 errored in 2.36s real.

**Temporary gfx1250 high-bank redispatch probe:**

I extended `VgprRedispatchTest` locally with a gfx1250/Wave32 parameter,
configured one 1,024-VGPR allocation block, dirtied every lane of every
register, halted the wave, redispatched it, and checked the complete block for
zero. The focused command was:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='WaveSizes/VgprRedispatchTest.RecycledAllocationStartsZero/Gfx1250'
```

Result: 1/1 passed, 0 failed, 0 skipped, and 0 errored in 0.01s real; the test
body took 2 ms. The probe was removed afterward.

**Idle-reset range ablation:**

I also temporarily added a gfx1250-shaped register-file microbenchmark with 64
blocks of 1,024 Wave32 VGPRs. Each of 5,000 iterations allocated one block,
touched one word per 4 KiB page, and retired the only live block. Five repeated
runs of the submitted whole-file idle reset took 69-70 ms after the first
iteration. Changing only the all-blocks-free branch to reset the retired block
took 77 ms in the same test:

```bash
$BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterFileBenchmark.Gfx1250SingleWaveIdleFree' \
  --gtest_repeat=5
```

This small synthetic probe did not support changing the submitted idle-reset
policy. Both temporary source changes were removed.

**gfx1250 hipBLASLt workload:**

I ran the same TheRock gfx1250 runtime and F32 128x128x128
`hipblaslt-bench` workload against the exact parent `bee28e14a8ec` and this PR
head. The workload was launched through rocJitsu with:

```bash
/usr/bin/time -f 'real %e user %U sys %S maxrss %M' \
  $BUILD_DIR/tools/rocjitsu/rocjitsu \
  --config $SRC_DIR/configs/gfx1250.json -- \
  $ROCM_PATH/bin/hipblaslt-bench \
  --api_method c --precision f32_r \
  -m 128 -n 128 -k 128 \
  --initialization zero --verify --print_kernel_info \
  --cold_iters 0 --iters <1-or-100>
```

Three independent one-iteration process runs produced:

| Revision | Wall times | Peak RSS |
| --- | --- | ---: |
| Parent `bee28e14a8ec` | 2.79s, 2.89s, 2.82s | approximately 4,089,900 KiB |
| PR `8e0a2596ba52` | 2.13s, 2.15s, 2.12s | approximately 1,992,000 KiB |

The one-iteration median improves by approximately 24%, and peak RSS falls by
approximately 51%.

A final post-probe confirmation with the exact command printed above completed
successfully in 2.39s wall time with 1,992,420 KiB peak RSS and zero norm error.

Three 100-iteration runs produced:

| Revision | Wall times | Peak RSS |
| --- | --- | ---: |
| Parent `bee28e14a8ec` | 5.55s, 8.23s, 6.61s | approximately 4,089,000 KiB |
| PR `8e0a2596ba52` | 4.91s, 4.99s, 4.96s | approximately 1,992,000 KiB |

The parent sustained measurements were noisy, but all three PR runs were
faster. Every run completed successfully and reported zero norm error. Because
the workload used zero initialization, I treat this primarily as an
end-to-end loading, selection, dispatch, synchronization, and performance
check rather than strong numerical coverage.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files <all changed rocJitsu files>
git diff --check HEAD^..HEAD
```

Result: all applicable pre-commit hooks passed, and `git diff --check` passed.
The reviewed source checkout has no tracked modifications.

At the time of review, CodeQL and the Clang ASan/UBSan corpus job pass. The
release, TSan, GCC ASan/UBSan, formatting, and several setup jobs failed before
checkout because GitHub Actions could not resolve or download standard actions;
their logs report service-unavailable/internal-server errors rather than
product test failures.

## Summary

The PR separates register allocation from physical commitment. SGPRs retain
eager `std::vector` storage, while every ISA-specific VGPR file now reserves one
contiguous anonymous Linux mapping and relies on normal page faults to commit
only touched pages. The mapping uses `MAP_NORESERVE`, opts out of transparent
huge pages when supported, and retains the existing contiguous pointer layout
used by SIMD and checkpoint code. Non-Linux builds use the eager-storage
fallback.

Register reuse still has a zero-state contract, but its implementation moves
from `ComputeUnitCore::dispatch_wf_at()` into `RegisterFile`. Eager storage
marks a freed block dirty and clears it on the next allocation. Demand-paged
storage clears partial edge pages and uses `MADV_DONTNEED` for every full page
inside the retired range, so subsequent reads see anonymous zero-filled pages.
When the final block retires, the implementation discards the complete
register-file range.

The partial-page handling is important because the mapping deliberately places
the first register 16 bytes after the mapping base. Adjacent allocation blocks
can therefore share edge pages. The submitted reset code clears only the
retired block's bytes on those shared pages and discards only pages wholly
contained in the reset range. The neighboring-block regression exercises this
case directly.

The integration ordering also appears sound. Wave halt callbacks run before
`free_wavefront_resources()` discards the register pages, checkpoint save reads
only active allocations, and checkpoint restore allocates a block before
copying VGPR bytes into it. The focused checkpoint and redispatch tests passed.

The result is useful beyond an RSS optimization. On the tested gfx1250
hipBLASLt process, it removes roughly 2 GiB of peak resident memory and also
reduces startup-dominated wall time. The main remaining review concerns are
making the new zero-on-allocation contract explicit and keeping the new
standalone benchmark from silently decaying.

## Actionable items

### 1. Document the zero-on-success postcondition of `RegisterFile::allocate()`

**Files:**

- `emulation/rocjitsu/lib/simdojo/include/simdojo/components/register_file.h:207-222`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.cpp:123-155`

The PR removes the explicit SGPR/VGPR clearing from `dispatch_wf_at()`, so
correct dispatch now depends on a stronger `RegisterFile::allocate()` contract:
every successful allocation must expose an entirely zeroed
`regs_per_block()` block, not merely the requested `count`. The implementation
and tests satisfy that requirement, but the public method documentation says
only that it returns a contiguous block.

Add an `@post` to `allocate()` stating that a successful return makes the full
allocation block zero-initialized for both storage policies. Also mention that
this is the reason eager storage defers a reset and demand-paged storage resets
on retirement. This prevents a future storage policy or reset optimization
from treating zeroing as optional RSS housekeeping and reintroducing register
state leakage between waves.

### 2. Replace `N/A` with a valid tracking issue or ticket

**Location:** PR description, `Issue Tracking` section.

The repository policy requires a recognized GitHub issue, JIRA ID, or other
accepted tracking reference. `N/A` does not satisfy that policy and will keep
the PR blocked even when product checks are green. Link the specific
performance/memory issue that owns this work; use `Related` unless this PR
fully resolves the tracking item.

## Suggestions

### 1. Keep the gfx1250 1,024-VGPR redispatch case as permanent coverage

**File:**

- `emulation/rocjitsu/tests/vgpr_redispatch_test.cpp:23-84`

The submitted integration parameters cover RDNA4 Wave32 and CDNA4 Wave64 with
256 requested VGPRs. The temporary gfx1250 case described above passed, but it
is the architecture with the largest configured per-wave VGPR count in the
current simulator.

Add `vgprs_per_wf` to `RedispatchCase`, retain 256 for the existing cases, and
add `ROCJITSU_CODE_ARCH_GFX1250`, Wave32, and 1,024 VGPRs. The CDNA4 unit test
already covers the same 128 KiB block byte geometry, so this is not evidence of
a current defect; it is direct integration coverage for high gfx1250 register
banks and the topology that benefits most from the change.

### 2. Give the standalone saturation benchmark an opt-in build/check target

**Files:**

- `emulation/rocjitsu/benchmarks/vgpr_saturation/README.md:14-32`
- `emulation/rocjitsu/benchmarks/vgpr_saturation/verify_resources.py:65-160`
- `emulation/rocjitsu/tests/CMakeLists.txt`

The benchmark and verifier add more than 500 lines, but no CMake or CI target
compiles the HIP source or runs the resource verifier. The README correctly
keeps performance observations out of CTest; that does not require leaving the
source completely unchecked.

Add a lightweight opt-in target that compiles `vgpr_saturation.hip` and runs
`verify_resources.py` when an appropriate ROCm compiler is available. It does
not need to launch rocJitsu or assert a timing threshold. This would catch
source/API breakage and changed compiler resource metadata while preserving the
benchmark's non-gating performance role.

## Commentary

### Full-file discard when the CU becomes idle

`RegisterFile::free()` scans the block bitmap and resets the entire mapping
when the final block retires. That initially looked like a possible gfx1250
retirement cost because the virtual range is approximately 8 MiB per CU.
However, the focused 5,000-retirement ablation above did not improve when the
idle case discarded only the 128 KiB retired block. I would keep the simpler
submitted behavior unless a real workload or profiler attributes material time
to the full-range `madvise`.

### Failure timing under `MAP_NORESERVE`

The new Linux policy changes worst-case allocation failure timing. Reserving
the virtual mapping can succeed even when the host could not physically back
every page; a later page fault can still encounter system-wide memory
exhaustion. The implementation documents this at the flag site. Given that the
purpose is to avoid charging untouched topology state and real workloads
commit only a fraction of the reservation, this is a reasonable tradeoff, but
it is worth retaining in operational documentation for constrained hosts.

### Pointer lifetime

The PR explicitly scopes mutable register references and pointers to the life
of their allocation. Existing synchronous plugin, memory-completion, and
checkpoint paths appear to honor that ordering. Any future asynchronous
consumer that keeps a raw VGPR pointer beyond a wave halt would now risk
reading newly zero-filled or recommitted pages, so the new lifetime wording is
an important part of the design rather than only API cleanup.
