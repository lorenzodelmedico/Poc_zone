"""Sous-ensemble SQL volontairement limité : une vue, un regroupement, une mesure."""
import re

from app.errors import AppError

# Liste positive : toute nouvelle construction nécessite une décision explicite.
ALLOWED_NODES = {
    "select", "from", "table", "identifier", "column", "alias", "where", "group",
    "order", "ordered", "limit", "literal", "boolean", "null", "and", "or", "not",
    "paren", "eq", "neq", "gt", "gte", "lt", "lte", "between", "in", "like", "ilike",
    "add", "sub", "mul", "div", "neg", "distinct", "star", "sum", "avg", "min", "max",
    "count", "coalesce", "nullif", "timestamptrunc", "datetrunc", "var", "cast", "datatype",
}


def reject(message):
    raise AppError("SQL_REJECTED", message, 422)


def identifier_value(identifier):
    if identifier is None:
        return ""
    return identifier.name if identifier.args.get("quoted") else identifier.name.lower()


def validate_sql(sql, metadata, max_rows=500, chart_id=None):
    import sqlglot
    from sqlglot import exp

    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.SqlglotError:
        reject("La requête n'est pas analysable en PostgreSQL.")
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        reject("Une seule instruction SELECT est autorisée.")
    root = statements[0]
    if any(node.key not in ALLOWED_NODES for node in root.walk()):
        reject("La requête utilise une construction hors du périmètre du POC.")
    if len(list(root.find_all(exp.Select))) != 1 or root.args.get("distinct"):
        reject("Les sous-requêtes et SELECT DISTINCT sont hors périmètre.")
    tables = list(root.find_all(exp.Table))
    view = metadata["view"]
    if len(tables) != 1:
        reject("La requête doit lire exactement une vue.")
    table = tables[0]
    if (identifier_value(table.args.get("this")) != view["name"]
            or identifier_value(table.args.get("db")) != view["schema"]
            or table.args.get("catalog") or table.args.get("alias")):
        reject("Seule la vue configurée, avec son schéma et sans alias de table, est autorisée.")

    columns = {col["name"]: col for col in metadata["columns"]}
    for col in root.find_all(exp.Column):
        name = identifier_value(col.args.get("this"))
        # Les alias de sortie sont admis seulement dans ORDER BY / GROUP BY.
        is_output_alias = (not col.table and name in {"x", "y"}
                           and col.find_ancestor(exp.Order, exp.Group) is not None)
        if name not in columns and not is_output_alias:
            reject("Une colonne utilisée n'appartient pas aux métadonnées autorisées.")
        if col.args.get("catalog") or (col.table and identifier_value(col.args.get("table")) != view["name"]):
            reject("Qualification de colonne hors périmètre.")
        if col.db and identifier_value(col.args.get("db")) != view["schema"]:
            reject("Schéma de colonne non autorisé.")

    for star in root.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count) or not metadata.get("allow_count_rows", False):
            reject("SELECT * est interdit ; COUNT(*) nécessite allow_count_rows=true.")
    for cast in root.find_all(exp.Cast):
        if cast.args["to"].sql(dialect="postgres").upper() not in {"DATE", "TEXT"}:
            reject("Seuls les CAST vers DATE ou TEXT sont admis dans ce POC.")
    for agg in root.find_all(exp.AggFunc):
        operation = agg.key.upper()
        refs = list(agg.find_all(exp.Column))
        for ref in refs:
            name = identifier_value(ref.args.get("this"))
            if operation not in columns.get(name, {}).get("allowed_aggregations", []):
                reject("Agrégation non autorisée pour une colonne utilisée.")
        if not refs and not (isinstance(agg, exp.Count) and list(agg.find_all(exp.Star))):
            reject("Une agrégation doit porter sur une colonne autorisée.")

    outputs = root.expressions
    if (len(outputs) != 2 or any(not isinstance(item, exp.Alias) for item in outputs)
            or [identifier_value(item.args.get("alias")) for item in outputs] != ["x", "y"]):
        reject("Deux sorties sont attendues, dans l'ordre : dimension AS x, agrégation AS y.")
    x_expr, y_expr = outputs[0].this, outputs[1].this
    if x_expr.key not in {"column", "timestamptrunc", "datetrunc", "cast"}:
        reject("La dimension x doit être une colonne ou une transformation de date autorisée.")
    x_refs = list(x_expr.find_all(exp.Column))
    if not x_refs or any(columns.get(identifier_value(c.args.get("this")), {}).get("role") != "dimension" for c in x_refs):
        reject("La sortie x doit utiliser une colonne de rôle dimension.")
    if list(x_expr.find_all(exp.AggFunc)) or not isinstance(y_expr, exp.AggFunc):
        reject("La sortie y doit être une agrégation unique ; x ne doit pas être agrégée.")
    if chart_id is not None and chart_id not in {"bar", "line"}:
        raise AppError("CHART_UNKNOWN", "Graphique hors périmètre.", 422)
    if chart_id == "line":
        temporal_types = {"date", "timestamp", "timestamptz", "timestamp with time zone", "timestamp without time zone"}
        temporal = all(re.sub(r"\(\s*\d+\s*\)", "", columns[identifier_value(c.args.get("this"))]["type"].lower()).strip() in temporal_types for c in x_refs)
        if any(cast.args["to"].sql(dialect="postgres").upper() != "DATE" for cast in x_expr.find_all(exp.Cast)):
            temporal = False
        if not temporal:
            raise AppError("CHART_INCOMPATIBLE", "La courbe sélectionnée nécessite une dimension temporelle native dans le SQL. Préciser la date ou reformuler l'analyse.", 422)
    group = root.args.get("group")
    if not group or len(group.expressions) != 1:
        reject("Un seul GROUP BY correspondant à x est attendu.")
    group_expr = group.expressions[0]
    alias_x = isinstance(group_expr, exp.Column) and not group_expr.table and group_expr.name == "x" and "x" not in columns
    if not alias_x and group_expr.sql(dialect="postgres") != x_expr.sql(dialect="postgres"):
        reject("GROUP BY doit reprendre exactement l'expression de x.")
    for clause_name in ("where", "order"):
        clause = root.args.get(clause_name)
        if clause_name == "where" and clause is not None and list(clause.find_all(exp.AggFunc)):
            reject("Une agrégation dans WHERE est interdite.")
    if root.args.get("order") is None:
        reject("ORDER BY est nécessaire pour un résultat stable.")

    limit = root.args.get("limit")
    count = max_rows + 1
    if limit:
        value = limit.expression
        if not isinstance(value, exp.Literal) or not value.is_int or int(value.this) < 1:
            reject("LIMIT doit être un entier positif.")
        count = min(count, int(value.this))
    # Le SQL exécuté provient de l'AST vérifié, avec une borne de résultats.
    return root.limit(count).sql(dialect="postgres", comments=False)
