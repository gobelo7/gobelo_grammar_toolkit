"""
morph_analyser.py — GobelloMorphAnalyser  (GGT Phase 2)
=========================================================
Language-agnostic morphological analyser for the Gobelo Grammar Toolkit.

Takes an AnnotatedSentence produced by GobeloWordTokenizer and enriches
each WordToken with:

  * A ranked list of SlotParse hypotheses (verb tokens)
  * Noun-class identification (noun tokens)
  * UD morphological features (feats dict) from the best parse
  * Populated MorphemeSpan objects for character-level annotation
  * Confirmed LexiconEntry matches (replaces Phase 1 stub hits)
  * Updated upos / lemma / is_oov on each token

All language-specific knowledge comes exclusively from the GGT YAML grammar
file (via GobeloGrammarLoader) and the LexiconEntry dicts it exposes.
No language-specific logic lives in this file.

Architecture
------------
The analyser works in two passes per sentence:

  Pass A · Verb analysis   (GobeloVerbParser)
        For every WORD / CLITIC / UNKNOWN token:
          1. Strip augment (if language has one)
          2. Try all SM prefixes  →  remainder fed to TAM stripper
          3. Try all TAM prefixes  →  remainder fed to OM stripper
          4. Try all OM prefixes   →  remainder = root + extensions + FV
          5. Match remainder against lexicon roots
          6. Strip extensions (appl, caus, recip, pass, neuter, revers)
          7. Identify final vowel
          8. Score hypothesis; keep top-N

  Pass B · Noun analysis   (GobeloNounAnalyser)
        For tokens not successfully verb-parsed:
          1. Try all NC prefixes from the YAML noun_classes table
          2. Augment stripping if applicable
          3. Match stem against noun lexicon
          4. Assign noun_class; build MorphemeSpan

Scoring
-------
Each hypothesis carries a float score in [0.0, 1.0]:

  + 0.40  lexicon root hit (SLOT8 confirmed)
  + 0.20  SM concord confirmed against NC of a nearby noun (deferred)
  + 0.15  full FV identified (SLOT11)
  + 0.10  TAM prefix identified (SLOT4)
  + 0.05  OM identified (SLOT7)
  + 0.05  extension zone identified (SLOT9)
  + 0.05  surface reconstruction matches token form exactly

  Maximum score without concord: 0.80  (concord = Phase 3 context layer)

GobeloGrammarLoader interface assumed
--------------------------------------
The analyser calls the following on the loader object:

  loader.lang_iso                          : str
  loader.grammar                           : dict  (raw YAML)
  loader.lexicon_verb                      : dict[str, LexiconEntry]
  loader.lexicon_noun                      : dict[str, LexiconEntry]
  loader.get("phonology.vowels_nfc", [])   : list[str]
  loader.get("phonology.tone_marks", [])   : list[str]
  loader.get("engine_features", {})        : dict
  loader.get("morphology.subject_markers", {})   : dict   NC → SM form(s)
  loader.get("morphology.tense_aspect", {})      : dict   TAM key → data
  loader.get("morphology.object_markers", {})    : dict   NC → OM form(s)
  loader.get("morphology.final_vowels", {})      : dict   name → form
  loader.get("morphology.extensions", {})        : dict   ext key → data
  loader.get("morphology.noun_classes", {})      : dict   NCn → data
  loader.get("morphology.negation", {})          : dict
  loader.get("morphology.augment", {})           : dict   (if applicable)

Usage
-----
    loader = GobeloGrammarLoader("toi")
    cfg    = CorpusConfig.load("corpus_config.yaml")
    tok    = GobeloWordTokenizer(loader, cfg)
    ana    = GobelloMorphAnalyser(loader)

    sentence = tok.tokenize("Bakali balima.")
    sentence = ana.analyse(sentence)

    for token in sentence.word_tokens():
        if token.best_slot_parse:
            print(token.form, "→", token.best_slot_parse.gloss_string())
        elif token.noun_class:
            print(token.form, "→ NC:", token.noun_class)
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from models import (
    AnnotatedSentence,
    ConfidenceLevel,
    LexiconCategory,
    LexiconEntry,
    MorphemeSpan,
    POSTag,
    SlotFill,
    SlotParse,
    TokenType,
    WordToken,
)


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

VERSION = "2.0.0"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _lower_nfc(s: str) -> str:
    return _nfc(s.lower())


def _confidence(hit: bool) -> ConfidenceLevel:
    return ConfidenceLevel.HIGH if hit else ConfidenceLevel.MEDIUM


# ---------------------------------------------------------------------------
# Null loader stub  (for unit-testing without real YAML)
# ---------------------------------------------------------------------------

class _NullLoader:
    """Minimal stub — returns empty structures for all grammar keys."""
    lang_iso     = "und"
    grammar      : Dict = {}
    lexicon_verb : Dict = {}
    lexicon_noun : Dict = {}

    def get(self, key: str, default: Any = None) -> Any:
        return default


# ---------------------------------------------------------------------------
# AnalyserConfig  — pre-computed tables built once from the loader
# ---------------------------------------------------------------------------

@dataclass
class _AnalyserConfig:
    """Pre-computed, language-specific analysis tables.

    All fields are plain Python dicts / lists / sets so the inner loop
    never touches YAML objects.
    """
    lang_iso: str

    # ---- Phonology ----
    vowels    : Set[str] = field(default_factory=set)
    tone_marks: Set[str] = field(default_factory=set)

    # ---- Engine flags ----
    has_augment      : bool = False
    extended_h_spread: bool = False

    # ---- Augment ----
    # form → morphological gloss   (e.g. "a" → "AUG")
    augment_forms: Dict[str, str] = field(default_factory=dict)

    # ---- Negation ----
    # prenegative forms that occupy SLOT2
    # e.g.  {"ha": "NEG.DISJ", "si": "NEG.PRE"}
    neg_preverbal : Dict[str, str] = field(default_factory=dict)   # form→gloss

    # ---- Subject Markers ----
    # NC → list[form]   (sorted longest-first for greedy matching)
    sm_table : Dict[str, List[str]] = field(default_factory=dict)
    # Reverse: form → [(NC, gloss)]   (one form may be ambiguous)
    sm_reverse: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)

    # ---- TAM prefixes ----
    # key → {"form": str|list, "gloss": str, "slot": "SLOT4"}
    tam_table   : Dict[str, Dict] = field(default_factory=dict)
    # Reverse: form → [(key, gloss)]
    tam_reverse : Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)

    # ---- Object Markers ----
    om_table   : Dict[str, List[str]] = field(default_factory=dict)
    om_reverse : Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)

    # ---- Final Vowels ----
    # name → form   (e.g. "indicative": "a", "perfective": "ile")
    fv_table  : Dict[str, str] = field(default_factory=dict)
    # Reverse: form → name  (sorted longest-first)
    fv_reverse: Dict[str, str] = field(default_factory=dict)

    # ---- Extensions (SLOT9 — single extension field, zones Z1-Z4 within) ----
    # key → {"form": str|list, "gloss": str, "zone": "Z1"|"Z2"|"Z3"|"Z4",
    #         "slot": "SLOT9"}
    ext_table   : Dict[str, Dict] = field(default_factory=dict)
    # Reverse: form → [(key, gloss, slot)]   longest-first
    ext_reverse : List[Tuple[str, str, str, str]] = field(default_factory=list)

    # ---- Noun Classes ----
    # NC key → {"prefix": str|list, "gloss": str, ...}
    nc_table : Dict[str, Dict] = field(default_factory=dict)
    # Reverse: prefix → [(NC, gloss)]   sorted longest-first
    nc_reverse: List[Tuple[str, str, str]] = field(default_factory=list)  # (prefix, NC, gloss)

    # ---- UD Feature mappings ----
    # TAM key → {UD feats dict}
    tam_ud_feats: Dict[str, Dict[str, str]] = field(default_factory=dict)


def _to_list(value) -> List[str]:
    """Normalise a YAML value that may be str or list[str] to a list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def _build_config(loader) -> _AnalyserConfig:
    """Construct an _AnalyserConfig from the loader's grammar."""
    cfg = _AnalyserConfig(lang_iso=getattr(loader, "lang_iso", "und"))

    # ---- Phonology --------------------------------------------------------
    vowels     = loader.get("phonology.vowels_nfc", []) or []
    tone_marks = loader.get("phonology.tone_marks", []) or []
    cfg.vowels      = set(vowels)
    cfg.tone_marks  = set(tone_marks)

    # ---- Engine features --------------------------------------------------
    eng = loader.get("engine_features", {}) or {}
    cfg.has_augment       = bool(eng.get("augment", False))
    cfg.extended_h_spread = bool(eng.get("extended_H_spread", False))

    # ---- Augment ----------------------------------------------------------
    aug_data = loader.get("morphology.augment", {}) or {}
    if isinstance(aug_data, dict):
        for nc_key, aug_info in aug_data.items():
            if isinstance(aug_info, dict):
                for f in _to_list(aug_info.get("form")):
                    cfg.augment_forms[_nfc(f)] = aug_info.get("gloss", "AUG")
            elif isinstance(aug_info, str):
                cfg.augment_forms[_nfc(aug_info)] = "AUG"

    # ---- Negation ---------------------------------------------------------
    neg_data = loader.get("morphology.negation", {}) or {}
    if isinstance(neg_data, dict):
        for key, info in neg_data.items():
            if isinstance(info, dict):
                for f in _to_list(info.get("form", info.get("pre_form"))):
                    cfg.neg_preverbal[_nfc(f)] = info.get("gloss", "NEG")
            elif isinstance(info, str):
                cfg.neg_preverbal[_nfc(info)] = "NEG"

    # ---- Subject Markers --------------------------------------------------
    sm_data = loader.get("morphology.subject_markers", {}) or {}
    if isinstance(sm_data, dict):
        for nc_key, sm_info in sm_data.items():
            forms: List[str] = []
            gloss = nc_key
            if isinstance(sm_info, dict):
                forms = _to_list(sm_info.get("form", sm_info.get("prefix", [])))
                gloss = sm_info.get("gloss", nc_key)
            elif isinstance(sm_info, str):
                forms = [sm_info]
            forms_nfc = [_nfc(f) for f in forms if f]
            if forms_nfc:
                cfg.sm_table[nc_key] = sorted(forms_nfc, key=len, reverse=True)
                for f in forms_nfc:
                    cfg.sm_reverse.setdefault(f, []).append((nc_key, gloss))

    # ---- TAM prefixes -----------------------------------------------------
    tam_data = loader.get("morphology.tense_aspect", {}) or {}
    _build_tam_tables(tam_data, cfg)

    # ---- Object Markers ---------------------------------------------------
    om_data = loader.get("morphology.object_markers", {}) or {}
    if isinstance(om_data, dict):
        for nc_key, om_info in om_data.items():
            forms: List[str] = []
            gloss = nc_key
            if isinstance(om_info, dict):
                forms = _to_list(om_info.get("form", om_info.get("prefix", [])))
                gloss = om_info.get("gloss", nc_key)
            elif isinstance(om_info, str):
                forms = [om_info]
            forms_nfc = [_nfc(f) for f in forms if f]
            if forms_nfc:
                cfg.om_table[nc_key] = sorted(forms_nfc, key=len, reverse=True)
                for f in forms_nfc:
                    cfg.om_reverse.setdefault(f, []).append((nc_key, gloss))

    # ---- Final Vowels -----------------------------------------------------
    fv_data = loader.get("morphology.final_vowels", {}) or {}
    if isinstance(fv_data, dict):
        for name, fv_info in fv_data.items():
            form = ""
            if isinstance(fv_info, dict):
                form = fv_info.get("form", "")
            elif isinstance(fv_info, str):
                form = fv_info
            if form:
                cfg.fv_table[name] = _nfc(form)
                cfg.fv_reverse[_nfc(form)] = name
    # Sort fv_reverse longest-first for greedy matching
    cfg.fv_reverse = dict(
        sorted(cfg.fv_reverse.items(), key=lambda kv: -len(kv[0]))
    )

    # ---- Extensions -------------------------------------------------------
    ext_data = loader.get("morphology.extensions", {}) or {}
    if isinstance(ext_data, dict):
        for key, ext_info in ext_data.items():
            if not isinstance(ext_info, dict):
                continue
            zone = str(ext_info.get("zone", "Z1")).upper()
            # All extensions occupy SLOT9 (single extension field) in v1 numbering
            slot = "SLOT9"
            gloss = ext_info.get("gloss", key)
            cfg.ext_table[key] = {
                "forms": _to_list(ext_info.get("form", [])),
                "gloss": gloss,
                "slot" : slot,
                "zone" : zone,
            }
            for f in _to_list(ext_info.get("form", [])):
                cfg.ext_reverse.append((_nfc(f), key, gloss, slot))
    # Sort longest-first so we always try longer extensions before shorter
    cfg.ext_reverse.sort(key=lambda t: -len(t[0]))

    # ---- Noun Classes -----------------------------------------------------
    nc_data = loader.get("morphology.noun_classes", {}) or {}
    if isinstance(nc_data, dict):
        for nc_key, nc_info in nc_data.items():
            if not isinstance(nc_info, dict):
                continue
            gloss = nc_info.get("gloss", nc_key)
            cfg.nc_table[nc_key] = nc_info
            # Collect prefix forms (singular prefix for noun matching)
            prefixes = _to_list(nc_info.get("prefix", nc_info.get("sg_prefix", [])))
            for p in prefixes:
                cfg.nc_reverse.append((_nfc(p), nc_key, gloss))
    # Sort longest prefix first (greedy)
    cfg.nc_reverse.sort(key=lambda t: -len(t[0]))

    # ---- TAM → UD feats mapping -------------------------------------------
    _build_ud_tam_feats(cfg)

    return cfg


