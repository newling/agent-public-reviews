> This is a review from an agent with an automatic prompt from the reviewer

**PR reviewed:** [ROCm/rocm-libraries#13674](https://github.com/ROCm/rocm-libraries/pull/13674)

Reviewed head: `1146125df53ee5df0f155b96ec8279c45ff849e6` (`<pr-head-ref>`), merge base `db2d71e0815`.

Suggestion branch: [`review/pr13674-suggestions`](https://github.com/newling/rocm-libraries/tree/review/pr13674-suggestions), based on the reviewed head ([diff against the PR head](https://github.com/newling/rocm-libraries/compare/1146125df53ee5df0f155b96ec8279c45ff849e6...ed013baa7902a6971b83a052d4c92214bd7b1144)).

| Commit | Item |
|---|---|
| [`e97c801e64f`](https://github.com/newling/rocm-libraries/commit/e97c801e64f378c9ee0fc1e9c5910c35342da72a) | 2. A thread that fails to start aborts the interpreter |
| [`ed013baa790`](https://github.com/newling/rocm-libraries/commit/ed013baa7902a6971b83a052d4c92214bd7b1144) | 3. The stinkytofu adaptor still probes fallback ISAs one subprocess at a time |
| [`50b18c1c03d`](https://github.com/newling/rocm-libraries/commit/50b18c1c03d5ab11b8f23872da526d62dacb81a9) | 4. `initMany` accepts only a `list` |
| [`bbe291b83da`](https://github.com/newling/rocm-libraries/commit/bbe291b83da5ab1359e2d6e7c416658e8d1ad9ca) | 5. `init` and `initMany` build `IsaInfo` separately |

Item 1 (Windows) has no commit. The commits are independent apart from textual adjacency in `base.hpp`; `ed013baa790` calls native `initMany` with a list, so it does not depend on `50b18c1c03d`.

## Tests

On the submitted PR, the new rocisa test, the existing assembler-probe tests and a TensileLite `TensileLogic --check-all` run pass. Comparing serial `init` with `initMany` over all 24 `SUPPORTED_ISA` entries gave identical asm, arch and register caps and asm bugs (19.4 s versus 2.1 s, 21 ISAs supported by the local assembler). On the suggestion branch, the same 24-ISA equivalence holds natively and through the stinkytofu adaptor. The rocisa suite, adaptor `test_base.py`/`test_true16.py`, six focused TensileLite unit files under both backends, and a gfx942 `TensileLogic --check-all` run (25.8 s on the merge base, 6.3 s on the branch, identical output) also pass apart from the failures noted below.

Local failures that also occur on the merge base, so are not caused by this PR: rocisa `test_async_store.py::test_async_store_high_vgpr_emits_msb_window`, adaptor `test_base.py::TestRocIsaForwarding::test_get_caps_raises_without_init`, and four `test_DecouplePGR.py` cases under `ROCISA_BACKEND=stinkytofu`. CI passes them, so they appear to come from the local build or environment.

CI: the TensileLite coverage lane and the Math CI unit lanes fail only in `tensilelite/Tests/unit/test_streamk_occupancy_probe.py`, which arrived on develop after this PR's base. Under the stinkytofu backend that the lane forces, its gfx950 expectation `global_store_dword` gets `global_store_b32`. The same test fails in the same lane on many unrelated PRs opened since that test landed. The rocblas shard 5 failure is a GPU hang in `gemm_ex`. Neither failure involves this change. `rocISA / Linux` and `rocISA / Windows` both ran and passed the new test.

## Summary

`makeIsaInfoMap` asks rocisa to initialize every ISA it needs. For `TensileLogic` that is all 24 entries in `SUPPORTED_ISA`, each probed by several hundred serial assembler runs. The PR adds `rocIsa::initMany`, which runs `initAsmCaps` for every uninitialized ISA on its own thread with the GIL released. It then fills the singleton's table serially after the GIL is reacquired, and `makeIsaInfoMap` calls it before its existing per-ISA loop. The design is well judged: worker threads touch only their own slots of local vectors, all writes to `m_isainfo` happen on the calling thread, and errors are collected per ISA and rethrown only after every probe has finished. A failure therefore leaves no partially initialized table (`isInit()` stays false after a missing assembler). The new test compares the two entry points in separate interpreters, includes a duplicate ISA and checks that an assembler was actually reached, so it guards against vacuous equality. Locally the speedup and equivalence claims hold across all 24 ISAs.

The POSIX side depends on #13668's `O_CLOEXEC` pipe, as the description says. The Windows implementation of the same `run()` helper has an equivalent problem that the PR does not address. The remaining items concern a failure mode during thread creation, the stinkytofu path not getting the speedup, and two smaller API points.

## Actionable items

### 1. The Windows `run()` is not safe to call from concurrent probes

`projects/hipblaslt/tensilelite/rocisa/rocisa/src/helper.cpp`, lines 76–90 and 133–137 (unchanged by this PR, but now called concurrently).

On POSIX, #13668 made the probe pipe `O_CLOEXEC` so that a child forked by another thread cannot inherit this probe's stdin write end. The Windows branch has the same hazard in a different form. Line 76 sets `bInheritHandle = TRUE`, so `CreatePipe` at line 87 creates both stdin ends inheritable. Only afterwards does line 89 clear inheritance on the write end. `CreateProcessA` is called with `bInheritHandles = TRUE` (line 137), which gives the child a copy of every inheritable handle in the process, not just the ones named in `STARTUPINFO`.

If thread B reaches `CreateProcessA` between thread A's lines 87 and 89, B's assembler receives a copy of A's stdin write end. A's assembler reads `-` until EOF, so it cannot finish before B's assembler exits. If A's `CreateProcessA` also lands in B's window, each assembler holds the other's write end. Both then wait for EOF indefinitely, and A's polling loop never sees its process exit. The window is short, which is consistent with the 3-ISA test passing once on `rocISA / Windows`. `TensileLogic` on Windows hipBLASLt builds, however, now creates thousands of processes from 24 threads at once. Separately, each probe's child-side ends (`hChildStd_IN_Rd`, `hChildStd_OUT_Wr`) stay inheritable in the parent until lines 167 and 206, so concurrent children also receive copies of other probes' pipes. That is harmless for the current read loop but unnecessary.

Fix this before enabling concurrency on Windows. Possible approaches:

- Create the pipes non-inheritable. Pass exactly the child's two handles through `STARTUPINFOEXA` with `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` and `EXTENDED_STARTUPINFO_PRESENT`. This is the most robust approach, and it is what Python's `subprocess` does on Windows.
- Hold a process-wide mutex from pipe creation through `CreateProcessA`, and close the parent's copies of the child-side ends immediately after `CreateProcessA`, inside the lock.
- Probe sequentially in `initMany` under `_WIN32` until `run()` is fixed.

No commit: I could not build or run the Windows path, and choosing among these options is a decision for the author.

### 2. A thread that fails to start aborts the interpreter

`projects/hipblaslt/tensilelite/rocisa/rocisa/include/base.hpp`, lines 135–148. Fixed in `e97c801e64f`.

`initMany` stores `std::thread`s in a vector and joins them after the creation loop. If constructing a later thread throws `std::system_error` (for example `EAGAIN` under a container pids limit or `RLIMIT_NPROC`), unwinding destroys the vector while earlier threads are still joinable, and `std::terminate` aborts the process. With an `LD_PRELOAD` shim that fails the third `pthread_create` (appendix A), the submitted PR prints `terminate called without an active exception` and exits with SIGABRT. `TensileLogic` then dies without a Python traceback.

The commit uses `std::vector<std::jthread>`; rocisa builds as C++20. `jthread` joins on destruction, so on that path the started probes finish, the GIL is reacquired and the error reaches Python as `RuntimeError: Resource temporarily unavailable`, with `isInit()` still false. The explicit join loop is no longer needed. No in-tree regression test is added, because one would need to compile and preload a native shim; appendix A gives the exact reproducer.

### 3. The stinkytofu adaptor still probes fallback ISAs one subprocess at a time

`projects/hipblaslt/tensilelite/rocisa_stinkytofu_adaptor/rocisa_stinkytofu_adaptor/base.py`, lines 261–268 and 271–316. Fixed in `ed013baa790`.

The description notes that gfx1250 builds and the unit lane use the stinkytofu backend. There, adaptor `initMany` calls `init()` for each arch. Every ISA without stinkytofu caps (23 of the 24 in `SUPPORTED_ISA`) goes through `_init_native_fallback`, which starts a fresh interpreter, imports native rocisa and probes that one ISA serially. Measured locally, adaptor `initMany` over `SUPPORTED_ISA` took 22.1 s with the PR, compared with 2.1 s for native `initMany`. The PR's speedup therefore does not reach `TensileLogic` on that backend.

The commit collects the ISAs without stinkytofu caps and probes them with one native `initMany` call in a single subprocess. It then calls `init()` for each arch as before, so `_current_isa`, `_assembler_path` and `_is_init` end up exactly as they would after per-arch `init()`. `_init_native_fallback` now takes a list of keys; `init` and `getIsaInfo` pass a one-element list. Locally the same call takes 1.83 s, and the resulting caps for all 24 ISAs are identical to per-arch adaptor `init()` (18.5 s). The PR's `test_initmany_inits_each_arch` is replaced by `test_initmany_probes_native_isas_in_one_fallback`. The new test feeds a generator with a duplicate and a stinkytofu-supported ISA. It requires one fallback call containing exactly the two native ISAs, checks the resulting table and checks that the last arch is selected. It fails with the PR's `base.py`.

## Suggestions

### 4. `initMany` accepts only a `list`

`projects/hipblaslt/tensilelite/rocisa/rocisa/include/base.hpp`, line 118, and `tensilelite/Common/Capabilities.py`, line 130. Fixed in `50b18c1c03d`.

Native `initMany` takes `const nb::list&`, so a tuple, generator or other sequence raises `TypeError`. The adaptor's `initMany`, documented as a mirror, accepts any iterable, as does calling `init()` in a loop. Code exercised only in the stinkytofu unit lane could therefore pass and then fail natively. `makeIsaInfoMap` already works around the restriction with `list(targetIsas)`. The commit takes `nb::iterable`, drops that copy, and adds `test_init_many_accepts_any_iterable`, which needs no assembler because it passes empty inputs. A tuple input to the submitted build raised `TypeError`; it is accepted on the branch.

### 5. `init` and `initMany` build `IsaInfo` separately

`projects/hipblaslt/tensilelite/rocisa/rocisa/include/base.hpp`, lines 107–112 and 153–161. Fixed in `bbe291b83da`.

Both entry points repeat the same four steps that build `IsaInfo` from the probed assembler caps. If a cap table were added to one and not the other, the two entry points would silently disagree; the new equivalence test covers only three ISAs. The commit moves those steps into one private `addIsaInfo` helper. It also removes the PR's misaligned assignment, which clang-format would rewrite.

## Commentary

- Concurrency equals the number of uninitialized ISAs, which is 24 for `TensileLogic`, with one assembler process each. That is modest compared with the build's own parallelism, and the CPU work is the same as before. A bound tied to `--jobs` would only matter if the ISA list grew substantially.
- With `debug=true`, `tryAssembler` writes five `std::cout` lines per probe from the worker threads, so debug output for different ISAs now interleaves. A debug investigation can pass one ISA at a time. Alternatively, a short comment on `initMany` could say that debug output is not ordered.
- After `initMany`, the `ti.init(v, ...)` calls in `makeIsaInfoMap` are no-ops natively. On the adaptor they still select the current ISA, as before. Keeping them is reasonable, because the loop does not have to know whether a backend implements `initMany`.
- The commit message for `61cb04542d9` gives 22 ISAs and ~66 s → ~6 s, while the description gives 24 ISAs and 18.2 s → 1.2 s. If the squash message is derived from the commits, aligning these would avoid confusion.

## Appendix A: thread-creation failure reproducer

`fail_third_thread.c`:

```c
// LD_PRELOAD shim: the third pthread_create in the process fails with EAGAIN,
// as it would when a container's pids limit or RLIMIT_NPROC is reached.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>

typedef int (*create_fn)(pthread_t*, const pthread_attr_t*, void* (*)(void*), void*);

int pthread_create(pthread_t* t, const pthread_attr_t* a, void* (*f)(void*), void* arg)
{
    static int calls = 0;
    static create_fn real;
    if(!real)
        real = (create_fn)dlsym(RTLD_NEXT, "pthread_create");
    if(++calls == 3)
        return EAGAIN;
    return real(t, a, f, arg);
}
```

```bash
clang -shared -fPIC -O1 -o fail_third_thread.so fail_third_thread.c -ldl
LD_PRELOAD=$PWD/fail_third_thread.so python -c "
import rocisa
ti = rocisa.rocIsa.getInstance()
try:
    ti.initMany([(9,4,2),(9,5,0),(12,0,1),(11,0,0)], '$ROCM_PATH/bin/amdclang++', False)
except Exception as e:
    print(type(e).__name__, e)
print('isInit', ti.isInit())
"
```

Submitted PR: `terminate called without an active exception`, exit status 134. With `e97c801e64f`: `RuntimeError Resource temporarily unavailable`, then `isInit False`.

## Appendix B: list-only input

```python
import rocisa
rocisa.rocIsa.getInstance().initMany((), "unused", False)
```

On the submitted PR this raises `TypeError: initMany(): incompatible function arguments`. With `50b18c1c03d` it returns without probing.
