This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#10601](https://github.com/ROCm/rocm-systems/pull/10601)

**Revision reviewed:** `c43f78866691` (`[rocjitsu] Materialize LDS backing on
demand`), one commit based on `e36e73e19cac`.

**Review mode:** independent review. I did not read existing PR reviews,
inline comments, review threads, or discussion comments.

**Public/repository status:** the repository, PR, base branch, and head branch
are public. The PR is open, non-draft, mergeable, and currently blocked by
required review/checks. It is labelled `Not ready to Review`.

**Exact-head focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: all 673 required steps passed in 253.00s real, 1887.30s user, and
68.44s sys.

**Exact-head LDS coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='LdsTest.*:LdsAllocationTest.*:*Lds*:*LDS*'
```

Result: 158/158 passed, 0 failed, 0 skipped, and 0 errored in 2.25s real.
This selection covers the new lazy-backing tests plus CU/WGP allocation,
ordinary and vector LDS accesses, direct-to-LDS operations, cluster
multicast, tensor DMA, atomics, bounds behavior, race-detector integration,
and virtual-LDS translation.

**Related lazy-VGPR contracts:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterFileTest.*:RegisterFileDeathTest.*:WaveSizes/VgprRedispatchTest.*'
```

Result: 10/10 passed, 0 failed, 0 skipped, and 0 errored in 0.01s real.

**Current-`develop` integration:**

```bash
git merge --no-commit --no-ff origin/develop

time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8

time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='LdsTest.*:LdsAllocationTest.*:*Lds*:*LDS*:RegisterFileTest.*:RegisterFileDeathTest.*:WaveSizes/VgprRedispatchTest.*'
```

The merge completed without conflicts. All 279 incremental build steps
passed in 158.98s real, and all 168 selected tests passed in 2.29s real. The
temporary merge was then aborted.

**Formatting and diff hygiene:**

```bash
git diff --check e36e73e19cacc47bf496c0871170f9096dba5521..HEAD

time -p .venv/bin/pre-commit run --files \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/lds.h \
  emulation/rocjitsu/tests/CMakeLists.txt \
  emulation/rocjitsu/tests/amdgpu_vm_test.cpp \
  emulation/rocjitsu/tests/lds_test.cpp
```

Both checks passed; pre-commit completed in 0.71s real.

**Published-head CI context:** the focused rocJITsu release, Clang
ASan/UBSan, GCC ASan/UBSan, TSan, and formatting jobs pass. The broad
multi-architecture workflow has failures in unrelated repository projects.
The repository-policy check fails because the PR description has no issue or
ticket reference.

## Summary

The PR separates architectural LDS capacity from allocated host backing.
Fresh CU-local and WGP-shared LDS pools have no byte backing; reads from the
unmaterialized suffix return zero, while writes and workgroup reservations
grow a contiguous prefix in 4 KiB logical granules. Clearing or reusing LDS
zeroes the existing prefix but deliberately retains its high-water allocation.
Removing the raw `data()` accessors also keeps callers from retaining pointers
across vector growth.

This is directly related to ROCm/rocm-systems#9779, the lazy-VGPR change that
merged on August 18, 2026. This PR's base already contains that merge. Both
changes establish the same useful semantic boundary:

- architectural capacity exists independently of host backing;
- absent backing reads as zero;
- mutable access materializes backing; and
- raw contiguous-pointer assumptions must not escape the storage owner.

The storage policies intentionally differ. The merged VGPR implementation
uses independent approximately 4 KiB chunks and releases them when register
allocations retire. This LDS implementation keeps one contiguous prefix,
materializes it as early as workgroup reservation, and never shrinks it. That
is a defensible tradeoff for a relatively small, bump-allocated, memcpy-heavy
scratchpad, and it avoids repeating the multi-register-contiguity bug found
during #9779 review. It does mean this is a retained high-water-mark cache,
not the same reclaimable sparse backing used for VGPRs.

The normal LDS paths, boundary reads, vector operations, zero-on-reuse
behavior, WGP ownership, and current-`develop` integration all look sound.
I found no code-correctness blocker in the valid emulator paths exercised by
the current tree.

## Actionable items

### 1. Link the PR to an issue or ticket

**Location:** PR description

The repository-policy check is failing because the description has no
recognized issue or ticket reference. Add the specific tracking item under an
`Issue Tracking` section. Separately, it would help readers to identify #9779
as the already-merged register-storage precedent, but a related PR should not
substitute for the required issue or ticket.

## Suggestions

### 1. Make reservation-time materialization an explicit, measured policy choice

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/lds.h:206-212`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:359-364`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/spi.h:232-234`
- `emulation/rocjitsu/tests/amdgpu_vm_test.cpp:249-293`

`zero_range()` currently materializes the complete reserved prefix. Thus an
immediate-termination kernel that declares 320 KiB of LDS allocates all 320
KiB even though no LDS instruction accesses it. By contrast, #9779 keeps a
VGPR allocation logical until mutable access and can reclaim its chunks after
retirement.

There is no correctness need to allocate an absent part of a zeroed range:
only the intersection with existing backing can contain stale bytes, while the
unmaterialized suffix already reads as zero. A fully first-write-driven policy
could clear only that intersection and leave the absent suffix implicit.

The current choice may still be preferable because it avoids vector growth in
the instruction hot path and because LDS reservations usually approximate the
working set. If so, document that rationale beside `zero_range()` and include
a no-touch, large-reservation comparison in the performance evidence. The
submitted tests currently assert reservation-time materialization as behavior
without establishing why it is the desired policy.

### 2. Add a direct `clear()` high-water regression

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/lds.h:200-204`
- `emulation/rocjitsu/tests/lds_test.cpp`

The class-level contract says that clearing LDS zeros contents while retaining
the materialized prefix. The direct tests cover repeated `zero_range()`, but
not `clear()`. Add a small test that materializes two granules, writes values
on both sides of the granule boundary, calls `clear()`, and verifies both
zero contents and unchanged `materialized_size_bytes()`.

## Commentary

### Relationship to lazy VGPR backing

The two PRs should be presented as members of the same memory-footprint
strategy, but the implementations should not be mechanically unified.
`SoftwareLazyRegisterStorage` has register-allocation ownership, compile-time
capacity, chunk reclamation, and non-contiguous storage semantics. LDS has
byte addressing, a runtime capacity, per-workgroup bump allocation, and hot
bulk/vector copies. Reusing the register class directly would couple unrelated
contracts.

A future shared primitive could make sense only if it captures the genuinely
common pieces—implicit-zero reads, bounded 4 KiB materialization, range
copy/clear, and an explicit reclamation policy—without forcing either VGPR or
LDS ownership rules onto the other.

### High-water lifetime

The claimed memory reduction is a startup/working-set improvement, not a
per-dispatch reclamation guarantee. Once a CU or WGP pool reaches a large LDS
reservation, that backing remains resident for the lifetime of the object.
That differs materially from #9779, which releases fully covered VGPR chunks
when a wave retires. The retained behavior may be the right latency tradeoff,
but it should be visible in the design description so future performance work
does not assume both lazy stores have the same lifetime.
