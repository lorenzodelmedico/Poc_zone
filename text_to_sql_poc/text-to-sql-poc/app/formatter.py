import math
from datetime import date, datetime, timezone
from decimal import Decimal

from app.errors import AppError


def format_result(rows, chart_type):
    result = []
    for row in rows:
        x, y = row["x"], row["y"]
        if isinstance(x, (date, datetime)):
            x = x.isoformat()
        elif x is None:
            x = "(sans catégorie)"
        elif not isinstance(x, (str, int, float)) or isinstance(x, bool):
            raise AppError("RESULT_TYPE", "Type de dimension non pris en charge.", 422)
        if isinstance(x, float) and not math.isfinite(x):
            raise AppError("RESULT_TYPE", "Dimension non finie.", 422)
        if y is not None:
            if isinstance(y, bool) or not isinstance(y, (int, float, Decimal)):
                raise AppError("RESULT_TYPE", "La mesure y doit être numérique ou nulle.", 422)
            try:
                y = float(y)
            except (OverflowError, ValueError):
                raise AppError("RESULT_TYPE", "Valeur numérique non représentable.", 422) from None
            if not math.isfinite(y):
                raise AppError("RESULT_TYPE", "Valeur numérique non finie.", 422)
        result.append({"x": x, "y": y})
    if chart_type == "line":
        # Une courbe de ce POC est temporelle : dates ISO uniquement.
        try:
            for row in result:
                stamp = datetime.fromisoformat(str(row["x"]).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                row["x"] = stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            result.sort(key=lambda row: str(row["x"]))
        except (ValueError, OverflowError):
            raise AppError("CHART_INCOMPATIBLE", "La courbe sélectionnée attend une date valide en x. Préciser la dimension temporelle.", 422) from None
    return result
