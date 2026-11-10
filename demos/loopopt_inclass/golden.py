"""The Python model of the in-class exercise: y[i] = x[i]^2 + x[i-1]^2, x[-1] = 0.

In float32, in the kernel's order: each square rounded, then the sum
rounded.  The test values are multiples of 1/8 in [-4, 4), so every square
and sum is exact anyway, and any correct rewrite matches bit for bit.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

N = 256          # must match sqsum.h


def default_x() -> np.ndarray:
    rng = np.random.default_rng(7)
    return (rng.integers(-32, 32, size=N) / 8).astype(np.float32)


def sqsum(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    prev = np.concatenate([np.zeros(1, np.float32), x[:-1]])
    return (x * x + prev * prev).astype(np.float32)


def write_cases(path: Path, x: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{v:.9g}" for v in x) + "\n", encoding="utf-8")
    return path


def write_golden(path: Path, x: np.ndarray) -> Path:
    y = sqsum(x)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"n": N, "y": [float(v) for v in y],
                                "y_bits": [int(b) for b in y.view(np.uint32)]}, indent=2)
                    + "\n", encoding="utf-8")
    return path
