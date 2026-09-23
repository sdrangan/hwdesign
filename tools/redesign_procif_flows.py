"""Redraw unit 4's two HLS-flow slides on the course palette.

Slides 43 ("HLS vs. RTL FPGA Design Flow") and 44 ("Bad vs. Good HLS Code
Write") were drafted with Office default shapes.  The earlier restyle pass
(``restyle_procif_section3.py``) put them on the course colours, but the
*layout* was still the original: two loose rows of rounded rectangles whose
arrangement carried no meaning.

These are rebuilt rather than recoloured, so the geometry can carry the point:

* Slide 43 right-aligns both flows, so the stages they **share** line up in a
  column.  The difference between RTL and HLS is then visible as what each one
  adds on the left, rather than as two unrelated rows.
* Slide 44 pairs each habit with its consequence on the same line.

The female-developer icon is kept.  It is reused as the existing picture
element, crop and all -- the source PNG has the words "Female Developer"
baked into it, and the slides hide that with ``srcRect``.  A freshly built
picture would put the caption back.

Usage, from the repo root, with the deck closed in PowerPoint::

    python tools/redesign_procif_flows.py --check
    python tools/redesign_procif_flows.py
"""
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from restructure_procif_section3 import (  # noqa: E402
    AMBER, AMBERTINT, DEEP, GRAYLINE, MUTED, SLATE, SLATELINE, SLATETINT,
    TEAL, TEALLINE, TEALTINT, TEXT, TINT, TINT2, VIOLET, WHITE,
    E, Ids, arrow, bullet, label, para, rpr, run, shape, slide_doc,
    sldnum_ph, textbox, title_ph,
)

# The two slides, by presentation position and expected title.
TARGETS = {
    43: "HLS vs. RTL FPGA Design Flow",
    44: "Bad vs. Good HLS Code Write",
}
ICON = "image56.png"          # the female-developer icon, shared by both
ICON_CROP = '<a:srcRect l="18038" t="-28" r="17239" b="23451"/>'
ICON_W, ICON_H = 1.21, 1.18

MARKER = "One flow, two front ends"   # a line only this script writes


def picture(ids: Ids, rid: str, x, y, w, h, crop: str = ICON_CROP) -> str:
    """An existing image, placed.  ``rid`` is the slide's own relationship id."""
    i = ids()
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{i}" name="Picture {i}"/>'
            f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/>'
            f'</p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/>{crop}'
            f'<a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{E(x)}" y="{E(y)}"/>'
            f'<a:ext cx="{E(w)}" cy="{E(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')


def chain(ids: Ids, boxes, right, y, h=0.88, bw=1.70, gap=0.30):
    """A right-aligned row of stage boxes joined by arrows.

    Right-aligned on purpose: the stages the two flows have in common then sit
    in the same column, and the extra work each flow does is what sticks out
    to the left.
    """
    out = []
    total = len(boxes) * bw + (len(boxes) - 1) * gap
    x0 = right - total
    for k, (text, fill, line, colour) in enumerate(boxes):
        x = x0 + k * (bw + gap)
        lines = text.split("|")
        paras = [para(lines[0], sz=13, color=colour, b=True, align="ctr")]
        for extra in lines[1:]:
            paras.append(para(extra, sz=11, color=MUTED, align="ctr"))
        out.append(shape(ids, x, y, bw, h, fill=fill, line=line, lw=1.25,
                         prst="roundRect", adj=10000, paras=paras))
        if k:
            out.append(arrow(ids, x - gap + 0.03, y + h / 2, x - 0.03, y + h / 2,
                             SLATE, lw=1.75))
    return out, x0


