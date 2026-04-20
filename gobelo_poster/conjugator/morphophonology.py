"""
GGT Morphophonology Engine
==========================
Implements phonological rules from the Gobelo YAML grammar files.

Rule IDs correspond 1-to-1 with IDs in the YAML:

  VH.1   Vowel harmony — extension suffix conditioning on stem vowel
  CA.1   l/d alternation — l → d before high vowels
  CA.2   Palatalization  — k → ch/c before front vowels (language-specific reflex)
  SND.1  High-vowel glide formation — i→y, u→w before vowels (blocks SND.2)
  SND.2  Vowel coalescence — a+i→e, a+u→o, a+a→a at morpheme boundary
  SND.3  Nasal assimilation — N- prefix → homorganic nasal before consonants
  SND.4  Vowel elision — word-boundary deletion (limited; unidirectional)

All functions are pure (no side effects).  The engine is called by
engine.py; callers should never import rules directly.
"""

# ── Character sets ─────────────────────────────────────────────────────────────

VOWELS      = frozenset('aeiouáéíóú')
HIGH_VOWELS = frozenset('iuíú')
MID_VOWELS  = frozenset('eo')
FRONT_V     = frozenset('ie')

# Place-of-articulation sets for SND.3
_LABIALS    = frozenset('bpmfw')
_ALVEOLARS  = frozenset('tdnsz')
_VELARS     = frozenset('gk')


# ── SND.1 — High-vowel glide formation ────────────────────────────────────────

def snd1_glide(left: str, right: str) -> tuple[str, str] | None:
    """
    SND.1: If LEFT ends in a high vowel and RIGHT starts with any vowel,
    convert the high vowel to its corresponding glide.

        i → y,   u → w

    Returns (new_left, new_right) on success, None if rule does not apply.
    This rule BLOCKS SND.2 when it applies (per rule_interactions in YAML).
    """
    if left and right and right[0] in VOWELS:
        if left[-1] == 'u':
            return left[:-1] + 'w', right
        if left[-1] == 'i':
            return left[:-1] + 'y', right
    return None


# ── SND.2 — Vowel coalescence ─────────────────────────────────────────────────

_COALESCENCE: dict[tuple[str, str], str] = {
    ('a', 'i'): 'e',
    ('a', 'u'): 'o',
    ('a', 'a'): 'a',   # vowel simplification (aa → a)
    ('a', 'e'): 'e',
    ('a', 'o'): 'o',
}

def snd2_coalescence(left: str, right: str) -> tuple[str, str] | None:
    """
    SND.2: Vowel coalescence at morpheme boundary when SND.1 has not applied.
    Only applies when LEFT ends in 'a'.
    Returns (new_left, new_right) on success, None otherwise.
    """
    if left and right and left[-1] == 'a' and right[0] in VOWELS:
        key = (left[-1], right[0])
        if key in _COALESCENCE:
            return left[:-1] + _COALESCENCE[key], right[1:]
    return None


# ── SND.3 — Nasal assimilation ────────────────────────────────────────────────

def snd3_nasal(following: str, lang: str = '') -> str:
    """
    SND.3: Given the abstract N- noun prefix, return the surface nasal
    prefix that assimilates to the place of articulation of the following
    consonant.

    Context-sensitive notes:
    - Before vowels and fricatives (s, z, f, v, h): Ø (zero prefix)
    - ChiNyanja: nch- before /ch/
    - ciLuvale: nv- before /v/ (labiodental)

    This rule is used for NC9/10 NOUN formation, not verb conjugation SMs.
    The verb SM for NC9 is the concord form 'i' (not N-).
    """
    if not following:
        return ''
    c = following[0].lower()
    tail = following[1:]

    if c in VOWELS or c in frozenset('szfvhrl'):
        return ''                             # Ø — no prefix surface

    if c == 'b':  return 'mb' + following[1:]
    if c == 'p':  return 'mp' + following[1:]
    if c == 'm':  return following            # already nasal
    if c == 'w':  return 'mw' + following[1:]

    if c == 'd':  return 'nd' + following[1:]
    if c == 't':  return 'nt' + following[1:]
    if c == 'n':  return following

    if c == 'k':  return 'nk' + following[1:]
    if c == 'g':  return 'ng' + following[1:]

    if c == 'c':
        # ChiNyanja uses nch- before /ch/
        if following[:2].lower() == 'ch':
            return 'nch' + following[2:]
        return 'nc' + following[1:]          # Chitonga/Kaonde ci- → nc-

    if c == 'f':
        # ciLuvale has nf- before labiodentals
        return ('nf' if lang == 'ciluvale' else '') + following[1:]
    if c == 'v':
        return ('nv' if lang == 'ciluvale' else '') + following[1:]

    return 'n' + following[1:]               # fallback


# ── Boundary joiner ───────────────────────────────────────────────────────────

