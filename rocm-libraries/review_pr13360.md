This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13360](https://github.com/ROCm/rocm-libraries/pull/13360)

**Reviewed head:** `cf8f6b7275ef4c23937e16b4b0212d2d35af09bb`

**Review date:** 2026-10-26

**Suggestion branch:** [review/pr13360-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr13360-suggestions), based on the reviewed head.

| Commit | Review item |
| --- | --- |
| [7417d28ea77](https://github.com/newling/rocm-libraries/commit/7417d28ea777c25e8ab6062383a99af422285fb9) | Return an empty name when hardware rejects a local index; includes a regression test |
| [dcab9ec7014](https://github.com/newling/rocm-libraries/commit/dcab9ec70143808a452d83d112b65108261fead4) | Release a local module if bookkeeping allocation fails |
| [da65b6747e3](https://github.com/newling/rocm-libraries/commit/da65b6747e37e80fba18e5e4a58bfd09e1ec8850) | Join the launch thread when a test assertion returns early |
| [c21d0134fe1](https://github.com/newling/rocm-libraries/commit/c21d0134fe16ea363d30cb1f33ed134f703493aa) | Clarify optional registration outputs and the index-range check |
| [76898439be9](https://github.com/newling/rocm-libraries/commit/76898439be932d9158a3e8407569b1fbcdebc8ed) | Document tuning-file precedence over exact local mappings |

These commits were published on 2026-10-26 and are suitable for individual inspection or cherry-picking. The PR head branch is preserved. No checks or workflow runs were triggered on the fork at the publication snapshot.

## Tests

The submitted and suggestion branches build with local kernels enabled; focused registry, master and adapter tests pass on both, and the suggestion branch also passes the new metadata regression and host cache tests. Allocation and assertion-failure probes confirm the fixes; focused ASan/UBSan probes, root and component pre-commit, changed-range clang-format 18.1.4 and whitespace checks pass.

Local builds used ROCm 7.1, its HIP compiler and Flang, and current hipblas-common headers. The submitted branch passed 39 focused tests; the suggestion branch passed 51 after adding the regression and host cache cases. The allocation probe uses the real adapter with an injected module API; the metadata probe registers a synthetic solution in the real shared registry and calls the public name functions. Neither probe requires launching a GPU kernel. Pre-push ASan/UBSan checks instrument the actual adapter translation unit and allocation probe, plus the reduced assertion-cleanup probe; supporting shared runtime objects were not rebuilt with sanitizers.

One additional, exploratory test, `CachingLibraryCollision.smoke_Bf16BiasHeuristicIsNotServedF16BiasSolutions`, crashed when pointed at the installed ROCm 7.1 device library. To reproduce that local configuration, run:

```sh
HIPBLASLT_TENSILE_LIBPATH="$DEVICE_LIBRARY_DIR" TENSILE_DB=0x1000 \
  "$BUILD_DIR/clients/hipblaslt-test" \
  --gtest_filter=CachingLibraryCollision.smoke_Bf16BiasHeuristicIsNotServedF16BiasSolutions
```

The parser reports mismatched metadata fields, including `computeInputType` and `CustomKernelName`. Deserialization returns no library, and `PlaceholderLibrary::loadPlaceholderLibrary` dereferences it. The parser and placeholder loader are unchanged by this PR. This run does not establish a regression in the PR and provides no successful GPU numerical evidence. A metadata-only fixture was also insufficient for this shipped-kernel test; the successful host cache cases do not depend on shipped payloads.

At the reviewed head, the dedicated [local-kernel workflow](https://github.com/ROCm/rocm-libraries/actions/runs/40373817445) passed on gfx942 and gfx950. Its current run contains the two single-GPU jobs, so the optional two-GPU lane has no result in that run. At the review snapshot, broader checks remained pending, and [TensileLite C++ project coverage](https://app.codecov.io/gh/ROCm/rocm-libraries/pull/13360) reports 48.93% against an 80% target. I could not establish a comparable base result for that coverage check.

I did not generate a fresh device library, run the full GPU registration suite locally, or repeat a feature-disabled build. The dedicated workflow supplies the GPU registration/launch evidence; the local build and probes cover the host behavior discussed below.

## Summary

The PR lets an application add compiled GPU functions to hipBLASLt without rebuilding its shipped kernel library. A payload consists of a solution-metadata shard and a code object containing GPU code. Registration assigns process-local algorithm indices, while a separate exact-shape mapping changes which suitable kernel the normal selection path prefers.

The implementation fully parses a shard before publishing its solutions, restricts them to their registered processor, and loads local code objects separately from shipped modules. Keeping local modules and function caches keyed by path preserves the identity of kernels whose names collide. The default-off build option limits exposure, and the tests check rejection, selection ordering, name collisions and concurrent registration with launches.

Functional registration and launches need GPU tests, while processor filtering, index lookup and loader bookkeeping fit focused host tests; the PR supplies both levels. Tests and the safe-default flag are present, so no waiver for omitted tests or flags is needed. Cache lookup is a direct downstream consumer of master selection, which motivated the focused host cache checks. The review findings concern boundaries within this registration concept.

## Actionable items

### Return an empty name when hardware rejects a local index

**Locations:** [`MasterSolutionLibrary.hpp:415–421`](https://github.com/ROCm/rocm-libraries/blob/cf8f6b7275ef4c23937e16b4b0212d2d35af09bb/projects/hipblaslt/tensilelite/include/Tensile/MasterSolutionLibrary.hpp#L415), [`tensile_host.cpp:8091–8092`](https://github.com/ROCm/rocm-libraries/blob/cf8f6b7275ef4c23937e16b4b0212d2d35af09bb/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L8091), and [`tensile_host.cpp:8118–8119`](https://github.com/ROCm/rocm-libraries/blob/cf8f6b7275ef4c23937e16b4b0212d2d35af09bb/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L8118).

The new hardware-aware lookup returns null for a registered local index whose processor differs from the handle's device. Both algorithm-name helpers immediately dereference that result. An algorithm retained from a registration on another architecture therefore crashes `hipblaslt_ext::getKernelNameFromAlgo` or `getSolutionNameFromAlgo`, even though the local API promises to treat that index as unknown on this device.

I registered a synthetic foreign-processor solution in the actual shared local registry, then queried its names through a valid native handle. Each public function independently terminated with SIGSEGV on the submitted libraries. Both return an empty string with [7417d28ea77](https://github.com/newling/rocm-libraries/commit/7417d28ea777c25e8ab6062383a99af422285fb9).

Check the lookup result before accessing either name. Commit [7417d28ea77](https://github.com/newling/rocm-libraries/commit/7417d28ea777c25e8ab6062383a99af422285fb9) implements this and adds `LocalKernelRegister.ForeignProcessorMetadata`. Its child process isolates the registration, and synthetic metadata exercises the processor boundary without needing a mixed-architecture GPU node.

### Release a local module if bookkeeping allocation fails

**Location:** [`HipSolutionAdapter.cpp:466–489`](https://github.com/ROCm/rocm-libraries/blob/cf8f6b7275ef4c23937e16b4b0212d2d35af09bb/projects/hipblaslt/tensilelite/src/hip/HipSolutionAdapter.cpp#L466).

After `hipModuleLoad` succeeds, the module is held only by a raw local variable until `m_localModules.emplace` finishes. If allocating the map entry, its path string or hash buckets throws, the module never enters the map that the adapter destructor unloads. The C API catches the exception, but the loaded GPU resource is lost.

The allocation probe in Appendix A arms a failure immediately after the module API reports success. On the submitted adapter, the first three allocation boundaries each leave one load and zero unloads. With [dcab9ec7014](https://github.com/newling/rocm-libraries/commit/dcab9ec70143808a452d83d112b65108261fead4), every tested boundary finishes with matching load and unload counts.

Keep a scope-owned module until the map accepts ownership. Commit [dcab9ec7014](https://github.com/newling/rocm-libraries/commit/dcab9ec70143808a452d83d112b65108261fead4) uses a nonallocating owner with the adapter's unload function, then releases it after insertion. A later diagnostic-name allocation failure leaves the module tracked, which is consistent with keeping loaded paths cached after failed registration. The global allocation override remains in the standalone probe rather than the shared test binary.

### Join the launch thread when a test assertion returns early

**Location:** [`local_kernel_register_test.cpp:496–526`](https://github.com/ROCm/rocm-libraries/blob/cf8f6b7275ef4c23937e16b4b0212d2d35af09bb/projects/hipblaslt/clients/tests/src/local_kernel_register_test.cpp#L496).

`DISABLED_RegisterWhileLaunchingWorker` starts a thread, then uses `ASSERT_GE(r.index, 0)` before its explicit join. If registration fails, that assertion returns from the test while the thread remains joinable. Destroying the thread calls `std::terminate` and aborts the worker.

Appendix B preserves the same loop, failure check, assertion and join ordering. A failed registration index produces SIGABRT on the submitted control flow; the scope-owned cleanup reports an ordinary GoogleTest failure with exit status 1.

Commit [da65b6747e3](https://github.com/newling/rocm-libraries/commit/da65b6747e37e80fba18e5e4a58bfd09e1ec8850) adds a scope object that signals completion and joins on every exit. It follows the cleanup pattern already used by the local-library reader test. The reduced probe validates the failure path without forcing an unrelated GPU registration failure.

## Suggestions

### Clarify optional registration outputs and the index-range check

**Locations:** [`hipblaslt-local-kernel.h:61–67`](https://github.com/ROCm/rocm-libraries/blob/cf8f6b7275ef4c23937e16b4b0212d2d35af09bb/projects/hipblaslt/library/include/hipblaslt/hipblaslt-local-kernel.h#L61) and [`hipblaslt-local-kernel.h:130–135`](https://github.com/ROCm/rocm-libraries/blob/cf8f6b7275ef4c23937e16b4b0212d2d35af09bb/projects/hipblaslt/library/include/hipblaslt/hipblaslt-local-kernel.h#L130).

The registration wrapper accepts null output pointers and writes no indices for a nonpositive capacity, but the header does not explain those choices. A call with no output buffer still registers solutions; it is not a count-only query. Also, `hipblasLtMatmulAlgoIsLocalKernel` checks the reserved index range rather than whether an index is registered or usable on this device, despite its current documentation.

Commit [c21d0134fe1](https://github.com/newling/rocm-libraries/commit/c21d0134fe16ea363d30cb1f33ed134f703493aa) documents the implemented behavior without changing it. This gives callers enough information to distinguish range classification from registration and support checks.

### Document tuning-file precedence over exact local mappings

**Location:** [`hipblaslt-local-kernel.h:89–95`](https://github.com/ROCm/rocm-libraries/blob/cf8f6b7275ef4c23937e16b4b0212d2d35af09bb/projects/hipblaslt/library/include/hipblaslt/hipblaslt-local-kernel.h#L89).

The header says the mapped kernel comes first, but [`rocblaslt_auxiliary.cpp:2852–2865`](https://github.com/ROCm/rocm-libraries/blob/cf8f6b7275ef4c23937e16b4b0212d2d35af09bb/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/rocblaslt_auxiliary.cpp#L2852) installs a usable tuning-file override before asking the master for its choices. For a single-result request, an override can consume the entire request. A mapping can therefore succeed without changing the returned algorithm.

Commit [76898439be9](https://github.com/newling/rocm-libraries/commit/76898439be932d9158a3e8407569b1fbcdebc8ed) documents that precedence and the existing priority of an explicitly supplied algorithm. This is a documentation change; changing preference policy requires a separate decision. The precedence observation is source-based.

## Commentary

The documentation of path lifetime and load-once behavior is useful: retaining a registered algorithm keeps it tied to its original code object. The tests also use an empty replacement kernel to distinguish module identity from numerical agreement, so a name collision cannot pass by running the shipped kernel.

The review branch has five focused commits based on `cf8f6b7275ef4c23937e16b4b0212d2d35af09bb`. The name-lookup regression is committed; the allocation and forced-assertion probes are preserved below. GPU registration tests, a mixed-architecture hardware run, a fresh device-library build and a feature-disabled rebuild were omitted locally for the reasons recorded under Tests. No architectural redesign or PR-description rewrite accompanies this review.

## Appendix A: module allocation failure probe

Save the following as `module-allocation-probe.cpp`. Compile it as HIP C++17 with `TENSILELITE_ENABLE_LOCAL_KERNELS`, using the source and generated TensileLite include directories and the rocisa include root, then link it against the built `tensilelite-host` and HIP runtime. Run it with that library on the dynamic-loader path.

The probe intentionally replaces global allocation only in this separate executable. Its module API returns a stand-in handle and records unloading, so the failure mechanism requires no GPU module.

```cpp
// Copyright Advanced Micro Devices, Inc., or its affiliates.
// SPDX-License-Identifier: MIT

#include <Tensile/hip/HipSolutionAdapter.hpp>
#include <cstdlib>
#include <iostream>
#include <new>

thread_local int failAfter = -1;
int loads = 0;
int unloads = 0;
int allocationToFail = 0;

void* operator new(std::size_t size)
{
    if(failAfter >= 0 && failAfter-- == 0)
    {
        failAfter = -1;
        throw std::bad_alloc();
    }
    if(void* ptr = std::malloc(size ? size : 1))
        return ptr;
    throw std::bad_alloc();
}
void operator delete(void* ptr) noexcept { std::free(ptr); }
void operator delete(void* ptr, std::size_t) noexcept { std::free(ptr); }

hipError_t loadModule(hipModule_t* module, char const*)
{
    ++loads;
    *module = reinterpret_cast<hipModule_t>(1);
    failAfter = allocationToFail;
    return hipSuccess;
}
hipError_t unloadModule(hipModule_t)
{
    ++unloads;
    return hipSuccess;
}
hipError_t noError() { return hipSuccess; }

int main()
{
    using Adapter = TensileLite::hip::SolutionAdapter;
    int failures = 0;
    for(int n = 0; n < 6; ++n)
    {
        loads = unloads = 0;
        allocationToFail = n;
        bool threw = false;
        std::size_t retained = 0;
        {
            Adapter adapter(Adapter::ModuleApi{loadModule, unloadModule, noError});
            try { adapter.loadLocalCodeObject("/nonexistent/allocation-probe.co"); }
            catch(std::bad_alloc const&) { threw = true; }
            failAfter = -1;
            retained = adapter.localCodeObjectCount();
        }
        std::cout << "allocation=" << n << " threw=" << threw
                  << " retained=" << retained << " loads=" << loads
                  << " unloads=" << unloads << '\n';
        if(loads != unloads)
            ++failures;
    }
    return failures ? 1 : 0;
}
```

## Appendix B: fatal assertion while a launcher is active

Save this as `launcher-assert-probe.cpp` and compile it as C++17 against GoogleTest with threads enabled. Run once without `JOIN_ON_EXIT`, then rebuild with `-DJOIN_ON_EXIT`. The first executable aborts; the second reports the intentionally failing assertion and exits with status 1. No HIP calls are needed to reproduce the thread-lifetime failure.

```cpp
// Copyright Advanced Micro Devices, Inc., or its affiliates.
// SPDX-License-Identifier: MIT

#include <gtest/gtest.h>
#include <atomic>
#include <thread>

TEST(LauncherFailure, FailedRegistration)
{
    std::atomic<bool> done{false};
    std::atomic<int> launches{0};
    std::thread launcher([&]() {
        while(!done.load() || launches.load() < 10)
        {
            if(::testing::Test::HasFailure())
                break;
            ++launches;
        }
    });
#ifdef JOIN_ON_EXIT
    struct StopLauncher
    {
        std::atomic<bool>& done;
        std::thread& launcher;
        ~StopLauncher()
        {
            done.store(true);
            if(launcher.joinable())
                launcher.join();
        }
    } stopLauncher{done, launcher};
#endif
    int registeredIndex = -1;
    ASSERT_GE(registeredIndex, 0);
    done.store(true);
    launcher.join();
}

int main(int argc, char** argv)
{
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
```
