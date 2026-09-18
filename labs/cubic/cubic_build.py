"""cubic — the Unit 3 lab build.

Three graded stages, run one at a time::

    python cubic_build.py --list-steps-verbose   # what the stages are
    python cubic_build.py --through pysim        # the fixed-point model, scored
    python cubic_build.py --through pyeval       # measure what it cost, scored
    python cubic_build.py --through svsim        # the SystemVerilog, scored
    python cubic_build.py                        # everything, then the submission zip
    python cubic_build.py --grades               # your scores, without rebuilding

and one ungraded stage you can run whenever you want it::

    python cubic_build.py --through svsing       # one hand-picked case, with waveforms

``pysim`` runs your Python cubic over the lab's cases at both bit-width settings
and asks whether the numbers stay inside their registers and still track the
floating-point answer.  ``pyeval`` runs the measuring code *you* wrote over
those results and asks two different questions of it: is your measurement right,
and does moving the binary point do what the theory says it does?  ``svsim``
then runs your SystemVerilog against the same cases and checks it against your
Python, case for case -- including the cases that saturate, where agreeing is
harder than it sounds.

The order is the point.  You find out whether the widths work while it is still
Python, where a fix costs an edit -- not after it is a pipeline, where it costs
an afternoon.

``svsing`` is not graded and is not part of the submission.  It runs one case
through ``tb_cubic_sing.sv`` and prints the pipeline registers cycle by cycle,
which is what you want when ``svsim`` says two hundred cases disagree and you
need to see one of them.

YOU DO NOT NEED TO EDIT THIS FILE.  Your work goes in ``cubic_model.py``,
``cubic_eval.py``, ``cubic.sv`` and ``tb_cubic_sing.sv``.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from waveflow.build.build import BuildConfig, BuildDag, BuildStep

from hwdesign.grading import (
    Checks, GradeReportStep, GradedStep, GradeResult, StudentSourceStep,
    run_graded_dag_cli,
)

_SOURCE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# The lab's specification
#
# These live here rather than in cubic_model.py so that the grader and the
# simulator agree on them no matter what a submission does to its own
# constants -- and so that a file which fails to import at all can still be
# scored against the right numbers instead of crashing the build.
# ---------------------------------------------------------------------------

#: The register width every value in this lab lives in.  Fixed: the lab is about
#: what happens when you move the binary point *within* a width, not about
#: buying accuracy with more bits.
WID = 16

#: The two settings, and the whole design of the lab.  Same width, same inputs,
#: four fractional bits apart.  At 8 the intermediate values of a cubic over
#: this input range fit and the fixed-point curve lies on the floating-point
#: one; at 12 there are four fewer integer bits, x**3 runs off the end, and the
#: saturation is visible to the eye.  They are graded separately for that
#: reason -- matching Python on the clean setting and matching it on the
#: saturating one are different achievements.
FBITS_SMALL = 8
FBITS_LARGE = 12
FBITS_TEST = (FBITS_SMALL, FBITS_LARGE)

#: Cases per setting, so 2 * NSAMP rows in all.  Large enough that a width
#: mistake which only bites on large inputs is caught, small enough that the
#: simulation is over in seconds.
NSAMP = 100

#: Seed for the case generator.
#:
#: This is *not* what makes the Python and SystemVerilog stages agree -- svsim
#: reads the vectors/cubic_py.csv that pysim wrote, inputs and expected answer
#: together, so whatever cases pysim chose are the cases the hardware is run
#: against.  It is here so that a score is reproducible.  With a fresh draw
#: every run, a design that is wrong on a rare input passes one invocation and
#: fails the next, and "case 37 disagrees" would not name the same case on your
#: machine as on anybody else's.
VECTOR_SEED = 20260917

#: Where x and the coefficients are drawn from.  The x range is what makes the
#: two settings differ: |x| up to 2 means x**3 reaches 8, which needs four
#: integer bits above the sign, and Q(16,12) has three.
X_LO, X_HI = -2.0, 2.0
A_LO, A_HI = -4.0, 4.0

#: Relative MSE a correct model may show at FBITS_SMALL.  Pure quantization
#: noise at 8 fractional bits over this input range measures 7.0e-6 -- that is
#: the reference solution's number, not an estimate -- so this leaves a correct
#: answer a seven-fold margin while staying four orders of magnitude below the
#: 7.8e-2 the saturating setting produces.  A shift that is off by one is worth
#: far more than the gap either way.
MSE_TOL_SMALL = 5e-5

#: How far past MSE_TOL_SMALL credit runs out.  An answer at ten times the
#: tolerance scores zero, and the credit falls linearly in between -- so a model
#: that is nearly right is told it is nearly right rather than simply failed.
MSE_CREDIT_SPAN = 10.0

#: The relative MSE at FBITS_LARGE has to be *at least* this, or the saturation
#: the lab is about did not happen.  A correct model measures 7.8e-2 here, so
#: this is an eight-fold margin below it.
#: The check is a floor rather than a ceiling on purpose: at this setting a
#: small error means the model is not reproducing the overflow, which is the one
#: behaviour the SystemVerilog has to match exactly.
MSE_FLOOR_LARGE = 1e-2

#: How closely a student's own measurement must match the true value for their
#: measuring code to count as correct.  Both sides compute this in float64 from
#: the same inputs, so the only difference should be the order of the additions.
MSE_TOL = 1e-12

#: Points for the x values the figure is drawn over -- a smooth sweep rather
#: than the random cases, because saturation is a shape and a scatter of a
#: hundred unordered points does not show a shape.
NPLOT = 200

#: The coefficients the figure's curve uses.  Fixed, so every student's figure
#: is the same picture and can be compared against the one on the lab page.
A_PLOT = (2.0, -0.5, -3.0)


def to_fixed(values: np.ndarray, fbits: int) -> np.ndarray:
    """Real values to their ``Q(., fbits)`` integers.

    ``cubic_model.py`` ships a copy of this, unredacted, because the student
    needs it too.  The grader keeps its own so that a submission which breaks
    the given helper -- editing outside the TODO is not forbidden, only
    unwise -- still gets scored against the cases everyone else was scored
    against, instead of halting the build with a traceback.
    """
    return np.round(np.asarray(values, dtype=np.float64) * (1 << fbits)).astype(np.int64)


def to_real(ints: np.ndarray, fbits: int) -> np.ndarray:
    """``Q(., fbits)`` integers back to real values.  See :func:`to_fixed`."""
    return np.asarray(ints, dtype=np.float64) / (1 << fbits)


def make_vectors(nsamp: int = NSAMP, seed: int = VECTOR_SEED) -> pd.DataFrame:
    """The lab's test cases: the same real problems, posed at both settings.

    One draw of ``x`` and ``a`` is used for every setting, so a row at
    ``fbits=8`` and the row at ``fbits=12`` with the same index are the same
    polynomial at the same point.  That is what makes the two settings
    comparable rather than merely two unrelated test sets.

    Drawn from a seeded generator, so every run of the lab -- yours, ours, and
    the one behind whatever score Gradescope shows -- uses the same cases.
    """
    rng = np.random.default_rng(seed)
    x = rng.uniform(X_LO, X_HI, nsamp)
    a = rng.uniform(A_LO, A_HI, (nsamp, 3))
    y = a[:, 0] + a[:, 1] * x + a[:, 2] * x**2 + x**3

    frames = []
    for fbits in FBITS_TEST:
        aint = to_fixed(a, fbits)
        frames.append(pd.DataFrame({
            "fbits": np.full(nsamp, fbits, dtype=np.int64),
            "xint": to_fixed(x, fbits),
            "aint0": aint[:, 0],
            "aint1": aint[:, 1],
            "aint2": aint[:, 2],
            "y": y,
        }))
    return pd.concat(frames, ignore_index=True)


def load_student_module(source_dir: Path, name: str):
    """Import one of the student's modules by path, fresh, whatever the working directory.

    By path rather than by name because the lab is a directory of scripts, not
    an installed package -- and freshly each time so that a rebuild in the same
    process picks up an edit instead of a cached module.
    """
    path = Path(source_dir) / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Stage 1 -- the Python fixed-point model
# ---------------------------------------------------------------------------

def run_model(fn, cases: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, str]:
    """Call the student's ``cubic_fixed`` once per setting.

    Returns ``(yint, ok, failure)``: the fixed-point outputs, a mask of the rows
    that produced a usable integer at all, and the first thing that went wrong.

    Per setting rather than all-or-nothing because "it worked at 8 fractional
    bits and broke at 12" is the most likely way for this lab to go wrong, and a
    student who gets one of the two should be told which.
    """
    yint = np.zeros(len(cases), dtype=np.int64)
    ok = np.zeros(len(cases), dtype=bool)
    failure = ""

    for fbits in FBITS_TEST:
        rows = (cases["fbits"].to_numpy() == fbits)
        block = cases[rows]
        aint = block[["aint0", "aint1", "aint2"]].to_numpy(dtype=np.int64)

        try:
            value = fn(block["xint"].to_numpy(dtype=np.int64), aint, WID, int(fbits))
        except Exception as exc:  # noqa: BLE001 -- any student error is a zero, not a crash
            if not failure:
                failure = (f"cubic_fixed raised {type(exc).__name__} at "
                           f"fbits={fbits}: {exc}")
            continue

        if value is None:
            if not failure:
                failure = ("cubic_fixed returned None — it has no `return` statement "
                           "yet. Open cubic_model.py and look for the TODO.")
            continue

        value = np.asarray(value).ravel()
        if value.size != int(rows.sum()):
            if not failure:
                failure = (f"cubic_fixed returned {value.size} values at fbits={fbits}; "
                           f"{int(rows.sum())} inputs were given. It must return one "
                           f"output per input.")
            continue

        yint[rows] = value.astype(np.int64)
        ok[rows] = True

    return yint, ok, failure


def check_model(cases: pd.DataFrame, yint: np.ndarray, ok: np.ndarray) -> Checks:
    """Score the fixed-point model on the two things it has to get right.

    It has to stay **inside its registers** -- a Q(16, F) value that does not fit
    in sixteen bits is not a Q(16, F) value, and the SystemVerilog has no way to
    produce one -- and at the setting where the arithmetic fits, it has to still
    **be the polynomial**.  The saturating setting is not scored for accuracy
    here: being inaccurate is what it is *for*, and how faithfully it saturates
    is svsim's question, where there is something to compare against.
    """
    checks = Checks()
    n = len(cases)
    fbits = cases["fbits"].to_numpy(dtype=np.int64)
    y = cases["y"].to_numpy(dtype=np.float64)

    range_label = f"Every output fits in {WID} bits"
    track_label = f"At F={FBITS_SMALL} your fixed point tracks the float"

    n_missing = int((~ok).sum())
    checks.that(n_missing == 0, 3, f"Produced an output for all {n} cases",
                f"{n_missing} of {n} cases produced no usable value")

    if not ok.any():
        note = "no outputs were produced, so there is nothing to check"
        checks.zero(3, range_label, note)
        checks.zero(4, track_label, note)
        return checks

    # The untouched template returns zeros.  Detected explicitly, because a
    # constant zero sits comfortably inside sixteen bits and would otherwise
    # collect the range check's three points for implementing nothing.
    produced = yint[ok]
    if int(np.unique(produced).size) == 1:
        note = (f"every case returned {int(produced[0])}, so your result does not "
                f"depend on x or a — open cubic_model.py and look for the TODO")
        checks.zero(3, range_label, note)
        checks.zero(4, track_label, note)
        return checks

    # --- did it stay in the register? ----------------------------------------
    lo, hi = -(1 << (WID - 1)), (1 << (WID - 1)) - 1
    outside = ok & ((yint < lo) | (yint > hi))
    note = ""
    if outside.any():
        first = int(np.flatnonzero(outside)[0])
        note = (f"{int(outside.sum())} of {n} outputs are outside {lo} to {hi}; the "
                f"first is case {first} at fbits={fbits[first]}, which returned "
                f"{yint[first]} — saturate after every product and after the final "
                f"sum, or the hardware cannot hold what your model produced")
    checks.fraction(1.0 - float(outside.mean()), 3, range_label, note)

    # --- at the clean setting, is it still the polynomial? --------------------
    #
    # Scored only at FBITS_SMALL.  At FBITS_LARGE a large error is the correct
    # answer, so scoring accuracy there would penalise a model for doing what
    # the lab set out to demonstrate.
    small = ok & (fbits == FBITS_SMALL)
    if not small.any():
        checks.zero(4, track_label, f"no usable outputs at fbits={FBITS_SMALL}")
        return checks

    yfix = yint[small] / float(1 << FBITS_SMALL)
    mse = float(np.mean((y[small] - yfix) ** 2) / np.mean(y[small] ** 2))
    excess = max(0.0, (mse - MSE_TOL_SMALL) / (MSE_CREDIT_SPAN * MSE_TOL_SMALL))
    checks.fraction(1.0 - excess, 4, track_label,
                    f"the relative MSE is {mse:.3e}, against a target of "
                    f"{MSE_TOL_SMALL:.1e} — at {FBITS_SMALL} fractional bits nothing "
                    f"should be saturating, so an error this size means a shift or a "
                    f"width is wrong rather than that the format is too coarse")
    return checks


@dataclass(kw_only=True)
class PySimStep(GradedStep):
    description = "Run your Python cubic at both settings and check what it produced."
    points = 10.0
    outputs = {"py_vectors": Path("vectors/cubic_py.csv")}
    consumes = ["cubic_model_src"]

    def evaluate(self, config: BuildConfig, **_) -> GradeResult:
        root = Path(config.root_dir)
        vectors = root / "vectors/cubic_py.csv"
        cases = make_vectors()
        yint = np.zeros(len(cases), dtype=np.int64)
        ok = np.zeros(len(cases), dtype=bool)
        failure = ""

        # Importing is inside the try as well: a file with a syntax error cannot
        # be loaded at all, and that has to score zero rather than take the build
        # down and leave you with no submission.
        try:
            model = load_student_module(root, "cubic_model")
            yint, ok, failure = run_model(model.cubic_fixed, cases)
        except Exception as exc:  # noqa: BLE001 -- any student error is a zero, not a crash
            failure = f"cubic_model.py raised {type(exc).__name__}: {exc}"

        # Written even when nothing was produced, so the next stages have a file
        # to read and can report a score instead of failing on a missing input.
        # The first six columns are also the testbench's $fscanf format -- change
        # the order and you must change tb_cubic.sv.
        vectors.parent.mkdir(parents=True, exist_ok=True)
        out = cases.copy()
        out["yint"] = yint
        out["yfix"] = yint / (1 << cases["fbits"].to_numpy(dtype=np.int64)).astype(float)
        out = out[["fbits", "xint", "aint0", "aint1", "aint2", "yint", "y", "yfix"]]
        out.to_csv(vectors, index=False)

        checks = check_model(cases, yint, ok)
        if failure:
            checks.note(failure)
        return checks.result(py_vectors=vectors)


# ---------------------------------------------------------------------------
# Stage 2 -- measuring what the format cost, before any hardware exists
# ---------------------------------------------------------------------------

def true_mse_by_fbits(table: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """``(widths, mse)`` -- the relative MSE of each setting, from the truth.

    Written as a groupby rather than as the mask-per-setting loop a student
    would reach for.  The grader has to compute the same answer as the
    submission it is grading, and this file ships whole -- so where the two
    would otherwise be the same lines of code, the grader takes the other route.
    """
    frame = pd.DataFrame({
        "fbits": table["fbits"].to_numpy(dtype=np.int64),
        "sqerr": (table["y"].to_numpy(dtype=np.float64)
                  - table["yfix"].to_numpy(dtype=np.float64)) ** 2,
        "sqref": table["y"].to_numpy(dtype=np.float64) ** 2,
    })
    grouped = frame.groupby("fbits")[["sqerr", "sqref"]].mean().sort_index()
    return (grouped.index.to_numpy(dtype=np.int64),
            (grouped["sqerr"] / grouped["sqref"]).to_numpy(dtype=np.float64))


def check_evaluation(table: pd.DataFrame, reported_all: float,
                     reported_widths: np.ndarray,
                     reported_mse: np.ndarray) -> Checks:
    """Score the student's measurements against the truth, and the design against both.

    Each measurement is worth two things, and they are different questions:
    *can you measure it* (the code) and *did the format do what the theory said*
    (the design).  A correct measurement of a model that never saturates earns
    the first and not the second, which is the distinction this stage exists to
    teach.
    """
    checks = Checks()
    y = table["y"].to_numpy(dtype=np.float64)
    yfix = table["yfix"].to_numpy(dtype=np.float64)

    # --- can you measure it? -------------------------------------------------
    mse_label = "Your rel_mse is correct"
    truth_all = float(np.mean((y - yfix) ** 2) / np.mean(y ** 2))
    checks.that(abs(float(reported_all) - truth_all) <= MSE_TOL, 3, mse_label,
                f"over all the cases you reported {reported_all:.6e}; the true "
                f"value is {truth_all:.6e}")

    split_label = "Your mse_by_fbits is correct"
    widths, truth = true_mse_by_fbits(table)
    reported_widths = np.asarray(reported_widths).ravel()
    reported_mse = np.asarray(reported_mse, dtype=np.float64).ravel()

    if not np.array_equal(reported_widths, widths):
        checks.zero(3, split_label,
                    f"you reported widths {list(reported_widths)}; the cases cover "
                    f"{list(widths)} — return one entry per distinct fbits, in "
                    f"increasing order")
    elif reported_mse.shape != truth.shape:
        checks.zero(3, split_label,
                    f"you returned {reported_mse.size} values for {truth.size} widths")
    else:
        gap = np.abs(reported_mse - truth)
        first = int(np.argmax(gap))
        checks.that(bool(gap.max() <= MSE_TOL), 3, split_label,
                    f"at fbits={widths[first]} you reported {reported_mse[first]:.6e} "
                    f"and the true value is {truth[first]:.6e}")

    # --- did the format do what the theory said? -----------------------------
    #
    # Scored from the true MSEs, not the reported ones: a student whose
    # measuring code is wrong should lose the measurement points, not have their
    # model judged by a broken instrument.
    trade_label = (f"F={FBITS_SMALL} approximates the float and F={FBITS_LARGE} "
                   f"saturates")
    by_width = dict(zip(widths.tolist(), truth.tolist()))
    small, large = by_width.get(FBITS_SMALL), by_width.get(FBITS_LARGE)

    if small is None or large is None:
        checks.zero(2, trade_label,
                    f"the vectors do not cover both settings — expected fbits "
                    f"{FBITS_SMALL} and {FBITS_LARGE}, found {list(widths)}")
    elif small > MSE_TOL_SMALL:
        checks.zero(2, trade_label,
                    f"at F={FBITS_SMALL} the relative MSE is {small:.3e}, past the "
                    f"{MSE_TOL_SMALL:.1e} expected — nothing should saturate at this "
                    f"setting, so this is a width or a shift, not the format")
    elif large < MSE_FLOOR_LARGE:
        checks.zero(2, trade_label,
                    f"at F={FBITS_LARGE} the relative MSE is only {large:.3e} — "
                    f"x**3 does not fit in {WID - FBITS_LARGE} integer bits over this "
                    f"input range, so a small error here means your model is not "
                    f"saturating where the hardware will")
    else:
        checks.that(True, 2, trade_label)

    return checks


@dataclass(kw_only=True)
class PyEvalStep(GradedStep):
    description = "Measure what the fixed-point format cost — before building any hardware."
    points = 10.0
    outputs = {"eval_figure": Path("results/cubic_fixp.png")}
    consumes = ["cubic_eval_src", "py_vectors"]

    def evaluate(self, config: BuildConfig, py_vectors: Path, **_) -> GradeResult:
        root = Path(config.root_dir)
        table = pd.read_csv(py_vectors)

        reported_all = 0.0
        reported_widths: np.ndarray = np.zeros(0, dtype=np.int64)
        reported_mse: np.ndarray = np.zeros(0, dtype=np.float64)
        failure = ""

        try:
            ev = load_student_module(root, "cubic_eval")
            reported_all = float(ev.rel_mse(
                table["y"].to_numpy(dtype=np.float64),
                table["yfix"].to_numpy(dtype=np.float64)))
            reported_widths, reported_mse = ev.mse_by_fbits(
                table["fbits"].to_numpy(dtype=np.int64),
                table["y"].to_numpy(dtype=np.float64),
                table["yfix"].to_numpy(dtype=np.float64))
        except Exception as exc:  # noqa: BLE001 -- any student error is a zero, not a crash
            failure = f"cubic_eval.py raised {type(exc).__name__}: {exc}"

        checks = check_evaluation(table, reported_all, reported_widths, reported_mse)
        if failure:
            checks.note(failure)

        # Only the figure's *existence* is scored.  Judging a plot mechanically
        # is a poor trade -- the checks that could be automated are the ones a
        # student can satisfy without drawing anything worth looking at -- so the
        # file goes into the submission instead, where a person can read it.
        figure = root / "results/cubic_fixp.png"
        # Removed first, so a figure left over from an earlier run cannot earn
        # the points for code that no longer draws one.
        figure.unlink(missing_ok=True)
        try:
            xplot, yplot, curves = self._plot_data(root)
            ev = load_student_module(root, "cubic_eval")
            ev.plot_fixed_vs_float(xplot, yplot, curves, figure)
        except Exception as exc:  # noqa: BLE001 -- a broken plot costs its own points, no more
            checks.note(f"plot_fixed_vs_float raised {type(exc).__name__}: {exc}")

        drew = figure.exists() and figure.stat().st_size > 0
        checks.that(drew, 2, "You produced a float-against-fixed figure",
                    f"no figure was written to {figure.name} — plot_fixed_vs_float "
                    f"must save one, and it is part of what you submit")
        if not drew:
            # The artifact is declared, so something has to be there for the
            # submission step to bundle.  A placeholder says plainly that no
            # plot was drawn rather than leaving a confusing gap.
            _placeholder_figure(figure)

        result = checks.result(eval_figure=figure)
        # Which file was written has to match what the check just said.  Saying
        # "figure written to ..." directly under "no figure was written" reads
        # as a bug in the grader, and a student cannot tell which half to trust.
        where = figure.relative_to(root)
        result.feedback.append(
            f"  figure written to {where}" if drew
            else f"  a placeholder was written to {where} so your submission is "
                 f"still complete")
        return result

    @staticmethod
    def _plot_data(root: Path) -> tuple[np.ndarray, np.ndarray, dict[int, np.ndarray]]:
        """The smooth sweep the figure is drawn over, run through the student's model.

        A sweep rather than the random cases: saturation is a *shape* -- flat
        shoulders where the cubic term ran out of register -- and a scatter of a
        hundred unordered points does not have a shape.
        """
        model = load_student_module(root, "cubic_model")
        xplot = np.linspace(X_LO * 2, X_HI * 2, NPLOT)
        aplot = np.array(A_PLOT)[None, :].repeat(NPLOT, axis=0)
        yplot = aplot[:, 0] + aplot[:, 1] * xplot + aplot[:, 2] * xplot**2 + xplot**3

        curves = {}
        for fbits in FBITS_TEST:
            yint = model.cubic_fixed(to_fixed(xplot, fbits), to_fixed(aplot, fbits),
                                     WID, fbits)
            curves[fbits] = to_real(np.asarray(yint), fbits)
        return xplot, yplot, curves


def _placeholder_figure(path: Path) -> None:
    """A stand-in PNG, so the declared artifact exists when no plot was drawn.

    Deliberately built with ``plt.figure`` rather than ``plt.subplots``, and
    with no axis calls: those lines would be byte-identical to ones inside a
    solution block in ``cubic_eval.py``, and labkit's leak guard -- rightly --
    cannot tell generic matplotlib boilerplate from a leaked answer.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(8.4, 4.0))
    fig.text(0.5, 0.5, "no comparison plot was drawn", ha="center", va="center",
             color="0.4")
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Stage 3 -- the SystemVerilog
# ---------------------------------------------------------------------------

