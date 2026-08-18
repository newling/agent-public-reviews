This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#9672

**Commit reviewed:** `ae530b2824b7` (`test(rocjitsu): preserve race suite
assertion parity`), the current PR head.

**Review mode:** independent first review. I did not read existing GitHub
reviews, inline comments, or discussion threads.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is a draft, is labeled not ready for review, and is
still awaiting review.

The release, Clang ASan/UBSan, TSan, formatting, package, and final TheRock
summary checks pass. The GCC ASan/UBSan job failed outside the touched
subsystem: its gfx1250 DBT corpus completed 19,997 cases, xfailed one known
memory-limit case, and timed out translating two code objects after 180 seconds
each. The Systems PR Bot also fails because the PR description has no valid
issue or ticket reference.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target race_suite_runner race_suite_runner_test \
           race_suite_gfx950_non_lds_target \
           race_suite_gfx950_lds_target \
           race_suite_gfx1151_non_lds_target \
           race_suite_gfx1151_lds_target \
  --parallel 8
```

Result: all 288 build steps passed in 157.50s real, 1186.21s user, and
37.78s sys. This build reconfigured the existing build tree and rebuilt broad
rocJitsu dependencies before compiling the four grouped HIP programs.

**Submitted race-suite tests:**

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure -L race-suite
```

Result: 43/43 passed, 0 failed, 0 skipped, and 0 errored in 4.27s real,
1.71s user, and 1.93s sys. This comprises the 42 preserved public
`RaceTest.*` names plus `RaceSuite.runner_unit`.

**Clean-case identity counterexample:**

I invoked the registered gfx950 VGPR-safe case but changed only the runtime
driver argument to the SGPR-safe case. I left the expected case ID and selected
static kernel set claiming that this was the VGPR case:

```bash
time -p $BUILD_DIR/tests/race-detector/race_suite_runner \
  --launcher $BUILD_DIR/tools/rocjitsu/rocjitsu \
  --config \
    $BUILD_DIR/tests/race-detector/race_suite_output_gfx950_vgpr_waitcnt_safe/config.json \
  --driver $BUILD_DIR/tests/race-detector/race_suite_gfx950_non_lds \
  --driver-argument sgpr_waitcnt_safe \
  --case vgpr_waitcnt_safe \
  --expectation-source \
    $SRC_DIR/tests/race-detector/race-suite/gfx950/non_lds_cases.hip \
  --sink-dir \
    $BUILD_DIR/tests/race-detector/race_suite_output_gfx950_vgpr_waitcnt_safe \
  --kernel vgpr_no_race_kernel
```

Result: exit status 0, `matched_expectations: 2/2`, and `score: 1` in
0.25s. The runtime executed `sgpr_no_race_kernel`, while the registration still
claimed that the case and static-analysis target were
`vgpr_waitcnt_safe`/`vgpr_no_race_kernel`. With no native findings, the runner
never consults the selected-kernel set.

**Unattributed common-expectation counterexample:**

I temporarily added the regression test reproduced in the appendix, rebuilt
`race_suite_runner_test`, ran only that test, and removed the probe afterward.
It loads the actual common expectations for `multi_kernel_race` as a future
Waitcheck adapter would see them, then supplies a finding attributed to
`clean_kernel_a` instead of `racy_kernel`.

Result: the test failed because
`missing_expectations(normalized, expected).empty()` was true. The common
contract required only `status: detected` and `access_pair: RW`; the unrelated
kernel still satisfied the case. The submitted source has 42 case blocks,
including 23 positive cases, but zero common `kernel:` checks and zero common
`domain:` checks.

**Domain probe:**

```bash
ctest --test-dir $BUILD_DIR -V \
  -R '^RaceTest\.gfx950_lds_cross_wave_race$'
```

