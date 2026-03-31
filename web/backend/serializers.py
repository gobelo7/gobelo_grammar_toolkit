"""
web/backend/serializers.py — Response serialisation helpers.

Extracted from app.py. All functions are pure (no Flask imports, no side effects).
"""
from __future__ import annotations
from typing import Any, Dict

from cache import get_mapper


def ser_morpheme(m) -> Dict[str, Any]:
    return {
        "form":         m.form,
        "slot_id":      m.slot_id,
        "slot_name":    m.slot_name,
        "content_type": m.content_type,
        "gloss":        m.gloss,
        "nc_id":        m.nc_id,
    }


def ser_hyp(h) -> Dict[str, Any]:
    return {
        "segmented":  h.segmented,
        "gloss_line": h.gloss_line,
        "confidence": round(h.confidence, 4),
        "morphemes":  [ser_morpheme(m) for m in h.morphemes],
        "warnings":   list(h.warnings),
    }


def ser_ud(ud, mp) -> Dict[str, Any]:
    return {
        "tense":        ud.tense,
        "aspect":       ud.aspect,
        "mood":         ud.mood,
        "voice":        ud.voice,
        "nounclass":    ud.nounclass,
        "number":       ud.number,
        "person":       ud.person,
        "polarity":     ud.polarity,
        "feats_string": mp.to_conllu_feats(ud),
        "warnings":     list(ud.warnings),
    }


def ser_token(tok, lang: str) -> Dict[str, Any]:
    mp = get_mapper(lang)
    ud = mp.map_segmented_token(tok)
    b  = tok.best
    return {
        "token":            tok.token,
        "language":         tok.language,
        "is_ambiguous":     tok.is_ambiguous,
        "hypothesis_count": len(tok.hypotheses),
        "best":             ser_hyp(b) if b else None,
        "all_hypotheses":   [ser_hyp(h) for h in tok.hypotheses[:5]],
        "ud_features":      ser_ud(ud, mp),
    }


def ser_paradigm(table, gen, fmt: str):
    if fmt == "csv":      return gen.to_csv(table)
    if fmt == "markdown": return gen.to_markdown(table)
    if fmt == "html":     return gen.to_html(table)
    cells = {
        f"{r}|{c}": {
            "surface":   cell.surface,
            "segmented": cell.segmented,
            "gloss":     cell.gloss,
            "warnings":  list(cell.warnings),
        }
        for (r, c), cell in table.cells.items()
    }
    return {
        "root":          table.root,
        "language":      table.language,
        "paradigm_type": table.paradigm_type,
        "rows":          list(table.rows),
        "columns":       list(table.columns),
        "cells":         cells,
        "metadata":      table.metadata,
    }
