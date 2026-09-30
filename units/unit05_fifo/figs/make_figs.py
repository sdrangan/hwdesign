"""Generate unit 5's figures.

Replaces fifo_figs.ipynb, for the reason unit 4's make_figs.py gives: a
notebook re-serialises its outputs on every run, so the tracked file changed
whether or not a figure did.  This script writes only the PNGs, byte-identically
when a figure has not changed.

    python make_figs.py                 # write the PNGs
    python make_figs.py --check         # fail if any tracked PNG is stale
    python make_figs.py --only axis_stall

The cycle-level figures are not drawn from hand-typed tables.  Each is
*simulated* from the rules its problem states (registered backpressure, a
consumer that is busy for so many cycles after a read) by `simulate_fifo`, and
the simulator is checked against the published solutions in fifo.xml before
anything is drawn.  A figure and a solution table that disagree is exactly the
kind of error a hand-drawn diagram hides.

Run it with the interpreter that has waveflow (hwdesign-venv), as for unit 4.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")                     # no display, and identical on any machine
import matplotlib.pyplot as plt           # noqa: E402
import numpy as np                        # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.patches import Patch      # noqa: E402

try:
    from waveflow.utils.timing import ClkSig, SigTimingInfo, TimingDiagram  # noqa: E402
except ModuleNotFoundError as exc:      # the usual cause: the wrong interpreter
    raise SystemExit(
        f"{exc}. waveflow lives in the pysilicon repo and is installed in hwdesign-venv "
        "and pysilicon-venv, not in chat-env. Run this with, for example:\n"
        "  ../../../hwdesign-venv/Scripts/python make_figs.py") from exc

HERE = Path(__file__).resolve().parent

# The deck's palette (see tools/build_fifo_slides.py, which shares unit 4's):
# violet for storage and the IP, slate for the processor and control, teal for
# data that moves, amber for trouble.
INK = "#262626"
VIOLET = "#57068C"
VIOLET_FILL = "#E4D5EF"
TEAL = "#00857C"
TEAL_FILL = "#CFE9E5"
SLATE = "#2F6FA8"
SLATE_FILL = "#DCE7F2"
AMBER = "#B4530F"
MUTED = "#6E6E6E"
IDLE = "#E9E9EE"

STYLE = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Calibri", "Carlito", "DejaVu Sans"],
    "font.size": 11,
    "axes.edgecolor": "#B9B9C4",
    "axes.linewidth": 0.8,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.frameon": False,
    "legend.fontsize": 10,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
}

CLK_PERIOD = 10


# ============================================================ simulation ===
def simulate_fifo(avail, depth, busy, ncycles, first_read_ok=1):
    """Cycle-by-cycle model of a producer, a bounded FIFO and a consumer.

    The rules are the ones fifo.xml's problems state, so one function serves the
    FIFO write-stall problem and the AXI4-Stream examples alike:

    * The producer offers element k from cycle avail[k] on, in order, and holds
      it (TVALID stays high) until it is written.
    * Registered backpressure: a write in cycle n is allowed only if the FIFO
      was not full at the *end* of cycle n-1 (TREADY in n = not full after n-1).
    * An element written in cycle n can be read in cycle n+first_read_ok at the
      earliest.  A read removes it from the FIFO in that cycle.
    * A read in cycle r keeps the consumer busy for cycles r+1 .. r+busy; its
      next read is at r+busy+1 at the earliest.

    Returns one dict per cycle.
    """
    names = [chr(ord("A") + k) for k in range(len(avail))]
    fifo, written = [], {}           # fifo holds names, oldest first
    nxt, free_at = 0, 0              # next element to write; consumer's next read
    busy_with, busy_until = None, -1
    full_prev = False
    rows = []
    for n in range(ncycles):
        tready = not full_prev
        # Producer
        offering = nxt < len(names) and avail[nxt] <= n
        if offering and tready:
            wr, wr_name = "transfer", names[nxt]
            fifo.append(names[nxt])
            written[names[nxt]] = n
            nxt += 1
        elif offering:
            wr, wr_name = "stall", names[nxt]
        else:
            wr, wr_name = "idle", None
        # Consumer: reads the head if it is old enough and the consumer is free
        if n >= free_at and fifo and written[fifo[0]] + first_read_ok <= n:
            got = fifo.pop(0)
            rd = f"read {got}"
            busy_with, busy_until = got, n + busy
            free_at = n + busy + 1
        elif busy_with is not None and n <= busy_until:
            rd = f"process {busy_with}"
        else:
            rd = "idle"
        full_prev = len(fifo) >= depth
        rows.append(dict(cycle=n, write=wr, elem=wr_name, tvalid=int(offering),
                         tready=int(tready), fifo=list(fifo), receiver=rd,
                         tready_next=int(not full_prev)))
    return rows


def self_check():
    """The simulator must reproduce the solutions published in fifo.xml."""
    # FIFO write stall: A-D available at 0-3, capacity 2, consumer busy 2 cycles.
    rows = simulate_fifo([0, 1, 2, 3], depth=2, busy=2, ncycles=13)
    got = [(r["write"], r["elem"], r["fifo"]) for r in rows[:6]]
    want = [("transfer", "A", ["A"]), ("transfer", "B", ["B"]),
            ("transfer", "C", ["B", "C"]), ("stall", "D", ["B", "C"]),
            ("stall", "D", ["C"]), ("transfer", "D", ["C", "D"])]
    assert got == want, f"FIFO write stall: {got}"
    assert [r["receiver"] for r in rows][10:13] == ["read D", "process D", "process D"]

    # AXI4-Stream timing with stalls: all at 0, depth 2, busy 1 cycle.
    rows = simulate_fifo([0, 0, 0, 0], depth=2, busy=1, ncycles=9)
    assert [r["tready"] for r in rows] == [1, 1, 1, 0, 1, 0, 1, 1, 1]
    assert [r["fifo"] for r in rows] == [["A"], ["B"], ["B", "C"], ["C"], ["C", "D"],
                                         ["D"], ["D"], [], []]
    assert [r["receiver"] for r in rows] == ["idle", "read A", "process A", "read B",
                                          "process B", "read C", "process C", "read D",
                                          "process D"]

    # AXI4-Stream timing (unbounded FIFO): A-C at 0, D at 6, busy 1 cycle.
    rows = simulate_fifo([0, 0, 0, 6], depth=99, busy=1, ncycles=9)
    assert [r["fifo"] for r in rows] == [["A"], ["B"], ["B", "C"], ["C"], ["C"], [],
                                         ["D"], [], []]


# ================================================================ drawing ===
def _level(name, times, values):
    return SigTimingInfo(name=name, times=times, values=values)


def _clock(ncyc):
    """A clock one cycle longer than the figure: waveflow's clock stops half a
    period early, so the last whole cycle needs the next rising edge.  Plot
    with trange=(0, p[ncyc])."""
    clk = ClkSig(clk_name="CLK", period=CLK_PERIOD, ncycles=ncyc + 1)
    return clk, clk.clk_periods()


def _per_cycle(name, p, values):
    """A signal that may change on every clock edge."""
    return _level(name, list(p[:len(values)]), [str(v) for v in values])


def _restyle(ax, td):
    """waveflow strokes waveforms in black; give them the deck's ink and weight,
    and quiet the clock grid."""
    for coll in ax.collections:
        if isinstance(coll, LineCollection):
            coll.set_color(INK)
            coll.set_linewidth(1.3)
    for line in ax.lines:                       # the clock grid
        line.set_color("#C9C9D2")
        line.set_linewidth(0.7)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)


def _cycle_axis(ax, p, ncycles):
    """Label the x axis in clock cycles, one tick at the middle of each."""
    ax.set_xticks([p[k] + CLK_PERIOD / 2 for k in range(ncycles)])
    ax.set_xticklabels([str(k) for k in range(ncycles)])
    ax.tick_params(axis="x", length=0)
    ax.set_xlabel("clock cycle")


def _legend(ax, entries, loc="center left", anchor=(1.01, 0.5)):
    ax.legend(handles=[Patch(label=lab, **kw) for lab, kw in entries],
              loc=loc, bbox_to_anchor=anchor, handlelength=1.6,
              borderpad=0.2, labelspacing=0.6)


def _shade(td, sig, p, cycles, kind):
    """Mark cycles on a data row: a transfer, or a wait."""
    for n in cycles:
        if kind == "transfer":
            td.add_patch(sig_name=sig, time=[p[n], p[n] + CLK_PERIOD],
                         facecolor=TEAL_FILL, edgecolor=TEAL, lw=1.0, zorder=0)
        else:
            td.add_patch(sig_name=sig, time=[p[n], p[n] + CLK_PERIOD],
                         facecolor="none", edgecolor=AMBER, hatch="///", lw=1.0, zorder=0)
            # waveflow writes the value before the patch exists; lift it above
            # the hatching on a white chip so the stalled element stays readable
            mid = p[n] + CLK_PERIOD / 2
            for txt in td.ax.texts:
                x, y = txt.get_position()
                if abs(x - mid) < 1e-6 and td.ybot[sig] < y < td.ytop[sig]:
                    txt.set_zorder(5)
                    txt.set_bbox(dict(facecolor="white", edgecolor="none", pad=2.5))


def _fifo_text(contents):
    return ",".join(contents) if contents else "–"


TRANSFER_KEY = ("transfer", dict(facecolor=TEAL_FILL, edgecolor=TEAL))
STALL_KEY = ("stall: waiting for TREADY", dict(facecolor="none", edgecolor=AMBER, hatch="///"))


# --------------------------------------------------------------- figures ---
def axis_stall(_):
    """The FIFO write-stall problem, drawn as AXI4-Stream signals."""
    ncyc = 10
    rows = simulate_fifo([0, 1, 2, 3], depth=2, busy=2, ncycles=ncyc)
    clk, p = _clock(ncyc)
    data = [r["elem"] if r["tvalid"] else "x" for r in rows]
    receiver = [r["receiver"].replace("process", "proc").replace("read", "rd") for r in rows]

    td = TimingDiagram(time_unit="cycle")
    td.add_signals([clk,
                    _per_cycle("TVALID", p, [r["tvalid"] for r in rows]),
                    _per_cycle("TREADY", p, [r["tready"] for r in rows]),
                    _per_cycle("TDATA", p, data),
                    _per_cycle("FIFO after cycle", p, [_fifo_text(r["fifo"]) for r in rows]),
                    _per_cycle("Receiver", p, receiver)])
    ax = td.plot_signals(fig_width=8, row_height=0.5, trange=(0, p[ncyc]))
    _shade(td, "TDATA", p, [r["cycle"] for r in rows if r["write"] == "transfer"], "transfer")
    _shade(td, "TDATA", p, [r["cycle"] for r in rows if r["write"] == "stall"], "stall")
    _restyle(ax, td)
    _cycle_axis(ax, p, ncyc)
    _legend(ax, [TRANSFER_KEY, STALL_KEY])
    return ax.figure


def _burst(ncyc, tready, tvalid, tlast, data):
    clk, p = _clock(ncyc)
    td = TimingDiagram(time_unit="cycle")
    td.add_signals([clk,
                    _per_cycle("TVALID", p, tvalid),
                    _per_cycle("TREADY", p, tready),
                    _per_cycle("TLAST", p, tlast),
                    _per_cycle("TDATA", p, data)])
    ax = td.plot_signals(fig_width=8, row_height=0.5, trange=(0, p[ncyc]))
    xfer = [n for n in range(ncyc) if tvalid[n] and tready[n]]
    stall = [n for n in range(ncyc) if tvalid[n] and not tready[n]]
    _shade(td, "TDATA", p, xfer, "transfer")
    _shade(td, "TDATA", p, stall, "stall")
    _restyle(ax, td)
    _cycle_axis(ax, p, ncyc)
    return ax, p, xfer


def burst_timing(_):
    """A four-element packet: two stalls, an idle beat, TLAST on D."""
    ax, p, _ = _burst(9,
                      tready=[0, 1, 0, 1, 1, 1, 0, 1, 1],
                      tvalid=[0, 1, 1, 1, 0, 1, 1, 1, 0],
                      tlast=[0, 0, 0, 0, 0, 0, 1, 1, 0],
                      data=["x", "A", "B", "B", "x", "C", "D", "D", "x"])
    beats = ["", "transfer", "stall", "transfer", "idle", "transfer", "stall", "last", ""]
    for n, b in enumerate(beats):
        if b:
            ax.text(p[n] + CLK_PERIOD / 2, ax.get_ylim()[1] + 0.12, b, ha="center",
                    va="bottom", fontsize=10, color=AMBER if b == "stall" else
                    (MUTED if b == "idle" else TEAL), clip_on=False)
    _legend(ax, [TRANSFER_KEY, STALL_KEY])
    return ax.figure


def tlast_solution(_):
    """The 'AXI4-Stream burst with TLAST' problem's table, as a waveform."""
    ax, p, xfer = _burst(6,
                         tready=[0, 1, 0, 1, 0, 1],
                         tvalid=[0, 1, 1, 1, 1, 1],
                         tlast=[0, 0, 0, 0, 1, 1],
                         data=["x", "1st", "2nd", "2nd", "3rd", "3rd"])
    assert xfer == [1, 3, 5]
    _legend(ax, [TRANSFER_KEY, STALL_KEY])
    return ax.figure


