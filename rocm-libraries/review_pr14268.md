This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14268](https://github.com/ROCm/rocm-libraries/pull/14268)

Reviewed head: `0a7e4f4a8d34e22a77bea654549e7f81001fd7fd`. Diff base: `03f14afc67660f699de2131b117b35d05e8905b6`. Scope: overall design, identity guarantees, migration, and integration boundaries.

Published suggestion branch: [review/pr14268-big-picture-20261026](https://github.com/newling/rocm-libraries/tree/review/pr14268-big-picture-20261026), based directly on the reviewed head. These commits can be inspected or cherry-picked independently.

| Review item | Commit | Change |
| --- | --- | --- |
| Numeric uniqueness | [ceeafc0430f](https://github.com/newling/rocm-libraries/commit/ceeafc0430f621dd32922be5ec1e8317456f977a) | Normalize decoded IDs and share collision handling with the YAML rewriter. |
| Numeric uniqueness | [ded72dec9ea](https://github.com/newling/rocm-libraries/commit/ded72dec9eaff33a1e90ae5b0101bba3ef46aa87) | Reject duplicate or zero IDs before writing the library mapping. |
| Runtime coverage suggestion | [caaf468e1ac](https://github.com/newling/rocm-libraries/commit/caaf468e1accd9df04538dc348d6996803d38563) | Exercise compressed 64-bit mapping and both native lookup overloads. |
| Persistence documentation | [a79fcf73fb7](https://github.com/newling/rocm-libraries/commit/a79fcf73fb787d9b34df7fa95367451e9c81a743) | Distinguish persisted, per-build, and absent runtime IDs. |

## Tests

Submitted host-library build, focused TensileLite/Geko Python suites, and a Python-to-C++ compressed metadata round trip passed; the suggestion branch's focused suites and native mapping tests also passed.

Three added counterexamples fail on the submitted code: alternate UID prefixes evade collision handling, UID lines with comments evade rewriting, and duplicate IDs silently overwrite mapping entries. The committed fixes make them pass. A wheel built from the submitted Geko sources reproduces the installed-package failure described below.

The native round trip checks a Python-written indexed solution and compressed UID mapping with `UINT64_MAX`, lazy shard resolution, both lookup overloads, repeated index lookup, unknown IDs, and older serialized metadata without a UID. The public getter with a real GPU handle and benchmark output were not exercised locally. Host checks are appropriate for these metadata changes; a new multi-architecture numerical sweep would add little evidence about UID identity.

Root pre-commit checks pass, and native additions use clang-format 18.1.4. Whole-file Python formatting/lint checks have pre-existing failures; comparison against the submitted code found no new formatting changes or lint diagnostics.

At the reviewed head, the automated UID-uniqueness, Geko, TensileLite Python, gfx90a ASAN, and gfx94X hipBLASLt lanes pass. Windows checks remain pending, and the hipBLASLt/TensileLite C++ coverage checks and gfx1250 FFM status are red. Those statuses were inspected but are not attributed to these UID changes.

## Summary

The PR carries a stored solution identifier from tuning logic into generated library metadata, translates it to the library's existing integer index, and exposes it through the extension API and benchmark output. Algorithm selection still uses the existing index, so this establishes identity without changing which GPU kernel executes.

That is a sensible migration boundary. Reusing the existing lazy index lookup avoids a second kernel-loading mechanism, and optional serialized fields keep older libraries readable. The central design question is whether every stage agrees on what an identifier names and when it remains stable. The implementation is close, but that agreement needs to hold at library assembly and across the supported installation paths.

## Actionable items

### Make numeric uniqueness an invariant through library assembly

Files: `projects/hipblaslt/tensilelite/tensilelite/Common/SolutionIdGen.py:199` and `:217`; `projects/hipblaslt/tensilelite/tensilelite/TensileCreateLibrary/Run.py:1513` in the reviewed head.

Generation compares UID strings, while serialization and lookup compare decoded integers. Both `0u5` and `0U5` are accepted by the codec and denote 5, but the collision helper keeps both. The independent line rewriter has the same mismatch and skips UID lines with YAML comments. When library creation builds its dictionary, equal numeric IDs overwrite one another. Two serialized solutions can therefore advertise one identifier while the mapping can recover only one of them.

Use one normalized representation for collision handling, reuse that handling in the rewriter, and validate the assembled per-architecture mapping before writing files. Reject a duplicate attached to different indices with a diagnostic identifying both indices. This check belongs at the build boundary because custom logic and IDs generated for missing fields do not necessarily pass through the repository's corpus checker.

Implemented in [ceeafc0430f](https://github.com/newling/rocm-libraries/commit/ceeafc0430f621dd32922be5ec1e8317456f977a) and [ded72dec9ea](https://github.com/newling/rocm-libraries/commit/ded72dec9eaff33a1e90ae5b0101bba3ef46aa87), with failing-before/passing-after counterexamples. The rewriter also preserves the YAML list marker and comment when replacing the UID.

### Give installed Geko an explicit dependency on the UID implementation

File: `projects/hipblaslt/utilities/geko/geko/library/uid_uniqueness.py:30`.

The helper locates TensileLite by walking four parents above its own source file. That works in the monorepo layout. The documented `pip install .` path places Geko in `site-packages`, where that traversal instead looks for `<venv>/lib/tensilelite/tensilelite/Common/SolutionIdGen.py`. Geko's wheel contains only its own package and does not install that file. Any nonempty call to `assign_fresh_solution_uids` fails with `FileNotFoundError`, which breaks final-library extraction through the newly changed dataframe functions.

Make the pure UID implementation available through the installed package's declared dependencies or packaged contents, or pass the configured hipBLASLt source root explicitly. Do not infer a source checkout from the installed module's location. Add a wheel-install smoke test executed outside the source tree; current source-tree tests cannot catch this failure.

No implementation commit: choosing the distribution/dependency boundary affects Geko packaging and its source-root API. The review preserves the exact small reproducer below rather than introducing a second codec or another path guess.

### State precisely which identifiers survive a rebuild

Files: `projects/hipblaslt/docs/solution-uid.md:3`; `projects/hipblaslt/library/include/hipblaslt/hipblaslt-ext.hpp:1161`.

The documentation describes a temporary identifier assigned during library loading. There are actually three cases: a UID persisted in logic YAML survives rebuilding; missing YAML fields receive an ID during Python library generation without being saved back; an older prebuilt file with no serialized UID remains zero in C++. The native probe confirms the last case. Benchmark users need this distinction before recording the new UID output as a stable reference.

Document these cases in the public getter and migration guide. Also say that the UID names a stored solution record: Geko creates a new record and ID when copying an Origami solution, while an Equality merge retains the existing record's ID when it matches the solution name.

Implemented in [a79fcf73fb7](https://github.com/newling/rocm-libraries/commit/a79fcf73fb787d9b34df7fa95367451e9c81a743). This changes the documentation without changing migration policy or runtime behavior.

## Suggestions

### Test the native mapping boundary directly

Files: `projects/hipblaslt/tensilelite/include/Tensile/MasterSolutionLibrary.hpp:211` and `:464`; `projects/hipblaslt/tensilelite/tests/MasterSolutionLibraryMapping_test.cpp:113`.

The added Python mapping test replaces both parsed solutions and the file writer, so it cannot detect 64-bit conversion, compression, or native lookup errors. Add a small host test that reads a compressed mapping containing IDs above 32 bits, resolves them through both lookup overloads, rejects an unknown ID, and verifies that missing UID metadata does not disable legacy index mappings.

Implemented in [caaf468e1ac](https://github.com/newling/rocm-libraries/commit/caaf468e1accd9df04538dc348d6996803d38563). It passes against the submitted runtime. The separate cross-language probe also passes, but its full generator-to-loader setup is not committed as a new testing framework. A direct public-getter smoke test in the existing GPU client lane remains useful when the next migration step starts consuming these identifiers.

## Commentary

The record-identity model fits the copy/merge behavior: identical kernel code can have distinct records and identifiers, while updates to an existing Equality record keep its identity. The current name-based merge policy is consequently part of the stability promise; replacing it with UID-based deduplication would change that model.

The UID table is generated and loaded eagerly with one entry per solution, although the solution metadata remains lazy. That is an explicit startup and memory cost of this representation. This review did not measure it; no performance regression is claimed.

The suggestion branch and this review are published. The source worktree is clean on [review/pr14268-big-picture-20261026](https://github.com/newling/rocm-libraries/tree/review/pr14268-big-picture-20261026) at [a79fcf73fb7](https://github.com/newling/rocm-libraries/commit/a79fcf73fb787d9b34df7fa95367451e9c81a743). The installed-Geko dependency decision and a real-handle API smoke test are the implementation/validation omissions. No PR description rewrite, GitHub review, or comment was made.

## Installed-package reproducer

Build and install Geko's wheel into an otherwise ordinary task environment, then run outside its source directory:

```sh
python -m pip wheel --no-deps "$SRC_DIR/projects/hipblaslt/utilities/geko" -w "$BUILD_DIR/wheels"
python -m pip install "$BUILD_DIR/wheels/geko-1.1.0-py3-none-any.whl"
cd "$BUILD_DIR"
python - <<'PY'
from types import SimpleNamespace
from geko.library.uid_uniqueness import assign_fresh_solution_uids

library = SimpleNamespace(solutions=[{"SolutionUID": "0u5"}])
assign_fresh_solution_uids([library])
PY
```

The submitted wheel raises `FileNotFoundError: SolutionIdGen.py not found: <venv>/lib/tensilelite/tensilelite/Common/SolutionIdGen.py`. The environment used for this check already had Geko's runtime dependencies and a built rocisa extension, so this is not a missing optional compiler dependency.
