> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14043](https://github.com/ROCm/rocm-libraries/pull/14043)

**Reviewed head:** `052114ad40a5029f264ecf8373ea4bb9ce25b19d`

**Diff base:** `1b4d4caea7ba81f9f5668d07571f18e7cb4c5ec1`

**Review date:** 2026-10-28

**Suggestion branch:** [review/pr14043-suggestions-20261028](https://github.com/newling/rocm-libraries/tree/review/pr14043-suggestions-20261028), based on the reviewed head.

| Commit | Review item |
| --- | --- |
| [a560b125003](https://github.com/newling/rocm-libraries/commit/a560b1250039bc7e14c6179a5b4456c14e2f6363) | Extend the scale-stride argument tests |
| [b8072a0a8d7](https://github.com/newling/rocm-libraries/commit/b8072a0a8d7d6fdd46e7bb673ba72965670d697a) | Keep source comments focused on the lasting contract |

Both commits are optional. The second applies after the first because both edit comments in the same test file. Neither changes runtime behavior.

## Tests

The submitted head built successfully with the ROCm compiler, MX support enabled and legacy rocRoller disabled; all 12 directly relevant native tests passed, as did seven gfx950 numerical cases in rocjitsu. The suggestion branch's six scale-stride tests also passed against that submitted runtime; the comment-only commit was verified to change no code lines, and `git diff --check` passed.

The seven numerical cases covered BF8, BF6, mixed BF8/BF6, unaligned output widths, and a preswizzled FP4 control. These results reuse the exact-head build and experiments performed while reconciling [#14370](https://github.com/ROCm/rocm-libraries/pull/14370). They used retained device kernels from [#14045](https://github.com/ROCm/rocm-libraries/pull/14045), rather than fresh device-library generation. The six natural-scale cases pass without #14370 and fail numerically when its client row-padding workaround is applied; the preswizzled control passes both ways. This directly supports retiring that workaround.

An additional heuristic-path BF8 case selected the expected natural-scale kernel and passed numerical checking. Mixed natural/preswizzled scale probes were rejected by existing API validation before reaching `getRocRollerSelectedSolutions`; those probes do not establish coverage of its new predicate checks. Physical-GPU validation, padded data leading dimensions, and the rocRoller-enabled/disabled StreamK selection comparison were not run locally. The PR description assigns the latter comparison to the later kernel-library landing in the stack.

Required CI checks are still red. The [TensileLite coverage job](https://github.com/ROCm/rocm-libraries/actions/runs/40724309204/job/122943552247) fails `test_occupancy_probe_emission`: it expects `global_store_dword`, while the instruction prints as `global_store_b32`. Math CI also reports an occupancy-probe `ArchAccUnifiedRegs` error. The affected Python generator, test and rocisa sources are unchanged by this diff. Other inspected failures were container setup or checkout failures, including a Math CI merge attempt against an unavailable commit. Conversely, the gfx950 build and race check, gfx90a ASAN tests, and pre-commit passed. These observations support reviewing the code independently of the red gates; they do not establish that the PR is ready to merge.

## Summary

The PR fixes a disagreement between the scale buffer supplied by hipBLASLt and the stride passed to an external custom kernel. At K=128 with blocks of 32, a compact row contains four scales, while the Tensile descriptor reports a padded pitch of eight. The new caller flag makes argument packing use four for hipBLASLt while preserving the descriptor stride for the separate TensileLite client, which actually allocates padded rows. Keeping those two caller contracts distinct is the right approach.

The selection changes distinguish StreamK, ordinary workgroup mapping, and preswizzled kernel names, then check hardware/problem eligibility and available workspace before returning a candidate. No correctness blocker was established in the reviewed diff. I would approve these code changes with the suggestions below treated as nonblocking, while leaving merge contingent on the remaining CI and stack integration checks.

## Actionable items

No blocking correctness findings. The comments below concern additional coverage and clarity.

## Suggestions

### Extend the scale-stride argument tests

At [CustomKernel_test.cpp:313](https://github.com/ROCm/rocm-libraries/blob/052114ad40a5029f264ecf8373ea4bb9ce25b19d/projects/hipblaslt/tensilelite/tests/CustomKernel_test.cpp#L313), the batch test covers only packed scales with the legacy argument layout. The changed argument packer also has a DataParallel version-1 branch, a `useInitialStridesAB` branch, and a default descriptor-layout branch. A regression in any of these could leave the existing test green.

Commit [a560b125003](https://github.com/newling/rocm-libraries/commit/a560b1250039bc7e14c6179a5b4456c14e2f6363) extends the existing probe to cover those branches, including free-dimension padding and partial blocks of 16 and 32. For M=N=60 and K=128, it checks a compact batch stride of 240 against a descriptor batch stride of 512. These are argument-packing checks, not claims that every probe shape is supported by a shipped device kernel. All six scale tests pass on the submitted implementation; this is preventive coverage rather than a newly reproduced defect.

### Keep source comments focused on the lasting contract

The introductions in [mx_scale_setup.hpp:6](https://github.com/ROCm/rocm-libraries/blob/052114ad40a5029f264ecf8373ea4bb9ce25b19d/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/mx_scale_setup.hpp#L6), [rocroller_kernel_match.hpp:21](https://github.com/ROCm/rocm-libraries/blob/052114ad40a5029f264ecf8373ea4bb9ce25b19d/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/include/rocroller_kernel_match.hpp#L21), their tests, and [tensile_host.cpp:7260](https://github.com/ROCm/rocm-libraries/blob/052114ad40a5029f264ecf8373ea4bb9ce25b19d/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L7260) repeat the extraction history and refer to line numbers in other files. That makes a small contract harder to find and gives future edits several copies to maintain.

Commit [b8072a0a8d7](https://github.com/newling/rocm-libraries/commit/b8072a0a8d7d6fdd46e7bb673ba72965670d697a) keeps the useful explanations of caller layout, name delimiters, StreamK/WGM interaction, and predicate/workspace filtering while shortening the surrounding history. Every changed line is a whole-line comment or whitespace; runtime code and compiler diagnostics are unchanged.

### Bring the description into line with the final implementation

In the PR description's “Technical Details,” update the statements that the batch stride stays padded and that compact stride calculation is unconditional. The reviewed head now selects both row and batch strides according to `customKernelMXScalesArePacked()`. The description also says the PR has no dependency, although its current base is the branch associated with [#14086](https://github.com/ROCm/rocm-libraries/pull/14086).

These details matter when deciding whether to retain a client workaround such as #14370. No replacement description was drafted or applied because this task requested a review.

## Commentary

The host setup helpers have a useful responsibility: they attach the descriptor and the caller-layout declaration together. The default remains appropriate for the TensileLite client. The flag changes emitted arguments, rather than which kernel is eligible, so its absence from the solution-cache comparison does not by itself establish a cache bug.

The new hardware/problem/workspace checks are important protection beyond name matching. The added name-matcher tests do not execute that selection loop. The later integration comparison should explicitly exercise a rejected predicate and insufficient workspace, and verify that selection continues to a usable candidate. A selection-fixture refactor was not included in these suggestions because the planned comparison depends on the later captured-kernel library in the stack.

The two linked commits above are the complete implementation handoff; the description corrections and later selection integration coverage remain unimplemented.
