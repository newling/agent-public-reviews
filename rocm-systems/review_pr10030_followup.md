This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#10030](https://github.com/ROCm/rocm-systems/pull/10030)

**Revision reviewed:** published head `52c78c36c789`, a five-commit stack
based directly on `origin/develop@35959f8e12`.

**Review mode:** comment-aware implementation follow-up. This pass independently
rechecked the original review's complete-range blocker and the later feedback
about denied operand views, split-profile operand writes, SDWA scalar
destinations, wide conversion loops, and released-wave ownership.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests rocjitsu_plugin_race_so \
           rocjitsu_plugin_logging_so --parallel 8
```

Result: the rebased build passed all 316 required steps in 111.53s real,
818.84s user, and 41.57s sys.

After the regeneration and exploratory probe pass, the final incremental build
of the exact source state passed in 6.11s real, 6.43s user, and 0.54s sys.

The compiler-backed coverage follow-up then rebuilt 214 affected steps in
73.07s real, 512.08s user, and 27.62s sys after the hand-maintained test commit
was placed below the generated-only top commit.

**Register ownership, plugin, and conversion coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RegisterAccessTest.*:ExecutionPluginTest.SgprWriteObservationUsesExplicitWavePhysicalBlock:HookOrderingTest.WorkgroupDispatchedReportsPhysicalRegisterBlockSizes:Cdna4CvtScaleTest.WideFp6ToF16ConsumesFp16OvflMode:Gfx1250CvtScaleTest.WideUnpackRejectsDestinationRangeBeforeWriting'
```

Result: 36/36 passed, 0 failed, 0 skipped, and 0 errored in 0.06s real.
This includes the permanent released-wave regression, denied-view stores,
SGPR64 and VGPR64 block-boundary rejection, GPR-indexed ownership, lifecycle
map clearing, physical register capacity reporting, SGPR write callbacks, and
the affected wide conversion path.

**Compiler-backed callable-SGPR evidence:**

```bash
time -p $BUILD_DIR/tests/probe_fixture_test \
  --gtest_filter='ProbeFixture.*'
```

Result: 4/4 passed, 0 failed, 0 skipped, and 0 errored in 0.01s real.
`ProbeFixture.CallableSgprUseExceedsKernelDescriptor` loads a real
compiler-generated gfx950 code object, verifies that its entry-kernel
descriptor grants 40 SGPRs (`s0..s39`), resolves the separately callable
device function, and decodes `s_mov_b32 s40, 1` from that function's body.

The existing runtime observation pair also passed:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='ExecutionPluginTest.SgprWriteObservationUsesExplicitWavePhysicalBlock:RegisterAccessTest.ExplicitWaveSgprAccessUsesReservedPhysicalBlock'
```

Result: 2/2 passed, 0 failed, 0 skipped, and 0 errored in 0.03s real.

**Focused AMDISA generator tests:**

```bash
time -p env MRISA_PATH=$MRISA_XML_DIR \
  .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_profile_properties.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_sema_derive.py
```

Result: 819 passed, 0 failed, 1 skipped, and 0 errored in 9.72s real. The skip
is an existing optional case.

An initial invocation pointed `MRISA_PATH` at the parent of the XML directory.
It produced 17 `FileNotFoundError` failures, with 793 passes and 10 skips. The
corrected command above uses the directory that directly contains the XML
files; all affected tests then passed. The initial failures were environment
setup errors, not product failures.

**Generation:**

```bash
ALLOW_DIRTY=1 BUILD_JOBS=8 FORMAT_JOBS=8 \
  $ISA_GENERATION_WRAPPER --repo $SRC_DIR --skip-build
```

Result: all-ten-ISA regeneration completed and was content-idempotent. It left
no tracked source changes.

**Formatting and diff hygiene:**

```bash
time -p bash -lc \
  'git diff --name-only origin/develop...HEAD -z |
   xargs -0 .venv/bin/pre-commit run --files'
git diff --check origin/develop...HEAD
```

Result: every applicable hook passed in 4.50s real, `git diff --check` passed,
and the reviewed source checkout has no tracked modifications.

The final head was published after local validation. Fresh formatting, policy,
CodeQL, sanitizer, release, and packaging jobs were queued immediately after
the push; no result was available yet at the end of this pass.

## Summary

The current stack establishes a coherent ownership boundary for
instruction-visible register operations.

Wave-bound SGPR and VGPR access now treats the executing wave as authoritative.
The complete physical range is checked before callbacks or storage access, so
64-bit and region operations cannot split across waves. CU-bound reads retain
a compatibility path, but it resolves one live owner for the complete range.
Raw runtime and memory-completion writes remain unobserved storage operations.

The follow-up commits close the concrete holes found in the original review:

- denied SIMD operand views now carry an explicit denied state, return benign
  zeros for reads, and no-op instead of falling through to raw writes;
- split-profile generated operand chunk writes retain the executing wave and
  validate the resolved physical register;
- SDWA 64-bit scalar comparison destinations use one `write_sgpr64()` call;
- affected wide gfx1250 conversions acquire complete source and destination
  regions before using their dwords;
- SGPR64 and VGPR64 access validates both registers before any callback or
  storage effect; and
- released waves cannot claim block zero because ownership requires a live,
  nonempty allocation, with permanent SGPR and VGPR regression coverage.

The physical-block policy remains appropriate. Descriptor register counts are
resource metadata, while callable code and unified ordinary/accumulator
register namespaces can validly reach registers beyond those counts. Plugins
therefore receive the capacity of the physical block they may actually observe.

The compiler-backed fixture now makes that rationale durable. It proves that a
real callable function can access `s40` while the entry kernel's descriptor
grants only `s0..s39`, and the existing runtime test verifies that the access is
observed and stored through the wave's reserved physical block.

I found no remaining actionable correctness, ownership, lifecycle, generated
output, or test issue in the rebased candidate.

## Actionable items

None.

## Suggestions

None.

## Commentary

### Existing review feedback

The original complete-range blocker and all current review feedback are
addressed in the candidate.

The still-unresolved ownership thread points at
`owns_sgpr_range()`/`owns_vgpr_range()`. Both predicates now reject allocations
whose count was cleared by `Wavefront::reset()`, and
`ReleasedWaveCannotOwnReallocatedRegisterBlock` verifies that a released wave
cannot modify or report writes against a live wave's SGPR or VGPR storage.

Suggested reply text for that thread:

```text
Addressed: both ownership predicates now require a nonempty live allocation
before applying the physical-block range check. The permanent
ReleasedWaveCannotOwnReallocatedRegisterBlock regression covers SGPR and VGPR
writes from a reset wave and verifies that live storage and callbacks remain
unchanged.
```

The earlier wide-conversion thread is also addressed for the affected
MSB-adjusted gfx1250 family. During this follow-up I separately probed the older
CDNA4 `V_CVT_SCALEF32_*PK32*` family. A destination starting at unified `v250`
remained inside CDNA4's 512-register physical ordinary/accumulator block; the
adjacent wave began at physical register 512 and was untouched. That family
still uses the documented CU-bound compatibility path, but its encodable range
does not reproduce the cross-wave failure fixed here.

### Publication state

The follow-up adds one hand-maintained test commit below the regenerated top
commit, so the published branch contains five PR commits and still has exactly
one generated-only commit at the top. The rewritten branch was published with
an exact force-with-lease, and fresh CI was queued. No review-thread resolution
or GitHub comment was performed for this follow-up.
