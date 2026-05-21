"""
tests/unit/test_validator.py
===========================

Unit tests for the GGT grammar validator, especially legacy compatibility
with production reference-grammar phonology fields.
"""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_GGT = _REPO / "ggt"
for p in (_GGT, Path("/mnt/user-data/uploads")):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ggt.core.config import GrammarConfig
from ggt.core.validator import GrammarValidator


def test_validator_accepts_legacy_tones_and_syllable_structure() -> None:
    raw = {
        "metadata": {
            "language": "bem",
            "iso_code": "bem",
            "guthrie": "M.40",
            "grammar_version": "1.0.0",
            "min_loader_version": "1.0.0",
            "max_loader_version": "1.0.0",
        },
        "phonology": {
            "vowels": ["a", "e", "i", "o", "u"],
            "consonants": ["b", "m", "n", "w"],
            "tones": {"system": "two_level_HL"},
            "syllable_structure": {"pattern": ["(C)V(N)"]},
        },
        "noun_class_system": {
            "noun_classes": {
                "NC1": {
                    "id": "NC1",
                    "prefix": "um",
                    "semantic_domain": "people",
                    "active": True,
                }
            }
        },
        "concord_system": {
            "concords": {
                "subject_concords": {"1SG": "ni"}
            }
        },
        "verb_system": {
            "verbal_system_components": {
                "tam": {},
                "derivational_extensions": {},
            },
            "verb_slots": {},
        },
        "tokenization": {
            "word_boundary_pattern": "\\s+",
        },
    }

    validator = GrammarValidator()
    config = GrammarConfig(language="bem")
    flags = validator.validate(raw, config)

    assert flags == []
