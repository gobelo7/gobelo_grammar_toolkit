#!/usr/bin/env bash
# rename_yamls.sh — Rename ggt/languages/ files to ISO 639-3 code names.
#
# Run from inside your GGT repo root.
# Uses git mv so full history is preserved on each file.
#
# Before:                After:
#   chibemba.yaml    →     bem.yaml
#   chitonga.yaml    →     toi.yaml
#   chinyanja.yaml   →     nya.yaml
#   luvale.yaml      →     lue.yaml
#   lunda.yaml       →     lun.yaml
#   kaonde.yaml      →     kqn.yaml
#   lozi.yaml        →     loz.yaml

set -euo pipefail

LANG_DIR="ggt/languages"

declare -A RENAMES=(
    [chibemba]=bem
    [chitonga]=toi
    [chinyanja]=nya
    [luvale]=lue
    [lunda]=lun
    [kaonde]=kqn
    [lozi]=loz
)

for old in "${!RENAMES[@]}"; do
    new="${RENAMES[$old]}"
    src="$LANG_DIR/${old}.yaml"
    dst="$LANG_DIR/${new}.yaml"

    if [[ -f "$src" ]]; then
        git mv "$src" "$dst"
        echo "  renamed: ${old}.yaml → ${new}.yaml"
    elif [[ -f "$dst" ]]; then
        echo "  already done: ${new}.yaml exists"
    else
        echo "  WARNING: $src not found — skipping"
    fi
done

git commit -m "refactor(ggt): rename language YAMLs to ISO 639-3 codes"
echo ""
echo "Done. All YAML files now use ISO 639-3 names."
echo "Update GobeloGrammarLoader to load f'{iso_code}.yaml' if not already done."
