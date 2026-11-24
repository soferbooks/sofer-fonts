"""The new Vilna Sofer - the printed-sefer look (Antigravity, 2026-11-23 / 24, ported from its scratch folder;
Mordy, 2026-11-24: the standard main text of every book from today).  Regular and Bold.

Built from the OLD Vilna Sofer, now called Vilna Classic (fonts/VilnaClassic.ttf: Culmus' Drugulin CLM letters
with Frank Sofer's marks, GPL-2 with the font exception) and Frank Sofer's cleaner curves, tuned to match
Mordy's four photos of a printed sefer: wider, squarer letters, snug book spacing, flat rooflines level at
y ~ 1018-1021, and Vilna's own unvowelled ע kept (ccmp + ayin.drugulin, scripts/vilna_old_ayin.py).

    1. snug Vilna base: Vilna Classic's letters scaled (VILNA_PARAMS) with side bearings pulled in to
       `ratio` of their size between sb_min and sb_max, anchors and composites carried along; GPOS trimmed to
       its first 1217 lookups (the rest - the collision rules of the old letter shapes - no longer fit);
    2. snug Frank base: Frank Sofer + the original Drugulin ע (vilna_old_ayin), scaled with FRANK_PARAMS
       (and the ע with the Vilna parameters), GPOS trimmed to its first 806 lookups;
    3. Vilna's pe, finalpe, samekh, lamed, lamed.wide, tet replaced by Frank's (OPTION_C_FRANK_LETTERS),
       marks re-anchored to the donor's own;
    4. the Bold: scripts/make_bold.py --strength 0.020 (STRENGTH_Y 0.014) from the regular;
    5. for each weight: dehi_beside, qof_vowel, under_body (ד: --dalet-only, --left-align), vav_two_marks,
       the collision fixer over every word of Tanach and the siddurim (twice, with clear_meteg between),
       the ם dagesh / dagesh chazak centred in its hollow, the dagesh chazak level with the dagesh on
       every letter (fix_finalmem_dagesh.py), the bearings (fix_lsb.py); the family name "Vilna Sofer".

    .venv/Scripts/python scripts/make_vilna_sofer.py [--out DIR] [--classic FILE] [--frank FILE]
                                                     [--drugulin FILE] [--work DIR] [--quick]

--out: where VilnaSofer.ttf and VilnaSofer-Bold.ttf are written (default fonts/ - pass another folder to
leave the shipped files alone).  --classic / --frank: the two inputs (default fonts/VilnaClassic.ttf,
fonts/FrankSofer.ttf).  --drugulin: Culmus' original DrugulinCLM.ttf (default
SoferShared/archive/font-sources/DrugulinCLM.ttf).  --quick: skip vav_two_marks and the collision
fixer / clear_meteg (each takes ~15-20 minutes a weight; they need the library in data/) - for testing only.
The full build needs the library; check afterwards with check_font_marks.py, check_meteg.py and
tests/test_font_marks.py.
"""
from __future__ import annotations

import copy
import math
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
FONTS = REPO / "fonts"
DRUGULIN_SRC = Path(r"C:\Users\morde\SoferShared\archive\font-sources\DrugulinCLM.ttf")

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fontTools.pens.boundsPen import BoundsPen  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402
from fontTools.ttLib.tables.ttProgram import Program  # noqa: E402

import dehi_beside  # noqa: E402
import fix_finalmem_dagesh as ffd  # noqa: E402
import fix_lsb  # noqa: E402
import make_bold  # noqa: E402
import qof_vowel  # noqa: E402
import under_body  # noqa: E402
import vilna_old_ayin  # noqa: E402

CORE_FRANK_LOOKUPS = 806
CORE_VILNA_LOOKUPS = 1217

# Wider, square-ish proportions + aligned flat roofs (y ~ 1018)
VILNA_PARAMS = dict(scale_x=1.11, scale_y=0.982, sx=12.0, sy=18.0, ratio=0.78, sb_min=54, sb_max=74)
FRANK_PARAMS = dict(scale_x=1.09, scale_y=0.913, sx=0.0, sy=56.0, ratio=0.62, sb_min=56, sb_max=76)
BOLD_STRENGTH = 0.020

