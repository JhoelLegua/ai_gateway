# AI Gateway Perimetral

[![Idioma: Español](https://img.shields.io/badge/Idioma-Español-blue.svg)](README_es.md)
[![Language: English](https://img.shields.io/badge/Language-English-gray.svg)](README.md)

Un proxy de seguridad perimetral para aplicaciones basadas en Modelos de Lenguaje Grande (LLM), diseñado con nivel de ingeniería y grado de tesis. Intercepta, inspecciona y sanitiza los prompts entrantes de los usuarios a través de un **pipeline de seguridad de 5 capas** antes de que alcancen el LLM en el backend, audita las respuestas salientes para prevenir la fuga de datos, persiste registros de auditoría para análisis humano (*Human-in-the-Loop* o HITL), despacha alertas de incidentes en tiempo real mediante Brevo SMTP e incluye **Telescope & Stress-Lab**: un panel de observabilidad en tiempo real y suite de pruebas de estrés.

---

## Visión General de la Arquitectura

```
                        [ Cliente / Frontend Web / Consumidores API ]
                                           |
                                           | Authorization: Bearer <TOKEN>
                                           v
+---------------------------------------------------------------------------------------+
|                                AI GATEWAY PERIMETRAL                                  |
|                                                                                       |
|   [ Pipeline de Entrada / Ingress ]                                                   |
|   |-- Capa 1: Filtro Heurístico       (regex / palabras prohibidas)        < 1ms      |
|   |-- Capa 2: Similitud Vectorial     (búsqueda coseno en ChromaDB)        5-20ms     |
|   |-- Capa 3: Clasificador IA         (DeBERTa-v3 en CPU / Prompt Guard)   25-60ms    |
|   |-- Capa 4: Inyección de Canario    (token criptográfico en el prompt)   < 1ms      |
|                                                                                       |
|   [ Motor de Reenvío / Forwarding ]                                                   |
|   +---> [Backend LLM en Groq Cloud] (qwen/qwen3.8-27b / llama-3.3-70b)                |
|                                                                                       |
|   [ Pipeline de Salida / Egress ]                                                     |
|   |-- Capa 5: Escáner de Egress       (auditoría de fuga de canario/prompt)< 2ms      |
|                                                                                       |
|   [ Observabilidad e Inteligencia ]                                                   |
|   |-- Bucle de Retroalimentación     (Auto-aprende nuevas firmas en ChromaDB)         |
|   |-- Recolector Telescope           (Percentiles P50, P95, Máx y códigos HTTP)       |
|   |-- Registros de Auditoría PG      (Historial de prompts para revisión HITL)        |
|   |-- Alertas SMTP en Brevo          (Notificación inmediata al equipo SOC)           |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
               Respuesta al Cliente (HTTP 200 / 400 / 500) + Telemetría Completa
```

---

## Características Principales

- **Pipeline de Seguridad en 5 Capas**: Heurísticas, Embeddings Vectoriales (ChromaDB), Clasificador de Intención por Aprendizaje Profundo (DeBERTa-v3), Inyección de Token Canario Criptográfico y Verificación de Salida (Egress).
- **Bucle de Inmunidad y Retroalimentación (*Immunity Feedback Loop*)**: Cuando las Capas 3 o 5 bloquean una inyección de prompt de día cero, el vector del ataque se registra automáticamente en ChromaDB en disco, permitiendo que la Capa 2 bloquee futuros ataques idénticos o semánticamente similares en menos de 20 ms sin requerir invocar el modelo neuronal pesado.
- **Telescope & Stress-Lab**:
  - Flujo animado interactivo de paquetes en SVG (Monitor Entrada -> Pipeline del Gateway -> Monitor Salida).
  - Tabla de latencias por percentiles y capas (P50, P95, Máx, Promedio).
  - Gráfico circular (*Donut*) de códigos de estado HTTP (200 OK, 400 Bloqueado en Ingress, 500 Bloqueado en Egress).
  - Laboratorio de Pruebas de Estrés configurable (usuarios virtuales, intervalos de delay, bucles, mezcla de tráfico limpio vs. ataques).
  - Exportación con un clic de toda la telemetría en formatos JSON y CSV.
- **Tabla de Auditoría Human-in-the-Loop (HITL)**: Todos los prompts interceptados y sus puntuaciones de confianza se almacenan en PostgreSQL (`prompt_audit_dataset`) para la revisión de analistas de seguridad y la curación de datasets.
- **Alertas Dinámicas al Equipo SOC**: Despacho automatizado de correos electrónicos con alertas de seguridad vía Brevo SMTP al personal activo registrado en PostgreSQL (`users_notification`).
- **Interfaz Web Moderna *Zero-Scroll***: Panel adaptable en 100vh sin barras de desplazamiento vertical, con temas claro y oscuro, soporte multi-idioma (ES/EN), escenarios interactivos de ataque y visualización de telemetría en vivo.

---

## Puntos de Acceso

| URL | Descripción |
|---|---|
| `http://localhost:8000/app/` | Interfaz de chat principal con inspector de seguridad en vivo y playground |
| `http://localhost:8000/telescope` | Panel de observabilidad Telescope y laboratorio de pruebas de estrés |
| `http://localhost:8000/docs` | Consola interactiva de documentación de API con Scalar |
| `http://localhost:8000/v1/gateway/health` | Endpoint público de salud, estado de ChromaDB y métricas del sistema |

---

## Requisitos Previos

- **Python 3.10** o superior
- Instancia de base de datos **PostgreSQL 14+**
- Clave de API gratuita de **[Groq Cloud](https://console.groq.com)**
- (Opcional) Cuenta gratuita de **[Brevo](https://app.brevo.com)** para alertas de incidentes por correo electrónico (SMTP)

---

## Inicio Rápido

### Opción A: Configuración Automatizada (Recomendada)

Ejecuta el script de instalación usando **Git Bash** (en Windows) o tu terminal de **Linux/macOS**:

```bash
bash setup.sh
```

### Opción B: Configuración Manual Paso a Paso

#### 1. Crear y activar el entorno virtual

```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

#### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

#### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```ini
BACKEND_API_KEY="gsk_tu_clave_de_groq"
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_gateway"
SMTP_ENABLED=True
SMTP_USER="tu-usuario-smtp@smtp-brevo.com"
SMTP_PASSWORD="tu-clave-de-brevo"
ALERT_SENDER_EMAIL="seguridad@tuempresa.com"
```

#### 4. Ejecutar el Gateway

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Control de Acceso Basado en Roles (RBAC)

El gateway implementa autenticación mediante **Bearer Tokens** validados contra hashes SHA-256 configurados en el archivo `.env`:

| Rol del Token | Variable de Entorno | Token de Prueba por Defecto | Endpoints Permitidos |
|---|---|---|---|
| **Token de Cliente** | `ALLOWED_CLIENT_API_KEYS_HASHES` | `test` | `POST /v1/gateway/chat`, `POST /v1/telescope/stress/run` |
| **Token de Administrador** | `ALLOWED_ADMIN_API_KEYS_HASHES` | `admin123` | `/v1/notifications/*`, `/v1/audit/*`, `/v1/gateway/reset-vault` |

---

## Referencia de la API

### 1. Proxy de Chat Perimetral

#### `POST /v1/gateway/chat`
* **Autenticación:** `Authorization: Bearer <CLIENT_TOKEN>`
* **Cuerpo de la Petición:**
```json
{
  "user_id": "usr_001",
  "session_id": "ses_001",
  "message": "¿Cuál es el saldo actual de mi cuenta bancaria?",
  "bypass_gateway": false
}
```
* **Respuestas:**
  - `200 OK`: La petición superó todas las capas. Devuelve la respuesta sanitizada del LLM + telemetría.
  - `400 Bad Request`: Bloqueado en Ingress (Capas 1, 2 o 3). Devuelve la capa responsable + telemetría.
  - `401 Unauthorized`: Token de cliente ausente o inválido.
  - `500 Internal Server Error`: Violación de seguridad en salida / fuga detectada (Capa 5).

---

### 2. Observabilidad y Stress-Lab (Telescope)

| Método | Endpoint | Auth | Descripción |
|---|---|---|---|
| `GET` | `/v1/telescope/metrics` | Pública | Devuelve métricas rodantes en tiempo real, latencias P50/P95/Máx por capa y conteos HTTP. |
| `GET` | `/v1/telescope/history` | Pública | Devuelve el historial de los últimos 200 eventos procesados para la visualización del pipeline. |
| `POST` | `/v1/telescope/stress/run` | Cliente | Inicia una prueba de estrés asíncrona (usuarios, delay, iteraciones, proporción de tráfico). |
| `POST` | `/v1/telescope/stress/stop` | Cliente | Detiene y cancela la prueba de estrés actualmente en ejecución. |
| `GET` | `/v1/telescope/stress/status` | Pública | Devuelve el estado en vivo del benchmark: progreso, peticiones exitosas/fallidas y throughput. |

---

### 3. Notificaciones de Incidentes y Destinatarios SOC (Administrador)

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/v1/notifications/recipients` | Registra un nuevo oficial de seguridad o analista SOC. |
| `GET` | `/v1/notifications/recipients` | Lista todos los destinatarios (filtro opcional por `?active_only=true`). |
| `PATCH` | `/v1/notifications/recipients/{id}/toggle` | Activa o pausa las alertas por correo para un destinatario. |
| `PUT` | `/v1/notifications/recipients/{id}` | Actualiza los datos de un destinatario existente. |
| `DELETE` | `/v1/notifications/recipients/{id}` | Elimina permanentemente a un destinatario de la base de datos. |

---

### 4. Auditoría HITL y Dataset de Amenazas (Administrador)

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/v1/audit/records` | Consulta registros interceptados (`?reviewed=bool`, `?is_threat=bool`, paginación). |
| `POST` | `/v1/audit/{id}/review` | Envía la verificación humana del analista (`is_threat`, `threat_category`, `reviewed_by_ci`). |
| `GET` | `/v1/audit/export/seed` | Exporta amenazas confirmadas en formato JSON compatible con ChromaDB. |

---

## Especificaciones del Pipeline de Seguridad

| Capa | Nombre | Mecanismo | Latencia Típica | Resultado ante Amenaza |
|---|---|---|---|---|
| **L1** | Filtro Heurístico | Patrones Regex + Palabras prohibidas | < 1 ms | HTTP 400 |
| **L2** | Similitud Vectorial | Búsqueda coseno en ChromaDB (`all-MiniLM-L6-v2`) | 5 - 20 ms | HTTP 400 |
| **L3** | Clasificador IA | Transformer (`DeBERTa-v3` / Prompt Guard) | 25 - 60 ms | HTTP 400 + Auto-aprendizaje en ChromaDB |
| **L4** | Inyección de Canario | Token criptográfico de alta entropía en el prompt del sistema | < 1 ms | Reenvío transparente hacia el LLM |
| **L5** | Escáner de Salida (Egress) | Verificación del canario + Heurísticas de fuga | < 2 ms | HTTP 500 + Auto-aprendizaje en ChromaDB |

---

## Estructura del Proyecto

```
ai_gateway/
├── app/
│   ├── main.py                         # Fábrica de la aplicación FastAPI y ciclo de vida (lifespan)
│   ├── api/
│   │   ├── gateway.py                  # POST /v1/gateway/chat
│   │   ├── telescope.py                # Métricas de Telescope y runner de pruebas de estrés
│   │   ├── monitoring.py               # GET /health, POST /reset-vault
│   │   ├── notifications.py            # CRUD /v1/notifications/recipients
│   │   └── audit.py                    # GET /v1/audit/records, POST /review, exportación
│   ├── core/
│   │   ├── config.py                   # Configuración con Pydantic Settings
│   │   ├── security.py                 # Autenticación RBAC Bearer y generador de canario
│   │   ├── metrics.py                  # Recolector de métricas con percentiles deque
│   │   └── pipeline/
│   │       ├── manager.py              # Orquestador del pipeline de 5 capas
│   │       ├── layer_1_heuristics.py   # Filtro heurístico de regex y palabras clave
│   │       ├── layer_2_vectorial.py    # Búsqueda semántica en ChromaDB
│   │       ├── layer_3_intelligence.py # Clasificador IA DeBERTa-v3
│   │       ├── layer_4_canary.py       # Inyección del token canario
│   │       └── layer_5_egress.py       # Auditoría de salida y detección de fugas
│   ├── db/
│   │   ├── session.py                  # Sesión asíncrona de SQLAlchemy e inicialización de BD
│   │   └── models.py                   # Modelos ORM (users_notification, prompt_audit_dataset)
│   ├── services/
│   │   ├── vector_db.py                # Servicio de almacenamiento vectorial ChromaDB
│   │   ├── llm_client.py               # Cliente HTTP asíncrono para Groq Cloud con Mock fallback
│   │   └── email_notifier.py           # Servicio de alertas por correo vía Brevo SMTP
│   └── models/
│       ├── schemas.py                  # Esquemas Pydantic para peticiones y respuestas
│       └── schemas_admin.py            # Esquemas para administración, auditoría y notificaciones
├── frontend/                           # Interfaz Web
│   ├── index.html                      # Panel principal de chat e inspector de seguridad
│   ├── style.css                       # Hoja de estilos Slate/Charcoal con diseño zero-scroll
│   ├── app.js                          # Lógica de cliente, i18n y renderizado de telemetría
│   └── telescope/                      # Telescope & Stress-Lab
│       ├── index.html                  # Monitor Telescope e interfaz de estrés
│       ├── telescope.css               # Sistema de diseño de Telescope
│       └── telescope.js                # Pipeline animado, métricas y runner de carga
├── data/
│   └── seed_attacks.json               # Dataset semilla con firmas de inyecciones conocidas
├── sql/
│   └── create_tables.sql               # Esquema DDL de PostgreSQL con disparadores e índices
├── docs/                               # Documentación de ingeniería
│   ├── arquitectura.md                 # Diseño de arquitectura y flujo de datos
│   ├── especificacion_tecnica.md       # Especificación técnica detallada
│   ├── guia_de_uso.md                  # Guía de uso paso a paso y demostración
│   └── reporte_utilidad_ai_gateway.md  # Reporte estratégico de utilidad y ROI
├── tests/                              # Suite de pruebas automatizadas con Pytest
├── .env.example                        # Plantilla de variables de entorno
├── requirements.txt                    # Dependencias de Python
└── setup.sh                            # Script automatizado de configuración
```

---

## Ejecución de Pruebas Automatizadas

```bash
# Ejecutar la suite completa (47 pruebas)
pytest tests/ -v

# Ejecutar módulos de prueba específicos
pytest tests/test_e2e_gateway.py -v      # Pruebas End-to-End del chat proxy
pytest tests/test_pipeline_layers.py -v  # Pruebas aisladas del pipeline de 5 capas
pytest tests/test_telescope.py -v        # Pruebas de Telescope y Stress-Lab
pytest tests/test_notifications.py -v    # Pruebas de notificaciones SOC y RBAC
pytest tests/test_audit.py -v            # Pruebas de dataset de auditoría y HITL
```

---

## Licencia

Este proyecto ha sido desarrollado como un proyecto de ingeniería y tesis académica bajo la Licencia MIT.
