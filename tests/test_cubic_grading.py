"""Tier 0/1 — the cubic lab's grading refuses to pay for a design that skips saturation.

These run against the *published* lab in ``labs/cubic``, which is what students
actually get, and they need neither Vivado nor a working submission.

The check being pinned here is the one that is easiest to weaken by accident and
whose failure mode is silent: it hands out points rather than raising.  At
``FBITS_LARGE`` only about fifteen cases in a hundred come out differently if the
saturation is left out altogether — so a design that ignores overflow entirely
still matches 85% of the setting that exists to *test* overflow.  A proportional
score over that setting would charge such a design roughly a third of a point out
of thirty, which is not a grade, it is a rounding error.  ``match_rails`` is what
closes it, and ``match_rails`` is exactly the kind of check a later edit
"simplifies" away.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from .conftest import REPO_ROOT, _load_module

CUBIC_DIR = REPO_ROOT / "labs" / "cubic"


@pytest.fixture(scope="module")
def cubic():
    """The published cubic build module, imported directly from labs/cubic."""
    return _load_module("cubic_build", CUBIC_DIR / "cubic_build.py")


def reference_cubic(xint: np.ndarray, aint: np.ndarray, wid: int, fbits: int,
                    clamp) -> np.ndarray:
    """The lab's arithmetic, with the overflow policy passed in.

    Lives here rather than in ``cubic_build.py`` because that file ships whole to
    the students: a reference implementation of what they are asked to write
    cannot go in it.  ``clamp`` is the knob these tests turn — the real
    ``saturate``, or a no-op standing in for a submission that forgot it.
    """
    x2 = clamp((xint * xint) >> fbits, wid)
    ax1 = clamp(((aint[:, 1] * xint) >> fbits) + aint[:, 0], wid)
    x3 = clamp((xint * x2) >> fbits, wid)
    ax2 = clamp((aint[:, 2] * x2) >> fbits, wid)
    return np.asarray(clamp(x3 + ax2 + ax1, wid), dtype=np.int64)


def model_outputs(cubic, clamp) -> np.ndarray:
    """Run :func:`reference_cubic` over the lab's cases, at both settings."""
    cases = cubic.make_vectors()
    out = np.zeros(len(cases), dtype=np.int64)
    for fbits in cubic.FBITS_TEST:
        rows = cases["fbits"].to_numpy() == fbits
        block = cases[rows]
        out[rows] = reference_cubic(
            block["xint"].to_numpy(dtype=np.int64),
            block[["aint0", "aint1", "aint2"]].to_numpy(dtype=np.int64),
            cubic.WID, int(fbits), clamp)
    return out


def vector_files(cubic, tmp_path, yint: np.ndarray, y_dut: np.ndarray):
    """Write the two CSVs ``compare_hardware`` reads, and return their paths."""
    cases = cubic.make_vectors()
    py = cases.copy()
    py["yint"] = yint
    py["yfix"] = yint / (1 << cases["fbits"].to_numpy()).astype(float)
    py = py[["fbits", "xint", "aint0", "aint1", "aint2", "yint", "y", "yfix"]]
    py_path = tmp_path / "cubic_py.csv"
    py.to_csv(py_path, index=False)

    sv = py[["fbits", "xint", "aint0", "aint1", "aint2", "yint"]].copy()
    sv["y_dut"] = y_dut
    sv_path = tmp_path / "cubic_sv.csv"
    sv.to_csv(sv_path, index=False)
    return py_path, sv_path


# ---------------------------------------------------------------------------
# The shape of the lab
# ---------------------------------------------------------------------------

def test_the_lab_is_worth_thirty_points(cubic):
    """Three stages of ten.  A stage that silently changed weight would show here."""
    assert sum(step.points for step in cubic.graded_steps()) == 30.0


def test_the_cases_are_reproducible(cubic):
    """Same seed, same cases -- which is what makes a score reproducible."""
    first, second = cubic.make_vectors(), cubic.make_vectors()
    assert first.equals(second)
    assert len(first) == cubic.NSAMP * len(cubic.FBITS_TEST)
    assert sorted(first["fbits"].unique()) == sorted(cubic.FBITS_TEST)


def test_the_two_settings_pose_the_same_problems(cubic):
    """The rows at F=8 and F=12 are the same polynomials, so they can be compared.

    If the two halves were drawn separately, "F=12 is worse than F=8" would be a
    statement about two different test sets rather than about the format.
    """
    cases = cubic.make_vectors()
    small = cases[cases["fbits"] == cubic.FBITS_SMALL]["y"].to_numpy()
    large = cases[cases["fbits"] == cubic.FBITS_LARGE]["y"].to_numpy()
    assert np.array_equal(small, large)


def test_the_single_case_step_is_not_on_the_submission_path(cubic):
    """`svsing` is a debugging aid, so `python cubic_build.py` must not run it.

    It is in the DAG -- everything in this lab is a build step -- but nothing in
    the `submit` chain consumes it, and `--through` collects only a target's
    dependencies.  A stray edge here would make every plain build pay for a
    Vivado invocation that grades nothing.
    """
    dag = cubic.build_cubic_dag()
    submit = next(s for s in dag.steps() if s.name == "submit")
    reachable, frontier = set(), [submit]
    while frontier:
        step = frontier.pop()
        for dep in step._deps:
            if dep.name not in reachable:
                reachable.add(dep.name)
                frontier.append(dep)

    assert "svsing" in dag.step_names(), "the step should still exist"
    assert "svsing" not in reachable
    assert {"pysim", "pyeval", "svsim"} <= reachable


