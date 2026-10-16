import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class CampaignStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Verdict(str, enum.Enum):
    VULNERABLE = "Vulnerable"
    SAFE = "Seguro"
    INCONCLUSIVE = "Inconcluso"


class Severity(str, enum.Enum):
    LOW = "Baja"
    MEDIUM = "Media"
    HIGH = "Alta"
    CRITICAL = "Crítica"


class Campaign(Base):
    """
    Una campaña agrupa toda la ejecución de pruebas contra un modelo
    objetivo concreto: qué categorías se lanzan, cuántas iteraciones,
    con qué modelos (atacante / objetivo / juez) y en qué host de Ollama
    vive cada uno (pueden ser hosts distintos, por ejemplo si el
    objetivo vive en un entorno remoto y el atacante/juez en local).
    """

    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)

    target_model: Mapped[str] = mapped_column(String, nullable=False)
    target_host: Mapped[str] = mapped_column(String, nullable=False)
    attacker_model: Mapped[str] = mapped_column(String, nullable=False)
    attacker_host: Mapped[str] = mapped_column(String, nullable=False)
    judge_model: Mapped[str] = mapped_column(String, nullable=False)
    judge_host: Mapped[str] = mapped_column(String, nullable=False)

    categories: Mapped[list] = mapped_column(JSON, default=list)
    iterations_per_category: Mapped[int] = mapped_column(Integer, default=5)
    risk_level: Mapped[str] = mapped_column(String, default="medio")
    canary: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    findings: Mapped[list["Finding"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class Finding(Base):
    """
    Cada fila representa un intento individual (un prompt lanzado y su
    resultado). Coincide con la tabla de hallazgos propuesta en la
    memoria del TFG: categoría, prompt, respuesta, resultado,
    confianza, severidad y recomendación.
    """

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    category: Mapped[str] = mapped_column(String, nullable=False)
    iteration: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_used: Mapped[str] = mapped_column(Text, nullable=False)
    response_evidence: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[Verdict] = mapped_column(Enum(Verdict), default=Verdict.INCONCLUSIVE)
    confidence: Mapped[float] = mapped_column(Integer, default=0)  # 0-100
    severity: Mapped[Severity] = mapped_column(Enum(Severity), default=Severity.LOW)
    recommendation: Mapped[str] = mapped_column(Text, default="")
    judge_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    canary_hit: Mapped[bool] = mapped_column(default=False)
    canary_variant: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="findings")
