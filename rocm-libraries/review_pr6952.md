> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#6952 — Initial version of test case for streamk with mxfp4 data type](https://github.com/ROCm/rocm-libraries/pull/6952)
**Base:** develop
**Files:** 20 added (+1,682 lines), 0 modified

## Tests

**Command:**
```
cd projects/hipblaslt/tensilelite && source .venv/bin/activate
python -m pytest Tensile/Tests/common -k "sk_mxfp4_<file>" -v \
  --prebuilt-client=<build>/tensilelite/client/tensilelite-client
```

**Hardware:** gfx950 (8 GPUs available on this node).

**Results:** All 15 non-grouped tests pass. All 5 grouped gemm tests
xfail as expected. No failures.

Measured wall-clock times for individual files (run in isolation, one
at a time):

| File | Kernel combos | Wall time | CPU time |
|------|--------------|-----------|----------|
| `debug_modes` | 16 | 5s | 1m 20s |
| `groupedgemm_basic` (xfail) | 3 | 3s | 25s |
| `basic_variants` | 72 | 8s | 3m 27s |
| `activation_basic` | 18 | 31s | 23m 11s |
| `comprehensive` | 960 | 51s | 46m 42s |
| `full_coverage` | 1,440 | 90s | 88m 41s |
| `activation_full_coverage` | 720 | 129s | 129m 50s |

The framework parallelizes kernel generation across CPU cores, so wall
time is much less than CPU time. The three largest files account for
~270s wall time (~4.5 min). Extrapolating from the per-combo rate, the
full 20-file suite should take roughly **6-8 minutes** wall time when
run sequentially on this machine.

**Hang observed in aggregate run:** When running all 20 files in a
single `pytest` invocation (`-k "sk_mxfp4"`), the 20th file
(`debug_modes`) hung indefinitely after 19/20 completed. The
`tensilelite-client` process was stuck on a single benchmark for 15+
minutes before being killed. This test completes in 5s when run alone.
The cause appears to be related to running many tests sequentially in
one process — possibly GPU resource exhaustion or a state leak between
tests. This warrants investigation as it could cause CI timeouts.

All CI checks pass (gfx94X build+test, math-ci, pre-commit).

## Summary

This PR adds 20 YAML benchmark test files for StreamK + MXFP4 (F4 data
type) on gfx950, all TN transpose only. The tests exercise StreamK
modes 1/2/3 across matrix instruction variants, batch sizes, activation
types, atomic variants, tree reduction, XCC mapping, and debug modes.

Five of the 20 files test GroupedGemm + StreamK, which is documented as
unsupported. These are marked `xfail-gfx950`.

## Actionable items

1. **Massive test count — 3,824 tests total, dominated by 3 files.**
   The combinatorial explosion is severe:

   | File | Fork variants | Problem sizes | Activations | Total |
   |------|--------------|---------------|-------------|-------|
   | `sk_mxfp4_full_coverage` | 96 | 15 | 1 | **1,440** |
   | `sk_mxfp4_comprehensive` | 192 | 5 | 1 | **960** |
   | `sk_mxfp4_activation_full_coverage` | 12 | 12 | 5 | **720** |
   | All other 12 non-grouped files | — | — | — | **477** |
   | 5 grouped gemm files (xfail) | — | — | — | **227** |
   | **Total** | | | | **3,824** |

   Each test generates a kernel, compiles it, and runs it on GPU. The
   `comprehensive` file has a 7-dimension fork cross-product (3 MI × 2
   DepthU × 2 StreamK × 2 Atomic × 2 TreeReduction × 2 XCCMapping × 2
   WGM = 192 variants). Full cross-products this large should be
   justified — pairwise coverage of these 7 dimensions would be
   sufficient and would reduce 192 variants to ~20-30.

   **For context:** the largest existing streamk test file
   (`sk_bgemm_quick.yaml`) has ~1,690 tests across 3 transpose variants
   and multiple benchmark groups. This PR adds more than double that for
   a single data type on a single transpose.

