#!/usr/bin/env bash
# Build all HFST transducers from GGTK package source
# Assumes GGTK is installed (pip install -e ../ggtk) and
# that ggtk/hfst/{lang}_hfst/ folders contain .lexc + .twolc files.
set -euo pipefail

ggtk_HFST="$(python -c 'import ggtk; import pathlib; print(pathlib.Path(ggtk.__file__).parent / "hfst")')"

LANGS=(bem toi nya lue lun kqn loz)

declare -A LANG_FOLDERS=(
    [bem]=bemba_hfst [toi]=chitonga_hfst [nya]=chinyanja_hfst
    [lue]=luvale_hfst [lun]=lunda_hfst [kqn]=kaonde_hfst [loz]=lozi_hfst
)

for lang in "${LANGS[@]}"; do
    folder="${LANG_FOLDERS[$lang]}"
    src="$ggtk_HFST/$folder/$lang.lexc"
    out="$ggtk_HFST/$folder/$lang.hfst"
    echo "Building $lang ($folder)..."
    hfst-lexc "$src" -o "$out"
done
echo "All transducers built."
