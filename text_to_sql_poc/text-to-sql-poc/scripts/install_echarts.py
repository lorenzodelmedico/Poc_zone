"""Préparer les fichiers ECharts locaux, sans npm ni étape de build."""
import argparse
import io
import json
import ssl
import tarfile
from pathlib import Path
from urllib.request import urlopen

VERSION = "5.6.0"
URL = f"https://registry.npmjs.org/echarts/-/echarts-{VERSION}.tgz"
DEST = Path(__file__).resolve().parents[1] / "frontend" / "vendor"


def install(archive):
    files = {"package/dist/echarts.min.js": "echarts.min.js",
             "package/LICENSE": "ECHARTS_LICENSE", "package/NOTICE": "ECHARTS_NOTICE"}
    selected = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
        package_file = source.extractfile("package/package.json")
        package = json.loads(package_file.read(100_000)) if package_file else {}
        if package.get("name") != "echarts" or package.get("version") != VERSION:
            raise ValueError("Version ECharts inattendue.")
        # Lire uniquement les fichiers attendus ; aucune extraction de chemins.
        for member_name, filename in files.items():
            member = source.getmember(member_name)
            if not member.isfile() or member.size > 10_000_000:
                raise ValueError("Archive ECharts invalide.")
            selected[filename] = source.extractfile(member).read()
    DEST.mkdir(parents=True, exist_ok=True)
    for name, content in selected.items():
        (DEST / name).write_bytes(content)
    print(f"ECharts {VERSION} installé dans frontend/vendor.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--archive", type=Path, help="Archive npm echarts-5.6.0.tgz déjà approuvée.")
    group.add_argument("--download", action="store_true", help="Téléchargement explicite depuis le registre npm public.")
    parser.add_argument("--ca-bundle", help="Bundle CA PEM pour le téléchargement HTTPS.")
    args = parser.parse_args()
    try:
        if args.download:
            with urlopen(URL, timeout=60, context=ssl.create_default_context(cafile=args.ca_bundle)) as response:
                archive = response.read(30_000_001)
            if len(archive) > 30_000_000:
                raise ValueError("Archive trop volumineuse.")
        else:
            archive = args.archive.read_bytes()
        install(archive)
    except Exception as exc:
        raise SystemExit(f"Installation ECharts impossible ({type(exc).__name__}). Utiliser une archive npm approuvée.") from None


if __name__ == "__main__":
    main()
