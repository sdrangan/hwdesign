---
title: Debugging one case
parent: Cubic Fixed Point
nav_order: 4
has_children: false
---

# Debugging one case

`svsim` tells you *how many* cases disagree. It cannot tell you which product
overflowed. For that there is a fourth build step:

```bash
python cubic_build.py --through svsing
```

It runs one case — one you choose — through `tb_cubic_sing.sv` and prints every
pipeline register on every clock.

**Nothing here is graded and nothing here is submitted.** It exists so that the
answer to "why is case 117 wrong" is a table rather than a guess. It is a build
step like the others because everything in this lab is, and because the DAG then
knows to re-run it when you edit `cubic.sv` — but no step in the `submit` chain
depends on it, so a plain `python cubic_build.py` skips it entirely.

You can run it at any point, including before `svsim` has ever passed.

## Setting up the case

At the top of `tb_cubic_sing.sv`:

```systemverilog
localparam real xr_test  =  2.5;
localparam real a0r_test =  1.0;
localparam real a1r_test = -0.5;
localparam real a2r_test =  0.25;
```

Change these to the case you want to look at. As given, nothing saturates at
`FBITS=8` — a good place to start. To see the saturating behaviour, change
`FBITS` to 12 a few lines above, or push `x` out towards 2.0.

When `svsim` reports a disagreement it prints the offending inputs as *integers*:

```
the first is row 117, where x=-7478, a0=-12239, a1=-11069, a2=-9137
```

Those are `Q(16,12)` values, so divide each by `2**12 = 4096` to get the real
numbers to type in above — and set `FBITS` to 12 to match.

## Completing `expected_y()`

This is the one thing you write in this file, and it is worth understanding why
it is not simply handed to you.

The real-valued answer is **not** the right target. Your module truncates on every
shift and clamps on every saturation, so its output differs from the exact value
by a little at `F=8` and by a lot at `F=12`. Comparing against the exact answer
would report a failure on a module that is working perfectly.

So `expected_y()` asks you to state, in integers, what you believe your own
design computes:

```systemverilog
x2  = sat_i((longint'(x_test) * x_test) >>> FBITS);
ax1 = ...
```

Use exactly the operations your `cubic.sv` uses — the same shifts, the same
`sat_i` calls, in the same order. If it then disagrees with the DUT, one of the
two is where your bug is, and the register trace tells you which.

Cast one operand of each product to `longint` so the multiply happens in 64 bits.
`x_test` and friends are `int`, and two of them multiplied can overflow 32 bits
before the shift brings the value back down.

`sat_i` is given.

## Reading the output

```
=== Cubic Fixed Point: one case ===
Parameters: WID=16, FBITS=8

Test inputs:
  x  =    640  (2.5000)
  a0 =    256  (1.0000)
  a1 =   -128  (-0.5000)
  a2 =     64  (0.2500)

Exact real answer:      16.9375
Your expected_y():        4336  (16.9375)

=== Pipeline registers, cycle by cycle ===
Cycle |  x_s0 |  x2_s1 | ax1_s1 |  x_s1 |      y
------|-------|--------|--------|-------|-------
    0 |     0 |      0 |      0 |     0 |      0
    1 |     0 |      0 |      0 |     0 |      0
    2 |   640 |      0 |      0 |     0 |      0
    3 |   640 |   1600 |    -64 |   640 |   4336
    4 |   640 |   1600 |    -64 |   640 |   4336
    ...

TEST PASSED: y = 4336, which is what expected_y() said.
```

The trace is the point. You can see the value move through the pipeline one stage
per clock: `x_s0` at cycle 2, then `x2_s1` and `ax1_s1` at cycle 3, and `y`
combinationally from there. It settles after two clocks and holds, because the
inputs are held.

**Check `x2_s1` first.** Every later term is built from it, so a wrong square
makes `x3`, `ax2` and `y` all wrong at once and the other three columns tell you
nothing you did not already know. Here `x = 2.5` is `640`, and
`640 * 640 >> 8 = 1600`, which is `6.25` — correct.

## Running it in the Vivado GUI

The step leaves its simulation in `sim/sing/`, so you can open the waveform
database there if you would rather look at signals than at a table. If you are on
the [NYU server](../../support/nyuremote/), follow the
[uv instructions](../../support/nyuremote/python.md) and run the step through
`uv`:

```bash
uv run python cubic_build.py --through svsing
```

----

Go to [grading and submission](./submit.md).
