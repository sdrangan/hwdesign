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
  * the unit is now Kernels and Shared Memory, in five sections
    (plans/unit9_10_memory_pipelining.md): shared memory and interconnects;
    transactions and the data mover; concurrent tasks, on the histogram; AXI4
    under the hood; memory-mapped queues.  All five are built; credit is
    unit 10's.
    Sections 2 and 3 run on one example, a histogram (demos/histogram, branch
    demo/histogram).  Section 2: the example, the protocol steps (the old
    phase slides), the data mover, the read and write transactions as sequence
    diagrams, a toy kernel (summem), and practice pairs on maxmem and on
    drawing two reads.  Section 3: concurrent tasks, hls::task with the
    histogram's top and its colour-mapped diagram, the control, compute and
    response tasks' code, one job task by task, and its timing, measured from
    the demo under XSI with the fenced write adaptor.
    Section 4 is the old AXI4 signal slides, as reference.  The old deck's Vitis m_axi
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
NEW_TITLE = "Kernels and Shared Memory"


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


SECTIONS = ["Shared Memory and Interconnects", "Transactions and the Data Mover",
            "Concurrent Tasks: the Histogram", "AXI4 Under the Hood",
            "Memory-Mapped Queues"]


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


# ---- the two transactions, as sequence diagrams ----------------------------
# Lifelines for the kernel, the data mover and the memory; time runs down.

SEQ_X = {"Kernel": 6.75, "Data mover": 9.25, "Memory": 11.75}
SEQ_FILL = {"Kernel": (TINT, VIOLET), "Data mover": (SLATETINT, SLATE),
            "Memory": (TEALTINT, TEAL)}


def _seq_frame(ids, y0=1.8, y1=5.3):
    out = []
    for name, x in SEQ_X.items():
        fill, line = SEQ_FILL[name]
        out.append(shape(ids, x - 0.75, y0, 1.5, 0.42, fill=fill, line=line, lw=1.25,
                         prst="roundRect", adj=20000,
                         paras=[para(name, sz=12, color=TEXT, b=True, align="ctr")]))
        out.append(arrow(ids, x, y0 + 0.42, x, y1, kit.GRAYLINE, lw=1.0, head=False, dash=True))
    out.append(arrow(ids, 12.75, y0 + 0.6, 12.75, y1, MUTED, lw=1.0))
    out.append(label(ids, 12.55, y1 + 0.02, 0.6, 0.3, "time", sz=10, align="ctr"))
    return out


def _msg(ids, a, b, y, color, text=None, lw=1.75, dash=False, above=True, sz=11):
    xa, xb = SEQ_X[a], SEQ_X[b]
    out = [arrow(ids, xa, y, xb, y, color, lw=lw, dash=dash)]
    if text:
        out.append(label(ids, min(xa, xb), y - 0.3 if above else y + 0.02, abs(xb - xa), 0.3,
                         text, sz=sz, color=TEXT, align="ctr"))
    return out


def _beats(ids, a, b, y, n, color, step=0.11, lw=1.25):
    return [arrow(ids, SEQ_X[a], y + k * step, SEQ_X[b], y + k * step, color, lw=lw)
            for k in range(n)]


TAG_NOTE = ("Both commands also carry a **tag**, `xfer_len` and `xfer_msg`, echoed back unread.  "
            "We need it later: when the response goes to a **different kernel** than the one "
            "that asked.")


def s_read_txn(ids):
    out = [title_ph(ids, "The Read Transaction"),
           col(ids, L, 5.2, [
               "A **transaction**: a command, then its response",
               "**Read command**, `MRCmd` on `rd_cmd`",
               ("-", "`addr`: where to start, a **word offset**, not a byte address"),
               ("-", "`len`: how many words"),
               "**Data response**: `len` words on `rd_data`, in order",
               ("-", "The first after a latency L, then one a cycle"),
               "The data **is** the response: the read is done when the last word arrives",
               "Words, not types: the kernel **packs and unpacks** its values"],
               h=3.9, sz=16, sub=14),
           *_seq_frame(ids),
           *_msg(ids, "Kernel", "Data mover", 2.6, VIOLET, "MRCmd: addr, len"),
           *_msg(ids, "Data mover", "Memory", 2.85, SLATE, "address", lw=1.25),
           *_beats(ids, "Memory", "Data mover", 3.55, 5, TEAL),
           label(ids, SEQ_X["Data mover"], 3.2, SEQ_X["Memory"] - SEQ_X["Data mover"], 0.3,
                 "burst", sz=11, color=TEXT, align="ctr"),
           *_beats(ids, "Data mover", "Kernel", 3.75, 5, TEAL),
           label(ids, SEQ_X["Kernel"], 4.3, SEQ_X["Data mover"] - SEQ_X["Kernel"], 0.3,
                 "len words on rd_data", sz=11, color=TEXT, align="ctr"),
           arrow(ids, 6.5, 2.65, 6.5, 3.75, AMBER, lw=1.25),
           arrow(ids, 6.5, 3.75, 6.5, 2.65, AMBER, lw=1.25),
           label(ids, 6.15, 3.05, 0.3, 0.3, "L", sz=12, color=AMBER, b=True, align="ctr"),
           card(ids, L, 5.65, W, 0.6, [para(TAG_NOTE, sz=13, color=TEXT)], anchor="ctr"),
           sldnum_ph(ids)]
    return out


def s_write_txn(ids):
    out = [title_ph(ids, "The Write Transaction"),
           col(ids, L, 5.2, [
               "**Write command**, `MWCmd` on `wr_cmd`: `addr`, `len`",
               "**Write data**: `len` words on `wr_data`",
               ("-", "The data mover writes each word as it arrives"),
               ("-", "The command may go first: the mover waits for the data"),
               "**Write response**, `MemComplete` on `wr_done`",
               ("-", "Sent once the memory has **acknowledged** the burst"),
               "Only the response means **the data is in memory**.  The last data word does "
               "not"],
               h=3.9, sz=16, sub=14),
           *_seq_frame(ids),
           *_msg(ids, "Kernel", "Data mover", 2.65, VIOLET, "MWCmd: addr, len"),
           *_beats(ids, "Kernel", "Data mover", 2.95, 5, TEAL),
           label(ids, SEQ_X["Kernel"], 3.48, SEQ_X["Data mover"] - SEQ_X["Kernel"], 0.3,
                 "len words on wr_data", sz=11, color=TEXT, align="ctr"),
           *_msg(ids, "Data mover", "Memory", 3.1, SLATE, "address", lw=1.25),
           *_beats(ids, "Data mover", "Memory", 3.25, 5, TEAL),
           *_msg(ids, "Memory", "Data mover", 4.15, SLATE, "acknowledge", lw=1.25, dash=True),
           *_msg(ids, "Data mover", "Kernel", 4.6, SLATE, "MemComplete: len", dash=True),
           card(ids, L, 5.65, W, 0.6, [para(TAG_NOTE, sz=13, color=TEXT)], anchor="ctr"),
           sldnum_ph(ids)]
    return out


# ---- a toy kernel on the data mover: summem --------------------------------
# The smallest kernel that uses a data mover: one command (addr, n) in, one read
# command out, n 32-bit words in (one element per word), their sum out.  Then two
# practice pairs: write a kernel like it (maxmem), and draw a kernel's activity.
# Timing rules, stated on the slides: reading the command takes 2 cycles, sending
# a read command 1; the mover's first word comes L cycles after it takes a command,
# then one a cycle; the kernel adds each word as it arrives; the response is 1 cycle.

SUM_SRC = """
// summem: the sum of n 32-bit words from addr
void summem(hls::stream<word_t>& s_cmd,     // in:  addr, n
            hls::stream<word_t>& rd_cmd,    // to the data mover
            hls::stream<word_t>& rd_data,   // from the data mover
            hls::stream<word_t>& s_resp) {  // out: the sum
    SumCmd c;
    c.read_stream<32>(s_cmd);       // 1. the command

    MRCmd rc;                       // 2. ask for the data
    rc.addr = c.addr;               //    a word offset
    rc.len  = c.n;                  //    one element per word
    rc.xfer_len = 0;                //    no tag (later)
    rc.write_stream<32>(rd_cmd);

    word_t sum = 0;                 // 3. add as it arrives
    for (int i = 0; i < c.n; i++) {
#pragma HLS PIPELINE II=1
        sum += rd_data.read();      //    waits for each word
    }
    s_resp.write(sum);              // 4. the response
}"""

SUM_L, SUM_N = 10, 32
# the job's events, in cycles: command read, read command sent, data, response
SUM_RC = 2
SUM_D0 = SUM_RC + 1 + SUM_L
SUM_D1 = SUM_D0 + SUM_N


