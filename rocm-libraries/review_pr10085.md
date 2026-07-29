> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#10085 — `feat(hipblaslt): add GPU-side correctness reference (--check_ref)`](https://github.com/ROCm/rocm-libraries/pull/10085)
**Base:** `develop`
**Files:** 13 changed (+1271/-103)
**Assessment:** REQUEST CHANGES
**Risk:** 4/5 — client-only code, but it is a test oracle: a false pass can hide a
library correctness regression, and the current CI tests do not exercise the new
oracle's failure behavior.

## Tests

No GPU tests were run locally because this system has no ROCm-capable GPU.

The PR's client-common target was configured and compiled for gfx1151:

```bash
cmake -S $SRC_DIR/projects/hipblaslt -B $BUILD_DIR -G Ninja \
  -DCMAKE_C_COMPILER=$ROCM_PATH/bin/amdclang \
  -DCMAKE_CXX_COMPILER=$ROCM_PATH/bin/amdclang++ \
  -DCMAKE_Fortran_COMPILER=gfortran \
  -DCMAKE_PREFIX_PATH=$ROCM_PATH \
  -DCMAKE_MODULE_PATH=$SRC_DIR/cmake/modules \
  -DCMAKE_BUILD_TYPE=Release \
  -DGPU_TARGETS=gfx1151 \
  -DHIPBLASLT_ENABLE_DEVICE=OFF \
  -DHIPBLASLT_ENABLE_CLIENT=ON \
  -DHIPBLASLT_BUILD_TESTING=OFF \
  -DHIPBLASLT_ENABLE_SAMPLES=OFF \
  -DHIPBLASLT_ENABLE_BLIS=OFF \
  -DHIPBLASLT_ENABLE_AMD_SMI=OFF \
  -DHIPBLASLT_ENABLE_ROCROLLER=OFF

cmake --build $BUILD_DIR --target hipblaslt-clients-common --parallel 8
git diff --check origin/develop...HEAD
git merge-tree --write-tree origin/develop HEAD
```

Results:

- `hipblaslt-clients-common`: built successfully in 67.95 seconds.
- The new `gpu_compare.cpp` emitted two warnings because the return values from
  `hipFree()` are ignored.
- `git diff --check`: passed.
- Current three-way merge with `develop`: clean.

The latest public TheRock rerun compiled gfx94X, gfx950, and Windows gfx1151
configurations successfully. All six gfx94X hipBLASLt shards passed, but the new
YAML entries were filtered out there by `gpu_arch: '950'`. The gfx950 test job
was skipped. The Windows hipBLASLt job stopped before running the suite because
the runner's `hipInfo.exe` sanity check timed out after three minutes. The
accompanying HOST_ASAN run also failed before compiling hipBLASLt because its
toolchain could not locate `libclang_rt.asan-x86_64.so`. Those two failures are
runner/toolchain infrastructure rather than evidence against this PR, but the
rerun still added no public functional execution of the new gfx950-only tests.

Math CI reported its hipBLASLt preliminary, precheckin, codecov,
static-analysis, and TensileLite-unit lanes passing.

### CPU-reference performance investigation

The CPU implementations used for this comparison are unchanged between the PR
head and the measured source revision (the relevant source blobs are identical).
Measurements used a Release build on a 12-core/24-thread x86-64 CPU, with
`OMP_NUM_THREADS=12` and `OPENBLAS_NUM_THREADS=12`.

The hipBLASLt measurement called the existing client `cblas_gemm<float>()`
wrapper, including its input conversion/copy and output conversion. The build
used OpenBLAS (`HIPBLASLT_ENABLE_BLIS=OFF`). The TensileLite measurement used
the standalone `cpu-gemm-driver --tryFastPath`; its post-timing validation was
temporarily disabled so it did not run a second, slow golden GEMM after each
sample. That one-line local change was restored and the target rebuilt afterward.

Representative median times:

