"""stereo -- the Unit 8 lab build: stereo block matching in Vitis HLS.

Four graded stages, in the order you do them::

    python stereo_build.py --list-steps-verbose   # what the steps are
    python stereo_build.py --through pysim        # 1. the golden model, scored
    python stereo_build.py --through base         # 2. the baseline kernel, scored
    python stereo_build.py --through opt          # 3. the optimized kernel, scored
    python stereo_build.py --through timing       # 4. co-simulation and its timing, scored
    python stereo_build.py                        # everything, then the submission zip
    python stereo_build.py --grades               # your scores, without rebuilding

``pysim`` grades stereo.py: shift_image(), disparity_map() and the figure, and
writes the vectors every later stage uses -- the lab's scene, and your model's
disparity map of it.  ``base`` runs stereo_base.cpp in C simulation and
synthesis; ``opt`` does the same for stereo.cpp.  ``cosim`` co-simulates
stereo.cpp and records its ports (about four minutes); ``timing`` grades the
co-simulation's answer, and your stereo_timing.py's reading of its ports.

A failed Vitis run does not stop the build: the stage that ran it scores zero
and says why, and the next build tries again.

YOU DO NOT NEED TO EDIT THIS FILE.  Your work goes in stereo.py,
stereo_base.cpp, stereo.cpp and stereo_timing.py.
"""
from __future__ import annotations

import bisect
import importlib.util
import json
import os
import re
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
# Here rather than in your files, so that the grader agrees with itself
# whatever a submission does to its own constants.  They repeat stereo.h and
# the top of stereo.py on purpose.
# ---------------------------------------------------------------------------

#: The image size, the disparities searched, and the window half-width.
H, W = 96, 128
NDISP = 16
HALF = 2

#: The scene every kernel is run on, shipped with the lab.
SCENE = ("scene_left.png", "scene_right.png")

#: The test images pysim draws: a seed, so that "pixel (40, 60) is wrong" names
#: the same pixel on your machine as on anybody else's.
TEST_SEED = 20261115
SHIFT_D = 6

#: The optimized kernel's targets.  A whole call -- load, compute and store,
#: one after the other -- is about 3*H*W = 36,864 cycles at one pixel per cycle
#: in each phase; LATENCY_MAX leaves room for the pipelines to fill and drain.
LATENCY_MAX = 40_000
#: The Zynq-7020 on the Pynq-Z2.
DEVICE = {"bram": 280, "dsp": 220, "ff": 106_400, "lut": 53_200}


def interior_mask() -> np.ndarray:
    """True where stereo.h's specification computes a disparity."""
    rows = (np.arange(H) >= HALF) & (np.arange(H) < H - HALF)
    cols = (np.arange(W) >= HALF + NDISP - 1) & (np.arange(W) < W - HALF)
    return np.outer(rows, cols)


def load_student_module(source_dir: Path, name: str):
    """Import one of your modules by path, freshly, whatever the working directory."""
    path = Path(source_dir) / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_png(path: Path) -> np.ndarray:
    from PIL import Image
    with Image.open(path) as im:
        return np.array(im.convert("L"), dtype=np.uint8)


def write_image(path: Path, img: np.ndarray) -> Path:
    """H rows of W integers: the format tb_stereo.cpp reads and writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, np.asarray(img, dtype=np.int64), fmt="%d")
    return path


def read_image(path: Path) -> np.ndarray | None:
    """An image written by write_image or the testbench, or None if it is not one."""
    try:
        img = np.loadtxt(path, dtype=np.int64, ndmin=2)
    except Exception:  # noqa: BLE001 -- unreadable is the same as absent
        return None
    return img if img.shape == (H, W) else None


# ---------------------------------------------------------------------------
# Stage 1 -- the golden model
# ---------------------------------------------------------------------------

def shifted(img: np.ndarray, d: int) -> np.ndarray:
    """The grader's own shift: the last column repeated d times on the right."""
    if d == 0:
        return img.copy()
    pad = np.repeat(img[:, -1:], d, axis=1)
    return np.concatenate([img[:, d:], pad], axis=1)


