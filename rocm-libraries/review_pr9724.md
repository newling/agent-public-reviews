> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#9724 — `test(hipblaslt): add CPU/GPU Inf/NaN consistency check for matmul`](https://github.com/ROCm/rocm-libraries/pull/9724)
**Base:** `develop`
**Files:** 5 changed (+162)
**Assessment:** REQUEST CHANGES
**Risk:** 3/5 — client/test-only code, but this is part of the correctness oracle and
the current abstraction can both duplicate existing checks and miss a non-finite
classification mismatch.

## Tests

The gtest client was configured and compiled for gfx1151 at PR head
`ae28d1a8974b`:

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
  -DHIPBLASLT_BUILD_TESTING=ON \
  -DHIPBLASLT_ENABLE_SAMPLES=OFF \
  -DHIPBLASLT_ENABLE_BLIS=OFF \
  -DHIPBLASLT_ENABLE_AMD_SMI=OFF \
  -DHIPBLASLT_ENABLE_ROCROLLER=OFF

cmake --build $BUILD_DIR --target hipblaslt-test --parallel 8

HIPBLASLT_TENSILE_LIBPATH=$PREBUILT_TENSILE_LIBRARY \
  $BUILD_DIR/clients/hipblaslt-test \
  --gtest_filter='*matmul_special_fp_64x64*'

git diff --check origin/develop...HEAD
git merge-tree --write-tree origin/develop HEAD
```

Results:

- `hipblaslt-test` built successfully in 53.23 seconds. The changed
  `GOOGLE_TEST` implementation was compiled.
- The 25 new special-value cases passed on gfx1151: 25 passed, 0 failed,
  0 skipped in 1.82 seconds wall time (645 ms reported by gtest).
- The test binary was linked from this PR, while the unchanged gfx1151 device
  code objects were reused from an existing build because this client-only PR
  does not generate them. Without that library path, all 25 cases failed before
  matmul with missing `TensileLibrary_lazy_gfx1151.dat` /
  `Kernels.so-000-gfx1151.hsaco`; that was a local build-configuration artifact,
  not a PR failure.
- `git diff --check` passed.
- The current three-way merge with `develop` is clean.

I also isolated the exact-comparison behavior on which the existing unit path
depends:

```bash
c++ -std=c++17 -x c++ - -lgtest -lgtest_main -pthread \
  -o /tmp/gtest-inf-equality <<'EOF'
#include <gtest/gtest.h>
#include <limits>

TEST(FloatEqSemantics, MaximumFiniteComparedWithInfinity)
{
    EXPECT_FLOAT_EQ(std::numeric_limits<float>::max(),
                    std::numeric_limits<float>::infinity());
}

TEST(DoubleEqSemantics, MaximumFiniteComparedWithInfinity)
{
    EXPECT_DOUBLE_EQ(std::numeric_limits<double>::max(),
                     std::numeric_limits<double>::infinity());
}
EOF

