"""Drugulin's dagesh where Culmus drew it, and the marks under ם centred (Mordy, 2026-11-17: "the dagesh is
centered on every frank letter but not in druglin ... look thru the original druglin"; "the ם nikkud is all
over the place").

Drugulin CLM has every letter with its dagesh drawn as one glyph (U+FB30-FB4A): the dot is the smallest
contour of each.  The built font's letters-with-dagesh are the letter and Frank Sofer's dagesh as components,
placed by make_stam_sefarad.by_shape in the letter's open space - off the designer's place in Drugulin's
heavy letters.  Here each dagesh, and each dagesh chazak's square (dageshxazaq), is put with its middle on
the middle of Culmus' own dot.  The marks under ם are put under its middle, as high as under מ.

    .venv/Scripts/python scripts/drugulin_dagesh.py <Drugulin.ttf> <DrugulinCLM-2048.ttf> [pad]   (in place)
"""
from __future__ import annotations

import sys
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

# (the precomposed letter with dagesh, for each letter)
WITH_DAGESH = {0x5D0: 0xFB30, 0x5D1: 0xFB31, 0x5D2: 0xFB32, 0x5D3: 0xFB33, 0x5D4: 0xFB34, 0x5D5: 0xFB35,
               0x5D6: 0xFB36, 0x5D8: 0xFB38, 0x5D9: 0xFB39, 0x5DA: 0xFB3A, 0x5DB: 0xFB3B, 0x5DC: 0xFB3C,
               0x5DE: 0xFB3E, 0x5E0: 0xFB40, 0x5E1: 0xFB41, 0x5E3: 0xFB43, 0x5E4: 0xFB44, 0x5E6: 0xFB46,
               0x5E7: 0xFB47, 0x5E8: 0xFB48, 0x5E9: 0xFB49, 0x5EA: 0xFB4A}


def _contours(font, name):
    pen = DecomposingRecordingPen(font.getGlyphSet())
    font.getGlyphSet()[name].draw(pen)
    out, cur = [], []
    for op, args in pen.value:
        if op == "moveTo":
            cur = [args[0]]
        elif op in ("lineTo", "curveTo", "qCurveTo"):
            cur += [a for a in args if a is not None]
        elif op in ("closePath", "endPath"):
            out.append(cur)
            cur = []
    return out


def _culmus_dot(src, cp):
    """The middle of the dot in Culmus' letter-with-dagesh (its smallest contour)."""
    name = src.getBestCmap().get(WITH_DAGESH[cp])
    if not name:
        return None
    cs = [c for c in _contours(src, name) if c]
    if len(cs) < 2:
        return None
    def area(c):
        xs, ys = [p[0] for p in c], [p[1] for p in c]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))
    dot = min(cs, key=area)
    xs, ys = [p[0] for p in dot], [p[1] for p in dot]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


FRANK = Path(__file__).resolve().parents[1] / "fonts" / "FrankSofer.ttf"
_FRANK: list = []
GAP = 45          # (the least room between the dot and the letter's ink, font units)


def _box(font, name):
    gs = font.getGlyphSet()
    bp = BoundsPen(gs)
    gs[name].draw(bp)
    return bp.bounds


def _like_frank(t, base, name, dot):
    """Where Frank Sofer has this dot, as the same share of the way across and up Drugulin's letter."""
    if not _FRANK:
        _FRANK.append(TTFont(FRANK))
    F = _FRANK[0]
    if name not in F["glyf"].glyphs or not F["glyf"][name].isComposite():
        return None
    fg = F["glyf"][name]
    fb = next((c for c in fg.components if c.glyphName == base.glyphName), None)
    fd = next((c for c in fg.components if c.glyphName in ("dagesh", "dageshxazaq")), None)
    if fb is None or fd is None:
        return None
    lx0, ly0, lx1, ly1 = _box(F, fb.glyphName)
    dx0, dy0, dx1, dy1 = _box(F, fd.glyphName)
    rx = (fd.x + (dx0 + dx1) / 2 - fb.x - lx0) / (lx1 - lx0)
    ry = (fd.y + (dy0 + dy1) / 2 - fb.y - ly0) / (ly1 - ly0)
    x0, y0, x1, y1 = _box(t, base.glyphName)
    return base.x + x0 + rx * (x1 - x0), base.y + y0 + ry * (y1 - y0)


