> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#10275 — `fix(tensilelite): fix data races in DataInitialization`](https://github.com/ROCm/rocm-libraries/pull/10275)
**Base:** `develop`
**Files:** 3 changed (+169/-28)
**Assessment:** REQUEST CHANGES
**Risk:** 3/5 — the changed code is in the TensileLite client/test path rather
than the shipped GEMM kernels, but the new suppression policy can make the
race detector silently accept unrelated real races, and one acknowledged
initialization race remains unfixed.

## Tests

The PR's TSan-instrumented TensileLite client was configured and built for
gfx1151:

```bash
cmake --preset tensilelite \
  -S $SRC_DIR/projects/hipblaslt \
  -B $BUILD_DIR \
  -DCMAKE_BUILD_TYPE=Release \
  -DGPU_TARGETS=gfx1151 \
  -DTENSILELITE_CLIENT_ENABLE_ROCPROFSDK=OFF \
  -DCMAKE_C_COMPILER=$ROCM_PATH/bin/amdclang \
  -DCMAKE_CXX_COMPILER=$ROCM_PATH/bin/amdclang++ \
  -DTENSILELITE_ENABLE_HOST_TSAN=ON \
  -DHIPBLASLT_BUNDLE_PYTHON_DEPS=ON

cmake --build $BUILD_DIR --target tensilelite-client --parallel 8
```

The build passed in 94.94 seconds. This compiled both changed
`DataInitialization` files with ThreadSanitizer instrumentation and linked the
client successfully.

I also replaced the grouped construction locally with `resize()` followed by
indexed initialization and rebuilt the focused target:

```bash
cmake --build $BUILD_DIR --target tensilelite-client-common --parallel 8
```

That exact form compiled successfully in 11.16 seconds. The experiment was
reverted after verification.

I then tested the suppression file against a deliberately racy program. The
program starts two threads together and has both call `memcpy()` into the same
64-byte destination:

```bash
$CXX -std=c++17 -O1 -g -fsanitize=thread -pthread \
  tsan_memcpy_race.cpp -o tsan-memcpy-race

TSAN_OPTIONS='halt_on_error=1:exitcode=66' \
  ./tsan-memcpy-race

TSAN_OPTIONS="halt_on_error=1:exitcode=66:print_suppressions=1:suppressions=$SRC_DIR/projects/hipblaslt/tensilelite/tsan_suppressions.txt" \
  ./tsan-memcpy-race
```

Results:

- Without suppressions: exited 66 with a ThreadSanitizer data-race report.
- With this PR's file: exited 0 and printed
  `Matched 1 suppressions: 1 race:memcpy`.

This is a concrete false negative caused by the new file. TSan checks every
symbolized function, source file, and module frame in the conflicting access
stacks; a generic entry such as `race:memcpy` is not limited to the report that
motivated it.

I also isolated the `Half` specialization's union change in a minimal OpenMP
program. After suppressing only the local libomp worker wake-up report, the
old form, with one union outside the parallel loop, exited 66 with a race at
the assignment to `x.bits`. The new form, with the union declared inside the
loop body, exited 0. This confirms that moving `x` is a real fix rather than a
cosmetic OpenMP annotation.

A matching Clang 22 LLVM-IR comparison found no generated-code difference
between the old implicit sharing and the new explicit
`shared(array, tensor, sizes, count, dim)` clauses. Both outlined functions
capture the same five objects by reference. The scalar `firstprivate` changes
for `numPacks` and `elements` do copy those read-only loop bounds by value.

I attempted one of the PR's listed workloads:

```bash
TSAN_OPTIONS='halt_on_error=1:exitcode=66' \
  $BUILD_DIR/Tensile.sh \
  $SRC_DIR/projects/hipblaslt/tensilelite/Tensile/Tests/common/streamk/sk_hgemm_lsu.yaml \
  $OUTPUT_DIR \
  --prebuilt-client=$BUILD_DIR/tensilelite/client/tensilelite-client
```

The run reached Tensile solution enumeration on gfx1151 but produced
`Actual Solutions: 0 / 1` and stopped with
`Your parameters resulted in 0 valid solutions` after 38.55 seconds. No
benchmark/client workload ran, so this supplied no local TSan result. The
other two configurations named in the PR target different GPU families.

Additional checks:

```bash
git diff --check <pr-base>...HEAD
git merge-tree --write-tree origin/develop HEAD
```

Both passed. The current three-way merge with `develop` is clean.

As of August 3, 2026, the public Windows gfx1151 hipBLASLt build and test pass,
as do the hipBLASLt preliminary, precheckin, code-coverage, and static-analysis
Math CI lanes. The red public jobs do not expose a failure in these changes:

- TensileLite coverage failed an unrelated Python coverage ratchet for
  `ValidWorkGroupMappingXCC.py`.
- HOST_ASAN failed during configuration because its toolchain could not find
  `libclang_rt.asan-x86_64.so`.
- Two Linux TheRock builds completed compilation but failed artifact
  post-processing because the expected SDK tree and
  `therock_manifest.json` were absent.

There is no public TSan job, and the new suppression file is not referenced by
CMake, the task runner, a test script, or CI.

## Summary

The PR makes three distinct changes:

1. It gives OpenMP variables explicit sharing attributes. The read-only scalar
   bounds become `firstprivate`; most tensor-based variables are explicitly
   `shared`, which matches their previous implicit behavior.
2. It moves the `Half` bit-conversion union inside its parallel loop and changes
   grouped-input construction from a stack temporary plus `push_back()` to
   reserved in-place vector construction.
3. It adds 45 runtime TSan race-suppression patterns covering OpenMP, memory
   allocation/copy operations, HIP, standard-library internals, project
   functions, third-party code, and one explicitly acknowledged real race.

The `Half` union move fixes an actual shared scratch-variable race. Copying
read-only loop bounds into each OpenMP task is also reasonable, although no
normal result changes.

The grouped vector does not need a map or a new ownership model. This helper is
private, its only callers pass a newly allocated empty
`ContractionGroupedInputs`, construction is serial, and the completed vector is
not returned until the loop finishes. `ContractionInputs` contains owned
`activationArgs`/`maxElements` vectors and external buffer pointers, but no
self-pointer or reference into its containing vector. Vector reallocation was
therefore safe; `reserve()` plus `emplace_back()` is a valid way to avoid
copies, not a concurrency guarantee on which correctness needs to depend.

The suppression file is the blocking issue. Runtime suppression files are a
supported last-resort mechanism for a proven sanitizer/runtime false positive
or an external bug that cannot yet be fixed locally. This file instead
suppresses broad operations that occur in ordinary race stacks, contains no
reproduction or issue references, is not wired into a repository command, and
suppresses an acknowledged project race. A clean run under this file cannot
support the claim that the production paths are race-free.

## Actionable items

1. **`projects/hipblaslt/tensilelite/tsan_suppressions.txt:18-76,85-97,113-134`
   — replace the broad stack-frame suppressions with narrowly evidenced
   exceptions.**

   Entries including `memcpy`, `malloc`, `free`, `operator delete`,
   `pthread_mutex_lock`, `pthread_mutex_init`, `std::_Sp_counted`, and broad
   project functions suppress a report whenever the name appears in either
   conflicting access stack. They are not scoped to one allocation, call site,
   or known OpenMP report. The deliberate `memcpy` race above passes under the
   file unchanged.

   Remove generic C/POSIX/standard-library and project-wide entries. For each
   remaining external false positive, preserve the unsuppressed report, reduce
   it to a minimal reproducer, identify the exact affected runtime/library
   version, link an upstream issue where possible, and match the narrowest
   stable external function or module. Run with `print_suppressions=1` and
   review the hit counts so a renamed or unexpectedly broad pattern cannot
   silently change coverage. Internal project races should be fixed rather than
   hidden by a stack frame elsewhere in the report.

2. **`projects/hipblaslt/tensilelite/client/include/DataInitialization.hpp:792-864`
   and `projects/hipblaslt/tensilelite/tsan_suppressions.txt:99-111` — define
   and fix the overlapping-tensor-index contract instead of suppressing one
   initializer.**

   The file explicitly labels `initArrayTrig` as a real race: two logical
   coordinates may map to the same physical index. `TensorDescriptor` accepts
   arbitrary strides and does not enforce injectivity. For example, sizes
   `{2,2}` with strides `{0,1}` map both `(0,0)` and `(1,0)` to index zero.

   The issue is not specific to `initArrayTrig`. `initArraySerialIdx`,
   `initArraySerialDim`, the `Half` specialization, and `initArrayIdentity` all
   parallelize logical coordinates and write through `tensor.index(coord)`.
   They can race under the same descriptor contract. The values can differ, so
   the suppression file's suggested atomic write would remove the formal race
   while leaving a nondeterministic initialized value.

   Decide whether overlapping descriptors are valid inputs. If they are not,
   reject them before entering these parallel loops. If they are valid, use a
   deterministic initialization policy—such as a serial path for overlapping
   layouts or an operation-specific traversal over unique physical
   destinations. Add direct tests for contiguous, padded-but-injective, and
   overlapping strides across all affected initialization modes. Remove
   `race:initArrayTrig`.

