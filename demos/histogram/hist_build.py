"""Build script for the histogram demo: free-running kernels that reach memory through
Waveflow's data movers.

Three designs share the messages (``hist_schema.py``), the test jobs and their golden
(``hist_golden.py``) and the timing analysis (``hist_timing.py``); each has a directory of its
own:

    --design simple    simple/hist_simple.cpp (unit 9): one compute task and the two plain
                       movers.  One job at a time: load, bin, store, wait for the write's
                       completion, respond.  Command and response on AXI4-Streams.
    --design mmqueue   mmqueue/hist_mmqueue.v (unit 9): the hist_simple kernel behind Waveflow's
                       memory-mapped slave adaptor -- a host writes commands into a queue and
                       reads responses out of one.
    --design pipeline  pipeline/hist_pipeline.cpp (unit 10, reference): five tasks on the framed
                       movers, one descriptor per job, so consecutive jobs overlap.

Each design builds into its own directories -- ``proj_<design>/``, ``csim_proj_<design>/``,
``xsi_<design>/`` and ``results/<design>/`` -- so building one never touches another's output.
``include/`` is shared: every design's generated headers, side by side.  The steps:

    simple, pipeline: gen_include -> vectors -> csim -> verify_csim -> synth -> xsi
                      -> verify_xsi -> timing
    mmqueue:          gen_include -> vectors -> synth -> xsi -> verify_xsi -> timing

mmqueue synthesizes the hist_simple kernel and has no C simulation of its own; its XSI top is
the hand-assembled ``hist_mmqueue.v`` plus Waveflow's adaptor RTL, driven by a host model
(``tb_xsi_hist_mmqueue.cpp``) on its AXI slave port.

``gen_include`` writes ``include/``: HistCmd / HistDesc / HistResp from ``hist_schema.py``;
the plain movers' MRCmd / MWCmd / MemComplete and the framed movers' MemRCmd / MemWCmd from
Waveflow's schemas; and Waveflow's mover bodies verbatim, the way its own generator copies
them.  ``csim`` runs Vitis C simulation; ``synth`` runs C synthesis; ``xsi`` drives the
synthesized RTL with Waveflow's AXI bus models and dumps a waveform; ``timing`` measures each
job's phases from it.  Every count and every response is checked against the NumPy golden
after both simulations.

    python hist_build.py                               # hist_simple, everything: ~2 minutes
    python hist_build.py --through verify_csim         # C simulation only: ~30 s
    python hist_build.py --design mmqueue              # synthesis, XSI, timing
    python hist_build.py --design pipeline

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
class Design:
    """What --design selects.

    src         the design's directory: its XSI testbench, and its RTL top if it has one.
    kernel      the HLS top that is synthesized, and the stem of its source.
    kernel_dir  where that source and its C simulation testbench are.  mmqueue's kernel is
                hist_simple's, from simple/.
    rtl_top     the Verilog top the XSI testbench drives.
    scope       where the kernel's own signals are in the waveform.
    csim        whether the design has a C simulation of its own (mmqueue's kernel is simple's).
    probes      which kernel the timing analysis reads: "simple" or "pipeline".
    rtl         extra Verilog: the hand-assembled top, from src/.
    """
    src: str
    kernel: str
    kernel_dir: str
    rtl_top: str
    scope: str
    csim: bool
    probes: str
    rtl: tuple[str, ...] = ()

    @property
    def mm(self) -> bool:
        return self.rtl_top != self.kernel


#: Waveflow's slave adaptor RTL, used as it is (waveflow/build/rtl).
ADAPTOR_RTL = ("axi_slave_front.v", "mm_queue_in.v", "mm_queue_out.v", "mm_sync_fifo.v")

DESIGNS = {
    "simple":   Design(src="simple", kernel="hist_simple", kernel_dir="simple",
                       rtl_top="hist_simple", scope="hist_simple", csim=True, probes="simple"),
    "mmqueue":  Design(src="mmqueue", kernel="hist_simple", kernel_dir="simple",
                       rtl_top="hist_mmqueue", scope="hist_mmqueue.u_kernel", csim=False,
                       probes="simple", rtl=("hist_mmqueue.v",)),
    "pipeline": Design(src="pipeline", kernel="hist_pipeline", kernel_dir="pipeline",
                       rtl_top="hist_pipeline", scope="hist_pipeline", csim=True,
                       probes="pipeline"),
}


def adaptor_rtl() -> list[Path]:
    import waveflow
    d = Path(waveflow.__file__).resolve().parent / "build" / "rtl"
    return [d / f for f in ADAPTOR_RTL]


# ---------------------------------------------------------------- headers --
@dataclass(kw_only=True)
class GenIncludeStep(BuildStep):
    """Generate include/: the kernels' message headers and Waveflow's mover headers."""

    description = ("Generate include/: HistCmd/HistDesc/HistResp, MRCmd/MWCmd/MemComplete, "
                   "MemRCmd/MemWCmd, Waveflow's movers.")
    consumes = ["schema_py"]
    produces = {"include_dir": Path(schema.INCLUDE_DIR)}
    params: ClassVar[dict] = {}

    def run(self, config: BuildConfig, **_) -> dict:
        from waveflow.build.streamutils import MemStreamStep, StreamUtilsStep
        from waveflow.hw.dataschema import DataSchemaStep
        from waveflow.hw.mem_stream import MemRCmd, MemWCmd
        from waveflow.hw.mem_stream import SCHEMA_CLASSES as PLAIN_MOVER_SCHEMAS
        from waveflow.hw.mem_stream import WORD_BW_SUPPORTED as MEM_WORD_BW

        include_dir = config.root_dir / schema.INCLUDE_DIR
        shutil.rmtree(include_dir, ignore_errors=True)   # no stale header survives a rename
        inner = BuildDag()
        inner.add(StreamUtilsStep(output_dir=schema.INCLUDE_DIR))
        inner.add(MemStreamStep(output_dir=schema.INCLUDE_DIR))      # the mover task bodies
        # hist_simple: the plain movers' MRCmd, MWCmd and MemComplete.
        for cls in PLAIN_MOVER_SCHEMAS:
            inner.add(DataSchemaStep(cls, word_bw_supported=MEM_WORD_BW,
                                     include_dir=schema.INCLUDE_DIR))
        # hist_pipeline: the framed movers' commands.  framed=True adds read_framed_stream /
        # write_framed_stream: a message on an internal stream with a `last` bit on its final word.
        for cls in (MemRCmd, MemWCmd):
            inner.add(DataSchemaStep(cls, word_bw_supported=MEM_WORD_BW,
                                     include_dir=schema.INCLUDE_DIR, framed=True))
        for cls in schema.SCHEMA_CLASSES:                            # HistCmd, HistDesc, HistResp
            inner.add(DataSchemaStep(cls, word_bw_supported=schema.WORD_BW_SUPPORTED,
                                     include_dir=schema.INCLUDE_DIR, framed=True))
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

    design: str
    description = "Write results/<design>/vectors: the memory image and the commands."
    consumes = ["golden_py", "schema_py"]
    params: ClassVar[dict] = {}

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"vectors": Path("results") / self.design / "vectors"}

    def run(self, config: BuildConfig, **_) -> dict:
        from waveflow.utils.burst_io import write_burst_bundle

        jobs = _jobs()
        d = config.root_dir / "results" / self.design / "vectors"
        shutil.rmtree(d, ignore_errors=True)
        mem, cmds = golden.memory_image(jobs), golden.cmd_words(jobs)
        golden.write_raw(d / "mem_in.bin", mem)              # C simulation
        golden.write_raw(d / "cmds.bin", cmds)
        write_burst_bundle([mem.astype(np.uint64)], d / "mem_in")   # XSI: one burst per command
        write_burst_bundle([c.astype(np.uint64) for c in golden.cmd_bursts(jobs)], d / "s_cmd")
        print(golden.summary(jobs))
        return {"vectors": d}


def verify(design: str, stage: str, mem_out: np.ndarray, resp: np.ndarray,
           root: Path, by_id: bool = False) -> Path:
    """Check every count and every response; write the report; fail the step on a mismatch.
    *by_id*: match responses to jobs by job_id, in any order (the mm host's view)."""
    jobs = _jobs()
    fails = golden.check(jobs, mem_out, resp, by_id=by_id)
    report = root / "results" / design / f"verify_{stage}.json"
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
def _run_vitis(config: BuildConfig, stage: str, d: Design, design: str, live_output: bool,
               **env_extra) -> str:
    env = {"HIST_STAGE": stage, "HIST_TOP": d.kernel, "HIST_SRC_DIR": d.kernel_dir,
           "HIST_PROJ": f"proj_{design}", **env_extra}
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
    design: str
    d: Design
    description = "Vitis C simulation: the hls::task kernel, its tasks run as threads."
    params = {"live_output": False}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return ["include_dir", "vectors", "tb_cpp", "run_tcl", "kernel_src"]

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"csim_dir": Path("results") / self.design / "csim"}

    def run(self, config: BuildConfig, vectors, live_output, **_) -> dict:
        out = config.root_dir / "results" / self.design / "csim"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        log = _run_vitis(config, "csim", self.d, self.design, live_output,
                         HIST_IN_DIR=Path(vectors).as_posix(), HIST_OUT_DIR=out.as_posix())
        (out / "vitis.log").write_text(log, encoding="utf-8")
        return {"csim_dir": out}


