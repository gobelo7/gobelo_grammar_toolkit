"""
GGT Grammar Data — All 7 Zambian Official Languages
=====================================================
Sourced from the Gobelo YAML grammar files (v1.0 RC).
This module provides the grammar data in a Python-native structure
optimised for conjugation.  When the actual .yaml files are present on
disk the engine.py loader will override these defaults with the full
grammar data.

Language keys match the URL parameter convention:
  chitonga · chibemba · chinyanja · silozi · cikaonde · ciluvale · cilunda
"""

from typing import TypedDict, Optional


# ── Type hints (documentation only) ──────────────────────────────────────────

class SCEntry(TypedDict):
    form: str
    label: str
    sublabel: str
    before_v: Optional[str]   # allomorph used before vowel-initial following segment


class TAMEntry(TypedDict):
    label: str
    marker: str    # empty string = zero marker (subjunctive etc.)
    fv: str        # final vowel for positive
    neg_fv: str    # final vowel for negative


class GroupEntry(TypedDict):
    label: str
    color: str     # 'human' | 'thing' | 'locative'
    rows: list[str]  # list of SC keys


class GrammarEntry(TypedDict):
    name: str
    iso: str
    guthrie: str
    lang_key: str
    neg_type: str           # 'pre' | 'infix'
    neg_pre: str            # pre-initial negation marker
    neg_infix: str          # infix negation marker (ChiNyanja -sa-)
    tam: dict[str, TAMEntry]
    tam_order: list[str]    # canonical display order
    default_tam: list[str]  # pre-selected on load
    subject_concords: dict[str, SCEntry]
    groups: list[GroupEntry]


# ── Shared row groups (reused across similar languages) ───────────────────────

_PERSONAL_ROWS  = ['1SG', '2SG', '3SG', '1PL', '2PL', '3PL']
_LOCATIVE_ROWS  = ['NC16', 'NC17', 'NC18']

_FULL_NC_ROWS   = [
    'NC1', 'NC2', 'NC3', 'NC4', 'NC5', 'NC6',
    'NC7', 'NC8', 'NC9', 'NC10', 'NC11', 'NC12',
    'NC13', 'NC14', 'NC15',
]

_CORE_NC_ROWS   = [
    'NC1', 'NC2', 'NC3', 'NC4',
    'NC7', 'NC8', 'NC9', 'NC10', 'NC14', 'NC15',
]


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  ChiTonga  (M.64)                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