def s_sum_diagram(ids):
    ky, kh = 2.35, 2.2                              # kernel and mover row
    kx, kw = 6.0, 1.75
    mx, mw = 8.55, 1.75
    ix, iw = 10.85, 0.45
    rx, rw = 11.6, 0.95
    out = [title_ph(ids, "A Toy Kernel: summem"),
           col(ids, L, 4.95, [
               "A host puts n numbers in memory and asks: **what is their sum?**",
               "The **command**: `addr` and `n`",
               ("-", "32-bit data: **one element per word**"),
               "The kernel sends the data mover **one read command**",
               "It **adds each word as it arrives**",
               "It sends the **sum** on a response stream",
               "The kernel never touches memory: **streams only**"],
               h=4.2, sz=16, sub=14),
           shape(ids, kx, ky, kw, kh, fill=TINT, line=VIOLET, lw=1.25, prst="roundRect",
                 adj=8000, paras=[para("summem", sz=15, color=TEXT, b=True, align="ctr"),
                                  para("kernel", sz=12, color=MUTED, align="ctr")]),
           shape(ids, mx, ky, mw, 1.3, fill=SLATETINT, line=SLATE, lw=1.25, prst="roundRect",
                 adj=10000, paras=[para("Data mover", sz=14, color=TEXT, b=True, align="ctr"),
                                   para("read", sz=12, color=MUTED, align="ctr")]),
           shape(ids, ix, 1.95, iw, 3.4, fill=GRAYFILL, line=SLATE, lw=1.0,
                 paras=[para("", sz=10)]),
           label(ids, ix - 0.55, 5.4, iw + 1.1, 0.3, "Interconnect", sz=12, color=TEXT, b=True,
                 align="ctr"),
           shape(ids, rx, 2.35, rw, 2.2, fill=TEALTINT, line=TEAL, lw=1.25, prst="roundRect",
                 adj=8000, paras=[para("Memory", sz=14, color=TEXT, b=True, align="ctr")]),
           shape(ids, mx, 4.3, mw, 0.75, fill="F7F7F7", line=kit.GRAYLINE, lw=1.0,
                 prst="roundRect", adj=12000,
                 paras=[para("CPU", sz=13, color=TEXT, b=True, align="ctr"),
                        para("another master", sz=11, color=MUTED, align="ctr")])]
    k2, m2 = kx + kw, mx + mw
    out += [
        # the kernel's own streams, to and from the host
        arrow(ids, kx + 0.55, 1.8, kx + 0.55, ky, VIOLET, lw=1.75),
        label(ids, kx + 0.65, 1.85, 1.8, 0.3, "s_cmd: addr, n", sz=11, color=TEXT),
        arrow(ids, kx + 1.2, ky + kh, kx + 1.2, ky + kh + 0.45, SLATE, lw=1.75),
        label(ids, kx + 0.2, ky + kh + 0.48, 1.8, 0.3, "s_resp: sum", sz=11, color=TEXT),
        # kernel <-> data mover
        arrow(ids, k2, 2.65, mx, 2.65, VIOLET, lw=1.5),
        label(ids, k2, 2.35, mx - k2, 0.3, "rd_cmd", sz=11, align="ctr"),
        arrow(ids, mx, 3.25, k2, 3.25, TEAL, lw=1.5),
        label(ids, k2, 2.95, mx - k2, 0.3, "rd_data", sz=11, align="ctr"),
        # data mover and CPU on the interconnect, which reaches the memory
        arrow(ids, m2, 3.0, ix, 3.0, TEAL, lw=2.0, head=False),
        label(ids, m2, 2.7, ix - m2, 0.3, "m_axi", sz=11, align="ctr"),
        arrow(ids, m2, 4.67, ix, 4.67, SLATE, lw=1.5, head=False, dash=True),
        arrow(ids, ix + iw, 3.45, rx, 3.45, TEAL, lw=2.0, head=False),
        band(ids, "The kernel says **what** to read; the data mover does the bus work.  "
                  "The CPU wrote the numbers, through the same interconnect.", y=5.8, h=0.6,
             sz=15),
        sldnum_ph(ids)]
    return out


def s_sum_code(ids):
    return [title_ph(ids, "summem: the Code"),
            lo.code(ids, L, 1.75, 6.9, SUM_SRC, sz=10.5),
            textbox(ids, 7.95, 1.75, 4.6, 4.4, [
                kit.bullet("**Four streams**, no memory port: the data mover owns that", sz=15,
                           spcBef=0),
                kit.bullet("`MRCmd` is the data mover's read command: where and how many "
                           "words.  Its tag fields come later", sz=15),
                kit.bullet("`rd_data.read()` **blocks**: the loop runs as fast as the words "
                           "come", sz=15),
                kit.bullet("`sum +=` is a loop-carried add: one cycle, so **II = 1** (unit 7)",
                           sz=15),
                kit.bullet("The sum wraps at 32 bits.  A real kernel would widen it", sz=15)]),
            sldnum_ph(ids)]


def s_sum_timeline(ids):
    cmd, data, comp = (SLATE, WHITE), (TEAL, WHITE), (VIOLET, WHITE)
    lat, wait = (kit.AMBERTINT, AMBER), ("F4F4F4", MUTED)
    rows = [("summem  kernel", [(0, SUM_RC, "cmd", *cmd), (SUM_RC, SUM_RC + 1, "", *cmd),
                                (SUM_RC + 1, SUM_D0, "waits for data", *wait),
                                (SUM_D0, SUM_D1, "adds each word as it arrives", *comp),
                                (SUM_D1, SUM_D1 + 1, "", *cmd)]),
            ("data mover", [(SUM_RC + 1, SUM_D0, "L", *lat),
                            (SUM_D0, SUM_D1, f"{SUM_N} words", *data)])]
    out = [title_ph(ids, "summem: When Each Task Works"),
           *gantt(ids, rows, SUM_D1 + 3, [0, SUM_RC + 1, SUM_D0, SUM_D1], x=L, y=1.85, w=W,
                  lab_w=1.85, row_h=0.6, gap=0.2)]
    lx = L
    for name, fill in (("command or response", SLATE), ("data", TEAL), ("compute", VIOLET),
                       ("memory latency", kit.AMBERTINT), ("waiting", "F4F4F4")):
        out.append(shape(ids, lx, 3.75, 0.3, 0.22, fill=fill, line=kit.GRAYLINE, lw=0.5))
        out.append(label(ids, lx + 0.38, 3.7, 2.0, 0.3, name, sz=12, color=TEXT))
        lx += 2.35
    out += [textbox(ids, L, 4.2, W, 1.3, [
                kit.bullet(f"The kernel sends its read command at cycle {SUM_RC}, then **waits**: "
                           f"the first word comes L = {SUM_L} cycles later", sz=15, spcBef=0),
                kit.bullet("Then both tasks are busy at once: the mover delivers a word a cycle, "
                           "the kernel adds it the same cycle", sz=15)]),
            band(ids, f"Job ≈ 2 + 1 + L + n + 1 = **{SUM_D1 + 1} cycles**.  The adding is free: "
                      "it hides under the read.", y=5.6, h=0.6, sz=16),
            sldnum_ph(ids)]
    return out


MAX_SRC = """
void maxmem(hls::stream<word_t>& s_cmd, hls::stream<word_t>& rd_cmd,
            hls::stream<word_t>& rd_data, hls::stream<word_t>& s_resp) {
    SumCmd c;                         // addr, n  (n >= 1)
    c.read_stream<32>(s_cmd);
    MRCmd rc;
    rc.addr = c.addr;  rc.len = c.n;  rc.xfer_len = 0;
    rc.write_stream<32>(rd_cmd);

    ap_int<32> best = rd_data.read(); // the first word
    word_t idx = 0;
    for (int i = 1; i < c.n; i++) {
#pragma HLS PIPELINE II=1
        ap_int<32> x = rd_data.read();
        if (x > best) { best = x; idx = i; }
    }
    s_resp.write(best);
    s_resp.write(idx);
}"""


def s_max_practice(ids):
    return [title_ph(ids, "Writing a Kernel: maxmem"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.75, W, 4.4, [
                para("Write `maxmem`, a kernel like `summem`.  Its command is the same `addr` and "
                     "`n` (n ≥ 1).  The data are **signed** 32-bit numbers, one per word.  It "
                     "responds with **two words**: the largest value, then its index (the first, "
                     "if there is a tie).", sz=16, color=TEXT, spcAft=8),
                part("(a)", "Write the kernel: its streams, the read command and the loop", 16),
                part("(b)", "Can the loop run at II = 1?  What is carried from one iteration to "
                            "the next?", 16),
                part("(c)", "A designer stops the loop early once `best` reaches 2³¹ − 1, since "
                            "nothing can beat it.  What goes wrong, and in which job?", 16)]),
            sldnum_ph(ids)]