# ---------------------------------------------------------------- slide 43 --
def s_design_flow(ids: Ids, rid: str) -> list[str]:
    out = [title_ph(ids, "HLS vs. RTL Design Flow")]
    right = 12.45
    tool = (TINT, TINT2, VIOLET)          # the tool does this
    you = (TEALTINT, TEALLINE, TEAL)      # you write this

    # --- band 1: traditional RTL -------------------------------------
    out.append(label(ids, 0.85, 1.62, 11.6, 0.3,
                     "Traditional RTL — you write the hardware description",
                     sz=14, color=VIOLET, b=True))
    out.append(picture(ids, rid, 0.90, 2.02, ICON_W, ICON_H))
    out.append(label(ids, 0.62, 3.22, 1.78, 0.3, "you", sz=12, color=MUTED, align="ctr"))
    boxes, x0 = chain(ids, [
        ("SystemVerilog|written by hand", *you),
        ("RTL Simulation", *tool),
        ("Package", *tool),
    ], right, 2.18)
    out += boxes
    # The RTL row is shorter, so right-aligning it leaves a gap exactly where
    # the HLS row has its extra stages.  Say what is missing there rather than
    # running a long empty arrow across it.
    out.append(arrow(ids, 2.20, 2.62, x0 - 0.05, 2.62, TEAL, lw=1.75, dash=True))
    out.append(label(ids, 2.30, 2.20, x0 - 2.45, 0.34,
                     "no high-level model to simulate — the first thing "
                     "you write is hardware",
                     sz=12, color=MUTED, align="ctr"))

    out.append(arrow(ids, 0.85, 3.62, 12.45, 3.62, GRAYLINE, lw=1.0, head=False))

    # --- band 2: HLS --------------------------------------------------
    out.append(label(ids, 0.85, 3.78, 11.6, 0.3,
                     "HLS — you write behaviour, the tool writes the hardware",
                     sz=14, color=TEAL, b=True))
    out.append(picture(ids, rid, 0.90, 4.18, ICON_W, ICON_H))
    out.append(label(ids, 0.62, 5.38, 1.78, 0.3, "you", sz=12, color=MUTED, align="ctr"))
    boxes, x0 = chain(ids, [
        ("C / C++|written by hand", *you),
        ("C Simulation", *tool),
        ("C Synthesis", *tool),
        ("RTL Simulation", *tool),
        ("Package", *tool),
    ], right, 4.34)
    out += boxes
    out.append(arrow(ids, 2.20, 4.78, x0 - 0.05, 4.78, TEAL, lw=1.75))

    # the generated-RTL note, under the synthesis box
    out.append(label(ids, x0 + 2 * 2.0 - 0.15, 5.30, 2.6, 0.3,
                     "RTL generated here", sz=11, color=VIOLET, align="ctr", b=True))

    out.append(shape(ids, 0.85, 5.80, 11.6, 0.62, fill=SLATETINT, line=SLATELINE,
                     lw=1.0, anchor="ctr", paras=[
                         para("**One flow, two front ends** — the last stages are "
                              "identical.  HLS changes what you write, not what the "
                              "FPGA gets.", sz=14, color=TEXT, align="ctr")]))
    out.append(sldnum_ph(ids))
    return out


# ---------------------------------------------------------------- slide 44 --
def s_good_bad(ids: Ids, rid: str) -> list[str]:
    out = [title_ph(ids, "Bad vs. Good HLS Code")]
    tool = (TINT, TINT2, VIOLET)

    def band(y, tag, tag_fill, accent, tint, line, headline, points, bubble=None):
        o = [shape(ids, 0.85, y, 1.28, 0.42, fill=tag_fill, prst="roundRect", adj=40000,
                   paras=[para(tag, sz=13, color=WHITE, b=True, align="ctr")])]
        o.append(label(ids, 2.30, y + 0.02, 5.2, 0.36, headline, sz=17,
                       color=accent, b=True))
        o.append(textbox(ids, 2.30, y + 0.52, 5.2, 1.5,
                         [bullet(p, sz=14, clr=accent, spcBef=5) for p in points]))
        # the pipeline on the right
        ix = 7.95
        o.append(picture(ids, rid, ix, y + 0.36, ICON_W, ICON_H))
        bx, bw, bh = 9.60, 1.30, 0.80
        for k, name in enumerate(("HLS|tool", "RTL|tool")):
            x = bx + k * (bw + 0.42)
            head, sub = name.split("|")
            o.append(shape(ids, x, y + 0.55, bw, bh, fill=tint, line=line, lw=1.25,
                           prst="roundRect", adj=12000, paras=[
                               para(head, sz=13, color=accent, b=True, align="ctr"),
                               para(sub, sz=11, color=MUTED, align="ctr")]))
            x1 = ix + ICON_W + 0.06 if k == 0 else bx + bw + 0.06
            o.append(arrow(ids, x1, y + 0.95, x - 0.06, y + 0.95, accent, lw=1.75))
        if bubble:
            o.append(shape(ids, ix - 0.30, y - 0.52, 2.35, 0.78, fill=WHITE,
                           line=accent, lw=1.25, prst="wedgeRoundRectCallout",
                           paras=[para(bubble, sz=12, color=accent, b=True, align="ctr")]))
        return o

    out += band(1.72, "AVOID", AMBER, AMBER, AMBERTINT, "E7C3A6",
                "Treat the tool as a black box",
                ["You get RTL you cannot judge",
                 "Poor performance, and no idea why"])

    # No rule between the bands: the callout on the lower band sits above its
    # own headline, and a rule there cut straight through it.  The two pills
    # already separate the halves.
    out += band(4.20, "AIM FOR", TEAL, TEAL, TEALTINT, TEALLINE,
                "Keep a mental model of the RTL",
                ["What should happen on each clock cycle?",
                 "What resources should it use?"],
                bubble="what should the RTL look like?")

    out.append(shape(ids, 0.85, 6.00, 11.6, 0.55, fill=TINT, line=TINT2, lw=1.0,
                     anchor="ctr", paras=[
                         para("The tool schedules the cycles — but only you can "
                              "tell whether what it produced is any good.",
                              sz=14, color=TEXT, align="ctr")]))
    out.append(sldnum_ph(ids))
    return out


