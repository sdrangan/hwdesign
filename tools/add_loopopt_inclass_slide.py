"""Add the in-class exercise slide to unit 7, after the synthesis-report problem.

The exercise is demos/loopopt_inclass, walked through in
docs/demos/loopopt/inclass.md: y[i] = x[i]^2 + x[i-1]^2 with x and y in
single-port memories, where the obvious loop asks for II = 1 and gets 2.  The
slide goes at the end of the Vitis HLS section, after the "Reading the
Synthesis Report" solution, since the exercise is about reading that report.

Like build_loopopt_slides.py, whose helpers it uses, this edits the deck once
and refuses to run on a deck that already has the slide.  It writes
loopopt.pptx in place (the deck is tracked in git), so close it in PowerPoint
first.

    python tools/add_loopopt_inclass_slide.py
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
from build_fifo_slides import (CODEFILL, GRAYLINE, L, TEXT, VIOLET, WHITE, W, Ids, heading,
                               label, para, part, pill, shape, sldnum_ph, textbox, title_ph)

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "units/unit07_loopopt/loopopt.pptx"
TITLE = "In Class: One Read per Iteration"
AFTER = "Reading the Synthesis Report"      # the last slide of that title: the solution

LOOP = """
for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
    float prev = (i == 0) ? 0.0f : x[i-1];
    y[i] = x[i]*x[i] + prev*prev;
}"""


def s_inclass(ids):
    return [title_ph(ids, TITLE), pill(ids, "IN CLASS"),
            textbox(ids, L, 1.75, 6.5, 2.0, [
                para("y[i] = x[i]^{2} + x[i−1]^{2}, with x[−1] = 0.  x and y are block RAMs "
                     "with **one port each**.", sz=16, color=TEXT, spcAft=6),
                para("The obvious loop asks for II = 1.  The report says **II = 2**.",
                     sz=16, color=TEXT)]),
            lo.code(ids, L, 3.15, 6.5, LOOP, sz=13),
            textbox(ids, 7.55, 1.75, 5.0, 3.3, [
                part("(a)", "How many times does an iteration read x?  How many reads can the "
                            "memory do per cycle?", 15, spcBef=0),
                part("(b)", "Each x[k] is read by two iterations.  Which?", 15),
                part("(c)", "Rewrite the loop in `sqsum.cpp` to reach **II = 1**.  Keep x "
                            "single-port; y must still match the model", 15),
                part("(d)", "Optional: `--through timing`, and compare the x addresses "
                            "before and after", 15)]),
            heading(ids, 7.55, 5.0, 5.0, "RUN"),
            shape(ids, 7.55, 5.3, 5.0, 0.8, fill=CODEFILL, line=GRAYLINE, lw=1.0, anchor="t",
                  inset=0.12, paras=[para("`cd demos/loopopt_inclass`", sz=12),
                                     para("`python sqsum_build.py`", sz=12, spcBef=4)]),
            shape(ids, L, 5.3, 6.5, 0.8, fill=VIOLET, prst="roundRect", adj=16000, paras=[
                para(f"{kit.DOCS_URL}  —  Demos › Loop Optimization › In-Class Exercise",
                     sz=13, color=WHITE, b=True, align="ctr")]),
            label(ids, L, 6.2, W, 0.32, "Under a minute per build.  Only sqsum.cpp is edited; "
                  "the build checks it, synthesizes it beside the reference and prints both.",
                  sz=12),
            sldnum_ph(ids)]


def main() -> None:
    work = Path(tempfile.gettempdir()) / "loopopt_inclass_slide"
    build = (work / "unpacked").resolve()
    if build.exists():
        shutil.rmtree(build)
    zipfile.ZipFile(DECK).extractall(build)
    slides = build / "ppt" / "slides"
    kit.BUILD, kit.SLIDES = build, slides
    lo.BUILD, lo.SLIDES = build, slides
    lo.FIGS = (ROOT / "units/unit07_loopopt/figs").resolve()

    order = kit.slide_order()
    titles = [kit.slide_title(n) for n in order]
    if TITLE in titles:
        raise SystemExit(f"{DECK.name} already has {TITLE!r}.")
    pos = max(k for k, t in enumerate(titles) if t.strip() == AFTER)
    # The donor: the solution slide itself, which has the content layout and no
    # pictures (only its layout relationship).  Not just any slide with one
    # relationship -- the title slide has one too.
    donor = order[pos]
    assert (slides / "_rels" / f"{donor}.rels").read_text(encoding="utf-8")         .count("<Relationship ") == 1, f"{donor} has pictures; pick another donor"
    made = kit.sh([sys.executable, "add_slide.py", str(build), donor],
                  cwd=kit._find_skill_scripts())
    name = re.search(r"Created ppt/slides/(slide\d+\.xml)", made).group(1)
    kit.set_order(order[:pos + 1] + [name] + order[pos + 1:])
    lo.write(name, s_inclass(Ids()))
    kit.pack(DECK)
    print(f"added {TITLE!r} as slide {pos + 2} of {len(order) + 1}; wrote {DECK}")


if __name__ == "__main__":
    main()
