This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9601](https://github.com/ROCm/rocm-systems/pull/9601)

**Commit reviewed:** `ad4396a696a1` (`[rocjitsu] Model synchronous DRM
timelines`), the current PR head.

**Review mode:** the code findings and counterexamples came from an independent
first review without using existing GitHub review threads or discussion. In a
later context pass requested by the reviewer, I read the current PR discussion
and relevant ROCr history to look for the motivating reproducer. That follow-up
did not change the findings below.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, and GitHub reports it as mergeable with
review still required. The release, Clang ASan/UBSan, GCC ASan/UBSan, TSan,
pre-commit, gfx94X/gfx950 package, TheRock summary, and HIP NVIDIA summary
checks pass. The Systems PR Bot policy check fails; the PR description's issue
tracking section currently says `N/A`, which does not satisfy this repository's
tracking policy.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target interposer_dup_test rocjitsu_bin rocjitsu_shared --parallel 8
```

Result: all 355 build steps passed in 106.40s real, 787.88s user, and
39.20s sys.

**Submitted descriptor, GEM, and syncobj interposer coverage:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R '^Interposer(Dup|Gem|Syncobj)Test\.' \
  --output-on-failure --timeout 120
```

Result: 23/23 passed, 0 failed, 0 skipped, 0 errored in 12.11s real,
2.42s user, and 9.28s sys.

**Motivating ROCr integration context:**

The PR description and discussion do not provide an end-to-end command,
captured ROCr failure, or test using the public HSA VMM API. The submitted
tests construct DRM structs and issue ioctls directly.

The relevant integration path is newer and narrower than ordinary HIP
allocation:

```text
hsa_amd_vmem_map / hsa_amd_vmem_set_access
  -> ROCr KfdDriver::Map
  -> hsaKmtMemoryVaMap
  -> DRM_AMDGPU_GEM_VA
  -> DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT
```

ROCr commit `b58362f60ff4` added the timeline creation/wait protocol to
`hsaKmtMemoryVaMap/Unmap` on June 23, 2026. rocjitsu's GEM_VA implementation
then landed in the July 19, 2026 integration PR #8672, and this PR followed on
August 2. That sequence explains why many existing HIP end-to-end programs
could pass: the traditional allocation path does not necessarily call these
explicit VMM map/unmap APIs, and tests linked against an older installed ROCr
would not issue the timeline ioctls.

Current ROCr source gives a useful expected pre-fix signature, although the PR
does not record an observed run. During per-GPU FMM setup, failure of
`drmSyncobjCreate` logs `Failed to create VM timeline syncobj`; a later VMM MAP
still issues GEM_VA and then reports
`DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT failed after MAP` when the wait ioctl fails.
The pre-PR rocjitsu GEM_VA handler ignored the timeline fields and applied the
mapping before that unsupported wait failed, so the overall ROCr operation
could return an error after partially mutating the GPU address space.

**DRM-file namespace and binary-syncobj counterexamples:**

I temporarily added two focused tests to `interposer_dup_test`:

1. import a GEM handle through one independent DRM open, then try to MAP it
   through a second independent DRM open;
2. request a GEM_VA output fence on a valid syncobj with
   `vm_timeline_point = 0`, the DRM binary-syncobj form.

```bash
time -p env ROCJITSU_RUNTIME_DIR=$RUNTIME_DIR \
  $BUILD_DIR/tools/rocjitsu/rocjitsu \
  --config $SRC_DIR/emulation/rocjitsu/configs/gfx950_cdna4_kmd.json \
  -- $BUILD_DIR/tests/interposer_dup_test \
  --gtest_filter='InterposerSyncobjReviewTest.*:InterposerGemReviewTest.*'
```

Result: 0/2 passed, 2 failed, 0 skipped, 0 errored in 0.61s real.

The foreign-handle MAP returned success rather than `-1/ENOENT`, and the
point-zero GEM_VA returned `-1/EINVAL` rather than success. Both failures are
genuine PR behavior. The Linux DRM path resolves GEM handles through the
calling `drm_file`, while the AMDGPU GEM_VA path deliberately treats a
nonzero output handle with point zero as replacement of the syncobj's binary
fence.

As a prototype, allowing point zero made the binary-syncobj regression pass.
Checking the `GemEntry::drm_file_id` against the calling DRM-file state made
the foreign MAP reject, although the current boolean helper then collapsed the
failure to `EINVAL`; the production fix needs to preserve the kernel-compatible
`ENOENT` result. All temporary source and test changes were removed, and the
submitted targets were rebuilt.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/kmd/linux/interposer.cpp \
  emulation/rocjitsu/tests/CMakeLists.txt \
  emulation/rocjitsu/tests/interposer_dup_test.cpp

git diff --check origin/develop...HEAD
```

Result: every applicable pre-commit hook passed, and `git diff --check`
passed.

I did not run the full local simulator corpus or a source-matched ROCr VMM
application. The focused run covers every submitted interposer case and both
concrete boundary counterexamples. The public release and sanitizer corpus jobs
provide broader simulator coverage, but the PR does not demonstrate that any
of those jobs executes the explicit ROCr VMM timeline path above.

**Evidence and confidence calibration:**

- The foreign GEM-handle MAP is a directly reproduced correctness bug with
  high confidence: the second independent DRM open successfully installs a
  mapping using the first file's handle. Applying the same ownership boundary
  to UNMAP, CLEAR, and GEM_CLOSE follows from the same file-private namespace,
  but those additional operations should each receive their own regression.
- Point-zero rejection is a directly reproduced DRM API-contract mismatch with
  high confidence. Its demonstrated impact on the motivating ROCr path is
  lower: current ROCr advances its VM timeline from point 1, so this appears to
  be unsupported valid binary-syncobj behavior rather than the immediate cause
  of the reported ROCr VMM failure.
- The pre-PR partial-mutation sequence is source-derived rather than captured
  from an end-to-end run: syncobj creation could fail, GEM_VA could still apply
  the mapping while ignoring timeline fields, and the later timeline wait
  could report the overall operation as failed.
- The invalid-user-pointer and source-matched VMM-test items are strict-review
  hardening suggestions, not blockers established by a current ROCr failure.

## Summary

This PR adds a userspace model of the DRM state current ROCr uses around
explicit HSA virtual-memory updates. This is not a protocol every HIP allocation
uses: the motivating path starts from the `hsa_amd_vmem_*` APIs and reaches
`hsaKmtMemoryVaMap/Unmap`.

The new `DrmFileState` is the central lifetime object. Each synthetic render
node open creates one state, while `dup`, `dup2`, `dup3`, and
`fcntl(F_DUPFD*)` attach additional descriptor numbers to the same
`shared_ptr`. A manual `open_fds` count includes in-flight dup reservations, so
a racing last close cannot reap the DRM file between the real duplication
syscall and interposer bookkeeping. The final descriptor close reaps GEM
objects by a stable DRM-file ID rather than by a reusable descriptor number.

Each DRM-file state also owns a syncobj handle table. A syncobj entry records
whether any fence has been installed plus the highest submitted and signaled
timeline points. Timeline waits resolve their handles under `fd_mutex_`, test
the submitted/signaled watermarks, and block on a condition variable until a
GEM VA update publishes a point or the absolute monotonic timeout expires.
Independent DRM opens therefore get separate syncobj namespaces, while
duplicated descriptors share one.

For GEM_VA, the ioctl rejects input fences because this simulator performs VM
updates synchronously. It looks up an optional output syncobj, performs MAP,
REPLACE, UNMAP, or CLEAR under the same mutex used by GEM bookkeeping, and
publishes the output point only after the page-table operation succeeds. That
lock boundary gives the intended atomic observation: a waiter cannot see the
timeline point before it can see the corresponding mapping mutation.

The main gap is that this new DRM-file identity is not applied consistently to
GEM handle lookup. Imports record `drm_file_id`, and final-close reaping uses
it, but MAP/UNMAP/CLEAR/GEM_CLOSE still operate on one process-global
`gem_entries_` map without checking the calling DRM file. The syncobj namespace
is isolated as intended; the GEM namespace is not.

There is also a smaller but direct UAPI mismatch at point zero. Timeline waits
correctly use point zero for binary syncobjs, but GEM_VA rejects the same
binary form even though the kernel accepts it and the PR's commit description
claims to model it.

## Actionable items

### 1. Scope every GEM operation to the calling DRM file

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/kmd/linux/interposer.cpp:1169-1200,1223-1236,1326-1337,1364-1370,2114-2122,2163-2175`

`prime_import()` records the owning `DrmFileState::id` in each `GemEntry`, but
`gem_map()`, `gem_unmap()`, `gem_clear()`, and `untrack_gem()` receive no DRM
fd or file token. They look up or evict entries from the process-global
`gem_entries_` map solely by handle/address. As a result, an independent DRM
open can use a handle created by another open.

The focused counterexample imported a BO through the first render-node open,
then issued GEM_VA MAP through the second open with the first file's handle.
The submitted interposer returned success and installed the mapping. The real
AMDGPU ioctl resolves the handle through the calling file's GEM handle table
and returns `ENOENT` when it is absent.

Carry the calling `DrmFileState` identity into every GEM operation and require
`GemEntry::drm_file_id` to match before reading or mutating the entry. Apply the
same boundary to:

- MAP, REPLACE, and UNMAP handle lookup;
- CLEAR's address-based eviction, so it cannot clear another DRM file's
  mappings;
- GEM_CLOSE, so one file cannot destroy another file's handle; and
- any future GEM helper that starts from a userspace handle or VM address.

The helper result needs more information than `bool`: unknown/foreign handles
should produce the ioctl's kernel-compatible lookup error (`ENOENT` for
AMDGPU_GEM_VA), while invalid ranges and operations can remain `EINVAL`.
Duplicated descriptors should continue to work because they resolve to the
same `DrmFileState::id`.

