"""Rebuild unit 5's slide deck, fifo.pptx, in the style of unit 4's.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
A *one-shot migration*, like tools/build_procif_slides.py: it reads the
pre-revision fifo.pptx, applies a fixed list of edits and writes a new deck.
Once the result is edited in PowerPoint, this script is a record of what was
done, not a way to rebuild it, and it refuses to run on its own output.

WHAT IT DOES
------------
  * learning objectives: rebuilt as a table of the unit's skills, exactly the
    ones fifo.xml's rubric items are tagged with (skills.xml in hwdesign-soln)
  * practice problems: the seven in-class problems in hwdesign-soln
    .../unit05_fifo/prob/fifo.xml, each as a PRACTICE slide and a SOLUTION
    slide.  The three required problems stay homework, as in unit 4: they are
    named on the slide that teaches them, not solved.
  * new figures from units/unit05_fifo/figs/make_figs.py: the register vs.
    FIFO timeline, the load-factor and frame-backlog simulations, and the
    AXI4-Stream waveforms, which are simulated from each problem's rules
  * redrawn FIFO diagrams, and rebuilt slides for the command-response
    example, its messages, IDs and error codes, and field packing
  * the demo walkthroughs (old slides 30-33 and 57-64: kernel code, Vitis TCL,
    simulation screenshots, the xilinxutils code generator) are replaced by
    one pointer slide per demo.  docs/demos/stream and docs/demos/fifoif carry
    the walkthrough, with commands that run.
  * restyles the kept slides onto unit 4's NYU Violet palette, and points the
    theme's accent1 at NYU Violet
  * renames master and slave to transmitter and receiver, the AXI4-Stream
    spec's own terms, as unit 4 moved AXI4-Lite to manager and subordinate
  * fixes content errors: the course number, the truncated FIFO-location
    bullet, the TVALID rule (a transmitter may not drop TVALID before the
    transfer), "addressing" promised but never taught, output streams
    labelled "Input stream", the squared-average IP labelled "Polynomial
    Eval", the example timing table that was the solution to a required
    problem, and the out-of-date packet structures (the demo's messages are
    PolyCmdHdr, PolyRespHdr and PolyRespFtr)

USAGE
-----
From the repo root, with the deck closed in PowerPoint:

    ../hwdesign-venv/Scripts/python units/unit05_fifo/figs/make_figs.py
    python tools/build_fifo_slides.py --out units/unit05_fifo/fifo_v5.pptx

Validate and render (PowerPoint draws what the class sees):

    python <skill>/scripts/office/validate.py OUT --original units/unit05_fifo/fifo.pptx
    tools/render_slides.ps1 -Deck OUT -OutDir out
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

from PIL import Image        # only to read a figure's aspect ratio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _find_skill_scripts():
    """The pptx skill's scripts/ directory, looked for under ~/.claude/skills
    only: globbing the whole home directory takes minutes."""
    roots = sorted((Path.home() / ".claude" / "skills").glob("**/pptx/scripts"))
    if not roots:
        raise SystemExit("pptx skill scripts not found under ~/.claude/skills; "
                         "pass --skill-scripts")
    return roots[0]


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", type=Path, default=ROOT / "units/unit05_fifo/fifo.pptx")
    p.add_argument("--out", type=Path, default=ROOT / "units/unit05_fifo/fifo_v5.pptx")
    p.add_argument("--figs", type=Path, default=ROOT / "units/unit05_fifo/figs")
    p.add_argument("--work", type=Path, default=Path(tempfile.gettempdir()) / "fifo_build")
    p.add_argument("--skill-scripts", type=Path, default=None)
    p.add_argument("--force", action="store_true",
                   help="run even if the source deck looks already migrated")
    a = p.parse_args()
    a.skill_scripts = a.skill_scripts or _find_skill_scripts()
    return a


ARGS = None     # set in main(); the helpers below only read BUILD and FIGS
BUILD = SLIDES = FIGS = None

# ---------------------------------------------------------------- palette ---
# Unit 4's (tools/build_procif_slides.py), so the two decks read as one course.
VIOLET = "57068C"     # NYU violet: key terms, bullets, table headers, the IP
DEEP = "330662"       # code and values
TINT = "EEE6F3"       # FIFO cells, cards
TINT2 = "D5C4E3"      # borders
MIDV = "B08AD0"       # an occupied FIFO cell in the old diagrams
BAND = "F7F3FA"       # banded table rows
TEAL = "00857C"       # data that moves; answers
TEALTINT = "DCEFEC"
TEALLINE = "9FD3CC"
AMBER = "B4530F"      # stalls, errors, common-error callouts
AMBERTINT = "FCEEE3"
SLATE = "2F6FA8"      # the processor, control, headers
SLATETINT = "EAF0F7"
SLATELINE = "B9CCE0"
TEXT = "262626"
MUTED = "6E6E6E"
GRAYFILL = "EDEDED"
GRAYLINE = "BFBFBF"
CODEFILL = "F4F4F7"
WHITE = "FFFFFF"

EMU = 914400
CONTENT_TOP = 1.62          # below the title and its rule
L, R = 0.75, 12.55          # content margins, as in unit 4's section 3
W = R - L

DOCS_URL = "sdrangan.github.io/hwdesign"


def E(inches):
    return int(round(inches * EMU))


class Ids:
    def __init__(self):
        self.n = 1

    def __call__(self):
        self.n += 1
        return self.n


# ------------------------------------------------------------------- text ---
def rpr(sz=None, color=None, b=False, i=False, font=None, baseline=None, tag="a:rPr"):
    attrs = ['lang="en-US"']
    if sz:
        attrs.append(f'sz="{int(round(sz * 100))}"')
    if b:
        attrs.append('b="1"')
    if i:
        attrs.append('i="1"')
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
    keep = ' xml:space="preserve"' if text != text.strip() or "  " in text else ""
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


def para(markup="", sz=None, color=None, b=False, align=None, marL=None,
         indent=None, bullet=None, spcBef=None, spcAft=None, i=False):
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
    if spcAft is not None:
        kids += f'<a:spcAft><a:spcPts val="{int(spcAft * 100)}"/></a:spcAft>'
    if bullet == "none":
        kids += "<a:buNone/>"
    elif bullet:
        char, bclr, pct = bullet
        kids += (f'<a:buClr><a:srgbClr val="{bclr}"/></a:buClr><a:buSzPct val="{pct}"/>'
                 f'<a:buFont typeface="Arial"/><a:buChar char="{char}"/>')
    ppr = ""
    if attrs or kids:
        ppr = f'<a:pPr {" ".join(attrs)}>{kids}</a:pPr>' if attrs else f"<a:pPr>{kids}</a:pPr>"
    body = runs(markup, dict(sz=sz, color=color, b=b, i=i)) if markup else ""
    return f"<a:p>{ppr}{body}{rpr(sz=sz, tag='a:endParaRPr')}</a:p>"


def b1(text, sz=20, spcBef=12):
    """A level-1 body bullet: the violet square the restyled slides use."""
    return para(text, sz=sz, color=TEXT, marL=0.3, indent=-0.3,
                bullet=("■", VIOLET, 70000), spcBef=spcBef)


def b2(text, sz=17, spcBef=3):
    """A level-2 body bullet: the grey dash."""
    return para(text, sz=sz, color=TEXT, marL=0.68, indent=-0.25,
                bullet=("–", "999999", 100000), spcBef=spcBef)


def bullet(text, sz=15, color=TEXT, clr=VIOLET, spcBef=6):
    """A compact bullet for cards and side columns."""
    return para(text, sz=sz, color=color, marL=0.26, indent=-0.26,
                bullet=("▪", clr, 70000), spcBef=spcBef)


def part(label_, text, sz, spcBef=9):
    """A lettered part with a hanging indent: '(a)<tab>text'."""
    return para(f"**{label_}**\t{text}", sz=sz, color=TEXT, marL=0.45, indent=-0.45,
                spcBef=spcBef)


def cont(text, sz, color=TEXT, spcBef=2):
    """A continuation line aligned with the part text above it."""
    return para(text, sz=sz, color=color, marL=0.45, indent=0, spcBef=spcBef)


def code_lines(src, sz=12):
    """Monospace lines, leading spaces kept."""
    return [para(f"`{ln}`" if ln.strip() else "", sz=sz) for ln in src.strip("\n").split("\n")]


# ----------------------------------------------------------------- shapes ---
def title_ph(ids, text):
    i = ids()
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Title {i}"/><p:cNvSpPr><a:spLocks noGrp="1"/>'
            f'</p:cNvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/>'
            f"<p:txBody><a:bodyPr/><a:lstStyle/><a:p>{run(text)}</a:p></p:txBody></p:sp>")


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
    return textbox(ids, x, y, w, h, [para(text, sz=sz, color=color, align=align, b=b)],
                   anchor=anchor)


def heading(ids, x, y, w, text):
    """A small-caps style column heading, as on unit 4's demo slide."""
    return label(ids, x, y, w, 0.3, text, sz=12, color=MUTED, b=True)


def shape(ids, x, y, w, h, fill=None, line=None, lw=1.0, prst="rect", paras=(), anchor="ctr",
          inset=0.06, adj=None, dash=False):
    i = ids()
    gd = f'<a:gd name="adj" fmla="val {adj}"/>' if adj is not None else ""
    geom = f'<a:prstGeom prst="{prst}"><a:avLst>{gd}</a:avLst></a:prstGeom>'
    fillx = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
    dashx = '<a:prstDash val="dash"/>' if dash else ""
    linex = (f'<a:ln w="{int(lw * 12700)}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill>'
             f'{dashx}</a:ln>' if line else "<a:ln><a:noFill/></a:ln>")
    tx = list(paras) or [para("", sz=10)]
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Shape {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm>'
            f"{geom}{fillx}{linex}</p:spPr>"
            f'<p:txBody><a:bodyPr wrap="square" lIns="{E(inset)}" tIns="{E(inset / 2)}" '
            f'rIns="{E(inset)}" bIns="{E(inset / 2)}" anchor="{anchor}" rtlCol="0"><a:noAutofit/>'
            f'</a:bodyPr><a:lstStyle/>{"".join(tx)}</p:txBody></p:sp>')


def card(ids, x, y, w, h, paras, fill=TINT, line=None, inset=0.16, anchor="t", adj=8000):
    return shape(ids, x, y, w, h, fill=fill, line=line, prst="roundRect", adj=adj,
                 anchor=anchor, inset=inset, paras=paras)


def code_box(ids, x, y, w, h, src, sz=12, inset=0.16):
    return shape(ids, x, y, w, h, fill=CODEFILL, line=GRAYLINE, lw=0.75, anchor="t",
                 inset=inset, paras=code_lines(src, sz))


