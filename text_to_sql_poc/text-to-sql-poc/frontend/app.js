/* Le modèle sélectionne une fiche. Le rendu utilise uniquement des modèles fixes. */
"use strict";
const $ = (id) => document.getElementById(id);
let chart = null;

function clearResult() {
  $("result").hidden = true;
  $("rows").replaceChildren();
  $("assumptions").replaceChildren();
  $("sql").textContent = "";
  $("chart-choice").textContent = "";
  if (chart) chart.clear();
}

async function loadCatalog() {
  $("vendor-warning").hidden = !!window.echarts;
  try {
    const response = await fetch("/api/catalog");
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Métadonnées indisponibles.");
    $("view-info").textContent = data.view.description;
    $("submit").disabled = false;
  } catch (error) {
    $("message").textContent = error.message;
  }
}

$("query-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearResult();
  $("submit").disabled = true;
  $("message").textContent = "Analyse en cours…";
  try {
    const response = await fetch("/api/query", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: $("question").value.trim() })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Requête invalide ou traitement indisponible.");
    if (data.status !== "ok") {
      $("message").textContent = data.clarification_question || "La demande ne peut pas être traitée.";
      return;
    }
    $("message").textContent = data.row_count ? "Analyse terminée." : "Aucun résultat pour ces filtres.";
    $("result").hidden = false;
    $("summary").textContent = `${data.row_count} groupe(s) · Référence ${data.request_id}`;
    $("sql").textContent = data.sql;
    $("chart-choice").textContent = `Présentation automatique : ${data.chart.label}. ${data.chart.reason}`;
    $("x-label").textContent = data.chart.x_label;
    $("y-label").textContent = data.chart.y_label;
    for (const assumption of data.assumptions) {
      const li = document.createElement("li");
      li.textContent = assumption;
      $("assumptions").appendChild(li);
    }
    for (const row of data.rows) {
      const tr = document.createElement("tr");
      for (const value of [row.x, row.y]) {
        const td = document.createElement("td");
        td.textContent = value === null ? "—" : String(value);
        tr.appendChild(td);
      }
      $("rows").appendChild(tr);
    }
    $("chart").hidden = !window.echarts || !data.row_count;
    if (window.echarts && data.row_count) {
      chart = chart || window.echarts.init($("chart"));
      chart.setOption(buildChartOption(data.chart, data.rows), true);
      chart.resize();
    }
  } catch (error) {
    clearResult();
    $("message").textContent = error.message;
  } finally {
    $("submit").disabled = false;
  }
});
window.addEventListener("resize", () => { if (chart) chart.resize(); });
loadCatalog();
