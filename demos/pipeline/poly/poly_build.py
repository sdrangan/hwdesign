"""Build script for the pipelining demo.

The kernel (``poly.cpp``), the testbench (``tb_poly.cpp``) and the Vitis
script (``run.tcl``) are hand-written.  This file adds the sequence, in two
parts.

Part 1, pipelining: the loop as written, with pipelining off, against the
same loop with ``#pragma HLS PIPELINE II=1``.

    make_inputs -> csim -> verify_csim -> synth_pipe -> pipe_report ----------------------------> pipeline
                                                     -> schedule_pipe
                                                     -> cosim_nopipe -> verify_cosim_nopipe -> vcd_nopipe -> timing_nopipe
                                                     -> cosim_pipe -> verify_cosim_pipe -> vcd_pipe -> timing_pipe

Part 2, unrolling: the pipelined loop unrolled by 2, 4 and 8, with the
arrays partitioned to match, and once without partitioning, to see the
memory bottleneck.

    verify_csim -> synth_unroll -> unroll_report ----------------------------------------------> unroll
                                -> schedule_nopart
                                -> cosim_unroll -> verify_cosim_unroll -> vcd_unroll -> timing_unroll

    python poly_build.py --through pipeline      # part 1: about 4 minutes
    python poly_build.py                         # both parts: about 10 more
    python poly_build.py --unroll 2 4 --sim-unroll 2 --force-step synth_unroll

Steps are skipped when their inputs have not changed; ``--list-steps``
prints the sequence.  Requires the ``hwdesign-venv`` environment (the one
with ``waveflow``) and an installed Vitis HLS.
"""
from __future__ import annotations

import json
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
    import poly_analysis as pa
    from golden import DEFAULT_COEFFS, default_x, write_cases, write_golden
except ModuleNotFoundError:  # running from another directory
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import poly_analysis as pa
    from golden import DEFAULT_COEFFS, default_x, write_cases, write_golden

_SOURCE_DIR = Path(__file__).resolve().parent

#: Part 1: the loop with pipelining off, and pipelined.
NOPIPE = pa.Variant("nopipe", pipeline=False)
PIPE = pa.Variant("pipe", pipeline=True)
#: Part 2: the unroll factors swept, each with the arrays partitioned to match;
#: the one factor also built without partitioning; and the one simulated.
DEFAULT_UNROLL = [2, 4, 8]
DEFAULT_NOPART = 4
DEFAULT_SIM_UNROLL = 4
#: The clock, in ns: 100 MHz, the PYNQ-Z2's usual fabric clock.
PERIOD_NS = 10.0


def unroll_variants(unroll: list[int], nopart: int) -> list[pa.Variant]:
    out = [pa.unroll_variant(f) for f in unroll]
    if nopart:
        out.append(pa.unroll_variant(nopart, partition=False))
    return out


