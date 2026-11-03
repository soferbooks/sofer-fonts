"""The meteg right beside its vowel, in every font that sets it elsewhere (Mordy, 2026-10-25:
"why is the meteg so far from the nikkud?").

Frank Ruehl puts the meteg at one place under each letter, wherever the vowel is: up to a third
of a letter away from it, or touching it (a kubutz under a נ); David Libre further still; Noto
Serif Hebrew and Noto Rashi on the vowel; Keter YG's and Simple's slanted styles touching it.
The fonts that set it well (Frank Sofer - Taamey D - Keter YG, Simple, the Taamey fonts, Keter
Aram Tsova, Shofar) keep it about 0.045 of the letter's height to the left of the vowel.

Each font that needs it gets one more GPOS lookup (mark to mark, last in the "mark" feature):
a meteg after a vowel under the same letter is set GAP to the left of the vowel's ink, at the
height the font itself gives it beside that vowel; a meteg with no vowel before it (on a shuruk)
is left where the font puts it.  Measured with HarfBuzz before and after (scripts/check_meteg.py
checks every meteg of the siddur and the Tanach for collisions).

    .venv/Scripts/python scripts/place_meteg.py      (changes the files in fonts/; a font done is left)
"""
from __future__ import annotations

import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.otlLib import builder as otl
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot

FONTS = Path(__file__).resolve().parents[1] / "fonts"
GAP = 0.045                     # (of the em: the good fonts' own gap)
# the vowels under the letter a meteg can follow (and the kamatz katan, shva na) - not the
# cholam, which is over the letter
VOWELS = [*range(0x05B0, 0x05B9), 0x05BB, 0x05C7, 0x05C8]
LETTERS = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"
# built by their own scripts (make_frank_sofer.py, make_stam_sefarad.py), which set the meteg well
SKIP = {"FrankSofer.ttf", "SoferStamSefarad.ttf", "SoferStamAshkenaz.ttf",
        "ShofarDemi-Bold.ttf"}      # (its vowels are other glyphs by then: the lookup does not reach them - kept)
# fonts whose letters are not set apart for the meteg (clear() spaces them for the widest vowel the
# next letter could have - gaps in וַֽיַּ, Mordy 2026-10-25: "fix taamei ashkenaz"); a meteg that
# touches is cleared there by scripts/clear_meteg.py, word by word
NO_SPACING = {"TaameyAshkenaz-Medium.ttf", "TaameyAshkenaz-Bold.ttf", "KeterAramTsova.ttf", "KeterYG-Medium.ttf",
              "KeterYG-Bold.ttf", "TaameyDavidCLM-Medium.ttf", "TaameyDavidCLM-Bold.ttf", "ShofarRegular.ttf"}


def _positions(font: hb.Font, text: str):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return list(zip(buf.glyph_infos, buf.glyph_positions))


def gaps(path: Path) -> list[float]:
    """The meteg's gap from each vowel under each letter, in em (negative: overlapping)."""
    font = hb.Font(hb.Face(hb.Blob(Path(path).read_bytes())))
    meteg = _positions(font, "ֽ")[0][0].codepoint
    out = []
    for v in VOWELS:
        for letter in LETTERS:
            got = _positions(font, letter + chr(v) + "ֽ")
            pen, boxes = 0, []
            for info, pos in got:
                e = font.get_glyph_extents(info.codepoint)
                x0 = pen + pos.x_offset + e.x_bearing
                boxes.append((info.codepoint, x0, x0 + e.width))
                pen += pos.x_advance
            m = [b for b in boxes if b[0] == meteg]
            rest = [b for b in boxes[1:] if b[0] != meteg]
            # (a letter and vowel drawn as one glyph - ךָ - has no vowel of its own to measure)
            if m and rest and len(boxes) == 3:
                out.append((rest[0][1] - m[0][2]) / font.face.upem)
    return out


def needs(path: Path) -> bool:
    g = gaps(path)
    return bool(g) and (min(g) < 0.02 or max(g) - min(g) > 0.03)


