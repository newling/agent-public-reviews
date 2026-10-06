This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13022](https://github.com/ROCm/rocm-libraries/pull/13022)

**Reviewed head:** [`97e1481b451214c125b22a7b5b9274d1d3cb0f7f`](https://github.com/ROCm/rocm-libraries/commit/97e1481b451214c125b22a7b5b9274d1d3cb0f7f) (2026-10-06), relative to #13021. Public repository and head; existing reviews/comments were not consulted.

**Published suggestion branch:** [`review/pr13022-suggestions-20261006`](https://github.com/newling/rocm-libraries/tree/review/pr13022-suggestions-20261006), based on that exact head, with no additional commits. The Stream-K guard relocation is supplied on #13005's suggestion branch as [`6503895955f`](https://github.com/newling/rocm-libraries/commit/6503895955f74e3780b395c4ebea5b89a6601f2b).

## Tests

Built the submitted checker, compiled the matmul header in benchmark and GOOGLE_TEST modes, and generated the new edge-case records with the actual YAML generator. The numerical checker is unchanged from #13021's locally passing 50-test suite. Whitespace checks pass.

Large GEMMs and the intermittent gfx950 failure were not replayed locally. Current Math CI and the latest applicable replacement multi-architecture/ASAN checks pass, while coverage remains red. Those passes include the new quarantine.

## Summary

The cases cover short K, ragged tiles, strided batches, output-type-driven solution selection and mixed FP8 formats, with repeated launches. The Stream-K check verifies that at least one returned solution belongs to the intended family. This makes a no-coverage run an explicit skip.

The previously observed f32 Stream-K failure now has a separate tracker, ROCM-32277, and a time-boxed quarantine. The description reports independent benchmark reproduction in 4/80 launches as well as 4/30 test runs. That is stronger evidence of a kernel issue than a passing retry, although it was not independently reproduced in this review.

## Actionable items

No new source finding beyond moving the Stream-K guard into #13005, where `requires_streamk` first appears. The suggested relocation already contains this exact implementation, so remove the duplicate when restacking.

## Suggestions

At `projects/hipblaslt/clients/tests/data/known_bugs.yaml:70`, the ROCM-32277 entry for `matmul_fast_check_streamk_batches` suppresses every f32 solution at both M=1031 and M=4099 on gfx950. The observed CI failure and the comment describe the partial tile at M=4099. Confirm the intended quarantine scope from the reproducer; if M=1031 is unaffected, add that shape restriction so its coverage stays active. No restriction was guessed locally because the full reproduction matrix is not available.

## Commentary

These are client/kernel integration tests, so YAML generation and existing checker self-tests establish only the harness side. Hardware runs establish the kernel configurations. The tracked quarantine is a way to land useful tests while the separate kernel fix proceeds; it is not a fix for ROCM-32277. Keep the removal deadline and independent benchmark reproducer attached to that work.

The published branch has no extra commits; the relocation commit is linked above.
