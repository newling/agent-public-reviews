> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#11717](https://github.com/ROCm/rocm-systems/pull/11717)

**Revision reviewed:** `a633e3d6febb0b0acd1bbe5d1cc01c96da53a77b`

**Review status:** In progress; this is the initial architecture and CI pass.

## Tests

The Clang 23 RelWithDebInfo `rocjitsu_tests` target built successfully; 347 focused race-detector and data-hazard core, adapter, helper, parser, and tensor-range tests passed, as did 18 non-GPU Python mutation-harness tests. In a local merge experiment, all 47 existing `RaceTest.*` HIP cases passed with both detectors loaded, and the data-hazard detector produced a completion summary for every case. It detected the intended resource class in all 25 cases the race suite expects to report, agreed on 19 of the 21 explicitly clean cases, and differed on the two cases discussed below. Twenty-one GPU mutation cases were deferred from this pass, and the installed device compiler does not support the gfx1250 end-to-end cases. The ASan/UBSan and GCC UBSan CI lanes each fail `TensorLdsWriteRangeTest.DescriptorTheExecutorRejectsWritesNothing` as described below; the Release lane's remaining FPSan corpus failure does not yet appear specific to this plugin. The TSan lane's broad failures are caused in part by this PR overwriting its exclusion list, also described below.

## Summary

Despite its title, this is not principally a switch that enables an existing rocJITsu plugin. It adds a new analysis subsystem: a simulator-neutral hazard engine with an installed C++ API and standalone shared library, a rocJITsu frontend and reporting layer, changes to the execution-plugin barrier contract, a large direct unit-test suite, and a Python mutation framework backed by a new HIP kernel corpus. The net diff is 83 files and about 21,000 added lines. Roughly 7,200 lines are C++ hazard tests, 4,000 are the neutral engine, 3,000 are the mutation framework, 2,500 are test kernels, and 2,500 are the rocJITsu adapter, plugin, and reporter.

The architectural flow is cleanly layered: rocJITsu execution callbacks are translated into small instruction, resource-access, wait, barrier, and lifecycle events; `DataHazardEngine` uses those events to maintain per-wave wait-counter FIFOs, per-workgroup LDS epochs, and a dispatch-scoped global-memory shadow; findings then pass through a rocJITsu collector for streaming, deduplication, and optional JSON serialization. Making the detector core independent of rocJITsu is the strongest choice in the change. It provides a plausible reusable boundary for another simulator and lets most of the state machine be tested without constructing a VM.

The important repository context is that rocJITsu already has a `race_detector` plugin. That detector also covers missing-wait register hazards and cross-wave LDS races, with lane and byte precision, so the submitted plugin substantially overlaps an existing user-facing tool. Its distinct contributions are the portable event API, a more explicit FIFO model of architecture-specific wait domains (including the newer split and tensor counters), cross-workgroup global-memory tracking, structured producer/consumer identities, and the mutation harness. The deeper review therefore needs to establish a durable division of responsibility between the two detectors and make sure their overlapping cases do not silently disagree.

The highest-risk boundaries are not the bulk of the implementation but the translations and retained-state contracts: mapping decoded rocJITsu instruction semantics into generic events; preserving lane and byte precision; retiring each wait FIFO correctly on every supported architecture; closing LDS epochs only at the correct barrier scope; bounding and clearing dispatch/workgroup/wave/global state; defining what constitutes a global race without a complete cross-workgroup happens-before model; and keeping the installed engine API and JSON output stable enough for external consumers. The mutation harness is useful evidence because it starts with compiler-generated kernels and removes final-ISA waits, but its classification model also needs a separate pass: numerical output is manifestation evidence, not by itself ground truth for whether a removed wait guarded a real dependency.

The source diff is much easier to review than the branch history. The PR currently contains 119 commits because a long patch sequence was merged and then largely duplicated, and it conflicts with current `develop` in the plugin documentation and plugin CMake file. I am treating that as integration debt rather than using the commit sequence as the unit of review.

## Actionable items

