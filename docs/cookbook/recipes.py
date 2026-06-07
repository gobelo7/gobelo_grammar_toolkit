"""
GGTK Cookbook - Common Tasks and Patterns
==========================================

This file contains practical examples for common GGTK tasks.
Run individual sections to see them in action.
"""

# ============================================================================
# Recipe 1: Basic Morphological Analysis
# ============================================================================

def recipe_basic_analysis():
    """Analyze a single word token."""
    from ggtk import GobeloGrammarLoader, GrammarConfig
    from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer
    
    # Initialize
    loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
    analyzer = MorphologicalAnalyzer(loader)
    
    # Analyze a token
    token = "balya"
    result = analyzer.analyze(token)
    
    print(f"Token: {result.token}")
    print(f"Best analysis: {result.best.segmented}")
    print(f"Gloss: {result.best.gloss_line}")
    print(f"Confidence: {result.best.confidence:.2f}")
    print(f"Morphemes:")
    for morpheme in result.best.morphemes:
        print(f"  - {morpheme.form} ({morpheme.gloss}) [{morpheme.slot_id}]")
    
    # Check for ambiguity
    if result.is_ambiguous:
        print(f"\nAlternative analyses ({len(result.hypotheses)} total):")
        for i, hyp in enumerate(result.top_n(3), 1):
            print(f"  {i}. {hyp.segmented} (confidence: {hyp.confidence:.2f})")


# ============================================================================
# Recipe 2: Sentence Segmentation
# ============================================================================

def recipe_sentence_segmentation():
    """Segment and analyze a full sentence."""
    from ggtk import GobeloGrammarLoader, GrammarConfig
    from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer
    
    loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
    analyzer = MorphologicalAnalyzer(loader)
    
    sentence = "Bakali bàlìzyà kùkàla kwàbo."
    results = analyzer.segment_text(sentence)
    
    print(f"Sentence: {sentence}\n")
    for result in results:
        if result.best:
            print(f"{result.token:15} → {result.best.segmented:20} | {result.best.gloss_line}")


# ============================================================================
# Recipe 3: Verb Paradigm Generation
# ============================================================================

def recipe_verb_paradigm():
    """Generate a complete verb paradigm."""
    from ggtk import GobeloGrammarLoader, GrammarConfig
    from ggtk.apps.paradigm_generator import ParadigmGenerator
    
    loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
    gen = ParadigmGenerator(loader)
    
    # Generate paradigm for verb root "lya" (eat)
    root = "lya"
    subject_nc = "NC1"  # human singular
    tam_id = "TAM_PRES"  # present tense
    
    paradigm = gen.generate_verb_paradigm(root, subject_nc, tam_id)
    
    print(f"Verb: {root} (Subject: {subject_nc}, TAM: {tam_id})\n")
    for form in paradigm.forms:
        print(f"{form.nc_id:6} → {form.surface:15} | {form.gloss}")


# ============================================================================
# Recipe 4: Concord Tables
# ============================================================================

def recipe_concord_tables():
    """Generate concord agreement tables."""
    from ggtk import GobeloGrammarLoader, GrammarConfig
    from ggtk.apps.concord_generator import ConcordGenerator
    
    loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
    gen = ConcordGenerator(loader)
    
    # Get subject concords
    sc = loader.get_subject_concords()
    print("Subject Concords:")
    print("-" * 40)
    for nc_id, form in sorted(sc.entries.items()):
        print(f"{nc_id:6} → {form}")
    
    # Cross-tabulate subject and object concords
    print("\n\nSubject-Object Concord Matrix:")
    print("=" * 60)
    matrix = gen.cross_tab("subject_concords", "object_concords")
    
    # Print header
    print(f"{'Subj':<8}", end="")
    for obj_nc in sorted(matrix.keys()):
        print(f"{obj_nc:<10}", end="")
    print()
    
    # Print rows
    for subj_nc in sorted(matrix.keys()):
        print(f"{subj_nc:<8}", end="")
        for obj_nc in sorted(matrix.keys()):
            if obj_nc in matrix[subj_nc]:
                print(f"{matrix[subj_nc][obj_nc]:<10}", end="")
            else:
                print(f"{'-':<10}", end="")
        print()


