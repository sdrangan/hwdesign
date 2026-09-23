"""Add two Waveflow slides to unit 4, between the demo and its limitations.

Students have already run Waveflow by this point in the unit -- the demo's
``scalar_fun_build.py`` is a Waveflow build graph -- but the deck never says
so, which leaves the tool invisible rather than optional.  These two slides
name it, show what its *modelling* layer adds on top of the build layer they
have used, and say plainly when that is worth paying for.

They go before "Limitations of AXI4-Lite for Data" rather than after it, so
the section still ends on the handoff to AXI4-Stream.

Content checked against the Waveflow docs (sdrangan.github.io/waveflow), not
written from memory.  Two things the flow does that are easy to state
loosely and get wrong:

* Function and timing are checked at *different* stages.  C-simulation
  compares the generated testbench's result against the Python golden; RTL
  co-simulation compares measured cycles against the Python estimate.  It is
  not one co-simulation step confirming both.
* Only the *sequential* testbench lowers to Vitis.  The concurrent system
  simulation -- host and kernel as two processes over a real link -- has
  nothing to lower onto, because a Vitis C++ testbench is a single
  straight-line ``int main()``.  The docs call this fundamental, and it is
  the honest limitation for the comparison slide.

The hero diagram is redrawn rather than embedded.  The source SVG uses CSS
``light-dark()`` colour pairs, which PowerPoint's SVG renderer is unlikely to
resolve, and redrawing puts it on the course palette exactly.  The AI chip in
the original is dropped: it is not what this lecture is about.

Usage, from the repo root, with the deck closed in PowerPoint::

    python tools/add_procif_waveflow_slides.py --check
    python tools/add_procif_waveflow_slides.py
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from restructure_procif_section3 import (  # noqa: E402
    AMBER, AMBERTINT, GRAYLINE, MUTED, SLATE, SLATELINE, SLATETINT,
    TEAL, TEALLINE, TEALTINT, TEXT, TINT, TINT2, VIOLET, WHITE,
    Ids, arrow, bullet, find_skill_scripts, label, para, run, rpr, shape,
    sh, slide_doc, sldnum_ph, textbox, title_ph,
)

ANCHOR_POS, ANCHOR_TITLE = 50, "The Demo: a Scalar Function IP"
NEXT_TITLE = "Limitations of AXI4-Lite for Data"
MARKER = "From waveform to silicon"      # a line only this script writes

DOCS_URL = "sdrangan.github.io/waveflow"


# ------------------------------------------------------------ the diagram --
def hero(ids: Ids, x0: float, y0: float) -> list[str]:
    """The Waveflow flow, redrawn: one model, two branches, two loops.

    Laid out so the slow branch can return down the right-hand edge without
    crossing the Python-sim box -- the columns are narrower than the region
    for exactly that reason.
    """
    bw, bh = 2.05, 0.70
    lx, rx = x0, x0 + 2.75                 # column origins
    ty, my = y0, y0 + 1.30                 # top row, middle row
    bar_y = y0 + 2.60
    right_edge = rx + bw + 0.42            # the slow loop's return lane
    out = []

    def box(x, y, head, sub, fill, line, colour):
        return shape(ids, x, y, bw, bh, fill=fill, line=line, lw=1.25,
                     prst="roundRect", adj=12000, paras=[
                         para(head, sz=13, color=colour, b=True, align="ctr"),
                         para(sub, sz=10, color=MUTED, align="ctr")])

    out += [
        box(lx, ty, "HLS codegen", "typed · generated", TINT, TINT2, VIOLET),
        box(rx, ty, "RTL synth / sim", "slow · cycle-exact", TINT, TINT2, VIOLET),
        box(lx, my, "Python model", "architecture · algorithm", TEALTINT, TEALLINE, TEAL),
        box(rx, my, "Python sim", "fast · bit-exact", TEALTINT, TEALLINE, TEAL),
    ]

    # the build path: model up to codegen, codegen across to RTL
    out.append(arrow(ids, lx + bw / 2, my - 0.04, lx + bw / 2, ty + bh + 0.04,
                     VIOLET, lw=1.75))
    out.append(arrow(ids, lx + bw + 0.04, ty + bh / 2, rx - 0.04, ty + bh / 2,
                     VIOLET, lw=1.75))
    # the fast path: model across to the Python simulator
    out.append(arrow(ids, lx + bw + 0.04, my + bh / 2, rx - 0.04, my + bh / 2,
                     TEAL, lw=1.75))

    # the two loops, both feeding the iterate bar
    out.append(arrow(ids, rx + bw / 2, my + bh + 0.04, rx + bw / 2, bar_y - 0.04,
                     TEAL, lw=1.75))
    out.append(label(ids, rx + bw / 2 + 0.06, my + bh + 0.10, 1.2, 0.26,
                     "fast loop", sz=10, color=TEAL))
    out.append(arrow(ids, right_edge, ty + bh / 2, right_edge, bar_y - 0.04,
                     SLATE, lw=1.75))
    out.append(label(ids, right_edge + 0.06, ty + bh + 0.30, 1.2, 0.26,
                     "slow loop", sz=10, color=SLATE))
    # and the bar feeding the model back
    out.append(arrow(ids, lx + bw / 2, bar_y - 0.04, lx + bw / 2, my + bh + 0.04,
                     TEAL, lw=1.75))

    out.append(shape(ids, lx, bar_y, right_edge - lx + 0.22, 0.46,
                     fill=SLATETINT, line=SLATELINE, lw=1.0, prst="roundRect",
                     adj=30000, paras=[
                         para("design · verify · calibrate · iterate",
                              sz=12, color=TEXT, b=True, align="ctr")]))
    return out


# ---------------------------------------------------------------- slide 51 --
def s_waveflow_intro(ids: Ids) -> list[str]:
    out = [title_ph(ids, "Waveflow: a Python Model First")]

    out.append(label(ids, 0.75, 1.58, 11.7, 0.3,
                     "“From waveform to silicon — in Python.”  "
                     "Describe the datapath once, simulate it fast and bit-exact, "
                     "and generate the hardware from the same source.",
                     sz=13, color=MUTED))

    out += hero(ids, 0.95, 2.08)

    out.append(label(ids, 7.35, 2.02, 5.1, 0.3, "THE FLOW, FOR THIS SAME IP",
                     sz=11, color=MUTED, b=True))
    steps = [
        ("Model it in Python", "the kernel, and its registers as a `VitisRegMap`"),
        ("Simulate in Python", "function, and **cycle-approximate** timing"),
        ("Generate the Vitis C++", "kernel and testbench; you keep the compute hook"),
        ("C-simulation checks **function**", "against the Python result"),
        ("Co-simulation checks **timing**", "against the Python estimate"),
    ]
    y = 2.38
    for n, (head, sub) in enumerate(steps, 1):
        out.append(shape(ids, 7.35, y, 0.34, 0.34, fill=VIOLET, prst="ellipse",
                         paras=[para(str(n), sz=11, color=WHITE, b=True, align="ctr")]))
        out.append(textbox(ids, 7.82, y - 0.04, 4.6, 0.6, [
            para(head, sz=13, color=TEXT, b=True),
            para(sub, sz=11, color=MUTED)]))
        y += 0.62

    out.append(shape(ids, 0.75, 5.72, 11.7, 0.62, fill=TEALTINT, line=TEALLINE,
                     lw=1.0, anchor="ctr", paras=[
                         para("You have already run part of it: "
                              "`scalar_fun_build.py` **is** a Waveflow build graph.  "
                              "What is new above is the modelling layer.",
                              sz=14, color=TEXT, align="ctr")]))
    out.append(sldnum_ph(ids))
    return out


# ---------------------------------------------------------------- slide 52 --
def s_waveflow_vs_vitis(ids: Ids) -> list[str]:
    out = [title_ph(ids, "Waveflow vs. Native Vitis")]
    top, ph, bh = 1.66, 0.56, 3.30
    lx, rx, w = 0.75, 6.85, 5.7

    out += [
        shape(ids, lx, top, w, ph, fill=AMBER, prst="roundRect", adj=14000,
              paras=[para("What it costs", sz=17, color=WHITE, b=True, align="ctr")]),
        shape(ids, lx, top + ph, w, bh, fill=AMBERTINT, line="E7C3A6", lw=1.0),
        textbox(ids, lx + 0.34, top + ph + 0.20, w - 0.68, bh - 0.4, [
            bullet("A **Python layer** between you and the tool — one more "
                   "thing to learn, and to debug", sz=14, clr=AMBER, spcBef=0),
            bullet("Its own vocabulary — `VitisRegMap`, `HostActivated`, "
                   "`SeqTB` — before you see any hardware", sz=14, clr=AMBER),
            bullet("**Early-stage research software**, by its own description", sz=14, clr=AMBER),
            # The markup parser handles **bold** and `code`, not *italics*.
            bullet("Only the **sequential** testbench lowers to Vitis: a C++ "
                   "testbench is one straight-line `main()`, so a concurrent "
                   "model has nothing to lower onto", sz=14, clr=AMBER),
        ]),
    ]

    out += [
        shape(ids, rx, top, w, ph, fill=TEAL, prst="roundRect", adj=14000,
              paras=[para("What it buys", sz=17, color=WHITE, b=True, align="ctr")]),
        shape(ids, rx, top + ph, w, bh, fill=TEALTINT, line=TEALLINE, lw=1.0),
        textbox(ids, rx + 0.34, top + ph + 0.20, w - 0.68, bh - 0.4, [
            bullet("**One source of truth** — simulation, generated C++ and "
                   "the register map all come from the same Python", sz=14,
                   clr=TEAL, spcBef=0),
            bullet("A model you can **explore in seconds**, instead of minutes "
                   "of synthesis per idea", sz=14, clr=TEAL),
            bullet("The build **checks itself**: the Python result is the golden "
                   "the C-simulation is graded against", sz=14, clr=TEAL),
            bullet("Timing you can **trust before synthesis**, because the "
                   "estimate is checked against measured cycles", sz=14, clr=TEAL),
        ]),
    ]

    out.append(shape(ids, 0.75, 5.62, 11.8, 0.92, fill=TINT, line=VIOLET, lw=1.25,
                     anchor="ctr", inset=0.24, paras=[
                         para("For `scalar_fun`, **nothing** — the kernel is four "
                              "lines, and a model of it is pure overhead.", sz=15,
                              color=TEXT, align="ctr"),
                         para("The payoff starts when the algorithm is worth exploring "
                              "before it is worth synthesizing.  " + DOCS_URL,
                              sz=14, color=VIOLET, b=True, align="ctr", spcBef=6)]))
    out.append(sldnum_ph(ids))
    return out


NEW_SLIDES = [
    ("Waveflow: a Python Model First", s_waveflow_intro),
    ("Waveflow vs. Native Vitis", s_waveflow_vs_vitis),
]


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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deck", type=Path,
                    default=Path("units/unit04_procif/procif.pptx"))
    ap.add_argument("--work", type=Path,
                    default=Path(tempfile.gettempdir()) / "procif_waveflow")
    ap.add_argument("--skill-scripts", type=Path, default=None)
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

    scripts = args.skill_scripts or find_skill_scripts()
    build = (args.work / "unpacked").resolve()
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    with zipfile.ZipFile(deck) as z:
        z.extractall(build)

    order = slide_order(build)
    titles = [slide_title(build, n) for n in order]
    if any(MARKER in (build / "ppt" / "slides" / n).read_text(encoding="utf-8")
           for n in order):
        raise SystemExit("The Waveflow slides are already in the deck.  Nothing to do.")
    if titles[ANCHOR_POS - 1] != ANCHOR_TITLE:
        raise SystemExit(f"expected '{ANCHOR_TITLE}' at {ANCHOR_POS}, "
                         f"found '{titles[ANCHOR_POS - 1]}'")
    if titles[ANCHOR_POS] != NEXT_TITLE:
        raise SystemExit(f"expected '{NEXT_TITLE}' at {ANCHOR_POS + 1}, "
                         f"found '{titles[ANCHOR_POS]}'")

    print(f"anchor: {ANCHOR_POS} {ANCHOR_TITLE} ({order[ANCHOR_POS - 1]})")
    print(f"next:   {ANCHOR_POS + 1} {NEXT_TITLE} (stays last in the section)")
    for t, _ in NEW_SLIDES:
        print(f"  + {t}")
    if args.check:
        print("\n--check: no files written.")
        return

    donor = None
    for name in order:
        rels = (build / "ppt" / "slides" / "_rels" / f"{name}.rels").read_text(encoding="utf-8")
        if len(re.findall(r"<Relationship ", rels)) != 1:
            continue
        m = re.search(r"slideLayout(\d+)\.xml", rels)
        if not m:
            continue
        layout = (build / "ppt" / "slideLayouts" / f"slideLayout{m.group(1)}.xml")
        nm = re.search(r'name="([^"]+)"', layout.read_text(encoding="utf-8")[:2000])
        if nm and nm.group(1) == "Title and Content":
            donor = name
            break
    if donor is None:
        raise SystemExit("no single-relationship slide on the 'Title and Content' layout")

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

    print(sh([sys.executable, "clean.py", str(build)], cwd=scripts).strip())

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
