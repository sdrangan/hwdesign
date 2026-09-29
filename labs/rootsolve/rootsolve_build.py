"""rootsolve — the Unit 4 lab build.

Four stages, in the order you do them::

    python rootsolve_build.py --list-steps-verbose   # what the steps are
    python rootsolve_build.py --through pysim        # 1. the golden model, scored
    python rootsolve_build.py --through vectors      # 2. the test vectors
    python rootsolve_build.py --through csim         # 3. the kernel, in C simulation
    python rootsolve_build.py --through cosim        #    ... and as synthesized RTL
    python rootsolve_build.py --through eval         # 4. the comparison, scored
    python rootsolve_build.py                        # everything, then the submission zip
    python rootsolve_build.py --grades               # your scores, without rebuilding

``pysim`` runs your ``fsolve()`` on the lab's own problems and asks whether it
converged -- to within ``tol``, by the update rule, stopping where it should.
``vectors`` runs your ``make_vectors()`` and writes ``vectors/tv_python.csv``.
``csim``, ``csynth`` and ``cosim`` hand those vectors to your testbench, first
against the C++ kernel and then against the RTL Vitis synthesized from it.
``eval`` runs the comparison code *you* wrote over what came back, and asks two
questions of it: is your comparison right, and does the kernel agree with the
model?

``vectors`` and the three Vitis steps are not scored on their own.  What they
produce is scored in ``eval``, and a step that fails does not stop the build:
it records what went wrong, ``eval`` reports it, and the next build tries the
step again.

YOU DO NOT NEED TO EDIT THIS FILE.  Your work goes in ``fsolve.py``,
``fsolve.cpp``, ``tb_fsolve.cpp`` and ``fsolve_eval.py``.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from waveflow.build.build import BuildConfig, BuildDag, BuildStep, SourceStep

from hwdesign.grading import (
    Checks, GradeReportStep, GradedStep, GradeResult, StudentSourceStep,
    run_graded_dag_cli,
)

_SOURCE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# The lab's specification
#
# These live here rather than in fsolve.py so that the grader agrees with
# itself no matter what a submission does to its own constants -- and so that
# a file which fails to import at all can still be scored against the right
# numbers instead of crashing the build.  The ranges repeat the ones at the top
# of fsolve.py on purpose.
# ---------------------------------------------------------------------------

#: The stopping tolerance, and the iteration budget, for every problem.
TOL = 1e-5
MAX_ITER = 500

#: The problem family: a1 is drawn as a2**2/3 plus a margin in this range,
#: which keeps f increasing and so keeps the iteration convergent.
A0_LO, A0_HI = -2.0, 2.0
A2_LO, A2_HI = -1.5, 1.5
A1_MARGIN_LO, A1_MARGIN_HI = 0.5, 2.5
X0_LO, X0_HI = -1.0, 1.0
STEP_LO, STEP_HI = 0.05, 0.1

#: How many problems pysim poses, and the seed they are drawn from.  A seed,
#: so that "case 7 did not converge" names the same case on your machine as on
#: anybody else's.
NCASE = 20
CASE_SEED = 20260929

#: The problem the convergence figure is drawn from, fixed so every student's
#: figure can be compared with the one on the lab page.  It is also the
#: max_iter check's problem, run with a budget of STALL_MAX_ITER updates --
#: far fewer than the 39 it needs.
FIG_CASE = {"a0": -1.0, "a1": 1.5, "a2": 0.5, "x0": 0.0, "step": 0.1}
STALL_MAX_ITER = 5

#: How many test vectors make_vectors must produce, and the seed it is given.
#: Twenty is enough to cover the family and few enough that co-simulation --
#: which runs every update of every vector as RTL -- is over in a minute.
NVEC = 20
VECTOR_SEED = 20260930

#: When the kernel's answer counts as the model's.  See fsolve_eval.py for the
#: reasoning.  XTOL: both answers satisfy |f(x)| < TOL and f' >= 0.5 at every
#: root in this family, so each is within 2e-5 of the true root and the two
#: within 4e-5 of each other.  NITER_TOL: near the end of a slow run |f(x)|
#: falls by only ~2.5% per update, and a rounding difference in f is the same
#: size, so the crossing of TOL can move by a few updates.  A kernel that
#: evaluates the polynomial in the model's order scores 0 on both.
XTOL = 1e-4
NITER_TOL = 5

#: Slack for the grader's float64 re-evaluation of f against a float32 one.
#: f32 rounding over the terms of this family is at most a few 1e-7.
FX_SLACK = 1e-6
#: Relative slack for checking one float32 update against the rule.
STEP_RTOL = 1e-6

#: The columns of every vector file, in order.  tb_fsolve.cpp reads and
#: writes them by position.
VECTOR_COLUMNS = ["a0", "a1", "a2", "x0", "tol", "max_iter", "step", "x", "fx", "niter"]
INPUT_COLUMNS = VECTOR_COLUMNS[:7]


def f64(x, a0, a1, a2):
    """The cubic in float64 -- the grader's reference for f, not the student's."""
    x = np.asarray(x, dtype=np.float64)
    return ((x + a2) * x + a1) * x + a0


def lab_cases(n: int = NCASE, seed: int = CASE_SEED) -> list[dict[str, float]]:
    """The problems pysim poses, each input rounded to float32 once, here.

    Drawn a column at a time rather than a problem at a time, as make_vectors
    does: this file ships whole, so where the two would otherwise be the same
    lines of code, the grader takes the other route.
    """
    rng = np.random.default_rng(seed)
    draws = {"a2": rng.uniform(A2_LO, A2_HI, n)}
    draws["a1"] = draws["a2"] ** 2 / 3.0 + rng.uniform(A1_MARGIN_LO, A1_MARGIN_HI, n)
    draws["a0"] = rng.uniform(A0_LO, A0_HI, n)
    draws["x0"] = rng.uniform(X0_LO, X0_HI, n)
    draws["step"] = rng.uniform(STEP_LO, STEP_HI, n)
    table = {k: v.astype(np.float32).astype(np.float64) for k, v in draws.items()}
    return [{k: float(table[k][i]) for k in table} for i in range(n)]


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
# Stage 1 -- the golden model
# ---------------------------------------------------------------------------

def unpack_run(value: Any) -> dict[str, Any]:
    """Normalise what ``fsolve`` returned, or raise ``ValueError`` saying why it can't be."""
    if value is None:
        raise ValueError("fsolve returned None — it has no `return` statement")
    if not isinstance(value, tuple) or len(value) != 4:
        raise ValueError("fsolve must return the tuple (x, fx, niter, hist)")
    x, fx, niter, hist = value
    if not isinstance(hist, dict) or "x" not in hist or "fx" not in hist:
        raise ValueError('hist must be a dict with keys "x" and "fx"')
    return {"x": float(x), "fx": float(fx), "niter": int(niter),
            "hx": np.asarray(hist["x"], dtype=np.float64).ravel(),
            "hf": np.asarray(hist["fx"], dtype=np.float64).ravel()}


