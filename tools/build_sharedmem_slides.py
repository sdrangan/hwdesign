"""Rebuild unit 9's slide deck, sharedmem.pptx, in the style of units 4 to 8 -- section 1 only.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
A *one-shot migration*, like tools/build_unroll_slides.py, whose pattern it
follows (and through tools/build_loopopt_slides.py the drawing kit,
tools/build_fifo_slides.py).  It reads the old deck, kept as
units/unit09_sharedmem/sharedmem_v1.pptx, keeps the slides of its first
section that are still right, builds the rest and writes a new deck.  Once the
result is edited in PowerPoint this script is a record of what was done, not a
way to rebuild it, and it refuses to run on its own output.

WHAT IT DOES
------------
  * the unit is now Transactional Interfaces to Memory, in five sections
    (plans/unit9_10_memory_pipelining.md): shared memory and interconnects,
    transactional interfaces (adaptors, hls::task, tags), AXI4 bursts and
    timing, memory-mapped queues and credit, and a histogram design example.
    Sections 1-3 are built.  Section 2 runs on one example, a histogram
    (demos/histogram, being built): the example, the protocol steps (the old
    phase slides), the data mover, hls::task, the tasks' code (placeholders
    until the demo lands), timing, and two practice pairs on y = a*x + b.
    Section 3 is the old AXI4 signal slides, as reference.  The old deck's Vitis m_axi
    histogram (slides 36-47) is left out, to be rebuilt around Waveflow's
    adaptors in section 5.
  * learning objectives: a table of skills for the whole unit.  The old
    objectives slide was a copy of unit 4's.
  * new slides: Streaming vs. Shared Memory (the old table had empty cells),
    Master or Slave? with a PRACTICE and a SOLUTION slide, and four slides on
    one flow (blocks 1 -> 4, B = 4, 2, 3 cycles, frames A, B, C): over a bus,
    over a crossbar (the transfers pipeline: period max(B), latency sum(B)),
    with a half-duplex DDR, and with the DDR appearing twice.  Their timelines
    are computed by schedule(), not placed by hand.  Then the Bus or Crossbar?
    PRACTICE and SOLUTION.
  * dropped: Typical RAM Architecture, Single and Multi-Port Memories and
    Problems with Multi-Port RAMs -- unit 8 teaches all three.
  * kept, fixed and restyled: the title, Addressable Memory, Dedicated vs
    Shared Memory, Why Share Memory?, the three examples (video, mobile SoC,
    DGX H100), How to Build Shared Memory, Interconnect, Transactions, Bus,
    Crossbar and Other Topologies.  Fixes: "Unit 8", "ProfS.", the unit's
    title, "Transactions, Master and Slaves", "need operate", "as need".
  * the practice problems are not in the LLM grader yet, so their slides carry
    no portal caption.  The homework problems that fit section 1 are named on
    the throughput slide.

USAGE
-----
From the repo root, with the deck closed in PowerPoint:

    python tools/build_sharedmem_slides.py

Validate and render (PowerPoint draws what the class sees):

    python <skill>/scripts/office/validate.py units/unit09_sharedmem/sharedmem.pptx \
        --original units/unit09_sharedmem/sharedmem_v1.pptx
    tools/render_slides.ps1 -Deck units/unit09_sharedmem/sharedmem.pptx -OutDir out
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
from build_fifo_slides import (AMBER, GRAYFILL, L, MUTED, SLATE, SLATETINT, TEAL, TEALTINT, TEXT, TINT,
                               VIOLET, W, WHITE, Ids, arrow, card, para, part, pill, shape,
                               sldnum_ph, table, textbox, title_ph)

ROOT = Path(__file__).resolve().parent.parent
UNIT = "Unit 9"
OLD_UNIT = "Unit 8 "
OLD_TITLE = "Shared Memory Transactions"
NEW_TITLE = "Transactional Interfaces to Memory"


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", type=Path, default=ROOT / "units/unit09_sharedmem/sharedmem_v1.pptx")
    p.add_argument("--out", type=Path, default=ROOT / "units/unit09_sharedmem/sharedmem.pptx")
    p.add_argument("--figs", type=Path, default=ROOT / "units/unit09_sharedmem/figs")
    p.add_argument("--work", type=Path, default=Path(tempfile.gettempdir()) / "sharedmem_build")
    p.add_argument("--skill-scripts", type=Path, default=None)
    p.add_argument("--force", action="store_true",
                   help="run even if the source deck looks already migrated")
    a = p.parse_args()
    a.skill_scripts = a.skill_scripts or kit._find_skill_scripts()
    return a


# ------------------------------------------------------------- slide bits ---
col, band, errcard, ctr = lo.col, lo.band, lo.errcard, lo.ctr
label = kit.label


def homework(ids, qtags, y=6.2):
    names = ", ".join(qtags)
    return label(ids, L, y, W, 0.32, f"Homework in the LLM grader: {UNIT} › {names}", sz=12)


SECTIONS = ["Shared Memory and Interconnects", "Transactional Interfaces",
            "AXI4 Under the Hood", "Memory-Mapped Queues and Credit",
            "Design Example: A Histogram"]


def s_outline(active):
    def build(ids):
        paras = []
        for k, name in enumerate(SECTIONS):
            on = k == active
            paras.append(para(f"**{name}**" if on else name, sz=24, spcBef=0 if k == 0 else 16,
                              color=VIOLET if on else "8C8C8C"))
        return [title_ph(ids, "Outline"), kit.textbox(ids, 1.2, 1.9, 10.5, 3.8, paras),
                sldnum_ph(ids)]
    return build


# ========================================================== section 0 ======
def s_objectives(ids):
    rows = [["Skill", "You will be able to"],
            ["Choose shared or dedicated memory",
             "Decide when data should move on a stream and when through a shared memory"],
            ["Identify master and slave",
             "Find which side starts each transaction, whichever way the data moves"],
            ["Estimate interconnect throughput",
             "Bound a job's transfer time on a bus and on a crossbar from the load on each port"],
            ["Design a transactional master",
             "Reach memory through read and write commands on streams, matching each "
             "completion to its command"],
            ["Time memory transactions",
             "Estimate when bursts, and the whole job, complete from latency and burst length"],
            ["Use memory-mapped queues",
             "Pass commands and responses through slave queues, with credits so the bus never "
             "stalls"]]
    return [title_ph(ids, "Learning Objectives"),
            table(ids, 1.0, 1.75, [3.7, 7.6], rows, rowh=0.56, sz=14),
            label(ids, 1.0, 5.85, 11.0, 0.4,
                  "Unit 4's AXI4-Lite registers and unit 5's streams and command–response "
                  "messages are used throughout.", sz=12),
            sldnum_ph(ids)]


# ========================================================== section 1 ======
def s_stream_vs_shared(ids):
    rows = [["", "Streaming", "Shared memory"],
            ["Access", "In order, each word once", "Any order, any number of times"],
            ["Who moves the data", "The producer pushes it when ready",
             "The consumer pulls it when needed"],
            ["Latency", "Fixed and small", "Variable: depends on arbitration and load"],
            ["Arbitration", "None on a point-to-point link", "Needed"],
            ["Hardware", "A link for every producer–consumer pair",
             "One memory and an interconnect, shared"],
            ["Typical use", "Fixed pipelines: video, radio front ends",
             "SoCs: CPU, GPU and NPU on one DRAM"]]
    first = [{"t": r[0], "b": True} for r in rows[1:]]
    body = [rows[0]] + [[first[k]] + rows[k + 1][1:] for k in range(len(first))]
    return [title_ph(ids, "Streaming vs. Shared Memory"),
            table(ids, L, 1.75, [2.5, 4.55, 4.75], body, rowh=0.5, sz=15),
            band(ids, "Stream when data flows **in order from one producer to one consumer**.  "
                      "Share when **many units** need the same data, or need it **out of order**.",
                 y=5.5, h=0.7, sz=16),
            sldnum_ph(ids)]


def s_master_or_slave(ids):
    x0, bw = 8.55, 2.1
    out = [title_ph(ids, "Master or Slave?"),
           col(ids, L, 6.9, [
               "**Master**: starts each transaction, deciding **when** and **which address**",
               "**Slave**: responds at the addresses it owns, and does nothing until addressed",
               "Ask who decides **when** the data moves",
               ("-", "Not which way it moves: a master reads and writes"),
               "One block can be both",
               ("-", "Unit 4's IP was a slave: the CPU moved every word"),
               ("-", "This unit: a slave for its commands, a master for its data")],
               h=3.5, sz=17, sub=15)]
    # The accelerator in the middle is a slave to the CPU and a master to the DDR.
    boxes = [(1.8, "CPU", SLATETINT, SLATE), (3.05, "Accelerator", TINT, VIOLET),
             (4.3, "DDR", TEALTINT, TEAL)]
    for y, name, fill, line in boxes:
        out.append(shape(ids, x0, y, bw, 0.62, fill=fill, line=line, lw=1.25, prst="roundRect",
                         adj=12000, paras=[para(name, sz=15, color=TEXT, b=True, align="ctr")]))
    xc = x0 + bw / 2
    out += [arrow(ids, xc, 2.42, xc, 3.05, SLATE, lw=2.0),
            arrow(ids, xc, 3.67, xc, 4.3, VIOLET, lw=2.0),
            label(ids, x0 + bw + 0.15, 2.5, 1.85, 0.5, "CPU is master: writes the command",
                  sz=12, color=SLATE),
            label(ids, x0 + bw + 0.15, 3.75, 1.85, 0.5, "Accelerator is master: reads the data",
                  sz=12, color=VIOLET),
            card(ids, L, 5.35, W, 0.8, [para(
                "AMBA renamed these **manager** and **subordinate** in 2021.  Port names keep the "
                "old letters: `M_AXI`, `s_axilite`, and Waveflow's `m_` and `s_` prefixes.",
                sz=14, color=TEXT)], anchor="ctr"),
            sldnum_ph(ids)]
    return out


MS_BLOCKS = [
    ("(a)", "A DDR memory controller"),
    ("(b)", "An Ethernet receiver that stores each arriving packet in DDR"),
    ("(c)", "A UART: the CPU reads each received byte from one of its registers"),
    ("(d)", "A histogram accelerator: the CPU writes it the address of the samples, and it "
            "reads them itself"),
    ("(e)", "The CPU"),
    ("(f)", "A DMA engine that copies a buffer from DDR to a block RAM when the CPU asks")]


def s_ms_practice(ids):
    paras = [para("For each block: does it need a **master** port, a **slave** port, or **both**?  "
                  "Say who starts each transaction.", sz=16, color=TEXT, spcAft=6)]
    paras += [part(k, t, 16) for k, t in MS_BLOCKS]
    return [title_ph(ids, "Master or Slave?"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 10.5, 4.2, paras), sldnum_ph(ids)]


def s_ms_solution(ids):
    ans = {"align": "ctr", "color": TEAL, "b": True}
    rows = [["Block", "Port", "Why"],
            ["(a) DDR controller", {"t": "slave", **ans}, "Answers every read and write; never starts one"],
            ["(b) Ethernet receiver", {"t": "master", **ans},
             "Packets arrive on their own schedule: it decides when to write, and where"],
            ["(c) UART", {"t": "slave", **ans}, "The CPU decides when to read each byte"],
            ["(d) Histogram accelerator", {"t": "both", **ans},
             "Slave for the CPU's command; master to fetch its samples"],
            ["(e) CPU", {"t": "master", **ans}, "Starts every load and store it makes"],
            ["(f) DMA engine", {"t": "both", **ans},
             "Slave for the CPU's request; master on both memories"]]
    return [title_ph(ids, "Master or Slave?"), pill(ids, "SOLUTION"),
            table(ids, L, 1.8, [3.0, 1.1, 7.7], rows, rowh=0.44, sz=14),
            errcard(ids, L, 5.05, W, 1.0, "Common error",
                    ["Deciding by the direction of the data.  In (b) the receiver only sends "
                     "data and the DDR only takes it, yet the receiver is the master."]),
            sldnum_ph(ids)]


# ---- a flow through the interconnect: four slides on one example ----------
# Blocks 1 -> 2 -> 3 -> 4; transfer k (block k to block k+1) takes B[k] cycles.
# Frames A, B, C arrive back to back.  The timelines are computed, not drawn by
# hand: see schedule().
B = [4, 2, 3]
FRAMES = "ABC"
FRAME_FILL = [VIOLET, TEAL, SLATE]
TMAX = 27                                   # the bus's last cycle: every slide uses one scale

# Which ports each transfer holds while it runs.  A transfer starts when its
# frame's previous transfer is done and every port it needs is free; among
# waiting transfers the oldest frame goes first.
SCENARIOS = {
    "bus":      [{"bus"}, {"bus"}, {"bus"}],
    "crossbar": [{"t1"}, {"t2"}, {"t3"}],
    "half":     [{"ddr"}, {"ddr"}, {"t3"}],              # block 2 is a half-duplex DDR
    "twice":    [{"ddr-w"}, {"ddr-r"}, {"ddr-w"}],       # blocks 2 and 4 are one full-duplex DDR
}


def schedule(res, durations=B, nframes=len(FRAMES)):
    """{(frame, transfer): (start, end)}, cycle by cycle."""
    free, done, out = {}, {}, {}
    pending = [(f, k) for f in range(nframes) for k in range(len(durations))]
    t = 0
    while pending:
        for f, k in sorted(pending):
            ready = k == 0 or done.get((f, k - 1), 10**9) <= t
            if ready and all(free.get(r, 0) <= t for r in res[k]):
                end = t + durations[k]
                out[(f, k)] = (t, end)
                done[(f, k)] = end
                for r in res[k]:
                    free[r] = end
                pending.remove((f, k))
        t += 1
    return out


def finishes(sched):
    """When each frame's last transfer ends."""
    n = len(B)
    return [sched[(f, n - 1)][1] for f in range(len(FRAMES))]


