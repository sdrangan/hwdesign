"""Build script for the in-class pipelining exercise.

You edit one file, sqsum.cpp, and run one command:

    python sqsum_build.py                    # check, synthesize, compare: about 3 minutes
    python sqsum_build.py --through timing   # also simulate the RTL and draw the timing

The first checks your kernel against the Python model (golden.py) in C
simulation, synthesizes it beside the reference loop (sqsum_ref.cpp), and
prints the two side by side: the II each loop reached, its latency, its
resources, and any warning Vitis gave about the II.  The second adds an RTL
co-simulation of your kernel and a timing diagram of its memory ports.

    make_inputs -> csim -> verify_csim -> synth -> report -> cosim -> verify_cosim -> vcd -> timing

Steps are skipped when nothing they read has changed, so after an edit to
sqsum.cpp only the steps that depend on it run again.  ``--list-steps``
prints the sequence.  Requires the hwdesign-venv environment (the one with
waveflow) and an installed Vitis HLS.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from waveflow.build.build import BuildConfig, BuildDag, BuildStep, SourceStep
from waveflow.build.cli import run_dag_cli
from waveflow.build.verify_steps import FunctionalVerifyStep
from waveflow.toolchain import toolchain

try:
    from golden import default_x, write_cases, write_golden
except ModuleNotFoundError:  # running from another directory
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from golden import default_x, write_cases, write_golden

_SOURCE_DIR = Path(__file__).resolve().parent
TOP = "sqsum"
SOLUTION = "sol"
PERIOD_NS = 10.0             # 100 MHz
KERNELS = {"ref": "sqsum_ref.cpp", "yours": "sqsum.cpp"}


def _run_stage(config: BuildConfig, stage: str, out_dir: Path, *,
               live_output: bool = False) -> str:
    """Run one stage of run.tcl in the build root; return what Vitis printed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {"SQ_STAGE": stage, "SQ_OUT_DIR": out_dir.as_posix(), "SQ_PERIOD": f"{PERIOD_NS:g}"}
    try:
        result = toolchain.run_vitis_hls(_SOURCE_DIR / "run.tcl", work_dir=config.root_dir,
                                         capture_output=not live_output, env=env)
    except Exception as exc:
        for stream in (getattr(exc, "stdout", None), getattr(exc, "stderr", None)):
            if stream:
                print(stream if isinstance(stream, str) else stream.decode(errors="replace"))
        raise RuntimeError(f"Vitis HLS stage '{stage}' failed: {exc}") from exc
    text = "".join(s if isinstance(s, str) else s.decode(errors="replace")
                   for s in (result.stdout, result.stderr) if s)
    return text


# ------------------------------------------------------------------ reports --
def report_dir(root: Path, kernel: str) -> Path:
    return root / f"proj_{kernel}" / SOLUTION / "syn" / "report"


def read_kernel(root: Path, kernel: str) -> dict:
    """The loop's row of the loop table, the call's latency and the resources,
    from the text synthesis reports."""
    rdir = report_dir(root, kernel)
    top_rpt = rdir / f"{TOP}_csynth.rpt"
    if not top_rpt.exists():
        raise RuntimeError(f"No synthesis report at {top_rpt}.")
    loops = []
    for rpt in sorted(rdir.glob("*_csynth.rpt")):
        for line in rpt.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*\|\s*[-+o]\s+(\S+)\s*\|(.*)\|\s*$", line)
            if not m:
                continue
            cells = [c.strip() for c in m.group(2).split("|")]
            if len(cells) == 7:     # min, max, iteration latency, II achieved, II target, trip, pipelined
                loops.append({"loop": m.group(1), "file": rpt.name, "latency": cells[1],
                              "iteration_latency": cells[2], "ii": cells[3],
                              "ii_target": cells[4], "trip_count": cells[5],
                              "pipelined": cells[6]})
    text = top_rpt.read_text(encoding="utf-8", errors="replace")
    lat = re.search(r"Latency \(cycles\).*?\n(?:.*\n){2}\s*\|\s*(\d+)\|\s*(\d+)\|", text)
    tot = re.search(r"^\|Total\s*\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|", text, re.M)
    return {"kernel": kernel, "loops": loops,
            "call_cycles": int(lat.group(2)) if lat else None,
            "bram": int(tot.group(1)) if tot else None, "dsp": int(tot.group(2)) if tot else None,
            "ff": int(tot.group(3)) if tot else None, "lut": int(tot.group(4)) if tot else None}