Add a regression with two independent opens that proves the second cannot MAP,
UNMAP, CLEAR, or GEM_CLOSE the first file's object, plus a duplicate-fd control
that proves the shared namespace still works.

### 2. Support GEM_VA output syncobjs at point zero

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/kmd/linux/interposer.cpp:1223-1229,1294-1299,1326-1331`

All three GEM mutation helpers reject `timeline && timeline_point == 0`.
Point zero is not an invalid timeline point in the DRM syncobj API: it is the
binary-syncobj form. In AMDGPU GEM_VA, a nonzero
`vm_timeline_syncobj_out` with `vm_timeline_point == 0` replaces the current
binary fence with the VM-update fence.

The focused counterexample created an unsignaled syncobj and requested it as a
MAP output at point zero. The submitted code returned `EINVAL` before applying
the map. Removing these three checks was sufficient for that regression to
pass because `signal_syncobj_locked()` already sets `has_fence` and leaves the
submitted/signaled watermark at zero, which is the representation the wait
path uses for a signaled binary fence.

Allow point zero whenever an output syncobj handle is present. Add direct MAP,
UNMAP, and CLEAR coverage that waits on point zero afterward, and retain a
control showing that handle zero still means "no output syncobj".

This is an actionable contract-completeness issue because point zero is valid
DRM behavior and the commit description claims to model it. It is lower
priority than the GEM namespace violation for the stated ROCr use case:
current ROCr supplies nonzero, incrementing VM timeline points.

## Suggestions

### 1. Copy and validate timeline-wait arrays before blocking

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/kmd/linux/interposer.cpp:971-1018`

