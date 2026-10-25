"""Generate unit 6's figures.

Replaces timing_figs.ipynb, for the reason units 4 and 5 give: a notebook
re-serialises its outputs on every run, so the tracked file changed whether or
not a figure did.  This script writes only the PNGs.

    python make_figs.py                 # every figure: waveforms and block diagrams
    python make_figs.py --only series_s2
    python make_figs.py --no-blocks     # skip the TikZ block diagrams

Two sources:

  * the waveforms are drawn here with waveflow's TimingDiagram.  The unknown
    intervals are not typed in: each is computed from the block delays by
    `settle`, and the three problems' figures are checked against the
    solutions published in timing.xml before anything is drawn.
  * the block diagrams are block_figs.tex, one tikzpicture per page,
    compiled with pdflatex and split into one PNG per page at 300 dpi.

Run it with the interpreter that has waveflow (hwdesign-venv), as for units 4
and 5.  The block diagrams also need pdflatex and pdftocairo (MiKTeX has both).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")                     # no display, and identical on any machine
import matplotlib.pyplot as plt           # noqa: E402
import numpy as np                        # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402

try:
    from waveflow.utils.timing import ClkSig, SigTimingInfo, TimingDiagram  # noqa: E402
except ModuleNotFoundError as exc:      # the usual cause: the wrong interpreter
    raise SystemExit(
        f"{exc}. waveflow lives in the pysilicon repo and is installed in hwdesign-venv, "
        "not in chat-env. Run this with, for example:\n"
        "  ../../../../hwdesign-venv/Scripts/python make_figs.py") from exc

HERE = Path(__file__).resolve().parent

# The deck's palette (tools/build_timing_slides.py, shared with units 4 and 5).
INK = "#262626"
VIOLET = "#57068C"
TEAL = "#00857C"
TEAL_FILL = "#CFE9E5"
SLATE = "#2F6FA8"
AMBER = "#B4530F"
MUTED = "#6E6E6E"
UNKNOWN = "#D9D9DE"                       # the X / ? regions

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
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
}

DPI = 250


# ================================================================= model ===
def _merge(points):
    """Drop repeats: two 'x' in a row is one unknown interval."""
    out = []
    for t, v in points:
        if out and out[-1][1] == v:
            continue
        out.append((t, v))
    return out


def combine(sig_a, sig_b, fn, delay):
    """The value-change points of a two-input block's output.

    Signals are [(t, value), ...], with 'x' for unknown.  The output goes
    unknown the moment either input changes, and settles `delay` after the
    later of the two is stable again: the maximum-propagation-delay rule the
    unit teaches.  A signal's first value is taken as stable long before.
    """
    times = sorted({t for t, _ in sig_a} | {t for t, _ in sig_b})

    def at(sig, t):
        v = sig[0][1]
        for tt, vv in sig:
            if tt <= t:
                v = vv
        return v

    pts = []
    for t in times:
        va, vb = at(sig_a, t), at(sig_b, t)
        if va == "x" or vb == "x":
            pts.append((t, "x"))
        else:
            pts.append((t, str(fn(int(va), int(vb)))))
    # each stable value takes `delay` to appear after its inputs settle; a
    # change straight from one value to another passes through unknown
    out = []
    for k, (t, v) in enumerate(pts):
        if v == "x" or k == 0:
            out.append((t, v))
        else:
            if pts[k - 1][1] != "x":
                out.append((t, "x"))
            out.append((t + delay, v))
    return _merge(out)


def unary(sig, fn, delay):
    return combine(sig, [(sig[0][0], "0")], lambda a, _b: fn(a), delay)


def self_check():
    """The model must reproduce the solutions published in timing.xml."""
    # Propagation delay: x unknown before 10, then 0, 4, 2; y = 2x+1, 3 ns.
    x = [(0, "x"), (10, "0"), (20, "4"), (30, "2")]
    y = unary(x, lambda v: 2 * v + 1, 3)
    assert y == [(0, "x"), (13, "1"), (20, "x"), (23, "9"), (30, "x"), (33, "5")], y

    # Series timing: x = 0 then 4 at 10; mult 3 ns, add 2 ns; a=3, b=6.
    x = [(0, "0"), (10, "4")]
    xsq = combine(x, x, lambda a, b: a * b, 3)
    yy = unary(xsq, lambda v: 3 * v, 3)
    z = unary(yy, lambda v: v + 6, 2)
    assert xsq == [(0, "0"), (10, "x"), (13, "16")], xsq
    assert yy == [(0, "0"), (10, "x"), (16, "48")], yy
    assert z == [(0, "6"), (10, "x"), (18, "54")], z

    # Multi-path timing: x = 0, unknown 10-12, then 4; z1 = 3x (3 ns),
    # z2 = x + 6 (2 ns), y = max (1 ns).  Stable at 15, 14 and 16.
    x = [(0, "0"), (10, "x"), (12, "4")]
    z1 = unary(x, lambda v: 3 * v, 3)
    z2 = unary(x, lambda v: v + 6, 2)
    ym = combine(z1, z2, max, 1)
    assert z1 == [(0, "0"), (10, "x"), (15, "12")], z1
    assert z2 == [(0, "6"), (10, "x"), (14, "10")], z2
    assert ym == [(0, "6"), (10, "x"), (16, "12")], ym


# ================================================================ drawing ===
def sig(name, points):
    """A waveflow signal from [(t, value), ...]; an empty list is a blank row."""
    return SigTimingInfo(name=name, times=[t for t, _ in points],
                         values=[str(v) for _, v in points])


def restyle(ax):
    """waveflow strokes in black and fills unknowns light grey: give them the
    deck's ink, weight and unknown tint, and quiet the frame."""
    for coll in ax.collections:
        if isinstance(coll, LineCollection):
            coll.set_color(INK)
            coll.set_linewidth(1.2)
        elif isinstance(coll, PolyCollection):
            coll.set_facecolor(UNKNOWN)
    for line in ax.lines:                       # the clock grid
        line.set_color("#C9C9D2")
        line.set_linewidth(0.7)
    for txt in ax.texts:
        txt.set_fontsize(11)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)


