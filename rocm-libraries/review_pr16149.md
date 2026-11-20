This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#16149](https://github.com/ROCm/rocm-libraries/pull/16149)

**Reviewed head:** `9a4fb62d7ee1640c5108bbf94086a5e2af23bd95`. **Base:** `a6274972b291d943a5edf3a9ca671c85b9b0e70e` (#16432).

**Scope:** Independent review of all five changed files under `projects/hipblaslt/tensilelite`: `client/src/Reference.cpp`, `src/ContractionSolution.cpp`, `tests/CMakeLists.txt`, `tests/ReferenceFloat8Scaling_test.cpp`, and `tests/Float8ConversionArguments_test.cpp`. Traced CPU narrowing, fast-path eligibility, ordinary/grouped conversion arguments, and their generated-kernel consumers. Later stack changes are outside this review.

**Assessment:** No functional blocker found in the submitted code. It is ready for code approval, with merge readiness still conditional on required CI, draft status, and the current GPU qualification requested in its test plan. This review directly validates CPU results and GPU argument construction; it does not provide a fresh GPU numerical run.

**Suggestion branch:** [review/pr16149-readiness-20261120](https://github.com/newling/rocm-libraries/tree/review/pr16149-readiness-20261120), based on the submitted head. Optional cleanup commit [a40150d6f455](https://github.com/newling/rocm-libraries/commit/a40150d6f455c9fcc9685ec2e295286af3322556) adds direct test includes, formats the new tests, and removes unrelated whitespace changes from the reference implementation. [Compare the suggestion with the reviewed head](https://github.com/newling/rocm-libraries/compare/9a4fb62d7ee1640c5108bbf94086a5e2af23bd95...a40150d6f455c9fcc9685ec2e295286af3322556).

## Tests

The exact submitted head built `tensilelite-tests`, `cpu-gemm-driver`, and `tensilelite-client` in Release mode with ROCm C++20 and OpenMP. All **59 focused reference and conversion-argument gtests** passed without skips. All **517 standard CPU-driver CTests** passed in 8.23 seconds. Runs used an OpenMP limit of eight threads per execution.

The ten added tests took approximately **8 ms combined in each of the two recorded runs**, excluding process startup: argument construction/scaling suites took 6/2 ms on the submitted head and 5/3 ms on the cleanup branch. These are host-only tests; the conversion tests inspect serialized kernel arguments without launching GPU kernels. Runtime is negligible for this suite, although some case combinations overlap as discussed below.

An independent K=3 probe passed **432 route executions**: 72 wide-output type configurations, three scale modes, and forced-slow versus fast-preferred execution. It covers Half/Half and both mixed storage directions, all eight OCP/fnuz compute pairs, Half/Float/BFloat16 outputs, non-power-of-two scales, alpha=1.5, and beta*C=0.5. Expected results are fixed literals derived from the input formats, not comparisons between the two implementations. Scalar configurations reject the fast path and complete through the slow dispatcher supplied by #16432; Vector and unscaled configurations remain fast-eligible.

For the negative control, retained the new tests and restored both production files from the parent. **Eight of the ten new gtests failed**, exposing omitted Vector scales, incorrect Scalar fast-path selection/results, and repeated split-K scale arguments. The unit-scale and other-narrowing controls still passed. Some failures cover the same cases, so this establishes regression detection rather than independent coverage from every test. Restored the submitted files afterward. The optional cleanup rebuilt all three targets and passed all 59 focused tests again. Production/test tokens are unchanged apart from direct standard-library includes.

Root and component pre-commit invocations succeeded. The root hooks exclude these C++ paths, and the component selector had no affected Python tests. Separate clang-format checks identified small formatting issues in the new scaling test; the suggestion fixes them. Final new-file formatting and whitespace checks pass.

At the November 20 review snapshot, required Component CI, Multi-Arch, and pre-commit passed, with Math CI Summary pending. The [Multi-Arch summary](https://github.com/ROCm/rocm-libraries/actions/runs/44770465616/job/136407841551) explicitly skipped Linux and Windows build/test branches. The [policy bot failure](https://github.com/ROCm/rocm-libraries/actions/runs/44770454272/job/136406446115) records an earlier cancelled pre-commit run; a later required pre-commit run succeeded. Non-required Codecov project checks reported 57.87% TensileLite-CPP and 69.28% hipBLASLt coverage against 80% targets; patch coverage passed. These statuses do not demonstrate a numerical regression in this change.

No full unit-suite, installed-package, Windows, sanitizer, GEMM performance, or fresh GPU numerical run was performed locally. A gfx942 worker was reachable, but its glibc 2.35 cannot run these binaries, which require glibc 2.38; no separate remote build was started. The description's earlier integrated GPU results were not independently reproduced. Its earlier conversion-scale suppression gives the same null/non-null choices as this head for the affected Half-to-Float8 cases, but that source comparison does not establish execution at the current head or complete gfx950 qualification.

## Summary

The two scale modes have different rounding boundaries. Scalar scaling multiplies a Half input before Float8 conversion; Vector scaling multiplies the completed narrowed dot product. The fast reference currently narrows first, so rejecting Scalar Half-to-Float8 problems for every output type is the correct conservative choice. The #16432 prerequisite now supplies the wide-output slow dispatch cases that this guard needs.

The GPU fix preserves the original scale pointers for the main kernel and replaces only an already-consumed Half-to-Float8 Scalar scale with null in conversion arguments. `KernelWriterAssembly.py` applies that scale before narrowing, and `KernelWriterConversion.py` explicitly interprets null as one. Ordinary and grouped conversion calls share the corrected builder; the grouped test checks separate argument blocks and distinct scale pointers for each problem. Vector, non-narrowing, SingleKernel/GSU=1, and other conversion controls retain their original pointers.

Restricting suppression to the four Float8 compute types avoids extending the Half-to-Float8 policy to unrelated size-reducing conversions. No new kernel ABI or changed argument layout is needed.

## Actionable items

None in the reviewed code. Shared validation and GPU qualification remain shipping prerequisites as described above.

## Suggestions

### Refresh the description to match the published stack

The PR's Technical Details still names #15274 as its immediate base, and Test Result/Risk level say the missing slow-dispatch cases remain unresolved and the changes are local. The actual base is #16432, this head is published, and the 432 independent route executions above confirm the wide-output dispatch prerequisite works with the expanded guard. Update those claims and distinguish current-head validation from the older integrated GPU campaign. This is a prose update; no replacement description was requested or prepared.

### Keep the patch focused and make test dependencies explicit

Optional commit [a40150d6f455](https://github.com/newling/rocm-libraries/commit/a40150d6f455c9fcc9685ec2e295286af3322556) adds `<cstddef>`/`<initializer_list>` to the new tests and `<cstdint>` to `tests/Float8ConversionArguments_test.cpp:8`, formats the new scaling test, and restores the parent's whitespace in unrelated parts of `client/src/Reference.cpp` beginning at submitted line 2035. It changes no arithmetic, routing, inputs, or assertions. These cleanups are not conditions for accepting the functional fix.

### Consider reducing overlapping test cases

The tests cover the right contracts, but the matrices could be smaller:

- In [`tests/ReferenceFloat8Scaling_test.cpp:129`](https://github.com/ROCm/rocm-libraries/blob/9a4fb62d7ee1640c5108bbf94086a5e2af23bd95/projects/hipblaslt/tensilelite/tests/ReferenceFloat8Scaling_test.cpp#L129), the broad compatibility test repeats the Vector+narrowing cases already covered by the focused test at line 113. Those combinations could be removed from the broad test.
- In [`tests/Float8ConversionArguments_test.cpp:122`](https://github.com/ROCm/rocm-libraries/blob/9a4fb62d7ee1640c5108bbf94086a5e2af23bd95/projects/hipblaslt/tensilelite/tests/Float8ConversionArguments_test.cpp#L122), the broad matrix repeats the dedicated Scalar regression's argument checks. Keep the dedicated test, which also checks input immutability. Of the broad matrix's 192 configurations, 128 create no conversion call; representative controls for each no-conversion route would suffice for the changed behavior. Repeated GSU=2/4 cases also exercise the same scale-suppression condition.

Retain both operand directions, the four Float8-type predicate checks, grouped argument packing, and Half/float-output dispatch coverage. For Float8 outputs, both execution preferences take the slow solver at this head; keeping them has value when #15275 adds fast Float8-output support. The Half/float-output Vector cases already exercise two implementations. Pruning is an optional readability choice, with negligible runtime benefit, and is not implemented on the suggestion branch.

## Scope decisions

The new Scalar eligibility rule also selects the slow path when scale buffers happen to contain one. Eligibility has only problem metadata, not the runtime scale values, and the conservative choice preserves correctness. A runtime unit-scale optimization would be separate performance work and was not added.

A fresh device run should exercise the affected split-K paths and scale modes on the intended gfx942/gfx950 configurations before shipping, as already requested in the PR's test plan. CPU expected values and argument-buffer checks support the code review but do not replace that qualification. No functional fix was omitted from the local suggestion branch.
