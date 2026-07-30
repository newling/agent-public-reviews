This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8344

**Review mode:** independent review. I did not read existing GitHub review
threads or discussion comments.

**Commit reviewed:** `42aa6b062cdd` (`adding store negative case`), the current
PR head.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, and GitHub reports it as mergeable. The
required HIP NVIDIA and TheRock summary checks pass; the visible release,
Clang/GCC ASan/UBSan, TSan, pre-commit, and package-build checks also pass.

The active development checkout contained unrelated files, so I exported the
public PR merge into a disposable source snapshot rather than switching that
checkout.

**Configuration:**

```bash
time -p cmake -S $SRC_DIR/emulation/rocjitsu -B $BUILD_DIR -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=/opt/rocm-7.2.0/lib/llvm/bin/clang \
  -DCMAKE_CXX_COMPILER=/opt/rocm-7.2.0/lib/llvm/bin/clang++ \
  -DBUILD_TESTING=ON
```

Result: configuration and generation passed in 7.39s real.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: `rocjitsu_tests` built and linked successfully. After the exploratory
counterexamples and prototypes were removed, I verified every temporarily
edited source blob against the submitted merge and rebuilt the eight
invalidated steps in 23.56s real, 58.16s user, and 1.91s sys.

**Submitted D16 def/use coverage:**

```bash
D16_FILTER='GeneratedInstDefUse.D16HiLoadReadsDestination:\
GeneratedInstDefUse.D16LoLoadReadsDestination:\
GeneratedInstDefUse.RegularLoadDoesNotReadDestination:\
GeneratedInstDefUse.D16BufferLoadReadsDestination:\
GeneratedInstDefUse.D16DsLoadReadsDestination:\
GeneratedInstDefUse.D16TbufferLoadReadsDestination:\
GeneratedInstDefUse.D16StoreDoesNotDefineData'

time -p $BUILD_DIR/tests/rocjitsu_tests --gtest_filter="$D16_FILTER"
```

Result on the restored submitted source: 7/7 passed, 0 failed, 0 skipped,
0 errored in less than 0.01s real.

**gfx1250 destination-bank counterexample:**

I added a temporary liveness regression containing:

```text
s_set_vgpr_msb <DST bank 2>
buffer_load_d16_u8 v1, ...
s_endpgm
```

The load preserves half of its destination, so physical `v513` (`v1` in
destination bank 2) must be live before the instruction. On the submitted code:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='LivenessAnalysis.Gfx1250D16LoadPreserveReadResolvesDestinationBank'
```

Result: 0/1 passed in less than 0.01s real:

```text
Actual:   liveness.is_live_before(load, VGPR 513) == false
Expected: true
```

The existing tests instantiate `InstDefUse` without gfx1250's VGPR-MSB
analysis, so they do not exercise the production liveness path that drops raw
VGPR entries from `implicit_uses()`.

**MUBUF format-load counterexample:**

I decoded CDNA3 `buffer_load_format_d16_x v5, ...` and required `v5` to be both
a def and a use. The submitted decoder reports the def, but not the preserved
destination read:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='GeneratedInstDefUse.D16MubufFormatLoadReadsDestination'
```

Result: 0/1 passed in less than 0.01s real:

```text
Actual:   idu.uses.contains(VGPR 5) == false
Expected: true
```

**Prototype validation:**

For the gfx1250 case, I temporarily added an operand-backed
`implicit_use_operands()` override for one D16 VBUFFER load. For the MUBUF case,
I temporarily added the equivalent `implicit_uses()` override to
`buffer_load_format_d16_x`. The two counterexamples and all seven submitted
D16 tests then passed:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter="$D16_FILTER:\
GeneratedInstDefUse.D16MubufFormatLoadReadsDestination:\
LivenessAnalysis.Gfx1250D16LoadPreserveReadResolvesDestinationBank"
```

Result: 9/9 passed, 0 failed, 0 skipped, 0 errored in less than 0.01s real.
The eight affected build steps passed in 23.03s real before this run.

**Diff hygiene:**

```bash
git diff --check <pr-base>..HEAD
```

Result: passed.

## Summary

This PR teaches generated instruction def/use metadata that single-element D16
memory loads preserve one half of their destination register and therefore read
the old destination value.

The generator identifies one-element D16 loads in the `flat_load`,
`buffer_load`, `tbuffer_load`, and `ds_read` semantic classes. It emits an
`implicit_uses()` override that adds `vdst` or `vdata` without placing that
destination in the architectural source-operand list, so disassembly remains
faithful while liveness sees the read-modify-write dependency. Generated
overrides are added across the CDNA, RDNA, and gfx1250 targets.

The tests decode low-half and high-half FLAT loads, an untyped buffer load, a
DS load, and a typed-buffer load; they also verify that a regular full-width
load does not read its destination and that a D16 store does not define its
data operand.

The basic representation is appropriate, but two paths do not reach that
representation: gfx1250's bank-aware liveness consumes an operand-backed hook
instead of raw VGPR implicit uses, and legacy MUBUF format loads never receive
the semantic classification on which the new predicate depends.

## Actionable items

### 1. Emit the operand-backed D16 preserve-read hook on gfx1250

**Files:** `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:6939-6972`,
`emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:8087-8120`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/analysis/def_use_chain.cpp:99-130`,
`emulation/rocjitsu/tests/analysis/liveness_test.cpp`

