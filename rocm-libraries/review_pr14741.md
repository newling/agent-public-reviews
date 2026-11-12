This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14741](https://github.com/ROCm/rocm-libraries/pull/14741)

Reviewed head: `362fae1d3e55e23f8ca47b7a53815a6ea5b9b29a`. Base and merge base: `aca3d5cef647336e7eac6e63a51a606d2e14deb2`.

Mode: follow-up review, including the previous reviews and replies, the complete current batching/subprocess diff, capability equivalence, and probing cost. Suggestion branch: [review/pr14741-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14741-suggestions), based on the reviewed head, ending at [698a24b9b90](https://github.com/newling/rocm-libraries/commit/698a24b9b90e5a1562dd9cadf14039fb5d97a250). The repository and PR head are public. The [suggestion diff](https://github.com/newling/rocm-libraries/compare/362fae1d3e55e23f8ca47b7a53815a6ea5b9b29a...698a24b9b90e5a1562dd9cadf14039fb5d97a250) compares the reviewed head with all suggestions.

## Tests

Built `_rocisa` with ROCm 7.1's compiler, Python 3.12, Ninja and ccache. With LLVM 23 as the **probed assembler**, the submitted rocisa suite passed (339 passed, 4 skipped); the suggestions passed after the state refactor and test replacement (339 passed, 4 skipped). The final include-only cleanup was rebuilt and passed both `initMany` smoke cases. The stronger SIGHUP case replaces the plain SIGKILL case, keeping the probing file at eight cases. All submitted probing tests ran locally on Linux. The skips concern optional plugin configurations. With ROCm 7.1 as the probed assembler, seven async-store/TDM expectations fail; those same seven failures reproduce on the exact base. Base and submitted assembly-capability tables match for all 24 supported architectures with both assemblers, across three paired runs per assembler. Root pre-commit checks and `git diff --check` pass on the suggestion branch.

A deterministic Win32 API shim compiles the actual Windows `run()` implementation and schedules a final diagnostic between the empty-pipe check and the exit check. On the submitted head, only the first diagnostic is captured; with suggestion [9a91c1eb233](https://github.com/newling/rocm-libraries/commit/9a91c1eb23304dc593b7600ad043f6e903e3ab13), both diagnostics are captured. The original reproduction also exercised the submitted batch parser and observed the last rejected source being accepted. The preserved script now checks output capture directly, so it works with either probe-state design. This is a controlled API-interleaving reproduction on Linux, not native Windows execution. The companion script is preserved in the appendix.

The added SIGHUP case passes with the submitted signal-status conversion and fails when that conversion is removed. Native Windows execution of the suggestions remains unverified locally.

The GitHub check snapshot inspected during this review included successful rocisa Linux/Windows lanes and the Windows hipBLASLt build/test. The rocisa workflow really runs pytest through `pip-install-test`, despite stale wording in `TESTING.md`. That snapshot was not all green: the gfx1250 FFM result reports 265 passes and nine timeouts, the miopen-dbsync job reports a runner/container failure, and coverage/Math CI statuses were unsuccessful or pending. This review has not established the cause of the FFM timeouts or treated those statuses as evidence of a batching defect.

## Summary

rocisa discovers assembler capabilities by trying short instruction sources. The replacement design sends independent sources sharing a command line in one assembler invocation, then uses line-numbered errors to reject the corresponding probes. Repeated passes discover probes reached through conditional expressions. Unattributable output and abnormal exit statuses trigger individual probing. This preserves the existing capability definitions while removing most process launches.

The earlier objection to a persistent home-directory cache is addressed: that cache and its file I/O are gone. The author also supplies a workload-level motivation, reporting about 110 seconds saved, or 16% of a Windows hipBLASLt build. Those figures compare one PR build with baseline medians; they are author-reported evidence, not a repeated Windows comparison performed here. The local measurements below independently support a substantial reduction in probing cost.

One correctness issue remains in the submitted Windows output reader. Batching makes its existing output-loss race affect capability decisions.

## Actionable items

### Drain output written before the child exits

[helper.cpp:191](https://github.com/ROCm/rocm-libraries/blob/362fae1d3e55e23f8ca47b7a53815a6ea5b9b29a/projects/hipblaslt/tensilelite/rocisa/rocisa/src/helper.cpp#L191), consumed by [hardware_caps.hpp:195](https://github.com/ROCm/rocm-libraries/blob/362fae1d3e55e23f8ca47b7a53815a6ea5b9b29a/projects/hipblaslt/tensilelite/rocisa/rocisa/include/hardware_caps.hpp#L195).

`PeekNamedPipe` can report zero available bytes, then the assembler can write its final diagnostic and exit before `WaitForSingleObject(..., 0)` observes the process. The loop immediately breaks and closes the pipe, discarding that output. If an earlier diagnostic was already collected, the batch has exit code 1 and a nonempty set of rejected lines. `answerPendingProbes()` therefore treats it as a complete answer and accepts sources whose diagnostics were lost. That can enable instructions which the assembler rejects. Losing *all* diagnostics happens to invoke the fallback; losing only the tail does not.

The reader predates this PR, but its captured text now decides which instructions are supported. The original reproduction returned `first accepted=0`, `last accepted=1` on the reviewed head even though the child rejected both sources. The preserved transport-level script demonstrates the same loss by printing `first diagnostic captured=1`, `last diagnostic captured=0`.

Fix: **[9a91c1eb233](https://github.com/newling/rocm-libraries/commit/9a91c1eb23304dc593b7600ad043f6e903e3ab13)** records that the child has exited and checks/drains the pipe again before accepting an empty result. It also handles a failed polling wait. The original reproduction then rejects both sources, and the preserved script captures both diagnostics. The commit enables the real-assembler batch-versus-individual comparison on Windows by applying POSIX skips only to tests that need shell scripts or signals; previously all eight new cases were skipped there. That portable comparison provides ordinary Windows coverage, while the API shim specifically demonstrates the race.

## Suggestions

### Own the probe state in one initialization

[hardware_caps.hpp:42](https://github.com/ROCm/rocm-libraries/blob/362fae1d3e55e23f8ca47b7a53815a6ea5b9b29a/projects/hipblaslt/tensilelite/rocisa/rocisa/include/hardware_caps.hpp#L42).

The two thread-local objects are correctly isolated in the submitted callers, but they make state lifetime indirect. `initAsmCaps` needs an active flag, an entry reset and an exception guard to manage state that belongs to one invocation. Its answer map and pending vector also store the same probe identities, followed by another duplicate scan when constructing batches.

Optional implementation **[fa68d23f858](https://github.com/newling/rocm-libraries/commit/fa68d23f858ea81f79800f511fe1c1d8b50a4378)** owns this state in a local `AssemblerProbes` object. One `map<Key, optional<bool>>` represents unanswered, accepted and rejected probes; unanswered entries supply the next batch. Normal destruction replaces the reset guard, and no thread-local storage or active flag remains. The object builds its two command lines once. Capability definitions pass only the instruction source and optional wave32 choice, removing repeated ISA/path/debug arguments. Execution/parsing helpers become private members.

The header is 233 lines shorter. Most diff movement comes from making the capability definitions members and removing invariant arguments. All instruction strings and capability expressions are preserved, checked after normalizing those argument removals and adjacent string literals. Source order within a batch now follows the answer map. The 24-ISA results still match the submitted PR with ROCm 7.1 and LLVM 23, and the full rocisa suite passes. This is an optional design improvement, separate from the required Windows fix.

### Preserve coverage for a signal after partial diagnostics

[test_asm_caps_probing.py:103](https://github.com/ROCm/rocm-libraries/blob/362fae1d3e55e23f8ca47b7a53815a6ea5b9b29a/projects/hipblaslt/tensilelite/rocisa/test/test_asm_caps_probing.py#L103).

The submitted killed-batch test uses SIGKILL without diagnostics. It still falls back if signal termination is returned as raw signal number 9, so it does not protect the SIGHUP distinction discussed in the earlier review. Suggestion **[254f7666dd7](https://github.com/newling/rocm-libraries/commit/254f7666dd7bc36aab5539855fe2b18ff7928dc7)** adds a batch which prints a valid line-numbered error and then dies of SIGHUP. **[3463e6c1c8f](https://github.com/newling/rocm-libraries/commit/3463e6c1c8fe57a6aca55b8daf07396f8cd76646)** removes the weaker plain-SIGKILL case, leaving this stronger case as its replacement. Returning raw status 1 would incorrectly accept subsequent probes. Removing the `128 + signal` conversion makes this test fail; the submitted implementation passes it.

### Refresh the nearby comments and direct includes

[base.hpp:109](https://github.com/ROCm/rocm-libraries/blob/362fae1d3e55e23f8ca47b7a53815a6ea5b9b29a/projects/hipblaslt/tensilelite/rocisa/rocisa/include/base.hpp#L109) still says each probe is an independent assembler run. [helper.hpp:33](https://github.com/ROCm/rocm-libraries/blob/362fae1d3e55e23f8ca47b7a53815a6ea5b9b29a/projects/hipblaslt/tensilelite/rocisa/rocisa/include/helper.hpp#L33) can also state more precisely that Windows always captures output when debug is off. Suggestion **[22a84251048](https://github.com/newling/rocm-libraries/commit/22a842510482502dc104d28e9d219a2a1c8d08e1)** corrects these comments and adds `<utility>` where the headers use `std::pair` and `std::move`. The includes are a dependency cleanup, not a demonstrated build failure.

### Remove the ineffective compiler guard

[helper.cpp:270](https://github.com/ROCm/rocm-libraries/blob/362fae1d3e55e23f8ca47b7a53815a6ea5b9b29a/projects/hipblaslt/tensilelite/rocisa/rocisa/src/helper.cpp#L270) conditionally includes `<cxxabi.h>` for `__GNUG__`, while the POSIX demangler unconditionally calls `abi::__cxa_demangle`. There is no alternate implementation behind that guard. **[698a24b9b90](https://github.com/newling/rocm-libraries/commit/698a24b9b90e5a1562dd9cadf14039fb5d97a250)** removes it and directly includes `<cstdio>` for `perror`.

### Clarify the description's assumptions and timing baselines

The [PR description](https://github.com/ROCm/rocm-libraries/pull/14741) describes the current batching implementation. Qualify the claim that the assembler reports every rejected line as an assumption validated for the tested probes and toolchains; the fallback cannot detect a parseable but incomplete diagnostic list. Also distinguish the passing Windows lanes from the eight new probing cases, all skipped on Windows in the submitted revision.

Reconcile the baseline figures between Motivation and Test Result, or identify them as different samples: TensileLogic is 147 versus 141 seconds, the complete build is 690 versus 680 seconds, and library probing is 24 versus 20 seconds. The savings calculated below use Test Result's figures.

## Scope decisions

The changed contract is host-side assembler discovery. Compiling rocisa, comparing real capability maps, exercising fallback/signal cases, and inspecting the Windows output reader are the appropriate checks. The existing `initMany` test also exercises concurrent production initialization. GPU numerical execution and a full local device-library build were not repeated; no instruction definition or numerical kernel changes in this diff. No additional feature flag is needed for an optimization intended to preserve the same discovery results.

The submitted thread-local state is correct for the current callers, but the optional local-object design expresses ownership directly and removes the reset protocol. Probes using different wave-size options stay in separate batches, and the existing `initAsmCaps` entry point is unchanged.

The implementation invokes the assembler through its command-line interface and uses documented OS process/pipe APIs; it does not call private LLVM internals. Diagnostic parsing depends on source locations and `error:`, rather than instruction-specific message wording. Both the submitted and suggested implementations still assume that every rejected probe produces a captured diagnostic. The Windows fix addresses the demonstrated capture failure, but does not remove that assumption. The capability comparisons support retaining this approach for the tested probes and toolchains; diagnostic completeness remains a compatibility constraint as either changes.

The coarse Windows/POSIX conditional remains useful: process creation, pipe handling and demangling use different operating-system APIs. Moving these implementations into two files would relocate the conditional to CMake without reducing that logic. The portability assessment covers Linux and Windows; the inherited `pipe2(O_CLOEXEC)` dependency is not available on every Unix-like host, so the POSIX label does not establish macOS support. Reusing COMGR for assembly would change which compiler is probed; the current API explicitly accepts an assembler executable. Neither restructuring is necessary for this optimization.

The eight probing cases are proportionate to the behavior: one six-architecture comparison covers distinct instruction families and conditional probes; two process-count cases cover ordinary and wave32 commands; two fallback cases cover unattributed errors and signal termination with partial diagnostics; one case interrupts waits; and two unsupported-ISA cases cover the different wave-size paths. The existing `initMany` comparison separately covers concurrent initialization. The redundant plain-SIGKILL case is removed; no new tests were added solely for the state refactor or preprocessor cleanup.

## Commentary

The [previous review](https://github.com/ROCm/rocm-libraries/pull/14741#pullrequestreview-5776954227) and its inline requests were checked against the final design:

| Earlier concern | Current disposition |
| --- | --- |
| Home-directory writes and an alternative to caching | Addressed by removing the persistent cache and batching the work itself. |
| Motivation as a share of a complete workload | The description now gives Windows build figures and explicitly identifies the relevant workload; local repeated probing measurements support the mechanism. |
| Thread-local implications | Correct isolation in the submitted implementation; optional [fa68d23f858](https://github.com/newling/rocm-libraries/commit/fa68d23f858ea81f79800f511fe1c1d8b50a4378) removes thread-local state and its reset protocol altogether. |
| Windows validation | The inspected public build/test lanes passed, but the new comparison was skipped on Windows and the output-drain race remains in the submitted code. Suggestion [9a91c1eb233](https://github.com/newling/rocm-libraries/commit/9a91c1eb23304dc593b7600ad043f6e903e3ab13) addresses both. |
| `Caps` spelling and `tensile` directory naming | The questioned cache API and directory are removed; existing `asmCaps` naming remains consistent with rocisa. |
| Silent cache-store failure | The store is removed. Missing executable, failed wait and failed poll paths throw; unusable batch diagnostics fall back to individual probes. |

### Reported performance in absolute and relative terms

The following arithmetic uses the author's Test Result figures, rather than new measurements:

| Workload | Before seconds | After seconds | Seconds saved | Time reduction |
| --- | ---: | ---: | ---: | ---: |
| Linux probing, 24 ISAs | 1.8 | 0.07 | 1.73 | 96.1% |
| Windows TensileLogic | 141 | 49 | 92 | 65.2% |
| Windows library probing | 20 | 0.5 | 19.5 | 97.5% |

The Windows steps together save 111.5 seconds, or 16.4% of the reported 680-second baseline build. This estimates their contribution to build-time savings from one PR build versus baseline medians; it is not a repeatedly measured reduction in complete build time. The local paired measurements below independently support the probing improvement.

### Local probing measurements

These are individual timed launches of a small C++ driver calling `initAsmCaps` for all 24 `SUPPORTED_ISA` entries using four worker threads, with the same driver and `-O2` build for the exact base and submitted head. Runs used low priority on a busy shared Linux host, with no separate warm-up. Each pair ran in the order shown. Every pair produced byte-identical assembly-capability tables. These timings measure probing, not an entire hipBLASLt build or GPU kernel execution.

| Assembler | Pair | Order | Base seconds | Submitted seconds |
| --- | ---: | --- | ---: | ---: |
| ROCm 7.1 / AMD clang 20 | 1 | Base, submitted | 6.966560 | 0.243933 |
| ROCm 7.1 / AMD clang 20 | 2 | Submitted, base | 6.915400 | 0.227476 |
| ROCm 7.1 / AMD clang 20 | 3 | Base, submitted | 6.808720 | 0.243893 |
| LLVM 23.1 | 1 | Base, submitted | 4.645850 | 0.130417 |
| LLVM 23.1 | 2 | Submitted, base | 4.904460 | 0.129402 |
| LLVM 23.1 | 3 | Base, submitted | 5.052010 | 0.163635 |

The small sample and shared-host load do not support a precise general speedup estimate. The consistent reduction and equal tables support the batching mechanism under these conditions.

### Appendix: deterministic Windows interleaving reproduction

The exact standalone source and setup are in [review_pr14741_windows_tail_repro.py](review_pr14741_windows_tail_repro.py). On a Linux host with Python 3 and a C++20-capable Clang, run:

```sh
python3 review_pr14741_windows_tail_repro.py "$SRC_DIR" --cxx clang++
```

`$SRC_DIR` is a checkout of the repository at the revision to test. The script creates its own temporary headers, compiles the actual `_WIN32` implementation in `helper.cpp`, runs the controlled interleaving, and deletes generated files. On the submitted revision it exits 1 and prints `last diagnostic captured=0`; on the suggestion branch it exits 0 and prints `last diagnostic captured=1`. It makes no claim about the frequency of that interleaving on a Windows host.

The published suggestion branch is [review/pr14741-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14741-suggestions): [9a91c1eb233](https://github.com/newling/rocm-libraries/commit/9a91c1eb23304dc593b7600ad043f6e903e3ab13) implements the actionable item, [254f7666dd7](https://github.com/newling/rocm-libraries/commit/254f7666dd7bc36aab5539855fe2b18ff7928dc7) adds the optional signal regression, [22a84251048](https://github.com/newling/rocm-libraries/commit/22a842510482502dc104d28e9d219a2a1c8d08e1) updates comments/includes, [fa68d23f858](https://github.com/newling/rocm-libraries/commit/fa68d23f858ea81f79800f511fe1c1d8b50a4378) localizes and simplifies probe state, [3463e6c1c8f](https://github.com/newling/rocm-libraries/commit/3463e6c1c8fe57a6aca55b8daf07396f8cd76646) removes the redundant test case, and [698a24b9b90](https://github.com/newling/rocm-libraries/commit/698a24b9b90e5a1562dd9cadf14039fb5d97a250) removes the redundant header guard. All bounded code findings have implementations. The description clarifications above remain for the author to incorporate. Native Windows validation and the unresolved external CI statuses remain the limits described above.
