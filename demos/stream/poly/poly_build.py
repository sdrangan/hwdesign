"""Build script for the poly demo: a streaming polynomial with in-band commands.

The kernel (``poly.cpp``), the testbench (``tb_poly.cpp``) and the Vitis
script (``run.tcl``) are written by hand.  The only generated code is the
headers in ``include/``, which pack and unpack the messages defined in
``poly_schema.py``.  What this file adds is the *sequence*:

    gen_include --+
    pysim --------+-> csim -> verify_csim -> csynth -> cosim -> verify_cosim
          |                                                  -> extract_vcd -> timing_diagram
          +-> plot_python
                                                           (all of it) -> report

Running it is one command::

    python poly_build.py                        # the whole flow
    python poly_build.py --through plot_python  # Python only, no Vitis
    python poly_build.py --through verify_csim  # fast: no synthesis

Steps are skipped when their inputs have not changed, and ``--force``
re-runs everything.  Options such as ``--word-bw`` only take effect when
their step runs, so pair them with ``--force-step`` -- see the README.

Requires the ``hwdesign-venv`` environment (the one with ``waveflow``) and,
from ``csim`` on, an installed Vitis HLS.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np

from waveflow.build.build import BuildConfig, BuildDag, BuildStep, SourceStep
from waveflow.build.cli import run_dag_cli

_SOURCE_DIR = Path(__file__).resolve().parent
if str(_SOURCE_DIR) not in sys.path:  # running from another directory
    sys.path.insert(0, str(_SOURCE_DIR))

import poly_golden as golden  # noqa: E402
import poly_schema as schema  # noqa: E402


# ---------------------------------------------------------------------------
# Generated headers
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class GenIncludeStep(BuildStep):
    """Generate the C++ headers that pack and unpack the messages."""

    description = "Generate include/ from poly_schema.py: one header per message, plus stream utilities."
    consumes = ["schema_py"]
    produces = {"include_dir": Path(schema.INCLUDE_DIR)}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        from waveflow.build.streamutils import StreamUtilsStep
        from waveflow.hw.arrayutils import ArrayUtilsStep
        from waveflow.hw.dataschema import DataSchemaStep

        include_dir = config.root_dir / schema.INCLUDE_DIR
        # Start clean, so a schema that was renamed or removed leaves no
        # stale header behind.
        shutil.rmtree(include_dir, ignore_errors=True)

        inner = BuildDag()
        inner.add(StreamUtilsStep(output_dir=schema.INCLUDE_DIR))
        for cls in schema.SCHEMA_CLASSES:
            inner.add(DataSchemaStep(cls, word_bw_supported=schema.WORD_BW_SUPPORTED,
                                     include_dir=schema.INCLUDE_DIR))
        inner.add(ArrayUtilsStep(schema.Float32, schema.WORD_BW_SUPPORTED))
        results = inner.run(config)
        failed = [name for name, r in results.items() if not r.success]
        if failed:
            raise RuntimeError(f"Header generation failed: {failed}")
        print(f"Generated {len(list(include_dir.glob('*.h')))} headers in {schema.INCLUDE_DIR}/")
        return {"include_dir": include_dir}


# ---------------------------------------------------------------------------
# Python: the golden model and its plot
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class PySimStep(BuildStep):
    """Write the test transactions, and the responses the model expects."""

    description = "Write vectors/ (the commands) and results/golden/ (the expected responses)."
    consumes = ["golden_py", "schema_py"]
    produces = {"py_vectors": Path("vectors"), "golden_dir": Path("results/golden")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        txns = golden.test_transactions()
        in_dir = config.root_dir / "vectors"
        out_dir = config.root_dir / "results" / "golden"
        shutil.rmtree(in_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)
        golden.write_inputs(in_dir, txns)
        golden.write_expected(out_dir, txns)
        print(f"Wrote {len(txns)} transactions to vectors/ and their expected "
              f"responses to results/golden/:")
        print(golden.summary(txns))
        return {"py_vectors": in_dir, "golden_dir": out_dir}


def _poly_tex(coeffs) -> str:
    """``[1, -2, 0, 4]`` -> ``1 - 2x + 4x^3``, for a plot label."""
    out = ""
    for p, c in enumerate(coeffs):
        if c == 0:
            continue
        mag = abs(float(c))
        coef = "" if (mag == 1 and p) else f"{mag:g}"
        term = coef + ("" if p == 0 else "x" if p == 1 else f"x^{p}")
        sign = "-" if c < 0 else "+"
        out += (f" {sign} " if out else ("-" if c < 0 else "")) + term
    return out or "0"


@dataclass(kw_only=True)
class PlotPythonStep(BuildStep):
    """Plot each transaction's polynomial, as the model evaluates it."""

    description = "Plot y against x for each transaction to results/poly_python.png."
    consumes = ["py_vectors", "golden_dir"]
    produces = {"python_plot": Path("results/poly_python.png")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, py_vectors, golden_dir, **_) -> dict:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 4.5))
        for k in range(golden.count_transactions(Path(py_vectors))):
            tx_id, coeffs, x = golden.read_transaction(Path(py_vectors), k)
            resp = golden.read_response(Path(golden_dir), k, len(x))
            ax.plot(x, resp.y, "o-", ms=3, lw=1,
                    label=f"tx_id 0x{tx_id:02x}:  $y = {_poly_tex(coeffs)}$  ({len(x)} samples)")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_title("Output of the Python golden model, per transaction")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", frameon=False, fontsize=9)
        fig.tight_layout()

        out = config.root_dir / "results" / "poly_python.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=120)
        plt.close(fig)
        print(f"Wrote {out.relative_to(config.root_dir)}")
        return {"python_plot": out}


