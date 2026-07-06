This is a review from an agent with an automatic prompt from the reviewer

## Abridged Review: ROCm/rocm-systems#7383

**Commit reviewed:** `62ae2e2502` (`rocjitsu: kmd emulation + hsa hooks`)

This is the simple developer-style repro: configure with Ninja, build
everything, then run all tests until the first failure.

## Configure

```bash
rm -rf $BUILD_DIR
cmake -S $SRC_DIR/emulation/rocjitsu \
  -B $BUILD_DIR \
  -G Ninja \
  -DBUILD_TESTING=ON
```

Result: configure succeeded.

Notable configure output:

```text
-- rocminfo test enabled (found $ROCM_PATH/bin/rocminfo)
-- HSA init test enabled (found $ROCM_PATH/lib/libhsa-runtime64.so)
-- HSA translate test built but NOT registered with CTest (no RDNA4 GPU)
-- CDNA4->CDNA3 dispatch tests built but NOT registered with CTest (no CDNA3 GPU)
-- HSA DBI smoke test built but NOT registered with CTest (no gfx90a)
```

## Build

```bash
cmake --build $BUILD_DIR --parallel 8
```

Result: full build succeeded.

Timing:

```text
real 128.80
user 972.18
sys 53.41
```

## Run Tests

```bash
ctest --test-dir $BUILD_DIR \
  --output-on-failure \
  --stop-on-failure
```

Result: first failure occurs at test 1116.

CTest summary:

```text
99% tests passed, 1 tests failed out of 1116
Total Test time (real) = 140.14 sec

The following tests FAILED:
  1116 - GuestKfdMultiprocessTest.ForkedChildrenDoNotRemoveParentOverlay (Failed)
```

The failing test output:

```text
Running main() from $SRC_DIR/emulation/rocjitsu/third_party/googletest-src/googletest/src/gtest_main.cc
Note: Google Test filter = GuestKfdMultiprocessTest.ForkedChildrenDoNotRemoveParentOverlay
[==========] Running 1 test from 1 test suite.
[----------] 1 test from GuestKfdMultiprocessTest
[ RUN      ] GuestKfdMultiprocessTest.ForkedChildrenDoNotRemoveParentOverlay
$SRC_DIR/emulation/rocjitsu/tests/guest_kfd_test.cpp:132: Failure
Expected: (parent_fd) >= (0), actual: -1 vs 0
[  FAILED  ] GuestKfdMultiprocessTest.ForkedChildrenDoNotRemoveParentOverlay (1 ms)
```

## Possible Explanation

The failing test is launched through the DBT guest config:

```text
configs/guest_gfx950_on_gfx1201.json
```

That config requires a real gfx1201 host GPU. This machine has `<kfd-device>`, but
the local KFD topology reports the real GPU node as:

```text
gfx_target_version=110501
gpu_id=65504
```

So the machine is in the problematic middle case:

```text
<kfd-device> exists, but the real host GPU required by the selected DBT guest config is not present.
```

The test skips only when `<kfd-device>` is unavailable. It does not skip when the
configured DBT guest host ISA is unavailable, so `open("<kfd-device>")` fails under
the rocjitsu DBT guest launcher and the test hits a hard assertion.

## Suggested Fix

Gate DBT guest runtime tests on the actual host ISA required by the selected
config. For this test, do not register or run the gfx1201 DBT guest test unless
a gfx1201 host is present. Alternatively, make the test skip with a clear
message when the configured host ISA is unavailable.