#: The names of the three checks stage 3 makes.  Kept beside compare_hardware
#: so that the function's return keys and the step's point weights cannot drift
#: apart silently.
MATCH_SMALL = "match_small"
MATCH_LARGE = "match_large"
MATCH_RAILS = "match_rails"


def saturating_rows(table: pd.DataFrame, fbits: int) -> np.ndarray:
    """Mask of the ``fbits`` rows whose Python output was clamped to a rail.

    "Clamped" is read off the value itself: an output sitting exactly on the
    largest or smallest number a signed ``WID``-bit register holds got there by
    saturating, because the polynomial has no reason to land precisely there
    otherwise.  Read off the value rather than recomputed, because recomputing
    would mean putting a reference implementation of ``cubic_fixed`` into this
    file -- which ships whole, to the students.
    """
    lo, hi = -(1 << (WID - 1)), (1 << (WID - 1)) - 1
    yint = table["yint"].to_numpy(dtype=np.int64)
    return ((table["fbits"].to_numpy(dtype=np.int64) == fbits)
            & ((yint == lo) | (yint == hi)))


def compare_hardware(py_path: Path, sv_path: Path) -> dict[str, tuple[float, str]]:
    """Score the simulation against the Python model.

    Returns ``check name -> (fraction earned, note)`` for the three checks named
    above.  Three rather than one because they are different achievements, and
    a single "how many cases matched" number would price them wrongly.

    The reason for the third is worth stating plainly.  At F=12 only about
    fifteen cases in a hundred come out differently if the saturation is left
    out altogether -- so a design that ignores overflow entirely still matches
    85% of the setting that exists to test overflow, and a proportional score
    would charge it almost nothing.  ``match_rails`` closes that: it looks only
    at the cases the Python model actually clamped, and it is all or nothing.
    """
    py = pd.read_csv(py_path)
    sv = pd.read_csv(sv_path)

    def all_zero(msg: str) -> dict[str, tuple[float, str]]:
        return {MATCH_SMALL: (0.0, msg), MATCH_LARGE: (0.0, msg),
                MATCH_RAILS: (0.0, msg)}

    if len(py) == 0:
        return all_zero("your Python model produced no cases, so there is "
                        "nothing to match")

    # Consistency between two languages is only evidence when there is something
    # to be consistent about.  The unedited template returns zero everywhere and
    # an unfinished module drives zero, so they agree perfectly while
    # implementing nothing -- this is the check that stops an untouched
    # submission collecting full marks here.
    if int(np.unique(py["yint"].to_numpy()).size) <= 1:
        return all_zero("your Python model returned the same value for every case, "
                        "so a matching simulation proves nothing — fix "
                        "cubic_model.py first")

    if len(sv) != len(py):
        # The usual cause is the testbench's watchdog: it prints a diagnosis and
        # calls $finish, so the simulation *succeeds* and simply stops early.
        # That is deliberate -- $fatal leaves xsim alive on Windows and stalls
        # the build for ten minutes -- but it means a short file, not an error,
        # is what reaches this function.
        return all_zero(
            f"the simulation recorded {len(sv)} cases but your Python model "
            f"produced {len(py)} — it stopped early. The simulator's own output, "
            f"above and in sim/cubic/logs/xsim.log, says where")

    want = py["yint"].to_numpy(dtype=np.int64)
    got = sv["y_dut"].to_numpy(dtype=np.int64)
    same = want == got

    def describe(rows: np.ndarray) -> tuple[float, str]:
        """``(fraction matching, note)`` over the rows in *rows*."""
        if not rows.any():
            return 0.0, "the simulation recorded no cases here"
        hit = same[rows]
        if hit.all():
            return 1.0, ""
        idx = int(np.flatnonzero(rows)[int(np.flatnonzero(~hit)[0])])
        return float(hit.mean()), (
            f"{int((~hit).sum())} of {int(rows.sum())} cases differ; the first is "
            f"row {idx}, where x={py['xint'][idx]}, a0={py['aint0'][idx]}, "
            f"a1={py['aint1'][idx]}, a2={py['aint2'][idx]} — Python says "
            f"{py['yint'][idx]} and the simulation says {sv['y_dut'][idx]}")

    fbits = sv["fbits"].to_numpy(dtype=np.int64)
    out = {MATCH_SMALL: describe(fbits == FBITS_SMALL),
           MATCH_LARGE: describe(fbits == FBITS_LARGE)}

    # The rail cases, all or nothing.
    rails = saturating_rows(py, FBITS_LARGE)
    if not rails.any():
        # No clamped outputs at the setting where the arithmetic overflows means
        # the Python model is not saturating either.  Scoring the hardware
        # against it would be scoring one unsaturated model against another and
        # calling the agreement a pass -- the same trap as the constant model
        # above, one level down.
        out[MATCH_RAILS] = (0.0,
            f"none of your F={FBITS_LARGE} outputs are at the ±{1 << (WID - 1)} "
            f"rails, so your Python model is not saturating — at this setting "
            f"x**3 does not fit, and something has to clamp. Fix cubic_model.py "
            f"first; there is nothing here for the hardware to match yet")
    else:
        hit = same[rails]
        out[MATCH_RAILS] = (1.0 if hit.all() else 0.0, "" if hit.all() else (
            f"{int((~hit).sum())} of the {int(rails.sum())} cases your model "
            f"clamped came back differently from the simulation. This check is "
            f"all or nothing: these are the cases the F={FBITS_LARGE} setting "
            f"exists to test, and they are the ones a design that ignores "
            f"overflow gets wrong"))

    return out


