"""
Configuración global de la plataforma.

Todos los valores pueden sobreescribirse mediante variables de entorno,
lo que permite ejecutar el laboratorio tanto en local como dentro de
Docker Compose sin tocar el código.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Ollama ---
    # Nota: Ollama sirve su API en HTTP plano por defecto (no HTTPS), así que
    # este host debe seguir siendo http:// salvo que tu propio Ollama esté
    # detrás de un proxy con TLS. El HTTPS de "importante que quede en https"
    # se aplica al panel web (ver README/instrucciones de arranque con
    # --ssl-keyfile/--ssl-certfile), no a la conexión interna con Ollama.
    ollama_host: str = "http://localhost:11434"
    default_attacker_model: str = "llama3.1:8b"
    default_target_model: str = "llama3.1:8b"
    default_judge_model: str = "llama3.1:8b"
    ollama_request_timeout: float = 120.0

    # --- Base de datos ---
    database_url: str = "sqlite+aiosqlite:///./data/redteam.db"

    # --- Panel web estático ---
    # En Docker se sirve desde /app/frontend (ver docker-compose.yml).
    # En desarrollo local, ejecuta el backend desde la raíz del repo y
    # sobreescribe esta variable con RTLLM_FRONTEND_DIR=./frontend si hace falta.
    frontend_dir: str = "/app/frontend"

    # --- Motor de ataque ---
    max_iterations_per_category: int = 8
    max_prompt_chars: int = 4000

    # --- Seguridad / uso responsable ---
    # La herramienta solo debe apuntar a hosts explícitamente autorizados.
    # Se define aquí una lista blanca para evitar lanzar campañas contra
    # cualquier host de Ollama arbitrario que alguien pegue en el panel.
    # Se aplica a los tres roles (objetivo, atacante, juez), ya que ahora
    # cada uno puede apuntar a un host distinto.
    allowed_target_hosts: list[str] = ["localhost", "127.0.0.1", "ollama"]

    model_config = SettingsConfigDict(env_prefix="RTLLM_", env_file=".env", extra="ignore")


settings = Settings()
