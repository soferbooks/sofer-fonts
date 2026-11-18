"""The last steps for the fonts made from Frank Sofer with other letters - Drugulin (Claude, from Culmus'
Drugulin CLM: the standard since 2026-11-17), Mekorot Rashi, Hadassah, regular and bold (Antigravity built
the Mekorot and Hadassah ones, 2026-11-17; Mordy asked Claude to check them):

1. a mark under ן where Frank Sofer puts it, in proportion to the letter's width (beside its leg, away
   from the letter before; these fonts had it at the right, under that letter's vowel: יָוָ֤ן);
2. Frank Sofer's own spacing rules turned back on: its "kern" feature (lookups 0 and 6 - a narrow letter,
   ו י ז נ ג ..., with a vowel under it is given room, so the vowels of the letters beside it do not
   meet) was left empty in these fonts, though the lookups are there: יָוָן's two kamatzes touched;
3. a vav with a vowel and a ta'am under it: the ta'am moved left, clear of the vowel, by as much as each
   vowel needs (scripts/vav_two_marks.py - יָוָ֤ן; before the collision fixer, which pushes two marks under
   one narrow letter the wrong way);
4. the collision fixer over every word of Tanach and the siddurim (make_stam_sefarad.fix_by_shaping);
5. the bearings (scripts/fix_lsb.py).

    .venv/Scripts/python scripts/finish_mekorot_fonts.py [font.ttf ...]   (default: the six files in fonts/)
"""
from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont

REPO = Path(__file__).resolve().parents[1]
FONTS = REPO / "fonts"
sys.path.insert(0, str(REPO / "scripts"))
import fix_lsb  # noqa: E402
import make_stam_sefarad as msf  # noqa: E402
import vav_two_marks  # noqa: E402

FILES = ("VilnaSofer.ttf", "VilnaSofer-Bold.ttf", "MekorotRashi.ttf", "MekorotRashi-Bold.ttf",
         "Hadassah.ttf", "Hadassah-Bold.ttf")
# (the Frank Sofer each was made from: its lookups are in the same order.  Drugulin's bold is its regular
#  thickened - scripts/make_bold.py - so Frank Sofer's regular)
MADE_FROM = {"VilnaSofer-Bold.ttf": "FrankSofer.ttf"}


def frank_of(path: Path) -> Path:
    return FONTS / MADE_FROM.get(path.name, "FrankSofer-Bold.ttf" if "Bold" in path.name else "FrankSofer.ttf")


def _mark_base(t: TTFont):
    """((lookup, subtable), MarkBasePos) of the font, extensions unwrapped."""
    for i, lk in enumerate(t["GPOS"].table.LookupList.Lookup):
        for j, st in enumerate(lk.SubTable):
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ == "MarkBasePos":
                yield (i, j), st


def kern_on(path: Path) -> str:
    """Frank Sofer's "kern" lookups in the font's "kern" feature again (the same lookups: the font was
    made from Frank Sofer, its lookups in the same order)."""
    frank = TTFont(frank_of(path))
    want = sorted({i for fr in frank["GPOS"].table.FeatureList.FeatureRecord if fr.FeatureTag == "kern"
                   for i in fr.Feature.LookupListIndex})
    t = TTFont(path)
    gpos = t["GPOS"].table
    for i in want:     # (the same rule in both: checked by its letters)
        a = getattr(gpos.LookupList.Lookup[i].SubTable[0], "ExtSubTable", gpos.LookupList.Lookup[i].SubTable[0])
        b = getattr(frank["GPOS"].table.LookupList.Lookup[i].SubTable[0], "ExtSubTable",
                    frank["GPOS"].table.LookupList.Lookup[i].SubTable[0])
        if [c.glyphs for c in a.InputCoverage] != [c.glyphs for c in b.InputCoverage]:
            raise SystemExit(f"{path.name}: lookup {i} is not Frank Sofer's")
    n = 0
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "kern" and not fr.Feature.LookupListIndex:
            fr.Feature.LookupListIndex = list(want)
            fr.Feature.LookupCount = len(want)
            n += 1
    t.save(path)
    return f"kern {want} on in {n} language systems"


UNDER_LIKE_FRANK = ("finalnun",)


def marks_below_like_frank(path: Path) -> str:
    """The anchors for marks below these letters (UNDER_LIKE_FRANK) at Frank Sofer's place, in proportion
    to the letter's advance (the lookups are Frank Sofer's, in the same order)."""
    frank = TTFont(frank_of(path))
    t = TTFont(path)
    glyf = t["glyf"]
    ftables = dict(_mark_base(frank))
    moved = 0
    for key, st in _mark_base(t):
        fst = ftables.get(key)
        if fst is None or fst.ClassCount != st.ClassCount:
            continue
        below = set()
        for mi, mn in enumerate(st.MarkCoverage.glyphs):
            g = glyf[mn]
            if g.numberOfContours:
                g.recalcBounds(glyf)
                if g.yMax <= 60:
                    below.add(st.MarkArray.MarkRecord[mi].Class)
        for n in UNDER_LIKE_FRANK:
            if n not in st.BaseCoverage.glyphs or n not in fst.BaseCoverage.glyphs:
                continue
            k = t["hmtx"][n][0] / frank["hmtx"][n][0]
            mine = st.BaseArray.BaseRecord[st.BaseCoverage.glyphs.index(n)].BaseAnchor
            theirs = fst.BaseArray.BaseRecord[fst.BaseCoverage.glyphs.index(n)].BaseAnchor
            for c in below:
                if mine[c] is not None and theirs[c] is not None:
                    mine[c].XCoordinate = round(theirs[c].XCoordinate * k)
                    moved += 1
    t.save(path)
    return f"{moved} anchors under {', '.join(UNDER_LIKE_FRANK)} as in Frank Sofer"


def finish(path: Path, words: list[str]) -> None:
    print(f"  {path.name}: {marks_below_like_frank(path)}", flush=True)
    print(f"  {path.name}: {kern_on(path)}", flush=True)
    print(f"  {path.name}: {vav_two_marks.fix(path, words)}", flush=True)
    print(f"  {path.name}: {msf.fix_by_shaping(path, words)}", flush=True)
    print(f"  {path.name}: {fix_lsb.fix(path)} bearings put right", flush=True)


if __name__ == "__main__":
    files = [Path(a) for a in sys.argv[1:]] or [FONTS / f for f in FILES]
    words = sorted(set(msf.tanach_words() + msf.siddur_words()))
    print(f"{len(words):,} words of Tanach and the siddurim", flush=True)
    for p in files:
        finish(p, words)
