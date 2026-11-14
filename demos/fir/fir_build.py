"""Build script for the FIR demo: one nested loop, written four ways.

The kernel (``fir.cpp``), the testbench (``tb_fir.cpp``) and the Vitis script
(``run.tcl``) are hand-written.  This file adds the sequence:

    make_inputs -> csim -> verify_csim_<variant> (x4) -> synth -> report
                                                              -> cosim -> verify_cosim -> vcd -> timing

``csim`` checks all four variants against the Python model (golden.py): they
are different C++, so each is checked.  ``synth`` builds each in its own
Vitis project, ``proj_<variant>``, and ``report`` puts them side by side in
``results/fir.md`` and ``results/fir.png``.  The co-simulation and timing
diagram are of one variant, the delay line by default.

    python fir_build.py --through report      # check and synthesize: about 3 minutes
    python fir_build.py                       # co-simulate and draw too: about 3 more
    python fir_build.py --sim-variant outer --force-step cosim

Steps are skipped when their inputs have not changed; ``--list-steps``
prints the sequence.  Requires the ``hwdesign-venv`` environment (the one
with ``waveflow``) and an installed Vitis HLS.
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
    from golden import NSAMP, NTAPS, default_case, write_cases, write_golden
except ModuleNotFoundError:  # running from another directory
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from golden import NSAMP, NTAPS, default_case, write_cases, write_golden

_SOURCE_DIR = Path(__file__).resolve().parent
TOP = "fir"
SOLUTION = "sol"
PERIOD_NS = 10.0             # 100 MHz, the PYNQ-Z2's usual fabric clock

#: The variants, in the order the demo tells them: name -> (FIR_VARIANT, what it is).
VARIANTS = {
    "inner": (0, "tap loop pipelined, not flattened"),
    "flat": (1, "tap loop pipelined, flattened by Vitis"),
    "outer": (2, "sample loop pipelined"),
    "delay": (3, "sample loop pipelined, delay line"),
}
SPECS = " ".join(f"{name}:{num}" for name, (num, _) in VARIANTS.items())
DEFAULT_SIM = "delay"


def _run_stage(config: BuildConfig, stage: str, out_dir: Path, *,
               live_output: bool = False, **env_extra) -> str:
    """Run one stage of run.tcl in the build root; return what Vitis printed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {"FIR_STAGE": stage, "FIR_OUT_DIR": out_dir.as_posix(), "FIR_VARIANTS": SPECS,
           "FIR_PERIOD": f"{PERIOD_NS:g}", **env_extra}
    try:
        result = toolchain.run_vitis_hls(_SOURCE_DIR / "run.tcl", work_dir=config.root_dir,
                                         capture_output=not live_output, env=env)
    except Exception as exc:
        for stream in (getattr(exc, "stdout", None), getattr(exc, "stderr", None)):
            if stream:
                print(stream if isinstance(stream, str) else stream.decode(errors="replace"))
        raise RuntimeError(f"Vitis HLS stage '{stage}' failed: {exc}") from exc
    return "".join(s if isinstance(s, str) else s.decode(errors="replace")
                   for s in (result.stdout, result.stderr) if s)


# ------------------------------------------------------------------ reports --
def report_dir(root: Path, name: str) -> Path:
    return root / f"proj_{name}" / SOLUTION / "syn" / "report"


