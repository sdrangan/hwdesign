---
title: Rewriting the Body
parent: Loop Optimization
nav_order: 8
has_children: false
---

# Rewriting the Body

[The previous page](reduction_stages.md) found the problem: unrolled by
the pragma, the four adds form a chain through `sum`, 16 stages from the
read of `sum` to its write. To gain, the body must be rewritten so that
**one** add is on the recurrence. Two ways to do it, both four times
faster than the rolled loop.

Both change the order of the additions, and so, for general data, the
rounding: the answer can differ from the rolled loop's in the last bits.
That is the programmer's decision, which is why the tool will not make it.

## `tree`: add the samples together first

```cpp
for (int i = 0; i < N; i += 4) {
#pragma HLS PIPELINE II=1
    sum += (x[i] + x[i+1]) + (x[i+2] + x[i+3]);
}
```

The three adds inside the brackets do not touch `sum`, so they can run
ahead; only the last add is on the recurrence. In the model, with one
adder doing all four adds:

```
S0-S3:    x0..x3 <= x[i..i+3]   // one port: one read a cycle
S2-S5:    a = x0 + x1
S4-S7:    b = x2 + x3
S9-S12:   t = a + b             // a ready after S5, b after S7
S15-S18:  sum = sum + t         // reads, writes sum
```

`sum` is read in S15 and written in S18: II ≥ 18 − 15 + 1 = **4**, the same
II as the rolled loop, but now each iteration adds **four** samples.

Why does `t` start in S9, not S8 when `b` is ready, and the last add in
S15, not S13? Because each add must enter the adder in a **different
cycle modulo 4**. At II = 4 a new iteration starts every 4 cycles, so an
add that enters in S8 would meet the next iteration's `b`, which enters in
its own S4, four cycles later, at the same moment. `a` is in slot 2, `b`
in slot 0, `t` in slot 1, the last add in slot 3. One adder, four slots,
four adds: [How many adders?](reduction_adders.md) draws it.

The four reads of `x` share one port, so they need four cycles: II ≥ 4
from the port, too. They fit in the four cycles the recurrence takes
anyway, so `x` does not need partitioning.

### What Vitis did

From `proj_tree/sol/.autopilot/db/fsum.verbose.sched.rpt`, via
`results/schedule.md`:

```text
II = 4, depth = 21 states

| Operation  | Kind  | States | Slot | Operands                             |
| x_load     | load  | 1-2    |      | i10 x_addr                           |
| x_load_1   | load  | 2-3    |      | i10 x_addr_1                         |
| x_load_2   | load  | 3-4    |      | i10 x_addr_2                         |
| add3       | fadd  | 4-8    | 0    | i32 bitcast_ln42, i32 bitcast_ln42_1 |
| x_load_3   | load  | 4-5    |      | i10 x_addr_3                         |
| add        | fadd  | 6-10   | 2    | i32 bitcast_ln42_2, i32 bitcast_ln42_3 |
| add1       | fadd  | 11-15  | 3    | i32 add3, i32 add                    |
| sum        | fadd  | 17-21  | 1    | i32 sum2_load, i32 add1              |
| sum2_load  | load  | 17     |      | i32 sum2                             |
| store_ln42 | store | 21     |      | i32 sum, i32 sum2                    |

4 adds start in states 4, 6, 11, 17: slots 0, 2, 3, 1 mod 4, 4 different.
Loop-carried: `sum2` loaded in state 17, stored in state 21: II >= 21 - 17 = 4.
```

The `bitcast`s are the four words of `x` as floats. `add3` is `x0 + x1`,
`add` is `x2 + x3`, `add1` joins them, and `sum` is the add on the
recurrence.

Vitis made the same choice as the model. `add1` could start in state 10,
when `add` finishes, but slot 10 mod 4 = 2 is `add`'s: it waits for state
11. The last add could start in 15, but slots 3 (state 15) and 0 (state 16)
are taken: it waits for 17. That waiting is why the depth is 21, against
7 for the rolled loop, and costs only the pipeline's fill: 1042 cycles,
against 4100.

## `lanes`: four running sums

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

Four running sums, one per sample of the unrolled iteration: unit 7's
partial sums, written as an unrolled loop. `part` is partitioned into four
registers, so all four can be read and written in the same iteration. In
the model:

```
S0-S3:  x0..x3 <= x[i..i+3]
S1-S4:  part[0] = part[0] + x0
S2-S5:  part[1] = part[1] + x1
S3-S6:  part[2] = part[2] + x2
S4-S7:  part[3] = part[3] + x3
```

Four recurrences, one per lane, each read in S(1 + j) and written in
S(4 + j): II ≥ 4 − 1 + 1 = **4**, as for the tree.

### What Vitis did

Here Vitis makes the loop a module of its own, so its schedule is
`proj_lanes/sol/.autopilot/db/fsum_Pipeline_sum_loop.verbose.sched.rpt`:

```text
II = 4, depth = 10 states

| Operation     | Kind  | States | Slot | Operands                          |
| x_load        | load  | 1-2    |      | i10 x_addr                        |
| x_load_1      | load  | 2-3    |      | i10 x_addr_1                      |
| add7          | fadd  | 3-7    | 3    | i32 add739_load, i32 bitcast_ln54 |
| add739_load   | load  | 3      |      | i32 add739                        |
| ...
| add7_3        | fadd  | 6-10   | 2    | i32 add7_393_load, i32 bitcast_ln54_3 |
| store_ln54    | store | 7      |      | i32 add7, i32 add739              |
| ...

4 adds start in states 3, 4, 5, 6: slots 3, 0, 1, 2 mod 4, 4 different.
Loop-carried: `add739` loaded in state 3, stored in state 7: II >= 7 - 3 = 4.
(and the same for add7_157, add7_275 and add7_393)
```

`add739`, `add7_157`, `add7_275` and `add7_393` are Vitis's names for
`part[0]` to `part[3]`. Each lane's add starts as soon as its word of `x`
arrives, one state apart, and each lands in its own slot without waiting:
depth 10.

The final line, `sum = (part[0] + part[1]) + (part[2] + part[3])`, runs once,
after the loop, in `fsum`'s own schedule
(`proj_lanes/sol/.autopilot/db/fsum.verbose.sched.rpt`). It matters for the
hardware, which is the next page.

## The two side by side

| | tree | lanes |
|---|---|---|
| adds per iteration | 4: three in the tree, one on `sum` | 4: one per lane |
| recurrences | one, `sum` | four, one per `part[j]` |
| II | 4 | 4 |
| depth | 21 | 10 |
| cycles, 1024 samples | 1042 | 1042 |
| DSP, FF | 2, 510 | 4, 878 |

The same speed. Lanes costs more: [how many adders?](reduction_adders.md)
says why.