def _run_stage(config: BuildConfig, stage: str, out_dir: Path, *,
               live_output: bool = False, **env_extra) -> None:
    """Invoke ``run.tcl`` for one stage.

    The script and the sources are read from beside this file; Vitis runs in
    the build root, ``config.root_dir``, so the projects land there.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    config.root_dir.mkdir(parents=True, exist_ok=True)
    env = {"POLY_STAGE": stage, "POLY_OUT_DIR": out_dir.as_posix(),
           "POLY_PERIOD": f"{PERIOD_NS:g}", **env_extra}
    try:
        result = toolchain.run_vitis_hls(_SOURCE_DIR / "run.tcl", work_dir=config.root_dir,
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


def built_variants(marker) -> list[pa.Variant]:
    """The variants a synth step actually built, from its marker file.

    Read back rather than taken from the options, which can differ from what
    was built: a synth step re-runs only when forced, not when an option
    changes.
    """
    out = []
    for spec in Path(marker).read_text(encoding="utf-8").split():
        name, pipeline, unroll, partition = spec.split(":")
        out.append(pa.Variant(name, pipeline == "1", int(unroll), partition == "1"))
    return out


# ------------------------------------------------------------- C simulation --
@dataclass(kw_only=True)
class MakeInputsStep(BuildStep):
    """Write the test vector and the expected results from the Python model."""

    description = "Write data/cases.txt and the golden results from golden.py."
    consumes = ["golden_py"]
    produces = {"cases": Path("data/cases.txt"), "golden_dir": Path("results/golden")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        x = default_x()
        cases = write_cases(config.root_dir / "data" / "cases.txt", DEFAULT_COEFFS, x)
        golden_dir = config.root_dir / "results" / "golden"
        write_golden(golden_dir / "results.json", DEFAULT_COEFFS, x)
        return {"cases": cases, "golden_dir": golden_dir}


@dataclass(kw_only=True)
class CSimStep(BuildStep):
    """Compile the testbench against the C++ kernel and run it."""

    description = "Run Vitis HLS C simulation into results/csim."
    consumes = ["poly_cpp", "poly_h", "poly_tb", "run_tcl", "cases"]
    produces = {"csim_dir": Path("results/csim")}
    params = {"live_output": False}

    def run(self, config: BuildConfig, cases, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "csim"
        out_dir.mkdir(parents=True, exist_ok=True)
        # The testbench reads cases.txt out of the directory it writes to.
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        _run_stage(config, "csim", out_dir, live_output=live_output)
        return {"csim_dir": out_dir}


# ---------------------------------------------------------------- synthesis --
@dataclass(kw_only=True)
class SynthStep(BuildStep):
    """Synthesize one part's variants, one Vitis project each, in one launch."""

    part: str                       # "pipe" or "unroll"
    description = "Run C synthesis of each variant."
    params = {"unroll": DEFAULT_UNROLL, "nopart": DEFAULT_NOPART, "live_output": False}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return ["poly_cpp", "poly_h", "run_tcl", "verify_report"]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        # A marker file, not the project directories: co-simulation writes
        # into those too, which would make them look newer than every step
        # after this one and re-run them all on the next build.
        return {f"synth_{self.part}_done": Path(f"results/synth_{self.part}/variants.txt")}

    def run(self, config: BuildConfig, unroll, nopart, live_output, **_) -> dict:
        variants = [NOPIPE, PIPE] if self.part == "pipe" else unroll_variants(unroll, nopart)
        out_dir = config.root_dir / "results" / f"synth_{self.part}"
        specs = " ".join(v.spec for v in variants)
        _run_stage(config, "synth", out_dir, live_output=live_output, POLY_VARIANTS=specs)
        marker = out_dir / "variants.txt"
        marker.write_text("\n".join(v.spec for v in variants) + "\n", encoding="utf-8")
        return {f"synth_{self.part}_done": marker}


@dataclass(kw_only=True)
class PipeReportStep(BuildStep):
    """Part 1's two variants, side by side, from their reports."""

    description = "Write results/pipe.json and pipe.md: pipelined against not."
    consumes = ["synth_pipe_done", "analysis_py"]
    produces = {"pipe_json": Path("results/pipe.json")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, synth_pipe_done, **_) -> dict:
        rows = [pa.read_variant(config.root_dir, v) for v in built_variants(synth_pipe_done)]
        pipe = next(r for r in rows if r["variant"] == PIPE.name)
        if pipe["ii"] != 1:
            raise RuntimeError(f"The pipelined loop reached II = {pipe['ii']}, not 1; see "
                               f"{PIPE.project}/{pa.SOLUTION}/{pa.SOLUTION}.log.")
        out = config.root_dir / "results" / "pipe.json"
        out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        table = pa.write_pipe_table(rows, config.root_dir / "results" / "pipe.md")
        print(table.read_text(encoding="utf-8"))
        return {"pipe_json": out}


@dataclass(kw_only=True)
class ScheduleStep(BuildStep):
    """One pipelined variant's schedule: which operation is in which cycle of
    an iteration, and how the iterations overlap."""

    which: str                      # "pipe" or "nopart"
    description = "Write results/schedule_<which>.md and .png from the schedule report."
    params = {"nopart": DEFAULT_NOPART}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return [f"synth_{'pipe' if self.which == 'pipe' else 'unroll'}_done", "analysis_py"]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {f"schedule_{self.which}": Path(f"results/schedule_{self.which}.png")}

    def run(self, config: BuildConfig, nopart, **_) -> dict:
        if self.which == "pipe":
            v = PIPE
        else:
            if not nopart:
                raise RuntimeError("--nopart 0 builds no unpartitioned variant to schedule.")
            v = pa.unroll_variant(nopart, partition=False)
        sched = pa.read_schedule(pa.sched_report(config.root_dir, v))
        results = config.root_dir / "results"
        table = pa.write_schedule_table(sched, results / f"schedule_{self.which}.md")
        # The overlapped-iterations view needs one operation of each kind per
        # iteration; an unrolled loop has several, so it gets one iteration.
        png = pa.write_schedule_plot(sched, results / f"schedule_{self.which}.png",
                                     overlap=v.unroll == 1)
        print(table.read_text(encoding="utf-8"))
        return {f"schedule_{self.which}": png}


