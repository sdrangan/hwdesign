"""cubic_model — a monic cubic polynomial, in floating point and in fixed point.

This is the golden model.  You will write the same arithmetic in SystemVerilog,
and the lab checks that the two agree **exactly** — not approximately, bit for
bit, including what happens when a value will not fit.

The function is

    y = x**3 + a2*x**2 + a1*x + a0

and the fixed-point version evaluates it on integers.  A value in ``Q(wid,
fbits)`` is the integer ``s`` standing for the real number ``s / 2**fbits``, in
a register ``wid`` bits wide.  Two facts follow, and they are the whole content
of this file:

**A product gains fractional bits.**  Multiplying two ``Q(wid, fbits)`` integers
gives a number with ``2*fbits`` fractional bits, so it has to be shifted back
down by ``fbits`` to be a ``Q(·, fbits)`` value again::

    x2int = (xint * xint) >> fbits

**A product also gains integer bits, and those have nowhere to go.**  The shift
above fixes the binary point but not the width: the result needs about
``2*wid - fbits`` bits, and it is being put back into ``wid``.  When it does not
fit, something has to give, and *which* thing is a design decision:

* **saturate** — clamp to the largest or smallest value the register holds.  The
  answer is wrong, but it is wrong in the direction it was already heading.
* **truncate** — keep the low ``wid`` bits and throw the rest away.  A number
  slightly too large comes back as a large negative one, and the output flips
  sign for no reason a plot can explain.

This lab saturates, because a saturating cubic degrades into something you can
still recognise and a wrapping one does not.  ``saturate`` and ``truncate`` both
come from :mod:`waveflow.utils.fixputils`, and you can swap one for the other in
a scratch copy to see the difference for yourself.

Everything is stored in ``np.int64`` rather than a ``wid``-bit type.  Numpy has
no 16-bit-with-saturation integer, and using int64 with an explicit
``saturate`` after each step models the hardware exactly while keeping the
overflow *visible in the source* instead of hidden in a dtype.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# `saturate(x, wid)` clamps to the signed `wid`-bit range; `truncate(x, wid)`
# wraps to it.  Both come from waveflow, so this model and the `sat` function in
# cubic.sv are two spellings of one definition.  The lab grades `saturate`;
# `truncate` is imported so you can substitute it and watch what happens.
from waveflow.utils.fixputils import saturate, truncate  # noqa: F401

#: The lab's two settings, and what makes them interesting.  At 8 fractional
#: bits the intermediate values of a cubic over this input range fit, and the
#: fixed-point curve lies on the floating-point one.  At 12 there are four fewer
#: integer bits, ``x**3`` runs off the end of the register, and the saturation
#: becomes plainly visible.  Nothing else about the two settings differs.
WID = 16
FBITS_SMALL = 8
FBITS_LARGE = 12


def cubic_float(
        x: NDArray[np.float64],     # shape (n,)
        a: NDArray[np.float64],     # shape (n, 3)
    ) -> NDArray[np.float64]:
    """Evaluate the monic cubic in floating point.

        y = a[:, 0] + a[:, 1] * x + a[:, 2] * x**2 + x**3

    This one is given.  It is the reference the fixed-point version is measured
    against, so there is nothing to decide here — no widths, no overflow, no
    rounding worth speaking of.

    Parameters
    ----------
    x : NDArray[np.float64]
        Input values, shape ``(n,)``.
    a : NDArray[np.float64]
        Coefficients ``a0, a1, a2``, shape ``(n, 3)``.

    Returns
    -------
    NDArray[np.float64]
        The polynomial at each ``x``, shape ``(n,)``.
    """
    return a[:, 0] + a[:, 1] * x + a[:, 2] * x**2 + x**3


def cubic_fixed(
        xint: NDArray[np.int64],    # shape (n,)
        aint: NDArray[np.int64],    # shape (n, 3)
        wid: int = WID,
        fbits: int = FBITS_SMALL,
    ) -> NDArray[np.int64]:
    """Evaluate the same cubic on ``Q(wid, fbits)`` integers.

    Every input, every intermediate and the output are ``Q(wid, fbits)``: after
    each product you shift by ``fbits`` to put the binary point back, and
    saturate to ``wid`` bits so nothing silently outgrows its register.

    Keep the *order* of the terms as the docstring gives it.  Saturation is not
    associative — clamping after ``x3 + ax2`` and then adding ``ax1`` can give a
    different answer from clamping once at the end — and your SystemVerilog has
    to reproduce whatever this file does, case for case.

    Parameters
    ----------
    xint : NDArray[np.int64]
        Input values in ``Q(wid, fbits)``, shape ``(n,)``.
    aint : NDArray[np.int64]
        Coefficients in ``Q(wid, fbits)``, shape ``(n, 3)``.
    wid : int
        Total bit width of the inputs, the output and every intermediate.
    fbits : int
        Fractional bits in that width.

    Returns
    -------
    NDArray[np.int64]
        The output in ``Q(wid, fbits)``, shape ``(n,)``.  Every value is within
        the signed ``wid``-bit range.
    """
    xint = np.asarray(xint, dtype=np.int64)
    aint = np.asarray(aint, dtype=np.int64)

    # TODO:  Evaluate the cubic in fixed point, and delete the `return` below.
    #
    #     x2int  = ...    x**2
    #     ax1int = ...    a1*x + a0
    #     x3int  = ...    x**3
    #     ax2int = ...    a2*x**2
    #     return ...      the sum of the three terms
    #
    # The pattern for one product is
    #
    #     saturate((p * q) >> fbits, wid)
    #
    # and it is worth understanding both halves before you write five of them:
    #
    #   * `>> fbits` is there because a product of two Q(wid, fbits) numbers has
    #     2*fbits fractional bits.  Without the shift your answer is 2**fbits
    #     times too large.
    #
    #   * `saturate(..., wid)` is there because the product also needs more
    #     *integer* bits than wid has.  Without it the model keeps values the
    #     hardware cannot hold, and your SystemVerilog will not match.
    #
    # Two things that are easy to get wrong:
    #
    #   * `a0` is not a product.  It is already Q(wid, fbits), so it is added
    #     directly -- shifting it would divide it by 2**fbits.
    #
    #   * Build x**3 as `xint * x2int`, reusing the square you already have.
    #     `xint**3` in one step would need three times the fractional bits and a
    #     different shift, and it is not what the hardware does.
    #
    # Saturate after every product and after the final sum.  Where you saturate
    # changes the answer, and the SystemVerilog has to make the same choices.
    return np.zeros(len(xint), dtype=np.int64)


def to_fixed(values: NDArray[np.float64], fbits: int) -> NDArray[np.int64]:
    """Convert real values to their ``Q(·, fbits)`` integers.  Given.

    Rounds rather than truncates, so the conversion itself costs at most half a
    unit in the last place and the error you measure later is the *arithmetic's*
    error rather than this function's.
    """
    return np.round(np.asarray(values, dtype=np.float64) * (1 << fbits)).astype(np.int64)


def to_real(ints: NDArray[np.int64], fbits: int) -> NDArray[np.float64]:
    """Convert ``Q(·, fbits)`` integers back to real values.  Given."""
    return np.asarray(ints, dtype=np.float64) / (1 << fbits)


if __name__ == "__main__":
    # Handy while you are working: run this file directly to see one case at
    # both settings, without going through the build.
    x = np.array([2.5])
    a = np.array([[1.0, -0.5, 0.25]])
    print(f"  x = {x[0]}   a0, a1, a2 = {tuple(a[0])}")
    print(f"  float      y = {cubic_float(x, a)[0]:.6f}")
    for fbits in (FBITS_SMALL, FBITS_LARGE):
        yint = cubic_fixed(to_fixed(x, fbits), to_fixed(a, fbits), WID, fbits)
        print(f"  Q({WID},{fbits:2d})   y = {to_real(yint, fbits)[0]:.6f}"
              f"   (yint = {int(yint[0])})")
