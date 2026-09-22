"""Rebuild unit 4's slide deck: procif.pptx -> procif_v4.pptx.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
This is a *one-shot migration*, not the source of the deck.  It reads the
pre-revision procif.pptx, applies a fixed list of edits, and writes a new file.
It cannot read changes back: once the new deck is adopted and edited in
PowerPoint, this script is a record of what was done, not a way to rebuild it.
Re-running it against an already-migrated deck would insert the new slides a
second time.

It is checked in for two reasons: it documents exactly what changed in the
deck, and its helpers (palette, paragraph/shape/table builders, the restyle and
diagram-recolour passes) are the starting point for giving sections 2 and 3,
and the other units' decks, the same treatment.

WHAT IT DOES
------------
  * inserts nine slides: byte vs. word addressing, address maps and register
    maps, each followed by an in-class practice problem and its solution.  The
    problems themselves live in hwdesign-soln .../prob/procif.xml; the slides
    only display them.
  * rebuilds the learning objectives as a table of the unit's skills, the
    on-chip memory table, the video example, and the SRAM/DRAM comparison
    (previously a screenshot of a table)
  * restyles section 1 onto an NYU Violet palette: violet for storage, slate
    blue for address and control, teal for data, amber for error callouts
  * points the theme's accent1 at NYU Violet, so style-driven shapes and table
    headers across the whole deck follow
  * fixes content errors: the video example's address width, the AXI4-Lite
    write response (the slave drives BVALID, the master answers BREADY), and
    several typos

REQUIREMENTS
------------
Python with lxml, and the pptx skill's scripts/ directory (add_slide.py,
clean.py) which is found automatically under ~/.claude/skills, or passed with
--skill-scripts.

USAGE
-----
    python tools/build_procif_slides.py \
        --src units/unit04_procif/procif.pptx \
        --out units/unit04_procif/procif_v4.pptx

Validate and render the result (PowerPoint renders fonts and equations exactly
as they will appear in class):

    python <skill>/scripts/office/validate.py out.pptx --original src.pptx
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def _find_skill_scripts():
    """Locate the pptx skill's scripts/ directory.

    Scoped to ~/.claude/skills deliberately: globbing the whole home directory
    takes minutes on a large profile and looks like a hang.
    """
    roots = sorted((Path.home() / ".claude" / "skills").glob("**/pptx/scripts"))
    if not roots:
        raise SystemExit(
            "pptx skill scripts not found under ~/.claude/skills; pass --skill-scripts")
    return roots[0]


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    here = Path(__file__).resolve().parent.parent
    p.add_argument("--src", type=Path, default=here / "units/unit04_procif/procif.pptx",
                   help="the pre-migration deck to read")
    p.add_argument("--out", type=Path, default=here / "units/unit04_procif/procif_v4.pptx",
                   help="the deck to write")
    p.add_argument("--work", type=Path, default=Path(tempfile.gettempdir()) / "procif_build",
                   help="scratch directory for the unpacked package")
    p.add_argument("--skill-scripts", type=Path, default=None,
                   help="the pptx skill's scripts/ directory")
    a = p.parse_args()
    a.skill_scripts = a.skill_scripts or _find_skill_scripts()
    return a

ARGS = _parse_args()
SRC = ARGS.src
OUT = ARGS.out
BUILD = ARGS.work / 'unpacked'
SCRIPTS = ARGS.skill_scripts
SLIDES = BUILD / "ppt" / "slides"

# ---------------------------------------------------------------- palette ---
VIOLET = "57068C"     # NYU violet: key terms, bullets, table headers
DEEP = "330662"       # code and values
TINT = "EEE6F3"       # memory cells, cards
TINT2 = "D5C4E3"      # borders
BAND = "F7F3FA"       # banded table rows
TEAL = "00857C"       # answers and results
TEALTINT = "DCEFEC"
TEALLINE = "9FD3CC"
AMBER = "B4530F"      # common-error callouts only
AMBERTINT = "FCEEE3"
TEXT = "262626"
MUTED = "6E6E6E"
GRAYFILL = "EDEDED"
GRAYLINE = "BFBFBF"
WHITE = "FFFFFF"
SLATE = "2F6FA8"       # address and control paths in the diagrams
SLATETINT = "EAF0F7"
SLATELINE = "B9CCE0"
GRAYTINT = "E9E9EE"

# The hand-drawn diagrams are recoloured rather than redrawn: three families
# only — violet for storage, slate blue for address and control, teal for data.
DIAGRAM_FILLS = {
    '<a:schemeClr val="accent1"><a:lumMod val="20000"/><a:lumOff val="80000"/></a:schemeClr>': TINT,
    '<a:schemeClr val="accent2"><a:lumMod val="20000"/><a:lumOff val="80000"/></a:schemeClr>': TINT,
    '<a:schemeClr val="accent3"><a:lumMod val="20000"/><a:lumOff val="80000"/></a:schemeClr>': TINT,
    '<a:schemeClr val="accent4"><a:lumMod val="20000"/><a:lumOff val="80000"/></a:schemeClr>': TINT,
    '<a:schemeClr val="accent5"><a:lumMod val="20000"/><a:lumOff val="80000"/></a:schemeClr>': SLATETINT,
    '<a:schemeClr val="accent6"><a:lumMod val="20000"/><a:lumOff val="80000"/></a:schemeClr>': SLATETINT,
    '<a:schemeClr val="accent5"><a:lumMod val="40000"/><a:lumOff val="60000"/></a:schemeClr>': SLATETINT,
    '<a:schemeClr val="accent5"><a:lumMod val="50000"/></a:schemeClr>': SLATE,
    '<a:schemeClr val="accent5"><a:lumMod val="75000"/></a:schemeClr>': SLATE,
    '<a:schemeClr val="accent6"><a:lumMod val="75000"/></a:schemeClr>': SLATE,
    '<a:schemeClr val="accent3"><a:lumMod val="75000"/></a:schemeClr>': VIOLET,
    '<a:schemeClr val="bg2"><a:lumMod val="75000"/></a:schemeClr>': GRAYTINT,
    '<a:srgbClr val="CCFF99"/>': TEALTINT,
    '<a:srgbClr val="E0F8E0"/>': TEALTINT,
    '<a:srgbClr val="00B050"/>': TEAL,
}

# Per-slide exceptions.  On the memory-mapped-registers diagram the green
# shapes are the address bus, its decoders and their select arrows (slate),
# while the grey bar is the data bus (teal) — the opposite of the default.
DIAGRAM_OVERRIDES = {
    "slide15.xml": {
        '<a:srgbClr val="E0F8E0"/>': SLATETINT,
        '<a:schemeClr val="bg2"><a:lumMod val="75000"/></a:schemeClr>': TEALTINT,
        '<a:srgbClr val="00B050"/>': SLATE,
    },
}

# Diagram label colours: greens become teal, blues become slate.
DIAGRAM_TEXT = {
    '<a:srgbClr val="00B050"/>': TEAL,
    '<a:schemeClr val="accent5"><a:lumMod val="75000"/></a:schemeClr>': SLATE,
    '<a:schemeClr val="accent6"><a:lumMod val="75000"/></a:schemeClr>': SLATE,
    '<a:schemeClr val="accent6"/>': SLATE,
    '<a:schemeClr val="accent5"/>': SLATE,
}

EMU = 914400


def E(inches):
    return int(round(inches * EMU))


class Ids:
    def __init__(self):
        self.n = 1

    def __call__(self):
        self.n += 1
        return self.n


# ------------------------------------------------------------------- text ---
def rpr(sz=None, color=None, b=False, font=None, baseline=None, tag="a:rPr"):
    attrs = ['lang="en-US"']
    if sz:
        attrs.append(f'sz="{int(round(sz * 100))}"')
    if b:
        attrs.append('b="1"')
    if baseline:
        attrs.append(f'baseline="{baseline}"')
    attrs.append('dirty="0"')
    inner = ""
    if color:
        inner += f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
    if font == "code":
        inner += '<a:latin typeface="Consolas"/><a:cs typeface="Consolas"/>'
    elif font == "math":
        inner += '<a:latin typeface="Cambria Math"/>'
    a = " ".join(attrs)
    return f"<{tag} {a}>{inner}</{tag}>" if inner else f"<{tag} {a}/>"


def run(text, **st):
    keep = ' xml:space="preserve"' if text != text.strip() else ""
    return f"<a:r>{rpr(**st)}<a:t{keep}>{escape(text)}</a:t></a:r>"


# **key**  !!answer!!  ^^warning^^  `code`  $math$  ^{sup}  _{sub}
OUTER = re.compile(r"(\*\*.+?\*\*|!!.+?!!|\^\^.+?\^\^)")
INNER = re.compile(r"(`[^`]+`|\$[^$]+\$|\^\{[^}]*\}|_\{[^}]*\})")


def runs(markup, base):
    out = []
    for seg in OUTER.split(markup):
        if not seg:
            continue
        st = dict(base)
        outer_color = False
        for mark, color in (("**", VIOLET), ("!!", TEAL), ("^^", AMBER)):
            if seg.startswith(mark) and seg.endswith(mark) and len(seg) > 4:
                seg, outer_color = seg[2:-2], True
                st.update(color=color, b=True)
                break
        for piece in INNER.split(seg):
            if not piece:
                continue
            st2 = dict(st)
            if piece.startswith("`"):
                piece = piece[1:-1]
                st2["font"] = "code"
                if not outer_color:
                    st2["color"] = DEEP
            elif piece.startswith("$"):
                piece, st2["font"] = piece[1:-1], "math"
            elif piece.startswith("^{"):
                piece, st2["baseline"] = piece[2:-1], 30000
            elif piece.startswith("_{"):
                piece, st2["baseline"] = piece[2:-1], -25000
            out.append(run(piece, **st2))
    return "".join(out)


def para(markup, sz=None, color=None, b=False, align=None, lvl=None, marL=None,
         indent=None, bullet=None, spcBef=None, spcAft=None):
    attrs = []
    if lvl:
        attrs.append(f'lvl="{lvl}"')
    if marL is not None:
        attrs.append(f'marL="{E(marL)}"')
    if indent is not None:
        attrs.append(f'indent="{E(indent)}"')
    if align:
        attrs.append(f'algn="{align}"')
    kids = ""
    if spcBef is not None:
        kids += f'<a:spcBef><a:spcPts val="{int(spcBef * 100)}"/></a:spcBef>'
    if spcAft is not None:
        kids += f'<a:spcAft><a:spcPts val="{int(spcAft * 100)}"/></a:spcAft>'
    if bullet == "none":
        kids += "<a:buNone/>"
    elif bullet:
        char, bclr = bullet
        kids += (f'<a:buClr><a:srgbClr val="{bclr}"/></a:buClr><a:buFont typeface="Arial"/>'
                 f'<a:buChar char="{char}"/>')
    ppr = ""
    if attrs or kids:
        ppr = f'<a:pPr {" ".join(attrs)}>{kids}</a:pPr>' if attrs else f"<a:pPr>{kids}</a:pPr>"
    body = runs(markup, dict(sz=sz, color=color, b=b))
    return f"<a:p>{ppr}{body}{rpr(sz=sz, tag='a:endParaRPr')}</a:p>"


def part(label, text, sz):
    """A lettered part with a hanging indent: '(a)<tab>text'."""
    return para(f"**{label}**\t{text}", sz=sz, color=TEXT, marL=0.45, indent=-0.45, spcBef=9)


def cont(text, sz, color=TEXT):
    """A continuation line aligned with the part text above it."""
    return para(text, sz=sz, color=color, marL=0.45, indent=0, spcBef=2)


def bullet_item(text, sz):
    return para(text, sz=sz, color=TEXT, marL=0.3, indent=-0.22, bullet=("•", VIOLET), spcBef=3)


def lst_style(sz1=20, sz2=18, margins=True, spacing=True):
    """Body bullets: violet squares at level 1, grey dashes at level 2.

    The template's margins were set for its ❑ glyph, which sits flush against
    the text, so the new bullets need their own margins even on old slides.
    Spacing is left to the template on old slides, whose layouts assume it.
    """
    m1 = f' marL="{E(0.3)}" indent="{E(-0.3)}"' if margins else ""
    m2 = f' marL="{E(0.68)}" indent="{E(-0.25)}"' if margins else ""
    s1 = '<a:spcBef><a:spcPts val="1400"/></a:spcBef>' if spacing else ""
    s2 = '<a:spcBef><a:spcPts val="400"/></a:spcBef>' if spacing else ""
    d1 = f'<a:defRPr sz="{sz1 * 100}"/>' if sz1 else ""
    d2 = f'<a:defRPr sz="{sz2 * 100}"/>' if sz2 else ""
    return ("<a:lstStyle>"
            f'<a:lvl1pPr{m1}>{s1}<a:buClr><a:srgbClr val="{VIOLET}"/></a:buClr><a:buSzPct val="70000"/>'
            f'<a:buFont typeface="Arial"/><a:buChar char="■"/>{d1}</a:lvl1pPr>'
            f'<a:lvl2pPr{m2}>{s2}<a:buClr><a:srgbClr val="999999"/></a:buClr><a:buSzPct val="100000"/>'
            f'<a:buFont typeface="Arial"/><a:buChar char="–"/>{d2}</a:lvl2pPr>'
            "</a:lstStyle>")


# ----------------------------------------------------------------- shapes ---
def title_ph(ids, text):
    i = ids()
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Title {i}"/><p:cNvSpPr><a:spLocks noGrp="1"/>'
            f'</p:cNvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/>'
            f"<p:txBody><a:bodyPr/><a:lstStyle/><a:p>{run(text)}</a:p></p:txBody></p:sp>")


def body_ph(ids, x, y, w, h, paras, sz1=20, sz2=18):
    i = ids()
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Content Placeholder {i}"/><p:cNvSpPr>'
            f'<a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm></p:spPr>'
            f'<p:txBody><a:bodyPr><a:noAutofit/></a:bodyPr>{lst_style(sz1, sz2)}{"".join(paras)}'
            f"</p:txBody></p:sp>")


def sldnum_ph(ids):
    i = ids()
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Slide Number Placeholder {i}"/><p:cNvSpPr>'
            f'<a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldNum" sz="quarter" idx="12"/>'
            f"</p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p>"
            f'<a:fld id="{{629637A9-119A-49DA-BD12-AAC58B377D80}}" type="slidenum">'
            f'<a:rPr lang="en-US" smtClean="0"/><a:t>‹#›</a:t></a:fld>'
            f'<a:endParaRPr lang="en-US" dirty="0"/></a:p></p:txBody></p:sp>')


def textbox(ids, x, y, w, h, paras, anchor="t", inset=0.0):
    i = ids()
    ins = E(inset)
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="TextBox {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/>'
            f'</p:nvSpPr><p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/>'
            f'</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="{ins}" tIns="{ins}" rIns="{ins}" bIns="{ins}" '
            f'anchor="{anchor}" rtlCol="0"><a:noAutofit/></a:bodyPr><a:lstStyle/>{"".join(paras)}'
            f"</p:txBody></p:sp>")


def label(ids, x, y, w, h, text, sz=12, color=MUTED, align=None, b=False, anchor="t"):
    return textbox(ids, x, y, w, h, [para(text, sz=sz, color=color, align=align, b=b)], anchor=anchor)


def shape(ids, x, y, w, h, fill=None, line=None, lw=1.0, prst="rect", paras=(), anchor="ctr",
          inset=0.06, adj=None):
    i = ids()
    gd = f'<a:gd name="adj" fmla="val {adj}"/>' if adj is not None else ""
    geom = f'<a:prstGeom prst="{prst}"><a:avLst>{gd}</a:avLst></a:prstGeom>'
    fillx = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
    linex = (f'<a:ln w="{int(lw * 12700)}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
             if line else "<a:ln><a:noFill/></a:ln>")
    tx = list(paras) or [para("", sz=10)]
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Shape {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm>'
            f"{geom}{fillx}{linex}</p:spPr>"
            f'<p:txBody><a:bodyPr wrap="square" lIns="{E(inset)}" tIns="{E(inset / 2)}" '
            f'rIns="{E(inset)}" bIns="{E(inset / 2)}" anchor="{anchor}" rtlCol="0"><a:noAutofit/>'
            f'</a:bodyPr><a:lstStyle/>{"".join(tx)}</p:txBody></p:sp>')


def table(ids, x, y, colw, rows, rowh=0.38, sz=14, header=True):
    i = ids()

    def border(tag):
        return f'<a:{tag} w="9525"><a:solidFill><a:srgbClr val="{TINT2}"/></a:solidFill></a:{tag}>'

    trs = []
    for r, row in enumerate(rows):
        tcs = []
        for cell in row:
            cell = {"t": cell} if isinstance(cell, str) else cell
            head = header and r == 0
            fill = cell.get("fill") or (VIOLET if head else (BAND if r % 2 else WHITE))
            color = cell.get("color") or (WHITE if head else TEXT)
            p = para(cell["t"], sz=cell.get("sz", sz), color=color, b=head, align=cell.get("align"))
            tcpr = (f'<a:tcPr marL="{E(0.08)}" marR="{E(0.06)}" marT="{E(0.03)}" marB="{E(0.03)}" '
                    f'anchor="ctr">{border("lnL")}{border("lnR")}{border("lnT")}{border("lnB")}'
                    f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr>')
            tcs.append(f"<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{p}</a:txBody>{tcpr}</a:tc>")
        trs.append(f'<a:tr h="{E(rowh)}">{"".join(tcs)}</a:tr>')
    grid = "".join(f'<a:gridCol w="{E(c)}"/>' for c in colw)
    W, H = sum(colw), rowh * len(rows)
    return (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="Table {i}"/>'
            f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/>'
            f'</p:nvGraphicFramePr><p:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(W)}" cy="{E(H)}"/>'
            f'</p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
            f'<a:tbl><a:tblPr firstRow="1" bandRow="1"><a:tableStyleId>{{2D5ABB26-0587-4C30-8999-92F81FD0307C}}'
            f'</a:tableStyleId></a:tblPr><a:tblGrid>{grid}</a:tblGrid>{"".join(trs)}</a:tbl>'
            f"</a:graphicData></a:graphic></p:graphicFrame>")


def cells(ids, x, y, labels, w, h, fill, sz=13, line=TINT2):
    return [shape(ids, x + k * w, y, w, h, fill=fill, line=line, lw=0.75,
                  paras=[para(lab, sz=sz, color=DEEP, align="ctr")]) for k, lab in enumerate(labels)]


def field_bar(ids, x, y, h, parts):
    """Adjacent labelled boxes: parts = [(width, fill, color, [(text, size, bold), ...]), ...]."""
    out, cx = [], x
    for w, fill, color, lines in parts:
        out.append(shape(ids, cx, y, w, h, fill=fill, line=TINT2, lw=0.75,
                         paras=[para(t, sz=s, color=color, b=bb, align="ctr") for t, s, bb in lines]))
        cx += w
    return out


def arrow(ids, x1, y1, x2, y2, color, lw=1.25, head=True):
    """A straight connector.  A connector's box is always drawn left-to-right
    and top-to-bottom, so a leftward or upward arrow is the same box flipped."""
    i = ids()
    x, y = min(x1, x2), min(y1, y2)
    w, h = abs(x2 - x1), abs(y2 - y1)
    flip = (' flipH="1"' if x2 < x1 else "") + (' flipV="1"' if y2 < y1 else "")
    tail = '<a:tailEnd type="triangle" w="med" len="med"/>' if head else ""
    return (f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{i}" name="Connector {i}"/><p:cNvCxnSpPr/>'
            f"<p:nvPr/></p:nvCxnSpPr>"
            f'<p:spPr><a:xfrm{flip}><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/>'
            f'</a:xfrm><a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>'
            f'<a:ln w="{int(lw * 12700)}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f"{tail}</a:ln></p:spPr></p:cxnSp>")


def pill(ids, kind):
    fill = TEAL if kind == "SOLUTION" else VIOLET
    return shape(ids, 10.55, 0.68, 1.6, 0.42, fill=fill, prst="roundRect", adj=50000,
                 paras=[para(kind, sz=13, color=WHITE, b=True, align="ctr")])


def portal_caption(ids, qtag):
    return label(ids, 1.2, 6.2, 9.0, 0.32, f"Also in the LLM grader: Unit 4 › {qtag}", sz=12)


NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')


def slide_doc(shapes):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<p:sld {NS}><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/>'
            f'<p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>{"".join(shapes)}'
            f"</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>")


def flat(items):
    out = []
    for it in items:
        out.extend(it if isinstance(it, list) else [it])
    return out


# ============================================================ new slides ===
def s_byte_word(ids):
    rows = [("0", ["0", "1", "2", "3"]), ("1", ["4", "5", "6", "7"]), ("2", ["8", "9", "10", "11"])]
    sh = [title_ph(ids, "Byte vs. Word Addressing"),
          body_ph(ids, 1.2, 1.75, 6.35, 4.6, [
              para("**Word address**: counts words: 0, 1, 2, …"),
              para("**Byte address**: counts bytes"),
              para("A $𝑊$-bit word spans $𝑊$/8 byte addresses", lvl=1),
              para("Word $𝑘$ starts at byte $4𝑘$ (32-bit) or $8𝑘$ (64-bit)", lvl=1),
              para("A byte address splits into two fields"),
              para("Low log₂($𝑊$/8) bits: the byte within the word", lvl=1),
              para("Remaining bits: the word index", lvl=1),
              para("Processor buses, including AXI, use **byte addresses**"),
              para("even when every access is a whole word", lvl=1),
          ], sz1=20, sz2=17),
          label(ids, 7.9, 1.78, 4.3, 0.3, "32-bit memory, byte-addressable", sz=13),
          label(ids, 7.9, 2.12, 0.8, 0.3, "Word", align="ctr"),
          label(ids, 8.85, 2.12, 2.48, 0.3, "Byte addresses", align="ctr")]
    for r, (idx, labs) in enumerate(rows):
        y = 2.45 + r * 0.5
        sh.append(label(ids, 7.9, y, 0.8, 0.44, f"`{idx}`", sz=14, color=DEEP, align="ctr", anchor="ctr"))
        sh += cells(ids, 8.85, y, [f"`{v}`" for v in labs], 0.62, 0.44, TINT)
    sh.append(label(ids, 8.85, 3.92, 2.48, 0.36, "⋮", sz=16, align="ctr"))
    sh.append(label(ids, 7.9, 4.3, 0.8, 0.44, "$𝑘$", sz=14, color=DEEP, align="ctr", anchor="ctr"))
    sh += cells(ids, 8.85, 4.3, ["$4𝑘$", "$4𝑘+1$", "$4𝑘+2$", "$4𝑘+3$"], 0.62, 0.44, TINT, sz=11)
    sh.append(label(ids, 8.85, 4.98, 3.3, 0.28, "A 32-bit byte address"))
    sh += field_bar(ids, 8.85, 5.28, 0.62, [
        (2.1, TINT, DEEP, [("word index", 13, True), ("bits 31–2", 11, False)]),
        (0.9, TEALTINT, TEAL, [("byte", 13, True), ("1–0", 11, False)])])
    sh.append(label(ids, 8.85, 5.95, 3.4, 0.3, "e.g. `0x14` → word 5, byte 0", sz=13, color=TEXT))
    sh.append(sldnum_ph(ids))
    return sh


def s_byte_word_practice(ids):
    sh = [title_ph(ids, "Byte and Word Addresses"), pill(ids, "PRACTICE"),
          textbox(ids, 1.2, 1.8, 6.7, 4.3, [
              para("A memory stores 64-bit words and is byte-addressable: byte address 0 is the first "
                   "byte of word 0, and each word occupies consecutive byte addresses.",
                   sz=18, color=TEXT, spcAft=6),
              part("(a)", "What is the byte address of word 13? Give it in decimal and in hexadecimal.", 18),
              part("(b)", "Which word contains byte address `0x5C`, and at which byte offset within that word?", 18),
              part("(c)", "The memory has a depth of 4096 words. How many address bits are needed with "
                          "byte addressing? How many with word addressing?", 18)]),
          label(ids, 8.3, 1.85, 3.9, 0.3, "64-bit words: 8 bytes each", sz=13)]
    for r in range(2):
        y = 2.25 + r * 0.5
        sh.append(label(ids, 8.3, y, 0.55, 0.42, f"`{r}`", sz=13, color=DEEP, align="ctr", anchor="ctr"))
        sh += cells(ids, 8.9, y, [f"`{8 * r + k}`" for k in range(8)], 0.41, 0.42, TINT, sz=11)
    sh += [label(ids, 8.9, 3.22, 3.28, 0.36, "⋮", sz=16, align="ctr"),
           label(ids, 8.3, 3.75, 3.9, 0.36, "Word 13 starts at byte ?", sz=15, color=VIOLET, b=True),
           portal_caption(ids, "Byte and word addresses"), sldnum_ph(ids)]
    return sh


def s_byte_word_solution(ids):
    sh = [title_ph(ids, "Byte and Word Addresses"), pill(ids, "SOLUTION"),
          textbox(ids, 1.2, 1.8, 6.8, 4.3, [
              part("(a)", "8 bytes per word, so word 13 starts at 13 × 8 = !!104!! = !!`0x68`!!", 17),
              part("(b)", "`0x5C` = 92 = 8 × 11 + 4 → !!word 11!!, !!byte 4!!", 17),
              cont("word = `addr >> 3`     byte = `addr & 0x7`", 15, MUTED),
              part("(c)", "Word addressing: 4096 = 2^{12} words → !!12 bits!!", 17),
              cont("Byte addressing: 4096 × 8 = 2^{15} bytes → !!15 bits!!", 17),
              cont("The extra 3 bits select the byte within the word", 15, MUTED)]),
          label(ids, 8.3, 1.85, 3.9, 0.3, "A byte address, 64-bit words")]
    sh += field_bar(ids, 8.3, 2.18, 0.62, [
        (2.6, TINT, DEEP, [("word index", 13, True), ("bits 14–3", 11, False)]),
        (1.3, TEALTINT, TEAL, [("byte", 13, True), ("2–0", 11, False)])])
    sh += [shape(ids, 8.3, 3.3, 3.9, 1.15, fill=AMBERTINT, prst="roundRect", adj=8000, anchor="t",
                 inset=0.16, paras=[para("^^Common error^^", sz=15, spcAft=4),
                                    para("Using 4 bytes per word, the 32-bit habit, gives 52, word 23 "
                                         "and 14 bits.", sz=15, color=TEXT)]),
           portal_caption(ids, "Byte and word addresses"), sldnum_ph(ids)]
    return sh


def s_address_map(ids):
    sh = [title_ph(ids, "Address Maps"),
          body_ph(ids, 1.2, 1.75, 6.35, 4.3, [
              para("Modules on a shared bus share one **global address space**"),
              para("Each module gets a **base address** and a size"),
              para("Size a power of two; base aligned to the size", lvl=1),
              para("**Local address**: the offset within a module"),
              para("Global address = base + local address", lvl=1),
              para("The module's decoder sees only the local address", lvl=1),
              para("Decoding a global address"),
              para("Upper bits select the module", lvl=1),
              para("Lower bits are the local address", lvl=1),
          ], sz1=20, sz2=17),
          label(ids, 1.2, 6.05, 6.3, 0.35,
                "Vitis also says “global memory” for off-chip DDR, a different meaning."),
          label(ids, 7.8, 1.78, 4.4, 0.3, "Example address map (not to scale)"),
          shape(ids, 10.05, 2.15, 2.15, 1.05, fill=TINT, line=TINT2,
                paras=[para("DDR", sz=15, color=DEEP, b=True, align="ctr"),
                       para("1 GB", sz=12, color=MUTED, align="ctr")]),
          shape(ids, 10.05, 3.45, 2.15, 0.75, fill=TEALTINT, line=TEALLINE,
                paras=[para("BRAM", sz=15, color=TEAL, b=True, align="ctr"),
                       para("8 KB", sz=12, color=MUTED, align="ctr")]),
          shape(ids, 10.05, 4.45, 2.15, 0.75, fill=TINT, line=TINT2,
                paras=[para("IP registers", sz=15, color=DEEP, b=True, align="ctr"),
                       para("4 KB", sz=12, color=MUTED, align="ctr")])]
    for y, addr in ((2.15, "0x0000_0000"), (2.92, "0x3FFF_FFFF"), (3.45, "0x4000_0000"),
                    (3.93, "0x4000_1FFF"), (4.45, "0x4001_0000"), (4.93, "0x4001_0FFF")):
        sh.append(label(ids, 7.75, y, 2.2, 0.28, f"`{addr}`", sz=12, color=DEEP, align="r"))
    sh += [shape(ids, 7.8, 5.4, 4.4, 0.85, fill=BAND, line=TINT2, prst="roundRect", adj=12000,
                 paras=[para("Global `0x4000_0104` → **BRAM**", sz=14, color=TEXT, align="ctr"),
                        para("local = `0x4000_0104` − `0x4000_0000` = `0x104`", sz=12, color=MUTED,
                             align="ctr")]),
           sldnum_ph(ids)]
    return sh


GL_TABLE = [["Module", "Base address", "Size"],
            ["Memory A", "`0x0000_0000`", "16 KB"],
            ["Memory B", "`0x0001_0000`", "64 KB"],
            ["IP registers", "`0x0002_0000`", "256 B"]]


def s_global_practice(ids):
    return [title_ph(ids, "Global and Local Addresses"), pill(ids, "PRACTICE"),
            textbox(ids, 1.2, 1.8, 6.7, 4.35, [
                para("A processor bus uses 32-bit byte addresses. Three modules share it, each occupying "
                     "a contiguous range of the global address space that starts at its base address.",
                     sz=16, color=TEXT, spcAft=4),
                part("(a)", "What global address does the processor use to access word 100 of Memory B?", 16),
                part("(b)", "The processor reads global address `0x0000_2A0C`. Which module responds? "
                            "What is the local byte address, and which local word is it?", 16),
                part("(c)", "What is the highest global address that belongs to Memory B? How many bits "
                            "does Memory B need for its local byte address?", 16)]),
            table(ids, 8.2, 1.9, [1.35, 1.65, 0.95], GL_TABLE, rowh=0.4, sz=13),
            textbox(ids, 8.2, 3.75, 3.95, 1.6, [
                para("Both memories store 32-bit words.", sz=13, color=TEXT),
                para("1 KB = 1024 bytes.", sz=13, color=TEXT, spcAft=6),
                para("**Local address**: offset from the module's base address", sz=13, color=TEXT, spcAft=6),
                para("**Global address** = base + local address", sz=13, color=TEXT)]),
            portal_caption(ids, "Global and local addresses"), sldnum_ph(ids)]


def s_global_solution(ids):
    sh = [title_ph(ids, "Global and Local Addresses"), pill(ids, "SOLUTION"),
          textbox(ids, 1.2, 1.8, 6.9, 4.35, [
              part("(a)", "Word 100 → local byte 100 × 4 = 400 = `0x190`", 16),
              cont("Global: `0x0001_0000` + `0x190` = !!`0x0001_0190`!!", 16),
              part("(b)", "Memory A spans `0x0000_0000`–`0x0000_3FFF` (16 KB = `0x4000`)", 16),
              cont("`0x2A0C` falls inside → !!Memory A!!, local byte !!`0x2A0C`!! (10764)", 16),
              cont("Local word = `0x2A0C` / 4 = !!`0xA83` = 2691!!", 16),
              part("(c)", "64 KB = `0x1_0000` bytes → B ends at !!`0x0001_FFFF`!!", 16),
              cont("Local byte addresses `0x0000`–`0xFFFF` → !!16 bits!!", 16)]),
          shape(ids, 10.0, 1.95, 2.2, 1.05, fill=TINT, line=TINT2,
                paras=[para("Memory A · 16 KB", sz=13, color=DEEP, b=True, align="ctr"),
                       para("`0x2A0C` is here", sz=11, color=TEAL, align="ctr")]),
          shape(ids, 10.0, 3.25, 2.2, 1.4, fill=TEALTINT, line=TEALLINE,
                paras=[para("Memory B · 64 KB", sz=13, color=DEEP, b=True, align="ctr"),
                       para("word 100 at local `0x190`", sz=11, color=TEAL, align="ctr")]),
          shape(ids, 10.0, 4.9, 2.2, 0.5, fill=TINT, line=TINT2,
                paras=[para("IP registers · 256 B", sz=12, color=DEEP, b=True, align="ctr")])]
    for y, addr in ((1.95, "0x0000_0000"), (2.72, "0x0000_3FFF"), (3.25, "0x0001_0000"),
                    (4.37, "0x0001_FFFF"), (4.9, "0x0002_0000")):
        sh.append(label(ids, 8.15, y, 1.78, 0.28, f"`{addr}`", sz=11, color=DEEP, align="r"))
    sh += [portal_caption(ids, "Global and local addresses"), sldnum_ph(ids)]
    return sh


def s_register_maps(ids):
    sh = [title_ph(ids, "Register Maps"),
          body_ph(ids, 1.2, 1.75, 5.75, 4.6, [
              para("**Register map**: where each field lives"),
              para("Offset from the IP's base, name, field bits, access", lvl=1),
              para("For now: no field spans two registers"),
              para("Each field fits inside one 32-bit register", lvl=1),
              para("Tight packing comes later, with serialization", lvl=1),
              para("Unused upper bits are **zero padding**"),
              para("Read back as 0; ignored by the hardware", lvl=1),
          ], sz1=20, sz2=17),
          label(ids, 7.3, 1.78, 4.9, 0.3, "Example: a vector-scaling IP"),
          table(ids, 7.3, 2.1, [0.95, 1.1, 1.85, 1.0], [
              ["Offset", "Register", "Field bits", "Access"],
              ["`0x00`", "`CTRL`", "start [0], done [1]", "R/W"],
              ["`0x04`", "`GAIN`", "7:0", "R/W"],
              ["`0x08`", "`LEN`", "9:0", "R/W"],
              ["`0x0C`", "`SUM`", "23:0", "R"]], rowh=0.4, sz=13),
          label(ids, 7.3, 4.45, 4.9, 0.28, "The `LEN` register: 32 bits")]
    sh += field_bar(ids, 7.3, 4.78, 0.6, [
        (3.4, GRAYFILL, MUTED, [("zero padding", 13, False), ("22 bits", 11, False)]),
        (1.5, TINT, VIOLET, [("LEN", 13, True), ("10 bits", 11, False)])])
    # The field boundary is at x = 10.7; keep 10 and 9 visibly on either side of it.
    sh += [label(ids, 7.3, 5.42, 0.5, 0.25, "`31`", sz=11),
           label(ids, 10.07, 5.42, 0.5, 0.25, "`10`", sz=11, align="r"),
           label(ids, 10.8, 5.42, 0.5, 0.25, "`9`", sz=11),
           label(ids, 11.7, 5.42, 0.5, 0.25, "`0`", sz=11, align="r"),
           sldnum_ph(ids)]
    return sh


REGS = ["CTRL", "a0", "a1", "a2", "a3", "n"]


def s_register_practice(ids):
    blank = [["Offset", "Register", "Field bits", "Padding"]] + [["", f"`{r}`", "", ""] for r in REGS]
    return [title_ph(ids, "Register Map of the Cubic IP"), pill(ids, "PRACTICE"),
            textbox(ids, 1.2, 1.8, 6.35, 4.35, [
                para("The cubic IP computes $𝑦[𝑖] = 𝑎₀ + 𝑎₁𝑥[𝑖] + 𝑎₂𝑥[𝑖]² + 𝑎₃𝑥[𝑖]³$ over a "
                     "vector of length $𝑛$. Its registers hold:", sz=15, color=TEXT, spcAft=2),
                bullet_item("`start`, `done`: 1 bit each, sharing `CTRL` (start = bit 0, done = bit 1)", 15),
                bullet_item("`a0`–`a3`: 16-bit signed coefficients", 15),
                bullet_item("`n`: 12-bit unsigned vector length", 15),
                part("(a)", "Write the register map: offset, field(s) and zero-padding bits for each register.", 15),
                part("(b)", "The IP is mapped at base `0x4000_0000`. What global address does the processor "
                            "write to set `a2`?", 15),
                part("(c)", "The processor writes $𝑎₂$ = −3. What 32-bit value reads back, in hex? What "
                            "number does code get if it treats that as a signed 32-bit integer?", 15)]),
            shape(ids, 7.85, 1.85, 4.35, 1.15, fill=TINT, prst="roundRect", adj=8000, anchor="t", inset=0.14,
                  paras=[para("**Layout rules**", sz=13, spcAft=3),
                         para("32-bit registers, one field each (`CTRL` holds both bits)", sz=12, color=TEXT),
                         para("Fields in the low bits, zero padding above", sz=12, color=TEXT),
                         para("Order from `0x00`: `CTRL`, `a0`, `a1`, `a2`, `a3`, `n`", sz=12, color=TEXT)]),
            table(ids, 7.85, 3.2, [1.0, 1.15, 1.2, 1.0], blank, rowh=0.33, sz=13),
            portal_caption(ids, "Register map"), sldnum_ph(ids)]


def s_register_solution(ids):
    filled = [["Offset", "Register", "Field bits", "Padding"],
              ["`0x00`", "`CTRL`", "start [0], done [1]", "30"],
              ["`0x04`", "`a0`", "15:0", "16"],
              ["`0x08`", "`a1`", "15:0", "16"],
              ["`0x0C`", "`a2`", "15:0", "16"],
              ["`0x10`", "`a3`", "15:0", "16"],
              ["`0x14`", "`n`", "11:0", "20"]]
    sh = [title_ph(ids, "Register Map of the Cubic IP"), pill(ids, "SOLUTION"),
          textbox(ids, 1.2, 1.8, 5.9, 3.0, [
              part("(a)", "See the table: registers sit 4 bytes apart", 16),
              part("(b)", "`0x4000_0000` + `0x0C` = !!`0x4000_000C`!!", 16),
              part("(c)", "−3 in 16-bit two's complement is `0xFFFD`", 16),
              cont("Zero padding → reads back as !!`0x0000_FFFD`!!", 16),
              cont("As a signed 32-bit integer: !!65533!!, not −3", 16)]),
          shape(ids, 1.2, 4.95, 5.9, 1.05, fill=AMBERTINT, prst="roundRect", adj=10000, inset=0.16,
                paras=[para("^^Watch out:^^ zero padding does not sign-extend.", sz=14, color=TEXT),
                       para("Software must sign-extend a padded signed field itself.", sz=14, color=TEXT)]),
          table(ids, 7.3, 1.9, [0.9, 1.0, 1.95, 1.05], filled, rowh=0.36, sz=13),
          label(ids, 7.3, 4.7, 4.9, 0.28, "The `a2` register after writing −3")]
    sh += field_bar(ids, 7.3, 5.0, 0.62, [
        (2.45, GRAYFILL, MUTED, [("`0000 0000 0000 0000`", 12, False), ("bits 31–16: padding", 10, False)]),
        (2.45, TINT, VIOLET, [("`1111 1111 1111 1101`", 12, True), ("bits 15–0: −3", 10, False)])])
    sh += [portal_caption(ids, "Register map"), sldnum_ph(ids)]
    return sh


# ======================================================= rebuilt slides ====
def s_video(ids):
    sh = [title_ph(ids, "Example: Video"),
          body_ph(ids, 1.2, 1.75, 7.1, 4.6, [
              para("A video processor stores 8 frames of raw video"),
              para("512 × 512 pixels, 3 color channels, 8 bits per channel", lvl=1),
              para("Memory capacity"),
              para("$𝐵$ = 512 × 512 × 3 × 8 bytes = 3·2^{21} bytes ≈ **6.3 MB**", lvl=1),
              para("A sizeable portion of memory, even on a large chip", lvl=1),
              para("Stored as 32-bit words"),
              para("$𝑁$ = $𝐵$/4 = 3·2^{19} ≈ 1.57 M words", lvl=1),
              para("Address bits: the smallest K with 2^{K} ≥ the count"),
              para("Byte addressing: 2^{K} ≥ 3·2^{21} → **K = 23**", lvl=1),
              para("Word addressing: 2^{K} ≥ 3·2^{19} → **K = 21**", lvl=1),
          ], sz1=18, sz2=16)]
    for k in range(8):
        front = k == 7
        sh.append(shape(ids, 8.75 + k * 0.09, 1.95 + k * 0.09, 2.4, 1.45, fill=TINT, line=TINT2, lw=0.75,
                        paras=[para("512 × 512 × 3", sz=15, color=DEEP, b=True, align="ctr"),
                               para("one frame", sz=11, color=MUTED, align="ctr")] if front else ()))
    sh += [label(ids, 8.75, 4.1, 3.05, 0.3, "8 frames", align="ctr"),
           label(ids, 8.75, 4.55, 1.75, 0.65, "**6.3 MB**", sz=30),
           label(ids, 8.75, 5.2, 1.75, 0.3, "capacity"),
           label(ids, 10.55, 4.55, 1.75, 0.65, "!!23 bits!!", sz=30),
           label(ids, 10.55, 5.2, 1.75, 0.3, "byte address"),
           sldnum_ph(ids)]
    return sh


def s_objectives(ids):
    """The unit's learning objectives are exactly its skills, from skills.xml."""
    rows = [["Skill", "You will be able to"],
            ["Size memory for a data stream",
             "Compute data rate, capacity and the number of memories, and choose registers, "
             "block memory or external memory"],
            ["Compute memory addresses",
             "Convert between word and byte addresses, split a global address into a local one, "
             "and lay out a register map"],
            ["Identify bus master and slave",
             "Say which party initiates a transaction, whichever way the data flows"],
            ["Time a valid/ready handshake",
             "Work out the cycle a transfer happens on, including when the receiver is busy"],
            ["Analyze AXI4-Lite transactions",
             "Time reads and writes across the AW, W, B, AR and R channels"],
            ["Build an IP with AXI4-Lite registers",
             "Write the Vitis HLS signature and s_axilite pragmas, and state the registers they "
             "produce"],
            ["Determine the limiting resource",
             "Compare the time spent moving data against the time spent computing"]]
    return [title_ph(ids, "Learning Objectives"),
            table(ids, 1.2, 1.8, [3.9, 7.1], rows, rowh=0.5, sz=15),
            label(ids, 1.2, 5.95, 9.0, 0.3,
                  "Each skill is assessed by problems in the LLM grader.", sz=12),
            sldnum_ph(ids)]