CHITONGA: GrammarEntry = {
    'name': 'ChiTonga', 'iso': 'toi', 'guthrie': 'M.64',
    'lang_key': 'chitonga',
    'neg_type': 'pre', 'neg_pre': 'ta', 'neg_infix': '',
    'tam': {
        'PRES': {'label': 'Present',       'marker': 'a',   'fv': 'a',   'neg_fv': 'i'},
        'PST':  {'label': 'Past',          'marker': 'aka', 'fv': 'a',   'neg_fv': 'i'},
        'RPST': {'label': 'Recent past',   'marker': 'ali', 'fv': 'a',   'neg_fv': 'i'},
        'FUT':  {'label': 'Near future',   'marker': 'yo',  'fv': 'a',   'neg_fv': 'i'},
        'RFUT': {'label': 'Remote future', 'marker': 'za',  'fv': 'a',   'neg_fv': 'i'},
        'HAB':  {'label': 'Habitual',      'marker': 'la',  'fv': 'a',   'neg_fv': 'i'},
        'SUBJ': {'label': 'Subjunctive',   'marker': '',    'fv': 'e',   'neg_fv': 'e'},
        'PERF': {'label': 'Perfect',       'marker': 'a',   'fv': 'ide', 'neg_fv': 'i'},
    },
    'tam_order': ['PRES', 'PST', 'RPST', 'FUT', 'RFUT', 'HAB', 'SUBJ', 'PERF'],
    'default_tam': ['PRES', 'PST', 'FUT', 'PERF'],
    'subject_concords': {
        # Personal
        '1SG': {'form': 'ndi', 'before_v': 'nd', 'label': 'I',          'sublabel': '1SG'},
        '2SG': {'form': 'u',                      'label': 'you (sg)',   'sublabel': '2SG'},
        '3SG': {'form': 'u',                      'label': 'he / she',  'sublabel': '3SG'},
        '1PL': {'form': 'tu',                     'label': 'we (excl)', 'sublabel': '1PL.EXCL'},
        '2PL': {'form': 'mu',                     'label': 'you (pl)',  'sublabel': '2PL'},
        '3PL': {'form': 'ba',                     'label': 'they',      'sublabel': '3PL'},
        # Noun classes
        'NC1':  {'form': 'u',  'label': 'NC1',  'sublabel': 'mu- person sg'},
        'NC2':  {'form': 'ba', 'label': 'NC2',  'sublabel': 'ba- people pl'},
        'NC3':  {'form': 'u',  'label': 'NC3',  'sublabel': 'mu- tree sg'},
        'NC4':  {'form': 'i',  'label': 'NC4',  'sublabel': 'mi- trees pl'},
        'NC5':  {'form': 'li', 'label': 'NC5',  'sublabel': 'li- body part sg'},
        'NC6':  {'form': 'a',  'label': 'NC6',  'sublabel': 'ma- mass / pl'},
        'NC7':  {'form': 'ci', 'label': 'NC7',  'sublabel': 'ci- thing sg'},
        'NC8':  {'form': 'zi', 'label': 'NC8',  'sublabel': 'zi- things pl'},
        'NC9':  {'form': 'i',  'label': 'NC9',  'sublabel': 'N- animal sg'},
        'NC10': {'form': 'zi', 'label': 'NC10', 'sublabel': 'N- animals pl'},
        'NC11': {'form': 'lu', 'label': 'NC11', 'sublabel': 'lu- long object'},
        'NC12': {'form': 'ka', 'label': 'NC12', 'sublabel': 'ka- diminutive sg'},
        'NC13': {'form': 'tu', 'label': 'NC13', 'sublabel': 'tu- diminutives pl'},
        'NC14': {'form': 'bu', 'label': 'NC14', 'sublabel': 'bu- abstract'},
        'NC15': {'form': 'ku', 'label': 'NC15', 'sublabel': 'ku- infinitive'},
        'NC16': {'form': 'pa', 'label': 'NC16', 'sublabel': 'pa- at / on'},
        'NC17': {'form': 'ku', 'label': 'NC17', 'sublabel': 'ku- towards'},
        'NC18': {'form': 'mu', 'label': 'NC18', 'sublabel': 'mu- inside'},
    },
    'groups': [
        {'label': 'Personal pronouns',          'color': 'human',    'rows': _PERSONAL_ROWS},
        {'label': 'Human noun classes',         'color': 'human',    'rows': ['NC1', 'NC2']},
        {'label': 'Plant · tree · body',        'color': 'thing',    'rows': ['NC3', 'NC4']},
        {'label': 'Object · thing · language',  'color': 'thing',
         'rows': ['NC5','NC6','NC7','NC8','NC9','NC10','NC11','NC12','NC13','NC14','NC15']},
        {'label': 'Locative classes',           'color': 'locative', 'rows': _LOCATIVE_ROWS},
    ],
}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  Chibemba  (M.42)                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

