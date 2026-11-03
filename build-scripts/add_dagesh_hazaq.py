"""Give every font a dagesh chazak (Mordy, 2026-10-21: "the same visual difference as the shva na
and nach"): the dagesh drawn as a square, as Taamey D (Frank Sofer) draws it, for U+05C9 - the
character Unicode approved for it in 2026 (as U+05C8 for the shva na), which Phonetic MAM uses.

The font builds the letter as it would with an ordinary dagesh, and the square one is swapped in
at the end, so every way a font has of joining a letter with its dagesh (a ligature, a letter
drawn with it, the shin with its dot) is kept:

1. first of all its rules, U+05C9 becomes the font's dagesh followed by an invisible marker;
2. last of all, whatever glyph the dagesh ended up in (the dagesh alone, or a letter joined with
   it) followed by the marker becomes its twin with the dagesh squared.

Frank Sofer and the Sefer Torah fonts have Taamey D's own.  Not Ezra SIL (its licence reserves
its name): there the text gets a plain dagesh (fonts.NO_SHVA_NA).

    python scripts/add_dagesh_hazaq.py        (changes the files in fonts/; a font done already is left)
"""
from __future__ import annotations

import copy
import unicodedata
from pathlib import Path

from fontTools.otlLib import builder as otl
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot

import add_shva_na as sn

FONTS = sn.FONTS
NAME, MARKER, INPUT, SUFFIX = "dageshxazaq", "xazaq.marker", "uni05C9", ".xz"


def _contours(t: TTFont, name: str) -> list:
    glyf = t["glyf"]
    coords, ends, flags = glyf[name].getCoordinates(glyf)
    out, start = [], 0
    for end in ends:
        out.append([(tuple(coords[i]), bool(flags[i] & 1)) for i in range(start, end + 1)])
        start = end + 1
    return out


