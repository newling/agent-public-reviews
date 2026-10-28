This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocjitsu-test-corpus#81](https://github.com/ROCm/rocjitsu-test-corpus/pull/81)

**Reviewed head:** `9ef6b2e0482577f919c88f44a8b8d0676d044b62`

**PR base:** `d3c5c82d35714a4759ce4bffe74987146b4a154d`

**Review branch:** [`review/pr81-suggestions`](https://github.com/newling/rocjitsu-test-corpus/tree/review/pr81-suggestions), based on the reviewed head. No additional commits. The scope decisions below require more than a bounded correction; I have not added an isolated runner or selected an oracle policy on the author's behalf. The accompanying branch contains the submitted head unchanged. No GitHub PR review or discussion comment has been posted.

## Tests

All five Guitar Hero executables build; 21 host contract tests pass; four complete emulator smokes and the CDNA4 prefix containing every added chain pass; both RDNA4 wave modes pass on matching hardware with seven workgroups, all three seeds, and three launches per seed.

The build uses ROCm SDK `10.1.0a20260812` and AMD Clang 23. Emulator results use a binary reporting rocm-systems revision `05dd35f51489f8604c1a42a425fb7af5b75aca40`. Its LeakSanitizer run reports allocations in ROCr signal/queue creation and libhsakmt after successful smokes. The successful emulator reruns use `ASAN_OPTIONS=detect_leaks=0`; they do not qualify leak freedom.

The complete CDNA4 smoke fails on both the PR and its base at an unchanged `buffer_store_format_d16_x`, with `unsupported operand value` followed by `HSA_STATUS_ERROR_EXCEPTION`. Reproduce with the matching SDK libraries on the search path:

```sh
ASAN_OPTIONS=detect_leaks=0 "$ROCJITSU" \
  --config "$SYSTEMS_SRC/emulation/rocjitsu/configs/gfx950_mi355x.json" \
  --cpu-thread-budget 8 -- \
  "$BUILD_DIR/cases/guitar-hero/guitar_hero_cdna4" \
  --groups 7 --seed-index 0
```

For the base comparison, assemble the base revision's CDNA4 source and supply its code object with `--code-object`. On the submitted head, adding `--stop-after-checkpoint 709` passes all 710 checkpoints through the last added CDNA4 chain. The full-run failure is an emulator limitation reproduced on unchanged code, not a demonstrated regression in this PR. Matching CDNA4/CDNA5 hardware was unavailable. Visible PR CI contains successful security checks but no functional qualification.

The separate mutation experiment in the appendix demonstrates a limitation of the shipped smoke; it is not included in the passing validation above.

## Summary

The change adds operand-format, address, memory-boundary, atomic-hint, scratch-offset, LDS-routing, and PC-import chains to four existing assembly sources. The RDNA4 source still builds in both strict wave modes. Intermediate results feed the rolling hashes before reuse, and the existing checkpoint IDs, allocation strides, runner interface, and manifest registrations remain intact.

Several choices help make these probes useful: memory consumers have backed, bounded addresses; waves use separate workspace regions; the RDNA4 LDS boundary tests select a single writer and synchronize before repartitioning; and the comments distinguish measured behavior from simulator assumptions. The buffer cases connect to the unusual gfx1250 partial-vector behavior described in [Triton #12512](https://github.com/triton-lang/triton/pull/12512), while also testing whole fits, residual byte boundaries, and nonzero address components.

I did not find a demonstrated assembly correctness defect in the paths inspected and exercised. The submitted implementation provides additional execution-smoke coverage. Its description promises additional regression-test infrastructure that is absent from this head.

## Actionable items

### Reconcile the promised isolated path with the submitted runner

Locations: `corpus/kernels/cases/guitar-hero/README.md:101`, `corpus/kernels/cases/guitar-hero/guitar_hero_cdna4/guitar_hero_cdna4.s:34395`; existing runner dispatch at `corpus/kernels/cases/guitar-hero/runner.hpp:90` and `:144`.

The PR description says it adds an isolated path with the same checkpoint IDs, so unrelated broad-sweep gaps do not hide later chains. The diff only inserts calls into the existing kernels. There is no new entry point, runner selection, or registered case for isolated execution. `--stop-after-checkpoint` still executes the entire preceding prefix.

This matters in practice: the full CDNA4 test fails on an unchanged formatted-buffer instruction in the available current emulator, even though the prefix covering the new chains succeeds. A caller cannot select a corner chain independently through the submitted interface.

Add and register the promised isolated path, document how its output/checkpoint contract relates to the full sweep, and test that it bypasses an unrelated failing sweep region. Alternatively, explicitly narrow the PR description to the execution-smoke additions actually submitted. I have not implemented this because entry-point selection, checkpoint handling, and registration require an agreed design; the review does not supply a replacement PR description.

### Reconcile the promised independent-oracle companions with smoke-only validation

Locations: `corpus/kernels/cases/guitar-hero/README.md:9`, `corpus/kernels/cases/guitar-hero/guitar_hero_rdna4/guitar_hero_rdna4.s:996`, `corpus/kernels/cases/guitar-hero/guitar_hero_cdna4/guitar_hero_cdna4.s:163`; existing workgroup comparison at `corpus/kernels/cases/guitar-hero/runner.hpp:171`.

The PR description promises independent-oracle companions for legacy half destinations, CDNA3 address/control consumers, and real CDNA4-to-CDNA3 BF16 translation. No such companions, expected-value checks, or translation launch configuration are added. The sources added here target gfx950, gfx1250, gfx1100, and gfx1201; the existing maintained ports do not themselves exercise a CDNA4-to-CDNA3 translation path.

The current harness compares each workgroup with group zero. As the README correctly explains, identical wrong results pass. On RDNA4 hardware, I replaced just the whole-fit B128 buffer load at `width=128`, `remaining=16`, `kind=0` with four zero writes. The workspace producer supplies four nonzero DWORDs, so this deliberately violates the load's result contract. The first changed digest was checkpoint 462, but the seven-workgroup smoke still exited successfully. The appendix preserves the exact mutation and setup.

If the claimed companions belong in this PR, add separately registered tests that check independently derived values and exercise the actual translation configuration; verify that a deliberate wrong result fails. Otherwise, correct the description's scope. This is a missing claimed feature, not an objection to retaining the documented smoke-only harness. I have not chosen or implemented the broader companion/oracle design in the review branch.

## Suggestions

### Reduce duplication in the new helper definitions

Locations: `corpus/kernels/cases/guitar-hero/guitar_hero_rdna4/guitar_hero_rdna4.s:25`, `corpus/kernels/cases/guitar-hero/guitar_hero_rdna3/guitar_hero_rdna3.s:28`, `corpus/kernels/cases/guitar-hero/guitar_hero_cdna4/guitar_hero_cdna4.s:36`, `corpus/kernels/cases/guitar-hero/guitar_hero_cdna5/guitar_hero_cdna5.s:19`.

The helper macros common to these files are identical apart from architecture-validation guards. Each copy also retains branches and encoding constants for targets that its own validation rejects. Consider sharing those definitions in a checked-in assembler include while keeping kernel bodies and target validation independent. If independent copies are intentional, a host contract checking their agreement would help prevent a later fix reaching only some targets. This is a larger maintenance choice, so no mechanical factoring commit is included.

## Commentary

Preserving checkpoint IDs helps downstream capture and diagnosis tools continue to identify regions. It does not preserve the old hash values: inserted folds deliberately change the rolling history from the first affected checkpoint onward. The updated raw-dump wording usefully explains why intermediate folded values cannot be recovered from the final v16–v31 dump.

The physical-qualification comments should remain. Passing group comparisons, assembler acceptance, and the emulator runs above do not establish every reserved-field rule or physical memory/scheduling behavior. The hardware runs cover the RDNA4 variants, while the comments explicitly leave several CDNA behaviors for matching hardware qualification.

## Appendix: exact whole-fit load mutation

This probe reads the submitted RDNA4 source, changes one expanded buffer case, and builds a wave32 code object. Set `SRC_DIR` to the corpus checkout, `BUILD_DIR` to its kernel build, `ROCM_PATH` to the SDK, and `PROBE_DIR` to a separate artifact directory. Run on matching gfx1201 hardware. The source checkout remains unchanged.

```python
from pathlib import Path
import os
import subprocess

src = Path(os.environ["SRC_DIR"])
build = Path(os.environ["BUILD_DIR"])
sdk = Path(os.environ["ROCM_PATH"])
probe = Path(os.environ["PROBE_DIR"])
probe.mkdir(parents=True, exist_ok=True)
source = src / "corpus/kernels/cases/guitar-hero/guitar_hero_rdna4/guitar_hero_rdna4.s"

needle = r"gh_corner_buffer_load \arch, \width, \kind"
replacement = r""".if (\width == 128) && (\remaining == 16) && (\kind == 0)
v_mov_b32 v16, 0
v_mov_b32 v17, 0
v_mov_b32 v18, 0
v_mov_b32 v19, 0
.else
gh_corner_buffer_load \arch, \width, \kind
.endif"""
text = source.read_text()
assert text.count(needle) == 1
mutated = probe / "wrong-full-fit.s"
mutated.write_text(text.replace(needle, replacement))
obj = probe / "wrong-full-fit.o"
hsaco = probe / "wrong-full-fit.hsaco"
subprocess.run([
    str(sdk / "lib/llvm/bin/amdclang"),
    "-target", "amdgcn-amd-amdhsa", "-mcpu=gfx1201",
    "-mno-wavefrontsize64", "-Wa,-defsym,GUITAR_HERO_WAVE_SIZE=32",
    "-x", "assembler", "-c", str(mutated), "-o", str(obj),
], check=True)
subprocess.run([
    str(sdk / "lib/llvm/bin/ld.lld"), "-shared", str(obj), "-o", str(hsaco),
], check=True)

env = os.environ.copy()
env.pop("LD_PRELOAD", None)
env.pop("HSA_HOTSWAP_ENABLE", None)
env["LD_LIBRARY_PATH"] = str(sdk / "lib") + ":" + env.get("LD_LIBRARY_PATH", "")
runner = build / "cases/guitar-hero/guitar_hero"
common = [str(runner), "--groups", "7", "--seed-index", "0", "--dump-digests"]
for name, extra in [("original", []), ("mutated", ["--code-object", str(hsaco)])]:
    result = subprocess.run(common + extra, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    rows = [line for line in result.stdout.splitlines() if line.startswith("1 ")]
    print(name, rows[462])
```

Observed checkpoint 462 digests:

```text
original 1 buffer_operations_00 f2b8782e70200433 684bb3b4a7d0f0ae
mutated  1 buffer_operations_00 6c8df4db783c556a a28fa191c69a64c
```

Both executions report a passing smoke. The changed digest shows that the inserted chain is observed; the successful exit shows that no independent expected-value oracle evaluates it.
