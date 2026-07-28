This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8705

**Commit reviewed:** `13069e1e33e1` (`feat(rocjitsu): partition execution by
XCD`).

**Follow-up mode:** this review considers the previous review of
`4587008cea21` and the subsequent public review discussion. The current PR was
then reviewed independently because its scope and implementation changed
substantially.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, and targets `develop`. The current head
is one commit rebased onto current `develop`. GitHub still requires a review.
Release, Clang ASan/UBSan, TSan, pre-commit, package, and TheRock checks pass.
The GCC ASan/UBSan job fails while compiling `matmul_test.cpp`, as reproduced
below.

The author removed `soc_dispatch` from this PR, split checkpoint restoration
into PR #9370, made generic FM partitioning explicit opt-in, and added the new
XCD helper to the existing vector-add, matmul, and scaling workload paths.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests scaling_test --parallel 8
```

Result: all 402 build steps passed in 128.67s real, 953.62s user, 46.72s sys
with the configured Clang host compiler.

**Partitioning, explicit-policy, and public C-API coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='XcdPartitioningTest.*:TopologyPartitionTest.*:TerminationTest.RequestExitWakesAllPartitions:StressTest.AsyncInjectionDuringActiveSimulation'
```

Result: 14/14 passed, 0 failed, 0 skipped, 0 errored. Timing: 1.46s real,
0.81s user, 0.61s sys.

**Real multi-XCD functional workloads:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='VectorAddStressTest.AllCUsGoldenReference_MultiThreaded:MatmulStressTest.TiledAllCUs_MultiThreaded:MatmulStressTest.MfmaAllCUs_MultiThreaded:MatmulStressTest.Cdna4TopologyDispatchAndHalt_MultiThreaded'
```

Result: 4/4 passed, 0 failed, 0 skipped, 0 errored. Timing: 1.60s real,
4.79s user, 0.59s sys.

**GCC compile check:**

I replayed the `matmul_test.cpp` compile from `compile_commands.json` with
`g++`, the same generated/include directories, and:

```bash
g++ -std=gnu++20 -fsyntax-only -Wall -Wextra -Wpedantic -Werror \
  <configured defines and include paths> \
  $SRC_DIR/tests/matmul_test.cpp
```

Result: failed with:

```text
matmul_test.cpp:123:8: error: suggest explicit braces to avoid ambiguous
'else' [-Werror=dangling-else]
```

This matches the current GCC ASan/UBSan CI failure.

**Release explicit-policy counterexample:**

I compiled a small Simdojo program with `-DNDEBUG`. It configured two engine
threads, manually installed one partition, and called `create()`:

```text
SimulationEngine config: num_threads = 2
Topology policy result:  1 partition
```

The submitted code accepted the mismatch and printed:

```text
contexts=2 partitions=1
```

The debug assertion in `setup_partitions()` is therefore the only validation
of this new caller-supplied contract. The temporary probe was removed.

**Scaling benchmark:**

```bash
time -p $BUILD_DIR/tests/scaling_test
```

I stopped the full sweep after its first single-thread measurement took about
119 seconds. The benchmark does not assert correctness, while the four focused
golden-result workloads above directly cover the changed helper. The author
reports completing the full 1–8-thread sweep.

**Diff hygiene and formatting:**

```bash
git diff --check <pr-base>..HEAD
$SRC_DIR/.venv/bin/pre-commit run --files \
  $(git diff --name-only <pr-base>..HEAD)
```

Result: passed.

## Summary

The rewritten PR has one coherent purpose: make whole XCD subtrees the
rocjitsu partition-affinity unit. Normal VM creation counts XCDs across all
SoCs, clamps the requested engine thread count to that total, and explicitly
installs a round-robin XCD mapping before engine creation. Components outside
an XCD remain on partition zero.

The Simdojo integration is now explicit. Multi-threaded engines must install a
partition policy before `create()`. The generic FM algorithm remains available
as the opt-in `partition_balanced()` operation; callers with hardware ownership
constraints use an explicit assignment. This is much clearer than using a
nonempty partition vector as a silent override of an automatic default.

The PR also makes `rj_vm_step()` return `ROCJITSU_STATUS_UNSUPPORTED` for
multi-partition VMs and uses the shipped XCD helper in the existing real-kernel
tests rather than retaining duplicate partitioning implementations.

The core XCD mapping and project-level direction look good. The remaining
new design issue is in the explicit partition-policy contract now exposed by
Simdojo: release builds do not validate that a caller-supplied policy matches
the engine configuration. This follow-up does not repeat the external-owner,
configuration naming, checkpoint, SoC-dispatch, or broader stack-design
questions covered by previous reviews.

## Actionable items

### 1. Validate explicit partition policies at runtime

**Files:** `emulation/rocjitsu/lib/simdojo/src/simulation.cpp:25-34`,
`emulation/rocjitsu/lib/simdojo/src/simulation.cpp:73-99`,
`emulation/rocjitsu/lib/simdojo/src/topology.cpp:215-229`

The new contract requires callers to choose a policy for a multi-threaded
engine, but its important invariants are still debug assertions:

- `config.num_threads` must be nonzero;
- `topology.partitions().size()` must equal `config.num_threads`;
- every explicit assignment must return an in-range partition ID;
- cross-partition links must have positive latency and must not be
  `QueuedLink`s.

In release mode, a two-thread engine accepted a one-partition topology and
created two contexts. Other mismatches can leave components with partition IDs
outside `contexts_`, causing out-of-bounds access when they schedule events.
An out-of-range `partition_manual()` callback similarly indexes the partition
vector unchecked when assertions are disabled.

Make `create()` and the partition APIs reject invalid configurations with
`std::invalid_argument` before mutating engine/component state. Add
release-independent tests for zero partitions, partition-count mismatch,
out-of-range assignments, zero-latency cross-partition links, and
cross-partition queued links.

### 2. Make the changed matmul test compile with GCC

**File:** `emulation/rocjitsu/tests/matmul_test.cpp:123`

The unbraced statement:

```cpp
if (num_threads > 1)
  ASSERT_TRUE(amdgpu::partition_topology_by_xcds(...));
```

triggers GCC's `-Wdangling-else` because `ASSERT_TRUE` is a control-flow macro,
and warnings are errors. Add braces around the conditional and require the
GCC sanitizer build to pass.

## Suggestions

None beyond the scope and design questions already raised in previous reviews.

## Commentary

The removal of `soc_dispatch` and checkpoint restoration makes this PR much
easier to reason about. Splitting checkpoint repair into PR #9370 and
postponing the separate dispatch-ownership model were good scope decisions.

Whole-XCD assignment is a reasonable current safety boundary because CP/CU/SPI
callbacks are partition-affine and the XCD owns shared L2 state. The rewritten
PR is focused enough that the two actionable items above can be handled without
another architectural decomposition.
