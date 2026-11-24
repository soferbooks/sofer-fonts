"""The dagesh and the marks under ם, ב, כ in Sofer's fonts (Antigravity, 2026-11-24, ported from its scratch
folder; Mordy's approvals of 2026-11-23 / 24).  Frank Sofer, Hadassah, Mekorot Rashi, both Sofer Stam fonts,
Vilna Classic and the new Vilna Sofer:

1. ם (finalmem, finalmem.wide): the dagesh and the dagesh chazak centred in the hollow (a MarkBasePos lookup
   appended to "mark", only for those two marks, so a vowel under ם is not disturbed); the hollow is found on
   the letter's own inner contour (2 contours), else by rasterising the letter and taking the largest enclosed
   white cavity (Mekorot Rashi's ם has 4 contours: the smallest one is a serif artefact).
2. ם gets the marks-above / marks-below anchors of mem, shifted to its centre (`םָ` fell off the left edge).
3. ב and כ: the dagesh (and the chazak) in the middle of the open bowl, measured on each letter
   (open_x0 + 0.53 of the way across at mid height; vertically the cavity's centre).
4. The dagesh chazak (U+05C9) level with the dagesh on every letter: the ".xazaq" composites and the
   standalone dageshxazaq MarkBasePos anchors.  TAAMEY D HAZARD: shindagesh.xazaq, trueshindagesh.xazaq and
   sindagesh.xazaq carry a hidden 30-degree rotation (c.transform) on the dageshxazaq component; setting only
   (x, y) would leave it rotating the dot 260 units onto ש's right arm - so the transform and its flags
   (0x0008 | 0x0040 | 0x0080) are cleared.

    .venv/Scripts/python scripts/fix_finalmem_dagesh.py <kind> <font.ttf> [...] [--out DIR] [--regular FILE]

kind: frank (regular or bold), vilna (the new Vilna Sofer), classic (Vilna Classic; --regular FILE for the
bold's kaf), hadassah, rashi, stam.  In place unless --out DIR (the file is then copied there first).  The rashi
kind uses `dehi_beside.fix(step=15)` to stay inside GPOS's 64 KB LookupList (203-239 subtables instead of
~1,000; falls back to 25).  Run after the font's other placement steps; then check_font_marks.py.
"""
from __future__ import annotations

import copy
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from fontTools.otlLib import builder as otl  # noqa: E402
from fontTools.pens.boundsPen import BoundsPen  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

import fix_lsb  # noqa: E402
import gpos_ext  # noqa: E402
from make_stam_sefarad import _outline_polys  # noqa: E402


def _glyph_center(t: TTFont, name: str) -> tuple[float, float]:
    gs = t.getGlyphSet()
    bp = BoundsPen(gs)
    gs[name].draw(bp)
    if bp.bounds is None:
        raise ValueError(f"Glyph {name!r} has empty bounds")
    x0, y0, x1, y1 = bp.bounds
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def _inner_hole_center(t: TTFont, name: str) -> tuple[int, int]:
    g = t["glyf"][name]
    if not g.isComposite() and getattr(g, "numberOfContours", 0) == 2:
        contours = []
        start = 0
        for end in g.endPtsOfContours:
            pts = g.coordinates[start:end + 1]
            xs = [x for x, _ in pts]
            ys = [y for _, y in pts]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            contours.append(((x1 - x0) * (y1 - y0), x0, y0, x1, y1))
            start = end + 1
        _, x0, y0, x1, y1 = min(contours, key=lambda c: c[0])
        return round((x0 + x1) / 2.0), round((y0 + y1) / 2.0)

    # (more than two contours - Mekorot Rashi's ם has 4, the smallest being a serif artefact: the
    #  largest enclosed white cavity of the rasterised letter)
    polys = _outline_polys(t, name)
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sc, pad = 0.5, 10
    w, h = int((x1 - x0) * sc) + 2 * pad, int((y1 - y0) * sc) + 2 * pad
    img = np.zeros((h, w), np.uint8)
    cv2.fillPoly(
        img,
        [np.array([[(px - x0) * sc + pad, (y1 - py) * sc + pad] for px, py in poly], np.int32) for poly in polys],
        255,
    )
    n, _, stats, _ = cv2.connectedComponentsWithStats((img == 0).astype(np.uint8))
    holes = []
    for i in range(1, n):
        lx, ty, cw, ch, area = stats[i]
        if lx > 0 and ty > 0 and lx + cw < w and ty + ch < h and area > 50:
            hx = round(x0 + (lx + (lx + cw - 1) - 2 * pad) / (2.0 * sc))
            hy = round(y1 - (ty + (ty + ch - 1) - 2 * pad) / (2.0 * sc))
            holes.append((area, hx, hy))
    if not holes:
        raise ValueError(f"No inner hole found for {name!r}")
    _, hx, hy = max(holes, key=lambda item: item[0])
    return hx, hy


