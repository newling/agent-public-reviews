> This is a review from an agent with an automatic prompt from the reviewer

**PR:** #8699 - `fix : [tensilelite] Add ASAN and TSAN support for debugging`
**Base:** develop
**Files:** 2 changed (+56/-0)

## Tests

Local checks run against the current PR head:

```bash
$VENV/bin/python -m py_compile projects/hipblaslt/tensilelite/tasks.py
cd projects/hipblaslt/tensilelite && $VENV/bin/invoke build-client --help
cd projects/hipblaslt/tensilelite && $VENV/bin/invoke build-client --enable-asan --enable-tsan; printf 'exit:%s\n' "$?"
cd projects/hipblaslt/tensilelite && $VENV/bin/invoke build-client --enable-asan --gpu-targets gfx1151 --no-configure --no-build; printf 'exit:%s\n' "$?"
git diff --check origin/develop...HEAD
```

Results:

- `py_compile`: passed.
- `build-client --help`: passed and shows the new `--enable-asan` and
  `--enable-tsan` flags.
- `build-client --enable-asan --enable-tsan`: printed `Error: ASAN and TSAN
  cannot be enabled simultaneously`, but exited with status 0. This is the
  basis for actionable item 2.
- `build-client --enable-asan --gpu-targets gfx1151 --no-configure --no-build`:
  exited with status 0 and printed that it rewrote the target to
  `gfx1151:xnack+`. I did not run CMake configure, but the rewritten target is
  not in the current supported target list; this is the basis for actionable
  item 1.
- `git diff --check origin/develop...HEAD`: passed.

I did not run a CMake configure or compile for this review. Current public CI has
the hipBLASLt ASAN workflow, math CI, TheRock CI summary, and pre-commit passing
on the current PR head. In particular:

- `Build (hipBLASLt | gfx90a | HOST_ASAN)`: passed in 47m10s.
- `Test hipBLASLt HOST_ASAN | gfx90a (quick)`: passed in 41m23s.
- `hipBLASLt ASAN CI Summary`: passed.

Those green jobs are useful coverage for the existing TheRock HOST_ASAN path:
`.github/workflows/hipblaslt-asan-ci.yml` configures through TheRock with
`-DhipBLASLt_SANITIZER=HOST_ASAN`, builds the `hipBLASLt` target, packages the
installed tree, and runs the quick `hipblaslt-test` path. The workflow does not
invoke `projects/hipblaslt/tensilelite/tasks.py` or set the new
`ENABLE_ASAN` / `ENABLE_TSAN` CMake options added by this PR, so it does not
cover the new `invoke build-client --enable-asan/--enable-tsan` wrapper behavior
called out below.

The Libraries PR Bot check is failing in its `Enforce policy` step; the log body
was not available through `gh run view`, but the local policy suggests this is
likely PR metadata / unit-test-policy related rather than a sanitizer compile
failure.

## Summary

This PR adds TensileLite-specific ASAN and TSAN switches to the standalone
`invoke build-client` flow. The new Python flags append `-DENABLE_ASAN=ON` or
`-DENABLE_TSAN=ON` to the TensileLite CMake configure command, reject the two
flags together in the wrapper, and automatically add `:xnack+` to GPU target
strings when either sanitizer flag is enabled.

On the CMake side, the new `ENABLE_ASAN` / `ENABLE_TSAN` options are local to
`projects/hipblaslt/tensilelite/CMakeLists.txt`. They add `-fsanitize=address`
or `-fsanitize=thread` to `tensilelite-host` through `-Xarch_host`, which means
the implementation is explicitly host-code sanitizer instrumentation, not GPU
device sanitizer instrumentation.

## Actionable items