def ii_warnings(log: str) -> dict[str, list[str]]:
    """The II warnings Vitis printed while synthesizing each kernel: HLS 200-885
    (not enough memory ports) and 200-880 (a loop-carried dependence)."""
    out, current = {k: [] for k in KERNELS}, None
    for line in log.splitlines():
        m = re.search(r"SQ_SYNTH: (\w+)", line)
        if m:
            current = m.group(1)
            continue
        m = re.search(r"\[HLS 200-88[05]\]\s*(.*)", line)
        if m and current in out:
            msg = re.sub(r"\s+", " ", m.group(1)).strip()
            if msg not in out[current]:
                out[current].append(msg)
    return out


def format_report(rows: list[dict], warnings: dict, root: Path) -> str:
    ref, yours = rows
    def loop(r, key):
        return ", ".join(l[key] for l in r["loops"]) or "-"
    table = [("", "reference", "yours"),
             ("II achieved (target)", f"{loop(ref, 'ii')} ({loop(ref, 'ii_target')})",
              f"{loop(yours, 'ii')} ({loop(yours, 'ii_target')})"),
             ("Iteration latency", loop(ref, "iteration_latency"), loop(yours, "iteration_latency")),
             ("Trip count", loop(ref, "trip_count"), loop(yours, "trip_count")),
             ("Total cycles, one call", str(ref["call_cycles"]), str(yours["call_cycles"])),
             ("DSP / FF / LUT", f"{ref['dsp']} / {ref['ff']} / {ref['lut']}",
              f"{yours['dsp']} / {yours['ff']} / {yours['lut']}")]
    w = [max(len(r[k]) for r in table) for k in range(3)]
    lines = [""] + ["  ".join(c.ljust(w[k]) for k, c in enumerate(r)) for r in table]
    lines.insert(2, "  ".join("-" * x for x in w))
    for name, label in (("ref", "reference"), ("yours", "yours")):
        lines.append("")
        if warnings.get(name):
            lines.append(f"Vitis warnings about the II, {label}:")
            lines += [f"  - {m}" for m in warnings[name]]
        else:
            lines.append(f"No II warnings for {label}.")
    files = sorted({l["file"] for l in yours["loops"]}) or [f"{TOP}_csynth.rpt"]
    rel = report_dir(root, "yours").relative_to(root).as_posix()
    lines += ["", "Your full synthesis report (the loop is in the Loop table):"]
    lines += [f"  {rel}/{f}" for f in files]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- steps --