def s_max_solution(ids):
    return [title_ph(ids, "Writing a Kernel: maxmem"), pill(ids, "SOLUTION"),
            lo.code(ids, L, 1.75, 7.0, MAX_SRC, sz=9.5),
            textbox(ids, 8.05, 1.75, 4.5, 4.5, [
                part("(a)", "On the left.  The first word sets `best`, so no “smallest value” "
                            "constant is needed", 14, spcBef=0),
                part("(b)", "Yes: `best` and `idx` are carried, but a compare and a select fit "
                            "in one cycle, like unit 7's accumulate", 14),
                part("(c)", "The words not read stay in `rd_data`.  **The next job** reads them "
                            "as its own data and answers wrong.  The kernel must read all n "
                            "words, whatever it does with them", 14)]),
            sldnum_ph(ids)]


TWO_SRC = """
SumCmd c;
c.read_stream<32>(s_cmd);
word_t sum = 0;
for (int k = 0; k < 2; k++) {           // two halves
    MRCmd rc;
    rc.addr = c.addr + k * (c.n / 2);
    rc.len  = c.n / 2;  rc.xfer_len = 0;
    rc.write_stream<32>(rd_cmd);
    for (int i = 0; i < c.n / 2; i++) {
#pragma HLS PIPELINE II=1
        sum += rd_data.read();
    }
}
s_resp.write(sum);"""

TWO_L, TWO_N = 10, 64


def _two_times(up_front, outstanding):
    """(rc2 sent, data2 start, response) for the two-half kernel, n = 64, L = 10."""
    h = TWO_N // 2
    d1 = SUM_RC + 1 + TWO_L                     # first half's first word
    e1 = d1 + h
    rc2 = SUM_RC + 1 if up_front else e1        # the cycle the second command is sent
    free = rc2 + 1
    if outstanding:
        d2 = max(free + TWO_L, e1)              # its latency overlaps the first burst
    else:
        d2 = max(free, e1) + TWO_L              # taken only once the first burst ends
    return rc2, d2, d2 + h


def s_two_practice(ids):
    return [title_ph(ids, "Drawing the Activity: Two Reads"), pill(ids, "PRACTICE"),
            lo.code(ids, L, 1.75, 5.6, TWO_SRC, sz=10.5),
            textbox(ids, 6.65, 1.75, 5.9, 4.5, [
                para(f"This kernel sums n words in two halves.  Take n = {TWO_N}, "
                     f"L = {TWO_L}.  Reading the command takes 2 cycles, sending a read command "
                     "1.  The data mover takes one command at a time, when it is free; its first "
                     "word comes L cycles later, then one a cycle.  Each word is added as it "
                     "arrives, and the response takes 1 cycle.", sz=14, color=TEXT, spcAft=6),
                part("(a)", "Draw the activity of the kernel and the data mover for one job.  "
                            "When is the response sent?", 14),
                part("(b)", "Send both read commands **before** the first loop.  Redraw.  "
                            "When now?", 14),
                part("(c)", "What would the data mover have to do for (b) to save the whole "
                            "second L?", 14)]),
            sldnum_ph(ids)]


def s_two_solution(ids):
    cmd, data, comp = (SLATE, WHITE), (TEAL, WHITE), (VIOLET, WHITE)
    lat, wait = (kit.AMBERTINT, AMBER), ("F4F4F4", MUTED)
    h = TWO_N // 2
    d1 = SUM_RC + 1 + TWO_L
    e1 = d1 + h
    rc2a, d2a, ra = _two_times(False, False)
    rc2b, d2b, rb = _two_times(True, False)
    _, d2c, rc_ = _two_times(True, True)
    rows = [("(a) kernel", [(0, SUM_RC, "", *cmd), (SUM_RC, SUM_RC + 1, "", *cmd),
                            (SUM_RC + 1, d1, "", *wait), (d1, e1, "adds", *comp),
                            (rc2a, rc2a + 1, "", *cmd), (rc2a + 1, d2a, "", *wait),
                            (d2a, ra, "adds", *comp), (ra, ra + 1, "", *cmd)]),
            ("(a) mover", [(SUM_RC + 1, d1, "L", *lat), (d1, e1, f"{h}", *data),
                           (rc2a + 1, d2a, "L", *lat), (d2a, ra, f"{h}", *data)]),
            ("(b) mover", [(SUM_RC + 1, d1, "L", *lat), (d1, e1, f"{h}", *data),
                           (e1, d2b, "L", *lat), (d2b, rb, f"{h}", *data)]),
            ("(c) mover", [(SUM_RC + 1, d1, "L", *lat), (d1, e1, f"{h}", *data),
                           (d2c, rc_, f"{h}", *data)])]
    return [title_ph(ids, "Drawing the Activity: Two Reads"), pill(ids, "SOLUTION"),
            *gantt(ids, rows, ra + 3, [0, d1, e1, rc_, ra], x=L, y=1.75, w=W, lab_w=1.4,
                   row_h=0.45, gap=0.12),
            textbox(ids, L, 4.35, W, 1.9, [
                part("(a)", f"The kernel asks for the second half only when the first is in: "
                            f"a second L.  Response at cycle **{ra}**", 14, spcBef=0),
                part("(b)", f"Only **{ra - rb}** cycle sooner, {rb}: the command waits in "
                            f"`rd_cmd`, and the mover still pays L after the first burst", 14),
                part("(c)", f"Take the next command **during** the burst (an outstanding "
                            f"request), so its L overlaps the first half's data: cycle "
                            f"**{rc_}**.  As written, the read adaptor takes one command per firing, so it does not; AXI allows it", 14)]),
            sldnum_ph(ids)]


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
            lo.code(ids, L, 1.75, 7.1, HIST_TOP, sz=9.5),
            label(ids, L, 5.85, 7.1, 0.35, "The histogram's top, demos/histogram/histogram_stream.cpp "
                  "(long lines wrapped).  `t_rd` and `t_wr` are Waveflow's adaptors.", sz=11),
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
ROLE = {**{t: EXT_C for t in ("s_cmd", "s_done", "m_rd", "m_wr")},
        **{t: TASK_C for t in ("t_ctrl", "t_rd", "t_comp", "t_wr", "t_resp", "hist_control",
                               "hist_compute", "hist_response", "mem_r_stream_task",
                               "mem_w_stream_done_task")},
        **{t: STREAM_C for t in ("rd_cmd", "wr_cmd", "rd_data", "wr_data", "wr_done", "job")}}
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


def _task_box(ids, x, y, w, h, name, role_text):
    return shape(ids, x, y, w, h, fill=TINT, line=TASK_C, lw=1.5, prst="roundRect", adj=18000,
                 paras=[para(name, sz=12, color=TASK_C, b=True, align="ctr"),
                        para(role_text, sz=10, color=TEXT, align="ctr")])


