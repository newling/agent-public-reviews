This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8705

**Commit reviewed:** `6cece9090054` (`feat(rocjitsu): partition execution by
XCD`).

**Follow-up mode:** this review considers the previous agent review of
`13069e1e33e1` and then independently evaluates the current patch. The two
previous actionable items are fixed: explicit partition-policy invariants now
use release-independent runtime validation with direct tests, and the matmul
test's `ASSERT_TRUE` conditional is braced.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, targets `develop`, and GitHub reports
the current head as mergeable with review still required. All current release,
Clang ASan/UBSan, GCC ASan/UBSan, TSan, pre-commit, package, and TheRock checks
pass; unrelated matrix entries are skipped.

**Focused RelWithDebInfo build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests scaling_test --parallel 8
```

Result: all 451 build steps passed in 231.73s real, 1757.42s user, 56.73s sys.

**Partition-policy, XCD mapping, termination, and public C-API coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='XcdPartitioningTest.*:TopologyPartitionTest.*:TerminationTest.RequestExitWakesAllPartitions:StressTest.AsyncInjectionDuringActiveSimulation'
```

Result on the submitted source: 21/21 passed, 0 failed, 0 skipped, 0 errored.
Timing: 1.41s real, 0.49s user, 0.87s sys.

**Real multi-XCD functional workloads:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='VectorAddStressTest.AllCUsGoldenReference_MultiThreaded:MatmulStressTest.TiledAllCUs_MultiThreaded:MatmulStressTest.MfmaAllCUs_MultiThreaded:MatmulStressTest.Cdna4TopologyDispatchAndHalt_MultiThreaded'
```

Result: 4/4 passed, 0 failed, 0 skipped, 0 errored. Timing: 0.91s real,
0.97s user, 0.59s sys.

**Balanced-policy external-owner counterexample:**

I temporarily added a Simdojo regression with one consumer in the topology
tree and one external producer connected to it by a normal link, then called:

```cpp
topology.partition_balanced(2);
```

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='TopologyPartitionTest.BalancedPartitionHandlesExternalLinkOwner'
```

Result on the submitted code: the test process segfaulted with exit status 139
while classifying links, before producing a GoogleTest result. Timing: 1.12s
real.

I then prototyped adding each unique external link-endpoint owner to the
component set before building the balanced partitioner's adjacency graph. The
counterexample and the submitted manual-repartition external-owner test passed:
2/2 passed, 0 failed, 0 skipped, 0 errored in 0.00s. The temporary regression
and prototype were removed. I rebuilt the submitted source and reran the
21-test focused selection reported above.

**Scaling benchmark:** I did not repeat the full timing sweep. It has no
correctness assertions, the previous review found its first single-thread
measurement took about two minutes, and the four focused golden-result
workloads above directly cover the submitted XCD helper.

**Diff hygiene and formatting:**

```bash
git diff --check <pr-base>..HEAD
$SRC_DIR/.venv/bin/pre-commit run --files \
  $(git diff --name-only <pr-base>..HEAD)
```

Result: passed.

## Summary

The current patch makes whole XCD subtrees the explicit rocjitsu partition
unit. VM creation counts XCDs across all configured GPUs, clamps the requested
engine worker count to that total, assigns complete XCD subtrees round-robin,
and leaves non-XCD components on partition zero. Multi-partition VMs use
`rj_vm_run()`; `rj_vm_step()` now returns a dedicated unsupported status.

At the Simdojo boundary, multi-threaded engines no longer silently invoke the
generic graph partitioner. Callers must select either an explicit manual policy
or the renamed `partition_balanced()` policy. The current revision also
validates zero worker counts, partition-count mismatches, out-of-range manual
assignments, zero-latency cross-partition links, and cross-partition queued
links without relying on debug assertions.

The XCD-specific path and the previous release/GCC fixes look good. The
remaining correctness issue is in the still-public balanced policy: it does
not apply the external-link-owner handling added to the manual policy and can
index the partition vector with an unassigned partition ID.

## Actionable items

### 1. Include or reject external link owners in `partition_balanced()`

