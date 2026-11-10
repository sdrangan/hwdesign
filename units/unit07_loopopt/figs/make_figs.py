"""Generate unit 7's figures.

Replaces loopopt_figs.ipynb, as units 4 to 6 did: a notebook re-serialises its
outputs on every run, so the tracked file changed whether or not a figure did.
This script writes only the PNGs.

    python make_figs.py                  # every figure: charts and block diagrams
    python make_figs.py --only util_two
    python make_figs.py --no-blocks      # skip the TikZ block diagrams

Two sources:

  * the charts are drawn here with matplotlib: which multiplier is busy when
    (the utilization slides), and pipeline occupancy charts, one row per loop
    iteration and one box per stage.  The numbers are checked by self_check()
    against the ones the slides and the problems quote.
  * the block diagrams are block_figs.tex, one tikzpicture per page,
    compiled with pdflatex and split into one PNG per page at 300 dpi.

The deck also uses figures it does not make: unit 6's quadratic diagrams
(units/unit06_timing/figs) and the pipelining demo's schedule and timing
diagrams (docs/demos/loopopt/images, made by demos/pipeline/poly).

Needs matplotlib, and for the block diagrams pdflatex and pdftocairo (MiKTeX
has both).  Any of the course's Python environments will do.
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
from matplotlib.patches import FancyBboxPatch  # noqa: E402

HERE = Path(__file__).resolve().parent

# The deck's palette (tools/build_fifo_slides.py, shared with units 4 to 6).
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

# Unit 6's quadratic, y = w2 x^2 + w1 x + w0: register 1 ns, multiply 4 ns, add 1.5 ns.
T_REG, T_MULT, T_ADD = 1.0, 4.0, 1.5
T_SINGLE = T_REG + 2 * T_MULT + 2 * T_ADD          # x_reg -> xsq -> xsq_w2 -> two adds
T_TWO = T_REG + T_MULT + T_ADD                      # either stage of the two-cycle design


def self_check():
    assert T_SINGLE == 12.0 and T_TWO == 6.5
    assert round(100 * T_MULT / T_SINGLE) == 33 and round(100 * T_MULT / T_TWO) == 62
    # the Multiplier utilization problem: y = (a x + b) x + c, same delays
    four = max(T_REG + T_MULT, T_REG + T_ADD)
    assert four == 5.0 and 3 * four + T_REG + T_ADD == 17.5


# ============================================================ utilization ===
SAMPLE_COLOURS = {"A": (VIOLET, TINT), "B": (TEAL, TEAL_FILL), "C": (SLATE, SLATE_FILL),
                  "D": (AMBER, AMBER_FILL)}


def busy_chart(rows, period, ncycles, title):
    """rows: [(name, [(t0, t1, sample), ...]), ...]; one bar per busy interval,
    coloured by the input sample it works on, on a grid of clock edges."""
    fig, ax = plt.subplots(figsize=(7.6, 0.62 * len(rows) + 1.25))
    n = len(rows)
    for k, (name, spans) in enumerate(rows):
        y = n - 1 - k
        for t0, t1, s in spans:
            edge, fill = SAMPLE_COLOURS[s]
            ax.add_patch(FancyBboxPatch((t0, y - 0.32), t1 - t0, 0.64,
                                        boxstyle="round,pad=0,rounding_size=0.12",
                                        fc=fill, ec=edge, lw=1.3, zorder=3))
            ax.text((t0 + t1) / 2, y, s, ha="center", va="center", fontsize=12,
                    color=edge, fontweight="bold", zorder=4)
    tmax = period * ncycles
    for c in range(ncycles + 1):
        ax.axvline(c * period, color=GRID, lw=1.0, ls=(0, (4, 3)), zorder=1)
    ax.set_xlim(0, tmax)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_yticks(range(n))
    ax.set_yticklabels([r[0] for r in rows][::-1])
    ax.set_xticks([c * period for c in range(ncycles + 1)])
    ax.set_xticklabels([f"{c * period:g}" for c in range(ncycles + 1)])
    ax.set_xlabel("time [ns]: the dashed lines are the clock edges")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title(title, loc="left", fontsize=12.5, color=VIOLET, fontweight="bold")
    fig.tight_layout()
    return fig


def util_single(_):
    """Single cycle at 12 ns: M1 (xsq) and M3 (w1 x) start at 1 ns, M2 waits for M1."""
    p, s = T_SINGLE, "ABC"
    rows = [("M1: xreg · xreg", [(k * p + T_REG, k * p + T_REG + T_MULT, s[k]) for k in range(3)]),
            ("M2: w2 · xsq", [(k * p + T_REG + T_MULT, k * p + T_REG + 2 * T_MULT, s[k])
                              for k in range(3)]),
            ("M3: w1 · xreg", [(k * p + T_REG, k * p + T_REG + T_MULT, s[k]) for k in range(3)])]
    return busy_chart(rows, p, 3, "Single cycle, T_clk = 12 ns: each multiplier busy 4 ns in 12")


def util_two(_):
    """Two cycles at 6.5 ns: M1 and M3 in stage 1, M2 in stage 2, a sample behind."""
    p, s = T_TWO, "ABCD"
    rows = [("M1: xreg · xreg", [(k * p + T_REG, k * p + T_REG + T_MULT, s[k]) for k in range(4)]),
            ("M2: w2 · xsq", [((k + 1) * p + T_REG, (k + 1) * p + T_REG + T_MULT, s[k])
                              for k in range(3)]),
            ("M3: w1 · xreg", [(k * p + T_REG, k * p + T_REG + T_MULT, s[k]) for k in range(4)])]
    return busy_chart(rows, p, 4, "Two cycles, T_clk = 6.5 ns: busy 4 ns in 6.5, "
                                  "on two samples at once")


# ============================================================== occupancy ===
STAGE_COLOURS = [(VIOLET, TINT), (TEAL, TEAL_FILL), (SLATE, SLATE_FILL), (AMBER, AMBER_FILL)]


def occupancy(iters, stages, starts, *, span=None, ncycles, title=None, notes=(),
              colour_of=None, width=7.6):
    """One row per iteration; iteration k runs stage j in cycle starts[k] + j
    (or over span[j] cycles).  notes: [(kind, ...)] annotations."""
    span = span or [1] * len(stages)
    fig, ax = plt.subplots(figsize=(width, 0.55 * len(iters) + 1.2))
    n = len(iters)
    for k, name in enumerate(iters):
        y = n - 1 - k
        c = starts[k]
        for j, st in enumerate(stages):
            ci = (colour_of(j) if colour_of else j) % len(STAGE_COLOURS)
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
    ax.set_yticklabels(iters[::-1])
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


def occ_terms(_):
    """Samples A to D through stages s0, s1, s2 at II = 1: L = 3."""
    return occupancy(["A", "B", "C", "D"], ["s0", "s1", "s2"], [0, 1, 2, 3], ncycles=7,
                     notes=[("span", 0, 1, -0.05, "II = 1", AMBER),
                            ("span", 3, 6, 3, "L = 3: sample D, from s0 to the end of s2", TEAL, "below")],
                     title="Each sample takes L = 3 cycles; a new one starts every II = 1")


def occ_memory(_):
    """The elementwise product: load, multiply, store, one iteration per cycle."""
    return occupancy(["i = 0", "i = 1", "i = 2", "i = 3"], ["load", "mult", "store"],
                     [0, 1, 2, 3], ncycles=6,
                     title="N = 4 iterations finish in N + 2 = 6 cycles: the last two drain")


def occ_merge(_):
    """Merge sort: stage 0 of the next iteration needs stage 1's i, j."""
    return occupancy(["k = 0", "k = 1", "k = 2", "k = 3"],
                     ["S0 read", "S1 compare", "S2 write"], [0, 2, 4, 6], ncycles=9, width=10.5,
                     notes=[("arrow", 2.0, 0, 2.0, 1, AMBER), ("arrow", 4.0, 1, 4.0, 2, AMBER),
                            ("arrow", 6.0, 2, 6.0, 3, AMBER),
                            ("span", 0, 2, -0.05, "II = 2", AMBER)],
                     title="i and j: produced in S1, needed in the next S0.  II = 1 − 0 + 1 = 2")


