"""
Gobelo Grammar Toolkit - Flask Web API
=======================================
RESTful API for accessing GGTK functionality via HTTP.

Endpoints:
  GET  /api/v1/languages          - List supported languages
  GET  /api/v1/info/<language>    - Grammar metadata
  POST /api/v1/analyze            - Morphological analysis
  POST /api/v1/generate           - Verb form generation
  GET  /api/v1/concords/<language>/<type> - Concord paradigms
  GET  /api/v1/noun-classes/<language>    - Noun class inventory

Usage:
  pip install flask flask-cors
  python app.py
  
  # Test: curl http://localhost:5000/api/v1/languages
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from typing import Dict, Any, List
import logging

from ggtk import GobeloGrammarLoader, GrammarConfig
from ggtk.apps.morphological_analyzer import MorphologicalAnalyzer
from ggtk.core.exceptions import GGTError, LanguageNotFoundError

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ggtk-api")

# ---------------------------------------------------------------------------
# Cache loaders and analyzers to avoid repeated initialization
# ---------------------------------------------------------------------------

class AnalyzerCache:
    """Thread-safe cache for language analyzers."""
    
    def __init__(self, maxsize: int = 10):
        self._cache: Dict[str, MorphologicalAnalyzer] = {}
        self._loaders: Dict[str, GobeloGrammarLoader] = {}
        self._maxsize = maxsize
    
    def get_analyzer(self, lang_iso: str) -> MorphologicalAnalyzer:
        if lang_iso not in self._cache:
            if len(self._cache) >= self._maxsize:
                # Remove oldest entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                del self._loaders[oldest_key]
            
            logger.info(f"Loading grammar for {lang_iso}")
            loader = GobeloGrammarLoader(GrammarConfig(language=lang_iso))
            analyzer = MorphologicalAnalyzer(loader)
            self._cache[lang_iso] = analyzer
            self._loaders[lang_iso] = loader
        
        return self._cache[lang_iso]
    
    def get_loader(self, lang_iso: str) -> GobeloGrammarLoader:
        if lang_iso not in self._loaders:
            self.get_analyzer(lang_iso)  # This loads both
        return self._loaders[lang_iso]

# Global cache instance
analyzer_cache = AnalyzerCache(maxsize=10)

# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Resource not found',
        'message': str(error)
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500

@app.errorhandler(LanguageNotFoundError)
def language_not_found(error):
    return jsonify({
        'error': 'Language not found',
        'message': str(error),
        'available_languages': getattr(error, 'available_languages', [])
    }), 404

@app.errorhandler(GGTError)
def ggtk_error(error):
    return jsonify({
        'error': type(error).__name__,
        'message': str(error),
        'context': getattr(error, 'context', {})
    }), 400

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route('/api/v1/languages', methods=['GET'])
def list_languages():
    """List all supported languages."""
    try:
        langs = GobeloGrammarLoader.list_supported_languages()
        return jsonify({
            'success': True,
            'count': len(langs),
            'languages': langs
        })
    except Exception as e:
        logger.error(f"Failed to list languages: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/info/<language>', methods=['GET'])
def get_language_info(language: str):
    """Get grammar metadata and feature summary for a language."""
    try:
        loader = analyzer_cache.get_loader(language)
        meta = loader.get_metadata()
        
        # Feature counts
        features = {}
        try:
            nc_all = loader.get_noun_classes(active_only=False)
            nc_active = [nc for nc in nc_all if nc.active]
            features['noun_classes'] = {
                'active': len(nc_active),
                'total': len(nc_all)
            }
        except GGTError:
            features['noun_classes'] = None
        
        try:
            tams = loader.get_tam_markers()
            features['tam_markers'] = len(tams)
        except GGTError:
            features['tam_markers'] = None
        
        try:
            exts = loader.get_extensions()
            features['verb_extensions'] = len(exts)
        except GGTError:
            features['verb_extensions'] = None
        
        try:
            ctypes = loader.get_all_concord_types()
            features['concord_paradigms'] = len(ctypes)
        except GGTError:
            features['concord_paradigms'] = None
        
        try:
            slots = loader.get_verb_slots()
            oblig = sum(1 for s in slots if s.obligatory)
            features['verb_slots'] = {
                'total': len(slots),
                'obligatory': oblig
            }
        except GGTError:
            features['verb_slots'] = None
        
        try:
            flags = loader.list_verify_flags()
            unresolved = [f for f in flags if not f.resolved]
            features['verify_flags'] = {
                'unresolved': len(unresolved),
                'total': len(flags)
            }
        except GGTError:
            features['verify_flags'] = None
        
        return jsonify({
            'success': True,
            'metadata': {
                'language': meta.language,
                'iso_code': meta.iso_code,
                'guthrie': meta.guthrie,
                'grammar_version': meta.grammar_version,
                'min_loader_version': meta.min_loader_version,
                'max_loader_version': meta.max_loader_version,
            },
            'features': features
        })
    
    except Exception as e:
        logger.error(f"Failed to get info for {language}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/analyze', methods=['POST'])
def analyze_token():
    """
    Analyze a single token morphologically.
    
    Request body:
    {
        "token": "balya",
        "language": "toi",
        "max_hypotheses": 5
    }
    """
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body must be JSON'
        }), 400
    
    token = data.get('token')
    language = data.get('language', 'toi')
    max_hypotheses = data.get('max_hypotheses', 5)
    
    if not token:
        return jsonify({
            'success': False,
            'error': 'Token is required'
        }), 400
    
    if not isinstance(token, str) or not token.strip():
        return jsonify({
            'success': False,
            'error': 'Token must be a non-empty string'
        }), 400
    
    try:
        analyzer = analyzer_cache.get_analyzer(language)
        result = analyzer.analyze(token.strip(), max_hypotheses=max_hypotheses)
        
        # Serialize hypotheses
        hypotheses = []
        for hyp in result.hypotheses:
            hypotheses.append({
                'segmented': hyp.segmented,
                'gloss_line': hyp.gloss_line,
                'confidence': hyp.confidence,
                'coverage': hyp.coverage,
                'remaining': hyp.remaining,
                'warnings': list(hyp.warnings),
                'rule_trace': list(hyp.rule_trace),
                'underlying': hyp.underlying,
                'morphemes': [
                    {
                        'form': m.form,
                        'slot_id': m.slot_id,
                        'slot_name': m.slot_name,
                        'content_type': m.content_type,
                        'gloss': m.gloss,
                        'nc_id': m.nc_id,
                    }
                    for m in hyp.morphemes
                ]
            })
        
        best = result.best
        response = {
            'success': True,
            'token': result.token,
            'language': result.language,
            'is_ambiguous': result.is_ambiguous,
            'hypothesis_count': len(result.hypotheses),
            'best_analysis': {
                'segmented': best.segmented,
                'gloss_line': best.gloss_line,
                'confidence': best.confidence,
                'coverage': best.coverage,
                'remaining': best.remaining,
                'warnings': list(best.warnings),
                'rule_trace': list(best.rule_trace),
                'underlying': best.underlying,
                'morphemes': [
                    {
                        'form': m.form,
                        'slot_id': m.slot_id,
                        'slot_name': m.slot_name,
                        'content_type': m.content_type,
                        'gloss': m.gloss,
                        'nc_id': m.nc_id,
                    }
                    for m in best.morphemes
                ]
            },
            'hypotheses': hypotheses[:max_hypotheses]
        }
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Analysis failed for '{token}': {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/analyze/batch', methods=['POST'])
def analyze_batch():
    """
    Analyze multiple tokens in one request.
    """
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body must be JSON'
        }), 400
    
    tokens = data.get('tokens', [])
    language = data.get('language', 'toi')
    max_hypotheses = data.get('max_hypotheses', 3)
    
    if not tokens or not isinstance(tokens, list):
        return jsonify({
            'success': False,
            'error': 'Tokens must be a non-empty list'
        }), 400
    
    if len(tokens) > 100:
        return jsonify({
            'success': False,
            'error': 'Maximum 100 tokens per batch request'
        }), 400
    
    try:
        analyzer = analyzer_cache.get_analyzer(language)
        results = []
        
        for token in tokens:
            if not isinstance(token, str) or not token.strip():
                continue
            
            result = analyzer.analyze(token.strip(), max_hypotheses=max_hypotheses)
            results.append({
                'token': result.token,
                'best_segmented': result.best.segmented if result.best else None,
                'best_gloss': result.best.gloss_line if result.best else None,
                'confidence': result.best.confidence if result.best else 0.0,
                'hypothesis_count': len(result.hypotheses)
            })
        
        return jsonify({
            'success': True,
            'count': len(results),
            'results': results
        })
    
    except Exception as e:
        logger.error(f"Batch analysis failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/generate', methods=['POST'])
def generate_form():
    """
    Generate a verb surface form from features.
    """
    data = request.json
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body must be JSON'
        }), 400
    
    language = data.get('language', 'toi')
    
    try:
        from ggtk.apps.morphological_analyzer import MorphFeatureBundle
        
        features = MorphFeatureBundle(
            root=data['root'],
            subject_nc=data['subject_nc'],
            tam_id=data['tam_id'],
            object_nc=data.get('object_nc'),
            extensions=tuple(data.get('extensions', [])),
            polarity=data.get('polarity', 'affirmative'),
            final_vowel=data.get('final_vowel', 'a'),
        )
        
        analyzer = analyzer_cache.get_analyzer(language)
        result = analyzer.generate(features)
        
        return jsonify({
            'success': True,
            'surface': result.surface,
            'segmented': result.segmented,
            'gloss': result.gloss,
            'underlying': result.underlying,
            'rule_trace': list(result.rule_trace),
            'warnings': list(result.warnings),
            'morphemes': [
                {
                    'form': m.form,
                    'slot_id': m.slot_id,
                    'slot_name': m.slot_name,
                    'content_type': m.content_type,
                    'gloss': m.gloss,
                }
                for m in result.morphemes
            ]
        })
    
    except KeyError as e:
        return jsonify({
            'success': False,
            'error': f'Missing required field: {e}'
        }), 400
    
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/concords/<language>/<concord_type>', methods=['GET'])
def get_concords(language: str, concord_type: str):
    """Get concord paradigm entries."""
    try:
        loader = analyzer_cache.get_loader(language)
        cs = loader.get_concords(concord_type)
        
        return jsonify({
            'success': True,
            'concord_type': cs.concord_type,
            'entries': cs.entries,
            'count': len(cs.entries)
        })
    
    except Exception as e:
        logger.error(f"Failed to get concords: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404


@app.route('/api/v1/noun-classes/<language>', methods=['GET'])
def get_noun_classes(language: str):
    """Get noun class inventory."""
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    
    try:
        loader = analyzer_cache.get_loader(language)
        ncs = loader.get_noun_classes(active_only=active_only)
        
        return jsonify({
            'success': True,
            'active_only': active_only,
            'count': len(ncs),
            'noun_classes': [
                {
                    'id': nc.id,
                    'prefix': nc.prefix,
                    'allomorphs': nc.allomorphs,
                    'semantic_domain': nc.semantic_domain,
                    'active': nc.active,
                    'singular_counterpart': nc.singular_counterpart,
                    'plural_counterpart': nc.plural_counterpart,
                }
                for nc in ncs
            ]
        })
    
    except Exception as e:
        logger.error(f"Failed to get noun classes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'GGTK API',
        'version': '1.0.0'
    })


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='GGTK Web API Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    logger.info(f"Starting GGTK API server on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
