"""
apps/ud_feature_mapper.py
==========================
UDFeatureMapper — map GGT morphological analysis to Universal Dependencies
(UD) FEATS column values for use in UD treebank construction.

This module implements the core of GGT Feature F-07.  Given a
``SegmentedToken`` produced by ``MorphologicalAnalyzer`` (F-02), it yields
a ``UDFeatureBundle`` whose fields are UD-compliant strings suitable for the
CoNLL-U ``FEATS`` column.  Individual mapping methods (``map_nc``,
``map_tam``, ``map_concord_key``, ``map_extension``) are also exposed so that
higher-level pipelines can map a single piece of grammar without constructing
a full ``SegmentedToken``.

Universal Dependencies Bantu guidelines
----------------------------------------
Bantu languages are covered by the UD Bantu extension documented in:

    Zeman et al. (2021). *Universal Dependencies 2.8*,
    LINDAT/CLARIAH-CZ digital library.

Key UD features used for Bantu:

``Nounclass``
    The Bantu noun-class index, expressed as ``Bantu1`` – ``Bantu23``
    following the Bleek–Meinhof convention.  The numeric index is derived
    from the GGT ``NounClass.id`` field (``"NC7"`` → ``Bantu7``).  Subclass
    suffixes (``"NC1a"`` → ``Bantu1``) are stripped.

``Number``
    ``Sing`` for singular-counterpart classes; ``Plur`` for plural-counterpart
    classes.  Derived from ``NounClass.plural_counterpart`` /
    ``NounClass.singular_counterpart``.  Locative and abstract classes
    (NC14–NC18) receive no ``Number`` value.

``Person``
    ``1``, ``2``, or ``3``.  Derived from subject/object concord keys whose
    identifier begins with a digit (``"1SG"``, ``"2PL"``, ``"3PL_HUMAN"``).
    Noun-class concord keys map to ``Person=3`` by UD convention.

``Tense``
    Derived from ``TAMMarker.tense``:

    ============  ===========
    GGT value     UD value
    ============  ===========
    present       Pres
    immediate_past Past
    remote_past   Past
    immediate_future Fut
    remote_future Fut
    none          (omitted)
    ============  ===========

``Aspect``
    Derived from ``TAMMarker.aspect``:

    ============  ===========
    GGT value     UD value
    ============  ===========
    imperfective  Imp
    perfective    Perf
    habitual      Hab
    progressive   Prog
    stative       (omitted — handled by StatPred)
    none          (omitted)
    ============  ===========

``Mood``
    Derived from ``TAMMarker.mood``:

    ============  ===========
    GGT value     UD value
    ============  ===========
    indicative    Ind
    subjunctive   Sub
    imperative    Imp
    conditional   Cnd
    persistive    (omitted — no direct UD equivalent; flagged as warning)
    none          (omitted)
    ============  ===========

``Voice``
    Derived from verb-extension semantics.  The mapper inspects each
    ``VerbExtension``'s ``semantic_value`` and ``id`` to infer UD voice:

    ============  ===========
    Extension id  UD Voice
    ============  ===========
    PASS          Pass
    CAUS          Caus
    APPL          Appl
    RECIP         Rcp
    REFL*         Rfl
    (none)        Act
    ============  ===========

``Polarity``
    ``Neg`` for negation morphemes (detected by gloss containing ``NEG``);
    otherwise omitted (``Pos`` is the UD default and is not written).

CoNLL-U output format
----------------------
``UDFeatureMapper.to_conllu_feats(bundle)`` returns the UD ``FEATS`` string
in alphabetical feature order, e.g.::

    Aspect=Perf|Mood=Ind|Nounclass=Bantu7|Number=Sing|Person=3|Tense=Past|Voice=Appl

An empty feature set is rendered as ``_`` per the CoNLL-U spec.

Design contract (Part 9)
-------------------------
* Accepts a ``GobeloGrammarLoader`` as its **only** grammar dependency.
* Uses **only** the public API (Part 6).
* Language-agnostic — all mapping tables are derived from loader data.
* Handles ``GGTError`` subclasses gracefully (degrades to partial mapping
  with warning strings in ``UDFeatureBundle.warnings``).

Usage
------
::

    from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    from gobelo_grammar_toolkit.apps.morphological_analyzer import (
        MorphologicalAnalyzer, MorphFeatureBundle,
    )
    from gobelo_grammar_toolkit.apps.ud_feature_mapper import UDFeatureMapper

    loader   = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    analyzer = MorphologicalAnalyzer(loader)
    mapper   = UDFeatureMapper(loader)

    tok = analyzer.analyze("cilya")
    bundle = mapper.map_segmented_token(tok)
    print(mapper.to_conllu_feats(bundle))
    # Nounclass=Bantu7|Number=Sing|Person=3|Tense=Pres|Voice=Act

    # Direct NC mapping
    nc_feat = mapper.map_nc("NC7")
    print(nc_feat.nounclass)    # "Bantu7"
    print(nc_feat.number)       # "Sing"

    # Direct TAM mapping
    tam_feat = mapper.map_tam("TAM_PST")
    print(tam_feat.tense)       # "Past"
    print(tam_feat.aspect)      # "Perf"
    print(tam_feat.mood)        # "Ind"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Tuple

from gobelo_grammar_toolkit.core.exceptions import GGTError

__all__ = [
    "UDFeatureMapper",
    "UDNounClassFeatures",
    "UDTAMFeatures",
    "UDConcordFeatures",
    "UDVoiceFeature",
    "UDFeatureBundle",
    "UDMappingError",
]

# ---------------------------------------------------------------------------
# UD vocabulary constants
# ---------------------------------------------------------------------------

# Tense
_UD_TENSE: Dict[str, str] = {
    "present":          "Pres",
    "immediate_past":   "Past",
    "remote_past":      "Past",
    "immediate_future": "Fut",
    "remote_future":    "Fut",
}

# Aspect
_UD_ASPECT: Dict[str, str] = {
    "imperfective": "Imp",
    "perfective":   "Perf",
    "habitual":     "Hab",
    "progressive":  "Prog",
}

# Mood
_UD_MOOD: Dict[str, str] = {
    "indicative":  "Ind",
    "subjunctive": "Sub",
    "imperative":  "Imp",
    "conditional": "Cnd",
}

# Voice — derived from VerbExtension.id (canonical) and semantic_value (fallback)
_UD_VOICE_BY_ID: Dict[str, str] = {
    "PASS":  "Pass",
    "CAUS":  "Caus",
    "APPL":  "Appl",
    "RECIP": "Rcp",
    "RECP":  "Rcp",
}

# Semantic keywords that indicate a particular voice even if ID is not in the map
_VOICE_SEMANTIC_KEYWORDS: List[Tuple[str, str]] = [
    ("passive",        "Pass"),
    ("agent demotion", "Pass"),
    ("caus",           "Caus"),
    ("beneficiar",     "Appl"),
    ("applicat",       "Appl"),
    ("reciproc",       "Rcp"),
    ("reflexive",      "Rfl"),
]

# Regex for extracting a numeric noun-class index from an id like "NC7", "NC1a", "NC10"
_NC_NUM_RE = re.compile(r"^[A-Za-z]+(\d+)", re.ASCII)

# Person labels: keys that begin with a digit are personal
_PERSON_LABEL_RE = re.compile(r"^([123])(?:SG|PL|PL_[A-Z]+)$", re.ASCII)

# Number from person key
_PL_KEY_RE = re.compile(r"PL", re.ASCII)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UDMappingError(GGTError):
    """
    Raised when the UD mapper encounters an unrecoverable error — for
    example, a TAM id that does not exist in the grammar.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


