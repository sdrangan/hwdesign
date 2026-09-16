"""subc — the Unit 2 lab build.

Three graded stages, run one at a time::

    python subc_build.py --list-steps-verbose   # what the stages are
    python subc_build.py --through pysim        # the golden model, scored
    python subc_build.py --through pyeval       # measure its error, scored
    python subc_build.py --through svsim        # the SystemVerilog, scored
    python subc_build.py                        # everything, then the submission zip
    python subc_build.py --grades               # your scores, without rebuilding

``pysim`` runs your Python divider over the lab's test cases and asks whether
the quotients meet the algorithm's error bound.  ``pyeval`` runs the measuring
code *you* wrote over those results and asks two different questions of it: is
your measurement right, and does the design actually converge the way the
theory says?  ``svsim`` then runs your SystemVerilog against the same cases and
checks it against your Python, case for case, on both the answer and the number
of clock cycles it took.

The order is the point.  You find out whether the algorithm converges while it
is still Python, where a fix costs an edit -- not after it is a state machine,
where it costs a day.

YOU DO NOT NEED TO EDIT THIS FILE.  Your work goes in ``subc_divide.py``,
``subc_eval.py``, ``subc_divide.sv`` and ``tb_subc_divide.sv``.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from waveflow.build.build import BuildConfig, BuildDag

from hwdesign.grading import (
    Checks, GradeReportStep, GradedStep, GradeResult, StudentSourceStep,
    run_graded_dag_cli,
)

_SOURCE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# The lab's specification
#
# These live here rather than in subc_divide.py so that the grader and the
# simulator agree on them no matter what a submission does to its own
# constants -- and so that a file which fails to import at all can still be
# scored against the right numbers instead of crashing the build.
# ---------------------------------------------------------------------------

#: How many (a, b, nbits) cases to run.  Large enough that a divider which is
#: wrong only on some inputs is caught, small enough that the simulation is
#: over in seconds.
NTEST = 200

#: Seed for the case generator.
#:
#: This is *not* what makes the Python and SystemVerilog stages agree -- svsim
#: reads the vectors/tv_python.csv that pysim wrote, inputs and expected answer
#: together, so whatever cases pysim chose are the cases the hardware is run
#: against.  It is here so that a score is reproducible.  With a fresh draw
#: every run, a divider that is wrong on a rare input passes one invocation and
#: fails the next, and "case 37 disagrees" would not name the same case on your
#: machine as on anybody else's.
VECTOR_SEED = 20260915

#: Range the divisor is drawn from.  The lower bound keeps b away from values
#: so small that a/b is a coarse grid of fractions the divider can hit exactly
#: by accident.
B_MIN, B_MAX = 16, 1 << 16

#: Range of the per-case fractional width.  It varies from case to case on
#: purpose: the SystemVerilog module takes nbits as a runtime *port* rather
#: than a parameter, and a state machine that ignores it still passes a test
#: set where every case asks for the same width.
NBITS_MIN, NBITS_MAX = 4, 16

#: How closely a student's own error measurement must match the true value for
#: their measuring code to count as correct.  This is arithmetic on values both
#: sides compute in float64, so the only difference should be rounding.
ERR_TOL = 1e-12

#: Extra clock cycles a correct design may take beyond its nbits iterations.
#: The reference machine spends one cycle accepting the inputs in IDLE, nbits
#: in RUN, and one asserting outvalid in DONE.  Measured against the reference
#: in :func:`_latency_bound`, which is what this is checked against -- do not
#: change one without re-running the solution.
LATENCY_MARGIN = 2


def _latency_bound(nbits: np.ndarray) -> np.ndarray:
    """The most clock cycles a case may take, as the testbench counts them."""
    return nbits + LATENCY_MARGIN


def make_vectors(ntest: int = NTEST, seed: int = VECTOR_SEED) -> pd.DataFrame:
    """The lab's test cases: ``a``, ``b`` and ``nbits``, with ``0 <= a < b``.

    Drawn from a seeded generator, so every run of the lab -- yours, ours, and
    the one behind whatever score Gradescope shows -- uses the same cases.
    """
    rng = np.random.default_rng(seed)
    b = rng.integers(B_MIN, B_MAX, size=ntest, dtype=np.int64)
    # rng.random() is in [0, 1), so a < b holds for every case, which is the
    # precondition subc_divide is allowed to assume (and does assert).
    a = (rng.random(ntest) * b).astype(np.int64)
    nbits = rng.integers(NBITS_MIN, NBITS_MAX + 1, size=ntest, dtype=np.int64)
    return pd.DataFrame({"a": a, "b": b, "nbits": nbits})


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
# Stage 1 -- the Python golden model
# ---------------------------------------------------------------------------

def run_model(fn, cases: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, str]:
    """Call the student's divider once per case.

    Returns ``(z, ok, failure)``: the quotient numerators, a mask of the cases
    that produced a usable integer at all, and the first thing that went wrong.

    Case by case rather than all-or-nothing because "it raised on one input" and
    "it raised on every input" are different marks, and a student who handles
    197 of 200 cases should be told which three broke rather than scoring zero.
    """
    z = np.zeros(len(cases), dtype=np.int64)
    ok = np.zeros(len(cases), dtype=bool)
    failure = ""

    for i, row in enumerate(cases.itertuples(index=False)):
        try:
            value = fn(np.uint32(row.a), np.uint32(row.b), int(row.nbits))
        except Exception as exc:  # noqa: BLE001 -- any student error is a zero, not a crash
            if not failure:
                failure = (f"subc_divide raised {type(exc).__name__} on case {i} "
                           f"(a={row.a}, b={row.b}, nbits={row.nbits}): {exc}")
            continue

        if value is None:
            if not failure:
                failure = ("subc_divide returned None — it has no `return` "
                           "statement yet. Open subc_divide.py and look for the TODO.")
            continue

        z[i] = int(value)
        ok[i] = True

    return z, ok, failure


def check_quotients(cases: pd.DataFrame, z: np.ndarray, ok: np.ndarray) -> Checks:
    """Score the golden model on the algorithm's own error bound.

    The bound is one-sided, and that is the whole content of the algorithm:
    conditional subtraction only ever sets a quotient bit it has already paid
    for, so ``qhat`` never overshoots.  Checking ``|a/b - qhat| < ulp`` instead
    would accept a divider that rounds the wrong way.
    """
    checks = Checks()
    a = cases["a"].to_numpy(dtype=np.float64)
    b = cases["b"].to_numpy(dtype=np.float64)
    nbits = cases["nbits"].to_numpy(dtype=np.int64)
    n = len(cases)

    bound_label = "Your quotient meets the error bound"
    vary_label = "Your z actually depends on a and b"

    n_missing = int((~ok).sum())
    checks.that(n_missing == 0, 3, f"Produced a quotient for all {n} test cases",
                f"{n_missing} of {n} cases produced no usable value")

    produced = z[ok]
    if produced.size == 0:
        note = "no quotients were produced, so there is nothing to check"
        checks.zero(4, bound_label, note)
        checks.zero(3, vary_label, note)
        return checks

    # The untouched template returns a constant.  Detected explicitly, because
    # a constant z passes the error bound on every case whose true quotient is
    # smaller than one ulp -- at nbits=4 that is one input pair in sixteen, so
    # the bound check on its own pays real points for implementing nothing.
    if int(np.unique(produced).size) == 1:
        note = (f"every case returned z = {int(produced[0])}, so your result does "
                f"not depend on a or b — open subc_divide.py and look for the TODO")
        # The bound check is zeroed too: a constant z has not met the bound, it
        # has dodged the question.  One note for both, so it is said once.
        checks.zero(4, bound_label, note)
        checks.zero(3, vary_label, note)
        return checks

    ulp = 1.0 / 2.0 ** nbits
    err = a / b - z * ulp
    within = ok & (err >= 0.0) & (err < ulp)

    note = ""
    if not within.all():
        first = int(np.flatnonzero(~within)[0])
        note = (f"{int((~within).sum())} of {n} cases are outside it; the first is "
                f"case {first}, where a={int(a[first])}, b={int(b[first])}, "
                f"nbits={nbits[first]} gave z={z[first]}, an error of "
                f"{err[first]:+.3e} against a bound of {ulp[first]:.3e}")
    checks.fraction(float(within.mean()), 4, bound_label, note)

    checks.that(True, 3, vary_label)
    return checks


@dataclass(kw_only=True)
class PySimStep(GradedStep):
    description = "Run your Python divider over the lab's cases and check the quotients."
    points = 10.0
    outputs = {"py_vectors": Path("vectors/tv_python.csv")}
    consumes = ["subc_divide_src"]

    def evaluate(self, config: BuildConfig, **_) -> GradeResult:
        root = Path(config.root_dir)
        vectors = root / "vectors/tv_python.csv"
        cases = make_vectors()
        z = np.zeros(len(cases), dtype=np.int64)
        ok = np.zeros(len(cases), dtype=bool)
        failure = ""

        # Importing is inside the try as well: a file with a syntax error cannot
        # be loaded at all, and that has to score zero rather than take the build
        # down and leave you with no submission.
        try:
            model = load_student_module(root, "subc_divide")
            z, ok, failure = run_model(model.subc_divide, cases)
        except Exception as exc:  # noqa: BLE001 -- any student error is a zero, not a crash
            failure = f"subc_divide.py raised {type(exc).__name__}: {exc}"

        # Written even when nothing was produced, so the next stages have a file
        # to read and can report a score instead of failing on a missing input.
        # The column order is also the testbench's $fscanf format -- change one
        # and you must change the other.
        vectors.parent.mkdir(parents=True, exist_ok=True)
        out = cases.copy()
        out["z"] = z
        out.to_csv(vectors, index=False)

        checks = check_quotients(cases, z, ok)
        if failure:
            checks.note(failure)
        return checks.result(py_vectors=vectors)


# ---------------------------------------------------------------------------
# Stage 2 -- measuring the error, before any hardware exists
# ---------------------------------------------------------------------------

def true_errors(cases: pd.DataFrame, z: np.ndarray) -> np.ndarray:
    """The signed approximation error ``a/b - z/2**nbits``, case by case."""
    a = cases["a"].to_numpy(dtype=np.float64)
    b = cases["b"].to_numpy(dtype=np.float64)
    nbits = cases["nbits"].to_numpy(dtype=np.int64)
    return a / b - z * (1.0 / 2.0 ** nbits)


def true_max_by_nbits(cases: pd.DataFrame, err: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(widths, worst)`` -- the largest absolute error seen at each ``nbits``.

    Written as a groupby rather than as the mask-per-width loop a student would
    reach for.  The grader has to compute the same answer as the submission it
    is grading, and this file ships whole -- so where the two would otherwise be
    the same lines of code, the grader takes the other route.
    """
    frame = pd.DataFrame({"nbits": cases["nbits"].to_numpy(dtype=np.int64),
                          "abs_err": np.abs(err)})
    grouped = frame.groupby("nbits")["abs_err"].max().sort_index()
    return grouped.index.to_numpy(dtype=np.int64), grouped.to_numpy(dtype=np.float64)


