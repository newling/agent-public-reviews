This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8705

**Commit reviewed:** `a487f322f99f` (`fix(rocjitsu): tighten XCD partition
setup`), the current PR head.

**Review mode:** third-round follow-up. I read the two previous agent reviews
and the subsequent public resolution discussion, then independently reviewed
the current patch and its new contracts.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, is mergeable, and still requires
review. The release, Clang ASan/UBSan, GCC ASan/UBSan, TSan, pre-commit,
gfx950 package, and HIP NVIDIA summary checks pass. The gfx94X package job
failed in the self-hosted container while cloning the unrelated
`compiler/amd-llvm` submodule, before configuration or compilation; its later
missing-build-artifact errors are consequences of that infrastructure failure.

The current base includes the asynchronous `request_exit()` barrier repair
from PR #9441. The submitted regression now removes the max-tick escape and
requires `ExitReason::EXIT_REQUEST`.

**RelWithDebInfo configuration:**

```bash
time -p cmake -S $SRC_DIR/emulation/rocjitsu -B $BUILD_DIR -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_COMPILER=$ROCM_PATH/lib/llvm/bin/clang \
  -DCMAKE_CXX_COMPILER=$ROCM_PATH/lib/llvm/bin/clang++ \
  -DBUILD_TESTING=ON
```

Result: configuration and generation passed in 7.08s real, 4.94s user, and
0.67s sys.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests scaling_test --parallel 8
```

Result: all 572 build steps passed in 256.84s real, 1970.24s user, and
61.68s sys.

**Partition-policy, XCD mapping, termination, stress, and public C-API
coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='XcdPartitioningTest.*:TopologyPartitionTest.*:TerminationTest.RequestExitWakesAllPartitions:StressTest.AsyncInjectionDuringActiveSimulation'
```

Result: 29/29 passed, 0 failed, 0 skipped, 0 errored. Timing: 1.37s real,
0.80s user, 0.71s sys.

**Real multi-XCD functional workloads:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='VectorAddStressTest.AllCUsGoldenReference_MultiThreaded:MatmulStressTest.TiledAllCUs_MultiThreaded:MatmulStressTest.MfmaAllCUs_MultiThreaded:MatmulStressTest.Cdna4TopologyDispatchAndHalt_MultiThreaded'
```

Result: 4/4 passed, 0 failed, 0 skipped, 0 errored. Timing: 0.86s real,
1.10s user, 0.55s sys.

**Repeated asynchronous-exit coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='TerminationTest.RequestExitWakesAllPartitions' \
  --gtest_repeat=20 --gtest_break_on_failure
```

Result: 20/20 iterations passed, 0 failed, 0 skipped, 0 errored. Timing:
1.01s real, 1.93s user, 1.23s sys.

**External-owner lifetime counterexample:**

I compiled `component.cpp`, `simulation.cpp`, and `topology.cpp` with:

```bash
$CXX -std=c++20 -O1 -g -fsanitize=address \
  -fno-omit-frame-pointer -pthread \
  -I$SRC_DIR/emulation/rocjitsu/lib/simdojo/include \
  -I$SRC_DIR/emulation/rocjitsu/lib/util/include \
  <simdojo sources> <probe source> -o $PROBE

time -p env ASAN_OPTIONS=halt_on_error=1:abort_on_error=0 $PROBE
```

The probe added a link from a caller-owned external component to a tree
component, partitioned once, destroyed the external component, and called
`partition_balanced(1)` again. It failed with exit status 1 in 0.05s real:

```text
ERROR: AddressSanitizer: heap-use-after-free
Port::owner()
Topology::append_link_endpoint_owners()
Topology::partition_balanced()
```

This is not a failure of a correctly maintained borrowed lifetime. It
demonstrates why that lifetime is a load-bearing part of the new
external-owner contract and must not be contradicted or left implicit.

**Rust C-status parity test:**

```bash
cargo test --manifest-path \
  $SRC_DIR/emulation/mirage/rocjitsu_sys/Cargo.toml \
  status_codes_match_c_api -- --exact
```

I could not run this test because `cargo` is not installed in the review
environment. The added test was inspected directly; it compares every C enum
entry with the Rust constants.

**Diff hygiene:**

```bash
git diff --check <pr-base>..HEAD
```

Result: passed. The public pre-commit check also passes.

I did not repeat the full scaling sweep. It has no correctness assertions,
the previous local review found that even its first single-thread measurement
took about two minutes, and the four golden-result workloads above directly
exercise the submitted XCD helper. The PR reports a completed 1-8-thread
sweep.

## Summary

The current patch makes whole XCD subtrees the explicit rocjitsu partition
unit. C-API VM creation collects every configured SoC, clamps the requested
engine partition count to the aggregate XCD count, warns when the effective
count differs, and installs a global round-robin XCD assignment before engine
creation. Non-XCD components remain on partition zero. Multi-partition VMs
run through `rj_vm_run()`; `rj_vm_step()` returns the new unsupported status.

Simdojo now requires an explicit policy for multi-threaded engines. The
generic graph algorithm remains available through `partition_balanced()`,
while `partition_manual()` supports hardware ownership constraints. Both
policies now include each unique link-endpoint owner even when it is outside
the root component tree, fixing the balanced-policy crash from the previous
review. Release-independent validation covers zero workers, partition-count
mismatches, out-of-range assignments, zero-latency boundary links, and
cross-partition queued links.

The previous XCD-helper documentation mismatch, balanced external-owner
crash, asynchronous-exit concern, error-message visibility, and topology
membership check are all resolved. The remaining issue is the ownership and
lifetime contract for the external components that the two partition policies
now retain and send through engine lifecycle hooks.

## Actionable items

### 1. State or enforce the lifetime of external link-endpoint owners

**Files:** `emulation/rocjitsu/lib/simdojo/include/simdojo/sim/topology.h:73-77,90-110,164-191`,
`emulation/rocjitsu/lib/simdojo/src/topology.cpp:149-155,215-252`,
`emulation/rocjitsu/docs/simdojo.md:263-267`

`partition_balanced()` and `partition_manual()` now append external
link-endpoint owners to their component lists. `Topology` stores only raw
`Port*`/`Component*` references for those objects; it neither owns them nor
can detect their destruction. Repartitioning dereferences their ports, and
the engine later calls `initialize()`, `startup()`, and `shutdown()` through
the retained component pointers.

The public contract currently says that `Topology` owns all components via
the root, while `partition_manual()` separately says it assigns external
owners. It never states that those external owners and their ports are
borrowed and must remain alive. The ASan probe above shows the resulting
failure mode, and the submitted tests already rely on the correct ordering by
declaring each external component before its `Topology` or
`SimulationEngine`.

Correct the ownership statement and document on `add_link()`,
`add_queued_link()`, `partition_balanced()`, and `partition_manual()` that
every endpoint owner outside the root tree must outlive all repartitioning and
engine create/run/shutdown operations that retain it. Add a short lifetime
comment to the external-owner tests so future declaration reordering does not
silently invalidate the examples. If the intended contract is ownership
rather than borrowing, add an owning external-component registration API and
use it instead of retaining untracked raw pointers.

## Suggestions

None.

## Commentary

The current implementation and focused execution paths otherwise look ready.
The new XCD helper rejects SoCs outside the supplied topology before mutation,
the aggregate multi-GPU mapping is documented and directly tested, and both
partition policies now agree on external endpoint participation.

The PR description's validation note is stale: it says the change is one
commit rebased onto `5d3ca048215e`, while the reviewed head is a five-commit
stack based on `f37277c071d0`. Updating that note would make the public review
state easier to follow, but it does not affect the implementation.