| Square GEMM | hipBLASLt CPU ref f32 | TensileLite fast CPU ref f32 | NumPy `@` f32 | raw OpenBLAS SGEMM |
|---:|---:|---:|---:|---:|
| 128 | 0.14 ms warm / 1.84 ms first call | 1.59 ms | 0.026 ms | 0.035 ms |
| 512 | 3.18 ms | 3.74 ms | 1.22 ms | 0.33 ms |
| 1024 | 4.37 ms | 19.73 ms | 5.27 ms | 1.65 ms |
| 2048 | 19.73 ms | 79.43 ms | 23.95 ms | 10.46 ms |
| 4096 | 112.95 ms | not measured | 143.52 ms | 80.65 ms |

At 2048 cubed, type conversion changes the picture:

| Input/output type | hipBLASLt CPU ref | TensileLite fast CPU ref |
|---|---:|---:|
| f32 | 19.73 ms | 79.43 ms |
| f16 | 84.77 ms | 84.57 ms |
| bf16 | 22.01 ms | 93.07 ms |

These numbers show that the existing hipBLASLt baseline is not generally a naive
triple loop. For dimensions or leading dimensions above 600,
`cblas_interface.cpp` calls the linked optimized `cblas_sgemm()`/`cblas_dgemm()`;
for smaller problems it uses the in-tree OpenMP `small_gemm()` because of a
documented BLIS issue. The build interface also already exposes
`HIPBLASLT_ENABLE_BLIS` / `--cpu-ref-lib blis|lapack`; with BLIS disabled, the
LAPACK/BLAS dependency can resolve to OpenBLAS as it did here.

NumPy f32 is therefore not orders of magnitude faster than the real hipBLASLt
CPU path at large sizes; they are in the same broad range, and both ultimately
use optimized BLAS. NumPy f16 is not a useful fast-BLAS baseline: on this system
it achieved only about 0.7 GFLOP/s and took about 3.0 seconds for 1024 cubed,
where the hipBLASLt wrapper took about 22 ms by converting to f32 and calling
SGEMM.

The README's retained 128-cubed example reports `ref-us=43688` (43.7 ms and
0.096 GFLOP/s). That is two orders of magnitude slower than the measured warm
hipBLASLt wrapper and over an order slower than its first invocation here. It is
an old static example, not credible performance evidence for this PR.

No corresponding GPU-reference timings are supplied by the PR, and none could
be collected locally. Consequently the claimed speedup, crossover size, and
type dependence cannot currently be established. The likely benefit is limited
to verification: computing `D_gold` and comparing output on the device avoids
the host reference computation, device-to-host output transfer, and host-side
comparison. It does not accelerate the hipBLASLt kernel, solution search, data
initialization, or normal unverified benchmark path.

## Summary

The PR adds `--check_ref cpu|gpu|both` to hipBLASLt's client layer. GPU mode
computes a naive, independent, one-thread-per-output GEMM into a device
`D_gold`, then runs a second device kernel that reduces unit-check, norm,
allclose, ULP, and non-finite metrics. Both mode retains the existing CPU
reference and checks the library output against both references.

The current GPU reference accepts:

- matching f32, f16, or bf16 A/B;
- any f32/f16/bf16 C and D combination;
- f32 compute;
- ordinary or strided-batched GEMM;
- default epilogue with no scaling, auxiliary output, bias, activation,
  swizzling, rotation, in-place C/D, grouped GEMM, or pointer-array batching.

Unsupported configurations fail loudly through `gpu_ref_supported()`, which is
a good central gate. The implementation is independent of TensileLite's
production kernels, also a good property for a correctness oracle.

The current feature is nevertheless much narrower than the hipBLASLt workloads
for which verification cost is most painful. Extending it is not just a matter
of adding more type tags:

- f64 needs double accumulation and a corresponding comparison path;
- integer GEMM needs exact integer accumulation, overflow, saturation, and
  output-conversion semantics;
- complex types need conjugation and complex error metrics;
- fp8/fp4/fp6 need compute-input quantization, scalar/vector/block/MX scaling,
  and exact rounding behavior;
