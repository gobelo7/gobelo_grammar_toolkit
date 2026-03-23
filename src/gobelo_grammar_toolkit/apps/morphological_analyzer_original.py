"""
apps/morphological_analyzer.py
================================
MorphologicalAnalyzer — segment a Bantu surface token into its constituent
morphemes, label each morpheme with its verb-template slot, and generate
inflected verb surface forms from a feature bundle.

This module implements two complementary functions described in the GGT
feature catalogue:

* **F-02 — Morpheme Segmenter / Tokenizer**: given a raw word token, produce
  a ranked list of segmentation hypotheses, each assigning morpheme boundaries,
  slot labels (SLOT1–SLOT11), and interlinear glosses.

* **F-01 — Surface Form Generator**: given a verb root and a
  ``MorphFeatureBundle`` specifying agreement, TAM, voice, and polarity, walk
  the verb slot template and concatenate the appropriate morphemes into a
  surface form with segmented representation and Leipzig gloss.

Design contract (Part 9)
-------------------------
* Accepts a ``GobeloGrammarLoader`` instance as its **only** grammar
  dependency.
* Uses **only** the public API methods from Part 6 of the spec.
* Is **language-agnostic** — no language-name checks, no hardcoded morphemes.
* Handles all ``GGTError`` subclasses gracefully.

Segmentation algorithm
-----------------------
The segmenter uses a **slot-driven, hypothesis-ranked** strategy:

1. Normalise the token with ``TokenizationRules.orthographic_normalization``.
2. Check ``TokenizationRules.special_cases`` for an exact match.
3. Build a prefix lattice by matching all subject-concord forms (longest
   first) against the front of the token — each match seeds a hypothesis.
4. For each hypothesis, attempt to match a TAM marker, then an optional
   object concord.
5. Strip the final vowel (SLOT10) and any recognised extensions (SLOT9)
   from the right end; the residue is the verb root (SLOT8).
6. Score each hypothesis by *coverage* (proportion of the token string
   assigned to a known morpheme), penalise unrecognised residues, and
   award bonuses for filling all obligatory slots.
7. Return the top-N hypotheses as a ``SegmentedToken``.

For nominal (non-verbal) analysis, a prefix scan over all noun-class
prefixes and allomorphs produces NC hypotheses ranked by prefix length.

Generation algorithm
---------------------
1. Sort verb slots by ``position``.
2. For each slot, consult ``allowed_content_types`` and fill from the
   feature bundle:
   - ``subject_concords`` → look up ``features.subject_nc`` in
     ``loader.get_subject_concords().entries``
   - ``tam`` → find the ``TAMMarker`` whose ``id == features.tam_id``,
     normalise form (strip leading/trailing ``-``)
   - ``object_concords`` → look up ``features.object_nc`` if provided
   - ``root`` → ``features.root``
   - ``extensions`` → concatenate each extension form in
     ``features.extensions`` (in order)
   - ``final_vowels`` → ``features.final_vowel``
   - All other slot types (negation, modal, etc.) are skipped unless
     explicitly provided in the bundle.
3. Concatenate filled slots → ``surface``.
4. Build hyphen-delimited ``segmented`` and Leipzig ``gloss`` strings.
5. Record sandhi/vowel-harmony rule IDs as ``warnings`` (the rules are
   named in the YAML but their phonological transformations are not
   encoded in the public API; applying them is left to F-01 post-processing
   which lies outside the v1.0 scope).

Usage
------
::

    from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    from gobelo_grammar_toolkit.apps.morphological_analyzer import (
        MorphologicalAnalyzer, MorphFeatureBundle,
    )

    loader   = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    analyzer = MorphologicalAnalyzer(loader)

    # Segment a surface token
    result = analyzer.analyze("balya")
    best   = result.best
    for m in best.morphemes:
        print(f"{m.form:<8} {m.slot_id}  {m.gloss}")

    # Generate a surface form
    features = MorphFeatureBundle(
        root="lya",
        subject_nc="NC1",
        tam_id="TAM_PRES",
        object_nc=None,
        extensions=(),
        polarity="affirmative",
        final_vowel="a",
    )
    sf = analyzer.generate(features)
    print(sf.surface)    # e.g. "alya"
    print(sf.segmented)  # e.g. "a-lya-a"
    print(sf.gloss)      # e.g. "NC1.SUBJ-eat-FV"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from gobelo_grammar_toolkit.core.exceptions import (
    GGTError,
    NounClassNotFoundError,
)

__all__ = [
    "MorphologicalAnalyzer",
    "Morpheme",
    "ParseHypothesis",
    "SegmentedToken",
    "MorphFeatureBundle",
    "SurfaceForm",
    "MorphAnalysisError",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MorphAnalysisError(GGTError):
    """
    Raised when the morphological analyzer encounters an unrecoverable
    error — for example, a ``MorphFeatureBundle`` that references an
    unknown TAM id, or a root string that is empty.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Morpheme:
    """
    A single identified morpheme within a segmented word token.

    Parameters
    ----------
    form : str
        The surface string of this morpheme as it appears in the token.
    slot_id : str
        The verb-template slot identifier this morpheme occupies, e.g.
        ``"SLOT3"``, ``"SLOT8"``, ``"SLOT10"``.  ``"UNKNOWN"`` if the
        morpheme could not be assigned to a slot.
    slot_name : str
        Human-readable slot label from ``VerbSlot.name``, e.g.
        ``"subject_marker"``, ``"verb_root"``.  Empty string for unknowns.
    content_type : str
        The category label for this morpheme, e.g. ``"subject_concord"``,
        ``"tam_marker"``, ``"verb_extension"``, ``"verb_root"``,
        ``"final_vowel"``, ``"object_concord"``, ``"noun_prefix"``.
    gloss : str
        Leipzig-style gloss label, e.g. ``"NC1.SUBJ"``, ``"PST"``,
        ``"APPL"``, ``"eat"``, ``"FV"``.
    nc_id : Optional[str]
        The noun class id associated with this morpheme (e.g. the NC whose
        subject concord this is), or ``None`` if not applicable.
    """

    form: str
    slot_id: str
    slot_name: str
    content_type: str
    gloss: str
    nc_id: Optional[str]


