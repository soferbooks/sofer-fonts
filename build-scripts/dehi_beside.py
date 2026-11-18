"""The dehi (U+05AD) and the yetiv (U+059A) beside the vowel under its letter, as Sefaria and the printed chumashim set it
(Mordy, 2026-11-18, from Tehillim 79:12, שִׁ֭בְעָתַיִם: "this is how it should look - can we fix it
everywhere?").

Taamey D sets the dehi past the letter's right edge and the vowel in the letter's middle, so there is
a gap between them - a sixth to a third of a letter (the widest under ש, whose vowel we centre under
its foot).  Here the dehi is moved left to stand GAP units right of the vowel under the same letter,
as far as Taamey D sets any ta'am beside a vowel (טִפְחָא beside a chirik: 100 units), for every
letter, with or without a dagesh or the shin / sin dot, and every vowel; with no vowel under the
letter, in the middle under it.  Only a ta'am that is further away moves.  One contextual rule, last in the
"mark" feature (letter, vowel, dehi; other marks skipped).

    .venv/Scripts/python scripts/dehi_beside.py <font.ttf> [...]     (in place)

Run after the font's other placement steps; then the collision fixer and check_marks.
"""
from __future__ import annotations

import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.otlLib import builder as otl
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot

DEHI = "֭"
YETIV = "֚"
TAAMIM = (DEHI, YETIV)     # (the ta'amim set under the letter to the right of its vowel - Mordy, 2026-11-18:
                           #  "other taamim that are to the right of the nikkud should act the same")
GAP = 100                 # (units of 2048: as Taamey D sets a ta'am beside a vowel under one letter)
LETTERS = "אבגדהוזחטיכלמנסעפצקרשת"   # (no final letters: a dehi / yetiv is on a word's first letter)
FORMS = ("", "ּ")    # (without / with a dagesh)
DOTS = {"ש": ("ׁ", "ׂ", "")}
VOWELS = [chr(c) for c in range(0x05B0, 0x05BC) if c not in (0x05B9, 0x05BA)] + ["ׇ", "׈"]   # (and the shva na)


def _shape(font: hb.Font, T: TTFont, gs, text: str):
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
            out.append((name, x + p.x_offset + b.bounds[0], x + p.x_offset + b.bounds[2]))
        x += p.x_advance
    return out


