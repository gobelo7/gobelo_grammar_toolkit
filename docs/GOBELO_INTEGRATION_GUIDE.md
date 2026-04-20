# Gobelo Platform — Integration Guide
## Folder Structure, Installation & YAML Integration

---

## 0. Current workspace integration

This repository already contains both the poster app and the core grammar toolkit.

- `gobelo_poster/` — Flask poster generator, API routes, and conjugation engine
- `gobelo_grammar_toolkit/` — core package with YAML grammar files in `gobelo_grammar_toolkit/languages`
- `gobelo_poster/app.py` already supports loading `GGT_YAML_DIR` for richer grammar data

Quick start from the repo root:

```bash
pip install -e .
cd gobelo_poster
GGT_YAML_DIR="../gobelo_grammar_toolkit/languages" python app.py
```

Then open `http://localhost:5050/poster`.

If you want a single domain, run the poster app behind a web server or reverse proxy and point `/poster` to the Flask app.

---

## 1. Complete Folder Structure

```
gobelo/                                   ← root of the entire project
│
├── .env                                  ← secrets (never commit)
├── .gitignore
├── README.md
│
├── grammar/                              ← ALL GGT YAML grammar files
│   ├── chitonga.yaml                     ✅ canonical reference / schema
│   ├── chibemba.yaml                     ✅ done
│   ├── chinyanja.yaml                    ✅ done
│   ├── silozi.yaml                       ✅ done
│   ├── cikaonde.yaml                     ✅ done
│   ├── ciluvale.yaml                     ✅ done
│   └── cilunda.yaml                      ✅ done
│
├── ggt/                                  ← GGT Python library (gobelo_grammar_toolkit)
│   ├── pyproject.toml
│   ├── README.md
│   └── gobelo_grammar_toolkit/
│       ├── __init__.py
│       ├── models.py                     ← typed dataclass models
│       ├── config.py                     ← immutable config
│       ├── exceptions.py                 ← typed exception hierarchy
│       ├── schema_validator.py
│       ├── grammar_normalizer.py
│       ├── loader.py                     ← GobeloGrammarLoader
│       ├── registry.py                   ← thread-safe GrammarRegistry
│       ├── morphological_analyzer.py
│       ├── ud_feature_mapper.py
│       ├── concord_generator.py
│       ├── verb_slot_validator.py
│       ├── corpus_annotation.py
│       ├── cross_language_comparator.py
│       ├── cli.py                        ← Click CLI
│       └── languages/
│           ├── __init__.py               ← importlib.resources anchor
│           ├── chitonga.yaml             ← embedded copies (symlinks or copies)
│           ├── chibemba.yaml
│           ├── chinyanja.yaml
│           ├── silozi.yaml
│           ├── cikaonde.yaml
│           ├── ciluvale.yaml
│           └── cilunda.yaml
│
├── backend/                              ← Flask API server
│   ├── app.py                            ← Flask application factory
│   ├── requirements.txt
│   ├── wsgi.py                           ← gunicorn entry point
│   ├── Procfile                          ← for Railway / Render deploy
│   │
│   ├── conjugator/                       ← conjugation engine (from gobelo_poster)
│   │   ├── __init__.py
│   │   ├── engine.py                     ← build_paradigm, conjugate, load_yaml_grammar
│   │   ├── grammar_data.py               ← embedded SC/TAM data for all 7 langs
│   │   └── morphophonology.py            ← SND.1-4, VH.1, CA.1-2
│   │
│   ├── api/                              ← API blueprints
│   │   ├── __init__.py
│   │   ├── conjugate.py                  ← POST /api/conjugate
│   │   ├── languages.py                  ← GET  /api/languages
│   │   ├── word_of_day.py                ← GET  /api/wotd
│   │   └── health.py                     ← GET  /api/health
│   │
│   ├── word_bank/                        ← Word of the Day data
│   │   ├── __init__.py
│   │   ├── loader.py                     ← loads from YAML + corpus
│   │   ├── chitonga.yaml
│   │   ├── chibemba.yaml
│   │   ├── chinyanja.yaml
│   │   ├── silozi.yaml
│   │   ├── cikaonde.yaml
│   │   ├── ciluvale.yaml
│   │   └── cilunda.yaml
│   │
│   └── templates/                        ← Flask templates (fallback / SSR)
│       └── poster/
│           └── index.html                ← verb poster SPA (from gobelo_poster)
│
└── frontend/                             ← All React/Vite applications
    │
    ├── platform/                         ← gobelo.zambantutools.org  (public)
    │   ├── package.json
    │   ├── vite.config.js
    │   ├── index.html
    │   └── src/
    │       ├── main.jsx
    │       ├── App.jsx                   ← GobелоPlatform root (Nav + routing)
    │       ├── components/
    │       │   ├── Nav.jsx
    │       │   ├── WordOfTheDay.jsx       ← from GobелоPlatform.jsx
    │       │   ├── ParadigmExplorer.jsx   ← from GobелоPlatform.jsx
    │       │   ├── Card.jsx               ← the social card display
    │       │   ├── LangPill.jsx
    │       │   └── ThemePicker.jsx
    │       ├── hooks/
    │       │   ├── useParadigm.js         ← calls POST /api/conjugate
    │       │   ├── useWordOfDay.js        ← calls GET  /api/wotd
    │       │   └── useLanguages.js        ← calls GET  /api/languages
    │       ├── data/
    │       │   ├── langs.js               ← language metadata constants
    │       │   └── themes.js              ← card colour themes
    │       └── styles/
    │           └── tokens.js              ← design tokens (T object)
    │
    └── admin/                             ← admin.gobelo.zambantutools.org (private)
        ├── package.json
        ├── vite.config.js
        ├── index.html
        └── src/
            ├── main.jsx
            ├── App.jsx                   ← GGT Grammar Admin root
            └── components/               ← (existing 55-file GGT Admin components)
                ├── MetadataEditor.jsx
                ├── NounClassEditor.jsx
                ├── ConcordEditor.jsx
                ├── VerbSystemEditor.jsx
                └── VerifyManager.jsx
```

