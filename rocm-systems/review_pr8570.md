This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8570
**Commit reviewed:** `93947b597cc85999f5de22d7f3d1e55442a935c9` (`rocjitsu: fix RDNA dispatch work-item state`)

**Public/repo status:** the repository is public, and the PR head is in the same public repository.

**Build command:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

Result: passed. The build reran CMake, rebuilt and linked `rocjitsu_tests`,
and completed in 120.08s real time.

**Focused CTest command:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R 'RdnaDispatchTest\.PackedTidHonorsRequestedComponents|DispatchEntryTest\.InitialExecMask|Gfx1250SimulationTest\.(MultiWaveDispatchHonorsPackedTidComponentCount|PartialWorkgroupMasksTailWaveExec|PartialGridTailMasksFinalWorkgroupExec|Partial2DGridTailMasksNonContiguousExecLanes|PartialFinalWorkgroupRoundsUpDispatchCount2D)|ConfigLoaderTest\.LoadRdnaKmdConfigs' \
  --output-on-failure --timeout 120
```

Result: passed. CTest selected 9 tests: 9 passed, 0 failed, 0 skipped,
0 errored. CTest reported 3.84s real time.

**Whitespace check:**

```bash
git diff --check origin/develop...HEAD
```

Result: passed with no whitespace errors.

**CI status at review time:** `pre-commit`, `test (release)`,
`test (asan-ubsan)`, the HIP NVIDIA summary, and the labeler were passing.
`test (asan-ubsan-gcc)` and one TheRock package build were still pending.
Two TheRock package builds were marked failed, but GitHub reported the package
workflow was still in progress and did not make failed logs available through
`gh run view --log-failed`, so I did not classify those package failures.
`therock-pr-bot` was failing with PR metadata policy errors; see actionable
item 1.

## Summary

This PR fixes rocjitsu dispatch initialization for packed work-item IDs and
partial-grid EXEC masks. RDNA3, RDNA3.5, and RDNA4 configs now use the packed
TID path that was already used by CDNA3, CDNA4, and gfx1250. The packed path
still always supplies X in `v0`, but it only packs Y and Z when
`TIDIG_COMP_CNT` requests those components, leaving unrequested packed fields
zero.

The PR also moves local work-item coordinate decomposition into a shared helper
and records the AQL grid extents on each kernel `DispatchEntry`. Initial EXEC
mask generation now walks lanes and masks off work-items outside the actual
grid, so final workgroups and multidimensional grid tails do not leave
out-of-grid lanes active. Both the command-processor dispatch path and the SPI
queue path now pass the global workgroup id into that helper, with the helper
subtracting `workgroup_id_offset` before converting the workgroup ordinal back
to grid coordinates.

The new and updated tests cover RDNA packed-TID component counts, gfx1250
packed-TID component counts, wave64 and multidimensional tail masks, partial
final workgroups, workgroup offsets, and config-loader packed-TID expectations.

## Actionable items

### 1. Fix the PR metadata policy failures

**Location:** PR metadata

The policy bot is failing for two PR metadata reasons:

```text
Title does not follow Conventional Commits style.
PR description must reference a JIRA ID, ISSUE ID, or a GitHub closing keyword.
```

The current title starts with `[rocjitsu]`, and the PR body has `JIRA ID` set
to `N/A`, which the policy checker does not accept as a valid reference.

Change the title to a Conventional Commits form such as:

```text
fix(rocjitsu): fix RDNA dispatch work-item state
```

Also update the PR description to include an accepted JIRA ID, issue ID, issue
URL, or closing-keyword reference. This appears to be the confirmed
PR-specific CI blocker.

## Suggestions

### 1. Consider adding CDNA coverage for packed-TID component counts

**File:** `emulation/rocjitsu/tests/amdgpu_vm_test.cpp:397`

`PackedTidHonorsRequestedComponents` covers RDNA3, RDNA3.5, and RDNA4, and the
gfx1250 simulation test covers gfx1250. The same implementation path is also
used for CDNA3 and CDNA4 through `CommandProcessor::packed_tid()`, and this PR
changes the packed component-count behavior for every packed target.

Consider extending the focused component-count test to include CDNA3 and CDNA4
as well, or add a short comment explaining why the RDNA/gfx1250 coverage is
the intended scope here.

### 2. Check the CDNA2/gfx90a packed-TID classification against LLVM

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.cpp:441`

The `packed_tid` architecture list includes CDNA3, CDNA4, RDNA3, RDNA3.5,
RDNA4, and gfx1250, but not CDNA2/gfx90a. LLVM currently defines
`FeaturePackedTID` as "Workitem IDs are packed into v0 at kernel launch" and
includes that feature in `FeatureISAVersion9_0_A`, the gfx90a feature set:

```text
https://github.com/llvm/llvm-project/blob/3eb929be5e17d66900020bd1caa7d2510d4f9601/llvm/lib/Target/AMDGPU/AMDGPU.td#L1340-L1342
https://github.com/llvm/llvm-project/blob/3eb929be5e17d66900020bd1caa7d2510d4f9601/llvm/lib/Target/AMDGPU/AMDGPU.td#L1805-L1816
```

LLVM's AMDGPU lowering also uses `VGPR0` masks for packed work-item Y and Z
when `hasPackedTID()` is true, while the non-packed path allocates `VGPR1` and
`VGPR2`:

```text
https://github.com/llvm/llvm-project/blob/3eb929be5e17d66900020bd1caa7d2510d4f9601/llvm/lib/Target/AMDGPU/SIISelLowering.cpp#L2864-L2892
```

LLVM's AMDGPU usage documentation also lists gfx90a with packed work-item IDs:

```text
https://github.com/llvm/llvm-project/blob/3eb929be5e17d66900020bd1caa7d2510d4f9601/llvm/docs/AMDGPUUsage.rst#L482-L488
```

If rocjitsu's CDNA2 launch-state model is intended to differ from LLVM's gfx90a
model, add a comment explaining the distinction. Otherwise, include CDNA2 in
the packed-TID classification and add regression coverage for it.

## Commentary

I did not find code-level blockers in the dispatch changes. The new
`initial_exec_mask_for_wave()` shape is more explicit than the old
workgroup-size-only mask: it handles the original intra-workgroup tail case and
also models final-grid bounds in X/Y/Z. The `workgroup_id_offset` handling is
consistent with the existing multi-XCD tests, which dispatch each command
processor a local one-dimensional slice and use the offset for global workgroup
IDs.

The packed-TID change also keeps the ABI behavior clear at the initialization
site: packed targets write only `v0`, while unpacked targets continue to write
`v0`, `v1`, and `v2` according to the requested component count.
