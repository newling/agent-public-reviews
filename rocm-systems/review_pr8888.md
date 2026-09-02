This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#8888](https://github.com/ROCm/rocm-systems/pull/8888)

**Review mode:** follow-up review. I read the existing review summaries,
inline threads, and PR discussion, then independently checked each current
concern against the submitted head.

**Commit reviewed:** `703496a922e4` (`def/use now track v_cmp and v_cmpx
implicit EXEC/VCC defs`), the current PR head.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, not a draft, targets `develop`, and is blocked by
outstanding change requests. GitHub reports the branch as mergeable apart from
the review/CI gates.

The active development checkout contained unrelated files, so I exported the
public PR commit into a disposable source snapshot instead of switching that
checkout.

**Clang build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: all 571 build steps passed in 172.02s real, 1286.55s user, and
60.13s sys.

**Submitted spill, descriptor, builder, special-state, and simulator
coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='InstrumentorSpill.*:InstrumentorSgprGate.*:\
InstrumentorProbeSpill.*:InstructionBuilder.BuildScratch*:\
InstructionBuilder.BuildWait*:Dbi*SpillSimFixture.*:\
Dbi*ExecPreserveSimFixture.*:Dbi*ExecWidenSpillSimFixture.*:\
Dbi*ExecMaskAtSpillSimFixture.*:KernelDescriptorScanTest.*:\
ProbeClobberTest.*'
```

Result on the final submitted source: 80/80 passed, 0 failed, 0 skipped,
0 errored in 0.15s real.

**GCC 13 ASan/UBSan build and focused tests:**

```bash
time -p cmake --build $GCC_ASAN_BUILD_DIR \
  --target rocjitsu_tests --parallel 8

time -p $GCC_ASAN_BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='<same focused filter as above>'
```

Result: all 571 build steps passed in 377.58s real, 2678.05s user, and
128.29s sys. The focused test selection passed 80/80, 0 failed, 0 skipped,
0 errored in 1.44s real.

The public GCC ASan/UBSan job is red, but its full log shows that the build
succeeded and 2,191 of 2,192 tests passed. The only failure was a 1,500-second
timeout in `TerminationTest.RequestExitWakesAllPartitions`, which is outside
this diff. The same test passed locally under the GCC sanitizer build:

```bash
time -p timeout 30s $GCC_ASAN_BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='TerminationTest.RequestExitWakesAllPartitions'
```

Result: 1/1 passed in 0.84s real. I therefore treat the public red check as a
transient unrelated timeout rather than a failure caused by this PR.

**Incoming-load spill-order counterexample:**

One current review thread asks whether loads must be completed before the spill
saves. I constructed a CDNA4 kernel with:

```text
scratch_store v2, 0
s_waitcnt 0
v2 = 0
scratch_load v2, 0          # asynchronous producer of the live value
ANCHOR: s_waitcnt 0         # original code waits before consuming v2
v3 = v2
```

The probe clobbers `v2`, so instrumentation must save it before the call. The
review regression inspects the generated trampoline and requires the first
spill store to be preceded by an incoming-load wait.

On the submitted code the regression failed:

```text
Expected: build_wait_loads_complete(arch)
Actual:   s_mov_b64 exec, -1
```

Result: 0/1 passed in 0.02s real. The simulator still produced the expected
numerical value, which is consistent with the existing review observation that
the simulator's memory completion behavior does not expose this hardware
wait-counter hazard.

I prototyped adding `build_wait_loads_complete()` before the spill stores and
updated one layout-sensitive sabotage test to locate the EXEC toggle rather
than assume it is immediately adjacent to the store. The counterexample and
the neighboring static/simulator spill and EXEC coverage passed: 57/57,
0 failed, 0 skipped, 0 errored in 0.13s real.

That prototype demonstrates the direct VGPR case only; the production fix must
also consider outstanding scalar, LDS, sample, and BVH producers and must place
the synchronization before special-state saves and use of selected temporary
registers. See Actionable Item 1.

**Diff hygiene:**

```bash
git diff --check <pr-base>..HEAD
```

Result: passed.

The temporary counterexample and prototype were removed. The submitted source
was restored, rebuilt, and used for the final 80-test Clang run above.

## Summary

This PR turns the existing DBI probe-call path from a dead-register-only
prototype into a state-preserving call envelope for CDNA3, CDNA4, and RDNA4.

The central policy remains:

```text
instrumentation clobbers = probe-body clobbers | call-envelope clobbers
spill set                = live before anchor & instrumentation clobbers
```

Ordinary VGPRs are stored directly to per-lane scratch. SGPRs move through a
dead VGPR lane using `v_writelane_b32`, then use the same scratch path; the
epilogue loads the bridge and recovers the scalar with `v_readlane_b32`.
`SpillManager` gives each register a stable four-byte per-lane slot in a
16-byte-aligned DBI spill zone above the kernel's existing private segment.

The probe-call planner also allocates SGPR resources within the kernel's actual
descriptor allocation: the fixed return link, a target-address pair, SCC
temporary, and save slots for EXEC/VCC/M0. EXEC and VCC are preserved
unconditionally because implicit effects are not yet complete enough to make
the decision precise; M0 remains clobber-gated. FLAT_SCRATCH-clobbering probes
fail closed because the spill instructions depend on that state.

When spilling, the trampoline:

1. saves special state;
2. widens EXEC to all lanes;
3. stores every live-and-clobbered register;
4. waits for the spill stores;
5. restores the anchor EXEC mask;
6. calls the probe;
7. widens EXEC for the reloads;
8. reloads spilled state and waits;
9. restores special state; and
10. executes the relocated original instruction.

The kernel descriptor's `private_segment_fixed_size` is increased atomically
with the `.text` replacement. Current spill support deliberately requires one
discoverable kernel descriptor and a nonzero existing private segment.

The PR also extracts kernel-descriptor discovery from the DBT translator into
a shared scanner, moves instruction construction into a common builders
directory, bounds temporary allocation by descriptor counts, adds the RDNA4
store-counter fence, and provides static plus simulator coverage for VGPR,
SGPR, combined, multi-SGPR, partial-EXEC, and special-state cases.

Most earlier review comments have materially improved the implementation. The
remaining correctness gap is synchronization with memory operations already
in flight when the anchor is reached.

## Actionable items

### 1. Drain incoming register-producing operations before saving or reusing registers

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/trampoline_builder.cpp:94-128`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/trampoline_builder.cpp:330-353`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/builders/spill_builders.h:131-159`,
`emulation/rocjitsu/tests/dbi/dbi_spill_sim_test.cpp`