def _build_tam_tables(tam_data: dict, cfg: _AnalyserConfig) -> None:
    """Flatten TAM data into cfg.tam_table and cfg.tam_reverse."""
    if not isinstance(tam_data, dict):
        return
    for key, info in tam_data.items():
        if not isinstance(info, dict):
            continue
        gloss = info.get("gloss", key)
        forms  = _to_list(info.get("form", info.get("prefix", [])))
        # Some YAML schemas nest sub-tenses; flatten them
        if not forms:
            for sub_key, sub_info in info.items():
                if isinstance(sub_info, dict) and "form" in sub_info:
                    sub_forms = _to_list(sub_info["form"])
                    sub_gloss = sub_info.get("gloss", f"{key}.{sub_key}")
                    full_key  = f"{key}.{sub_key}"
                    cfg.tam_table[full_key] = {
                        "forms": sub_forms,
                        "gloss": sub_gloss,
                    }
                    for f in sub_forms:
                        nf = _nfc(f)
                        cfg.tam_reverse.setdefault(nf, []).append((full_key, sub_gloss))
            continue
        cfg.tam_table[key] = {"forms": forms, "gloss": gloss}
        for f in forms:
            nf = _nfc(f)
            cfg.tam_reverse.setdefault(nf, []).append((key, gloss))


