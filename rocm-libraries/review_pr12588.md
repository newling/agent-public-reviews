This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12588](https://github.com/ROCm/rocm-libraries/pull/12588)

Reviewed head: `1d38aaf48da6878c8dcd285963a3ab7873a8cbaa`. Incremental base: #12587 at `4313b77c4df2fd2f12c9f69d22a86891eab3f0f8`.

Suggestion branch: [review/pr12588-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12588-suggestions), based on that exact head. Its one additional commit is [a66feec42e3 — calibrate the instruction-cache flush on the default stream](https://github.com/newling/rocm-libraries/commit/a66feec42e3f76b0aada46168f78b00f05263e23).

## Tests

The submitted host library, tests and benchmark build; all 21 store tests and 26 tuner GPU cases pass on MI300X, with two skips, and the same tuner cases pass after the fix.

The scoped gfx942 device library provides no candidate for the FP8 FNUZ test, and only one device was exposed, so the FP8 round trip and `ScratchIsDeviceLocal` were not exercised. The runs cover actual tuning, nonzero numerical output, replay, explicit and null algorithms, failure injection, budget stops and concurrent calls. They do not cover every epilogue or layout. The calibration counterexample logs `0 us per launch` before the fix and a positive measured cost afterward, approximately 9.75 microseconds on this worker.

The PR's CI snapshot remains red, including Linux test, Windows, ASAN and race jobs. The embedded #12586 lacks its current Windows and test-packaging fixes. The matching failures examined on #12587 are described in [that review](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12587.md); these local tests are not a substitute for restacking and rerunning the later heads.

## Summary

This is the stack's main behavioral change. #12586 defines persistence, and #12587 replays it. This PR lets the first eligible C-API matmul of an uncached problem measure supported kernels and save the fastest measured candidate. The search runs synchronously on the caller's stream, uses library-owned output/workspace scratch, and serializes tuning within the process. Later queries can reuse its result.

An explicit algorithm remains authoritative for the actual call, even if that call triggers tuning. A null-algorithm call can immediately launch the winner. Failed searches fall back, and expensive failed or budget-stopped attempts are latched to avoid repeating the stall. This PR discards a truncated search; keeping partial winners is deliberately left to #12589. #12590 separately routes the benchmark through this tuner.

The scratch isolation and the stream-drain guard are important design choices to retain. Candidate work must finish before another thread reuses the shared allocation, including when enumeration or measurement fails. Resolving candidates through the same index lookup used by replay also avoids timing one solution object and later retrieving a different one.

## Actionable items

### Calibrate the instruction-cache flush on the default stream

At [`tensile_host.cpp:3758`](https://github.com/ROCm/rocm-libraries/blob/1d38aaf48da6878c8dcd285963a3ab7873a8cbaa/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L3758), `ICacheFlush::current` uses `stream != nullptr` to decide whether calibration was requested. In HIP, `nullptr` is a valid default stream. Thus `costUs(nullptr)` creates or retrieves an entry whose cost stays zero, while the measurement loop still launches the flush on that stream.

Consequently, saved times for default-stream calls include flush cost, despite the documented subtraction. The same measurement on an explicit stream gets calibrated. Subtracting a common cost generally preserves candidate ordering, so this finding is about timing correctness and consistency; I did not demonstrate an incorrect GEMM result.

[a66feec42e3](https://github.com/newling/rocm-libraries/commit/a66feec42e3f76b0aada46168f78b00f05263e23) separates the calibration request from the stream handle. `launch` requests geometry only; `costUs` requests calibration for any valid stream, including `nullptr`.

## Suggestions

### Give scratch extent planning direct boundary tests

The new [`tensorSpanBytes` and `planScratch` helpers](https://github.com/ROCm/rocm-libraries/blob/1d38aaf48da6878c8dcd285963a3ab7873a8cbaa/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L3959) decide how much GPU memory candidates may read or write. Their overflow guards and distinction between an output upper bound and an input copy length are sensible, but the new integration tests mainly use contiguous, single-batch tensors.

Extract the pure extent/layout calculation into a privately testable helper and cover padded leading dimensions, broadcast batch strides, C/D sharing with different extents, gradient-bias strides, cap-induced reduction of rotation blocks, and arithmetic overflow. In particular, an expanded input span must disable copying that input, while an output span must remain large enough for the original strides. This is a suggestion about the new allocator's test boundary, not a demonstrated out-of-bounds write. I have not included the extraction in the branch because choosing that boundary would materially enlarge a focused calibration fix.

## Commentary

The default search can block a first call for minutes. Opt-in activation, an explicit start notice, progress reporting and a soft per-shape budget make that cost understandable. The budget is checked between candidates, so it is not a hard deadline. The process-wide lock protects scratch ownership; it does not isolate performance measurements from unrelated GPU work or coordinate multiple processes writing the same file.

“Matching the benchmark” should mean using the same measurement method, not guaranteeing the same winner across executions. Input data, competing GPU work, clock state and timing noise still matter. The cache's supported-problem check addresses whether a kernel can run; it cannot establish that a previous measurement remains the best one for a different workload environment.

The current descendants still embed the old #12586. Its [persistence fixes](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12586_v2_with_fixes.md) matter here because this is the first production writer. The inherited profile-name issue from #12587 is separate from the calibration commit above.

## Reproducing the calibration check

With a matching device library, run the existing default-stream test:

```bash
env -u HIPBLASLT_LOG_LEVEL HIPBLASLT_LOG_MASK=8 \
  "$BUILD_DIR/clients/hipblaslt-test" \
  --gtest_filter=TuningTune_pre_checkin.TuneWritesRowWithIdentityAndKeyFields \
  > calibration.log 2>&1
python3 - <<'PY'
import re
from pathlib import Path
text = Path('calibration.log').read_text()
assert '[  PASSED  ] 1 test.' in text
costs = re.findall(r'icache flush enabled, ([0-9.eE+-]+) us per launch', text)
assert costs and all(float(cost) > 0 for cost in costs)
PY
```

The final assertion fails on the submitted code and passes with the linked commit. The branch contains only that fix; no predecessor fixes or scratch-layout extraction are included. Native Windows, a complete device library and multi-device tests were omitted.
