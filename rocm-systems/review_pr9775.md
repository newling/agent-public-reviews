This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9775](https://github.com/ROCm/rocm-systems/pull/9775)

**Revision reviewed:** published head `8ef11c8e35b`, one commit based directly
on `origin/develop@4d5ab9bfbff`.

**Review mode:** comment-aware final review. This pass independently reviewed
the rebased diff and then checked every current review thread and PR discussion
item for remaining technical work.

**Public status:** the upstream repository, source fork, PR, and source branch
are public. The PR is open and non-draft.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: all 320 required steps passed in 101.01s real, 723.19s user, and
35.77s sys. The final base refresh after this build added only hipfile
documentation and left the complete rocJITsu tree unchanged; the focused
tests below were rerun after that refresh on the published head.

**Complete gfx1250 tensor-DMA selection:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Gfx1250ExecutionTest.TensorDma*'
```

Result: 13/13 passed, 0 failed, 0 skipped, and 0 errored in 2.63s real. This
includes the nonzero-process page-table regression for both tensor load and
tensor store, dense and gather forms, padding, iteration, descriptor count,
and barrier behavior.

**Block-memory boundary coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='GpuMemoryTest.BlockAccessSpansSparseFallbackPages:GpuMemoryTest.BlockAccessSpansMappedPages:GpuMemoryTest.BlockAccessRechecksTranslationAfterSparseFallbackPage'
```

Result: 3/3 passed, 0 failed, 0 skipped, and 0 errored in 0.02s real. These
tests exercise the existing `GpuMemory::read_block`/`write_block` behavior
that the new wave-scoped element copies rely on, including mapped and sparse
page boundaries.

**Formatting and diff hygiene:**

```bash
time -p bash -lc \
  'git diff --name-only origin/develop...HEAD -z |
   xargs -0 .venv/bin/pre-commit run --files'
git diff --check origin/develop...HEAD
```

Result: every applicable hook passed in 0.26s real, and `git diff --check`
passed. The source checkout has no tracked modifications.

On the preceding public head, rocJITsu formatting, release, Clang ASan/UBSan,
GCC ASan/UBSan, and TSan jobs passed. Two TheRock package jobs failed in their
`Fetch sources` step before patching, configuring, or building this PR; the
gfx125X package build passed. Fresh CI is queued for the published rebased
head.

## Summary

The bug is an address-space mismatch in the functional tensor-DMA path.
Tensor-DMA instructions used the compute unit's raw `GpuMemory` pointer and
therefore inherited VMID zero, even when the executing wave belonged to a
nonzero process. In local passthrough mode, a user-space-looking GPU virtual
address could consequently be treated as a host pointer instead of being
translated through the issuing process's page table.

The change establishes a wave-owned boundary for this direct backing-memory
path:

- `Wavefront` exposes block reads and writes that always pass its process ID;
- tensor DMA uses those methods for global load and store elements;
- the raw memory accessor is removed from the instruction-facing compute-unit
  view;
- each 1-, 2-, 4-, or 8-byte tensor element uses one block operation rather
  than taking translation locks once per byte; and
- the `GpuMemory` contract now distinguishes intentional VMID-zero host,
  driver, and test callers from wave-issued access.

The regression proves that VMID zero and the dispatched process resolve the
same GPU virtual address to different storage, then verifies that tensor load
and store both select the wave's process page table.

The rebase conflict was purely structural: upstream split the former
monolithic gfx1250 simulator test file by theme. The regression now resides in
the dedicated tensor-DMA test file; its behavior is unchanged.

I found no actionable correctness, ownership, address-translation,
page-boundary, generated-output, or test issue in the final rebased candidate.

## Actionable items

None.

## Suggestions

None.

## Commentary

### Existing review feedback

All four formal review threads are marked resolved.

The requested wave-scoped accessor is present, binds the process ID
structurally, removes the instruction-facing raw-memory escape, and preserves
VMID zero for non-wave callers. The requested element-sized
`read_block`/`write_block` conversion is also present. The focused regression
was retained and, after the upstream test split, now lives in the dedicated
tensor-DMA file.

One resolved thread identifies a real cache-visibility limitation for tensor
stores that write backing memory directly while an L2 line may remain stale.
That behavior predates this VMID correction, and the thread explicitly accepts
a focused follow-up. It is not fixed by this PR and remains the only known
technical follow-up.

A later PR discussion comment reported that an intermediate revision did not
build. It predates the current public head. The final rebased candidate builds
cleanly with the command and result above.

### Commit structure

The published branch is one hand-maintained commit directly atop
`origin/develop`.
It changes no generated files, so no generated-only top commit is required.