def follows_rule(case: dict[str, float], run: dict[str, Any]) -> str:
    """Why *run*'s history is not the iteration ``x <- x - step*f(x)``, or ``""`` if it is.

    Checked against the history rather than a reference solver, because this
    file ships to students whole: a reference ``fsolve`` in here would be the
    answer.  The history says everything the rule constrains -- where it
    started, that every fx is f at its x, that every x is the last one moved by
    step*fx, and that it ends at the x and fx returned.
    """
    hx, hf, n = run["hx"], run["hf"], run["niter"]
    if n < 1:
        return "it made no updates"
    if len(hx) != n + 1 or len(hf) != n + 1:
        return (f"niter is {n} but hist has {len(hx)} x values and {len(hf)} fx "
                f"values — both should have niter + 1, starting with x0")
    if hx[0] != case["x0"]:
        return f"hist['x'] starts at {hx[0]:.7g}, not at x0 = {case['x0']:.7g}"
    if hx[-1] != run["x"] or hf[-1] != run["fx"]:
        return "the last entries of hist are not the x and fx returned"

    fref = f64(hx, case["a0"], case["a1"], case["a2"])
    bad_f = np.flatnonzero(np.abs(hf - fref) > FX_SLACK * (1.0 + np.abs(fref)))
    if bad_f.size:
        k = int(bad_f[0])
        return (f"at update {k}, hist['fx'] is {hf[k]:.6g} but f(hist['x']) is "
                f"{fref[k]:.6g} — fx has to be f at the x stored beside it")

    moved = hx[:-1] - np.float32(case["step"]) * hf[:-1]
    bad_x = np.flatnonzero(np.abs(hx[1:] - moved) > STEP_RTOL * (1.0 + np.abs(moved)))
    if bad_x.size:
        k = int(bad_x[0])
        return (f"update {k + 1} went from x = {hx[k]:.7g} to {hx[k + 1]:.7g}; "
                f"x - step*f(x) is {moved[k]:.7g}")
    return ""


