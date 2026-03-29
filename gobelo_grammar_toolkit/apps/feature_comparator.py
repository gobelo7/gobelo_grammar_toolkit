"""
apps/feature_comparator.py
===========================
FeatureComparator — F-05 cross-language feature comparison.

Given a dot-notation feature path (e.g. ``noun_class.NC7.prefix``,
``extension.PASS.zone``, ``tam.TAM_PRES.form``) queries that path
against every loaded language and returns a :class:`ComparisonTable`.

Supported path schemas
-----------------------
All paths follow the pattern ``entity_type.entity_id.field``
(three segments), with the exception of ``metadata.<field>`` which
uses only two segments.

=================================  ==========================================
Path pattern                       Resolution
=================================  ==========================================
``noun_class.<NC_ID>.<field>``     ``loader.get_noun_class(NC_ID).<field>``
``tam.<TAM_ID>.<field>``           TAM list search → ``marker.<field>``
``extension.<EXT_ID>.<field>``     Extension list search → ``ext.<field>``
``concord.<type>.<key>``           ``loader.get_concords(type).entries[key]``
``metadata.<field>``               ``loader.get_metadata().<field>``
``verb_slot.<SLOT_ID>.<field>``    Slot list search → ``slot.<field>``
=================================  ==========================================

Any unknown ``entity_type`` prefix raises :class:`FeatureComparatorError`
with a message listing the valid prefixes, so the caller receives
immediate, actionable feedback rather than a silent empty result.

Design contract
---------------
- Accepts ``Dict[str, GobeloGrammarLoader]`` — multiple loaders, one per
  language.  This is the only constructor dependency.
- Uses **only** the public loader API (Part 6).  No raw YAML access.
- When an entity id does not exist in a language (e.g. ``extension.PASS``
  for stub languages), ``FeatureValue.found = False`` is returned — no
  exception is raised and the language still appears in the output.
- ``is_uniform`` counts only languages where ``found=True``.  Languages
  where ``found=False`` are separately listed in Markdown output as
  ``— (not present)``.

Usage
-----
::

    from gobelo_grammar_toolkit.apps.feature_comparator import FeatureComparator

    fc = FeatureComparator.for_all_languages()
    table = fc.compare("noun_class.NC7.prefix")
    print(fc.to_markdown(table))

    tables = fc.compare_many([
        "noun_class.NC1.prefix",
        "extension.PASS.zone",
        "tam.TAM_PRES.form",
    ])
    print(fc.to_markdown_multi(tables))
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from gobelo_grammar_toolkit import GrammarConfig, GobeloGrammarLoader
from gobelo_grammar_toolkit.core.exceptions import GGTError

__all__ = [
    "FeatureComparator",
    "FeatureValue",
    "ComparisonTable",
    "FeatureComparatorError",
]

# ─────────────────────────────────────────────────────────────────────────────
# Exception
# ─────────────────────────────────────────────────────────────────────────────


class FeatureComparatorError(GGTError):
    """
    Raised when a feature path is structurally invalid or references an
    unknown entity type.  Distinct from ``FeatureValue.found = False``,
    which represents a missing entity in a specific language.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


# ─────────────────────────────────────────────────────────────────────────────
# Frozen output types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FeatureValue:
    """
    The value of one feature path for one language.

    Parameters
    ----------
    language : str
        The language identifier (e.g. ``"chitonga"``).
    value : Any
        The raw Python value retrieved from the grammar model (may be
        ``str``, ``int``, ``bool``, ``list``, or ``None``).
    value_str : str
        Human-readable string representation of ``value``.  Used for
        uniformity comparison and tabular display.  Empty string when
        ``found=False``.
    found : bool
        ``True`` if the entity and field exist in this language's grammar.
        ``False`` if the entity id is absent (e.g. ``extension.PASS`` for
        a stub grammar that has only ``APPL``).
    error : Optional[str]
        Non-``None`` when an unexpected error occurred during resolution
        (separate from a clean ``found=False`` absence).
    """

    language: str
    value: Any
    value_str: str
    found: bool
    error: Optional[str]


