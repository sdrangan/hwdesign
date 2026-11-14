"""Build script for the float-sum demo: what unrolling does to a reduction.

The kernel (``fsum.cpp``), the testbench (``tb_fsum.cpp``) and the Vitis
script (``run.tcl``) are hand-written.  This file adds the sequence:

    make_inputs -> csim -> verify_csim_<variant> (x4) -> synth -> report

``csim`` checks all four variants against the Python model (golden.py): they
add in different orders, and the test values are chosen so every order gives
the same, exact, sum.  ``synth`` builds each variant in its own Vitis project,
``proj_<variant>``, and ``report`` puts them side by side in
``results/fsum.md``.

    python fsum_build.py          # about 3 minutes

Steps are skipped when their inputs have not changed; ``--list-steps``
prints the sequence.  Requires the ``hwdesign-venv`` environment (the one
with ``waveflow``) and an installed Vitis HLS.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from waveflow.build.build import BuildConfig, BuildDag, BuildStep, SourceStep
from waveflow.build.cli import run_dag_cli
from waveflow.build.verify_steps import FunctionalVerifyStep
from waveflow.toolchain import toolchain

try:
    from golden import N, default_x, write_cases, write_golden
except ModuleNotFoundError:  # running from another directory
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from golden import N, default_x, write_cases, write_golden

_SOURCE_DIR = Path(__file__).resolve().parent
TOP = "fsum"
SOLUTION = "sol"
PERIOD_NS = 10.0             # 100 MHz

#: name -> (FSUM_VARIANT, the loop body)
VARIANTS = {
    "rolled": (0, "sum += x[i]"),
    "pragma": (1, "sum += x[i], UNROLL factor=4"),
    "tree": (2, "sum += (x0 + x1) + (x2 + x3)"),
    "lanes": (3, "part[j] += x[i+j], j = 0..3"),
}
SPECS = " ".join(f"{name}:{num}" for name, (num, _) in VARIANTS.items())


def _run_stage(config: BuildConfig, stage: str, out_dir: Path, *,
               live_output: bool = False) -> str:
    """Run one stage of run.tcl in the build root; return what Vitis printed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {"FSUM_STAGE": stage, "FSUM_OUT_DIR": out_dir.as_posix(), "FSUM_VARIANTS": SPECS,
           "FSUM_PERIOD": f"{PERIOD_NS:g}"}
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
def read_variant(root: Path, name: str) -> dict:
    """The sum loop's row of the loop table, the call's latency and the
    resources, from the text reports (the loop may be in a sub-function's)."""
    rdir = root / f"proj_{name}" / SOLUTION / "syn" / "report"
    top_rpt = rdir / f"{TOP}_csynth.rpt"
    if not top_rpt.exists():
        raise RuntimeError(f"No synthesis report at {top_rpt}.")
    loop = {}
    for rpt in [top_rpt] + sorted(p for p in rdir.glob("*_csynth.rpt") if p != top_rpt):
        for line in rpt.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*\|\s*[-+o]\s+(\S+)\s*\|(.*)\|\s*$", line)
            if m and m.group(1).startswith("sum_loop") and not loop:
                cells = [c.strip() for c in m.group(2).split("|")]
                if len(cells) == 7:
                    loop = {"loop": m.group(1), "iteration_latency": cells[2], "ii": cells[3],
                            "trip_count": cells[5]}
    text = top_rpt.read_text(encoding="utf-8", errors="replace")
    lat = re.search(r"Latency \(cycles\).*?\n(?:.*\n){2}\s*\|\s*(\d+)\|\s*(\d+)\|", text)
    tot = re.search(r"^\|Total\s*\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|", text, re.M)
    return {"variant": name, "body": VARIANTS[name][1], **loop,
            "call_cycles": int(lat.group(2)) if lat else None,
            "dsp": int(tot.group(2)) if tot else None, "ff": int(tot.group(3)) if tot else None,
            "lut": int(tot.group(4)) if tot else None}


def write_table(rows: list[dict], path: Path) -> Path:
    lines = [f"| Variant | Loop body | II | Trip count | Iteration latency | Cycles, {N} samples "
             "| DSP | FF | LUT |", "|" + "---|" * 9]
    for r in rows:
        lines.append(f"| {r['variant']} | `{r['body']}` | {r.get('ii', '-')} | "
                     f"{r.get('trip_count', '-')} | {r.get('iteration_latency', '-')} | "
                     f"{r['call_cycles']} | {r['dsp']} | {r['ff']} | {r['lut']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------- steps --
@dataclass(kw_only=True)
class MakeInputsStep(BuildStep):
    description = "Write data/cases.txt and the golden result from golden.py."
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
    description = "Run every variant in C simulation, into results/csim/<variant>."
    consumes = ["fsum_cpp", "fsum_h", "tb_cpp", "run_tcl", "cases"]
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
    consumes = ["fsum_cpp", "fsum_h", "run_tcl"] + [f"verify_{v}" for v in VARIANTS]
    produces = {"synth_done": Path("results/synth/vitis.log")}
    params = {"live_output": False}

    def run(self, config: BuildConfig, live_output, **_) -> dict:
        out_dir = config.root_dir / "results" / "synth"
        log = _run_stage(config, "synth", out_dir, live_output=live_output)
        marker = out_dir / "vitis.log"
        marker.write_text(log, encoding="utf-8")
        return {"synth_done": marker}


@dataclass(kw_only=True)
class ReportStep(BuildStep):
    description = "Write results/fsum.json and fsum.md: the four variants side by side."
    consumes = ["synth_done"]
    produces = {"fsum_json": Path("results/fsum.json")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        rows = [read_variant(config.root_dir, v) for v in VARIANTS]
        results = config.root_dir / "results"
        out = results / "fsum.json"
        out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(write_table(rows, results / "fsum.md").read_text(encoding="utf-8"))
        return {"fsum_json": out}


# ----------------------------------------------------------------------- dag --
_RESULTS = [{"filename": "results.json", "compare_fields": ["n", "sum_bits"]}]


def build_dag() -> BuildDag:
    dag = BuildDag()
    for artifact, path in (("fsum_cpp", "fsum.cpp"), ("fsum_h", "fsum.h"),
                           ("tb_cpp", "tb_fsum.cpp"), ("run_tcl", "run.tcl"),
                           ("golden_py", "golden.py")):
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
    return dag


def main() -> None:
    run_dag_cli(
        build_dag,
        description="The float-sum demo: a reduction unrolled four ways.",
        default_through="report",
        root_dir=_SOURCE_DIR,
        extra_args=[(("--live-output",), {"action": "store_true",
                                          "help": "Stream Vitis output instead of capturing it."})],
        params_from_args=lambda a: {"live_output": a.live_output},
    )


if __name__ == "__main__":
    main()
