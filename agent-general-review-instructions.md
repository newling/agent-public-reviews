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

## Testing

Run all new tests in the PR locally. In the review, report:

- The exact command used to run the tests.
- How long the tests took.
- How many tests passed, failed, skipped, or errored.
- For any failures: the error message, and whether the failure is a
  genuine bug in the PR or an artifact of the local environment. Check
  CI status (`gh pr checks`) to compare. If a test fails locally but
  passes in CI (or vice versa), investigate why — import order
  dependencies, missing environment setup, version differences, etc.
  Report what you find.

If you were unable to run the tests, explain why.

## Review structure

The first line of every review must be:

> This is a review from an agent with an automatic prompt from the reviewer

1. **Tests** — results from running the PR's tests locally: command,
   timing, pass/fail counts, and analysis of any failures.
2. **Summary** — your own interpretation of what the PR does, based on
   reading the code. Do not rely on or repeat the PR description.
3. **Actionable items** — concrete issues worth addressing. Each item
   must include the file path, line number(s), what is wrong, and what
   to do about it. Write these so that an agent reading the review
   could act on them without needing further context.
4. **Suggestions** — items that would improve the PR but are less
   important. Same format: file path, line number(s), what to change.
5. **Commentary** — design observations, architectural notes, patterns
   worth discussing. These don't need file paths or specific fixes —
   they're for the author to consider.
