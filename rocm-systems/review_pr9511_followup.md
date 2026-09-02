This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9511](https://github.com/ROCm/rocm-systems/pull/9511)

**Commit reviewed:** `8ce3f2162438` (`[rocjtisu][fix][refactor] Refactor
multikernel indirect-branch tests`), the current PR head.

**Review mode:** comment-aware follow-up review. I read all three submitted
reviews and all four substantive inline comments from the requested reviewer,
then independently checked each request against the current code. Thread
resolution and outdated status were treated only as metadata, not as proof.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open and not a draft. GitHub reports it as conflicting with
`develop`, with review still required.

**Submitted focused tests on the unmodified head:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='BinaryTranslatorE2E.MultiKernelIndirectBranchFixtureHasExpectedShape:BinaryTranslatorE2E.TranslatesRealMultiKernelSharedSwappcCodeObject:BinaryTranslatorE2E.BuildsCfgForRealMultiKernelIndirectBranches:BinaryTranslatorE2E.MultiKernelIndirectBranchKernelScopesShareOnlyTheHelper:BinaryTranslatorE2E.SplitFixturesMatchFullFixtureKernelScopes'
```

Result: 5/5 passed, 0 failed, 0 skipped, 0 errored in 0.03s real,
0.02s user, and 0.00s sys.

**Direct-call locality counterexample:**

The first inline comment asked for two independent properties:

1. every object-wide `s_call_b64` should appear as a CFG terminator; and
2. the three deliberately planted sites should be reachable specifically from
   `multikernel_indirect_branch_scall`.

I temporarily moved one `RJ_STATIC_SCALL_ISLAND` from the scall kernel to the
setpc kernel in both the full and part1 fixture sources. The object still held
three direct calls, every call retained the expected tail-transfer CFG shape,
and full/split fixture shapes changed identically.

```bash
time -p cmake --build $BUILD_DIR \
  --target kernel_multikernel_indirect_branch \
           kernel_multikernel_indirect_branch_part1 \
           rocjitsu_tests --parallel 8

time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='BinaryTranslatorE2E.MultiKernelIndirectBranchFixtureHasExpectedShape:BinaryTranslatorE2E.TranslatesRealMultiKernelSharedSwappcCodeObject:BinaryTranslatorE2E.BuildsCfgForRealMultiKernelIndirectBranches:BinaryTranslatorE2E.MultiKernelIndirectBranchKernelScopesShareOnlyTheHelper:BinaryTranslatorE2E.SplitFixturesMatchFullFixtureKernelScopes'
```

Result: 5/5 passed, 0 failed, 0 skipped, 0 errored. This demonstrates that the
requested locality property is not covered by the current head. The temporary
fixture changes were removed, the original fixture artifacts were rebuilt,
and the unmodified tests above were rerun.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files \
  emulation/rocjitsu/tests/dbt/multikernel_indirect_branch_test.cpp

git diff --check $(git merge-base HEAD origin/develop)..HEAD
```

Result: every applicable pre-commit hook passed, and `git diff --check`
passed.

## Summary

There are four substantive inline comments from the requested reviewer. Three
are addressed in the current code:

1. **Make the recovered setpc count exact.** Addressed. The current CFG test
   requires exactly three recovered setpc blocks.
2. **Compare recovered swappc blocks with the total source swappc count.**
   Addressed. The current test requires equality with
   `count_text_mnemonic(..., "s_swappc_b64")`.
3. **Assert the negative setpc case: one ordinary helper return remains
   unrecovered.** Addressed more strongly than requested. The current test
   requires exactly one unrecovered setpc block and requires it to be the same
   block reached by every recovered helper call.

The remaining comment is only partially addressed:

4. **Verify both object-wide direct-call classification and scall-kernel
   locality.** The current fixture and CFG tests each require a global count of
   three, but no assertion proves that those three blocks are reachable from
   `multikernel_indirect_branch_scall`. The counterexample above moves one call
   to another kernel and still passes all five submitted tests.

Therefore, the answer is **no: not all of the requested review feedback is
addressed**. Three of four substantive comments are addressed; the direct-call
locality requirement remains outstanding.

This gap is a regression introduced by the PR, not a preexisting omission:

- Before the PR, the test compared the three call-site offsets with a golden
  vector. That oracle was compiler-fragile, but it did fail if a planted call
  moved out of the scall kernel.
- Commit `96b14fc9920d` replaced the offset vector with only a global count of
  three, introducing the locality gap.
- After the inline feedback, commit `a196466c3274` added both the object-wide
  terminator/mnemonic comparison and an explicit count of three direct-call
  blocks reachable from the scall entry.
- The final refactor at `8ce3f2162438` removed that scall-local count and
  returned to global-only assertions.

The current head therefore reintroduces a problem that had already been fixed
in an intermediate PR revision.

## Actionable items

### 1. Assert that all three planted direct calls belong to the scall kernel

**File:** `emulation/rocjitsu/tests/dbt/multikernel_indirect_branch_test.cpp:405-417,516-591,610-652`

The current assertions establish only that:

- `.text` contains three `s_call_b64` instructions;
- three CFG blocks terminate in `s_call_b64`; and
- every such block currently has the planted island's branch delta and
  nonreturning edge shape.

They do not establish that those blocks are reachable from
`kKernelScall`. Moving one structurally valid island into `kKernelSetpc` keeps
all three global properties true and passes the scope tests because both
kernels remain isolated from other kernels.

Build the `kKernelScall` scope and count the direct-call terminators within
that scope. Require exactly three there, and separately compare the
object-wide direct-call terminator count with
`count_text_mnemonic(*loaded.co, ..., "s_call_b64")`. This expresses both
halves of the original feedback:

- all decoded direct calls were represented as CFG terminators; and
- all three source-controlled fixture sites remained local to the scall
  kernel.

Commit `a196466c3274` already implemented this contract before the final
refactor. Restore the equivalent logic using the refactored `LoadedObject` and
`kernel_scope` helpers rather than designing a new oracle.

Do not use a global `s_call_b64 == 3` assertion as the locality check. It can
both miss the demonstrated relocation and fail unnecessarily if a future
compiler emits an additional valid direct call elsewhere.

## Suggestions

None specific to the requested review comments.

## Commentary

The current thread metadata is misleading in both directions. The direct-call
thread is marked resolved and outdated, but its locality requirement remains
uncovered. The negative-setpc thread is still unresolved in the UI, but the
current code implements a stronger structural assertion than the requested
count relation.

This follow-up assessment is intentionally limited to the requested reviewer's
comments. The independent first review records additional coverage and oracle
concerns that are separate from whether these four comments were handled.

## Appendix A: direct-call locality counterexample

Applied identically to
`tests/kernels/multikernel_indirect_branch.hip` and
`tests/kernels/multikernel_indirect_branch_part1.hip`:

```diff
 void multikernel_indirect_branch_setpc(...) {
   ...
   if (value == 0x16180339u)
     RJ_STATIC_SETPC_ISLAND(8, 9);
+  if (value == 0x1234abcdu)
+    RJ_STATIC_SCALL_ISLAND(24, 25);
   ...
 }

 void multikernel_indirect_branch_scall(...) {
   ...
-  if (value == 0x1234abcdu)
-    RJ_STATIC_SCALL_ISLAND(24, 25);
   ...
 }
```

All five submitted tests passed with one of the three planted direct calls in
the wrong kernel.
