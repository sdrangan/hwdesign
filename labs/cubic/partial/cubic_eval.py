"""cubic_eval — measuring what the fixed-point version cost you.

You have two implementations of the same polynomial: one in float64, one on
16-bit integers.  How much worse is the second one?

"It looked right on a plot" is not an answer, and neither is "it compiled".  You
answer it by *measuring* the difference across many inputs, in Python, where
measuring is cheap — and you do it **before** you write a line of SystemVerilog.
A width you got wrong here costs you an edit.  The same width found after you
have a pipeline costs you an afternoon of staring at waveforms.

That is the habit worth taking away from this lab: a golden model is not just
something to compare hardware against, it is where you find out whether the
design is worth building at all.

The measurement is a **relative** mean-squared error,

    rel_mse = mean((y - yfix)**2) / mean(y**2)

relative because the absolute error means nothing on its own.  An error of 0.01
is negligible when ``y`` is around 50 and catastrophic when ``y`` is around
0.02, and only the ratio tells the two apart.  It also makes the two settings
comparable, which is the point of computing it twice.

What you should find, and what the figure should show:

**At 16 bits with 8 fractional**, the fixed-point curve lies on the floating
point one.  The error is pure quantization — a fraction of a unit in the last
place, and ``rel_mse`` lands around 7e-6.

**At 16 bits with 12 fractional**, four integer bits have been traded away for
fractional ones.  ``x**3`` no longer fits, the saturation clamps it, and the
curve flattens into a plateau at the top and bottom of the range.  ``rel_mse``
is around 0.08 — four orders of magnitude worse, from moving a binary point and
changing nothing else.

More fractional bits is not better.  That is the whole lesson, and this file is
where you demonstrate it to yourself rather than being told.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray


def rel_mse(y: NDArray[np.float64], yfix: NDArray[np.float64]) -> float:
    """Return the relative mean-squared error of *yfix* against *y*.

        mean((y - yfix)**2) / mean(y**2)

    See the module docstring for why it is relative rather than absolute.

    Parameters
    ----------
    y : NDArray[np.float64]
        The floating-point reference, from ``cubic_float``.
    yfix : NDArray[np.float64]
        The fixed-point result converted back to real values, from
        ``cubic_fixed`` and then ``to_real``.

    Returns
    -------
    float
        A plain float.  Zero means the two agree exactly.
    """
    # TODO:  Compute the relative MSE, and delete the `return 0.0` below.
    #
    #     return mean((y - yfix)**2) / mean(y**2)
    #
    # `np.mean` does both averages.  Return a plain `float`, not a 0-d numpy
    # array -- the grader compares it against a float and prints it.
    return 0.0


def mse_by_fbits(fbits: NDArray[np.int64], y: NDArray[np.float64],
                 yfix: NDArray[np.float64]) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    """Return ``(widths, mse)`` — the relative MSE at each distinct ``fbits``.

    The cases at both settings arrive interleaved in one long array, with
    ``fbits`` saying which setting each one came from.  Split them, and measure
    each group separately: an MSE over the two settings together would average a
    good result with a bad one and describe neither.

    Parameters
    ----------
    fbits : NDArray[np.int64]
        The fractional width each case was computed at, one entry per case.
    y : NDArray[np.float64]
        The floating-point reference, one entry per case.
    yfix : NDArray[np.float64]
        The fixed-point result as a real value, one entry per case.

    Returns
    -------
    tuple[NDArray[np.int64], NDArray[np.float64]]
        The distinct ``fbits`` values **in increasing order**, and the relative
        MSE of the cases at each one.  Both arrays have one entry per distinct
        width.
    """
    fbits = np.asarray(fbits, dtype=np.int64)
    y = np.asarray(y, dtype=np.float64)
    yfix = np.asarray(yfix, dtype=np.float64)

    # TODO:  Measure each setting separately, then delete the `return` below.
    #
    #     widths = ...     the distinct fbits values, in increasing order
    #     mse    = ...     rel_mse of the cases at each width
    #     return widths, mse
    #
    # `np.unique(fbits)` gives you the distinct values, already sorted.  For
    # each one, `fbits == w` is a boolean mask selecting that setting's cases,
    # so `y[fbits == w]` and `yfix[fbits == w]` are the arrays to hand to your
    # own `rel_mse`.
    #
    # Call `rel_mse` rather than writing the formula a second time.  If it is
    # wrong you want it wrong in one place.
    widths = np.unique(fbits)
    return widths, np.zeros(len(widths), dtype=np.float64)


def plot_fixed_vs_float(xplot: NDArray[np.float64], yplot: NDArray[np.float64],
                        curves: dict[int, NDArray[np.float64]],
                        out_path: Path) -> Path:
    """Draw the fixed-point curves against the floating-point one, and save it.

    One subplot per setting, each showing the same floating-point curve with
    that setting's fixed-point curve over it.  Side by side, the two subplots
    are the argument of this lab in one picture: at 8 fractional bits the curves
    are indistinguishable, and at 12 the fixed-point one has flat shoulders
    where the cubic term saturated.

    The target is on the lab's `Measuring the error` page.

    Parameters
    ----------
    xplot : NDArray[np.float64]
        The x values, shared by every curve.
    yplot : NDArray[np.float64]
        The floating-point reference curve.
    curves : dict[int, NDArray[np.float64]]
        ``fbits -> the fixed-point curve at that setting``, as real values.
    out_path : Path
        Where to write the PNG.
    """
    # The backend is set up for you; writing to a file rather than opening a
    # window is what `Agg` is for.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    settings = sorted(curves)
    ncurve = len(settings)

    # TODO:  Draw the comparison and save it to `out_path`.
    #
    # `plt.subplots(1, ncurve)` gives you a figure and a row of axes -- one per
    # setting.  On each axis, plot two things: the floating-point curve
    # (`xplot`, `yplot`) and that setting's fixed-point curve
    # (`xplot`, `curves[fbits]`).  Draw the float one dashed so the two can be
    # told apart where they coincide, which at F=8 is everywhere.
    #
    # Label both axes, title each subplot with its W and F, and add a legend.
    # Compare what you get against the figure on the lab page: at F=12 you
    # should see flat shoulders at the top and bottom of the range, which is
    # the saturation.
    #
    # Pass `squeeze=False` to subplots and index the axes as `axes[0]`.  With
    # one setting, subplots otherwise hands back a bare axis rather than an
    # array, and the loop below breaks on a case you are unlikely to test.
    #
    # Finish with `savefig(out_path)`.  The file is part of what you submit,
    # and the lab checks that you produced it.
    return out_path
