"""Read the variants' synthesis reports and schedules, and plot them; and
draw the co-simulation timing diagrams.

Each variant is ``poly.cpp`` built with one set of loop optimizations, into
its own Vitis project, ``proj_<name>`` (see ``run.tcl``).  Its reports say
what Vitis HLS made of it:

* **the loop**: its trip count, its **initiation interval** (II, cycles
  between one iteration starting and the next) and its **iteration
  latency** (cycles from an iteration's first operation to its last; for a
  pipelined loop this is the pipeline's **depth**);
* **the call**: cycles from ap_start to ap_done, for the largest call,
  MAX_NSAMP = 1024 samples;
* **resources**: DSP blocks, flip-flops, LUTs and block RAMs.

The schedule -- which operation runs in which cycle of one iteration -- is
in a report Vitis writes for each pipelined loop,
``.autopilot/db/<module>.verbose.sched.rpt``.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

TOP = "poly"
SOLUTION = "sol"
LOOP = "sample_loop"
#: The arrays' size in poly.h: the call the report's worst-case latency is for.
MAX_NSAMP = 1024

# The deck's palette, as in the quad demo.
_VIOLET, _TEAL, _AMBER, _INK, _MUTED = "#57068C", "#00857C", "#B4530F", "#262626", "#6E6E6E"
_ROSE, _BLUE = "#B8336A", "#2C6E9B"


@dataclass(frozen=True)
class Variant:
    """One build of poly.cpp: which loop optimizations its pragmas turn on."""

    name: str
    pipeline: bool
    unroll: int = 1
    partition: bool = False

    @property
    def spec(self) -> str:
        """The form run.tcl reads: name:pipeline:unroll:partition."""
        return f"{self.name}:{int(self.pipeline)}:{self.unroll}:{int(self.partition)}"

    @property
    def project(self) -> str:
        return f"proj_{self.name}"

    def describe(self) -> str:
        if not self.pipeline:
            return "not pipelined"
        if self.unroll == 1:
            return "pipelined, II = 1"
        return (f"unrolled by {self.unroll}, "
                + ("arrays partitioned" if self.partition else "arrays not partitioned"))


def unroll_variant(factor: int, partition: bool = True) -> Variant:
    """The pipelined loop unrolled by ``factor``: u4, or u4_nopart."""
    return Variant(f"u{factor}" + ("" if partition else "_nopart"), True, factor, partition)


def report_dir(root: Path, v: Variant) -> Path:
    """Where Vitis writes one variant's synthesis reports."""
    return root / v.project / SOLUTION / "syn" / "report"


def _loop_node(rdir: Path):
    """The sample loop's entry in whichever module's report holds it.

    A pipelined loop is synthesized as a module of its own,
    ``poly_Pipeline_sample_loop``, and its entry is in that module's report;
    an unpipelined one stays inside ``poly``.  So search them all.
    """
    for xml in sorted(rdir.glob("*_csynth.xml")):
        node = ET.parse(xml).getroot().find(f"PerformanceEstimates/SummaryOfLoopLatency/{LOOP}")
        if node is not None:
            return node
    return None


