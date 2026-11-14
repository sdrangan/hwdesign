"""Generate unit 8's figures.

    python make_figs.py                  # every figure
    python make_figs.py --only partition

All of them are drawn here with matplotlib, in the deck's palette and in the
style of unit 7's (units/unit07_loopopt/figs/make_figs.py), whose occupancy
chart this reuses: one row per sample or iteration, one box per stage.
The numbers they show are checked by self_check() against the ones the
slides and the problems quote.

The deck also uses figures it does not make: the poly demo's unroll chart and
schedule (docs/demos/loopopt/images, made by demos/pipeline/poly) and the FIR
demo's chart and timing diagram (docs/demos/fir/images, made by demos/fir).

Needs matplotlib; any of the course's Python environments will do.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")                     # no display, and identical on any machine
import matplotlib.pyplot as plt           # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent

# The deck's palette (tools/build_fifo_slides.py, shared with units 4 to 7).
INK = "#262626"
VIOLET = "#57068C"
TINT = "#EEE6F3"
TEAL = "#00857C"
TEAL_FILL = "#CFE9E5"
SLATE = "#2F6FA8"
SLATE_FILL = "#EAF0F7"
AMBER = "#B4530F"
AMBER_FILL = "#FCEEE3"
MUTED = "#6E6E6E"
GRID = "#D9D9DE"
GRAY_FILL = "#EDEDED"

STYLE = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Calibri", "Carlito", "DejaVu Sans"],
    "font.size": 12,
    "axes.edgecolor": "#B9B9C4",
    "axes.linewidth": 0.8,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 11,
    "ytick.labelsize": 12,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
}
DPI = 250
STAGE_COLOURS = [(VIOLET, TINT), (TEAL, TEAL_FILL), (SLATE, SLATE_FILL), (AMBER, AMBER_FILL)]
BANK_COLOURS = [(VIOLET, TINT), (TEAL, TEAL_FILL), (SLATE, SLATE_FILL), (AMBER, AMBER_FILL)]

# The BRAM example on the slides: deliberately not the homework's numbers.
BRAM_KBIT = 18
EX_WORDS, EX_BITS = 1536, 32                       # 48 kbit


def brams(words, bits, banks):
    per_bank = math.ceil(words * bits / banks / (BRAM_KBIT * 1024))
    return per_bank * banks


def self_check():
    assert [brams(EX_WORDS, EX_BITS, u) for u in (1, 2, 4, 8)] == [3, 4, 4, 8]


# ============================================================ occupancy ===
def occupancy(rows, stages, starts, *, span=None, ncycles, title=None, notes=(),
              colour_of=None, width=7.6, row_h=0.55):
    """One row per sample; row k runs stage j in cycle starts[k] + j (or over
    span[j] cycles).  As unit 7's, plus a per-row colour."""
    span = span or [1] * len(stages)
    fig, ax = plt.subplots(figsize=(width, row_h * len(rows) + 1.2))
    n = len(rows)
    for k, name in enumerate(rows):
        y = n - 1 - k
        c = starts[k]
        for j, st in enumerate(stages):
            ci = (colour_of(k, j) if colour_of else j) % len(STAGE_COLOURS)
            edge, fill = STAGE_COLOURS[ci]
            ax.add_patch(FancyBboxPatch((c + 0.06, y - 0.32), span[j] - 0.12, 0.64,
                                        boxstyle="round,pad=0,rounding_size=0.1",
                                        fc=fill, ec=edge, lw=1.2, zorder=3))
            ax.text(c + span[j] / 2, y, st, ha="center", va="center", fontsize=11,
                    color=edge, fontweight="bold", zorder=4)
            c += span[j]
    for c in range(ncycles + 1):
        ax.axvline(c, color=GRID, lw=0.9, zorder=1)
    ax.set_xlim(0, ncycles)
    ax.set_ylim(-1.15, n - 0.2)
    ax.set_yticks(range(n))
    ax.set_yticklabels(rows[::-1])
    ax.set_xticks([c + 0.5 for c in range(ncycles)])
    ax.set_xticklabels([str(c) for c in range(ncycles)])
    ax.set_xlabel("clock cycle")
    ax.tick_params(axis="both", length=0)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    for note in notes:
        kind = note[0]
        if kind == "span":       # ("span", x0, x1, row, text, colour[, "below"])
            _, x0, x1, row, text, col = note[:6]
            below = len(note) > 6
            y = n - 1 - row + (-0.5 if below else 0.5)
            ax.annotate("", xy=(x1, y), xytext=(x0, y), annotation_clip=False,
                        arrowprops=dict(arrowstyle="<->", color=col, lw=1.4,
                                        shrinkA=0, shrinkB=0))
            ax.text((x0 + x1) / 2, y + (-0.06 if below else 0.06), text, ha="center",
                    va="top" if below else "bottom", color=col, fontsize=12, fontweight="bold")
        elif kind == "arrow":                  # ("arrow", x0, row0, x1, row1, colour)
            _, x0, r0, x1, r1, col = note
            ax.annotate("", xy=(x1, n - 1 - r1 + 0.18), xytext=(x0, n - 1 - r0 - 0.18),
                        arrowprops=dict(arrowstyle="->", color=col, lw=1.8), zorder=5)
    if title:
        ax.set_title(title, loc="left", fontsize=12.5, color=VIOLET, fontweight="bold")
    fig.tight_layout()
    return fig


