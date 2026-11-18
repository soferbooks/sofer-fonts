"""Drugulin's ע drawn with Frank Sofer's base (Mordy, 2026-11-17, after five rounds of pictures): Culmus'
Drugulin CLM ע hangs a long diagonal tail 379 units below the line, so its vowels were set far to the right,
under the letter before (וַֽעֲבַדְתֶּם touched).  Mordy: "make the frank ע but with the visuals such as ו, ז,
and thickness of drugulin".  Kept: Drugulin's ו (right arm) and ז (left arm).  Drawn anew, as Frank Sofer's:
the inside edge between the arms straight; the ו's right edge straight down, rounding into the base (nothing
sticking out); the base as thick as Drugulin's ב's (its top level with the ב's top, one straight line from
the tip to the ו rising 40 units toward the arms - "3"); its bottom sloping down to the left, the tip dipping
38 below the line (1/8 of the base, as Frank's dips under his ב), the tip cut on a slant.  The marks below
under the ink's middle and as high as under the ב ("raise the patach a bit to align with the other nikkud").

    .venv/Scripts/python scripts/drugulin_ayin.py <Drugulin.ttf>      (in place)
"""
from __future__ import annotations

import sys
from array import array
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
from fontTools.ttLib.tables.ttProgram import Program

# (the chosen one: "S2" of the trials)
SHAPE = dict(T=272, BR=70, BL=-38, P=0, tip=60, slant=45, frank=True, straight=40)


def outline(c, v):
    T, BR, BL, P, tip, sl = v["T"], v["BR"], v["BL"], v["P"], v["tip"], v["slant"]
    on, off = 1, 0
    rise = v.get("straight")
    def top(x):          # (the top line: straight from the tip, x=tip+sl, to the ו, x=588)
        if rise is None:
            return T
        return round(T - rise * (588 - x) / (588 - (tip + sl)))
    pts = [(on if i in ON else off, *c[i]) for i in range(0, 39)]          # (the ז's top and right edge to 38)
    pts += [(off, 425, top(425) + 120), (off, 440, top(440) + 30), (on, 448, top(448)),   # (into the base top)
            (on, 588, top(588)),                                              # (the straight edge between the arms)
            (off, 612, T + 15), (off, 628, T + 70)]                           # (curving up into the ו's left edge)
    pts += [(on if i in ON else off, *c[i]) for i in range(45, 86)]          # (the ו, to its right edge at 85)
    foot = 712
    if v.get("frank"):
        # (Frank's base: the ו's right edge straight down, rounding into a bottom that slopes down to the
        #  left; the tip cut on a slant; the top rising a little toward the ז)
        if rise is None:
            pts += [(off, 722, T + 90), (on, foot, T), (off, foot, BR), (on, 430, (BR + BL) // 2 + 5),
                    (on, tip + 25, BL), (on, tip, BL + 10), (on, tip + sl, T - 35), (on, 350, T), (off, 368, T + 12)]
        else:              # (the top straight: the tip's top on the line, the ז's left edge meeting it at a corner)
            pts += [(off, 722, T + 90), (on, foot, T), (off, foot, BR), (on, 430, (BR + BL) // 2 + 5),
                    (on, tip + 25, BL), (on, tip, BL + 10), (on, tip + sl, top(tip + sl)), (on, 352, top(352))]
    else:
        pts += [(off, 722, T + 90), (on, foot, T + 20),                          # (the ו's right edge to the foot)
                (on, foot + P, T - 25), (on, foot + P, BR),                       # (sticking out past it)
                (on, tip + sl + 20, BL), (on, tip, BL),                            # (the bottom, the tip)
                (on, tip + sl, T - 10), (on, 350, T), (off, 368, T + 12)]          # (the tip's slant, the top edge)
    pts += [(on if i in ON else off, *c[i]) for i in range(105, 110)]         # (the ז's left edge, up)
    return pts


ON: set = set()


def make(src, out, name, v):
    t = TTFont(src)
    glyf = t["glyf"]
    for n in [n for n in t.getGlyphOrder() if n == "ayin" or n.startswith("ayin.")]:
        g = glyf[n]
        c = list(g.coordinates)
        ON.clear()
        ON.update(i for i, f in enumerate(g.flags) if f & 1)
        pts = outline(c, v)
        g.coordinates = GlyphCoordinates([(x, y) for _, x, y in pts])
        g.flags = array("B", [f for f, _, _ in pts])
        g.endPtsOfContours = [len(pts) - 1]
        g.program = Program()
        g.program.fromBytecode(b"")
        g.recalcBounds(glyf)
        t["hmtx"][n] = (max(t["hmtx"][n][0], g.xMax + 60), g.xMin)
    gs = t.getGlyphSet()

    def bounds(n):
        bp = BoundsPen(gs)
        gs[n].draw(bp)
        return bp.bounds
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos" or "ayin" not in st.BaseCoverage.glyphs:
                continue
            below = {}
            for mi, mn in enumerate(st.MarkCoverage.glyphs):
                if glyf[mn].numberOfContours and bounds(mn)[3] <= 60:
                    mx0, _, mx1, _ = bounds(mn)
                    rec = st.MarkArray.MarkRecord[mi]
                    below.setdefault(rec.Class, []).append((mx0 + mx1) / 2 - rec.MarkAnchor.XCoordinate)
            x0, _, x1, _ = bounds("ayin")
            for n in ("ayin", "ayin.alt"):
                if n in st.BaseCoverage.glyphs:
                    rec = st.BaseArray.BaseRecord[st.BaseCoverage.glyphs.index(n)]
                    bet = (st.BaseArray.BaseRecord[st.BaseCoverage.glyphs.index("bet")].BaseAnchor
                           if "bet" in st.BaseCoverage.glyphs else None)
                    for cl, offs in below.items():
                        if rec.BaseAnchor[cl] is not None:
                            rec.BaseAnchor[cl].XCoordinate = round((x0 + x1) / 2 - sum(offs) / len(offs))
                            # (as high as under the ב: the ע's base now sits on the line as the ב's does -
                            #  Mordy: "raise the patach a bit to align with the other nikkud")
                            if bet is not None and bet[cl] is not None:
                                rec.BaseAnchor[cl].YCoordinate = bet[cl].YCoordinate
    # the build's rules for words with the old ע (its own collision fixes, after Frank Sofer's lookups):
    # tuned to the old tail, dropped - scripts/finish_mekorot_fonts.py makes new ones
    base = len(TTFont(Path(__file__).resolve().parents[1] / "fonts" / "FrankSofer.ttf")["GPOS"].table.LookupList.Lookup)
    ayins = {n for n in t.getGlyphOrder() if n == "ayin" or n.startswith("ayin.")}
    for lk in t["GPOS"].table.LookupList.Lookup[base:]:
        keep = []
        for st in lk.SubTable:
            sub = getattr(st, "ExtSubTable", st)
            covs = [*getattr(sub, "BacktrackCoverage", []), *getattr(sub, "InputCoverage", []),
                    *getattr(sub, "LookAheadCoverage", [])]
            if not (type(sub).__name__ == "ChainContextPos" and any(ayins & set(c.glyphs) for c in covs)):
                keep.append(st)
        lk.SubTable, lk.SubTableCount = keep, len(keep)
    if name:                      # (a trial under another name)
        for r in t["name"].names:
            if r.nameID in (1, 4, 16):
                r.string = name
    t.save(out)


if __name__ == "__main__":
    path = Path(sys.argv[1])
    make(path, path, None, SHAPE)
    print(f"{path.name}: the ayin drawn with Frank Sofer's base")
