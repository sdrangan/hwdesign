"""Read the clock-period sweep out of the synthesis reports, and plot it;
and draw the co-simulation timing diagram.

Each solution in ``quad_proj`` is the same kernel synthesized for one clock
period (run.tcl names them ``p10``, ``p3_33``, ``pipe_p10``, ...).  Its
report says what Vitis HLS made of that period:

* **latency**: cycles from ap_start to ap_done, and so in ns;
* **interval**: cycles before the next call can start -- latency + 1 for the
  plain function, 1 once it is pipelined;
* **estimated clock period**: the slowest register-to-register path Vitis
  scheduled.  Above the target, the design does not meet timing at that
  clock;
* **resources**: DSP blocks, flip-flops and LUTs.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT = "quad_proj"
TOP = "quad"

# The deck's palette (tools/build_timing_slides.py).
_VIOLET, _TEAL, _AMBER, _INK, _MUTED = "#57068C", "#00857C", "#B4530F", "#262626", "#6E6E6E"


def solution_name(period_ns: float, pipelined: bool = False) -> str:
    """The name run.tcl gives a solution: p3_33 for 3.33 ns."""
    name = "p" + f"{period_ns:g}".replace(".", "_")
    return f"pipe_{name}" if pipelined else name


def report_dir(root: Path, period_ns: float, pipelined: bool = False) -> Path:
    """Where Vitis writes one solution's synthesis report."""
    return root / PROJECT / solution_name(period_ns, pipelined) / "syn" / "report"


def read_solution(root: Path, period_ns: float, pipelined: bool = False) -> dict:
    """Everything the demo uses from one solution's report.

    waveflow's csynthparse does the reading: ``synth_target`` for the clock,
    ``module_latency`` for the latency and interval, ``CsynthParser`` for the
    resources.  Only the clock uncertainty is read here, since none of them
    returns it.
    """
    from waveflow.utils.csynthparse import CsynthParser, module_latency, synth_target

    rdir = report_dir(root, period_ns, pipelined)
    clock = synth_target(rdir)                  # target, estimated period, part
    lat = module_latency(rdir, TOP)             # latency and interval, in cycles
    if clock is None or lat is None:
        raise RuntimeError(f"No synthesis report in {rdir}: run the sweep step first.")
    parser = CsynthParser(report_path=str(rdir))
    parser.get_total_resources()                # DSP, FF, LUT, ...
    res = parser.total_resources

    xml = ET.parse(rdir / "csynth.xml").getroot()
    uncertainty = float(xml.findtext("UserAssignments/ClockUncertainty"))

    target, est = clock["target_period_ns"], clock["estimated_period_ns"]
    latency, interval = lat["latency_max"], lat["interval_max"]
    return {
        "solution": solution_name(period_ns, pipelined),
        "pipelined": pipelined,
        "target_ns": target,
        "fclk_mhz": round(1000.0 / target, 1),
        "uncertainty_ns": uncertainty,
        "estimated_ns": est,
        # Vitis schedules to the target minus the uncertainty; it reports a
        # violation when the estimate exceeds that.
        "meets_timing": est is not None and est <= target - uncertainty + 1e-9,
        "latency_cycles": latency,
        "latency_ns": None if latency is None else round(latency * target, 2),
        "interval_cycles": interval,
        "throughput_msps": None if not interval else round(1000.0 / (interval * target), 1),
        "dsp": res.get("DSP"),
        "ff": res.get("FF"),
        "lut": res.get("LUT"),
    }


def read_sweep(root: Path, periods: list[float]) -> list[dict]:
    """One row per (variant, period), slowest clock first."""
    return [read_solution(root, p, pipe) for pipe in (False, True)
            for p in sorted(periods, reverse=True)]


