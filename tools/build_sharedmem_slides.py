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
    Sections 1-3 are built.  Section 2 keeps the old transaction-phase slides
    and adds the adaptors, hls::task and tags; section 3 keeps the old AXI4
    signal slides and adds burst and job timing.  The old deck's Vitis m_axi
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
            "AXI4 Bursts and Timing", "Memory-Mapped Queues and Credit",
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
    out = [title_ph(ids, "Why a Transactional Interface?"),
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
            label(ids, L, 4.75, 5.7, 0.9,
                  "The write adaptor's `MWCmd` has the same fields.  Its data arrives on a stream "
                  "and is written from `addr` on.", sz=13, color=TEXT),
            kit.heading(ids, 6.75, 1.75, 5.8, "THE WHOLE ADAPTOR (SIMPLIFIED)"),
            lo.code(ids, 6.75, 2.1, 5.8, ADAPTOR_SRC, sz=11),
            label(ids, 6.75, 5.1, 5.8, 0.8,
                  "Waveflow's `mem_r_stream_task.h`.  The `_done` variant then writes a "
                  "`MemComplete`: the word count and the tag.", sz=12),
            sldnum_ph(ids)]


KERNEL_RD = """
MRCmd rc;                        // read n words of x
rc.addr = x_off;   rc.len = n;
rc.xfer_len = 1;   rc.xfer_msg.data[0] = job;
rc.write_stream<64>(rd_cmd);

for (int i = 0; i < n; i++) {
#pragma HLS PIPELINE II=1
    x[i] = rd_data.read();
}
MemComplete rd;
rd.read_stream<64>(rd_done);     // tag == job"""

KERNEL_WR = """
MWCmd wc;                        // write n words of y
wc.addr = y_off;   wc.len = n;
wc.xfer_len = 1;   wc.xfer_msg.data[0] = job;
wc.write_stream<64>(wr_cmd);

for (int i = 0; i < n; i++) {
#pragma HLS PIPELINE II=1
    wr_data.write(y[i]);
}
MemComplete wd;
wd.read_stream<64>(wr_done);     // after the write lands"""


