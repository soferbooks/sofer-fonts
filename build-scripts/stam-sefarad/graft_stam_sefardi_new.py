from __future__ import annotations

import math
import os
import sys
import types
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

import cv2
import numpy as np
from PIL import Image, ImageDraw

SCRATCH = Path(__file__).resolve().parent / "scratch"
SOFER_SCRIPTS = Path(__file__).resolve().parents[1]
OUTLINES_TTF = SCRATCH / "_stam_sefardi_new_outlines.ttf"
FRANK_PATH = SCRATCH / "release" / "FrankSofer.ttf"
OUT_PATH = SCRATCH / "release" / "SoferStamSefaradHayom.ttf"

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(SOFER_SCRIPTS))
import make_stam_sefarad as ms  # noqa: E402
from fontTools.pens.basePen import BasePen  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402
import fix_lsb  # noqa: E402
import check_font_marks  # noqa: E402

# Inject fast no-op stubs ONLY for the slow 204k-word full-corpus collision/meteg scans
# per visual-first workflow; full corpus passes run only after Mordy approves visual look.
ms.fix_by_shaping = lambda path, words: "skipped (visual pass)"
dummy_cm = types.ModuleType("clear_meteg")
dummy_cm.siddur_words = lambda: set()
dummy_cm.tanach_words = lambda: set()
dummy_cm.clear = lambda path, words: "skipped (visual pass)"
sys.modules["clear_meteg"] = dummy_cm

ms.FRANK = FRANK_PATH
ms.OUT = OUT_PATH
ms.FAMILY = "Sofer Stam Sefarad Hayom"
ms.SOURCE = "Mishnas Sofrim - Meoros HaMizrach (Minhag HaSofrim HaYom)"


def _glyph_polys(T: TTFont, name: str, step: int = 6) -> list[list[tuple[float, float]]]:
    class Polys(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.polys, self.cur = [], (0.0, 0.0)

        def _moveTo(self, a):
            self.polys.append([a])
            self.cur = a

        def _lineTo(self, a):
            self.polys[-1].append(a)
            self.cur = a

        def _qCurveToOne(self, a, b):
            x0, y0 = self.cur
            for i in range(1, step + 1):
                s = i / step
                m = 1.0 - s
                self.polys[-1].append((m * m * x0 + 2 * m * s * a[0] + s * s * b[0],
                                       m * m * y0 + 2 * m * s * a[1] + s * s * b[1]))
            self.cur = b

        def _curveToOne(self, a, b, c):
            x0, y0 = self.cur
            for i in range(1, step + 1):
                s = i / step
                m = 1.0 - s
                self.polys[-1].append((m ** 3 * x0 + 3 * m * m * s * a[0] + 3 * m * s * s * b[0] + s ** 3 * c[0],
                                       m ** 3 * y0 + 3 * m * m * s * a[1] + 3 * m * s * s * b[1] + s ** 3 * c[1]))
            self.cur = c

    gs = T.getGlyphSet()
    pen = Polys(gs)
    gs[name].draw(pen)
    return [p for p in pen.polys if len(p) >= 3]


def _dist_field(T: TTFont, base_name: str, scale: int = 3):
    """Build exact Euclidean distance-to-ink map (in font units) around base_name."""
    polys = _glyph_polys(T, base_name)
    if not polys:
        return None
    xs = [p[0] for c in polys for p in c]
    ys = [p[1] for c in polys for p in c]
    bx0, by0, bx1, by1 = min(xs), min(ys), max(xs), max(ys)
    x0 = int(bx0) - 240
    x1 = int(bx1) + 140
    y0 = min(0, int(by0)) - 100
    y1 = max(1250, int(by1)) + 100
    w_px = (x1 - x0) // scale + 1
    h_px = (y1 - y0) // scale + 1
    img = Image.new("L", (w_px, h_px), 0)
    from PIL import ImageChops
    for c in polys:
        one = Image.new("L", (w_px, h_px), 0)
        ImageDraw.Draw(one).polygon([((x - x0) / scale, (y1 - y) / scale) for x, y in c], fill=255)
        img = ImageChops.lighter(img, one) if False else Image.fromarray(np.bitwise_xor(np.array(img), np.array(one)))
    ink = (np.array(img) > 128).astype(np.uint8)
    dist_map = cv2.distanceTransform(1 - ink, cv2.DIST_L2, 5) * float(scale)
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "scale": scale, "ink": ink, "dist": dist_map, "bx": (bx0, by0, bx1, by1)}