def make(path: Path) -> str:
    t = TTFont(path)
    names = {r.toUnicode() for r in t["name"].names if r.nameID == 5}
    if any("meteg placed" in n for n in names):
        return f"{path.name}: done already"
    if not needs(path):
        return f"{path.name}: sets the meteg well already"
    cmap, glyf, upem = t.getBestCmap(), t["glyf"], t["head"].unitsPerEm
    meteg = cmap.get(0x05BD)
    if meteg is None:
        return f"{path.name}: no meteg"
    gdef = t["GDEF"].table
    classes = gdef.GlyphClassDef.classDefs
    # the vowel glyphs: those of the vowels' characters, and every mark drawn under the line that
    # is not a ta'am or the meteg (the font's own alternates of them)
    taamim = {cmap[c] for c in range(0x0591, 0x05B0) if c in cmap}
    vowels = {cmap[c] for c in VOWELS if c in cmap}
    for g, k in classes.items():
        if k == 3 and g in glyf.glyphs and g not in taamim and g != meteg:
            gl = glyf[g]
            gl.recalcBounds(glyf)
            if getattr(gl, "numberOfContours", 0) and gl.yMax < 0:
                vowels.add(g)
    vowels.discard(meteg)
    glyf[meteg].recalcBounds(glyf)
    m_right = glyf[meteg].xMax
    font = hb.Font(hb.Face(hb.Blob(Path(path).read_bytes())))
    rev_cmap = {g: c for c, g in cmap.items()}
    gap = round(GAP * upem)
    base_marks = {}
    for v in sorted(vowels):
        gl = glyf[v]
        gl.recalcBounds(glyf)
        if not getattr(gl, "numberOfContours", 0):
            continue
        # the meteg's height beside this vowel, as the font sets it (under ב); a vowel with no
        # character of its own: as beside the kamatz
        ch = rev_cmap.get(v, 0x05B8)
        got = _positions(font, "ב" + chr(ch) + "ֽ")
        mpos = next((p for i, p in got if i.codepoint == t.getGlyphID(meteg)), None)
        vpos = next((p for i, p in got[1:] if i.codepoint != t.getGlyphID(meteg)), None)
        dy = (mpos.y_offset - vpos.y_offset) if mpos and vpos else 0
        base_marks[v] = {0: otl.buildAnchor(gl.xMin - gap, dy)}
    rev = t.getReverseGlyphMap()
    sub = ot.MarkMarkPos()
    sub.Format = 1
    sub.Mark1Coverage = otl.buildCoverage([meteg], rev)
    sub.Mark2Coverage = otl.buildCoverage(sorted(base_marks, key=rev.get), rev)
    sub.ClassCount = 1
    sub.Mark1Array = otl.buildMarkArray({meteg: (0, otl.buildAnchor(m_right, 0))}, rev)
    sub.Mark2Array = ot.Mark2Array()
    sub.Mark2Array.Mark2Record = [otl.buildMark2Record([base_marks[g][0]]) for g in sub.Mark2Coverage.glyphs]
    sub.Mark2Array.Mark2Count = len(sub.Mark2Array.Mark2Record)
    # (a filtering set: only the vowels and the meteg - a dagesh or shin dot between them passed over)
    if not hasattr(gdef, "MarkGlyphSetsDef") or gdef.MarkGlyphSetsDef is None:
        gdef.Version = 0x00010002
        gdef.MarkGlyphSetsDef = ot.MarkGlyphSetsDef()
        gdef.MarkGlyphSetsDef.MarkSetTableFormat = 1
        gdef.MarkGlyphSetsDef.Coverage = []
        gdef.MarkGlyphSetsDef.MarkSetCount = 0
    sets = gdef.MarkGlyphSetsDef
    sets.Coverage.append(otl.buildCoverage(sorted(set(base_marks) | {meteg}), rev))
    sets.MarkSetCount = len(sets.Coverage)
    lookup = otl.buildLookup([sub], flags=0x0010, markFilterSet=sets.MarkSetCount - 1, table="GPOS")
    gpos = t["GPOS"].table
    gpos.LookupList.Lookup.append(lookup)
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)
    index = len(gpos.LookupList.Lookup) - 1
    added = 0
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "mark":
            fr.Feature.LookupListIndex.append(index)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
            added += 1
    if not added:
        return f"{path.name}: no mark feature - left as it was"
    for r in t["name"].names:
        if r.nameID == 5:
            r.string = r.toUnicode() + "; Sofer: meteg placed"
    before = gaps(path)
    import io
    buf = io.BytesIO()
    t.save(buf)
    t.close()
    path.write_bytes(buf.getvalue())
    after = gaps(path)
    return (f"{path.name}: meteg beside its vowel - gap was {min(before):.3f} to {max(before):.3f} em, "
            f"now {min(after):.3f} to {max(after):.3f}")