def timeline(ids, sched, x=5.0, y=1.95, w=7.55, shared=(), row_h=0.48, gap=0.2):
    """Rows for transfers 1->2, 2->3, 3->4; a block per frame per transfer."""
    lab_w = 1.15
    x0, scale = x + lab_w, (w - lab_w) / TMAX
    out = []
    for k in range(len(B)):
        ry = y + k * (row_h + gap)
        on = k in shared
        out.append(label(ids, x, ry + 0.06, lab_w - 0.1, row_h, f"{k + 1} → {k + 2}", sz=13,
                         color=AMBER if on else TEXT, b=on))
        out.append(shape(ids, x0, ry, w - lab_w, row_h, fill=kit.AMBERTINT if on else "F7F7F7",
                         line=None))
        for f in range(len(FRAMES)):
            s, e = sched[(f, k)]
            out.append(shape(ids, x0 + s * scale, ry + 0.04, (e - s) * scale, row_h - 0.08,
                             fill=FRAME_FILL[f], line=WHITE, lw=0.75,
                             paras=[para(FRAMES[f], sz=12, color=WHITE, b=True, align="ctr")]))
    ay = y + len(B) * (row_h + gap) - gap + 0.05
    for c in range(0, TMAX + 1, 3):
        out.append(label(ids, x0 + c * scale - 0.25, ay, 0.5, 0.25, str(c), sz=10, align="ctr"))
    out.append(label(ids, x, ay, lab_w - 0.1, 0.25, "cycle", sz=10))
    return out


def flow_column(ids, names, ddr=(), x=L + 0.15, y=1.95, bw=1.7, h=0.5, gap=0.42):
    """The flow, top to bottom, each arrow labelled with its B_k."""
    out = []
    for k, name in enumerate(names):
        by = y + k * (h + gap)
        is_ddr = k in ddr
        out.append(shape(ids, x, by, bw, h, fill=TEALTINT if is_ddr else TINT,
                         line=TEAL if is_ddr else VIOLET, lw=1.25, prst="roundRect", adj=12000,
                         paras=[para(name, sz=14, color=TEXT, b=True, align="ctr")]))
        if k < len(B):
            out.append(arrow(ids, x + bw / 2, by + h, x + bw / 2, by + h + gap, VIOLET, lw=1.75))
            out.append(label(ids, x + bw / 2 + 0.15, by + h + 0.06, 1.6, 0.3,
                             f"B_{{{k + 1}}} = {B[k]}", sz=13, color=TEXT))
    return out


def s_flow_bus(ids):
    sched = schedule(SCENARIOS["bus"])
    fa, fb, fc = finishes(sched)
    return [title_ph(ids, "A Flow Over a Bus"),
            *flow_column(ids, ["Block 1", "Block 2", "Block 3", "Block 4"]),
            label(ids, 5.0, 1.55, 7.55, 0.35, "Frames A, B, C arrive back to back.  A transfer "
                  "starts when its frame's last one is done and the path is free.", sz=12),
            *timeline(ids, sched),
            textbox(ids, 5.0, 4.15, 7.55, 1.2, [
                kit.bullet("**One transfer at a time**: the blocks never overlap", sz=15,
                           spcBef=0),
                kit.bullet(f"A done at {fa}, B at {fb}, C at {fc}", sz=15)]),
            band(ids, "Bus: cycles per frame = B_{1} + B_{2} + B_{3} = "
                      f"**{sum(B)}**", y=5.5, h=0.6, sz=17),
            sldnum_ph(ids)]


