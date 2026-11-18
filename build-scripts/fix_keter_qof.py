"""Keter Aram Tsova's vowels under ק in the middle of the room beside its leg, as under the other
letters (Mordy, 2026-10-25: "fix the nikkud under the ק to be more in line with the other
letters" - the font set them against the letter's right edge, and raised them beside the leg
before a meteg).  Every mark-to-base anchor of ק
for the vowels below moved so a kamatz is centred between the leg and the right edge; the hataf
vowels (wider) stay.  Changes the font in place: run it before scripts/place_meteg.py, then
scripts/clear_meteg.py.

    .venv/Scripts/python scripts/fix_keter_qof.py
"""
from __future__ import annotations

import io
from pathlib import Path

from fontTools.pens.pointInsidePen import PointInsidePen
from fontTools.ttLib import TTFont

FONT = Path(__file__).resolve().parents[1] / "fonts" / "KeterAramTsova.ttf"
QOFS = ("qof", "qofdagesh", "qofdagesh.xz")
KAMATZ_X = 740            # (the font's own anchor for the kamatz under ק)
SIMPLE = {"sheva", "shevana", "hiriq", "tsere", "segol", "patah", "qamats", "qubuts", "qamatsqatan", "meteg"}


def main() -> str:
    t = TTFont(io.BytesIO(FONT.read_bytes()))
    if "fixed: qof" in " ".join(r.toUnicode() for r in t["name"].names if r.nameID == 5):
        return "already done"
    gs = t.getGlyphSet()
    # the leg's right edge, just under the line, and the letter's right edge
    leg = max(x for x in range(0, 1200, 4) if _inside(gs, "qof", x, -150) and x < 600)
    g = t["glyf"]["qof"]
    g.recalcBounds(t["glyf"])
    target = round((leg + g.xMax) / 2)
    gpos = t["GPOS"].table
    moved = 0
    for lk in gpos.LookupList.Lookup:
        if lk.LookupType != 4:
            continue
        for st in lk.SubTable:
            classes = {}
            for name, rec in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord):
                classes.setdefault(rec.Class, set()).add(name)
            for q in QOFS:
                if q not in st.BaseCoverage.glyphs:
                    continue
                rec = st.BaseArray.BaseRecord[st.BaseCoverage.glyphs.index(q)]
                for c, anchor in enumerate(rec.BaseAnchor):
                    marks = classes.get(c, set())
                    if anchor is None or not marks or not marks <= SIMPLE:
                        continue
                    if "qamats" in marks:
                        # (the kamatz's anchor - 740 in the font - to the middle; the anchors the
                        #  font uses beside a meteg keep their distance from it)
                        anchor.XCoordinate += target - KAMATZ_X
                        # (and at the line's height: the font raised it beside the leg when a
                        #  meteg followed - Mordy, 2026-10-25: "the nikkud under the ק is high up")
                        anchor.YCoordinate = 0
                    else:
                        anchor.XCoordinate = target      # (shva, chirik, a lone meteg)
                    moved += 1
    for r in t["name"].names:
        if r.nameID == 5:
            r.string = r.toUnicode() + "; Sofer: fixed: qof"
    buf = io.BytesIO()
    t.save(buf)
    FONT.write_bytes(buf.getvalue())
    return f"{moved} anchors of ק moved: vowels centred at {target} (leg {leg}, edge {g.xMax})"


def _inside(gs, name, x, y) -> bool:
    pen = PointInsidePen(gs, (x, y))
    gs[name].draw(pen)
    return pen.getResult()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(main())
