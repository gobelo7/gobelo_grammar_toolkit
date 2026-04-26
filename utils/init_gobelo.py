#!/usr/bin/env python3
"""
init_gobelo.py — Initialise the Gobelo platform directory tree.

Usage:
    python init_gobelo.py                  # creates ./gobelo/
    python init_gobelo.py --root ~/projects/gobelo
    python init_gobelo.py --dry-run        # preview without creating anything
"""

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Language inventory (ISO 639-3 code → full name)
# ---------------------------------------------------------------------------
LANGUAGES = {
    "bem": "Bemba",
    "toi": "Chitonga",
    "nya": "Nyanja/Chichewa",
    "lue": "Luvale",
    "lun": "Lunda",
    "kqn": "Kaonde",
    "tum": "Tumbuka",
}

# ---------------------------------------------------------------------------
# Directory tree specification
# Each entry is a path relative to the project root.
# Files are indicated by a trailing filename (no trailing slash).
# Directories end with "/".
# ---------------------------------------------------------------------------
def build_tree(langs: dict) -> list[tuple[str, str | None]]:
    """
    Returns a list of (relative_path, optional_file_content) tuples.
    Directories have content=None; files have content=str.
    """
    entries: list[tuple[str, str | None]] = []

    def d(path: str):
        entries.append((path, None))

    def f(path: str, content: str = ""):
        entries.append((path, content))

    # ── apps ────────────────────────────────────────────────────────────────
    # NLP app interfaces — morphological analysis and other tools are
    # provided by the GGT package (pip install gobelo-ggt), not duplicated here.
    for app in ["tokenizer", "tagger", "concordancer", "corpus_viewer"]:
        d(f"apps/{app}")
        f(f"apps/{app}/__init__.py")
        f(f"apps/{app}/README.md", f"# {app.replace('_', ' ').title()}\n")

    d("apps/shared")
    f("apps/shared/__init__.py")
    f("apps/shared/config.py", "# Shared configuration across Gobelo apps\n")
    f("apps/shared/lang_utils.py", "# Language utility helpers\n")

    # ── corpus ───────────────────────────────────────────────────────────────
    d("corpus/_parallel/booklets")
    d("corpus/_parallel/aligned")
    f(
        "corpus/_parallel/aligned/.gitkeep",
        "# Aligned sentence files go here (e.g. story_001.tsv)\n"
        "# Columns: url, page, " + ", ".join(langs.keys()) + "\n",
    )

    for code, name in langs.items():
        for sub in ["raw", "tokenized", "annotated"]:
            d(f"corpus/{code}/{sub}")
            f(f"corpus/{code}/{sub}/.gitkeep")
        f(f"corpus/{code}/README.md", f"# {name} Corpus\n\nISO 639-3: `{code}`\n")

    # ── grammar (BGT YAML — single source of truth) ─────────────────────────
    # Note: HFST transducers and .lexc/.twolc source files live inside the
    # GGT package (ggt/hfst/) and are managed there. Gobelo consumes GGT as
    # a pip dependency — do not duplicate FST resources here.
    d("grammar")
    for code, name in langs.items():
        f(
            f"grammar/{code}.yaml",
            f"# {name} Grammar Config (BGT)\n"
            f"# ISO 639-3: {code}\n\n"
            "metadata:\n"
            f"  language: {name}\n"
            f"  iso639_3: {code}\n"
            "  version: 0.1.0\n\n"
            "# Add noun classes, concords, TAM markers, etc. below\n",
        )

    # ── scripts ──────────────────────────────────────────────────────────────
    d("scripts")
    f(
        "scripts/build_hfst.sh",
        "#!/usr/bin/env bash\n"
        "# Build all HFST transducers from GGT package source\n"
        "# Assumes GGT is installed (pip install -e ../ggt) and\n"
        "# that ggt/hfst/{lang}_hfst/ folders contain .lexc + .twolc files.\n"
        "set -euo pipefail\n\n"
        "GGT_HFST=\"$(python -c 'import ggt; import pathlib; "
        "print(pathlib.Path(ggt.__file__).parent / \"hfst\")')\"\n\n"
        f"LANGS=({' '.join(langs.keys())})\n\n"
        "declare -A LANG_FOLDERS=(\n"
        "    [bem]=bemba_hfst [toi]=chitonga_hfst [nya]=chinyanja_hfst\n"
        "    [lue]=luvale_hfst [lun]=lunda_hfst [kqn]=kaonde_hfst [loz]=lozi_hfst\n"
        ")\n\n"
        "for lang in \"${LANGS[@]}\"; do\n"
        '    folder="${LANG_FOLDERS[$lang]}"\n'
        '    src="$GGT_HFST/$folder/$lang.lexc"\n'
        '    out="$GGT_HFST/$folder/$lang.hfst"\n'
        '    echo "Building $lang ($folder)..."\n'
        '    hfst-lexc "$src" -o "$out"\n'
        "done\n"
        'echo "All transducers built."\n',
    )
    f(
        "scripts/validate_yaml.py",
        "#!/usr/bin/env python3\n"
        '"""Validate all BGT YAML grammar configs."""\n\n'
        "from pathlib import Path\n\n"
        "GRAMMAR_DIR = Path(__file__).parent.parent / 'grammar'\n\n"
        "def validate(path: Path) -> bool:\n"
        "    import yaml\n"
        "    with open(path) as fh:\n"
        "        data = yaml.safe_load(fh)\n"
        "    required = {'metadata'}\n"
        "    missing = required - data.keys()\n"
        "    if missing:\n"
        "        print(f'  FAIL {path.name}: missing keys {missing}')\n"
        "        return False\n"
        "    print(f'  OK   {path.name}')\n"
        "    return True\n\n"
        "if __name__ == '__main__':\n"
        "    files = sorted(GRAMMAR_DIR.glob('*.yaml'))\n"
        "    results = [validate(f) for f in files]\n"
        "    passed = sum(results)\n"
        "    print(f'\\n{passed}/{len(results)} configs valid.')\n",
    )
    f(
        "scripts/align_corpus.py",
        "#!/usr/bin/env python3\n"
        '"""Align multilingual sentence data from booklet CSVs."""\n\n'
        "from pathlib import Path\n\n"
        "BOOKLETS_DIR = Path(__file__).parent.parent / 'corpus' / '_parallel' / 'booklets'\n"
        "ALIGNED_DIR  = Path(__file__).parent.parent / 'corpus' / '_parallel' / 'aligned'\n\n"
        "# Alignment keys: story URL + page number\n"
        "ALIGN_KEYS = ['url', 'page']\n"
        f"LANGUAGES  = {list(langs.keys())}\n\n"
        "def align():\n"
        "    # TODO: implement alignment logic\n"
        "    pass\n\n"
        "if __name__ == '__main__':\n"
        "    align()\n",
    )

    # ── top-level ─────────────────────────────────────────────────────────────
    d("docs")
    d("tests")
    f(".gitignore",
        "# Python\n__pycache__/\n*.py[cod]\n*.egg-info/\ndist/\nbuild/\n\n"
        "# HFST compiled transducers live in GGT package — not duplicated here\n"
        "# OS\n.DS_Store\nThumbs.db\n",
    )
    f(
        "README.md",
        "# Gobelo Platform\n\n"
        "Multilingual NLP infrastructure for Zambian Bantu languages.\n\n"
        "## Languages\n\n"
        + "\n".join(f"- **{name}** (`{code}`)" for code, name in langs.items())
        + "\n\n"
        "## Structure\n\n"
        "| Folder | Purpose |\n"
        "|--------|----------|\n"
        "| `apps/` | NLP tools and interfaces |\n"
        "| `corpus/` | Raw, tokenized, and annotated text data |\n"
        "| `grammar/` | BGT YAML configs (single source of truth) |\n"
        "| `scripts/` | Build, validation, and pipeline scripts |\n\n"
        "## Dependencies\n\n"
        "Morphological analysis and HFST transducers are provided by the "
        "**GGT package** (`gobelo-ggt`), maintained as a separate repository.\n\n"
        "```bash\n"
        "pip install gobelo-ggt          # from PyPI (once published)\n"
        "pip install -e ../ggt           # local dev install\n"
        "```\n\n"
        "## Philosophy\n\n"
        "Frugal innovation · Language-agnostic design · YAML as single source of truth\n",
    )

    return entries


