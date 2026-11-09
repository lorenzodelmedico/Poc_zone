import json
import re
from pathlib import Path

from app.errors import AppError

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
AGGREGATIONS = {"SUM", "AVG", "MIN", "MAX", "COUNT"}


def load_metadata(path: Path) -> dict:
    def require(condition):
        if not condition:
            raise ValueError("Invalid metadata")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        view = data["view"]
        require(isinstance(view, dict))
        for key in ("schema", "name"):
            require(IDENTIFIER.fullmatch(view[key]))
        require(isinstance(view["grain"], str) and view["grain"].strip())
        require(isinstance(view["description"], str))
        columns = data["columns"]
        require(isinstance(columns, list) and columns)
        names = set()
        for col in columns:
            require(IDENTIFIER.fullmatch(col["name"]))
            require(col["name"] not in names)
            names.add(col["name"])
            require(col["role"] in {"dimension", "measure"})
            require(isinstance(col["type"], str) and col["type"])
            require(isinstance(col["description"], str))
            require(isinstance(col.get("allowed_aggregations", []), list))
            require(set(col.get("allowed_aggregations", [])) <= AGGREGATIONS)
        require(any(c["role"] == "dimension" for c in columns))
        require(isinstance(data.get("business_rules", []), list))
        require(all(isinstance(rule, str) for rule in data.get("business_rules", [])))
        require(isinstance(data.get("allow_count_rows", False), bool))
        return data
    except (OSError, ValueError, KeyError, TypeError):
        raise AppError("METADATA_INVALID", "Métadonnées absentes ou invalides ; vérifier METADATA_PATH et le JSON.") from None
