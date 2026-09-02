This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9779](https://github.com/ROCm/rocm-systems/pull/9779)

**Commit reviewed:** `8e7a5d7ddd11` (`Remove redundant linux specific impl`),
the current PR head.

**Review mode:** comment-aware follow-up after the portable software-page-table
rewrite. I independently reviewed the complete current diff, the register
access and matrix fast-path consumers affected by the new storage contract,
the current review discussion, and the benchmark migration.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, and GitHub reports it as mergeable.
A synthetic merge with current `origin/develop` completed without conflicts.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: all 457 build steps passed in 140.67s real, 1036.42s user, and
51.29s sys.

**Register-storage, redispatch, and checkpoint tests:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterFileTest.*:RegisterFileDeathTest.*:WaveSizes/VgprRedispatchTest.*:CheckpointTest.*:CApiTest.CheckpointRoundTrip'
```

Result: 14/14 passed, 0 failed, 0 skipped, and 0 errored in 2.82s real.
This covers mutable-only chunk materialization, aligned and shared-boundary
chunk reclamation, zero state after redispatch for Wave32, Wave64, and
gfx1250's 1,024-VGPR block, and checkpoint round trips across lazy-chunk
boundaries.

**Default-build WMMA test:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Gfx1250WmmaTest.F16Fp8K64MatchesReferenceLayout'
```

Result: 1/1 passed in 0.02s real. This build does not enable AVX-512, so the
test takes the scalar fallback and does not exercise the affected optimized
path.

**GCC ASan/AVX-512 build:**

```bash
cmake -S $SRC_DIR/emulation/rocjitsu -B $ASAN_BUILD_DIR -G Ninja \
  -DCMAKE_C_COMPILER=/usr/bin/gcc \
  -DCMAKE_CXX_COMPILER=/usr/bin/g++ \
  -DBUILD_TESTING=ON \
  -DRJ_ENABLE_ASAN=ON \
  -DCMAKE_CXX_FLAGS=-march=native \
  -DROCM_PATH=$ROCM_PATH

time -p cmake --build $ASAN_BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: all 576 build steps passed in 242.42s real, 1742.40s user, and
98.23s sys.

**Optimized-path counterexample:**

```bash
ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 \
LD_PRELOAD=<gcc-libasan> \
time -p $ASAN_BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Gfx1250WmmaTest.F16Fp8K64MatchesReferenceLayout'
```

Result: the single test aborted in 0.40s with an AddressSanitizer
`heap-buffer-overflow`. `exec_wmma_f16_f8_spec` performed a 4-byte read exactly
past a 4,096-byte
`SoftwareLazyRegisterStorage<VectorReg<32, uint32_t>>::Chunk`. The read came
from indexing `c_words[out.reg * wf + out.lane]` after obtaining `c_words`
from one register's `reg_data()` pointer.

**Scalar control in the same ASan binary:**

```bash
ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 \
LD_PRELOAD=<gcc-libasan> \
RJ_FORCE_SCALAR=1 \
time -p $ASAN_BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Gfx1250WmmaTest.F16Fp8K64MatchesReferenceLayout'
```

Result: 1/1 passed in 0.08s real. This isolates the failure to the optimized
multi-register pointer path rather than the instruction's scalar semantics or
test setup.

I first attempted the same ASan/AVX-512 configuration with the project's
default Clang compiler. Compilation stopped before tests in libstdc++'s
`<experimental/simd>` with its known Clang/AVX-512 integral-mask static
assertion. That is a toolchain limitation unrelated to this PR; GCC supplied
the required sanitizer coverage.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files <all changed rocJitsu files>
git diff --check <pr-base>..HEAD
```

Result: all applicable pre-commit hooks passed, `git diff --check` passed,
and the reviewed source checkout has no tracked modifications.

**GitHub CI:** release, Clang ASan/UBSan, GCC ASan/UBSan, TSan, formatting,
and setup checks pass on the reviewed head. Those builds do not enable the
AVX-512 matrix fast paths, which explains why sanitizer CI does not expose the
local counterexample. The policy check fails because the PR description still
uses `N/A` for issue tracking. Several broad packaging jobs remained in
progress at review time.

## Summary

The rewritten PR no longer reaches into Linux virtual-memory APIs. It replaces
the eager VGPR vector with a portable software page table: each CU retains its
global physical-register index space, but storage is split into approximately
4 KiB C++ allocations. Const access to an absent chunk observes shared
immutable zero storage without allocating, while mutable access allocates and
zero-initializes the containing chunk.

Retirement restores the full allocation block to zero. Whole chunks are
released immediately; when allocation blocks and chunks have shared
boundaries, the implementation clears only the retired range and releases the
remaining boundary chunks once the CU becomes idle. The focused churn and
redispatch tests cover both aligned and unaligned layouts.

The API now explicitly makes register pointers allocation-scoped and narrows
`raw_vgpr_data()` to exactly one VGPR. Checkpoint save and restore were adapted
accordingly: save copies one register at a time, and restore materializes only
registers containing nonzero serialized bytes. The submitted cross-chunk
checkpoint tests pass.

This is a materially simpler and more portable design than the earlier
`mmap`/`madvise` implementation. The old OS-specific allocation, page-boundary,
overcommit, and fallback concerns no longer apply.

However, removing CU-wide contiguity is not confined to checkpointing. The
optimized MFMA/WMMA implementations predate this PR and still acquire one
`VgprReadRegion::reg_data()` pointer, then index it as a dense span covering
multiple VGPRs. With the new storage, adjacent 4 KiB chunks are independent
allocations. The existing gfx1250 WMMA test crosses such a boundary and
performs an out-of-bounds read under AVX-512. The same pattern appears in all
13 specialized matrix fast paths, so this is a broad optimized-execution
contract violation rather than a one-test edge case.

I found one actionable correctness issue and one PR-policy/description issue.
The portable storage design itself otherwise looks coherent.

## Actionable items

### 1. Remove the multi-register contiguity assumption from optimized MFMA/WMMA execution

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:487-510`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:663-668`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:1840-1844`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:1918-1922`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:2034-2038`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:2114-2118`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:2555-2559`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:2681-2685`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:2783-2804`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:3336-3340`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:4055-4059`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:4131-4134`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:4220-4223`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:4309-4312`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/mma_exec.h:4397-4400`

`raw_vgpr_data()` now guarantees only one register, and
`VgprReadRegion::reg_data()` forwards that one-register pointer. Every matrix
site above then indexes the pointer using `relative_reg * wf_size + lane` or
passes the complete multi-register region to a bulk converter. That crosses
allocation boundaries whenever the region straddles a 4 KiB chunk.

The ASan counterexample above reads immediately past a 4,096-byte Wave32 chunk
at `mma_exec.h:2802`. Depending on allocator layout, non-sanitized builds can
crash or silently consume unrelated memory and produce incorrect matrix
results.

Make these paths use an API whose storage contract matches their access
pattern. Viable directions include gathering each region into contiguous
scratch through `reg_data(relative_reg)`/`lanes(relative_reg)`, or restoring a
contiguous allocation-block guarantee in the storage policy. If the latter
changes first-touch granularity, repeat the submitted performance and RSS
measurements.

Add permanent coverage that actually enables the wide-SIMD implementation.
The existing test is a good semantic counterexample, but ordinary and current
sanitizer CI compile only the scalar fallback. At minimum, run this case under
an AVX-512 sanitizer job and audit all 13 `reg_data()` sites before merging.

### 2. Replace `N/A` and update the PR description to match the rewrite

**Location:** PR description.

The repository policy requires a recognized GitHub issue, JIRA ID, or accepted
tracking reference. The current `N/A` keeps the policy check red and applies
the `Not ready to Review` label.

The description also retains claims from the old implementation: it says a
saturation benchmark is added here and that subsequent operations use the
preexisting contiguous pointer path. The benchmark has moved to the external
corpus, and the current implementation explicitly removes multi-register
contiguity.

Link the owning issue or ticket and rewrite the technical details/test results
for the portable software-page-table head. In particular, remove the
contiguous-pointer claim; it currently obscures the correctness issue above.

## Suggestions

### 1. State the fresh-zero destination precondition on sparse checkpoint restore

**File:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/checkpoint.cpp:36-48`

`restore_vgpr_block()` deliberately skips serialized registers whose bytes are
all zero. That is equivalent to a full restore only because its caller has
just dispatched a fresh wave and `RegisterFile::allocate()` guarantees the
entire block is zero.

Document that precondition beside the helper or make it explicit at the call
site. Without it, the helper looks reusable as a general overwrite operation
even though applying it to existing state would merge nonzero destination
bytes into the checkpoint.

### 2. Land the external benchmark before making it the sole reproduction

**File:**

- `emulation/rocjitsu/docs/simdojo.md:241-243`

The documentation pins the saturation workload to a public corpus commit, but
the corresponding corpus PR is still open and draft at review time. Land that
change, then point this documentation at the merged revision. This keeps the
benchmark and resource verifier durable after their removal from this
repository.

## Commentary

### The original low-level portability concern is resolved

The current head contains no `mmap`, `madvise`, `MAP_NORESERVE`, Linux
conditional allocator, or manual operating-system page-boundary code. The new
storage is ordinary C++ ownership around fixed-size chunks. The older review
threads about overcommit behavior, page alignment, and platform fallback are
outdated after the rewrite.

### Zero state, reclamation, and lifetime contracts

The revised `RegisterFile` documentation now gives `allocate()` an explicit
full-block zero postcondition and makes accesses allocation-scoped. The
submitted direct tests exercise aligned and shared-boundary reclamation,
immutable zero reads, mutable materialization, invalid access after free, and
complete zero state on reuse. I did not find a remaining issue in those
contracts.

### Current review feedback

The current multi-register-contiguity comment is correct and independently
reproduced above. The checkpoint comment is also valid as a contract
clarification. The earlier design discussion requesting a portable alternative
has been addressed by the software-only implementation.

### Why green sanitizer CI is insufficient here

The affected routines select their optimized implementation only when the
binary is compiled for a 16-lane native float SIMD width and scalar mode is not
forced. Current sanitizer CI passes because it does not compile that branch as
AVX-512. The scalar control passing in the same ASan binary demonstrates that
the test matrix needs explicit optimized-path coverage, not simply another
ordinary sanitizer run.
