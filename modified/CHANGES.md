# What Sofer changed in other projects' fonts

These are fonts Sofer prints with that come from other projects (Culmus, Google Noto, the David Libre
project, DejaVu), with Sofer's changes. Each keeps its own name and its own licence (`../licenses/`);
none of these licences reserves the name for the unchanged font. The scripts are in
`../build-scripts/`. Everything was checked with HarfBuzz, which shapes text as browsers and Typst do.

## The changes

| | Change | Script | Date |
|---|---|---|---|
| A | **Kamatz katan** (U+05C7) drawn with a bolder drop, so it is easy to tell from a kamatz gadol (a teardrop out of a flat stem, or a fuller ball, depending on the font's style) | `add_qamats_qatan.py` | 2026-10-20 |
| B | **Shva na** (U+05C8, Unicode 2026): the shva's two dots drawn as small squares, 15% bigger than the dot so it is seen at a glance; a shva followed by U+FB1E also gives it | `add_shva_na.py` | 2026-10-21, 2026-10-28 |
| C | **Dagesh chazak** (U+05C9, Unicode 2026): the dagesh drawn as a square at the dot's own size, in every letter | `add_dagesh_hazaq.py` | 2026-10-21 |
| D | **Meteg beside its vowel**: set 0.045 em to the left of the vowel under the same letter (the gap Taamey D, Keter YG and the Taamey fonts keep), at the height the font gives it; alone, in the middle under a letter with no vowel; beside a leg (ק) on the vowel's left, the vowel moved right to make room. Where the meteg would reach the next letter, the letters are set apart (not in the fonts marked "no spacing") | `place_meteg.py` | 2026-10-25 |
| E | **No meteg touching anything** over every word of Tanach and the siddurim: the marks under one letter set in a row (vowel, meteg, second vowel), then a rule for each meteg still touching, moving it aside or down | `clear_meteg.py` | 2026-10-25/26 |
| F | **ק's vowels** centred between its leg and its right edge, and not raised beside the leg before a meteg | `fix_keter_qof.py` | 2026-10-25 |
| G | **ק's leg parted from its roof** (it was drawn joined), its top cut on the slant of the leg's bottom | `fix_david_qof.py` | 2026-10-21 |
| H | **Every glyph's left bearing equal to its outline's left edge** (Chrome and Android place an outline by its bearing; PDFs do not - marks were drawn aside in browsers) | `fix_lsb.py` | 2026-11-16 |

## Which font got which

| Font | Files | Changes |
|---|---|---|
| Frank Ruehl CLM (Culmus) | `FrankRuehlCLM-Medium`, `-Bold`, `-MediumOblique`, `-BoldOblique` | A B C D H |
| Keter YG (Culmus) | `KeterYG-Medium`, `-Bold` | A B C D (no spacing) E H |
| Keter YG oblique (Culmus) | `KeterYG-MediumOblique`, `-BoldOblique` | A B C D H |
| Simple CLM (Culmus) | `SimpleCLM-Medium`, `-Bold`, `-MediumOblique`, `-BoldOblique` | A B C D H |
| Shofar (Culmus) | `ShofarRegular` | A B C D (no spacing) E H |
| Shofar Demi Bold (Culmus) | `ShofarDemi-Bold` | A B C E H |
| Taamey Ashkenaz (Culmus) | `TaameyAshkenaz-Medium`, `-Bold` | A B C D (no spacing) E H |
| Taamey David CLM (Culmus) | `TaameyDavidCLM-Medium`, `-Bold` | A B C D (no spacing) E H |
| Keter Aram Tsova | `KeterAramTsova` | A B C D (no spacing) E F H |
| Noto Rashi Hebrew (Google) | `NotoRashiHebrew-Regular`, `-Bold` | A B C D H |
| Noto Serif Hebrew (Google) | `NotoSerifHebrew-Regular`, `-Bold` | A B C D H |
| David Libre | `DavidLibre-Regular`, `-Bold` | A B C D G H |
| DejaVu Sans | `DejaVuSans` | H |

A known side effect of D in the fonts that are spaced (Frank Ruehl CLM above all): letters set apart for
the widest vowel the next letter could have leave visible gaps inside some words (e.g. after the first
letter of מִזְמֽוֹר). Sofer prints text with nikud in its own fonts, so this was not refined further.
`../docs/frank-ruehl-meteg.pdf` shows the meteg in Frank Ruehl CLM before and after.