def layered_test_scene(seed: int):
    """Three flat layers of independent random pixels, at disparities 3, 9 and 14.

    Returns (left, right, truth, safe).  `safe` marks the interior pixels whose
    5x5 window shows one layer only, in the left image and in the right image
    at that layer's disparity.  There the true disparity matches with SAD 0,
    and with independent random pixels no other disparity does: any correct
    model gets exactly the truth.
    """
    rng = np.random.default_rng(seed)
    wide = W + NDISP
    rows, cols = np.mgrid[0:H, 0:wide]
    layers = [(3, np.ones((H, wide), dtype=bool)),
              (9, (rows >= 14) & (rows < 80) & (cols >= 26) & (cols < 66)),
              (14, (rows >= 22) & (rows < 74) & (cols >= 82) & (cols < 118))]
    left = np.zeros((H, W), dtype=np.uint8)
    right = np.zeros((H, W), dtype=np.uint8)
    lab_l = np.zeros((H, W), dtype=np.int64)
    lab_r = np.zeros((H, W), dtype=np.int64)
    for k, (d, mask) in enumerate(layers):
        tex = rng.integers(0, 256, size=(H, wide), dtype=np.int64).astype(np.uint8)
        m_l, m_r = mask[:, :W], mask[:, d:d + W]
        left[m_l], lab_l[m_l] = tex[:, :W][m_l], k
        right[m_r], lab_r[m_r] = tex[:, d:d + W][m_r], k
    truth = np.array([d for d, _ in layers])[lab_l].astype(np.uint8)

    safe = np.zeros((H, W), dtype=bool)
    inside = interior_mask()
    for y, x in zip(*np.nonzero(inside)):
        k = lab_l[y, x]
        d = layers[k][0]
        win_l = lab_l[y - HALF:y + HALF + 1, x - HALF:x + HALF + 1]
        win_r = lab_r[y - HALF:y + HALF + 1, x - HALF - d:x + HALF + 1 - d]
        safe[y, x] = bool((win_l == k).all() and (win_r == k).all())
    return left, right, truth, safe


def conform_disparity(value: Any) -> np.ndarray:
    """What disparity_map returned, as an (H, W) array, or ValueError saying why not."""
    if value is None:
        raise ValueError("disparity_map returned None -- it has no `return` statement")
    arr = np.asarray(value)
    if arr.shape != (H, W):
        raise ValueError(f"disparity_map returned shape {arr.shape}, not ({H}, {W})")
    return arr


def check_model(checks: Checks, model: Any) -> bool:
    """Score shift_image and disparity_map.  Returns whether the model is right
    on everything checked, which the kernel stages need before they compare."""
    rng = np.random.default_rng(TEST_SEED)
    img = rng.integers(0, 256, size=(H, W), dtype=np.int64).astype(np.uint8)

    # --- shift_image ----------------------------------------------------------
    label = f"shift_image(img, {SHIFT_D}) moves the image {SHIFT_D} pixels left"
    note = ""
    try:
        got = np.asarray(model.shift_image(img.copy(), SHIFT_D))
        want = shifted(img, SHIFT_D)
        if got.shape != want.shape:
            note = f"it returned shape {got.shape}, not {want.shape}"
        elif not np.array_equal(got.astype(np.int64), want.astype(np.int64)):
            y, x = np.argwhere(got.astype(np.int64) != want.astype(np.int64))[0]
            note = (f"R[{y}][{x}] is {int(got[y, x])}; it should be img[{y}][{min(x + SHIFT_D, W - 1)}]"
                    f" = {int(want[y, x])}")
    except Exception as exc:  # noqa: BLE001 -- any student error is a zero, not a crash
        note = f"shift_image raised {type(exc).__name__}: {exc}"
    checks.that(not note, 2, label, note)

    def run(left, right):
        return conform_disparity(model.disparity_map(left.copy(), right.copy()))

    # --- the shape of the answer ---------------------------------------------
    label = "disparity_map returns uint8 values below NDISP, and 0 outside the interior"
    note = ""
    try:
        other = rng.integers(0, 256, size=(H, W), dtype=np.int64).astype(np.uint8)
        disp = run(img, other)
        outside = disp[~interior_mask()]
        if disp.dtype != np.uint8:
            note = f"the array's dtype is {disp.dtype}, not uint8"
        elif disp.max() >= NDISP:
            note = f"it has a value {int(disp.max())}; disparities run 0 .. {NDISP - 1}"
        elif outside.any():
            y, x = np.argwhere((disp != 0) & ~interior_mask())[0]
            note = (f"pixel ({y}, {x}) is outside the interior but has disparity "
                    f"{int(disp[y, x])} -- see the border rule in stereo.h")
    except Exception as exc:  # noqa: BLE001
        note = f"disparity_map raised {type(exc).__name__}: {exc}"
    shape_note, shape_label = note, label

    # --- a flat scene at one disparity ----------------------------------------
    label = f"A scene shifted by {SHIFT_D} has disparity {SHIFT_D} everywhere inside"
    note = ""
    try:
        disp = run(img, shifted(img, SHIFT_D))
        wrong = interior_mask() & (disp != SHIFT_D)
        if wrong.any():
            y, x = np.argwhere(wrong)[0]
            note = (f"{int(wrong.sum())} interior pixels are not {SHIFT_D}; the first is "
                    f"({y}, {x}), at {int(disp[y, x])}")
    except Exception as exc:  # noqa: BLE001
        note = f"disparity_map raised {type(exc).__name__}: {exc}"
    flat_ok = checks.that(not note, 2, label, note)
    # An answer of all zeros has the right shape, border and ties for free, so
    # those two checks count only once the model finds a disparity at all.
    gate = "" if flat_ok else "graded once disparity_map finds the disparity of a flat scene"
    shape_ok = checks.that(not shape_note and not gate, 2, shape_label, shape_note or gate)

    # --- three layers -----------------------------------------------------------
    label = "A three-layer scene: the right disparity wherever the window sees one layer"
    left, right, truth, safe = layered_test_scene(TEST_SEED + 1)
    frac, note = 0.0, ""
    try:
        disp = run(left, right)
        good = disp[safe] == truth[safe]
        frac = float(good.mean())
        if not good.all():
            y, x = np.argwhere(safe & (disp != truth))[0]
            note = (f"{int((~good).sum())} of {int(safe.sum())} such pixels are wrong; the "
                    f"first is ({y}, {x}): {int(disp[y, x])}, where the scene is at "
                    f"{int(truth[y, x])}")
    except Exception as exc:  # noqa: BLE001
        note = f"disparity_map raised {type(exc).__name__}: {exc}"
    checks.fraction(frac, 2, label, note)

    # --- ties ---------------------------------------------------------------------
    label = "On a tie the smallest disparity wins: a blank scene is 0 everywhere"
    note = ""
    try:
        blank = np.full((H, W), 128, dtype=np.uint8)
        disp = run(blank, blank)
        if disp.any():
            note = (f"every SAD is 0 on a blank scene, so every disparity ties and the "
                    f"answer is 0 -- but {int((disp != 0).sum())} pixels are not")
    except Exception as exc:  # noqa: BLE001
        note = f"disparity_map raised {type(exc).__name__}: {exc}"
    tie_ok = checks.that(not note and not gate, 1, label, note or gate)

    return shape_ok and flat_ok and frac == 1.0 and tie_ok