def s_flow_xbar(ids):
    sched = schedule(SCENARIOS["crossbar"])
    fa, fb, fc = finishes(sched)
    return [title_ph(ids, "The Same Flow Over a Crossbar"),
            *flow_column(ids, ["Block 1", "Block 2", "Block 3", "Block 4"]),
            *timeline(ids, sched),
            textbox(ids, 5.0, 4.15, 7.55, 1.3, [
                kit.bullet("Each transfer has its own path: they **pipeline**.  B moves 1 → 2 while "
                           "A moves 2 → 3", sz=15, spcBef=0),
                kit.bullet(f"A done at {fa}, B at {fb}, C at {fc}: a frame every "
                           f"{max(B)} cycles, but each still takes {sum(B)}", sz=15),
                kit.bullet("Block 2 holds A while it receives B: **two buffers** (unit 10)",
                           sz=15)]),
            band(ids, f"Crossbar: cycles per frame = max(B_{{1}}, B_{{2}}, B_{{3}}) = "
                      f"**{max(B)}**.  Like unit 7's II: the slowest stage sets the rate.",
                 y=5.5, h=0.6, sz=16),
            homework(ids, ["Crossbar request timing", "Packet processor scaling"]),
            sldnum_ph(ids)]


def s_flow_half(ids):
    sched = schedule(SCENARIOS["half"])
    fa, fb, fc = finishes(sched)
    return [title_ph(ids, "A Half-Duplex Block"),
            *flow_column(ids, ["Block 1", "DDR", "Block 3", "Block 4"], ddr=(1,)),
            *timeline(ids, sched, shared=(0, 1)),
            textbox(ids, 5.0, 4.15, 7.55, 1.3, [
                kit.bullet("The DDR is written (1 → 2) and read (2 → 3), but does **one at a "
                           "time**: the amber rows never overlap", sz=15, spcBef=0),
                kit.bullet(f"A done at {fa}, B at {fb}, C at {fc}: a frame every "
                           f"{B[0] + B[1]} cycles", sz=15)]),
            band(ids, f"Its transfers add: cycles per frame = max(B_{{1}} + B_{{2}}, B_{{3}}) = "
                      f"**{max(B[0] + B[1], B[2])}**", y=5.5, h=0.6, sz=17),
            homework(ids, ["Half-duplex DDR timing"]),
            sldnum_ph(ids)]


def s_flow_twice(ids):
    sched = schedule(SCENARIOS["twice"])
    fa, fb, fc = finishes(sched)
    wr = B[0] + B[2]
    return [title_ph(ids, "A Block That Appears Twice"),
            *flow_column(ids, ["Block 1", "DDR", "Block 3", "DDR"], ddr=(1, 3)),
            *timeline(ids, sched, shared=(0, 2)),
            textbox(ids, 5.0, 4.15, 7.55, 1.3, [
                kit.bullet("Block 3 reads its input from the DDR and writes its result back: "
                           "1 → 2 and 3 → 4 both **write the DDR**", sz=15, spcBef=0),
                kit.bullet(f"Full duplex, so reads run beside writes, but the writes take turns: "
                           f"C done at {fc}, a frame every {wr} cycles in the long run", sz=15)]),
            band(ids, "In general: add up the transfers through **each port**, reads and writes "
                      f"apart if full duplex.  The largest sets the rate: max({B[0]} + {B[2]}, "
                      f"{B[1]}) = **{max(wr, B[1])}**", y=5.5, h=0.75, sz=15),
            sldnum_ph(ids)]


XB_ROWS = [["Master", "Slave", "Words per frame"],
           ["Camera", "DDR (write)", "4,000"],
           ["Accelerator", "DDR (read)", "4,000"],
           ["Accelerator", "Block RAM (write)", "1,000"],
           ["CPU", "Block RAM (read)", "1,000"]]


def s_xb_practice(ids):
    return [title_ph(ids, "Bus or Crossbar?"), pill(ids, "PRACTICE"),
            table(ids, L, 1.8, [1.7, 2.1, 1.7], ctr(XB_ROWS), rowh=0.44, sz=14),
            label(ids, L, 4.15, 5.5, 1.5,
                  "A camera pipeline at 200 MHz.  Every port, master or slave, moves one word per "
                  "cycle, reads and writes combined.  Frames overlap; ignore protocol overhead.",
                  sz=13, color=TEXT),
            textbox(ids, 6.65, 1.8, 5.9, 4.3, [
                part("(a)", "On a bus: the cycles per frame, and the frames per second", 16,
                     spcBef=0),
                part("(b)", "The same on a crossbar.  Which port limits it?", 16),
                part("(c)", "The DDR controller is replaced by one that reads and writes at once, "
                            "a word of each per cycle.  The frames per second on each "
                            "interconnect now?  What limits the crossbar?", 16)]),
            sldnum_ph(ids)]


def s_xb_solution(ids):
    hi = {"align": "ctr", "color": TEAL, "b": True}
    rows = [["Port", "(b)", "(c)"],
            ["DDR", {"t": "8,000", **hi}, "4,000"],
            ["Accelerator", "5,000", {"t": "5,000", **hi}],
            ["Camera", "4,000", "4,000"],
            ["Block RAM", "2,000", "2,000"],
            ["CPU", "1,000", "1,000"]]
    return [title_ph(ids, "Bus or Crossbar?"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 6.6, 4.3, [
                part("(a)", "4,000 + 4,000 + 1,000 + 1,000 = !!10,000 cycles!!; 200 M / 10,000 = "
                            "!!20,000 frames/s!!", 15, spcBef=0),
                part("(b)", "The busiest port is the **DDR**: 4,000 + 4,000 = 8,000.  "
                            "!!8,000 cycles, 25,000 frames/s!!", 15),
                part("(c)", "Bus: still one transfer at a time, !!20,000 frames/s!!.  Crossbar: "
                            "the DDR carries 4,000 each way at once; now the **accelerator's** "
                            "port, 4,000 + 1,000, is the busiest: !!5,000 cycles, 40,000 "
                            "frames/s!!", 15)]),
            table(ids, 7.75, 1.8, [1.9, 1.4, 1.5], ctr(rows), rowh=0.4, sz=14),
            label(ids, 7.75, 4.25, 4.8, 0.4, "Words per frame on each port", sz=12),
            errcard(ids, 7.75, 4.7, 4.8, 1.35, "Common error",
                    ["Counting only the master ports.  The slave ports are shared too: here the "
                     "DDR, a slave, limits (b)."]),
            sldnum_ph(ids)]


# ---- the crossbar demo: AMD's axi_crossbar on the Zynq-7020 ---------------
# Measured by demos/xbar (branch demo/xbar): 100 MHz, 64-bit data, routed out
# of context; latency under XSI, first address handshake to last response.
# Figures copied from docs/demos/xbar/images.

def s_xbar_demo(ids):
    return kit._demo(ids, "The Demo: Crossbar or Shared Bus", "Demos › Crossbar or Shared Bus",
                     ["cd demos/xbar",
                      "python xbar_demo.py",
                      "python xbar_demo.py --fresh",
                      "python xbar_demo.py --through synth"],
                     ["The area table: every shape from 1x2 to 4x4, crossbar beside bus",
                      "2x2 and 4x4 simulated live in both modes",
                      "`--fresh` recompiles the simulations: about a minute",
                      "`--through synth` places and routes one 4x4: 3–4 minutes"],
                     ("AMD's axi_crossbar on the Pynq-Z2's Zynq-7020 at 100 MHz, 64-bit data.  "
                      "SAMD mode is a crossbar, SASD a shared bus.",
                      "The IP Vivado puts in a block design: real area, real cycles."))


def s_xbar_area(ids):
    rows = [["Shape", "Crossbar LUT / FF", "Bus LUT / FF"],
            ["1x2", "342 / 507", "265 / 230"],
            ["2x2", "618 / 545", "374 / 237"],
            ["4x4", "1,397 / 978", "649 / 251"]]
    return [title_ph(ids, "Crossbar or Bus: Area"),
            lo.pic(ids, "xbar_area_luts", L, 1.7, 6.9, 3.9, align="l"),
            table(ids, 7.85, 1.75, [1.0, 1.85, 1.85], ctr(rows), rowh=0.42, sz=14),
            textbox(ids, 7.85, 3.6, 4.7, 2.3, [
                kit.bullet("The bus is nearly **flat**: one transaction's registers, whatever "
                           "the shape (FFs 230 → 251)", sz=14, spcBef=0),
                kit.bullet("The crossbar grows **much faster**, and the gap widens with size", sz=14),
                kit.bullet("Still small here: the 4x4 crossbar is under 3% of the chip's 53,200 "
                           "LUTs.  All meet 100 MHz", sz=14)]),
            label(ids, L, 5.75, W, 0.4, "Zynq-7020, 100 MHz, 64-bit data, routed out of context.  "
                  "No BRAM, no DSP.", sz=12),
            sldnum_ph(ids)]


