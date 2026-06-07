# GGTK Web API

RESTful API for the Gobelo Grammar Toolkit.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py

# Or with custom options
python app.py --host 127.0.0.1 --port 8080 --debug
```

## API Endpoints

### List Languages
```bash
curl http://localhost:5000/api/v1/languages
```

### Get Language Info
```bash
curl http://localhost:5000/api/v1/info/toi
```

### Analyze Token
```bash
curl -X POST http://localhost:5000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"token": "balya", "language": "toi"}'
```

### Batch Analysis
```bash
curl -X POST http://localhost:5000/api/v1/analyze/batch \
  -H "Content-Type: application/json" \
  -d '{"tokens": ["balya", "muntu"], "language": "toi"}'
```

### Generate Verb Form
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

### Get Concords
```bash
curl http://localhost:5000/api/v1/concords/toi/subject_concords
```

### Get Noun Classes
```bash
curl http://localhost:5000/api/v1/noun-classes/toi
curl http://localhost:5000/api/v1/noun-classes/toi?active_only=false
```

## Configuration

The API uses an LRU cache (default size: 10) to store loaded grammars and analyzers for performance.

## Production Deployment

For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Error Handling

All endpoints return JSON responses with consistent error format:

```json
{
  "success": false,
  "error": "Error message",
  "context": {...}
}
```

## Rate Limiting

For production deployments, consider adding rate limiting using Flask-Limiter:

```bash
pip install flask-limiter
```

Then add to `app.py`:
```python
from flask_limiter import Limiter
limiter = Limiter(app, default_limits=["200 per day", "50 per hour"])
```
