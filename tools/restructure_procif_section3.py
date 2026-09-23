"""Restructure Section 3 of unit 4: replace the demo walkthrough with four slides.

Section 3 used to walk through the Vitis demo slide by slide -- source code,
pragmas, the Flow panel, synthesis output, the reports, RTL simulation.  All of
that now lives in the course docs (``docs/demos/procif/``), where the commands
are executable and the figures are generated from a real co-simulation.  Two
copies of the same walkthrough means one of them is always out of date, and the
deck is the copy nobody re-runs -- its code listing had drifted to a kernel
that no longer exists.

So the walkthrough goes, and what is left is what a docs page cannot do: the
framing before the demo, and the argument after it.

Kept (presentation order 40-47, unchanged):
    Outline, Example: Connecting a Simple IP, HLS vs. RTL, HLS vs. RTL FPGA
    Design Flow, Bad vs. Good HLS Code Write, Vitis HLS, FPGA Board
    Components, Target Architecture

Removed (48-59), all covered by the docs:
    IP Source Code, Module Declaration x3, Vitis HLS Testbench, Vitis HLS Flow
    Described in Flow Panel, Synthesis Output, Synthesis Report, RTL
    Simulation, RTL Simulation over Multiple Interactions, Execution Model,
    Deploying on an FPGA Board

Added in their place:
    48  Vitis Kernel Types            -- host-activated vs free-running
    49  Host-Activated Execution Model -- the call diagram
    50  The Demo                       -- pointer to the docs, with commands
    51  Limitations of AXI4-Lite       -- the measured cost, and what is next

"Execution Model" is not so much deleted as promoted: slide 49 is the same
idea, redrawn as a call diagram, with the register offsets the docs measured.

Usage, from the repo root, with the deck closed in PowerPoint::

    python tools/restructure_procif_section3.py --check
    python tools/restructure_procif_section3.py

The script refuses to run twice: it checks for a slide only it creates.
"""
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

# --------------------------------------------------------------- palette ---
# Same constants as tools/build_procif_slides.py, which styled sections 1-2.
VIOLET = "57068C"
DEEP = "330662"
TINT = "EEE6F3"
TINT2 = "D5C4E3"
TEAL = "00857C"
TEALTINT = "DCEFEC"
TEALLINE = "9FD3CC"
SLATE = "2F6FA8"
SLATETINT = "EAF0F7"
SLATELINE = "B9CCE0"
AMBER = "B4530F"
AMBERTINT = "FCEEE3"
TEXT = "262626"
MUTED = "6E6E6E"
WHITE = "FFFFFF"
GRAYLINE = "BFBFBF"

EMU = 914400

# The "Title and Content" layout puts the title and its rule in the top
# 1.6in, and the NYU footer bar occupies the bottom of the slide.  Content
# that strays outside this band collides with one or the other.
CONTENT_TOP, CONTENT_BOTTOM = 1.62, 6.55
MARKER = "Vitis Kernel Types"   # a slide only this script adds

# Section 3's demo walkthrough, in presentation order.  Titles are asserted
# before anything is deleted, so a deck that has moved on fails loudly rather
# than losing the wrong slides.
DOOMED = [
    (48, "IP Source Code"),
    (49, "Module Declaration"),
    (50, "Module Declaration"),
    (51, "Module Declaration"),
    (52, "Vitis HLS Testbench"),
    (53, "Vitis HLS Flow Described in Flow Panel"),
    (54, "Synthesis Output"),
    (55, "Synthesis Report"),
    (56, "RTL Simulation"),
    (57, "RTL Simulation over Multiple Interactions"),
    (58, "Execution Model"),
    (59, "Deploying on an FPGA Board"),
]
ANCHOR_POS, ANCHOR_TITLE = 47, "Target Architecture"

DOCS_URL = "sdrangan.github.io/hwdesign"
DOCS_CRUMB = "Demos › Bus Basics and Memory-Mapped Interfaces"


def E(inches: float) -> int:
    return int(round(inches * EMU))


class Ids:
    def __init__(self) -> None:
        self.n = 1

    def __call__(self) -> int:
        self.n += 1
        return self.n


