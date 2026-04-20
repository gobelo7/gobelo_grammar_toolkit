"""
GGT Conjugation Engine
======================
Generates surface verb forms by:
  1. Selecting the correct SC allomorph based on phonological context
  2. Assembling morpheme parts in template order (NEG + SC + TAM + ROOT + EXT + FV)
  3. Applying morphophonological rules (SND.1/SND.2) at each boundary

Optionally loads full grammar data from the GGT YAML files when they are
present on disk; falls back to the embedded grammar_data.py otherwise.

Public API
----------
  conjugate(sc_data, tam, root, negative, ...) -> str
  build_paradigm(grammar, root, tam_ids, show_neg, show_loc) -> list[dict]
  load_yaml_grammar(yaml_path) -> dict | None
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .morphophonology import (
    join_morphemes, VOWELS,
    appl_suffix, caus_suffix, pass_suffix, stat_suffix, rev_suffix,
)
from .grammar_data import GRAMMARS


# ── YAML loader (optional — enriches embedded data with full YAML content) ────

def load_yaml_grammar(yaml_path: str | Path) -> dict | None:
    """
    Attempt to load a GGT grammar YAML file and extract conjugation data.
    Returns a grammar dict compatible with build_paradigm(), or None on error.

    The YAML structure expected is the flat top-level schema from chitonga.yaml
    (no language-name root wrapper).  Only the fields needed for verb
    conjugation are extracted; everything else is ignored.
    """
    try:
        import yaml
    except ImportError:
        return None

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f)
    except Exception:
        return None

    if not isinstance(raw, dict):
        return None

    # Check if this looks like a valid grammar file (not a template)
    metadata = raw.get('metadata')
    if not isinstance(metadata, dict):
        return None
    
    language = metadata.get('language')
    if not isinstance(language, dict):
        return None

    # Pull the language key from metadata
    lang_key_from_yaml = (
        language.get('name', '')
           .lower()
           .replace('chi', 'chi')
           .replace(' ', '')
    )

    # Map YAML language name to our registry key
    _name_map = {
        'chitonga':  'chitonga',
        'chinyanja': 'chinyanja',
        'chichewa':  'chinyanja',
        'chibemba':  'chibemba',
        'silozi':    'silozi',
        'cikaonde':  'cikaonde',
        'ciluvale':  'ciluvale',
        'cilunda':   'cilunda',
    }
    lang_key = _name_map.get(lang_key_from_yaml)
    if not lang_key or lang_key not in GRAMMARS:
        return None

    # Start with embedded data (always present) then patch with YAML values
    grammar = dict(GRAMMARS[lang_key])

    # Extract TAM markers from verb_system
    vs = raw.get('verb_system', {})
    vsc = vs.get('verbal_system_components', {})
    yaml_tam = vsc.get('tam', {})
    if yaml_tam:
        for tid, entry in yaml_tam.items():
            if tid in grammar['tam']:
                # Patch marker and function text; keep our fv/neg_fv
                if 'forms' in entry:
                    grammar['tam'][tid]['marker'] = (
                        entry['forms'] if isinstance(entry['forms'], str)
                        else (entry['forms'][0] if entry['forms'] else '')
                    )
                if 'function' in entry:
                    grammar['tam'][tid]['yaml_function'] = entry['function']

    # Extract negation
    neg_pre_yaml = vsc.get('negation_pre', {})
    if neg_pre_yaml:
        pres_neg = neg_pre_yaml.get('present', {})
        forms = pres_neg.get('forms', [])
        if forms:
            grammar['neg_pre'] = forms[0] if isinstance(forms, list) else forms

    neg_infix_yaml = vsc.get('negation_infix', {})
    if neg_infix_yaml:
        neg_entry = neg_infix_yaml.get('negative', {})
        infix_form = neg_entry.get('forms', '')
        if infix_form:
            # Strip surrounding dashes: '-sa-' → 'sa'
            grammar['neg_infix'] = infix_form.strip('-')

    grammar['yaml_path'] = str(yaml_path)
    return grammar


# ── SC allomorph selection ────────────────────────────────────────────────────

def _select_sc(sc_data: dict, following: str) -> str:
    """
    Return the surface form of a subject concord given what follows it.

    Rules applied (in priority order):
      1. 'before_v' allomorph — used when following starts with a vowel
         (e.g. ndi → nd before a-initial TAM; cf. SND.4 vowel elision)
      2. Canonical 'form' — default
    """
    form = sc_data.get('form', '')
    if following and following[0] in VOWELS and 'before_v' in sc_data:
        return sc_data['before_v']
    return form


# ── Extension form selection ──────────────────────────────────────────────────

def _ext_form(ext_key: str, root: str, lang: str) -> str:
    """
    VH.1 — Return the extension suffix conditioned on stem vowels and language.
    The returned string is the bare suffix morpheme (no hyphens).
    """
    ext = ext_key.upper()
    if ext == 'APPL':  return appl_suffix(root, lang)
    if ext == 'CAUS':  return caus_suffix(root, lang)
    if ext == 'PASS':  return pass_suffix(root, lang)
    if ext == 'STAT':  return stat_suffix(root)
    if ext == 'REV':   return rev_suffix(root)
    if ext == 'RECIP': return 'an'
    if ext == 'PERF':
        # Perfective extension (not TAM perfect): -ilil-/-elel-
        return 'elel' if any(v in {'e', 'o'} for v in root.lower()) else 'ilil'
    if ext == 'INTENS':
        return 'esy' if any(v in {'e', 'o'} for v in root.lower()) else 'isy'
    return ext.lower()


# ── Core conjugation ──────────────────────────────────────────────────────────

def conjugate(
    sc_data:    dict,
    tam:        dict,
    root:       str,
    negative:   bool         = False,
    neg_type:   str          = 'pre',
    neg_pre:    str          = 'ta',
    neg_infix:  str          = 'sa',
    lang:       str          = 'chitonga',
    extensions: list[str]    = None,
) -> str:
    """
    Conjugate a verb form and return the phonologically correct surface string.

    Parameters
    ----------
    sc_data   : subject concord entry from grammar['subject_concords']
    tam       : TAM entry from grammar['tam']
    root      : bare verb root (strip leading/trailing hyphens before passing)
    negative  : produce the negative form
    neg_type  : 'pre' (pre-initial, e.g. ta-) | 'infix' (e.g. ChiNyanja -sa-)
    neg_pre   : pre-initial negation marker (neg_type == 'pre')
    neg_infix : infix negation marker (neg_type == 'infix')
    lang      : language key (used for VH.1 extension conditioning)
    extensions: list of extension keys in application order, e.g. ['APPL']

    Returns
    -------
    str — surface verb form with morphophonology applied
    """
    root = root.strip('-').strip()
    fv     = tam.get('neg_fv', 'i') if negative else tam['fv']
    marker = tam.get('marker', '')

    # Strip the conventional infinitive-final -a from the root before joining
    # with a vowel-initial final vowel (e.g. 'bona' + 'ide' → 'bon' + 'ide' → 'bonide',
    # not 'bona' + 'ide' → SND.2 a+i→e → 'bonede').
    # The user enters roots in their dictionary/infinitive form (e.g. 'bona' = to see).
    stem = root[:-1] if (root.endswith('a') and fv and fv[0] in VOWELS) else root

    # What immediately follows the SM determines allomorph choice
    if negative and neg_type == 'infix':
        first_after_sc = neg_infix or marker or stem
    else:
        first_after_sc = marker if marker else stem

    sc_form = _select_sc(sc_data, first_after_sc)

    # ── Assemble parts ────────────────────────────────────────────────────────
    parts: list[str] = []

    # 1. Pre-initial negation (ChiTonga ta-, Luvale ka-, SiLozi ha-, etc.)
    if negative and neg_type == 'pre' and neg_pre:
        parts.append(neg_pre)

    # 2. Subject concord
    parts.append(sc_form)

    # 3. Negation infix (ChiNyanja -sa-)
    if negative and neg_type == 'infix' and neg_infix:
        parts.append(neg_infix)

    # 4. TAM marker (may be empty string for subjunctive)
    """ if marker:
        parts.append(marker) """
    # 4. TAM marker — suppressed in negative forms
    #    Pre-initial neg (ta-): TAM is dropped entirely
    #    Infix neg (-sa-): -sa- occupies the TAM slot
    if marker and not negative:
        parts.append(marker)
    # 5. Verb stem (root with final -a stripped when FV is vowel-initial)
    parts.append(stem)

    # 6. Extensions (VH.1 applied inside _ext_form, conditioned on original root)
    if extensions:
        for ext in extensions:
            parts.append(_ext_form(ext, root, lang))

    # 7. Final vowel
    parts.append(fv)

    # ── Join with boundary rules ──────────────────────────────────────────────
    result = parts[0]
    for seg in parts[1:]:
        result = join_morphemes(result, seg)

    return result


# ── Paradigm builder ──────────────────────────────────────────────────────────

def build_paradigm(
    grammar:   dict,
    root:      str,
    tam_ids:   list[str],
    show_neg:  bool = False,
    show_loc:  bool = False,
    extensions: list[str] = None,
) -> list[dict]:
    """
    Build a complete verb paradigm.

    Returns a list of group dicts, each with structure:
    {
      'label': str,
      'color': str,
      'rows': [
        {
          'id': str,
          'label': str,
          'sublabel': str,
          'forms': {
            'TAM_ID': {'pos': str, 'neg': str | None}
          }
        }
      ]
    }
    """
    lang      = grammar['lang_key']
    neg_type  = grammar.get('neg_type', 'pre')
    neg_pre   = grammar.get('neg_pre', 'ta')
    neg_infix = grammar.get('neg_infix', 'sa')

    # Filter to requested TAM IDs that exist in this grammar
    tam_order    = grammar.get('tam_order', list(grammar['tam'].keys()))
    selected_tam = [tid for tid in tam_order if tid in tam_ids and tid in grammar['tam']]

    groups = grammar['groups']
    if not show_loc:
        groups = [g for g in groups if g['color'] != 'locative']

    result = []
    for group in groups:
        g_rows = []
        for sc_key in group['rows']:
            sc_data = grammar['subject_concords'].get(sc_key)
            if not sc_data:
                continue
            forms: dict[str, dict] = {}
            for tid in selected_tam:
                tam = grammar['tam'][tid]
                pos = conjugate(
                    sc_data, tam, root, False,
                    neg_type, neg_pre, neg_infix, lang, extensions,
                )
                neg_form = None
                if show_neg:
                    neg_form = conjugate(
                        sc_data, tam, root, True,
                        neg_type, neg_pre, neg_infix, lang, extensions,
                    )
                forms[tid] = {'pos': pos, 'neg': neg_form}

            g_rows.append({
                'id':       sc_key,
                'label':    sc_data['label'],
                'sublabel': sc_data.get('sublabel', ''),
                'forms':    forms,
            })

        result.append({
            'label': group['label'],
            'color': group['color'],
            'rows':  g_rows,
        })

    return result


# ── Morpheme-key helper (used by API to drive the poster's diagram) ───────────

def morpheme_key_example(
    grammar:  dict,
    root:     str,
    tam_id:   str,
    sc_key:   str = '3SG',
) -> dict:
    """
    Return a dict describing the morpheme decomposition of one example form,
    for rendering in the poster's morpheme-key bar.
    """
    lang      = grammar['lang_key']
    neg_type  = grammar.get('neg_type', 'pre')
    neg_pre   = grammar.get('neg_pre', 'ta')
    neg_infix = grammar.get('neg_infix', 'sa')

    tam     = grammar['tam'].get(tam_id) or next(iter(grammar['tam'].values()))
    sc_data = grammar['subject_concords'].get(sc_key, {})
    marker  = tam.get('marker', '')
    fv      = tam['fv']

    first_after_sc = marker if marker else root
    sc_form = _select_sc(sc_data, first_after_sc)

    surface = conjugate(sc_data, tam, root, False, neg_type, neg_pre, neg_infix, lang)

    slots = []
    if neg_type == 'pre' and neg_pre:
        slots.append({'label': 'neg. (pre-initial)', 'value': neg_pre + '-', 'dim': True})
    slots.append({'label': 'subj. concord', 'value': sc_form + '-'})
    if neg_type == 'infix' and neg_infix:
        slots.append({'label': 'neg. infix', 'value': '-' + neg_infix + '-', 'dim': True})
    slots.append({'label': 'TAM marker', 'value': marker or '∅'})
    slots.append({'label': 'verb root', 'value': '-' + root + '-', 'brand': True})
    slots.append({'label': 'final vowel', 'value': '-' + fv})

    return {
        'slots':       slots,
        'surface':     surface,
        'tam_label':   tam['label'],
        'sc_label':    sc_data.get('label', sc_key),
        'sc_sublabel': sc_data.get('sublabel', ''),
    }
