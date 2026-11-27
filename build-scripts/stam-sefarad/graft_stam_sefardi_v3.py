from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

SCRATCH = Path(__file__).resolve().parent / "scratch"
SOFER_SCRIPTS = Path(__file__).resolve().parents[1]
OUTLINES_V3 = SCRATCH / "_stam_sefardi_v3_outlines.ttf"
FRANK_PATH = SCRATCH / "release" / "FrankSofer.ttf"
OUT_PATH = SCRATCH / "release" / "SoferStamSefaradHayom.ttf"

sys.path.insert(0, str(SCRATCH))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(SOFER_SCRIPTS))

import graft_stam_sefardi_new as v1_graft  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402
import fix_lsb  # noqa: E402
import check_font_marks  # noqa: E402


def center_lamed_orphan_mark_anchor(T: TTFont, target_x: int = 0) -> int:
    """Center xiriq.orphan/sheva.orphan on lamed cleanly inside the gap between finalmem and lamed."""
    changed = 0
    for lk in T["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            if "xiriq.orphan" not in st.MarkCoverage.glyphs:
                continue
            cls_idx = st.MarkArray.MarkRecord[st.MarkCoverage.glyphs.index("xiriq.orphan")].Class
            for bname in ("lamed", "lameddagesh", "lameddagesh.xazaq"):
                if bname not in st.BaseCoverage.glyphs:
                    continue
                bi = st.BaseCoverage.glyphs.index(bname)
                a = st.BaseArray.BaseRecord[bi].BaseAnchor[cls_idx]
                if a is not None and a.XCoordinate != target_x:
                    a.XCoordinate = target_x
                    changed += 1
    return changed


def align_dropped_base_vowels(T: TTFont) -> int:
    """Keep below-base vowels cleanly centered & below dropped Sefardi pe (-165u) and tsadi (-150u)."""
    G = T["glyf"]
    if "qamats" not in G.glyphs:
        return 0
    G["qamats"].recalcBounds(G)
    q_ymax = G["qamats"].yMax
    changed = 0
    for lk in T["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos" or "qamats" not in st.MarkCoverage.glyphs:
                continue
            mi = st.MarkCoverage.glyphs.index("qamats")
            mc = st.MarkArray.MarkRecord[mi].Class
            ma = st.MarkArray.MarkRecord[mi].MarkAnchor
            for bname, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                root = bname.split(".")[0]
                if root not in ("pe", "pedagesh", "tsadi", "tsadidagesh"):
                    continue
                a = rec.BaseAnchor[mc]
                if a is None or bname not in G.glyphs:
                    continue
                g = G[bname]
                g.recalcBounds(G)
                cx = round(0.5 * (g.xMin + g.xMax))
                max_y = round(g.yMin - 95 - q_ymax + ma.YCoordinate)
                mod = False
                if abs(a.XCoordinate - cx) > 25:
                    a.XCoordinate = cx
                    mod = True
                if a.YCoordinate > max_y:
                    a.YCoordinate = max_y
                    mod = True
                if mod:
                    if a.Format != 1:
                        a.Format = 1
                    changed += 1
    return changed


def main():
    ms = v1_graft.ms
    ms.FRANK = FRANK_PATH
    ms.OUT = OUT_PATH
    ms.FAMILY = "Sofer Stam Sefarad Hayom"
    ms.SOURCE = "Mishnas Sofrim - Meoros HaMizrach (Minhag HaSofrim HaYom, v3 4-line aligned with authentic serifs)"

    print("Grafting FrankSofer nikud & ta'amim onto v3 Sefardi Stam outlines...")
    ms.main(str(OUTLINES_V3))

    T = TTFont(OUT_PATH)
    n1 = v1_graft.fix_all_dagesh_open_spots(T)
    n2 = v1_graft.clean_dagesh_xazaq_parity(T)
    n_xo = center_lamed_orphan_mark_anchor(T, target_x=0)
    n_dv = align_dropped_base_vowels(T)
    if n_dv:
        v1_graft.ms.apart_below(T)
    for rec in T["name"].names:
        if rec.nameID == 0:
            rec.string = (
                "Sofer Stam Sefarad Hayom v3: Hebrew Sefardi Stam outlines traced from perspective-normalized "
                "Mishnas Sofrim (Minhag HaSofrim HaYom / HaKtiva HaSefardit) diagrams with 4-line main-body calibration, "
                "authentic serifs, balanced bars and Old Sefardi widths, combined with Frank Sofer nikud, ta'amim, meteg, shva na, and dagesh chazak."
            )
    T.save(OUT_PATH)
    if n_dv:
        v1_graft.ms.clear_between(OUT_PATH)
    lsb_cnt = fix_lsb.fix(OUT_PATH)
    probs = check_font_marks.check_font(OUT_PATH)
    print(f"\nv3 Dagesh open-spot fixes: {len(n1)}")
    for line in n1:
        print(" ", line)
    print(f"v3 Xazaq parity synced: {len(n2)}, Lamed orphan anchors centered: {n_xo}, Dropped base vowels: {n_dv}, LSBs fixed: {lsb_cnt}")
    print(f"check_font_marks: {'OK (0 issues)' if not probs else str(len(probs)) + ' issue(s)'}")
    for p in probs[:15]:
        print(" ", p)
    print("Final v3 font saved at:", OUT_PATH)


if __name__ == "__main__":
    main()