Result: the test passed, but its normalized output described the cross-wave LDS
race as `domain: isa_async_hazard`. That domain is hard-coded for every record,
including workgroup memory races.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files <all existing changed rocJitsu files>
git diff --check $(git merge-base HEAD origin/develop)..HEAD
```

Result: all applicable pre-commit hooks passed and `git diff --check` passed.
After removing the temporary probe, `RaceSuite.runner_unit` rebuilt and passed.
At the end of the independent review pass, the reviewed source checkout had no
tracked modifications.

I did not run broad DBT, HIP, or external corpus suites locally. The patch
changes the complete race-test harness, so I ran every submitted race-suite
test. The remaining questions are harness case identity, normalized-result
contracts, and process/log failure behavior, which broader unrelated suites
would not answer.

## Summary

This PR replaces two monolithic HIP/GoogleTest programs with four grouped,
standalone HIP programs and moves all tool assertions into an external C++
runner. The four programs contain 21 gfx950 non-LDS cases, 13 gfx950 LDS cases,
six gfx1151 non-LDS cases, and two gfx1151 LDS cases. A stable case ID selects a
host-side run function, while CMake separately records one or more kernel names
for diagnostic attribution and future static analysis.

The runner launches rocJitsu, requires a `race.log`, rejects findings attributed
to kernels outside the registered set, normalizes the native records, reads
small FileCheck-like directives from comments beside the kernels, and matches
the common plus rocJitsu-specific expectations. The common directive language
currently expresses only detected/not-detected status and unordered `RW`/`WW`
access pairs. The rocJitsu-specific layer retains the old exact count,
resource-space, instruction, dispatch, symbol, workgroup, wave, lane, and trace
checks where the deleted GoogleTests asserted them.

The concrete value already delivered is substantial for rocJitsu maintenance:

- the HIP programs no longer know about GoogleTest, `RJ_SINK_DIR`, `race.log`,
  or rocJitsu diagnostic wording;
- the duplicated gfx950/gfx1151 parsers and assertion helpers are replaced by
  one tested parser/normalizer/matcher;
- all 42 public CTest names and their functional safe-case oracles remain;
- cases can be invoked directly as `<grouped-program> <case-id>`;
- multi-kernel cases carry explicit selected-kernel sets;
- missing plugin output and diagnostics from unexpected kernels now fail
  closed; and
- the runner, grouped programs, expectation-bearing sources, configs, and
  CTest commands have install-tree plumbing.

The cross-tool claim is only partially delivered. No Waitcheck, ConSan, or
other-plugin adapter is present, and the currently portable contract cannot yet
prove that another tool found the intended problem. It has no common domain,
capability, completeness, or finding-attribution requirement; the supplied
matcher is also intentionally tied to rocJitsu's first native finding. The
patch is therefore a useful rocJitsu harness refactor and a credible adapter
foundation, but it does not yet provide demonstrated cross-tool validation.

The size reflects that distinction: the PR removes 1,654 lines, adds 3,017
lines, and is a net increase of 1,363 lines. It adds no new detector capability
or new hazard case. Its present-day return is separation of concerns,
preservation of product assertions, direct case execution, and a place for
future adapters.

A second detector is not needed in this PR. The refactor stands on its own if
the rocJitsu plugin-test harness is made internally fail-closed and easier to
extend. Before adding another adapter, the highest-value improvements are to
make one source-owned descriptor define each case, represent normalized results
as structured data rather than prefixed strings, distinguish malformed plugin
output from a clean result, and test the runner's process/log failure paths
without starting the simulator.

## Actionable items

### 1. Require the common positive contract to identify the intended finding and the correct domain

**Files:**

- `emulation/rocjitsu/tests/race-detector/race-suite/README.md:38-65`
- `emulation/rocjitsu/tests/race-detector/race-suite/race_suite_runner_lib.cpp:197-218`
- `emulation/rocjitsu/tests/race-detector/race-suite/gfx950/non_lds_cases.hip:25-44,365-379`
- `emulation/rocjitsu/tests/race-detector/race-suite/gfx950/lds_cases.hip:25-35`
- `emulation/rocjitsu/tests/race-detector/race-suite/gfx1151/non_lds_cases.hip:25-40`
- `emulation/rocjitsu/tests/race-detector/race-suite/gfx1151/lds_cases.hip:25-30`

Every positive `RJ-CHECK` block currently requires only:

```text
status: detected
access_pair: RW|WW
```

Kernel identity and all other attribution live under
`RJ-CHECK-ROCJITSU-RACE`. Consequently, a new adapter using the common contract
can pass a case by reporting any finding with the same access pair. This is
already concrete in `multi_kernel_race`: the runtime intentionally launches
both `clean_kernel_a` and `racy_kernel`, and the temporary regression showed
that an RW finding from `clean_kernel_a` fully satisfies the common case.

The same layer also emits the wrong domain for existing cases.
`normalize()` unconditionally writes `domain: isa_async_hazard`, so
`lds_cross_wave_race` and the other cross-wave LDS tests are labeled as
asynchronous ISA hazards rather than workgroup memory races. No common case
checks a domain, so this error is invisible to the suite.

Add source-owned common metadata that distinguishes at least the hazard domain
and intended finding attribution. For these cases, stable kernel identity is
already available and should normally be a common check; cases that need
finer attribution should carry stable producer/consumer site IDs or another
tool-neutral location. Match all finding-specific common fields against one
finding from the intended kernel/site. Do not infer the case domain globally
inside the rocJitsu normalizer; carry it from the case contract or normalize it
from evidence sufficient to distinguish wait hazards from cross-wave memory
races.

Add regressions proving that:

- `multi_kernel_race` rejects a finding from `clean_kernel_a`;
- an LDS cross-wave case emits the workgroup-memory-race domain;
- a VGPR waitcnt case emits the asynchronous-ISA-hazard domain; and
- adapters can declare a case unsupported rather than treating every positive
  case as part of their capability domain.

### 2. Bind the runtime case and selected static kernels through one source-owned descriptor

**Files:**

- `emulation/rocjitsu/tests/race-detector/race-suite/hip_case.hpp:17-40`
- `emulation/rocjitsu/tests/race-detector/CMakeLists.txt:93-180`
- `emulation/rocjitsu/tests/race-detector/race-suite/race_suite_runner.cpp:125-145`

Case identity is duplicated across three independent places:

1. the `RJ-CASE` comment block;
2. the `NamedCase` runtime table; and
3. the CMake registration's case ID and kernel list.

The runner checks `--kernel` only by iterating native findings. A clean case has
no findings, so no relationship is checked between the runtime function that
actually ran and the kernels that a future static adapter is told to analyze.
The focused counterexample ran `sgpr_waitcnt_safe` while claiming
`vgpr_waitcnt_safe` and `vgpr_no_race_kernel`; it still scored 1.

Make the grouped program expose a source-owned descriptor for each case,
containing its stable case ID and selected kernel names alongside the run
function. The runner should query or validate that descriptor before launch,
and static adapters should consume the same descriptor instead of a separately
typed CMake list. A small `--describe <case>` or `--list-cases` protocol would
be sufficient; this does not require a manifest or discovery framework.

Add a regression that deliberately pairs one safe runtime selector with a
different safe kernel list and requires the runner to reject it before
execution. Positive tests alone do not cover this contract because their
diagnostics incidentally expose the mismatch.

### 3. Separate portable finding matching from rocJitsu's legacy first-record assertions

**Files:**

- `emulation/rocjitsu/tests/race-detector/race-suite/README.md:67-75`
- `emulation/rocjitsu/tests/race-detector/race-suite/race_suite_runner_lib.cpp:221-259`
- `emulation/rocjitsu/tests/race-detector/race-suite/race_suite_runner_lib.cpp:261-291`
- `emulation/rocjitsu/tests/race-detector/race-suite/race_suite_runner_test.cpp:112-125`

`missing_expectations()` stops collecting candidate lines as soon as it reaches
the second finding. `expectations()` then combines common and tool-specific
directives into one flat vector, so the first-record policy applies to every
caller of the shared library.

That preserves the deleted rocJitsu tests' `records[0]` behavior, but it is not
a suitable portable finding contract. Another tool may report several valid
findings in a different order, with the intended finding later in its native
output. Conversely, as the previous item demonstrates, weak common checks can
be satisfied by an unrelated first finding.

Return common and tool-specific expectations separately. Match the common
finding-specific fields atomically against any one correctly attributed
finding, while retaining a dedicated rocJitsu strict mode that checks the first
native finding where legacy product parity requires it. Add tests for:

- the intended common finding appearing second;
- two findings that each satisfy only part of a common contract;
- an unrelated first finding followed by the intended finding; and
- the existing rocJitsu first-record assertion remaining strict.

This separation can be implemented and tested entirely with synthetic
rocJitsu logs; it does not require another detector.

## Suggestions

### 1. Finish the rocJitsu plugin-test harness before adding another detector

**Files:**

- `emulation/rocjitsu/tests/race-detector/race-suite/hip_case.hpp:17-40`
- `emulation/rocjitsu/tests/race-detector/race-suite/race_suite_runner.h:14-26`
- `emulation/rocjitsu/tests/race-detector/race-suite/race_suite_runner.cpp:21-165`
- `emulation/rocjitsu/tests/race-detector/race-suite/race_suite_runner_lib.cpp:16-299`
- `emulation/rocjitsu/tests/race-detector/race-suite/race_suite_runner_test.cpp:19-182`
- `emulation/rocjitsu/tests/race-detector/CMakeLists.txt:93-180`

No additional detector is necessary to validate this refactor. The current
rocJitsu path has enough contracts and failure modes to justify the framework.
I recommend the following implementation order.

**P0 — one case descriptor**

Replace `NamedCase {name, run}` with a source-owned descriptor containing:

```cpp
struct CaseDescriptor {
  std::string_view id;
  std::span<const std::string_view> kernels;
  HazardDomain domain;
  CaseFunction run;
};
```

Have each grouped program support a small `--describe <case>` operation that
prints or validates the ID, kernels, and domain without launching HIP. The
rocJitsu runner should compare that descriptor with its command-line
registration before execution. This resolves the clean-case mismatch without a
manifest or automatic discovery system and gives future adapters one
authoritative case contract.

**P0 — structured normalization**

Replace the internal `std::vector<std::string>` result with explicit types, for
example:

```cpp
struct NormalizedFinding {
  std::string kernel;
  std::string space;
  std::string access_pair;
  std::string producer;
  std::string consumer;
  // Product-specific context remains optional.
};

