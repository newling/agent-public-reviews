This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15274](https://github.com/ROCm/rocm-libraries/pull/15274)

**Submitted head:** `e10a924073970893654f5d364decccfff0c5de5f`. **Incremental base:** `c72c8d23f0603f75ff1a9c59282ffacd0c46c4db` (#15266).

**Scope:** Full independent review of the four changed files: `client/src/Reference.cpp`, `client/cpu_gemm_driver.cpp`, `tests/CMakeLists.txt`, and `tests/ReferenceFastPath_test.cpp`, under `projects/hipblaslt/tensilelite`. Includes dispatch, type conversion, reduction and epilogue semantics, layouts, test registration, and relevant prerequisite behavior. The current head's discussion was not used as review evidence.

**Suggestion branch:** [review/pr15274-followup-20261118](https://github.com/newling/rocm-libraries/tree/review/pr15274-followup-20261118), based on the submitted head; final commit [a9a78ec1c4b](https://github.com/newling/rocm-libraries/commit/a9a78ec1c4bda3c54afd82b5453b2dc29b4e5e08). The branch contains one commit for each of the two actionable items and the previously requested optional conversion suggestion. [Compare all three suggestion commits with the reviewed head](https://github.com/newling/rocm-libraries/compare/e10a924073970893654f5d364decccfff0c5de5f...a9a78ec1c4bda3c54afd82b5453b2dc29b4e5e08).

## Tests

Both the submitted implementation and final suggestion branch built `tensilelite-tests`, `cpu-gemm-driver`, and `tensilelite-client` in the existing Release configuration with ROCm C++20 and OpenMP. All **517 CPU GEMM CTests passed on each revision**. The focused reference gtests passed **73 existing tests on the submitted head** and **77 tests on the suggestion branch**, including four added layout regressions. Two device-dependent MX initialization tests were skipped on each revision. Whitespace checks passed.

Three added regression tests were also run against the exact submitted `Reference.cpp`: the non-unit C stride, permuted C free indices, and multiple batch indices each failed with the fast path and passed with the slow path. All three pass with the fixes. A fourth test verifies C's separately mapped batch index on the final branch. The committed tests use explicit expected values and nonzero sentinels; they do not rely solely on fast/slow agreement.

Additional submitted-head driver probes passed for zero K, zero alpha, and column scaling across all six Int8 type combinations. The column-bias variant failed with both reference paths because of an existing driver limitation described under Scope decisions.

The CI snapshot includes a successful pre-commit run and unfinished component jobs. The policy-bot failure cites an earlier cancelled pre-commit run; it does not demonstrate a source failure. This review does not claim complete CI, Windows validation, local GPU execution, or a fresh measurement of the historical performance figures.

## Summary

The PR separates the Int8 integer dot product from its integer or floating-point epilogue while reusing the tiled reference solver. The six accepted type combinations match the slow-reference dispatch. Integer reduction wraps in 32 bits and converts once into the epilogue type; the dedicated Int8 epilogue ordering preserves the slow path's rounding and output conversion. The current code also avoids overwriting aliased C/D before reading C.

The main remaining problems are layout assumptions in the shared fast solver. They already affected some floating-point cases, but enabling Int8 here introduces regressions for Int8 inputs that previously used the general slow solver. The new packed-matrix driver tests do not expose them.

## Actionable items

### Address C using its own strides and index mapping

At [client/src/Reference.cpp:1572](https://github.com/ROCm/rocm-libraries/blob/e10a924073970893654f5d364decccfff0c5de5f/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1572) and [the C read at line 1838](https://github.com/ROCm/rocm-libraries/blob/e10a924073970893654f5d364decccfff0c5de5f/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1838), the fast solver assumes C has unit M stride and that C's free and batch indices occupy the same dimensions as D. Eligibility checks A, B, and D layout but does not enforce these C assumptions. The newly enabled Int8 dispatch therefore accepts problems for which it reads the wrong C elements.

For a 2×1×1 Int8 GEMM with `alpha=beta=1`, A `[2,3]`, B `[5]`, and logical C `[7,11]` stored as `[7,99,11]` with M stride 2, the expected D is `[17,26]`. The submitted fast path produces **`[17,114]`**, reading the padding value 99 as the second C element. The slow path produces `[17,26]`. A separate 2×2 case with C's free indices permuted also fails: fast `[21,28,31,40]`, expected `[21,32,27,40]`.

These descriptors are expressible through `ContractionProblemGemm::FromIndexSizes`, which the client uses for its problem identifiers and explicit tensor strides. Derive C's M, N, and batch strides from the corresponding indices' `.c` fields, and include the M stride in C's address calculation.

Commit [9e21696dd43](https://github.com/newling/rocm-libraries/commit/9e21696dd433bba7b2e34b4b7acdfd4f43192492) implements this change and adds three explicit-value regressions for a non-unit C stride, permuted C free indices, and a permuted C batch index. The correction also applies to the floating-point instantiations sharing this solver.

### Fall back when there is more than one batch index

At [client/src/Reference.cpp:1279](https://github.com/ROCm/rocm-libraries/blob/e10a924073970893654f5d364decccfff0c5de5f/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1279), eligibility rejects an empty batch-index list but accepts lists with multiple entries. The solver then uses only `batchIndices()[0]` and `batchSize(0)`, leaving outputs in the other batch dimensions uncomputed.

For `Contraction_m_Aimkl_Bmjkl_Cijkl_Dijkl` with index sizes `[1,1,2,2,1]`, A `[2,3,5,7]`, B `[11,13,17,19]`, and `alpha=1, beta=0`, all four scalar GEMMs should produce `[22,39,85,133]`. Starting D at `[-1,-1,-1,-1]`, the submitted fast path returns **`[22,39,-1,-1]`**. The slow path computes all four values. Before this PR, Int8 always reached that slow path.

Require exactly one batch index in fast-path eligibility unless the solver is extended to iterate all batch dimensions. Falling back preserves correct behavior without expanding this performance change into a general contraction rewrite.

Commit [a9a78ec1c4b](https://github.com/newling/rocm-libraries/commit/a9a78ec1c4bda3c54afd82b5453b2dc29b4e5e08) adds that eligibility guard and a regression that checks rejection by the fast-path predicate and correct results through the public solver with fast-path attempts both enabled and disabled.

## Suggestions

### Convert built-in arithmetic source types directly

At [client/src/Reference.cpp:66](https://github.com/ROCm/rocm-libraries/blob/e10a924073970893654f5d364decccfff0c5de5f/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L66), `loadTo` converts integer sources directly but sends every other source through float. Prefer `std::is_arithmetic_v<SrcType>` so built-in float and double also convert directly. Keep the intermediate float conversion for custom narrow floating-point wrappers that need it.

Taken alone, `loadTo<double, double>` would narrow `1 + 2^-30` to `1`. Ordinary FP64 GEMM selects `solveCPUFast<double>`, however, and `ShadowBuffer<double>` directly uses double input pointers. The existing FP64 precision regression and fast/slow driver tests pass. This is a helper cleanup, not a demonstrated double-GEMM failure.

Commit [74cda9dc53b](https://github.com/newling/rocm-libraries/commit/74cda9dc53b03faf6c14badc1b8e02c2ab79494b) changes the predicate and explanatory comment, retaining the integer conversions and narrow-wrapper path.

## Scope decisions

The existing Int32 epilogue overflow policy remains separate from this performance change, consistent with the reviewer's stated scope. The CPU references wrap the dot product, but their integer epilogues still use signed C++ arithmetic; the driver's wider golden calculation rejects out-of-range intermediates. Establishing a uniform overflow policy for those epilogues is independent work. The layout findings above are different: previously correct Int8 calls acquire wrong results when this PR enables the fast solver.

An additional driver probe using `--bias --scaleAlphaVec --factorDim 1` with M=3 and N=5 fails in both fast and slow modes. The existing driver allocates M bias entries and its oracle uses row bias, while the reference uses the selected column factor dimension. This setup and oracle behavior are unchanged from the incremental base, and the PR's added bias tests use factor dimension 0. Correcting the driver's column-bias setup and oracle is deferred; those probes are not evidence of an Int8 fast-path regression. Column scaling without bias passes for all six combinations.

The suggestion branch contains both bounded correctness fixes and the optional conversion cleanup, with no omitted implementation for the actionable items. Validation covers the host reference and its driver; GPU behavior and historical timing claims were not remeasured.
