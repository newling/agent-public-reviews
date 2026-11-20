#include "race-detector/race_test_builder.h"
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <limits>
using namespace rocjitsu;
using namespace rocjitsu::plugins::race_detector;
int main() {
  RaceTestBuilder builder(2, 8, 8, 32);
  constexpr uint64_t signals = std::numeric_limits<uint32_t>::max();
  const auto start = std::chrono::steady_clock::now();
  for (uint64_t signal = 0; signal < signals; ++signal) {
    // A named barrier of threshold 127, with no joined listeners, completes
    // every 127 arrivals. Those completions have no callback. The next
    // generation discards the preceding unobserved round.
    builder.signal(0, RaceTestBuilder::namedRound(1, signal / 127));
    if ((signal & ((uint64_t{1} << 28) - 1)) == 0) {
      const double seconds =
          std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
      std::printf("signals=%llu seconds=%.3f\n", static_cast<unsigned long long>(signal), seconds);
      std::fflush(stdout);
    }
  }
  builder.ldsWrite(0, 0, 64, 4, MemoryOrderClass::LDS, amdgpu::WaitCounterType::DSCNT);
  builder.waitDscnt(0, 0);
  const auto epoch = builder.events().releaseEpoch(EventId{0});
  builder.checkLdsRead(1, 0, 64, 4);
  std::printf("completion_epoch=%llu expected_races=1 actual_races=%d seconds=%.3f\n",
              static_cast<unsigned long long>(epoch), builder.raceCount(),
              std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count());
  return builder.raceCount() == 1 ? 0 : 1;
}
