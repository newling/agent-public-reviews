This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#16265](https://github.com/ROCm/rocm-libraries/pull/16265)

Reviewed head: `c65fb3722189504cc037a8310017941a876bbf21`, the same revision as the [second review](https://github.com/newling/agent-public-reviews/blob/deceeb8e70c0d46dd5772c743599f3df94d5f98a/rocm-libraries/review_pr16265_v2.md). This review is focused on design and placement: where the new files live, and the high-level choices this first PR of the bindings stack fixes for the PRs after it. For context it reads the file lists and descriptions of the stacked PRs (#16266, #16269, #16272, #16273, #16275), but it does not review their code. It does not repeat the correctness findings of the earlier reviews. Existing PR discussion was not an input.

Suggestion branch: none. Each item below either changes paths that every later PR in the stack touches or needs a decision from the author, so none is implemented here. The second review's suggestion branch, [review/pr16265-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr16265-v2-suggestions), still applies.

## Tests

No new builds. The reproduction for item 2 uses the second review's Linux install, built against ROCm 7.1.0 with Python 3.12. The HIP Python observations come from the public `ROCm/hip-python` repository and its PyPI releases.

## Summary

The bindings are in the right place. `projects/hipblaslt/python/` follows the repository's convention for bindings that live beside their library. hipDNN uses the same model: its `CMakeLists.txt` says "Python bindings are a standalone CMake project that consumes installed hipDNN artifacts", and they are under `projects/hipdnn/python/`. Origami and HostNumerics also keep their bindings in a `python/` directory next to the library. Keeping the bindings in the library's own tree matters, because a PR that changes hipBLASLt's C API can update and test the bindings against the checkout's headers in the same change. `test_errors.py` already relies on this. Keeping the bindings out of hipBLASLt's CMake and TheRock suits a development tool.

This first PR is the time to settle three things that will otherwise be inherited by six PRs: the layout inside `python/`, the package's identity (its name, its version, and its relationship to the existing HIP Python bindings), and how much policy the import-time loader carries. The items below are ordered by how expensive they become to change once the stack lands.

## Actionable items

### 1. State how these bindings relate to HIP Python's `rocm.bindings.hipblaslt`

[`DESIGN.md:5–7`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/DESIGN.md#L5-L7), PR description (Motivation)

The description says hipBLASLt "has no supported Python interface". AMD's HIP Python project (`ROCm/hip-python`) publishes `rocm-bindings-libraries` on PyPI, currently at 10.0.0.0.1.2, and it contains `rocm.bindings.hipblaslt`: Cython bindings generated from the hipBLASLt C headers. Its `examples/0_Basic_Usage/hipblaslt_gemm.py` runs a complete GEMM through matrix layouts, a matmul descriptor with attributes, a preference, `hipblasLtMatmulAlgoGetHeuristic` and `hipblasLtMatmul`. That covers much of the surface the stack plans to bind in #16272 (handle and descriptors) and #16275 (heuristic query and matmul). None of the six PR descriptions or diffs mentions HIP Python.

There are good reasons to keep separate bindings here. They build against the checkout's headers, so they can test a hipBLASLt change in the same PR. They are tied to one exact build. The validation the stack adds (scale types, workspace size, operand extents, dtype checks) goes beyond direct C calls. And the planned solution-index work presumably reaches into the C++ `hipblaslt-ext` API, which bindings generated from C headers do not cover. But the reader of `DESIGN.md` and the reviewers of #16272 and #16275 need that reasoning stated. Add a short section to `DESIGN.md` that names HIP Python and chooses one position:

1. Build the low-level C layer on `rocm.bindings.hipblaslt` (and its loader; see item 4), and focus this stack on what HIP Python does not provide; or
2. Keep independent bindings, and state why HIP Python cannot serve the testing workflow, which of the planned PRs duplicate its surface, and why.

Correct the description's motivation to match. This needs to be settled before #16272 and #16275, whose scope it determines.

### 2. Use a `src/` layout so the source tree can't shadow the installed package

[`pyproject.toml:25`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/pyproject.toml#L25), [`CMakeLists.txt:79–80`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/CMakeLists.txt#L79-L80)

The importable package is at `python/hipblaslt/`, directly in the project directory, and the C++ sources are in `python/src/`. Any Python started in `projects/hipblaslt/python/` therefore imports the uninstalled source tree, which has no `_core` and no generated `_build_info.py`. With the bindings installed, running `python -c "import hipblaslt"` or `python -m pytest tests/test_import.py` from that directory fails with:

```text
ImportError: cannot import name '_build_info' from partially initialized module 'hipblaslt' (most likely due to a circular import)
```

That error points away from the actual cause. The same layout is why the `_build_info.py.in` template ships in the wheel, which the second review reports.

The repository's other binding packages use a `src/` layout: `shared/origami/python/src/origami/` and `projects/hipdnn/python/frontend_wheel_package/src/hipdnn_frontend/`. Move the Python package to `python/src/<package>/` and the nanobind sources to a sibling such as `python/csrc/`. Then set `wheel.packages` and the `CMakeLists.txt` source paths to match. Because #16269, #16272, #16273 and #16275 all add files under `python/hipblaslt/` and `python/src/`, the move is cheapest in this PR. Not implemented here, to avoid presenting the author with a conflicting rebase of the whole stack.

## Suggestions

### 1. Name the package for its role

[`pyproject.toml:5–7`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/pyproject.toml#L5-L7)

The distribution name, the import name and the version are all hipBLASLt's own: `pip` reports `hipblaslt 1.5.0`, and code writes `import hipblaslt`. Together these present the package as the hipBLASLt Python API, while its description says it is "a development and testing tool, not a ROCm deliverable", and AMD already ships `rocm.bindings.hipblaslt`. hipDNN's bindings use a role-specific name (`hipdnn_frontend`). A name such as `hipblaslt_devtools` or `hipblaslt_testing` would match the stated scope. It would also leave `hipblaslt` for a future official package; that name is currently unregistered on PyPI. Choose the name before later PRs and downstream scripts start using `import hipblaslt`.

### 2. Keep the bindings' own revision visible in the version

[`DESIGN.md:11–15`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/DESIGN.md#L11-L15)

Using hipBLASLt's version shows which library the bindings were compiled against, which is useful. But two builds of different bindings code against the same hipBLASLt then report the same version, and the version would read as a hipBLASLt release if the package were ever distributed. A PEP 440 local label (for example `1.5.0+<bindings revision>`) or a separate attribute recording the bindings revision would keep both pieces of information. This matters less if suggestion 1 gives the package its own identity.

## Scope decisions

### Narrow the loader to the build the bindings were compiled against

[`hipblaslt/_loader.py`](https://github.com/ROCm/rocm-libraries/blob/c65fb3722189504cc037a8310017941a876bbf21/projects/hipblaslt/python/hipblaslt/_loader.py)

The loader is 646 of the PR's roughly 2,000 added lines, plus about 400 lines of tests. It contains an ELF dynamic-section parser, scanning of `/proc/self/maps` and of Windows modules, and a five-step lookup. Three of the four findings in the first and second reviews come from this policy layer: dependency search paths, hard links, and `ROCM_PATH` replacing the build-time library. Every later PR depends on it.

The extension is compiled against one hipBLASLt: its status table, its version check and, in later PRs, its structure layouts and attributes. That suggests a narrower contract: load the library recorded at build time, or the library named by `HIPBLASLT_PY_LIBRARY`; keep the rocm-sdk step so that a process shares torch's copy; and detect mixtures. Discovering a library through `ROCM_PATH` and `ROCM_HOME` would then go away. Before growing the custom loader further, also check whether `rocm_sdk`'s own preloading, or `rocm-bindings-core` (described as providing "the POSIX shared-library loader, and ROCm path resolution" for HIP Python), can replace part of it.

These are policy questions for the author, not demonstrated defects beyond those already reported. The answer to item 1 may decide them.

## Commentary

Because the bindings sit inside hipBLASLt's tree, which is opted out of the root formatting hooks, the PR needs a `projects/hipblaslt/(?!python/).*` carve-out in four separate `.pre-commit-config.yaml` excludes. That is reasonable for one directory. If more hipBLASLt directories opt in later, a single shared exclusion anchor would be easier to maintain than per-hook lookaheads.

Handoff: no suggestion branch for this review. Items 1 and 2 are best resolved before the stacked PRs; the loader scope decision may follow from item 1.