def _build_ud_tam_feats(cfg: _AnalyserConfig) -> None:
    """Populate cfg.tam_ud_feats from heuristic TAM key patterns."""
    # Cross-linguistic heuristics based on common Bantu TAM gloss patterns.
    # These are best-effort; the real mapping lives in the YAML gram file
    # under morphology.tense_aspect[key].ud_feats if present.
    for key, data in cfg.tam_table.items():
        gloss = data.get("gloss", "").upper()
        feats: Dict[str, str] = {}
        # Tense
        if any(x in gloss for x in ["PAST", "REMOTE", "HOD", "YEST"]):
            feats["Tense"] = "Past"
        elif any(x in gloss for x in ["FUT", "PROSP"]):
            feats["Tense"] = "Fut"
        elif any(x in gloss for x in ["PRES", "HAB"]):
            feats["Tense"] = "Pres"
        # Aspect
        if "PERF" in gloss:
            feats["Aspect"] = "Perf"
        elif "PROG" in gloss or "CONT" in gloss or "IMPERF" in gloss:
            feats["Aspect"] = "Prog"
        # Mood
        if "SUBJ" in gloss or "HORT" in gloss:
            feats["Mood"] = "Sub"
        elif "IMP" in gloss:
            feats["Mood"] = "Imp"
        elif "COND" in gloss:
            feats["Mood"] = "Cnd"
        cfg.tam_ud_feats[key] = feats


# ---------------------------------------------------------------------------
# Verb parser  — GobeloVerbParser
# ---------------------------------------------------------------------------

# Maximum number of distinct SlotParse hypotheses kept per token
_MAX_HYPOTHESES = 5


