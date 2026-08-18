This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#10345

**Revision reviewed:** `53b03ce258cc6758f4236abf328292607dd2fe83`

**Review mode:** independent review. I did not read existing PR reviews,
inline comments, review threads, or discussion comments.

**Public/repository status:** the repository, PR, base branch, and head
repository are public. The PR is open, non-draft, mergeable, and currently
labelled `Not ready to Review`.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: the 625-step build passed in 176.24s real, 1301.12s user, and
65.06s sys.

**Submitted behavior and neighboring Wave32 coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Gfx1250ExecutionTest.ScalarMovesTreatS102AndS103AsOrdinarySgprs:Gfx1250ExecutionTest.Wave32VectorComparePreservesVccHiScratch:Gfx1250ExecutionTest.VCmpGtU32Wave32ExplicitSdstPreservesHighSgpr:Gfx1250ExecutionTest.Wave32ScalarVccHiWritePreservesUpperHalf:Gfx1250SimulationTest.Ttmp8*:Gfx1250SimulationTest.TtmpWorkgroupIdsUseGridCoordinatesFor2DDispatch'
```

Result: 7/7 passed, 0 failed, 0 skipped, and 0 errored in 0.90s real.
This exercises the new scalar-selector behavior, both scalar and SIMD
implicit-VCC compare paths, explicit Wave32 mask destinations, raw scalar
VCC_HI writes, TTMP8 wave identity, queue packet identity, and the 2D
grid-valid flag.

**Focused generator tests:**

The first invocation used the sparse worktree's default MRISA path:

```bash
time -p .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_gen_vector_cmpx.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_sema_lower.py
```

Result: 304 passed, 17 failed, and 28 skipped in 1.91s real. Every failure
was a `FileNotFoundError` for a machine-readable ISA XML file absent from the
sparse worktree; none reached the changed generator behavior.

The same selection was rerun against the shared XML checkout:

```bash
time -p env MRISA_PATH=$MRISA_XML_DIR \
  .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_gen_vector_cmpx.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_sema_lower.py
```

Result: 339 passed, 0 failed, 10 skipped, and 0 errored in 11.49s real.
The skips are tests whose optional semantics XML is not present in the shared
XML checkout.

**Merge and diff hygiene:**

```bash
git diff --check <pr-base>..HEAD
git merge-tree --write-tree HEAD origin/develop
```

Both passed. The submitted head merges textually with current `origin/develop`
at the time of review.

**CI context:**

The release, Clang ASan/UBSan, GCC ASan/UBSan, TSan, formatting, CodeQL,
HIP NVIDIA, and multi-architecture summary checks are green. The Systems PR
Bot fails because the PR description contains no issue reference. The latest
TheRock packaging jobs were still running at the time of review; the earlier
red summaries belong to superseded runs whose package jobs were cancelled.

## Summary

This PR corrects three related pieces of architectural wave state.

First, it separates raw VCC storage from its active-lane mask. Scalar
instructions continue to read and write the complete VCC pair, including
VCC_HI scratch in Wave32, while vector predicate and carry producers update
only the lane-width portion through `set_vcc_mask()`. VCCZ now tests the
masked value rather than treating Wave32 VCC_HI scratch as an active predicate
bit.

Second, it makes scalar selectors 102 and 103 architecture-dependent.
Legacy CDNA targets continue to alias them to FLAT_SCRATCH, while GFX10+
targets resolve them as ordinary SGPRs. The gfx1250 decoded-instruction test
covers 32-bit and 64-bit reads and writes and proves that the separate scratch
base remains unchanged.

Third, it completes the gfx1250 TTMP8 launch payload. The low 25 bits receive
the AQL ring slot, bits 29:25 receive the wave index within its workgroup, and
bit 30 records whether Y/Z grid coordinates are valid. The existing TTMP6,
TTMP7, and TTMP9 coordinate layout remains intact.

The implementation is coherent on the exact submitted head. I found no
code-correctness blocker in the paths exercised above. The main work before
landing is repository-policy and stack hygiene, followed by explicit
coordination with the overlapping trap-register, wave-ID, register-access,
debugger, and architecture-renaming PRs.

## Actionable items

### 1. Link the PR to its tracking issue and identify the overlapping wave-ID PR

**Location:** PR description

The Systems PR Bot currently fails with:

```text
PR description must reference a JIRA ID, ISSUE ID, or a GitHub closing keyword.
```

ROCm/rocm-systems#10329 is the specific bug for the missing TTMP8 wave-ID
field, and ROCm/rocm-systems#10335 is the smaller competing implementation of
that fix. This PR contains the complete correction from #10335 plus the queue
packet and grid-valid fields, so the relationship should be explicit.

Add an issue-tracking section such as:

```text
## Issue Tracking

