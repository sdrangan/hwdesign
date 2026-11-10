---
title: In-Class Exercise
parent: Loop Optimization
nav_order: 4
has_children: false
---

# In-Class Exercise: One Read per Iteration

You have seen a loop reach II = 1. This one asks for II = 1 and does not get
it, and your job is to find out why and fix it. You edit **one loop**, run
**one command**, and read the synthesis report. Everything else, the
testbench, the Vitis script and the build, is written for you.

## The problem

For `i = 0, ..., N-1`, with `N = 256` and `x[-1] = 0`:

```
y[i] = x[i]^2 + x[i-1]^2
```

`x` and `y` are float arrays in block RAMs with **one port each**: one read
or one write per clock cycle, as in [the kernel](kernel.md). The obvious
loop is:

```cpp
sample_loop: for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
    float prev = (i == 0) ? 0.0f : x[i - 1];
    y[i] = x[i] * x[i] + prev * prev;
}
```

## The files

Everything is in `hwdesign/demos/loopopt_inclass`:

| File | What it is |
| --- | --- |
| `sqsum.cpp` | **your kernel: the only file you edit.** It starts as the obvious loop. |
| `sqsum_ref.cpp` | the obvious loop again, as a reference. Do not edit it. |
| `sqsum.h`, `tb_sqsum.cpp` | the size N, and the testbench |
| `golden.py` | the Python model your kernel must match, bit for bit |
| `run.tcl`, `sqsum_build.py` | the Vitis script and the build |

## Step 1: build it as it is

In `hwdesign-venv`, with Vitis installed:

```bash
(env) cd demos/loopopt_inclass
(env) python sqsum_build.py
```

It takes under a minute. The build runs your kernel in C simulation and
checks it against `golden.py`, synthesizes it beside the reference, and
prints the two side by side:

```
                        reference       yours
----------------------  --------------  --------------
II achieved (target)    2 (1)           2 (1)
Iteration latency       13              13
Trip count              256             256
Total cycles, one call  524             524
DSP / FF / LUT          5 / 677 / 1026  5 / 677 / 1026

Vitis warnings about the II, yours:
  - The II Violation in module 'sqsum' (loop 'sample_loop'): Unable to schedule
    'load' operation 32 bit ('x_load_1', sqsum.cpp:22) on array 'x' due to
    limited memory ports (II = 1). ...
```

Both loops asked for II = 1 and got 2: 524 cycles for 256 outputs. Open the
synthesis report it names, `proj_yours/sol/syn/report/sqsum_csynth.rpt`, and
find the same numbers in its **Loop** table.

Before you change anything, answer:

1. How many times does one iteration read `x`? How many reads can the
   memory do per cycle?
2. What II does that allow?
3. Each `x[k]` is read by two iterations. Which ones?

## Step 2: rewrite the loop

Rewrite the loop in `sqsum.cpp`, between the `edit from here` and `to here`
markers, so that it reaches **II = 1**. The rules:

- Keep the interface pragmas: `x` and `y` stay single-port memories.
  Partitioning `x` would add ports, which is unit 8's subject; here, find a
  way to need fewer.
- `y` must still match `golden.py` exactly. The build checks this before it
  synthesizes, and stops if it does not.

Then run the same command again. Only the steps your edit affects run
again. You are done when your column shows II = 1, about half the cycles,
and no II warning.

A hint, if you need one: a value one iteration computes can be kept in a
plain variable for the next iteration to use. Vitis keeps it in a register.

## Step 3 (optional): see it in the RTL

```bash
(env) python sqsum_build.py --through timing
```

This adds about two minutes: an RTL co-simulation of your kernel, checked
against `golden.py` again, then a timing diagram of its memory ports from
the start of the call, in `results/timing.png`. With II = 1, `x_address0`
steps through one address every cycle, and once the pipeline is full,
`y_we0` stays high and `y_address0` steps one per cycle too. Run it before
your rewrite instead, and you will see every `x` address **twice in a
row**, `0, 0, 1, 1, 2, 2, ...`: each `x[k]` read once as `x[i]` and again,
in the next cycle, as `x[i-1]`. `y_we0` is high only every other cycle.

## Afterwards

Compare the resources of the two columns. The reference squares two numbers
per iteration but did not use more multipliers. Why not?

Your loop also carries a value from one iteration to the next, as
`sum += x[i]` does in the floating-point accumulation problem (unit 7 in
the LLM grader), but yours still reaches II = 1. What is different?