def fix(path: Path) -> str:
    T = TTFont(path)
    data = path.read_bytes()
    font = hb.Font(hb.Face(hb.Blob(data)))
    gs = T.getGlyphSet()
    cmap = T.getBestCmap()
    scale = T["head"].unitsPerEm / 2048
    rules: dict = {}           # (ta'am glyph, base glyph, vowel glyph) -> dx
    vowel_glyphs, taam_glyphs = set(), set()
    for taam in TAAMIM:
        tg = cmap.get(ord(taam))
        if not tg:
            continue
        for c in LETTERS:
            for dot in DOTS.get(c, ("",)):
                for dg in FORMS:
                    for v in [""] + VOWELS:
                        g = _shape(font, T, gs, c + dg + dot + v + taam)
                        d = [q for q in g if q[0] == tg]
                        rest = [q for q in g if q[0] != tg]
                        if len(d) != 1 or not rest:
                            continue
                        base = max(rest, key=lambda q: q[2] - q[1])
                        under = [q for q in rest if q is not base]
                        if not v:
                            # (no vowel under the letter: the ta'am in the middle under it, as any other
                            #  ta'am alone - Mordy, 2026-11-18, of יוֹם: "why wasn't it directly under the letter")
                            if under:            # (a dagesh drawn apart: left as it is)
                                continue
                            dx = round((base[1] + base[2]) / 2 - (d[0][1] + d[0][2]) / 2)
                            if dx < 0:
                                rules[(tg, base[0], None)] = dx
                                taam_glyphs.add(tg)
                            continue
                        if len(under) != 1:      # (a dagesh drawn apart, or two marks: left as they are)
                            continue
                        vowel = under[0]
                        dx = round(vowel[2] + GAP * scale - d[0][1])
                        # (further away: moved in; over the vowel - Drugulin's ע set its dehi where its
                        #  vowel goes, the two in one blot, Mordy 2026-11-18 - moved out to stand beside it)
                        if dx < 0 or d[0][1] < vowel[2]:
                            rules[(tg, base[0], vowel[0])] = dx
                            vowel_glyphs.add(vowel[0])
                            taam_glyphs.add(tg)
    if not rules:
        return f"{path.name}: nothing to move"
    rev = T.getReverseGlyphMap()
    gpos, gdef = T["GPOS"].table, T["GDEF"].table
    sets = gdef.MarkGlyphSetsDef
    if sets is None:
        sets = gdef.MarkGlyphSetsDef = ot.MarkGlyphSetsDef()
        sets.MarkSetTableFormat, sets.Coverage, sets.MarkSetCount = 1, [], 0
        gdef.Version = 0x00010002
    # (every mark drawn under the line is in the set: a mark under the letter that is not a vowel known
    #  here - a meteg, the shva na - stops the "no vowel" rule, and the rule beside it does not match)
    gs_all = T.getGlyphSet()
    classes = getattr(gdef.GlyphClassDef, "classDefs", {})
    below = set()
    for n, c in classes.items():
        if c == 3 and n in gs_all:
            b = BoundsPen(gs_all)
            gs_all[n].draw(b)
            if b.bounds and b.bounds[3] <= 0:
                below.add(n)
    sets.Coverage.append(otl.buildCoverage(sorted(vowel_glyphs | taam_glyphs | below), rev))
    sets.MarkSetCount = len(sets.Coverage)
    lookups = gpos.LookupList.Lookup
    singles: dict = {}

    def single(tg, dx):
        if (tg, dx) not in singles:
            lookups.append(otl.buildLookup([otl.buildSinglePosSubtable(
                {tg: otl.buildValue({"XPlacement": dx})}, rev)], table="GPOS"))
            singles[(tg, dx)] = len(lookups) - 1
        return singles[(tg, dx)]
    groups: dict = {}
    for (tg, b, v), dx in rules.items():
        groups.setdefault((tg, v, dx), set()).add(b)
    subtables = []
    for (tg, v, dx), bs in sorted(groups.items(), key=lambda kv: (kv[0][2], kv[0][0], kv[0][1] or "")):
        st = ot.ChainContextPos()
        st.Format = 3
        # (with no vowel the letter itself is right before the ta'am: a vowel there - a mark of the
        #  set - does not match)
        st.BacktrackCoverage = ([otl.buildCoverage([v], rev)] if v else []) + [otl.buildCoverage(sorted(bs), rev)]
        st.InputCoverage = [otl.buildCoverage([tg], rev)]
        st.LookAheadCoverage = []
        st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = len(st.BacktrackCoverage), 1, 0
        r = ot.PosLookupRecord()
        r.SequenceIndex, r.LookupListIndex = 0, single(tg, dx)
        st.PosLookupRecord, st.PosCount = [r], 1
        subtables.append(st)
    chain = ot.Lookup()
    chain.LookupType, chain.LookupFlag, chain.MarkFilteringSet = 8, 0x0010, sets.MarkSetCount - 1
    chain.SubTable, chain.SubTableCount = subtables, len(subtables)
    lookups.append(chain)
    gpos.LookupList.LookupCount = len(lookups)
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "mark":
            fr.Feature.LookupListIndex.append(len(lookups) - 1)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    __import__("gpos_ext").as_extensions(T)
    T.save(path)
    moves = sorted(-d for d in rules.values())
    return (f"{path.name}: the dehi / yetiv set beside the vowel for {len(rules)} letter-and-vowel pairs "
            f"(moved {moves[0]}-{moves[-1]} units)")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(fix(Path(p)))