struct NormalizedResult {
  Status status;
  HazardDomain domain;
  std::vector<NormalizedFinding> findings;
};
```

Keep the current line-oriented output as a rendering format and keep the
directive language small. Matching structured fields first removes the need to
reparse prefixes, makes it impossible to combine fields from unrelated
findings accidentally, and gives domain and kernel attribution normal type
boundaries.

**P0 — explicit plugin-log outcomes**

`parse_races()` currently returns an empty vector for an unreadable input, while
the main program separately checks only file existence. Return an explicit
result that distinguishes:

- no log produced;
- log exists but cannot be read;
- malformed or unterminated `RACE` block;
- valid log with zero findings; and
- valid log with findings.

Only the fourth state should satisfy a clean case. Add parser tests for missing
`END_RACE`, malformed fields, a directory or unreadable path named
`race.log`, and a valid empty log.

**P0 — runner integration tests without the simulator**

The submitted unit tests cover parsing and matching, but not most of
`race_suite_runner.cpp`. Add a tiny fake launcher/helper executable that can
write a selected `race.log`, return a selected status, or terminate by signal.
Use it to test:

- unknown and missing command-line options;
- launcher exit failure and signal termination;
- absent, empty, malformed, and stale logs;
- diagnostics from an unexpected kernel;
- one and multiple valid findings;
- cleanup of the prior sink/runtime directories; and
- the safe-case runtime/kernel mismatch reproduced in this review.

These tests should run in milliseconds and exercise the plugin-test harness
directly, without adding another detector or invoking full GPU simulation.

**P1 — registration and contract audit**

Add one focused `RaceSuite.registration` test that queries the four grouped
programs and verifies that every source-owned descriptor has exactly one
`RJ-CASE` block and one CMake registration, and that the registered kernels and
domain match. Also validate simple directive invariants: exactly one status,
no empty checks, and a positive rocJitsu case must identify at least its
expected kernel and resource space.

This is a consistency test, not automatic case discovery. Explicit CMake
registration can remain because it makes public test names, configs, and
timeouts visible.

### 2. Add valid issue tracking and describe the delivered scope in the PR body

**File:** PR description

The Systems PR Bot fails because the description has no issue or ticket
reference. Add a specific tracking issue, or use the project's documented
generic rocJitsu execution-plugin parent issue when no narrower issue exists:
`Related: #9577`.

