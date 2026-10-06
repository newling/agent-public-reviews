This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12586](https://github.com/ROCm/rocm-libraries/pull/12586)

Reviewed on October 6, 2026 at `c10bbca17c8cd25a8e7cf9f6178631d081d648b9`, branch `tuning-split/2-cache-store`, against the `develop` merge base `d841945147609499bebdc40d3ff29436a3514b8f`. This is a correctness and design review of the complete rebased change. The upstream repository, fork, and reviewed head are public. The [earlier review](review_pr12586.md) remains unchanged.

This edition adds public fix links to the [published follow-up review](review_pr12586_v2.md). Its findings and reviewed PR revision are unchanged. The fixes have been grouped into one commit per implemented item; their final source tree is identical to the previously validated suggestion branch.

Published suggestion branch: [`review/pr12586-v2-fixes`](https://github.com/newling/rocm-libraries/tree/review/pr12586-v2-fixes), based on the exact reviewed head.

| Review item | Commit | Change |
| --- | --- | --- |
| Locale handling | [`94c13f2951a`](https://github.com/newling/rocm-libraries/commit/94c13f2951a313437b9a84e1688483d4e2f52455) | Read and write persisted numbers independently of the application's locale |
| Interrupted append recovery | [`aa965358116`](https://github.com/newling/rocm-libraries/commit/aa965358116b17ee4c733c62fb0c0ba62b833f75) | Separate a new record from an unterminated previous line |

Each commit includes the relevant regression tests. The append-recovery commit can also be cherry-picked independently onto the reviewed PR head.

## Tests

The submitted Linux host-library build and `TuningStore` suite passed; the suggestion branch passed the host build, store suite, and store tests with AddressSanitizer and UndefinedBehaviorSanitizer.

A supplementary host executable linked the submitted library objects and exercised the real key builder, GEMM-object construction and reuse, preference setters, and serialization. It verified normalization of the differing C/C++ defaults, synchronization of scheduling preferences, and persistence of the constructed key. Only device identification was replaced with fixed properties. This checks host behavior; it does not execute GPU kernels or establish equivalent behavior for every combination of public API calls.

The locale and interrupted-append regressions fail against the submitted store and pass with the corresponding changes. The numeric-locale regression executed locally; it explicitly skips on systems without an installed comma-decimal locale. The writer regression uses a custom C++ locale and has no installed-locale requirement.

Local builds used ROCm 7.1 with device-library generation disabled. Sanitizer tests compiled the store and its tests with upstream Clang 23. No local GPU matmul or native Windows run was performed. Current [Linux gfx942 store-test CI](https://github.com/ROCm/rocm-libraries/actions/runs/37324873875/job/111844215531) executes the renamed binary, and Linux gfx942/gfx950 and Windows gfx110X hipBLASLt jobs pass. The Windows build also passes, covering the earlier DLL-linking failure.

CI is not uniformly green. The [gfx90a ASAN job](https://github.com/ROCm/rocm-libraries/actions/runs/37324870268/job/111825031475) launches the smoke binary and times out after 20 minutes without a test banner or sanitizer diagnostic. That log does not establish a store defect. The gfx1250 simulator check reports `gsuaad_gfx1250` failing and six timeouts; its hardware check collected no test results. Coverage checks also fail. Those remaining signals are not diagnosed by this review, and the passing host checks do not resolve them.

## Summary

hipBLASLt chooses a GPU function, or kernel, to perform a matrix multiplication. A tuning file saves a previous choice so that a later call can reuse it. This PR gives those saved records a versioned format and separates their parsing and storage from kernel selection.

The problem key now distinguishes layouts, element types, operations applied to the result, scaling, scheduling preferences, and devices. Both the C API and C++ object API build that key through one function. The C++ object retains the key and updates it when scheduling preferences change. The runtime still resolves the saved index, checks its recorded name, and checks whether the resolved solution supports the actual problem and available workspace. File metadata does not replace those checks.

The separation is useful: parsing, matching, duplicate handling, and persistence can be exercised without running a GPU kernel. Returning copies of entries under a read lock also avoids exposing map iterators to later mutation. The fixes from the earlier review are present: private parsers no longer import DLL symbols, the test binary matches the artifact naming convention, and both recorded names survive serialization.

The responsibilities in the split from [#10424](https://github.com/ROCm/rocm-libraries/pull/10424) are:

| PR | Responsibility |
| --- | --- |
| [#12585](https://github.com/ROCm/rocm-libraries/pull/12585), merged | Repair existing override replay and validate saved entries by name |
| **#12586, this review** | Define the expanded key, versioned rows, host store, and existing override-path integration |
| [#12587](https://github.com/ROCm/rocm-libraries/pull/12587) | Add managed cache replay, including matmul calls without an explicit algorithm |
| [#12588](https://github.com/ROCm/rocm-libraries/pull/12588) | Measure candidate kernels for unseen problems and persist the winner |
| [#12589](https://github.com/ROCm/rocm-libraries/pull/12589) | Preserve incomplete searches and decide when to resume or widen tuning |
| [#12590](https://github.com/ROCm/rocm-libraries/pull/12590) | Route benchmark tuning through the library's tuner |

The last two branches depend on #12588 and are independent of each other. This PR introduces no runtime tuning mode and has no production caller of its row writer yet. Its storage design is a reasonable basis for the later layers. The review concerns below concern persistence behavior; they do not show incorrect numerical results from the existing override path.

## Actionable items

### Use a fixed numeric locale for persisted values

Locations: [`TuningCacheStore.cpp:419`](https://github.com/ROCm/rocm-libraries/blob/c10bbca17c8cd25a8e7cf9f6178631d081d648b9/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/TuningCacheStore.cpp#L419) and [`TuningCacheStore.cpp:103`](https://github.com/ROCm/rocm-libraries/blob/c10bbca17c8cd25a8e7cf9f6178631d081d648b9/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/TuningCacheStore.cpp#L103).

`formatTuningRow` constructs its output streams using the application's current C++ locale. A locale with digit grouping and a decimal comma writes dimension `1024` as `1.024`, index `1234` as `1.234`, and time `12.5` as `12,5`. The strict reader rejects the grouped integers, and the decimal comma introduces another CSV column. The writer can therefore report a successful append whose row cannot be loaded, even by the same build.

The reader has a related issue: `real()` uses `std::stod`, which follows the C numeric locale. Under the installed `en_DK.utf8` locale, a valid file containing `12.5` reloads its timing as `12`. This second case affects timing metadata, not the selected kernel or numerical result.

Give the writer's value stream the classic locale, and parse floating-point metadata with that same locale. Do not change the application's global locale to implement the fix. Commit [`94c13f2951a`](https://github.com/newling/rocm-libraries/commit/94c13f2951a313437b9a84e1688483d4e2f52455) makes those changes. Its regressions reproduce both lost rows and changed timing metadata on the submitted code.

These helpers are introduced here; their production use arrives with #12588. Fixing their numeric representation here prevents the later tuner from inheriting a persistence format that depends on application settings.

## Suggestions

### Keep the next append readable after an interrupted final line

Location: [`TuningCacheStore.cpp:535`](https://github.com/ROCm/rocm-libraries/blob/c10bbca17c8cd25a8e7cf9f6178631d081d648b9/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/TuningCacheStore.cpp#L535).

The loader already handles an orphan header, but the appender assumes the existing file ends with a newline. If a process stops partway through a header or value line, the next `appendTuningRow` concatenates its header with that suffix. It returns success, yet the next complete record disappears on reload because the combined header and values do not form a valid record.

I reproduced this with both an interrupted header and an interrupted value line: append a new entry at index 9, close the file, and reload it; the submitted code accepts no entry. This is recovery after a previous interruption, within the documented single-writer usage. It does not require concurrent processes writing the same file.

Commit [`aa965358116`](https://github.com/newling/rocm-libraries/commit/aa965358116b17ee4c733c62fb0c0ba62b833f75) inserts a newline before an append to a nonempty file. Existing complete files gain a harmless blank line, and incomplete suffixes cannot consume the next header. The regression retains index 9 in both cases. This is a defensive persistence improvement for the later writer, rather than evidence of a failure in normal override replay today.

## Commentary

The expanded key and the legacy key make different promises. Versioned rows require the expanded fields. Legacy rows deliberately match the historical ten fields, and both replay paths try those rows after the exact-key candidates. Consequently, changing a stride or result operation can still find a legacy entry. The subsequent solution-support check remains essential. Keeping old files usable is a reasonable compatibility choice, but the full-key guarantee applies to versioned rows, not every cache hit.

Please document the intended lifetime of legacy-file support. The benchmark still writes unversioned rows at this PR, so removing the reader here would break the existing benchmark-to-override workflow. #12590 switches the benchmark to the versioned writer but retains legacy reading, and the stack descriptions do not specify a deprecation or removal policy. State whether that compatibility is indefinite or whether a future release will require users to regenerate their files. Existing rows lack fields required by the expanded key, so adding a version number alone cannot migrate them. This is a policy clarification; no removal or migration change is implemented on the suggestion branch.

Problem identity, solution identity, and search policy are also separate concerns. This PR describes which problem an entry serves. It preserves #12585's accepted name-validation policy; it does not prove that a matching name identifies identical generated code across builds. Alpha, beta, and C/D aliasing are deliberately outside the key because heuristic queries cannot faithfully represent them. Reusing a valid solution therefore does not promise that it remains the fastest choice for every call sharing that key. Stronger solution fingerprints remain separate work.

Current-format entries are returned in file order, with later duplicates refreshing metadata. That is sufficient for this layer's existing override consumer. Once a later process may replace an earlier winner, replay ordering becomes part of the retuning policy. #12589 changes that ordering together with its completion metadata. Review those together: deciding that an entry is final while replaying a different, older entry would violate the intended behavior.

The submitted unit tests construct keys manually. Their strengths are the format and store checks; they cannot by themselves verify every public API's construction of the expanded key. The host probe adds evidence for the normalization and lifecycle cases described above, and #12588 explicitly schedules GPU integration tests with the production writer. That division is reasonable. Those tests should remain attached to the writer when the stack is updated.

At this snapshot, none of #12587–#12590 contains the reviewed #12586 head. They still need to incorporate this rebased layer and its fixes. This review inspects those branches only to establish dependencies and consumers; it is not a correctness review of their tuners or retuning policies. The current #12586 description's instruction to wait for #12585 and review only the top commit is also obsolete: the rebased PR has four commits.

The handoff is the published branch [`review/pr12586-v2-fixes`](https://github.com/newling/rocm-libraries/tree/review/pr12586-v2-fixes) with the commit mapping above. The host build, store suite, sanitizer regressions, and changed-line formatting were rechecked before publication. No broader tuning policy, stronger identity mechanism, GPU kernel change, or PR-description rewrite is included.