# ------------------------------------------------------------------ text ---
def rpr(sz=None, color=None, b=False, font=None, tag="a:rPr") -> str:
    attrs = ['lang="en-US"']
    if sz:
        attrs.append(f'sz="{int(round(sz * 100))}"')
    if b:
        attrs.append('b="1"')
    attrs.append('dirty="0"')
    inner = ""
    if color:
        inner += f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
    if font == "code":
        inner += '<a:latin typeface="Consolas"/><a:cs typeface="Consolas"/>'
    a = " ".join(attrs)
    return f"<{tag} {a}>{inner}</{tag}>" if inner else f"<{tag} {a}/>"


def run(text: str, **st) -> str:
    keep = ' xml:space="preserve"' if text != text.strip() else ""
    return f"<a:r>{rpr(**st)}<a:t{keep}>{escape(text)}</a:t></a:r>"


# **bold**  `code`  !!teal!!   -- the subset of build_procif_slides' markup
# that these slides need.
_TOK = re.compile(r"(\*\*.+?\*\*|`[^`]+`|!!.+?!!)")


def runs(markup: str, base: dict) -> str:
    out = []
    for piece in _TOK.split(markup):
        if not piece:
            continue
        st = dict(base)
        if piece.startswith("**"):
            piece, st["b"] = piece[2:-2], True
            st["color"] = st.get("color") or VIOLET
        elif piece.startswith("`"):
            piece, st["font"] = piece[1:-1], "code"
            st["color"] = DEEP
        elif piece.startswith("!!"):
            piece, st["color"] = piece[2:-2], TEAL
            st["b"] = True
        out.append(run(piece, **st))
    return "".join(out) or run("", **base)


def para(markup="", sz=None, color=None, b=False, align=None, marL=None,
         indent=None, bullet=None, spcBef=None) -> str:
    attrs = []
    if marL is not None:
        attrs.append(f'marL="{E(marL)}"')
    if indent is not None:
        attrs.append(f'indent="{E(indent)}"')
    if align:
        attrs.append(f'algn="{align}"')
    kids = ""
    if spcBef is not None:
        kids += f'<a:spcBef><a:spcPts val="{int(spcBef * 100)}"/></a:spcBef>'
    if bullet == "none":
        kids += "<a:buNone/>"
    elif bullet:
        char, bclr = bullet
        kids += (f'<a:buClr><a:srgbClr val="{bclr}"/></a:buClr><a:buSzPct val="70000"/>'
                 f'<a:buFont typeface="Arial"/><a:buChar char="{char}"/>')
    ppr = f'<a:pPr {" ".join(attrs)}>{kids}</a:pPr>' if attrs else (
        f"<a:pPr>{kids}</a:pPr>" if kids else "")
    return f"<a:p>{ppr}{runs(markup, dict(sz=sz, color=color, b=b))}" \
           f"{rpr(sz=sz, tag='a:endParaRPr')}</a:p>"


def bullet(markup, sz=15, color=TEXT, clr=VIOLET, spcBef=6):
    return para(markup, sz=sz, color=color, marL=0.26, indent=-0.26,
                bullet=("▪", clr), spcBef=spcBef)


# ---------------------------------------------------------------- shapes ---
def title_ph(ids: Ids, text: str) -> str:
    i = ids()
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Title {i}"/><p:cNvSpPr>'
            f'<a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="title"/></p:nvPr>'
            f'</p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>'
            f"<a:p>{run(text)}</a:p></p:txBody></p:sp>")


def sldnum_ph(ids: Ids) -> str:
    i = ids()
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Slide Number Placeholder {i}"/>'
            f'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
            f'<p:nvPr><p:ph type="sldNum" sz="quarter" idx="12"/></p:nvPr></p:nvSpPr>'
            f'<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p>'
            f'<a:fld id="{{629637A9-119A-49DA-BD12-AAC58B377D80}}" type="slidenum">'
            f'<a:rPr lang="en-US" smtClean="0"/><a:t>‹#›</a:t></a:fld>'
            f'<a:endParaRPr lang="en-US" dirty="0"/></a:p></p:txBody></p:sp>')


def textbox(ids: Ids, x, y, w, h, paras, anchor="t", inset=0.0) -> str:
    i = ids()
    ins = E(inset)
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="TextBox {i}"/>'
            f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/>'
            f'<a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="{ins}" tIns="{ins}" rIns="{ins}" '
            f'bIns="{ins}" anchor="{anchor}" rtlCol="0"><a:noAutofit/></a:bodyPr>'
            f'<a:lstStyle/>{"".join(paras)}</p:txBody></p:sp>')


