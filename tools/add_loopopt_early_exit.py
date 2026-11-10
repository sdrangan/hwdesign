"""Add "Early Termination" to the end of unit 7's "Limits on the II".

Four slides after "The Adder Pipeline":

  * Early Termination -- a loop that keeps the first NZ squares above zmin
    and breaks when z is full.  The next iteration may start only once this
    one did not break, and that is decided in the last stage: II = 3 by the
    minimum-II rule.  Asked for II = 1, Vitis packs the iteration into one
    cycle and misses timing instead.
  * Pipelining by Hand -- iteration i reads x[i], squares x[i-1] and tests
    x[i-2]; the exit test needs only j, produced and needed in the test.
  * The Stages in Hardware -- the block diagram, exit path highlighted.
  * Three Ways to Stop -- as written, no break (a guarded write), by hand.

x is ap_int<16> so the square fits in a cycle; a 32-bit square needs a
split of its own, which would only distract.  The numbers are Vitis HLS
2025.1 at 10 ns on xc7z020: as written II = 1 at an estimated 16.3 ns; no
break 6.8 ns, 260 cycles always; by hand 6.53 ns, 3 cycles after z fills.
The hand-pipelined loop matches the loop as written in C simulation and RTL
co-simulation.  Its data registers xr and zr have no reset, on purpose: with
"= 0" on xr, Vitis puts the initial-value mux on the square's path and the
estimate rises to 8.8 ns; the valid bits already say when they hold a sample.  A delay line on j, or DEPENDENCE false on an exit flag, does
not help: Vitis keeps the exit in the iteration whose work decides it.

Like add_loopopt_ii_rule.py, it edits loopopt.pptx in place once and refuses
to run twice.  Render the figures first (make_figs.py: occ_exit,
occ_exit_pipe, exit_pipe), and close the deck in PowerPoint.

    python tools/add_loopopt_early_exit.py
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import build_fifo_slides as kit
import build_loopopt_slides as lo
from build_fifo_slides import (L, TEXT, Ids, b1, b2, card, label, para, sldnum_ph, table,
                               textbox, title_ph)

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "units/unit07_loopopt/loopopt.pptx"
NEW_TITLES = ["Early Termination", "Pipelining by Hand", "The Stages in Hardware",
              "Three Ways to Stop"]
AFTER = "The Adder Pipeline"

EXIT_CODE = """
// x: ap_int<16>.  Keep the first NZ
// squares above zmin, then stop.
int j = 0;
for (int i = 0; i < NX; i++) {
#pragma HLS PIPELINE II=1
    int zi = x[i] * x[i];
    if (zi > zmin) {
        z[j] = zi;  j++;
    }
    if (j >= NZ) break;
}"""


def s_exit(ids):
    return [title_ph(ids, NEW_TITLES[0]),
            lo.code(ids, L, 1.75, 5.2, EXIT_CODE, sz=12),
            lo.pic(ids, "occ_exit", 6.2, 1.7, 6.35, 2.4),
            textbox(ids, 6.2, 4.25, 6.35, 1.9, [
                b1("Iteration i + 1 may start only once iteration i **did not break**", sz=15,
                   spcBef=0),
                b1("That needs j, **produced in S2**: so **II ≥ 3**", sz=15),
                b1("Asked for II = 1, Vitis **packs the iteration into one cycle** instead: "
                   "an estimated **16.3 ns**, at a 10 ns target", sz=15)]),
            textbox(ids, L, 5.0, 5.2, 1.0, [
                b1("A break **on data** is a loop-carried dependency", sz=15, spcBef=0),
                b2("A break on a counter, if (i >= n), is decided in S0: no limit", sz=13)]),
            sldnum_ph(ids)]


PIPE_CODE = """
ap_int<16> xr;  bool vx = false;
int        zr;  bool vz = false;
int j = 0;
for (int i = 0; i < NX + 2; i++) {
#pragma HLS PIPELINE II=1
    if (j >= NZ) break;
    if (vz && zr > zmin) {     // test x[i-2]
        z[j] = zr;  j++;
    }
    zr = xr * xr;  vz = vx;    // square x[i-1]
    vx = (i < NX);             // read x[i]
    if (vx) xr = x[i];
}"""


def s_pipe(ids):
    return [title_ph(ids, NEW_TITLES[1]),
            lo.code(ids, L, 1.75, 5.2, PIPE_CODE, sz=12),
            lo.pic(ids, "occ_exit_pipe", 6.2, 1.65, 6.35, 2.75),
            textbox(ids, 6.2, 4.5, 6.35, 1.7, [
                b1("Each iteration works on **three samples**", sz=15, spcBef=0),
                b1("Written **last stage first**: each line reads the register the iteration "
                   "before set", sz=15),
                b2("vx, vz: does the register hold a sample?  So xr, zr need no reset", sz=13),
                b2("NX + 2 iterations drain the last two samples", sz=13),
                b1("The exit needs only **j**: produced in the test, needed in the next test",
                   sz=15)]),
            lo.portal_caption(ids, "Early exit by hand"), sldnum_ph(ids)]


def s_hw(ids):
    return [title_ph(ids, NEW_TITLES[2]),
            lo.pic(ids, "exit_pipe", L, 1.75, 7.7, 4.0),
            lo.col(ids, 8.55, 4.0, [
                "xr, zr and j are the **stage registers**",
                "The square has a cycle of its own, between xr and zr",
                "The exit path is **one compare after the j register**, however long the "
                "square takes",
                "The break is **exact**: it stops 3 cycles after z fills"],
                y=1.85, h=3.9, sz=16),
            label(ids, L, 5.95, 12.0, 0.32, "Vitis HLS 2025.1 at 10 ns: II = 1, an estimated "
                  "6.53 ns.  C simulation and RTL co-simulation match the loop as written.",
                  sz=12),
            sldnum_ph(ids)]


GUARD_CODE = """
for (int i = 0; i < NX; i++) {
#pragma HLS PIPELINE II=1
    int zi = x[i] * x[i];
    if (zi > zmin && j < NZ) {
        z[j] = zi;  j++;
    }
}"""


def s_compare(ids):
    rows = lo.ctr([["", "II", "Clock", "Cycles", "Time"],
                   ["As written", "1", "16.3 ns ✗", "66 – 258", "1.1 – 4.2 µs"],
                   ["No break", "1", "6.8 ns", "260", "2.6 µs"],
                   ["By hand", "1", "6.5 ns", "66 – 260", "0.66 – 2.6 µs"]])
    return [title_ph(ids, NEW_TITLES[3]),
            table(ids, L, 1.8, [1.75, 0.6, 1.35, 1.3, 1.6], rows, rowh=0.46, sz=15),
            label(ids, L, 3.75, 6.6, 0.6, "Vitis HLS 2025.1, a 10 ns target.  Cycles depend on "
                  "when z fills: at least NZ = 64 samples.", sz=12),
            lo.code(ids, 7.55, 1.8, 5.0, GUARD_CODE, sz=12),
            label(ids, 7.55, 3.62, 5.0, 0.35, "No break: stop writing, not looping", sz=12),
            card(ids, L, 4.45, 12.0, 1.0, [
                para("A break is free when its test is **cheap and early**.  When it needs "
                     "this iteration's results, either **drop the break** and run every "
                     "iteration, or **move the work into earlier iterations** so the test reads "
                     "only registers.", sz=16, color=TEXT)]),
            sldnum_ph(ids)]


def main() -> None:
    work = Path(tempfile.gettempdir()) / "loopopt_early_exit"
    build = (work / "unpacked").resolve()
    if build.exists():
        shutil.rmtree(build)
    zipfile.ZipFile(DECK).extractall(build)
    slides = build / "ppt" / "slides"
    kit.BUILD, kit.SLIDES = build, slides
    lo.BUILD, lo.SLIDES = build, slides
    lo.FIGS = (ROOT / "units/unit07_loopopt/figs").resolve()

    order = kit.slide_order()
    titles = [kit.slide_title(n).strip() for n in order]
    if NEW_TITLES[0] in titles:
        raise SystemExit(f"{DECK.name} already has {NEW_TITLES[0]!r}.")

    def one(title):
        hits = [k for k, t in enumerate(titles) if t == title]
        if len(hits) != 1:
            raise SystemExit(f"expected one slide titled {title!r}, found {len(hits)}")
        return hits[0]

    after = one(AFTER)
    # Duplicates of the merge table slide, which has the content layout and
    # no pictures, each rewritten whole.
    donor = order[one("Merge Example")]
    assert (slides / "_rels" / f"{donor}.rels").read_text(encoding="utf-8") \
        .count("<Relationship ") == 1, f"{donor} has pictures; pick another donor"
    made = []
    for _ in NEW_TITLES:
        out = kit.sh([sys.executable, "add_slide.py", str(build), donor],
                     cwd=kit._find_skill_scripts())
        made.append(re.search(r"Created ppt/slides/(slide\d+\.xml)", out).group(1))
    kit.set_order(order[:after + 1] + made + order[after + 1:])

    for name, build_slide in zip(made, [s_exit, s_pipe, s_hw, s_compare]):
        lo.write(name, build_slide(Ids()))
    print(kit.sh([sys.executable, "clean.py", str(build)], cwd=kit._find_skill_scripts()).strip())
    kit.pack(DECK)
    print(f"added {', '.join(map(repr, NEW_TITLES))} as slides {after + 2} to "
          f"{after + 1 + len(NEW_TITLES)}; wrote {DECK}")


if __name__ == "__main__":
    main()