Fixes #10329
Supersedes #10335
```

Use `Supersedes` only after the maintainers agree that #10345 is the selected
implementation; otherwise use `Related: #10335`. The issue reference is
required for CI, and the PR cross-reference prevents two implementations of
the same TTMP8 wave-ID write from being reviewed and landed independently.

### 2. Put checked-in generated output in a generated-only top commit

**Files:**

- `emulation/rocjitsu/lib/python/amdisa/codegen/execute/sema_lower.py:270-280`
- `emulation/rocjitsu/lib/python/amdisa/codegen/execute/vector_cmp.py:159-171`
- `emulation/rocjitsu/lib/python/amdisa/codegen/execute/vector_cmp.py:369-416`
- `emulation/rocjitsu/lib/python/amdisa/codegen/execute/vector_cmp.py:496-501`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/generated/cdna1/vop3_exec.cpp`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/generated/cdna1/vopc_exec.cpp`
- corresponding generated CDNA2, CDNA3, CDNA4, and shared execution files

The PR is one commit containing both hand-maintained generator/runtime/test
changes and nine generated files. rocJITsu's generated-source convention
requires hand-maintained work below one generated-only top commit. That shape
makes regeneration reviewable, permits clean rebases over generator changes,
and is especially important here because ROCm/rocm-systems#10030 and
ROCm/rocm-systems#10137 also touch generator and generated execution output.

Split the current commit into:

1. hand-maintained generator, runtime, and test changes; and
2. a top `chore(rocjitsu): regenerate AMDGPU ISA sources` commit containing
   only checked-in generated output.

Regenerate from the final hand-maintained tree rather than mechanically moving
the current generated diff, then rerun the focused generator selection and
`git diff --check`.

## Suggestions

### 1. Add a direct VCCZ regression for nonzero Wave32 VCC_HI

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h:85-90`
- `emulation/rocjitsu/tests/cdna5_execution_test.cpp:113-139`

`Wave32VectorComparePreservesVccHiScratch` proves that an implicit vector
predicate write preserves VCC_HI, but no test consumes the resulting state
through VCCZ. Add a decoded scalar branch or direct resolver test with:

```text
VCC_LO = 0
VCC_HI = nonzero
wave size = 32
```

and require VCCZ to be true. Also include the complementary nonzero-low-half
case. This directly pins the new `vcc_mask()` contract rather than relying on
the producer-side test to cover it indirectly.

### 2. Cover the scalar-selector policy on both sides of the architecture boundary

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/isa_traits.h:102-123`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/scalar_operand_resolve.h:28-40`
- `emulation/rocjitsu/tests/cdna5_execution_test.cpp:27-111`

The new helper changes shared scalar resolution for every CDNA and RDNA
architecture, but the permanent decoded-instruction regression covers only
gfx1250. Add:

- one legacy CDNA case proving selectors 102/103 still access
  `scratch_base()`; and
- one RDNA case proving they access ordinary SGPR storage.

This is also the right place to reconcile the helper with the generated scalar
selector layout introduced by ROCm/rocm-systems#9578. That PR already derives
the flat-scratch selector from ISA profiles; using the same property would
avoid maintaining a second architecture switch.

### 3. Preserve the five-bit wave-index invariant from the focused fix

**File:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:403-409`

ROCm/rocm-systems#10335 explicitly checks that `wf_index_in_wg` fits the
five-bit TTMP8 field. This PR shifts the value without a mask or assertion.
Valid HSA workgroups fit, but the packet path does not itself validate the
1024-work-item limit before constructing the field.