OPTION_C_FRANK_LETTERS = [
    "pe", "finalpe", "samekh", "lamed", "lamed.wide", "tet",
]


# ---- glyph transforms (Antigravity's build_round3.py) -------------------------------------------

def hebrew_letter_glyphs(t: TTFont) -> list[str]:
    cmap = t.getBestCmap()
    base_names = {cmap[c] for c in range(0x05D0, 0x05EB) if c in cmap}
    out = []
    for n in t.getGlyphOrder():
        if any(n == b or n.startswith(b + ".") or n.startswith(b + "_") for b in base_names):
            g = t["glyf"][n]
            if not g.isComposite() or n == "alef.con":
                out.append(n)
    return out


def embolden_clamped(coords: list[tuple[int, int]], ends: list[int], sx: float, sy: float) -> list[tuple[float, float]]:
    out = [(float(x), float(y)) for x, y in coords]
    start = 0
    for end in ends:
        pts = out[start:end + 1]
        n = len(pts)
        for i in range(n):
            p = pts[i]
            j = (i - 1) % n
            while j != i and pts[j] == p:
                j = (j - 1) % n
            k = (i + 1) % n
            while k != i and pts[k] == p:
                k = (k + 1) % n
            ax, ay = p[0] - pts[j][0], p[1] - pts[j][1]
            bx, by = pts[k][0] - p[0], pts[k][1] - p[1]
            la, lb = math.hypot(ax, ay), math.hypot(bx, by)
            if not la or not lb:
                continue
            ax, ay, bx, by = ax / la, ay / la, bx / lb, by / lb
            nx, ny = -(ay + by), ax + bx
            d = ax * bx + ay * by
            if d < -0.92:
                continue
            f = min(1.0 / (1.0 + d), 2.0)
            out[start + i] = (p[0] + nx * f * sx / 2.0, p[1] + ny * f * sy / 2.0)
        start = end + 1
    return out


def transform_simple_glyph(
    t: TTFont, name: str, scale_x: float, scale_y: float, sx: float, sy: float, pad_l: int, pad_r: int
) -> None:
    glyf, hmtx = t["glyf"], t["hmtx"]
    g = glyf[name]
    if g.isComposite() or not getattr(g, "numberOfContours", 0):
        return
    scaled = [(x * scale_x, y * scale_y) for x, y in g.coordinates]
    emb = embolden_clamped(scaled, list(g.endPtsOfContours), sx, sy)
    dx, dy = sx / 2.0 + pad_l, sy / 2.0
    g.coordinates[:] = [(round(x + dx), round(y + dy)) for x, y in emb]
    g.program = Program()
    g.program.fromBytecode(b"")
    g.recalcBounds(glyf)
    old_adv, _ = hmtx[name]
    hmtx[name] = (round(old_adv * scale_x + sx) + pad_l + pad_r, g.xMin)


def _glyph_mid_y(t: TTFont, name: str) -> float:
    gs = t.getGlyphSet()
    bp = BoundsPen(gs)
    gs[name].draw(bp)
    if bp.bounds is None:
        return 0.0
    return (bp.bounds[1] + bp.bounds[3]) / 2.0


def _transform_anchor_xy(
    ax: int, ay: int, scale_x: float, scale_y: float, sx: float, sy: float, pad_l: int,
    is_above_zero_base: bool = False
) -> tuple[int, int]:
    nx = round(ax * scale_x + sx / 2.0 + pad_l)
    if is_above_zero_base:
        ny = round(ay + 1126.0 * (scale_y - 1.0) + sy)
    elif ay > 900:
        ny = round(ay * scale_y + sy)
    elif ay > 200:
        ny = round(ay * scale_y + sy / 2.0)
    elif ay < -100:
        ny = round(ay * scale_y)
    else:
        ny = ay
    return nx, ny


