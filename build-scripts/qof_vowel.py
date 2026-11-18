"""A vowel alone under ק under the lowest part of its body, near the leg (Mordy, 2026-11-18:
"the ק puts nikkud as if there's a meteg when there's no need - the nikkud can be closer to the leg").

Taamey D (and so Frank Sofer and the fonts made from it) sets every vowel under ק at the letter's right
edge, leaving room by the leg for a meteg - also when there is none.  Here a vowel with no other mark under
the letter is moved left to sit under the lowest part of the body that curves down (Mordy, 2026-11-18:
"as close as possible, sitting underneath the lowest part of the body that curves down"), never nearer
the leg than GAP.  With a meteg or a ta'am under the letter too, nothing changes (the
meteg pair is placed by make_frank_sofer.qof_with_meteg).  One contextual lookup, last in "mark": its first
rule (ק, the vowel, then another mark under the line) matches and does nothing; the second moves the vowel.

    .venv/Scripts/python scripts/qof_vowel.py <font.ttf> [...]     (in place)

Run once on a freshly built font, after its other placement steps; then the collision fixer and clear_meteg.
"""
from __future__ import annotations

import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.otlLib import builder as otl
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_frank_sofer import _runs  # noqa: E402

LOW = 30                   # (units of 2048: how far above the body's lowest point still counts as its lowest part)
GAP = 60                   # (units of 2048: the vowel's left end at least this far from the leg - Frank Ruehl CLM
                           #  keeps 72-97; Frank Sofer had 56-290, Vilna Sofer 107-341)
FORMS = ("", "ּ")
VOWELS = [chr(c) for c in range(0x05B0, 0x05BC) if c not in (0x05B9, 0x05BA)] + ["ׇ", "׈"]


def _shape(font, T, gs, text):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    x, out = 0, []
    for i, p in zip(buf.glyph_infos, buf.glyph_positions):
        name = T.getGlyphName(i.codepoint)
        b = BoundsPen(gs)
        gs[name].draw(b)
        if b.bounds:
            out.append((name, x + p.x_offset + b.bounds[0], x + p.x_offset + b.bounds[2], x))
        x += p.x_advance
    return out


def _lowest(T: TTFont, name: str, start: float) -> float:
    """The middle of the lowest part of the letter's body right of ``start`` (the ink's bottom edge
    within LOW of its lowest point, the leg left out): where the body curves down nearest the line."""
    from fontTools.pens.pointInsidePen import PointInsidePen
    gs, g = T.getGlyphSet(), T["glyf"][name]
    g.recalcBounds(T["glyf"])
    edge = []
    for x in range(int(start), g.xMax, 10):
        for y in range(-150, g.yMax, 5):
            pen = PointInsidePen(gs, (x, y))
            gs[name].draw(pen)
            if pen.getResult():
                edge.append((x, y))
                break
    bottom = min(y for x, y in edge)
    xs = [x for x, y in edge if y <= bottom + LOW * T["head"].unitsPerEm / 2048]
    return (min(xs) + max(xs)) / 2


def fix(path: Path) -> str:
    T = TTFont(path)
    gpos, gdef = T["GPOS"].table, T["GDEF"].table
    lookups = gpos.LookupList.Lookup
    import io
    buf = io.BytesIO()
    T.save(buf)
    font = hb.Font(hb.Face(hb.Blob(buf.getvalue())))
    gs = T.getGlyphSet()
    scale = T["head"].unitsPerEm / 2048
    rules: dict = {}           # (base glyph, vowel glyph) -> dx
    for dg in FORMS:
        for v in VOWELS:
            g = _shape(font, T, gs, "ק" + dg + v)
            if len(g) < 2:
                continue
            base = max(g, key=lambda q: q[2] - q[1])
            under = [q for q in g if q is not base]
            if len(under) != 1:
                continue
            vowel = under[0]
            legs = [r for r in _runs(T, base[0], -100 * scale)]
            if not legs:
                continue
            leg = base[3] + max(b for a, b in legs)
            low = base[3] + _lowest(T, base[0], leg - base[3] + GAP * scale)
            # (centred under the lowest part of the body, never nearer the leg than GAP)
            dx = max(round(low - (vowel[1] + vowel[2]) / 2), round(leg + GAP * scale - vowel[1]))
            if dx < 0:
                rules[(base[0], vowel[0])] = dx
    if not rules:
        return f"{path.name}: nothing to move"
    rev = T.getReverseGlyphMap()
    classes = getattr(gdef.GlyphClassDef, "classDefs", {})
    below = set()
    for n, c in classes.items():
        if c == 3 and n in gs:
            b = BoundsPen(gs)
            gs[n].draw(b)
            if b.bounds and b.bounds[3] <= 0:
                below.add(n)
    sets = gdef.MarkGlyphSetsDef
    if sets is None:
        sets = gdef.MarkGlyphSetsDef = ot.MarkGlyphSetsDef()
        sets.MarkSetTableFormat, sets.Coverage, sets.MarkSetCount = 1, [], 0
        gdef.Version = 0x00010002
    sets.Coverage.append(otl.buildCoverage(sorted(below | {v for _, v in rules}), rev))
    sets.MarkSetCount = len(sets.Coverage)
    bases = sorted({b for b, _ in rules})
    vowels = sorted({v for _, v in rules})
    singles: dict = {}

    def single(vg, dx):
        if (vg, dx) not in singles:
            lookups.append(otl.buildLookup([otl.buildSinglePosSubtable(
                {vg: otl.buildValue({"XPlacement": dx})}, rev)], table="GPOS"))
            singles[(vg, dx)] = len(lookups) - 1
        return singles[(vg, dx)]

    def chain(back, inputs, record, ahead=()):
        st = ot.ChainContextPos()
        st.Format = 3
        st.BacktrackCoverage = [otl.buildCoverage(back, rev)]
        st.InputCoverage = [otl.buildCoverage(i, rev) for i in inputs]
        st.LookAheadCoverage = [otl.buildCoverage(a, rev) for a in ahead]
        st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = 1, len(inputs), len(ahead)
        st.PosLookupRecord = []
        if record is not None:
            r = ot.PosLookupRecord()
            r.SequenceIndex, r.LookupListIndex = 0, record
            st.PosLookupRecord = [r]
        st.PosCount = len(st.PosLookupRecord)
        return st
    # (a meteg or a ta'am under the letter after the vowel: nothing.  Written as a look-ahead: with the
    #  other mark in the input, Typst's shaper (rustybuzz) took the rule as matching with no mark after)
    subtables = [chain(bases, [vowels], None, [sorted(below)])]
    groups: dict = {}
    for (b, v), dx in rules.items():
        groups.setdefault((v, dx), set()).add(b)
    for (v, dx), bs in sorted(groups.items()):
        subtables.append(chain(sorted(bs), [[v]], single(v, dx)))
    lk = ot.Lookup()
    lk.LookupType, lk.LookupFlag, lk.MarkFilteringSet = 8, 0x0010, sets.MarkSetCount - 1
    lk.SubTable, lk.SubTableCount = subtables, len(subtables)
    lookups.append(lk)
    gpos.LookupList.LookupCount = len(lookups)
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "mark":
            fr.Feature.LookupListIndex.append(len(lookups) - 1)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    __import__("gpos_ext").as_extensions(T)
    T.save(path)
    moves = sorted(-d for d in rules.values())
    return f"{path.name}: a vowel alone under ק moved toward the leg ({len(rules)} pairs, {moves[0]}-{moves[-1]} units)"


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(fix(Path(p)))