# ---------------------------------------------------------------------------
# Vitis: C simulation, synthesis, co-simulation
# ---------------------------------------------------------------------------

#: The teaching kernels are written for one word width each; the general
#: kernel takes either.
KERNELS = {"poly32": 32, "poly64": 64, "general": None}


def _word_bw(kernel: str, word_bw: int | None) -> int:
    """The word width to build ``kernel`` with: its own, or ``--word-bw``, or 32."""
    fixed = KERNELS[kernel]
    if word_bw is None:
        return fixed or 32
    if fixed is not None and word_bw != fixed:
        raise RuntimeError(f"--kernel {kernel} is written for a {fixed}-bit stream; "
                           f"drop --word-bw, or pass --word-bw {fixed}.")
    return word_bw


def _run_stage(config: BuildConfig, stage: str, kernel: str, word_bw: int | None,
               live_output: bool, env: dict[str, str] | None = None) -> None:
    """Run one stage of ``run.tcl``; raise with the error lines if it fails.

    The tool's output goes to ``results/<stage>/vitis.log``.
    """
    from waveflow.toolchain import toolchain

    word_bw = _word_bw(kernel, word_bw)
    log = config.root_dir / "results" / stage / "vitis.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    def attempt():
        return toolchain.run_vitis_hls(
            config.root_dir / "run.tcl",
            work_dir=config.root_dir,
            capture_output=not live_output,
            env={"POLY_STAGE": stage, "POLY_KERNEL": kernel, "POLY_WORD_BW": str(word_bw),
                 **(env or {})},
        )

    try:
        try:
            result = attempt()
        except subprocess.CalledProcessError as exc:
            # On Windows, co-simulation now and then fails while generating
            # its testbench files ("COSIM 212-5", with no compiler error) and
            # then passes when simply run again -- most likely a file briefly
            # locked by another process.  Retry that one failure, once.  A
            # real failure -- a compile error, a testbench FAIL, an RTL
            # mismatch -- reports a different message, so this cannot hide one.
            text = (exc.stdout or "") + (exc.stderr or "")
            if stage != "cosim" or "COSIM 212-5" not in text or ": error:" in text:
                raise
            print("Co-simulation failed while generating its files (COSIM 212-5); "
                  "retrying once.")
            result = attempt()
        log.write_text((result.stdout or "") + (result.stderr or ""), encoding="utf-8")
    except subprocess.CalledProcessError as exc:
        text = (exc.stdout or "") + (exc.stderr or "")
        log.write_text(text, encoding="utf-8")
        lines = [ln.strip() for ln in text.splitlines()]
        errors = ([ln for ln in lines if ": error:" in ln or "FAIL" in ln][:6]
                  + [ln for ln in lines if ln.startswith("ERROR")][:3])
        detail = "\n  ".join(errors) if errors else f"see {log}"
        raise RuntimeError(
            f"Vitis HLS stage '{stage}' failed (exit {exc.returncode}):\n  {detail}"
        ) from exc
    print(f"Vitis HLS stage '{stage}' done (kernel {kernel}, WORD_BW={word_bw}); "
          f"log in {log.relative_to(config.root_dir)}")


