This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#7534  
**Commit reviewed:** `20140cc2ea` (`[rocjitsu] Updated tests to use the new test_paths`)

**Build command:**

```bash
cmake --build $BUILD_DIR --parallel 8 --target rocjitsu_tests hsa_dbi_nop_asm_test hsa_dbi_nop_probe_test probe_fixture_test
```

**Build result:** passed.

**Focused test command:**

```bash
time -p ctest --test-dir $BUILD_DIR -R 'Probe|probe|TrampolineBuilder|InstructionBuilder|InstrumentorPatch|InstrumentorPatchElfShape|InstrumentorPatchDecoded|Spill|Validator|HsaDbiNop' --output-on-failure --timeout 60
```

**Focused test result:** 155/155 passed, 0 failed, 0 skipped, 0 errored. CTest reported 2.45s real time.

This covered the new probe symbol/callable/clobber tests, the trampoline-builder probe-call tests, instrumentor patch/probe tests, the real `rj_nop_probe_gfx90a` fixture test, and the static DBI nop-asm/nop-probe tests. The hardware DBI tests were not registered in this build because CMake reported no gfx90a/CDNA2 GPU.

**CI status at review time:** `pre-commit`, `test (release)`, and `test (asan-ubsan)` passed. TheRock package jobs and TheRock CI summary were failing; downstream TheRock test jobs were skipped. I did not diagnose the package-job failures because the focused local build and test path for this PR passed.

## Summary

This PR extends rocjitsu DBI from the existing inline-nop trampoline to a probe-call shape. A requested `InstrumentationPoint` can now carry a probe code object and symbol name; the instrumentor resolves the probe function, verifies it as a callable body, copies one copy of each distinct probe into the appended `.text` cave, and emits per-site trampolines that materialize the copied body address and call it with `s_swappc_b64`.

The implementation adds:

- `probe_symbol.{h,cpp}` for ELF symbol lookup, executable-section bounds checking, and body file-offset resolution.
- `probe_callable.{h,cpp}` for body validation and conversion to a copied `ProbeCallable`.
- `probe_clobber.{h,cpp}` for decode-derived ordinary clobber and special-state summaries.
- New SOP1/SOP2/SOPC instruction builders needed by the call envelope.
- Probe-call resource planning in `TrampolineBuilder`, including link pair, target pair, SCC preservation, and envelope byte emission.
- Instrumentor integration: probe registry deduplication, probe body layout before trampolines, liveness-driven resource checks, and fail-closed no-spill policy.
- New DBI fixture/probe tests, including a build-tree no-GPU static smoke test and GPU-gated dispatch/sabotage tests.

## Actionable Items

### 1. Probe validation should enforce the no-arg return-link ABI

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/probe_callable.cpp:190-209`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/instrumentor.cpp:530-541`

The PR description says this slice currently supports a no-argument probe that
returns through `s[30:31]`. That is a reasonable first calling convention, but
`build_probe_callable()` should enforce that ABI more completely. Today it walks
the body, rejects calls and scratch accesses, and then only checks that the last
decoded instruction is `s_setpc_b64 s[30:31]`. That is not enough to prove that
the copied probe will return to the trampoline. Two bad bodies still pass the
current verifier:

```asm
s_mov_b32 s30, 0
s_setpc_b64 s[30:31]
```

This overwrites the `s_swappc_b64` return PC before returning. Because `plan_probe_call()` allows the fixed link pair to be non-live at the anchor and the spill check only intersects clobbers with `live_before(anchor)`, this body can be accepted when `s30:s31` are dead in the host kernel, even though the probe itself destroys the return address.

```asm
s_endpgm
s_setpc_b64 s[30:31]
```

This also passes the final-instruction check but never returns in normal execution.

Fix this by making the callable verifier enforce the supported no-arg ABI, not
just the final mnemonic. At minimum, reject any instruction before the final
return that defines the convention's link pair, reject program terminators, and
reject control-flow that can skip or bypass the final return unless/ until the
verifier proves all targets remain inside the body and must eventually return.
If the intent is even narrower — exactly the checked-in `rj_nop_probe` shape for
now — then the verifier should say that in code by accepting only that shape
rather than accepting arbitrary bodies that happen to end in `s_setpc_b64
s[30:31]`.

### 2. The new probe DBI tests and fixtures are not wired into installed tests

**Files:** `emulation/rocjitsu/tests/CMakeLists.txt:385-410`, `emulation/rocjitsu/tests/CMakeLists.txt:914-970`, `emulation/rocjitsu/tests/kernels/CMakeLists.txt:104-124`

The existing inline DBI smoke test uses `rj_install_test_target()` plus `rj_add_test(... INSTALL_COMMAND ...)`, so it is available in the installed CTest tree. The new probe paths do not mirror that:

- `probe_fixture_test` is added with raw `add_test()` and no `rj_install_test_target()`.
- `hsa_dbi_nop_probe_test` is added with raw `add_test()` in `register_hsa_dbi_nop_probe_case()` and no installed-test registration.
- The new runtime fixtures used by those tests, `vector_add_probe_gfx90a.o` and `rj_nop_probe_gfx90a.hsaco`, are not added to `RJ_DEVICE_KERNEL_FIXTURES`, so even installed registration would not have the files that `test_paths.h` looks up through `ROCJITSU_KERNEL_DIR`.

This means the new no-GPU static probe-call coverage exists in the build tree but silently disappears from installed test packages. Please wire these through the same install path as `hsa_dbi_nop_asm_test`: install the test binaries, register installed CTest entries with `rj_add_test(... INSTALL_COMMAND ...)` or the local equivalent, and install the new `.o` / `.hsaco` fixtures under the installed kernel directory.

## Suggestions

### 1. Store `last_mnemonic` as an owning string in the callable verifier

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/probe_callable.cpp:169-207`

The loop comment says it uses strings because the decoded instruction is deleted between iterations, and `last_src0_name` is correctly copied into `std::string`. `last_mnemonic` is still a `std::string_view`. Most mnemonics are table-backed, but some decoded instruction classes expose mnemonic storage owned by the instruction instance. Copying `inst->mnemonic()` into `std::string last_mnemonic` would remove that lifetime dependency and match the comment.

### 2. Make special-state diagnostics distinguish reads from writes

**Files:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/probe_clobber.cpp:46-62`, `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/code/patch/instrumentor.cpp:92-120`

`scan_special_state()` currently scans both source and destination operands, but `check_probe_special_state()` reports "probe body writes special machine state". That is accurate for destinations but not for source-only uses such as a probe reading EXEC or VCC. If source-only special-state use is intentionally unsupported for this milestone, the diagnostic should say "uses or writes"; otherwise, track source and destination special state separately so harmless reads are not rejected under a write-preservation rationale.

## Commentary

The fail-closed shape is good for this milestone. The fixed `s30:s31` return convention, no-spill policy, SCC save/restore envelope, and static no-GPU smoke tests make the first probe-call slice understandable and reasonably bounded.

The static probe smoke test is especially useful: it catches "patched ELF is unchanged", missing copied body, wrong anchor branch, and missing `s_swappc_b64` without requiring a GPU. The hardware sabotage test is the right next layer for proving the call is actually executed when a gfx90a machine is available.