/tmp/gtest-inf-equality --gtest_color=no
```

Both tests passed. GoogleTest's `FLOAT_EQ` / `DOUBLE_EQ` use a four-ULP
comparison and intentionally regard the largest finite value as almost equal to
infinity. This supplies a concrete false-pass case for the PR's asymmetric
pre-check.

As of July 30, 2026, Math CI and pre-commit pass. The public HOST_ASAN build
fails during its build step, the gfx950 TheRock test job is skipped, and the
Windows gfx1151 build is still in progress. The gfx94X hipBLASLt shards pass.

## Summary

The PR adds an elementwise pre-pass over each matmul D result. When the CPU
reference is infinity, the GPU result must be an infinity with the same sign;
when the CPU reference is NaN, the GPU result must be NaN. It then runs the
existing unit or norm comparison. A 25-case precheckin sweep covers five
initializations across f16, bf16, f32, TF32, and f64, with the two known TF32
infinity failures quarantined on gfx950/gfx1250.

Some special-value policy is necessary, but not necessarily as a separate
matrix traversal:

- ordinary tolerance arithmetic cannot represent matching NaNs because NaN is
  unequal to itself;
- `Inf - Inf` is NaN, so a difference norm and a relative norm with an infinite
  denominator are not meaningful without an explicit policy;
- exact infinity equality works in normal IEEE comparison, but the existing
  GoogleTest ULP equality also accepts the adjacent largest finite value;
- the existing `near_check_general()` already has an explicit scalar
  finite/NaN/infinity classification branch, while `unit_check_general()`
  already special-cases a NaN reference.

The right abstraction is therefore a shared scalar classification policy used
by each numerical comparator, with the finite values then flowing through that
comparator's normal arithmetic. The current pre-pass instead duplicates the
unit/near traversal, does not make the norm itself well-defined, and applies
only half of the classification contract.

This is expected to be a small-to-medium client-side refactor, not a new
framework or public API. The minimum correctness change is smaller still:
classify both operands symmetrically and add direct adversarial tests. Reusing
that classification from unit/near and applying it during norm's existing
conversion loop is the preferred consolidation.

The consolidation should also be neutral or favorable for performance.
`unit_check` and `near_check` currently acquire a second full
`O(M*N*batch_count)` host-memory traversal from the new pre-pass; classifying
each pair inside their existing loops removes that pass. `norm_check_general()`
already traverses the matrices to build its double-precision temporary buffers,
so it can classify or neutralize special pairs during that same traversal.

## Actionable items

1. **`projects/hipblaslt/clients/common/include/unit.hpp:702-790` and
   `projects/hipblaslt/clients/common/include/testing_matmul.hpp:1156-1186` —
   integrate non-finite classification into the comparison primitives instead
   of adding an asymmetric outer pre-pass.**

   `check_special_value_consistency_impl()` examines the GPU value only when
   the CPU value is Inf or NaN. For
   `CPU = std::numeric_limits<float>::max(), GPU = +Inf`, it does nothing.
   The following `unit_check_general()` then uses `ASSERT_FLOAT_EQ`, which
   accepts that pair because they are one representable step apart. The same
   false pass occurs for double. Thus a GPU overflow from the largest finite
   reference to infinity can pass both the new check and the existing unit
   check.

   There is also duplicated policy and work: the unit macro already handles a
   NaN reference, and `hipblaslt_near_compare_double()` already classifies both
   operands symmetrically. Conversely, the norm still computes `Inf - Inf` and
   an infinite-reference relative norm after this pre-pass, so matching special
   values remain undefined in `norm_check_general()`.

   Add one shared scalar helper that classifies both operands and returns
   “both finite,” “matching special values,” or “mismatch.” Use it inline from
   exact and near checks; for norm/allclose, reject a classification mismatch
   and neutralize matching special entries before computing the finite metric,
   or explicitly document that those metrics reject all non-finite inputs.
   Remove the extra traversal from `check()`. If a standalone pre-pass is
   retained, it must at least reject a non-finite GPU result when the reference
   is finite and should not be placed in `unit.hpp` while also defining norm
   behavior.

   This request does not require a broad rewrite. A localized implementation
   can generalize the scalar finite/NaN/infinity logic already present in
   `near.hpp`, invoke it from the existing unit/near element loops, and apply it
   while norm copies values into its temporary buffers. The required
   before-merge portion is the symmetric classification and regression tests;
   if fully defining non-finite norm semantics would expand the PR
   substantially, explicitly rejecting non-finite norm inputs and tracking the
   finite-residual behavior as a follow-up would still close the false-pass
   hole.

   Clear errors do not require the separate traversal. Have the scalar helper
   return a classification such as `both_finite`, `matching_special`, or
   `mismatching_special`; the existing matrix loop still owns `i`, `j`, and
   `batch` and can emit the same detailed message:

   ```text
   Special value mismatch: reference is +Inf but result is NaN
   at (i=3, j=7, batch=0)
   ```

   This can preserve the PR's useful diagnostic while giving all comparison
   modes one consistent error path.

2. **`projects/hipblaslt/clients/tests/data/matmul_gtest.yaml:111-123` — add
   direct adversarial tests for the new comparison contract.**

   The new sweep defaults to `unit_check: 1`. Its Inf-to-NaN target is already
   rejected by `unit_check_general()` or `near_check_general()`, and the
   pre-existing `matmul_tf32_inf_ROCM1545` case already exercises that known
   regression. The zero and negative-zero cases never enter the new helper.
   On a correct GPU, deleting `check_special_value_consistency()` would
   therefore leave these 25 passing cases green; the end-to-end sweep does not
   establish that the new primitive is necessary or that its failure behavior
   is correct.

   Add focused comparator tests over controlled one-element or short buffers.
   Cover finite equality and mismatch, matching NaN, matching positive and
   negative infinity, Inf-to-NaN, infinity sign reversal, finite-to-NaN,
   finite-to-infinity, and both directions of largest-finite versus infinity.
   If the policy is shared with norm/allclose, directly test those metric
   results as well. At least one test should fail if the classification helper
   is replaced by a no-op.

## Suggestions

1. **`projects/hipblaslt/clients/tests/data/matmul_gtest.yaml:111-123` — clarify
   the signed-zero claim.**

   The helper checks only Inf and NaN, and the existing exact GoogleTest
   comparison treats `+0` and `-0` as equal. The current `neg_zero` GEMM also
   need not produce a negative-zero output. If preserving zero sign is part of
   the intended contract, add a direct `std::signbit` assertion and a case with
   a specified negative-zero result. Otherwise describe zero cases as ordinary
   initialization coverage rather than special-value consistency coverage.

2. **Use reference/result terminology in the reusable comparison layer.**

   `hCPU`/`hGPU` happens to describe the current caller, but the relevant
   contract is expected versus actual classification. Naming the helper and
   diagnostics around reference/result would make it usable by another host or
   device reference without encoding where each value was computed.

## Commentary

The PR is correct that NaN and infinity cannot simply be left to every existing
numeric formula. A branch is unavoidable somewhere: NaN equality is a policy
choice, and a relative norm over infinite values has no useful natural value.
The design question is where that branch belongs.

For exact and near comparisons, the branch belongs at the scalar comparison
site so every element is visited once and diagnostics retain its coordinates.
For norms, classification is part of defining the metric: matched non-finite
entries should either be excluded/neutralized before measuring the finite
residual, or make the metric explicitly unsupported. A gtest-only pre-pass in
`unit.hpp` cannot provide one coherent contract for unit, near, norm, allclose,
and benchmark verification.

Moving the branch into the existing loops should not make failures less
readable. The loop, rather than the scalar helper, can remain responsible for
formatting the assertion with expected/actual classification and matrix
coordinates. It also avoids situations in which the pre-pass and the numerical
comparator produce different messages for the same underlying mismatch.

The broader f16/bf16/f32/TF32/f64 sweep is useful regression coverage in its own
right. It should remain even if the standalone helper is removed, but its
purpose should be checking matmul special-value behavior through the normal
comparison contract rather than proving a second comparison layer.