def s_xbar_cycles(ids):
    return [title_ph(ids, "Crossbar or Bus: Throughput"),
            lo.pic(ids, "xbar_cycles", L, 1.65, 7.3, 3.7, align="l"),
            textbox(ids, 8.25, 1.75, 4.3, 3.6, [
                para("2, 3 or 4 masters each write 16 beats at once", sz=14, color=MUTED,
                     spcAft=6),
                kit.bullet("**One write alone**: 20–21 cycles on either", sz=15, spcBef=0),
                kit.bullet("**Each to its own slave**: 4 masters finish in !!30!! on the "
                           "crossbar, ^^80^^ on the bus", sz=15),
                kit.bullet("**All to one slave**: 75 against 80.  A slave takes one burst at a "
                           "time, so the crossbar barely helps", sz=15)]),
            band(ids, "As on the flow slides: a crossbar helps only when the traffic is **spread "
                      "over the slaves**.  Many masters on one DDR port gain almost nothing.",
                 y=5.5, h=0.7, sz=15),
            sldnum_ph(ids)]


def s_xbar_timeline(ids):
    return [title_ph(ids, "Parallelism, Not Latency"),
            lo.pic(ids, "xbar_timeline_4x4", L, 1.65, 8.0, 3.8, align="l"),
            textbox(ids, 8.95, 1.75, 3.6, 3.7, [
                kit.bullet("4x4: four 16-beat writes issued at cycle 0", sz=14, spcBef=0),
                kit.bullet("Crossbar, own slaves: done at 21, 24, 27, 30.  One **address "
                           "arbiter** still starts them 3 cycles apart: shared address, "
                           "multiple data", sz=14),
                kit.bullet("Every other case: one burst after another, 20 cycles each", sz=14)]),
            band(ids, "A crossbar buys **parallelism**, not latency: one write takes about 20 "
                      "cycles either way.", y=5.6, h=0.6, sz=16),
            sldnum_ph(ids)]


# ========================================================== section 2 ======
# AXI master transactions, through Waveflow's read and write adaptors
# (MemRStream / MemWStream).  C++ names are the generated headers' (MRCmd,
# MWCmd, MemComplete); the streams are named by role, rd_cmd / rd_data /
# rd_done, because the C++ completion port is still called s_done while the
# Python one was renamed m_done.

def gantt(ids, rows, tmax, ticks, x=5.9, y=2.0, w=6.65, lab_w=1.2, row_h=0.46, gap=0.16):
    """rows = [(label, [(start, end, text, fill, text_color), ...]), ...]."""
    x0, scale = x + lab_w, (w - lab_w) / tmax
    out = []
    for k, (name, spans) in enumerate(rows):
        ry = y + k * (row_h + gap)
        out.append(label(ids, x, ry + 0.07, lab_w - 0.1, row_h, name, sz=13, color=TEXT))
        out.append(shape(ids, x0, ry, w - lab_w, row_h, fill="F7F7F7", line=None))
        for s, e, text, fill, tcol in spans:
            out.append(shape(ids, x0 + s * scale, ry + 0.04, (e - s) * scale, row_h - 0.08,
                             fill=fill, line=WHITE, lw=0.75,
                             paras=[para(text, sz=11, color=tcol, b=True, align="ctr")]))
    ay = y + len(rows) * (row_h + gap) - gap + 0.05
    for c in ticks:
        out.append(label(ids, x0 + c * scale - 0.3, ay, 0.6, 0.25, str(c), sz=10, align="ctr"))
    out.append(label(ids, x, ay, lab_w - 0.1, 0.25, "cycle", sz=10))
    return out


def s_why_transactional(ids):
    kx, ax, mx = 6.3, 8.55, 11.0
    out = [title_ph(ids, "A Data Mover for Memory"),
           col(ids, L, 5.3, [
               "A kernel could drive its `m_axi` port itself",
               ("-", "Addresses, bursts and waiting all mixed into the compute"),
               "Instead: an **adaptor** owns the port",
               ("-", "The kernel sends a **command** on a stream"),
               ("-", "Gets the **data** on a stream"),
               ("-", "And a **completion** when the burst is done"),
               "The kernel sees **only streams**, as in unit 5",
               "Commands from many requesters can be **merged** onto one port"],
               h=4.0, sz=17, sub=15)]
    out.append(shape(ids, kx, 2.0, 1.55, 3.0, fill=TINT, line=VIOLET, lw=1.25, prst="roundRect",
                     adj=8000, paras=[para("Kernel", sz=15, color=TEXT, b=True, align="ctr")]))
    for y, name in ((2.0, "Read adaptor"), (3.75, "Write adaptor")):
        out.append(shape(ids, ax, y, 1.75, 1.25, fill=SLATETINT, line=SLATE, lw=1.25,
                         prst="roundRect", adj=10000,
                         paras=[para(name, sz=14, color=TEXT, b=True, align="ctr")]))
    out.append(shape(ids, mx, 2.0, 1.55, 3.0, fill=TEALTINT, line=TEAL, lw=1.25, prst="roundRect",
                     adj=8000, paras=[para("Memory", sz=15, color=TEXT, b=True, align="ctr")]))
    k2, a1, a2, m1 = kx + 1.55, ax, ax + 1.75, mx
    out += [arrow(ids, k2, 2.25, a1, 2.25, VIOLET, lw=1.5),
            label(ids, k2, 1.95, a1 - k2, 0.3, "command", sz=11, align="ctr"),
            arrow(ids, a1, 2.65, k2, 2.65, TEAL, lw=1.5),
            label(ids, k2, 2.35, a1 - k2, 0.3, "data", sz=11, align="ctr"),
            arrow(ids, a1, 3.0, k2, 3.0, SLATE, lw=1.5, dash=True),
            label(ids, k2, 2.7, a1 - k2, 0.3, "done", sz=11, align="ctr"),
            arrow(ids, k2, 4.0, a1, 4.0, VIOLET, lw=1.5),
            label(ids, k2, 3.7, a1 - k2, 0.3, "command", sz=11, align="ctr"),
            arrow(ids, k2, 4.4, a1, 4.4, TEAL, lw=1.5),
            label(ids, k2, 4.1, a1 - k2, 0.3, "data", sz=11, align="ctr"),
            arrow(ids, a1, 4.75, k2, 4.75, SLATE, lw=1.5, dash=True),
            label(ids, k2, 4.45, a1 - k2, 0.3, "done", sz=11, align="ctr"),
            arrow(ids, m1, 2.6, a2, 2.6, TEAL, lw=2.0),
            arrow(ids, a2, 4.35, m1, 4.35, TEAL, lw=2.0),
            label(ids, a2, 2.25, m1 - a2, 0.3, "m_axi", sz=11, align="ctr"),
            label(ids, a2, 4.0, m1 - a2, 0.3, "m_axi", sz=11, align="ctr"),
            card(ids, L, 5.4, W, 0.75, [para(
                "Industry name: a **DMA engine** driven by descriptors, such as AMD's AXI DataMover.  "
                "Waveflow's adaptors are a small one: no scatter-gather.", sz=14, color=TEXT)],
                anchor="ctr"),
            sldnum_ph(ids)]
    return out


def s_concurrent(ids):
    y, h = 2.35, 0.95
    boxes = [(6.9, "Read adaptor", SLATETINT, SLATE), (8.95, "Kernel", TINT, VIOLET),
             (11.0, "Write adaptor", SLATETINT, SLATE)]
    bw = 1.55
    out = [title_ph(ids, "Concurrent Tasks"),
           col(ids, L, 5.6, [
               "The kernel and its two adaptors are **three tasks running at once**",
               ("-", "A first in this course: until now a kernel was one function, called once "
                     "per job"),
               "Each task is a body that is **re-fired** whenever its input arrives",
               ("-", "No `ap_start`, no `ap_done`, no outer loop"),
               "Tasks share **nothing but streams**",
               ("-", "And the `m_axi` port, owned by one adaptor each")],
               h=3.6, sz=17, sub=15)]
    for x, name, fill, line in boxes:
        out.append(shape(ids, x, y, bw, h, fill=fill, line=line, lw=1.25, prst="roundRect",
                         adj=10000, paras=[para(name, sz=14, color=TEXT, b=True, align="ctr")]))
        out.append(label(ids, x, y - 0.32, bw, 0.3, "task", sz=11, align="ctr"))
    for x1, x2 in ((6.9 + bw, 8.95), (8.95 + bw, 11.0)):
        out.append(arrow(ids, x1, y + h / 2, x2, y + h / 2, VIOLET, lw=2.0, head=False))
        out.append(label(ids, x1 - 0.1, y + h / 2 + 0.05, x2 - x1 + 0.2, 0.3, "streams", sz=11,
                         align="ctr"))
    my = 4.15
    out += [shape(ids, 6.9, my, 5.65, 0.5, fill=TEALTINT, line=TEAL, lw=1.25, prst="roundRect",
                  adj=20000, paras=[para("Memory, over the interconnect", sz=13, color=TEXT,
                                         b=True, align="ctr")]),
            arrow(ids, 6.9 + bw / 2, my, 6.9 + bw / 2, y + h, TEAL, lw=1.75),
            arrow(ids, 11.0 + bw / 2, y + h, 11.0 + bw / 2, my, TEAL, lw=1.75),
            band(ids, "Units 7–8: one function, called, returns.  Now: tasks that never return, "
                      "all busy at once.", y=5.45, h=0.65, sz=16),
            sldnum_ph(ids)]
    return out