def occ_pipe(_):
    """The pipelined loop: one sample starts per cycle."""
    return occupancy([f"x[{k}]" for k in range(4)], ["load", "compute", "store"], [0, 1, 2, 3],
                     ncycles=7, colour_of=lambda k, j: j,
                     notes=[("span", 0, 1, -0.05, "II = 1", AMBER)],
                     title="Pipelined: one new sample every cycle")


def occ_unroll(_):
    """Unrolled by 2: two samples start together, in two copies of the body."""
    return occupancy([f"x[{k}]" for k in range(8)], ["load", "compute", "store"],
                     [k // 2 for k in range(8)], ncycles=7,
                     colour_of=lambda k, j: j,
                     notes=[("span", 0, 1, -0.05, "II = 1", AMBER)],
                     title="Unrolled by 2: two samples every cycle, in two copies of the body",
                     row_h=0.42)


def occ_ports(_):
    """Unrolled by 4 on one single-port memory: the loads take turns."""
    rows = [f"x[{k}]" for k in range(8)]
    starts = [4 * (k // 4) + k % 4 for k in range(8)]
    return occupancy(rows, ["load", "compute", "store"], starts, ncycles=11,
                     colour_of=lambda k, j: j, row_h=0.42, width=8.4,
                     notes=[("span", 0, 4, 7, "II = 4: the next iteration's loads wait", AMBER,
                             "below")],
                     title="Unrolled by 4, one port: the four loads take turns")


# ============================================================ partition ===
def _bank_row(ax, y, banks, label, sub):
    """banks: list of lists of element indices; one box per element."""
    x = 0.0
    for b, elems in enumerate(banks):
        edge, fill = BANK_COLOURS[b % len(BANK_COLOURS)]
        w = 0.62 * len(elems) + 0.18
        ax.add_patch(FancyBboxPatch((x, y - 0.42), w, 0.84, boxstyle="round,pad=0,rounding_size=0.08",
                                    fc="white", ec=edge, lw=1.6, zorder=2))
        for j, e in enumerate(elems):
            ax.add_patch(Rectangle((x + 0.09 + 0.62 * j, y - 0.27), 0.56, 0.54,
                                   fc=fill, ec=edge, lw=1.0, zorder=3))
            ax.text(x + 0.09 + 0.62 * j + 0.28, y, str(e), ha="center", va="center",
                    fontsize=11, color=edge, fontweight="bold", zorder=4)
        ax.text(x + w / 2, y + 0.55, f"bank {b}", ha="center", va="bottom", fontsize=10.5,
                color=edge)
        x += w + 0.3
    ax.text(-0.35, y + 0.08, label, ha="right", va="center", fontsize=13, fontweight="bold",
            color=INK)
    ax.text(-0.35, y - 0.28, sub, ha="right", va="center", fontsize=10.5, color=MUTED)


def partition(_):
    """x[0..7] in one memory, and partitioned three ways."""
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    _bank_row(ax, 6.0, [list(range(8))], "one memory", "1 port")
    _bank_row(ax, 4.3, [[0, 2, 4, 6], [1, 3, 5, 7]], "cyclic, factor 2", "x[k] in bank k % 2")
    _bank_row(ax, 2.6, [[0, 1, 2, 3], [4, 5, 6, 7]], "block, factor 2", "x[k] in bank k / 4")
    _bank_row(ax, 0.9, [[k] for k in range(8)], "complete", "8 registers")
    ax.set_xlim(-3.4, 9.4)
    ax.set_ylim(0.2, 7.0)
    ax.axis("off")
    fig.tight_layout()
    return fig


# ============================================================== BRAMs ======
def bram_banks(_):
    """The slides' example: 1536 x 32 bits, 48 kbit, partitioned 1, 2, 4, 8 ways."""
    fig, ax = plt.subplots(figsize=(9.0, 3.9))
    total = EX_WORDS * EX_BITS / 1024                # kbit
    for row, u in enumerate((1, 2, 4, 8)):
        y = 3 - row
        bank = total / u
        per = math.ceil(bank / BRAM_KBIT)
        x = 0.0
        for b in range(u):
            left = bank
            for _ in range(per):
                used = min(left, BRAM_KBIT)
                left -= used
                edge, fill = BANK_COLOURS[b % len(BANK_COLOURS)]
                ax.add_patch(Rectangle((x, y - 0.3), 0.9, 0.6, fc="white", ec=edge, lw=1.3))
                ax.add_patch(Rectangle((x, y - 0.3), 0.9 * used / BRAM_KBIT, 0.6, fc=fill,
                                       ec="none"))
                ax.add_patch(Rectangle((x, y - 0.3), 0.9, 0.6, fc="none", ec=edge, lw=1.3))
                x += 0.98
            x += 0.25
        n = brams(EX_WORDS, EX_BITS, u)
        ax.text(-0.3, y, f"{u} bank{'s' if u > 1 else ''}", ha="right", va="center",
                fontsize=12.5, fontweight="bold")
        ax.text(x + 0.2, y, f"{bank:g} kbit per bank  →  {n} BRAM18,  "
                f"{100 * total / (n * BRAM_KBIT):.0f}% full", ha="left", va="center",
                fontsize=11.5, color=VIOLET if n > 4 else INK)
    ax.set_xlim(-2.0, 17.5)
    ax.set_ylim(-0.6, 3.6)
    ax.axis("off")
    ax.set_title(f"A {EX_WORDS} × {EX_BITS}-bit array (48 kbit) in 18-kbit BRAMs.  "
                 "Shaded: the part of each block that holds data", loc="left", fontsize=12,
                 color=VIOLET, fontweight="bold")
    fig.tight_layout()
    return fig


# ========================================================== reductions =====
def _node(ax, x, y, text, edge=VIOLET, fill=TINT, r=0.32):
    ax.add_patch(plt.Circle((x, y), r, fc=fill, ec=edge, lw=1.5, zorder=3))
    ax.text(x, y, text, ha="center", va="center", fontsize=13, color=edge, fontweight="bold",
            zorder=4)


def _box(ax, x, y, text, edge=SLATE, fill=SLATE_FILL, w=1.0, h=0.5):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.08",
                                fc=fill, ec=edge, lw=1.4, zorder=3))
    ax.text(x, y, text, ha="center", va="center", fontsize=12, color=edge, zorder=4)


def _wire(ax, x0, y0, x1, y1, col=MUTED, lw=1.4):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="->", color=col, lw=lw, shrinkA=13, shrinkB=13), zorder=2)


