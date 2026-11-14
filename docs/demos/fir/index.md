---
title: "FIR: Nested Loops"
parent: Demos
nav_order: 9
has_children: true
---

# FIR: Nested Loops

Most real kernels are not one loop but several, one inside another: a loop
over the outputs around a loop over the terms of each one. A filter, a
matrix-vector product, a convolution. Which loop should be pipelined? What
happens to the inner loop when the outer one is? And where should each
term's data come from?

This demo answers those questions on the classic example, a **finite
impulse response (FIR) filter**: 16 taps, on 16-bit integer samples,

```
y[n] = h[0]*x[n] + h[1]*x[n-1] + ... + h[15]*x[n-15],     x[n] = 0 for n < 0
```

for every sample `n` of an array. The same arithmetic, 16 multiplies and
16 adds per output, is written four ways and synthesized by Vitis HLS:

| Variant | The loop nest | Cycles per sample | DSP |
| --- | --- | --- | --- |
| `inner` | the tap loop pipelined, the nest kept as two loops | 25 | 1 |
| `flat` | the same code, flattened by Vitis into one loop | 16 | 1 |
| `outer` | the sample loop pipelined: 16 reads of `x` per sample | 16 | 16 |
| `delay` | the sample loop pipelined, with a delay line | **1** | 16 |

The [loop optimization demo](../loopopt/) pipelined and unrolled a single
loop. Here the question is the nest.

## Learning Objectives

In going through this demo, you will:

- Pipeline the **inner** loop of a nest, and measure the cost of filling and
  draining it once per outer iteration
- See Vitis **flatten** a loop nest into one loop, and switch flattening off
  to compare
- Pipeline the **outer** loop, and see Vitis **unroll** the inner loop to do
  it
- Find the **memory port** limit an unrolled inner loop runs into, and read
  it in the synthesis log
- Remove it with a **delay line**: read each sample once and keep the last
  16 in registers
- Read the trade-off: one multiplier at 16 cycles per sample, or 16 at one

## The pages

1. [The kernel](kernel.md): the four ways of writing the nest, in one
   source, and the build.
2. [The results](results.md): the synthesis report for each, why each
   takes the cycles it does, and the delay line in RTL simulation.

## The code

Everything is in `hwdesign/demos/fir`:

| File | What it is |
| --- | --- |
| `fir.cpp`, `fir.h` | the kernel; `FIR_VARIANT` picks the way the nest is written |
| `tb_fir.cpp` | the testbench, for C simulation and co-simulation |
| `run.tcl` | the Vitis HLS script: `csim`, `synth` or `cosim` per invocation |
| `golden.py` | the test vector and an integer Python model |
| `fir_build.py` | the build script: which tool runs when, and what is checked |

To run all of it, in `hwdesign-venv` with Vitis installed:

```bash
(env) cd demos/fir
(env) python fir_build.py --through report    # check and synthesize: about 3 minutes
(env) python fir_build.py                     # co-simulate the delay line too
```
