"""Build script for the quad timing demo.

The kernel (``src/quad.cpp``), the testbench (``testbench/tb_quad.cpp``) and
the Vitis script (``run.tcl``) are hand-written.  This file adds the sequence:

    make_inputs -> csim -> verify_csim -> sweep -> sweep_report ----------------------> report
                                       -> cosim_slow -> verify_cosim_slow -> vcd_slow -> timing_slow
                                       -> cosim_fast -> verify_cosim_fast -> vcd_fast -> timing_fast

The point of the demo is ``sweep``: the same function synthesized at several
clock periods, to see Vitis HLS spread it over more cycles as the clock gets
faster.  Then one slow and one fast solution are simulated, so the extra
cycles show up between ap_start and ap_done.

    python quad_build.py --periods 10 --force-step sweep --through timing_slow   # one clock
    python quad_build.py --force-step sweep                                      # all of them
    python quad_build.py --periods 10 5 4 3.33 2.5 --force-step sweep

Steps are skipped when their inputs have not changed; ``--list-steps``
prints the sequence.  Requires the ``hwdesign-venv`` environment (the one
with ``waveflow``) and an installed Vitis HLS.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from waveflow.build.build import BuildConfig, BuildDag, BuildStep, SourceStep
from waveflow.build.cli import run_dag_cli
from waveflow.build.verify_steps import FunctionalVerifyStep
from waveflow.toolchain import toolchain

try:
    import quad_timing
    from golden import DEFAULT_CASES, write_cases, write_golden
except ModuleNotFoundError:  # running from another directory
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import quad_timing
    from golden import DEFAULT_CASES, write_cases, write_golden

_SOURCE_DIR = Path(__file__).resolve().parent

TOP = quad_timing.TOP
PROJECT = quad_timing.PROJECT

#: The clock periods swept, in ns: 50, 100, 150, 200, 250, 300 and 400 MHz.
DEFAULT_PERIODS = [20.0, 10.0, 6.67, 5.0, 4.0, 3.33, 2.5]
#: The two solutions simulated, one slow and one fast.  Both must be swept.
#: 100 MHz takes 2 cycles and 300 MHz 9, the fastest that meets timing.
DEFAULT_SLOW_NS, DEFAULT_FAST_NS = 10.0, 3.33


def _run_stage(config: BuildConfig, stage: str, out_dir: Path, *,
               live_output: bool = False, **env_extra) -> None:
    """Invoke ``run.tcl`` for one stage."""
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {"QUAD_STAGE": stage, "QUAD_OUT_DIR": out_dir.as_posix(), **env_extra}
    try:
        result = toolchain.run_vitis_hls(config.root_dir / "run.tcl", work_dir=config.root_dir,
                                         capture_output=not live_output, env=env)
    except Exception as exc:
        # The tool's own output says why; without it a failure is just an exit code.
        for stream in (getattr(exc, "stdout", None), getattr(exc, "stderr", None)):
            if stream:
                print(stream if isinstance(stream, str) else stream.decode(errors="replace"))
        raise RuntimeError(f"Vitis HLS stage '{stage}' failed: {exc}") from exc
    for stream in (result.stdout, result.stderr):
        if stream:
            print(stream)


@dataclass(kw_only=True)
class MakeInputsStep(BuildStep):
    """Write the test vector and the expected results from the Python model."""

    description = "Write data/cases.txt and the golden results from golden.py."
    consumes = ["golden_py"]
    produces = {"cases": Path("data/cases.txt"), "golden_dir": Path("results/golden")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        cases_path = write_cases(config.root_dir / "data" / "cases.txt", DEFAULT_CASES)
        golden_dir = config.root_dir / "results" / "golden"
        write_golden(golden_dir / "results.json", DEFAULT_CASES)
        return {"cases": cases_path, "golden_dir": golden_dir}


@dataclass(kw_only=True)
class CSimStep(BuildStep):
    """Compile the testbench against the C++ kernel and run it."""

    description = "Run Vitis HLS C simulation into results/csim."
    consumes = ["quad_cpp", "quad_h", "quad_tb", "run_tcl", "cases"]
    produces = {"csim_dir": Path("results/csim")}
    params = {"live_output": False}

    def run(self, config: BuildConfig, cases, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "csim"
        out_dir.mkdir(parents=True, exist_ok=True)
        # The testbench reads cases.txt out of the directory it writes to.
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        _run_stage(config, "csim", out_dir, live_output=live_output)
        return {"csim_dir": out_dir}


@dataclass(kw_only=True)
class SweepStep(BuildStep):
    """Synthesize the kernel once per clock period, plain and pipelined.

    One Vitis launch builds every solution, which saves restarting the tool
    for each one.
    """

    description = "Run C synthesis at every clock period in --periods, plain and pipelined."
    consumes = ["quad_cpp", "quad_h", "run_tcl", "verify_report"]
    # A marker file, not the project directory: co-simulation writes into
    # quad_proj too, which would make the directory look newer than every
    # step after it and re-run them all on the next build.
    produces = {"sweep_done": Path("results/sweep/periods.txt")}
    params = {"periods": DEFAULT_PERIODS, "live_output": False}

    def run(self, config: BuildConfig, periods, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "sweep"
        _run_stage(config, "sweep", out_dir, live_output=live_output,
                   QUAD_PERIODS=" ".join(f"{p:g}" for p in periods))
        marker = out_dir / "periods.txt"
        marker.write_text(" ".join(f"{p:g}" for p in periods) + "\n", encoding="utf-8")
        return {"sweep_done": marker}


def swept_periods(marker) -> list[float]:
    """The periods the last sweep actually built, from its marker file.

    Read back rather than taken from --periods, which can differ from what was
    built: the sweep re-runs only when forced, not when the option changes.
    """
    return [float(p) for p in Path(marker).read_text(encoding="utf-8").split()]


@dataclass(kw_only=True)
class SweepReportStep(BuildStep):
    """Read every solution's report into a table and a plot."""

    description = "Write results/sweep.json, sweep.md and sweep.png from the reports."
    consumes = ["sweep_done", "quad_timing_py"]
    produces = {"sweep_json": Path("results/sweep.json"),
                "sweep_png": Path("results/sweep.png")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, sweep_done, **_) -> dict:
        results = config.root_dir / "results"
        rows = quad_timing.read_sweep(config.root_dir, swept_periods(sweep_done))
        # Once, a sweep came back with one pipe_ solution unpipelined, its
        # return value turned into an `agg_result` port, and a re-run was
        # fine.  A plot drawn from that row misleads, so refuse it instead.
        bad = [r["solution"] for r in rows if r["pipelined"] and r["interval_cycles"] != 1]
        if bad:
            raise RuntimeError(f"{', '.join(bad)} did not pipeline to II = 1; see "
                               f"quad_proj/<solution>/<solution>.log.  Re-run the sweep "
                               "with --force-step sweep.")
        out = results / "sweep.json"
        out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        table = quad_timing.write_sweep_table(rows, results / "sweep.md")
        png = quad_timing.write_sweep_plot(rows, results / "sweep.png")
        print(table.read_text(encoding="utf-8"))
        return {"sweep_json": out, "sweep_png": png}


