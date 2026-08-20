> This is a review from an agent with an automatic prompt from the reviewer

**PR:** [#11051 — `fix(tensilelite): preserve initial code-object load errors`](https://github.com/ROCm/rocm-libraries/pull/11051)  
**Base:** `develop`  
**Files:** 4 changed (+119/-38)  
**Assessment:** REQUEST CHANGES  
**Risk:** 3/5 — this changes the error path that unloads all loaded modules and
rebuilds the lazy helper state.

This review describes the submitted PR head. The actionable item below was
also corrected in a separate local follow-up.

## Tests

I built the affected executable and ran the PR's focused unit test:

```bash
source $SRC_DIR/.venv/bin/activate
cmake --build $BUILD_DIR --target tensilelite-client --parallel 8

$SRC_DIR/.venv/bin/python -m pytest \
  $SRC_DIR/projects/hipblaslt/tensilelite/Tensile/Tests/unit/test_client_lazy_loading_context.py \
  -q
```

Results:

- `tensilelite-client` rebuilt and linked successfully in 2.53 seconds.
- The focused unit test completed in 0.03 seconds: 2 passed, 0 failed, 0
  skipped, and 0 errored.

The focused test is a source-order regression check. It verifies the required
ordering without a HIP module-load failure injection seam, but it cannot
execute the HIP error path itself.

## Summary

The PR records the normalized helper-HSACO directory and architecture before
the client loads its primary code objects. That lets the module-load recovery
path restore the helper module after an initial
`hipErrorLaunchFailure` or `hipErrorNoBinaryForGpu`, instead of constructing a
path with an empty architecture.

It factors normalization and recording into
`SolutionAdapter::setLazyLoadingContext()`, keeps the normal helper-load timing
after primary code objects, and adds source-order checks for the new contract.

## Actionable items

1. **`projects/hipblaslt/tensilelite/src/hip/HipSolutionAdapter.cpp:172,511`
   — do not let a failed helper-HSACO load re-enter module recovery, and retain
   the initial primary-load error if helper recovery fails.**

   The client now establishes lazy-loading context before its first primary
   load. On a primary `hipErrorNoBinaryForGpu` or `hipErrorLaunchFailure`, line
   172 calls `initializeLazyLoading()` with valid context. That function then
   loads `Kernels.so-000-<architecture>.hsaco` through the same
   `loadCodeObjectFile()` recovery entry point at line 511.

   If the helper is also incompatible or cannot launch, it returns either of
   those recoverable statuses and recursively enters the same clear-modules,
   initialize-helper, retry sequence. The recursion has no exit condition and
   can exhaust the stack. If the helper instead returns another error, such as
   `hipErrorFileNotFound`, the macro at line 172 returns the helper error and
   again hides the original primary-code-object failure.

   Add an internal non-recovering module-load path for helper HSACOs. Use it
   from `initializeLazyLoading()`, and if helper restoration fails during a
   primary-load recovery, log that failure but return the saved primary error.
   Extend the regression test to assert that helper loads use the
   non-recovering path and that recovery returns the saved error.

## Suggestions

None.

## Commentary

The early context recording is otherwise appropriately narrow: the client
still does not eagerly load helper code objects before the primary code-object
phase. A future HIP loader injection seam would make it possible to replace the
source-order tests with a behavioral regression that simulates a primary
failure followed by a helper failure, but that seam is not necessary to fix the
blocking recursion here.
