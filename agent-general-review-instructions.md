# Agent PR review instructions

These instructions are used by agents when reviewing PRs.

## Before reviewing

Verify that the PR, the repository, and the branch are all public.
Reviews in this directory are published publicly — do not review PRs
from private repos or internal branches.

## Process

Check out the PR branch, build it, and experiment with it. If you have
ideas for improving the code, try them locally to confirm they work
before suggesting them. The best review makes it very clear what needs
to be done to get the PR to a state you like, without writing the code
for the author.

## Tone and balance

Write as a constructive collaborator. Identify concrete strengths when the
diff or test evidence supports them, especially design choices worth keeping.
Do not manufacture praise, but do not make the review read as a list of faults.

Use sentence case for assessments and severity labels; do not use all-capital
negative labels such as `BLOCKING` or `CHANGES REQUESTED`. Prefer plain phrases
such as “Must address before merge,” “Important,” and “Changes requested.”

Explain each concern fully in one place. The summary may state the overall
assessment, but it should not enumerate findings that are repeated in the
actionable-items section, and commentary should not restate them again.

When an actionable item is supported by a temporary regression test, probe, or
counterexample that is removed from the checkout after validation, preserve the
exact minimal source in an appendix to the review. Include enough surrounding
setup or helper assumptions for the author to compile and run it without
reconstructing the test from prose. Omit an appendix only when the reproducer is
already committed in the PR/repository or is too large to include usefully; in
that case, provide a precise standalone command or a public artifact containing
the reproducer.

All else equal, prefer feedback that aligns the change with the project's existing conventions, helper APIs, and abstraction boundaries.

Reviews should be independent of any existing reviews on the PR. Unless
the reviewer explicitly asks you to look at other reviews, do not read
existing GitHub PR reviews, inline comments, review threads, or
discussion comments. Use the PR description, diff, relevant repository
context, local testing, and CI status as your inputs. If the reviewer
does ask for a follow-up review that considers comments, identify that
as a different review mode and independently evaluate the comments
instead of treating them as validation.

## Review depth

Do a cautious contract pass over every new or materially changed API,
helper, data structure, file format, configuration knob, and cross-module
behavior. Identify the implied contract: inputs, outputs,
ownership/lifetime, ordering or consistency guarantees, fallback
behavior, persistence/serialization behavior, error handling, and caller
obligations. If shared or low-level code relies on an undocumented or
untested contract, consider that an actionable issue even if the current
implementation happens not to fail in the obvious path.

Do a counterexample pass after you understand the intended behavior.
Construct small cases around boundary values, empty and partially
initialized state, overlapping operations, repeated calls, mixed old and
new paths, fallback paths, ownership/lifetime transitions, and
serialization or restoration boundaries. Report any counterexample that
would violate the apparent contract.

Compare the PR's stated purpose and the code's apparent intent against
direct test coverage. New low-level helpers, changed shared paths, and
new behavior boundaries should have direct tests or a clear reason they
do not. Do not treat broad integration tests or passing CI as sufficient
coverage for a new primitive unless they exercise the relevant edge
cases.

Before writing that there are no actionable items, explicitly reconsider
whether the PR includes any new APIs without documented contracts, new
helpers without direct tests, changed fallback paths, changed
serialization/persistence behavior, changed ownership/lifetime behavior,
or names/files whose placement obscures behavior. Promote these to
actionable items when they create a concrete maintenance or correctness
risk; otherwise explain why they are only suggestions or residual risk.

## Staging

When asked to stage review work for commit, stage only tracked files
that changed. Leave newly created review files untracked unless the
reviewer explicitly asks to stage new files too.

## Public hygiene

Reviews in this repository are public artifacts. Do not include private
machine paths, home-directory paths, local build-directory names, or
temporary-directory paths. Use neutral placeholders such as `$BUILD_DIR`,
`$SRC_DIR`, `$ROCM_PATH`, or `<device-path>` when an exact local path is
not needed to understand the result.

Do not identify people by personal names, local usernames, email
addresses, or GitHub handles. Use role-based wording such as "the
author", "the reviewer", or "a reviewer". Omit `Author` metadata fields
from review files. If a branch name or PR head ref contains a person's
handle, replace it with a neutral placeholder such as `<pr-head-ref>`.

Do not mention private workspace/session names or labels. Keep commands
and test notes reproducible without exposing which local workspace was
used.

## Testing

Testing supports the review; the number of tests run is not a measure of review
quality. Prioritize understanding the design, contracts, changed code, and
concrete downstream paths over accumulating broad test results.

Run new or changed tests that are directly relevant and reasonably quick. Do
not attempt an exhaustive local test run by default. If the relevant tests are
slow, select representative cases that exercise the changed contract and rely
on CI for broader coverage. Explain that choice in the review.

Summarize successful testing in one concise line. Name the relevant suites or
builds and give their aggregate result; omit exact commands, timings, and
per-test detail unless they materially affect the review or the reviewer asks
for them.

If a test fails or errors, add the detail needed to understand and reproduce
that result: the failing test or build, the relevant command and environment,
the error message, and whether the failure is a genuine bug in the PR or an
artifact of the local environment. Check CI status (`gh pr checks`) to compare.
If a test fails locally but passes in CI (or vice versa), investigate and
report the cause. Explain skipped tests only when the skips leave relevant
behavior untested.

If you were unable to run the tests, explain why.

### Test selection

Select additional tests from the changed files, changed contracts, and concrete
downstream call paths established during the review. Do not prioritize a
subsystem merely because it is an active project work area, appeared in recent
reviews, or is familiar to the reviewer.

Run a secondary subsystem's tests only when the diff touches shared behavior
that the subsystem demonstrably consumes, or when the reviewer explicitly asks
about that subsystem. Explain the dependency that makes those tests relevant.
Prefer focused tests for the affected path over a broad subsystem suite.

Avoid broad or exhaustive subsystem suites when a small number of focused tests
provide sufficient evidence, especially for slow integration, hardware,
emulation, or corpus tests. It is acceptable to omit slow tests that duplicate
green CI coverage. State what was omitted and why, without treating the omission
as an inherent review deficiency.

Stop testing once the important changed contracts and credible counterexamples
have adequate evidence. Spend the remaining review effort on code inspection,
API boundaries, failure modes, and maintainability rather than expanding the
test matrix without a concrete question.

Keep exploratory or follow-up tests separate from the PR's primary validation
in the written review. Do not present a fast but weakly related test suite as
evidence for the main change.

## Review structure

The first line of every review must be:

> This is a review from an agent with an automatic prompt from the reviewer

1. **Tests** — one concise line summarizing the relevant local test/build runs
   and their aggregate results, followed only by details needed to explain
   failures, errors, or material coverage gaps.
2. **Summary** — your own interpretation of what the PR does, based on
   reading the code. Note evidence-backed strengths as well as the overall
   assessment. Do not rely on or repeat the PR description, and do not preview
   every actionable item.
3. **Actionable items** — concrete issues worth addressing. Each item
   must include the file path, line number(s), what is wrong, and what
   to do about it. Write these so that an agent reading the review could act on
   them without needing further context. Use sentence-case headings and state
   each concern here only once.
4. **Suggestions** — items that would improve the PR but are less
   important. Same format: file path, line number(s), what to change.
5. **Commentary** — design observations, architectural notes, patterns
   worth discussing. These don't need file paths or specific fixes —
   they're for the author to consider.