**Files:** `emulation/rocjitsu/lib/simdojo/src/topology.cpp:209-236`,
`emulation/rocjitsu/lib/simdojo/src/topology.cpp:293-305`,
`emulation/rocjitsu/lib/simdojo/include/simdojo/sim/topology.h:159-165`

`partition_balanced()` builds its component set only with
`collect_all_components()`. If a link endpoint is owned by a component outside
the topology tree, `AdjacencyGraph::build()` skips that endpoint, the
partitioner never assigns it a partition ID, and `classify_links()` later uses
`INVALID_PARTITION_ID` as an index into `partitions_`. The temporary
two-partition regression above therefore segfaulted. The one-partition branch
does not call `classify_links()`, but it still omits the external owner from
engine registration and component lifecycle calls.

This ownership shape is supported by `Topology::add_link()` and is used by
rocjitsu's standalone backing controller. The rewritten
`partition_manual()` already scans link endpoints and includes each external
owner exactly once, so the two explicit policies currently have incompatible
safety contracts.

Make `partition_balanced()` include every unique link-endpoint owner in the
graph component set before partitioning, or reject such topologies with
`std::invalid_argument` before mutating partition state. Add direct
one-partition and multi-partition tests, including repeated partitioning, that
verify every endpoint owner has an in-range partition and occurs exactly once
in the resulting partitions.

## Suggestions

### 1. Update the XCD helper documentation for its one-partition behavior

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/partitioning.h:20-28`,
`emulation/rocjitsu/tests/partitioning_test.cpp:120-130`

The header says the helper installs a manual policy only when
`num_partitions` is greater than one and otherwise returns false. The current
implementation and direct test intentionally install a one-partition manual
mapping and return true. Document the actual nonzero-partition contract so a
caller does not treat the one-partition call as a no-op.

## Commentary

The previous review's release-validation and GCC findings are resolved, and
the submitted whole-XCD mapping passes the focused single-GPU, multi-GPU,
public C-API, and real-kernel coverage. The remaining item is isolated to the
generic balanced-policy boundary rather than the rocjitsu XCD policy itself.

## Appendix: external-owner counterexample

The following temporary regression was added beside the existing
`TopologyPartitionTest` cases in
`emulation/rocjitsu/tests/simdojo_sim_test.cpp`. It uses the file's existing
`ProducerComponent` and `ConsumerComponent` test helpers:

```cpp
TEST(TopologyPartitionTest, BalancedPartitionHandlesExternalLinkOwner) {
  Topology topology;
  auto root = std::make_unique<CompositeComponent>("root");
  auto consumer = std::make_unique<ConsumerComponent>("consumer");
  auto *consumer_ptr = consumer.get();
  root->add_child(std::move(consumer));
  topology.set_root(std::move(root));

  ProducerComponent external("external", 0, 1, false);
  topology.add_link(external.out_port(), consumer_ptr->in_port(), 1);

  topology.partition_balanced(2);

  EXPECT_LT(external.partition_id(), 2u);
  size_t occurrences = 0;
  for (const auto &partition : topology.partitions())
    occurrences +=
        std::count(partition.components.begin(), partition.components.end(), &external);
  EXPECT_EQ(occurrences, 1u);
}
```

On the submitted implementation, execution does not reach either expectation:
`partition_balanced(2)` leaves `external.partition_id()` equal to
`INVALID_PARTITION_ID`, and `classify_links()` uses that value as an index into
the partition vector and segfaults.

The prototype fix collected each unique link-endpoint owner before constructing
the adjacency graph:

```cpp
auto components = collect_all_components();
std::unordered_set<Component *> collected(components.begin(), components.end());
for (auto &link : links_) {
  for (Component *owner : {link->src()->owner(), link->dst()->owner()}) {
    if (owner && collected.insert(owner).second)
      components.push_back(owner);
  }
}
```

With that prototype, the regression and the submitted
`RepartitionRetainsExternalLinkOwnerOnce` test both passed. The production
snippet is included only to document how the diagnosis was confirmed; the
actionable item intentionally allows either including external owners or
rejecting them before partition state is mutated.
