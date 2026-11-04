This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocjitsu-test-corpus#83](https://github.com/ROCm/rocjitsu-test-corpus/pull/83)

**Reviewed head:** [`bbf76980b6b`](https://github.com/ROCm/rocjitsu-test-corpus/commit/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b), 2026-11-04. This follow-up combines a kernel-by-kernel walkthrough, an independent check of the current submission, and reconciliation with the [earlier proposal review](https://github.com/newling/agent-public-reviews/blob/main/rocjitsu-test-corpus/review_pr83_test_proposals_20261102.md). The current submission contains 15 kernels and 29 tests; it includes the load→store pair added after the 14-kernel walkthrough.

**Suggestion branch:** [review/corpus83-walkthrough-20261104](https://github.com/newling/rocjitsu-test-corpus/tree/review/corpus83-walkthrough-20261104), based directly on the reviewed head. [Combined changes](https://github.com/newling/rocjitsu-test-corpus/compare/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b...2e5d94b8f929bca2d38ef8b25645faa1bd0755ff). These are test and comment changes, with no emulator or shared-matcher implementation changes. The commits are incremental; later additions use the renamed LDS helpers, and test-adding commits update the common inventory count. Cherry-picking a subset may require retaining the original helper names and recomputing that count.

| Commit | Change |
| --- | --- |
| [1c71716](https://github.com/newling/rocjitsu-test-corpus/commit/1c717166506a264fdbbc3118375c5f7e4d725ee3) | remove sleep from cross-wave tensor DMA race |
| [5f7a444](https://github.com/newling/rocjitsu-test-corpus/commit/5f7a444fe2a864ced924363f37319403d78ebf6f) | cover real tensor store between empty stores |
| [3fe6b56](https://github.com/newling/rocjitsu-test-corpus/commit/3fe6b560758dc85ef399767ce2f5364f5048235e) | isolate zero-filled bytes in tensor DMA race pair |
| [019c698](https://github.com/newling/rocjitsu-test-corpus/commit/019c698c95731b33fd6f36d251143f5baacbb8cd) | expose waits in LDS helper names |
| [837cc6c](https://github.com/newling/rocjitsu-test-corpus/commit/837cc6cdce92c4499d50acffa39b020ca3b748c7) | cite current tensor ISA and qualify LDS fault coverage |
| [bdc31b3](https://github.com/newling/rocjitsu-test-corpus/commit/bdc31b3c74c2a13b81370d9c26d8b112ab804d70) | read across completed and pending tensor tiles |
| [147e1c4](https://github.com/newling/rocjitsu-test-corpus/commit/147e1c42a7dc0908a75fe90d13d281964efe3348) | cover strict DS and tensor source containment |
| [9afbcbf](https://github.com/newling/rocjitsu-test-corpus/commit/9afbcbfd36316e717ccbec3aa4a0c2d2267ac5b7) | cover contained and partially overlapping tensor footprints |
| [d477249](https://github.com/newling/rocjitsu-test-corpus/commit/d4772496ab7bc20d02d86507984983573b71c9a6) | interleave padded tensor loads from three waves |
| [36d08b3](https://github.com/newling/rocjitsu-test-corpus/commit/36d08b3fc10cb33e353e2f56a28646b89f2973e7) | count all iterations as one tensor instruction |
| [e6a2f5a](https://github.com/newling/rocjitsu-test-corpus/commit/e6a2f5afeedeb5d3cba4e843e3ff00863076a521) | cover both empty gather shapes in partial tensor waits |
| [7016ecb](https://github.com/newling/rocjitsu-test-corpus/commit/7016ecb0dc2f2bc2bb32a659aea70c509949a431) | cover mixed tensor load and store partial waits |
| [9147aaf](https://github.com/newling/rocjitsu-test-corpus/commit/9147aafc7dc2dc991f934f8d4ddc21288d3737ad) | distinguish ordinary async and tensor completion |
| [6354e38](https://github.com/newling/rocjitsu-test-corpus/commit/6354e3834b1ed138c5183372a1860bbe28252299) | exclude partial tensor store holes from LDS reads |
| [2e5d94b](https://github.com/newling/rocjitsu-test-corpus/commit/2e5d94b8f929bca2d38ef8b25645faa1bd0755ff) | preserve full tile values beside zero-fill-only probes |

## Tests

The submitted gfx1250 suite passes 29/29 and the final suggestion branch passes 61/61 under emulation. The corpus adapter/inventory tests pass 65/65, matcher tests 21/21, and HIP error-support tests 7/7; whitespace checks pass.

The runtime, shared interposer, and race plugin were built together from Systems [#14689 at `78238be8d02`](https://github.com/ROCm/rocm-systems/commit/78238be8d028187f0b320e607479f1235588bd94), the revision named by the corpus PR. It includes the inspected #14688 head `2880fe7abbf`; it is not a descendant of the later #14687 head `d137d72589b`. Results below apply to the exact tested stack revision, not an untested combination of current heads. Builds use AMD Clang 23 (`a01cdbd92d1f931738a4897502747a68ae36eccf`) for HIP. Hardware qualification remains outstanding. Hosted corpus checks are security scans and do not replace these emulator runs.

Two deliberate observation mutations establish test sensitivity. Omitting zero-filled LDS writes leaves the submitted zero-fill pair passing, while the proposed zero-fill race fails with `expected at least one race, got none`. Replacing padded footprints with solid bounding intervals makes the proposed interleaved safe case fail with a false LDS race at byte 32. The synchronized zero-fill control and interleaved peer-read race control still pass under these mutations. The mutations are described in the appendix and are absent from the final build.

## Summary

The tests cover the main dependencies introduced by gfx1250 tensor DMA: the tensor load writes LDS, the tensor store reads LDS, and TENSORcnt completion must be distinguished from both DScnt completion and synchronization between waves. The same-wave load/store tests now correctly require an intervening tensor wait in either direction. The safe cases check data, and the negative cases identify the conflicting instruction classes without asserting values that a race makes unreliable.

The most important remaining weakness is the zero-fill race's consumer: it can currently pass on a conflict in the ordinary copied half. The remaining sleep is also unnecessary scheduling dependence in a test whose expected conflict can be described in either orientation. Most other changes below are optional coverage or readability improvements. Shared limitations in older architecture tests are identified separately, rather than treated as new requirements for gfx1250 bring-up.

Locations in the findings refer to `corpus/race/integration/hip_race_gfx1250_test.hip` at the reviewed head, unless stated otherwise. Commit links show the concrete proposals.

## Actionable items

### Confine the zero-fill race to zero-filled bytes

**Location:** [lines 635–680](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L635-L680). **Commits:** [3fe6b56](https://github.com/newling/rocjitsu-test-corpus/commit/3fe6b560758dc85ef399767ce2f5364f5048235e) and [2e5d94b](https://github.com/newling/rocjitsu-test-corpus/commit/2e5d94b8f929bca2d38ef8b25645faa1bd0755ff).

The descriptor copies sixteen integers and zero-fills the remaining sixteen, but every lane of wave 1 currently reads its original `lane()*4` address. A race at byte zero therefore satisfies `kTensorLoadThenReadRace` even if zero-fill writes are never registered. The source comment already claims that the consumer reads the zero-filled half; the code does not yet do that.

Map the peer reads through `(kTensorHalf + lane() % kTensorHalf) * 4`. Every peer access then lies within bytes [64,128), so the existing matcher can only succeed on the intended footprint. The synchronized peer control expects zeros. A separate same-wave `tensor_load_zero_fill_full_tile` test retains the full 0…15 followed by sixteen zeros value check. This keeps ordinary copied-data correctness while isolating the peer conflict.

This adapts the earlier `886c70c` proposal and preserves its purpose. The mutation result above confirms the issue on the current reviewed head. No new diagnostic wording or requirement to report every lane is needed.

### Remove the final scheduling sleep

**Location:** [helper at line 140 and call at line 307](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L134-L140). **Commit:** [1c71716](https://github.com/newling/rocjitsu-test-corpus/commit/1c717166506a264fdbbc3118375c5f7e4d725ee3).

`tensor_load_cross_wave_no_barrier_race` must report a conflict regardless of which wave the emulator schedules first. The remaining `s_sleep 4` biases the conflict toward tensor-load→DS-read so that a directional expectation passes. The other cross-wave cases now use barriers where their purpose permits one; this case intentionally lacks that synchronization.

Remove the helper and accept either the LDS/read tensor-load→DS-read report or the LDS/write DS-read→tensor-load report. The proposal parses once, requires successful parsing, and retains the instruction, memory-space, access, and finding-count constraints. It does not add a barrier or relax other tests' expectations. A prior temporary read-first scheduling probe verified the reverse matcher orientation; the exact current proposal passes the three cross-wave cases. No comparable sleep was found in the existing gfx950/gfx1151 race integration tests.

## Suggestions

### Make helper waits visible at their call sites

**Location:** [lines 144–162](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L144-L162). **Commit:** [019c698](https://github.com/newling/rocjitsu-test-corpus/commit/019c698c95731b33fd6f36d251143f5baacbb8cd).

`ldsWrite` issues a DS store without waiting, while `ldsFill` writes and waits, and `ldsRead` also waits for its returned VGPR. That difference is easy to miss in tests whose purpose is precisely to omit or retain a wait. Rename the waited helpers to `ldsFillAndWait` and `ldsReadAndWait`, and explicitly document the issue-only write. Existing gfx950/gfx1151 examples generally show the corresponding waits directly in their kernel assembly; this helper asymmetry is local to the new file.

### Use the current ISA references and qualify boundary faults

**Locations:** [descriptor comment at line 67](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L67), NULL/NOP and zero-fill comments, and [boundary comment at line 732](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L732-L735). **Commit:** [837cc6c](https://github.com/newling/rocjitsu-test-corpus/commit/837cc6cdce92c4499d50acffa39b020ca3b748c7).

Use the [27 July 2026 CDNA5 guide](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf): descriptor fields are in §10.11.4, Tables 62–63; zero-fill and padding are in §10.11.2; tensor bounds and fault handling are in §10.11.6. The older Table 79/80 and §4.10.7 references are stale.

The boundary comment should distinguish continued descriptor processing from successful completion without a fault. Hardware may report MEMVIOL afterward when `LDS_CONFIG.ADDR_OUT_OF_RANGE_REPORTING` is enabled. These tests exercise the emulator with that reporting unmodeled. This clarification also preserves the current store test's decision not to assert the values sourced from outside LDS.

### Exercise unequal and partially overlapping footprints

**Locations:** [pipeline at line 350](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L350), [DS-write→tensor-store at line 432](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L432), and [store→load at line 469](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L469). **Commits:** [bdc31b3](https://github.com/newling/rocjitsu-test-corpus/commit/bdc31b3c74c2a13b81370d9c26d8b112ab804d70), [147e1c4](https://github.com/newling/rocjitsu-test-corpus/commit/147e1c42a7dc0908a75fe90d13d281964efe3348), [9afbcbf](https://github.com/newling/rocjitsu-test-corpus/commit/9afbcbfd36316e717ccbec3aa4a0c2d2267ac5b7).

The basic full-overlap tests are useful controls. Add the following shapes so correctness does not depend on equal starting addresses or equal range lengths:

| Interaction | Proposed shape | What the checks establish |
| --- | --- | --- |
| Partial tensor wait followed by DS reads | Read at byte 64 across the older/newer tile boundary | Lanes 0–15 read completed bytes; lanes 16–31 read pending bytes. Every returned report must name wave 1, a lane in 16–31, and a byte in [128,192). |
| DS writes followed by tensor store | DS writes [60,64), tensor reads [0,128) | A narrow producer still requires its DScnt wait; the valid control checks initialized sentinel values outside that word. |
| DS writes followed by tensor store | DS writes [0,128), tensor reads [60,64) | A narrow consumer still finds the overlapping producer; the valid control checks 115. |
| Tensor store followed by tensor load | [60,64) contained in [0,128), in either role | Strict source/destination containment, with waited data controls and missing-wait races. |
| Tensor store followed by tensor load | [0,128) versus [64,192), in either order | Left/right partial overlap, including a nonzero start for the older source. |

These are additional tensor-specific combinations, not a claim that all older tests require perfect overlap. Existing gfx950 EXEC-mask and dual-offset LDS tests already exercise unequal access sets, and its partial-vmcnt test combines completed and pending register inputs. Keep the final LDS readback in the tensor store→load kernel: it supports the synchronized test's value assertion. Its removal would lose that check.

### Put a real tensor store between two empty stores

**Location:** [empty-store group at lines 603–628](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L603-L628). **Commit:** [5f7a444](https://github.com/newling/rocjitsu-test-corpus/commit/5f7a444fe2a864ced924363f37319403d78ebf6f).

Issue empty→real→empty stores, then overwrite the real store's LDS source. Waiting for TENSORcnt≤1 establishes completion of the real store; waiting for ≤2 can retire only the leading empty store and must leave the overwrite unsafe. The safe control checks the real output and the unchanged global destination of the empty stores. An overwrite of the empty descriptor's nominal LDS source additionally rejects a fictitious read footprint for that empty operation.

A threshold of three after three issues would require no progress. The proposed ≤2 negative is more informative. This sandwich still cannot independently prove that the leading empty instruction counts; keep the existing real-load→empty-store case as a complementary check. The current submission already improved that existing case by overwriting the empty store's nominal source. Longer mixed queues also have precedent in gfx950 scratch/vmcnt tests.

### Fill interleaved stripes from three waves

**Location:** [padding group at lines 686–728](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L686-L728). **Commit:** [d477249](https://github.com/newling/rocjitsu-test-corpus/commit/d4772496ab7bc20d02d86507984983573b71c9a6).

Three waves each copy twelve integers, four at a time, skipping eight dwords between runs, with starting LDS offsets 0, 16, and 32. Their ownership pattern is `000011112222000011112222000011112222`, where each digit denotes the owner of one integer. The byte sets are disjoint even though their bounding intervals overlap.

The safe case has all waves issue, pass a raw barrier, wait for their own transfer, and read their own stripes before the next barrier. Other waves' transfer histories remain unpublished, but cannot conflict with those disjoint reads. A later barrier permits full assembled-data readback. A negative control reads a peer's stripes before that publication and must report a race. Both the per-wave probes and assembled safe output use distinct source values.

A write-only no-race assertion would be weak because LDS write/write detection is missing across architectures. The added reads make footprint precision observable: the bounding-interval mutation produces a false report. Existing gfx950 `buffer_load_lds_kernel` covers two disjoint contiguous writer blocks; this adds repeated padding holes and three writers.

### Cover multi-range instructions and empty gather shapes

**Locations:** [partial waits at line 350](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L350) and [empty instructions at line 540](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L540). **Commits:** [36d08b3](https://github.com/newling/rocjitsu-test-corpus/commit/36d08b3fc10cb33e353e2f56a28646b89f2973e7) and [e6a2f5a](https://github.com/newling/rocjitsu-test-corpus/commit/e6a2f5afeedeb5d3cba4e843e3ff00863076a521).

The multi-iteration case, adapted from the earlier `c4096a1` proposal, issues one tensor instruction with two disjoint LDS ranges alongside a second instruction. Its four controls distinguish whole-instruction retirement from retaining the newest instruction and from mistakenly allocating extra counter tokens per iteration/range. This directly exercises #14687's one-event-per-instruction contract through real HIP assembly.

#14688 also accepts empty gathers, while the submitted HIP cases cover NULL and dense zero-width tiles. Add gathers with zero valid row indices and, separately, zero row width with nonzero valid-index count. Each shape has a TENSORcnt≤1 safe case and a ≤2 missing-progress race control, and the safe cases check that nominal destination LDS remains unchanged. These reuse the existing empty-instruction kernel. They test ordinary NOP accounting without depending on the separately unqualified NULL-counting or NOP-barrier assumptions.

### Retain the useful earlier interaction proposals

**Locations:** [pipeline at line 350](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L350), [tensor-store source at line 392](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L392), and [empty-store handling at line 603](https://github.com/ROCm/rocjitsu-test-corpus/blob/bbf76980b6bbb6fe23f9fc4692af80aaf76c654b/corpus/race/integration/hip_race_gfx1250_test.hip#L603). **Commits:** [7016ecb](https://github.com/newling/rocjitsu-test-corpus/commit/7016ecb0dc2f2bc2bb32a659aea70c509949a431), [9147aaf](https://github.com/newling/rocjitsu-test-corpus/commit/9147aafc7dc2dc991f934f8d4ddc21288d3737ad), [6354e38](https://github.com/newling/rocjitsu-test-corpus/commit/6354e3834b1ed138c5183372a1860bbe28252299).

Three earlier suggestions remain useful and are adapted and revalidated here:

- An older tensor store from A and younger tensor load into B share TENSORcnt. After waiting to one, overwriting A is safe but reading B is not.
- An ordinary async load into LDS must complete on ASYNCcnt before a tensor store reads it. Waiting on TENSORcnt instead does not establish that dependency. This tests the bridge between the pre-existing async path and the new tensor consumer.
- A tensor store of two partially in-bounds rows reads only the valid portions of its LDS source. DS writes into a skipped portion are safe, while writes to neighboring actual source data race. This complements load-side padding and the all-empty store with partial store-side omission.

## Reconciliation with the earlier review

The earlier file remains unchanged as a published historical artifact. This review supersedes its recommendations where the two disagree.

| Earlier proposal or comment | Current disposition |
| --- | --- |
| `886c70c`: zero-filled-only consumer | Still needed; adapted here, with a separate full-tile value check. |
| `0b45be4`: unwaited same-wave tensor load→store expected safe | Withdraw that expectation. Completion FIFO does not prove ordered LDS accesses. The current PR already adds a waited safe case and an unwaited race case in this direction. Keep them. |
| `b418c36`: two unwaited overlapping tensor loads, newer data must win | Withdraw the unconditional value assertion. Completion order alone does not guarantee that final value. A no-race result is also inconclusive because WAW detection is absent. An explicit inter-load wait would make the value check meaningful. |
| `72976c1`, `5266850`, `ae3d8a3`, `c4096a1` | Adapted and revalidated in the current branch: mixed FIFO, ordinary async interaction, store holes, and multi-iteration accounting. |
| `80fb61e`: repeated split workgroup barriers with delayed waves | Optional later stress coverage. The current tests already have raw workgroup barriers and missing-wait/missing-barrier controls. This branch prioritizes deterministic footprint tests and does not carry the delay-based scheduling variants forward. |
| `60be4d8`: cross-wave tensor producer and tensor consumer | Still a useful optional extension, particularly after removing its scheduling delays. Existing cross-wave tensor→DS and new same-wave tensor→tensor tests cover its main dependency rules separately; no claim that the composed case is already covered end-to-end. |
| `08f4a0e`: ordinary async-store LDS-source tracker | Still a separate known implementation limitation, now documented in the Systems stack. Keep the old reproducer available; implementing async-store source observation is outside this corpus change. |
| `fb979aa`: LDS-barrier phase tracker | Still a documented detector false positive. The producer's descriptor arrival and consumer phase polling are not understood by the detector. Keep as a follow-up reproducer, with hardware qualification attached. Store-side arrival semantics also need separate qualification. |
| `63396c8`, `ea5cb52`: tensor/gfx950 LDS WAW trackers | Shared existing limitation. Retain their references for follow-up; do not require general WAW support for this PR or mistake a known-gap tracker passing for race detection working. |
| Earlier request to remove sleeps | Partly addressed in the submission; the last call is removed by this branch. |
| Earlier `kElements`/`kSentinel` naming concern | Addressed by `kTileElements`/`kUnwrittenValue`; not requested again. |
| Earlier question about checking the actual error report | Addressed: the tests parse real reports and match normalized fields plus marked instruction substrings. Exact full-message equality is unnecessary here. |
| Earlier same-wave store→load ordering concern | Addressed by the waited/unwaited pair and the separated completion/LDS-ordering model. |

## Commentary and complete kernel audit

The following covers every kernel in the current submission. Test counts refer to that submission, before the optional additions.

| Kernel group | Tests | Assessment |
| --- | ---: | --- |
| `vgpr_loadcnt_kernel` | 2 | Correct LOADcnt dependency. `s_wait_loadcnt` is also present on RDNA4, so it is not uniquely new to gfx1250. The exact compiler-chosen global-store mnemonic is also assumed by gfx950/gfx1151 tests; treat any asm/matcher cleanup as suite-wide work. |
| `tensor_load_same_wave_kernel` | 3 | Correct, missing, and unrelated counter waits distinguish LDS readiness. The read helper's own DScnt wait protects its VGPR result; it cannot repair an earlier missing tensor wait. Existing inspected assembly retained the read and consuming store. |
| `tensor_load_cross_wave_kernel` | 3 | Wait plus barrier is safe; either alone is insufficient. Final cleanup waits cannot repair an earlier peer access. Remove the remaining sleep as described above. |
| `tensor_load_pipeline_kernel` | 2 | Partial waits correctly distinguish the two tiles. The proposed straddling read tests both halves and report location. |
| `tensor_store_source_overwrite_kernel` | 2 | Correct LDS-source lifetime test. The raw barrier alone does not prove that the store has finished reading before the peer overwrites. |
| `tensor_store_after_ds_write_kernel` | 2 | Correct DScnt dependency before tensor consumption. Clarify helper waits and add the proposed containment variants. |
| `tensor_store_then_load_same_wave_kernel` | 2 | Correct waited/unwaited controls; keep data readback. The overlap additions broaden its geometry. |
| `tensor_load_then_store_same_wave_kernel` | 2 | Correct reverse-direction pair on the current head. This supersedes the earlier unwaited-safe proposal. |
| `tensor_load_then_empty_kernel` | 3 | Useful FIFO/accounting checks. The NULL-counting case is explicitly an emulator assumption pending hardware validation; the negative remains racy whether NULL counts or not. Dense NOP and empty gather coverage should remain distinguished from NULL. |
| `tensor_load_then_empty_store_kernel` | 1 | Useful mixed load/empty-store accounting check. The current source also overwrites the nominal empty source to check that no LDS read was registered. |
| `tensor_load_zero_fill_kernel` | 2 | Zero-fill is an actual LDS write. Restrict the peer to that region and retain full-tile value coverage separately. |
| `tensor_load_padding_kernel` | 2 | Padding skips LDS bytes; it does not write zeros. The gap probe at byte 64 is safe, while the data probe at byte 80 is not. All peer lanes read the same selected word. Gap values are intentionally unasserted because the gap is not initialized. |
| `tensor_load_past_lds_allocation_kernel` | 1 | Primarily functional integration coverage for #14689: the valid prefix survives a transfer spanning the allocation boundary. It does not directly prove that every invalid destination byte was dropped. |
| `tensor_store_past_lds_allocation_kernel` | 1 | Also directly relevant to #14689. Checks only the valid prefix 100…115; the invalid LDS source suffix remains unasserted. Retain the fault-reporting qualification. |
| `tensor_load_builtin_kernel` | 1 | Useful compiler integration: ordinary shared-array writes/readback surround the tensor builtin. Initialization synchronization precedes the builtin, so the later explicit tensor wait is still required. |

The stack has three distinct roles: [#14687](https://github.com/ROCm/rocm-systems/pull/14687) observes tensor issues and models their race dependencies; [#14688](https://github.com/ROCm/rocm-systems/pull/14688) accepts/counts instructions that move no data; [#14689](https://github.com/ROCm/rocm-systems/pull/14689) preserves valid transfer bytes across the LDS allocation boundary and clips reported ranges. The two boundary tests belong to that last functional change as well as providing a detector smoke check.

Ordinary DS behavior is relevant context, not another requested change here. CDNA5 §3.3.4.1 specifies preserved in-range store bytes, discarded out-of-range store bytes, zero results for out-of-range loads, alignment-mode-dependent granularity, and separate MEMVIOL reporting. The inspected ordinary DS execution path checks backing capacity without enforcing the workgroup's smaller allocation, including on gfx950. That pre-existing limitation is outside #14689's tensor-specific fix.

Further candidates from the stack are byte-prefix clipping inside a single element, active NOP barrier arrival versus NULL, and counter-capacity backpressure. These remain native/model-level or hardware-qualification work for now: native tests already exercise byte prefixes and NOP descriptor validation; the published guide does not establish every NOP/store barrier behavior; and a wait-immediate encoding alone should not be used as proof of an admission bound. HIP should not encode unqualified assumptions as architectural guarantees. Deferred issue/completion callback timing is best exercised by the existing Systems retry tests, where unavailability can be forced directly.

## Mutation details

For the sensitivity experiment, only `tensor_dma_lds_ranges` in Systems `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h` was changed at `78238be8d02`. The first alteration removes zero-filled writes from observation:

```diff
-    if (lds_bytes == 0 || (state.store_from_lds && !element.in_bounds))
+    if (lds_bytes == 0 || !element.in_bounds)
       continue;
```

The second alteration, immediately before `return ranges`, replaces disjoint runs with their bounding interval:

```cpp
if (!ranges.empty()) {
  const auto end = ranges.back().address + ranges.back().bytes;
  ranges.resize(1);
  ranges.front().bytes = end - ranges.front().address;
}
```

Rebuild the runtime, shared interposer and race plugin together. On the reviewed corpus head, run `tensor_load_zero_fill` and `tensor_load_zero_fill_cross_wave_race`: both pass despite missing zero-fill observation. On the suggestion branch, run those two plus `tensor_load_interleaved_own_stripes` and `tensor_load_interleaved_peer_stripes_race`: the zero-fill race and interleaved safe test fail for the expected reasons; the two controls pass. The zero-fill descriptor has no padding, and the interleaved descriptors have no zero-filled elements, so the two mutations affect separate tested conditions. Restore the function and rebuild before final validation.

The earlier reverse-orientation probe used the sleep-removal proposal on corpus `b078281` with Systems `76fbd15c408`. Its only temporary source change was to insert `asm volatile("s_sleep 4" ::: "memory");` immediately before `tensorLoad(desc)` inside the `if (wave == 0)` block of `tensor_load_cross_wave_kernel`. Running `tensor_load_cross_wave_no_barrier_race` then produced the DS-read→tensor-load orientation and passed the proposed either-direction matcher. This was a deliberate scheduling perturbation to exercise the matcher, not synchronization or a guarantee about hardware scheduling. The sleep was removed from the final proposal.

## Branch, validation and omissions

The suggestion branch ends at [2e5d94b](https://github.com/newling/rocjitsu-test-corpus/commit/2e5d94b8f929bca2d38ef8b25645faa1bd0755ff) and contains the fifteen commits mapped above. It has 21 kernels and 61 tests, retaining all 29 submitted tests and adding 32 cases. Source/config/inventory counts agree. Final validation used the restored, unmodified Systems `78238be8d02`; the temporary mutations were removed and the relevant runtime artifacts rebuilt. The corpus has no configured pre-commit hooks. No full multi-architecture corpus, sanitizer campaign, or hardware run is claimed; gfx1250 is the changed target, and the focused shared-support checks cover the adapter/helper changes.

The earlier published review and proposal branch remain preserved. This branch omits general LDS WAW support, async-store source observation, LDS-barrier synchronization, ordinary DS allocation enforcement, and a PR-description rewrite. The first four are separate emulator features/limitations, ordinary DS is a shared pre-existing behavior, and a description rewrite was not requested. The optional proposals are a selection menu; adopting every additional HIP case is not a prerequisite for taking the two actionable fixes.