COMPARE_ROWS = [["Feature", "Internal memory (SRAM)", "External memory (DRAM)"],
                ["Location", "On-chip", "Off-chip"],
                ["Storage cell", "6-T cell (cross-coupled inverters)", "Capacitor + access transistor"],
                ["Density", "Low", "High"],
                ["Capacity", "Small (KB–MB)", "Large (GB)"],
                ["Speed", "Very fast", "Slower"],
                ["Power", "Higher static", "Lower static, higher dynamic"],
                ["Access", "Direct by logic", "Through a memory controller"],
                ["Refresh", "No", "Yes"]]


def compare_table(ids):
    # Same footprint as the screenshot it replaces, so the cell images still fit.
    return table(ids, 1.07, 1.62, [1.6, 3.0, 2.8], COMPARE_ROWS, rowh=0.45, sz=14)


def s_onchip(ids):
    rows = [["Platform", "On-chip memory", "Typical size", "Notes"],
            ["Laptop CPU (Intel Core)", "SRAM (L1/L2/L3)", "20–40 MB", "L3 dominates; very fast"],
            ["NVIDIA A100 GPU", "SRAM (L2 cache)", "~40 MB", "HBM2e (40–80 GB) is off-chip, on-package"],
            ["Xilinx Virtex-7 FPGA", "BRAM (36 Kb blocks)", "2–6 MB", "Distributed across the fabric"],
            ["Custom ASIC (5 mm², 16 nm)", "SRAM", "5–10 MB", "Depends on layout and redundancy"]]
    return [title_ph(ids, "Example On-Chip Memory Sizes"),
            table(ids, 1.2, 1.95, [2.8, 2.3, 1.5, 4.4], rows, rowh=0.52, sz=16),
            shape(ids, 3.2, 4.95, 7.0, 0.8, fill=TINT, prst="roundRect", adj=30000,
                  paras=[para("Lesson: internal memory is limited. Use it judiciously.",
                              sz=20, color=VIOLET, b=True, align="ctr")]),
            label(ids, 1.2, 5.95, 11.0, 0.4,
                  "A 16 nm 6-T high-density bitcell is about 0.07 µm² (TSMC 128 Mb SRAM, ISSCC 2014), "
                  "so 5 mm² of bitcells holds ≈ 70 Mbit — roughly 5–7 MB once decoders and sense "
                  "amplifiers are counted.", sz=11),
            sldnum_ph(ids)]