The trampoline begins saving special state and emitting scratch stores without
first waiting for memory instructions that precede the anchor. Liveness says a
register's value will be needed later; it does not prove that an asynchronous
producer has finished writing that value.

For example:

```text
load v2
anchor: wait for load
use v2
```

If a probe clobbers `v2`, the rewritten path branches away before the original
wait and immediately issues `scratch_store v2`. The store can read the old
value because the load has not been drained. The prologue's existing
store-completion wait is too late: it occurs after the spill store has consumed
its source.

The same issue applies to the SGPR resources selected because they are dead at
the anchor. A previous asynchronous scalar load may still be scheduled to
write a dead target pair or special-state temporary. The instrumentation can
save EXEC or materialize the probe address there, then have the pending load
overwrite it before the call or restore.

Add an architecture-correct incoming-operation drain before the envelope first
reads or repurposes registers. A CDNA `s_waitcnt 0` supplies a conservative
barrier. RDNA4 has split queues, so `s_wait_loadcnt 0` alone is not a complete
general solution: vector loads, image/sample or BVH results, LDS/GDS results,
and scalar memory results use LOADCNT, SAMPLECNT/BVHCNT, DSCNT, and KMCNT
families respectively. Reuse or extract a neutral helper from the existing
wait-counter translation machinery rather than treating the scratch-load wait
as a universal pre-envelope barrier.

Add a regression shaped like the counterexample in Tests:

- issue a load into a register that is live at the anchor;
- place the original wait at the anchor or immediately afterward;
- force the probe to clobber that register;
- assert the trampoline drains the relevant incoming counter before the spill
  save;
- retain numerical or hardware coverage where the execution model can expose
  the hazard.

The minimal load-wait prototype made the direct VGPR regression and 57
neighboring tests pass, but the final implementation should cover every
register-producing counter used by supported architectures and protect the
selected SGPR temporaries as well as explicit spill sources.

### 2. Update the DBI design document and stale public header contracts

**Files:** `emulation/rocjitsu/docs/dbi-design.md:7,72-83,87-104,163-220,263-307`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/instrumentor.h:28-33`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/instrumentor.h:230-246`

The latest blocking review requests the documentation update, and the current
head still does not modify `docs/dbi-design.md`. The document continues to
state that:

- register spilling is future work and non-empty spill sets fail closed;
- the Instrumentor requires an empty spill set;
- the TrampolineBuilder emits only the old SCC/call envelope;
- SpillManager is not consumed by the pipeline and code generation remains
  future work;