def check_evaluation(cases: pd.DataFrame, z: np.ndarray,
                     reported_err: np.ndarray,
                     reported_widths: np.ndarray,
                     reported_worst: np.ndarray) -> Checks:
    """Score the student's measurements against the truth, and the design against both.

    Each measurement is worth two things, and they are different questions:
    *can you measure it* (the code) and *is the answer what the theory promised*
    (the design).  A correct measurement of a divider that overshoots earns the
    first and not the second, which is the distinction this stage exists to
    teach.
    """
    checks = Checks()
    nbits = cases["nbits"].to_numpy(dtype=np.int64)
    truth = true_errors(cases, z)
    widths, worst = true_max_by_nbits(cases, truth)

    # --- can you measure it? -------------------------------------------------
    err_label = "Your quant_error is correct"
    reported_err = np.asarray(reported_err, dtype=np.float64).ravel()
    if reported_err.shape != truth.shape:
        checks.zero(3, err_label,
                    f"you returned {reported_err.size} values; {truth.size} were asked for")
    else:
        gap = np.abs(reported_err - truth)
        first = int(np.argmax(gap))
        checks.that(bool(gap.max() <= ERR_TOL), 3, err_label,
                    f"the worst disagreement is {gap.max():.3e}, at case {first}, "
                    f"where you reported {reported_err[first]:+.6e} and the true "
                    f"error is {truth[first]:+.6e}")

    max_label = "Your per-nbits worst case is correct"
    reported_widths = np.asarray(reported_widths).ravel()
    reported_worst = np.asarray(reported_worst, dtype=np.float64).ravel()
    if not np.array_equal(reported_widths, widths):
        checks.zero(3, max_label,
                    f"you reported widths {list(reported_widths)}; the cases cover "
                    f"{list(widths)} — return one entry per distinct nbits, in order")
    elif reported_worst.shape != worst.shape:
        checks.zero(3, max_label,
                    f"you returned {reported_worst.size} maxima for "
                    f"{worst.size} widths")
    else:
        gap = np.abs(reported_worst - worst)
        first = int(np.argmax(gap))
        checks.that(bool(gap.max() <= ERR_TOL), 3, max_label,
                    f"at nbits={widths[first]} you reported {reported_worst[first]:.6e} "
                    f"and the true worst case is {worst[first]:.6e}")

    # --- is the design what the theory promised? -----------------------------
    #
    # Scored from the true errors, not the reported ones: a student whose
    # measuring code is wrong should lose the measurement points, not have
    # their design judged by a broken instrument.
    bound_label = "The error is one-sided and below 2**-nbits"
    ulp = 1.0 / 2.0 ** nbits
    holds = (truth >= 0.0) & (truth < ulp)
    if not holds.all():
        first = int(np.flatnonzero(~holds)[0])
        side = "negative" if truth[first] < 0 else "too large"
        checks.zero(2, bound_label,
                    f"case {first} has an error of {truth[first]:+.3e} ({side}) "
                    f"against a bound of {ulp[first]:.3e} — the quotient should "
                    f"never overshoot a/b")
    else:
        checks.that(True, 2, bound_label)

    return checks


