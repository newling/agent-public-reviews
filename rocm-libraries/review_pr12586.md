This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12586](https://github.com/ROCm/rocm-libraries/pull/12586)

Reviewed head: `ce54ac0b7db8c845d943ac48f69afb40f19d429c`, branch `tuning-split/2-cache-store`. This review covers the increment from `1bade4e6c6e9454c707d7bf24d2d9b24da5735b6`, its embedded predecessor from [#12585](https://github.com/ROCm/rocm-libraries/pull/12585). It is the second split from [#10424](https://github.com/ROCm/rocm-libraries/pull/10424). The accepted name-validation policy from the predecessor is taken as given.

This review records the stacked revision above. The reviewer plans to revisit it after rebasing onto `origin/develop`, once it is first in the stack.

Local suggestion branch: `review/pr12586-suggestions`, based on the exact reviewed head, with these separate commits:

| Item | Local commit | Change |
| --- | --- | --- |
| Actionable 1 | `98f64d81241941454eea2da35a0e1d42e3bcbb6b` | Remove DLL import/export annotations from private inline type parsers |
| Actionable 2 | `fd20b5c944d4d796350e24115cd496298b91ed89` | Rename the test executable to match TheRock's artifact rules |
| Suggestion 1 | `1e50f40f5823efa3d1683973a3b0ec06873b55d5` | Preserve solution names when writing a tuning row, with regression tests |

The commits are independently applicable. The suggestion branch remains local and unpublished; its commit IDs can be inspected with `git show` in that checkout. Source links below refer to the submitted head.

## Tests

The submitted head and suggestion branch both passed the Linux host-library build and complete `TuningStore.*` suite; the suggestion branch also passed the generated CTest artifact-layout smoke check and whitespace checks.

Local builds used Release, ROCm 7.1, and `HIPBLASLT_ENABLE_DEVICE=OFF`. No GPU matmul tests or full native Windows build were run locally. A Windows-target Clang linkage probe confirmed the import problem and the effect of removing the annotations; its source is preserved below. The artifact-layout check used the generated install-time CTest file and locally available host libraries, so it verifies executable selection and relative paths, not a complete downloaded ROCm distribution.

CI at the reviewed head has the Windows link failure and Linux missing-executable failure detailed below. The gfx90a ASAN build/test lane passed. Other GPU and Math CI failures remain undiagnosed; these fixes do not establish that all CI failures are resolved. Root and component pre-commit commands completed successfully, but the configured hooks do not format these hipBLASLt C++ files and selected no relevant TensileLite tests.

## Summary

The PR separates tuning-file storage from GPU execution and gives new rows a versioned format. A row associates a matrix-multiplication problem with a previously selected kernel. The problem key grows from ten to 48 fields, distinguishing layouts, output types, epilogues, scaling, scheduling preferences, and devices that previously shared a key. Both C and C++ now use one key builder; C++ retains its result and updates preferences applied after construction.

Existing benchmark files continue to match on the historical ten fields through a separate legacy map. Current-format rows require the expanded fields and a recorded name, and unknown schemas are rejected. The existing override path reads through this store immediately; production use of the new writer comes later in the stack.

This is a reasonable foundation for the next tuning changes. The separate store makes parsing, compatibility, ordering, and persistence testable without executing a GPU kernel. Keeping the legacy map separate also makes the compatibility policy visible. The concrete fixes below are small and do not require changing that design.

For the incremental PR, the line changes are:

| Area | Added | Removed |
| --- | ---: | ---: |
| Production source, including comments and moved helpers | 1,496 | 677 |
| Tests and test-category YAML | 598 | 0 |
| CMake build/test integration | 66 | 1 |
| Separate documentation files | 0 | 0 |
| **Total** | **2,160** | **678** |

The suggestion branch adds 22 lines and removes 7 across all three fixes, including 16 added test lines.

## Actionable items

### 1. Keep the standalone type parsers free of DLL imports

Location: [`projects/hipblaslt/library/src/amd_detail/include/hipblaslt_type_strings.hpp`, lines 14 and 56](https://github.com/ROCm/rocm-libraries/blob/ce54ac0b7db8c845d943ac48f69afb40f19d429c/projects/hipblaslt/library/src/amd_detail/include/hipblaslt_type_strings.hpp#L14).

The two moved `constexpr` helpers retain `HIPBLASLT_EXPORT`. The new static store target is compiled without `hipblaslt_EXPORTS`, so on Windows these definitions become `__declspec(dllimport)`. The standalone test links the store without hipBLASLt and cannot resolve the imports.

The [Windows CI build](https://github.com/ROCm/rocm-libraries/actions/runs/36216991402/job/108339855332) fails while linking `clients/hipblaslt-tuning-store-test.exe`:

```text
lld-link: error: undefined symbol: __declspec(dllimport) ... string_to_hipblas_computetype(...)
lld-link: error: undefined symbol: __declspec(dllimport) ... string_to_hip_datatype(...)
```

Remove the export annotations from these private inline definitions. Commit `98f64d81241` does that. The targeted Windows compilation changes both helpers from DLL imports to local inline definitions, and the Linux library and store tests still build and pass. The existing standalone test target provides the Windows regression check; the native CI build needs rerunning after the fix.

### 2. Include the new test executable in the test artifact

Locations: [`projects/hipblaslt/clients/CMakeLists.txt`, line 238](https://github.com/ROCm/rocm-libraries/blob/ce54ac0b7db8c845d943ac48f69afb40f19d429c/projects/hipblaslt/clients/CMakeLists.txt#L238), [`projects/hipblaslt/CMakeLists.txt`, line 709](https://github.com/ROCm/rocm-libraries/blob/ce54ac0b7db8c845d943ac48f69afb40f19d429c/projects/hipblaslt/CMakeLists.txt#L709), and [`projects/hipblaslt/clients/tests/CMakeLists.txt`, line 53](https://github.com/ROCm/rocm-libraries/blob/ce54ac0b7db8c845d943ac48f69afb40f19d429c/projects/hipblaslt/clients/tests/CMakeLists.txt#L53).

TheRock's [BLAS artifact manifest at the revision used by this CI run](https://github.com/ROCm/TheRock/blob/703336a7482c9ce323cd3608f34cbd2124820600/math-libs/BLAS/artifact-blas.toml) includes `bin/hipblaslt-test*` and `bin/hipblaslt/**`. The installed CTest file matches the second rule, but `bin/hipblaslt-tuning-store-test` matches neither. Consequently, the test definition reaches the test machine without its executable.

The [Linux gfx942 shard 2 log](https://github.com/ROCm/rocm-libraries/actions/runs/36216991402/job/108344080905) reports:

```text
Start 7: hipblaslt-tuning-store-test_standard_suite
Could not find executable ../hipblaslt-tuning-store-test
```

Rename the target to `hipblaslt-test-tuning-store` and update its link, install, and CTest references. Commit `fd20b5c944d` makes those changes and updates the category-file comment. This follows the existing artifact convention without needing a companion TheRock change. I verified the old name is excluded and the new name included by the manifest, then successfully ran the generated standard-suite CTest entry from a staged `bin/hipblaslt` layout.

## Suggestions

### 1. Preserve solution names through the writer

Location: [`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/TuningCacheStore.cpp`, lines 494–497](https://github.com/ROCm/rocm-libraries/blob/ce54ac0b7db8c845d943ac48f69afb40f19d429c/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/TuningCacheStore.cpp#L494).

The parser accepts a current row with either a kernel name or a solution name, and `TunedEntry::sameIdentity` compares both. However, `formatTuningRow` writes only the kernel name. A solution-name-only entry becomes a row the reader rejects; an entry with both names loses one identity field.

Commit `1e50f40f582` adds the `solution_name` column and covers both cases. Against the submitted writer, the tests reproduce a missing solution name and zero accepted rows, respectively; both pass with the fix. This is a smaller API consistency improvement because the writer has no production caller in this PR, and ordinary kernel-name entries already round-trip. It is not evidence that existing override replay fails.

## Commentary

The direct store tests are appropriate for this change: they exercise real parsing and lookup, including schema rejection, damaged rows, legacy matching, duplicate identity, and append/read behavior. Their principal limit is that they construct keys manually. They do not establish that real C and C++ calls produce equivalent expanded keys or keep cached preferences synchronized. The description explicitly schedules those integration checks with tune mode in [#12588](https://github.com/ROCm/rocm-libraries/pull/12588); that is a reasonable division, provided that coverage accompanies the production writer.

The expanded key identifies the problem, while the name check identifies the selected library entry under the already accepted policy. The PR does not establish binary equivalence across builds. Stronger fingerprints remain separate follow-up work. The writer also explicitly limits synchronization to writers within one process, so concurrent processes sharing a file are outside its supported contract.

All bounded findings above are implemented on `review/pr12586-suggestions`, ending at `1e50f40f5823efa3d1683973a3b0ec06873b55d5`. Broader runtime integration tests and stronger identity mechanisms are intentionally left to their respective follow-ups.

## Appendix: Windows linkage probe

The linked CI failure uses the PR's existing test target. This supplementary probe isolates the annotation effect without a Windows SDK. It compiles the actual submitted helper bodies with minimal declarations for their argument and return types; it does not validate the real Windows headers, ABI, or final link. Run the following Python with `SRC_DIR` set to the repository, `BUILD_DIR` to a scratch directory, and `CLANGXX` to Clang with the Windows target enabled. It was checked with Clang 20. Expected output is two DLL imports before the change and two local inline definitions afterward.

```python
import os
import re
import subprocess
from pathlib import Path

src = Path(os.environ['SRC_DIR'])
probe = Path(os.environ['BUILD_DIR']) / 'windows-helper-probe'
(probe / 'include/hipblaslt').mkdir(parents=True, exist_ok=True)
path = 'projects/hipblaslt/library/src/amd_detail/include/hipblaslt_type_strings.hpp'
header = subprocess.check_output(
    ['git', '-C', str(src), 'show', 'ce54ac0b7db8c845d943ac48f69afb40f19d429c:' + path],
    text=True)
(probe / 'include/string').write_text(
    '#pragma once\nnamespace std { class string {}; '
    'bool operator==(const string&, const char*); }\n')
types = sorted(set(re.findall(r'\bHIP_[RC]_\w+', header)))
compute = sorted(set(re.findall(r'\bHIPBLAS_COMPUTE_\w+', header)))
(probe / 'include/hipblaslt/hipblaslt.h').write_text(
    '#pragma once\n#define HIPBLASLT_EXPORT __declspec(dllimport)\n'
    'enum hipDataType {' + ','.join(types + ['HIPBLASLT_DATATYPE_INVALID']) + '};\n'
    'enum hipblasComputeType_t {'
    + ','.join(compute + ['HIPBLASLT_COMPUTE_TYPE_INVALID']) + '};\n')
for mode in ['before', 'after']:
    text = header if mode == 'before' else header.replace('HIPBLASLT_EXPORT\n', '')
    (probe / (mode + '.hpp')).write_text(text)
    (probe / (mode + '.cpp')).write_text(
        '#include "' + mode + '.hpp"\n'
        'hipDataType parseType(const std::string& s) { return string_to_hip_datatype(s); }\n'
        'hipblasComputeType_t parseCompute(const std::string& s) '
        '{ return string_to_hipblas_computetype(s); }\n')
    subprocess.run([
        os.environ.get('CLANGXX', 'clang++'), '--target=x86_64-pc-windows-msvc',
        '-std=c++17', '-nostdinc++', '-I' + str(probe / 'include'),
        '-S', '-emit-llvm', str(probe / (mode + '.cpp')),
        '-o', str(probe / (mode + '.ll'))], check=True)
    declarations = [line for line in (probe / (mode + '.ll')).read_text().splitlines()
                    if line.startswith(('declare ', 'define ')) and 'string_to_' in line]
    assert len(declarations) == 2
    assert all(('dllimport' in line) == (mode == 'before') for line in declarations)
    print(mode + ': ' + ('two DLL imports' if mode == 'before' else 'two local inline definitions'))
```