---

## 2. Step-by-Step Installation

### Prerequisites

```bash
# Confirm versions
python --version     # 3.11+
node --version       # 20+
npm --version        # 10+
git --version        # any recent
```

---

### Step 1 — Create the monorepo

```bash
mkdir gobelo && cd gobelo
git init
echo "node_modules/\n__pycache__/\n*.pyc\ndist/\nbuild/\n.env\n*.egg-info/" > .gitignore
```

---

### Step 2 — Copy in the YAML grammar files

```bash
mkdir grammar
# Copy your completed YAML files from wherever they live:
cp /path/to/chitonga.yaml   grammar/
cp /path/to/chibemba.yaml   grammar/
cp /path/to/chinyanja.yaml  grammar/
cp /path/to/silozi.yaml     grammar/
cp /path/to/cikaonde.yaml   grammar/
cp /path/to/ciluvale.yaml   grammar/
cp /path/to/cilunda.yaml    grammar/

# Confirm they all parse cleanly:
python3 -c "
import yaml, pathlib, sys
ok = True
for f in pathlib.Path('grammar').glob('*.yaml'):
    try:
        d = yaml.safe_load(f.read_text())
        print(f'  OK  {f.name}')
    except Exception as e:
        print(f'  FAIL {f.name}: {e}')
        ok = False
sys.exit(0 if ok else 1)
"
```

---

### Step 3 — Install the GGT library

```bash
mkdir ggt && cd ggt

# If gobelo_grammar_toolkit is already a package on disk, install it editably:
pip install -e /path/to/gobelo_grammar_toolkit

# OR if it is just a folder of .py files, create pyproject.toml:
cat > pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "gobelo_grammar_toolkit"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0"]

[tool.setuptools.packages.find]
where = ["."]

[tool.setuptools.package-data]
"gobelo_grammar_toolkit" = ["languages/*.yaml"]
EOF

cd ..
pip install -e ggt/
```

---

### Step 4 — Wire the YAML files into the GGT package

The GGT loader uses `importlib.resources` to find embedded YAML files.
Link (or copy) the grammar files into the package's `languages/` folder:

```bash
# Option A: symlinks (recommended — edits to grammar/ auto-reflect)
for lang in chitonga chibemba chinyanja silozi cikaonde ciluvale cilunda; do
  ln -sf "$(pwd)/grammar/${lang}.yaml" \
         "ggt/gobelo_grammar_toolkit/languages/${lang}.yaml"
done

# Option B: hard copies (simpler if symlinks cause issues on Windows)
cp grammar/*.yaml ggt/gobelo_grammar_toolkit/languages/

# Verify the GGT loader can find them:
python3 -c "
from gobelo_grammar_toolkit import GrammarRegistry
r = GrammarRegistry()
r.load_all()
for lang in r.available():
    g = r.get(lang)
    print(f'  {lang}: {g.metadata.language.name} loaded OK')
"
```

