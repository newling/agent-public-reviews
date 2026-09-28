This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12585](https://github.com/ROCm/rocm-libraries/pull/12585)

**Published review:** [Review, findings and design discussion](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12585.md)

**Reviewed head / suggestion-branch base:** `15ca67782a47898743ff1dd1a05278cbad35375a`

**Discussion and publication update:** 2026-09-28. The public PR still has the reviewed head. This revision consolidates the design discussion and publishes references in both directions between the review and the accompanying branches. The branch updates contain documentation only.

**Branch references:**

| Branch | Published tip | Scope |
| --- | --- | --- |
| [Review fixes](https://github.com/newling/rocm-libraries/tree/review/pr12585-suggestions) | [579f75591de](https://github.com/newling/rocm-libraries/commit/579f75591de0c84294df3fb1b7b87a63396af34f) | Two bounded review fixes, test formatting and a [review reference page](https://github.com/newling/rocm-libraries/blob/579f75591de0c84294df3fb1b7b87a63396af34f/projects/hipblaslt/docs/conceptual/pr12585-review.md) |
| [Fingerprint prototype](https://github.com/newling/rocm-libraries/tree/users/jnewling/hipblaslt-solution-fingerprint-prototype) | [ffcc971c6bd](https://github.com/newling/rocm-libraries/commit/ffcc971c6bd69ddf5b246929fd14023f5cf8810f) | The review fixes, experimental build-time solution fingerprints and a [review reference page](https://github.com/newling/rocm-libraries/blob/ffcc971c6bd69ddf5b246929fd14023f5cf8810f/projects/hipblaslt/docs/conceptual/pr12585-review.md) |

| Commit | Review item |
| --- | --- |
| [60af059977b](https://github.com/newling/rocm-libraries/commit/60af059977b38594eaf30394b2456b8d612cc389) | Reject incomplete tuning rows; add incomplete-row and empty-trailing-column regressions |
| [d71a3e6e4c3](https://github.com/newling/rocm-libraries/commit/d71a3e6e4c33bd05a66b320754007af4553524c1) | Give the heuristic output count a nonzero initial value in the test helper |
| [6e797f00b66](https://github.com/newling/rocm-libraries/commit/6e797f00b66d9f3a8a9c90b7b5516d6841f0ac72) | Prototype fingerprint generation, metadata, tuning-file output and replay validation |
| [f5e8a4aab48](https://github.com/newling/rocm-libraries/commit/f5e8a4aab48e0abe60ee252e407974080053b063) / [5baa1d76852](https://github.com/newling/rocm-libraries/commit/5baa1d76852374dae638dc0fade233057bc4a54e) | Equivalent test-formatting follow-ups on the review and prototype branches |
| [5166118284d](https://github.com/newling/rocm-libraries/commit/5166118284df183603790b688795aa05ca9680f3) | Remove the prototype's unused import and finish test formatting |
| [579f75591de](https://github.com/newling/rocm-libraries/commit/579f75591de0c84294df3fb1b7b87a63396af34f) / [ffcc971c6bd](https://github.com/newling/rocm-libraries/commit/ffcc971c6bd69ddf5b246929fd14023f5cf8810f) | Documentation-only links to this published review and the related branch; no implementation changes |

The implementation snapshots are [f5e8a4aab48](https://github.com/newling/rocm-libraries/commit/f5e8a4aab48e0abe60ee252e407974080053b063) for the review fixes and [5166118284d](https://github.com/newling/rocm-libraries/commit/5166118284df183603790b688795aa05ca9680f3) for the prototype. The published tips additionally contain the reference documentation linked above.

The first two fixes can be inspected or cherry-picked independently. The fingerprint prototype builds on both and is a separate follow-up, not a prerequisite for accepting the PR's name-validation policy. Source line references below refer to the submitted head unless stated otherwise.

## Tests

The submitted host library and tuning-test source built; the suggestion branch's host library, benchmark translation unit, and updated tuning-test executable built. A probe linked to the production parser reproduced incomplete-row admission on the submitted code and passed after the fix, alongside complete-row, legacy-row, orphan-header, and empty-trailing-column checks. `git diff --check` passed.

GPU execution did not complete. Running `tuning-cache-tests --gtest_filter='TuningCache_pre_checkin.*'` on gfx1201 with the installed device library stopped during initialization because `TensileLiteLibrary_lazy_gfx1201_Mapping.dat` was absent. The installed ROCm 7.1 library uses the older mapping layout. Generating a replacement with `GPU_TARGETS=gfx1201` and `TENSILELITE_LOGIC_FILTER=gfx1201/GridBased/gfx1201_Cijk_Ailk_Bljk_HHS_BH_Bias_SHB_HA_S_SAB_SCD_SAV_UserArgs` passed logic validation, then failed because AMD clang 20 from ROCm 7.1 does not recognize the generator's `-Xclangas` option. These are local environment limitations, not observed failures in the changed parser or replay code. The benchmark compile also required explicitly supplying the installed OpenBLAS header directory.

The 2026-09-28 CI refresh is mixed. Formatting, root pre-commit and preliminary checks pass, and all six Linux gfx94X hipBLASLt test shards pass. Math CI precheckin and coverage report failures in their Test stages; gfx1250 hardware/TensileLite checks, the Windows gfx110X hipBLASLt test, and the TensileLite C++ coverage check also fail. The [gfx90a ASAN job](https://github.com/ROCm/rocm-libraries/actions/runs/36440776023/job/108990573386) failed in **Fetch sources**, before compilation. The other failures have not been diagnosed in this review update and are not attributed to this PR without evidence. The PR reports MI300X results, which were not reproduced locally. Its `pre_checkin` fixture runs in the standard tier; quick/smoke does not select it. No broad local numerical suite was run because the required device-library path was unavailable.

Before publication, the full branch diffs passed root pre-commit and C++ changed-line formatting checks. The full TensileLite Python format/import/lint checks have inherited failures reproduced on the develop merge base; after removing an unused import introduced by the prototype, the Flake8 diagnostic set matches that baseline. Broad Python reformatting was left out of these focused branches.

For the cross-reference publication, root pre-commit was rerun across both complete branch diffs and passed its applicable checks. Diffs from the previously validated implementation snapshots contain only Markdown documentation; no source builds or GPU tests were repeated for those additions.

## Summary

The existing offline workflow runs `hipblaslt-bench` to choose an algorithm, writes its numeric solution index, and later uses that file to influence heuristic queries. This PR adds a kernel name to the saved choice and checks that name before returning the algorithm. “Replay” here means selecting the saved algorithm during a heuristic query; this PR does not introduce online benchmarking or change execution to consult the file when an application supplies an algorithm directly.

The C API previously disabled the entire file when its source revision differed; the C++ extension API omitted that check. Both now apply the same per-row rule: a named row must match the name found at its saved index, while an unnamed row requires a nonempty matching source revision. A matching name is followed by the existing problem-support and workspace checks. Rejected rows allow another row for that key, or ordinary heuristic selection, to be tried.

There are useful independent repairs here. Clearing the append-only result vector between candidates makes later rows usable. Copying map entries under the lock fixes the escaped-iterator contract. The grouped-GEMM guard removes an invalid cast, and suppressing grouped output from the benchmark closes the corresponding producer path. Restoring XF32 after an unsuccessful fallback keeps subsequent selection on the original problem.

The approach is a reasonable incremental improvement: C++ gains validation, and C can retain individually matching entries across builds. Its name check establishes a limited identity contract, not unchanged solution settings, machine code or performance. That limitation does not by itself justify rejecting the improvement. Evaluate the concrete implementation findings below on their merits; stronger identity, including the experimental fingerprint approach, can remain separate follow-up work.

## Actionable items

### Reject incomplete value rows before applying the legacy-row rule

`projects/hipblaslt/library/src/amd_detail/rocblaslt/src/UserDrivenTuningParser.cpp:99-105,249-259` pairs columns only up to the shorter of the header and value lists. A header declaring `solution_index,kernel_name` followed by a value row ending at `...,12` therefore becomes an index-only entry. If the file's version matches, the loader admits it as a legacy row and replay bypasses name validation. An interrupted append can also stop within the numeric index, turning a prefix of the intended index into another supported solution. The whole-row support check cannot establish that this was the recorded choice.

Require equal header/value cardinality before constructing the row, preserving explicit empty trailing CSV cells so well-formed rows remain readable. Commit [60af059977b](https://github.com/newling/rocm-libraries/commit/60af059977b38594eaf30394b2456b8d612cc389) implements this and adds `TruncatedNamedEntryIsNotTreatedAsLegacy` plus `NamedEntryWithEmptyTrailingColumnReplays`. The host probe below loads the incomplete record as `index=12 named=0` on the submitted code and loads no entry after the fix. Both GPU regressions compile; execution remains unverified for the environment reasons above. This fixes missing cells, not every possible corruption of a value row; a checksum or record terminator would be a separate format decision.

## Suggestions

### Avoid initializing the output count to the correct answer in the regression helper

`projects/hipblaslt/clients/tests/src/tuning_cache_test.cpp:221-234,667-670` initializes the actual count passed to `hipblasLtMatmulAlgoGetHeuristic` to zero. The `returned = -1` in the outer test is only a destination for the helper's later copy. Consequently, the existing single-algorithm test does not exercise the condition behind the uninitialized-count fix: the caller has already supplied the zero the implementation needs before adding the override result.

Commit [d71a3e6e4c3](https://github.com/newling/rocm-libraries/commit/d71a3e6e4c33bd05a66b320754007af4553524c1) starts the helper's output parameter at `-1`, so the API must initialize it. The updated test source builds. A GPU mutation run with the library initialization removed remains unverified locally.

## Commentary

### Relationship to the rejected larger PR

The rejection of [#10424](https://github.com/ROCm/rocm-libraries/pull/10424) was against `2de5d9dcef73b1cc1e08a289170503b8b812e6cc`. That proposal combined offline fixes, a larger persisted problem key, cache lookup, runtime benchmarking, tuning-resource controls, partial-search policy, and diagnostics. Its reference branch has since changed, so the old findings should not be treated as findings against every current split PR.

The current stack separates the principal decisions as follows:

| PR | Main scope |
| --- | --- |
| [#12585](https://github.com/ROCm/rocm-libraries/pull/12585) | Existing offline override fixes and name validation |
| [#12586](https://github.com/ROCm/rocm-libraries/pull/12586) | Versioned store, expanded problem key, and host tests |
| [#12587](https://github.com/ROCm/rocm-libraries/pull/12587) | Managed cache mode and execution-time lookup |
| [#12588](https://github.com/ROCm/rocm-libraries/pull/12588) | Runtime tuning of unseen problems |
| [#12589](https://github.com/ROCm/rocm-libraries/pull/12589) | Saving and revisiting incomplete searches |
| [#12590](https://github.com/ROCm/rocm-libraries/pull/12590) | Making the benchmark use the library's tuner |

The last two depend on #12588 independently. Their descriptions address the requested separation of partial-search policy and convergence on one tuner; their implementations were not fully reviewed here. #12585 adds no new tuning mode or compile-time feature variant, and its existing offline workflow is usable without the rest of the stack.

### Size and complexity

These are line additions/deletions, including comments and formatting, rather than counts of new behavior. The submitted-PR column compares its reviewed head with merge base `2ecc2115e9fc071a31047b803bdaab9fc09c507b`. The prototype column compares implementation snapshots `f5e8a4aab48` and `5166118284d`, so the shared review fixes are excluded. The later publication adds 9 documentation lines on the review branch and 11 on the prototype branch; those cross-references are excluded from this implementation comparison.

| Category | Submitted PR added / removed | Prototype additionally added / removed |
| --- | ---: | ---: |
| Library, benchmark and generator implementation | 458 / 233 | 230 / 45 |
| Tests and their build wiring | 706 / 0 | 374 / 1 |
| Documentation and changelog | 36 / 4 | 86 / 0 |
| Total | 1,200 / 237 | 690 / 46 |

The submitted PR has a net implementation increase of 225 lines; about 59% of its additions are tests and test wiring. The benchmark's shared `testing_matmul.hpp` is counted as implementation because it produces tuning records, despite its filename. The change is larger than a name comparison alone because it repairs several existing override-path contracts. It does not introduce the runtime tuner or cache machinery from the larger proposal. The prototype adds substantially more integration across generation, metadata, API access, CSV output and replay; its stronger check is not free in maintenance cost.

### The name check validates an index but does not replace it

For a saved `(index=123, kernel_name=K)`, the concrete outcomes are:

| Running library | Result |
| --- | --- |
| Index 123 still names K | Try that solution, subject to support/workspace checks |
| K moved to index 456, while 123 names another kernel | Reject this row; do not search for K |
| Index 123 names K, but its launch defaults changed | Accept the identity check and use the new defaults |
| Index 123 names K, but code generation or compilation changed its implementation | Accept the identity check; compiled contents are not compared |

`kernel_name` leaves out runtime launch settings such as how the reduction is split and how workgroups are scheduled. Multiple solutions can therefore share it. The documentation added at `projects/hipblaslt/docs/how-to/how-to-use-hipblaslt-offline-tuning.rst:99-119` explicitly acknowledges the changed-defaults and moved-index cases. It does not explicitly describe changed code behind an unchanged name. Its phrase "the same compiled kernel" is stronger than the implemented comparison: the check establishes the same name at the saved index, without comparing compiled contents. The limited contract does not establish that a previously measured launch configuration or performance survives an upgrade.

The existing `solution_name` is more descriptive, but it is also not a complete stable identity. In `projects/hipblaslt/tensilelite/Tensile/SolutionStructs/Naming.py:149-165`, both name builders return a custom kernel's supplied name directly, and both normalize every fixed `WorkGroupMappingXCC` value to 1. A direct naming probe using the existing `_minimal_kernel` fixture found identical kernel and solution names for values 2 and 8. Those values remain distinct runtime defaults in `sizeMapping.workGroupMappingXCC`. In contrast, changing ordinary `WorkGroupMapping` changes the solution name while leaving the kernel name unchanged. Neither string is a hash of the compiled code.

A future stable lookup could use a versioned description of the complete solution and launch settings, with a lookup table resolving that description to the current index. It would need an explicit policy for missing settings, collisions, custom kernels, and code-generator changes. The current name accessor alone does not supply that contract. The separately requested fingerprint prototype below explores stronger validation; finding solutions at moved indices remains future work.

### Enumerating solution fields is a smaller alternative

The omitted fields can be recorded explicitly. `projects/hipblaslt/tensilelite/Tensile/SolutionStructs/Naming.py` already identifies eight internal arguments excluded from kernel deduplication identity; the minimal kernel-name parameter list also omits them. GSU is separately omitted or masked, and fixed WGMXCC values are normalized. This gives ten concrete settings to retain:

| Settings | Why their actual values matter |
| --- | --- |
| `WorkGroupMapping`, `WorkGroupMappingXCCGroup`, `SFCWGM` | Workgroup scheduling and mapping |
| `StaggerU`, `StaggerUStride`, `StaggerUMapping` | How work is staggered through the reduction dimension |
| `GlobalSplitU`, `GlobalSplitUCoalesced`, `GlobalSplitUWorkGroupMappingRoundRobin` | Reduction splitting and its scheduling |
| `WorkGroupMappingXCC` | The actual fixed value is lost when naming normalizes it to 1 |

Ten is a concrete starting list, not a proven exhaustive count of all execution-relevant fields missing from a name. Custom names bypass the ordinary naming logic, and other solution/problem metadata also needs consideration. Reusing the existing serialized execution settings, including `SizeMapping`, would be less fragile than maintaining a second hand-written list of exceptions to the naming scheme. A versioned representation needs defined treatment of missing/default fields, stable ordering and values that only identify storage or ranking, such as an index or performance estimate. Runtime overrides need to be recorded and restored, or explicitly excluded from the supported tuning workflow.

Comparing these settings directly, or a build-time digest of them, would detect changed configuration without reading binaries or invalidating entries because an unrelated kernel changed. For example, a changed GSU default could reject the record even when the main kernel name stays unchanged. This would still accept identical settings compiled into different code after a generator/compiler change. Explicit enumeration and hashing are independent choices: enumeration defines what is compared; a hash is a compact representation of that information. A metadata-only digest has the same coverage as the metadata it encodes.

### Build-time fingerprint follow-up

The [prototype branch](https://github.com/newling/rocm-libraries/tree/users/jnewling/hipblaslt-solution-fingerprint-prototype), introduced in [6e797f00b66](https://github.com/newling/rocm-libraries/commit/6e797f00b66d9f3a8a9c90b7b5516d6841f0ac72), adds a fingerprint of serialized solution defaults, the main compiled code-object bundle, all generated helper binaries for the architecture, and the target architecture including stepping when present. Index, library-logic index, ranking estimates and the fingerprint itself are excluded from the serialized-state input. Dictionary ordering and installation paths do not affect the result. Each code-object file is hashed once during device-library generation; replay only compares the stored value after resolving the saved index. There is no runtime hashing or index relocation.

This catches changes that names conceal: the metadata demonstration changed WGMXCC from 1 to 8, retained both names, and produced a different fingerprint. Python fingerprint tests, CPU parser tests including ASAN/UBSAN, both C++ MessagePack loading paths, and host/benchmark/replay-test compilation passed. The metadata demonstration used synthetic artifact bytes and did not execute GPU kernels; full device-library/GPU qualification remains outstanding for the toolchain reasons above.

The stronger check has costs. Any changed kernel in a shared code-object bundle can invalidate other solutions, and binary differences need not imply a meaningful behavioral difference. New records require regenerated fingerprinted device metadata, and explicit split-K/WGM tuning overrides are not recorded because replay cannot restore them. Fingerprinted rows require a recognized matching fingerprint rather than falling back to names; existing tuning files retain the PR's weaker rules. Older readers ignore the new column and do not acquire the stronger guarantee. The prototype assumes metadata and device binaries are deployed together; it does not verify installed bytes at runtime.

Host-dispatch behavior, runtime overrides, driver behavior and operating conditions remain outside the fingerprint. Even identical device code cannot establish equal performance across those changes. A broader contract could add a host compatibility identity and recorded/restored effective settings, but should state its supported environment rather than promise universal equivalence. Finding an equivalent solution at a moved index is another independent extension.

A local build-time sample hashed 21 installed artifacts totaling 55.3 MiB in 61 ms. Runtime compares a 74-character versioned value. This illustrates where the cost falls; it is not a full device-library build benchmark. The prototype's [contract and limitations](https://github.com/newling/rocm-libraries/blob/ffcc971c6bd69ddf5b246929fd14023f5cf8810f/projects/hipblaslt/docs/conceptual/solution-fingerprint-prototype.md) are documented separately, and its additional line changes are recorded above.

### Bundle granularity and more selective fingerprints

There is no fixed number of kernels per bundle. In an installed ROCm 7.1 gfx942 library, 673 main bundles had between 1 and 2,913 distinct main kernel names, with median 71 and 90th percentile 611. These counts came from each bundle's matching metadata; unbundling the largest confirmed 2,913 defined kernel descriptors. The shared helper `.hsaco` contained 2,387 kernels. These are installed-library observations, not counts from a newly built prototype. They demonstrate why whole-bundle hashing can reject many unaffected solutions.

An individual solution has far fewer active dependencies. The current Tensile single-GEMM dispatch path in `ContractionSolution.cpp` has one main call and three optional helper stages: beta initialization, output conversion/reduction, and bias-gradient reduction. The helpers can share one physical file. Build-time helper enumeration already exists in `KernelHelperNaming.py`, and `getKernelNameFromData` joins the actual invocation names; the submitted PR deliberately records the main name from the algorithm accessor. Enumerating all possible helper variants for a solution can include more kernels than one particular GEMM launches. Generated activation support functions and headers are compiled into helpers rather than necessarily being extra launches.

A more selective fingerprint could cover the serialized settings and only the solution's enumerated device dependencies. Compiled identities must include kernel descriptors, constants and referenced device routines, not just instruction bytes. Per-kernel build artifacts could make that practical, but the shared helper compilation means it is additional generator/build work, not a trivial change to hash a symbol. It would remove unrelated bundle invalidation while retaining sensitivity to relevant code changes; it would not remove host/environment limitations.

### Alternatives and their tradeoffs

| Approach | Benefit | Remaining limitation or cost |
| --- | --- | --- |
| Name plus explicit solution fields, or a metadata-only digest | Detects changed configuration; avoids binary processing and bundle-wide invalidation | Identical settings can generate different code; completeness/schema must be maintained |
| Settings plus all relevant kernel names | Also covers helper selection beyond the main name | A main or helper implementation can change without its name changing |
| Settings plus per-kernel generated source/assembly hashes | Detects generator-output changes without depending on bundle layout | Must include generated support code and relevant dependencies; does not identify compiler-induced code differences |
| Settings plus per-kernel compiled-content fingerprints | Detects changed device implementation with less unrelated invalidation | Requires complete dependency capture and more build integration; byte changes can still be harmless |
| Explicit compatibility versions | Small representation; maintainers can preserve compatibility across harmless changes | Relies on correct version updates and a clearly owned compatibility policy |

All proposed hashing can happen at build time. Manual compatibility versions trade automatic change detection for a maintained policy; hashing generated source trades detection of compiler output changes for more reuse. Neither is a way to obtain exact compiled-code identity while also ignoring arbitrary compiled-code changes. The field-based alternative is a plausible smaller follow-up; per-kernel fingerprints are a possible refinement if stronger device-code identity is needed. None of these alternatives is a prerequisite for the submitted PR's bounded improvement.

### Validation boundaries and handoff

The new integration tests assert which index the heuristic selects, which directly addresses this PR's behavior. Pure parser and map contracts would also benefit from host tests: they should not require a GPU or several heuristic candidates merely to exercise malformed input, index zero, or load-once behavior. The next store PR advertises that separation, but it is not evidence that these contracts are tested on this PR's own head. The unconditional production reset hook is another consequence of testing through the singleton; an internal host-testable store could avoid expanding that pattern.

The original rejection discussion was read as requested. The initial metadata fetch also included an existing #12585 review; the findings above are supported by the source and local probes rather than that review's conclusions. This review is published in the review repository and links both code branches, their commits and their reference pages. Each branch's reference page links back to this review and across to the other branch; the prototype design document also links to its reference page. Nothing has been posted as a PR comment or GitHub review. The prototype adds focused CPU parser tests; field-only identity, selective device fingerprints, restoring custom overrides, finding moved solutions, host/runtime compatibility and full GPU qualification remain follow-up work.

## Appendix: production-parser reproducer

Save the following as `parser_probe.cpp`. It links the parser object from a configured and built checkout; only logging is disabled. Run it against the submitted head and the suggestion branch with each build's own generated version header and parser object.

```cpp
#include "UserDrivenTuningParser.hpp"
#include <fstream>
#include <iostream>

// The real parser is linked unchanged; only its logging sink is disabled.
std::ostream* get_logger_os() { return &std::cerr; }
uint32_t get_logger_layer_mode() { return 0; }
const char* rocblaslt_layer_mode2string(rocblaslt_layer_mode) { return ""; }
std::string prefix(const char*, const char*) { return {}; }
#define STR_IMPL(x) #x
#define STR(x) STR_IMPL(x)

int main(int argc, char** argv)
{
    if(argc != 3) return 2;
    const std::string mode = argv[2];
    const bool torn = mode == "torn";
    {
        std::ofstream file(argv[1]);
        file << "Git Version: " << STR(HIPBLASLT_VERSION_TWEAK) << '\n';
        const std::string header = "transA,transB,batch_count,m,n,k,a_type,b_type,c_type,compute_type,solution_index";
        if(mode == "orphan") file << header << ",kernel_name\n";
        file << header;
        if(mode != "legacy") file << ",kernel_name";
        if(mode == "empty_trailing") file << ",unused";
        file << '\n';
        file << "N,N,1,1024,512,1024,f16_r,f16_r,f16_r,f32_r,12";
        if(!torn && mode != "legacy") file << ",recorded_kernel";
        if(mode == "empty_trailing") file << ',';
        if(!torn) file << '\n';
    }
    TensileLite::getContractionProblemsFromFile(argv[1]);
    TensileLite::ProblemOverride key(false, false, rocisa::DataType::Half,
                                    rocisa::DataType::Half, rocisa::DataType::Float,
                                    rocisa::DataType::Half, 1024, 512, 1024, 1);
    const auto entries = TensileLite::OverrideMap::getMap().find(key);
    std::cout << "loaded=" << entries.size();
    if(!entries.empty())
        std::cout << " index=" << entries[0].solutionIndex
                  << " named=" << entries[0].kernelName.has_value();
    std::cout << '\n';
    return entries.size() == (torn ? 0 : 1) ? 0 : 1;
}
```

Configure with `CMAKE_EXPORT_COMPILE_COMMANDS=ON` and build `hipblaslt`. This script reuses the parser's real include paths, definitions, and compiler options:

```bash
python3 - "$BUILD_DIR" parser_probe.cpp <<'PY'
import json, pathlib, shlex, subprocess, sys
build = pathlib.Path(sys.argv[1]).resolve()
probe = pathlib.Path(sys.argv[2]).resolve()
commands = json.loads((build / 'compile_commands.json').read_text())
entry = next(x for x in commands if x['file'].endswith('/UserDrivenTuningParser.cpp'))
args = shlex.split(entry['command'])
obj = build / args[args.index('-o') + 1]
args.remove('-c')
args[args.index(entry['file'])] = str(probe)
exe = build / 'parser-probe'
args[args.index('-o') + 1] = str(exe)
args += ['-x', 'none', str(obj)]
subprocess.run(args, cwd=build, check=True)
for mode in ('complete', 'torn', 'legacy', 'orphan', 'empty_trailing'):
    result = subprocess.run([str(exe), str(build / 'probe.tuning'), mode],
                            capture_output=True, text=True)
    print(mode, result.returncode, result.stdout.strip())
PY
```

On the submitted parser, `torn` returns 1 and prints `loaded=1 index=12 named=0`; after the fix it returns 0 and prints `loaded=0`. The other four modes pass on both versions.
