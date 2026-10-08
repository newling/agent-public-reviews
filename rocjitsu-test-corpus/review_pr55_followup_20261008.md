This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocjitsu-test-corpus#55](https://github.com/ROCm/rocjitsu-test-corpus/pull/55)

**Reviewed head and suggestion-branch base:** [`10ea5cda34eb0a37aa694863a8c97e86c3c3b15b`](https://github.com/ROCm/rocjitsu-test-corpus/commit/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b).

**Review mode:** follow-up incorporating all four published reviews, all eight inline comments and replies, all three discussion comments, the [previous agent review](https://github.com/newling/agent-public-reviews/blob/main/rocjitsu-test-corpus/review_pr55.md), and the prior design discussions supplied by the reviewer. Findings were checked against the current source and experiments. The repository, fork, and reviewed branch are public.

**Suggestion branch:** [`review/pr55-followup-20261008`](https://github.com/newling/rocjitsu-test-corpus/tree/review/pr55-followup-20261008), tip [`9349ea5`](https://github.com/newling/rocjitsu-test-corpus/commit/9349ea543140008dd1db23045509ed2627e753fb). The PR branch remains at the reviewed head. This is a new review; the previously published review is preserved.

| Item | Commit | Change |
| --- | --- | --- |
| 1 | [`7a5593e`](https://github.com/newling/rocjitsu-test-corpus/commit/7a5593ef626c2e1effe057566c9a11c7f326b1ce) | Require a complete selected inventory and detect obsolete or absent outputs. |
| 2 | [`69a71e2`](https://github.com/newling/rocjitsu-test-corpus/commit/69a71e286f12ecba4c208b0b700772ee15d522a7) | Retain compiler failure diagnostics. |
| 3 | [`bcee00e`](https://github.com/newling/rocjitsu-test-corpus/commit/bcee00e56a5e063da9517e696bbf8b3f36b0f51d) | Parse quoted compiler flags and reject malformed quoting. |
| Suggestion B | [`f0f6a88`](https://github.com/newling/rocjitsu-test-corpus/commit/f0f6a88c7171338cd2fc93fc00bd764f11652eb9) | Clean temporary check output on every return path. |
| Suggestion A | [`5f9a900`](https://github.com/newling/rocjitsu-test-corpus/commit/5f9a9006bd0fc10a5bfe07df4fc4e0918f67b269) | Run inventory validation through pytest and add the missing test-file license header. |
| 4 | [`6c8ef99`](https://github.com/newling/rocjitsu-test-corpus/commit/6c8ef997aa95af4f5193d4926fe0535359c3031d) | Resolve SDK/compiler paths before changing directories; clarify compiler-discovery naming. |
| Suggestion C | [`9349ea5`](https://github.com/newling/rocjitsu-test-corpus/commit/9349ea543140008dd1db23045509ed2627e753fb) | Add and link the regeneration guide; correct help and workflow descriptions. |

The table follows branch order. Later regeneration tests extend the CLI fixture introduced in the first commit; the relative-SDK regression also uses the compiler fixture updated in the quoted-flags commit. Apply the series in order or carry those test-fixture dependencies when selecting commits.

## Tests

The submitted Python tests and inventory check pass; all pinned gfx950/gfx1250 artifacts regenerate byte for byte and assemble/link with the matching SDK; the expanded regeneration and inventory tests all pass on the suggestion branch.

The SDK was TheRock `10.1.0a20260818`, using its matching core and development packages, including rocWMMA headers. AMD Clang reports LLVM revision [`0bace1908348b840e6aa1b4b6e12151dae208158`](https://github.com/ROCm/llvm-project/commit/0bace1908348b840e6aa1b4b6e12151dae208158), the revision recorded in every pinned `.ident`. This closes the earlier review's uncertainty about whether the identified distribution can reproduce these files: all 37 reproduce exactly with the default flags. The final suggestion branch also passes real regeneration using a relative `ROCM_PATH`, preserves every pinned file's hash, and leaves no check output behind.

Copying the final regression sources onto the submitted tree reproduces the incomplete-check, inventory, diagnostic, quoting, relative-SDK, and cleanup failures described below. The same tests pass on the suggestion branch. The reproductions are committed in [tests/test_regenerate_asm.py](https://github.com/newling/rocjitsu-test-corpus/blob/9349ea543140008dd1db23045509ed2627e753fb/tests/test_regenerate_asm.py); compiler-free inventory coverage is in [tests/test_check_cases.py](https://github.com/newling/rocjitsu-test-corpus/blob/9349ea543140008dd1db23045509ed2627e753fb/tests/test_check_cases.py). Run them with:

```bash
python -m pytest tests/test_regenerate_asm.py tests/test_check_cases.py
```

These failure-path tests use an executable compiler stand-in, so they require no ROCm installation. Real regeneration was checked separately with `python corpus/race/scripts/regenerate_asm.py --check` and `ROCM_PATH` set to the matching SDK. GitHub reports no CI checks for the reviewed head. There is no pre-commit configuration in this checkout; patch whitespace checks pass. Runtime detector scoring was not rerun: this revision changes regeneration and inventory tooling, its assembly is unchanged from the previous review, and mutation generation/execution remains outside this diff.

## Summary

This PR supplies versioned device assembly for a kernel/target inventory and tools to regenerate or audit it. The author has adopted the requested manifest split: the current fields are `id`, `kernel`, `requires`, and the regeneration prerequisite `headers`. Mutation selection, hazard labels, wait-counter descriptions, and exemptions have moved out of this PR.

The revised compiler invocation uses an isolated directory and atomically replaces each destination after successful compilation. The submitted tests verify preservation of existing pinned files and unrelated caller outputs. The `.ident` comparison now also distinguishes a provenance-only change from changes to the remaining text. Both changes address the earlier inline requests and the author's replies are supported by the current implementation. Exact reproduction with the matching SDK provides useful evidence for keeping these assembly snapshots as stable test inputs. The remaining concerns are in the tooling's completeness and handling of caller inputs and failures.

## Actionable items

### 1. Require a complete selected inventory before reporting a match

Locations: [`corpus/race/scripts/regenerate_asm.py:324–340`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/corpus/race/scripts/regenerate_asm.py#L324-L340) and [`:354–363`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/corpus/race/scripts/regenerate_asm.py#L354-L363).

`main()` prints skipped cases but still calls `_report_drift()`, which visits only freshly generated files. With a sole case requiring unavailable rocWMMA headers, `--check` returns 0 and prints `committed assembly matches this toolchain` without compiling or comparing anything. With matching fresh files plus a committed `obsolete.s`, it also returns 0 because that extra file is never visited. An entirely absent fresh target directory is skipped in the same way.

This confirms the [latest incomplete-check comment](https://github.com/ROCm/rocjitsu-test-corpus/pull/55#discussion_r4222268586) and the previous agent review's obsolete-artifact finding. The separate inventory checker can detect an orphan when invoked, but it does not make the regeneration command's own success verdict complete.

Commit [`7a5593e`](https://github.com/newling/rocjitsu-test-corpus/commit/7a5593ef626c2e1effe057566c9a11c7f326b1ce) derives the expected case/target outputs, returns an incomplete status when requested cases are skipped or selection is empty, and compares expected, fresh, and committed filenames. Missing or obsolete outputs are reported. Update mode retains the author's optional-header skip behavior. The regressions exercise the public `main()` path as well as missing directories, obsolete files, and expected outputs absent from both trees.

### 2. Preserve the compiler's diagnostic when reporting a failure

Location: [`corpus/race/scripts/regenerate_asm.py:288–289`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/corpus/race/scripts/regenerate_asm.py#L288-L289).

`CompileError` includes the kernel/target context and captured compiler stderr, but `regenerate()` keeps only its first line. A compiler emitting `error: unknown argument` therefore produces only `FAIL: kernel.hip (gfx950):` at the CLI. The cause is unavailable to the person trying to repair the command. This remains applicable from item 6 of the previous agent review, even though missing optional headers now have a separate skip path.

Commit [`69a71e2`](https://github.com/newling/rocjitsu-test-corpus/commit/69a71e286f12ecba4c208b0b700772ee15d522a7) retains the complete exception text. `test_main_preserves_compiler_diagnostic` runs a failing compiler process, verifies the context and diagnostic in stderr, and checks that the pinned file survives.

### 3. Parse quoted flags before resolving include paths

Location: [`corpus/race/scripts/regenerate_asm.py:319`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/corpus/race/scripts/regenerate_asm.py#L319).

`--cxxflags='-I"headers with spaces"'` is still split on whitespace. The compiler receives a path ending in `"headers`, followed by separate `with` and `spaces"` arguments. The new absolute-path conversion cannot reconstruct the intended include argument. Unmatched quotes are also passed through to compilation instead of being diagnosed by the CLI. This is the quoted-flags suggestion from the previous review, still reproducible at this head.

Commit [`bcee00e`](https://github.com/newling/rocjitsu-test-corpus/commit/bcee00e56a5e063da9517e696bbf8b3f36b0f51d) uses `shlex.split()` without a shell and rejects malformed quoting before invoking the compiler. The regressions inspect the arguments received by an actual compiler stand-in and verify that malformed input never launches it.

### 4. Resolve a relative SDK path before entering the compiler directory

Locations: [`corpus/race/scripts/regenerate_asm.py:151–159`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/corpus/race/scripts/regenerate_asm.py#L151-L159) and [`:187–206`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/corpus/race/scripts/regenerate_asm.py#L187-L206).

The isolated working directory introduces another path dependency. With `ROCM_PATH=rocm` and a valid SDK in the caller's `rocm/` directory, discovery returns `rocm/bin/hipcc`. `subprocess.run(..., cwd=scratch)` then resolves that executable from the compiler's temporary directory and raises `FileNotFoundError: 'rocm/bin/hipcc'`. The configured SDK exists; its relative meaning was lost when the working directory changed.

Commit [`6c8ef99`](https://github.com/newling/rocjitsu-test-corpus/commit/6c8ef997aa95af4f5193d4926fe0535359c3031d) resolves configured/discovered SDK paths and a compiler found through `PATH` before changing directories. The regression reproduces the failure on submitted code and passes after the fix. Real regeneration of the complete inventory also passes with a relative SDK root on the suggestion branch. The same commit addresses the [compiler-discovery naming comment](https://github.com/ROCm/rocjitsu-test-corpus/pull/55#discussion_r4222268600): `find_hip_compiler()` and its error text describe both supported executable candidates.

## Suggestions

### A. Exercise the inventory checker through pytest

Locations: [`corpus/race/scripts/check_cases.py:46–96`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/corpus/race/scripts/check_cases.py#L46-L96) and [`tests/test_regenerate_asm.py:1`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/tests/test_regenerate_asm.py#L1).

The reduced checker correctly checks the current inventory when invoked directly, but no submitted pytest test invokes it. Keep the relevant part of the [latest review's testing request](https://github.com/ROCm/rocjitsu-test-corpus/pull/55#pullrequestreview-5460655605): test the inventory contract now, with mutation-parser tests accompanying the later consumer.

Commit [`5f9a900`](https://github.com/newling/rocjitsu-test-corpus/commit/5f9a9006bd0fc10a5bfe07df4fc4e0918f67b269) adds `tests/test_check_cases.py`. It checks the committed inventory and controlled cases for portable/target-specific ownership, missing sources and assembly, obsolete outputs, unknown fields, duplicate IDs/kernels, absent target directories, and unsupported schema versions. These checker tests also pass against the submitted implementation; the change adds automatic coverage. It also supplies the copyright and MIT SPDX header requested in the [test-file comment](https://github.com/ROCm/rocjitsu-test-corpus/pull/55#discussion_r4222268594).

### B. Remove temporary check output on completion

Location: [`corpus/race/scripts/regenerate_asm.py:321`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/corpus/race/scripts/regenerate_asm.py#L321).

The outer `mkdtemp()` has no matching cleanup. Successful checks, detected drift, compiler failures, and skipped cases all leave a `race-asm-*` directory. This confirms the [existing cleanup comment](https://github.com/ROCm/rocjitsu-test-corpus/pull/55#discussion_r4222268609).

Commit [`f0f6a88`](https://github.com/newling/rocjitsu-test-corpus/commit/f0f6a88c7171338cd2fc93fc00bd764f11652eb9) keeps regeneration and comparison inside a `TemporaryDirectory` context. The regression covers all four outcomes; the real compiler run also confirms that the temporary output is removed.

### C. Put the workflow in a discoverable guide and correct the command examples

Locations: [`README.md:18`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/README.md#L18), [`corpus/race/scripts/regenerate_asm.py:5–17`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/corpus/race/scripts/regenerate_asm.py#L5-L17), [`:294–313`](https://github.com/ROCm/rocjitsu-test-corpus/blob/10ea5cda34eb0a37aa694863a8c97e86c3c3b15b/corpus/race/scripts/regenerate_asm.py#L294-L313), and the PR description.

The [latest documentation request](https://github.com/ROCm/rocjitsu-test-corpus/pull/55#pullrequestreview-5460655605) remains applicable. There is no race guide or inventory link; the script calls the workflow both manual and a CI gate, and argparse flattens its long module docstring into help text. It also still calls regeneration the only part needing a HIP compiler, despite the host-harness compilation described in the previous review, and refers to mutation ordinals in a manifest that no longer contains them.

Commit [`9349ea5`](https://github.com/newling/rocjitsu-test-corpus/commit/9349ea543140008dd1db23045509ed2627e753fb) adds `corpus/race/README.md`, links it from the repository inventory, and gives argparse a short description. The guide covers layout, prerequisites, target selection, quoted include flags, inventory checking, per-file replacement, skip/incomplete behavior, textual versus provenance differences, and the current manual workflow. Source diagnostics now refer to downstream mutation expectations.

The PR description still uses the nonexistent `corpus/race/scripts/regenerate.py` in both examples. Change those paths to `corpus/race/scripts/regenerate_asm.py`. That external edit remains for the author; no replacement description was authored or posted.

## Commentary

The [author's final metadata reply](https://github.com/ROCm/rocjitsu-test-corpus/pull/55#issuecomment-6064406613) is reflected in the reviewed head. It supersedes the earlier reply about correcting the full mutation metadata. The later review was attached to [`0963060`](https://github.com/ROCm/rocjitsu-test-corpus/commit/0963060e7af114b7dd4a0f385c97de885bebde4e), before the split; its mutation-parser and counter-policy portions should follow the removed metadata into the generator PR.

That follow-up should retain the substantive earlier evidence: `fa-barrier-epoch` does not provide tensor-counter coverage; a shared counter such as gfx950 `lgkmcnt` does not by itself identify the raced resource; and the harmless gfx950 `lds_war_pattern` removals need target-aware exemptions. The previous agent review already corrected its initial WMMA concern: ordinal 3 is correct under the companion's zero-based eligible-wait rule. The newly raised negative-index and unsupported-wait concerns concern validating that domain, rather than changing the known correct WMMA value.

The latest counter explanations also need to travel with the consumer: excluding XCNT mutations is a choice to exclude replay-dependent hazards, and does not establish that removing XCNT is always safe; the [matching compiler checks XCNT on register definitions](https://github.com/ROCm/llvm-project/blob/0bace1908348b840e6aa1b4b6e12151dae208158/llvm/lib/Target/AMDGPU/SIInsertWaitcnts.cpp#L2462-L2463). DScnt's DS/FLAT role should not be broadened to ordinary global/buffer/scratch operations. Combined waits, XCNT exclusion, unsupported forms such as `s_wait_alu`, ordinal bounds, and exemption semantics should be tested together with the generator. Those fields and that parser are absent from the current inventory-only checker, so this review does not add them back. The original runtime counterexamples remain available in the previous review.

The earlier discussion of compiler-backed CI remains useful. This pass establishes that the identified SDK can reproduce the current snapshots, while the `.ident` field alone records only compiler provenance. A future reproduction gate would need to retain the matching SDK/header versions and flags as well. The prior preference to keep committed assembly is compatible with such a gate; adding that CI workflow is a separate change.

The handoff is the published branch [`review/pr55-followup-20261008`](https://github.com/newling/rocjitsu-test-corpus/tree/review/pr55-followup-20261008) and the commit mapping above, with focused before/after regressions and real regeneration validated. Omitted implementation is limited to the external PR-description correction, future CI integration, and the mutation-generator policy/schema work that the author explicitly moved to the next PR.