def check_model(cases: list[dict[str, float]], runs: list[dict[str, Any] | None],
                stall: dict[str, Any] | None) -> Checks:
    """Score the golden model: did it converge, by the rule, stopping where it should?"""
    checks = Checks()
    n = len(cases)
    ok = [r is not None for r in runs]
    n_ok = sum(ok)

    conv_label = f"|f(x)| < tol = {TOL:g} at the x returned"
    rule_label = "Every update is x - step*f(x), recorded in hist"
    first_label = "It stops at the first x with |f(x)| < tol"
    stall_label = "It stops after max_iter updates when it has not converged"

    checks.that(n_ok == n, 1, f"fsolve returned (x, fx, niter, hist) for all {n} cases",
                f"{n - n_ok} of {n} cases produced nothing usable")
    if n_ok == 0:
        note = "no case produced a usable result, so there is nothing to check"
        for points, label in ((3, conv_label), (2, rule_label), (1, first_label),
                              (1, stall_label)):
            checks.zero(points, label, note)
        return checks

    # --- converged ------------------------------------------------------------
    #
    # Two conditions, because either alone can be satisfied without converging:
    # the fx reported has to be small, *and* f really has to be small at the x
    # reported.  Returning fx = 0 passes the first; returning the fx from before
    # the last update, with the x after it, can pass it too.
    converged = []
    for case, run in zip(cases, runs):
        if run is None:
            converged.append(False)
            continue
        truth = float(f64(run["x"], case["a0"], case["a1"], case["a2"]))
        converged.append(abs(run["fx"]) < TOL and abs(truth) < TOL + FX_SLACK)
    converged = np.array(converged)
    note = ""
    if not converged.all():
        i = int(np.flatnonzero(~converged)[0])
        run = runs[i]
        note = (f"{int((~converged).sum())} of {n} cases did not converge; the first is "
                f"case {i}, " + ("which raised" if run is None else
                f"which returned x = {run['x']:.7g}, fx = {run['fx']:.3g} after "
                f"{run['niter']} updates, where f(x) = "
                f"{float(f64(run['x'], **{k: cases[i][k] for k in ('a0', 'a1', 'a2')})):.3g}"))
    checks.fraction(float(converged.mean()), 3, conv_label, note)

    # --- by the rule ------------------------------------------------------------
    reasons = [follows_rule(c, r) if r is not None else "it raised"
               for c, r in zip(cases, runs)]
    good = np.array([not why for why in reasons])
    note = ""
    if not good.all():
        i = int(np.flatnonzero(~good)[0])
        note = f"{int((~good).sum())} of {n} cases; in case {i}, {reasons[i]}"
    checks.fraction(float(good.mean()), 2, rule_label, note)

    # --- stops at the first x that is close enough ------------------------------
    #
    # Judged only on the cases that converged: one that did not has already lost
    # its points above, and has no "first converged x" to stop at.
    late = [i for i in np.flatnonzero(converged)
            if len(runs[i]["hf"]) > 1 and np.any(np.abs(runs[i]["hf"][:-1]) < TOL)]
    if not converged.any():
        checks.zero(1, first_label, "no case converged, so there is no stopping point to check")
    else:
        i = late[0] if late else 0
        k = int(np.flatnonzero(np.abs(runs[i]["hf"][:-1]) < TOL)[0]) if late else 0
        checks.that(not late, 1, first_label,
                    f"in case {i}, |f(x)| was already below tol after update {k}, but "
                    f"the loop went on to update {runs[i]['niter']} — test the "
                    f"condition before each update, not after")

    # --- runs out of budget cleanly ---------------------------------------------
    if stall is None:
        checks.zero(1, stall_label, f"fsolve raised or returned nothing usable when "
                                    f"called with max_iter = {STALL_MAX_ITER}")
    else:
        ran_out = (stall["niter"] == STALL_MAX_ITER and len(stall["hx"]) == STALL_MAX_ITER + 1
                   and abs(stall["fx"]) >= TOL)
        checks.that(ran_out, 1, stall_label,
                    f"with max_iter = {STALL_MAX_ITER} on a problem that needs far more, "
                    f"fsolve returned niter = {stall['niter']} and a hist of "
                    f"{len(stall['hx'])} x values — expected niter = {STALL_MAX_ITER} "
                    f"and {STALL_MAX_ITER + 1} values")
    return checks


@dataclass(kw_only=True)
class PySimStep(GradedStep):
    description = "Run your golden model on the lab's problems and check it converged."
    points = 10.0
    outputs = {"convergence_figure": Path("results/fsolve_hist.png")}
    consumes = ["fsolve_py_src"]

    def evaluate(self, config: BuildConfig, **_) -> GradeResult:
        root = Path(config.root_dir)
        cases = lab_cases()
        runs: list[dict[str, Any] | None] = [None] * len(cases)
        stall = None
        failure = ""

        # Importing is inside the try as well: a file with a syntax error cannot
        # be loaded at all, and that has to score zero rather than take the build
        # down and leave you with no submission.
        try:
            model = load_student_module(root, "fsolve")
            for i, case in enumerate(cases):
                try:
                    runs[i] = unpack_run(model.fsolve(
                        case["a0"], case["a1"], case["a2"], case["x0"],
                        TOL, MAX_ITER, case["step"]))
                except Exception as exc:  # noqa: BLE001 -- any student error is a zero, not a crash
                    if not failure:
                        failure = f"case {i}: fsolve raised {type(exc).__name__}: {exc}"
            try:
                stall = unpack_run(model.fsolve(
                    FIG_CASE["a0"], FIG_CASE["a1"], FIG_CASE["a2"], FIG_CASE["x0"],
                    TOL, STALL_MAX_ITER, FIG_CASE["step"]))
            except Exception as exc:  # noqa: BLE001
                if not failure:
                    failure = f"with max_iter = {STALL_MAX_ITER}, fsolve raised {type(exc).__name__}: {exc}"
        except Exception as exc:  # noqa: BLE001
            failure = f"fsolve.py raised {type(exc).__name__}: {exc}"

        checks = check_model(cases, runs, stall)
        if failure:
            checks.note(failure)

        # Only the figure's *existence* is scored.  Judging a plot mechanically
        # is a poor trade -- the checks that could be automated are the ones a
        # student can satisfy without drawing anything worth looking at -- so the
        # file goes into the submission instead, where a person can read it.
        figure = root / "results/fsolve_hist.png"
        # Removed first, so a figure left over from an earlier run cannot earn
        # the points for code that no longer draws one.
        figure.unlink(missing_ok=True)
        try:
            model = load_student_module(root, "fsolve")
            run = model.fsolve(FIG_CASE["a0"], FIG_CASE["a1"], FIG_CASE["a2"],
                               FIG_CASE["x0"], TOL, MAX_ITER, FIG_CASE["step"])
            unpack_run(run)  # raises, with a reason, if there is no hist to plot
            model.plot_convergence(run[3], TOL, figure)
        except Exception as exc:  # noqa: BLE001 -- a broken plot costs its own points, no more
            checks.note(f"plot_convergence raised {type(exc).__name__}: {exc}")

        drew = figure.exists() and figure.stat().st_size > 0
        checks.that(drew, 2, "You produced a convergence figure",
                    f"no figure was written to {figure.name} — plot_convergence must "
                    f"save one, and it is part of what you submit")
        if not drew:
            _placeholder_figure(figure, "no convergence plot was drawn")

        result = checks.result(convergence_figure=figure)
        where = figure.relative_to(root)
        result.feedback.append(
            f"  figure written to {where}" if drew
            else f"  a placeholder was written to {where} so your submission is still complete")
        return result


