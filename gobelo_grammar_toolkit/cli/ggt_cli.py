"""
cli/ggt_cli.py
==============
``ggt`` — Gobelo Grammar Toolkit command-line interface.

Exposes the GGT public API as a ``ggt`` shell command registered via the
``[project.scripts]`` entry point in ``pyproject.toml``.

Commands
--------
``ggt info <language>``
    Print grammar metadata and a feature-count summary table.

``ggt noun-classes <language>``
    Print all noun classes as a formatted table.
    ``--active-only``  hide inactive/abstract classes.

``ggt concords <language> <type>``
    Print all entries in a concord paradigm.
    ``--all-types``  list available paradigm names instead.

``ggt validate <path>``
    Load and validate a YAML grammar file; report errors / warnings.

``ggt verify-flags <language>``
    List all unresolved VERIFY flags in a grammar.
    ``--resolved``  include already-resolved flags.
    ``--field <prefix>``  filter by field path prefix.

``ggt diff <language_a> <language_b>``
    Semantic diff of two grammars.
    ``--feature <name>``  restrict to one feature section
    (choices: ``noun_classes``, ``tam``, ``concords``, ``extensions``,
    ``phonology``, ``all``).

Global options
--------------
``--no-color``  disable ANSI colour output.
``--quiet``     suppress progress/info messages; only output data.
``--version``   print GGT version and exit.

Exit codes
----------
0  success
1  grammar not found / load error
2  validation failure (``validate`` command)
3  unknown concord type (``concords`` command)
"""

from __future__ import annotations

import sys
import traceback
from typing import List, Optional

import click

from gobelo_grammar_toolkit.core import GrammarConfig, GobeloGrammarLoader
from gobelo_grammar_toolkit.core.exceptions import (
    GGTError,
    LanguageNotFoundError,
    ConcordTypeNotFoundError,
)

# ---------------------------------------------------------------------------
# Colour / formatting helpers
# ---------------------------------------------------------------------------

# ANSI codes used throughout — all access goes through these helpers so
# that ``--no-color`` can flip them to empty strings in one place.
_BOLD    = "\033[1m"
_DIM     = "\033[2m"
_RED     = "\033[31m"
_GREEN   = "\033[32m"
_YELLOW  = "\033[33m"
_CYAN    = "\033[36m"
_RESET   = "\033[0m"

# Module-level flag toggled by the ``--no-color`` global option.
_COLOR_ENABLED: bool = True


def _c(code: str, text: str) -> str:
    """Wrap *text* in ANSI *code* … RESET if colour is enabled."""
    if not _COLOR_ENABLED:
        return text
    return f"{code}{text}{_RESET}"


def _bold(text: str)   -> str: return _c(_BOLD,   text)
def _dim(text: str)    -> str: return _c(_DIM,    text)
def _red(text: str)    -> str: return _c(_RED,    text)
def _green(text: str)  -> str: return _c(_GREEN,  text)
def _yellow(text: str) -> str: return _c(_YELLOW, text)
def _cyan(text: str)   -> str: return _c(_CYAN,   text)