def _fresh_output_dir(config: BuildConfig, stage: str) -> Path:
    """Empty ``results/<stage>/`` of message files, so an earlier run's cannot pass for this one's."""
    out = config.root_dir / "results" / stage
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("txn*.bin"):
        f.unlink()
    return out


def _check_wrote(out: Path, stage: str, in_dir: Path) -> None:
    n = golden.count_transactions(in_dir)
    missing = [k for k in range(n) if not (out / f"txn{k}_resp_ftr.bin").exists()]
    if missing:
        raise RuntimeError(f"{stage} ran but the testbench wrote no response for "
                           f"transaction(s) {missing} in {out}.")


@dataclass(kw_only=True)
class CSimStep(BuildStep):
    """Compile the testbench against the C++ kernel and run the transactions."""

    description = "Run Vitis C simulation; the testbench writes results/csim/."
    consumes = ["poly_cpp", "poly32_cpp", "poly64_cpp", "poly_hpp", "tb_poly", "run_tcl", "include_dir",
                "py_vectors"]
    produces = {"csim_dir": Path("results/csim")}
    params = {"kernel": "general", "word_bw": None, "live_output": False}

    def run(self, config: BuildConfig, py_vectors, kernel, word_bw, live_output, **_) -> dict:
        out = _fresh_output_dir(config, "csim")
        _run_stage(config, "csim", kernel, word_bw, live_output)
        _check_wrote(out, "C simulation", Path(py_vectors))
        return {"csim_dir": out}


@dataclass(kw_only=True)
class CSynthStep(BuildStep):
    """Synthesize the kernel to RTL."""

    description = "Run Vitis C synthesis; the report is copied to results/csynth/."
    # verify_csim_report orders synthesis after a *verified* C simulation,
    # which is also the stage that (re)creates the project.
    consumes = ["poly_cpp", "poly32_cpp", "poly64_cpp", "poly_hpp", "run_tcl", "include_dir",
                "verify_csim_report"]
    produces = {"csynth_report": Path("results/csynth/poly_csynth.rpt")}
    params = {"kernel": "general", "word_bw": None, "live_output": False}

    def run(self, config: BuildConfig, kernel, word_bw, live_output, **_) -> dict:
        _run_stage(config, "csynth", kernel, word_bw, live_output)
        made = config.root_dir / "poly_proj/solution1/syn/report/poly_csynth.rpt"
        if not made.exists():
            raise RuntimeError(f"C synthesis ran but wrote no report at {made}.")
        report = config.root_dir / "results" / "csynth" / "poly_csynth.rpt"
        report.write_bytes(made.read_bytes())
        return {"csynth_report": report}


@dataclass(kw_only=True)
class CoSimStep(BuildStep):
    """Re-run the same testbench against the synthesized RTL."""

    description = "Run RTL co-simulation; the testbench writes results/cosim/."
    consumes = ["tb_poly", "run_tcl", "py_vectors", "csynth_report"]
    produces = {"cosim_dir": Path("results/cosim")}
    # `port` records the IP's ports for extract_vcd to replay.
    params = {"kernel": "general", "word_bw": None, "trace_level": "port", "live_output": False}

    def run(self, config: BuildConfig, py_vectors, kernel, word_bw, trace_level, live_output,
            **_) -> dict:
        out = _fresh_output_dir(config, "cosim")
        _run_stage(config, "cosim", kernel, word_bw, live_output,
                   env={"POLY_TRACE_LEVEL": trace_level})
        _check_wrote(out, "Co-simulation", Path(py_vectors))
        return {"cosim_dir": out}