def _subtable_is_above_zero_base(t: TTFont, st) -> bool:
    glyf = t["glyf"]
    ys = []
    for gname, rec in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord):
        if rec.MarkAnchor and rec.MarkAnchor.YCoordinate == 0 and gname in glyf:
            g = glyf[gname]
            if not g.isComposite() and getattr(g, "numberOfContours", 0):
                g.recalcBounds(glyf)
                ys.append(g.yMin)
    return bool(ys) and sum(y > 900 for y in ys) > len(ys) / 2


def transform_font(t: TTFont, params_by_glyph: dict[str, tuple[float, float, float, float, int, int]]) -> None:
    glyf, hmtx = t["glyf"], t["hmtx"]

    mark_mid_y = {}
    for n in t.getGlyphOrder():
        if n not in params_by_glyph:
            mark_mid_y[n] = _glyph_mid_y(t, n)

    for name, (scale_x, scale_y, sx, sy, pad_l, pad_r) in params_by_glyph.items():
        if name in glyf and not glyf[name].isComposite():
            transform_simple_glyph(t, name, scale_x, scale_y, sx, sy, pad_l, pad_r)

    anchor_params = dict(params_by_glyph)
    for cname in t.getGlyphOrder():
        g = glyf[cname]
        if g.isComposite():
            base_comps = [c for c in g.components if c.glyphName in params_by_glyph]
            if base_comps:
                anchor_params[cname] = params_by_glyph[base_comps[0].glyphName]

    if "GPOS" in t:
        for lk in t["GPOS"].table.LookupList.Lookup:
            for st in lk.SubTable:
                st = getattr(st, "ExtSubTable", st)
                kind = type(st).__name__
                if kind == "MarkBasePos":
                    above_zero = _subtable_is_above_zero_base(t, st)
                    for bname, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                        if bname not in anchor_params:
                            continue
                        scale_x, scale_y, sx, sy, pad_l, _ = anchor_params[bname]
                        for ci, a in enumerate(rec.BaseAnchor):
                            if a is None:
                                continue
                            ac = copy.copy(a)
                            ac.XCoordinate, ac.YCoordinate = _transform_anchor_xy(
                                ac.XCoordinate, ac.YCoordinate, scale_x, scale_y, sx, sy, pad_l, above_zero
                            )
                            rec.BaseAnchor[ci] = ac
                elif kind == "MarkLigPos":
                    for lname, lig in zip(st.LigatureCoverage.glyphs, st.LigatureArray.LigatureAttach):
                        if lname not in anchor_params:
                            continue
                        scale_x, scale_y, sx, sy, pad_l, _ = anchor_params[lname]
                        for comp_rec in lig.ComponentRecord:
                            for ci, a in enumerate(comp_rec.LigatureAnchor):
                                if a is None:
                                    continue
                                ac = copy.copy(a)
                                ac.XCoordinate, ac.YCoordinate = _transform_anchor_xy(
                                    ac.XCoordinate, ac.YCoordinate, scale_x, scale_y, sx, sy, pad_l, False
                                )
                                comp_rec.LigatureAnchor[ci] = ac

    for cname in t.getGlyphOrder():
        g = glyf[cname]
        if not g.isComposite():
            continue
        base_comps = [c for c in g.components if c.glyphName in params_by_glyph]
        if not base_comps:
            continue
        base_name = base_comps[0].glyphName
        scale_x, scale_y, sx, sy, pad_l, pad_r = params_by_glyph[base_name]
        letter_indices = [idx for idx, c in enumerate(g.components) if c.glyphName in params_by_glyph]
        for idx, c in enumerate(g.components):
            cx, cy = getattr(c, "x", 0), getattr(c, "y", 0)
            if c.glyphName in params_by_glyph:
                if idx == letter_indices[0]:
                    c.x = round(cx * scale_x)
                    c.y = round(cy * scale_y)
                else:
                    c.x = round(cx * scale_x + sx + pad_l + pad_r)
                    c.y = round(cy * scale_y)
            else:
                c.x = round(cx * scale_x + sx / 2.0 + pad_l)
                y_vis = mark_mid_y.get(c.glyphName, 0.0) + cy
                if y_vis > 950:
                    c.y = round(cy + y_vis * (scale_y - 1.0) + sy)
                elif y_vis > 200:
                    c.y = round(cy + y_vis * (scale_y - 1.0) + sy / 2.0)
                elif y_vis < -100:
                    c.y = round(cy + y_vis * (scale_y - 1.0))
                else:
                    c.y = cy
        g.recalcBounds(glyf)
        old_adv, _ = hmtx[cname]
        if len(letter_indices) >= 2:
            hmtx[cname] = (round(old_adv * scale_x + 2 * sx) + 2 * (pad_l + pad_r) if old_adv else 0, g.xMin)
        else:
            hmtx[cname] = (round(old_adv * scale_x + sx) + pad_l + pad_r if old_adv else 0, g.xMin)


