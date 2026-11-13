This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15743](https://github.com/ROCm/rocm-libraries/pull/15743)

Reviewed head: `7a000e7714a1b19cea60c8c6d1375c92eecd3f1c`. Target-base snapshot: `f65195cf63c927df0025b35342ce99f3e9e70b1f`; merge base: `84c6e7ced46a654eff0a668d9aecf568bb42de1d`.

Independent review of the swizzle transformation's wave-size assumptions, cached architecture-capability filtering in hipBLASLt, unknown-architecture and empty-result behavior, and the regressions. Suggestion branch: [review/pr15743-current-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15743-current-suggestions), based on the reviewed head, with no additional commits.

## Tests

The rocRoller implementation and tests are unchanged from the earlier submitted head `3181c9a85314d8681a85b0c82bcb85ebbcbd37c6`, which was built with Clang 23.1.0. `SwizzleScale*` passes both test cases, and the broader `[kernel-graph]` filter passes all 169 cases. The full rocRoller C/C++ tree passes clang-format 13.0.0 checking. Removing only the new wave64 assertion makes the new regression terminate with SIGFPE separately on the gfx1201 and gfx1250rev1 target configurations. Restoring the assertion and rebuilding makes all three target checks pass, including the gfx950 positive control. These are host-side graph transformations, not device execution.

The available local hipBLASLt client configuration disables rocRoller; it does not validate the changed interop source or the new capability-filter API regression. A complete local hipBLASLt build with rocRoller enabled and a wave32 API run remain unverified. The [earlier head's public gfx950 hipBLASLt job](https://github.com/ROCm/rocm-libraries/actions/runs/43464276300/job/132049772391) passes; CI for the reviewed head is still in progress at the review snapshot. On the earlier head, the separate rocRoller analysis failure occurs before analysis because the Dockerfile path is `null`; its precheckin failure is an illegal instruction in `GPU_KernelIndexTest`, outside the changed transformation. Those failures do not demonstrate a defect in this guard, and they do not count as completed validation.

## Summary

The swizzle distributes a tile across four 16-lane groups. On wave32, its integer per-wave calculations can produce zero, leading to division by zero during graph transformation. Checking wave size before those calculations turns that process-level signal into the existing `FatalError` mechanism. The regression exercises the transformation rather than merely matching an error string, and its wave64 control verifies that supported graphs still acquire exchanges.

The hipBLASLt capability filter complements the transformation guard: it avoids candidate generation for block-scaled GEMMs when the handle's device lacks block-scaling support. It caches the first lookup per handle, including a negative result, and treats an architecture lookup exception as unavailable support. Unscaled candidates keep their existing path. With no supported candidates, the function retains its existing successful empty-result behavior and reports zero algorithms. The API regression covers both a known device without block scaling and an unknown architecture. I found no production defect in these changes.

## Actionable items

None.

## Suggestions

None.

Handoff: [review/pr15743-current-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15743-current-suggestions) remains at the reviewed head; there are no suggestion commits. Local validation establishes the unchanged graph-transform guard. It does not establish end-to-end execution of hipBLASLt's new capability filter on a wave32 device.