@dataclass(kw_only=True)
class ExtractVcdStep(BuildStep):
    """Re-run the RTL simulation with VCD logging switched on.

    Co-simulation writes an AMD-proprietary ``.wdb`` waveform database that
    only Vivado can open; ``run_xsim_vcd`` patches the generated simulation
    scripts and runs the simulator again to get an open ``.vcd``.
    """

    description = "Re-run the RTL simulation with VCD logging and collect vcd/dump.vcd."
    consumes = ["cosim_dir"]
    produces = {"vcd": Path("vcd/dump.vcd")}
    params = {"trace_level": "port"}

    def run(self, config: BuildConfig, trace_level, **_) -> dict:
        from waveflow.scripts.xsim_vcd import run_xsim_vcd

        vcd_path = Path(run_xsim_vcd(top="poly", comp="poly_proj", soln="solution1",
                                     out="dump.vcd", trace_level=trace_level,
                                     workdir=config.root_dir))
        n_signals = vcd_path.read_text(encoding="utf-8", errors="replace").count("$var")
        if n_signals == 0:
            raise RuntimeError(f"{vcd_path} declares no signals -- the RTL simulation "
                               f"logged nothing (trace_level={trace_level!r}).")
        print(f"VCD has {n_signals} signals.")
        return {"vcd": vcd_path}


@dataclass(kw_only=True)
class TimingDiagramStep(BuildStep):
    """Decode every message from the VCD, measure the timing, and plot it.

    Two figures.  The waveform shows transaction 0 cycle by cycle, each
    burst shaded by the message it carries.  The overview shows every
    burst of every transaction on both ports, with the stalls marked.

    The decoded messages are also checked against the vectors and the
    model -- read off the wires rather than out of the testbench's files.
    """

    description = ("Decode the messages from the VCD; plot them and write "
                   "results/stream_timing.json.")
    consumes = ["vcd", "py_vectors", "golden_dir", "timing_py"]
    produces = {
        "timing_diagram": Path("results/timing_diagram.png"),
        "transactions_plot": Path("results/transactions.png"),
        "stream_timing": Path("results/stream_timing.json"),
    }
    params = {"trange": None}

    def run(self, config: BuildConfig, vcd, py_vectors, golden_dir, trange, **_) -> dict:
        import poly_timing

        in_dir, gold_dir = Path(py_vectors), Path(golden_dir)
        ntxn = golden.count_transactions(in_dir)
        trace = poly_timing.decode(Path(vcd), ntxn)
        results = config.root_dir / "results"

        failures = []
        for t in trace.txns:
            tx_id, coeffs, x = golden.read_transaction(in_dir, t.k)
            exp = golden.read_response(gold_dir, t.k, len(x))
            where = f"txn {t.k} (tx_id 0x{tx_id:02x})"
            if (int(t.cmd_hdr.tx_id) != tx_id or int(t.cmd_hdr.nsamp) != len(x)
                    or not np.array_equal(np.asarray(t.cmd_hdr.coeffs, np.float32), coeffs)
                    or not np.array_equal(t.x, x)):
                failures.append(f"{where}: the command on in_stream is not the test vector")
            if (int(t.resp_hdr.tx_id) != exp.tx_id or not np.array_equal(t.y, exp.y)
                    or int(t.resp_ftr.nsamp_read) != exp.nsamp_read
                    or int(t.resp_ftr.error) != int(exp.error)):
                failures.append(f"{where}: the response on out_stream differs from the model")

        diagram = poly_timing.write_timing_diagram(
            Path(vcd), results / "timing_diagram.png", trace,
            trange=tuple(trange) if trange else None)
        overview = poly_timing.write_transaction_plot(results / "transactions.png", trace)

        timing = {
            "word_bw": trace.word_bw,
            "clk_period_ns": trace.clk_period_ns,
            "transactions": poly_timing.measure(trace),
            "messages_match": not failures,
        }
        out = results / "stream_timing.json"
        out.write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")
        for m in timing["transactions"]:
            print(f"tx_id 0x{m['tx_id']:02x}: {m['nsamp']} samples, latency "
                  f"{m['latency_cycles']} cycles, transaction {m['transaction_cycles']} "
                  f"cycles (command header stalled {m['cmd_hdr_stall_cycles']})")
        if failures:
            raise RuntimeError("Decoded messages differ:\n  " + "\n  ".join(failures))
        return {"timing_diagram": diagram, "transactions_plot": overview,
                "stream_timing": out}


# ---------------------------------------------------------------------------
# The comparison against the Python model
# ---------------------------------------------------------------------------

