This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** [ROCm/rocm-systems#9328](https://github.com/ROCm/rocm-systems/pull/9328)

**Commit reviewed:** `f28881503ee8` (`parametrize vgpr granule by wave32 or
wave64`), the current PR head.

**Review mode:** independent first review. I did not use existing review
threads or discussion as review input.

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is not a draft, and GitHub reports it as mergeable
with review still required. The release, Clang ASan/UBSan, GCC ASan/UBSan,
TSan, pre-commit, gfx94X/gfx950 package, TheRock summary, and HIP NVIDIA
summary checks pass. The remaining failed check is the Systems PR Bot's
`Enforce policy` step rather than a build or test job.

The active checkout contained unrelated files, so I exported the public PR
commit into a disposable source snapshot rather than switching that checkout.

**RelWithDebInfo configuration:**

```bash
time -p cmake -S $SRC_DIR/emulation/rocjitsu -B $BUILD_DIR -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_C_COMPILER=$ROCM_PATH/lib/llvm/bin/clang \
  -DCMAKE_CXX_COMPILER=$ROCM_PATH/lib/llvm/bin/clang++ \
  -DBUILD_TESTING=ON
```

Result: configuration and generation passed in 15.53s real, 7.76s user, and
1.11s sys.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: all 568 build steps passed in 462.68s real, 3333.92s user, and
96.53s sys.

**Submitted Python profile and property-codegen coverage:**

```bash
time -p env PYTHONPATH=$SRC_DIR/emulation/rocjitsu/lib/python \
  $PYTHON -m pytest -q \
  $SRC_DIR/emulation/rocjitsu/lib/python/amdisa/tests/test_profile_properties.py
```

Result: 107/107 passed, 0 failed, 0 skipped, 0 errored. Pytest reported
0.38s; `time -p` reported 0.58s real, 1.60s user, and 0.05s sys.

**Configuration-consumer and submitted descriptor coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='ConfigLoaderTest.*:KernelDescriptorTranslator.Gfx1250UsesWave32SixteenVgprGranularity'
```

Result: 24/24 passed, 0 failed, 0 skipped, 0 errored in 0.63s real,
0.09s user, and 0.53s sys.

**CDNA2 descriptor counterexample:**

The repository already contains
`tests/dbt/device_kernels_translate_tests.cpp`, guarded internally by
`HAS_DEVICE_KERNELS`, but the file is not added to any CMake target. In the
disposable snapshot I temporarily added that existing file to
`rocjitsu_tests` under the existing `if(HAS_DEVICE_KERNELS)` block and built
the target again:

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests --parallel 8
```

Result: all 165 invalidated build steps passed in 98.73s real, 694.00s user,
and 21.68s sys.

I then ran its existing cross-architecture descriptor regression:

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='KernelDescriptorTranslator.CdnaAccVgprExpansionGrowsUnifiedVgprAllocationForRdna4'
```

Result: 0/1 passed, 1 failed, 0 skipped, 0 errored in less than 0.01s real.
The CDNA2 iteration reported:

```text
guest_agpr_count:              actual 0,  expected 64
target_vgpr_count:             actual 64, expected 128
target_vgpr_allocation_count:  actual 64, expected 128
target_vgpr_granulated:        actual 15, expected 31
```

The CDNA3 and CDNA4 iterations did not report failures. This is a genuine PR
regression: the submitted CDNA2 property changes descriptor decoding from the
previous eight-register granule to four.

I prototyped setting the CDNA2 Wave64 descriptor granule to eight and removing
the contradictory RDNA2 Wave64 prohibition from the Python profile. Invoking
`emit_isa_properties()` over all ten AMDGPU profiles then reproduced every
submitted property value; only clang-format's line wrapping differed. The
temporary source and build-list changes were removed afterward.

**Diff hygiene:**

```bash
git diff --check <pr-base>..HEAD
```

Result: passed.

I did not run the full local corpus. The public release and sanitizer corpus
jobs are green, while the focused checks above exercise the changed profile,
generated-table, configuration-consumer, and descriptor-consumer contracts.

## Summary

This PR moves AMDHSA VGPR-count encoding granules into the Python ISA profiles
and emits separate Wave32 and Wave64 values into the shared runtime
`IsaProperties` table. A new lookup helper selects the granule from an
architecture and wavefront size.

The DBT kernel-descriptor translator now uses that generated lookup when
decoding the guest's `GRANULATED_WORKITEM_VGPR_COUNT` and re-encoding the host
descriptor. The simulator configuration loader uses the same property with
the architecture's default wave size when configuring the command processor.
The intended result is one generated source of truth replacing two local
architecture tables.

That consolidation exposes a pre-existing disagreement: the command processor
used four for CDNA2, while the descriptor translator used eight for every
CDNA architecture except CDNA1. The PR resolves the disagreement in favor of
four, but GFX90A's descriptor encoding uses eight and the change breaks
AccVGPR-aware descriptor translation. A second disagreement remains inside
the new source of truth: the Python RDNA2 profile says Wave64 is unsupported,
while the checked-in generated table and C++ ISA trait say it is supported.

## Actionable items

### 1. Keep the GFX90A/CDNA2 descriptor granule at eight

**Files:** `emulation/rocjitsu/lib/python/amdisa/isa_profile.py:1167-1176`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/isa_properties.h:45-55`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/dbt/kernel_descriptor_translator.cpp:701-709`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/config/config_loader.cpp:423-429`,
`emulation/rocjitsu/tests/dbt/device_kernels_translate_tests.cpp:339-368`

`Cdna2Profile.descriptor_vgpr_count_granule_wave64` is four, but GFX90A uses
an eight-register `GRANULATED_WORKITEM_VGPR_COUNT` encoding granule. LLVM's
`AMDGPUBaseInfo.cpp::getVGPREncodingGranule()` returns eight whenever
`FeatureGFX90AInsts` is present, and the replaced DBT helper likewise returned
eight for CDNA2/3/4.

The difference is observable before any instruction translation. With
`GRANULATED_WORKITEM_VGPR_COUNT = 15`, the original code decodes 128 unified
VGPRs. The submitted property decodes 64. If `ACCUM_OFFSET = 15`, the
accumulator bank begins at unified index 64; the submitted result therefore
concludes that there are no AccVGPRs and emits a target allocation of only 64
registers. The existing regression described in Tests demonstrates the
resulting lost 64-register AccVGPR window.

Set the CDNA2 Wave64 descriptor granule to eight and regenerate
`isa_properties.h`. Because the two old consumers disagreed, this will also
change the command processor from four to eight; that is the correct outcome
for interpreting the same AMDHSA descriptor field. Add direct CDNA2
command-processor coverage alongside the existing gfx1250 granule assertion.

Also register `device_kernels_translate_tests.cpp` when
`HAS_DEVICE_KERNELS` is true, or move this descriptor-only regression into an
always-built DBT test file. At present the exact invariant that catches this
bug is present in the repository but absent from both the test binary and CI.

### 2. Make the generated RDNA2 wave-size property reproducible

**Files:** `emulation/rocjitsu/lib/python/amdisa/isa_profile.py:1301-1312`,
`emulation/rocjitsu/lib/python/amdisa/isa_properties_codegen.py:44-48,59-63`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/isa_properties.h:93-104`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/rdna2/isa.h:71-76`,
`emulation/rocjitsu/lib/python/amdisa/tests/test_profile_properties.py:144-200`

`Rdna2Profile.wave_size_max` returns 32 and its docstring says Wave64 is
unsupported. The submitted generated header nevertheless records
`.wave_size_max = 64`, matching the C++ RDNA2 trait and its explicit comment
that `ENABLE_WAVEFRONT_SIZE32=0` selects Wave64.

Regenerating the header from all profiles changes the checked-in RDNA2 entry
from 64 to 32, so the file marked `AUTO-GENERATED` is not reproducible from
the submitted generator inputs. No current caller reads `wave_size_max`, but
the new shared property already publishes a contradictory architecture
contract and a future consumer will receive different behavior depending on
which source it uses.

Remove the RDNA2 override or otherwise make the Python profile report 64,
update its docstring, and regenerate the header. Extend
`test_isa_properties_codegen_uses_profile_values` to include RDNA2, preferably
by checking every entry in `_AMDGPU_ARCH_ORDER`, so profile/generated-table
drift cannot recur on an architecture omitted from the hand-selected test
matrix.

## Suggestions

### 1. Give unsupported lookup inputs release-build behavior

**Files:** `emulation/rocjitsu/lib/python/amdisa/isa_properties_codegen.py:107-116`,
`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/isa_properties.h:158-167`

The new helper uses zero to represent an unsupported architecture/wave-size
combination and protects that sentinel only with `assert`. With `NDEBUG`, an
unsupported input silently returns zero; a direct release-mode probe using
`ROCJITSU_CODE_ARCH_RV64I` returned zero. The descriptor translator currently
clamps that to one in its conversion helpers, while the command processor
stores zero directly, so misuse has caller-dependent consequences.

Return an optional/result, retain a documented nonzero fallback, or use the
project's release-active error path. Add direct tests for every supported
architecture/wave-size pair and for one unsupported pair. The current call
sites construct supported AMDGPU inputs, so this is primarily hardening the
new shared helper's contract rather than a blocker for those paths.

## Commentary

Centralizing these values is the right abstraction direction. The important
part is to resolve the old tables by descriptor ABI meaning rather than by
choosing whichever value one consumer happened to use. Once the CDNA2 and
RDNA2 disagreements are corrected, the generated profile table gives both
DBT and simulation a much clearer extension point for future architectures.
