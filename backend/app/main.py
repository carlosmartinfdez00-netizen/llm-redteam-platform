import os

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .attack_engine import run_campaign
from .categories import CATEGORIES
from .config import settings
from .database import AsyncSessionLocal, get_session, init_db
from .models import Campaign, Finding, Verdict
from .reports import build_html_report, try_build_pdf_report
from .schemas import CampaignCreate, CampaignDetail, CampaignOut, CategoryOut

app = FastAPI(
    title="LLM Red Teaming Platform",
    description=(
        "Plataforma de evaluación automatizada de seguridad para aplicaciones "
        "basadas en modelos de lenguaje. Proyecto desarrollado como ampliación "
        "del TFG 'Análisis de seguridad ofensiva aplicada a modelos de lenguaje'."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    await init_db()


# --------------------------------------------------------------------------
# Categorías
# --------------------------------------------------------------------------
@app.get("/api/categories", response_model=list[CategoryOut])
async def list_categories() -> list[CategoryOut]:
    return [
        CategoryOut(id=c.id, name=c.name, description=c.description)
        for c in CATEGORIES.values()
    ]


# --------------------------------------------------------------------------
# Campañas
# --------------------------------------------------------------------------
async def _execute_campaign_in_background(campaign_id: str) -> None:
    async with AsyncSessionLocal() as session:
        await run_campaign(campaign_id, session, settings.max_prompt_chars)


@app.post("/api/campaigns", response_model=CampaignOut)
async def create_campaign(
    payload: CampaignCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> Campaign:
    campaign = Campaign(
        name=payload.name,
        target_model=payload.target_model,
        target_host=payload.target_host,
        attacker_model=payload.attacker_model,
        attacker_host=payload.attacker_host or payload.target_host,
        judge_model=payload.judge_model,
        judge_host=payload.judge_host or payload.target_host,
        categories=payload.categories,
        iterations_per_category=payload.iterations_per_category,
        risk_level=payload.risk_level,
        canary=payload.canary,
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)

    background_tasks.add_task(_execute_campaign_in_background, campaign.id)
    return campaign


async def _with_findings_summary(session: AsyncSession, campaign: Campaign) -> CampaignOut:
    """Añade el recuento de hallazgos y de hallazgos 'Vulnerable' a una
    campaña, para poder mostrar el badge de vulnerabilidad en la lista sin
    tener que cargar todos los hallazgos completos."""
    result = await session.execute(
        select(Finding.verdict, func.count(Finding.id))
        .where(Finding.campaign_id == campaign.id)
        .group_by(Finding.verdict)
    )
    counts = {row[0]: row[1] for row in result.all()}
    findings_count = sum(counts.values())
    vulnerable_count = counts.get(Verdict.VULNERABLE, 0)

    out = CampaignOut.model_validate(campaign)
    out.findings_count = findings_count
    out.vulnerable_count = vulnerable_count
    return out


@app.get("/api/campaigns", response_model=list[CampaignOut])
async def list_campaigns(session: AsyncSession = Depends(get_session)) -> list[CampaignOut]:
    result = await session.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    campaigns = list(result.scalars().all())
    return [await _with_findings_summary(session, c) for c in campaigns]


@app.get("/api/campaigns/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> Campaign:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    await session.refresh(campaign, attribute_names=["findings"])
    return campaign


@app.get("/api/campaigns/{campaign_id}/report", response_class=HTMLResponse)
async def get_campaign_report_html(
    campaign_id: str, session: AsyncSession = Depends(get_session)
) -> str:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    await session.refresh(campaign, attribute_names=["findings"])
    return build_html_report(campaign, campaign.findings)


@app.get("/api/campaigns/{campaign_id}/report.pdf")
async def get_campaign_report_pdf(
    campaign_id: str, session: AsyncSession = Depends(get_session)
) -> Response:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    await session.refresh(campaign, attribute_names=["findings"])
    html = build_html_report(campaign, campaign.findings)
    pdf_bytes = try_build_pdf_report(html)
    if pdf_bytes is None:
        raise HTTPException(
            status_code=501,
            detail=(
                "Generación de PDF en servidor no disponible (falta 'weasyprint'). "
                "Usa /api/campaigns/{id}/report y 'Imprimir a PDF' desde el navegador."
            ),
        )
    return Response(content=pdf_bytes, media_type="application/pdf")


# --------------------------------------------------------------------------
# Panel web estático
# --------------------------------------------------------------------------
if os.path.isdir(settings.frontend_dir):
    app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
