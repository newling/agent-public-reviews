#include "race-detector/race_test_builder.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <optional>
#include <vector>
using namespace rocjitsu;
using namespace rocjitsu::plugins::race_detector;
struct Case {
  int threshold, as, bs;
  bool both;
};
struct Summary {
  size_t total = 0, clean = 0, race = 0, checks = 0;
};
// Enumerate all issue orders of fixed per-wave programs. Wait can issue only
// with a completion bit. Memory knowledge is a set of individual access IDs.
void replay(const Case &c, const std::vector<int> &trace, Summary &s) {
  RaceTestBuilder b(3, 8, 8, 32);
  std::array<unsigned, 3> known{}, completed{};
  struct Event {
    int owner, address;
    bool write;
  };
  std::vector<Event> events;
  std::vector<unsigned> rounds;
  int count = 0, pending = -1, round = 0;
  unsigned released = 0;
  std::array<int, 3> pc{};
  bool anyRace = false;
  auto drain = [&](int w) {
    b.waitDscnt(w, 0);
    known[w] |= completed[w];
  };
  auto access = [&](int w, int address, bool write) {
    bool expected = false;
    for (size_t id = 0; id < events.size(); ++id) {
      auto &e = events[id];
      if (e.owner != w && e.address == address && (e.write || write) && !(known[w] & (1u << id)))
        expected = true;
    }
    b.clearViolations();
    if (write)
      b.ldsWrite(w, 0, address, 4, MemoryOrderClass::LDS, amdgpu::WaitCounterType::DSCNT);
    else
      b.ldsRead(w, 0, address, 4, 1, 0xf, amdgpu::WaitCounterType::DSCNT);
    ++s.checks;
    if (b.hasRace() != expected) {
      std::printf("mismatch threshold=%d trace=", c.threshold);
      for (int x : trace)
        std::printf("%d", x);
      std::printf(" accessor=%d expected=%d actual=%d\n", w, expected, b.raceCount());
      std::exit(1);
    }
    anyRace |= b.hasRace();
    completed[w] |= 1u << events.size();
    events.push_back({w, address, write});
  };
  for (int w : trace) {
    int op = pc[w]++;
    if (w < 2) {
      if (op == 0)
        access(w, 64 + 16 * w, true);
      else if (op == 1)
        drain(w);
      else {
        b.signal(w, RaceTestBuilder::namedRound(1, round));
        released |= known[w];
        if (++count == c.threshold) {
          rounds.push_back(released);
          std::vector<int> armed;
          if (pending < 0) {
            pending = round;
            armed.push_back(2);
          }
          b.completeRound(RaceTestBuilder::namedRound(1, round), armed);
          ++round;
          count = 0;
          released = 0;
        }
      }
    } else {
      if (op == 0) {
        b.waitPassed(2, RaceTestBuilder::namedRound(1, pending));
        known[2] |= rounds.at(pending);
        pending = -1;
      } else if (op == 1)
        access(2, 64, false);
      else if (c.both && op == 2)
        access(2, 80, false);
      else
        drain(2);
    }
  }
  ++s.total;
  if (anyRace)
    ++s.race;
  else
    ++s.clean;
}
void enumerate(const Case &c, std::array<int, 3> pc, int signals, std::vector<int> &trace,
               Summary &s) {
  const std::array<int, 3> lengths{2 + c.as, 2 + c.bs, c.both ? 4 : 3};
  if (pc == lengths) {
    replay(c, trace, s);
    return;
  }
  for (int w = 0; w < 3; ++w) {
    if (pc[w] == lengths[w] || (w == 2 && pc[2] == 0 && signals < c.threshold))
      continue;
    auto next = pc;
    ++next[w];
    trace.push_back(w);
    enumerate(c, next, signals + (w < 2 && pc[w] >= 2), trace, s);
    trace.pop_back();
  }
}
int main() {
  for (Case c : {Case{1, 1, 1, false}, Case{1, 1, 1, true}, Case{2, 1, 1, false},
                 Case{2, 1, 1, true}, Case{5, 2, 3, true}}) {
    Summary s;
    std::vector<int> trace;
    enumerate(c, {}, 0, trace, s);
    std::printf("threshold=%d signals=%d+%d reads=%s schedules=%zu clean=%zu race=%zu checks=%zu\n",
                c.threshold, c.as, c.bs, c.both ? "both" : "A", s.total, s.clean, s.race, s.checks);
    if (s.total == 0 || (c.threshold == 1 && c.both && s.clean) || (c.threshold > 1 && s.race) ||
        (c.threshold == 1 && !c.both && (!s.clean || !s.race)))
      return 1;
  }
}
