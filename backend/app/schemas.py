from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from .categories import CATEGORY_IDS
from .config import settings


def _validate_host(value: str) -> str:
    host = urlparse(value).hostname or value
    if host not in settings.allowed_target_hosts:
        raise ValueError(
            "El host no está en la lista de hosts autorizados "
            f"({settings.allowed_target_hosts}). Añádelo explícitamente en "
            "la configuración (RTLLM_ALLOWED_TARGET_HOSTS) solo si tienes "
            "autorización para probarlo."
        )
    return value


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)

    target_model: str
    target_host: str = settings.ollama_host
    attacker_model: str = settings.default_attacker_model
    attacker_host: str | None = Field(
        default=None,
        description="Host de Ollama para el modelo atacante. Si se omite, se usa target_host.",
    )
    judge_model: str = settings.default_judge_model
    judge_host: str | None = Field(
        default=None,
        description="Host de Ollama para el modelo juez. Si se omite, se usa target_host.",
    )

    categories: list[str] = Field(default_factory=lambda: list(CATEGORY_IDS))
    iterations_per_category: int = Field(default=5, ge=1, le=settings.max_iterations_per_category)
    risk_level: str = Field(default="medio", pattern="^(bajo|medio|alto)$")
    canary: str | None = Field(
        default=None,
        description=(
            "Cadena secreta insertada en el system prompt del objetivo (p. ej. un "
            "código canario, o una línea TOOL_CALL prohibida). Varios valores se "
            "pueden separar con '|'. Si aparece (literal u ofuscado) en una "
            "respuesta, el hallazgo se marca automáticamente como Vulnerable con "
            "confianza 100%, independientemente del veredicto del juez."
        ),
    )

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, value: list[str]) -> list[str]:
        unknown = set(value) - set(CATEGORY_IDS)
        if unknown:
            raise ValueError(f"Categorías desconocidas: {sorted(unknown)}")
        if not value:
            raise ValueError("Debe seleccionarse al menos una categoría")
        return value

    @field_validator("target_host")
    @classmethod
    def validate_target_host(cls, value: str) -> str:
        return _validate_host(value)

    @field_validator("attacker_host")
    @classmethod
    def validate_attacker_host(cls, value: str | None) -> str | None:
        return _validate_host(value) if value else value

    @field_validator("judge_host")
    @classmethod
    def validate_judge_host(cls, value: str | None) -> str | None:
        return _validate_host(value) if value else value


class FindingOut(BaseModel):
    id: str
    category: str
    iteration: int
    prompt_used: str
    response_evidence: str
    verdict: str
    confidence: float
    severity: str
    recommendation: str
    canary_hit: bool
    canary_variant: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignOut(BaseModel):
    id: str
    name: str
    target_model: str
    target_host: str
    attacker_model: str
    attacker_host: str
    judge_model: str
    judge_host: str
    categories: list[str]
    iterations_per_category: int
    canary: str | None
    status: str
    created_at: datetime
    finished_at: datetime | None
    error_message: str | None
    # Resumen agregado para la vista de lista, calculado por el backend
    # (no viene directamente del ORM: ver main.py).
    findings_count: int = 0
    vulnerable_count: int = 0

    class Config:
        from_attributes = True


class CampaignDetail(CampaignOut):
    findings: list[FindingOut] = Field(default_factory=list)


class CategoryOut(BaseModel):
    id: str
    name: str
    description: str
