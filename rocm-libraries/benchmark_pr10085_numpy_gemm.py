#!/usr/bin/env python3
"""Time an 8192x8192x8192 NumPy GEMM for comparison with PR 10085."""

import argparse
import os
import statistics
import time


parser = argparse.ArgumentParser()
parser.add_argument("--size", type=int, default=8192)
parser.add_argument("--threads", type=int, default=12)
parser.add_argument("--repetitions", type=int, default=3)
args = parser.parse_args()

for variable in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "BLIS_NUM_THREADS",
):
    os.environ[variable] = str(args.threads)

# Import after setting the BLAS thread environment.
import numpy as np


def median_ms(samples):
    return statistics.median(samples) * 1.0e3


def gflops(size, seconds):
    return 2.0 * size**3 / seconds / 1.0e9


n = args.size
rng = np.random.default_rng(10085)

print(f"NumPy {np.__version__}, n={n}, BLAS threads={args.threads}")

# Pure float32 SGEMM: the optimized operation underlying the hipBLASLt CPU
# reference after its f16 inputs have been converted.
a32 = rng.standard_normal((n, n), dtype=np.float32)
b32 = rng.standard_normal((n, n), dtype=np.float32)
d32 = np.empty((n, n), dtype=np.float32)
np.matmul(a32, b32, out=d32)

sgemm_times = []
for _ in range(args.repetitions):
    start = time.perf_counter()
    np.matmul(a32, b32, out=d32)
    sgemm_times.append(time.perf_counter() - start)

sgemm_seconds = statistics.median(sgemm_times)
print(
    f"float32 SGEMM:                  {median_ms(sgemm_times):8.1f} ms"
    f"  ({gflops(n, sgemm_seconds):.1f} GFLOP/s)"
)

del a32, b32, d32

# Closer model of the PR comment's f16 CPU reference:
# convert f16 A/B/C to f32, run SGEMM, add C (beta=1), then convert D to f16.
a16 = rng.standard_normal((n, n), dtype=np.float32).astype(np.float16)
b16 = rng.standard_normal((n, n), dtype=np.float32).astype(np.float16)
c16 = rng.standard_normal((n, n), dtype=np.float32).astype(np.float16)

conversion_times = []
gemm_times = []
output_times = []
total_times = []

for _ in range(args.repetitions):
    total_start = time.perf_counter()

    conversion_start = time.perf_counter()
    a32 = a16.astype(np.float32)
    b32 = b16.astype(np.float32)
    c32 = c16.astype(np.float32)
    conversion_times.append(time.perf_counter() - conversion_start)

    d32 = np.empty((n, n), dtype=np.float32)
    gemm_start = time.perf_counter()
    np.matmul(a32, b32, out=d32)
    gemm_times.append(time.perf_counter() - gemm_start)

    output_start = time.perf_counter()
    d32 += c32
    d16 = d32.astype(np.float16)
    output_times.append(time.perf_counter() - output_start)

    total_times.append(time.perf_counter() - total_start)
    del a32, b32, c32, d32, d16

print(f"f16 input conversion:           {median_ms(conversion_times):8.1f} ms")
print(f"f16-reference float32 SGEMM:    {median_ms(gemm_times):8.1f} ms")
print(f"beta*C and f16 output convert:  {median_ms(output_times):8.1f} ms")
print(f"f16-reference modeled total:    {median_ms(total_times):8.1f} ms")