def time_wastage(_):
    """Where the time goes: a register interface against a FIFO interface."""
    fig, axes = plt.subplots(2, 1, figsize=(8.5, 3.6), sharex=True)
    lanes = {
        "Register interface": [
            ("Processor", [(0, 4, SLATE, "write"), (4, 8, "hatch", "poll"), (12, 3, SLATE, "read"),
                           (15, 4, SLATE, "write"), (19, 8, "hatch", "poll"),
                           (27, 3, SLATE, "read")]),
            ("IP", [(0, 4, None, "idle"), (4, 8, VIOLET, "job 1"), (12, 7, None, "idle"),
                    (19, 8, VIOLET, "job 2"), (27, 3, None, "idle")]),
        ],
        "FIFO interface": [
            ("Processor", [(0, 3, SLATE, "push 1–3"), (3, 21, "free", "free for other work"),
                           (24, 6, SLATE, "pop responses")]),
            ("IP", [(0, 1, None, ""), (1, 8, VIOLET, "job 1"), (9, 8, VIOLET, "job 2"),
                    (17, 8, VIOLET, "job 3"), (25, 5, None, "idle")]),
        ],
    }
    for ax, (title, rows) in zip(axes, lanes.items()):
        for k, (lane, segs) in enumerate(rows):
            y = 1 - k
            for x0, w, kind, text in segs:
                if kind == "hatch":
                    ax.broken_barh([(x0, w)], (y - 0.32, 0.64), facecolors="white",
                                   edgecolors=AMBER, hatch="///", linewidth=1.0)
                    colour = AMBER
                elif kind == "free":
                    ax.broken_barh([(x0, w)], (y - 0.32, 0.64), facecolors=SLATE_FILL,
                                   edgecolors=SLATE_FILL, linewidth=1.0)
                    colour = SLATE
                elif kind is None:
                    ax.broken_barh([(x0, w)], (y - 0.32, 0.64), facecolors=IDLE,
                                   edgecolors=IDLE, linewidth=1.0)
                    colour = MUTED
                else:
                    ax.broken_barh([(x0, w)], (y - 0.32, 0.64), facecolors=kind,
                                   edgecolors="white", linewidth=1.5)
                    colour = "white"
                if text:
                    ax.text(x0 + w / 2, y, text, ha="center", va="center", fontsize=10,
                            color=colour, fontweight="bold" if colour == "white" else None,
                            bbox=dict(facecolor="white", edgecolor="none", pad=3.5)
                            if kind == "hatch" else None)
        ax.set_yticks([1, 0])
        ax.set_yticklabels([r[0] for r in rows], fontsize=11, color=INK)
        ax.tick_params(axis="y", length=0)
        ax.set_ylim(-0.6, 1.6)
        ax.set_title(title, loc="left", fontsize=12, fontweight="bold",
                     color=VIOLET if title.startswith("FIFO") else SLATE)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
    axes[1].set_xlim(0, 30)
    axes[1].set_xticks([])
    axes[1].set_xlabel("time →")
    fig.tight_layout(h_pad=1.2)
    return fig


