This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15276](https://github.com/ROCm/rocm-libraries/pull/15276)

**Reviewed head:** `d75df4bffb177b1701cd486e045d9d137ae59c71`. **Base:** `388533cd163ca0977324e6ec76dbec19bc11378d` (#15275).

**Scope:** Independent review of all four changed files under `projects/hipblaslt/tensilelite`: the reference implementation, CPU driver, CTest registrations and reference unit tests. Emphasis: a coherent, faster reference that can eventually replace the slow implementation, with economical tests and consistent numerical choices.

**Assessment:** No production correctness blocker found. Fix the two complex corruption-test registrations. Smaller driver matrices and shared output-pointer selection are useful optional reductions. Required CI is still incomplete in the November 20 snapshot.

**Suggestion branch:** [review/pr15276-readiness-20261120](https://github.com/newling/rocm-libraries/tree/review/pr15276-readiness-20261120), based on the reviewed head ([exact comparison](https://github.com/newling/rocm-libraries/compare/d75df4bffb177b1701cd486e045d9d137ae59c71...ac718301d54e51b165627d1c39e7297ef237dde9)). Three separate commits implement the registration fix ([6d49beddb7ed](https://github.com/newling/rocm-libraries/commit/6d49beddb7edd1b5211f9ac9e3e55c705a0425b2)), smaller tests ([3b41a4d3417a](https://github.com/newling/rocm-libraries/commit/3b41a4d3417aac783627a16161b9c6a5cda2eb7f)), and output-selection simplification ([ac718301d54e](https://github.com/newling/rocm-libraries/commit/ac718301d54e51b165627d1c39e7297ef237dde9)).

## Tests

Both submitted and suggestion revisions build `tensilelite-tests`, `cpu-gemm-driver` and `tensilelite-client` in Release mode with ROCm C++20 and OpenMP. Submitted: **793 standard driver CTests and 67 focused reference/conversion gtests pass**. Suggestion: **795 driver CTests and the same 67 gtests pass**. All **46 complex numerical driver checks**, including the two corrected registrations, also pass in the installed standard tier with `LD_LIBRARY_PATH` unset and SDK runtime dependencies supplied.

Temporarily disabling shadow-buffer conjugation fails the two conjugation-sensitive gtests and all 12 fast conjugation driver cases at the proposed smaller dimensions. Eligibility and the unrelated C/D alias test remain green. The mutation was removed before final validation. The four new gtests took about 1 ms combined in the submitted run; they exercise distinct useful behavior.

Root and component hooks pass; their selectors exclude these C++ files or find no affected Python tests. The suggestion's C++ edit passes scoped clang-format 18.1.4, and the complete diff passes whitespace checks. No full gtest-suite, GPU, Windows or sanitizer run was performed locally. This changes host reference computation; it does not change GPU kernels.

The November 20 CI snapshot has required work pending after the restack. The [policy failure](https://github.com/ROCm/rocm-libraries/actions/runs/44826172926/job/136599239374) cites a cancelled pre-commit run; a replacement pre-commit succeeded. A failed Component summary belongs to the cancelled run, while replacement coverage is queued. Math CI is pending and Multi-Arch builds are in progress. These are not observed numerical failures, but they are not completed qualification either.

## Summary

This is a useful extension of the existing tiled solver, without introducing a separate complex GEMM implementation. Complex float and double keep their storage type through multiplication, accumulation and the epilogue. A/B are conjugated once when requested; unconjugated matching-type inputs need no copy. D is written directly, and the epilogue reads its corresponding C value before writing, preserving the supported in-place C/D case.

The driver independently calculates expected results and checks real and imaginary components. Unit tests add non-real alpha/beta, an aliasing example with explicit expected values, distinct conjugation results and a finite random comparison spanning tile boundaries. Driver cases add transposes, batching and option rejection. Keeping both paths in these tests is useful during migration; the independent expectations should survive removal of the slow path.

Exploratory timings on the submitted production code show a useful benefit. Ryzen Threadripper PRO 9995WX, eight OpenMP threads, `OMP_DYNAMIC=FALSE`, `KMP_BLOCKTIME=0`, alpha=1, beta=0, no transposes. Complex float uses M=N=256, K=4096; complex double uses M=N=128, K=4096 with both operands conjugated. Each entry is one fresh process, with no warm-ups. Validation runs after the timed reference call and passes; execution time excludes validation, input setup and process startup.

| Measurement | Pair 1 | Pair 2 | Pair 3 |
| --- | ---: | ---: | ---: |
| Slow first (1=yes) | 1 | 0 | 1 |
| Complex float, slow ms | 154.871 | 153.736 | 148.595 |
| Complex float, fast ms | **38.3964** | **37.9028** | **38.4166** |
| Complex double, slow ms | 45.2494 | 44.2569 | 40.7591 |
| Complex double, fast ms | **21.3604** | **20.1470** | **20.5782** |

Approximately 4× and 2× respectively on these workloads. Three alternating pairs on a shared host are exploratory evidence, not a general guarantee or a reproduction of the five-config GPU-host campaign in the description.

## Actionable items

### Register both complex corruption checks through the shared helper

[`tests/CMakeLists.txt:1068`](https://github.com/ROCm/rocm-libraries/blob/d75df4bffb177b1701cd486e045d9d137ae59c71/projects/hipblaslt/tensilelite/tests/CMakeLists.txt#L1068) uses raw `add_test` for the two `c_InjectedFailure_Rejected` cases. They consequently lack standard labels, OpenMP limits, timeout and installed registration. The standard and installed validation routes in the test plan omit them, while bare `WILL_FAIL` can accept an unrelated driver error.

Commit [6d49beddb7ed](https://github.com/newling/rocm-libraries/commit/6d49beddb7edd1b5211f9ac9e3e55c705a0425b2) uses `add_cpu_gemm_test` with `EXPECTED_ERROR "Mismatch at 0:"`. This provides the ordinary eight-thread limit, timeout and both registrations, requiring exit code 1 and the intended mismatch diagnostic. The similar Float8 registrations belong to the preceding PR's review and are not duplicated here.

## Suggestions

### Use smaller matrices for complex driver coverage

The new cases at `tests/CMakeLists.txt:1033` inherit 133×147×165 or 137×149×163 matrices. Commit [3b41a4d3417a](https://github.com/newling/rocm-libraries/commit/3b41a4d3417aac783627a16161b9c6a5cda2eb7f) uses 35×39×17 for both types. This still crosses 32×32 output tiles and multiple eight-element K tiles, with tails on every dimension. Transposes, conjugation combinations, scalar choices, both precisions, both paths and three batches remain covered. It also removes the type-dependent size-selection branch.

All 44 ordinary numerical cases passed at both sizes in each measurement below. Each group launches them sequentially with the same eight-thread environment, including startup and validation. This comparison changes only dimensions; it excludes the two corruption checks and seven option checks.

| Measurement | Pair 1 | Pair 2 | Pair 3 |
| --- | ---: | ---: | ---: |
| Original sizes first (1=yes) | 1 | 0 | 1 |
| Original group, seconds | 1.6071 | 1.6177 | 1.6110 |
| Smaller group, seconds | **1.2885** | **1.3363** | **1.2869** |

The local saving is 17–20%, about 0.3 s for this group. Process startup limits the benefit; this is a modest test-cost reduction, not evidence that the original tests are prohibitively slow.

### Share matching-type output selection

`client/src/Reference.cpp:1788` enumerates float, double, Int32 and complex cases that all assign the same output pointer. Commit [ac718301d54e](https://github.com/newling/rocm-libraries/commit/ac718301d54e51b165627d1c39e7297ef237dde9) replaces the four branches with `problem.d().dataType() == TypeInfo<AccumT>::Enum`, removing 15 lines. This is equivalent for all five current accumulator instantiations; mismatched output types retain conversion storage. The full focused validation above covers the retained real, integer, Float8 and complex paths. No speedup is claimed for this simplification.

## Scope decisions

The numerical goal is the required complex GEMM, rather than permanent reproduction of every legacy intermediate operation. This layer keeps the same complex precision and K-order accumulation. The description appropriately limits agreement to tested finite-result cases: overflow and other nonfinite behavior may differ. Its word “bitwise” is stronger than the tests establish, because ordinary complex equality does not distinguish signed zeros; numerical equality is the useful claim here.

Complex bias/scaling/activation and unsupported type combinations still fall back. This preserves the existing support boundary without copying the slow path's ignored or zero-valued complex epilogue inputs into the new implementation. Before deleting that fallback, define which complex operations are supported and their numerical behavior explicitly. No broad epilogue redesign or legacy nonfinite emulation is proposed for this PR. All concrete changes proposed above are implemented on the suggestion branch.
