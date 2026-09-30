---
title: AXI4-Streaming
parent: Demos
nav_order: 5
has_children: true
---

# AXI4-Stream Interface

In the [scalar function example](../procif/), the IP talked to the processor
through a set of AXI4-Lite registers. The processor wrote each input to a
register, started the IP, waited for it to finish and read the result back.
That costs several clock cycles per value, which is fine for a handful of
scalars and hopeless for a long stream of data. In this demo, we introduce
the **AXI4-Stream** interface, an efficient protocol for moving long,
continuous bursts of data, one value per clock cycle.

We focus on the simplest case, **pure streaming**: data flows in and out
continuously, with no explicit start or end of the stream, and one output
for every input. Later demos introduce **block** transfers, where the stream
is divided into frames.

The example is a **moving average of squares**: a filter that reads one
sample per clock and writes one filtered sample per clock.

In going through this demo, you will learn to:

- Implement a Vitis HLS kernel with pure AXI4-Stream interfaces and no
  start/done handshake
- Write a Python **golden model** that generates the test vectors and the
  expected output
- Drive C simulation, synthesis and RTL co-simulation from a **build
  script**, and compare each against the golden model
- Read the synthesis report of a pipelined streaming kernel
- Extract a **VCD** from the RTL simulation and read the AXI4-Stream
  handshake, the latency and the throughput off a **timing diagram**

## Pre-Requirements

You will need the [software set-up](../../support/amd/) for Vitis and Python,
and the [virtual environment](../../support/repo/package.md) that has
`waveflow`. It will help to have gone through the
[scalar function demo](../procif/) first, since this one uses the same build
script pattern.

## Where the files are

Everything is in `hwdesign/demos/stream/avgfilt`:

| File | What it is |
| --- | --- |
| `avgfilt.cpp`, `avgfilt.h` | the Vitis HLS kernel |
| `tb_avgfilt.cpp` | the testbench, used for both C simulation and co-simulation |
| `avgfilt_golden.py` | the test signal and the Python golden model |
| `avgfilt_timing.py` | decodes the streams from the RTL simulation's VCD and plots them |
| `run.tcl` | the Vitis HLS script, one stage per invocation |
| `avgfilt_build.py` | the build script that runs the steps in order |

All of them are written by hand and already in the repo. Nothing is
generated, and you do not need to write any code to run the demo.

---

Go to [AXI4-Stream Protocol](./axistream.md)
