# Split-barrier review experiments

These sources accompany [the second review](../review_pr16020_v2.md). They run at the reviewed head and at the suggestion branch. The C++ probes drive the detector directly; the HIP program exercises the simulator and dynamically loaded race plugin. They do not require a GPU. All results in the review are emulation or host results, not hardware measurements.

## Detector probes

Start with a configured rocjitsu build that includes `lib/libgtest.a` and generated headers. Set `SRC_DIR` to `emulation/rocjitsu`, `BUILD_DIR` to that build, and `ARTIFACTS` to this directory. Clang 23.1 with C++20 was used. Build outputs belong outside the source checkout.

```bash
CXX=clang++ bash "$ARTIFACTS/build-probe.sh" "$SRC_DIR" "$BUILD_DIR" \
  "$ARTIFACTS/epoch_wrap_probe.cpp" "$BUILD_DIR/epoch-wrap-probe"
timeout 300s "$BUILD_DIR/epoch-wrap-probe"

CXX=clang++ bash "$ARTIFACTS/build-probe.sh" "$SRC_DIR" "$BUILD_DIR" \
  "$ARTIFACTS/schedule_probe.cpp" "$BUILD_DIR/schedule-probe"
"$BUILD_DIR/schedule-probe"

CXX=clang++ bash "$ARTIFACTS/build-probe.sh" "$SRC_DIR" "$BUILD_DIR" \
  "$ARTIFACTS/termination_probe.cpp" "$BUILD_DIR/termination-probe"
for waves in 2 3 4 16 32; do
  "$BUILD_DIR/termination-probe" "$waves"
done
```

The epoch probe deliberately performs `UINT32_MAX` counted signals, followed by one LDS store, a DSCNT drain, and an unsynchronized read by another wave. It returns 1 on the submitted head, with `completion_epoch=0 expected_races=1 actual_races=0`. With the suggestion it returns 0 and prints epoch 4294967296 and one race. It took 18.473 and 17.071 seconds respectively in the recorded optimized core runs; these are reproduction timings, not a performance comparison or full HIP-kernel timings. Its barrier has threshold 127 and no joined listeners, so unobserved completions create no callback. Each later generation discards the prior unobserved round. Memory use stays bounded, and no event ID approaches its own integer limit.

The schedule probe exhaustively enumerates legal issue orders of each specified small, fixed program, allowing the consumer's wait only after a completion. Its token-set oracle checks the ordering of each memory access. It does not claim to enumerate every possible HIP or ISA program. For threshold 1, it also preserves the first completion bit if another round finishes before the consumer waits.

The termination probe extends the earlier review's independent token-set oracle. Workgroup signals and waits are now separate actions. Named waits, JOIN, INIT, new accesses, and termination can occur between them. It includes 200 seeds, 800 actions per seed, and the requested wave count. Termination is permitted only when the exiting wave has no outstanding workgroup signal or completion bit, respecting the ISA's warning about signaling and then exiting. The oracle retains individual access tokens and does not use epochs, coverage minima, registry retirement, or a history-prefix scan.

To reproduce the sanitizer configuration, copy `build-probe.sh` and replace `-O3 -DNDEBUG` with `-O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined`. The review ran that configuration for 4 and 32 waves at both source revisions, with `ASAN_OPTIONS=detect_leaks=1`. The detector sources and probe were instrumented; the existing GoogleTest static library was not rebuilt with sanitizers.

## HIP probes

Use a gfx1250-capable HIP compiler. The recorded compiler came from ROCm SDK 10.1.0a20260812. The program was built with `-O2`. The assembly can be inspected separately:

```bash
"$HIP_CXX" -std=c++20 -O2 --offload-arch=gfx1250 -x hip \
  "$ARTIFACTS/barrier_probe.hip" -o "$BUILD_DIR/barrier-probe"
"$HIP_CXX" -std=c++20 -O2 --offload-arch=gfx1250 --cuda-device-only -S -x hip \
  "$ARTIFACTS/barrier_probe.hip" -o "$BUILD_DIR/barrier-probe.s"

cmake --build "$BUILD_DIR" --target rocjitsu rocjitsu_shared rocjitsu_hooks rocjitsu_plugin_race_so -j24
python3 "$ARTIFACTS/run-hip.py" "$SRC_DIR" "$BUILD_DIR" \
  "$BUILD_DIR/barrier-probe" "$BUILD_DIR/barrier-probe-results"
```

All runtime and plugin targets must come from the same source revision. Building only the launcher and plugin can leave an older `librocjitsu.so` in the build tree. A preliminary mixed-runtime run was discarded; it is not review evidence.

Each case runs in a fresh process with `gfx1250_mi455x.json`, two CPU workers, and `require_all_plugins=true`. The script saves the full reports and rejects launch failures, timeouts, missing plugin output, unexpected report counts, and non-LDS findings. The executable verifies defined output values in the safe cases. It does not prescribe values for unordered accesses.

| Case | Program | Perturbation | Observed LDS reports |
| --- | --- | --- | ---: |
| 0 | Threshold 1; C reads A | Delay A before signal | 1 |
| 1 | Threshold 1; C reads A | Delay B before signal | 0 |
| 2 | Threshold 1; C reads both | Delay A before signal | 1 |
| 3 | Threshold 1; C reads both | Delay B before signal | 1 |
| 4–7 | Threshold 2; same four variants | Same delays and read choices | 0 each |
| 8 | A → B → C, relayed through B's exit | A drains; B waits | 0 |
| 9 | Exit relay | A drains only after signaling B | 1 |
| 10 | Exit relay | B omits its wait | 1 |
| 11 | Ready threshold 5, consumed threshold 1 | A signals twice, B three times; 32 buffer reuses | 0 |

The delay is a loop of `s_nop 7`, not a synchronization operation. It perturbs the first contributing producer without adding a flag handoff. The observed threshold-1 outcomes are tied to this emulator configuration; they are not hardware-wide scheduling guarantees. The exhaustive core probe establishes the possible outcomes independently of these delays.

In the exit relay, A signals the workgroup barrier *before* writing. B acquires A's later write through a named barrier, then terminates instead of signaling the workgroup. C signals and waits on the workgroup before reading A's tile. A waits for C's acknowledgment before finishing, so A's own termination cannot accidentally make the negative controls safe. Generated assembly was checked for those signal, drain, wait, and exit paths.
