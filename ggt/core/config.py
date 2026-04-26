"""
core/config.py
==============
Configuration dataclass for the Gobelo (Bantu) Grammar Toolkit (GGT).

``GrammarConfig`` is the single object passed to ``GobeloGrammarLoader`` at
instantiation.  It carries every setting that controls *how* a grammar file
is located, parsed, and enforced — but contains no grammar data itself.

Design principles
-----------------
* **Value object** — ``GrammarConfig`` describes intent, not state.  It is
  populated once and treated as read-only after construction.  The ``@dataclass``
  decorator is used (not ``frozen=True``) to match the Part 4 specification,
  but callers should not mutate a config object after passing it to a loader.
* **Fail early** — ``__post_init__`` validates every field immediately, so
  invalid configurations are caught at instantiation time rather than surfacing
  as obscure failures deep in the loading pipeline.
* **No grammar knowledge** — this module imports nothing from the rest of the
  GGT core.  It is safe to import in isolation (e.g. in a CLI entrypoint or
  REST layer) without triggering any YAML loading.
* **Normalisation** — ``language`` is normalised to lowercase and stripped of
  whitespace so that ``GrammarConfig(language="chiTonga")`` and
  ``GrammarConfig(language="chitonga")`` are equivalent.

What ``GrammarConfig`` does NOT validate
----------------------------------------
* Whether ``language`` is present in the embedded registry — the registry is
  owned by ``core/registry.py``; the loader performs this check.
* Whether the file at ``override_path`` actually exists — path existence is a
  runtime concern checked by the loader, not a configuration concern.
* Whether the ``schema_version`` exists in ``SCHEMA_REGISTRY`` — that look-up
  belongs to ``core/validator.py``.

These separations keep ``config.py`` importable without any I/O side-effects.

Usage
-----
Standard load (embedded YAML):

>>> cfg = GrammarConfig(language="chitonga")
>>> cfg.language
'chitonga'

With external override:

>>> cfg = GrammarConfig(
...     language="chitonga",
...     override_path="/research/custom_chitonga.yaml",
... )

Strict mode (raise on any unverified form in the grammar):

>>> cfg = GrammarConfig(language="kaonde", strict_mode=True)

Pinned schema version (validate against schema 1.0 even if 1.1 is latest):

>>> cfg = GrammarConfig(language="luvale", schema_version="1.0.0")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

__all__ = ["GrammarConfig"]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Semantic versioning pattern: MAJOR.MINOR.PATCH — each component is one or
# more decimal digits.  Pre-release suffixes (1.0.0-alpha) are intentionally
# excluded; the GGT uses plain SemVer only.
_SEMVER_RE: re.Pattern[str] = re.compile(r"^\d+\.\d+\.\d+$")

# Minimum viable language identifier: at least two characters, only letters,
# digits, underscores, and hyphens.  This rejects obvious non-identifiers
# (empty string, path separators, shell metacharacters) while remaining
# permissive enough for any real language name slug.
_LANGUAGE_ID_RE: re.Pattern[str] = re.compile(r"^[a-z0-9][a-z0-9_\-]{1,}$")


# ---------------------------------------------------------------------------
# GrammarConfig
# ---------------------------------------------------------------------------


@dataclass
class GrammarConfig:
    """
    Configuration for ``GobeloGrammarLoader``.

    Populate this object and pass it to ``GobeloGrammarLoader`` to control
    which grammar file is loaded, how strictly it is validated, and how the
    loader behaves at runtime.

    Mandatory fields
    ----------------
    language : str
        Canonical language identifier.  Must match a key in the embedded
        language registry (see ``core/registry.py``).  Case-insensitive;
        normalised to lowercase on construction.

        Supported values (v1.0): ``"chitonga"``, ``"chibemba"``,
        ``"chinyanja"``, ``"luvale"``, ``"kaonde"``, ``"silozi"``,
        ``"lunda"``.

    Optional fields
    ---------------
    override_path : Optional[str]
        Absolute or relative path to an external YAML file that replaces
        the embedded grammar for ``language``.  When provided the file
        *must* pass full schema validation before the loader accepts it.
        Useful for research grammars and draft revisions that have not yet
        been merged into the package.
        Default: ``None`` (use the embedded file).

    strict_mode : bool
        When ``True``, the loader raises ``UnverifiedFormError`` if the
        grammar contains any unresolved ``VERIFY:`` annotations.  This is
        appropriate for production NLP pipelines where data quality must be
        guaranteed.
        When ``False`` (default), unresolved VERIFY annotations generate
        a ``GGTWarning`` but do not block loading.

    schema_version : Optional[str]
        Pin validation to a specific GGT schema version (e.g. ``"1.0.0"``).
        When ``None`` (default), the validator uses the latest known schema.
        Pinning is useful when an external YAML was authored for an older
        schema and should not be checked against newer optional-field
        requirements.
        Must be a valid ``MAJOR.MINOR.PATCH`` string if provided.

    locale : str
        BCP-47-style locale code for error messages and display labels,
        e.g. ``"en"`` or ``"en-GB"``.  Only ``"en"`` is fully supported
        in v1.0; other values are accepted for forward-compatibility but
        will silently fall back to English until translations are added.
        Default: ``"en"``.

    cache : bool
        When ``True`` (default), the loader caches the fully-parsed grammar
        object in memory after the first load.  Subsequent calls to any
        ``get_*()`` method return cached data without re-parsing the YAML.
        Set to ``False`` only when memory is tightly constrained or during
        testing with frequently-replaced grammar files.

    Raises
    ------
    ValueError
        If ``language`` is empty or contains invalid characters after
        normalisation.
    ValueError
        If ``override_path`` is an empty string (``None`` is allowed;
        an explicit empty string signals a likely programmer error).
    ValueError
        If ``schema_version`` is provided but does not match the
        ``MAJOR.MINOR.PATCH`` semver format.
    ValueError
        If ``locale`` is empty.

    Examples
    --------
    Minimal configuration — load the embedded chiTonga grammar:

    >>> cfg = GrammarConfig(language="chitonga")
    >>> cfg.language
    'chitonga'
    >>> cfg.strict_mode
    False
    >>> cfg.cache
    True

    All options — external YAML, strict quality checks, pinned schema:

    >>> cfg = GrammarConfig(
    ...     language="kaonde",
    ...     override_path="/data/kaonde_revised.yaml",
    ...     strict_mode=True,
    ...     schema_version="1.0.0",
    ...     locale="en",
    ...     cache=False,
    ... )
    >>> cfg.language
    'kaonde'
    >>> cfg.schema_version
    '1.0.0'

    Case-insensitive language name:

    >>> cfg = GrammarConfig(language="chiTonga")
    >>> cfg.language   # normalised to lowercase
    'chitonga'
    """

    # ------------------------------------------------------------------
    # Fields (match the Part 4 specification exactly)
    # ------------------------------------------------------------------

    language: str
    """
    Canonical language identifier, normalised to lowercase.
    Must match a key in the embedded language registry.
    """

    override_path: Optional[str] = None
    """
    Path to an external YAML grammar file.  ``None`` uses the embedded file.
    Path existence is validated at load time, not at config creation time.
    """

    strict_mode: bool = False
    """
    When ``True``, raise ``UnverifiedFormError`` on any unresolved VERIFY flag.
    When ``False``, emit a ``GGTWarning`` only.
    """

    schema_version: Optional[str] = None
    """
    Pin schema validation to this exact version.  ``None`` means "use latest".
    Must be a ``MAJOR.MINOR.PATCH`` string if provided.
    """

    locale: str = "en"
    """
    Locale code for display and error messages.  Only ``"en"`` is fully
    supported in v1.0.
    """

    cache: bool = True
    """
    Cache the parsed grammar in memory after first load.
    """

    # ------------------------------------------------------------------
    # Post-construction validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """
        Validate and normalise all fields immediately after construction.

        Called automatically by the dataclass machinery.  Raises
        ``ValueError`` for any field that fails validation so that the
        problem is surfaced at the earliest possible point — the moment the
        config object is created.

        Raises
        ------
        ValueError
            See class docstring for the full list of conditions.
        """
        self._validate_language()
        self._validate_override_path()
        self._validate_schema_version()
        self._validate_locale()

    # ------------------------------------------------------------------
    # Per-field validators  (private)
    # ------------------------------------------------------------------

    def _validate_language(self) -> None:
        """
        Normalise ``language`` to lowercase and verify its format.

        Raises
        ------
        ValueError
            If the normalised identifier is empty or contains characters
            that are not letters, digits, hyphens, or underscores.
        """
        if not isinstance(self.language, str):
            raise ValueError(
                f"GrammarConfig.language must be a str, "
                f"got {type(self.language).__name__!r}."
            )

        # Normalise first: strip whitespace, convert to lowercase.
        # Using object.__setattr__ is not required for a non-frozen dataclass,
        # but is explicit about intent.
        self.language = self.language.strip().lower()

        if not self.language:
            raise ValueError(
                "GrammarConfig.language must not be empty.  "
                "Provide a canonical language identifier such as "
                "'chitonga', 'chibemba', or 'chinyanja'."
            )

        if not _LANGUAGE_ID_RE.match(self.language):
            raise ValueError(
                f"GrammarConfig.language {self.language!r} contains invalid "
                f"characters.  Language identifiers must be at least two "
                f"characters long and contain only lowercase letters, digits, "
                f"hyphens, and underscores.  "
                f"Examples: 'chitonga', 'chibemba', 'chinyanja'."
            )

    def _validate_override_path(self) -> None:
        """
        Reject an explicitly-empty ``override_path`` string.

        ``None`` is the correct way to signal "no override"; an empty string
        most likely indicates a bug in the calling code (e.g. a variable that
        was never set).  Path existence is checked by the loader, not here.

        Raises
        ------
        ValueError
            If ``override_path`` is an empty or whitespace-only string.
        """
        if self.override_path is None:
            return

        if not isinstance(self.override_path, str):
            raise ValueError(
                f"GrammarConfig.override_path must be a str or None, "
                f"got {type(self.override_path).__name__!r}."
            )

        stripped = self.override_path.strip()
        if not stripped:
            raise ValueError(
                "GrammarConfig.override_path must not be an empty string.  "
                "Pass None to use the embedded grammar file, or provide a "
                "valid filesystem path to a YAML grammar override."
            )

        # Store the stripped version to avoid leading/trailing whitespace
        # causing subtle path-resolution failures on some operating systems.
        self.override_path = stripped

    def _validate_schema_version(self) -> None:
        """
        Verify that ``schema_version`` matches ``MAJOR.MINOR.PATCH`` format.

        The schema version is optional.  When provided it must be a valid
        semantic version string so that ``core/validator.py`` can look it
        up in ``SCHEMA_REGISTRY`` without ambiguity.

        Raises
        ------
        ValueError
            If ``schema_version`` is provided but is not a valid
            ``MAJOR.MINOR.PATCH`` string.
        """
        if self.schema_version is None:
            return

        if not isinstance(self.schema_version, str):
            raise ValueError(
                f"GrammarConfig.schema_version must be a str or None, "
                f"got {type(self.schema_version).__name__!r}."
            )

        stripped = self.schema_version.strip()
        if not stripped:
            raise ValueError(
                "GrammarConfig.schema_version must not be an empty string.  "
                "Pass None to use the latest schema version, or provide a "
                "version string in MAJOR.MINOR.PATCH format, e.g. '1.0.0'."
            )

        if not _SEMVER_RE.match(stripped):
            raise ValueError(
                f"GrammarConfig.schema_version {stripped!r} is not a valid "
                f"semantic version.  Expected MAJOR.MINOR.PATCH format where "
                f"each component is a non-negative integer, e.g. '1.0.0' or "
                f"'2.1.3'.  Pre-release suffixes are not supported."
            )

        self.schema_version = stripped

    def _validate_locale(self) -> None:
        """
        Verify that ``locale`` is a non-empty string.

        Full locale validation (e.g. BCP-47 parsing) is intentionally omitted
        to avoid importing a heavy Unicode library just for config validation.
        The loader will default to ``"en"`` behaviour if the requested locale
        has no translations.

        Raises
        ------
        ValueError
            If ``locale`` is empty or whitespace-only.
        """
        if not isinstance(self.locale, str):
            raise ValueError(
                f"GrammarConfig.locale must be a str, "
                f"got {type(self.locale).__name__!r}."
            )

        stripped = self.locale.strip()
        if not stripped:
            raise ValueError(
                "GrammarConfig.locale must not be an empty string.  "
                "Use a BCP-47 locale code such as 'en' or 'en-GB'.  "
                "Only 'en' is fully supported in GGT v1.0."
            )

        self.locale = stripped

    # ------------------------------------------------------------------
    # Convenience helpers  (public, non-mutation)
    # ------------------------------------------------------------------

    @property
    def uses_override(self) -> bool:
        """
        ``True`` if this config specifies an external YAML override file.

        Equivalent to ``config.override_path is not None``.  Provided as a
        readable property so that loader code can branch cleanly:

        >>> if cfg.uses_override:
        ...     raw = _load_external_yaml(cfg.override_path)
        ... else:
        ...     raw = _load_embedded_yaml(cfg.language)
        """
        return self.override_path is not None

    def summary(self) -> str:
        """
        Return a single-line human-readable summary of this configuration.

        Useful for log output and CLI status messages.

        Returns
        -------
        str
            E.g. ``"GrammarConfig(language='chitonga', strict=False, cache=True)"``.

        Examples
        --------
        >>> cfg = GrammarConfig(language="chitonga", strict_mode=True)
        >>> cfg.summary()
        "GrammarConfig(language='chitonga', strict=True, override=None, cache=True)"
        """
        override_display = (
            f"'{self.override_path}'"
            if self.override_path is not None
            else "None"
        )
        return (
            f"GrammarConfig("
            f"language={self.language!r}, "
            f"strict={self.strict_mode}, "
            f"override={override_display}, "
            f"cache={self.cache})"
        )
