#!/usr/bin/env python3
"""
scripts/add_language.py
========================
Scaffold a new grammar YAML from the canonical template and register
the language in the ggtk registry.

Run:
    python scripts/add_language.py bem
    python scripts/add_language.py kqn --guthrie L.41
    python scripts/add_language.py loz --display SiLozi

    # Unknown language (not in _KNOWN):
    python scripts/add_language.py xyz --guthrie X.00 --display MyLang

Steps performed:
    1. Resolve ISO code → display name, Guthrie from _KNOWN (or CLI flags).
    2. Check the ISO code is not already registered.
    3. Copy canonical_grammar_template.yaml → languages/<iso_code>.yaml
    4. Substitute the language, iso_code, and guthrie placeholders.
    5. Append the ISO code → filename mapping to registry.py.
    6. Print next steps for the grammar author (including __init__.py reminder).

The generated YAML is a VALID stub that the loader can parse immediately —
it will raise 0 errors (but many VERIFY flags until data is filled in).

NOTE: ISO 639-3 codes are used as the primary identifier throughout ggtk.
      YAML files are always named {iso_code}.yaml.
      After running this script, also add the language to ggtk/__init__.py
      LANGUAGE_REGISTRY with its canonical name and all known aliases.
"""

from __future__ import annotations

import sys
import re
import argparse
from pathlib import Path
from datetime import date

# ── path bootstrap ─────────────────────────────────────────────────
_SCRIPT = Path(__file__).resolve().parent
_REPO   = _SCRIPT.parent
_GGTK    = _REPO / "ggtk"
for p in (_GGTK,):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

_LANGUAGES_DIR = _GGTK / "languages"
_REGISTRY_PY   = _GGTK / "core" / "registry.py"
_INIT_PY       = _GGTK / "__init__.py"
_TEMPLATE      = _REPO / "outputs" / "ggtk-core" / "canonical_grammar_template.yaml"

if not _TEMPLATE.exists():
    _TEMPLATE = Path("/mnt/user-data/outputs/ggtk-core/canonical_grammar_template.yaml")

# ── Known languages keyed by ISO 639-3 code ────────────────────────
# This mirrors ggtk/__init__.py LANGUAGE_REGISTRY — keep in sync.
_KNOWN: dict[str, dict] = {
    "bem": dict(guthrie="M.42", display="Bemba"),
    "toi": dict(guthrie="M.64", display="Chitonga"),
    "nya": dict(guthrie="N.31", display="Nyanja"),
    "loz": dict(guthrie="K.21", display="SiLozi"),
    "lue": dict(guthrie="K.14", display="Luvale"),
    "lun": dict(guthrie="L.52", display="Lunda"),
    "kqn": dict(guthrie="L.41", display="Kaonde"),
}


def _ok(msg: str)   -> None: print(f"  \033[32m✓\033[0m  {msg}")
def _err(msg: str)  -> None: print(f"  \033[31m✗\033[0m  {msg}", file=sys.stderr)
def _info(msg: str) -> None: print(f"  \033[36m→\033[0m  {msg}")
def _warn(msg: str) -> None: print(f"  \033[33m!\033[0m  {msg}")


def register_language(iso_code: str) -> bool:
    """
    Add an ``"<iso_code>": "<iso_code>.yaml"`` entry to _LANGUAGE_REGISTRY
    in registry.py.  Idempotent — does nothing if already registered.
    """
    if not _REGISTRY_PY.exists():
        _err(f"Registry file not found: {_REGISTRY_PY}")
        return False

    src = _REGISTRY_PY.read_text(encoding="utf-8")

    # Already registered?
    if f'"{iso_code}"' in src or f"'{iso_code}'" in src:
        _info(f"'{iso_code}' already in registry.py — skipping.")
        return True

    # Find the _LANGUAGE_REGISTRY dict and insert before closing brace
    pattern = re.compile(r'(_LANGUAGE_REGISTRY\s*=\s*\{[^}]*?)(\})', re.DOTALL)
    m = pattern.search(src)
    if not m:
        _err(
            "Could not locate _LANGUAGE_REGISTRY dict in registry.py.\n"
            "Add the entry manually:\n"
            f'    "{iso_code}": "{iso_code}.yaml",  # {_KNOWN.get(iso_code, {}).get("display", "")}'
        )
        return False

    display = _KNOWN.get(iso_code, {}).get("display", "")
    comment = f"  # {display}" if display else ""
    new_entry = f'    "{iso_code}": "{iso_code}.yaml",{comment}\n'
    new_src = src[:m.start(2)] + new_entry + src[m.start(2):]
    _REGISTRY_PY.write_text(new_src, encoding="utf-8")
    return True


