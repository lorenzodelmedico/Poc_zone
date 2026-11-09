"""Vérifier les fichiers locaux sans afficher les valeurs de configuration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.errors import AppError
from app.charts import load_chart_catalog
from app.metadata import load_metadata
from app.settings import ROOT, load_settings


def main():
    try:
        settings = load_settings()
        load_metadata(settings.metadata_path)
        load_chart_catalog()
        settings.check_live()
        print("Configuration locale : OK (structure et champs obligatoires uniquement).")
        print("Aucune connexion réseau, aucun accès LLM et aucune requête BDD n'ont été testés.")
        if settings.db_token_mode == "custom":
            print("DB_TOKEN_MODE=custom : adaptation de app/database.py nécessaire avant utilisation.")
        if not (ROOT / "frontend/vendor/echarts.min.js").is_file():
            print("ECharts : absent ; exécuter scripts/install_echarts.py avant les graphiques.")
    except AppError as exc:
        print(f"{exc.code}: {exc.message}")
        raise SystemExit(1) from None
    except (ValueError, OSError):
        print("Configuration invalide : vérifier les valeurs numériques et les fichiers.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