@dataclass(kw_only=True)
class CompareStep(BuildStep):
    """Compare a Vitis run's responses against the Python model's, message by message.

    Used twice: after C simulation (is the C++ right?) and after
    co-simulation (does the RTL still do what the C++ did?).  Every field
    of every message is checked -- the echoed tx_id and the footer as well
    as the samples, because a kernel that computes the right numbers but
    answers the wrong command is still wrong.
    """

    description = "Compare a testbench's response files against results/golden/."
    params: ClassVar[dict] = {}

    actual_artifact: str
    report_artifact: str
    report_path: str
    rtol: float = 1e-5
    atol: float = 1e-6

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return ["py_vectors", "golden_dir", self.actual_artifact]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {self.report_artifact: Path(self.report_path)}

    def run(self, config: BuildConfig, py_vectors, golden_dir, **artifacts) -> dict:
        in_dir, gold_dir = Path(py_vectors), Path(golden_dir)
        actual_dir = Path(artifacts[self.actual_artifact])

        failures: list[str] = []
        txns = []
        for k in range(golden.count_transactions(in_dir)):
            tx_id, _, x = golden.read_transaction(in_dir, k)
            exp = golden.read_response(gold_dir, k, len(x))
            got = golden.read_response(actual_dir, k, len(x))
            close = np.isclose(got.y, exp.y, rtol=self.rtol, atol=self.atol)
            err = np.abs(got.y.astype(np.float64) - exp.y.astype(np.float64))
            txn = {
                "tx_id": tx_id,
                "nsamp": len(x),
                "tx_id_echoed": got.tx_id,
                "nsamp_read": got.nsamp_read,
                "error": got.error.name,
                "exact_matches": int(np.sum(got.y == exp.y)),
                "max_abs_err": float(err.max()) if len(x) else 0.0,
            }
            txns.append(txn)

            where = f"txn {k} (tx_id 0x{tx_id:02x})"
            if got.tx_id != exp.tx_id:
                failures.append(f"{where}: response header echoes tx_id 0x{got.tx_id:02x}")
            if got.error != exp.error:
                failures.append(f"{where}: footer reports {got.error.name}")
            if got.nsamp_read != exp.nsamp_read:
                failures.append(f"{where}: footer says {got.nsamp_read} samples read, "
                                f"expected {exp.nsamp_read}")
            bad = np.flatnonzero(~close)
            if bad.size:
                i = int(bad[0])
                failures.append(f"{where}: {bad.size} of {len(x)} samples differ; first "
                                f"at x={x[i]:.6g}: model {exp.y[i]:.9g}, kernel {got.y[i]:.9g}")
            print(f"{where}: {txn['exact_matches']} of {len(x)} samples bit-exact, "
                  f"max |error| = {txn['max_abs_err']:.3g}; tx_id echoed 0x{got.tx_id:02x}, "
                  f"footer {got.nsamp_read} read, {got.error.name}")

        report = {"pass": not failures, "actual": actual_dir.name,
                  "rtol": self.rtol, "atol": self.atol,
                  "transactions": txns, "failures": failures}
        out = config.root_dir / self.report_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if failures:
            raise RuntimeError(f"'{self.name}' failed:\n  " + "\n  ".join(failures))
        return {self.report_artifact: out}


@dataclass(kw_only=True)
class ReportStep(BuildStep):
    """Collect the verdicts and the measured timing into one small summary."""

    description = "Write results/summary.json: the comparison verdicts and the timing."
    # Consuming the plot and the timing as well makes this the DAG's single
    # leaf, so the default `--through report` runs everything.
    consumes = ["python_plot", "verify_csim_report", "verify_cosim_report", "stream_timing"]
    produces = {"summary": Path("results/summary.json")}
    params = {"kernel": "general"}

    def run(self, config: BuildConfig, python_plot, verify_csim_report,
            verify_cosim_report, stream_timing, kernel, **_) -> dict:
        def load(p):
            return json.loads(Path(p).read_text(encoding="utf-8"))

        csim, cosim = load(verify_csim_report), load(verify_cosim_report)
        timing = load(stream_timing)
        summary = {
            "top": "poly",
            "kernel": kernel,
            # Read off the VCD, so it is the width the RTL was actually built with.
            "word_bw": timing["word_bw"],
            "transactions": len(csim["transactions"]),
            "csim_verified": csim["pass"],
            "cosim_verified": cosim["pass"],
            "cosim_max_abs_err": max(t["max_abs_err"] for t in cosim["transactions"]),
            "messages_on_wires_match": timing["messages_match"],
            "latency_cycles": [t["latency_cycles"] for t in timing["transactions"]],
            "transaction_cycles": [t["transaction_cycles"] for t in timing["transactions"]],
            "python_plot": Path(python_plot).relative_to(config.root_dir).as_posix(),
        }
        out = config.root_dir / "results" / "summary.json"
        out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return {"summary": out}


