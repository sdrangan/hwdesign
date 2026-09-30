"""Decode the two AXI4-Stream ports from the co-simulation VCD, and plot them.

The VCD holds the IP's eight ports: the clock, the reset, and TDATA, TVALID
and TREADY on each of ``in_stream`` and ``out_stream``.  A sample moves
across a port on a rising clock edge where TVALID and TREADY are both high,
so the transfers can be read straight off the wires -- which gives three
things the rest of the build cannot:

* the **latency**: cycles from the first sample in to the first sample out;
* the **throughput**: whether a sample moved on every cycle, or stalled;
* the **data** itself, decoded from TDATA, which should be the test vector
  going in and the golden model's output coming out.

The co-simulation testbench keeps TVALID high after the last real sample
and feeds the RTL some extra beats of meaningless data until it has
collected every output.  Only the first ``nsamp`` beats on each port are
the test vector; the rest are marked on the full-run diagram and otherwise
ignored.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class StreamTrace:
    """What the two ports did, decoded from the VCD."""

    clk_period_ns: float
    #: Time (ns) of each transfer on each port, in order.
    t_in: np.ndarray
    t_out: np.ndarray
    #: TDATA of each transfer, reinterpreted as float32.
    x: np.ndarray
    y: np.ndarray
    #: Cycles in which a port had a transfer under way but TVALID or TREADY
    #: was low -- zero for a stream that never stalls.
    stalls_in: int
    stalls_out: int

    @property
    def latency_cycles(self) -> int:
        return int(round((self.t_out[0] - self.t_in[0]) / self.clk_period_ns))


def _parser(vcd_path: Path):
    from vcdvcd import VCDVCD
    from waveflow.utils.vcd import VcdParser

    vcd = VCDVCD(str(vcd_path), signals=None, store_tvs=True)
    vp = VcdParser(vcd)
    clk = vp.add_clock_signal()
    ins, _ = vp.add_axiss_signals(name="in_stream_", short_name_prefix="in_stream")
    outs, _ = vp.add_axiss_signals(name="out_stream_", short_name_prefix="out_stream")
    return vp, clk, ins, outs


def decode(vcd_path: Path, nsamp: int) -> StreamTrace:
    """Read the transfers on both ports; keep the first ``nsamp`` on each."""
    vp, clk, ins, outs = _parser(vcd_path)
    (burst_in,), period = vp.extract_axis_bursts(clk, ins)
    (burst_out,), _ = vp.extract_axis_bursts(clk, outs)

    def transfers(burst):
        # beat_type is one entry per cycle from the first transfer: 0 is a
        # transfer, anything else a cycle where the handshake did not happen.
        kinds = np.asarray(burst["beat_type"])
        cycles = np.flatnonzero(kinds == 0)[:nsamp]
        times = burst["tstart"] + cycles * period
        data = np.asarray(burst["data"][:nsamp]).astype(np.uint32).view(np.float32)
        stalls = int(np.sum(kinds[: cycles[-1] + 1] != 0)) if cycles.size else 0
        return times, data, stalls

    t_in, x, stalls_in = transfers(burst_in)
    t_out, y, stalls_out = transfers(burst_out)
    if len(x) < nsamp or len(y) < nsamp:
        raise RuntimeError(
            f"The VCD has {len(x)} input and {len(y)} output transfers; the test "
            f"vector has {nsamp} samples."
        )
    return StreamTrace(float(period), t_in, t_out, x, y, stalls_in, stalls_out)


_TEAL, _PURPLE = "#00857C", "#57068C"


def _as_float(label: str) -> str:
    """Relabel a TDATA value, given as a decimal integer, as the float32 it holds.

    Decoded here rather than by setting the parser's ``numeric_type`` to
    ``"float"``, which byte-swaps the word on a little-endian machine.
    """
    if not label.isdigit():
        return label  # X or Z
    return f"{np.array([int(label)], dtype=np.uint32).view(np.float32)[0]:.2f}"


def _crop(sig, t0: float, t1: float):
    """Keep only what ``sig`` does inside [t0, t1].

    The plotter clips segments to its window but still labels them, so a
    whole run's worth of TDATA labels piles up at the window's edges.
    Cropping first leaves it only the segments that are actually visible.
    """
    from waveflow.utils.timing import SigTimingInfo

    times = np.asarray(sig.times, dtype=float)
    # `< t1`, not `<=`: a change exactly at the right edge would be a
    # zero-width segment whose label overlaps its neighbour's.
    keep = np.flatnonzero((times > t0) & (times < t1))
    before = np.flatnonzero(times <= t0)
    idx = ([before[-1]] if before.size else []) + list(keep)
    new_times = [max(float(times[i]), t0) for i in idx]
    values = [sig.values[i] for i in idx]
    if sig.name.endswith("TDATA"):
        values = [_as_float(v) for v in values]
    return SigTimingInfo(sig.name, new_times, values, is_clock=sig.is_clock)


def _save(fig, png_path: Path) -> Path:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    # No timestamp metadata, so an unchanged simulation gives an identical file.
    fig.savefig(png_path, dpi=200, bbox_inches="tight", pad_inches=0.06,
                metadata={"Software": None, "Date": None})
    return png_path


def write_timing_diagram(vcd_path: Path, png_path: Path, trace: StreamTrace, *,
                         trange: tuple[float, float]) -> Path:
    """Plot every port over ``trange``, marking the first sample in and out."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from waveflow.utils.timing import TimingDiagram

    vp, *_ = _parser(vcd_path)
    for sig in vp.sig_info.values():
        # TDATA is a float32.  Read the word as a plain integer here; _crop
        # relabels it with the float value.
        if sig.short_name.endswith("TDATA"):
            sig.numeric_type = "uint"
            sig.numeric_fmt_str = "%d"

    t0, t1 = trange
    td = TimingDiagram()
    td.add_signals([_crop(s, t0, t1) for s in vp.get_td_signals()])
    ncycles = (t1 - t0) / trace.clk_period_ns
    ax = td.plot_signals(add_clk_grid=True, trange=trange,
                         fig_width=max(10.0, 0.55 * ncycles), text_mode="always")
    ax.set_xlabel("Time [ns]")
    tr = ax.get_xaxis_transform()

    t_in, t_out = trace.t_in[0], trace.t_out[0]
    for t, label, color in ((t_in, "first sample in", _TEAL),
                            (t_out, "first sample out", _PURPLE)):
        ax.axvline(t, color=color, lw=2, alpha=0.85, zorder=6)
        ax.text(t, 1.012, label, transform=tr, ha="center", va="bottom",
                fontsize=10, color=color, fontweight="bold")
    ax.annotate("", xy=(t_out, 1.085), xytext=(t_in, 1.085), xycoords=tr,
                arrowprops=dict(arrowstyle="<->", color="0.25", lw=1.2))
    ax.text((t_in + t_out) / 2, 1.1, f"latency: {trace.latency_cycles} cycles",
            transform=tr, ha="center", va="bottom", fontsize=11, color="0.15")

    fig = ax.get_figure()
    _save(fig, png_path)
    plt.close(fig)
    return png_path


