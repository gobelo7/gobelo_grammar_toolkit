"""
core/syllabifier.py
===================
YAML-driven syllabification helper for GGT.

This module syllabifies words using language-specific configuration loaded
from a Gobelo grammar YAML file. The syllabification algorithm is driven by
``SyllabificationData`` and ``SyllableStructure`` metadata derived from the
language grammar, including the vowel inventory and syllable-structure
patterns declared in ``phonology.syllable_structure``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ggt.core.exceptions import GGTError
from ggt.core.models import SyllabificationData

PUNCTUATION_STRIP_RE = re.compile(r"[^\w\u00C0-\u024F\u0300-\u036F]")


class SyllabificationError(GGTError):
    """Raised when a word cannot be syllabified with the available grammar."""


@dataclass(frozen=True)
class Syllable:
    """A single syllable extracted from a word.

    Parameters
    ----------
    text : str
        Surface form of the syllable.
    position : int
        Zero-based character offset in the original word.
    length : int
        Number of characters in the syllable.
    phoneme : Optional[str]
        Optional phonemic/IPA representation.
    """

    text: str
    position: int
    length: int
    phoneme: Optional[str] = None


@dataclass(frozen=True)
class SyllabificationResult:
    """Immutable result of syllabifying one word."""

    word: str
    iso_code: str
    syllables: tuple[Syllable, ...]
    method: str
    notes: Optional[str] = None

    @property
    def texts(self) -> tuple[str, ...]:
        return tuple(s.text for s in self.syllables)

    @property
    def count(self) -> int:
        return len(self.syllables)


class GrammarDrivenSyllabifier:
    """Syllabifies words using grammar YAML-driven rules."""

    def syllabify(
        self,
        word: str,
        syllabification: SyllabificationData,
        iso_code: str = "und",
    ) -> SyllabificationResult:
        clean = PUNCTUATION_STRIP_RE.sub("", word)

        if not clean:
            raise SyllabificationError(
                f"Word '{word}' is empty after punctuation stripping."
            )

        method = syllabification.method
        if method == "rule_based_cv":
            raw_syllables = self._cv_segment(clean, syllabification)
        else:
            raw_syllables = self._cv_segment(clean, syllabification)

        syllables = self._build_syllable_objects(clean, raw_syllables)

        return SyllabificationResult(
            word=word,
            iso_code=iso_code,
            syllables=syllables,
            method=method,
            notes=syllabification.notes,
        )

    def _cv_segment(
        self,
        word: str,
        syllabification: SyllabificationData,
    ) -> list[str]:
        vowels = syllabification.vowels
        max_cluster = syllabification.structure.max_onset_cluster_length
        syllables: list[str] = []
        word_lower = word.lower()
        i = 0
        n = len(word_lower)

        while i < n:
            ch = word_lower[i]
            if ch in vowels:
                syl = ch
                i += 1
                if (
                    i < n
                    and word_lower[i] in vowels
                    and word_lower[i] != ch
                ):
                    syl += word_lower[i]
                    i += 1
                syllables.append(syl)
                continue

            cluster = ""
            cluster_start = i
            while i < n and word_lower[i] not in vowels:
                if i - cluster_start >= max_cluster:
                    break
                cluster += word_lower[i]
                i += 1

            if i >= n:
                if syllables:
                    syllables[-1] += cluster
                else:
                    syllables.append(cluster)
                break

            syl = cluster + word_lower[i]
            i += 1
            if (
                i < n
                and word_lower[i] in vowels
                and word_lower[i] != word_lower[i - 1]
            ):
                syl += word_lower[i]
                i += 1
            syllables.append(syl)

        return syllables if syllables else [word_lower]

    def _build_syllable_objects(
        self,
        original: str,
        raw_syllables: list[str],
    ) -> tuple[Syllable, ...]:
        result: list[Syllable] = []
        search_pos = 0
        orig_lower = original.lower()

        for syl_text in raw_syllables:
            idx = orig_lower.find(syl_text, search_pos)
            if idx == -1:
                idx = search_pos

            display = original[idx : idx + len(syl_text)]
            result.append(
                Syllable(
                    text=display,
                    position=idx,
                    length=len(syl_text),
                    phoneme=None,
                )
            )
            search_pos = idx + len(syl_text)

        return tuple(result)


_default_syllabifier = GrammarDrivenSyllabifier()


def syllabify(
    word: str,
    syllabification: SyllabificationData,
    iso_code: str = "und",
) -> SyllabificationResult:
    return _default_syllabifier.syllabify(word, syllabification, iso_code)
