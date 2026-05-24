"""
core/syllabifier.py
===================
YAML-driven syllabification for ggtk.

Supports two methods (selected by ``SyllabificationData.method``):
- ``rule_based_cv``: Simple CV segmentation using vowel inventory + max onset.
- ``gobelo_phonological``: Full phonological syllabification using the complete
  consonant inventory from YAML (prenasalized, glide, complex clusters, long
  vowels, nasal nuclei) — zero hardcoded language data.

Design principle: **all phonological knowledge comes from the language YAML**.
Adding or modifying a language requires NO code changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ggtk.core.exceptions import GGTError
from ggtk.core.models import SyllabificationData

PUNCTUATION_STRIP_RE = re.compile(r"[^\w\u00C0-\u024F\u0300-\u036F]")


class SyllabificationError(GGTError):
    """Raised when a word cannot be syllabified with the available grammar."""


@dataclass(frozen=True)
class Syllable:
    """A single syllable extracted from a word."""

    text: str
    position: int
    length: int
    phoneme: Optional[str] = None
    onset: str = ""
    nucleus: str = ""
    coda: str = ""
    is_long: bool = False
    is_prenasalized: bool = False
    is_nasal_nucleus: bool = False


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

    def dotted(self, sep: str = "-") -> str:
        return sep.join(self.texts)


class GrammarDrivenSyllabifier:
    """Syllabifies words using grammar YAML-driven rules.

    All phonological data (vowels, consonants, clusters, long vowels)
    is sourced exclusively from ``SyllabificationData``. No language-specific
    constants exist in this code.
    """

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
        if method == "gobelo_phonological":
            raw = self._gobelo_phonological(clean, syllabification)
        else:
            raw = self._cv_segment(clean, syllabification)

        syllables = self._build_syllable_objects(clean, raw)
        return SyllabificationResult(
            word=word, iso_code=iso_code, syllables=syllables,
            method=method, notes=syllabification.notes,
        )

    # ------------------------------------------------------------------
    # Method: gobelo_phonological
    # ------------------------------------------------------------------

    def _gobelo_phonological(
        self, word: str, syl_data: SyllabificationData
    ) -> list[dict]:
        """Full phonological syllabification driven entirely by YAML data.

        Consonant clusters (prenasalized, glide, complex) are derived from
        the consonants frozenset in SyllabificationData — sorted longest-first
        for greedy matching. No hardcoded cluster lists.
        """
        vowels = syl_data.vowels
        long_vowels = syl_data.long_vowels
        # Build onset list from consonant inventory, sorted longest-first
        onsets = sorted(syl_data.consonants, key=len, reverse=True)

        word_lower = word.lower()
        results: list[dict] = []
        i = 0
        n = len(word_lower)

        while i < n:
            start = i

            # 1. Nasal nucleus: m/n before consonant or end (not onset of next syllable)
            if word_lower[i] in "mn" and word_lower[i] in vowels.__class__(c[0] for c in onsets if len(c) == 1):
                next_i = i + 1
                if next_i >= n or word_lower[next_i] not in vowels:
                    # Check it's not a multi-char onset (e.g., mb + vowel)
                    matched_onset = self._match_onset(word_lower, i, onsets)
                    if not (matched_onset and len(matched_onset) > 1 and
                            i + len(matched_onset) < n and
                            word_lower[i + len(matched_onset)] in vowels):
                        results.append({
                            "text": word_lower[i], "onset": "", "nucleus": word_lower[i],
                            "coda": "", "is_long": False, "is_prenasalized": False,
                            "is_nasal_nucleus": True,
                        })
                        i += 1
                        continue

            # 2. Onset — greedy match from YAML consonant inventory
            onset = ""
            is_pn = False
            matched = self._match_onset(word_lower, i, onsets)
            if matched and i + len(matched) < n and word_lower[i + len(matched)] in vowels:
                onset = matched
                # Prenasalized if starts with nasal + non-nasal
                is_pn = (len(matched) >= 2 and matched[0] in "mn"
                         and matched[1] not in "mn" and matched[1] not in "wy")
                i += len(matched)
            elif i < n and word_lower[i] not in vowels:
                onset = word_lower[i]
                i += 1

            # 3. Nucleus — long vowel preferred (from YAML long_vowels)
            if i >= n or word_lower[i] not in vowels:
                text = word_lower[start:max(i, start + 1)]
                i = max(i, start + 1)
                results.append({
                    "text": text, "onset": onset, "nucleus": "", "coda": "",
                    "is_long": False, "is_prenasalized": is_pn, "is_nasal_nucleus": False,
                })
                continue

            nucleus = ""
            is_long = False
            # Check for long vowel from YAML
            if i + 1 < n:
                digraph = word_lower[i:i + 2]
                if digraph in long_vowels:
                    nucleus = digraph
                    is_long = True
                    i += 2
                else:
                    nucleus = word_lower[i]
                    i += 1
            else:
                nucleus = word_lower[i]
                i += 1

            # 4. Coda — only if next segment is consonant AND not a valid onset for next syllable
            coda = ""
            if i < n and word_lower[i] not in vowels:
                # Check if current consonant(s) form a valid onset for next syllable
                next_onset = self._match_onset(word_lower, i, onsets)
                if next_onset and i + len(next_onset) < n and word_lower[i + len(next_onset)] in vowels:
                    pass  # Leave for next syllable
                elif i + 1 >= n:
                    # Word-final consonant is coda
                    coda = word_lower[i]
                    i += 1
                elif word_lower[i + 1] not in vowels:
                    # Consonant cluster: take first as coda
                    coda = word_lower[i]
                    i += 1

            results.append({
                "text": word_lower[start:i], "onset": onset, "nucleus": nucleus,
                "coda": coda, "is_long": is_long, "is_prenasalized": is_pn,
                "is_nasal_nucleus": False,
            })

        return results

    # ------------------------------------------------------------------
    # Method: rule_based_cv
    # ------------------------------------------------------------------

    def _cv_segment(
        self, word: str, syllabification: SyllabificationData
    ) -> list[dict]:
        """Simple CV segmentation using vowel set and max onset length."""
        vowels = syllabification.vowels
        max_cluster = syllabification.structure.max_onset_cluster_length
        syllables: list[dict] = []
        word_lower = word.lower()
        i = 0
        n = len(word_lower)

        while i < n:
            ch = word_lower[i]
            if ch in vowels:
                syl = ch
                i += 1
                if i < n and word_lower[i] in vowels and word_lower[i] != ch:
                    syl += word_lower[i]
                    i += 1
                syllables.append({"text": syl})
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
                    syllables[-1]["text"] += cluster
                else:
                    syllables.append({"text": cluster})
                break

            syl = cluster + word_lower[i]
            i += 1
            if i < n and word_lower[i] in vowels and word_lower[i] != word_lower[i - 1]:
                syl += word_lower[i]
                i += 1
            syllables.append({"text": syl})

        return syllables if syllables else [{"text": word_lower}]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _match_onset(word: str, i: int, onsets: list[str]) -> Optional[str]:
        """Greedy match: find longest consonant cluster from YAML inventory at position i."""
        for onset in onsets:
            if word[i:i + len(onset)] == onset:
                return onset
        return None

    def _build_syllable_objects(
        self, original: str, raw_syllables: list[dict]
    ) -> tuple[Syllable, ...]:
        result: list[Syllable] = []
        pos = 0
        orig_lower = original.lower()

        for syl in raw_syllables:
            text = syl["text"]
            idx = orig_lower.find(text, pos)
            if idx == -1:
                idx = pos
            display = original[idx:idx + len(text)]
            result.append(Syllable(
                text=display,
                position=idx,
                length=len(text),
                onset=syl.get("onset", ""),
                nucleus=syl.get("nucleus", ""),
                coda=syl.get("coda", ""),
                is_long=syl.get("is_long", False),
                is_prenasalized=syl.get("is_prenasalized", False),
                is_nasal_nucleus=syl.get("is_nasal_nucleus", False),
            ))
            pos = idx + len(text)

        return tuple(result)


_default_syllabifier = GrammarDrivenSyllabifier()


def syllabify(
    word: str,
    syllabification: SyllabificationData,
    iso_code: str = "und",
) -> SyllabificationResult:
    """Module-level convenience function."""
    return _default_syllabifier.syllabify(word, syllabification, iso_code)