def diagram(rows, trange, *, width=8.0, row_height=0.5, clock=None, xlabel="time [ns]",
            ticks=None, ax=None):
    """Draw [(name, points), ...] and return (ax, td)."""
    td = TimingDiagram(time_unit="ns")
    sigs = []
    if clock is not None:
        period, ncycles = clock
        sigs.append(ClkSig(clk_name="clk", period=period, ncycles=ncycles))
    sigs += [sig(n, p) for n, p in rows]
    td.add_signals(sigs)
    ax = td.plot_signals(fig_width=width, row_height=row_height, trange=trange,
                         add_clk_grid=clock is not None, ax=ax)
    restyle(ax)
    ax.set_xlabel(xlabel)
    if ticks is not None:
        ax.set_xticks(ticks)
    return ax, td


def mark_interval(ax, td, name, t0, t1, text=None, color=VIOLET):
    """Write an unknown interval's bounds inside it."""
    y = (td.ytop[name] + td.ybot[name]) / 2
    ax.text((t0 + t1) / 2, y, text or f"[{t0:g}, {t1:g}]", ha="center", va="center",
            fontsize=10.5, color=color, fontweight="bold", zorder=6)


def bracket(ax, t0, t1, y, text, color=VIOLET, where="below"):
    """A dimension line between two times, labelled below it, or beside it
    ("left", "right") when the span is too short for the text."""
    ax.annotate("", xy=(t1, y), xytext=(t0, y), annotation_clip=False,
                arrowprops=dict(arrowstyle="<->", color=color, lw=1.3,
                                shrinkA=0, shrinkB=0))
    kw = dict(color=color, fontsize=11, fontweight="bold")
    if where == "left":
        ax.text(t0 - 0.25, y, text, ha="right", va="center", **kw)
    elif where == "right":
        ax.text(t1 + 0.25, y, text, ha="left", va="center", **kw)
    else:
        ax.text((t0 + t1) / 2, y - 0.12, text, ha="center", va="top", **kw)


def guides(ax, times, y0, y1, color=MUTED):
    for t in times:
        ax.plot([t, t], [y0, y1], color=color, lw=0.8, ls=(0, (3, 2)), zorder=1,
                clip_on=False)