def _hr(char: str = "─", width: int = 72) -> str:
    return _dim(char * width)


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from *text* to obtain visible length."""
    import re as _re
    return _re.sub(r"\033\[[0-9;]*m", "", text)


def _visible_len(text: str) -> int:
    """Return the printable character count of *text* (ANSI codes excluded)."""
    return len(_strip_ansi(text))


def _table(headers: List[str], rows: List[List[str]]) -> str:
    """
    Render a simple fixed-width text table with column auto-sizing.

    Column widths are computed on *visible* character length so that cells
    containing ANSI colour codes (e.g. ``_green("yes")``) do not inflate the
    width calculation and misalign subsequent plain-text rows.

    Parameters
    ----------
    headers : List[str]
        Column header strings.
    rows : List[List[str]]
        Each inner list must have the same length as *headers*.

    Returns
    -------
    str
        The formatted table as a single string (no trailing newline).
    """
    cols = len(headers)
    # Measure widths on visible (ANSI-stripped) text only
    widths = [_visible_len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < cols:
                widths[i] = max(widths[i], _visible_len(str(cell)))

    sep  = "  ".join("─" * w for w in widths)
    head = "  ".join(_bold(h.ljust(widths[i])) for i, h in enumerate(headers))
    lines = [head, _dim(sep)]
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            s = str(cell)
            # Pad by visible length, not raw len, so ANSI-coloured cells align
            pad = widths[i] - _visible_len(s)
            cells.append(s + " " * max(pad, 0))
        lines.append("  ".join(cells))
    return "\n".join(lines)


def _ggt_version() -> str:
    """
    Return the running GGT version string.

    Tries ``importlib.metadata`` first (works when the package is installed).
    Falls back to ``LOADER_VERSION`` from the validator, which is always
    available because it is defined in source and not derived from packaging
    metadata.
    """
    try:
        import importlib.metadata as _meta
        return _meta.version("gobelo-grammar-toolkit")
    except Exception:
        pass
    try:
        from gobelo_grammar_toolkit.core.validator import LOADER_VERSION
        return LOADER_VERSION
    except Exception:
        return "unknown"


def _load(language: str, quiet: bool = False) -> GobeloGrammarLoader:
    """
    Load a grammar by language name, exiting with code 1 on error.
    """
    try:
        loader = GobeloGrammarLoader(GrammarConfig(language=language))
        return loader
    except LanguageNotFoundError as exc:
        click.echo(_red(f"Error: {exc}"), err=True)
        supported = GobeloGrammarLoader.list_supported_languages() \
            if hasattr(GobeloGrammarLoader, 'list_supported_languages') \
            else []
        if supported:
            click.echo(
                _dim(f"Supported languages: {', '.join(sorted(supported))}"),
                err=True,
            )
        sys.exit(1)
    except GGTError as exc:
        click.echo(_red(f"Grammar load error: {exc}"), err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=False,
)
@click.option(
    "--no-color", is_flag=True, default=False,
    help="Disable ANSI colour output.",
)
@click.option(
    "--quiet", "-q", is_flag=True, default=False,
    help="Suppress headers and progress messages.",
)
@click.version_option(
    version=_ggt_version(),
    prog_name="ggt",
    message="%(prog)s %(version)s (Gobelo Grammar Toolkit)",
)
@click.pass_context
def cli(ctx: click.Context, no_color: bool, quiet: bool) -> None:
    """
    Gobelo Grammar Toolkit — inspect, validate, and compare Bantu grammars.

    Run ``ggt <command> --help`` for command-specific options.
    """
    global _COLOR_ENABLED
    if no_color:
        _COLOR_ENABLED = False
    ctx.ensure_object(dict)
    ctx.obj["quiet"] = quiet


# ---------------------------------------------------------------------------
# ggt info
# ---------------------------------------------------------------------------

@cli.command("info")
@click.argument("language")
@click.pass_context
def cmd_info(ctx: click.Context, language: str) -> None:
    """
    Show grammar metadata and feature-count summary for LANGUAGE.

    \b
    Example:
        ggt info chitonga
    """
    quiet = ctx.obj.get("quiet", False)
    loader = _load(language, quiet=quiet)
    meta   = loader.get_metadata()

    if not quiet:
        click.echo(_hr())
        click.echo(
            _bold(f"  Grammar: {meta.language.upper()}")
            + _dim(f"  (ISO {meta.iso_code}  ·  Guthrie {meta.guthrie})")
        )
        click.echo(_hr())

    # ── Metadata block ────────────────────────────────────────────────
    def _row(label: str, value: str) -> None:
        click.echo(f"  {_dim(label + ':')}  {value}")

    _row("Language",        meta.language)
    _row("ISO 639-3",       meta.iso_code)
    _row("Guthrie code",    meta.guthrie)
    _row("Grammar version", meta.grammar_version)
    _row("Loader range",
         f"{meta.min_loader_version} – {meta.max_loader_version}")

    # ── Feature counts ────────────────────────────────────────────────
    click.echo()
    if not quiet:
        click.echo(_bold("  Feature summary"))
        click.echo(_dim("  " + "─" * 40))

    counts: List[tuple] = []

    try:
        nc_all    = loader.get_noun_classes(active_only=False)
        nc_active = [nc for nc in nc_all if nc.active]
        counts.append(("Noun classes", f"{len(nc_active)} active / {len(nc_all)} total"))
    except GGTError:
        counts.append(("Noun classes", _dim("(unavailable)")))

    try:
        tams = loader.get_tam_markers()
        counts.append(("TAM markers", str(len(tams))))
    except GGTError:
        counts.append(("TAM markers", _dim("(unavailable)")))

    try:
        exts = loader.get_extensions()
        counts.append(("Verb extensions", str(len(exts))))
    except GGTError:
        counts.append(("Verb extensions", _dim("(unavailable)")))

    try:
        ctypes = loader.get_all_concord_types()
        counts.append(("Concord paradigms", str(len(ctypes))))
    except GGTError:
        counts.append(("Concord paradigms", _dim("(unavailable)")))

    try:
        slots = loader.get_verb_slots()
        oblig = sum(1 for s in slots if s.obligatory)
        counts.append(("Verb slots", f"{len(slots)} ({oblig} obligatory)"))
    except GGTError:
        counts.append(("Verb slots", _dim("(unavailable)")))

    try:
        flags = loader.list_verify_flags()
        unresolved = [f for f in flags if not f.resolved]
        if unresolved:
            counts.append(("VERIFY flags",
                           _yellow(f"{len(unresolved)} unresolved / {len(flags)} total")))
        else:
            counts.append(("VERIFY flags",
                           _green(f"{len(flags)} total (all resolved)")))
    except GGTError:
        counts.append(("VERIFY flags", _dim("(unavailable)")))

    label_w = max(len(label) for label, _ in counts)
    for label, val in counts:
        click.echo(f"  {_dim((label + ':').ljust(label_w + 1))}  {val}")

    if not quiet:
        click.echo(_hr())


# ---------------------------------------------------------------------------
# ggt noun-classes
# ---------------------------------------------------------------------------

@cli.command("noun-classes")
@click.argument("language")
@click.option(
    "--active-only", is_flag=True, default=False,
    help="Hide inactive / abstract / locative classes.",
)
@click.pass_context
def cmd_noun_classes(ctx: click.Context, language: str, active_only: bool) -> None:
    """
    List all noun classes for LANGUAGE.

    \b
    Examples:
        ggt noun-classes chitonga
        ggt noun-classes chibemba --active-only
    """
    quiet  = ctx.obj.get("quiet", False)
    loader = _load(language, quiet=quiet)

    try:
        ncs = loader.get_noun_classes(active_only=active_only)
    except GGTError as exc:
        click.echo(_red(f"Error: {exc}"), err=True)
        sys.exit(1)

    if not ncs:
        click.echo(
            _yellow(
                f"No noun classes found for {language!r}"
                + (" (active only)" if active_only else "")
            )
        )
        return

    if not quiet:
        label = "active " if active_only else ""
        click.echo(_hr())
        click.echo(
            _bold(f"  Noun classes — {meta_lang(loader)} ({len(ncs)} {label}classes)")
        )
        click.echo(_hr())

    rows = []
    for nc in ncs:
        prefix    = nc.prefix or "—"
        allomorphs = ", ".join(nc.allomorphs) if nc.allomorphs else "—"
        sg_pair   = nc.singular_counterpart or "—"
        pl_pair   = nc.plural_counterpart   or "—"
        active_s  = _green("yes") if nc.active else _dim("no")
        domain    = (nc.semantic_domain or "").replace("_", " ")
        rows.append([nc.id, prefix, allomorphs, sg_pair, pl_pair, active_s, domain])

    click.echo(
        _table(
            ["ID", "Prefix", "Allomorphs", "SG pair", "PL pair", "Active", "Semantic domain"],
            rows,
        )
    )

    if not quiet:
        click.echo(_hr())


def meta_lang(loader: GobeloGrammarLoader) -> str:
    """Return a display string: 'chitonga (toi)'."""
    m = loader.get_metadata()
    return f"{m.language} ({m.iso_code})"


# ---------------------------------------------------------------------------
# ggt concords
# ---------------------------------------------------------------------------

@cli.command("concords")
@click.argument("language")
@click.argument("type", metavar="TYPE", default="", required=False)
@click.option(
    "--all-types", is_flag=True, default=False,
    help="List all available concord paradigm names and exit.",
)
@click.pass_context
def cmd_concords(
    ctx: click.Context,
    language: str,
    type: str,
    all_types: bool,
) -> None:
    """
    Show entries in a concord paradigm for LANGUAGE.

    TYPE is a paradigm name, e.g. ``subject``, ``subject_concords``,
    ``object``, ``possessive``, ``demonstrative_proximal``.
    Partial names are resolved: ``subject`` matches ``subject_concords``.

    \b
    Examples:
        ggt concords chitonga subject
        ggt concords silozi object_concords
        ggt concords kaonde --all-types
    """
    quiet  = ctx.obj.get("quiet", False)
    loader = _load(language, quiet=quiet)

    all_type_names = loader.get_all_concord_types()

    if all_types:
        if not quiet:
            click.echo(_hr())
            click.echo(_bold(f"  Concord paradigms — {meta_lang(loader)}"))
            click.echo(_hr())
        for t in sorted(all_type_names):
            click.echo(f"  {t}")
        if not quiet:
            click.echo(_hr())
        return

    if not type:
        click.echo(
            _red("Error: TYPE argument required. Use --all-types to list paradigms."),
            err=True,
        )
        sys.exit(3)

    # Resolve partial name: "subject" → "subject_concords"
    resolved_type = _resolve_concord_type(type, all_type_names)
    if resolved_type is None:
        click.echo(
            _red(f"Error: Unknown concord type {type!r} for {language!r}."),
            err=True,
        )
        click.echo(
            _dim(f"  Available: {', '.join(sorted(all_type_names))}"),
            err=True,
        )
        sys.exit(3)

    try:
        cs = loader.get_concords(resolved_type)
    except ConcordTypeNotFoundError as exc:
        click.echo(_red(f"Error: {exc}"), err=True)
        sys.exit(3)
    except GGTError as exc:
        click.echo(_red(f"Error: {exc}"), err=True)
        sys.exit(1)

    if not quiet:
        click.echo(_hr())
        click.echo(
            _bold(f"  {resolved_type}")
            + _dim(f"  — {meta_lang(loader)}")
            + (f"  ({len(cs.entries)} entries)" if cs.entries else "")
        )
        click.echo(_hr())

    if not cs.entries:
        click.echo(_yellow("  (no entries — grammar stub)"))
    else:
        rows = [[key, form] for key, form in sorted(cs.entries.items())]
        click.echo(_table(["Key", "Form"], rows))

    if not quiet:
        click.echo(_hr())


def _resolve_concord_type(
    partial: str, all_types: List[str]
) -> Optional[str]:
    """
    Fuzzy-resolve a user-supplied concord type string.

    Tries exact match, then ``partial + '_concords'`` suffix, then prefix
    match, then substring match.  Returns ``None`` if nothing matches.
    """
    if partial in all_types:
        return partial
    # e.g. "subject" → "subject_concords"
    with_suffix = partial + "_concords"
    if with_suffix in all_types:
        return with_suffix
    # prefix match
    prefix_hits = [t for t in all_types if t.startswith(partial)]
    if len(prefix_hits) == 1:
        return prefix_hits[0]
    # substring match
    sub_hits = [t for t in all_types if partial in t]
    if len(sub_hits) == 1:
        return sub_hits[0]
    return None


# ---------------------------------------------------------------------------
# ggt validate
# ---------------------------------------------------------------------------

@cli.command("validate")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--language", "-l", default=None,
    help="Override the language name used for error messages "
         "(defaults to filename stem).",
)
@click.option(
    "--strict", is_flag=True, default=False,
    help="Treat VERIFY flags as errors (strict mode).",
)
@click.pass_context
def cmd_validate(
    ctx: click.Context,
    path: str,
    language: Optional[str],
    strict: bool,
) -> None:
    """
    Load and validate a grammar YAML file at PATH.

    Exits with code 0 if the grammar loads cleanly, 2 on error.

    \b
    Examples:
        ggt validate /path/to/custom.yaml
        ggt validate ./kaonde.yaml --strict
    """
    quiet = ctx.obj.get("quiet", False)
    import pathlib

    lang_name = language or pathlib.Path(path).stem

    if not quiet:
        click.echo(_hr())
        click.echo(_bold(f"  Validating: {path}"))
        click.echo(_hr())

    # Strategy: attempt to load via GobeloGrammarLoader with override_path.
    # The loader applies schema validation, version checking, and VERIFY
    # flag extraction internally — which is exactly what we want to surface.
    try:
        cfg    = GrammarConfig(
            language=lang_name,
            override_path=path,
            strict_mode=strict,
        )
        loader = GobeloGrammarLoader(cfg)
    except GGTError as exc:
        click.echo(_red(f"  ✗  {type(exc).__name__}: {exc}"))
        if not quiet:
            click.echo(_hr())
        sys.exit(2)
    except Exception as exc:  # pylint: disable=broad-except
        # Catch yaml.YAMLError, FileNotFoundError, etc.
        click.echo(_red(f"  ✗  Unexpected error: {exc}"))
        if not quiet:
            click.echo(_hr())
        sys.exit(2)

    # Grammar loaded successfully — report VERIFY flags
    try:
        flags      = loader.list_verify_flags()
        unresolved = [f for f in flags if not f.resolved]
    except GGTError:
        flags = unresolved = []

    if unresolved:
        click.echo(
            _yellow(f"  ⚠  Grammar loaded with {len(unresolved)} unresolved VERIFY flag(s).")
        )
        for flag in unresolved[:10]:
            field = getattr(flag, 'field_path', '?')
            note  = getattr(flag, 'note', '')
            click.echo(f"     {_dim('·')} {_cyan(field)}: {note[:60]}")
        if len(unresolved) > 10:
            click.echo(_dim(f"     … and {len(unresolved) - 10} more. Run 'ggt verify-flags' for full list."))
    else:
        click.echo(_green("  ✓  Grammar loaded successfully — no unresolved VERIFY flags."))

    meta = loader.get_metadata()
    if not quiet:
        _row_pair = lambda k, v: click.echo(f"  {_dim(k + ':')}  {v}")
        click.echo()
        _row_pair("Language",        meta.language)
        _row_pair("Grammar version", meta.grammar_version)
        click.echo(_hr())

    if strict and unresolved:
        sys.exit(2)


# ---------------------------------------------------------------------------
# ggt verify-flags
# ---------------------------------------------------------------------------

@cli.command("verify-flags")
@click.argument("language")
@click.option(
    "--resolved", is_flag=True, default=False,
    help="Include already-resolved flags in the output.",
)
@click.option(
    "--field", "-f", default=None, metavar="PREFIX",
    help="Filter flags whose field path starts with PREFIX.",
)
@click.option(
    "--count", "-c", is_flag=True, default=False,
    help="Print count only, not individual flags.",
)
@click.pass_context
def cmd_verify_flags(
    ctx: click.Context,
    language: str,
    resolved: bool,
    field: Optional[str],
    count: bool,
) -> None:
    """
    List unresolved VERIFY flags in a grammar.

    VERIFY flags mark data items that need primary-source verification
    before the grammar can be considered complete.

    \b
    Examples:
        ggt verify-flags kaonde
        ggt verify-flags kaonde --resolved
        ggt verify-flags kaonde --field phonology
        ggt verify-flags kaonde --count
    """
    quiet  = ctx.obj.get("quiet", False)
    loader = _load(language, quiet=quiet)

    try:
        flags = loader.list_verify_flags()
    except GGTError as exc:
        click.echo(_red(f"Error: {exc}"), err=True)
        sys.exit(1)

    # Filter
    if not resolved:
        flags = [f for f in flags if not f.resolved]
    if field:
        flags = [f for f in flags if getattr(f, 'field_path', '').startswith(field)]

    if count:
        click.echo(str(len(flags)))
        return

    if not quiet:
        label = "VERIFY flags" + ("" if not resolved else " (including resolved)")
        filt  = f"  [field prefix: {field!r}]" if field else ""
        click.echo(_hr())
        click.echo(
            _bold(f"  {label} — {meta_lang(loader)}")
            + _dim(filt)
        )
        click.echo(_hr())

    if not flags:
        click.echo(
            _green("  ✓  No unresolved VERIFY flags.")
            if not resolved
            else _dim("  No VERIFY flags recorded.")
        )
        if not quiet:
            click.echo(_hr())
        return

    # Table: field_path | note | suggested_source | resolved
    rows = []
    for f in flags:
        fp   = getattr(f, 'field_path', '?')
        note = getattr(f, 'note', '')
        src  = getattr(f, 'suggested_source', '') or '—'
        res  = getattr(f, 'resolved', False)
        res_s = _green("yes") if res else _yellow("no")
        rows.append([fp, note[:50] + ("…" if len(note) > 50 else ""), src[:30] or "—", res_s])

    click.echo(_table(["Field path", "Note", "Suggested source", "Resolved"], rows))

    if not quiet:
        unresolved_n = sum(1 for f in flags if not getattr(f, 'resolved', False))
        click.echo()
        click.echo(
            _dim(f"  Total shown: {len(flags)}"
                 + (f"  ({unresolved_n} unresolved)" if resolved else ""))
        )
        click.echo(
            _dim("  Tip: run 'ggt verify-flags "
                 + language + " --field <section>' to filter by section.")
        )
        click.echo(_hr())


# ---------------------------------------------------------------------------
# ggt diff
# ---------------------------------------------------------------------------

_DIFF_FEATURES = ("noun_classes", "tam", "concords", "extensions", "phonology", "all")


@cli.command("diff")
@click.argument("language_a")
@click.argument("language_b")
@click.option(
    "--feature", "-F",
    type=click.Choice(_DIFF_FEATURES, case_sensitive=False),
    default="all",
    show_default=True,
    help="Restrict the diff to one feature section.",
)
@click.pass_context
def cmd_diff(
    ctx: click.Context,
    language_a: str,
    language_b: str,
    feature: str,
) -> None:
    """
    Semantic diff of two grammars across linguistic feature sections.

    Differences are reported as human-readable additions, removals, and
    value changes — not raw YAML line diffs.

    \b
    Examples:
        ggt diff chitonga chibemba
        ggt diff chitonga silozi --feature noun_classes
        ggt diff chitonga luvale --feature tam
    """
    quiet   = ctx.obj.get("quiet", False)
    loader_a = _load(language_a, quiet=quiet)
    loader_b = _load(language_b, quiet=quiet)

    if not quiet:
        click.echo(_hr())
        click.echo(
            _bold(f"  Grammar diff: {language_a}")
            + _dim(" vs ")
            + _bold(language_b)
            + _dim(f"  [feature: {feature}]")
        )
        click.echo(_hr())

    any_diff = False

    features_to_run = (
        ["noun_classes", "tam", "concords", "extensions", "phonology"]
        if feature == "all"
        else [feature]
    )

    for feat in features_to_run:
        diff_fn = {
            "noun_classes": _diff_noun_classes,
            "tam":          _diff_tam,
            "concords":     _diff_concords,
            "extensions":   _diff_extensions,
            "phonology":    _diff_phonology,
        }[feat]
        had_diff = diff_fn(loader_a, loader_b, language_a, language_b, quiet)
        any_diff = any_diff or had_diff

    if not any_diff and not quiet:
        click.echo(_green("  ✓  No differences detected between grammars."))

    if not quiet:
        click.echo(_hr())


# ── diff helpers ──────────────────────────────────────────────────────────

def _diff_section_header(title: str) -> None:
    click.echo(f"\n  {_bold(title)}")
    click.echo(_dim("  " + "─" * 50))


def _diff_line(symbol: str, color_fn, label: str, detail: str = "") -> None:
    detail_s = f"  {_dim(detail)}" if detail else ""
    click.echo(f"  {color_fn(symbol)} {label}{detail_s}")


def _diff_noun_classes(
    la: GobeloGrammarLoader,
    lb: GobeloGrammarLoader,
    name_a: str,
    name_b: str,
    quiet: bool,
) -> bool:
    """Diff noun class inventories."""
    try:
        ncs_a = {nc.id: nc for nc in la.get_noun_classes(active_only=False)}
        ncs_b = {nc.id: nc for nc in lb.get_noun_classes(active_only=False)}
    except GGTError:
        return False

    ids_a, ids_b = set(ncs_a), set(ncs_b)
    only_a = sorted(ids_a - ids_b)
    only_b = sorted(ids_b - ids_a)
    shared = sorted(ids_a & ids_b)

    # Value-level changes for shared NCs
    value_changes: List[tuple] = []
    for nc_id in shared:
        a, b = ncs_a[nc_id], ncs_b[nc_id]
        for field in ("prefix", "semantic_domain", "active",
                      "singular_counterpart", "plural_counterpart"):
            va, vb = getattr(a, field, None), getattr(b, field, None)
            if va != vb:
                value_changes.append((nc_id, field, va, vb))

    if not (only_a or only_b or value_changes):
        return False

    _diff_section_header("Noun classes")

    for nc_id in only_a:
        domain = (ncs_a[nc_id].semantic_domain or "").replace("_", " ")
        _diff_line("−", _red, f"{nc_id}",
                   f"only in {name_a}: {domain}")

    for nc_id in only_b:
        domain = (ncs_b[nc_id].semantic_domain or "").replace("_", " ")
        _diff_line("+", _green, f"{nc_id}",
                   f"only in {name_b}: {domain}")

    for nc_id, field, va, vb in value_changes:
        _diff_line("~", _yellow,
                   f"{nc_id}.{field}",
                   f"{name_a}: {va!r}  →  {name_b}: {vb!r}")

    if not quiet:
        click.echo(
            _dim(f"\n  Summary: {len(only_a)} removed, "
                 f"{len(only_b)} added, {len(value_changes)} value change(s)")
        )
    return True


def _diff_tam(
    la: GobeloGrammarLoader,
    lb: GobeloGrammarLoader,
    name_a: str,
    name_b: str,
    quiet: bool,
) -> bool:
    """Diff TAM marker inventories."""
    try:
        tams_a = {t.id: t for t in la.get_tam_markers()}
        tams_b = {t.id: t for t in lb.get_tam_markers()}
    except GGTError:
        return False

    only_a = sorted(set(tams_a) - set(tams_b))
    only_b = sorted(set(tams_b) - set(tams_a))
    shared = sorted(set(tams_a) & set(tams_b))

    value_changes: List[tuple] = []
    for tam_id in shared:
        a, b = tams_a[tam_id], tams_b[tam_id]
        for field in ("form", "tense", "aspect", "mood"):
            va, vb = getattr(a, field, None), getattr(b, field, None)
            if va != vb:
                value_changes.append((tam_id, field, va, vb))

    if not (only_a or only_b or value_changes):
        return False

    _diff_section_header("TAM markers")

    for tid in only_a:
        t = tams_a[tid]
        _diff_line("−", _red, tid,
                   f"only in {name_a}: {t.tense}/{t.aspect} form={t.form!r}")
    for tid in only_b:
        t = tams_b[tid]
        _diff_line("+", _green, tid,
                   f"only in {name_b}: {t.tense}/{t.aspect} form={t.form!r}")
    for tid, field, va, vb in value_changes:
        _diff_line("~", _yellow, f"{tid}.{field}",
                   f"{name_a}: {va!r}  →  {name_b}: {vb!r}")

    if not quiet:
        click.echo(_dim(
            f"\n  Summary: {len(only_a)} removed, "
            f"{len(only_b)} added, {len(value_changes)} value change(s)"
        ))
    return True


def _diff_concords(
    la: GobeloGrammarLoader,
    lb: GobeloGrammarLoader,
    name_a: str,
    name_b: str,
    quiet: bool,
) -> bool:
    """Diff concord paradigm availability and entry counts."""
    try:
        types_a = set(la.get_all_concord_types())
        types_b = set(lb.get_all_concord_types())
    except GGTError:
        return False

    only_a = sorted(types_a - types_b)
    only_b = sorted(types_b - types_a)
    shared = sorted(types_a & types_b)

    # For shared types, compare entry counts and individual key sets
    entry_diffs: List[tuple] = []
    for ct in shared:
        try:
            cs_a = la.get_concords(ct)
            cs_b = lb.get_concords(ct)
        except GGTError:
            continue
        keys_a = set(cs_a.entries.keys())
        keys_b = set(cs_b.entries.keys())
        keys_only_a = sorted(keys_a - keys_b)
        keys_only_b = sorted(keys_b - keys_a)
        # Form-level changes for shared keys
        form_changes = []
        for k in sorted(keys_a & keys_b):
            if cs_a.entries[k] != cs_b.entries[k]:
                form_changes.append((k, cs_a.entries[k], cs_b.entries[k]))
        if keys_only_a or keys_only_b or form_changes:
            entry_diffs.append((ct, keys_only_a, keys_only_b, form_changes))

    if not (only_a or only_b or entry_diffs):
        return False

    _diff_section_header("Concord paradigms")

    for ct in only_a:
        _diff_line("−", _red, ct, f"only in {name_a}")
    for ct in only_b:
        _diff_line("+", _green, ct, f"only in {name_b}")

    for ct, keys_only_a, keys_only_b, form_changes in entry_diffs:
        click.echo(f"\n    {_cyan(ct)}")
        for k in keys_only_a:
            _diff_line("  −", _red, k, f"only in {name_a}")
        for k in keys_only_b:
            _diff_line("  +", _green, k, f"only in {name_b}")
        for k, fa, fb in form_changes:
            _diff_line("  ~", _yellow, k,
                       f"{name_a}: {fa!r}  →  {name_b}: {fb!r}")

    if not quiet:
        click.echo(_dim(
            f"\n  Summary: {len(only_a)} paradigm(s) removed, "
            f"{len(only_b)} paradigm(s) added, "
            f"{len(entry_diffs)} paradigm(s) with entry-level differences"
        ))
    return True


def _diff_extensions(
    la: GobeloGrammarLoader,
    lb: GobeloGrammarLoader,
    name_a: str,
    name_b: str,
    quiet: bool,
) -> bool:
    """Diff verb extension inventories."""
    try:
        exts_a = {e.id: e for e in la.get_extensions()}
        exts_b = {e.id: e for e in lb.get_extensions()}
    except GGTError:
        return False

    only_a = sorted(set(exts_a) - set(exts_b))
    only_b = sorted(set(exts_b) - set(exts_a))
    shared = sorted(set(exts_a) & set(exts_b))

    value_changes: List[tuple] = []
    for ext_id in shared:
        a, b = exts_a[ext_id], exts_b[ext_id]
        for field in ("canonical_form", "zone"):
            va, vb = getattr(a, field, None), getattr(b, field, None)
            if va != vb:
                value_changes.append((ext_id, field, va, vb))

    if not (only_a or only_b or value_changes):
        return False

    _diff_section_header("Verb extensions")

    for eid in only_a:
        e = exts_a[eid]
        _diff_line("−", _red, eid,
                   f"only in {name_a}: zone={e.zone} form={e.canonical_form!r}")
    for eid in only_b:
        e = exts_b[eid]
        _diff_line("+", _green, eid,
                   f"only in {name_b}: zone={e.zone} form={e.canonical_form!r}")
    for eid, field, va, vb in value_changes:
        _diff_line("~", _yellow, f"{eid}.{field}",
                   f"{name_a}: {va!r}  →  {name_b}: {vb!r}")

    if not quiet:
        click.echo(_dim(
            f"\n  Summary: {len(only_a)} removed, "
            f"{len(only_b)} added, {len(value_changes)} value change(s)"
        ))
    return True


def _diff_phonology(
    la: GobeloGrammarLoader,
    lb: GobeloGrammarLoader,
    name_a: str,
    name_b: str,
    quiet: bool,
) -> bool:
    """Diff phonology metadata at the PhonologyRules field level."""
    try:
        ph_a = la.get_phonology()
        ph_b = lb.get_phonology()
    except GGTError:
        return False

    changes: List[tuple] = []
    for field in ("vowels", "consonants", "tone_system"):
        va = getattr(ph_a, field, None)
        vb = getattr(ph_b, field, None)
        if va != vb:
            # Summarise list differences briefly
            if isinstance(va, list) and isinstance(vb, list):
                only_a = sorted(set(str(x) for x in va) - set(str(x) for x in vb))
                only_b = sorted(set(str(x) for x in vb) - set(str(x) for x in va))
                if only_a or only_b:
                    detail = (
                        (f"−[{', '.join(only_a[:5])}] " if only_a else "")
                        + (f"+[{', '.join(only_b[:5])}]" if only_b else "")
                    ).strip()
                    changes.append((field, detail))
            else:
                va_s = str(va)[:40] if va else "(empty)"
                vb_s = str(vb)[:40] if vb else "(empty)"
                changes.append((field, f"{name_a}: {va_s}  →  {name_b}: {vb_s}"))

    # Compare sandhi rule counts
    sr_a = len(getattr(ph_a, "sandhi_rules", []) or [])
    sr_b = len(getattr(ph_b, "sandhi_rules", []) or [])
    if sr_a != sr_b:
        changes.append(("sandhi_rules", f"{name_a}: {sr_a} rules  →  {name_b}: {sr_b} rules"))

    if not changes:
        return False

    _diff_section_header("Phonology")

    for field, detail in changes:
        _diff_line("~", _yellow, field, detail)

    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point registered as ``ggt`` in pyproject.toml."""
    # Standalone exception safety: Click already handles SystemExit; this
    # catches anything that slips through without a nice error message.
    try:
        cli(standalone_mode=True)
    except (KeyboardInterrupt, EOFError):
        click.echo("\nInterrupted.", err=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
