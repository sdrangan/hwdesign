---
title: The baseline kernel
parent: Stereo Depth
nav_order: 2
has_children: false
---

# Stage 2: The baseline kernel

The first kernel is the specification written in C++, the obvious way, with
nothing optimized. It is the reference point: the next stage makes it about 470
times faster, and you need the "before" to measure that.

## `stereo_base.cpp`

The load and store phases are written for you. Read them first: they show the
stream interface. `pix_in.read()` returns one word, and its `data` field holds
the left pixel in bits 7:0 and the right pixel in bits 15:8.

You write the **compute** phase: for every pixel, the disparity the
specification defines. Loop over `y` and `x`, and for an interior pixel over
`d`, and for each `d` over the 5x5 window, reading `L` and `R` directly:

```cpp
comp_y: for (int y = 0; y < IMG_H; y++) {
    comp_x: for (int x = 0; x < IMG_W; x++) {
        ...
        disp_loop: for (int d = 0; d < NDISP; d++) {
            // the SAD of the window at d, then keep the best
        }
        D[y][x] = ...;
    }
}
```

`absdiff()` is given, and so is the type `sad_t`, wide enough for 25 differences
of up to 255. `interior(y, x)` in `stereo.h` says whether a pixel is in the
interior.

**Every loop gets `#pragma HLS PIPELINE off`.** Vitis pipelines innermost loops
on its own unless told not to, and this version is meant to do one operation at
a time. The stage checks that no loop in the report is pipelined.

## Running the stage

```bash
python stereo_build.py --through base
```

It runs `stereo_base.cpp` in C simulation on the lab's scene, through
`tb_stereo.cpp`, and compares the disparities it writes with your model's,
pixel by pixel. Then it synthesizes the kernel, and copies the report to
`results/base_csynth.rpt`.

Read the report's **Latency** and the loop table. For the reference solution:

```text
|- comp_y   |  24768|  17141952|  258 ~ 178562|  -|  -|   96|  no|
 + comp_x   |    256|    178560|      2 ~ 1395|  -|  -|  128|  no|
```

and about **17.2 million cycles** for one call: 0.17 s at 100 MHz, nearly 1,400
cycles for each interior pixel. Before you go on, account for that number from
the loops: how many absolute differences does one pixel need, and how many
cycles does each take when nothing overlaps? The resources are tiny, under a
thousand LUTs, because one adder and one comparator do all the work, one after
another.

----

Go to [one pixel per cycle](./optimize.md).
