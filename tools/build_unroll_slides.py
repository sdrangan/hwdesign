"""Rebuild unit 8's slide deck, unroll.pptx, in the style of units 4 to 7.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
A *one-shot migration*, like tools/build_loopopt_slides.py, whose helpers it
uses (and through it the drawing kit, tools/build_fifo_slides.py): it reads the
11-slide draft of unroll.pptx, keeps three of its slides, builds the rest and
writes a new deck.  Once the result is edited in PowerPoint, this script is a
record of what was done, not a way to rebuild it, and it refuses to run on
its own output.

WHAT IT DOES
------------
  * the unit is Loop Unrolling and Memory, in four sections: unrolling,
    memory bottlenecks, unrolling a reduction, and nested loops
  * learning objectives: a table of the skills unroll.xml's rubric items are
    tagged with (skills.xml in hwdesign-soln)
  * each section is built around a demo, with its measured numbers:
    demos/pipeline/poly (unrolling the cubic, docs/demos/loopopt/unroll.md),
    demos/fsum (a float sum, docs/demos/loopopt/reduction.md),
    demos/unroll_inclass (the in-class dot product) and demos/fir (the nest,
    docs/demos/fir).  All Vitis HLS 2025.1, Zynq-7020, 100 MHz.
  * practice problems solved in the lecture, a PRACTICE and a SOLUTION slide
    each: Unrolling the cubic, Wide band memory, Unrolling a float sum, FIR
    loop nest.  The homework problems (Choosing a partition, Memory with
    unrolling, Moving average, Row-column additions) are named on the slide
    that teaches them, not solved.
  * kept from the draft, fixed and restyled: the title slide, Single Port
    Memory and Multi-Port RAMs (their diagrams are native shapes).  Rebuilt:
    every slide whose code was a picture, and the duplicated Multi-Port RAMs
    slide is dropped.  Fixes: "ProfS.", "Mutli", "BMutli-port", "FGPA", and
    the title, which now matches the unit's name in the LLM grader.
  * figures from units/unit08_unroll/figs/make_figs.py, and the demos' own
    charts and timing diagrams from their docs folders.

USAGE
-----
From the repo root, with the deck closed in PowerPoint:

    ../hwdesign-venv/Scripts/python units/unit08_unroll/figs/make_figs.py
    python tools/build_unroll_slides.py --out units/unit08_unroll/unroll_v8.pptx

Validate and render (PowerPoint draws what the class sees):

    python <skill>/scripts/office/validate.py OUT --original units/unit08_unroll/unroll.pptx
    tools/render_slides.ps1 -Deck OUT -OutDir out
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
from build_fifo_slides import (AMBER, AMBERTINT, CODEFILL, GRAYLINE, L, TEAL, TEALLINE, TEALTINT,
                               TEXT, TINT, VIOLET, W, WHITE, Ids, b1, b2, card, heading, label,
                               para, part, pill, shape, sldnum_ph, table, textbox, title_ph)

ROOT = Path(__file__).resolve().parent.parent
UNIT = "Unit 8"
OLD_TITLE = "Loop Unrolling and Nested Loops"
NEW_TITLE = "Loop Unrolling and Memory"


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", type=Path, default=ROOT / "units/unit08_unroll/unroll.pptx")
    p.add_argument("--out", type=Path, default=ROOT / "units/unit08_unroll/unroll_v8.pptx")
    p.add_argument("--figs", type=Path, default=ROOT / "units/unit08_unroll/figs")
    p.add_argument("--work", type=Path, default=Path(tempfile.gettempdir()) / "unroll_build")
    p.add_argument("--skill-scripts", type=Path, default=None)
    p.add_argument("--force", action="store_true",
                   help="run even if the source deck looks already migrated")
    a = p.parse_args()
    a.skill_scripts = a.skill_scripts or kit._find_skill_scripts()
    return a


# ------------------------------------------------------------- slide bits ---
pic, code, col, band, errcard, ctr = lo.pic, lo.code, lo.col, lo.band, lo.errcard, lo.ctr


def portal_caption(ids, qtag):
    return label(ids, L, 6.2, 9.0, 0.32, f"Also in the LLM grader: {UNIT} › {qtag}", sz=12)


def homework(ids, qtag, y=6.2):
    return label(ids, L, y, W, 0.32, f"Homework in the LLM grader: {UNIT} › {qtag}", sz=12)


SECTIONS = ["Loop Unrolling", "Memory Bottlenecks", "Unrolling a Reduction", "Nested Loops"]


def s_outline(active):
    def build(ids):
        paras = []
        for k, name in enumerate(SECTIONS):
            on = k == active
            paras.append(para(f"**{name}**" if on else name, sz=24, spcBef=0 if k == 0 else 16,
                              color=VIOLET if on else "8C8C8C"))
        return [title_ph(ids, "Outline"), textbox(ids, 1.2, 1.9, 10.5, 3.8, paras),
                sldnum_ph(ids)]
    return build


# ========================================================== section 0 ======
def s_objectives(ids):
    rows = [["Skill", "You will be able to"],
            ["Unroll loops",
             "Unroll a loop by hand or by pragma, and predict its throughput and its cost in "
             "multipliers"],
            ["Find the II the memory ports allow",
             "Count each array's accesses per iteration against its ports, and see why "
             "unrolling alone does not help"],
            ["Mitigate memory bottlenecks",
             "Widen the word, partition the array, or keep reused samples in a delay line"],
            ["Compute memory addresses",
             "Find the bank and offset of an element under cyclic and block partitioning"],
            ["Size memory", "Count the block RAMs a partitioned array takes"],
            ["Pipeline loop nests",
             "Choose the loop to pipeline, and account for flattening and the unrolling it "
             "implies"]]
    return [title_ph(ids, "Learning Objectives"),
            table(ids, 1.0, 1.75, [3.7, 7.6], rows, rowh=0.56, sz=14),
            label(ids, 1.0, 5.85, 11.0, 0.4,
                  "Each skill is assessed by problems in the LLM grader.  Unit 7's pipelining "
                  "and loop-carried dependencies are used throughout.", sz=12),
            sldnum_ph(ids)]


# ========================================================== section 1 ======
UNROLL_CODE = """
// The loop
for (int i = 0; i < N; i++) {
    y[i] = w[i] * x[i];
}

