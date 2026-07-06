> This is a review from an agent with an automatic prompt from the reviewer

## Tests

**Command:**
```
cd projects/hipblaslt/tensilelite && source .venv/bin/activate && python -m pytest \
  Tensile/Tests/unit/test_benchmarkProblems_cache_library_file.py \
  Tensile/Tests/unit/test_writeClientConfigIni_library_file.py \
  Tensile/Tests/unit/test_writeClientConfig_wrapper_libraryFile_required.py -v
```
**Time:** 0.23s
**Results:** 9 passed, 0 failed, 0 skipped

All CI checks pass (Linux gfx94X, Windows gfx1151, math-ci precheckin,
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
   `cache.yaml` as `LibraryFile` and typed via a `CacheEntry` TypedDict. The
   cached code path reads it back instead of recomputing via `libraryDir()`.
   Legacy cache files lacking the field hit the existing `KeyError` handler
   and trigger a recompile.

3. **Import and call fixes** (`TensileClientConfig.py`): fixes stale imports
   from `Tensile.Common` (which no longer re-exports the needed names) and
   fixes the `writeClientConfigIni` call which was passing `None` positionally
   and missing required args.

4. **Required parameter** (`ClientWriter.py`): `libraryFile` is now required
   (no default) on both `writeClientConfigIni` and the `writeClientConfig`
   wrapper, with `*` making it keyword-only on the wrapper. This eliminates
   the class of bugs where a caller silently relies on the default.

## Actionable items

None. All items from the previous review round have been addressed (see
Commentary below).

## Suggestions

1. **`TensileClientConfig.py:186–192` — the comment is long for what it
   explains.** The 7-line comment could be reduced to 1–2 lines. The detailed
   history of what the old default was and why an empty string is bad is
   context that belongs in the commit message, not in the code.

## Commentary

**Items from the previous review round — all addressed:**

- **`TensileClientConfig.py:195` — `sourceDir=""` assertion failure:** Fixed.
  Now passes `outputDir` instead of `""`.

- **Unused `import pytest`:** Removed from both
  `test_writeClientConfigIni_library_file.py` and
  `test_benchmarkProblems_cache_library_file.py`.

- **`BenchmarkProblems.py:617–625` — verbose inline comments:** Removed
  entirely. The cached branch now has clean code without commentary about
  line numbers or task IDs.

- **`Loading.cpp:51–55` — verbose C++ comment:** Removed. The null check now
  stands on its own without explanation of LLVM `ErrorOr` semantics.

- **`TypedDict` for cache return value:** Added. `CacheEntry(TypedDict)` at
  `BenchmarkProblems.py:92` with `CodeObjectFiles: List[str]` and
  `LibraryFile: str`. Return type annotations added to all three cache
  functions.

- **Dead tuple code path in test:** Removed. The test now directly asserts
  on dict keys without an unreachable `else` branch.

**On reviewer inline comments — all addressed:**

- *Loading.cpp comment removed* (The author replied "Removed").
- *BenchmarkProblems.py cached-branch comment removed* (The author replied
  "Removed").
- *TypedDict added* (The author replied noting that strict runtime checking would
  require mypy or manual asserts, but added the type hints).
- *Legacy cache removal plan* — The author confirmed the TODO exists and he has a
  personal reminder to follow up.
- *ISO date format* — The author confirmed "August" (2026-08-04 = August 4th).

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
