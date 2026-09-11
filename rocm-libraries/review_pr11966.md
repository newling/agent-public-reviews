> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#11966](https://github.com/ROCm/rocm-libraries/pull/11966)

**Dependent PRs reviewed:** [ROCm/rocm-libraries#11967](https://github.com/ROCm/rocm-libraries/pull/11967), [ROCm/rocm-libraries#11968](https://github.com/ROCm/rocm-libraries/pull/11968), [ROCm/rocm-libraries#11969](https://github.com/ROCm/rocm-libraries/pull/11969), and [ROCm/rocm-libraries#11970](https://github.com/ROCm/rocm-libraries/pull/11970)

## Tests

Focused local selections covering the contract additions, crossover and ratchet logic, rejection harvests, and every new gfx942/gfx950 test in the terminal PR passed (528 passed, 2 skipped); all five per-PR diffs also pass `git diff --check`. The local compiler does not advertise the required gfx1250 ISA capabilities, so I used the public coverage job for those nodes.

The current public `TensileLite coverage / Linux` job for #11970 is red: 15 snapshots fail (14 set-cover gfx1250 nodes from #11968 and `test_s10_usef32xemulation_index_transpose_golden` from #11970). Applying the checked-in ratchet to that job's uploaded `coverage.json` exposes a second failure that CI did not reach: `Tensile/Components/PackData.py` measures 85.04% against an 89.06% floor.

A focused tox 4.61.4 probe confirmed that #11967's `ignore_errors = true` continues into artifact generation while retaining the first command's nonzero final status. A separate semantic counterexample against #11970 is included below; both tests in the affected module still passed after replacing their targeted conversion instruction with a no-op move.

## Summary

The stack's broad shape makes sense: consolidate direct mutation-driven contracts, make coverage publication reliable, harvest additional configurations, fix the one production failure found by the harvest, and finally lock in the larger code-generation coverage gain. The first PR's direct state, serialization, error, and copy-semantics assertions are particularly useful, and the measure/gate split in #11967 behaves correctly.

The terminal layer is not yet a trustworthy characterization net, however. Most of its tests prove that selected code is reachable and that generation returns zero, but do not observe the emitted behavior named in their docstrings. At the same time, their filename-hash snapshots are sensitive to unrelated solution-state changes and are already failing in current CI. The stack therefore has the undesirable combination of false negatives for real code-generation bugs and false positives for unrelated branch drift. The late MX guard and incomplete coverage rebaseline add two more correctness concerns that should be resolved before relying on the new floors.

## Actionable items

1. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/test_s11a_prolog_alpha_before_loadc_packe_char.py:44-62`, `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/test_setcover_gemm_char.py:77-88`, and the analogous new emit tests in #11970 — assert the emitted behavior that each test claims to characterize.**

   The smoke assertions check only that a kernel exists, returns `err == 0`, and has a plausible target directive. The saved result then drops `src` and records only `{basename, err}`. `config_harness.py:246-253` computes the basename before `processKernelSource` emits the assembly, so the basename cannot detect an incorrect instruction sequence in the emitter.

   This is not only theoretical. In the S11a path I replaced the targeted `VCvtI32toF32` at `Tensile/Components/GlobalWriteBatch.py:980` with a same-register `VMovB32`. That removes the required integer-to-float conversion while keeping generation successful and line coverage unchanged; both `test_s11a_*` tests still passed. Conversely, current CI has 15 name-only mismatches even though the corresponding emission checks pass, and the existing ADRs already record earlier waves of basename-only churn.

   Add a narrow, canonical semantic projection per case—for example the relevant opcode sequence, instruction count/order, derived state, or rejection diagnostic. A full assembly snapshot is unnecessary, but `{basename, err}` should be treated as an emission/identity smoke test rather than the behavioral golden. The zero-survivor cases such as `test_s08_assignderivedparameters_enablema_char.py:45-61` also need to assert the intended rejection reason or validator boundary; snapshotting the integer `0` merely repeats the preceding assertion and would pass if an unrelated earlier reject removed every solution.

2. **`projects/hipblaslt/tensilelite/Tensile/Components/LocalRead.py:622-631` — reject the unsupported MX layout during solution derivation instead of admitting a valid solution that aborts code generation.**

   #11969 converts the accidental divide-by-zero into a descriptive generic exception, but `test_mx_umlds0_char.py:54-66` confirms that the configuration remains valid through `_generateForkedSolutions` and then throws from `processKernelSource`. In a normal multi-solution generation this exception aborts the generation operation rather than filtering the unsupported candidate through the existing `reject(state, ...)` mechanism.

   Add the layout constraint to `Solution.assignDerivedParameters` or the relevant MX validator, with a focused test that the candidate is invalid and emits the intended rejection reason. Keeping a defensive assertion in `localReadMX` is reasonable, but it should be unreachable for an ordinarily derived solution. The three #11970 tests that intentionally execute unrelated emitter blocks before this exception (`test_s00_macroandsetimplclassic_mx_scale_char.py:50-62`, `test_s07_mx_block_scale_mxblocka_mxblockb_char.py:48-62`, and `test_s10_enableldstr_wmma_v3_fp4_fp6_lds_char.py:47-59`) should not ratchet coverage obtained only on the way to an accepted code-generation crash; replace them with direct component tests or document those branches as unreachable until the layout is implemented.

3. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/_codegen/config_harness.py:121-156` — identify the selected `BenchmarkProblems` entry explicitly.**

   The set-cover cases pass a file path and architecture, but the harness silently consumes only `benchmarkProblems[0]`. At the reviewed head, 57 of the 75 configurations listed by the three set-cover tests contain multiple `BenchmarkProblems` entries (some contain as many as 12). The saved node therefore does not establish which problem group supplied the advertised coverage and ignores the rest of a file whose name is presented as the test case.

   Add an explicit problem index or stable selector to each case, include that selector in the test ID/saved result, and assert that the selected group exists. If the set-cover calculation intended to cover the whole YAML, iterate the entries with a clearly stated per-file cap instead. This also prevents an unrelated reorder or insertion at the front of a shared `Tests/common` YAML from silently changing which behavior is measured.

4. **`projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/adr/0018-rebaseline-coverage-after-develop.md:9-29` and `projects/hipblaslt/tensilelite/Tensile/Tests/unit/characterization/coverage-baseline.json:6-118` — make the baseline reduction match its evidence, then regenerate it against the merge result that will actually land.**

   The ADR says nine floors were lowered and names six unchanged files plus three changed files. The actual parent-to-head baseline diff lowers ten floors. `KernelWriterAssembly.py`, one of the three named changed files, rises from 81.88% to 83.66%; the two large reductions that are not named are `Configuration.py` (99.25% to 92.53%, line 76) and `Solution.py` (76.77% to 73.02%, line 106). Those are also central targets of this mutation-testing stack, so silently weakening their floors is especially concerning.

   Reproduce and explain every reduction or retain the previous floor. After doing that, rebase/restack and regenerate from the actual merge tree: the latest public artifact is already below the checked-in `PackData.py` floor by 4.02 percentage points. Fix the 15 snapshot failures first so the normal coverage-gate step runs, rather than merely updating the baseline from a test run that is currently red.

5. **The 40 new `test_s*_char.py` modules in #11970 — remove the repeated harness and duplicate generation passes.**

   Thirty-one modules repeat the same two-test pattern: call `emit_kernels_from_config`, check generic success properties, call the same expensive function again, then hand-copy the `{basename, err}` transformation already available as `config_harness.golden_digest` (`config_harness.py:347-352`). The PR adds 2,437 lines of Python test code, 36 separate snapshot files, and 67 calls to `emit_kernels_from_config`; a representative two-test module took about 39 seconds locally because it generated the same kernel twice.

   Put the ordinary emit cases in one or a few stage-grouped parameter tables, run each case once through a fixture/helper, and keep only genuinely custom tests—specific rejection, state, or opcode assertions—as separate functions. The detailed target rationale can remain table metadata or concise comments. This preserves independent pytest node IDs while substantially reducing execution time and the surface that must be edited when the harness contract changes.

## Suggestions

1. **`projects/hipblaslt/tensilelite/pyproject.toml:27-36` — raise the whole-project floor after the current coverage result is stable.** The final ADR reports 84.08% and current CI measures 84.15%, but `fail_under` remains 75%. Per-file floors do not protect a newly added source file until the next baseline update, so a one-to-two-point margin below the stable result would provide the backstop described in the repository documentation without leaving roughly nine percentage points of unratcheted space.

## Commentary

The direct contract tests in #11966 are well chosen: they exercise ownership/copy behavior, nested configuration access, range preservation, serialization shape, boundary values, and explicit diagnostics rather than merely adding broad integration coverage. The focused local selection passed cleanly.

#11967's separation of measurement from enforcement is also sound. The explicit coverage-gate step keeps Jenkins's upload-only consumer separate, and the tox probe confirms that continuing after a failed test does not turn the environment green. The per-call warm-up change in #11970 is directionally sensible for isolating scheduler state, although it cannot stabilize a basename that changes because solution state or the base branch changes.

The main design correction is to keep three concepts distinct: reachability coverage, stable characterization assertions, and generation-validity checks. The current top layer blends them together. Once each test observes the behavior it names, the large configuration corpus becomes useful evidence rather than mostly a coverage-number ratchet.

## Appendix: semantic counterexample

The following temporary one-line change was applied at the reviewed stack head and then removed:

```diff
- module.add(VCvtI32toF32(dst=vgpr(srcRegName), src=vgpr(srcRegName), comment="Convert MI out reg to fp32"))
+ module.add(VMovB32(dst=vgpr(srcRegName), src=vgpr(srcRegName), comment="review probe: omit int32-to-fp32 conversion"))
```

The affected module still passed:

```text
pytest -q Tensile/Tests/unit/characterization/_codegen/test_s11a_prolog_alpha_before_loadc_packe_char.py
2 passed
```

The checkout was restored and verified clean afterward.