def s_top_mapped(ids):
    bw, bh = 1.15, 0.6
    xr, xc, xw = 7.85, 9.625, 11.4                   # read, compute and write columns
    yt, ym = 2.45, 3.7                               # control row, adaptor row
    cr, cc, cw = xr + bw / 2, xc + bw / 2, xw + bw / 2
    out = [title_ph(ids, "Reading the Top: Code and Hardware"),
           colour_code(ids, L, 1.75, 6.95, HIST_TOP, sz=9.5),
           _role_box(ids, xr, 1.75, bw, 0.38, "s_cmd", EXT_C, sz=12),
           _task_box(ids, xr, yt, bw, bh, "t_ctrl", "control"),
           _task_box(ids, xr, ym, bw, bh, "t_rd", "read adaptor"),
           _task_box(ids, xc, ym, bw, bh, "t_comp", "compute"),
           _task_box(ids, xw, ym, bw, bh, "t_wr", "write adaptor"),
           _task_box(ids, xc, 4.75, bw, bh, "t_resp", "response"),
           _role_box(ids, xr + 0.025, 4.85, 1.1, 0.38, "m_rd", EXT_C, sz=12),
           _role_box(ids, 11.95, 4.85, 0.6, 0.38, "m_wr", EXT_C, sz=11),
           _role_box(ids, xc + 0.025, 5.6, 1.1, 0.35, "s_done", EXT_C, sz=12),
           # to and from the outside
           arrow(ids, cr, 2.13, cr, yt, EXT_C, lw=1.75),
           arrow(ids, cr, 4.85, cr, ym + bh, EXT_C, lw=1.75),
           arrow(ids, 12.25, ym + bh, 12.25, 4.85, EXT_C, lw=1.75),
           arrow(ids, cc, 5.35, cc, 5.6, EXT_C, lw=1.75),
           # streams between tasks
           arrow(ids, cr, yt + bh, cr, ym, STREAM_C, lw=2.0),
           arrow(ids, xr + bw, 2.95, cc, ym, STREAM_C, lw=2.0),
           arrow(ids, xr + bw, 2.7, cw, ym, STREAM_C, lw=2.0),
           arrow(ids, xr + bw, ym + bh / 2, xc, ym + bh / 2, STREAM_C, lw=2.0),
           arrow(ids, xc + bw, ym + bh / 2, xw, ym + bh / 2, STREAM_C, lw=2.0),
           arrow(ids, 11.6, ym + bh, xc + bw, 5.05, STREAM_C, lw=2.0),
           label(ids, cr + 0.05, 3.15, 0.75, 0.28, "rd_cmd", sz=11, color=STREAM_C, b=True),
           label(ids, 9.75, 2.95, 0.5, 0.28, "job", sz=11, color=STREAM_C, b=True),
           label(ids, 10.55, 2.6, 0.9, 0.28, "wr_cmd", sz=11, color=STREAM_C, b=True),
           label(ids, xr + bw - 0.06, ym + bh / 2 + 0.03, 0.75, 0.28, "rd_data", sz=10, color=STREAM_C,
                 b=True, align="ctr"),
           label(ids, xc + bw - 0.06, ym + bh / 2 + 0.03, 0.75, 0.28, "wr_data", sz=10, color=STREAM_C,
                 b=True, align="ctr"),
           label(ids, 10.9, 5.15, 0.9, 0.28, "wr_done", sz=11, color=STREAM_C, b=True)]
    lx = L
    for name, role in (("external interface", EXT_C), ("task", TASK_C),
                       ("stream between tasks", STREAM_C)):
        out.append(_role_box(ids, lx, 5.95, 0.32, 0.26, "", role))
        out.append(label(ids, lx + 0.4, 5.92, 2.3, 0.3, name, sz=13, color=role, b=True))
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
                "By convention the adaptors move **words** of the memory's width, "
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
# The code and the measured numbers come from demos/histogram.  draft_note and
# placeholder mark anything still waiting on a demo; none is in use now.

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
               ("-", "32 uniform bins: bin = min(x >> shift, 31)"),
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
    out += [band(ids, "`histogram_stream`: command and response on **streams**.  Section 5: the "
                      "same kernel behind memory-mapped queues, `histogram_mm`.",
                 y=5.45, h=0.7, sz=15),
            sldnum_ph(ids)]
    return out


def s_hist_format(ids):
    cmd = [["Command, 5 words", "Meaning"],
           ["`job_id`", "A number the host chooses; echoed in the response"],
           ["`data_addr`, `n`", "Where the samples are (a **word offset**), and how many"],
           ["`cnt_addr`", "Where to write the 32 counts"],
           ["`shift`", "The bin width: bin = min(x >> shift, 31)"]]
    rsp = [["Response, 2 words", "Meaning"],
           ["`job_id`", "Which command this answers"],
           ["`status`", "OK (0), or N_TOO_LARGE (1) if n > 65,535"]]
    return [title_ph(ids, "Histogram: Command and Response"),
            table(ids, L, 1.8, [2.15, 4.55], cmd, rowh=0.48, sz=14),
            table(ids, 7.75, 1.8, [1.9, 2.9], rsp, rowh=0.48, sz=14),
            textbox(ids, 7.75, 3.4, 4.8, 2.4, [
                kit.bullet("Each is one message on a stream, as in unit 5", sz=14, spcBef=0),
                kit.bullet("32-bit samples, one per word; 16-bit counts, so n is at most "
                           "65,535", sz=14),
                kit.bullet("A refused job reads and writes nothing, but still gets a response",
                           sz=14),
                kit.bullet("The response is sent once the counts are in memory", sz=14)]),
            sldnum_ph(ids)]


HIST_TOP = """
void histogram_stream(hls::stream<word_t>& s_cmd,
                      const word_t* m_rd, word_t* m_wr,
                      hls::stream<word_t>& s_done) {
#pragma HLS INTERFACE axis  port=s_cmd
#pragma HLS INTERFACE m_axi port=m_rd offset=off bundle=gmem0
#pragma HLS stable variable=m_rd
#pragma HLS INTERFACE m_axi port=m_wr offset=off bundle=gmem1
#pragma HLS stable variable=m_wr
#pragma HLS INTERFACE axis  port=s_done
#pragma HLS INTERFACE ap_ctrl_none port=return
    hls_thread_local hls::stream<word_t, 16> rd_cmd, wr_cmd;
    hls_thread_local hls::stream<word_t> rd_data, wr_data, wr_done;
    hls_thread_local hls::stream<HistJob, 2> job;

    hls_thread_local hls::task t_ctrl(hist_control,
                                      s_cmd, rd_cmd, job, wr_cmd);
    hls_thread_local hls::task t_rd(mem_r_stream_task<MEM_DW>,
                                    rd_cmd, m_rd, rd_data);
    hls_thread_local hls::task t_comp(hist_compute, job, rd_data, wr_data);
    hls_thread_local hls::task t_wr(mem_w_stream_done_task<MEM_DW>,
                                    wr_cmd, wr_data, m_wr, wr_done);
    hls_thread_local hls::task t_resp(hist_response, wr_done, s_done);
}"""

HIST_CTRL = """
void hist_control(hls::stream<word_t>& cmd_in,
                  hls::stream<word_t>& rd_cmd,
                  hls::stream<HistJob>& job,
                  hls::stream<word_t>& wr_cmd) {
    HistCmd cmd;
    cmd.read_stream<MEM_DW>(cmd_in);
    const bool ok = (cmd.n <= MAX_N);

    if (ok) {                       // read n samples from data_addr
        MRCmd rc;
        rc.addr = cmd.data_addr;  rc.len = cmd.n;  rc.xfer_len = 0;
        rc.write_stream<MEM_DW>(rd_cmd);
    }
    HistJob j;                      // a refused job reads 0, emits nothing
    j.n = ok ? (int)cmd.n : 0;  j.shift = cmd.shift;  j.emit = ok;
    job.write(j);

    MWCmd wc;                       // write NBINS counts to cnt_addr
    wc.addr = cmd.cnt_addr;  wc.len = ok ? NBINS : 0;  wc.xfer_len = 2;
    wc.xfer_msg.data[XFER_JOB_ID] = cmd.job_id;
    wc.xfer_msg.data[XFER_STATUS] =
        (int)(ok ? HistStatus::OK : HistStatus::N_TOO_LARGE);
    wc.write_stream<MEM_DW>(wr_cmd);
}"""

HIST_COMP = """
void hist_compute(hls::stream<HistJob>& job,
                  hls::stream<word_t>& samples,
                  hls::stream<word_t>& counts_out) {
    count_t counts[NBINS];
#pragma HLS ARRAY_PARTITION variable=counts complete
    const HistJob j = job.read();
CLEAR: for (int b = 0; b < NBINS; b++) {
#pragma HLS UNROLL
        counts[b] = 0;
    }
SAMPLES: for (int i = 0; i < (int)j.n; i++) {
#pragma HLS PIPELINE II=1
        const word_t x = samples.read();
        const word_t bin = x >> j.shift;
        counts[bin < NBINS ? (int)bin : NBINS - 1]++;
    }
    if (j.emit) {
    COUNTS: for (int b = 0; b < NBINS; b++) {
#pragma HLS PIPELINE II=1
            counts_out.write(counts[b]);
        }
    }
}"""

HIST_RESP = """
void hist_response(hls::stream<word_t>& wr_done,
                   hls::stream<word_t>& resp_out) {
    MemComplete done;
    done.read_stream<MEM_DW>(wr_done);
    HistResp resp;
    resp.job_id = done.xfer_msg.data[XFER_JOB_ID];
    resp.status = (HistStatus)(int)done.xfer_msg.data[XFER_STATUS];
    resp.write_stream<MEM_DW>(resp_out);
}"""

HIST_SRC_NOTE = "demos/histogram, task bodies as in the demo; long lines wrapped."


def s_hist_ctrl(ids):
    return [title_ph(ids, "The Control Task"),
            lo.code(ids, L, 1.75, 7.2, HIST_CTRL, sz=10),
            textbox(ids, 8.25, 1.75, 4.3, 4.3, [
                kit.bullet("One command in; out: a command to **each adaptor** and a **job** "
                           "descriptor to compute", sz=14, spcBef=0),
                kit.bullet("Owns **no memory port**: it only writes messages", sz=14),
                kit.bullet("The job id and status ride in the **write command's tag**: the "
                           "write adaptor echoes them to the response task", sz=14),
                kit.bullet("A refused job (n > 65,535) reads and writes nothing, but still gets "
                           "a response", sz=14)]),
            label(ids, L, 6.15, W, 0.3, HIST_SRC_NOTE, sz=11),
            sldnum_ph(ids)]


