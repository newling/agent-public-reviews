> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#11377 — `refactor(hipblaslt): remove obsolete preprocessor branches`](https://github.com/ROCm/rocm-libraries/pull/11377)  
**Scope:** head `0c1b0ae8598`, including the two current review threads  
**Assessment:** CHANGES REQUESTED  
**Risk:** 3/5 — most changes delete inactive branches, but the pull request also
changes a conversion in a public low-precision header and relies on the ROCm 7
toolchain floor.

## Tests

I configured a standalone `gfx942` build with device-library generation and
GoogleTest disabled, then built the affected host/runtime targets:

```bash
cmake -S $SRC_DIR/projects/hipblaslt -B $BUILD_DIR -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER=$ROCM_PATH/bin/amdclang++ \
  -DCMAKE_C_COMPILER=$ROCM_PATH/bin/amdclang \
  -DCMAKE_Fortran_COMPILER=$ROCM_PATH/lib/llvm/bin/flang-new \
  -DCMAKE_PREFIX_PATH="$ROCM_PATH;$DEPS_DIR/msgpack-cxx/root/usr;$DEPS_DIR/boost/root/usr" \
  -DCMAKE_CXX_FLAGS=-I$DEPS_DIR/openblas/root/usr/include/x86_64-linux-gnu/openblas-pthread \
  -DGPU_TARGETS=gfx942 \
  -DPython_EXECUTABLE=/usr/bin/python3 \
  -DPython3_EXECUTABLE=/usr/bin/python3 \
  -DHIPBLASLT_ENABLE_FETCH=OFF \
  -DHIPBLASLT_ENABLE_HOST=ON \
  -DHIPBLASLT_ENABLE_DEVICE=OFF \
  -DHIPBLASLT_ENABLE_CLIENT=ON \
  -DHIPBLASLT_BUILD_TESTING=OFF \
  -DTENSILELITE_ENABLE_HOST=ON \
  -DTENSILELITE_ENABLE_CLIENT=OFF \
  -DTENSILELITE_BUILD_TESTING=OFF \
  -DHIPBLASLT_ENABLE_YAML=OFF \
  -DHIPBLASLT_ENABLE_ROCROLLER=OFF \
  -DHIPBLASLT_ENABLE_MXDATAGENERATOR=OFF \
  -DHIPBLASLT_ENABLE_BLIS=OFF \
  -DBLAS_LIBRARIES=$DEPS_DIR/openblas/root/usr/lib/x86_64-linux-gnu/openblas-pthread/libblas.a \
  -DLAPACK_LIBRARIES=$DEPS_DIR/openblas/root/usr/lib/x86_64-linux-gnu/openblas-pthread/liblapack.a \
  -Dmsgpack-cxx_DIR=$DEPS_DIR/msgpack-cxx/root/usr/lib/x86_64-linux-gnu/cmake/msgpack-cxx \
  -DBoost_INCLUDE_DIR=$DEPS_DIR/boost/root/usr/include

cmake --build $BUILD_DIR \
  --target tensilelite-host hipblaslt \
  --parallel 48

cmake --build $BUILD_DIR \
  --target hipblaslt-clients-common \
           hipblaslt-api-overhead \
           hipblaslt-bench-groupedgemm-fixed-mk \
           hipblaslt-bench-extop-layernorm \
           hipblaslt-bench-extop-matrixtransform \
           hipblaslt-bench-extop-softmax \
           hipblaslt-bench-extop-amax \
  --parallel 48
```

Results:

- The clean `tensilelite-host` and `hipblaslt` build completed 60 of 60 build
  steps in 42.55 seconds.
- The clean client-common build completed 71 of 71 build steps in 42.69
  seconds. The six executables whose unused compile definition is removed then
  completed 12 of 12 compile/link steps in 5.67 seconds.
- The compiler emitted pre-existing `-Wpsabi` warnings for FP6 vector arguments;
  no build step failed.

I also compiled a one-kernel `gfx942` probe equivalent to the new code in
`auxiliary_gtest.cpp`:

