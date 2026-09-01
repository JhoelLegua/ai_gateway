# AI Gateway Perimetral

A perimeter security proxy for LLM-based applications built as a thesis-grade
engineering project. Intercepts, inspects, and sanitizes user prompts through
a 5-layer security pipeline before they reach the backend LLM, and audits
responses before delivery to the client.

---

## Architecture Overview

```
Client / Frontend
      |
      | Authorization: Bearer <token>
      v
[AI Gateway Perimetral - FastAPI]
      |
      |-- Layer 1: Heuristic Filter      (regex / banned substrings)  < 1ms
      |-- Layer 2: Vector Similarity     (ChromaDB cosine search)     5-20ms
      |-- Layer 3: AI Classifier         (Transformer ONNX on CPU)    25-60ms
      |-- Layer 4: Canary Injection      (cryptographic token embed)  < 1ms
      |
      v
[Groq Cloud LLM - llama-3.3-70b-versatile]
      |
      v
      |-- Layer 5: Egress Scanner        (canary + leak detection)    < 2ms
      |
      v
Client Response (HTTP 200 / 400 / 500) + Telemetry
```

---

## Prerequisites

- Python 3.10 or higher
- A free [Groq Cloud](https://console.groq.com) account and API key
- (Optional) A [Brevo](https://app.brevo.com) account for SMTP email alerts

---

## Quick Start

### 1. Activate the virtual environment

```powershell
# Windows
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> Note: The first run will download the embedding model (`all-MiniLM-L6-v2`)
> and the Prompt Guard classifier (~270MB total) to `./models_cache`.
> Ensure you have at least 2GB of free RAM available.

### 3. Configure environment variables

```bash
copy .env.example .env
```

Open `.env` and set your Groq API key:

```bash
BACKEND_API_KEY="gsk_your_key_here"
```

To enable email alerts, also configure:

```bash
SMTP_ENABLED=True
SMTP_USER="your_brevo_email@example.com"
SMTP_PASSWORD="your_brevo_smtp_key"
ALERT_RECIPIENT_EMAIL="your_inbox@example.com"
```

### 4. Run the gateway

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Access Points

| URL | Description |
|-----|-------------|
| `http://localhost:8000/app` | Frontend chat interface with live security inspector |
| `http://localhost:8000/docs` | Scalar interactive API documentation |
| `http://localhost:8000/v1/gateway/health` | Health and statistics endpoint |

---

## API Endpoints

### POST /v1/gateway/chat

The primary gateway endpoint. Requires a valid `Authorization: Bearer <token>` header.

**Request:**
```json
{
  "user_id": "usr_001",
  "session_id": "ses_001",
  "message": "What is my account balance?",
  "bypass_gateway": false
}
```

**Responses:**
- `200 OK` - Request passed all layers, LLM response returned with telemetry.
- `400 Bad Request` - Request blocked at ingress (Layers 1, 2, or 3).
- `401 Unauthorized` - Invalid or missing Bearer token.
- `500 Internal Server Error` - Egress anomaly detected (Layer 5).

### GET /v1/gateway/health

Returns operational metrics, per-layer statistics, ChromaDB state, and model status.

### POST /v1/gateway/reset-vault

Clears all learned attack signatures from ChromaDB and reloads the seed dataset.
Requires a valid Bearer token.

---

## Authentication

The gateway uses Bearer token authentication. Client tokens are never stored
in plaintext. Only their SHA-256 hex digests are stored in `ALLOWED_CLIENT_API_KEYS_HASHES`.

To generate the hash for a new token:

```python
import hashlib
raw_token = "your_raw_token_here"
print(hashlib.sha256(raw_token.encode()).hexdigest())
```

The default development token is `test` (hash pre-configured in `.env.example`).

---

## Security Pipeline Details

| Layer | Name | Mechanism | Latency | On Block |
|-------|------|-----------|---------|----------|
| 1 | Heuristic Filter | Regex + banned substrings | < 1ms | HTTP 400 |
| 2 | Vector Similarity | ChromaDB cosine distance | 5-20ms | HTTP 400 |
| 3 | AI Classifier | Transformer (DistilRoBERTa ONNX) | 25-60ms | HTTP 400 + auto-registers in ChromaDB |
| 4 | Canary Injection | `secrets.token_hex()` + system prompt | < 1ms | N/A |
| 5 | Egress Scanner | Canary check + leak indicators | < 2ms | HTTP 500 + auto-registers in ChromaDB |

### Immunity Feedback Loop

When Layers 3 or 5 detect a new attack that is not yet in ChromaDB,
the attack prompt is automatically vectorized and registered. On the next
identical or semantically similar request, Layer 2 blocks it directly in
under 20ms without invoking the heavier AI model.

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
ai_gateway/
├── app/
│   ├── main.py                         # FastAPI app factory + lifespan
│   ├── api/
│   │   ├── gateway.py                  # POST /v1/gateway/chat
│   │   └── monitoring.py               # GET /health, POST /reset-vault
│   ├── core/
│   │   ├── config.py                   # Pydantic Settings singleton
│   │   ├── security.py                 # Bearer token validation + canary generation
│   │   ├── metrics.py                  # Thread-safe in-memory metrics collector
│   │   └── pipeline/
│   │       ├── manager.py              # Pipeline orchestrator
│   │       ├── layer_1_heuristics.py
│   │       ├── layer_2_vectorial.py
│   │       ├── layer_3_intelligence.py
│   │       ├── layer_4_canary.py
│   │       └── layer_5_egress.py
│   ├── services/
│   │   ├── vector_db.py                # ChromaDB wrapper
│   │   ├── llm_client.py               # Groq Cloud async HTTP client
│   │   └── email_notifier.py           # Brevo SMTP alert service
│   └── models/
│       └── schemas.py                  # Pydantic v2 request/response models
├── frontend/                           # Web UI (Chat + Security Inspector)
├── data/
│   └── seed_attacks.json               # Initial attack signature dataset
├── docs/                               # Technical documentation
├── tests/                              # Unit and E2E tests
├── .env.example                        # Configuration template
└── requirements.txt
```

---

## Technology Stack

| Category | Technology |
|----------|-----------|
| Runtime | Python 3.10+ |
| Web Framework | FastAPI + Uvicorn |
| API Documentation | Scalar (scalar-fastapi) |
| Vector Database | ChromaDB (embedded, local) |
| AI Security Model | protectai/distilroberta-base-prompt-injection |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| LLM Backend | Groq Cloud (llama-3.3-70b-versatile) |
| HTTP Client | httpx (async) |
| Email Alerts | Brevo SMTP (smtplib) |
| Configuration | pydantic-settings |

---

## Documentation

Additional documentation is available in the `/docs` directory:

- `docs/arquitectura.md` - Clean Architecture design and project structure
- `docs/especificacion_tecnica.md` - Full engineering specification and pipeline details
