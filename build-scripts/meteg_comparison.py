"""A picture of the meteg in Frank Ruehl CLM as Culmus made it and as Sofer changed it, for Culmus'
maintainer (Maxim Iorsh, 2026-11-18: "I would be grateful if you could show a visualization of
existing problems, and how the meteg placement was modified in these cases").

Part 1: every vowel under a few letters, with a meteg, before and after.  Part 2: the words of
Tanach and the siddurim where the original meteg was furthest from its vowel or touched it,
measured with HarfBuzz (as browsers and Typst shape them), before and after.

    .venv/Scripts/python scripts/meteg_comparison.py <original Medium.ttf> <original Bold.ttf> <out.pdf>

The "after" fonts are fonts/FrankRuehlCLM-Medium.ttf and -Bold.ttf (scripts/place_meteg.py).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import typst
import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

REPO = Path(__file__).resolve().parents[1]
METEG = 0x05BD
VOWELS = {0x05B0: "shva", 0x05B1: "chataf segol", 0x05B2: "chataf patach", 0x05B3: "chataf kamatz",
          0x05B4: "chirik", 0x05B5: "tzere", 0x05B6: "segol", 0x05B7: "patach", 0x05B8: "kamatz",
          0x05BB: "kubutz"}
LETTERS = "בדהלנקשת"
NL = chr(10)


def _renamed(src: Path, dst: Path, family: str) -> None:
    t = TTFont(src)
    for r in t["name"].names:
        if r.nameID in (1, 4, 16):
            r.string = family
        elif r.nameID == 6:
            r.string = family.replace(" ", "")
    t.save(dst)


_LOADED: dict = {}


def _font(path: Path):
    if path not in _LOADED:
        t = TTFont(path)
        gs = t.getGlyphSet()
        bounds = {}
        for n in t.getGlyphOrder():
            b = BoundsPen(gs)
            gs[n].draw(b)
            bounds[n] = b.bounds
        _LOADED[path] = (t, bounds, hb.Font(hb.Face(hb.Blob(path.read_bytes()))))
    return _LOADED[path]


def _boxes(path: Path, word: str):
    """[(cluster, glyph name, x0, y0, x1, y1)] as HarfBuzz sets the word, in font units."""
    t, bounds, font = _font(path)
    buf = hb.Buffer()
    buf.add_str(word)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    x, out = 0, []
    for i, p in zip(buf.glyph_infos, buf.glyph_positions):
        n = t.getGlyphName(i.codepoint)
        if bounds.get(n):
            x0, y0, x1, y1 = bounds[n]
            out.append((i.cluster, n, x + p.x_offset + x0, p.y_offset + y0, x + p.x_offset + x1, p.y_offset + y1))
        x += p.x_advance
    return out, t["head"].unitsPerEm, t.getBestCmap()


def meteg_gaps(path: Path, word: str, kinds: list | None = None) -> list[float]:
    """For each meteg after a vowel in the word: the gap between them (in em; below 0: touching).
    ``kinds`` gets (letter glyph, vowel glyph) for each."""
    boxes, upem, cmap = _boxes(path, word)
    meteg = cmap.get(METEG)
    vowels = {cmap[v] for v in VOWELS if v in cmap}
    out = []
    for c, n, *mb in boxes:
        if n != meteg:
            continue
        vs = [b for cc, nn, *b in boxes if cc == c and nn in vowels]
        if not vs:
            continue
        v = min(vs, key=lambda b: abs((b[0] + b[2]) / 2 - (mb[0] + mb[2]) / 2))
        dx = max(v[0] - mb[2], mb[0] - v[2])
        dy = max(v[1] - mb[3], mb[1] - v[3])
        out.append(max(dx, dy) / upem)
        if kinds is not None:
            base = next((nn for cc, nn, *b in boxes if cc == c and nn not in vowels and nn != meteg), "")
            kinds.append((base, next(nn for cc, nn, *b in boxes if cc == c and b == list(v))))
    return out


def words() -> list[str]:
    sys.path.insert(0, str(REPO / "scripts"))
    import make_stam_sefarad as m
    return sorted(set(m.tanach_words() + m.siddur_words()))


def main(orig_medium: str, orig_bold: str, out_pdf: str) -> None:
    after = REPO / "fonts" / "FrankRuehlCLM-Medium.ttf"
    tmp = Path(tempfile.mkdtemp())
    _renamed(Path(orig_medium), tmp / "before-medium.ttf", "Frank Ruehl Before")
    _renamed(Path(orig_bold), tmp / "before-bold.ttf", "Frank Ruehl Before")
    _renamed(after, tmp / "after-medium.ttf", "Frank Ruehl After")
    _renamed(REPO / "fonts" / "FrankRuehlCLM-Bold.ttf", tmp / "after-bold.ttf", "Frank Ruehl After")

    # part 2: the words where the original meteg was furthest away or touching
    rows = []
    for w in words():
        # (whole words only: not a fragment starting with a mark, nor one letter)
        if chr(METEG) not in w or not "א" <= w[0] <= "ת" or sum("א" <= c <= "ת" for c in w) < 3:
            continue
        kinds: list = []
        before = meteg_gaps(Path(orig_medium), w, kinds)
        if not before:
            continue
        rows.append((w, min(before), max(before), meteg_gaps(after, w), kinds[before.index(max(before))]))
    def varied(rs, n):
        """The first of each letter-and-vowel, so the list shows many kinds."""
        seen, out = set(), []
        for r in rs:
            if r[4] not in seen:
                seen.add(r[4])
                out.append(r)
            if len(out) == n:
                break
        return out
    touching = varied(sorted([r for r in rows if r[1] <= 0], key=lambda r: r[1]), 24)
    far = varied(sorted([r for r in rows if r[1] > 0], key=lambda r: -r[2]), 30)
    n_touch = sum(1 for r in rows if r[1] <= 0)
    n_all = len(rows)
    n_far = sum(1 for r in rows if r[2] > 0.09)

    def pair(text, size):
        return ("#grid(columns: (1fr, 1fr), gutter: 6pt, align: center + horizon,"
                f' text(font: "Frank Ruehl Before", size: {size}, "{text}"),'
                f' text(font: "Frank Ruehl After", size: {size}, "{text}"))' + NL)

    doc = ["#set page(width: 8.5in, height: auto, margin: 0.6in)" + NL,
           '#set text(font: "Noto Serif", size: 10pt)' + NL,
           '#let he(f, s, t) = text(font: f, size: s, dir: rtl, t)' + NL,
           "= The meteg in Frank Ruehl CLM: as released, and as Sofer changed it" + NL,
           "Each line: Culmus' Frank Ruehl CLM 0.140 on the left, Sofer's version on the right "
           "(scripts/place_meteg.py: the meteg set 0.045 em beside its vowel - the gap Taamey D, Keter YG and "
           "the Taamey fonts keep - at the height the font gives it; alone in the middle under a letter with "
           "no vowel; on the vowel's left beside a leg, as under ק). Shaped with HarfBuzz / Typst." + NL + NL,
           f"Of {n_all:,} words with a meteg in Tanach and the siddurim, the original meteg is more than "
           f"0.09 em from its vowel in {n_far:,} and touches it in {n_touch:,}." + NL + NL,
           "== 1. Every vowel with a meteg" + NL]
    doc.append('#grid(columns: (1fr, 1fr), gutter: 6pt, align: center, [*Frank Ruehl CLM (original)*], [*Sofer*])' + NL)
    for v, name in VOWELS.items():
        doc.append(f"#text(size: 8pt, fill: gray)[{name}]" + NL)
        doc.append(pair(" ".join(c + chr(v) + chr(METEG) for c in LETTERS), "30pt"))
    doc.append("== 2. Words where the original meteg touches its vowel" + NL)
    doc.append('#grid(columns: (1fr, 1fr), gutter: 6pt, align: center, [*Frank Ruehl CLM (original)*], [*Sofer*])' + NL)
    for w, lo, hi, aft, _k in touching:
        doc.append(pair(w, "26pt"))
    doc.append("== 3. Words where the original meteg is furthest from its vowel" + NL)
    doc.append("The gap in em, before -> after, under each pair." + NL)
    doc.append('#grid(columns: (1fr, 1fr), gutter: 6pt, align: center, [*Frank Ruehl CLM (original)*], [*Sofer*])' + NL)
    for w, lo, hi, aft, _k in far:
        doc.append(pair(w, "26pt"))
        a = max(aft) if aft else 0
        doc.append(f"#align(center, text(size: 8pt, fill: gray)[{hi:.3f} -> {a:.3f}])" + NL)
    doc.append("== Known side effect" + NL)
    doc.append("Where a meteg beside a wide vowel would reach the next letter, place_meteg.py sets the letters "
               "a little apart for the widest vowel that letter could have; in Frank Ruehl that leaves visible "
               "gaps inside some words (e.g. after the first letter of מִזְמֽוֹר). Sofer now prints text with "
               "nikud in its own fonts, so this was not refined further in Frank Ruehl." + NL)
    src = tmp / "meteg.typ"
    src.write_text("".join(doc), encoding="utf-8")
    Path(out_pdf).write_bytes(typst.compile(str(src), font_paths=[str(tmp), str(REPO / "fonts")]))
    print(f"{out_pdf}: {n_all} words with a meteg; far {n_far}, touching {n_touch}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
