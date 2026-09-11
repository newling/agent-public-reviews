This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#11473](https://github.com/ROCm/rocm-systems/pull/11473)

**Revision reviewed:** rebased candidate `b00b53553b`, based on `origin/develop` commit `28347f77f8`.

## Tests

The isolated `rocjitsu_tests` target built successfully; 27 focused generator metadata tests and 2 decoded-metadata/hook-ordering C++ tests passed. Full ten-ISA regeneration was reproducible, the changed-file hooks passed on the rebased stack, and the published PR checks are green.

## Summary

The design is sound for instructions modeled through rocJITsu's memory pipelines. It makes wait-counter membership, completion ordering, a possible second counter obligation, and EXEC masking immutable properties of the decoded instruction, so a plugin can inspect them in the existing before-instruction hook without parsing mnemonics or waiting until address calculation. Keeping `MemoryCompletionClass` separate from `WaitCounterType` is especially important: scalar memory and LDS can share LGKMCNT without sharing a FIFO completion guarantee.

The generator is the single source for both constructor metadata and execution-state counter assignment. Generic FLAT is represented conservatively as unordered with two counter domains, while fixed GLOBAL/SCRATCH forms retain one known domain. Returning versus non-returning atomics are selected from encoding fields, and the architecture profile explicitly controls the cases where non-FLAT VMEM stores can join the ordered VMEM class. The generated-only final commit and direct hook-ordering test make the large mechanical portion reviewable.

I found no correctness issue in this layer itself.

## Actionable items

None.

## Suggestions

### Document that this is not a complete inventory of counter-producing instructions

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/memory_issue.h:24-35`
- `emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:332-367`
- `emulation/rocjitsu/lib/python/amdisa/semantics.py:1749-1750`

The descriptor covers operations represented by `ScalarMemState` or `VectorMemState`, but hardware wait counters also cover events outside those pipelines. Examples include `S_MEMTIME`/`S_MEMREALTIME`, returned messages, and some barrier-state operations. The follow-on capacity work already needs special handling for messages, while timestamp operations currently have neither metadata nor a separate accounting path.

State this boundary in `MemoryIssueInfo`'s contract so consumers do not interpret `is_memory_op()` plus this descriptor as a complete counter-occupancy stream. If finite-counter accounting is expected to become a general consumer, consider a broader counter-issue descriptor or an explicit companion mechanism for non-memory events rather than accumulating mnemonic checks.

## Commentary

Placing this small descriptor in the existing padding of `Instruction` avoids adding a callback or changing hook order. The architecture-specific accessor in the generic instruction base is a pragmatic coupling, and the name makes that coupling visible.

The conservative `UNORDERED` classification for generic FLAT is a useful contract: it prevents downstream consumers from inferring FIFO completion merely because the operation carries VMCNT and LGKMCNT obligations. A later consumer may refine behavior using the resolved route, but that should be explicit rather than inferred from the counter name.

At the time of review, #11473 has no human review or inline discussion. Its only discussion comments are automated policy results. The published head is behind `develop`, so GitHub currently reports a merge conflict; the rebased candidate reviewed here resolves that overlap and preserves the newly merged packed-atomic generator behavior.