```bash
$ROCM_PATH/bin/amdclang++ -std=c++17 -x hip --offload-arch=gfx942 \
  -I$SRC_DIR/projects/hipblaslt/library/include/hipblaslt \
  -c $SCRATCH_DIR/bf8_fnuz_compile.cpp -o $SCRATCH_DIR/bf8_fnuz.o
```

The probe passed against the PR head in 0.77 seconds. Against the base header,
it failed in 0.36 seconds with `reference to __host__ function 'operator
_Float16' in __global__ function`. This demonstrates that changing the guard
back to `HIP_FP8_TYPE_OCP` makes the new compile test fail. The equivalent probe
source is already committed in `clients/tests/src/auxiliary_gtest.cpp`, so no
separate appendix is needed.

`git diff --check 179111941a7fda47712086bb609950b9ce3e1d44..0c1b0ae859845ee2f05557e330d818d833089666`
passed.

The public checks provide broader coverage: Linux `gfx94X` build and all six
hipBLASLt test shards passed; Linux `gfx950` and `gfx125X` builds passed;
Windows `gfx1151` build and hipBLASLt tests passed; and the host-address-
sanitizer quick test passed. The `gfx1250` FFM check reports 125 passes and 3
45-minute timeouts. The hipSPARSELt Math CI failure is infrastructure-related:
its test command exited successfully, after which Jenkins failed on a GitHub
API rate limit. The three project Codecov checks fail their absolute 80%
targets, while the patch check passes and the report says every modified
coverable line is covered.

## Summary

The pull request deletes inactive `#if 0` code, unused compile definitions,
unreachable alternatives, and checks for HIP versions older than the supported
ROCm 7 toolchain. It also uses `_WIN32` consistently and requires the C++17
filesystem implementation already selected by the targets.

The one product-behavior change repairs the `hipblaslt_bf8_fnuz` conversion to
`_Float16`. On `gfx942`, HIP enables FNUZ device conversions but disables OCP
device conversions. The old OCP predicate therefore declared this FNUZ
conversion as host-only. The new predicate and compile probe restore the
device-callable conversion.

## Actionable items

1. **PR description — record the BF8-FNUZ fail-before/pass-after evidence and
   make its defect tracking explicit.**

   The change is correctly covered by a shared-CI compile test, but the current
   description records only that the patched compilation passed. It does not
   show that the test rejects the unpatched predicate. Add the compiler error
   above and either state explicitly that issue #10605 tracks this defect or
   link a focused defect. This completes the defect-fix evidence and artifact
   linking required by the review policy.

## Suggestions