def label(ids, x, y, w, h, text, sz=12, color=MUTED, align=None, b=False, anchor="t"):
    return textbox(ids, x, y, w, h,
                   [para(text, sz=sz, color=color, align=align, b=b)], anchor=anchor)


def shape(ids: Ids, x, y, w, h, fill=None, line=None, lw=1.0, prst="rect",
          paras=(), anchor="ctr", inset=0.08, adj=None) -> str:
    i = ids()
    gd = f'<a:gd name="adj" fmla="val {adj}"/>' if adj is not None else ""
    geom = f'<a:prstGeom prst="{prst}"><a:avLst>{gd}</a:avLst></a:prstGeom>'
    fillx = (f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
             if fill else "<a:noFill/>")
    linex = (f'<a:ln w="{int(lw * 12700)}"><a:solidFill>'
             f'<a:srgbClr val="{line}"/></a:solidFill></a:ln>'
             if line else "<a:ln><a:noFill/></a:ln>")
    tx = list(paras) or [para("", sz=10)]
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Shape {i}"/><p:cNvSpPr/>'
            f'<p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/>'
            f'<a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm>{geom}{fillx}{linex}</p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="{E(inset)}" tIns="{E(inset / 2)}" '
            f'rIns="{E(inset)}" bIns="{E(inset / 2)}" anchor="{anchor}" rtlCol="0">'
            f'<a:noAutofit/></a:bodyPr><a:lstStyle/>{"".join(tx)}</p:txBody></p:sp>')


def arrow(ids: Ids, x1, y1, x2, y2, color, lw=1.5, head=True, dash=False) -> str:
    """A straight connector.  A connector's box is always drawn left-to-right
    and top-to-bottom, so a leftward or upward arrow is the same box flipped."""
    i = ids()
    x, y = min(x1, x2), min(y1, y2)
    w, h = abs(x2 - x1), abs(y2 - y1)
    flip = (' flipH="1"' if x2 < x1 else "") + (' flipV="1"' if y2 < y1 else "")
    tail = '<a:tailEnd type="triangle" w="med" len="med"/>' if head else ""
    dashx = '<a:prstDash val="dash"/>' if dash else ""
    return (f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{i}" name="Connector {i}"/>'
            f'<p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
            f'<p:spPr><a:xfrm{flip}><a:off x="{E(x)}" y="{E(y)}"/>'
            f'<a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>'
            f'<a:ln w="{int(lw * 12700)}"><a:solidFill><a:srgbClr val="{color}"/>'
            f"</a:solidFill>{dashx}{tail}</a:ln></p:spPr></p:cxnSp>")


NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')


def slide_doc(shapes) -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<p:sld {NS}><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
            f'<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr>'
            f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            f'{"".join(shapes)}</p:spTree></p:cSld>'
            f"<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>")