---

### Step 5 — Set up the Flask backend

```bash
mkdir -p backend/api backend/word_bank backend/conjugator backend/templates/poster

# Copy conjugation engine files (from gobelo_poster build):
cp gobelo_poster/conjugator/__init__.py    backend/conjugator/
cp gobelo_poster/conjugator/engine.py      backend/conjugator/
cp gobelo_poster/conjugator/grammar_data.py backend/conjugator/
cp gobelo_poster/conjugator/morphophonology.py backend/conjugator/

# Copy the poster SPA template:
cp gobelo_poster/templates/index.html  backend/templates/poster/

# Install Python dependencies:
cat > backend/requirements.txt << 'EOF'
flask>=3.0
pyyaml>=6.0
gunicorn>=21.0
python-dotenv>=1.0
gobelo_grammar_toolkit @ file://../ggt
EOF

pip install -r backend/requirements.txt
```

---

### Step 6 — Create the Flask app with full YAML integration

```bash
cat > backend/app.py << 'EOF'
"""
Gobelo Platform — Flask application
Integrates conjugation engine with the full GGT YAML grammar files.
"""
import os
from pathlib import Path
from flask import Flask, jsonify, render_template, request, send_from_directory
from dotenv import load_dotenv

load_dotenv()

# ── GGT registry (reads .yaml files from grammar/ directory) ─────────────────
try:
    from gobelo_grammar_toolkit import GrammarRegistry
    _registry = GrammarRegistry()
    _registry.load_all(yaml_dir=Path(os.environ.get('GGT_YAML_DIR', '../grammar')))
    GGT_AVAILABLE = True
except Exception as e:
    print(f"GGT registry unavailable: {e} — falling back to embedded grammar data")
    GGT_AVAILABLE = False

# ── Conjugation engine (always available) ────────────────────────────────────
from conjugator import GRAMMARS, build_paradigm, morpheme_key_example, load_yaml_grammar

# Enrich conjugator with .yaml data when GGT is available
YAML_DIR = Path(os.environ.get('GGT_YAML_DIR', '../grammar'))
if YAML_DIR.exists():
    for yaml_path in YAML_DIR.glob('*.yaml'):
        enriched = load_yaml_grammar(yaml_path)
        if enriched and 'lang_key' in enriched:
            GRAMMARS[enriched['lang_key']] = enriched


def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')

    # ── Serve the React platform (public) ──────────────────────────────────
    @app.route('/')
    @app.route('/wotd')
    @app.route('/paradigm')
    def platform():
        dist = Path('static/platform')
        if (dist / 'index.html').exists():
            return send_from_directory('static/platform', 'index.html')
        return "<h2>Run: cd frontend/platform && npm run build first</h2>", 200

    # ── Serve the poster SPA ───────────────────────────────────────────────
    @app.route('/poster')
    def poster():
        return render_template('poster/index.html')

    # ── Serve the admin (separate build) ───────────────────────────────────
    @app.route('/admin')
    @app.route('/admin/')
    def admin():
        dist = Path('static/admin')
        if (dist / 'index.html').exists():
            return send_from_directory('static/admin', 'index.html')
        return "<h2>Run: cd frontend/admin && npm run build first</h2>", 200

    # ── Static assets (React builds) ───────────────────────────────────────
    @app.route('/static/<path:filename>')
    def static_files(filename):
        return send_from_directory('static', filename)

    # ── API: Language list ──────────────────────────────────────────────────
    @app.route('/api/languages')
    def api_languages():
        langs = []
        for key, g in GRAMMARS.items():
            langs.append({
                'key':       key,
                'name':      g['name'],
                'iso':       g['iso'],
                'guthrie':   g['guthrie'],
                'default_tam': g.get('default_tam', []),
                'tam_order': g.get('tam_order', list(g['tam'].keys())),
                'tam': {
                    tid: {'label':t['label'],'marker':t['marker'],'fv':t['fv']}
                    for tid, t in g['tam'].items()
                },
                'neg_type':  g.get('neg_type','pre'),
                'neg_pre':   g.get('neg_pre',''),
                'neg_infix': g.get('neg_infix',''),
                'yaml_loaded': 'yaml_path' in g,
            })
        return jsonify(langs)

    # ── API: Conjugate ──────────────────────────────────────────────────────
    @app.route('/api/conjugate', methods=['POST'])
    def api_conjugate():
        data       = request.get_json(silent=True) or {}
        lang_key   = data.get('lang', 'chitonga')
        root       = (data.get('verb') or 'bona').strip('-').strip()
        gloss      = data.get('gloss', '')
        tam_ids    = data.get('tam', ['PRES','PST','FUT','PERF'])
        show_neg   = bool(data.get('show_neg', False))
        show_loc   = bool(data.get('show_loc', False))
        show_morph = bool(data.get('show_morph', True))
        extensions = data.get('extensions') or None

        if lang_key not in GRAMMARS:
            return jsonify({'error': f'Unknown language: {lang_key}'}), 400
        if not root:
            return jsonify({'error': 'Verb root required'}), 400

        grammar  = GRAMMARS[lang_key]
        paradigm = build_paradigm(grammar, root, tam_ids,
                                  show_neg=show_neg, show_loc=show_loc,
                                  extensions=extensions)

        tam_order    = grammar.get('tam_order', list(grammar['tam'].keys()))
        selected_tam = [
            {'id':tid,'label':grammar['tam'][tid]['label'],
             'marker':grammar['tam'][tid]['marker'],'fv':grammar['tam'][tid]['fv']}
            for tid in tam_order
            if tid in tam_ids and tid in grammar['tam']
        ]

        morph_key = None
        if show_morph and selected_tam:
            try:
                morph_key = morpheme_key_example(grammar, root, selected_tam[0]['id'])
            except Exception:
                pass

        neg_type = grammar.get('neg_type','pre')
        neg_formula = (
            f'SC + -{grammar.get("neg_infix","sa")}- + ROOT + FV'
            if neg_type=='infix' else
            f'{grammar.get("neg_pre","ta")}- + SC + ROOT + NEG.FV'
        )

        return jsonify({
            'lang':         {'name':grammar['name'],'iso':grammar['iso'],
                             'guthrie':grammar['guthrie'],'neg_type':neg_type,
                             'neg_pre':grammar.get('neg_pre',''),
                             'neg_infix':grammar.get('neg_infix','')},
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

    # ── API: Health ─────────────────────────────────────────────────────────
    @app.route('/api/health')
    def api_health():
        return jsonify({
            'status':    'ok',
            'version':   '1.0.0',
            'ggt':       GGT_AVAILABLE,
            'languages': list(GRAMMARS.keys()),
            'yaml_dir':  str(YAML_DIR),
        })

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=int(os.environ.get('PORT', 5050)))
EOF
```

