This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#16020](https://github.com/ROCm/rocm-systems/pull/16020)

**Reviewed head:** `ce03b0dc1913a03e31b7040029476d119510a6f3`

**Base:** `6824b1e09cfcc45d2f962602d940469e746698db`, the approved [plugin-hook prerequisite #16232](https://github.com/ROCm/rocm-systems/pull/16232).

**Mode and scope:** Full independent review of all 13 files in the detector-only diff: eight production files, four test/helper files, and the race-detector documentation. Existing reviews and discussion were explicitly requested and were read, including the prerequisite's published agent review. The simulator's hook contracts and execution paths were inspected where the detector depends on them. This review does not reopen optional prerequisite changes.

**Suggestion branch:** [review/pr16020-suggestions](https://github.com/newling/rocm-systems/tree/review/pr16020-suggestions), based directly on the reviewed head. [cd45db5359f](https://github.com/newling/rocm-systems/commit/cd45db5359ff79dd378ed938a80d192c53b4e7b9) implements actionable item 1; [70e83c42b69](https://github.com/newling/rocm-systems/commit/70e83c42b699f5a0f5e461cb2359fe73bbe7a799) implements suggestion 1; [faccc147570](https://github.com/newling/rocm-systems/commit/faccc147570d9ea4a10bcc4e34ee018d05e91edb) implements suggestion 3. [Compare all three suggestions against the reviewed head](https://github.com/newling/rocm-systems/compare/ce03b0dc1913a03e31b7040029476d119510a6f3...faccc147570d9ea4a10bcc4e34ee018d05e91edb).

## Tests

The full native test executable and runtime/plugin targets build with Clang 23.1, Release/NDEBUG, and Ninja. The relevant native selection passed **1,290 tests on the submitted head and 1,292 with the suggestions**, with the same 133 architecture/capability skips. The selection includes all 41 new core split-barrier tests and all nine new plugin tests; the suggestions add two regressions. The existing local configuration has `-Wno-error=unused-template` for unrelated Clang 23 warnings; no source warning policy was changed. This is a focused test run, not a claim that every test in the executable was run. Runtime validation of the suggestions is at [70e83c42b69](https://github.com/newling/rocm-systems/commit/70e83c42b699f5a0f5e461cb2359fe73bbe7a799); the final include-only commit passed a standalone header compile exercising equality and ordering.

At both revisions, **59 of 64 selected gfx1250 HIP tests passed**, and exactly the same five known investigation assertions failed: three LEAVE handoffs, one arrival-count polling handoff, and the missing KMcnt query-result hazard. All 22 cases added by [corpus PR #96](https://github.com/ROCm/rocjitsu-test-corpus/pull/96) passed their programmed expectations. The selection also includes two pre-existing split-barrier tests and all 40 cases on [the named-barrier investigation branch](https://github.com/ROCm/rocjitsu-test-corpus/tree/tests/gfx1250-named-barriers), pinned to `9af805d270b31b78a90c5b4a6547952ae771a4c2`. These were fresh-process functional-emulation runs with O2 HIP code, the required race plugin, `gfx1250_mi455x.json`, and two CPU workers; no hardware run is claimed.

An independent reference probe represents ordering as sets of individual completed accesses, without epochs, coverage minima, or retirement. Both implementations agreed with **407,418 access checks over 100 deterministic seeds and 500 actions per seed**, including RAW/WAR, signals before completion, repeated signals, three named channels, partial waits, old completion bits, JOIN/INIT, transitive handoffs, workgroup synchronization, and exits. The same probe passed with assertions plus ASan/UBSan instrumenting the detector core at both revisions. This checks the explicit signal/wait model; it is not an exhaustive ISA or schedule proof. Focused checks and the HIP runs found no additional functional regression.

The reviewed head's rocjitsu Release, ASan/UBSan, GCC UBSan, TSan, and pre-commit CI checks passed when inspected. The unrelated multi-architecture summary had failures in MIOpen jobs; it was not treated as a detector finding. All 13 reviewed files passed local pre-commit and whitespace checks with the suggestions.

## Summary

The split leaves the right responsibility in each layer. The prerequisite reports the signals that actually counted, the waves whose completion bits were armed, and the individual waits that passed. This PR consumes those facts to distinguish memory completion, release, acquisition, and retirement. No simulator production file is changed by this PR.

The vector-clock model handles cases that a global flush cannot: a consumer waiting before the producer waits, a consumer that still holds an older completion bit, relays between named barriers, and events that must remain visible to an uninvolved wave. Stamping an event when its **LDS access** completes also preserves the separate VGPR obligation of a partially completed FLAT operation. The exit path retains the distinction between work completed before a counted signal and work completed only when the wave ends.

The remaining issue is validation cost for multiple independent communicating groups. Skipping acquired epochs fixes the earlier one-pair example, but unrelated unacquired histories can still make an entirely ordered kernel quadratic. A small conservative range check addresses the concrete case below without changing release/acquire rules or deleting history.

## Actionable items

### 1. Skip disjoint histories when independent groups exchange LDS data

At [`core/race_detector.cpp:356`](https://github.com/ROCm/rocm-systems/blob/ce03b0dc1913a03e31b7040029476d119510a6f3/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp#L356), `forEachUnacquiredLdsEvent()` visits the unacquired suffix of **every other wave's** history. The chunk-count fast path does not prevent this once the queried tile has accesses from the current pair.

Consider four waves, with waves 0/1 joined to named barrier 1 and waves 2/3 joined to named barrier 2, both with threshold two. Each pair repeatedly performs:

```text
producer: LDS write to its pair's tile; s_wait_dscnt 0
both:     s_barrier_signal <pair>; s_barrier_wait <pair>
consumer: LDS read from that tile; s_wait_dscnt 0
both:     s_barrier_signal <pair>; s_barrier_wait <pair>
```

The two tiles are disjoint. Each pair orders its own producer/consumer accesses, while neither pair acquires the other's history. That history must remain available for a possible later cross-pair access, but scanning it for a disjoint tile cannot find a conflict. Currently each new access scans an increasingly long irrelevant suffix, producing O(N²) total validation work over N iterations.

This is a regression relative to the approved hook base, whose existing named-barrier callback retires the participating waves' completed events. The new retention is needed for correctness; the proposed change skips work that cannot affect the result while preserving that retention.

Detector-core measurements, seconds per timed loop, medians of five fresh-process runs:

| Workload | Iterations | Approved base | Submitted PR | With range check |
| --- | ---: | ---: | ---: | ---: |
| One pair, one idle outsider | 16,000 | 0.008873 | 0.015084 | 0.019407 |
| Two independent pairs | 4,000 | 0.004417 | 0.640711 | 0.007966 |
| Two independent pairs | 8,000 | 0.006934 | 2.824345 | 0.016652 |
| Two independent pairs | 16,000 | 0.015625 | 12.605276 | 0.034933 |

The repeated growth and source path establish the problem; these are synthetic core costs, not GPU throughput or a whole-program speedup claim. The one-pair result is a control for the history-skip behavior already fixed in this PR. Individual timings and the exact reproducer are below.

**Implemented in [cd45db5359f](https://github.com/newling/rocm-systems/commit/cd45db5359ff79dd378ed938a80d192c53b4e7b9).** Keep one conservative LDS address envelope per wave's retained history and bypass histories whose envelope cannot overlap the access. This adds two integer bounds per wave, with no per-byte or per-event index. Bounds expand as completed events are queued and reset when starting a new empty history. They may remain wider than necessary after partial retirement, which only admits extra scanning. The existing epoch check still selects the unacquired suffix.

The two added tests preserve later cross-pair RAW/WAR reports, check both ends of disjoint transfer intervals, and check a new operand-read history after retirement. The existing acquired/unacquired and sparse-registry tests also pass. The submitted probe serves as the performance counterexample; the suggested implementation changes its scaling while all access expectations remain the same.

## Suggestions

### 1. Describe the detector's direct handoff rule and the actual epoch boundary

At [`docs/race-detector.md:392`](https://github.com/ROCm/rocm-systems/blob/ce03b0dc1913a03e31b7040029476d119510a6f3/emulation/rocjitsu/docs/race-detector.md#L392) and [`core/race_detector.h:35`](https://github.com/ROCm/rocm-systems/blob/ce03b0dc1913a03e31b7040029476d119510a6f3/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.h#L35), “only when” reads as a universal ISA rule requiring the producer's own signal and the consumer's own wait. The implementation also supports transitive handoffs and termination, and additional hardware protocols are outside this model. Introduce the two bullets as the detector's **direct** handoff rule, then explain transitive acquisition as the text already does.

The header should say that the epoch is recorded when the LDS access completes; the full event can still have a pending register result. At [`core/race_detector.cpp:202`](https://github.com/ROCm/rocm-systems/blob/ce03b0dc1913a03e31b7040029476d119510a6f3/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp#L202), remove INIT from the operations said to clear the wave's completion bit. INIT discards counted signals and advances the generation; JOIN/LEAVE clear the bit. The simulator and [CDNA5 ISA, 27 July 2026](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf), §5.6/Table 22, agree on that distinction.

**Implemented in [70e83c42b69](https://github.com/newling/rocm-systems/commit/70e83c42b699f5a0f5e461cb2359fe73bbe7a799)**, including the matching test introduction and a short clarification that RDNA4 also reaches this signal/wait model. No synchronization behavior is changed.

### 2. Refresh the PR description after the split

The current description still has `TODO: <hooks PR link>`, links the closed counter-capacity issue #15036 instead of the split-barrier issue **#15037**, and says RDNA4 runs the wait as a single-instruction barrier. The actual base is **#16232**, and RDNA4 uses the shared split signal/wait path. Its “at most 32” architectural explanation and later “at most 64” implementation limit should also be distinguished.

Qualify the claim that every wait costs O(waves): `acquire()` can cause `recomputeCoverage()` to scan the other waves for multiple owners when the last holders of their minima advance. The incremental minimum avoids those rescans on most waits, but a particular wait can still do O(waves²) coverage work, in addition to retiring events. The description can explain that bounded tradeoff directly.

The existing performance table compares against the revision before the hooks; it already labels that combined-stack comparison correctly. Keep that distinction when adding results for the detector-only diff. No replacement description or remote edit was made.

### 3. Include comparison support directly

At [`core/types.h:53`](https://github.com/ROCm/rocm-systems/blob/ce03b0dc1913a03e31b7040029476d119510a6f3/emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/types.h#L53), the new defaulted three-way comparison depends on `<compare>`. Add the owning standard header rather than obtaining it through another include. **Implemented in [faccc147570](https://github.com/newling/rocm-systems/commit/faccc147570d9ea4a10bcc4e34ee018d05e91edb)** and checked by compiling the header on its own. This is dependency hygiene, not a demonstrated build failure.

## Scope decisions

[#16236](https://github.com/ROCm/rocm-systems/issues/16236) tracks polling/flag handoffs, and [#16237](https://github.com/ROCm/rocm-systems/issues/16237) tracks LEAVE ordering. They remain follow-up enhancements, not requirements for this PR. The corpus's two flag-forced expected reports are evidence of the detector's current boundary, not independent proof that those complete programs race. The separately documented missing KMcnt query-result hazard is also pre-existing.

General history compression remains separate. The suggested envelope is deliberately conservative: interleaved footprints or a retained history spanning both tiles can still need the slow scan. It solves the demonstrated disjoint-tile regression without requiring a new per-byte history representation. Events that outsiders may race with remain retained, so this is not a reduction in the model's synchronization coverage.

## Commentary

### Disposition of previous reviews

| Earlier request | Current disposition |
| --- | --- |
| [Rejoining a named barrier retains abandoned rounds](https://github.com/ROCm/rocm-systems/pull/16020#discussion_r4606626904) | Addressed: a newly armed bit removes that wave's older completed obligations without acquiring them. The repeated-rejoin and peer-keeps-old-wait tests are present and pass. |
| [Skip history the accessor has acquired](https://github.com/ROCm/rocm-systems/pull/16020#discussion_r4613511971) | Addressed for the reported one-pair/outsider case: completed events are in owner/epoch order and validation stops at the acquired prefix. The outsider still sees all retained conflicts. Actionable item 1 is the further case with two independently active groups. |
| [Actually exercise a duplicate cluster signal](https://github.com/ROCm/rocm-systems/pull/16020#discussion_r4613511982) | Addressed in the prerequisite: both waves of the first workgroup signal before the other workgroup, and the test requires two counted callbacks and all four waits. |
| [Correct barrier-callback threading documentation](https://github.com/ROCm/rocm-systems/pull/16020#discussion_r4630153532) | Addressed in the prerequisite: `docs/plugins.md` distinguishes the completion lock from the optional hot-hook lock on signal/wait. |
| [Distinguish notified, armed, and passed waits](https://github.com/ROCm/rocm-systems/pull/16020#pullrequestreview-5976913038) | Addressed across the hook docs and detector/test-builder `armed` parameter. The older completion bit acquires only its original round. |
| [Separate simulator hooks from detector changes](https://github.com/ROCm/rocm-systems/pull/16020#issuecomment-6995827320) | Addressed: this diff is exactly one detector commit on the hook PR, with no simulator production changes. |

The [published prerequisite review](https://github.com/newling/agent-public-reviews/blob/1c5a002472f159a563e6661422bd6c55c74f0917/rocm-systems/review_pr16232.md) contains optional legacy-vector and documentation improvements; those remain matters for that approved PR. Its later suggestion to test the next cluster generation after a peer exits is likewise a prerequisite test improvement, not an established defect introduced here.

### Measurement details

All core measurements used Clang 23.1, `-O3 -DNDEBUG -march=x86-64-v3`, one host thread, one lane's DWORD per pair, and the same inputs. Each sample used a fresh process; the timer surrounds the loop, excluding construction and destruction. There was no separate per-sample warm-up. The three revisions ran in rotated order within each repetition. The host was shared and busy. The short one-pair runs vary substantially, with both faster and slower suggestion samples; they establish neither performance parity nor a reliable gain or loss. The envelope adds a constant range check to this path, so representative application measurements remain necessary before making a general performance claim. The large two-pair effect repeats in every run and is supported by the O(N²) scan path.

B = approved hook base, P = submitted detector PR, S = suggested range check. The base probe uses the old per-member named-barrier retirement callback; P/S use counted signals, completion and waits. Every timed run reports zero races.

<details>
<summary>Individual timings in seconds</summary>

**1 pair(s), 16,000 iterations**

| | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Order | B → P → S | P → S → B | S → B → P | B → P → S | P → S → B |
| B | 0.009070 | 0.009022 | 0.007664 | 0.008873 | 0.008300 |
| P | 0.020463 | 0.019534 | 0.015084 | 0.013859 | 0.014124 |
| S | 0.019646 | 0.014610 | 0.024931 | 0.019407 | 0.015789 |

**2 pair(s), 4,000 iterations**

| | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Order | B → P → S | P → S → B | S → B → P | B → P → S | P → S → B |
| B | 0.004498 | 0.003615 | 0.004417 | 0.003523 | 0.004459 |
| P | 0.584147 | 0.718091 | 0.577803 | 0.640711 | 0.726816 |
| S | 0.007236 | 0.007966 | 0.008972 | 0.009018 | 0.007307 |

**2 pair(s), 8,000 iterations**

| | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Order | B → P → S | P → S → B | S → B → P | B → P → S | P → S → B |
| B | 0.007058 | 0.008703 | 0.006934 | 0.006269 | 0.006682 |
| P | 2.803798 | 2.824345 | 2.595584 | 2.919118 | 2.915303 |
| S | 0.018266 | 0.016652 | 0.017913 | 0.012389 | 0.013626 |

**2 pair(s), 16,000 iterations**

| | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Order | B → P → S | P → S → B | S → B → P | B → P → S | P → S → B |
| B | 0.019565 | 0.014938 | 0.015625 | 0.017064 | 0.012914 |
| P | 13.826346 | 13.411543 | 11.683569 | 12.605276 | 11.782753 |
| S | 0.035525 | 0.029478 | 0.034933 | 0.035011 | 0.026355 |

</details>

### Reproducing the performance case

Save the following as `probe.cpp`. The first argument selects one pair plus an idle outsider, or two independent pairs; the second selects the iteration count. The test builder drives the production detector and counter-completion code without simulating GPU instruction execution.

```cpp
#include "race-detector/race_test_builder.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>
using namespace rocjitsu;
using namespace rocjitsu::plugins::race_detector;

void drain(RaceTestBuilder &b, int wave) {
  PendingWaitCount wait;
  wait.add(amdgpu::WaitCounterType::DSCNT, 0);
  const_cast<RaceDetector &>(b.detector()).getWaveRaceState(wave).dispatch(wait);
}

void exchange(RaceTestBuilder &b, int pair, uint64_t generation) {
#ifdef REVIEW_BASE
  (void)generation;
  auto &detector = const_cast<RaceDetector &>(b.detector());
  detector.getWaveRaceState(pair * 2).flushBarrierPendingEvents();
  detector.getWaveRaceState(pair * 2 + 1).flushBarrierPendingEvents();
#else
  const auto round = RaceTestBuilder::namedRound(pair + 1, generation);
  b.signal(pair * 2, round);
  b.signal(pair * 2 + 1, round);
  b.completeRound(round, {pair * 2, pair * 2 + 1});
  b.waitPassed(pair * 2, round);
  b.waitPassed(pair * 2 + 1, round);
#endif
}

int main(int argc, char **argv) {
  if (argc != 3) return 2;
  const int pairs = std::atoi(argv[1]);
  const int iterations = std::atoi(argv[2]);
  RaceTestBuilder b(pairs == 1 ? 3 : 4, 8, 8, 32);
  const auto start = std::chrono::steady_clock::now();
  for (int index = 0; index < iterations; ++index) {
    for (int pair = 0; pair < pairs; ++pair) {
      const int writer = 2 * pair, reader = writer + 1, address = 64 + 64 * pair;
      b.ldsWrite(writer, 0, address, 4, MemoryOrderClass::LDS, amdgpu::WaitCounterType::DSCNT);
      drain(b, writer);
      exchange(b, pair, 2 * index);
      b.ldsRead(reader, 0, address, 4, 1, 0xf, amdgpu::WaitCounterType::DSCNT);
      drain(b, reader);
      exchange(b, pair, 2 * index + 1);
    }
  }
  const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
  std::printf("pairs=%d iterations=%d seconds=%.6f races=%d\n", pairs, iterations, seconds, b.raceCount());
  return b.raceCount() != 0;
}
```

Save the following as `build-probe.sh`. It compiles the core sources from the selected checkout, using GoogleTest from an existing rocjitsu build. That build must already have built `rocjitsu_tests`. The source-directory argument points to `emulation/rocjitsu`, and the output belongs outside the source checkout.

```bash
#!/usr/bin/env bash
set -eu
rj_review_source=${1:?Pass the emulation/rocjitsu source directory}
rj_review_build=${2:?Pass its configured build directory}
rj_review_probe=${3:?Pass probe.cpp}
rj_review_output=${4:?Pass the output executable path}
"${CXX:-clang++}" -std=c++20 -O3 -DNDEBUG -march=x86-64-v3 \
  -I"$rj_review_source/tests" \
  -I"$rj_review_source/lib/rocjitsu/include" \
  -I"$rj_review_source/lib/rocjitsu/src" \
  -I"$rj_review_source/lib/util/include" \
  -I"$rj_review_source/lib/arith/include" \
  -I"$rj_review_source/lib/simdojo/include" \
  -I"$rj_review_source/../../runtimes/api-headers/include" \
  -I"$rj_review_build/generated" \
  -I"$rj_review_build/_deps/googletest-src/googletest/include" \
  "$rj_review_probe" \
  "$rj_review_source/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp" \
  "$rj_review_source/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp" \
  "$rj_review_source/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/wait_counter_policy.cpp" \
  "$rj_review_build/lib/libgtest.a" -pthread -o "$rj_review_output"
```

For example:

```bash
CXX=clang++ bash build-probe.sh "$RJ_SRC" "$BUILD_DIR" probe.cpp "$BUILD_DIR/barrier-probe"
"$BUILD_DIR/barrier-probe" 2 4000
"$BUILD_DIR/barrier-probe" 2 8000
"$BUILD_DIR/barrier-probe" 2 16000
"$BUILD_DIR/barrier-probe" 1 16000
```

This recipe was compiled against the suggestion checkout. For the approved base, add `-DREVIEW_BASE` to the compiler invocation; the conditional code uses that revision's old callback API. The original comparison used exact core/header snapshots of each revision, with the same compiler and dependencies.

The [suggestion branch](https://github.com/newling/rocm-systems/tree/review/pr16020-suggestions) contains the bounded performance fix, documentation clarification, and comparison-header cleanup as separate commits. No simulator or general history-compression implementation is included. The validation limits above apply to the review and the suggested changes.
