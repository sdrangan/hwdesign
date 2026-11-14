---
title: Unrolling a Sum
parent: Loop Optimization
nav_order: 6
has_children: false
---

# Unrolling a Sum

Unrolling the cubic worked because its iterations are **independent**:
sample `i + 1` does not need anything sample `i` computes. A sum is
different. Every iteration adds to the total the last one produced: a
**loop-carried dependency**, as in unit 7. What does unrolling do to that?

The code is in `hwdesign/demos/fsum`. It sums 1024 floats, four ways:

```bash
(env) cd demos/fsum
(env) python fsum_build.py          # about 3 minutes
```

`x` is in a single-port memory, as in the other demos. A float add takes
**four cycles** at 100 MHz, pipelined: a new, independent add can start
every cycle, but an add that needs another's result waits four.

## The results

`results/fsum.md`, Vitis HLS 2025.1 on the Zynq-7020 at 100 MHz:

| Variant | Loop body | II | Trip count | Iteration latency | Cycles, 1024 samples | DSP | FF | LUT |
|---|---|---|---|---|---|---|---|---|
| rolled | `sum += x[i]` | 4 | 1024 | 7 | 4100 | 2 | 290 | 526 |
| pragma | `sum += x[i], UNROLL factor=4` | 16 | 256 | 18 | 4099 | 2 | 384 | 632 |
| tree | `sum += (x0 + x1) + (x2 + x3)` | 4 | 256 | 21 | 1042 | 2 | 510 | 682 |
| lanes | `part[j] += x[i+j], j = 0..3` | 4 | 256 | 10 | 1042 | 4 | 878 | 1175 |

The build checks every variant in C simulation first. The four add in
different orders, and a float sum in general depends on the order, so the
test values are multiples of 1/8: every partial sum is then exact, and all
four must match the Python model bit for bit.

## `rolled`: II = 4

```cpp
for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
    sum += x[i];
}
```

Unit 7's floating-point accumulation: each add waits four cycles for the
last one's `sum`. II = 4, about 4 × 1024 cycles. The log says so with HLS
200-880, a carried dependence on `sum`.

## `pragma`: unrolled by 4, and no faster

```cpp
for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=4
    sum += x[i];
}
```

A quarter of the iterations, and each takes **16** cycles: the same 4100
cycles in all. Unrolling made four copies of `sum += x[i]`, one after the
other:

```cpp
sum = (((sum + x[i]) + x[i+1]) + x[i+2]) + x[i+3];
```

That is a chain of four adds through `sum`, 4 × 4 = 16 cycles before the
next iteration can use it. A compiler may not reorder float additions,
since `(a + b) + c` and `a + (b + c)` can round differently, so Vitis keeps
the chain exactly as written.

## `tree`: one add on the recurrence

```cpp
for (int i = 0; i < N; i += 4) {
#pragma HLS PIPELINE II=1
    sum += (x[i] + x[i+1]) + (x[i+2] + x[i+3]);
}
```

The same four samples, added **among themselves first**, then to `sum`.
The two inner adds and the one that joins them do not depend on `sum`, so
they can run ahead; only the last add is on the recurrence. II = 4 again,
but now for four samples per iteration: **1042 cycles**, four times faster.

The four reads of `x` share one port, but they fit in the four cycles the
recurrence takes anyway, so `x` does not need partitioning here. And one
float adder (2 DSPs) does all three adds of an iteration, one after
another, in its four cycles.

This changes the order of the additions, and so, for general data, the
rounding: the answer can differ from the rolled loop's in the last bits.
That is the programmer's decision to make, which is why the tool will not.

## `lanes`: four partial sums

```cpp
float part[4] = {0, 0, 0, 0};
#pragma HLS ARRAY_PARTITION variable=part type=complete
for (int i = 0; i < N; i += 4) {
#pragma HLS PIPELINE II=1
    for (int j = 0; j < 4; j++)
        part[j] += x[i + j];
}
sum = (part[0] + part[1]) + (part[2] + part[3]);
```

Four running sums, one per lane of the unrolled iteration. Each is still a
four-cycle recurrence, so II = 4 and the same 1042 cycles as the tree, for
twice the DSPs. It is unit 7's interleaved partial sums, written as an
unrolled loop.

## What to take away

- Unrolling a loop with a loop-carried dependency **lengthens the
  recurrence**: four chained adds per iteration instead of one. On its own
  it buys nothing.
- To gain, rewrite the body so that only **one** operation is on the
  recurrence: add the unrolled samples together first, or keep a partial
  sum per lane.
- Integers are easier: the order of integer additions does not change the
  result, and an `int` add is short enough that a chain of several fits in
  one 10 ns cycle. The [in-class dot product](inclass_unroll.md) reaches
  II = 1 unrolled by 4 or 8, with one accumulator.