def _collect_effective_mark_offsets(t: TTFont) -> dict[tuple[str, str], tuple[int, int]]:
    offsets: dict[tuple[str, str], tuple[int, int]] = {}
    if "GPOS" not in t:
        return offsets
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            mark_info = [(mg, mr.Class, mr.MarkAnchor) for mg, mr in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord)]
            for bg, br in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                for mg, cls, ma in mark_info:
                    ba = br.BaseAnchor[cls] if cls < len(br.BaseAnchor) else None
                    if ba is not None and ma is not None:
                        offsets[(bg, mg)] = (ba.XCoordinate - ma.XCoordinate, ba.YCoordinate - ma.YCoordinate)
    return offsets


def swap_glyphs(target_tt: TTFont, donor_tt: TTFont, glyph_names: list[str]) -> None:
    t_glyf, d_glyf = target_tt["glyf"], donor_tt["glyf"]
    t_hmtx, d_hmtx = target_tt["hmtx"], donor_tt["hmtx"]
    donor_set = set()

    for gname in glyph_names:
        if gname not in d_glyf or gname not in t_glyf:
            continue
        t_glyf[gname] = copy.deepcopy(d_glyf[gname])
        t_hmtx[gname] = d_hmtx[gname]
        donor_set.add(gname)

    anchor_sync_set = set(donor_set)
    for cname in target_tt.getGlyphOrder():
        tg = t_glyf[cname]
        if not tg.isComposite():
            continue
        base_comps = [c for c in tg.components if c.glyphName in donor_set]
        if not base_comps:
            continue
        anchor_sync_set.add(cname)
        if cname in d_glyf and d_glyf[cname].isComposite():
            dg = d_glyf[cname]
            if [c.glyphName for c in tg.components] == [c.glyphName for c in dg.components]:
                for tc, dc in zip(tg.components, dg.components):
                    tc.x = dc.x
                    tc.y = dc.y
                tg.recalcBounds(t_glyf)
                t_hmtx[cname] = (d_hmtx[cname][0], tg.xMin)

    donor_offsets = _collect_effective_mark_offsets(donor_tt)
    if "GPOS" in target_tt:
        for lk in target_tt["GPOS"].table.LookupList.Lookup:
            for st in lk.SubTable:
                st = getattr(st, "ExtSubTable", st)
                if type(st).__name__ != "MarkBasePos":
                    continue
                class_marks: dict[int, list[tuple[str, object]]] = {}
                for mg, mr in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord):
                    if mr.MarkAnchor is not None:
                        class_marks.setdefault(mr.Class, []).append((mg, mr.MarkAnchor))
                for bg, br in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                    if bg not in anchor_sync_set:
                        continue
                    for ci, ba in enumerate(br.BaseAnchor):
                        if ba is None or ci not in class_marks:
                            continue
                        matched = None
                        for mg, ma in class_marks[ci]:
                            if (bg, mg) in donor_offsets:
                                dx, dy = donor_offsets[(bg, mg)]
                                matched = (ma.XCoordinate + dx, ma.YCoordinate + dy)
                                break
                        if matched is not None:
                            ac = copy.copy(ba)
                            ac.XCoordinate, ac.YCoordinate = matched
                            br.BaseAnchor[ci] = ac