class GobeloVerbParser:
    """Left-to-right verb slot-filler for all seven GGT languages.

    The verb template is:

      SLOT1 · Augment / initial vowel
      SLOT2 · Negation prefix (pre-subject)
      SLOT3 · Subject concord (SM)
      SLOT4 · TAM marker (pre-root)
      SLOT5 · Relative / subordinator marker  (reserved)
      SLOT6 · Negation (post-subject)
      SLOT7 · Object concord (OM)
      SLOT8 · Verb root       (confirmed against lexicon)
      SLOT9 · Extension field (Z1-Z4)
      SLOT10· TAM marker (post-root / aspect)  (reserved)
      SLOT11· Final vowel

    The parser attempts a prefix-peeling strategy: at each slot position it
    tries all known prefixes (longest-match first).  When a slot is skipped,
    it branches: one hypothesis with the skip, one without.  The branching is
    bounded by _MAX_HYPOTHESES.

    Returns a list of SlotParse objects sorted by score descending.
    """

    def __init__(self, cfg: _AnalyserConfig, lexicon_verb: Dict[str, LexiconEntry]) -> None:
        self._cfg   = cfg
        self._verbs = lexicon_verb or {}

    def parse(self, form: str) -> List[SlotParse]:
        """Return ranked SlotParse hypotheses for *form* (NFC lower-cased)."""
        norm = _lower_nfc(form)
        hypotheses: List[SlotParse] = []

        # Try with and without SLOT2 (pre-subject negation prefix)
        starts: List[Tuple[str, int, Dict]] = [(norm, 0, {})]  # (remainder, pos, slots_so_far)
        for neg_form, neg_gloss in sorted(
            self._cfg.neg_preverbal.items(), key=lambda kv: -len(kv[0])
        ):
            if norm.startswith(neg_form) and len(norm) > len(neg_form):
                starts.append((norm[len(neg_form):], len(neg_form), {
                    "SLOT2": SlotFill(
                        form=neg_form,
                        gloss=neg_gloss,
                        source_rule=f"NEG:{neg_form}",
                        confidence=ConfidenceLevel.HIGH,
                        start=0,
                        end=len(neg_form),
                    )
                }))
                break  # only try one negation prefix per hypothesis start

        for remainder, base_pos, prior_slots in starts:
            hyps = self._parse_from_slot3(remainder, base_pos, dict(prior_slots))
            hypotheses.extend(hyps)

        # Deduplicate by surface form, keep highest-scored
        seen: Dict[str, SlotParse] = {}
        for h in hypotheses:
            key = h.surface()
            if key not in seen or h.score > seen[key].score:
                seen[key] = h

        result = sorted(seen.values(), key=lambda h: h.score, reverse=True)
        return result[:_MAX_HYPOTHESES]

    # ------------------------------------------------------------------
    def _parse_from_slot3(
        self, remainder: str, base_pos: int, prior_slots: Dict
    ) -> List[SlotParse]:
        """Try all SM prefixes (SLOT3) → TAM (SLOT4) → OM (SLOT7) → root+ext+FV."""
        results: List[SlotParse] = []

        sm_candidates: List[Tuple[str, str, str]] = []  # (sm_form, NC, gloss)

        for nc_key, forms in self._cfg.sm_table.items():
            for sm_form in forms:  # already sorted longest-first
                if remainder.startswith(sm_form) and len(remainder) > len(sm_form):
                    sm_candidates.append((sm_form, nc_key, self._sm_gloss(nc_key)))
                    break  # one form per NC

        if not sm_candidates:
            # No SM found — try treating the whole form as root+FV
            return self._parse_rootfv(remainder, base_pos, prior_slots, sm_nc=None)

        for sm_form, sm_nc, sm_gloss in sm_candidates:
            sm_end = base_pos + len(sm_form)
            slot3 = SlotFill(
                form=sm_form, gloss=sm_gloss,
                source_rule=f"SM.{sm_nc}",
                confidence=ConfidenceLevel.HIGH,
                start=base_pos, end=sm_end,
            )
            slots_so_far = dict(prior_slots)
            slots_so_far["SLOT3"] = slot3          # Subject Marker → SLOT3
            after_sm = remainder[len(sm_form):]

            hyps = self._parse_from_slot4(after_sm, sm_end, slots_so_far, sm_nc)
            results.extend(hyps)

        return results

    def _sm_gloss(self, nc_key: str) -> str:
        """Build a Leipzig gloss for a subject marker."""
        nc_num = nc_key.replace("NC", "").replace("a", "").replace("b", "")
        return f"SM.{nc_key}"

    # ------------------------------------------------------------------
    def _parse_from_slot4(
        self, remainder: str, base_pos: int, prior_slots: Dict, sm_nc: Optional[str]
    ) -> List[SlotParse]:
        """Try TAM prefixes (SLOT4, optional) then route to SLOT7 (OM)."""
        results: List[SlotParse] = []
        tam_candidates: List[Tuple[str, str, str]] = []  # (form, key, gloss)

        for tam_form in sorted(self._cfg.tam_reverse.keys(), key=len, reverse=True):
            if remainder.startswith(tam_form) and len(remainder) > len(tam_form):
                for tam_key, tam_gloss in self._cfg.tam_reverse[tam_form]:
                    tam_candidates.append((tam_form, tam_key, tam_gloss))
                break  # greedy: longest TAM match wins

        # Branch: with TAM vs without TAM
        branches: List[Tuple[str, int, Dict]] = []
        # Without TAM (TAM may be zero-marked)
        branches.append((remainder, base_pos, dict(prior_slots)))

        for tam_form, tam_key, tam_gloss in tam_candidates[:2]:  # limit branching
            tam_end = base_pos + len(tam_form)
            slot4 = SlotFill(
                form=tam_form, gloss=tam_gloss,
                source_rule=f"TAM.{tam_key}",
                confidence=ConfidenceLevel.HIGH,
                start=base_pos, end=tam_end,
            )
            slots_copy = dict(prior_slots)
            slots_copy["SLOT4"] = slot4            # TAM → SLOT4
            branches.append((remainder[len(tam_form):], tam_end, slots_copy))

        for rem, pos, slots in branches:
            hyps = self._parse_from_slot7(rem, pos, slots, sm_nc)
            results.extend(hyps)

        return results

    # ------------------------------------------------------------------
    def _parse_from_slot7(
        self, remainder: str, base_pos: int, prior_slots: Dict, sm_nc: Optional[str]
    ) -> List[SlotParse]:
        """Try OM prefix (SLOT7, optional) then route to root+ext+FV."""
        results: List[SlotParse] = []

        # Without OM
        results.extend(self._parse_rootfv(remainder, base_pos, dict(prior_slots), sm_nc))

        # With OM (one OM per hypothesis)
        for om_form in sorted(self._cfg.om_reverse.keys(), key=len, reverse=True):
            if remainder.startswith(om_form) and len(remainder) > len(om_form):
                om_candidates = self._cfg.om_reverse[om_form]
                for om_nc, om_gloss in om_candidates[:1]:  # limit branching
                    om_end = base_pos + len(om_form)
                    slot7 = SlotFill(
                        form=om_form, gloss=f"OM.{om_nc}",
                        source_rule=f"OM.{om_nc}",
                        confidence=ConfidenceLevel.HIGH,
                        start=base_pos, end=om_end,
                    )
                    slots_copy = dict(prior_slots)
                    slots_copy["SLOT7"] = slot7    # Object Marker → SLOT7
                    hyps = self._parse_rootfv(
                        remainder[len(om_form):], om_end, slots_copy, sm_nc
                    )
                    results.extend(hyps)
                break  # greedy on OM

        return results

    # ------------------------------------------------------------------
    def _parse_rootfv(
        self, remainder: str, base_pos: int, prior_slots: Dict, sm_nc: Optional[str]
    ) -> List[SlotParse]:
        """Identify root (SLOT8), extensions (SLOT9), FV (SLOT11)."""
        if not remainder:
            return []

        results: List[SlotParse] = []

        # Try FV candidates (longest first) to isolate a candidate stem
        fv_candidates: List[Tuple[str, str]] = []  # (fv_form, fv_name)
        for fv_form, fv_name in self._cfg.fv_reverse.items():
            if remainder.endswith(fv_form) and len(remainder) > len(fv_form):
                fv_candidates.append((fv_form, fv_name))
                break  # greedy

        branches_fv: List[Tuple[str, Optional[str], Optional[str]]] = []
        # Without FV — may be an imperative or truncated form
        branches_fv.append((remainder, None, None))
        for fv_form, fv_name in fv_candidates:
            branches_fv.append((remainder[:-len(fv_form)], fv_form, fv_name))

        for stem_ext, fv_form, fv_name in branches_fv:
            hyps = self._match_root_and_extensions(
                stem_ext, base_pos, dict(prior_slots), sm_nc,
                fv_form, fv_name, remainder,
            )
            results.extend(hyps)

        return results

    # ------------------------------------------------------------------
    def _match_root_and_extensions(
        self,
        stem_ext  : str,
        base_pos  : int,
        prior_slots: Dict,
        sm_nc     : Optional[str],
        fv_form   : Optional[str],
        fv_name   : Optional[str],
        full_suffix: str,            # remainder including FV (for reconstruction check)
    ) -> List[SlotParse]:
        """Strip extensions from right side of stem_ext, then match root."""
        if not stem_ext:
            return []

        # Try various extension combinations (right-to-left peeling).
        # All extensions occupy SLOT9 (Z1-Z4 zone within); ext_slot from
        # cfg.ext_reverse is always "SLOT9" after the _build_config fix.
        ext_results: List[Tuple[str, Dict]] = []  # (root_candidate, ext_slots)
        ext_results.append((stem_ext, {}))  # no extensions

        # Peel extensions right-to-left  (max 4 passes, one per zone)
        working: List[Tuple[str, Dict]] = [(stem_ext, {})]
        for _pass in range(4):
            next_working: List[Tuple[str, Dict]] = []
            for candidate, ext_slots_so_far in working:
                for ext_form, ext_key, ext_gloss, ext_slot in self._cfg.ext_reverse:
                    if candidate.endswith(ext_form) and len(candidate) > len(ext_form):
                        new_candidate = candidate[:-len(ext_form)]
                        new_slots = dict(ext_slots_so_far)
                        # Only take one extension per slot (zone)
                        if ext_slot not in new_slots:
                            pos_start = base_pos + len(new_candidate)
                            pos_end   = pos_start + len(ext_form)
                            new_slots[ext_slot] = SlotFill(
                                form=ext_form, gloss=ext_gloss,
                                source_rule=f"EXT.{ext_key}",
                                confidence=ConfidenceLevel.HIGH,
                                start=pos_start, end=pos_end,
                            )
                            new_candidate_ext = (new_candidate, new_slots)
                            if new_candidate_ext not in ext_results:
                                ext_results.append(new_candidate_ext)
                            next_working.append((new_candidate, new_slots))
                        break  # greedy per zone
            if not next_working:
                break
            working = next_working[:4]  # limit branching

        hypotheses: List[SlotParse] = []
        for root_candidate, ext_slots in ext_results:
            hyp = self._build_hypothesis(
                root_candidate, base_pos, dict(prior_slots), ext_slots,
                sm_nc, fv_form, fv_name, full_suffix,
            )
            if hyp is not None:
                hypotheses.append(hyp)

        return hypotheses

    # ------------------------------------------------------------------
    def _build_hypothesis(
        self,
        root_candidate : str,
        base_pos       : int,
        prior_slots    : Dict,
        ext_slots      : Dict,
        sm_nc          : Optional[str],
        fv_form        : Optional[str],
        fv_name        : Optional[str],
        full_suffix    : str,
    ) -> Optional[SlotParse]:
        """Assemble a SlotParse, score it, and return it (or None if empty)."""
        if not root_candidate:
            return None

        # ---- SLOT8: root lookup ----
        norm_root = _lower_nfc(root_candidate)
        lex_entry: Optional[LexiconEntry] = self._verbs.get(norm_root)
        root_confidence = ConfidenceLevel.HIGH if lex_entry else ConfidenceLevel.LOW
        root_gloss = lex_entry.gloss if lex_entry else root_candidate
        root_source = f"LEX:{norm_root}" if lex_entry else f"HEUR:{norm_root}"

        root_start = base_pos
        root_end   = base_pos + len(root_candidate)

        slot8 = SlotFill(
            form=root_candidate, gloss=root_gloss,
            source_rule=root_source,
            confidence=root_confidence,
            start=root_start, end=root_end,
        )

        # ---- SLOT11: final vowel ----
        slot11: Optional[SlotFill] = None
        if fv_form and fv_name:
            fv_start = root_end + sum(
                len(f.form) for f in ext_slots.values() if f.form
            )
            slot11 = SlotFill(
                form=fv_form, gloss=f"FV.{fv_name.upper()}",
                source_rule=f"FV.{fv_name}",
                confidence=ConfidenceLevel.HIGH,
                start=fv_start, end=fv_start + len(fv_form),
            )

        # ---- Assemble SlotParse ----
        sp = SlotParse(
            lang_iso=self._cfg.lang_iso,
            analyser_version=VERSION,
        )
        # Prior slots (SLOT2 neg, SLOT3 SM, SLOT4 TAM, SLOT7 OM)
        for slot_key, fill in prior_slots.items():
            sp.set(slot_key, fill)
        # SLOT8: verb root
        sp.set("SLOT8", slot8)
        # SLOT9: extensions (all zones stored here)
        for slot_key, fill in ext_slots.items():
            sp.set(slot_key, fill)
        # SLOT11: final vowel
        if slot11:
            sp.set("SLOT11", slot11)

        if not sp.filled_slots():
            return None

        # ---- Score ----
        score = _score_hypothesis(sp, lex_entry, full_suffix)
        sp.score = score

        # ---- Flags ----
        if lex_entry:
            sp.add_flag("LEXICON_HIT")
        else:
            sp.add_flag("ROOT_HEURISTIC")
        if fv_form:
            sp.add_flag("FV_IDENTIFIED")

        return sp


