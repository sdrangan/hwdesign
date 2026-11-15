---
title: How Many Adders?
parent: Loop Optimization
nav_order: 9
has_children: false
---

# How Many Adders?

The tree and the lanes run at the same speed, but the synthesis report
gives lanes twice the DSPs, 4 against 2, and more flip-flops, 878 against
510. Does lanes build an adder per lane? No. This page counts.

## One pipelined adder, one add per cycle

A pipelined adder accepts a new add every cycle: while one add is in
`sum2`, the next can enter `sum1`. So in a loop at initiation interval II,
one adder can do up to II adds per iteration, one entering in each cycle,
and

```
adders >= adds per iteration / II
```

| Variant | Adds per iteration | II | Adders needed |
|---|---|---|---|
| rolled | 1 | 4 | 1, busy 1 cycle in 4 |
| pragma | 4 | 16 | 1, busy 4 cycles in 16 |
| tree | 4 | 4 | 1, busy every cycle |
| lanes | 4 | 4 | 1, busy every cycle |

The count is a lower bound. One adder is enough only if the adds can be
arranged so that no two enter it in the same cycle. In a pipelined loop,
cycle `c` of one iteration and cycle `c + II` of the next are the same
moment, so the condition is: every add starts in a different **slot**,
its start cycle modulo II. That is the slot column in
`results/schedule.md`, and why the tree's later adds wait on
[the previous page](reduction_rewrite.md).

## The adder, cycle by cycle

Once the loop is full, every cycle looks like one of these four. Each
column is a stage of the lecture's four-stage adder; `a(5)` is iteration
5's add `a`. Cycles 20 to 23, from the stage listings of the previous
pages:

**rolled**: `s`, the one add, `sum + x`

| Cycle | sum1 | sum2 | sum3 | sum4 |
|---|---|---|---|---|
| 20 | | | | s(4) |
| 21 | s(5) | | | |
| 22 | | s(5) | | |
| 23 | | | s(5) | |

**tree**: `a = x0 + x1`, `b = x2 + x3`, `t = a + b`, `s = sum + t`

| Cycle | sum1 | sum2 | sum3 | sum4 |
|---|---|---|---|---|
| 20 | b(4) | s(1) | a(4) | t(2) |
| 21 | t(3) | b(4) | s(1) | a(4) |
| 22 | a(5) | t(3) | b(4) | s(1) |
| 23 | s(2) | a(5) | t(3) | b(4) |

**lanes**: `p0` to `p3`, `part[j] += x[j]`

| Cycle | sum1 | sum2 | sum3 | sum4 |
|---|---|---|---|---|
| 20 | p3(4) | p2(4) | p1(4) | p0(4) |
| 21 | p0(5) | p3(4) | p2(4) | p1(4) |
| 22 | p1(5) | p0(5) | p3(4) | p2(4) |
| 23 | p2(5) | p1(5) | p0(5) | p3(4) |

Read across a row: in every cycle each stage holds at most one add, so one
adder does it all. Read down a column: in the rolled loop the adder works
one cycle in four; in the tree and the lanes, every cycle, with adds from
several iterations in it at once.

Unrolling did not add an adder. It **filled** the one that was there.

Vitis's adder has five states, not four, and its slots differ from the
model's in detail (the tree's adds start in slots 0, 2, 3, 1; the model's
in 2, 0, 1, 3), but the property is the same: four adds, four slots, one
adder. `results/schedule.md` lists them.

## So where is lanes' second adder?

The synthesis report counts the adders. In
`proj_<variant>/sol/syn/report/fsum_csynth.rpt`, the `Instance` table has a
row per hardware unit. For `tree`:

```text
|              Instance             |             Module             | BRAM_18K| DSP|  FF | LUT | URAM|
|fadd_32ns_32ns_32_5_full_dsp_1_U1  |fadd_32ns_32ns_32_5_full_dsp_1  |        0|   2|  205|  390|    0|
```

One adder, two DSPs. For `lanes`:

```text
|              Instance             |             Module             | BRAM_18K| DSP|  FF | LUT | URAM|
|fadd_32ns_32ns_32_5_full_dsp_1_U7  |fadd_32ns_32ns_32_5_full_dsp_1  |        0|   2|  205|  390|    0|
|fadd_32ns_32ns_32_5_full_dsp_1_U8  |fadd_32ns_32ns_32_5_full_dsp_1  |        0|   2|  205|  390|    0|
|grp_fsum_Pipeline_sum_loop_fu_50   |fsum_Pipeline_sum_loop          |        0|   0|  359|  281|    0|
```

Two adders, and the loop module, `fsum_Pipeline_sum_loop`, has **no** DSPs
of its own: Vitis moved its one adder up into `fsum` and shares it with
the code after the loop. The second adder is for that code:

```cpp
sum = (part[0] + part[1]) + (part[2] + part[3]);
```

It runs once, after the loop, and is not pipelined, so Vitis schedules it
for the shortest time. From `fsum.verbose.sched.rpt`, in
`results/schedule.md`:

```text
| add  | fadd | 3-7  | i32 add7_loc_load, i32 add7_1_loc_load |
| add1 | fadd | 3-7  | i32 add7_2_loc_load, i32 add7_3_loc_load |
| sum  | fadd | 8-12 | i32 add, i32 add1                      |

Adds starting together in state 3: one adder each.
```

`part[0] + part[1]` and `part[2] + part[3]` start in the same state, so
they need two adders. That is lanes' second adder, two DSPs, used for five
cycles of the whole call. The four running sums account for part of its
extra flip-flops.

The arithmetic checks: the loop needs one adder and the line after it two
at once, and the report has two in all, 4 DSPs. Three would be 6.

The `synth` log says the same in one line per module:

```text
INFO: [RTGEN 206-100] Generating core module 'fadd_32ns_32ns_32_5_full_dsp_1': 1 instance(s).
```

for each of `rolled`, `pragma` and `tree`, and for `lanes` a line for the
loop module and one with `2 instance(s)` for `fsum`.

## What to take away

- Unrolling a loop with a loop-carried dependency **lengthens the
  recurrence**: four chained adds per iteration instead of one. On its own
  it buys nothing.
- To gain, rewrite the body so that only **one** operation is on the
  recurrence: add the unrolled samples together first, or keep a partial
  sum per lane.
- Count the hardware with **adds per iteration ÷ II**, then check that the
  adds fit in different slots. Unrolling by 4 at II = 4 needs one adder,
  fully used; it is what the rolled loop left idle.
- Integers are easier: the order of integer additions does not change the
  result, and an `int` add is short enough that a chain of several fits in
  one 10 ns cycle. The [in-class dot product](inclass_unroll.md) reaches
  II = 1 unrolled by 4 or 8, with one accumulator.

### Try it

- Unroll the tree by 8, `sum += ((x0 + x1) + (x2 + x3)) + ((x4 + x5) + (x6 + x7))`.
  How many adds per iteration? With `x` in one memory, what limits the II,
  and how many adders does the count give? With `x` partitioned cyclic
  factor 2?
- In `lanes`, write the final line as a loop, `for (j...) sum += part[j];`.
  Predict the adders, then synthesize and read the `Instance` table.
