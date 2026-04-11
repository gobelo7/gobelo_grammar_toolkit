"""
pos_tagger.py — GobeloPOSTagger  (GGT Phase 3)
===============================================
Deterministic rule-based PoS tagger and UD feature mapper for the Gobelo
Grammar Toolkit.

Takes an AnnotatedSentence produced by GobelloMorphAnalyser (Phase 2) and
enriches each WordToken with:

  * A confirmed UPOS tag (replaces any Phase 2 heuristic assignment)
  * A full UD FEATS dict (Tense, Aspect, Mood, Number, Person, Polarity,
    VerbForm, Voice, Case, Degree, NounClass, Definite, PronType …)
  * An XPOS tag in GGT format (e.g. VERB.FIN, NOUN.NC3, PRON.REFL.NC7)
  * Confirmed CoNLL-U MISC entries (Morphemes=, Gloss=, NounClass=, etc.)
  * Closed-class UPOS for tokens not morphologically analysed by Phase 2
    (conjunctions, particles, adpositions, numerals, discourse markers)
  * Agreement-chain evidence tags for Phase 6 disambiguation

Architecture
------------
All language-specific knowledge flows from the GGT YAML grammar file.  The
tagger builds one internal _TaggerConfig at construction time from the loader,
then the hot tag() path touches only plain dicts and sets — no YAML objects
in the tagging inner loop.

The tagger works in three passes per sentence:

  Pass A · Per-token slot-parse → UPOS + FEATS
        For each token with a SlotParse (verb or noun analysis from Phase 2):
          1. Determine UPOS from filled-slot pattern
          2. Populate Tense/Aspect/Mood from SLOT4 (TAM) + SLOT11 (FV)
          3. Populate Number/Person from SLOT3 (SM)
          4. Populate Voice from extensions (SLOT9)
          5. Populate VerbForm, Polarity, NounClass
          6. Build XPOS string

  Pass B · Closed-class rule matching
        For tokens that Phase 2 did not analyse (no SlotParse or low score):
          1. Check function-word inventories from YAML
          2. Check special token types (PUNCT, NUMBER, SPECIAL)
          3. Apply positional heuristics (sentence-initial, post-verb)

  Pass C · Sentence-level agreement propagation
        Light one-pass left-to-right context sweep:
          1. Track last confirmed NC (from NOUN tokens)
          2. If a VERB token's SM matches that NC → boost its score, confirm
             Person/Number features from the noun's NC entry
          3. Mark agreement links in token MISC field (AgreeNC=NC3, etc.)

Loader interface assumed
------------------------
Same as Phase 2 morph_analyser.py.  The tagger additionally reads:

  loader.get("verb_system.verbal_system_components.final_vowels", {})
  loader.get("verb_system.verbal_system_components.negation_pre", {})
  loader.get("closed_class_words", {})     # optional block in YAML
  loader.get("morphology.particles", {})   # optional
  loader.get("morphology.conjunctions", {})
  loader.get("morphology.adpositions", {})

If those keys are absent the tagger silently skips closed-class matching for
the missing category — it never raises.

Usage
-----
    loader  = GobeloGrammarLoader("toi")
    tagger  = GobeloPOSTagger(loader)

    # After morph analysis:
    sentence = tagger.tag(sentence)          # mutates in-place, returns same obj
    sentences = tagger.tag_batch([s1, s2])

    # Standalone (tagger will call morphological analyser internally if needed):
    sentence = tagger.tag(sentence, run_morph=True)

UD feature reference
--------------------
All feature names and values follow UD v2 guidelines:
  https://universaldependencies.org/u/feat/index.html

Bantu-specific extensions (not in UD v2 core) stored with a GGT_ prefix in
FEATS until they are standardised:
  GGT_NounClass   : NC1 … NC18
  GGT_TonePattern : H, L, HL, LH, LHL (when determinable from YAML)
  GGT_SlotScore   : float 0–1 (analyser confidence, round to 2dp)
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from models import (
    AnnotatedSentence,
    ConfidenceLevel,
    LexiconEntry,
    POSTag,
    SlotFill,
    SlotParse,
    TokenType,
    WordToken,
)

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# UD FEATS constants
# ---------------------------------------------------------------------------

# Canonical UD Tense values
_UD_TENSE = {
    "pres": "Pres", "present": "Pres",
    "past": "Past", "pst": "Past",
    "fut":  "Fut",  "future": "Fut",
    "imp":  "Imp",  "imperfect": "Imp",
    "pqp":  "Pqp",  "pluperfect": "Pqp",
}

# Canonical UD Aspect values
_UD_ASPECT = {
    "perf": "Perf", "perfective": "Perf",
    "imp":  "Imp",  "imperfective": "Imp",
    "prog": "Prog", "progressive": "Prog",
    "hab":  "Hab",  "habitual": "Hab",
    "iter": "Iter", "iterative": "Iter",
    "pro":  "Prosp","prospective": "Prosp",
}

# Canonical UD Mood values
_UD_MOOD = {
    "ind":  "Ind",  "indicative": "Ind",
    "sub":  "Sub",  "subjunctive": "Sub",
    "imp":  "Imp",  "imperative": "Imp",
    "cnd":  "Cnd",  "conditional": "Cnd",
    "opt":  "Opt",  "optative": "Opt",
    "jus":  "Jus",  "jussive": "Jus",
    "pot":  "Pot",  "potential": "Pot",
}

# Canonical UD Voice values
_UD_VOICE = {
    "act":  "Act",  "active": "Act",
    "pass": "Pass", "passive": "Pass",
    "cau":  "Cau",  "causative": "Cau",
    "mid":  "Mid",  "middle": "Mid",
    "rcp":  "Rcp",  "reciprocal": "Rcp",
    "antip":"Antip","antipassive": "Antip",
}

# Canonical UD VerbForm values
_UD_VERBFORM = {
    "fin":  "Fin",  "finite": "Fin",
    "inf":  "Inf",  "infinitive": "Inf",
    "part": "Part", "participle": "Part",
    "conv": "Conv", "converb": "Conv",
    "vnoun":"Vnoun","verbal_noun": "Vnoun",
    "ger":  "Ger",  "gerund": "Ger",
}

# Extension key → Voice feature (cross-linguistic GGT gloss patterns)
_EXT_VOICE_MAP: Dict[str, str] = {
    "PASS": "Pass",
    "CAUS": "Cau",
    "RECIP": "Rcp",
    "RECP": "Rcp",
    "ANTIP": "Antip",
}

# Extension key → additional feature additions
_EXT_FEAT_MAP: Dict[str, Dict[str, str]] = {
    "APPL": {"Valency": "3"},
    "CAUS": {"Valency": "3"},
    "STAT": {"Aspect": "Stat"},
    "PASS": {"Voice": "Pass"},
    "RECIP": {"Voice": "Rcp"},
    "RECP": {"Voice": "Rcp"},
    "REV":  {"Aspect": "Rev"},
    "POS":  {"Aspect": "Pos"},
}

# NC → rough UD Number + Person heuristics (refined per language by YAML)
_NC_PERSON_NUMBER: Dict[str, Tuple[str, str]] = {
    # Human classes
    "NC1":   ("Sing", "3"),
    "NC1a":  ("Sing", "3"),
    "NC2":   ("Plur", "3"),
    "NC2a":  ("Plur", "3"),
    "NC2b":  ("Plur", "3"),
    # Agreement-class conventions for 1st/2nd person concords:
    # These keys come from the YAML concord glosses, not NC numbers
    "SM1SG": ("Sing", "1"),
    "SM2SG": ("Sing", "2"),
    "SM1PL": ("Plur", "1"),
    "SM1PLEXCL": ("Plur", "1"),
    "SM1PLINCL": ("Plur", "1"),
    "SM2PL": ("Plur", "2"),
    "1SG":   ("Sing", "1"),
    "2SG":   ("Sing", "2"),
    "1PL":   ("Plur", "1"),
    "1PL_EXCL": ("Plur", "1"),
    "1PL_INCL": ("Plur", "1"),
    "2PL":   ("Plur", "2"),
    "3PL_HUMAN": ("Plur", "3"),
    "3SG":   ("Sing", "3"),
    "3PL":   ("Plur", "3"),
}

# UPOS for closed-class YAML categories
_CAT_UPOS: Dict[str, POSTag] = {
    "conjunction": POSTag.CCONJ,
    "subordinator": POSTag.SCONJ,
    "particle": POSTag.PART,
    "adposition": POSTag.ADP,
    "discourse": POSTag.PART,
    "copula": POSTag.AUX,
    "auxiliary": POSTag.AUX,
    "determiner": POSTag.DET,
    "pronoun": POSTag.PRON,
    "interjection": POSTag.INTJ,
    "ideophone": POSTag.IDEOPH,
    "negation": POSTag.PART,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _lower_nfc(s: str) -> str:
    return _nfc(s.lower())


def _norm_key(s: str) -> str:
    """Lowercase, NFC, strip leading/trailing whitespace for dict lookup."""
    return _nfc(s.strip().lower())


def _ud_val(mapping: Dict[str, str], raw: str) -> Optional[str]:
    """Resolve a raw gloss fragment to a UD canonical value."""
    if not raw:
        return None
    key = raw.strip().lower().replace(".", "_").replace("-", "_")
    # Direct lookup
    if key in mapping:
        return mapping[key]
    # Substring scan (handles compound glosses like "PST.HOD")
    for fragment, val in mapping.items():
        if fragment in key:
            return val
    return None


def _to_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


# ---------------------------------------------------------------------------
# _TaggerConfig  — pre-computed tables built once from loader
# ---------------------------------------------------------------------------

@dataclass
class _TaggerConfig:
    """Pre-computed, language-specific tagging tables.

    Built once at GobeloPOSTagger construction time.  All fields are plain
    Python dicts / sets so the tagging inner loop never touches YAML.
    """
    lang_iso: str

    # ── TAM key → UD feature dict ──────────────────────────────────────
    # e.g. "PST": {"Tense": "Past", "Aspect": "Perf"}
    tam_ud: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # ── FV name → UD feature dict ──────────────────────────────────────
    # e.g. "perfective": {"Aspect": "Perf"},
    #      "subjunctive": {"Mood": "Sub"},
    #      "negative": {"Polarity": "Neg"}
    fv_ud: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # ── SM key → (Number, Person) ──────────────────────────────────────
    # e.g. "NC1": ("Sing", "3"), "1SG": ("Sing", "1")
    sm_np: Dict[str, Tuple[str, str]] = field(default_factory=dict)

    # ── NC → GGT_NounClass string ──────────────────────────────────────
    nc_tag: Dict[str, str] = field(default_factory=dict)

    # ── NC15 prefix forms → flag as infinitive ─────────────────────────
    nc15_prefixes: Set[str] = field(default_factory=set)

    # ── NC16/17/18 keys → locative flag ────────────────────────────────
    locative_ncs: Set[str] = field(default_factory=set)

    # ── Closed-class inventories ───────────────────────────────────────
    # form → (UPOS, xpos_detail, feats_dict)
    closed_class: Dict[str, Tuple[POSTag, str, Dict[str, str]]] = field(
        default_factory=dict
    )

    # ── Extension key → (Voice, extra_feats) ──────────────────────────
    ext_voice: Dict[str, str] = field(default_factory=dict)
    ext_feats: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # ── Number inventory (forms that are numeral tokens) ───────────────
    numeral_forms: Set[str] = field(default_factory=set)

    # ── Augment system present? ────────────────────────────────────────
    has_augment: bool = False


def _build_tagger_config(loader) -> _TaggerConfig:
    """Construct _TaggerConfig from loader grammar."""
    cfg = _TaggerConfig(lang_iso=getattr(loader, "lang_iso", "und"))

    # ── Engine features ────────────────────────────────────────────────
    eng = loader.get("engine_features", {}) or {}
    cfg.has_augment = bool(eng.get("augment", False))

    # ── NC table ──────────────────────────────────────────────────────
    nc_data = loader.get("morphology.noun_classes", {}) or {}
    for nc_key, nc_info in (nc_data.items() if isinstance(nc_data, dict) else []):
        cfg.nc_tag[nc_key] = nc_key  # "NC3" → "NC3"
        class_type = ""
        if isinstance(nc_info, dict):
            class_type = str(nc_info.get("class_type", ""))
        if nc_key in ("NC16", "NC17", "NC18") or class_type == "locative":
            cfg.locative_ncs.add(nc_key)

    # NC15 (infinitives) — collect its prefix forms
    nc15 = nc_data.get("NC15", {}) if isinstance(nc_data, dict) else {}
    if isinstance(nc15, dict):
        pfx = nc15.get("prefix", {})
        if isinstance(pfx, dict):
            for f in _to_list(pfx.get("canonical_form", "")) + _to_list(pfx.get("allomorphs", [])):
                if f:
                    cfg.nc15_prefixes.add(_nfc(f.rstrip("-")))
        elif isinstance(pfx, str):
            cfg.nc15_prefixes.add(_nfc(pfx.rstrip("-")))

    # ── TAM → UD features ─────────────────────────────────────────────
    tam_data = loader.get("morphology.tense_aspect", {}) or {}
    _build_tam_ud(tam_data, cfg)

    # ── FV → UD features ──────────────────────────────────────────────
    fv_data = (
        loader.get("morphology.final_vowels", {})
        or loader.get("verb_system.verbal_system_components.final_vowels", {})
        or {}
    )
    _build_fv_ud(fv_data, cfg)

    # ── SM → Number + Person ──────────────────────────────────────────
    sm_data = loader.get("morphology.subject_markers", {}) or {}
    _build_sm_np(sm_data, cfg)

    # ── Extension → Voice / extra feats ───────────────────────────────
    ext_data = loader.get("morphology.extensions", {}) or {}
    for ext_key, ext_info in (ext_data.items() if isinstance(ext_data, dict) else []):
        key_upper = ext_key.upper()
        if key_upper in _EXT_VOICE_MAP:
            cfg.ext_voice[ext_key] = _EXT_VOICE_MAP[key_upper]
        if key_upper in _EXT_FEAT_MAP:
            cfg.ext_feats[ext_key] = dict(_EXT_FEAT_MAP[key_upper])

    # ── Closed-class inventories ──────────────────────────────────────
    _build_closed_class(loader, cfg)

    return cfg


def _build_tam_ud(tam_data: dict, cfg: _TaggerConfig) -> None:
    """Populate cfg.tam_ud from TAM section of YAML."""
    if not isinstance(tam_data, dict):
        return

    for key, info in tam_data.items():
        if not isinstance(info, dict):
            continue
        feats: Dict[str, str] = {}
        gloss = str(info.get("gloss", key)).upper()

        # Check for explicit ud_feats block first
        ud_block = info.get("ud_feats") or info.get("ud_features") or {}
        if isinstance(ud_block, dict):
            feats.update({k: str(v) for k, v in ud_block.items()})

        # Derive from gloss if not already set
        if "Tense" not in feats:
            t = _ud_val(_UD_TENSE, gloss)
            if t:
                feats["Tense"] = t
        if "Aspect" not in feats:
            a = _ud_val(_UD_ASPECT, gloss)
            if a:
                feats["Aspect"] = a
        if "Mood" not in feats:
            m = _ud_val(_UD_MOOD, gloss)
            if m:
                feats["Mood"] = m

        # Additional heuristics from function/note fields
        function = str(info.get("function", "")).lower()
        if "habit" in function and "Aspect" not in feats:
            feats["Aspect"] = "Hab"
        if "negat" in function and "Polarity" not in feats:
            feats["Polarity"] = "Neg"
        if "subj" in function and "Mood" not in feats:
            feats["Mood"] = "Sub"
        if "cond" in function and "Mood" not in feats:
            feats["Mood"] = "Cnd"

        cfg.tam_ud[key] = feats

        # Handle nested sub-tenses (some YAMLs nest present.positive, present.negative)
        for sub_key, sub_info in info.items():
            if isinstance(sub_info, dict) and "form" in sub_info:
                sub_gloss = str(sub_info.get("gloss", f"{key}.{sub_key}")).upper()
                sub_feats: Dict[str, str] = {}
                sub_ud = sub_info.get("ud_feats") or {}
                if isinstance(sub_ud, dict):
                    sub_feats.update({k: str(v) for k, v in sub_ud.items()})
                if "Tense" not in sub_feats:
                    t = _ud_val(_UD_TENSE, sub_gloss)
                    if t:
                        sub_feats["Tense"] = t
                if "Aspect" not in sub_feats:
                    a = _ud_val(_UD_ASPECT, sub_gloss)
                    if a:
                        sub_feats["Aspect"] = a
                if "Mood" not in sub_feats:
                    m = _ud_val(_UD_MOOD, sub_gloss)
                    if m:
                        sub_feats["Mood"] = m
                cfg.tam_ud[f"{key}.{sub_key}"] = sub_feats


def _build_fv_ud(fv_data: dict, cfg: _TaggerConfig) -> None:
    """Populate cfg.fv_ud from final-vowel section of YAML."""
    if not isinstance(fv_data, dict):
        return

    # Hard-coded universal Bantu FV semantics (same across all GGT languages)
    _fv_defaults: Dict[str, Dict[str, str]] = {
        "indicative":         {"Mood": "Ind"},
        "subjunctive":        {"Mood": "Sub"},
        "negative":           {"Polarity": "Neg", "Mood": "Ind"},
        "imperative_singular":{"Mood": "Imp", "Number": "Sing"},
        "imperative_plural":  {"Mood": "Imp", "Number": "Plur"},
        "perfective":         {"Aspect": "Perf"},
        "infinitive":         {"VerbForm": "Inf"},
    }

    for name, fv_info in fv_data.items():
        feats: Dict[str, str] = {}
        # Check for explicit ud_feats first
        ud_block = {}
        if isinstance(fv_info, dict):
            ud_block = fv_info.get("ud_feats") or fv_info.get("ud_features") or {}
        if isinstance(ud_block, dict):
            feats.update({k: str(v) for k, v in ud_block.items()})

        # Apply defaults if nothing explicit
        defaults = _fv_defaults.get(_norm_key(name), {})
        for k, v in defaults.items():
            if k not in feats:
                feats[k] = v

        cfg.fv_ud[_norm_key(name)] = feats


def _build_sm_np(sm_data: dict, cfg: _TaggerConfig) -> None:
    """Populate cfg.sm_np from subject-marker section."""
    if not isinstance(sm_data, dict):
        return

    for key, info in sm_data.items():
        gloss = key
        if isinstance(info, dict):
            gloss = info.get("gloss", key)

        # Normalise key for lookup
        key_norm = _norm_key(key)

        # Try heuristic NC_PERSON_NUMBER table first
        pn = _NC_PERSON_NUMBER.get(key) or _NC_PERSON_NUMBER.get(key_norm.upper())
        if pn:
            cfg.sm_np[key] = pn
            continue

        # Derive from gloss
        gloss_up = str(gloss).upper()
        number = "Sing" if any(x in gloss_up for x in ("SG", "SING", "SINGULAR")) else (
                 "Plur" if any(x in gloss_up for x in ("PL", "PLUR", "PLURAL")) else "")
        person = ("1" if "1" in gloss_up else
                  "2" if "2" in gloss_up else
                  "3" if "3" in gloss_up or "NC" in gloss_up else "")
        if number or person:
            cfg.sm_np[key] = (number or "Sing", person or "3")


def _build_closed_class(loader, cfg: _TaggerConfig) -> None:
    """Populate cfg.closed_class from various YAML closed-class sections."""

    # Keys to try, each mapped to a UPOS
    sections: List[Tuple[str, str, POSTag]] = [
        ("morphology.conjunctions",  "CONJ",   POSTag.CCONJ),
        ("morphology.subordinators", "SCONJ",  POSTag.SCONJ),
        ("morphology.particles",     "PART",   POSTag.PART),
        ("morphology.adpositions",   "ADP",    POSTag.ADP),
        ("morphology.determiners",   "DET",    POSTag.DET),
        ("morphology.pronouns",      "PRON",   POSTag.PRON),
        ("morphology.auxiliaries",   "AUX",    POSTag.AUX),
        ("morphology.copula",        "COP",    POSTag.AUX),
        ("morphology.negation",      "NEG",    POSTag.PART),
        ("morphology.discourse",     "DISC",   POSTag.PART),
        ("morphology.interjections", "INTJ",   POSTag.INTJ),
        ("closed_class_words",       "CLOSED", None),       # generic block
    ]

    for yaml_key, xpos_base, default_upos in sections:
        data = loader.get(yaml_key, {}) or {}
        if not isinstance(data, dict):
            continue
        for entry_key, entry_val in data.items():
            forms: List[str] = []
            upos = default_upos
            xpos_detail = xpos_base
            extra_feats: Dict[str, str] = {}

            if isinstance(entry_val, dict):
                forms = _to_list(entry_val.get("form", entry_val.get("forms", [])))
                gloss = str(entry_val.get("gloss", entry_key))
                xpos_detail = f"{xpos_base}.{entry_key}"
                # Override UPOS if explicitly specified
                cat = str(entry_val.get("category", entry_val.get("pos", ""))).lower()
                if cat and cat in _CAT_UPOS:
                    upos = _CAT_UPOS[cat]
                # Feats from ud_feats block
                ud_block = entry_val.get("ud_feats") or {}
                if isinstance(ud_block, dict):
                    extra_feats.update({k: str(v) for k, v in ud_block.items()})
                # PronType for pronouns
                if upos == POSTag.PRON:
                    if any(x in gloss.upper() for x in ("REFL", "REFLEX")):
                        extra_feats["PronType"] = "Prs"
                        extra_feats["Reflex"] = "Yes"
                    elif any(x in gloss.upper() for x in ("INTERR", "QUEST", "WH")):
                        extra_feats["PronType"] = "Int"
                    elif any(x in gloss.upper() for x in ("DEM", "PROX", "DIST", "MED")):
                        extra_feats["PronType"] = "Dem"
                    else:
                        extra_feats["PronType"] = "Prs"
                # Polarity for negation
                if "NEG" in xpos_base:
                    extra_feats["Polarity"] = "Neg"
            elif isinstance(entry_val, str):
                forms = [entry_val]

            for f in forms:
                fn = _lower_nfc(f)
                if fn:
                    final_upos = upos or POSTag.X
                    cfg.closed_class[fn] = (final_upos, xpos_detail, dict(extra_feats))


# ---------------------------------------------------------------------------
# UPOS determination rules
# ---------------------------------------------------------------------------

def _determine_upos_and_verbform(
    sp: SlotParse,
    cfg: _TaggerConfig,
    token_form: str,
) -> Tuple[POSTag, str]:
    """Return (UPOS, VerbForm-or-empty) from a SlotParse.

    Rules (in priority order):
    1. No SM and no TAM and no ROOT → cannot determine from slots → X
    2. ROOT filled + SM filled → VERB (finite)
    3. ROOT filled + NC15 prefix → VERB (infinitive) / NOUN if no SM
    4. ROOT filled + no SM + NC prefix → NOUN
    5. ROOT only (no NC prefix, no SM) → VERB (imperative-like) or X
    6. NC prefix is locative (NC16-18) → ADP (locative case)
    """
    slot3  = sp.get("SLOT3")   # SM
    slot4  = sp.get("SLOT4")   # TAM
    slot8  = sp.get("SLOT8")   # ROOT
    slot11 = sp.get("SLOT11")  # FV

    has_sm   = not slot3.is_empty()
    has_tam  = not slot4.is_empty()
    has_root = not slot8.is_empty()
    has_fv   = not slot11.is_empty()

    # Check if noun-class prefix was resolved for this token
    noun_class = _get_nc_from_parse(sp)

    # ---- Locative noun used as adverbial / locative nominal ----
    # NC16/17/18 without TAM are locative nominals, not finite verbs.
    # Even if SLOT3 carries the locative prefix as an "SM", the absence
    # of a TAM prefix signals this is a nominal/adpositional use.
    if noun_class in cfg.locative_ncs and not has_tam:
        return POSTag.ADP, ""

    # ---- Infinitive (NC15 prefix detected) ----
    if noun_class == "NC15":
        return POSTag.VERB, "Inf"

    # ---- Finite verb ----
    if has_root and (has_sm or has_tam):
        return POSTag.VERB, "Fin"

    # ---- Noun ----
    if has_root and noun_class and not has_sm and not has_tam:
        return POSTag.NOUN, ""

    # ---- Imperative (no SM, no TAM, ROOT + FV only) ----
    if has_root and not has_sm and not has_tam:
        if has_fv:
            fv_gloss = slot11.gloss.lower()
            if "imp" in fv_gloss:
                return POSTag.VERB, "Fin"
        return POSTag.VERB, "Fin"  # default: treat bare root+FV as verb

    # ---- Fallback ----
    return POSTag.X, ""


def _get_nc_from_parse(sp: SlotParse) -> Optional[str]:
    """Extract noun class key from a SlotParse (via SLOT3 SM source_rule)."""
    # NC is encoded in SLOT3.source_rule as "SM.NC3"
    slot3 = sp.get("SLOT3")
    if not slot3.is_empty():
        rule = slot3.source_rule or ""
        if rule.startswith("SM.NC"):
            return rule[3:]  # "NC3"
        # Also check gloss
        gloss = slot3.gloss or ""
        if gloss.startswith("CL") or gloss.startswith("NC"):
            # Extract "NC3" from "CL3.SM" or "NC3.SM"
            parts = gloss.split(".")
            if parts[0].replace("CL", "NC").startswith("NC"):
                return parts[0].replace("CL", "NC")
    return None


# ---------------------------------------------------------------------------
# FEATS builder
# ---------------------------------------------------------------------------

def _build_full_feats(
    sp       : SlotParse,
    cfg      : _TaggerConfig,
    upos     : POSTag,
    verbform : str,
    token    : WordToken,
) -> Dict[str, str]:
    """Assemble the complete UD FEATS dict for a token with a SlotParse."""
    feats: Dict[str, str] = {}

    # ── VerbForm (from UPOS determination) ──────────────────────────────
    if verbform:
        feats["VerbForm"] = verbform
    elif upos == POSTag.VERB:
        feats["VerbForm"] = "Fin"

    # ── TAM → Tense / Aspect / Mood ────────────────────────────────────
    slot4 = sp.get("SLOT4")
    if not slot4.is_empty():
        tam_key = slot4.source_rule.replace("TAM.", "", 1) if slot4.source_rule else ""
        ud = cfg.tam_ud.get(tam_key, {})
        feats.update(ud)
        # If TAM key had sub-key (e.g. "PST.HOD"), try that too
        if not ud and "." in tam_key:
            ud = cfg.tam_ud.get(tam_key.split(".", 1)[0], {})
            feats.update(ud)

    # ── FV → Aspect / Mood (may override TAM if more specific) ──────────
    slot11 = sp.get("SLOT11")
    if not slot11.is_empty():
        fv_name = ""
        rule = slot11.source_rule or ""
        if rule.startswith("FV."):
            fv_name = _norm_key(rule[3:])
        elif slot11.gloss.startswith("FV."):
            fv_name = _norm_key(slot11.gloss[3:])
        if fv_name:
            fv_ud = cfg.fv_ud.get(fv_name, {})
            for k, v in fv_ud.items():
                # FV Mood overrides TAM Mood only if not already set from TAM
                if k == "Mood" and "Mood" in feats:
                    continue
                feats[k] = v

    # ── Default Mood for finite verbs ────────────────────────────────────
    if upos == POSTag.VERB and "Mood" not in feats and verbform == "Fin":
        feats["Mood"] = "Ind"

    # ── SM → Number / Person (SLOT3) ─────────────────────────────────────
    slot3 = sp.get("SLOT3")
    if not slot3.is_empty():
        sm_key = slot3.source_rule.replace("SM.", "", 1) if slot3.source_rule else ""
        pn = cfg.sm_np.get(sm_key)
        if pn is None:
            # Try the gloss
            gloss_key = (slot3.gloss or "").replace(".", "").replace("SM", "").strip()
            pn = cfg.sm_np.get(gloss_key) or _NC_PERSON_NUMBER.get(gloss_key)
        if pn:
            feats["Number"], feats["Person"] = pn
        else:
            # NC agreement: non-human NCs are always 3rd person
            nc = _get_nc_from_parse(sp)
            if nc and nc not in ("NC1", "NC2", "NC1a", "NC2a", "NC2b"):
                feats.setdefault("Person", "3")
                feats.setdefault("Number", "Sing" if not nc.endswith(
                    ("2", "4", "6", "8", "10", "13")
                ) else "Plur")

    # ── SLOT2 pre-subject negation ───────────────────────────────────────
    slot2 = sp.get("SLOT2")
    if not slot2.is_empty():
        feats["Polarity"] = "Neg"

    # ── Extensions → Voice / additional feats (SLOT9) ────────────────────
    voice_vals: List[str] = []
    ext_fill = sp.get("SLOT9")
    if not ext_fill.is_empty():
        rule = ext_fill.source_rule or ""
        ext_key = rule.replace("EXT.", "", 1) if rule.startswith("EXT.") else rule
        if ext_key in cfg.ext_voice:
            voice_vals.append(cfg.ext_voice[ext_key])
        if ext_key in cfg.ext_feats:
            for k, v in cfg.ext_feats[ext_key].items():
                if k != "Voice":
                    feats.setdefault(k, v)

    if voice_vals:
        feats["Voice"] = voice_vals[0]  # outermost extension wins
    elif upos == POSTag.VERB and "Voice" not in feats:
        feats["Voice"] = "Act"

    # ── Noun-specific features ────────────────────────────────────────────
    if upos == POSTag.NOUN:
        nc = _get_nc_from_parse(sp) or token.noun_class
        if nc:
            feats["GGT_NounClass"] = nc
            # UD Number from NC pairing
            if nc in ("NC2", "NC2a", "NC2b", "NC4", "NC6", "NC8",
                      "NC10", "NC13"):
                feats.setdefault("Number", "Plur")
            else:
                feats.setdefault("Number", "Sing")
        feats.pop("VerbForm", None)  # nouns don't have VerbForm

    # ── Infinitives ────────────────────────────────────────────────────────
    if verbform == "Inf":
        # Infinitives don't inflect for person/number
        feats.pop("Person", None)
        feats.pop("Number", None)
        feats.pop("Mood", None)

    # ── Confidence score ────────────────────────────────────────────────
    feats["GGT_SlotScore"] = f"{sp.score:.2f}"

    return feats


# ---------------------------------------------------------------------------
# XPOS builder
# ---------------------------------------------------------------------------

def _build_xpos(
    upos: POSTag, feats: Dict[str, str], sp: Optional[SlotParse], token: WordToken
) -> str:
    """Build a GGT XPOS string.

    Format:  UPOS[.DETAIL[.DETAIL…]]
    Examples:
      VERB.FIN.PAST.3SG
      NOUN.NC3.SING
      PRON.DEM.PROX.NC7
      AUX.PROG
      PART.NEG
    """
    parts = [upos.value]

    if upos == POSTag.VERB:
        vf = feats.get("VerbForm", "FIN").upper()
        parts.append(vf)
        tense = feats.get("Tense", "")
        if tense:
            parts.append(tense.upper())
        person = feats.get("Person", "")
        number = feats.get("Number", "")
        if person and number:
            parts.append(f"{person}{number[:2].upper()}")
        voice = feats.get("Voice", "")
        if voice and voice != "Act":
            parts.append(voice.upper())

    elif upos == POSTag.NOUN:
        nc = feats.get("GGT_NounClass") or token.noun_class or ""
        if nc:
            parts.append(nc)
        num = feats.get("Number", "")
        if num:
            parts.append(num.upper()[:4])

    elif upos in (POSTag.PRON, POSTag.DET):
        pt = feats.get("PronType", "")
        if pt:
            parts.append(pt.upper())
        nc = feats.get("GGT_NounClass") or token.noun_class or ""
        if nc:
            parts.append(nc)

    elif upos == POSTag.ADP:
        nc = feats.get("GGT_NounClass") or token.noun_class or ""
        if nc:
            parts.append(f"LOC.{nc}")

    elif upos == POSTag.PART:
        if feats.get("Polarity") == "Neg":
            parts.append("NEG")

    return ".".join(parts)


# ---------------------------------------------------------------------------
# Closed-class tagger  (Pass B)
# ---------------------------------------------------------------------------

def _tag_closed_class(
    token: WordToken,
    cfg  : _TaggerConfig,
) -> bool:
    """Try to assign UPOS from the closed-class inventory.

    Returns True if the token was successfully tagged, False otherwise.
    Mutates token.upos, token.xpos, token.feats in place.
    """
    if token.upos not in (None, POSTag.X):
        return False  # already tagged

    form_norm = _lower_nfc(token.form)
    result = cfg.closed_class.get(form_norm)
    if result is None:
        return False

    upos, xpos_detail, extra_feats = result
    token.upos = upos
    token.xpos = xpos_detail
    token.feats.update(extra_feats)
    token.add_flag("CLOSED_CLASS_TAGGED")
    return True


# ---------------------------------------------------------------------------
# Agreement chain  (Pass C)
# ---------------------------------------------------------------------------

@dataclass
class _AgreementState:
    """Running state for the sentence-level agreement propagation pass."""
    last_noun_nc  : Optional[str] = None   # NC of most recent NOUN token
    last_noun_idx : int = -1               # index in sentence.tokens


def _propagate_agreement(
    sentence: AnnotatedSentence,
    cfg     : _TaggerConfig,
) -> None:
    """Left-to-right agreement propagation.

    For each VERB token, if its SM (SLOT3) source_rule NC matches the NC
    of the most recently seen NOUN in the sentence, annotate both with
    agreement metadata in their MISC fields.

    This is a lightweight implementation; full chain resolution is Phase 6.
    """
    state = _AgreementState()

    for idx, token in enumerate(sentence.tokens):
        # ── Update last-seen NOUN NC ──────────────────────────────────
        if token.upos == POSTag.NOUN:
            nc = token.noun_class or token.feats.get("GGT_NounClass")
            if nc:
                state.last_noun_nc  = nc
                state.last_noun_idx = idx
            continue

        # ── For VERB: check SM-NC agreement via SLOT3 ────────────────
        if token.upos == POSTag.VERB and state.last_noun_nc:
            best = token.best_slot_parse
            if best is None:
                continue
            sm_nc = _get_nc_from_parse(best)
            if sm_nc and sm_nc == state.last_noun_nc:
                # Agreement confirmed
                token.set_misc("AgreeNC", sm_nc)
                token.set_misc("AgreeWith", str(state.last_noun_idx + 1))
                noun_token = sentence.tokens[state.last_noun_idx]
                noun_token.set_misc("AgreeVerb", str(idx + 1))
                token.add_flag("AGREE_CONFIRMED")


# ---------------------------------------------------------------------------
# Token MISC update
# ---------------------------------------------------------------------------

def _update_misc(token: WordToken, sp: Optional[SlotParse]) -> None:
    """Populate the CoNLL-U MISC field from analysis results."""
    if sp:
        # Morphemes= pipe-separated label=form pairs
        if token.morpheme_spans:
            token.set_misc(
                "Morphemes",
                "|".join(
                    f"{ms.label}={ms.form}"
                    for ms in token.morpheme_spans
                    if ms.form
                ),
            )
        # Gloss= Leipzig gloss of best parse
        gloss = sp.gloss_string()
        if gloss:
            token.set_misc("Gloss", gloss)
        # SlotScore
        token.set_misc("SlotScore", f"{sp.score:.3f}")

    # NounClass
    nc = token.noun_class or token.feats.get("GGT_NounClass")
    if nc:
        token.set_misc("NounClass", nc)

    # OOV flag
    if token.is_oov:
        token.set_misc("OOV", "Yes")


# ---------------------------------------------------------------------------
# Main tagger class
# ---------------------------------------------------------------------------

class GobeloPOSTagger:
    """Deterministic rule-based PoS tagger and UD feature mapper for GGT.

    Parameters
    ----------
    loader : GobeloGrammarLoader (or compatible mock)
        Provides grammar tables for the target language.
    min_score_threshold : float
        Minimum SlotParse score to accept for UPOS assignment.
        Tokens with best_parse.score < threshold fall through to
        closed-class matching and heuristics.
    run_agreement : bool
        Whether to run Pass C (sentence-level agreement propagation).
        Default True.  Disable for speed when only token-level output is needed.
    skip_token_types : set[TokenType]
        Token types to skip entirely.  Default: PUNCT, NUMBER, SPECIAL.
    """

    VERSION = VERSION

    def __init__(
        self,
        loader=None,
        min_score_threshold: float = 0.20,
        run_agreement: bool = True,
        skip_token_types: Optional[Set[TokenType]] = None,
    ) -> None:
        from morph_analyser import _NullLoader
        self._loader    = loader or _NullLoader()
        self._lang_iso  = getattr(self._loader, "lang_iso", "und")
        self._threshold = min_score_threshold
        self._do_agree  = run_agreement

        self._skip_types = skip_token_types or {
            TokenType.PUNCT, TokenType.NUMBER, TokenType.SPECIAL
        }

        self._cfg = _build_tagger_config(self._loader)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def tag(
        self,
        sentence: AnnotatedSentence,
        run_morph: bool = False,
    ) -> AnnotatedSentence:
        """Tag all tokens in *sentence* in place; return same object.

        Parameters
        ----------
        sentence : AnnotatedSentence
            Must have tokens; should have SlotParses from Phase 2.
        run_morph : bool
            If True, run GobelloMorphAnalyser on the sentence first.
            Useful for standalone use without a pre-built pipeline.
        """
        if run_morph:
            from morph_analyser import GobelloMorphAnalyser
            ana = GobelloMorphAnalyser(self._loader)
            ana.analyse(sentence)

        # Pass A — per-token slot parse → UPOS + FEATS
        for token in sentence.tokens:
            if token.token_type in self._skip_types:
                self._tag_special(token)
                continue
            if token.token_type == TokenType.CODE_SWITCH:
                self._tag_code_switch(token)
                continue
            self._tag_token(token)

        # Pass B — closed-class fallback (runs on untagged tokens)
        for token in sentence.tokens:
            if token.token_type in self._skip_types:
                continue
            _tag_closed_class(token, self._cfg)

        # Pass C — agreement propagation
        if self._do_agree:
            _propagate_agreement(sentence, self._cfg)

        sentence.add_pipeline_stage(f"GobeloPOSTagger-{self.VERSION}")
        return sentence

    def tag_batch(
        self,
        sentences: List[AnnotatedSentence],
        run_morph: bool = False,
    ) -> List[AnnotatedSentence]:
        """Tag a list of sentences."""
        return [self.tag(s, run_morph=run_morph) for s in sentences]

    # ------------------------------------------------------------------ #
    # Pass A — per-token
    # ------------------------------------------------------------------ #

    def _tag_token(self, token: WordToken) -> None:
        """Tag a single non-special token using its SlotParse (if available)."""
        best = token.best_slot_parse

        # ── Case 1: good SlotParse from Phase 2 ────────────────────────
        if best and best.score >= self._threshold:
            upos, verbform = _determine_upos_and_verbform(
                best, self._cfg, token.form
            )
            feats = _build_full_feats(best, self._cfg, upos, verbform, token)
            xpos  = _build_xpos(upos, feats, best, token)

            token.upos  = upos
            token.xpos  = xpos
            token.feats.update(feats)
            _update_misc(token, best)
            token.add_flag("POS_TAGGED")
            return

        # ── Case 2: Phase 2 attempted noun analysis but no SlotParse ───
        if token.noun_class:
            feats = self._feats_for_noun(token)
            xpos  = _build_xpos(POSTag.NOUN, feats, None, token)
            token.upos  = POSTag.NOUN
            token.xpos  = xpos
            token.feats.update(feats)
            _update_misc(token, None)
            token.add_flag("POS_TAGGED")
            return

        # ── Case 3: low-score SlotParse — still try to extract UPOS ───
        if best and best.score > 0.05:
            upos, verbform = _determine_upos_and_verbform(
                best, self._cfg, token.form
            )
            if upos != POSTag.X:
                feats = _build_full_feats(best, self._cfg, upos, verbform, token)
                xpos  = _build_xpos(upos, feats, best, token)
                token.upos  = upos
                token.xpos  = xpos
                token.feats.update(feats)
                token.feats["GGT_SlotScore"] = f"{best.score:.2f}"
                _update_misc(token, best)
                token.add_flag("POS_TAGGED_LOW_CONF")
                return

        # ── Case 4: no analysis — will be handled by Pass B / heuristics
        token.add_flag("POS_UNTAGGED")

    def _feats_for_noun(self, token: WordToken) -> Dict[str, str]:
        """Build FEATS for a noun token identified only by NC prefix."""
        feats: Dict[str, str] = {}
        nc = token.noun_class
        if nc:
            feats["GGT_NounClass"] = nc
            if nc in ("NC2", "NC2a", "NC2b", "NC4", "NC6", "NC8",
                      "NC10", "NC13"):
                feats["Number"] = "Plur"
            else:
                feats["Number"] = "Sing"
        return feats

    def _tag_special(self, token: WordToken) -> None:
        """Tag punctuation, numbers, and special tokens."""
        if token.token_type == TokenType.PUNCT:
            token.upos = POSTag.PUNCT
            token.xpos = "PUNCT"
        elif token.token_type == TokenType.NUMBER:
            token.upos = POSTag.NUM
            token.xpos = "NUM"
            token.feats["NumType"] = "Card"
        elif token.token_type == TokenType.SPECIAL:
            token.upos = token.upos or POSTag.SYM
            token.xpos = token.xpos or "SYM"

    def _tag_code_switch(self, token: WordToken) -> None:
        """Mark code-switched tokens."""
        token.upos = POSTag.X
        token.xpos = "X.CS"
        token.set_misc("CodeSwitch", token.code_switch_lang or "und")

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def describe(self) -> str:
        """Human-readable configuration summary."""
        cfg = self._cfg
        lines = [
            f"GobeloPOSTagger v{self.VERSION}",
            f"  lang_iso          : {self._lang_iso}",
            f"  TAM→UD mappings   : {len(cfg.tam_ud)}",
            f"  FV→UD mappings    : {len(cfg.fv_ud)}",
            f"  SM→Number/Person  : {len(cfg.sm_np)}",
            f"  NC entries        : {len(cfg.nc_tag)}",
            f"  NC15 prefixes     : {sorted(cfg.nc15_prefixes)}",
            f"  Locative NCs      : {sorted(cfg.locative_ncs)}",
            f"  Closed-class forms: {len(cfg.closed_class)}",
            f"  Score threshold   : {self._threshold}",
            f"  Agreement pass    : {self._do_agree}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"GobeloPOSTagger(lang={self._lang_iso!r}, v={self.VERSION})"
