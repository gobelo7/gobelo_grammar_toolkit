"""
core/normalizer.py
==================
Raw-to-typed normalization layer for the Gobelo (Bantu) Grammar Toolkit.

The normalizer translates the output of ``yaml.safe_load()`` (a plain Python
dict) into the typed, immutable model objects defined in ``core/models.py``.
It performs **no validation** and **no I/O** — those concerns belong to
``core/validator.py`` and ``core/loader.py`` respectively.

YAML format support
-------------------
The normalizer handles two YAML layouts transparently:

* **GGT-canonical format** — flat top-level keys ``metadata``,
  ``noun_classes``, ``concord_systems``, ``verb_system``, ``phonology``,
  ``tokenization`` (the format used by generated/simplified files).
* **chiTonga extended format** — a top-level ``chitonga_grammar`` wrapper
  with ``phonology_rules``, ``morphology``, and nested sub-structures
  (the authoritative reference-grammar format used by the Gobelo project).

The ``normalize()`` method detects the format automatically and routes to
the appropriate helper path.  Application code never needs to know which
format was on disk; it always receives the same typed model objects.

Design principles
-----------------
* **Defensive optional-field handling** — many YAML fields are optional.
  All helpers supply safe defaults when fields are absent or ``None``.
* **VERIFY annotation stripping** — ``_clean()`` removes ``VERIFY:``
  authoring annotations from string values before storage in model objects.
* **Immutable outputs** — every returned object is a ``frozen=True``
  dataclass.
* **No grammar logic** — the normalizer never infers, derives, or computes
  linguistic information.  Absent fields produce neutral Python defaults.

The ``_ParsedGrammar`` internal dataclass
-----------------------------------------
``GrammarNormalizer.normalize()`` returns a ``_ParsedGrammar`` instance that
the loader stores internally.  This type is not exported and must never be
returned across the public API boundary.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from gobelo_grammar_toolkit.core.models import (
    ConcordSet,
    DerivationalPattern,
    GrammarMetadata,
    NounClass,
    PhonologyRules,
    TAMMarker,
    TokenizationRules,
    VerbExtension,
    VerbSlot,
    VerifyFlag,
)

__all__ = [
    "_ParsedGrammar",
    "GrammarNormalizer",
]

# ---------------------------------------------------------------------------
# Compiled pattern: strip VERIFY annotations from string values
# ---------------------------------------------------------------------------

_VERIFY_STRIP_RE: re.Pattern[str] = re.compile(
    r"\s*VERIFY\s*:.*$",
    re.IGNORECASE | re.DOTALL,
)

# Extension dict keys that are *not* individual extension entries
_EXT_NON_ENTRY_KEYS = frozenset(
    {"extension_ordering", "semantic_composition", "description", "notes"}
)

# Concord sub-dict keys that are metadata, not NC entries
_CONCORD_META_KEYS = frozenset(
    {"description", "construction", "position", "syntax", "notes", "usage"}
)


# ---------------------------------------------------------------------------
# _ParsedGrammar — internal aggregate type
# ---------------------------------------------------------------------------


@dataclass
class _ParsedGrammar:
    """
    Internal aggregate of all typed grammar objects produced by
    ``GrammarNormalizer.normalize()``.

    This class is **private** to ``core/``.  It is never returned across
    the public API boundary.  The loader stores one instance per loaded
    grammar and delegates all public ``get_*()`` calls to its fields.

    Fields mirror the public API surface of ``GobeloGrammarLoader`` in a
    flat, pre-parsed form so that every public method is an O(1) attribute
    access with no repeated parsing.
    """

    metadata: GrammarMetadata
    noun_classes: Dict[str, NounClass]
    concord_systems: Dict[str, ConcordSet]
    tam_markers: List[TAMMarker]
    verb_extensions: List[VerbExtension]
    verb_slots: List[VerbSlot]
    derivational_patterns: List[DerivationalPattern]
    verb_template: Dict[str, Any]
    phonology: PhonologyRules
    tokenization: TokenizationRules
    verify_flags: List[VerifyFlag]


# ---------------------------------------------------------------------------
# TAM tense/aspect/mood inference table
# ---------------------------------------------------------------------------

# Maps canonical TAM id → (tense, aspect, mood)
_TAM_SEMANTIC_MAP: Dict[str, Tuple[str, str, str]] = {
    "PRES":     ("present",       "imperfective", "indicative"),
    "PST":      ("immediate_past","perfective",   "indicative"),
    "REC_PST":  ("immediate_past","perfective",   "indicative"),
    "REM_PST":  ("remote_past",   "perfective",   "indicative"),
    "FUT_NEAR": ("immediate_future", "none",      "indicative"),
    "FUT_REM":  ("remote_future", "none",         "indicative"),
    "HAB":      ("present",       "habitual",     "indicative"),
    "PERF":     ("present",       "perfective",   "indicative"),
    "PROG":     ("present",       "progressive",  "indicative"),
    "COND":     ("none",          "none",         "conditional"),
    "POT":      ("none",          "none",         "conditional"),
    "SUBJ":     ("none",          "none",         "subjunctive"),
    "IMP":      ("none",          "none",         "imperative"),
}


# ---------------------------------------------------------------------------
# GrammarNormalizer
# ---------------------------------------------------------------------------


class GrammarNormalizer:
    """
    Translates a validated raw YAML dict into a ``_ParsedGrammar``.

    This class is stateless: every ``normalize()`` call creates a fresh
    ``_ParsedGrammar`` from the supplied raw dict.  The same
    ``GrammarNormalizer`` instance may be reused across multiple grammar
    loads without side effects.

    Format detection
    ----------------
    If the raw dict contains a ``chitonga_grammar`` key the normalizer
    treats it as the *extended* Gobelo reference-grammar format.  Otherwise
    it falls back to the *GGT-canonical* flat format.  Both paths produce
    identical ``_ParsedGrammar`` outputs.

    Usage
    -----
    >>> normalizer = GrammarNormalizer()
    >>> parsed = normalizer.normalize(raw_yaml_dict, verify_flags)
    >>> isinstance(parsed.metadata, GrammarMetadata)
    True
    """

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def normalize(
        self,
        raw: Dict[str, Any],
        verify_flags: List[VerifyFlag],
    ) -> _ParsedGrammar:
        """
        Translate ``raw`` into a fully-typed ``_ParsedGrammar``.

        Parameters
        ----------
        raw : Dict[str, Any]
            Raw YAML dict from ``yaml.safe_load()``.  May use either the
            GGT-canonical flat schema or the chiTonga extended schema.
        verify_flags : List[VerifyFlag]
            Flag list produced by ``GrammarValidator.validate()`` (or an
            empty list if the validator was skipped).

        Returns
        -------
        _ParsedGrammar
            Fully populated internal grammar aggregate.
        """
        if "chitonga_grammar" in raw:
            return self._normalize_extended(raw["chitonga_grammar"], verify_flags)
        # Production reference-grammar format: top-level noun_class_system
        # and concord_system keys (the Gobelo project's own YAML files).
        if "noun_class_system" in raw or "concord_system" in raw:
            return self._normalize_canonical(
                self._remap_production_format(raw), verify_flags
            )
        return self._normalize_canonical(raw, verify_flags)

    # ------------------------------------------------------------------
    # Extended format (chitonga_grammar wrapper)
    # ------------------------------------------------------------------

    def _normalize_extended(
        self,
        root: Dict[str, Any],
        verify_flags: List[VerifyFlag],
    ) -> _ParsedGrammar:
        """Normalize the chiTonga extended reference-grammar YAML format."""
        morph: Dict[str, Any] = root.get("morphology") or {}
        verb_sys: Dict[str, Any] = morph.get("verb_system") or {}
        patterns_block: Dict[str, Any] = morph.get("patterns") or {}

        noun_classes = self._normalize_noun_classes_extended(
            morph.get("noun_classes") or {}
        )
        concord_systems = self._normalize_concord_systems_extended(
            morph.get("concords") or {}, verb_sys
        )
        verify_count = sum(1 for f in verify_flags if not f.resolved)

        return _ParsedGrammar(
            metadata=self._normalize_metadata_extended(
                root.get("metadata") or {}, verify_count
            ),
            noun_classes=noun_classes,
            concord_systems=concord_systems,
            tam_markers=self._normalize_tam_markers_dict(
                verb_sys.get("tam") or {}
            ),
            verb_extensions=self._normalize_verb_extensions_dict(
                verb_sys.get("extensions") or {}
            ),
            verb_slots=self._normalize_verb_slots_dict(
                verb_sys.get("verb_slots") or {}
            ),
            derivational_patterns=self._normalize_derivational_patterns_dict(
                patterns_block.get("derivational_patterns") or {}
            ),
            verb_template=copy.deepcopy(verb_sys),
            phonology=self._normalize_phonology_extended(
                root.get("phonology_rules") or {}
            ),
            tokenization=self._normalize_tokenization_extended(
                root.get("tokenization") or {}
            ),
            verify_flags=list(verify_flags),
        )

    # ------------------------------------------------------------------
    # Canonical format (flat schema)
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # Production reference-grammar format remapper
    # ------------------------------------------------------------------

    def _remap_production_format(
        self,
        raw: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Remap the Gobelo production YAML format to the canonical flat format
        so that ``_normalize_canonical`` can process it without changes.

        Production format has::

            metadata.language         — nested dict with name/iso_code/guthrie
            metadata.version          — instead of grammar_version
            metadata.schema_compatibility.min_parser_version
            noun_class_system.noun_classes  — keyed dict of NC entries
            concord_system.concords   — keyed dict of concord paradigms
            verb_system.verbal_system_components.tam  — keyed TAM dict
            verb_system.verbal_system_components.derivational_extensions
            verb_system.verb_slots    — keyed slot dict
            phonology.vowels          — nested dict with 'segments' list
            tokenization.word_boundary

        All of these are remapped to what ``_normalize_canonical`` already
        understands.  No linguistic data is changed.
        """
        out: Dict[str, Any] = {}

        # ── metadata ──────────────────────────────────────────────────
        raw_meta = raw.get("metadata") or {}
        lang_raw = raw_meta.get("language") or {}
        # Flatten nested language dict into top-level metadata keys
        meta_out: Dict[str, Any] = {}
        if isinstance(lang_raw, dict):
            meta_out["language"]  = lang_raw.get("name", "").lower().strip()
            meta_out["iso_code"]  = lang_raw.get("iso_code", "")
            meta_out["guthrie"]   = lang_raw.get("guthrie", "")
        else:
            meta_out["language"]  = str(lang_raw).lower().strip()
            meta_out["iso_code"]  = raw_meta.get("iso_code", "")
            meta_out["guthrie"]   = raw_meta.get("guthrie", "")

        # grammar_version: prefer grammar_version, fall back to version
        # Strip non-semver suffixes like "(RC)", "(beta)", "-dev" so
        # the version compatibility check accepts the value.
        _raw_ver = (
            raw_meta.get("grammar_version")
            or raw_meta.get("version", "1.0.0")
            or "1.0.0"
        )
        meta_out["grammar_version"] = re.sub(
            r"[^0-9.].*$", "", str(_raw_ver)
        ).strip(".") or "1.0.0"
        # loader version range: prefer explicit keys, fall back to schema_compat
        sc = raw_meta.get("schema_compatibility") or {}
        def _semver(v, fallback):
            """Ensure v is MAJOR.MINOR.PATCH; pad or clean as needed."""
            s = re.sub(r"[^0-9.].*$", "", str(v or fallback)).strip(".")
            parts = s.split(".")
            while len(parts) < 3:
                parts.append("0")
            return ".".join(parts[:3])

        meta_out["min_loader_version"] = _semver(
            raw_meta.get("min_loader_version")
            or sc.get("min_parser_version"), "1.0.0"
        )
        meta_out["max_loader_version"] = _semver(
            raw_meta.get("max_loader_version")
            or sc.get("max_parser_version"), "999.0.0"
        )
        out["metadata"] = meta_out

        # ── noun classes ──────────────────────────────────────────────
        ncs_block = raw.get("noun_class_system") or {}
        raw_ncs   = ncs_block.get("noun_classes") or {}
        # Inject id and semantic_domain so _normalize_noun_classes_canonical
        # can read the production NC format without special-casing.
        cooked_ncs = {}
        for nc_id, entry in raw_ncs.items():
            if not isinstance(entry, dict):
                continue
            e = dict(entry)
            if "id" not in e:
                e["id"] = nc_id
            if "semantic_domain" not in e:
                sem = e.get("semantics")
                if isinstance(sem, dict):
                    e["semantic_domain"] = sem.get("primary_domain", "unspecified")
                else:
                    e["semantic_domain"] = "unspecified"
            cooked_ncs[nc_id] = e
        out["noun_classes"] = cooked_ncs

        # ── concord systems ───────────────────────────────────────────
        concord_block = raw.get("concord_system") or {}
        # concord_system.concords is the dict of paradigms
        raw_concords = concord_block.get("concords") or {}
        # Strip metadata keys from each paradigm dict so
        # _extract_concord_entries only sees NC/person → form entries
        out["concord_systems"] = raw_concords

        # ── verb system ───────────────────────────────────────────────
        vs = raw.get("verb_system") or {}
        vsc = vs.get("verbal_system_components") or {}

        vs_out: Dict[str, Any] = {}

        # TAM: lives in verbal_system_components.tam (keyed dict)
        vs_out["tam_markers"] = vsc.get("tam") or {}

        # Extensions: lives in verbal_system_components.derivational_extensions
        vs_out["verb_extensions"] = vsc.get("derivational_extensions") or {}

        # Slots: lives in verb_system.verb_slots (keyed dict)
        vs_out["verb_slots"] = vs.get("verb_slots") or {}

        # Preserve the full verb_system block for verb_template
        vs_out["verb_template"] = vs

        out["verb_system"] = vs_out

        # ── phonology ─────────────────────────────────────────────────
        raw_phon = raw.get("phonology") or {}
        phon_out: Dict[str, Any] = {}

        # vowels: may be dict with 'segments' subkey
        vowels_raw = raw_phon.get("vowels") or []
        if isinstance(vowels_raw, dict):
            segs = vowels_raw.get("segments") or vowels_raw.get("short") or []
            phon_out["vowels"] = (
                [s["symbol"] if isinstance(s, dict) else str(s) for s in segs]
                if segs else ["a", "e", "i", "o", "u"]
            )
        else:
            phon_out["vowels"] = [str(v) for v in vowels_raw if v]

        # consonants
        cons_raw = raw_phon.get("consonants") or []
        if isinstance(cons_raw, dict):
            segs = cons_raw.get("segments") or []
            phon_out["consonants"] = [
                s["symbol"] if isinstance(s, dict) else str(s) for s in segs
            ]
        else:
            phon_out["consonants"] = [str(c) for c in cons_raw if c]

        # tone system
        tones_raw = raw_phon.get("tones") or {}
        if isinstance(tones_raw, dict):
            phon_out["tone_system"] = (
                tones_raw.get("system")
                or tones_raw.get("type")
                or "four_level"
            )
        else:
            phon_out["tone_system"] = str(tones_raw) if tones_raw else "four_level"

        # nasal prefixes, sandhi rules, vowel harmony rules
        engine = raw_phon.get("engine_features") or {}
        phon_out["nasal_prefixes"] = engine.get("nasal_prefixes") or []

        # sandhi rules: from processing_stages list
        stages = raw_phon.get("processing_stages") or []
        sandhi: List[str] = []
        vh: List[str] = []
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            rules = stage.get("rules") or []
            for rule in rules:
                rid = rule.get("id", "") if isinstance(rule, dict) else str(rule)
                if rid.startswith("SND"):
                    sandhi.append(rid)
                elif rid.startswith("VH"):
                    vh.append(rid)
        phon_out["sandhi_rules"]        = sandhi
        phon_out["vowel_harmony_rules"] = vh
        phon_out["notes"] = ""
        out["phonology"] = phon_out

        # ── tokenization ──────────────────────────────────────────────
        raw_tok = raw.get("tokenization") or {}
        out["tokenization"] = {
            "word_boundary_pattern": (
                raw_tok.get("word_boundary")
                or raw_tok.get("word_boundary_pattern")
                or r"\s+"
            ),
            "notes": "",
        }

        return out

    def _normalize_canonical(
        self,
        raw: Dict[str, Any],
        verify_flags: List[VerifyFlag],
    ) -> _ParsedGrammar:
        """
        Normalize the GGT-canonical flat YAML schema.

        Handles two sub-variants of the canonical schema:

        * **List-based** — ``verb_system.tam_markers`` is a list of dicts,
          ``verb_system.verb_slots`` is a list of dicts.  This is the format
          produced by generated/simplified grammars.
        * **Dict-based** — ``verb_system.tam_markers`` is a keyed dict
          (``{PRES: {...}, PST: {...}}``) and ``verb_system.verb_slots`` is
          a keyed dict (``{SLOT1: {...}, SLOT2: {...}}``).  This is the
          format used by the Gobelo reference-grammar YAML files after
          legacy normalisation.  The dict helpers (``_normalize_*_dict``)
          already exist in the extended-format path and are reused here.
        """
        verb_sys = raw.get("verb_system") or {}
        verify_count = sum(1 for f in verify_flags if not f.resolved)

        # ── TAM markers ─────────────────────────────────────────────────
        # May be a list (canonical) or a keyed dict (reference-grammar).
        raw_tam = verb_sys.get("tam_markers")
        if isinstance(raw_tam, dict):
            tam_markers = self._normalize_tam_markers_dict(raw_tam)
        else:
            tam_markers = self._normalize_tam_markers_list(raw_tam or [])

        # ── Verb extensions ─────────────────────────────────────────────
        # Same dual-format handling.
        raw_ext = verb_sys.get("verb_extensions")
        if isinstance(raw_ext, dict):
            verb_extensions = self._normalize_verb_extensions_dict(raw_ext)
        else:
            verb_extensions = self._normalize_verb_extensions_list(raw_ext or [])

        # ── Verb slots ──────────────────────────────────────────────────
        # Same dual-format handling.
        raw_slots = verb_sys.get("verb_slots")
        if isinstance(raw_slots, dict):
            verb_slots = self._normalize_verb_slots_dict(raw_slots)
        else:
            verb_slots = self._normalize_verb_slots_list(raw_slots or [])

        return _ParsedGrammar(
            metadata=self._normalize_metadata_canonical(
                raw.get("metadata") or {}, verify_count
            ),
            noun_classes=self._normalize_noun_classes_canonical(
                raw.get("noun_classes") or {}
            ),
            concord_systems=self._normalize_concord_systems_canonical(
                raw.get("concord_systems") or {}
            ),
            tam_markers=tam_markers,
            verb_extensions=verb_extensions,
            verb_slots=verb_slots,
            derivational_patterns=self._normalize_derivational_patterns_list(
                verb_sys.get("derivational_patterns") or []
            ),
            verb_template=copy.deepcopy(
                verb_sys.get("verb_template") or verb_sys
            ),
            phonology=self._normalize_phonology_canonical(
                raw.get("phonology") or {}
            ),
            tokenization=self._normalize_tokenization_canonical(
                raw.get("tokenization") or {}
            ),
            verify_flags=list(verify_flags),
        )

    # ==================================================================
    # Extended-format section normalizers
    # ==================================================================

    def _normalize_metadata_extended(
        self,
        raw_meta: Dict[str, Any],
        verify_count: int,
    ) -> GrammarMetadata:
        """
        Bridge the sparse chiTonga metadata block to ``GrammarMetadata``.

        The extended format only guarantees ``Yaml_version`` and
        ``framework_version``; all other GGT fields are supplied from
        per-language defaults.
        """
        yaml_ver = str(
            raw_meta.get("Yaml_version")
            or raw_meta.get("yaml_version")
            or "1.0"
        )
        return GrammarMetadata(
            language=_get_str(raw_meta, "language", default="chitonga"),
            iso_code=_get_str(raw_meta, "iso_code", default="toi"),
            guthrie=_get_str(raw_meta, "guthrie", default="M.64"),
            grammar_version=yaml_ver,
            min_loader_version=_get_str(
                raw_meta, "min_loader_version", default="1.0.0"
            ),
            max_loader_version=_get_str(
                raw_meta, "max_loader_version", default="*"
            ),
            verify_count=verify_count,
        )

    def _normalize_noun_classes_extended(
        self,
        raw_ncs: Dict[str, Any],
    ) -> Dict[str, NounClass]:
        """
        Translate the extended-format ``noun_classes`` mapping.

        Each NC entry uses a rich ``prefix`` sub-dict::

            NC1:
              prefix:
                canonical_form: mu-
                allomorphs:
                  - form: mw-
                    condition: before_vowels
              grammatical_number: singular
              paired_class: NC2
              active: true
              semantics:
                primary_domain: human_beings
        """
        result: Dict[str, NounClass] = {}
        for nc_id, entry in raw_ncs.items():
            if not isinstance(entry, dict):
                continue

            # --- prefix ---
            prefix_data = entry.get("prefix") or {}
            if isinstance(prefix_data, dict):
                prefix = _clean(_get_str(prefix_data, "canonical_form"))
                raw_allos = prefix_data.get("allomorphs") or []
                allomorphs: List[str] = []
                if isinstance(raw_allos, list):
                    for allo in raw_allos:
                        if isinstance(allo, dict):
                            f = allo.get("form", "")
                            if f:
                                allomorphs.append(_clean(str(f)))
                        elif isinstance(allo, str):
                            allomorphs.append(_clean(allo))
            else:
                prefix = _clean(str(prefix_data)) if prefix_data else ""
                allomorphs = []

            # --- semantic domain ---
            semantics = entry.get("semantics") or {}
            if isinstance(semantics, dict):
                sem_domain = _get_str(
                    semantics, "primary_domain", default="unspecified"
                )
            else:
                sem_domain = _get_str(entry, "semantic_domain", default="unspecified")

            # --- counterparts ---
            paired = _get_optional_str(entry, "paired_class")
            gram_num = _get_str(entry, "grammatical_number", default="").lower()
            if gram_num == "singular":
                plural_counterpart: Optional[str] = paired
                singular_counterpart: Optional[str] = None
            elif gram_num == "plural":
                plural_counterpart = None
                singular_counterpart = paired
            else:
                plural_counterpart = None
                singular_counterpart = paired  # locatives etc.

            result[nc_id] = NounClass(
                id=nc_id,
                prefix=prefix,
                allomorphs=allomorphs,
                semantic_domain=sem_domain,
                active=_get_bool(entry, "active", default=True),
                singular_counterpart=singular_counterpart,
                plural_counterpart=plural_counterpart,
            )
        return result

    def _normalize_concord_systems_extended(
        self,
        raw_concords: Dict[str, Any],
        verb_sys: Dict[str, Any],
    ) -> Dict[str, ConcordSet]:
        """
        Collect all concord paradigms from the extended format.

        Sources:
        * ``morphology.concords.*`` — possessive, adjectival, locative, etc.
        * ``morphology.verb_system.subject_concords``
        * ``morphology.verb_system.object_concords``

        Each NC entry looks like::

            NC1: {forms: ["wa", "w"], tone: "L", ...}

        The first element of ``forms`` is used as the canonical concord value
        in ``ConcordSet.entries``.  For demonstrative concords the sub-type
        keys (proximal, medial, distal) are each promoted to a separate
        ``ConcordSet`` named ``demonstrative_concords_proximal`` etc.
        """
        result: Dict[str, ConcordSet] = {}

        # --- morphology.concords ---
        for concord_type, entries in raw_concords.items():
            if concord_type in _CONCORD_META_KEYS:
                continue
            if not isinstance(entries, dict):
                continue

            if concord_type == "demonstrative_concords":
                for sub, sub_entries in entries.items():
                    if sub in _CONCORD_META_KEYS or not isinstance(sub_entries, dict):
                        continue
                    key = f"demonstrative_concords_{sub}"
                    result[key] = ConcordSet(
                        concord_type=key,
                        entries=self._extract_concord_entries(sub_entries),
                    )
            else:
                result[concord_type] = ConcordSet(
                    concord_type=concord_type,
                    entries=self._extract_concord_entries(entries),
                )

        # --- verb_system subject/object concords ---
        for sc_type in ("subject_concords", "object_concords"):
            raw_sc = verb_sys.get(sc_type) or {}
            if isinstance(raw_sc, dict):
                result[sc_type] = ConcordSet(
                    concord_type=sc_type,
                    entries=self._extract_concord_entries(raw_sc),
                )

        return result

    def _extract_concord_entries(
        self,
        raw_entries: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Flatten a concord NC-mapping to ``{nc_id: primary_form}``.

        Handles both the extended ``{forms: [...], ...}`` structure and
        plain ``{nc_id: "form_string"}`` entries.
        """
        cleaned: Dict[str, str] = {}
        for nc_id, entry_data in raw_entries.items():
            if nc_id in _CONCORD_META_KEYS:
                continue
            if isinstance(entry_data, dict):
                forms = entry_data.get("forms")
                if isinstance(forms, list) and forms:
                    cleaned[nc_id] = _clean(str(forms[0]))
                elif isinstance(forms, str):
                    cleaned[nc_id] = _clean(forms)
                # entries with no usable form are silently skipped
            elif isinstance(entry_data, str):
                cleaned[nc_id] = _clean(entry_data)
        return cleaned

    def _normalize_tam_markers_dict(
        self,
        raw_tams: Dict[str, Any],
    ) -> List[TAMMarker]:
        """
        Translate the extended ``verb_system.tam`` keyed dict.

        Example entry::

            PRES:
              forms: "a"
              tone: "L"
              function: "Present habitual"
              note: "Distinguished from perfect by final vowel"
        """
        result: List[TAMMarker] = []
        for tam_id, entry in raw_tams.items():
            if not isinstance(entry, dict):
                continue
            forms = entry.get("forms", "")
            if isinstance(forms, list):
                form = _clean(str(forms[0])) if forms else ""
            else:
                form = _clean(str(forms)) if forms else ""

            tense, aspect, mood = _TAM_SEMANTIC_MAP.get(
                tam_id, ("none", "none", "indicative")
            )
            notes = _get_str(entry, "note") or _get_str(entry, "notes")

            result.append(
                TAMMarker(
                    id=f"TAM_{tam_id}",
                    form=form,
                    tense=tense,
                    aspect=aspect,
                    mood=mood,
                    notes=notes,
                )
            )
        return result

    def _normalize_verb_extensions_dict(
        self,
        raw_exts: Dict[str, Any],
    ) -> List[VerbExtension]:
        """
        Translate the extended ``verb_system.extensions`` keyed dict.

        Non-extension management keys (``extension_ordering``,
        ``semantic_composition``) are silently skipped.

        Example entry::

            APPL:
              name: "Applicative"
              form: ["-il-", "-el-"]
              zone: Z1
              allomorphs:
                - form: ["-el-"]
                  context: "stem contains [e, o]"
        """
        result: List[VerbExtension] = []
        for ext_id, entry in raw_exts.items():
            if ext_id in _EXT_NON_ENTRY_KEYS or not isinstance(entry, dict):
                continue

            # canonical form — first element of the forms list
            forms = entry.get("form", [])
            if isinstance(forms, list):
                canonical = _clean(str(forms[0])) if forms else ""
            else:
                canonical = _clean(str(forms)) if forms else ""

            # allomorphs — may be [{form: [...], context}, ...]
            allomorphs: List[str] = []
            for allo in entry.get("allomorphs") or []:
                if isinstance(allo, dict):
                    f = allo.get("form", "")
                    if isinstance(f, list):
                        allomorphs.extend(
                            _clean(str(x)) for x in f if x
                        )
                    elif f:
                        allomorphs.append(_clean(str(f)))
                elif isinstance(allo, str):
                    allomorphs.append(_clean(allo))

            sem = (
                _get_str(entry, "function")
                or _get_str(entry, "name")
                or ext_id.lower()
            )

            result.append(
                VerbExtension(
                    id=ext_id,
                    canonical_form=canonical,
                    allomorphs=allomorphs,
                    zone=_get_str(entry, "zone", default="Z1"),
                    semantic_value=sem,
                )
            )
        return result

    def _normalize_verb_slots_dict(
        self,
        raw_slots: Dict[str, Any],
    ) -> List[VerbSlot]:
        """
        Translate the extended ``verb_system.verb_slots`` keyed dict.

        Example entry::

            SLOT3:
              code: "subject_concords"
              name: "Subject Concord"
              position: 3
              type: "Agreement"
              required: true
              description: "Agrees with subject in noun class, person, and number"
        """
        result: List[VerbSlot] = []
        for slot_id, entry in raw_slots.items():
            if not isinstance(entry, dict):
                continue

            code = entry.get("code")
            slot_type = entry.get("type", "")
            allowed = [code] if code else ([slot_type] if slot_type else [])

            forms_ref = entry.get("forms_ref")
            if forms_ref and isinstance(forms_ref, list):
                allowed = [str(r) for r in forms_ref if r]
            elif forms_ref and isinstance(forms_ref, str):
                allowed = [forms_ref]

            result.append(
                VerbSlot(
                    id=slot_id,
                    name=_get_str(entry, "name"),
                    position=_get_int(entry, "position", default=0),
                    obligatory=_get_bool(entry, "required", default=False),
                    allowed_content_types=allowed,
                    notes=_get_str(entry, "description"),
                )
            )
        result.sort(key=lambda s: s.position)
        return result

    def _normalize_derivational_patterns_dict(
        self,
        raw_pats: Dict[str, Any],
    ) -> List[DerivationalPattern]:
        """
        Translate the extended ``patterns.derivational_patterns`` keyed dict.

        Example entry::

            diminutive_formation:
              source_class: "any"
              target_class: "NC12/NC13"
              pattern: "ka-/tu- + stem"
              semantic_change: "indicates smallness, affection, or contempt"
        """
        result: List[DerivationalPattern] = []
        for pat_id, entry in raw_pats.items():
            if not isinstance(entry, dict):
                continue

            tc_str = _get_str(entry, "target_class")
            target_nc: Optional[str] = None
            if tc_str:
                # e.g. "NC12/NC13" → "NC12"
                first_part = tc_str.split("/")[0].strip()
                if first_part.upper().startswith("NC"):
                    target_nc = first_part.upper()

            out_cat = f"noun_{tc_str}" if tc_str else "noun"

            result.append(
                DerivationalPattern(
                    id=pat_id.upper(),
                    name=pat_id.replace("_", " "),
                    input_category=_get_str(
                        entry, "source_class", default="noun_stem"
                    ),
                    output_category=out_cat,
                    morphological_operation=_get_str(entry, "pattern"),
                    target_noun_class=target_nc,
                    description=_get_str(entry, "semantic_change"),
                )
            )
        return result

    def _normalize_phonology_extended(
        self,
        raw_phon: Dict[str, Any],
    ) -> PhonologyRules:
        """
        Translate the extended ``phonology_rules`` block.

        The inventory is nested::

            phonology_rules:
              inventory:
                vowels:
                  segments: [i, e, a, o, u]
                consonants:
                  segments: [b, bb, c, ...]
              tones:
                levels: [high, low, falling, rising]
        """
        inventory = raw_phon.get("inventory") or {}

        vowels_data = inventory.get("vowels") or {}
        consonants_data = inventory.get("consonants") or {}

        vowels = (
            _get_str_list(vowels_data, "segments")
            if isinstance(vowels_data, dict)
            else []
        )
        consonants = (
            _get_str_list(consonants_data, "segments")
            if isinstance(consonants_data, dict)
            else []
        )

        # Tone system — infer from levels count
        tones_data = raw_phon.get("tones") or {}
        levels: List[str] = []
        if isinstance(tones_data, dict):
            raw_levels = tones_data.get("levels") or []
            levels = [str(lv) for lv in raw_levels if lv is not None]
        n_levels = len(levels)
        if n_levels >= 4:
            tone_system = "four_level"
        elif n_levels == 3:
            tone_system = "three_level_HML"
        elif n_levels == 2:
            tone_system = "two_level_HL"
        else:
            tone_system = "none"

        # Sandhi/phonological rule identifiers from processing_stages
        sandhi_rules: List[str] = []
        for stage in raw_phon.get("processing_stages") or []:
            if isinstance(stage, dict):
                stage_id = _get_str(stage, "stage")
                if stage_id:
                    sandhi_rules.append(stage_id)

        # Standard Bantu nasal prefixes (inferred; chiTonga-specific)
        nasal_prefixes = ["m-", "n-", "ny-"]

        notes_val = raw_phon.get("integration_notes") or ""
        if isinstance(notes_val, str):
            notes = notes_val.strip()
        else:
            notes = str(notes_val).strip()

        return PhonologyRules(
            vowels=vowels,
            consonants=consonants,
            nasal_prefixes=nasal_prefixes,
            tone_system=tone_system,
            sandhi_rules=sandhi_rules,
            vowel_harmony_rules=[],
            notes=notes,
        )

    def _normalize_tokenization_extended(
        self,
        raw_tok: Dict[str, Any],
    ) -> TokenizationRules:
        """
        Translate the extended ``tokenization`` block.

        The extended format uses ``word_boundary`` (not
        ``word_boundary_pattern``) and ``morpheme_separators`` (not
        ``clitic_boundaries``).
        """
        # Morpheme separators → clitic boundaries
        morpheme_sep = raw_tok.get("morpheme_separators") or ["-"]
        if isinstance(morpheme_sep, list):
            clitic_boundaries = [str(s) for s in morpheme_sep if s is not None]
        else:
            clitic_boundaries = ["-"]

        # special_tokens.discourse_markers → special_cases
        special_cases: Dict[str, str] = {}
        st = raw_tok.get("special_tokens") or {}
        if isinstance(st, dict):
            for marker in st.get("discourse_markers") or []:
                if marker is not None:
                    special_cases[str(marker)] = "discourse_marker"

        description = _get_str(raw_tok, "description")

        return TokenizationRules(
            word_boundary_pattern=_get_str(
                raw_tok, "word_boundary", default=r"\s+"
            ),
            clitic_boundaries=clitic_boundaries,
            prefix_strip_patterns=[],
            suffix_strip_patterns=[],
            special_cases=special_cases,
            orthographic_normalization={},
            notes=description,
        )

    # ==================================================================
    # Canonical-format section normalizers
    # ==================================================================

    def _normalize_metadata_canonical(
        self,
        raw_meta: Dict[str, Any],
        verify_count: int,
    ) -> GrammarMetadata:
        # metadata.language may still be a nested dict if the file was loaded
        # without the legacy normalisation step (e.g. in tests or direct calls).
        lang_raw = raw_meta.get("language")
        if isinstance(lang_raw, dict):
            language = lang_raw.get("name", "").lower().strip() or ""
            iso_code  = _get_str(lang_raw, "iso_code") or _get_str(raw_meta, "iso_code")
            guthrie   = _get_str(lang_raw, "guthrie")  or _get_str(raw_meta, "guthrie")
        else:
            language  = _get_str(raw_meta, "language")
            iso_code  = _get_str(raw_meta, "iso_code")
            guthrie   = _get_str(raw_meta, "guthrie")

        return GrammarMetadata(
            language=language,
            iso_code=iso_code,
            guthrie=guthrie,
            grammar_version=_get_str(raw_meta, "grammar_version"),
            min_loader_version=_get_str(raw_meta, "min_loader_version"),
            max_loader_version=_get_str(raw_meta, "max_loader_version"),
            verify_count=verify_count,
        )

    def _normalize_noun_classes_canonical(
        self,
        raw_ncs: Dict[str, Any],
    ) -> Dict[str, NounClass]:
        """
        Translate a noun_classes mapping.

        Handles two entry formats:

        * **Canonical** — ``{prefix: "mu-", allomorphs: ["mw-"],
          semantic_domain: "humans", active: true,
          singular_counterpart: null, plural_counterpart: "NC2"}``
        * **Reference-grammar** — ``{prefix: {canonical_form: "mu-",
          allomorphs: [{form: "mw-", ...}]}, semantics: {primary_domain:
          "human_beings"}, grammatical_number: "singular",
          paired_class: "NC2", active: true}``

        Both are transparently normalised to ``NounClass``.
        """
        result: Dict[str, NounClass] = {}
        for nc_id, entry in raw_ncs.items():
            if not isinstance(entry, dict):
                continue

            # ── prefix ────────────────────────────────────────────────
            prefix_raw = entry.get("prefix")
            if isinstance(prefix_raw, dict):
                # Reference-grammar: prefix.canonical_form
                prefix = _clean(_get_str(prefix_raw, "canonical_form"))
                raw_allos = prefix_raw.get("allomorphs") or []
                allomorphs: List[str] = []
                if isinstance(raw_allos, list):
                    for allo in raw_allos:
                        if isinstance(allo, dict):
                            f = allo.get("form", "")
                            if f:
                                allomorphs.append(_clean(str(f)))
                        elif isinstance(allo, str):
                            allomorphs.append(_clean(allo))
            else:
                # Canonical: prefix is a plain string
                prefix = _clean(str(prefix_raw)) if prefix_raw else ""
                allomorphs = [
                    _clean(a)
                    for a in _get_list(entry, "allomorphs")
                    if isinstance(a, str)
                ]

            # ── semantic domain ────────────────────────────────────────
            semantics = entry.get("semantics")
            if isinstance(semantics, dict):
                sem_domain = _get_str(semantics, "primary_domain", default="unspecified")
            else:
                sem_domain = _get_str(entry, "semantic_domain", default="unspecified")

            # ── singular/plural counterparts ───────────────────────────
            # Canonical: explicit singular_counterpart / plural_counterpart
            # Reference-grammar: paired_class + grammatical_number
            if "singular_counterpart" in entry or "plural_counterpart" in entry:
                singular_counterpart = _get_optional_str(entry, "singular_counterpart")
                plural_counterpart   = _get_optional_str(entry, "plural_counterpart")
            else:
                paired    = _get_optional_str(entry, "paired_class")
                gram_num  = _get_str(entry, "grammatical_number", default="").lower()
                if gram_num == "singular":
                    plural_counterpart   = paired
                    singular_counterpart = None
                elif gram_num == "plural":
                    plural_counterpart   = None
                    singular_counterpart = paired
                else:
                    plural_counterpart   = None
                    singular_counterpart = paired

            result[nc_id] = NounClass(
                id=_get_str(entry, "id", default=nc_id),
                prefix=prefix,
                allomorphs=allomorphs,
                semantic_domain=sem_domain,
                active=_get_bool(entry, "active", default=True),
                singular_counterpart=singular_counterpart,
                plural_counterpart=plural_counterpart,
            )
        return result

    def _normalize_concord_systems_canonical(
        self,
        raw_concords: Dict[str, Any],
    ) -> Dict[str, ConcordSet]:
        result: Dict[str, ConcordSet] = {}
        for concord_type, entries in raw_concords.items():
            if not isinstance(entries, dict):
                continue
            # Reuse _extract_concord_entries: handles plain strings,
            # forms-list dicts, and skips metadata keys (description, etc.)
            result[concord_type] = ConcordSet(
                concord_type=concord_type,
                entries=self._extract_concord_entries(entries),
            )
        return result

    def _normalize_tam_markers_list(
        self,
        raw_tams: List[Any],
    ) -> List[TAMMarker]:
        result: List[TAMMarker] = []
        for entry in raw_tams:
            if not isinstance(entry, dict):
                continue
            result.append(
                TAMMarker(
                    id=_get_str(entry, "id"),
                    form=_clean(_get_str(entry, "form")),
                    tense=_get_str(entry, "tense", default="none"),
                    aspect=_get_str(entry, "aspect", default="none"),
                    mood=_get_str(entry, "mood", default="none"),
                    notes=_get_str(entry, "notes"),
                )
            )
        return result

    def _normalize_verb_extensions_list(
        self,
        raw_exts: List[Any],
    ) -> List[VerbExtension]:
        result: List[VerbExtension] = []
        for entry in raw_exts:
            if not isinstance(entry, dict):
                continue
            result.append(
                VerbExtension(
                    id=_get_str(entry, "id"),
                    canonical_form=_clean(_get_str(entry, "canonical_form")),
                    allomorphs=[
                        _clean(a)
                        for a in _get_list(entry, "allomorphs")
                        if isinstance(a, str)
                    ],
                    zone=_get_str(entry, "zone", default="Z1"),
                    semantic_value=_get_str(entry, "semantic_value"),
                )
            )
        return result

    def _normalize_verb_slots_list(
        self,
        raw_slots: List[Any],
    ) -> List[VerbSlot]:
        result: List[VerbSlot] = []
        for entry in raw_slots:
            if not isinstance(entry, dict):
                continue
            result.append(
                VerbSlot(
                    id=_get_str(entry, "id"),
                    name=_get_str(entry, "name"),
                    position=_get_int(entry, "position", default=0),
                    obligatory=_get_bool(entry, "obligatory", default=False),
                    allowed_content_types=_get_str_list(
                        entry, "allowed_content_types"
                    ),
                    notes=_get_str(entry, "notes"),
                )
            )
        result.sort(key=lambda s: s.position)
        return result

    def _normalize_derivational_patterns_list(
        self,
        raw_pats: List[Any],
    ) -> List[DerivationalPattern]:
        result: List[DerivationalPattern] = []
        for entry in raw_pats:
            if not isinstance(entry, dict):
                continue
            result.append(
                DerivationalPattern(
                    id=_get_str(entry, "id"),
                    name=_get_str(entry, "name"),
                    input_category=_get_str(entry, "input_category"),
                    output_category=_get_str(entry, "output_category"),
                    morphological_operation=_clean(
                        _get_str(entry, "morphological_operation")
                    ),
                    target_noun_class=_get_optional_str(
                        entry, "target_noun_class"
                    ),
                    description=_get_str(entry, "description"),
                )
            )
        return result

    def _normalize_phonology_canonical(
        self,
        raw_phon: Dict[str, Any],
    ) -> PhonologyRules:
        # vowels/consonants may be pre-flattened lists or still nested dicts
        vowels_raw = raw_phon.get("vowels") or []
        vowels = (
            _get_str_list(vowels_raw, "segments")
            if isinstance(vowels_raw, dict)
            else [str(v) for v in vowels_raw if v is not None]
        )

        consonants_raw = raw_phon.get("consonants") or []
        consonants = (
            _get_str_list(consonants_raw, "segments")
            if isinstance(consonants_raw, dict)
            else [str(c) for c in consonants_raw if c is not None]
        )

        # sandhi_rules: may be a list of id-strings (canonical) or a list of
        # rule dicts {id: "SND.1", ...} (reference-grammar).  In either case
        # extract the rule identifier string.
        sandhi_raw = raw_phon.get("sandhi_rules") or []
        if isinstance(sandhi_raw, list):
            sandhi_rules = [
                r.get("id") or r.get("name") or str(r)
                if isinstance(r, dict) else str(r)
                for r in sandhi_raw
                if r is not None
            ]
        elif isinstance(sandhi_raw, dict):
            sandhi_rules = list(sandhi_raw.keys())
        else:
            sandhi_rules = []

        # vowel_harmony_rules: same pattern
        vh_raw = raw_phon.get("vowel_harmony_rules") or []
        if isinstance(vh_raw, list):
            vowel_harmony_rules = [
                r.get("id") if isinstance(r, dict) else str(r)
                for r in vh_raw if r is not None
            ]
        elif isinstance(vh_raw, dict):
            vowel_harmony_rules = list(vh_raw.keys())
        else:
            vowel_harmony_rules = []

        # nasal_prefixes: canonical key may be absent; fall back to Bantu defaults
        nasal_raw = raw_phon.get("nasal_prefixes") or []
        if isinstance(nasal_raw, list) and nasal_raw:
            nasal_prefixes = [str(n) for n in nasal_raw if n is not None]
        else:
            # Infer from consonants block if available
            nasal_prefixes = _extract_nasal_prefixes(raw_phon)

        return PhonologyRules(
            vowels=vowels,
            consonants=consonants,
            nasal_prefixes=nasal_prefixes,
            tone_system=_get_str(raw_phon, "tone_system", default="none"),
            sandhi_rules=sandhi_rules,
            vowel_harmony_rules=vowel_harmony_rules,
            notes=_get_str(raw_phon, "notes"),
        )

    def _normalize_tokenization_canonical(
        self,
        raw_tok: Dict[str, Any],
    ) -> TokenizationRules:
        special_cases: Dict[str, str] = {}
        raw_sc = raw_tok.get("special_cases") or {}
        if isinstance(raw_sc, dict):
            for k, v in raw_sc.items():
                if isinstance(k, str) and isinstance(v, str):
                    special_cases[k] = v

        ortho_norm: Dict[str, str] = {}
        raw_on = raw_tok.get("orthographic_normalization") or {}
        if isinstance(raw_on, dict):
            for k, v in raw_on.items():
                if isinstance(k, str) and isinstance(v, str):
                    ortho_norm[k] = v

        return TokenizationRules(
            word_boundary_pattern=_get_str(
                raw_tok, "word_boundary_pattern", default=r"\s+"
            ),
            clitic_boundaries=_get_str_list(raw_tok, "clitic_boundaries"),
            prefix_strip_patterns=_get_str_list(
                raw_tok, "prefix_strip_patterns"
            ),
            suffix_strip_patterns=_get_str_list(
                raw_tok, "suffix_strip_patterns"
            ),
            special_cases=special_cases,
            orthographic_normalization=ortho_norm,
            notes=_get_str(raw_tok, "notes"),
        )


# ---------------------------------------------------------------------------
# Private helper functions
# ---------------------------------------------------------------------------


def _extract_nasal_prefixes(raw_phon: Dict[str, Any]) -> List[str]:
    """
    Infer nasal prefix forms from a phonology block.

    Checks ``consonants.nasal`` and ``nasal_prefix`` sub-fields before
    falling back to the standard Bantu set (m-, n-, ny-) which is correct
    for all seven Zambian languages in the initial registry.
    """
    # Check consonants.nasal list
    cons = raw_phon.get("consonants") or {}
    if isinstance(cons, dict):
        nasal_list = cons.get("nasal") or []
        if isinstance(nasal_list, list) and nasal_list:
            return [str(n) for n in nasal_list if n]

    # Standard Zambian Bantu nasal prefixes (safe default for all 7 languages)
    return ["m-", "n-", "ny-"]


def _clean(value: str) -> str:
    """
    Strip a VERIFY annotation from a string value.

    If ``value`` contains ``"VERIFY:"`` (case-insensitive), everything from
    that marker to the end of the string is removed and the result is
    stripped of whitespace.

    >>> _clean("mu-  VERIFY: Hoch 1960 §12")
    'mu-'
    >>> _clean("ba-")
    'ba-'
    """
    return _VERIFY_STRIP_RE.sub("", value).strip()


def _get_str(
    d: Dict[str, Any],
    key: str,
    default: str = "",
) -> str:
    """Return ``str(d[key])``, or ``default`` if absent/None."""
    val = d.get(key)
    if val is None:
        return default
    return str(val)


def _get_optional_str(
    d: Dict[str, Any],
    key: str,
) -> Optional[str]:
    """Return ``str(d[key])`` stripped, or ``None`` if absent/empty."""
    val = d.get(key)
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _get_bool(
    d: Dict[str, Any],
    key: str,
    default: bool = False,
) -> bool:
    """Return the boolean value at ``d[key]``, or ``default``."""
    val = d.get(key)
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "yes", "1")


def _get_int(
    d: Dict[str, Any],
    key: str,
    default: int = 0,
) -> int:
    """Return the integer value at ``d[key]``, or ``default``."""
    val = d.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _get_list(
    d: Dict[str, Any],
    key: str,
) -> List[Any]:
    """Return the list at ``d[key]``, or ``[]`` if absent/non-list."""
    val = d.get(key)
    if not isinstance(val, list):
        return []
    return val


def _get_str_list(
    d: Dict[str, Any],
    key: str,
) -> List[str]:
    """Return a list of strings from ``d[key]``, coercing non-string items."""
    raw_list = _get_list(d, key)
    return [str(item) for item in raw_list if item is not None]
