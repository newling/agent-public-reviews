This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15594](https://github.com/ROCm/rocm-libraries/pull/15594), including prerequisite [ROCm/rocm-libraries#15593](https://github.com/ROCm/rocm-libraries/pull/15593).

Independent review, 2026-11-11, covering file loading, failure/retry behavior, callers, build configurations, and tests. Existing PR reviews and discussion were not consulted.

| PR | Reviewed head | Diff base |
| --- | --- | --- |
| #15594: Windows long paths | `3330fa8b3076eef2f79ea74861597e2d00a69338` | #15593 head below |
| #15593: failed shard loads | `3fa36e788838e54b1023a7572aba6df1404a46aa` | `4038d881161c6ff0209badcfce4fd0b5ad6f526c` on `develop` |

The combined suggestion branch is [review/pr15594-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15594-suggestions), based on [the reviewed #15594 head](https://github.com/ROCm/rocm-libraries/commit/3330fa8b3076eef2f79ea74861597e2d00a69338), with head [89f78cb7534](https://github.com/newling/rocm-libraries/commit/89f78cb753400447dca51cbd8f27eae5f6044a33). The [comparison against the reviewed head](https://github.com/newling/rocm-libraries/compare/3330fa8b3076eef2f79ea74861597e2d00a69338...89f78cb753400447dca51cbd8f27eae5f6044a33) contains all three suggestion commits. The local `review/pr15593-suggestions` branch remains at its reviewed head; no functional correction to #15593 was identified. The small include cleanup for its test file is included on the combined branch.

## Tests

The submitted combined head and the suggestion branch both build `hipblaslt-test`, `tensilelite-tests`, and `tensilelite-client` in the Linux Release configuration with local kernels enabled, using ROCm 7.1's compiler. Both pass the selected 57 indexed/compressed/shard-loading tests and 70 adapter/local-kernel/long-path tests. The first adapter run lacked the shipped-code-object fixture; supplying `HIPBLASLT_LOCAL_KERNEL_TEST_LIB_DIR` resolved that test's failure. Root pre-commit and changed-line formatting checks pass.

The YAML configuration exposes item 2. Linking the submitted `long_path_gtest.cpp` directly against the actual YAML `tensilelite-host` gives a segmentation fault in the uncompressed-library case and a failed expectation in the compressed-library case; its code-object case passes. With the suggestion, only the applicable code-object case is registered in that configuration, and it passes. The full YAML client build encountered an unchanged ExtOp dependency error (`Tensile/msgpack/Loading.hpp` cannot find `msgpack.hpp`), so this result comes from the standalone test translation unit, not a successful full YAML client build. The appendix preserves the exact probe.

The reviewed #15594 head has a successful [Windows build](https://github.com/ROCm/rocm-libraries/actions/runs/43113010379/job/130844569148), but its [Windows hipBLASLt test job](https://github.com/ROCm/rocm-libraries/actions/runs/43113010379/job/130875817680) was queued at the final check. There was no local Windows execution or sanitizer run. In particular, the Windows discovery fix in item 1 is supported by source and the Windows API contract, rather than an observed Windows before/after run.

The older red Multi-Arch summaries inspected correspond to cancelled builds. The failed #15593 secret scan reports matches in base commit `4038d881161`, with none in the submitted change. These are not evidence of defects in these two diffs.

## Summary

#15593 puts the failure check before a missing or unusable shard can publish state. Throwing from the placeholder's `std::call_once` initializer allows a later attempt to retry; the tests exercise repeated failures and recovery after the file appears. The index lookup retains its existing no-solution convention and also leaves the failed shard unrecorded. I found no functional issue in this part of the stack.

#15594 addresses the separate cause of those failures: Windows file paths that exceed `MAX_PATH`. Converting paths at the file operation, and reading long-path code objects before calling `hipModuleLoadData`, are appropriate approaches. The single module-loading helper covers ordinary loads, local kernels, and rotation copies. Its test checks the supplied bytes and module cleanup. The remaining product issue is that discovery can reject a long path before this helper or the library loader is reached.

Host tests are appropriate for the shard error handling; Windows tests are essential for the path conversion. Adjacent loader, retry, and module-ownership tests were included in the local checks. Neither PR changes kernel arithmetic, so an architecture-wide numerical sweep is not needed for these changes. Tests are present, and no test waiver or feature flag is needed.

## Actionable items

### Apply long-path handling before library discovery

In #15594, [tensile_host.cpp:3384](https://github.com/ROCm/rocm-libraries/blob/3330fa8b3076eef2f79ea74861597e2d00a69338/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L3384) still checks the architecture-specific library using an unconverted path. The [master-file preflight at line 3461](https://github.com/ROCm/rocm-libraries/blob/3330fa8b3076eef2f79ea74861597e2d00a69338/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L3461) does the same. Directory discovery in [rocblaslt_auxiliary.cpp:3681](https://github.com/ROCm/rocm-libraries/blob/3330fa8b3076eef2f79ea74861597e2d00a69338/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp#L3681) has the corresponding problem for a sufficiently deep library directory.

Consider a valid install whose `TensileLibrary_lazy_gfx1151.dat.zlib` path is 270 characters, in a process without long-path opt-in. These checks execute before `LoadLibraryFilePreload`. MSVC's `std::filesystem::exists` passes the path to `GetFileAttributesExW`, whose [documented default limit is MAX_PATH](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileattributesexw). Thus discovery/preflight can fail or throw before the new file-opening code can help. The new tests call the loader directly and bypass these checks.

These checks predate the PR. They do not negate the fix for the reported case where only the longer shard names cross the limit, but they leave deeper installations unsupported by the proposed long-path fix. Apply the same conversion to discovery, the master-file probes, and the non-lazy directory traversal.

Implemented in commit [9a0188f0cfa](https://github.com/newling/rocm-libraries/commit/9a0188f0cfa781ceb8e2008c120a6bf639edc1a7); final formatting is in [89f78cb7534](https://github.com/newling/rocm-libraries/commit/89f78cb753400447dca51cbd8f27eae5f6044a33). The affected library and clients build on Linux. A Windows test through normal library initialization, with the master path itself beyond the limit and process opt-in disabled, is still needed. No end-to-end Windows regression test was added locally.

### Restrict the binary library fixtures to MessagePack builds

The two library cases in [long_path_gtest.cpp:142](https://github.com/ROCm/rocm-libraries/blob/3330fa8b3076eef2f79ea74861597e2d00a69338/projects/hipblaslt/clients/tests/src/long_path_gtest.cpp#L142) are registered unconditionally. Both write MessagePack data, but `HIPBLASLT_ENABLE_YAML=ON` makes `LoadLibraryFile` use the LLVM YAML reader. That reader cannot load these fixtures, and it does not implement the MessagePack loader's `.zlib` fallback.

This is reproducible with the submitted test source and the configured YAML library: `smoke_LoadsUncompressedLibrary` terminates with SIGSEGV after a YAML diagnostic; `smoke_LoadsCompressedLibrary` returns null and fails its expectation. The code-object case is independent of the serialization backend and passes.

Implemented in commit [e48062d98f0](https://github.com/newling/rocm-libraries/commit/e48062d98f011929a10a840fe392f9820e84b1ba): compile the MessagePack fixture builders and the two library cases only under `TENSILE_MSGPACK`, while keeping the code-object case in both configurations. The MessagePack configuration retains all three tests; the YAML probe registers and passes the code-object test.

## Suggestions

Add the direct `<utility>` dependency for `std::move` in [long_path_gtest.cpp:175](https://github.com/ROCm/rocm-libraries/blob/3330fa8b3076eef2f79ea74861597e2d00a69338/projects/hipblaslt/clients/tests/src/long_path_gtest.cpp#L175) and the changed [IndexedLibraryLoad_test.cpp](https://github.com/ROCm/rocm-libraries/blob/3fa36e788838e54b1023a7572aba6df1404a46aa/projects/hipblaslt/tensilelite/tests/IndexedLibraryLoad_test.cpp). Also describe the long-path fixture's purpose without recounting earlier fixes. These optional changes, and formatting of the discovery fix, are implemented in [89f78cb7534](https://github.com/newling/rocm-libraries/commit/89f78cb753400447dca51cbd8f27eae5f6044a33).

## Scope decisions

The different failure results in #15593 are retained deliberately: placeholder queries propagate an initialization error, while an index lookup can report no solution. Both paths permit retry. There is no reason to change that policy as part of the null-dereference fix.

Adding `ModuleApi::loadData` changes `SolutionAdapter`'s layout, as the description acknowledges. Consumers compiled against the old exported header must be rebuilt; the checks here cover the in-tree library and clients built together. This review does not establish compatibility with independently built binaries.

## Handoff

The suggestions are published on [review/pr15594-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15594-suggestions) at [89f78cb7534](https://github.com/newling/rocm-libraries/commit/89f78cb753400447dca51cbd8f27eae5f6044a33): [e48062d98f0](https://github.com/newling/rocm-libraries/commit/e48062d98f011929a10a840fe392f9820e84b1ba) fixes the YAML tests, [9a0188f0cfa](https://github.com/newling/rocm-libraries/commit/9a0188f0cfa781ceb8e2008c120a6bf639edc1a7) fixes discovery/preflight paths, and [89f78cb7534](https://github.com/newling/rocm-libraries/commit/89f78cb753400447dca51cbd8f27eae5f6044a33) contains the optional cleanup. Windows runtime validation, including a regression through normal library discovery, remains outstanding.

## Appendix: reproduce the YAML test failure

Start with a configured hipBLASLt host/client build and static GoogleTest libraries. Enable compilation-command export and the YAML backend, supplying the installed LLVM CMake package when necessary:

```sh
cmake -S "$SRC_DIR/projects/hipblaslt" -B "$BUILD_DIR" \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DHIPBLASLT_ENABLE_YAML=ON \
  -DLLVM_DIR="$LLVM_CMAKE_DIR"
cmake --build "$BUILD_DIR" --target tensilelite-host --parallel 8
python3 yaml_probe.py "$BUILD_DIR" "$GTEST_LIB_DIR" "$PROBE_DIR" \
  --revision 3330fa8b3076eef2f79ea74861597e2d00a69338
```

The script below uses the generated compiler arguments and the PR's exact test source. It links only the test translation unit, GoogleTest, HIP, and the built TensileLite library, avoiding the unrelated ExtOp build error. It disables core dumps and runs the three cases separately. To check the suggestion, omit `--revision` while the suggestion branch is checked out; the single applicable YAML case must run and pass.

```python
import argparse
import json
from pathlib import Path
import resource
import shlex
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('build', type=Path)
parser.add_argument('gtest_lib', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--revision')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
entry = next(e for e in json.loads((args.build / 'compile_commands.json').read_text())
             if e['file'].endswith('/long_path_gtest.cpp'))
command = shlex.split(entry['command'])
assert '-DTENSILE_YAML' in command
command[command.index('-o') + 1] = str(args.output / 'probe.o')
if args.revision:
    source = Path(entry['file'])
    root = subprocess.check_output(['git', '-C', str(source.parent),
                                    'rev-parse', '--show-toplevel'], text=True).strip()
    snapshot = args.output / 'long_path_gtest.cpp'
    snapshot.write_bytes(subprocess.check_output(
        ['git', '-C', root, 'show', f'{args.revision}:{source.relative_to(root)}']))
    command[command.index('-c') + 1] = str(snapshot)
command = [a for a in command if not a.startswith('--offload-arch=')]
command.append('--offload-host-only')
subprocess.run(command, cwd=args.build, check=True)
binary = args.output / 'probe'
rocm = Path(command[0]).parent.parent
subprocess.run([command[0], str(args.output / 'probe.o'), '-o', str(binary),
                f'-L{args.build}/tensilelite', f'-Wl,-rpath,{args.build}/tensilelite',
                '-ltensilelite-host', str(args.gtest_lib / 'libgtest_main.a'),
                str(args.gtest_lib / 'libgtest.a'), f'-L{rocm}/lib',
                f'-Wl,-rpath,{rocm}/lib', '-lamdhip64', '-pthread'], check=True)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
cases = ['smoke_LoadsUncompressedLibrary', 'smoke_LoadsCompressedLibrary',
         'smoke_LoadsCodeObject'] if args.revision else ['*']
for case in cases:
    with (args.output / f'{case.replace("*", "all")}.log').open('w') as log:
        result = subprocess.run([str(binary), f'--gtest_filter=LongPathLoading.{case}'],
                                stdout=log, stderr=subprocess.STDOUT)
    print(case, result.returncode)
```
