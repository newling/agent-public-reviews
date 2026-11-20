#include "race-detector/race_test_builder.h"
#include <array>
#include <bitset>
#include <cstdio>
#include <map>
#include <optional>
#include <random>
#include <vector>
using namespace rocjitsu;
using namespace rocjitsu::plugins::race_detector;
constexpr int kWaves = 32;
constexpr int kEvents = 1024;
using Knowledge = std::bitset<kEvents>;
struct Access {
  int owner;
  bool write;
  bool complete = false;
};

// The oracle stores individual completed-access tokens, with no epochs,
// coverage minima, retirement, or history-prefix shortcuts.
int main(int argc, char **argv) {
  const int nWaves = argc > 1 ? std::atoi(argv[1]) : 4;
  if (nWaves < 2 || nWaves > kWaves)
    return 2;
  size_t checks = 0;
  for (unsigned seed = 0; seed < 200; ++seed) {
    std::mt19937 random(seed);
    RaceTestBuilder b(nWaves, 8, 8, 32);
    std::array<Knowledge, kWaves> known{};
    std::array<bool, kWaves> ended{};
    std::array<int, kWaves> joined{1, 1, 2, 2};
    std::array<std::optional<BarrierRoundId>, kWaves> pending{};
    std::array<int, 3> arrivals{};
    std::array<uint64_t, 3> generations{};
    std::array<Knowledge, 3> signalled{};
    std::map<BarrierRoundId, Knowledge> released;
    uint64_t workgroupGeneration = 0;
    std::bitset<kWaves> workgroupSignals;
    std::array<std::optional<BarrierRoundId>, kWaves> workgroupPending{};
    Knowledge workgroupReleased;
    auto finishWorkgroup = [&]() {
      for (int w = 0; w < nWaves; ++w)
        if (!ended[w] && !workgroupSignals[w])
          return;
      const auto round = RaceTestBuilder::workgroupRound(workgroupGeneration++);
      std::vector<int> armed;
      for (int w = 0; w < nWaves; ++w) {
        if (ended[w])
          workgroupReleased |= known[w];
        else if (!workgroupPending[w]) {
          workgroupPending[w] = round;
          armed.push_back(w);
        }
      }
      released[round] = workgroupReleased;
      b.completeRound(round, armed);
      workgroupSignals.reset();
      workgroupReleased.reset();
    };
    std::vector<Access> accesses;
    auto drain = [&](int wave) {
      b.waitDscnt(wave, 0);
      for (size_t id = 0; id < accesses.size(); ++id)
        if (accesses[id].owner == wave) {
          accesses[id].complete = true;
          known[wave].set(id);
        }
    };
    auto check = [&](int wave, int id, int step) {
      const auto &access = accesses[id];
      const bool expected = wave != access.owner && !known[wave].test(id);
      b.clearViolations();
      if (access.write)
        b.checkLdsRead(wave, 0, 16 * id, 4);
      else
        b.checkLdsWrite(wave, 0, 16 * id, 4);
      ++checks;
      if (b.hasRace() != expected) {
        std::printf(
            "mismatch seed=%u step=%d wave=%d id=%d owner=%d complete=%d expected=%d reports=%d\n",
            seed, step, wave, id, access.owner, access.complete, expected, b.raceCount());
        std::exit(1);
      }
    };
    for (int step = 0; step < 800; ++step) {
      std::vector<int> live;
      for (int wave = 0; wave < nWaves; ++wave)
        if (!ended[wave])
          live.push_back(wave);
      const int wave = live[random() % live.size()];
      switch (random() % 11) {
      case 0:
      case 1: {
        const int id = static_cast<int>(accesses.size());
        const bool write = random() % 2;
        accesses.push_back({wave, write});
        if (write)
          b.ldsWrite(wave, 0, 16 * id, 4, MemoryOrderClass::LDS, amdgpu::WaitCounterType::DSCNT);
        else
          b.ldsRead(wave, 0, 16 * id, 4, 1, 0xf, amdgpu::WaitCounterType::DSCNT);
        if (random() % 2)
          drain(wave);
        break;
      }
      case 2:
        drain(wave);
        break;
      case 3: {
        const int channel = random() % 3;
        const auto round = RaceTestBuilder::namedRound(channel + 1, generations[channel]);
        b.signal(wave, round);
        signalled[channel] |= known[wave];
        if (++arrivals[channel] == 2) {
          released[round] = signalled[channel];
          std::vector<int> armed;
          bool notified = false;
          for (int member : live)
            if (joined[member] == channel + 1) {
              notified = true;
              if (!pending[member]) {
                pending[member] = round;
                armed.push_back(member);
              }
            }
          if (notified)
            b.completeRound(round, armed);
          arrivals[channel] = 0;
          signalled[channel].reset();
          ++generations[channel];
        }
        break;
      }
      case 4:
        if (pending[wave]) {
          b.waitPassed(wave, *pending[wave]);
          known[wave] |= released.at(*pending[wave]);
          pending[wave].reset();
        }
        break;
      case 5:
        joined[wave] = random() % 4;
        pending[wave].reset(); // JOIN clears only this wave's completion bit.
        break;
      case 6:
        if (!workgroupSignals[wave]) {
          b.signal(wave, RaceTestBuilder::workgroupRound(workgroupGeneration));
          workgroupReleased |= known[wave];
          workgroupSignals.set(wave);
          finishWorkgroup();
        }
        break;
      case 9:
        if (workgroupPending[wave]) {
          b.waitPassed(wave, *workgroupPending[wave]);
          known[wave] |= released.at(*workgroupPending[wave]);
          workgroupPending[wave].reset();
        }
        break;
      case 10:
        // Help a partially signalled round progress without making waits
        // atomic with its completion. Later actions can relay these acquires.
        for (int w : live)
          if (!workgroupSignals[w]) {
            b.signal(w, RaceTestBuilder::workgroupRound(workgroupGeneration));
            workgroupReleased |= known[w];
            workgroupSignals.set(w);
          }
        finishWorkgroup();
        break;
      case 8: {
        const int channel = random() % 3;
        arrivals[channel] = 0;
        signalled[channel].reset();
        ++generations[channel];
        // INIT discards counted signals, but leaves previously set wave bits.
        break;
      }
      case 7:
        if (step > 450 && live.size() > 1 && !workgroupSignals[wave] && !workgroupPending[wave]) {
          drain(wave);
          b.endWave(wave);
          ended[wave] = true;
          pending[wave].reset();
          finishWorkgroup();
        }
        break;
      }
      if (!accesses.empty())
        for (int trial = 0; trial < 8; ++trial) {
          const int accessor = live[random() % live.size()];
          if (!ended[accessor])
            check(accessor, random() % accesses.size(), step);
        }
    }
    for (int wave = 0; wave < nWaves; ++wave)
      if (!ended[wave])
        for (size_t id = 0; id < accesses.size(); ++id)
          check(wave, id, 800);
  }
  std::printf("%d waves, 200 seeds, 800 actions each, %zu access checks passed\n", nWaves, checks);
}
