"""Add "How Many Adders?" to unit 8's deck, and correct the tree and lanes slides.

A one-shot edit after tools/revise_unroll_reduction.py; it refuses to run
twice.  What the fsum demo's schedules show (Vitis HLS 2025.1,
proj_*/sol/.autopilot/db/*.verbose.sched.rpt, the cycle each fadd enters its
adder):

    tree    cycles 4, 6, 11, 17   mod 4: 0, 2, 3, 1   one adder, always busy
    lanes   cycles 3, 4, 5, 6     mod 4: 3, 0, 1, 2   one adder, always busy

so inside the loop the two need the same hardware: adders >= adds per
iteration / II = 4 / 4.  Lanes' second adder (4 DSPs against 2) is the
epilogue, (part[0] + part[1]) and (part[2] + part[3]) scheduled in the same
cycle; its extra flip-flops are the four running sums.

  * "Rewriting the Body: a Tree": a schedule one adder can run, each add in
    its own slot mod 4: a in S2, b in S4, t in S9, sum in S15 to S18
  * "Rewriting the Body: Four Lanes": the false "an adder per lane" goes
  * new, after it, "How Many Adders?": the adder's stages sum1 to sum4,
    cycle by cycle in the steady state, for rolled, tree and lanes
  * the float-sum solution's (c) follows the new tree schedule

From the repo root, with the deck closed in PowerPoint:

    python tools/revise_unroll_adders.py
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
import revise_unroll_reduction as rr
from build_fifo_slides import (AMBER, TEAL, TEXT, Ids, b1, card, heading, label, para, part,
                               pill, sldnum_ph, table, textbox, title_ph)

ROOT = Path(__file__).resolve().parent.parent
L, W = kit.L, kit.W
code, col, ctr, errcard = lo.code, lo.col, lo.ctr, lo.errcard
rule = rr.rule

NEW = "How Many Adders?"
TREE_T, LANES_T = "Rewriting the Body: a Tree", rr.NEW_LANES

# Each add: (label, the stage it enters sum1), relative to its iteration's S0.
ADDS = {"rolled": [("s", 1)],
        "tree": [("a", 2), ("b", 4), ("t", 9), ("s", 15)],
        "lanes": [("p0", 1), ("p1", 2), ("p2", 3), ("p3", 4)]}
II = 4

TREE_STAGES = """
S0–S3:    x0..x3 <= x[i..i+3]   // one a cycle
S2–S5:    a = x0 + x1
S4–S7:    b = x2 + x3
S9–S12:   t = a + b             // a ready S6, b S8
S15–S18:  sum = sum + t         // reads, writes sum"""


def s_tree(ids):
    rows = [["sum of 1024 floats", "II", "Iterations", "Cycles"],
            ["rolled", "4", "1024", "4,100"],
            [{"t": "tree", "align": "ctr", "color": TEAL}, "4", "256",
             {"t": "1,042", "align": "ctr", "color": TEAL}]]
    return [title_ph(ids, TREE_T),
            code(ids, L, 1.7, 6.3, rr.TREE, sz=12),
            code(ids, L, 2.97, 6.3, TREE_STAGES, sz=12),
            table(ids, L, 4.85, [2.6, 0.7, 1.3, 1.3], ctr(rows), rowh=0.38, sz=13),
            col(ids, 7.35, 5.2, [
                "Add the four samples **among themselves** first",
                ("-", "a, b and t do not touch sum: they run ahead"),
                ("-", "Each add enters sum1 in a **different cycle mod 4**: one adder "
                      "can do all four"),
                "Only **one** add on the recurrence"], y=1.7, h=2.0, sz=15, sub=13),
            rule(ids, 7.35, 3.75, 5.2, 1.05, 18, 15, "for **four** samples: 4× faster"),
            textbox(ids, 7.35, 4.95, 5.2, 1.3, [
                b1("Four reads of x on one port: II ≥ 4 there too.  They fit: **no "
                   "partition needed**", sz=14, spcBef=0),
                b1("You choose to reorder; the tool will not", sz=14, spcBef=6)]),
            sldnum_ph(ids)]


def s_lanes(ids):
    rows = [["", "II", "Cycles", "DSP", "FF"],
            ["tree", "4", "1,042", "2", "510"], ["lanes", "4", "1,042", "4", "878"]]
    return [title_ph(ids, LANES_T),
            code(ids, L, 1.7, 6.6, rr.LANES, sz=11),
            code(ids, L, 3.85, 6.6, rr.LANE_STAGES, sz=12),
            col(ids, 7.6, 4.95, [
                "Four running sums, one per sample: unit 7's partial sums as an unrolled "
                "loop",
                "Each part[j] is read in S(1 + j) and written in S(4 + j)"],
                y=1.7, h=1.7, sz=15),
            rule(ids, 7.6, 3.35, 4.95, 0.85, 4, 1),
            table(ids, 7.6, 4.35, [1.0, 0.6, 1.1, 0.75, 0.9], ctr(rows), rowh=0.36, sz=12),
            label(ids, L, 5.9, W, 0.5, "The same speed as the tree.  More hardware: why?  "
                  "The next slide counts the adders.", sz=13, color=TEXT),
            sldnum_ph(ids)]


