"""
apps/verb_slot_validator.py
============================
VerbSlotValidator — validate that a verb morpheme sequence is
well-formed with respect to the slot template of the loaded language.

This module implements GGT Part 9's ``VerbSlotValidator`` app.  It
accepts a ``SegmentedToken`` produced by ``MorphologicalAnalyzer``
(or an explicit list of ``SlotAssignment`` objects for programmatic
use) and runs a layered set of structural validation rules derived
entirely from the ``GobeloGrammarLoader`` public API.

Validation rule catalogue
--------------------------
Rules are organised into four layers, each with a ``rule_id``,
severity (``ERROR`` or ``WARNING``), and a human-readable message.

Layer 1 — Slot structure (from ``get_verb_slots()``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``OBLIG_SLOT_MISSING``  ERROR
    A slot marked ``obligatory=True`` has no morpheme assigned.

``CONTENT_TYPE_MISMATCH``  ERROR
    A morpheme's content type is not listed in the slot's
    ``allowed_content_types``.

``SLOT_OUT_OF_ORDER``  ERROR
    Morpheme positions are not monotonically non-decreasing
    (slot B appears before slot A despite B.position > A.position).

``OBLIG_SLOT_DUPLICATE``  WARNING
    A slot marked ``obligatory=True`` has more than one morpheme
    assigned (unusual — may indicate an analysis error).

``UNKNOWN_SLOT``  WARNING
    A morpheme references a slot id not found in the grammar's slot
    list (e.g. ``"UNKNOWN"``, ``"NC_PREFIX"`` from a nominal parse).

Layer 2 — Reference validity (from concord, TAM, extension indexes)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``INVALID_SUBJECT_CONCORD``  ERROR
    The subject-concord key extracted from the gloss does not exist
    in ``get_subject_concords().entries``.

``INVALID_OBJECT_CONCORD``  ERROR
    The object-concord key extracted from the gloss does not exist
    in ``get_object_concords().entries``.

``INVALID_EXTENSION``  ERROR
    An extension gloss is not a known ``VerbExtension.id``.

Layer 3 — Extension constraints (from ``get_verb_template()`` and ``get_extensions()``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``EXT_ZONE_ORDER``  ERROR
    Extensions violate the canonical zone precedence Z1 < Z2 < Z3 < Z4.

``EXT_INTRA_ZONE_ORDER``  ERROR
    Within a single zone the extensions appear in the wrong internal
    order (e.g. CAUS before APPL within Z1).

``EXT_INCOMPATIBLE``  ERROR
    Two extensions that are grammatically incompatible (e.g. PASS + STAT)
    appear in the same sequence.

``EXT_PASS_NOT_FINAL``  ERROR
    PASS does not appear as the last extension in the sequence
    (PASS is a Z3 extension constrained to always be final).

``EXT_MAX_EXCEEDED``  ERROR
    The number of extensions exceeds the grammar's
    ``validation.extension_validation.max_extensions`` value.

``EXT_TYPICAL_MAX_EXCEEDED``  WARNING
    The number of extensions exceeds the grammar's
    ``validation.extension_validation.typical_max`` value.
    Technically valid but rare in natural speech.

Layer 4 — Co-occurrence / agreement constraints (from ``get_verb_template()``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``RECIP_REQUIRES_PLURAL``  WARNING
    RECIP is present but the subject concord key does not indicate
    plural number (best-effort check; plural NC classes are checked
    against ``get_noun_classes()``).

``NEG_PRE_INFIX_EXCLUSIVE``  WARNING
    Both ``negation_pre`` (SLOT1) and ``negation_infix`` (SLOT4) are
    filled — the grammar documents these as mutually exclusive in
    most constructions.

Design contract (Part 9)
-------------------------
* Accepts a ``GobeloGrammarLoader`` as its **only** grammar dependency.
* Uses **only** the public API (Part 6).
* Language-agnostic — all rules are derived from loader data.
* Handles ``GGTError`` subclasses gracefully.

Usage
------
::

    from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    from gobelo_grammar_toolkit.apps.morphological_analyzer import (
        MorphologicalAnalyzer,
    )
    from gobelo_grammar_toolkit.apps.verb_slot_validator import (
        VerbSlotValidator,
    )

    loader    = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    analyzer  = MorphologicalAnalyzer(loader)
    validator = VerbSlotValidator(loader)

    tok    = analyzer.analyze("balya")
    result = validator.validate(tok)

    print(result.is_valid)          # True / False
    for v in result.violations:
        print(v.severity, v.rule_id, v.message)

    # Direct slot-assignment path (no MorphologicalAnalyzer needed)
    from gobelo_grammar_toolkit.apps.verb_slot_validator import SlotAssignment
    assignments = [
        SlotAssignment("SLOT3", "subject_concord", "ba", "3PL_HUMAN.SUBJ", None),
        SlotAssignment("SLOT8", "verb_root",       "ly", "ly",              None),
        SlotAssignment("SLOT10","final_vowel",      "a", "FV",              None),
    ]
    result2 = validator.validate_assignments(assignments)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from gobelo_grammar_toolkit.core.exceptions import GGTError

__all__ = [
    "VerbSlotValidator",
    "SlotAssignment",
    "ValidationViolation",
    "ValidationResult",
    "VerbSlotValidationError",
]

# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class VerbSlotValidationError(GGTError):
    """
    Raised when the validator itself encounters an unrecoverable
    configuration problem — for example, the loader returns no verb slots.
    Distinct from validation *failures*, which are reported via
    ``ValidationResult.violations`` rather than exceptions.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