def _dist_at(df, fx: float, fy: float) -> float:
    scale = df["scale"]
    px = int(round((fx - df["x0"]) / scale))
    py = int(round((df["y1"] - fy) / scale))
    h, w = df["dist"].shape
    if not (0 <= px < w and 0 <= py < h):
        return 0.0
    return float(df["dist"][py, px])


def _best_in_box(df, rx0: float, ry0: float, rx1: float, ry1: float, ideal: tuple[float, float], pull: float = 0.12, cap: float = 142.0) -> tuple[float, float, float]:
    """Find (x, y, clearance) inside [rx0..rx1, ry0..ry1] maximizing distance from ink cleanly."""
    scale = df["scale"]
    h, w = df["dist"].shape
    px0 = max(0, int(round((rx0 - df["x0"]) / scale)))
    px1 = min(w - 1, int(round((rx1 - df["x0"]) / scale)))
    py0 = max(0, int(round((df["y1"] - ry1) / scale)))
    py1 = min(h - 1, int(round((df["y1"] - ry0) / scale)))
    if px1 < px0 or py1 < py0:
        return ideal[0], ideal[1], 0.0
    sub = df["dist"][py0:py1 + 1, px0:px1 + 1]
    yy, xx = np.mgrid[py0:py1 + 1, px0:px1 + 1]
    fx = df["x0"] + xx * scale
    fy = df["y1"] - yy * scale
    score = np.minimum(sub, cap) - pull * np.hypot(fx - ideal[0], fy - ideal[1])
    best_idx = np.unravel_index(int(np.argmax(score)), score.shape)
    bx = float(fx[best_idx])
    by = float(fy[best_idx])
    bdist = float(sub[best_idx])
    return bx, by, bdist


