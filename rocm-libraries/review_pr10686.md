> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#10686](https://github.com/ROCm/rocm-libraries/pull/10686)

## Tests

`git diff --check` passed for the two-file delta unique to this PR. No Python tests were run because the submitted head has no Python-test change outside `skill`/`skills`; a merge-tree check against current `develop` fails with an add/add conflict in `projects/hipblaslt/skills/tensilelite-mutation-rerun/SKILL.md`. The current `therock-pr-bot` failure is a timeout waiting for required checks, while the docs-only Math CI summary passes by skipping its status gates.

## Summary

As currently submitted, this PR does not contain an actual Python-test delta to review. PR #10685 was squash-merged into `develop`, but this branch still descends from the pre-merge #10685 head. That stale ancestry makes GitHub show 15 changed files. The three displayed files outside `skills`—the characterization README, `pyproject.toml`, and `tox.ini`—are byte-identical in the pre-merge #10685 head, the merged #10685 commit, and this PR head. Relative to its intended dependency, #10686 uniquely changes only `SKILL.md` and the new `references/covering-set.md`.

The unique documentation usefully requires an explicit test list, target-file rather than package-total coverage, a successful pytest run, and a reproducible selection record. It also explains the cost and scope tradeoff of excluding hardware-driven `common` tests. However, the branch must first be restacked, and the proposed coverage gate does not establish that a reduced set includes the existing assertions relevant to mutation results.

## Actionable items

1. **Must address before merge — `projects/hipblaslt/skills/tensilelite-mutation-rerun/SKILL.md:1-51`: restack this PR onto the merged #10685 revision.**

   The current head repeats the full #10685 patch against an old merge base, and a three-way merge with current `develop` produces an add/add conflict in `SKILL.md`. This also makes the review UI present 13 already-merged or inherited files as if #10686 changed them. Rebase or otherwise restack the branch onto current `develop`, retain only the intended covering-set additions, resolve `SKILL.md` against the merged version, and rerun the focused checks on that resulting head. This is required before the submitted revision can be merged or its final diff reviewed reliably.

2. **Important — `projects/hipblaslt/skills/tensilelite-mutation-rerun/references/covering-set.md:3-19,47,60-70,80-94`: do not certify a reduced test selection from line coverage alone, and correct the Utilities example.**

   The document says the covering set avoids missing module behavior and records `status: "ok"` when selected tests pass and cover at least 80% of the file. Those facts show that lines executed, but not that the selection contains the assertions which distinguish a mutant from the original behavior. The concrete example selects only `Tensile/Tests/unit/characterization/CommonUtilities`, even though the repository also has the dedicated `Tensile/Tests/unit/Common/test_Utilities.py`. That direct suite covers distinct boundaries and exact outcomes; its path is missed by the literal `Tensile/Tests/unit/test_<Module>.py` discovery rule.

   Discover dedicated unit tests recursively rather than assuming they live directly under `unit/`, include the existing Utilities unit file in the example, and validate a reduced selection by comparing its per-mutant outcomes with the complete relevant unit-test candidate set. If that comparison is intentionally out of scope, describe the threshold as a coverage-based scheduling heuristic rather than evidence that the selected tests do not miss behavior, and do not label the selection unconditionally `ok`.

## Suggestions

None beyond the actionable items above.

## Commentary

Several commits in this branch's history temporarily changed `Tensile/Tests/unit/characterization/LibraryIO/test_parse_integration_char.py` and added Python mutation-helper tests outside the skill tree, but later commits explicitly removed those changes before the submitted head. They therefore are not part of PR #10686's current merge result and should not be reviewed or credited as this PR's test coverage. If the intended review target is one of the later mutation-driven Python-test PRs in the stack, it should be reviewed from that PR's final diff after the stack is restacked.
