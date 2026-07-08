This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#6962
**Commit reviewed:** `148e935736` (`fix(rocjitsu): address CPU dispatch review`)

**PR metadata:** public PR against public `ROCm/rocm-systems`, base `develop`, head
`ROCm:<pr-head-ref>`.

**Focused build command:**

```bash
time -p cmake --build $BUILD_DIR \
  --parallel 8 \
  --target rocjitsu_tests rocjitsu_bin librocjitsu.so
```

Result: build passed in 118.70s real time. This rebuilt the rocjitsu test
binary, CLI launcher, and shared interposer library after CMake regenerated the
build files.

**Daemon / ROCm Collective Communications Library (RCCL) test target build:**

```bash
time -p cmake --build $BUILD_DIR \
  --parallel 8 \
  --target daemon_test hip_rccl_test_target
```

Result: build passed in 4.20s real time.

**Focused PR test plan, L2/GpuMemory:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='L2CacheThreadingTest.*:GpuMemoryTest.BlockAccessHandlesPageBoundaries'
```

Result: 5/5 passed, 0 failed, 0 skipped, 0 errored. Real time: 0.04s.

**Focused PR test plan, multithreading/partition/config:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='*MultiThreaded*:*Partition*:*Config*'
```

Result: 30/30 passed, 0 failed, 0 skipped, 0 errored. Real time: 3.17s.

**Dispatch thread-count output invariance regression:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='VectorAddStressTest.CpuDispatchThreadsPreserveOutputBytes'
```

Result: 1/1 passed, 0 failed, 0 skipped, 0 errored. Real time: 0.81s.

**RCCL daemon regression coverage:**

```bash
time -p ctest --test-dir $BUILD_DIR \
  -L rccl --output-on-failure -j1
```

Result after rebuilding `daemon_test` and `hip_rccl_test_target`: 5/5 passed,
0 failed, 0 skipped, 0 errored. Real time: 76.55s.

One local incremental-build trap: running the RCCL label before rebuilding
`daemon_test` failed immediately because the stale test binary still referenced
the old two-GPU config filename. After rebuilding the daemon/RCCL targets, the
CTest entries used the renamed `gfx950` config and all five collectives passed.
I do not classify the first failure as a PR bug.

**Whitespace check:**

```bash
git diff --check origin/develop...HEAD
```

Result: passed with no whitespace errors.

**CI status at review time:** GitHub checks reported `test (release)`,
`test (asan-ubsan)`, `test (asan-ubsan-gcc)`, `pre-commit`,
`therock-pr-bot`, TheRock summary, and package builds passing. Several
hardware-specific jobs were skipped.

## Summary

This PR adds host-side parallel execution for rocjitsu functional-mode dispatch
processing. The command processor (CP) fetches packets and places workgroups,
then temporarily drops the queue lock and asks each Shader Processor Input
(SPI) to run one functional quantum on its active compute units (CUs) through an
SPI-owned CPU worker pool. Completion draining, cache maintenance, and signal
firing remain on the CP path after the worker fan-out rejoins.

The PR also makes the shared memory/cache paths more suitable for this
parallelism: level-2 cache (L2) public operations now take per-set locks,
`SparseMemory` uses striped page maps and block read/write helpers,
`GpuMemory` adds thread-local virtual memory ID (VMID) translation and memory
type (MTYPE) lookup caches, and completion flushing tracks unique L2s rather
than redundantly flushing through every CU.

## Actionable items

None. I did not find a concrete correctness issue beyond the questions already
raised in inline review discussion.

## Suggestions

### 1. Document the 1024 to 16384 functional quantum change

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/compute_unit.h:73`

The default `kFunctionalQuantum` increases from 1024 to 16384, but the code and
docs do not explain why that number is the new default. Since
`functional_quantum` controls how often CU execution yields back to the
dispatch/completion loop, this is not just a cosmetic constant change. A short
comment would make the scheduling tradeoff reviewable.

Please add a comment at the constant, for example:

```cpp
// Chosen to amortize functional-mode dispatch-pool fork/join overhead while
// still yielding periodically for completion draining and late-packet rescans.
```

If 16384 was chosen empirically, include the workload or measurement that led to
it. If `functional_quantum=0` is still a supported "run until inactive" mode,
please also document when a user should choose 0 or a smaller nonzero value.

### 2. Consider a future cache-bypass mode for race-detection/performance use cases

There is a useful adjacent idea from prior local experiments: when race
detection or functional correctness is the goal and cache hierarchy behavior is
not under investigation, bypassing simulated global L1/L2 for non-atomic global
memory can significantly reduce runtime. That should not be folded into this
PR, and the prior proof of concept is not directly suitable because it coupled
cache bypass with single-threaded memory lock elision.

For a future PR, a safer shape would be a config option such as
`global_cache_mode = "modeled" | "bypass_non_atomic"` that bypasses only
non-atomic global cache modeling, preserves thread-safe `GpuMemory` accesses,
and keeps atomics on the serialized L2 path. This would be especially relevant
for race-detection workflows where cache timing/coherence is not the subject of
the investigation.

## Commentary

The test coverage added around L2 threading, sparse-memory block accesses, XCD
partitioning, CPU dispatch pool reuse, and thread-count output invariance is
well targeted. The ROCm Collective Communications Library (RCCL) serial pin for
the two-GPU config is also important: the local `ctest -L rccl -j1` run passed
after rebuilding the daemon/RCCL test targets, which gives confidence that the
timeout regression noted in review discussion is covered by the current branch.