- epilogues need bias, activation, auxiliary output, amax, gradient, and scaling
  semantics.

The description says broader coverage will follow, but it does not give a
support matrix, architecture policy, ordering, or linked follow-up plan. The
current dispatch structure is manageable at three float-class types; extending
the 685-line reference/compare implementation without direct primitive tests
will make it increasingly difficult to distinguish intended semantic
differences from drift.

## Actionable items

1. **`projects/hipblaslt/clients/common/src/gpu_compare.cpp:199-213` and
   `projects/hipblaslt/clients/common/include/gpu_compare.hpp:17-24` — GPU mode
   weakens the existing verifier for matching NaN/Inf values.**

   A one-element counterexample with `gpu[0] = ref[0] = NaN` takes the
   `both_nan` branch, records no mismatch, contributes nothing to the norm,
   leaves every allclose bin at zero, and produces a passing unit/norm/allclose
   result. The existing CPU allclose uses `equal_nan=false`, so matching NaNs
   fail; the CPU norm also becomes NaN and fails. Matching same-signed
   infinities similarly pass the GPU norm while the CPU norm fails. Thus merely
   selecting `--check_ref gpu` can turn a default CPU-reference failure into a
   pass.

   Preserve the existing CPU verification contract in GPU mode, or explicitly
   change both implementations to one documented contract. At minimum, make
   non-finite pairs poison the norm/allclose result even when unit equality
   treats matching NaNs/infinities as equal. Add direct matching-NaN,
   mismatching-NaN, matching-infinity, and mismatching-infinity tests.

2. **`projects/hipblaslt/clients/tests/data/matmul_gtest.yaml:3331-3389` — the
   tests exercise only the zero-error happy path and therefore do not validate
   the new comparison oracle.**

   Every new case uses 128-cubed `integer_exact` inputs and diagonal A/B/C/D
   types. The expected comparison is zero for every metric. An implementation
   that accidentally leaves the reduction buffers at zero can pass all 56
   cases. The tests do not establish failure detection, allclose threshold
   selection, ULP max/average, non-finite handling, padded leading dimensions,
   mixed C/D dispatch, large-K tolerance behavior, `alpha=0`, or launch/error
   propagation.

   Add focused tests that populate two device buffers with controlled values and
   call `compare_gemm_device()` directly. Include at least one deliberate finite
   mismatch per metric, NaN/Inf cases, nontrivial `ldd`/stride padding, multiple
   batches with different errors, and every advertised output type. Add
   end-to-end cases for mixed C/D types and a non-integer large-K problem. The
   tests should demonstrate that perturbing either the reference kernel or the
   comparison result makes CI fail.

3. **`projects/hipblaslt/clients/tests/data/matmul_gtest.yaml:3340,3365,3389` —
   functional coverage is unnecessarily tied to gfx950.**

   The new kernels contain no gfx950-specific behavior, while their use of
   device double reductions, atomics, grid limits, and runtime type conversion
   is exactly what should be exercised across architecture families. In the
   completed public TheRock run, all gfx94X hipBLASLt shards passed without
   selecting these tests and the gfx950 test job was skipped. That leaves a
   single separate CI environment as the functional gate.

   Run a small mandatory `check_ref` case on every supported hipBLASLt GPU
   family represented in precheckin CI (at least gfx94X, gfx950, and a current
   RDNA/gfx11-or-later lane), or document a real architecture restriction in
   `gpu_ref_supported()` and the user-facing help. Keep larger combinatorial
   coverage on one architecture if runtime is a concern.

4. **`projects/hipblaslt/clients/common/include/testing_matmul.hpp:2088-2094` —
   invalid serialized `check_ref` values silently run the CPU path.**

   The CLI rejects strings outside `cpu|gpu|both`, but YAML/datafile input is an
   integer. Any value other than 1 or 2 makes `use_gpu_ref` false and
   `use_cpu_ref` true. A typo such as `check_ref: 3` therefore passes CI while
   not testing the requested GPU path, contrary to the reliability goal.

   Validate the enum range for every input source before selecting a reference,
   reject unknown values, and add an invalid-datafile regression test.