Retain an assertion or reject an oversized workgroup at packet validation.
Silently allowing bit 5 of the wave index to overlap TTMP8 bit 30 would turn a
malformed dispatch into duplicate wave identities and a corrupted grid-valid
flag.

### 4. Extend the TTMP8 test matrix to both sides of each bitfield boundary

**Files:**

- `emulation/rocjitsu/tests/cdna5_dispatch_memory_test.cpp:320-375`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:79-92`

The submitted tests cover a 2D dispatch, wave indices 0 and 1, and queue slots
0 and 1. Add compact cases showing:

- a 1D dispatch leaves bit 30 clear;
- a 3D dispatch sets bit 30;
- the queue packet field follows the wrapped ring slot; and
- bits 31 and all unassigned bits remain clear at launch.

These are inexpensive and make the packed ABI contract visible without
requiring readers to infer it from masks and shifts.

## Commentary

### Relationship to surrounding rocJITsu work

| Reference | Relationship to this PR |
| --- | --- |
| ROCm/rocm-systems#10335 | Implements only TTMP8[29:25]. #10345 is a functional superset and conflicts in `command_processor.cpp`; choose one implementation. |
| ROCm/rocm-systems#9578 | Moves TTMP/TBA/TMA selectors 108-123 from padded ordinary SGPR storage into dedicated per-wave trap-register storage. If it lands first, #10345 must write TTMP6-9 through that API and remove the 118-SGPR padding requirement. |
| ROCm/rocm-systems#9844 | The broader ROCgdb stack independently carries per-wave TTMP state, AQL packet identity, wave-in-workgroup identity, and workgroup coordinates. #9578 and #9844 already need reconciliation; #10345 should consume the selected storage model instead of creating a third convention. |
| ROCm/rocm-systems#10030 | Establishes wave-owned register observation and changes shared/generated register paths. A merge simulation with the reviewed head is clean, but the combined tree should still be regenerated and rerun because both PRs touch scalar resolution and generated VOPC execution. |
| ROCm/rocm-systems#10137 | Renames the logical gfx1250 architecture identity to CDNA5 and touches `isa_traits.h`, generator code, generated output, and the same tests. Rebase after the naming direction is settled so the new trait does not immediately require a follow-up rename. |
| ROCm/rocm-systems#10346 | Sibling gfx1250 barrier-synchronization work. A merge simulation is currently clean despite five overlapping files. Its generated kernels benefit from correct wave ABI state, so validating the combined stack is still worthwhile. |
| ROCm/rocm-systems#7483 | Established that scalar VCC writes must retain raw Wave32 VCC_HI. This PR correctly adds the complementary masked write API for vector predicate/carry producers. |
| ROCm/rocm-systems#8858 | Established generated ISA-profile properties for architecture policy. The scalar flat-scratch classification should follow that direction when reconciled with #9578. |

The important architectural split is:

```text
raw scalar state:
  set_vcc() / vcc()

active-lane predicate state:
  set_vcc_mask() / vcc_mask()
```

That boundary is clean and mirrors the already-established raw-versus-masked
EXEC API. The generator changes consistently use the masked side for implicit
VCC producers while retaining width-aware explicit SGPR mask writes.

The TTMP8 packet ID is also correctly derived from the AQL ring slot rather
than the monotonic queue read index. The ROCr trap handler reconstructs the
packet index from `(dispatch_ptr - queue_base) >> 6`, which is the same ring
slot represented here.

### Recommended landing sequence

1. Add `Fixes #10329` and settle whether #10345 supersedes #10335.
2. Split the hand-maintained and generated commits.
3. Choose and land the per-wave trap-register storage implementation from
   #9578/#9844, then rebase this PR so TTMP8 uses that storage.
4. Reconcile the generated scalar-selector property with #9578 and the CDNA5
   naming migration in #10137.
5. Regenerate on top of the final hand-maintained stack, including #10030 if
   it has landed.
6. Run the focused C++ and generator selections above, the added VCCZ and
   architecture-boundary tests, changed-file pre-commit, and `git diff --check`.
7. Validate the merged tree with #10346 before the sibling barrier work lands.

After those integration and repository-policy items, the technical content of
the reviewed head looks ready.
