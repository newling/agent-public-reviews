This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12590](https://github.com/ROCm/rocm-libraries/pull/12590)

Reviewed head: `bd3d79143c100a83b42003042b150cb0fab10780`. Incremental base: #12588 at `1d38aaf48da6878c8dcd285963a3ab7873a8cbaa`. #12589, which adds partial-search policy, is a sibling.

Suggestion branch: [review/pr12590-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12590-suggestions), based on that exact head.

| Commit | Review item |
| --- | --- |
| [60687f478e8](https://github.com/newling/rocm-libraries/commit/60687f478e809fa8ca11f5a8bf72388b14adab28) | Apply each YAML/data case's measurement settings before tuning it. |
| [02730c0f103](https://github.com/newling/rocm-libraries/commit/02730c0f103c971ddb9b14b79d16f2fd24949a21) | Use the Windows environment-setting function when building on Windows. |

These changes address separate issues and can be considered independently.

## Tests

The submitted and suggestion versions build on Linux and pass the command-line tune, repeat, C++ override, cache replay and conflicting-environment checks on MI300X; the YAML counterexample fails before its fix and passes afterward, and four padded/distinct-C-and-D layout checks pass.

QuickTune's parser successfully reads a positive latency and solution index from both ordinary and tuning output. These runs test parsing, not performance improvement. Native Windows validation of the suggested fix was unavailable; the submitted Windows failure is confirmed by the public CI log linked below. Testing used a scoped, matching gfx942 device library, not every architecture or epilogue.

As a separate integration check, I combined both sibling PRs and all six suggestion commits from #12587–#12590. The library and benchmark build, YAML cases use their individual settings, repeated identical tuning reuses the row, and widening a completed search from four to eight candidates tunes again and appends a version-2 row. C++ override and cache replay use the saved index, with numerical verification passing. This checks the interaction between the siblings; it does not resolve #12589's separate completed-versus-partial precedence issue or incorporate the current #12586 fixes.

The PR's automated checks remain red. Its embedded #12586 predates the Windows private-parser and test-packaging corrections; the new Windows error below is additional. The [#12587 review](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12587.md) describes the inherited failures examined in this pass.

## Summary

This PR makes `hipblaslt-bench` use the runtime tuner introduced by #12588 whenever `HIPBLASLT_TUNING_FILE` is set. An untimed C-API call searches and saves the winner, then the benchmark queries selection again and measures that winner. The benchmark's measurement options configure the library search, and the search has no time limit unless one is explicitly supplied.

Using one search implementation for offline tuning and application tuning is a useful simplification. The benchmark gives the tuning call the full workspace limit, so a small workspace requirement from the initial heuristic choice does not accidentally restrict the search. The change also removes file-writing side effects from result printing: persistence now uses the store's versioned rows, while output formatting only reports results.

This finishes the stack's path from persistence (#12586), through replay (#12587) and measurement (#12588), to a benchmark frontend. It does not require #12589 to work, but combining that sibling changes when an existing result is considered sufficient.

## Actionable items

### Use a supported environment setter on Windows

At [`clients/bench/src/client.cpp:130`](https://github.com/ROCm/rocm-libraries/blob/bd3d79143c100a83b42003042b150cb0fab10780/projects/hipblaslt/clients/bench/src/client.cpp#L130), the new helper calls POSIX `setenv` unconditionally. The [Windows build](https://github.com/ROCm/rocm-libraries/actions/runs/36216990764/job/108340522435) fails while compiling this line with `error: use of undeclared identifier 'setenv'`. This prevents the benchmark from building, regardless of whether a user enables tuning.

[02730c0f103](https://github.com/newling/rocm-libraries/commit/02730c0f103c971ddb9b14b79d16f2fd24949a21) calls `_putenv_s` under `WIN32` and keeps `setenv` elsewhere, following the client's existing portability convention. The Linux build passes with the change; the Windows lane must confirm the other branch.

### Configure the tuner from each data-file case

At [`client.cpp:1034`](https://github.com/ROCm/rocm-libraries/blob/bd3d79143c100a83b42003042b150cb0fab10780/projects/hipblaslt/clients/bench/src/client.cpp#L1034), `main` initializes the tuning environment from the command-line `Arguments`. A `--data` run subsequently loads separate arguments for each case, but [`run_bench_test` at line 296](https://github.com/ROCm/rocm-libraries/blob/bd3d79143c100a83b42003042b150cb0fab10780/projects/hipblaslt/clients/bench/src/client.cpp#L296) starts tuning without updating those settings.

Thus the library searches using command-line defaults while the later benchmark measures using the case's options. In the reproducer below, two cases request two and three candidates and disable flushing. With `--requested_solution 4`, the submitted code searches four candidates for both cases and enables instruction-cache flushing. Candidate count, warmup/timed iterations, rotation and flushing can all disagree with the case being run.

[60687f478e8](https://github.com/newling/rocm-libraries/commit/60687f478e809fa8ca11f5a8bf72388b14adab28) applies each data case's arguments through `enter_library_tune_mode` before its tuning pass. Mode/path selection is initialized early, but search settings are read for each tuning attempt. After the change, the logs show two and three candidates and no flush calibration. Ordinary command-line behavior still passes the same checks.

## Suggestions

No additional code suggestions from this pass. The branch contains the two bounded fixes above. The exact YAML regression is preserved below; it is not registered in the repository's shared test suite.

## Commentary

Sharing the measurement implementation does not guarantee identical winners across separate runs. The new changelog and helper comment say the benchmark and an application “cannot” choose different winners. GPU load, input data, clock state and measurement noise still permit that outcome; the supported claim is that they use the same search and timing method. The printed benchmark time is also a fresh measurement, distinct from the time saved by the tuner.

The benchmark inherits the runtime tuner's eligibility restrictions. It explicitly skips grouped and pointer-array problems, and the tuner also declines cases such as nonzero beta with C and D sharing storage. Users of offline tuning need to understand that a benchmark can run without adding a tuning row.

The legacy writer disappears here, but the reader remains. Existing unversioned files still have their older, less specific matching rules; newly written versioned rows distinguish full problem layouts. This change therefore completes writer migration without establishing a legacy-reader removal date.

The statement that a problem already in the file is never tuned again describes this PR without #12589. Once the siblings are combined, search coverage and budget decide whether to retune; the integration check above exercises that distinction. Restacking on current #12586 and rerunning shared CI remain necessary before relying on the stack as a whole.

## YAML counterexample

Save this as `bench-cases.yaml` in a fresh results directory:

```yaml
---
include: hipblaslt_common.yaml
include: matmul_common.yaml
Tests:
- name: tuning_options_small
  function:
    matmul: *hpa_half_precision
  M: 128
  N: 128
  K: 128
  transA: N
  transB: N
  alpha: 1
  beta: 0
  c_equal_d: false
  iters: 2
  cold_iters: 0
  rotating: 0
  flush: false
  requested_solution_num: 2
- name: tuning_options_large
  function:
    matmul: *hpa_half_precision
  M: 256
  N: 256
  K: 256
  transA: N
  transB: N
  alpha: 1
  beta: 0
  c_equal_d: false
  iters: 3
  cold_iters: 1
  rotating: 0
  flush: false
  requested_solution_num: 3
```

Set `$SRC_DIR` to the repository root, `$BUILD_DIR` to the standalone hipBLASLt build and `$DEVICE_LIBRARY` to its matching generated library. Use a Python environment with the generator's dependencies and a device library providing at least four supported FP16 candidates:

```bash
python3 "$SRC_DIR/projects/hipblaslt/clients/tests/hipblaslt_gentest.py" \
  -I "$SRC_DIR/projects/hipblaslt/clients/tests/data" \
  -I "$SRC_DIR/projects/hipblaslt/clients/common/include" \
  bench-cases.yaml -o bench-cases.data
env -u HIPBLASLT_TUNING_MODE -u HIPBLASLT_TUNING_CACHE_PATH \
  -u HIPBLASLT_TUNING_OVERRIDE_FILE -u HIPBLASLT_LOG_LEVEL \
  HIPBLASLT_TENSILE_LIBPATH="$DEVICE_LIBRARY" \
  HIPBLASLT_TUNING_FILE=case-options.tuning HIPBLASLT_LOG_MASK=8 \
  "$BUILD_DIR/clients/hipblaslt-bench" --data bench-cases.data \
  --requested_solution 4 --iters 2 --cold_iters 0 --rotating 0 \
  > case-options.log 2>&1
python3 - <<'PY'
import re
from pathlib import Path
text = Path('case-options.log').read_text()
assert re.findall(r'setup candidates=(\d+)', text) == ['2', '3']
assert 'icache flush enabled' not in text
assert text.count('tuning-done') == 2
PY
```

The submitted version reports `['4', '4']` and flush calibration; the suggestion branch passes all three assertions. Use a fresh tuning file for each version so existing rows do not bypass the search. These two commits contain no changes from predecessor suggestion branches; native Windows and exhaustive datatype/epilogue validation were omitted.