def _score_hypothesis(sp: SlotParse, lex_entry: Optional[LexiconEntry], full_suffix: str) -> float:
    """Compute a score in [0.0, 1.0] for a SlotParse hypothesis."""
    score = 0.0

    # Lexicon root hit
    if lex_entry:
        score += 0.40
        if lex_entry.verified:
            score += 0.02  # small bonus for verified entries

    # Final vowel identified (SLOT11)
    if "SLOT11" in sp.slots and not sp.slots["SLOT11"].is_empty():
        score += 0.15

    # TAM prefix identified (SLOT4)
    if "SLOT4" in sp.slots and not sp.slots["SLOT4"].is_empty():
        score += 0.10

    # Subject marker identified (SLOT3)
    if "SLOT3" in sp.slots and not sp.slots["SLOT3"].is_empty():
        score += 0.08

    # Object marker (SLOT7)
    if "SLOT7" in sp.slots and not sp.slots["SLOT7"].is_empty():
        score += 0.05

    # Extension identified (SLOT9)
    if "SLOT9" in sp.slots and not sp.slots["SLOT9"].is_empty():
        score += 0.05

    # Negation prefix (SLOT2)
    if "SLOT2" in sp.slots and not sp.slots["SLOT2"].is_empty():
        score += 0.03

    # Surface reconstruction bonus
    reconstructed = sp.surface()
    if reconstructed == _lower_nfc(full_suffix) or reconstructed == _lower_nfc(
        full_suffix + (sp.get("SLOT11").form or "")
    ):
        score += 0.05

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Noun analyser  — GobeloNounAnalyser
# ---------------------------------------------------------------------------