def _int(text) -> int | None:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def read_variant(root: Path, v: Variant) -> dict:
    """Everything the demo uses from one variant's reports."""
    from waveflow.utils.csynthparse import CsynthParser, module_latency, synth_target

    rdir = report_dir(root, v)
    clock = synth_target(rdir)
    call = module_latency(rdir, TOP)
    loop = _loop_node(rdir)
    if clock is None or call is None or loop is None:
        raise RuntimeError(f"No complete synthesis report in {rdir}: run the synth step first.")
    parser = CsynthParser(report_path=str(rdir))
    parser.get_total_resources()
    res, avail = parser.total_resources, parser.available_resources

    pipelined = loop.findtext("PipelineII") is not None
    # A pipelined loop reports its II and depth; one that is not reports the
    # latency of an iteration, and the next starts only when it is done.
    ii = _int(loop.findtext("PipelineII")) if pipelined else _int(loop.findtext("IterationLatency"))
    depth = _int(loop.findtext("PipelineDepth")) if pipelined else _int(loop.findtext("IterationLatency"))
    trips = _int(loop.findtext("TripCount/range/max")) or _int(loop.findtext("TripCount"))
    target, est = clock["target_period_ns"], clock["estimated_period_ns"]
    samples_per_cycle = v.unroll / ii if ii else None
    call_cycles = call["latency_max"]
    return {
        "variant": v.name,
        "description": v.describe(),
        "pipeline": v.pipeline,
        "unroll": v.unroll,
        "partition": v.partition,
        "target_ns": target,
        "estimated_ns": est,
        "fclk_mhz": round(1000.0 / target, 1),
        "loop_pipelined": pipelined,
        "trip_count": trips,
        "ii": ii,
        "iteration_latency": depth,
        "call_cycles": call_cycles,
        "call_us": round(call_cycles * target / 1000.0, 2),
        # Samples per clock cycle once the loop is running: each iteration
        # handles `unroll` samples, and one starts every II cycles.
        "samples_per_cycle": None if samples_per_cycle is None else round(samples_per_cycle, 3),
        "throughput_msps": None if samples_per_cycle is None
                           else round(samples_per_cycle * 1000.0 / target, 1),
        "dsp": res.get("DSP"), "ff": res.get("FF"), "lut": res.get("LUT"),
        "bram": res.get("BRAM_18K"),
        "dsp_avail": avail.get("DSP"), "ff_avail": avail.get("FF"),
        "lut_avail": avail.get("LUT"), "bram_avail": avail.get("BRAM_18K"),
    }


