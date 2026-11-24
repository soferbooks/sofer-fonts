"""Clear the meteg in particular words of one font (Antigravity, 2026-11-24: Mekorot Rashi had one word left,
מ׈צַו׉ֶֽך׉ָ׃ - a shva na, dagesh chazak and a meteg touching - after the dehi step; ported from its
_fix_rashi_meteg.py).  The word is given as text; clear_meteg.clear() adds the rule and the bearings are put
right.  Then check with scripts/check_meteg.py.

    .venv/Scripts/python scripts/clear_meteg_words.py <font.ttf> <word> [<word> ...]
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import clear_meteg  # noqa: E402
import fix_lsb  # noqa: E402

# Mekorot Rashi's remaining word (2026-11-24)
RASHI_WORD = "מ׈צַו׉ֶֽך׉ָ׃"

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    font = Path(sys.argv[1])
    words = Counter({w: 1 for w in sys.argv[2:]})
    if not words:
        raise SystemExit(__doc__)
    print("clear_meteg:", clear_meteg.clear(font, words, rounds=5), flush=True)
    print("bearings fixed:", fix_lsb.fix(font), flush=True)