def _square(pen, pts) -> None:
    """A square about the dot's centre (add_shva_na.SQUARE times its width), clockwise."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    h = (max(xs) - min(xs)) * sn.SQUARE / 2
    for i, (x, y) in enumerate(((cx - h, cy - h), (cx - h, cy + h), (cx + h, cy + h), (cx + h, cy - h))):
        (pen.moveTo if i == 0 else pen.lineTo)((round(x), round(y)))
    pen.closePath()


def _draw(pen, contour) -> None:
    start = next(i for i, (_, on) in enumerate(contour) if on)
    seq = contour[start:] + contour[:start]
    pen.moveTo(seq[0][0])
    offs = []
    for xy, on in seq[1:] + [seq[0]]:
        if on:
            pen.qCurveTo(*offs, xy) if offs else pen.lineTo(xy)
            offs = []
        else:
            offs.append(xy)
    pen.closePath()


def _twin(t: TTFont, name: str, dagesh: str, dot: tuple) -> object:
    """``name`` (a glyph with the dagesh in it) with its dagesh squared: a composite's dagesh
    component swapped; in a glyph drawn as one outline, the contour the size of the dagesh."""
    glyf = t["glyf"]
    g = glyf[name]
    if g.isComposite():
        if not any(c.glyphName == dagesh for c in g.components):
            # (a component that is itself a letter with the dagesh: its twin)
            new = copy.deepcopy(g)
            hit = False
            for c in new.components:
                if c.glyphName + SUFFIX in glyf.glyphs:
                    c.glyphName += SUFFIX
                    hit = True
            return new if hit else None
        new = copy.deepcopy(g)
        for c in new.components:
            if c.glyphName == dagesh:
                c.glyphName = NAME
        return new
    dw, dh = dot
    pen, found = TTGlyphPen(None), False
    for contour in _contours(t, name):
        xs, ys = [p[0][0] for p in contour], [p[0][1] for p in contour]
        if not found and abs(max(xs) - min(xs) - dw) < dw * 0.25 and abs(max(ys) - min(ys) - dh) < dh * 0.25:
            _square(pen, [p[0] for p in contour])
            found = True
        else:
            _draw(pen, contour)
    return pen.glyph() if found else None


def _with_dagesh(t: TTFont, dagesh: str) -> list[str]:
    """Every glyph the dagesh can end up in: the outputs of the rules joining it with a letter,
    the letters drawn with it (Unicode's presentation forms, U+FB1D-FB4F), and what other rules
    turn those into (alternate forms), over and over."""
    found = {dagesh}
    cmap = t.getBestCmap()
    for cp, g in cmap.items():
        if 0xFB1D <= cp <= 0xFB4F and "05BC" in unicodedata.decomposition(chr(cp)).split():
            found.add(g)
    lookups = t["GSUB"].table.LookupList.Lookup
    while True:
        before = len(found)
        for lk in lookups:
            for st in lk.SubTable:
                st = getattr(st, "ExtSubTable", st)
                for first, ligs in (getattr(st, "ligatures", None) or {}).items():
                    for lig in ligs:
                        if found & ({first} | set(lig.Component)):
                            found.add(lig.LigGlyph)
                for a, b in (getattr(st, "mapping", None) or {}).items():
                    if a in found and isinstance(b, str):
                        found.add(b)
                for a, bs in (getattr(st, "alternates", None) or {}).items():
                    if a in found:
                        found.update(bs)
        if len(found) == before:
            return sorted(found, key=t.getGlyphID)


def _shift_lookup_indices(t: TTFont, by: int) -> None:
    """Every reference to a GSUB lookup moved up by ``by`` (a lookup was put in front)."""
    gsub = t["GSUB"].table
    for fr in gsub.FeatureList.FeatureRecord:
        fr.Feature.LookupListIndex = [i + by for i in fr.Feature.LookupListIndex]
    for lk in gsub.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            for attr in ("SubstLookupRecord",):
                for rec in getattr(st, attr, None) or []:
                    rec.LookupListIndex += by
            for attr in ("SubRuleSet", "SubClassSet", "ChainSubRuleSet", "ChainSubClassSet"):
                for rs in getattr(st, attr, None) or []:
                    if rs is None:
                        continue
                    for rule in getattr(rs, "SubRule", None) or getattr(rs, "SubClassRule", None) or \
                            getattr(rs, "ChainSubRule", None) or getattr(rs, "ChainSubClassRule", None) or []:
                        for rec in rule.SubstLookupRecord:
                            rec.LookupListIndex += by
    if getattr(gsub, "FeatureVariations", None):
        raise ValueError("feature variations: not handled")


def _to_features(t: TTFont, index: int, front: bool) -> None:
    """Lookup ``index`` in ccmp (made for every script and language when the font has none)."""
    gsub = t["GSUB"].table
    recs = [fr for fr in gsub.FeatureList.FeatureRecord if fr.FeatureTag == "ccmp"]
    if not recs:
        fr = ot.FeatureRecord()
        fr.FeatureTag, fr.Feature = "ccmp", ot.Feature()
        fr.Feature.LookupListIndex, fr.Feature.LookupCount = [], 0
        gsub.FeatureList.FeatureRecord.append(fr)
        gsub.FeatureList.FeatureCount = len(gsub.FeatureList.FeatureRecord)
        fi = gsub.FeatureList.FeatureCount - 1
        for sr in gsub.ScriptList.ScriptRecord:
            for ls in [sr.Script.DefaultLangSys] + [r.LangSys for r in sr.Script.LangSysRecord]:
                if ls is not None:
                    ls.FeatureIndex.append(fi)
                    ls.FeatureCount = len(ls.FeatureIndex)
        recs = [fr]
    for fr in recs:
        idx = fr.Feature.LookupListIndex
        fr.Feature.LookupListIndex = [index] + idx if front else idx + [index]
        fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)


def make(path: Path) -> str:
    t = TTFont(path)
    cmap = t.getBestCmap()
    if 0x05BC not in cmap:
        return f"{path.name}: no dagesh"
    if 0x05C9 in cmap:
        return f"{path.name}: done already"
    dagesh, glyf = cmap[0x05BC], t["glyf"]
    holders = _with_dagesh(t, dagesh)
    gdef = t["GDEF"].table
    # the new glyphs: U+05C9 and the marker (empty marks), the square dagesh (a mark like the dagesh)
    for name in (INPUT, MARKER):
        sn._add_glyph(t, name, TTGlyphPen(None).glyph(), (0, 0))
        gdef.GlyphClassDef.classDefs[name] = 3
    for table in t["cmap"].tables:
        if table.isUnicode():
            table.cmap[0x05C9] = INPUT
    pen = TTGlyphPen(None)
    for c in _contours(t, dagesh):
        _square(pen, [p[0] for p in c])
    sn._add_glyph(t, NAME, pen.glyph(), t["hmtx"][dagesh])
    sn._as_mark_like(t, NAME, dagesh)
    glyf[dagesh].recalcBounds(glyf)
    dot = (glyf[dagesh].xMax - glyf[dagesh].xMin, glyf[dagesh].yMax - glyf[dagesh].yMin)
    # each glyph with the dagesh in it: its twin with the square one
    # (again and again: a letter drawn from another that has the dagesh - Frank Ruehl's שּׁ is
    #  its שּ with the shin's dot - gets its twin once that one has it)
    swap, todo = {dagesh: NAME}, [n for n in holders if n != dagesh]
    while todo:
        left = []
        for name in todo:
            g = _twin(t, name, dagesh, dot)
            if g is None:
                left.append(name)
                continue
            twin = name + SUFFIX
            sn._add_glyph(t, twin, g, t["hmtx"][name])
            glyf[twin].recalcBounds(glyf)
            sn_copy_as_base(t, twin, name)
            swap[name] = twin
        if len(left) == len(todo):
            break
        todo = left
    missed = todo
    # (the square dagesh and the twins count as the dagesh and its letters wherever the font's
    #  positioning rules look at them - Taamey Ashkenaz sets a vowel aside for a dagesh)
    for old, new in swap.items():
        _alias_in_rules(t, old, new)
    # 1. first: U+05C9 -> the dagesh and the marker
    gsub = t["GSUB"].table
    first = otl.buildLookup([otl.buildMultipleSubstSubtable({INPUT: [dagesh, MARKER]})], table="GSUB")
    _shift_lookup_indices(t, 1)
    gsub.LookupList.Lookup.insert(0, first)
    _to_features(t, 0, front=True)
    # 2. last: (the glyph with the dagesh, the marker) -> its twin; the other marks looked past
    if gdef.Version < 0x00010002:
        gdef.Version = 0x00010002
    if getattr(gdef, "MarkGlyphSetsDef", None) is None:
        gdef.MarkGlyphSetsDef = ot.MarkGlyphSetsDef()
        gdef.MarkGlyphSetsDef.MarkSetTableFormat = 1
        gdef.MarkGlyphSetsDef.Coverage = []
    sets = gdef.MarkGlyphSetsDef
    sets.Coverage.append(otl.buildCoverage([MARKER, dagesh], t.getReverseGlyphMap()))
    sets.MarkSetCount = len(sets.Coverage)
    last = otl.buildLookup([otl.buildLigatureSubstSubtable({(g, MARKER): tw for g, tw in swap.items()})],
                           flags=0x0010, markFilterSet=sets.MarkSetCount - 1, table="GSUB")
    gsub.LookupList.Lookup.append(last)
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
    index = gsub.LookupList.LookupCount - 1
    # (in every feature that joins a letter with its dagesh too, so it runs after them all)
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "ccmp" or any(_joins(gsub.LookupList.Lookup[i], dagesh) for i in fr.Feature.LookupListIndex):
            fr.Feature.LookupListIndex.append(index)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    t.save(path)
    note = f"; left as they are: {', '.join(missed)}" if missed else ""
    return f"{path.name}: dagesh chazak added ({len(swap) - 1} letters joined with it){note}"


def _alias_in_rules(t: TTFont, like: str, new: str) -> None:
    """In GPOS and GSUB: every class that holds ``like`` holds ``new`` too, and every contextual
    rule's coverage that has ``like`` has ``new`` (Taamey Ashkenaz draws a quiet א by the marks
    after it, and sets a vowel aside for a dagesh)."""
    gid = t.getGlyphID

    def walk(obj, in_context):
        if isinstance(obj, ot.ClassDef):
            if like in obj.classDefs:
                obj.classDefs[new] = obj.classDefs[like]
            return
        if isinstance(obj, ot.Coverage):
            if in_context and like in obj.glyphs and new not in obj.glyphs:
                obj.glyphs = sorted(obj.glyphs + [new], key=gid)
            return
        if isinstance(obj, list):
            for x in obj:
                walk(x, in_context)
            return
        if not hasattr(obj, "__dict__"):
            return
        ctx = in_context or type(obj).__name__ in CONTEXT
        for k, v in vars(obj).items():
            if isinstance(v, (ot.BaseTable, list, ot.ClassDef, ot.Coverage)):
                walk(v, ctx)

    for tag in ("GPOS", "GSUB"):
        for lk in t[tag].table.LookupList.Lookup:
            for st in lk.SubTable:
                st = getattr(st, "ExtSubTable", st)
                walk(st, type(st).__name__ in CONTEXT)


CONTEXT = ("ContextPos", "ChainContextPos", "PosRule", "PosClassRule", "ChainPosRule", "ChainPosClassRule",
           "ContextSubst", "ChainContextSubst", "SubRule", "SubClassRule", "ChainSubRule", "ChainSubClassRule")


def _joins(lk, dagesh: str) -> bool:
    for st in lk.SubTable:
        st = getattr(st, "ExtSubTable", st)
        for first, ligs in (getattr(st, "ligatures", None) or {}).items():
            if first == dagesh or any(dagesh in lig.Component for lig in ligs):
                return True
    return False


def sn_copy_as_base(t: TTFont, new: str, like: str) -> None:
    """``new`` placed as a base exactly like ``like`` (its class, its anchors for the marks)."""
    gid = t.getGlyphID
    gdef = t["GDEF"].table
    if like in gdef.GlyphClassDef.classDefs:
        gdef.GlyphClassDef.classDefs[new] = gdef.GlyphClassDef.classDefs[like]
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            for cov_attr, arr_attr, rec_attr, count in (("BaseCoverage", "BaseArray", "BaseRecord", "BaseCount"),
                                                        ("LigatureCoverage", "LigatureArray", "LigatureAttach", "LigatureCount"),
                                                        ("Mark2Coverage", "Mark2Array", "Mark2Record", "Mark2Count")):
                cov = getattr(st, cov_attr, None)
                if cov is None or like not in cov.glyphs or new in cov.glyphs:
                    continue
                arr = getattr(st, arr_attr)
                recs = getattr(arr, rec_attr)
                pairs = list(zip(cov.glyphs, recs)) + [(new, copy.deepcopy(recs[cov.glyphs.index(like)]))]
                pairs.sort(key=lambda p: gid(p[0]))
                cov.glyphs = [p[0] for p in pairs]
                setattr(arr, rec_attr, [p[1] for p in pairs])
                setattr(arr, count, len(pairs))


if __name__ == "__main__":
    for f in sn.files():
        print(make(FONTS / f))
