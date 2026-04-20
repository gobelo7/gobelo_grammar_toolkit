"""
Gobelo Poster — Flask Web Application
======================================
Routes
------
  GET  /                    Poster generator UI (reads URL params on load)
  GET  /poster              Alias for / (shareable URL format)
  POST /api/conjugate       Conjugate a verb and return a paradigm
  GET  /api/languages       List available languages
  GET  /api/health          Health / version check

Usage
-----
  pip install flask pyyaml
  python app.py

For production:
  gunicorn -w 4 -b 0.0.0.0:5050 "app:create_app()"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add the current directory to Python path so we can import conjugator
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from flask import Flask, jsonify, render_template, request, send_from_directory
import os
import sys
from pathlib import Path

# Add the current directory to Python path so we can import conjugator
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from conjugator import GRAMMARS, build_paradigm, load_yaml_grammar, morpheme_key_example
from conjugator.engine import conjugate


# ── App factory ───────────────────────────────────────────────────────────────

def create_app(yaml_dir: str | Path | None = None) -> Flask:
    """
    Create and configure the Flask application.

    Parameters
    ----------
    yaml_dir : optional path to a directory containing GGT .yaml grammar files.
               If supplied, the engine will attempt to load richer grammar data
               from those files and patch the embedded defaults.
    """
    app = Flask(__name__, template_folder='templates')

    if yaml_dir is None:
        yaml_dir = os.environ.get(
            'GGT_YAML_DIR',
            Path(__file__).resolve().parents[1] / 'gobelo_grammar_toolkit' / 'languages'
        )

    if yaml_dir is None:
        yaml_dir = os.environ.get(
            'GGT_YAML_DIR',
            Path(__file__).resolve().parents[1] / 'gobelo_grammar_toolkit' / 'languages'
        )

    # Optionally enrich embedded grammar data with .yaml files
    # Temporarily disabled due to YAML parsing issues
    if False and yaml_dir:
        yaml_dir = Path(yaml_dir)
        for yaml_path in yaml_dir.glob('*.yaml'):
            # Skip template files and very large files
            if 'template' in yaml_path.name or yaml_path.stat().st_size > 1000000:
                continue
            try:
                enriched = load_yaml_grammar(yaml_path)
                if enriched and 'lang_key' in enriched:
                    key = enriched['lang_key']
                    if key in GRAMMARS:
                        GRAMMARS[key] = enriched   # type: ignore[assignment]
                        app.logger.info(f'Loaded YAML grammar for {key} from {yaml_path}')
            except Exception as e:
                app.logger.warning(f'Failed to load {yaml_path}: {e}')
                continue

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route('/')
    @app.route('/poster')
    def index():
        """Serve the Gobelo Platform UI."""
        return render_template('index.html')

    @app.route('/api/languages')
    def list_languages():
        """Return a list of available languages with metadata."""
        langs = [
            {
                'key':     key,
                'name':    g['name'],
                'iso':     g['iso'],
                'guthrie': g['guthrie'],
                'default_tam': g.get('default_tam', []),
                'tam': {
                    tid: {'label': t['label'], 'marker': t['marker'], 'fv': t['fv']}
                    for tid, t in g['tam'].items()
                },
                'tam_order': g.get('tam_order', list(g['tam'].keys())),
                'neg_type': g.get('neg_type', 'pre'),
                'neg_pre':  g.get('neg_pre', ''),
                'neg_infix': g.get('neg_infix', ''),
                'yaml_loaded': 'yaml_path' in g,
            }
            for key, g in GRAMMARS.items()
        ]
        return jsonify(langs)

    @app.route('/api/conjugate', methods=['POST'])
    def conjugate_verb():
        """
        Conjugate a verb and return a full paradigm.

        Request body (JSON)
        -------------------
        {
          "lang":       "chitonga",
          "verb":       "bona",
          "gloss":      "to see",
          "tam":        ["PRES", "PST", "FUT", "PERF"],
          "show_neg":   false,
          "show_loc":   false,
          "show_morph": true,
          "extensions": []       // optional: ["APPL"], ["APPL","PASS"], etc.
        }

        Response (JSON)
        ---------------
        {
          "lang":        { name, iso, guthrie, neg_type, neg_pre, neg_infix },
          "root":        "bona",
          "gloss":       "to see",
          "selected_tam": [ { id, label, marker, fv } ],
          "paradigm":    [ { label, color, rows: [ { id, label, sublabel, forms } ] } ],
          "morph_key":   { slots, surface, tam_label, sc_label } | null,
          "formula":     "SC + TAM + ROOT + FV"
        }
        """
        data = request.get_json(silent=True) or {}

        lang_key   = data.get('lang', 'chitonga')
        root       = (data.get('verb') or 'bona').strip('-').strip()
        gloss      = data.get('gloss', '')
        tam_ids    = data.get('tam', ['PRES', 'PST', 'FUT', 'PERF'])
        show_neg   = bool(data.get('show_neg', False))
        show_loc   = bool(data.get('show_loc', False))
        show_morph = bool(data.get('show_morph', True))
        extensions = data.get('extensions') or None

        if lang_key not in GRAMMARS:
            return jsonify({'error': f'Unknown language key: {lang_key!r}. '
                                     f'Valid keys: {list(GRAMMARS)}'}), 400

        if not root:
            return jsonify({'error': 'Verb root is required'}), 400

        grammar = GRAMMARS[lang_key]

        # Build paradigm
        paradigm = build_paradigm(
            grammar, root, tam_ids,
            show_neg=show_neg,
            show_loc=show_loc,
            extensions=extensions,
        )

        # Ordered list of selected TAM entries
        tam_order    = grammar.get('tam_order', list(grammar['tam'].keys()))
        selected_tam = [
            {
                'id':     tid,
                'label':  grammar['tam'][tid]['label'],
                'marker': grammar['tam'][tid]['marker'],
                'fv':     grammar['tam'][tid]['fv'],
                'note':   grammar['tam'][tid].get('note', ''),
            }
            for tid in tam_order
            if tid in tam_ids and tid in grammar['tam']
        ]

        # Morpheme-key example (first selected TAM, 3SG)
        morph_key = None
        if show_morph and selected_tam:
            first_tid = selected_tam[0]['id']
            try:
                morph_key = morpheme_key_example(grammar, root, first_tid, sc_key='3SG')
            except Exception:
                pass   # non-fatal

        # Negation formula string for the poster footer
        neg_type  = grammar.get('neg_type', 'pre')
        neg_pre   = grammar.get('neg_pre', '')
        neg_infix = grammar.get('neg_infix', '')
        if neg_type == 'infix':
            neg_formula = f'SC + -{neg_infix}- + ROOT + FV'
        else:
            neg_formula = f'{neg_pre}- + SC + ROOT + NEG.FV'

        return jsonify({
            'lang': {
                'name':     grammar['name'],
                'iso':      grammar['iso'],
                'guthrie':  grammar['guthrie'],
                'neg_type': neg_type,
                'neg_pre':  neg_pre,
                'neg_infix': neg_infix,
            },
            'root':         root,
            'gloss':        gloss,
            'selected_tam': selected_tam,
            'paradigm':     paradigm,
            'morph_key':    morph_key,
            'formula':      'SC + TAM + ROOT + FV',
            'neg_formula':  neg_formula,
        })

    # ── API: Word of the Day ────────────────────────────────────────────────
    @app.route('/api/wotd')
    def api_wotd():
        from word_bank.loader import get_word_of_day
        lang = request.args.get('lang', 'chitonga')
        return jsonify(get_word_of_day(lang))

    @app.route('/api/health')
    def health():
        from word_bank.loader import _load
        word_bank_status = {}
        for lang in GRAMMARS.keys():
            try:
                words = _load(lang)
                word_bank_status[lang] = len(words)
            except Exception:
                word_bank_status[lang] = 0

        return jsonify({
            'status':    'ok',
            'version':   '1.0.0',
            'platform':  'Gobelo Platform',
            'languages': list(GRAMMARS.keys()),
            'word_bank': word_bank_status,
        })

    return app


# ── Entry point ───────────────────────────────────────────────────────────────

app = create_app(
    yaml_dir=os.environ.get('GGT_YAML_DIR')   # set in environment if YAML files present
)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=True, port=port, host='0.0.0.0')
