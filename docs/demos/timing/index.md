---
title: Timing and the Clock
parent: Demos
nav_order: 7
has_children: true
---

# Timing and the Clock

Unit 6 computes critical paths by hand: add the delays along each path,
compare the longest with the clock period, and split a computation over
more cycles when it does not fit. This demo lets Vitis HLS do the same
thing, for the quadratic from the lecture,

```
y = w2*x^2 + w1*x + w0
```

synthesized again and again at clock frequencies from 50 to 400 MHz. At
each one, Vitis decides how many clock cycles the computation needs. The
synthesis reports say how many, and an RTL simulation shows them on the
wires.

## Learning Objectives

In going through this demo, you will:

- Build a Vitis HLS kernel with **no AXI interface**: plain input wires, an
  output wire, and a start/done handshake
- Measure the **latency in cycles** and **latency in nanoseconds** from a **synthesis report**.
- Measure the latency as a function of the clock frequency.  The latency in cycles will increase with higher clock frequency, while the latency in nanoseconds will be approximately constant. 
- Find the fastest clock the design **meets timing** at, from the synthesis estimate
- Measure the benefit of **pipelining**: the same latency, but a new input every
  cycle

There are no loops here; they arrive in the next unit.

## The pages

1. [The kernel](kernel.md): the quadratic in C++, the lecture's block
   diagram of it, and the interface: plain wires and a start/done
   handshake, with no AXI.
2. [Synthesis at one clock](synth.md): the build steps at 100 MHz, how to
   read the synthesis report, reading it from Python with waveflow, and
   the RTL simulation's timing diagram.
3. [Analyzing the schedule](synth_sched.md): which operation Vitis put in
   which clock cycle, where the report is, and the timing slack, for the
   whole design and for each cycle.
4. [In-class exercise: beat the schedule](synth_inclass.md): rewrite the
   kernel so Vitis schedules it in fewer cycles, and build your version
   with `--fast`.
5. [Sweeping the clock](sweep.md): the same at seven clocks from 50 to
   400 MHz, the code that does it, the graphs, and what pipelining buys.

## The code

Everything is in `hwdesign/demos/timing/quad`:

| File | What it is |
| --- | --- |
| `quad.cpp`, `quad.h` | the kernel and its interface pragmas |
| `tb_quad.cpp` | the testbench, for C simulation and co-simulation |
| `run.tcl` | the Vitis HLS script: `csim`, `sweep` or `cosim` per invocation |
| `golden.py` | the test vector and an independent Python model |
| `quad_timing.py` | reads the synthesis reports, and plots them and the waveforms |
| `quad_build.py` | the build script: which tool runs when, and what is checked |

To run all of it, about eight minutes, in `hwdesign-venv` with Vitis
installed:

```bash
(env) python quad_build.py
```
