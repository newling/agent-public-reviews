This is a review from an agent with an automatic prompt from the reviewer

# CPU-reference stack review

Reviewed ROCm/rocm-libraries #15259, #15266, #15274, #15275, #15276, #15277 and #15278 independently, in dependency order. The seven submitted heads built and passed their existing tests. Targeted probes nevertheless found missing coverage for C/D aliasing, scaled input narrowing, unsupported reduction cleanup, non-HPA bias accumulation and NaN-sensitive comparison.

## Test assessment

The added tests are generally fast and useful, but they are not sufficient by themselves to establish the claimed behavior. The full submitted stack has 788 driver tests, adding 505 to the 283-test baseline. It took 5.21 s with four CTest workers. Focused reference gtests took 35–81 ms across the submitted heads. These timings describe a local host test run, not a performance replay of the affected GPU workloads.

| PR / review | New driver cases | Submitted driver / reference gtests | Driver wall time | Main gap |
| --- | ---: | ---: | ---: | --- |
| [#15259](review_pr15259.md) | 14 | 297 / 24 | 2.29 s | No correctness defect found; verify real OpenMP team limits |
| [#15266](review_pr15266.md) | 64 | 361 / 24 | 2.29 s | Int32 scalar boundary and diagnostic checking |
| [#15274](review_pr15274.md) | 79 | 440 / 30 | 2.74 s | Aliased Int32 C/D |
| [#15275](review_pr15275.md) | 207 | 647 / 32 | 4.18 s | Scaled Half-to-Float8 conversion |
| [#15276](review_pr15276.md) | 53 | 700 / 35 | 4.54 s | Aliased complex C/D |
| [#15277](review_pr15277.md) | 70 | 770 / 40 | 5.10 s | Unsupported batched reduction and non-HPA rounding |
| [#15278](review_pr15278.md) | 18 | 788 / 42 | 5.21 s | NaN false positives and obsolete slow-tail rejection |

A normalized command comparison found only two duplicate groups: `fast_F32_Sanity`/`fast_f32_NN`, and the corresponding slow pair. Both already existed before this stack. No added command duplicates another added command after option-order normalization. This does not prove every pair exercises independent logic; it does show that new registrations are not simply repeated invocations.

The fast/slow matrices exercise distinct implementations. Keep the independent integer/golden oracle and the focused gtests: exact rounding, saturation, aliasing, E padding, sampling and poisoned K tails serve different purposes. The Float8 matrix already reduces feature permutations for hybrid IDs. There is no measured runtime reason for wholesale deletion of these tests. The strongest improvements are compact boundary regressions and making negative tests verify their intended failure.

The submitted tests did not cover the reference's batched-gradient fallback because the driver rejects those arguments first. Similarly, `noscale` exclusions in test registration did not prevent the solver from accepting scaled narrowing cases. Test exclusions need matching eligibility boundaries or a separately validated semantic policy.

Use the binary directly for the focused gtests:

```sh
cmake --build "$BUILD_DIR" --target cpu-gemm-driver tensilelite-tests tensilelite-client -j 16
OMP_THREAD_LIMIT=8 OMP_NUM_THREADS=4 KMP_BLOCKTIME=0 \
  ctest --test-dir "$BUILD_DIR/tensilelite/tests" -R CPUGemm -j 4 --output-on-failure
OMP_THREAD_LIMIT=8 OMP_NUM_THREADS=4 KMP_BLOCKTIME=0 \
  "$BUILD_DIR/tensilelite/tests/tensilelite-tests" \
  '--gtest_filter=ReferenceFastPath.*:ReferenceMX*.*:*ReferenceMX*/*'
```

The source explicitly requests 64 slow-path threads, overriding `OMP_NUM_THREADS`; `OMP_THREAD_LIMIT` is needed to constrain the participating team. AMAX-D passed with limits of 1, 3 and 8. A CTest regex matching `ReferenceFastPath` misses the category-registered gtests in this configuration.

## Design and unsupported behavior

The useful unifications are concrete: consume tile sums directly during the epilogue, share bias-gradient reduction and its error handling, use `TypeInfo` as the type-mapping owner, and use one diagnostic-checking helper for failure tests. The tip suggestion also surfaces readable eligibility reasons through the existing predicate instead of requiring a source edit to enable logging.

Preserve the explicit numerical boundaries. Scaled Half-to-Float8 inputs and non-HPA narrow bias reduction need slow fallback until a different policy is defined. The slow Vector ScaleAB omission is retained, not repaired mathematically. Slow asymmetric MX remains unsupported even though equal-block K tails already work. Complex epilogue restrictions remain. Int32 accumulation is exact only while intermediate sums fit.

The MX-tail description incorrectly attributes current results to a slow-path over-read fixed in the base by #13630. The complex description's alpha-zero distinction was fixed in the base by #13482. Both descriptions need correction; no replacement descriptions were authored or posted.

## CI and validation limits

The inspected CI snapshots include successful broad summaries alongside cancelled and failed optional jobs. Downloaded failure logs showed a policy check complaining about cancelled pre-commit, a gfx1250 strict GEMM pytest exceeding 1200 seconds, and a gfx950 ASan job timing out while downloading artifacts before tests began. Those logs do not establish CPU-reference regressions or local sanitizer coverage.

The driver cases are not installed in the TheRock test package. They run in Math CI's unfiltered informational `coverage-cpp` lane. Focused gtests are categorized for standard/comprehensive/full, not quick. Passing ordinary installed quick lanes therefore does not establish that every new test ran. Making this host suite a dedicated gating job is a reasonable separate CI change; it is not implemented here.

Local validation built all three affected host targets at every submitted head and each suggestion implementation. No device execution, GPU performance replay, Windows qualification or local sanitizer run was performed. Root/component hooks were invoked; these C++/CMake paths largely opt out of formatting, and the component Python hook selected no tests. Whitespace checks passed.

## Suggestion branch integration

Each `review/prNNNN-suggestions` branch is based on that PR's exact submitted head. Its review lists the commits and validation. These are independently reviewable alternatives for applying each finding, not a combined repaired stack.

Carry the common tile-to-D correction once from #15274 and retain #15276's complex regression. When carrying #15266's `TypeInfo` cleanup into later PRs, migrate the later-added `TypeTraits` references too. Apply the shared failure-test helper and readable eligibility diagnostics once from #15278, and preserve the newly added fallback reasons from #15275/#15277. Those integration edits have not been represented as a tested combined branch.

The reviews and all seven suggestion branches are published. The original PRs are unchanged; no comments or formal reviews were posted to them. Build logs and other local evidence remain available separately.

## Published suggestion branches

| PR | Branch | Suggestion commits |
| --- | --- | --- |
| [#15259](https://github.com/ROCm/rocm-libraries/pull/15259) | [Suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15259-suggestions) | [f8ae33f6575](https://github.com/newling/rocm-libraries/commit/f8ae33f65755293d932e7066102d1b3378d71146) |
| [#15266](https://github.com/ROCm/rocm-libraries/pull/15266) | [Suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15266-suggestions) | [2fcafc2eee3](https://github.com/newling/rocm-libraries/commit/2fcafc2eee3f322abd349beeda112823931c8591), [088d585c895](https://github.com/newling/rocm-libraries/commit/088d585c895cff36e459ee0409c1b812edd9da81) |
| [#15274](https://github.com/ROCm/rocm-libraries/pull/15274) | [Suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15274-suggestions) | [1024648658c](https://github.com/newling/rocm-libraries/commit/1024648658c17b9f3dfafb3aa41929817081c84f), [3b524a30398](https://github.com/newling/rocm-libraries/commit/3b524a30398c6e136a3d049dc78fae2053ce3d97), [8886ad2d584](https://github.com/newling/rocm-libraries/commit/8886ad2d584b154fc7d986ce49f7b20e56661d7d) |
| [#15275](https://github.com/ROCm/rocm-libraries/pull/15275) | [Suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15275-suggestions) | [d930b5107f1](https://github.com/newling/rocm-libraries/commit/d930b5107f10b667c55bfe4a9454e4f4fa8f9d4b), [aef34bafaad](https://github.com/newling/rocm-libraries/commit/aef34bafaad8296981db27b07f6f2fe96bd6258e) |
| [#15276](https://github.com/ROCm/rocm-libraries/pull/15276) | [Suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15276-suggestions) | [7c3393ef929](https://github.com/newling/rocm-libraries/commit/7c3393ef929f82a8f899ded5a245816265954a1d) |
| [#15277](https://github.com/ROCm/rocm-libraries/pull/15277) | [Suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15277-suggestions) | [66106f99d91](https://github.com/newling/rocm-libraries/commit/66106f99d916da886beecc39e464681596074b6d), [de7815c2e50](https://github.com/newling/rocm-libraries/commit/de7815c2e5066f6b2ff76e589732a3b8a671e402), [26f8f56cec2](https://github.com/newling/rocm-libraries/commit/26f8f56cec2a4517b7edef1ade0da921334d228a) |
| [#15278](https://github.com/ROCm/rocm-libraries/pull/15278) | [Suggestions](https://github.com/newling/rocm-libraries/tree/review/pr15278-suggestions) | [f15ee4aacee](https://github.com/newling/rocm-libraries/commit/f15ee4aacee6031017b93c151ab6f2b3bb618a91), [b5d8bb5f9a5](https://github.com/newling/rocm-libraries/commit/b5d8bb5f9a552f26384ff3202fc100c608c10014), [66ef187d435](https://github.com/newling/rocm-libraries/commit/66ef187d43535cacaba49a328b77b0388909291e), [c7540acfc31](https://github.com/newling/rocm-libraries/commit/c7540acfc31bd3bfc502810669d0e598c14e3c57) |

## Appendix: native counterexample source and setup

The following exact probe source produced the aliasing, scalar-narrowing, non-HPA and invalid-gradient results cited above against the submitted stack tip. Save it as `cpu_reference_review_probes.cpp`. The committed regressions additionally cover both complex widths, both narrowed-operand directions and scale modes, both narrow reduction types, and A/B/D reduction error paths.

```cpp
#include <Reference.hpp>
#include <Tensile/ContractionProblem.hpp>
#include <Tensile/DataTypes.hpp>
#include <complex>
#include <iostream>
#include <string>
#include <vector>
using namespace TensileLite;
using namespace TensileLite::Client;
using DT = rocisa::DataType;
ContractionProblemGemm problem(DT ab, DT cd, DT alpha, size_t m, size_t n, size_t k, size_t batches=1)
{
    auto p = ContractionProblemGemm::GEMM_Strides(false,false,ab,ab,cd,cd,m,n,k,batches,m,-1,k,-1,m,-1,m,-1,1.0);
    p.setComputeInputTypeA(ab); p.setComputeInputTypeB(ab);
    p.setAlphaType(alpha); p.setBetaType(alpha);
    return p;
}
int main(int argc, char** argv)
{
    std::string mode=argv[1];
    bool fast=std::string(argv[2])=="fast";
    if(mode=="alias-i32")
    {
        auto p=problem(DT::Int8,DT::Int32,DT::Int32,1,1,1);
        int8_t a=2,b=3; int32_t cd=5;
        ContractionInputs in(&a,&b,&cd,&cd,int32_t(1),int32_t(1));
        SolveGemmCPU(p,in,-1,fast); std::cout << cd << " expected 11\n";
        return cd==11 ? 0:1;
    }
    if(mode=="alias-complex")
    {
        using T=std::complex<float>;
        auto p=problem(DT::ComplexFloat,DT::ComplexFloat,DT::ComplexFloat,1,1,1);
        T a(2,0),b(3,0),cd(5,1);
        ContractionInputs in(&a,&b,&cd,&cd,T(1,0),T(1,0));
        SolveGemmCPU(p,in,-1,fast); std::cout << cd << " expected (11,1)\n";
        return cd==T(11,1) ? 0:1;
    }
    if(mode=="scale")
    {
        auto p=ContractionProblemGemm::GEMM_Strides(false,false,DT::Half,DT::Float8,DT::Float8,DT::Float8,1,1,1,1,1,-1,1,-1,1,-1,1,-1,0.0);
        p.setComputeInputTypeA(DT::Float8);p.setComputeInputTypeB(DT::Float8);
        p.setAlphaType(DT::Float);p.setBetaType(DT::Float);
        p.setUseScaleAB("Scalar"); p.setScaleA(DT::Float,1);p.setScaleB(DT::Float,1);
        Half a(0.9f);Float8 b(1.0f),c(0.0f),d(0.0f); float sa=3,sb=1;
        ContractionInputs in(&a,&b,&c,&d,1.0f,0.0f);in.scaleA=&sa;in.scaleB=&sb;
        SolveGemmCPU(p,in,-1,fast);std::cout << float(d) << " scaled before quantization: 2.75\n";
        return float(d)==2.75f ? 0:1;
    }
    if(mode=="nonhpa")
    {
        constexpr size_t n=4097;
        auto p=problem(DT::Half,DT::Half,DT::Half,1,n,1);
        p.setHighPrecisionAccumulate(false);p.setUseGradient(true);p.setUseBias(1);
        p.setBias(DT::Half,1,1,true,ContractionProblemGemm::D);
        Half a(1.0f),bias(0.0f); std::vector<Half>b(n,Half(1.0f)),c(n,Half(0.0f)),d(n,Half(0.0f));
        ContractionInputs in(&a,b.data(),c.data(),d.data(),Half(1.0f),Half(0.0f));in.bias=&bias;
        SolveGemmCPU(p,in,-1,fast);std::cout << "bias=" << float(bias) << " first D=" << float(d[0]) << '\n';return 0;
    }
    if(mode=="invalid-gradient")
    {
        auto p=problem(DT::Float,DT::Float,DT::Float,1,1,1,2);
        p.setUseGradient(true);p.setUseBias(1);p.setBias(DT::Float,1,1,true,ContractionProblemGemm::D);
        std::vector<float>a(2,1),b(2,1),c(2,0),d(2,0);float bias=-99;
        ContractionInputs in(a.data(),b.data(),c.data(),d.data(),1.0f,0.0f);in.bias=&bias;
        try {SolveGemmCPU(p,in,-1,fast);std::cout << "returned success bias=" << bias << '\n';}
        catch(std::exception const& e){std::cout << "exception: " << e.what() << '\n';return 0;}
        return 1;
    }
    return 2;
}
```

In a Ninja build configured with `CMAKE_EXPORT_COMPILE_COMMANDS=ON`, build the normal `cpu-gemm-driver` first. Save the following as `build_native_probe.py`; it reuses that target's exact compiler and link settings, replacing only its main object. The build must correspond to the revision being checked.

```python
from pathlib import Path
import json, shlex, subprocess, sys
build = Path(sys.argv[1]).resolve()
source = Path(sys.argv[2]).resolve()
obj = build / 'cpu-reference-review-probes.o'
exe = build / 'cpu-reference-review-probes'
entry = next(x for x in json.loads((build / 'compile_commands.json').read_text())
             if x['file'].endswith('/tensilelite/client/cpu_gemm_driver.cpp'))
args = shlex.split(entry['command'])
args[args.index(entry['file'])] = str(source)
args[args.index('-o') + 1] = str(obj)
subprocess.run(args, cwd=entry['directory'], check=True)
link = subprocess.check_output(['ninja', '-t', 'commands', 'cpu-gemm-driver'],
                               cwd=build, text=True).splitlines()[-1]
args = shlex.split(link)
if args[0] == ':':
    start = args.index('&&') + 1
    args = args[start:args.index('&&', start)]
old_obj = next(x for x in args if x.endswith('/cpu_gemm_driver.cpp.o'))
args[args.index(old_obj)] = str(obj)
args[args.index('-o') + 1] = str(exe)
subprocess.run(args, cwd=build, check=True)
print(exe)
```

```sh
python3 build_native_probe.py "$BUILD_DIR" cpu_reference_review_probes.cpp
OMP_THREAD_LIMIT=8 OMP_NUM_THREADS=4 KMP_BLOCKTIME=0 \
  "$BUILD_DIR/cpu-reference-review-probes" alias-i32 fast
```

Modes are `alias-i32`, `alias-complex`, `scale`, `nonhpa`, and `invalid-gradient`; the second argument selects `fast` or `slow`. Run the invalid-gradient case in its own process: the submitted reference aborts. Apply the relevant suggestion branch before checking its fix; the branches do not incorporate one another's changes.