@dataclass(kw_only=True)
class SvSimStep(GradedStep):
    description = "Simulate your SystemVerilog cubic and compare it with your Python model."
    points = 10.0
    outputs = {"sv_vectors": Path("vectors/cubic_sv.csv")}
    consumes = ["cubic_sv_src", "py_vectors"]

    #: What each check is worth, and why the split is uneven.
    #:
    #: Most of the credit is on the clean setting, because that is where getting
    #: the shifts and the pipeline right is demonstrated, and it is the bulk of
    #: the work.  The F=12 setting carries little as a proportion -- only about
    #: fifteen cases in a hundred there even depend on the saturation, so a
    #: proportional score over it barely moves -- and carries the rest as the
    #: all-or-nothing rails check, which is the one a design that ignores
    #: overflow cannot pass by getting most of the other cases right.
    weights: ClassVar[dict[str, float]] = {
        MATCH_SMALL: 6.0, MATCH_LARGE: 2.0, MATCH_RAILS: 2.0,
    }

    #: What the student is told each check was about.
    labels: ClassVar[dict[str, str]] = {
        MATCH_SMALL: f"SystemVerilog matches your Python at F={FBITS_SMALL}",
        MATCH_LARGE: f"SystemVerilog matches your Python at F={FBITS_LARGE}",
        MATCH_RAILS: "Every case your model clamped, the hardware clamps too",
    }

    def evaluate(self, config: BuildConfig, **_) -> GradeResult:
        from waveflow.scripts.sv_sim import SvSimError, run_sv_sim

        root = Path(config.root_dir)
        checks = Checks()
        sv_path = root / "vectors/cubic_sv.csv"

        def zero_everything(note: str) -> GradeResult:
            for key, points in self.weights.items():
                checks.zero(points, self.labels[key], note)
            return checks.result(sv_vectors=_empty_sv_vectors(sv_path))

        # The simulation is run here rather than by a separate SvSimStep so that
        # a compile error, or a watchdog timeout, becomes a scored zero with the
        # tool output attached.  As its own DAG node it would raise, halt the
        # build, and leave you with a traceback and no submission file.
        try:
            run_sv_sim(
                [root / "cubic.sv"], root / "tb_cubic.sv",
                sim_dir=root / "sim/cubic",
                plusargs={"vecdir": root / "vectors"},
                capture_output=True,
            )
        except SvSimError as exc:
            return zero_everything(f"the simulation did not run: {exc}".rstrip())

        if not sv_path.exists():
            return zero_everything("the simulation finished but wrote no output file")

        scored = compare_hardware(root / "vectors/cubic_py.csv", sv_path)
        for key, points in self.weights.items():
            frac, note = scored.get(key, (0.0, "this check was not run"))
            checks.fraction(frac, points, self.labels[key], note)
        return checks.result(sv_vectors=sv_path)