TOP_SRC = """
void copy_top(hls::stream<word_t>& s_cmd,
              const word_t* m_in, word_t* m_out,
              hls::stream<word_t>& s_done) {
#pragma HLS INTERFACE axis  port=s_cmd
#pragma HLS INTERFACE axis  port=s_done
#pragma HLS INTERFACE m_axi port=m_in  offset=off bundle=gmem0
#pragma HLS INTERFACE m_axi port=m_out offset=off bundle=gmem1
#pragma HLS stable variable=m_in
#pragma HLS stable variable=m_out
#pragma HLS INTERFACE ap_ctrl_none port=return
    hls_thread_local hls::stream<word_t> rd_cmd;
    hls_thread_local hls::stream<word_t> wr_cmd;
    hls_thread_local hls::stream<word_t> data;
    hls_thread_local hls::task t0(ctrl_task,  s_cmd, rd_cmd, wr_cmd);
    hls_thread_local hls::task t1(read_task,  rd_cmd, m_in, data);
    hls_thread_local hls::task t2(write_task, wr_cmd, data, m_out, s_done);
}"""


def s_hls_task(ids):
    return [title_ph(ids, "Concurrent Tasks in Vitis: hls::task"),
            lo.code(ids, L, 1.75, 7.1, TOP_SRC, sz=10.5),
            label(ids, L, 5.2, 7.1, 0.4, "A copy kernel: Waveflow's `mem_copy` top, simplified.",
                  sz=12),
            textbox(ids, 8.15, 1.75, 4.4, 4.3, [
                kit.bullet("The top **declares channels and tasks**, and computes nothing", sz=15,
                           spcBef=0),
                kit.bullet("`hls_thread_local`: each stream and task is one piece of hardware, "
                           "for the life of the kernel", sz=15),
                kit.bullet("`hls::task t(f, args…)`: f runs whenever its inputs have data", sz=15),
                kit.bullet("`ap_ctrl_none`: nobody starts the kernel", sz=15),
                kit.bullet("A task body is **one firing**.  What must survive between firings is "
                           "`static`", sz=15)]),
            sldnum_ph(ids)]


# One colour per role, the same in the code and in the drawing.
EXT_C, TASK_C, STREAM_C = SLATE, VIOLET, TEAL
ROLE = {**{t: EXT_C for t in ("s_cmd", "s_done", "m_in", "m_out")},
        **{t: TASK_C for t in ("ctrl_task", "read_task", "write_task", "t0", "t1", "t2")},
        **{t: STREAM_C for t in ("rd_cmd", "wr_cmd", "data")}}
_TOKEN = re.compile(r"\b(" + "|".join(sorted(ROLE, key=len, reverse=True)) + r")\b")


def colour_code(ids, x, y, w, src, sz=10.5, inset=0.16):
    """A code box whose role tokens are bold and coloured; the rest as kit.code_box."""
    lines = src.strip("\n").split("\n")
    paras = []
    for ln in lines:
        runs, pos = [], 0
        for m in _TOKEN.finditer(ln):
            if m.start() > pos:
                runs.append(kit.run(ln[pos:m.start()], sz=sz, color=TEXT, font="code"))
            runs.append(kit.run(m.group(0), sz=sz, color=ROLE[m.group(0)], b=True, font="code"))
            pos = m.end()
        if pos < len(ln):
            runs.append(kit.run(ln[pos:], sz=sz, color=TEXT, font="code"))
        paras.append(f"<a:p>{''.join(runs)}{kit.rpr(sz=sz, tag='a:endParaRPr')}</a:p>")
    h = 2 * inset + len(lines) * sz * 1.22 / 72
    return shape(ids, x, y, w, h, fill=kit.CODEFILL, line=kit.GRAYLINE, lw=0.75, anchor="t",
                 inset=inset, paras=paras)


def _role_box(ids, x, y, w, h, text, role, sz=13):
    fill = {EXT_C: SLATETINT, TASK_C: TINT, STREAM_C: TEALTINT}[role]
    return shape(ids, x, y, w, h, fill=fill, line=role, lw=1.5, prst="roundRect", adj=18000,
                 paras=[para(text, sz=sz, color=role, b=True, align="ctr")])


def s_top_mapped(ids):
    # task boxes: (x, y, w, h)
    ctrl, rd, wr, th = (8.65, 2.75, 2.3), (7.95, 3.95, 1.75), (10.75, 3.95, 1.75), 0.6
    out = [title_ph(ids, "Reading the Top: Code and Hardware"),
           colour_code(ids, L, 1.75, 6.95, TOP_SRC, sz=10.5),
           # external interfaces
           _role_box(ids, 9.15, 1.8, 1.3, 0.45, "s_cmd", EXT_C),
           _role_box(ids, 8.2, 5.15, 1.25, 0.45, "m_in", EXT_C),
           _role_box(ids, 10.5, 5.15, 1.05, 0.45, "m_out", EXT_C),
           _role_box(ids, 11.65, 5.15, 0.9, 0.45, "s_done", EXT_C, sz=12),
           # tasks
           _role_box(ids, ctrl[0], ctrl[1], ctrl[2], th, "t0: ctrl_task", TASK_C),
           _role_box(ids, rd[0], rd[1], rd[2], th, "t1: read_task", TASK_C),
           _role_box(ids, wr[0], wr[1], wr[2], th, "t2: write_task", TASK_C),
           # wires to the outside
           arrow(ids, 9.8, 2.25, 9.8, ctrl[1], EXT_C, lw=1.75),
           arrow(ids, 8.825, 5.15, 8.825, rd[1] + th, EXT_C, lw=1.75),
           arrow(ids, 11.025, wr[1] + th, 11.025, 5.15, EXT_C, lw=1.75),
           arrow(ids, 12.1, wr[1] + th, 12.1, 5.15, EXT_C, lw=1.75),
           # streams between tasks
           arrow(ids, 9.2, ctrl[1] + th, 8.825, rd[1], STREAM_C, lw=2.25),
           arrow(ids, 10.4, ctrl[1] + th, 11.625, wr[1], STREAM_C, lw=2.25),
           arrow(ids, rd[0] + rd[2], rd[1] + th / 2, wr[0], wr[1] + th / 2, STREAM_C, lw=2.25),
           label(ids, 7.4, 3.3, 1.4, 0.3, "rd_cmd", sz=12, color=STREAM_C, b=True,
                 align="r"),
           label(ids, 11.15, 3.4, 1.4, 0.3, "wr_cmd", sz=12, color=STREAM_C, b=True),
           label(ids, rd[0] + rd[2], rd[1] - 0.02, wr[0] - rd[0] - rd[2], 0.3, "data", sz=12,
                 color=STREAM_C, b=True, align="ctr")]
    # legend, under the code
    lx = L
    for name, role in (("external interface", EXT_C), ("task", TASK_C),
                       ("stream between tasks", STREAM_C)):
        out.append(_role_box(ids, lx, 5.55, 0.32, 0.26, "", role))
        out.append(label(ids, lx + 0.4, 5.52, 2.3, 0.3, name, sz=13, color=role, b=True))
        lx += 2.45
    out.append(sldnum_ph(ids))
    return out


def s_task_streams(ids):
    return [title_ph(ids, "Streams Between Tasks"),
            kit.heading(ids, L, 1.75, 6.0, "THE RULES WE FOLLOW"),
            textbox(ids, L, 2.1, 6.0, 3.3, [
                kit.bullet("A task takes **streams** (`hls::stream`, `hls::stream_of_blocks`) "
                           "and nothing else, except…", sz=15, spcBef=0),
                kit.bullet("…an `m_axi` pointer, only as `stable` with `offset=off`: the one form "
                           "Vitis supports on a task", sz=15),
                kit.bullet("**No shared arrays or variables** between tasks", sz=15),
                kit.bullet("**One owner per `m_axi` port**, and it touches only streams.  Sharing "
                           "a port takes an arbiter: the adaptor's job", sz=15)]),
            card(ids, 7.05, 1.75, 5.5, 1.75, [
                para("**Why streams make concurrency safe**", sz=15, color=TEXT, spcAft=4),
                para("Each task's results depend only on the **order and values** it reads, never "
                     "on timing: unit 5's message queues.  The same idea outside hardware: Go "
                     "channels, actors, MPI.", sz=14, color=TEXT)]),
            card(ids, 7.05, 3.7, 5.5, 1.35, fill=kit.AMBERTINT, paras=[
                para("^^The cost: deadlock^^", sz=15, spcAft=4),
                para("A read on a stream that never fills **hangs** the design: no wrong answer, "
                     "no error.  Unit 10 returns to this.", sz=14, color=TEXT)]),
            label(ids, L, 5.55, W, 0.6,
                  "Waveflow found other forms of `m_axi` pointer deadlock at RTL after a few jobs, "
                  "while C simulation passed.  Its notes: "
                  "docs/guide/comp_codegen/freerunning_composite.md", sz=12),
            label(ids, L, 6.05, W, 0.35,
                  "**Unit 10** covers concurrent tasks in much more depth: pipelining them, "
                  "sizing their streams, and avoiding deadlock.", sz=14, color=TEXT),
            sldnum_ph(ids)]