def write_stream_plot(png_path: Path, trace: StreamTrace, y_model: np.ndarray) -> Path:
    """Plot the data on both ports against time, over the whole run.

    A waveform of a few hundred cycles is unreadable, but the *values* that
    crossed each port are not: plotted against the time they crossed, the
    output is visibly the filtered input, ``latency`` cycles later.  The
    Python model's output is drawn on top, at the times the RTL produced it.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
    axes[0].step(trace.t_in, trace.x, where="post", color="C0", lw=1)
    axes[0].set_ylabel("in_stream TDATA")
    axes[0].set_title("Samples crossing each port, decoded from the VCD")
    axes[1].step(trace.t_out, trace.y, where="post", color="C1", lw=1.5,
                 label="out_stream TDATA (RTL)")
    axes[1].plot(trace.t_out, y_model, "o", ms=2.5, color="0.25",
                 label="Python model")
    axes[1].set_ylabel("out_stream TDATA")
    axes[1].set_xlabel("Time [ns]")
    axes[1].legend(loc="upper left", frameon=False)

    lat_ns = trace.t_out[0] - trace.t_in[0]
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.axvline(trace.t_in[0], color=_TEAL, lw=1.2, ls="--")
        ax.axvline(trace.t_out[0], color=_PURPLE, lw=1.2, ls="--")
    axes[1].annotate("", xy=(trace.t_out[0], 0.5), xytext=(trace.t_in[0], 0.5),
                     xycoords=axes[1].get_xaxis_transform(),
                     arrowprops=dict(arrowstyle="<->", color="0.25", lw=1.2))
    axes[1].text(trace.t_in[0] + lat_ns / 2, 0.53,
                 f"{trace.latency_cycles} cycles",
                 transform=axes[1].get_xaxis_transform(), ha="center",
                 va="bottom", fontsize=9, color="0.15")
    fig.tight_layout()
    _save(fig, png_path)
    plt.close(fig)
    return png_path
