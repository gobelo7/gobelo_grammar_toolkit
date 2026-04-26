"""
apps/paradigm_generator.py  (v2 — phonology-aware paradigm generation)
=======================================================================
ParadigmGenerator — F-04 fully-inflected paradigm table generator.

Changes from v1
---------------
* ``ParadigmCell`` carries two new fields: ``underlying`` (the pre-phonology
  concatenation) and ``rule_trace`` (the ordered list of phonological rules
  that fired during generation).  These are populated from the v2
  ``SurfaceForm.underlying`` and ``SurfaceForm.rule_trace`` respectively.
* ``to_html()`` adds ``data-underlying`` and ``data-rules`` attributes so
  downstream interfaces can expose the derivation.
* ``to_markdown()`` warning count now reflects actual phonological rules
  applied, not just suppressed warnings.
* ``to_csv()`` adds an extra column for the underlying form when it differs
  from the segmented surface.
* ``_generate_cell()`` passes the full ``SurfaceForm`` into the cell builder.

Everything else is backward-compatible with v1.
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
        The subject-concord key used to generate this cell.
    tam_id : str
        The TAM marker id used.
    polarity : str
        Polarity string (``"affirmative"`` or ``"negative"``).
    surface : str
        Surface form (after phonological forward pass). ``"ERROR"`` if
        generation failed.
    segmented : str
        Hyphen-delimited morpheme segmentation of the underlying form.
    gloss : str
        Leipzig-style gloss line.
    warnings : Tuple[str, ...]
        Non-fatal issues (negation stubs, etc.).
    underlying : str
        The pre-phonology concatenation (new in v2).  Empty string on error
        or when identical to ``surface``.
    rule_trace : Tuple[str, ...]
        Ordered list of phonological rules that fired during generation
        (new in v2).  Empty when no rules fired or on error.
    """

    subject_nc_key: str
    tam_id: str
    polarity: str
    surface: str
    segmented: str
    gloss: str
    warnings: Tuple[str, ...]
    # v2 additions (default-safe for backward compat)
    underlying: str = ""
    rule_trace: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ParadigmTable:
    """
    A fully-inflected paradigm table.

    Parameters
    ----------
    root : str
        The verb root or noun stem.
    language : str
        The language identifier from the loader.
    paradigm_type : Literal["verb", "noun"]
    rows : Tuple[str, ...]
        Row labels (SC keys or concord type names).
    columns : Tuple[str, ...]
        Column labels (TAM ids or NC ids).
    cells : Dict[Tuple[str, str], ParadigmCell]
        ``(row_label, column_label) → ParadigmCell``.
    metadata : Dict[str, str]
        Arbitrary string metadata.
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
        An initialised loader for the target language.  ``MorphologicalAnalyzer``
        is created internally.

    Raises
    ------
    ParadigmGenerationError
        If the loader raises ``GGTError`` during construction, or if required
        grammar data (subject concords, TAM markers) is absent.
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

        # MorphologicalAnalyzer (internal)
        self._analyzer = MorphologicalAnalyzer(loader)

        # Subject concords
        try:
            sc = loader.get_subject_concords()
        except GGTError as exc:
            raise ParadigmGenerationError(
                f"Cannot build verb paradigm: no subject concords ({exc})"
            ) from exc
        self._sc_entries: Dict[str, str] = dict(sc.entries)

        # TAM markers
        try:
            self._tam_markers = list(loader.get_tam_markers())
        except GGTError as exc:
            raise ParadigmGenerationError(
                f"Cannot build verb paradigm: no TAM markers ({exc})"
            ) from exc
        if not self._tam_markers:
            raise ParadigmGenerationError(
                "Grammar has no TAM markers; cannot generate paradigm columns."
            )

        # TAM id → final-vowel override map
        self._tam_fv: Dict[str, str] = {}
        try:
            vt = loader.get_verb_template()
            self._tam_fv = self._extract_tam_fv_map(vt)
        except GGTError:
            pass

        # Concord types (for noun paradigm)
        self._concord_types: List[str] = []
        try:
            self._concord_types = list(loader.get_all_concord_types())
        except GGTError:
            pass

        # Concord set cache {type → entries dict}
        self._concord_cache: Dict[str, Dict[str, str]] = {}
        for ct in self._concord_types:
            try:
                cs = loader.get_concords(ct)
                self._concord_cache[ct] = dict(cs.entries)
            except GGTError:
                pass

    @staticmethod
    def _extract_tam_fv_map(vt: dict) -> Dict[str, str]:
        """Parse ``verb_template[tam_fv_interactions][patterns]`` → {tam_id: fv}."""
        patterns = {}
        try:
            patterns = vt.get("tam_fv_interactions", {}).get("patterns", {})
        except (AttributeError, TypeError):
            return {}

        KEYWORD_FRAGMENTS: List[Tuple[str, str]] = [
            ("negative_present", "negative_present"),
            ("perfect",          "perf"),
            ("subjunctive",      "subj"),
            ("habitual",         "hab"),
            ("present_habitual", "pres"),
        ]

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
            p_lower = pattern_name.lower()
            for kw_full, kw_short in KEYWORD_FRAGMENTS:
                if kw_full in p_lower or kw_short in p_lower:
                    fragment_fv[kw_short] = fv
                    break
            else:
                fragment_fv[pattern_name.lower()] = fv

        return fragment_fv

    def _fv_for_tam(self, tam_id: str) -> str:
        """Return the final vowel for a given TAM id; default ``"a"``."""
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

        Parameters
        ----------
        root : str
            Bare verb root (no affixes).
        extensions : Tuple[str, ...]
            Ordered verb extension ids to apply in every cell.
        polarities : Tuple[str, ...]
            Polarity values to generate (default: ``("affirmative",)``).
        exclude_sc_keys : Optional[FrozenSet[str]]
            SC keys to skip.

        Returns
        -------
        ParadigmTable
        """
        if not root:
            raise ParadigmGenerationError("root must be a non-empty string")

        multi_pol = len(polarities) > 1
        columns: List[str] = []
        for tam in self._tam_markers:
            for pol in polarities:
                col_label = f"{tam.id}/{pol}" if multi_pol else tam.id
                columns.append(col_label)

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

        Parameters
        ----------
        stem : str
            The noun stem (display and metadata only).
        nc_id : str
            The noun class of the stem (e.g. ``"NC1"``).

        Returns
        -------
        ParadigmTable
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
                continue
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
                underlying=form,
                rule_trace=(),
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

    def to_markdown(self, table: ParadigmTable, show_underlying: bool = False) -> str:
        """
        Render as a GitHub-Flavoured Markdown pipe table.

        Parameters
        ----------
        table : ParadigmTable
        show_underlying : bool
            When ``True``, append the underlying form in parentheses when it
            differs from the surface (v2 feature).

        Returns
        -------
        str
        """
        lines: List[str] = []

        first_header = (
            "**SC / TAM**" if table.paradigm_type == "verb" else "**Concord Type**"
        )
        header_cells = [first_header] + [f"**{col}**" for col in table.columns]
        lines.append("| " + " | ".join(header_cells) + " |")
        sep = ["---"] * len(header_cells)
        lines.append("| " + " | ".join(sep) + " |")

        rule_count = 0
        for row in table.rows:
            row_cells = [f"`{row}`"]
            for col in table.columns:
                cell = table.cells.get((row, col))
                if cell is None:
                    row_cells.append("")
                else:
                    text = cell.surface
                    if (
                        show_underlying
                        and cell.underlying
                        and cell.underlying != cell.surface
                    ):
                        text = f"{cell.surface} ({cell.underlying})"
                    row_cells.append(text)
                    rule_count += len(cell.rule_trace)
            lines.append("| " + " | ".join(row_cells) + " |")

        md = "\n".join(lines)

        footnotes: List[str] = []
        if rule_count:
            footnotes.append(
                f"> ℹ {rule_count} phonological rule application"
                f"{'s' if rule_count != 1 else ''} during generation"
            )
        if footnotes:
            md += "\n\n" + "\n".join(footnotes)

        return md

    # ------------------------------------------------------------------
    # Export: CSV
    # ------------------------------------------------------------------

    def to_csv(self, table: ParadigmTable, include_underlying: bool = True) -> str:
        """
        Render as RFC 4180 CSV.

        For verb paradigms each cell contains ``surface (segmented)``.
        When ``include_underlying=True`` and the underlying form differs
        from the surface, an extra column ``<TAM_id>_underlying`` is appended
        for each TAM column (v2 feature).

        Parameters
        ----------
        table : ParadigmTable
        include_underlying : bool
            Include underlying-form columns (default ``True``).

        Returns
        -------
        str
        """
        buf = io.StringIO()
        writer = csv.writer(buf, dialect="excel", lineterminator="\n")

        first_col = "SC Key" if table.paradigm_type == "verb" else "Concord Type"
        col_headers = list(table.columns)
        if include_underlying and table.paradigm_type == "verb":
            # Interleave underlying columns
            full_headers: List[str] = []
            for col in col_headers:
                full_headers.append(col)
                full_headers.append(f"{col}_underlying")
            writer.writerow([first_col] + full_headers)
        else:
            writer.writerow([first_col] + col_headers)

        for row in table.rows:
            row_data = [row]
            for col in table.columns:
                cell = table.cells.get((row, col))
                if cell is None:
                    row_data.append("")
                    if include_underlying and table.paradigm_type == "verb":
                        row_data.append("")
                elif table.paradigm_type == "verb":
                    row_data.append(f"{cell.surface} ({cell.segmented})")
                    if include_underlying:
                        row_data.append(cell.underlying if cell.underlying != cell.surface else "")
                else:
                    row_data.append(cell.surface)
            writer.writerow(row_data)

        return buf.getvalue()

    # ------------------------------------------------------------------
    # Export: HTML
    # ------------------------------------------------------------------

    def to_html(self, table: ParadigmTable, title: str = "") -> str:
        """
        Render as an HTML ``<table>``.

        Data cells now carry two additional attributes (v2):
        - ``data-underlying`` — the pre-phonology form
        - ``data-rules``      — pipe-delimited list of rule IDs that fired

        Parameters
        ----------
        table : ParadigmTable
        title : str
            Optional ``<caption>``.

        Returns
        -------
        str
        """
        lines: List[str] = []
        lines.append('<table class="ggt-paradigm">')

        if title:
            lines.append(f"  <caption>{html.escape(title)}</caption>")

        # thead
        lines.append("  <thead>")
        lines.append("    <tr>")
        first_th = "SC / TAM" if table.paradigm_type == "verb" else "Concord Type"
        lines.append(f'      <th scope="col">{html.escape(first_th)}</th>')
        for col in table.columns:
            lines.append(f'      <th scope="col">{html.escape(col)}</th>')
        lines.append("    </tr>")
        lines.append("  </thead>")

        # tbody
        lines.append("  <tbody>")
        for row in table.rows:
            lines.append("    <tr>")
            lines.append(f'      <th scope="row">{html.escape(row)}</th>')
            for col in table.columns:
                cell = table.cells.get((row, col))
                if cell is None:
                    lines.append("      <td></td>")
                else:
                    surf      = html.escape(cell.surface)
                    gloss     = html.escape(cell.gloss)
                    seg       = html.escape(cell.segmented)
                    underlying = html.escape(cell.underlying or "")
                    rules     = html.escape("|".join(
                        r.split(":")[0] for r in cell.rule_trace
                    ))
                    has_warn  = "true" if cell.warnings else "false"
                    lines.append(
                        f'      <td'
                        f' data-gloss="{gloss}"'
                        f' data-segmented="{seg}"'
                        f' data-underlying="{underlying}"'
                        f' data-rules="{rules}"'
                        f' data-has-warning="{has_warn}">'
                        f"{surf}</td>"
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

        Propagates ``SurfaceForm.underlying`` and ``SurfaceForm.rule_trace``
        into the cell (v2).  On ``MorphAnalysisError``, returns a cell with
        ``surface="ERROR"`` and the error in ``warnings``.
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
                underlying=sf.underlying,
                rule_trace=tuple(sf.rule_trace),
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
                underlying="",
                rule_trace=(),
            )
        except GGTError as exc:
            return ParadigmCell(
                subject_nc_key=sc_key,
                tam_id=tam_id,
                polarity=polarity,
                surface="ERROR",
                segmented="",
                gloss="",
                warnings=(f"{type(exc).__name__}: {exc}",),
                underlying="",
                rule_trace=(),
            )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def language(self) -> str:
        return self._language

    @property
    def sc_keys(self) -> Tuple[str, ...]:
        return tuple(self._sc_entries.keys())

    @property
    def tam_ids(self) -> Tuple[str, ...]:
        return tuple(t.id for t in self._tam_markers)

    @property
    def concord_types(self) -> Tuple[str, ...]:
        return tuple(self._concord_types)
