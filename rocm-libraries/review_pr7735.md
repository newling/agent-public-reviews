> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**Command:**
```
cd projects/hipblaslt/tensilelite && source .venv/bin/activate && python -m pytest \
  Tensile/Tests/unit/test_benchmarkProblems_cache_library_file.py \
  Tensile/Tests/unit/test_writeClientConfigIni_library_file.py \
  Tensile/Tests/unit/test_writeClientConfig_wrapper_libraryFile_required.py -v
```
**Time:** 0.56s
**Results:** 9 passed, 0 failed, 0 skipped

All CI checks also pass (Linux gfx94X, Windows gfx1151, math-ci precheckin,
codecov, clang-tidy, pre-commit).

## Summary

This PR fixes a SIGSEGV that occurs when using `--use-cache` on single-arch
builds (e.g., gfx1201). The root cause is a path mismatch: `libraryDir()`
returns `library/<arch>/` for single-arch builds, but `writeClientConfigIni`
defaulted to `library/TensileLibrary.yaml` (flat) when `libraryFile` was not
passed. The cached code path in `_benchmarkProblemType` omitted the kwarg,
so the client's `.ini` pointed at a nonexistent file, and `LLVMLoadLibraryFile`
dereferenced the resulting null `unique_ptr`.

The fix has four parts:

1. **C++ null check** (`Loading.cpp`): defense-in-depth — check the
   `ErrorOr` from `getFileAsStream` before dereferencing. Future wrong-path
   bugs become a one-line error instead of a crash.

2. **Cache round-trip** (`BenchmarkProblems.py`): `writeBenchmarkFiles` now
   returns the relative library-file path it wrote. This path is persisted in
   `cache.yaml` as `LibraryFile`. The cached code path reads it back instead
   of recomputing via `libraryDir()`. Legacy cache files lacking the field
   hit the existing `KeyError` handler and trigger a recompile.

3. **Import and call fixes** (`TensileClientConfig.py`): fixes stale imports
   from `Tensile.Common` (which no longer re-exports the needed names) and
   fixes the `writeClientConfigIni` call which was passing `None` positionally
   and missing required args.

4. **Required parameter** (`ClientWriter.py`): `libraryFile` is now required
   (no default) on both `writeClientConfigIni` and the `writeClientConfig`
   wrapper, with `*` making it keyword-only on the wrapper. This eliminates
   the class of bugs where a caller silently relies on the default.

## Actionable items

1. **`TensileClientConfig.py:195` — `sourceDir=""` will hit an assertion
   failure.** The call passes `""` for `sourceDir`, but `writeClientConfigIni`
   at `ClientWriter.py:563` asserts `os.path.exists(sourceDir)`, and
   `os.path.exists("")` is `False`. This was also broken before the PR (the
   old code also passed `""`), but since the PR is fixing up this call site
   anyway, it would be good to fix this too. The simplest approach: pass
   `outputDir` (which is already computed at line 193) as `sourceDir`, or
   `"."`, so the assert passes.

2. **`test_writeClientConfigIni_library_file.py:13` — unused `import pytest`.**
   `pytest` is imported but never referenced in this file. Same in
   `test_benchmarkProblems_cache_library_file.py:14` — `pytest` is imported
   but only used implicitly via `tmp_path` fixtures (which don't need the
   import).

## Suggestions

1. **`BenchmarkProblems.py:617–625` — trim inline comments.** The two comment
   blocks in the cached branch (lines 617–621 and 623–625) are detailed
   explanations of the bug this PR fixes, including references to specific
   line numbers ("line 109") and task numbers ("Task 6") that will rot. A
   shorter comment would serve better, e.g.:
   ```python
   # cachedLibraryFile comes from cache.yaml — see _readCacheIfValid.
   libraryFile = os.path.join(str(sourcePath), cachedLibraryFile)
   if not os.path.isfile(libraryFile):
       printExit(...)
   ```

2. **`Loading.cpp:51–55` — trim the C++ comment.** The 5-line comment
   explaining LLVM `ErrorOr` semantics, the original SIGSEGV, and the
   debugging timeline is informative now but will age poorly. Consider
   reducing to one line, e.g.:
   ```cpp
   // getFileAsStream failed — return nullptr instead of dereferencing null.
   ```

3. **Consider `TypedDict` for the cache return value.** The return type of
   `_readCacheIfValid` changed from a plain list to a `dict` with specific
   string keys (`CodeObjectFiles`, `LibraryFile`). A `TypedDict` would make
   the contract explicit and let type checkers catch key mismatches. This is
   beyond the scope of this bug fix but would be a clean follow-up.

4. **`test_benchmarkProblems_cache_library_file.py:58–66` — dead code path.**
   The `else` branch (lines 63–66) handling a tuple return type will never
   execute since `_readCacheIfValid` returns a dict. The comment says it
   "accepts either" but only one form exists. Removing the tuple branch would
   simplify the test.

## Commentary

**On previous review comments:**

- *Loading.cpp:53 — "comment seems like part of a bug fix explanation"*: I
  agree. The code pattern (null-check an `ErrorOr`) is standard LLVM
  practice; a one-line comment is sufficient.

- *BenchmarkProblems.py:134 — "Is there a plan to remove legacy caches?"*:
  The TODO at line 128 already documents this: remove after ~2026-08-04,
  which is ~3 months from the PR's date (2026-05-04). The plan exists.

- *BenchmarkProblems.py:132 — typing for return type checking*: `TypedDict`
  would be the right tool here. Worth considering as a follow-up.

- *BenchmarkProblems.py:518 — "Is that 08 April or 04 August?"*: The format
  is ISO 8601 (YYYY-MM-DD), so `2026-08-04` is August 4th. The format is
  unambiguous. Worth noting: the date matches the "~3 months" stated in the
  comment at line 128.

- *BenchmarkProblems.py:625 — "comment seems too specific to bug fix
  effort"*: I agree. The line-number reference ("line 109") and task
  reference ("Task 6") are particularly fragile.

**Design observations:**

The approach of persisting the library path in `cache.yaml` rather than
recomputing it is the right call — it eliminates the entire class of bugs
where `libraryDir()` layout assumptions diverge from what the build actually
wrote. Making `libraryFile` a required parameter closes the complementary
hole where a new call site could silently use a wrong default.

The source-inspection tests (using `inspect.getsource` and paren-matching to
verify call sites pass `libraryFile=`) are an unusual testing pattern. They
guard against a specific regression — someone removing the kwarg at a call
site — which a normal unit test couldn't catch without actually running a
benchmark. The tradeoff is that they're brittle to refactoring (renaming the
function or parameter would break them), but the risk they guard against is
high-severity (silent SIGSEGV). On balance, they're reasonable for this
specific invariant.
