> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13675](https://github.com/ROCm/rocm-libraries/pull/13675)

Reviewed head: `7356d47071604b79ec8d29f31762b7fa261510bd`. Merge base: `29e5b0a059e74e6b830f5572916fe17eeeff1682`.

Suggestion branch: [`review/pr13675-suggestions`](https://github.com/newling/rocm-libraries/tree/review/pr13675-suggestions), based on that exact head ([diff against the reviewed head](https://github.com/newling/rocm-libraries/compare/7356d47071604b79ec8d29f31762b7fa261510bd...22dab2211c56c5ecdca85d0830e6d128b88d784b)). Commit [`22dab2211c5`](https://github.com/newling/rocm-libraries/commit/22dab2211c56c5ecdca85d0830e6d128b88d784b) implements item 1 with tests only.

## Tests

Focused assembly/linker tests pass on the submitted PR and suggestion branch; architecture-routing tests, applicable pre-commit checks, and lint of the added tests also pass. Real ROCm 7.1 assembly/link/bundle checks produced 24 byte-identical comparisons against the merge base across gfx942, gfx950, and gfx1100, covering both compression settings and direct arguments versus response files.

All current required checks pass. The first [Multi-Arch CI attempt](https://github.com/ROCm/rocm-libraries/actions/runs/41609250298/attempts/1) failed in a Windows rocBLAS shard; its hipBLASLt and TensileLite jobs passed. That failing job's archived log returns HTTP 404, so its underlying cause was not established. The second attempt passed. Full device-library builds and GPU execution were left to CI; the published build-time measurements were not independently repeated.

## Summary

The assembly builder collects each code object's link-and-bundle work before starting a thread pool. It divides the configured CPU allowance among the simultaneous linkers and submits groups with more input objects first. Collecting the returned paths before reordering the work preserves the caller's output order. Each worker links before bundling, and the existing sorted object lists preserve deterministic linker input.

The shared linker and bundler objects construct arguments locally, and response files are named after their outputs. Those choices support concurrent subprocess use. I found no production correctness defect in the supported call paths. Unit tests are the appropriate level for the scheduling and exception behavior; the existing assembly, linker-argument, and architecture-routing tests are the relevant adjacent coverage. No feature flag or broader kernel-generation test matrix is needed for this build-only change.

## Actionable items

### 1. Test overlap and worker failure propagation through the pool

`projects/hipblaslt/tensilelite/tensilelite/Tests/unit/test_assembly_parallel_link.py`, submitted lines 53–135; behavior in `projects/hipblaslt/tensilelite/tensilelite/Toolchain/Assembly.py`, lines 184–186. Implemented in [`22dab2211c5`](https://github.com/newling/rocm-libraries/commit/22dab2211c56c5ecdca85d0830e6d128b88d784b).

The new tests check the per-link thread argument, submission order, and successful link/bundle calls, but they never require two jobs to overlap or a worker exception to reach `buildAssemblyCodeObjectFiles`' caller. All eight pass when the executor is forced to one worker. They also all pass when jobs are submitted without retrieving their results. The latter change would let the function report output paths even after a linker or bundler failed.

Add a test that holds two links at a barrier until both have started, and parameterized tests that fail the second code object's link or bundle and require the same exception at the caller. The commit adds these three cases. They pass with the submitted implementation, fail with the corresponding deliberate regressions, and run in the existing unit-test lanes. This is a gap in regression coverage, not a claim that the current implementation swallows exceptions or executes serially.

## Suggestions

None beyond item 1.

## Commentary

The largest-first scheduling rule estimates work by object count rather than byte size. That is a reasonable inexpensive heuristic here; it does not affect output contents or ordering. The single-code-object benchmark path still uses one worker and gives that link the configured CPU allowance.

All proposed changes are implemented on `review/pr13675-suggestions` in the single test commit above; no product-code fix is omitted.

## Appendix: reproduce the test-coverage counterexamples

With TensileLite and its test dependencies importable, save this as `probe_executor.py` outside the source tree. It substitutes an executor in memory and leaves production files unchanged:

```python
from concurrent.futures import ThreadPoolExecutor
import sys

import pytest
import tensilelite.Toolchain.Assembly as Assembly


class SerialExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers):
        super().__init__(max_workers=1)


class UnobservedExecutor(ThreadPoolExecutor):
    def map(self, function, *iterables, **kwargs):
        futures = [self.submit(function, *args) for args in zip(*iterables)]
        return iter([None] * len(futures))


Assembly.ThreadPoolExecutor = {
    "serial": SerialExecutor,
    "unobserved": UnobservedExecutor,
}[sys.argv[1]]
raise SystemExit(pytest.main(sys.argv[2:]))
```

Run from the TensileLite project directory, with `$PROBE` naming that script:

```bash
python "$PROBE" serial -q tensilelite/Tests/unit/test_assembly_parallel_link.py \
  -k 'not independent_links_overlap and not worker_errors'
python "$PROBE" unobserved -q tensilelite/Tests/unit/test_assembly_parallel_link.py \
  -k 'not independent_links_overlap and not worker_errors'
```

Both commands pass all eight submitted tests. On the suggestion branch, omit `-k` to include the added tests: `serial` fails the overlap case with `BrokenBarrierError`, and `unobserved` fails both error cases with `DID NOT RAISE RuntimeError`. Without either executor substitution, all eleven tests in the file pass.
