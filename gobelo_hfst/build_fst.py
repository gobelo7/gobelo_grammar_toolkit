#!/usr/bin/env python3
"""
=============================================================
 Chitonga FST Build Script  —  build_fst.py
=============================================================
 Reads:
   chitonga_grammar.yaml  (hfst_config section for parameters)
   verbs.yaml             (verb lexicon)
   nouns.yaml             (noun lexicon)
   closed_class.yaml      (non-inflecting items)
   chitonga.lexc          (morphotactics template)
   chitonga.twolc         (phonological rules — already complete)

 Generates:
   chitonga-full.lexc     (lexc with all vocab injected)
   chitonga-analyser.hfst (compiled analyser binary)
   chitonga-generator.hfst(compiled generator binary)
   build_report.yaml      (coverage stats + warnings)

 Usage:
   python3 build_fst.py
   python3 build_fst.py --lang chitonga --outdir build/
   python3 build_fst.py --no-compile   (generate lexc only)

 Requirements:
   pip install pyyaml
   hfst  (hfst-lexc, hfst-twolc, hfst-compose-intersect, hfst-invert)
   Install HFST: https://hfst.github.io  or  apt install hfst
=============================================================
"""

import argparse
import csv
import re
import shutil
import subprocess
import sys
import yaml
from pathlib import Path
from collections import defaultdict

# ─────────────────────────────────────────────────────────────
#  DEFAULTS
# ─────────────────────────────────────────────────────────────
DEFAULT_GRAMMAR    = "chitonga_grammar.yaml"
DEFAULT_HFST_CFG   = "hfst_config.yaml"
DEFAULT_LEXC_TMPL  = "chitonga.lexc"
DEFAULT_TWOLC      = "chitonga.twolc"
DEFAULT_VERBS      = "verbs.yaml"
DEFAULT_NOUNS      = "nouns.yaml"
DEFAULT_CLOSED     = "closed_class.yaml"
DEFAULT_OUTDIR     = "build"

# ─────────────────────────────────────────────────────────────
#  YAML LOADING
# ─────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        # Skip comment lines that aren't valid YAML
        lines = [l for l in f.readlines() if not l.strip().startswith("#") or l.strip() == "#"]
        return yaml.safe_load("".join(lines)) or {}


def load_yaml_with_comments(path: Path) -> dict:
    """Load YAML tolerating leading comment blocks."""
    with open(path, encoding="utf-8-sig") as f:
        content = f.read()
    return yaml.safe_load(content) or {}

# ─────────────────────────────────────────────────────────────
#  MULTICHAR SYMBOLS GENERATOR
# ─────────────────────────────────────────────────────────────

def collect_multichar_symbols(cfg: dict) -> list:
    """
    Flatten all multichar symbol lists from hfst_config.yaml
    into a single deduplicated list.
    """
    symbols = []
    ms = cfg.get("hfst_config", {}).get("multichar_symbols", {})
    for section_name, section in ms.items():
        if isinstance(section, list):
            for item in section:
                if isinstance(item, str):
                    # May be space-separated on one line: "+NC1 +NC2 ..."
                    symbols.extend(item.split())
                elif isinstance(item, list):
                    for s in item:
                        symbols.extend(str(s).split())

    # Flag diacritics — expand pattern @{P|R|D}.NC.{1..18}@
    fd = cfg.get("hfst_config", {}).get("flag_diacritics", {})
    for fd_name, fd_data in fd.items():
        if "symbols" in fd_data:
            symbols.extend(fd_data["symbols"])
        if "pairs" in fd_data:
            for pair in fd_data["pairs"]:
                vals = pair.get("values", [])
                feat = pair.get("feature", "X")
                for v in vals:
                    symbols.extend([
                        f"@P.{feat}.{v}@",
                        f"@R.{feat}.{v}@",
                        f"@D.{feat}.{v}@",
                    ])

    # Deduplicate preserving order
    seen = set()
    out = []
    for s in symbols:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out