def _placeholder_figure(path: Path, message: str) -> None:
    """A stand-in PNG, so a declared artifact exists when no figure was drawn."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(8.0, 3.0))
    fig.text(0.5, 0.5, message, ha="center", va="center", color="0.4")
    fig.savefig(path, dpi=100)
    plt.close(fig)


@dataclass(kw_only=True)
class PySimStep(GradedStep):
    description = "Grade stereo.py, and write the scene and your model's disparity map of it."
    points = 10.0
    outputs = {"disparity_figure": Path("results/disparity.png"),
               "left_vec": Path("vectors/left.txt"),
               "right_vec": Path("vectors/right.txt"),
               "py_disp": Path("vectors/disp_python.txt"),
               "golden": Path("results/golden.json")}
    consumes = ["stereo_py_src", "scene_left", "scene_right"]

    def evaluate(self, config: BuildConfig, **_) -> GradeResult:
        root = Path(config.root_dir)
        checks = Checks()
        left = read_png(root / SCENE[0])
        right = read_png(root / SCENE[1])
        write_image(root / "vectors/left.txt", left)
        write_image(root / "vectors/right.txt", right)

        model, failure = None, ""
        try:
            model = load_student_module(root, "stereo")
        except Exception as exc:  # noqa: BLE001
            failure = f"stereo.py raised {type(exc).__name__}: {exc}"

        if model is None:
            for points, label in ((2, "shift_image"), (2, "disparity_map's shape"),
                                  (2, "a flat scene"), (2, "a three-layer scene"),
                                  (1, "ties"), (1, "the figure")):
                checks.zero(points, label, "stereo.py could not be loaded")
            model_ok = False
        else:
            model_ok = check_model(checks, model)

        # Your model's answer on the lab's scene: what every kernel is held to.
        disp = np.zeros((H, W), dtype=np.int64)
        try:
            if model is not None:
                disp = conform_disparity(model.disparity_map(left.copy(), right.copy()))
        except Exception as exc:  # noqa: BLE001
            checks.note(f"disparity_map on the lab's scene raised {type(exc).__name__}: {exc}")
        write_image(root / "vectors/disp_python.txt", disp)

        figure = root / "results/disparity.png"
        figure.parent.mkdir(parents=True, exist_ok=True)
        figure.unlink(missing_ok=True)
        try:
            if model is not None:
                model.plot_disparity(left, right, np.asarray(disp, dtype=np.uint8), figure)
        except Exception as exc:  # noqa: BLE001
            checks.note(f"plot_disparity raised {type(exc).__name__}: {exc}")
        if model is not None:
            drew = figure.exists() and figure.stat().st_size > 0
            checks.that(drew, 1, "You drew the scene and its disparity map",
                        f"no figure was written to {figure.name} -- plot_disparity must save one")
        if not (figure.exists() and figure.stat().st_size > 0):
            _placeholder_figure(figure, "no disparity figure was drawn")

        golden = root / "results/golden.json"
        golden.write_text(json.dumps({"ok": bool(model_ok)}), encoding="utf-8")
        if failure:
            checks.note(failure)
        return checks.result(disparity_figure=figure, left_vec=root / "vectors/left.txt",
                             right_vec=root / "vectors/right.txt",
                             py_disp=root / "vectors/disp_python.txt", golden=golden)


# ---------------------------------------------------------------------------
# Running Vitis, and reading what it reports
# ---------------------------------------------------------------------------

def run_vitis_stage(root: Path, stage: str, live_output: bool) -> tuple[bool, str, Path]:
    """Run one stage of run.tcl.  Returns (ok, message, log); never raises."""
    from waveflow.toolchain import toolchain

    log = root / "results" / stage / "vitis.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = toolchain.run_vitis_hls(root / "run.tcl", work_dir=root,
                                         capture_output=not live_output,
                                         env={"STEREO_STAGE": stage})
        text, ok, message = (result.stdout or "") + (result.stderr or ""), True, ""
    except subprocess.CalledProcessError as exc:
        text = (exc.stdout or "") + (exc.stderr or "")
        ok, message = False, f"Vitis exited with status {exc.returncode}"
    except Exception as exc:  # noqa: BLE001 -- most often: Vitis is not installed or not found
        text, ok, message = "", False, f"{type(exc).__name__}: {exc}"
    log.write_text(text if isinstance(text, str) else text.decode(errors="replace"),
                   encoding="utf-8")
    if not ok:
        lines = [ln.strip() for ln in log.read_text(encoding="utf-8").splitlines()]
        errors = ([ln for ln in lines if ": error:" in ln][:3]
                  + [ln for ln in lines if ln.startswith("ERROR")])[:4]
        if errors:
            message += ":\n      " + "\n      ".join(errors)
    return ok, message, log


def read_report(report: Path) -> dict[str, Any]:
    """The loops, the call's worst-case latency and the resources, from a
    csynth report and the reports of the functions beside it."""
    out = {"loops": [], "latency": None, "resources": {}}
    if not report.exists():
        return out
    seen = set()
    for rpt in [report] + sorted(p for p in report.parent.glob("*_csynth.rpt") if p != report):
        for line in rpt.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*\|\s*[-+o]\s+(\S+)\s*\|(.*)\|\s*$", line)
            if not m or m.group(1) in seen:
                continue
            cells = [c.strip() for c in m.group(2).split("|")]
            if len(cells) == 7:   # min, max, iteration latency, II achieved, II target, trip, pipelined
                seen.add(m.group(1))
                out["loops"].append({"loop": m.group(1), "ii": cells[3],
                                     "trip": cells[5], "pipelined": cells[6].lower()})
    text = report.read_text(encoding="utf-8", errors="replace")
    lat = re.search(r"Latency \(cycles\).*?\n(?:.*\n){2}\s*\|\s*(\d+)\|\s*(\d+)\|", text)
    if lat:
        out["latency"] = int(lat.group(2))
    tot = re.search(r"^\|Total\s*\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|", text, re.M)
    if tot:
        out["resources"] = dict(zip(("bram", "dsp", "ff", "lut"), map(int, tot.groups())))
    return out


def golden_problem(root: Path) -> str:
    """Why your model's disparity map cannot be used to judge a kernel, or ""."""
    try:
        ok = json.loads((root / "results/golden.json").read_text(encoding="utf-8"))["ok"]
    except Exception:  # noqa: BLE001
        ok = False
    if not ok:
        return ("your golden model does not pass pysim yet, so there is nothing right to "
                "compare the kernel against -- fix stereo.py first")
    return ""