def _placeholder_figure(path: Path, message: str) -> None:
    """A stand-in PNG, so the declared artifact exists when no plot was drawn.

    Built with ``plt.figure`` and no axes on purpose: lines identical to ones in
    the plotting solution would trip labkit's leak guard, which rightly cannot
    tell matplotlib boilerplate from a leaked answer.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(8.4, 3.6))
    fig.text(0.5, 0.5, message, ha="center", va="center", color="0.4")
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# The ungraded steps' bookkeeping
#
# `vectors` and the three Vitis steps are plain build steps, and a plain step
# that raises halts the whole DAG -- no eval, no submission zip.  So they never
# raise for a student's mistake or a missing tool.  Each writes what it managed
# to produce, plus a status record that eval reads back and reports.
#
# A failed step also back-dates its outputs.  Otherwise the build would call it
# up to date on the next run -- nothing it consumes has changed -- and a failure
# caused by the environment (Vitis not on the path, say) would stick until you
# thought of --force.
# ---------------------------------------------------------------------------

#: The time a failed step's outputs are back-dated to: 2000-01-01.  Older than
#: any source, so the step is stale -- but not the epoch, because the submission
#: zip bundles some of these files and ZIP cannot store a time before 1980.
_BACKDATE = 946684800


def _status_path(stage: str) -> Path:
    return Path("results") / stage / "status.json"


def _finish(root: Path, stage: str, ok: bool, message: str, outputs: list[Path] = (),
            log: Path | None = None) -> None:
    """Record how *stage* went, print it, and back-date *outputs* if it failed."""
    status = root / _status_path(stage)
    status.parent.mkdir(parents=True, exist_ok=True)
    record = {"ok": ok, "message": message,
              "log": str(log.relative_to(root)) if log else None}
    status.write_text(json.dumps(record, indent=2), encoding="utf-8")
    if ok:
        print(f"    {message}")
        return
    # Not "FAILED": waveflow prints PASSED under every step that returned, and
    # the two on consecutive lines read as a contradiction.
    print(f"    ✗ {message}")
    if log:
        print(f"    the tool output is in {log.relative_to(root)}")
    for path in [status, *outputs]:
        if path.exists():
            os.utime(path, (_BACKDATE, _BACKDATE))


def read_status(root: Path, stage: str) -> dict[str, Any]:
    path = Path(root) / _status_path(stage)
    if not path.exists():
        return {"ok": False, "message": f"the {stage} step has not run", "log": None}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_header_only(path: Path) -> None:
    """An empty vector file, so a failure path still leaves its artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(",".join(VECTOR_COLUMNS) + "\n", encoding="utf-8")


def _count_rows(path: Path) -> int:
    try:
        return len(pd.read_csv(path))
    except Exception:  # noqa: BLE001 -- unreadable counts as empty
        return 0


# ---------------------------------------------------------------------------
# Stage 2 -- the test vectors
# ---------------------------------------------------------------------------

def conform_vectors(table: Any) -> pd.DataFrame:
    """Put make_vectors' table into the file's column order, or raise saying why it can't be."""
    if not isinstance(table, pd.DataFrame):
        raise ValueError(f"make_vectors returned a {type(table).__name__}, not a DataFrame")
    missing = [c for c in VECTOR_COLUMNS if c not in table.columns]
    if missing:
        raise ValueError(f"make_vectors' table has no column(s) {missing}")
    if len(table) == 0:
        raise ValueError("make_vectors returned no rows")
    out = table[VECTOR_COLUMNS].copy()
    for col in ("max_iter", "niter"):
        out[col] = out[col].astype(np.int64)
    return out


@dataclass(kw_only=True)
class VectorsStep(BuildStep):
    """Run your ``make_vectors()`` and write the file the testbench reads."""

    description = "Write vectors/tv_python.csv from your make_vectors() (ungraded; eval checks it)."
    params: ClassVar[dict] = {}
    consumes = ["fsolve_py_src"]
    produces: ClassVar[dict] = {"py_vectors": Path("vectors/tv_python.csv"),
                                "vectors_status": _status_path("vectors")}

    def run(self, config: BuildConfig, **_) -> dict[str, Any]:
        root = Path(config.root_dir)
        path = root / "vectors/tv_python.csv"
        try:
            model = load_student_module(root, "fsolve")
            table = conform_vectors(model.make_vectors(NVEC, VECTOR_SEED))
        except Exception as exc:  # noqa: BLE001 -- recorded, and reported by eval
            _write_header_only(path)
            _finish(root, "vectors", False, f"{type(exc).__name__}: {exc}", [path])
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            table.to_csv(path, index=False)
            _finish(root, "vectors", True,
                    f"wrote {len(table)} vectors to {path.relative_to(root)}; your model "
                    f"took {table['niter'].min()} to {table['niter'].max()} updates")
        return {"py_vectors": path, "vectors_status": root / _status_path("vectors")}


# ---------------------------------------------------------------------------
# Stage 3 -- the Vitis kernel
# ---------------------------------------------------------------------------

