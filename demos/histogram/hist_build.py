"""Build script for the histogram demo: a free-running kernel that reaches memory through
Waveflow's transactional adaptors.

Two versions share the task bodies (``hist_*.h``) and the messages (``hist_schema.py``), and
differ in how a command reaches the kernel and a response leaves it:

    --top stream   histogram_stream.cpp: command and response on AXI4-Streams
    --top mm       histogram_mm.v: the same kernel behind Waveflow's memory-mapped slave
                   adaptor -- a host writes commands into a queue and reads responses out of one

Each version builds into its own directories -- ``proj_<top>/``, ``csim_proj_<top>/``,
``xsi_<top>/`` and ``results/<top>/`` -- so building one never touches the other's output.
The steps:

    stream: gen_include -> vectors -> csim -> verify_csim -> synth -> xsi -> verify_xsi -> timing
    mm:     gen_include -> vectors -> synth -> xsi -> verify_xsi -> timing

The mm version synthesizes the same kernel (``histogram_stream``) and has no C simulation of its
own; its XSI top is the hand-assembled ``histogram_mm.v`` plus Waveflow's adaptor RTL, driven by
a host model (``tb_xsi_histogram_mm.cpp``) on its AXI slave port.

``gen_include`` writes ``include/``: this kernel's HistCmd / HistResp headers from
``hist_schema.py``, and Waveflow's adaptor headers (``mem_r_stream_task.h``,
``mem_w_stream_done_task.h``, ``MRCmd`` / ``MWCmd`` / ``MemComplete``) verbatim, the way its
own generator copies them.  ``csim`` runs Vitis C simulation; ``synth`` runs C synthesis;
``xsi`` drives the synthesized RTL with Waveflow's AXI bus models and dumps a waveform;
``timing`` measures each job's phases from it.  Every count and every response is checked
against the NumPy golden (``hist_golden.py``) after both simulations.

    python hist_build.py                          # everything, the stream version: ~3 minutes
    python hist_build.py --through verify_csim    # C simulation only: ~40 s
    python hist_build.py --top mm                 # the mm version: synthesis, XSI, timing

Steps are skipped when their inputs have not changed; ``--list-steps`` prints them.
Requires the ``hwdesign-venv`` environment (the one with ``waveflow``) and Vitis/Vivado 2025.1.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np

from waveflow.build.build import BuildConfig, BuildDag, BuildStep, SourceStep
from waveflow.build.cli import run_dag_cli
from waveflow.toolchain import toolchain

_SOURCE_DIR = Path(__file__).resolve().parent
if str(_SOURCE_DIR) not in sys.path:      # running from another directory
    sys.path.insert(0, str(_SOURCE_DIR))

import hist_golden as golden  # noqa: E402
import hist_schema as schema  # noqa: E402

@dataclass(frozen=True)
class Version:
    """What --top selects.

    kernel   the HLS top that is synthesized.  Both versions synthesize the same one: the mm
             version changes what is on the other end of the kernel's streams, not the kernel.
    rtl_top  the Verilog top the XSI testbench drives.
    scope    where the kernel's own signals are in the waveform.
    csim     whether the version has a C simulation of its own (mm's kernel is stream's).
    rtl      extra Verilog: the hand-assembled top and Waveflow's slave adaptor.
    """
    kernel: str
    rtl_top: str
    scope: str
    csim: bool
    rtl: tuple[str, ...] = ()

    @property
    def mm(self) -> bool:
        return self.rtl_top != self.kernel


#: Waveflow's slave adaptor RTL, used as it is (waveflow/build/rtl).
ADAPTOR_RTL = ("axi_slave_front.v", "mm_queue_in.v", "mm_queue_out.v", "mm_sync_fifo.v")

VERSIONS = {
    "stream": Version(kernel="histogram_stream", rtl_top="histogram_stream",
                      scope="histogram_stream", csim=True),
    "mm":     Version(kernel="histogram_stream", rtl_top="histogram_mm",
                      scope="histogram_mm.u_kernel", csim=False, rtl=("histogram_mm.v",)),
}
TOPS = {k: v.rtl_top for k, v in VERSIONS.items()}
SHARED_SOURCES = ["hist_types.h", "hist_control.h", "hist_compute.h", "hist_response.h"]


def adaptor_rtl() -> list[Path]:
    import waveflow
    d = Path(waveflow.__file__).resolve().parent / "build" / "rtl"
    return [d / f for f in ADAPTOR_RTL]


# ---------------------------------------------------------------- headers --
@dataclass(kw_only=True)
class GenIncludeStep(BuildStep):
    """Generate include/: the kernel's message headers and Waveflow's adaptor headers."""

    description = "Generate include/: HistCmd/HistResp from hist_schema.py, plus Waveflow's adaptors."
    consumes = ["schema_py"]
    produces = {"include_dir": Path(schema.INCLUDE_DIR)}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        from waveflow.build.streamutils import MemStreamStep, StreamUtilsStep
        from waveflow.hw.dataschema import DataSchemaStep
        from waveflow.hw.mem_stream import SCHEMA_CLASSES as MEM_SCHEMAS
        from waveflow.hw.mem_stream import WORD_BW_SUPPORTED as MEM_WORD_BW

        include_dir = config.root_dir / schema.INCLUDE_DIR
        shutil.rmtree(include_dir, ignore_errors=True)   # no stale header survives a rename
        inner = BuildDag()
        inner.add(StreamUtilsStep(output_dir=schema.INCLUDE_DIR))
        inner.add(MemStreamStep(output_dir=schema.INCLUDE_DIR))      # the adaptor task bodies
        for cls in MEM_SCHEMAS:                                      # MRCmd, MWCmd, MemComplete
            inner.add(DataSchemaStep(cls, word_bw_supported=MEM_WORD_BW,
                                     include_dir=schema.INCLUDE_DIR))
        for cls in schema.SCHEMA_CLASSES:                            # HistCmd, HistResp
            inner.add(DataSchemaStep(cls, word_bw_supported=schema.WORD_BW_SUPPORTED,
                                     include_dir=schema.INCLUDE_DIR))
        results = inner.run(config, force=True)
        failed = [name for name, r in results.items() if not r.success]
        if failed:
            raise RuntimeError(f"Header generation failed: {failed}")
        print(f"Generated {len(list(include_dir.glob('*.h')))} headers in {schema.INCLUDE_DIR}/")
        return {"include_dir": include_dir}


# ---------------------------------------------------------------- vectors --
def _jobs():
    return golden.test_jobs()


@dataclass(kw_only=True)
class VectorsStep(BuildStep):
    """The jobs' memory image and commands, for both simulations."""

    version: str
    description = "Write results/<top>/vectors: the memory image and the commands."
    consumes = ["golden_py", "schema_py"]
    params: ClassVar[dict] = {}

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"vectors": Path("results") / self.version / "vectors"}

    def run(self, config: BuildConfig, **_) -> dict:
        from waveflow.utils.burst_io import write_burst_bundle

        jobs = _jobs()
        d = config.root_dir / "results" / self.version / "vectors"
        shutil.rmtree(d, ignore_errors=True)
        mem, cmds = golden.memory_image(jobs), golden.cmd_words(jobs)
        golden.write_raw(d / "mem_in.bin", mem)              # C simulation
        golden.write_raw(d / "cmds.bin", cmds)
        write_burst_bundle([mem.astype(np.uint64)], d / "mem_in")   # XSI: one burst per command
        write_burst_bundle([c.astype(np.uint64) for c in golden.cmd_bursts(jobs)], d / "s_cmd")
        print(golden.summary(jobs))
        return {"vectors": d}