---

### Step 7 — Create the word bank loader

```bash
cat > backend/word_bank/__init__.py << 'EOF'
EOF

cat > backend/word_bank/loader.py << 'EOF'
"""
Word Bank Loader
================
Loads the Word of the Day pool for each language.
Priority order:
  1. Entries marked as verified in the language YAML word_bank section
  2. Entries from the Chitonga corpus frequency list (chitonga only)
  3. Fallback to hardcoded minimal set in the YAML files here

Daily word selection: deterministic seed from date so the same word
appears for all users on the same day.
"""
import datetime
from pathlib import Path
import yaml

_BANK_DIR = Path(__file__).parent
_cache: dict[str, list] = {}

def _load(lang: str) -> list:
    if lang in _cache:
        return _cache[lang]
    p = _BANK_DIR / f"{lang}.yaml"
    if p.exists():
        data = yaml.safe_load(p.read_text(encoding='utf-8'))
        words = data.get('words', [])
    else:
        words = []
    _cache[lang] = words
    return words

def get_word_of_day(lang: str) -> dict:
    pool = _load(lang)
    if not pool:
        return {
            'word': lang,
            'gloss': f'No word bank for {lang} yet',
            'nc': '', 'prefix': '', 'plural': '', 'pos': 'noun',
            'example': 'Add words to backend/word_bank/{lang}.yaml',
        }
    d = datetime.date.today()
    seed = d.year * 10000 + d.month * 100 + d.day
    return pool[seed % len(pool)]
EOF

# Create a sample word bank file for ChiTonga:
cat > backend/word_bank/chitonga.yaml << 'EOF'
# ChiTonga Word Bank — backend/word_bank/chitonga.yaml
# Fields: word, nc, prefix, plural, gloss, pos, example, source
# source: corpus | grammar | verified

words:
  - word: ubuntu
    nc: NC14
    prefix: bu-
    plural: null
    gloss: humanity; compassion for others
    pos: noun
    example: Ubuntu nduwe wakasolelwa.
    source: verified

  - word: mwana
    nc: NC1
    prefix: mu-
    plural: bana
    gloss: child; son or daughter
    pos: noun
    example: Mwana uyu ulila.
    source: verified

  - word: ng'anda
    nc: NC9
    prefix: "N-"
    plural: ing'anda
    gloss: house; home
    pos: noun
    example: Ng'anda ya Mweemba ili ciinda.
    source: verified

  - word: muntu
    nc: NC1
    prefix: mu-
    plural: bantu
    gloss: person; human being
    pos: noun
    example: Muntu woonse uyanda bulakalo.
    source: verified

  - word: luyando
    nc: NC11
    prefix: lu-
    plural: null
    gloss: love; deep affection
    pos: noun
    example: Luyando lukainda.
    source: verified

  - word: busuma
    nc: NC14
    prefix: bu-
    plural: null
    gloss: goodness; well-being
    pos: noun
    example: Busuma bwako buyoowa.
    source: verified

  - word: kubona
    nc: NC15
    prefix: ku-
    plural: null
    gloss: to see; to understand
    pos: verb
    example: Ndabona luumuno lwako.
    source: verified

  - word: ciindi
    nc: NC7
    prefix: ci-
    plural: ziindi
    gloss: time; season; period
    pos: noun
    example: Ciindi ca mbila citali.
    source: verified

  - word: bupe
    nc: NC14
    prefix: bu-
    plural: null
    gloss: gift; generosity
    pos: noun
    example: Bupe bwa Leza tabusoweki.
    source: verified

  - word: munzi
    nc: NC3
    prefix: mu-
    plural: minzi
    gloss: village; home settlement
    pos: noun
    example: Twaya kumunzi kwatusyalila.
    source: verified
EOF
```

