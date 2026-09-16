This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#11295](https://github.com/ROCm/rocm-libraries/pull/11295)

## Tests

`git diff --check` passed. The focused Python test module could not start because `pytest` is not installed, and the focused C++ test target could not be compiled because the available compiler rejects the required gfx1250 target. An isolated UBSan probe confirmed the signed-overflow item below. The current TensileLite coverage and Math CI checks pass; the quick hipBLASLt ASAN and gfx1250 TensileLite checks currently fail, but their available status does not establish a cause.

## Summary

This PR introduces a versioned indexed MessagePack layout that keeps individual solution payloads unparsed until selection reaches a leaf. The reader preserves the legacy layout, and the writer keeps the new format opt-in, which is a sound compatibility boundary for a new on-disk schema. `SolutionBlobCache` also has clear ownership and publication semantics: it owns the bytes, retains one published object for an index, memoizes failures, and carries the shard code-object filename to deferred solutions. The focused Python and C++ coverage added for format validation, writer behavior, cache behavior, parity, and shard registration is substantial.

The client’s full-enumeration mode needs one additional loading step before this can safely support a freshly initialized lazy master.

## Actionable items

### Load mapped shards before enumerating every solution

`projects/hipblaslt/tensilelite/include/Tensile/MasterSolutionLibrary.hpp:348-379` materializes only `blobCache` and the caches already present in `solutionSources`. A newly initialized lazy master has neither: the mapping has been read, but no index lookup or placeholder traversal has loaded a shard. Consequently, `projects/hipblaslt/tensilelite/client/src/SolutionIterator.cpp:374-380` leaves `solutions` empty and throws when `AllSolutionsIterator` is constructed as the first operation. This is a normal client path when best-solution mode is disabled, and it contradicts the new all-solutions support described by the change.

Load every unique shard named by `libraryMapping` before collecting and materializing the cache sources, then publish their solutions as the method already does. Add a client-level regression test that initializes the existing mapped indexed-shard fixture and constructs `AllSolutionsIterator` without first resolving an index; it should enumerate every shard index.

### Do not overflow while formatting a rejected span

`projects/hipblaslt/tensilelite/include/Tensile/Serialization/SolutionLibrary.hpp:242-251` correctly validates a span with unsigned subtraction, but the rejection message then evaluates `offset + length` as signed `int64_t`. The malformed-input case with both values equal to `1 << 62` therefore reaches signed overflow and undefined behavior while attempting to reject the file. UBSan reports this exact operation.

Avoid computing the endpoint in the diagnostic with signed arithmetic. Reporting `offset` and `length` separately is sufficient, or compute an endpoint only after a checked representability test. Keep the large-span malformed-file case under an overflow sanitizer where available.

## Suggestions

None.

## Commentary

The design choice to parse outside the cache writer lock is appropriate for selection workloads: it avoids serializing independent solution requests while still ensuring callers receive the same retained object for an index. Keeping the indexed writer opt-in also gives the reader-first rollout a clear compatibility story.

## Appendix: temporary probes

The following regression test was used with the existing mapped indexed-shard fixture. It requires adding `#include "SolutionIterator.hpp"` to `IndexedLibraryLoad_test.cpp`.

```cpp
TEST_F(PlaceholderIndexedShardTest, AllSolutionsIteratorLoadsAnUnvisitedIndexedShard)
{
    if(!layOutLibrary())
        GTEST_SKIP() << "legacy fixture unavailable or stale; see configs/SolutionLibraries/readme";

    auto lib = LoadLibraryFile<ContractionProblemGemm, ContractionSolution>(masterPath().string());
    ASSERT_NE(lib, nullptr);
    auto master = std::dynamic_pointer_cast<Master>(lib);
    ASSERT_NE(master, nullptr);
    ASSERT_TRUE(master->initLibraryMapping(masterPath().string()));
    ASSERT_TRUE(master->solutions.empty());
    ASSERT_TRUE(master->solutionSources.empty());

    EXPECT_NO_THROW({
        Client::AllSolutionsIterator iterator(
            master, std::shared_ptr<Hardware>{}, 2.0, -1, -1, false);
    });
    EXPECT_EQ(master->solutions.size(), shardIndices.size());
}
```

The following standalone probe was compiled with signed-integer-overflow sanitization. It reports that the sum cannot be represented in `int64_t`.

```cpp
#include <cstdint>
#include <iostream>

int main()
{
    constexpr int64_t offset = int64_t(1) << 62;
    constexpr int64_t length = int64_t(1) << 62;
    std::cout << offset + length << '\n';
}
```