CHIBEMBA: GrammarEntry = {
    'name': 'Chibemba', 'iso': 'bem', 'guthrie': 'M.42',
    'lang_key': 'chibemba',
    'neg_type': 'pre', 'neg_pre': 'ta', 'neg_infix': '',
    'tam': {
        'PRES': {'label': 'Present',       'marker': 'a',   'fv': 'a',   'neg_fv': 'i'},
        'PST':  {'label': 'Past',          'marker': 'na',  'fv': 'a',   'neg_fv': 'i'},
        'FUT':  {'label': 'Future',        'marker': 'laa', 'fv': 'a',   'neg_fv': 'i'},
        'HAB':  {'label': 'Habitual',      'marker': 'la',  'fv': 'a',   'neg_fv': 'i'},
        'SUBJ': {'label': 'Subjunctive',   'marker': '',    'fv': 'e',   'neg_fv': 'e'},
        'PERF': {'label': 'Perfect',       'marker': 'a',   'fv': 'ile', 'neg_fv': 'i'},
        'HPST': {'label': 'Hodiernal past','marker': 'ali', 'fv': 'ile', 'neg_fv': 'i'},
        'RPST': {'label': 'Remote past',   'marker': 'ale', 'fv': 'ile', 'neg_fv': 'i'},
    },
    'tam_order': ['PRES', 'PST', 'HPST', 'RPST', 'FUT', 'HAB', 'SUBJ', 'PERF'],
    'default_tam': ['PRES', 'PST', 'FUT', 'PERF'],
    'subject_concords': {
        '1SG': {'form': 'ndi', 'before_v': 'nd', 'label': 'I',         'sublabel': '1SG'},
        '2SG': {'form': 'u',                      'label': 'you (sg)', 'sublabel': '2SG'},
        '3SG': {'form': 'u',                      'label': 'he / she','sublabel': '3SG'},
        '1PL': {'form': 'tu',                     'label': 'we',      'sublabel': '1PL'},
        '2PL': {'form': 'mu',                     'label': 'you (pl)','sublabel': '2PL'},
        '3PL': {'form': 'ba',                     'label': 'they',    'sublabel': '3PL'},
        'NC1':  {'form': 'u',  'label': 'NC1',  'sublabel': 'mu- human sg'},
        'NC2':  {'form': 'ba', 'label': 'NC2',  'sublabel': 'ba- humans pl'},
        'NC3':  {'form': 'u',  'label': 'NC3',  'sublabel': 'mu- tree sg'},
        'NC4':  {'form': 'i',  'label': 'NC4',  'sublabel': 'mi- trees pl'},
        'NC7':  {'form': 'fi', 'label': 'NC7',  'sublabel': 'fi- thing sg'},
        'NC8':  {'form': 'bi', 'label': 'NC8',  'sublabel': 'bi- things pl'},
        'NC9':  {'form': 'i',  'label': 'NC9',  'sublabel': 'N- animal sg'},
        'NC10': {'form': 'zi', 'label': 'NC10', 'sublabel': 'N- animals pl'},
        'NC14': {'form': 'bu', 'label': 'NC14', 'sublabel': 'bu- abstract'},
        'NC15': {'form': 'ku', 'label': 'NC15', 'sublabel': 'ku- infinitive'},
        'NC16': {'form': 'pa', 'label': 'NC16', 'sublabel': 'pa- at / on'},
        'NC17': {'form': 'ku', 'label': 'NC17', 'sublabel': 'ku- towards'},
        'NC18': {'form': 'mu', 'label': 'NC18', 'sublabel': 'mu- inside'},
    },
    'groups': [
        {'label': 'Personal pronouns', 'color': 'human',    'rows': _PERSONAL_ROWS},
        {'label': 'Noun classes',      'color': 'thing',
         'rows': ['NC1','NC2','NC3','NC4','NC7','NC8','NC9','NC10','NC14','NC15']},
        {'label': 'Locative classes',  'color': 'locative', 'rows': _LOCATIVE_ROWS},
    ],
}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  ChiNyanja  (N.31) — Chichewa / Nyanja / Zambia + Malawi                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