def s_hist_compute(ids):
    return [title_ph(ids, "The Compute Task"),
            lo.code(ids, L, 1.75, 6.6, HIST_COMP, sz=10),
            textbox(ids, 7.65, 1.75, 4.9, 4.3, [
                kit.bullet("**Streams only**: samples in, counts out.  It never sees an address",
                           sz=14, spcBef=0),
                kit.bullet("Takes each sample **as it arrives** from the read adaptor", sz=14),
                kit.bullet("`counts[bin]++` is a read-modify-write: a repeat of the last bin "
                           "depends on it (unit 7)", sz=14),
                kit.bullet("The 32 counts are **registers** (`ARRAY_PARTITION complete`): "
                           "read, add and write fit in a cycle, **II = 1**", sz=14),
                kit.bullet("In a block RAM, Vitis still reports II = 1 but warns the chain "
                           "misses the 10 ns clock (HLS 200-887)", sz=14)]),
            label(ids, L, 6.15, W, 0.3, HIST_SRC_NOTE, sz=11),
            sldnum_ph(ids)]


def s_hist_resp(ids):
    return [title_ph(ids, "The Response Task"),
            lo.code(ids, L, 1.75, 7.2, HIST_RESP, sz=11),
            textbox(ids, 8.25, 1.75, 4.3, 3.0, [
                kit.bullet("Waits for the **write adaptor's completion**", sz=15, spcBef=0),
                kit.bullet("Its tag carries the job id and status the control task put "
                           "there", sz=15),
                kit.bullet("So the response is sent once the counts are **in memory**: after "
                           "the last burst's write response (B)", sz=15)]),
            card(ids, L, 4.4, 7.2, 1.3, [
                para("**Why a separate task?**", sz=15, color=TEXT, spcAft=4),
                para("Only the write adaptor knows when the counts have been written.  The "
                     "compute task's last count leaves before it lands.", sz=14, color=TEXT)]),
            label(ids, 8.25, 4.45, 4.3, 1.3,
                  "Measured: the response leaves **20 cycles** after the last B.  4 for the "
                  "adaptor to see it, 12 for the 10-word completion, 4 for this task.",
                  sz=13, color=TEXT),
            sldnum_ph(ids)]


# Measured, demos/histogram (histogram_stream under XSI, the fenced write
# adaptor), n = 256, each job alone, cycles from the command's last word:
# MRCmd written 1-13, read request 22, first sample 23 (L), compute from 28,
# last sample 293, last count 335, first write request 325, last B 360,
# response 380 (4 fence + 12 MemComplete + 4 response task).
HM = dict(L=23, n=256, last=293, comp0=28, cnt0=303, cnt1=335, aw=325, b=360, resp=380)
HIST_MEASURED = ("Measured: demos/histogram, histogram_stream under XSI, 100 MHz; cycles from "
                 "the command's last word.  The testbench memory answers in a cycle.")


def s_job_tasks(ids):
    """One job, task by task: the measured cycles of HM."""
    m = HM
    cmd, data, comp = (SLATE, WHITE), (TEAL, WHITE), (VIOLET, WHITE)
    lat, wait = (kit.AMBERTINT, AMBER), ("F4F4F4", MUTED)
    rows = [
        ("t_ctrl  control", [(0, 13, "", *cmd), (13, 24, "", *cmd)]),
        ("t_rd  read", [(0, m["L"], "L", *lat),
                        (m["L"], m["last"], f"{m['n']} samples, 16 bursts of 16", *data)]),
        ("t_comp  compute", [(13, m["comp0"], "", *wait),
                             (m["comp0"], m["last"] + 5, "bins each sample as it arrives", *comp),
                             (m["cnt0"], m["cnt1"], "", *data)]),
        ("t_wr  write", [(24, m["cnt0"], "has its command: waits for the counts", *wait),
                         (m["cnt0"], m["aw"], "", *data), (m["aw"], m["b"], "", *lat)]),
        ("t_resp  response", [(0, m["b"] + 4, "waits for the write's completion", *wait),
                              (m["b"] + 4, m["resp"], "", *cmd)]),
    ]
    out = [title_ph(ids, "One Job, Task by Task"),
           *gantt(ids, rows, m["resp"] + 6, [0, m["L"], m["last"], m["cnt1"], m["resp"]],
                  x=L, y=1.75, w=W, lab_w=1.85, row_h=0.5, gap=0.13)]
    lx = L
    for name, fill in (("command or response", SLATE), ("samples or counts", TEAL),
                       ("compute", VIOLET), ("latency or burst", kit.AMBERTINT),
                       ("waiting for input", "F4F4F4")):
        out.append(shape(ids, lx, 5.22, 0.3, 0.22, fill=fill, line=kit.GRAYLINE, lw=0.5))
        out.append(label(ids, lx + 0.38, 5.17, 2.0, 0.3, name, sz=12, color=TEXT))
        lx += 2.35
    out += [band(ids, "Each task works only when its input arrives.  Compute runs **under the "
                      "read**; the writer starts its first burst before the last count.", y=5.6,
                 h=0.55, sz=15),
            label(ids, L, 6.2, W, 0.32, HIST_MEASURED + "  n = 256.", sz=11),
            sldnum_ph(ids)]
    return out


def s_hist_timing(ids):
    m = HM
    lat = (GRAYFILL, TEXT)
    rows = [("Read samples", [(0, m["L"], "L", *lat),
                              (m["L"], m["last"], f"{m['n']} samples", TEAL, WHITE)]),
            ("Compute", [(m["comp0"], m["last"] + 5, "as the samples arrive", VIOLET, WHITE),
                         (m["cnt0"], m["cnt1"], "", TEAL, WHITE)]),
            ("Write counts", [(m["aw"], m["b"], "", AMBER, WHITE)]),
            ("Response", [(m["b"], m["resp"], "", SLATE, WHITE)])]
    return [title_ph(ids, "Timing a Histogram Job"),
            col(ids, L, 4.9, [
                "The read: **L = 23**, then a sample a cycle (plus one per 16-word burst)",
                ("-", "Most of L is the **command**: the 11-word MRCmd.  To DDR, add tens more"),
                "Compute takes each sample **as it arrives**: it hides under the read",
                "After the last sample: **42** cycles to finish the counts, **25** to write "
                "them, **20** to respond"],
                h=3.4, sz=15, sub=13),
            *gantt(ids, rows, m["resp"] + 4, [0, m["L"], m["last"], m["resp"]]),
            label(ids, 5.9, 4.6, 6.65, 0.5,
                  "n = 256: **380** cycles.  n = 700: 852.  n = 1024: 1196.", sz=13, color=TEXT),
            band(ids, "Job ≈ L + n·17/16 + 87.  Only the read grows with n; the compute costs "
                      "nothing, hidden under it.", y=5.3, h=0.6, sz=16),
            label(ids, L, 6.2, W, 0.32, HIST_MEASURED, sz=11),
            sldnum_ph(ids)]


def s_hist_overlap(ids):
    return [title_ph(ids, "Back to Back, Jobs Overlap"),
            lo.pic(ids, "hist_timeline_stream", L, 1.65, 7.0, 4.2, align="l"),
            textbox(ids, 8.0, 1.75, 4.55, 3.9, [
                kit.bullet("Five jobs, every command sent at once.  Top: the run; bottom: job 1",
                           sz=14, spcBef=0),
                kit.bullet("Job 2's read starts at **324**, while job 1 is still finishing its "
                           "counts (341), writing them (366) and responding (386)", sz=14),
                kit.bullet("The **read port** is the bottleneck: idle only 25 cycles between "
                           "jobs, while the mover takes its next command", sz=14),
                kit.bullet("All five: **3,379** cycles, against 3,667 one at a time", sz=14)]),
            band(ids, "Free-running tasks overlap jobs **with no extra code**.  Unit 10 makes "
                      "that overlap the design goal.", y=5.95, h=0.55, sz=15),
            sldnum_ph(ids)]


# ========================================================== section 5 ======
# Memory-mapped queues: how the host reaches a free-running kernel.  From
# Waveflow's docs/guide/interface/axi_mm/slave.md and slave_views.md.  Register
# banks and BRAM windows exist but are left to those docs; credit is unit 10's.

