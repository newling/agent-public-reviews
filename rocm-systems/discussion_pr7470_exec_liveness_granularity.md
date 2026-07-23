# PR 7470: EXEC and liveness granularity

This document accompanies [the PR 7470 review](review_pr7470.md). It separates
three analysis designs that can sound similar in discussion but have materially
different scope:

1. the PR's `Full`/`Unknown` EXEC state;
2. per-bit EXEC facts with whole-register liveness;
3. per-lane VGPR liveness.

The immediate PR goal is to recover safe full-register kills for
EXEC-masked vector definitions. This discussion is about possible follow-up
precision, not additional merge requirements for the current PR.

## The liveness problem

An AMDGPU VGPR contains one value per wave lane. An EXEC-masked definition
updates active lanes and preserves inactive lanes:

```text
for each lane:
    if EXEC[lane]:
        destination[lane] = result
    else:
        destination[lane] remains unchanged
```

Consequently, a vector definition kills the complete old register value only
when every lane is definitely overwritten. PR 7470 proves that condition by
tracking whether EXEC is definitely full before each instruction.

## Design 1: `Full` or `Unknown`

The PR uses:

```cpp
enum class ExecState : uint8_t {
  Full,
  Unknown,
};
```

`Unknown` means only that full EXEC has not been proven. It includes partial,
empty, data-dependent, and otherwise unmodeled masks.

The forward meet is:

```text
meet(Full, Full)       = Full
meet(Full, Unknown)    = Unknown
meet(Unknown, Unknown) = Unknown
```

The backward liveness rule is:

```text
if a definition is EXEC-masked and EXEC is not Full:
    do not kill its VGPR/AccVGPR destination
```

### Advantages

- Very small state.
- Fast convergence.
- Simple soundness argument.
- Directly answers the current consumer's yes/no question.
- Unknown instructions and values degrade conservatively.

### Precision limitation

The state cannot accumulate known-one bits across partial writes:

```asm
; Wave64, initial EXEC unknown
s_mov_b32 exec_lo, -1
s_mov_b32 exec_hi, -1
```

The submitted domain remains `Unknown` after both writes even though the final
EXEC value is full.

## Design 2: per-bit EXEC facts, whole-register liveness

A modest extension is:

```cpp
struct ExecState {
  uint64_t must_one;
  uint64_t must_zero;
};
```

A bit in `must_one` is definitely one on every path reaching the program point.
A bit in `must_zero` is definitely zero. A bit in neither mask is unknown.

The CFG meet is independent bitwise intersection:

```cpp
joined.must_one = left.must_one & right.must_one;
joined.must_zero = left.must_zero & right.must_zero;
```

For example:

```text
Path A must_one = 0x00000000ffffffff
Path B must_one = 0xffffffff00000000

Join must_one   = 0x0000000000000000
```

Every path has 32 known-one bits, but no individual bit is one on both paths.

Full EXEC is:

```cpp
state.must_one == active_wave_mask
```

The liveness representation can remain unchanged: one live/dead bit per
physical register. The richer EXEC state merely proves the existing
whole-register kill condition more often.

### Useful transfer rules

For a constant assignment to a positioned EXEC subregister:

```text
unaffected bits:
    preserve existing facts

affected constant-one bits:
    add to must_one, remove from must_zero

affected constant-zero bits:
    add to must_zero, remove from must_one

affected unknown bits:
    remove from both
```

For simple whole-mask operations with a known constant `C`:

```text
EXEC | C:
    must_one'  = must_one | C
    must_zero' = must_zero & ~C

EXEC & C:
    must_one'  = must_one & C
    must_zero' = must_zero | ~C

EXEC ^ C:
    bits selected by C exchange must_one and must_zero

~EXEC:
    must_one'  = must_zero
    must_zero' = must_one
```

Unrecognized writes can conservatively clear facts for the affected active
bits.

### Benefits beyond the current domain

- Consecutive half-writes can establish full EXEC.
- Writes to inactive Wave32 `exec_hi` bits are naturally state-neutral.
- A 64-bit value with low 32 bits set can establish Wave32 full EXEC even if
  its inactive high half is not all ones.
- `must_zero` can prove definitely empty EXEC and can support NOT/XOR transfer
  rules.
- Other analyses can inspect partial known masks without changing liveness.

### Costs

The bitwise transfer operations themselves are cheap. The more relevant costs
are:

- larger states and instruction snapshots;
- a taller fixed-point lattice, since individual facts can disappear across
  iterations;
- more semantic transfer rules to validate;
- greater risk that an incorrect positive fact produces an unsafe kill.

The solver also needs an explicit unreachable or uninitialized state. For a
must analysis, interior blocks begin with every possible fact and lose facts as
predecessors become known. With two masks, "every bit is both definitely one
and definitely zero" is best treated as the no-reachable-predecessor state,
not as an ordinary EXEC value.

### Saved EXEC values are orthogonal