3. **`projects/hipblaslt/tensilelite/CMakeLists.txt:4-74`,
   `projects/hipblaslt/tensilelite/tasks.py:235-332`, and
   `projects/hipblaslt/tensilelite/tsan_suppressions.txt:1-134` — provide one
   reproducible TSan entry point and direct regression coverage.**

   The repository can enable TSan, but it neither applies nor documents the new
   suppression file. The PR's test plan omits the exact build/run commands,
   GPU architecture, ROCm/Clang/libomp versions, `TSAN_OPTIONS`, unsuppressed
   reports, and suppression hit counts. None of the changed lifetime or
   OpenMP-sharing behavior has a direct test.

   Add a checked script, task, CTest target, or CI lane that builds with
   `TENSILELITE_ENABLE_HOST_TSAN=ON`, sets a repository-relative suppression
   path if narrowly justified suppressions remain, uses a nonzero sanitizer
   exit code, and prints matched suppressions. Include a focused test that
   fails with the old shared `Half` union. For grouped-input construction,
   preserve the original unsuppressed report and reduce it to a test that fails
   before the change; if vector growth cannot reproduce a report, test normal
   multi-group construction and describe the direct emplacement as a copy
   optimization rather than a race fix. Keep the larger YAML workloads as
   integration coverage, but do not use a clean broadly suppressed run as the
   primitive's only regression test.

## Suggestions

1. **`projects/hipblaslt/tensilelite/client/src/DataInitialization.cpp:2995-3004`
   — correct the explanation of the grouped-vector change.**

   The code is safe, but the comments claim that stack allocation and vector
   reallocation cause races through stale OpenMP references. This function
   launches no OpenMP work, stores no reference to the local `unit`, and has no
   concurrent reader of `inputs->grouped`. Preserve direct construction if the
   copy reduction is desired, but describe it as such.

   Since the final size is already known, an equally clear form is:

   ```cpp
   inputs->grouped.resize(offsets[0].size());
   for(size_t idx = 0; idx < inputs->grouped.size(); ++idx)
       setContractionInputs(..., &inputs->grouped[idx]);
   ```

   This exact form compiles in the TSan client build. It expresses fixed-size
   construction without implying that `std::vector` has an unsuitable
   ownership model. A map would add allocation, lookup, and iteration
   complexity without solving a demonstrated lifetime problem.

2. **`projects/hipblaslt/tensilelite/client/include/DataInitialization.hpp:758-875`
   — use one intentional OpenMP data-sharing style and narrow the stated root
   cause.**

   Keep the union inside the `Half` loop. For the other loops, either rely on
   the existing default sharing rules or use `default(none)` with shared
   read-only tensor/buffer state and `firstprivate` scalar bounds. The current
   mix explicitly shares `count` and `dim` in some functions while making
   equivalent bounds firstprivate in others.

   The previous code did not mark `TensorDescriptor` as firstprivate, and a
   matching Clang experiment generated identical captures before and after the
   explicit `shared` clauses. Update the PR description to distinguish the
   proven shared-union race, the by-value scalar capture changes, and any
   sanitizer/runtime report that remains only a suspected false positive.

3. **Validate every suppression pattern against a real symbol and hit count.**

   Sanitizer suppression templates use `*` wildcards with optional `^`/`$`
   anchors; they are not general regular expressions. At least one raw mangled
   pattern is written in regex style with `.*` immediately after
   `initArray`, while the actual mangled symbols have template arguments at
   that position. Dead patterns create false confidence, and the broad
   demangled fallback currently hides whether the narrow pattern works.

## Commentary

The grouped-input concern is useful because `reserve()` often does indicate a
fragile address-stability workaround. In this specific path, however, there is
no observer during construction and no self-referential object, so vector
relocation was not the underlying ownership problem. The stronger criticism is
that the PR attributes a race to relocation/stack reuse without preserving the
report or a test that demonstrates such a race.

Suppression files themselves are not unusual. They are analogous to narrowly
scoped sanitizer waivers: acceptable when the report is understood, the code
cannot be changed locally, and the waiver is specific and audited. A reviewer
checks one by first running without suppressions, examining both conflicting
access stacks and the allocation/thread-creation context, reproducing the
report minimally, and proving the relevant synchronization or external bug.
Then the reviewer runs with only the proposed narrow entry and
`print_suppressions=1`, confirms the expected hit count, and keeps an
intentional unsuppressed race test to ensure the detector still fails when it
should. This PR's `memcpy` false-pass counterexample shows why a zero-warning
count alone is not evidence.

The OpenMP changes divide into two categories. Moving the shared conversion
union into the loop is necessary and fixes observable undefined behavior.
Making immutable scalar loop bounds firstprivate is reasonable and may avoid
tool sensitivity around a caller's stack. The explicit `shared` clauses for
objects that were already implicitly shared are mainly documentation and do
not substantiate the stated TensorDescriptor-copy root cause.
