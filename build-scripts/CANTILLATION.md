# Cantillation marks: where each sits

Mordy's reference (2026-10-21), from his research: the ta'amim are divided into nine classes by
where they sit on their letter. Any font Sofer uses or builds (Frank Sofer, the Sefer Torah
fonts, a font whose kamatz katan is redrawn) must keep each ta'am in its place.
`scripts/check_font_marks.py` checks this for every bundled font (also run by the tests and
after a font update).

## The table as given

| Class | Where | Unicode |
|---|---|---|
| CANT1 | Above left | U+0599, U+05A1, U+05A9, U+05AE |
| CANT2 | Above centre left | U+0597, U+05A8, U+05AC |
| CANT3 | Above centre | U+0592 - U+0595, U+05A7, U+05AB |
| CANT4 | Above centre right | U+0598, U+059C, U+059E, U+059F |
| CANT5 | Above right | U+059D, U+05A0 |
| CANT6 | Below left | (contextually mapped) |
| CANT7 | Below centre left | U+0591, U+05A3, U+05A6 |
| CANT8 | Below centre right | U+0596, U+05A4, U+05AA |
| CANT9 | Below right | (contextually mapped) |

## Checked against Unicode's names (what the check uses)

A few entries above do not match Unicode, and seven ta'amim are missing:

- **U+05A7 is darga, which goes below the letter**, not above (CANT3).
- **U+05A1 is pazer**, which sits above its letter, not at the left edge with the postpositive
  marks (CANT1).
- Missing: U+059A **yetiv** and U+05AD **dehi** (below right, prepositive - CANT9), U+059B
  **tevir**, U+05A2 **atnah hafukh**, U+05A5 **merkha** (below), U+05AF masora circle (above).

The check groups the marks by what can be tested on a single letter:

| Group | Rule | Ta'amim (Unicode) |
|---|---|---|
| Above, left edge (postpositive) | over the letter's left edge or past it | pashta 0599, telisha qetana 05A9, zinor 05AE |
| Above, right edge (prepositive) | over the letter's right edge or past it | geresh muqdam 059D, telisha gedola 05A0 |
| Above | above the letter, over it | segol 0592, shalshelet 0593, zaqef qatan 0594, zaqef gadol 0595, revia 0597, zarqa 0598, geresh 059C, gershayim 059E, qarney para 059F, pazer 05A1, qadma 05A8, ole 05AB, iluy 05AC |
| Below | under the letter, under it | etnahta 0591, tipeha 0596, tevir 059B, atnah hafukh 05A2, munah 05A3, mahapakh 05A4, merkha 05A5, merkha kefula 05A6, darga 05A7, yerah ben yomo 05AA |
| Below, right edge (prepositive) | under the letter's right edge or past it | yetiv 059A, dehi 05AD |

(The finer left / centre / right positions within "above" and "below" depend on the letter and
the marks around it - the fonts' own layout logic decides them - so they are not checked.)