def center_finalmem_dagesh(path: Path) -> str:
    """Append a MarkBasePos lookup to 'mark' centering dagesh/dageshxazaq in finalmem."""
    t = TTFont(path)
    glyf = t["glyf"]

    dx, dy = _glyph_center(t, "dagesh")
    sx, sy = _glyph_center(t, "dageshxazaq")
    marks = {
        "dagesh": (0, otl.buildAnchor(round(dx), round(dy))),
        "dageshxazaq": (0, otl.buildAnchor(round(sx), round(sy))),
    }

    bases: dict[str, dict[int, object]] = {}
    hole_info = []
    for gname in ("finalmem", "finalmem.wide"):
        if gname in glyf:
            hx, hy = _inner_hole_center(t, gname)
            bases[gname] = {0: otl.buildAnchor(hx, hy)}
            hole_info.append(f"{gname}@({hx},{hy})")

    if not bases:
        raise ValueError("Neither finalmem nor finalmem.wide found in font")

    subtable = otl.buildMarkBasePosSubtable(marks, bases, t.getReverseGlyphMap())
    lk = otl.buildLookup([subtable], table="GPOS")

    gpos = t["GPOS"].table
    idx = len(gpos.LookupList.Lookup)
    gpos.LookupList.Lookup.append(lk)
    gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)

    mark_features = 0
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "mark":
            fr.Feature.LookupListIndex.append(idx)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
            mark_features += 1

    if not mark_features:
        raise ValueError("No 'mark' feature found in GPOS")

    gpos_ext.as_extensions(t)
    t.save(path)
    lsb_fixed = fix_lsb.fix(path)
    return f"L{idx} ({', '.join(hole_info)}), {lsb_fixed} lsb fixed"


def sync_dagesh_xazaq_on_font(t: TTFont, only_bases: set[str] | None = None) -> str:
    """Align .xazaq composites and standalone dageshxazaq GPOS anchors to match dagesh."""
    glyf = t["glyf"]
    d_cx, d_cy = _glyph_center(t, "dagesh")
    x_cx, x_cy = _glyph_center(t, "dageshxazaq")

    dagesh_by_stem: dict[frozenset[str], tuple[str, tuple[float, float]]] = {}
    xazaq_composites: list[tuple[str, frozenset[str]]] = []

    for gn in t.getGlyphOrder():
        g = glyf[gn]
        if not g.isComposite():
            continue
        comps = g.components
        d_comps = [c for c in comps if c.glyphName == "dagesh"]
        x_comps = [c for c in comps if c.glyphName == "dageshxazaq"]
        stem = frozenset(c.glyphName for c in comps if c.glyphName not in ("dagesh", "dageshxazaq"))
        if d_comps and stem:
            base_off_x, base_off_y = 0, 0
            if len(stem) == 1:
                bc = next(c for c in comps if c.glyphName in stem)
                base_off_x, base_off_y = bc.x, bc.y
            dagesh_by_stem[stem] = (gn, (d_comps[0].x + d_cx - base_off_x, d_comps[0].y + d_cy - base_off_y))
        elif x_comps and stem:
            xazaq_composites.append((gn, stem))

    comp_updated = 0
    for xgn, stem in xazaq_composites:
        if stem not in dagesh_by_stem:
            continue
        if only_bases is not None and not (stem & only_bases):
            continue
        dgn, _ = dagesh_by_stem[stem]
        dg = glyf[dgn]
        xg = glyf[xgn]
        d_dot = next(c for c in dg.components if c.glyphName == "dagesh")
        d_by_name = {c.glyphName: (c.x, c.y) for c in dg.components if c.glyphName != "dagesh"}
        changed = False
        for c in xg.components:
            if c.glyphName == "dageshxazaq":
                nx = round(d_dot.x + d_cx - x_cx)
                ny = round(d_dot.y + d_cy - x_cy)
                # (Taamey D's shin xazaq composites carry a 30-degree rotation: cleared, see the header)
                if hasattr(c, "transform"):
                    delattr(c, "transform")
                    changed = True
                if c.flags & (0x0008 | 0x0040 | 0x0080):
                    c.flags &= ~(0x0008 | 0x0040 | 0x0080)
                    changed = True
            elif c.glyphName in d_by_name:
                nx, ny = d_by_name[c.glyphName]
            else:
                continue
            if (c.x, c.y) != (nx, ny):
                c.x, c.y = nx, ny
                changed = True
        if changed:
            xg.recalcBounds(glyf)
            comp_updated += 1

    bases: dict[str, dict[int, object]] = {}
    skip = {"finalmem", "finalmem.wide"}
    for stem, (_, (px, py)) in dagesh_by_stem.items():
        target_base = None
        if len(stem) == 1:
            b = next(iter(stem))
            if b not in skip:
                target_base = b
        elif stem == frozenset({"shin", "shindot"}):
            target_base = "trueshin"
        elif stem == frozenset({"shin", "sindot"}):
            target_base = "sin"
        if target_base and target_base in glyf:
            if only_bases is None or target_base in only_bases or bool(stem & only_bases):
                bases[target_base] = {0: otl.buildAnchor(round(px), round(py))}

    if bases:
        subtable = otl.buildMarkBasePosSubtable(
            {"dageshxazaq": (0, otl.buildAnchor(round(x_cx), round(x_cy)))},
            bases,
            t.getReverseGlyphMap(),
        )
        lk = otl.buildLookup([subtable], table="GPOS")
        gpos = t["GPOS"].table
        idx = len(gpos.LookupList.Lookup)
        gpos.LookupList.Lookup.append(lk)
        gpos.LookupList.LookupCount = len(gpos.LookupList.Lookup)
        for fr in gpos.FeatureList.FeatureRecord:
            if fr.FeatureTag == "mark":
                fr.Feature.LookupListIndex.append(idx)
                fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)

    return f"{comp_updated} xazaq composites + {len(bases)} MarkBasePos anchors synced"