- probe calls reject every non-empty spill set; and
- the test matrix contains none of the new spill, special-state, descriptor,
  or simulator coverage.

The architecture diagram and probe-call sequence also omit descriptor
discovery, scratch growth, class-specific save/restore, EXEC widening and
anchor-mask restoration, special-state preservation, wait ordering, and the
one-kernel/nonzero-scratch restrictions.

Update the document to describe the submitted behavior and clearly retain the
actual deferrals: AccVGPR support, multi-kernel/multi-text spilling, zero-
private-segment setup, FLAT_SCRATCH-clobbering probes, exact conditional
EXEC/VCC preservation, link-pair negotiation or SGPR growth, general EXEC
policy, and range extension.

The public header is stale for the same reason. Its top-level future-work list
still names probe-call bodies, and the spill-policy comment says builder
planning and dead-register selection land in a later slice even though this PR
implements both. Align these comments with the final public design contract.

## Suggestions

### 1. Make the saved-EXEC lookup explicit instead of defaulting to s0

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/trampoline_builder.cpp:330-358`

`emit_probe_call()` initializes `exec_temp` to zero and then searches
`special_state_saves`. The current Instrumentor sets `preserve_exec = true`
before planning, and the planner also requests EXEC preservation for a spill,
so the production caller satisfies the invariant. A malformed or future
builder caller would silently emit `s_mov_b64 exec, s[0:1]` when no EXEC save
exists.

Use `std::optional<uint16_t>` or a sentinel and fail emission when
`full_mask_exec` is true but the plan lacks an EXEC save. This turns an
important plan/emit invariant into a checked contract and addresses the
corresponding open review thread without changing current behavior.

### 2. Resolve special scalar operand codes through the target architecture

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/builders/instruction_builder.h:92-109`

The global VCC, EXEC, and negative-inline constants are taken from CDNA4's
generated operand table and direct tests prove that their current values match
the other supported ISAs. That is sufficient for today's binaries, but it
makes future ISA support depend on remembering to extend a cross-generation
equality test.

Prefer small arch-parameterized accessors, as already done for M0, or derive
the values through a generated shared property. This keeps the builder's
stated target-parameterized contract intact when a future encoding diverges.

### 3. Explain why the SGPR bridge currently excludes spilled VGPRs

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/instrumentor.cpp:384-397`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/trampoline_builder.cpp:100-121`

An open review question asks why a VGPR already being spilled cannot serve as
the SGPR bridge. Under the current emission order, excluding it is necessary:
the epilogue restores ordinary VGPRs first, then repeatedly loads SGPR values
through the bridge. If the bridge were one of the restored VGPRs, the final
SGPR restore would overwrite its recovered kernel value.

Add that reason to the planner comment. Reusing a spilled VGPR could be a
future optimization, but it requires restoring SGPRs first and the bridge VGPR
last, or issuing a final reload of the bridge after all `v_readlane`
operations.

## Commentary

The existing review history was useful and most of its earlier blocking
correctness concerns are resolved in the current head:

- spill stores and loads execute under full EXEC;
- the anchor EXEC mask is restored before the probe;
- EXEC/VCC are preserved despite incomplete implicit-effect summaries;
- temporary SGPR selection is bounded by the descriptor allocation;
- RDNA4 uses a store-counter wait before reloads;
- descriptor discovery is shared with DBT rather than duplicated;
- multi-kernel failure, combined VGPR/SGPR spilling, and multiple SGPR spills
  have direct tests; and
- shared DBI test utilities were moved out of the patch-only directory.

The currently open EXEC-policy comment is a design choice rather than a
correctness defect. Running the probe under the anchor mask gives
instrumentation the same lane participation as the interrupted program point;
running under full EXEC can also be useful for tools. The future public API
should make that policy explicit instead of relying indefinitely on one
default.

The `SpillSlot::cls` field is redundant in the current two-vector plan, but it
records the register class and is immediately useful to the stacked AccVGPR
extension. Removing it here only to reintroduce it in the child PR would create
churn without improving the contract.

The shared/private split is moving in the intended direction. Kernel-
descriptor scanning, register analysis, slot allocation arithmetic, instruction
builders, and byte-level descriptor mutation are reusable mechanisms. Probe
ABI, interrupted-state preservation, EXEC policy, stable register-to-slot
identity, and all-or-nothing site handling remain DBI orchestration policy.

The red GCC sanitizer check should not be attributed to this change. Its log
shows an unrelated termination test timing out after the rest of the 2,192-test
run passed, while the exact submitted head builds and passes the focused spill
coverage locally under GCC ASan/UBSan.
