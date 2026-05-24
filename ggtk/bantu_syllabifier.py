"""
bantu_syllabifier.py — CLI utility
===================================
Command-line syllabification using Gobelo grammar YAML files.

All phonological data is loaded from the language YAML — no hardcoded
constants. Specify a language ISO code and the grammar drives everything.

Usage:
    python -m ggtk.bantu_syllabifier --lang toi "mbwazibide bantu"
    python -m ggtk.bantu_syllabifier --lang bem  # runs demo
"""

import sys
import argparse

from ggtk.core import GrammarConfig, GobeloGrammarLoader
from ggtk.core.syllabifier import (
    GrammarDrivenSyllabifier,
    Syllable,
    SyllabificationResult,
)


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

def format_table(result: SyllabificationResult) -> str:
    dotted = result.dotted()
    structures = " | ".join(_syl_structure(s) for s in result.syllables)
    return f"{result.word:<20} {dotted:<30} {result.count:>5}   {structures}"


def format_morpheme_detail(result: SyllabificationResult) -> str:
    lines = [f"Word: {result.word}  →  {result.dotted()}", ""]
    for idx, syl in enumerate(result.syllables, 1):
        flags = []
        if syl.is_long:
            flags.append("LONG")
        if syl.is_prenasalized:
            flags.append("PRENASALIZED")
        if syl.is_nasal_nucleus:
            flags.append("NASAL-NUCLEUS")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"  {idx}. {syl.text:<10}  "
            f"onset={syl.onset or '∅':>4}  "
            f"nucleus={syl.nucleus or '∅':>3}  "
            f"coda={syl.coda or '∅':>2}"
            f"{flag_str}"
        )
    return "\n".join(lines)


def _syl_structure(syl: Syllable) -> str:
    if syl.is_nasal_nucleus:
        return "N"
    s = ""
    if syl.onset:
        s += "NC" if syl.is_prenasalized else ("CC" if len(syl.onset) > 1 else "C")
    s += "VV" if syl.is_long else "V"
    if syl.coda:
        s += "C"
    return s


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DEMO_SENTENCES = {
    "toi": "mbwazibide bantu mboonga buumba bwakujaya",
    "bem": "abantu balelanda icibemba",
    "nya": "anthu amalankhula chinyanja",
}


def main():
    parser = argparse.ArgumentParser(description="Gobelo Grammar Toolkit — Syllabifier CLI")
    parser.add_argument("--lang", default="toi", help="ISO 639-3 language code (default: toi)")
    parser.add_argument("sentences", nargs="*", help="Sentences to syllabify")
    args = parser.parse_args()

    # Load grammar from YAML
    config = GrammarConfig(language=args.lang)
    loader = GobeloGrammarLoader(config=config)
    syl_data = loader.get_syllabification()
    iso_code = loader.get_metadata().iso_code

    syllabifier = GrammarDrivenSyllabifier()
    sentences = args.sentences or [DEMO_SENTENCES.get(args.lang, DEMO_SENTENCES["toi"])]

    for sentence in sentences:
        words = sentence.split()
        print("=" * 70)
        print(f"Language: {args.lang} | Method: {syl_data.method}")
        print(f"Sentence: {sentence}\n")
        print(f"{'Word':<20} {'Syllables':<30} {'Count':>5} {'Structure'}")
        print("-" * 70)

        total = 0
        results = []
        for word in words:
            result = syllabifier.syllabify(word, syl_data, iso_code=iso_code)
            print(format_table(result))
            results.append(result)
            total += result.count

        print(f"\nTotal syllables: {total}\n")
        print("Morpheme detail:")
        for result in results:
            print(format_morpheme_detail(result))
            print()


if __name__ == "__main__":
    main()