# ======================================================== the new slides ===
def s_kernel_types(ids: Ids) -> list[str]:
    """Two panels: the kernel type we use, and the one we do not."""
    top, ph, bh = 2.00, 0.62, 3.88
    lx, rx, w = 0.75, 6.85, 5.7
    out = [title_ph(ids, "Vitis Kernel Types")]

    out += [
        label(ids, lx, CONTENT_TOP, 11.8, 0.32,
              "Vitis kernels come in two shapes.  The difference is who decides "
              "when the kernel runs.", sz=14, color=MUTED),
    ]

    # --- left panel: host activated -----------------------------------
    out += [
        shape(ids, lx, top, w, ph, fill=VIOLET, prst="roundRect", adj=12000,
              paras=[para("Host-Activated", sz=19, color=WHITE, b=True, align="ctr")]),
        shape(ids, lx, top + ph, w, bh, fill=TINT, line=TINT2, lw=1.0),
        textbox(ids, lx + 0.34, top + ph + 0.22, w - 0.68, bh - 0.44, [
            para("`#pragma HLS INTERFACE s_axilite port=return`", sz=12),
            para("`ap_ctrl_hs`  — the default", sz=12, color=MUTED, spcBef=2),
            bullet("Explicitly started by the processor", spcBef=12),
            bullet("Signals completion with a status bit, and can raise an interrupt"),
            bullet("The closest thing to a **function call** in hardware"),
            bullet("But the processor writes every input and reads every output"),
            bullet("Not how most production designs move data"),
            para("Our focus — it is the easiest to reason about, and every "
                 "idea in it carries over.", sz=13, color=VIOLET, b=True,
                 marL=0.26, bullet="none", spcBef=12),
        ]),
    ]

    # --- right panel: free running -------------------------------------
    out += [
        shape(ids, rx, top, w, ph, fill=TEAL, prst="roundRect", adj=12000,
              paras=[para("Free-Running Task", sz=19, color=WHITE, b=True, align="ctr")]),
        shape(ids, rx, top + ph, w, bh, fill=TEALTINT, line=TEALLINE, lw=1.0),
        textbox(ids, rx + 0.34, top + ph + 0.22, w - 0.68, bh - 0.44, [
            para("`#pragma HLS INTERFACE ap_ctrl_none port=return`", sz=12),
            para("`ap_ctrl_none`", sz=12, color=MUTED, spcBef=2),
            bullet("Runs continuously, waiting on data", clr=TEAL, spcBef=12),
            bullet("Operates without the processor once started", clr=TEAL),
            bullet("Enables far greater **concurrency**", clr=TEAL),
            bullet("Data arrives on a stream, not in registers", clr=TEAL),
            bullet("How real accelerators are built", clr=TEAL),
            para("Examined in the advanced course — and glimpsed next "
                 "lecture, with AXI4-Stream.", sz=13, color=TEAL, b=True,
                 marL=0.26, bullet="none", spcBef=12),
        ]),
    ]

    out.append(sldnum_ph(ids))
    return out


def s_execution_model(ids: Ids) -> list[str]:
    """The host-activated call, drawn as a sequence diagram."""
    out = [title_ph(ids, "Host-Activated Execution Model")]

    lx, rx = 2.55, 9.15          # lifeline centres
    hw, hh, htop = 2.5, 0.46, 1.72
    ltop, lbot = htop + hh, 5.95

    out += [
        shape(ids, lx - hw / 2, htop, hw, hh, fill=SLATE, prst="roundRect", adj=14000,
              paras=[para("Processor (PS)", sz=15, color=WHITE, b=True, align="ctr")]),
        shape(ids, rx - hw / 2, htop, hw, hh, fill=VIOLET, prst="roundRect", adj=14000,
              paras=[para("Vitis IP (PL)", sz=15, color=WHITE, b=True, align="ctr")]),
        # lifelines
        arrow(ids, lx, ltop, lx, lbot, GRAYLINE, lw=1.0, head=False, dash=True),
        arrow(ids, rx, ltop, rx, lbot, GRAYLINE, lw=1.0, head=False, dash=True),
    ]

    # (y, direction, label, register note, colour)
    steps = [
        (2.62, "r", "write x, w, b", "0x10, 0x18, 0x20", SLATE),
        (3.18, "r", "write 1 to CTRL  — ap_start", "0x00", SLATE),
        (4.46, "l", "ap_done set in CTRL", "optionally an interrupt", VIOLET),
        (5.00, "r", "read CTRL — poll for done", "0x00", SLATE),
        (5.56, "l", "return y", "0x28", VIOLET),
    ]
    for y, direction, text, note, colour in steps:
        x1, x2 = (lx, rx) if direction == "r" else (rx, lx)
        out.append(arrow(ids, x1, y, x2, y, colour, lw=2.0))
        # Label and register offset share one line.  On two lines the offset
        # sat directly on the next step's label -- the steps are only about
        # half an inch apart, and each text box is taller than that.
        caption = ('<a:p><a:pPr algn="ctr"/>'
                   + run(text, sz=13, color=colour, b=True)
                   + run("   ·   " + note, sz=11, color=MUTED)
                   + rpr(sz=13, tag="a:endParaRPr") + "</a:p>")
        out.append(textbox(ids, lx + 0.15, y - 0.40, rx - lx - 0.3, 0.34, [caption]))

    # the kernel's own work, as a box on its lifeline
    out.append(shape(ids, rx - 0.12, 3.50, 2.05, 0.72, fill=TINT, line=VIOLET, lw=1.25,
                     paras=[para("kernel runs", sz=13, color=VIOLET, b=True, align="ctr"),
                            para("5 cycles", sz=11, color=MUTED, align="ctr")]))
    out.append(label(ids, lx - 2.45, 3.56, 2.3, 0.6,
                     "processor waits,\nor does something else", sz=11, color=MUTED,
                     align="r"))

    out.append(shape(ids, 0.75, 6.06, 11.8, 0.46, fill=SLATETINT, line=SLATELINE, lw=1.0,
                     paras=[para("Measured on the bus: **4 writes and 2 reads** per call, "
                                 "**22 cycles** of traffic for **5 cycles** of computation.",
                                 sz=14, color=TEXT, align="ctr")]))
    out.append(sldnum_ph(ids))
    return out


