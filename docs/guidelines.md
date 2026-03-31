Got it — the naming was inverted from what I assumed. So the correct mapping is:

- **`index.html`** (dark, React/Tailwind) = **Linguist Admin Shell**
- **`ggt_index_v1.html`** (warm, vanilla JS) = **Student/Teacher Frontend**

Let me put together a structured implementation guideline.Here is the full implementation guideline.

---

## Project structure changes

Add one directory, keep everything else:

```
web/
├── backend/       app.py
├── frontend/      ggt_index_v1.html   ← served at /
└── admin/         index.html (+ src/) ← served at /admin
```

The admin shell is a Vite/React project. Its `dist/` output gets served by Flask as a static folder, same as the existing frontend.

---

## 1. Flask routing (app.py)

Split the 15 existing routes into two Blueprints:

```python
# blueprints/public.py  — student/teacher routes
# GET  /api/languages
# GET  /api/analyse
# GET  /api/vocab
# POST /api/quiz
# ... (read-only, no auth required)

# blueprints/admin.py   — linguist routes
# GET/POST /admin/api/languages/<lang>   (YAML read/write)
# POST     /admin/api/validate
# POST     /admin/api/build-hfst
# GET      /admin/api/routes             (introspection)
# ... (mutations, should be auth-protected)
```

Register them in `app.py`:
```python
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
```

Serve the two frontends as separate static folders:
```python
@app.route('/admin', defaults={'path': ''})
@app.route('/admin/<path:path>')
def serve_admin(path): ...   # serves web/admin/dist/

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path): ... # serves web/frontend/
```

---

## 2. Linguist admin shell (index.html / React)

This app owns everything a linguist needs to manage the grammar:

- **Language manager** — browse, diff, and edit `languages/*.yaml` via `/admin/api/languages/<lang>`
- **Validator panel** — run `validate_grammar.py` inline, surface errors with line references
- **HFST build console** — trigger `build_hfst.sh`, stream stdout, show success/fail status
- **Route monitor** — live table of all 15 Flask routes with last-called timestamps
- **Apps dashboard** — health/status of the 7 NLP modules

The dark GGT color theme (`#080c10` background, `#e8934a` accent) is already defined in `tailwind.config`. Keep it — it visually distinguishes the admin shell from the student frontend at a glance.

---

## 3. Student/teacher frontend (ggt_index_v1.html)

No structural changes needed. The existing vanilla JS app continues to call `/api/*` routes only. The only updates required:

- Point `GET('/api/languages')` at the public Blueprint (already `/api/languages` — no change)
- Remove any direct YAML file access if it exists — all data goes through Flask
- The vocabulary vocab cards that call `qa('s', ...)` and `setRole('student')` remain untouched

---

## 4. Auth boundary

The admin Blueprint should be protected even minimally before any YAML write routes go live. A simple approach for a single-team tool:

```python
# admin Blueprint: check a shared secret header or session token
@admin_bp.before_request
def require_admin():
    if request.headers.get('X-Admin-Token') != app.config['ADMIN_TOKEN']:
        abort(403)
```

The React admin shell stores the token in memory (not localStorage) and attaches it to every fetch.

---

## 5. Shared data contract

The `languages/*.yaml` files are the single source of truth. The rule:

- **Admin shell** reads and writes via `/admin/api/languages/<lang>` (PATCH for edits, POST for new language)
- **Student frontend** reads only via `/api/languages` (returns list) and `/api/analyse` etc.
- Neither frontend touches the filesystem directly — all YAML I/O goes through `core/loader.py`

---

## 6. Build and dev workflow

```
web/admin/          ← Vite project (npm run dev / npm run build)
web/frontend/       ← no build step, edit HTML directly
web/backend/app.py  ← flask run (serves both in production)
```

For development, run Vite's dev server on port 5174 and proxy `/admin/api/*` to Flask on 5000. In production, `npm run build` outputs to `web/admin/dist/` which Flask serves as a static folder.

This keeps the two frontends completely independent — different tech stacks, different audiences, different deploy cadences — while sharing one Flask process and one set of YAML files.
This keeps the two frontends completely independent — different tech stacks, different audiences, different deploy cadences — while sharing one Flask process and one set of YAML files.