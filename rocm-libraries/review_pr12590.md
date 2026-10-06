This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12590](https://github.com/ROCm/rocm-libraries/pull/12590)

Reviewed head: [bd3d79143c1](https://github.com/ROCm/rocm-libraries/commit/bd3d79143c100a83b42003042b150cb0fab10780). Incremental base: [#12588](https://github.com/ROCm/rocm-libraries/pull/12588) at [1d38aaf48da](https://github.com/ROCm/rocm-libraries/commit/1d38aaf48da6878c8dcd285963a3ab7873a8cbaa). Partial-search PR [#12589](https://github.com/ROCm/rocm-libraries/pull/12589) is a sibling.

Suggestion branch: [review/pr12590-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12590-v2-suggestions), based on that exact head ([suggestion diff](https://github.com/newling/rocm-libraries/compare/bd3d79143c100a83b42003042b150cb0fab10780...3809ca52f3205359af037e5caa61a6b33eb0e0bb)).

| Commit | Review item |
| --- | --- |
| [60687f478e8](https://github.com/newling/rocm-libraries/commit/60687f478e809fa8ca11f5a8bf72388b14adab28) | Apply each data-file case's measurement settings before tuning it. |
| [02730c0f103](https://github.com/newling/rocm-libraries/commit/02730c0f103c971ddb9b14b79d16f2fd24949a21) | Use the Windows environment setter on Windows. |
| [3809ca52f32](https://github.com/newling/rocm-libraries/commit/3809ca52f3205359af037e5caa61a6b33eb0e0bb) | Document the scope of C++ tuning overrides and correct claims about shared search behavior. |

The commits address separate items and can be considered independently. The first two retain their previously validated implementation; the third changes documentation and comments only.

## Tests

The submitted and suggestion implementations build on Linux and pass command-line tune/repeat, C++ override, cache replay and environment-conflict checks on MI300X; the YAML counterexample fails before its fix and passes afterward, and padded/distinct-C-and-D numerical checks pass.

Additional second-pass probes rebuilt the exact submitted head and checked C++ split-K, repeated split-K options and WGM. Numerical verification passes; the logs confirm the option scope described below. QuickTune parses both ordinary and tuning output. Testing used a scoped, matching gfx942 library. Native Windows validation of the proposed fix and exhaustive datatype/epilogue coverage were omitted. The new prose was checked against these call paths and results; it needs no additional runtime test.

Separately, combining both siblings with the six implementation commits from [#12587](https://github.com/ROCm/rocm-libraries/pull/12587)–[#12590](https://github.com/ROCm/rocm-libraries/pull/12590) builds and passes the benchmark workflows: per-case settings reach version-2 rows, repeat runs reuse a winner, and widening four to eight candidates retunes. This checks sibling integration, without resolving [#12589](https://github.com/ROCm/rocm-libraries/pull/12589)'s precedence issue or incorporating current [#12586](https://github.com/ROCm/rocm-libraries/pull/12586).

CI remains red. The new Windows compile failure is linked below; the [cache-layer review](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12587.md) describes the inherited Windows/parser, packaging and other CI failures. Focused local results do not establish broad CI success.

## Summary

With `HIPBLASLT_TUNING_FILE` set, the benchmark first makes an untimed C-API call that invokes [#12588](https://github.com/ROCm/rocm-libraries/pull/12588)'s runtime search and saves its winner. It then queries selection again and benchmarks the selected solution. The command-line measurement settings configure the library search, whose budget is unlimited unless explicitly set.

Using one search implementation for offline and application tuning reduces duplicated selection logic. Supplying the full workspace limit to the tuning call also avoids restricting the search to the initial heuristic choice's smaller workspace requirement. Persistence moves out of result printing into the store's versioned writer.

This connects persistence ([#12586](https://github.com/ROCm/rocm-libraries/pull/12586)), replay ([#12587](https://github.com/ROCm/rocm-libraries/pull/12587)) and measurement ([#12588](https://github.com/ROCm/rocm-libraries/pull/12588)) to the benchmark frontend. It works independently of [#12589](https://github.com/ROCm/rocm-libraries/pull/12589); combining that sibling changes the rules for reusing an existing search.

## Actionable items

### Use a supported environment setter on Windows

At [`client.cpp:130`](https://github.com/ROCm/rocm-libraries/blob/bd3d79143c100a83b42003042b150cb0fab10780/projects/hipblaslt/clients/bench/src/client.cpp#L130), the new helper calls POSIX `setenv` unconditionally. The [Windows build](https://github.com/ROCm/rocm-libraries/actions/runs/36216990764/job/108340522435) fails with `error: use of undeclared identifier 'setenv'`. The benchmark cannot build, regardless of whether tuning is enabled.

Commit [02730c0f103](https://github.com/newling/rocm-libraries/commit/02730c0f103c971ddb9b14b79d16f2fd24949a21) uses `_putenv_s` under `WIN32`, following the client's existing portability convention, and retains `setenv` elsewhere. The Linux build passes; the Windows lane still needs to validate the proposed fix.

### Configure the tuner from each data-file case

At [`client.cpp:1034`](https://github.com/ROCm/rocm-libraries/blob/bd3d79143c100a83b42003042b150cb0fab10780/projects/hipblaslt/clients/bench/src/client.cpp#L1034), `main` initializes tuning settings from command-line `Arguments`. A `--data` run loads separate arguments for each case, but [`run_bench_test` at line 296](https://github.com/ROCm/rocm-libraries/blob/bd3d79143c100a83b42003042b150cb0fab10780/projects/hipblaslt/clients/bench/src/client.cpp#L296) starts tuning without applying those settings.

The library therefore searches using command-line defaults while the final benchmark uses the case's options. The reproducer below requests two and three candidates with flushing disabled. Given command-line `--requested_solution 4`, the submitted search measures four candidates in both cases with flushing enabled. Iteration counts and rotation can disagree too.

Commit [60687f478e8](https://github.com/newling/rocm-libraries/commit/60687f478e809fa8ca11f5a8bf72388b14adab28) applies each data case through `enter_library_tune_mode` before its search. Mode/path initialization remains early; search settings are read for each attempt. The reproducer then reports two and three candidates without flush calibration. Repeated occurrences of an already tuned shape still follow the runtime tuner's once-per-process policy.

## Suggestions

### Document which options apply to the search and to the final benchmark

At [`client.cpp:86`](https://github.com/ROCm/rocm-libraries/blob/bd3d79143c100a83b42003042b150cb0fab10780/projects/hipblaslt/clients/bench/src/client.cpp#L86), `tune_with_library` forces the tuning pass through the C API. C++ `--splitk` and `--wgm` overrides therefore apply only when benchmarking the already selected solution. The search measures each candidate with its defaults, and the saved row stores neither override.

The split-K grid probe confirms the consequence: an ordinary run benchmarks multiple algorithms with the requested split-K values, while tuning selects one algorithm first and then benchmarks only that algorithm with those values. All checked outputs remain numerically correct. This changes the scope of the offline search; the absence of override fields in the saved format itself predates this PR.

Commit [3809ca52f32](https://github.com/newling/rocm-libraries/commit/3809ca52f3205359af037e5caa61a6b33eb0e0bb) makes this limit explicit in the [offline-tuning guide at line 58](https://github.com/ROCm/rocm-libraries/blob/bd3d79143c100a83b42003042b150cb0fab10780/projects/hipblaslt/docs/how-to/how-to-use-hipblaslt-offline-tuning.rst#L58) and helper comment. It also corrects [`CHANGELOG.md:27`](https://github.com/ROCm/rocm-libraries/blob/bd3d79143c100a83b42003042b150cb0fab10780/projects/hipblaslt/CHANGELOG.md#L27) and [`client.cpp:112`](https://github.com/ROCm/rocm-libraries/blob/bd3d79143c100a83b42003042b150cb0fab10780/projects/hipblaslt/clients/bench/src/client.cpp#L112): sharing the search implementation cannot guarantee identical winners across different data, GPU conditions and timing noise. The comment now distinguishes cached mode/path from settings read per search. No new tuning API or file-format change is proposed.

## Commentary

The benchmark inherits runtime eligibility restrictions. The documentation commit points offline users to them, including in-place C/D with nonzero beta: benchmarking can succeed while tuning is skipped and no row is added.

The legacy writer disappears here, while the reader remains compatible with older, less specific rows. A legacy-reader removal policy belongs to the persistence layer. Also, the statement that an existing row is never retuned describes this head without [#12589](https://github.com/ROCm/rocm-libraries/pull/12589); after combining the siblings, search coverage and budget govern that decision.

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

The submitted version reports `['4', '4']` and flush calibration; the suggestion branch passes all three assertions. Use a fresh tuning file for each version. This reproducer is not registered in shared CI.

## C++ option-scope probe

Save the following as `probe_bench_options.py` and run `python3 probe_bench_options.py "$BUILD_DIR" "$RESULTS_DIR"`, using an empty results directory and a matching gfx942 device library with at least four supported FP16 candidates. It captures ordinary and tuning logs separately. An optional case name after those two paths, such as `splitk-grid`, selects one case.

```python
import json
import os
from pathlib import Path
import re
import subprocess
import sys

build, results = map(Path, sys.argv[1:3])
results.mkdir(parents=True, exist_ok=True)
env = {k: v for k, v in os.environ.items() if not k.startswith('HIPBLASLT_TUNING_')}
env.update(HIP_VISIBLE_DEVICES='0', HIPBLASLT_TENSILE_LIBPATH=str(build/'Tensile/library/gfx942'))
common = [str(build/'clients/hipblaslt-bench'), '--api_method', 'cpp', '--precision', 'f16_r',
          '-m', '128', '-n', '128', '-k', '128', '--alpha', '1', '--beta', '0',
          '--requested_solution', '4', '--iters', '2', '--cold_iters', '0', '--rotating', '0',
          '--verify', '--print_kernel_info']
cases = [('plain', []), ('splitk', ['--splitk', '2']), ('splitk-grid', ['--splitk', '1', '--splitk', '2', '--splitk', '4']),
         ('wgm', ['--wgm', '2'])]
for name, options in cases:
    if len(sys.argv) > 3 and name != sys.argv[3]:
        continue
    for tune in (False, True):
        label = name + ('-tune' if tune else '-ordinary')
        case_env = dict(env)
        if tune:
            path = results / f'{label}.tuning'
            assert not path.exists(), path
            case_env.update(HIPBLASLT_TUNING_FILE=str(path), HIPBLASLT_LOG_MASK='8')
        process = subprocess.run(common + options, env=case_env, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=90)
        (results/f'{label}.log').write_text(process.stdout)
        print(json.dumps(dict(case=label, status=process.returncode,
                              support=re.findall(r'Is supported (.+)',process.stdout),
                              selected=re.findall(r'--Solution index: (\d+)',process.stdout),
                              tune_winner=re.findall(r'tuning-done winner=(\d+)',process.stdout),
                              errors=[s for s in process.stdout.splitlines() if any(t in s for t in ['not support', 'Error', 'ERROR', 'Failed'])])), flush=True)
```

In the tuning logs, `tune_winner` contains one index and every subsequent `selected` entry is that same index. The full logs show the requested `Custom tuning: GSU` or `WGM` values applied afterward; ordinary logs contain multiple selected algorithm indexes. Candidate indexes and timings depend on the generated library and device. All completed probes returned status 0 with numerical verification enabled.

The branch contains the three mapped commits. The temporary GPU probes remain in these appendices; a shared-CI YAML regression, native Windows validation and predecessor fixes are outside this branch.