def _pick_dagesh_spot(T: TTFont, df, base_name: str, cur_cx: float, cur_cy: float) -> tuple[float, float, float]:
    root = base_name.split(".")[0]
    bx0, by0, bx1, by1 = df["bx"]
    bw = bx1 - bx0
    BODY_H = 1115.0

    # Special closed-hole letters: finalmem & samekh -> exact center of contour hole!
    if root in ("finalmem", "samekh"):
        g = T["glyf"][base_name]
        if not g.isComposite() and g.numberOfContours >= 2:
            pts = g.coordinates[g.endPtsOfContours[0] + 1 : g.endPtsOfContours[1] + 1]
            cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2.0
            cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2.0
            return cx, cy, _dist_at(df, cx, cy)

    # Letters that require canonical placement in specific open bay/valley
    if root in ("shin", "trueshin", "sin"):
        # Right open valley between middle branch and right branch (classic dagesh position)
        return _best_in_box(df, bx0 + 0.56 * bw, 350.0, bx0 + 0.88 * bw, 800.0, (bx0 + 0.72 * bw, 560.0), pull=0.08)
    if root == "tsadi":
        # Wide open V-valley between left head and right diagonal arm
        return _best_in_box(df, bx0 + 0.24 * bw, 420.0, bx0 + 0.66 * bw, 830.0, (bx0 + 0.44 * bw, 610.0), pull=0.10)
    if root == "ayin":
        # Open V-valley between left head and right diagonal arm
        return _best_in_box(df, bx0 + 0.30 * bw, 400.0, bx0 + 0.72 * bw, 850.0, (bx0 + 0.50 * bw, 600.0), pull=0.10)
    if root == "xet":
        # Central open corridor strictly between left and right legs
        return _best_in_box(df, bx0 + 0.34 * bw, 240.0, bx0 + 0.66 * bw, 700.0, (bx0 + 0.50 * bw, 500.0), pull=0.10)
    if root in ("dalet", "resh", "finalkaf"):
        # Open pocket under the roof & left of right leg
        return _best_in_box(df, bx0 + 0.22 * bw, 250.0, bx0 + 0.72 * bw, 740.0, (bx0 + 0.44 * bw, 520.0), pull=0.10)
    if root == "bet":
        # Centered vertically in [360..755] (y=558) and nestled at 0.53*bw like Old Sefard/Ashkenaz
        tx, ty = bx0 + 0.53 * bw, 558.0
        return tx, ty, _dist_at(df, tx, ty)
    if root == "kaf":
        # Centered vertically in [360..755] (y=558) and balanced at 0.495*bw (~583u, ~237u clear of inner U-bend)
        tx, ty = bx0 + 0.495 * bw, 558.0
        return tx, ty, _dist_at(df, tx, ty)
    if root == "pe":
        return _best_in_box(df, bx0 + 0.38 * bw, 220.0, bx0 + 0.72 * bw, 720.0, (bx0 + 0.54 * bw, 475.0), pull=0.12)
    if root in ("mem", "he", "tav", "tet"):
        return _best_in_box(df, bx0 + 0.22 * bw, 220.0, bx0 + 0.76 * bw, 780.0, (cur_cx, 545.0), pull=0.12)
    if root == "finalpe":
        return _best_in_box(df, bx0 + 0.22 * bw, 320.0, bx0 + 0.72 * bw, 840.0, (cur_cx, 560.0), pull=0.12)
    if root == "qof":
        return _best_in_box(df, bx0 + 0.30 * bw, 240.0, bx0 + 0.72 * bw, 740.0, (bx0 + 0.52 * bw, 500.0), pull=0.10)
    if root == "lamed":
        return _best_in_box(df, bx0 + 0.28 * bw, 260.0, bx0 + 0.74 * bw, 720.0, (bx0 + 0.50 * bw, 490.0), pull=0.10)
    if root == "nun":
        # Centered vertically in [360..755] (y=558) and tucked inward at 0.35*bw like Old Sefard/Ashkenaz (0.35)
        return _best_in_box(df, bx0 + 0.26 * bw, 520.0, bx0 + 0.44 * bw, 590.0, (bx0 + 0.35 * bw, 558.0), pull=0.35, cap=100.0)
    if root == "gimel":
        # Centered vertically in [360..755] (y=558) and tucked inward at 0.33*bw like Old Sefard/Ashkenaz (0.31)
        return _best_in_box(df, bx0 + 0.24 * bw, 520.0, bx0 + 0.42 * bw, 590.0, (bx0 + 0.33 * bw, 558.0), pull=0.35, cap=105.0)
    if root == "vav":
        # Shuruq cleanly under left head overhang (0.24*bw, y=535) matching Old Sefard/Ashkenaz (0.23) without protruding left of xMin
        return _best_in_box(df, bx0 + 0.18 * bw, 505.0, bx0 + 0.32 * bw, 565.0, (bx0 + 0.24 * bw, 535.0), pull=0.40, cap=90.0)
    if root == "zayin":
        # Left open pocket under zayin head overhang, clear left of narrow stem
        return _best_in_box(df, bx0 - 130.0, 440.0, bx0 + 0.35 * bw, 680.0, (bx0 + 0.08 * bw, 540.0), pull=0.12)
    if root == "yod":
        # Open arch below-left of yod body
        return _best_in_box(df, bx0 - 100.0, 440.0, bx0 + 0.55 * bw, 660.0, (bx0 + 0.10 * bw, 540.0), pull=0.12)
    if root == "alef":
        # Check open upper-right pocket and lower-left pocket of alef, pick cleanest open spot!
        c1 = _best_in_box(df, bx0 + 0.48 * bw, 550.0, bx0 + 0.86 * bw, 860.0, (bx0 + 0.66 * bw, 680.0), pull=0.10)
        c2 = _best_in_box(df, bx0 + 0.15 * bw, 200.0, bx0 + 0.52 * bw, 520.0, (bx0 + 0.32 * bw, 360.0), pull=0.10)
        # Wait: check classic alef mapiq spot just left of middle diagonal if clear enough, else widest
        return c2 if c2[2] >= 106.0 else (c1 if c1[2] > c2[2] else c2)

    if _dist_at(df, cur_cx, cur_cy) >= 112.0:
        return cur_cx, cur_cy, _dist_at(df, cur_cx, cur_cy)
    return _best_in_box(df, bx0 - 20.0, 220.0, bx1 + 20.0, 820.0, (cur_cx, cur_cy), pull=0.12)


