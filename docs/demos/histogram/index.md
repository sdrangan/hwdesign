---
title: "Histogram: Transactional Memory"
parent: Demos
nav_order: 10
has_children: true
---

# Histogram: Transactional Interfaces to Memory

An accelerator rarely gets its data handed to it on a stream. More often the data sits in
DRAM, and the host only says *where*: "the samples are at this address, there are `n` of
them, put the result over there." The kernel then has to fetch its own inputs and store its
own outputs. How should it talk to memory, and how does the host know a job is done?

This demo answers those questions on a small, concrete kernel: a **histogram**. Given `n`
32-bit samples in memory, count how many land in each of 32 bins,

```
bin = min(x >> shift, 31)
```

and write the 32 counts back to memory. The arithmetic is one shift and one increment per
sample; everything interesting is in the interfaces. The kernel is built from **concurrent
tasks** (`hls::task`), and none of the tasks it is made of touches an address bus directly.
Instead a task sends a **memory command**, "read `len` words starting at word `addr`", and a
**data mover** (one of Waveflow's memory adaptors) turns it into AXI bursts and streams the
words back.

```
s_cmd -> control --rd_cmd--> mem_r_stream --rd_data--> compute --wr_data--> mem_w_stream_done
             |                   (m_rd)                    ^                  (m_wr)   |
             +-------------------- job --------------------+                  wr_done |
                                                                                       v
                                                             s_done <- response <------+
```

## Learning Objectives

In going through this demo, you will:

- Follow one job through the **command–response protocol**: a command in, memory commands
  to the data movers, a response out once the job's results are written
- Write a **compute task** that sees only streams, never an address
- See how the data movers take **word offsets** and turn them into AXI bursts
- Keep a loop at **II=1** through a read-modify-write, by holding the counts in registers
- Read the **timing of a job** from an RTL waveform: the command, the read burst, the
  compute, the write burst and the response, and the latency `L` before the first word
- See consecutive jobs **overlap**, and why the read port stays the bottleneck

## The pages

1. [The tasks and messages](tasks.md): the command and response, the memory commands, and
   the body of each task. These are shared by every version of the kernel.
2. [The stream version](stream.md): the top, with the command and response on AXI4-Streams;
   how it is built and checked; and the measured timing of each job.

## The code

Everything is in `hwdesign/demos/histogram`:

| File | What it is |
| --- | --- |
| `hist_types.h` | constants, the job descriptor, and the includes every task shares |
| `hist_control.h`, `hist_compute.h`, `hist_response.h` | the three task bodies |
| `histogram_stream.cpp` | the stream version's top |
| `tb_histogram_stream.cpp` | its C simulation testbench |
| `tb_xsi_histogram_stream.cpp` | its RTL testbench, run through XSI |
| `hist_schema.py` | the command and response, as Waveflow data schemas |
| `hist_golden.py` | the test jobs and the NumPy golden |
| `hist_timing.py` | the per-job timing, measured from the RTL waveform |
| `hist_build.py` | the build script |

To run all of it, in `hwdesign-venv` with Vitis and Vivado installed:

```bash
(env) cd demos/histogram
(env) python hist_build.py --through verify_csim    # C simulation: about 15 seconds
(env) python hist_build.py                          # synthesis, RTL and timing: about 75 seconds
```
