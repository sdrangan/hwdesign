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
sample; everything interesting is in the interfaces. No task that does the arithmetic touches
an address bus. Instead it sends a **memory command**, "read `len` words starting at word
`addr`", and a **data mover** (one of Waveflow's memory adaptors) turns it into AXI bursts and
streams the words back.

## Three designs

The same histogram is built three ways. All three take the same `HistCmd`, send the same
`HistResp`, run the same five test jobs and are checked against the same NumPy golden.

| Design | Unit | What it shows |
| --- | --- | --- |
| [`hist_simple`](simple.md) | 9 | One compute task and two plain data movers. The compute task runs each job start to finish: send a read command, bin the samples, send a write command and the counts, **wait** for the write's completion, respond. Jobs never overlap. |
| [`hist_mmqueue`](mmqueue.md) | 9 | `hist_simple`'s kernel, unchanged, behind memory-mapped queues, so a host sends commands and collects responses with ordinary bus writes and reads. |
| [`hist_pipeline`](pipeline.md) | 10 | Five tasks on Waveflow's framed movers, with one descriptor per job carried through all of them, so the next job's read starts while this one is still computing and writing. |

**Why two kernels.** Unit 9 is about the *mechanics* of a transaction: a command to a data
mover, a burst on the bus, a write acknowledgement, a completion message, a response. In
`hist_simple` every one of those happens in order, one job at a time, inside one function a
student can read top to bottom, so each step can be found in the waveform. Its cost is that the
read port sits idle while the job's counts are written and acknowledged, and the write port
sits idle while the samples are read. Unit 10 is about removing that idle time
(load–compute–store), and `hist_pipeline` is the reference for it: the same jobs finish in
3369 cycles instead of 3567. Unit 10's own example may be a different kernel; `hist_pipeline`
is kept building and passing as the contrast.

## Learning objectives

With `hist_simple` and `hist_mmqueue` (unit 9), you will:

- Follow one job through the **command–response protocol**: a command in, a memory command to
  each data mover, a completion from the write mover, a response out
- Define messages once in Python and use the **generated serialization** in C++, with no hand
  packing
- See how the data movers take **word offsets** and turn them into AXI bursts
- Keep a loop at **II=1** through a read-modify-write, by holding the counts in registers
- Read the **timing of a job** from an RTL waveform: the command, the read burst, the
  compute, the write burst, the acknowledgement, the completion and the response
- See why a response must wait for the **write acknowledgement**
- Put a stream kernel behind **memory-mapped queues**, so a processor can drive it

With `hist_pipeline` (unit 10), you will see consecutive jobs **overlap**, what it takes (a
descriptor that travels with the data, FIFOs deep enough to hold it), and why the read port
stays the bottleneck.

## The pages

1. [hist_simple](simple.md): the top, the compute task, the messages, how it is checked, and
   the measured timing of each job.
2. [hist_mmqueue](mmqueue.md): the same kernel behind a memory-mapped slave adaptor, and the
   timing seen from the host.
3. [hist_pipeline](pipeline.md): the overlapped design, its top and its timing, for unit 10.
4. [hist_pipeline's tasks](pipeline_tasks.md): its descriptor, its streams and its task bodies.
5. [Messages and serialization](messages.md): how a message is declared in Python, what the
   generator produces, and the two ways to carry information with a memory transfer.

## The code

Everything is in `hwdesign/demos/histogram`. The Python is shared; each design has a
directory:

| Path | What it is |
| --- | --- |
| `hist_schema.py` | `HistCmd`, `HistResp` (and `hist_pipeline`'s `HistDesc`), as Waveflow data schemas |
| `hist_golden.py` | the test jobs, the memory image and the NumPy golden |
| `hist_timing.py` | the per-job timing, measured from the RTL waveform, and the timeline figures |
| `hist_build.py` | the build script, with `--design simple`, `mmqueue` or `pipeline` |
| `run.tcl` | the Vitis HLS script: C simulation or synthesis of one design |
| `simple/` | `hist_simple.cpp` (the top and the compute task), `hist_simple.h`, and the testbenches |
| `mmqueue/` | `hist_mmqueue.v` (the slave adaptor around `hist_simple`) and its host testbench |
| `pipeline/` | `hist_pipeline.cpp`, its three task bodies, and the testbenches |

To run it, in `hwdesign-venv` with Vitis and Vivado installed:

```bash
(env) cd demos/histogram
(env) python hist_build.py --through verify_csim     # hist_simple, C simulation: about 45 s
(env) python hist_build.py                           # + synthesis, RTL and timing: about 2 min
(env) python hist_build.py --design mmqueue          # about 2 minutes
(env) python hist_build.py --design pipeline         # about 2 minutes
```