class GobeloNounAnalyser:
    """Identify noun-class prefix for noun tokens.

    Strategy:
      1. Try all NC prefixes (longest first).
      2. If language has augment, try stripping augment before prefix.
      3. Match remainder against noun lexicon.
      4. Assign noun_class, build MorphemeSpan list.

    Returns a list of (nc_key, stem, lex_entry_or_None, score) tuples.
    """

    def __init__(self, cfg: _AnalyserConfig, lexicon_noun: Dict[str, LexiconEntry]) -> None:
        self._cfg   = cfg
        self._nouns = lexicon_noun or {}

    def analyse(self, form: str) -> List[Tuple[str, str, Optional[LexiconEntry], float]]:
        """Return list of (nc_key, stem, entry, score) sorted by score desc."""
        norm = _lower_nfc(form)
        results: List[Tuple[str, str, Optional[LexiconEntry], float]] = []

        # Build candidate forms to try (with and without augment)
        candidates: List[str] = [norm]
        for aug_form in sorted(self._cfg.augment_forms, key=len, reverse=True):
            if norm.startswith(aug_form) and len(norm) > len(aug_form):
                candidates.append(norm[len(aug_form):])
                break

        for candidate in candidates:
            for prefix, nc_key, nc_gloss in self._cfg.nc_reverse:
                if candidate.startswith(prefix) and len(candidate) > len(prefix):
                    stem = candidate[len(prefix):]
                    entry = self._nouns.get(stem)
                    score = self._score(prefix, stem, entry, nc_key)
                    results.append((nc_key, stem, entry, score))

        # Fallback: direct stem lookup without NC prefix
        if not results:
            entry = self._nouns.get(norm)
            if entry:
                results.append((entry.noun_class or "?", norm, entry, 0.30))

        # Sort by score
        results.sort(key=lambda t: t[3], reverse=True)
        return results[:3]  # top-3 hypotheses

    def _score(
        self,
        prefix: str,
        stem  : str,
        entry : Optional[LexiconEntry],
        nc_key: str,
    ) -> float:
        score = 0.0
        if entry:
            score += 0.50
            if entry.noun_class == nc_key:
                score += 0.20  # NC matches lexicon entry's own declared NC
            if entry.verified:
                score += 0.05
        if len(prefix) > 0:
            score += 0.15   # prefix identified
        if len(stem) >= 2:
            score += 0.05   # non-trivial stem
        return min(score, 1.0)