def extend_below(ax, td, depth):
    """Room under the rows for brackets: waveflow sets ylim to the rows."""
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo - depth, hi)
    ax.figure.set_size_inches(ax.figure.get_size_inches()[0],
                              ax.figure.get_size_inches()[1] * (hi - lo + depth) / (hi - lo))


# -------------------------------------------------------------- section 1 ---
def analog_levels(_):
    """A noisy wire voltage, and the bands that read it as 0, 1 or undefined."""
    t = np.linspace(0, 10, 600)
    rng = np.random.default_rng(4)
    v = 0.1 + 0.8 / (1 + np.exp(-(t - 3.5) * 6)) - 0.8 / (1 + np.exp(-(t - 7.2) * 6))
    v = v + 0.025 * np.convolve(rng.standard_normal(t.size), np.ones(9) / 3, "same")
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    ax.axhspan(0.8, 1.05, color=TEAL_FILL, lw=0)
    ax.axhspan(0.2, 0.8, color="#F3F3F6", lw=0)
    ax.axhspan(-0.05, 0.2, color="#F6E3D3", lw=0)
    ax.plot(t, v, color=INK, lw=1.4)
    for y, txt, c in ((0.92, "logic 1", TEAL), (0.5, "undefined", MUTED), (0.07, "logic 0", AMBER)):
        ax.text(10.15, y, txt, va="center", fontsize=11, color=c, fontweight="bold")
    ax.set_yticks([0.2, 0.8, 1.0])
    ax.set_yticklabels(["20% Vdd", "80% Vdd", "Vdd"])
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlim(0, 10)
    ax.set_xticks([])
    ax.set_xlabel("time")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    return fig


def rise_fall(_):
    """A pulse with finite rise and fall times, and the logic values it reads as."""
    tp = [0, 2, 3, 6, 7, 9]
    vp = [0, 0, 1, 1, 0, 0]
    fig, ax = plt.subplots(figsize=(5.4, 3.0))
    ax.plot(tp, vp, color=INK, lw=1.6)
    for y in (0.1, 0.9):
        ax.axhline(y, color=MUTED, lw=0.8, ls=(0, (3, 2)))
        ax.text(9.15, y, f"{int(y * 100)}%", va="center", fontsize=10, color=MUTED)
    for a, b, txt in ((2.1, 2.9, "rise time"), (6.1, 6.9, "fall time")):
        ax.axvspan(a, b, color=UNKNOWN, lw=0)
        ax.annotate("", xy=(b, -0.12), xytext=(a, -0.12), annotation_clip=False,
                    arrowprops=dict(arrowstyle="<->", color=VIOLET, lw=1.2, shrinkA=0, shrinkB=0))
        ax.text((a + b) / 2, -0.2, txt, ha="center", va="top", fontsize=10, color=VIOLET)
    for x, txt, c in ((1.0, "0", INK), (2.5, "X", AMBER), (4.5, "1", INK), (6.5, "X", AMBER),
                      (8.0, "0", INK)):
        ax.text(x, -0.48, txt, ha="center", va="center", fontsize=15, color=c, fontweight="bold")
    ax.set_xlim(0, 9)
    ax.set_ylim(-0.6, 1.1)
    ax.axis("off")
    return fig


