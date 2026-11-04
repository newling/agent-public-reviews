> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-systems#15000](https://github.com/ROCm/rocm-systems/pull/15000)

**Reviewed head:** `d72da9f4825e5786a2fd46f9357b49e9b5b90649`

**Suggestion branch:** [`review/pr15000-suggestions`](https://github.com/newling/rocm-systems/tree/review/pr15000-suggestions), based on the reviewed head.

| Commit | Item |
| --- | --- |
| [`fb009ebd0bd`](https://github.com/newling/rocm-systems/commit/fb009ebd0bdd3e4295a68ba9da63d1f41927ef90) | Actionable item 1: compile the portable switch dispatch on x86-64 ELF hosts |

## Tests

On a Clang 23 Release build of the submitted head, the `ModelOnlyIsaTest` CTest entries (including the new `DecodeTableLayout` check) passed 3/3, and the changed generator test modules passed (911 passed, 1 existing skip). On the suggestion branch, the same CTest entries pass and the ten new portable-decoder objects build. CI passed in every rocjitsu lane (Release, ASan+UBSan, TSan, GCC UBSan, symbol isolation).

I also ran two exploratory checks outside the PR's own tests. First, every generated `decoder.cpp` compiled with `-mcmodel=medium`, which leaves `__code_model_small__` undefined and therefore selects the switch path. All ten compiled cleanly and contained no table symbols. Second, a small standalone program reproduced the generated layout: a table emitted from `emitTables`, filled with member factories and factories from another translation unit, and linked into a shared library with `-ffunction-sections -fdata-sections -Wl,--gc-sections`. Every slot dispatched to the right factory under GCC 13 (`-O2` and `-flto=auto`) and Clang 20 (`-O2`, ThinLTO, and full LTO with lld), and the table added no dynamic relocations. The source is in the appendix. The PR's CI configures rocjitsu with `LTO=OFF`, so this is the only evidence I have for the LTO claims in `decode_table.h`.

## Summary

The PR changes how the generated AMDGPU decoders store their dispatch tables. Previously, each primary and sub-decode table was a `std::array` of function pointers, so every entry needed a dynamic relocation at load time. With ten architectures, that is 38,840 relocations; I summed the table sizes in the generated sources and got exactly the number in the description. On small-model x86-64 ELF hosts, each table becomes a `DecodeTable<DecodeFunc, N>` of signed 32-bit offsets from the table's own address. The table is defined entirely in inline assembly inside a `[[gnu::used]]` `emitTables` function, so the linker resolves each `factory - table` difference statically and the data stays in read-only memory. On every other host, the generator emits a `switch` over the same opcode map, using the most common target as the `default` label.

The tricky parts are handled carefully. Passing each factory through an `"i"` operand makes the compiler see the address as taken, which keeps the factory alive and correctly named through LTO, section GC, and archive extraction; my LTO probe confirmed this with both compilers. Numbered subsections put each run in slot order no matter how the compiler schedules the `asm` statements. The `visibility push(hidden)` makes the factories locally bound, so the PC-relative difference resolves without a dynamic relocation even in PIC code. The new generator test `test_portable_decode_switches_match_relative_tables` reconstructs both representations from the checked-in sources and requires them to agree slot by slot, which guards against the two paths drifting apart. `DecodeTableLayout` checks the linked binary and fails if the table is missing, has the wrong size, sits in a writable segment, or is subject to text relocations. Its marker symbol is chosen by a predicate that is independent of `host_target.h`, so it would also notice if an x86-64 build silently stopped using the relative table.

The main gap is that CI never compiles the second representation; item 1 covers it.

## Actionable items

### 1. CI never compiles the portable switch dispatch

`emulation/rocjitsu/lib/python/amdisa/codegen/_generator.py:18189` (`table_dispatch`) emits an `#if RJ_HOST_HAS_X86_64_ELF_REL32 … #else switch … #endif` block for each of the 150 tables across the ten decoders. Every rocjitsu CI job runs on small-model x86-64 Linux, where `emulation/rocjitsu/lib/util/include/util/host_target.h:36` sets the macro to 1, so CI never compiles the `#else` branch. The new pytest checks that the switch labels match the table text, but not that the switch is valid C++. A generator change that misspelled a factory name, dropped a `DecodeFunc`-dependent helper from the switch path, or emitted a duplicate `case` would pass CI. It would then break the first aarch64, Windows, or non-small-model build. For example, renaming a single switch target in `generated/rdna4/decoder.cpp` still builds and passes on the submitted head, because no build compiles that line.

Commit [`fb009ebd0bd`](https://github.com/newling/rocm-systems/commit/fb009ebd0bdd3e4295a68ba9da63d1f41927ef90) closes the gap with two small changes:

- `host_target.h` defines `RJ_HOST_HAS_X86_64_ELF_REL32` only when it is not already defined, and documents that a build may predefine it as 0 (and that predefining 1 elsewhere is unsupported).
- `rj_add_split_amdgpu_isa_library` in `emulation/rocjitsu/lib/rocjitsu/src/rocjitsu/isa/CMakeLists.txt` adds an unlinked `rocjitsu_isa_<arch>_portable_decoder_check` object library on x86-64 ELF hosts. It compiles that architecture's `decoder.cpp` with `RJ_HOST_HAS_X86_64_ELF_REL32=0`, and because it is part of `all`, every existing CI lane builds it under its own compiler and sanitizer flags.

On the suggestion branch, the ten check objects build and contain no table symbols. With the same one-line rename in `generated/rdna4/decoder.cpp`, the build now fails with `no member named 'decodeMissingFactory' in namespace 'rocjitsu::rdna4::detail'`. The added cost is ten compiles of a mostly declarative file, about a second each locally. If the author would rather not have a predefinable host macro, the same object library could pass `-mcmodel=medium` instead; I preferred the explicit define because it does not depend on how each compiler spells code-model macros.

## Suggestions

### 1. Explain the connection to #14039 in the description

The description ends with "Follow-up to the startup performance regression introduced in #14039." #14039 decoupled KFD/GEM memory backing from application file limits and does not touch the decoders, so a reader cannot tell why relocations in the decoder tables relate to it. A sentence explaining which startup path #14039 made more sensitive to dynamic relocation processing would let reviewers judge the rocminfo startup numbers in context. This is a description-only change, so the suggestion branch has no commit for it.

## Commentary

The PR keeps two complete representations of each dispatch map in every generated decoder, which adds about 15,000 net lines across the ten files. I think the cost is acceptable. Both representations come from one generator function over one list, the pytest checks that they agree, and item 1 makes the build check that the second one compiles. Generating only the run list and expanding it with macros would cut the file size, but the generated code would be harder to read, and diffs would be harder to review when an opcode moves.

The `.subsection` ordering and the "i"-operand reachability are subtle enough that a future maintainer could easily "simplify" them away. The comments in `decode_table.h` explain both, which is the right place for that explanation. The layout test and the LTO behavior shown by the appendix probe cover the failure modes a simplification would most likely introduce, with the caveat that CI does not exercise LTO.

The relative table relies on every factory being in the same linked image as its table and within ±2 GiB. That holds for every current consumer, because the factories are hidden and compiled into the same object libraries, and the linker rejects any violation outright, so a future violation would fail loudly instead of corrupting dispatch.

## Appendix: standalone LTO and section-GC probe

Build from the repository root with `run.sh "$SRC_DIR"` and `CLANGXX` set to a Clang that has a matching `ld.lld`. The script needs `g++`, `readelf`, and `rg`.

`decoder.cpp`:

```cpp
#include "rocjitsu/isa/arch/amdgpu/shared/decode_table.h"

namespace rocjitsu::fake {
#pragma GCC visibility push(hidden)
namespace detail {
int distributedA(int);
int distributedB(int);
} // namespace detail
struct DecoderImpl {
  static int decode(unsigned index, int value);

private:
  static int memberA(int value) { return value + 1000; }
  static int invalid(int) { return -1; }
  using DecodeFunc = int (*)(int);
  static const amdgpu::DecodeTable<DecodeFunc, 8> primary_decode_table;
  [[gnu::used]] static void emitTables();
};
#pragma GCC visibility pop

int DecoderImpl::decode(unsigned index, int value) {
  return primary_decode_table[index & 7](value);
}

void DecoderImpl::emitTables() {
  RJ_BEGIN_DECODE_TABLE(primary_decode_table)
  RJ_DECODE_RUN(0, 2, &detail::distributedA);
  RJ_DECODE_RUN(2, 1, &DecoderImpl::memberA);
  RJ_DECODE_RUN(3, 3, &DecoderImpl::invalid);
  RJ_DECODE_RUN(6, 2, &detail::distributedB);
  RJ_END_DECODE_TABLE()
}

[[gnu::visibility("default")]] int decode(unsigned index, int value) {
  return DecoderImpl::decode(index, value);
}
} // namespace rocjitsu::fake
```

`factories.cpp`:

```cpp
namespace rocjitsu::fake::detail {
int distributedA(int value) { return value + 1; }
int distributedB(int value) { return value * 2; }
} // namespace rocjitsu::fake::detail
```

`main.cpp`:

```cpp
#include <cstdio>

namespace rocjitsu::fake {
int decode(unsigned index, int value);
}

int main() {
  const int expected[8] = {11, 11, 1010, -1, -1, -1, 20, 20};
  int failures = 0;
  for (unsigned i = 0; i < 8; ++i) {
    int got = rocjitsu::fake::decode(i, 10);
    if (got != expected[i]) {
      std::printf("slot %u: got %d expected %d\n", i, got, expected[i]);
      ++failures;
    }
  }
  std::puts(failures ? "FAIL" : "PASS");
  return failures != 0;
}
```

`run.sh`:

```bash
#!/usr/bin/env bash
set -u
here=$(cd "$(dirname "$0")" && pwd)
src=$1
inc="-I$src/emulation/rocjitsu/lib/rocjitsu/src -I$src/emulation/rocjitsu/lib/util/include"
out=$(mktemp -d)
status=0
run() {
  local name=$1 cxx=$2 flags=$3
  $cxx -std=c++20 -O2 $flags $inc -fvisibility=hidden \
      "$here/decoder.cpp" "$here/factories.cpp" -o "$out/libdec.so" -shared -fPIC \
      -Wl,--gc-sections -ffunction-sections -fdata-sections 2>"$out/err" &&
    $cxx -O2 $flags "$here/main.cpp" -fvisibility=default -o "$out/main" \
      -Wl,-rpath,"$out" "$out/libdec.so" 2>>"$out/err"
  printf '%-28s ' "$name"
  if [[ -x $out/main ]] && "$out/main" >"$out/log"; then
    printf 'PASS dynrel=%s\n' "$(readelf -rW "$out/libdec.so" | rg -c 'R_X86_64_(RELATIVE|64|GLOB_DAT)' || true)"
  else
    echo FAIL
    cat "$out/err" "$out/log" 2>/dev/null | head -20
    status=1
  fi
  rm -f "$out/main" "$out/libdec.so"
}
for cxx in g++ "$CLANGXX"; do
  run "$(basename "$cxx") O2" "$cxx" ""
done
run "g++ -flto=auto" g++ "-flto=auto"
run "clang++ -flto=thin" "$CLANGXX" "-flto=thin -fuse-ld=lld"
run "clang++ -flto=full" "$CLANGXX" "-flto -fuse-ld=lld"
rm -rf "$out"
exit $status
```

Every configuration printed `PASS dynrel=7`. All seven relocations come from the C runtime startup objects (the init/fini array entries, `__dso_handle`, and `GLOB_DAT` entries for `__cxa_finalize`, `__gmon_start__`, and the TM clone table hooks). None of them point into the decode table.
