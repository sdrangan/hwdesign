"""Build script for the float-sum demo: what unrolling does to a reduction.

The kernel (``fsum.cpp``), the testbench (``tb_fsum.cpp``) and the Vitis
script (``run.tcl``) are hand-written.  This file adds the sequence:

    make_inputs -> csim -> verify_csim_<variant> (x4) -> synth -> report, schedule

``csim`` checks all four variants against the Python model (golden.py): they
add in different orders, and the test values are chosen so every order gives
the same, exact, sum.  ``synth`` builds each variant in its own Vitis project,
``proj_<variant>``, and ``report`` puts them side by side in
``results/fsum.md``.  ``schedule`` reads each variant's schedule report and
writes ``results/schedule.md``: which state each add, read and running sum
is in, and the II the running sum allows.

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


# ----------------------------------------------------------------- schedule --
# Vitis writes the schedule of every module it synthesizes to
#   proj_<variant>/sol/.autopilot/db/<module>.verbose.sched.rpt
# -- an internal file (hidden folder, format may change between versions; this
# parser reads Vitis HLS 2025.1's).  The loop is scheduled inside `fsum` itself,
# except in lanes, where Vitis makes it a module of its own,
# fsum_Pipeline_sum_loop, and `fsum` keeps the epilogue after it.
_OP_LINE = re.compile(
    r'^ST_(?P<state>\d+) : Operation \d+ \[(?P<k>\d+)/(?P<n>\d+)\].*?'
    r'"%(?P<name>[\w.]+) = (?P<op>\w+) (?P<args>[^"]*)"(?: \[(?P<src>[^\]]+)\])?')
_PIPE = re.compile(r"Pipeline-0 : II = (?P<ii>\d+), D = (?P<d>\d+)")


def sched_reports(root: Path, name: str) -> list[Path]:
    """The variant's schedule reports: the loop's module first, then fsum."""
    db = root / f"proj_{name}" / SOLUTION / ".autopilot" / "db"
    found = [p for p in (db / f"{TOP}_Pipeline_sum_loop.verbose.sched.rpt",
                         db / f"{TOP}.verbose.sched.rpt") if p.is_file()]
    if not found:
        raise RuntimeError(f"No schedule report in {db}: synthesize {name} first.")
    return found


def read_schedule(path: Path) -> dict:
    """The float adds, the reads of x and the loads and stores of the running
    sums, each with the states it spans.

    An operation of n states appears in each, marked [n/n] down to [1/n].
    Dropped: the loop counter (an i10 or i11), the zeroing of the sums before
    the loop, bit casts and the rest of the bookkeeping, which take no time."""
    text = path.read_text(encoding="utf-8", errors="replace")
    pipe = _PIPE.search(text)
    ops: list[dict] = []
    open_ops: dict[str, dict] = {}
    for line in text.splitlines():
        hit = _OP_LINE.match(line)
        if hit is None:
            continue
        op, name, args = hit["op"], hit["name"], hit["args"]
        if op == "fadd":
            pass
        elif op == "load" and ("%x_addr" in args or args.startswith("i32 ")):
            pass
        elif op == "store" and args.startswith("i32 ") and not args.startswith("i32 0,"):
            pass
        else:
            continue
        state, k, n = int(hit["state"]), int(hit["k"]), int(hit["n"])
        entry = open_ops.get(name)
        if k == n or entry is None:
            entry = {"name": name, "op": op, "args": args.replace("%", ""),
                     "first": state, "last": state,
                     "src": (hit["src"] or "").split("->")[0]}
            ops.append(entry)
            open_ops[name] = entry
        entry["last"] = max(entry["last"], state)
    ops.sort(key=lambda o: (o["first"], o["name"]))
    return {"report": path, "ii": int(pipe["ii"]) if pipe else None,
            "depth": int(pipe["d"]) if pipe else None, "ops": ops}


def recurrences(sched: dict) -> list[dict]:
    """Each running sum the loop loads and later stores: the loop-carried
    dependencies.  The next iteration may load in the state this one
    stores, so they allow II >= store state - load state."""
    loads = {o["args"].split()[-1]: o["first"] for o in sched["ops"] if o["op"] == "load"
             and not o["args"].endswith(("x_addr",)) and "x_addr" not in o["args"]}
    out = []
    for o in sched["ops"]:
        if o["op"] == "store":
            var = o["args"].split()[-1]
            if var in loads:
                out.append({"var": var, "load": loads[var], "store": o["first"],
                            "ii_min": o["first"] - loads[var]})
    return out


def adders_built(root: Path, name: str) -> int:
    """fadd instances in every module's synthesis report, counted once each."""
    rdir = root / f"proj_{name}" / SOLUTION / "syn" / "report"
    names = set()
    for rpt in rdir.glob("*_csynth.rpt"):
        names.update(re.findall(r"^\s*\|(fadd_\w+_U\d+)\s*\|", rpt.read_text(
            encoding="utf-8", errors="replace"), re.M))
    return len(names)


