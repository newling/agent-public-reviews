> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#14689](https://github.com/ROCm/rocm-systems/pull/14689)

**Reviewed head:** [ff4ed4f0470](https://github.com/ROCm/rocm-systems/commit/ff4ed4f0470), stacked on #14688 `d8ebb9854cc` and #14687 `8202e50072c`; reviewed on 2026-11-04.

**Review mode:** follow-up. The reviewer asked for points no earlier reviewer has raised. The existing review threads and review bodies were read only to avoid repeating them. Settled topics are not raised again: ISA citations, modeling-choice wording, MEMVIOL, the 256-byte vs 2048-byte granularity, byte-granular race tracking, removal of `element_size_bytes`, naming, the i32-at-254 boundary tests, a fixture with a nonzero LDS base, the empty-`lds_ranges` wording, and the fully clipped fault test.

**Suggestion branch:** [review/pr14689-followup-20261104](https://github.com/newling/rocm-systems/tree/review/pr14689-followup-20261104), based on the reviewed head ([combined diff](https://github.com/newling/rocm-systems/compare/ff4ed4f04709cd3845b072fc1368785c34524f3d...a4f7f704afa3e73ea0c76388b04ff82986e9c9ab)). The commits are independent of each other.

| Commit | Item |
| --- | --- |
| [a4f7f704afa](https://github.com/newling/rocm-systems/commit/a4f7f704afa3e73ea0c76388b04ff82986e9c9ab) | [Describe accurately how other LDS paths treat the allocation end](#describe-accurately-how-other-lds-paths-treat-the-allocation-end) |
| [d2cb5e0f023](https://github.com/newling/rocm-systems/commit/d2cb5e0f0235a7425e0db75c829779d62cda3155) | [Document the allocation clipping in the race-detector guide](#document-the-allocation-clipping-in-the-race-detector-guide) |
| [3c2020ae838](https://github.com/newling/rocm-systems/commit/3c2020ae8385b933fe1780ad0bc5aba8c0019613) | [Check a partial store against an older LDS write](#check-a-partial-store-against-an-older-lds-write) |

## Tests

Clang 23 Release build: focused native tests (`*Tensor*:*Race*:IntervalSet.*:PerfsimPluginTest.*:GpuVmPipeline.*`) pass on the reviewed head (472/472) and on the suggestion branch (473/473). The companion gfx1250 corpus ([rocjitsu-test-corpus#83](https://github.com/ROCm/rocjitsu-test-corpus/pull/83) at `bbf7698`) passes 29/29 against the reviewed head, including both past-allocation cases.

## Summary

With this PR, an LDS address past the wave's allocation no longer rejects a tensor DMA instruction. Each element keeps the leading bytes that fit before the allocation end. A load writes only those bytes; a store reads the remaining bytes as zero. Observers receive byte ranges, and the race detector tracks exactly the bytes transferred. Execution, observation and detection agree. Every clipping shape (straddling element, padding, iteration, gather, zero-fill, a wholly clipped tile) has an execution test, and the race side has decoded tests at the boundary. The remaining points concern how this boundary model relates to the emulator's other LDS paths, and documentation.

## Actionable items

### Describe accurately how other LDS paths treat the allocation end

`emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/tensor_dma.h:511-512` says "The same dispatch granularity also bounds DS and FLAT accesses". The `append_copy` comment at `:593-595` contrasts the byte-prefix model only with the ISA rule for ordinary LDS instructions. Two facts about rocjitsu itself are missing:

- **Ordinary DS accesses are not bounded by the wave's allocation at all.** `execute_lds_access` (`vm/amdgpu/memory_pipeline.cpp`) clips only RDNA4 FLAT-to-LDS lanes against `flat_local_allocation_end`. Ordinary DS lanes use `Lds::vector_store` and are bounded only by the CU's LDS backing. A gfx1250 probe with a 256-byte allocation ran `ds_store_b32 v0, v1 offset:256`; the word just past the allocation changed from the sentinel to the stored value (source in the appendix). The existing `GlobalLoadAsyncToLdsDropsDestinationPastWorkgroupAllocation` test, with the same setup, leaves that word untouched.
- **gfx1250 async loads to LDS drop a whole straddling access.** `cdna5::async_lds_lane_address` returns `kInvalidLdsAddress` whenever `relative_addr + access_size_bytes > wf.lds_size()`. `AsyncLdsAddressRejectsAccessOutsideAllocation` pins this: a 16-byte access starting 4 bytes before the end is dropped entirely.

So the emulator now has two LDS-DMA engines on the same architecture with different straddle policies. A `tensor_load_to_lds` of one i64 at offset 252 writes four bytes; a `global_load_async_to_lds_b64` to the same offset writes none. Data and race reports differ accordingly. The ISA does not settle either policy, so whether to align them is the author's call. Either way, the comments should describe rocjitsu's actual behavior, so the next person qualifying hardware knows there are two models to check. [a4f7f704afa](https://github.com/newling/rocm-systems/commit/a4f7f704afa3e73ea0c76388b04ff82986e9c9ab) corrects the DS sentence and adds the async-to-LDS contrast; it changes no behavior.

### Document the allocation clipping in the race-detector guide

`emulation/rocjitsu/docs/race-detector.md:207-213` describes which bytes a tensor transfer covers (zero-filled elements, padding, in-tensor elements for stores) but not the new allocation boundary. The same guide documents the RDNA4 FLAT allocation bound at `:288-293`. Readers of the race-detector guide should know that bytes past `lds_base + lds_size` (including the 256-byte scheduler rounding) are neither transferred nor tracked, and that a straddling element contributes only its in-range prefix. The plugin-API docs already say this. [d2cb5e0f023](https://github.com/newling/rocm-systems/commit/d2cb5e0f0235a7425e0db75c829779d62cda3155) adds that sentence to the tensor DMA paragraph.

### Mention the plugin-facing changes in the description

Technical Details lists the clipping and the narrower observer ranges. It doesn't mention two interface changes a plugin author would need to know about:

- `TensorDmaIssueObservation::element_size_bytes` is removed.
- `WaveRaceState::registerLdsRangeEvent` loses its `elementBytes` parameter and always registers byte by byte.

No replacement text is supplied.

## Suggestions

### Check a partial store against an older LDS write

`emulation/rocjitsu/tests/execution_plugin_race_test.cpp:883-905`. The decoded boundary tests cover a partial load in both orders, but a partial store only as a registered read (a later DS write races with it). The store's own validation against an older pending DS write, which goes through the `validateRead` branch of `onAmdgpuTensorDmaIssued`, is untested at the boundary. As a mutation, I made only the store branch round its range to whole DWORDs (appendix). All six existing partial- and whole-element decoded tests still passed. [3c2020ae838](https://github.com/newling/rocm-systems/commit/3c2020ae8385b933fe1780ad0bc5aba8c0019613) adds `PartialElementStoreIsCheckedAgainstAnOlderWrite`: wave 1 writes the DWORD at 252, then wave 0 stores an i32 at 254. The test requires a report at byte 254, the first byte the store actually reads. It fails under the mutation and passes on the submitted code.

## Commentary

- The ordinary DS behavior above predates this PR. In emulation, a DS store past a workgroup's allocation can write another workgroup's LDS on the same CU, which tensor DMA and async-to-LDS no longer do. Changing that is outside this PR's scope. Until it changes, the three LDS paths disagree about what lies past the allocation end.
- If hardware qualification picks one straddle policy for LDS DMA, the tensor path is easy to change: `append_copy` computes `lds_bytes` in one place, and the observer ranges and race tracking follow from it.

## Branch, validation and omissions

Branch [review/pr14689-followup-20261104](https://github.com/newling/rocm-systems/tree/review/pr14689-followup-20261104) has three commits on `ff4ed4f0470`, in the order listed above. Changed-file pre-commit hooks pass. No production behavior changed.

Omitted: a description rewrite (not requested), any change to the DS or async-to-LDS behavior (outside this PR and a modeling decision), and hardware qualification of the straddle policies.

## Appendix: reproducers

The DS-store probe, added temporarily to `emulation/rocjitsu/tests/cdna5_cluster_test.cpp` and modeled on `GlobalLoadAsyncToLdsDropsDestinationPastWorkgroupAllocation`. On the reviewed head it prints `PROBE lds_base=0 word past allocation=0x12345678 (sentinel 0xa5a5a5a5)`:

```cpp
TEST(Gfx1250SimulationTest, ProbeDsStorePastWorkgroupAllocation) {
  constexpr uint64_t kernel_addr = 0x10000;
  constexpr uint32_t lds_bytes_per_wg = 256;
  constexpr uint32_t kSentinel = 0xa5a5a5a5u;
  const auto store = cdna5::build_vds(cdna5::kDsStoreB32Vds,
                                      {.offset0 = 0, .offset1 = 1, .addr = 0, .data0 = 1});
  const uint32_t code[] = {
      0x7E000280u,              // v_mov_b32_e32 v0, 0
      0x7E0202FFu, 0x12345678u, // v_mov_b32_e32 v1, 0x12345678
      store[0],    store[1],    // ds_store_b32 v0, v1 offset:256
      0xBFC60000u,              // s_wait_dscnt 0
      S_ENDPGM_GFX12,
  };
  Gfx1250Sim sim;
  ASSERT_NO_FATAL_FAILURE(sim.initialize());
  uint64_t kernel_object = sim.write_kernel(kernel_addr, code, std::size(code), 128);
  hsa_kernel_dispatch_packet_t pkt{};
  pkt.header = HSA_PACKET_TYPE_KERNEL_DISPATCH;
  pkt.setup = 1;
  pkt.workgroup_size_x = 1;
  pkt.workgroup_size_y = 1;
  pkt.workgroup_size_z = 1;
  pkt.grid_size_x = 1;
  pkt.grid_size_y = 1;
  pkt.grid_size_z = 1;
  pkt.group_segment_size = lds_bytes_per_wg;
  pkt.kernel_object = kernel_object;
  test::AqlQueue queue(sim.memory, sim.cp());
  queue.submit(pkt);
  ASSERT_TRUE(sim.engine->step());
  auto *wf = sim.cu()->wf(0);
  ASSERT_NE(wf, nullptr);
  ASSERT_EQ(wf->lds_size(), lds_bytes_per_wg);
  const uint32_t outside_allocation = wf->lds_base() + lds_bytes_per_wg;
  sim.cu()->lds().write32(outside_allocation, kSentinel);
  EXPECT_NO_THROW(sim.engine->run());
  std::printf("PROBE lds_base=%u word past allocation=0x%08x (sentinel 0x%08x)\n", wf->lds_base(),
              sim.cu()->lds().read32(outside_allocation), kSentinel);
}
```

The store-validation mutation used for the suggestion, in `race_detector/plugin.cpp`'s `onAmdgpuTensorDmaIssued`:

```diff
-    const auto bytes = detector->ldsBytesInRange(range.address, range.bytes, kByteGranularity);
+    const auto bytes = detector->ldsBytesInRange(range.address, range.bytes, issue.is_load ? kByteGranularity : 4);
```
