#!/usr/bin/env python3
"""Validate all BGT YAML grammar configs."""

from pathlib import Path

GRAMMAR_DIR = Path(__file__).parent.parent / 'grammar'

def validate(path: Path) -> bool:
    import yaml
    with open(path) as fh:
        data = yaml.safe_load(fh)
    required = {'metadata'}
    missing = required - data.keys()
    if missing:
        print(f'  FAIL {path.name}: missing keys {missing}')
        return False
    print(f'  OK   {path.name}')
    return True

if __name__ == '__main__':
    files = sorted(GRAMMAR_DIR.glob('*.yaml'))
    results = [validate(f) for f in files]
    passed = sum(results)
    print(f'\n{passed}/{len(results)} configs valid.')

