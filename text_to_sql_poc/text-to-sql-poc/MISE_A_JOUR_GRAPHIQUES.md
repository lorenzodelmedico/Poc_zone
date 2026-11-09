# Mise à jour — sélection automatique des graphiques

Date : 9 novembre 2026. Version du catalogue : `1.1`.

## Comportement livré

La page contient un champ de question et le bouton « Analyser ». Aucun menu, choix manuel ou champ caché de type de graphique.

Le MCP fournit deux fiches : barres de comparaison et courbe temporelle. Chaque fiche documente sa description, ses cas d'usage, ses exclusions, des exemples, les données nécessaires et les liens officiels ECharts utilisés.

Un seul appel au LLM reçoit la question, le schéma et ces fiches. La réponse contient le SQL et une sélection structurée : identifiant, justification et libellés d'axes. Le backend contrôle le choix, la compatibilité avec le SQL et les données retournées. Le frontend remplit un modèle ECharts fixe et affiche la justification.

## Exemples attendus

| Demande | Comportement attendu |
|---|---|
| « Comparer les heures par catégorie en 2025 » | Barres, regroupement par catégorie. |
| « Comment évoluent les heures chaque mois en 2025 ? » | Courbe, regroupement temporel et axe `time`. |
| « Afficher en barres les heures par mois en 2025 » | Barres sur des périodes, si les données et le calcul sont compatibles. |
| « Une courbe par catégorie » sans dimension temporelle | Précision sur le temps nécessaire ; une sélection incompatible est bloquée. |
| « Les heures » sans regroupement exploitable | Précision sur l'analyse attendue, sauf règle métier explicite. |
| Demande d'un graphique absent du catalogue | Réponse hors périmètre, sans modèle inventé. |

Ces choix attendus sont des critères d'évaluation du modèle ; une réponse structurée et compatible ne garantit pas à elle seule la bonne interprétation de la question.

## Fichiers concernés

| Fichier | Modification |
|---|---|
| `config/chart_catalog.json` | Catalogue documenté prêt à l'emploi. |
| `app/charts.py` | Lecture du catalogue et résolution contrôlée de la sélection. |
| `app/mcp_server.py` | Exposition des fiches avec `get_chart_catalog`. |
| `app/metadata.py` | Retrait de l'ancienne liste sommaire des graphiques. |
| `app/llm.py` | Fiches dans le prompt et contrat JSON comprenant `chart`. |
| `app/api.py` | Entrée texte seule et contrôle du choix avant l'accès à la base. |
| `app/sql_validator.py` | Vérification du type temporel de la dimension avant une courbe. |
| `app/formatter.py` | Dates de courbe normalisées en UTC et triées. |
| `frontend/index.html`, `frontend/app.js`, `frontend/style.css` | Suppression du sélecteur et affichage du choix automatique. |
| `frontend/chart-options.js` | Deux modèles de rendu fixes ; aucune option libre exécutée depuis le LLM. |
| `scripts/check_config.py` | Vérification du catalogue local. |
| `tests/` | Contrats, catalogue, compatibilité, absence de choix manuel et tests JavaScript. |
| `.github/workflows/tests.yml` | Tests Python et JavaScript en CI. |
| Documents Markdown | Guide, cadrage, sources et bilan de validation actualisés. |

## Installation de la mise à jour

L'archive complète contient l'ensemble du projet à jour ; aucun assemblage de patches n'est nécessaire. Conserver les fichiers locaux `.env`, `config/metadata.local.json` et le fichier ECharts déjà installé, puis remplacer les fichiers versionnés par ceux de l'archive et ajouter les nouveaux fichiers. Redémarrer le backend et recharger la page.

Le service de jeton, le connecteur PostgreSQL et les variables d'environnement gardent les mêmes contrats. Les descriptions des graphiques ne nécessitent aucun nom interne. Aucun nouveau modèle ou service n'est ajouté.

Le contrat HTTP de `POST /api/query` change : seule `question` est acceptée ; un ancien client envoyant `chart_type` reçoit HTTP 422 et doit être mis à jour. La réponse LLM sans `chart` est également refusée. Les clients doivent charger la version actualisée de l'interface.

Le support reste limité aux deux modèles documentés, à une vue et à une série. L'ajout de nouvelles fiches nécessite aussi d'étendre la validation et le rendu. Le framework Semantic Router et les embeddings ne sont pas nécessaires à cette version : la sélection est effectuée par le LLM existant à partir des fiches.

Les contrôles exécutés et les limites d'évaluation sont détaillés dans [VALIDATION.md](VALIDATION.md). Le guide complet figure dans [GUIDE_UTILISATION.md](GUIDE_UTILISATION.md).