@dataclass(kw_only=True)
class CoSimStep(BuildStep):
    """Re-run the testbench against one synthesized solution: the slow or
    the fast one."""

    which: str                      # "slow" or "fast"
    description = "Run RTL co-simulation of one swept solution."
    params = {"slow_ns": DEFAULT_SLOW_NS, "fast_ns": DEFAULT_FAST_NS, "live_output": False}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return ["quad_tb", "run_tcl", "cases", "sweep_done"]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {f"cosim_{self.which}_dir": Path(f"results/cosim_{self.which}")}

    def run(self, config: BuildConfig, cases, sweep_done, slow_ns, fast_ns, live_output,
            **_) -> dict:
        period = slow_ns if self.which == "slow" else fast_ns
        periods = swept_periods(sweep_done)
        if not any(abs(period - p) < 1e-9 for p in periods):
            raise RuntimeError(f"The {self.which} period, {period:g} ns, is not among the swept "
                               f"periods {periods}: there is no solution to simulate.  Sweep "
                               "it with --periods ... --force-step sweep.")
        out_dir = config.root_dir / "results" / f"cosim_{self.which}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        solution = quad_timing.solution_name(period)
        try:
            try:
                _run_stage(config, "cosim", out_dir, live_output=live_output,
                           QUAD_SOLUTION=solution)
            except RuntimeError:
                # The first co-simulation after a fresh synthesis sometimes
                # fails at once, at "Instrumenting C test bench", with "file
                # generation failed" and nothing in its logs; the same command
                # then passes.  So one retry before giving up.
                print(f"Co-simulation of {solution} failed; retrying once.")
                _run_stage(config, "cosim", out_dir, live_output=live_output,
                           QUAD_SOLUTION=solution)
        except RuntimeError:
            # Freshness is decided by file times, so a results directory left
            # behind by a failed run would pass as done on the next build.
            shutil.rmtree(out_dir, ignore_errors=True)
            raise
        return {f"cosim_{self.which}_dir": out_dir}


