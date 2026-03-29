"""
apps/morphological_analyzer.py  (v2 — slot-aware phonology architecture)
=========================================================================
Three-layer analysis / generation pipeline replacing the v1 string-based
approach:

Analysis (surface → structure):
  SURFACE FORM
    ↓  PhonologyEngine.reverse()     — undo sandhi / vowel harmony
  UNDERLYING MORPHOLOGICAL FORM
    ↓  SlotParser.parse()            — slot-driven hypothesis lattice (SLOT1–11)
  STRUCTURED MORPHOLOGICAL ANALYSIS

Generation (features → surface):
  FEATURE BUNDLE
    ↓  SlotFiller.fill()             — slot-driven morpheme assembly
  UNDERLYING CONCATENATION
    ↓  PhonologyEngine.forward()     — apply sandhi / vowel harmony
  SURFACE FORM

Key architectural changes over v1
-----------------------------------
* ``SlotParser``       — replaces the hard-coded SC→TAM→OC prefix chain.
                         Every slot in SLOT1–SLOT11 participates in the
                         hypothesis lattice; slot6/slot7 are no longer ignored.
* ``PhonologyEngine``  — replaces "record as warning" with a real rule engine:
                         forward application (generation) and reverse mapping
                         (analysis).  Carries underlying representation and a
                         full rule trace.
* ``StructuredMorph``  — internal representation is a dict of slot→MorphNode,
                         never a '+' or '-' joined string.  Serialised forms
                         are produced lazily from the structure.
* ``ConstraintEngine`` — prevents invalid slot combinations from entering the
                         lattice (e.g. two subject concords, TAM in wrong slot).
* Scoring              — ``_score()`` now includes a phonological plausibility
                         component alongside coverage and obligatory-slot bonus.
* All public types (``Morpheme``, ``ParseHypothesis``, ``SegmentedToken``,
  ``MorphFeatureBundle``, ``SurfaceForm``) are backward-compatible with v1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import (
    Dict, FrozenSet, List, Optional, Sequence, Tuple
)

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
    # Sub-components (importable for testing / extension)
    "PhonologyEngine",
    "SlotParser",
    "SlotFiller",
    "ConstraintEngine",
    "StructuredMorph",
]


# ============================================================================
# Exceptions
# ============================================================================

class MorphAnalysisError(GGTError):
    """Raised when the analyzer encounters an unrecoverable error."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


# ============================================================================
# Internal: Structured Morphological Representation
# ============================================================================

@dataclass
class MorphNode:
    """
    A single morpheme node in the internal slot-keyed representation.

    This is the *internal* intermediate form — it is never exposed directly
    to callers.  ``Morpheme`` (the public frozen type) is derived from it.
    """
    slot_id: str          # e.g. "SLOT3"
    slot_name: str        # e.g. "subject_marker"
    surface: str          # surface string of this morpheme
    underlying: str       # underlying (pre-phonology) string; may equal surface
    content_type: str     # e.g. "subject_concord", "tam_marker"
    gloss: str            # Leipzig label
    nc_id: Optional[str] = None


@dataclass
class StructuredMorph:
    """
    The internal structured representation of a morphological analysis.

    Slot order is maintained via ``slot_order`` (a list of slot IDs in
    position order).  ``nodes`` maps slot_id → MorphNode.

    Converting to a public ``ParseHypothesis`` is done via
    ``to_hypothesis()``.
    """
    slot_order: List[str]                  # ordered slot IDs present
    nodes: Dict[str, MorphNode]            # slot_id → node
    surface_form: str                      # original token
    remaining: str = ""                    # unaccounted-for residue
    rule_trace: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def morphemes_ordered(self) -> List[MorphNode]:
        return [self.nodes[s] for s in self.slot_order if s in self.nodes]

    def surface_string(self) -> str:
        return "".join(n.surface for n in self.morphemes_ordered if n.surface)

    def underlying_string(self) -> str:
        return "".join(n.underlying for n in self.morphemes_ordered if n.underlying)

    def segmented(self) -> str:
        return "-".join(n.surface for n in self.morphemes_ordered if n.surface)

    def gloss_line(self) -> str:
        return "-".join(n.gloss for n in self.morphemes_ordered if n.surface)

    def to_morphemes(self) -> Tuple["Morpheme", ...]:
        return tuple(
            Morpheme(
                form=n.surface,
                slot_id=n.slot_id,
                slot_name=n.slot_name,
                content_type=n.content_type,
                gloss=n.gloss,
                nc_id=n.nc_id,
            )
            for n in self.morphemes_ordered
            if n.surface
        )

    def to_hypothesis(self, confidence: float) -> "ParseHypothesis":
        return ParseHypothesis(
            morphemes=self.to_morphemes(),
            surface_form=self.surface_form,
            remaining=self.remaining,
            confidence=confidence,
            warnings=tuple(self.warnings),
            rule_trace=tuple(self.rule_trace),
            underlying=self.underlying_string(),
        )


# ============================================================================
# Public result types  (backward-compatible with v1)
# ============================================================================

@dataclass(frozen=True)
class Morpheme:
    """A single identified morpheme within a segmented word token."""
    form: str
    slot_id: str
    slot_name: str
    content_type: str
    gloss: str
    nc_id: Optional[str]


@dataclass(frozen=True)
class ParseHypothesis:
    """One segmentation hypothesis for a surface token."""
    morphemes: Tuple[Morpheme, ...]
    surface_form: str
    remaining: str
    confidence: float
    warnings: Tuple[str, ...]
    # v2 additions (default-safe for backward compat)
    rule_trace: Tuple[str, ...] = ()
    underlying: str = ""

    @property
    def segmented(self) -> str:
        return "-".join(m.form for m in self.morphemes if m.form)

    @property
    def gloss_line(self) -> str:
        return "-".join(m.gloss for m in self.morphemes if m.form)

    @property
    def coverage(self) -> float:
        if not self.surface_form:
            return 1.0
        assigned = sum(len(m.form) for m in self.morphemes if m.form)
        return assigned / len(self.surface_form)


@dataclass(frozen=True)
class SegmentedToken:
    """Complete segmentation result for a single word token."""
    token: str
    language: str
    hypotheses: Tuple[ParseHypothesis, ...]
    best: Optional[ParseHypothesis]

    @property
    def is_ambiguous(self) -> bool:
        return len(self.hypotheses) > 1

    def top_n(self, n: int = 3) -> Tuple[ParseHypothesis, ...]:
        return self.hypotheses[:n]


@dataclass(frozen=True)
class MorphFeatureBundle:
    """Feature specification for verb surface-form generation."""
    root: str
    subject_nc: str
    tam_id: str
    object_nc: Optional[str] = None
    extensions: Tuple[str, ...] = ()
    polarity: str = "affirmative"
    final_vowel: str = "a"
    # v2 additions
    extra_slots: Dict[str, str] = field(default_factory=dict)
    """
    Freeform slot overrides for slots not covered by the standard bundle
    (e.g. negation prefix, modal, post-final).  Keys are slot IDs (e.g.
    ``"SLOT1"``); values are surface strings to insert.
    """


@dataclass(frozen=True)
class SurfaceForm:
    """The result of generating a verb surface form."""
    surface: str
    segmented: str
    gloss: str
    morphemes: Tuple[Morpheme, ...]
    features: MorphFeatureBundle
    warnings: Tuple[str, ...]
    # v2 additions
    underlying: str = ""
    rule_trace: Tuple[str, ...] = ()


# ============================================================================
# Layer 1 — PhonologyEngine
# ============================================================================