@dataclass(kw_only=True)
class UnrollReportStep(BuildStep):
    """Part 2: throughput and resources against the unroll factor."""

    description = "Write results/unroll.json, unroll.md and unroll.png."
    consumes = ["synth_unroll_done", "synth_pipe_done", "analysis_py"]
    produces = {"unroll_json": Path("results/unroll.json"),
                "unroll_png": Path("results/unroll.png")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, synth_unroll_done, **_) -> dict:
        # The pipelined loop is unroll factor 1.
        variants = [PIPE] + built_variants(synth_unroll_done)
        rows = [pa.read_variant(config.root_dir, v) for v in variants]
        results = config.root_dir / "results"
        out = results / "unroll.json"
        out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        table = pa.write_unroll_table(rows, results / "unroll.md")
        png = pa.write_unroll_plot(rows, results / "unroll.png")
        print(table.read_text(encoding="utf-8"))
        return {"unroll_json": out, "unroll_png": png}


# ----------------------------------------------------------- co-simulation --
def _sim_variant(which: str, sim_unroll: int) -> pa.Variant:
    return {"nopipe": NOPIPE, "pipe": PIPE}.get(which) or pa.unroll_variant(sim_unroll)


def _synth_marker(which: str) -> str:
    return "synth_unroll_done" if which == "unroll" else "synth_pipe_done"


@dataclass(kw_only=True)
class CoSimStep(BuildStep):
    """Re-run the testbench against one synthesized variant."""

    which: str                      # "nopipe", "pipe" or "unroll"
    description = "Run RTL co-simulation of one variant."
    params = {"sim_unroll": DEFAULT_SIM_UNROLL, "live_output": False}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return ["poly_tb", "run_tcl", "cases", _synth_marker(self.which)]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {f"cosim_{self.which}_dir": Path(f"results/cosim_{self.which}")}

    def run(self, config: BuildConfig, cases, sim_unroll, live_output, **artifacts) -> dict:
        v = _sim_variant(self.which, sim_unroll)
        built = built_variants(artifacts[_synth_marker(self.which)])
        if v not in built:
            raise RuntimeError(f"{v.name} was not synthesized (built: "
                               f"{', '.join(b.name for b in built)}).  Add it with --unroll "
                               "... --force-step synth_unroll.")
        out_dir = config.root_dir / "results" / f"cosim_{self.which}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cases.txt").write_bytes(Path(cases).read_bytes())
        try:
            # Co-simulation sometimes fails within seconds, at "Instrumenting C
            # test bench", with "file generation failed" -- the same transient
            # failure the quad demo retries (see its quad_build.py).  A later
            # attempt passes, so wait between attempts.
            for wait_s in (15, 30, None):
                try:
                    _run_stage(config, "cosim", out_dir, live_output=live_output,
                               POLY_VARIANTS=v.spec, POLY_VARIANT=v.name)
                    break
                except RuntimeError:
                    if wait_s is None:
                        raise
                    print(f"Co-simulation of {v.name} failed; retrying in {wait_s} s.")
                    time.sleep(wait_s)
        except RuntimeError:
            # Freshness is decided by file times, so a results directory left
            # behind by a failed run would pass as done on the next build.
            shutil.rmtree(out_dir, ignore_errors=True)
            raise
        return {f"cosim_{self.which}_dir": out_dir}


