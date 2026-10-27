> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14268](https://github.com/ROCm/rocm-libraries/pull/14268)

Reviewed head: [`fb3c2b3e7cbb41d9be7986e3f3eafb5b02a27e73`](https://github.com/ROCm/rocm-libraries/pull/14268/commits/fb3c2b3e7cbb41d9be7986e3f3eafb5b02a27e73) (`<pr-head-ref>`), merge base [`03f14afc67660f699de2131b117b35d05e8905b6`](https://github.com/ROCm/rocm-libraries/commit/03f14afc67660f699de2131b117b35d05e8905b6). This is a fresh, independent review of the current head; it does not build on earlier review comments.

Suggestion branch: [`review/pr14268-v2`](https://github.com/newling/rocm-libraries/tree/review/pr14268-v2) ([commits on top of the reviewed head](https://github.com/newling/rocm-libraries/compare/fb3c2b3e7cbb41d9be7986e3f3eafb5b02a27e73...f433f447c55dbd39ff41176b4542a1e2424ad2f7)), based directly on the reviewed head. Each commit can be inspected or cherry-picked on its own.

| Commit | Item |
|---|---|
| [`7af83079333`](https://github.com/newling/rocm-libraries/commit/7af830793338475009caa10dc9d292baf40ed84d) | Actionable 1: Geko binds `SolutionIdGen.py` to the workflow's checkout and fails when it is missing |
| [`62c38e295b0`](https://github.com/newling/rocm-libraries/commit/62c38e295b0177599af95fa995b7fd3c6db512c2) | Actionable 3: read the UID map on the first UID lookup |
| [`59c6020b964`](https://github.com/newling/rocm-libraries/commit/59c6020b964be94b11a520a8e120a8821443dd39) | Suggestion 1: drop the redundant shard load in `getSolutionByUid` |
| [`a374f7cf37a`](https://github.com/newling/rocm-libraries/commit/a374f7cf37a29ef27db2cd91f0263fa638dc76b2) | Suggestion 2: docs say that generation replaces colliding UIDs |
| [`f433f447c55`](https://github.com/newling/rocm-libraries/commit/f433f447c55dbd39ff41176b4542a1e2424ad2f7) | Suggestion 3: docs distinguish the file position, the build index and the stored UID |

Actionable 2 and suggestion 4 have no commit because each depends on a policy decision.

## Tests

On the PR head, the focused TensileLite UID Python tests (114), the Geko UID, library and pipeline unit tests (71), and the TensileLite host gtest suite (658 passed, 8 skipped) all pass. On the suggestion branch, the full Geko unit suite (559 passed, 44 skipped) and the TensileLite host suite (659 passed, 8 skipped) pass.

- The corpus uniqueness scan passes in its default mode. With `HIPBLASLT_REQUIRE_SOLUTION_UID=1` it fails: 178 shipped solutions have no `SolutionUID` (actionable 2).
- The bench-side C++ base62 formatter matches the Python `encode_solution_uid`/`decode_solution_uid` on 2,007 values, including 0, 2^63 and 2^64−1.
- No device library was generated and no GPU GEMM was run. The C++ runtime path was exercised through host gtests and a load-time probe (appendix B).
- CI snapshot at review time: 81 pass, 41 pending, 0 failing. The UID-uniqueness, GEKO and TensileLite coverage lanes pass.

## Summary

The PR carries the persisted `SolutionUID` from logic YAML into the runtime. `Contractions.Solution` decodes it, the msgpack metadata stores it as `solutionUid`, and `TensileCreateLibrary` writes a per-architecture `UidMapping` (UID to dense index). Before writing that map it rejects a zero UID or one UID on two indices. `hipblaslt_ext::getUidFromAlgo` reports the UID of a selected algorithm, and `hipblaslt-bench` prints it. On the generation side, each writer now makes UIDs unique within its own run:

- LibraryLogic shares one `seen` set across a Tensile process.
- `TensileMergeLibrary` keeps the pooled UID on a `SolutionNameMin` match and redraws a colliding one.
- Geko gives fresh UIDs to `final_libs`/`full_libs` and rewrites collisions across one generation's logic files.

Selection still uses the dense index.

Several choices are worth keeping:

- **One numeric collision rule everywhere.** Comparisons use the decoded integer, and `claim_solution_uid` is shared by all writers, so `0U5` and `0u5` collide in every one of them.
- **Runtime is additive.** It is keyed by the existing dense index, and older metadata without a UID still loads with a value of zero.
- **The map writer checks against the assembled library.** It catches duplicates that span logic files, which no single generation run can see.

The two substantive problems are both about what the UID guarantees in practice. A documented Geko install path silently produces exactly the duplicate this PR sets out to prevent. And the build mints throwaway UIDs that look identical to persisted ones for solutions that have none, a set that is already large on current develop.

## Actionable items

### 1. A non-editable Geko install silently keeps copied Origami UIDs

`projects/hipblaslt/utilities/geko/geko/library/uid_uniqueness.py:17-68`, `geko/library/operations.py:169,604,718`, `utilities/geko/README.md:600`

`_solution_id_gen_path()` locates the codec at `Path(__file__).parents[4]/tensilelite/...`. That path exists only in a source tree or an editable install. With `pip install .`, which the Geko README documents as the primary install at line 280, the file is not found. `_load_solution_id_gen()` then logs a warning and returns `None`, and `assign_fresh_solution_uids` and `uniquify_generated_logic` return 0 without changing anything.

So `from_full_dataframe` writes the Origami UID into `full_libs`, and the merge into the Equality file keeps it, because that UID is not in the Equality pool. The duplicate surfaces only later, when `TensileCreateLibrary` or the uniqueness CI rejects the merged tree. By then it is far from the Geko run that caused it, and the warning has scrolled away. Appendix A reproduces this: a non-editable layout reports `codec path exists False`, `assigned 0`, and the Origami UID survives.

CI does not exercise this path. The "Test pip install" step installs Geko non-editably, but `tests/__init__.py` makes pytest put the source tree first on `sys.path`, so the tests import the checkout copy.

The workflows already know the right checkout: `run_search` and `run_optimize` validate `hipblaslt_path`, and `prune_library` receives it. Commit [`7af83079333`](https://github.com/newling/rocm-libraries/commit/7af830793338475009caa10dc9d292baf40ed84d) makes these changes:

- Adds an optional `hipblaslt_path` to `merge_solutions`, `from_dataframe`, `from_full_dataframe` and the two `uid_uniqueness` entry points. When given, it selects the codec's checkout; otherwise the containing checkout is used, as before.
- Passes the path from the five pipeline call sites and from `prune_library`.
- Raises `FileNotFoundError` when the codec is still missing.
- Updates the README sentence and replaces the two "warns and keeps" tests with tests that a missing codec raises and leaves the input unchanged. Further tests check that an explicit checkout is used and that `run_search` forwards its checkout.

The PR description still describes an earlier version of this code: required `hipblaslt_path` arguments and "a missing file names that path". It should be updated to match whichever behavior lands.

### 2. Build-time UIDs look identical to persisted ones, and the shipped corpus is not required to have persisted UIDs

`projects/hipblaslt/tensilelite/tensilelite/Contractions.py:1057`, `tensilelite/Common/SolutionIdGen.py:153-164`, `tensilelite/tox.ini:88-100`, `library/include/hipblaslt/hipblaslt-ext.hpp:1152-1168`, `docs/solution-uid.md:3-9`

A solution without a `SolutionUID` gets a fresh random UID from `read_solution_uid` on every `TensileCreateLibrary` run. That value goes into the msgpack metadata and the `UidMapping`, is returned by `getUidFromAlgo`, and is printed by the bench as `--Solution UID: 0u…`, exactly like a persisted UID. The API documentation and `docs/solution-uid.md` do say such a UID is build-specific. But nothing available to a caller distinguishes the two, so a user who records a UID from bench output for one of these solutions gets an identifier that will not exist in the next build. That is the failure mode the UID was introduced to remove. It also makes the generated metadata and `UidMapping` differ between two builds of the same source.

The affected set is not small, and it is growing. At this PR's base the strict scan reports 178 shipped solutions without a UID, in 120 files (gfx1250, gfx1250-strict and gfx1151). Current develop ([`dcfd28a87c2`](https://github.com/ROCm/rocm-libraries/commit/dcfd28a87c2006b9eb9fcafa7f0b82d80cd2b4eb)) has about 6,000:

- [#13981](https://github.com/ROCm/rocm-libraries/pull/13981) regenerated the four gfx942 I8II GridBased files with 4,369 solutions and no UIDs, dropping the 23 that had been backfilled.
- [#13497](https://github.com/ROCm/rocm-libraries/pull/13497) added 73 gfx942 solutions without UIDs.

The `library-uniqueness` CI gate lets this through, because `HIPBLASLT_REQUIRE_SOLUTION_UID` is not set in the tox environment or the workflow. Even with it set, the gate checks only that UIDs are unique within one tree, not that they survive. A PR that rewrites a logic file and drops or regenerates the UIDs of solutions that are still present passes it.

A UID's stability rests on two things: the value being stored in the YAML, and every tool carrying it forward. The time-and-random format only keeps new values from colliding.

This PR is what makes the gap observable, because it is the first to expose these UIDs at runtime. The fix is a policy choice, so there is no commit. The options are complementary:

- **Make persistence mandatory for shipped logic.** Backfill the missing UIDs and set `HIPBLASLT_REQUIRE_SOLUTION_UID=1` in `[testenv:library-uniqueness]`. With this PR, LibraryLogic, `TensileMergeLibrary` and Geko all mint UIDs, so ordinary tuning output already complies. The strict gate would mainly catch hand-written or externally generated logic.
- **Check continuity against the target branch.** Extend the uniqueness job to compare the PR's logic files with the merge base. Fail when a `SolutionUID` disappears or changes while a solution with the same `SolutionNameMin` remains in that file, unless the change was an explicit regeneration.
- **Do not expose a UID that was not persisted.** Missing → 0 at build time, leave it out of `UidMapping`, and keep rejecting an explicit `0u0` when it is decoded. `getUidFromAlgo` and the bench would then guarantee that a non-zero UID survives rebuilds. This changes the PR's stated "every solution gets a UID" behavior, so it depends on whether the next PR's UID-keyed MatchTable needs complete coverage within one build.

If none is adopted, the bench should at least not print a build-specific UID as if it were stable. Today the cost is limited, because nothing selects by UID yet. Once the next PR adds `--solution_uid` and a UID-keyed MatchTable, users will record UIDs and expect them to keep working, so these guarantees belong before or with that change.

### 3. The UID map is decoded during every library setup, before anything uses it

`projects/hipblaslt/tensilelite/include/Tensile/MasterSolutionLibrary.hpp:210-213`

`initLibraryMapping` now loads `TensileLiteLibrary_lazy_<arch>_UidMapping.dat` eagerly in every process. Nothing in this PR uses the map outside tests: `getUidFromAlgo` resolves through the index, and `getSolutionByUid` has no production caller until the selection PR.

The map has one entry per solution, and `messagePackLoadStringKeyMapping` converts every integer key to a `std::string` and back. With a gfx942-sized map, the load costs about 200–230 ms of setup and 22 MB of retained memory per process, with an 82 MB peak during decode (appendix B). A real gfx942 build carries about 364k solutions across `aquavanjaram/gfx942*`, so the synthetic size matches.

Commit [`62c38e295b0`](https://github.com/newling/rocm-libraries/commit/62c38e295b0177599af95fa995b7fd3c6db512c2) changes the following:

- `initLibraryMapping` stores only the path.
- A `uidMapping()` accessor loads the file once (`std::call_once`) on the first UID lookup.
- Both `getSolutionByUid` overloads use the accessor.
- A new test, `UidMappingLoadsOnFirstUidLookup`, fails on the original, because the map is populated right after `initLibraryMapping`, and passes on the branch.

If the selection PR keeps the string-keyed msgpack form, decoding the map as a native integer-keyed msgpack map, or as a sorted array, would also cut the one-time cost.

## Suggestions

### 1. `getSolutionByUid(problem, hardware, uid)` loads the shard twice

`projects/hipblaslt/tensilelite/include/Tensile/MasterSolutionLibrary.hpp:471`

The explicit `loadLibrary(it->second)` is redundant. `getSolutionByIndex` goes through `resolveSolutionByIndex`, whose first step is `loadLibrary(index)`. Commit [`59c6020b964`](https://github.com/newling/rocm-libraries/commit/59c6020b964be94b11a520a8e120a8821443dd39) removes the extra call, which also makes the two overloads symmetric.

### 2. The docs say generation "rejects" collisions; it replaces them

`projects/hipblaslt/docs/solution-uid.md:60-62`

One Tensile process, one Geko generation and one merge each redraw a zero, malformed or colliding UID. None of them fails. The only hard failure inside a build is `TensileCreateLibrary` rejecting an ambiguous map. The paragraph also repeats the "later step" sentence from line 9. Commit [`a374f7cf37a`](https://github.com/newling/rocm-libraries/commit/a374f7cf37a29ef27db2cd91f0263fa638dc76b2) corrects the wording.

### 3. Explain why the UID differs from both solution indices

`projects/hipblaslt/docs/solution-uid.md:16`

The document defines the UID, but it doesn't say why the existing numbers cannot serve. There are two of them:

- the `SolutionIndex` in each logic file, which is a position within that file and is renumbered by tuning, merge and Geko;
- the index behind `--solution_index`, `getIndexFromAlgo` and MatchTable, which `TensileCreateLibrary` assigns afresh for each build's set of architectures and files.

A reader can easily mistake the first for a stored identifier. Commit [`f433f447c55`](https://github.com/newling/rocm-libraries/commit/f433f447c55dbd39ff41176b4542a1e2424ad2f7) adds a short section that explains both, why the stored, position-independent, uncoordinated UID avoids their problems, and that stability depends on tools carrying the field forward.

### 4. State when a UID must change

`projects/hipblaslt/docs/solution-uid.md`, regeneration section

A UID identifies a logic record, not kernel content. It stays unchanged when a solution's parameters are edited in place, while the same kernel copied into another file or architecture directory gets a different UID. The docs mention regeneration only "after a duplicate is reported".

Consumers that record UIDs, such as tuning caches and the planned UID-keyed MatchTable, need a stated rule: should a parameter edit that changes the compiled kernel keep the UID? If it does, such consumers should also check the kernel name when replaying, as the offline-tuning validation does with indices today. This is a policy decision, so there is no commit.

## Commentary

**The dense index stays as the runtime's internal key.** The algo struct, lazy-shard ranges, predicate trees and MatchTable all use it, and the UID map is a layer on top. That is the right shape for an additive change. It also means the stable identity contract lives entirely in the YAML corpus and the generators, which is why actionable 2 matters more than any runtime check.

**The base62 codec now has a C++ copy in a client header.** It is correct (see Tests). When the next PR parses `--solution_uid`, a single C++ encode/decode pair in the library or TensileLite, tested against the Python vectors, would avoid a third implementation.

## Appendix A: non-editable Geko install keeps the copied UID

From any directory, install Geko non-editably into an isolated target, then call the helper as `from_full_dataframe` does:

```bash
python -m pip install --no-deps --target "$TMP_SITE" "$SRC_DIR/projects/hipblaslt/utilities/geko"
cd /tmp && PYTHONPATH="$TMP_SITE" python - <<'EOF'
import logging; logging.basicConfig(level=logging.WARNING)
from types import SimpleNamespace
import geko.library.uid_uniqueness as u
print("codec path exists", u._solution_id_gen_path().is_file())
origami = {"SolutionUID": "0uOrigami1"}
lib = SimpleNamespace(solutions=[dict(origami)])
print("assigned", u.assign_fresh_solution_uids([lib]))
print("same as Origami source:", lib.solutions[0]["SolutionUID"] == origami["SolutionUID"])
EOF
```

On the PR head this prints a warning, then `codec path exists False`, `assigned 0` and `same as Origami source: True`. On the suggestion branch, the call without a checkout raises `FileNotFoundError`. With `hipblaslt_path="$SRC_DIR/projects/hipblaslt"` it assigns one fresh UID.

## Appendix B: UID map load cost

Generate a gfx942-sized map with the PR's own writer (from `projects/hipblaslt/tensilelite`):

```python
from tensilelite import LibraryIO
from tensilelite.Common.SolutionIdGen import generate_solution_id
m = {}
while len(m) < 364179:
    m[generate_solution_id()] = len(m)
LibraryIO.write("$OUT/TensileLiteLibrary_lazy_gfx942_UidMapping", m, "msgpack")
```

Then time the runtime loader, linking against `libtensilelite-host` from a host build:

```cpp
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <map>
#include <malloc.h>
#include <string>

namespace TensileLite
{
    std::map<uint64_t, int> LoadUidMapping(std::string const& filename);
}

static long rssKb()
{
    std::ifstream status("/proc/self/status");
    std::string   line;
    while(std::getline(status, line))
        if(line.rfind("VmRSS:", 0) == 0)
            return std::stol(line.substr(6));
    return -1;
}

int main(int argc, char** argv)
{
    long before  = rssKb();
    auto start   = std::chrono::steady_clock::now();
    auto mapping = TensileLite::LoadUidMapping(argv[1]); // path without .zlib
    auto stop    = std::chrono::steady_clock::now();
    malloc_trim(0);
    std::printf("entries=%zu load_ms=%.1f retained_rss_mb=%.1f\n",
                mapping.size(),
                std::chrono::duration<double, std::milli>(stop - start).count(),
                (rssKb() - before) / 1024.0);
}
```

Three runs gave `entries=364179`, `load_ms` 196–230, and `retained_rss_mb=22.4`. A `getrusage` variant measured an 82–84 MB peak-RSS increase during the load. The compressed file is 2.4 MB.

## Appendix C: corpus coverage commands

```bash
# Strict scan at the PR head (from projects/hipblaslt/tensilelite)
HIPBLASLT_REQUIRE_SOLUTION_UID=1 HIPBLASLT_UID_TEST_PROCESSES=8 \
  python -m pytest -q --noconftest tensilelite/Tests/unit/test_solution_uid_uniqueness.py
# -> 178 solution(s) ... are missing SolutionUID

# Approximate line counts on any ref (from the repository root)
L=projects/hipblaslt/library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full
git grep -h -c -E '^\s*-?\s*SolutionIndex:' origin/develop -- $L | awk '{s+=$1} END {print s}'
git grep -h -c -E '^\s*-?\s*SolutionUID:'   origin/develop -- $L | awk '{s+=$1} END {print s}'
# develop dcfd28a87c2: 708205 vs 702199
```

## Branch handoff

The branch [`review/pr14268-v2`](https://github.com/newling/rocm-libraries/tree/review/pr14268-v2) is based on the reviewed head [`fb3c2b3e7cb`](https://github.com/ROCm/rocm-libraries/pull/14268/commits/fb3c2b3e7cbb41d9be7986e3f3eafb5b02a27e73), and its tip is [`f433f447c55`](https://github.com/newling/rocm-libraries/commit/f433f447c55dbd39ff41176b4542a1e2424ad2f7). The commits, in order:

- [`7af83079333`](https://github.com/newling/rocm-libraries/commit/7af830793338475009caa10dc9d292baf40ed84d) — actionable 1, Geko checkout binding and missing-codec error
- [`59c6020b964`](https://github.com/newling/rocm-libraries/commit/59c6020b964be94b11a520a8e120a8821443dd39) — suggestion 1
- [`a374f7cf37a`](https://github.com/newling/rocm-libraries/commit/a374f7cf37a29ef27db2cd91f0263fa638dc76b2) — suggestion 2
- [`62c38e295b0`](https://github.com/newling/rocm-libraries/commit/62c38e295b0177599af95fa995b7fd3c6db512c2) — actionable 3, UID map read on first lookup
- [`f433f447c55`](https://github.com/newling/rocm-libraries/commit/f433f447c55dbd39ff41176b4542a1e2424ad2f7) — suggestion 3

Validation on the final tip:

- full Geko unit suite: 559 passed, 44 skipped
- TensileLite UID Python tests: 114 passed
- TensileLite host gtest: 659 passed, 8 skipped
- `UidMappingLoadsOnFirstUidLookup` fails on the original header
- clang-format 18 on changed lines, black on changed Geko files, whitespace checks and root pre-commit: all pass

Omitted:

- Actionable 2 (UID persistence policy, backfill, strict and continuity gates) and suggestion 4 (UID change rule) are policy decisions.
- The device-library build and GPU run were not performed; a gfx942-sized UID map exercised the runtime load cost instead.