# ====================================================== redrawn figures ====
#
# The hand-drawn figures are replaced with ones built from the same helpers as
# the new slides, so the whole section shares a vocabulary: violet for storage,
# slate blue for address and control, teal for data, a selected row in solid
# violet.  Each function returns the shapes for one slide's figure; the slide's
# title and body text are left alone.

def cell_stack(ids, x, y, w, h, labels, fill=TINT, sz=13, selected=None, gap=0.0):
    """A column of memory cells, optionally with one row highlighted."""
    out = []
    for k, lab in enumerate(labels):
        on = selected == k
        out.append(shape(ids, x, y + k * (h + gap), w, h,
                         fill=VIOLET if on else fill, line=TINT2, lw=0.75,
                         paras=[para(lab, sz=sz, color=WHITE if on else DEEP, align="ctr")]))
    return out


def fig_addressable_memory(ids):
    rows = [["Byte address", "Data"],
            ["`0`", "Word 0"], ["`4`", "Word 1"], ["`8`", "Word 2"],
            ["⋮", "⋮"], ["`4(𝑁−1)`", "Word $𝑁−1$"]]
    return [table(ids, 8.05, 2.15, [1.6, 2.5], rows, rowh=0.44, sz=14),
            label(ids, 8.05, 5.0, 4.1, 0.3, "A 32-bit memory, $𝑁$ words deep", align="ctr")]


