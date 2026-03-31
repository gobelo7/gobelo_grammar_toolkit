"""
core/exceptions.py
==================
Typed exception hierarchy for the Gobelo (Bantu) Grammar Toolkit (GGT).

All exceptions inherit from ``GGTError``, which itself inherits from the
built-in ``Exception``.  This means callers can catch the entire family with
a single ``except GGTError`` clause, or catch specific subtypes for fine-
grained error handling.

Every exception carries:

* A ``message`` attribute — a linguist-readable English explanation of what
  went wrong, suitable for display in a CLI tool or log file.
* Additional structured attributes where appropriate (e.g.
  ``SchemaValidationError`` carries the lists of missing and extra YAML keys
  so that a schema-migration tool can act on them programmatically).

Usage example
-------------
>>> try:
...     loader = GobeloGrammarLoader(config=GrammarConfig(language="namwanga"))
... except LanguageNotFoundError as e:
...     print(e.message)
...     print(f"Supported languages: {e.available_languages}")

Design principles
-----------------
* **Never use bare** ``raise Exception(...)`` anywhere in the toolkit — always
  raise a specific ``GGTError`` subclass.
* **Never swallow errors silently** — if something is structurally wrong with
  a YAML file or a caller's request, raise immediately rather than returning
  a partial or empty result.
* **Distinguish data errors from programming errors** — all ``GGTError``
  subclasses represent *expected* failure modes (bad YAML, unknown language,
  etc.).  Bugs in the toolkit itself surface as ordinary Python exceptions
  (``TypeError``, ``AssertionError``, etc.) and are *not* wrapped here.

Importable from the public package surface
------------------------------------------
All exceptions are re-exported from ``gobelo_grammar_toolkit.exceptions``
(the package-level shim) so that downstream apps do not need to import from
``gobelo_grammar_toolkit.core.exceptions`` directly.
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid a circular import at runtime: VerifyFlag is defined in models.py,
    # which does not import from exceptions.py.  The TYPE_CHECKING guard means
    # this import only happens during static analysis (mypy, pyright).
    from gobelo_grammar_toolkit.core.models import VerifyFlag

__all__ = [
    "GGTError",
    "LanguageNotFoundError",
    "SchemaValidationError",
    "VersionIncompatibleError",
    "UnverifiedFormError",
    "ConcordTypeNotFoundError",
    "NounClassNotFoundError",
]


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class GGTError(Exception):
    """
    Base class for all Gobelo Grammar Toolkit errors.

    Catching ``GGTError`` will catch every error originating from the GGT
    library.  Catching a specific subclass will catch only that error type.

    All ``GGTError`` subclasses carry a ``message`` attribute that contains a
    linguist-readable explanation of the problem.  The ``args[0]`` attribute
    (used by Python's default ``str(exception)`` rendering) is set to the same
    string, so standard logging and traceback formatting work as expected.

    Parameters
    ----------
    message : str
        A clear, human-readable explanation of what went wrong.  Should be
        written so that a linguist with no Python experience can understand
        it and take remedial action.

    Examples
    --------
    Catching all GGT errors:

    >>> try:
    ...     loader.get_noun_class("NC99")
    ... except GGTError as e:
    ...     print(f"Grammar error: {e.message}")
    """

    def __init__(self, message: str) -> None:
        self.message: str = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.message!r})"


# ---------------------------------------------------------------------------
# Language registry errors
# ---------------------------------------------------------------------------


class LanguageNotFoundError(GGTError):
    """
    Raised when the requested language identifier is not present in the
    embedded language registry.

    This error occurs when a ``GrammarConfig`` is constructed (or a loader
    is initialised) with a ``language`` value that does not match any key in
    the GGT language registry.  Common causes:

    * A typo in the language name (e.g. ``"chitona"`` instead of
      ``"chitonga"``).
    * Requesting a language that has not yet been added to the toolkit.
    * Using an ISO code instead of the canonical short name.

    Parameters
    ----------
    language : str
        The language identifier that was requested but not found.
    available_languages : List[str]
        The list of language identifiers currently registered in the
        embedded registry, provided so the caller can suggest alternatives.
    message : Optional[str]
        Override the auto-generated message.  If ``None``, a standard
        message is constructed from ``language`` and ``available_languages``.

    Examples
    --------
    >>> try:
    ...     loader = GobeloGrammarLoader(
    ...         config=GrammarConfig(language="namwanga")
    ...     )
    ... except LanguageNotFoundError as e:
    ...     print(e.message)
    ...     # "Language 'namwanga' is not in the GGT registry.
    ...     #  Supported languages: chitonga, chibemba, chinyanja, ..."
    ...     print(e.available_languages)
    ...     # ['chitonga', 'chibemba', 'chinyanja', 'luvale', 'kaonde',
    ...     #  'silozi', 'lunda']
    """

    def __init__(
        self,
        language: str,
        available_languages: List[str],
        message: Optional[str] = None,
    ) -> None:
        self.language: str = language
        self.available_languages: List[str] = list(available_languages)

        if message is None:
            names = ", ".join(sorted(available_languages))
            message = (
                f"Language '{language}' is not in the GGT registry.  "
                f"Supported languages: {names}.  "
                f"Check the spelling of the language name or consult the "
                f"language registry documentation."
            )
        super().__init__(message)


# ---------------------------------------------------------------------------
# Schema validation errors
# ---------------------------------------------------------------------------


class SchemaValidationError(GGTError):
    """
    Raised when a YAML grammar file fails structural schema validation.

    This error is raised by the loader's schema validator before any
    linguistic data is parsed.  It indicates that the YAML file does not
    conform to the current GGT schema — either because required top-level
    keys are absent, or because unexpected extra keys are present that the
    loader does not know how to handle.

    This error is most commonly encountered when:

    * An externally-supplied ``override_path`` YAML file was authored without
      following the GGT schema.
    * A grammar YAML file has been manually edited in a way that broke its
      structure.
    * A schema migration (F-12) was run incompletely, leaving the file in a
      mixed-version state.

    Parameters
    ----------
    missing_keys : List[str]
        Top-level (or nested) YAML keys that the schema requires but that
        are absent from the file, e.g. ``["metadata", "noun_classes"]``.
        Each key is expressed as a dot-notation path,
        e.g. ``"metadata.grammar_version"``.
    extra_keys : List[str]
        Keys present in the YAML file that the schema does not recognise.
        These may indicate a forward-compatibility issue (the YAML was
        authored for a newer schema version) or a typo.
    yaml_path : Optional[str]
        Filesystem path to the YAML file that failed validation, if known.
        ``None`` when validating an in-memory structure.
    message : Optional[str]
        Override the auto-generated message.

    Examples
    --------
    >>> try:
    ...     loader = GobeloGrammarLoader(
    ...         config=GrammarConfig(
    ...             language="chitonga",
    ...             override_path="/path/to/broken.yaml",
    ...         )
    ...     )
    ... except SchemaValidationError as e:
    ...     print(e.message)
    ...     print("Missing:", e.missing_keys)
    ...     print("Extra:  ", e.extra_keys)
    """

    def __init__(
        self,
        missing_keys: List[str],
        extra_keys: List[str],
        yaml_path: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.missing_keys: List[str] = list(missing_keys)
        self.extra_keys: List[str] = list(extra_keys)
        self.yaml_path: Optional[str] = yaml_path

        if message is None:
            location = f" in '{yaml_path}'" if yaml_path else ""
            parts: List[str] = [
                f"Grammar YAML schema validation failed{location}."
            ]
            if missing_keys:
                parts.append(
                    f"  Required keys that are absent: "
                    f"{', '.join(missing_keys)}."
                )
            if extra_keys:
                parts.append(
                    f"  Unrecognised keys (possible typos or newer-schema "
                    f"fields): {', '.join(extra_keys)}."
                )
            parts.append(
                "  Run 'ggt validate <path>' for a detailed report, or use "
                "the schema migration tool (F-12) to update the file."
            )
            message = "  ".join(parts)
        super().__init__(message)


# ---------------------------------------------------------------------------
# Version compatibility errors
# ---------------------------------------------------------------------------


class VersionIncompatibleError(GGTError):
    """
    Raised when the grammar YAML's declared version range is incompatible
    with the running GGT loader version.

    Every GGT-conformant YAML file declares ``min_loader_version`` and
    ``max_loader_version`` in its ``metadata`` block.  The loader checks
    these values against its own version at initialisation time and raises
    this exception if the running loader falls outside the declared window.

    There are two flavours:

    * **Too old** — the YAML requires a newer loader than is installed.
      The grammar was probably authored for a future version of the toolkit.
    * **Too new** — the loader is newer than the YAML's maximum supported
      version.  The YAML was probably authored for an older schema and has
      not yet been migrated.

    Parameters
    ----------
    yaml_version : str
        The ``grammar_version`` declared in the YAML file's ``metadata``
        block, e.g. ``"2.0.0"``.
    loader_version : str
        The version of the running GGT loader, e.g. ``"1.3.0"``.
    min_loader_version : str
        The ``min_loader_version`` declared in the YAML, e.g. ``"1.5.0"``.
    max_loader_version : str
        The ``max_loader_version`` declared in the YAML, e.g. ``"3.0.0"``.
    yaml_path : Optional[str]
        Filesystem path to the incompatible YAML file, if known.
    message : Optional[str]
        Override the auto-generated message.

    Examples
    --------
    >>> try:
    ...     loader = GobeloGrammarLoader(
    ...         config=GrammarConfig(language="luvale", override_path="/p/luvale_v2.yaml")
    ...     )
    ... except VersionIncompatibleError as e:
    ...     print(e.message)
    ...     print(f"YAML grammar version : {e.yaml_version}")
    ...     print(f"Running loader version: {e.loader_version}")
    """

    def __init__(
        self,
        yaml_version: str,
        loader_version: str,
        min_loader_version: str,
        max_loader_version: str,
        yaml_path: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.yaml_version: str = yaml_version
        self.loader_version: str = loader_version
        self.min_loader_version: str = min_loader_version
        self.max_loader_version: str = max_loader_version
        self.yaml_path: Optional[str] = yaml_path

        if message is None:
            location = f" ('{yaml_path}')" if yaml_path else ""
            message = (
                f"Grammar YAML{location} (grammar_version={yaml_version!r}) "
                f"is not compatible with the running GGT loader "
                f"(version={loader_version!r}).  "
                f"The YAML requires a loader in the range "
                f"[{min_loader_version}, {max_loader_version}].  "
                f"Either upgrade the GGT package to a compatible version "
                f"or run the schema migration tool to update the YAML file: "
                f"'ggt migrate <path> --to <target_version>'."
            )
        super().__init__(message)


# ---------------------------------------------------------------------------
# Strict-mode / VERIFY errors
# ---------------------------------------------------------------------------


class UnverifiedFormError(GGTError):
    """
    Raised in ``strict_mode`` when one or more VERIFY-flagged forms are
    present in the loaded grammar YAML.

    When ``GrammarConfig(strict_mode=True)`` is set, the loader refuses to
    return data from a grammar that contains any unresolved ``# VERIFY:``
    annotations.  This mode is recommended for production pipelines where
    data quality must be guaranteed.

    In non-strict mode (the default), the same condition results in a
    ``warnings.warn()`` call but does not raise an exception.

    The ``flags`` attribute gives application code direct access to the
    list of unresolved flags, which can be forwarded to the VERIFY Flag
    Resolver workflow (F-06).

    Parameters
    ----------
    flags : List[VerifyFlag]
        The complete list of unresolved ``VerifyFlag`` objects found in the
        grammar.  Each flag carries the field path, the current uncertain
        value, and the original ``# VERIFY:`` comment text.
    language : str
        The language for which the flags were found, e.g. ``"kaonde"``.
    message : Optional[str]
        Override the auto-generated message.

    Examples
    --------
    >>> try:
    ...     loader = GobeloGrammarLoader(
    ...         config=GrammarConfig(language="kaonde", strict_mode=True)
    ...     )
    ... except UnverifiedFormError as e:
    ...     print(e.message)
    ...     for flag in e.flags:
    ...         print(f"  [{flag.field_path}] {flag.note}")
    """

    def __init__(
        self,
        flags: "List[VerifyFlag]",
        language: str,
        message: Optional[str] = None,
    ) -> None:
        self.flags: "List[VerifyFlag]" = list(flags)
        self.language: str = language

        if message is None:
            count = len(flags)
            noun = "flag" if count == 1 else "flags"
            message = (
                f"Grammar for '{language}' contains {count} unresolved "
                f"VERIFY {noun} and strict_mode is enabled.  "
                f"Resolve all VERIFY annotations before using this grammar "
                f"in a production context, or set strict_mode=False to "
                f"proceed with a warning.  Use 'ggt verify-flags {language}' "
                f"to list all unresolved flags, or use the F-06 VERIFY Flag "
                f"Resolver workflow to address them systematically."
            )
        super().__init__(message)


# ---------------------------------------------------------------------------
# Lookup errors
# ---------------------------------------------------------------------------


class ConcordTypeNotFoundError(GGTError):
    """
    Raised when a caller requests a concord type that is not present in the
    loaded grammar.

    This error is raised by ``GobeloGrammarLoader.get_concords(concord_type)``
    when the requested ``concord_type`` string does not match any key in the
    ``concord_systems`` section of the grammar YAML.  Not all concord types
    exist in all languages (e.g. some languages lack a distinct possessive
    concord), so this error is an expected and recoverable condition.

    Parameters
    ----------
    concord_type : str
        The concord type identifier that was requested but not found, e.g.
        ``"demonstrative_concords_distal"``.
    available_types : List[str]
        The list of concord type identifiers that *are* available in this
        grammar.  Provided so the caller can suggest alternatives or
        enumerate valid options.
    language : str
        The language for which the lookup was attempted, e.g.
        ``"silozi"``.
    message : Optional[str]
        Override the auto-generated message.

    Examples
    --------
    >>> try:
    ...     cs = loader.get_concords("demonstrative_concords_distal")
    ... except ConcordTypeNotFoundError as e:
    ...     print(e.message)
    ...     print("Available types:", e.available_types)
    """

    def __init__(
        self,
        concord_type: str,
        available_types: List[str],
        language: str,
        message: Optional[str] = None,
    ) -> None:
        self.concord_type: str = concord_type
        self.available_types: List[str] = list(available_types)
        self.language: str = language

        if message is None:
            names = ", ".join(sorted(available_types))
            message = (
                f"Concord type '{concord_type}' is not defined in the "
                f"'{language}' grammar.  "
                f"Available concord types: {names}.  "
                f"Use GobeloGrammarLoader.get_all_concord_types() to "
                f"enumerate the concord types defined for this language."
            )
        super().__init__(message)


class NounClassNotFoundError(GGTError):
    """
    Raised when a caller requests a noun class that is not defined in the
    loaded grammar.

    This error is raised by ``GobeloGrammarLoader.get_noun_class(nc_id)``
    when the requested noun-class identifier does not match any entry in the
    ``noun_classes`` section of the grammar YAML.

    Note that noun class inventories differ across languages: NC15 (the
    infinitival/locative class in some languages) may not exist in others,
    and class numbering conventions can vary.  Always enumerate available
    classes via ``get_noun_classes()`` rather than assuming a particular
    class exists in a given language.

    Parameters
    ----------
    nc_id : str
        The noun-class identifier that was requested but not found, e.g.
        ``"NC17"``.
    available_classes : List[str]
        The list of noun-class identifiers that *are* defined in this
        grammar, e.g. ``["NC1", "NC2", "NC3", ..., "NC14"]``.
    language : str
        The language for which the lookup was attempted.
    message : Optional[str]
        Override the auto-generated message.

    Examples
    --------
    >>> try:
    ...     nc = loader.get_noun_class("NC17")
    ... except NounClassNotFoundError as e:
    ...     print(e.message)
    ...     print("Available classes:", e.available_classes)
    """

    def __init__(
        self,
        nc_id: str,
        available_classes: List[str],
        language: str,
        message: Optional[str] = None,
    ) -> None:
        self.nc_id: str = nc_id
        self.available_classes: List[str] = list(available_classes)
        self.language: str = language

        if message is None:
            names = ", ".join(sorted(available_classes))
            message = (
                f"Noun class '{nc_id}' is not defined in the "
                f"'{language}' grammar.  "
                f"Defined classes: {names}.  "
                f"Use GobeloGrammarLoader.get_noun_classes() to enumerate "
                f"all noun classes for this language, including inactive ones "
                f"(pass active_only=False)."
            )
        super().__init__(message)