def verify(version: str, stage: str, mem_out: np.ndarray, resp: np.ndarray,
           root: Path, by_id: bool = False) -> Path:
    """Check every count and every response; write the report; fail the step on a mismatch.
    *by_id*: match responses to jobs by job_id, in any order (the mm host's view)."""
    jobs = _jobs()
    fails = golden.check(jobs, mem_out, resp, by_id=by_id)
    report = root / "results" / version / f"verify_{stage}.json"
    report.write_text(json.dumps({
        "stage": stage, "jobs": len(jobs), "responses": golden.parse_responses(resp),
        "matched": "by job_id" if by_id else "in command order",
        "passed": not fails, "failures": fails}, indent=2) + "\n", encoding="utf-8")
    if fails:
        raise RuntimeError(f"{stage}: " + "; ".join(fails))
    how = "matched by job_id" if by_id else "in order"
    print(f"{stage}: all {len(jobs)} jobs' counts and responses ({how}) match the golden")
    return report


# ------------------------------------------------------------------ Vitis --
def _run_vitis(config: BuildConfig, stage: str, top: str, version: str, live_output: bool,
               **env_extra) -> str:
    env = {"HIST_STAGE": stage, "HIST_TOP": top, "HIST_PROJ": f"proj_{version}", **env_extra}
    try:
        r = toolchain.run_vitis_hls(_SOURCE_DIR / "run.tcl", work_dir=config.root_dir,
                                    capture_output=not live_output, env=env)
    except Exception as exc:
        for s in (getattr(exc, "stdout", None), getattr(exc, "stderr", None)):
            if s:
                print(s if isinstance(s, str) else s.decode(errors="replace"))
        raise RuntimeError(f"Vitis HLS stage '{stage}' failed: {exc}") from exc
    return "".join(s if isinstance(s, str) else s.decode(errors="replace")
                   for s in (r.stdout, r.stderr) if s)


