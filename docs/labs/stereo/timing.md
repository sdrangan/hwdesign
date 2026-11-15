---
title: Co-simulation and timing
parent: Stereo Depth
nav_order: 4
has_children: false
---

# Stage 4: Co-simulation and timing

The synthesis report says how long a call *should* take. Co-simulation runs the
RTL Vitis generated, cycle by cycle, and shows what it *does*.

## Co-simulation

```bash
python stereo_build.py --through cosim
```

This runs `tb_stereo.cpp` against `stereo.cpp`'s RTL, about four minutes, and
writes its disparities to `vectors/disp_cosim.txt`. Then it re-runs the RTL
simulation with every port recorded, and turns the recording into a table with
one row per clock cycle of the call, `results/cosim/signals.csv`:

| Column | Port | |
| --- | --- | --- |
| `cycle` | | 0 at the rising edge where `ap_start` is first 1, or a word is first taken, whichever is first |
| `ap_start`, `ap_done` | | the block-level handshake |
| `in_valid`, `in_ready` | `pix_in_TVALID`, `pix_in_TREADY` | a pixel word is offered, and taken |
| `out_valid`, `out_ready` | `disparity_TVALID`, `disparity_TREADY` | a disparity is offered, and taken |

Why "whichever is first"? The kernel takes its first two words a cycle or two
*before* `ap_start`. Vitis puts a **register slice** on each AXI4-Stream port,
a two-word buffer that keeps the stream's timing paths short, and the input's
accepts words as soon as they are offered, whether or not the kernel has been
started. Look for it in the first rows of the table.

## `stereo_timing.py`

A word moves on an AXI4-Stream in a cycle where VALID and READY are both 1: a
**handshake**. From the handshakes you can find the three phases:

| Phase | From | To |
| --- | --- | --- |
| **load** | the first input handshake | the last input handshake |
| **compute** | the cycle after the last input handshake | the cycle before the first output handshake |
| **store** | the first output handshake | the last output handshake |

You write two functions:

* `find_phases(sig)` returns them as `{"load": (first, last), "compute": ...,
  "store": ...}`, inclusive, in the table's cycle numbers.
* `plot_phases(sig, phases, path)` draws the whole call as a timing diagram:
  the input and output handshakes and `ap_done` as 0/1 traces, one above the
  other, with the three phases shaded or labeled and their lengths given.

At this scale a timing diagram is a picture of where the time goes: 36,000
cycles, each trace a solid bar while its stream is busy.

## Running the stage

```bash
python stereo_build.py --through timing
```

It grades:

* that co-simulation matches your model, bit for bit
* that `find_phases()` finds the same phases the build does, from the same table
* that the phases are what the design intends: 12,288 words in and 12,288 out,
  each phase about one word per cycle, the call within 40,000 cycles
* that you drew the diagram, `results/phases.png`

![A timing diagram of one call of the reference kernel. The input handshake trace is solid for the first third of the call, the load phase, 12,293 cycles; then nothing happens on either stream for the compute phase, 11,794 cycles; then the output handshake trace is solid for the last third, the store phase, 12,288 cycles. ap_start is high throughout; ap_done is a single cycle at the very end.](./images/phases.png)

For the reference solution, co-simulation measures **36,374 cycles** for the
call: load 12,293, compute 11,794, store 12,288, within a few cycles of the
synthesis report's estimate.

## What the diagram says

The three phases **do not overlap**. For the first third of the call the
compute hardware, 400 absolute differences, sits idle, waiting for the frame
to arrive. For the middle third the input stream is idle. For the last third,
both are.

That is the price of the simple structure: a whole frame in block RAM, then
computed, then sent. Two questions to think about before the next unit:

* The compute phase needs rows `y-2` to `y+2` to compute row `y`. When, during
  the load, does it have everything it needs for its first row? How much of the
  load could the compute have overlapped?
* If it computed as the rows arrived, how many rows of each image would it ever
  need to hold at once? What would that do to the BRAM count, and to the
  largest image the kernel could handle?

The answers are **line buffers** and the **load-compute-store** pattern, and
they are the next unit.

----

Go to [grading and submission](./submit.md).
