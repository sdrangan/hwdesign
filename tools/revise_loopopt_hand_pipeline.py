"""Teach unit 7's "pipelining by hand" the way the Verilog pipelines are taught.

add_loopopt_early_exit.py showed the hand-pipelined early-exit loop as
finished code.  This walks to it in five slides, from "Pipelining by Hand"
to just before "Three Ways to Stop":

  * Pipelining by Hand -- the procedure, beside the computation graph of one
    iteration (exit_graph): draw the graph, cut it into stages, put a
    register named <value>_s<n> on every edge that crosses a cut, passing
    through what a later stage needs, write the body last stage first, and
    fill and drain with valid bits.
  * Cutting into Stages -- exit_stages: S0 read, S1 square, S2 test and
    write; j is produced and needed in S2.  Rewrites "The Stages in
    Hardware".
  * Naming the Registers -- exit_regs: x_s0, z_s1, and the valid bits
    v_s0, v_s1 passed down beside the data.
  * The Code, Last Stage First -- the loop in _sn names, beside the cycle
    chart; reverse order is what <= does in SystemVerilog.
  * Filling and Draining -- a table of which sample each stage holds at
    both ends, and the flush trick: loop to i < NX + 2, guard the read with
    v_s0 = (i < NX).

The loop is the one add_loopopt_early_exit.py measured, renamed (xr is x_s0,
zr is z_s1, vx is v_s0, vz is v_s1): Vitis HLS 2025.1, 10 ns, II = 1 at an
estimated 6.53 ns, matching the loop as written in C simulation and RTL
co-simulation.

Edits loopopt.pptx in place once and refuses to run twice.  Render the
figures first (make_figs.py: exit_graph, exit_stages, exit_regs,
occ_exit_pipe), and close the deck in PowerPoint.

    python tools/revise_loopopt_hand_pipeline.py
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
from build_fifo_slides import L, Ids, b1, b2, label, sldnum_ph, table, textbox, title_ph

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "units/unit07_loopopt/loopopt.pptx"
MARKER = "Naming the Registers"         # a slide only this script makes


def s_procedure(ids):
    return [title_ph(ids, "Pipelining by Hand"),
            textbox(ids, L, 1.75, 5.9, 4.4, [
                b1("**1.**  Draw the **computation graph** of one iteration", sz=16, spcBef=0),
                b1("**2.**  **Cut it into stages**, each one clock cycle", sz=16),
                b1("**3.**  Put a **register on every edge that crosses a cut**", sz=16),
                b2("Name it for the stage that writes it: z_s1 is z, written by S1", sz=14),
                b2("Pass through what a later stage needs: v_s1 = v_s0", sz=14),
                b1("**4.**  Write the body **last stage first**", sz=16),
                b1("**5.**  **Fill and drain** with valid bits", sz=16),
                b2("The same steps as pipelining in SystemVerilog", sz=14)]),
            lo.pic(ids, "exit_graph", 6.75, 1.85, 5.85, 3.4, align="t"),
            label(ids, 6.75, 4.5, 5.85, 0.35, "One iteration of the early-exit loop",
                  sz=12, align="ctr"),
            sldnum_ph(ids)]


def s_stages(ids):
    return [title_ph(ids, "Cutting into Stages"),
            lo.pic(ids, "exit_stages", L, 1.75, 7.7, 4.1),
            lo.col(ids, 8.55, 4.0, [
                "**S0** reads, **S1** squares, **S2** tests and writes",
                "Each stage must **fit one clock cycle**",
                "j is **produced and needed in S2**",
                ("-", "II ≥ 2 − 2 + 1 = 1"),
                "So the exit test reads only the **j register**"],
                y=1.85, h=4.0, sz=16, sub=15),
            sldnum_ph(ids)]


def s_regs(ids):
    return [title_ph(ids, MARKER),
            lo.pic(ids, "exit_regs", L, 1.75, 7.7, 4.1),
            lo.col(ids, 8.55, 4.0, [
                "A register wherever a value **crosses a cut**",
                "Named for the stage that writes it: **x_s0**, **z_s1**",
                "**Pass through** what a later stage needs: S2 must know z_s1 holds a "
                "sample, so **v_s1 = v_s0**",
                ("-", "Like x1_s1 in the multi-path example"),
                "Data registers need **no reset**; the valid bits do"],
                y=1.85, h=4.2, sz=16, sub=14),
            sldnum_ph(ids)]


CODE = """
ap_int<16> x_s0;  bool v_s0 = false;
int        z_s1;  bool v_s1 = false;
int j = 0;
for (int i = 0; i < NX + 2; i++) {
#pragma HLS PIPELINE II=1
    if (j >= NZ) break;
    // S2: test and write
    if (v_s1 && z_s1 > zmin) {
        z[j] = z_s1;  j++;
    }
    // S1: square
    z_s1 = x_s0 * x_s0;  v_s1 = v_s0;
    // S0: read
    v_s0 = (i < NX);
    if (v_s0) x_s0 = x[i];
}"""


def s_code(ids):
    return [title_ph(ids, "The Code, Last Stage First"),
            lo.code(ids, L, 1.75, 5.2, CODE, sz=12),
            lo.pic(ids, "occ_exit_pipe", 6.2, 1.65, 6.35, 2.75),
            textbox(ids, 6.2, 4.5, 6.35, 1.5, [
                b1("One block per stage, in **reverse order**", sz=15, spcBef=0),
                b1("Each stage reads the _s registers **before** the stage ahead of it "
                   "overwrites them: what **<=** does in SystemVerilog", sz=15),
                b1("Each iteration works on **three samples**", sz=15)]),
            label(ids, L, 6.15, 12.0, 0.32, "Vitis HLS 2025.1 at 10 ns: II = 1, an estimated "
                  "6.53 ns.  C simulation and RTL co-simulation match the loop as written.",
                  sz=12),
            sldnum_ph(ids)]


def s_drain(ids):
    dash = "–"
    rows = lo.ctr([["Iteration", "S0 reads", "S1 squares", "S2 tests"],
                   ["i = 0", "x[0]", dash, dash],
                   ["i = 1", "x[1]", "x[0]", dash],
                   ["i = 2", "x[2]", "x[1]", "x[0]"],
                   ["…", "…", "…", "…"],
                   ["i = NX − 1", "x[NX−1]", "x[NX−2]", "x[NX−3]"],
                   ["i = NX", dash, "x[NX−1]", "x[NX−2]"],
                   ["i = NX + 1", dash, dash, "x[NX−1]"]])
    return [title_ph(ids, "Filling and Draining"),
            table(ids, L, 1.8, [1.55, 1.45, 1.45, 1.45], rows, rowh=0.44, sz=14),
            lo.col(ids, 7.0, 5.55, [
                "**Fill**: in iterations 0 and 1, z_s1 holds no sample yet.  v_s1 is "
                "false, so S2 skips the test",
                "**Drain**: run the loop to **i < NX + 2**, so the last two samples "
                "reach S2",
                "But **guard the read**: v_s0 = (i < NX), and read x[i] only if v_s0",
                "One loop, no prologue or epilogue: the **valid bits** handle both ends"],
                y=1.8, h=4.2, sz=15),
            lo.portal_caption(ids, "Early exit by hand"), sldnum_ph(ids)]


def main() -> None:
    work = Path(tempfile.gettempdir()) / "loopopt_hand_pipeline"
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
    if MARKER in titles:
        raise SystemExit(f"{DECK.name} already has {MARKER!r}.")

    def one(title):
        hits = [k for k, t in enumerate(titles) if t == title]
        if len(hits) != 1:
            raise SystemExit(f"expected one slide titled {title!r}, found {len(hits)}")
        return hits[0]

    by_hand, hardware = one("Pipelining by Hand"), one("The Stages in Hardware")
    assert hardware == by_hand + 1 and one("Three Ways to Stop") == hardware + 1, \
        "the early-exit slides are not in the expected order"

    donor = order[one("Merge Example")]
    assert (slides / "_rels" / f"{donor}.rels").read_text(encoding="utf-8") \
        .count("<Relationship ") == 1, f"{donor} has pictures; pick another donor"
    made = []
    for _ in range(3):
        out = kit.sh([sys.executable, "add_slide.py", str(build), donor],
                     cwd=kit._find_skill_scripts())
        made.append(re.search(r"Created ppt/slides/(slide\d+\.xml)", out).group(1))
    kit.set_order(order[:hardware + 1] + made + order[hardware + 1:])

    lo.write(order[by_hand], s_procedure(Ids()))
    lo.write(order[hardware], s_stages(Ids()))
    for name, build_slide in zip(made, [s_regs, s_code, s_drain]):
        lo.write(name, build_slide(Ids()))
    print(kit.sh([sys.executable, "clean.py", str(build)], cwd=kit._find_skill_scripts()).strip())
    kit.pack(DECK)
    print(f"rewrote slides {by_hand + 1} and {hardware + 1}, added slides {hardware + 2} to "
          f"{hardware + 4}; wrote {DECK}")


if __name__ == "__main__":
    main()
