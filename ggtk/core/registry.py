"""
core/registry.py
================
Language registry for the Gobelo (Bantu) Grammar Toolkit (GGT).

The registry is the **single source of truth** for which languages are
embedded in the package and what YAML filename each one uses.  It is kept
minimal by design: one private dict that maps the canonical language
identifier to the filename within ``ggtk/languages/``.

No grammar data, YAML parsing, or model instantiation lives here.  The
registry's only job is name → filename resolution and resource probing.

Design principles
-----------------
* **Zero grammar knowledge** — no imports from the rest of GGT; prevents
  circular-import cycles.
* **Single addition point** — adding a new language requires one dict
  entry here plus the YAML file.  See maintainer checklist below.
* **Stable keys** — identifiers must never be renamed; that would be a
  breaking API change requiring a MAJOR version bump.
* **Lazy resource probing** — ``probe_language_resource()`` uses
  ``importlib.resources`` to verify the YAML is accessible in the
  installed package, giving an early-failure diagnostic.

``importlib.resources`` strategy
---------------------------------
Python ≥ 3.9: ``importlib.resources.files()`` → ``Traversable``.  Works
for wheel installs, editable installs, zip archives, and plain checkouts.
Python 3.8: fallback to ``importlib.resources.is_resource()`` / ``open_text()``.

The loader (``core/loader.py``) calls ``files()`` directly for the actual
read; the registry only *probes* resource existence here — this keeps all
resource-resolution logic co-located without duplicating I/O at load time.

Adding a language (maintainer checklist)
-----------------------------------------
1. Create ``ggtk/languages/<iso_code>.yaml``
   (follow the ggtk-canonical schema; filename = ISO 639-3 code).
2. Add ``"<iso_code>"`` to ``_LANGUAGE_REGISTRY`` (value is auto-derived
   as ``f"{iso_code}.yaml"`` — no separate mapping needed).
3. Add the ISO code, canonical name, and aliases to ``ggtk/__init__.py``
   ``LANGUAGE_REGISTRY``.
4. Run: ``python -m pytest tests/ -q``
5. Run: ``python -m ggtk.core.registry probe <iso_code>``
6. Update ``CHANGELOG.md`` under ``## [Unreleased] → Added``.
7. Bump version in ``pyproject.toml`` (MINOR if new language, PATCH if
   data-only fix).

Language identifiers
--------------------
ISO 639-3 codes are used directly as identifiers throughout ggtk.
Alias resolution (e.g. "chichewa" → "nya") is handled in ``ggtk/__init__.py``.

    ISO 639-3   Guthrie   Canonical name   Notes
    ---------   -------   --------------   -----
    toi         M.64      Chitonga         Valley/Lake Tonga (Zambia)
    bem         M.42      Bemba            Northern Zambia
    nya         N.31      Nyanja           Also Chichewa/Nyanja
    lue         K.14      Luvale           North-West Zambia / Angola
    kqn         L.41      Kaonde           North-West Zambia
    loz         K.21      SiLozi           Western Province, Zambia
    lun         L.52      Lunda            North-West Zambia
"""

from __future__ import annotations

import importlib.resources as _resources
from typing import Dict, FrozenSet, List, Optional

__all__ = [
    "SUPPORTED_LANGUAGES",
    "is_registered",
    "get_yaml_filename",
    "list_languages",
    "probe_language_resource",
    "get_resource_path",
]

# ---------------------------------------------------------------------------
# Registry dict  — only place language IDs are defined
# ---------------------------------------------------------------------------

# Keys are ISO 639-3 codes. Values are derived as f"{code}.yaml" —
# stored explicitly here so the dict remains the single source of truth
# for which languages are embedded, independent of __init__.py.
_LANGUAGE_REGISTRY: Dict[str, str] = {
    "bem": "bem.yaml",  # Bemba
    "kqn": "kqn.yaml",  # Kaonde
    "loz": "loz.yaml",  # SiLozi
    "lue": "lue.yaml",  # Luvale
    "lun": "lun.yaml",  # Lunda
    "nya": "nya.yaml",  # Nyanja / Chichewa
    "toi": "toi.yaml",  # Chitonga
}