@dataclass(kw_only=True)
class VerifyCSimStep(BuildStep):
    design: str
    description = "Check the C simulation's counts and responses against the NumPy golden."
    consumes = ["csim_dir"]
    params: ClassVar[dict] = {}

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"verify_csim": Path("results") / self.design / "verify_csim.json"}

    def run(self, config: BuildConfig, csim_dir, **_) -> dict:
        d = Path(csim_dir)
        return {"verify_csim": verify(self.design, "csim", golden.read_raw(d / "mem_out.bin"),
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
    design: str
    d: Design
    description = "Vitis C synthesis; results/<design>/synth.json: the loops' II and the resources."
    params = {"live_output": False}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        gate = ["verify_csim"] if self.d.csim else []
        return ["include_dir", "run_tcl", "kernel_src"] + gate

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"synth": Path("results") / self.design / "synth.json"}

    def run(self, config: BuildConfig, live_output, **_) -> dict:
        top = self.d.kernel
        log = _run_vitis(config, "synth", self.d, self.design, live_output)
        out = config.root_dir / "results" / self.design
        out.mkdir(parents=True, exist_ok=True)
        (out / "synth.log").write_text(log, encoding="utf-8")
        rdir = config.root_dir / f"proj_{self.design}" / "sol" / "syn" / "report"
        text = (rdir / f"{top}_csynth.rpt").read_text(encoding="utf-8", errors="replace")
        tot = re.search(r"^\|Total\s*\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|", text, re.M)
        fmax = re.search(r"Estimated Fmax: ([\d.]+) MHz", log)
        res = {"top": top, "loops": _loops(rdir),
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
    an AXI4-Stream master on s_cmd (or, for mmqueue, a host on the AXI slave port), an AXI4 read
    slave on m_axi_gmem0 and a write slave on m_axi_gmem1 over one shared memory, and an
    AXI4-Stream slave on s_done.
    """

    design: str
    d: Design
    description = "Run the RTL under XSI (Waveflow's bus models), once per scenario, with waveforms."
    params: ClassVar[dict] = {}

    @property
    def consumes(self) -> list:  # type: ignore[override]
        return ["synth", "vectors", "xsi_tb_cpp"] + (["rtl_top_v"] if self.d.mm else [])

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"xsi_dir": Path("results") / self.design / "xsi"}

    def run(self, config: BuildConfig, vectors, **_) -> dict:
        from waveflow.build.trace_steps import render_vcd_dumper
        from waveflow.build.xsi_workspace import XsiWorkspace
        from waveflow.utils.burst_io import write_run_params

        root = config.root_dir
        top = self.d.rtl_top
        ws_dir = root / f"xsi_{self.design}"
        vdir = root / f"proj_{self.design}" / "sol" / "syn" / "verilog"
        tb = f"tb_xsi_{top}"
        rtl = sorted(vdir.glob("*.v"))
        if self.d.mm:                               # the hand-assembled top and the adaptor
            rtl += [_SOURCE_DIR / self.d.src / f for f in self.d.rtl] + adaptor_rtl()
        # The waveform: the top's own nets, and for mm the kernel's inside it too.  Of two nested
        # scopes XSim dumps only the outer one (render_vcd_dumper refuses them), so mm dumps two
        # levels from the top in one call: the top's nets and those of each instance in it (the
        # kernel's FIFO strobes among them).
        dumper = render_vcd_dumper(top)
        if self.d.mm:
            dumper = dumper.replace(f"$dumpvars(1, {top});", f"$dumpvars(2, {top});")
        ws = XsiWorkspace(ws_dir, top=top)
        ws.prepare(rtl_files=rtl, tb_name=tb,
                   tb_cpp=(_SOURCE_DIR / self.d.src / f"{tb}.cpp").read_text(encoding="utf-8"),
                   init_files=sorted(vdir.glob("*.dat")), trace=True,
                   extra_files={f"vcd_dumper_{top}.v": dumper})
        out = root / "results" / self.design / "xsi"
        shutil.rmtree(out, ignore_errors=True)
        jobs = _jobs()
        vcd = ws_dir / f"{top}_trace.vcd"
        outputs = ("mem_out", "resp", "cmd_sent") if self.d.mm else ("mem_out", "s_done")
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
#: once; isolated leaves each job alone in the kernel, so its phases are measured from an idle
#: start.  For hist_simple the two should take the same time per job: it never overlaps jobs.
SCENARIOS = {"back_to_back": 0, "isolated": 1500}


@dataclass(kw_only=True)
class VerifyXsiStep(BuildStep):
    design: str
    d: Design
    description = "Check the RTL's counts and responses, in every scenario, against the golden."
    consumes = ["xsi_dir"]
    params: ClassVar[dict] = {}

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"verify_xsi": Path("results") / self.design / "verify_xsi_isolated.json"}

    def run(self, config: BuildConfig, xsi_dir, **_) -> dict:
        from waveflow.utils.burst_io import read_burst_bundle

        reports = {}
        for scenario in SCENARIOS:
            d = Path(xsi_dir) / scenario
            mem = np.concatenate(read_burst_bundle(d / "mem_out")).astype(np.uint32)
            resp_dir = d / ("resp" if self.d.mm else "s_done")
            resp = np.concatenate(read_burst_bundle(resp_dir)).astype(np.uint32)
            reports[scenario] = verify(self.design, f"xsi_{scenario}", mem, resp,
                                       config.root_dir, by_id=self.d.mm)
        return {"verify_xsi": reports["isolated"]}


@dataclass(kw_only=True)
class TimingStep(BuildStep):
    design: str
    d: Design
    description = "Measure each job's phases from the waveforms: timing_*.md/.json, timeline.png."
    consumes = ["verify_xsi", "xsi_dir", "timing_py"]
    params: ClassVar[dict] = {}

    @property
    def produces(self) -> dict:  # type: ignore[override]
        return {"timing": Path("results") / self.design / "timing_isolated.json"}

    def run(self, config: BuildConfig, xsi_dir, **_) -> dict:
        import hist_timing

        out = config.root_dir / "results" / self.design
        jobs = _jobs()
        title = (f"{self.d.rtl_top}: the kernel's phases inside the slave adaptor (XSI)"
                 if self.d.mm else None)
        hdr = {"hdr_in": desc_nwords(), "hdr_out": memw_nwords() + desc_nwords()} \
            if self.d.probes == "pipeline" else {}
        rows = {}
        for scenario in SCENARIOS:
            d = Path(xsi_dir) / scenario
            res = hist_timing.measure(
                d / f"{self.d.rtl_top}_trace.vcd", self.d.scope, jobs,
                golden.NBINS, len(golden.cmd_bursts(jobs)[0]), golden.resp_nwords(), out,
                name=scenario, figure=(scenario == "back_to_back"), title=title,
                probes=self.d.probes, **hdr)
            rows[scenario] = res["rows"]
            print(f"{scenario}:")
            print(res["table"])
            if self.d.mm:
                print(host_timing(d, res["rows"], out, scenario))
        print(hist_timing.totals(rows, out))
        print(f"Timeline: {(out / 'timeline.png').relative_to(config.root_dir).as_posix()}")
        return {"timing": out / "timing_isolated.json"}


def desc_nwords() -> int:
    """Words in one HistDesc on hist_pipeline's streams: from the schema, never a literal."""
    d = schema.HistDesc(job_id=0, status=schema.HistStatus.OK, n=0, shift=0, cnt_addr=0)
    return len(d.serialize(word_bw=schema.MEM_DW))


def memw_nwords() -> int:
    """Words in one MemWCmd, hist_pipeline's write mover header."""
    from waveflow.hw.mem_stream import MemWCmd
    return len(MemWCmd(addr=0, len=0, fwd_bursts=0).serialize(word_bw=schema.MEM_DW))


def host_timing(d: Path, rows: list[dict], out: Path, scenario: str) -> str:
    """The mm design, seen from the host: per job, when its command packet's bus write started
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
    design = args.design
    d = DESIGNS[design]
    dag = BuildDag()
    sources = [("schema_py", "hist_schema.py"), ("golden_py", "hist_golden.py"),
               ("timing_py", "hist_timing.py"), ("run_tcl", "run.tcl"),
               ("xsi_tb_cpp", f"{d.src}/tb_xsi_{d.rtl_top}.cpp")]
    if d.csim:
        sources.append(("tb_cpp", f"{d.kernel_dir}/tb_{d.kernel}.cpp"))
    if d.mm:
        sources.append(("rtl_top_v", f"{d.src}/{d.rtl_top}.v"))
    for artifact, path in sources:
        dag.add(SourceStep(artifact=artifact, path=_SOURCE_DIR / path))
    # The kernel's directory, whole: its top, its headers (and its testbenches).
    dag.add(SourceStep(artifact="kernel_src", path=_SOURCE_DIR / d.kernel_dir))
    dag.add(GenIncludeStep(name="gen_include"))
    dag.add(VectorsStep(name="vectors", design=design))
    if d.csim:
        dag.add(CSimStep(name="csim", design=design, d=d))
        dag.add(VerifyCSimStep(name="verify_csim", design=design))
    dag.add(SynthStep(name="synth", design=design, d=d))
    dag.add(XsiStep(name="xsi", design=design, d=d))
    dag.add(VerifyXsiStep(name="verify_xsi", design=design, d=d))
    dag.add(TimingStep(name="timing", design=design, d=d))
    return dag


def main() -> None:
    run_dag_cli(
        build_dag,
        description="The histogram demo: free-running kernels on Waveflow's data movers.",
        default_through="timing",
        root_dir=_SOURCE_DIR,
        extra_args=[(("--design",), {"default": "simple", "choices": list(DESIGNS),
                                     "help": "Which design: simple (unit 9), mmqueue (unit 9, "
                                             "simple behind memory-mapped queues) or pipeline "
                                             "(unit 10)."}),
                    (("--live-output",), {"action": "store_true",
                                          "help": "Stream Vitis output instead of capturing it."})],
        params_from_args=lambda a: {"live_output": a.live_output},
    )


if __name__ == "__main__":
    main()
