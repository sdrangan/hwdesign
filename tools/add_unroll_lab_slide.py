"""Add the stereo lab's slide to unit 8's deck, unroll.pptx, after "What to Take Away".

A one-shot edit of the deck tools/build_unroll_slides.py made, with the same
drawing kit: it refuses to run on a deck that already has the slide.  The
numbers are the reference solution's (docs/labs/stereo), Vitis HLS 2025.1,
Zynq-7020 at 100 MHz.

From the repo root, with the deck closed in PowerPoint:

    python tools/add_unroll_lab_slide.py
    tools/render_slides.ps1 -Deck units/unit08_unroll/unroll.pptx -OutDir out
"""
import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import build_fifo_slides as kit
import build_loopopt_slides as lo
from build_fifo_slides import (L, TEAL, TEALLINE, TEALTINT, TEXT, VIOLET, W, WHITE, Ids, b1,
                               label, para, shape, sldnum_ph, table, textbox, title_ph)

ROOT = Path(__file__).resolve().parent.parent
TITLE = "Lab: Stereo Depth"
AFTER = "What to Take Away"


def s_lab(ids):
    rows = [["Stage", "You write", "Reference result"],
            ["1  Golden model", "shift an image; block-matching disparity map, in Python",
             "the scene's three depths"],
            ["2  Baseline", "the kernel, bit exact, every loop unpipelined",
             "17.2 M cycles a frame"],
            ["3  Optimized", "partitioned rows, window registers: compute at II = 1",
             {"t": "36,378 cycles", "align": "ctr", "color": TEAL}],
            ["4  Co-simulation", "find load, compute and store in the RTL's handshakes",
             "a third of the call each"]]
    return [title_ph(ids, TITLE),
            shape(ids, 10.55, 0.68, 1.6, 0.42, fill=VIOLET, prst="roundRect", adj=50000,
                  paras=[para("TAKE-HOME", sz=13, color=WHITE, b=True, align="ctr")]),
            textbox(ids, L, 1.6, 5.9, 2.0, [
                b1("Two cameras: a nearer point shifts **further** between the images.  That "
                   "shift, the **disparity**, is depth", sz=14, spcBef=0),
                b1("Each pixel: a 5×5 window of the left image against **16** shifts of the "
                   "right; the smallest sum of absolute differences wins", sz=14, spcBef=6),
                b1("96 × 128 pixels, **400** absolute differences each", sz=14, spcBef=6)]),
            lo.pic(ids, "stereo/disparity", 6.85, 1.6, 5.7, 1.95),
            table(ids, L, 3.45, [2.2, 6.2, 3.4], lo.ctr(rows), rowh=0.38, sz=13),
            shape(ids, L, 5.5, W, 0.5, fill=VIOLET, prst="roundRect", adj=16000, paras=[
                para(f"{kit.DOCS_URL}  —  Labs › Stereo Depth  —  code in labs/stereo",
                     sz=15, color=WHITE, b=True, align="ctr")]),
            shape(ids, L, 6.1, W, 0.42, fill=TEALTINT, line=TEALLINE, lw=1.0, paras=[
                para("The three phases do **not** overlap: the compute waits for the whole "
                     "frame.  Why, and what to do about it, is the next unit.", sz=13,
                     color=TEXT, align="ctr")]),
            sldnum_ph(ids)]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--deck", type=Path, default=ROOT / "units/unit08_unroll/unroll.pptx")
    p.add_argument("--out", type=Path, default=None, help="default: overwrite --deck")
    p.add_argument("--work", type=Path, default=Path(tempfile.gettempdir()) / "unroll_lab")
    p.add_argument("--skill-scripts", type=Path, default=None)
    a = p.parse_args()
    scripts = a.skill_scripts or kit._find_skill_scripts()
    out = a.out or a.deck

    build = (a.work / "unpacked").resolve()
    slides = build / "ppt" / "slides"
    kit.BUILD, kit.SLIDES = build, slides
    lo.BUILD, lo.SLIDES = build, slides
    lo.FIG_DIRS["stereo"] = ROOT / "docs/labs/stereo/images"
    if build.exists():
        shutil.rmtree(build)
    zipfile.ZipFile(a.deck).extractall(build)

    order = kit.slide_order()
    titles = [kit.slide_title(n).strip() for n in order]
    if TITLE in titles:
        raise SystemExit(f"{a.deck.name} already has {TITLE!r}")
    if AFTER not in titles:
        raise SystemExit(f"{a.deck.name} has no {AFTER!r} slide to follow")

    # The donor is a slide with only its layout relationship: an Outline slide.
    donor = next(n for n, t in zip(order, titles) if t == "Outline"
                 and (slides / "_rels" / f"{n}.rels").read_text(encoding="utf-8")
                 .count("<Relationship ") == 1)
    made = kit.sh([sys.executable, "add_slide.py", str(build), donor], cwd=scripts)
    name = re.search(r"Created ppt/slides/(slide\d+\.xml)", made).group(1)
    at = titles.index(AFTER) + 1
    kit.set_order(order[:at] + [name] + order[at:])
    lo.write(name, s_lab(Ids()))

    print(kit.sh([sys.executable, "clean.py", str(build)], cwd=scripts).strip())
    kit.pack(out)
    print(f"wrote {out}: {TITLE!r} is slide {at + 1} of {len(order) + 1}")


if __name__ == "__main__":
    main()
