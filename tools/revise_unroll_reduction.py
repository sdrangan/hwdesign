"""Rework unit 8's "Unrolling a Reduction" section to reason stage by stage.

A one-shot edit of unroll.pptx, the deck tools/build_unroll_slides.py made,
with the same drawing kit; it refuses to run twice.  Every variant of the
float sum is written out as the stages of one iteration, with the float adder
as four stages, sum1 to sum4, and the II read off the loop-carried
dependency:

    sum read in stage Sr, written in stage Sw:   II >= Sw - Sr + 1

What changes, in the section that starts at "Unrolling a Sum":

  * new, after it: "A Float Sum, Stage by Stage": the adder's stages, the
    rolled loop's stages, a cycle table of three iterations at II = 4
  * "Unrolling a Float Sum": the unrolled chain's stages, S1 to S16
  * "Rewriting the Body" becomes "Rewriting the Body: a Tree", with its
    stages, and a new "Rewriting the Body: Four Lanes" follows it
  * the practice and solution slides: the solution reasons in stages
  * the stage slide says why the pragmas keep "II=1".  Measured on demos/fsum,
    Vitis HLS 2025.1: with PIPELINE alone the log says "Target II = NA" and
    the rolled loop settles at II = 6 (21 unrolled by 4, 6 for the tree and
    lanes).  With II=1 it tries II = 1, 2, 3, reports each violation
    (HLS 200-880), and reaches 4: the target makes the scheduler work.

From the repo root, with the deck closed in PowerPoint:

    python tools/revise_unroll_reduction.py
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
import build_unroll_slides as ub
from build_fifo_slides import (AMBER, TEAL, TEXT, Ids, b1, b2, card, heading, label, para,
                               part, pill, sldnum_ph, table, textbox, title_ph)

ROOT = Path(__file__).resolve().parent.parent
L = kit.L
code, col, ctr, errcard, pic = lo.code, lo.col, lo.ctr, lo.errcard, lo.pic
portal_caption = ub.portal_caption

NEW_STAGES = "A Float Sum, Stage by Stage"
NEW_LANES = "Rewriting the Body: Four Lanes"
SECTION = ["Unrolling a Sum", "Unrolling a Float Sum", "Rewriting the Body",
           "Unrolling a Float Sum", "Unrolling a Float Sum", "In Class: Unrolling a Dot Product"]

PRAGMA_NOTE = ("Why `II=1` when it cannot be met?  It is a target: Vitis tries II = 1, 2, "
               "3, reports each violation (HLS 200-880) and settles at 4.  With `PIPELINE` "
               "alone, \"Target II = NA\": it stopped at **6**.")


def rule(ids, x, y, w, h, write, read, extra=None, sz=15):
    """The II read off a loop-carried dependency, as a card."""
    ii = write - read + 1
    paras = [para(f"Dependency from **S{write}** back to **S{read}**", sz=sz, color=TEXT),
             para(f"II ≥ {write} − {read} + 1 = **{ii}**", sz=sz + 2, color=TEXT, spcBef=4)]
    if extra:
        paras.append(para(extra, sz=sz - 2, color=TEXT, spcBef=4))
    return card(ids, x, y, w, h, paras)


# --------------------------------------------------------------- the int sum
DOT4 = """
#pragma HLS ARRAY_PARTITION variable=a type=cyclic factor=4
#pragma HLS ARRAY_PARTITION variable=b type=cyclic factor=4
int sum = 0;
for (int i = 0; i < N; i += 4) {
#pragma HLS PIPELINE II=1
    sum += a[i]*b[i]     + a[i+1]*b[i+1]
         + a[i+2]*b[i+2] + a[i+3]*b[i+3];
}"""


def s_int_sum(ids):
    rows = [["Dot product, N = 256", "II", "Cycles", "DSP"],
            ["plain loop", "1", "261", "1"], ["unrolled by 4", "1", "70", "4"],
            ["unrolled by 8", "1", "38", "8"]]
    return [title_ph(ids, "Unrolling a Sum"),
            col(ids, L, 6.6, [
                "A sum carries **sum** from one iteration to the next",
                "Unrolled, the products are added **among themselves** first: a tree",
                ("-", "Only the last add is on the loop-carried path"),
                "An int add fits in **one stage**: sum is read and written in the same "
                "stage, so II = 1 with one accumulator"], h=2.3, sz=16, sub=14),
            code(ids, L, 4.05, 6.6, DOT4, sz=11, inset=0.1),
            pic(ids, "adder_tree", 7.6, 1.65, 4.95, 3.0),
            table(ids, 7.6, 4.75, [2.45, 0.6, 1.0, 0.7], ctr(rows), rowh=0.36, sz=12),
            sldnum_ph(ids)]


# --------------------------------------------------- the rolled float sum
ADDER = """
z1 = sum1(a, b)
z2 = sum2(z1)
z3 = sum3(z2)
z4 = sum4(z3)        // = a + b"""

