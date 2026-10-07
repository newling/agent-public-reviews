This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocjitsu-test-corpus#55](https://github.com/ROCm/rocjitsu-test-corpus/pull/55)

**Reviewed head and suggestion-branch base:** [`40fe53933d61cbd26c46d26ece3eed44ea37efb5`](https://github.com/ROCm/rocjitsu-test-corpus/commit/40fe53933d61cbd26c46d26ece3eed44ea37efb5).

**Suggestion branch:** [review/pr55-suggestions](https://github.com/newling/rocjitsu-test-corpus/tree/review/pr55-suggestions), tip [`9d7690e`](https://github.com/newling/rocjitsu-test-corpus/commit/9d7690ef3f4890ad014ccc544e46b543bd456026).

**Scope recommendation:** [Keep this PR's manifest focused on assembly regeneration](#c-keep-the-manifest-focused-on-assembly-regeneration). The mutation metadata and its findings should accompany the mutation generator in a follow-up PR.

This review corrects the initial assessment of the available mutation contract and adds focused runtime and failure-path checks. The public PR head is unchanged. The public [companion engine at `e3b6bab`](https://github.com/ROCm/rocjitsu-test-corpus/commit/e3b6bab0767ccb5b75950db73e84adbdd8d083a3) was inspected to establish how these artifacts and metadata are consumed; that engine is outside this PR's diff. The initial PR metadata response inadvertently included an existing GitHub review; no further review comments or threads were consulted. Findings below were checked directly against source and local experiments.

| Review item | Commits | Implementation |
| --- | --- | --- |
| 1 | [`4ecd2cf`](https://github.com/newling/rocjitsu-test-corpus/commit/4ecd2cf3930779f6b7298ce99c43f0bd012c3222), [`4a11cd0`](https://github.com/newling/rocjitsu-test-corpus/commit/4a11cd0e9b7fd666ffef80c6f696186e4de74f43) | Preserve existing outputs on failure, including dangling caller symlinks; regression tests. |
| 2 | [`2c638b6`](https://github.com/newling/rocjitsu-test-corpus/commit/2c638b691677ccd86be8afdcb89e2cae60ad98b7) | Detect committed artifacts that regeneration no longer produces; regression tests. |
| 3 | [`3c02f39`](https://github.com/newling/rocjitsu-test-corpus/commit/3c02f3924aad790248b3889a08e61999428f88fe) | Correct tensor-wait coverage and check manifest/artifact consistency. |
| 4 | [`75c3907`](https://github.com/newling/rocjitsu-test-corpus/commit/75c3907701e20ce1da84db47035a769082a32681) | Document the established selection and metadata rules; check existing exemption references. |
| 5 | None | Missing harmless-mutation exemptions require a target-aware representation shared with the companion consumer. |
| 6 | [`1179ded`](https://github.com/newling/rocjitsu-test-corpus/commit/1179ded737d875b8f32cb624e6110dc48e91f514) | Preserve compiler diagnostics and correct the missing-header skip claim; regression test. |
| Suggestion A | [`f24ce9f`](https://github.com/newling/rocjitsu-test-corpus/commit/f24ce9fad2e0dbd2f990e0074ada0b0c5dbab73b), [`9d7690e`](https://github.com/newling/rocjitsu-test-corpus/commit/9d7690ef3f4890ad014ccc544e46b543bd456026) | Preserve quoted compiler flags and reject malformed quoting before compilation; regression tests. |
| Suggestion C | None | Proposed scope reduction: retain the assembly inventory here and introduce mutation metadata with its consumer. |

The two commits in item 1 are sequential, as are the two in suggestion A. Item 2's tests extend the file introduced by item 1. The four commits after the first review were added without rewriting the earlier branch history.

## Tests

All focused Python regressions pass on the updated branch; selected gfx950 baselines and mutation controls execute successfully with the race plugin; the first review's assembly/link validation of all 37 unchanged pinned files remains applicable.

The final Python tests were copied onto both the submitted source and the previous suggestion tip. The submitted source reproduces the preservation, drift, coverage, diagnostic, and flag-parsing failures; the previous suggestion tip reproduces the newly added diagnostic and flag-parsing failures. Test sources are committed in [`tests/test_race_regenerate_asm.py`](https://github.com/newling/rocjitsu-test-corpus/blob/9d7690ef3f4890ad014ccc544e46b543bd456026/tests/test_race_regenerate_asm.py) and [`tests/test_race_manifest.py`](https://github.com/newling/rocjitsu-test-corpus/blob/9d7690ef3f4890ad014ccc544e46b543bd456026/tests/test_race_manifest.py) and run with:

```bash
python -m pytest tests/test_race_regenerate_asm.py tests/test_race_manifest.py -q
```

The runtime probe links the pinned gfx950 assembly to freshly compiled ROCm 7.1 host objects. The `add_checked`, `war_pattern`, and `lds_war_pattern` baselines return `PASS` without race reports. Mutations and positive controls are described in item 5 and Commentary; the exact probe source is in the appendix. This is representative gfx950 validation, not a full corpus, gfx1250 runtime, or multi-detector qualification.

The original `--check --target gfx950` run compiled every selected kernel with AMD Clang 20 and then reported expected textual drift from the pinned AMD Clang 23 artifacts. Artifact assembly used Clang 23.1 and linking used LLD 20 after standalone LLD 23 could not load `libicui18n.so.70`. Those are toolchain/environment results, not additional PR defects. GitHub reports no CI checks for the reviewed head.

## Summary

The PR pins a complete kernel/target assembly inventory and provides explicit regeneration. This makes changes to the instruction streams visible in version control and records useful compiler provenance. This pass also examines whether the metadata gives consumers reliable mutation expectations, using both instruction dependencies and executable controls. Stable instruction text is useful, but each scored mutation still needs a justified expectation.

## Actionable items

Items 3–5 concern mutation metadata. If the scope reduction in [Suggestion C](#c-keep-the-manifest-focused-on-assembly-regeneration) is adopted, address them in the follow-up PR that introduces that metadata and its consumer. Their evidence and existing fixes are retained below; they apply here if the full manifest remains in this PR.

### 1. Preserve existing assembly when compilation fails

Location: [`corpus/race/scripts/regenerate_asm.py:127–138`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/scripts/regenerate_asm.py#L127-L138).

The script unlinks the pinned output before invoking the compiler. Compilation failure, or successful exit without an output, therefore deletes the previous baseline. It also deletes a possible automatic compiler-output filename in the caller's directory, including during `--check`, without establishing that the file belongs to this invocation.

The committed regression tests reproduce both failures, including a dangling caller symlink. Commits [`4ecd2cf`](https://github.com/newling/rocjitsu-test-corpus/commit/4ecd2cf3930779f6b7298ce99c43f0bd012c3222) and [`4a11cd0`](https://github.com/newling/rocjitsu-test-corpus/commit/4a11cd0e9b7fd666ffef80c6f696186e4de74f43) compile to a temporary output, normalize it, and replace the pinned destination only after success. They refuse a preexisting automatic-output filename instead of deleting it. The compiler retains the caller's directory so relative flags keep their meaning. This provides per-output preservation; it is not a transaction across all kernels or a guarantee for concurrent invocations sharing a working directory.

### 2. Include obsolete committed files in drift detection

Location: [`corpus/race/scripts/regenerate_asm.py:235–244`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/scripts/regenerate_asm.py#L235-L244).

The comparison walks only fresh files. If a removed case leaves `obsolete.s` in the committed directory, identical remaining files make `--check` report a match. A target with committed files but no fresh directory is skipped too. This can hide inventory changes from an assembly-discovering consumer.

Commit [`2c638b6`](https://github.com/newling/rocjitsu-test-corpus/commit/2c638b691677ccd86be8afdcb89e2cae60ad98b7) compares the union of filenames and reports committed files that are no longer generated. Its tests cover additions, removals, content changes, matching contents, and an absent fresh directory. It reports obsolete files for deliberate removal.

### 3. Remove the unsupported tensor-wait coverage claim

Location: [`corpus/race/cases.toml:182–190`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/cases.toml#L182-L190).

`fa-barrier-epoch` lists `tensorcnt`, but its pinned assembly has no `s_wait_tensorcnt`. Its source explicitly substitutes `ds_store_b16` for tensor DMA. The manifest therefore advertises coverage that this artifact cannot provide.

Commit [`3c02f39`](https://github.com/newling/rocjitsu-test-corpus/commit/3c02f3924aad790248b3889a08e61999428f88fe) removes that counter and separates the example from the tensor-DMA grouping. The compiler-free check verifies declared gfx1250 counters against the artifacts and accepts combined mnemonics such as `s_wait_loadcnt_dscnt`. This is a presence check, not a semantic proof of the hazard produced by removing a wait.

### 4. Document the existing mutation contract

Locations: [`corpus/race/cases.toml:15–23`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/cases.toml#L15-L23) and [`:252–260`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/cases.toml#L252-L260).

**Correction to the first review:** treating the ordinal convention as an unresolved design choice was too strong. The public companion's `find_wait_sites` assigns zero-based ordinals after excluding `s_wait_xcnt`, with combined waits counted as one instruction. Running it against the pinned WMMA artifact selects the intended epilogue at line 148 for `ordinal = 3`. The existing value is correct. The metadata should document that established rule when it is introduced.

The companion also already consults surrounding instructions when proposing resource tags, and it does not read `waits` as a mutation-selection filter. The first review should have acknowledged that implementation rather than implying those choices were wholly absent. The general limitation remains: gfx950 `lgkmcnt` covers scalar loads and LDS operations, so `access` plus counter alone cannot establish the raced resource.

Commit [`75c3907`](https://github.com/newling/rocjitsu-test-corpus/commit/75c3907701e20ce1da84db47035a769082a32681) documents these facts, the non-exhaustive gfx1250 vocabulary used by `waits`, and the distinction between a kernel's source pattern and an individual mutant's hazard. It preserves the existing WMMA exemption and adds a check that exemption ordinals resolve to the declared mnemonics on the supported targets. It also makes clear that a mnemonic check cannot detect a changed dependency guarded by another occurrence of the same mnemonic. Semantic revalidation after regeneration is still required.

### 5. Exempt the harmless LDS wait removals

Location: [`corpus/race/cases.toml:140–148`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/cases.toml#L140-L148), with the pinned sites in [`asm/gfx950/lds_war_pattern.s:32–43`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/asm/gfx950/lds_war_pattern.s#L32-L43).

This case opts into every eligible wait mutation but has no exemptions. The waits at lines 34 and 42, ordinals 2 and 4, drain LDS stores before barriers. Each thread owns its `sdata[tid]` slot; subsequent reads of a slot come from its owning wave, and the final read of `sdata[0]` is performed by thread 0. With the in-wave LDS ordering described by the kernel, removing either store-draining wait creates no cross-wave dependency and no register-result hazard. These mutations do not acquire the intended race merely because a wait was removed.

Both mutated executables return `PASS` with no race report. As a positive control, removing ordinal 3, the wait between `ds_read_b32 v2, v1` and `v_add_u32_e32 v2, 1, v2`, reports the expected VGPR read hazard. Static address ownership and instruction ordering establish the harmless cases; the runtime control corroborates the distinction. The companion generator emits ordinals 2 and 4 without `exempt`, so a consumer expecting every non-exempt mutation to expose a race would count a correct nondetection as a miss.

Add justified exemptions and validate them alongside a known-hazard control. This needs a target-aware representation or another shared selector: the existing exemption format applies a single exact mnemonic to every target, but these sites use `s_waitcnt` on gfx950 and `s_wait_dscnt` on gfx1250. Adding a gfx950-only `site` string to the portable case would make the companion reject the other target. No guessed schema or cross-PR consumer change is included on the suggestion branch. The concrete gfx950 counterexamples and their build/run probe are preserved below.

### 6. Preserve the compiler's failure diagnostic

Locations: [`corpus/race/scripts/regenerate_asm.py:177–182`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/scripts/regenerate_asm.py#L177-L182) and [`corpus/race/cases.toml:244–245`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/cases.toml#L244-L245).

`compile_device_asm` captures the diagnostic, but `regenerate` keeps only the exception's first line. An error such as a missing `rocwmma/rocwmma.hpp` consequently produces only `FAIL: kernel.hip (gfx950):`, without the reason or source location. This prevents the regeneration command from explaining how to fix its toolchain or include-path failure. The nearby manifest comment also promises a skip for missing headers, although regeneration returns failure.

Commit [`1179ded`](https://github.com/newling/rocjitsu-test-corpus/commit/1179ded737d875b8f32cb624e6110dc48e91f514) retains the complete diagnostic and corrects the skip claim without changing the failure policy. The regression uses a failing compiler process and verifies that both the kernel/target context and the diagnostic survive.

## Suggestions

### A. Preserve quoting in extra compiler flags

Location: [`corpus/race/scripts/regenerate_asm.py:212`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/scripts/regenerate_asm.py#L212).

`--cxxflags='-I"headers with spaces"'` is split on whitespace, leaving embedded quotes and multiple arguments instead of one include path. Commits [`f24ce9f`](https://github.com/newling/rocjitsu-test-corpus/commit/f24ce9fad2e0dbd2f990e0074ada0b0c5dbab73b) and [`9d7690e`](https://github.com/newling/rocjitsu-test-corpus/commit/9d7690ef3f4890ad014ccc544e46b543bd456026) use shell-style lexical parsing without a shell, test the actual compiler argument list, and reject unmatched quoting before compiling. The malformed-input regression is compiler-free on the submitted code as well.

### B. Correct the documented command and compiler requirement

The PR description names the nonexistent `corpus/race/scripts/regenerate.py`; both examples should use `regenerate_asm.py`. Also, the script's opening docstring calls regeneration the only part that needs a HIP compiler. The companion still invokes `hipcc --cuda-host-only` and links host objects to the pinned device image, as exercised by the runtime probe. Commit [`75c3907`](https://github.com/newling/rocjitsu-test-corpus/commit/75c3907701e20ce1da84db47035a769082a32681) corrects that source docstring. No replacement PR description was authored.

### C. Keep the manifest focused on assembly regeneration

Locations: [`corpus/race/cases.toml:1–42`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/cases.toml#L1-L42) and [`corpus/race/scripts/regenerate_asm.py:144–179`](https://github.com/ROCm/rocjitsu-test-corpus/blob/40fe53933d61cbd26c46d26ece3eed44ea37efb5/corpus/race/scripts/regenerate_asm.py#L144-L179).

Please reduce `cases.toml` in this PR to the kernel and target inventory needed for assembly regeneration. Keep the `[corpus]` schema/name header and each case's `id`, `kernel`, and `requires`. Introduce `mutate`, `access`, `hazard`, `waits`, `[[case.exempt]]`, and the associated mutation descriptions and documentation alongside the mutation generator, so those expectations can be reviewed and tested together with their consumer.

The regeneration script validates the schema and reads only `kernel` and `requires` from each case; stable `id` values can remain useful to identify the inventory. Keeping this minimal manifest, the pinned assembly, the regeneration script, and inventory checks together leaves a self-contained assembly PR. The companion can then extend the same file, avoiding a second kernel/target inventory. Preserve useful regeneration prerequisites, such as the rocWMMA include-path instructions, with the assembly tooling.

The current file also defines mutation and scoring behavior whose correctness depends on the companion implementation. Review the counter-coverage claims, per-mutant hazard labels, ordinal rules, and target-aware exemptions with that implementation and its behavioral tests. The findings in items 3–5 remain relevant to that follow-up; assembly regeneration can be assessed independently of those decisions.

This is a proposed split across the PR stack. The existing suggestion branch retains the submitted manifest structure and its validated fixes; it does not implement the split or change the companion. The metadata-specific fixes and tests should accompany the fields if they move to the follow-up.

## Commentary

A concrete companion follow-up surfaced during the same probes. `war_pattern` ordinal 2 produces a VGPR read-after-write hazard, but the companion labels it `WAR`. `lds_war_pattern` ordinal 3 similarly produces a VGPR read-after-write hazard, while the companion derives `resource = "lds", hazard = "WAR"`. The instruction pairs are `global_load_dword` → `v_mad_u64_u32` and `ds_read_b32` → `v_add_u32_e32`, respectively. The `access = "lds"` field correctly describes the latter kernel's memory use; it is the consumer's promotion of source-pattern and heuristic tags into per-mutant expectations that needs correction. That code is outside #55, and the branch's documentation change does not fix its tagging algorithm.

The companion also has a separate toolchain-discovery bug at [`build.py:57–58`](https://github.com/ROCm/rocjitsu-test-corpus/blob/e3b6bab0767ccb5b75950db73e84adbdd8d083a3/corpus/race/scripts/build.py#L57-L58): `explicit := os.environ.get("ROCM_PATH") is not None` assigns a Boolean, so setting `ROCM_PATH` causes `Path(True)` to raise `TypeError`. This was encountered while preparing the probe. With the companion scripts on `PYTHONPATH`, `ROCM_PATH=/opt/rocm python -c 'import build; build.rocm_path()'` reproduces it. The fix belongs to that companion: bind the environment value before testing it against `None`. The appendix supplies a `Toolchain` explicitly, so the successful runtime builds do not validate default discovery. This bug is absent from #55's `regenerate_asm.rocm_path` and was not added to the suggestion branch.

Handoff: [review/pr55-suggestions](https://github.com/newling/rocjitsu-test-corpus/tree/review/pr55-suggestions) contains the commits mapped above. The original bounded fixes remain, the contract documentation is corrected, and diagnostics and quoted flags have new regression coverage. Target-aware exemptions, the identified companion issues, and broader runtime qualification remain explicit follow-ups.

## Appendix: exact runtime counterexample probe

Use the reviewed head for `source`, and `build.py` plus `mutate.py` from the linked companion revision in the `engine` directory. Supply a gfx950 RocJITsu configuration with `"plugins": {"race": {}}` and configure the library search path for the chosen SDK and RocJITsu build. The probe uses explicit tool paths and builds each mutation from the pinned assembly; it does not recompile device HIP source.

```bash
python probe_mutants.py "$SRC_DIR" "$ENGINE_DIR" "$BUILD_DIR" \
  "$ROCJITSU_BIN" "$CONFIG" --clang "$CLANG" --lld "$LLD" --sdk "$ROCM_PATH"
```

```python
"""Build and run selected pinned-assembly mutations with explicit tool paths."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys


parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("engine", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("runner", type=Path)
parser.add_argument("config", type=Path)
parser.add_argument("--clang", default="clang-23")
parser.add_argument("--lld", default="ld.lld-20")
parser.add_argument("--sdk", type=Path, default=Path("/opt/rocm"))
args = parser.parse_args()
sys.path.insert(0, str(args.engine.resolve()))
import build
import mutate

llvm = args.sdk / "llvm/bin"
toolchain = build.Toolchain(
    args.sdk, args.sdk / "bin/hipcc", llvm / "clang",
    llvm / "clang-offload-bundler", llvm / "llvm-mc", Path("/usr/bin/nm")
)
results = []
for name, ordinal in [
    ("war_pattern", 2),
    ("lds_war_pattern", 2),
    ("lds_war_pattern", 3),
    ("lds_war_pattern", 4),
]:
    work = (args.output / f"{name}-wait{ordinal}").resolve()
    work.mkdir(parents=True, exist_ok=True)
    assembly = work / f"{name}.s"
    site = mutate.apply_wait_mutation(
        args.source / "corpus/race/asm/gfx950" / f"{name}.s", ordinal, assembly
    )
    subprocess.run([
        args.clang, "--target=amdgcn-amd-amdhsa", "-mcpu=gfx950",
        "-x", "assembler", "-c", "-nogpulib", str(assembly), "-o", str(work / "device.o")
    ], check=True)
    subprocess.run([
        args.lld, "-shared", "--no-undefined", str(work / "device.o"),
        "-o", str(work / "device.hsaco")
    ], check=True)
    host = build.compile_host_object(
        args.source / "corpus/race/kernels" / f"{name}.hip", work / "host.o", tools=toolchain
    )
    bundle = build.create_offload_bundle(
        work / "device.hsaco", "gfx950", work / "device.hipfb", tools=toolchain
    )
    fatbin = build.embed_fatbin(
        bundle, build.fatbin_symbol(host, tools=toolchain), work, work / "fatbin.o", tools=toolchain
    )
    executable = build.link_executable(host, fatbin, work / name, tools=toolchain)
    command = [
        str(args.runner), "--config", str(args.config), "--cpu-thread-budget=1", "--", str(executable)
    ]
    with (work / "run.log").open("w") as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            status = child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            status = child.wait()
    output = (work / "run.log").read_text(errors="replace")
    races = [line for line in output.splitlines() if line.startswith("RACE ")]
    result = {
        "kernel": name, "ordinal": ordinal, "line": site.line_number + 1,
        "removed": site.full_line.strip(), "returncode": status,
        "pass": "PASS" in output, "race_count": len(races), "first_races": races[:3],
        "log": str(work / "run.log")
    }
    results.append(result)
    print(json.dumps(result), flush=True)
(args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
```