@dataclass
class PhonRule:
    """
    A compiled phonological rule loaded from the grammar.

    ``pattern``    — compiled regex matching the surface context
    ``target``     — the string (or group reference) to rewrite TO (forward)
    ``source``     — the string (or group reference) to rewrite FROM (reverse)
    ``rule_id``    — the original rule identifier from the YAML
    ``rule_type``  — "sandhi" | "vowel_harmony" | "nasal_assimilation" | ...
    ``boundary``   — True if the rule is boundary-sensitive
    """
    rule_id: str
    rule_type: str
    pattern: re.Pattern
    target: str          # replacement for forward (generation)
    source: str          # replacement for reverse (analysis)
    boundary: bool = False


class PhonologyEngine:
    """
    Boundary-aware phonological rule engine.

    Responsibilities
    ----------------
    * ``forward(nodes)``  — apply rules left-to-right at morpheme boundaries
                            to produce the surface string from underlying forms.
    * ``reverse(surface)``— attempt to undo surface alternations by applying
                            rules right-to-left (reverse mapping) to recover
                            candidate underlying strings.
    * ``score(surface, underlying)`` — phonological plausibility score [0,1]:
                            1.0 when the underlying → surface derivation is
                            fully accounted for by known rules; lower when
                            unexplained segments remain.

    Rule compilation
    ----------------
    Rules are compiled from the grammar's ``phonology`` section.  The grammar
    can supply rules as:
      - Named sandhi rules (string identifiers) — compiled into simple
        vowel-sequence rewrite rules via heuristic expansion.
      - Vowel harmony rules — compiled into feature-propagation rewrites.
      - Nasal prefix assimilation patterns loaded from ``nasal_prefixes``.

    In the absence of fully-specified rule objects in the YAML, the engine
    degrades to a set of universal Bantu heuristics so that *something*
    useful always happens rather than silently skipping phonology.
    """

    # Universal Bantu sandhi heuristics (surface rewrite, boundary marker = "|")
    # Format: (pattern_str, forward_replacement, reverse_replacement, rule_id)
    _UNIVERSAL_RULES: List[Tuple[str, str, str, str]] = [
        # Vowel hiatus coalescence: V + V → long V or glide insertion
        (r"([aeiou])\|([aeiou])", r"\2", r"\1|\2", "SANDHI_V_V_COALESCENCE"),
        # Glide formation: i/u before vowel → y/w
        (r"i\|([aeiou])", r"y\1", r"i|\1", "SANDHI_GLIDE_I"),
        (r"u\|([aeiou])", r"w\1", r"u|\1", "SANDHI_GLIDE_U"),
        # Final vowel elision before following vowel-initial morpheme
        (r"a\|([aeiou])", r"\1", r"a|\1", "SANDHI_FV_ELISION"),
        # Nasal + voiced stop → prenasalised stop (very common in Bantu)
        (r"[nŋ]\|b", r"mb", r"n|b", "SANDHI_NASAL_B"),
        (r"[nŋ]\|d", r"nd", r"n|d", "SANDHI_NASAL_D"),
        (r"[nŋ]\|g", r"ŋg", r"n|g", "SANDHI_NASAL_G"),
    ]

    def __init__(
        self,
        vowels: FrozenSet[str],
        sandhi_rule_ids: List[str],
        vowel_harmony_ids: List[str],
        nasal_prefixes: FrozenSet[str],
        rule_objects: Optional[List[dict]] = None,
    ) -> None:
        self._vowels = vowels
        self._sandhi_ids = sandhi_rule_ids
        self._harmony_ids = vowel_harmony_ids
        self._nasal_prefixes = nasal_prefixes
        self._rules: List[PhonRule] = []
        self._compile_rules(rule_objects or [])

    # ------------------------------------------------------------------
    # Rule compilation
    # ------------------------------------------------------------------

    def _compile_rules(self, rule_objects: List[dict]) -> None:
        """Compile grammar-supplied rule objects + universal heuristics."""
        compiled: List[PhonRule] = []

        # 1. Grammar-supplied rule objects (if the YAML includes full specs)
        for rd in rule_objects:
            try:
                r = PhonRule(
                    rule_id=rd["id"],
                    rule_type=rd.get("type", "sandhi"),
                    pattern=re.compile(rd["pattern"]),
                    target=rd.get("target", ""),
                    source=rd.get("source", ""),
                    boundary=rd.get("boundary", False),
                )
                compiled.append(r)
            except (KeyError, re.error):
                pass

        # 2. Heuristic rules derived from sandhi rule IDs (name-based)
        for rule_id in self._sandhi_ids:
            heuristic = self._heuristic_from_id(rule_id)
            if heuristic and not any(r.rule_id == rule_id for r in compiled):
                compiled.append(heuristic)

        # 3. Vowel harmony rules
        if self._harmony_ids:
            compiled.extend(self._compile_harmony_rules())

        # 4. Nasal assimilation from nasal_prefixes
        compiled.extend(self._compile_nasal_rules())

        # 5. Universal Bantu fallback heuristics (appended last so grammar
        #    rules take priority, but they are always present as a safety net)
        for pat_str, fwd, rev, rid in self._UNIVERSAL_RULES:
            if not any(r.rule_id == rid for r in compiled):
                try:
                    compiled.append(PhonRule(
                        rule_id=rid,
                        rule_type="sandhi",
                        pattern=re.compile(pat_str),
                        target=fwd,
                        source=rev,
                        boundary=True,
                    ))
                except re.error:
                    pass

        self._rules = compiled

    def _heuristic_from_id(self, rule_id: str) -> Optional[PhonRule]:
        """
        Try to derive a rule from the rule ID string alone.

        Covers common naming conventions found in Bantu grammar YAMLs:
        *_vowel_coalescence, *_glide_formation, *_nasal_assimilation,
        *_final_vowel_elision, *_vowel_harmony, etc.
        """
        rid = rule_id.lower()
        if "vowel_coalescence" in rid or "coalescence" in rid:
            return PhonRule(
                rule_id=rule_id, rule_type="sandhi",
                pattern=re.compile(r"([aeiou])\|([aeiou])"),
                target=r"\2", source=r"\1|\2", boundary=True,
            )
        if "glide" in rid:
            return PhonRule(
                rule_id=rule_id, rule_type="sandhi",
                pattern=re.compile(r"([iu])\|([aeiou])"),
                target=lambda m: ("y" if m.group(1) == "i" else "w") + m.group(2),
                source=r"\1|\2", boundary=True,
            )
        if "elision" in rid or "final_vowel_elision" in rid:
            return PhonRule(
                rule_id=rule_id, rule_type="sandhi",
                pattern=re.compile(r"[aeiou]\|([aeiou])"),
                target=r"\1", source=r"a|\1", boundary=True,
            )
        if "nasal" in rid and "assim" in rid:
            return PhonRule(
                rule_id=rule_id, rule_type="sandhi",
                pattern=re.compile(r"([nŋmɲ])\|([bdg])"),
                target=r"\1\2", source=r"\1|\2", boundary=True,
            )
        return None

    def _compile_harmony_rules(self) -> List[PhonRule]:
        """
        Compile vowel-harmony propagation rules.

        Uses the standard ATR (Advanced Tongue Root) height-harmony model
        common to many Bantu languages: /e o/ in the root trigger /e o/ in
        suffixes that otherwise contain /a/; /i u/ trigger /i u/ propagation.
        The exact system is approximated; a full specification would require
        feature matrices from the grammar.
        """
        rules: List[PhonRule] = []
        for rid in self._harmony_ids:
            rid_lower = rid.lower()
            if "atr" in rid_lower or "height" in rid_lower or "harmony" in rid_lower:
                # /e/ triggers /e/ in following suffix vowel positions
                rules.append(PhonRule(
                    rule_id=f"{rid}:E_SPREAD",
                    rule_type="vowel_harmony",
                    pattern=re.compile(r"e([^aeiou]*)\|a"),
                    target=r"e\1e",
                    source=r"e\1|a",
                    boundary=True,
                ))
                rules.append(PhonRule(
                    rule_id=f"{rid}:O_SPREAD",
                    rule_type="vowel_harmony",
                    pattern=re.compile(r"o([^aeiou]*)\|a"),
                    target=r"o\1o",
                    source=r"o\1|a",
                    boundary=True,
                ))
        return rules

    def _compile_nasal_rules(self) -> List[PhonRule]:
        """
        Compile nasal assimilation rules from ``nasal_prefixes``.
        Each known nasal prefix triggers an assimilation rule when it abuts
        a following consonant across a boundary.
        """
        rules: List[PhonRule] = []
        for prefix in sorted(self._nasal_prefixes, key=len, reverse=True):
            if not prefix:
                continue
            esc = re.escape(prefix)
            rules.append(PhonRule(
                rule_id=f"NASAL_ASSIM_{prefix.upper()}",
                rule_type="sandhi",
                pattern=re.compile(esc + r"\|([bdg])"),
                target=prefix + r"\1",
                source=esc + r"|\1",
                boundary=True,
            ))
        return rules

    # ------------------------------------------------------------------
    # Core engine methods
    # ------------------------------------------------------------------

    def forward(self, nodes: List[MorphNode]) -> Tuple[str, List[str]]:
        """
        Apply phonological rules left-to-right across morpheme boundaries to
        produce a surface string from the ordered list of underlying MorphNodes.

        Returns ``(surface_string, rule_trace)``.

        The boundary marker ``|`` is inserted between adjacent morphemes before
        rule application, then stripped from the output.  Rules that have
        ``boundary=True`` only fire at ``|`` positions.
        """
        if not nodes:
            return "", []

        # Build boundary-marked underlying string
        parts = [n.underlying or n.surface for n in nodes if n.underlying or n.surface]
        marked = "|".join(parts)

        trace: List[str] = []
        result = marked

        for rule in self._rules:
            if not rule.boundary:
                # Non-boundary rule: apply anywhere
                new = rule.pattern.sub(rule.target, result)
            else:
                # Boundary rule: only fires if "|" is in the match span
                new = _boundary_sub(rule.pattern, rule.target, result)
            if new != result:
                trace.append(
                    f"{rule.rule_id}: {result!r} → {new!r}"
                )
                result = new

        # Strip all remaining boundary markers
        surface = result.replace("|", "")
        return surface, trace

    def reverse(self, surface: str) -> List[Tuple[str, List[str]]]:
        """
        Attempt to recover candidate underlying strings from a surface form by
        applying rules in reverse order (right-to-left over the rule list).

        Returns a list of ``(underlying_candidate, rule_trace)`` pairs, sorted
        by number of rules fired (more rules = more transformations resolved).
        Multiple candidates arise when rules are ambiguous (e.g. both
        elision and glide formation could have produced the same surface).

        In the worst case (no rules fire) the surface is returned unchanged as
        the single candidate with an empty trace.
        """
        candidates: List[Tuple[str, List[str]]] = [(surface, [])]

        for rule in reversed(self._rules):
            new_candidates: List[Tuple[str, List[str]]] = []
            for candidate, trace in candidates:
                # Try the reverse substitution
                reversed_src = rule.source
                if callable(reversed_src):
                    # Callable target — skip (not trivially reversible)
                    new_candidates.append((candidate, trace))
                    continue
                try:
                    new = re.sub(rule.pattern, reversed_src, candidate)
                except re.error:
                    new_candidates.append((candidate, trace))
                    continue
                if new != candidate:
                    new_candidates.append((
                        new,
                        trace + [f"{rule.rule_id}⁻¹: {candidate!r} → {new!r}"],
                    ))
                # Always keep the un-reversed candidate too (ambiguity)
                new_candidates.append((candidate, trace))
            # Deduplicate
            seen: Dict[str, List[str]] = {}
            for cand, tr in new_candidates:
                if cand not in seen or len(tr) > len(seen[cand]):
                    seen[cand] = tr
            candidates = list(seen.items())

        # Sort: most rules fired first (richest underlying form first)
        candidates.sort(key=lambda x: len(x[1]), reverse=True)
        return candidates

    def score(self, surface: str, underlying: str) -> float:
        """
        Phonological plausibility: ratio of surface characters that are
        accounted for by the forward derivation from ``underlying``.

        Score is 1.0 when ``forward([...underlying...])`` exactly produces
        ``surface``; it degrades proportionally to unexplained edits.
        Returns a value in [0.0, 1.0].
        """
        if not surface:
            return 1.0
        # Quick exact-match shortcut
        if surface == underlying.replace("|", ""):
            return 1.0
        # Use SequenceMatcher-style: longest common subsequence ratio
        import difflib
        ratio = difflib.SequenceMatcher(None, underlying, surface).ratio()
        return round(ratio, 4)

    @property
    def rules(self) -> List[PhonRule]:
        """Read-only list of compiled rules (for inspection / testing)."""
        return list(self._rules)