def build_poly_dag() -> BuildDag:
    dag = BuildDag()

    # The hand-written sources.  Declaring them makes a step re-run when its
    # source changes.
    dag.add(SourceStep(artifact="poly_cpp", path=_SOURCE_DIR / "poly.cpp"))
    dag.add(SourceStep(artifact="poly32_cpp", path=_SOURCE_DIR / "poly32.cpp"))
    dag.add(SourceStep(artifact="poly64_cpp", path=_SOURCE_DIR / "poly64.cpp"))
    dag.add(SourceStep(artifact="poly_hpp", path=_SOURCE_DIR / "poly.hpp"))
    dag.add(SourceStep(artifact="tb_poly", path=_SOURCE_DIR / "tb_poly.cpp"))
    dag.add(SourceStep(artifact="run_tcl", path=_SOURCE_DIR / "run.tcl"))
    dag.add(SourceStep(artifact="schema_py", path=_SOURCE_DIR / "poly_schema.py"))
    dag.add(SourceStep(artifact="golden_py", path=_SOURCE_DIR / "poly_golden.py"))
    dag.add(SourceStep(artifact="timing_py", path=_SOURCE_DIR / "poly_timing.py"))

    dag.add(GenIncludeStep(name="gen_include"))
    dag.add(PySimStep(name="pysim"))
    dag.add(PlotPythonStep(name="plot_python"))

    dag.add(CSimStep(name="csim"))
    dag.add(CompareStep(name="verify_csim", actual_artifact="csim_dir",
                        report_artifact="verify_csim_report",
                        report_path="results/verify_csim.json"))
    dag.add(CSynthStep(name="csynth"))
    dag.add(CoSimStep(name="cosim"))
    dag.add(CompareStep(name="verify_cosim", actual_artifact="cosim_dir",
                        report_artifact="verify_cosim_report",
                        report_path="results/verify_cosim.json"))
    dag.add(ExtractVcdStep(name="extract_vcd"))
    dag.add(TimingDiagramStep(name="timing_diagram"))

    dag.add(ReportStep(name="report"))
    return dag


def main() -> None:
    run_dag_cli(
        build_poly_dag,
        description="Simulate the poly in-band streaming demo in Python, C and RTL.",
        default_through="report",
        root_dir=_SOURCE_DIR,
        extra_args=[
            (("--kernel",), {"default": "general", "choices": list(KERNELS),
                             "help": "Which kernel to build: poly32 or poly64, written out "
                                     "for one word width, or the general poly.cpp."}),
            (("--word-bw",), {"type": int, "default": None, "choices": schema.WORD_BW_SUPPORTED,
                              "help": "Stream word width in bits: 32 carries one float "
                                      "sample per word, 64 carries two.  Defaults to the "
                                      "kernel's own, or 32 for the general kernel."}),
            (("--trace-level",), {"default": "port", "choices": ["port", "all"],
                                  "help": "Which signals co-simulation records for the VCD."}),
            (("--trange",), {"type": float, "nargs": 2, "default": None,
                             "metavar": ("T0", "T1"),
                             "help": "Time range in ns for the waveform.  By default it "
                                     "spans transaction 0."}),
            (("--live-output",), {"action": "store_true",
                                  "help": "Stream Vitis output instead of capturing it "
                                          "to results/<stage>/vitis.log."}),
        ],
        params_from_args=lambda a: {
            "kernel": a.kernel,
            "word_bw": a.word_bw,
            "trace_level": a.trace_level,
            "trange": tuple(a.trange) if a.trange else None,
            "live_output": a.live_output,
        },
    )


if __name__ == "__main__":
    main()