def compare_with_model(checks: Checks, points: float, label: str, root: Path,
                       ran: bool, why: str, got_path: Path) -> None:
    """Score a kernel's disparity map against your model's, pixel for pixel."""
    problem = golden_problem(root)
    if problem:
        checks.zero(points, label, problem)
        return
    if not ran:
        checks.zero(points, label, why)
        return
    want = read_image(root / "vectors/disp_python.txt")
    got = read_image(got_path)
    if got is None:
        checks.zero(points, label, f"{got_path.name} is missing or is not {H} rows of {W}")
        return
    # Scored on the interior, where there is something to compute: a kernel
    # that writes nothing gets the border's zeros right for free.  A wrong
    # border halves what the interior earns.
    bad = got != want
    inside = interior_mask()
    frac = float((~bad[inside]).mean())
    note = ""
    if bad.any():
        y, x = np.argwhere(bad)[0]
        note = (f"{int(bad.sum())} of {H * W} pixels differ from your model; the first is "
                f"({y}, {x}): the kernel says {int(got[y, x])}, the model {int(want[y, x])}")
        if bad[~inside].any():
            frac *= 0.5
            note += " -- and the border, which must be 0, is wrong too"
    checks.fraction(frac, points, label, note)


def _copy_report(root: Path, proj: str, dest: Path, flat: Path) -> bool:
    """Copy a project's csynth reports into dest's folder, and the top one to
    `flat` too: the submission zip is flat, and two stereo_csynth.rpt collide."""
    made = root / proj / "solution1/syn/report/stereo_csynth.rpt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    for old in dest.parent.glob("*_csynth.rpt"):
        old.unlink()
    if not made.exists():
        dest.write_text("not synthesized\n", encoding="utf-8")
        shutil.copyfile(dest, flat)
        return False
    for rpt in made.parent.glob("*_csynth.rpt"):
        shutil.copyfile(rpt, dest.parent / rpt.name)
    shutil.copyfile(made, flat)
    return True