# ─────────────────────────────────────────────────────────────
#  LEXC VERB ROOT GENERATION
# ─────────────────────────────────────────────────────────────

def generate_verb_roots(verbs_yaml: Path) -> tuple:
    """
    Read verbs.yaml and generate lexc entries for VerbRoot lexicon.
    Returns (lexc_lines: list[str], stats: dict, warnings: list[str])
    """
    data = load_yaml_with_comments(verbs_yaml)
    verbs = data.get("verbs", [])

    lines    = []
    stats    = {"total": 0, "high": 0, "medium": 0, "low": 0,
                "skipped_corrupt": 0, "no_stem": 0}
    warnings = []

    lines.append("! ── VerbRoot: auto-generated from verbs.yaml ──────────────────")
    lines.append("LEXICON VerbRoot")

    for entry in verbs:
        stats["total"] += 1

        if entry.get("corrupt"):
            stats["skipped_corrupt"] += 1
            continue

        stem  = (entry.get("stem") or "").strip()
        conf  = entry.get("stem_confidence", "low")
        form  = entry.get("full_form", "").strip()
        senses = entry.get("senses", [])
        gloss = senses[0]["meaning"] if senses else "?"
        gloss = gloss.replace('"', "'").replace("!", "")

        if not stem or len(stem) < 2:
            stats["no_stem"] += 1
            warnings.append(f"WARN: no usable stem for '{form}' (gloss: {gloss})")
            # Emit a commented-out placeholder so the linguist sees it
            lines.append(f"! STEM_MISSING: {form}  [{gloss}]  — fill stem in verbs.yaml")
            continue

        # Confidence marker in comment
        conf_note = {"high": "", "medium": " [conf:medium]", "low": " [conf:LOW — verify]"}
        note = conf_note.get(conf, "")

        stats[conf] = stats.get(conf, 0) + 1

        # Multiple senses → one lexc entry per sense (same stem, different gloss tag)
        # For FST purposes one entry suffices; extra senses live in the YAML.
        lines.append(f"  {stem}%+V:{stem} DerivSuffix ; ! {gloss}{note}")

        # Also emit full form if it differs from stem (for surface lookup)
        norm = form.lower().strip()
        if norm and norm != stem and len(norm) >= 3:
            lines.append(f"  {norm}%+V:{norm} DerivSuffix ; ! {gloss} (full form)")

    lines.append("")
    return lines, stats, warnings


# ─────────────────────────────────────────────────────────────
#  LEXC NOUN ROOT GENERATION
# ─────────────────────────────────────────────────────────────

