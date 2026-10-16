"""
Cliente ligero para la API de Ollama (/api/chat), usado tanto para el
modelo atacante, como para el objetivo y el juez. Los tres roles pueden
apuntar a modelos y HOSTS distintos, lo que permite, por ejemplo, tener
el objetivo en un entorno remoto y el atacante/juez en local.
"""
import httpx

from .config import settings


class OllamaError(RuntimeError):
    pass


async def chat(
    host: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.8,
    json_mode: bool = False,
) -> str:
    """
    Envía una conversación al endpoint /api/chat de Ollama y devuelve el
    texto de la respuesta. `messages` sigue el formato estándar
    [{"role": "system"|"user"|"assistant", "content": "..."}].

    Si `json_mode` es True, se activa el modo de salida estructurada de
    Ollama (decodificación restringida a JSON válido): el modelo no puede
    generar texto que no sea JSON, ni aunque el prompt no se siga al pie
    de la letra. Esto es mucho más fiable que solo pedirlo por prompt,
    especialmente con modelos pequeños (3B) que a veces ignoran el
    formato solicitado. Se usa para las llamadas al modelo JUEZ.
    """
    url = host.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_request_timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise OllamaError(f"Error comunicando con Ollama en {url}: {exc}") from exc

    try:
        return data["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise OllamaError(f"Respuesta inesperada de Ollama: {data}") from exc