# (letters whose dot goes in the middle of their open space - Mordy: "centered in the area of airspace it is
#  supposed to be in of each letter", naming ג ד מ ט נ ס פ ף; ל kept as it was ("a surprisingly good job"), and
#  ו ז י, whose dot stands beside the stroke, and א ש)
AIRSPACE = {"bet", "gimel", "dalet", "he", "tet", "kaf", "finalkaf", "mem", "nun", "samekh", "pe", "finalpe",
            "tsadi", "qof", "resh", "tav"}
# (of those, the letters with a closed bowl, whose dot goes in the middle of it; the others - open below or
#  to the side, ד ג נ צ ק ר פ - keep the roomiest point)
BOWL = {"bet"}   # (Mordy, 2026-11-17, looking at both: "old מ ט ה ת were better" - only ב by its bowl)
# (Mordy's corrections after looking, in font units: + is right / up)
TWEAK = {"bet": (60, 0),         # "ב should be moved right a bit", then "ב right" (160 too much, 80 a bit too much; Mordy first wrote "left"
         "he": (0, 160),         #  and meant right); "ה needed to be moved up", then "ה up"
         "gimel": (80, -70),     # "ג lowered", then "ג right"
         "nun": (80, -70),       # "נ lower", then "נ right"
         "kaf": (80, 0),         # "כ right"
         "samekh": (60, 0)}      # "ס right" (80 too much, 40 not enough)
# (a dot's middle set by hand, in the letter's units, when one is needed)
FIXED: dict = {}


def _airspace(t, letter, dot):
    """The middle of the letter's open space for this dot: inside the letter's box, from the line up to its
    top, the point furthest from the ink (the centre of the largest circle that fits)."""
    import numpy as np
    import cv2
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from make_stam_sefarad import _outline_polys
    sc = 0.25
    x0, y0, x1, y1 = _box(t, letter)
    lo = max(0, y0)
    w, h = int((x1 - x0) * sc) + 1, int((y1 - lo) * sc) + 1
    ink = np.zeros((h, w), np.uint8)
    cv2.fillPoly(ink, [np.array([[(px - x0) * sc, (y1 - py) * sc] for px, py in p], np.int32)
                       for p in _outline_polys(t, letter)], 255)
    free = (ink == 0).astype(np.uint8)
    free[0, :] = free[-1, :] = free[:, 0] = free[:, -1] = 0       # (the box's edges count as walls)
    # (the letter's enclosed white - its bowl: white with ink on at least three of its four sides - and the
    #  dot at the middle of it, as the eye sees it; the roomiest point had put it against a stroke: Mordy,
    #  2026-11-17: "the dagesh in the ב and mem is not centered")
    has = ink > 0
    up = np.maximum.accumulate(has, axis=0)
    down = np.maximum.accumulate(has[::-1], axis=0)[::-1]
    left = np.maximum.accumulate(has, axis=1)
    right = np.maximum.accumulate(has[:, ::-1], axis=1)[:, ::-1]
    inside = (free > 0) & ((up.astype(int) + down + left + right) >= 3)
    n, comp, stats, _ = cv2.connectedComponentsWithStats(inside.astype(np.uint8))
    if n > 1 and letter in BOWL:
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        ys, xs = np.nonzero(comp == big)
        return x0 + xs.mean() / sc, y1 - ys.mean() / sc
    dist = cv2.distanceTransform(free, cv2.DIST_L2, 5)
    yy, xx = np.unravel_index(np.argmax(dist), dist.shape)
    return x0 + xx / sc, y1 - yy / sc


