"""Build script for the scalar_fun demo.

Everything the hardware is made of here is hand-written: the kernel
(``src/scalar_fun.cpp``), the testbench (``testbench/tb_scalar_fun.cpp``)
and the Vitis script (``run.tcl``).  Nothing is generated.  What this file
adds is the *sequence* -- which tool runs when, what each one needs, and
what is checked in between:

    make_inputs -> csim -> verify_csim -> csynth -> cosim -> verify_cosim
                                                         -> extract_vcd
                                                         -> timing_diagram

Running it is one command::

    python scalar_fun_build.py --through verify_csim   # fast, no synthesis
    python scalar_fun_build.py --through timing_diagram

Steps are skipped when their inputs have not changed, so editing the
testbench re-runs C simulation without re-synthesizing, and ``--force``
re-runs everything.  ``--list-steps`` prints the sequence.

Requires the ``hwdesign-venv`` environment (the one with ``waveflow``) and
an installed Vitis HLS.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from waveflow.build.build import BuildConfig, BuildDag, BuildStep, SourceStep
from waveflow.build.cli import run_dag_cli
from waveflow.build.cosim_steps import ExtractCosimTimingStep
from waveflow.build.verify_steps import FunctionalVerifyStep
from waveflow.toolchain import toolchain

try:
    from golden import DEFAULT_CASES, write_cases, write_golden
    from timing_diagram import write_timing_diagram
except ModuleNotFoundError:  # running from another directory
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from golden import DEFAULT_CASES, write_cases, write_golden
    from timing_diagram import write_timing_diagram

_SOURCE_DIR = Path(__file__).resolve().parent

# The synthesized IP's name.  It is `simp_fun`, not `scalar_fun`, because
# that is the name in the pre-built bitstream -- see src/scalar_fun.h.
TOP = "simp_fun"
PROJECT = "scalar_fun_proj"
SOLUTION = "solution1"


def _run_stage(config: BuildConfig, stage: str, out_dir: Path, *,
               clk_period_ns: float, trace_level: str = "none",
               live_output: bool = False) -> None:
    """Invoke ``run.tcl`` for one stage."""
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {
        "SCALAR_FUN_STAGE": stage,
        "SCALAR_FUN_OUT_DIR": out_dir.as_posix(),
        "SCALAR_FUN_TRACE_LEVEL": trace_level,
        "SCALAR_FUN_CLK_PERIOD_NS": f"{clk_period_ns:g}",
    }
    try:
        result = toolchain.run_vitis_hls(
            config.root_dir / "run.tcl",
            work_dir=config.root_dir,
            capture_output=not live_output,
            env=env,
        )
    except Exception as exc:
        raise RuntimeError(f"Vitis HLS stage '{stage}' failed: {exc}") from exc
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)


@dataclass(kw_only=True)
class MakeInputsStep(BuildStep):
    """Write the test vector and the expected results from the Python model."""

    description = "Write data/cases.txt and the golden results from golden.py."
    consumes = ["golden_py"]
    produces = {
        "cases": Path("data/cases.txt"),
        "golden_dir": Path("results/golden"),
    }
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        cases_path = write_cases(config.root_dir / "data" / "cases.txt", DEFAULT_CASES)
        golden_dir = config.root_dir / "results" / "golden"
        write_golden(golden_dir / "results.json", DEFAULT_CASES)
        # The testbench reads its vector from the directory it is given, so
        # the golden directory carries a copy too -- that way the golden run
        # and the graded runs are demonstrably the same stimulus.
        write_cases(golden_dir / "cases.txt", DEFAULT_CASES)
        return {"cases": cases_path, "golden_dir": golden_dir}


@dataclass(kw_only=True)
class CSimStep(BuildStep):
    """Compile the testbench against the C++ kernel and run it."""

    description = "Run Vitis HLS C simulation into results/csim."
    consumes = ["scalar_fun_cpp", "scalar_fun_h", "scalar_fun_tb", "run_tcl", "cases"]
    produces = {"csim_dir": Path("results/csim")}
    params = {"clk_period_ns": 10.0, "live_output": False}

    def run(self, config: BuildConfig, cases, clk_period_ns, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "csim"
        # The testbench reads cases.txt out of the directory it writes to.
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        _run_stage(config, "csim", out_dir, clk_period_ns=clk_period_ns,
                   live_output=live_output)
        return {"csim_dir": out_dir}


@dataclass(kw_only=True)
class CSynthStep(BuildStep):
    """Synthesize the kernel to RTL."""

    description = "Run Vitis HLS C synthesis."
    consumes = ["scalar_fun_cpp", "scalar_fun_h", "run_tcl", "verify_report"]
    produces = {"report_dir": Path(f"{PROJECT}/{SOLUTION}")}
    params = {"clk_period_ns": 10.0, "live_output": False}

    def run(self, config: BuildConfig, clk_period_ns, live_output, **_) -> dict:
        _run_stage(config, "csynth", config.root_dir / "results" / "csynth",
                   clk_period_ns=clk_period_ns, live_output=live_output)
        report_dir = config.root_dir / PROJECT / SOLUTION
        if not report_dir.exists():
            raise RuntimeError(f"C synthesis produced no solution at {report_dir}.")
        return {"report_dir": report_dir}


@dataclass(kw_only=True)
class CoSimStep(BuildStep):
    """Re-run the same testbench against the synthesized RTL."""

    description = "Run RTL co-simulation into results/cosim, with tracing on."
    consumes = ["scalar_fun_tb", "run_tcl", "cases", "report_dir"]
    produces = {"cosim_dir": Path("results/cosim")}
    # `port` traces the IP's ports -- the status signals and the AXI4-Lite
    # bundle -- which is what the timing diagram is about, and spares the
    # VCD a few hundred internal signals.
    params = {"clk_period_ns": 10.0, "trace_level": "port", "live_output": False}

    def run(self, config: BuildConfig, cases, clk_period_ns, trace_level,
            live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "cosim"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        _run_stage(config, "cosim", out_dir, clk_period_ns=clk_period_ns,
                   trace_level=trace_level, live_output=live_output)
        return {"cosim_dir": out_dir}


@dataclass(kw_only=True)
class ExtractVcdStep(BuildStep):
    """Re-run the RTL simulation with VCD logging switched on.

    Co-simulation writes an AMD-proprietary ``.wdb`` waveform database that
    only Vivado can open.  Getting an open ``.vcd`` out of it means patching
    the generated simulation scripts and running the simulator again --
    which ``run_xsim_vcd`` does, so the steps in the RTL-simulation notes do
    not have to be done by hand.
    """

    description = "Re-run the RTL simulation with VCD logging and collect vcd/dump.vcd."
    consumes = ["cosim_dir"]
    produces = {"vcd": Path("vcd/dump.vcd")}
    params = {"trace_level": "port"}

    def run(self, config: BuildConfig, trace_level, **_) -> dict:
        from waveflow.scripts.xsim_vcd import run_xsim_vcd

        vcd_path = Path(run_xsim_vcd(
            top=TOP,
            comp=PROJECT,
            soln=SOLUTION,
            out="dump.vcd",
            trace_level=trace_level,
            workdir=config.root_dir,
        ))
        # The simulator can reject the logging command it was given and still
        # exit cleanly, leaving a valid but empty VCD.  Without this check the
        # step passes and the failure only surfaces as an empty plot.
        n_signals = vcd_path.read_text(encoding="utf-8", errors="replace").count("$var")
        if n_signals == 0:
            raise RuntimeError(
                f"{vcd_path} declares no signals -- the RTL simulation logged "
                f"nothing (trace_level={trace_level!r}). Check the xsim output "
                f"above for a rejected log_vcd command."
            )
        print(f"VCD has {n_signals} signals.")
        return {"vcd": vcd_path}


@dataclass(kw_only=True)
class TimingDiagramStep(BuildStep):
    """Plot the processor interface from the VCD.

    Two figures, because they answer different questions.  The first shows a
    single call with its phases shaded -- what one invocation costs.  The
    second shows the whole run with each call marked -- that the cost repeats
    unchanged.
    """

    description = "Plot per-call and whole-run AXI4-Lite timing diagrams."
    consumes = ["vcd", "timing_diagram_py", "axi_trace_py"]
    produces = {
        "timing_diagram": Path("results/timing_diagram.png"),
        "timing_diagram_call": Path("results/timing_diagram_call.png"),
    }
    params = {"trange": None, "pad_ns": 15.0}

    def run(self, config: BuildConfig, vcd, trange, pad_ns, **_) -> dict:
        import axi_trace

        results = config.root_dir / "results"
        # The zoom window is read off the first decoded call rather than
        # hard-coded, so it stays right if the test vector changes.
        call_range = trange
        if call_range is None:
            calls = axi_trace.decode(Path(vcd))
            if not calls:
                raise RuntimeError(f"No AXI calls decoded from {vcd}.")
            call_range = (calls[0].start_ns - pad_ns, calls[0].end_ns + pad_ns)

        call_png = write_timing_diagram(
            Path(vcd), results / "timing_diagram_call.png",
            trange=call_range, phases=True,
        )
        full_png = write_timing_diagram(
            Path(vcd), results / "timing_diagram.png",
            iteration_marks=True,
        )
        return {"timing_diagram": full_png, "timing_diagram_call": call_png}


@dataclass(kw_only=True)
class ReportStep(BuildStep):
    """Collect what the run measured into one small summary."""

    description = "Write results/summary.json: cycle count and both verify verdicts."
    # Consuming the timing diagram as well makes this the DAG's single leaf,
    # so `--through report` really does run everything.  `--through
    # timing_diagram` would skip the verify and timing steps, which are not
    # its ancestors.
    consumes = ["cosim_timing", "verify_report", "verify_cosim_report", "timing_diagram"]
    produces = {"summary": Path("results/summary.json")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, cosim_timing, verify_report,
            verify_cosim_report, timing_diagram, **_) -> dict:
        def load(p):
            return json.loads(Path(p).read_text(encoding="utf-8"))

        summary = {
            "top": TOP,
            "transaction_cycles": load(cosim_timing)["transaction_cycles"],
            "csim_verified": load(verify_report)["pass"],
            "cosim_verified": load(verify_cosim_report)["pass"],
            "timing_diagram": str(Path(timing_diagram).relative_to(config.root_dir)),
            "calls_decoded": len(__import__("axi_trace").decode(config.root_dir / "vcd" / "dump.vcd")),
        }
        out = config.root_dir / "results" / "summary.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return {"summary": out}


# Both verification steps compare the same field, so the manifest is shared.
_RESULTS_MANIFEST = [{"filename": "results.json", "compare_fields": ["y"]}]


def build_scalar_fun_dag() -> BuildDag:
    dag = BuildDag()

    # The hand-written sources.  Declaring them makes a step re-run when its
    # source changes -- edit the testbench and C simulation runs again.
    dag.add(SourceStep(artifact="scalar_fun_cpp", path=_SOURCE_DIR / "src" / "scalar_fun.cpp"))
    dag.add(SourceStep(artifact="scalar_fun_h", path=_SOURCE_DIR / "src" / "scalar_fun.h"))
    dag.add(SourceStep(artifact="scalar_fun_tb",
                       path=_SOURCE_DIR / "testbench" / "tb_scalar_fun.cpp"))
    dag.add(SourceStep(artifact="run_tcl", path=_SOURCE_DIR / "run.tcl"))
    dag.add(SourceStep(artifact="golden_py", path=_SOURCE_DIR / "golden.py"))
    dag.add(SourceStep(artifact="timing_diagram_py", path=_SOURCE_DIR / "timing_diagram.py"))
    dag.add(SourceStep(artifact="axi_trace_py", path=_SOURCE_DIR / "axi_trace.py"))

    dag.add(MakeInputsStep(name="make_inputs"))

    dag.add(CSimStep(name="csim"))
    dag.add(FunctionalVerifyStep(
        name="verify_csim",
        golden_dir_artifact="golden_dir",
        actual_dir_artifact="csim_dir",
        jsons=_RESULTS_MANIFEST,
        report_path="results/verify_csim.json",
    ))

    dag.add(CSynthStep(name="csynth"))

    dag.add(CoSimStep(name="cosim"))
    dag.add(FunctionalVerifyStep(
        name="verify_cosim",
        golden_dir_artifact="golden_dir",
        actual_dir_artifact="cosim_dir",
        jsons=_RESULTS_MANIFEST,
        report_path="results/verify_cosim.json",
        # A second FunctionalVerifyStep would otherwise produce the same
        # `verify_report` artifact as the first.
        report_artifact="verify_cosim_report",
    ))

    dag.add(ExtractCosimTimingStep(
        name="extract_cosim_timing",
        top=TOP,
        report_dir_artifact="report_dir",
    ))
    dag.add(ExtractVcdStep(name="extract_vcd"))
    dag.add(TimingDiagramStep(name="timing_diagram"))
    dag.add(ReportStep(name="report"))
    return dag


def main() -> None:
    run_dag_cli(
        build_scalar_fun_dag,
        description="Build, simulate and time the scalar_fun demo.",
        default_through="verify_csim",
        root_dir=_SOURCE_DIR,
        extra_args=[
            (("--clk-period-ns",), {"type": float, "default": 10.0, "metavar": "NS",
                                    "help": "Target clock period in ns."}),
            (("--trace-level",), {"default": "port", "choices": ["port", "all"],
                                  "help": "Co-simulation waveform tracing."}),
            (("--trange",), {"type": float, "nargs": 2, "default": None,
                             "metavar": ("T0", "T1"),
                             "help": "Limit the timing diagram to this time range "
                                     "in ns.  The full run covers all five test "
                                     "cases; one transaction reads better in class."}),
            (("--live-output",), {"action": "store_true",
                                  "help": "Stream Vitis output instead of capturing it."}),
        ],
        params_from_args=lambda a: {
            "clk_period_ns": a.clk_period_ns,
            "trace_level": a.trace_level,
            "live_output": a.live_output,
            "trange": tuple(a.trange) if a.trange else None,
        },
    )


if __name__ == "__main__":
    main()
