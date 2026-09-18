---
title: The Python model
parent: Cubic Fixed Point
nav_order: 1
has_children: false
---

# Stage 1: The Python fixed-point model

Before implementing anything in SystemVerilog, you build the same arithmetic in
Python, where debugging is cheap. This model is the **golden model**: the
hardware is checked against it, case for case, and "the hardware is right" in
this lab means "the hardware agrees with your Python exactly".

That is a stronger statement than it sounds, and it shapes how you write this
file.

## Fixed point, in one paragraph

A value in `Q(wid, fbits)` is a signed integer `s`, held in a register `wid` bits
wide, standing for the real number `s / 2**fbits`. So `Q(16,8)` holds values from
-128 up to just under +128 in steps of 1/256, and `Q(16,12)` holds -8 up to just
under +8 in steps of 1/4096. Same sixteen bits; a different trade.

Everything in `cubic_model.py` — inputs, coefficients, intermediates and the
output — is `Q(wid, fbits)` with the same `wid` and `fbits`.

## Two facts about products

**A product gains fractional bits.** Multiply two `Q(wid, fbits)` integers and
the result has `2*fbits` fractional bits, so it has to be shifted back down to be
a `Q(., fbits)` value again:

```python
x2int = (xint * xint) >> fbits
```

Forget the shift and your answer is `2**fbits` times too large.

**A product also gains integer bits, and those have nowhere to go.** The shift
above fixes the binary point but not the width: the product needs roughly
`2*wid - fbits` bits and is being put back into `wid`. When it does not fit,
something has to give, and *which* thing is a design decision:

* **saturate** — clamp to the largest or smallest value the register holds. The
  answer is wrong, but wrong in the direction it was already heading.
* **truncate** — keep the low `wid` bits and discard the rest. A value slightly
  too large comes back as a large *negative* one, and the output flips sign for
  no reason a plot can explain.

This lab saturates. A saturating cubic degrades into something you can still
recognise; a wrapping one does not.

Both functions come from waveflow:

```python
from waveflow.utils.fixputils import saturate, truncate

x2int = saturate((xint * xint) >> fbits, wid)
```

`truncate` is imported for you as well. Substituting it and re-running the plot
is worth thirty seconds of your time — it is the fastest way to see why the
choice matters.

## What to write

One function in `cubic_model.py`:

| Function | Returns |
| --- | --- |
| `cubic_fixed(xint, aint, wid, fbits)` | The polynomial on `Q(wid, fbits)` integers, one output per input |

`cubic_float()`, `to_fixed()` and `to_real()` are given. The five operations, in
this order:

```
x2int  = x**2
ax1int = a1*x + a0
x3int  = x**3
ax2int = a2*x**2
y      = x3int + ax2int + ax1int
```

with a shift and a saturation at each step. Three things reliably catch people
out:

* **`a0` is not a product.** It is already `Q(wid, fbits)`, so it is added
  directly. Shifting it divides it by `2**fbits`.

* **Build `x**3` from the square you already have** — `xint * x2int` — not as
  `xint**3`. Three factors at once need a different shift, and, more importantly,
  they saturate in a different place. Your SystemVerilog builds it from the
  registered square, so your Python must too.

* **Keep the order.** Saturation is not associative: clamping after
  `x3 + ax2` and then adding `ax1` can give a different answer from clamping once
  at the end. Whatever you write here is what the hardware has to reproduce.

## Running the stage

```bash
python cubic_build.py --through pysim
```

```
Python fixed-point model: 10/10
  ✓ (3/3) Produced an output for all 200 cases
  ✓ (3/3) Every output fits in 16 bits
  ✓ (4/4) At F=8 your fixed point tracks the float
```

The second check is the one that catches a missing saturation: a `Q(16,12)` value
that does not fit in sixteen bits is not a `Q(16,12)` value, and the hardware has
no way to produce one. If your model can, your model and your hardware are
computing different things and the comparison in [stage 3](./sv.md) will say so.

The third check is scored only at `F=8`. At `F=12` a large error is the *correct*
answer — the format really is too coarse there — so grading accuracy at that
setting would penalise you for demonstrating the thing the lab set out to show.

A quick sanity check while you work: run the file directly.

```bash
python cubic_model.py
```

```
  x = 2.5   a0, a1, a2 = (1.0, -0.5, 0.25)
  float      y = 16.937500
  Q(16, 8)   y = 16.937500   (yint = 4336)
  Q(16,12)   y = 7.999756   (yint = 32767)
```

Those two numbers are the whole lab in miniature. At `Q(16,8)` the answer is
exact to four decimal places. At `Q(16,12)`, 16.94 does not fit in a format whose
largest value is just under 8, so it comes back clamped at the rail — `32767`,
the largest signed sixteen-bit integer.

----

Go to [measuring the error](./evaluate.md).
