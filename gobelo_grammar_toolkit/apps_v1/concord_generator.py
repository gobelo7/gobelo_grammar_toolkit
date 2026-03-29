"""
apps/concord_generator.py
=========================
ConcordGenerator — given a noun class, produce all concord forms across every
concord paradigm declared in the loaded grammar.

This module implements the ``ConcordGenerator`` app specified in GGT Part 9 and
is the primary tool for building agreement-paradigm tables, populating NLP
feature vectors, and generating reference-grammar concord matrices.

Overview
--------
Bantu languages express nominal agreement (concord) across a wide range of
syntactic contexts: subject marking on verbs, object marking, demonstratives
(proximal/medial/distal), possessives, adjectivals, relative markers, and
more.  The *number and names* of concord paradigms are language-specific and
declared in the YAML grammar file — this app makes no assumptions about which
paradigms exist, how many there are, or what they are named.

The core method, ``generate_all_concords(nc_id)``, returns a flat
``Dict[str, str]`` mapping each concord-type name to the surface form for the
requested noun class.  Only concord types for which a form exists (either
directly or via subclass fallback) are included in the dict; absent entries
signal that this noun class does not participate in that concord paradigm,
which is a linguistically meaningful fact (not a data error).

NC subclass fallback
--------------------
Many Bantu languages have noun-class subclasses (e.g. NC1a for kinship terms,
NC2a for their plurals, NC2b for proper names).  Subclasses often share their
agreement morphology with the base class but differ in prefix shape or
semantic domain.  The generator implements a **two-step lookup**:

1. Look for the exact ``nc_id`` key in ``ConcordSet.entries``.
2. If not found, strip the trailing alphabetic suffix to obtain the *base
   class* (``NC1a → NC1``, ``NC2b → NC2``) and retry.
3. If still not found, the concord type is excluded from the result for this
   NC (logged as ``ABSENT``).

This is the correct linguistic behaviour: NC1a kinship terms use NC1 agreement
morphology except where the grammar explicitly overrides it.

Design contract (Part 9)
-------------------------
* Accepts a ``GobeloGrammarLoader`` instance as its **only** grammar
  dependency — never reads YAML files directly.
* Uses **only** the public API methods from Part 6 of the spec.
* Is **language-agnostic** — no language-name checks, no hardcoded prefixes,
  no hardcoded concord-type lists.
* Handles ``GGTError`` subclasses gracefully via the ``ConcordResult.absent``
  flag and the ``errors`` field of ``AllConcordsResult``.

Typed return objects
--------------------
``generate_all_concords()`` returns the spec-mandated ``Dict[str, str]`` for
easy consumption by downstream code that simply needs ``{type: form}`` pairs.

All richer methods return the typed ``ConcordResult`` / ``AllConcordsResult`` /
``ConcordParadigm`` dataclasses defined below.  These carry full provenance
(which NC key was actually matched, whether a fallback was used, etc.) and are
safe to cache, hash, and compare.

Usage
-----
::

    from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    from gobelo_grammar_toolkit.apps.concord_generator import ConcordGenerator

    loader = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    gen    = ConcordGenerator(loader)

    # Flat dict: concord_type → form (only types where a form exists)
    forms = gen.generate_all_concords("NC7")
    print(forms["possessive_concords"])  # "ca"

    # Rich result with provenance
    result = gen.generate_concord("NC1a", "possessive_concords")
    print(result.form)          # "wa"
    print(result.is_fallback)   # False (NC1a has a direct entry here)

    # Full paradigm for one concord type across all active NCs
    paradigm = gen.generate_paradigm("subject_concords")
    for nc_id, form in paradigm.entries.items():
        print(f"  {nc_id}: {form}")

    # Markdown table of all concord types × all NCs
    print(gen.format_paradigm_table("possessive_concords", fmt="markdown"))

    # Cross-tabulation: List[ConcordRow] — one row per NC
    tab = gen.cross_tab()
    for row in tab.rows:
        print(row.nc_id, row.forms)
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Sequence

from gobelo_grammar_toolkit.core.exceptions import (
    ConcordTypeNotFoundError,
    GGTError,
    NounClassNotFoundError,
)
from gobelo_grammar_toolkit.core.loader import GobeloGrammarLoader
from gobelo_grammar_toolkit.core.models import NounClass

__all__ = [
    "ConcordGenerator",
    "ConcordResult",
    "AllConcordsResult",
    "ConcordParadigm",
    "ConcordRow",
    "CrossTab",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Regex that matches and captures the trailing alphabetic suffix of a
#: noun-class sub-identifier.  Used for base-class fallback resolution.
#: Examples: "NC1a" → suffix "a" / base "NC1";  "NC2b" → suffix "b".
_NC_SUBCLASS_RE = re.compile(r"^(NC\d+)([a-z]+)$")

#: Output formats understood by ``format_paradigm_table()``.
FormatLiteral = Literal["text", "markdown", "csv"]

# ---------------------------------------------------------------------------
# Typed result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConcordResult:
    """
    Result of a single concord lookup for one noun class and one concord type.

    This is the granular return type for ``ConcordGenerator.generate_concord()``.
    It carries the surface form *and* full provenance so callers can distinguish
    a direct hit from a subclass-fallback hit from a genuine absence.

    Parameters
    ----------
    nc_id : str
        The noun-class identifier that was *requested* (e.g. ``"NC1a"``).
    concord_type : str
        The concord paradigm that was queried (e.g. ``"possessive_concords"``).
    form : Optional[str]
        The surface concord morpheme, e.g. ``"wa"``, ``"ca-"``.  ``None``
        when this noun class does not participate in the requested concord
        paradigm (``absent`` will be ``True``).
    source_nc_id : str
        The NC key that was actually matched in ``ConcordSet.entries``.
        Equals ``nc_id`` for a direct hit; equals the base class (e.g.
        ``"NC1"``) for a fallback hit; equals ``nc_id`` when ``absent`` is
        ``True`` (no match found anywhere in the fallback chain).
    is_fallback : bool
        ``True`` when ``source_nc_id != nc_id``, meaning the form was
        inherited from the base class rather than declared explicitly for
        this sub-class.
    absent : bool
        ``True`` when no form could be found — neither for the exact NC id
        nor for its base class.  A ``True`` value here is linguistically
        meaningful: this NC simply does not participate in this concord type
        (e.g. NC1 human-class nouns use the pronoun agreement system in
        subject position rather than a class-numbered concord).

    Examples
    --------
    Direct hit::

        ConcordResult(
            nc_id="NC7", concord_type="possessive_concords",
            form="ca", source_nc_id="NC7",
            is_fallback=False, absent=False,
        )

    Sub-class fallback::

        ConcordResult(
            nc_id="NC1a", concord_type="subject_concords",
            form=None, source_nc_id="NC1a",
            is_fallback=False, absent=True,
        )
    """

    nc_id: str
    concord_type: str
    form: Optional[str]
    source_nc_id: str
    is_fallback: bool
    absent: bool


@dataclass(frozen=True)
class AllConcordsResult:
    """
    All concord forms for a single noun class across every concord paradigm
    declared in the grammar.

    Returned by ``ConcordGenerator.generate_all_concords_rich()``.  The
    ``forms`` attribute is the same mapping exposed by the spec-mandated
    ``generate_all_concords()`` method — a flat ``Dict[str, str]`` from
    concord-type name to form, containing **only** the paradigms for which a
    form was found.

    Parameters
    ----------
    nc_id : str
        The noun-class identifier that was requested.
    language : str
        ISO-code or language name from the loaded grammar's metadata, for
        display and serialisation.
    results : Dict[str, ConcordResult]
        Full per-paradigm provenance, keyed by concord-type name.  Includes
        both present (``absent=False``) and absent (``absent=True``) results.
    forms : Dict[str, str]
        Flat mapping of concord-type → form, only for paradigms where a form
        was found.  This is what ``generate_all_concords()`` returns.
    absent_types : List[str]
        Sorted list of concord-type names for which no form was found for
        this NC (i.e. all ``ConcordResult`` objects where ``absent=True``).
    fallback_types : List[str]
        Sorted list of concord-type names where the form was inherited from
        the base class (``is_fallback=True``).
    errors : Dict[str, str]
        Any ``GGTError`` messages encountered during lookup, keyed by
        concord-type name.  Non-empty only when a concord type raised an
        unexpected error (as opposed to a normal absence).
    """

    nc_id: str
    language: str
    results: Dict[str, ConcordResult]
    forms: Dict[str, str]
    absent_types: List[str]
    fallback_types: List[str]
    errors: Dict[str, str]


@dataclass(frozen=True)
class ConcordParadigm:
    """
    All noun-class entries for a single concord paradigm.

    Returned by ``ConcordGenerator.generate_paradigm()``.  Only noun classes
    that have an entry in ``ConcordSet.entries`` (for either the exact NC id
    or its base-class fallback) are included in ``entries``.

    Parameters
    ----------
    concord_type : str
        The concord paradigm name (e.g. ``"subject_concords"``).
    language : str
        Language identifier from the loaded grammar's metadata.
    entries : Dict[str, str]
        Mapping from NC id to concord form, ordered by NC numeric suffix.
        Only NCs that participate in this paradigm are included.
    source_nc_ids : Dict[str, str]
        For each NC id in ``entries``, the key that was actually matched —
        useful for detecting fallback entries.
    noun_class_count : int
        Total number of noun classes returned (len of ``entries``).
    """

    concord_type: str
    language: str
    entries: Dict[str, str]
    source_nc_ids: Dict[str, str]
    noun_class_count: int


@dataclass(frozen=True)
class ConcordRow:
    """
    One row of a cross-tabulation: all concord forms for one noun class.

    Parameters
    ----------
    nc_id : str
        Noun-class identifier.
    semantic_domain : str
        Semantic domain from ``NounClass.semantic_domain``.
    active : bool
        Whether the noun class is active in the grammar.
    forms : Dict[str, str]
        Concord-type → form mapping (only present types).  Same content as
        ``generate_all_concords(nc_id)``.
    absent_types : List[str]
        Concord types for which no form was found.
    fallback_types : List[str]
        Concord types resolved via base-class fallback.
    """

    nc_id: str
    semantic_domain: str
    active: bool
    forms: Dict[str, str]
    absent_types: List[str]
    fallback_types: List[str]


@dataclass(frozen=True)
class CrossTab:
    """
    Full cross-tabulation of concord forms: noun classes × concord types.

    Returned by ``ConcordGenerator.cross_tab()``.

    Parameters
    ----------
    language : str
        Language identifier from the loaded grammar's metadata.
    concord_types : List[str]
        Column headers — all concord types included in the tabulation,
        alphabetically sorted.
    rows : List[ConcordRow]
        One row per noun class, sorted by NC numeric suffix.
    noun_class_count : int
        Total number of noun classes included.
    concord_type_count : int
        Total number of concord-type columns.
    """

    language: str
    concord_types: List[str]
    rows: List[ConcordRow]
    noun_class_count: int
    concord_type_count: int


# ---------------------------------------------------------------------------
# ConcordGenerator
# ---------------------------------------------------------------------------


class ConcordGenerator:
    """
    Produce concord agreement forms for any noun class in a loaded grammar.

    This class is the sole client of ``GobeloGrammarLoader`` for all
    concord-related queries.  It is entirely language-agnostic: it reads the
    set of available concord types at construction time and adapts to
    whatever paradigms the grammar declares.

    Parameters
    ----------
    loader : GobeloGrammarLoader
        An already-initialised loader for the target language.  The generator
        holds a reference but never mutates the loader.

    Raises
    ------
    TypeError
        If ``loader`` is not a ``GobeloGrammarLoader`` instance.

    Examples
    --------
    ::

        loader = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
        gen    = ConcordGenerator(loader)

        # Spec-mandated method
        forms = gen.generate_all_concords("NC7")
        # → {"possessive_concords": "ca", "subject_concords": "ci", ...}

        # Rich result
        rich  = gen.generate_all_concords_rich("NC7")
        print(rich.absent_types)  # e.g. ["interrogative_concords"]
    """

    def __init__(self, loader: GobeloGrammarLoader) -> None:
        if not isinstance(loader, GobeloGrammarLoader):
            raise TypeError(
                f"ConcordGenerator requires a GobeloGrammarLoader instance; "
                f"got {type(loader).__name__}."
            )
        self._loader = loader
        # Materialise the list of concord types once at construction time.
        # get_all_concord_types() is O(1) on the cached _ParsedGrammar and
        # returns a sorted list, so caching here is just a micro-optimisation.
        self._concord_types: List[str] = loader.get_all_concord_types()
        self._language: str = loader.get_metadata().language

    # ------------------------------------------------------------------
    # Primary public API (Part 9 spec)
    # ------------------------------------------------------------------

    def generate_all_concords(self, nc_id: str) -> Dict[str, str]:
        """
        Return all concord forms for ``nc_id`` across every paradigm in the
        grammar.

        This is the **spec-mandated** method signature.  Only concord types
        for which a form was found (either directly or via subclass fallback)
        are included in the returned dict.  Absent entries — concord types
        where this noun class genuinely does not participate — are omitted
        rather than mapped to ``None`` or an empty string, because a missing
        key is semantically unambiguous whereas a ``None`` value is not.

        Parameters
        ----------
        nc_id : str
            Noun-class identifier (case-sensitive), e.g. ``"NC1"``,
            ``"NC7"``, ``"NC1a"``.

        Returns
        -------
        Dict[str, str]
            Mapping from concord-type name to surface form.  Keys are a
            subset of ``loader.get_all_concord_types()``.  Iteration order
            is alphabetical (concord-type name).

        Raises
        ------
        NounClassNotFoundError
            If ``nc_id`` is not registered in the loaded grammar.

        Examples
        --------
        ::

            gen = ConcordGenerator(loader)
            forms = gen.generate_all_concords("NC7")
            assert forms["possessive_concords"] == "ca"
            assert "subject_concords" in forms
        """
        # Validate NC id via the loader (raises NounClassNotFoundError if bad)
        self._loader.get_noun_class(nc_id)
        return self._build_forms(nc_id)

    # ------------------------------------------------------------------
    # Rich result variant
    # ------------------------------------------------------------------

    def generate_all_concords_rich(self, nc_id: str) -> AllConcordsResult:
        """
        Return all concord forms for ``nc_id`` with full provenance metadata.

        This is the richer version of ``generate_all_concords()``.  The
        returned ``AllConcordsResult.forms`` attribute contains the identical
        ``Dict[str, str]`` produced by the spec-mandated method.

        Parameters
        ----------
        nc_id : str
            Noun-class identifier.

        Returns
        -------
        AllConcordsResult

        Raises
        ------
        NounClassNotFoundError
            If ``nc_id`` is not registered.
        """
        # Validate
        self._loader.get_noun_class(nc_id)

        results: Dict[str, ConcordResult] = {}
        errors: Dict[str, str] = {}

        for ct in self._concord_types:
            try:
                result = self._lookup(nc_id, ct)
            except GGTError as exc:
                errors[ct] = str(exc)
                continue
            results[ct] = result

        forms = {ct: r.form for ct, r in results.items() if not r.absent and r.form is not None}
        absent = sorted(ct for ct, r in results.items() if r.absent)
        fallbacks = sorted(ct for ct, r in results.items() if r.is_fallback)

        return AllConcordsResult(
            nc_id=nc_id,
            language=self._language,
            results=results,
            forms=forms,
            absent_types=absent,
            fallback_types=fallbacks,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Single concord lookup
    # ------------------------------------------------------------------

    def generate_concord(self, nc_id: str, concord_type: str) -> ConcordResult:
        """
        Return the concord form for a single (nc_id, concord_type) pair.

        Parameters
        ----------
        nc_id : str
            Noun-class identifier.
        concord_type : str
            Concord-type name (must be in ``get_all_concord_types()``).

        Returns
        -------
        ConcordResult
            Full result with provenance.  ``result.absent`` is ``True`` if
            no form was found for this NC in this paradigm.

        Raises
        ------
        NounClassNotFoundError
            If ``nc_id`` is not registered.
        ConcordTypeNotFoundError
            If ``concord_type`` is not present in the grammar.

        Examples
        --------
        ::

            result = gen.generate_concord("NC7", "possessive_concords")
            assert result.form == "ca"
            assert not result.is_fallback
        """
        self._loader.get_noun_class(nc_id)      # validates nc_id
        self._loader.get_concords(concord_type)  # validates concord_type
        return self._lookup(nc_id, concord_type)

    # ------------------------------------------------------------------
    # Paradigm for one concord type across all NCs
    # ------------------------------------------------------------------

    def generate_paradigm(
        self,
        concord_type: str,
        active_only: bool = True,
    ) -> ConcordParadigm:
        """
        Return all noun-class entries for a single concord paradigm.

        Iterates every noun class in the grammar and looks up its form in
        ``concord_type``, applying subclass fallback as needed.  Only noun
        classes for which a form exists are included in the result.

        Parameters
        ----------
        concord_type : str
            The paradigm to query (e.g. ``"subject_concords"``).
        active_only : bool
            When ``True`` (default), only active noun classes are included.

        Returns
        -------
        ConcordParadigm

        Raises
        ------
        ConcordTypeNotFoundError
            If ``concord_type`` is not present in the grammar.

        Examples
        --------
        ::

            paradigm = gen.generate_paradigm("subject_concords")
            print(paradigm.entries["NC7"])   # "ci"
            print(paradigm.noun_class_count) # number of NCs with an entry
        """
        self._loader.get_concords(concord_type)  # validates; raises if missing

        ncs: List[NounClass] = self._loader.get_noun_classes(active_only=active_only)
        entries: Dict[str, str] = {}
        source_nc_ids: Dict[str, str] = {}

        for nc in ncs:
            result = self._lookup(nc.id, concord_type)
            if not result.absent and result.form is not None:
                entries[nc.id] = result.form
                source_nc_ids[nc.id] = result.source_nc_id

        return ConcordParadigm(
            concord_type=concord_type,
            language=self._language,
            entries=entries,
            source_nc_ids=source_nc_ids,
            noun_class_count=len(entries),
        )

    # ------------------------------------------------------------------
    # Available types for one NC
    # ------------------------------------------------------------------

    def list_available_concord_types(self, nc_id: str) -> List[str]:
        """
        Return the concord types that have an entry for ``nc_id``.

        Parameters
        ----------
        nc_id : str
            Noun-class identifier.

        Returns
        -------
        List[str]
            Alphabetically sorted list of concord-type names for which a form
            (direct or via fallback) was found for this NC.

        Raises
        ------
        NounClassNotFoundError
            If ``nc_id`` is not registered.
        """
        forms = self.generate_all_concords(nc_id)
        return sorted(forms.keys())

    # ------------------------------------------------------------------
    # Cross-tabulation
    # ------------------------------------------------------------------

    def cross_tab(
        self,
        concord_types: Optional[Sequence[str]] = None,
        active_only: bool = True,
    ) -> CrossTab:
        """
        Build a full concord form cross-tabulation.

        Produces a ``CrossTab`` with one ``ConcordRow`` per noun class and
        one column per concord type.  This is the data source for paradigm
        tables in reference grammars, teaching materials, and the CLI.

        Parameters
        ----------
        concord_types : Optional[Sequence[str]]
            Restrict columns to a subset of concord types.  When ``None``
            (default), all paradigms returned by ``get_all_concord_types()``
            are included.
        active_only : bool
            When ``True`` (default), only active noun classes are included.

        Returns
        -------
        CrossTab

        Raises
        ------
        ConcordTypeNotFoundError
            If any element of ``concord_types`` is not in the grammar.
        """
        # Validate concord_type subset
        selected_types: List[str]
        if concord_types is not None:
            for ct in concord_types:
                self._loader.get_concords(ct)  # raises if bad
            selected_types = sorted(concord_types)
        else:
            selected_types = self._concord_types  # already sorted

        ncs: List[NounClass] = self._loader.get_noun_classes(active_only=active_only)
        rows: List[ConcordRow] = []

        for nc in ncs:
            nc_forms: Dict[str, str] = {}
            nc_absent: List[str] = []
            nc_fallbacks: List[str] = []

            for ct in selected_types:
                result = self._lookup(nc.id, ct)
                if result.absent or result.form is None:
                    nc_absent.append(ct)
                else:
                    nc_forms[ct] = result.form
                    if result.is_fallback:
                        nc_fallbacks.append(ct)

            rows.append(
                ConcordRow(
                    nc_id=nc.id,
                    semantic_domain=nc.semantic_domain,
                    active=nc.active,
                    forms=nc_forms,
                    absent_types=nc_absent,
                    fallback_types=nc_fallbacks,
                )
            )

        return CrossTab(
            language=self._language,
            concord_types=selected_types,
            rows=rows,
            noun_class_count=len(rows),
            concord_type_count=len(selected_types),
        )

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def format_paradigm_table(
        self,
        concord_type: str,
        fmt: FormatLiteral = "text",
        active_only: bool = True,
    ) -> str:
        """
        Render a concord paradigm as a formatted string table.

        Supported formats:

        * ``"text"`` — plain-text aligned columns, suitable for terminal
          output and log files.
        * ``"markdown"`` — GitHub-flavoured Markdown table with ``|`` column
          separators and ``---`` header underlines.
        * ``"csv"`` — RFC 4180 CSV with header row ``nc_id,form``.

        Parameters
        ----------
        concord_type : str
            The paradigm to render.
        fmt : Literal["text", "markdown", "csv"]
            Output format.  Default: ``"text"``.
        active_only : bool
            Restrict to active noun classes.  Default: ``True``.

        Returns
        -------
        str
            Formatted table string.

        Raises
        ------
        ConcordTypeNotFoundError
            If ``concord_type`` is not in the grammar.
        ValueError
            If ``fmt`` is not one of the supported literals.
        """
        if fmt not in ("text", "markdown", "csv"):
            raise ValueError(
                f"Unsupported format {fmt!r}.  "
                f"Choose one of: 'text', 'markdown', 'csv'."
            )

        paradigm = self.generate_paradigm(concord_type, active_only=active_only)

        if fmt == "csv":
            return self._format_csv(paradigm)
        if fmt == "markdown":
            return self._format_markdown(paradigm)
        return self._format_text(paradigm)

    def format_cross_tab(
        self,
        concord_types: Optional[Sequence[str]] = None,
        active_only: bool = True,
        fmt: FormatLiteral = "markdown",
    ) -> str:
        """
        Render the full concord cross-tabulation as a formatted string.

        Parameters
        ----------
        concord_types : Optional[Sequence[str]]
            Restrict columns.  ``None`` → all paradigms.
        active_only : bool
            Restrict to active noun classes.
        fmt : Literal["text", "markdown", "csv"]
            Output format.  Default: ``"markdown"`` (most readable for
            multi-column tables).

        Returns
        -------
        str
            Formatted multi-column table string.
        """
        if fmt not in ("text", "markdown", "csv"):
            raise ValueError(
                f"Unsupported format {fmt!r}.  "
                f"Choose one of: 'text', 'markdown', 'csv'."
            )

        tab = self.cross_tab(concord_types=concord_types, active_only=active_only)

        if fmt == "csv":
            return self._format_cross_tab_csv(tab)
        if fmt == "markdown":
            return self._format_cross_tab_markdown(tab)
        return self._format_cross_tab_text(tab)

    # ------------------------------------------------------------------
    # Private: core lookup logic
    # ------------------------------------------------------------------

    def _lookup(self, nc_id: str, concord_type: str) -> ConcordResult:
        """
        Look up the form for ``(nc_id, concord_type)`` with subclass fallback.

        Resolution order:
        1. Exact key ``nc_id`` in ``ConcordSet.entries``.
        2. If ``nc_id`` is a subclass (e.g. ``"NC1a"``), strip the suffix
           and retry with the base class (``"NC1"``).
        3. If still not found, return an ``absent=True`` result.

        This method never raises ``GGTError`` — it always returns a
        ``ConcordResult``.  Callers that need to distinguish loader errors
        from normal absences should catch ``GGTError`` themselves.
        """
        concord_set = self._loader.get_concords(concord_type)
        entries = concord_set.entries

        # Step 1 — exact match
        if nc_id in entries:
            return ConcordResult(
                nc_id=nc_id,
                concord_type=concord_type,
                form=entries[nc_id],
                source_nc_id=nc_id,
                is_fallback=False,
                absent=False,
            )

        # Step 2 — base-class fallback for subclasses
        base = self._base_class(nc_id)
        if base is not None and base in entries:
            return ConcordResult(
                nc_id=nc_id,
                concord_type=concord_type,
                form=entries[base],
                source_nc_id=base,
                is_fallback=True,
                absent=False,
            )

        # Step 3 — genuinely absent
        return ConcordResult(
            nc_id=nc_id,
            concord_type=concord_type,
            form=None,
            source_nc_id=nc_id,
            is_fallback=False,
            absent=True,
        )

    def _build_forms(self, nc_id: str) -> Dict[str, str]:
        """
        Build the flat ``{concord_type: form}`` dict for ``nc_id``.

        Skips concord types where the NC is absent.  Errors are silently
        skipped (the type simply won't appear in the output).
        """
        forms: Dict[str, str] = {}
        for ct in self._concord_types:
            try:
                result = self._lookup(nc_id, ct)
            except GGTError:
                continue
            if not result.absent and result.form is not None:
                forms[ct] = result.form
        return forms

    # ------------------------------------------------------------------
    # Private: base-class resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _base_class(nc_id: str) -> Optional[str]:
        """
        Strip the trailing alphabetic suffix from a noun-class sub-identifier.

        Returns the base-class string if ``nc_id`` matches the subclass
        pattern, otherwise returns ``None``.

        Examples
        --------
        >>> ConcordGenerator._base_class("NC1a")
        'NC1'
        >>> ConcordGenerator._base_class("NC2b")
        'NC2'
        >>> ConcordGenerator._base_class("NC7")
        None
        >>> ConcordGenerator._base_class("NC1")
        None
        """
        m = _NC_SUBCLASS_RE.match(nc_id)
        return m.group(1) if m else None

    # ------------------------------------------------------------------
    # Private: single-paradigm formatters
    # ------------------------------------------------------------------

    @staticmethod
    def _format_text(paradigm: ConcordParadigm) -> str:
        """Plain-text aligned two-column table."""
        header = (
            f"Concord paradigm: {paradigm.concord_type}\n"
            f"Language: {paradigm.language}\n"
            f"Noun classes: {paradigm.noun_class_count}\n"
            + "-" * 32 + "\n"
            + f"{'NC':<10}  Form\n"
            + "-" * 32
        )
        rows = [header]
        for nc_id, form in paradigm.entries.items():
            rows.append(f"{nc_id:<10}  {form}")
        return "\n".join(rows)

    @staticmethod
    def _format_markdown(paradigm: ConcordParadigm) -> str:
        """GitHub-flavoured Markdown table."""
        lines = [
            f"### {paradigm.concord_type}  ({paradigm.language})",
            "",
            "| NC | Form |",
            "|----|------|",
        ]
        for nc_id, form in paradigm.entries.items():
            lines.append(f"| {nc_id} | {form} |")
        return "\n".join(lines)

    @staticmethod
    def _format_csv(paradigm: ConcordParadigm) -> str:
        """RFC 4180 CSV with header row."""
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["nc_id", "form"])
        for nc_id, form in paradigm.entries.items():
            writer.writerow([nc_id, form])
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Private: cross-tab formatters
    # ------------------------------------------------------------------

    @staticmethod
    def _format_cross_tab_csv(tab: CrossTab) -> str:
        """CSV cross-tab: nc_id + one column per concord type."""
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["nc_id", "semantic_domain"] + tab.concord_types)
        for row in tab.rows:
            values = [row.forms.get(ct, "") for ct in tab.concord_types]
            writer.writerow([row.nc_id, row.semantic_domain] + values)
        return buf.getvalue()

    @staticmethod
    def _format_cross_tab_markdown(tab: CrossTab) -> str:
        """Markdown cross-tab table."""
        # Short-form column headers (strip common suffixes for readability)
        def short(ct: str) -> str:
            return ct.replace("_concords", "").replace("_", "-")

        headers = ["NC", "Domain"] + [short(ct) for ct in tab.concord_types]
        lines = [
            f"### Concord cross-tabulation — {tab.language}",
            "",
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        for row in tab.rows:
            cells = [row.nc_id, row.semantic_domain] + [
                row.forms.get(ct, "—") for ct in tab.concord_types
            ]
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)

    @staticmethod
    def _format_cross_tab_text(tab: CrossTab) -> str:
        """Plain-text cross-tab (nc_id and form per line, grouped by type)."""
        parts: List[str] = [
            f"Cross-tabulation — {tab.language}",
            f"NCs: {tab.noun_class_count}   Paradigms: {tab.concord_type_count}",
        ]
        for ct in tab.concord_types:
            parts.append("")
            parts.append(f"  [{ct}]")
            for row in tab.rows:
                form = row.forms.get(ct, "—")
                parts.append(f"    {row.nc_id:<8} {form}")
        return "\n".join(parts)
