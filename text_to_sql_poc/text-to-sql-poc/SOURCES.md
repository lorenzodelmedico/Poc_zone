# Sources techniques et provenance des descriptions

Mise à jour : 9 novembre 2026. Sources primaires uniquement. Le catalogue contient des reformulations françaises ; aucun appel au site ECharts n'a lieu à l'exécution.

## Documentation officielle ECharts utilisée pour la sélection automatique

Les pourcentages indiquent une contribution éditoriale estimée de chaque page à cette évolution, et non une mesure scientifique, un pourcentage de code ou une probabilité de bon choix.

| Référence | Page officielle | Contribution estimée | Utilisation |
|---|---|---:|---|
| E1 | [Basic Bar](https://echarts.apache.org/handbook/en/how-to/chart-types/bar/basic-bar/) | 30 % | Comparaison de groupes, série `bar` et axes catégorie/valeur. |
| E2 | [Basic Line](https://echarts.apache.org/handbook/en/how-to/chart-types/line/basic-line/) | 25 % | Description de la ligne, série `line`, différence entre valeur absente et zéro. |
| E3 | [Dataset](https://echarts.apache.org/handbook/en/concepts/dataset/) | 20 % | Séparation des données et de la configuration ; mapping explicite avec `encode`. |
| E4 | [Axis](https://echarts.apache.org/handbook/en/concepts/axis/) | 15 % | Axe temporel `time` pour la courbe et axe numérique `value` pour la mesure. |
| E5 | [Chart Container and Size](https://echarts.apache.org/handbook/en/concepts/chart-size/) | 10 % | Initialisation dans un conteneur dimensionné et redimensionnement. |

Le champ `sources` de chaque fiche dans `config/chart_catalog.json` relie sa description aux pages ECharts pertinentes.

## Choix propres au POC

- Les identifiants `bar` et `line`, les exemples de demandes et la préférence « évolution temporelle = courbe » sont des choix d'implémentation.
- ECharts accepte aussi des courbes sur des axes catégoriels ou numériques. La restriction de `line` à une dimension temporelle native est volontaire dans ce POC.
- Le catalogue est interprété par le LLM interne. La documentation ECharts ne fournit ni routeur en langage naturel ni garantie de bonne sélection.
- Deux sorties SQL `x`/`y`, une seule mesure et une seule série restent les limites du projet.
- Les valeurs nulles restent nulles. Les périodes absentes ne sont pas ajoutées ou remplies avec des zéros.
- Les dates sont normalisées en UTC avant le rendu. Aucun calcul métier supplémentaire n'est demandé au modèle après l'exécution SQL.

## Références techniques du projet initial

| Référence | Source officielle | Rôle conservé |
|---|---|---|
| S1 | [MCP — SDK Python](https://github.com/modelcontextprotocol/python-sdk) | Serveur FastMCP, session cliente et appels d'outils sur stdio. |
| S2 | [PostgreSQL — paramètres de connexion](https://www.postgresql.org/docs/current/runtime-config-client.html) | Lecture seule, search_path et limites de durée. |
| S3 | [Psycopg 3 — transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html) | Connexions et transactions. |
| S4 | [SQLGlot — API](https://sqlglot.com/sqlglot.html) | Analyse et régénération du SQL contrôlé. |
| S5 | [Apache ECharts — dataset](https://echarts.apache.org/handbook/en/concepts/dataset/) | Liaison des résultats aux axes et séries. |

Le contrat du service de jeton et les règles métier réelles restent à renseigner localement. Les sources ne prouvent pas la correction du SQL sur une vue donnée ; l'évaluation par résultats de référence demeure nécessaire.