def occ_float(_):
    """prod *= x[i] with a 4-cycle multiply: each multiply waits for the last."""
    return occupancy(["i = 0", "i = 1", "i = 2"], ["S0", "S1 – S4 multiply"], [0, 4, 8],
                     span=[1, 4], ncycles=13,
                     notes=[("arrow", 5.0, 0, 5.0, 1, AMBER), ("arrow", 9.0, 1, 9.0, 2, AMBER),
                            ("span", 0, 4, -0.05, "II = 4", AMBER)],
                     title="prod: produced at the end of S4, needed in the next S1.  "
                           "II = 4 − 1 + 1 = 4")


def occ_sum(_):
    """int sum += x[i]: the add needs the last add's sum, one stage later -- no wait."""
    return occupancy(["i = 0", "i = 1", "i = 2", "i = 3"], ["S0 load", "S1 add"],
                     [0, 1, 2, 3], ncycles=6,
                     notes=[("arrow", 2.0, 0, 2.0, 1, AMBER), ("arrow", 3.0, 1, 3.0, 2, AMBER),
                            ("arrow", 4.0, 2, 4.0, 3, AMBER),
                            ("span", 0, 1, -0.05, "II = 1", AMBER)],
                     title="sum: produced in S1, needed in the next S1.  II = 1 − 1 + 1 = 1")


