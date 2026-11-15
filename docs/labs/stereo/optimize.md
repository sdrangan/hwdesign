---
title: One pixel per cycle
parent: Stereo Depth
nav_order: 3
has_children: false
---

# Stage 3: One pixel per cycle

Now the same kernel, bit for bit, with the compute phase at **one pixel per
clock cycle**. The load and store phases are written for you, pipelined at II
= 1 already; you write the compute phase and the pragmas it needs, in
`stereo.cpp`.

## What one pixel per cycle takes

Pipeline the pixel loop at II = 1, and everything inside it has to happen in
one iteration, every cycle:

* **The loops inside are unrolled.** A pipelined loop's body must be
  straight-line code, so Vitis unrolls the `d` loop and the 5x5 window
  completely: 16 x 25 = **400 absolute differences**, 16 adder trees and a
  16-way minimum, all at once. You do not need `UNROLL` pragmas for that, as
  long as the bounds are constants.
* **The data has to arrive.** Read as in the baseline, those 400 differences
  need 25 pixels of `L` and up to 20 x 5 of `R`, every cycle, from memories
  that deliver one word per port per cycle. That is the
  [memory bottleneck](../../demos/loopopt/unroll.md#without-partitioning-no-faster-at-all)
  of unrolling, at scale. Pipeline the baseline loop as it stands and the
  report will show an II in the hundreds.

The fix has two parts, and both are in this unit.

### 1. A delay line in two dimensions

Neighbouring pixels share most of their windows. Moving one pixel to the
right, the 5x5 window loses its leftmost column and gains one new column on the
right; the other 20 pixels are the same. So keep the window in **registers**,
and each cycle **shift** it one column left and read just **one new column**
of 5 pixels. That is the [FIR's delay line](../../demos/fir/kernel.md#delay-keep-the-samples-in-a-delay-line),
with columns instead of samples.

The right image needs a wider window. For disparity `d` the window is `d`
columns further left, so all 16 disparities together need **5 + 15 = 20
columns** of `R`, rows `y-2` to `y+2`: a 5 x 20 register window, shifted the
same way.

```cpp
pix_t lwin[WIN][WIN], rwin[WIN][RWIN];        // RWIN = WIN + NDISP - 1 = 20
```

Both have to be registers, readable all at once: partition them completely.

**Alignment.** When the newest column read is `x`, the left window's centre is
`xc = x - 2`, and that is the pixel whose disparity you have just computed.
Write it to `D[y][xc]`, not `D[y][x]`. This is the Moving average homework's
trap, in 2-D.

### 2. Five rows at once: partition the images

Each cycle reads one column of 5 pixels, rows `y-2` to `y+2`, from each image.
With each image in one memory, that is 5 reads through one port. Partition `L`
and `R` on their **row** dimension, cyclically, so that any 5 consecutive rows
are in 5 different memories:

```cpp
#pragma HLS ARRAY_PARTITION variable=L dim=1 type=cyclic factor=...
```

Row `y` goes to memory `y % factor`. Five consecutive rows are in five
different memories exactly when the factor is at least 5. Take a power of two:
then `y % factor` and `y / factor` are bit selects, where 5 needs a divider.
Compare part (d) of *Choosing a partition* in the LLM grader.

## Write it

The `TODO`s in `stereo.cpp` walk through it: the partition pragmas, the window
registers, and the compute loop. Keep the loop labels `comp_y` and `comp_x`: the
stage finds your compute loop in the report by its name. Rows `0, 1, 94, 95` are
never computed; the store phase writes 0 for anything outside the interior.

Two things that are not bugs:

* The windows are never cleared between rows. As `x` runs from 0, the window
  fills, and by the first interior pixel (`xc = 17`, so `x = 19`) every column
  in both windows is from the current row.
* Vitis flattens `comp_y` and `comp_x` into one loop, `comp_y_comp_x`, of 92 x
  128 iterations. That is what you want: the pipeline fills once per call, not
  once per row.

## Running the stage

```bash
python stereo_build.py --through opt
```

C simulation first, compared with your model, then synthesis, with the report
copied to `results/opt_csynth.rpt`. The stage grades:

* that C simulation matches your model
* that the compute loop is pipelined at **II = 1**
* that a whole call takes at most **40,000 cycles**
* that the design **fits** on the Zynq-7020

If the II is not 1, the synthesis log, `results/csynth/vitis.log`, says why:
search it for `II Violation`. A message naming `limited memory ports` on `L` or
`R` means the partition is missing or too small.

For the reference solution:

```text
|- comp_y_comp_x  |  11786|  11786|  12|  1|  1|  11776|  yes|
```

**36,378 cycles** for the whole call: load, 12,289; compute, 11,786; store,
12,290. That is about 470 times faster than the baseline. It uses about 29,000
LUTs, 55% of the chip, for the 400 absolute differences and their adder trees,
and no DSPs at all: there is no multiplication anywhere in this algorithm.

----

Go to [co-simulation and timing](./timing.md).