def fig_ram_architecture(ids):
    # Everything stays left of x = 7.5: the body text of this slide is the
    # right-hand column.
    top, ch, n = 2.5, 0.56, 5
    sh = [textbox(ids, 1.2, 3.4, 1.45, 0.8,
                  [para("Address input", sz=13, color=SLATE, b=True, align="ctr"),
                   para("log₂($𝑁$) bits", sz=12, color=MUTED, align="ctr")]),
          arrow(ids, 2.6, 3.8, 3.0, 3.8, SLATE),
          shape(ids, 3.0, 3.35, 1.25, 0.9, fill=SLATETINT, line=SLATELINE,
                paras=[para("Address", sz=13, color=SLATE, b=True, align="ctr"),
                       para("decoder", sz=13, color=SLATE, b=True, align="ctr")]),
          label(ids, 4.5, 2.05, 1.9, 0.3, "$𝑁$ data words", sz=13, align="ctr"),
          label(ids, 6.3, 2.05, 1.2, 0.3, "Data bus", sz=13, color=TEAL, align="ctr")]
    sh += cell_stack(ids, 4.5, top, 1.9, ch, ["", "", "selected word", "", ""], selected=2, sz=12)
    sh.append(shape(ids, 6.6, top, 0.6, n * ch, fill=TEALTINT, line=TEALLINE))
    for k in range(n):
        y = top + ch / 2 + k * ch
        sh.append(arrow(ids, 4.3, y, 4.45, y, SLATE, lw=1.0))            # wordline select
        sh.append(arrow(ids, 6.65, y, 6.45, y, TEAL, lw=1.0, head=False))
    sh += [label(ids, 4.5, top + n * ch + 0.12, 1.9, 0.3, "one row per word", sz=12, align="ctr"),
           label(ids, 6.3, top + n * ch + 0.12, 1.2, 0.3, "R/W", sz=12, color=TEXT, align="ctr")]
    return sh


