#include "execution_plugin_race_test.cpp"
#include "rocjitsu/vm/amdgpu/memory_pipeline.h"

class DecodedBarrierCellReviewTest
    : public TensorDmaRaceTest,
      public testing::WithParamInterface<std::tuple<bool, bool, int>> {
protected:
  static constexpr uint32_t kFirstCell = 64;
  static constexpr uint32_t kSecondCell = 128;

  void SetUp() override {
    ASSERT_NO_FATAL_FAILURE(TensorDmaRaceTest::SetUp());
    const uint32_t base = fixture.cu()->allocate_lds(256);
    for (auto *wave : waves) {
      wave->set_lds_base(base);
      wave->set_lds_size(256);
    }
    waves[1]->pc = 0x8000;
    for (const auto cell : {kFirstCell, kSecondCell})
      fixture.cu()->lds().write64(base + cell, lds_barrier_cell_init_state(1));
  }

  void execute(unsigned wave_index, std::span<const uint32_t> words) {
    auto &wave = *waves[wave_index];
    wave.pc += 16;
    std::unique_ptr<Instruction> inst(decode_valid(*decoder, words.data()));
    ASSERT_NE(inst, nullptr);
    fixture.plugin_group_->onAmdgpuBeforeExecuteInstruction(wave.pc, *inst, wave);
    ASSERT_TRUE(fixture.cu()->execute_instruction(inst.get(), wave).succeeded());
    fixture.plugin_group_->onAmdgpuAfterExecuteInstruction(wave.pc, *inst, wave);
    if (inst->data() && inst->data()->tag() == LOCAL_MEM) {
      const auto &state = *inst->data_as<VectorMemState>();
      auto access = local_access(wave.exec());
      access.is_load = state.is_load;
      access.active_lane_mask = state.exec_mask;
      access.request_lane_mask = state.lane_mask;
      fixture.plugin_group_->onAmdgpuMemoryAccessRouted(access, *inst, wave);
      LocalMemPipeline pipeline;
      ASSERT_EQ(pipeline.issue(inst.release(), wave), VmAccessOutcome::Complete);
    }
  }

  void arrive(bool async, bool reverse) {
    auto &wave = *waves[0];
    wave.set_exec(3);
    for (unsigned lane = 0; lane != 2; ++lane) {
      wave.debug_write_vgpr(0, lane, (lane != unsigned(reverse)) ? kSecondCell : kFirstCell);
      wave.debug_write_vgpr(2, lane, 1);
      wave.debug_write_vgpr(3, lane, 0);
    }
    const auto words =
        async ? cdna5::build_vds(cdna5::kDsAtomicAsyncBarrierArriveB64Vds, {.addr = 0})
              : cdna5::build_vds(cdna5::kDsAtomicBarrierArriveRtnB64Vds,
                                  {.addr = 0, .data0 = 2, .vdst = 4});
    ASSERT_NO_FATAL_FAILURE(execute(0, words));
    for (const auto cell : {kFirstCell, kSecondCell})
      ASSERT_EQ(fixture.cu()->lds().read64(wave.lds_base() + cell),
                lds_barrier_cell_update_arrive(lds_barrier_cell_init_state(1)));
  }

  void poll(uint32_t cell) {
    waves[1]->debug_write_vgpr(0, 0, cell);
    ASSERT_NO_FATAL_FAILURE(execute(
        1, cdna5::build_vds(cdna5::kDsLoadB32Vds, {.addr = 0, .vdst = 8})));
    const std::array<uint32_t, 1> wait{0xbfc60000u}; // s_wait_dscnt 0
    ASSERT_NO_FATAL_FAILURE(execute(1, wait));
    ASSERT_NE(waves[1]->debug_read_vgpr(8, 0) & (1u << 29), 0u);
  }

  void overwrite(uint32_t cell) {
    waves[1]->debug_write_vgpr(0, 0, cell);
    waves[1]->debug_write_vgpr(2, 0, 0);
    ASSERT_NO_FATAL_FAILURE(execute(
        1, cdna5::build_vds(cdna5::kDsStoreB32Vds, {.addr = 0, .data0 = 2})));
  }
};

TEST_P(DecodedBarrierCellReviewTest, AcquiringOneCellMustNotAcquireASiblingArrival) {
  const auto [async, reverse, poll_mode] = GetParam();
  ASSERT_NO_FATAL_FAILURE(arrive(async, reverse));
  if (poll_mode != 0)
    ASSERT_NO_FATAL_FAILURE(poll(poll_mode == 1 ? kFirstCell : kSecondCell));
  ASSERT_EQ(sink->str().find("RACE "), std::string::npos) << sink->str();
  ASSERT_NO_FATAL_FAILURE(overwrite(kSecondCell));
  const bool reports_race = sink->str().find("RACE ") != std::string::npos;
  EXPECT_EQ(reports_race, poll_mode != 2) << sink->str();
  if (reports_race) {
    EXPECT_NE(sink->str().find("type=LDS access=write"), std::string::npos);
    EXPECT_NE(sink->str().find("write-after-read (WAR)"), std::string::npos);
  }
}

INSTANTIATE_TEST_SUITE_P(
    BothFormsAndLaneOrders, DecodedBarrierCellReviewTest,
    testing::Combine(testing::Bool(), testing::Bool(), testing::Values(0, 1, 2)),
    ([](const testing::TestParamInfo<DecodedBarrierCellReviewTest::ParamType> &info) {
      const auto [async, reverse, poll_mode] = info.param;
      return std::string(async ? "Async" : "Returning") + (reverse ? "Reversed" : "Forward") +
             (poll_mode == 0 ? "NoPoll" : poll_mode == 1 ? "OtherCellPolled" : "SameCellPolled");
    }));
