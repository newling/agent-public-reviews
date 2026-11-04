This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#15008](https://github.com/ROCm/rocm-systems/pull/15008)

**Reviewed head:** `803ad699c317188b04ad486db60024aeaa5e10bb`, verified unchanged on 2026-11-04. The comparison baseline is its parent, `01793658f83`.

**Suggestion branch:** [review/pr15008-suggestions](https://github.com/newling/rocm-systems/tree/review/pr15008-suggestions), based directly on the reviewed head.

| Commit | Review item | Change |
| --- | --- | --- |
| [4adcc57aaf840911a1e8a0181177445136253e54](https://github.com/newling/rocm-systems/commit/4adcc57aaf840911a1e8a0181177445136253e54) | Suggestion 1 | Add focused GCC LTO and Clang ThinLTO CI jobs for the existing decoding and symbol-boundary tests. |

## Tests

All eight selected tests pass in Clang 23.1 Release, GCC 13.3 Release with LTO, and Clang/LLD 20.1.2 Release with ThinLTO; 22 additional compiled-fixture checks behave as expected with GNU and LLVM `nm`; the suggestion workflow passes actionlint and changed-file pre-commit checks.

The eight tests are the decoding smoke test and the seven symbol checks listed in the timing table below. Their binaries were built from the submitted production and test sources. The suggestion adds only a workflow: its configure settings, build targets and CTest selection were exercised locally for both LTO compiler families. The hosted workflow itself has not been dispatched, and its Ubuntu-provided Clang version was not reproduced locally. Configuration logs confirmed `-flto=auto` for GCC and `-flto=thin` for Clang, rather than silently falling back to a non-LTO build.

The original failure is reproducible with GCC 13.3 LTO. Applying the parent scripts and their original test arguments to the same binaries makes `ModelOnlyIsaTest.SymbolBoundary`, `Gfx1250B0ToA0Library.SymbolBoundary`, `StaticAnalysis.SymbolBoundary`, and `IsaRegistryCompositionTest.NarrowSymbolBoundary` fail because `cdna5::Decoder::decode` is absent. The submitted scripts pass, and `ModelOnlyIsaTest.DecodesWithoutExecutionCallback` confirms that decoding still works. The parent scripts also pass on the tested non-LTO Clang and Clang ThinLTO binaries: the failure depends on the compiler's optimization decisions.

The additional fixtures cover defined, missing, imported and weak-imported factories; misleading namespace prefixes and overloads; forbidden execution definitions and imports; and the narrow registry's required export and exclusion of other architectures. These are separate checker-contract experiments, not added repository tests.

Clang 23's local LLD could not start because its installed ICU 70 runtime libraries were missing. The ThinLTO run therefore used the working Clang/LLD 20 installation. This configuration issue occurred before project compilation. All four existing hosted rocjitsu corpus configurations passed when inspected. A full local emulator/corpus or sanitizer run was omitted because the PR changes only symbol-check scripts and their arguments.

## Summary

The shared checker now verifies that each requested decoder factory has a definition in the inspected binary. The required names come from explicit architecture lists instead of falling back to a standalone CDNA5 decode-wrapper symbol. Checking defined POSIX-format records with an exact name boundary also prevents an imported factory, an overload, or a longer namespace prefix from satisfying the requirement.

Keeping a separate all-symbol scan preserves detection of forbidden execution imports. Reusing the checker for the narrow registry retains its export and architecture restrictions while applying the shared execution-code exclusions. The static-analysis test now requires every built-in model factory. Every existing caller supplies the newly mandatory architecture argument. I did not find a correctness defect in these changes.

## Actionable items

No confirmed correctness issue to report.

## Suggestions

### 1. Exercise the LTO configuration in CI

**Location:** [`.github/workflows/rocjitsu-corpus-tests.yml:86`](https://github.com/ROCm/rocm-systems/blob/803ad699c317188b04ad486db60024aeaa5e10bb/.github/workflows/rocjitsu-corpus-tests.yml#L86), with configuration at [line 430](https://github.com/ROCm/rocm-systems/blob/803ad699c317188b04ad486db60024aeaa5e10bb/.github/workflows/rocjitsu-corpus-tests.yml#L430).

The existing matrix never enables LTO, and this PR does not add a configuration that does. The successful existing jobs therefore do not exercise the GCC LTO failure reproduced above. Add a focused Release+LTO job for GCC and Clang that builds the model-only consumers and runs their existing checks, including the decoding smoke test. Check that CMake actually enabled LTO, since the current configuration can warn and continue without IPO support.

**Implemented in:** [4adcc57aaf840911a1e8a0181177445136253e54](https://github.com/newling/rocm-systems/commit/4adcc57aaf840911a1e8a0181177445136253e54), adding `.github/workflows/rocjitsu-model-only-lto.yml`. It uses the existing checkout convention, builds only the seven relevant targets, and runs the eight selected tests without requiring a GPU or ROCm SDK. The GCC and Clang configurations were validated locally as described above. This optional CI addition incurs two additional builds; their hosted duration has not been measured and is separate from the submitted PR's checker overhead below.

For a minimal reproduction of the old GCC LTO failure, use the submitted head and an out-of-tree build:

```sh
cmake -S "$SRC_DIR/emulation/rocjitsu" -B "$BUILD_DIR" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DLTO=ON -DBUILD_TESTING=ON \
  -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ -DROCM_PATH= \
  -DFETCHCONTENT_BASE_DIR="$BUILD_DIR/_deps"
cmake --build "$BUILD_DIR" --parallel 2 --target rocjitsu_model_only_test
ctest --test-dir "$BUILD_DIR" -R '^ModelOnlyIsaTest\.' --output-on-failure
git -C "$SRC_DIR" show \
  803ad699c317188b04ad486db60024aeaa5e10bb^:emulation/rocjitsu/tests/check_model_only_symbols.cmake \
  > "$BUILD_DIR/check_model_only_symbols.before.cmake"
cmake -DNM="$(command -v nm)" \
  -DMODEL_BINARY="$BUILD_DIR/tests/rocjitsu_model_only_test" \
  -P "$BUILD_DIR/check_model_only_symbols.before.cmake"
```

With GCC 13.3, both submitted tests pass, then the parent script fails with `model-only binary is missing model symbol: rocjitsu::cdna5::Decoder::decode(unsigned int const*, util::DiagnosticEmitter const&)`.

## Commentary

### Measured test-time overhead

There is a consistent slowdown in the symbol-check tests. On identical Clang 23.1 Release binaries with LLVM `nm` 23.1 and CMake 4.4.3, the sum of the seven per-test medians increases from **2.634 seconds to 3.848 seconds: +1.214 seconds, or 46%**.

| Symbol check | Parent script | Submitted script | Increase |
| --- | ---: | ---: | ---: |
| Decode fuzzer | 0.463 s | 0.699 s | 0.235 s |
| Code-object fuzzer | 0.480 s | 0.735 s | 0.255 s |
| Static analysis | 0.783 s | 1.146 s | 0.364 s |
| Waitcheck stream | 0.749 s | 1.011 s | 0.262 s |
| Model-only ISA | 0.048 s | 0.076 s | 0.028 s |
| Gfx1250 translator library | 0.054 s | 0.086 s | 0.032 s |
| Narrow registry | 0.058 s | 0.095 s | 0.038 s |
| **Sum of medians** | **2.634 s** | **3.848 s** | **1.214 s** |

Each test/version pair had one warm-up and seven measured serial runs, alternating which version ran first. The commands used each revision's original arguments and scripts against the same binary, and every measured non-LTO invocation passed. No review build ran concurrently with these measurements. These numbers exclude build time and CTest discovery; they are not a full-suite benchmark.

For the three GCC LTO checks that already passed before the fix, median increases were approximately 0.112–0.114 seconds each. The four failing parent checks are unsuitable for a successful-test timing comparison because they exit early.

The extra `nm --defined-only` invocation adds another symbol scan and demangling pass; static analysis also checks more required factories. The measured relative increase is noticeable within this small test group, while its absolute cost is about one additional second in the measured non-LTO configuration. The submitted PR changes no compiler/linker settings or production execution path. I would retain the stricter checks at this cost; no timing optimization is proposed without evidence that the extra second is consequential.

The handoff is `review/pr15008-suggestions` with the single CI commit mapped above. No production changes or speculative symbol-check rewrites were made. Validation covers the submitted checks and the suggested workflow's local build/test commands; hosted execution and broad emulator testing remain outside this review.