# ---------------------------------------------------------------------------
# Input / output dataclasses
# ---------------------------------------------------------------------------

_ZONE_ORDER = {"Z1": 1, "Z2": 2, "Z3": 3, "Z4": 4}
_SC_KEY_RE  = re.compile(r"^(.+?)(?:\.(SUBJ|NEG).*)?$")
_OC_KEY_RE  = re.compile(r"^(.+?)\.OBJ")
_NC_NUM_RE  = re.compile(r"^[A-Za-z]+(\d+)")


@dataclass(frozen=True)
class SlotAssignment:
    """
    A single morpheme assigned to a verb slot.

    This is the primitive unit consumed by ``VerbSlotValidator``.
    It can be constructed manually or derived from ``MorphologicalAnalyzer``
    output via ``VerbSlotValidator.assignments_from_token()``.

    Parameters
    ----------
    slot_id : str
        The slot identifier, e.g. ``"SLOT3"``, ``"SLOT8"``.  Use
        ``"UNKNOWN"`` for morphemes that could not be assigned to a slot.
    content_type : str
        The morpheme category, using the ``MorphologicalAnalyzer``
        vocabulary: ``"subject_concord"``, ``"object_concord"``,
        ``"tam_marker"``, ``"verb_root"``, ``"verb_extension"``,
        ``"final_vowel"``.
    form : str
        The surface string of the morpheme, e.g. ``"ba"``, ``"lya"``.
    gloss : str
        Leipzig-style gloss, e.g. ``"3PL_HUMAN.SUBJ"``, ``"PST.PFV"``,
        ``"APPL"``, ``"lya"``, ``"FV"``.
    nc_id : Optional[str]
        The noun-class id associated with this morpheme, or ``None``.
    """

    slot_id: str
    content_type: str
    form: str
    gloss: str
    nc_id: Optional[str]


@dataclass(frozen=True)
class ValidationViolation:
    """
    A single validation rule violation.

    Parameters
    ----------
    rule_id : str
        Machine-readable rule identifier, e.g. ``"OBLIG_SLOT_MISSING"``.
    severity : str
        ``"ERROR"`` — sequence is ill-formed; ``"WARNING"`` — sequence is
        unusual but may be valid.
    slot_id : Optional[str]
        The slot involved, if applicable.
    morpheme_form : Optional[str]
        The surface form of the offending morpheme, if applicable.
    message : str
        Human-readable description for linguists.
    """

    rule_id: str
    severity: str
    slot_id: Optional[str]
    morpheme_form: Optional[str]
    message: str


@dataclass(frozen=True)
class ValidationResult:
    """
    Complete validation result for one morpheme sequence.

    Parameters
    ----------
    is_valid : bool
        ``True`` if and only if there are no ``ERROR``-severity violations.
        ``WARNING`` violations alone do not make a sequence invalid.
    morpheme_sequence : Tuple[SlotAssignment, ...]
        The input sequence that was validated (in the order passed).
    violations : Tuple[ValidationViolation, ...]
        All violations (errors and warnings combined), in the order they
        were detected.
    errors : Tuple[ValidationViolation, ...]
        Only ``ERROR``-severity violations.
    warnings : Tuple[ValidationViolation, ...]
        Only ``WARNING``-severity violations.
    slot_coverage : Dict[str, int]
        Mapping from slot id to the number of morphemes assigned to it.
        Only slots that have at least one assignment are included.
    error_count : int
        Length of ``errors``.
    warning_count : int
        Length of ``warnings``.
    """

    is_valid: bool
    morpheme_sequence: Tuple[SlotAssignment, ...]
    violations: Tuple[ValidationViolation, ...]
    errors: Tuple[ValidationViolation, ...]
    warnings: Tuple[ValidationViolation, ...]
    slot_coverage: Dict[str, int]
    error_count: int
    warning_count: int

    def summary(self) -> str:
        """
        Return a one-line human-readable summary of the result.

        Examples
        --------
        ``"VALID — 0 errors, 0 warnings"``
        ``"INVALID — 2 errors, 1 warning: OBLIG_SLOT_MISSING, EXT_ZONE_ORDER"``
        """
        status = "VALID" if self.is_valid else "INVALID"
        rule_ids = ", ".join(v.rule_id for v in self.errors)
        parts = [
            f"{status} — {self.error_count} error{'s' if self.error_count != 1 else ''}",
            f"{self.warning_count} warning{'s' if self.warning_count != 1 else ''}",
        ]
        if rule_ids:
            parts.append(f"({rule_ids})")
        return "; ".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm_content_type(ct: str) -> str:
    """
    Normalise a ``MorphologicalAnalyzer`` content_type to the
    vocabulary used in ``VerbSlot.allowed_content_types``.

    The analyzer uses singular forms (``"subject_concord"``); the slot
    template uses the concord-paradigm name (``"subject_concords"``).
    """
    return {
        "subject_concord": "subject_concords",
        "object_concord":  "object_concords",
        "tam_marker":      "tam",
        "verb_root":       "root",
        "verb_extension":  "extensions",
        "final_vowel":     "final_vowels",
    }.get(ct, ct)


