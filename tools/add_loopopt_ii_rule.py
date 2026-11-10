"""Teach one procedure for the minimum II in unit 7's "Limits on the II".

Adds a slide, "Finding the Minimum II", at the start of the section, and
rewrites the two slides after the merge example to use it:

  * write one iteration stage by stage, one clock cycle per stage, a load in
    a stage of its own and a k-cycle operation over k stages
  * for each value carried to the next iteration, note the stage Sn that
    produces it and the stage Sm of the next iteration that needs it
  * then II >= n - m + 1, the largest over the carried values.  Iteration i
    starts in cycle t, so Sn ends at t + n; iteration i+1's Sm starts at
    t + II + m, which must be later.

Worked on sum += x[i] (S1 needs S1: II = 1), then merge (S0 needs S1:
II = 2) and a running product through a 4-cycle multiply (S1 needs S4:
II = 4).  The homework's rule, "Stage 0 depends on Stage k gives II = k + 1"
(Loop carry dependency in loopopt.xml), is its m = 0 case.

Like add_loopopt_inclass_slide.py, it edits loopopt.pptx in place once, with
build_loopopt_slides.py's helpers, and refuses to run twice.  Regenerate the
figures first (make_figs.py: occ_sum, occ_merge, occ_float), and close the
deck in PowerPoint.

    python tools/add_loopopt_ii_rule.py
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
from build_fifo_slides import (L, TEXT, Ids, b1, b2, card, para, sldnum_ph, textbox,
                               title_ph)

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "units/unit07_loopopt/loopopt.pptx"
NEW_TITLE = "Finding the Minimum II"

SUM_CODE = """
int sum = 0;
for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
    sum += x[i];
}
// S0: x0 <= x[i]        a load takes a cycle
// S1: sum <= sum + x0   a one-cycle add"""


def s_ii_rule(ids):
    return [title_ph(ids, NEW_TITLE),
            textbox(ids, L, 1.75, 6.1, 4.3, [
                b1("**1.**  Write one iteration **stage by stage**, one cycle per stage", sz=16,
                   spcBef=0),
                b2("A load takes a stage of its own; a k-cycle operation, k stages", sz=14),
                b1("**2.**  For each value carried to the next iteration: the stage **S_{n}** "
                   "that produces it, and the stage **S_{m}** of the next iteration that "
                   "needs it", sz=16),
                b1("**3.**  Then **II ≥ n − m + 1**; take the largest", sz=16),
                b2("Iteration i starts in cycle t: S_{n} ends at t + n", sz=14),
                b2("Iteration i + 1's S_{m} starts at t + II + m, which must be later", sz=14),
                b2("If n < m, the value is ready in time: no limit beyond II = 1", sz=14)]),
            lo.code(ids, 7.05, 1.75, 5.5, SUM_CODE, sz=11, inset=0.1),
            lo.pic(ids, "occ_sum", 7.05, 3.55, 5.5, 2.6),
            sldnum_ph(ids)]


MERGE_STAGES = """
// S0: read at i and j
x1i <= x1[i];
x2j <= x2[j];
// S1: compare, and advance i or j
if (x1i < x2j) begin
    yk <= x1i;  i <= i + 1;
end else begin
    yk <= x2j;  j <= j + 1;
end
// S2: write
y[k] <= yk;  k <= k + 1;"""


def s_merge_limit(ids):
    return [title_ph(ids, "The Pipelining Limit"),
            lo.code(ids, L, 1.75, 5.0, MERGE_STAGES, sz=12),
            lo.pic(ids, "occ_merge", 6.0, 1.7, 6.55, 3.1),
            textbox(ids, 6.0, 4.9, 6.55, 1.2, [
                b1("i and j are **produced in S1** and **needed in S0** of the next "
                   "iteration", sz=15, spcBef=0),
                b1("So **II ≥ 1 − 0 + 1 = 2**: a **loop-carried dependency**", sz=15)]),
            lo.homework(ids, "Loop carry dependency"), sldnum_ph(ids)]


PROD_CODE = """
float prod = 1;
for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
    prod *= x[i];
}"""


def s_float(ids):
    return [title_ph(ids, "A Multi-Cycle Recurrence"),
            lo.col(ids, L, 5.4, [
                "A float multiply takes several cycles: say **4**",
                ("-", "S0: load x[i];  S1 to S4: the multiply"),
                "prod is **produced at the end of S4** and **needed in S1** of the next "
                "iteration",
                "So **II ≥ 4 − 1 + 1 = 4**, whatever the pragma asks",
                ("-", "The multiplier is pipelined, but the next multiply's input is not ready"),
                ("-", "Vitis reports the II it achieved, and warns")], h=3.3, sz=16, sub=14),
            lo.code(ids, L, 5.0, 5.4, PROD_CODE, sz=11, inset=0.1),
            lo.pic(ids, "occ_float", 6.45, 1.75, 6.1, 3.0),
            card(ids, 6.45, 5.0, 6.1, 1.0, [
                para("The same rule as before: a multi-cycle operation just spans more "
                     "stages.", sz=15, color=TEXT)]),
            sldnum_ph(ids)]


def main() -> None:
    work = Path(tempfile.gettempdir()) / "loopopt_ii_rule"
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
    if NEW_TITLE in titles:
        raise SystemExit(f"{DECK.name} already has {NEW_TITLE!r}.")

    def one(title):
        hits = [k for k, t in enumerate(titles) if t == title]
        if len(hits) != 1:
            raise SystemExit(f"expected one slide titled {title!r}, found {len(hits)}")
        return hits[0]

    limit, multi = one("The Pipelining Limit"), one("A Multi-Cycle Recurrence")
    outline = max(k for k, t in enumerate(titles) if t == "Outline")
    assert outline < limit < multi, "the section's slides are not in the expected order"

    # The new slide: a duplicate of the merge table slide, which has the
    # content layout and no pictures, rewritten whole.
    donor = order[one("Merge Example")]
    assert (slides / "_rels" / f"{donor}.rels").read_text(encoding="utf-8") \
        .count("<Relationship ") == 1, f"{donor} has pictures; pick another donor"
    made = kit.sh([sys.executable, "add_slide.py", str(build), donor],
                  cwd=kit._find_skill_scripts())
    name = re.search(r"Created ppt/slides/(slide\d+\.xml)", made).group(1)
    kit.set_order(order[:outline + 1] + [name] + order[outline + 1:])

    lo.write(name, s_ii_rule(Ids()))
    lo.write(order[limit], s_merge_limit(Ids()))
    lo.write(order[multi], s_float(Ids()))
    print(kit.sh([sys.executable, "clean.py", str(build)], cwd=kit._find_skill_scripts()).strip())
    kit.pack(DECK)
    print(f"added {NEW_TITLE!r} as slide {outline + 2}; rewrote slides {limit + 2} and "
          f"{multi + 2}; wrote {DECK}")


if __name__ == "__main__":
    main()
