"""Decode the poly kernel's messages from the co-simulation VCD, and plot them.

On each AXI4-Stream port, a TLAST ends a burst, and every message and every
sample block is its own burst.  So the bursts on the wires line up one to
one with the protocol:

    in_stream:   PolyCmdHdr | x ...   (per transaction)
    out_stream:  PolyRespHdr | y ... | PolyRespFtr

Each burst's TDATA words are unpacked with the same schemas the kernel's
headers were generated from (``poly_schema.py``), which recovers every
message exactly as it crossed the port.  That gives the timing -- when each
message went by, the latency, how long a transaction takes, where the
stream stalled -- and one more check that the messages are the right ones.

After the last transaction, the co-simulation testbench keeps feeding the
input some beats of meaningless data; that last, unterminated burst is
ignored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from waveflow.hw.arrayutils import read_array

from poly_schema import Float32, PolyCmdHdr, PolyRespFtr, PolyRespHdr

# Burst colours, by kind of message.
_COLOR = {"hdr": "#E8A33D", "data": "#2E9E5B", "ftr": "#2F6FA8"}


@dataclass
class Burst:
    """One TLAST-terminated burst on one port."""

    port: str          # "in" or "out"
    kind: str          # "hdr", "data" or "ftr"
    txn: int
    # The burst occupies the bus from t0 to t1.  A word transfers on the
    # clock edge at the END of the cycle it is on the bus, so t0 is one
    # cycle before the first transfer's edge and t1 is the last one's edge.
    t0: float
    t1: float
    nwords: int
    stalls: int        # cycles inside the burst where nothing transferred
    label: str         # decoded contents, for the plot
    #: Per cycle from t0: True if a word transferred at the end of it.
    moved: list[bool] = field(default_factory=list)


@dataclass
class Txn:
    """What one transaction looked like on the wires."""

    k: int
    cmd_hdr: PolyCmdHdr
    x: np.ndarray
    resp_hdr: PolyRespHdr
    y: np.ndarray
    resp_ftr: PolyRespFtr
    bursts: list[Burst] = field(default_factory=list)

    def burst(self, port: str, kind: str) -> Burst:
        return next(b for b in self.bursts if b.port == port and b.kind == kind)


@dataclass
class Trace:
    word_bw: int
    clk_period_ns: float
    txns: list[Txn]

    def cycles(self, t0: float, t1: float) -> int:
        return int(round((t1 - t0) / self.clk_period_ns))


def _parser(vcd_path: Path):
    from vcdvcd import VCDVCD
    from waveflow.utils.vcd import VcdParser

    vp = VcdParser(VCDVCD(str(vcd_path), signals=None, store_tvs=True))
    clk = vp.add_clock_signal()
    ins, word_bw = vp.add_axiss_signals(name="in_stream_", short_name_prefix="in_stream")
    outs, _ = vp.add_axiss_signals(name="out_stream_", short_name_prefix="out_stream")
    return vp, clk, ins, outs, word_bw


def decode(vcd_path: Path, ntxn: int) -> Trace:
    """Split both ports into bursts and unpack each into its message."""
    vp, clk, ins, outs, word_bw = _parser(vcd_path)
    bursts_in, period = vp.extract_axis_bursts(clk, ins)
    bursts_out, _ = vp.extract_axis_bursts(clk, outs)

    # Two bursts in and three out per transaction; the unterminated padding
    # burst after the last transaction is not one of them.
    bursts_in = [b for b in bursts_in if b["complete"]]
    if len(bursts_in) < 2 * ntxn or len(bursts_out) < 3 * ntxn:
        raise RuntimeError(
            f"The VCD has {len(bursts_in)} input and {len(bursts_out)} output bursts; "
            f"{ntxn} transactions need {2 * ntxn} and {3 * ntxn}.")

    mask = (1 << word_bw) - 1

    def words(b):
        # The parser reads TDATA as a *signed* integer, so a word with its top
        # bit set comes back negative; masking to the port width restores the
        # bits.  The result is a uint64 array rather than a list, because
        # read_array converts a list of Python ints through float64, which
        # corrupts the low half of a 64-bit word.
        return np.array([int(w) & mask for w in b["data"]], dtype=np.uint64)

    def span(port, kind, k, b, label):
        kinds = b["beat_type"]
        t0 = float(b["tstart"]) - period
        return Burst(port, kind, k, t0, t0 + len(kinds) * period, len(b["data"]),
                     sum(1 for t in kinds if t != 0), label,
                     moved=[t == 0 for t in kinds])

    txns = []
    for k in range(ntxn):
        b_cmd, b_x = bursts_in[2 * k], bursts_in[2 * k + 1]
        b_rh, b_y, b_rf = bursts_out[3 * k: 3 * k + 3]

        cmd = PolyCmdHdr().deserialize(words(b_cmd), word_bw=word_bw)
        nsamp = int(cmd.nsamp)
        x = np.asarray(read_array(words(b_x), elem_type=Float32, word_bw=word_bw,
                                  shape=nsamp).val, dtype=np.float32)
        rh = PolyRespHdr().deserialize(words(b_rh), word_bw=word_bw)
        y = np.asarray(read_array(words(b_y), elem_type=Float32, word_bw=word_bw,
                                  shape=nsamp).val, dtype=np.float32)
        rf = PolyRespFtr().deserialize(words(b_rf), word_bw=word_bw)

        t = Txn(k, cmd, x, rh, y, rf)
        t.bursts = [
            span("in", "hdr", k, b_cmd, f"PolyCmdHdr tx_id=0x{int(cmd.tx_id):02x}"),
            span("in", "data", k, b_x, f"x: {nsamp} samples"),
            span("out", "hdr", k, b_rh, f"PolyRespHdr tx_id=0x{int(rh.tx_id):02x}"),
            span("out", "data", k, b_y, f"y: {nsamp} samples"),
            span("out", "ftr", k, b_rf, f"PolyRespFtr {int(rf.nsamp_read)} read, "
                                        f"{rf.error.name}"),
        ]
        txns.append(t)
    return Trace(word_bw, float(period), txns)


def measure(trace: Trace) -> list[dict]:
    """Per-transaction timing, in clock cycles."""
    out = []
    for t in trace.txns:
        cmd, xin = t.burst("in", "hdr"), t.burst("in", "data")
        rh, yout, rf = t.burst("out", "hdr"), t.burst("out", "data"), t.burst("out", "ftr")
        out.append({
            "tx_id": int(t.cmd_hdr.tx_id),
            "nsamp": int(t.cmd_hdr.nsamp),
            "cmd_hdr_words": cmd.nwords,
            "cmd_hdr_stall_cycles": cmd.stalls,
            # First sample in to first sample out: the pipeline depth.
            "latency_cycles": trace.cycles(xin.t0, yout.t0),
            "samples_in_cycles": trace.cycles(xin.t0, xin.t1),
            "samples_out_cycles": trace.cycles(yout.t0, yout.t1),
            # Command header's first word to the footer's last: the whole
            # transaction, as the host sees it.
            "transaction_cycles": trace.cycles(cmd.t0, rf.t1),
        })
    return out


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def _save(fig, png_path: Path) -> Path:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, dpi=200, bbox_inches="tight", pad_inches=0.06,
                metadata={"Software": None, "Date": None})
    return png_path


def _crop(sig, t0: float, t1: float):
    """Keep only what ``sig`` does inside [t0, t1)."""
    from waveflow.utils.timing import SigTimingInfo

    times = np.asarray(sig.times, dtype=float)
    keep = np.flatnonzero((times > t0) & (times < t1))
    before = np.flatnonzero(times <= t0)
    idx = ([before[-1]] if before.size else []) + list(keep)
    return SigTimingInfo(sig.name, [max(float(times[i]), t0) for i in idx],
                         [sig.values[i] for i in idx], is_clock=sig.is_clock)


def write_timing_diagram(vcd_path: Path, png_path: Path, trace: Trace, *,
                         trange: tuple[float, float] | None = None) -> Path:
    """The ports cycle by cycle over transaction 0, each burst shaded by message."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from waveflow.utils.timing import TimingDiagram

    t0_txn = trace.txns[0]
    T = trace.clk_period_ns
    if trange is None:
        trange = (t0_txn.burst("in", "hdr").t0 - 3 * T, t0_txn.burst("out", "ftr").t1 + 3 * T)
    t0, t1 = trange

    vp, *_ = _parser(vcd_path)
    # TKEEP and TSTRB are constant all-ones; they would only take up rows.
    sigs = [s for s in vp.get_td_signals()
            if not (s.name.endswith("TKEEP") or s.name.endswith("TSTRB"))]
    td = TimingDiagram()
    td.add_signals([_crop(s, t0, t1) for s in sigs])
    ax = td.plot_signals(add_clk_grid=False, trange=trange,
                         fig_width=16, text_mode="never")
    ax.set_xlabel("Time [ns]")

    # Shade each burst, and name it inside its TDATA band.
    for t in trace.txns:
        for b in t.bursts:
            if b.t1 <= t0 or b.t0 >= t1:
                continue
            row = f"{b.port}_stream_TDATA"
            td.add_patch(sig_name=row, time=[b.t0, b.t1], color=_COLOR[b.kind], alpha=0.35)
            ymid = (td.ytop[row] + td.ybot[row]) / 2
            ax.text((max(b.t0, t0) + min(b.t1, t1)) / 2, ymid, b.label,
                    ha="center", va="center", fontsize=8, color="0.1",
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=0.8))
    ax.legend(handles=[Patch(facecolor=_COLOR[k], alpha=0.35, label=n) for k, n in
                       (("hdr", "header"), ("data", "samples"), ("ftr", "footer"))],
              loc="upper left", bbox_to_anchor=(1.005, 1.0), frameon=False)

    fig = ax.get_figure()
    _save(fig, png_path)
    plt.close(fig)
    return png_path


