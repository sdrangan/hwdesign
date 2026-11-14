"""The Python model of the in-class exercise: the dot product of a and b.

Integers throughout, so the order of the additions does not matter and any
correct unrolled loop matches bit for bit.  The samples are in [-1000, 1000],
so no product or partial sum comes near the 32-bit limit.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

N = 256          # must match dot.h


def default_ab() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(8)
    return (rng.integers(-1000, 1001, size=N).astype(np.int16),
            rng.integers(-1000, 1001, size=N).astype(np.int16))


def dot(a: np.ndarray, b: np.ndarray) -> int:
    return int(np.dot(a.astype(np.int64), b.astype(np.int64)))


def write_cases(path: Path, a: np.ndarray, b: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(str(int(v)) for v in list(a) + list(b)) + "\n", encoding="utf-8")
    return path


def write_golden(path: Path, a: np.ndarray, b: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"n": N, "dot": dot(a, b)}, indent=2) + "\n", encoding="utf-8")
    return path
