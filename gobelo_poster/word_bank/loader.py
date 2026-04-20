"""
Word Bank Loader
================
Loads the Word of the Day pool for each language.
Priority order:
  1. Entries marked as verified in the language YAML word_bank section
  2. Entries from the Chitonga corpus frequency list (chitonga only)
  3. Fallback to hardcoded minimal set in the YAML files here

Daily word selection: deterministic seed from date so the same word
appears for all users on the same day.
"""
import datetime
from pathlib import Path
import yaml

_BANK_DIR = Path(__file__).parent
_cache: dict[str, list] = {}

def _load(lang: str) -> list:
    if lang in _cache:
        return _cache[lang]
    p = _BANK_DIR / f"{lang}.yaml"
    if p.exists():
        data = yaml.safe_load(p.read_text(encoding='utf-8'))
        words = data.get('words', [])
    else:
        words = []
    _cache[lang] = words
    return words

def get_word_of_day(lang: str) -> dict:
    pool = _load(lang)
    if not pool:
        return {
            'word': lang,
            'gloss': f'No word bank for {lang} yet',
            'nc': '', 'prefix': '', 'plural': '', 'pos': 'noun',
            'example': 'Add words to gobelo_poster/word_bank/{lang}.yaml',
        }
    d = datetime.date.today()
    seed = d.year * 10000 + d.month * 100 + d.day
    return pool[seed % len(pool)]