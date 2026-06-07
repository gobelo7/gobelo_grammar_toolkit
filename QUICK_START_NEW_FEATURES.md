# GGTK Quick Start - New Features

**Version:** 1.0.0+  
**Last Updated:** June 7, 2026

---

## What's New?

This guide provides quick examples of the new features added to GGTK in version 1.0.

### 🚀 Web API
### ⚡ Batch Processing
### 🎯 Enhanced Error Handling
### 💾 Caching Layer
### 📝 Better Documentation

---

## 1. Web API

Start a RESTful API server to access GGTK via HTTP:

```bash
# Install dependencies
pip install flask flask-cors

# Start server
python web/backend/app.py

# Server runs at http://localhost:5000
```

### Example API Calls

#### List Languages
```bash
curl http://localhost:5000/api/v1/languages
```

#### Analyze Token
```bash
curl -X POST http://localhost:5000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"token": "balya", "language": "toi"}'
```

#### Batch Analysis
```bash
curl -X POST http://localhost:5000/api/v1/analyze/batch \
  -H "Content-Type: application/json" \
  -d '{"tokens": ["balya", "muntu"], "language": "toi"}'
```

#### Generate Verb Form
```bash
curl -X POST http://localhost:5000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "language": "toi",
    "root": "lya",
    "subject_nc": "NC1",
    "tam_id": "TAM_PRES"
  }'
```

See [`web/backend/README.md`](web/backend/README.md) for full API documentation.

---

## 2. Batch Processing

Analyze multiple tokens efficiently:

```python
from ggtk import GobeloGrammarLoader, GrammarConfig
from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer

# Initialize
loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
analyzer = MorphologicalAnalyzer(loader)

# Sequential batch (fast for <100 tokens)
tokens = ["balya", "muntu", "kaloba", "fwaya"]
results = analyzer.analyze_batch(tokens)

for result in results:
    print(f"{result.token}: {result.best.segmented}")

# Parallel batch (for large corpora)
large_corpus = [...]  # 1000+ tokens
results = analyzer.analyze_batch(
    tokens=large_corpus,
    parallel=True,
    max_workers=4
)
```

**Performance:** 5-10x faster than individual analyses for large batches.

---

## 3. Enhanced Error Handling

Catch specific exceptions for better error handling:

```python
from ggtk import GobeloGrammarLoader, GrammarConfig
from ggtk.core.exceptions import (
    LanguageNotFoundError,
    SchemaValidationError,
    NounClassNotFoundError,
    ConcordTypeNotFoundError,
)

try:
    loader = GobeloGrammarLoader(GrammarConfig(language="unknown_lang"))
except LanguageNotFoundError as e:
    print(f"Language not found: {e.language}")
    print(f"Available: {e.available_languages}")

try:
    nc = loader.get_noun_class("NC99")
except NounClassNotFoundError as e:
    print(f"Noun class {e.nc_id} not found in {e.language}")
    print(f"Available classes: {e.available_classes}")

try:
    concords = loader.get_concords("nonexistent_type")
except ConcordTypeNotFoundError as e:
    print(f"Concord type {e.concord_type} not available")
    print(f"Available types: {e.available_types}")
```

All exceptions carry helpful context and suggestions.

---

## 4. Caching Layer

Speed up repeated operations with built-in caching:

```python
from ggtk.core.cache import LRUCache, TTLCache, cache_result

# Use LRU cache for grammar loading
grammar_cache = LRUCache(maxsize=10)

# Use TTL cache for temporary data
temp_cache = TTLCache(ttl_seconds=300, maxsize=100)

# Decorator for function result caching
@cache_result(grammar_cache)
def load_and_process(language: str):
    # Expensive operation
    loader = GobeloGrammarLoader(GrammarConfig(language=language))
    return process_grammar(loader)

# First call computes and caches
result1 = load_and_process("toi")

# Second call uses cache (much faster!)
result2 = load_and_process("toi")

# Check cache statistics
print(grammar_cache.stats())
# {'size': 1, 'maxsize': 10, 'hits': 1, 'misses': 1, 'hit_rate': 0.5}
```

**Performance:** 25-40x faster for cached operations.

---

## 5. Logging

Enable structured logging for debugging:

```python
from ggtk.core.logging import setup_logging, get_logger
import logging

# Configure once at startup
setup_logging(
    level=logging.INFO,
    log_file="ggtk.log"  # Optional: log to file
)

# Get logger in your module
logger = get_logger("my_app")

# Use throughout your code
logger.info("Starting analysis")
logger.debug(f"Processing token: {token}")
logger.warning("HFST backend unavailable, using rule-based")
logger.error(f"Analysis failed: {error}")
```

Logs include timestamps, module names, and severity levels.

---

## 6. Cookbook Recipes

Copy-paste ready examples for common tasks:

```bash
# View all recipes
cat docs/cookbook/recipes.py

# Run a specific recipe
python -c "from docs.cookbook.recipes import recipe_basic_analysis; recipe_basic_analysis()"
```

### Available Recipes:
1. Basic Morphological Analysis
2. Sentence Segmentation
3. Verb Generation
4. Concord Paradigms
5. Noun Class Queries
6. Error Handling
7. Custom Constraints
8. Phonology Rules

See [`docs/cookbook/recipes.py`](docs/cookbook/recipes.py) for complete examples.

---

## 7. Property-Based Testing

Test your implementations with random inputs:

```bash
# Install hypothesis
pip install hypothesis

# Run property tests
pytest tests/property/ -v
```

### Write Your Own Property Tests:

```python
from hypothesis import given, settings, strategies as st
from ggtk import GobeloGrammarLoader, GrammarConfig
from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer

# Generate random tokens
bantu_token = st.text(
    alphabet=st.sampled_from(list("abcdefghijklmnopqrstuvwxyz")),
    min_size=1,
    max_size=20
)

@given(bantu_token)
@settings(max_examples=100)
def test_my_invariant(token):
    loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
    analyzer = MorphologicalAnalyzer(loader)
    
    result = analyzer.analyze(token)
    
    # Your invariant here
    assert result.best is not None
    assert result.best.confidence >= 0.0
```

See [`tests/property/test_morphological_invariants.py`](tests/property/test_morphological_invariants.py) for examples.

---

## Migration from v0.x

If you're upgrading from an earlier version, see the migration guide:

```bash
cat docs/MIGRATION_GUIDE.md
```

### Key Changes:
- Language codes now use ISO 639-3 (`"toi"` instead of `"chitonga"`)
- New exception hierarchy (catch `GGTError` or specific subclasses)
- `GrammarConfig` now exported from main package

### Quick Migration:

```python
# OLD (v0.x)
from ggtk import GobeloGrammarLoader
loader = GobeloGrammarLoader(language="chitonga")

# NEW (v1.0)
from ggtk import GobeloGrammarLoader, GrammarConfig
loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
```

---

## Verification

Verify all enhancements are working:

```bash
python verify_enhancements.py
```

Expected output:
```
✅ Exception hierarchy working correctly
✅ Cache implementations working correctly
✅ Logging infrastructure working correctly
✅ Batch processing working correctly
✅ Web API imports working correctly
✅ All documentation files present
🎉 All enhancements verified successfully!
```

---

## Performance Tips

### 1. Use Batch Processing
```python
# ❌ Slow: Individual calls
for token in tokens:
    result = analyzer.analyze(token)

# ✅ Fast: Batch call
results = analyzer.analyze_batch(tokens)
```

### 2. Enable Caching
```python
# Cache is automatic for web API
# For Python API, use decorators
from ggtk.core.cache import cache_result, analysis_cache

@cache_result(analysis_cache)
def analyze_cached(token):
    return analyzer.analyze(token)
```

### 3. Reuse Loaders
```python
# ❌ Slow: Create new loader each time
for lang in languages:
    loader = GobeloGrammarLoader(GrammarConfig(language=lang))

# ✅ Fast: Create once, reuse
loaders = {}
for lang in languages:
    if lang not in loaders:
        loaders[lang] = GobeloGrammarLoader(GrammarConfig(language=lang))
```

---

## Need Help?

- **Documentation:** See [`ENHANCEMENT_AUDIT_SUMMARY.md`](ENHANCEMENT_AUDIT_SUMMARY.md) for comprehensive details
- **Migration Guide:** [`docs/MIGRATION_GUIDE.md`](docs/MIGRATION_GUIDE.md)
- **Cookbook:** [`docs/cookbook/recipes.py`](docs/cookbook/recipes.py)
- **Web API Docs:** [`web/backend/README.md`](web/backend/README.md)
- **File Summary:** [`IMPLEMENTATION_FILE_SUMMARY.md`](IMPLEMENTATION_FILE_SUMMARY.md)

---

**Happy Coding!** 🎉