@dataclass(kw_only=True)
class ExtractVcdStep(BuildStep):
    """Re-run one variant's RTL simulation with VCD logging switched on.

    Co-simulation writes an AMD-proprietary ``.wdb`` that only Vivado opens;
    ``run_xsim_vcd`` patches the generated simulation scripts to log an open
    ``.vcd`` instead, and runs the simulator again.
    """

    which: str
    description = "Re-run one RTL simulation with VCD logging into vcd/."
    params = {"sim_unroll": DEFAULT_SIM_UNROLL}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return [f"verify_cosim_{self.which}_report"]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {f"vcd_{self.which}": Path(f"vcd/{self.which}.vcd")}

    def run(self, config: BuildConfig, sim_unroll, **_) -> dict:
        from waveflow.scripts.xsim_vcd import run_xsim_vcd

        v = _sim_variant(self.which, sim_unroll)
        vcd_path = Path(run_xsim_vcd(top=pa.TOP, comp=v.project, soln=pa.SOLUTION,
                                     out=f"{self.which}.vcd", trace_level="port",
                                     workdir=config.root_dir))
        n = vcd_path.read_text(encoding="utf-8", errors="replace").count("$var")
        print(f"{vcd_path.name}: {n} signals.")
        return {f"vcd_{self.which}": vcd_path}


@dataclass(kw_only=True)
class TimingDiagramStep(BuildStep):
    """The start of one variant's call: x read, y written, cycle by cycle."""

    which: str
    description = "Plot the memory ports from one VCD, and record what it measured."
    params = {"sim_unroll": DEFAULT_SIM_UNROLL}

    #: How much of each call to draw, in cycles from ap_start.  None draws up
    #: to a few cycles after the first write to y.
    WINDOW: ClassVar[dict] = {"nopipe": 70, "pipe": None, "unroll": None}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return [f"vcd_{self.which}", "analysis_py"]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {f"timing_{self.which}": Path(f"results/timing_{self.which}.json")}

    def run(self, config: BuildConfig, sim_unroll, **artifacts) -> dict:
        v = _sim_variant(self.which, sim_unroll)
        results = config.root_dir / "results"
        measured = pa.write_timing_diagram(
            Path(artifacts[f"vcd_{self.which}"]), results / f"timing_{self.which}.png",
            period_ns=PERIOD_NS, title=v.describe(), ncycles=self.WINDOW[self.which],
            # Pipelined, the data changes every cycle and its labels would
            # overlap; the addresses tell the story.  Unpipelined, there is
            # room to show the values too.
            show_data=not v.pipeline)
        measured = {"variant": v.name, "nsamp": len(default_x()), **measured}
        out = results / f"timing_{self.which}.json"
        out.write_text(json.dumps(measured, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(measured, indent=2))
        return {f"timing_{self.which}": out}


# ---------------------------------------------------------------- summaries --
@dataclass(kw_only=True)
class PipelineSummaryStep(BuildStep):
    """Part 1's leaf: the report's numbers beside what simulation measured."""

    description = "Write results/pipeline.json: part 1, predicted and measured."
    consumes = ["pipe_json", "schedule_pipe", "timing_nopipe", "timing_pipe"]
    produces = {"pipeline_summary": Path("results/pipeline.json")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, pipe_json, timing_nopipe, timing_pipe, **_) -> dict:
        rows = json.loads(Path(pipe_json).read_text(encoding="utf-8"))
        sims = {d["variant"]: d for d in (json.loads(Path(p).read_text(encoding="utf-8"))
                                          for p in (timing_nopipe, timing_pipe))}
        summary = [{**{k: r[k] for k in ("variant", "ii", "iteration_latency", "call_cycles",
                                         "dsp", "ff", "lut")},
                    "simulated": sims.get(r["variant"])} for r in rows]
        out = config.root_dir / "results" / "pipeline.json"
        out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        for s in summary:
            sim = s["simulated"] or {}
            print(f"{s['variant']:8s} II={s['ii']:<3} depth={s['iteration_latency']:<3} "
                  f"simulated: {sim.get('nsamp')} samples in {sim.get('call_cycles')} cycles, "
                  f"first y at cycle {sim.get('first_write_cycle')}")
        return {"pipeline_summary": out}


@dataclass(kw_only=True)
class UnrollSummaryStep(BuildStep):
    """The DAG's single leaf: part 2, with part 1 before it."""

    description = "Write results/summary.json: both parts."
    consumes = ["pipeline_summary", "unroll_json", "unroll_png", "schedule_nopart",
                "timing_unroll"]
    produces = {"summary": Path("results/summary.json")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, pipeline_summary, unroll_json, timing_unroll,
            **_) -> dict:
        unroll = json.loads(Path(unroll_json).read_text(encoding="utf-8"))
        summary = {
            "pipeline": json.loads(Path(pipeline_summary).read_text(encoding="utf-8")),
            "unroll": [{k: r[k] for k in ("variant", "unroll", "partition", "ii", "trip_count",
                                          "samples_per_cycle", "call_cycles", "dsp", "ff",
                                          "lut")} for r in unroll],
            "unroll_simulated": json.loads(Path(timing_unroll).read_text(encoding="utf-8")),
        }
        out = config.root_dir / "results" / "summary.json"
        out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary["unroll_simulated"], indent=2))
        return {"summary": out}