ROLLED = """
// sum += x[i], one iteration
S0:  xi <= x[i];  i <= i + 1
S1:  z1 = sum1(xi, sum)   // reads sum
S2:  z2 = sum2(z1)
S3:  z3 = sum3(z2)
S4:  sum = sum4(z3)       // writes sum"""


def s_stages(ids):
    rows = [["Cycle", "iteration 0", "iteration 1", "iteration 2"]]
    for t in range(10):
        row = [str(t)]
        for it in range(3):
            s = t - 4 * it
            cell = f"S{s}" if 0 <= s <= 4 else ""
            if (it, s) == (0, 4):
                cell = {"t": "S4: writes sum", "align": "ctr", "color": TEAL}
            elif (it, s) == (1, 1):
                cell = {"t": "S1: reads it", "align": "ctr", "color": TEAL}
            row.append(cell)
        rows.append(row)
    return [title_ph(ids, NEW_STAGES),
            heading(ids, L, 1.7, 5.6, "THE FLOAT ADDER: FOUR STAGES, ONE CYCLE EACH"),
            code(ids, L, 2.0, 5.6, ADDER, sz=11),
            label(ids, L, 3.02, 5.6, 0.35, "A new, independent add can enter sum1 every cycle.",
                  sz=12),
            heading(ids, L, 3.45, 5.6, "THE ROLLED LOOP"),
            code(ids, L, 3.75, 5.6, ROLLED, sz=11),
            card(ids, L, 5.7, 5.6, 0.85, [para(PRAGMA_NOTE, sz=12, color=TEXT)],
                 fill=kit.AMBERTINT),
            table(ids, 6.75, 1.7, [0.8, 1.6, 1.6, 1.6], ctr(rows), rowh=0.34, sz=12),
            rule(ids, 6.75, 5.7, 5.8, 0.85, 4, 1),
            sldnum_ph(ids)]


# --------------------------------------------------- unrolled by the pragma
FSUM_PRAGMA = """
for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=4
    sum += x[i];
}"""

CHAIN = """
S0–S3:    x0..x3 <= x[i..i+3]   // one a cycle
S1–S4:    z = sum + x0          // reads sum
S5–S8:    z = z + x1
S9–S12:   z = z + x2
S13–S16:  sum = z + x3          // writes sum"""


def s_float_sum(ids):
    rows = [["sum of 1024 floats", "II", "Iterations", "Cycles"],
            ["rolled: sum += x[i]", "4", "1024", "4,100"],
            [{"t": "UNROLL factor=4", "align": "ctr", "color": AMBER},
             {"t": "16", "align": "ctr", "color": AMBER}, "256",
             {"t": "4,099", "align": "ctr", "color": AMBER}]]
    return [title_ph(ids, "Unrolling a Float Sum"),
            code(ids, L, 1.7, 5.9, FSUM_PRAGMA, sz=12),
            code(ids, L, 3.12, 5.9, CHAIN, sz=12),
            table(ids, L, 4.85, [2.6, 0.7, 1.3, 1.3], ctr(rows), rowh=0.38, sz=13),
            col(ids, 6.95, 5.6, [
                "Four copies of `sum += x[i]`, **in order**: "
                "(((sum + x0) + x1) + x2) + x3",
                ("-", "Vitis keeps the order of float adds: reordering changes the "
                      "rounding"),
                "Four adds in a chain through sum: 16 stages"], y=1.7, h=2.2, sz=15,
                sub=13),
            rule(ids, 6.95, 3.95, 5.6, 1.25, 16, 1,
                 "A quarter of the iterations, each 4× longer: **no faster at all**"),
            label(ids, 6.95, 5.35, 5.6, 0.9, "demos/fsum, Vitis HLS 2025.1 at 100 MHz; the log "
                  "reports HLS 200-880, a carried dependence on sum.  reduction.md in the demo "
                  "docs.", sz=12),
            sldnum_ph(ids)]


# ------------------------------------------------------------- the tree
TREE = """
for (int i = 0; i < N; i += 4) {
#pragma HLS PIPELINE II=1
    sum += (x[i] + x[i+1]) + (x[i+2] + x[i+3]);
}"""