def read_variant(root: Path, name: str) -> dict:
    """Every loop's row of the loop table, the call's worst-case latency (a
    full call, nsamp = MAX_NSAMP) and the resources, from the text reports."""
    rdir = report_dir(root, name)
    top_rpt = rdir / f"{TOP}_csynth.rpt"
    if not top_rpt.exists():
        raise RuntimeError(f"No synthesis report at {top_rpt}.")
    text = top_rpt.read_text(encoding="utf-8", errors="replace")
    loops, seen = [], set()
    # A pipelined loop is often a sub-function of its own (fir_Pipeline_...),
    # with its row in that function's report as well as the top's.
    for rpt in [top_rpt] + sorted(p for p in rdir.glob("*_csynth.rpt") if p != top_rpt):
        for line in rpt.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*\|\s*[-+o]\s+(\S+)\s*\|(.*)\|\s*$", line)
            if not m or m.group(1) in seen:
                continue
            cells = [c.strip() for c in m.group(2).split("|")]
            if len(cells) == 7:     # min, max, iteration latency, II achieved, II target, trip, pipelined
                seen.add(m.group(1))
                loops.append({"loop": m.group(1), "latency": cells[1],
                              "iteration_latency": cells[2], "ii": cells[3],
                              "ii_target": cells[4], "trip_count": cells[5],
                              "pipelined": cells[6]})
    lat = re.search(r"Latency \(cycles\).*?\n(?:.*\n){2}\s*\|\s*(\d+)\|\s*(\d+)\|", text)
    tot = re.search(r"^\|Total\s*\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|", text, re.M)
    cycles = int(lat.group(2)) if lat else None
    return {"variant": name, "fir_variant": VARIANTS[name][0], "what": VARIANTS[name][1],
            "loops": loops, "call_cycles": cycles,
            "cycles_per_sample": round(cycles / NSAMP, 2) if cycles else None,
            "bram": int(tot.group(1)) if tot else None, "dsp": int(tot.group(2)) if tot else None,
            "ff": int(tot.group(3)) if tot else None, "lut": int(tot.group(4)) if tot else None}


def ii_warnings(log: str) -> dict[str, list[str]]:
    """The II warnings Vitis printed while synthesizing each variant: HLS
    200-885 (not enough memory ports) and 200-880 (a loop-carried dependence)."""
    out, current = {k: [] for k in VARIANTS}, None
    for line in log.splitlines():
        m = re.search(r"FIR_SYNTH: (\w+)", line)
        if m:
            current = m.group(1)
            continue
        m = re.search(r"\[HLS 200-88[05]\]\s*(.*)", line)
        if m and current in out:
            msg = re.sub(r"\s+", " ", m.group(1)).strip()
            if msg not in out[current]:
                out[current].append(msg)
    return out


def _pipelined_loop(row: dict) -> dict:
    """The loop that carries the work: the pipelined one with the samples or
    the taps in its name (not the coefficient copy), else the first."""
    piped = [l for l in row["loops"] if l["pipelined"].lower() == "yes"
             and ("sample" in l["loop"] or "tap" in l["loop"])]
    return (piped or row["loops"] or [{}])[0]