def _queue_walk(p_arr, p_srv, n, rng):
    """Backlog of an unbounded FIFO: a Bernoulli arrival and a Bernoulli
    departure (if anything is waiting) each cycle."""
    q, out = 0, np.empty(n, dtype=int)
    a = rng.random(n) < p_arr
    s = rng.random(n) < p_srv
    for k in range(n):
        q = max(q + int(a[k]) - int(s[k] and q > 0), 0)
        out[k] = q
    return out


def load_factor(_):
    """Backlog over time at three load factors, with the same random seed."""
    n, p_srv = 4000, 0.5
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    for rho, colour, name in ((0.8, TEAL, "ρ = 0.8   stable"),
                              (1.0, SLATE, "ρ = 1.0   critical"),
                              (1.2, AMBER, "ρ = 1.2   unstable")):
        q = _queue_walk(rho * p_srv, p_srv, n, np.random.default_rng(7))
        ax.plot(np.arange(n), q, color=colour, lw=1.4)
        ax.text(n * 1.01, q[-1], name, color=colour, va="center", fontsize=11,
                fontweight="bold")
    ax.set_xlim(0, n)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("clock cycle")
    ax.set_ylabel("elements in the FIFO")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    return fig


# The accelerator problem: a frame every 20 ms, 5 ms of work, or 105 ms on 10%.
FRAME_MS, CHEAP_MS, DEAR_MS, NFRAMES = 20, 5, 105, 300


