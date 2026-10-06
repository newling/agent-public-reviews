This is a review from an agent with an automatic prompt from the reviewer

> Superseded by the [audited review](review_pr13060_audit_20261006.md), which corrects incomplete handling of copied addresses in the earlier fix. The original draft is preserved below.

**PR reviewed:** [ROCm/rocm-libraries#13060](https://github.com/ROCm/rocm-libraries/pull/13060)

**Reviewed head:** [`0e3cc4944a998f61b3f1f0934538abf396cbf48f`](https://github.com/ROCm/rocm-libraries/commit/0e3cc4944a998f61b3f1f0934538abf396cbf48f) (2026-10-06). Public repository and head; existing reviews and discussion comments were not consulted.

**Local review branch:** `review/pr13060-suggestions-20261006`, based on that exact head. Commits in order: [`6be02800f34`](https://github.com/newling/rocm-libraries/commit/6be02800f34a88d488181dc4759209c9e6a5873c) checks carry ordering on reachable paths; [`3838b580396`](https://github.com/newling/rocm-libraries/commit/3838b580396fb183ef2c4771b296ec1275475180) handles the implicit addk source; [`1c8c09fc87a`](https://github.com/newling/rocm-libraries/commit/1c8c09fc87ae1e78c4933b7c623edce2039f13ba) distinguishes scalar reads from carry writes; [`e931587ab08`](https://github.com/newling/rocm-libraries/commit/e931587ab08b0faa2a9efc753b9603a3f3aaca5e) preserves disassembly label aliases. Later commits are based on the preceding fixes.

## Tests

Built rocisa; the final lint suite passes 57 tests, including generated kernels and all new regressions. Black and whitespace checks pass. Each finding was reproduced before its fix. Two gfx1250 assembly cases skip because the local ROCm 7.1 assembler does not support that target.

The submitted head has passing Math CI, ASAN and pre-commit checks. Failed gfx1250, coverage and rocSOLVER multi-architecture checks remain unattributed.

## Summary

This checks for 32-bit arithmetic on the low word of a 64-bit address when no matching high-word carry is visible. Direct instruction examples, compiled disassembly and generated kernels are useful complementary tests. Source and disassembly share the parser and analysis. The existing CFG is a useful foundation for the ordering checks below.

## Actionable items

### Check carry before every reachable use

The scalar/vector carry scans in `projects/hipblaslt/tensilelite/Tensile/Utilities/address_carry_lint.py` accept a carry later in the linear instruction sequence even when an address was already used, or a conditional branch bypasses that carry. For example, `s_add_u32 s8, s8, 64; s_load_dword s0, s[8:9], 0; s_addc_u32 s9, s9, 0` is silently accepted. Conversely, a valid unconditional branch to the matching carry is reported. See `carried_before_use` at suggestion-branch line 363.

Commit [`6be02800f34`](https://github.com/newling/rocm-libraries/commit/6be02800f34a88d488181dc4759209c9e6a5873c) follows the existing CFG, keeping the carry and copied-low obligations until the corresponding high update. Tests cover scalar/vector use-before-carry, branch bypass and valid cross-branch chains, while retaining the existing copied-address case. This remains a bounded heuristic, including existing copy/search limits.

### Include the implicit input of s_addk_i32

The constant-only exemption in `lint` in the same file treats `s_addk_i32 s8, 64` as having no register input, although it adds to its destination. An uncarried pointer increment followed by `s_load_dword s0, s[8:9], 0` is ignored. See suggestion-branch line 426. Commit [`3838b580396`](https://github.com/newling/rocm-libraries/commit/3838b580396fb183ef2c4771b296ec1275475180) excludes that instruction from the exemption and adds a regression.

### Distinguish scalar sources from vector carry writes

In `carry_writes` in the same file, operand 1 of a scalar add is a source, but the submitted helper treats it like the second destination of vector carry instructions. Valid vector carry in `s[20:21]` is considered overwritten by `s_add_u32 s30, s20, 1`, which only reads `s20`. See suggestion-branch line 348. Commit [`1c8c09fc87a`](https://github.com/newling/rocm-libraries/commit/1c8c09fc87ae1e78c4933b7c623edce2039f13ba) limits the second-destination interpretation to vector carry instructions and tests a valid low/high chain with that scalar read between them.

### Retain branch-target aliases in disassembly

Default objdump output can omit a label aliasing the kernel entry while branches still refer to that label. The CFG loses the backward edge and misses an uncarried address use on the next loop iteration. See `disassemble` in the same file, suggestion-branch line 464. Commit [`e931587ab08`](https://github.com/newling/rocm-libraries/commit/e931587ab08b0faa2a9efc753b9603a3f3aaca5e) adds `--show-all-symbols` and an assembly/disassembly regression with a loop label at the entry address. The original source reports the issue, original disassembly misses it, and fixed disassembly agrees with source.

## Suggestions

No scope expansion requested. Keep findings framed as suspicious sequences for investigation, consistent with the documented heuristic scope.

## Commentary

The appropriate levels for this developer tool are instruction-level unit tests, assembly/disassembly and representative generated kernels. New regressions use the existing unit suite; no feature flag or omitted-test waiver is needed. Exhaustive GPU execution would not directly test the parser/CFG contract. All minimal reproducers are committed with their fixes. No branch was pushed or review posted. Remaining omissions are gfx1250 assembly with a supporting toolchain and attribution of failed CI checks.
