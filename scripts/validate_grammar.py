#!/usr/bin/env python3
"""
scripts/validate_grammar.py
============================
Validate a GGT grammar YAML file against the loader schema.

Reports all structural errors, version compatibility issues, and
unresolved VERIFY flags.  Exit code 0 = valid, 1 = invalid.

Usage:
    python scripts/validate_grammar.py languages/chitonga.yaml
    python scripts/validate_grammar.py languages/chibemba.yaml --strict
    python scripts/validate_grammar.py languages/ --all
    python scripts/validate_grammar.py --all              # default languages/ dir

Options:
    --strict    Treat unresolved VERIFY flags as errors (exit 1)
    --all       Validate every .yaml file in the target directory
    --quiet     Only print errors, not the section-by-section summary
    --json      Output a machine-readable JSON report to stdout
"""

from __future__ import annotations

import sys
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# ── path bootstrap ─────────────────────────────────────────────────
_SCRIPT = Path(__file__).resolve().parent
_REPO   = _SCRIPT.parent
_GGT    = _REPO / "ggt"
for p in (_GGT, Path("/mnt/user-data/uploads")):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gobelo_grammar_toolkit.core.config     import GrammarConfig
from gobelo_grammar_toolkit.core.loader     import GobeloGrammarLoader
from gobelo_grammar_toolkit.core.registry   import is_registered
from gobelo_grammar_toolkit.core.exceptions import (
    GGTError, LanguageNotFoundError,
    VersionIncompatibleError, SchemaValidationError,
)

# ── ANSI colours ───────────────────────────────────────────────────
_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"

def _c(text: str, color: str, quiet: bool = False) -> str:
    if quiet or not sys.stdout.isatty():
        return text
    return f"{color}{text}{_RESET}"


@dataclass
class ValidationReport:
    path:       Path
    language:   Optional[str]      = None
    valid:      bool               = False
    errors:     List[str]          = field(default_factory=list)
    warnings:   List[str]          = field(default_factory=list)
    flags:      List[str]          = field(default_factory=list)
    stats:      dict               = field(default_factory=dict)
    exception:  Optional[str]      = None


def validate_file(yaml_path: Path, strict: bool = False) -> ValidationReport:
    """
    Load a grammar YAML through the full GGT loader pipeline and collect
    all errors, warnings, and VERIFY flags into a report.
    """
    report = ValidationReport(path=yaml_path)

    # ── Step 1: detect language from filename ─────────────────────
    lang = yaml_path.stem   # e.g. "chitonga.yaml" → "chitonga"
    report.language = lang

    # ── Step 2: check registry ────────────────────────────────────
    if not is_registered(lang):
        report.errors.append(
            f"Language '{lang}' is not in the GGT registry. "
            f"Add it to gobelo_grammar_toolkit/core/registry.py before validating."
        )
        return report

    # ── Step 3: attempt full load ─────────────────────────────────
    try:
        cfg    = GrammarConfig(language=lang, override_path=str(yaml_path))
        loader = GobeloGrammarLoader(cfg)
    except VersionIncompatibleError as e:
        report.errors.append(f"Version incompatible: {e}")
        report.exception = type(e).__name__
        return report
    except SchemaValidationError as e:
        report.errors.append(f"Schema error: {e}")
        report.exception = type(e).__name__
        return report
    except GGTError as e:
        report.errors.append(f"Load error ({type(e).__name__}): {e}")
        report.exception = type(e).__name__
        return report
    except Exception as e:
        report.errors.append(f"Unexpected error: {type(e).__name__}: {e}")
        report.exception = type(e).__name__
        return report

    # ── Step 4: collect statistics ────────────────────────────────
    try:
        m       = loader.get_metadata()
        ncs     = loader.get_noun_classes(active_only=False)
        ncs_act = loader.get_noun_classes(active_only=True)
        tams    = loader.get_tam_markers()
        exts    = loader.get_extensions()
        cts     = loader.get_all_concord_types()
        slots   = loader.get_verb_slots()
        phon    = loader.get_phonology()
        flags   = loader.list_verify_flags()
        sc      = loader.get_subject_concords()
        oc      = loader.get_object_concords()

        report.stats = {
            "grammar_version":    m.grammar_version,
            "noun_class_count":   len(ncs),
            "active_nc_count":    len(ncs_act),
            "tam_count":          len(tams),
            "extension_count":    len(exts),
            "concord_type_count": len(cts),
            "slot_count":         len(slots),
            "tone_system":        phon.tone_system,
            "verify_flags":       len(flags),
            "sc_entry_count":     len(sc.entries),
            "oc_entry_count":     len(oc.entries),
        }

        # ── Step 5: structural warnings ───────────────────────────
        oblig = {s.id for s in slots if s.obligatory}
        for must in ("SLOT3", "SLOT8", "SLOT10"):
            if must not in oblig:
                report.warnings.append(
                    f"Expected {must} to be obligatory but it is not. "
                    "Check verb_slots section."
                )

        # Warn if subject_concords or object_concords is missing
        for ct_name in ("subject_concords", "object_concords"):
            if ct_name not in cts:
                report.warnings.append(
                    f"Concord type '{ct_name}' is missing from concord_systems. "
                    "MorphologicalAnalyzer requires this."
                )

        # ── Step 6: VERIFY flags ──────────────────────────────────
        for f in flags:
            msg = (
                f"VERIFY [{f.field_path}] = {f.current_value!r}  "
                f"→ {f.note or 'no note'}  "
                f"(source: {f.suggested_source or 'unspecified'})"
            )
            report.flags.append(msg)
            if strict:
                report.errors.append(f"Unresolved VERIFY flag: {msg}")

        report.valid = (len(report.errors) == 0)

    except GGTError as e:
        report.errors.append(f"Post-load error: {e}")

    return report


