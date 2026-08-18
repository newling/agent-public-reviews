## Review follow-up after the `develop` rebase

The branch is rebased onto current `develop`, including the lazy-VGPR storage
change from #9779. The rebase preserves the five-commit structure: all
hand-maintained generator, runtime, and test changes remain below one
generated-only top commit.

The follow-up closes the remaining ownership and boundary issues from review:

- Each wave's `InstructionComputeUnitView` now retains the executing wave.
  Existing generated and shared instruction helpers that accept the CU-shaped
  service view therefore validate physical SGPR/VGPR indices against that wave
  instead of re-attributing escaped indices through the CU reverse map.
- A four-dword gfx1250 buffer descriptor can no longer begin in one wave and
  consume its upper dwords from an adjacent wave.
- Denied VGPR read regions expose explicit ownership validity, independently of
  whether the observed lane mask is empty. Multi-register denied reads return
  bounded zero spans/copies and never expose foreign or undersized storage.
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

Until those implementations are reconciled and one lands, this PR explicitly
fails closed when a trap selector does not fit the live wave's ordinary block.
It no longer silently returns zero, drops a write, or reaches an adjacent
wave's SGPRs.

## Related work

- #9470: closed SGPR write-after-write detector that motivated this
  observation foundation.
- #9578: focused per-wave trap-register storage.
- #9844: broader debugger stack with overlapping trap-register storage.
- #9779: merged lazy-VGPR backing integrated by this rebase.
- #10032: merged model/execution source split followed by the generated output
  in this branch.

## Follow-up validation

- focused register, execution-plugin, hook-ordering, loader, race-detector,
  address-calculation, and wide-conversion coverage passes;
- compiler-backed callable-SGPR probe coverage passes;
- 833 focused generator tests pass with 2 expected skips;
- all-ten-ISA generation is content-idempotent;
- changed-file pre-commit and `git diff --check` pass.
