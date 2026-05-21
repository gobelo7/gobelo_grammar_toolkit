# Gobelo Platform

Multilingual NLP infrastructure for Zambian Bantu languages.

## Languages

- **Bemba** (`bem`)
- **Chitonga** (`toi`)
- **Nyanja/Chichewa** (`nya`)
- **Luvale** (`lue`)
- **Lunda** (`lun`)
- **Kaonde** (`kqn`)
- **Tumbuka** (`tum`)

## Structure

| Folder | Purpose |
|--------|----------|
| `apps/` | NLP tools and interfaces |
| `data/corpus/` | Raw, tokenized, and annotated text data |
| `data/lexicon/` | Community dictionary data (SQLite + CSV wordlists) |
| `grammar/` | BGT YAML configs (single source of truth) |
| `scripts/` | Build, validation, and pipeline scripts |

## Dependencies

Morphological analysis and HFST transducers are provided by the **GGT package** (`gobelo-ggt`), maintained as a separate repository.

```bash
pip install gobelo-ggt          # from PyPI (once published)
pip install -e ../ggt           # local dev install
```

## Philosophy

Frugal innovation · Language-agnostic design · YAML as single source of truth