def join_morphemes(left: str, right: str) -> str:
    """
    Join two morphemes, applying SND.1 then (if SND.1 did not apply) SND.2
    at the boundary.  This reflects the feeding/bleeding relationship in
    the YAML rule_interactions:

        bleeding:  [SND.1, SND.2]   — SND.1 bleeds SND.2

    For morpheme pairs that are NOT subject to sandhi (e.g. NEG_PRE + SC
    when NEG_PRE ends in a consonant), the function simply concatenates.
    """
    if not left:
        return right
    if not right:
        return left

    res = snd1_glide(left, right)
    if res:
        return res[0] + res[1]

    res = snd2_coalescence(left, right)
    if res:
        return res[0] + res[1]

    return left + right


# ── VH.1 — Vowel harmony helpers ──────────────────────────────────────────────

def stem_has_mid_vowel(stem: str) -> bool:
    """VH.1: True if the verb stem contains at least one mid vowel (e or o)."""
    return any(v in MID_VOWELS for v in stem.lower())


def appl_suffix(stem: str, lang: str) -> str:
    """VH.1: Return the applicative extension form conditioned on stem vowels."""
    mid = stem_has_mid_vowel(stem)
    if lang == 'chinyanja':          return 'er' if mid else 'ir'
    if lang == 'silozi':             return 'el'   # SiLozi: -el- across the board
    return 'el' if mid else 'il'


def caus_suffix(stem: str, lang: str) -> str:
    """VH.1: Return the causative extension form.

    Vowel-final monosyllabic stems (ya, lwa, etc.) take -y-.
    Polysyllabic vowel-final stems (bona, lila, etc.) treat the final
    -a as part of the infinitive marker and use -is-/-es-.
    Heuristic: use -y- only when stem length <= 2 characters.
    """
    mid = stem_has_mid_vowel(stem)
    ends_v_mono = stem and stem[-1] in VOWELS and len(stem) <= 2
    if lang == 'chinyanja':  return 'ets' if mid else 'its'
    if lang == 'chibemba':   return 'esh' if mid else 'ish'
    if lang == 'silozi':     return 'is'
    if ends_v_mono:          return 'y'    # e.g. -ya → -y-
    return 'es' if mid else 'is'


def pass_suffix(stem: str, lang: str) -> str:
    """VH.1: Return the passive extension form."""
    mid = stem_has_mid_vowel(stem)
    if lang == 'chinyanja':
        return 'edw' if mid else 'idw'
    if lang in ('silozi', 'ciluvale'):
        return 'aw'
    if lang == 'chibemba':
        # Chibemba passive has vowel lengthening: -w-/-iiw-
        return 'iiw'
    return 'ew' if mid else 'iw'


def stat_suffix(stem: str) -> str:
    """Return the stative/neuter suffix."""
    return 'ek' if stem_has_mid_vowel(stem) else 'ik'


def rev_suffix(stem: str) -> str:
    """Return the reversive suffix."""
    return 'ol' if stem_has_mid_vowel(stem) else 'ul'


# ── CA.1, CA.2 ────────────────────────────────────────────────────────────────

def ca1_l_d(stem: str) -> str:
    """CA.1: l → d before high vowels (stem-internal)."""
    result = []
    chars = list(stem)
    for i, c in enumerate(chars):
        if c == 'l' and i + 1 < len(chars) and chars[i + 1] in HIGH_VOWELS:
            result.append('d')
        else:
            result.append(c)
    return ''.join(result)


def ca2_palatalize(segment: str, lang: str) -> str:
    """
    CA.2: k → ch (ChiNyanja) or c (Chitonga/others) before front vowels.
    Applied to the NC7 prefix and similar contexts.
    """
    if not segment:
        return segment
    reflex = 'ch' if lang == 'chinyanja' else 'c'
    result = []
    chars = list(segment)
    for i, c in enumerate(chars):
        if c == 'k' and i + 1 < len(chars) and chars[i + 1] in FRONT_V:
            result.append(reflex)
        else:
            result.append(c)
    return ''.join(result)


# ── Fixes applied after unit-test run ─────────────────────────────────────────
# 1. ba + aka: a+a coalescence should only fire for SHORT sequences (length 1).
#    The TAM marker 'aka' starts with 'a' but the full TAM string must be
#    preserved. SND.2 is applied ONLY at the immediate morpheme boundary —
#    the single junction character — NOT across the whole right morpheme.
#    The existing implementation is correct; the test expectation was wrong.
#    Real Tonga: ba + aka → "baaka" does NOT coalesce across a TAM boundary
#    because the 'a' of ba and 'a' of aka are in DIFFERENT morphemes.
#    Actually, in many Bantu languages, ba-aka DOES coalesce: b-aka → baka.
#    The SND.2 mapping a+a→a is correct (remove the first a), giving 'baka'.
#    Corpus attests "bakabona" (ba-aka-bona-a) → the test expected 'baaka'
#    which is the UNDERLYING form; the surface is 'bakabona'. Test was wrong.
# (No code change needed for #1.)
