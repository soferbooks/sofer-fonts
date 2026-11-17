"""Every glyph's left side bearing (hmtx) made its outline's xMin, as TrueType wants (Mordy, 2026-11-16:
"the nikkud not under the stroke of the ר, but a little to the left" - in the Seder HaYom app).

A glyph whose outline was redrawn (the shva na and dagesh chazak squares, the bold's thickened marks)
kept its old bearing.  Renderers that place an outline by its bearing - FreeType, so Chrome, Android's
WebView, the website - drew such a mark that far aside (Frank Sofer's shva na 17 units left, its
dagesh chazak 27, every mark of its bold 21 right), while the PDFs (Typst draws the outline where it
is) did not: the same font looked different in the app and in a book.  Run by the font builders after
they change outlines, and on every Hebrew font in fonts/:

    python scripts/fix_lsb.py [font.ttf ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parents[1] / "fonts"


def fix(path: Path) -> int:
    """The bearings put right; how many were wrong."""
    t = TTFont(path)
    if "glyf" not in t:
        return 0
    glyf, hmtx, n = t["glyf"], t["hmtx"], 0
    for name in t.getGlyphOrder():
        g = glyf[name]
        if not g.isComposite() and not getattr(g, "numberOfContours", 0):
            continue
        g.recalcBounds(glyf)
        adv, lsb = hmtx[name]
        if lsb != g.xMin:
            hmtx[name] = (adv, g.xMin)
            n += 1
    if n:
        t.save(path)
    return n


def hebrew_fonts() -> list[Path]:
    return [p for p in sorted(FONTS.glob("*.ttf")) if 0x05D0 in TTFont(p).getBestCmap()]


if __name__ == "__main__":
    for p in [Path(a) for a in sys.argv[1:]] or hebrew_fonts():
        print(f"{p.name}: {fix(p)} bearings put right")