ADAPTOR_SRC = """
template <int MEM_DW>
void mem_r_stream_task(
    hls::stream<ap_uint<MEM_DW>>& rd_cmd,
    const ap_uint<MEM_DW>* m_mem,       // m_axi
    hls::stream<ap_uint<MEM_DW>>& rd_data) {
    MRCmd c;
    c.read_stream<MEM_DW>(rd_cmd);      // one command
    for (int w = 0; w < c.len; ++w) {
#pragma HLS PIPELINE II=1
        rd_data.write(m_mem[c.addr + w]);   // the burst
    }
}"""


def s_read_adaptor(ids):
    rows = [["Field", "Meaning"],
            ["`addr`", "Where to start: a **word offset** in the buffer, not a byte address"],
            ["`len`", "How many words"],
            ["`xfer_len`", "How many words of the tag are used"],
            ["`xfer_msg`", "The **tag**: up to 8 words, echoed back on the completion"]]
    return [title_ph(ids, "The Read Adaptor"),
            kit.heading(ids, L, 1.75, 5.6, "THE COMMAND, MRCmd"),
            table(ids, L, 2.1, [1.4, 4.3], rows, rowh=0.5, sz=14),
            label(ids, L, 4.7, 5.7, 0.7,
                  "The write adaptor's `MWCmd` has the same fields.  Its data arrives on a stream "
                  "and is written from `addr` on.", sz=13, color=TEXT),
            card(ids, L, 5.45, W, 0.8, [para(
                "By convention the adaptors move **words**, the memory's width (here 64 bits), "
                "not data types.  The kernel **packs** its values into words and **unpacks** "
                "them: four 16-bit samples per word, say.  `len` counts words.", sz=14,
                color=TEXT)], anchor="ctr"),
            kit.heading(ids, 6.75, 1.75, 5.8, "THE WHOLE ADAPTOR (SIMPLIFIED)"),
            lo.code(ids, 6.75, 2.1, 5.8, ADAPTOR_SRC, sz=11),
            label(ids, 6.75, 4.7, 5.8, 0.7,
                  "Waveflow's `mem_r_stream_task.h`.  The `_done` variant then writes a "
                  "`MemComplete`: the word count and the tag.", sz=12),
            sldnum_ph(ids)]


def s_tags(ids):
    fb = kit.field_bar
    return [title_ph(ids, "Tags: Matching Completions"),
            col(ids, L, 6.1, [
                "Every command carries a **tag**, `xfer_msg`",
                "The adaptor **echoes it** on the completion, unread",
                "The requester decides what it means",
                ("-", "A job number, which buffer, who asked"),
                "So several jobs can be **in flight**, and an arbiter can merge requesters "
                "without remembering who asked what",
                "The stage that issues a read need not be the one that takes the data: "
                "the start of **task pipelining** (unit 10)"],
                h=4.1, sz=16, sub=14),
            kit.heading(ids, 7.2, 1.8, 5.3, "COMMAND"),
            *fb(ids, 7.2, 2.1, 0.55, [
                (1.5, TINT, TEXT, [("addr 512", 13, False)]),
                (1.4, TINT, TEXT, [("len 64", 13, False)]),
                (1.9, TEALTINT, TEAL, [("tag: job 7", 13, True)])]),
            arrow(ids, 9.85, 2.75, 9.85, 3.45, SLATE, lw=1.75),
            label(ids, 10.0, 2.85, 2.5, 0.4, "the adaptor runs the burst", sz=12),
            kit.heading(ids, 7.2, 3.5, 5.3, "COMPLETION"),
            *fb(ids, 7.2, 3.8, 0.55, [
                (2.9, TINT, TEXT, [("len 64", 13, False)]),
                (1.9, TEALTINT, TEAL, [("tag: job 7", 13, True)])]),
            card(ids, 7.2, 4.65, 4.8, 1.05, [para(
                "Industry: AXI's own **transaction IDs** (ARID, AWID) do this inside the "
                "interconnect; NVMe and NICs use **completion queues**.", sz=13, color=TEXT)]),
            sldnum_ph(ids)]


def s_burst_timing(ids):
    rows = [["Transfer", "Cycles"],
            ["write, 1 beat", "7"], ["write, 8 / 16 beats", "17 / 21"],
            ["read, 8 / 16 beats", "12 / 20"]]
    return [title_ph(ids, "Timing a Burst"),
            col(ids, L, 6.3, [
                "A burst of n words takes about **L + n** cycles",
                ("-", "L: the address handshake, the interconnect, the memory's own latency"),
                ("-", "Then one word per cycle"),
                "L is a few cycles to on-chip memory; **tens** to DDR",
                "An AXI burst is at most **256 beats**, and may not cross a 4 KB boundary",
                ("-", "A longer transfer is several bursts, each paying L"),
                ("-", "Unless the master issues the next address early: outstanding requests"),
                "Reads and writes have **separate channels**: they can overlap"],
                h=4.3, sz=16, sub=14),
            kit.heading(ids, 7.5, 1.8, 5.0, "MEASURED THROUGH AMD'S CROSSBAR"),
            table(ids, 7.5, 2.15, [3.0, 2.0], ctr(rows), rowh=0.45, sz=14),
            label(ids, 7.5, 4.05, 5.0, 0.9,
                  "Waveflow, under XSI, to an on-chip memory: about **5 + n**.  "
                  "docs/guide/interface/axi_mm/crossbar.md", sz=12),
            homework(ids, ["AXI write burst timing", "AXI4 timing diagram"]),
            sldnum_ph(ids)]


JOB_L, JOB_N, JOB_D = 10, 64, 6


# ---- section 2's running example: a histogram ------------------------------
# The code and the measured numbers come from demos/histogram (being built on
# branch demo/histogram).  Until then the slides that need them carry a draft
# note or a placeholder.

def draft_note(ids, text, y=6.2):
    return label(ids, L, y, W, 0.32, f"^^Draft^^: {text}", sz=12)


def placeholder(ids, title, lines):
    return [title_ph(ids, title),
            shape(ids, L, 1.8, W, 3.9, fill="FFFBF7", line=AMBER, lw=1.25, dash=True,
                  anchor="t", inset=0.3,
                  paras=[para("^^To come from demos/histogram^^", sz=16, spcAft=8)] +
                        [kit.bullet(t, sz=15) for t in lines]),
            sldnum_ph(ids)]


def s_hist_example(ids):
    out = [title_ph(ids, "A Running Example: A Histogram"),
           col(ids, L, 5.7, [
               "Count how many of n samples fall in each of a few **bins**",
               ("-", "Bin = x >> shift: uniform bins, no search"),
               "A good first example",
               ("-", "The samples are many: they live in **memory**"),
               ("-", "The result is small: a few counts"),
               ("-", "Each sample is read once"),
               "The host puts the samples in memory and sends a **command**; the kernel "
               "reads, counts, writes the counts back, and sends a **response**"],
               h=4.0, sz=16, sub=14)]
    tb, kx, dy = (6.95, 1.95, 1.6, 2.1), (9.75, 1.95, 2.0, 2.1), 4.55
    out += [shape(ids, tb[0], tb[1], tb[2], tb[3], fill=SLATETINT, line=SLATE, lw=1.25,
                  prst="roundRect", adj=8000, anchor="t", inset=0.15,
                  paras=[para("Host or testbench", sz=14, color=TEXT, b=True, align="ctr")]),
            shape(ids, kx[0], kx[1], kx[2], kx[3], fill=TINT, line=VIOLET, lw=1.25,
                  prst="roundRect", adj=8000,
                  paras=[para("Histogram kernel", sz=14, color=TEXT, b=True, align="ctr")]),
            arrow(ids, tb[0] + tb[2], 2.45, kx[0], 2.45, SLATE, lw=1.75),
            label(ids, tb[0] + tb[2], 2.1, kx[0] - tb[0] - tb[2], 0.3, "s_cmd", sz=12,
                  color=SLATE, b=True, align="ctr"),
            arrow(ids, kx[0], 3.55, tb[0] + tb[2], 3.55, SLATE, lw=1.75),
            label(ids, tb[0] + tb[2], 3.2, kx[0] - tb[0] - tb[2], 0.3, "s_done", sz=12,
                  color=SLATE, b=True, align="ctr"),
            shape(ids, 6.95, dy, 4.8, 0.6, fill=TEALTINT, line=TEAL, lw=1.25, prst="roundRect",
                  adj=20000, paras=[para("DDR: samples in, counts out", sz=14, color=TEXT, b=True,
                                         align="ctr")]),
            arrow(ids, 10.35, dy, 10.35, kx[1] + kx[3], TEAL, lw=1.75),
            arrow(ids, 11.15, kx[1] + kx[3], 11.15, dy, TEAL, lw=1.75),
            label(ids, 9.4, 4.1, 0.9, 0.3, "samples", sz=11, color=TEAL, align="r"),
            label(ids, 11.25, 4.1, 0.9, 0.3, "counts", sz=11, color=TEAL)]
    # a small histogram, for the eye
    for k, hgt in enumerate([0.2, 0.45, 0.75, 0.95, 0.65, 0.35, 0.15]):
        out.append(shape(ids, 7.2 + k * 0.17, 3.85 - hgt, 0.14, hgt, fill=VIOLET, line=None))
    out += [band(ids, "`histogram_stream`: command and response on **streams**.  Section 4: the "
                      "same kernel with them in memory-mapped queues, `histogram_mm`.",
                 y=5.45, h=0.7, sz=15),
            sldnum_ph(ids)]
    return out