def run_vitis_stage(root: Path, stage: str, live_output: bool) -> tuple[bool, str, Path]:
    """Run one stage of ``run.tcl``.  Returns ``(ok, message, log)``; never raises.

    Every line of the tool's output goes to ``results/<stage>/vitis.log``.  The
    message is the first few lines that say ERROR, which is usually enough to
    tell a compile error from a missing tool without opening the log.
    """
    from waveflow.toolchain import toolchain

    log = root / "results" / stage / "vitis.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = toolchain.run_vitis_hls(root / "run.tcl", work_dir=root,
                                         capture_output=not live_output,
                                         env={"ROOTSOLVE_STAGE": stage})
        text, ok, message = (result.stdout or "") + (result.stderr or ""), True, ""
    except subprocess.CalledProcessError as exc:
        text = (exc.stdout or "") + (exc.stderr or "")
        ok, message = False, f"Vitis exited with status {exc.returncode}"
    except Exception as exc:  # noqa: BLE001 -- most often: Vitis is not installed or not found
        text, ok, message = "", False, f"{type(exc).__name__}: {exc}"

    log.write_text(text, encoding="utf-8")
    if not ok:
        # The compiler's own `file:line: error:` lines first -- they name the
        # line to fix, where Vitis's ERROR lines only say that compiling failed.
        lines = [ln.strip() for ln in text.splitlines()]
        errors = ([ln for ln in lines if ": error:" in ln][:3]
                  + [ln for ln in lines if ln.startswith("ERROR")])[:4]
        if errors:
            message += ":\n      " + "\n      ".join(errors)
        elif live_output:
            message += " (see the output above)"
    return ok, message, log


@dataclass(kw_only=True)
class CSimStep(BuildStep):
    """Compile the testbench against your kernel and run it on the vectors."""

    description = "Run Vitis C simulation; the testbench writes vectors/tv_csim.csv."
    params = {"live_output": False}
    consumes = ["fsolve_cpp_src", "fsolve_h", "tb_fsolve_src", "run_tcl", "py_vectors"]
    produces: ClassVar[dict] = {"csim_vectors": Path("vectors/tv_csim.csv"),
                                "csim_status": _status_path("csim")}

    def run(self, config: BuildConfig, py_vectors, live_output, **_) -> dict[str, Any]:
        root = Path(config.root_dir)
        out = root / "vectors/tv_csim.csv"
        # Removed first, so a file from an earlier run cannot pass for this one's.
        out.unlink(missing_ok=True)
        artifacts = {"csim_vectors": out, "csim_status": root / _status_path("csim")}

        if _count_rows(Path(py_vectors)) == 0:
            _write_header_only(out)
            _finish(root, "csim", False, "skipped: vectors/tv_python.csv has no vectors "
                                         "— see the vectors step", [out])
            return artifacts

        ok, message, log = run_vitis_stage(root, "csim", live_output)
        if not out.exists():
            _write_header_only(out)
            if ok:
                ok, message = False, ("C simulation ran but the testbench wrote no "
                                      "vectors/tv_csim.csv")
        if ok:
            message = f"the testbench recorded {_count_rows(out)} vectors in {out.relative_to(root)}"
        _finish(root, "csim", ok, message, [out], log)
        return artifacts


@dataclass(kw_only=True)
class CSynthStep(BuildStep):
    """Synthesize the kernel to RTL."""

    description = "Run Vitis C synthesis; the report is copied to results/csynth/."
    params = {"live_output": False}
    # csim_status orders this after csim, which is the stage that (re)creates
    # the project.  It is also how synthesis knows to skip a kernel that does
    # not simulate.
    consumes = ["fsolve_cpp_src", "fsolve_h", "run_tcl", "csim_status"]
    produces: ClassVar[dict] = {"csynth_report": Path("results/csynth/fsolve_csynth.rpt"),
                                "csynth_status": _status_path("csynth")}

    def run(self, config: BuildConfig, live_output, **_) -> dict[str, Any]:
        root = Path(config.root_dir)
        report = root / "results/csynth/fsolve_csynth.rpt"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.unlink(missing_ok=True)
        artifacts = {"csynth_report": report, "csynth_status": root / _status_path("csynth")}

        if not read_status(root, "csim")["ok"]:
            report.write_text("not synthesized: C simulation did not succeed\n", encoding="utf-8")
            _finish(root, "csynth", False, "skipped: C simulation did not succeed", [report])
            return artifacts

        ok, message, log = run_vitis_stage(root, "csynth", live_output)
        made = root / "fsolve_proj/solution1/syn/report/fsolve_csynth.rpt"
        if made.exists():
            shutil.copyfile(made, report)
        else:
            report.write_text("synthesis wrote no report\n", encoding="utf-8")
            if ok:
                ok, message = False, f"synthesis ran but wrote no report at {made.relative_to(root)}"
        if ok:
            message = f"the synthesis report is in {report.relative_to(root)}"
        _finish(root, "csynth", ok, message, [report], log)
        return artifacts


@dataclass(kw_only=True)
class CoSimStep(BuildStep):
    """Re-run the same testbench against the synthesized RTL."""

    description = "Run RTL co-simulation; the testbench writes vectors/tv_cosim.csv."
    params = {"live_output": False}
    consumes = ["tb_fsolve_src", "run_tcl", "py_vectors", "csynth_status"]
    produces: ClassVar[dict] = {"cosim_vectors": Path("vectors/tv_cosim.csv"),
                                "cosim_status": _status_path("cosim")}

    def run(self, config: BuildConfig, live_output, **_) -> dict[str, Any]:
        root = Path(config.root_dir)
        out = root / "vectors/tv_cosim.csv"
        out.unlink(missing_ok=True)
        artifacts = {"cosim_vectors": out, "cosim_status": root / _status_path("cosim")}

        if not read_status(root, "csynth")["ok"]:
            _write_header_only(out)
            _finish(root, "cosim", False, "skipped: synthesis did not succeed", [out])
            return artifacts

        ok, message, log = run_vitis_stage(root, "cosim", live_output)
        if not out.exists():
            _write_header_only(out)
            if ok:
                ok, message = False, ("co-simulation ran but the testbench wrote no "
                                      "vectors/tv_cosim.csv")
        if ok:
            message = f"the testbench recorded {_count_rows(out)} vectors in {out.relative_to(root)}"
        _finish(root, "cosim", ok, message, [out], log)
        return artifacts