def bus_with_units(ids, bx, by, bh, unit_x, unit_w, units, label_y):
    """A vertical bus bar with boxes hanging off it."""
    out = [shape(ids, bx, by, 0.4, bh, fill=VIOLET),
           label(ids, bx - 0.35, label_y, 1.1, 0.3, "Bus", sz=14, color=VIOLET, b=True, align="ctr")]
    for k, name in enumerate(units):
        y = by + 0.25 + k * ((bh - 0.9) / max(len(units) - 1, 1))
        out.append(shape(ids, unit_x, y, unit_w, 0.62, fill=TINT, line=TINT2,
                         paras=[para(name, sz=14, color=DEEP, align="ctr")]))
        out.append(arrow(ids, bx + 0.4, y + 0.31, unit_x, y + 0.31, TEAL, lw=1.25))
    return out


def fig_bus(ids):
    return bus_with_units(ids, 8.9, 2.3, 3.3, 10.2, 1.9, ["Unit A", "Unit B", "Unit C"], 1.9) + [
        label(ids, 8.3, 5.85, 4.0, 0.3, "One unit drives the bus at a time", sz=12, align="ctr")]


def fig_high_z(ids):
    # Kept right of x = 10.3: the tri-state table on this slide renders wider
    # than its stored width, and reaches about 9.7 inches.
    return bus_with_units(ids, 10.4, 2.2, 2.4, 11.3, 0.95, ["A", "B", "C"], 1.82)


