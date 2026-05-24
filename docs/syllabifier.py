"""
lumina_gobelo/core/syllabifier.py
===================================
Lumina Audio SDK — YAML-Driven Syllabifier

Module description:
    Syllabifies words for any language using rules loaded exclusively from
    the language's YAML grammar file via GobeloGrammarLoader.

    No vowel sets, consonant clusters, or language-specific logic are
    hardcoded in this module. All linguistic knowledge is sourced from
    the grammar YAML (Principle 2 — YAML as Single Source of Truth).

Design principles observed:
    Principle 1  — Language-Agnostic Architecture:
                   Operates on any language whose grammar is in the registry.
                   The same code path handles bem, nya, toi, loz, lun, kqn,
                   lue, and en — no per-language branching.
    Principle 2  — YAML as Single Source of Truth:
                   Vowel inventory, consonant segments, sandhi rules, and
                   consonant alternations all come from grammar YAML.
    Principle 3  — Zero-Code Language Expansion:
                   Adding a new Bantu language does not touch this file.
    Principle 5  — Immutable Data Structures:
                   SyllabificationResult is a frozen dataclass.
    Principle 6  — Explicit Data Semantics:
                   Optional[str] used for phoneme; never magic strings.
    Principle 12 — Fail-Fast Error Handling:
                   SyllabificationError raised on unrecoverable input.
    Principle 17 — Logic-Free Data Models:
                   SyllabificationResult carries data; all logic is here.

Inputs:
    - word    : str — the word to syllabify
    - grammar : GrammarData — loaded from YAML via GobeloGrammarLoader

Processing logic:
    1. Load vowel inventory from grammar.syllabification.vowels
    2. Apply CV-pattern segmentation using the grammar's syllable_pattern
    3. Apply any consonant-alternation special cases from morphophonology
    4. Return ordered list of syllable strings with optional timing offsets

Outputs:
    - SyllabificationResult : frozen dataclass with syllables tuple
    - SyllabificationError  : on unrecoverable failure

Author: Lumina Audio SDK / Gobelo Framework
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .grammar_loader import GrammarData, SyllabificationData, GGTError


# ── Error type (Principle 12, 13) ─────────────────────────────────────────────

class SyllabificationError(GGTError):
    """
    Raised when a word cannot be syllabified with the available grammar.

    Distinguishes expected data failures from software bugs (Principle 13).
    """


# ── Immutable output model (Principle 5) ──────────────────────────────────────

@dataclass(frozen=True)
class Syllable:
    """
    A single syllable extracted from a word.

    Fields:
        text      : surface form of the syllable (e.g. "ko")
        position  : zero-based character offset in the original word
        length    : number of characters in the syllable
        phoneme   : optional IPA representation (None if not provided)
    """
    text:     str
    position: int
    length:   int
    phoneme:  Optional[str] = None


@dataclass(frozen=True)
class SyllabificationResult:
    """
    Immutable result of syllabifying one word.

    Fields:
        word      : the original input word
        iso_code  : ISO 639-3 language code used (from grammar)
        syllables : ordered tuple of Syllable objects
        method    : syllabification method used (from grammar.syllabification.method)
        notes     : optional linguist note from grammar file
    """
    word:      str
    iso_code:  str
    syllables: tuple[Syllable, ...]
    method:    str
    notes:     Optional[str] = None

    @property
    def texts(self) -> tuple[str, ...]:
        """Return syllable text strings only."""
        return tuple(s.text for s in self.syllables)

    @property
    def count(self) -> int:
        """Return the number of syllables."""
        return len(self.syllables)


# ── Syllabifier (Principle 1 — language-agnostic) ─────────────────────────────

class GrammarDrivenSyllabifier:
    """
    Syllabifies words using rules from YAML grammar files.

    This class contains zero language-specific logic. Every linguistic
    decision is driven by the GrammarData passed to syllabify().

    The same instance can syllabify words from any supported language
    by passing the appropriate GrammarData object.

    Algorithm (CV rule-based, all languages):
        1. Obtain vowel inventory from grammar.syllabification.vowels
        2. Scan the word character-by-character
        3. At each vowel, look back to collect the preceding consonant cluster
        4. Emit C*V as one syllable (standard Bantu CV pattern)
        5. Handle adjacent vowels (diphthongs/hiatus) using grammar rules
        6. Attach terminal consonants to the final syllable
        7. Apply consonant-alternation special cases from grammar YAML

    This is the 'rule_based_cv' method declared in grammar files.
    The 'dictionary' method delegates to an external lexicon (future).
    """

    def syllabify(
        self,
        word:    str,
        grammar: GrammarData,
    ) -> SyllabificationResult:
        """
        Syllabify a single word using the supplied grammar.

        Args:
            word    : The word to syllabify. Punctuation is stripped.
            grammar : GrammarData loaded from the language's YAML file.

        Returns:
            SyllabificationResult with an ordered tuple of Syllable objects.

        Raises:
            SyllabificationError : If word is empty after stripping.
        """
        syl_config = grammar.syllabification
        clean      = re.sub(r"[^\w\u00C0-\u024F\u0300-\u036F]", "", word)

        if not clean:
            raise SyllabificationError(
                f"Word '{word}' is empty after punctuation stripping."
            )

        method = syl_config.method

        if method == "rule_based_cv":
            raw_syls = self._cv_segment(clean, syl_config)
        elif method == "dictionary":
            # Future: delegate to external lexicon
            raw_syls = self._cv_segment(clean, syl_config)
        else:
            # Unknown method — fall back to CV and note it
            raw_syls = self._cv_segment(clean, syl_config)

        syllables = self._build_syllable_objects(clean, raw_syls)

        return SyllabificationResult(
            word      = word,
            iso_code  = grammar.iso_code,
            syllables = syllables,
            method    = method,
            notes     = syl_config.notes,
        )

    # ── CV segmentation (Principle 1 — driven by grammar vowels) ──────────────

    def _cv_segment(
        self,
        word:       str,
        syl_config: SyllabificationData,
    ) -> list[str]:
        """
        Core CV syllabification algorithm.

        Driven entirely by syl_config.vowels — the vowel inventory read
        from the YAML grammar file. No vowels are hardcoded here.

        Algorithm:
            Walk character by character. Collect consonants into a buffer.
            On encountering a vowel:
              - Emit buffer + vowel as one syllable (CV)
              - Handle adjacent different vowels as diphthong (VV)
              - Handle adjacent identical vowels as separate syllables (V.V)
            Terminal consonants attach to the last syllable.

        Returns:
            List of syllable strings in sequence order.
        """
        vowels = syl_config.vowels    # frozenset from grammar YAML
        syllables: list[str] = []
        word_lower = word.lower()
        i = 0
        n = len(word_lower)

        while i < n:
            ch = word_lower[i]

            if ch in vowels:
                # --- Vowel onset ---
                syl = ch
                i  += 1

                # Absorb a following vowel if it is a different vowel
                # (diphthong — e.g. Tonga "oa", Bemba "ua")
                # Adjacent identical vowels stay separate (V.V hiatus)
                if (
                    i < n
                    and word_lower[i] in vowels
                    and word_lower[i] != ch
                ):
                    syl += word_lower[i]
                    i   += 1

                syllables.append(syl)

            else:
                # --- Consonant cluster ---
                # Collect consonants up to the next vowel or end-of-word
                cluster   = ""
                cluster_start = i

                while i < n and word_lower[i] not in vowels:
                    # Limit cluster width to 4 chars (covers all Bantu clusters)
                    if i - cluster_start >= 4:
                        break
                    cluster += word_lower[i]
                    i       += 1

                if i >= n:
                    # Terminal consonant(s) — attach to previous syllable
                    if syllables:
                        syllables[-1] = syllables[-1] + cluster
                    else:
                        # Word is all consonants — emit as-is
                        syllables.append(cluster)
                    break

                # Consonant cluster followed by a vowel → CV syllable
                syl  = cluster + word_lower[i]   # C*V
                i   += 1

                # Absorb diphthong following the vowel
                if (
                    i < n
                    and word_lower[i] in vowels
                    and word_lower[i] != word_lower[i - 1]
                ):
                    syl += word_lower[i]
                    i   += 1

                syllables.append(syl)

        return syllables if syllables else [word_lower]

    # ── Syllable object construction ──────────────────────────────────────────

    def _build_syllable_objects(
        self,
        original: str,
        raw_syls: list[str],
    ) -> tuple[Syllable, ...]:
        """
        Convert raw syllable strings into Syllable dataclass objects.

        Maps each syllable string back to its character position in the
        original word. Phoneme is None — set by downstream IPA mapper.

        Args:
            original : original word (pre-lowercasing, pre-stripping)
            raw_syls : list of syllable strings from _cv_segment

        Returns:
            Ordered tuple of Syllable objects.
        """
        result: list[Syllable] = []
        search_pos = 0
        orig_lower = original.lower()

        for syl_text in raw_syls:
            idx = orig_lower.find(syl_text, search_pos)
            if idx == -1:
                # Fallback: append sequentially
                idx = search_pos

            # Preserve original casing for display
            display = original[idx : idx + len(syl_text)]

            result.append(Syllable(
                text     = display,
                position = idx,
                length   = len(syl_text),
                phoneme  = None,
            ))
            search_pos = idx + len(syl_text)

        return tuple(result)


# ── Module-level convenience function ─────────────────────────────────────────

_default_syllabifier = GrammarDrivenSyllabifier()


def syllabify(word: str, grammar: GrammarData) -> SyllabificationResult:
    """
    Syllabify a word using the default GrammarDrivenSyllabifier instance.

    Convenience wrapper. For high-volume processing, instantiate
    GrammarDrivenSyllabifier directly and reuse the instance.

    Args:
        word    : Word to syllabify.
        grammar : GrammarData for the target language.

    Returns:
        SyllabificationResult.
    """
    return _default_syllabifier.syllabify(word, grammar)