def _clear(t, letter, dot, x, y):
    """The dot moved, as little as needed, until it is GAP clear of the letter's ink (Drugulin's strokes are
    heavier than Frank's): sideways first, toward the letter's middle or away from it, then up or down."""
    import numpy as np
    import cv2
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from make_stam_sefarad import _outline_polys
    sc = 0.25

    def mask(polys, dx, dy, size=(900, 900), off=(200, 600)):
        img = np.zeros(size, np.uint8)
        cv2.fillPoly(img, [np.array([[(px + dx) * sc + off[0], off[1] - (py + dy) * sc] for px, py in p], np.int32)
                           for p in polys], 255)
        return img
    L = mask(_outline_polys(t, letter), 0, 0)
    L = cv2.dilate(L, np.ones((int(GAP * sc) * 2 + 1,) * 2, np.uint8))
    dp = _outline_polys(t, dot)
    def ok(dx, dy):
        return not np.any(np.logical_and(L > 0, mask(dp, dx, dy) > 0))
    if ok(x, y):
        return x, y
    for step in range(10, 260, 10):
        for dx, dy in ((-step, 0), (step, 0), (0, step), (0, -step)):
            if ok(x + dx, y + dy):
                return x + dx, y + dy
    return x, y


def fix(path: Path, source: Path, pad: int = 25) -> str:
    t, src = TTFont(path), TTFont(source)
    glyf, gs = t["glyf"], t.getGlyphSet()
    letter_of = {name: cp for cp, name in t.getBestCmap().items() if 0x5D0 <= cp <= 0x5EA}

    def centre(name):
        bp = BoundsPen(gs)
        gs[name].draw(bp)
        x0, y0, x1, y1 = bp.bounds
        return (x0 + x1) / 2, (y0 + y1) / 2
    moved = []
    placed = {}           # (each letter's dagesh middle, for its dagesh chazak)

    def has(name, dot):
        g = glyf[name]
        return g.isComposite() and any(c.glyphName == dot for c in g.components)
    # (the dagesh first, then the dagesh chazak in the same place: Mordy, 2026-11-17, "in hazak fix them
    #  too to be similar placement as non hazak")
    order = ([n for n in t.getGlyphOrder() if has(n, "dagesh")]
             + [n for n in t.getGlyphOrder() if has(n, "dageshxazaq") and not has(n, "dagesh")])
    for name in order:
        g = glyf[name]
        base = next((c for c in g.components if c.glyphName in letter_of), None)
        dots = [c for c in g.components if c.glyphName in ("dagesh", "dageshxazaq")]
        if base is None or not dots:
            continue
        if dots[0].glyphName == "dageshxazaq" and base.glyphName == "shin":
            continue        # (ש's chazak already sits on its dagesh as Typst prints it; moving it put it off)
        if dots[0].glyphName == "dageshxazaq" and base.glyphName in placed:
            px, py = placed[base.glyphName]
            for d in dots:
                cx, cy = centre(d.glyphName)
                nx, ny = round(base.x + px - cx), round(base.y + py - cy)
                if (nx, ny) != (d.x, d.y):
                    moved.append(f"{name} {nx - d.x:+d},{ny - d.y:+d}")
                    d.x, d.y = nx, ny
            g.recalcBounds(glyf)
            continue
        cp = letter_of[base.glyphName]
        if base.glyphName not in AIRSPACE and base.glyphName not in TWEAK:
            # (ש, א, ל, ו, ז, י: kept where they are - redone by Frank Sofer's share the ש's dot fell on its
            #  ink; Mordy, 2026-11-17, liked them as they were); its dagesh chazak goes there too
            if dots[0].glyphName == "dagesh":
                cx, cy = centre("dagesh")
                if base.glyphName in FIXED:
                    fx, fy = FIXED[base.glyphName]
                    nx, ny = round(base.x + fx - cx), round(base.y + fy - cy)
                    if (nx, ny) != (dots[0].x, dots[0].y):
                        moved.append(f"{name} {nx - dots[0].x:+d},{ny - dots[0].y:+d}")
                        dots[0].x, dots[0].y = nx, ny
                        g.recalcBounds(glyf)
                placed[base.glyphName] = (dots[0].x + cx - base.x, dots[0].y + cy - base.y)
            continue
        # (Mordy, after Culmus' own places: "the dagesh is centered on every frank letter but not in druglin" -
        #  so Frank Sofer's place, the same share of the way across and up the letter as in his)
        target = None
        if base.glyphName in AIRSPACE:
            ax, ay = _airspace(t, base.glyphName, dots[0].glyphName)
            target = (base.x + ax, base.y + ay)
        if target is None:
            target = _like_frank(t, base, name, dots[0].glyphName)
        if target is None:
            target = _culmus_dot(src, cp)
            if target is None:
                continue
            target = (target[0] + pad + base.x, target[1] + base.y)
        tx, ty = target
        dx, dy = TWEAK.get(base.glyphName, (0, 0))
        tx, ty = tx + dx, ty + dy
        for d in dots:
            cx, cy = centre(d.glyphName)
            nx, ny = round(tx - cx), round(ty - cy)
            nx, ny = _clear(t, base.glyphName, d.glyphName, nx, ny)
            if (nx, ny) != (d.x, d.y):
                moved.append(f"{name} {nx - d.x:+d},{ny - d.y:+d}")
                d.x, d.y = nx, ny
            if d.glyphName == "dagesh":
                placed[base.glyphName] = (nx + cx - base.x, ny + cy - base.y)
        g.recalcBounds(glyf)
    # the marks under ם: it had no place for them at all (Frank Sofer neither: a vowel fell to its bottom
    # left) - מ's anchors given to it, those below under its middle, as high as under מ
    import copy
    fm, m = t.getBestCmap()[0x5DD], t.getBestCmap()[0x5DE]
    below_n = 0
    fx = centre(fm)[0]
    mx = centre(m)[0]
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos" or m not in st.BaseCoverage.glyphs:
                continue
            mrec = st.BaseArray.BaseRecord[st.BaseCoverage.glyphs.index(m)]
            if fm in st.BaseCoverage.glyphs:
                rec = st.BaseArray.BaseRecord[st.BaseCoverage.glyphs.index(fm)]
            else:
                rec = copy.deepcopy(mrec)
                glyphs = st.BaseCoverage.glyphs + [fm]
                order = sorted(range(len(glyphs)), key=lambda i: t.getGlyphID(glyphs[i]))
                records = st.BaseArray.BaseRecord + [rec]
                st.BaseCoverage.glyphs = [glyphs[i] for i in order]
                st.BaseArray.BaseRecord = [records[i] for i in order]
                st.BaseArray.BaseCount = len(st.BaseArray.BaseRecord)
            for a, ma in zip(rec.BaseAnchor, mrec.BaseAnchor):
                if a is not None and ma is not None:
                    a.XCoordinate = round(ma.XCoordinate - mx + fx)     # (the same place, about ם's middle)
                    a.YCoordinate = ma.YCoordinate
                    below_n += 1
    # the dagesh chazak (U+05C9) as a separate mark - as Typst, which prints the books, sets it (its Unicode
    # tables do not know U+05C9, so the letter-with-chazak above is never chosen): a rule putting the
    # square's middle on each letter's dagesh middle, last in the "mark" feature (Mordy, 2026-11-17: "in
    # hazak fix them too to be similar placement as non hazak")
    from fontTools.otlLib import builder as otl
    from fontTools.ttLib.tables import otTables as ot
    sx, sy = centre("dageshxazaq")
    bases = {}
    for letter, (px, py) in placed.items():
        if letter == "shin":
            continue        # (ש: Typst already sets its chazak on its dagesh; this rule put it a sixth of a letter off)
        bases[letter] = {0: otl.buildAnchor(round(px), round(py))}
    gpos = t["GPOS"].table
    lk = otl.buildLookup([otl.buildMarkBasePosSubtable({"dageshxazaq": (0, otl.buildAnchor(round(sx), round(sy)))},
                                              bases, t.getReverseGlyphMap())], table="GPOS")
    gpos.LookupList.Lookup.append(lk)
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "mark":
            fr.Feature.LookupListIndex.append(len(gpos.LookupList.Lookup) - 1)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    __import__("gpos_ext").as_extensions(t)
    t.save(path)
    return f"{len(moved)} dageshes put where Culmus drew them; {below_n} anchors under final mem centred"


if __name__ == "__main__":
    pad = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    print(fix(Path(sys.argv[1]), Path(sys.argv[2]), pad))