CHINYANJA: GrammarEntry = {
    'name': 'ChiNyanja', 'iso': 'nya', 'guthrie': 'N.31',
    'lang_key': 'chinyanja',
    'neg_type': 'infix', 'neg_pre': '', 'neg_infix': 'sa',
    'notes': {
        'negation': '-sa- infix occupies SLOT4; blocks TAM marker',
        'perfect': 'Perfect = H tone on -na- TAM (segmentally identical to PST)',
        'appl': 'Rhotic -ir-/-er- (not lateral -il-/-el-)',
        'caus': 'Affricate -its-/-ets-',
        'pass': '-idw-/-edw-',
        'nc14': 'u- (NOT bu-)',
        'nc2': 'a- (NOT ba-)',
    },
    'tam': {
        'PRES': {'label': 'Present',       'marker': 'ma',  'fv': 'a', 'neg_fv': 'e'},
        'PST':  {'label': 'Past',          'marker': 'na',  'fv': 'a', 'neg_fv': 'a'},
        'FUT':  {'label': 'Future',        'marker': 'dza', 'fv': 'a', 'neg_fv': 'a'},
        'SUBJ': {'label': 'Subjunctive',   'marker': '',    'fv': 'e', 'neg_fv': 'e'},
        'PERF': {'label': 'Perfect (H)',   'marker': 'ná',  'fv': 'a', 'neg_fv': 'a',
                 'note': 'High tone on -ná- distinguishes perfect from past -na-'},
        'PROG': {'label': 'Progressive',   'marker': 'ku',  'fv': 'a', 'neg_fv': 'a',
                 'note': '-ku- + infinitive; a-ku-ona = he is seeing'},
    },
    'tam_order': ['PRES', 'PST', 'PERF', 'FUT', 'SUBJ', 'PROG'],
    'default_tam': ['PRES', 'PST', 'FUT'],
    'subject_concords': {
        '1SG': {'form': 'ndi', 'before_v': 'nd', 'label': 'I',         'sublabel': '1SG'},
        '2SG': {'form': 'u',                      'label': 'you (sg)', 'sublabel': '2SG'},
        '3SG': {'form': 'u',                      'label': 'he / she','sublabel': '3SG'},
        '1PL': {'form': 'ti',                     'label': 'we',      'sublabel': '1PL'},
        '2PL': {'form': 'mu',                     'label': 'you (pl)','sublabel': '2PL'},
        '3PL': {'form': 'a',                      'label': 'they',    'sublabel': '3PL (a-)'},
        'NC1':  {'form': 'u',   'label': 'NC1',  'sublabel': 'mu- human sg'},
        'NC2':  {'form': 'a',   'label': 'NC2',  'sublabel': 'a- humans pl'},
        'NC3':  {'form': 'u',   'label': 'NC3',  'sublabel': 'mu- tree sg'},
        'NC4':  {'form': 'i',   'label': 'NC4',  'sublabel': 'mi- trees pl'},
        'NC7':  {'form': 'chi', 'label': 'NC7',  'sublabel': 'chi- thing sg'},
        'NC8':  {'form': 'zi',  'label': 'NC8',  'sublabel': 'zi- things pl'},
        'NC9':  {'form': 'i',   'label': 'NC9',  'sublabel': 'N- animal sg'},
        'NC10': {'form': 'zi',  'label': 'NC10', 'sublabel': 'N- animals pl'},
        'NC14': {'form': 'u',   'label': 'NC14', 'sublabel': 'u- abstract (not bu-)'},
        'NC15': {'form': 'ku',  'label': 'NC15', 'sublabel': 'ku- infinitive'},
        'NC16': {'form': 'pa',  'label': 'NC16', 'sublabel': 'pa- at / on'},
        'NC17': {'form': 'ku',  'label': 'NC17', 'sublabel': 'ku- towards'},
        'NC18': {'form': 'mu',  'label': 'NC18', 'sublabel': 'mu- inside'},
    },
    'groups': [
        {'label': 'Personal pronouns', 'color': 'human',    'rows': _PERSONAL_ROWS},
        {'label': 'Noun classes',      'color': 'thing',
         'rows': ['NC1','NC2','NC3','NC4','NC7','NC8','NC9','NC10','NC14','NC15']},
        {'label': 'Locative classes',  'color': 'locative', 'rows': _LOCATIVE_ROWS},
    ],
}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SiLozi  (K.21)                                                             ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