@dataclass(kw_only=True)
class CSimStep(BuildStep):
    version: str
    top: str
    description = "Vitis C simulation: the hls::task kernel, its tasks run as threads."
    params = {"live_output": False}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return ["include_dir", "vectors", "top_cpp", "tb_cpp", "run_tcl"] + SHARED_SOURCES

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"csim_dir": Path("results") / self.version / "csim"}

    def run(self, config: BuildConfig, vectors, live_output, **_) -> dict:
        out = config.root_dir / "results" / self.version / "csim"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        log = _run_vitis(config, "csim", self.top, self.version, live_output,
                         HIST_IN_DIR=Path(vectors).as_posix(), HIST_OUT_DIR=out.as_posix())
        (out / "vitis.log").write_text(log, encoding="utf-8")
        return {"csim_dir": out}


@dataclass(kw_only=True)
class VerifyCSimStep(BuildStep):
    version: str
    description = "Check the C simulation's counts and responses against the NumPy golden."
    consumes = ["csim_dir"]
    params: ClassVar[dict] = {}

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"verify_csim": Path("results") / self.version / "verify_csim.json"}

    def run(self, config: BuildConfig, csim_dir, **_) -> dict:
        d = Path(csim_dir)
        return {"verify_csim": verify(self.version, "csim", golden.read_raw(d / "mem_out.bin"),
                                      golden.read_raw(d / "resp.bin"), config.root_dir)}


def _loops(rdir: Path) -> list[dict]:
    """Every loop's row of the synthesis loop tables."""
    loops, seen = [], set()
    for rpt in sorted(rdir.glob("*_csynth.rpt")):
        for line in rpt.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*\|\s*[-+o]\s+(\S+)\s*\|(.*)\|\s*$", line)
            if not m or m.group(1) in seen:
                continue
            cells = [c.strip() for c in m.group(2).split("|")]
            if len(cells) == 7:
                seen.add(m.group(1))
                loops.append({"loop": m.group(1), "function": rpt.stem.replace("_csynth", ""),
                              "iteration_latency": cells[2], "ii": cells[3],
                              "trip_count": cells[5], "pipelined": cells[6]})
    return loops


