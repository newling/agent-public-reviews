> This is a review from an agent with an automatic prompt from the reviewer

# Review: PR #12125 — revert gfx950_id75a3 GEKO equality logic

**PR reviewed:** [ROCm/rocm-libraries#12125](https://github.com/ROCm/rocm-libraries/pull/12125)

Date reviewed: 2026-09-17  
Commit reviewed: `bf8c53cc53874dd3583f8dc217d501c4f5e57f8a`

## Tests

Local `TensileLogic --check-all` validation using the current `develop` implementation accepted all 2,746 BBS and 154 XSS solutions in the changed files with zero rejects; the full gfx950 corpus accepted 77,384 solutions, with two documented known-bug skips outside these files. YAML parsing, solution/reference consistency, the exact pre-#11941 content comparison, `KernArgsVersion` removal check, and `git diff --check` also passed.

Public CI built the gfx950 device library and passed all 45,303 tests it executed on an MI355X reporting PCI chip ID `0x75a3`. The aggregate checks are red for unrelated reasons: the gfx942 precheckin leg exhausted device memory in two 16 GiB allocation tests and returned an invalid argument in one smoke test, the ASAN job failed while fetching sources, and the gfx1250 job produced no test report.

## Summary

This PR restores two device-ID-specific gfx950 equality-logic files to their exact state immediately before #11941. Semantically, it removes 29 BBS and 10 XSS GEKO solutions. In the BBS file, 27 newly added exact problem sizes disappear and two existing problem sizes return to their former solutions; in the XSS file, 10 newly added problem sizes disappear. That is the intended set of 39 routing changes from #11941.

The whole-file replacement creates a much larger textual diff because the tuning merge reserialized existing entries. Normalizing serialized defaults shows that the retained BBS solutions are unchanged apart from the integer/string spelling of code-object version. The retained XSS solutions restore `MaxOccupancy` from 64 to their pre-#11941 value of 40, while all other normalized solution parameters and all common problem-to-solution mappings remain the same. The current validator accepts the restored schema defaults.

Only #11943 touched these files after #11941 and before this PR's base, and its 39 edits solely removed `KernArgsVersion: 2` from the newly added solutions. None of those settings are reintroduced by this rollback. The two files have also not changed between the PR base and current `develop`, and the PR merges with current `develop` without conflict.

## Actionable items

None.

## Suggestions

None.

## Commentary

The public gfx950 run now answers the uncertainty recorded in the PR description: the runner does select the `gfx950_id75a3` tree, because it reports PCI chip ID `0x75a3`, and the complete target test run passes with this rollback. Updating the verification checklist before merge would make that evidence visible to later readers.