@dataclass(frozen=True)
class ParseHypothesis:
    """
    One segmentation hypothesis for a surface token.

    Parameters
    ----------
    morphemes : Tuple[Morpheme, ...]
        Ordered sequence of morphemes from left to right.
    surface_form : str
        The original token string that was parsed.
    remaining : str
        Any portion of the token string that could not be assigned to a
        known morpheme.  An empty string means full coverage.
    confidence : float
        Heuristic confidence score in the range [0.0, 1.0].  Higher is
        better.  Computed from coverage, obligatory-slot satisfaction, and
        length of the residue.
    warnings : Tuple[str, ...]
        Diagnostics generated during parsing, e.g. notes about ambiguous
        forms, missing obligatory slots, or sandhi rules that were not
        applied.
    """

    morphemes: Tuple[Morpheme, ...]
    surface_form: str
    remaining: str
    confidence: float
    warnings: Tuple[str, ...]

    @property
    def segmented(self) -> str:
        """
        Return a hyphen-delimited segmented representation, e.g. ``"a-lya-a"``.

        Morphemes with an empty form are skipped.
        """
        return "-".join(m.form for m in self.morphemes if m.form)

    @property
    def gloss_line(self) -> str:
        """
        Return a hyphen-delimited Leipzig gloss line, e.g.
        ``"NC1.SUBJ-eat-FV"``.
        """
        return "-".join(m.gloss for m in self.morphemes if m.form)

    @property
    def coverage(self) -> float:
        """Proportion of the surface string assigned to known morphemes."""
        if not self.surface_form:
            return 1.0
        assigned = sum(len(m.form) for m in self.morphemes if m.form)
        return assigned / len(self.surface_form)


@dataclass(frozen=True)
class SegmentedToken:
    """
    The complete segmentation result for a single word token.

    Parameters
    ----------
    token : str
        The original (pre-normalization) token string.
    language : str
        The language identifier from the grammar loader.
    hypotheses : Tuple[ParseHypothesis, ...]
        All generated parse hypotheses, sorted by descending confidence.
    best : Optional[ParseHypothesis]
        The highest-confidence hypothesis.  ``None`` only if ``hypotheses``
        is empty (should not occur in practice; the analyzer always
        produces at least a single-morpheme fallback hypothesis).
    """

    token: str
    language: str
    hypotheses: Tuple[ParseHypothesis, ...]
    best: Optional[ParseHypothesis]

    @property
    def is_ambiguous(self) -> bool:
        """``True`` if more than one hypothesis was generated."""
        return len(self.hypotheses) > 1

    @property
    def top_n(self, n: int = 3) -> Tuple[ParseHypothesis, ...]:
        """Return the top-n hypotheses."""
        return self.hypotheses[:n]


@dataclass(frozen=True)
class MorphFeatureBundle:
    """
    Feature specification for verb surface-form generation (F-01).

    Pass an instance of this to ``MorphologicalAnalyzer.generate()`` to
    produce a fully-inflected verb form.

    Parameters
    ----------
    root : str
        The bare verb root (no affixes), e.g. ``"lya"``, ``"bona"``.
        Must not be empty.
    subject_nc : str
        The subject concord key as it appears in the grammar's
        ``subject_concords`` entries — either a noun-class id (e.g.
        ``"NC1"``, ``"NC7"``) or a person label (e.g. ``"1SG"``,
        ``"2PL"``).
    tam_id : str
        The ``TAMMarker.id`` value from the grammar, e.g.
        ``"TAM_PRES"``, ``"TAM_PST"``.
    object_nc : Optional[str]
        The object concord key if an object marker is required.  ``None``
        to omit the object concord slot entirely.
    extensions : Tuple[str, ...]
        Ordered tuple of ``VerbExtension.id`` values to apply in the given
        order, e.g. ``("APPL", "PASS")``.  Use an empty tuple for bare
        roots.
    polarity : str
        ``"affirmative"`` or ``"negative"``.  Negative polarity typically
        requires filling SLOT1 / SLOT4 (negation prefix/infix), but the
        exact negative forms are not in the Part 6 public API; a warning
        is emitted and the affirmative form is generated instead.
    final_vowel : str
        The final-vowel morpheme for SLOT10, e.g. ``"a"`` (default
        indicative), ``"e"`` (subjunctive in many Bantu languages).
        Defaults to ``"a"``.
    """

    root: str
    subject_nc: str
    tam_id: str
    object_nc: Optional[str] = None
    extensions: Tuple[str, ...] = ()
    polarity: str = "affirmative"
    final_vowel: str = "a"


@dataclass(frozen=True)
class SurfaceForm:
    """
    The result of generating a verb surface form (F-01).

    Parameters
    ----------
    surface : str
        The generated surface string, e.g. ``"alya"``.
    segmented : str
        Hyphen-delimited morpheme segmentation, e.g. ``"a-lya-a"``.
    gloss : str
        Leipzig-style gloss, e.g. ``"NC1.SUBJ-eat-FV"``.
    morphemes : Tuple[Morpheme, ...]
        Ordered sequence of morpheme records that make up the surface form.
    features : MorphFeatureBundle
        The feature bundle used to generate this form.
    warnings : Tuple[str, ...]
        Non-fatal issues encountered during generation, e.g. sandhi rules
        that exist in the grammar but were not applied because their
        phonological transformations are not encoded in the public API.
    """

    surface: str
    segmented: str
    gloss: str
    morphemes: Tuple[Morpheme, ...]
    features: MorphFeatureBundle
    warnings: Tuple[str, ...]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HYPHEN_RE = re.compile(r"^-+|-+$")


