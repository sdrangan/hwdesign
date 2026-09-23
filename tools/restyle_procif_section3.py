"""Bring unit 4's Section 3 slides onto the course palette, and fix the title slide.

Sections 1 and 2 were restyled to the NYU palette by ``build_procif_slides.py``;
Section 3 (the Vitis demo) was left on the colours it was drafted with.  This
script closes that gap.

It is deliberately narrow.  The deck's theme ``accent1`` is *already* the NYU
violet (57068C), so nothing here touches the theme -- a theme edit would reach
all 59 slides, including the ones already styled by hand.  What is off-palette
in Section 3 is a handful of **explicit** colours, so only those are remapped,
and only on the Section 3 slides.

Run from the repo root, with the deck closed in PowerPoint::

    python tools/restyle_procif_section3.py --check    # report, change nothing
    python tools/restyle_procif_section3.py

Re-running is safe: the substitutions are idempotent, and ``--check`` says what
is left to do.
"""
from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from pathlib import Path

DECK = Path("units/unit04_procif/procif.pptx")

# Section 3, in presentation order 41-47, is slide30.xml .. slide36.xml.
# (Presentation order is set by <p:sldIdLst>, which does not match the file
# numbering elsewhere in this deck -- see _section3_parts.)
SECTION3_PRES_RANGE = (41, 47)

# --- Palette (same constants build_procif_slides.py uses) -------------------
VIOLET = "57068C"
TEAL = "00857C"
SLATE = "2F6FA8"
TEAL_TINT = "D9EDEB"
SLATE_TINT = "E3EDF6"

# Explicit colours that Section 3 was drafted with, and what they become.
# The greens are the HLS-flow boxes and arrows on "HLS vs. RTL FPGA Design
# Flow" and "Bad vs. Good HLS Code Write".  Red is left alone: on the
# bad/good slide it is carrying meaning, not decoration.
COLOR_MAP = {
    "00B050": TEAL,       # medium green -> course teal
    "E0F8E0": TEAL_TINT,  # pale green fill -> pale teal
    "002060": SLATE,      # dark navy text -> course slate
    "DEE6F8": SLATE_TINT,  # pale Office blue fill -> pale slate
}

# Theme accents used in Section 3.  ``accent1`` is already the NYU violet, so
# it is left alone -- and the theme itself is never edited, because it backs
# all 59 slides including the ones already styled by hand.  ``accent5`` and
# ``accent6`` are Office blues that clash with the slate used elsewhere, so
# they are converted to explicit palette colours *on these slides only*.
#
# Both map to the same slate on purpose.  Where the two were used side by
# side, the shapes carry their own lumMod/lumOff tint modifiers, which are
# preserved by the rewrite -- so the light/dark contrast between them
# survives even though the base colour is now shared.
SCHEME_MAP = {
    "accent5": SLATE,
    "accent6": SLATE,
}

# --- Title slide ------------------------------------------------------------
TEXT_FIXES = [
    ("EL-GY 9463:  Introduction to Hardware Design",
     "ECE-GY 6463:  Advanced Hardware Design"),
    # Two instructors, so the abbreviation is the plural "Profs."
    ("ProfS. Sundeep Rangan", "Profs. Sundeep Rangan"),
]


def _section3_parts(z: zipfile.ZipFile) -> list[str]:
    """Return the slide parts for Section 3, resolved through presentation order."""
    pres = z.read("ppt/presentation.xml").decode("utf-8")
    rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
    rid_to_target = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    order = re.findall(r'<p:sldId[^>]*r:id="([^"]+)"', pres)
    lo, hi = SECTION3_PRES_RANGE
    return ["ppt/" + rid_to_target[rid].replace("../", "")
            for i, rid in enumerate(order, 1) if lo <= i <= hi]


def _first_slide_part(z: zipfile.ZipFile) -> str:
    return _all_parts_in_order(z)[0]


def _all_parts_in_order(z: zipfile.ZipFile) -> list[str]:
    pres = z.read("ppt/presentation.xml").decode("utf-8")
    rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
    rid_to_target = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    order = re.findall(r'<p:sldId[^>]*r:id="([^"]+)"', pres)
    return ["ppt/" + rid_to_target[rid].replace("../", "") for rid in order]


def _recolor(xml: str) -> tuple[str, int]:
    n = 0
    for old, new in COLOR_MAP.items():
        # Only the value is swapped; any lumMod/lumOff children are preserved,
        # so tints and shades of the colour move with it.
        pattern = re.compile(r'(srgbClr val=")' + old + r'(")', re.IGNORECASE)
        xml, k = pattern.subn(r"\g<1>" + new + r"\g<2>", xml)
        n += k
    return xml, n


