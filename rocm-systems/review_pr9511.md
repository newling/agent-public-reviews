This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9511](https://github.com/ROCm/rocm-systems/pull/9511)

**Commit reviewed:** `8ce3f2162438` (`[rocjtisu][fix][refactor] Refactor
multikernel indirect-branch tests`), the current PR head.

**Review mode:** independent first review. I did not read existing GitHub
reviews, inline comments, or discussion threads.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open and is not a draft. GitHub currently reports the PR as
conflicting with `develop`, with review still required.

The release, GCC ASan/UBSan, TSan, and pre-commit rocJITsu checks pass. The
Clang ASan/UBSan job built and ran 2,349 tests; 2,348 passed and the unrelated
`RocjitsuCliDaemon.LaunchesApplicationAfterDaemonIsReady` test timed out after
its nested HIP vector-add test had passed. The failed TheRock sanity job did
not reach project testing: its environment setup timed out downloading a
Python package.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: all 466 build steps passed in 134.39s real, 997.72s user, and
49.06s sys.

**All five submitted multi-kernel indirect-branch tests:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='BinaryTranslatorE2E.MultiKernelIndirectBranchFixtureHasExpectedShape:BinaryTranslatorE2E.TranslatesRealMultiKernelSharedSwappcCodeObject:BinaryTranslatorE2E.BuildsCfgForRealMultiKernelIndirectBranches:BinaryTranslatorE2E.MultiKernelIndirectBranchKernelScopesShareOnlyTheHelper:BinaryTranslatorE2E.SplitFixturesMatchFullFixtureKernelScopes'
```

Result: 5/5 passed, 0 failed, 0 skipped, 0 errored in 0.04s real,
0.03s user, and 0.00s sys.

**Coverage-preservation mutations:**

I applied two temporary mutations, rebuilt the affected fixture/test targets,
and removed both mutations afterward.

First, I removed kernel A's second shared-helper call from both the full and
part0 fixture sources, leaving five helper calls instead of the source-declared
six. On the PR head, all five submitted tests still passed:

```bash
cmake --build $BUILD_DIR \
  --target kernel_multikernel_indirect_branch \
           kernel_multikernel_indirect_branch_part0 \
           rocjitsu_tests --parallel 8

$BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='BinaryTranslatorE2E.MultiKernelIndirectBranchFixtureHasExpectedShape:BinaryTranslatorE2E.TranslatesRealMultiKernelSharedSwappcCodeObject:BinaryTranslatorE2E.BuildsCfgForRealMultiKernelIndirectBranches:BinaryTranslatorE2E.MultiKernelIndirectBranchKernelScopesShareOnlyTheHelper:BinaryTranslatorE2E.SplitFixturesMatchFullFixtureKernelScopes'
```

Result on the PR head: 5/5 passed. Result at the pre-PR base: 1/4 passed and
3/4 failed. The legacy translation test reported five helper swappc sites
instead of at least six, the legacy CFG test reported five recovered swappc
blocks instead of at least six, and the legacy per-kernel scope test reported
six blocks for kernel A instead of eight.

Second, I made the test scope walker drop the last reachable block from every
kernel scope:

```cpp
if (!ordered.empty())
  ordered.pop_back();
```

Result on the PR head: 5/5 submitted tests still passed. At the pre-PR base,
the golden per-kernel count test failed for all seven kernels, each short by
one block; the full-versus-split comparison still passed because both sides
were under-counted identically.

These mutations demonstrate that the new suite is not a strict coverage
superset of the old suite. Exact machine-layout assertions were removed, which
is desirable, but two source/CFG completeness contracts were removed with
them.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files \
  emulation/rocjitsu/tests/dbt/multikernel_indirect_branch_test.cpp

git diff --check $(git merge-base HEAD origin/develop)..HEAD
```

Result: every applicable pre-commit hook passed, and `git diff --check`
passed.

I did not run broad simulator, HIP, race-detector, or corpus suites. This PR
changes only one DBT test file, the five directly affected tests pass locally,
and the public release corpus is green. The remaining review questions are
about whether the new test oracles remain valid across compiler changes, not
about accumulating wider runtime coverage.

## Summary

This PR turns one compiler-layout-sensitive DBT test file into a five-part
contract suite.

The fixture test establishes the seven expected kernel descriptors and a
baseline for the shared helper. The translation test checks that all kernels
remain dispatchable after CDNA4-to-CDNA3 translation, that recovered indirect
calls become direct calls, and that the shared helper is copied into each
calling kernel's translated scope. The CFG test distinguishes recovered
`s_swappc_b64` calls, recovered `s_setpc_b64` branches, the helper's unresolved
return, and the three deliberately planted nonreturning `s_call_b64` islands.

The two scope tests replace exact block counts with relationships: isolated
kernels should overlap no other scope, helper-calling kernels should overlap
only in the shared callee, and compiling the same kernel bodies in split
objects should preserve each kernel's entry-relative CFG shape.

The refactor also centralizes fixture loading, switches kernel lookup from
mixed virtual/file offsets to the parsed kernel name, uses the shared
environment-aware kernel-path helper, and reports all error-severity
translation diagnostics.

The main remaining problem is that two new oracles still identify generated
code by incidental machine-code choices. One treats every direct scalar call
in the object as one of the three inline-assembly islands, even though the
file explicitly says the compiler may choose direct calls for the helper. The
other identifies helper copies by searching for a raw literal word whose
materialization is not guaranteed by the source language or ABI.

The refactor also drops two independent coverage properties: it no longer
proves that the fixture contains all six source-declared helper calls, and it
no longer has an oracle for a kernel scope that is consistently
under-approximated in both the full and split objects. Both losses were
confirmed with temporary mutations.

## Actionable items

### 1. Restore source-call and local-scope completeness without restoring brittle offsets

**File:** `emulation/rocjitsu/tests/dbt/multikernel_indirect_branch_test.cpp:388-418,438-480,516-591,594-702`

The refactor removes two coverage properties that the pre-PR tests enforced.

First, the source declares six calls into the shared helper: two from kernel A
and one from each of kernels B-E. The old translation and CFG tests required
at least six compiler-emitted/recovered swappc sites. The new tests require
that all five kernels share some helper block and that every swappc the
compiler happened to emit was recovered, but they do not require kernel A to
contain its second call.

The temporary fixture mutation in Tests replaced kernel A's second call with
`first ^ base` in both the full and split source. All five submitted tests
passed with only five helper calls. The pre-PR translation, CFG, and golden
scope tests all failed.

Do not restore the opcode-specific `source_swappc >= 6` assertion. Instead,
identify the shared callee structurally and assert six returning call sites to
it regardless of whether each site is encoded as a recovered
`s_swappc_b64` or a direct `s_call_b64`. Assert the per-kernel distribution as
well: two sites from kernel A and one from each of kernels B-E. This preserves
the source-controlled contract while allowing compiler opcode changes.

Second, replacing expected per-kernel block counts with full-versus-split
scope shapes loses any defect that affects both objects identically. The
temporary `ordered.pop_back()` mutation removed one reachable block from every
computed scope. All five submitted tests still passed because overlap
relations were unchanged and both sides of every split comparison lost the
same block. The old golden count test failed for all seven kernels.

Keep the relational tests, but add an independent completeness oracle for each
kernel's own scope. It need not be a raw block-count table. Prefer
source-controlled landmarks such as:

- the expected number and per-kernel distribution of helper calls;
- all three setpc islands and all three scall islands;
- each kernel's range-check exit and final store/end path; and
- the expected join/continuation relationships around the planted islands.

An execution-level fixture test can supplement these structural checks, but
the static suite should still fail when a reachable local block is omitted
consistently from both full and split objects.

### 2. Restrict the `s_call_b64` island assertions to the dedicated scall kernel

**File:** `emulation/rocjitsu/tests/dbt/multikernel_indirect_branch_test.cpp:395-415,554-591`

The fixture documentation correctly says that the six shared-helper call
sites are source-level invariants but their encoding as indirect
`s_swappc_b64` rather than direct `s_call_b64` is the compiler's choice.
Despite that, `MultiKernelIndirectBranchFixtureHasExpectedShape` asserts that
the entire code object contains exactly three `s_call_b64` instructions.

`BuildsCfgForRealMultiKernelIndirectBranches` has the same assumption in a
stronger form. Its `else if (mnemonic == "s_call_b64")` branch treats every
direct call in every kernel as an `RJ_STATIC_SCALL_ISLAND`: it requires a
four-byte branch delta, no call edge, and no continuation, then requires the
global count to be three.

A valid compiler change that encodes one or more shared-helper calls directly
would therefore fail this suite even when DBT builds the correct returning
`DirectCall` edge. Such a call has a real continuation and need not use the
island's fixed four-byte target delta. This recreates the compiler-version
fragility the PR is intended to remove.

Build the `kKernelScall` scope first and apply the three island assertions only
to `s_call_b64` terminators reachable from that kernel. The source of
`multikernel_indirect_branch_scall` controls that there are exactly three such
sites and that they are nonreturning tail transfers. Allow direct calls in the
five helper-calling kernels, and validate those according to their actual
returning call-edge contract rather than classifying them as islands.

Add a control case, synthetic if necessary, with a returning direct call
outside the scall kernel so this test cannot regress to global opcode
classification.

### 3. Do not use an incidental literal word as the helper-copy identity

**File:** `emulation/rocjitsu/tests/dbt/multikernel_indirect_branch_test.cpp:70-93,414-417,462-466`

`kHelperMarkerWord` assumes that the C++ expression
`salt * 0x45d9f3b` produces one standalone `0x045d9f3b` word in source
`.text`, and that translating each helper copy preserves that exact raw word.
The test itself acknowledges that `count_text_word` is not decoding an
instruction and also matches coincidental words.

The source and ABI do not guarantee this materialization. A compiler may
synthesize the constant, move it through a constant-data path, select a future
encoding that does not carry it as a separate dword, or introduce another
unrelated occurrence. Translation-time semantic expansion could also emit the
same raw value for another reason. In all of those cases the helper and its
five per-scope copies can be correct while either the source baseline or the
translated count fails.

Replace the raw-word scan with an identity controlled by the fixture or by the
translator contract. Options include:

- plant a unique, explicitly encoded inline-assembly marker in the helper;
- derive the original helper from the recovered swappc callee and verify one
  corresponding callee copy in each translated kernel scope; or
- expose/use translation placement metadata that directly identifies copied
  source blocks.

Whichever mechanism is chosen should distinguish the helper structurally
rather than relying on the compiler's current constant-materialization
strategy.

## Suggestions

### 1. Build the test CFG with the same external-entry policy as DBT

**File:** `emulation/rocjitsu/tests/dbt/multikernel_indirect_branch_test.cpp:245-273`

`load_fixture()` supplies the complete set of kernel entries but calls
`BasicBlock::build` with its default
`ExternalEntryPolicy::InferPredecessorless`. The production translator calls
the same builder with `ExternalEntryPolicy::ExplicitOnly` after assembling its
complete entry list.

The policy affects indirect-target dataflow: under the default, every
predecessorless block starts with externally unconstrained register state;
under the production policy, an unlisted predecessorless block remains
unreachable until a real edge reaches it. The current fixture produces the
same passing result under the installed compiler, but a future layout can make
the CFG-only tests exercise a different recovery contract from the translator
they claim to model.

Pass `ExternalEntryPolicy::ExplicitOnly` explicitly in `load_fixture()`.

### 2. Avoid defining a kernel's own extent solely by the next kernel entry

**File:** `emulation/rocjitsu/tests/dbt/multikernel_indirect_branch_test.cpp:277-319,636-643`

`kernel_scope()` classifies every reachable block from one kernel entry up to
the next kernel entry as `own_offsets`; everything else is
`external_blocks`. The overlap assertion then requires kernel A's external
blocks to equal the shared helper.

This currently works because the ROCm 7.2 compiler emits the device helper
before all kernel entries. If a compiler or linker places that helper after
kernel A but before kernel B, the CFG remains correct, but kernel A classifies
the helper as its own body and the overlap assertion fails.

Prefer an actual function extent when one is available, or identify the shared
callee from the recovered call target and compare overlap against that callee's
reachable blocks. That keeps the oracle independent of physical function
ordering.

## Commentary

The move from literal block counts to set relationships is a substantial
improvement. Counting cross-kernel edges that the scope walk prunes is
particularly useful: without that counter, the same containment rule being
tested could hide the edge that violated it.

The split-fixture comparison is also better calibrated than the previous
exact-count table. Entry-relative block offsets preserve enough CFG shape to
catch padding absorption without pinning the full object's absolute layout.

The PR currently conflicts with `develop` because that branch also changed the
same `BuildsCfgForRealMultiKernelIndirectBranches` assertions. Resolve the
conflict before landing and rerun the five focused tests against the resolved
file; the actionable oracle issues above should be addressed during that
resolution rather than mechanically choosing either side.

## Appendix A: missing sixth helper-call mutation

Applied identically to
`tests/kernels/multikernel_indirect_branch.hip` and
`tests/kernels/multikernel_indirect_branch_part0.hip`:

```diff
 const unsigned base = input[idx];
 const unsigned first =
     multikernel_indirect_branch_shared_block(base + idx, 17u);
-const unsigned second =
-    multikernel_indirect_branch_shared_block(first ^ base, 29u);
+const unsigned second = first ^ base;
 output[idx] = first + second;
```

On the PR head, all five submitted tests passed. At the pre-PR base, the
translation, CFG, and golden kernel-A scope checks failed.

## Appendix B: systematic scope under-count mutation

Applied at the end of the test-local `reachable_kernel_blocks()` helper:

```cpp
if (!ordered.empty())
  ordered.pop_back();
```

On the PR head, all five submitted tests passed. At the pre-PR base,
`CountsRealMultiKernelIndirectBranchCfgBlocksPerKernel` failed for all seven
kernels, each with one fewer reachable block than expected.