def s_hist_format(ids):
    cmd = [["Command field", "Meaning"],
           ["`job`", "A number the host chooses; echoed in the response"],
           ["`samp_off`, `n`", "Where the samples are (a **word offset**), and how many"],
           ["`cnt_off`", "Where to write the counts"],
           ["`shift`", "The bin width: bin = x >> shift"]]
    rsp = [["Response field", "Meaning"],
           ["`job`", "Which command this answers"],
           ["`status`", "0: done.  Nonzero: refused, e.g. n too large"]]
    return [title_ph(ids, "Histogram: Command and Response"),
            table(ids, L, 1.8, [2.1, 4.6], cmd, rowh=0.48, sz=14),
            table(ids, 7.75, 1.8, [1.7, 3.1], rsp, rowh=0.48, sz=14),
            textbox(ids, 7.75, 3.4, 4.8, 2.0, [
                kit.bullet("Each is one message on a stream, as in unit 5", sz=14, spcBef=0),
                kit.bullet("The response is sent only **after the counts are in memory**: the "
                           "host may read them as soon as it arrives", sz=14)]),
            draft_note(ids, "the fields will match demos/histogram's code once it is built."),
            sldnum_ph(ids)]


def s_hist_tasks(ids):
    return placeholder(ids, "The Histogram's Tasks", [
        "The block diagram of the histogram's top: control, read adaptor, compute, write "
        "adaptor, response",
        "The top's code beside it, coloured as on the copy kernel: interfaces, tasks, streams",
        "What each stream carries: commands, samples, counts, completions"])


def s_hist_ctrl(ids):
    return placeholder(ids, "The Control Task", [
        "Reads the command; checks it; issues the MRCmd for the samples and the MWCmd for the "
        "counts, both tagged with the job",
        "Passes a job descriptor (n, shift) to the compute task"])


def s_hist_compute(ids):
    return placeholder(ids, "The Compute Task", [
        "Takes the descriptor, then n samples straight off the read stream",
        "counts[x >> shift]++ at II = 1, and how the read-modify-write on a repeated bin is "
        "handled (unit 7)",
        "Streams the counts to the write adaptor"])


def s_hist_resp(ids):
    return placeholder(ids, "The Response Task", [
        "Waits for the write adaptor's completion: the counts are in memory",
        "Sends the response with the job from the completion's tag"])


H_L, H_N, H_D, H_NB = 10, 256, 4, 16


def s_hist_timing(ids):
    r_end = H_L + H_N
    c_end = r_end + H_D
    w_end = c_end + H_L + H_NB
    lat = (GRAYFILL, TEXT)
    rows = [("Read samples", [(0, H_L, "L", *lat), (H_L, r_end, f"{H_N} samples", TEAL, WHITE)]),
            ("Compute", [(H_L + 1, c_end, "one sample per cycle, as they arrive", VIOLET,
                          WHITE)]),
            ("Write counts", [(c_end, c_end + H_L, "L", *lat),
                              (c_end + H_L, w_end, f"{H_NB}", TEAL, WHITE)]),
            ("Response", [(w_end, w_end + 3, "", SLATE, WHITE)])]
    return [title_ph(ids, "Timing a Histogram Job"),
            col(ids, L, 4.9, [
                "The read: L, then one sample per cycle",
                "Compute takes each sample **as it arrives**: no buffer, it hides under the read",
                "The counts wait for the **last** sample, then a short write",
                "The response waits for the write's completion"],
                h=3.4, sz=15, sub=13),
            *gantt(ids, rows, w_end + 3, [0, c_end, w_end]),
            label(ids, 5.9, 4.6, 6.65, 0.5,
                  f"n = {H_N}, L = {H_L}, pipeline depth D = {H_D}, {H_NB} bins: about "
                  f"{w_end} cycles", sz=13, color=TEXT),
            band(ids, "Job ≈ L + n + D + L + bins.  The compute costs almost nothing: it "
                      "overlaps the read.", y=5.3, h=0.6, sz=16),
            draft_note(ids, "illustrative numbers.  The measured ones come from "
                            "demos/histogram under XSI."),
            sldnum_ph(ids)]


SCALE_SKEL = """
void scale_task(hls::stream<word_t>& s_cmd,
                hls::stream<word_t>& rd_cmd,
                hls::stream<word_t>& rd_data,
                hls::stream<word_t>& wr_cmd,
                hls::stream<word_t>& wr_data) {
    ScaleCmd c;              // job, x_off, y_off, n, a, b
    c.read_stream<64>(s_cmd);

    MRCmd rc;                // (a)
    rc.addr = ____;   rc.len = ____;
    rc.xfer_len = 1;  rc.xfer_msg.data[0] = ____;
    rc.write_stream<64>(rd_cmd);

    MWCmd wc;                // (b)
    wc.addr = ____;   wc.len = ____;
    wc.xfer_len = 1;  wc.xfer_msg.data[0] = ____;
    wc.write_stream<64>(wr_cmd);

    // (c)  y[i] = a * x[i] + b, one word per cycle
}"""

SCALE_LOOP = """
for (int i = 0; i < c.n; i++) {
#pragma HLS PIPELINE II=1
    word_t x = rd_data.read();
    wr_data.write(c.a * x + c.b);
}"""


def s_scale_practice(ids):
    return [title_ph(ids, "Writing a Task: y = a·x + b"), pill(ids, "PRACTICE"),
            lo.code(ids, L, 1.75, 6.6, SCALE_SKEL, sz=10.5),
            textbox(ids, 7.6, 1.75, 4.95, 4.4, [
                para("One task reads a command with `x_off`, `y_off`, `n`, `a`, `b`, and drives "
                     "a read and a write adaptor.  x and y are 64-bit, the memory's width: "
                     "one element per word.", sz=15, color=TEXT, spcAft=6),
                part("(a)", "Fill in the read command", 15),
                part("(b)", "Fill in the write command", 15),
                part("(c)", "Write the loop, at II = 1", 15),
                part("(d)", "The write command goes out before any data.  Why is that safe?",
                     15),
                part("(e)", "Who should send the response to the host, and when?", 15)]),
            sldnum_ph(ids)]


def s_scale_solution(ids):
    return [title_ph(ids, "Writing a Task: y = a·x + b"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 6.4, 4.4, [
                part("(a)", "`rc.addr = c.x_off; rc.len = c.n;` tag `c.job`.  len = n only "
                            "because each element fills a word: 16-bit x, four to a word, "
                            "would need len = n/4 and a loop that unpacks", 15, spcBef=0),
                part("(b)", "`wc.addr = c.y_off; wc.len = c.n;` tag `c.job`", 15),
                part("(c)", "The loop on the right: one read and one write per iteration", 15),
                part("(d)", "The writer only **queues** it: it writes each word as it arrives on "
                            "`wr_data`, and waits otherwise", 15),
                part("(e)", "Whoever reads the **write adaptor's completion**: only then are the "
                            "words in memory.  Not this task: its last write leaves before they "
                            "land", 15)]),
            lo.code(ids, 7.35, 1.8, 5.2, SCALE_LOOP, sz=12),
            errcard(ids, 7.35, 3.55, 5.2, 2.2, "Common errors",
                    ["Byte addresses: the adaptors take word offsets.",
                     "Leaving a completion stream unread: once its FIFO is full the adaptor "
                     "stops, a deadlock several jobs later."]),
            sldnum_ph(ids)]


def s_scale_timing_practice(ids):
    return [title_ph(ids, "Timing y = a·x + b"), pill(ids, "PRACTICE"),
            lo.code(ids, L, 1.75, 5.2, SCALE_LOOP, sz=12),
            label(ids, L, 3.4, 5.2, 2.6,
                  "A read delivers its first word L cycles after its command, then one per "
                  "cycle.  A write completes L cycles after its last word arrives.  The loop "
                  "has pipeline depth D.  Use L = 10, D = 4, n = 1024, and let each transfer be "
                  "one burst.", sz=14, color=TEXT),
            textbox(ids, 6.3, 1.75, 6.25, 4.4, [
                part("(a)", "Draw the read, compute and write on one timeline.  When does the "
                            "write complete?", 15, spcBef=0),
                part("(b)", "The loop only reaches II = 2.  When now?", 15),
                part("(c)", "Another version first copies all of x into a local array, then "
                            "computes y into another, then streams y out.  When?", 15),
                part("(d)", "Which version would you build, and when is the other one "
                            "necessary?", 15)]),
            sldnum_ph(ids)]


