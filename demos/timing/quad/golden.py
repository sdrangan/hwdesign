"""Test vectors and the Python reference model for the quad demo.

The kernel, the testbench and this file all compute y = w2*x^2 + w1*x + w0.
Comparing the hardware's output against a model written independently of it
is what catches a testbench that agrees with a broken kernel.

This module is the single source of the test vector: it writes both
``cases.txt``, which the C++ testbench reads, and the golden ``results.json``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Case:
    """One set of inputs to the kernel."""

    x: int
    w2: int
    w1: int
    w0: int


# The first three are the unit 6 slides' example: w0, w1, w2 = 4, -7, 5 and
# x = 10, -4, 8, giving y = 434, 112, 268.  Kept in step with the built-in
# fallback in tb_quad.cpp.
DEFAULT_CASES: list[Case] = [
    Case(x=10, w2=5, w1=-7, w0=4),
    Case(x=-4, w2=5, w1=-7, w0=4),
    Case(x=8, w2=5, w1=-7, w0=4),
    Case(x=3, w2=2, w1=1, w0=0),
    Case(x=-6, w2=-1, w1=3, w0=9),
]


def quad(x: int, w2: int, w1: int, w0: int) -> int:
    """The reference model.  The vector is small enough that 32-bit int
    arithmetic never wraps, so plain Python integers agree with the C++."""
    return w2 * x * x + w1 * x + w0


def write_cases(path: Path, cases: list[Case]) -> Path:
    """Write the vector in the format ``load_cases()`` in the testbench reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [str(len(cases))] + [f"{c.x} {c.w2} {c.w1} {c.w0}" for c in cases]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_golden(path: Path, cases: list[Case]) -> Path:
    """Write the expected results, in the shape the testbench writes its own."""
    path.parent.mkdir(parents=True, exist_ok=True)
    results = {"n": len(cases), "y": [quad(c.x, c.w2, c.w1, c.w0) for c in cases]}
    path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return path
