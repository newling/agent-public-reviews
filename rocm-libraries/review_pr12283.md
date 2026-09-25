This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12283](https://github.com/ROCm/rocm-libraries/pull/12283)

**Reviewed head:** `67c9d0868388b305250f3982a7bf97f8cbed9344`.
**Review mode:** Follow-up to [the reviewer's comments](https://github.com/ROCm/rocm-libraries/pull/12283#pullrequestreview-5322347481), adding test evidence and the performance tradeoff of the proposed shared selection check.
**Suggestion branch:** [`review/pr12283-followup-suggestions`](https://github.com/newling/rocm-libraries/tree/review/pr12283-followup-suggestions), based on that exact head.
**Commit mapping:** [`8056c8e7ac03c73cbbdaf9f8f3bf4d3ac683fab0`](https://github.com/newling/rocm-libraries/commit/8056c8e7ac03c73cbbdaf9f8f3bf4d3ac683fab0) implements actionable item 1. The test fix and the two implementation prototypes linked by the reviewer are published on separate branches.

## Tests

The submitted guard and predicate passed focused C++ and Python tests during the original review; their implementation and tests are unchanged at this head. The current suggestion branch rebuilt the TensileLite host library in the MessagePack configuration and passed the focused `LaunchDimGuard` and `Predicates` suites. Mutation testing during the original review demonstrated the precision-test gap below and verified the corrected fixture.

Separately, the [shared-grid prototype](https://github.com/newling/rocm-libraries/commit/51781da6271eb447ab800113f680ddf7369e69cf) built hipBLASLt, TensileLite host/client-common and the C++ test executable; focused launch-limit, custom-kernel, Stream-K and selection tests, affected Python checks, formatting checks and launch-limit UBSan tests passed. Those results validate the prototype, which is based on develop, rather than the submitted PR. No GPU dispatch was tested locally, and the installed HIP headers do not exercise cluster launch support.

At this follow-up, [CI](https://github.com/ROCm/rocm-libraries/pull/12283/checks) is mixed: TensileLite unit and precheckin jobs pass, while hipBLASLt gfx94X shard 2/6, gfx90a ASAN, gfx1250 hardware, rocjitsu race, hipBLASLt coverage and TensileLite C++ project coverage checks report failures. These current failures were not diagnosed in this focused follow-up and remain untriaged here.

## Summary

The PR addresses two different needs: refusing an unrepresentable HIP launch, and filtering candidates early enough for selection to consider another solution. The launch guard checks the actual dimensions and correctly distinguishes ordinary work-item counts from cluster workgroup counts. Keeping that final check is useful whichever selection policy is chosen.

The new Stream-K predicate cheaply bounds a possible one-workgroup-per-output-tile fallback. Its integer arithmetic and accumulation of all free and batch indices are useful choices. The reviewer's shared-grid alternative makes selection more faithful to dispatch, with additional CPU work discussed below.

## Actionable items

### 1. Make the precision test cross the rejection boundary

**Location:** [`projects/hipblaslt/tensilelite/tests/Predicates_test.cpp:382–405`](https://github.com/ROCm/rocm-libraries/blob/67c9d0868388b305250f3982a7bf97f8cbed9344/projects/hipblaslt/tensilelite/tests/Predicates_test.cpp#L382).

`StreamKWorkgroupNumberCheck_NonRepresentableDimension_Rejected` uses `M=16,777,217`, `N=256`, and a `16×16` macro tile. Integer arithmetic produces 16,777,232 tiles; float rounding produces 16,777,216. Both exceed the maximum of 16,777,215, so both implementations reject the problem. The comment's claim that rounding would cause acceptance is incorrect. Replacing `ceilDiv()` with `return std::ceil(static_cast<float>(numerator) / denominator);` leaves all nine submitted Stream-K predicate tests green.

Use `M=268,435,441`, `N=16`, with the same macro tile. Exact division gives 16,777,216 tiles, which must be rejected. Float rounds M down to 268,435,440 and gives 16,777,215 tiles, which the broken implementation accepts. Commit **`8056c8e7ac0`** updates the fixture and its explanation, with compile-time checks that it straddles the boundary. The corrected test fails under the float mutation with `Actual: true; Expected: false` and passes with the submitted integer implementation.

## Suggestions

### Describe the current tree-fixup fallback accurately

**Location:** PR description, Technical Details; compare [`projects/hipblaslt/tensilelite/src/ContractionSolution.cpp:6801–6826`](https://github.com/ROCm/rocm-libraries/blob/67c9d0868388b305250f3982a7bf97f8cbed9344/projects/hipblaslt/tensilelite/src/ContractionSolution.cpp#L6801).

The description says tree-fixup falls back to `skGrid=tiles` at the iteration threshold. The current code uses a thread-count-dependent tile limit and chooses `cuCount * occupancy` when `tiles >= maxTiles`. Update that explanation. The separate [insufficient-workspace fallback](https://github.com/ROCm/rocm-libraries/blob/67c9d0868388b305250f3982a7bf97f8cbed9344/projects/hipblaslt/tensilelite/src/ContractionSolution.cpp#L5981) still sets `sk.grid=tiles`, so the oversized-grid concern remains real.

## Commentary

The tradeoff behind the reviewer's second proposal is precision versus selection cost. The PR's [new predicate](https://github.com/ROCm/rocm-libraries/blob/67c9d0868388b305250f3982a7bf97f8cbed9344/projects/hipblaslt/tensilelite/include/Tensile/ContractionProblemPredicates.hpp#L1640) checks the tile fallback unconditionally and assumes 256 threads per workgroup. It can exclude a candidate whose resolved Stream-K grid would fit, while larger workgroups can still need rejection by the final guard. The shared-grid prototype instead uses the solution's actual workgroup size and resolved launch dimensions, including workspace fallback. Sharing that calculation reduces the chance of selection and dispatch drifting apart. It also requires regenerating solution metadata to attach `LaunchLimits` to Stream-K candidates.

The current prototype repeats Stream-K resolution already performed by `requiredWorkspaceSize()`. Candidate validation already scales with the number of candidates examined; this adds work per candidate reaching the check. It does not change selection from constant time to linear time.

A small release-build CPU microbenchmark measured the new check at roughly **0.04–0.12 µs per candidate** across the sampled modes. For an `8192×8192×8192` GEMM with Stream-K mode 3 and the default grid model, the existing workspace query took **0.096 µs** and the new check **0.107 µs**, measured separately. Adding those suggests roughly **2.1× the workspace-query cost** when both run. **The percentage overhead on total selection time is unknown:** neither the full selection baseline nor a PR-versus-prototype end-to-end comparison was measured. At approximately 0.1 µs per added check, 1,000 evaluated candidates would add approximately 100 µs; that is an extrapolation.

These measurements used a Ryzen Threadripper PRO 9995WX, a synthetic gfx950 description with 256 CUs, 256-thread workgroups, `128×128` macro tiles, depth 64 and 32 MiB workspace. Each result was the median of five batches of 2,000 calls after warmup, repeatedly checking the same candidate. Real candidate traversal and cache behavior can differ; this measures CPU checking cost, not GPU execution performance.

The shared calculation is attractive for consistency and for retaining usable candidates, but its extra selection cost should be measured through the heuristic API before choosing it on performance grounds. Resolving Stream-K settings once for both workspace and grid checks could avoid the duplicate work; that optimization is not implemented in the prototype.

The published handoff is `review/pr12283-followup-suggestions`, with **`8056c8e7ac0`** for the precision test; focused checks pass and the commit is whitespace-clean. The review adds no further production changes to the two published alternatives. GPU validation, CI failure diagnosis and end-to-end selection benchmarking remain outside this follow-up.