def frame_patterns(seed=11):
    k = np.arange(NFRAMES)
    uniform = k % 10 == 0
    bursty = (k % 100) < 10
    random = np.random.default_rng(seed).random(NFRAMES) < 0.10
    return {"(i) uniform": uniform, "(iii) random": random, "(ii) bursty": bursty}


def frame_backlog_series(dear):
    """Frames waiting in the input FIFO (not counting the one in service),
    sampled every millisecond."""
    arrive = np.arange(NFRAMES) * FRAME_MS
    start = np.empty(NFRAMES)
    t_free = 0.0
    for k in range(NFRAMES):
        start[k] = max(arrive[k], t_free)
        t_free = start[k] + (DEAR_MS if dear[k] else CHEAP_MS)
    t = np.arange(0, NFRAMES * FRAME_MS)
    waiting = (np.searchsorted(arrive, t, side="right")
               - np.searchsorted(start, t, side="right"))
    return t, waiting


def frame_backlog(_):
    """Solution figure for 'Accelerator throughput and FIFO depth' (b)."""
    pats = frame_patterns()
    fig, axes = plt.subplots(3, 1, figsize=(6.4, 4.4), sharex=True)
    colours = {"(i) uniform": TEAL, "(iii) random": SLATE, "(ii) bursty": AMBER}
    for ax, (name, dear) in zip(axes, pats.items()):
        t, w = frame_backlog_series(dear)
        ax.fill_between(t / 1000, w, step="post", color=colours[name], alpha=0.25, lw=0)
        ax.step(t / 1000, w, where="post", color=colours[name], lw=1.1)
        ax.text(0.995, 0.93, f"{name}:  peak {w.max()} frames", transform=ax.transAxes,
                ha="right", va="top", fontsize=11, color=colours[name], fontweight="bold")
        ax.set_ylim(0, 50)
        ax.set_yticks([0, 25, 50])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[1].set_ylabel("frames waiting")
    axes[-1].set_xlabel("time [s]")
    axes[-1].set_xlim(0, NFRAMES * FRAME_MS / 1000)
    fig.tight_layout(h_pad=0.4)
    return fig


