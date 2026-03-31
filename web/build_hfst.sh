#!/usr/bin/env bash
# =============================================================
#  scripts/build_hfst.sh
#  Compile HFST morphological analysers for all 7 languages.
#
#  Usage:
#    ./scripts/build_hfst.sh              # build all languages
#    ./scripts/build_hfst.sh chitonga     # build one language
#    ./scripts/build_hfst.sh --no-test    # skip smoke tests
#    ./scripts/build_hfst.sh --clean      # remove build/ first
#
#  Prerequisites:
#    pip install pyyaml
#    HFST tools: hfst-lexc, hfst-twolc, hfst-compose-intersect, hfst-invert
#      macOS:  brew install hfst
#      Debian: sudo apt install hfst
#      Source: https://hfst.github.io
#
#  Output:
#    gobelo_grammar_toolkit/hfst/compiled/<language>-analyser.hfst
#    gobelo_grammar_toolkit/hfst/compiled/<language>-generator.hfst
# =============================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FST_DIR="$REPO_ROOT/gobelo_grammar_toolkit/hfst"
LEXICON_DIR="$FST_DIR/lexicons"
COMPILED_DIR="$FST_DIR/compiled"
BUILD_PY="$FST_DIR/build_fst.py"
LANGUAGES=(chitonga chibemba chinyanja silozi luvale lunda kaonde)

# ── parse args ─────────────────────────────────────────────────
RUN_TESTS=true
CLEAN=false
TARGET_LANGS=()

for arg in "$@"; do
  case "$arg" in
    --no-test) RUN_TESTS=false ;;
    --clean)   CLEAN=true ;;
    --help|-h)
      grep '^#' "$0" | grep -v '^#!' | sed 's/^# *//'
      exit 0 ;;
    *)
      # Treat unrecognised args as language names
      TARGET_LANGS+=("$arg") ;;
  esac
done

if [ ${#TARGET_LANGS[@]} -eq 0 ]; then
  TARGET_LANGS=("${LANGUAGES[@]}")
fi

# ── check prerequisites ────────────────────────────────────────
check_tool() {
  if ! command -v "$1" &>/dev/null; then
    echo "ERROR: '$1' not found on PATH."
    echo "Install HFST: https://hfst.github.io  or  sudo apt install hfst"
    exit 1
  fi
}
for tool in hfst-lexc hfst-twolc hfst-compose-intersect hfst-invert hfst-lookup; do
  check_tool "$tool"
done
check_tool python3

# ── clean ──────────────────────────────────────────────────────
if $CLEAN; then
  echo "Cleaning compiled directory: $COMPILED_DIR"
  rm -rf "$COMPILED_DIR"
fi
mkdir -p "$COMPILED_DIR"

# ── build each language ────────────────────────────────────────
SUCCESS=()
FAILURE=()

for lang in "${TARGET_LANGS[@]}"; do
  echo ""
  echo "══════════════════════════════════════════"
  echo "  Building: $lang"
  echo "══════════════════════════════════════════"

  LANG_LEXICON_DIR="$LEXICON_DIR/$lang"
  VERBS_YAML="$LANG_LEXICON_DIR/${lang}_verbs.yaml"
  NOUNS_YAML="$LANG_LEXICON_DIR/${lang}_nouns.yaml"
  CLOSED_YAML="$LANG_LEXICON_DIR/${lang}_closed.yaml"

  # Check lexicon files exist
  missing=()
  for f in "$VERBS_YAML" "$NOUNS_YAML" "$CLOSED_YAML"; do
    [[ -f "$f" ]] || missing+=("$f")
  done
  if [ ${#missing[@]} -gt 0 ]; then
    echo "  SKIP: Missing lexicon file(s):"
    for f in "${missing[@]}"; do echo "    $f"; done
    FAILURE+=("$lang (missing lexicons)")
    continue
  fi

  # Run Python build script
  build_args=(
    python3 "$BUILD_PY"
    --lang    "$lang"
    --verbs   "$VERBS_YAML"
    --nouns   "$NOUNS_YAML"
    --closed  "$CLOSED_YAML"
    --outdir  "$COMPILED_DIR"
  )
  if ! $RUN_TESTS; then
    build_args+=(--no-test)
  fi

  if "${build_args[@]}"; then
    SUCCESS+=("$lang")
    echo "  ✓ $lang → $COMPILED_DIR/${lang}-analyser.hfst"
  else
    FAILURE+=("$lang (build script failed)")
    echo "  ✗ $lang build FAILED"
  fi
done

# ── summary ────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
echo "  Build Summary"
echo "══════════════════════════════════════════"
echo "  Successful: ${#SUCCESS[@]} / ${#TARGET_LANGS[@]}"
for lang in "${SUCCESS[@]}"; do echo "    ✓ $lang"; done
if [ ${#FAILURE[@]} -gt 0 ]; then
  echo "  Failed:"
  for f in "${FAILURE[@]}"; do echo "    ✗ $f"; done
fi

echo ""
if [ ${#FAILURE[@]} -gt 0 ]; then
  exit 1
fi
exit 0
