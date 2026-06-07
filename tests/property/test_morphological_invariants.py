"""
Property-based tests for morphological analyzer invariants.

Uses Hypothesis library to generate random inputs and verify
that the analyzer maintains certain invariants.
"""

import pytest
from hypothesis import given, settings, strategies as st
from ggtk.core.config import GrammarConfig
from ggtk.core.loader import GobeloGrammarLoader
from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer


@pytest.fixture(scope="module")
def analyzer():
    """Module-scoped analyzer for property tests."""
    loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
    return MorphologicalAnalyzer(loader)


# Strategy for generating valid-looking Bantu tokens
bantu_token = st.text(
    alphabet=st.sampled_from(list("abcdefghijklmnopqrstuvwxyz-")),
    min_size=1,
    max_size=20
).filter(lambda x: x.isalpha() or '-' in x)


class TestMorphologicalInvariants:
    """Test invariants that should always hold."""
    
    @given(bantu_token)
    @settings(max_examples=100)
    def test_analyze_always_returns_result(self, analyzer, token):
        """Analyzer should never crash on alphabetic input."""
        result = analyzer.analyze(token)
        assert result.token == token
        assert result.best is not None
        assert len(result.hypotheses) > 0
    
    @given(bantu_token)
    @settings(max_examples=100)
    def test_best_has_highest_confidence(self, analyzer, token):
        """Best hypothesis should have highest confidence."""
        result = analyzer.analyze(token)
        if len(result.hypotheses) > 1:
            best_conf = result.best.confidence
            for hyp in result.hypotheses:
                assert hyp.confidence <= best_conf + 0.001  # Allow small epsilon
    
    @given(bantu_token)
    @settings(max_examples=100)
    def test_segmented_form_preserves_characters(self, analyzer, token):
        """Segmented form should contain all original characters."""
        result = analyzer.analyze(token)
        segmented = result.best.segmented
        # Remove hyphens from segmented form
        segmented_no_hyphens = segmented.replace('-', '')
        # Should be a permutation of original token (case-insensitive)
        assert sorted(segmented_no_hyphens.lower()) == sorted(token.lower())
    
    @given(bantu_token)
    @settings(max_examples=100)
    def test_confidence_in_valid_range(self, analyzer, token):
        """Confidence scores should be between 0 and 1."""
        result = analyzer.analyze(token)
        for hyp in result.hypotheses:
            assert 0.0 <= hyp.confidence <= 1.0
    
    @given(bantu_token)
    @settings(max_examples=100)
    def test_morphemes_not_empty(self, analyzer, token):
        """Each hypothesis should have at least one morpheme."""
        result = analyzer.analyze(token)
        for hyp in result.hypotheses:
            assert len(hyp.morphemes) > 0
    
    @given(bantu_token)
    @settings(max_examples=100)
    def test_gloss_line_matches_morpheme_count(self, analyzer, token):
        """Gloss line should have same number of parts as morphemes."""
        result = analyzer.analyze(token)
        for hyp in result.hypotheses:
            morpheme_count = len([m for m in hyp.morphemes if m.form])
            gloss_parts = hyp.gloss_line.split('-')
            assert len(gloss_parts) == morpheme_count


class TestBatchProcessing:
    """Test batch processing invariants."""
    
    @given(st.lists(bantu_token, min_size=1, max_size=10))
    @settings(max_examples=50)
    def test_batch_preserves_order(self, analyzer, tokens):
        """Batch analysis should preserve token order."""
        results = analyzer.analyze_batch(tokens)
        assert len(results) == len(tokens)
        for result, token in zip(results, tokens):
            assert result.token == token
    
    @given(st.lists(bantu_token, min_size=1, max_size=10))
    @settings(max_examples=50)
    def test_batch_same_as_individual(self, analyzer, tokens):
        """Batch results should match individual analysis."""
        batch_results = analyzer.analyze_batch(tokens)
        individual_results = [analyzer.analyze(t) for t in tokens]
        
        for batch_res, ind_res in zip(batch_results, individual_results):
            assert batch_res.token == ind_res.token
            assert batch_res.best.segmented == ind_res.best.segmented
            assert abs(batch_res.best.confidence - ind_res.best.confidence) < 0.001