### Return an empty tensor range for descriptors the executor rejects

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/plugins/data_hazard/plugin.cpp:775-805`, `emulation/rocjitsu/tests/data-hazard/tensor_lds_range_tests.cpp:70-75`

`tensor_lds_ranges()` documents invalid descriptors as touching no LDS, and the direct test constructs such a descriptor and expects an empty result. The implementation instead asserts that `validate_supported_descriptor()` succeeds. That validator reports failure through its return value rather than an exception, so debug/assert-enabled configurations abort before reaching the existing catch block. This is the failure in both the ASan/UBSan and GCC UBSan CI lanes. In builds with `NDEBUG`, the validation result is discarded and the helper proceeds to derive ranges for an operation the executor will reject, so the apparent Release pass does not satisfy the stated contract either.

Check the validation result and return an empty range on failure before calling `for_each_lds_run()`. Keep the existing regression test enabled in both assertion-enabled and Release configurations.

### Make focused data-hazard test builds produce the plugin they load

**Files:** `emulation/rocjitsu/tests/data-hazard/CMakeLists.txt:8`, `emulation/rocjitsu/tests/race-detector/CMakeLists.txt:19-25`

Building `hip_data_hazard_tests_gfx950_target` does not build `librocjitsu_plugin_data_hazard.so`. Running either registered `DataHazardTest.*` case after that focused build fails because rocJITsu cannot load the plugin; the clean case reports that no log was produced and the hazardous case sees zero findings. The analogous race-test helper explicitly adds a dependency on `rocjitsu_plugin_race_so`, which is why the two race cases work under the same focused-build procedure.

Add the corresponding runtime-plugin dependency to the data-hazard HIP target. Prefer putting this behavior in the shared plugin-test CMake helper proposed below so future test suites cannot omit the module they load.

### Preserve the common exclusions when constructing the TSan test set

**File:** `.github/workflows/rocjitsu-corpus-tests.yml:243-293`

The workflow defines `TSAN_EXCLUDED_TESTS` at line 243, then immediately replaces it at line 272 using `${ASAN_UBSAN_EXCLUDED_TESTS[@]}`, which is not defined anywhere. The second assignment discards the common exclusions, `RaceTest.*`, `DataHazardTest.*`, and several other additions from the first assignment. This is why the current TSan job runs a broad set of tests that the comments say must be excluded and reports 42 failures, including both detector suites.

Build each sanitizer list once from the intended parent list, using names that match the references at lines 297-313. Add a lightweight shell or workflow test that expands the final regex and verifies representative common, ASan-specific, and TSan-specific entries so another list overwrite cannot silently change the test matrix.

## Suggestions

### Run shared HIP hazard cases through both detector adapters

**Files:** `emulation/rocjitsu/tests/race-detector/hip_race_gfx950_test.hip:37-84`, `emulation/rocjitsu/tests/data-hazard/hip_data_hazard_gfx950_test.hip:152-197`, `emulation/rocjitsu/tests/race-detector/CMakeLists.txt:49-139`, `emulation/rocjitsu/tests/data-hazard/CMakeLists.txt:20-88`

The data-hazard end-to-end file duplicates the race detector's safe/racy gfx950 VGPR-wait kernels, allocation and launch logic, per-case output directories, configuration rewriting, and CTest registration. Only the native report parser and assertions actually differ. The copied topology configurations have already drifted (`num_sdma_queues_per_engine` is two in one and eight in the other), and the missing shared-object dependency above is another concrete product of maintaining parallel harnesses.

Move overlapping end-to-end cases into a tool-neutral hazard suite. Compile each architecture/domain program once, select one case at runtime, and run that same artifact under a tool matrix. Keep one adapter per native report format: the race adapter should retain its current strict kernel, symbol, count, wave/lane, and trace assertions; the data-hazard adapter should normalize its own findings. Match only stable semantics such as detected/not-detected, hazard domain, resource space, access pair, and required synchronization in the common layer. In particular, do not require a directed RAW/WAR label or one exact wave pair for a cross-wave case whose access order is scheduling-dependent.

The smallest precursor PR can be an NFC refactor of only the existing `vgpr_waitcnt` safe/racy race tests into this shared location, with the race adapter as its sole initial consumer and the public `RaceTest.*` names preserved. This PR can then add the data-hazard adapter and register the same two cases under `DataHazardTest.*`, deleting its duplicate HIP source and configuration. Expanding to SGPR, WAW, LDS, partial-wait, and scratch cases should follow only after that vertical slice is stable. The plugin-specific white-box core and adapter tests should remain separate; sharing those would reduce coverage to the two engines' lowest common denominator.

## Commentary

The review will proceed by contract rather than by file size. The neutral event/API layer comes first because every frontend and report depends on it; the wait FIFO and resource-overlap algorithms come next; the rocJITsu callback adapter, lifecycle, and barrier behavior follow; then reporting/deduplication and the mutation oracle; finally the documentation, build/install surface, and targeted end-to-end cases. That order should expose semantic mismatches before spending time on the large test corpus that encodes them.

Several design choices are already worth preserving: decoded instruction metadata, rather than mnemonic-only classification, supplies most asynchronous-operation semantics; completed barriers are reported separately from barrier instructions, so early-arriving waves do not close an LDS epoch; and the core's finding type retains hazard kind, resource kind, producer/consumer identity, address/size, and required wait. One question for the reporting pass is whether enough of that structure survives the rocJITsu collector and JSON boundary for downstream tools to consume it without parsing English messages.

The two plugins currently have five useful testing levels. Primitive/container and core state-machine tests are implementation-specific and should stay with their owners. rocJITsu adapter tests are also plugin-specific because they protect different callback translations. Native report-parser tests should remain adapter-specific but feed a common normalized finding contract. Compiled HIP cases, topology configuration, process launch, artifact isolation, and common semantic expectations are the main shared layer. The mutation pipeline is a later shared layer: its compile/disassemble/mutate/rebuild machinery already accepts a runner abstraction, but report loading and scoring are still hard-coded to the data-hazard JSON/count model and must become tool-adapter responsibilities before the race detector can consume the same mutants.

The full HIP-corpus experiment confirms that this split is practical. Every existing case executes successfully with both plugins observing the same run, and no established race-detector test changes behavior. Finding counts should not be shared assertions: several LDS cases produce two data-hazard findings where the race detector's current deduplication expects one, and one multi-kernel case produces one intended VGPR finding plus 192 findings from the data-hazard detector's additional global-memory domain.

Two established clean cases require tool-specific expectations. `lds_same_wave_order` produces one same-wave LDS RAW and one WAR finding because the data-hazard engine treats those DS operations as pending until `lgkmcnt(0)`, while the existing detector models ordinary same-wave DS accesses as ordered. That semantic disagreement needs an ISA-model decision before the case can have a common clean expectation. `multi_kernel` produces 64 global WAW findings because `clean_kernel_a` launches five workgroups but indexes its output with `threadIdx.x` alone, causing several workgroups to write the same addresses. That is outside the existing detector's domain but is a real input to the new global shadow, so this case is clean only for the race-detector profile rather than universally clean.