def sync_dagesh_xazaq(path: Path, only_bases: set[str] | None = None) -> str:
    """File-level wrapper: sync dageshxazaq, convert extensions, save, and fix LSB."""
    t = TTFont(path)
    msg = sync_dagesh_xazaq_on_font(t, only_bases=only_bases)
    gpos_ext.as_extensions(t)
    t.save(path)
    lsb = fix_lsb.fix(path)
    return f"{msg}; {lsb} lsb fixed"


VILNA_XAZAQ_BASES = {"alef", "he", "tet", "lamed", "finalpe", "pe", "samekh", "shin", "trueshin", "sin"}
CLASSIC_XAZAQ_BASES = {"alef", "he", "shin", "trueshin", "sin", "kaf"}


# ---- ב and כ: the dagesh in the middle of the open bowl; ם: the marks of mem -----------------------

def _measure_open_bowl(t: TTFont, gn: str) -> tuple[int, int]:
    """Measure the balanced optical center (x, y) inside the open bowl of bet/kaf."""
    polys = _outline_polys(t, gn)
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sc = 0.5
    pad = 10
    w, h = int((x1 - x0) * sc) + 2 * pad, int((y1 - y0) * sc) + 2 * pad
    img = np.zeros((h, w), np.uint8)
    cv2.fillPoly(
        img,
        [np.array([[(px - x0) * sc + pad, (y1 - py) * sc + pad] for px, py in poly], np.int32) for poly in polys],
        255,
    )
    has = img > 0
    up = np.maximum.accumulate(has, axis=0)
    down = np.maximum.accumulate(has[::-1], axis=0)[::-1]
    right = np.maximum.accumulate(has[:, ::-1], axis=1)[:, ::-1]
    bowl = (~has) & up & down & right
    ys_b, _ = np.nonzero(bowl)
    mid_y_px = int(round(ys_b.mean()))
    row_xs = np.where(bowl[mid_y_px])[0]
    open_x0 = x0 + (row_xs.min() - pad) / sc
    open_x1 = x0 + (row_xs.max() - pad) / sc
    mid_x_px = int(round((row_xs.min() + row_xs.max()) / 2))
    col_ys = np.where(bowl[:, mid_x_px])[0]
    open_y1 = y1 - (col_ys.min() - pad) / sc
    open_y0 = y1 - (col_ys.max() - pad) / sc
    tx = round(open_x0 + 0.53 * (open_x1 - open_x0))
    ty = round((open_y0 + open_y1) / 2.0)
    return tx, ty