def write_sweep_table(rows: list[dict], path: Path) -> Path:
    """The sweep as a Markdown table, for the docs and the terminal."""
    head = ("| Clock | Target | Estimated | Latency | Latency | Interval | DSP | FF | LUT |\n"
            "|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for variant in (False, True):
        lines.append(f"| **{'pipelined, II = 1' if variant else 'not pipelined'}** "
                     "| | | | | | | | |")
        for r in (r for r in rows if r["pipelined"] == variant):
            # Plain text: a Windows console prints the table, and cp1252 has no check marks.
            est = f"{r['estimated_ns']:.2f} ns" + ("" if r["meets_timing"] else " (fails)")
            # Latency 0: ap_done rises in the cycle ap_start does; all combinational.
            lat_ns = "same cycle" if r["latency_cycles"] == 0 else f"{r['latency_ns']:g} ns"
            lines.append(f"| {r['fclk_mhz']:g} MHz | {r['target_ns']:g} ns | {est} "
                         f"| {r['latency_cycles']} cycles | {lat_ns} "
                         f"| {r['interval_cycles']} | {r['dsp']} | {r['ff']} | {r['lut']} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return path


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


def write_sweep_plot(rows: list[dict], png_path: Path) -> Path:
    """Latency in cycles and in ns, throughput, and the achieved clock period,
    against the target clock frequency."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plain = [r for r in rows if not r["pipelined"]]
    pipe = [r for r in rows if r["pipelined"]]
    f = [r["fclk_mhz"] for r in plain]

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.0))
    axes = axes.ravel()
    ax = axes[0]
    ax.plot(f, [r["latency_cycles"] for r in plain], "o-", color=_VIOLET, lw=2)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("latency [clock cycles]")
    ax.set_title("A faster clock takes more cycles", loc="left", fontsize=11, color=_INK)

    ax = axes[1]
    ax.plot(f, [r["latency_ns"] for r in plain], "o-", color=_VIOLET, lw=2)
    for r in plain:
        if r["latency_cycles"] == 0:
            ax.annotate("0 cycles: all\ncombinational", (r["fclk_mhz"], 0),
                        xytext=(40, 18), textcoords="offset points", fontsize=9, color=_MUTED,
                        arrowprops=dict(arrowstyle="-", color=_MUTED, lw=0.8))
    ax.set_ylim(bottom=0)
    ax.set_ylabel("latency [ns]")
    ax.set_title("but no less time: registers cost delay", loc="left", fontsize=11, color=_INK)

    ax = axes[2]
    ax.plot(f, [r["throughput_msps"] for r in plain], "o-", color=_VIOLET, lw=2,
            label="not pipelined")
    ax.plot(f, [r["throughput_msps"] for r in pipe], "s-", color=_TEAL, lw=2,
            label="pipelined, II = 1")
    ax.set_ylim(bottom=0)
    ax.set_ylabel("throughput [M results/s]")
    ax.set_title("Pipelining: a new input every cycle", loc="left", fontsize=11, color=_INK)
    ax.legend(frameon=False, fontsize=9)

    ax = axes[3]
    ax.plot(f, [r["target_ns"] for r in plain], "-", color=_MUTED, lw=1.2, label="target period")
    ax.plot(f, [r["target_ns"] - r["uncertainty_ns"] for r in plain], ":", color=_MUTED,
            lw=1.2, label="target − uncertainty")
    ok = [r for r in plain if r["meets_timing"]]
    bad = [r for r in plain if not r["meets_timing"]]
    ax.plot([r["fclk_mhz"] for r in ok], [r["estimated_ns"] for r in ok], "o", color=_TEAL,
            label="estimated: meets timing")
    if bad:
        ax.plot([r["fclk_mhz"] for r in bad], [r["estimated_ns"] for r in bad], "X",
                color=_AMBER, ms=9, label="estimated: fails timing")
    ax.set_ylabel("clock period [ns]")
    ax.set_ylim(bottom=0)
    ax.set_title("Achieved clock period", loc="left", fontsize=11, color=_INK)
    ax.legend(frameon=False, fontsize=9)

    for ax in axes:
        ax.set_xlabel("target clock frequency [MHz]")
        _style(ax)
    fig.tight_layout(w_pad=2.0, h_pad=1.6)
    _save(fig, png_path)
    plt.close(fig)
    return png_path


# ------------------------------------------------------------ timing diagram --
def _parser(vcd_path: Path):
    from vcdvcd import VCDVCD
    from waveflow.utils.vcd import VcdParser

    vcd = VCDVCD(str(vcd_path), signals=None, store_tvs=True)
    vp = VcdParser(vcd)
    vp.add_clock_signal()
    names = list(vcd.signals)

    def find(suffix):
        hits = [s for s in names if s.split(".")[-1].split("[")[0] == suffix]
        if not hits:
            raise RuntimeError(f"No signal named {suffix!r} in {vcd_path}; it has {names}")
        return hits[0]

    for short in ("ap_start", "ap_done", "x", "ap_return"):
        vp.add_signal(find(short), short_name="y" if short == "ap_return" else short)
    return vp


def handshakes(vcd_path: Path) -> list[tuple[float, float]]:
    """(start, done) times of each call: the rising edge of ap_start that
    begins it, and the clock edge at which ap_done is high."""
    vp = _parser(vcd_path)
    sigs = {s.name: s for s in vp.get_td_signals()}
    start, done = sigs["ap_start"], sigs["ap_done"]
    starts = [t for t, v in zip(start.times, start.values) if v == "1"]
    dones = [t for t, v in zip(done.times, done.values) if v == "1"]
    calls = []
    for t0 in starts:
        later = [t for t in dones if t > t0]
        if later:
            calls.append((t0, later[0]))
    return calls


def write_timing_diagram(vcd_path: Path, png_path: Path, *, period_ns: float,
                         ncalls: int = 3) -> Path:
    """The first few calls: ap_start, x, ap_done and y, with the latency of
    the first call marked."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from waveflow.utils.timing import SigTimingInfo, TimingDiagram

    calls = handshakes(vcd_path)
    if not calls:
        raise RuntimeError(f"No ap_start / ap_done handshake found in {vcd_path}.")
    t0 = calls[0][0] - 2 * period_ns
    t1 = calls[min(ncalls, len(calls)) - 1][1] + 2 * period_ns

    vp = _parser(vcd_path)
    td = TimingDiagram()
    for s in vp.get_td_signals():
        keep = [k for k, t in enumerate(s.times) if t < t1]
        td.add_signal(SigTimingInfo(s.name, [s.times[k] for k in keep],
                                    [s.values[k] for k in keep], is_clock=s.is_clock))
    ncyc = (t1 - t0) / period_ns
    ax = td.plot_signals(add_clk_grid=True, trange=(t0, t1),
                         fig_width=max(8.0, 0.32 * ncyc), text_mode="always")
    ax.set_xlabel("time [ns]")
    tr = ax.get_xaxis_transform()
    a, b = calls[0]
    cycles = round((b - a) / period_ns)
    for t, c in ((a, _TEAL), (b, _VIOLET)):
        ax.axvline(t, color=c, lw=2, alpha=0.85, zorder=6)
    ax.annotate("", xy=(b, 1.06), xytext=(a, 1.06), xycoords=tr,
                arrowprops=dict(arrowstyle="<->", color=_INK, lw=1.2))
    ax.text((a + b) / 2, 1.09, f"{1000 / period_ns:g} MHz clock:  latency {cycles} cycles "
            f"= {cycles * period_ns:g} ns", transform=tr, ha="center", va="bottom",
            fontsize=11, color=_INK)
    fig = ax.get_figure()
    _save(fig, png_path)
    plt.close(fig)
    return png_path