def fix_all_dagesh_open_spots(T: TTFont) -> list[str]:
    """Place EVERY dagesh (composites AND GPOS MarkBasePos anchors) cleanly into open white space."""
    G = T["glyf"]
    hmtx = T["hmtx"]
    if "dagesh" not in G.glyphs:
        return []
    G["dagesh"].recalcBounds(G)
    dcx = (G["dagesh"].xMin + G["dagesh"].xMax) / 2.0
    dcy = (G["dagesh"].yMin + G["dagesh"].yMax) / 2.0
    notes = []
    dfs: dict[str, dict | None] = {}

    def get_df(bname: str):
        if bname not in dfs:
            dfs[bname] = _dist_field(T, bname)
        return dfs[bname]

    # 1. Fix all non-xazaq composite glyphs containing dagesh
    for name in T.getGlyphOrder():
        if name.endswith(".xazaq"):
            continue
        g = G[name]
        if not g.isComposite():
            continue
        dc = next((c for c in g.components if c.glyphName == "dagesh"), None)
        base_c = next((c for c in g.components if c.glyphName not in ("dagesh", "dageshxazaq", "shindot", "sindot", "telishagedola", "gereshacc.pre")), None)
        if dc is None or base_c is None:
            continue
        df = get_df(base_c.glyphName)
        if df is None:
            continue
        cur_cx = dc.x - base_c.x + dcx
        cur_cy = dc.y - base_c.y + dcy
        # Reset any prior left-overhang shift on base_c so re-running is 100% idempotent
        if base_c.x != 0 and base_c.glyphName in hmtx.metrics:
            base_c.x = 0
            hmtx[name] = (hmtx[base_c.glyphName][0], hmtx[name][1])
        tx, ty, clr = _pick_dagesh_spot(T, df, base_c.glyphName, cur_cx, cur_cy)
        nx = round(base_c.x + tx - dcx)
        ny = round(base_c.y + ty - dcy)
        if abs(nx - dc.x) > 2 or abs(ny - dc.y) > 2:
            dc.x, dc.y = nx, ny
            notes.append(f"comp {name}: dagesh moved to ({nx},{ny}) clear={clr:.0f}")
        g.recalcBounds(G)
        hmtx[name] = (hmtx[name][0], g.xMin)
        # Ensure comfortable LSB >= 45 if left-hanging shuruq/zayin/yod dagesh shifted left of base xMin
        if g.xMin < 45:
            shift = 50 - g.xMin
            for c in g.components:
                c.x += shift
            g.recalcBounds(G)
            adv, _ = hmtx[name]
            hmtx[name] = (adv + shift, g.xMin)

    # 2. Split 'dagesh' & 'dageshxazaq' into their OWN dedicated MarkClass inside MarkBasePos
    # so vowels below (qamats, patax, segol, sheva, etc.) NEVER move with dagesh!
    from fontTools.ttLib.tables import otTables as ot
    for lk in T["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            d_marks = [dn for dn in ("dagesh", "dageshxazaq") if dn in st.MarkCoverage.glyphs]
            if not d_marks:
                continue
            old_classes = {
                dn: st.MarkArray.MarkRecord[st.MarkCoverage.glyphs.index(dn)].Class
                for dn in d_marks
            }
            ref_dn = "dagesh" if "dagesh" in old_classes else d_marks[0]
            ref_cls = old_classes[ref_dn]
            ma = st.MarkArray.MarkRecord[st.MarkCoverage.glyphs.index(ref_dn)].MarkAnchor

            # Check if this MarkClass is shared with non-dagesh marks (like vowels!)
            others_in_cls = [
                mn for mn, rec in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord)
                if rec.Class == ref_cls and mn not in ("dagesh", "dageshxazaq")
            ]
            if others_in_cls:
                new_cls = st.ClassCount
                st.ClassCount += 1
                for rec in st.BaseArray.BaseRecord:
                    orig_a = rec.BaseAnchor[ref_cls]
                    if orig_a is not None:
                        a_copy = ot.Anchor()
                        a_copy.Format = 1
                        a_copy.XCoordinate = orig_a.XCoordinate
                        a_copy.YCoordinate = orig_a.YCoordinate
                    else:
                        a_copy = None
                    rec.BaseAnchor.append(a_copy)
                for dn in d_marks:
                    idx = st.MarkCoverage.glyphs.index(dn)
                    st.MarkArray.MarkRecord[idx].Class = new_cls
                target_cls = new_cls
            else:
                target_cls = ref_cls

            for bname, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                a = rec.BaseAnchor[target_cls]
                if a is None:
                    continue
                root = bname.split(".")[0]
                if root not in ("alef","bet","gimel","dalet","he","vav","zayin","xet","tet","yod",
                                "finalkaf","kaf","lamed","finalmem","mem","finalnun","nun","samekh",
                                "ayin","finalpe","pe","finaltsadi","tsadi","qof","resh","shin",
                                "trueshin","sin","tav"):
                    continue
                df = get_df(bname)
                if df is None:
                    continue
                cur_cx = a.XCoordinate - ma.XCoordinate + dcx
                cur_cy = a.YCoordinate - ma.YCoordinate + dcy
                tx, ty, clr = _pick_dagesh_spot(T, df, bname, cur_cx, cur_cy)
                nax = round(tx - dcx + ma.XCoordinate)
                nay = round(ty - dcy + ma.YCoordinate)
                if abs(nax - a.XCoordinate) > 4 or abs(nay - a.YCoordinate) > 4:
                    a.XCoordinate, a.YCoordinate = nax, nay
                    if a.Format != 1:
                        a.Format = 1
                    notes.append(f"gpos {bname}: isolated dagesh anchor -> ({nax},{nay}) clear={clr:.0f}")
    return notes