def s_scale_timing_solution(ids):
    L_, D_, n_ = 10, 4, 1024
    a_ = 2 * L_ + D_ + n_
    b_ = 2 * L_ + D_ + 2 * n_
    c_ = 2 * L_ + 3 * n_ + D_
    lat = (GRAYFILL, TEXT)
    rows = [("Read x", [(0, L_, "", *lat), (L_, L_ + n_, "x", TEAL, WHITE)]),
            ("Compute", [(L_ + 1, L_ + D_ + n_, "a·x + b", VIOLET, WHITE)]),
            ("Write y", [(L_ + D_, L_ + D_ + n_, "y", TEAL, WHITE),
                         (L_ + D_ + n_, a_, "", *lat)])]
    return [title_ph(ids, "Timing y = a·x + b"), pill(ids, "SOLUTION"),
            *gantt(ids, rows, a_, [0, a_], x=L, y=1.85, w=6.2),
            textbox(ids, 7.25, 1.8, 5.3, 4.3, [
                part("(a)", f"All three overlap: the last y reaches the writer at L + D + n, so "
                            f"it completes at 2L + D + n = !!{a_:,}!!", 14, spcBef=0),
                part("(b)", f"The full stream holds back the read: one word per 2 cycles, "
                            f"!!≈ {b_:,}!!", 14),
                part("(c)", f"Three phases in sequence: (L + n) + (n + D) + (n + L) = "
                            f"!!{c_:,}!!, about 3×", 14),
                part("(d)", "Stream when each word is used once, in order.  Buffer when it is "
                            "reused or read out of order, as the histogram's counts are.  "
                            "Unit 10 overlaps the buffered phases across jobs", 14)]),
            label(ids, L, 4.2, 6.2, 0.5, "(a), to scale: read, compute and write overlap.",
                  sz=12),
            sldnum_ph(ids)]


# ============================================================== passes ====
MIGRATED_MARKER = "Bus or Crossbar?"   # a slide only this script makes

EXPECTED = {1: "Unit 8", 2: "Learning Objectives", 3: "Outline", 4: "Addressable Memory",
            6: "Dedicated vs Shared Memory", 7: "Why Share Memory?",
            8: "How to Build Shared Memory", 11: "Interconnect",
            12: "Transactions, Master and Slaves", 13: "Bus Topology", 14: "Crossbar Topology",
            15: "Other Topologies", 23: "Streaming vs. Shared Memory",
            24: "Streaming Example:  Simple Video Processing", 25: "Shared Memory Ex:  Mobile SoC",
            26: "Shared Memory Ex:  Nvidia DGX H100",
            19: "Shared Memory Transaction", 20: "Shared Mem Transaction:  Command Phase",
            21: "Shared Mem Transaction:  Compute Phase",
            22: "Shared Mem Transaction:  Response Phase", 28: "AXI Family of Protocols",
            29: "AXI4 Memory Mapped Features", 32: "Review:  AXI4-Lite Write Protocol",
            33: "AXI4-Full Burst Signals", 34: "AXI4 Write Example"}

# ('old', position, builder or None) keeps or rebuilds an old slide; ('new', builder)
# adds one.  Old slides not listed are dropped: 5, 9 and 10 (unit 8 teaches them),
# 16 onward (sections 2-4, to be rebuilt).
PLAN = [
    ("old", 1, None), ("old", 2, s_objectives), ("old", 3, s_outline(0)),
    # section 1: shared memory and interconnects
    ("old", 4, None), ("old", 6, None), ("old", 7, None), ("old", 23, s_stream_vs_shared),
    ("old", 24, None), ("old", 25, None), ("old", 26, None),
    ("old", 8, None), ("old", 11, None), ("old", 12, None),
    ("new", s_master_or_slave), ("new", s_ms_practice), ("new", s_ms_solution),
    ("old", 13, None), ("old", 14, None),
    ("new", s_flow_bus), ("new", s_flow_xbar), ("new", s_flow_half), ("new", s_flow_twice),
    ("new", s_xb_practice), ("new", s_xb_solution),
    ("old", 15, None),
    ("new", s_xbar_demo), ("new", s_xbar_area), ("new", s_xbar_cycles),
    ("new", s_xbar_timeline),
    # section 2: transactional interfaces, on a running example
    ("new", s_outline(1)), ("new", s_hist_example),
    ("old", 20, None), ("old", 21, None), ("old", 22, None), ("new", s_hist_format),
    ("new", s_why_transactional), ("new", s_concurrent), ("new", s_hls_task),
    ("new", s_top_mapped), ("new", s_task_streams), ("new", s_read_adaptor), ("new", s_tags),
    ("new", s_hist_tasks), ("new", s_hist_ctrl), ("new", s_hist_compute), ("new", s_hist_resp),
    ("new", s_scale_practice), ("new", s_scale_solution),
    ("new", s_burst_timing), ("new", s_hist_timing),
    ("new", s_scale_timing_practice), ("new", s_scale_timing_solution),
    # section 3: AXI4 under the hood
    ("new", s_outline(2)),
    ("old", 28, None), ("old", 29, None), ("old", 32, None), ("old", 33, None),
    ("old", 34, None),
]


def text_fixes(old):
    """Content corrections on the slides that are kept, not rebuilt."""
    s = old
    kit.fix(s[1], f"<a:t>{OLD_UNIT}</a:t>", f"<a:t>{UNIT} </a:t>")
    kit.fix(s[1], f"<a:t>{OLD_TITLE}</a:t>", f"<a:t>{NEW_TITLE}</a:t>")
    kit.fix(s[1], "ProfS. Sundeep", "Profs. Sundeep")
    kit.fix(s[12], "<a:t>Transactions, Master and Slaves</a:t>",
            "<a:t>Transactions, Masters and Slaves</a:t>")
    kit.fix(s[7], "PS need operate on same data", "PS need to operate on the same data")
    kit.fix(s[26], "fetch data as need<", "fetch data as needed<")
    kit.fix(s[19], "Later, we will show to map these into memory",
            "Section 3: the same streams, mapped into memory as queues")
    # the three phase slides, told as the histogram
    kit.fix(s[20], "<a:t>input data </a:t>", "<a:t>the samples </a:t>")
    kit.fix(s[20], "Data to be processed", "The n samples to bin")
    kit.fix(s[20], "<a:t>input command </a:t>", "<a:t>the command </a:t>")
    kit.fix(s[20], "Input address:  Where data resides", "samp_off, n:  where the samples are")
    kit.fix(s[20], "Output address:  Where output should reside",
            "cnt_off:  where the counts should go")
    kit.fix(s[20], "Command info:  What to do with data", "shift:  the bin width")
    kit.fix(s[20], "<a:t>Input</a:t>", "<a:t>Samples</a:t>")
    kit.fix(s[20], "<a:t>data</a:t>", "<a:t></a:t>")
    kit.fix(s[21], "<a:t>input data </a:t>", "<a:t>the samples </a:t>")
    kit.fix(s[21], "Uses input address sent in command", "n words at samp_off, from the command")
    kit.fix(s[21], "Kernel processes input data", "Kernel bins each one:  counts[x >> shift]++")
    kit.fix(s[21], "<a:t>Input</a:t>", "<a:t>Samples</a:t>")
    kit.fix(s[21], "<a:t>data</a:t>", "<a:t></a:t>")
    kit.fix(s[21], "<a:t>Computes </a:t>", "<a:t>Bins the </a:t>")
    kit.fix(s[21], "<a:t>results</a:t>", "<a:t>samples</a:t>")
    kit.fix(s[22], "<a:t>output data </a:t>", "<a:t>the counts </a:t>")
    kit.fix(s[22], "Uses output address sent in command", "At cnt_off, from the command")
    kit.fix(s[22], "<a:t>Kernel sends </a:t>",
            "<a:t>Kernel sends the response (job, status) on s_done</a:t>")
    kit.fix(s[22], "<a:t>Output</a:t>", "<a:t>Counts</a:t>")
    kit.fix(s[22], "<a:t>Input</a:t>", "<a:t>Samples</a:t>")
    kit.fix(s[22], "<a:t>data</a:t>", "<a:t></a:t>", count=2)
    kit.fix(s[34], "Before write burst 0 completed", "Before burst 0 ends")


def main():
    args = _parse_args()
    build = (args.work / "unpacked").resolve()
    slides = build / "ppt" / "slides"
    kit.BUILD, kit.SLIDES = build, slides
    lo.BUILD, lo.SLIDES, lo.FIGS = build, slides, args.figs.resolve()
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