def set_family_name(t: TTFont, family: str) -> None:
    ps = family.replace(" ", "")
    for r in t["name"].names:
        if r.nameID in (1, 16):
            r.string = family
        elif r.nameID == 2:
            r.string = "Regular"
        elif r.nameID == 4:
            r.string = family
        elif r.nameID == 6:
            r.string = ps
        elif r.nameID == 3:
            r.string = f"Sofer : {family}"


# ---- the snug bases (Antigravity's build_printed_sefer.py) ---------------------------------------

def snug_params_for(
    t: TTFont, *, scale_x: float, scale_y: float, sx: float, sy: float,
    ratio: float, sb_min: int, sb_max: int
) -> dict[str, tuple[float, float, float, float, int, int]]:
    """Compute per-glyph parameters with snug printed-book side bearings."""
    glyf, hmtx = t["glyf"], t["hmtx"]
    gs = t.getGlyphSet()
    params = {}
    for gname in hebrew_letter_glyphs(t):
        g = glyf[gname]
        if g.isComposite():
            bp = BoundsPen(gs)
            gs[gname].draw(bp)
            if bp.bounds is None:
                params[gname] = (scale_x, scale_y, sx, sy, 0, 0)
                continue
            xMin, _, xMax, _ = bp.bounds
        else:
            g.recalcBounds(glyf)
            xMin, xMax = g.xMin, g.xMax
        adv = hmtx[gname][0]
        lsb_after = round(xMin * scale_x)
        rsb_after = round((adv - xMax) * scale_x)
        target_lsb = max(sb_min, min(sb_max, round(lsb_after * ratio)))
        target_rsb = max(sb_min, min(sb_max, round(rsb_after * ratio)))
        pad_l = target_lsb - lsb_after
        pad_r = target_rsb - rsb_after
        params[gname] = (scale_x, scale_y, sx, sy, pad_l, pad_r)
    return params


def trim_lookups(path: Path, keep_count: int) -> None:
    t = TTFont(path)
    gpos = t["GPOS"].table
    lookups = gpos.LookupList.Lookup
    if len(lookups) > keep_count:
        del lookups[keep_count:]
        gpos.LookupList.LookupCount = len(lookups)
        for fr in gpos.FeatureList.FeatureRecord:
            fr.Feature.LookupListIndex = [i for i in fr.Feature.LookupListIndex if i < keep_count]
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    t.save(path)


def build_snug_vilna(classic: Path, dst: Path) -> Path:
    shutil.copyfile(classic, dst)
    t = TTFont(dst)
    params = snug_params_for(t, **VILNA_PARAMS)
    transform_font(t, params)
    t.save(dst)
    trim_lookups(dst, CORE_VILNA_LOOKUPS)
    fix_lsb.fix(dst)
    return dst


def build_snug_frank(frank: Path, drugulin: Path, dst: Path) -> Path:
    shutil.copyfile(frank, dst)
    vilna_old_ayin.add(drugulin, dst)
    t = TTFont(dst)
    params = snug_params_for(t, **FRANK_PARAMS)
    # Use Vilna proportions & snug bearings for ayin.drugulin
    ag = t["glyf"]["ayin.drugulin"]
    ag.recalcBounds(t["glyf"])
    adv = t["hmtx"]["ayin.drugulin"][0]
    vx, vy, vsx, vsy = VILNA_PARAMS["scale_x"], VILNA_PARAMS["scale_y"], VILNA_PARAMS["sx"], VILNA_PARAMS["sy"]
    lsb_a = round(ag.xMin * vx)
    rsb_a = round((adv - ag.xMax) * vx)
    t_lsb = max(VILNA_PARAMS["sb_min"], min(VILNA_PARAMS["sb_max"], round(lsb_a * VILNA_PARAMS["ratio"])))
    t_rsb = max(VILNA_PARAMS["sb_min"], min(VILNA_PARAMS["sb_max"], round(rsb_a * VILNA_PARAMS["ratio"])))
    params["ayin.drugulin"] = (vx, vy, vsx, vsy, t_lsb - lsb_a, t_rsb - rsb_a)
    transform_font(t, params)
    t.save(dst)
    trim_lookups(dst, CORE_FRANK_LOOKUPS)
    fix_lsb.fix(dst)
    return dst