def fig_high_z_data_bus(ids):
    sh = [label(ids, 1.6, 1.95, 1.9, 0.3, "$𝑁$ data words", sz=13, align="ctr"),
          label(ids, 3.75, 1.95, 1.05, 0.3, "Data bus", sz=13, color=TEAL, align="ctr")]
    sh += cell_stack(ids, 1.6, 2.35, 1.9, 0.45, ["", "", "drives the bus", "", ""], selected=2, sz=12)
    sh.append(shape(ids, 3.95, 2.35, 0.65, 2.25, fill=TEALTINT, line=TEALLINE))
    for k in range(5):
        y = 2.55 + k * 0.45
        sh.append(arrow(ids, 3.55, y, 3.9, y, TEAL if k == 2 else GRAYLINE, lw=1.25, head=(k == 2)))
    sh += [label(ids, 1.6, 4.7, 1.9, 0.3, "others go to $𝑍$", sz=12, align="ctr"),
           label(ids, 3.75, 4.7, 1.05, 0.3, "R/W", sz=12, color=TEXT, align="ctr")]
    return sh


def s_external_internal(ids):
    """Rebuilt whole: this slide's content was all loose text boxes."""
    return [title_ph(ids, "External vs. Internal Memory"),
            shape(ids, 1.4, 2.5, 2.9, 1.5, fill=TINT, line=TINT2,
                  paras=[para("External memory", sz=16, color=DEEP, b=True, align="ctr"),
                         para("DRAM", sz=12, color=MUTED, align="ctr")]),
            textbox(ids, 1.4, 4.2, 2.9, 1.5, [
                bullet_item("Off-chip", 14),
                bullet_item("High capacity (GB)", 14),
                bullet_item("Reached over an I/O interface", 14)]),
            arrow(ids, 4.5, 3.25, 5.9, 3.25, SLATE, lw=2.0),
            label(ids, 4.4, 2.85, 1.6, 0.3, "I/O", sz=13, color=SLATE, b=True, align="ctr"),
            shape(ids, 6.0, 2.1, 5.3, 2.35, fill="FBFAFC", line=TINT2,
                  paras=[para("", sz=10)], anchor="t"),
            label(ids, 6.15, 2.2, 2.0, 0.3, "One chip", sz=12),
            shape(ids, 6.35, 2.65, 2.2, 1.5, fill=SLATETINT, line=SLATELINE,
                  paras=[para("Internal memory", sz=15, color=SLATE, b=True, align="ctr"),
                         para("SRAM, BRAM", sz=12, color=MUTED, align="ctr")]),
            shape(ids, 8.85, 2.65, 2.2, 1.5, fill=TEALTINT, line=TEALLINE,
                  paras=[para("Processing", sz=15, color=TEAL, b=True, align="ctr"),
                         para("hardware", sz=15, color=TEAL, b=True, align="ctr")]),
            arrow(ids, 8.6, 3.4, 8.8, 3.4, TEAL, lw=2.0),
            textbox(ids, 6.35, 4.6, 4.7, 1.5, [
                bullet_item("On-chip", 14),
                bullet_item("Low capacity (KB–MB)", 14),
                bullet_item("Direct, low-latency access from the datapath", 14)]),
            sldnum_ph(ids)]


