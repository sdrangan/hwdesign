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
  * the unit is now Transactional Interfaces to Memory, in four sections
    (plans/unit9_10_memory_pipelining.md): shared memory and interconnects,
    AXI master transactions, memory-mapped queues and credit, and a histogram
    design example.  Only section 1 is built; the old deck's sections 2-4
    (transaction phases, AXI4-MM signals, the Vitis m_axi histogram) are left
    out, to be rebuilt around Waveflow's adaptors.
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
from build_fifo_slides import (AMBER, L, MUTED, SLATE, SLATETINT, TEAL, TEALTINT, TEXT, TINT,
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


SECTIONS = ["Shared Memory and Interconnects", "AXI Master Transactions",
            "Memory-Mapped Queues and Credit", "Design Example: A Histogram"]


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


# ============================================================== passes ====
MIGRATED_MARKER = "Bus or Crossbar?"   # a slide only this script makes

EXPECTED = {1: "Unit 8", 2: "Learning Objectives", 3: "Outline", 4: "Addressable Memory",
            6: "Dedicated vs Shared Memory", 7: "Why Share Memory?",
            8: "How to Build Shared Memory", 11: "Interconnect",
            12: "Transactions, Master and Slaves", 13: "Bus Topology", 14: "Crossbar Topology",
            15: "Other Topologies", 23: "Streaming vs. Shared Memory",
            24: "Streaming Example:  Simple Video Processing", 25: "Shared Memory Ex:  Mobile SoC",
            26: "Shared Memory Ex:  Nvidia DGX H100"}

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