# ---------------------------------------------------------------------------
# Typed result dataclasses (all frozen — immutable UD values)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UDNounClassFeatures:
    """
    UD features derived from a Bantu noun class.

    Parameters
    ----------
    nc_id : str
        The original GGT noun-class identifier (e.g. ``"NC7"``).
    nounclass : Optional[str]
        UD ``Nounclass`` value, e.g. ``"Bantu7"``.  ``None`` if the id
        could not be parsed to a Bantu class number.
    number : Optional[str]
        UD ``Number`` value: ``"Sing"`` or ``"Plur"``.  ``None`` for
        abstract/infinitive/locative classes (NC14–NC18) and subclasses
        that do not participate in number contrasts.
    gender : Optional[str]
        Always ``None`` for Bantu (Bantu languages use noun classes rather
        than grammatical gender); included for CoNLL-U schema compatibility.
    warnings : Tuple[str, ...]
        Non-fatal mapping issues, e.g. when a subclass suffix is stripped
        or when number cannot be determined from the grammar data.
    """

    nc_id: str
    nounclass: Optional[str]
    number: Optional[str]
    gender: Optional[str]
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class UDTAMFeatures:
    """
    UD features derived from a GGT ``TAMMarker``.

    Parameters
    ----------
    tam_id : str
        The original GGT TAM marker identifier.
    tense : Optional[str]
        UD ``Tense`` value: ``"Pres"``, ``"Past"``, ``"Fut"``.  ``None``
        when the TAM marker does not encode tense (e.g. pure aspect markers).
    aspect : Optional[str]
        UD ``Aspect`` value: ``"Imp"``, ``"Perf"``, ``"Hab"``, ``"Prog"``.
        ``None`` when not applicable.
    mood : Optional[str]
        UD ``Mood`` value: ``"Ind"``, ``"Sub"``, ``"Imp"``, ``"Cnd"``.
        ``None`` when not applicable.
    warnings : Tuple[str, ...]
        Non-fatal mapping issues, e.g. when a GGT value (``"persistive"``)
        has no direct UD equivalent.
    """

    tam_id: str
    tense: Optional[str]
    aspect: Optional[str]
    mood: Optional[str]
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class UDConcordFeatures:
    """
    UD Person and Number features derived from a subject or object
    concord key.

    Parameters
    ----------
    concord_key : str
        The original GGT concord key, e.g. ``"1SG"``, ``"NC7"``,
        ``"3PL_HUMAN"``.
    concord_type : str
        The concord paradigm name, e.g. ``"subject_concords"``.
    person : Optional[str]
        UD ``Person`` value: ``"1"``, ``"2"``, or ``"3"``.  Noun-class
        keyed concords are always ``"3"`` by UD convention.
    number : Optional[str]
        UD ``Number`` value: ``"Sing"`` or ``"Plur"``.
    warnings : Tuple[str, ...]
    """

    concord_key: str
    concord_type: str
    person: Optional[str]
    number: Optional[str]
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class UDVoiceFeature:
    """
    UD ``Voice`` feature derived from a GGT ``VerbExtension``.

    Parameters
    ----------
    ext_id : str
        The original GGT extension identifier, e.g. ``"PASS"``.
    voice : str
        UD ``Voice`` value: ``"Pass"``, ``"Caus"``, ``"Appl"``, ``"Rcp"``,
        ``"Rfl"``, or ``"Act"`` (active — when no voice-marking extension is
        present).
    warnings : Tuple[str, ...]
    """

    ext_id: str
    voice: str
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class UDFeatureBundle:
    """
    The complete UD feature set for a single analysed word token.

    All feature fields follow UD conventions for the FEATS column of a
    CoNLL-U file.  A ``None`` value means the feature is not applicable or
    could not be determined; it is omitted from the CoNLL-U string.

    Parameters
    ----------
    token : str
        The original surface token that was analysed.
    language : str
        The language identifier from the grammar loader.
    nounclass : Optional[str]
        UD ``Nounclass``, e.g. ``"Bantu7"``.
    number : Optional[str]
        UD ``Number``: ``"Sing"`` or ``"Plur"``.
    person : Optional[str]
        UD ``Person``: ``"1"``, ``"2"``, or ``"3"``.
    tense : Optional[str]
        UD ``Tense``: ``"Pres"``, ``"Past"``, ``"Fut"``.
    aspect : Optional[str]
        UD ``Aspect``: ``"Imp"``, ``"Perf"``, ``"Hab"``, ``"Prog"``.
    mood : Optional[str]
        UD ``Mood``: ``"Ind"``, ``"Sub"``, ``"Imp"``, ``"Cnd"``.
    voice : Optional[str]
        UD ``Voice``: ``"Act"``, ``"Pass"``, ``"Caus"``, ``"Appl"``,
        ``"Rcp"``, ``"Rfl"``.
    polarity : Optional[str]
        UD ``Polarity``: ``"Neg"`` only (``"Pos"`` is the UD default and
        is not written to the FEATS column).
    gender : Optional[str]
        Always ``None`` for Bantu; included for schema compatibility.
    source_nc_id : Optional[str]
        The GGT noun-class id that produced the ``nounclass`` value.
    source_tam_id : Optional[str]
        The GGT TAM id that produced the ``tense`` / ``aspect`` / ``mood``.
    source_ext_ids : Tuple[str, ...]
        The GGT extension ids that contributed to ``voice``.
    warnings : Tuple[str, ...]
        Accumulated non-fatal mapping warnings from all sub-mappings.
    """

    token: str
    language: str
    nounclass: Optional[str]
    number: Optional[str]
    person: Optional[str]
    tense: Optional[str]
    aspect: Optional[str]
    mood: Optional[str]
    voice: Optional[str]
    polarity: Optional[str]
    gender: Optional[str]
    source_nc_id: Optional[str]
    source_tam_id: Optional[str]
    source_ext_ids: Tuple[str, ...]
    warnings: Tuple[str, ...]