def table(ids, x, y, colw, rows, rowh=0.38, sz=14, header=True, head_fill=VIOLET):
    i = ids()

    def border(tag):
        return f'<a:{tag} w="9525"><a:solidFill><a:srgbClr val="{TINT2}"/></a:solidFill></a:{tag}>'

    heights = rowh if isinstance(rowh, (list, tuple)) else [rowh] * len(rows)
    trs = []
    for r, row in enumerate(rows):
        tcs = []
        for cell in row:
            cell = {"t": cell} if isinstance(cell, str) else cell
            head = header and r == 0
            fill = cell.get("fill") or (head_fill if head else (BAND if r % 2 else WHITE))
            color = cell.get("color") or (WHITE if head else TEXT)
            p = para(cell["t"], sz=cell.get("sz", sz), color=color, b=head or cell.get("b", False),
                     align=cell.get("align"))
            tcpr = (f'<a:tcPr marL="{E(0.08)}" marR="{E(0.06)}" marT="{E(0.03)}" marB="{E(0.03)}" '
                    f'anchor="ctr">{border("lnL")}{border("lnR")}{border("lnT")}{border("lnB")}'
                    f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr>')
            tcs.append(f"<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{p}</a:txBody>{tcpr}</a:tc>")
        trs.append(f'<a:tr h="{E(heights[r])}">{"".join(tcs)}</a:tr>')
    grid = "".join(f'<a:gridCol w="{E(c)}"/>' for c in colw)
    W_, H = sum(colw), sum(heights)
    return (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="Table {i}"/>'
            f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/>'
            f'</p:nvGraphicFramePr><p:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(W_)}" cy="{E(H)}"/>'
            f'</p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
            f'<a:tbl><a:tblPr firstRow="1" bandRow="1"><a:tableStyleId>{{2D5ABB26-0587-4C30-8999-92F81FD0307C}}'
            f'</a:tableStyleId></a:tblPr><a:tblGrid>{grid}</a:tblGrid>{"".join(trs)}</a:tbl>'
            f"</a:graphicData></a:graphic></p:graphicFrame>")


def arrow(ids, x1, y1, x2, y2, color, lw=1.5, head=True, dash=False):
    """A straight connector; a leftward or upward arrow is the same box flipped."""
    i = ids()
    x, y = min(x1, x2), min(y1, y2)
    w, h = abs(x2 - x1), abs(y2 - y1)
    flip = (' flipH="1"' if x2 < x1 else "") + (' flipV="1"' if y2 < y1 else "")
    tail = '<a:tailEnd type="triangle" w="med" len="med"/>' if head else ""
    dashx = '<a:prstDash val="dash"/>' if dash else ""
    return (f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{i}" name="Connector {i}"/><p:cNvCxnSpPr/>'
            f"<p:nvPr/></p:nvCxnSpPr>"
            f'<p:spPr><a:xfrm{flip}><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/>'
            f'</a:xfrm><a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>'
            f'<a:ln w="{int(lw * 12700)}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f"{dashx}{tail}</a:ln></p:spPr></p:cxnSp>")


def field_bar(ids, x, y, h, parts):
    """Adjacent labelled boxes: parts = [(width, fill, color, [(text, size, bold), ...]), ...]."""
    out, cx = [], x
    for w, fill, color, lines in parts:
        out.append(shape(ids, cx, y, w, h, fill=fill, line=TINT2, lw=0.75,
                         paras=[para(t, sz=s, color=color, b=bb, align="ctr") for t, s, bb in lines]))
        cx += w
    return out


def fifo_stack(ids, x, y, w, ch, labels, filled, sz=14):
    """A vertical FIFO: labels top to bottom, `filled` of them occupied, from the bottom."""
    out, n = [], len(labels)
    for k, lab in enumerate(labels):
        on = k >= n - filled
        out.append(shape(ids, x, y + k * ch, w, ch, fill=VIOLET if on else TINT, line=TINT2,
                         lw=0.75, paras=[para(lab, sz=sz, color=WHITE if on else DEEP, b=on,
                                              align="ctr")]))
    return out


def pill(ids, kind):
    fill = {"SOLUTION": TEAL, "IN CLASS": VIOLET, "PRACTICE": VIOLET}[kind]
    return shape(ids, 10.55, 0.68, 1.6, 0.42, fill=fill, prst="roundRect", adj=50000,
                 paras=[para(kind, sz=13, color=WHITE, b=True, align="ctr")])


def portal_caption(ids, qtag):
    return label(ids, L, 6.2, 9.0, 0.32, f"Also in the LLM grader: Unit 5 › {qtag}", sz=12)


# --------------------------------------------------------------- pictures ---
_PENDING = {}     # placeholder token -> figure file, resolved when the slide is written


def picture(ids, fig, x, y, w=None, h=None):
    """A generated figure.  Give w or h; the other follows the PNG's aspect ratio.

    The relationship id is not known until the slide is written, so the XML
    carries a token that write() swaps for a real rId."""
    path = FIGS / f"{fig}.png"
    if not path.exists():
        raise SystemExit(f"missing {path}: run units/unit05_fifo/figs/make_figs.py first")
    with Image.open(path) as im:
        aspect = im.width / im.height
    if w is None:
        w = h * aspect
    if h is None:
        h = w / aspect
    token = f"@@RID:{fig}@@"
    _PENDING[token] = path
    i = ids()
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="Picture {i}" descr="{fig}"/>'
            f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{token}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/><a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')


def _attach_pictures(slide, xml):
    relp = SLIDES / "_rels" / f"{slide}.rels"
    rels = relp.read_text(encoding="utf-8")
    for token in sorted(set(re.findall(r"@@RID:[^@]+@@", xml))):
        src = _PENDING[token]
        media = BUILD / "ppt" / "media" / f"u5_{src.name}"
        media.write_bytes(src.read_bytes())
        n = max([int(k) for k in re.findall(r'Id="rId(\d+)"', rels)] + [0]) + 1
        rels = rels.replace(
            "</Relationships>",
            f'<Relationship Id="rId{n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            f'relationships/image" Target="../media/{media.name}"/></Relationships>')
        xml = xml.replace(token, f"rId{n}")
    relp.write_text(rels, encoding="utf-8")
    return xml


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


# ========================================================== section 1 =====
def s_objectives(ids):
    """The unit's learning objectives are exactly the skills its problems assess."""
    rows = [["Skill", "You will be able to"],
            ["Work out FIFO timing",
             "Find the cycle each element is written, read and finished, and when a full FIFO "
             "stalls the producer"],
            ["Size memory for a data stream",
             "Compute a FIFO's element width and total size from its fields and its depth"],
            ["Compare producer and consumer rates",
             "Decide whether a consumer keeps up, when a stream finishes, and how burstiness "
             "sets the FIFO depth"],
            ["Time a valid/ready handshake",
             "Apply registered backpressure: when TREADY drops, and the cycle a stalled "
             "transfer completes"],
            ["Describe AXI4-Stream",
             "Find the cycles that carry a transfer, and where a packet framed by TLAST ends"],
            ["Serialize and deserialize structured data",
             "Pack a header into 32-bit words and write the code, moving fixed-point fields "
             "by their bit pattern"]]
    return [title_ph(ids, "Learning Objectives"),
            table(ids, 1.2, 1.8, [3.9, 7.1], rows, rowh=0.55, sz=15),
            label(ids, 1.2, 5.85, 11.0, 0.6,
                  "Each skill is assessed by problems in the LLM grader.  The demos add what no "
                  "problem tests yet: streaming kernels in Vitis HLS, and command-response messages "
                  "with transaction IDs and error codes.", sz=12),
            sldnum_ph(ids)]


def s_recap(ids):
    """Replaces 'FIFO Motivation' and the two 'Problem' slides: the costs, as
    measured in unit 4's demo, rather than restated in the abstract."""
    out = [title_ph(ids, "Recap: The Cost of a Register Interface")]
    stats = [("22", "cycles of bus traffic per call", SLATE),
             ("5", "cycles of actual computation", VIOLET),
             ("1", "call at a time: nothing is queued", AMBER)]
    for k, (big, cap, colour) in enumerate(stats):
        x = L + k * 3.97
        out.append(shape(ids, x, CONTENT_TOP + 0.05, 3.75, 1.16, fill=WHITE, line=colour, lw=1.5,
                         prst="roundRect", adj=8000, paras=[
                             para(big, sz=30, color=colour, b=True, align="ctr"),
                             para(cap, sz=12, color=MUTED, align="ctr")]))
    out += [heading(ids, L, 3.05, 5.9, "PROBLEM 1: HANDSHAKE OVERHEAD"),
            textbox(ids, L, 3.4, 5.9, 1.9, [
                bullet("Every value is its own AXI4-Lite transaction: address, data, response",
                       spcBef=0),
                bullet("About **3 cycles** per register transfer"),
                bullet("Guaranteed delivery and flow control, paid for **per value**")]),
            heading(ids, 6.95, 3.05, 5.6, "PROBLEM 2: POLLING"),
            textbox(ids, 6.95, 3.4, 5.6, 1.9, [
                bullet("The processor starts the IP, then **asks repeatedly** whether it is done",
                       spcBef=0),
                bullet("The IP sits **idle** while the processor writes inputs and reads outputs"),
                bullet("Neither side can work ahead of the other")]),
            shape(ids, L, 5.45, W, 0.75, fill=TINT, line=VIOLET, lw=1.25, paras=[
                para("This unit: put a **FIFO** between them, so each side runs at its own pace.",
                     sz=17, color=TEXT, align="ctr")]),
            label(ids, L, 6.25, 9.0, 0.3, "Figures measured in unit 4's scalar-function demo.",
                  sz=11),
            sldnum_ph(ids)]
    return out


def s_time_wastage(ids):
    return [title_ph(ids, "Where the Time Goes"),
            picture(ids, "time_wastage", 1.35, 1.7, w=10.6),
            shape(ids, L, 5.82, W, 0.62, fill=BAND, line=TINT2, prst="roundRect", adj=20000,
                  paras=[para("A FIFO **decouples** the two sides in time: the processor queues "
                              "work and leaves, and the IP runs job after job.", sz=16,
                              color=TEXT, align="ctr")]),
            sldnum_ph(ids)]


def _fifo_figure(ids, x, top, filled, labels=None, ch=0.42, w=1.5):
    """Producer, arrow, FIFO, arrow, consumer: the FIFO diagrams' shared frame."""
    labels = labels or [""] * 6
    n = len(labels)
    cx = x + w / 2
    bot = top + 0.75 + n * ch
    return flat([
        label(ids, x - 0.6, top, w + 1.2, 0.32, "Producer", sz=15, color=SLATE, b=True, align="ctr"),
        arrow(ids, cx, top + 0.35, cx, top + 0.7, SLATE, lw=2.0),
        fifo_stack(ids, x, top + 0.75, w, ch, labels, filled),
        arrow(ids, cx, bot + 0.05, cx, bot + 0.4, TEAL, lw=2.0),
        label(ids, x - 0.6, bot + 0.43, w + 1.2, 0.32, "Consumer", sz=15, color=TEAL, b=True,
              align="ctr")])


def s_fifo(ids):
    return flat([
        title_ph(ids, "FIFO"),
        textbox(ids, L, 1.75, 7.6, 4.7, [
            b1("**FIFO** (first-in, first-out): a hardware queue", spcBef=0),
            b2("Stores elements from a **producer** in order of arrival"),
            b2("Returns them to a **consumer** in the same order"),
            b1("**Decouples** producer and consumer timing"),
            b2("Each side runs at its own pace"),
            b1("Built-in **flow control**"),
            b2("The producer waits while the FIFO is full"),
            b2("The consumer waits while it is empty"),
            b1("Absorbs **bursts** of data, and enables **streaming**")]),
        _fifo_figure(ids, 9.6, 1.75, filled=3),
        sldnum_ph(ids)])


def s_terminology(ids):
    x, top, ch, w = 9.9, 1.75, 0.42, 1.5
    y0 = top + 0.75
    sh = flat([
        title_ph(ids, "FIFO Terminology"),
        textbox(ids, L, 1.75, 7.2, 4.7, [
            b1("**Producer**: the module that writes to the FIFO", spcBef=0),
            b2("Each write adds an element"),
            b1("**Consumer**: the module that reads from it"),
            b2("Each read removes an element"),
            b1("**Element**: one item stored in the FIFO"),
            b1("**Element width**: the size of each element, in bits or bytes"),
            b1("**Depth**: the maximum number of elements"),
            b1("**Size** = depth × element width")]),
        _fifo_figure(ids, x, top, filled=3),
        # element width, as a dimension across the top cell
        arrow(ids, x + w / 2, y0 + ch / 2, x + 0.04, y0 + ch / 2, MUTED, lw=1.0),
        arrow(ids, x + w / 2, y0 + ch / 2, x + w - 0.04, y0 + ch / 2, MUTED, lw=1.0),
        label(ids, x - 2.05, y0 + ch / 2 - 0.17, 1.95, 0.32, "element width", sz=13, color=TEXT,
              align="r"),
        # depth, down the right side
        arrow(ids, x + w + 0.2, y0, x + w + 0.2, y0 + 6 * ch, MUTED, lw=1.0, head=False),
        label(ids, x + w + 0.3, y0 + 2.6 * ch, 0.9, 0.3, "depth", sz=13, color=TEXT),
        # one element
        arrow(ids, x - 0.55, y0 + 4.5 * ch, x - 0.05, y0 + 4.5 * ch, VIOLET, lw=1.25),
        label(ids, x - 2.45, y0 + 4.5 * ch - 0.17, 1.85, 0.32, "one element", sz=13, color=VIOLET,
              align="r"),
        sldnum_ph(ids)])
    return sh


def s_order(ids):
    x, top, ch, w = 9.6, 1.75, 0.42, 1.5
    y0 = top + 0.75
    return flat([
        title_ph(ids, "FIFO Order"),
        textbox(ids, L, 1.75, 7.2, 4.7, [
            b1("The producer writes A, then B, then C", spcBef=0),
            b1("A is at the **head**: the oldest element"),
            b1("C is at the **tail**: the newest"),
            b1("The consumer reads from the head"),
            b2("It reads A, B, C: the order they were written"),
            b1("No reordering, and no addresses"),
            b2("Contrast the random-access memory of unit 4")]),
        _fifo_figure(ids, x, top, filled=3, labels=["", "", "", "C", "B", "A"]),
        label(ids, x + w + 0.15, y0 + 3 * ch + 0.05, 1.3, 0.32, "← tail", sz=14, color=TEXT),
        label(ids, x + w + 0.15, y0 + 5 * ch + 0.05, 1.3, 0.32, "← head", sz=14, color=TEXT),
        sldnum_ph(ids)])


def s_overflow(ids):
    x, top, ch, w = 9.6, 1.75, 0.42, 1.5
    return flat([
        title_ph(ids, "FIFO Overflow"),
        textbox(ids, L, 1.75, 7.5, 4.7, [
            b1("The producer has an element, but the FIFO is **full**", spcBef=0),
            b1("**Blocking write**"),
            b2("The FIFO deasserts READY; the producer waits and retries"),
            b2("The default for hardware interfaces, AXI4-Stream included"),
            b2("Also called a stall, backpressure or flow control"),
            b1("**Drop**"),
            b2("An element is discarded: the new one (tail drop), or one already queued"),
            b2("Common in network routers")]),
        _fifo_figure(ids, x, top, filled=6, labels=["F", "E", "D", "C", "B", "A"]),
        shape(ids, x + w + 0.35, top - 0.05, 0.55, 0.42, fill=AMBERTINT, line=AMBER, lw=1.25,
              paras=[para("G", sz=14, color=AMBER, b=True, align="ctr")]),
        label(ids, x + w + 0.1, top + 0.42, 1.3, 0.55, "full: wait\nor drop", sz=12, color=AMBER,
              align="ctr"),
        sldnum_ph(ids)])


# ------------------------------------------------------- section 1 problems --
def s_sizing_practice(ids):
    return [title_ph(ids, "Sizing FIFOs"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 6.9, 4.2, [
                para("A FIFO buffer stores commands with three fields.  Here `ap_int<n>` is an "
                     "integer with n bits.  Assume the fields are packed with no padding.",
                     sz=18, color=TEXT, spcAft=6),
                part("(a)", "What is the element width in bytes?", 18),
                part("(b)", "If the FIFO has a depth of 32 elements, what is the total size of "
                            "the FIFO in bytes?", 18)]),
            code_box(ids, 8.05, 1.9, 4.5, 1.85, """
struct Command {
    ap_int<16> command_id;
    ap_int<32> operand1;
    ap_int<32> operand2;
};""", sz=14),
            portal_caption(ids, "Sizing FIFOs"), sldnum_ph(ids)]


def s_sizing_solution(ids):
    return flat([
        title_ph(ids, "Sizing FIFOs"), pill(ids, "SOLUTION"),
        textbox(ids, L, 1.8, 6.9, 3.0, [
            part("(a)", "16 + 32 + 32 = 80 bits = 2 + 4 + 4 bytes = !!10 bytes!!", 18),
            part("(b)", "32 elements × 10 bytes = !!320 bytes!!", 18),
            cont("Size = depth × element width", 15, MUTED)]),
        label(ids, 8.05, 1.85, 4.5, 0.3, "One element, no padding"),
        field_bar(ids, 8.05, 2.18, 0.7, [
            (0.9, SLATETINT, SLATE, [("id", 13, True), ("2 B", 11, False)]),
            (1.8, TINT, DEEP, [("operand1", 13, True), ("4 B", 11, False)]),
            (1.8, TINT, DEEP, [("operand2", 13, True), ("4 B", 11, False)])]),
        card(ids, 8.05, 3.25, 4.5, 1.45, fill=AMBERTINT, paras=[
            para("^^Common errors^^", sz=15, spcAft=4),
            para("Leaving the width in bits: 80.", sz=14, color=TEXT),
            para("Padding command_id to 4 bytes: 12.  The question rules that out.", sz=14,
                 color=TEXT)]),
        portal_caption(ids, "Sizing FIFOs"), sldnum_ph(ids)])


def _timing_table(rows, blank=False):
    head = ["Cycle", "Producer", "FIFO after", "Consumer"]
    out = [head]
    for r in rows:
        out.append([r[0], r[1], "" if blank else r[2], "" if blank else r[3]])
    return out


FT_ROWS = [("0", "write A", "[A]", "idle"), ("1", "write B", "[B]", "read A"),
           ("2", "—", "[B]", "process A"), ("3", "—", "[ ]", "read B"),
           ("4", "—", "[ ]", "process B"), ("5", "—", "[ ]", "idle"),
           ("6", "write C", "[C]", "idle"), ("7", "—", "[ ]", "read C")]


def s_ftiming_practice(ids):
    return [title_ph(ids, "FIFO Timing"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 6.6, 4.3, [
                para("A producer writes A, B and C into a FIFO at cycles 0, 1 and 6.  An element "
                     "can be read on the cycle after it is written.", sz=16, color=TEXT, spcAft=4),
                para("After reading an element in cycle R, the consumer processes it in R+1, and "
                     "can read the next one in R+2 at the earliest.  It starts idle and reads as "
                     "soon as it can.", sz=16, color=TEXT, spcAft=4),
                para("At which cycle does the consumer read:", sz=16, color=TEXT),
                part("(a)", "A?", 16, spcBef=4), part("(b)", "B?", 16, spcBef=4),
                part("(c)", "C?", 16, spcBef=4)]),
            label(ids, 7.75, 1.8, 4.8, 0.3, "Work it cycle by cycle"),
            table(ids, 7.75, 2.12, [0.75, 1.25, 1.25, 1.55], _timing_table(FT_ROWS, blank=True),
                  rowh=0.4, sz=13),
            portal_caption(ids, "FIFO timing"), sldnum_ph(ids)]


def s_ftiming_solution(ids):
    return [title_ph(ids, "FIFO Timing"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 6.6, 3.2, [
                part("(a)", "A is read at !!cycle 1!!, the first cycle after it is written", 17),
                part("(b)", "B is in the FIFO from cycle 2, but the consumer is processing A: "
                            "read at !!cycle 3!!", 17),
                part("(c)", "The consumer is free from cycle 5, but C arrives at 6: read at "
                            "!!cycle 7!!", 17)]),
            card(ids, L, 4.75, 6.6, 1.2, fill=BAND, line=TINT2, paras=[
                para("**Two limits**", sz=15, spcAft=4),
                para("An element waits for a busy consumer (B), or the consumer waits for an "
                     "element (C).", sz=14, color=TEXT)]),
            table(ids, 7.75, 2.12, [0.75, 1.25, 1.25, 1.55], _timing_table(FT_ROWS),
                  rowh=0.4, sz=13),
            portal_caption(ids, "FIFO timing"), sldnum_ph(ids)]


def s_stall_practice(ids):
    return [title_ph(ids, "FIFO Write Stall"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 7.3, 4.35, [
                para("A producer has elements A, B, C and D, available for writing at the "
                     "earliest in cycles 0, 1, 2 and 3.", sz=16, color=TEXT, spcAft=2),
                bullet("The FIFO holds **2 elements**.  A write can occur only if the FIFO was "
                       "not full after the previous cycle; otherwise the producer **stalls** and "
                       "retries each cycle.", sz=15),
                bullet("An element written in cycle N can be read, and removed, in N+1 at the "
                       "earliest.", sz=15),
                bullet("A read in cycle R is processed in R+1 and R+2; the next read is at R+3 "
                       "at the earliest.  The consumer starts idle.", sz=15),
                para("For each element, give the cycle its write **succeeds**, and the last cycle "
                     "of its processing:", sz=16, color=TEXT, spcBef=10),
                para("**(a)**  A      **(b)**  B      **(c)**  C      **(d)**  D", sz=16,
                     color=TEXT, spcBef=6)]),
            card(ids, 8.45, 1.9, 4.1, 2.1, paras=[
                para("**Work it cycle by cycle**", sz=15, spcAft=6),
                para("For each cycle: what the producer does, what the FIFO holds at the end of "
                     "it, and what the consumer does.", sz=14, color=TEXT, spcAft=6),
                para("The FIFO state at the end of a cycle decides the next cycle's write.",
                     sz=14, color=TEXT)]),
            portal_caption(ids, "FIFO write stall"), sldnum_ph(ids)]


def s_stall_solution(ids):
    rows = [["Cycle", "Producer", "FIFO after", "Consumer"],
            ["0", "write A", "[A]", "idle"], ["1", "write B", "[B]", "read A"],
            ["2", "write C", "[B, C] full", "process A"],
            ["3", {"t": "D stalls", "color": AMBER, "b": True}, "[B, C] full", "process A"],
            ["4", {"t": "D stalls", "color": AMBER, "b": True}, "[C]", "read B"],
            ["5", "write D", "[C, D] full", "process B"], ["6", "—", "[C, D] full", "process B"],
            ["7", "—", "[D]", "read C"], ["8–9", "—", "[D]", "process C"],
            ["10", "—", "[ ]", "read D"], ["11–12", "—", "[ ]", "process D"]]
    return [title_ph(ids, "FIFO Write Stall"), pill(ids, "SOLUTION"),
            table(ids, L, 1.8, [0.85, 1.45, 1.6, 1.5], rows, rowh=0.34, sz=13),
            label(ids, 6.65, 1.8, 5.9, 0.3, "Write succeeds · processing ends"),
            textbox(ids, 6.65, 2.1, 5.9, 1.9, [
                part("(a)", "A: !!cycle 0!! · !!cycle 3!!", 17, spcBef=4),
                part("(b)", "B: !!cycle 1!! · !!cycle 6!!", 17, spcBef=4),
                part("(c)", "C: !!cycle 2!! · !!cycle 9!!", 17, spcBef=4),
                part("(d)", "D: !!cycle 5!! · !!cycle 12!!", 17, spcBef=4)]),
            card(ids, 6.65, 4.15, 5.9, 1.6, fill=AMBERTINT, paras=[
                para("^^Why not cycle 4 for D?^^", sz=15, spcAft=4),
                para("B is read in cycle 4, but the write decision uses the FIFO state after "
                     "cycle 3, which is full.  The slot freed in cycle 4 is usable in cycle 5.",
                     sz=14, color=TEXT)]),
            portal_caption(ids, "FIFO write stall"), sldnum_ph(ids)]


def s_rates(ids):
    y = 4.35
    return flat([
        title_ph(ids, "Producer and Consumer Rates"),
        textbox(ids, L, 1.75, W, 2.5, [
            b1("**Producer rate** λ: the average number of elements written per unit time",
               spcBef=0),
            b2("Per clock cycle, per second, …  If the producer sends jobs, it is the workload"),
            b1("**Consumer rate** μ: the maximum number of reads per unit time"),
            b2("If each element must be processed, it is the consumer's throughput"),
            b2("With a varying cost per element: 1 / the **average** time per element")]),
        shape(ids, 1.2, y, 2.3, 0.85, fill=SLATETINT, line=SLATELINE, paras=[
            para("Producer", sz=16, color=SLATE, b=True, align="ctr")]),
        arrow(ids, 3.55, y + 0.42, 4.55, y + 0.42, SLATE, lw=2.0),
        label(ids, 3.55, y - 0.02, 1.0, 0.35, "λ", sz=18, color=SLATE, b=True, align="ctr"),
        [shape(ids, 4.6 + k * 0.42, y + 0.1, 0.42, 0.65, fill=VIOLET if k >= 2 else TINT,
               line=TINT2, lw=0.75) for k in range(5)],
        arrow(ids, 6.8, y + 0.42, 7.8, y + 0.42, TEAL, lw=2.0),
        label(ids, 6.8, y - 0.02, 1.0, 0.35, "μ", sz=18, color=TEAL, b=True, align="ctr"),
        shape(ids, 7.85, y, 2.3, 0.85, fill=TEALTINT, line=TEALLINE, paras=[
            para("Consumer", sz=16, color=TEAL, b=True, align="ctr")]),
        card(ids, 10.45, y - 0.25, 2.1, 1.35, fill=TINT, anchor="ctr", paras=[
            para("Load factor", sz=13, color=MUTED, align="ctr"),
            para("ρ = λ / μ", sz=24, color=VIOLET, b=True, align="ctr")]),
        label(ids, 1.2, 5.55, 11.0, 0.6,
              "ρ compares the averages.  Whether the FIFO stays small depends on ρ, and also on "
              "how bursty the arrivals are: next.", sz=15, color=TEXT),
        sldnum_ph(ids)])


def s_load_factor(ids):
    rows = [["Load factor", "In hardware", "What the FIFO does"],
            ["ρ < 1  stable", "Under-utilized: headroom",
             "Drains between bursts.  Short-term stalls or drops are still possible"],
            ["ρ = 1  critical", "Fully utilized",
             "No headroom.  Only perfectly regular traffic keeps up; with any randomness the "
             "backlog keeps growing"],
            ["ρ > 1  unstable", "Over-subscribed",
             "Grows without bound.  With backpressure the producer falls ever further behind; "
             "without it, elements are dropped"]]
    return [title_ph(ids, "Load Factor and Stability"),
            table(ids, L, 1.85, [1.55, 1.6, 3.05], rows, rowh=[0.45, 1.0, 1.1, 1.1], sz=13),
            picture(ids, "load_factor", 7.15, 1.85, w=5.4),
            label(ids, 7.15, 5.5, 5.4, 0.6, "Random arrivals and departures, same random seed, "
                  "unbounded FIFO.  Queueing theory names the three regimes.", sz=11),
            sldnum_ph(ids)]


def s_accel_practice(ids):
    return [title_ph(ids, "Throughput and FIFO Depth"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, W, 4.4, [
                para("A vision accelerator processes frames one at a time.  Each frame takes "
                     "**5 ms**; on the **10%** of frames with an object of interest it takes an "
                     "extra 100 ms, **105 ms** in all.", sz=16, color=TEXT, spcAft=2),
                part("(a)", "What is the maximum frame rate the accelerator can sustain without "
                            "its input FIFO growing without bound?", 16, spcBef=8),
                part("(b)", "Frames now arrive at **50 frames/s**, one every 20 ms.  Rank these "
                            "patterns of expensive frames by how large the input FIFO typically "
                            "needs to be, smallest first, and explain:", 16, spcBef=8),
                cont("(i)  Uniform: every 10th frame — 0, 10, 20, …", 15, spcBef=6),
                cont("(ii)  Bursty: runs of 10 — frames 0–9, then 100–109, then 200–209, …", 15),
                cont("(iii)  Random: each frame independently, with probability 10%", 15)]),
            portal_caption(ids, "Accelerator throughput and FIFO depth"), sldnum_ph(ids)]


def s_accel_solution(ids):
    return [title_ph(ids, "Throughput and FIFO Depth"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.8, 6.2, 4.35, [
                part("(a)", "Average time: 0.9 × 5 + 0.1 × 105 = 15 ms", 16),
                cont("Maximum rate: 1 / 15 ms ≈ !!66.7 frames/s!!", 16),
                part("(b)", "!!(i) uniform < (iii) random < (ii) bursty!!", 16, spcBef=12),
                cont("The average load is the same in all three.  What differs is how the "
                     "expensive frames cluster, and a cluster builds a backlog the FIFO must "
                     "hold while the accelerator falls behind.", 14),
                cont("Uniform: about 105 / 20 ≈ 5 frames arrive during one expensive frame, and "
                     "drain before the next.", 14, MUTED, spcBef=6),
                cont("Bursty: 10 × 105 = 1050 ms, while about 52 frames arrive: a backlog of "
                     "40–50.", 14, MUTED, spcBef=4)]),
            picture(ids, "frame_backlog", 7.2, 1.75, h=3.75),
            label(ids, 7.2, 5.55, 5.35, 0.6, "Simulated at 50 frames/s.  The random pattern is "
                  "one draw: its peak varies from run to run, and is unbounded in principle.",
                  sz=11),
            portal_caption(ids, "Accelerator throughput and FIFO depth"), sldnum_ph(ids)]


# ========================================================== section 2 =====
def s_axis_example(ids):
    """Replaces the example timing table, which was the published solution to a
    required problem ('AXI4-Stream timing with stalls').  The new example is the
    in-class write-stall problem, now on AXI4-Stream wires."""
    return [title_ph(ids, "Example: Backpressure on AXI4-Stream"),
            picture(ids, "axis_stall", 1.2, 1.68, h=3.2),
            textbox(ids, L, 4.95, 7.3, 1.3, [
                bullet("The FIFO write-stall problem, on the wires: A–D offered at cycles 0–3, "
                       "FIFO depth 2", sz=14, spcBef=0),
                bullet("**Registered TREADY**: high in a cycle if the FIFO was not full after the "
                       "previous one", sz=14, spcBef=4),
                bullet("D waits with **TVALID held high** until TREADY returns in cycle 5", sz=14,
                       spcBef=4)]),
            card(ids, 8.35, 4.95, 4.2, 1.2, fill=BAND, line=TINT2, paras=[
                para("TREADY high with TVALID low (cycles 8–9) is not a transfer: the receiver "
                     "is ready, the transmitter has nothing to send.", sz=13, color=TEXT)]),
            label(ids, L, 6.25, W, 0.3, "Homework in the LLM grader: Unit 5 › AXI4-Stream timing, "
                  "AXI4-Stream timing with stalls, Non-pipelined slave throughput", sz=12),
            sldnum_ph(ids)]


def _demo(ids, title, crumb, cmds, watch, band):
    """One pointer slide per demo.  The walkthrough itself lives in the docs."""
    out = [title_ph(ids, title),
           shape(ids, L, 1.46, W, 0.76, fill=VIOLET, prst="roundRect", adj=16000,
                 paras=[para(f"{DOCS_URL}   —   {crumb}", sz=18, color=WHITE, b=True,
                             align="ctr")]),
           heading(ids, L, 2.42, 5.9, "RUN THE WHOLE FLOW"),
           shape(ids, L, 2.76, 5.9, 2.0, fill=CODEFILL, line=GRAYLINE, lw=1.0, anchor="t",
                 inset=0.16, paras=[para(f"`{c}`", sz=12, spcBef=0 if k == 0 else 6)
                                    for k, c in enumerate(cmds)]),
           heading(ids, 6.95, 2.42, 5.6, "WHAT TO WATCH FOR"),
           textbox(ids, 6.95, 2.76, 5.6, 2.2,
                   [bullet(w, sz=14, spcBef=0 if k == 0 else 6) for k, w in enumerate(watch)]),
           shape(ids, L, 5.1, W, 1.35, fill=TEALTINT, line=TEALLINE, lw=1.0, inset=0.24,
                 paras=[para(band[0], sz=15, color=TEXT, align="ctr"),
                        para(band[1], sz=14, color=TEAL, b=True, align="ctr", spcBef=8)]),
           sldnum_ph(ids)]
    return out


def s_demo_stream(ids):
    return _demo(ids, "The Demo: a Streaming Filter", "Demos › AXI4-Streaming",
                 ["cd demos/stream/avgfilt",
                  "python avgfilt_build.py --list-steps",
                  "python avgfilt_build.py --through verify_csim",
                  "python avgfilt_build.py"],
                 ["The kernel has **no start or done**: two `axis` ports and `ap_ctrl_none`",
                  "`PIPELINE II=1`: one sample in and one out **every cycle**",
                  "The C simulation still calls the kernel **like a function**, and exits on an "
                  "empty stream",
                  "The timing diagram shows the handshake, the latency and the throughput"],
                 ("Measured in co-simulation: 200 samples out in 200 cycles, after a latency of "
                  "19 cycles, with no stalls.",
                  "That empty-stream exit is the first sign of the next section's limitation."))


# ========================================================== section 4 =====
def s_burst_example(ids):
    """The old table and its separate illustration, on one slide."""
    return [title_ph(ids, "Example Burst Timing"),
            picture(ids, "burst_timing", 1.2, 1.68, h=3.05),
            textbox(ids, L, 4.85, 7.0, 1.5, [
                bullet("A packet of four elements, A–D: **7 beats, 4 transfers**", sz=15,
                       spcBef=0),
                bullet("B and D stall: TREADY is low, and TDATA and TLAST are **held**", sz=15),
                bullet("Cycle 4 is idle: TVALID drops inside the packet", sz=15)]),
            card(ids, 8.05, 4.85, 4.5, 1.3, fill=BAND, line=TINT2, paras=[
                para("The packet ends with the **transfer** that has TLAST = 1: cycle 7, not "
                     "cycle 6 where TLAST first rises.", sz=14, color=TEXT)]),
            sldnum_ph(ids)]


TLAST_ROWS = [["Cycle", "TREADY", "TVALID", "TLAST"],
              ["0", "0", "0", "0"], ["1", "1", "1", "0"], ["2", "0", "1", "0"],
              ["3", "1", "1", "0"], ["4", "0", "1", "1"], ["5", "1", "1", "1"]]


def s_tlast_practice(ids):
    return [title_ph(ids, "AXI4-Stream Burst with TLAST"), pill(ids, "PRACTICE"),
            table(ids, L, 1.9, [1.0, 1.15, 1.15, 1.15],
                  [[{"t": c, "align": "ctr"} for c in r] for r in TLAST_ROWS], rowh=0.45, sz=15),
            textbox(ids, 6.0, 1.85, 6.55, 4.0, [
                para("A transfer occurs on any cycle where TVALID = 1 and TREADY = 1.", sz=18,
                     color=TEXT, spcAft=6),
                part("(a)", "What is the first cycle of the burst, the first with TVALID = 1?", 18),
                part("(b)", "On which cycle does the last transfer occur?", 18),
                part("(c)", "How many elements were transferred in the burst?", 18)]),
            portal_caption(ids, "AXI4-Stream burst with TLAST"), sldnum_ph(ids)]


def s_tlast_solution(ids):
    return [title_ph(ids, "AXI4-Stream Burst with TLAST"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.75, 7.2, 2.2, [
                part("(a)", "!!Cycle 1!!: the first cycle with TVALID = 1", 17, spcBef=0),
                part("(b)", "!!Cycle 5!!.  TLAST rises in cycle 4, but TREADY = 0 there, so the "
                            "last element stalls", 17, spcBef=6),
                part("(c)", "!!3 elements!!: transfers on cycles 1, 3 and 5.  The burst is 5 "
                            "beats, 2 of them stalls", 17, spcBef=6)]),
            card(ids, 8.35, 1.8, 4.2, 1.95, fill=AMBERTINT, paras=[
                para("^^Common errors^^", sz=15, spcAft=4),
                para("Counting a cycle with TVALID = 1 but TREADY = 0: 5 elements.", sz=14,
                     color=TEXT, spcAft=4),
                para("Ending the burst where TLAST first rises: cycle 4.", sz=14, color=TEXT)]),
            picture(ids, "tlast_solution", 1.6, 3.88, h=2.25),
            portal_caption(ids, "AXI4-Stream burst with TLAST"), sldnum_ph(ids)]


def _msg_row(ids, x, y, blocks, h=0.55):
    """A message sequence on one stream: blocks = [(width, fill, line, colour, text)].
    A thin amber bar after each block is a TLAST."""
    out, cx = [], x
    for w, fill, line, colour, text in blocks:
        out.append(shape(ids, cx, y, w, h, fill=fill, line=line, lw=0.75,
                         paras=[para(text, sz=12, color=colour, b=True, align="ctr")]))
        out.append(shape(ids, cx + w, y - 0.06, 0.07, h + 0.12, fill=AMBER))
        cx += w + 0.07
    return out


def s_block_poly(ids):
    x0, y0 = 7.05, 1.8
    hdr = (1.45, SLATETINT, SLATELINE, SLATE)
    dat = (TEALTINT, TEALLINE, TEAL)
    return flat([
        title_ph(ids, "Example: A Command-Response IP"),
        textbox(ids, L, 1.75, 6.0, 4.6, [
            b1("Evaluate a cubic on a stream of samples", sz=19, spcBef=0),
            b2("$𝑦[𝑘] = 𝑐₀ + 𝑐₁𝑥[𝑘] + 𝑐₂𝑥[𝑘]² + 𝑐₃𝑥[𝑘]³$", sz=16),
            b1("The coefficients arrive **with the data**, in a command", sz=19),
            b2("Each transaction can use a different polynomial", sz=16),
            b2("No separate AXI4-Lite path to keep in step", sz=16),
            b1("One **transaction**: a command in, a response out", sz=19),
            b1("**TLAST** ends each message, so the IP can tell a header from the samples that "
               "follow", sz=19)]),
        label(ids, x0, y0, 3.0, 0.3, "in_stream", sz=13, color=TEXT, b=True),
        _msg_row(ids, x0, y0 + 0.35, [hdr + ("PolyCmdHdr",),
                                      (3.3,) + dat + ("x[0] … x[nsamp−1]",)]),
        arrow(ids, x0 + 2.4, y0 + 1.0, x0 + 2.4, y0 + 1.45, TEAL, lw=2.0),
        shape(ids, x0 + 0.9, y0 + 1.5, 3.0, 0.75, fill=VIOLET, prst="roundRect", adj=14000,
              paras=[para("poly IP", sz=16, color=WHITE, b=True, align="ctr")]),
        arrow(ids, x0 + 2.4, y0 + 2.3, x0 + 2.4, y0 + 2.75, TEAL, lw=2.0),
        label(ids, x0, y0 + 2.75, 3.0, 0.3, "out_stream", sz=13, color=TEXT, b=True),
        _msg_row(ids, x0, y0 + 3.1, [hdr + ("PolyRespHdr",),
                                     (2.25,) + dat + ("y[0] … y[nsamp−1]",),
                                     hdr + ("PolyRespFtr",)]),
        shape(ids, x0, y0 + 3.95, 0.07, 0.3, fill=AMBER),
        label(ids, x0 + 0.15, y0 + 3.93, 3.0, 0.3, "= TLAST", sz=12, color=AMBER, b=True),
        sldnum_ph(ids)])


def s_messages(ids):
    rows = [["Message", "Field", "Type", "Holds"],
            [{"t": "PolyCmdHdr", "b": True}, "`tx_id`", "uint16", "Transaction ID"],
            ["", "`coeffs`", "4 × float32", "$𝑐₀$ … $𝑐₃$"],
            ["", "`nsamp`", "uint16", "Number of samples that follow"],
            [{"t": "PolyRespHdr", "b": True}, "`tx_id`", "uint16", "Echo of the command's ID"],
            [{"t": "PolyRespFtr", "b": True}, "`nsamp_read`", "uint16", "Samples actually read"],
            ["", "`error`", "3-bit enum", "What went wrong, if anything"]]
    return [title_ph(ids, "Command and Response Messages"),
            table(ids, L, 1.8, [1.9, 1.65, 1.6, 3.35], rows, rowh=0.44, sz=14),
            card(ids, 9.55, 1.8, 3.0, 3.08, fill=TINT, paras=[
                para("**Defined once, in Python**", sz=15, spcAft=6),
                para("`poly_schema.py` describes each message as a waveflow data schema.",
                     sz=13, color=TEXT, spcAft=6),
                para("The C++ that packs and unpacks them is generated from it, so the kernel, "
                     "the testbench and the model agree.", sz=13, color=TEXT)]),
            heading(ids, L, 5.08, 6.0, "ONE TRANSACTION, WHERE EVERY | IS A TLAST"),
            shape(ids, L, 5.4, W, 0.95, fill=CODEFILL, line=GRAYLINE, lw=0.75, anchor="ctr",
                  inset=0.2, paras=[
                      para("`in_stream:    PolyCmdHdr   |  x[0], x[1], …, x[nsamp−1]  |`", sz=14),
                      para("`out_stream:   PolyRespHdr  |  y[0], y[1], …, y[nsamp−1]  |  "
                           "PolyRespFtr  |`", sz=14, spcBef=4)]),
            sldnum_ph(ids)]


def s_ids_errors(ids):
    top, ph, bh = 1.75, 0.55, 2.9
    lx, rx, w = L, 6.85, 5.7
    errs = [["Code", "Error"], ["0", "`NO_ERROR`"], ["1", "`TLAST_EARLY_CMD_HDR`"],
            ["2", "`NO_TLAST_CMD_HDR`"], ["3", "`TLAST_EARLY_SAMP_IN`"],
            ["4", "`NO_TLAST_SAMP_IN`"], ["5", "`WRONG_NSAMP`"]]
    return [title_ph(ids, "Robust Messages: IDs and Error Codes"),
            shape(ids, lx, top, w, ph, fill=VIOLET, prst="roundRect", adj=12000,
                  paras=[para("Transaction IDs", sz=18, color=WHITE, b=True, align="ctr")]),
            shape(ids, lx, top + ph, w, bh, fill=TINT, line=TINT2),
            textbox(ids, lx + 0.3, top + ph + 0.2, w - 0.6, bh - 0.4, [
                bullet("The command carries `tx_id`; the response header echoes it", spcBef=0),
                bullet("The host matches each response to its command"),
                bullet("A gap or a repeat in the IDs exposes a lost or duplicated message"),
                bullet("Several commands can be in flight at once")]),
            shape(ids, rx, top, w, ph, fill=SLATE, prst="roundRect", adj=12000,
                  paras=[para("Error codes, in the footer", sz=18, color=WHITE, b=True,
                              align="ctr")]),
            table(ids, rx, top + ph, [0.9, w - 0.9], errs, rowh=bh / 7, sz=13, head_fill=SLATE),
            shape(ids, L, 5.45, W, 1.0, fill=AMBERTINT, line=AMBER, lw=1.0, inset=0.2, paras=[
                para("Hardware cannot stop on bad input: the next command is already queued.  It "
                     "must **report** the error and **resynchronize** at the next TLAST.", sz=15,
                     color=TEXT, align="ctr"),
                para("The demo's hand-written kernel reports; its general kernel also recovers.",
                     sz=13, color=MUTED, align="ctr", spcBef=4)]),
            sldnum_ph(ids)]


def s_packing(ids):
    x = 7.35
    return flat([
        title_ph(ids, "Packing Fields into Words"),
        textbox(ids, L, 1.75, 6.3, 4.7, [
            b1("A stream moves fixed-width **words**: 32 or 64 bits", sz=18, spcBef=0),
            b1("**Rule**: no field crosses a word boundary", sz=18),
            b2("Pack small fields together; start a new word when the next will not fit", sz=15),
            b2("Set unused bits to zero", sz=15),
            b1("An integer field: assign its value to a bit range", sz=18),
            b2("`w.range(15, 0) = nsamp_read;`", sz=15),
            b1("A **fixed-point** field: copy its **bits**, not its value", sz=18),
            b2("`w.range(11, 0) = a.range(11, 0);`  copies the bits", sz=15),
            b2("`w.range(11, 0) = a;`  converts the value: 0.75 becomes 0", sz=15)]),
        label(ids, x, 1.8, 5.2, 0.3, "The demo's PolyRespFtr: two fields in one 32-bit word"),
        field_bar(ids, x, 2.15, 0.7, [
            (1.9, GRAYFILL, MUTED, [("zero", 13, False), ("31–19", 11, False)]),
            (1.1, AMBERTINT, AMBER, [("error", 13, True), ("18–16", 11, False)]),
            (2.2, TINT, VIOLET, [("nsamp_read", 13, True), ("15–0", 11, False)])]),
        label(ids, x, 3.2, 5.2, 0.3, "Its PolyCmdHdr at 32 bits: six words"),
        field_bar(ids, x, 3.55, 0.7, [
            (0.95, SLATETINT, SLATE, [("tx_id", 12, True), ("w0", 10, False)])] +
            [(0.82, TEALTINT, TEAL, [(f"c{k}", 12, True), (f"w{k + 1}", 10, False)])
             for k in range(4)] +
            [(0.97, SLATETINT, SLATE, [("nsamp", 12, True), ("w5", 10, False)])]),
        card(ids, x, 4.6, 5.2, 1.5, fill=BAND, line=TINT2, paras=[
            para("A float fills a word exactly.  A 16-bit field leaves the upper half of its "
                 "word zero, which a 64-bit stream packs more tightly.", sz=13, color=TEXT)]),
        sldnum_ph(ids)])


CMDHDR = """
class CmdHdr {
    ap_uint<16> trans_id;
    // Q1.11: 1 sign bit, 11 fractional bits;
    // 1.0 corresponds to π radians
    ap_fixed<12,1> yaw, pitch, roll;
    ap_uint<16> nsamp;
};"""


def s_ser_practice(ids):
    return [title_ph(ids, "Serializing a Command Header"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 6.4, 4.3, [
                para("`ap_uint<n>` is an n-bit unsigned integer.  `ap_fixed<W,I>` is a signed "
                     "fixed-point value with W bits in all, I of them integer bits, the sign "
                     "included.", sz=16, color=TEXT, spcAft=4),
                part("(a)", "How many 32-bit words does one header need, if no field may be "
                            "split across a word boundary?", 16),
                part("(b)", "Complete the function below to serialize a header into 32-bit "
                            "words.  Use the minimum number of words.", 16)]),
            code_box(ids, 7.45, 1.85, 5.1, 2.35, CMDHDR, sz=13),
            code_box(ids, 7.45, 4.4, 5.1, 1.15, """
void serialize(const CmdHdr &cmd_hdr,
               ap_uint<32> words[/* ? */]) {
    ...
}""", sz=13),
            portal_caption(ids, "Serializing a command header"), sldnum_ph(ids)]


def s_ser_solution(ids):
    return flat([
        title_ph(ids, "Serializing a Command Header"), pill(ids, "SOLUTION"),
        textbox(ids, L, 1.75, 5.9, 1.0, [
            part("(a)", "16 + 12 + 12 + 12 + 16 = 68 bits: more than two words.  Three suffice: "
                        "!!3 words!!", 16, spcBef=0)]),
        label(ids, L + 0.45, 2.85, 1.0, 0.3, "word 0", sz=12, color=TEXT),
        field_bar(ids, L + 1.25, 2.8, 0.45, [(0.6, GRAYFILL, MUTED, [("0", 11, False)]),
                                             (1.9, TINT, VIOLET, [("yaw 27–16", 12, True)]),
                                             (2.2, SLATETINT, SLATE, [("trans_id 15–0", 12, True)])]),
        label(ids, L + 0.45, 3.4, 1.0, 0.3, "word 1", sz=12, color=TEXT),
        field_bar(ids, L + 1.25, 3.35, 0.45, [(0.8, GRAYFILL, MUTED, [("0", 11, False)]),
                                              (1.95, TINT, VIOLET, [("roll 23–12", 12, True)]),
                                              (1.95, TINT, VIOLET, [("pitch 11–0", 12, True)])]),
        label(ids, L + 0.45, 3.95, 1.0, 0.3, "word 2", sz=12, color=TEXT),
        field_bar(ids, L + 1.25, 3.9, 0.45, [(2.5, GRAYFILL, MUTED, [("0", 11, False)]),
                                             (2.2, SLATETINT, SLATE, [("nsamp 15–0", 12, True)])]),
        card(ids, L, 4.6, 5.9, 1.45, fill=AMBERTINT, paras=[
            para("^^The error that matters^^", sz=15, spcAft=4),
            para("`w0.range(27, 16) = cmd_hdr.yaw;` converts the value to an integer: "
                 "yaw = −0.25 packs as 0, not `0xE00`.", sz=13, color=TEXT)]),
        code_box(ids, 6.95, 1.75, 5.6, 4.35, """
void serialize(const CmdHdr &cmd_hdr,
               ap_uint<32> words[3]) {
    ap_uint<32> w0 = 0;              // trans_id | yaw
    w0.range(15, 0)  = cmd_hdr.trans_id;
    w0.range(27, 16) = cmd_hdr.yaw.range(11, 0);
    words[0] = w0;

    ap_uint<32> w1 = 0;              // pitch | roll
    w1.range(11, 0)  = cmd_hdr.pitch.range(11, 0);
    w1.range(23, 12) = cmd_hdr.roll.range(11, 0);
    words[1] = w1;

    ap_uint<32> w2 = 0;              // nsamp
    w2.range(15, 0) = cmd_hdr.nsamp;
    words[2] = w2;
}""", sz=11),
        portal_caption(ids, "Serializing a command header"), sldnum_ph(ids)])


def s_deser_practice(ids):
    rows = [["Word", "Bits", "Field", "Width"],
            ["0", "15:0", "`trans_id`", "16"], ["0", "27:16", "`yaw`", "12"],
            ["1", "11:0", "`pitch`", "12"], ["1", "23:12", "`roll`", "12"],
            ["2", "15:0", "`nsamp`", "16"]]
    return [title_ph(ids, "Deserializing a Command Header"), pill(ids, "PRACTICE"),
            textbox(ids, L, 1.8, 6.1, 2.0, [
                para("The same `CmdHdr` has been serialized into three 32-bit words with the "
                     "packing in the table.", sz=16, color=TEXT, spcAft=6),
                para("Complete `deserialize`.  It must assign every field, and each fixed-point "
                     "field must get back **exactly** the value serialized, negative angles "
                     "included.", sz=16, color=TEXT)]),
            table(ids, L, 3.95, [0.9, 1.1, 1.6, 1.0], rows, rowh=0.36, sz=13),
            code_box(ids, 7.15, 1.85, 5.4, 2.35, CMDHDR, sz=13),
            code_box(ids, 7.15, 4.4, 5.4, 1.15, """
void deserialize(CmdHdr &cmd_hdr,
                 ap_uint<32> words[3]) {
    // Fill in your solution here
}""", sz=13),
            portal_caption(ids, "Deserializing a command header"), sldnum_ph(ids)]


def s_deser_solution(ids):
    return [title_ph(ids, "Deserializing a Command Header"), pill(ids, "SOLUTION"),
            textbox(ids, L, 1.75, 5.9, 2.6, [
                para("Assigning an integer to an `ap_fixed` is a **numeric conversion**, not a "
                     "bit copy.", sz=16, color=TEXT, spcAft=6),
                para("`cmd_hdr.yaw = w0.range(27, 16);` reads the 12 bits as an integer between "
                     "−2048 and 2047, which wraps to 0 or −1 in the range [−1, 1).", sz=15,
                     color=TEXT, spcAft=6),
                para("Write the bits into the field with `.range()` instead.  All 12 bits, the "
                     "sign bit included, are copied, so no sign extension is needed.", sz=15,
                     color=TEXT)]),
            card(ids, L, 4.5, 5.9, 1.55, fill=TINT, paras=[
                para("**The same rule, both ways**", sz=15, spcAft=4),
                para("Serialize: `w.range(…) = f.range(11, 0);`", sz=14, color=TEXT),
                para("Deserialize: `f.range(11, 0) = w.range(…);`", sz=14, color=TEXT,
                     spcBef=2)]),
            code_box(ids, 6.95, 1.75, 5.6, 4.35, """
void deserialize(CmdHdr &cmd_hdr,
                 ap_uint<32> words[3]) {
    ap_uint<32> w0 = words[0];
    ap_uint<32> w1 = words[1];
    ap_uint<32> w2 = words[2];

    // Word 0: trans_id | yaw
    cmd_hdr.trans_id = w0.range(15, 0);
    cmd_hdr.yaw.range(11, 0) = w0.range(27, 16);

    // Word 1: pitch | roll
    cmd_hdr.pitch.range(11, 0) = w1.range(11, 0);
    cmd_hdr.roll.range(11, 0)  = w1.range(23, 12);

    // Word 2: nsamp
    cmd_hdr.nsamp = w2.range(15, 0);
}""", sz=11),
            portal_caption(ids, "Deserializing a command header"), sldnum_ph(ids)]


def s_demo_poly(ids):
    return _demo(ids, "The Demo: a Command-Response IP",
                 "Demos › Command-Response FIFO Interface",
                 ["cd demos/stream/poly",
                  "python poly_build.py --list-steps",
                  "python poly_build.py --through verify_csim \\",
                  "    --kernel poly32 --force-step csim",
                  "python poly_build.py"],
                 ["The messages are written once, in `poly_schema.py`; the headers that pack "
                  "them are generated",
                  "Three kernels, one function: `poly32` and `poly64` pack by hand, `general` "
                  "uses the generated code",
                  "Every TLAST is checked, and a misplaced one is reported in the footer",
                  "The timing diagram decodes each message off the wires"],
                 ("Three transactions, checked field by field against the Python model.  Output "
                  "starts 34 cycles after the input, then comes out one sample per cycle.",
                  "Same stream interface as the filter; the messages are what is new."))


def s_summary(ids):
    rows = [["", "AXI4-Lite registers", "AXI4-Stream, pure", "AXI4-Stream, packets"],
            [{"t": "Carries", "b": True}, "A few control values", "An endless sequence of samples",
             "Commands and data, framed by TLAST"],
            [{"t": "Rate", "b": True}, "About 3 cycles per value", "One value per cycle",
             "One word per cycle"],
            [{"t": "Control", "b": True}, "Is the interface", "A separate path, hard to keep "
             "in step", "Travels with the data"],
            [{"t": "Flow control", "b": True}, "A handshake per transaction",
             "TREADY backpressure into a FIFO", "The same, plus IDs and error codes"],
            [{"t": "Seen in", "b": True}, "Unit 4, scalar function", "Unit 5, streaming filter",
             "Unit 5, polynomial IP"]]
    return [title_ph(ids, "Choosing an Interface"),
            table(ids, L, 1.85, [1.9, 3.3, 3.3, 3.3], rows, rowh=0.62, sz=14),
            shape(ids, L, 5.85, W, 0.6, fill=TINT, line=VIOLET, lw=1.25, paras=[
                para("Registers to **configure** an IP; streams to **feed** it.", sz=17,
                     color=TEXT, align="ctr")]),
            sldnum_ph(ids)]


# ============================================================== passes ====
def sh(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode:
        raise SystemExit(f"FAILED: {' '.join(map(str, cmd))}\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


def slide_order():
    pres = (BUILD / "ppt" / "presentation.xml").read_text(encoding="utf-8")
    rels = (BUILD / "ppt" / "_rels" / "presentation.xml.rels").read_text(encoding="utf-8")
    rid = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    return [rid[r].split("/")[-1] for r in re.findall(r'<p:sldId[^>]*r:id="([^"]+)"', pres)]


def slide_title(name):
    xml = (SLIDES / name).read_text(encoding="utf-8")
    texts = [t.strip() for t in re.findall(r"<a:t>(.*?)</a:t>", xml, re.S) if t.strip()]
    return texts[0] if texts else ""


def set_order(names):
    """Rewrite <p:sldIdLst> to exactly these slide parts, in this order.  Parts
    left out are deleted by clean.py afterwards."""
    ppath = BUILD / "ppt" / "presentation.xml"
    pres = ppath.read_text(encoding="utf-8")
    rels = (BUILD / "ppt" / "_rels" / "presentation.xml.rels").read_text(encoding="utf-8")
    by_file = {t.split("/")[-1]: r for r, t in re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels)}
    entries = {m.group(1): m.group(0) for m in re.finditer(r'<p:sldId [^>]*r:id="([^"]+)"\s*/>', pres)}
    new = "".join(entries[by_file[n]] for n in names)
    pres, k = re.subn(r"<p:sldIdLst>.*?</p:sldIdLst>", f"<p:sldIdLst>{new}</p:sldIdLst>", pres,
                      flags=re.S)
    assert k == 1
    ppath.write_text(pres, encoding="utf-8")


def write(slide, shapes):
    xml = _attach_pictures(slide, slide_doc(shapes))
    (SLIDES / slide).write_text(xml, encoding="utf-8")
    drop_unused_rels(slide)


def drop_unused_rels(slide):
    """Remove image relationships a rebuilt slide no longer references."""
    xml = (SLIDES / slide).read_text(encoding="utf-8")
    relp = SLIDES / "_rels" / f"{slide}.rels"
    rels = relp.read_text(encoding="utf-8")
    for rid, target in re.findall(r'<Relationship Id="(rId\d+)"[^>]*Target="([^"]+)"', rels):
        if "media" in target and f'r:embed="{rid}"' not in xml and f'r:id="{rid}"' not in xml:
            rels = re.sub(rf'<Relationship Id="{rid}"[^>]*/>', "", rels)
    relp.write_text(rels, encoding="utf-8")


def fix(slide, old, new, count=1):
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")
    n = t.count(old)
    assert n == count, f"{slide}: expected {count} of {old!r}, found {n}"
    p.write_text(t.replace(old, new), encoding="utf-8")


def fix_lowest(slide, old, new):
    """Replace the lowest-placed of several identical labels: in the stream
    diagrams, the y[k] label under the x[k] one."""
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")
    best = None
    for m in re.finditer(re.escape(old), t):
        start = t.rfind("<p:sp>", 0, m.start())
        off = re.search(r'<a:off x="-?\d+" y="(-?\d+)"', t[start:m.start()])
        y = int(off.group(1))
        if best is None or y > best[0]:
            best = (y, m.start())
    assert best and best[0] > E(4.3), f"{slide}: no low {old!r}"
    p.write_text(t[:best[1]] + new + t[best[1] + len(old):], encoding="utf-8")


# The old theme's purples, used for highlighted terms.
HIGHLIGHT_OLD = [
    '<a:schemeClr val="accent1"><a:lumMod val="60000"/><a:lumOff val="40000"/></a:schemeClr>',
    '<a:schemeClr val="accent1"/>',
    '<a:schemeClr val="accent2"><a:lumMod val="75000"/></a:schemeClr>',
]


def lst_style():
    """Body bullets: violet squares at level 1, grey dashes at level 2, with
    margins for them; spacing left to the template."""
    m1 = f' marL="{E(0.3)}" indent="{E(-0.3)}"'
    m2 = f' marL="{E(0.68)}" indent="{E(-0.25)}"'
    return ("<a:lstStyle>"
            f'<a:lvl1pPr{m1}><a:buClr><a:srgbClr val="{VIOLET}"/></a:buClr><a:buSzPct val="70000"/>'
            f'<a:buFont typeface="Arial"/><a:buChar char="■"/></a:lvl1pPr>'
            f'<a:lvl2pPr{m2}><a:buClr><a:srgbClr val="999999"/></a:buClr><a:buSzPct val="100000"/>'
            f'<a:buFont typeface="Arial"/><a:buChar char="–"/></a:lvl2pPr>'
            "</a:lstStyle>")


def restyle(slide):
    """New bullets on the body placeholder, NYU violet for highlighted text."""
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")

    def body(m):
        spx = m.group(0)
        ph = re.search(r"<p:ph[^>]*>", spx)
        if ph and 'idx="1"' in ph.group(0) and "type=" not in ph.group(0):
            spx = re.sub(r"<a:lstStyle/>|<a:lstStyle>.*?</a:lstStyle>", lst_style(), spx,
                         count=1, flags=re.S)
        return spx

    t = re.sub(r"<p:sp>.*?</p:sp>", body, t, flags=re.S)

    def recolor(m):
        x = m.group(0)
        for old in HIGHLIGHT_OLD:
            x = x.replace(old, f'<a:srgbClr val="{VIOLET}"/>')
        return x

    t = re.sub(r"<a:rPr\b[^>]*>.*?</a:rPr>", recolor, t, flags=re.S)
    p.write_text(t, encoding="utf-8")


def _sc(val, mod=None, off=None):
    inner = (f'<a:lumMod val="{mod}"/>' if mod else "") + (f'<a:lumOff val="{off}"/>' if off else "")
    return f'<a:schemeClr val="{val}">{inner}</a:schemeClr>' if inner else f'<a:schemeClr val="{val}"/>'


# The hand-drawn diagrams are recoloured, not redrawn: violet for storage and
# the IP, slate for the processor and control, teal for data.
DIAGRAM_FILLS = {
    _sc("accent2", 20000, 80000): TINT,
    _sc("accent2", 60000, 40000): MIDV,
    _sc("accent4", 20000, 80000): TINT,
    _sc("accent5", 20000, 80000): SLATETINT,
    _sc("accent5", 40000, 60000): SLATETINT,
    _sc("accent5", 50000): SLATE,
    _sc("accent5", 75000): SLATE,
    _sc("accent6", 20000, 80000): SLATETINT,
    _sc("accent6", 75000): SLATE,
    '<a:srgbClr val="CADEB2"/>': TEALTINT,
    '<a:srgbClr val="00B050"/>': TEAL,
    '<a:srgbClr val="E0F8E0"/>': TEALTINT,
    '<a:srgbClr val="CCFFCC"/>': TEALTINT,
}
DIAGRAM_TEXT = {
    _sc("accent5", 75000): SLATE,
    _sc("accent6", 75000): SLATE,
    _sc("accent6"): SLATE,
    _sc("tx2", 60000, 40000): SLATE,
    _sc("accent2", 60000, 40000): VIOLET,
    '<a:srgbClr val="00B050"/>': TEAL,
    '<a:srgbClr val="0070C0"/>': SLATE,
    '<a:srgbClr val="FF0000"/>': AMBER,
}


def recolour_diagrams(slide):
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")

    def sub(table_):
        def one(m):
            x = m.group(0)
            for old, new in table_.items():
                x = x.replace(old, f'<a:srgbClr val="{new}"/>')
            return x
        return one

    t = re.sub(r"<p:spPr>.*?</p:spPr>", sub(DIAGRAM_FILLS), t, flags=re.S)
    t = re.sub(r"<a:rPr\b[^>]*>.*?</a:rPr>", sub(DIAGRAM_TEXT), t, flags=re.S)
    p.write_text(t, encoding="utf-8")


def retheme_accent1():
    """Point the theme's magenta accent1 at NYU violet, as unit 4 did, so the
    outline arrows and style-driven table headers follow."""
    p = BUILD / "ppt" / "theme" / "theme1.xml"
    t = p.read_text(encoding="utf-8")
    t, k = re.subn(r'(<a:accent1>\s*<a:srgbClr val=")92278F("/>)', rf"\g<1>{VIOLET}\g<2>", t, count=1)
    assert k == 1, "theme accent1 not found"
    p.write_text(t, encoding="utf-8")


def pack(out):
    if out.exists():
        out.unlink()
    files = sorted(p for p in BUILD.rglob("*") if p.is_file())
    ct = BUILD / "[Content_Types].xml"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ct, "[Content_Types].xml")
        for f in files:
            if f != ct:
                z.write(f, f.relative_to(BUILD).as_posix())


MIGRATED_MARKER = "Recap: The Cost of a Register Interface"   # a slide only this script makes

# The deck this script was written against: title of each old slide it moves,
# rewrites or drops, by presentation position.  Checked before anything is done.
EXPECTED = {1: "Unit 5", 2: "Learning Objectives", 4: "FIFO Motivation",
            5: "Problem 1: Handshaking Overhead", 7: "Problem 2:  Time Wastage", 8: "FIFO",
            11: "Example Problem", 13: "Solution", 14: "FIFO Overflow",
            17: "Producer and Consumer Rate", 18: "Load Factor and Stability ",
            21: "Queueing Theory", 22: "Outline", 24: "Solution:  Streaming FIFO Interface",
            28: "Example Timing", 29: "Example:  Streaming Squared Average",
            32: "In-Class Demo", 34: "Outline", 43: "Outline", 46: "Example Burst Timing",
            48: "Example:  Block Polynomial Accelerator", 51: "Serialization / Deserialization",
            53: "Serialization / Deserialization in Hardware", 54: "Example Problem",
            64: "Vitis HLS Code Generation"}

# ('old', position, builder or None) keeps or rebuilds an old slide; ('new', builder)
# adds one.  Old slides not listed are dropped: 5, 6, 23 (the handshake and
# polling problems, now the recap), 30-33 and 57-64 (the demo walkthroughs, now
# in the docs), 47 (merged into the burst example), 50 and 56 (merged).
PLAN = [
    ("old", 1, None), ("old", 2, s_objectives), ("old", 3, None),
    ("old", 4, s_recap), ("old", 7, s_time_wastage),
    ("old", 8, s_fifo), ("old", 9, s_terminology), ("old", 10, s_order),
    ("old", 11, s_sizing_practice), ("new", s_sizing_solution),
    ("old", 12, s_ftiming_practice), ("old", 13, s_ftiming_solution),
    ("old", 14, s_overflow), ("old", 15, s_stall_practice), ("old", 16, s_stall_solution),
    ("old", 17, s_rates), ("old", 18, s_load_factor),
    ("old", 19, s_accel_practice), ("old", 20, s_accel_solution), ("old", 21, None),
    # section 2: pure streaming
    ("old", 22, None), ("old", 24, None), ("old", 25, None), ("old", 26, None),
    ("old", 27, None), ("old", 28, s_axis_example), ("old", 29, None), ("new", s_demo_stream),
    # section 3: limitations
    ("old", 34, None), ("old", 35, None), ("old", 36, None), ("old", 37, None),
    ("old", 38, None), ("old", 39, None), ("old", 40, None), ("old", 41, None),
    ("old", 42, None),
    # section 4: packets
    ("old", 43, None), ("old", 44, None), ("old", 45, None), ("old", 46, s_burst_example),
    ("new", s_tlast_practice), ("new", s_tlast_solution),
    ("old", 48, s_block_poly), ("old", 49, s_messages), ("new", s_ids_errors),
    ("old", 51, None), ("old", 52, None), ("old", 53, None), ("new", s_packing),
    ("old", 54, s_ser_practice), ("old", 55, s_ser_solution),
    ("new", s_deser_practice), ("new", s_deser_solution),
    ("new", s_demo_poly), ("new", s_summary),
]


def text_fixes(old):
    """Content corrections on slides that are kept, not rebuilt."""
    s = old
    fix(s[1], "EL-GY 9463:  Introduction to Hardware Design", "ECE-GY 6463:  Advanced Hardware Design")
    fix(s[1], "ProfS. Sundeep", "Profs. Sundeep")
    for n in (3, 22, 34, 43):
        fix(s[n], "<a:t>FIFO Interfaces</a:t>", "<a:t>FIFOs</a:t>")
        fix(s[n], "<a:t>AXI4 Pure Streaming Interface</a:t>", "<a:t>AXI4-Stream: Pure Streaming</a:t>")
        fix(s[n], "<a:t>AXI4 Packetized Streaming</a:t>",
            "<a:t>AXI4-Stream: Packets and Serialization</a:t>")

    # AXI4-Stream overview: "addressing" was promised for later in the unit
    # and never taught; TDEST and friends are optional and not used here.
    fix(s[25], "<a:t>AXI4-Streaming Protocol</a:t>", "<a:t>AXI4-Stream</a:t>")
    fix(s[25], "AXI4-Memory mapped:  Later", "AXI4 (full, memory-mapped):  later")
    fix(s[25], "Provides a simple interface with DATA, READY, VALID",
        "Core signals: TDATA, TVALID and TREADY")
    fix(s[25], "Additional capabilities (covered later in this unit):", "Optional signals:")
    fix(s[25], "<a:t>Packetization</a:t>", "<a:t>TLAST, marking the end of a packet: later in this unit</a:t>")
    fix(s[25], "<a:t>Addressing  </a:t>", "<a:t>TKEEP, TSTRB, TID, TDEST, TUSER: not covered here</a:t>")

    # The sentence stopped mid-way.  The role words are renamed below.
    fix(s[26], "FIFO is typically realized on the ", "FIFO is typically realized on the slave side")
    fix(s[26], "Slave is the consumer / receiver", "Slave is the consumer")

    # A master may not withdraw TVALID once raised: it holds TVALID and TDATA
    # until the transfer.  "re-assert on the next cycle" says the opposite.
    fix(s[27], "On any cycle has data to transfer, master:", "On any cycle it has data, the master:")
    fix(s[27], "Slave asserts TREADY on any cycle it can accept data", "Slave asserts TREADY when it can accept data")
    fix(s[27], "Otherwise, master can re-assert TVALID on next cycle",
        "Otherwise it holds TVALID and TDATA until TREADY=1")
    fix(s[27], "Can transfer up to data element", "At most one element transfers per cycle")

    # The squared-average IP was labelled as the polynomial one, and on every
    # stream diagram the output y[k] was labelled "Input stream".
    fix(s[29], "<a:t>Polynomial</a:t>", "<a:t>Squared</a:t>")
    fix(s[29], "<a:t>Eval</a:t>", "<a:t>average</a:t>")
    for n in (29, 37, 38, 40):
        fix_lowest(s[n], "<a:t>Input stream</a:t>", "<a:t>Output stream</a:t>")

    fix(s[36], "Each input is a image", "Each input is an image")
    fix(s[45], "Ends TLAST=1 and successful transfer", "Ends with the transfer that has TLAST=1")
    fix(s[45], "Stall beat (TVALID=1, TREADY=0)", "Stall beat (TVALID=1, TREADY=0): data held")
    fix(s[53], "Often write custom serialization",
        "Written by hand, or generated from a schema")


ROLE_WORDS = [("MASTER", "TRANSMITTER"), ("SLAVE", "RECEIVER"),
              ("Master", "Transmitter"), ("Slave", "Receiver"),
              ("master", "transmitter"), ("slave", "receiver")]


def rename_roles(slide):
    """master/slave -> transmitter/receiver, the AXI4-Stream spec's terms (AMBA
    IHI 0051B).  Unit 4 made the same move for AXI4-Lite, whose spec says
    manager and subordinate.  Confined to <a:t> runs, whole words only, so
    shape names and relationship ids do not move."""
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")
    n = 0

    def one(m):
        nonlocal n
        s = m.group(2)
        for old, new in ROLE_WORDS:
            s, k = re.subn(rf"\b{old}\b", new, s)
            n += k
        return f"{m.group(1)}{s}</a:t>"

    t = re.sub(r"(<a:t(?: [^>]*)?>)(.*?)</a:t>", one, t, flags=re.S)
    p.write_text(t, encoding="utf-8")
    return n


def widen_label(slide, text, grow):
    """A diagram label box sized for the old, shorter word: widen it about its centre."""
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")
    n = 0

    def one(m):
        nonlocal n
        sp = m.group(0)
        if "".join(re.findall(r"<a:t>([^<]*)</a:t>", sp)) != text:
            return sp
        off = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"/><a:ext cx="(\d+)" cy="(\d+)"/>', sp)
        x, y, cx, cy = (int(v) for v in off.groups())
        n += 1
        return sp.replace(off.group(0), f'<a:off x="{x - E(grow) // 2}" y="{y}"/>'
                                        f'<a:ext cx="{cx + E(grow)}" cy="{cy}"/>')

    t = re.sub(r"<p:sp>(?:(?!</p:sp>).)*?</p:sp>", one, t, flags=re.S)
    p.write_text(t, encoding="utf-8")
    return n


def add_shapes(slide, shapes):
    p = SLIDES / slide
    t = p.read_text(encoding="utf-8")
    p.write_text(t.replace("</p:spTree>", "".join(shapes) + "</p:spTree>"), encoding="utf-8")


def main():
    global ARGS, BUILD, SLIDES, FIGS
    ARGS = _parse_args()
    BUILD = (ARGS.work / "unpacked").resolve()
    SLIDES = BUILD / "ppt" / "slides"
    FIGS = ARGS.figs.resolve()
    scripts = ARGS.skill_scripts

    if BUILD.exists():
        shutil.rmtree(BUILD)
    zipfile.ZipFile(ARGS.src).extractall(BUILD)

    order = slide_order()
    titles = [slide_title(n) for n in order]
    if MIGRATED_MARKER in titles and not ARGS.force:
        raise SystemExit(f"{ARGS.src.name} already contains {MIGRATED_MARKER!r}: it has been "
                         "through this script.  This is a one-shot migration; see the docstring.")
    for pos, want in EXPECTED.items():
        got = titles[pos - 1]
        if got.strip() != want.strip():
            raise SystemExit(f"expected {want!r} at position {pos}, found {got!r}")
    old = {k + 1: n for k, n in enumerate(order)}

    # 1. structure, before any content edit: new slides duplicate a donor that
    # has only its layout relationship ("Title and Content"), then the final
    # order is written in one go.
    donor = old[4]
    assert (SLIDES / "_rels" / f"{donor}.rels").read_text(encoding="utf-8").count("<Relationship ") == 1
    final, jobs = [], []
    for item in PLAN:
        if item[0] == "old":
            _, pos, fn = item
            final.append(old[pos])
            if fn:
                jobs.append((old[pos], fn))
        else:
            made = sh([sys.executable, "add_slide.py", str(BUILD), donor], cwd=scripts)
            name = re.search(r"Created ppt/slides/(slide\d+\.xml)", made).group(1)
            final.append(name)
            jobs.append((name, item[1]))
    set_order(final)
    kept = [n for n in final if n not in {s for s, _ in jobs}]
    print(f"{len(final)} slides: {len(jobs)} built, {len(kept)} kept, "
          f"{len(order) - len(final) + sum(1 for i in PLAN if i[0] == 'new')} old dropped")

    # 2. content
    for name, fn in jobs:
        write(name, fn(Ids()))

    # 3. fixes and restyle on the kept slides
    text_fixes(old)
    renamed = sum(rename_roles(n) for n in kept)
    widened = sum(widen_label(n, "TRANSMITTER", 0.8) for n in kept)
    # Students meet master and slave in Vitis (and in its pragma docs), so the
    # terminology slide says once what the old words were.
    ids = Ids()
    ids.n = 900
    add_shapes(old[26], [label(ids, 1.2, 6.22, 11.0, 0.3,
                               "Called master and slave in older texts, and still in Vitis.",
                               sz=13)])
    print(f"role words renamed: {renamed}, label boxes widened: {widened}")
    retheme_accent1()
    for name in kept:
        restyle(name)
        recolour_diagrams(name)

    # 4. pack
    print(sh([sys.executable, "clean.py", str(BUILD)], cwd=scripts).strip())
    pack(ARGS.out)
    print("wrote", ARGS.out)


if __name__ == "__main__":
    main()