---

### Step 8 — Create the .env file

```bash
cat > .env << 'EOF'
# Gobelo Platform — environment variables
# NEVER commit this file

SECRET_KEY=change-this-to-a-random-string-in-production
GGT_YAML_DIR=../grammar
PORT=5050

# Anthropic API key — for AI example sentence generation
ANTHROPIC_API_KEY=sk-ant-...your-key-here...

# For production
FLASK_ENV=production
EOF
```

---

### Step 9 — Set up the frontend (platform)

```bash
cd frontend
npm create vite@latest platform -- --template react
cd platform
npm install

# Install dependencies used in GobелоPlatform.jsx:
npm install

# Create the entry point:
cat > src/App.jsx << 'EOF'
// Paste the full contents of GobелоPlatform.jsx here
// (the file Claude generated — it is a single default-export component)
EOF

cat > src/main.jsx << 'EOF'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
ReactDOM.createRoot(document.getElementById('root')).render(<App />)
EOF

# Update vite.config.js to proxy API calls to Flask in dev:
cat > vite.config.js << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:5050',
    }
  },
  build: {
    outDir: '../../backend/static/platform',
    emptyOutDir: true,
  }
})
EOF

cd ../..
```

---

### Step 10 — Set up the admin frontend

```bash
cd frontend
npm create vite@latest admin -- --template react
cd admin
npm install js-yaml lodash

# Copy your existing GGT Admin component files into src/
# (the 55-file GGT Grammar Admin Vite project you already have)

# Update vite.config.js:
cat > vite.config.js << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    outDir: '../../backend/static/admin',
    emptyOutDir: true,
  }
})
EOF

cd ../..
```

---

## 3. Running Everything

### Development (3 terminals)

**Terminal 1 — Flask backend:**
```bash
cd gobelo/backend
source ../.venv/bin/activate      # or your virtualenv
GGT_YAML_DIR=../grammar python app.py
# → http://localhost:5050
```

**Terminal 2 — Platform frontend (hot-reload):**
```bash
cd gobelo/frontend/platform
npm run dev
# → http://localhost:5173  (proxies /api/* to Flask)
```

**Terminal 3 — Admin frontend (hot-reload):**
```bash
cd gobelo/frontend/admin
npm run dev -- --port 5174
# → http://localhost:5174
```

### Production build

```bash
# Build both React apps (writes into backend/static/)
cd frontend/platform && npm run build && cd ../..
cd frontend/admin    && npm run build && cd ../..

# Serve everything from Flask via gunicorn:
cd backend
gunicorn -w 4 -b 0.0.0.0:5050 "app:create_app()"
```