def s_kernel_use(ids):
    return [title_ph(ids, "Using the Adaptors from a Kernel"),
            kit.heading(ids, L, 1.75, 5.75, "READ"),
            lo.code(ids, L, 2.1, 5.75, KERNEL_RD, sz=11),
            kit.heading(ids, 6.8, 1.75, 5.75, "WRITE"),
            lo.code(ids, 6.8, 2.1, 5.75, KERNEL_WR, sz=11),
            band(ids, "Every access to memory is a **command**, a stream of **data**, and a "
                      "**completion**.  The kernel never touches an address bus.",
                 y=5.45, h=0.65, sz=15),
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


def _job_rows(L_, n, d):
    r_end = L_ + n
    c_end = r_end + n + d
    w_end = c_end + L_ + n
    lat = (GRAYFILL, TEXT)
    return ([("Read x", [(0, L_, "L", *lat), (L_, r_end, f"{n} words", TEAL, WHITE)]),
             ("Compute", [(r_end, c_end, f"{n} + {d}", VIOLET, WHITE)]),
             ("Write y", [(c_end, c_end + L_, "L", *lat),
                          (c_end + L_, w_end, f"{n} words", TEAL, WHITE)])],
            [0, r_end, c_end, w_end])


def s_job_timing(ids):
    rows, ticks = _job_rows(JOB_L, JOB_N, JOB_D)
    total = ticks[-1]
    return [title_ph(ids, "Timing a Job"),
            col(ids, L, 4.9, [
                "Load, compute, store, **one after another**",
                ("-", f"Read: L + n"),
                ("-", "Compute, pipelined at II = 1: n + its depth D"),
                ("-", "Write: L + n"),
                "Then the completion goes back to the host"],
                h=3.2, sz=16, sub=14),
            *gantt(ids, rows, total, ticks),
            label(ids, 5.9, 4.1, 6.65, 0.6,
                  f"n = {JOB_N} words, L = {JOB_L}, D = {JOB_D}: the job takes {total} cycles, "
                  f"and memory is idle for the {JOB_N + JOB_D} of the compute.", sz=13,
                  color=TEXT),
            band(ids, "Job time ≈ (L + n_{in}) + (n + D) + (L + n_{out}).  Unit 10 overlaps the "
                      "three phases across jobs.", y=5.3, h=0.65, sz=16),
            sldnum_ph(ids)]


def s_job_practice(ids):
    return [title_ph(ids, "Timing a Vector Add"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 11.8, 4.4, [
                para("A kernel computes z = x + y on N-word vectors.  It loads x, then y, through "
                     "one read adaptor into local buffers; adds them at II = 1 with a pipeline "
                     "depth of 4; then writes z through a write adaptor.  Each burst costs L + n "
                     "with L = 10, and a burst is at most 256 words.", sz=16, color=TEXT,
                     spcAft=6),
                part("(a)", "N = 256.  How many cycles does one job take?", 16),
                part("(b)", "N = 1024.  How many cycles now?  How many of them are latency L?", 16),
                part("(c)", "N = 1024, with x and y in two different memories, each read by its "
                            "own adaptor through a crossbar.  How many cycles?", 16)]),
            sldnum_ph(ids)]


def s_job_solution(ids):
    return [title_ph(ids, "Timing a Vector Add"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 7.0, 4.4, [
                part("(a)", "Read x 266, read y 266, add 256 + 4 = 260, write 266: "
                            "!!1,058 cycles!!", 15, spcBef=0),
                part("(b)", "Each vector is 4 bursts.  Reads 8 × 266 = 2,128; add 1,028; "
                            "writes 4 × 266 = 1,064: !!4,220 cycles!!, of which 12 × 10 = "
                            "!!120!! are latency", 15),
                part("(c)", "The two reads run at once: 4 × 266 = 1,064 to load both.  "
                            "1,064 + 1,028 + 1,064 = !!3,156 cycles!!, 1.34× faster", 15),
                kit.cont("Still three phases in sequence: memory sits idle during the add.  "
                     "Unit 10 overlaps them.", 15, color=MUTED, spcBef=8)]),
            errcard(ids, 8.05, 1.8, 4.5, 2.6, "Common errors",
                    ["Paying L once for a 1,024-word vector: an AXI burst is at most 256 "
                     "beats.",
                     "Counting the add as N cycles: a pipeline of depth D adds D."]),
            sldnum_ph(ids)]


def s_cmd_practice(ids):
    return [title_ph(ids, "Commands for a Convolution"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 11.8, 4.4, [
                para("A kernel computes y[n] = Σ_{i} h[i] x[n − i] for n = 0, …, n_{x} + n_{k} − 2, "
                     "with x zero outside 0 … n_{x} − 1.  The host has put x (n_{x} samples) "
                     "and h (n_{k} taps) in DDR, one per word, and chosen where y goes.  A "
                     "control task in the kernel reads the host's command and drives a read and "
                     "a write adaptor.", sz=16, color=TEXT, spcAft=6),
                part("(a)", "What fields does the host's command need?", 16),
                part("(b)", "List the `MRCmd` and `MWCmd` the control task issues for one job: "
                            "`addr`, `len` and tag for each.  In what order?", 16),
                part("(c)", "What should the tags carry, and why?", 16)]),
            sldnum_ph(ids)]


def s_cmd_solution(ids):
    hi = {"color": TEAL, "b": True}
    rows = [["Command", "addr", "len", "tag"],
            [{"t": "MRCmd", **hi}, "h_off", "n_{k}", "job, h"],
            [{"t": "MRCmd", **hi}, "x_off", "n_{x}", "job, x"],
            [{"t": "MWCmd", **hi}, "y_off", "n_{x} + n_{k} − 1", "job"]]
    return [title_ph(ids, "Commands for a Convolution"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 6.4, 4.4, [
                part("(a)", "A job number; `x_off` and n_{x}; `h_off` and n_{k}; `y_off`.  "
                            "The output length follows: n_{x} + n_{k} − 1", 15, spcBef=0),
                part("(b)", "The table.  The taps first, so they are in place before the "
                            "samples stream through", 15),
                part("(c)", "The **job number**, and which buffer: the completion then says which "
                            "read finished for which job, and the response to the host can name "
                            "its job.  The adaptor never reads it", 15)]),
            table(ids, 7.35, 1.8, [1.35, 1.0, 1.75, 1.1], ctr(rows), rowh=0.45, sz=14),
            errcard(ids, 7.35, 3.85, 5.2, 1.75, "Common errors",
                    ["Byte addresses: the adaptor takes word offsets.",
                     "Writing n_{x} outputs: a full convolution has n_{x} + n_{k} − 1."]),
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
    # section 2: transactional interfaces
    ("new", s_outline(1)),
    ("old", 19, None), ("old", 20, None), ("old", 21, None), ("old", 22, None),
    ("new", s_why_transactional), ("new", s_concurrent), ("new", s_hls_task),
    ("new", s_task_streams), ("new", s_read_adaptor), ("new", s_kernel_use),
    ("new", s_tags), ("new", s_cmd_practice), ("new", s_cmd_solution),
    # section 3: AXI4 bursts and timing
    ("new", s_outline(2)),
    ("old", 28, None), ("old", 29, None), ("old", 32, None), ("old", 33, None),
    ("old", 34, None),
    ("new", s_burst_timing), ("new", s_job_timing), ("new", s_job_practice),
    ("new", s_job_solution),
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
    kit.fix(s[22], "<a:t>Kernel sends </a:t>",
            "<a:t>Kernel sends a response on the response stream</a:t>")
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
