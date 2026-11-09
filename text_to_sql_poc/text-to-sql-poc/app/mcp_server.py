"""Serveur MCP réel sur stdio ; stdout réservé au protocole."""
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.charts import load_chart_catalog
from app.metadata import load_metadata
from app.settings import ROOT

mcp = FastMCP("metadata-text-to-sql")


@mcp.tool()
def get_view_metadata() -> dict:
    """Retourner la seule vue autorisée, ses colonnes, types et règles métier."""
    path = Path(os.getenv("METADATA_PATH", "config/metadata.local.json"))
    return load_metadata(path if path.is_absolute() else ROOT / path)


@mcp.tool()
def get_chart_catalog() -> dict:
    """Retourner les fiches ECharts : descriptions, exemples, besoins en données et sources officielles."""
    return load_chart_catalog()


if __name__ == "__main__":
    mcp.run(transport="stdio")