// Unrolled by 2
for (int i = 0; i < N; i += 2) {
    y[i]   = w[i]   * x[i];
    y[i+1] = w[i+1] * x[i+1];
}"""


def s_unroll_idea(ids):
    return [title_ph(ids, "Loop Unrolling"),
            col(ids, L, 5.6, [
                "Pipelining gave **one** sample per cycle",
                ("-", "Faster needs more than one sample **started** per cycle"),
                "**Unroll**: copy the loop body",
                ("-", "Unrolled by 2: half the iterations, each doing two samples"),
                ("-", "Two copies of the hardware"),
                "Pipelined at II = 1, that is **two samples per cycle**"],
                sz=17, sub=15, h=2.9),
            code(ids, L, 4.4, 5.6, UNROLL_CODE.split("\n\n")[0].strip() + "\n", sz=12),
            code(ids, 6.65, 1.8, 5.9, UNROLL_CODE.split("\n\n")[1], sz=13),
            pic(ids, "occ_unroll", 6.65, 3.75, 5.9, 2.45),
            sldnum_ph(ids)]


PRAGMA_CODE = """
for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=2
    y[i] = w[i] * x[i];
}"""


def s_unroll_vitis(ids):
    return [title_ph(ids, "Loop Unrolling in Vitis"),
            col(ids, L, 6.1, [
                "One pragma: `UNROLL factor=U`",
                ("-", "Vitis copies the body U times, as if written by hand"),
                ("-", "N need not divide by U: Vitis adds the exit checks"),
                "`UNROLL` with no factor: **completely**, no loop left",
                "A pipelined loop unrolls **every loop inside it** completely",
                ("-", "Its body must be straight-line code"),
                ("-", "Section 4: what that does to nested loops")], sz=17, sub=15),
            heading(ids, 7.1, 1.75, 5.4, "THE SAME LOOP, UNROLLED BY 2"),
            code(ids, 7.1, 2.1, 5.45, PRAGMA_CODE, sz=14),
            card(ids, 7.1, 4.25, 5.45, 1.25, [
                para("Unrolling does nothing for **latency**: each sample still takes as long. "
                     "It buys **throughput**, with hardware.", sz=15, color=TEXT)]),
            sldnum_ph(ids)]


def s_pipe_vs_unroll(ids):
    return [title_ph(ids, "Pipelining and Unrolling"),
            pic(ids, "occ_pipe", L, 1.7, 5.75, 2.6),
            pic(ids, "occ_unroll", 6.8, 1.7, 5.75, 3.3),
            textbox(ids, L, 4.55, 5.75, 1.6, [
                b1("**Pipelining**: the same hardware works on several samples, each at a "
                   "different stage", sz=15, spcBef=0),
                b1("Throughput up to one sample per cycle, for a few registers", sz=15)]),
            textbox(ids, 6.8, 5.1, 5.75, 1.1, [
                b1("**Unrolling**: U copies of the hardware, U samples per cycle", sz=15,
                   spcBef=0)]),
            sldnum_ph(ids)]


def s_demo_unroll(ids):
    return kit._demo(ids, "The Demo: Unrolling the Cubic",
                     "Demos › Loop Optimization › Unrolling the Loop",
                     ["cd demos/pipeline/poly",
                      "python poly_build.py --list-steps",
                      "python poly_build.py",
                      "python poly_build.py --unroll 2 4 8 16 --force-step synth_unroll"],
                     ["`synth_unroll` builds the pipelined loop unrolled by **2, 4 and 8**, with "
                      "x and y partitioned to match",
                      "and once by 4 **without** partitioning",
                      "`unroll_report` tabulates cycles and resources",
                      "`timing_unroll`: four x addresses stepping together"],
                     ("1024 samples: 1,063 cycles pipelined, 168 unrolled by 8.  15 DSPs become "
                      "120.",
                      "Unit 7's cubic: the same kernel, now several samples per cycle."))


def s_unroll_results(ids):
    rows = [["Unroll", "Partitioned", "II", "Iterations", "Cycles", "DSP"],
            ["1", "–", "1", "1024", "1,063", "15"],
            ["2", "yes", "1", "512", "552", "30"],
            ["4", "yes", "1", "256", "296", "60"],
            ["8", "yes", "1", "128", "168", "120"],
            [{"t": "4", "align": "ctr", "color": AMBER}, {"t": "no", "align": "ctr", "color": AMBER},
             {"t": "4", "align": "ctr", "color": AMBER}, {"t": "256", "align": "ctr", "color": AMBER},
             {"t": "1,066", "align": "ctr", "color": AMBER}, {"t": "15", "align": "ctr", "color": AMBER}]]
    return [title_ph(ids, "Unrolling the Cubic: Results"),
            table(ids, L, 1.75, [1.0, 1.35, 0.6, 1.2, 1.0, 0.8], ctr(rows), rowh=0.44, sz=14),
            textbox(ids, L, 4.6, 6.0, 1.6, [
                b1("Each doubling **halves the iterations** and **doubles the DSPs**",
                   sz=15, spcBef=0),
                b1("About 40 cycles do not shrink: the pipeline's depth, the coefficients, the "
                   "handshake", sz=15),
                b1("Unrolled but **not partitioned**: no faster at all", sz=15)]),
            pic(ids, "docs/unroll", 7.0, 1.75, 5.55, 3.1),
            label(ids, 7.0, 4.95, 5.55, 1.0, "1024 samples, Vitis HLS 2025.1, Zynq-7020 at "
                  "100 MHz.  The chip has 220 DSPs.  From results/unroll.md; unroll.md in the "
                  "demo docs walks through it.", sz=12),
            sldnum_ph(ids)]


def _cubic_table(ids, x, y, sz=13):
    rows = [["Unroll", "Partitioned", "II", "Cycles", "DSP"],
            ["1", "–", "1", "1,063", "15"], ["2", "yes", "1", "552", "30"],
            ["4", "yes", "1", "296", "60"], ["8", "yes", "1", "168", "120"],
            ["4", "no", "4", "1,066", "15"]]
    return table(ids, x, y, [0.95, 1.3, 0.55, 0.95, 0.75], ctr(rows), rowh=0.38, sz=sz)


def s_cubic_practice(ids):
    return [title_ph(ids, "Unrolling the Cubic"), pill(ids, "PRACTICE"),
            _cubic_table(ids, L, 1.8),
            label(ids, L, 4.15, 4.6, 0.9, "The demo's cubic, 1024 samples, 100 MHz.  The "
                  "Zynq-7020 has 220 DSPs.", sz=13),
            textbox(ids, 5.7, 1.8, 6.85, 4.3, [
                part("(a)", "For the partitioned designs, write the cycles as A + 1024/U.  "
                            "Find A.  What is it?", 15, spcBef=0),
                part("(b)", "The speedup of U = 8 over U = 1.  Why is it less than 8?", 15),
                part("(c)", "Predict the cycles and DSPs for U = 16.  Would it fit?", 15),
                part("(d)", "The unpartitioned design: why II = 4, and so about 1,066 "
                            "cycles?  Why only 15 DSPs, when it has four copies of the "
                            "body?", 15)]),
            portal_caption(ids, "Unrolling the cubic"), sldnum_ph(ids)]


def s_cubic_solution(ids):
    return [title_ph(ids, "Unrolling the Cubic"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 6.7, 4.3, [
                part("(a)", "1063 − 1024 = 39, 552 − 512 = 40, 296 − 256 = 40, 168 − 128 = 40: "
                            "!!A ≈ 40!!.  The cycles that do not depend on U: the 30-cycle "
                            "pipeline depth, the coefficient reads and the handshake", 15,
                     spcBef=0),
                part("(b)", "1063 / 168 ≈ !!6.3×!!, for 8× the DSPs.  The 40 fixed cycles "
                            "do not shrink", 15),
                part("(c)", "40 + 64 = !!104 cycles!!; 16 × 15 = !!240 DSPs!!, more than the "
                            "220 the chip has", 15),
                part("(d)", "Four reads of x per iteration, one port: !!II = 4!!, 256 × 4 + "
                            "≈40.  Each multiply's four copies come a cycle apart, so they "
                            "**take turns** on one multiplier: 15 DSPs", 15)]),
            errcard(ids, 7.75, 1.8, 4.8, 2.1, "Common error",
                    ["Expecting 1024 / 8 = 128 cycles: the fixed cycles stay.",
                     "Expecting 60 DSPs for the unpartitioned design: at II = 4, Vitis "
                     "shares."]),
            portal_caption(ids, "Unrolling the cubic"), sldnum_ph(ids)]


# ========================================================== section 2 ======
NOPART_LOG = """
WARNING: [HLS 200-885] The II Violation in module
'poly_Pipeline_sample_loop' (loop 'sample_loop'):
Unable to schedule 'load' operation 32 bit
('x_load_1', poly.cpp:75) on array 'x' due to
limited memory ports (II = 2). Please consider
using a memory core with more ports or
partitioning the array 'x'."""


def s_bottleneck(ids):
    return [title_ph(ids, "The Memory Bottleneck"),
            pic(ids, "occ_ports", L, 1.7, 6.6, 3.5, align="l"),
            col(ids, 7.6, 4.95, [
                "Unrolled by 4: each iteration reads **4 words of x**",
                "x is a block RAM with **one port**: one read per cycle",
                ("-", "The four reads take turns"),
                ("-", "The next iteration's wait: II = 4"),
                "Vitis says so in the log"], h=2.7, sz=16, sub=14),
            code(ids, 7.6, 4.25, 4.95, NOPART_LOG, sz=9, inset=0.1),
            label(ids, L, 5.4, 6.6, 0.8, "The poly demo's u4_nopart: it tried II = 1, 2 "
                  "and 3, and settled on 4.  Its schedule is in the demo docs.", sz=12),
            sldnum_ph(ids)]


def s_port_rule(ids):
    rows = [["Loop", "Reads of the array per iteration", "Ports", "II ≥"],
            ["y[i] = horner(c, x[i])", "1", "1", "1"],
            ["the same, unrolled by 4", "4", "1", "4"],
            ["unrolled by 4, x in 4 banks", "1 per bank", "1 per bank", "1"],
            ["unrolled by 4, true dual-port", "4", "2", "2"]]
    return [title_ph(ids, "The II the Memory Ports Allow"),
            card(ids, L, 1.75, W, 0.85, [
                para("For each array:  II  ≥  ⌈ accesses per iteration  /  ports ⌉.  "
                     "The loop's II is the largest, over every array, and over unit 7's "
                     "loop-carried limit.", sz=17, color=TEXT, align="ctr")], anchor="ctr"),
            table(ids, L, 2.85, [4.2, 3.8, 1.5, 1.0], ctr(rows), rowh=0.42, sz=14),
            col(ids, L, W, [
                "**Unrolling copies logic, not ports**: U copies need U accesses per cycle",
                "Reads and writes both count: a single-port memory does one or the other"],
                y=5.05, h=1.2, sz=15),
            sldnum_ph(ids)]


def s_four_fixes(ids):
    def c(x, y, n, title, lines):
        return card(ids, x, y, 5.8, 2.0, [para(f"^^{n}.  {title}^^", sz=16, spcAft=4)] +
                    [para(t, sz=14, color=TEXT, spcAft=2) for t in lines])
    return [title_ph(ids, "Four Solutions"),
            c(L, 1.75, 1, "More ports", [
                "A true multi-port RAM: any addresses, any cycle",
                "FPGA block RAMs have two ports; more is costly"]),
            c(6.75, 1.75, 2, "A wider word", [
                "64 bits read two 32-bit values in one access",
                "Only for values stored side by side"]),
            c(L, 3.95, 3, "Partition the array", [
                "Split it over several memories, each with its own port",
                "Only if each access lands in a different one"]),
            c(6.75, 3.95, 4, "Read less: reuse", [
                "Keep values the next iterations need in registers",
                "Section 4: the delay line"]),
            sldnum_ph(ids)]


WIDE_CODE = """
ap_uint<64> xw[N/2], ww[N/2], yw[N/2];
for (int i = 0; i < N/2; i++) {
#pragma HLS PIPELINE II=1
    ap_uint<64> xv = xw[i], wv = ww[i];  // one read each
    ap_uint<64> yv;
    yv.range(31, 0)  = xv.range(31, 0)  * wv.range(31, 0);
    yv.range(63, 32) = xv.range(63, 32) * wv.range(63, 32);
    yw[i] = yv;                          // one write
}"""


def s_wide(ids):
    return [title_ph(ids, "Using a Wider Word"),
            code(ids, L, 1.75, 7.6, WIDE_CODE, sz=12),
            col(ids, 8.65, 3.9, [
                "Two 32-bit values per **64-bit** word",
                "Unrolled by 2, with **one access** per array per iteration: II = 1",
                "Picking out the fields is wiring: no cycles",
                "Works only when the values one iteration needs are **contiguous**"],
                y=1.75, sz=15),
            sldnum_ph(ids)]


def s_wbm_practice(ids):
    src = """