Per-bit EXEC state does not require tracking SGPR provenance:

```asm
s_mov_b64 exec, s[0:1]
```

may simply clear all `must_one` and `must_zero` facts. Remembering that
`s[0:1]` contains a previously saved EXEC mask is a separate value-analysis
extension. It can be added only if real workloads justify the complexity.

### Expected practical value

For the current liveness consumer, the immediate benefit remains:

```text
prove Full at more program points
    -> recognize more whole-register kills
    -> find more or lower scratch VGPRs
```

The right next step would be instrumentation rather than immediate
implementation. Count:

- partial constant EXEC writes encountered from `Unknown`;
- points where a `must_one` prototype reaches full but the two-state analysis
  remains unknown;
- additional liveness kills;
- changed `find_free_run()` results.

If these counts are negligible on the corpus, the two-state representation is
the better engineering tradeoff.

## Design 3: per-lane VGPR liveness

True lane-wise liveness changes the register state itself:

```text
live[v0] = bitmask of v0 lanes whose current values may be read later
```

The backward transfer for a register is:

```text
LiveIn[r] =
    UsedLanes[r]
    union
    (LiveOut[r] minus DefinitelyWrittenLanes[r])
```

At a CFG branch, successor liveness is unioned per lane because liveness is a
may property:

```text
LiveOut[B][r] = union of LiveIn[S][r] for each successor S
```

### Complementary partial definitions

This analysis can establish complete death even when no one instruction runs
under full EXEC:

```asm
; old v0 exists

; exactly lanes 0-31 active
v_mov_b32 v0, s0

; exactly lanes 32-63 active
v_mov_b32 v0, s1

; all lanes active
v_add_f32 v2, v0, v1
```

Working backward:

```text
before the use:
    all v0 lanes live

cross the high-half definition:
    only low v0 lanes live

cross the low-half definition:
    no old v0 lanes live
```

The old value before the first definition is completely dead even though
neither definition is a whole-register kill. Whole-register liveness cannot
express this composition.

### Potential consumers

- More precise scratch-register availability.
- Lane-aware reaching definitions and use-def chains.
- Detecting reads of lanes without reaching definitions.
- Dead-code analysis for instructions whose written lanes are unused.
- More selective save/restore planning.
- In much more ambitious work, packing values with disjoint lane populations
  into one physical VGPR.

### Costs and difficulty

This is substantially larger than per-bit EXEC state:

- Liveness storage grows from approximately one bit per register to up to 64
  bits per register.
- Instruction-level snapshots can become much larger.
- Uses and definitions can execute under different masks.
- Runtime comparisons produce data-dependent EXEC masks whose concrete lanes
  cannot be known statically.
- Calls, loops, reconvergence, WQM/WWM behavior, and EXEC restores complicate
  lane provenance.
- Physical instructions name whole VGPRs, so exploiting disjoint lane
  occupancy requires preserving the masks under which each value is valid.

Exact lane reasoning quickly becomes symbolic predicate analysis:

```text
EXEC = old_EXEC & (v0 < v1)
```

A fixed known-one/known-zero abstraction must forget most bits after such an
operation. Symbolically retaining the predicate is possible, but it is a
different scale of analysis.

## Relation to LLVM AMDGPU

LLVM's `LaneBitmask` and live-interval subranges generally refer to
subregister coverage, such as low/high pieces or tuple components. They are not
one live interval per AMDGPU work-item lane.

LLVM has additional advantages while compiling:

- SSA virtual registers;
- PHIs and structured divergent control flow;
- explicit compiler-created EXEC transitions;
- value provenance before physical-register reuse.

The AMDGPU backend linearizes divergent regions by saving, masking, and
restoring EXEC, and VALU instructions carry EXEC dependencies. Ordinary
machine liveness can primarily track virtual register values and
subregisters. Rocjitsu analyzes already allocated physical ISA, after many SSA
values have reused the same physical VGPR, so it must reconstruct the
lane-preservation facts needed for safe binary transformation.

PR 7470 should therefore not be viewed as recreating LLVM's register
allocator. It recovers one fact from final ISA that is especially valuable to
physical-register liveness: whether a vector definition overwrites every wave
lane.

## Recommendation

For PR 7470:

1. Keep whole-register liveness.
2. Fix the submitted active-wave-mask classification and conservative
   descriptor fallback described in [the review](review_pr7470.md).
3. Merge the two-state EXEC analysis once those contracts are correct.

For a possible follow-up:

1. Instrument real kernels to measure missed full-EXEC proofs.
2. Prototype `must_one`, adding `must_zero` only if transfer rules need it.
3. Materialize only `Full`/not-`Full` for liveness queries to limit memory
   growth.
4. Consider true per-lane VGPR liveness only if complementary partial
   definitions measurably block scratch allocation.

This sequence preserves the current PR's clear abstraction boundary and makes
additional complexity contingent on demonstrated benefit.