def fix_bet_kaf_dagesh(t: TTFont, bases: tuple[str, ...] = ("bet", "kaf")) -> str:
    """Recenter dagesh (and .xazaq composites) inside bet and kaf open bowls."""
    glyf = t["glyf"]
    dot_centers = {
        "dagesh": _glyph_center(t, "dagesh"),
        "dageshxazaq": _glyph_center(t, "dageshxazaq"),
    }
    summary = []
    for base_gn in bases:
        if base_gn not in glyf:
            continue
        tx, ty = _measure_open_bowl(t, base_gn)
        for gn in t.getGlyphOrder():
            g = glyf[gn]
            if not g.isComposite():
                continue
            bcomp = next((c for c in g.components if c.glyphName == base_gn), None)
            dcomps = [c for c in g.components if c.glyphName in dot_centers]
            if bcomp is None or not dcomps or len(g.components) != 2:
                continue
            for dc in dcomps:
                cx, cy = dot_centers[dc.glyphName]
                dc.x = round(bcomp.x + tx - cx)
                dc.y = round(bcomp.y + ty - cy)
            g.recalcBounds(glyf)
        summary.append(f"{base_gn}@({tx},{ty})")
    return ", ".join(summary)


def fix_finalmem_vowels(t: TTFont) -> int:
    """Ensure finalmem and finalmem.wide have centered below/above MarkBasePos anchors from mem."""
    glyf = t["glyf"]
    if "mem" not in glyf or "finalmem" not in glyf:
        return 0
    mem_mid = _glyph_center(t, "mem")[0]
    targets = []
    for gn in ("finalmem", "finalmem.wide"):
        if gn in glyf:
            targets.append((gn, _glyph_center(t, gn)[0]))

    added = 0
    order_map = {n: i for i, n in enumerate(t.getGlyphOrder())}
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos" or "mem" not in st.BaseCoverage.glyphs:
                continue
            mrec = st.BaseArray.BaseRecord[st.BaseCoverage.glyphs.index("mem")]
            for target_gn, target_mid in targets:
                if target_gn in st.BaseCoverage.glyphs:
                    continue
                rec = copy.deepcopy(mrec)
                dx = round(target_mid - mem_mid)
                for a in rec.BaseAnchor:
                    if a is not None:
                        a.XCoordinate += dx
                glyphs = st.BaseCoverage.glyphs + [target_gn]
                records = st.BaseArray.BaseRecord + [rec]
                perm = sorted(range(len(glyphs)), key=lambda i: order_map[glyphs[i]])
                st.BaseCoverage.glyphs = [glyphs[i] for i in perm]
                st.BaseArray.BaseRecord = [records[i] for i in perm]
                st.BaseArray.BaseCount = len(st.BaseArray.BaseRecord)
                added += 1
    return added


def _set_composite_dot(t: TTFont, base_gn: str, tx: int, ty: int) -> None:
    glyf = t["glyf"]
    centers = {
        "dagesh": _glyph_center(t, "dagesh"),
        "dageshxazaq": _glyph_center(t, "dageshxazaq"),
    }
    for gn in t.getGlyphOrder():
        g = glyf[gn]
        if not g.isComposite() or len(g.components) != 2:
            continue
        bc = next((c for c in g.components if c.glyphName == base_gn), None)
        dc = next((c for c in g.components if c.glyphName in centers), None)
        if bc is None or dc is None:
            continue
        cx, cy = centers[dc.glyphName]
        dc.x = round(bc.x + tx - cx)
        dc.y = round(bc.y + ty - cy)
        g.recalcBounds(glyf)


def classic_bold_kaf(bold_path: Path, regular_path: Path) -> str:
    """Vilna Classic Bold: kafdagesh was 126 units too far left (protruding into the mouth).  Put where
    Regular's is, relative to the letter's own width (Regular's dot centre + the shift of the kaf's middle)."""
    tr = TTFont(regular_path)
    rg = tr["glyf"]["kafdagesh"]
    rd = next(c for c in rg.components if c.glyphName == "dagesh")
    rcx, rcy = _glyph_center(tr, "dagesh")
    rx, ry = rd.x + rcx, rd.y + rcy
    rk0, rk1 = tr["glyf"]["kaf"].xMin, tr["glyf"]["kaf"].xMax
    tb = TTFont(bold_path)
    bk0, bk1 = tb["glyf"]["kaf"].xMin, tb["glyf"]["kaf"].xMax
    tx = round(rx + ((bk0 + bk1) / 2.0 - (rk0 + rk1) / 2.0))
    ty = round(ry)
    _set_composite_dot(tb, "kaf", tx, ty)
    tb.save(bold_path)
    return f"kafdagesh -> ({tx},{ty})"


