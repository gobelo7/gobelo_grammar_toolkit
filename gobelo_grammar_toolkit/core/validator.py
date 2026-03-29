"""
core/validator.py
=================
Schema validation, version compatibility checking, and VERIFY-flag extraction
for the Gobelo (Bantu) Grammar Toolkit (GGT).

This module is the gatekeeper between raw YAML data and the typed model layer.
No ``GobeloGrammarLoader`` method should ever expose data from a YAML file that
has not passed through ``GrammarValidator.validate()`` first.

Architecture overview
---------------------
Validation is divided into three sequential phases, each with a distinct
failure mode:

1. **Schema check** (``_check_required_keys``)
   Verifies that the raw YAML dict contains all mandatory top-level and
   section-level keys defined in the target ``SchemaDefinition``.  Also
   flags unexpected keys at the top level and ``metadata`` level to catch
   typos in externally-authored files.
   Raises: ``SchemaValidationError``

2. **Version compatibility check** (``_check_version_compatibility``)
   Compares the running loader version (``LOADER_VERSION``) against the
   ``min_loader_version`` and ``max_loader_version`` declared in the YAML
   ``metadata`` block.  Runs after Phase 1 so that the metadata keys are
   guaranteed to be present.
   Raises: ``VersionIncompatibleError``

3. **VERIFY flag extraction and handling** (``_extract_verify_flags``,
   ``_handle_verify_flags``)
   Recursively scans all YAML values for inline ``VERIFY:`` annotations and
   also parses the optional structured ``verify_flags`` section.  In
   ``strict_mode`` raises ``UnverifiedFormError``; otherwise emits a
   ``GGTWarning``.
   Raises: ``UnverifiedFormError`` (strict mode only)
   Warns:  ``GGTWarning`` (non-strict mode)
   Returns: ``List[VerifyFlag]`` for the loader to cache and expose via
   ``list_verify_flags()``.

Schema definition model
-----------------------
The GGT grammar YAML schema is itself versioned.  A ``SchemaDefinition``
dataclass captures the required and known keys for every section of the YAML
for one schema version.  All schema definitions live in ``SCHEMA_REGISTRY``,
keyed by their semver string.

When ``GrammarConfig.schema_version`` is ``None``, the validator uses
``LATEST_SCHEMA_VERSION``.  When a version is pinned, the validator looks it
up in ``SCHEMA_REGISTRY`` and raises ``ValueError`` (a programmer error, not a
grammar data error) if the version is not found.

VERIFY annotation convention
-----------------------------
Because YAML comments (``#``) are stripped by the PyYAML parser, VERIFY
annotations must be embedded in actual string *values*.  The GGT authoring
convention is:

    ``"VERIFY: <note text>"``  — entire value is a VERIFY annotation
    ``"mu-  VERIFY: Hoch 1960 §12"`` — form followed by inline annotation

The validator detects any string value containing ``"VERIFY:"`` (case-
insensitive) using ``_VERIFY_INLINE_RE`` and creates a ``VerifyFlag`` for it.

Additionally, the F-06 resolver workflow writes resolved and unresolved flags
to a structured top-level ``verify_flags`` list.  Both sources are merged,
with structured entries taking precedence over inline ones when both exist
for the same ``field_path``.

Loader version
--------------
``LOADER_VERSION`` is the authoritative version string for the running toolkit.
It is defined here (not in ``__init__.py``) because the validator is the only
module that needs it at runtime.  The CLI and public API surface it via
``GobeloGrammarLoader.loader_version``.

Usage
-----
The validator is not called directly by application code; it is invoked
internally by ``GobeloGrammarLoader.__init__``:

>>> from gobelo_grammar_toolkit.core.config import GrammarConfig
>>> from gobelo_grammar_toolkit.core.validator import GrammarValidator
>>> validator = GrammarValidator()
>>> flags = validator.validate(raw_yaml_dict, config, yaml_path="/p/f.yaml")
>>> # flags is List[VerifyFlag]; empty list means no VERIFY annotations found.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, TYPE_CHECKING

from gobelo_grammar_toolkit.core.exceptions import (
    SchemaValidationError,
    UnverifiedFormError,
    VersionIncompatibleError,
)

if TYPE_CHECKING:
    from gobelo_grammar_toolkit.core.config import GrammarConfig
    from gobelo_grammar_toolkit.core.models import VerifyFlag

__all__ = [
    "LOADER_VERSION",
    "LATEST_SCHEMA_VERSION",
    "SCHEMA_REGISTRY",
    "GGTWarning",
    "SchemaDefinition",
    "GrammarValidator",
]

# ---------------------------------------------------------------------------
# Package-level constants
# ---------------------------------------------------------------------------

#: The semantic version of the running GGT loader.  Increment this value when
#: releasing a new toolkit version.  Grammar YAML files declare the range of
#: loader versions they support via ``min_loader_version`` /
#: ``max_loader_version``; the validator enforces that this constant falls
#: within that range.
LOADER_VERSION: str = "1.0.0"

#: The most recent grammar YAML schema version known to this loader.  Used
#: when ``GrammarConfig.schema_version`` is ``None``.
LATEST_SCHEMA_VERSION: str = "1.0.0"

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------

# Semantic versioning: MAJOR.MINOR.PATCH (stdlib, no packaging dependency).
# Mirrors the identical pattern in core/config.py — defined independently
# here to keep the two modules free of a circular import dependency.
_SEMVER_RE: re.Pattern[str] = re.compile(r"^\d+\.\d+\.\d+$")

# Detects a VERIFY annotation embedded in a YAML string value.
# Matches "VERIFY:" optionally preceded by content (the current form) and
# optionally followed by a note.  Case-insensitive to tolerate "verify:".
_VERIFY_INLINE_RE: re.Pattern[str] = re.compile(r"VERIFY\s*:", re.IGNORECASE)

# ---------------------------------------------------------------------------
# GGTWarning
# ---------------------------------------------------------------------------


class GGTWarning(UserWarning):
    """
    Base class for all non-fatal GGT warnings.

    Catching or filtering ``GGTWarning`` targets exactly the warnings
    emitted by the GGT library, without affecting unrelated ``UserWarning``
    instances from other libraries.

    The most common cause is the presence of unresolved ``VERIFY:``
    annotations in a grammar loaded with ``strict_mode=False``.

    Usage in application code:

    >>> import warnings
    >>> warnings.filterwarnings("error", category=GGTWarning)
    >>> # Now any GGT warning raises an exception instead of printing.

    To silence GGT warnings entirely (not recommended for production):

    >>> warnings.filterwarnings("ignore", category=GGTWarning)
    """


# ---------------------------------------------------------------------------
# SchemaDefinition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SchemaDefinition:
    """
    The complete schema specification for one version of the GGT grammar YAML.

    A ``SchemaDefinition`` captures which keys are *required* and which are
    *known* (required ∪ optional) for every section of the grammar YAML.
    The validator uses these sets to:

    * Raise ``SchemaValidationError`` when a required key is absent.
    * Flag unexpected *extra* keys at the top level and ``metadata`` level
      (where the key set is tightly controlled).

    Extra-key detection is **not** applied to deeply-nested sections
    (individual noun-class entries, TAM markers, etc.) because new optional
    fields may be added to those structures via MINOR version bumps without
    requiring downstream apps to change.

    Parameters
    ----------
    schema_version : str
        The ``MAJOR.MINOR.PATCH`` version string this definition corresponds
        to, e.g. ``"1.0.0"``.
    required_top_level_keys : FrozenSet[str]
        Top-level YAML sections that must be present in every grammar file.
    known_top_level_keys : FrozenSet[str]
        All top-level keys the schema recognises (required ∪ optional).
        A key present in the YAML but absent from this set is reported as
        an *extra* key in ``SchemaValidationError.extra_keys``.
    required_metadata_keys : FrozenSet[str]
        Sub-keys of the ``metadata`` block that are mandatory.
    known_metadata_keys : FrozenSet[str]
        All ``metadata`` sub-keys the schema recognises.
    required_phonology_keys : FrozenSet[str]
        Sub-keys of the ``phonology`` block that are mandatory.
    known_phonology_keys : FrozenSet[str]
        All ``phonology`` sub-keys the schema recognises.
    required_noun_class_entry_keys : FrozenSet[str]
        Keys that each entry in the ``noun_classes`` mapping must have.
        The noun-class mapping is ``{NC_id: {key: value, …}, …}``; these
        keys are checked on every entry value dict.
    known_noun_class_entry_keys : FrozenSet[str]
        All recognised keys for a noun-class entry.
    required_verb_system_keys : FrozenSet[str]
        Sub-keys of the ``verb_system`` block that are mandatory.
    known_verb_system_keys : FrozenSet[str]
        All ``verb_system`` sub-keys the schema recognises.
    required_tokenization_keys : FrozenSet[str]
        Sub-keys of the ``tokenization`` block that are mandatory.
    known_tokenization_keys : FrozenSet[str]
        All ``tokenization`` sub-keys the schema recognises.

    Examples
    --------
    Access the v1.0 schema definition:

    >>> schema = SCHEMA_REGISTRY["1.0.0"]
    >>> "metadata" in schema.required_top_level_keys
    True
    >>> "grammar_version" in schema.required_metadata_keys
    True
    """

    schema_version: str

    # Top-level sections
    required_top_level_keys: FrozenSet[str]
    known_top_level_keys: FrozenSet[str]

    # metadata block
    required_metadata_keys: FrozenSet[str]
    known_metadata_keys: FrozenSet[str]

    # phonology block
    required_phonology_keys: FrozenSet[str]
    known_phonology_keys: FrozenSet[str]

    # noun_classes: per-entry validation (the mapping value dicts)
    required_noun_class_entry_keys: FrozenSet[str]
    known_noun_class_entry_keys: FrozenSet[str]

    # verb_system block
    required_verb_system_keys: FrozenSet[str]
    known_verb_system_keys: FrozenSet[str]

    # tokenization block
    required_tokenization_keys: FrozenSet[str]
    known_tokenization_keys: FrozenSet[str]


# ---------------------------------------------------------------------------
# SCHEMA_REGISTRY — canonical v1.0 definition
# ---------------------------------------------------------------------------

def _build_v1_0_schema() -> SchemaDefinition:
    """
    Build and return the canonical GGT schema definition for version 1.0.0.

    This function is called once at module import time and its result is
    stored in ``SCHEMA_REGISTRY["1.0.0"]``.  It is a private function (not
    a classmethod on ``SchemaDefinition``) so that the schema registry can be
    populated without any class-level side effects.

    When the schema evolves, add a ``_build_v1_1_schema()`` function (etc.)
    alongside this one and register it in ``SCHEMA_REGISTRY``.  Do not modify
    this function retroactively — backwards compatibility requires that
    ``SCHEMA_REGISTRY["1.0.0"]`` always returns the original v1.0 definition.

    Returns
    -------
    SchemaDefinition
        Fully-populated schema definition for GGT grammar YAML v1.0.
    """
    return SchemaDefinition(
        schema_version="1.0.0",

        # ── Top-level ──────────────────────────────────────────────────────
        # Every compliant YAML grammar file must have exactly these six
        # sections.  ``verify_flags`` is optional: it is written by the
        # F-06 VERIFY Flag Resolver and absent from freshly-authored files.
        
        required_top_level_keys=frozenset({
            "metadata",
            "phonology",
            "noun_classes",
            "concord_systems",
            "verb_system",
            "tokenization",
        }),
        known_top_level_keys=frozenset({
            "metadata",
            "phonology",
            "noun_classes",
            "concord_systems",
            "verb_system",
            "tokenization",
            "verify_flags",        # optional: structured VERIFY output (F-06)
            # Gobelo reference-grammar format variants (normalised before validation)
            "noun_class_system",   # normalised to noun_classes
            "concord_system",      # normalised to concord_systems
            "phonology_rules",     # normalised to phonology
            "morphology",          # unwrapped during legacy normalisation
        }),

        # ── metadata ───────────────────────────────────────────────────────
        # Version identity fields used by the loader for compatibility checks.
        # ``display_name``, ``contributors``, ``last_updated``, and ``notes``
        # are optional authoring metadata not required for parsing.
        required_metadata_keys=frozenset({
            "language",
            "iso_code",
            "guthrie",
            "grammar_version",
            "min_loader_version",
            "max_loader_version",
        }),
        known_metadata_keys=frozenset({
            "language",
            "iso_code",
            "guthrie",
            "grammar_version",
            "min_loader_version",
            "max_loader_version",
            "display_name",        # e.g. "chiTonga" (properly capitalised)
            "contributors",        # list of contributor names
            "last_updated",        # ISO-8601 date string
            "notes",               # free-text authoring commentary
            # Gobelo reference-grammar variant metadata keys
            "version",             # normalised to grammar_version
            "Yaml_version",        # legacy capitalisation variant
            "framework",           # framework version sub-dict
            "schema_compatibility",# min/max parser version sub-dict
            "orthography",         # orthography description
            "tone_marking",        # tone marking convention
            "date_created",        # creation date
            "maintainer",          # maintainer name
            "documentation",       # documentation link
            "Target_audience",     # target audience description
            "reference_grammar",   # reference grammar citation
            "editing_instructions",# editing guidance
        }),

        # ── phonology ──────────────────────────────────────────────────────
        # Vowel and consonant inventories and tone system are required to
        # support the surface-form generator (F-01) and segmenter (F-02).
        # Sandhi and vowel-harmony rules, and nasal prefix lists, are
        # optional because not all languages have documented systems for them.
        required_phonology_keys=frozenset({
            "vowels",
            "consonants",
            "tone_system",
        }),
        known_phonology_keys=frozenset({
            "vowels",
            "consonants",
            "tone_system",
            "nasal_prefixes",
            "sandhi_rules",
            "vowel_harmony_rules",
            "notes",
        }),

        # ── noun_classes entries ────────────────────────────────────────────
        # Validated per entry in the noun_classes mapping.  ``id``,
        # ``prefix``, ``semantic_domain``, and ``active`` are the minimum
        # required to construct a ``NounClass`` model object.
        # ``allomorphs``, ``singular_counterpart``, and ``plural_counterpart``
        # are optional because not every language documents these.
        required_noun_class_entry_keys=frozenset({
            "id",
            "prefix",
            "semantic_domain",
            "active",
        }),
        known_noun_class_entry_keys=frozenset({
            "id",
            "prefix",
            "allomorphs",
            "semantic_domain",
            "active",
            "singular_counterpart",
            "plural_counterpart",
            "notes",
        }),

        # ── verb_system ────────────────────────────────────────────────────
        # TAM markers, verb extensions, and verb slots are the three pillars
        # of the GGT slot architecture and are required.
        # Derivational patterns and the verb template are optional enrichments.
        required_verb_system_keys=frozenset({
            "tam_markers",
            "verb_extensions",
            "verb_slots",
        }),
        known_verb_system_keys=frozenset({
            "tam_markers",
            "verb_extensions",
            "verb_slots",
            "derivational_patterns",
            "verb_template",
            "notes",
        }),

        # ── tokenization ───────────────────────────────────────────────────
        # Only ``word_boundary_pattern`` is strictly required; the segmenter
        # (F-02) needs at least this to operate.  All other tokenization
        # sub-fields are optional enhancements.
        required_tokenization_keys=frozenset({
            "word_boundary_pattern",
        }),
        known_tokenization_keys=frozenset({
            "word_boundary_pattern",
            "clitic_boundaries",
            "prefix_strip_patterns",
            "suffix_strip_patterns",
            "special_cases",
            "orthographic_normalization",
            "notes",
        }),
    )


#: Registry of all known ``SchemaDefinition`` objects, keyed by semver string.
#:
#: To add a new schema version:
#: 1. Write a ``_build_vX_Y_schema()`` function.
#: 2. Add ``"X.Y.0": _build_vX_Y_schema()`` to this dict.
#: 3. Update ``LATEST_SCHEMA_VERSION``.
#: 4. Document the change in ``CHANGELOG.md``.
SCHEMA_REGISTRY: Dict[str, SchemaDefinition] = {
    "1.0.0": _build_v1_0_schema(),
}


# ---------------------------------------------------------------------------
# Semver utilities  (stdlib only — no packaging dependency)
# ---------------------------------------------------------------------------


def _parse_semver(version: str) -> Tuple[int, int, int]:
    """
    Parse a ``MAJOR.MINOR.PATCH`` version string into a comparable tuple.

    Parameters
    ----------
    version : str
        A semantic version string, e.g. ``"1.2.3"``.

    Returns
    -------
    Tuple[int, int, int]
        ``(major, minor, patch)`` as integers.

    Raises
    ------
    ValueError
        If ``version`` does not match ``MAJOR.MINOR.PATCH`` format.

    Examples
    --------
    >>> _parse_semver("1.2.3")
    (1, 2, 3)
    >>> _parse_semver("1.0.0") < _parse_semver("2.0.0")
    True
    """
    if not _SEMVER_RE.match(version.strip()):
        raise ValueError(
            f"Version string {version!r} is not in MAJOR.MINOR.PATCH format."
        )
    parts = version.strip().split(".")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _semver_in_range(
    version: str,
    min_version: str,
    max_version: str,
) -> bool:
    """
    Return ``True`` if ``min_version <= version <= max_version``.

    All three arguments must be ``MAJOR.MINOR.PATCH`` semver strings.
    Comparison is performed component-by-component as integers (not
    lexicographically), so ``"1.10.0" > "1.9.0"`` as expected.

    Parameters
    ----------
    version : str
        The version to test, e.g. ``LOADER_VERSION``.
    min_version : str
        Lower bound (inclusive), e.g. ``metadata["min_loader_version"]``.
    max_version : str
        Upper bound (inclusive), e.g. ``metadata["max_loader_version"]``.

    Returns
    -------
    bool
        ``True`` if ``version`` falls within ``[min_version, max_version]``.

    Raises
    ------
    ValueError
        If any argument fails semver format validation.

    Examples
    --------
    >>> _semver_in_range("1.3.0", "1.0.0", "2.0.0")
    True
    >>> _semver_in_range("0.9.0", "1.0.0", "2.0.0")
    False
    >>> _semver_in_range("3.0.0", "1.0.0", "2.0.0")
    False
    """
    v = _parse_semver(version)
    lo = _parse_semver(min_version)
    hi = _parse_semver(max_version)
    return lo <= v <= hi


# ---------------------------------------------------------------------------
# GrammarValidator
# ---------------------------------------------------------------------------


class GrammarValidator:
    """
    Validates a raw YAML grammar dict against the GGT schema.

    ``GrammarValidator`` is stateless after construction — the ``loader_version``
    is fixed at instantiation and all validation state is local to each
    ``validate()`` call.  This makes it safe to share a single
    ``GrammarValidator`` instance across multiple grammar loads (e.g. in a
    long-running REST server).

    Parameters
    ----------
    loader_version : str
        The toolkit version to use for compatibility checks.  Defaults to
        ``LOADER_VERSION`` (the version of the installed package).  Passing
        a custom version is useful in unit tests that need to simulate
        older or newer loaders without patching the module-level constant.

    Raises
    ------
    ValueError
        If ``loader_version`` is not a valid ``MAJOR.MINOR.PATCH`` string.

    Examples
    --------
    Default validator (uses installed toolkit version):

    >>> validator = GrammarValidator()
    >>> flags = validator.validate(raw, config, yaml_path="/p/grammar.yaml")
    >>> len(flags)   # number of unresolved VERIFY annotations
    0

    Test validator pinned to an older version:

    >>> validator = GrammarValidator(loader_version="0.9.0")
    """

    def __init__(self, loader_version: str = LOADER_VERSION) -> None:
        if not _SEMVER_RE.match(loader_version.strip()):
            raise ValueError(
                f"loader_version {loader_version!r} is not a valid "
                f"MAJOR.MINOR.PATCH semver string."
            )
        self._loader_version: str = loader_version.strip()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def loader_version(self) -> str:
        """
        The loader version string this validator was constructed with.

        Read-only.  Used by the loader to expose ``GobeloGrammarLoader.loader_version``.
        """
        return self._loader_version

    def validate(
        self,
        raw: Dict[str, Any],
        config: "GrammarConfig",
        yaml_path: Optional[str] = None,
    ) -> "List[VerifyFlag]":
        """
        Run all three validation phases against a raw YAML dict.

        This method must be called before any data is extracted from ``raw``.
        It is designed so that a failure in Phase 1 prevents Phase 2 from
        running on incomplete data, and a failure in Phase 2 prevents VERIFY
        flags from being surfaced for a fundamentally broken grammar.

        Phases
        ------
        1. Schema check — required keys, extra keys
        2. Version compatibility — loader version within YAML's declared range
        3. VERIFY flag extraction — inline and structured; raise or warn

        Parameters
        ----------
        raw : Dict[str, Any]
            The Python dict produced by ``yaml.safe_load()`` of a grammar
            YAML file.  Must not be ``None`` or empty — an empty dict will
            fail Phase 1 immediately.
        config : GrammarConfig
            The configuration object for this load.  Used for
            ``config.schema_version`` (schema selection),
            ``config.strict_mode`` (VERIFY handling), and
            ``config.language`` (error messages).
        yaml_path : Optional[str]
            Filesystem path to the YAML file, for inclusion in error messages.
            Pass ``None`` when validating an in-memory dict.

        Returns
        -------
        List[VerifyFlag]
            All VERIFY flags found in ``raw``, merging structured and inline
            sources.  Includes both resolved and unresolved flags — the
            loader stores all of them and exposes them via
            ``GobeloGrammarLoader.list_verify_flags()``.  An empty list
            means the grammar has no VERIFY annotations at all.

        Raises
        ------
        SchemaValidationError
            Phase 1: one or more required keys are missing, or unexpected
            extra keys are present at the top level or in ``metadata``.
        VersionIncompatibleError
            Phase 2: the running loader version is outside the range declared
            by ``metadata.min_loader_version`` / ``metadata.max_loader_version``.
        UnverifiedFormError
            Phase 3: VERIFY flags are present and ``config.strict_mode`` is
            ``True``.
        ValueError
            If ``config.schema_version`` names a version not in
            ``SCHEMA_REGISTRY``.

        Examples
        --------
        >>> validator = GrammarValidator()
        >>> with open("chitonga.yaml") as f:
        ...     raw = yaml.safe_load(f)
        >>> flags = validator.validate(raw, GrammarConfig(language="chitonga"))
        >>> print(f"Loaded with {len(flags)} VERIFY flags")
        """
        schema = self._resolve_schema(config)

        # Pre-phase: if the raw dict is in the Gobelo production reference-grammar
        # format (noun_class_system / concord_system top-level keys), remap it
        # to canonical form so all three phases can validate it normally.
        # This mirrors the same detection used in GrammarNormalizer.normalize().
        if "noun_class_system" in raw or "concord_system" in raw:
            raw = self._remap_production_to_canonical(raw)

        # Phase 1 — structural schema check.  Must run first so that Phase 2
        # can safely access raw["metadata"]["min_loader_version"] etc.
        self._check_required_keys(raw, schema, yaml_path)

        # Phase 2 — version compatibility.  Metadata keys are now guaranteed
        # present by Phase 1.
        self._check_version_compatibility(raw, yaml_path)

        # Phase 3 — VERIFY flag extraction and enforcement.
        flags = self._extract_verify_flags(raw)
        self._handle_verify_flags(flags, config)

        return flags

    # ------------------------------------------------------------------
    # Phase 0 — schema resolution
    # ------------------------------------------------------------------

    def _resolve_schema(self, config: "GrammarConfig") -> SchemaDefinition:
        """
        Look up the ``SchemaDefinition`` to validate against.

        Uses ``config.schema_version`` if set; otherwise falls back to
        ``LATEST_SCHEMA_VERSION``.

        Parameters
        ----------
        config : GrammarConfig
            The loader configuration.

        Returns
        -------
        SchemaDefinition
            The schema definition to use for this validation run.

        Raises
        ------
        ValueError
            If ``config.schema_version`` is set to a version not present
            in ``SCHEMA_REGISTRY``.
        """
        target_version = config.schema_version or LATEST_SCHEMA_VERSION

        if target_version not in SCHEMA_REGISTRY:
            available = ", ".join(sorted(SCHEMA_REGISTRY.keys()))
            raise ValueError(
                f"GrammarConfig.schema_version {target_version!r} is not in "
                f"SCHEMA_REGISTRY.  Known schema versions: {available}.  "
                f"Either use schema_version=None to target the latest schema, "
                f"or update the GGT package to a version that includes the "
                f"requested schema."
            )

        return SCHEMA_REGISTRY[target_version]

    # ------------------------------------------------------------------
    # Phase 1 — required key and extra key checks
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # Production format remapper
    # ------------------------------------------------------------------

    @staticmethod
    def _remap_production_to_canonical(raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remap the Gobelo production reference-grammar YAML format to the
        canonical flat schema that the validator and normalizer expect.

        Called from ``validate()`` when ``noun_class_system`` or
        ``concord_system`` are present at the top level.

        This is a pure structural remapping — no linguistic data is changed.
        The remapped dict is used only for validation and normalisation;
        the original file on disk is never modified.
        """
        out: Dict[str, Any] = {}

        # ── metadata ──────────────────────────────────────────────────
        raw_meta = raw.get("metadata") or {}
        lang_raw = raw_meta.get("language") or {}
        meta_out: Dict[str, Any] = {}

        if isinstance(lang_raw, dict):
            meta_out["language"]  = lang_raw.get("name", "").lower().strip()
            meta_out["iso_code"]  = lang_raw.get("iso_code", "")
            meta_out["guthrie"]   = lang_raw.get("guthrie", "")
        else:
            meta_out["language"]  = str(lang_raw).lower().strip()
            meta_out["iso_code"]  = raw_meta.get("iso_code", "")
            meta_out["guthrie"]   = raw_meta.get("guthrie", "")

        sc = raw_meta.get("schema_compatibility") or {}
        # Strip non-semver suffixes like "(RC)", "(beta)", "-dev" so
        # the version compatibility check accepts the value.
        _raw_ver = (
            raw_meta.get("grammar_version")
            or raw_meta.get("version", "1.0.0")
            or "1.0.0"
        )
        meta_out["grammar_version"] = re.sub(
            r"[^0-9.].*$", "", str(_raw_ver)
        ).strip(".") or "1.0.0"
        def _semver(v, fallback):
            """Ensure v is MAJOR.MINOR.PATCH; pad or clean as needed."""
            s = re.sub(r"[^0-9.].*$", "", str(v or fallback)).strip(".")
            parts = s.split(".")
            while len(parts) < 3:
                parts.append("0")
            return ".".join(parts[:3])

        meta_out["min_loader_version"] = _semver(
            raw_meta.get("min_loader_version")
            or sc.get("min_parser_version"), "1.0.0"
        )
        meta_out["max_loader_version"] = _semver(
            raw_meta.get("max_loader_version")
            or sc.get("max_parser_version"), "999.0.0"
        )
        out["metadata"] = meta_out

        # ── phonology ─────────────────────────────────────────────────
        raw_phon = raw.get("phonology") or {}
        phon_out: Dict[str, Any] = {}

        vowels_raw = raw_phon.get("vowels") or []
        if isinstance(vowels_raw, dict):
            segs = vowels_raw.get("segments") or vowels_raw.get("short") or []
            phon_out["vowels"] = [
                s["symbol"] if isinstance(s, dict) else str(s)
                for s in segs if s
            ] or ["a", "e", "i", "o", "u"]
        else:
            phon_out["vowels"] = [str(v) for v in vowels_raw if v]

        cons_raw = raw_phon.get("consonants") or []
        if isinstance(cons_raw, dict):
            segs = cons_raw.get("segments") or []
            phon_out["consonants"] = [
                s["symbol"] if isinstance(s, dict) else str(s)
                for s in segs if s
            ]
        else:
            phon_out["consonants"] = [str(c) for c in cons_raw if c]

        tones_raw = raw_phon.get("tones") or {}
        if isinstance(tones_raw, dict):
            phon_out["tone_system"] = (
                tones_raw.get("system")
                or tones_raw.get("type")
                or "four_level"
            )
        else:
            phon_out["tone_system"] = str(tones_raw) if tones_raw else "four_level"

        out["phonology"] = phon_out

        # ── noun_classes ──────────────────────────────────────────────
        ncs_block = raw.get("noun_class_system") or {}
        raw_ncs   = ncs_block.get("noun_classes") or {}
        # Inject the fields the validator and normalizer require into each entry.
        # Production format stores id implicitly (as the dict key) and uses
        # semantics.primary_domain instead of semantic_domain.
        cooked_ncs = {}
        for nc_id, entry in raw_ncs.items():
            if not isinstance(entry, dict):
                continue
            e = dict(entry)  # shallow copy — never mutate the parsed YAML
            # Inject id from the dict key if absent
            if "id" not in e:
                e["id"] = nc_id
            # Inject semantic_domain from semantics.primary_domain if absent
            if "semantic_domain" not in e:
                sem = e.get("semantics")
                if isinstance(sem, dict):
                    e["semantic_domain"] = sem.get("primary_domain", "unspecified")
                else:
                    e["semantic_domain"] = "unspecified"
            cooked_ncs[nc_id] = e
        out["noun_classes"] = cooked_ncs

        # ── concord_systems ───────────────────────────────────────────
        concord_block = raw.get("concord_system") or {}
        out["concord_systems"] = concord_block.get("concords") or {}

        # ── verb_system ───────────────────────────────────────────────
        vs = raw.get("verb_system") or {}
        vsc = vs.get("verbal_system_components") or {}
        out["verb_system"] = {
            "tam_markers":        vsc.get("tam") or {},
            "verb_extensions":    vsc.get("derivational_extensions") or {},
            "verb_slots":         vs.get("verb_slots") or {},
        }

        # ── tokenization ──────────────────────────────────────────────
        raw_tok = raw.get("tokenization") or {}
        out["tokenization"] = {
            "word_boundary_pattern": (
                raw_tok.get("word_boundary")
                or raw_tok.get("word_boundary_pattern")
                or r"\s+"
            ),
        }

        return out

    def _check_required_keys(
        self,
        raw: Dict[str, Any],
        schema: SchemaDefinition,
        yaml_path: Optional[str],
    ) -> None:
        """
        Verify that all required YAML keys are present and no unexpected
        extra keys appear at the controlled levels.

        Checked levels
        ~~~~~~~~~~~~~~
        * **Top level** — required and extra keys both checked.
        * **metadata** — required and extra keys both checked.
        * **phonology** — required keys checked; extra keys tolerated.
        * **noun_classes entries** — required keys checked per entry; extra
          keys tolerated (new optional fields must not break parsers).
        * **verb_system** — required keys checked; extra keys tolerated.
        * **tokenization** — required keys checked; extra keys tolerated.
        * **concord_systems** — only presence of the section is checked;
          concord type names vary by language and are not schema-controlled.

        Parameters
        ----------
        raw : Dict[str, Any]
            The raw YAML dict.
        schema : SchemaDefinition
            The schema to validate against.
        yaml_path : Optional[str]
            Filesystem path for error messages.

        Raises
        ------
        SchemaValidationError
            If any required key is absent or any unexpected top-level /
            metadata key is found.  All violations are collected before
            raising so the caller receives the complete list in one error.
        """
        missing: List[str] = []
        extra: List[str] = []

        if not isinstance(raw, dict):
            raise SchemaValidationError(
                missing_keys=["<entire document>"],
                extra_keys=[],
                yaml_path=yaml_path,
                message=(
                    "The grammar YAML file did not parse to a mapping at the "
                    "top level.  Ensure the file is a valid YAML document "
                    "whose root is a key-value mapping, not a list or scalar."
                ),
            )

        # ── Top-level keys ──────────────────────────────────────────────────
        for key in schema.required_top_level_keys:
            if key not in raw:
                missing.append(key)

        for key in raw:
            if key not in schema.known_top_level_keys:
                extra.append(key)

        # ── metadata sub-keys ───────────────────────────────────────────────
        # Only check if metadata is present (its absence is already in
        # `missing`; we don't want cascading NoneType errors).
        metadata = raw.get("metadata")
        if isinstance(metadata, dict):
            for key in schema.required_metadata_keys:
                if key not in metadata:
                    missing.append(f"metadata.{key}")
            for key in metadata:
                if key not in schema.known_metadata_keys:
                    extra.append(f"metadata.{key}")
        elif metadata is not None:
            # metadata key is present but not a dict — structural error.
            missing.append("metadata.<mapping>")

        # ── phonology sub-keys ──────────────────────────────────────────────
        phonology = raw.get("phonology")
        if isinstance(phonology, dict):
            for key in schema.required_phonology_keys:
                if key not in phonology:
                    missing.append(f"phonology.{key}")
        elif phonology is not None:
            missing.append("phonology.<mapping>")

        # ── noun_classes entries ────────────────────────────────────────────
        # The noun_classes section is a mapping of NC_id → entry dict.
        # Every entry dict must have the required keys.
        noun_classes = raw.get("noun_classes")
        if isinstance(noun_classes, dict):
            if not noun_classes:
                # An empty noun_classes section is structurally invalid.
                missing.append("noun_classes.<at least one entry>")
            else:
                for nc_id, entry in noun_classes.items():
                    if not isinstance(entry, dict):
                        missing.append(f"noun_classes.{nc_id}.<mapping>")
                        continue
                    for key in schema.required_noun_class_entry_keys:
                        if key not in entry:
                            missing.append(f"noun_classes.{nc_id}.{key}")
        elif noun_classes is not None:
            missing.append("noun_classes.<mapping>")

        # ── concord_systems ─────────────────────────────────────────────────
        # Concord type names vary by language; we only verify the section
        # exists and is a non-empty mapping.
        concord_systems = raw.get("concord_systems")
        if isinstance(concord_systems, dict):
            if not concord_systems:
                missing.append("concord_systems.<at least one concord type>")
        elif concord_systems is not None:
            missing.append("concord_systems.<mapping>")

        # ── verb_system sub-keys ─────────────────────────────────────────────
        verb_system = raw.get("verb_system")
        if isinstance(verb_system, dict):
            for key in schema.required_verb_system_keys:
                if key not in verb_system:
                    missing.append(f"verb_system.{key}")
        elif verb_system is not None:
            missing.append("verb_system.<mapping>")

        # ── tokenization sub-keys ────────────────────────────────────────────
        tokenization = raw.get("tokenization")
        if isinstance(tokenization, dict):
            for key in schema.required_tokenization_keys:
                if key not in tokenization:
                    missing.append(f"tokenization.{key}")
        elif tokenization is not None:
            missing.append("tokenization.<mapping>")

        # ── Raise if anything went wrong ─────────────────────────────────────
        if missing or extra:
            raise SchemaValidationError(
                missing_keys=sorted(missing),
                extra_keys=sorted(extra),
                yaml_path=yaml_path,
            )

    # ------------------------------------------------------------------
    # Phase 2 — version compatibility
    # ------------------------------------------------------------------

    def _check_version_compatibility(
        self,
        raw: Dict[str, Any],
        yaml_path: Optional[str],
    ) -> None:
        """
        Verify that the running loader version falls within the grammar's
        declared compatibility window.

        Reads ``metadata.min_loader_version`` and ``metadata.max_loader_version``
        from ``raw`` and checks that ``self._loader_version`` satisfies:

            ``min_loader_version <= loader_version <= max_loader_version``

        This check is performed after Phase 1, so these keys are guaranteed
        to exist.

        Parameters
        ----------
        raw : Dict[str, Any]
            The raw YAML dict (already Phase-1 validated).
        yaml_path : Optional[str]
            Filesystem path for error messages.

        Raises
        ------
        VersionIncompatibleError
            If the loader version falls outside the declared range, or if
            any of the three version strings cannot be parsed as semver.
        """
        meta: Dict[str, Any] = raw["metadata"]
        grammar_version: str = str(meta["grammar_version"])
        min_loader: str = str(meta["min_loader_version"])
        max_loader: str = str(meta["max_loader_version"])

        # Validate that the YAML-declared version strings are well-formed
        # before comparing.  A malformed version string in the YAML is a
        # schema data error, not a compatibility error per se — but it
        # surfaces here rather than in Phase 1 because the value *format*
        # is a runtime concern.
        for label, version_str in [
            ("metadata.grammar_version", grammar_version),
            ("metadata.min_loader_version", min_loader),
            ("metadata.max_loader_version", max_loader),
        ]:
            if not _SEMVER_RE.match(version_str.strip()):
                raise VersionIncompatibleError(
                    yaml_version=grammar_version,
                    loader_version=self._loader_version,
                    min_loader_version=min_loader,
                    max_loader_version=max_loader,
                    yaml_path=yaml_path,
                    message=(
                        f"The value of {label!r} in the grammar YAML is "
                        f"{version_str!r}, which is not a valid "
                        f"MAJOR.MINOR.PATCH semver string.  Correct the "
                        f"grammar file's metadata block before loading."
                    ),
                )

        # Check min <= max for sanity.
        if _parse_semver(min_loader) > _parse_semver(max_loader):
            raise VersionIncompatibleError(
                yaml_version=grammar_version,
                loader_version=self._loader_version,
                min_loader_version=min_loader,
                max_loader_version=max_loader,
                yaml_path=yaml_path,
                message=(
                    f"The grammar YAML declares "
                    f"min_loader_version={min_loader!r} which is greater than "
                    f"max_loader_version={max_loader!r}.  This is an authoring "
                    f"error in the grammar file's metadata block."
                ),
            )

        # Core compatibility check.
        if not _semver_in_range(self._loader_version, min_loader, max_loader):
            raise VersionIncompatibleError(
                yaml_version=grammar_version,
                loader_version=self._loader_version,
                min_loader_version=min_loader,
                max_loader_version=max_loader,
                yaml_path=yaml_path,
            )

    # ------------------------------------------------------------------
    # Phase 3 — VERIFY flag extraction
    # ------------------------------------------------------------------

    def _extract_verify_flags(
        self,
        raw: Dict[str, Any],
    ) -> "List[VerifyFlag]":
        """
        Extract all VERIFY annotations from the raw YAML dict.

        Two complementary sources are merged:

        1. **Structured** ``verify_flags`` section — written by the F-06
           resolver workflow.  Each entry is a full ``VerifyFlag`` record.

        2. **Inline** ``VERIFY:`` markers embedded in string values
           throughout the grammar sections.  These are the primary authoring
           convention; they are detected recursively in all sections *except*
           ``verify_flags`` itself (to avoid double-counting).

        Deduplication
        ~~~~~~~~~~~~~
        If the same ``field_path`` appears in both sources, the structured
        entry takes precedence (it is more complete and was written by the
        resolver).  The inline entry for that path is discarded.

        Parameters
        ----------
        raw : Dict[str, Any]
            The raw YAML dict.

        Returns
        -------
        List[VerifyFlag]
            Merged list of all VERIFY flags.  Structured entries appear
            first, followed by unique inline entries.  The list is ordered
            deterministically: structured flags preserve their YAML order;
            inline flags are ordered by depth-first traversal.
        """
        structured: List[VerifyFlag] = self._extract_structured_flags(raw)
        structured_paths: FrozenSet[str] = frozenset(
            f.field_path for f in structured
        )

        inline: List[VerifyFlag] = []
        for section_key, section_value in raw.items():
            if section_key == "verify_flags":
                # Do not re-scan the structured section for inline markers;
                # doing so would corrupt the already-extracted structured flags.
                continue
            self._scan_for_inline_flags(
                node=section_value,
                path=section_key,
                collector=inline,
            )

        unique_inline: List[VerifyFlag] = [
            f for f in inline if f.field_path not in structured_paths
        ]

        return structured + unique_inline

    def _extract_structured_flags(
        self,
        raw: Dict[str, Any],
    ) -> "List[VerifyFlag]":
        """
        Parse the optional ``verify_flags`` top-level list into ``VerifyFlag``
        objects.

        The ``verify_flags`` section is written by the F-06 VERIFY Flag
        Resolver.  Each entry in the list must be a mapping with the keys
        defined by the ``VerifyFlag`` model.

        Missing or malformed individual entries are silently skipped (a
        ``GGTWarning`` is emitted for each), because a partially-populated
        ``verify_flags`` section should not block loading of an otherwise
        valid grammar.

        Parameters
        ----------
        raw : Dict[str, Any]
            The raw YAML dict.

        Returns
        -------
        List[VerifyFlag]
            Parsed structured flags; empty list if the section is absent or
            contains no valid entries.
        """
        from gobelo_grammar_toolkit.core.models import VerifyFlag

        flags_data = raw.get("verify_flags")
        if flags_data is None:
            return []

        if not isinstance(flags_data, list):
            warnings.warn(
                "The 'verify_flags' section of this grammar YAML is not a "
                "list.  Expected a YAML sequence of flag entries.  The "
                "section will be ignored.",
                GGTWarning,
                stacklevel=4,
            )
            return []

        flags: List[VerifyFlag] = []
        for idx, entry in enumerate(flags_data):
            if not isinstance(entry, dict):
                warnings.warn(
                    f"verify_flags[{idx}] is not a mapping and will be "
                    f"skipped.  Each entry in 'verify_flags' must be a "
                    f"YAML mapping with keys: field_path, current_value, "
                    f"note, suggested_source, resolved.",
                    GGTWarning,
                    stacklevel=4,
                )
                continue

            # Be permissive: coerce values to the expected types rather than
            # hard-failing on individual entries.
            try:
                flag = VerifyFlag(
                    field_path=str(entry.get("field_path", "")),
                    current_value=str(entry.get("current_value", "")),
                    note=str(entry.get("note", "")),
                    suggested_source=str(entry.get("suggested_source", "")),
                    resolved=bool(entry.get("resolved", False)),
                )
                flags.append(flag)
            except (TypeError, ValueError) as exc:
                warnings.warn(
                    f"verify_flags[{idx}] could not be parsed and will be "
                    f"skipped: {exc}",
                    GGTWarning,
                    stacklevel=4,
                )

        return flags

    def _scan_for_inline_flags(
        self,
        node: Any,
        path: str,
        collector: "List[VerifyFlag]",
    ) -> None:
        """
        Recursively walk ``node`` and append a ``VerifyFlag`` for every
        string value that contains a ``VERIFY:`` annotation.

        The walk is depth-first.  Dicts, lists, and scalars are all handled;
        ``None``, booleans, and numbers are silently skipped.

        Dot-notation paths are constructed by joining the key/index at each
        level:

        * Dict keys: ``parent.child_key``
        * List indices: ``parent[0]``, ``parent[1]``, …

        Value parsing
        ~~~~~~~~~~~~~
        For a value like ``"mu-  VERIFY: Hoch 1960 §12"``:

        * ``current_value`` = ``"mu-"``  (text before ``VERIFY:``)
        * ``note``          = ``"Hoch 1960 §12"``  (text after ``VERIFY:``)

        For a value that *starts* with ``VERIFY:``:

        * ``current_value`` = ``""``  (no form precedes the annotation)
        * ``note``          = everything after ``VERIFY:``

        ``suggested_source`` is always ``""`` for inline flags — the source
        cannot be reliably parsed from an inline string.

        Parameters
        ----------
        node : Any
            The current YAML node being examined.
        path : str
            Dot-notation path to ``node`` within the full YAML structure.
        collector : List[VerifyFlag]
            List to which newly-created ``VerifyFlag`` objects are appended.
        """
        from gobelo_grammar_toolkit.core.models import VerifyFlag

        if isinstance(node, str):
            match = _VERIFY_INLINE_RE.search(node)
            if match:
                # Text before "VERIFY:" is the current (uncertain) form.
                # Text after "VERIFY:" is the annotation note.
                pre = node[: match.start()].strip()
                note = node[match.end() :].strip()
                collector.append(
                    VerifyFlag(
                        field_path=path,
                        current_value=pre,
                        note=note,
                        suggested_source="",
                        resolved=False,
                    )
                )

        elif isinstance(node, dict):
            for key, value in node.items():
                child_path = f"{path}.{key}"
                self._scan_for_inline_flags(value, child_path, collector)

        elif isinstance(node, list):
            for idx, item in enumerate(node):
                child_path = f"{path}[{idx}]"
                self._scan_for_inline_flags(item, child_path, collector)

        # bool, int, float, None: no VERIFY annotation possible — skip.

    # ------------------------------------------------------------------
    # Phase 3 — VERIFY flag enforcement
    # ------------------------------------------------------------------

    def _handle_verify_flags(
        self,
        flags: "List[VerifyFlag]",
        config: "GrammarConfig",
    ) -> None:
        """
        Raise or warn based on unresolved VERIFY flags and ``strict_mode``.

        Only *unresolved* flags (``VerifyFlag.resolved == False``) count
        toward the strict-mode threshold and the warning count.  Resolved
        flags are retained in the returned list so that the F-06 workflow
        can track history, but they do not trigger any error or warning.

        Parameters
        ----------
        flags : List[VerifyFlag]
            All flags (resolved and unresolved) extracted from the grammar.
        config : GrammarConfig
            The loader configuration; consulted for ``strict_mode`` and
            ``language``.

        Raises
        ------
        UnverifiedFormError
            If there are unresolved flags and ``config.strict_mode`` is
            ``True``.
        """
        unresolved = [f for f in flags if not f.resolved]
        if not unresolved:
            return

        if config.strict_mode:
            raise UnverifiedFormError(
                flags=unresolved,
                language=config.language,
            )

        # Non-strict: emit a GGTWarning so the caller is informed but not
        # blocked.  stacklevel=4 attempts to point the warning at the
        # loader's caller rather than deep inside the validator.  The exact
        # depth depends on the loader's call graph and may need adjustment
        # if the loader wraps this in additional helper methods.
        count = len(unresolved)
        noun = "flag" if count == 1 else "flags"
        warnings.warn(
            f"Grammar for '{config.language}' contains {count} unresolved "
            f"VERIFY {noun}.  Forms marked VERIFY have not been confirmed "
            f"against a primary reference grammar.  Use "
            f"'ggt verify-flags {config.language}' to review them, or "
            f"set strict_mode=True to raise an error on these.  "
            f"Proceeding with caution is advised in production workflows.",
            GGTWarning,
            stacklevel=4,
        )
