"""GPOS made savable however many rules it holds (2026-11-17: Drugulin's thousands of collision rules
outgrew the font format's 16-bit offsets, and fontTools could not save it - "OTLOffsetOverflowError"):

* a lookup of more than MAX_SUBTABLES subtables is split: the rest go into new lookups at the end, listed
  in every feature the first is in (the collision rules only add to a glyph's position or advance, and
  which of them apply depends on the glyphs alone, so their order does not matter);
* every lookup stored as an extension lookup (type 9), its subtables reached by 32-bit offsets.

The same rules, the same shaping."""
from __future__ import annotations

from fontTools.ttLib.tables import otTables as ot

MAX_SUBTABLES = 250


def as_extensions(font) -> None:
    if "GPOS" not in font:
        return
    gpos = font["GPOS"].table
    lookups = gpos.LookupList.Lookup
    for i in range(len(lookups)):
        lk = lookups[i]
        if len(lk.SubTable) <= MAX_SUBTABLES:
            continue
        rest, lk.SubTable = lk.SubTable[MAX_SUBTABLES:], lk.SubTable[:MAX_SUBTABLES]
        lk.SubTableCount = len(lk.SubTable)
        while rest:
            part = ot.Lookup()
            part.LookupType, part.LookupFlag = lk.LookupType, lk.LookupFlag
            if hasattr(lk, "MarkFilteringSet"):
                part.MarkFilteringSet = lk.MarkFilteringSet
            part.SubTable, rest = rest[:MAX_SUBTABLES], rest[MAX_SUBTABLES:]
            part.SubTableCount = len(part.SubTable)
            lookups.append(part)
            for fr in gpos.FeatureList.FeatureRecord:
                if i in fr.Feature.LookupListIndex:
                    fr.Feature.LookupListIndex.append(len(lookups) - 1)
                    fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    gpos.LookupList.LookupCount = len(lookups)
    for lk in lookups:
        if lk.LookupType == 9:
            continue
        subs = []
        for st in lk.SubTable:
            e = ot.ExtensionPos()
            e.Format, e.ExtensionLookupType, e.ExtSubTable = 1, lk.LookupType, st
            subs.append(e)
        lk.LookupType, lk.SubTable, lk.SubTableCount = 9, subs, len(subs)