def s_demo(ids: Ids) -> list[str]:
    """One pointer slide.  The walkthrough itself lives in the docs."""
    out = [title_ph(ids, "The Demo: a Scalar Function IP")]

    out.append(shape(ids, 0.75, 1.46, 11.8, 0.76, fill=VIOLET, prst="roundRect", adj=16000,
                     paras=[para(f"{DOCS_URL}   —   {DOCS_CRUMB}",
                                 sz=18, color=WHITE, b=True, align="ctr")]))

    out.append(label(ids, 0.75, 2.42, 5.9, 0.3, "RUN THE WHOLE FLOW", sz=12,
                     color=MUTED, b=True))
    out.append(shape(ids, 0.75, 2.76, 5.9, 1.95, fill="F4F4F7", line=GRAYLINE, lw=1.0,
                     anchor="t", inset=0.16, paras=[
                         para("`cd demos/scalar_fun/scalar_fun_vitis`", sz=12),
                         para("`python scalar_fun_build.py --list-steps`", sz=12, spcBef=6),
                         para("`python scalar_fun_build.py --through verify_csim`", sz=12, spcBef=6),
                         para("`python scalar_fun_build.py --through report`", sz=12, spcBef=6),
                     ]))

    out.append(label(ids, 6.95, 2.42, 5.6, 0.3, "WHAT TO WATCH FOR", sz=12,
                     color=MUTED, b=True))
    out.append(textbox(ids, 6.95, 2.76, 5.6, 2.0, [
        bullet("Each step **declares what it needs** — the order is derived, "
               "not written down", spcBef=0),
        bullet("A step whose inputs have not changed is **skipped**"),
        bullet("The build **refuses to synthesize** code that failed its checks"),
        bullet("Results are checked twice: after C simulation, and again "
               "against the **synthesized RTL**"),
    ]))

    out.append(shape(ids, 0.75, 5.02, 11.8, 1.5, fill=TEALTINT, line=TEALLINE, lw=1.0,
                     anchor="ctr", inset=0.24, paras=[
                         para("The demo ends with a timing diagram decoded from a real "
                              "co-simulation — the processor writing x, w and b, "
                              "starting the IP, polling for done, and reading y back.",
                              sz=15, color=TEXT, align="ctr"),
                         para("Everything on the next slide was measured from it.",
                              sz=14, color=TEAL, b=True, align="ctr", spcBef=8),
                     ]))
    out.append(sldnum_ph(ids))
    return out


def s_limitations(ids: Ids) -> list[str]:
    """The argument the demo exists to make."""
    out = [title_ph(ids, "Limitations of AXI4-Lite for Data")]

    # three measured figures across the top
    stats = [
        ("22", "cycles of bus traffic\nper call", SLATE),
        ("5", "cycles of actual\ncomputation", VIOLET),
        ("3.7 M", "calls/s — one DSP\ndoes 100 M MAC/s", AMBER),
    ]
    for i, (big, cap, colour) in enumerate(stats):
        x = 0.75 + i * 3.97
        out.append(shape(ids, x, CONTENT_TOP, 3.75, 1.16, fill=WHITE, line=colour, lw=1.5,
                         prst="roundRect", adj=8000, anchor="ctr", paras=[
                             para(big, sz=30, color=colour, b=True, align="ctr"),
                             para(cap, sz=12, color=MUTED, align="ctr")]))

    out.append(label(ids, 0.75, 3.00, 5.9, 0.3, "IT IS SLOW TO MOVE EACH VALUE",
                     sz=12, color=MUTED, b=True))
    out.append(textbox(ids, 0.75, 3.34, 5.9, 2.1, [
        bullet("**Four writes and two reads** to deliver 3 values and collect 1",
               spcBef=0),
        bullet("About **3 cycles** per register transfer"),
        bullet("The bus cost does **not shrink** if the kernel gets cleverer — "
               "here the interface dominates completely"),
    ]))

    out.append(label(ids, 6.95, 3.00, 5.6, 0.3, "THE PROCESSOR MUST POLL",
                     sz=12, color=MUTED, b=True))
    out.append(textbox(ids, 6.95, 3.34, 5.6, 2.1, [
        bullet("The host cannot know when the IP is done — it **asks, repeatedly**",
               spcBef=0),
        bullet("Each poll is a full AXI4-Lite read transaction"),
        bullet("Interrupts avoid the spinning, but cost a context switch — "
               "more than a 5-cycle kernel is worth"),
    ]))

    out.append(shape(ids, 0.75, 5.58, 11.8, 0.95, fill=TINT, line=VIOLET, lw=1.25,
                     anchor="ctr", inset=0.24, paras=[
                         para("AXI4-Lite is not the problem — using a **control** "
                              "interface as a **data** interface is.", sz=15,
                              color=TEXT, align="ctr"),
                         para("Next: AXI4-Stream — one transfer per cycle, no addresses, "
                              "and the processor out of the inner loop.",
                              sz=15, color=VIOLET, b=True, align="ctr", spcBef=6),
                     ]))
    out.append(sldnum_ph(ids))
    return out


