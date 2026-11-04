"""Make "Frank Sofer": Ben Denckla's Taamey D - the maintained successor of Taamey Frank CLM,
with better placement of the ta'amim (Mordy, 2026-10-21: use Taamey D wherever Taamey Frank was
used).  Taamey D reserves its name, so the changed font has its own.

Mordy's changes (2026-10-21): the marks below closer to the letters (as Frank Ruehl's); placed
by each letter's shape under ר, ד (the leg), ו (the stroke) and ת (the open space), the cholam
centred over a vav; the kamatz katan Sofer's bold drop, hanging a little lower ("the 3/5 mix",
chosen from five); the shva na.

Taamey D is GPL-2 with the font exception (its license.txt, kept as
fonts/licenses/TAAMEY-D-LICENSE.txt); downloaded 2026-10-21 from
https://bdenckla.github.io/hbofonts/downloads/ (snapshot 0.931-hbofonts-42ca46e82f78).

    python scripts/make_frank_sofer.py <Taamey_D.ttf>     ->  fonts/FrankSofer.ttf
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fonts" / "FrankSofer.ttf"
FAMILY = "Frank Sofer"


def main(src: str) -> None:
    shutil.copyfile(src, OUT)
    OUT.chmod(0o644)
    # its kamatz katan (Mordy, 2026-10-21, from five shown: "the 3/5 mix"): Sofer's - the drop
    # drawn fuller and bolder - hanging a little lower on a longer stem
    import importlib.util
    spec = importlib.util.spec_from_file_location("aq", ROOT / "scripts" / "add_qamats_qatan.py")
    aq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(aq)
    print("  " + aq.make(OUT, lower=KATAN_LOWER))
    t = TTFont(OUT)
    print(f"  marks below raised on {raise_below(t)} letters")
    for rec in t["name"].names:
        if rec.nameID in (1, 16):
            rec.string = FAMILY
        elif rec.nameID in (3, 4, 6):
            text = rec.toUnicode()
            rec.string = text.replace("Taamey D", FAMILY).replace("Taamey_D", FAMILY.replace(" ", "")) \
                .replace("TaameyD", FAMILY.replace(" ", ""))
        elif rec.nameID == 0:
            rec.string = rec.toUnicode() + ("\n\nFrank Sofer: Taamey D (Ben Denckla, GPL-2 with the font exception) "
                                            "with the marks below raised closer to the letters and placed by each letter's shape (resh, dalet, vav, tav, the vav's cholam) by Sofer, 2026; renamed, as Taamey D's "
                                            "licence reserves its name.")
    t.save(OUT)
    print(f"{OUT.name}: {FAMILY}")
    _shva_na(OUT)
    t = TTFont(OUT)
    print(f"  under the open space: {', '.join(under_open_space(t))}; cholam over the vav: {holam_male(t)}")
    print(f"  under the foot: {', '.join(under_the_foot(t))}; kamatz katan as the kamatz: {qatan_as_qamats(t)}")
    print(f"  under the leg: {', '.join(under_the_leg(t))}")
    print(f"  clear of the cholam of וֹ: {clear_of_holam(t)}")
    print(f"  nothing touching: {', '.join(nothing_touching(t))}")
    print(f"  a vowel and a meteg under ק moved under it: {', '.join(qof_with_meteg(t))}")
    print(f"  the chataf kamatz with the kamatz katan's drop: {hataf_as_qatan(t)}")
    print(f"  a vowel kept in the middle beside a ta'am or meteg: {centred_with_another(t)}")
    t.save(OUT)
    # (no mark touching anything in the siddurim either, found by shaping every word - Mordy,
    #  2026-11-04: "fix the fonts for the siddur"; a revia mugrash on one letter touched)
    import make_stam_sefarad
    print("  siddur: " + make_stam_sefarad.fix_by_shaping(OUT, make_stam_sefarad.siddur_words()))
    _check_marks(OUT)



KATAN_LOWER = 0.18


# How much closer the marks below come to their letter (Mordy, 2026-10-21: "rather it closer"):
# Taamey D hangs them 0.095 em under the line, Frank Ruehl 0.058 - raised by the difference
RAISE = 0.035


def raise_below(t: TTFont) -> int:
    """Bring the marks below (nikud and ta'amim) up toward the letter, as close as Frank
    Ruehl's: each letter's anchor for them on the line (not the letters with a tail, whose
    anchors are elsewhere) goes up by RAISE."""
    dy = round(RAISE * t["head"].unitsPerEm)
    done = set()
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            cls = {r.Class for g, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if g in ("qamats", "tipxa")}
            if len(cls) != 1:
                continue
            c = cls.pop()
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                a = rec.BaseAnchor[c]
                if a is not None and a.YCoordinate == 0:
                    a.YCoordinate = dy
                    done.add(name)
    return len(done)


# Where Frank Ruehl centres a mark under these letters: its share of the letter's ink width,
# from the right (measured with HarfBuzz, 2026-10-21; Taamey D: 0.5, the middle)
UNDER_LEG = {"resh": 0.20, "dalet": 0.30, "vav": None}     # (ו: under its stroke, measured - Mordy, 2026-10-21)


def _runs(t: TTFont, name: str, y: float, step: int = 4) -> list[tuple[int, int]]:
    """The stretches of ink across the glyph at height ``y``, right to left in x order."""
    from fontTools.pens.pointInsidePen import PointInsidePen
    gs, g = t.getGlyphSet(), t["glyf"][name]
    g.recalcBounds(t["glyf"])
    runs, start, last = [], None, None
    for x in range(g.xMin - step, g.xMax + 2 * step, step):
        pen = PointInsidePen(gs, (x, y))
        gs[name].draw(pen)
        if pen.getResult():
            start = x if start is None else start
            last = x
        elif start is not None:
            runs.append((start, last))
            start = None
    return runs


def _foot(t: TTFont, name: str) -> list[tuple[int, int]]:
    """The letter's ink just above the line it stands on."""
    g = t["glyf"][name]
    g.recalcBounds(t["glyf"])
    return _runs(t, name, max(g.yMin, 0) + 0.08 * (g.yMax - max(g.yMin, 0)))


OPEN_SPACE = ("he", "xet", "tav")     # (the letters standing on two legs)
ON_A_FLOOR = {"shin": ("shin", "trueshin", "sin"), "tet": ("tet",)}   # (and those on a floor)


def _family(name: str, roots) -> bool:
    """``name`` is one of ``roots`` or a form of it (with a dagesh, a dot, wide ...)."""
    if "shin" in roots:              # (every form of ש: with its dots, a dagesh, a geresh ...)
        return name.startswith(roots) and not name.endswith("dot")
    return any(name == r or name.startswith((r + ".", r + "dagesh", r + "mapiq", r + "rafe")) for r in roots)


def under_open_space(t: TTFont) -> list[str]:
    """The marks below ה ח ת (a vowel alone, or with its ta'am - they move together) centred
    under the open space between the legs, not under the whole letter (Mordy, 2026-10-21: ת;
    2026-10-29: every letter with two legs)."""
    done = []
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            cls = {r.Class for g, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if g in ("qamats", "tipxa")}
            if len(cls) != 1:
                continue
            c = cls.pop()
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                if not _family(name, OPEN_SPACE) or rec.BaseAnchor[c] is None:
                    continue
                runs = _foot(t, name)
                if len(runs) >= 2:
                    rec.BaseAnchor[c].XCoordinate = round((runs[0][1] + runs[-1][0]) / 2)
                    done.append(name)
    return done


def under_the_foot(t: TTFont) -> list[str]:
    """The marks below ש and ט centred under the floor they stand on, not under the whole letter,
    whose arms reach further out (Mordy, 2026-10-28: ש; 2026-10-29: ט)."""
    done = []
    feet = {}
    for plain in ON_A_FLOOR:
        g = t["glyf"][plain]
        g.recalcBounds(t["glyf"])
        feet[plain] = max(g.yMin, 0) + 0.08 * (g.yMax - max(g.yMin, 0))   # (the plain letter's: its other forms too)
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            cls = {r.Class for g, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if g in ("qamats", "tipxa")}
            if len(cls) != 1:
                continue
            c = cls.pop()
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                plain = next((k for k, roots in ON_A_FLOOR.items() if _family(name, roots)), None)
                if plain is None or rec.BaseAnchor[c] is None:
                    continue
                runs = _runs(t, name, feet[plain])
                if runs:
                    rec.BaseAnchor[c].XCoordinate = round((runs[0][0] + runs[-1][1]) / 2)
                    done.append(name)
    return done


def qatan_as_qamats(t: TTFont) -> int:
    """The kamatz katan placed as the kamatz wherever Taamey D places the kamatz by a rule of its
    own (Mordy, 2026-10-28: קׇֽדָשִׁים - with a meteg under ק its rule for the kamatz did not
    take the kamatz katan, which went past the letter's edge, away from its leg).  Returns the
    places added."""
    import copy
    order = {g: i for i, g in enumerate(t.getGlyphOrder())}

    def add(cov, *arrays):
        if cov is None or "qamats" not in cov.glyphs or "qamatsqatan" in cov.glyphs:
            return 0
        src = cov.glyphs.index("qamats")
        at = next((i for i, g in enumerate(cov.glyphs) if order[g] > order["qamatsqatan"]), len(cov.glyphs))
        for arr in arrays:
            arr.insert(at, copy.deepcopy(arr[src]))
        cov.glyphs.insert(at, "qamatsqatan")
        return 1
    n = 0
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            kind = type(st).__name__
            if kind == "SinglePos":
                if st.Format == 2:
                    n += add(st.Coverage, st.Value)
                    st.ValueCount = len(st.Value)
                else:
                    n += add(st.Coverage)
            elif kind == "MarkMarkPos":
                n += add(st.Mark1Coverage, st.Mark1Array.MarkRecord)
                st.Mark1Array.MarkCount = len(st.Mark1Array.MarkRecord)
                n += add(st.Mark2Coverage, st.Mark2Array.Mark2Record)
                st.Mark2Array.Mark2Count = len(st.Mark2Array.Mark2Record)
            elif kind == "MarkBasePos":
                n += add(st.MarkCoverage, st.MarkArray.MarkRecord)
                st.MarkArray.MarkCount = len(st.MarkArray.MarkRecord)
            elif kind == "ChainContextPos" and st.Format == 3:
                for cov in (*st.BacktrackCoverage, *st.InputCoverage, *st.LookAheadCoverage):
                    n += add(cov)
            elif kind == "ContextPos" and st.Format == 3:
                for cov in st.Coverage:
                    n += add(cov)
    return n


def hataf_as_qatan(t: TTFont) -> bool:
    """The chataf kamatz drawn with the kamatz katan's drop, as it is read (Mordy, 2026-10-28):
    its composite's kamatz becomes the kamatz katan."""
    glyf = t["glyf"]
    name = t.getBestCmap().get(0x05B3)
    if not name or not glyf[name].isComposite() or "qamatsqatan" not in glyf.glyphs:
        return False
    for c in glyf[name].components:
        if c.glyphName == "qamats":
            c.glyphName = "qamatsqatan"
    glyf[name].recalcBounds(glyf)
    return True


QOF_GAP = 60     # (between the ק's leg and a meteg beside a vowel under it, font units)


def qof_with_meteg(t: TTFont) -> list[str]:
    """A vowel and a meteg under ק: Taamey D sets the vowel well to the right, so the meteg is
    clear of the leg, and the pair stood out past the letter (the shva na, the kamatz katan).
    Both moved left together to the middle of the room between the leg and the letter's right
    edge, the meteg at least QOF_GAP from the leg (Mordy, 2026-10-28).  A lookup run last: for
    "ק, a vowel, the meteg" (a third mark under the letter - a ta'am - leaves them).  Returns the
    vowels moved."""
    import io
    import uharfbuzz as hb
    from fontTools.otlLib import builder as otl
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib.tables import otTables as ot

    gpos, gdef, glyf = t["GPOS"].table, t["GDEF"].table, t["glyf"]
    lookups = gpos.LookupList.Lookup
    rev, order, gs = t.getReverseGlyphMap(), t.getGlyphOrder(), t.getGlyphSet()
    mark = [fr for fr in gpos.FeatureList.FeatureRecord if fr.FeatureTag == "mark"]
    # (done before: its lookups - the last ones - taken out first)
    def ours(lk):
        return lk.LookupType == 8 and all(
            getattr(st, "Format", 0) == 3 and st.BacktrackCoverage and st.InputGlyphCount in (2, 3)
            and "qof" in st.BacktrackCoverage[0].glyphs and "meteg" in st.InputCoverage[1].glyphs
            for st in lk.SubTable)
    old = sorted({i for fr in mark for i in fr.Feature.LookupListIndex if ours(lookups[i])})
    if old:
        nested = [r.LookupListIndex for i in old for st in lookups[i].SubTable for r in st.PosLookupRecord]
        first = min(old + nested)
        drop = set(range(first, len(lookups)))
        for fr in gpos.FeatureList.FeatureRecord:
            fr.Feature.LookupListIndex = [i for i in fr.Feature.LookupListIndex if i not in drop]
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
        del lookups[first:]
        gpos.LookupList.LookupCount = len(lookups)
    buf_font = io.BytesIO()
    t.save(buf_font)
    font = hb.Font(hb.Face(hb.Blob(buf_font.getvalue())))

    def shaped(text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf)
        out, x = [], 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            name = order[info.codepoint]
            bp = BoundsPen(gs)
            gs[name].draw(bp)
            if bp.bounds:
                out.append((name, x + pos.x_offset + bp.bounds[0], x + pos.x_offset + bp.bounds[2]))
            x += pos.x_advance
        return out
    qof = glyf["qof"]
    qof.recalcBounds(glyf)
    leg = max(b for a, b in _runs(t, "qof", -100))         # (the leg's right side, under the line)
    right = qof.xMax
    glyph_class = getattr(gdef.GlyphClassDef, "classDefs", {}) if gdef.GlyphClassDef else {}
    under = sorted(g for g, c in glyph_class.items() if c == 3 and g in glyf.glyphs
                   and _bottom(glyf, g) < 0 and _top(glyf, g) <= 0)
    shifts = {}
    for cp in [*range(0x05B0, 0x05BC), 0x05C7, 0x05C8]:
        if cp == 0x05BD:
            continue
        g = shaped("ק" + chr(cp) + "ֽ")
        marks = [x for x in g if x[0] != "qof"]
        if len(marks) != 2 or not any(x[0] == "meteg" for x in marks):
            continue
        vowel = next(x[0] for x in marks if x[0] != "meteg")
        if vowel not in under:
            continue
        lo, hi = min(x[1] for x in marks), max(x[2] for x in marks)
        meteg_lo = next(x[1] for x in marks if x[0] == "meteg")
        dx = round((leg + right) / 2 - (lo + hi) / 2)
        dx = max(dx, leg + QOF_GAP - meteg_lo)             # (never nearer the leg than that)
        if dx:
            shifts.setdefault(dx, []).append(vowel)
    if not shifts:
        return []
    bases = sorted(g for g in glyf.glyphs if g == "qof" or g.startswith("qofdagesh"))
    sets = gdef.MarkGlyphSetsDef
    if gdef.Version < 0x00010002 or sets is None:
        gdef.Version = 0x00010002
        gdef.MarkGlyphSetsDef = sets = ot.MarkGlyphSetsDef()
        sets.MarkSetTableFormat, sets.Coverage = 1, []
    sets.Coverage.append(otl.buildCoverage(under, rev))
    sets.MarkSetCount = len(sets.Coverage)
    fset = sets.MarkSetCount - 1

    def rule(vowels, count, index):
        st = ot.ChainContextPos()
        st.Format = 3
        st.BacktrackCoverage = [otl.buildCoverage(bases, rev)]
        st.InputCoverage = ([otl.buildCoverage(vowels, rev), otl.buildCoverage(["meteg"], rev)]
                            + [otl.buildCoverage(under, rev)] * (count - 2))
        st.LookAheadCoverage = []
        st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = 1, count, 0
        recs = []
        if index is not None:
            for seq in (0,):               # (the meteg hangs on the vowel: it moves with it)
                r = ot.PosLookupRecord()
                r.SequenceIndex, r.LookupListIndex = seq, index
                recs.append(r)
        st.PosLookupRecord, st.PosCount = recs, len(recs)
        return st
    subtables = []
    allv = sorted({v for vs in shifts.values() for v in vs})
    subtables.append(rule(allv, 3, None))                  # (with a ta'am too: left)
    for dx, vowels in sorted(shifts.items()):
        lookups.append(otl.buildLookup([otl.buildSinglePosSubtable(
            {g: otl.buildValue({"XPlacement": dx}) for g in [*vowels, "meteg"]}, rev)], table="GPOS"))
        subtables.append(rule(vowels, 2, len(lookups) - 1))
    chain = ot.Lookup()
    chain.LookupType, chain.LookupFlag, chain.MarkFilteringSet = 8, 0x0010, fset
    chain.SubTable, chain.SubTableCount = subtables, len(subtables)
    lookups.append(chain)
    gpos.LookupList.LookupCount = len(lookups)
    for fr in mark:
        fr.Feature.LookupListIndex.append(len(lookups) - 1)
        fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    return allv


def holam_male(t: TTFont) -> bool:
    """וֹ: the cholam centred over the vav, not over its stroke (Mordy, 2026-10-21)."""
    glyf = t["glyf"]
    if "vavxolam" not in glyf.glyphs or not glyf["vavxolam"].isComposite():
        return False
    comps = glyf["vavxolam"].components
    vav = next(c for c in comps if c.glyphName == "vav")
    dot = next(c for c in comps if c.glyphName == "xolam")
    glyf["vav"].recalcBounds(glyf)
    glyf["xolam"].recalcBounds(glyf)
    centre = vav.x + (glyf["vav"].xMin + glyf["vav"].xMax) / 2
    dot.x = round(centre - (glyf["xolam"].xMin + glyf["xolam"].xMax) / 2)
    glyf["vavxolam"].recalcBounds(glyf)
    return True


def under_the_leg(t: TTFont) -> list[str]:
    """A lone mark under ר or ד (and their forms with dagesh) moves from the middle to under
    the leg; a vowel and a ta'am under the same letter stay where Taamey D sets them, side by
    side (Mordy, 2026-10-21: moving them both made them touch).  A GPOS lookup run after the
    marks are attached: for each letter, "the letter, one mark below" moves the mark, and
    "the letter, two marks below" (tried first) leaves them.  Done again on a font that has it
    already (the Sefer Torah fonts get Frank Sofer's, measured on Frank's letters), it is
    replaced.  Returns the letters done."""
    from fontTools.otlLib import builder as otl
    from fontTools.ttLib.tables import otTables as ot

    gpos, gdef, glyf = t["GPOS"].table, t["GDEF"].table, t["glyf"]
    lookups = gpos.LookupList.Lookup
    # (the marks below, and each letter's anchor for them: Taamey D's mark-to-base lookup)
    below, anchors = None, {}
    for lk in lookups:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if not hasattr(st, "BaseCoverage") or below is not None and anchors:
                continue
            cls = {r.Class for g, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if g in ("qamats", "tipxa")}
            if len(cls) != 1:
                continue
            c = cls.pop()
            below = [g for g, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if r.Class == c]
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                if rec.BaseAnchor[c] is not None:
                    anchors[name] = rec.BaseAnchor[c].XCoordinate
    # (a font that has it already: its lookups are the last ones, taken out first)
    mark = [fr for fr in gpos.FeatureList.FeatureRecord if fr.FeatureTag == "mark"]
    def ours(lk):
        return lk.LookupType == 8 and all(
            getattr(st, "Format", 0) == 3 and st.BacktrackCoverage
            and all(g.startswith(tuple(UNDER_LEG)) for g in st.BacktrackCoverage[0].glyphs)
            for st in lk.SubTable)
    old = sorted({i for fr in mark for i in fr.Feature.LookupListIndex if ours(lookups[i])})
    if old:
        nested = [r.LookupListIndex for i in old for st in lookups[i].SubTable for r in st.PosLookupRecord]
        first = min(old + nested)
        drop = set(range(first, len(lookups)))
        for fr in gpos.FeatureList.FeatureRecord:
            fr.Feature.LookupListIndex = [i for i in fr.Feature.LookupListIndex if i not in drop]
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
        del lookups[first:]
    # the filtering set: the marks below only (the dagesh and the marks above are looked past)
    if gdef.Version < 0x00010002:
        gdef.Version = 0x00010002
    if getattr(gdef, "MarkGlyphSetsDef", None) is None:
        gdef.MarkGlyphSetsDef = ot.MarkGlyphSetsDef()
        gdef.MarkGlyphSetsDef.MarkSetTableFormat = 1
        gdef.MarkGlyphSetsDef.Coverage = []
    rev = t.getReverseGlyphMap()
    # (every mark under the line, Taamey D's other ones too - the dehi, set apart at the
    #  letter's right: it is a second mark under the letter as much as a vowel's ta'am is;
    #  the hbofonts collision check found the vowel moved into it, Mordy 2026-10-22)
    glyph_class = getattr(gdef.GlyphClassDef, "classDefs", {}) if gdef.GlyphClassDef else {}
    under = sorted(set(below) | {g for g, c in glyph_class.items() if c == 3 and g in glyf.glyphs
                                 and _bottom(glyf, g) < 0 and _top(glyf, g) <= 0})
    taam_under = sorted({g for cp, g in t.getBestCmap().items() if 0x0591 <= cp <= 0x05AF and g in under})
    sets = gdef.MarkGlyphSetsDef
    sets.Coverage.append(otl.buildCoverage(under, rev))
    sets.MarkSetCount = len(sets.Coverage)
    fset = sets.MarkSetCount - 1
    shifts = {}
    for name, x in anchors.items():
        key = next((k for k in UNDER_LEG if name == k or name.startswith(k + "dagesh")), None)
        if key is None:
            continue
        g = glyf[name]
        g.recalcBounds(glyf)
        if UNDER_LEG[key] is None:          # (under the stroke: the middle of the ink at the foot)
            runs = _foot(t, name)
            if not runs:
                continue
            dx = round((runs[-1][0] + runs[-1][1]) / 2 - x)
        else:
            dx = round(g.xMax - UNDER_LEG[key] * (g.xMax - g.xMin) - x)
        if dx:
            shifts.setdefault(dx, []).append(name)
    if not shifts:
        return []
    subtables, moves = [], []
    for dx, bases in sorted(shifts.items()):
        single = otl.buildLookup([otl.buildSinglePosSubtable({g: otl.buildValue({"XPlacement": dx}) for g in below}, rev)],
                                 table="GPOS")
        lookups.append(single)
        moves.append((bases, len(lookups) - 1))
    for bases, _ in moves:              # (a vowel and a ta'am: left as they are)
        subtables.append(_chain(otl, ot, rev, bases, under, 2, None))
    for bases, _ in moves:              # (a ta'am under the letter before - the יּ's tevir in
        for back in (1, 2):             #  וַיֵּ֛רֶד: moved under the leg the vowel touched it; left)
            subtables.append(_chain(otl, ot, rev, bases, below, 1, None, [taam_under] + [under] * (back - 1)))
    for bases, index in moves:          # (one mark: under the leg)
        subtables.append(_chain(otl, ot, rev, bases, below, 1, index))
    chain = ot.Lookup()
    chain.LookupType, chain.LookupFlag, chain.MarkFilteringSet = 8, 0x0010, fset
    chain.SubTable, chain.SubTableCount = subtables, len(subtables)
    lookups.append(chain)
    gpos.LookupList.LookupCount = len(lookups)
    for fr in mark:
        fr.Feature.LookupListIndex.append(len(lookups) - 1)
        fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    return sorted(g for bases, _ in moves for g in bases)


CLEAR_OF_HOLAM = ("pashta", "tsinor")    # (the marks set at the top of a final וֹ)
HOLAM_GAP = 50                           # their least room from the centred cholam, font units


def clear_of_holam(t: TTFont) -> dict[str, int]:
    """A pashta or a zarka on וֹ moved left, just clear of the cholam - which is centred over the
    vav now (holam_male), right under where Taamey D puts them (the hbofonts collision check:
    אֹתוֹ֙, 300 words; Mordy, 2026-10-22).  A GPOS lookup after under_the_leg's (a rebuild drops
    both).  Returns each mark's move."""
    import math
    from fontTools.otlLib import builder as otl
    from fontTools.ttLib.tables import otTables as ot
    gpos, gdef, glyf = t["GPOS"].table, t["GDEF"].table, t["glyf"]
    if "vavxolam" not in glyf.glyphs or not glyf["vavxolam"].isComposite():
        return {}
    dot = next(c for c in glyf["vavxolam"].components if c.glyphName == "xolam")
    holam = [(x + dot.x, y + dot.y) for x, y in _points(t, "xolam")]
    moves = {}
    for lk in gpos.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos" or "vavxolam" not in st.BaseCoverage.glyphs:
                continue
            base = st.BaseArray.BaseRecord[st.BaseCoverage.glyphs.index("vavxolam")]
            for m in CLEAR_OF_HOLAM:
                if m in moves or m not in st.MarkCoverage.glyphs:
                    continue
                rec = st.MarkArray.MarkRecord[st.MarkCoverage.glyphs.index(m)]
                a = base.BaseAnchor[rec.Class]
                if a is None:
                    continue
                ox, oy = a.XCoordinate - rec.MarkAnchor.XCoordinate, a.YCoordinate - rec.MarkAnchor.YCoordinate
                pts = _points(t, m)

                def room(dx):
                    return min(math.dist((x + ox + dx, y + oy), q) for x, y in pts for q in holam)
                dx = next((-d for d in range(0, 401, 8) if room(-d) >= HOLAM_GAP), 0)
                if dx:
                    moves[m] = dx
    if not moves:
        return {}
    rev = t.getReverseGlyphMap()
    sets = gdef.MarkGlyphSetsDef
    sets.Coverage.append(otl.buildCoverage(list(moves), rev))
    sets.MarkSetCount = len(sets.Coverage)
    lookups = gpos.LookupList.Lookup
    subtables = []
    for m, dx in moves.items():
        lookups.append(otl.buildLookup([otl.buildSinglePosSubtable({m: otl.buildValue({"XPlacement": dx})}, rev)],
                                       table="GPOS"))
        st = ot.ChainContextPos()
        st.Format = 3
        st.BacktrackCoverage = [otl.buildCoverage(["vavxolam"], rev)]
        st.InputCoverage = [otl.buildCoverage([m], rev)]
        st.LookAheadCoverage = []
        st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = 1, 1, 0
        r = ot.PosLookupRecord()
        r.SequenceIndex, r.LookupListIndex = 0, len(lookups) - 1
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
    return moves


RAFE_GAP = 40                       # between a rafe and a ta'am set over it


def nothing_touching(t: TTFont) -> list[str]:
    """The collisions Taamey D has itself (Mordy, 2026-10-22: "remove all collisions"), found by
    shaping every word of Tanach: a ta'am over a rafe (בָֿ֝֗ם, Tehillim 68:18) raised above it.
    (The Ten Commandments' kamatz and patach under one letter, the two readings, are kept apart
    by Taamey D itself: MAM puts a CGJ, U+034F, between them.)  GPOS lookups after the others."""
    from fontTools.otlLib import builder as otl
    from fontTools.ttLib.tables import otTables as ot
    gpos, gdef, glyf = t["GPOS"].table, t["GDEF"].table, t["glyf"]
    rev = t.getReverseGlyphMap()
    lookups = gpos.LookupList.Lookup
    sets = gdef.MarkGlyphSetsDef
    done, chains = [], []

    def single(values):
        lookups.append(otl.buildLookup([otl.buildSinglePosSubtable(
            {g: otl.buildValue(v) for g, v in values.items()}, rev)], table="GPOS"))
        return len(lookups) - 1

    def rule(alternatives, fset):
        """One chained lookup: each (inputs, moves) tried in turn, the first that matches."""
        chain = ot.Lookup()
        chain.LookupType, chain.LookupFlag, chain.MarkFilteringSet = 8, 0x0010, fset
        chain.SubTable = [subtable(i, m) for i, m in alternatives]
        chain.SubTableCount = len(chain.SubTable)
        chains.append(chain)

    def subtable(inputs, moves):
        st = ot.ChainContextPos()
        st.Format = 3
        st.BacktrackCoverage, st.LookAheadCoverage = [], []
        st.InputCoverage = [otl.buildCoverage(c, rev) for c in inputs]
        st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = 0, len(inputs), 0
        st.PosLookupRecord = []
        for i, index in moves:
            r = ot.PosLookupRecord()
            r.SequenceIndex, r.LookupListIndex = i, index
            st.PosLookupRecord.append(r)
        st.PosCount = len(st.PosLookupRecord)
        return st

    def filter_set(glyphs):
        sets.Coverage.append(otl.buildCoverage(sorted(glyphs), rev))
        sets.MarkSetCount = len(sets.Coverage)
        return sets.MarkSetCount - 1

    # a ta'am over a rafe: raised clear of it
    if "rafe" in glyf.glyphs:
        glyf["rafe"].recalcBounds(glyf)
        top = glyf["rafe"].yMax
        above = {}
        for cp, g in t.getBestCmap().items():
            if 0x0591 <= cp <= 0x05AF and g in glyf.glyphs and _bottom(glyf, g) > 900:
                dy = top + RAFE_GAP - _bottom(glyf, g)
                if dy > 0:
                    above.setdefault(dy, []).append(g)
        if above:
            marks = sorted(g for gs in above.values() for g in gs)
            fset = filter_set(["rafe"] + marks)
            up = single({g: {"YPlacement": dy} for dy, gs in above.items() for g in gs})
            # (a rafe and up to three ta'amim over one letter - בָֿ֝֗ם has a geresh muqdam too)
            rule([([["rafe"]] + [marks] * k, [(i, up) for i in range(1, k + 1)]) for k in (3, 2, 1)], fset)
            done.append(f"{sum(len(g) for g in above.values())} ta'amim raised over a rafe")
    for chain in chains:
        lookups.append(chain)
        for fr in gpos.FeatureList.FeatureRecord:
            if fr.FeatureTag == "mark":
                fr.Feature.LookupListIndex.append(len(lookups) - 1)
                fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    gpos.LookupList.LookupCount = len(lookups)
    return done


def _points(t: TTFont, name: str, step: int = 6) -> list[tuple[float, float]]:
    """Points along a glyph's outline (its curves sampled)."""
    from fontTools.pens.basePen import BasePen

    class Pts(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.p, self.cur = [], (0, 0)

        def _moveTo(self, a):
            self.p.append(a)
            self.cur = a

        def _lineTo(self, a):
            x0, y0 = self.cur
            self.p += [(x0 + (a[0] - x0) * i / step, y0 + (a[1] - y0) * i / step) for i in range(1, step + 1)]
            self.cur = a

        def _qCurveToOne(self, a, b):
            x0, y0 = self.cur
            for i in range(1, step + 1):
                s = i / step
                self.p.append(((1 - s) ** 2 * x0 + 2 * (1 - s) * s * a[0] + s * s * b[0],
                               (1 - s) ** 2 * y0 + 2 * (1 - s) * s * a[1] + s * s * b[1]))
            self.cur = b

        def _curveToOne(self, a, b, c):
            x0, y0 = self.cur
            for i in range(1, step + 1):
                s, m = i / step, 1 - i / step
                self.p.append((m ** 3 * x0 + 3 * m * m * s * a[0] + 3 * m * s * s * b[0] + s ** 3 * c[0],
                               m ** 3 * y0 + 3 * m * m * s * a[1] + 3 * m * s * s * b[1] + s ** 3 * c[1]))
            self.cur = c
    gs = t.getGlyphSet()
    pen = Pts(gs)
    gs[name].draw(pen)
    return pen.p


EDGE_TAAMIM = (0x059A, 0x05AD)      # (yetiv and dehi: set at the letter's edge - never moved)
AS_THEY_ARE = {"qof", "finalkaf", "finalnun", "finalpe", "finaltsadi"}   # (ק: qof_with_meteg; the tails)


def centred_with_another(t: TTFont) -> dict[str, int]:
    """A vowel with a ta'am or a meteg under one letter: Taamey D sets the two side by side
    around the middle, so the vowel was off its place.  The vowel now stays where it stands
    alone - under ה ח ת in the open space, under ש ט in the middle of the floor, under any other
    letter where Frank Sofer puts it (Mordy, 2026-11-03: כֶ with a ta'am, בַ with a meteg - the
    vowel moved "even though it's unnecessary") - the other mark beside it as far from it as
    before; only when the two would then stand out past the letter is the vowel moved, by as
    little as keeps them under it (Mordy, 2026-10-29: "only move the nikkud if necessary").  Not
    ק (`qof_with_meteg`), the final letters, or a letter with a tail under the line (the Sefer
    Torah fonts' ע פ א: the ta'am would meet the tail).  Beside a yetiv or a dehi
    only the vowel moves, and only away from it.  A lookup run last; a third mark under the
    letter leaves them as they were.  Returns the pairs moved, by letter."""
    import io
    import uharfbuzz as hb
    from fontTools.otlLib import builder as otl
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib.tables import otTables as ot

    gpos, gdef, glyf = t["GPOS"].table, t["GDEF"].table, t["glyf"]
    lookups = gpos.LookupList.Lookup
    rev, order, gs = t.getReverseGlyphMap(), t.getGlyphOrder(), t.getGlyphSet()
    mark = [fr for fr in gpos.FeatureList.FeatureRecord if fr.FeatureTag == "mark"]
    upem = t["head"].unitsPerEm
    plains = {name: chr(cp) for cp, name in t.getBestCmap().items()   # (not a letter with a tail under
              if 0x05D0 <= cp <= 0x05EA and name in t["glyf"].glyphs   #  the line - the Stam ע, פ, א:
              and name not in AS_THEY_ARE and _bottom(t["glyf"], name) > -0.05 * upem}   #  its marks are set by it)

    def ours(lk):          # (its chain: every rule after ה ח ט ת or ש - or, since 2026-11-03,
        if lk.LookupType != 8 or not lk.SubTable:      #  after any letter, opened by "three: as they were")
            return False
        sts = [st for st in lk.SubTable if getattr(st, "Format", 0) == 3 and st.BacktrackCoverage]
        if len(sts) != len(lk.SubTable):
            return False
        first = sts[0]
        if (first.InputGlyphCount == 3 and not first.PosLookupRecord
                and {"xet", "tet", "kaf", "bet"} <= set(first.BacktrackCoverage[0].glyphs)):
            return True
        return all({"xet", "tet"} & set(st.BacktrackCoverage[0].glyphs)
                   and not {"bet", "qof", "alef"} & set(st.BacktrackCoverage[0].glyphs) for st in sts)
    # (done before - the Sefer Torah fonts start from Frank Sofer: its lookups taken out first)
    old = sorted({i for fr in mark for i in fr.Feature.LookupListIndex if ours(lookups[i])})
    if old:
        nested = [r.LookupListIndex for i in old for st in lookups[i].SubTable for r in st.PosLookupRecord]
        first = min(old + nested)
        drop = set(range(first, len(lookups)))
        for fr in gpos.FeatureList.FeatureRecord:
            fr.Feature.LookupListIndex = [i for i in fr.Feature.LookupListIndex if i not in drop]
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
        del lookups[first:]
        gpos.LookupList.LookupCount = len(lookups)
    data = io.BytesIO()
    t.save(data)
    font = hb.Font(hb.Face(hb.Blob(data.getvalue())))

    def shaped(text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf)
        out, x = [], 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            name = order[info.codepoint]
            bp = BoundsPen(gs)
            gs[name].draw(bp)
            if bp.bounds:
                out.append((name, x + pos.x_offset + bp.bounds[0], x + pos.x_offset + bp.bounds[2]))
            x += pos.x_advance
        return out

    glyph_class = getattr(gdef.GlyphClassDef, "classDefs", {}) if gdef.GlyphClassDef else {}
    under = sorted(g for g, c in glyph_class.items() if c == 3 and g in glyf.glyphs
                   and _bottom(glyf, g) < 0 and _top(glyf, g) <= 0)
    vowels = [*range(0x05B0, 0x05BC), 0x05C7, 0x05C8]
    others = [0x05BD] + [cp for cp in range(0x0591, 0x05B0)]
    rules, moved = {}, {}            # ((letter, vowel glyph, dx, both), [other glyphs])
    for plain, ch in plains.items():
        if plain not in glyf.glyphs:
            continue
        middle = None
        if plain in ON_A_FLOOR:
            g = glyf[plain]
            g.recalcBounds(glyf)
            runs = _runs(t, plain, max(g.yMin, 0) + 0.08 * (g.yMax - max(g.yMin, 0)))
            middle = (runs[0][0] + runs[-1][1]) / 2
        elif plain in OPEN_SPACE:
            runs = _foot(t, plain)
            middle = (runs[0][1] + runs[-1][0]) / 2
        for v in vowels:
            alone = [x for x in shaped(ch + chr(v)) if x[0] != plain]
            if len(alone) != 1 or alone[0][0] not in under:
                continue
            vowel, home = alone[0][0], (alone[0][1] + alone[0][2]) / 2   # (where it stands alone)
            for o in others:
                g = shaped(ch + chr(v) + chr(o))
                base = next((x for x in g if x[0] == plain), None)
                marks = [x for x in g if x[0] != plain]
                if base is None or len(marks) != 2 or not all(x[0] in under for x in marks):
                    continue
                own = [x for x in marks if x[0] == vowel]
                if len(own) != 1:
                    continue
                vx, ox = own[0], next(x for x in marks if x is not own[0])
                letter = glyf[plain]
                lo, hi = base[1], base[2]                              # (the letter's ink)
                want = round((base[1] - letter.xMin + middle if middle is not None else home) - (vx[1] + vx[2]) / 2)
                if abs(want) < 4:
                    continue
                if o in EDGE_TAAMIM:                                   # (the vowel alone, away from it)
                    away = 1 if (vx[1] + vx[2]) > (ox[1] + ox[2]) else -1
                    if want * away <= 0:
                        continue
                    dx = min(want, hi - vx[2]) if away > 0 else max(want, lo - vx[1])
                    both = False
                else:
                    left, right = lo - min(vx[1], ox[1]), hi - max(vx[2], ox[2])
                    if left > right:
                        continue
                    dx, both = round(min(max(want, left), right)), True
                if abs(dx) < 4:
                    continue
                # (a ta'am or meteg under a vowel hangs on it - Taamey D's mark-to-mark: it moves
                #  with it; beside a yetiv or a dehi the vowel moves alone, measured below)
                rules.setdefault((plain, vowel, dx, both), []).append(ox[0])
                moved.setdefault(ch, set()).add(vowel)
    if not rules:
        return {}
    sets = gdef.MarkGlyphSetsDef
    if gdef.Version < 0x00010002 or sets is None:
        gdef.Version = 0x00010002
        gdef.MarkGlyphSetsDef = sets = ot.MarkGlyphSetsDef()
        sets.MarkSetTableFormat, sets.Coverage = 1, []
    sets.Coverage.append(otl.buildCoverage(under, rev))
    sets.MarkSetCount = len(sets.Coverage)
    fset = sets.MarkSetCount - 1
    families = {p: sorted(g for g in glyf.glyphs if _family(g, ON_A_FLOOR.get(p, (p,))) and glyph_class.get(g) != 3)
                for p in plains}
    shift_of = {}

    def shift(dx, names):
        key = (dx, tuple(sorted(set(names))))
        if key not in shift_of:
            lookups.append(otl.buildLookup([otl.buildSinglePosSubtable(
                {g: otl.buildValue({"XPlacement": dx}) for g in key[1]}, rev)], table="GPOS"))
            shift_of[key] = len(lookups) - 1
        return shift_of[key]

    def rule(bases, first, second, count, recs):
        st = ot.ChainContextPos()
        st.Format = 3
        st.BacktrackCoverage = [otl.buildCoverage(bases, rev)]
        st.InputCoverage = [otl.buildCoverage(first, rev), otl.buildCoverage(second, rev)] + \
            [otl.buildCoverage(under, rev)] * (count - 2)
        st.LookAheadCoverage = []
        st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = 1, count, 0
        st.PosLookupRecord = []
        for seq, index in recs:
            r = ot.PosLookupRecord()
            r.SequenceIndex, r.LookupListIndex = seq, index
            st.PosLookupRecord.append(r)
        st.PosCount = len(st.PosLookupRecord)
        return st
    subtables = [rule(sorted({g for p in plains for g in families[p]}), under, under, 3, [])]   # (three: as they were)
    for (plain, vowel, dx, both), seconds in sorted(rules.items()):
        recs = [(0, shift(dx, [vowel]))]
        subtables.append(rule(families[plain], [vowel], sorted(set(seconds)), 2, recs))
    chain = ot.Lookup()
    chain.LookupType, chain.LookupFlag, chain.MarkFilteringSet = 8, 0x0010, fset
    chain.SubTable, chain.SubTableCount = subtables, len(subtables)
    lookups.append(chain)
    gpos.LookupList.LookupCount = len(lookups)
    for fr in mark:
        fr.Feature.LookupListIndex.append(len(lookups) - 1)
        fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    return {ch: len(vs) for ch, vs in moved.items()}


def _bottom(glyf, name):
    glyf[name].recalcBounds(glyf)
    return getattr(glyf[name], "yMin", 0)


def _top(glyf, name):
    glyf[name].recalcBounds(glyf)
    return getattr(glyf[name], "yMax", 0)


def _chain(otl, ot, rev, bases, below, count, index, before=()):
    """"the letter (after ``before``, nearest last), ``count`` marks below": move the first by
    lookup ``index`` (None: leave them)."""
    st = ot.ChainContextPos()
    st.Format = 3
    st.BacktrackCoverage = [otl.buildCoverage(bases, rev)] + [otl.buildCoverage(c, rev) for c in reversed(before)]
    st.InputCoverage = [otl.buildCoverage(below, rev)] * count
    st.LookAheadCoverage = []
    st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = len(st.BacktrackCoverage), count, 0
    recs = []
    if index is not None:
        r = ot.PosLookupRecord()
        r.SequenceIndex, r.LookupListIndex = 0, index
        recs.append(r)
    st.PosLookupRecord, st.PosCount = recs, len(recs)
    return st


def _shva_na(path) -> None:
    """The shva na rule (scripts/add_shva_na.py: shva + varika -> Taamey D's shva na)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("add_shva_na", ROOT / "scripts" / "add_shva_na.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("  " + mod.make(Path(path)))
    print("  " + mod.resquare(Path(path)))


def _check_marks(path) -> None:
    """Every ta'am in its place (fonts/CANTILLATION.md)?"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_font_marks", ROOT / "scripts" / "check_font_marks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    problems = mod.check_font(Path(path))
    print(f"  ta'amim placement: {'every one in its place' if not problems else str(len(problems)) + ' problem(s)'}")
    for p in problems[:20]:
        print("   ", p)

if __name__ == "__main__":
    main(sys.argv[1])
    # (and its bold, made from it - scripts/make_bold.py; Mordy, 2026-10-26)
    sys.path.insert(0, str(Path(__file__).parent))
    import make_bold
    bold = OUT.with_name(OUT.stem + "-Bold.ttf")
    print(make_bold.make(OUT, bold))
    # the steps placed by the letters' ink measured again on the bold's thicker letters (the ק's
    # leg grew past its meteg - Mordy, 2026-10-29); the first takes out its own and later lookups
    t = TTFont(bold)
    print(f"  bold: a vowel and a meteg under ק: {', '.join(qof_with_meteg(t))}")
    print(f"  bold: a vowel kept in the middle beside a ta'am or meteg: {centred_with_another(t)}")
    t.save(bold)
    # (its thicker letters: no mark touching anything in Tanach or the siddurim, found by shaping
    #  every word - Mordy, 2026-11-04: the bold had never been checked; 115 siddur words touched)
    import make_stam_sefarad
    print("  bold: " + make_stam_sefarad.fix_by_shaping(bold, make_stam_sefarad.tanach_words()
                                                         + make_stam_sefarad.siddur_words()))
    _check_marks(bold)