#: Package where YAML files are embedded as ``importlib.resources`` data.
_LANGUAGES_PACKAGE: str = "ggtk.languages"

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Frozenset of all registered ISO 639-3 codes (stable within MAJOR).
SUPPORTED_LANGUAGES: FrozenSet[str] = frozenset(_LANGUAGE_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_registered(language: str) -> bool:
    """
    Return ``True`` if ``language`` is present in the registry.

    Case-sensitive.  ``GrammarConfig.__post_init__`` normalises to
    lowercase before calling here.

    Examples
    --------
    >>> is_registered("toi")
    True
    >>> is_registered("swahili")
    False
    """
    return language in _LANGUAGE_REGISTRY


def get_yaml_filename(language: str) -> Optional[str]:
    """
    Return the YAML resource filename for a registered language, or ``None``.

    Returns the bare filename (e.g. ``"toi.yaml"``), not a path.
    The loader resolves it via ``importlib.resources.files()``.

    Examples
    --------
    >>> get_yaml_filename("toi")
    'toi.yaml'
    >>> get_yaml_filename("swahili") is None
    True
    """
    return _LANGUAGE_REGISTRY.get(language)


def list_languages() -> List[str]:
    """
    Return a sorted list of all registered language identifiers.

    Examples
    --------
    >>> list_languages()
    ['bem', 'kqn', 'loz', 'lue', 'lun', 'nya', 'toi']
    """
    return sorted(_LANGUAGE_REGISTRY.keys())


def probe_language_resource(language: str) -> bool:
    """
    Return ``True`` if the YAML resource for ``language`` is accessible.

    Verifies the embedded file is reachable in the installed package
    *without* reading it.  Useful for build/CI diagnostics and the
    ``ggt probe`` CLI command.

    A ``False`` result typically means the ``languages/*.yaml`` glob in
    ``pyproject.toml`` did not pick up the file during packaging.

    Examples
    --------
    >>> probe_language_resource("toi")   # file must exist on disk
    True
    >>> probe_language_resource("klingon")
    False
    """
    filename = _LANGUAGE_REGISTRY.get(language)
    if filename is None:
        return False
    try:
        if hasattr(_resources, "files"):
            resource = _resources.files(_LANGUAGES_PACKAGE).joinpath(filename)
            return resource.is_file()
        # Python 3.8 fallback
        return _resources.is_resource(_LANGUAGES_PACKAGE, filename)  # type: ignore[attr-defined]
    except (ModuleNotFoundError, FileNotFoundError, TypeError):
        return False


def get_resource_path(language: str):
    """
    Return a ``Traversable`` reference to the YAML resource for ``language``.

    The returned object supports ``.read_text(encoding)`` and ``.is_file()``
    and works for wheel, zip, and source-checkout installs.

    This centralises the ``importlib.resources.files()`` call so the
    loader never needs to import ``importlib.resources`` for the common path.

    Raises
    ------
    KeyError
        If ``language`` is not in the registry.

    Examples
    --------
    >>> ref = get_resource_path("toi")
    >>> text = ref.read_text(encoding="utf-8")
    """
    filename = _LANGUAGE_REGISTRY[language]  # KeyError if not registered
    return _resources.files(_LANGUAGES_PACKAGE).joinpath(filename)


# ---------------------------------------------------------------------------
# __main__ probe entrypoint
# python -m ggtk.core.registry [list | probe <lang>]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    argv = sys.argv[1:]

    if not argv or argv[0] == "list":
        print("Registered languages:")
        for lang in list_languages():
            ok = probe_language_resource(lang)
            mark = "✓" if ok else "✗ MISSING"
            print(f"  {mark}  {lang:<14}  {get_yaml_filename(lang)}")

    elif len(argv) == 2 and argv[0] == "probe":
        lang = argv[1]
        if not is_registered(lang):
            print(f"ERROR: '{lang}' not registered.  Known: {list_languages()}", file=sys.stderr)
            sys.exit(1)
        if probe_language_resource(lang):
            print(f"OK  {lang!r}  →  {get_yaml_filename(lang)}")
        else:
            print(f"MISSING  {lang!r}  →  {get_yaml_filename(lang)}", file=sys.stderr)
            sys.exit(2)

    else:
        print("Usage: python -m ggtk.core.registry [list | probe <language>]")
        sys.exit(1)