def occupancy(variant, t0=20):
    """Rows of the adder's stages in cycles t0 .. t0+3 of the steady state."""
    rows = [["Cycle", "sum1", "sum2", "sum3", "sum4"]]
    for t in range(t0, t0 + II):
        row = [str(t)]
        for j in range(4):                       # stage sum(j+1)
            cell = ""
            for name, s in ADDS[variant]:
                d = t - j - s                    # its iteration starts at cycle d
                if d >= 0 and d % II == 0:
                    assert not cell, f"{variant}: two adds in sum{j + 1} at cycle {t}"
                    cell = f"{name}({d // II})"
            row.append(cell)
        rows.append(row)
    return rows


def s_adders(ids):
    out = [title_ph(ids, NEW)]
    x, w = L, 3.75
    notes = {"rolled": "1 add per iteration: busy **1 cycle in 4**",
             "tree": "a, b, t, s: 4 adds, 4 slots: **always busy**",
             "lanes": "p0 to p3: 4 adds, 4 slots: **always busy**"}
    for k, v in enumerate(["rolled", "tree", "lanes"]):
        xx = x + k * (w + 0.26)
        out += [heading(ids, xx, 1.65, w, v.upper()),
                table(ids, xx, 1.95, [0.75, 0.75, 0.75, 0.75, 0.75],
                      ctr(occupancy(v)), rowh=0.36, sz=12),
                label(ids, xx, 3.85, w, 0.6, notes[v], sz=13, color=TEXT)]
    out += [card(ids, L, 4.55, 5.75, 1.6, [
                para("**One pipelined adder** takes a new add every cycle", sz=15,
                     color=TEXT),
                para("Adders ≥ adds per iteration ÷ II", sz=17, color=TEXT, spcBef=6),
                para("rolled 1 ÷ 4,  tree 4 ÷ 4,  lanes 4 ÷ 4: **one adder each**", sz=14,
                     color=TEXT, spcBef=6)]),
            textbox(ids, 6.75, 4.55, 5.8, 1.7, [
                b1("Unrolling did not add an adder: it **filled** the one there", sz=14,
                   spcBef=0),
                b1("Lanes' second adder is **after** the loop: part[0] + part[1] and "
                   "part[2] + part[3], scheduled in the same cycle", sz=14, spcBef=6),
                b1("Its extra flip-flops hold the four running sums", sz=14, spcBef=6)]),
            label(ids, L, 6.25, W, 0.32, "Cycles 20 to 23, when every iteration's adds are under way; a(5) is iteration 5's add a.  "
                  "Vitis's schedules for demos/fsum do the same: one adder, each add in its own "
                  "slot.", sz=11),
            sldnum_ph(ids)]
    return out


def s_fsum_solution(ids):
    shapes = rr.s_fsum_solution(ids)
    old = ("S2 to S11 run ahead; sum read in S12, written in S15")
    new = ("a, b, t run ahead; sum read in S15, written in S18")
    hits = [k for k, s in enumerate(shapes) if isinstance(s, str) and old in s]
    assert len(hits) == 1, "solution (c) text not found"
    shapes[hits[0]] = shapes[hits[0]].replace(old, new)
    return shapes


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--deck", type=Path, default=ROOT / "units/unit08_unroll/unroll.pptx")
    p.add_argument("--out", type=Path, default=None, help="default: overwrite --deck")
    p.add_argument("--work", type=Path, default=Path(tempfile.gettempdir()) / "unroll_add")
    p.add_argument("--skill-scripts", type=Path, default=None)
    a = p.parse_args()
    scripts = a.skill_scripts or kit._find_skill_scripts()
    out = a.out or a.deck

    build = (a.work / "unpacked").resolve()
    slides = build / "ppt" / "slides"
    kit.BUILD, kit.SLIDES = build, slides
    lo.BUILD, lo.SLIDES = build, slides
    if build.exists():
        shutil.rmtree(build)
    zipfile.ZipFile(a.deck).extractall(build)

    order = kit.slide_order()
    titles = [kit.slide_title(n).strip() for n in order]
    if NEW in titles:
        raise SystemExit(f"{a.deck.name} already has {NEW!r}")
    k = titles.index(TREE_T)
    want = [TREE_T, LANES_T, "Unrolling a Float Sum", "Unrolling a Float Sum"]
    if titles[k:k + 4] != want:
        raise SystemExit(f"expected {want} from slide {k + 1}, found {titles[k:k + 4]}")
    tree_s, lanes_s, _, soln_s = order[k:k + 4]

    donor = next(n for n, t in zip(order, titles) if t == "Outline"
                 and (slides / "_rels" / f"{n}.rels").read_text(encoding="utf-8")
                 .count("<Relationship ") == 1)
    made = kit.sh([sys.executable, "add_slide.py", str(build), donor], cwd=scripts)
    new_s = re.search(r"Created ppt/slides/(slide\d+\.xml)", made).group(1)
    kit.set_order(order[:k + 2] + [new_s] + order[k + 2:])
    for name, fn in [(tree_s, s_tree), (lanes_s, s_lanes), (new_s, s_adders),
                     (soln_s, s_fsum_solution)]:
        lo.write(name, fn(Ids()))

    print(kit.sh([sys.executable, "clean.py", str(build)], cwd=scripts).strip())
    kit.pack(out)
    print(f"wrote {out}: {NEW!r} is slide {k + 3} of {len(order) + 1}")


if __name__ == "__main__":
    main()
