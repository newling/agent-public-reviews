This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9317](https://github.com/ROCm/rocm-systems/pull/9317)

**Revision reviewed:** local rebased head `b707c0b54eab`, a six-commit stack
based directly on `origin/develop@625071369a`. The local rebased head has not
been pushed.

**Base clarification:** ROCm/rocm-systems has no public `main` branch. Both the
upstream repository and the public source fork use `develop` as their default
branch, and the PR targets `develop`. I therefore rebased onto
`origin/develop`, the only existing requested-repository base.

**Public/repository status:** the upstream repository, source fork, PR, base
branch, and head branch are public. The published PR is open and non-draft.
GitHub reports the old published head `c2443eaae5a4` as conflicting because it
predates the local rebase.

**All-ISA regeneration and build:**

```bash
$ISA_GENERATION_WRAPPER --repo $SRC_DIR
```

The canonical ten-ISA generation completed and the resulting 619-step
`rocjitsu_tests` build passed. The wrapper's wall-clock time was not captured.
The generation changed exactly 31 VOP model files under the generated ISA
tree. The upstream `gfx1250`-to-`cdna5` rename is reflected in the regenerated
path.

I repeated the generation with the dirty-tree override:

```bash
before=$(git diff | sha256sum | cut -d' ' -f1)
ALLOW_DIRTY=1 $ISA_GENERATION_WRAPPER --repo $SRC_DIR
after=$(git diff | sha256sum | cut -d' ' -f1)
test "$before" = "$after"
```

Both diffs had SHA-256
`d7f5f660f41161c440df96d5c85382d80f9e9f5ac01e2c79f83faa89a577746f`.
The repeated 618-step rebuild also passed.

**Rebase integration check:**

The mechanically rebased Wave64 VCMPX test initially failed because upstream
now separates ISA model code from its execution backend:

```text
C++ exception with description "operand execution backend is not linked"
```

That run passed 38/39 `DppPermuteTest.*` cases. The local rebased stack now
registers the RDNA4 execution backend in the new test, matching the surrounding
test helpers and upstream contract. The focused rebuild was:

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: the two-step incremental rebuild passed in 5.98s real, 6.18s user,
and 0.87s sys.

**DPP diagnostics, availability, and EXEC-mask coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='DppPermuteTest.*'
```

Result: 39/39 passed, 0 failed, 0 skipped, and 0 errored in 0.07s real.
GoogleTest reported 0.055s.

**Generator/profile and encoding-provenance coverage:**

```bash
time -p env MRISA_PATH=$MRISA_XML_DIR \
  .venv/bin/python -m pytest -q \
  emulation/rocjitsu/lib/python/amdisa/tests/test_generator_profile_gates.py \
  emulation/rocjitsu/lib/python/amdisa/tests/test_instruction_encoding_availability.py
```

Result: 259 passed, 0 failed, 1 skipped, and 0 errored in 11.40s real.
Pytest reported 11.28s.

An initial sparse-worktree run omitted `MRISA_PATH`: 229 passed, 21 failed,
and 10 skipped in 1.62s real. Every failure was a `FileNotFoundError` for the
intentionally absent in-worktree MRISA XML directory. Rerunning with the
canonical shared XML directory produced the passing result above; this was an
environment setup error, not a PR failure.

**Formatting and diff hygiene:**

```bash
time -p .venv/bin/pre-commit run --files \
  $(git diff --name-only origin/develop..HEAD)
git diff --check origin/develop..HEAD
```

Result: every applicable hook passed in 2.70s real, and `git diff --check`
passed.

The final stack contains five hand-maintained commits followed by one
generated-only top commit. The top commit contains exactly the 31 regenerated
VOP files, and no generated file appears in the lower commits.

On the old published head, the release, Clang ASan/UBSan, GCC ASan/UBSan, TSan,
pre-commit, and repository-policy checks pass. The broad repository matrix
contains failures, but it has not run against the local rebased head.

## Summary

The PR improves unsupported-modifier diagnostics without changing modifier
availability or execution semantics. Generated constructors previously
combined unsupported DPP16 and DPP8 markers into one condition and reported
both as `DPP`. The generator now emits one rejection branch per marker, so a
DPP8 selector reports that DPP8 is unsupported while the ordinary DPP selector
continues to report DPP.

This remains instruction-specific rather than architecture-wide. The parser
records the instruction's complete non-skipped encoding set before
condition-gated alternate entries are omitted from class emission. The
generator uses that provenance to decide independently whether a base
instruction supports DPP16, DPP8, or SDWA. An instruction with both RDNA4 VOPC
forms receives both extension decoders; an F64 comparison without those forms
receives separate, accurately labeled rejection branches.

The direct C++ test exercises both sides of that contract. `V_CMP_EQ_U32`
accepts DPP16 and DPP8 constructor shapes, while `V_CMP_EQ_F64` rejects them
with exact `DPP` and `DPP8` messages. The Python source-shape test pins the same
generated behavior before compilation.

The Wave64 VCMPX test covers a separate existing execution contract: DPP writes
must merge comparison results into all 64 `EXEC` bits without disturbing
masked-off bits or VCC. An active mismatch at lane 33 makes the test fail if an
implementation updates only the low 32 bits. The expected result preserves the
unwritten old bits while clearing the selected low- and high-half comparison
bits.

The refreshed generated commit carries only the diagnostic source change
through the current generator and current ISA layout. Upstream's ISA
model/execution split and `gfx1250`-to-`cdna5` rename account for the structural
difference from the old generated commit; two complete regeneration/build
passes were content-identical.

I found no remaining actionable correctness, test, generated-output,
documentation, or maintainability issue in the local rebased stack.

## Actionable items

None.

## Suggestions

None.

## Commentary

### Contract and counterexample pass

- DPP16 and DPP8 markers are tested independently for a supported and an
  unsupported RDNA4 VOPC instruction.
- The runtime test checks the complete `InvalidInst::what()` string, so the
  diagnostic distinction cannot regress while preserving only the exception
  type.
- The generator handles the mixed-support case: existing VOP1 coverage has
  DPP16 support but DPP8 rejection, while the new VOPC case covers both
  supported and both unsupported.
- Encoding provenance is captured before condition-gated alternates are
  filtered from emitted instruction classes, while profile-wide skipped
  encodings remain excluded.
- The Wave64 case includes an active upper-half mismatch and nontrivial old
  `EXEC` bits, covering both high-half modification and masked-bit
  preservation.
- The rebase-specific execution-backend registration was validated by a
  concrete failure before the adjustment and a passing focused suite after it.
- Repeated all-ISA generation is content-idempotent, and generated output
  remains isolated in the top commit.

### Scope

The PR intentionally does not change which instructions support DPP, DPP8, or
SDWA and does not change DPP execution. Its behavioral surface is the
specificity of invalid-instruction diagnostics plus tests that pin existing
availability and Wave64 EXEC semantics.
