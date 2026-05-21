#!/usr/bin/env bash
# Build all HFST transducers from GGT package source
# Assumes GGT is installed (pip install -e ../ggt) and
# that ggt/hfst/{lang}_hfst/ folders contain .lexc + .twolc files.
set -euo pipefail

GGT_HFST="$(python -c 'import ggt; import pathlib; print(pathlib.Path(ggt.__file__).parent / "hfst")')"

LANGS=(bem toi nya lue lun kqn loz)

declare -A LANG_FOLDERS=(
    [bem]=bemba_hfst [toi]=chitonga_hfst [nya]=chinyanja_hfst
    [lue]=luvale_hfst [lun]=lunda_hfst [kqn]=kaonde_hfst [loz]=lozi_hfst
)

for lang in "${LANGS[@]}"; do
    folder="${LANG_FOLDERS[$lang]}"
    src="$GGT_HFST/$folder/$lang.lexc"
    out="$GGT_HFST/$folder/$lang.hfst"
    echo "Building $lang ($folder)..."
    hfst-lexc "$src" -o "$out"
done
echo "All transducers built."