# ---------------------------------------------------------------------------
# Stage 2 -- the baseline kernel
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class BaseStep(GradedStep):
    description = "C-simulate and synthesize stereo_base.cpp; grade it."
    points = 10.0
    params = {"live_output": False}
    outputs = {"base_disp": Path("vectors/disp_base_csim.txt"),
               "base_report": Path("results/base/stereo_csynth.rpt"),
               "base_flat": Path("results/base_csynth.rpt")}
    consumes = ["stereo_base_cpp_src", "stereo_h", "tb_stereo", "run_tcl", "left_vec",
                "right_vec", "py_disp", "golden"]

    def evaluate(self, config: BuildConfig, live_output=False, **_) -> GradeResult:
        root = Path(config.root_dir)
        checks = Checks()
        disp = root / "vectors/disp_base_csim.txt"
        disp.unlink(missing_ok=True)
        report = root / "results/base/stereo_csynth.rpt"

        ok, message, log = run_vitis_stage(root, "base_csim", live_output)
        why = f"C simulation failed: {message} -- the tool output is in {log.relative_to(root)}"
        compare_with_model(checks, 5, "C simulation of stereo_base.cpp matches your model",
                           root, ok and disp.exists(), why if not ok else
                           "the testbench wrote no vectors/disp_base_csim.txt", disp)

        synth_ok = False
        if ok:
            synth_ok, message, log = run_vitis_stage(root, "base_csynth", live_output)
        made = _copy_report(root, "base_proj", report, root / "results/base_csynth.rpt") and synth_ok
        rpt = read_report(report)
        piped = [l["loop"] for l in rpt["loops"] if l["pipelined"] == "yes"]
        has_comp = any("comp" in l["loop"] for l in rpt["loops"])
        checks.that(made and has_comp, 2, "stereo_base.cpp synthesizes, compute phase and all",
                    "skipped: C simulation did not succeed" if not ok else
                    f"synthesis failed: {message} -- see {log.relative_to(root)}" if not made else
                    "the report has no compute loop -- write the compute phase, with its loops "
                    "labeled comp_y, comp_x, ...")
        if not made:
            checks.zero(3, "Every loop is left unpipelined", "there is no synthesis report")
        elif not has_comp:
            checks.zero(3, "Every loop is left unpipelined",
                        "the report has no compute loop -- write the compute phase, with its "
                        "loops labeled comp_y, comp_x, ...")
        else:
            checks.that(not piped and bool(rpt["loops"]), 3, "Every loop is left unpipelined",
                        f"the report shows {', '.join(piped)} pipelined -- the baseline needs "
                        f"`#pragma HLS PIPELINE off` in every loop" if piped else
                        "the report lists no loops")
            if rpt["latency"]:
                checks.note(f"  worst-case latency of one call: {rpt['latency']:,} cycles, "
                            f"{rpt['latency'] / (H * W):.0f} per pixel")
        if not disp.exists():
            write_image(disp, np.zeros((H, W), dtype=np.int64))
        return checks.result(base_disp=disp, base_report=report,
                             base_flat=root / "results/base_csynth.rpt")


