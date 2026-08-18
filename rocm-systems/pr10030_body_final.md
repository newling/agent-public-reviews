## Summary

rocJITsu execution plugins receive callbacks while simulated GPU instructions
run. Analyses built on those callbacks need register reads and writes to be
attributed to the correct wavefront and reported before register storage is
accessed.

Previously, SGPR and VGPR observation followed different paths. Some accesses
carried the executing wave explicitly, while others inferred it from a
physical register index. SGPR writes also had no instruction-level callback.
This could make ownership ambiguous and allowed multi-register operations to
cross a wave's register boundary partially.

This PR establishes one contract for instruction-visible register access. A
valid SGPR or VGPR access belongs entirely to one live wavefront, produces the
corresponding plugin callbacks, and only then reads or modifies storage.
Accesses that do not fit within that wave's physical register block are
rejected without partial callbacks or storage effects.

Ownership uses the physical register block reserved for the wave rather than
the kernel descriptor's requested count. Descriptor counts remain useful
resource metadata, but callable code may use registers beyond the entry
kernel's reported count. Observation therefore uses the complete physical
block reserved for the wave.

Raw VM operations such as dispatch initialization and memory completion remain
separate. They update register storage without pretending to be
instruction-level accesses.

## Scope

This is foundational register-observation work. It:

- adds the missing SGPR-write callback;
- aligns SGPR and VGPR ownership;
- makes complete multi-register operations range-atomic;
- updates generated instruction paths to preserve the executing wave;
- reports physical register capacities consistently to plugins;
- clears ownership mappings when waves release their resources; and
- keeps denied read/write views inert without exposing foreign storage.

It does not add a new race-detector category or change wait-counter behavior.
This work was extracted from closed PR #9470, which combined the infrastructure
with SGPR write-after-write detection. That detection can return as a smaller
consumer of this foundation.

## Review follow-up after the `develop` rebase

The branch is rebased onto current `develop`, including the lazy-VGPR storage
change from #9779. The history contains five hand-maintained commits followed
by one generated-only top commit.

The follow-up closes the remaining ownership and boundary issues from review:

- Each wave's `InstructionComputeUnitView` retains the executing wave.
  Existing generated and shared instruction helpers that accept the CU-shaped
  service view therefore validate physical SGPR/VGPR indices against that wave
  instead of re-attributing escaped indices through the CU reverse map.
- A four-dword gfx1250 buffer descriptor can no longer begin in one wave and
  consume its upper dwords from an adjacent wave.
- Denied VGPR read regions expose explicit ownership validity independently of
  whether the observed lane mask is empty. Multi-register denied reads return
  bounded zero spans/copies.
- Wide gfx1250 pack/unpack conversions validate complete source and destination
  regions before producing destination effects. Runtime coverage includes
  unpack-source, unpack-destination, pack-source, and pack-destination
  boundaries.
- The generated SDWA scalar destination is pinned to one atomic
  `write_sgpr64()` operation.
- Released-wave ownership tests no longer require freed lazy register storage
  to remain readable.

## Trap-register relationship

Selectors 108-123 are architectural per-wave TTMP/TBA/TMA state, not ordinary
SGPR storage. Dedicated trap-register storage remains deliberately separate
from this observation PR:

- #9578 is the focused per-wave trap-register storage implementation.
- #9844 contains overlapping trap-register storage as part of the broader
  debugger stack.

Until those implementations are reconciled and one lands, this PR fails closed
when a trap selector does not fit the live wave's ordinary block. It no longer
silently returns zero, drops a write, or reaches an adjacent wave's SGPRs.

The model/execution source split from merged PR #10032 is also reflected in
this branch's generated execution output.

## Testing

Validation on the final rebased tree includes:

- a 325-step focused build of `rocjitsu_tests` and the logging/race plugins;
- 175 focused C++ tests passed with one expected SIMD-capability skip;
- 37 additional address-calculation, SMEM, and MUBUF tests passed;
- 4 compiler-backed callable-SGPR probe tests passed;
- 833 focused generator tests passed with 2 expected skips;
- all-ten-ISA generation is content-idempotent; and
- changed-file pre-commit and `git diff --check` pass.

Coverage includes adjacent-wave SGPR/VGPR access, complete-range rejection,
released-wave ownership, zero-mask validity, GPR indexing, callable
beyond-descriptor SGPR use, wide conversion boundaries, and generated SDWA
atomicity.

## Issue Tracking

Related: #9577

Foundational work extracted from closed PR #9470.

Related trap-register work: #9578 and #9844.