@dataclass(frozen=True)
class ComparisonTable:
    """
    Cross-language comparison result for a single feature path.

    Parameters
    ----------
    feature_path : str
        The dot-notation path that was queried.
    languages : Tuple[str, ...]
        All languages in the comparator, in the order they were provided.
    values : Dict[str, FeatureValue]
        Mapping ``language → FeatureValue`` for every language.
    unique_values : FrozenSet[str]
        Set of distinct ``value_str`` strings across all languages
        where ``found=True``.
    is_uniform : bool
        ``True`` iff ``len(unique_values) <= 1`` across all
        languages where ``found=True``.
    divergent_languages : FrozenSet[str]
        Languages whose ``value_str`` differs from the modal (most
        common) value, or languages where ``found=False``.
    """

    feature_path: str
    languages: Tuple[str, ...]
    values: Dict[str, FeatureValue]
    unique_values: FrozenSet[str]
    is_uniform: bool
    divergent_languages: FrozenSet[str]


# ─────────────────────────────────────────────────────────────────────────────
# Path router — constants and resolution logic
# ─────────────────────────────────────────────────────────────────────────────

_VALID_ENTITY_TYPES = frozenset({
    "noun_class",
    "tam",
    "extension",
    "concord",
    "metadata",
    "verb_slot",
})

_ENTITY_TYPE_ALIASES: Dict[str, str] = {
    # Allow plural and alternate spellings
    "noun_classes": "noun_class",
    "nc":           "noun_class",
    "extensions":   "extension",
    "ext":          "extension",
    "verb_slots":   "verb_slot",
    "slot":         "verb_slot",
    "tams":         "tam",
}


def _canonical_entity_type(raw: str) -> str:
    """Return the canonical entity type, resolving aliases."""
    canon = _ENTITY_TYPE_ALIASES.get(raw, raw)
    if canon not in _VALID_ENTITY_TYPES:
        raise FeatureComparatorError(
            f"Unknown entity type {raw!r}. "
            f"Valid prefixes: {sorted(_VALID_ENTITY_TYPES)}. "
            f"Path format: entity_type.entity_id.field  "
            f"(or metadata.field for 2-segment metadata paths)."
        )
    return canon