# ---------------------------------------------------------------------------
# Creation logic
# ---------------------------------------------------------------------------
def initialise(root: Path, dry_run: bool = False) -> None:
    entries = build_tree(LANGUAGES)
    created_dirs = 0
    created_files = 0

    print(f"{'[DRY RUN] ' if dry_run else ''}Initialising Gobelo platform at: {root}\n")

    for rel_path, content in entries:
        full = root / rel_path

        if content is None:
            # Directory
            if not dry_run:
                full.mkdir(parents=True, exist_ok=True)
            print(f"  DIR   {rel_path}/")
            created_dirs += 1
        else:
            # File
            if not dry_run:
                full.parent.mkdir(parents=True, exist_ok=True)
                if not full.exists():
                    full.write_text(content, encoding="utf-8")
                    # Make shell scripts executable
                    if full.suffix == ".sh":
                        full.chmod(full.stat().st_mode | 0o111)
            print(f"  FILE  {rel_path}")
            created_files += 1

    print(
        f"\n{'Would create' if dry_run else 'Created'} "
        f"{created_dirs} directories and {created_files} files.\n"
    )
    if not dry_run:
        print(f"✓ Gobelo platform ready at: {root.resolve()}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialise the Gobelo platform directory tree."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("gobelo"),
        help="Root directory for the project (default: ./gobelo)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the tree without creating anything",
    )
    args = parser.parse_args()

    if not args.dry_run and args.root.exists():
        answer = input(
            f"'{args.root}' already exists. Continue and add missing items? [y/N] "
        )
        if answer.strip().lower() != "y":
            print("Aborted.")
            sys.exit(0)

    initialise(root=args.root, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