@dataclass(kw_only=True)
class SynthStep(BuildStep):
    version: str
    top: str
    after_csim: bool = True
    description = "Vitis C synthesis; results/<top>/synth.json: the loops' II and the resources."
    params = {"live_output": False}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        gate = ["verify_csim"] if self.after_csim else []
        return ["include_dir", "top_cpp", "run_tcl"] + gate + SHARED_SOURCES

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"synth": Path("results") / self.version / "synth.json"}

    def run(self, config: BuildConfig, live_output, **_) -> dict:
        log = _run_vitis(config, "synth", self.top, self.version, live_output)
        out = config.root_dir / "results" / self.version
        (out / "synth.log").write_text(log, encoding="utf-8")
        rdir = config.root_dir / f"proj_{self.version}" / "sol" / "syn" / "report"
        text = (rdir / f"{self.top}_csynth.rpt").read_text(encoding="utf-8", errors="replace")
        tot = re.search(r"^\|Total\s*\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|", text, re.M)
        fmax = re.search(r"Estimated Fmax: ([\d.]+) MHz", log)
        res = {"top": self.top, "loops": _loops(rdir),
               "fmax_mhz": float(fmax.group(1)) if fmax else None,
               "bram": int(tot.group(1)) if tot else None, "dsp": int(tot.group(2)) if tot else None,
               "ff": int(tot.group(3)) if tot else None, "lut": int(tot.group(4)) if tot else None}
        (out / "synth.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
        for lp in res["loops"]:
            if lp["loop"] in ("SAMPLES", "COUNTS", "A2S", "S2A"):
                print(f"  {lp['function']:<40} {lp['loop']:<8} II={lp['ii']}  "
                      f"iteration latency={lp['iteration_latency']}")
        print(f"  FF {res['ff']}, LUT {res['lut']}, BRAM {res['bram']}, DSP {res['dsp']}, "
              f"estimated Fmax {res['fmax_mhz']} MHz")
        return {"synth": out / "synth.json"}


# -------------------------------------------------------------------- XSI --
@dataclass(kw_only=True)
class XsiStep(BuildStep):
    """Drive the synthesized RTL with Waveflow's bus models, through XSI, with a waveform.

    Vitis co-simulation of an ap_ctrl_none design is unreliable, so this is the RTL check:
    an AXI4-Stream master on s_cmd, an AXI4 read slave on m_axi_gmem0 and a write slave on
    m_axi_gmem1 over one shared memory, and an AXI4-Stream slave on s_done.
    """

    version: str
    v: Version
    description = "Run the RTL under XSI (Waveflow's bus models), once per scenario, with waveforms."
    params: ClassVar[dict] = {}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return ["synth", "vectors", "xsi_tb_cpp"] + (["rtl_top_v"] if self.v.mm else [])

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"xsi_dir": Path("results") / self.version / "xsi"}

    def run(self, config: BuildConfig, vectors, **_) -> dict:
        from waveflow.build.trace_steps import render_vcd_dumper
        from waveflow.build.xsi_workspace import XsiWorkspace
        from waveflow.utils.burst_io import write_run_params

        root = config.root_dir
        top = self.v.rtl_top
        ws_dir = root / f"xsi_{self.version}"
        vdir = root / f"proj_{self.version}" / "sol" / "syn" / "verilog"
        tb = f"tb_xsi_{top}"
        rtl = sorted(vdir.glob("*.v"))
        if self.v.mm:                               # the hand-assembled top and the adaptor
            rtl += [_SOURCE_DIR / f for f in self.v.rtl] + adaptor_rtl()
        # The waveform: the top's own nets, and for mm the kernel's inside it too.  XSim honours
        # only the first $dumpvars, so mm dumps two levels from the top in one call: the top's
        # nets and those of each instance in it (the kernel's FIFO strobes among them).
        dumper = render_vcd_dumper(top)
        if self.v.mm:
            dumper = dumper.replace(f"$dumpvars(1, {top});", f"$dumpvars(2, {top});")
        ws = XsiWorkspace(ws_dir, top=top)
        ws.prepare(rtl_files=rtl, tb_name=tb,
                   tb_cpp=(root / f"{tb}.cpp").read_text(encoding="utf-8"),
                   init_files=sorted(vdir.glob("*.dat")), trace=True,
                   extra_files={f"vcd_dumper_{top}.v": dumper})
        out = root / "results" / self.version / "xsi"
        shutil.rmtree(out, ignore_errors=True)
        jobs = _jobs()
        vcd = ws_dir / f"{top}_trace.vcd"
        outputs = ("mem_out", "resp", "cmd_sent") if self.v.mm else ("mem_out", "s_done")
        for scenario, gap in SCENARIOS.items():
            vec = ws_dir / scenario                 # the run's vectors/ (WF_VECTORS_DIR)
            shutil.rmtree(vec, ignore_errors=True)
            for name in ("mem_in", "s_cmd"):
                shutil.copytree(Path(vectors) / name, vec / name)
            write_run_params(vec, mem_words=golden.MEM_WORDS, cmd_gap=gap, n_cycles=40000,
                             resp_words=len(jobs) * golden.resp_nwords(), njobs=len(jobs))
            vcd.unlink(missing_ok=True)             # never measure a previous run's waveform
            log = ws.run(vectors_dir=vec)           # builds the RTL and testbench once
            line = re.search(r"HIST_XSI: .*", log)
            print(f"{scenario}: " + (line.group(0) if line else log[-2000:]))
            if not vcd.exists():
                raise RuntimeError(f"XSI ran but wrote no {vcd.name}")
            d = out / scenario
            d.mkdir(parents=True)
            for name in outputs:
                if not (vec / name).exists():
                    raise RuntimeError(f"XSI wrote no vectors/{name}:\n{log[-3000:]}")
                shutil.copytree(vec / name, d / name)
            shutil.copyfile(vcd, d / vcd.name)
            (d / "xsi.log").write_text(log, encoding="utf-8")
        return {"xsi_dir": out}


