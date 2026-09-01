# ⚙️ Especificación Técnica de Ingeniería: AI Gateway Perimetral

Este documento detalla los requerimientos, la especificación de interfaces de programación (API), el comportamiento de cada capa del pipeline, la arquitectura del dashboard de observabilidad **Telescope & Stress-Lab** y las matrices de decisión técnica.

---

## 1. Stack Tecnológico y Componentes

| Categoría | Tecnología | Rol en la Arquitectura |
|---|---|---|
| **Runtime** | Python 3.10+ | Tipado estricto con Pydantic v2 y soporte asíncrono nativo (`asyncio`). |
| **Framework Web** | FastAPI + Uvicorn | Servidor ASGI asíncrono con `lifespan` context manager y pooling HTTP. |
| **Base de Datos Relacional** | PostgreSQL (`asyncpg` + `SQLAlchemy 2.0`) | Almacén persistente de auditoría HITL y destinatarios de alertas SOC. |
| **Base de Datos Vectorial** | ChromaDB (persistente) | Almacenamiento local de firmas vectoriales de ataques conocidos. |
| **Modelo de Clasificación** | `deepset/deberta-v3-base-injection` | Inferencia Transformer para detección de intenciones de ataque en CPU. |
| **Modelo de Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | Vectorización semántica de texto en 384 dimensiones. |
| **Proveedor LLM** | Groq Cloud (`qwen/qwen3.8-27b` / `llama-3.3-70b`) | Inferencia de ultra-baja latencia con fallback determinístico Mock. |
| **Servicio de Alertas** | Brevo SMTP (`smtplib` + `asyncio.to_thread`) | Despacho asíncrono no bloqueante de reportes de incidentes a personal SOC. |
| **Documentación de API** | Scalar (`scalar-fastapi`) | Renderizado OpenAPI interactivo en `/docs`. |
| **Observabilidad & Estrés** | Telescope & Stress-Lab | Telemetría en tiempo real, percentiles P50/P95/Máx y generador de carga. |
| **Frontend Web** | HTML5 / Vanilla JS / CSS3 Moderno | UI responsive en 100vh sin scroll vertical, bilingüe (ES/EN) y temas claros/oscuros. |

---

## 2. Especificación de Endpoints

### 2.1. Endpoints de Chat Perimetral (Client Token)

#### `POST /v1/gateway/chat`
* **Header:** `Authorization: Bearer <CLIENT_TOKEN>`
* **Request:**
  ```json
  {
    "user_id": "usr_001",
    "session_id": "ses_001",
    "message": "¿Cuáles son los requisitos para abrir una cuenta?",
    "bypass_gateway": false
  }
  ```
* **Códigos de Respuesta:**
  - `200 OK`: Petición limpia y respuesta del LLM auditada con `canary_verified: true` y telemetría por capa.
  - `400 Bad Request`: Bloqueado en Ingress (Capas 1, 2 o 3). Devuelve `layer`, `reason`, `telemetry` y `total_latency_ms`.
  - `401 Unauthorized`: Token de cliente inválido o ausente.
  - `500 Internal Server Error`: Bloqueado en Egress (Capa 5 - Fuga de canario o contexto detectada).

---

### 2.2. Endpoints de Observabilidad y Stress-Lab (Telescope)

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/v1/telescope/metrics` | Pública | Métricas agregadas en vivo: P50, P95, Máx, Promedio por capa y conteo de estados HTTP. |
| `GET` | `/v1/telescope/history` | Pública | Lista rodante de los últimos 200 eventos de peticiones con desglose de latencia y estado. |
| `POST` | `/v1/telescope/stress/run` | Client | Inicia una prueba de estrés asíncrona parametrizable (usuarios concurrentes, delay, iteraciones, mix). |
| `POST` | `/v1/telescope/stress/stop` | Client | Cancela y detiene la prueba de estrés en ejecución. |
| `GET` | `/v1/telescope/stress/status` | Pública | Estado en vivo del benchmark: progreso, peticiones exitosas/fallidas, errores y throughput. |

---

### 2.3. Endpoints de Notificaciones y Equipo SOC (Admin Token)

* **Header:** `Authorization: Bearer <ADMIN_TOKEN>`

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/v1/notifications/recipients` | Registra un nuevo destinatario (`first_name`, `last_name`, `ci`, `email`, `role`, `is_active`). |
| `GET` | `/v1/notifications/recipients` | Lista todos los destinatarios (`?active_only=true` opcional). |
| `PATCH` | `/v1/notifications/recipients/{id}/toggle` | Invierte el estado `is_active` para silenciar o reactivar alertas. |
| `PUT` | `/v1/notifications/recipients/{id}` | Actualización parcial o total de datos del destinatario. |
| `DELETE` | `/v1/notifications/recipients/{id}` | Eliminación física del registro de la base de datos. |

