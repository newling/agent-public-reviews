This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#9470](https://github.com/ROCm/rocm-systems/pull/9470)

**Revision reviewed:** local revival candidate `e0970cc1fa`, one commit based directly on `origin/develop@1c1419a943`.

**Review mode:** comment-aware follow-up. I independently rechecked the current one-commit diff, then evaluated the historical review comments and the prior local review suggestion against the current `develop` contracts.

## Tests

The focused Release/Ninja build passed for `rocjitsu_tests`, `rocjitsu_plugin_race_so`, and the gfx950 HIP race binary; 104/104 race-detector and scalar plugin-path tests and 39/39 gfx950 race integration tests passed, as did changed-file pre-commit and `git diff --check`.

Generated gfx950 code inspection confirmed that both safe kernels wait between the two relevant writes, while the `_race` kernels retain the intended adjacent load/write or load/load sequence before their cleanup wait.

## Summary

The follow-up preserves the narrow SGPR/TTMP WAW policy while addressing the remaining review coverage. The shared scalar-access helper now has direct permanent evidence for both read and write deduplication, the TTMP write callback is covered through the actual race-plugin path, and each new HIP behavior has a safe/racy pair expressed through the current structured expectation helpers.

The historical ownership, physical-range, generated-source, plugin-ABI, and split-wait concerns no longer belong to this diff. They were resolved or superseded by the wave-owned register-access and typed wait-counter foundation already merged into `develop`. The revival consumes those APIs without changing them.

I found no remaining actionable correctness, test, documentation, or maintainability issue in the final candidate.

## Actionable items

None.

## Suggestions

None.

## Commentary

### Historical review disposition

- Typed wave ownership and complete-range validation are supplied by merged #10030; the obsolete physical-index callback and generated-code changes were dropped.
- The old plugin-ABI concern is absent because this revision adds no virtual callback or ABI change; it consumes the callback already in `develop`.
- Typed `KMCNT`, `VSCNT`, and other split-wait routing is supplied by the merged wait-counter model rather than reimplemented here.
- The old partial-`LGKMCNT` scan and invalid-destination routing comments apply to superseded implementations and are absent from this focused policy diff.
- Positive HIP cases use the `_race` suffix, and both load-to-move and load-to-load now have waited unsuffixed counterparts.
- The generator mismatch, adjacent-wave storage corruption, straddling-write behavior, and operand-resolution issues were all part of the superseded foundation and are not reintroduced.

### Reopening hygiene

The original PR description still describes the obsolete seven-commit stack. Replace it with the prepared policy-only description before reopening, and treat CI from the historical head as stale. The current candidate should receive a fresh CI run after publication.
