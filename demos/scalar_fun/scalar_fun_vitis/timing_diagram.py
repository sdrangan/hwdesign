"""Draw the AXI4-Lite timing diagram from the co-simulation VCD.

Co-simulation records every signal in the synthesized IP.  The interesting
ones here are the handful on the processor interface: the status signals
(``ap_start``, ``ap_done``, ``ap_idle``) and the ``s_axi_ctrl`` bundle that
carries the register reads and writes.  Plotted together they show the
execution model the unit describes -- the processor writes x, w and b,
raises start, waits for done, then reads y back.

This used to be a notebook the student ran by hand after a manual RTL
simulation.  It is a build step now, so the diagram is produced by the same
command that runs the simulation and cannot fall out of step with it.
"""
from __future__ import annotations

from pathlib import Path

# Address and data buses read better in hex than in decimal.
_HEX_SIGNALS = ("ARADDR", "AWADDR", "RDATA", "WDATA")


# Tints for the three phases of one call.  Light enough to read signal
# transitions straight through them.
_PHASE_STYLE = [
    ("Host loads inputs", "#2F6FA8", 0.13),
    ("Kernel runs", "#E8A33D", 0.18),
    ("Host reads result", "#00857C", 0.13),
]


def _annotate_phases(ax, calls, trange) -> None:
    """Shade the load / run / read-back phases of every visible call."""
    lo, hi = ax.get_xlim()
    tr = ax.get_xaxis_transform()
    for call in calls:
        spans = [
            (call.start_ns, call.load_end_ns),
            (call.load_end_ns, call.read_start_ns),
            (call.read_start_ns, call.end_ns),
        ]
        for (t0, t1), (label, color, alpha) in zip(spans, _PHASE_STYLE):
            if t1 < lo or t0 > hi:
                continue
            ax.axvspan(t0, t1, color=color, alpha=alpha, lw=0, zorder=0)
            # Only label when the band is wide enough to hold the text.
            if (min(t1, hi) - max(t0, lo)) > 0.12 * (hi - lo):
                ax.text((max(t0, lo) + min(t1, hi)) / 2, 1.012, label,
                        transform=tr, ha="center", va="bottom",
                        fontsize=9, color=color, fontweight="bold")


def _annotate_iterations(ax, calls) -> None:
    """Mark where each call begins."""
    lo, hi = ax.get_xlim()
    tr = ax.get_xaxis_transform()
    for i, call in enumerate(calls, 1):
        t = call.start_ns
        if not (lo <= t <= hi):
            continue
        ax.axvline(t, color="#57068C", lw=2.2, alpha=0.85, zorder=6)
        ax.text(t, 1.012, f"call {i}", transform=tr, ha="left", va="bottom",
                fontsize=9, color="#57068C", fontweight="bold")


def write_timing_diagram(
    vcd_path: Path,
    png_path: Path,
    *,
    trange: tuple[float, float] | None = None,
    prefix: str = "s_axi_ctrl",
    phases: bool = False,
    iteration_marks: bool = False,
) -> Path:
    """Parse ``vcd_path`` and write a timing diagram to ``png_path``.

    ``phases`` tints each call's load / run / read-back phases, and
    ``iteration_marks`` draws a rule where every call begins.  Both are
    derived from the trace itself (see :mod:`axi_trace`), so they stay
    correct if the test vector changes.
    """
    import matplotlib
    matplotlib.use("Agg")
    from vcdvcd import VCDVCD

    from waveflow.utils.timing import TimingDiagram
    from waveflow.utils.vcd import VcdParser

    vcd = VCDVCD(str(vcd_path), signals=None, store_tvs=True)

    vp = VcdParser(vcd)
    vp.add_status_signals()
    vp.add_signals_prefix(prefix=prefix)

    for sig in vp.sig_info.values():
        if any(name in sig.short_name for name in _HEX_SIGNALS):
            sig.numeric_fmt_str = "%x"
            sig.numeric_type = "uint"

    td = TimingDiagram()
    td.add_signals(vp.get_td_signals())
    ax = td.plot_signals(
        add_clk_grid=True,
        trange=trange,
        text_mode="auto",
        text_scale_factor=10,
    )
    ax.set_xlabel("Time [ns]")

    if phases or iteration_marks:
        import axi_trace
        calls = axi_trace.decode(vcd_path)
        if phases:
            _annotate_phases(ax, calls, trange)
        if iteration_marks:
            _annotate_iterations(ax, calls)

    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig = ax.get_figure()
    # Suppress the timestamp and tool version PNG metadata, so an unchanged
    # simulation produces a byte-identical file and `git status` stays quiet.
    fig.savefig(
        png_path,
        dpi=200,
        bbox_inches="tight",
        pad_inches=0.06,
        metadata={"Software": None, "Date": None},
    )
    fig.clf()
    return png_path