---

### 2.4. Endpoints de Auditoría y Dataset HITL (Admin Token)

* **Header:** `Authorization: Bearer <ADMIN_TOKEN>`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/v1/audit/records` | Consulta registros de prompts interceptados (`?reviewed=bool`, `?is_threat=bool`, paginación). |
| `POST` | `/v1/audit/{id}/review` | Registra la validación humana de analista (`is_threat: bool`, `threat_category`, `reviewed_by_ci`). |
| `GET` | `/v1/audit/export/seed` | Exporta amenazas confirmadas (`reviewed=true` y `is_threat=true`) en formato JSON compatible con ChromaDB. |

---

### 2.5. Endpoints de Mantenimiento y UI

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/v1/gateway/health` | Pública | Métricas del sistema, recuento de firmas ChromaDB y estado de modelos. |
| `POST` | `/v1/gateway/reset-vault` | Admin | Limpia las firmas aprendidas en ChromaDB y restaura el dataset semilla. |
| `GET` | `/docs` | Pública | Documentación Scalar interactiva. |
| `GET` | `/app/` | Pública | Frontend web con chat, playground de ataques e inspector de seguridad. |
| `GET` | `/telescope` | Pública | Redirección a `/app/telescope/` para el monitor Telescope y Stress-Lab. |

---

## 3. Matriz de Decisiones y Respuestas por Capa

| Capa | Nombre | Condición de Activación | Acción y Salida |
|---|---|---|---|
| **L1** | Heurística | Coincidencia de Regex o palabras clave prohibidas. | HTTP 400. Alerta LOW en Brevo. |
| **L2** | Vectorial | Distancia coseno en ChromaDB < `SIMILARITY_THRESHOLD` (0.15). | HTTP 400. Alerta LOW en Brevo. |
| **L3** | Inteligencia IA | Inferencia DeBERTa con score > `INJECTION_SCORE_THRESHOLD` (0.75). | HTTP 400. Auto-aprende en ChromaDB. Alerta MEDIUM en Brevo. |
| **L4** | Canario | Inyección del token `BnkCanary_<hex>` en el system prompt antes de invocar al LLM. | Paso transparente hacia el LLM. |
| **L5** | Escáner Egress | Detección del token canario o patrones de fuga en la respuesta del LLM. | HTTP 500. Auto-aprende en ChromaDB. Alerta HIGH en Brevo. |

---

## 4. Motor de Pruebas de Carga y Métricas de Rendimiento (Stress-Lab)

El módulo Telescope incluye un runner asíncrono basado en `asyncio.create_task` y semáforos de concurrencia:

1. **Parámetros configurables:**
   - **Usuarios Concurrentes:** 1 a 50 clientes simultáneos.
   - **Tiempo entre Peticiones (Delay):** 0 a 3000 ms.
   - **Iteraciones / Bucles:** 1 a 20 repeticiones por usuario.
   - **Mix de Tráfico:** Proporción de tráfico benigno (prompts bancarios legítimos) vs. vectores de ataque (Inyecciones L1, L2, L3 y L5).

2. **Cálculo de Percentiles en Tiempo Real:**
   - Estructura `collections.deque(maxlen=10000)` para muestreo continuo de latencias sin degradación de memoria.
   - Cálculo instantáneo de **P50 (Mediana)**, **P95 (Cola de alta latencia)**, **Máximo** y **Promedio**.
   - Histograma de respuestas HTTP: `200 OK` (Pasan limpio), `400 Bad Request` (Bloqueados en Ingress), `500 Error` (Bloqueados en Egress).