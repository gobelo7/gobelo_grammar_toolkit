#!/usr/bin/env python3
"""Align multilingual sentence data from booklet CSVs."""

from pathlib import Path

BOOKLETS_DIR = Path(__file__).parent.parent / 'corpus' / '_parallel' / 'booklets'
ALIGNED_DIR  = Path(__file__).parent.parent / 'corpus' / '_parallel' / 'aligned'

# Alignment keys: story URL + page number
ALIGN_KEYS = ['url', 'page']
LANGUAGES  = ['bem', 'toi', 'nya', 'lue', 'lun', 'kqn', 'loz']

def align():
    # TODO: implement alignment logic
    pass

if __name__ == '__main__':
    align()