CLEAR = 0.025                   # (of the em: the least space left between a meteg and other ink)


def _glyphs(font: hb.Font, text: str) -> list[tuple[int, int, int, int]]:
    """(glyph, x, y, advance) of each glyph, left to right as printed."""
    out, pen = [], 0
    for info, pos in _positions(font, text):
        out.append((info.codepoint, pen + pos.x_offset, pos.y_offset, pos.x_advance))
        pen += pos.x_advance
    return out


def clear(path: Path) -> str:
    """No meteg touching anything (Mordy, 2026-10-25: "check for collisions with the meteg";
    scripts/check_meteg.py finds them), measured on every letter (with and without a dagesh, ש
    with its dots) and every vowel:
    * a meteg with no vowel under its letter (a cholam over it: עֹֽרֶף; a shuruk: וּֽ) is set in the
      middle under the letter, as a siddur has it (the fonts put it where a vowel would have been);
    * where the meteg beside the vowel's left would touch the letter's leg (ק), the vowel and the
      meteg move right together (Mordy: the meteg on the left "like normal"; as Frank Sofer does);
      a meteg alone there sits in the room beside the leg;
    * a meteg reaching past its letter's edge into the letter beside it, where that letter has ink
      at the meteg's height (its vowel, a final letter's tail), has the two letters set apart by
      as much as is needed (the left-hand letter's advance larger).
    More GPOS lookups after make()'s, in the "mark" feature."""
    sys.path.insert(0, str(Path(__file__).parent))
    from check_meteg import Ink
    t = TTFont(path)
    names = {r.toUnicode() for r in t["name"].names if r.nameID == 5}
    if any("meteg cleared" in n for n in names):
        return f"{path.name}: cleared already"
    cmap, glyf, upem = t.getBestCmap(), t["glyf"], t["head"].unitsPerEm
    meteg = cmap.get(0x05BD)
    if meteg is None:
        return f"{path.name}: no meteg"
    order, gid = t.getGlyphOrder(), t.getGlyphID
    font = hb.Font(hb.Face(hb.Blob(Path(path).read_bytes())))
    ink = Ink(path)
    step = ink.step
    near = max(1, round(CLEAR * upem / step))
    clear_u = round(CLEAR * upem)
    gdef = t["GDEF"].table
    # (Frank Ruehl's own table does not call the meteg a mark: it is one)
    gdef.GlyphClassDef.classDefs[meteg] = 3
    marks = {g for g, k in gdef.GlyphClassDef.classDefs.items() if k == 3}
    mark_ids = {gid(g) for g in marks if g in t.getReverseGlyphMap()}
    vowels = [chr(v) for v in VOWELS if v in cmap]
    # every letter as printed: alone, with a dagesh, ש with its dots - (its text, its base glyph)
    variants = {}
    for ch in LETTERS:
        if ord(ch) not in cmap:
            continue
        for text in (ch, ch + "ּ") + ((ch + "ׁ", ch + "ׂ", ch + "ּׁ", ch + "ּׂ")
                                            if ch == "ש" else ()):
            got = _glyphs(font, text)
            base = next((g for g in got if g[0] not in mark_ids), None)
            if base is not None:
                variants.setdefault(order[base[0]], text)

    def cells(g, x, y):
        return {(cx + x // step, cy + y // step) for cx, cy in ink.cells(g)}

    def shaped(text):
        got = _glyphs(font, text)
        base = next(g for g in got if g[0] not in mark_ids)
        m = next((g for g in got if g[0] == gid(meteg)), None)
        return got, base, m

    def reach(base, mc):
        xs = [x * step for x, _ in mc]
        return base[1] - min(xs), max(xs) + step - (base[1] + base[3])

    def touches(base, mc):
        """Does the meteg come near the letter's ink under the line (ק's leg, a final letter's
        tail)?  (Its foot on the line is over every meteg, as the font made it.)"""
        bc = {(x, y) for x, y in cells(base[0], base[1], base[2]) if y * step < -clear_u}
        grown = {(x + a, y + b) for x, y in bc for a in range(-near, near + 1) for b in range(-near, near + 1)}
        return bool(mc & grown)

    def free_mid(base, mc, prefer):
        """Where under the letter a meteg (its cells mc) is clear of the letter's ink under the
        line: the shift nearest ``prefer`` (0: where it is) that clears it, or None."""
        for d in sorted(range(-base[3], base[3] + 1, step), key=lambda d: abs(d - prefer)):
            if not touches(base, {(x + round(d / step), y) for x, y in mc}):
                return d
        return None

    # 1. a meteg alone under its letter: in the middle - or, beside a leg (ק), in the middle of
    #    the room beside it (the shift for each letter)
    centre, band = {}, None
    for name, text in variants.items():
        got, base, m = shaped(text + "ֽ")
        if m is None:
            continue
        mc = cells(m[0], m[1], m[2])
        if band is None:
            ys = [y * step for _, y in mc]
            band = (min(ys) - clear_u, max(ys) + step + clear_u)
        e = font.get_glyph_extents(m[0])
        middle = round(base[1] + base[3] / 2 - (m[1] + e.x_bearing + e.width / 2))
        d = free_mid(base, mc, middle)
        centre[name] = middle if d is None else d
    # 2. beside a vowel, the meteg stays on its left (Mordy, 2026-10-25: "like normal"); where it
    #    would touch the letter's leg (ק), the vowel and the meteg move right together, as far as
    #    needed (as Frank Sofer sets them)
    vshift, reach_l, reach_r = {}, {}, {}
    for name, text in variants.items():
        for v in vowels:
            got, base, m = shaped(text + v + "ֽ")
            if m is None:
                continue
            mc = cells(m[0], m[1], m[2])
            vg = next((g for g in got if g[0] in mark_ids and g[0] != m[0]
                       and font.get_glyph_extents(g[0]).y_bearing < 0), None)
            if touches(base, mc) and vg is not None:
                vc = cells(vg[0], vg[1], vg[2])
                for d in range(step, base[3] + 1, step):
                    k = round(d / step)
                    if not touches(base, {(x + k, y) for x, y in mc | vc}):
                        vshift[(name, order[vg[0]])] = d
                        mc = {(x + k, y) for x, y in mc}
                        break
            l, r = reach(base, mc)
            reach_l[name] = max(reach_l.get(name, -upem), l)
            reach_r[name] = max(reach_r.get(name, -upem), r)
        # (alone)
        got, base, m = shaped(text + "ֽ")
        if m is not None and name in centre:
            mc = {(x + round(centre[name] / step), y) for x, y in cells(m[0], m[1], m[2])}
            l, r = reach(base, mc)
            reach_l[name] = max(reach_l.get(name, -upem), l)
            reach_r[name] = max(reach_r.get(name, -upem), r)
    # each letter's free room at the meteg's height, on its right and left side, its vowels included
    room_r, room_l = {}, {}
    for name, text in variants.items():
        for v in [""] + vowels:
            got = _glyphs(font, text + v)
            base = next(g for g in got if g[0] not in mark_ids)
            xs = [x * step for g in got for x, y in cells(g[0], g[1], g[2]) if band[0] <= y * step <= band[1]]
            rr = base[1] + base[3] - (max(xs) + step) if xs else base[3]
            ll = (min(xs) - base[1]) if xs else base[3]
            room_r[name] = min(room_r.get(name, rr), rr)
            room_l[name] = min(room_l.get(name, ll), ll)

    def q(x):
        return int(-(-x // 10) * 10)                    # (up to the next 10 units)
    rev = t.getReverseGlyphMap()
    vowel_glyphs = sorted(g for g in marks if g in glyf.glyphs and g != meteg and getattr(glyf[g], "numberOfContours", 0)
                          and (glyf[g].recalcBounds(glyf) or glyf[g].yMax < 0))
    sets = gdef.MarkGlyphSetsDef
    sets.Coverage.append(otl.buildCoverage(sorted(set(vowel_glyphs) | {meteg}, key=rev.get), rev))
    sets.MarkSetCount = len(sets.Coverage)
    fset = sets.MarkSetCount - 1
    gpos = t["GPOS"].table
    lookups = gpos.LookupList.Lookup
    in_feature = []

    def add(lookup):
        lookups.append(lookup)
        return len(lookups) - 1

    def cov(glyphs):
        return otl.buildCoverage(sorted(set(glyphs), key=rev.get), rev)

    def chain(inputs, records):
        st = ot.ChainContextPos()
        st.Format = 3
        st.BacktrackCoverage, st.BacktrackGlyphCount = [], 0
        st.LookAheadCoverage, st.LookAheadGlyphCount = [], 0
        st.InputCoverage = [cov(c) for c in inputs]
        st.InputGlyphCount = len(inputs)
        st.PosLookupRecord = []
        for i, index in records:
            r = ot.PosLookupRecord()
            r.SequenceIndex, r.LookupListIndex = i, index
            st.PosLookupRecord.append(r)
        st.PosCount = len(st.PosLookupRecord)
        return st

    def chain_lookup(subtables):
        lk = ot.Lookup()
        lk.LookupType, lk.LookupFlag, lk.MarkFilteringSet = 8, 0x0010, fset
        lk.SubTable = subtables
        lk.SubTableCount = len(subtables)
        in_feature.append(add(lk))

    def single(values):
        return add(otl.buildLookup([otl.buildSinglePosSubtable(
            {g: otl.buildValue(v) for g, v in values.items()}, rev)], table="GPOS"))

    did = []
    # 1. alone: in the middle (a lookup on the meteg, by the letter before it)
    by_shift = {}
    for name, dx in centre.items():
        if abs(dx) >= 10:
            by_shift.setdefault(q(dx) if dx > 0 else -q(-dx), set()).add(name)
    if by_shift:
        chain_lookup([chain([bs, {meteg}], [(1, single({meteg: {"XPlacement": dx}}))])
                      for dx, bs in sorted(by_shift.items())])
        did.append("alone: in the middle under its letter")
    # 2. under a leg: the vowel (and the meteg on it) moved right
    if vshift:
        by_d = {}
        for (name, vg), d in vshift.items():
            by_d.setdefault(q(d), {}).setdefault(name, set()).add(vg)
        subs = []
        for d, names in sorted(by_d.items()):
            move = single({vg: {"XPlacement": d} for vgs in names.values() for vg in vgs})
            for name, vgs in names.items():
                subs.append(chain([{name}, vgs, {meteg}], [(1, move)]))
        chain_lookup(subs)
        did.append("the vowel moved right under " + "".join(sorted({variants[n][0] for n, _ in vshift})))
    # 3. letters set apart where the meteg reaches the letter beside it
    subtables, need_lookups = [], {}

    def by_need(need):
        if need not in need_lookups:
            need_lookups[need] = single({g: {"XAdvance": need} for g in variants})
        return need_lookups[need]
    pairs = {}
    for b, rl in reach_l.items():
        for n, room in room_r.items():
            need = q(rl + clear_u - room)
            if need > 0:
                pairs.setdefault(need, {}).setdefault(b, set()).add(n)
    for need, bs in sorted(pairs.items(), reverse=True):
        by_next = {}
        for b, ns in bs.items():
            by_next.setdefault(frozenset(ns), set()).add(b)
        for ns, group in by_next.items():
            # (with a vowel under the letter, or the meteg alone)
            subtables.append(chain([group, set(vowel_glyphs), {meteg}, ns], [(3, by_need(need))]))
            subtables.append(chain([group, {meteg}, ns], [(2, by_need(need))]))
    worst_l = min(room_l.values())
    for b, rr in sorted(reach_r.items()):
        need = q(rr + clear_u - worst_l)
        if need > 0:
            subtables.append(chain([{b}, set(vowel_glyphs), {meteg}], [(0, by_need(need))]))
            subtables.append(chain([{b}, {meteg}], [(0, by_need(need))]))
    if subtables:
        chain_lookup(subtables)
        did.append(f"letters set apart ({len(subtables)} rules)")
    for index in in_feature:
        for fr in gpos.FeatureList.FeatureRecord:
            if fr.FeatureTag == "mark":
                fr.Feature.LookupListIndex.append(index)
                fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    gpos.LookupList.LookupCount = len(lookups)
    for r in t["name"].names:
        if r.nameID == 5:
            r.string = r.toUnicode() + "; Sofer: meteg cleared"
    import io
    buf = io.BytesIO()
    t.save(buf)
    t.close()
    path.write_bytes(buf.getvalue())
    return f"{path.name}: " + ("; ".join(did) or "nothing touched")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    from add_shva_na import files
    for f in sys.argv[1:] or [f for f in files() if f not in SKIP]:
        print(make(FONTS / f))
        if f not in NO_SPACING:
            print(clear(FONTS / f))