def s_registers_vs_bulk(ids):
    """Replaces 'Registers vs. Block Memory': the choice is per value, and the
    criterion is stated rather than implied."""
    reg = [para("**Registers**", sz=19, align="ctr", spcAft=6),
           bullet_item("Parallel access: many values in the same cycle", 14),
           bullet_item("Any register value is available to the datapath", 14),
           bullet_item("Higher area per bit", 14),
           bullet_item("A host reads and writes them one at a time", 14)]
    bulk = [para("**Bulk storage**", sz=19, align="ctr", spcAft=6),
            bullet_item("Typically one word per access", 14),
            bullet_item("Much higher density", 14),
            bullet_item("A host moves data to and from it in bulk", 14),
            bullet_item("Block RAM on chip, DRAM off chip", 14)]
    return [title_ph(ids, "Registers vs. Bulk Storage"),
            label(ids, 1.2, 1.78, 11.0, 0.35,
                  "Every IP holds a mix. The choice is made per value, not per design.",
                  sz=17, color=TEXT),
            shape(ids, 1.2, 2.3, 5.3, 2.75, fill=TINT, line=TINT2, prst="roundRect", adj=6000,
                  anchor="t", inset=0.18, paras=reg),
            shape(ids, 6.9, 2.3, 5.3, 2.75, fill=SLATETINT, line=SLATELINE, prst="roundRect",
                  adj=6000, anchor="t", inset=0.18, paras=bulk),
            shape(ids, 1.2, 5.35, 11.0, 0.8, fill=BAND, line=TINT2, prst="roundRect", adj=20000,
                  paras=[para("A few values needed at once → **registers**.     "
                              "Thousands touched one at a time → **bulk storage**.",
                              sz=17, color=TEXT, align="ctr")]),
            sldnum_ph(ids)]


def fig_memory_mapped(ids):
    sh = [shape(ids, 7.9, 2.2, 0.4, 3.3, fill=TEALTINT, line=TEALLINE),
          label(ids, 7.35, 1.85, 1.5, 0.3, "Data bus", sz=12, color=TEAL, align="ctr"),
          shape(ids, 8.95, 2.2, 0.4, 3.3, fill=SLATETINT, line=SLATELINE),
          label(ids, 8.55, 1.85, 1.8, 0.3, "Address bus", sz=12, color=SLATE, align="ctr")]
    for y, name, fill, line, colour in ((2.45, "Registers", SLATETINT, SLATELINE, SLATE),
                                        (4.15, "Block memory", TINT, TINT2, VIOLET)):
        sh += [shape(ids, 9.75, y + 0.1, 0.95, 0.6, fill=SLATETINT, line=SLATELINE,
                     paras=[para("decoder", sz=11, color=SLATE, align="ctr")]),
               arrow(ids, 9.35, y + 0.4, 9.7, y + 0.4, SLATE, lw=1.25),
               arrow(ids, 10.7, y + 0.4, 11.0, y + 0.4, SLATE, lw=1.25),
               arrow(ids, 8.3, y + 1.05, 11.0, y + 1.05, TEAL, lw=1.25, head=False),
               label(ids, 11.0, y - 0.3, 1.3, 0.3, name, sz=13, color=colour, b=True, align="ctr")]
        sh += cell_stack(ids, 11.0, y, 1.2, 0.3, ["", "", ""], fill=fill, sz=10)
    return sh


def fig_cubic_ip(ids):
    sh = [label(ids, 10.3, 1.85, 1.8, 0.3, "Registers", sz=13, color=SLATE, b=True, align="ctr")]
    sh += cell_stack(ids, 10.3, 2.2, 1.8, 0.4,
                     ["$𝑎[0]$", "$𝑎[1]$", "$𝑎[2]$", "$𝑎[3]$"], fill=SLATETINT, sz=13)
    for x, name in ((8.7, "𝑥"), (10.5, "𝑦")):
        sh += cell_stack(ids, x, 4.3, 1.6, 0.4,
                         [f"${name}[0]$", f"${name}[1]$", "⋮", f"${name}[𝑛−1]$"], sz=13)
    sh.append(label(ids, 8.7, 6.0, 3.4, 0.3, "Block memory", sz=13, color=VIOLET, b=True, align="ctr"))
    return sh


def s_inclass_exercise(ids):
    return [title_ph(ids, "Where Does Each Value Live?"), pill(ids, "IN CLASS"),
            textbox(ids, 1.2, 1.8, 6.9, 4.4, [
                para("Pick a computation that interests you: filtering in video processing, "
                     "encryption, a neural-network layer, a matrix product. It must take at "
                     "least one array, image or stream.", sz=17, color=TEXT, spcAft=6),
                part("(a)", "List the inputs and outputs, with a size or a rate for each.", 17),
                part("(b)", "Which would you hold in **registers**? Why?", 17),
                part("(c)", "Which would you hold in **bulk storage**? Why?", 17),
                part("(d)", "Choose a problem size. Give the register map, and the size of the "
                            "bulk storage in words.", 17)]),
            shape(ids, 8.4, 1.85, 3.8, 1.75, fill=TINT, prst="roundRect", adj=8000, anchor="t",
                  inset=0.16, paras=[
                      para("**Decide per value**", sz=15, spcAft=6),
                      para("Registers: parallel access, available to the datapath, higher area "
                           "per bit", sz=13, color=TEXT, spcAft=5),
                      para("Bulk storage: one word per access, much higher density", sz=13,
                           color=TEXT)]),
            label(ids, 8.4, 3.85, 3.8, 0.9,
                  "How the data crosses into the IP is the next section, and units 5 and 9.",
                  sz=12),
            portal_caption(ids, "Storage partitioning"), sldnum_ph(ids)]


FIGURES = {
    "slide4.xml": fig_addressable_memory,
    "slide6.xml": fig_ram_architecture,
    "slide7.xml": fig_bus,
    "slide8.xml": fig_high_z,
    "slide9.xml": fig_high_z_data_bus,
    "slide15.xml": fig_memory_mapped,
    "slide16.xml": fig_cubic_ip,
}


def redraw_figure(slide, fn):
    """Drop the hand-drawn shapes and connectors, keep placeholders, tables and
    pictures, then add the new figure."""
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")
    t, n_sp = re.subn(r"<p:sp>(?:(?!</p:sp>).)*?</p:sp>",
                      lambda m: "" if "<p:ph" not in m.group(0) else m.group(0), t, flags=re.S)
    t, n_cx = re.subn(r"<p:cxnSp>.*?</p:cxnSp>", "", t, flags=re.S)
    t = t.replace("</p:spTree>", "".join(fn(Ids())) + "</p:spTree>")
    p.write_text(t, encoding="utf-8")
    return n_sp, n_cx


