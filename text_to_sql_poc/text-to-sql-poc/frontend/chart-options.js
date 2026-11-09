/* Deux modèles fixes. Les données et la sélection contrôlée viennent du serveur. */
"use strict";

function buildChartOption(chart, rows) {
  const expectedAxes = { bar: "category", line: "time" };
  if (!Object.hasOwn(expectedAxes, chart.type) || chart.x_axis_type !== expectedAxes[chart.type]) {
    throw new Error("Présentation retournée incompatible avec les modèles disponibles.");
  }
  return {
    tooltip: { trigger: "axis", renderMode: "richText" },
    grid: { left: 55, right: 25, top: 25, bottom: 65, containLabel: true },
    dataset: { dimensions: ["x", "y"], source: rows },
    xAxis: { type: expectedAxes[chart.type], name: chart.x_label, axisLabel: { hideOverlap: true } },
    yAxis: { type: "value", name: chart.y_label },
    series: [{ type: chart.type, encode: { x: "x", y: "y" }, connectNulls: false }]
  };
}

if (typeof module !== "undefined") module.exports = { buildChartOption };