def _value_str(value: Any) -> str:
    """
    Produce a stable, human-readable string from any grammar field value.

    - Lists are rendered as comma-separated strings (sorted for stability).
    - ``None`` renders as ``""`` (empty string) rather than ``"None"``,
      so a missing optional field is visually distinct from the literal
      string ``"None"``.
    - All other types use ``str()``.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    return str(value)


def _resolve(path: str, loader: GobeloGrammarLoader) -> FeatureValue:
    """
    Resolve a dot-notation feature path against one loader.

    Returns a :class:`FeatureValue`.  Never raises; errors are captured
    in ``FeatureValue.error``.  A cleanly absent entity produces
    ``found=False, error=None``.
    """
    lang = loader.config.language

    # ── Parse segments ────────────────────────────────────────────────
    segments = path.split(".", maxsplit=2)

    if len(segments) < 2:
        return FeatureValue(
            language=lang, value=None, value_str="", found=False,
            error=f"Path {path!r} must have at least 2 segments (entity_type.field).",
        )

    raw_type = segments[0]
    try:
        entity_type = _canonical_entity_type(raw_type)
    except FeatureComparatorError as exc:
        return FeatureValue(
            language=lang, value=None, value_str="", found=False,
            error=str(exc),
        )

    # ── metadata — 2-segment path ─────────────────────────────────────
    if entity_type == "metadata":
        field_name = segments[1]
        try:
            meta = loader.get_metadata()
            if not hasattr(meta, field_name):
                return FeatureValue(
                    language=lang, value=None, value_str="", found=False,
                    error=f"GrammarMetadata has no field {field_name!r}.",
                )
            raw = getattr(meta, field_name)
            return FeatureValue(
                language=lang, value=raw,
                value_str=_value_str(raw), found=True, error=None,
            )
        except GGTError as exc:
            return FeatureValue(
                language=lang, value=None, value_str="", found=False,
                error=str(exc),
            )

    # ── All other entity types require 3 segments ─────────────────────
    if len(segments) < 3:
        return FeatureValue(
            language=lang, value=None, value_str="", found=False,
            error=(
                f"Path {path!r} must have 3 segments for entity type "
                f"{entity_type!r}: {entity_type}.entity_id.field"
            ),
        )

    entity_id  = segments[1]
    field_name = segments[2]

    try:
        raw = _fetch(entity_type, entity_id, field_name, loader)
    except _NotFound as exc:
        return FeatureValue(
            language=lang, value=None, value_str="", found=False, error=None,
        )
    except _FieldMissing as exc:
        return FeatureValue(
            language=lang, value=None, value_str="", found=False,
            error=str(exc),
        )
    except GGTError as exc:
        return FeatureValue(
            language=lang, value=None, value_str="", found=False,
            error=str(exc),
        )
    except Exception as exc:  # pragma: no cover — safety net
        return FeatureValue(
            language=lang, value=None, value_str="", found=False,
            error=f"Unexpected error: {type(exc).__name__}: {exc}",
        )

    return FeatureValue(
        language=lang, value=raw,
        value_str=_value_str(raw), found=True, error=None,
    )


# ── Private sentinel exceptions (never leave this module) ────────────────────


class _NotFound(Exception):
    """Entity id not present in the grammar."""


class _FieldMissing(Exception):
    """Entity exists but does not have the requested field."""


def _fetch(entity_type: str, entity_id: str, field_name: str,
           loader: GobeloGrammarLoader) -> Any:
    """
    Fetch the raw field value from the grammar; raise ``_NotFound`` or
    ``_FieldMissing`` for clean absence.  Any ``GGTError`` is re-raised.
    """
    if entity_type == "noun_class":
        # get_noun_class raises NounClassNotFoundError (a GGTError subclass)
        # for unknown ids — catch and re-raise as _NotFound.
        try:
            obj = loader.get_noun_class(entity_id)
        except GGTError:
            raise _NotFound()
        return _getattr_or_raise(obj, field_name)

    elif entity_type == "tam":
        markers = loader.get_tam_markers()
        obj = next((t for t in markers if t.id == entity_id), None)
        if obj is None:
            raise _NotFound()
        return _getattr_or_raise(obj, field_name)

    elif entity_type == "extension":
        exts = loader.get_extensions()
        obj = next((e for e in exts if e.id == entity_id), None)
        if obj is None:
            raise _NotFound()
        return _getattr_or_raise(obj, field_name)

    elif entity_type == "concord":
        # entity_id = concord_type, field_name = concord_key
        try:
            cs = loader.get_concords(entity_id)
        except GGTError:
            raise _NotFound()
        if field_name not in cs.entries:
            raise _NotFound()
        return cs.entries[field_name]

    elif entity_type == "verb_slot":
        slots = loader.get_verb_slots()
        obj = next((s for s in slots if s.id == entity_id), None)
        if obj is None:
            raise _NotFound()
        return _getattr_or_raise(obj, field_name)

    # Should never reach here; _canonical_entity_type guards the valid set.
    raise FeatureComparatorError(f"Unhandled entity type {entity_type!r}.")  # pragma: no cover


def _getattr_or_raise(obj: Any, field_name: str) -> Any:
    """Return ``getattr(obj, field_name)`` or raise ``_FieldMissing``."""
    if not hasattr(obj, field_name):
        raise _FieldMissing(
            f"{type(obj).__name__} has no field {field_name!r}. "
            f"Available fields: {[f for f in vars(obj) if not f.startswith('_')]}."
        )
    return getattr(obj, field_name)


# ─────────────────────────────────────────────────────────────────────────────
# FeatureComparator
# ─────────────────────────────────────────────────────────────────────────────


class FeatureComparator:
    """
    Cross-language feature comparator.

    Parameters
    ----------
    loaders : Dict[str, GobeloGrammarLoader]
        Mapping ``language_name → GobeloGrammarLoader``.  The dict order
        determines the row order in all output tables.

    Raises
    ------
    FeatureComparatorError
        If ``loaders`` is empty.

    Examples
    --------
    >>> fc = FeatureComparator.for_all_languages()
    >>> table = fc.compare("extension.PASS.zone")
    >>> print(fc.to_markdown(table))

    >>> tables = fc.compare_many([
    ...     "noun_class.NC7.prefix",
    ...     "tam.TAM_PRES.form",
    ...     "metadata.grammar_version",
    ... ])
    >>> print(fc.to_markdown_multi(tables))
    """

    def __init__(self, loaders: Dict[str, GobeloGrammarLoader]) -> None:
        if not loaders:
            raise FeatureComparatorError(
                "FeatureComparator requires at least one loader. "
                "Pass a non-empty Dict[str, GobeloGrammarLoader]."
            )
        # Preserve insertion order
        self._loaders: Dict[str, GobeloGrammarLoader] = dict(loaders)
        self._languages: Tuple[str, ...] = tuple(self._loaders.keys())

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def for_all_languages(cls) -> "FeatureComparator":
        """
        Convenience factory: build one loader per supported language and
        return a :class:`FeatureComparator` covering all 7 languages.

        The language list is discovered via
        ``GobeloGrammarLoader.list_supported_languages()`` so this method
        does not hardcode any language names.

        Returns
        -------
        FeatureComparator

        Examples
        --------
        >>> fc = FeatureComparator.for_all_languages()
        >>> len(fc.languages)
        7
        """
        # Use any language to discover the full supported list
        sentinel = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
        supported = sentinel.list_supported_languages()
        loaders = {
            lang: GobeloGrammarLoader(GrammarConfig(language=lang))
            for lang in supported
        }
        return cls(loaders)

    # ------------------------------------------------------------------
    # Core comparison
    # ------------------------------------------------------------------

    def compare(self, feature_path: str) -> ComparisonTable:
        """
        Compare one feature path across all loaded languages.

        Parameters
        ----------
        feature_path : str
            Dot-notation path, e.g. ``"noun_class.NC7.prefix"``,
            ``"extension.PASS.zone"``, ``"metadata.grammar_version"``.

        Returns
        -------
        ComparisonTable

        Raises
        ------
        FeatureComparatorError
            If the path has an unknown ``entity_type`` prefix.  (Individual
            per-language lookup failures are captured in
            ``FeatureValue.error`` and never raise here.)

        Examples
        --------
        >>> table = fc.compare("tam.TAM_PRES.form")
        >>> table.is_uniform
        True
        """
        # Validate the entity_type segment up-front so a bad prefix raises
        # immediately rather than appearing silently in every FeatureValue.
        segments = feature_path.split(".", maxsplit=1)
        if segments:
            _canonical_entity_type(segments[0])  # raises on bad prefix

        values: Dict[str, FeatureValue] = {}
        for lang, loader in self._loaders.items():
            values[lang] = _resolve(feature_path, loader)

        return self._build_table(feature_path, values)

    def compare_many(
        self, feature_paths: List[str]
    ) -> Dict[str, ComparisonTable]:
        """
        Compare multiple feature paths, returning one
        :class:`ComparisonTable` per path.

        Parameters
        ----------
        feature_paths : List[str]
            Ordered list of dot-notation paths.

        Returns
        -------
        Dict[str, ComparisonTable]
            Keys are the original path strings; values are comparison
            tables in the same order as ``feature_paths``.

        Raises
        ------
        FeatureComparatorError
            On the first path with an unknown entity type prefix.

        Examples
        --------
        >>> tables = fc.compare_many([
        ...     "noun_class.NC1.prefix",
        ...     "extension.PASS.zone",
        ... ])
        """
        return {path: self.compare(path) for path in feature_paths}

    # ------------------------------------------------------------------
    # Table construction
    # ------------------------------------------------------------------

    def _build_table(
        self, feature_path: str, values: Dict[str, FeatureValue]
    ) -> ComparisonTable:
        """Compute derived fields and construct the frozen ComparisonTable."""
        # Unique value_str values across languages where found=True
        found_strs = [
            fv.value_str for fv in values.values() if fv.found
        ]
        unique_values: FrozenSet[str] = frozenset(found_strs)
        is_uniform = len(unique_values) <= 1

        # Determine the modal (most common) value_str
        modal: Optional[str] = None
        if found_strs:
            from collections import Counter
            modal = Counter(found_strs).most_common(1)[0][0]

        # Divergent: found=False OR value_str differs from modal
        divergent: FrozenSet[str] = frozenset(
            lang
            for lang, fv in values.items()
            if not fv.found or (modal is not None and fv.value_str != modal)
        )

        return ComparisonTable(
            feature_path=feature_path,
            languages=self._languages,
            values=values,
            unique_values=unique_values,
            is_uniform=is_uniform,
            divergent_languages=divergent,
        )

    # ------------------------------------------------------------------
    # Export: Markdown (single table)
    # ------------------------------------------------------------------

    def to_markdown(self, table: ComparisonTable) -> str:
        """
        Render one :class:`ComparisonTable` as a Markdown pipe table.

        Columns: ``Language``, the feature path (truncated to 40 chars
        if necessary), ``Status``.  Each row shows the language, its
        value (or ``— (not present)`` / ``⚠ <error>``), and a ``✗``
        divergence marker.

        A summary line is appended:

        - ``✓ Feature is uniform across all N languages.``
        - ``✗ Feature diverges in N language(s): <list>.``

        Parameters
        ----------
        table : ComparisonTable

        Returns
        -------
        str
        """
        path_header = _truncate(table.feature_path, 40)
        lines: List[str] = []

        # Header
        lines.append(f"| Language | {path_header} | Status |")
        lines.append("|---|---|---|")

        # Rows
        for lang in table.languages:
            fv = table.values[lang]
            if fv.error:
                val_col = f"⚠ {fv.error[:60]}"
            elif not fv.found:
                val_col = "— *(not present)*"
            else:
                val_col = _escape_md(fv.value_str) or "*(empty)*"

            diverges = "✗" if lang in table.divergent_languages else ""
            lines.append(f"| {lang} | {val_col} | {diverges} |")

        # Summary
        n_found = sum(1 for fv in table.values.values() if fv.found)
        if table.is_uniform:
            lines.append(
                f"\n> ✓ Feature is uniform across all {n_found} "
                f"language{'s' if n_found != 1 else ''} where present."
            )
        else:
            div_list = ", ".join(sorted(table.divergent_languages))
            lines.append(
                f"\n> ✗ Feature diverges in "
                f"{len(table.divergent_languages)} language(s): {div_list}."
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Export: Markdown (multi-table)
    # ------------------------------------------------------------------

    def to_markdown_multi(
        self, tables: Dict[str, ComparisonTable]
    ) -> str:
        """
        Render multiple :class:`ComparisonTable` objects as a single
        Markdown document.

        Produces a combined table with one row per language, one column
        per feature path, plus a ``DIVERGES`` column that lists paths
        that differ for that language.

        Parameters
        ----------
        tables : Dict[str, ComparisonTable]
            Ordered dict of ``{feature_path: ComparisonTable}``.

        Returns
        -------
        str

        Examples
        --------
        >>> tables = fc.compare_many(["noun_class.NC7.prefix", "extension.PASS.zone"])
        >>> print(fc.to_markdown_multi(tables))
        """
        if not tables:
            return "_No feature paths provided._"

        paths = list(tables.keys())

        # ── Header ────────────────────────────────────────────────────
        header_cols = ["| Language"]
        for p in paths:
            header_cols.append(_truncate(p, 30))
        header_cols.append("DIVERGES |")
        lines = [" | ".join(header_cols)]

        sep_cols = ["|---"] * (len(paths) + 2)
        lines.append("".join(sep_cols) + "|")

        # ── Data rows ─────────────────────────────────────────────────
        for lang in self._languages:
            row = [f"| {lang}"]
            diverging_paths: List[str] = []
            for p in paths:
                t = tables[p]
                fv = t.values.get(lang)
                if fv is None:
                    cell = "*n/a*"
                elif fv.error:
                    cell = f"⚠ err"
                elif not fv.found:
                    cell = "—"
                else:
                    cell = _escape_md(fv.value_str) or "*(empty)*"

                if fv is not None and lang in t.divergent_languages:
                    diverging_paths.append(_truncate(p, 20))
                row.append(cell)

            diverges_col = ", ".join(diverging_paths) if diverging_paths else ""
            row.append(f"{diverges_col} |")
            lines.append(" | ".join(row))

        # ── Summary block ─────────────────────────────────────────────
        lines.append("")
        uniform = [p for p, t in tables.items() if t.is_uniform]
        diverges = [p for p, t in tables.items() if not t.is_uniform]
        if uniform:
            lines.append(
                f"> ✓ Uniform across all languages: "
                + ", ".join(f"`{p}`" for p in uniform)
            )
        if diverges:
            lines.append(
                f"> ✗ Diverges across languages: "
                + ", ".join(f"`{p}`" for p in diverges)
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Export: CSV (single table)
    # ------------------------------------------------------------------

    def to_csv(self, table: ComparisonTable) -> str:
        """
        Render one :class:`ComparisonTable` as RFC 4180 CSV.

        Columns: ``language``, ``value``, ``found``, ``diverges``,
        ``error``.

        Parameters
        ----------
        table : ComparisonTable

        Returns
        -------
        str
        """
        buf = io.StringIO()
        writer = csv.writer(buf, dialect="excel", lineterminator="\n")
        writer.writerow(["language", "value", "found", "diverges", "error"])

        for lang in table.languages:
            fv = table.values[lang]
            writer.writerow([
                lang,
                fv.value_str if fv.found else "",
                str(fv.found),
                str(lang in table.divergent_languages),
                fv.error or "",
            ])

        return buf.getvalue()

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def languages(self) -> Tuple[str, ...]:
        """Tuple of all language names in the comparator, in insertion order."""
        return self._languages

    @property
    def loader_count(self) -> int:
        """Number of language loaders held by this comparator."""
        return len(self._loaders)

    def get_loader(self, language: str) -> GobeloGrammarLoader:
        """
        Return the loader for a specific language.

        Parameters
        ----------
        language : str

        Returns
        -------
        GobeloGrammarLoader

        Raises
        ------
        FeatureComparatorError
            If the language is not in this comparator.
        """
        if language not in self._loaders:
            raise FeatureComparatorError(
                f"Language {language!r} is not in this comparator. "
                f"Available: {sorted(self._loaders)}."
            )
        return self._loaders[language]


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────


def _truncate(s: str, max_len: int) -> str:
    """Truncate a string to ``max_len`` chars, adding ``…`` if cut."""
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _escape_md(s: str) -> str:
    """Escape Markdown pipe characters and backticks within a table cell."""
    return s.replace("|", "\\|").replace("`", "\\`")