FIGURES = {
    "axis_stall": axis_stall,
    "burst_timing": burst_timing,
    "tlast_solution": tlast_solution,
    "time_wastage": time_wastage,
    "load_factor": load_factor,
    "frame_backlog": frame_backlog,
}


# ----------------------------------------------------------------- output ---
def render(name, out_dir):
    """Write one figure and return its path."""
    with plt.rc_context(STYLE):
        fig = FIGURES[name](None)
        path = out_dir / f"{name}.png"
        # Software and Date are the only non-deterministic chunks matplotlib
        # writes; None drops the key rather than writing an empty one.
        fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.06,
                    metadata={"Software": None, "Date": None})
        plt.close(fig)
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE, help="where the PNGs are written")
    ap.add_argument("--only", action="append", choices=sorted(FIGURES),
                    help="render one figure (repeatable)")
    ap.add_argument("--check", action="store_true",
                    help="render to a temp directory and compare; exit 1 if any file differs")
    args = ap.parse_args()
    names = args.only or sorted(FIGURES)
    self_check()

    if args.check:
        stale = []
        with tempfile.TemporaryDirectory() as tmp:
            for name in names:
                fresh = render(name, Path(tmp))
                tracked = args.out / f"{name}.png"
                if not tracked.exists():
                    stale.append(f"{name}: missing")
                elif digest(tracked) != digest(fresh):
                    stale.append(f"{name}: {digest(tracked)} -> {digest(fresh)}")
        for s in stale:
            print("stale:", s)
        print(f"{len(names) - len(stale)}/{len(names)} figures up to date")
        return 1 if stale else 0

    args.out.mkdir(parents=True, exist_ok=True)
    for name in names:
        path = render(name, args.out)
        print(f"{path.name:24s} {digest(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