# ---------------------------------------------------------------------------
# Stage 1 -- the model
# ---------------------------------------------------------------------------

def test_a_correct_model_scores_full_marks(cubic):
    """The reference implementation must satisfy the rubric it is graded by."""
    from waveflow.utils.fixputils import saturate

    cases = cubic.make_vectors()
    yint = model_outputs(cubic, saturate)
    ok = np.ones(len(cases), dtype=bool)

    assert cubic.check_model(cases, yint, ok).result().score == 10.0


def test_the_untouched_stub_earns_nothing_beyond_running(cubic):
    """A constant output earns neither the range check nor the accuracy one.

    Zeroing the range check is the point.  Zero sits comfortably inside sixteen
    bits, so a model that returns it has not demonstrated that it saturates —
    it has dodged the question, and crediting it would hand an unedited
    submission three free marks.
    """
    cases = cubic.make_vectors()
    zeros = np.zeros(len(cases), dtype=np.int64)     # what BEGIN STUB returns
    ok = np.ones(len(cases), dtype=bool)             # it does return, on every case

    result = cubic.check_model(cases, zeros, ok).result()

    # 3 of the 10 are "your file imports and runs", which the stub does earn.
    assert result.score == 3.0
    assert result.max_score == 10.0


def test_a_model_that_never_saturates_loses_the_range_check(cubic):
    """Without saturation the F=12 outputs leave the register, and that is caught."""
    cases = cubic.make_vectors()
    yint = model_outputs(cubic, lambda v, w: np.asarray(v))
    ok = np.ones(len(cases), dtype=bool)

    awarded = {c.name: c.points
               for c in cubic.check_model(cases, yint, ok).checks}
    range_check = f"Every output fits in {cubic.WID} bits"
    assert awarded[range_check] < 3.0


# ---------------------------------------------------------------------------
# Stage 3 -- the hardware comparison, and the reason match_rails exists
# ---------------------------------------------------------------------------

def test_a_correct_design_scores_full_marks(cubic, tmp_path):
    from waveflow.utils.fixputils import saturate

    yint = model_outputs(cubic, saturate)
    py_path, sv_path = vector_files(cubic, tmp_path, yint, yint)

    scored = cubic.compare_hardware(py_path, sv_path)
    assert all(frac == 1.0 for frac, _ in scored.values())


def test_skipping_saturation_is_not_a_rounding_error(cubic, tmp_path):
    """The check this whole module exists for.

    A design that ignores overflow still matches most of the saturating
    setting, so the proportional check barely moves.  ``match_rails`` has to
    zero, or forgetting the one thing F=12 is there to test costs almost
    nothing.
    """
    from waveflow.utils.fixputils import saturate

    yint = model_outputs(cubic, saturate)                      # correct Python
    y_dut = model_outputs(cubic, lambda v, w: np.asarray(v))   # hardware without sat
    py_path, sv_path = vector_files(cubic, tmp_path, yint, y_dut)

    scored = cubic.compare_hardware(py_path, sv_path)

    assert scored[cubic.MATCH_SMALL][0] == 1.0, "F=8 never saturates, so it is unaffected"
    # The proportional check is nearly satisfied -- which is the problem.
    assert scored[cubic.MATCH_LARGE][0] > 0.5
    # And this is the answer to it.
    assert scored[cubic.MATCH_RAILS][0] == 0.0
    assert "all or nothing" in scored[cubic.MATCH_RAILS][1]


def test_a_python_model_that_never_clamps_cannot_pass_the_rails_check(cubic, tmp_path):
    """Two unsaturated models agreeing is not evidence, one level down from the constant trap.

    ``match_rails`` reads the saturating cases off the student's own Python
    output.  If that output never reaches a rail there is no subset to check,
    and an empty subset must score zero rather than pass vacuously.
    """
    no_sat = model_outputs(cubic, lambda v, w: np.asarray(v))
    py_path, sv_path = vector_files(cubic, tmp_path, no_sat, no_sat)

    scored = cubic.compare_hardware(py_path, sv_path)
    assert scored[cubic.MATCH_RAILS][0] == 0.0
    assert "cubic_model.py" in scored[cubic.MATCH_RAILS][1]


def test_two_constant_models_do_not_agree_their_way_to_marks(cubic, tmp_path):
    """The svsim consistency floor: matching stubs prove nothing."""
    zeros = np.zeros(cubic.NSAMP * len(cubic.FBITS_TEST), dtype=np.int64)
    py_path, sv_path = vector_files(cubic, tmp_path, zeros, zeros)

    scored = cubic.compare_hardware(py_path, sv_path)
    assert all(frac == 0.0 for frac, _ in scored.values())
    assert "cubic_model.py" in scored[cubic.MATCH_SMALL][1]


def test_a_short_simulation_scores_zero_rather_than_matching_what_it_reached(cubic, tmp_path):
    """The watchdog calls $finish, so a stalled run looks like a *successful* short one."""
    from waveflow.utils.fixputils import saturate

    yint = model_outputs(cubic, saturate)
    py_path, sv_path = vector_files(cubic, tmp_path, yint, yint)
    pd.read_csv(sv_path).head(10).to_csv(sv_path, index=False)

    scored = cubic.compare_hardware(py_path, sv_path)
    assert all(frac == 0.0 for frac, _ in scored.values())
    assert "stopped early" in scored[cubic.MATCH_SMALL][1]
