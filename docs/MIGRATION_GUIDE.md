# Migration Guide

This guide helps you migrate between major versions of the Gobelo Grammar Toolkit.

## Table of Contents
- [Upgrading to v1.0](#upgrading-to-v10)
- [Breaking Changes](#breaking-changes)
- [Deprecations](#deprecations)
- [New Features](#new-features)
- [Migration Examples](#migration-examples)

---

## Upgrading to v1.0

Version 1.0 introduces several improvements to the API and internal architecture. Most changes are backward-compatible, but some breaking changes require attention.

### Installation

```bash
# Upgrade to latest version
pip install --upgrade ggtk

# Or install from source
git clone https://github.com/gobelo/gobelo-grammar-toolkit.git
cd gobelo-grammar-toolkit
pip install -e .
```

---

## Breaking Changes

### 1. Language Codes Now Use ISO 639-3

**Before (v0.x):**
```python
loader = GobeloGrammarLoader(GrammarConfig(language="chitonga"))
```

**After (v1.0):**
```python
loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
```

**Migration:**
Use the language registry to resolve display names to ISO codes:
```python
from ggtk import resolve_language

# This still works - resolves "chitonga" to "toi"
iso_code = resolve_language("chitonga")  # Returns "toi"
loader = GobeloGrammarLoader(GrammarConfig(language=iso_code))
```

**Supported ISO codes:**
- `toi` - chiTonga
- `bem` - chiBemba
- `nya` - chiNyanja
- `loz` - siLozi
- `lue` - Luvale
- `lun` - Lunda
- `kqn` - Kaonde

### 2. Concord Access Methods Changed

**Before (v0.x):**
```python
# Direct access to concord dict
concords = loader.get_concords("subject")
```

**After (v1.0):**
```python
# Use specific method or full concord type name
sc = loader.get_subject_concords()
# OR
cs = loader.get_concords("subject_concords")
```

**Migration:**
```python
# Old way (still works with fuzzy matching in CLI)
loader.get_concords("subject")

# New recommended ways
loader.get_subject_concords()  # Convenience method
loader.get_object_concords()   # Convenience method
loader.get_concords("subject_concords")  # Full name
loader.get_concords("possessive_concords")  # Other types
```

### 3. Removed Direct Grammar Access

**Before (v0.x):**
```python
# Direct access to raw grammar dict
grammar = loader.grammar
noun_classes = grammar['noun_classes']
```

**After (v1.0):**
```python
# Use typed getter methods
noun_classes = loader.get_noun_classes()
metadata = loader.get_metadata()
```

**Reason:** This change enforces type safety and prevents accidental mutation of internal state.

**Migration:**
Replace all direct dictionary access with appropriate getter methods:
- `loader.grammar['noun_classes']` → `loader.get_noun_classes()`
- `loader.grammar['metadata']` → `loader.get_metadata()`
- `loader.grammar['verb_system']` → `loader.get_verb_template()`

---

## Deprecations

The following features are deprecated in v1.0 and will be removed in v2.0:

### 1. Legacy YAML Format Support

Grammars using the old `{lang}_grammar:` wrapper format still work but should be migrated to the canonical flat format.

**Old format:**
```yaml
chitonga_grammar:
  metadata:
    language: chitonga
  noun_classes:
    ...
```

**New format:**
```yaml
metadata:
  language: toi
  iso_code: toi
noun_classes:
  ...
```

### 2. String-Based Morpheme Representations

Internal morpheme representations now use structured `MorphNode` objects instead of concatenated strings. The public API remains the same, but custom extensions may need updates.

---

## New Features

### 1. Web API

A RESTful Flask API is now available:

```bash
cd web/backend
pip install -r requirements.txt
python app.py
```

**Example usage:**
```bash
curl http://localhost:5000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"token": "balya", "language": "toi"}'
```

See `web/backend/README.md` for full API documentation.

### 2. Enhanced Error Handling

All exceptions now include structured context and helpful suggestions:

```python
try:
    result = analyzer.analyze("invalid_token")
except MorphologicalAnalysisError as e:
    print(e.context)      # {'token': 'invalid_token', 'language': 'toi'}
    print(e.suggestion)   # Helpful migration advice
    print(e.error_code)   # 'ANALYSIS_ERROR'
```

### 3. Batch Processing

Analyze multiple tokens efficiently:

```python
# Method 1: Using segment_text for sentences
results = analyzer.segment_text("Balya muntu cilya.")

# Method 2: Web API batch endpoint
POST /api/v1/analyze/batch
{
  "tokens": ["balya", "muntu", "cilya"],
  "language": "toi"
}
```

### 4. Caching

Loaders and analyzers are now cached automatically in the web API, reducing initialization overhead for repeated requests.

### 5. Improved Documentation

- Complete API reference in `docs/API_REFERENCE.md`
- Cookbook examples in `docs/cookbook/`
- Migration guide (this document)

---

## Migration Examples

### Example 1: Basic Loader Usage

**Before:**
```python
from ggtk.core.loader import GobeloGrammarLoader

loader = GobeloGrammarLoader("chitonga")
meta = loader.grammar['metadata']
print(meta['language'])
```

**After:**
```python
from ggtk import GobeloGrammarLoader, GrammarConfig

loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
meta = loader.get_metadata()
print(meta.language)
```

### Example 2: Morphological Analysis

**Before:**
```python
from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer

analyzer = MorphologicalAnalyzer(loader)
result = analyzer.analyze("balya")
print(result.segmented)  # May not exist in old version
```

**After:**
```python
from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer

analyzer = MorphologicalAnalyzer(loader)
result = analyzer.analyze("balya")
print(result.best.segmented)  # ba-ly-a
print(result.best.gloss_line)  # NC2.SUBJ-eat-FV
print(result.best.confidence)  # 0.95
```

### Example 3: Error Handling

**Before:**
```python
try:
    result = analyzer.analyze("")
except Exception as e:
    print(f"Error: {e}")
```

**After:**
```python
from ggtk.core.exceptions_enhanced import MorphologicalAnalysisError

try:
    result = analyzer.analyze("")
except MorphologicalAnalysisError as e:
    print(f"Error: {e.message}")
    print(f"Context: {e.context}")
    print(f"Suggestion: {e.suggestion}")
```

### Example 4: Web API Integration

**New in v1.0:**
```python
import requests

response = requests.post(
    'http://localhost:5000/api/v1/analyze',
    json={'token': 'balya', 'language': 'toi'}
)

if response.status_code == 200:
    data = response.json()
    print(data['best_analysis']['segmented'])
```

---

## Troubleshooting

### Issue: "LanguageNotFoundError: language='chitonga'"

**Solution:** Use ISO 639-3 code or resolve the name:
```python
from ggtk import resolve_language
iso = resolve_language("chitonga")  # Returns "toi"
loader = GobeloGrammarLoader(GrammarConfig(language=iso))
```

### Issue: "AttributeError: 'GobeloGrammarLoader' object has no attribute 'grammar'"

**Solution:** Use getter methods instead:
```python
# Wrong
data = loader.grammar

# Correct
metadata = loader.get_metadata()
noun_classes = loader.get_noun_classes()
```

### Issue: "ConcordTypeNotFoundError"

**Solution:** Use full concord type names:
```python
# Check available types
types = loader.get_all_concord_types()
print(types)  # ['subject_concords', 'object_concords', ...]

# Use exact name
cs = loader.get_concords("subject_concords")
```

---

## Getting Help

- **Documentation:** https://gobelo.github.io/ggtk
- **Issues:** https://github.com/gobelo/gobelo-grammar-toolkit/issues
- **Email:** beenzu7@gmail.com

---

## Version Compatibility Matrix

| Feature | v0.x | v1.0 | v2.0 (planned) |
|---------|------|------|----------------|
| Language codes | Display names | ISO 639-3 | ISO 639-3 |
| Grammar access | Direct dict | Typed getters | Typed getters |
| Error handling | Basic | Enhanced | Enhanced + retry |
| Web API | None | Flask REST | FastAPI + WebSocket |
| Caching | None | LRU cache | Distributed cache |
| Batch processing | No | Yes | Async batch |

---

*Last updated: June 2026*