def generate_noun_roots(nouns_yaml: Path) -> tuple:
    """
    Read nouns.yaml and generate lexc entries for NounRoot lexica.
    Returns (lexc_lines: list[str], stats: dict, warnings: list[str])
    """
    data = load_yaml_with_comments(nouns_yaml)
    nouns = data.get("nouns", [])

    # Group by class_singular
    by_nc = defaultdict(list)
    stats = {"total": 0, "nc_assigned": 0, "nc_unknown": 0,
             "skipped_corrupt": 0, "multiword": 0}
    warnings = []

    for entry in nouns:
        stats["total"] += 1
        if entry.get("corrupt"):
            stats["skipped_corrupt"] += 1
            continue
        nc = entry.get("class_singular")
        if not nc:
            stats["nc_unknown"] += 1
            warnings.append(
                f"WARN: no NC for '{entry.get('full_form_singular','')}' — skipped"
            )
            continue
        if isinstance(nc, list):
            nc = nc[0]   # take first if ambiguous
        stats["nc_assigned"] += 1
        by_nc[str(nc)].append(entry)

    lines = []
    lines.append("! ── Noun root lexica: auto-generated from nouns.yaml ──────────")

    for nc in sorted(by_nc.keys(), key=lambda x: int(re.sub(r"\D","",x) or "99")):
        lines.append(f"LEXICON NounRoot{nc}")
        for entry in by_nc[nc]:
            form  = entry.get("full_form_singular", "").strip()
            norm  = form.lower()
            senses = entry.get("senses", [])
            gloss = senses[0]["meaning"] if senses else "?"
            gloss = gloss.replace('"', "'")

            # Strip the class prefix to get the root
            root = _strip_nc_prefix(norm, nc)

            if not root or len(root) < 1:
                warnings.append(f"WARN: empty root for '{form}' NC{nc}")
                lines.append(f"! EMPTY_ROOT: {form}  — check prefix stripping for {nc}")
                continue

            if " " in root:
                stats["multiword"] += 1
                lines.append(f"! MULTIWORD: {form}  — needs phrase lexicon entry")
                continue

            lines.append(f"  {root}%+N:{root} # ; ! {gloss}")

            # Plural form if available
            plural = entry.get("full_form_plural", "")
            plural_nc = entry.get("class_plural", "")
            if plural and plural_nc:
                pl_norm = plural.strip().lower()
                pl_root = _strip_nc_prefix(pl_norm, str(plural_nc))
                if pl_root and len(pl_root) >= 1 and " " not in pl_root:
                    lines.append(f"  {pl_root}%+N:{pl_root} # ; ! {gloss} (plural)")

        lines.append("")

    return lines, stats, warnings


def _strip_nc_prefix(word: str, nc: str) -> str:
    """
    Strip the noun class prefix from a word to get the stem.
    Uses the prefix map from the grammar.
    """
    NC_PREFIXES = {
        "NC1":  ["mw", "mu"],
        "NC1a": [],
        "NC2":  ["ba", "b"],
        "NC3":  ["mw", "mu"],
        "NC4":  ["my", "mi"],
        "NC5":  ["ly", "li", ""],
        "NC6":  ["ma", "m"],
        "NC7":  ["chi", "ci", "c"],
        "NC8":  ["zy", "zi", "z"],
        "NC9":  ["ng", "ny", "mb", "nd", "n", "m", ""],
        "NC10": ["zy", "zi", "n"],
        "NC11": ["lw", "lu"],
        "NC12": ["ka", "k"],
        "NC13": ["tw", "tu"],
        "NC14": ["bw", "bu"],
        "NC15": ["kw", "ku"],
        "NC16": ["aa", "a"],
        "NC17": ["kw", "ku"],
        "NC18": ["mw", "mu"],
    }
    prefixes = NC_PREFIXES.get(nc, [])
    for pfx in sorted(prefixes, key=len, reverse=True):
        if word.startswith(pfx) and len(word) > len(pfx):
            return word[len(pfx):]
    return word   # no prefix matched — return as-is


# ─────────────────────────────────────────────────────────────
#  CLOSED CLASS GENERATION
# ─────────────────────────────────────────────────────────────

def generate_closed_class(closed_yaml: Path) -> tuple:
    """Read closed_class.yaml and generate ClosedClass lexicon entries."""
    data = load_yaml_with_comments(closed_yaml)
    items = data.get("closed_class", [])

    lines = ["! ── ClosedClass: auto-generated from closed_class.yaml ──────────",
             "LEXICON ClosedClass"]
    stats = {"total": 0}
    warnings = []

    for entry in items:
        stats["total"] += 1
        form = entry.get("normalised") or entry.get("full_form", "")
        form = form.strip().lower()
        pos  = entry.get("pos", "PART")
        tag  = f"+{pos[:4].upper()}"
        senses = entry.get("senses", [])
        gloss = senses[0]["meaning"] if senses else "?"
        gloss = gloss.replace('"', "'")

        # Handle multiple NC-specific forms (demonstratives etc.)
        for sense in senses:
            nc = sense.get("noun_class")
            if nc:
                nc_tag = f"%+{nc}" if isinstance(nc, str) else ""
                lines.append(f"  {form}{tag}{nc_tag}:{form} # ; ! {gloss}")
            else:
                lines.append(f"  {form}{tag}:{form} # ; ! {gloss}")

    lines.append("")
    return lines, stats, warnings


