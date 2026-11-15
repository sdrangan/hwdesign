---
title: Stereo Depth
parent: Labs
nav_order: 6
has_children: true
---

# Unit 8 Lab: Stereo Depth in Vitis HLS

## Overview

Two cameras a few centimetres apart see the same scene from slightly different
places. A near object appears in noticeably different positions in the two
images; a far one hardly moves. That shift, the **disparity**, is how a robot,
a drone or an AR headset judges depth: depth is inversely proportional to
disparity.

In this lab you build a hardware accelerator that computes a **disparity map**
from a pair of images by **block matching**: for every pixel of the left image,
it searches along the same row of the right image for the 5x5 block that
matches best.

![Three panels: the lab's left and right images, a textured background with a striped rectangle and a checked disc in front of it, and the disparity map computed from them, in which the background, the rectangle and the disc appear as three flat regions of increasing disparity.](./images/disparity.png)

The algorithm is a few lines. Making it fast is the lab. Written as plain
loops, the kernel takes about **17 million clock cycles** for one 96 x 128
frame. Pipelined and unrolled, with its memories partitioned to match, it
computes **one pixel per clock cycle**, about 470 times faster. You will make
that change yourself, and measure every step of it.

## Learning Objectives

In going through the lab, you will:

* Build a **golden model** of block-matching stereo in Python, and check it on
  scenes whose depth you know
* Write a **baseline Vitis HLS kernel** from the model, bit-exact, and measure
  its latency and resources
* Optimize it to **II = 1**: **pipeline** the pixel loop, **unroll** the 16
  disparities and the 5x5 window, **partition** the images so a 5-row column
  can be read in one cycle, and keep the windows in **registers**, a delay line
  in two dimensions
* **Co-simulate** the optimized kernel and read its timing: the **load,
  compute and store** phases of one call, and why they do not overlap

This is the unit's material at scale. The [FIR demo](../../demos/fir/) has a
nest of two loops and a 1-D delay line. Here the nest is four loops deep, the
window is 2-D, and pipelining the pixel loop unrolls 400 absolute differences
and a 16-way minimum into a single cycle.

## The algorithm

The images are **rectified**: warped so that the two cameras' rows line up. A
point in the scene then appears on the *same row* in both images, shifted left
in the right image by its disparity `d`. So the search for a match runs along
the row only.

For a pixel `(y, x)` of the left image, and each candidate disparity
`d = 0, 1, ..., 15`, compare the 5x5 window around `(y, x)` in the left image
with the 5x5 window around `(y, x - d)` in the right image, by the **sum of
absolute differences**:

```
SAD(y, x, d) = sum over i, j in -2 .. 2 of | L[y+i][x+j] - R[y+i][x+j-d] |
```

The pixel's disparity is the `d` with the **smallest SAD**. The complete
specification, which the model and both kernels have to meet exactly, is in
`stereo.h`:

* **Ties** go to the smallest `d`.
* Pixels whose window, or whose shifted window for some `d`, would fall off the
  image get disparity **0**. So disparities are computed in the **interior**
  `2 <= y < 94`, `17 <= x < 126`.
* Pixels and SADs are integers (`uint8` pixels, 16-bit SADs), so "matches"
  means **bit for bit**.

## The interface

The kernel is the command-response pattern's simpler cousin from unit 5:
pixels in on one AXI4-Stream, disparities out on another, and `ap_start` /
`ap_done` for the call.

```cpp
void stereo(hls::stream<in_word_t> &pix_in, hls::stream<out_word_t> &disparity);
```

It reads 96 x 128 words, one per pixel in raster order, each carrying the left
pixel in bits 7:0 and the right pixel in bits 15:8. It writes 96 x 128
disparities in the same order, with TLAST on the last. Inside, every version
works in three **phases**, one after the other:

| Phase | What it does |
| --- | --- |
| **load** | read the input words into two on-chip arrays, `L` and `R` |
| **compute** | compute every pixel's disparity into an array `D` |
| **store** | write `D` out |

The images are small enough that a whole frame fits in block RAM, which is what
makes this simple. It is also what costs time: nothing is computed until the
whole frame has arrived. Removing that wait is the next unit's subject.

## Files

```
hwdesign/
└── labs/
    └── stereo/
        ├── stereo_build.py      # Runs the build steps and scores them
        ├── run.tcl              # The Vitis HLS script, one stage per run
        ├── stereo.h             # The interface and the specification
        ├── tb_stereo.cpp        # The testbench, for both kernels
        ├── scene_left.png       # The scene every kernel is run on
        ├── scene_right.png
        ├── partial/
        │   ├── stereo.py        # The golden model
        │   ├── stereo_base.cpp  # The baseline kernel
        │   ├── stereo.cpp       # The optimized kernel
        │   └── stereo_timing.py # Reading the co-simulation's timing
        ├── vectors/             # These are created by the build:
        ├── results/             #   generated data, reports, figures and logs.
        ├── eval/                #   None of it is edited by hand, and none of
        ├── base_proj/           #   it is submitted except the zip.
        ├── stereo_proj/
        └── submission/
```

The four files in `partial/` are not complete. Each has `TODO` comments marking
what to write:

| File | What you write |
| --- | --- |
| `stereo.py` | `shift_image()`, `disparity_map()` and `plot_disparity()` |
| `stereo_base.cpp` | The compute phase, as plain loops with pipelining off |
| `stereo.cpp` | The pragmas and the compute loop that reach one pixel per cycle |
| `stereo_timing.py` | `find_phases()` and `plot_phases()` |

**You do not need to copy anything by hand.** The first build copies each file
out of `partial/` into the lab directory and says so. Edit the copies at the top
level, not the ones in `partial/`; the build never overwrites your work once the
top-level files exist.

## Build steps

The lab uses the Waveflow [Build DAG](https://sdrangan.github.io/waveflow/docs/guide/build/),
as the [root solver lab](../rootsolve/) does. Four stages are scored, 10 points
each:

| Stage | Command | What it does |
| --- | --- | --- |
| 1. `pysim` | `python stereo_build.py --through pysim` | Grades your golden model, and writes the scene and your model's disparity map of it, for the kernels to be checked against |
| 2. `base` | `python stereo_build.py --through base` | C-simulates and synthesizes `stereo_base.cpp` |
| 3. `opt` | `python stereo_build.py --through opt` | C-simulates and synthesizes `stereo.cpp`, and grades its II, latency and size |
| &nbsp;&nbsp;&nbsp;`cosim` | `python stereo_build.py --through cosim` | Co-simulates `stereo.cpp`'s RTL and records its ports, about four minutes. Not scored itself |
| 4. `timing` | `python stereo_build.py --through timing` | Grades the co-simulation, and your reading of its timing |
| `submit` | `python stereo_build.py` | Collects the scores and builds the Gradescope zip |

None of the steps stops the build when it fails. A failed Vitis run scores zero
for the stage that ran it, says why, and is retried on the next build, so you
always get a submission zip.

Run it in `hwdesign-venv`, with Vitis HLS installed. Each stage only re-runs
when a file it depends on changes: editing `stereo.cpp` re-runs `opt`, `cosim`
and `timing`, but not `base`.

## Pages

* [Stage 1: the golden model](./python.md)
* [Stage 2: the baseline kernel](./base.md)
* [Stage 3: one pixel per cycle](./optimize.md)
* [Stage 4: co-simulation and timing](./timing.md)
* [Grading and submission](./submit.md)

----

Go to [the golden model](./python.md).