def scaffold_grammar(
    iso_code: str,
    guthrie: str,
    display_name: str,
    force: bool = False,
) -> Path:
    """
    Copy the canonical template to languages/<iso_code>.yaml and
    substitute placeholder values.
    """
    if not _TEMPLATE.exists():
        raise FileNotFoundError(f"Canonical template not found: {_TEMPLATE}")

    _LANGUAGES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _LANGUAGES_DIR / f"{iso_code}.yaml"

    if out_path.exists() and not force:
        raise FileExistsError(
            f"{out_path} already exists.  Use --force to overwrite."
        )

    template = _TEMPLATE.read_text(encoding="utf-8")

    # Substitute template placeholders (template is based on bem/Bemba)
    replacements = {
        '"bem"':     f'"{iso_code}"',
        '"M.42"':    f'"{guthrie}"',
        '"Bemba"':   f'"{display_name}"',
        '"1.0.0"':   '"1.0.0"',          # grammar_version stays at 1.0.0
        "2025-01-01": str(date.today()),
    }
    result = template
    for old, new in replacements.items():
        result = result.replace(old, new, 1)

    header = (
        f"# {'='*60}\n"
        f"# {display_name} — ggtk Grammar YAML\n"
        f"# Generated by scripts/add_language.py on {date.today()}\n"
        f"# ISO 639-3: {iso_code}   Guthrie: {guthrie}\n"
        f"#\n"
        f"# NEXT STEPS FOR GRAMMAR AUTHOR:\n"
        f"#   1. Fill every REQUIRED field (search for TODO or empty strings)\n"
        f"#   2. Replace VERIFY: placeholders with confirmed primary-source data\n"
        f"#   3. Run: python scripts/validate_grammar.py languages/{iso_code}.yaml\n"
        f"#   4. Commit when all errors are resolved (VERIFY flags may remain)\n"
        f"# {'='*60}\n\n"
    )
    out_path.write_text(header + result, encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a new ggtk grammar YAML and register it",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "iso_code",
        help="ISO 639-3 code for the language (e.g. bem, toi, nya)",
    )
    parser.add_argument("--guthrie",     default=None, help="Guthrie code (e.g. M.42)")
    parser.add_argument("--display",     default=None, help="Display name (e.g. Bemba)")
    parser.add_argument("--force",       action="store_true", help="Overwrite existing YAML")
    parser.add_argument("--no-register", action="store_true", help="Skip editing registry.py")
    args = parser.parse_args()

    iso_code = args.iso_code.lower().strip()

    # Validate looks like an ISO 639-3 code (2–3 lowercase letters/digits)
    if not re.fullmatch(r"[a-z]{2,3}", iso_code):
        _err(
            f"'{iso_code}' does not look like an ISO 639-3 code "
            "(2–3 lowercase letters, e.g. 'bem', 'toi', 'nya')."
        )
        return 1

    # Resolve Guthrie and display name from _KNOWN defaults or CLI flags
    known = _KNOWN.get(iso_code, {})
    guthrie      = args.guthrie or known.get("guthrie")
    display_name = args.display or known.get("display") or iso_code.upper()

    if not guthrie:
        _err(
            f"--guthrie is required for unknown language '{iso_code}' "
            "(e.g. --guthrie M.42)"
        )
        return 1

    print(f"\nAdding language: {iso_code}")
    print(f"  Display:    {display_name}")
    print(f"  Guthrie:    {guthrie}")
    print()

    # Guard: already a YAML?
    out_path = _LANGUAGES_DIR / f"{iso_code}.yaml"
    if out_path.exists() and not args.force:
        _err(f"{out_path} already exists.  Use --force to overwrite.")
        return 1

    # 1. Scaffold YAML
    try:
        created = scaffold_grammar(iso_code, guthrie, display_name, force=args.force)
        _ok(f"Created: {created}")
    except Exception as e:
        _err(str(e))
        return 1

    # 2. Register in registry.py
    if not args.no_register:
        ok = register_language(iso_code)
        if ok:
            _ok(f"Registered '{iso_code}' → '{iso_code}.yaml' in registry.py")
        else:
            _err("registry.py edit failed — add the entry manually (see above).")

    # 3. Next steps
    print()
    print("Next steps:")
    _info(f"Edit YAML:      {out_path}")
    _info(f"Validate:       python scripts/validate_grammar.py languages/{iso_code}.yaml")
    _info(
        f"Reload check:   python -c \""
        f"from ggtk.core.loader import GobeloGrammarLoader; "
        f"from ggtk.core.config import GrammarConfig; "
        f"GobeloGrammarLoader(GrammarConfig(language='{iso_code}'))\""
    )
    print()
    _warn(
        f"Also add '{iso_code}' to ggtk/__init__.py LANGUAGE_REGISTRY with "
        f"its canonical name and all known aliases — alias resolution "
        f"(e.g. 'chichewa' → 'nya') is not automatic."
    )
    print()
    print(f"Sections to fill in {iso_code}.yaml:")
    print("  metadata        → language, iso_code, guthrie, grammar_version")
    print("  phonology       → vowels, consonants, tone_system, sandhi_rules")
    print("  noun_classes    → prefix, allomorphs, semantic_domain for each NC")
    print("  concord_systems → subject_concords, object_concords, possessive_concords")
    print("  verb_system     → tam_markers, verb_extensions, verb_slots")
    print("  tokenization    → word_boundary_pattern")
    return 0


if __name__ == "__main__":
    sys.exit(main())

