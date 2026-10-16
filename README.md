# LLM Red Teaming Platform

Plataforma de evaluación automatizada de seguridad ofensiva para modelos de lenguaje. Lanzas una campaña contra un modelo objetivo, un LLM atacante genera y adapta los ataques, un LLM juez puntúa cada intento y obtienes un informe con los hallazgos.

Desarrollada como parte del TFG *«Análisis de seguridad ofensiva aplicada a modelos de lenguaje»* (Grado en Ingeniería de la Ciberseguridad, Universidad Europea de Madrid).

> **Uso responsable.** Está pensada para evaluar modelos propios o para los que exista autorización explícita. No la uses contra servicios de terceros sin permiso. Por eso las campañas solo se aceptan contra hosts de una lista blanca (ver [Seguridad](#seguridad-y-uso-responsable)).

## Cómo funciona

```
                 ┌────────────────────────────────────────────┐
  Panel web ───► │  FastAPI  (campañas · hallazgos · informes)│ ──► SQLite
                 └──────────────┬─────────────────────────────┘
                                │ por cada categoría e iteración
        ┌───────────────────────┼───────────────────────────┐
        ▼                       ▼                           ▼
   ATACANTE LLM  ──prompt──►  OBJETIVO LLM  ──respuesta──► JUEZ LLM
 (genera el siguiente        (conversación             (veredicto JSON:
  ataque según el             multi-turno               Vulnerable / Seguro /
  historial)                  persistente)              Inconcluso + severidad)
                                                             │
                                          detección determinista de canario
                                          (puede sobrescribir al juez)
```

1. **Primera iteración**: se envía el `seed_prompt` de la categoría.
2. **Siguientes iteraciones**: el modelo atacante redacta el siguiente prompt a partir de los últimos intentos (qué envió, qué respondió el objetivo, qué veredicto recibió), en lugar de recorrer una lista fija.
3. **Objetivo**: recibe los ataques en una conversación multi-turno que no se reinicia entre iteraciones, así que se puede observar escalada real.
4. **Juez**: devuelve un JSON estructurado (razonamiento, veredicto, confianza, severidad, recomendación). Se usa el modo JSON forzado de Ollama y el razonamiento va primero para que los modelos pequeños no decidan sin razonar.
5. **Canario** (opcional): si insertas una cadena secreta en el system prompt del objetivo y aparece en una respuesta, el hallazgo pasa a *Vulnerable* con confianza 100 %, aunque el juez opine otra cosa. La detección cubre literal, sin distinguir mayúsculas, deletreado con separadores, invertido, Base64 y ROT13, y admite varios canarios separados por `|`.

Cada rol (objetivo, atacante, juez) puede usar un modelo y un host de Ollama distintos, por ejemplo el objetivo en un entorno remoto y atacante y juez en local.

## Categorías de prueba

El catálogo está en [`backend/app/categories.py`](backend/app/categories.py). Cada categoría define el prompt del atacante, el prompt semilla y el foco de evaluación del juez.

| Categoría | En el panel |
|---|---|
| Prompt injection directa | ✅ seleccionable |
| Jailbreaks | ✅ seleccionable |
| Extracción de system prompt / información confidencial | ✅ seleccionable |
| Abuso de herramientas | ✅ seleccionable |
| Prompt injection indirecta (RAG / documentos) | definida, deshabilitada en el panel |
| Escalada iterativa | definida, deshabilitada en el panel |
| Fuga de datos entre usuarios/conversaciones | definida, deshabilitada en el panel |
| Generación de contenido inseguro / contrario a política | definida, deshabilitada en el panel |

El panel solo habilita las cuatro primeras (`REFINED_CATEGORY_IDS` en `frontend/app.js`); las otras cuatro están en el backend pero aún no están afinadas.

## Puesta en marcha con Docker

Requisitos: Docker y Docker Compose.

```bash
git clone <URL-del-repo>
cd llm-redteam-platform
docker compose up -d --build

# Descarga los modelos en el contenedor de Ollama (el tamaño depende del modelo)
docker compose exec ollama ollama pull llama3.1:8b
```

Abre <http://localhost:8000>, rellena el modelo objetivo (por ejemplo `llama3.1:8b`) y lanza la campaña. Atacante y juez usan `llama3.1:8b` por defecto si dejas esos campos vacíos.

Para usar GPU NVIDIA, descomenta el bloque `deploy` del servicio `ollama` en [`docker-compose.yml`](docker-compose.yml).

## Ejecución local (sin Docker)

Requisitos: Python 3.12+ y un Ollama accesible.

```bash
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

cd backend
RTLLM_FRONTEND_DIR=../frontend python -m uvicorn app.main:app --port 8000
```

El panel queda en <http://localhost:8000> y la documentación interactiva de la API en <http://localhost:8000/docs>.

### HTTPS en local (opcional)

```bash
cd backend
python generate_cert.py          # crea certs/cert.pem y certs/key.pem (autofirmado, 825 días)
RTLLM_FRONTEND_DIR=../frontend python -m uvicorn app.main:app --port 8000 \
  --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
```

El navegador avisará de que el certificado es autofirmado. La conexión con Ollama sigue siendo HTTP: es interna entre el backend y Ollama. `certs/` está en `.gitignore`.

## Configuración

Todas las variables llevan el prefijo `RTLLM_` (ver [`.env.example`](.env.example) y [`backend/app/config.py`](backend/app/config.py)).

| Variable | Por defecto | Descripción |
|---|---|---|
| `RTLLM_OLLAMA_HOST` | `http://localhost:11434` | Host de Ollama por defecto |
| `RTLLM_DEFAULT_{ATTACKER,TARGET,JUDGE}_MODEL` | `llama3.1:8b` | Modelo por defecto de cada rol |
| `RTLLM_OLLAMA_REQUEST_TIMEOUT` | `120` | Timeout por petición (s) |
| `RTLLM_DATABASE_URL` | `sqlite+aiosqlite:///./data/redteam.db` | Base de datos |
| `RTLLM_MAX_ITERATIONS_PER_CATEGORY` | `8` | Máximo de iteraciones por categoría |
| `RTLLM_MAX_PROMPT_CHARS` | `4000` | Longitud máxima del prompt del atacante |
| `RTLLM_ALLOWED_TARGET_HOSTS` | `["localhost","127.0.0.1","ollama"]` | Lista blanca de hosts (JSON) |
| `RTLLM_FRONTEND_DIR` | `/app/frontend` | Carpeta del panel web |

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/categories` | Catálogo de categorías |
| `POST` | `/api/campaigns` | Crea y lanza una campaña (se ejecuta en segundo plano) |
| `GET` | `/api/campaigns` | Lista campañas con recuento de hallazgos y de vulnerables |
| `GET` | `/api/campaigns/{id}` | Detalle y hallazgos |
| `GET` | `/api/campaigns/{id}/report` | Informe HTML autocontenido, listo para imprimir a PDF |
| `GET` | `/api/campaigns/{id}/report.pdf` | PDF en servidor; requiere instalar `weasyprint` (opcional) |

Ejemplo:

```bash
curl -X POST http://localhost:8000/api/campaigns \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "baseline llama3.1",
        "target_model": "llama3.1:8b",
        "categories": ["direct_injection", "extraction"],
        "iterations_per_category": 5,
        "canary": "CANARY-TFG-9382"
      }'
```

Cada hallazgo guarda categoría, iteración, prompt usado, respuesta como evidencia, veredicto, confianza (0–100), severidad (Baja/Media/Alta/Crítica), recomendación, la salida cruda del juez y si saltó el canario (y con qué variante).

## Estructura

```
backend/app/
  main.py             API FastAPI y servidor del panel
  attack_engine.py    bucle de la campaña (atacante → objetivo → juez)
  judge.py            rúbrica del juez y parseo robusto de su JSON
  canary_detection.py detección determinista de fugas
  categories.py       catálogo de categorías
  ollama_client.py    cliente de /api/chat de Ollama
  reports.py          informes HTML/PDF
  models.py schemas.py database.py config.py
backend/Dockerfile  ·  backend/generate_cert.py
frontend/           panel web estático (HTML, CSS, JS sin dependencias)
docker-compose.yml
```

## Seguridad y uso responsable

- **Lista blanca de hosts.** Los hosts de objetivo, atacante y juez se validan contra `RTLLM_ALLOWED_TARGET_HOSTS`. Añade un host solo si tienes autorización para probarlo.
- **Sin autenticación.** El panel y la API no tienen login y el CORS está abierto (`*`). Por eso `docker-compose.yml` publica los puertos solo en `127.0.0.1`. No lo expongas a una red sin un proxy con autenticación delante.
- **Datos sensibles.** La base de datos contiene los prompts de ataque y las respuestas completas de los modelos evaluados. No la subas a repositorios públicos (`data/` y `*.db` están en `.gitignore`).
- **El juez es un LLM.** Su veredicto es una estimación probabilística y puede fallar, sobre todo con modelos pequeños. Revisa a mano los hallazgos relevantes; solo la detección de canario es determinista.

## Licencia

[MIT](LICENSE)