def _strip_hyphens(form: str) -> str:
    """Remove leading/trailing hyphens used as slot-boundary markers in YAML."""
    return _HYPHEN_RE.sub("", form).strip()


def _base_nc(nc_id: str) -> str:
    """
    Return the base noun class by stripping trailing alphabetic subclass
    suffix, e.g. ``"NC1a"`` → ``"NC1"``, ``"NC2b"`` → ``"NC2"``.
    """
    return re.sub(r"[a-z]+$", "", nc_id)


def _confidence(
    morphemes: Sequence[Morpheme],
    token: str,
    obligatory_slots: FrozenSet[str],
) -> float:
    """
    Compute a heuristic confidence score for a parse hypothesis.

    Scoring factors:

    * **Coverage** (0.0–0.5): proportion of the token string assigned to
      known morphemes.
    * **Obligatory slots** (0.0–0.25): bonus for each obligatory slot that
      is filled.
    * **Root non-empty** (0.0–0.10): bonus if a verb root morpheme is present.
    * **Root length** (0.0–0.15): prefer longer roots over single-char roots
      to prevent greedy extension over-matching.
      Score = min(root_length / 4, 1.0) × 0.15.
    """
    assigned = sum(len(m.form) for m in morphemes if m.form)
    total = len(token) if token else 1
    coverage_score = min(assigned / total, 1.0) * 0.5

    filled_ids = frozenset(m.slot_id for m in morphemes if m.form)
    oblig_score = (
        len(filled_ids & obligatory_slots) / max(len(obligatory_slots), 1) * 0.25
    )

    root_forms = [m.form for m in morphemes if m.content_type == "verb_root" and m.form]
    root_len = len(root_forms[0]) if root_forms else 0
    root_score = 0.10 if root_len > 0 else 0.0
    root_len_score = min(root_len / 4, 1.0) * 0.15

    return round(coverage_score + oblig_score + root_score + root_len_score, 4)


# ---------------------------------------------------------------------------
# MorphologicalAnalyzer
# ---------------------------------------------------------------------------