int x[3*n], d[n];   // x: one port
for (int i = 0; i < n; i++) {
    d[i] = x[3*i]   * x[3*i] +
           x[3*i+1] * x[3*i+1] +
           x[3*i+2] * x[3*i+2];
}"""
    return [title_ph(ids, "Wide Band Memory"), pill(ids, "PRACTICE"),
            code(ids, L, 1.8, 5.8, src, sz=13),
            textbox(ids, 6.85, 1.8, 5.7, 4.3, [
                para("Each read takes one cycle; the arithmetic is fully pipelined; x allows "
                     "one read per cycle.", sz=15, color=TEXT, spcAft=4),
                part("(a)", "The minimum II.  What limits it?", 15),
                part("(b)", "The three values are packed into one `ap_uint<96> xpacked[n]`.  "
                            "Rewrite the loop with `p.range(31, 0)` and its like, and find "
                            "the new minimum II", 15)]),
            portal_caption(ids, "Wide band memory"), sldnum_ph(ids)]


WBM_SOLN = """
for (int i = 0; i < n; i++) {
#pragma HLS PIPELINE II=1
    ap_uint<96> p = xpacked[i];    // one read
    int x0 = p.range(31, 0);
    int x1 = p.range(63, 32);
    int x2 = p.range(95, 64);
    d[i] = x0*x0 + x1*x1 + x2*x2;
}"""


def s_wbm_solution(ids):
    return [title_ph(ids, "Wide Band Memory"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 5.6, 4.2, [
                part("(a)", "Three reads of x per iteration on one port: !!II = 3!!.  The "
                            "memory, not the arithmetic", 15, spcBef=0),
                part("(b)", "One 96-bit read per iteration, the fields by bit selection: "
                            "!!II = 1!!", 15)]),
            code(ids, 6.55, 1.8, 6.0, WBM_SOLN, sz=12),
            errcard(ids, 6.55, 4.55, 6.0, 1.45, "Common error",
                    ["Indexing xpacked[3*i]: three words per iteration again, II = 3."]),
            portal_caption(ids, "Wide band memory"), sldnum_ph(ids)]


PART_PRAGMA = """
float x[1024];
#pragma HLS ARRAY_PARTITION variable=x type=cyclic factor=4
#pragma HLS ARRAY_PARTITION variable=y type=block  factor=4
#pragma HLS ARRAY_PARTITION variable=c type=complete"""


