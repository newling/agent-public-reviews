This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15277](https://github.com/ROCm/rocm-libraries/pull/15277)

Reviewed head: `4d532fdb146dea3a6b76c497d5b46507a4f7e75b`, against #15276 at `d75df4bffb177b1701cd486e045d9d137ae59c71`. Independent review of all four changed files, emphasizing reference speed, numerical consistency, compact code, and fast tests. Existing PR discussion was not used.

Suggestion branch: [review/pr15277-readiness-20261120](https://github.com/newling/rocm-libraries/tree/review/pr15277-readiness-20261120), based on the reviewed head. Commit [40b55ff4997c](https://github.com/newling/rocm-libraries/commit/40b55ff4997c49d00bd50f5cd9972d887c72eabb) fixes narrow accumulation and adds its regression; [c0fc27096954](https://github.com/newling/rocm-libraries/commit/c0fc27096954596cb4ad3f1421cdc62cc110b8dd) reduces the new non-MX test sizes. [Complete suggestion comparison](https://github.com/newling/rocm-libraries/compare/4d532fdb146dea3a6b76c497d5b46507a4f7e75b...c0fc27096954596cb4ad3f1421cdc62cc110b8dd).

## Tests

Release builds of `tensilelite-tests`, `cpu-gemm-driver`, and `tensilelite-client` passed. The submitted head passed 75 focused reference/conversion gtests and 863 standard CPU-driver CTests. The suggestion branch passed 76 focused gtests and the same 863 driver tests, plus all 70 newly added registrations from an installed tree with `LD_LIBRARY_PATH` unset and ROCm runtime dependencies supplied. Focused gtests took 0.33 seconds; the driver suite took 14.14 seconds with 16 CTest workers. Root and component hooks, scoped formatting, and whitespace checks passed; the root C++ hooks exclude these paths.

The new cancellation regression and corrected eligibility assertions fail against the submitted implementation. The numerical regression observes 1 where narrow accumulation requires 0; both pass with the fix. No GPU, Windows, sanitizer, or full gtest run was performed locally.

At the November 20 review, the head was open and non-draft. Shared CI was incomplete: Math CI is pending and replacement coverage/build jobs are queued or running. The [policy-bot failure](https://github.com/ROCm/rocm-libraries/actions/runs/44826172423/job/136599237407) explicitly cites a cancelled pre-commit run; replacement pre-commit passed. This is not an all-green CI assessment.

## Summary

This layer removes two substantial reasons to fall back to the scalar reference: saving preactivation E and computing activation/bias gradients. It extends the existing tiled GEMM epilogue and reuses `ReductionCPU`, preserving the same numerical operations for ordinary Float32 workloads. E uses its own type and strides; gradient E remains an input; bias reduction sees values before gate residual and output conversion. These are useful boundaries to preserve as the stack moves toward one reference implementation.

The tests mostly target the right distinctions. The small E-content test checks preactivation ordering, Half rounding, and padding. Gradient tests exercise activation selection, E immutability, gate ordering, A/B/D reduction sources, transposes, and sampling. The driver supplies an independent scalar calculation across data types. The missing distinction is non-HPA GEMM precision outside bias-gradient mode.

## Actionable items

### Preserve narrow accumulation for E output and gradients without bias

At [Reference.cpp:1430](https://github.com/ROCm/rocm-libraries/blob/4d532fdb146dea3a6b76c497d5b46507a4f7e75b/projects/hipblaslt/tensilelite/client/src/Reference.cpp#L1430), the precision guard applies only when both gradient and bias are enabled. However, non-HPA `H_H_H` and `B_B_S` use Half/BFloat16 accumulation throughout the slow GEMM and epilogue; the fast solver uses float regardless of bias.

For a 1×1×3 Half GEMM, take A = `[2048, 1, -2048]`, B = `[1, 1, 1]`, alpha = 1, and beta = 0. Narrow accumulation loses the middle 1 and returns 0; the submitted fast path returns 1. Forward E therefore receives 1 instead of 0. A gradient with no bias, E = 1, and DRelu likewise produces D = 1 instead of 0. BFloat16 exhibits the same difference with 256 replacing 2048. With HPA enabled, 1 is correct on both paths. This is a material numerical difference, beyond last-bit evaluation-order variation.

Commit [40b55ff4997c](https://github.com/newling/rocm-libraries/commit/40b55ff4997c49d00bd50f5cd9972d887c72eabb) broadens the existing guard to all non-HPA instances of those two type IDs. Its compact regression asserts independently known D/E values for ordinary GEMM, forward E, and gradient E, under both precision settings and both requested paths. It also updates the previous eligibility test, which explicitly expected the faulty configurations to be eligible.

The ordinary-GEMM discrepancy is inherited. E and gradient modes previously fell back, so enabling those modes introduces the discrepancy here. Applying one precision rule across these modes avoids making accuracy depend on which optional output is requested. Float32/HPA execution remains eligible.

## Suggestions

### Use smaller matrices for the new epilogue driver cases

At [tests/CMakeLists.txt:1085](https://github.com/ROCm/rocm-libraries/blob/4d532fdb146dea3a6b76c497d5b46507a4f7e75b/projects/hipblaslt/tensilelite/tests/CMakeLists.txt#L1085), the 60 new non-MX numerical cases inherit roughly 133×147×165 dimensions. Their new contract is epilogue/output behavior; 37×35×19 retains full and partial 32×32 tiles and full and partial 8-element K blocks.

Commit [c0fc27096954](https://github.com/newling/rocm-libraries/commit/c0fc27096954596cb4ad3f1421cdc62cc110b8dd) uses that common size without removing cases. MX dimensions and the narrow-accumulation saturation regressions retain their original sizes. All cases pass at the smaller size. Alternating serial runs of the complete 60-case group gave the following wall times; each case used a fresh process and eight OpenMP threads:

| Group wall time, seconds | Pair 1 | Pair 2 | Pair 3 |
| --- | ---: | ---: | ---: |
| Original sizes first | 1 | 0 | 1 |
| Original sizes | 2.516615 | 2.560146 | 2.440548 |
| Smaller sizes | **2.192656** | **2.313167** | **2.249464** |

The observed saving is modest because process startup remains. These three exploratory pairs do not establish a general CI speedup.

The numerical-fix commit also adds the owning `<stdexcept>` and `<type_traits>` headers for the changed test's standard-library uses.

## Scope decisions

The new guard preserves an existing numerical contract through fallback. Removing the slow path will require implementing that narrow arithmetic in the replacement or explicitly changing the precision contract; silently promoting non-HPA work is not an equivalent replacement.

The duplicated fast/slow reduction dispatch and the inherited unsupported-shape error/double-free problem are already assigned to [#16150](https://github.com/ROCm/rocm-libraries/pull/16150). This review does not duplicate that later layer. #15277 retains the single-batch bias-reduction boundary. Earlier stack suggestions about raw CTest registration are also not repeated: all 70 registrations added here use the standard helper, and their installed execution passed.

## Commentary

The expected performance benefit comes from using the existing tiled K loop for these newly eligible modes; E writes and bias reductions still have their own costs. Exploratory measurements support that expectation for Float32:

| CPU reference time, milliseconds | Pair 1 | Pair 2 | Pair 3 |
| --- | ---: | ---: | ---: |
| Slow first | 1 | 0 | 1 |
| Forward E, slow | 455.311 | 353.147 | 471.533 |
| Forward E, fast | **20.6138** | **21.7306** | **23.1650** |
| Gradient with bias from D, slow | 453.773 | 457.188 | 455.436 |
| Gradient with bias from D, fast | **24.4588** | **23.9167** | **24.5459** |

Setup: AMD Ryzen Threadripper PRO 9995WX, Release build, ROCm SDK 10.1.0a20260812 compiler/runtime, eight OpenMP threads (`OMP_THREAD_LIMIT=8`, `OMP_DYNAMIC=FALSE`, `KMP_BLOCKTIME=0`), NN Float32, M=1023, N=1025, K=1021, alpha=1, beta=0.5, bias and Relu enabled, E enabled. The gradient runs additionally enable `--gradient`; bias source defaults to D. Runs used the numerical-guard fix, which does not alter these Float32 paths. Forward pairs ran before gradient pairs.

Each entry is one timed `SolveGemmCPU` call in a fresh `cpu-gemm-driver` process, with no warmup. Driver validation remained enabled by default and ran after timing; all D/E or D/bias comparisons passed. These are slow-versus-fast measurements on the same implementation, not separate base/head builds. The shared host and three pairs permit an exploratory workload-specific conclusion, not a universal speedup or significance claim.

The suggestion branch ends at [c0fc27096954](https://github.com/newling/rocm-libraries/commit/c0fc27096954596cb4ad3f1421cdc62cc110b8dd): numerical compatibility first, smaller tests second. The actionable fix is implemented and locally validated; broader platform validation remains as noted above.