The D16 branch emits only `implicit_uses()`. That is sufficient when
`InstDefUse` has no VGPR-MSB analysis, which is why the submitted RDNA4/CDNA3
tests pass. It is not sufficient for real gfx1250 liveness.

When a `Gfx1250VgprMsbAnalysis` is present, `InstDefUse` obtains preserved VGPR
reads from `implicit_use_operands()` so it can resolve each operand's SRC/DST
bank. It then explicitly removes every VGPR reported by the flat
`implicit_uses()` hook. Because generated D16 loads do not override
`implicit_use_operands()`, their destination preserve-read disappears entirely.
The counterexample above sets destination bank 2 and loads into encoded `v1`;
the submitted liveness result incorrectly considers physical `v513` dead.
Scratch allocation or instrumentation can consequently reuse a register whose
old half the load still needs to preserve.

For profiles with `uses_vgpr_msb_indexing`, generate
`implicit_use_operands()` alongside the D16 `implicit_uses()` override, call the
base implementation, and push the same destination operand (`vdst` or
`vdata`). This should mirror the existing `_partial_def_outputs` path at
lines 8087-8109.

Add a gfx1250 `LivenessAnalysis` regression that sets a nonzero destination
bank before a D16 load and verifies:

- the physical destination-bank register is live before the load;
- the unbanked low-index alias is not substituted for it; and
- an unknown destination bank conservatively reads every candidate bank.

The one-instruction generated-code prototype made the known-bank regression
and all neighboring submitted D16 tests pass.

### 2. Include `BUFFER_LOAD_FORMAT_D16_X` in the D16 load classification

**Files:** `emulation/rocjitsu/lib/python/amdisa/semantics.py:2031-2093`,
`emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:2767-2785`,
`emulation/rocjitsu/tests/analysis/liveness_test.cpp:3940-3962`

Legacy MUBUF contains `buffer_load_format_d16_x`, whose single 16-bit result
preserves the other half of `vdata`. The semantic table already lists
`FORMAT_D16_X` as `(elem_size=2, num_elems=1)`, but `_derive_mubuf()` consults
only `_FLAT_DATA_MAP`; `_BUFFER_FORMAT_MAP` is never consumed. The instruction
therefore falls back to semantic class `nop`, has neither `d16_lo` nor
`d16_hi`, and fails `_d16_load_reads_dst()`.

The submitted generated MUBUF constructor still reports `vdata` as a
destination, but it emits no implicit destination use. The direct CDNA3
counterexample therefore sees `v5` as a def only, even though the corresponding
MTBUF `tbuffer_load_format_d16_x` is handled by this PR.

Classify the MUBUF format-load family precisely enough that
`buffer_load_format_d16_x` reaches the one-element D16 predicate, or add an
equivalent narrow predicate that does not unintentionally change execution
generation for the currently unimplemented format instructions. Keep
format stores excluded, regenerate every affected target, and add direct
positive/negative MUBUF format tests.

The minimal generated override made the MUBUF counterexample and all submitted
D16 tests pass.

## Suggestions

None beyond the two correctness items above.

## Commentary

Representing the preserved half as an implicit use is the right abstraction.
Appending the destination to `src_operands_` would duplicate it in printed
assembly and make the architectural operand list misleading. The existing
partial-def infrastructure also demonstrates the needed two-hook contract:
`implicit_uses()` is the architecture-neutral view, while
`implicit_use_operands()` carries operand role and width for gfx1250's banked
register model.

The generated output is otherwise mechanically consistent with the generator,
and the submitted positive load cases plus regular-load and store negatives
provide a useful baseline once the gfx1250 and MUBUF-format boundaries are
added.