# ---------------------------------------------------------------------------
# Stage 3 -- the optimized kernel
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class OptStep(GradedStep):
    description = "C-simulate and synthesize stereo.cpp; grade its II, latency and size."
    points = 10.0
    params = {"live_output": False}
    outputs = {"opt_disp": Path("vectors/disp_csim.txt"),
               "opt_report": Path("results/opt/stereo_csynth.rpt"),
               "opt_flat": Path("results/opt_csynth.rpt"),
               "opt_status": Path("results/opt/status.json")}
    consumes = ["stereo_cpp_src", "stereo_h", "tb_stereo", "run_tcl", "left_vec",
                "right_vec", "py_disp", "golden"]

    def evaluate(self, config: BuildConfig, live_output=False, **_) -> GradeResult:
        root = Path(config.root_dir)
        checks = Checks()
        disp = root / "vectors/disp_csim.txt"
        disp.unlink(missing_ok=True)
        report = root / "results/opt/stereo_csynth.rpt"

        ok, message, log = run_vitis_stage(root, "csim", live_output)
        why = f"C simulation failed: {message} -- the tool output is in {log.relative_to(root)}"
        compare_with_model(checks, 3, "C simulation of stereo.cpp matches your model", root,
                           ok and disp.exists(), why if not ok else
                           "the testbench wrote no vectors/disp_csim.txt", disp)

        synth_ok = False
        if ok:
            synth_ok, message, log = run_vitis_stage(root, "csynth", live_output)
        made = _copy_report(root, "stereo_proj", report, root / "results/opt_csynth.rpt") and synth_ok
        rpt = read_report(report)

        label = "The compute loop is pipelined at II = 1"
        comp = [l for l in rpt["loops"] if "comp" in l["loop"] and l["pipelined"] == "yes"]
        if not made:
            checks.zero(4, label, "skipped: C simulation did not succeed" if not ok else
                        f"synthesis failed: {message} -- see {log.relative_to(root)}")
        elif not comp:
            names = ", ".join(f"{l['loop']} ({'pipelined' if l['pipelined'] == 'yes' else 'not pipelined'})"
                              for l in rpt["loops"]) or "none"
            checks.zero(4, label, f"no pipelined loop has `comp` in its name -- label the compute "
                                  f"loops comp_y and comp_x.  The report's loops: {names}")
        else:
            iis = [l["ii"] for l in comp]
            checks.that(all(ii == "1" for ii in iis), 4, label,
                        f"{comp[0]['loop']} reached II = {iis[0]}; the synthesis log says why "
                        f"(search it for 'II Violation')")

        # The latency and the size are only worth points for a kernel that
        # computes: one with no compute loop is short and small for free.
        ii_ok = bool(made and comp and all(l["ii"] == "1" for l in comp))
        label = f"A whole call takes at most {LATENCY_MAX:,} cycles"
        if made and not ii_ok:
            checks.zero(1, label, "graded once the compute loop reaches II = 1")
        elif not made or rpt["latency"] is None:
            checks.zero(1, label, "there is no synthesis report to read it from")
        else:
            checks.that(rpt["latency"] <= LATENCY_MAX, 1, label,
                        f"the report's worst case is {rpt['latency']:,} cycles")

        label = "It fits on the Zynq-7020"
        res = rpt["resources"]
        if made and not ii_ok:
            checks.zero(2, label, "graded once the compute loop reaches II = 1")
        elif not made or not res:
            checks.zero(2, label, "there is no synthesis report to read it from")
        else:
            over = [f"{k.upper()} {res[k]:,} of {DEVICE[k]:,}" for k in DEVICE if res[k] > DEVICE[k]]
            checks.that(not over, 2, label, "over: " + ", ".join(over))
            checks.note("  " + ", ".join(f"{k.upper()} {res[k]:,} ({100 * res[k] / DEVICE[k]:.0f}%)"
                                         for k in ("lut", "ff", "bram", "dsp"))
                        + (f"; worst-case latency {rpt['latency']:,} cycles" if rpt["latency"] else ""))

        if not disp.exists():
            write_image(disp, np.zeros((H, W), dtype=np.int64))
        status = root / "results/opt/status.json"
        status.write_text(json.dumps({"synthesized": bool(made)}), encoding="utf-8")
        return checks.result(opt_disp=disp, opt_report=report, opt_status=status,
                             opt_flat=root / "results/opt_csynth.rpt")


# ---------------------------------------------------------------------------
# Co-simulation, and the ports it recorded
# ---------------------------------------------------------------------------

#: The columns of results/cosim/signals.csv, and the port each is read from.
SIGNALS = {"ap_start": "ap_start", "ap_done": "ap_done",
           "in_valid": "pix_in_TVALID", "in_ready": "pix_in_TREADY",
           "out_valid": "disparity_TVALID", "out_ready": "disparity_TREADY"}

#: A failed step's outputs are back-dated so the next build retries it (see
#: rootsolve_build.py); 2000-01-01, since ZIP cannot store times before 1980.
_BACKDATE = 946684800


def extract_signals(vcd_path: Path, out_csv: Path) -> int:
    """One row per rising clock edge, from the start of the call to two cycles after ap_done.
    Each value is the one the port held just before the edge: what the edge saw."""
    from vcdvcd import VCDVCD

    vcd = VCDVCD(str(vcd_path), signals=None, store_tvs=True)

    def find(port: str):
        hits = [s for s in vcd.signals if s.split(".")[-1].split("[")[0] == port]
        if not hits:
            raise RuntimeError(f"no signal {port} in {vcd_path.name}")
        return vcd[min(hits, key=len)].tv

    clk = find("ap_clk")
    edges = [t for k, (t, v) in enumerate(clk) if v == "1" and k > 0]
    columns = {}
    for col, port in SIGNALS.items():
        tv = find(port)
        times = [t for t, _ in tv]
        values = [1 if v == "1" else 0 for _, v in tv]
        columns[col] = [values[bisect.bisect_left(times, t) - 1] if bisect.bisect_left(times, t) else 0
                        for t in edges]
    table = pd.DataFrame(columns)
    # The call starts at ap_start -- or a little before it: Vitis puts a
    # register slice on each AXI4-Stream port, and the input's takes its first
    # two words as soon as they are offered, whether or not the kernel has
    # started.  So cycle 0 is whichever comes first.
    taken = np.flatnonzero((table["in_valid"] * table["in_ready"]).to_numpy())
    start = int(np.flatnonzero(table["ap_start"].to_numpy())[0])
    if taken.size:
        start = min(start, int(taken[0]))
    done = start + int(np.flatnonzero(table["ap_done"].to_numpy()[start:])[0])
    table = table.iloc[start:done + 3].reset_index(drop=True)
    table.insert(0, "cycle", np.arange(len(table)))
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_csv, index=False)
    return done - start


