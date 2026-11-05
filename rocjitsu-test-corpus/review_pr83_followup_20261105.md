This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocjitsu-test-corpus#83](https://github.com/ROCm/rocjitsu-test-corpus/pull/83)

**Reviewed head:** [`ed967d41d4d`](https://github.com/ROCm/rocjitsu-test-corpus/commit/ed967d41d4d5c97e5e547bd5554660457ef55a2d), 2026-11-05, base `develop` at `86181748e9`. Follow-up review after the author's re-request. It checks the current head independently and accounts for every earlier review, inline thread and reply: the 2026-11-03 review, a second reviewer's 2026-11-04 review, the [2026-11-04 walkthrough review](https://github.com/newling/agent-public-reviews/blob/main/rocjitsu-test-corpus/review_pr83_walkthrough_20261104.md) and its posted inline comments, and the overview of the remaining suggestion commits.

**Suggestion branch:** [review/pr83-followup-20261105](https://github.com/newling/rocjitsu-test-corpus/tree/review/pr83-followup-20261105), based directly on the reviewed head. [Combined changes](https://github.com/newling/rocjitsu-test-corpus/compare/ed967d41d4d5c97e5e547bd5554660457ef55a2d...32d2547153098ae9ace2ba03784e5c440c41de2a).

| Commit | Change | Item |
| --- | --- | --- |
| [420dfe0](https://github.com/newling/rocjitsu-test-corpus/commit/420dfe0f27ebf97cab1531385d740288dee2f920) | Rename the expectations with the neighboring suites' `…RaceExpectation` suffix and name the VGPR expectation | Outstanding naming requests |
| [67df059](https://github.com/newling/rocjitsu-test-corpus/commit/67df059390d7e21fdf1d8c77756073c0dc63c5dc) | Rename `Wait`/`Sync` to `WaitMode`/`SyncMode` | Outstanding naming requests |
| [1bed2ee](https://github.com/newling/rocjitsu-test-corpus/commit/1bed2ee21e5aca8a1df9aa6816a486c5518ecb71) | Add `kElementBytes` and use it for tile sizes and per-element LDS offsets | Outstanding naming requests |
| [93ae907](https://github.com/newling/rocjitsu-test-corpus/commit/93ae9078369ed601f0e6ea056b47fcd613fb9f13) | Remove a duplicate section header and align trailing comments | Duplicate section header |
| [32d2547](https://github.com/newling/rocjitsu-test-corpus/commit/32d2547153098ae9ace2ba03784e5c440c41de2a) | Describe the added test groups in the README | README coverage paragraph |

## Tests

All 61 gfx1250 cases pass under emulation, both at the reviewed head and on the suggestion branch, against rocm-systems `develop` at [`a757bf71a82`](https://github.com/ROCm/rocm-systems/commit/a757bf71a82). That commit is the merge of #14689 and contains the merged #14687 and #14688. Matcher tests pass 24/24, including the three new alternative-matching tests. The adapter and inventory tests pass 123/123, and the HIP support tests pass 7/7. Whitespace checks pass. The emulator, shared interposer and race plugin were built together in Release with Clang 23; the HIP tests use the corpus SDK's AMD Clang. Hardware validation is not claimed.

The two observation mutations from the previous review were repeated against the reworked tests. The first stops recording zero-filled LDS writes; the second records each transfer as one solid interval instead of its separate runs. With both applied, three cases fail as intended: `tensor_load_zero_fill_cross_wave_race` ("expected at least one race, got none"), `tensor_store_holes` (false race) and `tensor_load_padding_interleaved_stripes` (false race). Their controls `tensor_load_zero_fill`, `tensor_load_zero_fill_full_tile`, `tensor_store_holes_adjacent_data_race` and `tensor_load_padding_peer_stripe_race` still pass. The mutation is reproduced in the appendix and was reverted before the final runs.

The new tests add little compile or run time. These were measured at the reviewed head on a lightly loaded host, with a cold build where noted and no compiler cache:

| Cost | Result |
| --- | --- |
| HIP object compile, 3 runs | 3.1–3.5 s. Same compiler and flags: gfx950 suite 3.0–3.2 s, gfx1151 suite 2.8–3.2 s. |
| Cold build of the gfx1250 program (CMake configure, GoogleTest, compile, link; 4 build jobs) | 6.6 s |
| All 61 cases, one at a time | 20.3 s |
| Each case | 0.31–0.37 s |
| Peak memory per case | 109–119 MB |

Times are nearly uniform across cases, so per-process startup dominates rather than the emulated work. Memory stays small even with the full `gfx1250_mi455x` topology, so the race target can use that config without the reduced topology the gfx950 race tests use. Runtimes were not compared with the other suites.

## Summary

The PR now covers each interaction that gfx1250 tensor DMA adds to LDS race detection. Within a wave, overlapping transfers require a TENSORcnt wait, and so do DS accesses to their LDS. Across waves, the issuing wave's wait and a barrier are both required. Partial waits retire whole instructions in issue order, including iterated, NULL, NOP, empty-gather and out-of-tensor transfers. The detector tracks the exact LDS footprint: zero-fill is written, padding and a store's out-of-tensor elements are skipped, and bytes past the LDS allocation are dropped. Every safe case checks the data it moved, and every race case names the conflicting instructions.

The author adopted all the walkthrough suggestions and improved several of them:

- The either-direction matcher is now a tested shared helper (`matchAnyRaceExpectation`, `ExpectAnyRace`).
- The containment and partial-overlap cases assert that each report is at the first byte the two transfers share. This matches the detector's documented choice of reporting the lowest shared byte.
- The same-wave footprint table reads back all of LDS rather than only the loaded tile.
- The one-word tensor store checks that the rest of the output keeps its sentinel.
- The empty/real/empty store sequence uses one tile, so the trailing pending empty store itself shows that no LDS read was recorded.

The new ISA citations (§10.11.1, §10.11.3, §10.8 for ordering; §10.11.2/§10.11.6 for zero-fill; §10.11.6 for MEMVIOL) match the July 2026 CDNA5 guide.

What remains is small: three naming requests from the second reviewer that received neither a change nor a reply, a stale test plan, and the rocm-systems work needed for these tests to run in CI.

## Actionable items

### Apply or answer the outstanding naming requests

**Locations:** [expectations at lines 159–213 and 248](https://github.com/ROCm/rocjitsu-test-corpus/blob/ed967d41d4d5c97e5e547bd5554660457ef55a2d/corpus/race/integration/hip_race_gfx1250_test.hip#L159-L213), [`Wait` at line 256](https://github.com/ROCm/rocjitsu-test-corpus/blob/ed967d41d4d5c97e5e547bd5554660457ef55a2d/corpus/race/integration/hip_race_gfx1250_test.hip#L256), [`Sync` at line 303](https://github.com/ROCm/rocjitsu-test-corpus/blob/ed967d41d4d5c97e5e547bd5554660457ef55a2d/corpus/race/integration/hip_race_gfx1250_test.hip#L303), [`kTileBytes` at line 47](https://github.com/ROCm/rocjitsu-test-corpus/blob/ed967d41d4d5c97e5e547bd5554660457ef55a2d/corpus/race/integration/hip_race_gfx1250_test.hip#L47). **Commits:** [420dfe0](https://github.com/newling/rocjitsu-test-corpus/commit/420dfe0f27ebf97cab1531385d740288dee2f920), [67df059](https://github.com/newling/rocjitsu-test-corpus/commit/67df059390d7e21fdf1d8c77756073c0dc63c5dc), [1bed2ee](https://github.com/newling/rocjitsu-test-corpus/commit/1bed2ee21e5aca8a1df9aa6816a486c5518ecb71).

The [2026-11-04 review body](https://github.com/ROCm/rocjitsu-test-corpus/pull/83#pullrequestreview-5762252836) asked for three renames. These requests were in the review body rather than inline threads, which may be why they were missed. Every other item from that review is addressed at this head.

- **`…RaceExpectation` suffix:** the gfx950 and gfx1151 suites name their expectations this way, for example `kVgprWaitcntRaceExpectation` and `kLdsWave32CrossWaveRaceExpectation`. [420dfe0](https://github.com/newling/rocjitsu-test-corpus/commit/420dfe0f27ebf97cab1531385d740288dee2f920) renames the seven gfx1250 constants accordingly. It also gives the inline VGPR expectation a name, `kVgprLoadcntRaceExpectation`.
- **`WaitMode` and `SyncMode`:** [67df059](https://github.com/newling/rocjitsu-test-corpus/commit/67df059390d7e21fdf1d8c77756073c0dc63c5dc) renames the enums so that `template <WaitMode Mode>` states what the argument selects.
- **`kElementBytes`:** [1bed2ee](https://github.com/newling/rocjitsu-test-corpus/commit/1bed2ee21e5aca8a1df9aa6816a486c5518ecb71) defines `kElementBytes` once, derives `kTileBytes` from it, and uses it for every per-element LDS offset that previously multiplied by a literal 4. `firstSharedByte` now uses `std::max`, so the file includes `<algorithm>` directly.

These commits change only names and spelling. All 61 cases pass unchanged. If the author prefers the current names, a short reply in the review thread would close the requests instead.

### Update the test plan to the merged rocm-systems revision

The description still says the tests pass against the pre-merge #14689 head `78238be8d02` and "once the full stack … is merged". All three rocm-systems PRs merged on 2026-11-05. The 61 cases pass against the merge commit. Suggested replacement for the Test Plan and Test Result sections:

> All 61 gfx1250 cases pass under emulation against rocm-systems `develop` at `a757bf71a82`, which contains the merged tensor-DMA stack (#14687, #14688, #14689). The matcher, adapter and HIP support tests also pass. The corpus repository's own CI runs only security scans, so these results come from local runs.

## Suggestions

### Duplicate section header

**Location:** [line 513](https://github.com/ROCm/rocjitsu-test-corpus/blob/ed967d41d4d5c97e5e547bd5554660457ef55a2d/corpus/race/integration/hip_race_gfx1250_test.hip#L513). **Commit:** [93ae907](https://github.com/newling/rocjitsu-test-corpus/commit/93ae9078369ed601f0e6ea056b47fcd613fb9f13).

`// --- LDS addresses past the workgroup's allocation ---` appears twice. One copy sits directly above `// --- A tensor store's LDS source ---`, left over from moving the iteration group; the real section starts at line 1421. The commit removes the stray copy and realigns the trailing comments in `Tile` and `describe()`.

### README coverage paragraph

**Location:** [README.md lines 136–145](https://github.com/ROCm/rocjitsu-test-corpus/blob/ed967d41d4d5c97e5e547bd5554660457ef55a2d/README.md#L136-L145). **Commit:** [32d2547](https://github.com/newling/rocjitsu-test-corpus/commit/32d2547153098ae9ace2ba03784e5c440c41de2a).

The paragraph was written before the later groups were added. It says each race case removes a TENSORcnt wait, a barrier, a DS wait or a pipeline transfer. Some newer race cases do something else: they replace the ASYNCcnt wait with a TENSORcnt wait, omit the wait between overlapping same-wave tensor transfers, or read a peer's stripe. The paragraph also omits iterated instructions, empty gathers and store holes. The commit adds those without lengthening the paragraph much.

## Scope decisions

### Running these tests in rocm-systems CI

rocm-systems pins this corpus by SHA (`ROCJITSU_DBT_CORPUS_REF` in `rocjitsu-corpus-tests.yml`). Its race runner, `emulation/rocjitsu/tests/corpus/run-corpus-tests.sh`, lists only gfx942, gfx950 and gfx1151 in `race_targets`. Merging this PR and moving the pin is therefore not enough to run the gfx1250 cases in CI. A rocm-systems change also needs to add the gfx1250 race target with `configs/gfx1250_mi455x.json`, which is the config the README now names. This belongs in that companion change, not this PR. Suggested text:

> After this merges, a rocm-systems follow-up moves the corpus pin to the merge commit and adds gfx1250 to the race targets in `tests/corpus/run-corpus-tests.sh`, so these cases run against every rocjitsu change.

### Compiler-selected output store

In the 2026-11-04 thread on line 251, the reviewer called this a follow-up cleanup rather than a request for this PR. The author has since preferred option (a), writing the output with inline asm too. In this file only `vgpr_loadcnt_race` depends on the compiler's choice of store; every other producer and consumer is explicit asm. The gfx950 and gfx1151 suites share the pattern, so a suite-wide follow-up remains the right scope. No commit is included.

## Commentary: earlier requests at this head

| Earlier request | Status at `ed967d4` |
| --- | --- |
| Remove `s_sleep` (2026-11-03 review and inline thread) | Done. Barriers replace every sleep that a barrier can replace; the no-barrier case accepts either report direction through `ExpectAnyRace`. |
| `kElements`/`kSentinel` naming | Done: `kTileElements`, `kUnwrittenValue`. |
| Check the actual report | Answered: reports are parsed and matched on type, access, instruction and count; several cases now also check the reported byte. |
| Same-wave store→load ordering | Done. Both directions require a TENSORcnt wait, with the ordering explained and the ISA cited above the kernels. |
| Header comment too specific for future gfx1250 tests | Deferred by that reviewer. The header now names both covered areas. |
| Restrict zero-fill race reads to zero-filled bytes | Done; mutation-checked above. |
| July 2026 ISA references; MEMVIOL qualification | Done. |
| NULL counting labeled as an assumption (source and README) | Done. |
| Overwrite the empty store's LDS source | Done in `tensor_store_outside_tensor_counts`, and implied again by the single-tile empty/real/empty case. |
| `allocFilled`/`ExpectValues` in `RaceTestBase`; `itertools.permutations`; per-target sources in `TARGET_LAYOUT` | Done. |
| `…RaceExpectation`, `WaitMode`/`SyncMode`, `kElementBytes` | Not addressed; see the actionable item. |
| Record the passing rocm-systems SHA | Recorded for the pre-merge head; update it as described above. |
| Walkthrough suggestions: sleep removal, empty-store sandwich, zero-fill isolation, helper names, ISA/MEMVIOL, straddling read, DS/tensor containment, tensor footprints, interleaved stripes | All adopted, several strengthened as described in the summary. |
| Overview groups: iterations with documentation, empty gathers, mixed FIFO, async-load→tensor-store, store holes | All adopted. |
| Compiler-selected output store | Follow-up; see scope decisions. |

## Appendix: observation mutation

This change was applied temporarily to `tensor_dma_lds_ranges` in rocm-systems `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h` at `a757bf71a82`. The emulator, shared interposer and race plugin were then rebuilt:

```diff
-    if (lds_bytes == 0 || (state.store_from_lds && !element.in_bounds))
+    if (lds_bytes == 0 || !element.in_bounds)
       continue;
@@
+  if (!ranges.empty()) {
+    const auto end = ranges.back().address + ranges.back().bytes;
+    ranges.resize(1);
+    ranges.front().bytes = end - ranges.front().address;
+  }
   return ranges;
```

The first hunk stops recording zero-filled load bytes. The second records each transfer as one interval from its first byte to its last, filling the gaps. The zero-fill descriptors have no padding or holes, and the padded and store-hole descriptors have no zero-filled elements, so each failing case isolates one mutation.

## Branch, validation and omissions

The [suggestion branch](https://github.com/newling/rocjitsu-test-corpus/tree/review/pr83-followup-20261105) adds the five commits above to `ed967d4`. They change names, comments and the README only; test behavior and the 61-case inventory are unchanged. No hardware, multi-architecture or sanitizer run is claimed. The PR description is not rewritten here; only the test-plan paragraph above is suggested. The rocm-systems CI change is a companion task outside this repository.
