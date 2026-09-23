> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#10925](https://github.com/ROCm/rocm-systems/pull/10925)

**Revision reviewed:** rebased candidate `632d03decb`, six commits on `origin/develop` at `cf9aa6d00b`.

## Tests

The release `rocjitsu_tests` target and both affected HIP race-test binaries built successfully; all 259 focused execution-plugin, hook-ordering, instruction-metadata, memory-pipeline, and race-detector tests passed, as did all 72 gfx950/gfx1151 race integration cases and 394 focused ISA-profile/codegen tests. Full ten-ISA regeneration left no tracked diff, changed-file pre-commit hooks passed, and `git diff --check` passed.

## Summary

This PR publishes target-specific VMCNT and LGKMCNT capacities and uses them to model issue-time implicit backpressure before a memory instruction reads its operands. When a new issue would exceed a finite counter, the detector applies the same conservative per-domain completion reasoning used for an explicit partial wait. The implementation accounts for multi-token scalar fetches, keeps generic FLAT's counter obligations independent, and preserves conservative behavior when mixed or unordered traffic prevents identifying a particular completion.

The six-commit capacity layer replayed cleanly onto `develop`; `git range-diff` reports every patch as identical to the preserved pre-rebase series. I found no correctness issue within the explicitly limited memory-pipeline scope.

## Actionable items

None.

## Suggestions

None.

## Commentary

I rechecked all 23 existing review threads. The earlier documentation, naming, default-value, architecture-source, generic-FLAT, multi-token scalar-load, test-layout, and mixed-class integration-test requests are addressed in the current stack. In particular, the two threads still shown as unresolved on GitHub are now covered by the merged generic-FLAT foundation and by the gfx950/gfx1151 mixed scalar/LDS capacity tests in this PR.

The comments about non-memory counter producers remain relevant as an explicit scope boundary. Timestamp queries are not represented by decoded memory-issue metadata, and messages receive only an issue-time LGKMCNT pressure update rather than persistent event/result tracking. The PR description should continue to state that complete accounting for those producers and GFX12+ capacity behavior is out of scope.

The earlier hot-path performance question is also a residual consideration because capacity checks scan the wave's outstanding candidate events. The previously recorded fixed-workload A/B result found no consistent regression (about a one-percent median difference, within run-to-run noise), and the scan is bounded by small hardware capacities for ordinary ordered streams; highly ambiguous mixed streams remain the worst case.