1. **`projects/hipblaslt/tensilelite/tasks.py:310` - remove the automatic
   `:xnack+` rewrite for host-only ASAN/TSAN builds.**

   The wrapper rewrites every target without an `:xnack` suffix when either
   `--enable-asan` or `--enable-tsan` is set:

   ```python
   if enable_asan or enable_tsan:
       targets = gpu_targets.split(',')
       ...
       if ':xnack' not in target:
           target = f"{target}:xnack+"
   ```

   The green `hipBLASLt ASAN CI` jobs do not exercise this path; they use the
   existing TheRock `hipBLASLt_SANITIZER=HOST_ASAN` flow rather than
   `invoke build-client --enable-asan`. In TheRock's sanitizer model,
   `HOST_ASAN` is host-side ASAN without device-side instrumentation, while
   full `ASAN`/`TSAN` are the modes that rewrite GPU targets for device-side
   sanitizer support. That makes this standalone wrapper's unconditional target
   rewrite too broad.

   The wrapper also does not match the local CMake implementation in
   `projects/hipblaslt/tensilelite/CMakeLists.txt:53-72`, where both sanitizer
   flag sets are passed through `-Xarch_host` and therefore apply to host code.
   For a host-only sanitizer build, `xnack+` is not required and should not
   silently change the device target requested by the user.

   This also creates invalid target strings. For example, `gfx1151` is a
   supported target, but `gfx1151:xnack+` is not listed in
   `projects/hipblaslt/cmake/tensilelite_supported_architectures.cmake:5-28`.
   A user asking for CPU-side ASAN/TSAN on `gfx1151` would have their valid
   target rewritten into an unsupported target before CMake configuration. The
   same risk applies to other targets that do not have an `:xnack+` entry in the
   supported list.

   If this PR is meant to provide host-only sanitizer support, remove the
   `:xnack+` rewrite and the GPU-sanitizer comment. If this wrapper really needs
   to select ASAN-compatible targets, reuse the existing hipBLASLt/TheRock
   sanitizer and target-normalization plumbing instead of inventing a second
   unconditional rewrite, and reject unsupported or explicit `:xnack-` targets
   rather than leaving them untouched.

2. **`projects/hipblaslt/tensilelite/tasks.py:299` - make mutually exclusive
   sanitizer flags fail the task.**

   The wrapper currently detects `--enable-asan --enable-tsan`, prints an error,
   and then returns normally:

   ```python
   if enable_asan and enable_tsan:
       print("Error: ASAN and TSAN cannot be enabled simultaneously", file=sys.stderr)
       return
   ```

   `invoke` treats that as success. Locally, the command printed the error and
   exited with status 0:

   ```bash
   cd projects/hipblaslt/tensilelite && $VENV/bin/invoke build-client --enable-asan --enable-tsan
   # Error: ASAN and TSAN cannot be enabled simultaneously
   # exit:0
   ```

   That is especially easy to miss in automation, where a wrapper script may
   only check the exit code. Change this branch to raise `Exit(code=1)` or
   another non-zero failure so the Python wrapper has the same semantics as the
   CMake-side `message(FATAL_ERROR ...)` check.

## Suggestions

1. **`projects/hipblaslt/tensilelite/CMakeLists.txt:4` - consider using a
   namespaced option name.**

   `ENABLE_ASAN` and `ENABLE_TSAN` are very generic cache variables in a large
   monorepo that already has `HIPBLASLT_ENABLE_ASAN` and `HIPBLASLT_ENABLE_TSAN`.
   If these flags are intentionally TensileLite-only and host-only, names such as
   `TENSILELITE_ENABLE_HOST_ASAN` and `TENSILELITE_ENABLE_HOST_TSAN` would make
   the scope clearer and reduce confusion with the existing hipBLASLt sanitizer
   options.

2. **`projects/hipblaslt/tensilelite/tasks.py:306` - consider making early
   user-facing build failures consistently non-zero.**

   This task has several branches that print an error and `return`, including no
   detected GPU target and invalid ROCm compiler paths. That behavior predates
   this PR in most cases, so I am not treating it as a required fix here, but the
   new ASAN/TSAN conflict follows the same pattern and shows why it is risky:
   command-line failures look successful to callers.

## Commentary

The core CMake idea is reasonable for debugging TensileLite host-side issues:
instrument the host library and let those usage requirements propagate to the
standalone client build. The risky part is mixing that host-only sanitizer path
with GPU-target rewriting and GPU-sanitizer language. Keeping the option names,
comments, and target handling aligned with the actual host-only implementation
would make this feature much easier to reason about.