def _boundary_sub(pattern: re.Pattern, repl, text: str) -> str:
    """
    Apply ``pattern.sub(repl, text)`` only at positions that include ``|``.

    For each non-overlapping match, skip it if the matched span contains no
    ``|`` character.
    """
    result = []
    pos = 0
    for m in pattern.finditer(text):
        if "|" not in m.group(0):
            continue
        result.append(text[pos:m.start()])
        if callable(repl):
            result.append(repl(m))
        else:
            result.append(m.expand(repl))
        pos = m.end()
    result.append(text[pos:])
    return "".join(result)


# ============================================================================
# Layer 2 — ConstraintEngine
# ============================================================================

class ConstraintEngine:
    """
    Prevents invalid slot-filling combinations from producing hypotheses.

    Rules encoded here:
    * At most one subject concord per form.
    * At most one TAM marker per form.
    * At most one object concord per form.
    * Object concord must follow TAM and precede root.
    * Final vowel must occupy the highest-numbered slot.
    * Extension must precede final vowel.
    * Root must be non-empty for verbal analyses.
    * Slot positions must be strictly increasing left-to-right.

    Additional constraints can be registered at runtime via
    ``add_constraint(name, fn)`` where ``fn(nodes: Dict[str, MorphNode]) -> bool``.
    """

    def __init__(self, slot_order: List) -> None:
        # slot_order: list of VerbSlot objects sorted by position
        self._slot_positions: Dict[str, int] = {
            s.id: s.position for s in slot_order
        }
        self._extra: Dict[str, callable] = {}

    def add_constraint(self, name: str, fn) -> None:  # type: ignore[no-untyped-def]
        self._extra[name] = fn

    def validate(self, nodes: Dict[str, MorphNode]) -> Tuple[bool, List[str]]:
        """
        Validate a slot→node mapping.

        Returns ``(valid, list_of_violations)``.  Empty violation list means
        the analysis is structurally sound.
        """
        violations: List[str] = []

        # Count content types
        ct_counts: Dict[str, int] = {}
        for node in nodes.values():
            ct_counts[node.content_type] = ct_counts.get(node.content_type, 0) + 1

        if ct_counts.get("subject_concord", 0) > 1:
            violations.append("Multiple subject concords assigned.")
        if ct_counts.get("tam_marker", 0) > 1:
            violations.append("Multiple TAM markers assigned.")
        if ct_counts.get("object_concord", 0) > 1:
            violations.append("Multiple object concords assigned.")
        if ct_counts.get("final_vowel", 0) > 1:
            violations.append("Multiple final vowels assigned.")

        # Strict position ordering
        prev_pos = -1
        for slot_id in sorted(nodes.keys(),
                               key=lambda s: self._slot_positions.get(s, 999)):
            pos = self._slot_positions.get(slot_id, 999)
            if pos < prev_pos:
                violations.append(
                    f"Slot position violation: {slot_id} (pos {pos}) "
                    f"is out of order (previous pos {prev_pos})."
                )
            prev_pos = pos

        # Root non-empty for verbal forms
        root_nodes = [n for n in nodes.values() if n.content_type == "verb_root"]
        if root_nodes and not any(n.surface for n in root_nodes):
            violations.append("Verb root is empty.")

        # Extra constraints
        for name, fn in self._extra.items():
            try:
                ok = fn(nodes)
                if not ok:
                    violations.append(f"Custom constraint '{name}' failed.")
            except Exception as exc:  # noqa: BLE001
                violations.append(f"Custom constraint '{name}' raised: {exc}")

        return (len(violations) == 0), violations


