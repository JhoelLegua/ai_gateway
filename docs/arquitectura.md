### 1. Arquitectura del Proyecto

La estructura sigue el patrón de **Clean Architecture** adaptada para microservicios ligeros en Python.

```text
ai-gateway-perimetral/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Punto de entrada FastAPI + Config Scalar
│   ├── api/                    # Definición de Endpoints
│   │   ├── __init__.py
│   │   ├── gateway.py          # /v1/gateway/chat
│   │   └── monitoring.py       # /v1/gateway/health y /v1/gateway/reset
│   ├── core/                   # El "Cerebro" del Gateway
│   │   ├── __init__.py
│   │   ├── config.py           # Gestión de variables de entorno (.env)
│   │   ├── security.py         # Generador de Tokens Canario
│   │   └── pipeline/           # Implementación de las 5 Capas
│   │       ├── __init__.py
│   │       ├── manager.py      # Orquestador del flujo Ingress/Egress
│   │       ├── layer_1_heuristics.py
│   │       ├── layer_2_vectorial.py
│   │       ├── layer_3_intelligence.py
│   │       └── layer_5_egress.py
│   ├── services/               # Integraciones Externas
│   │   ├── __init__.py
│   │   ├── llm_client.py       # Cliente HTTPX asíncrono para el Agente LLM
│   │   └── vector_db.py        # Wrapper para ChromaDB
│   └── models/                 # Esquemas Pydantic (Request/Response)
│       ├── __init__.py
│       └── schemas.py
├── data/                       # Almacenamiento local de ChromaDB
├── models_cache/               # Caché local para modelos ONNX/Hugging Face
├── tests/                      # Pruebas unitarias de inyección
├── .env                        # Variables de entorno reales (no subir)
├── .env.example                # Plantilla de configuración
├── requirements.txt            # Dependencias del proyecto
└── README.md
```

---

### 2. Archivo: `.env.example`

Este archivo define las configuraciones necesarias para que el Gateway se comunique con el modelo principal y gestione sus umbrales de seguridad.

```bash
# Configuración del Servidor Gateway
APP_NAME="AI-Gateway-Perimetral"
APP_ENV=development
HOST=0.0.0.0
PORT=8000

# URL del Agente LLM / Backend Real (A donde se reenvía el prompt seguro)
BACKEND_LLM_URL="http://localhost:8080/v1/chat"
BACKEND_API_KEY="sk-tu-api-key-aqui"

# Configuración de Seguridad - Capa 2 (Vectorial)
VECTOR_DB_PATH="./data/gateway_vector_db"
SIMILARITY_THRESHOLD=0.15

# Configuración de Seguridad - Capa 3 (AI Classifier)
# Modelos sugeridos: meta-llama/Prompt-Guard-86M-v1 o protectai/distilroberta-base-prompt-injection
PROMPT_GUARD_MODEL="protectai/distilroberta-base-prompt-injection"

# Configuración de Seguridad - Capa 4/5 (Canario)
CANARY_PREFIX="BnkCanary_"

# Caché de Modelos
HF_HOME="./models_cache"
```

---

### 3. Archivo: `requirements.txt`

Las librerías están seleccionadas para garantizar el soporte **asíncrono** y el procesamiento **In-Memory**.

```text
# Web Server y API
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
scalar-fastapi>=1.0.0      # Motor de documentación interactiva
python-dotenv>=1.0.0
pydantic-settings>=2.1.0

# Seguridad y Detección
llm-guard>=0.3.0           # Framework principal de seguridad para LLMs
chromadb>=0.4.22           # Base de datos vectorial embebida
sentence-transformers>=2.3.0 # Para generación de embeddings locales
httpx>=0.26.0              # Cliente HTTP asíncrono

# Procesamiento de IA (Optimizado para CPU)
onnx>=1.15.0
onnxruntime>=1.17.0
torch --index-url https://download.pytorch.org/whl/cpu # Solo versión CPU para ligereza
transformers>=4.37.0

# Utilidades
python-multipart>=0.0.9
secrets>=1.0.2
```

### Notas adicionales sobre el despliegue:
*   **Scalar:** En `main.py`, se configurará para que al acceder a `/docs` se renderice la interfaz de Scalar consumiendo el JSON generado por FastAPI en `/openapi.json`.
*   **Modelos ONNX:** La primera vez que se ejecute el Gateway con `llm-guard`, este descargará automáticamente los modelos a la carpeta `models_cache`. Es recomendable tener al menos 2GB de RAM libres para el "calentamiento" inicial.
*   **ChromaDB:** Se configura en modo persistente apuntando a `./data/` para que los ataques detectados no se pierdan al reiniciar el servidor.