# ─────────────────────────────────────────────────────────────
#  LEXC ASSEMBLY
# ─────────────────────────────────────────────────────────────

def build_full_lexc(
    template_path: Path,
    verb_lines: list,
    noun_lines: list,
    closed_lines: list,
    multichar_symbols: list,
    out_path: Path,
):
    """
    Read the lexc template, inject generated lexica, write full lexc.
    Replaces stub lexicon sections with generated content.
    """
    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    # 1. Replace the Multichar_Symbols block with the full generated list
    ms_block  = "Multichar_Symbols\n"
    ms_block += "\n".join(f"  {s}" for s in multichar_symbols)
    ms_block += "\n"
    # Find and replace existing Multichar_Symbols block
    template = re.sub(
        r"Multichar_Symbols\n.*?(?=\n! ──|\nLEXICON Root)",
        ms_block + "\n",
        template,
        count=1,
        flags=re.DOTALL,
    )

    # 2. Replace stub VerbRoot with generated entries
    verb_section = "\n".join(verb_lines) + "\n"
    template = re.sub(
        r"LEXICON VerbRoot\n.*?(?=\n! ──|\nLEXICON DerivSuffix)",
        verb_section,
        template,
        count=1,
        flags=re.DOTALL,
    )

    # 3. Append noun root lexica (they are stubs in template)
    noun_section = "\n".join(noun_lines) + "\n"
    # Replace from NounRootNC1 to end of file
    template = re.sub(
        r"(LEXICON NounRootNC1\n).*",
        noun_section,
        template,
        count=1,
        flags=re.DOTALL,
    )

    # 4. Replace ClosedClass stub
    closed_section = "\n".join(closed_lines) + "\n"
    template = re.sub(
        r"LEXICON ClosedClass\n.*?(?=\n! ══|\Z)",
        closed_section,
        template,
        count=1,
        flags=re.DOTALL,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(template)
    print(f"  Generated: {out_path}  ({out_path.stat().st_size // 1024} KB)")


# ─────────────────────────────────────────────────────────────
#  HFST COMPILATION
# ─────────────────────────────────────────────────────────────

def check_hfst() -> bool:
    """Check that HFST tools are available."""
    for tool in ["hfst-lexc", "hfst-twolc", "hfst-compose-intersect", "hfst-invert"]:
        if not shutil.which(tool):
            print(f"  WARNING: {tool} not found in PATH")
            return False
    return True


def run(cmd: str, description: str) -> bool:
    """Run a shell command, print result."""
    print(f"  [{description}]")
    print(f"    $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    ERROR (exit {result.returncode}):")
        print(f"    {result.stderr.strip()[:400]}")
        return False
    print(f"    OK")
    return True


def compile_fst(lexc: Path, twolc: Path, out_dir: Path) -> dict:
    """Run the full HFST pipeline. Returns dict of output paths."""
    morph  = out_dir / "chitonga-morphotactics.hfst"
    phon   = out_dir / "chitonga-phonology.hfst"
    anal   = out_dir / "chitonga-analyser.hfst"
    gen    = out_dir / "chitonga-generator.hfst"

    steps = [
        (f"hfst-lexc {lexc} -o {morph}",
         "Compile lexc morphotactics"),
        (f"hfst-twolc {twolc} -o {phon}",
         "Compile twolc phonology"),
        (f"hfst-compose-intersect {morph} {phon} -o {anal}",
         "Compose-intersect → analyser"),
        (f"hfst-invert {anal} -o {gen}",
         "Invert → generator"),
    ]

    results = {}
    for cmd, desc in steps:
        ok = run(cmd, desc)
        results[desc] = "OK" if ok else "FAILED"
        if not ok:
            print(f"\n  Build stopped at: {desc}")
            break

    return results


# ─────────────────────────────────────────────────────────────
#  SMOKE TEST
# ─────────────────────────────────────────────────────────────

def smoke_test(analyser: Path) -> list:
    """
    Run a small set of known words through the analyser.
    Returns list of (word, expected_tag, actual_output, pass/fail).
    """
    TEST_CASES = [
        # surface_form          expected_tag_fragment
        ("aabona",              "+CONJ"),
        ("kuti",                "+CONJ"),
        ("naa",                 "+CONJ"),
        ("cintu",               "+NC7+SG"),
        ("zintu",               "+NC8+PL"),
        ("muntu",               "+NC1+SG"),
        ("bantu",               "+NC2+PL"),
    ]

    results = []
    for word, expected in TEST_CASES:
        cmd = f"echo '{word}' | hfst-lookup {analyser}"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = res.stdout.strip()
        passed = expected in output
        results.append({
            "word":     word,
            "expected": expected,
            "output":   output[:120],
            "pass":     passed,
        })
        status = "PASS" if passed else "FAIL"
        print(f"    {status}  {word:20} → {output[:60]}")

    return results


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Build Chitonga HFST morphological analyser from YAML grammar"
    )
    parser.add_argument("--grammar",   default=DEFAULT_GRAMMAR,
                        help=f"Grammar YAML (default: {DEFAULT_GRAMMAR})")
    parser.add_argument("--hfst-cfg",  default=DEFAULT_HFST_CFG,
                        help=f"HFST config YAML (default: {DEFAULT_HFST_CFG})")
    parser.add_argument("--lexc-tmpl", default=DEFAULT_LEXC_TMPL,
                        help=f"lexc template (default: {DEFAULT_LEXC_TMPL})")
    parser.add_argument("--twolc",     default=DEFAULT_TWOLC,
                        help=f"twolc file (default: {DEFAULT_TWOLC})")
    parser.add_argument("--verbs",     default=DEFAULT_VERBS)
    parser.add_argument("--nouns",     default=DEFAULT_NOUNS)
    parser.add_argument("--closed",    default=DEFAULT_CLOSED)
    parser.add_argument("--outdir",    default=DEFAULT_OUTDIR)
    parser.add_argument("--no-compile", action="store_true",
                        help="Generate lexc only; do not run hfst-lexc etc.")
    parser.add_argument("--no-test",   action="store_true",
                        help="Skip smoke tests after compilation")
    args = parser.parse_args()

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(" Chitonga FST Builder")
    print("=" * 60)

    # ── Load config ───────────────────────────────────────────
    print("\nLoading configuration...")
    cfg = {}
    for path in [args.grammar, args.hfst_cfg]:
        p = Path(path)
        if p.exists():
            cfg.update(load_yaml_with_comments(p))
            print(f"  Loaded: {path}")
        else:
            print(f"  NOT FOUND: {path} — using defaults")

    # ── Collect multichar symbols ─────────────────────────────
    print("\nCollecting multichar symbols...")
    symbols = collect_multichar_symbols(cfg)
    print(f"  {len(symbols)} symbols collected")

    # ── Generate lexicon sections ─────────────────────────────
    print("\nGenerating VerbRoot from verbs.yaml...")
    v_lines, v_stats, v_warns = generate_verb_roots(Path(args.verbs))
    print(f"  {v_stats['total']} verbs | high={v_stats['high']} "
          f"medium={v_stats.get('medium',0)} low={v_stats['low']} "
          f"skipped={v_stats['skipped_corrupt']+v_stats['no_stem']}")

    print("\nGenerating NounRoot lexica from nouns.yaml...")
    n_lines, n_stats, n_warns = generate_noun_roots(Path(args.nouns))
    print(f"  {n_stats['total']} nouns | assigned={n_stats['nc_assigned']} "
          f"unknown={n_stats['nc_unknown']} skipped={n_stats['skipped_corrupt']}")

    print("\nGenerating ClosedClass from closed_class.yaml...")
    c_lines, c_stats, c_warns = generate_closed_class(Path(args.closed))
    print(f"  {c_stats['total']} closed-class items")

    # ── Assemble full lexc ────────────────────────────────────
    print("\nAssembling chitonga-full.lexc...")
    full_lexc = out_dir / "chitonga-full.lexc"
    build_full_lexc(
        template_path=Path(args.lexc_tmpl),
        verb_lines=v_lines,
        noun_lines=n_lines,
        closed_lines=c_lines,
        multichar_symbols=symbols,
        out_path=full_lexc,
    )

    # ── Compile ───────────────────────────────────────────────
    compile_results = {}
    if not args.no_compile:
        print("\nChecking HFST tools...")
        hfst_available = check_hfst()
        if not hfst_available:
            print("  HFST tools not found. Skipping compilation.")
            print("  Install: https://hfst.github.io  or  sudo apt install hfst")
        else:
            print("\nCompiling FST...")
            compile_results = compile_fst(full_lexc, Path(args.twolc), out_dir)

    # ── Smoke test ────────────────────────────────────────────
    test_results = []
    analyser = out_dir / "chitonga-analyser.hfst"
    if not args.no_test and analyser.exists():
        print("\nRunning smoke tests...")
        test_results = smoke_test(analyser)
        passed = sum(1 for r in test_results if r["pass"])
        print(f"  {passed}/{len(test_results)} tests passed")

    # ── Write report ──────────────────────────────────────────
    all_warnings = v_warns + n_warns + c_warns
    report = {
        "verb_stats":     v_stats,
        "noun_stats":     n_stats,
        "closed_stats":   c_stats,
        "warnings":       all_warnings,
        "compile_steps":  compile_results,
        "smoke_tests":    test_results,
        "summary": {
            "total_verb_entries":  v_stats["total"],
            "total_noun_entries":  n_stats["total"],
            "total_closed_items":  c_stats["total"],
            "warnings_count":      len(all_warnings),
            "build_status": (
                "complete" if all(v == "OK" for v in compile_results.values())
                else "lexc_only" if not compile_results
                else "partial"
            ),
        },
    }
    report_path = out_dir / "build_report.yaml"
    with open(report_path, "w", encoding="utf-8") as f:
        yaml.dump(report, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, indent=2)
    print(f"\nBuild report: {report_path}")

    # ── Summary ───────────────────────────────────────────────
    print()
    print("=" * 60)
    print(" BUILD SUMMARY")
    print("=" * 60)
    print(f"  Verb entries    : {v_stats['total']}")
    print(f"  Noun entries    : {n_stats['total']}")
    print(f"  Closed-class    : {c_stats['total']}")
    print(f"  Warnings        : {len(all_warnings)}")
    if compile_results:
        for step, status in compile_results.items():
            icon = "✓" if status == "OK" else "✗"
            print(f"  {icon} {step}")
    else:
        print("  Compilation: skipped (--no-compile or HFST not found)")
    if test_results:
        passed = sum(1 for r in test_results if r["pass"])
        print(f"  Smoke tests     : {passed}/{len(test_results)} passed")

    if all_warnings:
        print(f"\nFirst {min(5, len(all_warnings))} warnings:")
        for w in all_warnings[:5]:
            print(f"  {w}")
        if len(all_warnings) > 5:
            print(f"  ... {len(all_warnings)-5} more in build_report.yaml")

    print(f"\nOutputs in: {out_dir}/")
    print(f"  chitonga-full.lexc")
    if compile_results:
        print(f"  chitonga-analyser.hfst")
        print(f"  chitonga-generator.hfst")


if __name__ == "__main__":
    main()
