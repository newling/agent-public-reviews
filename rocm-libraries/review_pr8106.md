> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#8106 — [tensilelite] Add fast path reference gemm for MXFP4](https://github.com/ROCm/rocm-libraries/pull/8106)
**Author:** Alex-Vasile
**Base:** develop
**Files:** 4 changed (+825/−115)

## Tests

Built locally with ninja (out-of-tree). The build config has
`TENSILELITE_BUILD_TESTING=OFF`, so `ctest` finds no tests. I ran the
`cpu-gemm-driver` directly with the same arguments from the new
CMakeLists.txt entries.

**Positive tests — all 27 PASS (max diff: 0 on every one):**

| Category | Tests |
|----------|-------|
| Fast path, all transpose combos (NN/TN/NT/TT), MX32 | 4 |
| Slow path, all transpose combos, MX32 | 4 |
| Fast path, K=192, all transpose combos, MX32 | 4 |
| Fast + slow, no MX (mxBlock=0) | 2 |
| Fast path, epilogue features (bias, relu, scaleAlphaVec, allFeatures, beta, scaleAB scalar/vector) | 7 |
| Fast path, mxBlock=16 | 1 |
| Batched (batchCount=2), fast + slow, NN + TT | 4 |
| Asymmetric MX (A32/B64, A64/B32), fast only | 2 |
| Edge cases (K=mxBlock, M=1, N=1, alpha=0, odd dims) | 5 |

**Negative tests — all 7 correctly exit with code 1:**

| Test | Error message |
|------|---------------|
| Slow path asymmetric MX | "asymmetric MX ... only supported on the fast path" |
| --mxBlock + --mxBlockA conflict | "--mxBlock cannot be combined with --mxBlockA or --mxBlockB" |
| One-sided MX | "--mxBlockA and --mxBlockB must both be > 0" |
| K not aligned to mxBlock | "K (33) must be a multiple of mxBlockA (32)" |
| K < mxBlock | "K (16) must be >= mxBlockA (32)" |
| Non-power-of-2 mxBlock | "mxBlockA (6) must be a power of 2" |
| mxBlock with f32 type | "mxBlock ... only supported for type f4" |

**Regression check:** f32, f16, bf16 tests (various transpose combos, fast/slow) all still pass.

**CI status:** An initial run failed across all platforms (appears to be
a pre-push revision). The second CI run (triggered on the current
commit) has all hipblaslt shards passing; only unrelated rocblas shards
still pending.

## Summary

This PR adds MXFP4 (FP4 data with MX block-scaling) support to the CPU
reference GEMM used for validation. Two paths are extended:

1. **Slow path** (`columnMajorGemm` in `cpu_gemm_driver.cpp`): the
   inner K-reduction is restructured into block-sized segments, each
   multiplied by the product of the corresponding per-block MX scale
   factors from A and B. Supports symmetric MX only (mxBlockA ==
   mxBlockB).

2. **Fast path** (`SolveCPU` in `Reference.cpp`): the tiled reference
   implementation gains per-tile MX scale lookup, accumulating into a
   partial buffer per BLOCK_K tile, then scaling by (sa * sb) before
   folding into the output. Supports both symmetric and asymmetric MX
   (mxBlockA != mxBlockB), provided each is a multiple of BLOCK_K=8.

The PR also:
- Adds `Float4` to `ShadowBuffer` (FP4→f32 unpacking via
  `__amd_cvt_fp4x2_to_floatx2_scale`).
- Removes the blanket `rejectFast("MX_block")` gate in
  `isFastPathEligible` and replaces it with fine-grained alignment /
  divisibility checks.
- Adds ~50 new CTest entries covering all transpose combos, epilogue
  features, batched, asymmetric MX, edge sizes, and negative cases.
- Adds `--mxBlock`, `--mxBlockA`, `--mxBlockB`, `--batchCount` CLI
  flags to `cpu-gemm-driver`.
- Fixes `DataInit_test.cpp` to use the renamed `isMXProblemExceptF6`.