# ---- the recipe of each font ---------------------------------------------------------------------

def set_font_family(path: Path, family: str, bold: bool) -> None:
    """Update font naming records while preserving copyright/license/vendor metadata."""
    t = TTFont(path)
    subfamily = "Bold" if bold else "Regular"
    ps_name = f"{family.replace(' ', '')}-Bold" if bold else family.replace(" ", "")
    full_name = f"{family} Bold" if bold else family
    unique_id = f"FontForge 2.0 : {family} : 24-11-2026{' Bold' if bold else ''}"

    mapping = {
        1: family,
        2: subfamily,
        3: unique_id,
        4: full_name,
        6: ps_name,
        16: family,
        17: subfamily,
    }
    for r in t["name"].names:
        if r.nameID in mapping:
            r.string = mapping[r.nameID]

    t.save(path)
    fix_lsb.fix(path)


def apply(kind: str, path: Path, regular: Path | None = None) -> list[str]:
    """The 2026-11-24 fixes for one font file, in place.  Returns what each step did."""
    import dehi_beside
    import qof_vowel
    import under_body
    out: list[str] = []
    if kind == "frank":
        t = TTFont(path)
        bk = fix_bet_kaf_dagesh(t)
        fm = fix_finalmem_vowels(t)
        t.save(path)
        out.append(f"bet/kaf=[{bk}] finalmem anchors=+{fm}")
        out.append(center_finalmem_dagesh(path))
        out.append(sync_dagesh_xazaq(path))
    elif kind == "vilna":
        out.append(center_finalmem_dagesh(path))
        out.append(sync_dagesh_xazaq(path, only_bases=VILNA_XAZAQ_BASES))
    elif kind == "classic":
        if "Bold" in path.name and regular is not None:
            out.append(classic_bold_kaf(path, regular))
        out.append(center_finalmem_dagesh(path))
        out.append(sync_dagesh_xazaq(path, only_bases=CLASSIC_XAZAQ_BASES))
        out.append(under_body.fix(path, lamed=False, left=True))
    elif kind == "hadassah":
        t = TTFont(path)
        bk = fix_bet_kaf_dagesh(t, bases=("bet",))
        fm = fix_finalmem_vowels(t)
        t.save(path)
        out.append(f"bet=[{bk}] finalmem anchors=+{fm}")
        out.append(center_finalmem_dagesh(path))
        out.append(sync_dagesh_xazaq(path))
        out.append(dehi_beside.fix(path))
        out.append(under_body.fix(path, lamed=False, left=True))
    elif kind == "rashi":
        t = TTFont(path)
        fm = fix_finalmem_vowels(t)
        t.save(path)
        out.append(f"finalmem anchors=+{fm}")
        out.append(center_finalmem_dagesh(path))
        out.append(sync_dagesh_xazaq(path))
        # (Mekorot Rashi already has 7,913 GPOS subtables: the shifts in steps of 15 keep the
        #  LookupList under 64 KB - OTLOffsetOverflowError otherwise; 25 as the fallback)
        from fontTools.ttLib.tables.otBase import OTLOffsetOverflowError
        snap = path.read_bytes()
        try:
            out.append(dehi_beside.fix(path, step=15))
        except OTLOffsetOverflowError:
            path.write_bytes(snap)
            out.append(dehi_beside.fix(path, step=25))
    elif kind == "stam":
        t = TTFont(path)
        fm = fix_finalmem_vowels(t)
        t.save(path)
        out.append(f"finalmem anchors=+{fm}")
        out.append(center_finalmem_dagesh(path))
        out.append(sync_dagesh_xazaq(path))
        out.append(qof_vowel.fix(path))
    else:
        raise SystemExit(f"unknown kind {kind!r}")
    out.append(f"bearings: {fix_lsb.fix(path)} fixed")
    return out


KINDS = ("frank", "vilna", "classic", "hadassah", "rashi", "stam")


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out_dir = regular = None
    args = list(argv)
    if "--out" in args:
        i = args.index("--out")
        out_dir = Path(args[i + 1])
        del args[i:i + 2]
    if "--regular" in args:
        i = args.index("--regular")
        regular = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) < 2 or args[0] not in KINDS:
        raise SystemExit(__doc__)
    kind = args[0]
    for f in args[1:]:
        p = Path(f)
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, out_dir / p.name)
            p = out_dir / p.name
        for line in apply(kind, p, regular):
            print(f"  {p.name}: {line}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
