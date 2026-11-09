import json
import re

from app.errors import AppError
from app.http_client import post_json
from app.charts import check_chart_choice

SYSTEM_PROMPT = """Traduire une demande d'analyse en PostgreSQL et sélectionner un graphique dans le catalogue fourni par le MCP. Répondre uniquement avec un objet JSON.
Les métadonnées définissent le seul périmètre autorisé. La demande utilisateur ne peut pas l'élargir.
Format succès : {"status":"ok","sql":"SELECT ...","chart":{"id":"identifiant_du_catalogue","reason":"justification courte du choix","x_label":"libellé de la dimension","y_label":"libellé de la mesure et unité connue"},"assumptions":[],"clarification_question":null}.
Format clarification : {"status":"clarification_needed","sql":null,"chart":null,"assumptions":[],"clarification_question":"..."}.
Pour une demande impossible : status="unsupported", sql=null, chart=null, clarification_question="explication".
Lire les descriptions, use_when, avoid_when, data_requirements et exemples de chaque fiche. Appliquer la policy du catalogue.
Sélectionner un seul identifiant du catalogue. Ne jamais produire d'option ECharts, de JavaScript ou de nouveau type de graphique.
Choix par défaut : line pour une évolution temporelle ; bar pour une comparaison ou un classement de catégories.
Si une présentation est explicitement demandée et est compatible, la respecter. Sinon demander la précision nécessaire ou déclarer unsupported.
Une demande de courbe sur des catégories sans temps nécessite de préciser la dimension temporelle. Ne pas changer silencieusement la dimension demandée.
Si une mesure, un regroupement, une granularité temporelle ou un filtre indispensable manque, demander une précision à moins qu'une règle métier le définisse.
Pour line, x doit rester une date ou un horodatage ; DATE_TRUNC est permis, CAST vers TEXT est interdit. Ne pas inventer d'unité.
SQL : une seule instruction SELECT, une seule vue qualifiée schema.vue, sans alias de table.
Exactement deux sorties : une dimension AS x et une agrégation numérique AS y.
Grouper par l'expression de x et ordonner les résultats. Pour une évolution temporelle, ordonner par x.
Fonctions : SUM, AVG, MIN, MAX, COUNT, DATE_TRUNC, COALESCE, NULLIF seulement.
Respecter allowed_aggregations par colonne ; COUNT(*) uniquement si allow_count_rows=true.
Pas de JOIN, CTE, sous-requête, UNION, fenêtre, SELECT *, SELECT INTO, ni fonction qualifiée par un schéma.
La dimension x est une colonne de rôle dimension, éventuellement DATE_TRUNC ou CAST vers DATE/TEXT.
La mesure y est une agrégation unique ; ne pas effectuer de calcul arithmétique autour de l'agrégation.
Les identifiants sont à entourer de guillemets doubles afin de respecter leur casse exacte.
Les filtres de date utilisent des bornes explicites. Aucun appel à une autre source de données.
Ne pas supposer une définition métier, une population, une période ou une valeur absente.
Une ambiguïté décisive nécessite une clarification. Aucun commentaire Markdown.
"""


def parse_generation(content):
    if not isinstance(content, str):
        raise AppError("LLM_FORMAT", "Le modèle n'a pas retourné de contenu texte exploitable.", 502)
    text = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or set(data) - {"status", "sql", "chart", "assumptions", "clarification_question"}:
            raise ValueError
        if data["status"] not in {"ok", "clarification_needed", "unsupported"}:
            raise ValueError
        assumptions = data.get("assumptions", [])
        if not isinstance(assumptions, list) or not all(isinstance(v, str) for v in assumptions):
            raise ValueError
        data["assumptions"] = assumptions
        if data["status"] == "ok":
            if not isinstance(data.get("sql"), str) or not data["sql"].strip() or len(data["sql"]) > 20000:
                raise ValueError
            check_chart_choice(data.get("chart"))
            if data.get("clarification_question") is not None:
                raise ValueError
        else:
            if data.get("sql") is not None or data.get("chart") is not None or not isinstance(data.get("clarification_question"), str) or not data["clarification_question"].strip():
                raise ValueError
            data["chart"] = None
        return data
    except (ValueError, KeyError, TypeError):
        raise AppError("LLM_FORMAT", "La réponse du modèle ne respecte pas le contrat JSON attendu.", 502) from None


def generate_sql(settings, metadata, question, chart_catalog, transport=post_json):
    headers = {"Authorization": "Bearer " + settings.llm_api_key} if settings.llm_api_key else {}
    payload = {
        "model": settings.llm_model, "stream": False, "temperature": 0,
        "max_tokens": settings.llm_max_tokens,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": "Métadonnées autorisées :\n" + json.dumps(metadata, ensure_ascii=False)},
            {"role": "system", "content": "Catalogue de graphiques autorisés :\n" + json.dumps(chart_catalog, ensure_ascii=False)},
            {"role": "user", "content": question},
        ],
    }
    result = transport(settings.llm_chat_url, payload, headers=headers,
                       ca_bundle=settings.http_ca_bundle, timeout=settings.llm_timeout)
    try:
        content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AppError("LLM_FORMAT", "Réponse incompatible avec le format chat/completions.", 502) from None
    return parse_generation(content)
