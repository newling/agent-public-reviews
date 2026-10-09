This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#13203](https://github.com/ROCm/rocm-systems/pull/13203)

**Reviewed head:** [`ee5be03e23517af3ecba5db88f8a36843d463364`](https://github.com/ROCm/rocm-systems/commit/ee5be03e23517af3ecba5db88f8a36843d463364).

**Review branch:** [review/pr13203-suggestions](https://github.com/newling/rocm-systems/tree/review/pr13203-suggestions), based on the exact reviewed head.

**Publication update (2026-10-09):** The PR has advanced to [`d707e97a62d`](https://github.com/ROCm/rocm-systems/commit/d707e97a62db1f71b9bf85798e7354f5c5af1e4c), which already includes the navigation fix described in item 1. That item is addressed in the current PR. The review and runtime validation below cover the original head above; the newer runtime changes have not been re-reviewed here.

| Commit | Review item |
| --- | --- |
| [`55e69c815c7`](https://github.com/newling/rocm-systems/commit/55e69c815c706da40a6da5aa04ff3ce9809d0405) | Item 1: register the new ISA diagnostics guide in the handbook navigation. |

## Tests

The submitted head passes the Clang 23/Ninja Release build and the focused `IsaDiagnosticsTest` suite; full ISA/DBT regeneration reproduces the checked-in sources exactly. The suggestion passes the strict handbook build and changed-file pre-commit checks.

The submitted head's strict handbook build fails locally and in [the handbook CI job](https://github.com/ROCm/rocm-systems/actions/runs/37958117645/job/113913725652); the cause and reproduction are in item 1. The suggestion changes only documentation navigation, so the runtime results also apply to the review branch.

The diagnostic suite exercises scalar offsets and alignment, MFMA broadcast boundaries and format exceptions, VOPD ports and scalar budgets, IU modifiers, effective EXEC on transpose loads, permlane widths, suppression accounting, and asynchronous MFMA reporting at the issuing PC. Architecture-inapplicable parameter combinations skip as expected. Supplemental VOPD wave-mask generator checks also pass.

The hosted rocjitsu Release, ASan/UBSan, TSan, and GCC UBSan jobs pass. The separate [gfx94X sanity job](https://github.com/ROCm/rocm-systems/actions/runs/37958289332/job/113933136947) fails with missing runtime artifacts, including `offload-arch` and `rocm_agent_enumerator`, and failures to run `rocminfo`; that result does not establish a regression in these diagnostics. Full corpus, separate Mirage integration, hardware comparisons, and local sanitizer builds were omitted; local validation focuses on the changed execution and decoding contracts.

## Summary

The change separates restrictions determined from an instruction's encoding from those requiring runtime operands. Decoders cache the former as flags, and the CU reports them on the issuing thread, including the asynchronous MMA path. Address and permutation checks reuse the values already read for execution. The shared reporting path adds wave and PC context and limits warning output per CU without rejecting instructions.

The architecture and operand-role qualification is a useful part of the design. In particular, CDNA5 ordinary scalar loads retain their negative-offset exception, MFMA format selectors are excluded from broadcast checks, and GFX12 VOPD sharing is distinguished from older port restrictions. The tests include legal neighbors of the diagnosed cases. I found no additional actionable runtime correctness issue within the documented coverage.

## Actionable items

### 1. Register the ISA diagnostics page in the handbook navigation

Locations: the new [`emulation/rocjitsu/docs/isa-diagnostics.md:1`](https://github.com/ROCm/rocm-systems/blob/ee5be03e23517af3ecba5db88f8a36843d463364/emulation/rocjitsu/docs/isa-diagnostics.md#L1) and the user-guide entries in [`emulation/rocjitsu/website/handbook/mkdocs.yml:83`](https://github.com/ROCm/rocm-systems/blob/ee5be03e23517af3ecba5db88f8a36843d463364/emulation/rocjitsu/website/handbook/mkdocs.yml#L83).

The new page is linked from configuration documentation but is absent from MkDocs' explicit `nav`. The handbook treats that omission as a warning, which fails its strict build and prevents publication. The existing guide-creation instructions require registering each regular guide.

From the repository root, with the pinned handbook dependencies installed, this reproduces the submitted failure:

```sh
ROCJITSU_DOCS_OFFLINE=1 python -m mkdocs build --strict \
  -f emulation/rocjitsu/website/handbook/mkdocs.yml \
  --site-dir "$BUILD_DIR/handbook"
```

The diagnostic is:

```text
WARNING - The following pages exist in the docs directory, but are not included in the "nav" configuration:
  - isa-diagnostics.md
Aborted with 1 warnings in strict mode!
```

Add `- ISA diagnostics: isa-diagnostics.md` beside the memory-wait diagnostics entry in the user guide. **Implemented in [`55e69c815c7`](https://github.com/newling/rocm-systems/commit/55e69c815c706da40a6da5aa04ff3ce9809d0405); also present in the current PR head.** The same strict build passes with this one-line change, and changed-file hooks pass. The existing strict build directly checks the missing registration; no additional test is needed.

## Suggestions

None.

## Commentary

Keeping decoded diagnostic flags independent of memory-wait configuration makes the new behavior available through the shared CU execution path. The runtime conditions remain in the relevant address or execution helpers, where operand values are already available. The new reporting API documents its issuing-thread obligation, and the asynchronous MFMA test exercises that boundary.

The deliberately limited coverage is clear in the guide. Allocation fallbacks and unresolved cross-operation dependency rules should continue to require ISA-specific evidence before becoming unconditional warnings. This review does not propose broadening that policy.

Review work is published on [review/pr13203-suggestions](https://github.com/newling/rocm-systems/tree/review/pr13203-suggestions), with [`55e69c815c7`](https://github.com/newling/rocm-systems/commit/55e69c815c706da40a6da5aa04ff3ce9809d0405) implementing item 1. Focused runtime validation and regeneration pass on the submitted code, and handbook validation passes with the suggestion. No finding implementation was omitted. The original-head suggestion branch is preserved for inspection; its navigation change is already present in the updated PR.
