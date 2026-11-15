---
title: "In-Class: Unrolling a Dot Product"
parent: Loop Optimization
nav_order: 10
has_children: false
---

# In-Class Exercise: Unrolling a Dot Product

[Unrolling the loop](unroll.md) made the cubic four times faster, once the
arrays were partitioned. Now you do it by hand, on a smaller loop, and
measure each step: what unrolling alone buys, what partitioning adds, and
what it costs. You edit **one loop**, run **one command** after each step,
and read the table it prints.

## The problem

The dot product of two vectors of `N = 256` samples:

```
dot = a[0]*b[0] + a[1]*b[1] + ... + a[N-1]*b[N-1]
```

`a` and `b` are 16-bit integers in block RAMs with **one port each**: one
read per clock cycle. The result is a 32-bit `int`. The plain loop is:

```cpp
int sum = 0;
dot_loop: for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
    sum += a[i] * b[i];
}
return sum;
```

It already runs at II = 1: one sample per cycle. Your goal is **four
samples per cycle**, about a quarter of the cycles.

## The files

Everything is in `hwdesign/demos/unroll_inclass`:

| File | What it is |
| --- | --- |
| `dot.cpp` | **your kernel: the only file you edit.** It starts as the plain loop. |
| `dot_ref.cpp` | the plain loop again, as a reference. Do not edit it. |
| `dot.h`, `tb_dot.cpp` | the size N, and the testbench |
| `golden.py` | the Python model your kernel must match exactly |
| `run.tcl`, `dot_build.py` | the Vitis script and the build |

## Step 1: build it as it is

In `hwdesign-venv`, with Vitis installed:

```bash
(env) cd demos/unroll_inclass
(env) python dot_build.py
```

It takes about a minute: C simulation against `golden.py`, then synthesis of
your kernel beside the reference, then the two side by side:

```
                             reference    yours
---------------------------  -----------  -----------
II achieved (target)         1 (1)        1 (1)
Trip count                   256          256
Iteration latency            5            5
Total cycles, one call       261          261
Cycles per sample (N = 256)  1.02         1.02
Memory ports on a / b        1 / 1        1 / 1
DSP / FF / LUT               1 / 53 / 90  1 / 53 / 90
```

One multiplier (one DSP), one sample per cycle: 256 iterations plus a few
cycles to fill the pipeline.

## Step 2: unroll by hand

Rewrite the loop so that each iteration handles **four** samples, `i`,
`i+1`, `i+2` and `i+3`, and steps `i` by 4. Keep `PIPELINE II=1`, and leave
the interface pragmas alone. Build again. Before you look at the table,
predict:

1. How many iterations, and how many multipliers?
2. How many reads of `a` does one iteration make? How many can the memory do
   per cycle? What II does that allow?
3. So how many cycles?

Then check your answers against the table, and read the Vitis warning it
prints under it.

## Step 3: partition the arrays

Give each array four memories, one for each of the four samples an
iteration reads. Add, at the top of the function, after the interface
pragmas:

```cpp
#pragma HLS ARRAY_PARTITION variable=a type=cyclic factor=4
#pragma HLS ARRAY_PARTITION variable=b type=cyclic factor=4
```

Build again. You are done when your column shows **II = 1**, about a
quarter of the reference's cycles, and **4 / 4** memory ports.

`a` and `b` are arguments of the top function, so partitioning them
changes the **interface**: the IP now has four memory ports for each, and
whatever is connected to it has to supply four memories.

## Step 4: experiment

Each of these is a one-line change. Predict the result, then build:

- `type=block` instead of `type=cyclic`. Which memory holds `a[0]`,
  `a[1]`, `a[2]`, `a[3]` now?
- Your hand-unrolled loop replaced by the plain loop with
  `#pragma HLS UNROLL factor=4` after the `PIPELINE` pragma. Is anything
  different?
- Factor 8, for both the unroll and the partition. How many cycles, and
  how many DSPs?

## Step 5 (optional): see it in the RTL

```bash
(env) python dot_build.py --through timing
```

This adds about two minutes: an RTL co-simulation of your kernel, checked
against `golden.py` again, then a timing diagram of the memory ports of
`a` in `results/timing.png`, one address and one enable per memory. With
the arrays partitioned by 4, the four addresses step together, one per
cycle.

## Afterwards

Your rewrite has four multipliers but only one accumulator, `sum`, and it
still reaches II = 1. How do the four products reach `sum` in one cycle,
and why is that fine for an `int`?

What would change if `a`, `b` and `sum` were `float`? A float add takes
four cycles: see [Unrolling a sum](reduction.md).