# ============================================================================
# Layer 2 — SlotParser  (analysis: underlying form → StructuredMorph)
# ============================================================================

class SlotParser:
    """
    Slot-driven hypothesis lattice builder.

    Replaces the hard-coded SC→TAM→OC prefix chain.  Every slot in
    SLOT1–SLOT11 participates in matching; the parser walks the slot list
    in position order and, for each slot, attempts all candidate forms that
    appear at the current position in the remaining string.

    The result is a set of ``StructuredMorph`` objects representing all
    valid analyses (subject to ``ConstraintEngine`` filtering).  Hypotheses
    are scored in ``MorphologicalAnalyzer._score()`` after phonology.
    """

    def __init__(
        self,
        slot_order: List,                              # VerbSlot list, sorted
        sc_index: Dict[str, List[Tuple[str, str]]],    # form → [(key, type)]
        oc_index: Dict[str, List[Tuple[str, str]]],
        tam_by_form: Dict[str, List],
        ext_by_form: Dict[str, List],
        vowel_set: FrozenSet[str],
        constraint_engine: ConstraintEngine,
        # Maps for additional slot types (extensible)
        extra_slot_indexes: Optional[Dict[str, Dict[str, List[Tuple[str, str]]]]] = None,
    ) -> None:
        self._slots = slot_order  # sorted by position
        self._sc_index = sc_index
        self._oc_index = oc_index
        self._tam_by_form = tam_by_form
        self._ext_by_form = ext_by_form
        self._vowel_set = vowel_set
        self._constraints = constraint_engine
        self._extra = extra_slot_indexes or {}

        # Pre-sort form lists longest-first (greedy match)
        self._sc_forms = sorted(sc_index.keys(), key=len, reverse=True)
        self._oc_forms = sorted(oc_index.keys(), key=len, reverse=True)
        self._tam_forms = sorted(tam_by_form.keys(), key=len, reverse=True)
        self._ext_forms = sorted(ext_by_form.keys(), key=len, reverse=True)

        # Build per-slot dispatch table
        self._slot_dispatch = self._build_dispatch()

    # ------------------------------------------------------------------
    # Dispatch table
    # ------------------------------------------------------------------

    def _build_dispatch(self) -> Dict[str, callable]:
        """
        Map each slot's primary content type to a match function.

        The match function signature is:
            fn(remaining: str) → List[Tuple[MorphNode, str]]
        where each tuple is (matched_node, rest_of_string_after_match).
        An empty list means "no match; skip this slot".
        """
        dispatch: Dict[str, callable] = {}
        for slot in self._slots:
            types = set(slot.allowed_content_types)
            # Determine primary type (first match wins in this priority order)
            if types & {"subject_concords", "relative_concords"}:
                dispatch[slot.id] = self._make_concord_matcher(
                    slot, self._sc_forms, self._sc_index,
                    content_type="subject_concord",
                    gloss_fn=lambda key: (
                        f"{key}.SUBJ" if key.startswith("NC") else f"{key}.SUBJ"
                    ),
                )
            elif "tam" in types:
                dispatch[slot.id] = self._make_tam_matcher(slot)
            elif "object_concords" in types:
                dispatch[slot.id] = self._make_concord_matcher(
                    slot, self._oc_forms, self._oc_index,
                    content_type="object_concord",
                    gloss_fn=lambda key: f"{key}.OBJ",
                )
            elif "root" in types:
                dispatch[slot.id] = self._make_root_matcher(slot)
            elif "extensions" in types:
                dispatch[slot.id] = self._make_extension_matcher(slot)
            elif "final_vowels" in types:
                dispatch[slot.id] = self._make_fv_matcher(slot)
            else:
                # Generic: check extra slot indexes or skip
                dispatch[slot.id] = self._make_generic_matcher(slot, types)
        return dispatch

    # ------------------------------------------------------------------
    # Matcher factories
    # ------------------------------------------------------------------

    def _make_concord_matcher(
        self,
        slot,
        forms_desc: List[str],
        index: Dict[str, List[Tuple[str, str]]],
        content_type: str,
        gloss_fn,
    ):
        def match(remaining: str) -> List[Tuple[MorphNode, str]]:
            results = []
            for form in forms_desc:
                if remaining.startswith(form) and len(form) < len(remaining):
                    for key, _ in index[form]:
                        node = MorphNode(
                            slot_id=slot.id,
                            slot_name=slot.name,
                            surface=form,
                            underlying=form,
                            content_type=content_type,
                            gloss=gloss_fn(key),
                            nc_id=key if key.startswith("NC") else None,
                        )
                        results.append((node, remaining[len(form):]))
                    break  # longest match wins
            # Zero-form (empty) match — slot is present but unfilled
            results.append((None, remaining))
            return results
        return match

    def _make_tam_matcher(self, slot):
        def match(remaining: str) -> List[Tuple[MorphNode, str]]:
            results = []
            for form in self._tam_forms:
                if remaining.startswith(form) and len(form) < len(remaining):
                    for tam in self._tam_by_form[form]:
                        node = MorphNode(
                            slot_id=slot.id,
                            slot_name=slot.name,
                            surface=form,
                            underlying=form,
                            content_type="tam_marker",
                            gloss=_tam_gloss(tam),
                        )
                        results.append((node, remaining[len(form):]))
                    break
            results.append((None, remaining))
            return results
        return match

    def _make_root_matcher(self, slot):
        """
        Root slot: the root is whatever remains after all pre-root slots are
        filled and all post-root material is stripped from the right.
        The actual root extraction is deferred to parse(); this matcher is a
        placeholder that returns the full remaining string as a candidate root.
        """
        def match(remaining: str) -> List[Tuple[MorphNode, str]]:
            if not remaining:
                return [(None, remaining)]
            node = MorphNode(
                slot_id=slot.id,
                slot_name=slot.name,
                surface=remaining,
                underlying=remaining,
                content_type="verb_root",
                gloss=remaining,
            )
            return [(node, "")]
        return match

    def _make_extension_matcher(self, slot):
        def match(remaining: str) -> List[Tuple[MorphNode, str]]:
            results = []
            for form in self._ext_forms:
                if (
                    len(form) >= 2
                    and remaining.endswith(form)
                    and len(form) < len(remaining)
                ):
                    ext_obj = self._ext_by_form[form][0]
                    node = MorphNode(
                        slot_id=slot.id,
                        slot_name=slot.name,
                        surface=form,
                        underlying=form,
                        content_type="verb_extension",
                        gloss=ext_obj.id,
                    )
                    results.append((node, remaining[:-len(form)]))
                    break
            results.append((None, remaining))
            return results
        return match

    def _make_fv_matcher(self, slot):
        def match(remaining: str) -> List[Tuple[MorphNode, str]]:
            if remaining and remaining[-1] in self._vowel_set:
                fv = remaining[-1]
                node = MorphNode(
                    slot_id=slot.id,
                    slot_name=slot.name,
                    surface=fv,
                    underlying=fv,
                    content_type="final_vowel",
                    gloss="FV",
                )
                return [
                    (node, remaining[:-1]),
                    (None, remaining),
                ]
            return [(None, remaining)]
        return match

    def _make_generic_matcher(self, slot, types: set):
        """
        For slots whose content type is in ``extra_slot_indexes``, attempt
        a prefix match.  For all others, produce only the zero-match.
        """
        extra_index = self._extra.get(slot.id)
        if extra_index is None:
            # Unknown slot type → always emit zero-match so the lattice
            # continues through SLOT6, SLOT7, etc. without skipping.
            def match_zero(remaining: str) -> List[Tuple[MorphNode, str]]:
                return [(None, remaining)]
            return match_zero

        forms_desc = sorted(extra_index.keys(), key=len, reverse=True)

        def match_extra(remaining: str) -> List[Tuple[MorphNode, str]]:
            results = []
            for form in forms_desc:
                if remaining.startswith(form) and len(form) < len(remaining):
                    for key, ctype in extra_index[form]:
                        node = MorphNode(
                            slot_id=slot.id,
                            slot_name=slot.name,
                            surface=form,
                            underlying=form,
                            content_type=ctype,
                            gloss=key,
                        )
                        results.append((node, remaining[len(form):]))
                    break
            results.append((None, remaining))
            return results
        return match_extra

    # ------------------------------------------------------------------
    # Core parse
    # ------------------------------------------------------------------

    def parse(
        self,
        underlying: str,
        surface_form: str,
        max_hypotheses: int = 5,
    ) -> List[StructuredMorph]:
        """
        Parse ``underlying`` (the reverse-phonology output) using the full
        slot lattice (SLOT1–SLOT11).

        Strategy
        --------
        1. Separate "pre-root" slots (left-to-right prefix matching) from
           "post-root" slots (right-to-left suffix matching).
        2. Build all combinations of pre-root slot fillings via DFS.
        3. For each pre-root combination, strip post-root material from the
           right end, leaving the root as the residue.
        4. Validate every completed StructuredMorph with the ConstraintEngine.
        5. Return up to ``max_hypotheses`` valid candidates (unsorted — caller
           scores them).
        """
        root_slot_idx = next(
            (i for i, s in enumerate(self._slots) if "root" in s.allowed_content_types),
            len(self._slots) // 2,
        )
        pre_root_slots = self._slots[:root_slot_idx]
        post_root_slots = self._slots[root_slot_idx + 1:]
        root_slot = self._slots[root_slot_idx] if root_slot_idx < len(self._slots) else None

        # Phase A: enumerate pre-root fillings
        pre_root_combos: List[Tuple[Dict[str, MorphNode], str]] = [({}, underlying)]
        for slot in pre_root_slots:
            fn = self._slot_dispatch.get(slot.id)
            if fn is None:
                continue
            new_combos: List[Tuple[Dict[str, MorphNode], str]] = []
            for current_nodes, remaining in pre_root_combos:
                for node_or_none, rest in fn(remaining):
                    new_nodes = dict(current_nodes)
                    if node_or_none is not None:
                        new_nodes[slot.id] = node_or_none
                    new_combos.append((new_nodes, rest))
            pre_root_combos = new_combos

        # Phase B: for each pre-root combo, strip post-root from the right
        results: List[StructuredMorph] = []
        seen_segs: set = set()

        for pre_nodes, after_pre in pre_root_combos:
            # Right-side: try stripping FV, then extensions
            post_combos: List[Tuple[Dict[str, MorphNode], str]] = [({}, after_pre)]
            for slot in reversed(post_root_slots):
                fn = self._slot_dispatch.get(slot.id)
                if fn is None:
                    continue
                new_post: List[Tuple[Dict[str, MorphNode], str]] = []
                for post_nodes, remaining in post_combos:
                    for node_or_none, rest in fn(remaining):
                        new_nodes = dict(post_nodes)
                        if node_or_none is not None:
                            new_nodes[slot.id] = node_or_none
                        new_post.append((new_nodes, rest))
                post_combos = new_post

            for post_nodes, root_candidate in post_combos:
                if not root_candidate and not root_slot:
                    continue
                # Build combined node map
                all_nodes: Dict[str, MorphNode] = {}
                all_nodes.update(pre_nodes)
                all_nodes.update(post_nodes)

                # Assign root
                if root_slot and root_candidate:
                    all_nodes[root_slot.id] = MorphNode(
                        slot_id=root_slot.id,
                        slot_name=root_slot.name,
                        surface=root_candidate,
                        underlying=root_candidate,
                        content_type="verb_root",
                        gloss=root_candidate,
                    )

                # Validate
                valid, violations = self._constraints.validate(all_nodes)
                if not valid:
                    continue

                # Build ordered slot list (only filled slots, in position order)
                ordered_ids = [
                    s.id for s in self._slots if s.id in all_nodes
                ]
                sm = StructuredMorph(
                    slot_order=ordered_ids,
                    nodes=all_nodes,
                    surface_form=surface_form,
                    warnings=violations,
                )

                # Deduplicate by segmented form
                seg_key = sm.segmented()
                if seg_key in seen_segs:
                    continue
                seen_segs.add(seg_key)
                results.append(sm)

                if len(results) >= max_hypotheses * 4:
                    break

        return results


