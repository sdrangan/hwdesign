"""subc_eval — measuring how good your divider actually is.

You have a divider that returns a number.  Is it right?

"It compiles" is not an answer, and neither is "it looked right on one
example".  You answer it by *measuring* the approximation error across many
cases, in Python, where measuring is cheap — and you do it **before** you write
a line of SystemVerilog.  A flaw you find here costs you an edit.  The same
flaw found after you have a state machine costs you a day of staring at
waveforms.

That is the habit worth taking away from this lab: a golden model is not just
something to compare hardware against, it is where you find out whether the
design is worth building.

The theory promises two things, and they are different claims:

**The error is bounded** — ``a/b - qhat`` is less than ``2**-nbits``, so every
extra bit halves the worst case.  Plotted against ``nbits`` on a log axis, that
is a straight line, and seeing it come out straight is how you know the
algorithm is converging at the rate it should.

**The error is one-sided** — ``qhat`` never exceeds ``a/b``.  A divider that
rounds to nearest would have a smaller *absolute* error and would still be
wrong, because the rest of the design is entitled to assume the quotient is an
under-estimate.  A measurement that throws the sign away cannot tell the two
apart, which is why :func:`quant_error` returns a signed value.

The definitions, and what the finished figure should look like, are on the
lab's `Measuring the error` page.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


def quant_error(a: np.ndarray, b: np.ndarray, z: np.ndarray,
                nbits: np.ndarray) -> np.ndarray:
    """Return the **signed** approximation error ``a/b - z/2**nbits``, case by case.

    Signed, not absolute: the sign is what tells a divider that under-estimates
    (correct) from one that overshoots (wrong).  See the module docstring.

    Parameters
    ----------
    a, b : np.ndarray
        The dividends and divisors, one per case.
    z : np.ndarray
        The quotient numerators your divider returned.
    nbits : np.ndarray
        The fractional width asked for in each case.  It varies from case to
        case, so this has to be an array, not a constant.

    Returns
    -------
    np.ndarray
        One float per case.  For a correct divider every value is in
        ``[0, 2**-nbits)``.
    """
    # TODO:  Compute the signed error, and delete the `return` below.
    #
    #     return a/b - z/(2**nbits)
    #
    # Two things to be careful about:
    #
    #   * These are integer arrays.  Convert to float before dividing, or numpy
    #     does integer division and hands you zeros.
    #
    #   * `nbits` is an array, one entry per case, not a single number.  Write
    #     the expression elementwise and numpy will pair each z with its own
    #     nbits.
    return np.zeros(len(a), dtype=np.float64)


def max_error_by_nbits(nbits: np.ndarray,
                       err: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(widths, worst)`` — the largest absolute error at each ``nbits``.

    This is the summary the figure is drawn from.  The worst case is the right
    statistic here, not the average: the bound the theory gives you is a promise
    about *every* case, so a single case that breaks it matters and an average
    would hide it.

    Parameters
    ----------
    nbits : np.ndarray
        The fractional width of each case.
    err : np.ndarray
        The signed errors from :func:`quant_error`.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        The distinct widths **in increasing order**, and the largest absolute
        error seen at each one.  Both arrays have one entry per distinct width.
    """
    # TODO:  Group the errors by nbits and take the worst of each, then delete
    # the `return` below.
    #
    #     widths = ...        the distinct nbits values, in increasing order
    #     worst  = ...        the largest |err| among the cases at each width
    #     return widths, worst
    #
    # `np.unique(nbits)` gives you the distinct values, already sorted.  For
    # each one, `nbits == w` is a boolean mask selecting that width's cases —
    # `err[nbits == w]` is their errors, and you want the largest absolute
    # value among them.
    #
    # Take the absolute value here.  The sign is checked separately; this
    # function is about magnitude.
    widths = np.unique(nbits)
    return widths, np.zeros(len(widths), dtype=np.float64)


def plot_error(widths: np.ndarray, worst: np.ndarray, out_path: Path) -> Path:
    """Draw worst-case error against ``nbits``, and save it to *out_path*.

    Plot the values *you* measured rather than recomputing them: the picture is
    then a picture of your own :func:`max_error_by_nbits`, and a mistake in it
    is something you can see rather than only something you are told.

    The target is on the lab's `Measuring the error` page.

    Parameters
    ----------
    widths : np.ndarray
        The distinct ``nbits`` values, increasing.
    worst : np.ndarray
        The worst absolute error at each width.
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

    widths = np.asarray(widths)
    worst = np.asarray(worst, dtype=np.float64)

    # TODO:  Draw the figure and save it to `out_path`.
    #
    # `plt.subplots()` gives you a figure and an axis.  On the axis, `semilogy`
    # plots with a logarithmic y-axis — which is the point of this plot: the
    # bound 2**-nbits is a straight line on a log axis, so a divider that
    # converges at the right rate runs parallel to it, and one that does not is
    # obvious at a glance.
    #
    # Plot two things: your measured worst case at each width, and the bound
    # `1/2**widths` for comparison.  Label both axes, give it a title, and add
    # a legend so the two lines can be told apart.
    #
    # A worst case of exactly zero cannot be drawn on a log axis.  Clamp to
    # something tiny (`np.maximum(worst, 1e-18)`) so an unimplemented divider
    # produces a figure instead of an exception.
    #
    # Finish with `savefig(out_path)`.  The file is part of what you submit,
    # and the lab checks that you produced it.
    return out_path