SILOZI: GrammarEntry = {
    'name': 'SiLozi', 'iso': 'loz', 'guthrie': 'K.21',
    'lang_key': 'silozi',
    'neg_type': 'pre', 'neg_pre': 'ha', 'neg_infix': '',
    'tam': {
        'PRES': {'label': 'Present',     'marker': 'a',  'fv': 'a',   'neg_fv': 'i'},
        'PST':  {'label': 'Past',        'marker': 'ne', 'fv': 'ile', 'neg_fv': 'ile'},
        'FUT':  {'label': 'Future',      'marker': 'ka', 'fv': 'a',   'neg_fv': 'i'},
        'SUBJ': {'label': 'Subjunctive', 'marker': '',   'fv': 'e',   'neg_fv': 'e'},
        'PERF': {'label': 'Perfect',     'marker': 'a',  'fv': 'ile', 'neg_fv': 'i'},
    },
    'tam_order': ['PRES', 'PST', 'FUT', 'SUBJ', 'PERF'],
    'default_tam': ['PRES', 'PST', 'FUT'],
    'subject_concords': {
        '1SG': {'form': 'ni',  'label': 'I',         'sublabel': '1SG'},
        '2SG': {'form': 'u',   'label': 'you (sg)',  'sublabel': '2SG'},
        '3SG': {'form': 'u',   'label': 'he / she', 'sublabel': '3SG'},
        '1PL': {'form': 'lu',  'label': 'we',        'sublabel': '1PL'},
        '2PL': {'form': 'mu',  'label': 'you (pl)', 'sublabel': '2PL'},
        '3PL': {'form': 'ba',  'label': 'they',      'sublabel': '3PL'},
        'NC1':  {'form': 'u',  'label': 'NC1',  'sublabel': 'mo- human sg'},
        'NC2':  {'form': 'ba', 'label': 'NC2',  'sublabel': 'ba- humans pl'},
        'NC3':  {'form': 'u',  'label': 'NC3',  'sublabel': 'mo- tree sg'},
        'NC4':  {'form': 'i',  'label': 'NC4',  'sublabel': 'mi- trees pl'},
        'NC7':  {'form': 'si', 'label': 'NC7',  'sublabel': 'si- thing sg'},
        'NC8':  {'form': 'li', 'label': 'NC8',  'sublabel': 'li- things pl'},
        'NC9':  {'form': 'i',  'label': 'NC9',  'sublabel': 'N- animal sg'},
        'NC10': {'form': 'li', 'label': 'NC10', 'sublabel': 'N- animals pl'},
        'NC14': {'form': 'bu', 'label': 'NC14', 'sublabel': 'bu- abstract'},
        'NC15': {'form': 'ku', 'label': 'NC15', 'sublabel': 'ku- infinitive'},
        'NC16': {'form': 'fa', 'label': 'NC16', 'sublabel': 'fa- at / on (Sotho fa-)'},
        'NC17': {'form': 'ku', 'label': 'NC17', 'sublabel': 'ku- towards'},
        'NC18': {'form': 'mu', 'label': 'NC18', 'sublabel': 'mu- inside'},
    },
    'groups': [
        {'label': 'Personal pronouns', 'color': 'human',    'rows': _PERSONAL_ROWS},
        {'label': 'Noun classes',      'color': 'thing',
         'rows': ['NC1','NC2','NC3','NC4','NC7','NC8','NC9','NC10','NC14','NC15']},
        {'label': 'Locative classes',  'color': 'locative', 'rows': _LOCATIVE_ROWS},
    ],
}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  ciKaonde  (L.41)                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

CIKAONDE: GrammarEntry = {
    'name': 'ciKaonde', 'iso': 'kqn', 'guthrie': 'L.41',
    'lang_key': 'cikaonde',
    'neg_type': 'pre', 'neg_pre': 'ta', 'neg_infix': '',
    'tam': {
        'PRES': {'label': 'Present',     'marker': 'a',   'fv': 'a',   'neg_fv': 'i'},
        'PST':  {'label': 'Past',        'marker': 'aka', 'fv': 'ile', 'neg_fv': 'i'},
        'FUT':  {'label': 'Future',      'marker': 'yo',  'fv': 'a',   'neg_fv': 'i'},
        'HAB':  {'label': 'Habitual',    'marker': 'la',  'fv': 'a',   'neg_fv': 'i'},
        'SUBJ': {'label': 'Subjunctive', 'marker': '',    'fv': 'e',   'neg_fv': 'e'},
        'PERF': {'label': 'Perfect',     'marker': 'a',   'fv': 'ile', 'neg_fv': 'i'},
    },
    'tam_order': ['PRES', 'PST', 'FUT', 'HAB', 'SUBJ', 'PERF'],
    'default_tam': ['PRES', 'PST', 'FUT'],
    'subject_concords': {
        '1SG': {'form': 'ndi', 'before_v': 'nd', 'label': 'I',         'sublabel': '1SG'},
        '2SG': {'form': 'u',                      'label': 'you (sg)', 'sublabel': '2SG'},
        '3SG': {'form': 'u',                      'label': 'he / she','sublabel': '3SG'},
        '1PL': {'form': 'tu',                     'label': 'we',      'sublabel': '1PL'},
        '2PL': {'form': 'mu',                     'label': 'you (pl)','sublabel': '2PL'},
        '3PL': {'form': 'ba',                     'label': 'they',    'sublabel': '3PL'},
        'NC1':  {'form': 'u',  'label': 'NC1',  'sublabel': 'mu- human sg'},
        'NC2':  {'form': 'ba', 'label': 'NC2',  'sublabel': 'ba- humans pl'},
        'NC3':  {'form': 'u',  'label': 'NC3',  'sublabel': 'mu- tree sg'},
        'NC4':  {'form': 'i',  'label': 'NC4',  'sublabel': 'mi- trees pl'},
        'NC7':  {'form': 'ci', 'label': 'NC7',  'sublabel': 'ci- thing sg'},
        'NC8':  {'form': 'bi', 'label': 'NC8',  'sublabel': 'bi- things pl'},
        'NC9':  {'form': 'i',  'label': 'NC9',  'sublabel': 'N- animal sg'},
        'NC10': {'form': 'bi', 'label': 'NC10', 'sublabel': 'N- animals pl'},
        'NC14': {'form': 'bu', 'label': 'NC14', 'sublabel': 'bu- abstract'},
        'NC15': {'form': 'ku', 'label': 'NC15', 'sublabel': 'ku- infinitive'},
        'NC16': {'form': 'pa', 'label': 'NC16', 'sublabel': 'pa- at / on'},
        'NC17': {'form': 'ku', 'label': 'NC17', 'sublabel': 'ku- towards'},
        'NC18': {'form': 'mu', 'label': 'NC18', 'sublabel': 'mu- inside'},
    },
    'groups': [
        {'label': 'Personal pronouns', 'color': 'human',    'rows': _PERSONAL_ROWS},
        {'label': 'Noun classes',      'color': 'thing',
         'rows': ['NC1','NC2','NC3','NC4','NC7','NC8','NC9','NC10','NC14','NC15']},
        {'label': 'Locative classes',  'color': 'locative', 'rows': _LOCATIVE_ROWS},
    ],
}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  ciLuvale  (K.14)                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