def clean_dagesh_xazaq_parity(T: TTFont) -> list[str]:
    """Strip any hidden 30° rotation transform from shin/sin .xazaq composites and align dageshxazaq
    centers cleanly with their non-xazaq dagesh twins."""
    G = T["glyf"]
    hmtx = T["hmtx"]
    notes = []
    if "dagesh" not in G.glyphs or "dageshxazaq" not in G.glyphs:
        return notes
    G["dagesh"].recalcBounds(G)
    G["dageshxazaq"].recalcBounds(G)
    dx_c = (G["dagesh"].xMin + G["dagesh"].xMax) / 2.0
    dy_c = (G["dagesh"].yMin + G["dagesh"].yMax) / 2.0
    xx_c = (G["dageshxazaq"].xMin + G["dageshxazaq"].xMax) / 2.0
    xy_c = (G["dageshxazaq"].yMin + G["dageshxazaq"].yMax) / 2.0

    for name in T.getGlyphOrder():
        if not name.endswith(".xazaq"):
            continue
        g = G[name]
        if not g.isComposite():
            continue
        twin_map = {"vavdagesh.xazaq": "vavdou"}
        twin_name = twin_map.get(name, name[:-6])
        twin = G[twin_name] if twin_name in G.glyphs and G[twin_name].isComposite() else None
        for c in g.components:
            if hasattr(c, "transform"):
                delattr(c, "transform")
            c.flags &= ~(0x0008 | 0x0040 | 0x0080)
        if twin is not None:
            td = next((c for c in twin.components if c.glyphName == "dagesh"), None)
            tb = next((c for c in twin.components if c.glyphName not in ("dagesh", "shindot", "sindot")), None)
            xd = next((c for c in g.components if c.glyphName == "dageshxazaq"), None)
            xb = next((c for c in g.components if c.glyphName not in ("dageshxazaq", "shindot", "sindot")), None)
            if td is not None and xd is not None:
                # Copy exact relative center offset (td - tb) onto xb, and mirror advance if twin padded
                off_x = (td.x - (tb.x if tb else 0)) + dx_c
                off_y = (td.y - (tb.y if tb else 0)) + dy_c
                if tb is not None and xb is not None:
                    xb.x, xb.y = tb.x, tb.y
                xd.x = round((xb.x if xb else 0) + off_x - xx_c)
                xd.y = round((xb.y if xb else 0) + off_y - xy_c)
                # Keep shindot/sindot synced too if present
                for dn in ("shindot", "sindot"):
                    td_s = next((c for c in twin.components if c.glyphName == dn), None)
                    xd_s = next((c for c in g.components if c.glyphName == dn), None)
                    if td_s is not None and xd_s is not None:
                        xd_s.x, xd_s.y = td_s.x, td_s.y
                hmtx[name] = hmtx[twin_name]
                notes.append(f"{name}: synced to {twin_name} dageshxazaq=({xd.x},{xd.y})")
        g.recalcBounds(G)
    return notes


def main():
    print("Grafting FrankSofer nikud & ta'amim onto new Sefardi Stam outlines...")
    ms.main(str(OUTLINES_TTF))

    T = TTFont(OUT_PATH)
    n1 = fix_all_dagesh_open_spots(T)
    n2 = clean_dagesh_xazaq_parity(T)
    for rec in T["name"].names:
        if rec.nameID == 0:
            rec.string = (
                "Sofer Stam Sefarad Hayom: Hebrew Sefardi Stam outlines traced from Mishnas Sofrim "
                "(Me'oros HaMizrach - Minhag HaSofrim HaYom / HaKtiva HaSefardit), combined with "
                "Frank Sofer nikud, ta'amim, meteg, shva na, and dagesh chazak marks."
            )
    T.save(OUT_PATH)
    lsb_cnt = fix_lsb.fix(OUT_PATH)
    probs = check_font_marks.check_font(OUT_PATH)
    print(f"\nDagesh open-spot fixes: {len(n1)}")
    for line in n1:
        print(" ", line)
    print(f"Xazaq parity synced: {len(n2)}, LSBs fixed: {lsb_cnt}")
    print(f"check_font_marks: {'OK (0 issues)' if not probs else str(len(probs)) + ' issue(s)'}")
    for p in probs[:10]:
        print(" ", p)
    print("Final font saved at:", OUT_PATH)


if __name__ == "__main__":
    main()
