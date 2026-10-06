This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13027](https://github.com/ROCm/rocm-libraries/pull/13027)

**Reviewed head:** [`2ac9fca28440087070e0e8629b4df818b63620ac`](https://github.com/ROCm/rocm-libraries/commit/2ac9fca28440087070e0e8629b4df818b63620ac) (2026-10-06).

**Published suggestion branch:** [`review/pr13027-suggestions-20261006`](https://github.com/newling/rocm-libraries/tree/review/pr13027-suggestions-20261006), based on that exact head, with no additional commits. The repository and PR head are public. GitHub reviews and discussion comments were not consulted.

## Tests

Built the submitted rocisa with Clang 23 and ran `rocisa/test/test_lowering64.py`: all 117 cases passed, including actual assembly for gfx90a, gfx942 and gfx950 using ROCm 7.1. `git diff --check` passed.

Current Math CI passes. The PR also has failed gfx1250 FFM and project-coverage checks, and a rocSOLVER failure in the multi-architecture run. Those failures have not been attributed to this change. The local tests assemble instructions; they do not execute them on three physical GPUs.

## Summary

On targets without a native 64-bit add, rocisa emits an add for the low word followed by an add that consumes its carry in the high word. The old shared operand splitter duplicated a scalar immediate into both words. This change separates integer splitting from packed floating-point splitting, so an increment of five becomes a low increment of five and a high increment of zero.

The implementation also accounts for instruction encoding: a vector literal goes in the operand position that supports it, and an unencodable high half is rejected. The tests check both arithmetic decomposition and actual assembler acceptance. Keeping those two checks is useful because numerically sensible instruction text can still be impossible to encode.

## Actionable items

No source change requested from this review. The supported integer range, rejection of symbolic and non-integral inputs, signed high halves, register-pair handling, and unchanged native/packed paths were inspected. The new helper is exercised through both instructions that use it; a duplicate test of the helper's implementation is unnecessary.

## Suggestions

No additional code suggestion. Keep this PR independent of the fast_check stack and address-carry lint, as it is now. Its focused lowering and assembly tests provide a useful landing unit without waiting for the larger client verifier.

## Commentary

The conservative rejection at magnitude 2^53 is appropriate for the current Python-to-C++ conversion through `double`: some integers have already lost information at that point. Expanding the range would require preserving integer values in the binding, and is separate work. The existing restriction on a vector immediate's high half is also stated explicitly rather than silently emitting an invalid instruction.

The right test level is rocisa instruction generation plus assembly on the affected targets. Existing register-only users of these composite instructions are the adjacent paths to preserve; packed operations continue to use their original splitter. No new behavior flag is needed for correcting this operand decomposition, and no omitted-test waiver is necessary for the changed behavior. Resolve or explain the remaining failed automated checks before landing; successful local assembly does not replace that work.

The published branch has no additional commits because no bounded implementation change was warranted.