TREE_STAGES = """
S0–S3:    x0..x3 <= x[i..i+3]   // one a cycle
S2–S5:    a = x0 + x1
S4–S7:    b = x2 + x3
S8–S11:   t = a + b
S12–S15:  sum = sum + t         // reads, writes sum"""


def s_tree(ids):
    rows = [["sum of 1024 floats", "II", "Iterations", "Cycles"],
            ["rolled", "4", "1024", "4,100"],
            [{"t": "tree", "align": "ctr", "color": TEAL}, "4", "256",
             {"t": "1,042", "align": "ctr", "color": TEAL}]]
    return [title_ph(ids, "Rewriting the Body: a Tree"),
            code(ids, L, 1.7, 6.3, TREE, sz=12),
            code(ids, L, 2.97, 6.3, TREE_STAGES, sz=12),
            table(ids, L, 4.75, [2.6, 0.7, 1.3, 1.3], ctr(rows), rowh=0.38, sz=13),
            col(ids, 7.35, 5.2, [
                "Add the four samples **among themselves** first",
                ("-", "S2 to S11 do not touch sum: they run ahead"),
                "Only **one** add on the recurrence"], y=1.7, h=1.9, sz=15, sub=13),
            rule(ids, 7.35, 3.6, 5.2, 1.05, 15, 12, "for **four** samples: 4× faster"),
            textbox(ids, 7.35, 4.8, 5.2, 1.4, [
                b1("Four reads of x on one port take 4 cycles: II ≥ 4 there too.  They "
                   "fit: **no partition needed**", sz=14, spcBef=0),
                b1("You choose to reorder; the tool will not", sz=14, spcBef=6)]),
            sldnum_ph(ids)]


# ------------------------------------------------------------ four lanes
LANES = """
float part[4] = {0, 0, 0, 0};
#pragma HLS ARRAY_PARTITION variable=part type=complete
for (int i = 0; i < N; i += 4) {
#pragma HLS PIPELINE II=1
    for (int j = 0; j < 4; j++)
        part[j] += x[i + j];
}
sum = (part[0] + part[1]) + (part[2] + part[3]);"""

LANE_STAGES = """
S0–S3:  x0..x3 <= x[i..i+3]
S1–S4:  part[0] = part[0] + x0
S2–S5:  part[1] = part[1] + x1
S3–S6:  part[2] = part[2] + x2
S4–S7:  part[3] = part[3] + x3"""


def s_lanes(ids):
    rows = [["", "II", "Iterations", "Cycles", "DSP"],
            ["tree", "4", "256", "1,042", "2"], ["lanes", "4", "256", "1,042", "4"]]
    return [title_ph(ids, NEW_LANES),
            code(ids, L, 1.7, 6.6, LANES, sz=11),
            code(ids, L, 3.85, 6.6, LANE_STAGES, sz=12),
            col(ids, 7.6, 4.95, [
                "Four running sums, one per sample: unit 7's partial sums as an unrolled "
                "loop",
                "Each part[j] is read in S(1 + j) and written in S(4 + j)"],
                y=1.7, h=1.9, sz=15),
            rule(ids, 7.6, 3.35, 4.95, 0.85, 4, 1),
            table(ids, 7.6, 4.35, [1.0, 0.6, 1.2, 1.0, 0.75], ctr(rows), rowh=0.36, sz=12),
            label(ids, L, 5.9, W_, 0.5, "The same speed as the tree, with an adder per lane.  "
                  "Both are now at the port's limit too: four reads of x, one port.", sz=13,
                  color=TEXT),
            sldnum_ph(ids)]


W_ = kit.W


# ------------------------------------------------------ practice, solution
def s_fsum_practice(ids):
    return [title_ph(ids, "Unrolling a Float Sum"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 7.3, 4.3, [
                para("sum of N = 1024 floats in x, one port.  A float add is four stages, "
                     "sum1 to sum4; a new, independent add can enter sum1 every cycle.",
                     sz=15, color=TEXT, spcAft=2),
                part("(a)", "The plain loop, `sum += x[i]`: its stages, the II and the cycles",
                     15),
                part("(b)", "With `UNROLL factor=4`, which keeps the order of the adds: the "
                            "body, its stages, the II and the cycles", 15),
                part("(c)", "Rewrite the unrolled body with one add on the recurrence: its "
                            "stages, II, cycles.  Must x be partitioned?", 15),
                part("(d)", "The same, unrolled by 8: II and cycles with x in one memory, "
                            "then cyclic factor 2", 15)]),
            code(ids, 8.35, 1.85, 4.2, "\nfloat sum = 0;\nfor (int i = 0; i < N; i++) {\n"
                 "#pragma HLS PIPELINE II=1\n    sum += x[i];\n}", sz=12),
            portal_caption(ids, "Unrolling a float sum"), sldnum_ph(ids)]