class MorphologicalAnalyzer:
    """
    Language-agnostic morphological analyzer for Bantu verb and noun tokens.

    The analyzer builds its entire knowledge base from the
    ``GobeloGrammarLoader`` public API at construction time.  No grammar
    data is hard-coded; all morpheme recognition is data-driven.

    Parameters
    ----------
    loader : GobeloGrammarLoader
        An initialised loader for the target language.  The loader is
        queried once in ``__init__``; it is then stored as ``self.loader``
        and not called again during ``analyze()`` or ``generate()``.

    Raises
    ------
    MorphAnalysisError
        If the loader raises an unexpected ``GGTError`` during index
        construction.  Ordinary ``GGTError`` subclasses (e.g.
        ``NounClassNotFoundError``) are caught and re-raised as
        ``MorphAnalysisError`` with a diagnostic message.

    Examples
    --------
    >>> from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    >>> from gobelo_grammar_toolkit.apps.morphological_analyzer import (
    ...     MorphologicalAnalyzer, MorphFeatureBundle,
    ... )
    >>> loader   = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    >>> analyzer = MorphologicalAnalyzer(loader)

    Segment a token:

    >>> result = analyzer.analyze("alya")
    >>> result.best.segmented
    'a-lya-a'

    Generate a surface form:

    >>> bundle = MorphFeatureBundle(
    ...     root="lya", subject_nc="NC1", tam_id="TAM_PRES"
    ... )
    >>> sf = analyzer.generate(bundle)
    >>> sf.surface
    'alya'
    """

    def __init__(self, loader) -> None:  # type: ignore[no-untyped-def]
        self._loader = loader
        try:
            self._build_indexes()
        except GGTError as exc:
            raise MorphAnalysisError(
                f"Failed to build morphological indexes: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Index construction (called once in __init__)
    # ------------------------------------------------------------------

    def _build_indexes(self) -> None:
        """
        Query the loader's public API once and build all data structures
        needed for O(1) morpheme lookup during analysis and generation.
        """
        meta = self._loader.get_metadata()
        self._language: str = meta.language

        # ── Verb slots ────────────────────────────────────────────────
        slots = self._loader.get_verb_slots()
        self._slots_by_id: Dict[str, object] = {s.id: s for s in slots}
        self._slot_order: List = sorted(slots, key=lambda s: s.position)

        # Identify the root slot position boundary
        self._root_slot_pos: int = next(
            (s.position for s in self._slot_order if "root" in s.allowed_content_types),
            8,  # fallback to canonical SLOT8
        )
        self._obligatory_slot_ids: FrozenSet[str] = frozenset(
            s.id for s in slots if s.obligatory
        )

        # Pre-root slots (fill from the left during analysis)
        self._pre_root_slots: List = [
            s for s in self._slot_order if s.position < self._root_slot_pos
        ]
        # Post-root slots (fill from the right, excluding root)
        self._post_root_slots: List = [
            s
            for s in self._slot_order
            if s.position > self._root_slot_pos
        ]

        # Root slot object
        self._root_slot = next(
            (s for s in slots if "root" in s.allowed_content_types), None
        )

        # ── Subject concords ──────────────────────────────────────────
        # _sc_index: normalised form → list of (key, "subject_concords")
        self._sc_index: Dict[str, List[Tuple[str, str]]] = {}
        try:
            sc = self._loader.get_subject_concords()
            for key, raw_form in sc.entries.items():
                form = _strip_hyphens(raw_form)
                if form:
                    self._sc_index.setdefault(form, []).append(
                        (key, "subject_concords")
                    )
        except GGTError:
            pass  # Language may have no subject concords (stub)

        # ── Object concords ───────────────────────────────────────────
        self._oc_index: Dict[str, List[Tuple[str, str]]] = {}
        try:
            oc = self._loader.get_object_concords()
            for key, raw_form in oc.entries.items():
                form = _strip_hyphens(raw_form)
                if form:
                    self._oc_index.setdefault(form, []).append(
                        (key, "object_concords")
                    )
        except GGTError:
            pass

        # ── All concord types (for generate) ─────────────────────────
        self._all_concord_types: List[str] = self._loader.get_all_concord_types()

        # Full concord map: concord_type → {key: form}
        # Used during generation to look up any concord type by name.
        self._concord_map: Dict[str, Dict[str, str]] = {}
        for ctype in self._all_concord_types:
            try:
                cset = self._loader.get_concords(ctype)
                self._concord_map[ctype] = {
                    k: _strip_hyphens(v) for k, v in cset.entries.items()
                }
            except GGTError:
                pass

        # ── TAM markers ───────────────────────────────────────────────
        # _tam_by_id: id → TAMMarker (for generation)
        # _tam_by_form: normalised form → [TAMMarker] (for analysis)
        self._tam_by_id: Dict[str, object] = {}
        self._tam_by_form: Dict[str, List] = {}
        for tam in self._loader.get_tam_markers():
            self._tam_by_id[tam.id] = tam
            form = _strip_hyphens(tam.form)
            if form:
                self._tam_by_form.setdefault(form, []).append(tam)

        # ── Verb extensions ───────────────────────────────────────────
        # _ext_by_id: id → VerbExtension (for generation)
        # _ext_by_form: normalised form → [VerbExtension] (for analysis)
        self._ext_by_id: Dict[str, object] = {}
        self._ext_by_form: Dict[str, List] = {}
        for ext in self._loader.get_extensions():
            self._ext_by_id[ext.id] = ext
            canon = _strip_hyphens(ext.canonical_form)
            if canon:
                self._ext_by_form.setdefault(canon, []).append(ext)
            for allomorph in ext.allomorphs:
                af = _strip_hyphens(allomorph)
                if af:
                    self._ext_by_form.setdefault(af, []).append(ext)

        # ── Noun class prefixes ───────────────────────────────────────
        # _nc_by_prefix: normalised prefix → [NounClass]
        self._nc_by_prefix: Dict[str, List] = {}
        for nc in self._loader.get_noun_classes(active_only=False):
            # Canonical prefix
            prefix = _strip_hyphens(nc.prefix)
            if prefix and prefix not in ("Ø", "N"):
                self._nc_by_prefix.setdefault(prefix, []).append(nc)
            # Allomorphs
            for allo in nc.allomorphs:
                af = _strip_hyphens(allo)
                if af and af not in ("Ø", "N") and not af.startswith("["):
                    self._nc_by_prefix.setdefault(af, []).append(nc)

        # ── Phonology ─────────────────────────────────────────────────
        phon = self._loader.get_phonology()
        self._vowel_set: FrozenSet[str] = frozenset(phon.vowels)
        self._sandhi_rules: List[str] = list(phon.sandhi_rules)
        self._vowel_harmony_rules: List[str] = list(phon.vowel_harmony_rules)
        self._nasal_prefixes: FrozenSet[str] = frozenset(
            _strip_hyphens(p) for p in phon.nasal_prefixes
        )

        # ── Tokenization ─────────────────────────────────────────────
        tok = self._loader.get_tokenization_rules()
        self._word_boundary_re: re.Pattern = re.compile(
            tok.word_boundary_pattern or r"\s+"
        )
        self._ortho_norm: Dict[str, str] = dict(tok.orthographic_normalization)
        self._special_cases: Dict[str, str] = dict(tok.special_cases)

        # ── Sorted form lists (longest-first for greedy matching) ────
        self._sc_forms_desc: List[str] = sorted(
            self._sc_index.keys(), key=len, reverse=True
        )
        self._oc_forms_desc: List[str] = sorted(
            self._oc_index.keys(), key=len, reverse=True
        )
        self._tam_forms_desc: List[str] = sorted(
            self._tam_by_form.keys(), key=len, reverse=True
        )
        self._ext_forms_desc: List[str] = sorted(
            self._ext_by_form.keys(), key=len, reverse=True
        )
        self._nc_prefix_forms_desc: List[str] = sorted(
            self._nc_by_prefix.keys(), key=len, reverse=True
        )

        # Slot id lookup for each content type (for gloss labelling)
        self._slot_for_content: Dict[str, Tuple[str, str]] = {}
        for s in slots:
            for ct in s.allowed_content_types:
                key = ct.split(".")[-1]  # strip "concords." prefix if present
                self._slot_for_content.setdefault(key, (s.id, s.name))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalise(self, token: str) -> str:
        """Apply orthographic normalisation and lowercase."""
        s = token.lower()
        for src, tgt in self._ortho_norm.items():
            s = s.replace(src.lower(), tgt.lower())
        return s

    def _slot_for(self, content_type: str) -> Tuple[str, str]:
        """Return (slot_id, slot_name) for the given content type, or UNKNOWN."""
        return self._slot_for_content.get(content_type, ("UNKNOWN", ""))

    def _try_match_prefix(
        self, s: str, forms_desc: List[str], index: Dict[str, List]
    ) -> Optional[Tuple[str, List]]:
        """
        Try to match the longest possible prefix of ``s`` against the
        forms in ``forms_desc`` (sorted longest-first).

        Returns ``(matched_form, candidates)`` or ``None``.
        """
        for form in forms_desc:
            if s.startswith(form) and len(form) < len(s):
                return form, index[form]
        return None

    def _try_match_suffix(
        self, s: str, forms_desc: List[str], index: Dict[str, List]
    ) -> Optional[Tuple[str, List]]:
        """
        Try to match the longest possible suffix of ``s`` against the
        forms in ``forms_desc`` (sorted longest-first).

        Returns ``(matched_form, candidates)`` or ``None``.
        """
        for form in forms_desc:
            if s.endswith(form) and len(form) < len(s):
                return form, index[form]
        return None

    def _gloss_for_sc(self, key: str) -> str:
        """Build a Leipzig gloss for a subject concord key."""
        if key.startswith("NC"):
            return f"{key}.SUBJ"
        if key.startswith("NEG"):
            return f"{key}.SUBJ.NEG"
        return f"{key}.SUBJ"

    def _gloss_for_oc(self, key: str) -> str:
        """Build a Leipzig gloss for an object concord key."""
        if key.startswith("NC"):
            return f"{key}.OBJ"
        return f"{key}.OBJ"

    def _gloss_for_tam(self, tam) -> str:  # type: ignore[no-untyped-def]
        """Build a short Leipzig gloss for a TAM marker."""
        parts = []
        if tam.tense not in ("none", ""):
            t_map = {
                "present": "PRS",
                "immediate_past": "PST",
                "remote_past": "REM.PST",
                "immediate_future": "FUT",
                "remote_future": "REM.FUT",
            }
            parts.append(t_map.get(tam.tense, tam.tense.upper()))
        if tam.aspect not in ("none", "", "imperfective"):
            a_map = {
                "perfective": "PFV",
                "progressive": "PROG",
                "habitual": "HAB",
                "stative": "STAT",
            }
            parts.append(a_map.get(tam.aspect, tam.aspect.upper()))
        if tam.mood not in ("none", "", "indicative"):
            m_map = {
                "subjunctive": "SBJV",
                "conditional": "COND",
                "imperative": "IMP",
            }
            parts.append(m_map.get(tam.mood, tam.mood.upper()))
        return ".".join(parts) if parts else tam.id.replace("TAM_", "")

    # ------------------------------------------------------------------
    # Core analysis  (verbal)
    # ------------------------------------------------------------------

    def _analyze_verbal(
        self, token: str, normalised: str, max_hypotheses: int
    ) -> List[ParseHypothesis]:
        """
        Generate parse hypotheses for a verbal token using the verb
        slot template.

        Returns a list sorted by descending confidence, capped at
        ``max_hypotheses``.
        """
        hypotheses: List[ParseHypothesis] = []

        # -- Phase 1: seed hypotheses from subject concord candidates ----
        sc_seeds: List[Tuple[str, str, str, str]] = []  # (form, key, conc_type, remaining)

        for form in self._sc_forms_desc:
            if normalised.startswith(form) and len(form) < len(normalised):
                for key, ctype in self._sc_index[form]:
                    sc_seeds.append((form, key, ctype, normalised[len(form):]))
                break  # longest match wins for this pass

        # Also consider a zero-SC case (for forms that begin with the root)
        sc_seeds.append(("", "", "", normalised))

        for sc_form, sc_key, sc_ctype, after_sc in sc_seeds:
            # -- Phase 2: try to match a TAM marker ----------------------
            tam_seeds: List[Tuple[str, object, str]] = []  # (form, TAMMarker|None, remaining)

            for form in self._tam_forms_desc:
                if after_sc.startswith(form) and len(form) < len(after_sc):
                    for tam in self._tam_by_form[form]:
                        tam_seeds.append((form, tam, after_sc[len(form):]))
                    break  # longest match wins

            # Zero-TAM case
            tam_seeds.append(("", None, after_sc))

            for tam_form, tam_obj, after_tam in tam_seeds:
                # -- Phase 3: optional object concord --------------------
                oc_seeds: List[Tuple[str, str, str, str]] = []

                for form in self._oc_forms_desc:
                    if after_tam.startswith(form) and len(form) < len(after_tam):
                        for key, ctype in self._oc_index[form]:
                            oc_seeds.append((form, key, ctype, after_tam[len(form):]))
                        break

                oc_seeds.append(("", "", "", after_tam))

                for oc_form, oc_key, oc_ctype, after_oc in oc_seeds:
                    # -- Phase 4: build post-root candidates (with AND without
                    #    extension stripping) so both parses enter the hypothesis
                    #    pool and the confidence scorer can rank them fairly.
                    s_base = after_oc

                    fv_slot = self._slot_for_content.get(
                        "final_vowels", ("SLOT10", "final_vowel")
                    )
                    ext_slot = self._slot_for_content.get(
                        "extensions", ("SLOT9", "extension_field")
                    )

                    # Strip final vowel from the shared base
                    fv_form = ""
                    s_after_fv = s_base
                    if s_after_fv and s_after_fv[-1] in self._vowel_set:
                        fv_form = s_after_fv[-1]
                        s_after_fv = s_after_fv[:-1]

                    # Candidate A: no extension — root = everything after FV strip
                    post_root_variants: List[Tuple[str, List[Morpheme]]] = [
                        (s_after_fv, []),
                    ]

                    # Candidate B: greedily match one extension from the right
                    for ext_form in self._ext_forms_desc:
                        # Require extension ≥ 2 chars to avoid single-char
                        # ambiguity (e.g. "-y-" CAUS allomorph matches too broadly)
                        if (
                            len(ext_form) >= 2
                            and s_after_fv.endswith(ext_form)
                            and len(ext_form) < len(s_after_fv)
                        ):
                            ext_root = s_after_fv[: -len(ext_form)]
                            ext_obj = self._ext_by_form[ext_form][0]
                            ext_m = Morpheme(
                                form=ext_form,
                                slot_id=ext_slot[0],
                                slot_name=ext_slot[1],
                                content_type="verb_extension",
                                gloss=ext_obj.id,
                                nc_id=None,
                            )
                            post_root_variants.append((ext_root, [ext_m]))
                            break  # one extension candidate is enough

                    for root_candidate, ext_morphemes in post_root_variants:
                        root_form = root_candidate
                        root_slot = self._root_slot
                        root_sid = root_slot.id if root_slot else "SLOT8"
                        root_sname = root_slot.name if root_slot else "verb_root"

                        # -- Assemble morpheme sequence ------------------
                        morphemes: List[Morpheme] = []

                        if sc_form:
                            sid, sname = self._slot_for("subject_concords")
                            morphemes.append(
                                Morpheme(
                                    form=sc_form,
                                    slot_id=sid,
                                    slot_name=sname,
                                    content_type="subject_concord",
                                    gloss=self._gloss_for_sc(sc_key),
                                    nc_id=sc_key if sc_key.startswith("NC") else None,
                                )
                            )

                        if tam_form and tam_obj is not None:
                            sid, sname = self._slot_for("tam")
                            morphemes.append(
                                Morpheme(
                                    form=tam_form,
                                    slot_id=sid,
                                    slot_name=sname,
                                    content_type="tam_marker",
                                    gloss=self._gloss_for_tam(tam_obj),
                                    nc_id=None,
                                )
                            )

                        if oc_form:
                            sid, sname = self._slot_for("object_concords")
                            morphemes.append(
                                Morpheme(
                                    form=oc_form,
                                    slot_id=sid,
                                    slot_name=sname,
                                    content_type="object_concord",
                                    gloss=self._gloss_for_oc(oc_key),
                                    nc_id=oc_key if oc_key.startswith("NC") else None,
                                )
                            )

                        morphemes.append(
                            Morpheme(
                                form=root_form,
                                slot_id=root_sid,
                                slot_name=root_sname,
                                content_type="verb_root",
                                gloss=root_form,
                                nc_id=None,
                            )
                        )

                        morphemes.extend(ext_morphemes)

                        if fv_form:
                            morphemes.append(
                                Morpheme(
                                    form=fv_form,
                                    slot_id=fv_slot[0],
                                    slot_name=fv_slot[1],
                                    content_type="final_vowel",
                                    gloss="FV",
                                    nc_id=None,
                                )
                            )

                        conf = _confidence(morphemes, normalised, self._obligatory_slot_ids)

                        w: List[str] = []
                        if self._sandhi_rules:
                            w.append(
                                f"Sandhi rules ({', '.join(self._sandhi_rules)}) "
                                f"are declared in the grammar but were not applied — "
                                f"surface form may differ from the segmented representation."
                            )

                        hypotheses.append(
                            ParseHypothesis(
                                morphemes=tuple(morphemes),
                                surface_form=token,
                                remaining="",
                                confidence=conf,
                                warnings=tuple(w),
                            )
                        )

        # De-duplicate (same segmented string → keep highest confidence)
        seen: Dict[str, ParseHypothesis] = {}
        for hyp in hypotheses:
            key = hyp.segmented
            if key not in seen or hyp.confidence > seen[key].confidence:
                seen[key] = hyp

        sorted_hyps = sorted(seen.values(), key=lambda h: h.confidence, reverse=True)
        return sorted_hyps[:max_hypotheses]

    # ------------------------------------------------------------------
    # Core analysis  (nominal)
    # ------------------------------------------------------------------

    def _analyze_nominal(
        self, token: str, normalised: str, max_hypotheses: int
    ) -> List[ParseHypothesis]:
        """
        Generate parse hypotheses for a nominal (noun) token by scanning
        the noun-class prefix index.
        """
        hypotheses: List[ParseHypothesis] = []

        for prefix in self._nc_prefix_forms_desc:
            if not normalised.startswith(prefix):
                continue
            stem = normalised[len(prefix):]
            if not stem:
                continue
            for nc in self._nc_by_prefix[prefix]:
                morphemes = [
                    Morpheme(
                        form=prefix,
                        slot_id="NC_PREFIX",
                        slot_name="noun_class_prefix",
                        content_type="noun_prefix",
                        gloss=f"{nc.id}.PREFIX",
                        nc_id=nc.id,
                    ),
                    Morpheme(
                        form=stem,
                        slot_id="STEM",
                        slot_name="noun_stem",
                        content_type="noun_stem",
                        gloss=stem,
                        nc_id=nc.id,
                    ),
                ]
                conf = _confidence(morphemes, normalised, frozenset())
                hypotheses.append(
                    ParseHypothesis(
                        morphemes=tuple(morphemes),
                        surface_form=token,
                        remaining="",
                        confidence=conf,
                        warnings=(),
                    )
                )

        if not hypotheses:
            # Fallback: whole token as an unsegmented stem
            m = Morpheme(
                form=normalised,
                slot_id="UNKNOWN",
                slot_name="",
                content_type="unknown",
                gloss=normalised,
                nc_id=None,
            )
            hypotheses.append(
                ParseHypothesis(
                    morphemes=(m,),
                    surface_form=token,
                    remaining="",
                    confidence=0.0,
                    warnings=("No matching noun-class prefix found.",),
                )
            )

        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses[:max_hypotheses]

    # ------------------------------------------------------------------
    # Public analysis methods
    # ------------------------------------------------------------------

    def analyze(
        self,
        token: str,
        max_hypotheses: int = 5,
    ) -> SegmentedToken:
        """
        Segment a surface token into morphemes, generating up to
        ``max_hypotheses`` ranked parse hypotheses.

        Both verbal and nominal analyses are attempted.  Verbal hypotheses
        tend to score higher when a subject-concord prefix is recognised;
        nominal hypotheses score higher when a noun-class prefix is found.
        All hypotheses are merged and ranked by confidence.

        Parameters
        ----------
        token : str
            A single word token in the target language orthography.
        max_hypotheses : int
            Maximum number of hypotheses to return (default 5).

        Returns
        -------
        SegmentedToken
            Contains all hypotheses sorted by descending confidence.

        Examples
        --------
        >>> result = analyzer.analyze("alya")
        >>> result.best.segmented
        'a-lya-a'
        >>> result.best.gloss_line
        'NC16.SUBJ-lya-FV'
        """
        if not token or not token.strip():
            raise MorphAnalysisError("token must be a non-empty string.")

        normed = self._normalise(token.strip())

        # Special-case exact match
        if normed in self._special_cases:
            label = self._special_cases[normed]
            m = Morpheme(
                form=normed,
                slot_id="LEXICAL",
                slot_name="special_case",
                content_type="special_case",
                gloss=label,
                nc_id=None,
            )
            hyp = ParseHypothesis(
                morphemes=(m,),
                surface_form=token,
                remaining="",
                confidence=1.0,
                warnings=(),
            )
            return SegmentedToken(
                token=token,
                language=self._language,
                hypotheses=(hyp,),
                best=hyp,
            )

        verbal_hyps = self._analyze_verbal(token, normed, max_hypotheses)
        nominal_hyps = self._analyze_nominal(token, normed, max_hypotheses)

        all_hyps_map: Dict[str, ParseHypothesis] = {}
        for h in verbal_hyps + nominal_hyps:
            key = h.segmented
            if key not in all_hyps_map or h.confidence > all_hyps_map[key].confidence:
                all_hyps_map[key] = h

        ranked = sorted(all_hyps_map.values(), key=lambda h: h.confidence, reverse=True)
        ranked = ranked[:max_hypotheses]

        return SegmentedToken(
            token=token,
            language=self._language,
            hypotheses=tuple(ranked),
            best=ranked[0] if ranked else None,
        )

    def analyze_verbal(
        self,
        token: str,
        max_hypotheses: int = 5,
    ) -> SegmentedToken:
        """
        Segment a token assuming it is a verb form.

        Equivalent to ``analyze()`` but restricts the search to the
        verbal slot template only (no nominal prefix scan).

        Parameters
        ----------
        token : str
            A single verb word form.
        max_hypotheses : int
            Maximum number of hypotheses to return.

        Returns
        -------
        SegmentedToken
        """
        normed = self._normalise(token.strip())
        hyps = self._analyze_verbal(token, normed, max_hypotheses)
        if not hyps:
            m = Morpheme(
                form=normed,
                slot_id="UNKNOWN",
                slot_name="",
                content_type="unknown",
                gloss=normed,
                nc_id=None,
            )
            hyps = [
                ParseHypothesis(
                    morphemes=(m,),
                    surface_form=token,
                    remaining="",
                    confidence=0.0,
                    warnings=("No verbal analysis found.",),
                )
            ]
        return SegmentedToken(
            token=token,
            language=self._language,
            hypotheses=tuple(hyps),
            best=hyps[0],
        )

    def analyze_nominal(
        self,
        token: str,
        max_hypotheses: int = 5,
    ) -> SegmentedToken:
        """
        Segment a token assuming it is a noun form.

        Restricts the search to noun-class prefix matching only.

        Parameters
        ----------
        token : str
            A single nominal word form.
        max_hypotheses : int
            Maximum number of hypotheses.

        Returns
        -------
        SegmentedToken
        """
        normed = self._normalise(token.strip())
        hyps = self._analyze_nominal(token, normed, max_hypotheses)
        return SegmentedToken(
            token=token,
            language=self._language,
            hypotheses=tuple(hyps),
            best=hyps[0] if hyps else None,
        )

    def segment_text(
        self,
        text: str,
        max_hypotheses: int = 3,
    ) -> List[SegmentedToken]:
        """
        Tokenize running text on word boundaries and analyze each token.

        Parameters
        ----------
        text : str
            A sentence or passage in the target language.
        max_hypotheses : int
            Passed through to ``analyze()`` for each token.

        Returns
        -------
        List[SegmentedToken]
            One entry per word token, preserving left-to-right order.

        Examples
        --------
        >>> results = analyzer.segment_text("mwana alya nyama")
        >>> len(results)
        3
        """
        tokens = self._word_boundary_re.split(text.strip())
        return [
            self.analyze(t, max_hypotheses=max_hypotheses)
            for t in tokens
            if t
        ]

    # ------------------------------------------------------------------
    # Surface form generation (F-01)
    # ------------------------------------------------------------------

    def generate(
        self,
        features: MorphFeatureBundle,
    ) -> SurfaceForm:
        """
        Generate an inflected verb surface form from a feature bundle.

        Walks the verb slot template in position order, filling each slot
        from the feature bundle using the public API concord, TAM, and
        extension data.

        Phonological post-processing (sandhi, vowel harmony) is *not*
        applied — the sandhi rule identifiers declared in the grammar are
        listed in ``SurfaceForm.warnings`` so that a higher-level
        surface-form generator (F-01) can apply them.

        Parameters
        ----------
        features : MorphFeatureBundle
            Feature specification including root, subject NC, TAM id,
            optional object NC, extensions, polarity, and final vowel.

        Returns
        -------
        SurfaceForm
            The generated form with surface string, segmented representation,
            Leipzig gloss, constituent morphemes, and warnings.

        Raises
        ------
        MorphAnalysisError
            If ``features.root`` is empty, ``features.tam_id`` is not found
            in the grammar, or ``features.subject_nc`` has no entry in the
            subject-concord paradigm.

        Examples
        --------
        >>> bundle = MorphFeatureBundle(
        ...     root="lya", subject_nc="NC7", tam_id="TAM_PRES"
        ... )
        >>> sf = analyzer.generate(bundle)
        >>> sf.surface
        'cilya'
        >>> sf.gloss
        'NC7.SUBJ-lya-FV'
        """
        if not features.root:
            raise MorphAnalysisError("MorphFeatureBundle.root must not be empty.")

        tam_obj = self._tam_by_id.get(features.tam_id)
        if tam_obj is None:
            available = sorted(self._tam_by_id.keys())
            raise MorphAnalysisError(
                f"TAM id {features.tam_id!r} not found in grammar for "
                f"{self._language!r}.  Available: {available}"
            )

        sc_map = self._concord_map.get("subject_concords", {})
        sc_form_raw = sc_map.get(features.subject_nc)
        if sc_form_raw is None:
            # Try base class fallback
            base = _base_nc(features.subject_nc)
            sc_form_raw = sc_map.get(base)
        if sc_form_raw is None:
            available = sorted(sc_map.keys())
            raise MorphAnalysisError(
                f"Subject concord key {features.subject_nc!r} not found for "
                f"{self._language!r}.  Available: {available}"
            )
        sc_form = _strip_hyphens(sc_form_raw)

        oc_form: Optional[str] = None
        if features.object_nc:
            oc_map = self._concord_map.get("object_concords", {})
            raw = oc_map.get(features.object_nc)
            if raw is None:
                base = _base_nc(features.object_nc)
                raw = oc_map.get(base)
            if raw is not None:
                oc_form = _strip_hyphens(raw)

        # Resolve extensions
        ext_objects = []
        for ext_id in features.extensions:
            ext_obj = self._ext_by_id.get(ext_id)
            if ext_obj is None:
                raise MorphAnalysisError(
                    f"Extension id {ext_id!r} not found in grammar for "
                    f"{self._language!r}.  Available: {sorted(self._ext_by_id.keys())}"
                )
            ext_objects.append(ext_obj)

        tam_form = _strip_hyphens(tam_obj.form)

        # -- Walk slots in order, fill from feature bundle ---------------
        morphemes: List[Morpheme] = []
        warnings: List[str] = []

        for slot in self._slot_order:
            types = slot.allowed_content_types

            # Subject concord
            if any(t in types for t in ("subject_concords", "relative_concords")):
                if sc_form:
                    morphemes.append(
                        Morpheme(
                            form=sc_form,
                            slot_id=slot.id,
                            slot_name=slot.name,
                            content_type="subject_concord",
                            gloss=self._gloss_for_sc(features.subject_nc),
                            nc_id=(
                                features.subject_nc
                                if features.subject_nc.startswith("NC")
                                else None
                            ),
                        )
                    )

            # TAM (pre-root in many Bantu languages)
            elif "tam" in types:
                if tam_form:
                    morphemes.append(
                        Morpheme(
                            form=tam_form,
                            slot_id=slot.id,
                            slot_name=slot.name,
                            content_type="tam_marker",
                            gloss=self._gloss_for_tam(tam_obj),
                            nc_id=None,
                        )
                    )

            # Object concord
            elif "object_concords" in types:
                if oc_form:
                    morphemes.append(
                        Morpheme(
                            form=oc_form,
                            slot_id=slot.id,
                            slot_name=slot.name,
                            content_type="object_concord",
                            gloss=self._gloss_for_oc(features.object_nc or ""),
                            nc_id=(
                                features.object_nc
                                if features.object_nc and features.object_nc.startswith("NC")
                                else None
                            ),
                        )
                    )

            # Verb root
            elif "root" in types:
                morphemes.append(
                    Morpheme(
                        form=features.root,
                        slot_id=slot.id,
                        slot_name=slot.name,
                        content_type="verb_root",
                        gloss=features.root,
                        nc_id=None,
                    )
                )

            # Extensions
            elif "extensions" in types:
                for ext_obj in ext_objects:
                    ef = _strip_hyphens(ext_obj.canonical_form)
                    morphemes.append(
                        Morpheme(
                            form=ef,
                            slot_id=slot.id,
                            slot_name=slot.name,
                            content_type="verb_extension",
                            gloss=ext_obj.id,
                            nc_id=None,
                        )
                    )

            # Final vowel
            elif "final_vowels" in types:
                morphemes.append(
                    Morpheme(
                        form=features.final_vowel,
                        slot_id=slot.id,
                        slot_name=slot.name,
                        content_type="final_vowel",
                        gloss="FV",
                        nc_id=None,
                    )
                )

            # Slots whose content is not in the public API (negation, modal,
            # post-final) — skip in affirmative; warn for negative polarity.
            elif features.polarity == "negative" and any(
                "negat" in t or "neg" in t for t in types
            ):
                warnings.append(
                    f"Negative polarity requested but slot {slot.id} "
                    f"({types}) is not accessible via the Part 6 public API.  "
                    f"Affirmative form generated instead."
                )

        # Filter morphemes with empty forms (zero morphemes, etc.)
        morphemes = [m for m in morphemes if m.form]

        surface = "".join(m.form for m in morphemes)
        segmented = "-".join(m.form for m in morphemes)
        gloss = "-".join(m.gloss for m in morphemes)

        if self._sandhi_rules:
            warnings.append(
                f"The following sandhi rules are declared in the grammar but "
                f"were not applied (phonological transformations are not "
                f"encoded in the public API): "
                f"{', '.join(self._sandhi_rules)}.  "
                f"Surface form may require post-processing."
            )
        if self._vowel_harmony_rules:
            warnings.append(
                f"Vowel-harmony rules "
                f"({', '.join(self._vowel_harmony_rules)}) "
                f"were not applied."
            )

        return SurfaceForm(
            surface=surface,
            segmented=segmented,
            gloss=gloss,
            morphemes=tuple(morphemes),
            features=features,
            warnings=tuple(warnings),
        )

    # ------------------------------------------------------------------
    # Interlinear gloss
    # ------------------------------------------------------------------

    def generate_interlinear(
        self,
        token: str,
        max_hypotheses: int = 1,
    ) -> str:
        """
        Produce a two-line Leipzig interlinear gloss for a single token.

        Line 1: morpheme-segmented form (e.g. ``a-lya-a``)
        Line 2: gloss line               (e.g. ``NC1.SUBJ-eat-FV``)

        Uses the best parse hypothesis from ``analyze()``.

        Parameters
        ----------
        token : str
            A single word token.
        max_hypotheses : int
            Passed to ``analyze()``.

        Returns
        -------
        str
            Two-line string ready for display or LaTeX gb4e formatting.

        Examples
        --------
        >>> print(analyzer.generate_interlinear("alya"))
        a-lya-a
        NC16.SUBJ-lya-FV
        """
        result = self.analyze(token, max_hypotheses=max_hypotheses)
        if result.best is None:
            return f"{token}\n???"
        best = result.best
        return f"{best.segmented}\n{best.gloss_line}"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def language(self) -> str:
        """The language identifier from the grammar loader."""
        return self._language

    @property
    def loader(self):  # type: ignore[no-untyped-def]
        """The ``GobeloGrammarLoader`` instance this analyzer was built from."""
        return self._loader