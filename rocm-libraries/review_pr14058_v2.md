This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#14058](https://github.com/ROCm/rocm-libraries/pull/14058)

**Reviewed head / base for both branches:** [1002c9cb6b8f](https://github.com/ROCm/rocm-libraries/commit/1002c9cb6b8fcaf0600e3d3f60812285f3940d31)

**Current design with fixes:** [review/pr14058-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14058-suggestions)

**Optional alternative:** [review/pr14058-compact-metadata](https://github.com/newling/rocm-libraries/tree/review/pr14058-compact-metadata)

**Changes from the reviewed head:** [current-design fixes](https://github.com/newling/rocm-libraries/compare/1002c9cb6b8fcaf0600e3d3f60812285f3940d31...review/pr14058-suggestions) · [alternative](https://github.com/newling/rocm-libraries/compare/1002c9cb6b8fcaf0600e3d3f60812285f3940d31...review/pr14058-compact-metadata)

The branches are independent choices based on the same PR head. The alternative does not need to land before the current design.

| Branch | Item | Commit |
| --- | --- | --- |
| [review/pr14058-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14058-suggestions) | 1. Preserve duplicate keys written in other YAML forms | [64e5079205d](https://github.com/newling/rocm-libraries/commit/64e5079205d0ce9d3b2681d007fe3c2392ef83aa) |
| [review/pr14058-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14058-suggestions) | 2. Verify that a matched line is outside a scalar or collection | [d7720b938cc](https://github.com/newling/rocm-libraries/commit/d7720b938ccced9d86e6fd97c596308f13b372fe) |
| [review/pr14058-compact-metadata](https://github.com/newling/rocm-libraries/tree/review/pr14058-compact-metadata) | Optional smaller metadata and ordinary whole-document parsing | [8d8c566ba09](https://github.com/newling/rocm-libraries/commit/8d8c566ba0937402ba23d9469e017a144bad749e) |

## Tests

Matching rocisa built with Clang 23 and Python 3.12; submitted primary tests: 155 passed; current-design fixes: 164 primary and 190 caller tests passed; alternative: 369 focused metadata, CLI and caller tests passed with 115 unchanged saved expected results; pure-Python loader checks, root pre-commit, B506 and changed-file Flake8 passed.

All nine new correctness regressions fail on the submitted implementation and pass on both accompanying branches. The alternative also passes 33 configuration-reader cases with the pure-Python loader. Its shipped-metadata check fails when supplied the original graph-bearing metadata and passes after graph removal. Tests cover inference of a missing argument descriptor, explicit descriptors, and a single YAML parse in either case. The removed scanner assertions were replaced by value-based YAML cases and the distribution check; no saved expected results were rewritten.

For all 248 kernels, both configuration-read operations return identical results across the submitted PR, the fixes, the alternative and ordinary full parsing of the original files. All retained metadata fields match after removing only the two graph entries. All 70 modified kernels assemble with AMD Clang 24 for their recorded targets (69 gfx950 and one gfx942); every object section other than the metadata note matches the original, including executable instructions, descriptors, symbols and relocations.

At the publication check on 2026-10-22, the reviewed head was unchanged. [TensileLite coverage / Linux](https://github.com/ROCm/rocm-libraries/actions/runs/39796231407/job/119884214510) now passes, as do pre-commit and the component summary. [The C++ coverage check](https://app.codecov.io/gh/ROCm/rocm-libraries/pull/14058) reports 48.93% against an 80% target and fails; its cause is not established here. The PR changes no C++ code, and `codecov.yml` carries that coverage flag forward. Math CI and the multi-architecture math jobs remain pending. The passing Multi-Arch ASAN summary has a skipped Linux lane. These results do not establish completion of the quick tier under its 15-minute cap.

## Summary

TensileLite reads configuration embedded in assembly files for custom GPU functions, called kernels. This change selects PyYAML's C implementation and extracts the small `custom.config` entry before parsing. It reads the remaining metadata only when it must infer an argument descriptor. That avoids constructing the large rocRoller graph for kernels with explicit descriptors.

The tests check the extracted text itself, preserving a useful distinction between returning the right configuration and actually using the faster path. Coverage includes comments, block-scalar newlines, external anchors, duplicate plain keys and a representative large kernel. The accompanying fixes address two valid YAML layouts that produce results inconsistent with parsing the document as a whole. Keeping this design with those fixes is a reasonable option; the alternative below offers a smaller reader and smaller distributed files, with a measured speed tradeoff.

## Actionable items

### 1. Preserve duplicate keys written in other YAML forms

[`CustomKernels.py:210`](https://github.com/ROCm/rocm-libraries/blob/1002c9cb6b8fcaf0600e3d3f60812285f3940d31/projects/hipblaslt/tensilelite/tensilelite/CustomKernels.py#L210) and [`CustomKernels.py:241–251`](https://github.com/ROCm/rocm-libraries/blob/1002c9cb6b8fcaf0600e3d3f60812285f3940d31/projects/hipblaslt/tensilelite/tensilelite/CustomKernels.py#L241): the duplicate check recognizes only the literal `custom.config:` spelling. For this valid document, a whole-block parse returns `{"A": 2}`, while the submitted configuration reader returns `{"A": 1}`:

```yaml
custom.config: {A: 1}
"custom.config": {A: 2}
```

The same regression occurs with single quotes, escaped characters in a quoted key, an explicit `? custom.config` key, or whitespace before the colon. A slice that parses successfully cannot detect these later overrides, so the exception fallback never runs. This can silently retain an earlier tuning value or argument configuration.

Fall back to the whole document when a column-zero key uses quoted or explicit syntax, including tags, anchors and aliases. Recognize whitespace before the colon when detecting repeated plain keys. Commit [64e5079205d](https://github.com/newling/rocm-libraries/commit/64e5079205d0ce9d3b2681d007fe3c2392ef83aa) implements this conservative fallback and adds five regression cases. Every shipped kernel still takes the slice.

### 2. Verify that a matched line is outside a scalar or collection

[`CustomKernels.py:241–246`](https://github.com/ROCm/rocm-libraries/blob/1002c9cb6b8fcaf0600e3d3f60812285f3940d31/projects/hipblaslt/tensilelite/tensilelite/CustomKernels.py#L241): column zero does not establish that a line is a top-level YAML key. Multiline quoted strings can contain an apparent entry there:

```yaml
note: "text
custom.config: {A: 1}
end"
```

The whole document contains only `note`. The submitted reader nevertheless returns `{"A": 1}`, because the middle line parses independently. Previously it raised `RuntimeError` for the missing configuration. A flow sequence containing the same line is likewise accepted despite the document being a list. The existing quoted-scalar test catches this only when there is another matching line later.

Before slicing a match after preceding content, establish that the prefix is a complete top-level mapping. Fall back to the whole document when the prefix cannot parse independently or is not a mapping. Commit [d7720b938cc](https://github.com/newling/rocm-libraries/commit/d7720b938ccced9d86e6fd97c596308f13b372fe) implements that check and adds four cases covering double and single quotes, a nested quoted string, and a flow sequence. Comment-only prefixes avoid the extra parse. This commit follows item 1 on the suggestion branch.

## Suggestions

### Optionally omit diagnostic graphs and parse the document normally

Current reader: [`CustomKernels.py:224–283`](https://github.com/ROCm/rocm-libraries/blob/1002c9cb6b8fcaf0600e3d3f60812285f3940d31/projects/hipblaslt/tensilelite/tensilelite/CustomKernels.py#L224). Producer controls: [`Settings.hpp:213–223`](https://github.com/ROCm/rocm-libraries/blob/1002c9cb6b8fcaf0600e3d3f60812285f3940d31/shared/rocroller/lib/include/rocRoller/Utilities/Settings.hpp#L213) and [`AssemblyKernel.hpp:130–150`](https://github.com/ROCm/rocm-libraries/blob/1002c9cb6b8fcaf0600e3d3f60812285f3940d31/shared/rocroller/lib/include/rocRoller/Serialization/AssemblyKernel.hpp#L130).

Most of the input is an optional record of how rocRoller constructed each kernel. TensileLite does not use that graph to read settings or prepare arguments. Omit `.kernel_graph` and `.kernel_graph_dot` from shipped files, retain `.command` and all other fields, and let the normal YAML loader read the complete document once. This removes the layout scanner and its fallback rules. Quoted keys, repeated keys, multiline strings and external anchors then follow normal YAML interpretation automatically. Invalid YAML anywhere in the retained document is reported again.

Commit [8d8c566ba09](https://github.com/newling/rocm-libraries/commit/8d8c566ba0937402ba23d9469e017a144bad749e) implements this choice on [review/pr14058-compact-metadata](https://github.com/newling/rocm-libraries/tree/review/pr14058-compact-metadata), independently of the two fixes. It removes only the graph entries from 70 files, reducing embedded YAML across all 248 kernels from 70.23 MB to 4.28 MB, or 93.9%. The assembly instructions and every retained field are preserved. It replaces the reader with ordinary full parsing and reuses that result when inferring a missing descriptor. The large deletion count is generated graph text.

The existing export controls are `ROCROLLER_SERIALIZE_KERNEL_GRAPH=0` and `ROCROLLER_SERIALIZE_KERNEL_GRAPH_DOT=0`. Both must be set: DOT's default follows assembly saving. The commit adds `projects/hipblaslt/tensilelite/docs/custom-kernel-metadata.md` with these instructions and a unit test that rejects graph records in any shipped rocRoller kernel. `rocroller-gemm generate --graph` can save diagnostic graphs separately. The runtime reader gains no new stripping code or secondary configuration file.

### Performance comparison

The PR already supplies speed measurements. Its description reports all-kernel preparation at 155.6 seconds before the change and 1.43–1.45 seconds after it, plus collection and CLI measurements. Those are author measurements; the table below is a separate local comparison of the exact submitted head and both review branches.

Each run uses a fresh Python 3.12 process on the same Linux host, PyYAML's C safe loader, all 248 kernels and an explicit kernel directory. It includes file reads and recursive discovery. Three interleaved runs were made per design; ordinary full parsing of the original files was run once per operation. Times cover loading metadata and preparing settings, without GPU execution.

| Operation over all 248 kernels | Original files, full C parsing | Submitted PR | Current design with fixes | Smaller metadata, full C parsing |
| --- | ---: | ---: | ---: | ---: |
| `readCustomKernelConfig` | 19.87 s | 0.529–0.554 s | 0.566–0.579 s | 1.262–1.300 s |
| `getCustomKernelConfig` | 20.89 s | 0.671–0.908 s | 0.927–0.931 s | 1.071–1.299 s |

The alternative is about 17 times faster than full C parsing of the original files for kernel preparation. Relative to that baseline, it retains about 98% of the repaired current design's time savings for `getCustomKernelConfig` and about 96% for configuration reading alone. The current design remains faster in these measurements: median kernel preparation is 0.93 seconds versus 1.26 seconds. Both return identical settings. These numbers do not predict the full test job's wall time or indicate faster GPU calculations.

## Commentary

The current design avoids parsing unrelated metadata even if more of it is added later. Its two local fixes preserve that benefit for every shipped kernel, but the reader still contains rules approximating YAML layout and intentionally overlooks malformed data outside the extracted settings. Its advantage is the smaller source change and slightly lower measured loading time.

The alternative moves the main source of excess data out of the shipped files. It uses the existing generator controls and reduces reader code, so future changes to YAML spelling or layout need no scanner updates. New kernels must follow the export guide; the corpus test makes a reintroduced diagnostic graph visible in the unit lane. Ordinary retained metadata can still grow, and archived graph-bearing external kernels still parse correctly but cost more time. Detailed graph inspection of the shipped files requires separate diagnostic artifacts or regeneration.

Host-side reader and caller tests directly exercise the current-design fixes. For the alternative's changed assembly files, compiling all affected kernels and comparing object sections provides additional evidence that deleting diagnostic metadata preserves execution. No GPU execution, full generator run, whole unit suite or hosted quick-tier run was performed on the alternative. Before adopting that option, use the normal gfx950 and gfx942 build/test lanes to confirm the packaging and installed-resource behavior; local byte comparisons do not replace that lane.

Both requested branches are published in the fork and remain based on the reviewed PR head. [review/pr14058-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr14058-suggestions) contains items 1 and 2 in separate commits; [review/pr14058-compact-metadata](https://github.com/newling/rocm-libraries/tree/review/pr14058-compact-metadata) contains the independent alternative in one commit. Choosing the current design does not depend on adopting the alternative. The original review is preserved. This review is published in the review repository; no GitHub review or comment was posted on the PR, and its description is unchanged.