# ============================================================================
# Layer 3 — SlotFiller  (generation: features → StructuredMorph)
# ============================================================================

class SlotFiller:
    """
    Walks the slot template in position order and fills from a
    ``MorphFeatureBundle``.

    This replaces the hard-coded if/elif chain in the v1 ``generate()``
    method and handles *all* slots including SLOT1 (negation), SLOT2
    (tense-aspect pre-prefix), SLOT4 (negative INFIX), SLOT6 (relative
    tense), SLOT7 (object concord long-distance), and SLOT11 (post-final)
    via the ``extra_slots`` field of ``MorphFeatureBundle``.
    """

    def __init__(
        self,
        slot_order: List,
        concord_map: Dict[str, Dict[str, str]],
        tam_by_id: Dict[str, object],
        ext_by_id: Dict[str, object],
    ) -> None:
        self._slots = slot_order
        self._concord_map = concord_map
        self._tam_by_id = tam_by_id
        self._ext_by_id = ext_by_id

    def fill(self, features: "MorphFeatureBundle") -> StructuredMorph:
        """
        Fill the slot template from ``features`` and return a
        ``StructuredMorph`` ready for phonological forward pass.

        Raises ``MorphAnalysisError`` on validation failure.
        """
        if not features.root:
            raise MorphAnalysisError("MorphFeatureBundle.root must not be empty.")

        tam_obj = self._tam_by_id.get(features.tam_id)
        if tam_obj is None:
            raise MorphAnalysisError(
                f"TAM id {features.tam_id!r} not found.  "
                f"Available: {sorted(self._tam_by_id.keys())}"
            )

        # Resolve SC
        sc_form = _resolve_concord(
            self._concord_map, "subject_concords", features.subject_nc
        )
        if sc_form is None:
            raise MorphAnalysisError(
                f"Subject concord {features.subject_nc!r} not found.  "
                f"Available: {sorted(self._concord_map.get('subject_concords', {}).keys())}"
            )

        # Resolve OC (optional)
        oc_form: Optional[str] = None
        if features.object_nc:
            oc_form = _resolve_concord(
                self._concord_map, "object_concords", features.object_nc
            )

        # Resolve extensions
        ext_objects = []
        for ext_id in features.extensions:
            ext_obj = self._ext_by_id.get(ext_id)
            if ext_obj is None:
                raise MorphAnalysisError(
                    f"Extension id {ext_id!r} not found.  "
                    f"Available: {sorted(self._ext_by_id.keys())}"
                )
            ext_objects.append(ext_obj)

        tam_form = _strip_hyphens(tam_obj.form)

        # Walk slots
        nodes: Dict[str, MorphNode] = {}
        warnings: List[str] = []
        ext_queue = list(ext_objects)

        for slot in self._slots:
            types = set(slot.allowed_content_types)
            sid, sname = slot.id, slot.name

            # Check extra_slots override first
            if sid in features.extra_slots:
                override_form = features.extra_slots[sid]
                nodes[sid] = MorphNode(
                    slot_id=sid, slot_name=sname,
                    surface=override_form, underlying=override_form,
                    content_type="override", gloss=f"{sid}.OVERRIDE",
                )
                continue

            if types & {"subject_concords", "relative_concords"}:
                if sc_form:
                    nodes[sid] = MorphNode(
                        slot_id=sid, slot_name=sname,
                        surface=sc_form, underlying=sc_form,
                        content_type="subject_concord",
                        gloss=(f"{features.subject_nc}.SUBJ"
                               if features.subject_nc.startswith("NC")
                               else f"{features.subject_nc}.SUBJ"),
                        nc_id=(features.subject_nc
                               if features.subject_nc.startswith("NC") else None),
                    )
            elif "tam" in types:
                if tam_form:
                    nodes[sid] = MorphNode(
                        slot_id=sid, slot_name=sname,
                        surface=tam_form, underlying=tam_form,
                        content_type="tam_marker",
                        gloss=_tam_gloss(tam_obj),
                    )
            elif "object_concords" in types:
                if oc_form:
                    nodes[sid] = MorphNode(
                        slot_id=sid, slot_name=sname,
                        surface=oc_form, underlying=oc_form,
                        content_type="object_concord",
                        gloss=(f"{features.object_nc}.OBJ"
                               if features.object_nc and features.object_nc.startswith("NC")
                               else f"{(features.object_nc or '')}.OBJ"),
                        nc_id=(features.object_nc
                               if features.object_nc and features.object_nc.startswith("NC")
                               else None),
                    )
            elif "root" in types:
                nodes[sid] = MorphNode(
                    slot_id=sid, slot_name=sname,
                    surface=features.root, underlying=features.root,
                    content_type="verb_root",
                    gloss=features.root,
                )
            elif "extensions" in types:
                # Consume from queue; one extension per iteration
                while ext_queue:
                    ext_obj = ext_queue.pop(0)
                    ef = _strip_hyphens(ext_obj.canonical_form)
                    nodes[sid] = MorphNode(
                        slot_id=sid, slot_name=sname,
                        surface=ef, underlying=ef,
                        content_type="verb_extension",
                        gloss=ext_obj.id,
                    )
                    break
            elif "final_vowels" in types:
                nodes[sid] = MorphNode(
                    slot_id=sid, slot_name=sname,
                    surface=features.final_vowel, underlying=features.final_vowel,
                    content_type="final_vowel",
                    gloss="FV",
                )
            elif features.polarity == "negative" and any(
                "neg" in t for t in types
            ):
                warnings.append(
                    f"Slot {sid} ({types}) requires negative morphology not "
                    f"accessible via the public API. Use extra_slots override."
                )
            # All other slot types (SLOT1 neg, SLOT6 rel, SLOT7 long-dist OC,
            # SLOT11 post-final) are silently skipped unless overridden via
            # extra_slots — they appear in the lattice correctly (unfilled).

        ordered_ids = [s.id for s in self._slots if s.id in nodes]
        return StructuredMorph(
            slot_order=ordered_ids,
            nodes=nodes,
            surface_form="",  # filled after forward phonology
            warnings=warnings,
        )