def analog_digital(_):
    """An analog signal, thresholded at 20% and 80%, and the 0 / 1 / X signal."""
    period, nper, nt = 10, 3, 1200
    t = np.linspace(0, period * nper, nt)
    x = 0.5 + 0.5 * np.maximum(np.minimum(1.5 * np.sin(2 * np.pi * t / period), 1), -1)
    lo, hi = 0.2, 0.8
    vals = np.where(x < lo, "0", np.where(x > hi, "1", "x"))
    pts = [(t[0], vals[0])]
    for k in range(1, nt):
        if vals[k] != vals[k - 1]:
            pts.append((t[k], vals[k]))
    fig, axes = plt.subplots(2, 1, figsize=(6.4, 3.6), gridspec_kw=dict(height_ratios=[2.2, 1]))
    ax = axes[0]
    ax.plot(t, x, color=SLATE, lw=1.5)
    for y in (lo, hi):
        ax.axhline(y, color=AMBER, lw=0.9, ls=(0, (4, 3)))
    for tt, _ in pts[1:]:
        ax.axvline(tt, color="#C9C9D2", lw=0.6)
    ax.set_xlim(0, 30)
    ax.set_ylim(-0.05, 1.08)
    ax.set_yticks([0, lo, hi, 1])
    ax.set_xticks([])
    ax.set_title("analog signal, with thresholds", loc="left", fontsize=11, color=SLATE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    diagram([("x", pts)], (0, 30), ax=axes[1])
    axes[1].set_title("digital signal: 0, 1 and X", loc="left", fontsize=11, color=INK)
    fig.tight_layout(h_pad=0.6)
    return fig


def stable_prop(_):
    """y = x^2: x goes from 4 to 5 at t = 10, and y settles 3 ns later."""
    x = [(-5, "4"), (10, "5")]
    y = unary(x, lambda v: v * v, 3)
    ax, td = diagram([("x", x), ("y", y)], (-5, 20), width=6.4, row_height=0.55)
    extend_below(ax, td, 0.7)
    guides(ax, [10, 13], -0.25, td.ytop["x"])
    bracket(ax, 10, 13, -0.3, "$T_{prop}$ = 3 ns")
    return ax.figure


def max_delay(_):
    """The same transition through many instances: the delay varies, and the
    timing diagram shows the worst case."""
    rng = np.random.default_rng(2)
    dly = rng.uniform(0, 5.5, size=10)
    t = np.linspace(-3, 20, 500)
    dt = np.maximum(0, t[:, None] - dly[None, :])
    v = 1 - np.exp(-(dt / 2.0) ** 2)
    fig, axes = plt.subplots(2, 1, figsize=(6.4, 3.8), sharex=True,
                             gridspec_kw=dict(height_ratios=[2.2, 1]))
    ax = axes[0]
    ax.plot(t, v, color=SLATE, lw=0.9, alpha=0.75)
    for y in (0.2, 0.8):
        ax.axhline(y, color=AMBER, lw=0.9, ls=(0, (4, 3)))
    ax.set_ylim(-0.05, 1.08)
    ax.set_yticks([0, 0.2, 0.8, 1])
    ax.set_title("the same transition, ten circuit instances", loc="left", fontsize=11, color=SLATE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    worst = float(np.ceil(t[np.argmax(v.min(axis=1) > 0.8)]))
    _, td = diagram([("x", [(-3, "0"), (0, "x"), (worst, "1")])], (-3, 20), ax=axes[1])
    axes[1].set_title(f"timing diagram: unknown until the worst case, {worst:g} ns",
                      loc="left", fontsize=11, color=INK)
    for a in axes:
        a.axvline(0, color=MUTED, lw=0.8, ls=(0, (3, 2)))
        a.axvline(worst, color=MUTED, lw=0.8, ls=(0, (3, 2)))
    fig.tight_layout(h_pad=0.6)
    return fig


# Linear + ReLU: y = max(a*x + b, 0), mult 3 ns, add 1.5 ns, max 1 ns, inputs
# in transition for 2 ns after each change.
T_IN, T_MULT, T_ADD, T_MAX = 2, 3, 1.5, 1


def relu_signals(changes):
    """x, a, b change together at each (t, x, a, b); return every signal."""
    def inp(k):
        pts = []
        for t, *vals in changes:
            pts += [(t, "x"), (t + T_IN, str(vals[k]))]
        return _merge(pts)
    x, a, b = inp(0), inp(1), inp(2)
    mult = combine(x, a, lambda p, q: p * q, T_MULT)
    add = combine(mult, b, lambda p, q: p + q, T_ADD)
    y = unary(add, lambda p: max(p, 0), T_MAX)
    return [("x", x), ("a", a), ("b", b), ("mult_out", mult), ("add_out", add), ("y", y)]


def series_step(k):
    """Slides 12-15: the single change at t = 0, revealed one block at a time."""
    def fig(_):
        rows = relu_signals([(0, 10, 3, 15)])
        shown = [(n, p if i < 3 + k else []) for i, (n, p) in enumerate(rows)]
        ax, td = diagram(shown, (0, 10), width=6.6, row_height=0.5, ticks=range(0, 11, 2))
        ends = {"x": 2, "mult_out": 5, "add_out": 6.5, "y": 7.5}
        for n, _ in rows[:3 + k]:
            if n in ends:
                mark_interval(ax, td, n, 0, ends[n])
        return ax.figure
    return fig


def series_total(_):
    rows = relu_signals([(0, 10, 3, 15)])
    ax, td = diagram(rows, (0, 10), width=6.6, row_height=0.5, ticks=range(0, 11, 2))
    extend_below(ax, td, 1.5)
    guides(ax, [2, 5, 6.5, 7.5], -0.95, td.ytop["x"])
    bracket(ax, 2, 5, -0.25, "$T_{mult}$")
    bracket(ax, 5, 6.5, -0.25, "$T_{add}$")
    bracket(ax, 6.5, 7.5, -0.25, "$T_{max}$")
    bracket(ax, 2, 7.5, -0.95, "$T_{tot}$ = 5.5 ns", color=TEAL)
    return ax.figure


def series_multi(_):
    rows = relu_signals([(0, 10, 3, 15), (10, -4, 10, 4), (20, 8, 12, -5)])
    ax, _ = diagram(rows, (0, 30), width=8.6, row_height=0.5)
    return ax.figure


def multipath_rows():
    x = [(5, "0"), (10, "x"), (12, "4")]
    r = unary(x, lambda v: max(v, 0), 1)
    xsq = combine(x, x, lambda p, q: p * q, 3)
    y = combine(xsq, r, lambda p, q: p + q, 1.5)
    return [("x", x), ("r", r), ("xsq", xsq), ("y", y)]


def multipath_step(k):
    """Slides 22-24: the input, then r and xsq, then y."""
    def fig(_):
        rows = multipath_rows()
        n_shown = {0: 1, 1: 3, 2: 4}[k]
        shown = [(n, p if i < n_shown else []) for i, (n, p) in enumerate(rows)]
        ax, td = diagram(shown, (5, 20), width=6.6, row_height=0.5)
        ends = {"x": 12, "r": 13, "xsq": 15, "y": 16.5}
        for n, _ in rows[:n_shown]:
            mark_interval(ax, td, n, 10, ends[n])
        return ax.figure
    return fig


# ------------------------------------------------------- problem solutions ---
def q_propagation(_):
    x = [(0, "x"), (10, "0"), (20, "4"), (30, "2")]
    y = unary(x, lambda v: 2 * v + 1, 3)
    ax, td = diagram([("x", x), ("y", y)], (0, 40), width=7.6, row_height=0.55)
    for t in (10, 20, 30):
        mark_interval(ax, td, "y", t, t + 3, "?")
    return ax.figure


def q_series(_):
    x = [(0, "0"), (10, "4")]
    xsq = combine(x, x, lambda a, b: a * b, 3)
    yy = unary(xsq, lambda v: 3 * v, 3)
    z = unary(yy, lambda v: v + 6, 2)
    ax, td = diagram([("x", x), ("xsq", xsq), ("y", yy), ("z", z)], (5, 22), width=6.4,
                     row_height=0.5)
    for n, t1 in (("xsq", 13), ("y", 16), ("z", 18)):
        mark_interval(ax, td, n, 10, t1)
    return ax.figure


def q_multipath(_):
    x = [(0, "0"), (10, "x"), (12, "4")]
    z1 = unary(x, lambda v: 3 * v, 3)
    z2 = unary(x, lambda v: v + 6, 2)
    y = combine(z1, z2, max, 1)
    ax, td = diagram([("x", x), ("z1", z1), ("z2", z2), ("y", y)], (5, 20), width=6.4,
                     row_height=0.5)
    for n, t1 in (("x", 12), ("z1", 15), ("z2", 14), ("y", 16)):
        mark_interval(ax, td, n, 10, t1)
    return ax.figure


# -------------------------------------------------------------- section 2 ---
def _register_rows():
    """A register with a 10 ns clock: D settles before the edge at 10, Q
    follows 1 ns after it."""
    d = [(0, "0"), (2, "x"), (4, "1"), (15, "x"), (17, "2")]
    q = [(0, "0"), (10, "x"), (11, "1")]
    return [("D", d), ("Q", q)]


def setup_hold(_):
    ax, td = diagram(_register_rows(), (0, 20), width=6.4, row_height=0.55, clock=(10, 2),
                     ticks=range(0, 21, 5))
    extend_below(ax, td, 1.3)
    guides(ax, [4, 10, 15], -0.3, td.ytop["D"])
    bracket(ax, 4, 10, -0.3, "setup margin", color=TEAL)
    bracket(ax, 10, 15, -0.3, "hold margin", color=SLATE)
    td.add_patch("D", time=[8.5, 10], facecolor="none", edgecolor=TEAL, hatch="///", lw=1.0)
    td.add_patch("D", time=[10, 11], facecolor="none", edgecolor=SLATE, hatch="\\\\\\", lw=1.0)
    # the value sits under the hatching at the edge; move it into the clear part
    yd = (td.ytop["D"] + td.ybot["D"]) / 2
    for txt in ax.texts:
        if txt.get_text() == "1" and abs(txt.get_position()[1] - yd) < 1e-6:
            txt.set_position((6.2, yd))
    ax.text(9.9, -0.95, "min set-up time", ha="right", va="top", fontsize=10, color=TEAL)
    ax.text(10.1, -0.95, "min hold time", ha="left", va="top", fontsize=10, color=SLATE)
    return ax.figure


def clk_to_q(_):
    ax, td = diagram(_register_rows(), (0, 20), width=6.4, row_height=0.55, clock=(10, 2),
                     ticks=range(0, 21, 5))
    extend_below(ax, td, 0.7)
    guides(ax, [10, 11], -0.3, td.ytop["D"])
    bracket(ax, 10, 11, -0.3, "")
    ax.text(11.4, -0.3, "clock-to-Q time", va="center", fontsize=11, color=VIOLET,
            fontweight="bold")
    return ax.figure


# Counter x <- x + 1: clock-to-Q 2 ns, adder 3 ns, 10 ns clock.
def counter_rows():
    x = [(0, "x"), (2, "0"), (10, "x"), (12, "1"), (20, "x"), (22, "2")]
    xnext = unary(x, lambda v: v + 1, 3)
    return [("x", x), ("xnext", xnext)]


def counter_detailed(_):
    ax, td = diagram(counter_rows(), (0, 30), width=7.0, row_height=0.55, clock=(10, 3),
                     ticks=range(0, 31, 5))
    extend_below(ax, td, 1.4)
    guides(ax, [10, 12, 15], -0.95, td.ytop["x"])
    bracket(ax, 10, 12, -0.3, "$T_{clk\\text{-}Q}$", color=SLATE, where="left")
    bracket(ax, 12, 15, -0.95, "$T_{PD}$", color=TEAL, where="right")
    return ax.figure


def counter_abstract(_):
    fig, axes = plt.subplots(2, 1, figsize=(6.4, 3.9),
                             gridspec_kw=dict(height_ratios=[1, 1], hspace=0.9))
    diagram(counter_rows(), (0, 30), clock=(10, 3), ticks=range(0, 31, 10), ax=axes[0])
    axes[0].set_title("detailed: every delay", loc="left", fontsize=11, color=SLATE)
    abstract = [("x", [(0, "0"), (10, "1"), (20, "2")]),
                ("xnext", [(0, "1"), (10, "2"), (20, "3")])]
    diagram(abstract, (0, 30), clock=(10, 3), ticks=range(0, 31, 10), ax=axes[1])
    axes[1].set_title("abstract, or cycle-accurate: delays → 0", loc="left", fontsize=11,
                      color=VIOLET)
    return fig


# -------------------------------------------------------------- section 3 ---
def relu_sync_rows():
    """Registered x, a, b (0 ns register) into mult 3 ns, add 1.5, max 1."""
    def inp(vals):
        pts = [(0, "x")]
        for k, v in enumerate(vals):
            pts += [(4 + 10 * k, "x"), (6 + 10 * k, str(v))]
        return _merge(pts)

    def reg(vals):
        return [(0, "x")] + [(10 + 10 * k, str(v)) for k, v in enumerate(vals)]
    X, A, B = [10, -4, 8], [3, 10, 12], [15, 4, -5]
    xr, ar, br = reg(X), reg(A), reg(B)
    mult = combine(xr, ar, lambda p, q: p * q, T_MULT)
    add = combine(mult, br, lambda p, q: p + q, T_ADD)
    y = unary(add, lambda p: max(p, 0), T_MAX)
    return [("x", inp(X)), ("a", inp(A)), ("b", inp(B)), ("xreg", xr), ("areg", ar),
            ("breg", br), ("mult_out", mult), ("add_out", add), ("y", y)]


def relu_sync(_):
    ax, td = diagram(relu_sync_rows(), (0, 40), width=7.4, row_height=0.42, clock=(10, 4),
                     ticks=range(0, 41, 10))
    extend_below(ax, td, 1.5)
    guides(ax, [10, 15.5, 20], -0.95, td.ytop["xreg"])
    bracket(ax, 10, 15.5, -0.3, "$T_{crit}$ = 5.5 ns", color=AMBER, where="right")
    bracket(ax, 10, 20, -0.95, "$T_{clk}$ = 10 ns", color=SLATE)
    return ax.figure


# Two-cycle quadratic: register 1 ns, mult 4 ns, add 1.5 ns; w0, w1, w2 = 4, -7, 5.
W0, W1, W2 = 4, -7, 5
T_REG, T_QMULT, T_QADD = 1, 4, 1.5


def two_cycle_rows():
    X = [10, -4, 8]
    x = [(0, "x")]
    for k, v in enumerate(X):
        x += [(4 + 10 * k, "x"), (6 + 10 * k, str(v))]
    x = _merge(x)
    xreg = _merge([(0, "x")] + sum([[(10 * (k + 1), "x"), (10 * (k + 1) + T_REG, str(v))]
                                    for k, v in enumerate(X)], []))
    xsq_in = combine(xreg, xreg, lambda p, q: p * q, T_QMULT)
    lin_in = unary(unary(xreg, lambda p: W1 * p, T_QMULT), lambda p: p + W0, T_QADD)

    def registered(src):
        """The value each rising edge captures, out 1 ns later."""
        out = [(0, "x")]
        for edge in range(10, 60, 10):
            v = "x"
            for t, vv in src:
                if t <= edge - 1e-9:
                    v = vv
            if v != "x":
                out += [(edge, "x"), (edge + T_REG, v)]
        return _merge(out)
    xsq, lin = registered(xsq_in), registered(lin_in)
    y = combine(unary(xsq, lambda p: W2 * p, T_QMULT), lin, lambda p, q: p + q, T_QADD)
    rows = [("x", x), ("xreg", xreg), ("xsq input", xsq_in), ("xsq", xsq),
            ("lin_term input", lin_in), ("lin_term", lin), ("y", y)]
    finals = [v for _, v in y if v != "x"]
    assert finals[:3] == ["434", "112", "268"], finals
    return rows


def two_cycle(_):
    ax, _ = diagram(two_cycle_rows(), (0, 50), width=8.2, row_height=0.42, clock=(10, 5),
                    ticks=range(0, 51, 10))
    return ax.figure


def pipeline(_):
    ax, td = diagram(two_cycle_rows(), (0, 40), width=7.0, row_height=0.42, clock=(10, 4),
                     ticks=range(0, 41, 10))
    yx = (td.ytop["x"] + td.ybot["x"]) / 2
    yy = (td.ytop["y"] + td.ybot["y"]) / 2
    ax.annotate("", xy=(28.5, yy + 0.2), xytext=(9, yx - 0.2),
                arrowprops=dict(arrowstyle="->", color=AMBER, lw=1.8))
    ax.text(40, td.ytop["clk"] + 0.25, "x = 10 is captured at the edge at 10 ns;  y = 434 "
            "is ready before the edge at 30 ns: 2 cycles", color=AMBER, fontsize=11,
            fontweight="bold", ha="right", va="bottom")
    return ax.figure


# -------------------------------------------------------------- section 4 ---
def vcd_example(_):
    x = [(0, "x"), (3, "5"), (20, "17"), (40, "8")]
    y = [(0, "x"), (12, "3"), (25, "12"), (35, "0")]
    ax, _ = diagram([("x", x), ("y", y)], (0, 50), width=8.0, row_height=0.55)
    return ax.figure


WAVEFORMS = {
    "analog_levels": analog_levels,
    "rise_fall": rise_fall,
    "analog_digital": analog_digital,
    "stable_prop": stable_prop,
    "max_delay": max_delay,
    "series_s0": series_step(0),
    "series_s1": series_step(1),
    "series_s2": series_step(2),
    "series_s3": series_step(3),
    "series_total": series_total,
    "series_multi": series_multi,
    "multipath_t0": multipath_step(0),
    "multipath_t1": multipath_step(1),
    "multipath_t2": multipath_step(2),
    "q_propagation": q_propagation,
    "q_series": q_series,
    "q_multipath": q_multipath,
    "setup_hold": setup_hold,
    "clk_to_q": clk_to_q,
    "counter_detailed": counter_detailed,
    "counter_abstract": counter_abstract,
    "relu_sync_timing": relu_sync,
    "two_cycle": two_cycle,
    "pipeline": pipeline,
    "vcd_example": vcd_example,
}


# ----------------------------------------------------------------- output ---
def render(name, out_dir):
    with plt.rc_context(STYLE):
        fig = WAVEFORMS[name](None)
        path = out_dir / f"{name}.png"
        # Software and Date are the only non-deterministic chunks matplotlib writes.
        fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.06,
                    metadata={"Software": None, "Date": None})
        plt.close(fig)
    return path


def block_names():
    tex = (HERE / "block_figs.tex").read_text(encoding="utf-8")
    return re.findall(r"^% fig: (\S+)", tex, flags=re.M)


def render_blocks(out_dir, only=None):
    """Compile block_figs.tex in a temp directory and split it into PNGs."""
    names = block_names()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # course.sty is found by a path relative to figs/; give the copy its own
        shutil.copy(HERE.parent.parent / "styles" / "course.sty", tmp / "course.sty")
        tex = (HERE / "block_figs.tex").read_text(encoding="utf-8").replace(
            "{../../styles/course}", "{course}")
        (tmp / "block_figs.tex").write_text(tex, encoding="utf-8")
        r = subprocess.run(["pdflatex", "-shell-escape", "-interaction=nonstopmode",
                            "block_figs.tex"], cwd=tmp, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        pdf = tmp / "block_figs.pdf"
        if r.returncode or not pdf.exists():
            log = (tmp / "block_figs.log").read_text(encoding="utf-8", errors="replace")
            errs = "\n".join(re.findall(r"^!.*$", log, flags=re.M)[:10])
            raise SystemExit(f"pdflatex failed on block_figs.tex:\n{errs}")
        pages = int(re.search(r"Pages:\s+(\d+)", subprocess.run(
            ["pdfinfo", str(pdf)], capture_output=True, text=True).stdout).group(1))
        if pages != len(names):
            raise SystemExit(f"block_figs.pdf has {pages} pages but {len(names)} '% fig:' names")
        for k, name in enumerate(names, 1):
            if only and name not in only:
                continue
            subprocess.run(["pdftocairo", "-png", "-r", "300", "-singlefile", "-f", str(k),
                            "-l", str(k), str(pdf), str(out_dir / name)], check=True)
            print(f"{name}.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE, help="where the PNGs are written")
    ap.add_argument("--only", action="append", help="render one figure (repeatable)")
    ap.add_argument("--no-blocks", action="store_true", help="skip block_figs.tex")
    args = ap.parse_args()
    self_check()
    args.out.mkdir(parents=True, exist_ok=True)
    known = set(WAVEFORMS) | set(block_names())
    for name in args.only or []:
        if name not in known:
            raise SystemExit(f"unknown figure {name!r}")
    for name in sorted(WAVEFORMS):
        if not args.only or name in args.only:
            print(render(name, args.out).name)
    if not args.no_blocks and (not args.only or set(args.only) & set(block_names())):
        render_blocks(args.out, set(args.only) if args.only else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
