> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#10872 — `fix(hipblaslt): opt BLIS CPU reference into multiple threads by default`](https://github.com/ROCm/rocm-libraries/pull/10872)
**Base:** `develop`
**Files:** 3 changed (+47/-2)
**Assessment:** REQUEST CHANGES
**Risk:** 2/5 — client/test code only, but one advertised environment-override
case silently runs single-threaded with the BLIS package downloaded by the
project's normal build task.

## Tests

I reviewed and tested PR head `7f86a54432d`. Its current three-way merge with
`develop` is clean.

I configured separate BLIS-enabled and BLIS-disabled out-of-tree builds with
the device library disabled, then built the changed static library and its main
executable consumer:

```bash
cmake -S $SRC_DIR/projects/hipblaslt -B $BLIS_BUILD -G Ninja \
  -DGPU_TARGETS=gfx1151 \
  -DCMAKE_BUILD_TYPE=Release \
  "-DCMAKE_PREFIX_PATH=$ROCM_PATH;$ROCM_PATH/hcc;$ROCM_PATH/hip" \
  -DCMAKE_MODULE_PATH=$ROCM_PATH/hip/cmake \
  -DCMAKE_CXX_COMPILER=$ROCM_PATH/bin/amdclang++ \
  -DCMAKE_C_COMPILER=$ROCM_PATH/bin/amdclang \
  -DCMAKE_Fortran_COMPILER=gfortran \
  -DCMAKE_INSTALL_PREFIX=$BLIS_INSTALL \
  -DHIPBLASLT_ENABLE_DEVICE=OFF \
  -DHIPBLASLT_ENABLE_CLIENT=ON \
  -DHIPBLASLT_BUILD_TESTING=OFF \
  -DTENSILELITE_BUILD_TESTING=OFF \
  -DHIPBLASLT_ENABLE_YAML=OFF \
  -DHIPBLASLT_ENABLE_ROCROLLER=OFF \
  -DHIPBLASLT_ENABLE_BLIS=ON \
  -DBLIS_ROOT=$BLIS_ROOT

cmake -S $SRC_DIR/projects/hipblaslt -B $LAPACK_BUILD -G Ninja \
  -DGPU_TARGETS=gfx1151 \
  -DCMAKE_BUILD_TYPE=Release \
  "-DCMAKE_PREFIX_PATH=$ROCM_PATH;$ROCM_PATH/hcc;$ROCM_PATH/hip" \
  -DCMAKE_MODULE_PATH=$ROCM_PATH/hip/cmake \
  -DCMAKE_CXX_COMPILER=$ROCM_PATH/bin/amdclang++ \
  -DCMAKE_C_COMPILER=$ROCM_PATH/bin/amdclang \
  -DCMAKE_Fortran_COMPILER=gfortran \
  -DCMAKE_INSTALL_PREFIX=$LAPACK_INSTALL \
  -DHIPBLASLT_ENABLE_DEVICE=OFF \
  -DHIPBLASLT_ENABLE_CLIENT=ON \
  -DHIPBLASLT_BUILD_TESTING=OFF \
  -DTENSILELITE_BUILD_TESTING=OFF \
  -DHIPBLASLT_ENABLE_YAML=OFF \
  -DHIPBLASLT_ENABLE_ROCROLLER=OFF \
  -DHIPBLASLT_ENABLE_BLIS=OFF

cmake --build $BLIS_BUILD --target hipblaslt-clients-common --parallel 8
cmake --build $LAPACK_BUILD --target hipblaslt-clients-common --parallel 8
cmake --build $BLIS_BUILD --target hipblaslt-bench --parallel 8
cmake --build $LAPACK_BUILD --target hipblaslt-bench --parallel 8
```

Results:

- BLIS client-common build: passed in 61.20 seconds.
- LAPACK-only client-common build: passed in 61.91 seconds.
- BLIS `hipblaslt-bench` incremental build/link: passed in 16.09 seconds.
- LAPACK-only `hipblaslt-bench` incremental build/link: passed in 16.08
  seconds.
- The BLIS executable contains `setup_blis()` and the inline function's
  process-wide static guard. The LAPACK-only executable contains neither, and
  its consumer compile command does not define `HIPBLASLT_ENABLE_BLIS`.

I then compiled the standalone probe in the appendix against the AOCL BLIS 2.0
package that `tasks.py` downloads when no system BLIS is installed. Eight
process-isolated policy cases were checked: 7 matched the stated contract, 1
failed, 0 were skipped, and 0 errored.

Passing cases included:

- a 24-processor affinity mask selected 8 threads;
- one- and two-processor masks selected 1 and 2 threads;
- a 12-processor mask remained capped at 8;
- `OMP_NUM_THREADS=3` selected 3;
- `BLIS_NUM_THREADS=4 OMP_NUM_THREADS=3` selected 4; and
- an empty `BLIS_NUM_THREADS` with no OMP request selected the default 8.

The failing case was:

```bash
BLIS_NUM_THREADS= OMP_NUM_THREADS=3 $BUILD_DIR/setup_blis_probe
```

The PR produced:

```text
nt=0 jc=-1 pc=-1 ic=-1 jr=-1 ir=-1
```

For this BLIS version, an operation with non-positive `nt` and no manual loop
ways falls back to one thread, so the explicit OMP request is lost.

I tested a minimal correction that explicitly restores the OMP value when the
higher-precedence BLIS variable exists but is empty. The failing case then
reported `nt=3`; the existing BLIS-over-OMP and ordinary OMP cases still
reported 4 and 3, and the focused client-common target rebuilt successfully in
1.07 seconds. The experiment was removed, and the untouched PR target was
rebuilt successfully in 1.15 seconds.

Additional checks:

```bash
git diff --check HEAD^..HEAD
git merge-tree --write-tree origin/develop HEAD
```

Both passed.

As of August 17, 2026, the required public Math CI summary, TheRock summary,
and pre-commit checks pass. The replacement TheRock run builds and tests the
hipBLASLt path successfully; older jobs displayed as failures belong to
cancelled initial runs. Codecov reports 52.00% patch coverage and fails its
69.42% patch target, which is consistent with the new environment/affinity
policy lacking direct tests.

## Summary

The PR removes a dead static initializer from the BLIS archive member and makes
the first inline `cblas_gemm()` dispatch call `setup_blis()` through a
thread-safe function-local static. A public compile definition ensures only
BLIS-linked consumers emit that reference, which makes the linker pull
`blis_interface.cpp` into the client executable.

At setup, the code initializes BLIS, preserves nonempty `OMP_NUM_THREADS` or
`BLIS_NUM_THREADS` requests, and otherwise sets a process-global default of the
smaller of the current Linux affinity count and eight. Non-Linux platforms fall
back to `std::thread::hardware_concurrency()`. BLIS-disabled builds retain the
existing path.

The lazy archive-linkage fix and compile-definition propagation work as
intended. The blocking issue is the interaction between the PR's
“set-but-empty means unset” rule and the older BLIS parser used by the project's
fallback dependency.

## Actionable items

1. **`projects/hipblaslt/clients/common/src/blis_interface.cpp:49-59,67-71`
   — preserve `OMP_NUM_THREADS` when `BLIS_NUM_THREADS` is present but empty.**

   `setup_blis()` initializes BLIS before the helper examines the environment.
   AOCL BLIS 2.0's environment reader treats any non-null
   `BLIS_NUM_THREADS` value as present and applies `strtol()` directly, so an
   empty string becomes zero rather than the “not set” sentinel. Because BLIS
   gives its variable precedence over `OMP_NUM_THREADS`, initialization does
   not consume the OMP value.

   The helper then checks OMP first. With
   `BLIS_NUM_THREADS="" OMP_NUM_THREADS=3`, it sees the nonempty OMP request and
   returns without repairing BLIS's zero thread count. BLIS consequently uses
   its single-thread fallback. This contradicts both stated contracts: the
   explicit OMP choice is not respected, and an empty BLIS value does not
   behave as unset.

   Resolve the two variables using BLIS precedence while accounting for an
   empty higher-precedence value. When BLIS is empty and OMP is nonempty,
   explicitly transfer the OMP request into the initialized BLIS runtime (or
   use another approach that does not temporarily mutate the process
   environment). Preserve BLIS's parsing behavior for values such as OpenMP
   thread lists.

   Add direct process-isolated tests covering the cross-product of absent,
   empty, and nonempty BLIS/OMP values, including this exact counterexample,
   plus one affinity-cap case. Run the same tests with the fallback BLIS package
   used by `tasks.py`, not only a newer system AOCL installation. Also correct
   the comment on lines 51-52: BLIS documents that these environment variables
   are read once during initialization, not on every simple-interface call.

## Suggestions

1. **`projects/hipblaslt/clients/common/src/blis_interface.cpp:49-64` —
   clarify or preserve prior BLIS runtime-API configuration.**

   With neither environment variable set, a process that has already called
   `bli_thread_set_num_threads(2)` is changed to 8 by this helper. I confirmed
   that sequence against the same BLIS package. Since the setting is
   process-global, this can override another component's explicit runtime
   policy even though the PR describes existing thread choices as preserved.

   Either preserve detectable prior runtime configuration before installing
   the hipBLASLt default, or narrow the documented override contract to
   environment variables and explain that the client owns the global BLIS
   runtime setting. Include the chosen behavior in the direct policy tests.

## Commentary

AOCL BLIS 4.2 handles an empty `BLIS_NUM_THREADS` differently: it treats a
non-positive value as invalid and consults the OpenMP runtime. That does not
remove this issue, because the repository's normal clean-machine fallback
downloads AOCL BLIS 2.0, and the PR is intended to improve those manual client
builds.

The function-local static is a good fit for the archive-linking problem. It
makes initialization lazy, is thread-safe for concurrent first calls, and
avoids changing LAPACK-only consumers. The final executable inspection confirms
that the new reference actually pulls the formerly dead archive member.

## Appendix: empty-BLIS override reproducer

Save as `$BUILD_DIR/setup_blis_probe.cpp`:

```cpp
#include <blis.h>
#include <cstdio>

void setup_blis();

int main()
{
    setup_blis();
    std::printf("nt=%lld jc=%lld pc=%lld ic=%lld jr=%lld ir=%lld\n",
                static_cast<long long>(bli_thread_get_num_threads()),
                static_cast<long long>(bli_thread_get_jc_nt()),
                static_cast<long long>(bli_thread_get_pc_nt()),
                static_cast<long long>(bli_thread_get_ic_nt()),
                static_cast<long long>(bli_thread_get_jr_nt()),
                static_cast<long long>(bli_thread_get_ir_nt()));
}
```

Compile and run against the BLIS package installed by the project's build task:

```bash
$CXX -std=c++17 -O2 \
  -I$BLIS_ROOT/include/blis \
  $BUILD_DIR/setup_blis_probe.cpp \
  $SRC_DIR/projects/hipblaslt/clients/common/src/blis_interface.cpp \
  $BLIS_ROOT/lib/libblis-mt.a \
  -fopenmp -lpthread -lm -ldl \
  -o $BUILD_DIR/setup_blis_probe

BLIS_NUM_THREADS= OMP_NUM_THREADS=3 $BUILD_DIR/setup_blis_probe
```

The PR reports `nt=0`; the tested correction reports `nt=3`.