def _empty_sv_vectors(path: Path) -> Path:
    """Write a header-only cubic_sv.csv, so the failure path still has its artifact.

    ``GradeReportStep`` refuses to bundle a file that is not there, so a student
    whose simulation never ran would otherwise get no submission zip at all --
    which is exactly the student who most needs to submit what they have.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("fbits,xint,aint0,aint1,aint2,yint,y_dut\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The ungraded stage -- one case, with the pipeline registers on show
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class SvSingStep(BuildStep):
    """Run ``tb_cubic_sing.sv``: one hand-picked case, printed cycle by cycle.

    A DAG step rather than a bare ``sv_sim`` command line so that everything in
    this lab is run the same way, and so the DAG knows it has to be redone when
    ``cubic.sv`` changes.  It is not a :class:`GradedStep` and nothing downstream
    consumes it: no step in the ``submit`` chain depends on it, so
    ``python cubic_build.py`` skips it entirely and you run it when you want it.

    It is the tool for the moment ``svsim`` reports two hundred disagreements.
    A count does not tell you which product overflowed; the pipeline registers
    printed for one case you chose yourself do.
    """

    description = "Run one hand-picked case and print the pipeline registers (ungraded)."
    params: ClassVar[dict] = {}
    consumes = ["cubic_sv_src", "cubic_sing_tb_src"]
    produces: ClassVar[dict] = {"sing_log": Path("sim/sing/logs/xsim.log")}

    def run(self, config: BuildConfig, **_) -> dict[str, Any]:
        from waveflow.scripts.sv_sim import SvSimError, run_sv_sim

        root = Path(config.root_dir)
        try:
            run_sv_sim(
                [root / "cubic.sv"], root / "tb_cubic_sing.sv",
                sim_dir=root / "sim/sing",
                capture_output=True,
            )
        except SvSimError as exc:
            # This one does raise.  It is not on the submission path, so halting
            # costs nothing, and a student running it is asking to see what the
            # simulator said rather than to be given a score.
            raise RuntimeError(
                f"tb_cubic_sing.sv did not run.\n{exc}\n"
                f"The simulator's output is in sim/sing/logs/.") from exc

        log = root / "sim/sing/logs/xsim.log"
        print("    the case above is the one set at the top of tb_cubic_sing.sv — "
              "change it and re-run to try another")
        return {"sing_log": log}


# ---------------------------------------------------------------------------
# The graph
# ---------------------------------------------------------------------------

def lab_steps() -> tuple[list[StudentSourceStep], list[GradedStep], BuildStep]:
    """The student's four files, the three stages that grade them, and the spare.

    The graded stages are built together with the sources because each stage
    needs to know which files are *its* -- a stage whose files are all still the
    shipped template reports "not started" instead of a page of failed checks.
    """
    model_src = StudentSourceStep(artifact="cubic_model_src", path=Path("cubic_model.py"))
    eval_src = StudentSourceStep(artifact="cubic_eval_src", path=Path("cubic_eval.py"))
    sv_src = StudentSourceStep(artifact="cubic_sv_src", path=Path("cubic.sv"))
    # The single-case testbench is a student file too -- the expected value at
    # the top of it has to be recomputed to match whatever arithmetic you wrote
    # -- but nothing grades it, so it is not `starts_from` for any stage.
    sing_tb_src = StudentSourceStep(artifact="cubic_sing_tb_src",
                                    path=Path("tb_cubic_sing.sv"))

    return ([model_src, eval_src, sv_src, sing_tb_src],
            [PySimStep(name="pysim", title="Python fixed-point model",
                       starts_from=[model_src]),
             PyEvalStep(name="pyeval", title="Measuring the quantization error",
                        starts_from=[eval_src]),
             SvSimStep(name="svsim", title="SystemVerilog cubic",
                       starts_from=[sv_src])],
            SvSingStep(name="svsing"))


def graded_steps() -> list[GradedStep]:
    """The graded stages, in the order the submission reports them."""
    return lab_steps()[1]


def build_cubic_dag() -> BuildDag:
    dag = BuildDag()
    (model_src, eval_src, sv_src, sing_tb_src), (pysim, pyeval, svsim), svsing = lab_steps()

    dag.add(model_src)
    dag.add(pysim)

    dag.add(eval_src)
    dag.add(pyeval)

    dag.add(sv_src)
    dag.add(svsim)

    # Off the submission path on purpose: `--through submit` collects only what
    # its target depends on, so this runs when you ask for it and never
    # otherwise.  A single hand-picked case is a debugging aid, not evidence.
    dag.add(sing_tb_src)
    dag.add(svsing)

    # svsim does not consume pyeval's output, and no edge pretends otherwise --
    # the reason to measure the error before building hardware is a habit, not a
    # data dependency, and a DAG that lies about its dependencies is worth less
    # than the lesson.
    dag.add(GradeReportStep(
        name="submit", graded=[pysim, pyeval, svsim],
        # The comparison figure goes in the zip so it can be looked at.  It is
        # the one part of this lab whose quality a person can judge in a second
        # and a script cannot judge at all.
        bundle=[Path("cubic_model.py"), Path("cubic_eval.py"), Path("cubic.sv"),
                Path("vectors/cubic_py.csv"), Path("vectors/cubic_sv.csv"),
                Path("results/cubic_fixp.png")]))
    return dag


def main() -> None:
    run_graded_dag_cli(
        build_cubic_dag,
        graded_steps=graded_steps,
        description="cubic — Unit 3 lab: a monic cubic polynomial in fixed point.",
        default_through="submit",
        root_dir=_SOURCE_DIR,
    )


if __name__ == "__main__":
    main()