@dataclass(kw_only=True)
class CoSimStep(BuildStep):
    """Co-simulate stereo.cpp's RTL, record its ports, and tabulate them by cycle."""

    description = "Run RTL co-simulation of stereo.cpp (about four minutes) and record its ports."
    params = {"live_output": False}
    consumes = ["tb_stereo", "run_tcl", "left_vec", "right_vec", "opt_report", "opt_status"]
    produces: ClassVar[dict] = {"cosim_disp": Path("vectors/disp_cosim.txt"),
                                "signals": Path("results/cosim/signals.csv"),
                                "cosim_status": Path("results/cosim/status.json")}

    def run(self, config: BuildConfig, live_output=False, **_) -> dict[str, Any]:
        root = Path(config.root_dir)
        disp = root / "vectors/disp_cosim.txt"
        signals = root / "results/cosim/signals.csv"
        status = root / "results/cosim/status.json"
        status.parent.mkdir(parents=True, exist_ok=True)
        disp.unlink(missing_ok=True)
        ok, message = True, ""
        try:
            synthesized = json.loads((root / "results/opt/status.json")
                                     .read_text(encoding="utf-8"))["synthesized"]
        except Exception:  # noqa: BLE001
            synthesized = False
        if not synthesized:
            ok, message = False, "skipped: stereo.cpp did not synthesize -- see the opt stage"
        else:
            ok, message, log = run_vitis_stage(root, "cosim", live_output)
            if not ok:
                message += f" -- the tool output is in {log.relative_to(root)}"
        if ok:
            try:
                from waveflow.scripts.xsim_vcd import run_xsim_vcd
                vcd = Path(run_xsim_vcd(top="stereo", comp="stereo_proj", soln="solution1",
                                        out="stereo.vcd", trace_level="port", workdir=root))
                ncycles = extract_signals(vcd, signals)
                message = f"co-simulated one call in {ncycles:,} cycles; ports in {signals.relative_to(root)}"
            except Exception as exc:  # noqa: BLE001
                ok, message = False, f"reading the waveform failed: {type(exc).__name__}: {exc}"
        if not disp.exists():
            write_image(disp, np.zeros((H, W), dtype=np.int64))
        if not ok or not signals.exists():
            pd.DataFrame(columns=["cycle", *SIGNALS]).to_csv(signals, index=False)
        status.write_text(json.dumps({"ok": ok, "message": message}), encoding="utf-8")
        print(f"    {message}" if ok else f"    x {message}")
        if not ok:
            for path in (status, signals, disp):
                os.utime(path, (_BACKDATE, _BACKDATE))
        return {"cosim_disp": disp, "signals": signals, "cosim_status": status}


# ---------------------------------------------------------------------------
# Stage 4 -- co-simulation and its timing
# ---------------------------------------------------------------------------