# ---------------------------------------------------------------------------
# Stage 4 -- the comparison
# ---------------------------------------------------------------------------

#: What each row of the comparison fixture tests, and whether it should match.
#: The fixture is made up rather than simulated, so that your comparison code
#: is judged on every way a vector can fail -- including ways your own kernel,
#: being correct, never exercises.
FIXTURE_ROWS: list[tuple[str, bool]] = [
    ("identical to the model", True),
    ("identical to the model", True),
    ("identical to the model", True),
    ("identical to the model", True),
    ("off by a rounding-sized 0.5*XTOL in x and one update", True),
    ("20*XTOL above the model's root", False),
    ("20*XTOL below the model's root", False),
    ("NITER_TOL + 3 updates more than the model", False),
    ("NITER_TOL + 3 updates fewer than the model", False),
    ("fx = +3*tol: it did not converge", False),
    ("fx = -3*tol: it did not converge, on the negative side", False),
    ("fx = -0.5*tol and slightly off in x: converged and close", True),
]


def comparison_fixture(seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """A made-up ``(golden, dut)`` pair, one row per entry of FIXTURE_ROWS."""
    rng = np.random.default_rng(seed)
    n = len(FIXTURE_ROWS)
    a2 = rng.uniform(A2_LO, A2_HI, n)
    golden = pd.DataFrame({
        "a0": rng.uniform(A0_LO, A0_HI, n), "a1": a2 * a2 / 3 + 1.0, "a2": a2,
        "x0": rng.uniform(X0_LO, X0_HI, n), "tol": np.full(n, TOL),
        "max_iter": np.full(n, MAX_ITER), "step": rng.uniform(STEP_LO, STEP_HI, n),
        "x": rng.uniform(-1.5, 1.5, n), "fx": rng.uniform(-0.9, 0.9, n) * TOL,
        "niter": rng.integers(20, 200, n),
    })
    dut = golden.copy()
    dut.loc[4, "x"] += 0.5 * XTOL
    dut.loc[4, "niter"] += 1
    dut.loc[5, "x"] += 20 * XTOL
    dut.loc[6, "x"] -= 20 * XTOL
    dut.loc[7, "niter"] += NITER_TOL + 3
    dut.loc[8, "niter"] -= NITER_TOL + 3
    dut.loc[9, "fx"] = 3 * TOL
    dut.loc[10, "fx"] = -3 * TOL
    dut.loc[11, "fx"] = -0.5 * TOL
    dut.loc[11, "x"] -= 0.3 * XTOL
    return golden, dut


def check_measurement(checks: Checks, ev: Any) -> None:
    """Score vector_errors and vector_matches against the fixture's known answers."""
    golden, dut = comparison_fixture()
    want = {name: np.abs(golden[col].to_numpy(dtype=np.float64)
                         - dut[col].to_numpy(dtype=np.float64))
            for name, col in (("x_err", "x"), ("fx_err", "fx"), ("niter_err", "niter"))}

    err_label = "Your vector_errors is correct"
    if ev is None:
        checks.zero(2, err_label, "fsolve_eval.py could not be loaded")
    else:
        note = ""
        try:
            got = ev.vector_errors(golden.copy(), dut.copy())
            for name, truth in want.items():
                if name not in got:
                    note = f"the result has no {name} column"
                    break
                values = np.asarray(got[name], dtype=np.float64).ravel()
                if values.shape != truth.shape:
                    note = f"{name} has {values.size} entries for {truth.size} vectors"
                    break
                wrong = np.flatnonzero(np.abs(values - truth) > 1e-12)
                if wrong.size:
                    i = int(wrong[0])
                    note = (f"{name} for vector {i} ({FIXTURE_ROWS[i][0]}) is "
                            f"{values[i]:.6g}; it should be {truth[i]:.6g}")
                    break
        except Exception as exc:  # noqa: BLE001
            note = f"vector_errors raised {type(exc).__name__}: {exc}"
        checks.that(not note, 2, err_label, note)

    match_label = "Your vector_matches is correct"
    if ev is None:
        checks.zero(2, match_label, "fsolve_eval.py could not be loaded")
        return
    truth = np.array([should for _, should in FIXTURE_ROWS])
    note = ""
    try:
        got = np.asarray(ev.vector_matches(golden.copy(), dut.copy(), XTOL, NITER_TOL)).ravel()
        if got.shape != truth.shape:
            note = f"it returned {got.size} values for {truth.size} vectors"
        else:
            wrong = np.flatnonzero(got.astype(bool) != truth)
            if wrong.size:
                i = int(wrong[0])
                note = (f"vector {i} is {FIXTURE_ROWS[i][0]}, so it should "
                        f"{'' if truth[i] else 'not '}match — you returned {bool(got[i])}"
                        f" ({wrong.size} of {truth.size} vectors are wrong)")
    except Exception as exc:  # noqa: BLE001
        note = f"vector_matches raised {type(exc).__name__}: {exc}"
    checks.that(not note, 2, match_label, note)


def vector_problems(py: pd.DataFrame, status: dict[str, Any]) -> str:
    """Why *py* cannot be used to judge a kernel, or ``""`` if it can.

    This is the floor under the comparison.  Two things that agree prove
    nothing when there is nothing to agree about: an unwritten model returns
    x0 after zero updates, an unwritten kernel does the same, and the two match
    perfectly.  So the vectors themselves have to be real problems that the
    model really solved before a kernel's agreement with them is worth anything.
    """
    fix = "fix make_vectors in fsolve.py first; there is nothing to compare the kernel against yet"
    if not status.get("ok", False):
        return f"the vectors step failed ({status.get('message')}) — {fix}"
    if len(py) < NVEC:
        return f"vectors/tv_python.csv has {len(py)} vectors; the lab needs {NVEC} — {fix}"
    rising = py["a1"].to_numpy(dtype=np.float64) > py["a2"].to_numpy(dtype=np.float64) ** 2 / 3
    if not rising.all():
        i = int(np.flatnonzero(~rising)[0])
        return (f"vector {i} has a1 = {py['a1'][i]:.4g} and a2 = {py['a2'][i]:.4g}, so "
                f"a1 <= a2**2/3 and f is not increasing — {fix}")
    solved = np.abs(py["fx"].to_numpy(dtype=np.float64)) < py["tol"].to_numpy(dtype=np.float64)
    if not solved.all():
        i = int(np.flatnonzero(~solved)[0])
        return (f"your model did not converge on vector {i} (fx = {py['fx'][i]:.3g}) — "
                f"fix fsolve first; a kernel cannot be checked against an answer that "
                f"is not one")
    if int(py["niter"].min()) < 1 or py["x"].nunique() < NVEC // 2:
        return (f"the vectors are degenerate — {py['x'].nunique()} distinct roots and "
                f"as few as {int(py['niter'].min())} updates — {fix}")
    return ""


def check_hardware(checks: Checks, label: str, points: float, stage: str,
                   py: pd.DataFrame, dut_path: Path, status: dict[str, Any],
                   problem: str) -> None:
    """Score one kernel run against the model, from the grader's own comparison.

    Scored from the grader's comparison rather than the student's: a student
    whose comparison code is wrong should lose the comparison points, not have
    their kernel judged by a broken instrument.
    """
    if problem:
        checks.zero(points, label, problem)
        return
    if not status.get("ok", False):
        where = f" — the tool output is in {status['log']}" if status.get("log") else ""
        checks.zero(points, label, f"{stage} did not complete: {status.get('message')}{where}")
        return
    try:
        dut = pd.read_csv(dut_path)
    except Exception as exc:  # noqa: BLE001
        checks.zero(points, label, f"{dut_path.name} could not be read: {exc}")
        return
    missing = [c for c in VECTOR_COLUMNS if c not in dut.columns]
    if missing:
        checks.zero(points, label, f"{dut_path.name} has no column(s) {missing} — write the "
                                   f"header exactly as tb_fsolve.cpp's kHeader")
        return
    if len(dut) != len(py):
        checks.zero(points, label, f"the testbench recorded {len(dut)} vectors of {len(py)}")
        return

    # The testbench echoes the inputs, so a row written in the wrong order, or
    # with the arguments passed to fsolve in the wrong order, shows up as a
    # row whose inputs are not the vector's.
    same_in = np.isclose(dut[INPUT_COLUMNS].to_numpy(dtype=np.float64),
                         py[INPUT_COLUMNS].to_numpy(dtype=np.float64),
                         rtol=1e-6, atol=0.0).all(axis=1)
    if not same_in.all():
        i = int(np.flatnonzero(~same_in)[0])
        checks.zero(points, label,
                    f"row {i} of {dut_path.name} has inputs "
                    f"{dut[INPUT_COLUMNS].iloc[i].tolist()} but vector {i} is "
                    f"{py[INPUT_COLUMNS].iloc[i].tolist()} — write one row per vector, "
                    f"in order, echoing the inputs the vector gave")
        return

    x_gap = np.abs(py["x"].to_numpy(dtype=np.float64) - dut["x"].to_numpy(dtype=np.float64))
    n_gap = np.abs(py["niter"].to_numpy(dtype=np.int64) - dut["niter"].to_numpy(dtype=np.int64))
    stopped = np.abs(dut["fx"].to_numpy(dtype=np.float64)) < py["tol"].to_numpy(dtype=np.float64)
    good = stopped & (x_gap <= XTOL) & (n_gap <= NITER_TOL)

    note = ""
    if not good.all():
        i = int(np.flatnonzero(~good)[0])
        why = ("the kernel did not converge" if not stopped[i]
               else f"x differs by {x_gap[i]:.2e}, past XTOL = {XTOL:g}" if x_gap[i] > XTOL
               else f"niter differs by {n_gap[i]}, past NITER_TOL = {NITER_TOL}")
        note = (f"{int((~good).sum())} of {len(py)} vectors differ; the first is vector {i}: "
                f"the model says x = {py['x'][i]:.7g} after {py['niter'][i]} updates, "
                f"{stage} says x = {dut['x'][i]:.7g}, fx = {dut['fx'][i]:.3g} after "
                f"{dut['niter'][i]} — {why}")
    checks.fraction(float(good.mean()), points, label, note)
    if good.all():
        # Compared as float32: the vector file holds each value's full float64
        # expansion and the testbench nine digits of it, so the same float
        # arrives as two float64s that differ around 1e-10.
        same_x = (py["x"].to_numpy(dtype=np.float32) == dut["x"].to_numpy(dtype=np.float32))
        exact = int((same_x & (n_gap == 0)).sum())
        checks.note(f"  {stage}: {exact} of {len(py)} vectors match the model exactly")


@dataclass(kw_only=True)
class EvalStep(GradedStep):
    description = "Compare the kernel's answers with the model's, with your fsolve_eval.py."
    points = 10.0
    consumes = ["fsolve_eval_src", "py_vectors", "vectors_status",
                "csim_vectors", "csim_status", "cosim_vectors", "cosim_status"]

    def evaluate(self, config: BuildConfig, py_vectors: Path, csim_vectors: Path,
                 cosim_vectors: Path, **_) -> GradeResult:
        root = Path(config.root_dir)
        checks = Checks()

        # --- can you compare? --------------------------------------------------
        ev, failure = None, ""
        try:
            ev = load_student_module(root, "fsolve_eval")
        except Exception as exc:  # noqa: BLE001 -- any student error is a zero, not a crash
            failure = f"fsolve_eval.py raised {type(exc).__name__}: {exc}"
        check_measurement(checks, ev)

        # --- does the kernel agree? -------------------------------------------
        try:
            py = pd.read_csv(py_vectors)
        except Exception:  # noqa: BLE001
            py = pd.DataFrame(columns=VECTOR_COLUMNS)
        problem = vector_problems(py, read_status(root, "vectors"))
        check_hardware(checks, "C simulation agrees with your model", 3, "csim",
                       py, Path(csim_vectors), read_status(root, "csim"), problem)
        check_hardware(checks, "RTL co-simulation agrees with your model", 3, "cosim",
                       py, Path(cosim_vectors), read_status(root, "cosim"), problem)

        if failure:
            checks.note(failure)
        return checks.result()


# ---------------------------------------------------------------------------
# The graph
# ---------------------------------------------------------------------------

def lab_steps() -> tuple[list[StudentSourceStep], list[GradedStep]]:
    """The student's four files and the two stages that grade them.

    Built together because each graded stage needs to know which files are
    *its* -- a stage whose files are all still the shipped template reports
    "not started" instead of a page of failed checks.
    """
    py_src = StudentSourceStep(artifact="fsolve_py_src", path=Path("fsolve.py"))
    cpp_src = StudentSourceStep(artifact="fsolve_cpp_src", path=Path("fsolve.cpp"))
    tb_src = StudentSourceStep(artifact="tb_fsolve_src", path=Path("tb_fsolve.cpp"))
    eval_src = StudentSourceStep(artifact="fsolve_eval_src", path=Path("fsolve_eval.py"))

    return ([py_src, cpp_src, tb_src, eval_src],
            [PySimStep(name="pysim", title="The golden model converges",
                       starts_from=[py_src]),
             # The C++ files count as a start on this stage too: most of its
             # points are for the kernel, and a student who has written the
             # kernel but not yet the comparison has started.
             EvalStep(name="eval", title="The kernel agrees with the model",
                      starts_from=[eval_src, cpp_src, tb_src])])


def graded_steps() -> list[GradedStep]:
    """The graded stages, in the order the submission reports them."""
    return lab_steps()[1]


def build_rootsolve_dag() -> BuildDag:
    dag = BuildDag()
    (py_src, cpp_src, tb_src, eval_src), (pysim, evaluate) = lab_steps()

    # The files you complete, and the ones given whole.  Declaring the given
    # ones too means editing run.tcl, say, re-runs the Vitis steps.
    for src in (py_src, cpp_src, tb_src, eval_src):
        dag.add(src)
    dag.add(SourceStep(artifact="fsolve_h", path=_SOURCE_DIR / "fsolve.h"))
    dag.add(SourceStep(artifact="run_tcl", path=_SOURCE_DIR / "run.tcl"))

    dag.add(pysim)
    dag.add(VectorsStep(name="vectors"))
    dag.add(CSimStep(name="csim"))
    dag.add(CSynthStep(name="csynth"))
    dag.add(CoSimStep(name="cosim"))
    dag.add(evaluate)

    # vectors does not consume pysim's output, and no edge pretends otherwise.
    # Checking the model before you trust its answers is a habit, not a data
    # dependency -- and pysim is on the submission path regardless.
    dag.add(GradeReportStep(
        name="submit", graded=[pysim, evaluate],
        bundle=[Path("fsolve.py"), Path("fsolve_eval.py"), Path("fsolve.cpp"),
                Path("tb_fsolve.cpp"), Path("vectors/tv_python.csv"),
                Path("vectors/tv_csim.csv"), Path("vectors/tv_cosim.csv"),
                Path("results/fsolve_hist.png")]))
    return dag


def main() -> None:
    run_graded_dag_cli(
        build_rootsolve_dag,
        graded_steps=graded_steps,
        description="rootsolve — Unit 4 lab: a cubic root solver as a Vitis HLS kernel.",
        default_through="submit",
        root_dir=_SOURCE_DIR,
        extra_args=[
            (("--live-output",), {"action": "store_true",
                                  "help": "Stream Vitis output as it runs instead of "
                                          "capturing it to results/<stage>/vitis.log."}),
        ],
        params_from_args=lambda a: {"live_output": a.live_output},
    )


if __name__ == "__main__":
    main()