2. **Fork parameter space containment — smaller files are subsets of
   the larger ones.** The fork parameters of `basic_variants`,
   `atomic_variants`, `tree_reduction`, `batch_sizes`, and
   `activation_basic` are strict subsets of `full_coverage` and/or
   `comprehensive`. This means the same kernels are generated, compiled,
   and executed multiple times across files. If both the "full coverage"
   and the individual-dimension files run in the same CI job, the
   individual files add no coverage — every test case they contain is
   already covered by the larger file.

   **Recommendation:** either keep only the "full coverage" files (which
   subsume the smaller ones), or keep only the smaller focused files and
   drop the full cross-products. Having both is pure redundancy.

3. **Grouped gemm files use `xfail` instead of `skip` — still burns CI
   time.** The 5 `groupedgemm` files (227 tests) are marked
   `xfail-gfx950`, meaning they still execute the full pipeline (kernel
   generation, compilation, GPU execution) before failing. Since
   GroupedGemm + StreamK is explicitly documented as unsupported, these
   should use `skip-gfx950` instead to avoid wasting CI resources. Or
   remove them entirely and add them when support lands.

4. **Single-value ForkParameters should be BenchmarkCommonParameters.**
   Every file lists parameters like `WavefrontSize: [64]`,
   `StaggerU: [0]`, `UseSubtileImpl: [1]`, `PrefetchGlobalRead: [2]`,
   etc. as ForkParameters despite having only one value (they produce
   no fork branching). These should be BenchmarkCommonParameters to
   clarify intent — ForkParameters should contain only the dimensions
   that actually vary.

## Suggestions

1. **Identical GlobalParameters and ProblemType across all 20 files.**
   Every file has byte-identical GlobalParameters (18 lines) and nearly
   identical ProblemType sections (only difference: `ActivationType` and
   `GroupedGemm`). Consider consolidating into fewer files with multiple
   BenchmarkProblem groups, or using YAML anchors/includes if supported.
   20 separate files with 90%+ identical boilerplate is hard to maintain
   — a typo fix in GlobalParameters requires editing all 20 files.

2. **Problem size overlap across files.** The size `[256, 256, 1, 1024]`
   appears in 12 of 15 non-grouped files; `[512, 512, 1, 1024]` appears
   in 10 of 15. Combined with the fork parameter containment (item 2
   above), this means many specific test cases (same kernel + same
   problem size) are executed identically across multiple files.

3. **No estimate of CI runtime in the PR description.** Measured locally:
   the three largest files alone take ~4.5 minutes wall time, and the
   full 20-file suite is estimated at 6-8 minutes on an 8-GPU gfx950
   node. This is manageable but should be documented — especially since
   CI nodes may have fewer GPUs/cores, which would increase wall time
   significantly (the framework parallelizes heavily). The hang observed
   during the aggregate run (see Tests section) is a separate concern
   that could cause CI timeouts.

## Commentary

The test plan (streamk × mxfp4 × gfx950 coverage) is reasonable and
addresses a real gap. The concern is entirely about scale: the current
structure generates ~3,800 tests where ~500-800 carefully chosen tests
would achieve the same coverage.

The most effective reduction would be:
- Drop the 5 grouped gemm files entirely (add when support lands).
- Keep `full_coverage` and `activation_full_coverage` as the primary
  coverage files, but reduce their fork cross-products to pairwise
  combinations instead of full Cartesian products.
- Drop the individual-dimension files (`basic_variants`,
  `atomic_variants`, `tree_reduction`, etc.) since they are subsumed
  by the full-coverage files.
- Keep `problem_sizes` (unique sizes not elsewhere) and `debug_modes`
  (tests a distinct feature) as standalone files.

This would reduce the suite from ~3,800 tests to ~500-800 while
maintaining the same parameter coverage.

## Previous review context

**Reviewer (COMMENTED):** Two comments on the initial revision:
- Asked to keep `PrintSolutionRejectionReason` commented out (default).
  **Status: addressed** — it is commented out in all files.
- Asked to remove unnecessary Subtile-related parameters
  (`UseSgprForGRO`, `ForceDisableShadowInit`, `TransposeLDS`, `LdsPad*`,
  `LDSTrInst`, `StoreRemapVectorWidth`). **Status: addressed** — these
  parameters have been removed from all files. However, other
  single-value parameters remain as ForkParameters (see actionable
  item 4).
