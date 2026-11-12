This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#15266](https://github.com/ROCm/rocm-libraries/pull/15266)

**Submitted head:** `4554dab796dee28e4e640b7f688c4d0f12d5b375`. **Incremental base:** `571ecae3fc4814ff951461d1d14e48f780975511`.

Independent review of the incremental change and its interaction with the CPU-reference stack, emphasizing test adequacy, runtime, overlap, design reuse, and unsupported cases. Inputs were the public descriptions, code, repository guidance and CI status/logs; target-PR discussions and existing reviews were not read.

**Suggestion branch:** [review/pr15266-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15266-suggestions), based on the submitted head above; final head [088d585c895cff36e459ee0409c1b812edd9da81](https://github.com/newling/rocm-libraries/commit/088d585c895cff36e459ee0409c1b812edd9da81).

## Tests

Submitted head: `cpu-gemm-driver`, `tensilelite-tests`, and `tensilelite-client` built successfully; **361 driver CTests and 24 focused reference gtests passed**. The driver suite took 2.29 s with four CTest workers. Suggestion implementation: the same targets built; **362 driver CTests and 24 focused reference gtests passed**. Later comment-only commits, where present, do not change that execution result.

Validation used a Release ROCm compiler build. Controlled runs set `OMP_THREAD_LIMIT=8`, `OMP_NUM_THREADS=4`, and `KMP_BLOCKTIME=0`; the original stack-tip driver timing predates the thread-limit setting. These are host numerical tests, not GPU-kernel performance measurements. Root/component hook invocations and full-stack whitespace checks were clean; the formatting hooks opt out of these C++/CMake paths, and no Python tests were selected by the component hook. No local GPU or sanitizer run is claimed.

The gtests were run directly with `--gtest_filter=ReferenceFastPath.*:ReferenceMX*.*:*ReferenceMX*/*`. In the category-based build, a CTest name regex containing `ReferenceFastPath` does not select them. Driver CTests are build-tree tests and are not installed into the TheRock test package; Math CI's unfiltered `coverage-cpp` lane runs them but is informational. The gtest categories include standard/comprehensive/full, not quick.

## Summary

Separating input storage, output storage, and scalar/epilogue types is necessary to test the six existing Int8 reference combinations. Integer golden accumulation with an explicit int32-range check and exact output comparison is a useful oracle. This PR establishes the slow-path baseline; the next PR's corresponding fast tests exercise a different implementation, so those pairs are justified.

The 64 added driver cases are inexpensive and cover dispatch, transpose, scalar types, epilogue operations and batching. They miss an important scalar boundary and currently check rejected options only through a nonzero exit status.

## Actionable items

### Preserve the full advertised Int32 scalar range during CLI parsing

At [client/cpu_gemm_driver.cpp:1145](https://github.com/ROCm/rocm-libraries/blob/4554dab796dee28e4e640b7f688c4d0f12d5b375/projects/hipblaslt/tensilelite/client/cpu_gemm_driver.cpp#L1145) and [client/cpu_gemm_driver.cpp:1292](https://github.com/ROCm/rocm-libraries/blob/4554dab796dee28e4e640b7f688c4d0f12d5b375/projects/hipblaslt/tensilelite/client/cpu_gemm_driver.cpp#L1292), alpha and beta are parsed as `float` before checking whether they fit Int32. `2147483647` rounds to `2147483648` and is rejected even though it is valid.

Minimal driver reproduction:

```sh
"$BUILD_DIR/tensilelite/client/cpu-gemm-driver" -M 1 -N 1 -K 0 \
  --type i8 --typeCD i32 --typeAlpha i32 --alpha 0 --beta 2147483647 --validate
```

Suggestion commit [2fcafc2eee3](https://github.com/newling/rocm-libraries/commit/2fcafc2eee3f322abd349beeda112823931c8591) carries parsed scalars as double until conversion to the selected scalar type and adds this boundary case. It passes without weakening integer-domain validation.

## Suggestions

### Use the existing type metadata

[client/cpu_gemm_driver.cpp:80](https://github.com/ROCm/rocm-libraries/blob/4554dab796dee28e4e640b7f688c4d0f12d5b375/projects/hipblaslt/tensilelite/client/cpu_gemm_driver.cpp#L80) duplicates the type-to-enum mapping in private `TypeTraits` specializations. `TensileLite::TypeInfo<T>::Enum` already owns this mapping, including packed Float4. Suggestion commit [088d585c895](https://github.com/newling/rocm-libraries/commit/088d585c895cff36e459ee0409c1b812edd9da81) replaces the private table. Later stack commits that add `TypeTraits` call sites should use `TypeInfo` when integrating this change.

### Require the intended diagnostic in rejected-option tests

[tests/CMakeLists.txt:784](https://github.com/ROCm/rocm-libraries/blob/4554dab796dee28e4e640b7f688c4d0f12d5b375/projects/hipblaslt/tensilelite/tests/CMakeLists.txt#L784) uses `WILL_FAIL`; an unrelated runtime error also satisfies the test. The shared correction is implemented once at the stack tip in #15278's suggestion branch ([66ef187d435](https://github.com/newling/rocm-libraries/commit/66ef187d43535cacaba49a328b77b0388909291e)). It requires exit code 1 and the intended diagnostic, including for this PR's cases. Keep one helper instead of adding a separate failure runner for each PR.

## Scope decisions

The six-type dispatch matrix is useful coverage and should remain. The existing full-range Int8-to-Int8 cases often saturate; #15274's narrow-range cases complement them by making incorrect in-range arithmetic observable. That is a useful extension rather than duplicate coverage.

## Suggestion branch handoff

| Suggestion commit | Item |
| --- | --- |
| [2fcafc2eee3](https://github.com/newling/rocm-libraries/commit/2fcafc2eee3f322abd349beeda112823931c8591) | preserve int32 scalar values in cpu-gemm-driver |
| [088d585c895](https://github.com/newling/rocm-libraries/commit/088d585c895cff36e459ee0409c1b812edd9da81) | use TypeInfo in the CPU GEMM driver |

The suggestion branches are published. Each branch contains its own corrections on its own submitted head, not the other review branches' fixes. Integrate shared changes in stack order, including the alias fix once and later `TypeInfo` call sites. PR-description corrections are reported for the author to make; none were published. See [the cross-PR assessment](review_cpu_reference_stack_15259_15278.md) for test overlap, CI limits and integration notes.