def _lanes(ids, lanes, y0=1.8, y1=5.25, w=1.35):
    """Sequence-diagram lifelines: lanes = [(name, x, fill, line)]."""
    out = []
    for name, x, fill, line in lanes:
        out.append(shape(ids, x - w / 2, y0, w, 0.42, fill=fill, line=line, lw=1.25,
                         prst="roundRect", adj=20000,
                         paras=[para(name, sz=12, color=TEXT, b=True, align="ctr")]))
        out.append(arrow(ids, x, y0 + 0.42, x, y1, kit.GRAYLINE, lw=1.0, head=False, dash=True))
    return out


def _say(ids, x1, x2, y, color, text, dash=False, lw=1.75, sz=11):
    return [arrow(ids, x1, y, x2, y, color, lw=lw, dash=dash),
            label(ids, min(x1, x2), y - 0.29, abs(x2 - x1), 0.28, text, sz=sz, color=TEXT,
                  align="ctr")]


def s_mm_gap(ids):
    out = [title_ph(ids, "Who Sends the Command?"),
           col(ids, L, 5.4, [
               "So far the **testbench** drove `s_cmd` and `s_done`: AXI-Streams, wired "
               "straight to the kernel",
               "In an SoC the job comes from the **CPU**, a master on the interconnect",
               ("-", "It can only issue reads and writes to addresses"),
               "So the kernel needs a **slave** port, at an address the CPU can reach",
               "Its data path does not change: the data movers are still masters"],
               h=3.8, sz=16, sub=14)]
    # so far: testbench wired to the kernel
    out += [kit.heading(ids, 6.6, 1.75, 2.6, "SO FAR"),
            shape(ids, 6.6, 2.1, 1.4, 0.7, fill=SLATETINT, line=SLATE, lw=1.25, prst="roundRect",
                  adj=15000, paras=[para("Testbench", sz=13, color=TEXT, b=True, align="ctr")]),
            shape(ids, 8.75, 2.1, 1.4, 0.7, fill=TINT, line=VIOLET, lw=1.25, prst="roundRect",
                  adj=15000, paras=[para("Kernel", sz=13, color=TEXT, b=True, align="ctr")]),
            arrow(ids, 8.0, 2.3, 8.75, 2.3, SLATE, lw=1.5),
            arrow(ids, 8.75, 2.6, 8.0, 2.6, SLATE, lw=1.5),
            label(ids, 10.25, 2.25, 2.3, 0.4, "s_cmd, s_done: streams", sz=12, color=SLATE),
            # in an SoC
            kit.heading(ids, 6.6, 3.15, 2.6, "IN AN SOC"),
            shape(ids, 6.6, 3.5, 1.4, 0.7, fill=SLATETINT, line=SLATE, lw=1.25, prst="roundRect",
                  adj=15000, paras=[para("CPU", sz=13, color=TEXT, b=True, align="ctr")]),
            shape(ids, 8.35, 3.35, 0.4, 1.9, fill=GRAYFILL, line=SLATE, lw=1.0),
            label(ids, 7.85, 5.27, 1.4, 0.3, "interconnect", sz=11, align="ctr"),
            shape(ids, 9.1, 3.5, 1.4, 0.7, fill=TINT, line=VIOLET, lw=1.25, prst="roundRect",
                  adj=15000, paras=[para("Kernel", sz=13, color=TEXT, b=True, align="ctr")]),
            shape(ids, 9.1, 4.5, 1.4, 0.6, fill=TEALTINT, line=TEAL, lw=1.25, prst="roundRect",
                  adj=15000, paras=[para("DDR", sz=13, color=TEXT, b=True, align="ctr")]),
            arrow(ids, 8.0, 3.85, 8.35, 3.85, SLATE, lw=1.75),
            arrow(ids, 8.75, 3.85, 9.1, 3.85, AMBER, lw=1.75, dash=True),
            label(ids, 10.6, 3.65, 1.95, 0.4, "^^?^^  a slave port", sz=13, color=TEXT),
            arrow(ids, 8.75, 4.8, 9.1, 4.8, TEAL, lw=1.75, head=False),
            band(ids, "The CPU speaks **reads and writes**; the kernel speaks **streams**.  "
                      "Something has to translate.", y=5.65, h=0.6, sz=16),
            sldnum_ph(ids)]
    return out


def s_slave_adaptor(ids):
    ax, aw = 8.75, 2.0
    out = [title_ph(ids, "The Slave Adaptor"),
           col(ids, L, 5.6, [
               "Why not `s_axilite`, as in unit 4?",
               ("-", "A free-running kernel has no `ap_start`: it cannot **see** a write happen"),
               ("-", "And Vitis cannot generate a full AXI4 slave"),
               "Instead: a **slave adaptor**, hand-written RTL in the top",
               ("-", "Bus transactions in, **stream messages** out"),
               "**Kernels stay stream-only**: everything a kernel sees is a stream message",
               "Each **view** is a 4 KB window of addresses"],
               h=4.0, sz=16, sub=14),
           shape(ids, 6.65, 2.4, 1.3, 0.7, fill=SLATETINT, line=SLATE, lw=1.25, prst="roundRect",
                 adj=15000, paras=[para("CPU", sz=13, color=TEXT, b=True, align="ctr")]),
           shape(ids, ax, 1.95, aw, 2.6, fill="F7F7F7", line=SLATE, lw=1.25, prst="roundRect",
                 adj=6000, anchor="t", inset=0.1,
                 paras=[para("Slave adaptor", sz=13, color=TEXT, b=True, align="ctr")]),
           shape(ids, ax + 0.2, 2.5, aw - 0.4, 0.55, fill=SLATETINT, line=SLATE, lw=1.0,
                 prst="roundRect", adj=20000,
                 paras=[para("queue in", sz=12, color=SLATE, b=True, align="ctr")]),
           shape(ids, ax + 0.2, 3.25, aw - 0.4, 0.55, fill=SLATETINT, line=SLATE, lw=1.0,
                 prst="roundRect", adj=20000,
                 paras=[para("queue out", sz=12, color=SLATE, b=True, align="ctr")]),
           label(ids, ax + 0.1, 3.95, aw - 0.2, 0.5, "(register bank, BRAM window)", sz=10,
                 align="ctr"),
           shape(ids, 11.5, 2.3, 1.05, 1.6, fill=TINT, line=VIOLET, lw=1.25, prst="roundRect",
                 adj=10000, paras=[para("Kernel", sz=13, color=TEXT, b=True, align="ctr")]),
           arrow(ids, 7.95, 2.75, ax, 2.75, SLATE, lw=1.75),
           label(ids, 7.9, 2.42, 0.9, 0.3, "writes", sz=11, align="ctr"),
           arrow(ids, ax, 3.5, 7.95, 3.5, SLATE, lw=1.75),
           label(ids, 7.9, 3.53, 0.9, 0.3, "reads", sz=11, align="ctr"),
           arrow(ids, ax + aw - 0.2, 2.78, 11.5, 2.78, TEAL, lw=1.75),
           arrow(ids, 11.5, 3.52, ax + aw - 0.2, 3.52, TEAL, lw=1.75),
           label(ids, 10.55, 2.45, 1.0, 0.3, "stream", sz=11, color=TEAL, align="ctr"),
           label(ids, 10.55, 3.55, 1.0, 0.3, "stream", sz=11, color=TEAL, align="ctr"),
           card(ids, L, 5.35, W, 0.85, [para(
               "Waveflow also provides a **register bank** (configuration and status) and a "
               "**BRAM window** (memory the host reads and writes by address).  We use only the "
               "queues; the others are in Waveflow's docs: Interfaces › AXI-MM › Slave side.",
               sz=14, color=TEXT)], anchor="ctr"),
           sldnum_ph(ids)]
    return out


def s_queues(ids):
    rows = [["View", "The host (bus side)", "The kernel"],
            ["queue in", "writes a **packet** of words: one burst", "reads a stream; TLAST ends "
                                                                    "each packet"],
            ["queue out", "reads **exactly n** words", "writes a stream"]]
    return [title_ph(ids, "Queue In and Queue Out"),
            table(ids, L, 1.8, [1.7, 4.9, 5.2], rows, rowh=[0.42, 0.55, 0.55], sz=14),
            textbox(ids, L, 3.55, 6.0, 2.5, [
                kit.bullet("A packet goes in **whole**, once there is room for all of it", sz=15,
                           spcBef=0),
                kit.bullet("A completed write means the queue **took** the words, not that the "
                           "kernel has read them", sz=15),
                kit.bullet("Queue out has no packet boundaries on the bus: the host says how "
                           "many words it wants", sz=15)]),
            card(ids, 7.0, 3.55, 5.55, 2.35, [
                para("**Interrupts, not polling**", sz=15, color=TEXT, spcAft=4),
                kit.bullet("Each queue raises a line when **room** (queue in) or **words** "
                           "(queue out) reach a threshold the host sets", sz=14, spcBef=0),
                kit.bullet("The host sleeps on it, then writes or reads: it never reads a count "
                           "and never stalls the bus", sz=14),
                kit.bullet("The threshold is set by a write to the window's upper half", sz=14)]),
            sldnum_ph(ids)]


