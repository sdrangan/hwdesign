"""fsolve_eval — comparing what the kernel returned with what the model predicted.

The testbench writes one row per test vector: the inputs it was given, and the
``x``, ``fx`` and ``niter`` the kernel returned.  The vector file has the same
inputs and the golden model's answer.  This file decides whether the two
agree.

"Agree" cannot mean "equal".  The kernel and the model compute in the same
precision, and if they evaluate the polynomial in the same order they often
do match to the last bit -- but nothing guarantees it, and a synthesized
floating-point core is allowed to round differently from the CPU in cases
the C standard leaves open.  What *is* guaranteed is weaker, and it is what
this file checks:

* **The kernel converged** -- ``|fx| < tol`` at the ``x`` it returned.  A root
  estimate that is close to the model's but did not converge is a kernel that
  ran out of iterations by luck.
* **It found the same root**, to within ``xtol``.  Both answers satisfy
  ``|f(x)| < tol``, so both are within about ``tol / f'(root)`` of the true
  root, and a rounding difference moves the answer around inside that band.
* **It took about as many steps**, to within ``niter_tol``.  Near the end of a
  run ``|f(x)|`` shrinks by only a few percent per update, so a rounding
  difference in ``f`` can move the moment it crosses ``tol`` by an update or
  two.  A difference of fifty is not rounding -- it is a different loop.

The tolerances are the lab's, and the build passes them in.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray


def vector_errors(golden: pd.DataFrame, dut: pd.DataFrame) -> pd.DataFrame:
    """Return the absolute difference between the model and the kernel, per vector.

    Parameters
    ----------
    golden : pd.DataFrame
        The test vectors, with the model's answers in columns ``x``, ``fx``
        and ``niter``.
    dut : pd.DataFrame
        What the testbench recorded: the same rows in the same order, with the
        kernel's answers in columns ``x``, ``fx`` and ``niter``.

    Returns
    -------
    pd.DataFrame
        One row per vector and three columns:

        * ``x_err``     -- ``|x_golden - x_dut|``
        * ``fx_err``    -- ``|fx_golden - fx_dut|``
        * ``niter_err`` -- ``|niter_golden - niter_dut|``
    """
    # TODO:  Build and return the three columns, then delete the placeholder.
    #
    # `golden["x"] - dut["x"]` subtracts row by row, because the two frames
    # have the same rows in the same order; `.abs()` does the rest.  Return
    # a DataFrame with the columns x_err, fx_err and niter_err.
    n = len(golden)
    return pd.DataFrame({"x_err": np.zeros(n), "fx_err": np.zeros(n),
                         "niter_err": np.zeros(n, dtype=np.int64)})


def vector_matches(golden: pd.DataFrame, dut: pd.DataFrame,
                   xtol: float, niter_tol: int) -> NDArray[np.bool_]:
    """Return which vectors the kernel got right, as a boolean array.

    A vector matches when all three of these hold -- see the module docstring
    for why each one is there:

    * the kernel converged:  ``|fx_dut| < tol``, with ``tol`` the vector's own
      tolerance from the ``tol`` column;
    * ``|x_golden - x_dut| <= xtol``;
    * ``|niter_golden - niter_dut| <= niter_tol``.

    Parameters
    ----------
    golden, dut : pd.DataFrame
        As for :func:`vector_errors`.
    xtol : float
        The largest root difference that counts as the same root.
    niter_tol : int
        The largest iteration-count difference that counts as the same run.

    Returns
    -------
    NDArray[np.bool_]
        One entry per vector, True where the kernel matched.
    """
    # TODO:  Combine the three conditions, then delete the placeholder.
    #
    # Call your own vector_errors() for the two differences rather than
    # computing them again -- if it is wrong you want it wrong in one place.
    # Each condition is a boolean array with one entry per vector, and `&`
    # combines them element by element.  Take `tol` from golden["tol"], not
    # from a constant: it is a per-vector input like any other.
    return np.zeros(len(golden), dtype=bool)


if __name__ == "__main__":
    # Handy while you are working: compare the C-simulation output directly,
    # once the build has produced it.
    from pathlib import Path

    here = Path(__file__).resolve().parent
    golden = pd.read_csv(here / "vectors" / "tv_python.csv")
    dut = pd.read_csv(here / "vectors" / "tv_csim.csv")
    err = vector_errors(golden, dut)
    ok = vector_matches(golden, dut, xtol=1e-4, niter_tol=5)
    print(pd.concat([golden[["x", "niter"]], err], axis=1).assign(match=ok).to_string())
    print(f"\n  {int(np.sum(ok))} of {len(ok)} vectors match")