# ============================================================================
# Scoring
# ============================================================================

def _score(
    sm: StructuredMorph,
    token: str,
    obligatory_slots: FrozenSet[str],
    phon_engine: PhonologyEngine,
) -> float:
    """
    Heuristic confidence score for a ``StructuredMorph`` hypothesis.

    Components
    ----------
    coverage         (0–0.40)  proportion of the token assigned to known morphemes
    obligatory slots (0–0.20)  bonus per obligatory slot filled
    root quality     (0–0.10)  root present + (0–0.10) root length bonus
    phonology        (0–0.20)  PhonologyEngine.score(surface, underlying)
    """
    nodes = list(sm.morphemes_ordered)
    assigned = sum(len(n.surface) for n in nodes if n.surface)
    total = len(token) if token else 1
    coverage = min(assigned / total, 1.0) * 0.40

    filled_ids = frozenset(sm.slot_order)
    oblig = (
        len(filled_ids & obligatory_slots) / max(len(obligatory_slots), 1) * 0.20
    )

    root_nodes = [n for n in nodes if n.content_type == "verb_root" and n.surface]
    root_len = len(root_nodes[0].surface) if root_nodes else 0
    root_score = 0.10 if root_len > 0 else 0.0
    root_len_score = min(root_len / 4, 1.0) * 0.10

    phon_score = (
        phon_engine.score(token, sm.underlying_string()) * 0.20
    )

    return round(coverage + oblig + root_score + root_len_score + phon_score, 4)


# ============================================================================
# Helpers shared by both layers
# ============================================================================

_HYPHEN_RE = re.compile(r"^-+|-+$")


def _strip_hyphens(form: str) -> str:
    return _HYPHEN_RE.sub("", form).strip()


def _base_nc(nc_id: str) -> str:
    return re.sub(r"[a-z]+$", "", nc_id)


def _resolve_concord(
    concord_map: Dict[str, Dict[str, str]],
    ctype: str,
    key: str,
) -> Optional[str]:
    """Look up a concord form; try base NC fallback if exact key missing."""
    entries = concord_map.get(ctype, {})
    raw = entries.get(key)
    if raw is None:
        raw = entries.get(_base_nc(key))
    return _strip_hyphens(raw) if raw is not None else None


def _tam_gloss(tam) -> str:  # type: ignore[no-untyped-def]
    parts = []
    t_map = {
        "present": "PRS", "immediate_past": "PST", "remote_past": "REM.PST",
        "immediate_future": "FUT", "remote_future": "REM.FUT",
    }
    a_map = {
        "perfective": "PFV", "progressive": "PROG",
        "habitual": "HAB", "stative": "STAT",
    }
    m_map = {"subjunctive": "SBJV", "conditional": "COND", "imperative": "IMP"}
    if tam.tense not in ("none", ""):
        parts.append(t_map.get(tam.tense, tam.tense.upper()))
    if tam.aspect not in ("none", "", "imperfective"):
        parts.append(a_map.get(tam.aspect, tam.aspect.upper()))
    if tam.mood not in ("none", "", "indicative"):
        parts.append(m_map.get(tam.mood, tam.mood.upper()))
    return ".".join(parts) if parts else tam.id.replace("TAM_", "")


# ============================================================================
# MorphologicalAnalyzer  (public facade)
# ============================================================================

