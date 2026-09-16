"""Tier 0 — the subc lab's grading refuses to pay for an unimplemented divider.

These run against the *published* lab in ``labs/subc``, which is what students
actually get, and they need neither Vivado nor a working submission.

The check being pinned here is the one that is easiest to weaken by accident and
whose failure mode is silent: it hands out points rather than raising.  The
template's ``BEGIN STUB`` returns a constant zero, and a constant zero satisfies
the algorithm's error bound on every case whose true quotient is smaller than one
unit in the last place -- at ``nbits=4`` that is one input pair in sixteen.  So
the bound check on its own pays real marks for implementing nothing, and
``check_quotients`` has to detect the constant directly.
"""
from __future__ import annotations

import numpy as np
import pytest

from .conftest import REPO_ROOT, _load_module

SUBC_DIR = REPO_ROOT / "labs" / "subc"


@pytest.fixture(scope="module")
def subc():
    """The published subc build module, imported directly from labs/subc."""
    return _load_module("subc_build", SUBC_DIR / "subc_build.py")


def test_the_lab_is_worth_thirty_points(subc):
    """Three stages of ten.  A stage that silently changed weight would show here."""
    assert sum(step.points for step in subc.graded_steps()) == 30.0


def test_the_cases_are_reproducible(subc):
    """Same seed, same cases -- which is what makes a score reproducible."""
    first = subc.make_vectors()
    second = subc.make_vectors()
    assert first.equals(second)
    assert (first["a"] < first["b"]).all(), "subc_divide's precondition must hold"
    assert len(first) == subc.NTEST


def test_the_untouched_stub_scores_zero(subc):
    """A constant z earns nothing -- neither the bound check nor the variation one.

    Zeroing the bound check as well is the point.  A constant z has not met the
    bound, it has dodged the question, and crediting it proportionally would hand
    an unedited submission a few marks for free.
    """
    cases = subc.make_vectors()
    z = np.zeros(len(cases), dtype=np.int64)     # what BEGIN STUB returns
    ok = np.ones(len(cases), dtype=bool)         # it does return, on every case

    result = subc.check_quotients(cases, z, ok).result()

    # 3 of the 10 are "your file imports and runs", which the stub does earn.
    assert result.score == 3.0
    assert result.max_score == 10.0
    awarded = {c.name: c.points for c in result.checks}
    assert awarded["Your quotient meets the error bound"] == 0.0
    assert awarded["Your z actually depends on a and b"] == 0.0


def test_a_correct_divider_scores_full_marks(subc):
    """The reference implementation must satisfy the rubric it is graded by."""
    cases = subc.make_vectors()
    z = np.array([
        (int(row.a) * (1 << int(row.nbits))) // int(row.b)
        for row in cases.itertuples(index=False)
    ], dtype=np.int64)
    ok = np.ones(len(cases), dtype=bool)

    assert subc.check_quotients(cases, z, ok).result().score == 10.0


def test_a_divider_that_rounds_to_nearest_is_rejected(subc):
    """The bound is one-sided, so a smaller *absolute* error is still wrong.

    This is the distinction the lab teaches, and a rubric written with
    ``abs(err) < ulp`` would accept it.
    """
    cases = subc.make_vectors()
    z = np.array([
        round(int(row.a) * (1 << int(row.nbits)) / int(row.b))
        for row in cases.itertuples(index=False)
    ], dtype=np.int64)
    ok = np.ones(len(cases), dtype=bool)

    assert subc.check_quotients(cases, z, ok).result().score < 10.0


def test_two_constant_models_do_not_agree_their_way_to_marks(subc, tmp_path):
    """The svsim consistency floor: matching stubs prove nothing."""
    import pandas as pd

    cases = subc.make_vectors()
    flat = cases.copy()
    flat["z"] = 0
    py_path = tmp_path / "tv_python.csv"
    flat.to_csv(py_path, index=False)

    sv_path = tmp_path / "tv_sv.csv"
    pd.DataFrame({
        "a": cases["a"], "b": cases["b"], "nbits": cases["nbits"],
        "z_exp": 0, "z": 0, "cycles": cases["nbits"],
    }).to_csv(sv_path, index=False)

    z_frac, z_note, cyc_frac, _ = subc.compare_hardware(py_path, sv_path)
    assert z_frac == 0.0 and cyc_frac == 0.0
    assert "subc_divide.py" in z_note


def test_latency_is_not_credited_to_a_testbench_that_ran_nothing(subc, tmp_path):
    """cycles = 0 is what an undriven testbench records, and it is 'within nbits+2'."""
    import pandas as pd

    cases = subc.make_vectors()
    good = cases.copy()
    # A real, varying model, so the consistency floor is not what fails here.
    good["z"] = [(int(r.a) * (1 << int(r.nbits))) // int(r.b)
                 for r in cases.itertuples(index=False)]
    py_path = tmp_path / "tv_python.csv"
    good.to_csv(py_path, index=False)

    sv_path = tmp_path / "tv_sv.csv"
    pd.DataFrame({
        "a": cases["a"], "b": cases["b"], "nbits": cases["nbits"],
        "z_exp": good["z"], "z": 0xDEADBEEF, "cycles": 0,
    }).to_csv(sv_path, index=False)

    _, _, cyc_frac, _ = subc.compare_hardware(py_path, sv_path)
    assert cyc_frac == 0.0
