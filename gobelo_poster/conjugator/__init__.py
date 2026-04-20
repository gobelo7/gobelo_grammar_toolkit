"""
Gobelo Conjugator Package
=========================
Public API for the GGT verb conjugation engine.

  from conjugator import build_paradigm, morpheme_key_example, GRAMMARS, load_yaml_grammar
"""

from .engine import build_paradigm, conjugate, morpheme_key_example, load_yaml_grammar
from .grammar_data import GRAMMARS

__all__ = [
    'build_paradigm',
    'conjugate',
    'morpheme_key_example',
    'load_yaml_grammar',
    'GRAMMARS',
]