def s_partition(ids):
    return [title_ph(ids, "Array Partitioning"),
            pic(ids, "partition", L, 1.7, 6.4, 3.2, align="l"),
            code(ids, L, 5.05, 6.4, PART_PRAGMA, sz=10, inset=0.1),
            col(ids, 7.45, 5.1, [
                "Split the array over F memories, **banks**, each with its own port",
                "**cyclic**: x[k] in bank k % F, at offset k / F",
                ("-", "Neighbours in different banks"),
                "**block**: x[k] in bank k / (N/F), at offset k % (N/F)",
                ("-", "Each bank a stretch of the array"),
                "**complete**: every element a register",
                ("-", "For small arrays only")], y=1.75, sz=15, sub=13),
            sldnum_ph(ids)]


def s_choose(ids):
    rows = [["dot.cpp, unrolled by 4", "II", "Cycles", "Ports on a"],
            ["not partitioned", "4", "262", "1"],
            ["block, factor 4", {"t": "4", "align": "ctr", "color": AMBER},
             {"t": "262", "align": "ctr", "color": AMBER}, "4"],
            ["cyclic, factor 4", {"t": "1", "align": "ctr", "color": TEAL},
             {"t": "70", "align": "ctr", "color": TEAL}, "4"]]
    return [title_ph(ids, "Matching the Partition to the Access"),
            col(ids, L, 5.7, [
                "Ask: which elements does **one iteration** access?",
                "Put them in **different banks**",
                ("-", "a[i] … a[i+3]: neighbours, so **cyclic**"),
                ("-", "Block puts all four in one bank: no better than before"),
                ("-", "a[i] and a[i+N/2]: halves, so **block**"),
                "More banks than accesses per iteration buys nothing"], sz=16, sub=14),
            table(ids, 6.75, 1.85, [2.6, 0.7, 1.0, 1.5], ctr(rows), rowh=0.45, sz=14),
            label(ids, 6.75, 3.85, 5.8, 0.8, "The in-class dot product, N = 256, Vitis HLS "
                  "2025.1 at 100 MHz.  With block, the log names array a_0.", sz=12),
            homework(ids, "Choosing a partition"), sldnum_ph(ids)]


def s_bram(ids):
    return [title_ph(ids, "Partitioning Costs Memory"),
            pic(ids, "bram_banks", L, 1.7, 8.0, 3.5, align="l"),
            col(ids, 9.0, 3.55, [
                "A block RAM holds 18 kbit",
                "Each bank needs **its own** blocks",
                "While banks fill their blocks, partitioning is free",
                "Once they are smaller, the count grows **with F**: blocks mostly empty"],
                y=1.75, sz=15),
            band(ids, "Unrolling multiplies the logic, and past a point the memory too, while "
                      "the data stays the same size.", y=5.35, h=0.62, sz=15),
            homework(ids, "Memory with unrolling"), sldnum_ph(ids)]


IF_RPT = """
* AP_MEMORY
| x_0_address0  | out | 8  |
| x_0_q0        | in  | 32 |
| x_1_address0  | out | 8  |
| x_1_q0        | in  | 32 |
..."""