def s_hist_mm(ids):
    """histogram_mm.v, demos/histogram: the slave adaptor around the stream kernel."""
    def box(x, y, w, h, lines, fill, line):
        paras = [para(lines[0], sz=12, color=TEXT, b=True, align="ctr")]
        paras += [para(t, sz=10, color=MUTED, align="ctr") for t in lines[1:]]
        return shape(ids, x, y, w, h, fill=fill, line=line, lw=1.25, prst="roundRect",
                     adj=15000, paras=paras)

    out = [title_ph(ids, "histogram_mm: Only the Top Changes"),
           col(ids, L, 5.15, [
               "`histogram_mm.v`: an RTL top around the **unchanged** stream kernel",
               "`axi_slave_front`: the only part that speaks AXI, one transaction at a time",
               "A **decoder**: address bit 12 picks one of two 4 KB views",
               "`qcmd`, a queue in, feeds `s_cmd`; `qresp`, a queue out, takes `s_done`",
               "The kernel's two `m_axi` ports go straight out to memory",
               "Assembled by hand from Waveflow's modules, used as they are"],
               h=4.0, sz=15, sub=13),
           # the slave adaptor's outline
           shape(ids, 7.85, 1.75, 4.75, 2.15, fill="FAFAFA", line=SLATE, lw=1.0, dash=True),
           label(ids, 7.95, 3.5, 1.45, 0.3, "slave adaptor", sz=11, color=SLATE, b=True),
           box(6.3, 1.95, 1.3, 0.65, ["Host", "the CPU"], SLATETINT, SLATE),
           box(7.95, 1.95, 1.95, 0.65, ["axi_slave_front", "AXI4 in"], WHITE, SLATE),
           box(10.2, 1.95, 2.3, 0.65, ["decoder", "address bit 12"], WHITE, SLATE),
           box(9.45, 3.0, 1.45, 0.75, ["qcmd", "queue in, 0x0000"], SLATETINT, SLATE),
           box(11.05, 3.0, 1.45, 0.75, ["qresp", "queue out, 0x1000"], SLATETINT, SLATE),
           box(9.45, 4.2, 3.05, 0.75, ["histogram_stream", "the five tasks, unchanged"],
               TINT, VIOLET),
           box(6.3, 4.2, 1.3, 0.75, ["DDR", "samples, counts"], TEALTINT, TEAL),
           arrow(ids, 7.6, 2.27, 7.95, 2.27, SLATE, lw=1.75),
           arrow(ids, 9.9, 2.27, 10.2, 2.27, SLATE, lw=1.5),
           arrow(ids, 10.75, 2.6, 10.17, 3.0, SLATE, lw=1.25),
           arrow(ids, 11.95, 2.6, 11.77, 3.0, SLATE, lw=1.25),
           arrow(ids, 10.17, 3.75, 10.17, 4.2, TEAL, lw=1.75),
           label(ids, 9.35, 3.93, 0.75, 0.26, "s_cmd", sz=10, color=TEAL, b=True, align="r"),
           arrow(ids, 11.77, 4.2, 11.77, 3.75, TEAL, lw=1.75),
           label(ids, 11.85, 3.93, 0.8, 0.26, "s_done", sz=10, color=TEAL, b=True),
           arrow(ids, 9.45, 4.58, 7.6, 4.58, TEAL, lw=1.75),
           label(ids, 7.65, 4.25, 1.8, 0.28, "m_axi: gmem0, gmem1", sz=10, color=TEAL,
                 align="ctr"),
           arrow(ids, 9.45, 3.12, 6.95, 2.6, AMBER, lw=1.25, dash=True),
           label(ids, 6.3, 3.0, 1.6, 0.3, "irq_cmd, irq_resp", sz=10, color=AMBER),
           band(ids, "Same kernel, same tasks: only who sends the command changed.", y=5.45,
                h=0.55, sz=16),
           label(ids, L, 6.15, W, 0.32, "demos/histogram/histogram_mm.v.  Waveflow generates "
                 "this adaptor for its own kernels, not yet for an HLS kernel.", sz=11),
           sldnum_ph(ids)]
    return out


MM_HOST = """
void writer() {               // every command, as soon as there is room
    for (const auto& cmd : scenario_bursts())
        qcmd.write(cmd);      // on irq_cmd: one write, [len | 5 words]
}
void reader() {               // one response per job, in any order
    for (long k = 0; k < njobs; ++k)
        resp = qresp.get(2);  // sleeps on irq_resp, pops 2 words
}
"""


def s_mm_host(ids):
    rows = [["Address", "View", "The host", "The kernel"],
            ["0x0000", "qcmd", "writes a packet [len, 5 words]; a read returns the free room",
             "reads `HistCmd` on `s_cmd`"],
            ["0x0800", "qcmd", "writes the room threshold for `irq_cmd`", ""],
            ["0x1000", "qresp", "each read pops one response word", "writes `HistResp` on "
                                                                       "`s_done`"],
            ["0x1800", "qresp", "reads the words waiting; writes the threshold for `irq_resp`",
             ""]]
    return [title_ph(ids, "The Address Map and the Host"),
            table(ids, L, 1.75, [1.15, 0.95, 6.3, 3.4], rows, rowh=0.38, sz=13),
            lo.code(ids, L, 4.0, 7.0, MM_HOST, sz=11),
            textbox(ids, 8.0, 4.0, 4.55, 2.1, [
                kit.bullet("Two threads that **block**, on Waveflow's `xsi_sw.h`", sz=14,
                           spcBef=0),
                kit.bullet("Measured: a command costs the host **7 cycles** (one 6-beat "
                           "write); a response arrives **6** after the kernel sends it", sz=14),
                kit.bullet("Nothing is polled: each threshold is written once", sz=14)]),
            label(ids, L, 6.25, W, 0.3, "demos/histogram/tb_xsi_histogram_mm.cpp, simplified.  "
                  "The upper half of each 4 KB view is its control.", sz=11),
            sldnum_ph(ids)]


def s_host_job(ids):
    xs = {"Host": 6.55, "Queues": 8.45, "Kernel": 10.35, "DDR": 12.0}
    out = [title_ph(ids, "A Job, from the Host's Side"),
           col(ids, L, 5.0, [
               "The host writes the samples to DDR",
               "It **pushes** the 5-word command into queue in: one write",
               "It **sleeps** on queue out's interrupt",
               "The kernel runs the job, as in section 3",
               "The kernel's response lands in queue out: the interrupt fires",
               "The host **reads** the 2 words, then the counts from DDR"],
               h=4.2, sz=15, sub=13),
           *_lanes(ids, [("Host", xs["Host"], SLATETINT, SLATE),
                         ("Queues", xs["Queues"], "F7F7F7", SLATE),
                         ("Kernel", xs["Kernel"], TINT, VIOLET),
                         ("DDR", xs["DDR"], TEALTINT, TEAL)], w=1.25),
           *_say(ids, xs["Host"], xs["DDR"], 2.65, TEAL, "samples"),
           *_say(ids, xs["Host"], xs["Queues"], 3.05, SLATE, "command"),
           *_say(ids, xs["Queues"], xs["Kernel"], 3.35, TEAL, "s_cmd", lw=1.25),
           *_say(ids, xs["Kernel"], xs["DDR"], 3.75, TEAL, "read, write", lw=1.25),
           *_say(ids, xs["Kernel"], xs["Queues"], 4.15, TEAL, "s_done", lw=1.25),
           *_say(ids, xs["Queues"], xs["Host"], 4.5, AMBER, "interrupt", dash=True, lw=1.25),
           *_say(ids, xs["Queues"], xs["Host"], 4.85, SLATE, "read 2 words"),
           *_say(ids, xs["DDR"], xs["Host"], 5.2, TEAL, "counts"),
           band(ids, "Two bus accesses per job reach the kernel: one write in, one read out.  "
                     "Measured: 7 cycles to send, 6 to collect.", y=5.6, h=0.55, sz=15),
           sldnum_ph(ids)]
    return out


