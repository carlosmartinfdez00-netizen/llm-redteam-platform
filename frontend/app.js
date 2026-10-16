const API = "/api";
let selectedCampaignId = null;
let pollTimer = null;

// Categorías ya afinadas: se muestran marcadas y seleccionables. Las demás
// (aún sin desarrollar) se muestran sin marcar, deshabilitadas y en gris.
const REFINED_CATEGORY_IDS = new Set(["direct_injection", "extraction", "tool_abuse", "jailbreak"]);

async function api(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------
// Categorías
// ---------------------------------------------------------------------
async function loadCategories() {
  const categories = await api("/categories");
  const container = document.getElementById("categories-list");
  container.innerHTML = "";
  categories.forEach((cat) => {
    const refined = REFINED_CATEGORY_IDS.has(cat.id);
    const div = document.createElement("label");
    div.className = "category-item" + (refined ? "" : " category-item-disabled");
    div.innerHTML = `
      <input type="checkbox" name="category" value="${cat.id}" ${refined ? "checked" : "disabled"}>
      <span><strong>${cat.name}</strong><span class="cat-desc">${cat.description}</span></span>
    `;
    container.appendChild(div);
  });
}

// ---------------------------------------------------------------------
// Crear campaña
// ---------------------------------------------------------------------
document.getElementById("campaign-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const selectedCategories = Array.from(
    document.querySelectorAll('input[name="category"]:checked')
  ).map((el) => el.value);

  if (selectedCategories.length === 0) {
    alert("Selecciona al menos una categoría.");
    return;
  }

  const payload = {
    name: document.getElementById("name").value,
    target_model: document.getElementById("target_model").value,
    iterations_per_category: parseInt(document.getElementById("iterations").value, 10),
    categories: selectedCategories,
  };

  const targetHost = document.getElementById("target_host").value;
  if (targetHost) payload.target_host = targetHost;

  const attackerModel = document.getElementById("attacker_model").value;
  if (attackerModel) payload.attacker_model = attackerModel;
  const attackerHost = document.getElementById("attacker_host").value;
  if (attackerHost) payload.attacker_host = attackerHost;

  const judgeModel = document.getElementById("judge_model").value;
  if (judgeModel) payload.judge_model = judgeModel;
  const judgeHost = document.getElementById("judge_host").value;
  if (judgeHost) payload.judge_host = judgeHost;

  const canaryValue = document.getElementById("canary").value;
  if (canaryValue) payload.canary = canaryValue;

  try {
    const campaign = await api("/campaigns", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await loadCampaigns();
    selectCampaign(campaign.id);
  } catch (err) {
    alert("Error al crear la campaña: " + err.message);
  }
});

// ---------------------------------------------------------------------
// Listado de campañas (columna izquierda)
// ---------------------------------------------------------------------
function vulnBadge(campaign) {
  if (campaign.findings_count === 0) {
    return '<span class="vuln-pill vuln-pending">Sin datos</span>';
  }
  if (campaign.vulnerable_count > 0) {
    return `<span class="vuln-pill vuln-yes">Vulnerable (${campaign.vulnerable_count})</span>`;
  }
  return '<span class="vuln-pill vuln-no">Seguro</span>';
}

function modelsLine(campaign) {
  return `Objetivo: <strong>${campaign.target_model}</strong> · Atacante: <strong>${campaign.attacker_model}</strong> · Juez: <strong>${campaign.judge_model}</strong>`;
}

async function loadCampaigns() {
  const campaigns = await api("/campaigns");
  const container = document.getElementById("campaigns-list");
  container.innerHTML = "";
  if (campaigns.length === 0) {
    container.innerHTML = '<p class="form-note">Todavía no hay campañas.</p>';
    return;
  }
  campaigns.forEach((c) => {
    const row = document.createElement("div");
    row.className = "campaign-row" + (c.id === selectedCampaignId ? " selected" : "");
    row.innerHTML = `
      <div class="campaign-row-top">
        <strong>${c.name}</strong>
        <div class="badges">
          <span class="status-pill status-${c.status}">${c.status}</span>
          ${vulnBadge(c)}
        </div>
      </div>
      <div class="models-line">${modelsLine(c)}</div>
      <div class="form-note">${c.categories.length} categorías · ${new Date(c.created_at).toLocaleString()}</div>
    `;
    row.addEventListener("click", () => selectCampaign(c.id));
    container.appendChild(row);
  });
}

// ---------------------------------------------------------------------
// Detalle de campaña (columna derecha)
// ---------------------------------------------------------------------
function verdictCounts(findings) {
  const counts = {};
  findings.forEach((f) => (counts[f.verdict] = (counts[f.verdict] || 0) + 1));
  return counts;
}

async function selectCampaign(id) {
  selectedCampaignId = id;
  document.getElementById("detail-empty-state").style.display = "none";
  document.getElementById("detail-content").style.display = "block";
  await refreshDetail();
  await loadCampaigns(); // para resaltar la fila seleccionada

  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    if (!selectedCampaignId) return;
    const campaign = await api(`/campaigns/${selectedCampaignId}`);
    renderDetail(campaign);
    if (campaign.status !== "running" && campaign.status !== "pending") {
      clearInterval(pollTimer);
      await loadCampaigns();
    }
  }, 3000);
}

async function refreshDetail() {
  if (!selectedCampaignId) return;
  const campaign = await api(`/campaigns/${selectedCampaignId}`);
  renderDetail(campaign);
}

function renderDetail(campaign) {
  document.getElementById("detail-title").textContent = campaign.name;
  document.getElementById("report-link").href = `${API}/campaigns/${campaign.id}/report`;

  document.getElementById("detail-models").innerHTML = modelsLine(campaign);

  const counts = verdictCounts(campaign.findings);
  const summary = document.getElementById("detail-summary");
  summary.innerHTML = `
    <div class="stat-chip"><b>${campaign.status}</b>Estado</div>
    <div class="stat-chip"><b>${campaign.findings.length}</b>Hallazgos totales</div>
    <div class="stat-chip"><b class="verdict-Vulnerable">${counts["Vulnerable"] || 0}</b>Vulnerable</div>
    <div class="stat-chip"><b class="verdict-Seguro">${counts["Seguro"] || 0}</b>Seguro</div>
    <div class="stat-chip"><b class="verdict-Inconcluso">${counts["Inconcluso"] || 0}</b>Inconcluso</div>
  `;

  const container = document.getElementById("findings-table-container");
  if (campaign.findings.length === 0) {
    container.innerHTML = '<p class="form-note">Aún no hay hallazgos (la campaña puede estar en curso).</p>';
    return;
  }
  const rows = campaign.findings
    .map(
      (f) => `
      <tr>
        <td>${f.category}</td>
        <td>${f.iteration}</td>
        <td class="mono">${escapeHtml(f.prompt_used)}</td>
        <td class="mono">${escapeHtml(f.response_evidence)}</td>
        <td class="verdict-${f.verdict}">${f.verdict}${f.canary_hit ? ` 🐤 (${f.canary_variant})` : ""}</td>
        <td>${Math.round(f.confidence)}%</td>
        <td>${f.severity}</td>
        <td>${escapeHtml(f.recommendation)}</td>
      </tr>`
    )
    .join("");
  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Categoría</th><th>#</th><th>Prompt</th><th>Evidencia</th>
          <th>Resultado</th><th>Confianza</th><th>Severidad</th><th>Recomendación</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------
loadCategories();
loadCampaigns();
