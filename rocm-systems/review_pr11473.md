This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#11473](https://github.com/ROCm/rocm-systems/pull/11473)

**Revision reviewed:** rebased candidate `97bb3fe445`, based on `origin/develop` commit `28508acbca`.

## Tests

The Clang 20 `rocjitsu_tests` target built successfully; 38 focused hook-ordering, decoded-metadata, wait-counter, and atomic integration tests passed, as did all 25 focused generator metadata tests. Full ten-ISA regeneration matched the checked-in ISA output exactly, all branch-diff pre-commit hooks passed, and `git diff --check` passed.

## Summary

This change makes wait-counter membership, completion ordering, an optional second counter obligation, and EXEC masking immutable properties of decoded AMDGPU memory instructions. Plugins can inspect that information in the existing before-instruction hook without parsing mnemonics or waiting for operand reads and address routing. Keeping completion ordering separate from counter membership is the right abstraction: scalar memory and LDS operations can share a counter without belonging to one usable FIFO completion class.

The generator is the source of both constructor metadata and execution-state counter selection. Generic FLAT instructions conservatively expose both possible counter domains and an unordered completion class, fixed GLOBAL and SCRATCH forms expose their known domain, and atomic metadata follows the decoded return policy. The generated output is reproducible, and the public contract now explicitly states that the descriptor covers rocJITsu's modeled memory pipelines rather than every hardware counter-producing event.

I found no correctness issue in the submitted layer.

## Actionable items

None.

## Suggestions

None.

## Commentary

The rebase preserves the newer atomic floating-point policy and GLOBAL-only decode behavior while adding metadata-aware wait-counter selection. The generated-output test now distinguishes segmented/generic FLAT descriptors from fixed-domain GLOBAL ADDTID forms that share the same generated source file.
