"""David Libre's ק: its leg is drawn joined to the roof (one outline), so in the headings the
"stick" touched the roof (Mordy, 2026-10-21).  Here the leg is cut off just under the roof's
inner line, leaving a small gap as in a printed David ק, its top cut on the same slant as
the leg's own bottom (Mordy: "match the bottom of its own ק").  (David Libre is OFL with no
reserved names: it may be changed under its own name.)

    python scripts/fix_david_qof.py        (changes the files in fonts/; done already: left)
"""
from __future__ import annotations

from pathlib import Path

from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parents[1] / "fonts"
# the outline's points, by number: the roof (with the letter's right side) and the leg (each
# file's own numbering - checked against the coordinates below before anything is changed)
CUTS = {
    "DavidLibre-Bold.ttf": {"roof": (10, 70), "leg": (73, 7), "check": {7: (249, 627), 10: (192, 681), 70: (536, 688), 73: (486, 629), 77: (477, -183), 2: (294, -362)},
                            "bottom": (77, 2)},
    "DavidLibre-Regular.ttf": {"roof": (10, 58), "leg": (61, 6), "check": {6: (228, 778), 10: (133, 821), 58: (414, 821), 61: (387, 792), 70: (393, -238), 2: (270, -393)},
                               "bottom": (70, 2)},
}
GAP = 0.045          # (the gap between the roof and the leg: its share of the em)


def fix(path: Path, cut: dict) -> str:
    t = TTFont(path)
    name = t.getBestCmap()[0x05E7]
    glyf = t["glyf"]
    g = glyf[name]
    if g.numberOfContours != 1:
        return f"{path.name}: done already"
    coords, ends, flags = g.getCoordinates(glyf)
    pts = [(tuple(coords[i]), bool(flags[i] & 1)) for i in range(len(coords))]
    for i, xy in cut["check"].items():
        assert pts[i][0] == xy and pts[i][1], f"{path.name}: point {i} is {pts[i]}, not {xy}"
    n = len(pts)
    r0, r1 = cut["roof"]
    l0, l1 = cut["leg"]
    roof = pts[r0:r1 + 1]
    leg = [pts[i % n] for i in range(l0, n + l1 + 1)]
    # the leg's top: cut level, the gap under the roof's lowest inner point
    under = min(p[0][1] for p in roof[:1] + roof[-1:])
    top = round(under - GAP * t["head"].unitsPerEm)
    (lx_r, ly_r), (lx_l, ly_l) = leg[0][0], leg[-1][0]
    leg[0] = ((lx_r, min(ly_r, top)), True)
    # (the slant of the leg's bottom: from where its right side starts to turn to its tip)
    (bx_r, by_r), (bx_l, by_l) = pts[cut["bottom"][0]][0], pts[cut["bottom"][1]][0]
    slant = (by_r - by_l) / (bx_r - bx_l)
    leg[-1] = ((lx_l, min(ly_l, top) - round(slant * (lx_r - lx_l))), True)
    pen = TTGlyphPen(None)
    for contour in (roof, leg):
        _draw(pen, contour)
    new = pen.glyph()
    glyf[name] = new
    new.recalcBounds(glyf)
    t.save(path)
    return f"{path.name}: the ק's leg parted from its roof"


def _draw(pen, contour):
    """A closed TrueType contour (on / off-curve points) through a pen."""
    start = next(i for i, (_, on) in enumerate(contour) if on)
    seq = contour[start:] + contour[:start]
    pen.moveTo(seq[0][0])
    offs = []
    for xy, on in seq[1:] + [seq[0]]:
        if on:
            if offs:
                pen.qCurveTo(*offs, xy)
                offs = []
            else:
                pen.lineTo(xy)
        else:
            offs.append(xy)
    pen.closePath()


if __name__ == "__main__":
    for f, cut in CUTS.items():
        print(fix(FONTS / f, cut))