def s_interface(ids):
    return [title_ph(ids, "Partitioning an Argument"),
            col(ids, L, 4.6, [
                "x is an **argument** of the top function",
                "Partitioned by 4, the IP has **four** memory ports for it",
                ("-", "Whoever calls it must supply four memories"),
                ("-", "Each address is 8 bits: 256 of the 1024 samples"),
                "The four addresses step **together**: four reads per cycle"],
                h=3.3, sz=15, sub=13),
            code(ids, L, 4.8, 4.6, IF_RPT, sz=11, inset=0.1),
            pic(ids, "docs/timing_unroll", 5.6, 1.75, 6.95, 4.35),
            sldnum_ph(ids)]


# ========================================================== section 3 ======
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
                "An int add is fast: II = 1 with **one** accumulator"], h=2.3, sz=16, sub=14),
            code(ids, L, 4.05, 6.6, DOT4, sz=11, inset=0.1),
            pic(ids, "adder_tree", 7.6, 1.65, 4.95, 3.0),
            table(ids, 7.6, 4.75, [2.45, 0.6, 1.0, 0.7], ctr(rows), rowh=0.36, sz=12),
            sldnum_ph(ids)]


FSUM_PRAGMA = """
for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=4
    sum += x[i];
}
// becomes a chain through sum:
sum = (((sum + x[i]) + x[i+1]) + x[i+2]) + x[i+3];"""


def s_float_sum(ids):
    rows = [["sum of 1024 floats", "II", "Iterations", "Cycles"],
            ["rolled: sum += x[i]", "4", "1024", "4,100"],
            [{"t": "UNROLL factor=4", "align": "ctr", "color": AMBER},
             {"t": "16", "align": "ctr", "color": AMBER}, "256",
             {"t": "4,099", "align": "ctr", "color": AMBER}]]
    return [title_ph(ids, "Unrolling a Float Sum"),
            col(ids, L, 5.8, [
                "A float add takes **4 cycles**: the rolled loop is unit 7's II = 4",
                "Unrolled by 4: a quarter of the iterations, but each takes **16**",
                ("-", "Vitis keeps the **order** of float adds: reordering changes the "
                      "rounding"),
                ("-", "Four adds in a chain through sum: 4 × 4 cycles"),
                "**No faster at all**"], h=3.2, sz=16, sub=14),
            table(ids, L, 4.95, [2.6, 0.7, 1.3, 1.1], ctr(rows), rowh=0.38, sz=13),
            code(ids, 6.85, 1.8, 5.7, FSUM_PRAGMA, sz=12),
            label(ids, 6.85, 4.6, 5.7, 0.9, "demos/fsum, Vitis HLS 2025.1 at 100 MHz; the log "
                  "reports HLS 200-880, a carried dependence on sum.  reduction.md in the demo "
                  "docs.", sz=12),
            sldnum_ph(ids)]


TREE_CODE = """
// tree: one add on the recurrence
for (int i = 0; i < N; i += 4) {
#pragma HLS PIPELINE II=1
    sum += (x[i] + x[i+1]) + (x[i+2] + x[i+3]);
}

// lanes: four partial sums
for (int i = 0; i < N; i += 4) {
#pragma HLS PIPELINE II=1
    for (int j = 0; j < 4; j++)
        part[j] += x[i + j];
}"""


def s_float_fix(ids):
    rows = [["", "II", "Iterations", "Cycles", "DSP"],
            ["tree", "4", "256", "1,042", "2"], ["lanes", "4", "256", "1,042", "4"]]
    return [title_ph(ids, "Rewriting the Body"),
            code(ids, L, 1.75, 6.0, TREE_CODE, sz=12),
            col(ids, 7.05, 5.5, [
                "Put **one** add on the recurrence: II = 4 for **four** samples",
                ("-", "4× faster than rolled"),
                "The 4 reads of x fit in the 4 cycles: no partition needed",
                "You choose to reorder; the tool will not"], y=1.75, h=2.85, sz=15, sub=13),
            table(ids, 7.05, 4.65, [1.3, 0.7, 1.3, 1.1, 0.8], ctr(rows), rowh=0.38, sz=13),
            sldnum_ph(ids)]


def s_fsum_practice(ids):
    return [title_ph(ids, "Unrolling a Float Sum"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 7.3, 4.3, [
                para("sum of N = 1024 floats in x, one port.  A float add takes 4 cycles; a new, "
                     "independent one can start every cycle.", sz=15, color=TEXT, spcAft=2),
                part("(a)", "The plain loop, `sum += x[i]`: the II and the cycles", 15),
                part("(b)", "With `UNROLL factor=4`, which keeps the order of the adds: the "
                            "body, the II and the cycles", 15),
                part("(c)", "Rewrite the unrolled body with one add on the recurrence: II, "
                            "cycles.  Must x be partitioned?", 15),
                part("(d)", "The same, unrolled by 8: II and cycles with x in one memory, "
                            "then cyclic factor 2", 15)]),
            code(ids, 8.35, 1.85, 4.2, "\nfloat sum = 0;\nfor (int i = 0; i < N; i++) {\n"
                 "#pragma HLS PIPELINE II=1\n    sum += x[i];\n}", sz=12),
            portal_caption(ids, "Unrolling a float sum"), sldnum_ph(ids)]


def s_fsum_solution(ids):
    return [title_ph(ids, "Unrolling a Float Sum"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 7.2, 4.3, [
                part("(a)", "Each add waits for the last: !!II = 4!!, about !!4,096 cycles!!",
                     15, spcBef=0),
                part("(b)", "(((sum + x0) + x1) + x2) + x3: four adds in a chain, !!II = 16!!, "
                            "256 × 16 ≈ !!4,096!!: no gain", 15),
                part("(c)", "sum += (x0 + x1) + (x2 + x3): !!II = 4!!, 256 × 4 ≈ "
                            "!!1,024!!.  No partition: 4 reads fit in the 4 cycles", 15),
                part("(d)", "8 reads, one port: !!II = 8!!, 128 × 8 ≈ 1,024, no better.  "
                            "Two banks: 4 reads each, !!II = 4!!, about !!512!!", 15)]),
            errcard(ids, 8.25, 1.8, 4.3, 2.4, "Common error",
                    ["Unrolled by 4, so 4× faster: not while the four adds are a chain "
                     "through sum."]),
            label(ids, 8.25, 4.4, 4.3, 1.5, "Measured (demos/fsum): 4,100, 4,099 and 1,042 "
                  "cycles for (a) to (c).", sz=12),
            portal_caption(ids, "Unrolling a float sum"), sldnum_ph(ids)]