def occ_exit(_):
    """The early-exit loop as written: the next iteration may start only once
    this one's test says it did not break."""
    return occupancy(["i = 0", "i = 1", "i = 2"], ["S0 read", "S1 square", "S2 test · write"],
                     [0, 3, 6], ncycles=9, width=10.5,
                     notes=[("arrow", 3.0, 0, 3.0, 1, AMBER), ("arrow", 6.0, 1, 6.0, 2, AMBER),
                            ("span", 0, 3, -0.05, "II = 3", AMBER)],
                     title="The exit: decided in S2, needed before the next S0.  "
                           "II = 2 − 0 + 1 = 3")


def occ_exit_pipe(_):
    """Pipelined by hand: one loop iteration is one column -- it reads x[i],
    squares x[i-1] and tests x[i-2] -- and j passes test to test."""
    fig = occupancy(["x[0]", "x[1]", "x[2]", "x[3]"], ["read", "square", "test · write"],
                    [0, 1, 2, 3], ncycles=6, width=9.0,
                    notes=[("arrow", 3.0, 0, 3.0, 1, AMBER), ("arrow", 4.0, 1, 4.0, 2, AMBER),
                           ("arrow", 5.0, 2, 5.0, 3, AMBER),
                           ("span", 0, 1, -0.05, "II = 1", AMBER)],
                    title="j: produced in the test, needed in the next test.  "
                          "II = 2 − 2 + 1 = 1")
    ax = fig.axes[0]
    n = 4
    ax.add_patch(FancyBboxPatch((2.02, -0.48), 0.86, n - 0.04,boxstyle="round,pad=0,rounding_size=0.08",
                                fc="none", ec=SLATE, lw=2.0, ls=(0, (4, 2)), zorder=6))
    ax.text(2.5, -0.7,"loop iteration i = 2: reads x[2], squares x[1], tests x[0]",
            ha="center", va="top", color=SLATE, fontsize=11.5, fontweight="bold")
    return fig


FIGURES = {
    "occ_exit": occ_exit,
    "occ_exit_pipe": occ_exit_pipe,
    "util_single": util_single,
    "util_two": util_two,
    "occ_terms": occ_terms,
    "occ_memory": occ_memory,
    "occ_merge": occ_merge,
    "occ_float": occ_float,
    "occ_sum": occ_sum,
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
    known = set(FIGURES) | set(block_names())
    for name in args.only or []:
        if name not in known:
            raise SystemExit(f"unknown figure {name!r}")
    for name in sorted(FIGURES):
        if not args.only or name in args.only:
            print(render(name, args.out).name)
    if not args.no_blocks and (not args.only or set(args.only) & set(block_names())):
        render_blocks(args.out, set(args.only) if args.only else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