@dataclass(kw_only=True)
class ExtractVcdStep(BuildStep):
    """Re-run one solution's RTL simulation with VCD logging switched on.

    Co-simulation writes an AMD-proprietary ``.wdb`` that only Vivado opens;
    ``run_xsim_vcd`` patches the generated simulation scripts to log an open
    ``.vcd`` instead, and runs the simulator again.
    """

    which: str
    description = "Re-run one RTL simulation with VCD logging into vcd/."
    params = {"slow_ns": DEFAULT_SLOW_NS, "fast_ns": DEFAULT_FAST_NS}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return [f"verify_cosim_{self.which}_report"]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {f"vcd_{self.which}": Path(f"vcd/{self.which}.vcd")}

    def run(self, config: BuildConfig, slow_ns, fast_ns, **_) -> dict:
        from waveflow.scripts.xsim_vcd import run_xsim_vcd

        period = slow_ns if self.which == "slow" else fast_ns
        vcd_path = Path(run_xsim_vcd(top=TOP, comp=PROJECT,
                                     soln=quad_timing.solution_name(period),
                                     out=f"{self.which}.vcd", trace_level="port",
                                     workdir=config.root_dir))
        # The simulator can reject the logging command and still exit cleanly,
        # leaving a valid but empty VCD.
        n = vcd_path.read_text(encoding="utf-8", errors="replace").count("$var")
        if n == 0:
            raise RuntimeError(f"{vcd_path} declares no signals: the RTL simulation logged "
                               "nothing.  Check the xsim output above.")
        print(f"{vcd_path.name}: {n} signals.")
        return {f"vcd_{self.which}": vcd_path}


@dataclass(kw_only=True)
class TimingDiagramStep(BuildStep):
    """The first calls at the slow or the fast clock.  One step per clock,
    so a single-frequency run can stop at ``timing_slow``."""

    which: str
    description = "Plot ap_start, x, ap_done and y from one VCD."
    params = {"slow_ns": DEFAULT_SLOW_NS, "fast_ns": DEFAULT_FAST_NS}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return [f"vcd_{self.which}", "quad_timing_py"]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {f"timing_{self.which}": Path(f"results/timing_{self.which}.png")}

    def run(self, config: BuildConfig, slow_ns, fast_ns, **artifacts) -> dict:
        period = slow_ns if self.which == "slow" else fast_ns
        png = quad_timing.write_timing_diagram(
            Path(artifacts[f"vcd_{self.which}"]),
            config.root_dir / "results" / f"timing_{self.which}.png", period_ns=period)
        return {f"timing_{self.which}": png}