# ================================================================ passes ====
def sh(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit(f"FAILED: {' '.join(map(str, cmd))}\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


def add_after(src_slide, after_slide):
    out = sh([sys.executable, "add_slide.py", str(BUILD), src_slide, "--after", after_slide], cwd=SCRIPTS)
    m = re.search(r"(slide\d+\.xml)", out.split("Created", 1)[1]) if "Created" in out else None
    if not m:
        raise SystemExit(f"could not parse add_slide output:\n{out}")
    return m.group(1)


def fix(slide, old, new):
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")
    n = t.count(old)
    assert n == 1, f"{slide}: expected 1 of {old!r}, found {n}"
    p.write_text(t.replace(old, new), encoding="utf-8")


def fix_all(slide, old, new):
    """Slides carrying equations store the body twice, as the math version and
    a fallback copy, so body text has to be replaced in both."""
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")
    assert old in t, f"{slide}: {old!r} not found"
    p.write_text(t.replace(old, new), encoding="utf-8")


# The old theme's purples, used for highlighted terms.  Blue (registers) and
# green (data buses) are left alone: in the diagrams those colours mean something.
HIGHLIGHT_OLD = [
    '<a:schemeClr val="accent1"><a:lumMod val="60000"/><a:lumOff val="40000"/></a:schemeClr>',
    '<a:schemeClr val="accent1"/>',
    '<a:schemeClr val="tx2"><a:lumMod val="60000"/><a:lumOff val="40000"/></a:schemeClr>',
    '<a:schemeClr val="accent2"><a:lumMod val="75000"/></a:schemeClr>',
]


def restyle(slide):
    """New bullets on the body placeholder, NYU violet for highlighted text runs."""
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")
    n_bul = 0

    def body(m):
        nonlocal n_bul
        spx = m.group(0)
        if re.search(r'<p:ph[^>]*idx="1"', spx) and "type=" not in re.search(r"<p:ph[^>]*>", spx).group(0):
            spx, k = re.subn(r"<a:lstStyle/>|<a:lstStyle>.*?</a:lstStyle>",
                             lst_style(None, None, margins=True, spacing=False), spx, count=1, flags=re.S)
            n_bul += k
        return spx

    t = re.sub(r"<p:sp>.*?</p:sp>", body, t, flags=re.S)
    n_col = 0

    def recolor(m):
        nonlocal n_col
        x = m.group(0)
        for old in HIGHLIGHT_OLD:
            if old in x:
                n_col += 1
                x = x.replace(old, f'<a:srgbClr val="{VIOLET}"/>')
        return x

    t = re.sub(r"<a:rPr\b[^>]*>.*?</a:rPr>", recolor, t, flags=re.S)
    p.write_text(t, encoding="utf-8")
    return n_bul, n_col


def recolour_diagrams(slide):
    """Recolour hand-drawn shapes and their labels; leave geometry alone."""
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")
    n = 0
    fills = dict(DIAGRAM_FILLS, **DIAGRAM_OVERRIDES.get(slide, {}))
    texts = dict(DIAGRAM_TEXT, **{k: v for k, v in DIAGRAM_OVERRIDES.get(slide, {}).items()
                                  if k in DIAGRAM_TEXT})

    def in_spPr(m):
        nonlocal n
        x = m.group(0)
        for old, new in fills.items():
            if old in x:
                n += x.count(old)
                x = x.replace(old, f'<a:srgbClr val="{new}"/>')
        return x

    def in_rPr(m):
        nonlocal n
        x = m.group(0)
        for old, new in texts.items():
            if old in x:
                n += x.count(old)
                x = x.replace(old, f'<a:srgbClr val="{new}"/>')
        return x

    t = re.sub(r"<p:spPr>.*?</p:spPr>", in_spPr, t, flags=re.S)
    t = re.sub(r"<a:rPr\b[^>]*>.*?</a:rPr>", in_rPr, t, flags=re.S)
    p.write_text(t, encoding="utf-8")
    return n


def retheme_accent1():
    """The theme's magenta accent drives every style-driven shape and table
    header in the deck.  Point it at NYU violet, which the footer band already
    uses, instead of recolouring each shape."""
    p = BUILD / "ppt" / "theme" / "theme1.xml"
    t = p.read_text(encoding="utf-8")
    t, k = re.subn(r'(<a:accent1>\s*<a:srgbClr val=")92278F("/>)', rf"\g<1>{VIOLET}\g<2>", t, count=1)
    assert k == 1, "theme accent1 not found"
    p.write_text(t, encoding="utf-8")


def drop_unused_rels(slide):
    """Remove image relationships a rebuilt slide no longer references."""
    xml = (SLIDES / slide).read_text(encoding="utf-8")
    relp = SLIDES / "_rels" / f"{slide}.rels"
    rels = relp.read_text(encoding="utf-8")
    for rid, target in re.findall(r'<Relationship Id="(rId\d+)"[^>]*Target="([^"]+)"', rels):
        if "media" in target and f'r:embed="{rid}"' not in xml and f'r:id="{rid}"' not in xml:
            rels = re.sub(rf'<Relationship Id="{rid}"[^>]*/>', "", rels)
    relp.write_text(rels, encoding="utf-8")


def write(slide, shapes):
    (SLIDES / slide).write_text(slide_doc(shapes), encoding="utf-8")


def pack():
    if OUT.exists():
        OUT.unlink()
    files = sorted(p for p in BUILD.rglob("*") if p.is_file())
    ct = BUILD / "[Content_Types].xml"
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ct, "[Content_Types].xml")
        for f in files:
            if f != ct:
                z.write(f, f.relative_to(BUILD).as_posix())


def main():
    if BUILD.exists():
        shutil.rmtree(BUILD)
    zipfile.ZipFile(SRC).extractall(BUILD)

    # 1. structure: every insertion before any content edit
    n1 = add_after("slide3.xml", "slide4.xml")
    n2 = add_after("slide3.xml", n1)
    n3 = add_after("slide3.xml", n2)
    n4 = add_after("slide3.xml", "slide7.xml")
    n5 = add_after("slide3.xml", n4)
    n6 = add_after("slide3.xml", n5)
    n7 = add_after("slide3.xml", "slide16.xml")
    n8 = add_after("slide3.xml", n7)
    n9 = add_after("slide3.xml", n8)
    n10 = add_after("slide3.xml", n9)          # the in-class exercise closes section 1
    print("new slides:", n1, n2, n3, n4, n5, n6, n7, n8, n9, n10)

    # 2. content
    for slide, fn in ((n1, s_byte_word), (n2, s_byte_word_practice), (n3, s_byte_word_solution),
                      (n4, s_address_map), (n5, s_global_practice), (n6, s_global_solution),
                      (n7, s_register_maps), (n8, s_register_practice), (n9, s_register_solution),
                      (n10, s_inclass_exercise),
                      ("slide2.xml", s_objectives), ("slide10.xml", s_external_internal),
                      ("slide12.xml", s_onchip), ("slide13.xml", s_video),
                      ("slide14.xml", s_registers_vs_bulk)):
        write(slide, fn(Ids()))

    # Slide 11: swap the screenshot of a table for a real one, keeping the
    # SRAM and DRAM cell images beside it.
    p11 = SLIDES / "slide11.xml"
    t11 = p11.read_text(encoding="utf-8")
    t11, k = re.subn(r'<p:pic>(?:(?!</p:pic>).)*?r:embed="rId2".*?</p:pic>', "", t11, flags=re.S)
    assert k == 1, f"slide11: expected 1 table screenshot, removed {k}"
    t11 = t11.replace("</p:spTree>", compare_table(Ids()) + "</p:spTree>")
    p11.write_text(t11, encoding="utf-8")

    for s in ("slide2.xml", "slide11.xml", "slide12.xml", "slide13.xml"):
        drop_unused_rels(s)

    # 3. restyle the untouched section-1 slides
    for s in ("slide4.xml", "slide5.xml", "slide6.xml", "slide7.xml", "slide8.xml", "slide9.xml",
              "slide10.xml", "slide11.xml", "slide14.xml", "slide15.xml", "slide16.xml"):
        b, c = restyle(s)
        print(f"restyle {s}: bullets {b}, highlighted runs {c}")

    # 3b. the hand-drawn diagrams, and the theme accent behind style-driven shapes
    retheme_accent1()
    total = 0
    for s in ("slide4.xml", "slide6.xml", "slide7.xml", "slide8.xml", "slide9.xml", "slide10.xml",
              "slide11.xml", "slide14.xml", "slide15.xml", "slide16.xml"):
        total += recolour_diagrams(s)
    print(f"diagram colours remapped: {total}")

    # 3c. redraw the hand-drawn figures in the same vocabulary as the new slides
    for s, fn in FIGURES.items():
        n_sp, n_cx = redraw_figure(s, fn)
        print(f"redraw {s}: dropped {n_sp} shapes, {n_cx} connectors")

    # 4. text fixes
    fix("slide4.xml", "Each of the data element", "Each data element")
    fix("slide7.xml", " so only unit drives the bus", " so only one unit drives the bus")
    fix("slide8.xml", ", noted ", ", denoted ")
    # A stray trailing tab after "denoted Z": harmless with the template's flush
    # bullets, but with real bullet margins it wraps to an empty line and pushes
    # the last bullet under the table.
    p8 = SLIDES / "slide8.xml"
    t8, n_tab = re.subn(r'<a:r><a:rPr lang="en-US" dirty="0"/><a:t>\t</a:t></a:r>(?=</a:p>)', "",
                        p8.read_text(encoding="utf-8"))
    assert n_tab >= 1, "slide8: stray tab run not found"
    p8.write_text(t8, encoding="utf-8")
    # The register-map practice problem says "the cubic IP from lecture"; name the slide it means.
    fix("slide16.xml", "<a:t>Example</a:t>", "<a:t>Example: The Cubic IP</a:t>")

    # Storage type and exposure are separate things, and this slide is about
    # exposure: it maps registers *and* block memory into one address space.
    fix_all("slide15.xml", "Memory Mapped Registers", "Memory-Mapped Storage")
    # "&" is stored escaped in the slide XML.
    fix_all("slide15.xml", "Processor sees registers &amp; block memory together",
            "Processor sees registers and block memory in one address space")
    fix_all("slide15.xml", "One continuous address space",
            "Being addressable is independent of what the storage is made of")

    # Say why each value sits where it does, rather than only where.
    fix_all("slide16.xml", "Small, individual pieces", "Four values, all needed in the same cycle")
    fix_all("slide16.xml", "Ideal for large vectors", "n values, only one touched per cycle")
    fix("slide17.xml", "Processor Interfaces with AXI-Lite", "Processor Interfaces with AXI4-Lite")
    fix("slide17.xml", "Implementing AXI-Lite Interface in Vitis<", "Implementing AXI4-Lite Interface in Vitis HLS<")

    # The write response was described backwards: the slave drives BVALID and the
    # master answers with BREADY, which is what the slide's own diagram shows and
    # what the AXI4-Lite Write problem's solution says.  Both the math copy of the
    # body and its fallback carry the text, so replace every occurrence.
    p21 = SLIDES / "slide21.xml"
    t21 = p21.read_text(encoding="utf-8")
    for old, new in (
        ("Handshake:", "Write response (B channel):"),
        ("After both are transferred, slave set BREADY=1",
         "After both transfers, the slave sets BVALID=1 with the write response"),
        ("Master sets BVALID=1 to acknowledge",
         "The master sets BREADY=1 to accept it; the response transfers when BVALID=BREADY=1"),
        ("Can start next transaction in same clock cycle as BVALID=1",
         "Each channel is free for the next transaction once its own handshake completes"),
    ):
        assert old in t21, f"slide21: {old!r} not found"
        t21 = t21.replace(old, new)
    p21.write_text(t21, encoding="utf-8")

    # 5. pack
    print(sh([sys.executable, "clean.py", str(BUILD)], cwd=SCRIPTS).strip())
    pack()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
