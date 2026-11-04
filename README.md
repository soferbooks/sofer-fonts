# Sofer fonts

Hebrew fonts for printing sefarim with full nikud and ta'amim, made for
[Sofer](https://soferbooks.com), which prints custom sefarim to order. Free to use, share and change
under the GNU GPL version 2 with the font exception (see "Licence" below).

| Font | File | What it is |
|---|---|---|
| **Frank Sofer** | `fonts/FrankSofer.ttf` | A classic Frank Ruehl-style book face with nikud and ta'amim, every mark in its place |
| **Frank Sofer Bold** | `fonts/FrankSofer-Bold.ttf` | Its bold |
| **Sofer Stam Ashkenaz** | `fonts/SoferStamAshkenaz.ttf` | Ashkenazi Sefer Torah script **with nikud and ta'amim** |
| **Sofer Stam Sefarad** | `fonts/SoferStamSefarad.ttf` | Sefardi Sefer Torah script **with nikud and ta'amim** |

## What is special about them

- **No collisions.** Every word of Tanach (the Miqra according to the Masorah text) and of the
  siddurim (the Wikitext Sefardi siddur and Sefaria's siddurim) was shaped in each font and checked: no vowel, ta'am or meteg touches a letter or another mark. In the Sefer Torah
  fonts the marks are kept clear of the crowns (tagin) and of the letters' tails.
- **Each ta'am in its proper place**, including the prepositive and postpositive ones
  (`build-scripts/CANTILLATION.md` lists where each one sits; `check_font_marks.py` checks it).
- **Shva na and dagesh chazak** (Unicode U+05C8 and U+05C9, approved 2026): drawn as the dot made
  square, at the dot's own size. A shva followed by U+FB1E also gives the shva na.
- **Kamatz katan** (U+05C7) with a bolder drop, so it is easy to tell from a kamatz gadol, and the
  chataf kamatz drawn the same way (all but Sofer Stam Sefarad).
- **Vowels placed by each letter's shape**: centred in the opening of ה ח ת, under the foot of ט ש,
  under the leg of ר ד, beside the leg of ק, with the meteg set right beside its vowel.
- **Sefer Torah script with nikud**: the Stam fonts are the same height as Frank Sofer's letters
  (crowns not counted), so they can be mixed on one page - e.g. Shnayim Mikra, the pasuk in
  Sefer Torah script and then in regular letters.

## Where they come from (credits)

- **Frank Sofer** is Ben Denckla's **Taamey D** 0.931
  ([hbofonts](https://bdenckla.github.io/hbofonts/)), whose letters come from Yoram Gnat's
  **Taamey Frank CLM** (Culmus). It is renamed because Taamey D's licence reserves that name. Our
  changes: the marks under the line raised closer to the letter, the placements above, the kamatz
  katan, the shva na and dagesh chazak, and the bold.
- **Sofer Stam Ashkenaz / Sefarad** take their letters from Yoram Gnat's **Stam Ashkenaz CLM** and
  **Stam Sefarad CLM** ([Culmus](https://culmus.sourceforge.io)), and their nikud, ta'amim and mark
  placement from Frank Sofer, with every mark moved clear of the Stam letters' shapes.

The original copyright notices are in `licenses/`.

## Licence

GNU General Public License version 2 (`LICENSE`), **with the font exception**: you may embed these
fonts in a document (a PDF, a printed book) without that document falling under the GPL. If you
change a font and share it, share your changes under the same licence, and give it another name if
you start from Frank Sofer (Taamey D's reserved name).

> As a special exception, if you create a document which uses this font, and embed this font or
> unaltered portions of this font into the document, this font does not by itself cause the
> resulting document to be covered by the GNU General Public License. This exception does not
> however invalidate any other reasons why the document might be covered by the GNU General Public
> License. If you modify this font, you may extend this exception to your version of the font, but
> you are not obligated to do so. If you do not wish to do so, delete this exception statement from
> your version.

## The build scripts

`build-scripts/` holds the Python scripts (fontTools, HarfBuzz) that make these fonts from their
sources: `make_frank_sofer.py` (from Taamey D), `make_bold.py`, `make_stam_sefarad.py` (from the
Culmus Stam fonts; `--ashkenaz` for the Ashkenazi one), and the steps they run (`add_shva_na.py`,
`add_dagesh_hazaq.py`, `add_qamats_qatan.py`, `place_meteg.py`, `clear_meteg.py`,
`check_font_marks.py`). They are copied from the Sofer project as they are, so they expect its
folders (and, for the collision search over Tanach and the siddurim, its text library); they are here so every change
to the fonts can be seen and repeated.