CILUVALE: GrammarEntry = {
    'name': 'ciLuvale', 'iso': 'lue', 'guthrie': 'K.14',
    'lang_key': 'ciluvale',
    'neg_type': 'pre', 'neg_pre': 'ka', 'neg_infix': '',
    'tam': {
        'PRES': {'label': 'Present',     'marker': 'a',   'fv': 'a',   'neg_fv': 'i'},
        'PST':  {'label': 'Past',        'marker': 'aka', 'fv': 'ile', 'neg_fv': 'i'},
        'FUT':  {'label': 'Future',      'marker': 'yo',  'fv': 'a',   'neg_fv': 'i'},
        'SUBJ': {'label': 'Subjunctive', 'marker': '',    'fv': 'e',   'neg_fv': 'e'},
        'PERF': {'label': 'Perfect',     'marker': 'a',   'fv': 'ile', 'neg_fv': 'i'},
    },
    'tam_order': ['PRES', 'PST', 'FUT', 'SUBJ', 'PERF'],
    'default_tam': ['PRES', 'PST', 'FUT'],
    'subject_concords': {
        '1SG': {'form': 'ndi', 'before_v': 'nd', 'label': 'I',         'sublabel': '1SG'},
        '2SG': {'form': 'u',                      'label': 'you (sg)', 'sublabel': '2SG'},
        '3SG': {'form': 'u',                      'label': 'he / she','sublabel': '3SG'},
        '1PL': {'form': 'tu',                     'label': 'we',      'sublabel': '1PL'},
        '2PL': {'form': 'mu',                     'label': 'you (pl)','sublabel': '2PL'},
        '3PL': {'form': 'a',                      'label': 'they',    'sublabel': '3PL (a-)'},
        'NC1':  {'form': 'u',   'label': 'NC1',  'sublabel': 'mu- human sg'},
        'NC2':  {'form': 'a',   'label': 'NC2',  'sublabel': 'a- humans pl'},
        'NC3':  {'form': 'u',   'label': 'NC3',  'sublabel': 'mu- tree sg'},
        'NC4':  {'form': 'i',   'label': 'NC4',  'sublabel': 'mi- trees pl'},
        'NC7':  {'form': 'chi', 'label': 'NC7',  'sublabel': 'chi- thing sg'},
        'NC8':  {'form': 'vi',  'label': 'NC8',  'sublabel': 'vi- things pl (Zone K)'},
        'NC9':  {'form': 'i',   'label': 'NC9',  'sublabel': 'N- animal sg'},
        'NC10': {'form': 'zi',  'label': 'NC10', 'sublabel': 'N- animals pl'},
        'NC14': {'form': 'bu',  'label': 'NC14', 'sublabel': 'bu- abstract'},
        'NC15': {'form': 'ku',  'label': 'NC15', 'sublabel': 'ku- infinitive'},
        'NC16': {'form': 'pa',  'label': 'NC16', 'sublabel': 'pa- at / on'},
        'NC17': {'form': 'ku',  'label': 'NC17', 'sublabel': 'ku- towards'},
        'NC18': {'form': 'mu',  'label': 'NC18', 'sublabel': 'mu- inside'},
    },
    'groups': [
        {'label': 'Personal pronouns', 'color': 'human',    'rows': _PERSONAL_ROWS},
        {'label': 'Noun classes',      'color': 'thing',
         'rows': ['NC1','NC2','NC3','NC4','NC7','NC8','NC9','NC10','NC14','NC15']},
        {'label': 'Locative classes',  'color': 'locative', 'rows': _LOCATIVE_ROWS},
    ],
}


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  ciLunda  (L.52)                                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