# ---------------------------------------------------------------------------
# UD feature builder
# ---------------------------------------------------------------------------

def _build_ud_feats(sp: SlotParse, cfg: _AnalyserConfig) -> Dict[str, str]:
    """Extract UD morphological features from the best SlotParse."""
    feats: Dict[str, str] = {}

    # Tense / Aspect / Mood from TAM slot (SLOT4)
    slot4 = sp.get("SLOT4")
    if not slot4.is_empty():
        # Extract TAM key from source_rule e.g. "TAM.PAST.REMOTE"
        tam_key = slot4.source_rule.replace("TAM.", "", 1)
        ud = cfg.tam_ud_feats.get(tam_key, {})
        feats.update(ud)

    # Number / Person from SM slot (SLOT3)
    slot3 = sp.get("SLOT3")
    if not slot3.is_empty():
        # Derive person/number from NC heuristic
        nc_feats = _nc_to_ud(slot3.source_rule.replace("SM.", ""))
        feats.update(nc_feats)

    # VerbForm
    feats["VerbForm"] = "Fin"

    # Negation from pre-subject negation (SLOT2)
    slot2 = sp.get("SLOT2")
    if not slot2.is_empty():
        feats["Polarity"] = "Neg"

    return feats


_NC_UD: Dict[str, Dict[str, str]] = {
    # Standard Bantu NC → approximate UD person/number heuristics
    "NC1"  : {"Number": "Sing", "Person": "3"},
    "NC1a" : {"Number": "Sing", "Person": "3"},
    "NC2"  : {"Number": "Plur", "Person": "3"},
    "NC2a" : {"Number": "Plur", "Person": "3"},
    # 1st/2nd person concords (cross-linguistic)
    "SM1SG": {"Number": "Sing", "Person": "1"},
    "SM2SG": {"Number": "Sing", "Person": "2"},
    "SM1PL": {"Number": "Plur", "Person": "1"},
    "SM2PL": {"Number": "Plur", "Person": "2"},
}

def _nc_to_ud(nc_key: str) -> Dict[str, str]:
    return dict(_NC_UD.get(nc_key, {}))


# ---------------------------------------------------------------------------
# MorphemeSpan builder
# ---------------------------------------------------------------------------

def _build_morpheme_spans(sp: SlotParse, form: str) -> List[MorphemeSpan]:
    """Create MorphemeSpan objects from a SlotParse aligned to *form*."""
    spans: List[MorphemeSpan] = []
    slot_label_map = {
        "SLOT1" : "AUG",
        "SLOT2" : "NEG_PRE",
        "SLOT3" : "SM",
        "SLOT4" : "TAM",
        "SLOT5" : "REL",
        "SLOT6" : "NEG_POST",
        "SLOT7" : "OM",
        "SLOT8" : "ROOT",
        "SLOT9" : "EXT",
        "SLOT10": "TAM_POST",
        "SLOT11": "FV",
    }
    norm_form = _lower_nfc(form)
    for slot_key in sorted(sp.slots.keys(), key=lambda k: int(k[4:])):
        fill = sp.slots[slot_key]
        if fill.is_empty() or fill.start < 0:
            continue
        start = fill.start
        end   = fill.end
        # Sanity-check offsets against the actual form length
        if start > len(norm_form) or end > len(norm_form):
            continue
        ms = MorphemeSpan(
            start = start,
            end   = end,
            form  = norm_form[start:end] if start < end else fill.form,
            label = slot_label_map.get(slot_key, slot_key),
            gloss = fill.gloss,
            slot  = slot_key,
        )
        spans.append(ms)
    return spans


# ---------------------------------------------------------------------------
# Main analyser class  — GobelloMorphAnalyser
# ---------------------------------------------------------------------------

