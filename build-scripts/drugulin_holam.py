"""Drugulin's cholam where Frank Sofer puts it (Mordy, 2026-11-17: "I feel like franks are a bit lower and
more to the right in many cases. Can u compare them and standardize?").

For each letter (and the letter with a dagesh or dagesh chazak), the cholam is set as Frank Sofer sets it
over the same letter: the same gap above the letter's top, and its middle the same distance from the
letter's left edge - measured by shaping both fonts.  It is one rule, last in the "mark" feature.  ו (the
cholam male, centred), ל (לֹא has its own glyph) and ש (the shin dot) keep their own rules.

    .venv/Scripts/python scripts/drugulin_holam.py <Drugulin.ttf> <FrankSofer.ttf>     (in place)

Run after drugulin_dagesh.py and before the collision fixer (finish_mekorot_fonts.py), whose rules come
after this one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.otlLib import builder as otl
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

LETTERS = "אבגדהזחטיכךמםנןסעפףצץקרת"
HOLAM = 0x05B9


def _box(t, name):
    gs = t.getGlyphSet()
    b = BoundsPen(gs)
    gs[name].draw(b)
    return b.bounds


def _placed(path: Path, text: str):
    """(letter glyph, its x, y), (cholam glyph, its x, y) as shaped."""
    f = hb.Font(hb.Face(hb.Blob(path.read_bytes())))
    t = TTFont(path)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(f, buf)
    x, out = 0, []
    for i, p in zip(buf.glyph_infos, buf.glyph_positions):
        out.append((t.getGlyphName(i.codepoint), x + p.x_offset, p.y_offset))
        x += p.x_advance
    holam = t.getBestCmap()[HOLAM]
    marks = [q for q in out if q[0] == holam]
    bases = [q for q in out if q[0] != holam]
    return (bases[0], marks[0]) if marks and bases else (None, None)


def frank_places(frank: Path) -> dict:
    """For each letter: (the cholam's middle from the letter's left edge, its bottom above the letter's top)."""
    t = TTFont(frank)
    out = {}
    for c in LETTERS:
        (ln, lx, ly), (hn, hx, hy) = _placed(frank, c + chr(HOLAM))
        lb, hbx = _box(t, ln), _box(t, hn)
        out[c] = (hx + (hbx[0] + hbx[2]) / 2 - (lx + lb[0]), hy + hbx[1] - (ly + lb[3]))
    return out


def fix(path: Path, frank: Path) -> str:
    want = frank_places(frank)
    t = TTFont(path)
    cmap = t.getBestCmap()
    holam = cmap[HOLAM]
    hb_ = _box(t, holam)
    mark_anchor = otl.buildAnchor(round((hb_[0] + hb_[2]) / 2), round(hb_[1]))
    glyf = t["glyf"]
    bases = {}
    for c, (dx, gap) in want.items():
        letter = cmap.get(ord(c))
        if not letter:
            continue
        x0, _, _, top = _box(t, letter)
        anchor = otl.buildAnchor(round(x0 + dx), round(top + gap))
        bases[letter] = {0: anchor}
        # (the form the font sets before a cholam - א becomes "alef.con")
        shaped, _ = _placed(path, c + chr(HOLAM))
        if shaped and shaped[0] != letter:
            sx0, _, _, stop = _box(t, shaped[0])
            bases[shaped[0]] = {0: otl.buildAnchor(round(sx0 + dx), round(stop + gap))}
        # (the same letter with a dagesh or dagesh chazak: the same ink, the same place)
        for name in t.getGlyphOrder():
            g = glyf[name]
            if (name != letter and g.isComposite() and g.components[0].glyphName == letter
                    and g.components[0].x == 0 and g.components[0].y == 0
                    and all(k.glyphName in ("dagesh", "dageshxazaq") for k in g.components[1:])):
                bases[name] = {0: anchor}
    # the cholam of the letter before an א, drawn over the א's head ("alef.xolam": רֹאשׁ, בֹּא): as far from
    # the א's right edge and as high above it as in Frank Sofer (Mordy, 2026-11-17: "can we fix the א too")
    ft = TTFont(frank)
    for name in [n for n in t.getGlyphOrder() if n.endswith(".xolam")]:
        if name not in ft["glyf"].glyphs or not glyf[name].isComposite() or not ft["glyf"][name].isComposite():
            continue
        def parts(font, g):
            letter = next((c for c in g.components if "olam" not in c.glyphName), None)
            mark = next((c for c in g.components if "olam" in c.glyphName), None)
            return letter, mark
        fl, fm = parts(ft, ft["glyf"][name])
        dl, dm = parts(t, glyf[name])
        if None in (fl, fm, dl, dm):
            continue
        fb, fh = _box(ft, fl.glyphName), _box(ft, fm.glyphName)
        db, dh = _box(t, dl.glyphName), _box(t, dm.glyphName)
        from_right = (fl.x + fb[2]) - (fm.x + (fh[0] + fh[2]) / 2)
        gap = (fm.y + fh[1]) - (fl.y + fb[3])
        dm.x = round(dl.x + db[2] - from_right - (dh[0] + dh[2]) / 2)
        dm.y = round(dl.y + db[3] + gap - dh[1])
        glyf[name].recalcBounds(glyf)
    gpos = t["GPOS"].table
    lk = otl.buildLookup([otl.buildMarkBasePosSubtable({holam: (0, mark_anchor)}, bases, t.getReverseGlyphMap())],
                         table="GPOS")
    gpos.LookupList.Lookup.append(lk)
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "mark":
            fr.Feature.LookupListIndex.append(len(gpos.LookupList.Lookup) - 1)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    __import__("gpos_ext").as_extensions(t)
    t.save(path)
    return f"{path.name}: the cholam over {len(bases)} glyphs set as in {frank.name}"


if __name__ == "__main__":
    print(fix(Path(sys.argv[1]), Path(sys.argv[2])))
