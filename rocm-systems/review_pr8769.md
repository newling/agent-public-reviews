This is a review from an agent with an automatic prompt from the reviewer

## Tests

**PR reviewed:** ROCm/rocm-systems#8769

**Commit reviewed:** `e9ff9606a790` (`fix(rocjitsu): report unsupported AQL
packet errors`).

**Public/repo status:** the repository, PR, base branch, and head branch are
public. The PR is open, is a draft, targets `develop`, and currently has merge
conflicts.

**Focused build:**

```bash
time -p cmake --build $BUILD_DIR \
  --target rocjitsu_tests daemon_test hsa_invalid_packet_test rocjitsu_bin \
  --parallel 8
```

Result: passed in 130.73s real, 975.11s user, 48.82s sys.

**Command-processor and RPC unit coverage:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='*Unsupported*Packet*:RemoteDriverQueueErrorTest.*'
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='*VendorSpecificReportsUnsupportedFormatsWithoutConsumption*'
```

Result before adding the review probe: 8/8 passed, 0 failed, 0 skipped,
0 errored. The commands took 0.03s and 0.06s real.

**Local ROCr end-to-end test:**

```bash
time -p ctest --test-dir $BUILD_DIR --output-on-failure \
  -R '^HsaInvalidPacketTest\.LocalModeReportsQueueError$'
```

Result: 1/1 passed in 0.84s real.

**Daemon ROCr end-to-end test:**

```bash
time -p timeout 30s $BUILD_DIR/tests/daemon_test \
  --gtest_filter='DaemonTest.UnsupportedPacketReportsQueueError'
```

Result: 1/1 passed in 0.68s real and passed in 10/10 additional runs. It also
passed while the other non-RCCL daemon tests ran concurrently.

The original release and Clang-sanitizer CI jobs timed out in this daemon test.
I could not reproduce that timeout locally on the same commit. The GCC
sanitizer job failed the local end-to-end test because the ASan runtime did not
appear first in the preloaded-library list. The PR requires a rebase because it
now conflicts with `develop`; rerun CI after resolving that conflict.

**Four-byte-aligned signal-write counterexample:**

```bash
time -p $BUILD_DIR/tests/rocjitsu_tests \
  --gtest_filter='RemoteDriverQueueErrorTest.AppliesFourByteAlignedSignalWrite'
```

Result: 0/1 passed in 0.02s real. The client logged
`Ignoring misaligned RPC signal write address` and left the signal value at
zero. The failure reproduced in 10/10 additional runs. The temporary test
passed pre-commit and was removed after validation.

## Summary

The PR changes unsupported AQL packets from successful no-ops into queue
faults. Unsupported standard and AMD vendor packets remain at the queue read
index, do not decrement their completion signal, and report the ROCr-compatible
packet-format exception. A faulted queue stops fetching further packets and
reports the error once.

For local mode, the command processor writes the exception signal and event
mailbox before routing the KFD interrupt. For daemon mode, queue creation
marshals the client-private signal metadata to the daemon; later queue faults
append signal stores to an ioctl response so the client can publish them before
returning the ready event. The RPC protocol version is correctly bumped for
this wire-format change.

The packet classification, queue-stopping behavior, local callback path,
legacy masks, daemon metadata marshalling, and one-shot error behavior all
look sound in focused testing.

## Actionable items

### 1. Do not drop valid four-byte-aligned queue error signals

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/kmd/linux/remote_driver.cpp:639`

The daemon response parser applies `RpcSignalWrite` only when the target address
is aligned to `alignof(uint64_t)`:

```cpp
if ((write.address & (alignof(uint64_t) - 1)) != 0)
  continue;
```

ROCr's `HsaUserContextSaveAreaHeader::ErrorReason` is a pointer to a 64-bit
signal payload, but its documented ABI requirement is only four-byte
alignment. A valid address with `address % 8 == 4` is therefore accepted by
ROCr/KFD but silently skipped by the daemon client. The error event can wake
while its signal value remains zero, so the queue callback does not receive the
intended packet-format error.

Support the ABI's four-byte alignment instead of dropping the store. The
implementation still needs release publication before returning the event, but
it cannot require stronger alignment than the source contract. Add the
regression below.

### 2. Make the new end-to-end test runnable under the sanitizer matrices

**File:** `emulation/rocjitsu/tests/CMakeLists.txt:1078`

