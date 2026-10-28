---
title: "In-Class Exercise: Beat the Schedule"
parent: Timing and the Clock
nav_order: 4
has_children: false
---

# In-Class Exercise: Beat the Schedule

At 100 MHz, Vitis scheduled the quadratic in **3 states, a latency of
2 cycles**, and left more than 2.7 ns of slack in every state: over a
third of each clock period unused (see [Analyzing the
schedule](synth_sched.md)).

**Can you get Vitis to schedule it in fewer states?**

## The rules

- Change only the **body** of the function: the arithmetic in C++.
- Keep the function's name, `quad`, and its arguments, types and return
  type, so the testbench still calls it.
- It must compute the **same y** for every input. The build checks this
  before it synthesizes anything.
- No pragmas, and no changes to the clock or to `run.tcl`. The point is
  what the arithmetic itself allows.

## Work it out on paper first

Use the delays from the schedule report, rounded:

| Operation | Delay |
|---|---|
| 8-bit × 8-bit multiply | 4.5 ns |
| 16-bit × 8-bit multiply | 4.6 ns |
| an addition | about 2 ns |

and the budget of **7.3 ns** per state. Draw the block diagram of
`y = w2*x^2 + w1*x + w0`, mark when each value is ready, and find the
fewest states a schedule could use. Then try to write C++ that gets
Vitis to find it.

<details markdown="1">
<summary>Hint 1</summary>

Look at the schedule's block diagram. Which values really have to wait
for `xsq`, and which do not?

</details>

<details markdown="1">
<summary>Hint 2</summary>

Vitis adds the terms in the grouping your C++ writes. Is there another
grouping of the same sum, with the same result, that would let some of
the adding happen earlier?

</details>

## Trying it in Vitis

Don't edit `quad.cpp`: it is the reference. Work on a copy instead. From
`hwdesign/demos/timing/quad`:

```bash
(env) cp quad.cpp quad_fast.cpp                 # PowerShell: Copy-Item quad.cpp quad_fast.cpp
```

`quad_fast.cpp` is in the demo's `.gitignore`, so it stays yours and
never gets committed. Edit it, then build it with `--fast`:

```bash
(env) python quad_build.py --fast --periods 10 --through sweep_report
```

`--fast` runs the whole build on `quad_fast.cpp` instead of `quad.cpp`,
and puts everything it makes in a separate folder, `fast/`, beside the
reference build:

| Reference | Yours |
|---|---|
| `quad_proj/p10/` | `fast/quad_proj/p10/` |
| `results/` | `fast/results/` |

It takes about two minutes: C simulation, the check against the Python
model, then synthesis at 10 ns. If your C++ computes a different y,
`verify_csim` fails and nothing is synthesized: fix the arithmetic and
run it again.

Each time you change `quad_fast.cpp`, run the same command again. The
build sees that the file changed and redoes C simulation and synthesis.

## Reading your results

Compare your solution with the reference, in the same reports as before:

1. **The latency and the slack.** `fast/results/sweep.md` has your
   latency, and `fast/quad_proj/p10/syn/report/csynth.rpt` the slack, in
   the same table as
   [the reference's](synth_sched.md#for-the-whole-design).
2. **The schedule.** In
   `fast/quad_proj/p10/.autopilot/db/quad.verbose.sched.rpt`, find
   `Number of FSM states`, then which operations went into which state,
   and the `Timing violations` section for each state's delay.
3. **Draw it.** Sketch your schedule's block diagram, like the
   [reference's](synth_sched.md#the-schedule-as-a-block-diagram): the
   operations in each state, and the registers between them.

Then answer:

- How many states does your schedule have? What is the latency?
- Which state is now the slowest, and how much slack does it leave?
- Did the number of registers in the synthesis report go up or down? Why?
- Your version still has to be correct for inputs the test vector never
  tries. Is the rewrite exactly the same function for every 8-bit input,
  or only for these five cases?

To see your design on the wires, extend the build to the co-simulation
and the timing diagram, about two minutes more:

```bash
(env) python quad_build.py --fast --periods 10 --through timing_slow
```

and compare `fast/results/timing_slow.png` with the reference's
100 MHz diagram on [Synthesis at one clock](synth.md#step-4-the-timing-diagram-vcd_slow-timing_slow).

## Going further

Does your rewrite still help at a faster clock, where each multiply
already spans several states? Try 300 MHz:

```bash
(env) python quad_build.py --fast --periods 10 3.33 --force-step sweep --through sweep_report
```

`--force-step sweep` is needed because the build reruns a step when a
file changes, not when an option does.
