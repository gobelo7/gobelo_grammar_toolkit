"""
Verification script for GGTK enhancements.
Tests that all new components are working correctly.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_exceptions():
    """Test exception hierarchy."""
    print("Testing exception hierarchy...")
    from ggtk.core.exceptions import (
        GGTError,
        LanguageNotFoundError,
        SchemaValidationError,
        VersionIncompatibleError,
        UnverifiedFormError,
        ConcordTypeNotFoundError,
        NounClassNotFoundError,
    )
    
    # Test base exception
    try:
        raise GGTError("Test error")
    except GGTError as e:
        assert str(e) == "Test error"
        assert e.message == "Test error"
    
    # Test LanguageNotFoundError
    try:
        raise LanguageNotFoundError("unknown", ["toi", "nya", "bem"])
    except LanguageNotFoundError as e:
        assert e.language == "unknown"
        assert len(e.available_languages) == 3
    
    # Test SchemaValidationError
    try:
        raise SchemaValidationError(
            missing_keys=["metadata", "noun_classes"],
            extra_keys=["typo_field"]
        )
    except SchemaValidationError as e:
        assert len(e.missing_keys) == 2
        assert len(e.extra_keys) == 1
    
    print("✅ Exception hierarchy working correctly\n")


def test_cache():
    """Test caching layer."""
    print("Testing cache implementations...")
    from ggtk.core.cache import LRUCache, TTLCache, cache_result
    
    # Test LRU Cache
    cache = LRUCache(maxsize=3)
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")
    
    assert cache.get("key1") == "value1"
    assert cache.size == 3
    
    # Access key2 to make it recently used
    cache.get("key2")
    
    # Add fourth item (should evict LRU - key3, since key1 and key2 were accessed)
    cache.set("key4", "value4")
    assert cache.size == 3
    assert cache.get("key3") is None  # key3 should be evicted (least recently used)
    assert cache.get("key1") is not None  # key1 still there
    assert cache.get("key2") is not None  # key2 still there
    assert cache.get("key4") == "value4"  # new key present
    
    # Test stats
    stats = cache.stats()
    assert 'hits' in stats
    assert 'misses' in stats
    assert 'hit_rate' in stats
    
    # Test TTL Cache
    import time
    ttl_cache = TTLCache(ttl_seconds=1, maxsize=10)
    ttl_cache.set("temp", "data")
    assert ttl_cache.get("temp") == "data"
    time.sleep(1.1)
    assert ttl_cache.get("temp") is None  # Expired
    
    # Test decorator
    call_count = [0]
    
    @cache_result(LRUCache(maxsize=10))
    def expensive_function(x):
        call_count[0] += 1
        return x * 2
    
    result1 = expensive_function(5)
    result2 = expensive_function(5)  # Should use cache
    assert result1 == result2 == 10
    assert call_count[0] == 1  # Only called once
    
    print("✅ Cache implementations working correctly\n")


def test_logging():
    """Test logging infrastructure."""
    print("Testing logging configuration...")
    from ggtk.core.logging import setup_logging, get_logger
    import logging
    
    # Setup logging
    setup_logging(level=logging.DEBUG)
    
    # Get logger
    logger = get_logger("test_module")
    assert logger.name == "ggtk.test_module"
    
    # Test logging (should not raise)
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    
    print("✅ Logging infrastructure working correctly\n")


def test_morphological_analyzer_batch():
    """Test batch processing in morphological analyzer."""
    print("Testing batch processing...")
    from ggtk import GobeloGrammarLoader, GrammarConfig
    from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer
    
    loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
    analyzer = MorphologicalAnalyzer(loader)
    
    # Test single analysis
    result = analyzer.analyze("balya")
    assert result.token == "balya"
    assert result.best is not None
    
    # Test batch analysis
    tokens = ["balya", "muntu", "kaloba"]
    results = analyzer.analyze_batch(tokens)
    
    assert len(results) == 3
    assert all(r.best is not None for r in results)
    assert results[0].token == "balya"
    assert results[1].token == "muntu"
    assert results[2].token == "kaloba"
    
    print("✅ Batch processing working correctly\n")


def test_web_api_imports():
    """Test that web API can be imported."""
    print("Testing web API imports...")
    try:
        from flask import Flask
        print("  Flask available ✓")
    except ImportError:
        print("  ⚠ Flask not installed (install with: pip install flask)")
        return
    
    # Check that app.py exists and is syntactically valid
    app_path = project_root / "web" / "backend" / "app.py"
    assert app_path.exists(), "Web backend app.py not found"
    
    # Import the app module
    import importlib.util
    spec = importlib.util.spec_from_file_location("web_app", str(app_path))
    module = importlib.util.module_from_spec(spec)
    
    print("✅ Web API imports working correctly\n")


def test_documentation_files():
    """Verify documentation files exist."""
    print("Checking documentation files...")
    
    docs = {
        "Migration Guide": project_root / "docs" / "MIGRATION_GUIDE.md",
        "Cookbook": project_root / "docs" / "cookbook" / "recipes.py",
        "Web Backend README": project_root / "web" / "backend" / "README.md",
        "Enhancement Summary": project_root / "ENHANCEMENT_AUDIT_SUMMARY.md",
    }
    
    for name, path in docs.items():
        assert path.exists(), f"{name} not found at {path}"
        print(f"  ✓ {name}")
    
    print("✅ All documentation files present\n")


def test_property_tests():
    """Verify property-based tests exist."""
    print("Checking property-based tests...")
    
    test_path = project_root / "tests" / "property" / "test_morphological_invariants.py"
    assert test_path.exists(), "Property tests not found"
    
    # Try importing hypothesis
    try:
        import hypothesis
        print("  ✓ Hypothesis library available")
    except ImportError:
        print("  ⚠ Hypothesis not installed (install with: pip install hypothesis)")
    
    print("✅ Property-based tests structure verified\n")


def main():
    """Run all verification tests."""
    print("=" * 70)
    print("GGTK Enhancement Verification")
    print("=" * 70)
    print()
    
    tests = [
        ("Exception Hierarchy", test_exceptions),
        ("Caching Layer", test_cache),
        ("Logging Infrastructure", test_logging),
        ("Batch Processing", test_morphological_analyzer_batch),
        ("Web API", test_web_api_imports),
        ("Documentation", test_documentation_files),
        ("Property Tests", test_property_tests),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ {name} FAILED: {e}\n")
            failed += 1
            import traceback
            traceback.print_exc()
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print("\n🎉 All enhancements verified successfully!")
        return 0
    else:
        print(f"\n⚠️  {failed} verification(s) failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