def handshake_phases(sig: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """The grader's own reading of the phases, for comparison with yours."""
    def span(valid, ready):
        hit = np.nonzero(sig[valid].to_numpy() * sig[ready].to_numpy())[0]
        return int(sig["cycle"].iloc[hit.min()]), int(sig["cycle"].iloc[hit.max()])
    phases = {"load": span("in_valid", "in_ready"), "store": span("out_valid", "out_ready")}
    phases["compute"] = (phases["load"][1] + 1, phases["store"][0] - 1)
    return phases


@dataclass(kw_only=True)
class TimingStep(GradedStep):
    description = "Grade the co-simulation, and your stereo_timing.py's reading of it."
    points = 10.0
    outputs = {"phase_figure": Path("results/phases.png")}
    consumes = ["stereo_timing_py_src", "cosim_disp", "signals", "cosim_status", "py_disp",
                "golden"]

    def evaluate(self, config: BuildConfig, **_) -> GradeResult:
        root = Path(config.root_dir)
        checks = Checks()
        try:
            status = json.loads((root / "results/cosim/status.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            status = {"ok": False, "message": "the cosim step has not run"}
        compare_with_model(checks, 4, "RTL co-simulation matches your model", root,
                           status["ok"], f"co-simulation did not complete: {status['message']}",
                           root / "vectors/disp_cosim.txt")
        cosim_right = (not golden_problem(root) and status["ok"] and
                       np.array_equal(read_image(root / "vectors/disp_cosim.txt"),
                                      read_image(root / "vectors/disp_python.txt")))

        sig = pd.read_csv(root / "results/cosim/signals.csv")
        figure = root / "results/phases.png"
        figure.parent.mkdir(parents=True, exist_ok=True)
        figure.unlink(missing_ok=True)
        if not status["ok"] or sig.empty:
            for points, label in ((3, "find_phases finds the load, compute and store phases"),
                                  (2, "The phases are one after the other, one word per cycle"),
                                  (1, "You drew the timing diagram")):
                checks.zero(points, label, "there is no co-simulation to read")
            _placeholder_figure(figure, "no co-simulation to draw")
            return checks.result(phase_figure=figure)

        truth = handshake_phases(sig)
        label = "find_phases finds the load, compute and store phases"
        mine, note = None, ""
        try:
            timing = load_student_module(root, "stereo_timing")
            mine = timing.find_phases(sig.copy())
            for name, (lo, hi) in truth.items():
                got = tuple(int(v) for v in mine[name])
                if got != (lo, hi):
                    note = f"{name} is ({got[0]}, {got[1]}); it is ({lo}, {hi})"
                    break
        except Exception as exc:  # noqa: BLE001
            note = f"find_phases raised {type(exc).__name__}: {exc}"
        checks.that(not note, 3, label, note)

        n_in = int((sig["in_valid"] * sig["in_ready"]).sum())
        n_out = int((sig["out_valid"] * sig["out_ready"]).sum())
        load_n = truth["load"][1] - truth["load"][0] + 1
        store_n = truth["store"][1] - truth["store"][0] + 1
        problems = []
        if n_in != H * W or n_out != H * W:
            problems.append(f"{n_in} words in and {n_out} out; expected {H * W} each")
        if load_n > H * W + 16 or store_n > H * W + 16:
            problems.append(f"load took {load_n:,} cycles and store {store_n:,} for {H * W:,} "
                            f"words: not one word per cycle -- pipeline both loops at II = 1")
        total = len(sig) - 3
        if total > LATENCY_MAX:
            problems.append(f"the call took {total:,} cycles, past {LATENCY_MAX:,}")
        if not cosim_right:
            # A kernel that computes nothing streams in and out at full speed.
            problems = ["graded once co-simulation matches your model"]
        checks.that(not problems, 2, "The phases are one after the other, one word per cycle",
                    "; ".join(problems))
        checks.note("  " + ", ".join(f"{k} {hi - lo + 1:,}" for k, (lo, hi) in truth.items())
                    + f" cycles; the call {total:,}")

        try:
            timing = load_student_module(root, "stereo_timing")
            timing.plot_phases(sig.copy(), mine if mine else truth, figure)
        except Exception as exc:  # noqa: BLE001
            checks.note(f"plot_phases raised {type(exc).__name__}: {exc}")
        drew = figure.exists() and figure.stat().st_size > 0
        checks.that(drew, 1, "You drew the timing diagram",
                    f"no figure was written to {figure.name} -- plot_phases must save one")
        if not drew:
            _placeholder_figure(figure, "no timing diagram was drawn")
        return checks.result(phase_figure=figure)


# ---------------------------------------------------------------------------
# The graph
# ---------------------------------------------------------------------------

def lab_steps():
    """Your four files, and the four stages that grade them."""
    py_src = StudentSourceStep(artifact="stereo_py_src", path=Path("stereo.py"))
    base_src = StudentSourceStep(artifact="stereo_base_cpp_src", path=Path("stereo_base.cpp"))
    opt_src = StudentSourceStep(artifact="stereo_cpp_src", path=Path("stereo.cpp"))
    timing_src = StudentSourceStep(artifact="stereo_timing_py_src", path=Path("stereo_timing.py"))
    graded = [PySimStep(name="pysim", title="The golden model", starts_from=[py_src]),
              BaseStep(name="base", title="The baseline kernel", starts_from=[base_src]),
              OptStep(name="opt", title="The optimized kernel", starts_from=[opt_src]),
              TimingStep(name="timing", title="Co-simulation and its timing",
                         starts_from=[timing_src, opt_src])]
    return [py_src, base_src, opt_src, timing_src], graded


def graded_steps() -> list[GradedStep]:
    return lab_steps()[1]


def build_stereo_dag() -> BuildDag:
    dag = BuildDag()
    sources, (pysim, base, opt, timing) = lab_steps()
    for src in sources:
        dag.add(src)
    for artifact, path in (("stereo_h", "stereo.h"), ("tb_stereo", "tb_stereo.cpp"),
                           ("run_tcl", "run.tcl"), ("scene_left", SCENE[0]),
                           ("scene_right", SCENE[1])):
        dag.add(SourceStep(artifact=artifact, path=_SOURCE_DIR / path))
    dag.add(pysim)
    dag.add(base)
    dag.add(opt)
    dag.add(CoSimStep(name="cosim"))
    dag.add(timing)
    dag.add(GradeReportStep(
        name="submit", graded=[pysim, base, opt, timing],
        bundle=[Path("stereo.py"), Path("stereo_base.cpp"), Path("stereo.cpp"),
                Path("stereo_timing.py"), Path("results/disparity.png"),
                Path("results/phases.png"), Path("results/base_csynth.rpt"),
                Path("results/opt_csynth.rpt")]))
    return dag


def main() -> None:
    run_graded_dag_cli(
        build_stereo_dag,
        graded_steps=graded_steps,
        description="stereo -- Unit 8 lab: stereo block matching as a Vitis HLS kernel.",
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