def adder_tree(_):
    """sum += (p0 + p1) + (p2 + p3): the tree is off the loop-carried path."""
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    xs = [0, 1.5, 3.0, 4.5]
    for k, x in enumerate(xs):
        _box(ax, x, 4.0, f"a[i+{k}]·b[i+{k}]", w=1.35)
    _node(ax, 0.75, 2.85, "+")
    _node(ax, 3.75, 2.85, "+")
    for k, x in enumerate(xs):
        _wire(ax, x, 3.75, 0.75 if k < 2 else 3.75, 2.85)
    _node(ax, 2.25, 1.75, "+")
    _wire(ax, 0.75, 2.85, 2.25, 1.75)
    _wire(ax, 3.75, 2.85, 2.25, 1.75)
    _node(ax, 2.25, 0.6, "+", edge=AMBER, fill=AMBER_FILL)
    _wire(ax, 2.25, 1.75, 2.25, 0.6)
    _box(ax, 4.4, 0.6, "sum", edge=AMBER, fill=AMBER_FILL, w=0.9)
    ax.annotate("", xy=(3.95, 0.45), xytext=(2.25, 0.45),
                arrowprops=dict(arrowstyle="-|>", color=AMBER, lw=1.8, shrinkA=14, shrinkB=0,
                                mutation_scale=16), zorder=2)
    ax.annotate("", xy=(2.45, 0.86), xytext=(4.4, 0.85),
                arrowprops=dict(arrowstyle="-|>", color=AMBER, lw=1.8, shrinkA=13, shrinkB=0,
                                mutation_scale=16, connectionstyle="arc3,rad=0.45"), zorder=2)
    ax.text(3.3, -0.25, "loop-carried: one add", ha="center", va="center", color=AMBER,
            fontsize=12, fontweight="bold")
    ax.text(-0.8, 2.3, "tree:\nno feedback", ha="center", va="center", color=VIOLET,
            fontsize=12, fontweight="bold")
    ax.set_xlim(-1.6, 5.4)
    ax.set_ylim(-0.6, 4.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    return fig


# ============================================================ FIR ==========
FIR_T = 4             # taps in the timeline sketch
FIR_FILL = 3          # cycles to fill and drain the tap loop's pipeline, per entry


def fir_timeline(_):
    """Which cycles produce an output, for the four ways of writing the loop
    nest, with a 4-tap filter: one box per output sample's work."""
    ncycles = 26
    fig, ax = plt.subplots(figsize=(10.5, 3.9))
    rows = [("inner", "tap loop pipelined:\nrefilled for every sample", AMBER, AMBER_FILL),
            ("flat", "flattened: one tap per cycle,\nno gaps", SLATE, SLATE_FILL),
            ("outer", "sample loop pipelined, one port:\none sample per 4 cycles", VIOLET, TINT),
            ("delay", "delay line:\none sample per cycle", TEAL, TEAL_FILL)]
    for r, (name, desc, edge, fill) in enumerate(rows):
        y = 3 - r
        c, n = 0, 0
        while c < ncycles:
            if name == "inner":
                w, gap = FIR_T, FIR_FILL
            elif name in ("flat", "outer"):
                w, gap = FIR_T, 0
            else:
                w, gap = 1, 0
            w_draw = min(w, ncycles - c)
            ax.add_patch(FancyBboxPatch((c + 0.06, y - 0.3), w_draw - 0.12, 0.6,
                                        boxstyle="round,pad=0,rounding_size=0.08",
                                        fc=fill, ec=edge, lw=1.2, zorder=3))
            if w_draw >= 1:
                ax.text(c + w_draw / 2, y, str(n) if w == 1 else f"y[{n}]", ha="center", va="center", fontsize=10.5,
                        color=edge, fontweight="bold", zorder=4)
            c += w + gap
            n += 1
        ax.text(-0.4, y, name, ha="right", va="center", fontsize=13, fontweight="bold",
                color=edge)
        ax.text(ncycles + 0.4, y, desc, ha="left", va="center", fontsize=10.5, color=MUTED)
    for c in range(ncycles + 1):
        ax.axvline(c, color=GRID, lw=0.8, zorder=1)
    ax.set_xlim(-2.6, ncycles + 8.5)
    ax.set_ylim(-0.7, 3.6)
    ax.set_yticks([])
    ax.set_xticks([c + 0.5 for c in range(0, ncycles, 5)])
    ax.set_xticklabels([str(c) for c in range(0, ncycles, 5)])
    ax.set_xlabel("clock cycle")
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="both", length=0)
    ax.set_title(f"A {FIR_T}-tap FIR: the cycles each output sample's work occupies",
                 loc="left", fontsize=12.5, color=VIOLET, fontweight="bold")
    fig.tight_layout()
    return fig