---

## 4. URL Map

| URL | What it serves |
|-----|---------------|
| `/` | Gobelo Platform (Word of the Day) |
| `/paradigm` | Paradigm Explorer |
| `/poster` | Verb Poster Generator |
| `/admin` | GGT Grammar Admin (private) |
| `/api/languages` | Language list + TAM data |
| `/api/conjugate` | Verb paradigm (POST) |
| `/api/wotd?lang=chitonga` | Word of the Day |
| `/api/health` | Health + YAML load status |

---

## 5. YAML Integration Flow

```
grammar/*.yaml
     │
     ├─→ ggt/gobelo_grammar_toolkit/languages/   (symlinks)
     │        └─→ GrammarRegistry.load_all()     ← GGT Python library
     │
     └─→ backend/conjugator/engine.py
              └─→ load_yaml_grammar(path)
                       └─→ patches GRAMMARS dict
                                └─→ POST /api/conjugate
                                         └─→ build_paradigm()
                                                  └─→ morphophonology rules
```

**Edit cycle:**
```
1. Open Grammar Admin at /admin
2. Load chitonga.yaml → edit NC prefix / concord form / VERIFY flag
3. Download → save to grammar/chitonga.yaml
4. Flask auto-reloads (or restart) → enriched data appears in /api/conjugate
5. Poster + Paradigm Explorer reflect the change immediately
```

---

## 6. Quick Verification

```bash
# 1. YAML files parse
python3 -c "
import yaml,pathlib
for f in pathlib.Path('grammar').glob('*.yaml'):
    yaml.safe_load(f.read_text())
    print(f'OK {f.name}')
"

# 2. GGT registry loads
python3 -c "
from gobelo_grammar_toolkit import GrammarRegistry
r = GrammarRegistry(); r.load_all(yaml_dir='grammar')
print([g.metadata.language.iso_code for g in r.all()])
"

# 3. Conjugation engine + YAML enrichment
python3 -c "
import sys; sys.path.insert(0,'backend')
from conjugator import GRAMMARS, build_paradigm, load_yaml_grammar
from pathlib import Path
for p in Path('grammar').glob('*.yaml'):
    e = load_yaml_grammar(p)
    if e: GRAMMARS[e['lang_key']] = e
para = build_paradigm(GRAMMARS['chitonga'],'bona',['PRES','PERF'])
for g in para:
    for r in g['rows'][:2]:
        print(r['id'], r['forms'])
"

# 4. Flask health check
curl http://localhost:5050/api/health
# → {"ggt":true,"languages":[...],"status":"ok","yaml_loaded":true}

# 5. Full conjugation round-trip
curl -s -X POST http://localhost:5050/api/conjugate \
  -H 'Content-Type: application/json' \
  -d '{"lang":"chitonga","verb":"bona","tam":["PRES","PERF"],"show_neg":true}' \
  | python3 -m json.tool | head -40
```

---

## 7. Adding More Words to the Word Bank

Edit `backend/word_bank/<language>.yaml` and add entries:

```yaml
words:
  - word: kulya
    nc: NC15
    prefix: ku-
    plural: null
    gloss: to eat; to consume
    pos: verb
    example: Tulalya limbuto mwiiyo.
    source: corpus       # ← mark origin for quality tracking
```

For the Chitonga corpus integration, a separate script reads the
frequency list and auto-populates verified entries:

```bash
# Future script (once corpus pipeline is wired):
python3 scripts/corpus_to_wordbank.py \
  --corpus corpus/chitonga_1m.txt \
  --lang chitonga \
  --min-freq 50 \
  --output backend/word_bank/chitonga.yaml
```

---

## 8. Deployment to Production (Railway / Render)

```bash
# backend/Procfile
web: gunicorn -w 2 -b 0.0.0.0:$PORT "app:create_app()"

# Set environment variables in Railway/Render dashboard:
GGT_YAML_DIR=/app/grammar     # mount grammar/ as a volume or copy in build
SECRET_KEY=...
ANTHROPIC_API_KEY=...

# Build step (runs before deploy):
cd frontend/platform && npm ci && npm run build
cd frontend/admin    && npm ci && npm run build
```

All grammar YAML files should be included in the git repo (they are
linguistics data, not secrets). The `.env` file must never be committed.
