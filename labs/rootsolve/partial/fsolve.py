"""fsolve — the golden model: a root solver for a monic cubic, in float32.

This is the model the Vitis kernel in ``fsolve.cpp`` is checked against.  It
finds a root of

    f(x) = a0 + a1*x + a2*x**2 + x**3

with the simplest iteration there is,

    x[k+1] = x[k] - step * f(x[k])

stopping as soon as ``|f(x)| < tol``, or after ``max_iter`` updates if that
never happens.

Everything is computed in **single precision** (``np.float32``), because that
is what the hardware computes in.  A golden model in float64 would be *more*
accurate than the kernel, and the difference would show up in the comparison
as a mismatch that is nobody's bug.

Why the iteration converges
---------------------------
If ``f`` is increasing, then ``f(x) > 0`` means ``x`` is to the right of the
root and ``x - step*f(x)`` moves left; ``f(x) < 0`` moves right.  Either way
``x`` heads toward the root -- provided ``step`` is small enough not to jump
over it and land further away than it started.

A monic cubic is increasing everywhere exactly when its derivative
``3x**2 + 2*a2*x + a1`` has no real root, which is when

    a1 > a2**2 / 3

That condition is what ``make_vectors`` has to respect.  Draw coefficients
without it and some of your test vectors will have three roots, or a flat
spot, and the iteration can stall or wander off.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# The range the test vectors are drawn from.  Given.
#
# `step` is drawn rather than fixed so that the vectors exercise different
# convergence rates -- a vector at step=0.05 takes about twice as many
# iterations as the same one at step=0.1.  The upper limit is set by the
# steepest derivative these coefficients can produce near a root: much above
# 0.1 and the iteration starts to overshoot.
# ---------------------------------------------------------------------------
A0_LO, A0_HI = -2.0, 2.0
A2_LO, A2_HI = -1.5, 1.5
#: a1 is drawn as ``a2**2/3 + margin``, with the margin in this range.  The
#: lower limit keeps f from being nearly flat at its root, which is where the
#: iteration is slowest.
A1_MARGIN_LO, A1_MARGIN_HI = 0.5, 2.5
X0_LO, X0_HI = -1.0, 1.0
STEP_LO, STEP_HI = 0.05, 0.1
TOL = 1e-5
MAX_ITER = 500

#: The columns of a test-vector file, in order.  The first seven are the
#: kernel's inputs, in the order ``fsolve()`` takes them; the last three are
#: what the golden model produced.  ``tb_fsolve.cpp`` reads the file by
#: position, so this order is fixed.
VECTOR_COLUMNS = ["a0", "a1", "a2", "x0", "tol", "max_iter", "step", "x", "fx", "niter"]


def fcubic(x: np.float32, a0: np.float32, a1: np.float32, a2: np.float32) -> np.float32:
    """Evaluate the monic cubic at one point, in float32.  Given.

    The order of the operations is deliberate, and ``fsolve.cpp`` should use
    the same one::

        x2 = x * x
        x3 = x2 * x
        fx = a0 + a1*x + a2*x2 + x3      # added left to right

    Floating-point addition is not associative: ``(a + b) + c`` and
    ``a + (b + c)`` can differ in the last bit.  Evaluate the polynomial in
    the same order in both languages and the two can agree *exactly*; evaluate
    it differently -- Horner's rule, say -- and they agree only to within
    rounding, which is enough to shift the iteration count by one or two.
    """
    x2 = x * x
    x3 = x2 * x
    return a0 + a1 * x + a2 * x2 + x3


def fsolve(
        a0: float,
        a1: float,
        a2: float,
        x0: float,
        tol: float = TOL,
        max_iter: int = MAX_ITER,
        step: float = 0.1,
    ) -> tuple[np.float32, np.float32, int, dict[str, list[np.float32]]]:
    """Find a root of the monic cubic by the iteration ``x <- x - step*f(x)``.

    The arguments are in the same order as the kernel's in ``fsolve.cpp``.

    The iteration is::

        x  = x0
        fx = f(x)
        repeat until |fx| < tol, or max_iter updates have been made:
            x  = x - step * fx
            fx = f(x)

    Three things about it are part of the specification, because the kernel
    has to do the same and the lab checks that it does:

    * ``fx`` is always ``f(x)`` **at the returned x** -- not at the x before
      the last update.
    * ``niter`` counts **updates**.  If ``x0`` is already a root, ``niter`` is
      0.  If the loop runs out, ``niter`` is ``max_iter``.
    * It stops at the **first** ``x`` with ``|f(x)| < tol``.  One extra update
      would still be a root, but it would not be the one the kernel returns.

    Parameters
    ----------
    a0, a1, a2 : float
        The coefficients of ``f(x) = a0 + a1*x + a2*x**2 + x**3``.
    x0 : float
        The starting point.
    tol : float
        Stop once ``|f(x)| < tol``.
    max_iter : int
        The most updates to make.
    step : float
        The step size.

    Returns
    -------
    x : np.float32
        The final estimate of the root.
    fx : np.float32
        ``f(x)`` at that estimate.
    niter : int
        The number of updates made.
    hist : dict
        ``{"x": [...], "fx": [...]}`` -- every x visited and f at it, *starting
        with x0*, so both lists have ``niter + 1`` entries and the last ones
        are the returned ``x`` and ``fx``.
    """
    # Everything in float32, including the constants.  A single float64 in
    # the loop would promote the whole update to float64, and the model would
    # quietly stop being a model of the hardware.
    a0, a1, a2 = np.float32(a0), np.float32(a1), np.float32(a2)
    tol, step = np.float32(tol), np.float32(step)

    x = np.float32(x0)
    fx = fcubic(x, a0, a1, a2)
    niter = 0
    hist: dict[str, list[np.float32]] = {"x": [x], "fx": [fx]}

    # TODO:  Run the iteration.  While |fx| >= tol and fewer than max_iter
    # updates have been made:
    #
    #     update x        x = x - step*fx
    #     recompute fx    at the new x, with fcubic
    #     count it        niter
    #     record it       append the new x and fx to hist
    #
    # Test the stopping condition *before* each update, not after it.  If x0
    # is already a root the loop must not run at all, and niter must be 0.

    return x, fx, niter, hist


def plot_convergence(hist: dict[str, list[np.float32]], tol: float, out_path: Path) -> Path:
    """Plot one run of the solver, and save the figure to *out_path*.

    Two subplots side by side, both against the iteration number:

    * ``x``, so the approach to the root is visible;
    * ``|f(x)|`` on a **log** scale, with ``tol`` drawn as a horizontal line.
      On a linear axis the last ninety percent of the run is a flat line on
      the floor; on a log axis it is a straight slope, and the slope is the
      convergence rate.

    Parameters
    ----------
    hist : dict
        The ``hist`` that :func:`fsolve` returned.
    tol : float
        The tolerance the run stopped at.
    out_path : Path
        Where to write the PNG.
    """
    # The backend is set up for you; `Agg` writes files without opening a window.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    iters = np.arange(len(hist["x"]))

    # TODO:  Draw the two subplots and save the figure to `out_path`.
    #
    # `plt.subplots(1, 2)` gives you a figure and two axes.  On the first,
    # plot hist["x"] against `iters`.  On the second, plot the absolute value
    # of hist["fx"] with `semilogy`, and mark `tol` with `axhline`.  Label
    # the axes, then `savefig(out_path)` and `plt.close` the figure.
    return out_path


def make_vectors(nvec: int, seed: int) -> pd.DataFrame:
    """Draw *nvec* random problems, solve each one, and return the table.

    These are the test vectors: the testbench feeds the first seven columns
    to the kernel and records what comes back, and ``fsolve_eval.py`` compares
    that against the last three.

    Draw each problem from the ranges at the top of this file:

    * ``a2`` uniform in ``[A2_LO, A2_HI]``;
    * ``a1`` as ``a2**2 / 3`` plus a margin uniform in
      ``[A1_MARGIN_LO, A1_MARGIN_HI]`` -- this is what keeps ``f`` increasing,
      see the module docstring;
    * ``a0`` uniform in ``[A0_LO, A0_HI]``, ``x0`` in ``[X0_LO, X0_HI]``,
      ``step`` in ``[STEP_LO, STEP_HI]``;
    * ``tol = TOL`` and ``max_iter = MAX_ITER`` for every vector.

    Then run :func:`fsolve` on it.

    Store every real-valued input as the float32 value the model actually
    used -- ``float(np.float32(v))``, not ``v``.  The testbench reads the file
    into ``float`` variables, and if the file held the float64 value the
    kernel would be handed a slightly different number than the model was.

    Parameters
    ----------
    nvec : int
        How many vectors to draw.
    seed : int
        Seed for ``np.random.default_rng``, so the same call gives the same
        vectors every time.

    Returns
    -------
    pd.DataFrame
        One row per vector, with exactly the columns in ``VECTOR_COLUMNS``,
        in that order.
    """
    rng = np.random.default_rng(seed)

    # TODO:  Build `rows`, one dict per vector with the keys in
    # VECTOR_COLUMNS, then delete the `rows = []` placeholder below.
    #
    # For each of the `nvec` vectors: draw a2 first (a1 depends on it), then
    # a1, a0, x0 and step with `rng.uniform(lo, hi)`.  Round each to float32,
    # call fsolve, and record the inputs alongside the x, fx and niter it
    # returned.  Store x and fx as plain floats and niter as an int.
    rows = []
    return pd.DataFrame(rows, columns=VECTOR_COLUMNS)


if __name__ == "__main__":
    # Handy while you are working: run this file directly to solve one
    # problem and see the iteration, without going through the build.
    x, fx, niter, hist = fsolve(-1.0, 1.5, 0.5, x0=0.0, tol=TOL, max_iter=MAX_ITER, step=0.1)
    print(f"  root x = {float(x):.7f}   f(x) = {float(fx):.3e}   after {niter} updates")
    print(make_vectors(5, seed=0).to_string(index=False))
