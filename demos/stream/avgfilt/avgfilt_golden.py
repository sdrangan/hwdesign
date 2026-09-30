"""The Python golden model and test signal for the avgfilt demo.

The kernel, the testbench and this file all compute the same moving average
of squares,

    y[k] = (x[k]**2 + x[k-1]**2 + x[k-2]**2) / WIN_SIZE

in three places: C++, then synthesized RTL, then Python.  That redundancy is
the point.  The testbench checks itself, but a testbench that agrees with a
broken kernel still prints PASS; comparing against a model written
independently of the hardware is what catches that.

The model computes in float32, in the same order as the kernel -- square,
add the two older squares left to right, multiply by 1/WIN_SIZE -- so a
correct kernel matches it bit for bit, not merely to within a tolerance.

This module is also the single source of the test signal: it writes
``vectors/tv_python.csv``, which the C++ testbench reads its input from.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

#: The window length.  Must match ``win_size`` in avgfilt.h.
WIN_SIZE = 3

#: Columns of every vector file: the golden model's, and the two the
#: testbench writes after C simulation and co-simulation.
COLUMNS = ["n", "x", "y"]


def test_signal(nsamp: int = 200, seed: int = 1) -> np.ndarray:
    """A sinusoid whose amplitude steps up halfway, plus a little noise.

    The frequency is 1/6 cycle per sample, so ``sin**2`` repeats every 3
    samples and the 3-sample average of it is exactly ``amp**2 / 2``: the
    squared input swings from 0 to ``amp**2`` while the output stays flat.
    The output tracks the signal's power, so at the amplitude step it jumps
    from 0.125 to 1.125.  Only the noise makes it ripple.
    """
    rng = np.random.default_rng(seed)
    n = np.arange(nsamp)
    amp = np.where(n < nsamp // 2, 0.5, 1.5)
    x = amp * np.sin(2 * np.pi * n / 6) + 0.05 * rng.standard_normal(nsamp)
    return x.astype(np.float32)


def avgfilt(x: np.ndarray) -> np.ndarray:
    """The reference model.  The filter starts from zero state, as the kernel does."""
    x = np.asarray(x, dtype=np.float32)
    xsq = x * x
    # The two older squares, delayed by one and two samples, with zeros
    # shifted in -- the kernel's xsq0 and xsq1.
    xsq0 = np.concatenate([np.zeros(1, np.float32), xsq[:-1]])
    xsq1 = np.concatenate([np.zeros(2, np.float32), xsq[:-2]])
    inv_win_size = np.float32(1) / np.float32(WIN_SIZE)
    return ((xsq + xsq0) + xsq1) * inv_win_size


def write_vectors(path: Path, x: np.ndarray, y: np.ndarray) -> Path:
    """Write ``n,x,y`` rows.  ``%.9g`` round-trips a float32 exactly."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(COLUMNS)]
    lines += [f"{i},{float(xi):.9g},{float(yi):.9g}" for i, (xi, yi) in enumerate(zip(x, y))]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def read_vectors(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read back the ``x`` and ``y`` columns of a vector file, as float32."""
    data = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
    if data.size == 0:
        return np.zeros(0, np.float32), np.zeros(0, np.float32)
    return data[:, 1].astype(np.float32), data[:, 2].astype(np.float32)