def s_fsum_solution(ids):
    return [title_ph(ids, "Unrolling a Float Sum"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 7.3, 4.3, [
                part("(a)", "S0 reads x[i]; sum read in !!S1!!, written in !!S4!!: II ≥ 4 − 1 "
                            "+ 1 = !!4!!, about !!4,096 cycles!!", 14, spcBef=0),
                part("(b)", "(((sum + x0) + x1) + x2) + x3: four adds in a chain, sum read "
                            "in S1, written in S16: !!II = 16!!, 256 × 16 ≈ !!4,096!!: no "
                            "gain", 14),
                part("(c)", "sum += (x0 + x1) + (x2 + x3): S2 to S11 run ahead; sum read in "
                            "S12, written in S15: !!II = 4!!, 256 × 4 ≈ !!1,024!!.  No "
                            "partition: 4 reads fit in the 4 cycles", 14),
                part("(d)", "8 reads, one port: !!II = 8!!, 128 × 8 ≈ 1,024, no better.  "
                            "Two banks: 4 reads each, !!II = 4!!, about !!512!!", 14)]),
            errcard(ids, 8.35, 1.8, 4.2, 2.4, "Common error",
                    ["Unrolled by 4, so 4× faster: not while the four adds are a chain "
                     "through sum."]),
            label(ids, 8.35, 4.4, 4.2, 1.5, "Measured (demos/fsum): 4,100, 4,099 and 1,042 "
                  "cycles for (a) to (c).", sz=12),
            portal_caption(ids, "Unrolling a float sum"), sldnum_ph(ids)]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--deck", type=Path, default=ROOT / "units/unit08_unroll/unroll.pptx")
    p.add_argument("--out", type=Path, default=None, help="default: overwrite --deck")
    p.add_argument("--work", type=Path, default=Path(tempfile.gettempdir()) / "unroll_red")
    p.add_argument("--skill-scripts", type=Path, default=None)
    a = p.parse_args()
    scripts = a.skill_scripts or kit._find_skill_scripts()
    out = a.out or a.deck

    build = (a.work / "unpacked").resolve()
    slides = build / "ppt" / "slides"
    kit.BUILD, kit.SLIDES = build, slides
    lo.BUILD, lo.SLIDES, lo.FIGS = build, slides, (ROOT / "units/unit08_unroll/figs").resolve()
    if build.exists():
        shutil.rmtree(build)
    zipfile.ZipFile(a.deck).extractall(build)

    order = kit.slide_order()
    titles = [kit.slide_title(n).strip() for n in order]
    if NEW_STAGES in titles:
        raise SystemExit(f"{a.deck.name} already has {NEW_STAGES!r}: it has been revised")
    k = titles.index(SECTION[0])
    if titles[k:k + len(SECTION)] != SECTION:
        raise SystemExit(f"expected {SECTION} from slide {k + 1}, found "
                         f"{titles[k:k + len(SECTION)]}")
    int_s, float_s, fix_s, prac_s, soln_s = order[k:k + 5]

    def new_slide():
        donor = next(n for n, t in zip(order, titles) if t == "Outline"
                     and (slides / "_rels" / f"{n}.rels").read_text(encoding="utf-8")
                     .count("<Relationship ") == 1)
        made = kit.sh([sys.executable, "add_slide.py", str(build), donor], cwd=scripts)
        return re.search(r"Created ppt/slides/(slide\d+\.xml)", made).group(1)

    stages_s, lanes_s = new_slide(), new_slide()
    kit.set_order(order[:k] + [int_s, stages_s, float_s, fix_s, lanes_s, prac_s, soln_s]
                  + order[k + 5:])
    for name, fn in [(int_s, s_int_sum), (stages_s, s_stages), (float_s, s_float_sum),
                     (fix_s, s_tree), (lanes_s, s_lanes), (prac_s, s_fsum_practice),
                     (soln_s, s_fsum_solution)]:
        lo.write(name, fn(Ids()))

    print(kit.sh([sys.executable, "clean.py", str(build)], cwd=scripts).strip())
    kit.pack(out)
    print(f"wrote {out}: slides {k + 1} to {k + 7} are the reworked section, "
          f"{len(order) + 2} slides in all")


if __name__ == "__main__":
    main()