NEW_SLIDES = [
    ("Vitis Kernel Types", s_kernel_types),
    ("Host-Activated Execution Model", s_execution_model),
    ("The Demo: a Scalar Function IP", s_demo),
    ("Limitations of AXI4-Lite for Data", s_limitations),
]


# ================================================================ plumbing ==
def find_skill_scripts() -> Path:
    """Locate the pptx skill's scripts/ directory.

    Scoped to ~/.claude/skills deliberately: globbing the whole home directory
    takes minutes on a large profile and looks like a hang.
    """
    roots = sorted((Path.home() / ".claude" / "skills").glob("**/pptx/scripts"))
    if not roots:
        raise SystemExit("pptx skill scripts not found; pass --skill-scripts")
    return roots[0]


def sh(cmd, cwd=None) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{' '.join(map(str, cmd))} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def slide_order(build: Path) -> list[str]:
    """Slide part names in presentation order (which is not file order)."""
    pres = (build / "ppt" / "presentation.xml").read_text(encoding="utf-8")
    rels = (build / "ppt" / "_rels" / "presentation.xml.rels").read_text(encoding="utf-8")
    rid = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    return [rid[r].replace("../", "").split("/")[-1]
            for r in re.findall(r'<p:sldId[^>]*r:id="([^"]+)"', pres)]


def slide_title(build: Path, name: str) -> str:
    xml = (build / "ppt" / "slides" / name).read_text(encoding="utf-8")
    texts = [t.strip() for t in re.findall(r"<a:t>(.*?)</a:t>", xml, re.S) if t.strip()]
    return texts[0] if texts else ""