#: The XSI runs: name -> idle cycles between commands.  back_to_back queues every command at
#: once, so the jobs overlap; isolated leaves each job alone in the kernel, so its phases are
#: measured from an idle start.
SCENARIOS = {"back_to_back": 0, "isolated": 1500}


@dataclass(kw_only=True)
class VerifyXsiStep(BuildStep):
    version: str
    v: Version
    description = "Check the RTL's counts and responses, in every scenario, against the golden."
    consumes = ["xsi_dir"]
    params: ClassVar[dict] = {}

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"verify_xsi": Path("results") / self.version / "verify_xsi_isolated.json"}

    def run(self, config: BuildConfig, xsi_dir, **_) -> dict:
        from waveflow.utils.burst_io import read_burst_bundle

        reports = {}
        for scenario in SCENARIOS:
            d = Path(xsi_dir) / scenario
            mem = np.concatenate(read_burst_bundle(d / "mem_out")).astype(np.uint32)
            resp_dir = d / ("resp" if self.v.mm else "s_done")
            resp = np.concatenate(read_burst_bundle(resp_dir)).astype(np.uint32)
            reports[scenario] = verify(self.version, f"xsi_{scenario}", mem, resp,
                                       config.root_dir, by_id=self.v.mm)
        return {"verify_xsi": reports["isolated"]}


@dataclass(kw_only=True)
class TimingStep(BuildStep):
    version: str
    v: Version
    description = "Measure each job's phases from the waveforms: timing_*.md/.json, timeline.png."
    consumes = ["verify_xsi", "xsi_dir"]
    params: ClassVar[dict] = {}

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"timing": Path("results") / self.version / "timing_isolated.json"}

    def run(self, config: BuildConfig, xsi_dir, **_) -> dict:
        import hist_timing

        out = config.root_dir / "results" / self.version
        jobs = _jobs()
        title = (f"{self.v.rtl_top}: the kernel's phases inside the slave adaptor (XSI)"
                 if self.v.mm else None)
        for scenario in SCENARIOS:
            d = Path(xsi_dir) / scenario
            res = hist_timing.measure(
                d / f"{self.v.rtl_top}_trace.vcd", self.v.scope, jobs,
                golden.NBINS, len(golden.cmd_bursts(jobs)[0]), golden.resp_nwords(), out,
                name=scenario, figure=(scenario == "back_to_back"), title=title)
            print(f"{scenario}:")
            print(res["table"])
            if self.v.mm:
                print(host_timing(d, res["rows"], out, scenario))
        print(f"Timeline: {(out / 'timeline.png').relative_to(config.root_dir).as_posix()}")
        return {"timing": out / "timing_isolated.json"}


