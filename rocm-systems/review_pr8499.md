This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8499
**Commit reviewed:** `49088efc01366beac17d2193173c7a4f71202e8b` (`rocjitsu: fix RDNA WGP and wave32 EXEC semantics`)

**Public/repo status:** the repository is public, and the PR head is in the same public repository.

**Build command:**

```bash
time -p cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests
```

Result: passed. The build reran CMake, rebuilt and linked `rocjitsu_tests`, and completed in 117.81s real time.

**Focused CTest command:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -R 'RdnaDispatchTest|CheckpointTest\.SaveAndRestoreWave32ExecScratch|CodeObjectPatcher\.AppliesArchSpecificWgpModeBit|ExecMaskTest|Rdna4ExecMaskTest|DppPermuteTest\.(RdnaGeneratedVcmpxDppWave32WriteMaskPreservesExec|Gfx1250GeneratedVcmpxDppWave32WriteMaskPreservesExec)|Gfx1250ExecutionTest\.(DsAtomicAsyncBarrierArriveFlipsRawBarrierPhase|LocalMemPipelineUsesInjectedBarrierDecrementPayload)|InstructionExecutionHarness\.Rdna4' \
  --output-on-failure --timeout 120
```

Result: passed. CTest selected 19 tests: 19 passed, 0 failed, 0 skipped, 0 errored. CTest reported 1.91s real time. This covered the new RDNA WGP dispatch tests, the wave32 raw-EXEC checkpoint and scalar-scratch tests, descriptor WGP-mode patching, generated VCMPX/DPP EXEC preservation, and the gfx1250 local-memory pipeline tests affected by the LDS routing constructor change.

**Whitespace check:**

```bash
git diff --check origin/develop...HEAD
```

Result: passed with no whitespace errors.

**CI status at review time:** `pre-commit`, `test (release)`, `test (asan-ubsan)`, `test (asan-ubsan-gcc)`, CodeQL analysis, and TheRock package/summary jobs were passing. `therock-pr-bot` was failing in the "Enforce policy" step; see actionable item 1.

## Summary

This PR adds explicit RDNA WGP-mode handling in rocjitsu and separates active-lane EXEC semantics from raw architectural EXEC storage for wave32.

For WGP mode, the command processor now detects `COMPUTE_PGM_RSRC1.WGP_MODE` through an ISA trait, validates LDS capacity against a sibling-CU WGP pool, and asks the SPI to reserve a paired-WGP LDS backing. WGP-mode wavefronts still execute on one physical CU, but DS/local-memory operations route through the placement-selected `Wavefront::lds()` backing, allowing a workgroup to address the combined LDS capacity of the sibling pair. CU-mode and WGP-mode residency are kept mutually exclusive for a sibling pair.

For wave32 EXEC, `Wavefront::exec()` now returns only active lane bits while `exec_raw()` exposes the full architectural pair. Generated scalar operand code reads and writes raw EXEC for scalar selector values, while vector/memory execution continues to use masked active-lane EXEC. Checkpointing saves and restores raw EXEC so wave32 `EXEC_HI` scratch state survives round trips.

The tests exercise WGP-mode capacity/routing/rejection cases, raw EXEC preservation through checkpoint and scalar instructions, generated VCMPX/DPP writes preserving `EXEC_HI`, and the descriptor patcher's WGP-mode bit policy.

## Actionable items

### 1. Fix the PR title policy failure

**Location:** PR metadata

The live PR title is:

```text
[rocjitsu] Support RDNA WGP mode and fix wave32 EXEC semantics
```

The repository policy requires Conventional Commits style:

```text
type(optional-scope): short description
```

with a lowercase/digit/hyphen optional scope. That is why `therock-pr-bot` is failing in the policy step even though the compile/test jobs are green.

Change the title to something like:

```text
fix(rocjitsu): support RDNA WGP mode and preserve wave32 EXEC_HI
```

or another policy-compliant title under the 80-character title limit.

### 2. Reject WGP-mode clustered dispatches with a runtime error

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:744`

