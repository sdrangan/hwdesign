---
title: Measuring the error
parent: Cubic Fixed Point
nav_order: 2
has_children: false
---

# Stage 2: Measuring what the format cost

## Why this stage exists

You now have two implementations of the same polynomial: one in `float64`, one on
sixteen-bit integers. How much worse is the second one?

"It looked right on a plot" is not an answer, and neither is "it compiled". The
way you answer it is to **measure** the difference across many inputs — in
Python, where measuring is cheap, and *before* you write a line of SystemVerilog.

That ordering is the point of this stage, and it is not the order most people
reach for. The temptation is to get the RTL going and debug it there. But a width
you got wrong here costs you an edit; the same width found after you have a
pipeline costs you an afternoon of staring at waveforms, and you will spend most
of it wondering whether the bug is in the hardware when it was in the format all
along.

So: a golden model is not just something to compare hardware against. It is where
you find out whether the design is worth building.

## The measurement

A **relative** mean-squared error:

```
rel_mse = mean((y - yfix)**2) / mean(y**2)
```

Relative, because the absolute error means nothing on its own. An error of 0.01
is negligible when `y` is around 50 and catastrophic when `y` is around 0.02, and
only the ratio tells the two apart. It also makes the two settings comparable,
which is the whole reason for computing it twice.

## What to write

Three functions in `cubic_eval.py`:

| Function | Returns |
| --- | --- |
| `rel_mse(y, yfix)` | The relative MSE, as a plain `float` |
| `mse_by_fbits(fbits, y, yfix)` | `(widths, mse)` — the distinct `fbits` in increasing order, and the relative MSE of the cases at each |
| `plot_fixed_vs_float(xplot, yplot, curves, out_path)` | Saves the figure below to `out_path` |

The cases at both settings arrive interleaved in one long array, with `fbits`
saying which setting each one came from. `mse_by_fbits` splits them: an MSE taken
over both settings together would average a good result with a bad one and
describe neither.

Call `rel_mse` from inside `mse_by_fbits` rather than writing the formula a
second time. If it is wrong, you want it wrong in one place.

## What you should find

| Setting | Relative MSE | Why |
| --- | --- | --- |
| `Q(16,8)` | about `7e-6` | Pure quantization — a fraction of a unit in the last place |
| `Q(16,12)` | about `8e-2` | `x**3` no longer fits; the saturation clamps it |

Four orders of magnitude, from moving a binary point and changing nothing else.

If your `F=8` number is much larger than `7e-6`, nothing should be saturating at
that setting — so the cause is a shift or a width, not the format. If your `F=12`
number is much *smaller* than `8e-2`, your model is probably not saturating at
all, which will cost you in [stage 3](./sv.md).

## The figure

`plot_fixed_vs_float` draws one subplot per setting, each showing the same
floating-point curve with that setting's fixed-point curve over it:

![Two subplots of the same cubic. At W=16 F=8 the fixed-point curve and the floating-point curve are indistinguishable. At W=16 F=12 the fixed-point curve is flat outside roughly -1.5 < x < 3 where the value saturated, while the float curve continues.](./images/cubic_fixp.png)

Draw the floating-point curve **dashed**, so the two can be told apart where they
coincide — which at `F=8` is everywhere. The flat shoulders in the right-hand
subplot are the saturation: outside a narrow window the cubic term has run out of
register and the output sits at the rail.

One practical note: pass `squeeze=False` to `plt.subplots` and index the axes as
`axes[0]`. With a single setting, `subplots` otherwise hands back a bare axis
rather than an array, and your loop breaks on a case you are unlikely to test.

## Running the stage

```bash
python cubic_build.py --through pyeval
```

```
Measuring the quantization error: 10/10
  ✓ (3/3) Your rel_mse is correct
  ✓ (3/3) Your mse_by_fbits is correct
  ✓ (2/2) F=8 approximates the float and F=12 saturates
  ✓ (2/2) You produced a float-against-fixed figure
```

Notice what the first two checks and the third are doing. The first two ask
**can you measure it** — your numbers against the true ones. The third asks
**did the format do what the theory said** — and it is scored from the true
values, not from yours, so a broken measurement costs you the measurement marks
without also condemning a model that was fine.

A correct measurement of a model that never saturates earns the first two and not
the third. That distinction is the thing this stage exists to teach.

Only the *existence* of the figure is scored. Judging a plot mechanically is a
poor trade — the checks that could be automated are the ones you can satisfy
without drawing anything worth looking at — so the file goes into your submission
instead, where a person can read it.

----

Go to [the SystemVerilog](./sv.md).