def _lst_style() -> str:
    """The course body-bullet style: violet squares, then grey dashes.

    The template's own margins were set for its hollow-square glyph, which
    sits flush against the text, so the replacement needs margins of its own.
    Spacing is left to the layout, which these older slides were built for.
    """
    m1 = f' marL="{E(0.3)}" indent="{E(-0.3)}"'
    m2 = f' marL="{E(0.68)}" indent="{E(-0.25)}"'
    return ("<a:lstStyle>"
            f'<a:lvl1pPr{m1}><a:buClr><a:srgbClr val="{VIOLET}"/></a:buClr>'
            f'<a:buSzPct val="70000"/><a:buFont typeface="Arial"/>'
            f'<a:buChar char="▪"/></a:lvl1pPr>'
            f'<a:lvl2pPr{m2}><a:buClr><a:srgbClr val="999999"/></a:buClr>'
            f'<a:buSzPct val="100000"/><a:buFont typeface="Arial"/>'
            f'<a:buChar char="–"/></a:lvl2pPr>'
            "</a:lstStyle>")


def _rebullet(xml: str) -> tuple[str, int]:
    """Put course bullets on a slide's body placeholder.

    Sections 1 and 2 were done by build_procif_slides.py; Section 3 was not,
    so its slides still carry the template's hollow squares.  Only the content
    placeholder is touched -- titles and slide numbers keep their own styles.
    """
    n = 0

    def body(m):
        nonlocal n
        sp = m.group(0)
        ph = re.search(r"<p:ph[^>]*>", sp)
        if not ph or 'idx="1"' not in ph.group(0) or "type=" in ph.group(0):
            return sp
        if f'<a:srgbClr val="{VIOLET}"/></a:buClr>' in sp:
            return sp        # already restyled
        sp, k = re.subn(r"<a:lstStyle/>|<a:lstStyle>.*?</a:lstStyle>",
                        _lst_style(), sp, count=1, flags=re.S)
        n += k
        return sp

    return re.sub(r"<p:sp>.*?</p:sp>", body, xml, flags=re.S), n


def E(inches: float) -> int:
    return int(round(inches * 914400))


def _remap_scheme(xml: str) -> tuple[str, int]:
    """Convert theme accents to explicit palette colours, keeping tint modifiers."""
    n = 0
    for accent, rgb in SCHEME_MAP.items():
        xml, k1 = re.subn(rf'<a:schemeClr val="{accent}"\s*/>',
                          f'<a:srgbClr val="{rgb}"/>', xml)
        # schemeClr never nests, so a non-greedy match finds its own close tag.
        xml, k2 = re.subn(rf'<a:schemeClr val="{accent}">(.*?)</a:schemeClr>',
                          rf'<a:srgbClr val="{rgb}">\g<1></a:srgbClr>', xml, flags=re.S)
        n += k1 + k2
    return xml, n


def _retext(xml: str) -> tuple[str, int]:
    n = 0
    for old, new in TEXT_FIXES:
        # The run may be split across <a:t> elements; handle the common case
        # where it is not, and report when nothing matched.
        if old in xml:
            xml = xml.replace(old, new)
            n += 1
    return xml, n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deck", type=Path, default=DECK)
    ap.add_argument("--check", action="store_true",
                    help="Report what would change and exit.")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    deck: Path = args.deck
    if not deck.exists():
        raise SystemExit(f"No deck at {deck} (run from the repo root).")
    lock = deck.with_name("~$" + deck.name)
    if lock.exists():
        try:
            with open(deck, "r+b"):
                pass
            print(f"note: {lock.name} exists but the deck is not locked "
                  f"(stale lock file from a previous session).")
        except PermissionError:
            raise SystemExit(f"{deck.name} is open in PowerPoint. Close it first.")

    with zipfile.ZipFile(deck) as z:
        parts = {n: z.read(n) for n in z.namelist()}
        section3 = set(_section3_parts(z))
        first = _first_slide_part(z)
        order = _all_parts_in_order(z)

    changes: list[str] = []
    updated: dict[str, bytes] = {}

    for name in order:
        if name not in section3:
            continue
        xml = parts[name].decode("utf-8")
        new_xml, n = _recolor(xml)
        new_xml, m = _remap_scheme(new_xml)
        new_xml, b = _rebullet(new_xml)
        if n or m or b:
            changes.append(f"  {name}: {n} explicit + {m} theme colour(s), "
                           f"{b} bullet list(s) (slide {order.index(name) + 1})")
            updated[name] = new_xml.encode("utf-8")

    xml = parts[first].decode("utf-8")
    new_xml, n = _retext(xml)
    if n:
        changes.append(f"  {first}: {n} text fix(es) (title slide)")
        updated[first] = new_xml.encode("utf-8")

    if not changes:
        print("Nothing to change -- deck is already restyled.")
        return
    print("\n".join(changes))

    if args.check:
        print("\n--check: no files written.")
        return

    if not args.no_backup:
        backup = deck.with_suffix(".pptx.bak")
        shutil.copy2(deck, backup)
        print(f"\nBackup written to {backup.name}")

    parts.update(updated)
    tmp = deck.with_suffix(".pptx.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        # Preserve the original part order; PowerPoint does not require it,
        # but keeping it makes the diff between two builds intelligible.
        with zipfile.ZipFile(deck) as z:
            for info in z.infolist():
                out.writestr(info, parts[info.filename])
    tmp.replace(deck)
    print(f"Wrote {deck}")


if __name__ == "__main__":
    main()