@dataclass(kw_only=True)
class MakeInputsStep(BuildStep):
    description = "Write data/cases.txt and the expected results from golden.py."
    consumes = ["golden_py"]
    produces = {"cases": Path("data/cases.txt"), "golden_dir": Path("results/golden")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        x = default_x()
        cases = write_cases(config.root_dir / "data" / "cases.txt", x)
        golden_dir = config.root_dir / "results" / "golden"
        write_golden(golden_dir / "results.json", x)
        return {"cases": cases, "golden_dir": golden_dir}


@dataclass(kw_only=True)
class CSimStep(BuildStep):
    description = "Run your kernel in C simulation into results/csim."
    consumes = ["sqsum_cpp", "sqsum_h", "tb_cpp", "run_tcl", "cases"]
    produces = {"csim_dir": Path("results/csim")}
    params = {"live_output": False}

    def run(self, config: BuildConfig, cases, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "csim"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        _run_stage(config, "csim", out_dir, live_output=live_output)
        return {"csim_dir": out_dir}


@dataclass(kw_only=True)
class SynthStep(BuildStep):
    description = "Synthesize the reference and your kernel."
    consumes = ["sqsum_cpp", "sqsum_ref_cpp", "sqsum_h", "run_tcl", "verify_report"]
    # A marker file, not the projects: co-simulation writes into those too.
    produces = {"synth_done": Path("results/synth/warnings.json")}
    params = {"live_output": False}

    def run(self, config: BuildConfig, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "synth"
        log = _run_stage(config, "synth", out_dir, live_output=live_output)
        (out_dir / "vitis.log").write_text(log, encoding="utf-8")
        marker = out_dir / "warnings.json"
        marker.write_text(json.dumps(ii_warnings(log), indent=2) + "\n", encoding="utf-8")
        return {"synth_done": marker}


@dataclass(kw_only=True)
class ReportStep(BuildStep):
    description = "Print the two kernels side by side; write results/report.txt."
    consumes = ["synth_done"]
    produces = {"report": Path("results/report.txt")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, synth_done, **_) -> dict:
        rows = [read_kernel(config.root_dir, k) for k in KERNELS]
        warnings = json.loads(Path(synth_done).read_text(encoding="utf-8"))
        text = format_report(rows, warnings, config.root_dir)
        out = config.root_dir / "results" / "report.txt"
        out.write_text(text, encoding="utf-8")
        (config.root_dir / "results" / "report.json").write_text(
            json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(text)
        return {"report": out}


@dataclass(kw_only=True)
class CoSimStep(BuildStep):
    description = "Run RTL co-simulation of your kernel."
    # The report too, so a run through the timing diagram prints it first.
    consumes = ["tb_cpp", "run_tcl", "cases", "synth_done", "report"]
    produces = {"cosim_dir": Path("results/cosim")}
    params = {"live_output": False}

    def run(self, config: BuildConfig, cases, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "cosim"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        try:
            # Co-simulation sometimes fails within seconds, at "Instrumenting C
            # test bench" -- the transient failure the other demos retry.
            for wait_s in (15, 30, None):
                try:
                    _run_stage(config, "cosim", out_dir, live_output=live_output)
                    break
                except RuntimeError:
                    if wait_s is None:
                        raise
                    print(f"Co-simulation failed; retrying in {wait_s} s.")
                    time.sleep(wait_s)
        except RuntimeError:
            shutil.rmtree(out_dir, ignore_errors=True)
            raise
        return {"cosim_dir": out_dir}


@dataclass(kw_only=True)
class ExtractVcdStep(BuildStep):
    description = "Re-run the RTL simulation with VCD logging into vcd/yours.vcd."
    consumes = ["verify_cosim_report"]
    produces = {"vcd": Path("vcd/yours.vcd")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        from waveflow.scripts.xsim_vcd import run_xsim_vcd
        vcd = Path(run_xsim_vcd(top=TOP, comp="proj_yours", soln=SOLUTION, out="yours.vcd",
                                trace_level="port", workdir=config.root_dir))
        return {"vcd": vcd}


@dataclass(kw_only=True)
class TimingStep(BuildStep):
    description = "Draw your kernel's memory ports from the VCD: results/timing.png."
    consumes = ["vcd"]
    produces = {"timing": Path("results/timing.png")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, vcd, **_) -> dict:
        png = config.root_dir / "results" / "timing.png"
        measured = write_timing_diagram(Path(vcd), png)
        (config.root_dir / "results" / "timing.json").write_text(
            json.dumps(measured, indent=2) + "\n", encoding="utf-8")
        print(f"Simulated: {measured['call_cycles']} cycles for {measured['n']} outputs; "
              f"the first y written {measured['first_write_cycle']} cycles after ap_start.")
        print(f"Timing diagram: {png.relative_to(config.root_dir).as_posix()}")
        return {"timing": png}


# ----------------------------------------------------------- timing diagram --
def _short(name: str) -> str:
    return name.split(".")[-1].split("[")[0]


def _find(names: list[str], short: str) -> str:
    hits = [s for s in names if _short(s) == short]
    if not hits:
        raise RuntimeError(f"No signal named {short!r} in the VCD.")
    return min(hits, key=len)        # the top-level port: the shortest path


def write_timing_diagram(vcd_path: Path, png_path: Path, ncycles: int = 24) -> dict:
    """ap_start, the x reads and the y writes for the first cycles of the call."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from vcdvcd import VCDVCD
    from waveflow.utils.timing import SigTimingInfo, TimingDiagram
    from waveflow.utils.vcd import VcdParser

    vcd = VCDVCD(str(vcd_path), signals=None, store_tvs=True)
    names = list(vcd.signals)
    vp = VcdParser(vcd)
    vp.add_clock_signal()
    for short, kind in (("ap_start", None), ("x_ce0", None), ("x_address0", "uint"),
                        ("y_we0", None), ("y_address0", "uint"), ("ap_done", None)):
        kw = {"numeric_type": kind, "numeric_fmt_str": "%d"} if kind else {}
        vp.add_signal(_find(names, short), short_name=short, **kw)
    sigs = {s.name: s for s in vp.get_td_signals()}

    def first(sig, after=-1.0):
        return next(t for t, v in zip(sigs[sig].times, sigs[sig].values) if v == "1" and t > after)

    start = first("ap_start")
    done = first("ap_done", start)
    we = sigs["y_we0"]
    first_write = next(t for t, v in zip(we.times, we.values) if v == "1" and t > start)
    t0, t1 = start - 2 * PERIOD_NS, start + ncycles * PERIOD_NS

    td = TimingDiagram()
    for s in vp.get_td_signals():
        keep = [k for k, t in enumerate(s.times) if t < t1]
        td.add_signal(SigTimingInfo(s.name, [s.times[k] for k in keep],
                                    [s.values[k] for k in keep], is_clock=s.is_clock))
    ax = td.plot_signals(add_clk_grid=True, trange=(t0, t1), fig_width=12.0, text_mode="always")
    ax.set_xlabel("time [ns]")
    ax.set_title("Your kernel: the x reads and y writes at the start of the call",
                 loc="left", fontsize=12)
    fig = ax.get_figure()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=200, bbox_inches="tight", pad_inches=0.06,
                metadata={"Software": None, "Date": None})
    plt.close(fig)
    return {"n": len(default_x()), "call_cycles": round((done - start) / PERIOD_NS),
            "first_write_cycle": round((first_write - start) / PERIOD_NS)}


# ----------------------------------------------------------------------- dag --
_RESULTS = [{"filename": "results.json", "compare_fields": ["n", "y_bits"]}]


def build_dag() -> BuildDag:
    dag = BuildDag()
    for artifact, path in (("sqsum_cpp", "sqsum.cpp"), ("sqsum_ref_cpp", "sqsum_ref.cpp"),
                           ("sqsum_h", "sqsum.h"), ("tb_cpp", "tb_sqsum.cpp"),
                           ("run_tcl", "run.tcl"), ("golden_py", "golden.py")):
        dag.add(SourceStep(artifact=artifact, path=_SOURCE_DIR / path))
    dag.add(MakeInputsStep(name="make_inputs"))
    dag.add(CSimStep(name="csim"))
    dag.add(FunctionalVerifyStep(name="verify_csim", golden_dir_artifact="golden_dir",
                                 actual_dir_artifact="csim_dir", jsons=_RESULTS,
                                 report_path="results/verify_csim.json",
                                 report_artifact="verify_report"))
    dag.add(SynthStep(name="synth"))
    dag.add(ReportStep(name="report"))
    dag.add(CoSimStep(name="cosim"))
    dag.add(FunctionalVerifyStep(name="verify_cosim", golden_dir_artifact="golden_dir",
                                 actual_dir_artifact="cosim_dir", jsons=_RESULTS,
                                 report_path="results/verify_cosim.json",
                                 report_artifact="verify_cosim_report"))
    dag.add(ExtractVcdStep(name="vcd"))
    dag.add(TimingStep(name="timing"))
    return dag


def main() -> None:
    run_dag_cli(
        build_dag,
        description="The in-class pipelining exercise: build your sqsum.cpp beside the "
                    "reference and compare.",
        default_through="report",
        root_dir=_SOURCE_DIR,
        extra_args=[(("--live-output",), {"action": "store_true",
                                          "help": "Stream Vitis output instead of capturing it."})],
        params_from_args=lambda a: {"live_output": a.live_output},
    )


if __name__ == "__main__":
    main()
