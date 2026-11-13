> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13508](https://github.com/ROCm/rocm-libraries/pull/13508)

**Reviewed head:** `a948b2e85b3b7a38e7533647ab6d722f165931bc` (15 commits on base `63939d782570f26e2bcc9598bb9d483e04967d17`, the merge of #13360)

**Review date:** 2026-11-13

**Review mode:** Independent review of the full branch diff from its merge base. Existing review threads and PR discussion were not read. Scope: the on-disk store, its integration into registration, mapping, refresh and device initialization, the public header contract, the TensileLite device-class key, build wiring and tests.

**Suggestion branch:** [review/pr13508-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr13508-suggestions), based on the exact reviewed head.

| Commit | Review item |
| --- | --- |
| [aeefcd1cce45](https://github.com/newling/rocm-libraries/commit/aeefcd1cce459e5d4aee960a128b2032b443cc37) | [Name every hook the test option enables](#name-every-hook-the-test-build-option-enables) |

## Tests

On a host-only gfx1201 build (two gfx1201 devices, so the two-device tests ran) with local kernels and the test hooks enabled, `LocalKernel*:HipSolutionAdapter*` passes 85 of 85 with no skips at the submitted head, including all 33 `LocalKernelPersist` multi-process scenarios. The bf16 TN payloads and the shipped library came from a separately generated full gfx1201 kernel library. The same suites also pass on the submitted head merged with current `develop` (no textual conflicts). The suggestion commit only changes a CMake comment and option help string; it reconfigures cleanly. Root pre-commit and `git diff --check` pass over the branch diff. At the reviewed head, the dedicated local-kernel workflow passes on gfx942 and gfx950.

The base-freshness check reports that the base lacks `develop` commits from 2026-11-03 onward; the branch is about 470 commits behind. One of those commits changes a premise of this PR; see the first actionable item.

No feature-disabled build, sanitizer run or numerical validation beyond the tests' own exact-result checks was performed locally.

## Summary

The PR makes registered local kernels and their exact mappings outlive the process. Payload files are copied into a content-addressed `objects/` directory, and an append-only, per-build, per-device-class journal records which payloads exist and which shape each was mapped to. Every process that names the library replays the journal for a device when hipBLASLt first initializes it, before the first heuristic query, and `hipblasLtLocalKernelRefresh` replays what other processes appended since. Mappings name a solution by its index inside the payload, and assigned indices are rebuilt on load, so process-local indices never reach the disk.

The core design is sound and carefully reasoned. Records are written under an exclusive `flock`, re-read under it, and carry a per-line checksum; a failed append is truncated away rather than left for the next writer to complete. Objects are written to a temporary name, synced and linked into place before any record names them. Replay re-applies mappings strictly in journal order, so re-reading from an earlier offset (after a skipped payload is repaired, or after a read-back is missed) restores each key's last mapping rather than reordering the candidates. The registry lock is never held across file locks, hashing or shard parsing. The code objects of saved payloads are loaded lazily, as for the shipped library, so startup does not pay for loading kernels that are never used. The test suite exercises these paths as real separate processes, including crash residue, replaced journals, lock timeouts and concurrent writers.

## Actionable items

### Drop the gfx1250 A0 device class when rebasing onto develop

**Locations:** [`LocalKernelLibrary.hpp:52-97`](https://github.com/ROCm/rocm-libraries/blob/a948b2e85b3b7a38e7533647ab6d722f165931bc/projects/hipblaslt/tensilelite/include/Tensile/LocalKernelLibrary.hpp#L52), the [public header](https://github.com/ROCm/rocm-libraries/blob/a948b2e85b3b7a38e7533647ab6d722f165931bc/projects/hipblaslt/library/include/hipblaslt/hipblaslt-local-kernel.h#L17), [`local_kernel_library_gtest.cpp:624`](https://github.com/ROCm/rocm-libraries/blob/a948b2e85b3b7a38e7533647ab6d722f165931bc/projects/hipblaslt/clients/tests/src/local_kernel_library_gtest.cpp#L624) and [`local_kernel_persist_test.cpp:70`](https://github.com/ROCm/rocm-libraries/blob/a948b2e85b3b7a38e7533647ab6d722f165931bc/projects/hipblaslt/clients/tests/src/local_kernel_persist_test.cpp#L70).

`LocalDeviceClass::of` gives a gfx1250 that reports `gfx1250` with `asicRevision == 0` the target `gfx1250v0`. The header, the TensileLite comment and both tests justify this as matching the shipped library, which "serves gfx1250 A0 from gfx1250v0". That was true at this PR's base. [#15123](https://github.com/ROCm/rocm-libraries/pull/15123) (`c923380a67f`, merged 2026-11-09) removed the `gfx1250v0` library and the asicRevision check from hipBLASLt and hipSPARSELt. On current `develop`, the device name alone selects `library/<name>/`, and `gfx1250-strict` is the only route to V0 kernels.

The PR merges cleanly onto `develop` and its tests pass there, so nothing fails visibly. After the rebase, though, this class split would be the only remaining asicRevision read in hipBLASLt, and every comment describing it would be false. It is also the only reason `LocalKernelLibrary.hpp` includes `Tensile/hip/HipHardware.hpp` and `dynamic_cast`s to `hip::HipAMDGPU`. When rebasing, take the target from the reported architecture name alone. Remove the `v0` suffix, the HipHardware include and cast, and the A0 cases in `smoke_DeviceClassTellsGfx1250TargetsApart` and `deviceScope()`. Then update the header text about gfx1250 revisions. `gfx1250-strict` stays distinct because the runtime reports it under its own name.

If the author wants to keep a stepping split for local mappings on purpose (for example, so a mapping tuned on B0 is never applied to an A0 that reports `gfx1250`), that is a defensible independent policy. It then needs its own rationale, not a reference to the shipped library. No commit is provided because the change belongs to the rebase; at the reviewed base the current behavior is consistent.

### Update the PR description to match the implementation

Several statements in the description no longer describe the code, and one is reversed:

- "Not in this PR: … scoping records by hipBLASLt version." Journals are now per build: `<scope>/journal-<version>-<git stamp>`, starting with a `V <format> <build> <id>` line. A journal written by another build is not read.
- The layout is given as `<arch>/journal` with records `R <datHash> <coHash> <dat|dat.zlib>` and `E …`. The directory is now a device class (kernel target, compute unit count and, where reported, PCI chip ID, e.g. `gfx950_CU256_ID75a3`). Every record ends in a checksum field.
- Loading and Refresh are described as per architecture. Both are per device class, and the API now returns `HIPBLAS_STATUS_ARCH_MISMATCH` on a device whose class differs from the one hipBLASLt uses for that architecture name. That new failure mode is not mentioned.
- Saved code objects are no longer loaded at startup; they load when a kernel first runs.
- The crash-handling text describes terminating a partial line on the next append. The code now also truncates a failed append and rejects partial lines by checksum.
- Only group- and world-writable directories are said to be refused. The code also refuses directories and journals owned by another user.
- The Test Plan and Test Result list 10 persistence tests and 116 tests in total; there are now 33 `LocalKernelPersist` scenarios.

Reviewers read the description to understand the on-disk format and its compatibility rules. The per-build behavior in particular has user-visible consequences (see Scope decisions), so the description should state it rather than deny it.

## Suggestions

### Name every hook the test build option enables

**Location:** [`projects/hipblaslt/CMakeLists.txt:84-86`](https://github.com/ROCm/rocm-libraries/blob/a948b2e85b3b7a38e7533647ab6d722f165931bc/projects/hipblaslt/CMakeLists.txt#L84).

The comment and the option's help text say `HIPBLASLT_ENABLE_LOCAL_KERNEL_TEST` makes the library honor `HIPBLASLT_LOCAL_KERNEL_TEST_SCOPE`. The option also enables `HIPBLASLT_LOCAL_KERNEL_TEST_CU` and `HIPBLASLT_LOCAL_KERNEL_TEST_PAUSE_MS`, which change device-class checks and add a delay inside `hipblasLtLocalKernelSetExactMatch`. Anyone deciding whether the option is safe to enable needs the complete list. Implemented in [aeefcd1cce45](https://github.com/newling/rocm-libraries/commit/aeefcd1cce459e5d4aee960a128b2032b443cc37).

## Scope decisions

### Saved kernels disappear silently when hipBLASLt is rebuilt or upgraded

Each build reads only `journal-<its own stamp>`, and the stamp includes the git hash. Any rebuild at another commit therefore starts with an empty library: no saved kernels and no mappings. The old journal and its objects remain on disk, and nothing reports why they are unused. The stated reason, that a saved code object takes the kernel arguments its build's launch code passes, justifies not trusting another build's records. It does not require the loss to be silent. A tuning workflow that upgrades hipBLASLt (for example, a nightly ROCm) loses its tuned selections without any message. The author should decide whether to accept this as documented behavior or to warn once per scope when other builds' journals exist but this build's does not. The warning is a few lines in `Store::read`. Re-registering the old payloads under a new build is a separate, larger decision.

### Libraries owned by another user are refused even for reading

Every directory, journal and object must be owned by the effective user. That rules out a deployment where one account (or root) prepares a library that other users' workloads only read, which fits the description's "tuner in one process, workload in another" model when the two run as different users. Accepting root-owned files that are not group- or world-writable, as `ld.so` and `sshd` do, would allow that without letting another unprivileged user choose the code. Writes would still fail on permissions and return `HIPBLAS_STATUS_INTERNAL_ERROR`. This is a policy choice, so it is left to the author rather than implemented here.

## Commentary

Startup cost grows with the size of the library. Each process that sets the variable re-hashes both objects of every saved payload for its device class, and fully parses every shard, when it initializes the device. Payloads that no current mapping uses are included. The object hash processes one byte at a time with two dependent multiply chains. On this host it hashed the 143 code objects of a full gfx1201 kernel library (154 MB) in 0.163 s in each of 5 back-to-back runs, about 0.94 GB/s single-threaded. That is negligible for a handful of payloads, but a library that accumulates whole shipped-size shards (2–7 MB each) adds roughly a second per GB to each process's first device initialization. Without compaction or removal (explicitly deferred), it only grows. This needs no change now, but it is worth recording as a reason to prioritize the deferred introspection and removal work.

`tensile_host.cpp` gains about 900 lines of local kernel registry, replay and journal logic on top of #13360's additions. The functions are coherent, but they share almost nothing with the rest of that file. Moving the local kernel runtime into its own translation unit would make the concurrency invariants easier to review together with `local_kernel_store.cpp`.

## Handoff

Suggestion branch [review/pr13508-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr13508-suggestions) contains one commit, [aeefcd1cce45](https://github.com/newling/rocm-libraries/commit/aeefcd1cce459e5d4aee960a128b2032b443cc37), on top of the reviewed head. The gfx1250 item is described rather than committed because it applies to the rebase. Validation used one gfx1201 host and payloads from a locally generated gfx1201 kernel library. gfx942/gfx950 and gfx1250 behavior rests on the PR's CI and source reading.
