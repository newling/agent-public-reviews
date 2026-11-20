#include <cstdio>
#include <cstdlib>
#include <hip/hip_runtime.h>
#include <vector>
__device__ int wave() { return __builtin_amdgcn_readfirstlane(threadIdx.x) / 32; }
__device__ int lane() { return threadIdx.x % 32; }
__device__ void drain() { asm volatile("s_wait_dscnt 0" ::: "memory"); }
__device__ void wgSignal() { asm volatile("s_barrier_signal -1" ::: "memory"); }
__device__ void wgWait() { asm volatile("s_barrier_wait -1" ::: "memory"); }
__device__ void group() {
  wgSignal();
  wgWait();
}
__device__ void waitNamed() { asm volatile("s_barrier_wait 1" ::: "memory"); }
__device__ void writeLds(int tile, int value) {
  unsigned address = tile * 128 + lane() * 4;
  asm volatile("ds_store_b32 %0, %1" ::"v"(address), "v"(value) : "memory");
}
__device__ int readLds(int tile) {
  unsigned address = tile * 128 + lane() * 4;
  int value;
  asm volatile("ds_load_b32 %0, %1\ns_wait_dscnt 0" : "=v"(value) : "v"(address) : "memory");
  return value;
}
// This is a scheduling perturbation, not a memory handoff.
__device__ void delay() {
  for (int i = 0; i < 512; ++i)
    asm volatile("s_nop 7");
}
__global__ __attribute__((amdgpu_flat_work_group_size(96, 96))) void
thresholdKernel(int *out, int threshold, int delayed, int readBoth) {
  __shared__ __amdgpu_named_workgroup_barrier_t ready;
  if (wave() == 0)
    __builtin_amdgcn_s_barrier_init(&ready, threshold);
  if (wave() == 2)
    __builtin_amdgcn_s_barrier_join(&ready);
  group();
  if (wave() < 2) {
    writeLds(wave(), 100 + 100 * wave() + lane());
    drain();
    if (wave() == delayed)
      delay();
    __builtin_amdgcn_s_barrier_signal_var(&ready, 0);
  } else {
    waitNamed();
    out[lane()] = readLds(0);
    if (readBoth)
      out[32 + lane()] = readLds(1);
  }
  group();
}
// A signals the workgroup before writing. B relays A's later write by
// waiting on ab and then terminating instead of signalling the workgroup.
// C's workgroup wait must acquire B's knowledge of A. The ack keeps A alive.
// Mode 1 removes A's drain before its named signal. Mode 2 removes B's wait.
template <int Mode>
__global__ __attribute__((amdgpu_flat_work_group_size(96, 96))) void exitRelayKernel(int *out) {
  __shared__ __amdgpu_named_workgroup_barrier_t ab, ack;
  if (wave() == 0) {
    __builtin_amdgcn_s_barrier_init(&ab, 1);
    __builtin_amdgcn_s_barrier_init(&ack, 1);
    __builtin_amdgcn_s_barrier_join(&ack);
  } else if (wave() == 1)
    __builtin_amdgcn_s_barrier_join(&ab);
  group();
  if (wave() == 0) {
    wgSignal();
    writeLds(0, 300 + lane());
    if constexpr (Mode != 1)
      drain();
    __builtin_amdgcn_s_barrier_signal_var(&ab, 0);
    if constexpr (Mode == 1)
      drain();
    waitNamed();
    wgWait();
  } else if (wave() == 1) {
    if constexpr (Mode != 2)
      waitNamed();
    // This wave's s_endpgm substitutes for its workgroup signal.
  } else {
    wgSignal();
    wgWait();
    out[lane()] = readLds(0);
    __builtin_amdgcn_s_barrier_signal_var(&ack, 0);
  }
}
// Count five signals from two producers, then return buffer ownership using
// a distinct barrier. Both producers listen for the consumer's one ack.
__global__ __attribute__((amdgpu_flat_work_group_size(96, 96))) void
countedPipelineKernel(int *out) {
  __shared__ __amdgpu_named_workgroup_barrier_t ready, consumed;
  if (wave() == 0) {
    __builtin_amdgcn_s_barrier_init(&ready, 5);
    __builtin_amdgcn_s_barrier_init(&consumed, 1);
  }
  if (wave() < 2)
    __builtin_amdgcn_s_barrier_join(&consumed);
  else
    __builtin_amdgcn_s_barrier_join(&ready);
  group();
  for (int iteration = 0; iteration < 32; ++iteration) {
    if (wave() < 2) {
      writeLds(wave(), iteration * 1000 + 100 * wave() + lane());
      drain();
      for (int arrival = 0; arrival < wave() + 2; ++arrival)
        __builtin_amdgcn_s_barrier_signal_var(&ready, 0);
      waitNamed();
    } else {
      waitNamed();
      out[lane()] = readLds(0);
      out[32 + lane()] = readLds(1);
      __builtin_amdgcn_s_barrier_signal_var(&consumed, 0);
    }
  }
  group();
}
void check(hipError_t error) {
  if (error != hipSuccess) {
    std::fprintf(stderr, "HIP error: %s\n", hipGetErrorString(error));
    std::exit(2);
  }
}
int main(int argc, char **argv) {
  int test = argc > 1 ? std::atoi(argv[1]) : 0;
  int *out;
  check(hipMalloc(&out, 64 * sizeof(int)));
  check(hipMemset(out, 0xa5, 64 * sizeof(int)));
  if (test < 8)
    thresholdKernel<<<1, 96, 256>>>(out, (test & 4) ? 2 : 1, test & 1, (test & 2) != 0);
  else if (test == 8)
    exitRelayKernel<0><<<1, 96, 256>>>(out);
  else if (test == 9)
    exitRelayKernel<1><<<1, 96, 256>>>(out);
  else if (test == 10)
    exitRelayKernel<2><<<1, 96, 256>>>(out);
  else
    countedPipelineKernel<<<1, 96, 256>>>(out);
  check(hipGetLastError());
  check(hipDeviceSynchronize());
  std::vector<int> values(64);
  check(hipMemcpy(values.data(), out, 256, hipMemcpyDeviceToHost));
  std::printf("case=%d output[0]=%d output[32]=%d\n", test, values[0], values[32]);
  // Unordered reads have no prescribed value.
  if ((test >= 4 && test <= 8) || test == 11) {
    for (int i = 0; i < 32; ++i)
      if (values[i] != (test == 11 ? 31000 : test == 8 ? 300 : 100) + i)
        return 3;
    if (test == 11 || (test < 8 && (test & 2)))
      for (int i = 0; i < 32; ++i)
        if (values[32 + i] != (test == 11 ? 31100 : 200) + i)
          return 3;
  }
  check(hipFree(out));
}