def _extract_sc_key(gloss: str) -> str:
    """
    Extract the subject-concord lookup key from a gloss string.

    ``"NC7.SUBJ"`` → ``"NC7"``
    ``"3PL_HUMAN.SUBJ"`` → ``"3PL_HUMAN"``
    ``"1SG.SUBJ"`` → ``"1SG"``
    ``"NEG.SG.SUBJ"`` → ``"NEG.SG"``
    """
    # Remove .SUBJ and .NEG.SUBJ suffixes
    key = re.sub(r"\.SUBJ(\.NEG)?$", "", gloss)
    return key.strip()


def _extract_oc_key(gloss: str) -> str:
    """Extract the object-concord lookup key from a gloss string."""
    key = re.sub(r"\.OBJ$", "", gloss)
    return key.strip()


def _key_is_plural(key: str, nc_plural_ids: FrozenSet[str]) -> Optional[bool]:
    """
    Best-effort check of whether a concord key indicates plural number.

    Returns ``True`` if definitely plural, ``False`` if definitely
    singular, ``None`` if unknown.
    """
    if "PL" in key:
        return True
    if "SG" in key:
        return False
    # NC-keyed: check if this NC has a singular_counterpart (→ plural)
    if key in nc_plural_ids:
        return True
    # NC-keyed: check if this NC has a plural_counterpart only (→ singular)
    if _NC_NUM_RE.match(key):
        return False  # assume singular if in the NC namespace and not in plural set
    return None


# ---------------------------------------------------------------------------
# VerbSlotValidator
# ---------------------------------------------------------------------------


