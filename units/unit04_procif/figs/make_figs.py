"""Generate unit 4's timing-diagram figures.

Replaces procif_figs.ipynb.  A notebook re-serialises its outputs and execution
counts on every run, so the tracked file changed whether or not a figure did;
this script writes only the PNGs, and writes them byte-identically when the
figure has not changed, so `git status` stays quiet.

    python make_figs.py                 # write the PNGs
    python make_figs.py --check         # fail if any tracked PNG is stale
    python make_figs.py --only axi_read # one figure

Determinism: matplotlib stamps a PNG with the library version and the time of
writing, so those two chunks are suppressed explicitly.  Everything else about
a matplotlib PNG is a pure function of the inputs, given a fixed matplotlib and
FreeType.  A version bump can still change antialiasing by a pixel; that shows
up as a one-off diff on every figure, which is the honest signal that the
rendering changed.

The drawing itself comes from waveflow (waveflow.utils.timing).  That module
strokes every waveform in black at a fixed line width, so the house style is
applied after the draw by restyling the line collections it produced.
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

# The deck's palette (see tools/build_procif_slides.py): violet for the address
# channel, teal for the data channel, slate for anything about control.
INK = "262626"
VIOLET = "#57068C"
VIOLET_FILL = "#E4D5EF"
TEAL = "#00857C"
TEAL_FILL = "#CFE9E5"
SLATE = "#2F6FA8"
MUTED = "#6E6E6E"

STYLE = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Calibri", "Carlito", "DejaVu Sans"],
    "font.size": 11,
    "axes.edgecolor": "#B9B9C4",
    "axes.linewidth": 0.8,
    "text.color": "#262626",
    "axes.labelcolor": "#262626",
    "xtick.color": "#6E6E6E",
    "xtick.labelsize": 10,
    "legend.frameon": False,
    "legend.fontsize": 10,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
}

CLK_PERIOD = 10
NCYCLES = 8


def _clock(ncycles=NCYCLES):
    clk = ClkSig(clk_name="CLK", period=CLK_PERIOD, ncycles=ncycles)
    return clk, clk.clk_periods()


def _level(name, times, values):
    return SigTimingInfo(name=name, times=times, values=values)


def _restyle(ax, td):
    """waveflow strokes waveforms in black; give them the deck's ink and weight,
    and quiet the clock grid."""
    for coll in ax.collections:
        if isinstance(coll, LineCollection):
            coll.set_color("#" + INK)
            coll.set_linewidth(1.3)
    for line in ax.lines:                       # the clock grid
        line.set_color("#C9C9D2")
        line.set_linewidth(0.7)
    ax.set_xlabel(f"time [{td.time_unit}]")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="x", length=3)


def _legend(ax, entries):
    ax.legend(handles=[Patch(label=lab, **kw) for lab, kw in entries],
              loc="center left", bbox_to_anchor=(1.01, 0.5), handlelength=1.6,
              borderpad=0.2, labelspacing=0.6)


# --------------------------------------------------------------- figures ---
def axi_write(_):
    """AXI4-Lite write: address and data handshake in different cycles."""
    # One cycle longer than the others: the write response needs BVALID and
    # then BREADY after the later of the two handshakes.
    clk, p = _clock(9)
    irdy, iaddr, idat = 1, 2, 4

    td = TimingDiagram()
    td.add_signals([clk,
                    _level("AWREADY", [p[0], p[irdy], p[iaddr + 1]], ["0", "1", "0"]),
                    _level("AWVALID", [p[0], p[iaddr], p[iaddr + 1]], ["0", "1", "0"]),
                    _level("AWADDR[7:0]", [p[0], p[iaddr], p[iaddr + 1]], ["0x00", "0x12", "0x34"])])
    td.add_signals([clk,
                    _level("WREADY", [p[0], p[irdy], p[idat + 1]], ["0", "1", "0"]),
                    _level("WVALID", [p[0], p[idat], p[idat + 1]], ["0", "1", "0"]),
                    _level("WDATA[7:0]", [p[0], p[idat], p[idat + 1]], ["0x00", "0xAB", "0xCD"])])
    # The response transfers where BVALID and BREADY overlap, so BVALID stays
    # asserted until the master answers: they must share a cycle.
    iend = max(iaddr + 1, idat + 1)
    td.add_signals([_level("BVALID", [p[0], p[iend + 1], p[iend + 3]], ["0", "1", "0"]),
                    _level("BREADY", [p[0], p[iend + 2], p[iend + 3]], ["0", "1", "0"])])

    ax = td.plot_signals(fig_width=10, row_height=0.52)
    td.add_patch(sig_name="AWADDR[7:0]", ind=1, facecolor=VIOLET_FILL, edgecolor=VIOLET, lw=1.0)
    td.add_patch(sig_name="WDATA[7:0]", ind=1, facecolor=TEAL_FILL, edgecolor=TEAL, lw=1.0)
    # The span is (bottom row, top row): add_patch takes ybot of the first and
    # ytop of the second, so naming them the other way round draws nothing.
    td.add_patch(sig_name=["BREADY", "BVALID"], time=[p[iend + 2], p[iend + 3]],
                 facecolor="none", edgecolor=SLATE, lw=1.2, linestyle="--")
    _restyle(ax, td)
    _legend(ax, [("address transferred", dict(facecolor=VIOLET_FILL, edgecolor=VIOLET)),
                 ("data transferred", dict(facecolor=TEAL_FILL, edgecolor=TEAL)),
                 ("response transferred", dict(facecolor="none", edgecolor=SLATE, linestyle="--"))])
    return ax.figure


def axi_write_stall(_):
    """AXI4-Lite write where the slave is not ready when the master is."""
    clk, p = _clock()
    irdy, iaddr, idat = 2, 1, 1
    ardyend = max(irdy, iaddr) + 1
    drdyend = max(irdy, idat) + 1

    td = TimingDiagram()
    td.add_signals([clk,
                    _level("AWREADY", [p[0], p[irdy], p[ardyend]], ["0", "1", "0"]),
                    _level("AWVALID", [p[0], p[iaddr], p[ardyend]], ["0", "1", "0"]),
                    _level("AWADDR[7:0]", [p[0], p[iaddr], p[ardyend]], ["0x00", "0x12", "0x34"])])
    td.add_signals([clk,
                    _level("WREADY", [p[0], p[irdy], p[drdyend]], ["0", "1", "0"]),
                    _level("WVALID", [p[0], p[idat], p[drdyend]], ["0", "1", "0"]),
                    _level("WDATA[7:0]", [p[0], p[idat], p[drdyend]], ["0x00", "0xAB", "0xCD"])])
    iend = max(drdyend, ardyend) + 1
    td.add_signals([_level("BVALID", [p[0], p[iend], p[iend + 2]], ["0", "1", "0"]),
                    _level("BREADY", [p[0], p[iend + 1], p[iend + 2]], ["0", "1", "0"])])

    ax = td.plot_signals(fig_width=10, row_height=0.52)
    for sig, fill, edge in (("AWADDR[7:0]", VIOLET_FILL, VIOLET), ("WDATA[7:0]", TEAL_FILL, TEAL)):
        td.add_patch(sig_name=sig, time=[p[1], p[2]], facecolor="none", edgecolor=edge,
                     hatch="///", lw=1.0)
        td.add_patch(sig_name=sig, time=[p[2], p[3]], facecolor=fill, edgecolor=edge, lw=1.0)
    _restyle(ax, td)
    _legend(ax, [("waiting for READY", dict(facecolor="none", edgecolor=MUTED, hatch="///")),
                 ("address transferred", dict(facecolor=VIOLET_FILL, edgecolor=VIOLET)),
                 ("data transferred", dict(facecolor=TEAL_FILL, edgecolor=TEAL))])
    return ax.figure


def axi_read(_):
    """AXI4-Lite read: address out, data back a cycle later."""
    clk, p = _clock()
    irdy, iaddr, idat = 1, 2, 4

    td = TimingDiagram()
    td.add_signals([clk,
                    _level("ARREADY", [p[0], p[irdy], p[iaddr + 1]], ["0", "1", "0"]),
                    _level("ARVALID", [p[0], p[iaddr], p[iaddr + 1]], ["0", "1", "0"]),
                    _level("ARADDR[7:0]", [p[0], p[iaddr], p[iaddr + 1]], ["0x00", "0x12", "0x34"])])
    # The slave drives RVALID a cycle before the master answers RREADY, as in
    # the AXI4-Lite Read problem: the data transfers where they overlap.
    td.add_signals([clk,
                    _level("RVALID", [p[0], p[idat], p[idat + 2]], ["0", "1", "0"]),
                    _level("RREADY", [p[0], p[idat + 1], p[idat + 2]], ["0", "1", "0"]),
                    _level("RDATA[7:0]", [p[0], p[idat], p[idat + 2]], ["0x00", "0xAB", "0xCD"])])

    ax = td.plot_signals(fig_width=10, row_height=0.52)
    td.add_patch(sig_name="ARADDR[7:0]", ind=1, facecolor=VIOLET_FILL, edgecolor=VIOLET, lw=1.0)
    td.add_patch(sig_name="RDATA[7:0]", time=[p[idat + 1], p[idat + 2]],
                 facecolor=TEAL_FILL, edgecolor=TEAL, lw=1.0)
    _restyle(ax, td)
    _legend(ax, [("address transferred", dict(facecolor=VIOLET_FILL, edgecolor=VIOLET)),
                 ("data returned", dict(facecolor=TEAL_FILL, edgecolor=TEAL))])
    return ax.figure


FIGURES = {
    "axi_write": axi_write,
    "axi_write_stall": axi_write_stall,
    "axi_read": axi_read,
}

# Figures a problem in hwdesign-soln shows to students.  They are copied into
# the solution package's image directory so the portal and the slides display
# the same file, rather than two copies that drift apart.
PROBLEM_FIGURES = {"axi_write_stall"}
SOLN_IMAGES = (HERE / "../../../../hwdesign-soln/units/unit04_procif/prob/images").resolve()


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
        note = ""
        if name in PROBLEM_FIGURES:
            if SOLN_IMAGES.is_dir():
                (SOLN_IMAGES / path.name).write_bytes(path.read_bytes())
                note = f"-> {SOLN_IMAGES.name}/"
            else:
                note = f"(not copied: {SOLN_IMAGES} missing)"
        print(f"{path.name:24s} {digest(path)}  {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