def write_transaction_plot(png_path: Path, trace: Trace) -> Path:
    """Every burst of every transaction on both ports, as bars against time."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    T = trace.clk_period_ns
    fig, ax = plt.subplots(figsize=(14, 3.4))
    lanes = {"in": 1.0, "out": 0.0}
    for t in trace.txns:
        for b in t.bursts:
            y = lanes[b.port]
            # Solid where words moved; hatched where the burst was stalled
            # (TVALID or TREADY low) -- time spent waiting.
            runs, start = [], 0
            for i in range(1, len(b.moved) + 1):
                if i == len(b.moved) or b.moved[i] != b.moved[start]:
                    runs.append((b.moved[start], b.t0 + start * T, (i - start) * T))
                    start = i
            for moved, ts, dur in runs:
                ax.broken_barh([(ts, dur)], (y - 0.3, 0.6),
                               facecolors=_COLOR[b.kind] if moved else "white",
                               edgecolor="0.2" if moved else _COLOR[b.kind],
                               hatch=None if moved else "////", lw=0.6)
            if b.kind == "data":
                ax.text((b.t0 + b.t1) / 2, y, f"{'x' if b.port == 'in' else 'y'}: "
                        f"{int(t.cmd_hdr.nsamp)}", ha="center", va="center", fontsize=8,
                        color="white", fontweight="bold")
        cmd = t.burst("in", "hdr")
        ax.text(cmd.t0, 1.36, f"tx_id 0x{int(t.cmd_hdr.tx_id):02x}", ha="left",
                va="bottom", fontsize=8, color="0.25")
        # The pipeline latency: first sample in to first sample out.
        xin, yout = t.burst("in", "data"), t.burst("out", "data")
        ax.annotate("", xy=(yout.t0, 0.38), xytext=(xin.t0, 0.62),
                    arrowprops=dict(arrowstyle="->", color="0.3", lw=1))
        ax.text((xin.t0 + yout.t0) / 2, 0.5, f"{trace.cycles(xin.t0, yout.t0)} cyc",
                ha="center", va="center", fontsize=7, color="0.3",
                bbox=dict(facecolor="white", edgecolor="none", pad=0.5))

    ax.set_yticks([1, 0], ["in_stream", "out_stream"])
    ax.set_ylim(-0.55, 1.55)
    ax.set_xlabel("Time [ns]")
    ax.set_title(f"Messages on each port, decoded from the VCD (WORD_BW={trace.word_bw})")
    ax.grid(True, axis="x", alpha=0.3)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=_COLOR[k], label=n) for k, n in
                       (("hdr", "header"), ("data", "samples"), ("ftr", "footer"))]
              + [Patch(facecolor="white", edgecolor="0.4", hatch="////", label="stalled")],
              loc="upper left", bbox_to_anchor=(1.005, 1.0), frameon=False)
    fig.tight_layout()
    _save(fig, png_path)
    plt.close(fig)
    return png_path
