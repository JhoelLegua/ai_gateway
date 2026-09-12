# AI Gateway Perimetral

[![Language: English](https://img.shields.io/badge/Language-English-blue.svg)](README.md)
[![Idioma: Español](https://img.shields.io/badge/Idioma-Español-gray.svg)](README_es.md)

A production-grade, perimeter security proxy for LLM-based applications engineered as a thesis-level defense system. Intercepts, inspects, and sanitizes incoming user prompts through a **5-layer security pipeline** before they reach the backend LLM, audits outgoing model responses to prevent data leakage, persists audit trails for Human-in-the-Loop (HITL) analysis, dispatches real-time incident alerts via Brevo SMTP, and includes **Telescope & Stress-Lab**: a real-time observability dashboard and load testing suite.

---

## Architecture Overview

```
                        [ Client / Web Frontend / API Consumers ]
                                           |
                                           | Authorization: Bearer <TOKEN>
                                           v
+---------------------------------------------------------------------------------------+
|                                AI GATEWAY PERIMETRAL                                  |
|                                                                                       |
|   [ Ingress Pipeline ]                                                                |
|   |-- Layer 1: Heuristic Filter      (regex / banned substrings)          < 1ms       |
|   |-- Layer 2: Vector Similarity     (ChromaDB cosine search)             5-20ms      |
|   |-- Layer 3: AI Classifier         (DeBERTa-v3 on CPU / Prompt Guard)   25-60ms     |
|   |-- Layer 4: Canary Injection      (high-entropy token embed in prompt) < 1ms       |
|                                                                                       |
|   [ Forwarding Engine ]                                                               |
|   +---> [Groq Cloud LLM Backend] (qwen/qwen3.8-27b / llama-3.3-70b)                   |
|                                                                                       |
|   [ Egress Pipeline ]                                                                 |
|   |-- Layer 5: Egress Scanner        (canary leak & system prompt audit)  < 2ms       |
|                                                                                       |
|   [ Observability & Intelligence ]                                                    |
|   |-- Immunity Feedback Loop         (Auto-learns new attack signatures in ChromaDB)  |
|   |-- Telescope Metrics Collector    (Rolling P50, P95, Max latencies & HTTP codes)   |
|   |-- PostgreSQL Audit Logs          (Full prompt history for HITL review)            |
|   |-- Brevo SMTP Alerts              (Instant incident notification to SOC team)      |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
                 Client Response (HTTP 200 / 400 / 500) + Complete Telemetry
```

---

## Key Features

- **5-Layer Security Pipeline**: Heuristics, Vector Embeddings (ChromaDB), Deep Learning Intent Classifier (DeBERTa-v3), Cryptographic Canary Injection, and Egress Verification.
- **Immunity Feedback Loop**: When Layers 3 or 5 block a zero-day prompt injection, the attack vector is automatically vectorized and registered in ChromaDB on disk, allowing Layer 2 to block subsequent identical or semantically similar attacks in < 20ms without invoking the heavier neural model.
- **Telescope & Stress-Lab**:
  - Live animated SVG packet pipeline flow (Monitor Ingress -> Gateway Pipeline -> Monitor Egress).
  - Percentile latency table by layer (P50, P95, Max, Average).
  - HTTP status breakdown donut chart (200 OK, 400 Ingress Blocked, 500 Egress Blocked).
  - Configurable Stress Testing Lab (virtual users, intervals, loops, clean/attack traffic ratio).
  - One-click export of benchmarking telemetry in JSON and CSV.
- **Human-in-the-Loop (HITL) Audit Table**: All intercepted prompts and confidence scores are stored in PostgreSQL (`prompt_audit_dataset`) for security analyst triage and dataset curation.
- **Dynamic SOC Alerting**: Automated email dispatch with security alerts via Brevo SMTP to active personnel configured in PostgreSQL (`users_notification`).
- **Modern Zero-Scroll Web UI**: Responsive 100vh dashboard with light/dark themes, multilingual support (ES/EN), attack playground presets, and real-time layer telemetry visualization.

---

## Access Points

| URL | Description |
|---|---|
| `http://localhost:8000/app/` | Main chat interface with live security inspector & attack playground |
| `http://localhost:8000/telescope` | Telescope real-time observability dashboard & stress testing lab |
| `http://localhost:8000/docs` | Scalar interactive API documentation & testing console |
| `http://localhost:8000/v1/gateway/health` | Public health, ChromaDB state, and system metrics endpoint |

---

## Prerequisites

- **Python 3.10** or higher
- **PostgreSQL 14+** database instance
- Free **[Groq Cloud](https://console.groq.com)** API key
- (Optional) Free **[Brevo](https://app.brevo.com)** account for SMTP email incident alerts

---

## Quick Start

### Option A: Automated Setup (Recommended)

Run the setup script using **Git Bash** (Windows) or **Linux/macOS terminal**:

```bash
bash setup.sh
```

### Option B: Manual Setup

#### 1. Create and activate the virtual environment

```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
source .venv/Scripts/activate
```

#### 2. Install dependencies

```bash
pip install -r requirements.txt
```

#### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```ini
BACKEND_API_KEY="gsk_your_groq_api_key"
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_gateway"
SMTP_ENABLED=True
SMTP_USER="your-smtp-user@smtp-brevo.com"
SMTP_PASSWORD="your-brevo-key"
ALERT_SENDER_EMAIL="security@yourcompany.com"
```

#### 4. Run the Gateway

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Role-Based Access Control (RBAC)

The gateway enforces **Bearer Token Authentication** using SHA-256 hex digests defined in `.env`:

| Token Role | Environment Variable | Default Dev Token | Allowed Endpoints |
|---|---|---|---|
| **Client Token** | `ALLOWED_CLIENT_API_KEYS_HASHES` | `test` | `POST /v1/gateway/chat`, `POST /v1/telescope/stress/run` |
| **Admin Token** | `ALLOWED_ADMIN_API_KEYS_HASHES` | `admin123` | `/v1/notifications/*`, `/v1/audit/*`, `/v1/gateway/reset-vault` |

---

## API Reference

### 1. Perimeter Chat Proxy

#### `POST /v1/gateway/chat`
* **Auth:** `Authorization: Bearer <CLIENT_TOKEN>`
* **Request Body:**
```json
{
  "user_id": "usr_001",
  "session_id": "ses_001",
  "message": "¿Cuál es el saldo actual de mi cuenta bancaria?",
  "bypass_gateway": false
}
```
* **Responses:**
  - `200 OK`: Request passed all layers. Returns sanitized LLM response + telemetry.
  - `400 Bad Request`: Blocked at Ingress (Layers 1, 2, or 3). Returns blocked layer + telemetry.
  - `401 Unauthorized`: Missing or invalid client token.
  - `500 Internal Server Error`: Egress violation (Layer 5).

---

### 2. Telescope Observability & Stress-Lab

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/v1/telescope/metrics` | Public | Returns real-time rolling metrics, P50/P95/Max latencies by layer, and HTTP counts. |
| `GET` | `/v1/telescope/history` | Public | Returns rolling log of recent request events for the visual pipeline. |
| `POST` | `/v1/telescope/stress/run` | Client | Launches an asynchronous stress benchmark (users, delay, iterations, mix ratio). |
| `POST` | `/v1/telescope/stress/stop` | Client | Stops any currently running stress test. |
| `GET` | `/v1/telescope/stress/status` | Public | Returns live progress, success count, error count, and throughput. |

---

### 3. Incident Notifications & SOC Recipients (Admin)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/v1/notifications/recipients` | Register new security officer / SOC analyst. |
| `GET` | `/v1/notifications/recipients` | List all recipients (filter by `?active_only=true`). |
| `PATCH` | `/v1/notifications/recipients/{id}/toggle` | Activate or pause email notifications for a recipient. |
| `PUT` | `/v1/notifications/recipients/{id}` | Update recipient details. |
| `DELETE` | `/v1/notifications/recipients/{id}` | Remove recipient from database. |

---

### 4. HITL Audit & Threat Dataset (Admin)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/v1/audit/records` | Query intercepted requests (`?reviewed=bool`, `?is_threat=bool`, pagination). |
| `POST` | `/v1/audit/{id}/review` | Submit human analyst verification (`is_threat`, `threat_category`, `reviewed_by_ci`). |
| `GET` | `/v1/audit/export/seed` | Export verified threats as ChromaDB seed JSON. |

---

## Security Pipeline Specifications

| Layer | Name | Mechanism | Typical Latency | Outcome on Threat |
|---|---|---|---|---|
| **L1** | Heuristic Filter | Regex patterns + banned keywords | < 1 ms | HTTP 400 |
| **L2** | Vector Similarity | ChromaDB cosine search (`all-MiniLM-L6-v2`) | 5 - 20 ms | HTTP 400 |
| **L3** | AI Classifier | Transformer (`DeBERTa-v3` / Prompt Guard) | 25 - 60 ms | HTTP 400 + Auto-learned in ChromaDB |
| **L4** | Canary Injection | Cryptographic entropy token in system prompt | < 1 ms | Transparent forwarding |
| **L5** | Egress Scanner | Canary integrity check + leak heuristics | < 2 ms | HTTP 500 + Auto-learned in ChromaDB |

---

## Project Structure

```
ai_gateway/
├── app/
│   ├── main.py                         # FastAPI application factory & lifespan
│   ├── api/
│   │   ├── gateway.py                  # POST /v1/gateway/chat
│   │   ├── telescope.py                # Telescope metrics & stress testing runner
│   │   ├── monitoring.py               # GET /health, POST /reset-vault
│   │   ├── notifications.py            # CRUD /v1/notifications/recipients
│   │   └── audit.py                    # GET /v1/audit/records, POST /review, export
│   ├── core/
│   │   ├── config.py                   # Pydantic Settings configuration
│   │   ├── security.py                 # RBAC Bearer authentication & canary generator
│   │   ├── metrics.py                  # Rolling metrics collector with deque percentiles
│   │   └── pipeline/
│   │       ├── manager.py              # Orchestrator for 5-layer pipeline
│   │       ├── layer_1_heuristics.py   # Regex & banned keyword filter
│   │       ├── layer_2_vectorial.py    # ChromaDB semantic search
│   │       ├── layer_3_intelligence.py # DeBERTa-v3 AI classifier
│   │       ├── layer_4_canary.py       # Canary token injection
│   │       └── layer_5_egress.py       # Egress audit & leakage detection
│   ├── db/
│   │   ├── session.py                  # Async SQLAlchemy session factory & init_db
│   │   └── models.py                   # ORM models (users_notification, prompt_audit_dataset)
│   ├── services/
│   │   ├── vector_db.py                # ChromaDB vector store service
│   │   ├── llm_client.py               # Groq Cloud async HTTP client with mock fallback
│   │   └── email_notifier.py           # Brevo SMTP alert service
│   └── models/
│       ├── schemas.py                  # Request/Response Pydantic models
│       └── schemas_admin.py            # Admin, Audit & Notification schemas
├── frontend/                           # Web UI
│   ├── index.html                      # Main chat & security inspector dashboard
│   ├── style.css                       # Zero-scroll Slate/Charcoal stylesheet
│   ├── app.js                          # Client logic, i18n & telemetry renderer
│   └── telescope/                      # Telescope & Stress-Lab
│       ├── index.html                  # Telescope monitor & stress UI
│       ├── telescope.css               # Telescope design system
│       └── telescope.js                # Animated pipeline, metrics & runner logic
├── data/
│   └── seed_attacks.json               # Seed dataset of known prompt injections
├── sql/
│   └── create_tables.sql               # PostgreSQL DDL schema with triggers
├── docs/                               # Engineering & Thesis Documentation
│   ├── archify/                        # Archify Interactive Diagram Suite (HTML/SVG)
│   │   ├── index.html                  # Master architecture explorer hub
│   │   ├── 01_componentes.html         # Component map & Clean Architecture
│   │   ├── 02_flujo_pipeline.html      # 5-layer pipeline data flow
│   │   ├── 03_secuencia_peticion.html  # Interactive sequence diagram
│   │   ├── 04_maquina_estados.html     # FSM state machine & canary lifecycle
│   │   ├── 05_telescope_observabilidad.html # Telescope telemetry pipeline
│   │   └── specs/                      # Official Archify typed JSON IR specs
│   ├── arquitectura.md                 # Architecture design & data flow
│   ├── especificacion_tecnica.md       # Technical engineering specification
│   ├── guia_de_uso.md                  # Step-by-step user and demo guide
│   ├── marco_teorico_metodologico_tesis.md # Academic theoretical & methodological thesis framework
│   └── reporte_utilidad_ai_gateway.md  # Strategic utility & ROI report
├── tests/                              # Pytest test suite (47 automated tests)
├── .agents/skills/archify/             # Official Archify agent skill
├── .env.example                        # Environment variables template
├── requirements.txt                    # Python dependencies
└── setup.sh                            # Automated setup script
```

---

## Interactive Architecture Diagram Suite

This repository includes a complete interactive architecture diagram suite with self-contained HTML5 + inline SVG maps, dark/light theme switcher, real-time packet animations, dependency reach tracing, and component inspection drawer:

| Architecture Diagram | Specification File | Self-Contained Interactive Viewer | Server Mount URL |
| :--- | :--- | :--- | :--- |
| **01. Components & Clean Arch** | [`01_componentes.archify.json`](file:///d:/Limberth/ai_gateway/docs/archify/specs/01_componentes.archify.json) | [`01_componentes.html`](file:///d:/Limberth/ai_gateway/docs/archify/01_componentes.html) | `http://localhost:8000/archify/01_componentes.html` |
| **02. Pipeline & Data Flow** | [`02_flujo_pipeline.archify.json`](file:///d:/Limberth/ai_gateway/docs/archify/specs/02_flujo_pipeline.archify.json) | [`02_flujo_pipeline.html`](file:///d:/Limberth/ai_gateway/docs/archify/02_flujo_pipeline.html) | `http://localhost:8000/archify/02_flujo_pipeline.html` |
| **03. Sequence Trace** | [`03_secuencia_peticion.archify.json`](file:///d:/Limberth/ai_gateway/docs/archify/specs/03_secuencia_peticion.archify.json) | [`03_secuencia_peticion.html`](file:///d:/Limberth/ai_gateway/docs/archify/03_secuencia_peticion.html) | `http://localhost:8000/archify/03_secuencia_peticion.html` |
| **04. State Machine (FSM)** | [`04_maquina_estados.archify.json`](file:///d:/Limberth/ai_gateway/docs/archify/specs/04_maquina_estados.archify.json) | [`04_maquina_estados.html`](file:///d:/Limberth/ai_gateway/docs/archify/04_maquina_estados.html) | `http://localhost:8000/archify/04_maquina_estados.html` |
| **05. Telescope & Telemetry** | [`05_telescope_observabilidad.archify.json`](file:///d:/Limberth/ai_gateway/docs/archify/specs/05_telescope_observabilidad.archify.json) | [`05_telescope_observabilidad.html`](file:///d:/Limberth/ai_gateway/docs/archify/05_telescope_observabilidad.html) | `http://localhost:8000/archify/05_telescope_observabilidad.html` |
| **06. System Design & ADRs** | [`06_diseno_sistema.archify.json`](file:///d:/Limberth/ai_gateway/docs/archify/specs/06_diseno_sistema.archify.json) | [`06_diseno_sistema.html`](file:///d:/Limberth/ai_gateway/docs/archify/06_diseno_sistema.html) | `http://localhost:8000/archify/06_diseno_sistema.html` |
| **07. Scalability & HA** | [`07_escalabilidad_alta_disponibilidad.archify.json`](file:///d:/Limberth/ai_gateway/docs/archify/specs/07_escalabilidad_alta_disponibilidad.archify.json) | [`07_escalabilidad_alta_disponibilidad.html`](file:///d:/Limberth/ai_gateway/docs/archify/07_escalabilidad_alta_disponibilidad.html) | `http://localhost:8000/archify/07_escalabilidad_alta_disponibilidad.html` |
| **Master Architecture Hub** | *Specification Aggregator* | [`index.html`](file:///d:/Limberth/ai_gateway/docs/archify/index.html) | **`http://localhost:8000/architecture`** |

> **Offline-ready**: All HTML diagrams are standalone and require no external internet access or CDN dependencies. You can double-click them in your file manager or export them as vector SVGs for inclusion into thesis documents and presentations.

---

## Running Automated Tests

```bash
# Run all 47 unit and integration tests
pytest tests/ -v

# Run specific test suites
pytest tests/test_e2e_gateway.py -v      # End-to-end chat proxy tests
pytest tests/test_pipeline_layers.py -v  # 5-layer pipeline isolation tests
pytest tests/test_telescope.py -v        # Telescope & Stress-Lab tests
pytest tests/test_notifications.py -v    # SOC notifications & RBAC tests
pytest tests/test_audit.py -v            # Audit dataset & HITL tests
```

---

## License

This project is developed as an academic and engineering thesis project under the MIT License.
