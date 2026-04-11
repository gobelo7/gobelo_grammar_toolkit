"""
ggt_loader_adapter.py — GGTLoaderAdapter
=========================================
Wraps a raw GGT YAML grammar dict and exposes exactly the interface
expected by GobeloWordTokenizer and GobelloMorphAnalyser.

Usage
-----
    import yaml
    from ggt_loader_adapter import GGTLoaderAdapter
    from word_tokenizer import GobeloWordTokenizer
    from morph_analyser import GobelloMorphAnalyser

    with open("chibemba.yaml") as f:
        grammar = yaml.safe_load(f)

    loader = GGTLoaderAdapter(grammar, lang_iso="bem")
    tok    = GobeloWordTokenizer(loader)
    ana    = GobelloMorphAnalyser(loader)

    sentence = tok.tokenize("Balima amasaka.")
    sentence = ana.analyse(sentence)
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

__all__ = ["GGTLoaderAdapter"]

_SKIP_EMPTY = {"Ø", "ø", "∅", "-", "", "null"}

def _to_list(value: Any) -> List[str]:
    if value is None: return []
    if isinstance(value, str): return [value] if value else []
    if isinstance(value, list): return [str(v) for v in value if v is not None]
    return [str(value)]

def _strip_h(form: str) -> str:
    return form.strip("-")


class GGTLoaderAdapter:
    """
    Adapter from GGT YAML structure to the GobeloWordTokenizer /
    GobelloMorphAnalyser loader interface.

    Parameters
    ----------
    grammar     : dict from yaml.safe_load(ggt_yaml_file)
    lang_iso    : ISO 639-3 code, e.g. "bem", "loz"
    lexicon_verb: optional {root: LexiconEntry}
    lexicon_noun: optional {stem: LexiconEntry}
    """

    def __init__(
        self,
        grammar: Dict[str, Any],
        lang_iso: str = "und",
        lexicon_verb: Optional[Dict] = None,
        lexicon_noun: Optional[Dict] = None,
    ) -> None:
        self._g           = grammar
        self.lang_iso     = lang_iso
        self.grammar      = grammar
        self.lexicon_verb = lexicon_verb or {}
        self.lexicon_noun = lexicon_noun or {}
        self._cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    def get(self, key: str, default: Any = None) -> Any:
        if key not in self._cache:
            self._cache[key] = self._resolve(key, default)
        return self._cache[key]

    def _resolve(self, key: str, default: Any) -> Any:
        dispatch = {
            "phonology.vowels_nfc"        : self._vowels,
            "phonology.tone_marks"        : lambda: [],
            "engine_features"             : self._engine_features,
            "clitics"                     : self._clitics,
            "morphology.subject_markers"  : self._subject_markers,
            "morphology.object_markers"   : self._object_markers,
            "morphology.tense_aspect"     : self._tense_aspect,
            "morphology.final_vowels"     : self._final_vowels,
            "morphology.extensions"       : self._extensions,
            "morphology.noun_classes"     : self._noun_classes,
            "morphology.negation"         : self._negation,
            "morphology.augment"          : self._augment,
        }
        fn = dispatch.get(key)
        return fn() if fn else default

    # ── Phonology ──────────────────────────────────────────────────────
    def _vowels(self) -> List[str]:
        ph = self._g.get("phonology", {})
        vb = ph.get("vowels", {})
        segs = _to_list(vb.get("segments", [])) if isinstance(vb, dict) else _to_list(vb)
        return [v for v in segs if len(v) == 1]

    def _engine_features(self) -> Dict[str, Any]:
        ef = self._g.get("phonology", {}).get("engine_features", {})
        result: Dict[str, Any] = {}
        if isinstance(ef, dict):
            for k, v in ef.items():
                result[k] = v.get("default", False) if isinstance(v, dict) else bool(v)
        ncs = self._g.get("noun_class_system", {}).get("noun_classes", {})
        result["augment"] = any(
            isinstance(v, dict)
            and isinstance(v.get("augment"), dict)
            and v["augment"].get("usage") not in ("not_applicable", None)
            and v["augment"].get("form")
            for v in ncs.values()
        )
        return result

    # ── Clitics ────────────────────────────────────────────────────────
    def _clitics(self) -> Dict[str, List[str]]:
        tok = self._g.get("tokenization", {})
        cl  = tok.get("clitics", {}) if isinstance(tok, dict) else {}
        if isinstance(cl, dict):
            return {"proclitics": _to_list(cl.get("proclitics", [])),
                    "enclitics":  _to_list(cl.get("enclitics", []))}
        return {"proclitics": [], "enclitics": []}

    # ── Concord tables ─────────────────────────────────────────────────
    def _subject_markers(self) -> Dict[str, Dict]:
        return self._concord_table(
            self._g.get("concord_system",{}).get("concords",{}).get("subject_concords",{})
        )

    def _object_markers(self) -> Dict[str, Dict]:
        return self._concord_table(
            self._g.get("concord_system",{}).get("concords",{}).get("object_concords",{})
        )

    def _concord_table(self, raw: Dict) -> Dict[str, Dict]:
        SKIP = {"description", "position", "note", "notes"}
        result: Dict[str, Dict] = {}
        for k, entry in raw.items():
            if k in SKIP or not isinstance(entry, dict): continue
            forms = _to_list(entry.get("forms") or entry.get("form") or [])
            allo  = entry.get("allomorphs", {})
            if isinstance(allo, dict):
                forms += _to_list(allo.get("forms", []))
            forms = list(dict.fromkeys(
                _strip_h(f) for f in forms if f not in _SKIP_EMPTY
            ))
            if not forms: continue
            result[k] = {"form": forms, "gloss": entry.get("gloss", k)}
        return result

    # ── TAM ────────────────────────────────────────────────────────────
    def _tense_aspect(self) -> Dict[str, Dict]:
        raw = (self._g.get("verb_system",{})
                      .get("verbal_system_components",{})
                      .get("tam",{}))
        result: Dict[str, Dict] = {}
        for k, e in raw.items():
            if not isinstance(e, dict): continue
            forms = [_strip_h(f) for f in _to_list(e.get("forms") or e.get("form") or [])
                     if f not in _SKIP_EMPTY]
            if forms:
                result[k] = {"form": forms, "gloss": e.get("gloss", k)}
        return result

    # ── Final vowels ───────────────────────────────────────────────────
    def _final_vowels(self) -> Dict[str, Dict]:
        raw = (self._g.get("verb_system",{})
                      .get("verbal_system_components",{})
                      .get("final_vowels",{}))
        result: Dict[str, Dict] = {}
        for name, e in raw.items():
            if isinstance(e, str):
                f = _strip_h(e)
                if f: result[name] = {"form": f, "gloss": f"FV.{name.upper()}"}
            elif isinstance(e, dict):
                raw_f = e.get("forms") or e.get("form") or ""
                f = _strip_h(str(raw_f))
                if f: result[name] = {"form": f, "gloss": e.get("gloss", f"FV.{name.upper()}")}
        return result

    # ── Extensions ─────────────────────────────────────────────────────
    def _extensions(self) -> Dict[str, Dict]:
        SKIP = {"extension_ordering", "semantic_composition"}
        ZONE_SLOT = {"Z1":"SLOT6","Z2":"SLOT7","Z3":"SLOT8","Z4":"SLOT9"}
        raw = (self._g.get("verb_system",{})
                      .get("verbal_system_components",{})
                      .get("derivational_extensions",{}))
        result: Dict[str, Dict] = {}
        for k, e in raw.items():
            if k in SKIP or not isinstance(e, dict): continue
            forms = [_strip_h(f) for f in _to_list(e.get("form") or [])
                     if f not in _SKIP_EMPTY]
            if not forms: continue
            zone = str(e.get("zone","Z1"))
            result[k] = {"form": forms, "gloss": e.get("gloss",k),
                         "zone": zone, "slot": ZONE_SLOT.get(zone,"SLOT6")}
        return result

    # ── Noun classes ───────────────────────────────────────────────────
    def _noun_classes(self) -> Dict[str, Dict]:
        raw = (self._g.get("noun_class_system",{}).get("noun_classes",{}))
        result: Dict[str, Dict] = {}
        for nc_key, e in raw.items():
            if not isinstance(e, dict): continue
            pb = e.get("prefix", {})
            if isinstance(pb, dict):
                canonical = _strip_h(pb.get("canonical_form",""))
                allos = [_strip_h(a.get("form",""))
                         for a in (pb.get("allomorphs",[]) or [])
                         if isinstance(a, dict) and a.get("form")]
            elif isinstance(pb, str):
                canonical, allos = _strip_h(pb), []
            else:
                continue
            forms = list(dict.fromkeys(
                f for f in [canonical]+allos if f and f not in _SKIP_EMPTY
            ))
            if not forms: continue
            sem = e.get("semantics", {})
            gloss = sem.get("primary_domain", nc_key) if isinstance(sem, dict) else nc_key
            result[nc_key] = {"prefix": forms, "gloss": gloss,
                              "sg_class": nc_key, "pl_class": e.get("paired_class"),
                              "active": e.get("active", True)}
        return result

    # ── Negation ───────────────────────────────────────────────────────
    def _negation(self) -> Dict[str, Dict]:
        raw = (self._g.get("verb_system",{})
                      .get("verbal_system_components",{})
                      .get("negation_pre",{}))
        result: Dict[str, Dict] = {}
        for k, e in raw.items():
            if not isinstance(e, dict): continue
            forms = [_strip_h(f) for f in _to_list(e.get("forms",[])) if f not in _SKIP_EMPTY]
            if forms:
                result[k] = {"form": forms, "pre_form": forms, "gloss": e.get("gloss","NEG")}
        return result

    # ── Augment ────────────────────────────────────────────────────────
    def _augment(self) -> Dict[str, Dict]:
        raw = self._g.get("noun_class_system",{}).get("noun_classes",{})
        seen: Dict[str, str] = {}
        for e in raw.values():
            if not isinstance(e, dict): continue
            aug = e.get("augment", {})
            if not isinstance(aug, dict): continue
            if aug.get("usage") in ("not_applicable", None): continue
            f = aug.get("form")
            if isinstance(f, str):
                stripped = _strip_h(f)
                if stripped and stripped not in _SKIP_EMPTY:
                    seen[stripped] = "AUG"
        return {f: {"form": f, "gloss": "AUG"} for f in seen}

    # ── Diagnostics ────────────────────────────────────────────────────
    def describe(self) -> str:
        sm  = self.get("morphology.subject_markers", {})
        om  = self.get("morphology.object_markers",  {})
        tam = self.get("morphology.tense_aspect",    {})
        fv  = self.get("morphology.final_vowels",    {})
        ext = self.get("morphology.extensions",      {})
        nc  = self.get("morphology.noun_classes",    {})
        neg = self.get("morphology.negation",        {})
        ef  = self.get("engine_features",            {})
        aug = self.get("morphology.augment",         {})
        return "\n".join([
            f"GGTLoaderAdapter  lang={self.lang_iso!r}",
            f"  subject markers   : {len(sm)}",
            f"  object markers    : {len(om)}",
            f"  TAM markers       : {len(tam)}",
            f"  final vowels      : {len(fv)}",
            f"  extensions        : {len(ext)}",
            f"  noun classes      : {len(nc)}",
            f"  negation contexts : {len(neg)}",
            f"  augment forms     : {sorted(aug)}",
            f"  engine.augment    : {ef.get('augment')}",
            f"  engine.H_spread   : {ef.get('extended_H_spread')}",
            f"  verb lexicon      : {len(self.lexicon_verb)} roots",
            f"  noun lexicon      : {len(self.lexicon_noun)} stems",
        ])

    def __repr__(self) -> str:
        return f"GGTLoaderAdapter(lang={self.lang_iso!r})"