# ---- the pipeline (Antigravity's build_sefer1_full.py + the release step of fix_finalmem_dagesh.py) --

def run_pipeline_for_weight(path: Path, words: list[str] | None, meteg_words) -> None:
    """The placement, collision and ם / dagesh-chazak steps.  words None = --quick (no collision steps)."""
    import clear_meteg
    import make_stam_sefarad as msf
    import vav_two_marks
    print(f"\n=== Placement & collision pipeline for {path.name} ===", flush=True)
    print("  1. dehi_beside:", dehi_beside.fix(path), flush=True)
    print("  2. qof_vowel:", qof_vowel.fix(path), flush=True)
    print("  3. under_body (dalet left-align):", under_body.fix(path, lamed=False, left=True), flush=True)
    if words is not None:
        print("  4. vav_two_marks:", vav_two_marks.fix(path, words), flush=True)
        print("  5. fix_by_shaping (pass 1):", msf.fix_by_shaping(path, words), flush=True)
        print("  6. clear_meteg:", clear_meteg.clear(path, meteg_words, rounds=10), flush=True)
        print("  7. fix_by_shaping (pass 2):", msf.fix_by_shaping(path, words), flush=True)
    print("  8. center_finalmem_dagesh:", ffd.center_finalmem_dagesh(path), flush=True)
    print("  9. sync_dagesh_xazaq:", ffd.sync_dagesh_xazaq(path, only_bases=ffd.VILNA_XAZAQ_BASES), flush=True)
    print(" 10. fix_lsb:", fix_lsb.fix(path), "bearings fixed", flush=True)


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = list(argv)

    def opt(name: str, default: Path) -> Path:
        if name in args:
            i = args.index(name)
            v = Path(args[i + 1])
            del args[i:i + 2]
            return v
        return default

    out_dir = opt("--out", FONTS)
    classic = opt("--classic", FONTS / "VilnaClassic.ttf")
    frank = opt("--frank", FONTS / "FrankSofer.ttf")
    drugulin = opt("--drugulin", DRUGULIN_SRC)
    work = opt("--work", out_dir / "_work_vilna_sofer")
    quick = "--quick" in args
    out_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    reg = out_dir / "VilnaSofer.ttf"
    bold = out_dir / "VilnaSofer-Bold.ttf"
    vilna_base = work / "_sefer1_vilna_base.ttf"
    frank_base = work / "_sefer1_frank_base.ttf"

    print("Building the Vilna Sofer Regular base (Vilna Classic, snug)...", flush=True)
    build_snug_vilna(classic, vilna_base)
    build_snug_frank(frank, drugulin, frank_base)
    shutil.copyfile(vilna_base, reg)
    t1 = TTFont(reg)
    swap_glyphs(t1, TTFont(frank_base), OPTION_C_FRANK_LETTERS)
    set_family_name(t1, "Sefer1")
    t1.save(reg)
    fix_lsb.fix(reg)

    print(f"Building the Bold (strength {BOLD_STRENGTH})...", flush=True)
    make_bold.STRENGTH = BOLD_STRENGTH
    make_bold.STRENGTH_Y = round(BOLD_STRENGTH * 0.7, 4)
    print(" ", make_bold.make(reg, bold), flush=True)

    words = meteg_words = None
    if not quick:
        import check_meteg
        import make_stam_sefarad as msf
        print("Loading Tanach and siddur words...", flush=True)
        words = msf.tanach_words() + msf.siddur_words()
        meteg_words = check_meteg.siddur_words()
        meteg_words.update(check_meteg.tanach_words())
        print(f"Loaded {len(words)} total words, {len(meteg_words)} distinct meteg words.", flush=True)

    run_pipeline_for_weight(reg, words, meteg_words)
    run_pipeline_for_weight(bold, words, meteg_words)
    ffd.set_font_family(reg, "Vilna Sofer", bold=False)
    ffd.set_font_family(bold, "Vilna Sofer", bold=True)
    print("\nDone: " + str(reg) + " and " + str(bold), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