@dataclass(kw_only=True)
class PyEvalStep(GradedStep):
    description = "Measure your divider's error — does it converge? — before building hardware."
    points = 10.0
    outputs = {"eval_figure": Path("results/subc_error.png")}
    consumes = ["subc_eval_src", "py_vectors"]

    def evaluate(self, config: BuildConfig, py_vectors: Path, **_) -> GradeResult:
        root = Path(config.root_dir)
        table = pd.read_csv(py_vectors)
        cases = table[["a", "b", "nbits"]]
        z = table["z"].to_numpy(dtype=np.int64)

        reported_err = np.zeros(len(table), dtype=np.float64)
        reported_widths: np.ndarray = np.zeros(0, dtype=np.int64)
        reported_worst: np.ndarray = np.zeros(0, dtype=np.float64)
        failure = ""

        try:
            ev = load_student_module(root, "subc_eval")
            reported_err = np.asarray(ev.quant_error(
                cases["a"].to_numpy(), cases["b"].to_numpy(), z,
                cases["nbits"].to_numpy()), dtype=np.float64)
            reported_widths, reported_worst = ev.max_error_by_nbits(
                cases["nbits"].to_numpy(), reported_err)
        except Exception as exc:  # noqa: BLE001 -- any student error is a zero, not a crash
            failure = f"subc_eval.py raised {type(exc).__name__}: {exc}"

        checks = check_evaluation(cases, z, reported_err,
                                  reported_widths, reported_worst)
        if failure:
            checks.note(failure)

        # The figure plots what the student measured, not a recomputed set, so a
        # wrong measurement is visible rather than hidden by the plot.
        #
        # Only its *existence* is scored.  Judging a plot mechanically is a poor
        # trade -- the checks that could be automated are the ones a student can
        # satisfy without drawing anything worth looking at -- so the file goes
        # into the submission instead, where a person can read it.
        figure = root / "results/subc_error.png"
        # Removed first, so a figure left over from an earlier run cannot earn
        # the point for code that no longer draws one.
        figure.unlink(missing_ok=True)
        try:
            ev = load_student_module(root, "subc_eval")
            ev.plot_error(reported_widths, reported_worst, figure)
        except Exception as exc:  # noqa: BLE001 -- a broken plot costs its own points, no more
            checks.note(f"plot_error raised {type(exc).__name__}: {exc}")

        drew = figure.exists() and figure.stat().st_size > 0
        checks.that(drew, 2, "You produced an error-vs-nbits figure",
                    f"no figure was written to {figure.name} — plot_error must save "
                    f"one, and it is part of what you submit")
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


