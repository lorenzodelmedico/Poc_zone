"""Catalogue documenté et contrat de sélection ; aucun appel LLM supplémentaire."""
import json
from pathlib import Path

from app.errors import AppError
from app.settings import ROOT

RENDERERS = {"bar": {"series_type": "bar", "x_axis_type": "category", "y_axis_type": "value"},
             "line": {"series_type": "line", "x_axis_type": "time", "y_axis_type": "value"}}


def load_chart_catalog(path: Path | None = None):
    try:
        data = json.loads((path or ROOT / "config/chart_catalog.json").read_text(encoding="utf-8"))
        if not isinstance(data["catalog_version"], str) or not isinstance(data["policy"], str):
            raise ValueError
        if not isinstance(data["charts"], list) or len(data["charts"]) != len(RENDERERS):
            raise ValueError
        ids = set()
        for card in data["charts"]:
            identifier = card["id"]
            if not isinstance(identifier, str) or identifier not in RENDERERS or identifier in ids:
                raise ValueError
            ids.add(identifier)
            if card["echarts"] != RENDERERS[identifier]:
                raise ValueError
            for name in ("label", "description"):
                if not isinstance(card[name], str) or not card[name].strip():
                    raise ValueError
            for name in ("use_when", "avoid_when", "examples", "sources"):
                if not isinstance(card[name], list) or not card[name] or not all(isinstance(v, str) and v.strip() for v in card[name]):
                    raise ValueError
            if not all(url.startswith("https://echarts.apache.org/handbook/") for url in card["sources"]):
                raise ValueError
            requirements = card["data_requirements"]
            if (not isinstance(requirements["x"], str) or not isinstance(requirements["y"], str)
                    or requirements["single_series"] is not True):
                raise ValueError
        return data
    except (OSError, ValueError, KeyError, TypeError):
        raise AppError("CHART_CATALOG_INVALID", "Catalogue de graphiques absent ou invalide : config/chart_catalog.json.") from None


def check_chart_choice(selection):
    if not isinstance(selection, dict) or set(selection) != {"id", "reason", "x_label", "y_label"}:
        raise ValueError("Invalid chart choice")
    for key, size in {"id": 40, "reason": 400, "x_label": 80, "y_label": 80}.items():
        value = selection[key]
        if not isinstance(value, str) or not value.strip() or len(value) > size:
            raise ValueError("Invalid chart field")


def resolve_chart(selection, catalog):
    try:
        check_chart_choice(selection)
    except ValueError:
        raise AppError("LLM_CHART_FORMAT", "La sélection du graphique ne respecte pas le contrat attendu.", 502) from None
    card = next((item for item in catalog["charts"] if item["id"] == selection["id"]), None)
    if card is None or card["id"] not in RENDERERS:
        raise AppError("CHART_UNKNOWN", "Le modèle a sélectionné un graphique hors du catalogue autorisé.", 422)
    # Seule la configuration serveur contrôlée est transmise au moteur de rendu.
    return {"id": card["id"], "label": card["label"], "type": RENDERERS[card["id"]]["series_type"],
            "x_axis_type": RENDERERS[card["id"]]["x_axis_type"], "x_field": "x", "y_field": "y",
            "reason": selection["reason"], "x_label": selection["x_label"], "y_label": selection["y_label"]}
