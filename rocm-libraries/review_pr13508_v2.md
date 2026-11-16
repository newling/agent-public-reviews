> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13508](https://github.com/ROCm/rocm-libraries/pull/13508)

**Reviewed head:** `49a49ea7106783c8e59564551dc94b5055f44a76`, with merge base `93111abbd56c8bf46fcff7003424711da1ea918f`.

**Review date:** 2026-11-16

**Scope:** Independent second review of the persistence implementation, registration and replay, device-class matching, public contracts, build wiring and tests. The previous published review was consulted; current PR discussion and review threads were not read. This round excludes nits.

**Suggestion branch:** [review/pr13508-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr13508-v2-suggestions), based on the reviewed head. Commit [1f1eb8a9e12](https://github.com/newling/rocm-libraries/commit/1f1eb8a9e1224ea8be16ab91176b3b2b9ae31407) implements the actionable item.

## Tests

The submitted implementation passes all 86 existing `LocalKernel*` and `HipSolutionAdapter*` tests on a machine with two gfx1201 GPUs, with no skips. The added directory-sync regression fails for both kernel registration and mapping publication. The initial 300-second test cap was reached near the end; the remaining four existing tests were then run separately and passed. The final suggestion passes all 87 tests in one run, with no skips, including failed-save retries and loading in another process. Standalone filesystem probes confirm that the suggestion rejects both permission failures and an injected object-directory `fsync` error, and adds the journal and parent-directory syncs.

Validation uses a Release host build with local kernels and the test hooks enabled, plus a separately generated gfx1201 device library. Its inactive `FusedGemmA2A` metadata was translated to the equivalent `FusedA2A: Disabled` representation required by upstream [#14168](https://github.com/ROCm/rocm-libraries/pull/14168); the code objects were unchanged. The unconverted fixture fails to load on the new base, independently of persistence. At review intake the dedicated local-kernel CI passed on gfx942 and gfx950. Root and component pre-commit checks and formatting of the suggestion changes pass. No fresh sanitizer, feature-disabled build, other GPU architecture run, or power-loss test was performed locally.

## Summary

This PR adds persistence to the runtime kernel registration introduced in [#13360](https://github.com/ROCm/rocm-libraries/pull/13360). A process can leave additional compiled kernels and their problem mappings for subsequent workload processes, storing the compiled code and launch metadata separately from the shipped library. Every process using the directory reconstructs its own kernel indices, while saved mappings identify a solution by the hashes of its payload files and its index inside the payload. That distinction is necessary because an assigned runtime index is not a stable identifier across processes.

The implementation covers more than writing a cache file: it coordinates writers, detects incomplete records, restores mappings in journal order, and retries payloads whose damaged files have been repaired. Loading code objects only when a kernel is used avoids loading every saved kernel into every process. Build-specific journals and device-class matching deliberately restrict reuse.

The previous review's architecture naming and description concerns have been addressed. The new warning also explains why kernels saved by another build are not loaded. I found one additional issue in the filesystem durability path.

## Actionable items

### Complete directory synchronization before reporting a successful save

**Locations:** [`local_kernel_store.cpp:168`](https://github.com/ROCm/rocm-libraries/blob/49a49ea7106783c8e59564551dc94b5055f44a76/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/local_kernel_store.cpp#L168), [`publishObjects:855`](https://github.com/ROCm/rocm-libraries/blob/49a49ea7106783c8e59564551dc94b5055f44a76/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/local_kernel_store.cpp#L855), and [`appendUnlessKnown:932`](https://github.com/ROCm/rocm-libraries/blob/49a49ea7106783c8e59564551dc94b5055f44a76/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/local_kernel_store.cpp#L932).

`syncDirectory` ignores both a failed directory open and a failed `fsync`, so `publishObjects` reports success even when the object names have not been made durable. Separately, creating a journal synchronizes its contents but never its containing directory; the ancestors automatically created for a new library path also lack synchronization of their names. Linux's [fsync contract](https://man7.org/linux/man-pages/man2/fsync.2.html) explicitly says that syncing a file does not necessarily persist its directory entry. After a machine crash, an acknowledged save can therefore lose its journal or leave a journal referring to missing objects.

A syscall probe at the submitted head forces the object-directory `fsync` to return `EIO`; the store still reports success and appends the payload record. A second probe makes the device-class directory searchable and writable but unreadable (`0300`), so files can be created but the directory cannot be opened for syncing. Journal creation still succeeds without attempting that sync. These exercise error handling without corrupting payload contents or simulating a power cut.

Propagate directory synchronization failures, persist created directory entries, and sync the journal's containing directory before appending records. These checks must also cover existing paths: a failed attempt or another writer can leave a directory or empty journal whose name has not yet been synchronized. The API regression at the submitted head publishes 778 new kernels after the failed object-directory open, and publishes the mapping after the journal-directory restriction. An extended case rejects a partial fix that skips synchronizing an existing directory on retry. The regression also checks recovery after restoring permissions and loading the saved result in another process. Implemented and validated in [1f1eb8a9e12](https://github.com/newling/rocm-libraries/commit/1f1eb8a9e1224ea8be16ab91176b3b2b9ae31407).

## Suggestions

None.

## Scope decisions

Payload persistence complements the existing [tune/cache machinery](https://github.com/ROCm/rocm-libraries/pull/12588). The tuning cache records a choice referring to a solution that must already be available; this PR preserves the compiled code and launch metadata needed to restore an externally supplied kernel in another process. Those payloads still need to use the compatible hipBLASLt/Tensile formats and calling convention. The exact-mapping journal also records a selection decision, overlapping the tuning cache's responsibility. A usable tuning-file entry takes precedence over a local mapping, and an explicitly supplied algorithm retains its selection.

Convergence on one selection store can be considered separately. It would need stable references to local kernels, an explicit policy for manual mappings versus measured winners, and a decision about when newly registered kernels should cause retuning. The current persistence capability is useful with the defined precedence; this review does not require a selection redesign or claim that a combined tuning-and-persistence workflow has been tested.

## Commentary

Reuse currently requires the same hipBLASLt build, GPU class and effective user. Those restrictions support a tuner and workload running under one account with one installed build. They do not supply a portable kernel package for arbitrary ROCm upgrades or a library centrally published for other users. The current description states these limits; the new warning improves the upgrade case without implying automatic migration.

## Appendix: standalone filesystem reproduction

Save the following as `store_probe.cpp`. It exercises the actual store implementation with arbitrary payload bytes; no GPU or valid kernel is needed to check the file operations. Use the generated headers from a configured hipBLASLt build and run as an ordinary user for the permission cases.

```cpp
#include "include/local_kernel_store.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sys/stat.h>
#include <cstdlib>

namespace fs = std::filesystem;
namespace store = rocblaslt::local_kernel_store;
int main(int argc, char** argv)
{
    if(argc != 3) return 2;
    const fs::path root = argv[1];
    const std::string mode = argv[2];
    setenv("HIPBLASLT_LOCAL_KERNEL_LIBRARY", root.c_str(), 1);
    auto* s = store::Store::configured();
    if(!s) return 3;
    const fs::path source = root.parent_path() / "source";
    std::ofstream(source) << "payload bytes\n";
    fs::path restricted;
    if(mode == "objects") restricted = root / "objects";
    if(mode == "journal")
    {
        restricted = root / "gfx1201_CU32";
        fs::create_directory(restricted);
    }
    if(!restricted.empty() && chmod(restricted.c_str(), 0300)) return 4;
    store::PayloadRecord payload;
    store::StagedObjects staged;
    std::string error;
    bool ok = store::identifyPayload(source, source, &payload, &error)
        && s->stageObjects(source, source, &payload, &staged, &error)
        && s->publishObjects(&staged, &error)
        && s->appendPayload("gfx1201_CU32", payload, &error);
    if(!restricted.empty()) chmod(restricted.c_str(), 0700);
    std::cout << "save_success=" << ok << " error=" << error << '\n';
    return ok ? 0 : 1;
}
```

At the reviewed revision, build and run it with:

```sh
clang++ -std=c++17 -O1 -pthread \
  -I "$SRC_DIR/projects/hipblaslt/library/src/amd_detail/rocblaslt/src" \
  -I "$BUILD_DIR/library/include" \
  store_probe.cpp \
  "$SRC_DIR/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/local_kernel_store.cpp" \
  -o store_probe
probe_dir=$(mktemp -d)
./store_probe "$probe_dir/objects-case" objects
strace -yy -e trace=openat,fsync -o journal.trace \
  ./store_probe "$probe_dir/journal-case" journal
strace -yy -e trace=openat,fsync -o normal.trace \
  ./store_probe "$probe_dir/normal-case" normal
sync_number=$(awk '/^fsync\(/ {n++; if ($0 ~ /\/objects>/) {print n; exit}}' normal.trace)
strace -yy -e trace=openat,fsync -e inject=fsync:error=EIO:when="$sync_number" -o eio.trace \
  ./store_probe "$probe_dir/eio-case" normal
strace -yy -e trace=mkdir,openat,fsync -o nested.trace \
  ./store_probe "$probe_dir/new/a/b/library" normal
```

The permission and injected-error cases all report `save_success=1` at the submitted head. The journal trace has a file `fsync` but no `fsync` of its device-class directory. The object-directory `fsync` is the fifth at the submitted head; its injected `EIO` is ignored. The command derives its ordinal from a normal trace so it also works with the suggestion's additional directory syncs. The nested-path trace at the submitted head omits synchronization of the entries for `new`, `a`, and `b`.

The suggestion returns failure with the relevant directory error in each permission and injected-error case, synchronizes the parent-directory entries, and still succeeds without restricted permissions or injected errors.

The [suggestion branch](https://github.com/newling/rocm-libraries/tree/review/pr13508-v2-suggestions) contains one [commit](https://github.com/newling/rocm-libraries/commit/1f1eb8a9e1224ea8be16ab91176b3b2b9ae31407) for the actionable item. No implementation items remain open; the separate selection-policy discussion and validation limits are recorded above.
