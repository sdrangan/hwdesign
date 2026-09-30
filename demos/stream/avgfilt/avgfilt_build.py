"""Build script for the avgfilt demo: pure AXI4-Stream, no TLAST.

Everything the hardware is made of here is hand-written: the kernel
(``avgfilt.cpp``), the testbench (``tb_avgfilt.cpp``) and the Vitis script
(``run.tcl``).  Nothing is generated.  What this file adds is the
*sequence* -- which tool runs when, what each one needs, and what is checked
in between:

    pysim -> plot_python ------------------------------------------> report
          -> csim -> verify_csim -> csynth -> cosim -> verify_cosim -^
                                                    -> extract_vcd -> timing_diagram -^

Running it is one command::

    python avgfilt_build.py                        # the whole flow
    python avgfilt_build.py --through plot_python  # Python only, no Vitis
    python avgfilt_build.py --through verify_csim  # fast: no synthesis

Steps are skipped when their inputs have not changed, and ``--force``
re-runs everything.  ``--list-steps`` prints the sequence.

Requires the ``hwdesign-venv`` environment (the one with ``waveflow``) and,
from ``csim`` on, an installed Vitis HLS.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np

from waveflow.build.build import BuildConfig, BuildDag, BuildStep, SourceStep
from waveflow.build.cli import run_dag_cli

try:
    import avgfilt_golden as golden
except ModuleNotFoundError:  # running from another directory
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import avgfilt_golden as golden

_SOURCE_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Python: the golden model and its plot
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class PySimStep(BuildStep):
    """Generate the test signal and run it through the Python model."""

    description = "Write vectors/tv_python.csv: the test signal and the golden output."
    consumes = ["golden_py"]
    produces = {"py_vectors": Path("vectors/tv_python.csv")}
    params = {"nsamp": 200, "seed": 1}

    def run(self, config: BuildConfig, nsamp, seed, **_) -> dict:
        x = golden.test_signal(nsamp=nsamp, seed=seed)
        y = golden.avgfilt(x)
        path = golden.write_vectors(config.root_dir / "vectors" / "tv_python.csv", x, y)
        print(f"Wrote {len(x)} samples to {path.relative_to(config.root_dir)}")
        return {"py_vectors": path}


@dataclass(kw_only=True)
class PlotPythonStep(BuildStep):
    """Plot the input and the filtered output from the Python model."""

    description = "Plot the input and the filtered output to results/avgfilt_python.png."
    consumes = ["py_vectors"]
    produces = {"python_plot": Path("results/avgfilt_python.png")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, py_vectors, **_) -> dict:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        x, y = golden.read_vectors(Path(py_vectors))
        n = np.arange(len(x))

        fig, axes = plt.subplots(2, 1, figsize=(8, 5), sharex=True)
        axes[0].plot(n, x, color="C0", lw=1)
        axes[0].set_ylabel("x[n]")
        axes[0].set_title("Input")
        axes[1].plot(n, x * x, color="0.7", lw=1, label="x[n]$^2$")
        axes[1].plot(n, y, color="C1", lw=1.5,
                     label=f"y[n], average of {golden.WIN_SIZE} squares")
        axes[1].set_ylabel("y[n]")
        axes[1].set_xlabel("Sample n")
        axes[1].set_title("Output of the Python golden model")
        axes[1].legend(loc="upper left", frameon=False)
        for ax in axes:
            ax.grid(True, alpha=0.3)
        fig.tight_layout()

        out = config.root_dir / "results" / "avgfilt_python.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=120)
        plt.close(fig)
        print(f"Wrote {out.relative_to(config.root_dir)}")
        return {"python_plot": out}


# ---------------------------------------------------------------------------
# Vitis: C simulation, synthesis, co-simulation
# ---------------------------------------------------------------------------

def _run_stage(config: BuildConfig, stage: str, live_output: bool,
               env: dict[str, str] | None = None) -> None:
    """Run one stage of ``run.tcl``; raise with the error lines if it fails.

    The tool's output goes to ``results/<stage>/vitis.log`` -- it is long,
    and nearly all of it is compiler warnings from Vitis's own headers.
    """
    from waveflow.toolchain import toolchain

    log = config.root_dir / "results" / stage / "vitis.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = toolchain.run_vitis_hls(
            config.root_dir / "run.tcl",
            work_dir=config.root_dir,
            capture_output=not live_output,
            env={"AVGFILT_STAGE": stage, **(env or {})},
        )
        log.write_text((result.stdout or "") + (result.stderr or ""), encoding="utf-8")
    except subprocess.CalledProcessError as exc:
        text = (exc.stdout or "") + (exc.stderr or "")
        log.write_text(text, encoding="utf-8")
        lines = [ln.strip() for ln in text.splitlines()]
        # The compiler's `file:line: error:` lines name the line to fix, and
        # the testbench's FAIL lines name the sample; Vitis's own ERROR lines
        # only say that something failed.
        errors = ([ln for ln in lines if ": error:" in ln or "FAIL" in ln][:6]
                  + [ln for ln in lines if ln.startswith("ERROR")][:3])
        detail = "\n  ".join(errors) if errors else f"see {log}"
        raise RuntimeError(
            f"Vitis HLS stage '{stage}' failed (exit {exc.returncode}):\n  {detail}"
        ) from exc
    print(f"Vitis HLS stage '{stage}' done; log in {log.relative_to(config.root_dir)}")


@dataclass(kw_only=True)
class CSimStep(BuildStep):
    """Compile the testbench against the C++ kernel and run it on the vectors."""

    description = "Run Vitis C simulation; the testbench writes vectors/tv_csim.csv."
    consumes = ["avgfilt_cpp", "avgfilt_h", "tb_avgfilt", "run_tcl", "py_vectors"]
    produces = {"csim_vectors": Path("vectors/tv_csim.csv")}
    params = {"live_output": False}

    def run(self, config: BuildConfig, live_output, **_) -> dict:
        out = config.root_dir / "vectors" / "tv_csim.csv"
        # Removed first, so a file from an earlier run cannot pass for this one's.
        out.unlink(missing_ok=True)
        _run_stage(config, "csim", live_output)
        if not out.exists():
            raise RuntimeError(f"C simulation ran but the testbench wrote no {out}.")
        return {"csim_vectors": out}


@dataclass(kw_only=True)
class CSynthStep(BuildStep):
    """Synthesize the kernel to RTL."""

    description = "Run Vitis C synthesis; the report is copied to results/csynth/."
    # verify_csim_report orders synthesis after a *verified* C simulation --
    # there is no point synthesizing a kernel that computes the wrong thing.
    # It also orders it after csim, the stage that (re)creates the project.
    consumes = ["avgfilt_cpp", "avgfilt_h", "run_tcl", "verify_csim_report"]
    produces = {"csynth_report": Path("results/csynth/avgfilt_csynth.rpt")}
    params = {"live_output": False}

    def run(self, config: BuildConfig, live_output, **_) -> dict:
        _run_stage(config, "csynth", live_output)
        made = config.root_dir / "avgfilt_proj/solution1/syn/report/avgfilt_csynth.rpt"
        if not made.exists():
            raise RuntimeError(f"C synthesis ran but wrote no report at {made}.")
        report = config.root_dir / "results" / "csynth" / "avgfilt_csynth.rpt"
        report.write_bytes(made.read_bytes())
        return {"csynth_report": report}


@dataclass(kw_only=True)
class CoSimStep(BuildStep):
    """Re-run the same testbench against the synthesized RTL."""

    description = "Run RTL co-simulation; the testbench writes vectors/tv_cosim.csv."
    consumes = ["tb_avgfilt", "run_tcl", "py_vectors", "csynth_report"]
    produces = {"cosim_vectors": Path("vectors/tv_cosim.csv")}
    # `port` records the IP's ports -- the two AXI4-Stream interfaces --
    # which is what the timing diagram is about.  extract_vcd replays this
    # recording, so it has to be on here.
    params = {"trace_level": "port", "live_output": False}

    def run(self, config: BuildConfig, trace_level, live_output, **_) -> dict:
        out = config.root_dir / "vectors" / "tv_cosim.csv"
        out.unlink(missing_ok=True)
        _run_stage(config, "cosim", live_output, env={"AVGFILT_TRACE_LEVEL": trace_level})
        if not out.exists():
            raise RuntimeError(f"Co-simulation ran but the testbench wrote no {out}.")
        return {"cosim_vectors": out}


@dataclass(kw_only=True)
class ExtractVcdStep(BuildStep):
    """Re-run the RTL simulation with VCD logging switched on.

    Co-simulation writes an AMD-proprietary ``.wdb`` waveform database that
    only Vivado can open.  Getting an open ``.vcd`` out of it means patching
    the generated simulation scripts and running the simulator again, which
    ``run_xsim_vcd`` does.
    """

    description = "Re-run the RTL simulation with VCD logging and collect vcd/dump.vcd."
    consumes = ["cosim_vectors"]
    produces = {"vcd": Path("vcd/dump.vcd")}
    params = {"trace_level": "port"}

    def run(self, config: BuildConfig, trace_level, **_) -> dict:
        from waveflow.scripts.xsim_vcd import run_xsim_vcd

        vcd_path = Path(run_xsim_vcd(
            top="avgfilt",
            comp="avgfilt_proj",
            soln="solution1",
            out="dump.vcd",
            trace_level=trace_level,
            workdir=config.root_dir,
        ))
        n_signals = vcd_path.read_text(encoding="utf-8", errors="replace").count("$var")
        if n_signals == 0:
            raise RuntimeError(f"{vcd_path} declares no signals -- the RTL simulation "
                               f"logged nothing (trace_level={trace_level!r}).")
        print(f"VCD has {n_signals} signals.")
        return {"vcd": vcd_path}


@dataclass(kw_only=True)
class TimingDiagramStep(BuildStep):
    """Decode both AXI4-Stream ports from the VCD, and plot them.

    Two figures, because they answer different questions.  The waveform
    shows the start of the stream cycle by cycle -- the handshake, and the
    latency from the first sample in to the first sample out.  The data
    plot shows the whole run: the values that crossed each port, with the
    Python model on top.

    The decoded data is also checked, so this is a third comparison against
    the model -- read off the wires rather than from the testbench's file.
    """

    description = ("Plot the AXI4-Stream ports from the VCD; measure latency and "
                   "stalls into results/stream_timing.json.")
    consumes = ["vcd", "py_vectors", "timing_py"]
    produces = {
        "timing_diagram": Path("results/timing_diagram.png"),
        "stream_data_plot": Path("results/stream_data.png"),
        "stream_timing": Path("results/stream_timing.json"),
    }
    params = {"trange": None}

    def run(self, config: BuildConfig, vcd, py_vectors, trange, **_) -> dict:
        import avgfilt_timing

        x_py, y_py = golden.read_vectors(Path(py_vectors))
        trace = avgfilt_timing.decode(Path(vcd), nsamp=len(x_py))
        results = config.root_dir / "results"

        # The zoom window is read off the trace rather than hard-coded, so it
        # stays right if the latency changes: a few cycles before the first
        # sample goes in, to a few after the first comes out.
        period = trace.clk_period_ns
        window = trange or (trace.t_in[0] - 3 * period, trace.t_out[0] + 5 * period)
        diagram = avgfilt_timing.write_timing_diagram(
            Path(vcd), results / "timing_diagram.png", trace, trange=window)
        data_plot = avgfilt_timing.write_stream_plot(
            results / "stream_data.png", trace, y_py)

        n = len(x_py)
        timing = {
            "clk_period_ns": period,
            "nsamp": n,
            "latency_cycles": trace.latency_cycles,
            # From the first sample out to the last: n - 1 cycles means one
            # sample per clock, an initiation interval of 1.
            "output_cycles": int(round((trace.t_out[-1] - trace.t_out[0]) / period)) + 1,
            "stalls_in": trace.stalls_in,
            "stalls_out": trace.stalls_out,
            "input_matches_vectors": bool(np.array_equal(trace.x, x_py)),
            "output_matches_model": bool(np.array_equal(trace.y, y_py)),
        }
        out = results / "stream_timing.json"
        out.write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")
        print(f"Latency {timing['latency_cycles']} cycles; {n} samples out in "
              f"{timing['output_cycles']} cycles; stalls in/out "
              f"{trace.stalls_in}/{trace.stalls_out}.")

        if not timing["input_matches_vectors"]:
            raise RuntimeError("The samples on in_stream_TDATA are not the test vector.")
        if not timing["output_matches_model"]:
            raise RuntimeError("The samples on out_stream_TDATA differ from the Python model.")
        return {"timing_diagram": diagram, "stream_data_plot": data_plot,
                "stream_timing": out}


# ---------------------------------------------------------------------------
# The comparison against the Python model
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class CompareStep(BuildStep):
    """Compare a Vitis run's output against the Python golden model.

    Used twice, because the two comparisons answer different questions:
    after C simulation, whether the C++ is right; after co-simulation,
    whether the synthesized RTL still does what the C++ did.

    Both sides compute in float32 in the same order, so a correct kernel
    matches bit for bit and the report counts exact matches.  The pass
    criterion is still a tolerance, since exactness is a property of this
    kernel rather than of float arithmetic in general.
    """

    description = "Compare a testbench output file against vectors/tv_python.csv."
    params: ClassVar[dict] = {}

    actual_artifact: str
    report_artifact: str
    report_path: str
    rtol: float = 1e-5
    atol: float = 1e-6

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return ["py_vectors", self.actual_artifact]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {self.report_artifact: Path(self.report_path)}

    def run(self, config: BuildConfig, py_vectors, **artifacts) -> dict:
        actual_path = Path(artifacts[self.actual_artifact])
        x_py, y_py = golden.read_vectors(Path(py_vectors))
        x_hw, y_hw = golden.read_vectors(actual_path)

        failures: list[str] = []
        if len(y_hw) != len(y_py):
            failures.append(f"{actual_path.name} has {len(y_hw)} samples, "
                            f"the model has {len(y_py)}")
        n = min(len(y_hw), len(y_py))
        if not np.array_equal(x_hw[:n], x_py[:n]):
            failures.append(f"the input x in {actual_path.name} is not the model's "
                            f"-- the testbench did not run the golden vectors")

        err = np.abs(y_hw[:n].astype(np.float64) - y_py[:n].astype(np.float64))
        close = np.isclose(y_hw[:n], y_py[:n], rtol=self.rtol, atol=self.atol)
        bad = np.flatnonzero(~close)
        if bad.size:
            i = int(bad[0])
            failures.append(f"{bad.size} of {n} samples differ; first at n={i}: "
                            f"model {y_py[i]:.9g}, kernel {y_hw[i]:.9g}")

        report = {
            "pass": not failures,
            "actual": actual_path.name,
            "nsamp": int(n),
            "exact_matches": int(np.sum(y_hw[:n] == y_py[:n])),
            "max_abs_err": float(err.max()) if n else 0.0,
            "rtol": self.rtol,
            "atol": self.atol,
            "failures": failures,
        }
        out = config.root_dir / self.report_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        print(f"{actual_path.name} vs the model: {report['exact_matches']} of {n} "
              f"samples bit-exact, max |error| = {report['max_abs_err']:.3g}")
        if failures:
            raise RuntimeError(f"'{self.name}' failed: " + "; ".join(failures))
        return {self.report_artifact: out}


@dataclass(kw_only=True)
class ReportStep(BuildStep):
    """Collect both verdicts and the measured timing into one small summary."""

    description = "Write results/summary.json: the comparison verdicts and the stream timing."
    # Consuming the plot and the timing as well makes this the DAG's single
    # leaf, so the default `--through report` really does run everything.
    consumes = ["python_plot", "verify_csim_report", "verify_cosim_report", "stream_timing"]
    produces = {"summary": Path("results/summary.json")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, python_plot, verify_csim_report,
            verify_cosim_report, stream_timing, **_) -> dict:
        def load(p):
            return json.loads(Path(p).read_text(encoding="utf-8"))

        csim, cosim = load(verify_csim_report), load(verify_cosim_report)
        timing = load(stream_timing)
        summary = {
            "top": "avgfilt",
            "nsamp": csim["nsamp"],
            "csim_verified": csim["pass"],
            "csim_max_abs_err": csim["max_abs_err"],
            "cosim_verified": cosim["pass"],
            "cosim_max_abs_err": cosim["max_abs_err"],
            "latency_cycles": timing["latency_cycles"],
            "output_cycles": timing["output_cycles"],
            "stalls": timing["stalls_in"] + timing["stalls_out"],
            "python_plot": Path(python_plot).relative_to(config.root_dir).as_posix(),
        }
        out = config.root_dir / "results" / "summary.json"
        out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return {"summary": out}


def build_avgfilt_dag() -> BuildDag:
    dag = BuildDag()

    # The hand-written sources.  Declaring them makes a step re-run when its
    # source changes -- edit the testbench and C simulation runs again.
    dag.add(SourceStep(artifact="avgfilt_cpp", path=_SOURCE_DIR / "avgfilt.cpp"))
    dag.add(SourceStep(artifact="avgfilt_h", path=_SOURCE_DIR / "avgfilt.h"))
    dag.add(SourceStep(artifact="tb_avgfilt", path=_SOURCE_DIR / "tb_avgfilt.cpp"))
    dag.add(SourceStep(artifact="run_tcl", path=_SOURCE_DIR / "run.tcl"))
    dag.add(SourceStep(artifact="golden_py", path=_SOURCE_DIR / "avgfilt_golden.py"))
    dag.add(SourceStep(artifact="timing_py", path=_SOURCE_DIR / "avgfilt_timing.py"))

    dag.add(PySimStep(name="pysim"))
    dag.add(PlotPythonStep(name="plot_python"))

    dag.add(CSimStep(name="csim"))
    dag.add(CompareStep(name="verify_csim", actual_artifact="csim_vectors",
                        report_artifact="verify_csim_report",
                        report_path="results/verify_csim.json"))
    dag.add(CSynthStep(name="csynth"))
    dag.add(CoSimStep(name="cosim"))
    dag.add(CompareStep(name="verify_cosim", actual_artifact="cosim_vectors",
                        report_artifact="verify_cosim_report",
                        report_path="results/verify_cosim.json"))
    dag.add(ExtractVcdStep(name="extract_vcd"))
    dag.add(TimingDiagramStep(name="timing_diagram"))

    dag.add(ReportStep(name="report"))
    return dag


def main() -> None:
    run_dag_cli(
        build_avgfilt_dag,
        description="Simulate the avgfilt pure-streaming demo in Python, C and RTL.",
        default_through="report",
        root_dir=_SOURCE_DIR,
        extra_args=[
            (("--nsamp",), {"type": int, "default": 200,
                            "help": "Number of samples in the test signal."}),
            (("--seed",), {"type": int, "default": 1,
                           "help": "Seed for the test signal's noise."}),
            (("--trace-level",), {"default": "port", "choices": ["port", "all"],
                                  "help": "Which signals co-simulation records for the VCD: "
                                          "the IP's ports, or every internal signal too."}),
            (("--trange",), {"type": float, "nargs": 2, "default": None,
                             "metavar": ("T0", "T1"),
                             "help": "Time range in ns for the timing diagram.  By default "
                                     "it spans the first sample in to the first sample out."}),
            (("--live-output",), {"action": "store_true",
                                  "help": "Stream Vitis output instead of capturing it "
                                          "to results/<stage>/vitis.log."}),
        ],
        params_from_args=lambda a: {
            "nsamp": a.nsamp,
            "seed": a.seed,
            "trace_level": a.trace_level,
            "trange": tuple(a.trange) if a.trange else None,
            "live_output": a.live_output,
        },
    )


if __name__ == "__main__":
    main()
