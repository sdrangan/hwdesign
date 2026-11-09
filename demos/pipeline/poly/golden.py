"""Test vector and the Python reference model for the pipelining demo.

The kernel, the testbench and this file all evaluate the cubic

    y = ((c3*x + c2)*x + c1)*x + c0

by Horner's method in FP32.  Every operation is rounded to FP32 in the same
order in all three, so the hardware has to match this model bit for bit:
the comparison is of the floats' bit patterns, ``y_bits``, not of printed
values that can agree while the numbers differ in the last place.

This module is the single source of the test vector: it writes both
``cases.txt``, which the C++ testbench reads, and the golden ``results.json``.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

#: The coefficients c0..c3, as in the unit 7 slides' example.
DEFAULT_COEFFS = [1.0, -2.0, -3.0, 4.0]
#: Samples per call.  Enough to see the pipeline fill and drain, few enough
#: that the unpipelined co-simulation stays short.
DEFAULT_NSAMP = 64


def default_x(nsamp: int = DEFAULT_NSAMP) -> np.ndarray:
    """x evenly spaced over [-1, 1), in FP32."""
    return (np.arange(nsamp, dtype=np.float32) * np.float32(2.0 / nsamp)
            - np.float32(1.0)).astype(np.float32)


def poly(coeffs, x: np.ndarray) -> np.ndarray:
    """The reference model: Horner's method, each step rounded to FP32."""
    c = np.asarray(coeffs, dtype=np.float32)
    x = np.asarray(x, dtype=np.float32)
    y = np.full_like(x, c[3])
    for k in (2, 1, 0):
        y = (y * x).astype(np.float32)
        y = (y + c[k]).astype(np.float32)
    return y


def write_cases(path: Path, coeffs, x: np.ndarray) -> Path:
    """Write the vector in the format ``load_case()`` in the testbench reads.

    ``%.9g`` is enough digits for any FP32 value to read back exactly.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [str(len(x)), " ".join(f"{np.float32(v):.9g}" for v in coeffs)]
    lines += [f"{v:.9g}" for v in np.asarray(x, dtype=np.float32)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_golden(path: Path, coeffs, x: np.ndarray) -> Path:
    """Write the expected results, in the shape the testbench writes its own."""
    path.parent.mkdir(parents=True, exist_ok=True)
    y = poly(coeffs, x)
    results = {"n": int(len(y)),
               "y": [float(f"{v:.9g}") for v in y],
               "y_bits": [int(b) for b in y.view(np.uint32)]}
    path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return path