1. **`projects/hipblaslt/library/include/hipblaslt/hipblaslt_bfloat6.h:30` —
   link the upstream fix and give the workaround a removal condition.**

   The upstream implementation is tracked by `ROCM-22232` and was changed by
   [ROCm/rocm-systems#3530](https://github.com/ROCm/rocm-systems/pull/3530).
   That change removes the `fp6x32_packed` bitfield representation and the
   failing size assertion in favor of byte-wise packing. The ROCm 7.1 header
   still contains the old implementation. Mention the upstream change and say
   that this guard can be removed after the minimum supported ROCm release
   contains it.

2. **`projects/hipblaslt/clients/tests/src/auxiliary_gtest.cpp:38-39` — say
   “device-enabled FNUZ conversion” instead of “native FNUZ support.”**

   `HIP_FP8_TYPE_FNUZ` means HIP exposes the conversion to device code; it does
   not necessarily mean the target has a native conversion instruction. For
   example, the proposed HIP support for additional targets uses a software
   conversion path. The narrower wording will remain accurate if that support
   lands.

## Commentary

The removed `ROCBLASLT_INTERNAL_API` definitions do not remove or hide an API.
At the PR base, the only seven occurrences of that exact token in the entire
hipBLASLt tree are the seven CMake definitions deleted here. No source or header
tests the token. The similarly named rocBLAS compatibility switch is
`ROCBLAS_INTERNAL_API`, without `LT`, and is a separate macro.

The compile-only BF8-FNUZ test is the appropriate lowest-level test. The defect
is whether device compilation accepts the conversion; launching the kernel
would not add evidence about that declaration qualifier.

The latest tested synthetic merge is 32 commits behind current `develop`.
`develop` has since changed `tensile_host.cpp` for the Stream-K synchronization
fix. A current three-way merge is clean and keeps this PR's changes limited to
the inactive diagnostic blocks, but the combined source has not run through
PR checks. Rebase and rerun before merge.

## Review questions

1. **Changed functionality:** dead compatibility and diagnostic branches are
   removed, platform checks are normalized, and the BF8-FNUZ conversion becomes
   callable from device code when HIP enables FNUZ conversions.
2. **Appropriate test level:** host/client builds for the cleanup and a device
   compile test for the conversion. Both are present; Windows and multiple GPU
   architectures are covered by public checks.
3. **Omitted tests or flags:** no feature flag is needed because the functional
   change restores an existing conversion on the intended path. No runtime test
   is required for a declaration-availability defect.
4. **Adjacent tests:** Windows client builds, the `gfx950` OCP path, the
   hipSPARSELt consumer of shared TensileLite code, and the current-base merge
   are the relevant adjacent checks. The first two pass; the hipSPARSELt job's
   reported failure is a GitHub API-rate-limit error; the current-base merge
   still needs a PR rerun.

## Recommended PR-description rewrite

```markdown
ISSUE ID : #10605

## Motivation

hipBLASLt still contains compile-time branches for HIP versions older than the
ROCm 7 toolchain it supports, along with disabled diagnostics and alternatives
that select identical implementations. These branches obscure which paths are
active. The audit also found that the BF8-FNUZ conversion to `_Float16` used the
OCP capability predicate, which makes the conversion host-only in `gfx942`
device code.

## Technical Details

- Use `HIP_FP8_TYPE_FNUZ` for the `hipblaslt_bf8_fnuz` conversion to
  `_Float16` and add a device-compilation regression kernel.
- Remove inactive `#if 0` blocks, unused compile definitions, an unavailable
  FP6x16 alternative, and pre-ROCm-7 header fallbacks.
- Use `_WIN32` consistently for source-level Windows checks.
- Use the C++17 filesystem library selected by the existing target settings.

The FP6 host-fallback workaround remains because supported ROCm headers still
contain the older packed-bitfield implementation. Its upstream replacement is
tracked by ROCM-22232 and ROCm/rocm-systems#3530.

## Test Plan

- Build the hipBLASLt and TensileLite host libraries and all affected client
  executables for `gfx942`.
- Compile the BF8-FNUZ conversion kernel for `gfx942` and verify that restoring
  the old predicate produces a host-function-from-device compilation error.
- Run Linux `gfx94X`, Linux `gfx950`/`gfx125X` build coverage, Windows
  `gfx1151`, host address-sanitizer, precheckin, and static-analysis checks.

## Test Result

- The `gfx942` host/runtime/client build passed.
- The BF8-FNUZ probe passes on this branch and fails against the base header
  with `reference to __host__ function 'operator _Float16' in __global__
  function`.
- Linux `gfx94X` build/tests, Linux `gfx950` and `gfx125X` builds, Windows
  `gfx1151` build/tests, host address-sanitizer, hipBLASLt precheckin, and
  hipBLASLt static analysis passed.
- The `gfx1250` FFM run completed 125 tests and timed out 3 tests at 45 minutes.
  The hipSPARSELt status failed after its test command exited successfully
  because Jenkins hit a GitHub API rate limit. The Codecov patch check passed;
  project checks remain below their absolute 80% thresholds.

## Submission Checklist

- [x] Look over the contributing guidelines at
  https://github.com/ROCm/ROCm/blob/develop/CONTRIBUTING.md#pull-requests.

## Risk level

Moderate (3/5). The patch mostly deletes inactive code, but it changes public
low-precision headers and the minimum-toolchain assumptions used by client and
runtime builds. Linux, Windows, and architecture-specific compilation cover
those paths.
```
