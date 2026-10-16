"""
Generación de informes.

Se genera un informe HTML autocontenido a partir de los hallazgos de una
campaña, maquetado para imprimirse limpiamente como PDF desde el propio
navegador (Ctrl+P -> Guardar como PDF).
"""
from collections import Counter
from datetime import datetime

from jinja2 import Environment, BaseLoader, select_autoescape

from .models import Campaign, Finding

_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Informe de Red Teaming LLM - {{ campaign.name }}</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2.5rem; color: #1a1a1a; }
  h1 { font-size: 1.6rem; margin-bottom: 0.2rem; }
  .subtitle { color: #666; margin-bottom: 1.5rem; }
  .meta-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem 1.5rem; margin-bottom: 2rem; font-size: 0.9rem; }
  .meta-grid div span { display:block; color:#666; font-size:0.75rem; text-transform:uppercase; letter-spacing:.03em; }
  .summary { display:flex; gap:1rem; margin-bottom: 2rem; flex-wrap: wrap; }
  .stat { border:1px solid #e2e2e2; border-radius:8px; padding: 0.75rem 1.1rem; min-width: 120px; }
  .stat b { display:block; font-size:1.4rem; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 2rem; font-size: 0.85rem; }
  th, td { border: 1px solid #e2e2e2; padding: 0.5rem 0.6rem; text-align: left; vertical-align: top; }
  th { background: #f5f5f5; }
  .verdict-Vulnerable { color: #b3261e; font-weight: 600; }
  .verdict-Seguro { color: #1e7a34; font-weight: 600; }
  .verdict-Inconcluso { color: #a15c00; font-weight: 600; }
  .sev-Crítica, .sev-Alta { color: #b3261e; font-weight: 600; }
  .sev-Media { color: #a15c00; }
  .sev-Baja { color: #1e7a34; }
  .evidence, .prompt { white-space: pre-wrap; max-width: 340px; font-family: ui-monospace, monospace; font-size: 0.78rem; }
  .category-block { margin-bottom: 1.5rem; }
  .disclaimer { font-size: 0.75rem; color: #888; border-top: 1px solid #e2e2e2; padding-top: 1rem; margin-top: 2rem; }
  @media print { body { margin: 1cm; } }
</style>
</head>
<body>
  <h1>Informe de evaluación de seguridad ofensiva de LLM</h1>
  <div class="subtitle">Campaña: {{ campaign.name }} — generado el {{ generated_at }}</div>

  <div class="meta-grid">
    <div><span>Modelo objetivo</span>{{ campaign.target_model }} ({{ campaign.target_host }})</div>
    <div><span>Modelo atacante</span>{{ campaign.attacker_model }} ({{ campaign.attacker_host }})</div>
    <div><span>Modelo juez</span>{{ campaign.judge_model }} ({{ campaign.judge_host }})</div>
    <div><span>Iteraciones/categoría</span>{{ campaign.iterations_per_category }}</div>
    <div><span>Categorías evaluadas</span>{{ campaign.categories|length }}</div>
    <div><span>Estado</span>{{ campaign.status.value }}</div>
    <div><span>Total de hallazgos</span>{{ findings|length }}</div>
  </div>

  <div class="summary">
    {% for verdict, count in verdict_counts.items() %}
    <div class="stat"><b class="verdict-{{ verdict }}">{{ count }}</b>{{ verdict }}</div>
    {% endfor %}
    {% for sev, count in severity_counts.items() %}
    <div class="stat"><b class="sev-{{ sev }}">{{ count }}</b>Severidad {{ sev }}</div>
    {% endfor %}
  </div>

  {% for category, items in findings_by_category.items() %}
  <div class="category-block">
    <h2>{{ category }}</h2>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Prompt utilizado</th>
          <th>Evidencia (respuesta)</th>
          <th>Resultado</th>
          <th>Confianza</th>
          <th>Severidad</th>
          <th>Recomendación</th>
        </tr>
      </thead>
      <tbody>
        {% for f in items %}
        <tr>
          <td>{{ f.iteration }}</td>
          <td class="prompt">{{ f.prompt_used }}</td>
          <td class="evidence">{{ f.response_evidence }}</td>
          <td class="verdict-{{ f.verdict.value }}">{{ f.verdict.value }}{% if f.canary_hit %} 🐤 ({{ f.canary_variant }}){% endif %}</td>
          <td>{{ f.confidence|round(0)|int }}%</td>
          <td class="sev-{{ f.severity.value }}">{{ f.severity.value }}</td>
          <td>{{ f.recommendation }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endfor %}

  <div class="disclaimer">
    Informe generado automáticamente por la plataforma de evaluación de seguridad
    ofensiva de LLM desarrollada como parte del TFG "Análisis de seguridad ofensiva
    aplicada a modelos de lenguaje". Los hallazgos deben revisarse manualmente antes
    de tomar decisiones; el veredicto del modelo juez es una ayuda a la triaje, no un
    resultado certificado. Esta herramienta debe usarse únicamente sobre modelos
    propios o sistemas para los que se disponga de autorización explícita.
  </div>
</body>
</html>
"""

_env = Environment(loader=BaseLoader(), autoescape=select_autoescape(["html"]))
_template = _env.from_string(_TEMPLATE)


def build_html_report(campaign: Campaign, findings: list[Finding]) -> str:
    findings_by_category: dict[str, list[Finding]] = {}
    for f in findings:
        findings_by_category.setdefault(f.category, []).append(f)

    verdict_counts = Counter(f.verdict.value for f in findings)
    severity_counts = Counter(f.severity.value for f in findings)

    return _template.render(
        campaign=campaign,
        findings=findings,
        findings_by_category=findings_by_category,
        verdict_counts=verdict_counts,
        severity_counts=severity_counts,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


def try_build_pdf_report(html: str) -> bytes | None:
    """Intenta generar un PDF con weasyprint si está instalado. Devuelve
    None si la dependencia no está disponible."""
    try:
        from weasyprint import HTML  # type: ignore
    except ImportError:
        return None
    return HTML(string=html).write_pdf()
