# Independent barrier-cell arrivals

These probes accompany [the review of systems #16148](../review_pr16148.md). The reviewed systems head is `4d612756ff5461bd22e1df47165ce0300db86e7c`. The HIP helpers and companion cases come from [corpus #97](https://github.com/ROCm/rocjitsu-test-corpus/pull/97), pinned at `ae83692bd61765d6423d5c29060463e4f732067b`.

Two waves share two aligned cells, C0 and C1, each initialized to require one arrival. The producer executes one DS arrive instruction with two active lanes, one per cell. The consumer optionally polls a cell until its first phase completes, then overwrites C1. The producer's lane-to-cell assignment is also reversed. The tested arrival forms are `ds_atomic_barrier_arrive_rtn_b64` and `ds_atomic_async_barrier_arrive_b64`.

| Consumer action before overwriting C1 | Expected | Observed in native and HIP probes | Cases per probe |
| --- | --- | --- | ---: |
| No poll | Race | Race | 4 |
| Poll C0 | Race | No race | 4 |
| Poll C1 | Clean | Clean | 4 |

Each probe therefore passes eight cases and fails four at the reviewed head. The assertions preserve the desired behavior, so both test commands return nonzero. The four failures say that an expected LDS race was absent; there were no launch, decode, data-output, timeout, or plugin-loading failures.

The expectation follows CDNA5 ISA revision 27 July 2026, §§11.2.1–11.2.2. Each lane performs its own atomic update; the ISA provides no ordering of sibling lanes that lets observing C0 establish completion of the arrival at C1. Section 5.7.1.4's LDS instruction ordering justifies handing off earlier instructions. It does not make one lane's cell a completion token for its sibling lanes. [Authoritative PDF](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-cdna5-instruction-set-architecture.pdf).

## Native probe

Set `SRC_DIR` to the systems checkout's `emulation/rocjitsu`, `BUILD_DIR` to its configured Ninja build, `ARTIFACTS` to this directory, and `EVIDENCE` to an existing output directory outside the source tree. The build must have `CMAKE_EXPORT_COMPILE_COMMANDS=ON` and the native tests enabled. The recorded build uses Clang 23.1, C++20, Release/NDEBUG, and the existing `-Wno-error=unused-template` option. Expensive checks are disabled.

```bash
cmake --build "$BUILD_DIR" --target rocjitsu_tests --parallel 8
python3 "$ARTIFACTS/build-probe.py" "$BUILD_DIR" \
  "$ARTIFACTS/multicell_probe.cpp" "$EVIDENCE/multicell-probe"
"$EVIDENCE/multicell-probe" \
  --gtest_filter='*DecodedBarrierCellReviewTest.*' \
  --gtest_output="xml:$EVIDENCE/native.xml"
```

The [source](multicell_probe.cpp) reuses the submitted two-wave fixture. It decodes and executes the arrival, load, store, and wait instructions. The fixture supplies before/after/routed-memory notifications, and the production local-memory pipeline performs the accesses and emits the per-lane arrival notifications. Cell contents and the loaded phase bit are checked. No-poll controls establish that the conflicting cell access is represented in the detector.

The [build script](build-probe.py) takes the existing native test compilation and link commands, replaces only the fixture translation unit with the probe, and writes a separate executable. It neither edits the checkout nor replaces the normal test binary. All other production and test objects come from the configured build.

## HIP probe and companion cases

Use a gfx1250-capable HIP compiler. The recorded compiler is the `hipcc` from ROCm SDK `10.1.0a20260812`, reporting HIP 7.16 and AMD Clang 23.0.0git. `CORPUS_INPUTS` must be an existing directory outside the source tree. Fetch the three pinned public inputs:

```bash
for name in hip_race_gfx1250_test.hip race_test_support.hpp race_log_expectation.hpp; do
  curl --fail --location \
    "https://raw.githubusercontent.com/ROCm/rocjitsu-test-corpus/ae83692bd61765d6423d5c29060463e4f732067b/corpus/race/integration/$name" \
    --output "$CORPUS_INPUTS/$name"
done

"$HIP_CXX" -std=c++20 -O2 --offload-arch=gfx1250 -x hip \
  "$ARTIFACTS/multicell_probe.hip" -I"$CORPUS_INPUTS" \
  -isystem "$BUILD_DIR/_deps/googletest-src/googletest/include" \
  -x none "$BUILD_DIR/lib/libgtest.a" -pthread -o "$EVIDENCE/cell-hip-tests"

cmake --build "$BUILD_DIR" \
  --target rocjitsu rocjitsu_shared rocjitsu_cli rocjitsu_plugin_race_so --parallel 8
python3 "$ARTIFACTS/run-hip.py" "$SRC_DIR" "$BUILD_DIR" \
  "$EVIDENCE/cell-hip-tests" "$EVIDENCE/hip-results" \
  --corpus-source "$CORPUS_INPUTS/hip_race_gfx1250_test.hip"
```

The [HIP source](multicell_probe.hip) includes the pinned corpus source to reuse its helpers, fixture, and main. The [runner](run-hip.py) runs each case in a fresh process with `gfx1250_mi455x.json`, two CPU workers, and `require_all_plugins=true`. All runtime and plugin targets must be built from the same systems revision. The output directory must be new, avoiding stale XML or race logs. Each case has a 50-second timeout and a further five-second termination limit.

With `--corpus-source`, this runs the 22 submitted cell cases and 12 new cases: **30 pass, four fail**. Omit that option to run only the 12 new cases. The driver rejects missing/empty test execution, skipped tests, missing plugin output, and nonzero exits. Expected-race tests check LDS reports and the arrival/store instruction pair. Every new kernel checks its independently written completion output, without asserting a value for the unordered cell update.

The emitted ISA was inspected: one arrive instruction has both producer lanes active, their addresses differ by eight bytes, the consumer's phase loop precedes its store to C1, and the final workgroup barrier follows the tested accesses. For the no-poll HIP controls, the consumer happened to store first and the producer reported RAW; the native controls execute the producer first and report WAR.

The runs are functional emulation and host execution. No GPU hardware run, sanitizer run, throughput measurement, or exhaustive schedule exploration was performed. The optional source suggestions in the review do not implement the ordering fix.
