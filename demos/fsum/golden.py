"""The Python model of the float-sum demo: the sum of N floats.

The four variants add in different orders, and in general a float sum depends
on the order.  So the test values are multiples of 1/8 in [-4, 4): every
partial sum of 1024 of them is a multiple of 1/8 below 4096 in size, which a
float holds exactly, and every order gives the same, exact, result.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

N = 1024          # must match fsum.h


def default_x() -> np.ndarray:
    rng = np.random.default_rng(9)
    return (rng.integers(-32, 32, size=N) / 8).astype(np.float32)


def fsum(x: np.ndarray) -> np.float32:
    return np.float32(np.sum(x.astype(np.float64)))     # exact for these values


def write_cases(path: Path, x: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{v:.9g}" for v in x) + "\n", encoding="utf-8")
    return path


def write_golden(path: Path, x: np.ndarray) -> Path:
    s = fsum(x)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"n": N, "sum": float(s),
                                "sum_bits": int(np.array([s], np.float32).view(np.uint32)[0])},
                               indent=2) + "\n", encoding="utf-8")
    return path