The body should also record the delivered scale and boundary: all 42 existing
HIP race tests are migrated; the rocJitsu adapter is implemented; other tool
adapters, capability selection, and score aggregation are follow-up work. That
would make the substantial internal value visible without implying that a
cross-sanitizer comparison is already runnable.

### 3. Keep the framework deliberately specific and small

**Files:**

- `emulation/rocjitsu/tests/race-detector/race-suite/README.md:77-100`
- `emulation/rocjitsu/tests/race-detector/race-suite/race_suite_runner.cpp:109-165`
- `emulation/rocjitsu/tests/race-detector/CMakeLists.txt:47-71`

`race_suite_runner` is not tool-neutral: it launches rocJitsu, sets
rocJitsu-specific environment variables, requires `race.log`, parses the native
rocJitsu format, and hard-codes `tool: rocjitsu-race`. A name such as
`rocjitsu_race_suite_runner` would make the boundary clearer. The expectation
parser and generic matching model can remain in a small shared library once
the portable and product-specific matching policies are separated.

Do not add a manifest, schema dependency, automatic discovery mechanism,
regular-expression language, score aggregation, or adapter plugin framework in
this PR. A source-owned case descriptor, structured result types, and focused
failure-path tests address the current maintenance risks without turning the
test refactor into a testing platform.

## Commentary