The second commit fixes a build break caused by the
`isMXProblem`→`isMXProblemExceptF6` rename (presumably from PR #8006).

## Actionable items

### 1. Unreachable `mxBlock < 0` check

**File:** `cpu_gemm_driver.cpp`, line 956

The check `if(mxBlock < 0)` is dead code. By line 956, `mxBlock` has
already been consumed: if it was `> 0`, it was copied into
`mxBlockA`/`mxBlockB` at line 938; if it was `0`, it was left alone. But
there's no path where `mxBlock < 0` reaches this point without having
been caught earlier — `mxBlock` is an `int` parsed from CLI so it *can*
be negative, but the check at line 956 is ordered after the `if(mxBlock
> 0)` block, meaning a negative `mxBlock` silently passes through the
expansion block and lands here. This ordering makes the check
*reachable* but confusingly late. Move it before the expansion block
(before line 930) so the intent is clear and the negative value is
caught before any logic runs.

### 2. Help strings contradict the conflict check

**File:** `cpu_gemm_driver.cpp`, lines 849–851 vs 930–935

The help strings for `--mxBlockA` and `--mxBlockB` say "overrides
--mxBlock for A/B", implying they can be combined with `--mxBlock` (e.g.
`--mxBlock 32 --mxBlockA 16` to mean "both 32 but override A to 16").
But the code rejects that combination outright:

```cpp
if(mxBlock > 0 && (mxBlockA > 0 || mxBlockB > 0))
    // Error: --mxBlock cannot be combined with --mxBlockA or --mxBlockB
```

Either implement override semantics (apply `--mxBlock` first, then let
per-side flags override) or change the help strings to say the flags are
mutually exclusive with `--mxBlock`.

### 3. Duplicate one-sided MX validation

**File:** `cpu_gemm_driver.cpp`, lines 362–368 and 946–954

The one-sided MX rejection is checked twice: once in `main()` (line 948)
and again inside the templated `runGemm()` (line 363). Both reject the
same condition. The `main()` check is sufficient (and runs first); the
`runGemm()` check is redundant. If the intent is defense-in-depth,
consider replacing the `runGemm()` copy with an `assert` to signal it's
a precondition rather than user-facing validation.

### 4. `batchCount < 1` on an unsigned type

**File:** `cpu_gemm_driver.cpp`, line 335

`batchCount` is `size_t` (unsigned), so `batchCount < 1` is equivalent
to `batchCount == 0`. The `< 1` phrasing suggests the author may have
been guarding against negative values, but `size_t` can't be negative.
Change to `== 0` for clarity, or change the parameter type to a signed
integer if negative values are a realistic concern from the CLI layer.

### 5. `#ifndef _WIN32` inside function parameter list

**File:** `cpu_gemm_driver.cpp`, lines 194–201

Putting `#ifndef _WIN32` around trailing parameters in a function
signature (with the comma outside the guard) is fragile and hard to
read. If the Windows build is not a current target for this file,
consider a single `#ifndef _WIN32` around the entire function or file
instead of threading the preprocessor through parameter lists. If
Windows support *is* needed, the current approach compiles but will
produce hard-to-debug linker mismatches if a caller forgets the same
guards.

## Suggestions

### 1. Consider a smaller tolerance or exact match assertion

The tolerance for FP4 is set to 0.5 (`cpu_gemm_driver.cpp`, line 788).
In practice, every test I ran reports `max diff: 0`. If exact match is
the expected behavior (since both paths use the same E2M1 value set and
float32 accumulation), consider tightening to an exact check and only
relaxing if a real case demands it. A tolerance of 0.5 could mask a
one-bit MX scale error.

### 2. Factor the FP4 init loop to avoid duplicating the padding logic

`cpu_gemm_driver.cpp`, lines 504–516: the FP4 init for A and B is
nearly identical (same `randomFp4` + `Float4x2(v0, v1)` pattern, same
odd-element padding). A small helper lambda taking the storage vector
and element count would remove the duplication.

### 3. Add `--mxBlock` / `--batchCount` to the help string header

`cpu_gemm_driver.cpp`, line 833: the `--type` help string was updated to
mention `f4`, but the program's one-line description / usage summary (if
any) doesn't mention MX or batching. If this tool is used by others
besides the author, a brief note in the top-level help would aid
discoverability.

## Commentary

The PR is well-structured: slow-path reference is minimal and easy to
audit, the fast-path extension mirrors the existing tiled structure, and
the test matrix is thorough (transpose × path × features × edge cases ×
negative). The asymmetric-MX design (step by min(mxBlockA, mxBlockB) in
the slow path, per-tile scale lookup in the fast path) is clean and the
decision to reject asymmetric on the slow path rather than implementing
a subtly-wrong version is sound.

The PR depends on #8006 (still open), which presumably contains the
`isMXProblem` → `isMXProblemExceptF6` rename. The second commit in this
PR patches the build break from that rename. This dependency should be
called out clearly (it is mentioned in the PR description).

The `strToDataType` lambda picks up two unrelated type strings (`f64`,
`tf32`) — presumably forward-looking additions. `tf32` maps to
`DataType::Float`, which is technically correct (TF32 is a truncation of
float32) but could surprise a reader expecting a distinct type.
