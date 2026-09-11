> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#11987](https://github.com/ROCm/rocm-libraries/pull/11987)

## Tests

Host-only probes of the new decision helper passed for the `NOT_SUPPORTED` fallback, clamp, match, and other-error paths. The complete `hipblaslt-test` target could not be configured locally because the required `msgpackc-cxx` CMake package is unavailable. `git diff --check` passed. Public pre-commit and the hipBLASLt ASAN build pass; Math CI is still running, while the failing Multi-Arch summary belongs to a cancelled run whose build and test jobs were skipped.

## Summary

This PR prevents ordinary benchmark runs from initializing AMD-SMI when monitoring is disabled, then makes an explicitly enabled monitor tolerate a missing PCI BDF by choosing an AMD-SMI processor ordinal instead of throwing. The direct tests cover the extracted status decision, and making the AMD-SMI dependency public correctly supplies the newly direct header dependency to consumers.

The fallback still needs to preserve the selected device across AMD-SMI sockets; otherwise it can emit plausible but incorrect telemetry for a different GPU.

## Actionable items

### Retain socket identity when selecting a BDF-less device

`projects/hipblaslt/clients/common/src/efficiency_monitor.cpp:484-523`

`hipDeviceIndex` identifies a visible HIP device across the host, but `deviceCount` is the number of processor handles only in the socket currently being iterated. On the first `AMDSMI_STATUS_NOT_SUPPORTED`, the new branch immediately returns `selectFallbackAmdsmiIndex(hipDeviceIndex, deviceCount)`. For example, with one processor on socket 0 and the requested HIP device 1 on socket 1, the fallback clamps `1` to `0` and `setDeviceId()` subsequently uses socket 0's `m_processorHandles[0]`. The benchmark then reports frequency and efficiency values for the wrong accelerator rather than reporting that its requested device could not be identified.

Keep a processor handle (or socket/index pair) in the fallback result and choose it only after considering the handles from all sockets. If an ordinal mapping cannot be established reliably, disable the monitor for that run with a clear warning instead of substituting a different device. Add a regression test that models the two-socket case; the present helper accepts only a per-socket count, so it cannot represent this boundary.

## Suggestions

None.

## Commentary

The `enabled()` guard in the benchmark is a useful narrow fix for the original non-telemetry startup path, and retaining the non-`NOT_SUPPORTED` error behavior avoids masking unrelated AMD-SMI failures.

## Appendix: minimal multi-socket fallback probe

```cpp
#include "efficiency_monitor.hpp"
#include <cassert>

int main()
{
    // AMD-SMI is enumerating socket 0, which has one processor. HIP device 1
    // belongs to a later socket, but BDF lookup is unavailable on socket 0.
    const auto fallback = decideBdfMatch(AMDSMI_STATUS_NOT_SUPPORTED,
                                         /*smiIndex=*/0,
                                         /*amdSmiPciId=*/0,
                                         /*hipPciId=*/0,
                                         /*hipDeviceIndex=*/1,
                                         /*amdsmiDeviceCount=*/1);
    assert(fallback.action == BdfMatchAction::ReturnIndex);
    assert(fallback.index == 0);
}
```

In `GetAMDSMIIndex()`, that `0` is returned immediately and is used to index the processor vector for the current, first socket.