`wait_syncobj_timeline()` converts the userspace `handles` and `points`
addresses to raw pointers, dereferences them while holding `fd_mutex_`, and
re-reads `points` on every evaluation. An invalid pointer therefore faults the
process inside the preload library instead of returning `EFAULT`, and a
concurrent caller mutation can change the requested points after the ioctl has
started. The kernel copies both arrays once before entering its wait loop.

Use a fault-tolerant self-copy into local vectors before acquiring the state
lock, return `EFAULT` when either array is inaccessible, and evaluate only the
snapshotted values. Add bad-handle-array and bad-point-array tests. This is
primarily ABI hardening; the ROCr path supplies valid stable arrays.

### 2. Add a source-matched ROCr VMM end-to-end regression

**Files:** `emulation/rocjitsu/tests/CMakeLists.txt:1150-1240` and a new focused
VMM test executable

The PR's direct ioctl tests establish the new primitive's local semantics, but
they reproduce neither the motivating ROCr call chain nor its failure mode.
That leaves integration assumptions untested: per-GPU syncobj creation during
FMM setup, the nonzero sequence point passed to GEM_VA, the subsequent
`WAIT_FOR_SUBMIT` timeline wait, and the error propagation back through
`hsa_amd_vmem_set_access`.

Add a small test linked against the source-matched ROCr build that:

1. reserves a GPU VA range with `hsa_amd_vmem_address_reserve`;
2. creates and maps a VMM allocation handle;
3. sets GPU access, which reaches `hsaKmtMemoryVaMap`;
4. optionally performs a minimal GPU read/write;
5. unmaps and releases the handle.

Run it through the rocjitsu launcher. Before this PR, the expected failure
should include the syncobj-creation warning or the MAP timeline-wait error;
afterward, the complete map/use/unmap sequence should pass. This would explain
the user-visible regression directly and protect the exact integration that
motivates the change.

## Commentary

The `shared_ptr<DrmFileState>` design is a useful extension of the earlier KFD
dup hardening. It distinguishes the descriptor number from the open DRM-file
identity, which is exactly what is needed for duplicate sharing, stale-fd
replacement, and last-close cleanup. The reservation-before-dup sequence is
also well motivated: it keeps the state alive across the only window where the
kernel has created a descriptor but the interposer has not recorded it yet.

The timeline model is intentionally much simpler than a general DRM fence
chain, but it is appropriate for synchronous simulator VM updates: submission
and signaling happen together, so a highest-point watermark captures the
observable wait behavior. Publishing that watermark under the same mutex as
the page-table mutation is the important correctness property.

The absence of an end-to-end reproducer initially makes the scope look broader
than it is. Existing HIP applications can continue to work because normal
allocation and mapping may stay on KFD memory ioctls; this PR is specifically
closing the newer explicit-VMM path after ROCr started attaching DRM timeline
points to `hsaKmtMemoryVaMap/Unmap`.

The PR description should be reconciled with the submitted code. It says
regressing points are rejected without changing mappings, while
`OutOfOrderTimelinePointPreservesWatermark` deliberately accepts point 1 after
point 2 and performs the UNMAP. The implementation matches Linux's permissive
out-of-order timeline insertion more closely than that description, so the
description should state the chosen contract rather than promising rejection.

Finally, the CMake consolidation into `rj_add_interposer_test_suite()` improves
the reviewability of this area: the descriptor, GEM, and syncobj cases now use
one registration path with the same launcher, runtime-directory, installed
test, and skip behavior.

## Appendix A: independent DRM-file GEM namespace regression

This test uses the existing `open_kfd`, `open_drm_render`,
`make_sized_memfd`, `prime_import`, `DRM_AMDGPU_GEM_VA_request`, and
`gem_close` helpers from `interposer_dup_test.cpp`.

```cpp
TEST(InterposerGemTest, IndependentDrmOpenCannotMapForeignHandle) {
  int kfd = open_kfd();
  ASSERT_GE(kfd, 0);
  ASSERT_TRUE(kfd_version_ok(kfd));

  int owner = open_drm_render();
  int foreign = open_drm_render();
  if (owner < 0 || foreign < 0)
    GTEST_SKIP() << "synthetic DRM render node unavailable in this configuration";

  constexpr size_t kBoSize = 0x1000;
  constexpr uint64_t kVa = 0x1000000000ULL;
  int dmabuf = make_sized_memfd(kBoSize);
  ASSERT_GE(dmabuf, 0);

  uint32_t gem_handle = 0;
  ASSERT_TRUE(prime_import(owner, dmabuf, &gem_handle));

  drm_amdgpu_gem_va map{};
  map.handle = gem_handle;
  map.operation = AMDGPU_VA_OP_MAP;
  map.flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE;
  map.va_address = kVa;
  map.map_size = kBoSize;

  const int foreign_map_rc = ioctl(foreign, DRM_AMDGPU_GEM_VA_request(), &map);
  const int foreign_map_errno = errno;
  EXPECT_EQ(foreign_map_rc, -1);
  EXPECT_EQ(foreign_map_errno, ENOENT);

  // Keep cleanup deterministic on the buggy implementation, where the foreign
  // MAP unexpectedly succeeds.
  if (foreign_map_rc == 0) {
    drm_amdgpu_gem_va unmap = map;
    unmap.operation = AMDGPU_VA_OP_UNMAP;
    ASSERT_EQ(ioctl(foreign, DRM_AMDGPU_GEM_VA_request(), &unmap), 0);
  }

  // Control: the owning DRM file must still be able to use its handle.
  ASSERT_EQ(ioctl(owner, DRM_AMDGPU_GEM_VA_request(), &map), 0);
  drm_amdgpu_gem_va unmap = map;
  unmap.operation = AMDGPU_VA_OP_UNMAP;
  EXPECT_EQ(ioctl(owner, DRM_AMDGPU_GEM_VA_request(), &unmap), 0);

  EXPECT_EQ(gem_close(owner, gem_handle), 0);
  EXPECT_EQ(close(dmabuf), 0);
  EXPECT_EQ(close(foreign), 0);
  EXPECT_EQ(close(owner), 0);
  EXPECT_EQ(close(kfd), 0);
}
```

