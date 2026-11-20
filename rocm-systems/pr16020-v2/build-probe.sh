#!/usr/bin/env bash
set -eu
rj_review_source=${1:?Pass the emulation/rocjitsu source directory}
rj_review_build=${2:?Pass its configured build directory}
rj_review_probe=${3:?Pass probe.cpp}
rj_review_output=${4:?Pass the output executable path}
"${CXX:-clang++}" -std=c++20 -O3 -DNDEBUG -march=x86-64-v3 \
  -I"$rj_review_source/tests" \
  -I"$rj_review_source/lib/rocjitsu/include" \
  -I"$rj_review_source/lib/rocjitsu/src" \
  -I"$rj_review_source/lib/util/include" \
  -I"$rj_review_source/lib/arith/include" \
  -I"$rj_review_source/lib/simdojo/include" \
  -I"$rj_review_source/../../runtimes/api-headers/include" \
  -I"$rj_review_build/generated" \
  -isystem "$rj_review_build/_deps/googletest-src/googletest/include" \
  "$rj_review_probe" \
  "$rj_review_source/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/race_detector.cpp" \
  "$rj_review_source/lib/rocjitsu/src/rocjitsu/vm/plugins/race_detector/core/wave_race_state.cpp" \
  "$rj_review_source/lib/rocjitsu/src/rocjitsu/isa/arch/amdgpu/shared/wait_counter_policy.cpp" \
  "$rj_review_build/lib/libgtest.a" -pthread -o "$rj_review_output"