def host_timing(d: Path, rows: list[dict], out: Path, scenario: str) -> str:
    """The mm version, seen from the host: per job, when its command packet's bus write started
    and finished, when the kernel took the command and pushed the response (from the kernel's
    rows), and when the host's read of that response finished -- matched by job_id."""
    from waveflow.utils.burst_io import read_burst_bundle

    log = (d / "xsi.log").read_text(encoding="utf-8")
    ops = [(m.group(1), int(m.group(2), 16), int(m.group(3)), int(m.group(4)), int(m.group(5)))
           for m in re.finditer(r"^OP ([RW]) 0x([0-9a-f]+) n=(\d+) s=(-?\d+) e=(-?\d+)", log, re.M)]
    cmd_writes = [o for o in ops if o[0] == "W" and o[1] == 0x0000]      # [len | 5 words]
    resp_reads = [o for o in ops if o[0] == "R" and o[1] == 0x1000]      # one HistResp
    words = np.concatenate(read_burst_bundle(d / "resp")).astype(np.uint32)
    resps = golden.parse_responses(words)
    read_end = {job_id: resp_reads[k][4] for k, (job_id, _) in enumerate(resps)}
    table = ["| job | host write starts | host write ends | kernel takes cmd (last word) | "
             "kernel sends resp (last word) | host read ends | host write start -> read end |",
             "|---|---|---|---|---|---|---|"]
    host = []
    for k, r in enumerate(rows):
        ws, we = cmd_writes[k][3], cmd_writes[k][4]
        re_ = read_end.get(r["job_id"])
        host.append({"job_id": r["job_id"], "write_start": ws, "write_end": we,
                     "kernel_cmd_last": r["cmd_last"], "kernel_resp_last": r["resp_last"],
                     "read_end": re_})
        table.append(f"| {r['job_id']} | {ws} | {we} | {r['cmd_last']} | {r['resp_last']} | "
                     f"{re_} | {re_ - ws if re_ is not None else '-'} |")
    others = [o for o in ops if not (o in cmd_writes or o in resp_reads)]
    text = (f"Host view ({scenario}), absolute cycles:\n\n" + "\n".join(table) +
            f"\n\nOther bus operations (interrupt thresholds): " +
            ", ".join(f"{o[0]} 0x{o[1]:x} at {o[3]}" for o in others))
    (out / f"timing_host_{scenario}.md").write_text(text + "\n", encoding="utf-8")
    (out / f"timing_host_{scenario}.json").write_text(json.dumps(host, indent=2) + "\n",
                                                      encoding="utf-8")
    return text


# -------------------------------------------------------------------- DAG --
def build_dag(args) -> BuildDag:
    version = args.top
    v = VERSIONS[version]
    kernel = v.kernel
    dag = BuildDag()
    sources = [("schema_py", "hist_schema.py"), ("golden_py", "hist_golden.py"),
               ("top_cpp", f"{kernel}.cpp"), ("xsi_tb_cpp", f"tb_xsi_{v.rtl_top}.cpp"),
               ("run_tcl", "run.tcl")]
    if v.csim:
        sources.append(("tb_cpp", f"tb_{kernel}.cpp"))
    if v.mm:
        sources.append(("rtl_top_v", f"{v.rtl_top}.v"))
    for artifact, path in sources:
        dag.add(SourceStep(artifact=artifact, path=_SOURCE_DIR / path))
    for path in SHARED_SOURCES:
        dag.add(SourceStep(artifact=path, path=_SOURCE_DIR / path))
    dag.add(GenIncludeStep(name="gen_include"))
    dag.add(VectorsStep(name="vectors", version=version))
    if v.csim:
        dag.add(CSimStep(name="csim", version=version, top=kernel))
        dag.add(VerifyCSimStep(name="verify_csim", version=version))
    dag.add(SynthStep(name="synth", version=version, top=kernel, after_csim=v.csim))
    dag.add(XsiStep(name="xsi", version=version, v=v))
    dag.add(VerifyXsiStep(name="verify_xsi", version=version, v=v))
    dag.add(TimingStep(name="timing", version=version, v=v))
    return dag


def main() -> None:
    run_dag_cli(
        build_dag,
        description="The histogram demo: a free-running kernel on Waveflow's memory adaptors.",
        default_through="timing",
        root_dir=_SOURCE_DIR,
        extra_args=[(("--top",), {"default": "stream", "choices": list(VERSIONS),
                                  "help": "Which version: stream or mm."}),
                    (("--live-output",), {"action": "store_true",
                                          "help": "Stream Vitis output instead of capturing it."})],
        params_from_args=lambda a: {"live_output": a.live_output},
    )


if __name__ == "__main__":
    main()
