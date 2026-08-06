This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#9328

**Commit reviewed:** `ce4288651510` (`Use optional instead of exception`), the
current PR head.

**Review mode:** comment-aware follow-up review. I read the full PR discussion,
the three substantive inline threads, the original independent review, and the
commits added after that review. I then checked each request against the current
implementation rather than treating replies, resolved state, or outdated state
as evidence.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, is mergeable, and still requires review.
The new CI run was mostly queued or in progress at the time of review. The PR
description still uses `N/A` for issue tracking, so it does not satisfy the
repository's issue-reference policy.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR --target rocjitsu_tests --parallel 8
```

Result: all 431 build steps passed in 160.65s real, 1192.77s user, and
55.62s sys. The build reconfigured first and compiled
`device_kernels_translate_tests.cpp`, confirming that the previously omitted
descriptor regression is now part of the test binary.

**Python profile and generated-header coverage:**

```bash
time -p env PYTHONPATH=$SRC_DIR/emulation/rocjitsu/lib/python \
  $PYTHON -m pytest -q \
  $SRC_DIR/emulation/rocjitsu/lib/python/amdisa/tests/test_profile_properties.py
```

Result: 110/110 passed, 0 failed, 0 skipped, and 0 errored. Pytest reported
0.33s; `time -p` reported 0.58s real, 1.69s user, and 0.05s sys. This includes
the new exact comparison between a complete ten-profile regeneration and the
checked-in `isa_properties.h`.

**Focused lookup and descriptor-consumer coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='IsaPropertiesTest.*:KernelDescriptorTranslator.CdnaAccVgprExpansionGrowsUnifiedVgprAllocationForRdna4:KernelDescriptorTranslator.RdnaWave64UsesAmdhsaDescriptorVgprEncoding:KernelDescriptorTranslator.Gfx1250UsesWave32SixteenVgprGranularity'
```

Result: 5/5 passed, 0 failed, 0 skipped, and 0 errored in 0.02s real,
0.02s user, and 0.00s sys. The cases cover the complete supported lookup
matrix, unsupported inputs, the CDNA2/3/4 AccVGPR translation regression, RDNA
Wave64's four-register descriptor granule, and gfx1250 Wave32's sixteen-register
granule.

**Formatting and diff hygiene:**

```bash
.venv/bin/pre-commit run --files <all eight changed files>
git diff --check <pr-base>...HEAD
```

Result: all applicable hooks passed and `git diff --check` passed. The reviewed
checkout has no tracked modifications.

I did not run the broad simulator or corpus suites locally. The changed
contracts are the generated property table, unsupported lookup behavior, DBT
descriptor conversion, and command-processor configuration; the focused tests
exercise the property and descriptor boundaries directly, while the current
public sanitizer and release jobs are still running.

## Summary

The current patch makes the Python ISA profiles the generated source of truth
for default and maximum wave size plus Wave32/Wave64 AMDHSA descriptor VGPR
granules. The generated C++ table exposes a constexpr optional lookup, allowing
unsupported architecture/wave pairs to be represented explicitly rather than
returning zero in release builds.

The DBT descriptor translator now uses that lookup for both source decoding and
target encoding. Unsupported pairs produce a translation diagnostic while
retaining deterministic best-effort counts for further diagnostics. The
command processor selects the granule for the simulator's architecture-fixed
default wave size. The patch also registers the existing device-kernel
translation test file, bringing its CDNA AccVGPR and RDNA Wave64 descriptor
regressions into the built test target.

All substantive review comments are addressed:

| Requested change | Current implementation | Assessment |
| --- | --- | --- |
| Keep CDNA2/GFX90A Wave64 at an eight-register descriptor granule | `Cdna2Profile` and the generated table use eight; the AccVGPR regression is now compiled and passes | Addressed |
| Resolve the RDNA2 Wave64 contradiction and make generation reproducible | RDNA2 inherits the RDNA1 maximum of 64, and a ten-profile exact round-trip test compares the generated and checked-in headers | Addressed |
| Give unsupported inputs release-build behavior | The helper returns `std::optional`; direct tests reject RISC-V and unsupported AMDGPU wave modes; callers handle absence explicitly | Addressed |
| Let DBT consume the shared values | Both guest decode and host re-encode use the generated wave-specific lookup | Addressed |

The GitHub thread metadata has not caught up with the code: two corrected
threads are still shown as unresolved and outdated, while the active RDNA2
thread is unresolved. That is only mechanical state; the requested behavior is
present and tested in the current head.

## Actionable items

None in the current code.

## Suggestions

### 1. Update the PR title and issue tracking before merge

**File:** PR title and description

The title still ends in `(NFC)`, but this patch intentionally changes the
command processor's CDNA2 descriptor decoding from a four-register granule to
the correct eight-register granule. That is a functional correction, even
though the broader refactor is source-of-truth consolidation.

Remove `(NFC)`, mention the CDNA2 correction and DBT sharing in the description,
and replace `N/A` with a valid issue or ticket reference. This will make the
delivered behavior clear and satisfy the repository policy check.

### 2. Add a direct command-processor assertion for CDNA2

**Files:**

- `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:40-45`
- `emulation/rocjitsu/tests/shared_infra_test.cpp:151-190`

The complete helper matrix and DBT consumers are tested, but the changed
command-processor consumer is covered only indirectly by inspection. Add a
small test that configures a `CommandProcessor` for CDNA2 and requires
`vgpr_granularity() == 8`. This is not needed to establish the current code's
correctness, but it would pin the specific functional correction that makes
the `(NFC)` label inaccurate.

## Commentary

The new code is sensible. Returning an optional from the generated helper is a
clean boundary: the data table represents unsupported pairs with zero, while
callers cannot accidentally consume that sentinel as a real granule. The
complete generated-header round trip is substantially stronger than the
previous substring sampling, and registering the dormant descriptor tests
closes the exact coverage hole raised during review.

DBT still has architecture switches for default-wave selection and supported
wave-size checks alongside the generated `wave_size` and `wave_size_max`
properties. Those switches currently agree with the table, and an unsupported
combination now fails safely through the optional lookup. Consolidating those
remaining switches could be considered later, but it is not necessary for this
PR.