The PR adds `hsa_invalid_packet_test`, applies `rj_configure_target(... TEST)`,
and then launches the instrumented binary through rocjitsu's preload path. The
GCC ASan/UBSan CI job fails before the test runs:

```text
ASan runtime does not come first in initial library list
```

Configure the child binary and launcher so the sanitizer runtime is loaded
before `librocjitsu.so`, or exclude the child from sanitizer instrumentation
and rely on the instrumented simulator/interposer. Require the local case to
pass in the GCC sanitizer CI job after the branch is rebased.

## Suggestions

### 1. Read queue metadata through a fault-tolerant user-memory helper

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/kmd/linux/remote_driver.cpp:64`

`queue_error_state()` directly `memcpy`s from the client-provided
`ctx_save_restore_address` and from an address derived from
`write_pointer_address`. A malformed or stale CREATE_QUEUE argument can
therefore crash the client process while the corresponding kernel ioctl would
normally reject an invalid user pointer.

Consider using a non-faulting self-read such as `process_vm_readv`, returning an
empty error-metadata record or `-EFAULT` when the memory is inaccessible. Add a
bad-pointer regression around CREATE_QUEUE serialization.

### 2. Tie the generic unsupported branch to hardware-defined support

**File:** `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/vm/amdgpu/command_processor.cpp:48`

The physical gfx1100 reproducer establishes the desired behavior for unknown
AMD vendor format `0xff`: leave it unconsumed and report
`HSA_STATUS_ERROR_INVALID_PACKET_FORMAT`. The KFD UAPI also provides the named
`EC_QUEUE_PACKET_UNSUPPORTED` and `EC_QUEUE_PACKET_VENDOR_UNSUPPORTED`
constants used by ROCr's exception handler.

Prefer those named constants over local numeric values `20` and `23`, and
document which standard packet types the modeled GPU hardware rejects. A
packet supported by the target hardware but merely unimplemented in rocjitsu
should remain visible as an emulator feature gap rather than being attributed
to an invalid application packet.

## Commentary

The release/Clang daemon timeout visible in the original CI run remains
unexplained, but it was not reproducible in isolated or repeated local runs.
Since the branch has substantial conflicts in the same command-processor, RPC,
driver, and test files, the meaningful integration result will be the
post-rebase CI run.

## Appendix: four-byte-alignment regression

```cpp
TEST(RemoteDriverQueueErrorTest, AppliesFourByteAlignedSignalWrite) {
  int sv[2];
  ASSERT_EQ(socketpair(AF_UNIX, SOCK_STREAM, 0, sv), 0) << strerror(errno);

  alignas(8) std::array<uint8_t, 16> storage{};
  uint8_t *target = storage.data() + 4;
  ASSERT_EQ(reinterpret_cast<uintptr_t>(target) & 7u, 4u);
  constexpr uint64_t kValue = 0x123456789abcdef0ULL;

  std::jthread server([&, server_fd = sv[1]] {
    rocjitsu::RpcHeader hdr{};
    if (!rocjitsu::rpc_recv_exact(server_fd, &hdr, sizeof(hdr)))
      return;
    std::vector<uint8_t> request(hdr.payload_bytes);
    if (!rocjitsu::rpc_recv_exact(server_fd, request.data(), request.size()))
      return;

    auto *ireq = reinterpret_cast<rocjitsu::RpcIoctlRequest *>(request.data());
    const rocjitsu::RpcSignalWrite write{
        reinterpret_cast<uint64_t>(target),
        kValue,
    };
    rocjitsu::RpcHeader response{};
    response.opcode = rocjitsu::RPC_IOCTL;
    response.request_id = hdr.request_id;
    response.payload_bytes = ireq->args_bytes + sizeof(write);
    rocjitsu::rpc_send_exact(server_fd, &response, sizeof(response));
    rocjitsu::rpc_send_exact(server_fd, request.data() + sizeof(*ireq), ireq->args_bytes);
    rocjitsu::rpc_send_exact(server_fd, &write, sizeof(write));
    ::close(server_fd);
  });

  kfd_ioctl_get_version_args args{};
  rocjitsu::RemoteDriver driver(sv[0]);
  ASSERT_EQ(driver.ioctl(AMDKFD_IOC_GET_VERSION, &args), 0);

  uint64_t actual = 0;
  std::memcpy(&actual, target, sizeof(actual));
  EXPECT_EQ(actual, kValue);
}
```
