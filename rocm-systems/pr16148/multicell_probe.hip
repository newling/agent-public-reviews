#include "hip_race_gfx1250_test.hip"

#include <string>
#include <tuple>

namespace {

// Each cell requires one arrival. Only two lanes of the producer arrive,
// and the consumer overwrites cell 1 after the selected poll, if any.
__global__ __attribute__((amdgpu_flat_work_group_size(64, 64))) void
independent_cell_arrivals_kernel(bool async, bool reverse, int poll_mode, int *finished) {
  if (waveIndex() == 0 && lane() == 0) {
    cellInit(cell(0), 1);
    cellInit(cell(1), 1);
  }
  barrier();
  if (waveIndex() == 0) {
    if (lane() < 2) {
      const uint32_t address = cell(lane() ^ int(reverse));
      if (async)
        cellArriveAsync(address);
      else
        cellArrive(address);
    }
  } else if (lane() == 0) {
    if (poll_mode != 0)
      cellWaitPhase(cell(poll_mode == 1 ? 0 : 1), 1);
    cellInit(cell(1), 1);
    finished[0] = 1;
  }
  // A rendezvous after the conflicting accesses cannot order them.
  barrier();
}

class BarrierCellReviewHipTest
    : public rocjitsu::test::RaceTestBase,
      public testing::WithParamInterface<std::tuple<bool, bool, int>> {};

TEST_P(BarrierCellReviewHipTest, AcquiringOneCellMustNotAcquireASiblingArrival) {
  const auto [async, reverse, poll_mode] = GetParam();
  auto *finished = alloc<int>(1);
  independent_cell_arrivals_kernel<<<1, 64, kCellLdsBytes>>>(async, reverse, poll_mode, finished);
  RACE_HIP_CHECK(hipGetLastError());
  sync();
  ExpectValues(finished, std::vector<int>{1});
  if (poll_mode == 2) {
    ExpectNoRace();
  } else {
    const char *arrive = async ? "ds_atomic_async_barrier_arrive_b64"
                              : "ds_atomic_barrier_arrive_rtn_b64";
    ExpectAnyRace({{.findings = FindingCount::OneOrMore,
                   .type = "LDS",
                   .access = "write",
                   .producer = arrive,
                   .consumer = "ds_store_b64"},
                  {.findings = FindingCount::OneOrMore,
                   .type = "LDS",
                   .access = "read",
                   .producer = "ds_store_b64",
                   .consumer = arrive}});
    const auto parsed = rocjitsu::test::parseRaceLogFromEnvironment();
    ASSERT_TRUE(parsed.ok()) << parsed.error;
    for (const auto &record : parsed.records)
      EXPECT_GE(record.reg, int(cell(1)));
  }
}

INSTANTIATE_TEST_SUITE_P(
    BothFormsAndLaneOrders, BarrierCellReviewHipTest,
    testing::Combine(testing::Bool(), testing::Bool(), testing::Values(0, 1, 2)),
    ([](const testing::TestParamInfo<BarrierCellReviewHipTest::ParamType> &info) {
      const auto [async, reverse, poll_mode] = info.param;
      return std::string(async ? "Async" : "Returning") + (reverse ? "Reversed" : "Forward") +
             (poll_mode == 0 ? "NoPoll" : poll_mode == 1 ? "OtherCellPolled" : "SameCellPolled");
    }));

} // namespace
