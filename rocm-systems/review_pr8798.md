This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8798

**Commit reviewed:** `24c80ef9c9fa` (`test(rocjitsu): mark packed destinations explicitly`),
the second commit in the PR's two-commit stack.

**Public/repo status:** the repository, PR, base branch, and fork head are
public. The PR is open, not draft, and targets `develop`. GitHub currently
reports the PR as conflicting because `develop` advanced after the PR's base.

**GitHub checks:**

```bash
gh pr checks 8798 --repo ROCm/rocm-systems
```

Result: all visible required checks were passing or skipped as expected,
including release, Clang sanitizer, GCC sanitizer, focused TSan, pre-commit,
CodeQL, package builds, and policy checks.

**Build command:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: passed. Timing: 217.76s real, 1650.64s user, 50.82s sys.

**PR-focused CTest command:**

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure \
  -R '^(RegisterAccessTest\.|ExecutionPluginTest\.)'
```

Result: CTest selected 20 tests: 19 passed, 0 failed, 1 skipped, 0 errored.
Timing: 0.14s real, 0.08s user, 0.06s sys. The skipped test was the existing
`ExecutionPluginTest.MfmaFastPathReadHookReportsRace`, whose SIMD path requires
16-lane `native<float>`.

**Changed generator assertion:**

```bash
time -p $PYTEST_ENV/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py \
  -k 'gfx1250_generated_operand_merges_packed_16bit_destinations'
```

Result: 1 passed, 0 failed, 0 skipped, 117 deselected. Timing: 0.36s real,
2.24s user, 0.04s sys.

The full generator-profile file produced 104 passes, 10 skips, and 4 failures.
All four failures were local-environment artifacts: the sparse review checkout
does not contain the shared machine-readable ISA XML files. The changed
generated-output assertion does not require those XML files and passed. Public
CI also passed the generator/pre-commit coverage on the reviewed head.

**Write-boundary static scans:**

```bash
rg -n -P '\.(read|write)_vgpr\(|\.(read|write)_sgpr\(' \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu \
  emulation/rocjitsu/lib/python/amdisa/codegen \
  -g'*.h' -g'*.cpp' -g'*.py' | rg -v 'RegisterAccess'

rg -n -P 'raw_cu\(|raw_vgpr_(data|reg)|\bSimdAccess::' \
  emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu \
  emulation/rocjitsu/lib/python/amdisa/codegen \
  -g'*.h' -g'*.cpp' -g'*.py' | \
  rg -v 'register_access.h|isa_operand_simd_inl.h'
```

Result: passed. Neither scan found an instruction/generator path that directly
writes raw VGPR storage outside the intended private backend and
`RegisterAccess`.

**Counterexample test:**

I temporarily added a `RegisterAccessTest` that acquired an
`OperandWriteView` with lane 4 as the observed mask, then called
`store_native()` with a chunk mask that writes lane 5. The write changed lane 5,
but no plugin event covered lane 5:

```text
RegisterAccessTest.OperandWriteViewsCannotWriteUnobservedLanes
Value of: lane_five_was_observed
  Actual: false
Expected: true
```

The temporary test was removed after reproducing the issue, and the clean PR
source was rebuilt and retested successfully.

**Pre-commit and diff hygiene:**

```bash
.venv/bin/pre-commit run --files $(git diff --name-only <pr-base>...HEAD)
git diff --check <pr-base>...HEAD
```

Result: both passed.

## Summary

The PR adds a lane-mask- and byte-mask-aware VGPR write hook to the execution
plugin API and routes instruction-visible writes through the `RegisterAccess`
boundary introduced by PR 8417. The hook is propagated through the normal and
profiled plugin groups. Physical VGPR writes, logical operand writes, chunk
writes, SIMD write views, and matrix write regions now notify plugins; raw
memory-pipeline completion writes deliberately remain storage operations and do
not fire the instruction-write hook.

The broad architecture is aligned with the previous register-backdoor work.
Instruction and generator code no longer has direct raw VGPR-write sites, and
the mutable raw storage needed by SIMD/MFMA paths remains behind private operand
backend methods or `RegisterAccess` views. Packed 16-bit scalar operand writes
separately report the preserved-half read and selected-half write with precise
byte masks.

The write-region API is internally consistent: `VgprWriteRegion` stores its
declared lane mask and refuses to mutate lanes outside that mask. The logical
SIMD write views do not have that property. They report the acquisition mask to
plugins, discard it, and later accept an independent store mask. Consequently,
using the intended facade is not by itself sufficient to guarantee that every
written lane was included in a plugin event.

## Actionable items

### 1. Make SIMD write views enforce the mask that was reported to plugins

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/register_access.h:141`

`write_operand()`, `write_operand64()`, `write_operand_pair32()`,
`readwrite_operand()`, and `readwrite_operand64()` notify plugins using the
lane mask supplied when the view is acquired (`register_access.h:665-708`).
Their `store_native()`, `store_narrow()`, and `store_native_pair()` methods
then accept a second independent mask and pass it directly to raw storage
(`register_access.h:147-175`, `195-214`, `248-276`, `311-330`, and
`425-445`).

This permits an actual write outside the observed mask. The counterexample
above acquired a view for lane 4, wrote lane 5 through `store_native()`, and
changed lane 5 without any plugin event covering it. Current SIMD callers
appear to pass matching `exec`/chunk masks, but the API does not enforce that
caller discipline and therefore does not provide the guarantee this PR is
intended to establish.

Carry the observed mask in every mutable operand view and reject or constrain
stores whose global mask `(chunk_mask << lane_base)` is not a subset of it.
Alternatively, move write notification into the store methods and report the
actual global store mask. Apply the same rule to 32-bit, narrow, 64-bit,
pair-32, and read-write views, and add a regression that attempts the mismatched
mask case.

### 2. Resolve the current `develop` conflict without widening the public raw-read API

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:466`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/memory_pipeline.cpp:119`

The PR adds public virtual `read_vgpr_raw()` and uses it from memory completion
and DS completion logging. Current `develop` independently fixed the same D16
false-firing problem by keeping the hook-free read local to
`vector_complete()`, using existing raw storage. This is the sole content
conflict reported by a merge-tree check.

When rebasing, keep `develop`'s localized D16 storage-read approach and avoid
retaining `read_vgpr_raw()` as another generally callable hook-free CU API.
Use a similarly local raw-storage read for the DS diagnostic if it still needs
one. This keeps the intentional VM/storage exception narrow and avoids
creating a conveniently named escape hatch that future instruction helpers
could misuse.

## Suggestions

### 1. Add an instruction-level VGPR write-hook regression

**File:** `emulation/rocjitsu/tests/execution_plugin_test.cpp`

The new direct `RegisterAccessTest` coverage is useful, and the static scans
show that current generated instruction code uses the facade. An execution
test that runs one SIMD VALU instruction and verifies the destination physical
register, active lane mask, and byte mask would pin the cross-module contract
from generated instruction through `RegisterAccess` to the plugin group. A
64-bit destination case would also verify that both physical VGPR halves are
reported.

## Commentary

The central design direction is good: plugin observation belongs at the
instruction-facing `RegisterAccess` boundary, not in raw register storage,
because memory completions and runtime setup intentionally use the same
physical storage without representing synchronous instruction writes.

The remaining issue is not another discovered raw-write backdoor; the static
boundary scans were clean. It is that the new mutable SIMD view API separates
"mask reported to plugins" from "mask actually written" without preserving an
invariant between them. Closing that gap would make the facade itself enforce
the guarantee instead of relying on every current and future SIMD caller to
keep two masks synchronized.
