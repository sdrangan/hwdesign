"""Test vectors and the Python reference model for the scalar_fun demo.

The kernel, the testbench and this file all compute ``y = max(w*x + b, 0)``,
in three different places: C++, then synthesized RTL, then Python.  That
redundancy is the point.  The testbench checks itself, but a testbench that
agrees with a broken kernel still prints PASS; comparing against a model
written independently of the hardware is what catches that.

This module is the single source of the test vector.  It writes both
``cases.txt`` -- which the C++ testbench reads -- and the golden
``results.json``, so the two cannot drift apart.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Case:
    """One set of inputs to the kernel."""

    x: int
    w: int
    b: int


# Kept in step with the built-in fallback in tb_scalar_fun.cpp.
DEFAULT_CASES: list[Case] = [
    Case(x=3, w=2, b=4),      # positive, passes through
    Case(x=-1, w=5, b=0),     # negative, clipped to zero
    Case(x=10, w=-2, b=3),    # negative, clipped to zero
    Case(x=0, w=1, b=-5),     # negative bias alone, clipped to zero
    Case(x=7, w=7, b=7),      # positive, passes through
]


def scalar_fun(x: int, w: int, b: int) -> int:
    """The reference model: one artificial neuron with a ReLU."""
    act_in = w * x + b
    return act_in if act_in > 0 else 0


def write_cases(path: Path, cases: list[Case]) -> Path:
    """Write the vector in the format ``load_cases()`` in the testbench reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [str(len(cases))]
    lines += [f"{c.x} {c.w} {c.b}" for c in cases]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_golden(path: Path, cases: list[Case]) -> Path:
    """Write the expected results, in the shape the testbench writes its own."""
    path.parent.mkdir(parents=True, exist_ok=True)
    results = {
        "n": len(cases),
        "x": [c.x for c in cases],
        "w": [c.w for c in cases],
        "b": [c.b for c in cases],
        "y": [scalar_fun(c.x, c.w, c.b) for c in cases],
    }
    path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return path
