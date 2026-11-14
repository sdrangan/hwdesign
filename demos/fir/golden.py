"""The Python model of the FIR demo: y[n] = sum_k h[k] x[n-k], x[n] = 0 for n < 0.

Integers throughout, so every variant of the kernel must match bit for bit,
whatever order it adds in.  Samples and coefficients are in [-1000, 1000], so
a sum of 16 products stays far inside 32 bits.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

NTAPS = 16          # must match fir.h
NSAMP = 1024        # the test vector: a full-size call, MAX_NSAMP in fir.h


def default_case() -> tuple[np.ndarray, np.ndarray]:
    """A smoothing filter's shape (a raised cosine, scaled to integers), and a
    noisy square wave to filter."""
    k = np.arange(NTAPS)
    h = np.round(1000 * (0.5 - 0.5 * np.cos(2 * np.pi * (k + 1) / (NTAPS + 1)))).astype(np.int16)
    rng = np.random.default_rng(16)
    n = np.arange(NSAMP)
    x = 600 * np.sign(np.sin(2 * np.pi * n / 128)) + rng.integers(-300, 301, size=NSAMP)
    return h, np.clip(x, -1000, 1000).astype(np.int16)


def fir(h: np.ndarray, x: np.ndarray) -> np.ndarray:
    return np.convolve(x.astype(np.int64), h.astype(np.int64))[:len(x)]


def write_cases(path: Path, h: np.ndarray, x: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    vals = [len(x)] + [int(v) for v in h] + [int(v) for v in x]
    path.write_text("\n".join(str(v) for v in vals) + "\n", encoding="utf-8")
    return path


def write_golden(path: Path, h: np.ndarray, x: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"nsamp": len(x), "y": [int(v) for v in fir(h, x)]}) + "\n",
                    encoding="utf-8")
    return path