def s_jobs_queued(ids):
    out = [title_ph(ids, "Several Jobs in Flight"),
           col(ids, L, 6.0, [
               "The host need not wait for one job before sending the next",
               ("-", "Queue in holds as many **whole commands** as fit"),
               "Measured, five jobs: every command is in by cycle **53**",
               ("-", "The kernel takes them at 17, 47, 77, 405 and 1517: jobs 4 and 5 wait "
                     "**in the queue**"),
               "Each response carries its `job_id`, and the host matches it to its job",
               ("-", "The tag idea again, end to end"),
               "The jobs overlap inside the kernel, as in section 3"],
               h=4.0, sz=16, sub=14)]
    # a queue with stacked commands
    qx, qy, cw, ch = 8.2, 1.9, 2.4, 0.42
    out.append(kit.heading(ids, qx, 1.6, 3.0, "QUEUE IN, FILLING"))
    for k, (txt, fill, col_) in enumerate((("job 7  (5 words)", TINT, VIOLET),
                                           ("job 6  (5 words)", TINT, VIOLET),
                                           ("job 5  (5 words)", TINT, VIOLET),
                                           ("job 4: being read", VIOLET, WHITE))):
        out.append(shape(ids, qx, qy + k * (ch + 0.06), cw, ch, fill=fill, line=VIOLET, lw=1.0,
                         paras=[para(txt, sz=12, color=col_, b=True, align="ctr")]))
    out += [arrow(ids, qx + cw / 2, qy + 4 * (ch + 0.06) - 0.02, qx + cw / 2, 4.35, VIOLET,
                  lw=1.75),
            label(ids, qx, 4.38, cw, 0.3, "to t_ctrl", sz=12, color=TEXT, align="ctr"),
            arrow(ids, 11.75, 2.11, qx + cw + 0.08, 2.11, SLATE, lw=1.75),
            label(ids, 10.75, 2.2, 1.8, 0.3, "the host pushes", sz=12, color=TEXT,
                  align="ctr"),
            band(ids, "The queue's depth is how many jobs the host can hand over without "
                      "waiting.", y=5.5, h=0.6, sz=16),
            sldnum_ph(ids)]
    return out


def s_bus_backpressure(ids):
    xs = {"Host": 6.8, "Adaptor": 9.2, "Kernel": 11.6}
    out = [title_ph(ids, "Back-Pressure Does Not Cross a Bus"),
           col(ids, L, 5.4, [
               "On a stream, a full receiver holds TREADY low: only the sender waits",
               "Over a bus, a write into a full queue holds **WREADY** low",
               ("-", "The adaptor serves one transaction at a time: **every** access to it waits"),
               ("-", "Including the host's read of queue out, which would let the kernel go on"),
               "Not a slowdown: a **deadlock**",
               "Rule: **never write without knowing there is room**.  The host waits on the room "
               "interrupt"],
               h=4.1, sz=15, sub=13),
           *_lanes(ids, [("Host", xs["Host"], SLATETINT, SLATE),
                         ("Adaptor", xs["Adaptor"], "F7F7F7", SLATE),
                         ("Kernel", xs["Kernel"], TINT, VIOLET)], y1=5.0, w=1.3),
           *_say(ids, xs["Host"], xs["Adaptor"], 2.7, SLATE, "write command"),
           label(ids, xs["Adaptor"] - 0.1, 2.85, 2.6, 0.3, "^^queue in full: WREADY low^^",
                 sz=11),
           *_say(ids, xs["Kernel"], xs["Adaptor"], 3.6, TEAL, "response: queue out full",
                 lw=1.25),
           label(ids, xs["Adaptor"] + 0.05, 3.7, 2.4, 0.3, "kernel blocks", sz=11),
           *_say(ids, xs["Host"], xs["Adaptor"], 4.4, SLATE, "read responses", dash=True),
           label(ids, xs["Host"] - 0.3, 4.48, 2.7, 0.3, "^^waits behind the write^^", sz=11,
                 align="ctr"),
           card(ids, L, 5.35, W, 0.85, fill=kit.AMBERTINT, paras=[para(
               "A **kernel** writing another kernel's queue over the bus needs the general form "
               "of the rule: **credit**.  Unit 10, with pipelines of kernels.", sz=14,
               color=TEXT)], anchor="ctr"),
           sldnum_ph(ids)]
    return out


def s_queue_practice(ids):
    return [title_ph(ids, "Queuing Jobs"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, W, 4.4, [
                para("`histogram_mm`'s queue in holds 512 words and its queue out 128.  A "
                     "command is 5 words, a response 2; a packet goes in only whole.  The "
                     "interconnect is a crossbar.", sz=16, color=TEXT, spcAft=8),
                part("(a)", "How many commands can be waiting in queue in?", 16),
                part("(b)", "The host pushes 300 commands as fast as it can, never checking an "
                            "interrupt, and only then reads the 300 responses.  What happens?  "
                            "At which command?", 16),
                part("(c)", "Change the host so it cannot happen.  Name two ways.", 16)]),
            sldnum_ph(ids)]


def s_queue_solution(ids):
    return [title_ph(ids, "Queuing Jobs"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 7.0, 4.4, [
                part("(a)", "512 / 5: !!102 commands!! (510 words)", 15, spcBef=0),
                part("(b)", "Queue out fills after **64** responses, and the kernel blocks on "
                            "the 65th.  It has taken about 65 commands (a few more if `t_ctrl` "
                            "runs ahead); 102 more wait in queue in.  The host's write of command "
                            "!!≈ 168!! stalls the bus, so it never reaches its reads: a "
                            "**deadlock**", 15),
                part("(c)", "Wait on queue in's **room** interrupt before each push; and read "
                            "responses as they come (or keep at most 64 jobs outstanding, what "
                            "queue out can hold)", 15)]),
            errcard(ids, 8.05, 1.8, 4.5, 2.7, "Common errors",
                    ["Thinking the stall only slows the host: the host is the one that would "
                     "drain queue out.",
                     "Forgetting queue out: queue in alone would only make the host wait."]),
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
    # section 2: transactions and the data mover
    ("new", s_outline(1)), ("new", s_hist_example),
    ("old", 20, None), ("old", 21, None), ("old", 22, None), ("new", s_hist_format),
    ("new", s_why_transactional), ("new", s_read_txn), ("new", s_write_txn),
    ("new", s_sum_diagram), ("new", s_sum_code), ("new", s_sum_timeline),
    ("new", s_max_practice), ("new", s_max_solution),
    ("new", s_two_practice), ("new", s_two_solution),
    # section 3: concurrent tasks, on the histogram
    ("new", s_outline(2)),
    ("new", s_concurrent), ("new", s_hls_task),
    ("new", s_top_mapped), ("new", s_task_streams), ("new", s_tags),
    ("new", s_hist_ctrl), ("new", s_hist_compute), ("new", s_hist_resp),
    ("new", s_job_tasks),
    ("new", s_burst_timing), ("new", s_hist_timing), ("new", s_hist_overlap),
    # section 4: AXI4 under the hood
    ("new", s_outline(3)),
    ("old", 28, None), ("old", 29, None), ("old", 32, None), ("old", 33, None),
    ("old", 34, None),
    # section 5: memory-mapped queues
    ("new", s_outline(4)), ("new", s_mm_gap), ("new", s_slave_adaptor), ("new", s_queues),
    ("new", s_hist_mm), ("new", s_mm_host), ("new", s_host_job), ("new", s_jobs_queued),
    ("new", s_bus_backpressure), ("new", s_queue_practice), ("new", s_queue_solution),
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
    kit.fix(s[20], "Input address:  Where data resides", "data_addr, n:  where the samples are")
    kit.fix(s[20], "Output address:  Where output should reside",
            "cnt_addr:  where the counts should go")
    kit.fix(s[20], "Command info:  What to do with data", "shift:  the bin width")
    kit.fix(s[20], "<a:t>Input</a:t>", "<a:t>Samples</a:t>")
    kit.fix(s[20], "<a:t>data</a:t>", "<a:t></a:t>")
    kit.fix(s[21], "<a:t>input data </a:t>", "<a:t>the samples </a:t>")
    kit.fix(s[21], "Uses input address sent in command", "n words at data_addr, from the command")
    kit.fix(s[21], "Kernel processes input data", "Kernel bins each one:  counts[bin]++")
    kit.fix(s[21], "<a:t>Input</a:t>", "<a:t>Samples</a:t>")
    kit.fix(s[21], "<a:t>data</a:t>", "<a:t></a:t>")
    kit.fix(s[21], "<a:t>Computes </a:t>", "<a:t>Bins the </a:t>")
    kit.fix(s[21], "<a:t>results</a:t>", "<a:t>samples</a:t>")
    kit.fix(s[22], "<a:t>output data </a:t>", "<a:t>the counts </a:t>")
    kit.fix(s[22], "Uses output address sent in command", "At cnt_addr, from the command")
    kit.fix(s[22], "<a:t>Kernel sends </a:t>",
            "<a:t>Kernel sends the response (job_id, status) on s_done</a:t>")
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