CILUNDA: GrammarEntry = {
    'name': 'ciLunda', 'iso': 'lun', 'guthrie': 'L.52',
    'lang_key': 'cilunda',
    'neg_type': 'pre', 'neg_pre': 'ta', 'neg_infix': '',
    'tam': {
        'PRES': {'label': 'Present',     'marker': 'a',   'fv': 'a',   'neg_fv': 'i'},
        'PST':  {'label': 'Past',        'marker': 'aka', 'fv': 'ile', 'neg_fv': 'i'},
        'FUT':  {'label': 'Future',      'marker': 'yo',  'fv': 'a',   'neg_fv': 'i'},
        'SUBJ': {'label': 'Subjunctive', 'marker': '',    'fv': 'e',   'neg_fv': 'e'},
        'PERF': {'label': 'Perfect',     'marker': 'a',   'fv': 'ile', 'neg_fv': 'i'},
    },
    'tam_order': ['PRES', 'PST', 'FUT', 'SUBJ', 'PERF'],
    'default_tam': ['PRES', 'PST', 'FUT'],
    'subject_concords': {
        '1SG': {'form': 'ndi', 'before_v': 'nd', 'label': 'I',         'sublabel': '1SG'},
        '2SG': {'form': 'u',                      'label': 'you (sg)', 'sublabel': '2SG'},
        '3SG': {'form': 'u',                      'label': 'he / she','sublabel': '3SG'},
        '1PL': {'form': 'tu',                     'label': 'we',      'sublabel': '1PL'},
        '2PL': {'form': 'mu',                     'label': 'you (pl)','sublabel': '2PL'},
        '3PL': {'form': 'a',                      'label': 'they',    'sublabel': '3PL (a-)'},
        'NC1':  {'form': 'u',  'label': 'NC1',  'sublabel': 'mu- human sg'},
        'NC2':  {'form': 'a',  'label': 'NC2',  'sublabel': 'a- humans pl'},
        'NC3':  {'form': 'u',  'label': 'NC3',  'sublabel': 'mu- tree sg'},
        'NC4':  {'form': 'i',  'label': 'NC4',  'sublabel': 'mi- trees pl'},
        'NC7':  {'form': 'ci', 'label': 'NC7',  'sublabel': 'ci- thing sg'},
        'NC8':  {'form': 'i',  'label': 'NC8',  'sublabel': 'i- things pl (L.52 unique)'},
        'NC9':  {'form': 'i',  'label': 'NC9',  'sublabel': 'N- animal sg'},
        'NC10': {'form': 'zi', 'label': 'NC10', 'sublabel': 'N- animals pl'},
        'NC14': {'form': 'bu', 'label': 'NC14', 'sublabel': 'bu- abstract'},
        'NC15': {'form': 'ku', 'label': 'NC15', 'sublabel': 'ku- infinitive'},
        'NC16': {'form': 'pa', 'label': 'NC16', 'sublabel': 'pa- at / on'},
        'NC17': {'form': 'ku', 'label': 'NC17', 'sublabel': 'ku- towards'},
        'NC18': {'form': 'mu', 'label': 'NC18', 'sublabel': 'mu- inside'},
    },
    'groups': [
        {'label': 'Personal pronouns', 'color': 'human',    'rows': _PERSONAL_ROWS},
        {'label': 'Noun classes',      'color': 'thing',
         'rows': ['NC1','NC2','NC3','NC4','NC7','NC8','NC9','NC10','NC14','NC15']},
        {'label': 'Locative classes',  'color': 'locative', 'rows': _LOCATIVE_ROWS},
    ],
}


# ── Registry ───────────────────────────────────────────────────────────────────

GRAMMARS: dict[str, GrammarEntry] = {
    'chitonga':  CHITONGA,
    'chibemba':  CHIBEMBA,
    'chinyanja': CHINYANJA,
    'silozi':    SILOZI,
    'cikaonde':  CIKAONDE,
    'ciluvale':  CILUVALE,
    'cilunda':   CILUNDA,
}
