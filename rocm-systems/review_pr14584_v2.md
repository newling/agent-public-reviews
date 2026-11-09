This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#14584](https://github.com/ROCm/rocm-systems/pull/14584)

Reviewed head: [`cb566b8e9e02`](https://github.com/ROCm/rocm-systems/commit/cb566b8e9e02c2b68e5343a7f310eb6e4a903de4), against base [`f3d84e8c4ce7`](https://github.com/ROCm/rocm-systems/commit/f3d84e8c4ce7cbb7feaafec2847964909790805d). Independent review of simulator termination and async causality, command-processor fault cleanup, concurrent-dispatch oracles and CLI, and multiplexer/AFL integration. The target PR's discussion was not consulted. This report covers the current revision; the [earlier published review](https://github.com/newling/agent-public-reviews/blob/main/rocm-systems/review_pr14584.md) remains unchanged.

Suggestion branch: [review/pr14584-suggestions-20261109](https://github.com/newling/rocm-systems/tree/review/pr14584-suggestions-20261109), based on the reviewed head ([combined diff](https://github.com/newling/rocm-systems/compare/cb566b8e9e02c2b68e5343a7f310eb6e4a903de4...1bbd70c2fc7e82ae52535c826cec1c8cbf1be235)). Optional changes are [`55cd6c7e9dd`](https://github.com/newling/rocm-systems/commit/55cd6c7e9dd7b0d5110b3b91e6d78a06fd040334) (types and includes) and [`1bbd70c2fc7`](https://github.com/newling/rocm-systems/commit/1bbd70c2fc7e82ae52535c826cec1c8cbf1be235) (fault-test consolidation). Both commit messages link back to this review.

## Tests

The submitted head built with Clang 23 in Release mode and passed 143 focused CTests, eight campaign-runner Python tests, and deterministic random seeds 0–999. The random campaign executed 2,668 scheduling modes, including 247 inputs under the exact-result oracle. The suggestion branch rebuilt successfully and passed the affected tests and pre-commit hooks.

Removing the command processor's added doorbell wake makes both the one-packet and blocked-successor fault regressions fail on a stranded primary. Removing the barrier's async drain makes `TickLimitDoesNotDelayBufferedAsyncWork` fail on callback/release timestamps and completion cause. These mutations were reverted. Representative gfx942, gfx1100 and gfx1250 atomic/wait suffixes also matched independent `llvm-mc` output.

The current hosted rocjitsu Release, ASan/UBSan, TSan, GCC/UBSan and fuzz jobs passed. This review did not run a local sanitizer/AFL campaign or hardware tests. WSL and Windows rocFFT gates were red and were not diagnosed here.

## Summary

The fuzzer exercises real queue admission, workgroup retirement and completion publication across both engine partitioning and shared dispatch workers. Keeping an exact memory oracle for a known atomic program, while restricting arbitrary kernels to lifecycle and scheduling checks, gives the two input classes useful and distinct purposes. The address-space boundary protects the queue and completion signals from fuzzed stores.

The simulator changes give finite runs a structured distinction between reaching the horizon and draining with a primary still active. The async-drain and fault-wake regressions distinguish the intended behavior when their fixes are removed. I found no runtime correctness defect in the reviewed revision.

## Actionable items

### Add a tracking reference to the PR description

Location: PR description; [the description policy](https://github.com/ROCm/rocm-systems/blob/cb566b8e9e02c2b68e5343a7f310eb6e4a903de4/tools/systems_pr_bot/policy.yml#L53).

The current two-paragraph description has no tracking issue or JIRA reference. Running the checked-in `ensure_pr_description()` with the current policy and description reports “no valid JIRA/ISSUE/closing-keyword reference found”; `therock-pr-bot` is also failing. Add the actual tracking issue or ticket, using an `ISSUE ID` or `JIRA ID` line. No description edit was made because the appropriate reference is not supplied by this PR.

## Suggestions

### Make the harness's borrowed types and direct dependencies explicit

Locations: [concurrent_dispatch_fuzz_core.cpp:502](https://github.com/ROCm/rocm-systems/blob/cb566b8e9e02c2b68e5343a7f310eb6e4a903de4/emulation/rocjitsu/fuzz/concurrent_dispatch/concurrent_dispatch_fuzz_core.cpp#L502), [concurrent_dispatch_fuzz_main.cpp:37](https://github.com/ROCm/rocm-systems/blob/cb566b8e9e02c2b68e5343a7f310eb6e4a903de4/emulation/rocjitsu/fuzz/concurrent_dispatch/concurrent_dispatch_fuzz_main.cpp#L37), and the new test helpers.

The [project style guide](https://github.com/ROCm/rocm-systems/blob/cb566b8e9e02c2b68e5343a7f310eb6e4a903de4/emulation/rocjitsu/docs/style.md) asks for explicit types when a function call hides the result type. Spell out the borrowed SoC, memory, cache, observer and command-processor pointers, the iterator, and `std::from_chars_result`. Include the declaring headers for the operand constant, result type and standard-library facilities used by the affected code. This is optional readability and dependency cleanup; the submitted build succeeds. Implemented in [`55cd6c7e9dd`](https://github.com/newling/rocm-systems/commit/55cd6c7e9dd7b0d5110b3b91e6d78a06fd040334).

### Combine the duplicate fault-publication tests

Location: [concurrent_dispatch_fuzz_test.cpp:417](https://github.com/ROCm/rocm-systems/blob/cb566b8e9e02c2b68e5343a7f310eb6e4a903de4/emulation/rocjitsu/tests/fuzz/concurrent_dispatch/concurrent_dispatch_fuzz_test.cpp#L417) and [line 464](https://github.com/ROCm/rocm-systems/blob/cb566b8e9e02c2b68e5343a7f310eb6e4a903de4/emulation/rocjitsu/tests/fuzz/concurrent_dispatch/concurrent_dispatch_fuzz_test.cpp#L464).

`TerminalFaultReleasesPrimaryAcrossWorkerModes` and `TerminallyFaultedPacketDoesNotPublishCompletion` replay the same unmapped store with overlapping assertions. Combine their expectations and explicitly check `published_completions == 0`, so the publication claim is visible in the retained test. The harness already validates the underlying invariant; this is a test simplification. Implemented in [`1bbd70c2fc7`](https://github.com/newling/rocm-systems/commit/1bbd70c2fc7e82ae52535c826cec1c8cbf1be235), on top of the type/include cleanup.

## Commentary

The documented oracle limits remain relevant when interpreting findings: acquire/release flags are exercised, but the canonical atomic followed by a harness flush is not an independent fence-semantics test. Arbitrary kernels can legitimately change fault behavior with scheduling and therefore still require replay and triage. Neither a passing random campaign nor a retained fuzz input alone establishes general correctness or a distinct simulator defect.

The suggestion branch contains the two optional commits linked above. The only required item identified above is the description's tracking reference; no runtime fix is proposed. Validation limits are recorded under Tests.