@dataclass(kw_only=True)
class ReportStep(BuildStep):
    """Collect what the run measured into one summary: the DAG's single leaf."""

    description = "Write results/summary.json: the sweep and the simulated latencies."
    consumes = ["sweep_json", "timing_slow", "timing_fast", "vcd_slow", "vcd_fast"]
    produces = {"summary": Path("results/summary.json")}
    params = {"slow_ns": DEFAULT_SLOW_NS, "fast_ns": DEFAULT_FAST_NS}

    def run(self, config: BuildConfig, sweep_json, vcd_slow, vcd_fast, slow_ns, fast_ns,
            **_) -> dict:
        rows = json.loads(Path(sweep_json).read_text(encoding="utf-8"))

        def simulated(vcd, period):
            calls = quad_timing.handshakes(Path(vcd))
            return sorted({round((b - a) / period) for a, b in calls})

        summary = {
            "top": TOP,
            "sweep": [{k: r[k] for k in ("solution", "fclk_mhz", "estimated_ns", "meets_timing",
                                         "latency_cycles", "latency_ns", "interval_cycles")}
                      for r in rows],
            # The cycles co-simulation measured between ap_start and ap_done,
            # which should be the report's latency.
            "simulated_latency_cycles": {f"{slow_ns:g} ns": simulated(vcd_slow, slow_ns),
                                         f"{fast_ns:g} ns": simulated(vcd_fast, fast_ns)},
        }
        out = config.root_dir / "results" / "summary.json"
        out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary["simulated_latency_cycles"], indent=2))
        return {"summary": out}


_RESULTS_MANIFEST = [{"filename": "results.json", "compare_fields": ["y"]}]


def build_quad_dag() -> BuildDag:
    dag = BuildDag()
    for artifact, path in (("quad_cpp", "src/quad.cpp"), ("quad_h", "src/quad.h"),
                           ("quad_tb", "testbench/tb_quad.cpp"), ("run_tcl", "run.tcl"),
                           ("golden_py", "golden.py"), ("quad_timing_py", "quad_timing.py")):
        dag.add(SourceStep(artifact=artifact, path=_SOURCE_DIR / path))

    dag.add(MakeInputsStep(name="make_inputs"))
    dag.add(CSimStep(name="csim"))
    dag.add(FunctionalVerifyStep(name="verify_csim", golden_dir_artifact="golden_dir",
                                 actual_dir_artifact="csim_dir", jsons=_RESULTS_MANIFEST,
                                 report_path="results/verify_csim.json"))
    dag.add(SweepStep(name="sweep"))
    dag.add(SweepReportStep(name="sweep_report"))
    for which in ("slow", "fast"):
        dag.add(CoSimStep(name=f"cosim_{which}", which=which))
        dag.add(FunctionalVerifyStep(name=f"verify_cosim_{which}", golden_dir_artifact="golden_dir",
                                     actual_dir_artifact=f"cosim_{which}_dir",
                                     jsons=_RESULTS_MANIFEST,
                                     report_path=f"results/verify_cosim_{which}.json",
                                     report_artifact=f"verify_cosim_{which}_report"))
        dag.add(ExtractVcdStep(name=f"vcd_{which}", which=which))
        dag.add(TimingDiagramStep(name=f"timing_{which}", which=which))

    dag.add(ReportStep(name="report"))
    return dag


def main() -> None:
    run_dag_cli(
        build_quad_dag,
        description="Synthesize the quadratic at several clock periods and time it.",
        default_through="report",
        root_dir=_SOURCE_DIR,
        extra_args=[
            (("--periods",), {"type": float, "nargs": "+", "default": DEFAULT_PERIODS,
                              "metavar": "NS", "help": "Clock periods to synthesize, in ns."}),
            (("--slow-ns",), {"type": float, "default": DEFAULT_SLOW_NS,
                              "help": "The slow solution to simulate; must be swept."}),
            (("--fast-ns",), {"type": float, "default": DEFAULT_FAST_NS,
                              "help": "The fast solution to simulate; must be swept."}),
            (("--live-output",), {"action": "store_true",
                                  "help": "Stream Vitis output instead of capturing it."}),
        ],
        params_from_args=lambda a: {
            "periods": list(a.periods),
            "slow_ns": a.slow_ns,
            "fast_ns": a.fast_ns,
            "live_output": a.live_output,
        },
    )


if __name__ == "__main__":
    main()