def _placeholder_figure(path: Path) -> None:
    """A stand-in PNG, so the declared artifact exists when no plot was drawn.

    Deliberately built with ``plt.figure`` rather than ``plt.subplots``, and
    with no axis calls: those lines would be byte-identical to ones inside a
    solution block in ``subc_eval.py``, and labkit's leak guard -- rightly --
    cannot tell generic matplotlib boilerplate from a leaked answer.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(7.0, 4.0))
    fig.text(0.5, 0.5, "no error plot was drawn", ha="center", va="center",
             color="0.4")
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Stage 3 -- the SystemVerilog
# ---------------------------------------------------------------------------

def compare_hardware(py_path: Path, sv_path: Path) -> tuple[float, str, float, str]:
    """Score the simulation against the Python model.

    Returns ``(z_fraction, z_note, cycle_fraction, cycle_note)``.
    """
    py = pd.read_csv(py_path)
    sv = pd.read_csv(sv_path)

    if len(py) == 0:
        msg = "your Python model produced no cases, so there is nothing to match"
        return 0.0, msg, 0.0, msg

    # Consistency between two languages is only evidence when there is something
    # to be consistent about.  Both unedited templates produce a constant, so
    # they agree perfectly while implementing nothing -- this is the check that
    # stops an untouched submission collecting full marks here.
    if int(np.unique(py["z"].to_numpy()).size) <= 1:
        msg = ("your Python model returned the same z for every case, so a matching "
               "simulation proves nothing — fix subc_divide.py first")
        return 0.0, msg, 0.0, msg

    if len(sv) != len(py):
        # The usual cause is the testbench's watchdog: it prints a diagnosis and
        # calls $finish, so the simulation *succeeds* and simply stops early.
        # That is deliberate -- $fatal leaves xsim alive on Windows and stalls
        # the build for ten minutes -- but it means a short file, not an error,
        # is what reaches this function.
        msg = (f"the simulation recorded {len(sv)} cases but your Python model "
               f"produced {len(py)} — it stopped early, which usually means the "
               f"module stopped handshaking. The simulator's own output, above "
               f"and in sim/logs/xsim.log, says where")
        return 0.0, msg, 0.0, msg

    z_py = py["z"].to_numpy(dtype=np.int64)
    z_sv = sv["z"].to_numpy(dtype=np.int64)
    same = z_py == z_sv

    z_note = ""
    if not same.all():
        first = int(np.flatnonzero(~same)[0])
        z_note = (f"{int((~same).sum())} of {len(py)} cases differ; the first is case "
                  f"{first}, where a={py['a'][first]}, b={py['b'][first]}, "
                  f"nbits={py['nbits'][first]} — Python says {z_py[first]} and the "
                  f"simulation says {z_sv[first]}")

    nbits = sv["nbits"].to_numpy(dtype=np.int64)
    cycles = sv["cycles"].to_numpy(dtype=np.int64)
    bound = _latency_bound(nbits)

    # Latency is only credited on a case that was answered correctly, and that
    # took at least one cycle to answer.  Both guards earn their place:
    #
    #   * fast and wrong is not a design.  Timing a case whose answer is wrong
    #     measures nothing.
    #   * an untouched testbench never drives the module at all, so it records
    #     cycles = 0 -- which is comfortably "within nbits + 2" and would
    #     otherwise collect full marks for running no cases whatsoever.
    quick = same & (cycles >= 1) & (cycles <= bound)

    cycle_note = ""
    if not quick.all():
        first = int(np.flatnonzero(~quick)[0])
        if cycles[first] < 1:
            why = ("it reports 0 cycles — the testbench never waited for outvalid "
                   "on this case")
        elif not same[first]:
            why = "its answer was wrong, so its timing earns nothing"
        else:
            why = (f"nbits={nbits[first]} should finish within {bound[first]} "
                   f"cycles but took {cycles[first]}")
        cycle_note = (f"{int((~quick).sum())} of {len(sv)} cases did not earn it; "
                      f"the first is case {first}, where {why}")

    return float(same.mean()), z_note, float(quick.mean()), cycle_note


@dataclass(kw_only=True)
class SvSimStep(GradedStep):
    description = "Simulate your SystemVerilog divider and compare it with your Python model."
    points = 10.0
    outputs = {"sv_vectors": Path("vectors/tv_sv.csv")}
    consumes = ["subc_sv_src", "subc_tb_src", "py_vectors"]

    def evaluate(self, config: BuildConfig, **_) -> GradeResult:
        from waveflow.scripts.sv_sim import SvSimError, run_sv_sim

        root = Path(config.root_dir)
        checks = Checks()
        z_label = "SystemVerilog matches your Python model"
        cycle_label = "Each case finishes within nbits + 2 cycles"
        sv_path = root / "vectors/tv_sv.csv"

        # The simulation is run here rather than by a separate SvSimStep so that
        # a compile error, or a watchdog timeout, becomes a scored zero with the
        # tool output attached.  As its own DAG node it would raise, halt the
        # build, and leave you with a traceback and no submission file.
        try:
            run_sv_sim(
                [root / "subc_divide.sv"], root / "tb_subc_divide.sv",
                sim_dir=root / "sim",
                plusargs={"vecdir": root / "vectors"},
                capture_output=True,
            )
        except SvSimError as exc:
            note = f"the simulation did not run: {exc}".rstrip()
            checks.zero(6, z_label, note)
            checks.zero(4, cycle_label, note)
            return checks.result(sv_vectors=_empty_sv_vectors(sv_path))

        if not sv_path.exists():
            note = "the simulation finished but wrote no output file"
            checks.zero(6, z_label, note)
            checks.zero(4, cycle_label, note)
            return checks.result(sv_vectors=_empty_sv_vectors(sv_path))

        z_frac, z_note, cyc_frac, cyc_note = compare_hardware(
            root / "vectors/tv_python.csv", sv_path)
        checks.fraction(z_frac, 6, z_label, z_note)
        checks.fraction(cyc_frac, 4, cycle_label, cyc_note)
        return checks.result(sv_vectors=sv_path)


def _empty_sv_vectors(path: Path) -> Path:
    """Write a header-only tv_sv.csv, so the failure path still has its artifact.

    ``GradeReportStep`` refuses to bundle a file that is not there, so a student
    whose simulation never ran would otherwise get no submission zip at all --
    which is exactly the student who most needs to submit what they have.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("a,b,nbits,z_exp,z,cycles\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The graph
# ---------------------------------------------------------------------------

def lab_steps() -> tuple[list[StudentSourceStep], list[GradedStep]]:
    """The student's four files, and the three stages that grade them.

    Built together because each stage needs to know which files are *its* -- a
    stage whose files are all still the shipped template reports "not started"
    instead of a page of failed checks.
    """
    divide_src = StudentSourceStep(artifact="subc_divide_src", path=Path("subc_divide.py"))
    eval_src = StudentSourceStep(artifact="subc_eval_src", path=Path("subc_eval.py"))
    sv_src = StudentSourceStep(artifact="subc_sv_src", path=Path("subc_divide.sv"))
    # The testbench is a student file too: the handshake that drives the module
    # -- assert invalid, wait for outvalid, pulse outready -- lives there, and
    # implementing that protocol is half of what this lab is about.
    tb_src = StudentSourceStep(artifact="subc_tb_src", path=Path("tb_subc_divide.sv"))

    return ([divide_src, eval_src, sv_src, tb_src],
            [PySimStep(name="pysim", title="Python golden model",
                       starts_from=[divide_src]),
             PyEvalStep(name="pyeval", title="Measuring the error",
                        starts_from=[eval_src]),
             SvSimStep(name="svsim", title="SystemVerilog divider",
                       starts_from=[sv_src, tb_src])])


def graded_steps() -> list[GradedStep]:
    """The graded stages, in the order the submission reports them."""
    return lab_steps()[1]


def build_subc_dag() -> BuildDag:
    dag = BuildDag()
    (divide_src, eval_src, sv_src, tb_src), (pysim, pyeval, svsim) = lab_steps()

    dag.add(divide_src)
    dag.add(pysim)

    dag.add(eval_src)
    dag.add(pyeval)

    dag.add(sv_src)
    dag.add(tb_src)
    dag.add(svsim)

    # svsim does not consume pyeval's output, and no edge pretends otherwise --
    # the reason to measure the error before building hardware is a habit, not a
    # data dependency, and a DAG that lies about its dependencies is worth less
    # than the lesson.
    dag.add(GradeReportStep(
        name="submit", graded=[pysim, pyeval, svsim],
        # The error plot goes in the zip so it can be looked at.  It is the one
        # part of this lab whose quality a person can judge in a second and a
        # script cannot judge at all.
        bundle=[Path("subc_divide.py"), Path("subc_eval.py"),
                Path("subc_divide.sv"), Path("tb_subc_divide.sv"),
                Path("vectors/tv_python.csv"), Path("vectors/tv_sv.csv"),
                Path("results/subc_error.png")]))
    return dag


def main() -> None:
    run_graded_dag_cli(
        build_subc_dag,
        graded_steps=graded_steps,
        description="subc — Unit 2 lab: division by conditional subtraction.",
        default_through="submit",
        root_dir=_SOURCE_DIR,
    )


if __name__ == "__main__":
    main()