On the reviewed head, `foreign_map_rc` is zero, demonstrating that the second
independent DRM open can use the first file's handle.

## Appendix B: GEM_VA binary-syncobj point-zero regression

This test uses the same existing helpers.

```cpp
TEST(InterposerSyncobjTest, GemVaAcceptsBinarySyncobjPointZero) {
  int kfd = open_kfd();
  ASSERT_GE(kfd, 0);
  ASSERT_TRUE(kfd_version_ok(kfd));

  int drm = open_drm_render();
  if (drm < 0)
    GTEST_SKIP() << "synthetic DRM render node unavailable in this configuration";

  drm_syncobj_create create{};
  ASSERT_EQ(ioctl(drm, DRM_IOCTL_SYNCOBJ_CREATE, &create), 0);

  constexpr size_t kBoSize = 0x1000;
  constexpr uint64_t kVa = 0x1000000000ULL;
  int dmabuf = make_sized_memfd(kBoSize);
  ASSERT_GE(dmabuf, 0);

  uint32_t gem_handle = 0;
  ASSERT_TRUE(prime_import(drm, dmabuf, &gem_handle));

  drm_amdgpu_gem_va map{};
  map.handle = gem_handle;
  map.operation = AMDGPU_VA_OP_MAP;
  map.flags = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE;
  map.va_address = kVa;
  map.map_size = kBoSize;
  map.vm_timeline_syncobj_out = create.handle;
  map.vm_timeline_point = 0;
  ASSERT_EQ(ioctl(drm, DRM_AMDGPU_GEM_VA_request(), &map), 0);

  uint32_t handles[] = {create.handle};
  uint64_t points[] = {0};
  drm_syncobj_timeline_wait wait{};
  wait.handles = reinterpret_cast<uintptr_t>(handles);
  wait.points = reinterpret_cast<uintptr_t>(points);
  wait.count_handles = 1;
  wait.flags = DRM_SYNCOBJ_WAIT_FLAGS_WAIT_ALL;
  EXPECT_EQ(ioctl(drm, DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT, &wait), 0);

  drm_amdgpu_gem_va unmap{};
  unmap.handle = gem_handle;
  unmap.operation = AMDGPU_VA_OP_UNMAP;
  unmap.va_address = kVa;
  unmap.map_size = kBoSize;
  EXPECT_EQ(ioctl(drm, DRM_AMDGPU_GEM_VA_request(), &unmap), 0);

  drm_syncobj_destroy destroy{};
  destroy.handle = create.handle;
  EXPECT_EQ(ioctl(drm, DRM_IOCTL_SYNCOBJ_DESTROY, &destroy), 0);
  EXPECT_EQ(gem_close(drm, gem_handle), 0);
  EXPECT_EQ(close(dmabuf), 0);
  EXPECT_EQ(close(drm), 0);
  EXPECT_EQ(close(kfd), 0);
}
```

On the reviewed head, the GEM_VA MAP returns `-1/EINVAL` before applying the
mapping because all three mutation helpers reject a nonnull syncobj at point
zero.