def write_table(rows: list[dict], path: Path) -> Path:
    head = ("| Variant | Pipelined loop | II | Trip count | Iteration latency | "
            f"Cycles, {NSAMP} samples | Cycles / sample | DSP | FF | LUT |")
    lines = [head, "|" + "---|" * 10]
    for r in rows:
        lp = _pipelined_loop(r)
        lines.append(f"| {r['variant']} | {lp.get('loop', '-')} | {lp.get('ii', '-')} | "
                     f"{lp.get('trip_count', '-')} | {lp.get('iteration_latency', '-')} | "
                     f"{r['call_cycles']} | {r['cycles_per_sample']} | {r['dsp']} | {r['ff']} | "
                     f"{r['lut']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_plot(rows: list[dict], path: Path) -> Path:
    """Cycles per output sample, and DSPs, for each variant."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [r["variant"] for r in rows]
    colors = ["#8E8E8E", "#2F6FA8", "#B4530F", "#00857C"][:len(rows)]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.6))
    for ax, key, title in ((ax1, "cycles_per_sample", "Cycles per output sample"),
                           (ax2, "dsp", "DSP blocks")):
        vals = [r[key] or 0 for r in rows]
        bars = ax.bar(names, vals, color=colors)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:g}", ha="center", va="bottom",
                    fontsize=11)
        ax.set_title(title, loc="left", fontsize=12)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylim(0, max(vals) * 1.18 if max(vals) else 1)
    fig.suptitle(f"{NTAPS}-tap FIR, {NSAMP} samples, Vitis HLS at 100 MHz", x=0.01, ha="left",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=200, metadata={"Software": None, "Date": None})
    plt.close(fig)
    return path


# --------------------------------------------------------------------- steps --
@dataclass(kw_only=True)
class MakeInputsStep(BuildStep):
    description = "Write data/cases.txt and the golden results from golden.py."
    consumes = ["golden_py"]
    produces = {"cases": Path("data/cases.txt"), "golden_dir": Path("results/golden")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        h, x = default_case()
        cases = write_cases(config.root_dir / "data" / "cases.txt", h, x)
        golden_dir = config.root_dir / "results" / "golden"
        write_golden(golden_dir / "results.json", h, x)
        return {"cases": cases, "golden_dir": golden_dir}


@dataclass(kw_only=True)
class CSimStep(BuildStep):
    description = "Run every variant in C simulation, into results/csim/<variant>."
    consumes = ["fir_cpp", "fir_h", "tb_cpp", "run_tcl", "cases"]
    produces = {f"csim_{v}": Path(f"results/csim/{v}") for v in VARIANTS}
    params = {"live_output": False}

    def run(self, config: BuildConfig, cases, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "csim"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        _run_stage(config, "csim", out_dir, live_output=live_output)
        return {f"csim_{v}": out_dir / v for v in VARIANTS}


@dataclass(kw_only=True)
class SynthStep(BuildStep):
    description = "Synthesize every variant, one Vitis project each."
    consumes = ["fir_cpp", "fir_h", "run_tcl"] + [f"verify_{v}" for v in VARIANTS]
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
    description = "Write results/fir.json, fir.md and fir.png: the four variants side by side."
    consumes = ["synth_done"]
    produces = {"fir_json": Path("results/fir.json"), "fir_png": Path("results/fir.png")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, synth_done, **_) -> dict:
        rows = [read_variant(config.root_dir, v) for v in VARIANTS]
        warnings = json.loads(Path(synth_done).read_text(encoding="utf-8"))
        for r in rows:
            r["ii_warnings"] = warnings.get(r["variant"], [])
        results = config.root_dir / "results"
        out = results / "fir.json"
        out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        table = write_table(rows, results / "fir.md")
        png = write_plot(rows, results / "fir.png")
        print(table.read_text(encoding="utf-8"))
        for r in rows:
            for w in r["ii_warnings"]:
                print(f"{r['variant']}: {w}")
        return {"fir_json": out, "fir_png": png}


@dataclass(kw_only=True)
class CoSimStep(BuildStep):
    description = "Run RTL co-simulation of one variant (--sim-variant, the delay line by default)."
    consumes = ["tb_cpp", "run_tcl", "cases", "fir_json"]
    produces = {"cosim_dir": Path("results/cosim")}
    params = {"sim_variant": DEFAULT_SIM, "live_output": False}

    def run(self, config: BuildConfig, cases, sim_variant, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "cosim"
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        (out_dir / "variant.txt").write_text(sim_variant + "\n", encoding="utf-8")
        try:
            # Co-simulation sometimes fails within seconds, at "Instrumenting C
            # test bench" -- the transient failure the other demos retry.
            for wait_s in (15, 30, None):
                try:
                    _run_stage(config, "cosim", out_dir, live_output=live_output,
                               FIR_VARIANT=sim_variant)
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
    description = "Re-run the co-simulated variant's RTL with VCD logging into vcd/<variant>.vcd."
    consumes = ["verify_cosim_report", "cosim_dir"]
    produces = {"vcd": Path("vcd")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, cosim_dir, **_) -> dict:
        from waveflow.scripts.xsim_vcd import run_xsim_vcd
        name = (Path(cosim_dir) / "variant.txt").read_text(encoding="utf-8").strip()
        run_xsim_vcd(top=TOP, comp=f"proj_{name}", soln=SOLUTION, out=f"{name}.vcd",
                     trace_level="port", workdir=config.root_dir)
        return {"vcd": config.root_dir / "vcd"}


@dataclass(kw_only=True)
class TimingStep(BuildStep):
    description = "Draw the x reads and y writes from the VCD: results/timing_<variant>.png."
    consumes = ["vcd", "cosim_dir"]
    produces = {"timing": Path("results/timing.json")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, vcd, cosim_dir, **_) -> dict:
        name = (Path(cosim_dir) / "variant.txt").read_text(encoding="utf-8").strip()
        png = config.root_dir / "results" / f"timing_{name}.png"
        measured = write_timing_diagram(Path(vcd) / f"{name}.vcd", png, name)
        out = config.root_dir / "results" / "timing.json"
        out.write_text(json.dumps(measured, indent=2) + "\n", encoding="utf-8")
        print(f"Simulated {name}: {measured['call_cycles']} cycles for {measured['nsamp']} "
              f"samples; the first y written {measured['first_write_cycle']} cycles after "
              f"ap_start.")
        print(f"Timing diagram: {png.relative_to(config.root_dir).as_posix()}")
        return {"timing": out}


# ----------------------------------------------------------- timing diagram --
def _short(name: str) -> str:
    return name.split(".")[-1].split("[")[0]


def _find(names: list[str], short: str) -> str:
    hits = [s for s in names if _short(s) == short]
    if not hits:
        raise RuntimeError(f"No signal named {short!r} in the VCD.")
    return min(hits, key=len)        # the top-level port: the shortest path


def write_timing_diagram(vcd_path: Path, png_path: Path, name: str, ncycles: int = 40) -> dict:
    """ap_start, the x reads, the y writes and ap_done, for the first cycles
    after the coefficients are loaded."""
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
    first_read = first("x_ce0", start)
    first_write = first("y_we0", start)
    t0 = first_read - 2 * PERIOD_NS
    t1 = t0 + ncycles * PERIOD_NS

    td = TimingDiagram()
    for s in vp.get_td_signals():
        keep = [k for k, t in enumerate(s.times) if t < t1]
        td.add_signal(SigTimingInfo(s.name, [s.times[k] for k in keep],
                                    [s.values[k] for k in keep], is_clock=s.is_clock))
    ax = td.plot_signals(add_clk_grid=True, trange=(t0, t1), fig_width=12.0, text_mode="always")
    ax.set_xlabel("time [ns]")
    ax.set_title(f"FIR, {name}: the x reads and y writes from the first read of x",
                 loc="left", fontsize=12)
    fig = ax.get_figure()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=200, bbox_inches="tight", pad_inches=0.06,
                metadata={"Software": None, "Date": None})
    plt.close(fig)
    return {"variant": name, "nsamp": NSAMP, "call_cycles": round((done - start) / PERIOD_NS),
            "first_read_cycle": round((first_read - start) / PERIOD_NS),
            "first_write_cycle": round((first_write - start) / PERIOD_NS)}


# ----------------------------------------------------------------------- dag --
_RESULTS = [{"filename": "results.json", "compare_fields": ["nsamp", "y"]}]


def build_dag() -> BuildDag:
    dag = BuildDag()
    for artifact, path in (("fir_cpp", "fir.cpp"), ("fir_h", "fir.h"), ("tb_cpp", "tb_fir.cpp"),
                           ("run_tcl", "run.tcl"), ("golden_py", "golden.py")):
        dag.add(SourceStep(artifact=artifact, path=_SOURCE_DIR / path))
    dag.add(MakeInputsStep(name="make_inputs"))
    dag.add(CSimStep(name="csim"))
    for v in VARIANTS:
        dag.add(FunctionalVerifyStep(name=f"verify_csim_{v}", golden_dir_artifact="golden_dir",
                                     actual_dir_artifact=f"csim_{v}", jsons=_RESULTS,
                                     report_path=f"results/verify_csim_{v}.json",
                                     report_artifact=f"verify_{v}"))
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
        description="The FIR demo: one nested loop written four ways, synthesized and compared.",
        default_through="timing",
        root_dir=_SOURCE_DIR,
        extra_args=[(("--sim-variant",), {"default": DEFAULT_SIM, "choices": list(VARIANTS),
                                          "help": "The variant to co-simulate and draw."}),
                    (("--live-output",), {"action": "store_true",
                                          "help": "Stream Vitis output instead of capturing it."})],
        params_from_args=lambda a: {"sim_variant": a.sim_variant, "live_output": a.live_output},
    )


if __name__ == "__main__":
    main()