The clustered-dispatch path only has a debug assertion for the new WGP-mode incompatibility:

```cpp
if (entry.has_workgroup_clusters()) {
  assert(!entry.wgp_mode && "workgroup clusters are gfx1250-only and use CU mode");
  ...
```

In non-assert builds, an AMD extended dispatch whose kernel descriptor has `WGP_MODE` set would enter the cluster planner anyway. That path reserves ordinary CU-local LDS and never uses `ShaderProcessorInput::allocate_workgroup()` or the paired-WGP LDS reservation, so the dispatch would silently ignore the descriptor's WGP placement semantics.

If WGP-mode clusters are intentionally unsupported, replace the assertion with an explicit runtime check before the cluster planner runs:

```cpp
if (entry.has_workgroup_clusters() && entry.wgp_mode) {
  throw std::runtime_error("WGP-mode workgroup clusters are not supported");
}
```

Add a regression test using an RDNA architecture, a descriptor with `WGP_MODE` set, and an AMD extended dispatch with `cluster_size_x > 1`, and check that both debug and release builds reject it. If WGP-mode clusters are intended to work later, this path needs a cluster-aware WGP placement implementation rather than falling through to CU-local placement.

## Suggestions

### 1. Consider reducing the boilerplate in the runtime WGP-mode trait dispatch

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/isa_traits.cpp:19`

`arch_supports_wgp_mode()` is correct, and the `ROCJITSU_CODE_ARCH_NUM_ARCHS` static assertion is useful because it forces new architectures to be classified. But the function is mostly a long enum-to-ISA switch that repeats the same pattern for every architecture:

```cpp
case ROCJITSU_CODE_ARCH_RDNA4:
  return HasWgpMode<rdna4::Isa>;
```

This is not blocking, but it may be worth simplifying if more runtime ISA-property queries are expected. Options include centralizing enum-to-trait dispatch in one helper, or using a small table/helper for properties that are already family-level. Keep the exhaustive-new-architecture guard either way; that is the valuable part of the current shape.

### 2. Consider extracting the dispatch LDS-capacity calculation

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:986`

The block that computes `lds_capacity`, aligns `group_segment_fixed_size`, and emits WGP-vs-CU error messages is readable now, but it is a new policy decision inside the already large `process_aql_packet()` path. If this grows or gets reused by other packet paths, extracting a helper such as `validate_dispatch_lds_capacity()` would make the WGP/CU distinction easier to test directly and would keep packet decoding separate from resource-policy validation.

## Commentary

The split between `exec()` and `exec_raw()` is the right abstraction for wave32: vector execution and memory masks need active lanes, while scalar operand selectors need the whole architectural register pair. The generated operand changes are mechanical and consistent with that contract.

The WGP LDS design is also reasonably contained. The SPI owns the paired-CU LDS backing and reservation map, while wavefronts only carry the placement-selected `Lds*`. That keeps local-memory execution independent of whether the workgroup came from CU mode or WGP mode.

The mention of gfx1250 in the PR description appears to be about the DBT flow: gfx1250 is the source code object being translated to the simulated RDNA4 target. It is also explicitly kept out of WGP mode because this code models `WGP_MODE` as unavailable for gfx1250. The CDNA targets such as gfx950/gfx942 are outside this WGP-mode path; the new trait marks CDNA as not supporting WGP mode.

The `exec()` / `exec_raw()` distinction is clear at the `Wavefront` API boundary, and the changed generated scalar operand code now uses `exec_raw()` where scalar selectors need the full register pair. The remaining broad `exec()` uses I checked are in vector execution, address calculation, DPP/SDWA, memory masks, and EXECZ-style active-lane queries, where the lane-masked view is the intended one.

The new loop in `CommandProcessor::notify_wg_complete()` that calls `release_wgp_workgroup()` is related to the core WGP change. It releases the SPI-owned WGP reservation when the workgroup lifetime ends, allowing the paired-WGP LDS allocator to reset after the last resident WGP-mode workgroup retires.