| Claimed or implied value | What the patch actually provides | Assessment |
| --- | --- | --- |
| Tool-neutral HIP cases | Standalone grouped programs selected by stable case ID, with no embedded log parser or GoogleTest assertions | Strongly delivered |
| FileCheck-like expectations beside the code | Three deliberately small directives, exact scalar matching, and instruction-field substring matching | Delivered and appropriately restrained |
| Preserve existing rocJitsu coverage | All 42 public names remain; focused tests pass; functional safe-case checks and strict diagnostic assertions are retained | Strongly delivered |
| Let static and runtime tools select one case | Runtime dispatch and a CMake-selected kernel set exist; host executables are suitable inputs for tools that can select one kernel | Partially delivered; metadata can drift for clean cases |
| Cross-tool semantic comparison | Common `status` and `access_pair`, plus a binary score | Intentionally deferred; first strengthen domain, attribution, completeness, and the rocJitsu runner |
| Generic runner | A dependency-free C++ executable | Not delivered; the executable is a rocJitsu-specific adapter |

The grouping choice is sensible for the named consumers. Runtime tools execute
only the selected case, and a final-ISA checker that accepts a host executable
and one kernel entry can ignore dormant kernels in the same code object. This
does not make the source universally isolated for every possible static
analyzer, but it avoids compiling 42 separate HIP translation units while
serving the tools identified by the PR.

Keeping common expectations deliberately weaker than rocJitsu product checks
is also the right direction. The issue is not that every wave, lane, register,
or exact count should become portable. The issue is that the portable minimum
has become weaker than a valid detection oracle: it currently says only that
some finding with the same unordered access pair existed. Domain and intended
site attribution are the minimum additions needed to turn the refactor into a
meaningful cross-tool suite.

## Implementation update

Following the review, the requested plugin-test refactor improvements were
implemented in the working tree on top of the reviewed head. No second detector
was added.

The implementation now provides:

- a source-owned `CaseDescriptor` for every case, containing the stable case
  ID, selected kernels, hazard domain, and runtime function;
- `--describe <case>` and `--list-cases` modes on every grouped HIP program;
- exact pre-launch validation between each CMake registration and the program
  descriptor;
- one runtime selector: the runner always launches its validated `--case` ID,
  so the earlier independent `--driver-argument` mismatch is no longer
  representable;
- structured `NormalizedResult` and `NormalizedFinding` types, with the
  line-oriented output retained as a rendering format;
- explicit missing, unreadable, malformed, valid-empty, and valid-with-finding
  plugin-log outcomes;
- common `domain:` metadata for all 42 cases and a common intended `kernel:`
  check for all 23 positive cases;
- common finding checks matched atomically against any one complete finding,
  while rocJitsu-specific legacy checks remain scoped to the first native
  finding;
- a renamed `rocjitsu_race_suite_runner` executable that makes the
  tool-specific boundary explicit;
- a fake launcher and fake case driver covering process, signal, cleanup, log,
  descriptor, and kernel-attribution failure paths without starting the
  simulator; and
- four registration audits comparing the program descriptors, source
  `RJ-CASE` blocks, and CMake registrations, while enforcing basic contract
  invariants.

Focused validation after implementation:

```text
RaceTest public cases:                 42
Runner unit/integration tests:          2
Registration audits:                    4
Complete race-suite result:         48/48 passed
Installed RaceTest generation:      42/42 present
Pre-commit:                          passed
git diff --check:                    passed
```

The previously misclassified gfx950 cross-wave LDS case now emits:

```text
domain: workgroup_memory_race
matched_expectations: 12/12
score: 1
```

The original clean-case counterexample depended on supplying an independent
`--driver-argument`. That option has been removed; attempting to use it now
fails as an unknown option, and the validated case ID is passed directly to the
grouped program.

## Appendix: temporary common-contract regression

The following test was added temporarily, failed on the reviewed head, and was
removed after validation:

```cpp
TEST(RaceSuiteRunnerReviewProbe, CommonContractRejectsUnrelatedFinding) {
  const auto source =
      std::filesystem::path(__FILE__).parent_path() / "gfx950" / "non_lds_cases.hip";
  const auto expected =
      rocjitsu::race_suite::expectations(source, "multi_kernel_race", "waitcheck");
  const std::vector<std::string> normalized{
      "tool: waitcheck",
      "status: detected",
      "finding: 0",
      "access_pair: RW",
      "kernel: clean_kernel_a",
  };

  EXPECT_FALSE(
      rocjitsu::race_suite::missing_expectations(normalized, expected).empty());
}
```

Observed failure:

```text
Value of: missing_expectations(normalized, expected).empty()
  Actual: true
Expected: false
```
