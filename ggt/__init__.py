"""
Gobelo Grammar Toolkit (GGT)
=============================
Canonical language registry with ISO 639-3 alias resolution.

All apps and tools must identify languages by ISO 639-3 code internally.
YAML grammar files in ggt/languages/ are named by ISO code: {code}.yaml.
Use resolve_language() to normalise any user-supplied name or spelling.

Supported languages (7):
    bem  Bemba        toi  Chitonga     nya  Nyanja
    lue  Luvale       lun  Lunda        kqn  Kaonde
    loz  SiLozi

Not yet in scope:
    tum  Tumbuka  (corpus only — no GGT YAML)
"""

from ggt.core.loader import GobeloGrammarLoader  # noqa: F401  (re-exported)
from ggt.core.exceptions import LanguageNotFoundError

__version__ = "0.2.0"
__all__ = [
    "LANGUAGE_REGISTRY",
    "resolve_language",
    "language_info",
    "GobeloGrammarLoader",
    "LanguageNotFoundError",
]

# ---------------------------------------------------------------------------
# Canonical registry
#
# Structure per entry:
#   iso_code → {
#       "name"    : canonical display name,
#       "aliases" : list of all known alternate names / spellings (lowercase),
#   }
#
# YAML files are always ggt/languages/{iso_code}.yaml — no separate mapping
# needed. Alias lists reflect real-world variation found in Zambian govt
# documents, academic literature, and community usage. Kept lowercase —
# matching is always case-insensitive via resolve_language().
# ---------------------------------------------------------------------------
LANGUAGE_REGISTRY: dict[str, dict] = {
    "bem": {
        "name": "Bemba",
        "aliases": [
            "bemba",
            "chibemba",
            "icibemba",
            "wemba",
            "chiwemba",
            "ibemba",
        ],
    },
    "toi": {
        "name": "Chitonga",
        "aliases": [
            "chitonga",
            "tonga",
            "citonga",
            "valley tonga",
            "zambezi tonga",
            "tonga of zambia",
            "tonga of the plateau",
        ],
    },
    "nya": {
        "name": "Nyanja",
        "aliases": [
            "nyanja",
            "chinyanja",
            "chichewa",
            "nyanja/chichewa",
            "chichewa/nyanja",
            "chicheŵa",
            "chewa",
            "cewa",
            "mang'anja",
            "manganja",
        ],
    },
    "lue": {
        "name": "Luvale",
        "aliases": [
            "luvale",
            "chiluvale",
            "lovale",
            "lwena",
            "luena",
            "luwena",
        ],
    },
    "lun": {
        "name": "Lunda",
        "aliases": [
            "lunda",
            "chilunda",
            "ruund",
            "chibinda",
            "lunda-kazembe",
        ],
    },
    "kqn": {
        "name": "Kaonde",
        "aliases": [
            "kaonde",
            "chikaonde",
            "kahonde",
            "cikaonde",
        ],
    },
    "loz": {
        "name": "SiLozi",
        "aliases": [
            "silozi",
            "lozi",
            "kololo",
            "rozi",
            "rotse",
            "barotse",
            "si lozi",
        ],
    },
}

# ---------------------------------------------------------------------------
# Flat alias index — built once at import time
# Maps every alias (and iso code itself) → iso_code
# ---------------------------------------------------------------------------
_ALIAS_INDEX: dict[str, str] = {}

for _code, _entry in LANGUAGE_REGISTRY.items():
    _ALIAS_INDEX[_code] = _code                    # iso code resolves to itself
    _ALIAS_INDEX[_entry["name"].lower()] = _code   # canonical name resolves too
    for _alias in _entry["aliases"]:
        _ALIAS_INDEX[_alias.lower()] = _code


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_language(name: str) -> str:
    """
    Resolve any language name or alias to its canonical ISO 639-3 code.

    Matching is case-insensitive and exact — no partial or fuzzy matching.
    Pass an ISO code, canonical name, or any known alias.

    Parameters
    ----------
    name : str
        Language identifier supplied by user, data file, or config.

    Returns
    -------
    str
        ISO 639-3 code, e.g. ``"bem"``, ``"toi"``, ``"nya"``.

    Raises
    ------
    LanguageNotFoundError
        If ``name`` cannot be matched to any registered language.

    Examples
    --------
    >>> resolve_language("icibemba")
    'bem'
    >>> resolve_language("Chichewa")
    'nya'
    >>> resolve_language("silozi")
    'loz'
    >>> resolve_language("BEM")
    'bem'
    >>> resolve_language("tonga")
    'toi'
    """
    key = name.strip().lower()
    if key in _ALIAS_INDEX:
        return _ALIAS_INDEX[key]
    raise LanguageNotFoundError(
        f"Unknown language: '{name}'.\n"
        f"Supported ISO codes: {sorted(LANGUAGE_REGISTRY.keys())}.\n"
        f"Call ggt.language_info('<code>') to see all aliases per language,\n"
        f"or inspect ggt.LANGUAGE_REGISTRY for the full registry."
    )


def language_info(name: str) -> dict:
    """
    Return the full registry entry for a language.

    Accepts an ISO code, canonical name, or any known alias.

    Parameters
    ----------
    name : str
        Any resolvable language identifier.

    Returns
    -------
    dict
        Registry entry with keys ``name``, ``yaml``, ``aliases``.

    Examples
    --------
    >>> ggt.language_info("chichewa")
    {'name': 'Nyanja', 'yaml': 'chinyanja', 'aliases': [...]}
    """
    return LANGUAGE_REGISTRY[resolve_language(name)]


def list_languages() -> list[dict]:
    """
    Return a summary list of all supported languages.

    Returns
    -------
    list of dict
        Each dict has keys ``iso`` and ``name``.

    Examples
    --------
    >>> for lang in ggt.list_languages():
    ...     print(lang["iso"], lang["name"])
    bem Bemba
    toi Chitonga
    ...
    """
    return [
        {"iso": code, "name": entry["name"]}
        for code, entry in LANGUAGE_REGISTRY.items()
    ]