class GobelloMorphAnalyser:
    """Language-agnostic morphological analyser for GGT.

    Parameters
    ----------
    loader : GobeloGrammarLoader (or compatible mock)
        Provides grammar tables for the target language.
    max_hypotheses : int
        Maximum SlotParse hypotheses to keep per verb token.
    skip_token_types : set[TokenType]
        Token types to skip entirely (default: PUNCT, NUMBER, SPECIAL).
    """

    VERSION = VERSION

    def __init__(
        self,
        loader=None,
        max_hypotheses: int = _MAX_HYPOTHESES,
        skip_token_types: Optional[Set[TokenType]] = None,
    ) -> None:
        self._loader   = loader or _NullLoader()
        self._lang_iso = getattr(self._loader, "lang_iso", "und")
        self._max_hyp  = max_hypotheses

        self._skip_types = skip_token_types or {
            TokenType.PUNCT, TokenType.NUMBER, TokenType.SPECIAL
        }

        self._cfg = _build_config(self._loader)

        lexicon_verb = getattr(self._loader, "lexicon_verb", {}) or {}
        lexicon_noun = getattr(self._loader, "lexicon_noun", {}) or {}

        self._verb_parser  = GobeloVerbParser(self._cfg, lexicon_verb)
        self._noun_analyser = GobeloNounAnalyser(self._cfg, lexicon_noun)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def analyse(self, sentence: AnnotatedSentence) -> AnnotatedSentence:
        """Morphologically analyse all word tokens in *sentence* in place.

        Returns the same sentence object (mutated) for chaining.
        """
        for token in sentence.tokens:
            if token.token_type in self._skip_types:
                continue
            if token.token_type == TokenType.CODE_SWITCH:
                continue  # code-switched tokens are handled by Phase 3
            self._analyse_token(token)

        # Mark sentence pipeline
        sentence.add_pipeline_stage(f"GobelloMorphAnalyser-{self.VERSION}")
        return sentence

    def analyse_batch(
        self, sentences: List[AnnotatedSentence]
    ) -> List[AnnotatedSentence]:
        """Analyse a list of sentences."""
        return [self.analyse(s) for s in sentences]

    # ------------------------------------------------------------------ #
    # Token-level analysis
    # ------------------------------------------------------------------ #

    def _analyse_token(self, token: WordToken) -> None:
        """Attempt verb parse, then noun parse, then update token fields."""
        form = token.form

        # 1. Verb parse
        verb_hyps = self._verb_parser.parse(form)

        if verb_hyps and verb_hyps[0].score >= 0.20:
            # Accept as verb-analysed
            for hyp in verb_hyps:
                token.add_slot_parse(hyp)

            best = token.best_slot_parse
            if best:
                token.upos  = POSTag.VERB
                token.lemma = best.root_form() or token.lemma

                # Populate feats
                token.feats.update(_build_ud_feats(best, self._cfg))

                # MorphemeSpans
                spans = _build_morpheme_spans(best, form)
                for ms in spans:
                    token.add_morpheme_span(ms)

                # Lexicon match: resolve from best parse
                root = best.root_form()
                if root:
                    entry = (getattr(self._loader, "lexicon_verb", {}) or {}).get(
                        _lower_nfc(root)
                    )
                    if entry and entry not in token.lexicon_matches:
                        token.add_lexicon_match(entry)

                # CoNLL-U MISC
                token.set_misc(
                    "Morphemes",
                    "|".join(
                        f"{ms.label}={ms.form}"
                        for ms in token.morpheme_spans
                        if ms.form
                    ),
                )
                token.set_misc("Score", f"{best.score:.3f}")

            token.add_flag("VERB_ANALYSED")
            return

        # 2. Noun parse (if verb parse didn't produce a confident result)
        noun_hyps = self._noun_analyser.analyse(form)

        if noun_hyps:
            best_nc, best_stem, best_entry, best_score = noun_hyps[0]

            if best_score >= 0.15:
                token.noun_class = best_nc
                token.upos = POSTag.NOUN

                if best_entry:
                    if best_entry not in token.lexicon_matches:
                        token.add_lexicon_match(best_entry)
                    token.lemma = best_entry.root

                # MorphemeSpan for the NC prefix
                nc_info = self._cfg.nc_table.get(best_nc, {})
                prefixes = _to_list(nc_info.get("prefix", nc_info.get("sg_prefix", [])))
                form_norm = _lower_nfc(form)
                for p in prefixes:
                    if form_norm.startswith(p):
                        nc_span = MorphemeSpan(
                            start=0, end=len(p),
                            form=p,
                            label="NC_PREFIX",
                            gloss=best_nc,
                            slot=None,
                        )
                        token.add_morpheme_span(nc_span)
                        stem_span = MorphemeSpan(
                            start=len(p), end=len(form_norm),
                            form=form_norm[len(p):],
                            label="STEM",
                            gloss=best_entry.gloss if best_entry else best_stem,
                            slot=None,
                        )
                        token.add_morpheme_span(stem_span)
                        break

                token.feats["NounClass"] = best_nc
                token.set_misc("NounClass", best_nc)
                token.set_misc("NCScore", f"{best_score:.3f}")
                token.add_flag("NOUN_ANALYSED")

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def describe(self) -> str:
        """Return a human-readable configuration summary."""
        cfg = self._cfg
        lines = [
            f"GobelloMorphAnalyser v{self.VERSION}",
            f"  lang_iso         : {self._lang_iso}",
            f"  SM entries (SLOT3)  : {len(cfg.sm_table)}",
            f"  TAM entries (SLOT4) : {len(cfg.tam_table)}",
            f"  OM entries (SLOT7)  : {len(cfg.om_table)}",
            f"  FV entries (SLOT11) : {len(cfg.fv_table)}",
            f"  Extension entries (SLOT9): {len(cfg.ext_table)}",
            f"  NC entries       : {len(cfg.nc_table)}",
            f"  NC prefix index  : {len(cfg.nc_reverse)} entries",
            f"  Verb lexicon     : {len(getattr(self._loader,'lexicon_verb',{}) or {})} roots",
            f"  Noun lexicon     : {len(getattr(self._loader,'lexicon_noun',{}) or {})} stems",
            f"  Augment          : {cfg.has_augment}",
            f"  H-spread         : {cfg.extended_h_spread}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"GobelloMorphAnalyser(lang={self._lang_iso!r}, v={self.VERSION})"
