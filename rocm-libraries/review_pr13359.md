This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13359](https://github.com/ROCm/rocm-libraries/pull/13359)

**Reviewed head:** `6d07d222f8473f7ca5da811503d2fc5fd774193a`  
**Suggestion branch:** [review/pr13359-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr13359-suggestions), based on that exact head. The four commits were published with the reviewer's authorization; no review or PR comment was posted.

| Commit | Review item |
| --- | --- |
| [b1aee1521a1](https://github.com/newling/rocm-libraries/commit/b1aee1521a1db23be2c4af69830962ba76c8a147) | Preserve registration inputs when allocation fails |
| [caf6db5c69e](https://github.com/newling/rocm-libraries/commit/caf6db5c69e91b60860b7a3800dcba6bf9a74e1a) | Join reader threads on test failure |
| [b8fa59e9a84](https://github.com/newling/rocm-libraries/commit/b8fa59e9a84eba1ae8434aee375d97a002ac43f0) | Document the solution ownership rules |
| [8c110148ac5](https://github.com/newling/rocm-libraries/commit/8c110148ac56507d85fa998b6098014041eb675e) | Add the required shell-script license headers |

## Tests

ROCm 7.1 host build with the feature enabled: all 24 submitted LocalKernel tests passed; the suggestion branch passed those 24 plus four focused selection-cache tests. A focused probe also confirmed that mapping and remapping override an already populated shipped cache. The feature-disabled library build and symbol check passed. Allocation-failure and forced-assertion probes confirmed the findings before the fixes and the corrected behavior afterward; changed C++ formatting and shell syntax checks passed.

The [dedicated GitHub workflow](https://github.com/ROCm/rocm-libraries/actions/runs/39815181348) passed on gfx942 and gfx950 at the reviewed head. The broader checks are not all green: the [multi-architecture TensileLite job](https://github.com/ROCm/rocm-libraries/actions/runs/39815182898/job/120087229446) exceeded its 15-minute test-step limit. FFM gfx1250 and coverage checks also report failures; their causes were not established here. Unrelated Windows component tests also failed. These statuses are separate from the successful dedicated registry tests.

No local GPU kernel execution or full device-library generation was attempted. This PR changes host registration and selection; the new tests exercise those paths directly. Later registration and persistence PRs need their own payload-loading and execution validation. The allocation probe remains a standalone reproducer in the appendix, rather than replacing allocation globally inside the shared test binary.

## Summary

This PR adds an internal registry for additional kernel solution objects, which describe GPU functions and how to launch them. Registration assigns process-local indices and exposes compatible solutions to enumeration. An explicit shape mapping makes the newest compatible local solution take precedence in ordinary best/top selection; otherwise selection falls back to the shipped library.

The separation between registration and selection is useful, and the tests check meaningful boundaries: wrong types, predicate rejection, mapping order, and shipped fallback. Looking up local mappings above the shipped cache lets a later mapping affect subsequent selection queries. The exported singleton and PUBLIC compile definition also address sharing across libraries and consistent class layout.

The default-off feature flag and direct host tests are appropriate for this slice. No omitted-test waiver is needed for its core behavior. Adjacent cache tests were selected because the changed master delegates fallback and remaining top candidates to that cache. The bounded fixes below preserve the implementation's design.

## Actionable items

### Preserve registration inputs when allocation fails

**Location at reviewed head:** `projects/hipblaslt/tensilelite/include/Tensile/LocalKernelLibrary.hpp:308`.

`addSolutions()` increments `m_nextIndex` and changes each caller-owned solution before inserting it into the new map. Map insertion can throw `std::bad_alloc`. The unpublished map is discarded, but the input objects retain local indices. A retry then rejects them as already indexed even though index lookup cannot find them. In a two-solution probe, failure at either map-node allocation reproduced this state.

Prepare all map entries and the returned index vector before changing the objects or advancing the counter. Only then assign indices/tags and publish. Commit [b1aee1521a1](https://github.com/newling/rocm-libraries/commit/b1aee1521a1db23be2c4af69830962ba76c8a147) makes this small ordering change. The appendix probe fails on the submitted header and passes with the fix, including retry at the original indices.

### Document the solution ownership rules

**Location at reviewed head:** `projects/hipblaslt/tensilelite/include/Tensile/LocalKernelLibrary.hpp:275`.

The snapshot contains shared pointers to mutable solution objects. Neither copying the snapshot nor the registry mutex protects later writes through the caller's pointer or a lookup result. Changing a problem type can invalidate its stored mapping key; changing metadata or predicates during a query can race with readers.

State that callers must finish initialization and have exclusive access to incoming objects during registration, then leave index, tag, problem type, launch metadata, and predicates unchanged. This is a documentation request; it does not require changing pointer types or ownership architecture. Commit [b8fa59e9a84](https://github.com/newling/rocm-libraries/commit/b8fa59e9a84eba1ae8434aee375d97a002ac43f0) documents the existing requirement.

## Suggestions

### Join reader threads on test failure

**Location at reviewed head:** `projects/hipblaslt/clients/tests/src/local_kernel_library_gtest.cpp:537`.

The writer uses `ASSERT_TRUE` while four reader threads are running. A failed assertion returns before setting `done` or joining them. Destruction of a joinable `std::thread` terminates the binary. Passing an unregistered index on the first iteration reproduced SIGABRT and `terminate called without an active exception`.

Use scope-based cleanup to stop and join readers on every exit, and check the final lookup before dereferencing it. Commit [caf6db5c69e](https://github.com/newling/rocm-libraries/commit/caf6db5c69e91b60860b7a3800dcba6bf9a74e1a) does both. With the same injected failure, the fixed test reports a normal failed-test result and completes the test run. The normal concurrency test still passes.

### Add the required shell-script license headers

**Locations at reviewed head:** line 1 of `projects/hipblaslt/scripts/local-kernels/{common,configure-build,fetch-sdk,install-deps,run-tests,stage-hipblas-common}.sh`.

All six new scripts lack the short copyright and SPDX headers required by `projects/hipblaslt/AGENTS.md`, under “License headers.” Add them immediately after each shebang. Commit [8c110148ac5](https://github.com/newling/rocm-libraries/commit/8c110148ac56507d85fa998b6098014041eb675e) contains only those headers; all six scripts pass `bash -n`.

## Commentary

**Possible follow-up work; none of this is a change request for this PR.**

The runtime-tuning stack and this registry provide different capabilities: tuning measures and chooses among available kernels, while registration expands the available set. Their problem-to-solution preference records overlap. A follow-up could retain this registry while sharing one decision lookup and persistence format between measured winners and externally supplied mappings. It would need to define matching scope and precedence, and represent registered solutions with stable payload references because these integer indices last only for one process.

That follow-up should distinguish changing a selection from replacing loaded code. Existing algorithm objects can continue referring to an earlier solution; changing a mapping affects fresh queries. A customer-facing lifecycle description should say when code is loaded, whether replacement is supported, and how application caches interact with new choices. Useful integration cases are selecting before mapping, tuning after registration, and restoring saved decisions after registration order changes.

## Appendix: focused reproducers

### Allocation failure

Save the following as `registration_failure.cpp`. It instantiates the real registration helper with minimal solution objects; no device execution is needed. `allocationsUntilFailure` is enabled only around registration. The loop checks that every allocation exception leaves both objects untouched and permits retry without consuming indices.

```cpp
#include <Tensile/LocalKernelLibrary.hpp>
#include <cstdlib>
#include <iostream>
#include <new>

static int allocationsUntilFailure = -1;
void* operator new(std::size_t size)
{
    if(allocationsUntilFailure == 0)
        throw std::bad_alloc();
    if(allocationsUntilFailure > 0)
        --allocationsUntilFailure;
    if(void* p = std::malloc(size ? size : 1))
        return p;
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }

struct Solution
{
    enum class MatchingTag { Others, Equal };
    int index = -1;
    MatchingTag tag = MatchingTag::Others;
};
struct Problem { using Solution = ::Solution; };

int main()
{
    int failures = 0;
    for(int failAt = 0; failAt < 16; ++failAt)
    {
        TensileLite::LocalKernelLibrary<Problem> library;
        auto a = std::make_shared<Solution>();
        auto b = std::make_shared<Solution>();
        const std::vector<std::shared_ptr<Solution>> incoming{a, b};
        allocationsUntilFailure = failAt;
        bool threw = false;
        try { library.addSolutions(incoming); }
        catch(std::bad_alloc const&) { threw = true; }
        allocationsUntilFailure = -1;
        if(!threw) continue;
        bool unchanged = a->index == -1 && b->index == -1
            && a->tag == Solution::MatchingTag::Others
            && b->tag == Solution::MatchingTag::Others
            && library.registeredCount() == 0;
        auto retried = library.addSolutions(incoming);
        bool retryWorked = retried == std::vector<int>{TensileLite::LocalKernelIndexBase,
                                                       TensileLite::LocalKernelIndexBase + 1};
        if(!unchanged || !retryWorked)
        {
            ++failures;
            std::cout << "failure at allocation " << failAt
                      << ": inputs unchanged=" << unchanged
                      << ", retry works=" << retryWorked << '\n';
        }
    }
    return failures ? 1 : 0;
}
```

Compile and run against the submitted header, then the fixed header:

```bash
"$ROCM_PATH/bin/amdclang++" -std=c++20 -x hip --offload-host-only \
  -D__HIP_PLATFORM_AMD__ -DROCM_USE_FLOAT16 -D__HIP_HCC_COMPAT_MODE__=1 \
  -I"$SRC_DIR/projects/hipblaslt/tensilelite/include" \
  -I"$SRC_DIR/projects/hipblaslt/tensilelite/rocisa" \
  -I"$BUILD_DIR/tensilelite/include" -I"$ROCM_PATH/include" \
  registration_failure.cpp -o registration_failure
./registration_failure
```

The submitted implementation reports `inputs unchanged=0, retry works=0` at allocations 5 and 6 and exits 1. The fixed implementation exits 0.

### Concurrency-test failure

The helper functions already exist in the PR's `local_kernel_library_gtest.cpp`. In a temporary copy of that file, replace the writer loop in `smoke_ConcurrentReadersAndWriter` with this exact loop, leaving the rest of the submitted test unchanged:

```cpp
for(int i = 0; i < 200; i++)
{
    int index = library.addSolutions({makeSolution(problem)}).at(0);
    ASSERT_TRUE(library.setExactMatch(localExactShapeFor(problem), i == 0 ? index + 1 : index));
}
```

Build the temporary source using the same include paths and definitions as its normal test object, linking `tensilelite-host`, `gtest_main`, `gtest`, and threads. Run with `--gtest_filter=LocalKernelLibrary.smoke_ConcurrentReadersAndWriter`. The first index plus one is unregistered, so the assertion fails deterministically. The submitted cleanup aborts the process; the cleanup in [caf6db5c69e](https://github.com/newling/rocm-libraries/commit/caf6db5c69e91b60860b7a3800dcba6bf9a74e1a) joins readers and returns the ordinary failed-test exit code 1. This injected failure is not part of the suggestion branch.