INCLASS_LOOP = """
int sum = 0;
for (int i = 0; i < N; i++) {
#pragma HLS PIPELINE II=1
    sum += a[i] * b[i];
}
return sum;"""


def s_inclass(ids):
    return [title_ph(ids, "In Class: Unrolling a Dot Product"), pill(ids, "IN CLASS"),
            textbox(ids, L, 1.75, 6.5, 1.3, [
                para("N = 256 samples of 16-bit a and b, each in a block RAM with **one port**.  "
                     "The plain loop: 261 cycles, one DSP.  Goal: **four samples per cycle**.",
                     sz=15, color=TEXT)]),
            code(ids, L, 3.0, 6.5, INCLASS_LOOP, sz=13),
            textbox(ids, 7.55, 1.75, 5.0, 3.4, [
                part("(a)", "Unroll by 4 by hand.  Predict, then build: iterations, "
                            "multipliers, II, cycles", 14, spcBef=0),
                part("(b)", "Partition a and b, cyclic, factor 4.  Build again", 14),
                part("(c)", "Try block instead of cyclic; then `UNROLL factor=4`; then "
                            "factor 8", 14),
                part("(d)", "Why does one accumulator reach II = 1 here, but not for a "
                            "float sum?", 14)]),
            heading(ids, 7.55, 5.0, 5.0, "RUN"),
            shape(ids, 7.55, 5.3, 5.0, 0.8, fill=CODEFILL, line=GRAYLINE, lw=1.0, anchor="t",
                  inset=0.12, paras=[para("`cd demos/unroll_inclass`", sz=12),
                                     para("`python dot_build.py`", sz=12, spcBef=4)]),
            shape(ids, L, 5.3, 6.5, 0.8, fill=VIOLET, prst="roundRect", adj=16000, paras=[
                para(f"{kit.DOCS_URL}  —  Demos › Loop Optimization › In-Class: Unrolling",
                     sz=13, color=WHITE, b=True, align="ctr")]),
            label(ids, L, 6.2, W, 0.32, "About a minute per build.  Only dot.cpp is edited; "
                  "the build checks it, synthesizes it beside the plain loop and prints both.",
                  sz=12),
            sldnum_ph(ids)]


# ========================================================== section 4 ======
FIR_CODE = """
for (int n = 0; n < nsamp; n++) {     // samples
    int acc = 0;
    for (int k = 0; k < 16; k++) {    // taps
        int xk = (n - k >= 0) ? x[n - k] : 0;
        acc += h[k] * xk;
    }
    y[n] = acc;
}"""


def s_fir(ids):
    return [title_ph(ids, "Nested Loops: an FIR Filter"),
            col(ids, L, 5.6, [
                "y[n] = h[0]·x[n] + h[1]·x[n−1] + … + h[15]·x[n−15]",
                ("-", "16 taps, 16-bit integer samples"),
                "A loop over **samples** around a loop over **taps**",
                "16 multiply-adds per sample, however it is written",
                "Which loop do we pipeline?",
                ("-", "And where does each tap's x come from?")], sz=16, sub=14),
            code(ids, 6.6, 1.8, 5.95, FIR_CODE, sz=12),
            label(ids, 6.6, 4.4, 5.95, 0.9, "x, h and y are block RAMs with one port each.  "
                  "Integer adds take one cycle, so no loop-carried limit: the nest and the "
                  "ports decide.", sz=12),
            sldnum_ph(ids)]


def s_inner(ids):
    rows = [["Pipeline the tap loop", "Cycles per sample", "DSP"],
            ["kept as two loops", "25", "1"], ["flattened by Vitis", "16", "1"]]
    return [title_ph(ids, "Pipelining the Inner Loop"),
            pic(ids, "fir_timeline", L, 1.65, 7.6, 2.95, align="l"),
            col(ids, 8.55, 4.0, [
                "The tap loop reaches **II = 1**",
                "But it restarts for **every sample**: fill, drain, enter, leave",
                "Vitis **flattens** the nest into one loop of 16 × 1024",
                ("-", "Filled once per call"),
                ("-", "`LOOP_FLATTEN off` stops it")], y=1.75, sz=15, sub=13),
            table(ids, L, 4.8, [3.2, 2.2, 0.9], ctr(rows), rowh=0.4, sz=13),
            label(ids, 7.15, 4.85, 5.4, 1.1, "Flattened, one tap per cycle: 16 cycles per "
                  "sample is the best **one** multiplier can do.", sz=14, color=TEXT),
            sldnum_ph(ids)]


OUTER_CODE = """
for (int n = 0; n < nsamp; n++) {
#pragma HLS PIPELINE II=1        // the sample loop
    int acc = 0;
    for (int k = 0; k < 16; k++)  // unrolled by Vitis
        acc += c[k] * x[n - k];   // 16 reads of x
    y[n] = acc;
}"""


def s_outer(ids):
    return [title_ph(ids, "Pipelining the Outer Loop"),
            code(ids, L, 1.75, 6.3, OUTER_CODE, sz=12),
            col(ids, 7.35, 5.2, [
                "Vitis **unrolls the tap loop**: 16 multipliers, 16 DSPs",
                "Each iteration reads **16 words of x**, from one port",
                ("-", "II = 16: 16 cycles per sample"),
                "As slow as the flattened loop, with **16 times the multipliers**, each "
                "idle 15 cycles in 16"], y=1.75, sz=15, sub=13),
            errcard(ids, L, 4.4, 6.3, 1.6, "The coefficients",
                    ["Copied once into c, partitioned complete: 16 registers, all readable "
                     "at once.  h in its memory would be a second 16-read bottleneck."]),
            sldnum_ph(ids)]


DELAY_CODE = """
#pragma HLS ARRAY_PARTITION variable=xdly type=complete
for (int n = 0; n < nsamp; n++) {
#pragma HLS PIPELINE II=1
    for (int k = 15; k > 0; k--)   // shift, oldest first
        xdly[k] = xdly[k - 1];
    xdly[0] = x[n];                // the only read of x
    int acc = 0;
    for (int k = 0; k < 16; k++)   // xdly[k] = x[n-k]
        acc += c[k] * xdly[k];
    y[n] = acc;
}"""


