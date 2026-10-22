This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14024](https://github.com/ROCm/rocm-libraries/pull/14024)

Reviewed head: [1060a68208b](https://github.com/ROCm/rocm-libraries/commit/1060a68208b295563a2cc2827d72554a4dfb5063). Incremental base: [75b7cd394ad](https://github.com/ROCm/rocm-libraries/commit/75b7cd394adcdd50638161a880ae0279db662716), the head of stacked [#14023](https://github.com/ROCm/rocm-libraries/pull/14023).

Local suggestion branch: `review/pr14024-suggestions`, based on that exact reviewed head. The two additional commits remain local; their published patches can be inspected and applied independently:

| Commit | Review item |
| --- | --- |
| [33722a2af67](patches/pr14024-33722a2af67.patch) | Apply strict verification to datafile runs |
| [b0a023fcef1](patches/pr14024-b0a023fcef1.patch) | Describe the GEMM tolerance accurately |

## Tests

Submitted benchmark and test targets build; HostUnit and BenchVerify pass. Both suites pass with the suggestions, including the added setup and mixed-precision cases; the dispatch reproducer changes from exit 0/1 to exit 2 as described below.

Local compilation used ROCm 7.1 and the focused host/client build. A real GEMM run on gfx1201 could not use the installed device library: the PR's loader expects `TensileLiteLibrary_lazy_gfx1201_Mapping.dat`, which the older installed library lacks. With `HIPBLASLT_TENSILE_LIBPATH=$ROCM_PATH/lib/hipblaslt/library`, both single-run and datafile attempts report `Could not initialize Tensile library mapping` and terminate with SIGSEGV before verification. This is an incompatible local artifact, not evidence against this diff. The initial gfx90a client build also could not launch its initialization code on gfx1201; rebuilding with both `GPU_TARGETS` and cached `GPU_BUILD_TARGETS` set to gfx1201 resolves that earlier mismatch.

The reviewed head has passing [TheRock hipBLASLt gfx942 and Windows GPU lanes](https://github.com/ROCm/rocm-libraries/actions/runs/39473778927), [gfx90a ASAN](https://github.com/ROCm/rocm-libraries/actions/runs/39468403586), component checks and pre-commit. Root pre-commit also completes locally, although its hooks select no applicable files for these client changes. Full device-library generation and a broad local GPU suite were omitted; the relevant host-buffer checks and CLI dispatch probe provide the local evidence.

The overall CI result is red. The [gfx1250-strict job](https://github.com/ROCm/rocm-libraries/actions/runs/39510959697/job/118931739498) builds hipBLASLt and passes its tests, then fails the TensileLite common case `gemm/gfx12/decouple_pgr_tdm_fuse_gfx1250.yaml`: `test_config_build` exceeds the 600-second pytest timeout. The [same lane on the incremental base](https://github.com/ROCm/rocm-libraries/actions/runs/39510862006/job/118931434972) passes. The timed-out build does not run the changed benchmark/check code, but the timeout's cause remains unconfirmed; this is not a fully green validation result.

The [MIOpen gfx942 failures](https://github.com/ROCm/rocm-libraries/actions/runs/39473778927/job/118908734475) include its FP8/BFP8 hipBLASLt integration cases; one reports relative error `0.16524330327301656` against `0.07` at `projects/miopen/test/gtest/hipblaslt_gemm.cpp:235`. All four corresponding MIOpen shards also fail on [the incremental base](https://github.com/ROCm/rocm-libraries/actions/runs/39473794425). This PR changes client comparison code, which those library consumers do not use. [Project coverage](https://app.codecov.io/gh/ROCm/rocm-libraries/pull/14024) is `64.36%` against an `80.00%` target; that check is also red on the base. Neither signal establishes a regression from this client-only diff.

## Summary

The benchmark gains an optional exit status for failed CPU-reference comparisons of result D. Failed norm and element comparisons accumulate across problems and solutions; a previously successful process exits 2 in strict mode, while an existing error retains its code.

The per-batch norm decision is a useful choice: accurate batches can produce a large summed reporting value without any individual batch violating its limit. The pointer-array correction also makes the reported sum count each batch once. Direct tests exercise both behaviors, and the new option leaves default exit handling intact.

Host unit tests are the appropriate level for exit-code precedence and option setup. The existing `check()` tests add useful coverage of batch traversal and actual failure counting. No waiver is needed for these client-only changes: tests are present, strict mode is optional, and the pointer-array fix has a direct regression case. Adjacent checks should cover datafile dispatch and mixed-precision tolerances, as below; a kernel-generation or unrelated subsystem test sweep is not warranted by this diff.

## Actionable items

### Apply strict verification to datafile runs

At [`clients/bench/src/client.cpp:1056`](https://github.com/ROCm/rocm-libraries/blob/1060a68208b295563a2cc2827d72554a4dfb5063/projects/hipblaslt/clients/bench/src/client.cpp#L1056), datafile mode returns before the strict-mode setup at [line 1318](https://github.com/ROCm/rocm-libraries/blob/1060a68208b295563a2cc2827d72554a4dfb5063/projects/hipblaslt/clients/bench/src/client.cpp#L1318). `run_bench_test()` disables unit checks but leaves each record's norm and allclose settings intact. A YAML/data record with both settings zero therefore runs without comparison under `--verify_strict`, and the failure counter remains zero. The option's promise to imply verification does not hold for `--data` or `--yaml`.

A record with `norm_check: 1` and the default `norm_check_assert: true` has a related problem. A failed norm invokes `CHECK_SUCCESS` before the new counter increment, exiting 1 immediately. It cannot collect all failures or report the promised strict exit 2.

Move strict verification setup into the shared dispatch path, after loading each record. Enable both D comparisons and disable the immediate norm assertion when strict mode is active. Preserve datafile verification settings in default mode.

Commit [33722a2af67](patches/pr14024-33722a2af67.patch) implements this through `apply_strict_verification()` in `hipblaslt_bench_options`, called by `run_bench_test()`. The HostUnit cases cover disabled comparisons, an enabled immediate assertion, and default-mode preservation. A probe retaining the original parser and dispatch but replacing GEMM execution with a failure recorder confirms the submitted datafile path has `norm=0 allclose=0 assert=1` and exits 0. With an enabled norm assertion it exits 1. Both strict cases reach `norm=1 allclose=1 assert=0` and exit 2 with the fix. The exact probe is below.

## Suggestions

### Describe the GEMM tolerance accurately

At [`clients/bench/README.md:128`](https://github.com/ROCm/rocm-libraries/blob/1060a68208b295563a2cc2827d72554a4dfb5063/projects/hipblaslt/clients/bench/README.md#L128) and [`docs/conceptual/hipblaslt-clients.rst:64`](https://github.com/ROCm/rocm-libraries/blob/1060a68208b295563a2cc2827d72554a4dfb5063/projects/hipblaslt/docs/conceptual/hipblaslt-clients.rst#L64), the limit is described as belonging to the output type. The diagnostic at [`testing_matmul.hpp:1492`](https://github.com/ROCm/rocm-libraries/blob/1060a68208b295563a2cc2827d72554a4dfb5063/projects/hipblaslt/clients/common/include/testing_matmul.hpp#L1492) likewise labels it with that type.

The implementation actually takes the largest tolerance among the output and input types, with an additional 0.5 allowance for f32 output using `HIPBLAS_COMPUTE_32F_FAST_16BF`. For example, f16 inputs and f32 output use 0.01, not the documented f32 limit of 1e-5. The added host-buffer case passes an approximately 0.001 relative error for that combination. A user interpreting strict mode as enforcing the output-type threshold would draw the wrong conclusion from a successful run.

Keep the existing numerical policy and describe the tolerance as a GEMM limit, including its input-type and compute-mode dependence. Commit [b0a023fcef1](patches/pr14024-b0a023fcef1.patch) updates both documents and the diagnostic, and adds a focused mixed-precision check. It does not change which results pass.

## Commentary

The strict counter covers D's norm and allclose checks. It does not cover auxiliary output, gradient bias or amaxD. That scope is explicit in the PR description and is reasonable for this slice.

The finite-data batch and counterexample pass did not establish another correctness defect. Matching and mismatching non-finite values remain governed by the existing comparators: strict mode rejects a NaN norm, while allclose has its own special-value behavior. This PR does not define a new non-finite equality policy. The norm-tolerance extraction preserves the previous type and compute-mode rules.

The suggestion branch remains local; the patches above are published with this review. The two commits implement the bounded findings; matching device-library validation remains omitted for the local environment reason above. No PR-description rewrite was produced.

## Dispatch reproducer

Configure and build the PR's `hipblaslt-bench` target with `CMAKE_EXPORT_COMPILE_COMMANDS=ON`, using a client build for the visible GPU. Set `SRC_DIR` to the repository root, `BUILD_DIR` to the standalone hipBLASLt build, and `PROBE_DIR` to an out-of-source directory. This probe deliberately replaces GEMM execution; it tests CLI parsing, loaded `Arguments`, dispatch and exit handling, not GPU arithmetic.

Save this as `$PROBE_DIR/no-verification.yaml`:

```yaml
---
include: hipblaslt_common.yaml
Tests:
- name: strict_datafile
  function: matmul
  a_type: f32_r
  b_type: f32_r
  c_type: f32_r
  d_type: f32_r
  compute_type: c_f32_r
  transA: N
  transB: N
  scale_type: f32_r
  M: 8
  N: 4
  K: 8
  norm_check: 0
  allclose_check: 0
```

Generate its binary data using the configured Python environment:

```bash
python "$SRC_DIR/projects/hipblaslt/clients/tests/hipblaslt_gentest.py" \
  -I "$SRC_DIR/projects/hipblaslt/clients/tests/data" \
  -I "$SRC_DIR/projects/hipblaslt/clients/common/include" \
  -o "$PROBE_DIR/no-verification.data" "$PROBE_DIR/no-verification.yaml"
```

The following standalone Python script uses the build's actual compile and link commands. Its replacement body is the complete minimal failure recorder used for the assertion-sensitive reproduction:

```python
import json
import os
from pathlib import Path
import shlex
import subprocess

src = Path(os.environ['SRC_DIR']).resolve()
build = Path(os.environ['BUILD_DIR']).resolve()
probe_dir = Path(os.environ['PROBE_DIR']).resolve()
probe_dir.mkdir(parents=True, exist_ok=True)
client = src / 'projects/hipblaslt/clients/bench/src/client.cpp'
text = client.read_text()
old = '        testing_matmul(arg);'
recorder = '''        std::cout << "RECORDER norm=" << int(arg.norm_check)
                  << " allclose=" << int(arg.allclose_check)
                  << " assert=" << arg.norm_check_assert << std::endl;
        if(arg.norm_check)
        {
            if(arg.norm_check_assert) CHECK_SUCCESS(false);
            ++hipblaslt_bench_options::verification_failures();
        }
        if(arg.allclose_check) ++hipblaslt_bench_options::verification_failures();'''
assert text.count(old) == 1
probe = probe_dir / 'client-recorder.cpp'
probe.write_text(text.replace(old, recorder, 1))
entry = next(e for e in json.loads((build / 'compile_commands.json').read_text())
             if Path(e['file']).resolve() == client)
compile_args = shlex.split(entry['command'])
compile_args[compile_args.index(str(client))] = str(probe)
obj = probe_dir / 'client-recorder.o'
compile_args[compile_args.index('-o') + 1] = str(obj)
subprocess.run(compile_args, cwd=build, check=True)
link = subprocess.check_output(
    ['ninja', '-t', 'commands', 'hipblaslt-bench'], cwd=build, text=True
).splitlines()[-1]
assert link.startswith(': && ') and link.endswith(' && :')
link_args = shlex.split(link[len(': && '):-len(' && :')])
original_obj = 'clients/CMakeFiles/hipblaslt-bench.dir/bench/src/client.cpp.o'
link_args[link_args.index(original_obj)] = str(obj)
exe = probe_dir / 'client-recorder'
link_args[link_args.index('-o') + 1] = str(exe)
subprocess.run(link_args, cwd=build, check=True)
for args in [
    ['--verify_strict', '-m', '8', '-n', '4', '-k', '8'],
    ['--data', str(probe_dir / 'no-verification.data'), '--verify_strict'],
    ['--data', str(probe_dir / 'no-verification.data')],
]:
    result = subprocess.run([str(exe), *args])
    print(args, 'exit', result.returncode)
```

The submitted head exits 2 for the single-run control, 0 for strict datafile mode, and 0 for default datafile mode. With [33722a2af67](patches/pr14024-33722a2af67.patch), those statuses are 2, 2 and 0. To reproduce the immediate-assertion variant, change the YAML to `norm_check: 1` and add `norm_check_assert: true`, regenerate the data and repeat. The submitted strict datafile run then exits 1; the suggestion exits 2 and reports both failed checks.
