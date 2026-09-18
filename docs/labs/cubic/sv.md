---
title: The SystemVerilog
parent: Cubic Fixed Point
nav_order: 3
has_children: false
---

# Stage 3: The SystemVerilog

Now write the same arithmetic in hardware, and check it against the Python you
already trust.

"The same" is meant literally. This stage does not ask whether your module is
approximately right — it compares `y` against your model's output **case for
case, as integers**. An off-by-one in a shift is a few hundred disagreeing cases;
a missing saturation is a handful that appear only at `Q(16,12)`.

## The pipeline

`cubic.sv` is a three-stage pipeline. The declarations, the parameters and the
`sat` function are given; you write the two marked blocks.

**Stage 0** registers the four inputs:

```
x_s0 <= x,   a0_s0 <= a0,   a1_s0 <= a1,   a2_s0 <= a2
```

**Stage 1** computes the square and the linear term, and carries `x` and `a2`
forward for the stage that still needs them:

```
x2_s1  <= sat((x_s0 * x_s0) >>> FBITS)
ax1_s1 <= sat(((a1_s0 * x_s0) >>> FBITS) + a0_s0)
x_s1   <= x_s0
a2_s1  <= a2_s0
```

**Stage 2** is combinational:

```
x3    = sat((x_s1 * x2_s1) >>> FBITS)
ax2   = sat((a2_s1 * x2_s1) >>> FBITS)
yfull = sat(x3 + ax2 + ax1_s1)
y     = yfull[WID-1:0]
```

Note that `x3` and `ax2` are both built from the **registered, already-saturated**
`x2_s1`, not from a fresh product. Your Python does the same thing. If one of
them re-derives the square, the two will differ on exactly the cases that
saturate — which are the cases this stage weighs most heavily.

## Four things that will bite you

**Use `>>>`, not `>>`.** `>>>` is the arithmetic shift: it copies the sign bit
down. `>>` shifts zeros into the top, turning a negative value into a large
positive one. Both compile.

**Parenthesise the shift.** In SystemVerilog `>>>` binds *looser* than `+`, so

```systemverilog
a1_s0 * x_s0 >>> FBITS + a0_s0     // shifts by (FBITS + a0_s0)
```

is not what you meant, and nothing warns you. Write
`((a1_s0 * x_s0) >>> FBITS) + a0_s0`.

**`a0` is added after the shift**, not before — it is already `Q(WID,FBITS)`.

**Use `<=` in the `always_ff`, not `=`.** Every right-hand side there must read
the value a signal had *before* the clock edge. With blocking assignment,
`x_s1 <= x_s0` would pick up the `x_s0` assigned two lines earlier and the
pipeline would collapse into a single stage.

## Saturation, and when to bother

The `sat` function is given. It is the SystemVerilog spelling of waveflow's
`saturate(value, wid)`, which your Python model uses — the two have to make the
same decisions in the same places.

**You can ignore saturation at first.** At `Q(16,8)` nothing in the test set
overflows, so a module with no `sat` calls at all passes the `F=8` check
completely. That is a reasonable way to get the arithmetic and the pipeline
working before taking on the overflow behaviour, and the grading is split so that
you can bank the first part.

It does not stay free, though. See below.

## The testbench

`tb_cubic.sv` is given whole and needs no editing. It reads the cases your Python
model wrote, drives each one through the module and records what came back.

One detail worth knowing, because it explains the shape of the file: `FBITS` is a
module **parameter**, fixed at elaboration, so a plusarg cannot change it. Rather
than run the simulator twice, the testbench holds *two* instances of the DUT —
one at `Q(16,8)`, one at `Q(16,12)` — driven from the same wires. Each row of the
vector file says which setting it belongs to, and is scored against that
instance's output. The other instance computes something meaningless for that
row, and nobody looks at it.

## Running the stage

```bash
python cubic_build.py --through svsim
```

The build invokes `xvlog`, `xelab` and `xsim` for you; there is no separate
`sv_sim` command line to remember. You do need Vivado on your path — follow the
[instructions](../../support/amd/launching.md) — and on Windows, run it from a
command prompt rather than PowerShell.

```
SystemVerilog cubic: 10/10
  ✓ (6/6) SystemVerilog matches your Python at F=8
  ✓ (2/2) SystemVerilog matches your Python at F=12
  ✓ (2/2) Every case your model clamped, the hardware clamps too
```

## Why the three checks are weighted the way they are

Most of the credit sits on `F=8`, because that is where getting the shifts and
the pipeline right is demonstrated, and it is the bulk of the work.

The third check needs explaining. At `F=12` only about **fifteen cases in a
hundred** come out differently if the saturation is left out altogether. So a
design that ignores overflow entirely still matches 85% of the setting that
exists to *test* overflow — and a purely proportional score would charge it
around a third of a point out of thirty. That is not a grade, it is a rounding
error.

So the last check looks only at the cases your Python model actually clamped, and
it is **all or nothing**:

```
~ (1.7/2) SystemVerilog matches your Python at F=12 — 15 of 100 cases differ; the
          first is row 117, where x=-7478, a0=-12239, a1=-11069, a2=-9137 —
          Python says -32768 and the simulation says 18126
✗ (0/2)   Every case your model clamped, the hardware clamps too — 8 of the 8
          cases your model clamped came back differently from the simulation.
          This check is all or nothing: these are the cases the F=12 setting
          exists to test, and they are the ones a design that ignores overflow
          gets wrong
```

Note also what it does *not* let you do. The check reads the saturating cases off
your own Python output. If that output never reaches a rail, there is no subset
to check — and an empty subset scores zero rather than passing vacuously. Two
unsaturated models agreeing with each other is not evidence of anything.

## When cases disagree

A count does not tell you which product overflowed. For that, run the single-case
step: [debugging one case](./sim_sing.md).

----

Go to [debugging one case](./sim_sing.md).
