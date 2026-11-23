"""The marks under ל under its body, and a lone mark under ד under its leg, measured on the font's own
letters (Open Siddur, 2026-11-23, on Sofer Stam Ashkenaz / Sefarad and Mekorot Rashi: "the positioning
of niqqudot under the stem of the lamed"; Mordy: "the stem of the ד also looks off").

The fonts made from Frank Sofer (scripts/make_stam_sefarad.py) take each anchor from Frank's letter to
the same place across the new letter's whole width.  The Stam ל's flag reaches far left, so its vowels
came out under the flag's end, left of the body; the Stam ד is wider than Frank's, so the vowel that
Frank Sofer sets under the leg (make_frank_sofer.under_the_leg: 30% of the letter's width from its right)
came out left of the leg.  Here:

- ל (every form): the anchor the marks under the line hang from is moved so a lone vowel sits under the
  middle of the letter's ink just above the line (FOOT_Y) - where Frank Sofer sets it on its own ל.
  Every mark under the ל moves with it (a vowel and its ta'am or meteg keep their places side by side).
- ד (every form): one contextual lookup, last in "mark": a lone mark under the letter (no other mark
  under it after) moves to under the letter's lowest point - the bottom tip of its leg (Mordy,
  2026-11-23); Frank Sofer and its bold too; with two marks under
  the letter they stay where they were (as in Frank Sofer).

    .venv/Scripts/python scripts/under_body.py <font.ttf> [...] [--dalet-only] [--lamed-by -0.17]   (in place)

Run on a built font after its other placement steps, then the collision fixer and clear_meteg
(make_stam_sefarad.py runs it for the Sefer Torah fonts).  Run again on a font that has it, it changes
nothing (the ל is already there; the ד's lookup is found and replaced).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.otlLib import builder as otl
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_frank_sofer import _runs  # noqa: E402

FOOT_Y = 60          # (units of 2048: the height of the ink measured, just above the line)
MIN_MOVE = 25        # (units of 2048: closer than this to its place, a mark is left as it is)
LETTERS = {"ל": "lamed", "ד": "dalet"}


def _font(T):
    buf = io.BytesIO()
    T.save(buf)
    return hb.Font(hb.Face(hb.Blob(buf.getvalue())))


def _shape(font, T, gs, text):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    x, out = 0, []
    for i, p in zip(buf.glyph_infos, buf.glyph_positions):
        name = T.getGlyphName(i.codepoint)
        b = BoundsPen(gs)
        gs[name].draw(b)
        if b.bounds:
            out.append((name, x + p.x_offset + b.bounds[0], x + p.x_offset + b.bounds[2], x))
        x += p.x_advance
    return out


def _target(T, name, scale, which):
    """The middle of the letter's ink at FOOT_Y: the widest stretch (ל's body), or the rightmost (ד's leg)."""
    runs = _runs(T, name, FOOT_Y * scale)
    if not runs:
        return None
    return max(runs, key=lambda r: r[1] - r[0]) if which == "lamed" else max(runs, key=lambda r: r[1])


def _lowest_x(T, name, tol=12):
    """The x of the letter's lowest ink (the middle of its outline's points within ``tol`` units of the
    lowest one): the bottom tip of the ד's leg (Mordy, 2026-11-23: "the nikud under the LOWEST point of
    the ד")."""
    from fontTools.pens.basePen import BasePen

    class _Pts(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.pts = []

        def _moveTo(self, p):
            self.pts.append(p)
            self.last = p

        def _lineTo(self, p):
            self.pts.append(p)
            self.last = p

        def _curveToOne(self, a, b, c):
            p0 = self.last
            for i in range(1, 17):
                t = i / 16
                mt = 1 - t
                self.pts.append((mt ** 3 * p0[0] + 3 * mt * mt * t * a[0] + 3 * mt * t * t * b[0] + t ** 3 * c[0],
                                 mt ** 3 * p0[1] + 3 * mt * mt * t * a[1] + 3 * mt * t * t * b[1] + t ** 3 * c[1]))
            self.last = c

        def _qCurveToOne(self, a, b):
            p0 = self.last
            for i in range(1, 13):
                t = i / 12
                mt = 1 - t
                self.pts.append((mt * mt * p0[0] + 2 * mt * t * a[0] + t * t * b[0],
                                 mt * mt * p0[1] + 2 * mt * t * a[1] + t * t * b[1]))
            self.last = b

    gs = T.getGlyphSet()
    pen = _Pts(gs)
    gs[name].draw(pen)
    if not pen.pts:
        return None
    low = min(y for _, y in pen.pts)
    xs = [x for x, y in pen.pts if y <= low + tol]
    return (min(xs) + max(xs)) / 2


def _below_marks(T, gs):
    classes = getattr(T["GDEF"].table.GlyphClassDef, "classDefs", {})
    out = set()
    for n, c in classes.items():
        if c == 3 and n in gs:
            b = BoundsPen(gs)
            gs[n].draw(b)
            if b.bounds and b.bounds[3] <= 0:
                out.add(n)
    return out


def _lamed(T, scale, by: float = 0.0) -> list[str]:
    """Move the ל forms' anchors for the marks below the line: under the body's middle, or (``by``,
    a fraction of the letter's width; minus = left) by that much."""
    font, gs = _font(T), T.getGlyphSet()
    shifts = {}
    if by:
        for n in T.getGlyphOrder():
            if n.startswith("lamed") and T["glyf"][n].numberOfContours:
                g = T["glyf"][n]
                g.recalcBounds(T["glyf"])
                shifts[n] = round(by * (g.xMax - g.xMin))
    for form in (() if by else ("", "ּ", "ּ׉")):
        g = _shape(font, T, gs, "ל" + form + "ְ")
        base = max(g, key=lambda q: q[2] - q[1])
        under = [q for q in g if q is not base and q[0] in ("sheva", "shevana")]
        if not under:
            continue
        run = _target(T, base[0], scale, "lamed")
        if run is None:
            continue
        centre = (under[0][1] + under[0][2]) / 2 - base[3]
        third = (run[1] - run[0]) / 5
        if run[0] + third <= centre <= run[1] - third:
            continue                    # (already under the body's middle: left as the font has it)
        shifts[base[0]] = round((run[0] + run[1]) / 2 - centre)
    # (the letter's other forms - wide, for justifying: as the plain one)
    for n in T.getGlyphOrder():
        root = n.split(".")[0]
        if n not in shifts and root in shifts and n.startswith("lamed"):
            shifts[n] = shifts[root]
    below = _below_marks(T, gs)
    done = []
    for lk in T["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            # (the classes of the marks under the line: only their anchors move)
            classes = {r.Class for g, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if g in below}
            for base, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                dx = shifts.get(base)
                if not dx or abs(dx) < MIN_MOVE * scale:
                    continue
                for c in classes:
                    a = rec.BaseAnchor[c]
                    if a is not None:
                        a.XCoordinate += dx
                        done.append(f"{base} {dx:+d}")
    return sorted(set(done))


def _dalet(T, scale) -> list[str]:
    gpos, gdef = T["GPOS"].table, T["GDEF"].table
    lookups = gpos.LookupList.Lookup
    rev = T.getReverseGlyphMap()
    # (a font that has it: the lookup and its single moves taken out first - they are the last ones)
    mark = [fr for fr in gpos.FeatureList.FeatureRecord if fr.FeatureTag == "mark"]
    sets = gdef.MarkGlyphSetsDef

    def ours(i):
        """Our ד lookup: the last one, a chain whose every rule looks back at ד forms only."""
        if i != len(lookups) - 1:
            return False
        subs = [getattr(st, "ExtSubTable", st) for st in lookups[i].SubTable]
        for st in subs:
            back = getattr(st, "BacktrackCoverage", None)
            if getattr(st, "Format", 0) != 3 or not back or not all(g.startswith("dalet") for g in back[0].glyphs):
                return False
        return bool(subs)
    old = [i for fr in mark for i in fr.Feature.LookupListIndex if ours(i)]
    if old:
        i = old[0]
        nested = [r.LookupListIndex for st in lookups[i].SubTable
                  for r in getattr(st, "ExtSubTable", st).PosLookupRecord]
        first = min([i] + nested)
        drop = set(range(first, len(lookups)))
        for fr in gpos.FeatureList.FeatureRecord:
            fr.Feature.LookupListIndex = [j for j in fr.Feature.LookupListIndex if j not in drop]
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
        del lookups[first:]
    font, gs = _font(T), T.getGlyphSet()
    below = _below_marks(T, gs)
    rules: dict = {}
    for form in ("", "ּ", "ּ׉", "ֿ"):
        for cp in list(range(0x0591, 0x05B0)) + list(range(0x05B0, 0x05BC)) + [0x05BD, 0x05C7, 0x05C8]:
            if cp in (0x05B9, 0x05BA, 0x059A, 0x05AD):     # (the dehi and yetiv: set beside, dehi_beside.py)
                continue
            g = _shape(font, T, gs, "ד" + form + chr(cp))
            if len(g) < 2:
                continue
            base = max(g, key=lambda q: q[2] - q[1])
            under = [q for q in g if q is not base and q[0] in below]
            if len(under) != 1:
                continue
            low = _lowest_x(T, base[0], 12 * scale)
            if low is None:
                continue
            m = under[0]
            dx = round(base[3] + low - (m[1] + m[2]) / 2)
            if abs(dx) >= MIN_MOVE * scale:
                rules[(base[0], m[0])] = dx
    if not rules:
        return []
    if sets is None:
        sets = gdef.MarkGlyphSetsDef = ot.MarkGlyphSetsDef()
        sets.MarkSetTableFormat, sets.Coverage, sets.MarkSetCount = 1, [], 0
        gdef.Version = 0x00010002
    sets.Coverage.append(otl.buildCoverage(sorted(below), rev))
    sets.MarkSetCount = len(sets.Coverage)
    singles: dict = {}

    def single(mg, dx):
        if (mg, dx) not in singles:
            lookups.append(otl.buildLookup([otl.buildSinglePosSubtable(
                {mg: otl.buildValue({"XPlacement": dx})}, rev)], table="GPOS"))
            singles[(mg, dx)] = len(lookups) - 1
        return singles[(mg, dx)]

    def chain(back, inputs, record, ahead=()):
        st = ot.ChainContextPos()
        st.Format = 3
        st.BacktrackCoverage = [otl.buildCoverage(back, rev)]
        st.InputCoverage = [otl.buildCoverage(i, rev) for i in inputs]
        st.LookAheadCoverage = [otl.buildCoverage(a, rev) for a in ahead]
        st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = 1, len(inputs), len(ahead)
        st.PosLookupRecord = []
        if record is not None:
            r = ot.PosLookupRecord()
            r.SequenceIndex, r.LookupListIndex = 0, record
            st.PosLookupRecord = [r]
        st.PosCount = len(st.PosLookupRecord)
        return st
    bases = sorted({b for b, _ in rules})
    marks = sorted({m for _, m in rules})
    # (another mark under the letter after it: nothing - a look-ahead, as qof_vowel.py, for Typst's shaper)
    subtables = [chain(bases, [marks], None, [sorted(below)])]
    groups: dict = {}
    for (b, m), dx in rules.items():
        groups.setdefault((m, dx), set()).add(b)
    for (m, dx), bs in sorted(groups.items()):
        subtables.append(chain(sorted(bs), [[m]], single(m, dx)))
    lk = ot.Lookup()
    lk.LookupType, lk.LookupFlag, lk.MarkFilteringSet = 8, 0x0010, sets.MarkSetCount - 1
    lk.SubTable, lk.SubTableCount = subtables, len(subtables)
    lookups.append(lk)
    gpos.LookupList.LookupCount = len(lookups)
    for fr in mark:
        fr.Feature.LookupListIndex.append(len(lookups) - 1)
        fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    moves = sorted(set(rules.values()))
    return [f"{len(rules)} lone marks, {moves[0]:+d}..{moves[-1]:+d} units"]


def fix(path: Path, lamed: bool = True, lamed_by: float = 0.0) -> str:
    T = TTFont(path)
    scale = T["head"].unitsPerEm / 2048
    lam = _lamed(T, scale, lamed_by) if lamed or lamed_by else ["not moved (--dalet-only)"]
    T2 = TTFont(io.BytesIO(_save(T)))
    dal = _dalet(T2, scale)
    __import__("gpos_ext").as_extensions(T2)
    T2.save(path)
    return f"{path.name}: ל {', '.join(lam) or 'already under its body'}; ד {', '.join(dal) or 'already under its leg'}"


def _save(T):
    buf = io.BytesIO()
    T.save(buf)
    return buf.getvalue()


if __name__ == "__main__":
    # (--dalet-only: the ד alone - Mekorot Rashi, whose ל's vowel stands under its slanting body as drawn)
    # (--lamed-by F: the marks under ל moved by F of the letter's width, minus = left - Mekorot Rashi's,
    #  Mordy 2026-11-23: "the ל in Rashi should be a bit more to the left")
    by = float(sys.argv[sys.argv.index("--lamed-by") + 1]) if "--lamed-by" in sys.argv else 0.0
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] != "--lamed-by"]
    for p in args:
        print(fix(Path(p), lamed="--dalet-only" not in sys.argv, lamed_by=by))
