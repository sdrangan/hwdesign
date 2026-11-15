---
title: Reading the II from the Stages
parent: Loop Optimization
nav_order: 7
has_children: false
---

# Reading the II from the Stages

A float add takes several cycles. This page lists the stages of one
iteration, finds the loop-carried dependency among them, and reads the II
off it, first in the lecture's model and then in Vitis's own schedule.
The demo is set up on [the previous page](reduction.md).

## The model: a four-stage adder

The lecture models the float adder as four stages, one cycle each:

```
z1 = sum1(a, b)
z2 = sum2(z1)
z3 = sum3(z2)
z4 = sum4(z3)        // = a + b
```

It is pipelined: a new, independent add can enter `sum1` every cycle. One
add takes four cycles from its operands to its result.

## `rolled`: `sum += x[i]`

One iteration, stage by stage:

```
S0:  xi <= x[i];  i <= i + 1
S1:  z1 = sum1(xi, sum)   // reads sum
S2:  z2 = sum2(z1)
S3:  z3 = sum3(z2)
S4:  sum = sum4(z3)       // writes sum
```

`sum` is written in S4, and the next iteration reads it in its S1. So
iteration `n + 1`'s S1 must come after iteration `n`'s S4: a loop-carried
dependency from S4 back to S1. If a variable is read in stage Sr and
written in stage Sw,

```
II >= Sw - Sr + 1
```

Here II ≥ 4 − 1 + 1 = **4**. Three iterations, cycle by cycle:

| Cycle | iteration 0 | iteration 1 | iteration 2 |
|---|---|---|---|
| 0 | S0 | | |
| 1 | S1 | | |
| 2 | S2 | | |
| 3 | S3 | | |
| 4 | **S4: writes sum** | S0 | |
| 5 | | **S1: reads it** | |
| 6 | | S2 | |
| 7 | | S3 | |
| 8 | | S4 | S0 |
| 9 | | | S1 |

### What Vitis did

`results/schedule.md`, from
`proj_rolled/sol/.autopilot/db/fsum.verbose.sched.rpt`:

```text
II = 4, depth = 7 states

| Operation  | Kind  | States | Operands                        | Source      |
| x_load     | load  | 1-2    | i10 x_addr                      | fsum.cpp:20 |
| sum        | fadd  | 3-7    | i32 sum2_load, i32 bitcast_ln20 | fsum.cpp:20 |
| sum2_load  | load  | 3      | i32 sum2                        | fsum.cpp:20 |
| store_ln20 | store | 7      | i32 sum, i32 sum2               | fsum.cpp:20 |

Loop-carried: `sum2` loaded in state 3, stored in state 7: II >= 7 - 3 = 4.
```

A state is a clock cycle of the iteration, numbered from 1. Reading it
against the model:

- **`x_load`, states 1–2** is S0. A block RAM read takes two states: the
  address goes out in one, the word comes back in the next.
- **`sum`, the `fadd`, states 3–7** is S1 to S4. Vitis's adder,
  `fadd_32ns_32ns_32_5_full_dsp` in the report, has **five** states, not
  four.
- **`sum2`** is the register that holds `sum`. It is loaded in state 3,
  as the add starts, and stored in state 7, as it ends.

Why is the II still 4 with a five-state adder? Vitis lets the next
iteration load `sum2` in the **same** state this one stores it, taking the
new value straight from the adder's output. The adder's last state and the
next add's first overlap, so each add costs four cycles on the recurrence:
the model's number. In Vitis's state numbers the rule loses its + 1:

```
II >= store state - load state = 7 - 3 = 4
```

The **depth**, 7, is the iteration latency in the synthesis report: two
states of load before the five of the add. It sets how long the pipeline
takes to fill, not the II.

## `pragma`: `UNROLL factor=4`

```cpp
for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=4
    sum += x[i];
}
```

Unrolling by 4 makes four copies of the body, in order:

```cpp
sum = (((sum + x[i]) + x[i+1]) + x[i+2]) + x[i+3];
```

Vitis keeps the order: float addition is not associative, `(a + b) + c`
and `a + (b + c)` can round differently, so a compiler may not reorder
them. Stage by stage, in the model:

```
S0-S3:    x0..x3 <= x[i..i+3]   // one port: one read a cycle
S1-S4:    z = sum + x0          // reads sum
S5-S8:    z = z + x1
S9-S12:   z = z + x2
S13-S16:  sum = z + x3          // writes sum
```

`sum` is read in S1 and written in S16: II ≥ 16 − 1 + 1 = **16**. A quarter
of the iterations, each four times longer: no faster at all.

### What Vitis did

From `proj_pragma/sol/.autopilot/db/fsum.verbose.sched.rpt`:

```text
II = 16, depth = 18 states

| Operation  | Kind  | States | Operands                        |
| x_load     | load  | 1-2    | i10 x_addr                      |
| sum2_load  | load  | 2      | i32 sum2                        |
| sum_1      | fadd  | 2-6    | i32 sum2_load, i32 bitcast_ln32 |
| x_load_1   | load  | 2-3    | i10 x_addr_1                    |
| x_load_2   | load  | 3-4    | i10 x_addr_2                    |
| x_load_3   | load  | 4-5    | i10 x_addr_3                    |
| sum_2      | fadd  | 6-10   | i32 sum_1, i32 bitcast_ln32_1   |
| sum_3      | fadd  | 10-14  | i32 sum_2, i32 bitcast_ln32_2   |
| sum        | fadd  | 14-18  | i32 sum_3, i32 bitcast_ln32_3   |
| store_ln32 | store | 18     | i32 sum, i32 sum2               |

Loop-carried: `sum2` loaded in state 2, stored in state 18: II >= 18 - 2 = 16.
```

Four adds, each starting in the state the one before ends (6, 10, 14),
each needing the one before's result: a chain of four through `sum2`. The
four reads of `x` go one per state on the single port, and finish long
before the adds need them.

### Try it

- Put the rolled and pragma schedules side by side. Which operations moved,
  and which did not change at all?
- The log for `pragma` lists `HLS 200-880` violations. At which II values,
  and between which two operations?

Next: [rewriting the body](reduction_rewrite.md).
