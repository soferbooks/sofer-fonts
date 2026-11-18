"""Vilna Sofer's ע as Culmus drew it (Drugulin CLM, its long diagonal tail) wherever nothing is under it
(Mordy, 2026-11-18: "can Vilna Sofer revert to the old ע when there is no nikkud underneath it?").

The ע with Frank Sofer's base (scripts/drugulin_ayin.py) stays for an ע with a vowel, meteg or ta'am under
it - the tail had pushed those under the letter before.  Here the original is added as "ayin.drugulin"
(scaled to the font's 2,048 units and moved right by the font's padding, as make_stam_sefarad set every
letter; in the bold thickened as make_bold does), given the ע's anchors for the marks above it, and swapped
in by "ccmp": an ע followed by a mark under the line (the marks above skipped) stays, any other becomes the
original.  Written as a look-ahead (a rule with the next mark in its input is taken as matching by Typst's
shaper).

    .venv/Scripts/python scripts/vilna_old_ayin.py <Culmus DrugulinCLM.ttf> fonts/VilnaSofer.ttf
    .venv/Scripts/python scripts/vilna_old_ayin.py <Culmus DrugulinCLM.ttf> fonts/VilnaSofer-Bold.ttf --bold

(The Culmus file, GPL-2 with the font exception, is kept in SoferShared/archive/font-sources/.)  Run once
on a freshly built font; then the collision fixer.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fontTools.otlLib import builder as otl
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot

sys.path.insert(0, str(Path(__file__).resolve().parent))
NAME = "ayin.drugulin"
PAD = 25                   # (make_stam_sefarad --pad 25: each letter moved right this much, its advance 2x more)
BOLD = 0.018               # (make_bold.py --strength 0.018, as the bold was made)


def add(src: Path, path: Path, bold: bool = False) -> str:
    S, T = TTFont(src), TTFont(path)
    if NAME in T.getGlyphOrder():
        return f"{path.name}: has it already"
    k = T["head"].unitsPerEm / S["head"].unitsPerEm
    sname = S.getBestCmap()[0x05E2]
    rec = DecomposingRecordingPen(S.getGlyphSet())
    S.getGlyphSet()[sname].draw(rec)
    pen = TTGlyphPen(None)
    rec.replay(TransformPen(pen, (k, 0, 0, k, PAD, 0)))
    g = pen.glyph()
    adv = round(S["hmtx"][sname][0] * k) + 2 * PAD
    if bold:
        import make_bold
        upem = T["head"].unitsPerEm
        sx, sy = BOLD * upem, round(BOLD * 0.7, 4) * upem
        new = make_bold._embolden(list(g.coordinates), list(g.endPtsOfContours), sx, sy)
        g.coordinates[:] = [(x + round(sx / 2), y) for x, y in new]
        adv += round(sx)
    glyf = T["glyf"]
    order = T.getGlyphOrder() + [NAME]
    T.setGlyphOrder(order)
    glyf.glyphOrder = order
    glyf[NAME] = g
    g.recalcBounds(glyf)
    T["hmtx"][NAME] = (adv, g.xMin)
    if "post" in T and hasattr(T["post"], "extraNames"):
        T["post"].extraNames.append(NAME)
    ayin = T.getBestCmap()[0x05E2]
    gdef = T["GDEF"].table
    gdef.GlyphClassDef.classDefs[NAME] = 1
    rev = T.getReverseGlyphMap(rebuild=True)
    # (the marks above it: the ע's own anchors - the arms are the same; nothing goes under it)
    gpos = T["GPOS"].table
    copied = 0
    for lk in gpos.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ == "MarkBasePos" and ayin in st.BaseCoverage.glyphs:
                i = st.BaseCoverage.glyphs.index(ayin)
                st.BaseCoverage.glyphs.append(NAME)
                r = ot.BaseRecord()
                r.BaseAnchor = list(st.BaseArray.BaseRecord[i].BaseAnchor)
                st.BaseArray.BaseRecord.append(r)
                st.BaseArray.BaseCount = len(st.BaseArray.BaseRecord)
                copied += 1
    # (the swap: in "ccmp", last)
    gs = T.getGlyphSet()
    below = []
    for n, c in gdef.GlyphClassDef.classDefs.items():
        if c == 3 and n in gs:
            b = BoundsPen(gs)
            gs[n].draw(b)
            if b.bounds and b.bounds[3] <= 0:
                below.append(n)
    sets = gdef.MarkGlyphSetsDef
    if sets is None:
        sets = gdef.MarkGlyphSetsDef = ot.MarkGlyphSetsDef()
        sets.MarkSetTableFormat, sets.Coverage, sets.MarkSetCount = 1, [], 0
        gdef.Version = 0x00010002
    sets.Coverage.append(otl.buildCoverage(sorted(below), rev))
    sets.MarkSetCount = len(sets.Coverage)
    gsub = T["GSUB"].table
    lookups = gsub.LookupList.Lookup
    lookups.append(otl.buildLookup([otl.buildSingleSubstSubtable({ayin: NAME})], table="GSUB"))
    swap = len(lookups) - 1

    def chain(ahead, record):
        st = ot.ChainContextSubst()
        st.Format = 3
        st.BacktrackCoverage, st.InputCoverage = [], [otl.buildCoverage([ayin], rev)]
        st.LookAheadCoverage = [otl.buildCoverage(a, rev) for a in ahead]
        st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = 0, 1, len(ahead)
        st.SubstLookupRecord = []
        if record is not None:
            r = ot.SubstLookupRecord()
            r.SequenceIndex, r.LookupListIndex = 0, record
            st.SubstLookupRecord = [r]
        st.SubstCount = len(st.SubstLookupRecord)
        return st
    lk = ot.Lookup()
    lk.LookupType, lk.LookupFlag, lk.MarkFilteringSet = 6, 0x0010, sets.MarkSetCount - 1
    lk.SubTable = [chain([sorted(below)], None), chain([], swap)]
    lk.SubTableCount = 2
    lookups.append(lk)
    gsub.LookupList.LookupCount = len(lookups)
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "ccmp":
            fr.Feature.LookupListIndex.append(len(lookups) - 1)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    T["maxp"].numGlyphs = len(order)
    T.save(path)
    import fix_lsb
    fix_lsb.fix(path)
    return f"{path.name}: the original ע added ({copied} anchor tables), used with nothing under it"


if __name__ == "__main__":
    src, *rest = sys.argv[1:]
    bold = "--bold" in rest
    for p in [r for r in rest if r != "--bold"]:
        print(add(Path(src), Path(p), bold))