def print_report(report: ValidationReport, quiet: bool = False) -> None:
    """Pretty-print one validation report."""
    status = (_c("✓ VALID",   _GREEN, quiet) if report.valid
              else _c("✗ INVALID", _RED,   quiet))
    print(f"\n{_c(str(report.path), _BOLD, quiet)}")
    print(f"  Status:   {status}")
    if report.language:
        print(f"  Language: {report.language}")

    if report.stats and not quiet:
        s = report.stats
        print(f"  Grammar:  v{s.get('grammar_version','?')}  |  "
              f"{s.get('noun_class_count','?')} NCs  |  "
              f"{s.get('tam_count','?')} TAM  |  "
              f"{s.get('extension_count','?')} ext  |  "
              f"{s.get('concord_type_count','?')} concord types")
        print(f"  Phonology: tone={s.get('tone_system','?')}  |  "
              f"SC entries={s.get('sc_entry_count','?')}  |  "
              f"OC entries={s.get('oc_entry_count','?')}")

    for e in report.errors:
        print(f"  {_c('ERROR',   _RED,    quiet)}: {e}")
    for w in report.warnings:
        print(f"  {_c('WARN',    _YELLOW, quiet)}: {w}")
    for f in report.flags:
        print(f"  {_c('VERIFY',  _CYAN,   quiet)}: {f}")

    if not report.errors and not report.warnings and not report.flags:
        print(f"  {_c('No issues found.', _GREEN, quiet)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate GGT grammar YAML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("paths", nargs="*", help="YAML file(s) or directory to validate")
    parser.add_argument("--all",    action="store_true", help="Validate all .yaml files in target directory")
    parser.add_argument("--strict", action="store_true", help="Treat VERIFY flags as errors")
    parser.add_argument("--quiet",  action="store_true", help="Only print errors")
    parser.add_argument("--json",   action="store_true", help="Output JSON report")
    args = parser.parse_args()

    # Resolve targets
    targets: list[Path] = []
    input_paths = args.paths or ["languages"]
    for raw in input_paths:
        p = Path(raw)
        if p.is_dir() or args.all:
            search = p if p.is_dir() else Path("languages")
            targets.extend(sorted(search.glob("*.yaml")))
        elif p.exists():
            targets.append(p)
        else:
            print(f"Error: path not found: {raw}", file=sys.stderr)
            return 2

    if not targets:
        print("No grammar YAML files found.", file=sys.stderr)
        return 2

    # Validate each
    reports = [validate_file(t, strict=args.strict) for t in targets]

    if args.json:
        out = []
        for r in reports:
            out.append({
                "path":     str(r.path),
                "language": r.language,
                "valid":    r.valid,
                "errors":   r.errors,
                "warnings": r.warnings,
                "flags":    r.flags,
                "stats":    r.stats,
            })
        print(json.dumps(out, indent=2))
    else:
        for r in reports:
            print_report(r, quiet=args.quiet)

        # Summary line
        n_valid   = sum(1 for r in reports if r.valid)
        n_invalid = len(reports) - n_valid
        print(f"\n{'─'*50}")
        print(f"  {_c(str(n_valid)+' valid', _GREEN, args.quiet)}  "
              f"{_c(str(n_invalid)+' invalid', _RED if n_invalid else _GREEN, args.quiet)}  "
              f"({len(reports)} total)")

    return 0 if all(r.valid for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