class VerbSlotValidator:
    """
    Language-agnostic structural validator for Bantu verb morpheme sequences.

    Builds all validation indexes from the ``GobeloGrammarLoader`` public API
    at construction time.  The loader is not referenced after ``__init__``.

    Parameters
    ----------
    loader : GobeloGrammarLoader
        An initialised loader for the target language.

    Raises
    ------
    VerbSlotValidationError
        If ``GGTError`` is raised during index construction, or if the
        loader returns no verb slots (grammar is unusable for validation).

    Examples
    --------
    >>> from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    >>> from gobelo_grammar_toolkit.apps.verb_slot_validator import VerbSlotValidator
    >>> loader    = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    >>> validator = VerbSlotValidator(loader)
    >>> # … (see module docstring for full usage)
    """

    def __init__(self, loader) -> None:  # type: ignore[no-untyped-def]
        try:
            self._build_indexes(loader)
        except GGTError as exc:
            raise VerbSlotValidationError(
                f"Failed to build VerbSlotValidator indexes: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_indexes(self, loader) -> None:  # type: ignore[no-untyped-def]
        meta = loader.get_metadata()
        self._language: str = meta.language

        # ── Verb slots ────────────────────────────────────────────────
        slots = loader.get_verb_slots()
        if not slots:
            raise VerbSlotValidationError(
                f"No verb slots found in grammar for {self._language!r}; "
                f"cannot validate morpheme sequences."
            )
        self._slot_by_id: Dict[str, object] = {s.id: s for s in slots}
        self._slot_position: Dict[str, int] = {s.id: s.position for s in slots}
        self._obligatory_ids: FrozenSet[str] = frozenset(
            s.id for s in slots if s.obligatory
        )
        # slot_id → set of normalised allowed content types
        self._allowed_types: Dict[str, FrozenSet[str]] = {}
        for s in slots:
            types: Set[str] = set()
            for t in s.allowed_content_types:
                # Strip "concords." qualifier prefix used in SLOT2
                types.add(t.split(".")[-1])
                types.add(t)  # also keep the full form
            self._allowed_types[s.id] = frozenset(types)

        # ── Subject / object concord keys ─────────────────────────────
        self._sc_keys: FrozenSet[str] = frozenset()
        self._oc_keys: FrozenSet[str] = frozenset()
        try:
            sc = loader.get_subject_concords()
            self._sc_keys = frozenset(sc.entries.keys())
        except GGTError:
            pass
        try:
            oc = loader.get_object_concords()
            self._oc_keys = frozenset(oc.entries.keys())
        except GGTError:
            pass

        # ── TAM markers ───────────────────────────────────────────────
        self._tam_ids: FrozenSet[str] = frozenset()
        try:
            self._tam_ids = frozenset(t.id for t in loader.get_tam_markers())
        except GGTError:
            pass

        # ── Extensions ────────────────────────────────────────────────
        # ext_id → zone string ("Z1" … "Z4")
        self._ext_zone: Dict[str, str] = {}
        self._ext_ids: FrozenSet[str] = frozenset()
        try:
            for ext in loader.get_extensions():
                self._ext_zone[ext.id] = ext.zone
            self._ext_ids = frozenset(self._ext_zone.keys())
        except GGTError:
            pass

        # ── Noun classes: which are plural ────────────────────────────
        # An NC is "plural" if it has a singular_counterpart (i.e. it IS the plural form)
        self._plural_nc_ids: FrozenSet[str] = frozenset()
        try:
            self._plural_nc_ids = frozenset(
                nc.id
                for nc in loader.get_noun_classes(active_only=False)
                if getattr(nc, "singular_counterpart", None) is not None
            )
        except GGTError:
            pass

        # ── Verb template constraint data ─────────────────────────────
        # Read once; all access via helper methods below.
        self._max_extensions: int = 5      # spec default
        self._typical_max: int = 3         # spec default
        self._zone_internal_order: Dict[str, List[str]] = {}
        self._ext_incompatible: Dict[str, FrozenSet[str]] = {}
        self._pass_must_be_final: bool = False

        try:
            vt = loader.get_verb_template()
            self._load_template_constraints(vt)
        except GGTError:
            pass  # degrade gracefully — rules that need template data will be skipped

    def _load_template_constraints(self, vt: dict) -> None:
        """Parse all constraint data from the verb template dict."""

        def _dig(d: dict, *keys):
            for k in keys:
                if not isinstance(d, dict):
                    return None
                d = d.get(k)
            return d

        # Max / typical extension counts
        max_ext = _dig(vt, "validation", "extension_validation", "max_extensions")
        if isinstance(max_ext, (int, str)):
            try:
                self._max_extensions = int(max_ext)
            except (ValueError, TypeError):
                pass

        typ_max = _dig(vt, "validation", "extension_validation", "typical_max")
        if isinstance(typ_max, (int, str)):
            try:
                self._typical_max = int(typ_max)
            except (ValueError, TypeError):
                pass

        # Zone internal ordering
        zones_data = _dig(vt, "extensions", "extension_ordering", "zones")
        if isinstance(zones_data, dict):
            for zone_id, zone_info in zones_data.items():
                if isinstance(zone_info, dict):
                    order = zone_info.get("internal_order")
                    if isinstance(order, list):
                        self._zone_internal_order[zone_id] = [
                            str(x) for x in order
                        ]

        # Extension-level incompatibilities (from individual extension entries)
        ext_entries = vt.get("extensions", {})
        if isinstance(ext_entries, dict):
            for ext_id, ext_data in ext_entries.items():
                if not isinstance(ext_data, dict):
                    continue
                incompat_list = _dig(ext_data, "constraints", "incompatible_with")
                if isinstance(incompat_list, list):
                    self._ext_incompatible[ext_id] = frozenset(
                        str(x) for x in incompat_list if x
                    )

        # PASS-final constraint from strict_rules
        strict = _dig(vt, "extensions", "extension_ordering", "strict_rules")
        if isinstance(strict, list):
            for rule in strict:
                if isinstance(rule, dict):
                    applies = rule.get("applies_to", [])
                    if "PASS" in (applies if isinstance(applies, list) else []):
                        self._pass_must_be_final = True

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def validate(self, token) -> ValidationResult:  # type: ignore[no-untyped-def]
        """
        Validate a ``SegmentedToken`` against the grammar's verb slot
        template using the best parse hypothesis.

        Parameters
        ----------
        token : SegmentedToken
            Output of ``MorphologicalAnalyzer.analyze()``.  Uses
            ``token.best.morphemes`` as the morpheme sequence.

        Returns
        -------
        ValidationResult

        Examples
        --------
        >>> tok    = analyzer.analyze("balya")
        >>> result = validator.validate(tok)
        >>> result.is_valid
        True
        >>> result.summary()
        'VALID — 0 errors, 0 warnings'
        """
        assignments = self.assignments_from_token(token)
        return self.validate_assignments(assignments)

    def validate_assignments(
        self,
        assignments: List[SlotAssignment],
    ) -> ValidationResult:
        """
        Validate an explicit list of ``SlotAssignment`` objects.

        This is the primary validation engine.  All other ``validate_*``
        methods convert their input to a list of ``SlotAssignment`` and
        delegate here.

        Parameters
        ----------
        assignments : List[SlotAssignment]
            Ordered sequence of slot assignments representing the morpheme
            sequence to validate.  Order must match the intended left-to-right
            surface order.

        Returns
        -------
        ValidationResult
        """
        violations: List[ValidationViolation] = []

        # ── Layer 1: slot structure ───────────────────────────────────
        violations.extend(self._check_slot_structure(assignments))

        # ── Layer 2: reference validity ───────────────────────────────
        violations.extend(self._check_reference_validity(assignments))

        # ── Layer 3: extension constraints ───────────────────────────
        ext_assignments = [
            a for a in assignments if a.content_type == "verb_extension"
        ]
        violations.extend(self._check_extension_constraints(ext_assignments))

        # ── Layer 4: co-occurrence / agreement ────────────────────────
        violations.extend(self._check_cooccurrence_constraints(assignments))

        # Partition errors vs warnings
        errors   = tuple(v for v in violations if v.severity == "ERROR")
        warnings = tuple(v for v in violations if v.severity == "WARNING")

        # Slot coverage map
        coverage: Dict[str, int] = {}
        for a in assignments:
            coverage[a.slot_id] = coverage.get(a.slot_id, 0) + 1

        return ValidationResult(
            is_valid=len(errors) == 0,
            morpheme_sequence=tuple(assignments),
            violations=tuple(violations),
            errors=errors,
            warnings=warnings,
            slot_coverage=coverage,
            error_count=len(errors),
            warning_count=len(warnings),
        )

    def validate_morpheme_sequence(
        self,
        morphemes,  # Iterable[Morpheme]
    ) -> ValidationResult:
        """
        Validate an iterable of ``Morpheme`` objects directly (without
        wrapping them in a ``SegmentedToken``).

        Parameters
        ----------
        morphemes : Iterable[Morpheme]

        Returns
        -------
        ValidationResult
        """
        assignments = [
            SlotAssignment(
                slot_id=getattr(m, "slot_id", "UNKNOWN"),
                content_type=getattr(m, "content_type", "unknown"),
                form=getattr(m, "form", ""),
                gloss=getattr(m, "gloss", ""),
                nc_id=getattr(m, "nc_id", None),
            )
            for m in morphemes
        ]
        return self.validate_assignments(assignments)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def assignments_from_token(token) -> List[SlotAssignment]:  # type: ignore[no-untyped-def]
        """
        Convert a ``SegmentedToken``'s best hypothesis into a list of
        ``SlotAssignment`` objects.

        Parameters
        ----------
        token : SegmentedToken

        Returns
        -------
        List[SlotAssignment]
            Empty list if ``token.best`` is ``None``.
        """
        best = getattr(token, "best", None)
        if best is None:
            return []
        morphemes = getattr(best, "morphemes", ())
        return [
            SlotAssignment(
                slot_id=getattr(m, "slot_id", "UNKNOWN"),
                content_type=getattr(m, "content_type", "unknown"),
                form=getattr(m, "form", ""),
                gloss=getattr(m, "gloss", ""),
                nc_id=getattr(m, "nc_id", None),
            )
            for m in morphemes
        ]

    # ------------------------------------------------------------------
    # Layer 1: slot structure checks
    # ------------------------------------------------------------------

    def _check_slot_structure(
        self, assignments: List[SlotAssignment]
    ) -> List[ValidationViolation]:
        violations: List[ValidationViolation] = []
        assigned_ids = {a.slot_id for a in assignments}
        slot_counts: Dict[str, int] = {}
        for a in assignments:
            slot_counts[a.slot_id] = slot_counts.get(a.slot_id, 0) + 1

        # OBLIG_SLOT_MISSING
        for sid in self._obligatory_ids:
            if sid not in assigned_ids:
                slot = self._slot_by_id.get(sid)
                sname = getattr(slot, "name", sid) if slot else sid
                violations.append(
                    ValidationViolation(
                        rule_id="OBLIG_SLOT_MISSING",
                        severity="ERROR",
                        slot_id=sid,
                        morpheme_form=None,
                        message=(
                            f"Obligatory slot {sid} ({sname!r}) has no morpheme assigned. "
                            f"Every finite verb requires this slot to be filled."
                        ),
                    )
                )

        # OBLIG_SLOT_DUPLICATE
        for sid in self._obligatory_ids:
            if slot_counts.get(sid, 0) > 1:
                violations.append(
                    ValidationViolation(
                        rule_id="OBLIG_SLOT_DUPLICATE",
                        severity="WARNING",
                        slot_id=sid,
                        morpheme_form=None,
                        message=(
                            f"Obligatory slot {sid} has {slot_counts[sid]} morphemes "
                            f"assigned (expected 1). This may indicate an analysis error."
                        ),
                    )
                )

        # CONTENT_TYPE_MISMATCH and UNKNOWN_SLOT
        for a in assignments:
            if a.slot_id not in self._slot_by_id:
                if a.slot_id not in ("UNKNOWN", "NC_PREFIX", "STEM", "LEXICAL"):
                    violations.append(
                        ValidationViolation(
                            rule_id="UNKNOWN_SLOT",
                            severity="WARNING",
                            slot_id=a.slot_id,
                            morpheme_form=a.form,
                            message=(
                                f"Slot {a.slot_id!r} is not defined in the grammar's "
                                f"verb slot template. Morpheme {a.form!r} ({a.gloss!r}) "
                                f"cannot be validated for content type."
                            ),
                        )
                    )
                continue  # can't check content type for unknown slots

            allowed = self._allowed_types.get(a.slot_id, frozenset())
            norm_ct = _norm_content_type(a.content_type)
            # Accept both the normalised form and the raw form
            if norm_ct not in allowed and a.content_type not in allowed:
                violations.append(
                    ValidationViolation(
                        rule_id="CONTENT_TYPE_MISMATCH",
                        severity="ERROR",
                        slot_id=a.slot_id,
                        morpheme_form=a.form,
                        message=(
                            f"Morpheme {a.form!r} (type {a.content_type!r}) in {a.slot_id} "
                            f"has a content type not listed as allowed for that slot. "
                            f"Allowed: {sorted(allowed)}."
                        ),
                    )
                )

        # SLOT_OUT_OF_ORDER — verify monotone non-decreasing positions
        last_pos = -1
        last_sid = ""
        for a in assignments:
            pos = self._slot_position.get(a.slot_id, -1)
            if pos == -1:
                continue  # unknown slot — skip ordering check
            if pos < last_pos:
                violations.append(
                    ValidationViolation(
                        rule_id="SLOT_OUT_OF_ORDER",
                        severity="ERROR",
                        slot_id=a.slot_id,
                        morpheme_form=a.form,
                        message=(
                            f"Slot {a.slot_id} (position {pos}) appears after "
                            f"{last_sid} (position {last_pos}), violating the "
                            f"canonical slot ordering."
                        ),
                    )
                )
            last_pos = pos
            last_sid = a.slot_id

        return violations

    # ------------------------------------------------------------------
    # Layer 2: reference validity
    # ------------------------------------------------------------------

    def _check_reference_validity(
        self, assignments: List[SlotAssignment]
    ) -> List[ValidationViolation]:
        violations: List[ValidationViolation] = []

        for a in assignments:
            ct = a.content_type

            # Subject concord key validity
            if ct == "subject_concord" and self._sc_keys:
                key = _extract_sc_key(a.gloss)
                if key and key not in self._sc_keys:
                    violations.append(
                        ValidationViolation(
                            rule_id="INVALID_SUBJECT_CONCORD",
                            severity="ERROR",
                            slot_id=a.slot_id,
                            morpheme_form=a.form,
                            message=(
                                f"Subject-concord key {key!r} (from gloss {a.gloss!r}) "
                                f"is not in the grammar's subject concord paradigm."
                            ),
                        )
                    )

            # Object concord key validity
            elif ct == "object_concord" and self._oc_keys:
                key = _extract_oc_key(a.gloss)
                if key and key not in self._oc_keys:
                    violations.append(
                        ValidationViolation(
                            rule_id="INVALID_OBJECT_CONCORD",
                            severity="ERROR",
                            slot_id=a.slot_id,
                            morpheme_form=a.form,
                            message=(
                                f"Object-concord key {key!r} (from gloss {a.gloss!r}) "
                                f"is not in the grammar's object concord paradigm."
                            ),
                        )
                    )

            # Extension id validity
            elif ct == "verb_extension" and self._ext_ids:
                ext_id = a.gloss  # gloss is the extension id (e.g. "APPL")
                if ext_id and ext_id not in self._ext_ids:
                    violations.append(
                        ValidationViolation(
                            rule_id="INVALID_EXTENSION",
                            severity="ERROR",
                            slot_id=a.slot_id,
                            morpheme_form=a.form,
                            message=(
                                f"Extension id {ext_id!r} is not a known verb extension "
                                f"in the grammar. Known: {sorted(self._ext_ids)}."
                            ),
                        )
                    )

        return violations

    # ------------------------------------------------------------------
    # Layer 3: extension constraints
    # ------------------------------------------------------------------

    def _check_extension_constraints(
        self, ext_assignments: List[SlotAssignment]
    ) -> List[ValidationViolation]:
        violations: List[ValidationViolation] = []

        if not ext_assignments:
            return violations

        ext_ids = [a.gloss for a in ext_assignments]
        known_exts = [e for e in ext_ids if e in self._ext_ids]

        # EXT_MAX_EXCEEDED
        n = len(ext_ids)
        if n > self._max_extensions:
            violations.append(
                ValidationViolation(
                    rule_id="EXT_MAX_EXCEEDED",
                    severity="ERROR",
                    slot_id="SLOT9",
                    morpheme_form="+".join(ext_ids),
                    message=(
                        f"{n} extensions found; grammar maximum is "
                        f"{self._max_extensions}. The sequence is ill-formed."
                    ),
                )
            )
        elif n > self._typical_max:
            violations.append(
                ValidationViolation(
                    rule_id="EXT_TYPICAL_MAX_EXCEEDED",
                    severity="WARNING",
                    slot_id="SLOT9",
                    morpheme_form="+".join(ext_ids),
                    message=(
                        f"{n} extensions found; typical maximum is "
                        f"{self._typical_max}. This is grammatically possible "
                        f"but rare in natural speech."
                    ),
                )
            )

        # Collect zones in sequence order
        zones_in_order = [
            self._ext_zone.get(e) for e in ext_ids if e in self._ext_zone
        ]

        # EXT_ZONE_ORDER — zones must be non-decreasing
        last_zone_ord = 0
        last_ext_id   = ""
        for ext_id, zone in zip(ext_ids, zones_in_order):
            if zone is None:
                continue
            zone_ord = _ZONE_ORDER.get(zone, 0)
            if zone_ord < last_zone_ord:
                violations.append(
                    ValidationViolation(
                        rule_id="EXT_ZONE_ORDER",
                        severity="ERROR",
                        slot_id="SLOT9",
                        morpheme_form=ext_id,
                        message=(
                            f"Extension {ext_id!r} (zone {zone}) appears after "
                            f"{last_ext_id!r} (zone {self._ext_zone.get(last_ext_id)}) "
                            f"but zone ordering requires Z1 < Z2 < Z3 < Z4."
                        ),
                    )
                )
            last_zone_ord = zone_ord
            last_ext_id   = ext_id

        # EXT_INTRA_ZONE_ORDER — within each zone, internal order must be respected
        zone_groups: Dict[str, List[str]] = {}
        for ext_id in ext_ids:
            z = self._ext_zone.get(ext_id)
            if z:
                zone_groups.setdefault(z, []).append(ext_id)

        for zone_id, exts_in_zone in zone_groups.items():
            canonical = self._zone_internal_order.get(zone_id, [])
            if not canonical or len(exts_in_zone) < 2:
                continue
            # Build expected positions
            canon_pos = {ext: i for i, ext in enumerate(canonical)}
            seq = [canon_pos.get(e, -1) for e in exts_in_zone if canon_pos.get(e, -1) >= 0]
            for i in range(1, len(seq)):
                if seq[i] < seq[i - 1]:
                    bad = exts_in_zone[i]
                    prev = exts_in_zone[i - 1]
                    violations.append(
                        ValidationViolation(
                            rule_id="EXT_INTRA_ZONE_ORDER",
                            severity="ERROR",
                            slot_id="SLOT9",
                            morpheme_form=bad,
                            message=(
                                f"Extension {bad!r} appears after {prev!r} within {zone_id}, "
                                f"but canonical intra-zone order is "
                                f"{' < '.join(e for e in canonical if e in zone_groups[zone_id])}."
                            ),
                        )
                    )
                    break

        # EXT_INCOMPATIBLE — pairwise incompatibility check
        ext_id_set = frozenset(ext_ids)
        seen_pairs: Set[FrozenSet] = set()
        for ext_id in ext_id_set:
            incompat = self._ext_incompatible.get(ext_id, frozenset())
            for other in incompat:
                pair = frozenset({ext_id, other})
                if other in ext_id_set and pair not in seen_pairs:
                    seen_pairs.add(pair)
                    violations.append(
                        ValidationViolation(
                            rule_id="EXT_INCOMPATIBLE",
                            severity="ERROR",
                            slot_id="SLOT9",
                            morpheme_form=f"{ext_id}+{other}",
                            message=(
                                f"Extensions {ext_id!r} and {other!r} are grammatically "
                                f"incompatible and cannot co-occur in the same verb form."
                            ),
                        )
                    )

        # EXT_PASS_NOT_FINAL — PASS must be the last extension
        if self._pass_must_be_final and "PASS" in ext_ids:
            if ext_ids[-1] != "PASS":
                idx = ext_ids.index("PASS")
                violations.append(
                    ValidationViolation(
                        rule_id="EXT_PASS_NOT_FINAL",
                        severity="ERROR",
                        slot_id="SLOT9",
                        morpheme_form="PASS",
                        message=(
                            f"PASS (passive) must be the final extension but appears "
                            f"at position {idx + 1} of {len(ext_ids)} "
                            f"(followed by {ext_ids[idx + 1:]!r})."
                        ),
                    )
                )

        return violations

    # ------------------------------------------------------------------
    # Layer 4: co-occurrence / agreement constraints
    # ------------------------------------------------------------------

    def _check_cooccurrence_constraints(
        self, assignments: List[SlotAssignment]
    ) -> List[ValidationViolation]:
        violations: List[ValidationViolation] = []
        content_types = {a.content_type for a in assignments}
        ext_ids_present = frozenset(
            a.gloss for a in assignments if a.content_type == "verb_extension"
        )

        # NEG_PRE_INFIX_EXCLUSIVE
        has_neg_pre   = any(a.content_type == "negation_pre"   for a in assignments)
        has_neg_infix = any(a.content_type == "negation_infix" for a in assignments)
        if has_neg_pre and has_neg_infix:
            violations.append(
                ValidationViolation(
                    rule_id="NEG_PRE_INFIX_EXCLUSIVE",
                    severity="WARNING",
                    slot_id=None,
                    morpheme_form=None,
                    message=(
                        "Both SLOT1 (negation_pre) and SLOT4 (negation_infix) are "
                        "filled. The grammar documents pre-initial and infix negation "
                        "as mutually exclusive in most constructions."
                    ),
                )
            )

        # RECIP_REQUIRES_PLURAL
        if "RECIP" in ext_ids_present:
            sc_gloss: Optional[str] = None
            for a in assignments:
                if a.content_type == "subject_concord":
                    sc_gloss = a.gloss
                    break

            if sc_gloss is not None:
                sc_key = _extract_sc_key(sc_gloss)
                is_plural = _key_is_plural(sc_key, self._plural_nc_ids)
                if is_plural is False:  # definitively singular
                    violations.append(
                        ValidationViolation(
                            rule_id="RECIP_REQUIRES_PLURAL",
                            severity="WARNING",
                            slot_id="SLOT9",
                            morpheme_form="RECIP",
                            message=(
                                f"RECIP (reciprocal) extension requires a plural subject, "
                                f"but subject concord key {sc_key!r} appears to be singular. "
                                f"Reciprocal actions require multiple participants."
                            ),
                        )
                    )

        return violations

    # ------------------------------------------------------------------
    # Standalone extension-ordering check (public convenience)
    # ------------------------------------------------------------------

    def check_extension_ordering(
        self, ext_ids: List[str]
    ) -> ValidationResult:
        """
        Validate an ordered list of extension ids against zone and
        intra-zone ordering constraints, without a full morpheme sequence.

        Parameters
        ----------
        ext_ids : List[str]
            Ordered list of ``VerbExtension.id`` values as they appear in
            the verb form, e.g. ``["APPL", "PASS"]``.

        Returns
        -------
        ValidationResult
            ``morpheme_sequence`` contains one ``SlotAssignment`` per
            extension id.

        Examples
        --------
        >>> validator.check_extension_ordering(["APPL", "PASS"]).is_valid
        True
        >>> validator.check_extension_ordering(["PASS", "APPL"]).is_valid
        False
        """
        assignments = [
            SlotAssignment(
                slot_id="SLOT9",
                content_type="verb_extension",
                form=ext_id,
                gloss=ext_id,
                nc_id=None,
            )
            for ext_id in ext_ids
        ]
        ext_violations = self._check_extension_constraints(assignments)
        ref_violations = self._check_reference_validity(assignments)
        all_v = ref_violations + ext_violations

        errors   = tuple(v for v in all_v if v.severity == "ERROR")
        warnings = tuple(v for v in all_v if v.severity == "WARNING")
        coverage = {"SLOT9": len(ext_ids)} if ext_ids else {}

        return ValidationResult(
            is_valid=len(errors) == 0,
            morpheme_sequence=tuple(assignments),
            violations=tuple(all_v),
            errors=errors,
            warnings=warnings,
            slot_coverage=coverage,
            error_count=len(errors),
            warning_count=len(warnings),
        )

    # ------------------------------------------------------------------
    # Grammar introspection helpers (all via public API indexes)
    # ------------------------------------------------------------------

    def obligatory_slots(self) -> List[str]:
        """
        Return the ids of all obligatory slots, sorted by position.

        Returns
        -------
        List[str]
        """
        return sorted(
            self._obligatory_ids,
            key=lambda s: self._slot_position.get(s, 999),
        )

    def allowed_content_types(self, slot_id: str) -> FrozenSet[str]:
        """
        Return the set of allowed content types for a slot id.

        Parameters
        ----------
        slot_id : str

        Returns
        -------
        FrozenSet[str]
            Empty if the slot id is not in the grammar.
        """
        return self._allowed_types.get(slot_id, frozenset())

    def known_extension_ids(self) -> FrozenSet[str]:
        """Return all known verb-extension ids from the grammar."""
        return self._ext_ids

    def extension_zone(self, ext_id: str) -> Optional[str]:
        """
        Return the zone label for a given extension id, or ``None`` if unknown.

        Parameters
        ----------
        ext_id : str

        Returns
        -------
        Optional[str]
        """
        return self._ext_zone.get(ext_id)

    @property
    def language(self) -> str:
        """The language identifier from the grammar loader."""
        return self._language

    @property
    def max_extensions(self) -> int:
        """Maximum number of extensions allowed per verb form."""
        return self._max_extensions

    @property
    def typical_max_extensions(self) -> int:
        """Typical maximum extensions (above this triggers a WARNING)."""
        return self._typical_max