def s_delay(ids):
    return [title_ph(ids, "A Delay Line"),
            pic(ids, "delay_line", L, 1.65, 6.0, 2.55, align="l"),
            code(ids, 6.95, 1.75, 5.6, DELAY_CODE, sz=11),
            col(ids, L, 6.0, [
                "Each x[n] is used by **16** outputs: read it **once**",
                "Keep the last 16 in registers that shift every cycle",
                "**II = 1**: one sample per cycle, all 16 multipliers busy"],
                y=4.35, h=1.8, sz=15),
            homework(ids, "Moving average"), sldnum_ph(ids)]


def s_demo_fir(ids):
    return kit._demo(ids, "The Demo: an FIR Filter, Four Ways", "Demos › FIR: Nested Loops",
                     ["cd demos/fir",
                      "python fir_build.py --list-steps",
                      "python fir_build.py --through report",
                      "python fir_build.py"],
                     ["`csim` checks **all four** variants against the Python model",
                      "`synth` builds `inner`, `flat`, `outer` and `delay`",
                      "`report`: cycles and DSPs side by side",
                      "`timing`: the delay line reads one x per cycle"],
                     ("1024 samples: 25,601 cycles with the tap loop restarted, 1,053 with "
                      "the delay line.",
                      "The same 16 multiply-adds per sample, four ways."))


def s_fir_results(ids):
    rows = [["Variant", "Pipelined", "II", "Cycles", "Per sample", "DSP"],
            ["inner", "tap loop", "1", "25,601", "25.0", "1"],
            ["flat", "nest, flattened", "1", "16,391", "16.0", "1"],
            ["outer", "sample loop", {"t": "16", "align": "ctr", "color": AMBER}, "16,412",
             "16.0", "16"],
            ["delay", "sample loop", {"t": "1", "align": "ctr", "color": TEAL},
             {"t": "1,053", "align": "ctr", "color": TEAL}, "1.03", "16"]]
    return [title_ph(ids, "The FIR: Results"),
            table(ids, L, 1.75, [1.0, 1.75, 0.55, 1.05, 1.15, 0.65], ctr(rows), rowh=0.42,
                  sz=13),
            pic(ids, "fir/fir", 7.2, 1.7, 5.35, 2.4),
            textbox(ids, L, 4.1, 6.3, 2.0, [
                b1("Pipelining an inner loop pays its fill **per outer iteration**, unless "
                   "flattened", sz=14, spcBef=0),
                b1("Pipelining an outer loop **unrolls** the inner one: parallel hardware "
                   "needing parallel data", sz=14),
                b1("The delay line supplies it with **one** read per sample", sz=14)]),
            label(ids, 7.2, 4.3, 5.35, 1.4, "Vitis HLS 2025.1, Zynq-7020 at 100 MHz.  "
                  "Co-simulation of delay: 1,049 cycles, every output checked.  results.md "
                  "in the demo docs.", sz=12),
            sldnum_ph(ids)]


def s_fir_practice(ids):
    return [title_ph(ids, "FIR Loop Nest"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 7.2, 4.3, [
                para("An 8-tap integer FIR on N = 512 samples; x, h and y in single-port "
                     "memories; an int add takes one cycle.  Pipelined alone, the tap loop "
                     "costs 8 + 6 cycles per sample: the taps, plus filling, draining, "
                     "entering and leaving it.", sz=14, color=TEXT, spcAft=2),
                part("(a)", "Tap loop pipelined, not flattened: the cycles", 14),
                part("(b)", "Flattened: the cycles.  Why faster?", 14),
                part("(c)", "Sample loop pipelined, h in registers: what happens to the tap "
                            "loop?  Multipliers, II, cycles", 14),
                part("(d)", "With a delay line: reads of x per sample, II, cycles, "
                            "multipliers", 14)]),
            code(ids, 8.25, 1.85, 4.3, "\nfor (n = 0; n < N; n++) {\n  acc = 0;\n"
                 "  for (k = 0; k < 8; k++)\n    acc += h[k]*x[n-k];\n  y[n] = acc;\n}",
                 sz=12),
            portal_caption(ids, "FIR loop nest"), sldnum_ph(ids)]


def s_fir_solution(ids):
    rows = [["", "Cycles", "Multipliers"], ["(a) inner", "7,168", "1"],
            ["(b) flat", "≈ 4,096", "1"], ["(c) outer", "≈ 4,096", "8"],
            ["(d) delay", "≈ 512", "8"]]
    return [title_ph(ids, "FIR Loop Nest"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 7.0, 4.3, [
                part("(a)", "512 × (8 + 6) = !!7,168 cycles!!", 14, spcBef=0),
                part("(b)", "One loop of 512 × 8 iterations at II = 1, filled once: "
                            "!!≈ 4,096!!", 14),
                part("(c)", "Unrolled completely: !!8 multipliers!!.  8 reads of x on one "
                            "port: !!II = 8!!, 512 × 8 ≈ !!4,096!!: no faster", 14),
                part("(d)", "!!One read!! per sample, !!II = 1!!, !!≈ 512 cycles!!, 8 "
                            "multipliers, all busy", 14)]),
            table(ids, 8.1, 1.85, [1.6, 1.3, 1.5], ctr(rows), rowh=0.42, sz=13),
            errcard(ids, 8.1, 4.15, 4.45, 1.85, "Common error",
                    ["(c) at II = 1: the unrolled tap loop needs 8 samples of x a cycle."]),
            portal_caption(ids, "FIR loop nest"), sldnum_ph(ids)]


MATVEC = """
int A[64][8], x[8];
#pragma HLS ARRAY_PARTITION variable=A dim=2 type=complete
#pragma HLS ARRAY_PARTITION variable=x type=complete
for (int i = 0; i < 64; i++) {        // rows: pipelined
#pragma HLS PIPELINE II=1
    int acc = 0;
    for (int j = 0; j < 8; j++)       // columns: unrolled
        acc += A[i][j] * x[j];        // 8 banks, one each
    y[i] = acc;
}"""


def s_loop_order(ids):
    return [title_ph(ids, "Loop Order and Partitioning"),
            col(ids, L, 5.8, [
                "A 2-D array partitioned on **one dimension**: `dim=2` puts each column in "
                "its own bank",
                "The loop order decides which elements meet in an iteration",
                ("-", "Inner loop over the **partitioned** dimension, unrolled: one element "
                      "from each bank, **II = 1**"),
                ("-", "The other way round: every access in one bank, the rest idle"),
                "Here y = A·x: a row of A per cycle, 8 multipliers"],
                sz=16, sub=14),
            code(ids, 6.85, 1.8, 5.7, MATVEC, sz=12),
            homework(ids, "Row-column additions"), sldnum_ph(ids)]