def delay_line(_):
    """The direct-form FIR: a shift register of samples, a multiplier per tap,
    and an adder tree."""
    fig, ax = plt.subplots(figsize=(9.0, 3.8))
    T = 4
    xs = [1.4 + 2.0 * k for k in range(T)]
    ax.text(0.0, 3.0, "x[n]", ha="center", va="center", fontsize=14, color=INK)
    for k, x in enumerate(xs):
        ax.add_patch(Rectangle((x - 0.55, 2.7), 1.1, 0.6, fc=TINT, ec=VIOLET, lw=1.5, zorder=3))
        ax.text(x, 3.0, f"xdly[{k}]", ha="center", va="center", fontsize=11.5, color=VIOLET,
                fontweight="bold", zorder=4)
        src = 0.25 if k == 0 else xs[k - 1] + 0.55
        ax.annotate("", xy=(x - 0.55, 3.0), xytext=(src, 3.0),
                    arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.4), zorder=2)
        _node(ax, x, 1.75, "×", edge=TEAL, fill=TEAL_FILL, r=0.3)
        ax.annotate("", xy=(x, 2.05), xytext=(x, 2.7),
                    arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.4), zorder=2)
        ax.text(x + 0.42, 1.75, f"h[{k}]", ha="left", va="center", fontsize=11.5, color=TEAL)
        ax.text(x, 3.55, f"x[n−{k}]" if k else "x[n]", ha="center", va="center", fontsize=10.5,
                color=MUTED)
    _box(ax, sum(xs) / T, 0.55, "adder tree", edge=SLATE, fill=SLATE_FILL, w=2.4, h=0.55)
    for x in xs:
        ax.annotate("", xy=(sum(xs) / T + (x - sum(xs) / T) * 0.35, 0.83), xytext=(x, 1.45),
                    arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.3), zorder=2)
    ax.annotate("", xy=(sum(xs) / T + 2.6, 0.55), xytext=(sum(xs) / T + 1.2, 0.55),
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.4), zorder=2)
    ax.text(sum(xs) / T + 2.75, 0.55, "y[n]", ha="left", va="center", fontsize=14)
    ax.text(xs[-1] + 0.9, 3.0, "each cycle: shift right,\nread one new x[n]", ha="left",
            va="center", fontsize=11, color=VIOLET)
    ax.set_xlim(-0.5, 11.6)
    ax.set_ylim(0.0, 3.9)
    ax.axis("off")
    fig.tight_layout()
    return fig


FIGURES = {
    "occ_pipe": occ_pipe,
    "occ_unroll": occ_unroll,
    "occ_ports": occ_ports,
    "partition": partition,
    "bram_banks": bram_banks,
    "adder_tree": adder_tree,
    "fir_timeline": fir_timeline,
    "delay_line": delay_line,
}


# ----------------------------------------------------------------- output ---
def render(name, out_dir):
    with plt.rc_context(STYLE):
        fig = FIGURES[name](None)
        path = out_dir / f"{name}.png"
        # Software and Date are the only non-deterministic chunks matplotlib writes.
        fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.06,
                    metadata={"Software": None, "Date": None})
        plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE, help="where the PNGs are written")
    ap.add_argument("--only", action="append", help="render one figure (repeatable)")
    args = ap.parse_args()
    self_check()
    args.out.mkdir(parents=True, exist_ok=True)
    for name in args.only or []:
        if name not in FIGURES:
            raise SystemExit(f"unknown figure {name!r}")
    for name in sorted(FIGURES):
        if not args.only or name in args.only:
            print(render(name, args.out).name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
