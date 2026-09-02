This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9936](https://github.com/ROCm/rocm-systems/pull/9936)

**Revision reviewed:** local rebased candidate `7f9982d0e553`, a three-commit
stack based on `origin/develop@4afd2ec347`. The candidate has not been
published. The public PR head remains `459c14fe8f1d`.

After the review, `origin/develop` advanced by two unrelated ROCR commits to
`391ec91ede`. The candidate therefore needs one more rebase and focused rerun
before publication.

**Public/repository status:** the upstream repository, source fork, PR, base
branch, and intended PR head branch are public. The PR is open and non-draft.
The latest GitHub query returned mergeability as unknown while the stale
published head was being recalculated. Review is still required.

**Focused build before probes:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: no work was needed; the command passed in 0.03s real, 0.02s user, and
0.01s sys.

**Submitted tensor-DMA coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Gfx1250ExecutionTest.TensorDma*'
```

Result: 23/23 passed, 0 failed, 0 skipped, and 0 errored in 2.80s real.
GoogleTest reported 2.731s.

**Temporary layout/rank counterexamples:**

I temporarily added the two tests in Appendix A, rebuilt, ran only those
tests, and removed them:

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8

time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='Gfx1250ExecutionTest.ReviewProbeTensorDma*'
```

The incremental build passed in 5.85s real. The probes produced 0/2 passes in
0.91s real:

- a rank-3 `{2,2,2}` tensor with internal strides `{4,2}` was rejected as
  `tensor DMA iterate overlapping strides`, although
  `x + 4*y + 2*z` maps its coordinate box one-to-one onto offsets `0..7`;
- a rank-2 gather tensor with extents `{2,0}` loaded
  `0x53000000, 0x53000001` into LDS instead of zero-filling, then stored
  `0x54000000, 0x54000001` to global memory instead of suppressing the writes.

Both failures are deterministic model-contract failures, not environment
artifacts.

**Final build after removing probes:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: the two affected compilation steps passed in 5.81s real, 5.73s user,
and 0.58s sys. The submitted 23-test selection above then passed.

**Formatting and diff hygiene:**

```bash
time -p .venv/bin/pre-commit run --files \
  $(git diff --name-only 4afd2ec347..HEAD)
git diff --check 4afd2ec347..HEAD
```

Result: every applicable hook passed in 0.31s real, `git diff --check`
passed, and no tracked modification remains.

On the older public head, formatting, release, Clang ASan/UBSan, GCC
ASan/UBSan, TSan, TheRock packaging/sanity, HIP NVIDIA, multi-architecture,
and repository-policy checks passed. Those checks do not cover the third local
commit or the current rebased candidate.

## Summary

The PR fixes a real mismatch between tensor-DMA address generation and tensor
bounds. Iterate mode changes each repeated tile's starting global address by
`iteration * global_increment`, but the old bounds predicate checked only the
tile-local coordinate. A tile could therefore move beyond the tensor while
every local coordinate still appeared valid.

The new design makes the right conceptual correction. It treats the global
increment as an affine offset in tensor storage, converts that offset into an
iteration-origin coordinate, and checks:

```text
iteration_origin[dimension] + tile_coordinate[dimension] < tensor_extent[dimension]
```

That gives one bounds rule for sub-row, row, and plane advances instead of
special-casing each movement. It also correctly gives loads and stores
different out-of-bounds effects: loads zero-fill LDS, while stores suppress
the global write.

The zero-extent correction is likewise conceptually right. For an active
tensor rank, any zero extent makes the coordinate domain empty; zero is not an
"unbounded" sentinel. Preserving completion-barrier arrival and TENSORCNT
retirement for an empty transfer is also the coherent execution contract.

The validation refinements in the final local commit improve the submitted
design. Computing the occupied lower-dimensional span accepts padded rows and
planes that the earlier `stride * extent` recurrence rejected. Skipping layout
validation for a fully masked descriptor and skipping inverse decomposition
for a non-iterating descriptor are both sensible.

Two geometric representation problems remain:

1. tensor rank is inferred from nonzero extent values, so a zero-sized axis can
   disappear and change the operation from rank 2 to rank 1; and
2. coordinate-axis order is treated as if it must also be increasing memory
   stride order, so a valid transposed/permuted layout is misclassified as
   overlapping.

These are not merely broader descriptor-feature requests. They break the two
contracts this PR specifically introduces: zero active extents and inversion
of iteration address offsets. I found two actionable correctness items.

## Actionable items

### 1. Preserve gather rank independently of tensor extent values

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h:57-95`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h:133-164`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h:183-185`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h:289-315`
- `emulation/rocjitsu/tests/cdna5_tensor_dma_test.cpp:1256-1355`

`TensorDmaDescriptor::rank()` returns gather rank 2 only when
`tensor_dims[1] != 0`. This conflates dimension count with dimension size.

Appendix A constructs a rank-2 gather descriptor with:

```text
tensor extents: {2, 0}
outer stride:   2
tile dim0:      2
gather index:   0
```

The second active axis is empty, so the whole load must zero-fill and the whole
store must be suppressed. Instead, `rank()` returns 1. The gather path then
interprets the index as a one-dimensional offset and performs both global
accesses.

The upstream AMDGPU descriptor operation represents rank by the lengths of its
size/stride lists, independently of their values, and permits non-negative
sizes including zero. Its lowering also leaves an encoded non-innermost stride
for an ordinary rank-2 descriptor. The simulator must not silently reinterpret
that descriptor as rank 1.

Determine and encode the raw descriptor's architectural rank rule explicitly.
For descriptors produced by the current lowering, preserve whether the outer
stride field was encoded before replacing zero fields with default strides,
and use that as a rank-2 hint when the second extent is zero. If a raw
zero-extent descriptor is genuinely ambiguous, reject it with a deliberate
architectural `UnimplementedInst` instead of performing lower-rank memory
accesses.

Add the second Appendix A probe permanently for both load zero-fill and store
suppression. Keep the existing `{0, nonzero}` rank-2 gather test; the two tests
cover different zero-axis positions and expose the rank/value distinction.

### 2. Invert iteration offsets in memory-stride order rather than descriptor dimension order

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h:188-210`
- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h:235-260`
- `emulation/rocjitsu/tests/cdna5_tensor_dma_test.cpp:679-780`

`validate_dense_iteration_layout()` and `dense_iteration_origin()` assume that
the descriptor's logical dimensions are already ordered by increasing memory
stride. That assumption is stronger than non-overlap and is not part of the
upstream descriptor verifier, which requires the innermost stride to be one
but permits arbitrary outer stride order.

The first Appendix A probe uses:

```text
tensor extents:   {2, 2, 2}
implicit stride0: 1
stride1:          4
stride2:          2
```

Its address map is:

```text
offset(x, y, z) = x + 4*y + 2*z
```

The eight coordinates map uniquely to offsets `0..7`. An iteration increment
of two therefore advances from origin `{0,0,0}` to `{0,0,1}`. The current
validator first incorporates stride 4 and obtains an occupied span of 6, then
sees stride 2 and throws "overlapping strides." The layout is permuted, not
overlapping.

Represent active axes as records containing at least:

```text
logical dimension
stride, including implicit stride 1 for dimension 0
extent
```

Sort those records by stride for validation and inverse decomposition. Validate
the saturated occupied span in increasing-stride order, then divide/remainder
in decreasing-stride order and write each decoded coordinate back to its
logical dimension. This retains the submitted fast mixed-radix inverse while
supporting ordinary transposed/permuted padded layouts.

If the hardware contract intentionally requires canonical logical stride
order, encode and document that actual restriction and report a
`non-canonical iterate stride order` diagnostic. Do not call a one-to-one
layout overlapping.

Add the first Appendix A regression permanently while retaining
`TensorDmaIterateRejectsOverlappingStrides`, which is a genuine aliasing case.

## Suggestions

### 1. Give rank, emptiness, validation, and inversion one internal layout abstraction

**File:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h:57-260`

The implementation currently has four loosely coupled representations of the
same geometry:

- rank inferred by `TensorDmaDescriptor::rank()`;
- active emptiness computed by `has_empty_active_extent()`;
- invertibility checked by `validate_dense_iteration_layout()`; and
- the inverse itself implemented by `dense_iteration_origin()`.

Introduce a small internal layout object built during descriptor parsing. It
should own the explicit or inferred rank, logical axes, strides, extents,
emptiness, and the validated inverse ordering. Then the copy path asks that
object for an iteration origin instead of passing `rank` separately and
reconstructing assumptions.

This would make the important invariant structural: the same axis ordering
that passed validation is necessarily the ordering used by inversion.
`validate_dense_iteration_layout()` should also be renamed because it accepts
padded layouts; `validate_iterable_layout()` or
`validate_mixed_radix_layout()` describes the real contract more accurately.

### 2. Extract a decoded-descriptor test builder while keeping one raw encoding test

**File:**

- `emulation/rocjitsu/tests/cdna5_tensor_dma_test.cpp:313-835`
- `emulation/rocjitsu/tests/cdna5_tensor_dma_test.cpp:1256-1355`

The production change is compact, but its tests repeat long sequences of raw
SGPR writes. That makes it difficult to see whether a case differs in shape,
tile, stride, iteration increment, or descriptor-group presence, and it made
the missing zero-outer-axis/permuted-axis cases less obvious.

Add a test-only builder that names:

```text
tensor extents
tile extents
global strides
global/LDS increments
iteration count
gather indices
barrier options
```

Keep at least one decoded raw-instruction test to pin the bit layout. Use the
builder for the geometry matrix so that cases read as coordinate contracts
rather than packed register arithmetic.

### 3. Avoid origin decomposition entirely for a fully masked transfer

**File:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h:320-353`

The final commit skips layout validation when an active extent is zero, but
`copy_dense_tensor()` still calls `dense_iteration_origin()` for every
iteration. The result cannot affect bounds because `fully_masked` is already
false-to-in-bounds for every element.

Use an all-zero origin when `fully_masked`, just as the code already does for a
non-iterating or repeated-origin transfer. This is a small simplification, but
it makes the empty-domain contract explicit and removes unnecessary dependence
on arbitrary stride fields.

## Commentary

### Motivation and scope

The PR is well scoped. The complete failing TensileLite workload crosses at
least three independent contracts:

1. which process/VMID translates tensor-DMA global addresses;
2. which tensor coordinates are in bounds after iterate-mode advancement; and
3. whether a descriptor count disables the transfer.

Keeping those in separate PRs makes each correction testable without claiming
that the complete tail-loop semantic mismatch is resolved. This PR should
continue to state that it advances the reproducer rather than closes it.

### Geometric model

The clean mathematical model is:

```text
tensor domain D = product over dimensions d of [0, extent[d])

address(c) = base + sum over d of c[d] * stride[d]

iteration address offset = iteration * global_increment

iteration origin =
    inverse_address(iteration address offset)

element coordinate =
    iteration origin + tile-local coordinate
```

A load writes zero when the element coordinate is outside `D`; a store emits
no global write. If any active extent is zero, `D` is empty. Atomic-barrier
arrival and wait-counter retirement describe operation completion, not the
number of copied bytes, so they still occur for an empty domain.

That is the right overall design and is substantially cleaner than
row-specific or tail-specific predicates.

The two actionable findings are exactly where the implementation departs from
that model:

- rank is topological information and cannot be derived from whether an extent
  happens to be nonzero; and
- logical axis order and storage-stride order are different coordinate-system
  choices and cannot be conflated.

Once those are represented explicitly, the submitted origin-plus-local
coordinate predicate is both elegant and accurate.

### Landing sequence

Before publication:

1. fix or explicitly reject the zero-outer-extent gather ambiguity;
2. support stride permutations in the inverse, or document the real hardware
   restriction with an accurate diagnostic;
3. rebase the three-commit stack onto current `origin/develop`;
4. rerun the focused 23-test set, both permanent counterexamples, changed-file
   pre-commit, and `git diff --check`; and
5. publish and let fresh CI validate the rebased head.

Do not expand this PR into VMID propagation, zero-count enablement, cache
visibility, or the unresolved repeated tail-issue behavior.

## Appendix A: temporary counterexamples

The following tests use the existing `Gfx1250Sim`,
`write_tensor_dma_d0()`, `write_wave_sgpr()`, `write_global_u32()`,
`read_global_u32()`, and `decode_gfx1250()` helpers in
`cdna5_tensor_dma_test.cpp`.

```cpp
TEST(Gfx1250ExecutionTest, ReviewProbeTensorDmaIterateAllowsPermutedNonOverlappingStrides) {
  Gfx1250Sim sim;
  auto *cu = sim.cu();
  auto *wf = cu->dispatch_wf(0, 0, kGfx1250ScalarSlots, 32);
  ASSERT_NE(wf, nullptr);
  wf->set_lds_base(cu->allocate_lds(256));

  constexpr uint64_t kGlobal = 0x183000;
  constexpr uint32_t kSentinel = 0xDEADDEADu;
  write_tensor_dma_d0(*cu, *wf, 0, kGlobal);
  write_wave_sgpr(*cu, *wf, 12, (2u << 16) | (1u << 19)); // i32, iterate enabled.
  write_wave_sgpr(*cu, *wf, 13, 2u << 16);                // tensor dim0.
  write_wave_sgpr(*cu, *wf, 14, 2u << 16);                // tensor dim1.
  write_wave_sgpr(*cu, *wf, 15, 1u << 16);                // tile dim0.
  write_wave_sgpr(*cu, *wf, 16, 1u | (1u << 16));         // tile dim1 and dim2.
  write_wave_sgpr(*cu, *wf, 17, 4u);                      // tensor dim1 stride.
  write_wave_sgpr(*cu, *wf, 18, 2u << 16);                // tensor dim2 stride.
  write_wave_sgpr(*cu, *wf, 19, 0);
  write_wave_sgpr(*cu, *wf, 20, 2u);       // tensor dim2.
  write_wave_sgpr(*cu, *wf, 21, 1u);       // LDS increment in elements.
  write_wave_sgpr(*cu, *wf, 22, 2u);       // advance along tensor dim2.
  write_wave_sgpr(*cu, *wf, 23, 1u << 16); // iteration_count - 1.

  for (uint32_t i = 0; i < 8; ++i)
    write_global_u32(*sim.memory, kGlobal + i * sizeof(uint32_t), 0x52000000u + i);
  cu->lds().write32(wf->lds_base(), kSentinel);
  cu->lds().write32(wf->lds_base() + sizeof(uint32_t), kSentinel);

  const std::array<uint32_t, 3> load_words = {0xd0710001u, 0x7c000000u, 0x7c140c00u};
  auto load = decode_gfx1250(load_words, "tensor_load_to_lds");
  ASSERT_NE(load, nullptr);
  ASSERT_NO_THROW(load->execute(*load, wf));

  EXPECT_EQ(cu->lds().read32(wf->lds_base()), 0x52000000u);
  EXPECT_EQ(cu->lds().read32(wf->lds_base() + sizeof(uint32_t)), 0x52000002u);
}
```

```cpp
TEST(Gfx1250ExecutionTest, ReviewProbeTensorDmaGatherRankTwoZeroOuterExtentMasksTile) {
  Gfx1250Sim sim;
  auto *cu = sim.cu();
  auto *wf = cu->dispatch_wf(0, 0, kGfx1250ScalarSlots, 32);
  ASSERT_NE(wf, nullptr);
  wf->set_lds_base(cu->allocate_lds(256));

  constexpr uint64_t kGlobal = 0x184000;
  constexpr uint32_t kTileElements = 2;
  constexpr uint32_t kGlobalSentinel = 0xAC1DAC1Du;
  constexpr uint32_t kLdsSentinel = 0xDEADDEADu;
  write_tensor_dma_d0(*cu, *wf, 0, kGlobal);
  write_wave_sgpr(*cu, *wf, 0, 1u | (1u << 31)); // gather enabled.
  write_wave_sgpr(*cu, *wf, 12, 2u << 16);       // i32 elements.
  write_wave_sgpr(*cu, *wf, 13, 2u << 16);       // tensor dim0.
  write_wave_sgpr(*cu, *wf, 14, 0);              // tensor dim1 is empty.
  write_wave_sgpr(*cu, *wf, 15, kTileElements << 16);
  write_wave_sgpr(*cu, *wf, 16, 1u); // one valid gather index.
  write_wave_sgpr(*cu, *wf, 17, kTileElements);
  write_wave_sgpr(*cu, *wf, 18, 0);
  write_wave_sgpr(*cu, *wf, 19, 0);
  write_wave_sgpr(*cu, *wf, 20, 0); // gather index.
  write_wave_sgpr(*cu, *wf, 21, 0);
  write_wave_sgpr(*cu, *wf, 22, 0);
  write_wave_sgpr(*cu, *wf, 23, 0);
  write_wave_sgpr(*cu, *wf, 24, 0);
  write_wave_sgpr(*cu, *wf, 25, 0);
  write_wave_sgpr(*cu, *wf, 26, 0);
  write_wave_sgpr(*cu, *wf, 27, 0);

  for (uint32_t i = 0; i < kTileElements; ++i) {
    write_global_u32(*sim.memory, kGlobal + i * sizeof(uint32_t), 0x53000000u + i);
    cu->lds().write32(wf->lds_base() + i * sizeof(uint32_t), kLdsSentinel);
  }

  const std::array<uint32_t, 3> load_words = {0xd0710001u, 0x7c000000u, 0x18140c00u};
  auto load = decode_gfx1250(load_words, "tensor_load_to_lds");
  ASSERT_NE(load, nullptr);
  load->execute(*load, wf);

  for (uint32_t i = 0; i < kTileElements; ++i)
    EXPECT_EQ(cu->lds().read32(wf->lds_base() + i * sizeof(uint32_t)), 0u) << "element " << i;

  for (uint32_t i = 0; i < kTileElements; ++i) {
    write_global_u32(*sim.memory, kGlobal + i * sizeof(uint32_t), kGlobalSentinel);
    cu->lds().write32(wf->lds_base() + i * sizeof(uint32_t), 0x54000000u + i);
  }

  const std::array<uint32_t, 3> store_words = {0xd0714001u, 0x7c000000u, 0x18140c00u};
  auto store = decode_gfx1250(store_words, "tensor_store_from_lds");
  ASSERT_NE(store, nullptr);
  store->execute(*store, wf);

  for (uint32_t i = 0; i < kTileElements; ++i)
    EXPECT_EQ(read_global_u32(*sim.memory, kGlobal + i * sizeof(uint32_t)), kGlobalSentinel)
        << "element " << i;
}
```
