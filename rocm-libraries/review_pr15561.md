This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15561](https://github.com/ROCm/rocm-libraries/pull/15561)

Reviewed head: `cd39621d1ecf25682a99da51610b05608ca0ff5a`. Base: `e8b44f8b6b0e8d9ffffc294203d6ef063a85f40d`.

Mode: independent review, including the requested comment follow-up about fixed indices across builds. Scope: all five changed files, the index encoder/decoder, backend dispatch, support-check and execution callers, and test registration. Local suggestion branch: `review/pr15561-suggestions`, based on the reviewed head. Commit `8b0d4ac41aedfa648d1e84ce196ec68c7af00a4e` implements suggestion 1 only.

## Tests

At the submitted head, focused compiler checks passed for the complete `solution_selection.cpp` and for `algo_errors_gtest.cpp` with `HIPBLASLT_USE_ROCROLLER` enabled. A temporary host probe using the submitted encoder, decoder, validator, types and tile tables passed 3,168 cases under AddressSanitizer and UndefinedBehaviorSanitizer. It covered both tile tables with every flag combination, field boundaries, cleared markers, each reserved bit, the fixed invalid indices, and the stated decoding of 80950. The probe extracted those definitions; it did not link or execute the full hipBLASLt library.

The suggestion changes only a comment; the complete branch passes `git diff --check`. GPU execution and a full rocRoller-enabled build were not repeated locally: the available GPUs are gfx1201 and the existing hipBLASLt builds disable rocRoller. The PR description reports passing GPU regressions on gfx950 and a failing control without the fix; those results were not independently reproduced here.

At inspection on 2026-11-11, formatting and component checks passed, while Math CI and codecov remained pending. The required Multi-Arch summary failed; its linked Linux Quartz completion job was cancelled with no steps. This is incomplete CI evidence, not an independently demonstrated code failure.

## Summary

The guard rejects indices that cannot represent a rocRoller algorithm before either cache lookup or kernel generation. The support-check and execution paths propagate that rejection. The encoder uses bits 0–27 for fields and flags, sets bit 31, and leaves bits 28–30 clear, consistent with the new validator.

The public regression obtains a valid algorithm from the current build, verifies it is supported, and clears only its marker bit. The decoder ignores that bit, so the resulting algorithm would otherwise describe the same kernel. This is a useful control against rejection for unrelated tile or problem errors. The separate Tensile-algorithm case exercises the original backend mismatch. The public test belongs to the normal smoke suite; the auxiliary test remains coverage-only.

## Actionable items

None found within the reviewed scope and validation limits.

## Suggestions

### 1. Explain the two reasons the fixed indices are invalid

At [`testing_auxiliary.hpp:4136`](https://github.com/ROCm/rocm-libraries/blob/cd39621d1ecf25682a99da51610b05608ca0ff5a/projects/hipblaslt/clients/common/include/testing_auxiliary.hpp#L4136), the comment describes all three indices as lacking the marker bit. That is true for 0 and 80950, but false for -1: its marker is set, and its reserved bits cause rejection.

The [comment-only patch](patches/pr15561-8b0d4ac41ae.patch), from local commit `8b0d4ac41aedfa648d1e84ce196ec68c7af00a4e`, corrects the comment and explains why the nonnegative cases do not depend on a build's Tensile index assignments. No executable behavior changes.

## Commentary

The fixed-index check is stable across builds under the existing encoding. A Tensile index can identify a different solution in another build, but this test never resolves that index through Tensile. Both 0 and 80950 lack the rocRoller marker and must be rejected regardless of their catalog meaning, or whether the catalog contains them at all. The -1 sentinel is rejected because its reserved bits are set.

The claim that 80950 decodes to a 32×1920×1728 tile comes from rocRoller's fixed bit-field decoder, not from a build's solution catalog. A future encoding change could require updating that explanatory detail. The test's rejection expectation does not depend on those dimensions. Cases that require a valid rocRoller algorithm obtain one from the running build.

The local suggestion branch contains only the comment clarification above. Its patch accompanies this review and applies from the repository root at the reviewed head. GPU regressions and the review-time CI snapshot remain the validation limits; no identified implementation fix was omitted.