def s_takeaway(ids):
    rows = [["", "Throughput", "Costs", "Limited by"],
            ["Pipelining", "up to 1 per cycle", "registers", "loop-carried chains"],
            ["Unrolling by U", "up to U per cycle", "U copies of the logic", "memory ports"],
            ["Partitioning by F", "F accesses per cycle", "F memories, ports, BRAMs",
             "the access pattern"],
            ["Delay line", "1 read per sample", "registers", "—"]]
    return [title_ph(ids, "What to Take Away"),
            table(ids, L, 1.8, [2.4, 2.6, 3.4, 3.4], ctr(rows), rowh=0.5, sz=15),
            band(ids, "Unrolling buys throughput with hardware, **if** the memory can feed it "
                      "and no loop-carried chain grows with it.", y=4.85, h=0.75, sz=16),
            sldnum_ph(ids)]


# ============================================================== passes ====
MIGRATED_MARKER = "Unrolling the Cubic: Results"   # a slide only this script makes

EXPECTED = {1: "Unit 8", 2: "Learning Objectives", 3: "Outline", 4: "Loop Unrolling",
            7: "Single Port Memory", 8: "Three Solutions", 9: "Mutli"}

# ('old', position, builder or None) keeps or rebuilds an old slide; ('new', builder)
# adds one.  Old slides not listed are dropped: 11, a copy of 9.
PLAN = [
    ("old", 1, None), ("old", 2, s_objectives), ("old", 3, s_outline(0)),
    # section 1: loop unrolling
    ("old", 4, s_unroll_idea), ("old", 5, s_unroll_vitis), ("new", s_pipe_vs_unroll),
    ("new", s_demo_unroll), ("new", s_unroll_results),
    ("new", s_cubic_practice), ("new", s_cubic_solution),
    # section 2: memory bottlenecks
    ("new", s_outline(1)), ("old", 6, s_bottleneck), ("old", 7, None), ("new", s_port_rule),
    ("old", 8, s_four_fixes), ("old", 9, None), ("old", 10, s_wide),
    ("new", s_wbm_practice), ("new", s_wbm_solution),
    ("new", s_partition), ("new", s_choose), ("new", s_bram), ("new", s_interface),
    # section 3: unrolling a reduction
    ("new", s_outline(2)), ("new", s_int_sum), ("new", s_float_sum), ("new", s_float_fix),
    ("new", s_fsum_practice), ("new", s_fsum_solution), ("new", s_inclass),
    # section 4: nested loops
    ("new", s_outline(3)), ("new", s_fir), ("new", s_inner), ("new", s_outer),
    ("new", s_delay), ("new", s_demo_fir), ("new", s_fir_results),
    ("new", s_fir_practice), ("new", s_fir_solution), ("new", s_loop_order),
    ("new", s_takeaway),
]


def text_fixes(old):
    """Content corrections on the slides that are kept, not rebuilt."""
    s = old
    kit.fix(s[1], "ProfS. Sundeep", "Profs. Sundeep")
    kit.fix(s[1], f"<a:t>{OLD_TITLE}</a:t>", f"<a:t>{NEW_TITLE}</a:t>")
    kit.fix(s[9], "<a:t>Mutli</a:t>", "<a:t>Multi</a:t>")
    kit.fix(s[9], "BMutli", "Multi")


def main():
    args = _parse_args()
    build = (args.work / "unpacked").resolve()
    slides = build / "ppt" / "slides"
    figs = args.figs.resolve()
    kit.BUILD, kit.SLIDES = build, slides
    lo.BUILD, lo.SLIDES, lo.FIGS = build, slides, figs
    lo.FIG_DIRS.update({"docs": ROOT / "docs/demos/loopopt/images",
                        "fir": ROOT / "docs/demos/fir/images"})
    scripts = args.skill_scripts

    if build.exists():
        shutil.rmtree(build)
    zipfile.ZipFile(args.src).extractall(build)

    order = kit.slide_order()
    titles = [kit.slide_title(n) for n in order]
    if MIGRATED_MARKER in titles and not args.force:
        raise SystemExit(f"{args.src.name} already contains {MIGRATED_MARKER!r}: it has been "
                         "through this script.  This is a one-shot migration; see the docstring.")
    for pos, want in EXPECTED.items():
        got = titles[pos - 1]
        if got.strip() != want.strip():
            raise SystemExit(f"expected {want!r} at position {pos}, found {got!r}")
    old = {k + 1: n for k, n in enumerate(order)}

    # 1. structure: new slides duplicate a donor that has only its layout
    # relationship (slide 2, Learning Objectives), then the order is written.
    donor = old[2]
    assert (slides / "_rels" / f"{donor}.rels").read_text(encoding="utf-8").count(
        "<Relationship ") == 1
    final, jobs = [], []
    for item in PLAN:
        if item[0] == "old":
            _, pos, fn = item
            final.append(old[pos])
            if fn:
                jobs.append((old[pos], fn))
        else:
            made = kit.sh([sys.executable, "add_slide.py", str(build), donor], cwd=scripts)
            name = re.search(r"Created ppt/slides/(slide\d+\.xml)", made).group(1)
            final.append(name)
            jobs.append((name, item[1]))
    kit.set_order(final)
    kept = [n for n in final if n not in {s for s, _ in jobs}]
    n_new = sum(1 for i in PLAN if i[0] == "new")
    print(f"{len(final)} slides: {len(jobs)} built, {len(kept)} kept, "
          f"{len(order) - (len(final) - n_new)} old dropped")

    # 2. content
    for name, fn in jobs:
        lo.write(name, fn(Ids()))

    # 3. fixes and restyle on the kept slides
    text_fixes(old)
    kit.retheme_accent1()
    for name in kept:
        kit.restyle(name)
        kit.recolour_diagrams(name)
        lo.restyle_textboxes(name)

    # 4. pack
    print(kit.sh([sys.executable, "clean.py", str(build)], cwd=scripts).strip())
    kit.pack(args.out)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
