"""
apps/paradigm_generator.py
===========================
ParadigmGenerator — F-04 fully-inflected paradigm table generator.

Produces a :class:`ParadigmTable` for a verb root or noun stem across
all subject concords × all TAM markers (verb) or across all concord
types × the noun class of the stem (noun).  Tables can be exported as
Markdown, CSV (RFC 4180), or HTML.

Design contract
---------------
- Accepts a single ``GobeloGrammarLoader`` as its only grammar dependency.
- Language-agnostic: no hardcoded language names, prefixes, or TAM ids
  (except the generic FV-extraction logic, which reads ``tam_fv_interactions``
  from the verb template).
- Catches ``MorphAnalysisError`` per cell; records ``surface="ERROR"`` and
  continues — the table is never aborted for one bad cell.
- ``MorphologicalAnalyzer`` is instantiated internally; it is not a
  constructor parameter.

Usage
-----
::

    from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    from gobelo_grammar_toolkit.apps.paradigm_generator import ParadigmGenerator

    loader = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    gen    = ParadigmGenerator(loader)

    table = gen.generate_verb_paradigm("lya")
    print(gen.to_markdown(table))

    noun_table = gen.generate_noun_paradigm("muntu", "NC1")
    print(gen.to_csv(noun_table))
"""

from __future__ import annotations

import csv
import html
import io
import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Literal, Optional, Tuple

from gobelo_grammar_toolkit.core.exceptions import GGTError
from gobelo_grammar_toolkit.apps.morphological_analyzer import (
    MorphAnalysisError,
    MorphFeatureBundle,
    MorphologicalAnalyzer,
)

__all__ = [
    "ParadigmGenerator",
    "ParadigmCell",
    "ParadigmTable",
    "ParadigmGenerationError",
]

# ─────────────────────────────────────────────────────────────────────────────
# Exception
# ─────────────────────────────────────────────────────────────────────────────