# ---------------------------------------------------------------------------
# UDFeatureMapper
# ---------------------------------------------------------------------------


class UDFeatureMapper:
    """
    Language-agnostic mapper from GGT grammar analysis to Universal
    Dependencies FEATS values.

    All mapping tables are derived from the ``GobeloGrammarLoader`` public
    API at construction time.  The mapper holds no grammar data after init
    other than what is strictly required for mapping — it does not cache
    the loader itself beyond index construction.

    Parameters
    ----------
    loader : GobeloGrammarLoader
        An initialised loader for the target language.  Queried once in
        ``__init__``; not referenced during mapping calls.

    Raises
    ------
    UDMappingError
        If ``GGTError`` is raised during index construction (e.g. a stub
        grammar that is missing a required section).

    Examples
    --------
    >>> from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    >>> from gobelo_grammar_toolkit.apps.ud_feature_mapper import UDFeatureMapper
    >>> loader = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    >>> mapper = UDFeatureMapper(loader)
    >>> feat = mapper.map_nc("NC7")
    >>> feat.nounclass
    'Bantu7'
    >>> feat.number
    'Sing'
    """

    def __init__(self, loader) -> None:  # type: ignore[no-untyped-def]
        try:
            self._build_indexes(loader)
        except GGTError as exc:
            raise UDMappingError(
                f"Failed to build UD mapping indexes: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_indexes(self, loader) -> None:  # type: ignore[no-untyped-def]
        meta = loader.get_metadata()
        self._language: str = meta.language

        # ── Noun classes ──────────────────────────────────────────────
        # _nc_index: nc_id → NounClass
        self._nc_index: Dict[str, object] = {}
        try:
            for nc in loader.get_noun_classes(active_only=False):
                self._nc_index[nc.id] = nc
        except GGTError:
            pass

        # ── TAM markers ───────────────────────────────────────────────
        # _tam_index: tam_id → TAMMarker
        self._tam_index: Dict[str, object] = {}
        try:
            for tam in loader.get_tam_markers():
                self._tam_index[tam.id] = tam
        except GGTError:
            pass

        # ── Verb extensions ───────────────────────────────────────────
        # _ext_index: ext_id → VerbExtension
        self._ext_index: Dict[str, object] = {}
        try:
            for ext in loader.get_extensions():
                self._ext_index[ext.id] = ext
        except GGTError:
            pass

        # ── Subject/object concord key sets ───────────────────────────
        # Used for Person resolution when the concord_key is NC-indexed
        self._subject_concord_keys: FrozenSet[str] = frozenset()
        self._object_concord_keys: FrozenSet[str] = frozenset()
        try:
            sc = loader.get_subject_concords()
            self._subject_concord_keys = frozenset(sc.entries.keys())
        except GGTError:
            pass
        try:
            oc = loader.get_object_concords()
            self._object_concord_keys = frozenset(oc.entries.keys())
        except GGTError:
            pass

        # Determine which NC ids are plural (have singular_counterpart)
        # Used for Number derivation in map_concord_key
        self._plural_nc_ids: FrozenSet[str] = frozenset(
            nc_id
            for nc_id, nc in self._nc_index.items()  # type: ignore[union-attr]
            if getattr(nc, "singular_counterpart", None) is not None
        )

    # ------------------------------------------------------------------
    # Static mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_bantu_class(nc_id: str) -> Optional[str]:
        """
        Convert a GGT noun-class id to a UD ``Nounclass`` value.

        ``"NC7"`` → ``"Bantu7"``, ``"NC1a"`` → ``"Bantu1"``,
        ``"NC2b"`` → ``"Bantu2"``.  Returns ``None`` if no numeric
        index can be parsed.
        """
        m = _NC_NUM_RE.match(nc_id)
        if m:
            return f"Bantu{m.group(1)}"
        return None

    @staticmethod
    def _parse_person_number(key: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract UD Person and Number from a concord key string.

        Examples
        --------
        ``"1SG"``        → ``("1", "Sing")``
        ``"2PL"``        → ``("2", "Plur")``
        ``"3PL_HUMAN"``  → ``("3", "Plur")``
        ``"1PL_EXCL"``   → ``("1", "Plur")``
        ``"NC7"``        → ``("3", None)``  (UD convention: noun class = 3rd person)
        ``"NEG.SG"``     → ``(None, "Sing")``
        """
        m = _PERSON_LABEL_RE.match(key)
        if m:
            person = m.group(1)
            number = "Plur" if "PL" in key else "Sing"
            return person, number

        # Patterns like "1PL_EXCL", "1PL_INCL" — not matched by simple regex
        first = key.split("_")[0]
        if first in ("1PL", "2PL", "3PL"):
            return first[0], "Plur"
        if first in ("1SG", "2SG", "3SG"):
            return first[0], "Sing"

        # Noun-class keyed concord → always Person=3
        if _NC_NUM_RE.match(key):
            return "3", None

        # NEG labels
        if key.startswith("NEG"):
            number = "Sing" if "SG" in key else ("Plur" if "PL" in key else None)
            return None, number

        return None, None

    @staticmethod
    def _voice_from_extension(ext_id: str, semantic_value: str) -> str:
        """
        Derive a UD ``Voice`` value from a ``VerbExtension``.

        First checks ``_UD_VOICE_BY_ID``; falls back to keyword scan of
        ``semantic_value`` for extensions whose id is not directly mapped.
        Returns ``"Act"`` when neither check succeeds.
        """
        if ext_id in _UD_VOICE_BY_ID:
            return _UD_VOICE_BY_ID[ext_id]
        sem_lower = semantic_value.lower()
        for keyword, voice in _VOICE_SEMANTIC_KEYWORDS:
            if keyword in sem_lower:
                return voice
        return "Act"  # default: active (not voice-marking)

    # ------------------------------------------------------------------
    # Public mapping methods
    # ------------------------------------------------------------------

    def map_nc(self, nc_id: str) -> UDNounClassFeatures:
        """
        Map a GGT noun-class identifier to UD ``Nounclass`` and ``Number``.

        Parameters
        ----------
        nc_id : str
            A noun-class identifier as returned by ``NounClass.id``, e.g.
            ``"NC7"``, ``"NC1a"``, ``"NC2b"``.

        Returns
        -------
        UDNounClassFeatures

        Raises
        ------
        UDMappingError
            If ``nc_id`` is not present in the loaded grammar and cannot be
            parsed to a Bantu class number.

        Examples
        --------
        >>> mapper.map_nc("NC7")
        UDNounClassFeatures(nc_id='NC7', nounclass='Bantu7', number='Sing', ...)
        >>> mapper.map_nc("NC2")
        UDNounClassFeatures(nc_id='NC2', nounclass='Bantu2', number='Plur', ...)
        """
        warnings: List[str] = []
        nounclass = self._parse_bantu_class(nc_id)
        if nounclass is None:
            raise UDMappingError(
                f"Cannot derive a Bantu class number from nc_id {nc_id!r}."
            )

        # Subclass suffix stripped → warn
        base_numeric = _NC_NUM_RE.match(nc_id)
        if base_numeric and nc_id != f"NC{base_numeric.group(1)}":
            warnings.append(
                f"Subclass suffix stripped from {nc_id!r} → mapped as "
                f"{nounclass!r}.  Subclass {nc_id!r} may have distinct "
                f"agreement behaviour not captured by the Bantu class number."
            )

        # Number from grammar data if nc is in the index
        number: Optional[str] = None
        nc_obj = self._nc_index.get(nc_id)
        if nc_obj is None:
            # Try base class
            base_id = f"NC{base_numeric.group(1)}" if base_numeric else nc_id
            nc_obj = self._nc_index.get(base_id)

        if nc_obj is not None:
            sg_counterpart = getattr(nc_obj, "singular_counterpart", None)
            pl_counterpart = getattr(nc_obj, "plural_counterpart", None)
            if sg_counterpart is not None:
                number = "Plur"
            elif pl_counterpart is not None:
                number = "Sing"
            else:
                warnings.append(
                    f"{nc_id!r} has no singular/plural counterpart in the "
                    f"grammar (abstract, infinitive, or locative class); "
                    f"UD Number omitted."
                )
        else:
            warnings.append(
                f"{nc_id!r} not found in loaded grammar; Number derived "
                f"from id pattern only (not available)."
            )

        return UDNounClassFeatures(
            nc_id=nc_id,
            nounclass=nounclass,
            number=number,
            gender=None,  # Bantu does not use grammatical gender
            warnings=tuple(warnings),
        )

    def map_tam(self, tam_id: str) -> UDTAMFeatures:
        """
        Map a GGT ``TAMMarker.id`` to UD ``Tense``, ``Aspect``, and ``Mood``.

        Parameters
        ----------
        tam_id : str
            A TAM marker identifier as returned by ``TAMMarker.id``, e.g.
            ``"TAM_PRES"``, ``"TAM_PST"``.

        Returns
        -------
        UDTAMFeatures

        Raises
        ------
        UDMappingError
            If ``tam_id`` is not in the loaded grammar.

        Examples
        --------
        >>> mapper.map_tam("TAM_PST")
        UDTAMFeatures(tam_id='TAM_PST', tense='Past', aspect='Perf', mood='Ind', ...)
        """
        tam_obj = self._tam_index.get(tam_id)
        if tam_obj is None:
            available = sorted(self._tam_index.keys())
            raise UDMappingError(
                f"TAM id {tam_id!r} not found in grammar for "
                f"{self._language!r}.  Available: {available}"
            )

        warnings: List[str] = []

        tense = _UD_TENSE.get(getattr(tam_obj, "tense", "none"), None)
        aspect = _UD_ASPECT.get(getattr(tam_obj, "aspect", "none"), None)
        mood = _UD_MOOD.get(getattr(tam_obj, "mood", "none"), None)

        raw_tense = getattr(tam_obj, "tense", "none")
        raw_aspect = getattr(tam_obj, "aspect", "none")
        raw_mood = getattr(tam_obj, "mood", "none")

        if raw_tense not in ("none", "") and tense is None:
            warnings.append(
                f"GGT tense value {raw_tense!r} for {tam_id!r} has no "
                f"direct UD Tense mapping; omitted."
            )
        if raw_aspect not in ("none", "", "stative") and aspect is None:
            warnings.append(
                f"GGT aspect value {raw_aspect!r} for {tam_id!r} has no "
                f"direct UD Aspect mapping; omitted."
            )
        if raw_mood == "persistive":
            warnings.append(
                f"GGT mood 'persistive' for {tam_id!r} has no UD equivalent "
                f"(UD does not define a Persistive mood); omitted."
            )
        elif raw_mood not in ("none", "") and mood is None:
            warnings.append(
                f"GGT mood value {raw_mood!r} for {tam_id!r} has no "
                f"direct UD Mood mapping; omitted."
            )

        return UDTAMFeatures(
            tam_id=tam_id,
            tense=tense,
            aspect=aspect,
            mood=mood,
            warnings=tuple(warnings),
        )

    def map_concord_key(
        self,
        concord_key: str,
        concord_type: str = "subject_concords",
    ) -> UDConcordFeatures:
        """
        Map a GGT subject- or object-concord key to UD ``Person`` and
        ``Number``.

        Parameters
        ----------
        concord_key : str
            A key from a ``ConcordSet.entries`` dict, e.g. ``"1SG"``,
            ``"NC7"``, ``"3PL_HUMAN"``, ``"NEG.SG"``.
        concord_type : str
            The concord paradigm name (used for provenance only, not for
            the mapping logic itself).  Defaults to ``"subject_concords"``.

        Returns
        -------
        UDConcordFeatures

        Examples
        --------
        >>> mapper.map_concord_key("1SG")
        UDConcordFeatures(concord_key='1SG', ..., person='1', number='Sing', ...)
        >>> mapper.map_concord_key("NC7")
        UDConcordFeatures(concord_key='NC7', ..., person='3', number='Sing', ...)
        >>> mapper.map_concord_key("3PL_HUMAN")
        UDConcordFeatures(concord_key='3PL_HUMAN', ..., person='3', number='Plur', ...)
        """
        warnings: List[str] = []
        person, number = self._parse_person_number(concord_key)

        # For NC-keyed concords, try to derive number from the grammar
        if person == "3" and number is None and _NC_NUM_RE.match(concord_key):
            nc_obj = self._nc_index.get(concord_key)
            if nc_obj is not None:
                sg = getattr(nc_obj, "singular_counterpart", None)
                pl = getattr(nc_obj, "plural_counterpart", None)
                if sg is not None:
                    number = "Plur"
                elif pl is not None:
                    number = "Sing"

        if person is None and number is None:
            warnings.append(
                f"Could not derive UD Person or Number from concord key "
                f"{concord_key!r}; both values omitted."
            )
        elif person is None:
            warnings.append(
                f"Could not derive UD Person from concord key "
                f"{concord_key!r}; Person omitted."
            )
        elif number is None:
            warnings.append(
                f"Could not derive UD Number from concord key "
                f"{concord_key!r}; Number omitted."
            )

        return UDConcordFeatures(
            concord_key=concord_key,
            concord_type=concord_type,
            person=person,
            number=number,
            warnings=tuple(warnings),
        )

    def map_extension(self, ext_id: str) -> UDVoiceFeature:
        """
        Map a GGT ``VerbExtension.id`` to a UD ``Voice`` value.

        Parameters
        ----------
        ext_id : str
            A verb-extension identifier, e.g. ``"PASS"``, ``"CAUS"``,
            ``"APPL"``.

        Returns
        -------
        UDVoiceFeature

        Raises
        ------
        UDMappingError
            If ``ext_id`` is not present in the loaded grammar.

        Examples
        --------
        >>> mapper.map_extension("PASS")
        UDVoiceFeature(ext_id='PASS', voice='Pass', ...)
        >>> mapper.map_extension("APPL")
        UDVoiceFeature(ext_id='APPL', voice='Appl', ...)
        >>> mapper.map_extension("INTENS")
        UDVoiceFeature(ext_id='INTENS', voice='Act', ...)  # no voice marking
        """
        ext_obj = self._ext_index.get(ext_id)
        if ext_obj is None:
            available = sorted(self._ext_index.keys())
            raise UDMappingError(
                f"Extension id {ext_id!r} not found in grammar for "
                f"{self._language!r}.  Available: {available}"
            )

        sem = getattr(ext_obj, "semantic_value", "")
        voice = self._voice_from_extension(ext_id, sem)

        warnings: List[str] = []
        if voice == "Act" and ext_id not in _UD_VOICE_BY_ID:
            warnings.append(
                f"Extension {ext_id!r} (semantic: {str(sem)[:60]!r}) is not a "
                f"voice-marking extension; mapped as Voice=Act by default."
            )

        return UDVoiceFeature(
            ext_id=ext_id,
            voice=voice,
            warnings=tuple(warnings),
        )

    # ------------------------------------------------------------------
    # Full token mapping (F-07 primary entry point)
    # ------------------------------------------------------------------

    def map_segmented_token(self, token) -> UDFeatureBundle:  # type: ignore[no-untyped-def]
        """
        Map a ``SegmentedToken`` (from ``MorphologicalAnalyzer``) to a full
        ``UDFeatureBundle``.

        Uses the **best** parse hypothesis from the token.  If the token
        has no hypotheses, all feature fields are ``None``.

        The method reads ``Morpheme.content_type``, ``Morpheme.nc_id``,
        and ``Morpheme.gloss`` from the hypothesis morphemes to determine
        which UD features to fill.

        Parameters
        ----------
        token : SegmentedToken
            Output of ``MorphologicalAnalyzer.analyze()``.

        Returns
        -------
        UDFeatureBundle

        Examples
        --------
        >>> tok = analyzer.analyze("cilya")
        >>> bundle = mapper.map_segmented_token(tok)
        >>> bundle.nounclass
        'Bantu7'
        >>> bundle.tense
        'Pres'
        >>> mapper.to_conllu_feats(bundle)
        'Nounclass=Bantu7|Number=Sing|Person=3|Tense=Pres|Voice=Act'
        """
        warnings: List[str] = []

        # Fallback bundle for tokenless / hypothesisless input
        _empty = UDFeatureBundle(
            token=getattr(token, "token", ""),
            language=self._language,
            nounclass=None,
            number=None,
            person=None,
            tense=None,
            aspect=None,
            mood=None,
            voice=None,
            polarity=None,
            gender=None,
            source_nc_id=None,
            source_tam_id=None,
            source_ext_ids=(),
            warnings=("No parse hypothesis available.",),
        )

        best = getattr(token, "best", None)
        if best is None:
            return _empty

        morphemes = getattr(best, "morphemes", ())

        nounclass: Optional[str] = None
        number: Optional[str] = None
        person: Optional[str] = None
        tense: Optional[str] = None
        aspect: Optional[str] = None
        mood: Optional[str] = None
        voice: Optional[str] = None
        polarity: Optional[str] = None
        source_nc_id: Optional[str] = None
        source_tam_id: Optional[str] = None
        source_ext_ids: List[str] = []
        voice_morphemes: List[str] = []  # extension ids found

        for morph in morphemes:
            ct = getattr(morph, "content_type", "")
            gloss = getattr(morph, "gloss", "")
            nc_id = getattr(morph, "nc_id", None)

            # ── Subject concord ──────────────────────────────────────
            if ct == "subject_concord":
                # Derive Nounclass from nc_id if present
                if nc_id and _NC_NUM_RE.match(nc_id):
                    try:
                        nc_feat = self.map_nc(nc_id)
                        if nounclass is None:
                            nounclass = nc_feat.nounclass
                            source_nc_id = nc_id
                        if number is None:
                            number = nc_feat.number
                        warnings.extend(nc_feat.warnings)
                    except UDMappingError as exc:
                        warnings.append(str(exc))

                # Always derive Person/Number from the concord key
                # The concord key is in the gloss: "NC7.SUBJ" → "NC7",
                # "3PL_HUMAN.SUBJ" → "3PL_HUMAN", "1SG.SUBJ" → "1SG"
                ck = gloss.split(".")[0] if "." in gloss else gloss
                try:
                    cf = self.map_concord_key(ck, "subject_concords")
                    if person is None:
                        person = cf.person
                    # Number from concord key only overwrites if not yet set
                    # from noun class (NC-derived number is more authoritative)
                    if number is None:
                        number = cf.number
                    warnings.extend(cf.warnings)
                except GGTError as exc:
                    warnings.append(str(exc))

            # ── Object concord ───────────────────────────────────────
            elif ct == "object_concord":
                ck = gloss.split(".")[0] if "." in gloss else gloss
                # Object concord also informs Nounclass/Number of the object
                # but UD convention for verbs prioritises the subject
                # so we only fill if not already set from SC
                if nc_id and _NC_NUM_RE.match(nc_id) and nounclass is None:
                    try:
                        nc_feat = self.map_nc(nc_id)
                        nounclass = nc_feat.nounclass
                        source_nc_id = nc_id
                        if number is None:
                            number = nc_feat.number
                        warnings.extend(nc_feat.warnings)
                    except UDMappingError as exc:
                        warnings.append(str(exc))

            # ── TAM marker ───────────────────────────────────────────
            elif ct == "tam_marker":
                # Gloss is a short string like "PST.PFV"; look up by id
                # via the full TAM id in _tam_index where gloss == label
                # Fall back to scanning _tam_index for a matching gloss label
                tam_id_found = self._find_tam_id_by_gloss(gloss)
                if tam_id_found:
                    try:
                        tf = self.map_tam(tam_id_found)
                        if tense is None:
                            tense = tf.tense
                        if aspect is None:
                            aspect = tf.aspect
                        if mood is None:
                            mood = tf.mood
                        source_tam_id = tam_id_found
                        warnings.extend(tf.warnings)
                    except UDMappingError as exc:
                        warnings.append(str(exc))

            # ── Verb extension ───────────────────────────────────────
            elif ct == "verb_extension":
                ext_id = gloss  # extension gloss is the extension id
                if ext_id in self._ext_index:
                    try:
                        vf = self.map_extension(ext_id)
                        voice_morphemes.append(ext_id)
                        source_ext_ids.append(ext_id)
                        warnings.extend(vf.warnings)
                    except UDMappingError as exc:
                        warnings.append(str(exc))

            # ── Noun prefix (nominal token) ──────────────────────────
            elif ct == "noun_prefix":
                if nc_id and _NC_NUM_RE.match(nc_id) and nounclass is None:
                    try:
                        nc_feat = self.map_nc(nc_id)
                        nounclass = nc_feat.nounclass
                        source_nc_id = nc_id
                        number = nc_feat.number
                        person = "3"  # nouns are 3rd person
                        warnings.extend(nc_feat.warnings)
                    except UDMappingError as exc:
                        warnings.append(str(exc))

            # ── Override (v2 extra_slots fill) ───────────────────────
            # Morphemes produced by SlotFiller via MorphFeatureBundle.extra_slots
            # carry content_type="override".  They participate in verbal-morpheme
            # detection (so Voice=Act is not suppressed) but must not be
            # misread as negation or subject concords via gloss inspection.
            elif ct == "override":
                pass  # slot-filling override: skip all sub-mapping

            # ── Negation ─────────────────────────────────────────────
            elif ct in ("negation", "negation_pre", "negation_infix"):
                polarity = "Neg"
            elif "NEG" in gloss.upper() and ct == "subject_concord":
                polarity = "Neg"

        # Resolve voice from collected extensions
        # Priority: Pass > Caus > Appl > Rcp > Rfl > Act
        _voice_priority = ["Pass", "Caus", "Appl", "Rcp", "Rfl", "Act"]
        if voice_morphemes:
            candidate_voices = []
            for ext_id in voice_morphemes:
                try:
                    vf = self.map_extension(ext_id)
                    candidate_voices.append(vf.voice)
                except UDMappingError:
                    pass
            for v in _voice_priority:
                if v in candidate_voices:
                    voice = v
                    break
            if voice is None and candidate_voices:
                voice = candidate_voices[0]
        else:
            # No extension → active voice (only set if this is a verbal token)
            # We detect verbal tokens by presence of a subject concord or TAM,
            # or an override morpheme (v2 extra_slots fill occupying a verb slot).
            has_verbal_morpheme = any(
                getattr(m, "content_type", "") in (
                    "subject_concord", "tam_marker", "verb_root", "final_vowel",
                    "override",  # v2: extra_slots slot fills count as verbal evidence
                )
                for m in morphemes
            )
            if has_verbal_morpheme:
                voice = "Act"

        return UDFeatureBundle(
            token=getattr(token, "token", ""),
            language=self._language,
            nounclass=nounclass,
            number=number,
            person=person,
            tense=tense,
            aspect=aspect,
            mood=mood,
            voice=voice,
            polarity=polarity,
            gender=None,
            source_nc_id=source_nc_id,
            source_tam_id=source_tam_id,
            source_ext_ids=tuple(source_ext_ids),
            warnings=tuple(warnings),
        )

    # ------------------------------------------------------------------
    # CoNLL-U FEATS serialisation
    # ------------------------------------------------------------------

    def to_conllu_feats(self, bundle: UDFeatureBundle) -> str:
        """
        Serialise a ``UDFeatureBundle`` to a CoNLL-U ``FEATS`` column
        string.

        Features are output in **alphabetical order** as required by the
        CoNLL-U specification.  Features with a ``None`` value are omitted.
        An empty feature set (all values ``None``) is rendered as ``_``.

        Parameters
        ----------
        bundle : UDFeatureBundle

        Returns
        -------
        str
            CoNLL-U FEATS string, e.g.
            ``"Aspect=Perf|Mood=Ind|Nounclass=Bantu7|Number=Sing|Person=3|Tense=Past|Voice=Appl"``
            or ``"_"`` if no features are set.

        Examples
        --------
        >>> mapper.to_conllu_feats(bundle)
        'Nounclass=Bantu7|Number=Sing|Person=3|Tense=Pres|Voice=Act'
        """
        pairs: Dict[str, str] = {}

        if bundle.aspect is not None:
            pairs["Aspect"] = bundle.aspect
        if bundle.gender is not None:
            pairs["Gender"] = bundle.gender
        if bundle.mood is not None:
            pairs["Mood"] = bundle.mood
        if bundle.nounclass is not None:
            pairs["Nounclass"] = bundle.nounclass
        if bundle.number is not None:
            pairs["Number"] = bundle.number
        if bundle.person is not None:
            pairs["Person"] = bundle.person
        if bundle.polarity is not None:
            pairs["Polarity"] = bundle.polarity
        if bundle.tense is not None:
            pairs["Tense"] = bundle.tense
        if bundle.voice is not None:
            pairs["Voice"] = bundle.voice

        if not pairs:
            return "_"
        return "|".join(f"{k}={v}" for k, v in sorted(pairs.items()))

    def to_conllu_feats_str(self, token) -> str:  # type: ignore[no-untyped-def]
        """
        Convenience: map a ``SegmentedToken`` to a CoNLL-U FEATS string
        in one call.

        Equivalent to ``to_conllu_feats(map_segmented_token(token))``.

        Examples
        --------
        >>> tok = analyzer.analyze("cilya")
        >>> mapper.to_conllu_feats_str(tok)
        'Nounclass=Bantu7|Number=Sing|Person=3|Tense=Pres|Voice=Act'
        """
        return self.to_conllu_feats(self.map_segmented_token(token))

    # ------------------------------------------------------------------
    # Bulk / convenience methods
    # ------------------------------------------------------------------

    def map_nc_list(self, nc_ids: List[str]) -> List[UDNounClassFeatures]:
        """
        Map a list of noun-class ids in a single call.

        Raises ``UDMappingError`` on the first unmappable id.

        Parameters
        ----------
        nc_ids : List[str]

        Returns
        -------
        List[UDNounClassFeatures]
        """
        return [self.map_nc(nc_id) for nc_id in nc_ids]

    def map_all_tams(self) -> Dict[str, UDTAMFeatures]:
        """
        Map all TAM markers in the loaded grammar, returning a dict keyed
        by TAM id.

        Returns
        -------
        Dict[str, UDTAMFeatures]
        """
        return {
            tam_id: self.map_tam(tam_id)
            for tam_id in sorted(self._tam_index.keys())
        }

    def map_all_extensions(self) -> Dict[str, UDVoiceFeature]:
        """
        Map all verb extensions in the loaded grammar, returning a dict
        keyed by extension id.

        Returns
        -------
        Dict[str, UDVoiceFeature]
        """
        return {
            ext_id: self.map_extension(ext_id)
            for ext_id in sorted(self._ext_index.keys())
        }

    def export_nc_table(self) -> str:
        """
        Return a human-readable Markdown table mapping all noun classes to
        their UD features.  Useful for documentation and grammar review.

        Returns
        -------
        str
            A Markdown table with columns: NC ID, UD Nounclass, UD Number.

        Examples
        --------
        >>> print(mapper.export_nc_table())
        | NC ID | Nounclass | Number |
        |-------|-----------|--------|
        | NC1   | Bantu1    | Sing   |
        | NC2   | Bantu2    | Plur   |
        ...
        """
        rows = []
        for nc_id in sorted(self._nc_index.keys(), key=_nc_sort_key):
            try:
                f = self.map_nc(nc_id)
                rows.append(
                    f"| {nc_id:<6} | {f.nounclass or '—':<9} | {f.number or '—':<6} |"
                )
            except UDMappingError:
                rows.append(f"| {nc_id:<6} | (error)   | —      |")
        header = "| NC ID  | Nounclass | Number |\n|--------|-----------|--------|"
        return header + "\n" + "\n".join(rows)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_tam_id_by_gloss(self, gloss: str) -> Optional[str]:
        """
        Reverse-look up a TAM id by its Leipzig gloss label.

        The ``MorphologicalAnalyzer`` stores the gloss (e.g. ``"PST.PFV"``)
        on the ``Morpheme``; this helper recovers the full TAM id
        (e.g. ``"TAM_PST"``) so we can call ``map_tam()``.

        Strategy:
        1. If ``gloss`` is itself a key in ``_tam_index``, return it.
        2. Build gloss from each TAM and compare.
        3. Return the first match, or ``None``.
        """
        if gloss in self._tam_index:
            return gloss

        for tam_id, tam_obj in self._tam_index.items():
            expected_gloss = self._build_tam_gloss(tam_obj)
            if expected_gloss == gloss:
                return tam_id
        return None

    @staticmethod
    def _build_tam_gloss(tam_obj) -> str:  # type: ignore[no-untyped-def]
        """Reconstruct the short Leipzig gloss for a TAM marker object."""
        parts = []
        tense = getattr(tam_obj, "tense", "none")
        aspect = getattr(tam_obj, "aspect", "none")
        mood = getattr(tam_obj, "mood", "none")
        t_map = {
            "present": "PRS",
            "immediate_past": "PST",
            "remote_past": "REM.PST",
            "immediate_future": "FUT",
            "remote_future": "REM.FUT",
        }
        a_map = {
            "perfective": "PFV",
            "progressive": "PROG",
            "habitual": "HAB",
            "stative": "STAT",
        }
        m_map = {
            "subjunctive": "SBJV",
            "conditional": "COND",
            "imperative": "IMP",
        }
        if tense not in ("none", ""):
            parts.append(t_map.get(tense, tense.upper()))
        if aspect not in ("none", "", "imperfective"):
            parts.append(a_map.get(aspect, aspect.upper()))
        if mood not in ("none", "", "indicative"):
            parts.append(m_map.get(mood, mood.upper()))
        return ".".join(parts) if parts else getattr(tam_obj, "id", "").replace("TAM_", "")

    @property
    def language(self) -> str:
        """The language identifier from the grammar loader."""
        return self._language


def _nc_sort_key(nc_id: str) -> Tuple[int, str]:
    """Sort NC ids numerically then alphabetically by subclass suffix."""
    m = _NC_NUM_RE.match(nc_id)
    return (int(m.group(1)), nc_id) if m else (999, nc_id)
