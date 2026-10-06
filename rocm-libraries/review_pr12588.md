This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#12588](https://github.com/ROCm/rocm-libraries/pull/12588)

Reviewed head: [1d38aaf48da](https://github.com/ROCm/rocm-libraries/commit/1d38aaf48da6878c8dcd285963a3ab7873a8cbaa). Incremental base: [#12587](https://github.com/ROCm/rocm-libraries/pull/12587) at [4313b77c4df](https://github.com/ROCm/rocm-libraries/commit/4313b77c4df2fd2f12c9f69d22a86891eab3f0f8).

Suggestion branch: [review/pr12588-v2-suggestions](https://github.com/newling/rocm-libraries/tree/review/pr12588-v2-suggestions), based on that exact head ([suggestion diff](https://github.com/newling/rocm-libraries/compare/1d38aaf48da6878c8dcd285963a3ab7873a8cbaa...a66feec42e3f76b0aada46168f78b00f05263e23)). Its sole additional commit is [a66feec42e3](https://github.com/newling/rocm-libraries/commit/a66feec42e3f76b0aada46168f78b00f05263e23), the default-stream calibration suggestion. Its implementation and previously validated tree are unchanged.

## Tests

The submitted host library, tests and benchmark build; all 21 store tests and 26 available tuner GPU cases pass on MI300X, and the same tuner cases pass with the calibration change.

The scoped gfx942 library has no candidate for the FP8 FNUZ round trip, and the device-local scratch test needs two visible GPUs; those two cases were skipped. Native Windows and exhaustive datatype, epilogue and layout coverage were omitted. These results are retained from the unchanged revisions; the calibration counterexample is described below.

CI remains red. The head embeds [#12586](https://github.com/ROCm/rocm-libraries/pull/12586) before its Windows and test-packaging corrections; the [cache-layer review](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12587.md) describes the diagnosed inherited failures and unresolved CI coverage.

## Summary

This PR supplies the runtime search behind `HIPBLASLT_TUNING_MODE=tune`. The first eligible matmul of an uncached problem measures supported candidates synchronously on the caller's stream and saves the fastest measured solution. Library-owned output and workspace scratch isolate the measurements from the caller's output.

An explicit algorithm remains authoritative for the actual call, even if that call triggers tuning. A null-algorithm call can immediately launch the winner. Failed and budget-stopped attempts fall back and are latched to avoid repeatedly stalling the process. This version discards truncated searches; [#12589](https://github.com/ROCm/rocm-libraries/pull/12589) adds partial winners, while sibling [#12590](https://github.com/ROCm/rocm-libraries/pull/12590) makes the benchmark use this search.

The stream-drain guard and serialized scratch ownership are worth retaining: outstanding candidate work must finish before another thread reuses the allocation, including after failures. Resolving candidates through replay's index lookup also keeps the measured and subsequently retrieved solution consistent.

## Actionable items

No GEMM correctness defect was established in this layer. The timing and coverage improvements below are suggestions.

## Suggestions

### Calibrate flush cost on the default stream too

At [`tensile_host.cpp:3758`](https://github.com/ROCm/rocm-libraries/blob/1d38aaf48da6878c8dcd285963a3ab7873a8cbaa/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L3758), `ICacheFlush::current` uses `stream != nullptr` to decide whether to calibrate. HIP uses `nullptr` for the valid default stream. Consequently, `costUs(nullptr)` remains zero even though the timing loop launches the flush.

Saved default-stream timings include the flush overhead, while explicit-stream timings subtract it. Subtracting a common cost normally preserves candidate ordering, so this deserves limited weight: it is a timing-consistency defect, with no demonstrated wrong winner or GEMM result.

Commit [a66feec42e3](https://github.com/newling/rocm-libraries/commit/a66feec42e3f76b0aada46168f78b00f05263e23) separates the calibration request from the stream handle. `launch` requests geometry only; `costUs` requests calibration for any valid stream. The existing default-stream test reports zero flush cost before the change and a positive measured cost afterward, approximately 9.75 microseconds in the validation run.

### Add focused coverage for scratch extent boundaries

[`tensorSpanBytes` and `planScratch` at `tensile_host.cpp:3959`](https://github.com/ROCm/rocm-libraries/blob/1d38aaf48da6878c8dcd285963a3ab7873a8cbaa/projects/hipblaslt/library/src/amd_detail/rocblaslt/src/tensile_host.cpp#L3959) decide the memory candidates can access. The added integration tests mainly use contiguous, single-batch tensors. Add direct coverage for padded and broadcast strides, unequal C/D extents, gradient-bias spans, cap-induced rotation reduction and arithmetic overflow.

The important contract is that a conservative output extent remains large enough, while an uncertain input extent must never become permission to copy beyond the caller's allocation. Inspection of the guards and copy decisions did not establish an out-of-bounds defect. The tests would protect a consequential boundary against later changes.

Use whichever existing test boundary keeps this small; extracting a new helper is optional. No implementation is included because the useful change is coverage of these cases, whose placement needs a broader test change than the calibration fix.

## Commentary

The per-shape budget is a soft limit checked between candidates. It cannot cancel a submitted measurement batch. The process-wide lock protects shared scratch, but GPU work from unrelated callers can still perturb timings. Those constraints matter more than minor naming or factoring preferences.

The inherited [store persistence fixes](https://github.com/newling/agent-public-reviews/blob/main/rocm-libraries/review_pr12586_v2_with_fixes.md) matter here because this layer is the first production writer. They and [#12587](https://github.com/ROCm/rocm-libraries/pull/12587)'s profile fix are outside the accompanying branch. The scratch, failure-cleanup and support-probe paths did not reveal another concrete failure in this pass.

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

The final assertion fails on the submitted code and passes with [a66feec42e3](https://github.com/newling/rocm-libraries/commit/a66feec42e3f76b0aada46168f78b00f05263e23). The branch contains that fix only; direct scratch-boundary coverage and a shared-CI calibration assertion remain unimplemented.