def describe_schedule(root: Path, name: str) -> list[str]:
    lines = [f"## {name}: `{VARIANTS[name][1]}`", ""]
    for path in sched_reports(root, name):
        sched = read_schedule(path)
        rel = path.relative_to(root).as_posix()
        if sched["ii"]:
            lines += [f"`{rel}`: the loop, II = {sched['ii']}, depth = {sched['depth']} "
                      "states", ""]
        else:
            lines += [f"`{rel}`: after the loop, not pipelined", ""]
        lines += ["| Operation | Kind | States | Slot | Operands | Source |", "|---|---|---|---|---|---|"]
        for o in sched["ops"]:
            span = str(o["first"]) if o["first"] == o["last"] else f"{o['first']}-{o['last']}"
            slot = (str(o["first"] % sched["ii"]) if sched["ii"] and o["op"] == "fadd" else "")
            lines.append(f"| {o['name']} | {o['op']} | {span} | {slot} | {o['args']} | "
                         f"{o['src']} |")
        lines.append("")
        adds = [o for o in sched["ops"] if o["op"] == "fadd"]
        if sched["ii"]:
            slots = sorted({o["first"] % sched["ii"] for o in adds})
            lines.append(f"{len(adds)} add{'s' if len(adds) > 1 else ''} start"
                         f"{'' if len(adds) > 1 else 's'} in state{'s' if len(adds) > 1 else ''} "
                         f"{', '.join(str(o['first']) for o in adds)}: slots "
                         f"{', '.join(str(o['first'] % sched['ii']) for o in adds)} mod "
                         f"{sched['ii']}, {len(slots)} different.")
            for r in recurrences(sched):
                lines.append(f"Loop-carried: `{r['var']}` loaded in state {r['load']}, stored "
                             f"in state {r['store']}: II >= {r['store']} - {r['load']} = "
                             f"{r['ii_min']}.")
        elif adds:
            together = [s for s in {o["first"] for o in adds}
                        if sum(o["first"] == s for o in adds) > 1]
            if together:
                lines.append(f"Adds starting together in state {together[0]}: one adder each.")
        lines.append("")
    lines += [f"Adders built (fadd instances in the synthesis reports): "
              f"{adders_built(root, name)}", ""]
    return lines


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


@dataclass(kw_only=True)
class ScheduleStep(BuildStep):
    description = ("Write results/schedule.md: each variant's adds, reads and sums, state by "
                   "state, from Vitis's schedule reports.")
    consumes = ["synth_done"]
    produces = {"schedule_md": Path("results/schedule.md")}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        lines = ["# The four variants, state by state", "",
                 "From `proj_<variant>/sol/.autopilot/db/*.verbose.sched.rpt`.  A state is a "
                 "clock cycle of one iteration; Slot is an add's first state mod II.", ""]
        for v in VARIANTS:
            lines += describe_schedule(config.root_dir, v)
        out = config.root_dir / "results" / "schedule.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote {out}")
        return {"schedule_md": out}


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
    dag.add(ScheduleStep(name="schedule"))
    return dag


def main() -> None:
    run_dag_cli(
        build_dag,
        description="The float-sum demo: a reduction unrolled four ways.",
        default_through="schedule",
        root_dir=_SOURCE_DIR,
        extra_args=[(("--live-output",), {"action": "store_true",
                                          "help": "Stream Vitis output instead of capturing it."})],
        params_from_args=lambda a: {"live_output": a.live_output},
    )


if __name__ == "__main__":
    main()