5. **`projects/hipblaslt/clients/common/include/argument_model.hpp:109-122`,
   `projects/hipblaslt/clients/common/include/testing_matmul.hpp:5031-5443`, and
   `projects/hipblaslt/clients/bench/README.md:94-100` — the performance claim
   and reported baseline are not sufficiently defined.**

   `ref-us` identifies neither the implementation nor the linked CBLAS backend.
   In `both` mode it sums CPU and GPU reference time, so `ref-Gflops` is not the
   throughput of either reference. Renaming the long-standing `CPU-us` and
   `CPU-Gflops` columns for default CPU mode also changes the CSV schema for
   downstream consumers. The README keeps an implausibly slow old 128-cubed
   baseline while the PR supplies no CPU-vs-GPU measurements.

   Preserve or version the existing CPU column names, and report separate
   `cpu-ref-us` and `gpu-ref-us` values in both mode rather than summing them.
   Document whether the CPU path selected BLIS, another CBLAS provider, or the
   small in-tree GEMM. Before merge, provide reference-only and end-to-end
   verification timings for representative small/large shapes, f32/f16/bf16,
   and at least the CI architectures. Include warm/cold policy, thread count,
   CBLAS provider, GPU architecture, and comparison/copy costs. This is needed
   to establish what the change actually speeds up and where it regresses.

## Suggestions

1. **`projects/hipblaslt/clients/common/src/gpu_compare.cpp:302-327` — use an
   existing checked device-buffer abstraction, or explicitly check/log cleanup
   failures.**

   The local gfx1151 build emits `nodiscard` warnings for both `hipFree()` calls.
   Ignoring cleanup errors also conflicts with the surrounding "fail loudly on
   HIP error" policy. A non-throwing destructor can still log a cleanup failure;
   an existing RAII buffer would reduce bespoke lifetime code.

2. **`projects/hipblaslt/clients/common/src/reference_device.cpp:13-23` and
   `projects/hipblaslt/clients/common/src/gpu_compare.cpp:19-29` — factor the
   duplicated HIP error helper.**

   The two copies already define the same logging contract. A small shared
   internal helper would prevent their behavior or wording from diverging as
   more GPU-reference components are added.

3. **Add a user-facing support matrix and follow-up sequence.**

   Keep `gpu_ref_supported()` as the executable source of truth, but document
   the current matrix and identify the intended order for architecture, type,
   scaling, epilogue, and batching expansion. Without that, "broader coverage
   later" gives CI owners no basis for deciding which suites may safely migrate
   from CPU to GPU verification.

## Commentary

The independent naive GPU GEMM is a defensible correctness design: using
hipBLASLt, TensileLite, or another optimized GPU GEMM as the oracle would risk
sharing the same implementation defect. The central support gate and loud
unsupported-config errors are also preferable to silently falling back for a
requested GPU check.

The device comparator is where most of the avoidable risk and complexity lies.
It reimplements four existing host metrics and deliberately differs from some of
their edge semantics. That can still be maintainable, but only if its primitive
contracts are directly tested with adversarial inputs. End-to-end exact GEMMs
are not a substitute for those tests.

The existing TensileLite fast CPU reference is useful context but is not an
obvious replacement for hipBLASLt's current CBLAS path. In these local simple
GEMMs, hipBLASLt's OpenBLAS-backed reference was about four times faster than
the TensileLite fast path for large f32 and bf16, and approximately equal for
f16. TensileLite supports a broader and more detailed type/feature model, but
reusing it would add coupling to the same backend ecosystem and would not by
itself solve the simple-GEMM baseline.

The most valuable next evidence is a GPU timing matrix. The CPU results show a
plausible opportunity—especially for f16 conversion and device-to-host
verification overhead—but they do not show that this one-thread-per-output GPU
kernel beats optimized host SGEMM for f32/bf16, nor by how much. That question
should be answered before the new path becomes a CI strategy.