BUILDERS = {43: s_design_flow, 44: s_good_bad}


# ================================================================ plumbing ==
def slide_order(build: Path) -> list[str]:
    pres = (build / "ppt" / "presentation.xml").read_text(encoding="utf-8")
    rels = (build / "ppt" / "_rels" / "presentation.xml.rels").read_text(encoding="utf-8")
    rid = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    return [rid[r].replace("../", "").split("/")[-1]
            for r in re.findall(r'<p:sldId[^>]*r:id="([^"]+)"', pres)]


def slide_title(build: Path, name: str) -> str:
    xml = (build / "ppt" / "slides" / name).read_text(encoding="utf-8")
    t = [x.strip() for x in re.findall(r"<a:t>(.*?)</a:t>", xml, re.S) if x.strip()]
    return t[0] if t else ""


def icon_rid(build: Path, name: str) -> str:
    rels = (build / "ppt" / "slides" / "_rels" / f"{name}.rels").read_text(encoding="utf-8")
    m = re.search(rf'Id="([^"]+)"[^>]*media/{ICON}"', rels)
    if not m:
        raise SystemExit(f"{name}: no relationship to {ICON}")
    return m.group(1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Redraw unit 4's HLS-flow slides.")
    ap.add_argument("--deck", type=Path,
                    default=Path("units/unit04_procif/procif.pptx"))
    # Scratch goes to the system temp directory, not into the repo --
    # unpacking a deck produces a few hundred files, and
    # build_procif_slides.py already sets this precedent.
    ap.add_argument("--work", type=Path,
                    default=Path(tempfile.gettempdir()) / "procif_flows")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    deck: Path = args.deck
    if not deck.exists():
        raise SystemExit(f"No deck at {deck} (run from the repo root).")
    try:
        with open(deck, "r+b"):
            pass
    except PermissionError:
        raise SystemExit(f"{deck.name} is open in PowerPoint. Close it first.")

    build = (args.work / "unpacked").resolve()
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    with zipfile.ZipFile(deck) as z:
        z.extractall(build)

    order = slide_order(build)
    plan = []
    for pos, want in TARGETS.items():
        name = order[pos - 1]
        got = slide_title(build, name)
        if MARKER in (build / "ppt" / "slides" / name).read_text(encoding="utf-8"):
            raise SystemExit(f"slide {pos} has already been redrawn.  Nothing to do.")
        if got != want:
            raise SystemExit(f"expected '{want}' at position {pos}, found '{got}'")
        plan.append((pos, name, icon_rid(build, name)))
        print(f"  {pos}  {name:<14} {want}  (icon rel {plan[-1][2]})")

    if args.check:
        print("\n--check: no files written.")
        return

    for pos, name, rid in plan:
        (build / "ppt" / "slides" / name).write_text(
            slide_doc(BUILDERS[pos](Ids(), rid)), encoding="utf-8")
        print(f"  redrew {name}")

    backup = deck.with_suffix(".pptx.bak")
    shutil.copy2(deck, backup)
    tmp = deck.with_suffix(".pptx.tmp")
    if tmp.exists():
        tmp.unlink()
    ct = build / "[Content_Types].xml"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ct, "[Content_Types].xml")
        for f in sorted(p for p in build.rglob("*") if p.is_file()):
            if f != ct:
                z.write(f, f.relative_to(build).as_posix())
    tmp.replace(deck)
    print(f"backup: {backup.name}\nwrote {deck}")


if __name__ == "__main__":
    main()