class ParadigmGenerationError(GGTError):
    """
    Raised when the generator encounters an unrecoverable configuration
    problem (e.g. the loader returns no subject concords or no TAM markers).
    Distinct from per-cell ``MorphAnalysisError``, which is caught silently.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


# ─────────────────────────────────────────────────────────────────────────────
# Frozen output types
# ─────────────────────────────────────────────────────────────────────────────

_FV_IN_PARENS = re.compile(r"\((\w+)\)\s*$")


@dataclass(frozen=True)
class ParadigmCell:
    """
    One fully-inflected form in the paradigm table.

    Parameters
    ----------
    subject_nc_key : str
        The subject-concord key used to generate this cell
        (e.g. ``"1SG"``, ``"NC7"``).
    tam_id : str
        The TAM marker id used (e.g. ``"TAM_PRES"``).
    polarity : str
        Polarity string passed to ``MorphFeatureBundle``
        (e.g. ``"affirmative"``, ``"negative"``).
    surface : str
        Surface form (concatenated morphemes). ``"ERROR"`` if generation
        failed.
    segmented : str
        Hyphen-delimited morpheme segmentation (e.g. ``"ci-a-lya-a"``).
        Empty string on error.
    gloss : str
        Leipzig-style gloss line (e.g. ``"NC7.SUBJ-PRS-lya-FV"``).
        Empty string on error.
    warnings : Tuple[str, ...]
        Sandhi and other warnings from ``SurfaceForm.warnings``, plus any
        error message if generation failed.
    """

    subject_nc_key: str
    tam_id: str
    polarity: str
    surface: str
    segmented: str
    gloss: str
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class ParadigmTable:
    """
    A fully-inflected paradigm table.

    Parameters
    ----------
    root : str
        The verb root or noun stem used to generate this table.
    language : str
        The language identifier from the loader.
    paradigm_type : Literal["verb", "noun"]
        ``"verb"`` for a verb paradigm (SC × TAM), ``"noun"`` for a
        concord-agreement table (concord type × NC class).
    rows : Tuple[str, ...]
        Row labels.  For verb paradigms these are SC keys; for noun
        paradigms these are concord type names.
    columns : Tuple[str, ...]
        Column labels.  For verb paradigms these are TAM ids; for noun
        paradigms these are NC ids (typically just the one nc_id passed
        to :meth:`generate_noun_paradigm`).
    cells : Dict[Tuple[str, str], ParadigmCell]
        Mapping ``(row_label, column_label) → ParadigmCell``.  Missing
        (row, column) pairs indicate that no form exists (e.g. a concord
        type that has no entry for the given NC).
    metadata : Dict[str, str]
        Arbitrary string metadata: ``language``, ``root``,
        ``paradigm_type``, ``extensions``, ``polarities``.
    """

    root: str
    language: str
    paradigm_type: Literal["verb", "noun"]
    rows: Tuple[str, ...]
    columns: Tuple[str, ...]
    cells: Dict[Tuple[str, str], ParadigmCell]
    metadata: Dict[str, str]


# ─────────────────────────────────────────────────────────────────────────────
# ParadigmGenerator
# ─────────────────────────────────────────────────────────────────────────────


class ParadigmGenerator:
    """
    Generates fully-inflected paradigm tables for verbs and nouns.

    Parameters
    ----------
    loader : GobeloGrammarLoader
        An initialised loader for the target language.  This is the
        **only** grammar dependency; ``MorphologicalAnalyzer`` is
        created internally.

    Raises
    ------
    ParadigmGenerationError
        If the loader raises ``GGTError`` during index construction, or
        if required grammar data (subject concords, TAM markers) is absent.

    Examples
    --------
    >>> from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
    >>> from gobelo_grammar_toolkit.apps.paradigm_generator import ParadigmGenerator
    >>> loader = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
    >>> gen    = ParadigmGenerator(loader)
    >>> table  = gen.generate_verb_paradigm("lya")
    >>> print(gen.to_markdown(table))
    """

    def __init__(self, loader) -> None:  # type: ignore[no-untyped-def]
        try:
            self._build(loader)
        except GGTError as exc:
            raise ParadigmGenerationError(
                f"ParadigmGenerator init failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build(self, loader) -> None:  # type: ignore[no-untyped-def]
        meta = loader.get_metadata()
        self._language: str = meta.language

        # ── MorphologicalAnalyzer (internal) ──────────────────────────
        self._analyzer = MorphologicalAnalyzer(loader)

        # ── Subject concords ──────────────────────────────────────────
        try:
            sc = loader.get_subject_concords()
        except GGTError as exc:
            raise ParadigmGenerationError(
                f"Cannot build verb paradigm: no subject concords available ({exc})"
            ) from exc
        # Preserve insertion order (YAML order = person/number order)
        self._sc_entries: Dict[str, str] = dict(sc.entries)

        # ── TAM markers ───────────────────────────────────────────────
        try:
            self._tam_markers = list(loader.get_tam_markers())
        except GGTError as exc:
            raise ParadigmGenerationError(
                f"Cannot build verb paradigm: no TAM markers available ({exc})"
            ) from exc
        if not self._tam_markers:
            raise ParadigmGenerationError(
                "Grammar has no TAM markers; cannot generate paradigm columns."
            )

        # ── tam_id → final_vowel override map ─────────────────────────
        # Read from verb template's tam_fv_interactions.patterns.
        # Each pattern's SLOT10 string looks like "final_vowels.NAME (fv)".
        # Match pattern names to TAM ids via substring search on the tam id.
        self._tam_fv: Dict[str, str] = {}
        try:
            vt = loader.get_verb_template()
            self._tam_fv = self._extract_tam_fv_map(vt)
        except GGTError:
            pass  # degrade gracefully; all TAMs will use default FV "a"

        # ── All concord types (for noun paradigm) ─────────────────────
        self._concord_types: List[str] = []
        try:
            self._concord_types = list(loader.get_all_concord_types())
        except GGTError:
            pass

        # ── Concord set cache {type → entries dict} ───────────────────
        self._concord_cache: Dict[str, Dict[str, str]] = {}
        for ct in self._concord_types:
            try:
                cs = loader.get_concords(ct)
                self._concord_cache[ct] = dict(cs.entries)
            except GGTError:
                pass

    @staticmethod
    def _extract_tam_fv_map(vt: dict) -> Dict[str, str]:
        """
        Parse ``verb_template["tam_fv_interactions"]["patterns"]`` and
        return a mapping ``{tam_id: final_vowel}``.

        Strategy
        --------
        Each pattern in the ``patterns`` dict has a ``slots.SLOT10``
        value of the form ``"final_vowels.<name> (<fv>)"``.  We extract
        the FV from the parenthesised suffix.

        We then match the pattern name to TAM ids by looking for a
        keyword fragment of the pattern name (e.g. ``"perf"`` in
        ``"TAM_PERF"``, ``"subj"`` in ``"TAM_SUBJ"``).  Patterns that
        don't match any TAM id are ignored.  TAMs not matched by any
        pattern keep the default FV ``"a"``.
        """
        patterns = {}
        try:
            patterns = vt.get("tam_fv_interactions", {}).get("patterns", {})
        except (AttributeError, TypeError):
            return {}

        # Map pattern-name keywords → fv
        # e.g. "perfect" → "ide", "subjunctive" → "e", "negative_present" → "i"
        # keyword fragments to try (longest first for priority)
        KEYWORD_FRAGMENTS: List[Tuple[str, str]] = [
            ("negative_present", "negative_present"),
            ("perfect",          "perf"),
            ("subjunctive",      "subj"),
            ("habitual",         "hab"),
            ("present_habitual", "pres"),
        ]

        # Build {fragment: fv}
        fragment_fv: Dict[str, str] = {}
        for pattern_name, pat in patterns.items():
            if not isinstance(pat, dict):
                continue
            slot10 = ""
            try:
                slot10 = str(pat.get("slots", {}).get("SLOT10", ""))
            except (AttributeError, TypeError):
                pass
            m = _FV_IN_PARENS.search(slot10)
            if not m:
                continue
            fv = m.group(1)
            # Map this pattern name to a keyword
            p_lower = pattern_name.lower()
            for kw_full, kw_short in KEYWORD_FRAGMENTS:
                if kw_full in p_lower or kw_short in p_lower:
                    fragment_fv[kw_short] = fv
                    break
            else:
                # Store under the raw pattern name as a fallback key
                fragment_fv[pattern_name.lower()] = fv

        return fragment_fv

    def _fv_for_tam(self, tam_id: str) -> str:
        """
        Return the final vowel to use for a given TAM id.

        Checks the ``fragment_fv`` map built from ``tam_fv_interactions``.
        Falls back to ``"a"``.
        """
        tam_lower = tam_id.lower()
        for fragment, fv in self._tam_fv.items():
            if fragment in tam_lower:
                return fv
        return "a"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_verb_paradigm(
        self,
        root: str,
        extensions: Tuple[str, ...] = (),
        polarities: Tuple[str, ...] = ("affirmative",),
        exclude_sc_keys: Optional[FrozenSet[str]] = None,
    ) -> ParadigmTable:
        """
        Generate a fully-inflected verb paradigm table.

        Iterates over every ``(sc_key, tam)`` pair for each requested
        polarity.  When multiple polarities are requested the TAM column
        labels are suffixed with the polarity (e.g. ``"TAM_PRES/neg"``).

        Parameters
        ----------
        root : str
            Bare verb root (no affixes), e.g. ``"lya"``, ``"bona"``.
        extensions : Tuple[str, ...]
            Ordered verb extension ids to include in every cell,
            e.g. ``("APPL",)``.
        polarities : Tuple[str, ...]
            Polarity values to generate.  Default: ``("affirmative",)``.
            Pass ``("affirmative", "negative")`` for a positive/negative
            split.
        exclude_sc_keys : Optional[FrozenSet[str]]
            SC keys to skip (e.g. ``frozenset({"NEG.SG", "NEG.1PL"})``).

        Returns
        -------
        ParadigmTable

        Raises
        ------
        ParadigmGenerationError
            If ``root`` is empty.

        Examples
        --------
        >>> table = gen.generate_verb_paradigm("lya")
        >>> table.cells[("1SG", "TAM_PRES")].surface
        'ndialyaa'
        """
        if not root:
            raise ParadigmGenerationError("root must be a non-empty string")

        # Column labels: TAM ids, optionally suffixed with polarity
        multi_pol = len(polarities) > 1
        columns: List[str] = []
        for tam in self._tam_markers:
            for pol in polarities:
                col_label = f"{tam.id}/{pol}" if multi_pol else tam.id
                columns.append(col_label)

        # Row labels: SC keys in insertion order, filtered
        rows: List[str] = [
            k for k in self._sc_entries
            if exclude_sc_keys is None or k not in exclude_sc_keys
        ]
        if not rows:
            raise ParadigmGenerationError(
                "No subject-concord keys remain after applying exclude_sc_keys."
            )

        cells: Dict[Tuple[str, str], ParadigmCell] = {}

        for sc_key in rows:
            for tam in self._tam_markers:
                for pol in polarities:
                    col_label = f"{tam.id}/{pol}" if multi_pol else tam.id
                    final_vowel = self._fv_for_tam(tam.id)
                    cell = self._generate_cell(
                        root=root,
                        sc_key=sc_key,
                        tam_id=tam.id,
                        polarity=pol,
                        extensions=extensions,
                        final_vowel=final_vowel,
                    )
                    cells[(sc_key, col_label)] = cell

        ext_str = "+".join(extensions) if extensions else ""
        pol_str = ",".join(polarities)
        return ParadigmTable(
            root=root,
            language=self._language,
            paradigm_type="verb",
            rows=tuple(rows),
            columns=tuple(columns),
            cells=cells,
            metadata={
                "language":      self._language,
                "root":          root,
                "paradigm_type": "verb",
                "extensions":    ext_str,
                "polarities":    pol_str,
            },
        )

    def generate_noun_paradigm(
        self,
        stem: str,
        nc_id: str,
    ) -> ParadigmTable:
        """
        Generate a concord-agreement table for a noun stem in a given NC.

        Rows are concord type names; the single column is ``nc_id``.
        Each cell contains the concord prefix for that type, or an empty
        string if the concord type has no entry for the given NC.

        This method does **not** use ``MorphologicalAnalyzer``; it reads
        directly from the concord cache built at ``__init__`` time.

        Parameters
        ----------
        stem : str
            The noun stem (used for display and metadata only).
        nc_id : str
            The noun class of the stem (e.g. ``"NC1"``, ``"NC7"``).

        Returns
        -------
        ParadigmTable

        Raises
        ------
        ParadigmGenerationError
            If ``stem`` or ``nc_id`` is empty.

        Examples
        --------
        >>> table = gen.generate_noun_paradigm("muntu", "NC1")
        >>> table.cells[("subject_concords", "NC1")].surface
        'u'
        """
        if not stem:
            raise ParadigmGenerationError("stem must be a non-empty string")
        if not nc_id:
            raise ParadigmGenerationError("nc_id must be a non-empty string")

        rows: List[str] = []
        cells: Dict[Tuple[str, str], ParadigmCell] = {}

        for ct in self._concord_types:
            entries = self._concord_cache.get(ct, {})
            if nc_id not in entries:
                continue  # this concord type has no entry for nc_id — skip row
            form = str(entries[nc_id])
            rows.append(ct)
            cells[(ct, nc_id)] = ParadigmCell(
                subject_nc_key=nc_id,
                tam_id="",
                polarity="",
                surface=form,
                segmented=form,
                gloss=f"{ct}.{nc_id}",
                warnings=(),
            )

        return ParadigmTable(
            root=stem,
            language=self._language,
            paradigm_type="noun",
            rows=tuple(rows),
            columns=(nc_id,),
            cells=cells,
            metadata={
                "language":      self._language,
                "stem":          stem,
                "nc_id":         nc_id,
                "paradigm_type": "noun",
            },
        )

    # ------------------------------------------------------------------
    # Export: Markdown
    # ------------------------------------------------------------------

    def to_markdown(self, table: ParadigmTable) -> str:
        """
        Render the paradigm table as a GitHub-Flavoured Markdown pipe table.

        The first column contains row labels (SC keys or concord type names).
        Subsequent columns contain the surface form for each column label
        (TAM id or NC id).  If a cell is absent the slot is left empty.

        A ``> ⚠ N sandhi warnings suppressed`` footnote is appended when
        any cell contains non-empty warnings.

        Parameters
        ----------
        table : ParadigmTable

        Returns
        -------
        str
        """
        lines: List[str] = []

        # Header row
        header_cells = ["**SC / TAM**" if table.paradigm_type == "verb" else "**Concord Type**"]
        header_cells += [f"**{col}**" for col in table.columns]
        lines.append("| " + " | ".join(header_cells) + " |")

        # Separator row
        sep = ["---"] * len(header_cells)
        lines.append("| " + " | ".join(sep) + " |")

        # Data rows
        warning_count = 0
        for row in table.rows:
            row_cells = [f"`{row}`"]
            for col in table.columns:
                cell = table.cells.get((row, col))
                if cell is None:
                    row_cells.append("")
                else:
                    row_cells.append(cell.surface)
                    warning_count += len(cell.warnings)
            lines.append("| " + " | ".join(row_cells) + " |")

        md = "\n".join(lines)

        if warning_count:
            md += f"\n\n> ⚠ {warning_count} sandhi warning{'s' if warning_count != 1 else ''} suppressed"

        return md

    # ------------------------------------------------------------------
    # Export: CSV
    # ------------------------------------------------------------------

    def to_csv(self, table: ParadigmTable) -> str:
        """
        Render the paradigm table as RFC 4180 CSV.

        Each cell contains ``surface (segmented)`` — e.g. ``cialyaa (ci-a-lya-a)``.
        For noun paradigms, only the surface form is written.

        Parameters
        ----------
        table : ParadigmTable

        Returns
        -------
        str
            UTF-8 CSV string (newline-terminated).
        """
        buf = io.StringIO()
        writer = csv.writer(buf, dialect="excel", lineterminator="\n")

        # Header row
        first_col = "SC Key" if table.paradigm_type == "verb" else "Concord Type"
        writer.writerow([first_col] + list(table.columns))

        # Data rows
        for row in table.rows:
            row_data = [row]
            for col in table.columns:
                cell = table.cells.get((row, col))
                if cell is None:
                    row_data.append("")
                elif table.paradigm_type == "verb":
                    row_data.append(f"{cell.surface} ({cell.segmented})")
                else:
                    row_data.append(cell.surface)
            writer.writerow(row_data)

        return buf.getvalue()

    # ------------------------------------------------------------------
    # Export: HTML
    # ------------------------------------------------------------------

    def to_html(self, table: ParadigmTable, title: str = "") -> str:
        """
        Render the paradigm table as an HTML ``<table>``.

        - Column headers use ``<th scope="col">``.
        - Row headers use ``<th scope="row">``.
        - Data cells use ``<td data-gloss="...">``, where ``data-gloss``
          is populated from ``ParadigmCell.gloss``.
        - A ``<caption>`` element is added when ``title`` is non-empty.
        - All values are HTML-escaped.

        Parameters
        ----------
        table : ParadigmTable
        title : str
            Optional caption for the table.

        Returns
        -------
        str
            Self-contained ``<table>…</table>`` fragment (no ``<html>``
            wrapper).
        """
        lines: List[str] = []
        lines.append('<table class="ggt-paradigm">')

        if title:
            lines.append(f"  <caption>{html.escape(title)}</caption>")

        # ── thead ─────────────────────────────────────────────────────
        lines.append("  <thead>")
        lines.append("    <tr>")
        first_th = "SC / TAM" if table.paradigm_type == "verb" else "Concord Type"
        lines.append(f'      <th scope="col">{html.escape(first_th)}</th>')
        for col in table.columns:
            lines.append(f'      <th scope="col">{html.escape(col)}</th>')
        lines.append("    </tr>")
        lines.append("  </thead>")

        # ── tbody ─────────────────────────────────────────────────────
        lines.append("  <tbody>")
        for row in table.rows:
            lines.append("    <tr>")
            lines.append(f'      <th scope="row">{html.escape(row)}</th>')
            for col in table.columns:
                cell = table.cells.get((row, col))
                if cell is None:
                    lines.append('      <td></td>')
                else:
                    surf    = html.escape(cell.surface)
                    gloss   = html.escape(cell.gloss)
                    seg     = html.escape(cell.segmented)
                    has_warn = "true" if cell.warnings else "false"
                    lines.append(
                        f'      <td data-gloss="{gloss}"'
                        f' data-segmented="{seg}"'
                        f' data-has-warning="{has_warn}">'
                        f'{surf}</td>'
                    )
            lines.append("    </tr>")
        lines.append("  </tbody>")
        lines.append("</table>")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal cell generation
    # ------------------------------------------------------------------

    def _generate_cell(
        self,
        root: str,
        sc_key: str,
        tam_id: str,
        polarity: str,
        extensions: Tuple[str, ...],
        final_vowel: str,
    ) -> ParadigmCell:
        """
        Generate a single ``ParadigmCell`` via ``MorphologicalAnalyzer.generate()``.

        On ``MorphAnalysisError``, returns a cell with ``surface="ERROR"``
        and the error message in ``warnings``.
        """
        try:
            bundle = MorphFeatureBundle(
                root=root,
                subject_nc=sc_key,
                tam_id=tam_id,
                object_nc=None,
                extensions=extensions,
                polarity=polarity,
                final_vowel=final_vowel,
            )
            sf = self._analyzer.generate(bundle)
            return ParadigmCell(
                subject_nc_key=sc_key,
                tam_id=tam_id,
                polarity=polarity,
                surface=sf.surface,
                segmented=sf.segmented,
                gloss=sf.gloss,
                warnings=tuple(sf.warnings),
            )
        except MorphAnalysisError as exc:
            return ParadigmCell(
                subject_nc_key=sc_key,
                tam_id=tam_id,
                polarity=polarity,
                surface="ERROR",
                segmented="",
                gloss="",
                warnings=(str(exc),),
            )
        except GGTError as exc:
            # Any other GGTError from the analyzer
            return ParadigmCell(
                subject_nc_key=sc_key,
                tam_id=tam_id,
                polarity=polarity,
                surface="ERROR",
                segmented="",
                gloss="",
                warnings=(f"{type(exc).__name__}: {exc}",),
            )

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def language(self) -> str:
        """The language identifier from the grammar loader."""
        return self._language

    @property
    def sc_keys(self) -> Tuple[str, ...]:
        """All subject-concord keys available for verb paradigm rows."""
        return tuple(self._sc_entries.keys())

    @property
    def tam_ids(self) -> Tuple[str, ...]:
        """All TAM ids available for verb paradigm columns."""
        return tuple(t.id for t in self._tam_markers)

    @property
    def concord_types(self) -> Tuple[str, ...]:
        """All concord type names available for noun paradigm rows."""
        return tuple(self._concord_types)
