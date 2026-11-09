---
title: Loop Optimization
parent: Demos
nav_order: 8
has_children: true
---

# Loop Optimization

Hardware pays off most when the same work is repeated many times: a loop,
in software. A processor runs one iteration after another. Custom
hardware can do better in two ways, and this demo measures both, on the
polynomial from the lecture evaluated over an array of samples:

```
y[i] = c0 + c1*x[i] + c2*x[i]^2 + c3*x[i]^3
```

1. **Pipelining**: start the next iteration before the last one has
   finished. One evaluation takes 30 clock cycles, but a pipelined loop
   starts a new one every cycle, so 30 are in progress at once.
2. **Unrolling**: build several copies of the loop body, so several
   samples start in each cycle. That only pays if the memories holding
   `x` and `y` can deliver that many words per cycle, which is what
   **array partitioning** is for.

The [timing demo](../timing/) did this for a single computation with no
loop. Here the loop is the point.

## Learning Objectives

In going through this demo, you will:

- Use the **`PIPELINE` pragma** to pipeline a loop in Vitis HLS, and switch
  pipelining off to compare
- Read a loop's **initiation interval (II)**, **iteration latency** and
  **trip count** from the synthesis report, and from them the cycles for
  the whole call
- Read the **schedule** of a pipelined loop: which operation is in which
  cycle of an iteration, and how the iterations overlap
- See pipelining in an **RTL simulation**: a new address on the `x` memory
  every cycle, instead of one every 30
- Use the **`UNROLL` pragma**, and the **`ARRAY_PARTITION` pragma** to give
  the unrolled loop the memory ports it needs
- Measure the trade-off: **throughput** against **DSP blocks, LUTs and
  flip-flops**, as the unroll factor grows

## The pages

Part 1, pipelining:

1. [The kernel](kernel.md): the polynomial in C++, its memory interface,
   and the pragmas, switched on and off by macros so one source builds
   every variant.
2. [Pipelining the loop](pipeline.md): the build steps, the synthesis
   report with and without the `PIPELINE` pragma, and the two RTL
   simulations.
3. [The pipeline schedule](schedule.md): which operation Vitis put in which
   cycle, and why a new iteration can start every cycle.

Part 2, unrolling:

4. [Unrolling the loop](unroll.md): unroll factors 2, 4 and 8, the memory
   bottleneck without partitioning, and throughput against resources.

## The code

Everything is in `hwdesign/demos/pipeline/poly`:

| File | What it is |
| --- | --- |
| `poly.cpp`, `poly.h` | the kernel; its pragmas are switched by the `POLY_*` macros |
| `tb_poly.cpp` | the testbench, for C simulation and co-simulation |
| `run.tcl` | the Vitis HLS script: `csim`, `synth` or `cosim` per invocation |
| `golden.py` | the test vector and an independent FP32 Python model |
| `poly_analysis.py` | reads the reports and schedules, and plots them and the waveforms |
| `poly_build.py` | the build script: which tool runs when, and what is checked |

To run all of it, in `hwdesign-venv` with Vitis installed:

```bash
(env) python poly_build.py --through pipeline    # part 1
(env) python poly_build.py                       # part 2 as well
```
