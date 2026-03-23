# Connecting GGT Python Library to Web Application

## Quick Start

### Step 1: Install Your GGT Library

```bash
# Option A: Install from source
cd /path/to/your/ggt/repository
pip install -e .

# Option B: Install from PyPI (when published)
pip install gobelo-grammar-toolkit
```

### Step 2: Verify GGT Installation

```bash
python -c "from gobelo_grammar_toolkit import GobeloGrammarLoader; print('GGT OK')"
```

### Step 3: Test the Bridge

```bash
cd /home/z/my-project
echo '{"action": "languages"}' | python3 python/bridge.py
```

Expected output:
```json
{"languages": [...], "success": true, "ggt_available": true}
```

### Step 4: Check Connection

Visit: `http://localhost:3000/api/ggt?action=check`

Expected response:
```json
{
  "ggtAvailable": true,
  "message": "GGT Python library connected"
}
```

---

## How It Works

The API route (`/src/app/api/ggt/route.ts`) automatically detects if your GGT Python library is available:

1. **First request**: Checks if Python + GGT is available
2. **If available**: Routes all requests through `python/bridge.py`
3. **If not available**: Falls back to mock data

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Browser    │────▶│  Next.js    │────▶│  Python     │
│  Request    │     │  API Route  │     │  Bridge     │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼ (if Python unavailable)
                    ┌─────────────┐
                    │  Mock Data  │
                    └─────────────┘
```

---

## Deployment Scenarios

### Scenario 1: Development (Local)

The web app automatically executes Python via `child_process`. Just ensure:
- Python 3.9+ is installed
- GGT library is installed (`pip install -e .`)
- The bridge script is executable

### Scenario 2: Production Web (Vercel, Netlify)

For serverless deployment, you have several options:

#### Option A: Use External Python API

Deploy the Python service separately (e.g., Railway, Fly.io, AWS Lambda) and configure the API to call it:

```typescript
// In src/app/api/ggt/route.ts, add:
const PYTHON_API_URL = process.env.GGT_API_URL || 'http://localhost:50051';

async function callPythonAPI(action: string, params: any) {
  const response = await fetch(`${PYTHON_API_URL}/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  return response.json();
}
```

#### Option B: Docker Container

Deploy both Next.js and Python in a single Docker container:

```dockerfile
# Dockerfile
FROM node:20-slim

# Install Python
RUN apt-get update && apt-get install -y python3 python3-pip

# Install GGT
COPY python /app/python
WORKDIR /app/python
RUN pip3 install -r requirements.txt
RUN pip3 install -e /path/to/ggt

# Install Node app
COPY . /app
WORKDIR /app
RUN npm ci && npm run build

CMD npm start
```

### Scenario 3: Desktop Application

The Electron app bundles the Python executable:

1. Build Python executable: `pyinstaller python/build.spec`
2. Electron loads it automatically on startup
3. Communication via localhost HTTP

---

## Available API Endpoints

### GET Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/ggt?action=languages` | List all supported languages |
| `GET /api/ggt?action=metadata&lang=chitonga` | Get language metadata |
| `GET /api/ggt?action=tam&lang=chitonga` | Get TAM markers |
| `GET /api/ggt?action=concords&lang=chitonga` | Get subject/object concords |
| `GET /api/ggt?action=noun-classes&lang=chitonga` | Get noun classes |
| `GET /api/ggt?action=extensions&lang=chitonga` | Get verb extensions |
| `GET /api/ggt?action=verb-slots&lang=chitonga` | Get verb slot template |
| `GET /api/ggt?action=check` | Check GGT connection status |

### POST Endpoints

| Endpoint | Body | Description |
|----------|------|-------------|
| `POST /api/ggt?action=analyze` | `{word, language}` | Analyze a word |
| `POST /api/ggt?action=segment` | `{text, language}` | Segment running text |
| `POST /api/ggt?action=paradigm` | `{root, language, extensions[]}` | Generate paradigm table |
| `POST /api/ggt?action=generate` | `{root, subject, tam, language}` | Generate surface form |
| `POST /api/ggt?action=corpus` | `{text, language}` | Annotate corpus (CoNLL-U) |
| `POST /api/ggt?action=interlinear` | `{word, language}` | Generate interlinear gloss |

---

## Example Usage

### Analyze a Word

```bash
curl -X POST "http://localhost:3000/api/ggt?action=analyze" \
  -H "Content-Type: application/json" \
  -d '{"word": "balya", "language": "chitonga"}'
```

Response:
```json
{
  "analysis": {
    "input": "balya",
    "segmented": "ba-ly-a",
    "gloss": "3PL_HUMAN.SUBJ-ly-FV",
    "confidence": 0.925,
    "morphemes": [
      {"slot": "SLOT3", "type": "subject_concord", "form": "ba", "gloss": "3PL_HUMAN.SUBJ"},
      {"slot": "SLOT8", "type": "verb_root", "form": "ly", "gloss": "ly"},
      {"slot": "SLOT10", "type": "final_vowel", "form": "a", "gloss": "FV"}
    ]
  }
}
```

### Generate a Paradigm

```bash
curl -X POST "http://localhost:3000/api/ggt?action=paradigm" \
  -H "Content-Type: application/json" \
  -d '{"root": "bon", "language": "chitonga"}'
```

---

## Troubleshooting

### Error: "GGT library not available"

**Cause**: Python cannot import GGT module

**Solutions**:
1. Verify installation: `pip show gobelo-grammar-toolkit`
2. Check Python path: `python -c "import sys; print(sys.path)"`
3. Install in correct environment

### Error: "Python bridge not available"

**Cause**: Bridge script not found or not executable

**Solutions**:
1. Verify file exists: `ls python/bridge.py`
2. Check Python command: `which python3`
3. Make executable: `chmod +x python/bridge.py`

### Error: Timeout

**Cause**: Analysis taking too long

**Solutions**:
1. Increase timeout in API route
2. Use simpler queries
3. Pre-load grammars on startup

### Mock Data Being Used

**Diagnosis**: Visit `/api/ggt?action=check`

If `ggtAvailable: false`, check:
1. Python is installed and accessible
2. GGT library is installed
3. No import errors in bridge.py

---

## File Locations

```
/home/z/my-project/
├── python/
│   ├── bridge.py          # Python CLI bridge (NEW)
│   ├── service/
│   │   └── main.py        # FastAPI service
│   └── build.spec         # PyInstaller config
│
├── src/app/api/ggt/
│   └── route.ts           # Next.js API route (UPDATED)
│
└── src/lib/
    └── ggt-data.ts        # Mock data (fallback)
```

---

## Next Steps

1. **Install GGT**: `pip install -e /path/to/ggt/repository`
2. **Test Bridge**: `echo '{"action": "languages"}' | python3 python/bridge.py`
3. **Restart Dev Server**: The connection check happens on first API call
4. **Verify**: Visit `/api/ggt?action=check`

For production deployment, consider using the FastAPI service (`python/service/main.py`) as a separate backend service.
