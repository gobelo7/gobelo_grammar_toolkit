"""
core/loader.py
==============
Main public entry point for the Gobelo (Bantu) Grammar Toolkit (GGT).

``GobeloGrammarLoader`` is the **only** class application code needs to
import.  It owns the full lifecycle of a grammar resource: locating the
correct YAML file, loading it from disk, validating the schema and version,
normalizing the raw dict into typed model objects, and serving those objects
via a stable, typed public API.

Architecture
------------
The loader sits at the top of a three-layer pipeline::

    disk (YAML)
        │
        ▼
    GobeloGrammarLoader.__init__
        │  ① locate YAML  (registry + override_path)
        │  ② load YAML    (_load_embedded_yaml / _load_external_yaml)
        │  ③ validate     (GrammarValidator.validate → List[VerifyFlag])
        │  ④ normalize    (GrammarNormalizer.normalize → _ParsedGrammar)
        │  ⑤ cache        (self._parsed : _ParsedGrammar)
        ▼
    public get_*() methods  →  typed frozen dataclasses

Public API — 14 methods + 2 properties
---------------------------------------
``get_metadata()``             → ``GrammarMetadata``
``get_noun_classes()``         → ``List[NounClass]``
``get_noun_class(nc_id)``      → ``NounClass``
``get_subject_concords()``     → ``ConcordSet``
``get_object_concords()``      → ``ConcordSet``
``get_concords(concord_type)`` → ``ConcordSet``
``get_all_concord_types()``    → ``List[str]``
``get_tam_markers()``          → ``List[TAMMarker]``
``get_extensions()``           → ``List[VerbExtension]``
``get_verb_template()``        → ``Dict[str, Any]``   (deep copy; only raw dict in API)
``get_verb_slots()``           → ``List[VerbSlot]``
``get_patterns()``             → ``List[DerivationalPattern]``
``get_phonology()``            → ``PhonologyRules``
``get_tokenization_rules()``   → ``TokenizationRules``
``list_verify_flags()``        → ``List[VerifyFlag]``  (unresolved only)
``config``  (property)         → ``GrammarConfig``
``loader_version`` (property)  → ``str``

YAML resolution
---------------
When ``GrammarConfig.override_path`` is ``None``:
    The loader looks up the language id in the registry
    (``core/registry.py``) to find the YAML filename, then resolves it as
    a package resource via ``importlib.resources.files()``.  This works
    whether the package is installed as a wheel, a zip, or a plain
    directory.

When ``GrammarConfig.override_path`` is set:
    The loader skips the registry lookup and reads the YAML directly from
    the provided ``pathlib.Path``.  This is used for development, testing,
    and custom grammar files.

Validation and strict mode
--------------------------
Every loaded YAML passes through ``GrammarValidator.validate()``.  In
``strict_mode``, any unresolved VERIFY flag raises ``UnverifiedFormError``.

No raw dicts cross the public boundary
---------------------------------------
Every method returns a frozen dataclass **except** ``get_verb_template()``,
which the spec explicitly types as ``Dict[str, Any]`` and which always
returns a **deep copy** to prevent callers from mutating internal state.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import importlib.resources as _importlib_resources
    _HAS_FILES_API = hasattr(_importlib_resources, "files")
except ImportError:
    _HAS_FILES_API = False

try:
    import yaml as _yaml
except ImportError as _e:
    raise ImportError(
        "PyYAML is required by the Gobelo Grammar Toolkit.  "
        "Install it with:  pip install pyyaml"
    ) from _e

from gobelo_grammar_toolkit.core.config import GrammarConfig
from gobelo_grammar_toolkit.core.exceptions import (
    ConcordTypeNotFoundError,
    LanguageNotFoundError,
    NounClassNotFoundError,
)
from gobelo_grammar_toolkit.core.models import (
    ConcordSet,
    DerivationalPattern,
    GrammarMetadata,
    NounClass,
    PhonologyRules,
    TAMMarker,
    TokenizationRules,
    VerbExtension,
    VerbSlot,
    VerifyFlag,
)
from gobelo_grammar_toolkit.core.normalizer import GrammarNormalizer, _ParsedGrammar
from gobelo_grammar_toolkit.core.registry import get_yaml_filename, is_registered
from gobelo_grammar_toolkit.core.validator import LOADER_VERSION, GrammarValidator

__all__ = ["GobeloGrammarLoader"]


def list_supported_languages_helper() -> List[str]:
    """Internal helper to avoid circular imports in __init__."""
    from gobelo_grammar_toolkit.core.registry import list_languages
    return list_languages()

# ---------------------------------------------------------------------------
# Module-level singletons  — stateless, safe to share across instances
# ---------------------------------------------------------------------------

_VALIDATOR = GrammarValidator()
_NORMALIZER = GrammarNormalizer()

# Regex for extracting numeric part of an NC identifier
_NC_NUMERIC_RE = re.compile(r"(\d+)")


# ---------------------------------------------------------------------------
# GobeloGrammarLoader
# ---------------------------------------------------------------------------


class GobeloGrammarLoader:
    """
    Primary public interface for loading and querying a Bantu grammar file.

    Parameters
    ----------
    config : GrammarConfig
        Configuration specifying the language, optional YAML override path,
        strict-mode flag, and schema version pin.

    Raises
    ------
    LanguageNotFoundError
        If ``config.override_path`` is ``None`` and the language id is not
        registered.
    FileNotFoundError
        If ``config.override_path`` points to a non-existent file.
    SchemaValidationError
        If the YAML fails structural validation.
    VersionIncompatibleError
        If the running loader version is outside the grammar's window.
    UnverifiedFormError
        If ``config.strict_mode`` is ``True`` and unresolved VERIFY flags
        are present.
    yaml.YAMLError
        If the YAML cannot be parsed.
    """

    def __init__(self, config: GrammarConfig) -> None:
        self._config = config

        # ① Locate YAML -------------------------------------------------------
        if config.uses_override:
            yaml_path: Optional[Path] = Path(config.override_path)  # type: ignore[arg-type]
            if not yaml_path.exists():
                raise FileNotFoundError(
                    f"Grammar override file not found: {yaml_path}"
                )
        else:
            if not is_registered(config.language):
                raise LanguageNotFoundError(
                    language=config.language,
                    available_languages=list_supported_languages_helper(),
                )
            yaml_path = None

        # ② Load YAML ---------------------------------------------------------
        raw: Dict[str, Any] = (
            self._load_external_yaml(yaml_path)
            if yaml_path is not None
            else self._load_embedded_yaml(config.language)
        )

        # Unwrap any '<language>_grammar:' top-level wrapper
        raw = self._unwrap_language_wrapper(raw)

        # ③ Normalise legacy / variant schema → GGT-canonical flat form
        # This MUST run before the validator so the validator always sees
        # the canonical key names (noun_classes, concord_systems, etc.).
        raw = self._normalize_legacy_schema(raw)

        # ④ Validate ----------------------------------------------------------
        verify_flags: List[VerifyFlag] = _VALIDATOR.validate(raw, config, yaml_path)

        # ⑤ Language-match sanity check
        if "metadata" in raw:
            meta_lang_raw = raw["metadata"].get("language")
            # Production format: metadata.language is a nested dict with a 'name' key.
            # Canonical format:  metadata.language is a plain string.
            if isinstance(meta_lang_raw, dict):
                meta_lang = meta_lang_raw.get("name", "")
            else:
                meta_lang = meta_lang_raw
            if meta_lang and str(meta_lang).lower() != self._config.language.lower():
                raise ValueError(
                    f"Grammar language mismatch: config='{self._config.language}' "
                    f"metadata='{meta_lang}'"
                )

        # ⑥ Normalize → typed model -------------------------------------------
        self._parsed: _ParsedGrammar = _NORMALIZER.normalize(raw, verify_flags)


    # --- New insert ---
    def _unwrap_language_wrapper(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect and unwrap a '<language>_grammar' YAML wrapper.

        Many Gobelo grammars are structured as:

            kaonde_grammar:
                metadata:
                noun_classes:
                ...

        The validator expects the inner structure, so this method removes
        the wrapper before validation.
        """

        if not isinstance(raw, dict):
            return raw

        # Case 1: wrapper matches config language
        expected_wrapper = f"{self._config.language}_grammar"
        if expected_wrapper in raw:
            return raw[expected_wrapper]

        # Case 2: generic *_grammar wrapper
        if len(raw) == 1:
            key = next(iter(raw))
            if key.endswith("_grammar"):
                return raw[key]

        return raw


    # --- New insert ---
    def _normalize_legacy_schema(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate every known Gobelo YAML variant into the GGT-canonical
        flat schema that the validator and normalizer both expect.

        Handles the chitonga_grammar.yaml reference-grammar format which
        uses different key names, nested structures, and sub-dict metadata
        compared to the canonical schema.
        """
        if not isinstance(raw, dict):
            return raw

        # ── 1. METADATA ────────────────────────────────────────────────
        meta: Dict[str, Any] = raw.get("metadata") or {}

        # metadata.language may be a nested dict: extract flat fields
        lang_block = meta.get("language")
        if isinstance(lang_block, dict):
            # iso_code and guthrie live inside the nested dict
            if "iso_code" not in meta:
                meta["iso_code"] = lang_block.get("iso_code", "")
            if "guthrie" not in meta:
                meta["guthrie"] = lang_block.get("guthrie", "")
            # Flatten language name to a plain string
            name = lang_block.get("name", "")
            meta["language"] = name.lower().strip() if name else self._config.language

        # grammar_version: try metadata.version first, then framework.Yaml_version
        if "grammar_version" not in meta:
            ver = meta.get("version") or meta.get("Yaml_version")
            if ver is None:
                fw = meta.get("framework")
                if isinstance(fw, dict):
                    ver = fw.get("Yaml_version") or fw.get("version")
            if ver is not None:
                # strip trailing " (RC)" or similar qualifiers for semver
                ver_str = str(ver).strip()
                import re as _re
                ver_clean = _re.sub(r"\s*\(.*?\)", "", ver_str).strip()
                # Pad to MAJOR.MINOR.PATCH if only MAJOR.MINOR supplied
                parts = ver_clean.split(".")
                while len(parts) < 3:
                    parts.append("0")
                meta["grammar_version"] = ".".join(parts[:3])
            else:
                meta["grammar_version"] = "1.0.0"

        # min_loader_version: from framework_version or schema_compatibility
        if "min_loader_version" not in meta:
            sc = meta.get("schema_compatibility")
            if isinstance(sc, dict):
                # min_parser_version may be "1.0" — pad to semver
                raw_min = str(sc.get("min_parser_version", "1.0"))
                parts = raw_min.split(".")
                while len(parts) < 3:
                    parts.append("0")
                meta["min_loader_version"] = ".".join(parts[:3])
            elif "framework_version" in meta:
                meta["min_loader_version"] = str(meta.pop("framework_version"))
            else:
                meta["min_loader_version"] = "1.0.0"

        # max_loader_version: from schema_compatibility or hard default
        if "max_loader_version" not in meta:
            sc = meta.get("schema_compatibility")
            if isinstance(sc, dict):
                raw_max = str(sc.get("max_parser_version", "999.0.0"))
                # "2.x" → "999.0.0"
                if "x" in raw_max.lower() or "*" in raw_max:
                    raw_max = "999.0.0"
                parts = raw_max.split(".")
                while len(parts) < 3:
                    parts.append("0")
                meta["max_loader_version"] = ".".join(parts[:3])
            else:
                meta["max_loader_version"] = "999.0.0"

        raw["metadata"] = meta

        # ── 2. NOUN CLASSES ────────────────────────────────────────────
        # chitonga.yaml: noun_class_system.noun_classes -> noun_classes
        if "noun_classes" not in raw and "noun_class_system" in raw:
            nc_sys = raw["noun_class_system"]
            if isinstance(nc_sys, dict):
                raw["noun_classes"] = nc_sys.get("noun_classes") or {}

        # Ensure each NC entry has flat 'id' and 'semantic_domain' keys
        # (the validator checks for these; the normalizer also reads them)
        nc_dict = raw.get("noun_classes") or {}
        if isinstance(nc_dict, dict):
            for nc_key, nc_entry in nc_dict.items():
                if not isinstance(nc_entry, dict):
                    continue
                # Inject 'id' from the dict key if absent
                if "id" not in nc_entry:
                    nc_entry["id"] = nc_key
                # Flatten semantics.primary_domain -> semantic_domain
                if "semantic_domain" not in nc_entry:
                    sem = nc_entry.get("semantics")
                    if isinstance(sem, dict):
                        nc_entry["semantic_domain"] = sem.get("primary_domain", "unspecified")
                    else:
                        nc_entry["semantic_domain"] = "unspecified"

        # ── 3. CONCORD SYSTEMS ─────────────────────────────────────────
        # chitonga.yaml: concord_system.concords -> concord_systems
        if "concord_systems" not in raw and "concord_system" in raw:
            cs_block = raw["concord_system"]
            if isinstance(cs_block, dict):
                raw["concord_systems"] = cs_block.get("concords") or {}

        # ── 4. PHONOLOGY ───────────────────────────────────────────────
        # phonology_rules -> phonology (from morphology wrapper)
        if "phonology_rules" in raw and "phonology" not in raw:
            raw["phonology"] = raw.pop("phonology_rules")

        # phonology.tone_system: synthesise from phonology.tones if absent
        phon = raw.get("phonology")
        if isinstance(phon, dict) and "tone_system" not in phon:
            tones = phon.get("tones") or {}
            if isinstance(tones, dict):
                levels = tones.get("levels") or []
                n = len(levels) if isinstance(levels, list) else 0
                phon["tone_system"] = (
                    "four_level"      if n >= 4
                    else "three_level" if n == 3
                    else "2-tone"      if n == 2
                    else "two_level_HL"
                )
            else:
                phon["tone_system"] = "2-tone"

        # phonology.vowels: may be a nested dict {segments:[...]}
        if isinstance(phon, dict):
            vowels = phon.get("vowels")
            if isinstance(vowels, dict):
                phon["vowels"] = vowels.get("segments") or []
            consonants = phon.get("consonants")
            if isinstance(consonants, dict):
                phon["consonants"] = consonants.get("segments") or []

        # ── 5. VERB SYSTEM ─────────────────────────────────────────────
        # morphology.verb_system -> verb_system  (morph wrapper)
        if "morphology" in raw:
            morph = raw.pop("morphology")
            if "noun_classes" not in raw and "noun_classes" in morph:
                raw["noun_classes"] = morph["noun_classes"]
            if "concord_systems" not in raw and "concord_systems" in morph:
                raw["concord_systems"] = morph["concord_systems"]
            if "verb_system" not in raw and "verb_system" in morph:
                raw["verb_system"] = morph["verb_system"]

        # Within verb_system: lift verbal_system_components.tam and
        # derivational_extensions up to the top of verb_system where the
        # normalizer's _normalize_canonical expects them.
        vs = raw.get("verb_system")
        if isinstance(vs, dict):
            vsc = vs.get("verbal_system_components") or {}
            if isinstance(vsc, dict):
                # TAM markers: verbal_system_components.tam -> verb_system.tam_markers
                # Keep as the dict keyed by TAM id — the normalizer handles both
                if "tam_markers" not in vs and "tam" in vsc:
                    vs["tam_markers"] = vsc["tam"]   # dict; canonical normalizer gets list
                # Derivational extensions: derivational_extensions -> verb_extensions
                if "verb_extensions" not in vs and "derivational_extensions" in vsc:
                    vs["verb_extensions"] = vsc["derivational_extensions"]

        # ── 6. TOKENIZATION ────────────────────────────────────────────
        if "tokenization" not in raw:
            raw["tokenization"] = {"word_boundary_pattern": r"\s+"}
        else:
            tok = raw["tokenization"]
            if isinstance(tok, dict) and "word_boundary_pattern" not in tok:
                # chitonga.yaml uses 'word_boundary' not 'word_boundary_pattern'
                wb = tok.get("word_boundary")
                tok["word_boundary_pattern"] = str(wb) if wb else r"\s+"

        return raw
        
    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def config(self) -> GrammarConfig:
        """The ``GrammarConfig`` used to initialise this loader instance."""
        return self._config

    @property
    def loader_version(self) -> str:
        """
        Running GGT loader version string (e.g. ``"1.0.0"``).

        This is the value against which grammar compatibility windows are
        checked at load time.
        """
        return LOADER_VERSION

    # ------------------------------------------------------------------
    # Public API — 14 methods
    # ------------------------------------------------------------------

    def get_metadata(self) -> GrammarMetadata:
        """
        Return version and identity metadata for the loaded grammar.

        Returns
        -------
        GrammarMetadata
            Frozen dataclass with ``language``, ``iso_code``, ``guthrie``,
            ``grammar_version``, ``min_loader_version``,
            ``max_loader_version``, and ``verify_count``.

        Examples
        --------
        >>> meta = loader.get_metadata()
        >>> meta.language
        'chitonga'
        >>> meta.iso_code
        'toi'
        """
        return self._parsed.metadata

    def get_noun_classes(self, active_only: bool = True) -> List[NounClass]:
        """
        Return all noun classes, sorted by NC number.

        Parameters
        ----------
        active_only : bool
            When ``True`` (default) only classes with ``active=True`` are
            included.  Pass ``False`` to include archaic/vestigial classes.

        Returns
        -------
        List[NounClass]
            Sorted by numeric NC suffix: NC1, NC1a, NC2, NC2a, …, NC18.

        Examples
        --------
        >>> [nc.id for nc in loader.get_noun_classes()[:4]]
        ['NC1', 'NC1a', 'NC2', 'NC2a']
        """
        ncs = list(self._parsed.noun_classes.values())
        if active_only:
            ncs = [nc for nc in ncs if nc.active]
        ncs.sort(key=lambda nc: self._nc_sort_key(nc.id))
        return ncs

    def get_noun_class(self, nc_id: str) -> NounClass:
        """
        Return a single noun class by its identifier.

        Parameters
        ----------
        nc_id : str
            Noun-class identifier (case-sensitive), e.g. ``"NC1"``,
            ``"NC9"``, ``"NC1a"``.

        Returns
        -------
        NounClass

        Raises
        ------
        NounClassNotFoundError
            If ``nc_id`` is not present in the grammar.

        Examples
        --------
        >>> nc1 = loader.get_noun_class("NC1")
        >>> nc1.prefix
        'mu-'
        """
        nc = self._parsed.noun_classes.get(nc_id)
        if nc is None:
            available = sorted(
                self._parsed.noun_classes.keys(),
                key=self._nc_sort_key,
            )
            raise NounClassNotFoundError(
                nc_id=nc_id,
                available_classes=available,
                language=self._config.language,
            )
        return nc

    def get_subject_concords(self) -> ConcordSet:
        """
        Return the subject-concord paradigm.

        Convenience wrapper for ``get_concords("subject_concords")``.

        Returns
        -------
        ConcordSet

        Raises
        ------
        ConcordTypeNotFoundError
            If the grammar does not declare a subject-concord paradigm.

        Examples
        --------
        >>> sc = loader.get_subject_concords()
        >>> sc.entries["NC3"]
        'u'
        """
        return self.get_concords("subject_concords")

    def get_object_concords(self) -> ConcordSet:
        """
        Return the object-concord paradigm.

        Convenience wrapper for ``get_concords("object_concords")``.

        Returns
        -------
        ConcordSet

        Raises
        ------
        ConcordTypeNotFoundError
            If the grammar does not declare an object-concord paradigm.

        Examples
        --------
        >>> oc = loader.get_object_concords()
        >>> oc.entries["NC7"]
        'ci'
        """
        return self.get_concords("object_concords")

    def get_concords(self, concord_type: str) -> ConcordSet:
        """
        Return a named concord paradigm.

        Parameters
        ----------
        concord_type : str
            A concord-type key as returned by ``get_all_concord_types()``,
            e.g. ``"possessive_concords"``,
            ``"demonstrative_concords_proximal"``.

        Returns
        -------
        ConcordSet

        Raises
        ------
        ConcordTypeNotFoundError
            If ``concord_type`` is not present in the grammar.

        Examples
        --------
        >>> poss = loader.get_concords("possessive_concords")
        >>> poss.entries["NC1"]
        'wa'
        """
        cs = self._parsed.concord_systems.get(concord_type)
        if cs is None:
            available = self.get_all_concord_types()
            raise ConcordTypeNotFoundError(
                concord_type=concord_type,
                available_types=available,
                language=self._config.language,
            )
        return cs

    def get_all_concord_types(self) -> List[str]:
        """
        Return the names of all available concord paradigms.

        Returns
        -------
        List[str]
            Alphabetically sorted list of concord-type identifiers.

        Examples
        --------
        >>> "subject_concords" in loader.get_all_concord_types()
        True
        """
        return sorted(self._parsed.concord_systems.keys())

    def get_tam_markers(self) -> List[TAMMarker]:
        """
        Return all TAM markers in YAML declaration order.

        Returns
        -------
        List[TAMMarker]

        Examples
        --------
        >>> tams = loader.get_tam_markers()
        >>> tams[0].id
        'TAM_PRES'
        """
        return list(self._parsed.tam_markers)

    def get_extensions(self) -> List[VerbExtension]:
        """
        Return all verb extensions in YAML declaration order.

        Returns
        -------
        List[VerbExtension]

        Examples
        --------
        >>> exts = loader.get_extensions()
        >>> exts[0].id
        'APPL'
        >>> exts[0].zone
        'Z1'
        """
        return list(self._parsed.verb_extensions)

    def get_verb_template(self) -> Dict[str, Any]:
        """
        Return the verb-system template dict as a deep copy.

        This is the **only** public method that returns a raw ``dict``.
        The spec explicitly types the return value as ``Dict[str, Any]``
        because the verb template is a free-form structure that varies by
        language and schema version.  A deep copy is returned on every call
        to prevent callers from mutating internal loader state.

        Returns
        -------
        Dict[str, Any]
            Deep copy of the ``verb_system`` sub-dict from the YAML.
        """
        return copy.deepcopy(self._parsed.verb_template)

    def get_verb_slots(self) -> List[VerbSlot]:
        """
        Return all verb template slots, sorted by position (ascending).

        Returns
        -------
        List[VerbSlot]
            SLOT1 … SLOT11 in positional order.

        Examples
        --------
        >>> slots = loader.get_verb_slots()
        >>> slots[0].id
        'SLOT1'
        >>> slots[2].obligatory   # SLOT3 = subject concord
        True
        """
        return list(self._parsed.verb_slots)

    def get_patterns(self) -> List[DerivationalPattern]:
        """
        Return all derivational patterns in YAML declaration order.

        Returns
        -------
        List[DerivationalPattern]

        Examples
        --------
        >>> pats = loader.get_patterns()
        >>> pats[0].id
        'DIMINUTIVE_FORMATION'
        """
        return list(self._parsed.derivational_patterns)

    def get_phonology(self) -> PhonologyRules:
        """
        Return the phonological inventory and rule set.

        Returns
        -------
        PhonologyRules

        Examples
        --------
        >>> phon = loader.get_phonology()
        >>> phon.vowels
        ['i', 'e', 'a', 'o', 'u']
        """
        return self._parsed.phonology

    def get_tokenization_rules(self) -> TokenizationRules:
        """
        Return the language-specific tokenization rules.

        Returns
        -------
        TokenizationRules

        Examples
        --------
        >>> rules = loader.get_tokenization_rules()
        >>> rules.clitic_boundaries
        ['+', '-']
        """
        return self._parsed.tokenization

    def list_verify_flags(self) -> List[VerifyFlag]:
        """
        Return all *unresolved* VERIFY flags from the grammar YAML.

        Resolved flags (``VerifyFlag.resolved == True``) are not included.
        Returns an empty list when the grammar is fully verified.

        In ``strict_mode``, any unresolved flag causes ``__init__`` to raise
        ``UnverifiedFormError``; this method therefore only returns non-empty
        results when ``strict_mode=False``.

        Returns
        -------
        List[VerifyFlag]

        Examples
        --------
        >>> flags = loader.list_verify_flags()
        >>> len(flags)
        0
        """
        return [f for f in self._parsed.verify_flags if not f.resolved]

    # ------------------------------------------------------------------
    # Class-level utilities
    # ------------------------------------------------------------------

    @classmethod
    def list_supported_languages(cls) -> List[str]:
        """
        Return the language ids registered in the GGT toolkit.

        Returns
        -------
        List[str]
            Alphabetically sorted list, e.g.
            ``["chibemba", "chitonga", "chinyanja", ...]``.
        """
        from gobelo_grammar_toolkit.core.registry import list_languages

        return list_languages()

    # ------------------------------------------------------------------
    # Private: YAML loading
    # ------------------------------------------------------------------

    def _load_embedded_yaml(self, language: str) -> Dict[str, Any]:
        """
        Load a grammar YAML from the package's embedded ``languages/`` dir.

        Uses ``importlib.resources.files()`` (Python ≥ 3.9) when available;
        falls back to ``importlib.resources.open_text()`` for older runtimes.
        Both paths work with installed wheels and zip archives.
        """
        filename = get_yaml_filename(language)
        package = "gobelo_grammar_toolkit.languages"

        if _HAS_FILES_API:
            ref = _importlib_resources.files(package).joinpath(filename)
            text = ref.read_text(encoding="utf-8")
        else:
            with _importlib_resources.open_text(  # type: ignore[attr-defined]
                package, filename, encoding="utf-8"
            ) as fh:
                text = fh.read()

        raw = _yaml.safe_load(text)

        if not isinstance(raw, dict):
            raise ValueError(
                f"Embedded grammar '{filename}' did not parse to a YAML "
                f"mapping; got {type(raw).__name__}."
            )
        return raw

    def _load_external_yaml(self, path: Path) -> Dict[str, Any]:
        """
        Load a grammar YAML from an arbitrary filesystem path.

        Raises
        ------
        FileNotFoundError
            If ``path`` does not exist (checked before calling this method,
            but re-raised here for completeness).
        yaml.YAMLError
            If the file cannot be parsed.
        ValueError
            If the parsed YAML is not a mapping.
        """
        with open(path, "r", encoding="utf-8") as fh:
            raw = _yaml.safe_load(fh)

        if not isinstance(raw, dict):
            raise ValueError(
                f"Grammar file '{path}' did not parse to a YAML mapping; "
                f"got {type(raw).__name__}."
            )
        return raw

    # ------------------------------------------------------------------
    # Private: helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _nc_sort_key(nc_id: str) -> tuple:
        """
        Stable sort key for noun-class identifiers.

        Numeric parts sort as integers (NC2 < NC10), sub-class suffixes
        sort after the base (NC1 < NC1a < NC2).

        Examples
        --------
        >>> GobeloGrammarLoader._nc_sort_key("NC1")
        (1, '')
        >>> GobeloGrammarLoader._nc_sort_key("NC1a")
        (1, 'a')
        >>> GobeloGrammarLoader._nc_sort_key("NC2b")
        (2, 'b')
        >>> GobeloGrammarLoader._nc_sort_key("NC10")
        (10, '')
        """
        m = _NC_NUMERIC_RE.search(nc_id)
        if m:
            return (int(m.group(1)), nc_id[m.end():])
        return (9999, nc_id)


# ---------------------------------------------------------------------------
# Module-level helper: lightweight validation for the extended YAML format
# ---------------------------------------------------------------------------

_VERIFY_INLINE_RE = re.compile(r"VERIFY\s*:", re.IGNORECASE)


def _validate_extended(
    raw: Dict[str, Any],
    config: "GrammarConfig",  # type: ignore[name-defined]
) -> List[VerifyFlag]:
    """
    Lightweight validation pass for the chiTonga extended YAML format.

    The extended format (top-level key ``chitonga_grammar``) does not
    conform to the GGT-canonical flat schema, so the full
    ``GrammarValidator`` is not applicable.  This function:

    * Checks the ``chitonga_grammar`` key is present and is a mapping.
    * Recursively scans all string values for inline ``VERIFY:`` annotations
      and constructs ``VerifyFlag`` objects for any found.
    * Respects ``strict_mode``: raises ``UnverifiedFormError`` if any
      unresolved flags are present.

    Parameters
    ----------
    raw : Dict[str, Any]
        Full parsed YAML dict (must contain ``chitonga_grammar``).
    config : GrammarConfig
        Loader configuration (used for ``strict_mode`` and language name).

    Returns
    -------
    List[VerifyFlag]
        Zero or more ``VerifyFlag`` objects (all with ``resolved=False``).
    """
    from gobelo_grammar_toolkit.core.exceptions import UnverifiedFormError
    from gobelo_grammar_toolkit.core.validator import GGTWarning
    import warnings as _warnings

    flags: List[VerifyFlag] = []
    _scan_for_verify(raw, path="", flags=flags)

    if flags and config.strict_mode:
        raise UnverifiedFormError(
            flags=flags,
            language=config.language,
        )
    if flags:
        _warnings.warn(
            f"Grammar '{config.language}' loaded with {len(flags)} "
            f"unresolved VERIFY flag(s).  Call list_verify_flags() for details.",
            GGTWarning,
            stacklevel=4,
        )

    return flags


def _scan_for_verify(
    node: Any,
    path: str,
    flags: List[VerifyFlag],
    max_depth: int = 30,
) -> None:
    """
    Recursively scan ``node`` for inline ``VERIFY:`` annotations.

    Parameters
    ----------
    node : Any
        The current YAML node (dict, list, scalar).
    path : str
        Dot-notation path to this node, for the ``VerifyFlag.field_path``.
    flags : List[VerifyFlag]
        Accumulator list; matched flags are appended here.
    max_depth : int
        Guard against pathologically deep YAML structures.
    """
    if max_depth <= 0:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            child_path = f"{path}.{k}" if path else str(k)
            _scan_for_verify(v, child_path, flags, max_depth - 1)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _scan_for_verify(item, f"{path}[{i}]", flags, max_depth - 1)
    elif isinstance(node, str) and _VERIFY_INLINE_RE.search(node):
        m = re.search(r"VERIFY\s*:\s*(.*)", node, re.IGNORECASE | re.DOTALL)
        note = m.group(1).strip() if m else node
        # value before the annotation
        current_val = re.sub(r"\s*VERIFY\s*:.*", "", node, flags=re.IGNORECASE | re.DOTALL).strip()
        flags.append(
            VerifyFlag(
                field_path=path,
                current_value=current_val,
                note=note,
                suggested_source="",
                resolved=False,
            )
        )
