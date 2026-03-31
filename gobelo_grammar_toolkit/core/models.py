"""
core/models.py
==============
Typed data model layer for the Gobelo (Bantu) Grammar Toolkit (GGT).

All objects in this module are immutable, frozen dataclasses. They form the
exclusive currency of the public API: every method on ``GobeloGrammarLoader``
returns one of these types, and no raw YAML structure ever crosses the public
boundary.

Design principles
-----------------
* **Frozen dataclasses** – all instances are immutable after construction.
  Downstream apps can safely cache, hash, and compare them without defensive
  copying.
* **Explicit ``None`` vs. absent** – optional fields use ``Optional[T]``
  rather than sentinel strings such as ``"N/A"``.  This makes missing data
  unambiguous and easy to guard against in application code.
* **Linguist-facing docstrings** – every field is documented in terms
  familiar to a field linguist, not just a software engineer.
* **No grammar logic** – these classes carry *data*; they contain no methods
  that compute, infer, or derive linguistic forms.  All such logic lives in
  the loader or in the ``apps/`` layer.

Bantu grammar background
------------------------
Bantu languages organise nouns into classes (traditionally NC1–NC18) each
with a dedicated prefix that triggers agreement (concord) on verbs,
adjectives, and other dependants.  Verbs are highly agglutinative and are
analysed as a sequence of obligatory and optional slot positions
(SLOT1–SLOT11 in the GGT slot architecture).  Tense, aspect, and mood
(TAM) are expressed by distinct morphemes occupying specific slots.  Verb
extensions (applicative, causative, passive, reciprocal, …) are suffixed to
the verb root before the final vowel.

Usage example
-------------
These classes are not instantiated directly by application code.  They are
returned by ``GobeloGrammarLoader`` methods:

>>> from gobelo_grammar_toolkit.core.config import GrammarConfig
>>> from gobelo_grammar_toolkit.core.loader import GobeloGrammarLoader
>>> loader = GobeloGrammarLoader(config=GrammarConfig(language="chitonga"))
>>> nc1 = loader.get_noun_class("NC1")
>>> print(nc1.prefix)   # e.g. "mu-"
>>> print(nc1.active)   # True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

__all__ = [
    "NounClass",
    "ConcordSet",
    "TAMMarker",
    "VerbExtension",
    "VerbSlot",
    "DerivationalPattern",
    "PhonologyRules",
    "TokenizationRules",
    "VerifyFlag",
    "GrammarMetadata",
]


# ---------------------------------------------------------------------------
# Noun class system
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NounClass:
    """
    A single Bantu noun class, characterised by its prefix and agreement
    behaviour.

    Bantu noun classes are traditionally numbered NC1–NC18 (following the
    Bleek–Meinhof convention), though individual languages may have gaps,
    mergers, or additional sub-classes.  Each class carries a nominal prefix
    that also determines the shape of concord morphemes on other constituents.

    Parameters
    ----------
    id : str
        Canonical class identifier, e.g. ``"NC1"``, ``"NC2"``, ``"NC9a"``.
        This is the key used throughout the GGT to cross-reference concord
        tables, verb templates, and derivational patterns.
    prefix : str
        The canonical (citation-form) prefix for this class, e.g. ``"mu-"``
        for NC1 in chiTonga or ``"ba-"`` for NC2.  Recorded *with* the
        hyphen to make segmentation boundaries explicit.
    allomorphs : List[str]
        Phonologically-conditioned surface variants of the prefix, e.g.
        ``["m-", "mu-"]`` for the NC1 prefix before stems beginning with a
        vowel vs. a consonant.  May be an empty list if no alternation is
        attested.
    semantic_domain : str
        Primary semantic grouping of nouns in this class, expressed as a
        short English label, e.g. ``"humans – singular"``, ``"trees"``,
        ``"abstracts/infinitives"``.  Populated from the reference grammar;
        use ``"unspecified"`` when no clear semantic coherence is documented.
    active : bool
        ``True`` if this class is productively used in contemporary speech
        for new coinages.  ``False`` marks archaic or vestigial classes that
        still appear in the lexicon but are no longer extended to new nouns
        (e.g. certain augmentative/diminutive classes in SiLozi).
    singular_counterpart : Optional[str]
        The ``id`` of the class that forms the singular of nouns whose plural
        is in this class.  ``None`` for classes that have no singular/plural
        pairing (e.g. mass nouns, abstracts, locatives).
    plural_counterpart : Optional[str]
        The ``id`` of the class that forms the plural of nouns whose singular
        is in this class.  ``None`` for the same reasons as above.

    Examples
    --------
    Typical NC1/NC2 pair in chiBemba:

    >>> nc1 = NounClass(
    ...     id="NC1",
    ...     prefix="u-",
    ...     allomorphs=["w-"],
    ...     semantic_domain="humans – singular",
    ...     active=True,
    ...     singular_counterpart=None,
    ...     plural_counterpart="NC2",
    ... )
    >>> nc1.plural_counterpart
    'NC2'
    """

    id: str
    prefix: str
    allomorphs: List[str]
    semantic_domain: str
    active: bool
    singular_counterpart: Optional[str]
    plural_counterpart: Optional[str]


# ---------------------------------------------------------------------------
# Concord system
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConcordSet:
    """
    One complete set of agreement (concord) morphemes for a given concord
    type across all noun classes.

    Bantu languages exhibit pervasive nominal agreement: verbs carry a
    subject marker, an optional object marker, and other dependants carry
    their own agreement prefixes, all of which are indexed to the noun class
    of the head noun.  The GGT organises these into named concord types
    (e.g. ``"subject_concords"``, ``"object_concords"``,
    ``"adjectival_concords"``).

    A ``ConcordSet`` captures *one* such type in full, mapping every
    noun-class id to its corresponding concord form for that type.

    Parameters
    ----------
    concord_type : str
        The name of this concord paradigm, matching a top-level key in the
        ``concord_systems`` section of the YAML grammar file, e.g.
        ``"subject_concords"``, ``"object_concords"``,
        ``"demonstrative_concords_proximal"``.
    entries : Dict[str, str]
        Mapping from noun-class id (e.g. ``"NC1"``) to the surface concord
        morpheme for this concord type (e.g. ``"a-"``).  Only classes that
        participate in this concord type are included; absent entries signal
        that the concord type does not apply to that class (not that the
        form is unknown).

    Examples
    --------
    Subject concords for Chinyanja (partial):

    >>> sc = ConcordSet(
    ...     concord_type="subject_concords",
    ...     entries={
    ...         "NC1": "a-",
    ...         "NC2": "a-",
    ...         "NC3": "u-",
    ...         "NC4": "i-",
    ...         "NC5": "li-",
    ...         "NC6": "a-",
    ...     },
    ... )
    >>> sc.entries["NC1"]
    'a-'
    """

    concord_type: str
    entries: Dict[str, str]


# ---------------------------------------------------------------------------
# TAM system
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TAMMarker:
    """
    A single Tense-Aspect-Mood (TAM) morpheme in the verb template.

    In Bantu languages TAM morphemes typically occupy SLOT2 or a nearby
    position in the verb template and are combined with subject-concord
    prefixes and, optionally, object-concord prefixes to produce fully
    inflected verb forms.

    Parameters
    ----------
    id : str
        Unique mnemonic identifier for this TAM marker within the grammar
        file, e.g. ``"TAM_PRES_PFV"``, ``"TAM_PAST_IMM"``,
        ``"TAM_FUT_DIST"``.
    form : str
        The canonical surface form of the morpheme, e.g. ``"-a-"``,
        ``"-ka-"``.  Hyphens indicate slot boundaries.
    tense : str
        Tense value expressed by this morpheme, using the GGT vocabulary:
        ``"present"``, ``"immediate_past"``, ``"remote_past"``,
        ``"immediate_future"``, ``"remote_future"``, or ``"none"`` for
        markers that do not encode tense independently.
    aspect : str
        Aspect value: ``"perfective"``, ``"imperfective"``,
        ``"progressive"``, ``"habitual"``, ``"stative"``, or ``"none"``.
    mood : str
        Mood value: ``"indicative"``, ``"subjunctive"``, ``"imperative"``,
        ``"conditional"``, ``"persistive"``, or ``"none"``.
    notes : str
        Free-text annotation for the linguist.  Used to flag dialectal
        variation, VERIFY-pending status, or cross-references to the
        reference grammar.  Empty string if no note is needed.

    Examples
    --------
    Immediate-past perfective in chiTonga:

    >>> tam = TAMMarker(
    ...     id="TAM_PAST_IMM_PFV",
    ...     form="-a-",
    ...     tense="immediate_past",
    ...     aspect="perfective",
    ...     mood="indicative",
    ...     notes="Hoch (1960: §34); tone distinguishes from present.",
    ... )
    >>> tam.tense
    'immediate_past'
    """

    id: str
    form: str
    tense: str
    aspect: str
    mood: str
    notes: str


# ---------------------------------------------------------------------------
# Verb extensions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerbExtension:
    """
    A single Bantu verb extension (valency-changing or voice-marking suffix).

    Verb extensions are suffixes attached to the verb root before the final
    vowel.  They modify argument structure (applicative adds a beneficiary or
    instrumental; causative adds a causer; passive demotes the agent) or
    express reciprocal or reversive meanings.  Multiple extensions may stack.

    Parameters
    ----------
    id : str
        Canonical identifier for the extension, e.g. ``"APPL"``
        (applicative), ``"CAUS"`` (causative), ``"PASS"`` (passive),
        ``"RECP"`` (reciprocal), ``"REV"`` (reversive/separative).
    canonical_form : str
        The citation-form suffix, typically without the preceding root
        consonant, e.g. ``"-el-"``, ``"-ish-"``, ``"-iw-"``.
    allomorphs : List[str]
        Phonologically-conditioned surface alternants, e.g.
        ``["-el-", "-il-"]`` for the applicative under vowel-harmony
        systems.  May be empty if no alternation is documented.
    zone : str
        Slot zone within the post-root extension field, following the GGT
        zone labels ``"Z1"`` through ``"Z4"``.  Extensions in later zones
        are closer to the final vowel.  Use ``"Z1"`` for extensions that
        immediately follow the root, ``"Z4"`` for those closest to the
        final vowel.
    semantic_value : str
        Brief English description of the semantic contribution, e.g.
        ``"beneficiary/instrumental argument addition"``,
        ``"agent demotion / passive voice"``.

    Examples
    --------
    Applicative extension in Luvale:

    >>> appl = VerbExtension(
    ...     id="APPL",
    ...     canonical_form="-el-",
    ...     allomorphs=["-el-", "-il-"],
    ...     zone="Z1",
    ...     semantic_value="adds a beneficiary or goal argument",
    ... )
    >>> appl.zone
    'Z1'
    """

    id: str
    canonical_form: str
    allomorphs: List[str]
    zone: str
    semantic_value: str


# ---------------------------------------------------------------------------
# Verb slot architecture
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerbSlot:
    """
    A single positional slot in the Bantu verb template (SLOT1–SLOT11).

    The GGT verb template models the agglutinative Bantu verb as a linear
    sequence of up to eleven slots, each of which may host a specific set
    of morpheme types.  This architecture follows the analysis in standard
    reference grammars for each supported language.

    Typical slot ordering (not all languages use all slots):

    +-------+---------------------------------+
    | SLOT  | Canonical content               |
    +=======+=================================+
    | SLOT1 | Augment / initial vowel         |
    +-------+---------------------------------+
    | SLOT2 | Negation prefix (pre-subject)   |
    +-------+---------------------------------+
    | SLOT3 | Subject concord                 |
    +-------+---------------------------------+
    | SLOT4 | TAM marker (pre-root)           |
    +-------+---------------------------------+
    | SLOT5 | Relative / subordinator marker  |
    +-------+---------------------------------+
    | SLOT6 | Negation (post-subject)         |
    +-------+---------------------------------+
    | SLOT7 | Object concord                  |
    +-------+---------------------------------+
    | SLOT8 | Verb root                       |
    +-------+---------------------------------+
    | SLOT9 | Extension field (Z1–Z4)         |
    +-------+---------------------------------+
    | SLOT10| TAM marker (post-root / aspect) |
    +-------+---------------------------------+
    | SLOT11| Final vowel                     |
    +-------+---------------------------------+

    The exact mapping is language-specific and is encoded in the YAML.

    Parameters
    ----------
    id : str
        Slot identifier string, e.g. ``"SLOT1"``, ``"SLOT8"``.
    name : str
        Human-readable label for this slot, e.g. ``"subject_marker"``,
        ``"verb_root"``, ``"final_vowel"``.
    position : int
        Linear index (1-based) of this slot in the verb template.  Used
        to sort and validate morpheme sequences.
    obligatory : bool
        ``True`` if every well-formed verb must contain a filler for this
        slot.  ``False`` if the slot may be absent (e.g. object concord,
        negation marker).
    allowed_content_types : List[str]
        Labels describing what categories of morpheme may fill this slot,
        e.g. ``["subject_concord"]``, ``["tam_marker", "empty"]``,
        ``["verb_root"]``.  These labels correspond to keys in the grammar
        YAML and are used by the ``VerbSlotValidator`` app.
    notes : str
        Free-text annotation for linguists.  May cite the reference grammar
        or note language-specific deviations from the canonical slot order.
        Empty string if no note is needed.

    Examples
    --------
    Subject-concord slot in a chiTonga verb template:

    >>> slot3 = VerbSlot(
    ...     id="SLOT3",
    ...     name="subject_marker",
    ...     position=3,
    ...     obligatory=True,
    ...     allowed_content_types=["subject_concord"],
    ...     notes="Encodes both subject agreement and certain TAM distinctions.",
    ... )
    >>> slot3.obligatory
    True
    """

    id: str
    name: str
    position: int
    obligatory: bool
    allowed_content_types: List[str]
    notes: str


# ---------------------------------------------------------------------------
# Derivational patterns
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DerivationalPattern:
    """
    A morphological derivational pattern documented in the grammar YAML.

    Derivational patterns describe systematic relationships between related
    word forms that go beyond inflection — for example, the nominalisation
    of a verb root to form an action noun, or the formation of an agentive
    noun.  Unlike verb extensions (which are always post-root suffixes),
    derivational patterns may involve prefixes, suffixes, or class
    reassignment.

    Parameters
    ----------
    id : str
        Unique identifier for this pattern, e.g. ``"NMLZ_ACTION"``,
        ``"AGENTIVE_NC1"``, ``"DEVERB_INSTRUMENT"``.
    name : str
        Short English label, e.g. ``"action nominalisation"``,
        ``"agentive noun (NC1 prefix)"``.
    input_category : str
        The morphological category of the input form, e.g. ``"verb_root"``,
        ``"noun_stem"``, ``"adjective"``.
    output_category : str
        The morphological category of the derived form, e.g.
        ``"noun_NC14"``, ``"noun_NC1"``.
    morphological_operation : str
        Formal description of the change: ``"prefix + class_reassignment"``,
        ``"suffix -i + class_reassignment"``, etc.  This is an informal
        description for documentation, not executable code.
    target_noun_class : Optional[str]
        If the derivation produces a noun, the id of the resulting noun class
        (e.g. ``"NC14"`` for infinitival/action nouns in many Bantu
        languages).  ``None`` for non-nominal derivations.
    description : str
        Full prose description of the pattern, suitable for inclusion in a
        reference grammar or teaching material.

    Examples
    --------
    Action nominalisation in Kaonde (NC14 infinitival):

    >>> pattern = DerivationalPattern(
    ...     id="NMLZ_ACTION_NC14",
    ...     name="action nominalisation",
    ...     input_category="verb_root",
    ...     output_category="noun_NC14",
    ...     morphological_operation="prefix bu-/ku- + root + final vowel -a",
    ...     target_noun_class="NC14",
    ...     description=(
    ...         "Any verb root may be nominalised to form an abstract action "
    ...         "noun by prefixing the NC14 augment and nominal prefix."
    ...     ),
    ... )
    >>> pattern.target_noun_class
    'NC14'
    """

    id: str
    name: str
    input_category: str
    output_category: str
    morphological_operation: str
    target_noun_class: Optional[str]
    description: str


# ---------------------------------------------------------------------------
# Phonology
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PhonologyRules:
    """
    Phonological inventory and rule system for a single language.

    Bantu languages share broad phonological properties (5-vowel systems,
    large consonant inventories with nasal consonants, tone as grammatically
    distinctive) but differ in detail — SiLozi has a 7-vowel system, Luvale
    has a complex labial-velar series, and so on.  This model captures the
    language-specific rules that downstream apps need to apply phonological
    post-processing (e.g. nasal assimilation, vowel harmony, tone
    assignment) when generating or parsing surface forms.

    Parameters
    ----------
    vowels : List[str]
        Phonemic vowel inventory, e.g. ``["a", "e", "i", "o", "u"]`` for a
        5-vowel language or ``["a", "e", "ɛ", "i", "o", "ɔ", "u"]`` for a
        7-vowel system.  Symbols follow IPA conventions.
    consonants : List[str]
        Phonemic consonant inventory as IPA symbols, e.g.
        ``["b", "c", "d", "f", "g", "h", "j", "k", "l", "m", "n", ...]``.
    nasal_prefixes : List[str]
        NC-prefix forms that consist entirely of a nasal segment, e.g.
        ``["m-", "n-", "ny-", "ŋ-"]``.  Required by the morpheme segmenter
        (F-02) because nasal prefixes trigger consonant-mutation on the
        stem-initial segment.
    tone_system : str
        High-level description of the tone system:
        ``"two_level_HL"``, ``"three_level_HML"``, ``"privative_H"``,
        or ``"none"`` for languages without lexical tone contrast.
    sandhi_rules : List[str]
        Identifiers of active morphophonological sandhi rules, as defined
        in the ``phonology.sandhi_rules`` section of the YAML, e.g.
        ``["SND.1_vowel_coalescence", "SND.2_glide_formation",
           "SND.3_nasal_assimilation", "SND.4_tone_shift"]``.
        The surface-form generator (F-01) applies these rules in order.
    vowel_harmony_rules : List[str]
        Identifiers of active vowel harmony rules, e.g.
        ``["VH.1_height_harmony", "VH.2_ATR_spread"]``.  Empty list for
        languages without documented vowel harmony.
    notes : str
        Free-text annotation for linguists covering known issues, gaps in
        the documentation, or VERIFY-pending phonological analyses.

    Examples
    --------
    chiTonga phonology (simplified):

    >>> phon = PhonologyRules(
    ...     vowels=["a", "e", "i", "o", "u"],
    ...     consonants=["b", "d", "f", "g", "h", "j", "k", "l",
    ...                  "m", "n", "p", "s", "t", "w", "y", "z"],
    ...     nasal_prefixes=["m-", "n-"],
    ...     tone_system="two_level_HL",
    ...     sandhi_rules=["SND.1_vowel_coalescence", "SND.3_nasal_assimilation"],
    ...     vowel_harmony_rules=[],
    ...     notes="Tone documentation follows Hoch (1960).",
    ... )
    >>> phon.tone_system
    'two_level_HL'
    """

    vowels: List[str]
    consonants: List[str]
    nasal_prefixes: List[str]
    tone_system: str
    sandhi_rules: List[str]
    vowel_harmony_rules: List[str]
    notes: str


# ---------------------------------------------------------------------------
# Tokenization rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenizationRules:
    """
    Language-specific tokenization rules for segmenting running text.

    Bantu text is typically written without spaces between morphemes, but
    orthographic conventions vary: some languages write the subject concord
    as a separate word in certain registers; clitic pronouns may be
    orthographically attached or detached; tone marks and diacritics may
    or may not be present.  These rules are used by the morpheme segmenter
    (F-02) and the corpus annotation pipeline (F-09).

    Parameters
    ----------
    word_boundary_pattern : str
        A regular-expression pattern (Python ``re`` syntax) that matches
        word boundaries in running text, e.g. ``r"\\s+"``.  This is the
        primary split pattern for tokenizing sentences into word tokens.
    clitic_boundaries : List[str]
        Strings or regex patterns that mark clitic attachment boundaries
        within a token, e.g. ``["-"]``.
    prefix_strip_patterns : List[str]
        Ordered list of regex patterns used to strip known prefixes during
        preliminary segmentation.  Applied before the main morphological
        parse.  E.g. ``["^(mu|ba|ka|ku|lu|bu|tu|ma|chi|zi)-"]``.
    suffix_strip_patterns : List[str]
        Analogous to ``prefix_strip_patterns`` but for suffixes, e.g.
        final vowels: ``["(a|e|i|o|u)$"]``.
    special_cases : Dict[str, str]
        A lookup table for idiomatic multi-word expressions or irregular
        forms that must be handled as a single token, mapping the surface
        string to its canonical lemma or token type label, e.g.
        ``{"ndi": "copula_1SG", "ndiwe": "copula_2SG"}``.
    orthographic_normalization : Dict[str, str]
        Mapping of non-standard orthographic variants to their canonical
        forms, e.g. ``{"ny": "ñ", "ng'": "ŋ"}``.  Applied before all
        pattern matching.
    notes : str
        Free-text annotation for linguists.

    Examples
    --------
    Minimal tokenization rules for Lunda:

    >>> rules = TokenizationRules(
    ...     word_boundary_pattern=r"\\s+",
    ...     clitic_boundaries=["-"],
    ...     prefix_strip_patterns=["^(mu|ba|ka|ku|lu|bu|tu|ma|chi|zi)-"],
    ...     suffix_strip_patterns=["(a|e|i|o|u)$"],
    ...     special_cases={"ndi": "copula_1SG"},
    ...     orthographic_normalization={"ng'": "ŋ"},
    ...     notes="Kawasha (2003) §2 is the authoritative orthography source.",
    ... )
    >>> rules.clitic_boundaries
    ['-']
    """

    word_boundary_pattern: str
    clitic_boundaries: List[str]
    prefix_strip_patterns: List[str]
    suffix_strip_patterns: List[str]
    special_cases: Dict[str, str]
    orthographic_normalization: Dict[str, str]
    notes: str


# ---------------------------------------------------------------------------
# VERIFY flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifyFlag:
    """
    A single unresolved ``VERIFY`` annotation in a grammar YAML file.

    During grammar authoring, forms that require verification against a
    primary source are tagged with a ``# VERIFY:`` comment in the YAML.
    These flags are extracted by the loader and exposed via
    ``GobeloGrammarLoader.list_verify_flags()``.  In ``strict_mode``,
    the presence of any flag raises ``UnverifiedFormError``; otherwise
    a warning is emitted.

    The structured ``VerifyFlag`` model enables the VERIFY Flag Resolver
    workflow (F-06) to present each flag to a linguist for resolution,
    record the confirmed form, and write it back to the YAML.

    Parameters
    ----------
    field_path : str
        Dot-notation path to the flagged field within the YAML structure,
        e.g. ``"concord_systems.subject_concords.NC9"`` or
        ``"verb_extensions.APPL.allomorphs[1]"``.
    current_value : str
        The value currently present in the YAML for this field.  May be
        an empty string, a placeholder like ``"??"``, or a form that the
        grammar author suspects may be incorrect.
    note : str
        The full text of the ``# VERIFY:`` comment from the YAML, e.g.
        ``"Cross-check against Horton (1949: 87); heard -ile- in fieldwork"``.
    suggested_source : str
        The primary reference grammar entry the linguist should consult
        to resolve this flag, e.g. ``"Horton (1949: §34)"``.  May be an
        empty string if no specific source is suggested.
    resolved : bool
        ``True`` if this flag has been marked as resolved by the F-06
        resolver workflow.  Newly extracted flags from the YAML are always
        ``False``; the resolver sets this to ``True`` when writing back.

    Examples
    --------
    A VERIFY flag for an uncertain applicative allomorph in kaonde.yaml:

    >>> flag = VerifyFlag(
    ...     field_path="verb_extensions.APPL.allomorphs",
    ...     current_value="-el-",
    ...     note="Uncertain whether -il- allomorph exists in Kaonde; "
    ...          "not confirmed in Stevick (1965).",
    ...     suggested_source="Stevick (1965: §18)",
    ...     resolved=False,
    ... )
    >>> flag.resolved
    False
    """

    field_path: str
    current_value: str
    note: str
    suggested_source: str
    resolved: bool


# ---------------------------------------------------------------------------
# Grammar metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GrammarMetadata:
    """
    Version and identity metadata for a loaded grammar YAML file.

    Every GGT-conformant YAML file must declare a ``metadata`` block at
    the top level.  The loader reads this block first, before parsing any
    linguistic data, in order to enforce version compatibility.

    Version semantics follow `Semantic Versioning 2.0 <https://semver.org>`_:

    * **MAJOR** bump — a field was removed or renamed; downstream apps may
      break without code changes.
    * **MINOR** bump — a new optional field was added; backwards-compatible.
    * **PATCH** bump — corrections to linguistic data with no schema change.

    The ``min_loader_version`` and ``max_loader_version`` fields form the
    *compatibility window*: the toolkit loader will refuse to load a grammar
    whose window does not include the running loader version, raising
    ``VersionIncompatibleError``.

    Parameters
    ----------
    language : str
        Canonical language name as recorded in the language registry,
        e.g. ``"chitonga"``, ``"chibemba"``, ``"chinyanja"``.  Must match
        the ``GrammarConfig.language`` value that triggered the load.
    iso_code : str
        ISO 639-3 code for the language, e.g. ``"toi"`` (chiTonga),
        ``"bem"`` (chiBemba), ``"nya"`` (Chinyanja).
    guthrie : str
        Guthrie classification code, e.g. ``"M.64"`` (chiTonga),
        ``"M.42"`` (chiBemba).  Follows Nurse & Philippson (2003).
    grammar_version : str
        Semantic version of this grammar file's *data*, e.g. ``"1.3.2"``.
        Incremented whenever the YAML content changes.
    min_loader_version : str
        Minimum version of the GGT loader required to parse this grammar,
        e.g. ``"1.0.0"``.  Loaders older than this value must refuse the
        file.
    max_loader_version : str
        Maximum version of the GGT loader that is guaranteed to be
        compatible with this grammar.  Loaders newer than this value may
        attempt the load but will emit a ``VersionIncompatibleError``.
        Use ``"*"`` to indicate no upper bound (not recommended for
        production grammars).
    verify_count : int
        Total number of unresolved ``# VERIFY:`` comments found in this
        YAML file at load time.  A value of 0 indicates a fully verified
        grammar.  Large counts (e.g. kaonde.yaml currently has 118)
        indicate areas requiring primary-source validation.

    Examples
    --------
    Metadata for the chiTonga grammar:

    >>> meta = GrammarMetadata(
    ...     language="chitonga",
    ...     iso_code="toi",
    ...     guthrie="M.64",
    ...     grammar_version="1.0.0",
    ...     min_loader_version="1.0.0",
    ...     max_loader_version="2.0.0",
    ...     verify_count=12,
    ... )
    >>> meta.iso_code
    'toi'
    >>> meta.verify_count
    12
    """

    language: str
    iso_code: str
    guthrie: str
    grammar_version: str
    min_loader_version: str
    max_loader_version: str
    verify_count: int
