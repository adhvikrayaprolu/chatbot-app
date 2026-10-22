# GPU Study Notes — original public demo

## Thread indexing
For a one-dimensional CUDA launch, a thread computes its global index as blockIdx.x * blockDim.x + threadIdx.x. A bounds guard compares this index with the array length before reading or writing. This handles the final partially filled block.

## Memory coalescing
Adjacent threads accessing adjacent elements allow memory accesses to be combined into fewer transactions. Strided accesses may require more transactions. Coalescing concerns global-memory access patterns; shared-memory bank conflicts are a separate issue.

## Synchronization
A block barrier waits for participating threads within the same block. It does not synchronize separate blocks. All required threads must reach a block barrier consistently; placing it in a branch taken by only part of a block can be invalid.

## Tiling
A tiled matrix multiplication stages reusable input tiles in shared memory. Threads load tiles cooperatively, synchronize before consuming them, and synchronize before overwriting them with the next tile. Boundary checks remain necessary for dimensions not divisible by the tile size.

## Measurement
Report workload dimensions, precision, hardware, compiler options and timing method. Warm-up runs should be separated from measured runs. GPU operations are asynchronous, so host timings need appropriate synchronization or device events. A speedup claim requires comparable measured baselines.

These notes are independently written for this repository. They are not an excerpt or conversion of the private textbook.