# ============================================================================
# Recipe 5: Language Comparison
# ============================================================================

def recipe_language_comparison():
    """Compare features across languages."""
    from ggtk import GobeloGrammarLoader, GrammarConfig
    from ggtk.apps.feature_comparator import FeatureComparator
    
    # Load two languages
    toi_loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
    bem_loader = GobeloGrammarLoader(GrammarConfig(language="bem"))
    
    # Create comparator
    comparator = FeatureComparator({
        "chitonga": toi_loader,
        "chibemba": bem_loader
    })
    
    # Compare noun classes
    print("Comparing Noun Classes:")
    print("=" * 60)
    diff = comparator.compare_feature("noun_classes")
    print(diff.summary())
    
    # Compare TAM markers
    print("\n\nComparing TAM Markers:")
    print("=" * 60)
    tam_diff = comparator.compare_feature("tam")
    print(tam_diff.summary())


# ============================================================================
# Recipe 6: Corpus Annotation
# ============================================================================

def recipe_corpus_annotation():
    """Annotate corpus text in CoNLL-U format."""
    from ggtk import GobeloGrammarLoader, GrammarConfig
    from ggtk.apps.corpus_annotator import CorpusAnnotator
    
    loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
    annotator = CorpusAnnotator(loader)
    
    # Annotate text
    text = "Bakali bàlìzyà. Muntu wàkàlà."
    annotated = annotator.annotate_text(text)
    
    # Convert to CoNLL-U format
    conllu = annotator.to_conllu(annotated)
    print("CoNLL-U Output:")
    print("=" * 60)
    print(conllu)


# ============================================================================
# Recipe 7: Error Handling Best Practices
# ============================================================================

def recipe_error_handling():
    """Demonstrate proper error handling."""
    from ggtk import GobeloGrammarLoader, GrammarConfig
    from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer
    from ggtk.core.exceptions_enhanced import MorphologicalAnalysisError
    
    loader = GobeloGrammarLoader(GrammarConfig(language="toi"))
    analyzer = MorphologicalAnalyzer(loader)
    
    # Example 1: Handle invalid input gracefully
    try:
        result = analyzer.analyze("")
    except MorphologicalAnalysisError as e:
        print(f"Caught expected error:")
        print(f"  Message: {e.message}")
        print(f"  Context: {e.context}")
        print(f"  Suggestion: {e.suggestion}")
    
    # Example 2: Fallback analysis
    result = analyzer.analyze("unknown_word")
    if result.best.confidence < 0.5:
        print(f"\nLow confidence analysis: {result.best.segmented}")
        print(f"Warnings: {result.best.warnings}")


# ============================================================================
# Recipe 8: Web API Client Example
# ============================================================================

def recipe_web_api_client():
    """Example of using the web API from Python."""
    import requests
    
    base_url = "http://localhost:5000/api/v1"
    
    # Example 1: List languages
    response = requests.get(f"{base_url}/languages")
    if response.status_code == 200:
        data = response.json()
        print(f"Supported languages: {data['languages']}")
    
    # Example 2: Analyze token
    response = requests.post(
        f"{base_url}/analyze",
        json={'token': 'balya', 'language': 'toi'}
    )
    if response.status_code == 200:
        data = response.json()
        print(f"\nAnalysis: {data['best_analysis']['segmented']}")
        print(f"Gloss: {data['best_analysis']['gloss_line']}")
    
    # Example 3: Batch analysis
    response = requests.post(
        f"{base_url}/analyze/batch",
        json={'tokens': ['balya', 'muntu'], 'language': 'toi'}
    )
    if response.status_code == 200:
        data = response.json()
        print(f"\nBatch results: {data['count']} tokens analyzed")


if __name__ == "__main__":
    print("GGTK Cookbook Examples")
    print("=" * 60)
    print("\nRun individual recipes by calling their functions:")
    print("  recipe_basic_analysis()")
    print("  recipe_sentence_segmentation()")
    print("  recipe_verb_paradigm()")
    print("  etc.")