def drop_from_sldIdLst(build: Path, names: set[str]) -> int:
    """Remove the presentation's references to these slide parts.

    The parts themselves are left for clean.py, which also prunes the media
    and relationships that only they used.
    """
    prels = build / "ppt" / "_rels" / "presentation.xml.rels"
    rels = prels.read_text(encoding="utf-8")
    rid = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    doomed_rids = {r for r, t in rid.items() if t.split("/")[-1] in names}

    ppath = build / "ppt" / "presentation.xml"
    pres = ppath.read_text(encoding="utf-8")
    n = 0
    for r in doomed_rids:
        pres, k = re.subn(rf'<p:sldId[^>]*r:id="{r}"\s*/>', "", pres)
        n += k
    ppath.write_text(pres, encoding="utf-8")
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Restructure unit 4 Section 3.")
    ap.add_argument("--deck", type=Path,
                    default=Path("units/unit04_procif/procif.pptx"))
    ap.add_argument("--out", type=Path, default=None)
    # Scratch goes to the system temp directory, not into the repo --
    # unpacking a deck produces a few hundred files, and
    # build_procif_slides.py already sets this precedent.
    ap.add_argument("--work", type=Path,
                    default=Path(tempfile.gettempdir()) / "procif_restructure")
    ap.add_argument("--skill-scripts", type=Path, default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    deck: Path = args.deck
    out: Path = args.out or deck
    if not deck.exists():
        raise SystemExit(f"No deck at {deck} (run from the repo root).")
    lock = deck.with_name("~$" + deck.name)
    if lock.exists():
        try:
            with open(deck, "r+b"):
                pass
        except PermissionError:
            raise SystemExit(f"{deck.name} is open in PowerPoint. Close it first.")

    scripts = args.skill_scripts or find_skill_scripts()
    # Absolute: add_slide.py and clean.py are run with cwd set to the skill's
    # scripts directory, so a relative path would resolve against that.
    build = (args.work / "unpacked").resolve()
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    with zipfile.ZipFile(deck) as z:
        z.extractall(build)

    order = slide_order(build)
    titles = [slide_title(build, n) for n in order]

    if MARKER in titles:
        raise SystemExit(
            f"'{MARKER}' is already in the deck -- Section 3 has been "
            f"restructured already.  Nothing to do.")

    # Check the deck is the one this script was written against, before
    # deleting anything.
    if titles[ANCHOR_POS - 1] != ANCHOR_TITLE:
        raise SystemExit(f"expected '{ANCHOR_TITLE}' at position {ANCHOR_POS}, "
                         f"found '{titles[ANCHOR_POS - 1]}'")
    doomed = {}
    for pos, want in DOOMED:
        got = titles[pos - 1]
        if got != want:
            raise SystemExit(f"expected '{want}' at position {pos}, found '{got}'")
        doomed[order[pos - 1]] = want

    print(f"anchor: {ANCHOR_POS} {ANCHOR_TITLE} ({order[ANCHOR_POS - 1]})")
    print("to remove:")
    for name, t in doomed.items():
        print(f"  {name:<14} {t}")
    print("to add, after the anchor:")
    for t, _ in NEW_SLIDES:
        print(f"  {t}")
    if args.check:
        print("\n--check: no files written.")
        return

    # A donor slide whose only relationship is a "Title and Content" layout.
    #
    # Both halves matter.  One relationship means the duplicate carries no
    # images or notes to strip afterwards.  The layout matters more: on the
    # "Title Slide" layout the title placeholder is centred half-way down the
    # slide, so a new slide's title lands *behind* its own content, and that
    # layout's decoration shows through as a stray bracket.
    donor = None
    for name in order:
        rels = (build / "ppt" / "slides" / "_rels" / f"{name}.rels").read_text(encoding="utf-8")
        if len(re.findall(r"<Relationship ", rels)) != 1:
            continue
        m = re.search(r"slideLayout(\d+)\.xml", rels)
        if not m:
            continue
        layout = (build / "ppt" / "slideLayouts" / f"slideLayout{m.group(1)}.xml")
        name_m = re.search(r'name="([^"]+)"', layout.read_text(encoding="utf-8")[:2000])
        if name_m and name_m.group(1) == "Title and Content":
            donor = name
            break
    if donor is None:
        raise SystemExit("no single-relationship slide on the 'Title and Content' layout")
    print(f"donor slide: {donor}")

    after = order[ANCHOR_POS - 1]
    for title, fn in NEW_SLIDES:
        made = sh([sys.executable, "add_slide.py", str(build), donor, "--after", after],
                  cwd=scripts)
        m = re.search(r"(slide\d+\.xml)", made.split("Created", 1)[1]) if "Created" in made else None
        if not m:
            raise SystemExit(f"could not parse add_slide output:\n{made}")
        new_name = m.group(1)
        (build / "ppt" / "slides" / new_name).write_text(
            slide_doc(fn(Ids())), encoding="utf-8")
        print(f"  + {new_name}  {title}")
        after = new_name

    removed = drop_from_sldIdLst(build, set(doomed))
    print(f"removed {removed} slide reference(s)")

    print(sh([sys.executable, "clean.py", str(build)], cwd=scripts).strip())

    if out == deck:
        backup = deck.with_suffix(".pptx.bak")
        shutil.copy2(deck, backup)
        print(f"backup: {backup.name}")
    tmp = out.with_suffix(".pptx.tmp")
    if tmp.exists():
        tmp.unlink()
    ct = build / "[Content_Types].xml"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ct, "[Content_Types].xml")
        for f in sorted(p for p in build.rglob("*") if p.is_file()):
            if f != ct:
                z.write(f, f.relative_to(build).as_posix())
    tmp.replace(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