# -------------------------------------------------------------------- tables --
def write_pipe_table(rows: list[dict], path: Path) -> Path:
    """Pipelined against not, as a Markdown table."""
    head = ("| Variant | II | Iteration latency | Trip count | Cycles, 1024 samples | Time "
            "| DSP | FF | LUT |\n|---|---|---|---|---|---|---|---|---|\n")
    lines = [f"| {r['description']} | {r['ii']} | {r['iteration_latency']} cycles "
             f"| {r['trip_count']} | {r['call_cycles']} | {r['call_us']:g} us "
             f"| {r['dsp']} | {r['ff']} | {r['lut']} |" for r in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_unroll_table(rows: list[dict], path: Path) -> Path:
    """The unrolled variants, with the pipelined loop as unroll factor 1."""
    head = ("| Unroll | Partitioned | II | Trip count | Samples / cycle | Cycles, 1024 samples "
            "| DSP | FF | LUT |\n|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for r in rows:
        part = "-" if r["unroll"] == 1 else ("yes" if r["partition"] else "no")
        lines.append(f"| {r['unroll']} | {part} | {r['ii']} | {r['trip_count']} "
                     f"| {r['samples_per_cycle']:g} | {r['call_cycles']} "
                     f"| {r['dsp']} ({100 * r['dsp'] / r['dsp_avail']:.0f}%) "
                     f"| {r['ff']} | {r['lut']} ({100 * r['lut'] / r['lut_avail']:.0f}%) |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------- plots --
def _save(fig, png_path: Path) -> Path:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    # No timestamp metadata, so an unchanged run gives an identical file.
    fig.savefig(png_path, dpi=200, bbox_inches="tight", pad_inches=0.06,
                metadata={"Software": None, "Date": None})
    return png_path


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(alpha=0.25, lw=0.5)


def write_unroll_plot(rows: list[dict], png_path: Path) -> Path:
    """Throughput and resources against the unroll factor."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    base = [r for r in rows if r["unroll"] == 1]
    part = base + [r for r in rows if r["unroll"] > 1 and r["partition"]]
    nopart = base + [r for r in rows if r["unroll"] > 1 and not r["partition"]]
    part.sort(key=lambda r: r["unroll"])
    nopart.sort(key=lambda r: r["unroll"])
    factors = [r["unroll"] for r in part]

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    ax = axes[0]
    ax.plot(factors, factors, "--", color=_MUTED, lw=1, label="ideal: one sample per copy")
    ax.plot(factors, [r["samples_per_cycle"] for r in part], "o-", color=_TEAL, lw=2,
            label="arrays partitioned")
    if len(nopart) > 1:
        ax.plot([r["unroll"] for r in nopart], [r["samples_per_cycle"] for r in nopart], "s-",
                color=_AMBER, lw=2, label="one single-port memory each")
    ax.set_ylabel("samples per clock cycle")
    ax.set_title("Unrolling pays only if memory keeps up", loc="left", fontsize=11, color=_INK)
    ax.legend(frameon=False, fontsize=9)

    ax = axes[1]
    for key, label, color, marker in (("dsp", "DSP", _VIOLET, "o"), ("lut", "LUT", _TEAL, "s"),
                                      ("ff", "FF", _AMBER, "^")):
        ax.plot(factors, [100.0 * r[key] / r[f"{key}_avail"] for r in part], marker + "-",
                color=color, lw=2, label=label)
    ax.set_ylabel("% of the xc7z020")
    ax.set_title("and the hardware grows with it", loc="left", fontsize=11, color=_INK)
    ax.legend(frameon=False, fontsize=9)

    for ax in axes:
        ax.set_xscale("log", base=2)
        ax.set_xticks(factors)
        ax.set_xticklabels([str(f) for f in factors])
        ax.set_xlabel("unroll factor")
        ax.set_ylim(bottom=0)
        _style(ax)
    fig.tight_layout(w_pad=2.5)
    _save(fig, png_path)
    plt.close(fig)
    return png_path


# ------------------------------------------------------------------ schedule --
_OP_LINE = re.compile(
    r'^ST_(?P<state>\d+) : Operation \d+ \[(?P<k>\d+)/(?P<n>\d+)\].*?'
    r'"%(?P<name>[\w.]+) = (?P<op>\w+) [^"]*"(?: \[(?P<src>[^\]]+)\])?')
_CORE = re.compile(r'<CoreInst = "(?P<core>[^"]+)">')
_PIPE = re.compile(r"Pipeline-0 : II = (?P<ii>\d+), D = (?P<d>\d+)")


def sched_report(root: Path, v: Variant) -> Path:
    """The schedule of the variant's sample loop.  Only a pipelined loop has
    one of its own; an unpipelined loop is scheduled inside ``poly``."""
    db = root / v.project / SOLUTION / ".autopilot" / "db"
    path = db / f"{TOP}_Pipeline_{LOOP}.verbose.sched.rpt"
    if not path.is_file():
        raise RuntimeError(f"No schedule report at {path}.  Only a pipelined loop has one; "
                           f"is {v.name} pipelined, and synthesized?")
    return path


def read_schedule(path: Path) -> dict:
    """The operations that do the work, and the states each one occupies.

    Kept: the floating-point multiplies and adds, and the loads and stores
    on the x and y memories (whose CoreInst is a RAM).  Dropped: the loop
    counter, port reads, bit casts and the rest of the bookkeeping, all of
    which take no time of their own.

    An operation that takes n states appears once in each, marked
    ``[n/n]``, ``[n-1/n]``, ... ``[1/n]``; ``[n/n]`` starts a new one.  Names
    are not unique -- the stores of an unrolled loop are all
    ``store_ln<line>`` -- so that marker, not the name, separates them.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    m = _PIPE.search(text)
    if m is None:
        raise RuntimeError(f"{path} describes no pipeline.")
    rows: list[dict] = []
    open_ops: dict[str, dict] = {}         # name -> the instance still in progress
    for line in text.splitlines():
        hit = _OP_LINE.match(line)
        if hit is None:
            continue
        core = _CORE.search(line)
        core = core.group("core") if core else ""
        op = hit.group("op")
        if op not in ("fmul", "fadd") and not core.startswith("RAM"):
            continue
        state, k, n, name = (int(hit.group("state")), int(hit.group("k")), int(hit.group("n")),
                             hit.group("name"))
        entry = open_ops.get(name)
        if k == n or entry is None:
            entry = {"name": name, "op": op, "core": core, "first": state, "last": state,
                     "src": (hit.group("src") or "").split("->")[0]}
            rows.append(entry)
            open_ops[name] = entry
        entry["last"] = max(entry["last"], state)
    rows.sort(key=lambda o: (o["first"], o["name"]))
    return {"ii": int(m.group("ii")), "depth": int(m.group("d")), "ops": rows}


def write_schedule_table(sched: dict, path: Path) -> Path:
    """One line per operation: the states it spans."""
    lines = [f"II = {sched['ii']}, depth = {sched['depth']} states", "",
             "| Operation | Kind | States | Cycles | Source |", "|---|---|---|---|---|"]
    for o in sched["ops"]:
        span = (f"{o['first']}" if o["first"] == o["last"] else f"{o['first']}-{o['last']}")
        lines.append(f"| {o['name']} | {o['op']} | {span} | {o['last'] - o['first'] + 1} "
                     f"| {o['src']} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


_OP_COLOR = {"load": _BLUE, "fmul": _VIOLET, "fadd": _TEAL, "store": _AMBER}


def _op_label(o: dict) -> str:
    return {"load": "load x", "store": "store y"}.get(o["op"], o["op"])


def _gantt(ax, ops: list[dict], depth: int, span: int) -> None:
    """One iteration, one row per operation.  State s is cycle s-1."""
    for row, o in enumerate(ops):
        start, width = o["first"] - 1, o["last"] - o["first"] + 1
        ax.barh(row, width, left=start, height=0.7, color=_OP_COLOR.get(o["op"], _MUTED),
                edgecolor="white")
        ax.text(start + width / 2, row, f"{width}", ha="center", va="center", fontsize=8,
                color="white")
    ax.set_yticks(range(len(ops)))
    ax.set_yticklabels([f"{_op_label(o)}  ({o['name']})" for o in ops], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, span)
    ax.set_title(f"One iteration: {depth} cycles from loading x to storing y",
                 loc="left", fontsize=11, color=_INK)


def write_schedule_plot(sched: dict, png_path: Path, *, nsamples: int = 6,
                        overlap: bool = True) -> Path:
    """Top: one iteration's operations against the cycle it is in.  Bottom,
    with ``overlap``: the first few iterations, each starting II cycles after
    the last.  That view needs one operation of each kind per iteration, so
    an unrolled loop gets the top alone."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    ops, ii, depth = sched["ops"], sched["ii"], sched["depth"]
    span = depth + (nsamples - 1) * ii if overlap else depth
    if not overlap:
        fig, ax1 = plt.subplots(figsize=(max(9.0, 0.3 * span), 1.2 + 0.26 * len(ops)))
        _gantt(ax1, ops, depth, span)
        ax1.set_xlabel("clock cycle of the iteration")
        kinds = [k for k in _OP_COLOR if any(o["op"] == k for o in ops)]
        ax1.legend(handles=[Patch(color=_OP_COLOR[k], label={"load": "load x", "store":
                                  "store y"}.get(k, k)) for k in kinds],
                   frameon=False, fontsize=8, loc="upper right")
        for side in ("top", "right"):
            ax1.spines[side].set_visible(False)
        ax1.grid(axis="x", alpha=0.25, lw=0.5)
        ax1.set_axisbelow(True)
        fig.tight_layout()
        _save(fig, png_path)
        plt.close(fig)
        return png_path

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(max(9.0, 0.3 * span), 2.0 + 0.32 * (len(ops) + nsamples)),
                                   gridspec_kw={"height_ratios": [len(ops), nsamples]})
    _gantt(ax1, ops, depth, span)

    # Several iterations, overlapped.
    for k in range(nsamples):
        for o in ops:
            start, width = k * ii + o["first"] - 1, o["last"] - o["first"] + 1
            ax2.barh(k, width, left=start, height=0.7, color=_OP_COLOR.get(o["op"], _MUTED),
                     edgecolor="white", lw=0.5)
    ax2.set_yticks(range(nsamples))
    ax2.set_yticklabels([f"iteration {k}" for k in range(nsamples)], fontsize=8)
    ax2.invert_yaxis()
    ax2.set_xlim(0, span)
    ax2.set_xlabel("clock cycle")
    every = "every cycle" if ii == 1 else f"every {ii} cycles"
    inflight = -(-depth // ii)             # ceil(depth / II)
    ax2.set_title(f"Pipelined, II = {ii}: a new iteration {every}, up to {inflight} in flight "
                  "at once", loc="left", fontsize=11, color=_INK)
    kinds = [k for k in _OP_COLOR if any(o["op"] == k for o in ops)]
    ax2.legend(handles=[Patch(color=_OP_COLOR[k], label={"load": "load x", "store": "store y"}
                              .get(k, k)) for k in kinds],
               frameon=False, fontsize=8, ncol=len(kinds), loc="lower right",
               bbox_to_anchor=(1.0, 1.12))
    for ax in (ax1, ax2):
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.grid(axis="x", alpha=0.25, lw=0.5)
        ax.set_axisbelow(True)
    fig.tight_layout(h_pad=1.5)
    _save(fig, png_path)
    plt.close(fig)
    return png_path


# ------------------------------------------------------------ timing diagram --
_PORT = re.compile(r"^(?P<arr>x|y)(?:_(?P<bank>\d+))?_(?P<sig>address0|ce0|q0|we0|d0)$")


def _vcd(vcd_path: Path):
    from vcdvcd import VCDVCD
    return VCDVCD(str(vcd_path), signals=None, store_tvs=True)


def _short(name: str) -> str:
    return name.split(".")[-1].split("[")[0]


def _find(names: list[str], short: str, vcd_path: Path) -> str:
    hits = [s for s in names if _short(s) == short]
    if not hits:
        raise RuntimeError(f"No signal named {short!r} in {vcd_path}")
    # The top-level port, not a sub-module's copy of it: the shortest path.
    return min(hits, key=len)


def _memory_ports(names: list[str]) -> dict[tuple, str]:
    """The x and y memory ports, keyed by (array, bank, signal)."""
    ports = {}
    for s in names:
        m = _PORT.match(_short(s))
        if m is None:
            continue
        key = (m.group("arr"), int(m.group("bank") or 0), m.group("sig"))
        if key not in ports or len(s) < len(ports[key]):
            ports[key] = s
    return ports


def handshake(vcd_path: Path) -> tuple[float, float]:
    """(start, done) of the call: ap_start's first rise, and the first time
    ap_done is high after it."""
    from waveflow.utils.vcd import VcdParser

    vcd = _vcd(vcd_path)
    vp = VcdParser(vcd)
    names = list(vcd.signals)
    vp.add_signal(_find(names, "ap_start", vcd_path), short_name="ap_start")
    vp.add_signal(_find(names, "ap_done", vcd_path), short_name="ap_done")
    sigs = {s.name: s for s in vp.get_td_signals()}
    start = next(t for t, v in zip(sigs["ap_start"].times, sigs["ap_start"].values) if v == "1")
    done = next(t for t, v in zip(sigs["ap_done"].times, sigs["ap_done"].values)
                if v == "1" and t > start)
    return start, done


def _writes(vcd, ports, period_ns, time_scale=1e3) -> list[float]:
    """Times at which any y bank's write enable is high on a clock edge."""
    times = set()
    for (arr, _bank, sig), name in ports.items():
        if arr != "y" or sig != "we0":
            continue
        tv = vcd[name].tv
        for (t, v), nxt in zip(tv, tv[1:] + [(None, None)]):
            if v != "1":
                continue
            t1 = nxt[0] if nxt[0] is not None else t + period_ns * time_scale
            k = t
            while k < t1:
                times.add(k / time_scale)
                k += period_ns * time_scale
    return sorted(times)


def write_timing_diagram(vcd_path: Path, png_path: Path, *, period_ns: float, title: str,
                         ncycles: int | None = None, show_data: bool = True) -> dict:
    """The start of the call: ap_start, each x read address, and each y
    write, with the first sample's latency marked.

    Returns what was measured: the call's cycles, and the cycle of the first
    write to y counted from ap_start.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from waveflow.utils.timing import SigTimingInfo, TimingDiagram
    from waveflow.utils.vcd import VcdParser

    start, done = handshake(vcd_path)
    vcd = _vcd(vcd_path)
    names = list(vcd.signals)
    ports = _memory_ports(names)
    writes = _writes(vcd, ports, period_ns)
    first_write = next(t for t in writes if t > start)

    t0 = start - 2 * period_ns
    t1 = (first_write + 8 * period_ns) if ncycles is None else start + ncycles * period_ns
    t1 = min(t1, done + 2 * period_ns)

    vp = VcdParser(vcd)
    vp.add_clock_signal()
    vp.add_signal(_find(names, "ap_start", vcd_path), short_name="ap_start")
    banks = sorted({b for (_a, b, _s) in ports})
    for arr, sigs in (("x", ("address0",) + (("q0",) if show_data else ())),
                      ("y", ("we0", "address0") + (("d0",) if show_data else ()))):
        for b in banks:
            for sig in sigs:
                name = ports.get((arr, b, sig))
                if name is None:
                    continue
                label = f"{arr}_{b}_{sig}" if len(banks) > 1 else f"{arr}_{sig}"
                if sig in ("q0", "d0"):
                    vp.add_signal(name, short_name=label, numeric_type="float",
                                  numeric_fmt_str="%.2f")
                else:
                    vp.add_signal(name, short_name=label, numeric_type="uint",
                                  numeric_fmt_str="%d")
    vp.add_signal(_find(names, "ap_done", vcd_path), short_name="ap_done")

    td = TimingDiagram()
    for s in vp.get_td_signals():
        keep = [k for k, t in enumerate(s.times) if t < t1]
        td.add_signal(SigTimingInfo(s.name, [s.times[k] for k in keep],
                                    [s.values[k] for k in keep], is_clock=s.is_clock))
    ncyc = (t1 - t0) / period_ns
    ax = td.plot_signals(add_clk_grid=True, trange=(t0, t1),
                         fig_width=min(18.0, max(8.0, 0.34 * ncyc)), text_mode="always")
    ax.set_xlabel("time [ns]")
    tr = ax.get_xaxis_transform()
    lat = round((first_write - start) / period_ns)
    for t, c in ((start, _TEAL), (first_write, _VIOLET)):
        ax.axvline(t, color=c, lw=2, alpha=0.85, zorder=6)
    ax.annotate("", xy=(first_write, 1.06), xytext=(start, 1.06), xycoords=tr,
                arrowprops=dict(arrowstyle="<->", color=_INK, lw=1.2))
    ax.text((start + first_write) / 2, 1.09,
            f"{title}:  first y written {lat} cycles after ap_start", transform=tr,
            ha="center", va="bottom", fontsize=11, color=_INK)
    _save(ax.get_figure(), png_path)
    plt.close(ax.get_figure())
    return {"call_cycles": round((done - start) / period_ns),
            "first_write_cycle": lat,
            "writes_in_window": sum(1 for t in writes if start <= t < t1)}
