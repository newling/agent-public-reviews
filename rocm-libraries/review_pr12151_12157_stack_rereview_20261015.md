This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12153](https://github.com/ROCm/rocm-libraries/pull/12153)

**Scope:** follow-up review of #12151–#12157 on 2026-10-15, explicitly checking previous review comments and independently inspecting the updated cumulative diff. All seven public heads were unchanged at the final refresh. The original [published review](https://github.com/newling/agent-public-reviews/blob/4e775b3c286a3f385fe35b38668f96b1e6a94e8a/rocm-libraries/review_pr12151_12157_stack_20261009.md) remains unchanged.

**Review branch:** [review/pr12151-12157-rereview-20261015-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12151-12157-rereview-20261015-suggestions), based on submitted #12157 head [fa9035337ad9](https://github.com/ROCm/rocm-libraries/commit/fa9035337ad9b1df3760e9261bf038766891770a).

| Item | Suggestion commit |
|---|---|
| Snapshot guard's remaining default-path defect | [e8e4ddef55af](https://github.com/newling/rocm-libraries/commit/e8e4ddef55afcdc94d3782d174552393f68153c2) |
| Wheel still includes the source-only test | [5c833005f074](https://github.com/newling/rocm-libraries/commit/5c833005f074ea7e0dc133bb6f6c67467d05eae7) |
| Root PR's new conflict with develop | No commit; requires refreshing and restacking the author's branches. |

The two commits touch separate behavior and can be inspected or cherry-picked independently. Prefer integrating existing #13409 for the guard issue if that PR lands first.

## Tests

Built the submitted Python wheel and rocisa; 664 focused tests, two unchanged snapshots, and 12 wheel/source-launcher probes passed. Complete unit/common collection, full-diff root pre-commit, and whitespace checks succeeded. Both suggestion fixes have failing-before/passing-after checks, and the final guard/source-only suites passed together.

Testing used Python 3.12, ROCm 7.1, AMD clang 20, and an out-of-tree Ninja build. The focused runs cover custom-kernel metadata, all previously missed import files, the stepping child-process environment, gfx1201 assembly generation, namespace identity, resources, library-creation helpers, CPU-only flow, and temporary-build preservation. Another 77 selected gfx1250 cases skipped because this compiler does not support gfx1250. No complete unit execution, GPU/client workload sweep, or full hipBLASLt rebuild was performed; those would duplicate broader automation without resolving the Python loading questions. Collection is not execution.

On the submitted head, a four-snapshot counterexample makes the default guard report zero changes and return success. The explicitly supplied directory detects the same change. The new regression reproduces the defect; after the first suggestion commit, the guard suite and counterexample pass. The second regression builds a wheel and inspects its actual contents: it fails against the original packaging settings and passes after the wheel exclusion. The submitted wheel independently reproduces `FileNotFoundError` in its packaged source-only test.

At the 2026-10-15 18:09 UTC snapshot, Math CI passed on #12153–#12157, #12151 remained pending, and [#12152 precheckin](https://math-ci.amd.com/job/rocm-libraries/job/precheckin/job/hipblaslt/job/PR-12152/16/stages/) failed on gfx950. Its failing case is `nightly_matmul_fast_check_every_solution_repeat_f16_rf16_rf16_rf16_rf32_r_NN_4099_2053_129_2_4099_129_n2_4099_4099_1_APIFindAllAlgo`: one of 1,071 solutions fails on repetition 2. This is a numerical test failure, not a runner setup error. The reviewed changes do not modify the kernel arithmetic, selection rules, or parsed YAML settings, so the evidence does not attribute it to this migration. It still needs an explanation or follow-up from the owning team.

The current Codecov project checks on #12153–#12157 fail their absolute 80% targets; at #12157 the reported values are 49.70% for TensileLite C++ and 43.30% for hipBLASLt. Patch coverage and TensileLite unit coverage pass. These are different from the old coverage job's missing-path failure: the workflow paths are now correct. The policy bot passes on all seven PRs. GitHub reports unknown mergeability during refresh, but a local merge calculation establishes the root conflict described below.

## Summary

TensileLite generates hipBLASLt's matrix-multiplication kernels. The merged parent moved its Python implementation from `Tensile` to `tensilelite` and retained a compatibility alias. These seven PRs migrate the tests, mock targets, command launchers, and package-owned text to the new name.

The revised stack repairs the earlier metadata collection error and generator import, completes the missing test imports, and preserves module identity through the legacy alias. The wheel probes verify shared mutable state, shared mock targets, package resources, loading an old-spelling pickle, both namespace import orders, module commands, and source-launcher fallback.

| PR | Reviewed head | Incremental scope |
|---|---|---|
| [#12151](https://github.com/ROCm/rocm-libraries/pull/12151) | [98e3b70250c7](https://github.com/ROCm/rocm-libraries/commit/98e3b70250c7dca13ed0bd999f6f14d9c61408da) | Common and early characterization imports. |
| [#12152](https://github.com/ROCm/rocm-libraries/pull/12152) | [0a03025db68a](https://github.com/ROCm/rocm-libraries/commit/0a03025db68a953f851968cfd182a75bdf32c1c8) | Further characterization imports and mock targets. |
| [#12153](https://github.com/ROCm/rocm-libraries/pull/12153) | [bab5ce8f02ef](https://github.com/ROCm/rocm-libraries/commit/bab5ce8f02efcdaea4109564fbaf369d5e57ce64) | Codegen and metadata test imports, including their repairs. |
| [#12154](https://github.com/ROCm/rocm-libraries/pull/12154) | [a07812b7c802](https://github.com/ROCm/rocm-libraries/commit/a07812b7c80258b4c9605a6ebccfd96c7e96c1bd) | Remaining ordinary unit imports and stepping-test repair. |
| [#12155](https://github.com/ROCm/rocm-libraries/pull/12155) | [c7c4d0661c8b](https://github.com/ROCm/rocm-libraries/commit/c7c4d0661c8b5da95f2a138985831e889bad8f0c) | Follow-up test imports and helpers. |
| [#12156](https://github.com/ROCm/rocm-libraries/pull/12156) | [b941a75331e6](https://github.com/ROCm/rocm-libraries/commit/b941a75331e60e44ca2e0a8fd2d43dd63be2076b) | Paths, generated fixture text, source references, and diagnostic expectations. |
| [#12157](https://github.com/ROCm/rocm-libraries/pull/12157) | [fa9035337ad9](https://github.com/ROCm/rocm-libraries/commit/fa9035337ad9b1df3760e9261bf038766891770a) | Runtime references, terminology, import guard, and CMake source-only exclusion. |

The cumulative diff from merge base [2e5ef67c4afa](https://github.com/ROCm/rocm-libraries/commit/2e5ef67c4afa6b8883351cf5c024c5aef9bcd160) changes 465 files, +2,449/-2,403 lines. Normalized Python comparison identifies only the intended namespace/text edits, equivalent import rearrangements, and the new source guard. No existing test function is removed; all 26 changed YAML files parse identically before and after, and no `.ambr` file changes. These checks support retaining the mechanical migration and existing expected results.

### Previous comments checked

Read every paginated review, inline comment, discussion comment, and review thread on the seven PRs. They contain six reviews, no inline comments or threads, and no written author response to the linked four-item review. Resolution below is based on code and tests, not acknowledgement.

| Previous concern | Current result |
|---|---|
| Invalid/duplicated metadata imports and stale package variable | Addressed in #12153. Imports are valid, predicate constants remain, and resource paths use `tensilelite.__file__`. Metadata tests pass. |
| Seven missed imports, old `sys.modules` lookup, and stepping `NameError` | Addressed by #12152 and #12154. All five affected files use the new namespace; the final guard and focused tests pass. |
| Nonexistent gfx1201 generator import | Addressed in #12153 using `tensilelite.TensileCreateLibrary.Run`. The same three assembly cases pass. A later internal-module rename is no longer needed to make this intermediate PR valid. |
| Coverage workflow, uniqueness selector, and snapshot default | Workflow and selector are corrected in the rebased base. The default remains unresolved in every reviewed head; see item 1. |
| Predecessor links in descriptions | #12152–#12157 now link their immediate predecessor. #12151 links merged #12150, although its technical details still repeat an old branch suffix. Cosmetic. |
| Optional script/recipe to reconstruct the mechanical diff on #12151 | No recipe was added. The original reviewer explicitly presented this as a thought, not a request. No correctness issue follows from leaving it optional. |
| Existing LGTM/approval comments | No additional technical requests. They do not replace checking the revised heads. |

Also checked the five concrete concerns in the merged [#12150 review](https://github.com/ROCm/rocm-libraries/pull/12150#pullrequestreview-5435800142): the race-check driver path, decision-document ownership paths, unused `cmake/*` package-data block, mutation command paths, and geko test fixture path are all corrected in the reviewed tree. The author's parent reply clarifies physical moves versus deferred import migration. The other parent observations concern cosmetic text/whitespace and the pre-existing ambiguity of the separately shipped Tensile package; they do not establish additional unresolved fixes in these seven PRs.

## Actionable items

### 1. Complete the snapshot guard's default-path correction

[`check_snapshot_diff.py:54`](https://github.com/ROCm/rocm-libraries/blob/fa9035337ad9b1df3760e9261bf038766891770a/projects/hipblaslt/tensilelite/tensilelite/Tests/unit/characterization/tools/check_snapshot_diff.py#L54) still defaults to `Tensile/Tests/unit/characterization`. With `--characterization-dir` omitted, four changed snapshots in the current repository layout return exit 0 and print `OK - 0 .ambr file(s) changed (threshold 3)`. This leaves the final part of previous item 4 unresolved. The workflow supplies an explicit directory, so its repaired invocation does not suffer this default-path defect.

Integrate [#13409](https://github.com/ROCm/rocm-libraries/pull/13409), open at [0ed6913d7ac1](https://github.com/ROCm/rocm-libraries/commit/0ed6913d7ac1fd79f2e6d4a95a385cc92bcb7501) at the review snapshot, or apply the narrow correction in suggestion commit [e8e4ddef55af](https://github.com/newling/rocm-libraries/commit/e8e4ddef55afcdc94d3782d174552393f68153c2). The separate PR also checks nonexistent directories and has already incorporated feedback on that behavior; those changes are outside this seven-PR review. Its presence does not change the reviewed heads. The suggestion commit corrects the default and retains an explicit non-default-directory test alongside its new regression.

### 2. Exclude source-only checks from the wheel too

[`pyproject.toml:117`](https://github.com/ROCm/rocm-libraries/blob/fa9035337ad9b1df3760e9261bf038766891770a/projects/hipblaslt/tensilelite/pyproject.toml#L117) discovers every `tensilelite*` package, while `MANIFEST.in` recursively includes Python files. Consequently the submitted wheel contains `tensilelite/Tests/unit/source_only/test_canonical_imports.py`. Its [`test_installed_artifacts_exclude_source_only_tests:55`](https://github.com/ROCm/rocm-libraries/blob/fa9035337ad9b1df3760e9261bf038766891770a/projects/hipblaslt/tensilelite/tensilelite/Tests/unit/source_only/test_canonical_imports.py#L55) reads a repository CMakeLists.txt that the wheel does not ship. Running that packaged module produces `FileNotFoundError`; the other two checks pass.

The CMake exclusion added by #12157 is appropriate, but it covers only CMake-installed artifacts. Exclude this directory from both setuptools package discovery and package data while retaining it in the source checkout. Suggestion commit [5c833005f074](https://github.com/newling/rocm-libraries/commit/5c833005f074ea7e0dc133bb6f6c67467d05eae7) implements this and adds a source test that builds the wheel in temporary storage, checks the directory is absent, and verifies the compatibility shim and resource module remain packaged. No test is disabled to conceal a failure; this check depends on repository files and belongs in source validation.

Reproduce on the submitted wheel after unpacking it:

```sh
python -m pytest --noconftest -q \
  "$WHEEL_DIR/tensilelite/Tests/unit/source_only/test_canonical_imports.py"
```

### 3. Refresh the root PR without losing the new version-probe tests

[`test_global_parameters_char.py:100`](https://github.com/ROCm/rocm-libraries/blob/98e3b70250c7dca13ed0bd999f6f14d9c61408da/projects/hipblaslt/tensilelite/tensilelite/Tests/unit/characterization/GlobalParameters/test_global_parameters_char.py#L100) now conflicts with develop [2501d0b28cce](https://github.com/ROCm/rocm-libraries/commit/2501d0b28cce0ab9e9961b237a350e442bc99d5a). The root changes `from Tensile import __version__` to the lowercase spelling beside `_stub_hipcc(monkeypatch)`. Develop independently replaces the old compiler probe with `_set_rocm_version(monkeypatch)` and updates the version-failure test. A read-only `git merge-tree --write-tree` calculation reports this content conflict.

Refresh #12151 and restack its descendants, preserving develop's new version helper/failure test and the lowercase import. Recheck those tests and the final import guard after integration. No suggestion commit changes the submitted version-probe behavior: applying only the upstream test would mismatch this head's implementation, while a rebase would replace the exact reviewed base. This requires a coordinated stack refresh rather than an isolated fix on the review branch.

## Suggestions

Remove the redundant old dependency branch suffix from #12151's technical details; its existing #12150 link is sufficient. No PR-description rewrite was requested or drafted.

## Commentary

The relevant test level is Python unit/characterization testing plus wheel and command-launcher checks. The alias identity tests and unchanged saved results are useful evidence because this migration must preserve which module receives a mock and which object owns global settings. Device arithmetic and selection are unchanged, so a new numerical GPU sweep is not needed to assess those edits. Existing Math CI remains relevant integration evidence, including its unresolved failure.

The final source guard adds a concrete protection against accidental legacy imports. Its scope intentionally excludes the compatibility suite and uses repository files for the install-rule check. The CMake and wheel exclusions should express that same source-only boundary. This stack introduces no new numerical type, public runtime API, serialization format, or ownership/lifetime rule; the old-spelling pickle probe confirms the retained compatibility path.

Handoff: published branch [review/pr12151-12157-rereview-20261015-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12151-12157-rereview-20261015-suggestions) ends at [5c833005f074](https://github.com/newling/rocm-libraries/commit/5c833005f074ea7e0dc133bb6f6c67467d05eae7), with the two-item commit mapping above. Both bounded code fixes are implemented and validated. Stack refresh, remote checks, and the gfx950 failure explanation remain with the author/reviewer. This rereview and its suggestion branch are published; no rebase or CI rerun was performed.