_RESULTS_MANIFEST = [{"filename": "results.json", "compare_fields": ["n", "y_bits"]}]


def _verify(name: str, actual: str, report: str, artifact: str = "verify_report"):
    return FunctionalVerifyStep(name=name, golden_dir_artifact="golden_dir",
                                actual_dir_artifact=actual, jsons=_RESULTS_MANIFEST,
                                report_path=report, report_artifact=artifact)


def build_poly_dag() -> BuildDag:
    dag = BuildDag()
    for artifact, path in (("poly_cpp", "poly.cpp"), ("poly_h", "poly.h"),
                           ("poly_tb", "tb_poly.cpp"), ("run_tcl", "run.tcl"),
                           ("golden_py", "golden.py"), ("analysis_py", "poly_analysis.py")):
        dag.add(SourceStep(artifact=artifact, path=_SOURCE_DIR / path))

    dag.add(MakeInputsStep(name="make_inputs"))
    dag.add(CSimStep(name="csim"))
    dag.add(_verify("verify_csim", "csim_dir", "results/verify_csim.json"))

    # Part 1: pipelining.
    dag.add(SynthStep(name="synth_pipe", part="pipe"))
    dag.add(PipeReportStep(name="pipe_report"))
    dag.add(ScheduleStep(name="schedule_pipe", which="pipe"))
    # Part 2: unrolling.
    dag.add(SynthStep(name="synth_unroll", part="unroll"))
    dag.add(UnrollReportStep(name="unroll_report"))
    dag.add(ScheduleStep(name="schedule_nopart", which="nopart"))

    for which in ("nopipe", "pipe", "unroll"):
        dag.add(CoSimStep(name=f"cosim_{which}", which=which))
        dag.add(_verify(f"verify_cosim_{which}", f"cosim_{which}_dir",
                        f"results/verify_cosim_{which}.json", f"verify_cosim_{which}_report"))
        dag.add(ExtractVcdStep(name=f"vcd_{which}", which=which))
        dag.add(TimingDiagramStep(name=f"timing_{which}", which=which))

    dag.add(PipelineSummaryStep(name="pipeline"))
    dag.add(UnrollSummaryStep(name="unroll"))
    return dag


def main() -> None:
    run_dag_cli(
        build_poly_dag,
        description="Pipeline and unroll a loop in Vitis HLS, and measure what each buys.",
        default_through="unroll",
        root_dir=_SOURCE_DIR,
        extra_args=[
            (("--unroll",), {"type": int, "nargs": "+", "default": DEFAULT_UNROLL,
                             "metavar": "N", "help": "Unroll factors to synthesize, "
                             "each with the arrays partitioned to match."}),
            (("--nopart",), {"type": int, "default": DEFAULT_NOPART, "metavar": "N",
                             "help": "The unroll factor also built without partitioning "
                                     "(0 for none)."}),
            (("--sim-unroll",), {"type": int, "default": DEFAULT_SIM_UNROLL, "metavar": "N",
                                 "help": "The unrolled variant to simulate; must be in --unroll."}),
            (("--live-output",), {"action": "store_true",
                                  "help": "Stream Vitis output instead of capturing it."}),
        ],
        params_from_args=lambda a: {
            "unroll": list(a.unroll),
            "nopart": a.nopart,
            "sim_unroll": a.sim_unroll,
            "live_output": a.live_output,
        },
    )


if __name__ == "__main__":
    main()