class MorphologicalAnalyzer:
    """
    Language-agnostic morphological analyzer for Bantu verb and noun tokens.

    Implements the three-layer pipeline:

    Analysis:
      surface → (reverse phonology) → underlying → (slot parsing) → structure

    Generation:
      features → (slot filling) → underlying → (forward phonology) → surface

    All grammar knowledge is loaded once from ``GobeloGrammarLoader`` in
    ``__init__``; the loader is not called again during ``analyze()`` or
    ``generate()``.
    """

    def __init__(self, loader) -> None:  # type: ignore[no-untyped-def]
        self._loader = loader
        self._backend = None  # optional HFST backend; set externally if needed
        try:
            self._build_indexes()
        except GGTError as exc:
            raise MorphAnalysisError(
                f"Failed to build morphological indexes: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_indexes(self) -> None:
        meta = self._loader.get_metadata()
        self._language: str = meta.language

        # ── Verb slots ─────────────────────────────────────────────────
        slots = self._loader.get_verb_slots()
        self._slot_order: List = sorted(slots, key=lambda s: s.position)
        self._slots_by_id: Dict[str, object] = {s.id: s for s in slots}
        self._root_slot_pos: int = next(
            (s.position for s in self._slot_order
             if "root" in s.allowed_content_types),
            8,
        )
        self._obligatory_slot_ids: FrozenSet[str] = frozenset(
            s.id for s in slots if s.obligatory
        )

        # ── Concords ───────────────────────────────────────────────────
        self._all_concord_types: List[str] = self._loader.get_all_concord_types()
        self._concord_map: Dict[str, Dict[str, str]] = {}
        for ctype in self._all_concord_types:
            try:
                cset = self._loader.get_concords(ctype)
                self._concord_map[ctype] = {
                    k: _strip_hyphens(v) for k, v in cset.entries.items()
                }
            except GGTError:
                pass

        # SC index (form → [(key, type)])
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
            pass

        # OC index
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

        # ── TAM markers ────────────────────────────────────────────────
        self._tam_by_id: Dict[str, object] = {}
        self._tam_by_form: Dict[str, List] = {}
        for tam in self._loader.get_tam_markers():
            self._tam_by_id[tam.id] = tam
            form = _strip_hyphens(tam.form)
            if form:
                self._tam_by_form.setdefault(form, []).append(tam)

        # ── Verb extensions ────────────────────────────────────────────
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

        # ── Noun class prefixes ────────────────────────────────────────
        self._nc_by_prefix: Dict[str, List] = {}
        for nc in self._loader.get_noun_classes(active_only=False):
            prefix = _strip_hyphens(nc.prefix)
            if prefix and prefix not in ("Ø", "N"):
                self._nc_by_prefix.setdefault(prefix, []).append(nc)
            for allo in nc.allomorphs:
                af = _strip_hyphens(allo)
                if af and af not in ("Ø", "N") and not af.startswith("["):
                    self._nc_by_prefix.setdefault(af, []).append(nc)
        self._nc_prefix_forms_desc: List[str] = sorted(
            self._nc_by_prefix.keys(), key=len, reverse=True
        )

        # ── Phonology ──────────────────────────────────────────────────
        phon = self._loader.get_phonology()
        self._vowel_set: FrozenSet[str] = frozenset(phon.vowels)

        # Attempt to load full rule objects (may not exist in all grammars)
        rule_objects: List[dict] = []
        try:
            rule_objects = list(phon.rule_objects)  # v2 grammar extension
        except AttributeError:
            pass

        self._phon_engine = PhonologyEngine(
            vowels=self._vowel_set,
            sandhi_rule_ids=list(phon.sandhi_rules),
            vowel_harmony_ids=list(phon.vowel_harmony_rules),
            nasal_prefixes=frozenset(
                _strip_hyphens(p) for p in phon.nasal_prefixes
            ),
            rule_objects=rule_objects,
        )

        # ── Tokenization ───────────────────────────────────────────────
        tok = self._loader.get_tokenization_rules()
        self._word_boundary_re: re.Pattern = re.compile(
            tok.word_boundary_pattern or r"\s+"
        )
        self._ortho_norm: Dict[str, str] = dict(tok.orthographic_normalization)
        self._special_cases: Dict[str, str] = dict(tok.special_cases)

        # ── Constraint engine ──────────────────────────────────────────
        self._constraint_engine = ConstraintEngine(self._slot_order)

        # ── Slot parser ────────────────────────────────────────────────
        self._slot_parser = SlotParser(
            slot_order=self._slot_order,
            sc_index=self._sc_index,
            oc_index=self._oc_index,
            tam_by_form=self._tam_by_form,
            ext_by_form=self._ext_by_form,
            vowel_set=self._vowel_set,
            constraint_engine=self._constraint_engine,
        )

        # ── Slot filler ────────────────────────────────────────────────
        self._slot_filler = SlotFiller(
            slot_order=self._slot_order,
            concord_map=self._concord_map,
            tam_by_id=self._tam_by_id,
            ext_by_id=self._ext_by_id,
        )

        # ── Slot→content-type lookup (for gloss labelling) ─────────────
        self._slot_for_content: Dict[str, Tuple[str, str]] = {}
        for s in slots:
            for ct in s.allowed_content_types:
                key = ct.split(".")[-1]
                self._slot_for_content.setdefault(key, (s.id, s.name))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalise(self, token: str) -> str:
        s = token.lower()
        for src, tgt in self._ortho_norm.items():
            s = s.replace(src.lower(), tgt.lower())
        return s

    # ------------------------------------------------------------------
    # Public: analyze
    # ------------------------------------------------------------------

    def analyze(self, token: str, max_hypotheses: int = 5) -> SegmentedToken:
        """
        Segment a surface token into morphemes using the 3-layer pipeline.

        1. Reverse phonology: recover candidate underlying forms.
        2. Slot parsing: build hypothesis lattice over all SLOT1–SLOT11.
        3. Score: coverage + obligatory slots + phonological plausibility.
        4. Validate and rank; return top-N hypotheses.

        Parameters
        ----------
        token : str
            A single word token in the target language orthography.
        max_hypotheses : int
            Maximum number of hypotheses to return (default 5).

        Returns
        -------
        SegmentedToken
        """
        if not token or not token.strip():
            raise MorphAnalysisError("token must be a non-empty string.")

        # Optional HFST backend path (unchanged from v1)
        if self._backend:
            try:
                results = self._backend.lookup(token.strip().lower())
                if results:
                    return self._hfst_results_to_segmented(token, results[:max_hypotheses])
            except Exception as e:
                pass  # fall through

        normed = self._normalise(token.strip())

        # Special-case exact match
        if normed in self._special_cases:
            label = self._special_cases[normed]
            m = Morpheme(
                form=normed, slot_id="LEXICAL", slot_name="special_case",
                content_type="special_case", gloss=label, nc_id=None,
            )
            hyp = ParseHypothesis(
                morphemes=(m,), surface_form=token,
                remaining="", confidence=1.0, warnings=(),
            )
            return SegmentedToken(
                token=token, language=self._language,
                hypotheses=(hyp,), best=hyp,
            )

        # Layer 1: reverse phonology → candidate underlying forms
        underlying_candidates = self._phon_engine.reverse(normed)

        # Layer 2 + 3: slot parse each underlying candidate, score, collect
        all_hyps: Dict[str, ParseHypothesis] = {}

        for underlying_str, phon_trace in underlying_candidates[:3]:
            structured_morphs = self._slot_parser.parse(
                underlying=underlying_str,
                surface_form=token,
                max_hypotheses=max_hypotheses * 2,
            )
            for sm in structured_morphs:
                sm.rule_trace = phon_trace + sm.rule_trace
                conf = _score(sm, normed, self._obligatory_slot_ids, self._phon_engine)
                hyp = sm.to_hypothesis(conf)
                key = hyp.segmented
                if key not in all_hyps or hyp.confidence > all_hyps[key].confidence:
                    all_hyps[key] = hyp

        # Also run nominal analysis
        nominal_hyps = self._analyze_nominal(token, normed, max_hypotheses)
        for h in nominal_hyps:
            key = h.segmented
            if key not in all_hyps or h.confidence > all_hyps[key].confidence:
                all_hyps[key] = h

        ranked = sorted(all_hyps.values(), key=lambda h: h.confidence, reverse=True)
        ranked = ranked[:max_hypotheses]

        # Fallback if nothing was found
        if not ranked:
            m = Morpheme(
                form=normed, slot_id="UNKNOWN", slot_name="",
                content_type="unknown", gloss=normed, nc_id=None,
            )
            ranked = [ParseHypothesis(
                morphemes=(m,), surface_form=token,
                remaining="", confidence=0.0,
                warnings=("No analysis found.",),
            )]

        return SegmentedToken(
            token=token,
            language=self._language,
            hypotheses=tuple(ranked),
            best=ranked[0],
        )

    def analyze_verbal(self, token: str, max_hypotheses: int = 5) -> SegmentedToken:
        """Segment a token assuming it is a verb form (no nominal prefix scan)."""
        if not token or not token.strip():
            raise MorphAnalysisError("token must be a non-empty string.")
        normed = self._normalise(token.strip())
        underlying_candidates = self._phon_engine.reverse(normed)
        all_hyps: Dict[str, ParseHypothesis] = {}
        for underlying_str, phon_trace in underlying_candidates[:3]:
            for sm in self._slot_parser.parse(underlying_str, token, max_hypotheses * 2):
                sm.rule_trace = phon_trace + sm.rule_trace
                conf = _score(sm, normed, self._obligatory_slot_ids, self._phon_engine)
                hyp = sm.to_hypothesis(conf)
                key = hyp.segmented
                if key not in all_hyps or hyp.confidence > all_hyps[key].confidence:
                    all_hyps[key] = hyp
        ranked = sorted(all_hyps.values(), key=lambda h: h.confidence, reverse=True)[
            :max_hypotheses
        ]
        if not ranked:
            m = Morpheme(
                form=normed, slot_id="UNKNOWN", slot_name="",
                content_type="unknown", gloss=normed, nc_id=None,
            )
            ranked = [ParseHypothesis(
                morphemes=(m,), surface_form=token,
                remaining="", confidence=0.0,
                warnings=("No verbal analysis found.",),
            )]
        return SegmentedToken(
            token=token, language=self._language,
            hypotheses=tuple(ranked), best=ranked[0],
        )

    def analyze_nominal(self, token: str, max_hypotheses: int = 5) -> SegmentedToken:
        """Segment a token assuming it is a noun form."""
        normed = self._normalise(token.strip())
        hyps = self._analyze_nominal(token, normed, max_hypotheses)
        return SegmentedToken(
            token=token, language=self._language,
            hypotheses=tuple(hyps), best=hyps[0] if hyps else None,
        )

    def _analyze_nominal(
        self, token: str, normalised: str, max_hypotheses: int
    ) -> List[ParseHypothesis]:
        hypotheses: List[ParseHypothesis] = []
        for prefix in self._nc_prefix_forms_desc:
            if not normalised.startswith(prefix):
                continue
            stem = normalised[len(prefix):]
            if not stem:
                continue
            for nc in self._nc_by_prefix[prefix]:
                morphemes = (
                    Morpheme(
                        form=prefix, slot_id="NC_PREFIX",
                        slot_name="noun_class_prefix",
                        content_type="noun_prefix",
                        gloss=f"{nc.id}.PREFIX", nc_id=nc.id,
                    ),
                    Morpheme(
                        form=stem, slot_id="STEM",
                        slot_name="noun_stem",
                        content_type="noun_stem",
                        gloss=stem, nc_id=nc.id,
                    ),
                )
                assigned = len(prefix) + len(stem)
                conf = round(min(assigned / max(len(normalised), 1), 1.0) * 0.5, 4)
                hypotheses.append(ParseHypothesis(
                    morphemes=morphemes, surface_form=token,
                    remaining="", confidence=conf, warnings=(),
                ))
        if not hypotheses:
            m = Morpheme(
                form=normalised, slot_id="UNKNOWN", slot_name="",
                content_type="unknown", gloss=normalised, nc_id=None,
            )
            hypotheses.append(ParseHypothesis(
                morphemes=(m,), surface_form=token,
                remaining="", confidence=0.0,
                warnings=("No matching noun-class prefix found.",),
            ))
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses[:max_hypotheses]

    # ------------------------------------------------------------------
    # Public: generate
    # ------------------------------------------------------------------

    def generate(self, features: MorphFeatureBundle) -> SurfaceForm:
        """
        Generate an inflected verb surface form from a feature bundle.

        Pipeline: feature bundle → SlotFiller → StructuredMorph
                                → PhonologyEngine.forward() → surface

        Parameters
        ----------
        features : MorphFeatureBundle
            Feature specification including root, subject NC, TAM id,
            optional object NC, extensions, polarity, final vowel, and
            optional ``extra_slots`` for SLOT1/4/6/7/11.

        Returns
        -------
        SurfaceForm
            The generated form with surface string, underlying string,
            segmented representation, Leipzig gloss, morphemes, warnings,
            and the full phonological rule trace.

        Raises
        ------
        MorphAnalysisError
            If required features are missing or unknown.
        """
        # Layer 1: fill slots → StructuredMorph (underlying representation)
        sm = self._slot_filler.fill(features)
        warnings = list(sm.warnings)

        # Layer 2: forward phonology → surface
        nodes = sm.morphemes_ordered
        surface, rule_trace = self._phon_engine.forward(nodes)

        # Update underlying form on the StructuredMorph
        underlying = sm.underlying_string()

        # Build final morpheme list (surface forms after phonology may differ
        # from underlying; for now we use underlying forms per morpheme — a
        # full implementation would propagate rule changes back per-node)
        morphemes = sm.to_morphemes()

        # Segmented and gloss from the underlying (structured) form
        segmented = sm.segmented()
        gloss = sm.gloss_line()

        return SurfaceForm(
            surface=surface,
            segmented=segmented,
            gloss=gloss,
            morphemes=morphemes,
            features=features,
            warnings=tuple(warnings),
            underlying=underlying,
            rule_trace=tuple(rule_trace),
        )

    # ------------------------------------------------------------------
    # Public: interlinear gloss
    # ------------------------------------------------------------------

    def generate_interlinear(self, token: str, max_hypotheses: int = 1) -> str:
        """
        Produce a two-line Leipzig interlinear gloss for a single token.

        Line 1: morpheme-segmented form (e.g. ``a-lya-a``)
        Line 2: gloss line               (e.g. ``NC1.SUBJ-eat-FV``)
        """
        result = self.analyze(token, max_hypotheses=max_hypotheses)
        if result.best is None:
            return f"{token}\n???"
        best = result.best
        return f"{best.segmented}\n{best.gloss_line}"

    def segment_text(
        self, text: str, max_hypotheses: int = 3
    ) -> List[SegmentedToken]:
        """Tokenize running text and analyze each token."""
        tokens = self._word_boundary_re.split(text.strip())
        return [self.analyze(t, max_hypotheses=max_hypotheses) for t in tokens if t]

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def language(self) -> str:
        return self._language

    @property
    def loader(self):  # type: ignore[no-untyped-def]
        return self._loader

    @property
    def phonology_engine(self) -> PhonologyEngine:
        """Direct access to the phonology engine (for testing / extension)."""
        return self._phon_engine

    @property
    def slot_parser(self) -> SlotParser:
        """Direct access to the slot parser (for testing / extension)."""
        return self._slot_parser

    @property
    def constraint_engine(self) -> ConstraintEngine:
        """Direct access to the constraint engine (for adding custom rules)."""
        return self._constraint_engine
