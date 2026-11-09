# Prompt projet — POC Text-to-SQL, MCP et ECharts

## Objectif

Maintenir un POC local qui transforme une question en SQL PostgreSQL sur une vue métier contrôlée et sélectionne automatiquement une présentation parmi des fiches ECharts documentées. Préserver un projet simple, lisible et configurable avec des valeurs génériques.

## Flux attendu

1. Le client envoie uniquement `question` à `POST /api/query`. Aucun sélecteur de graphique dans l'interface ; `chart_type` n'est plus accepté dans cette entrée.
2. Le backend appelle les outils du MCP spécialisé pour obtenir la vue autorisée et les fiches de `config/chart_catalog.json`.
3. Le backend fournit au LLM interne la question, les métadonnées, les fiches documentées et le contrat de sortie.
4. En un seul appel, le LLM retourne le SQL, `chart.id`, une justification et les libellés d'axes ; ou une clarification/un refus avec `sql=null` et `chart=null`.
5. Le backend résout l'identifiant dans le catalogue et valide le SQL. Une courbe nécessite une dimension temporelle native selon le schéma ; un graphique inconnu est refusé. Aucune exécution métier si la sélection ou le SQL est invalide.
6. Le backend obtient auprès d'un service un jeton au moyen d'un identifiant et d'un mot de passe, puis réutilise ce jeton en mémoire selon sa durée effective connue.
7. Le connecteur exécute la requête en lecture seule, avec une durée maximale.
8. Le backend retourne `rows`, une description de graphique contrôlée, `sql`, `assumptions` et un identifiant de requête. Les dates de courbe sont normalisées en UTC puis triées.
9. Le client remplit un modèle ECharts fixe et affiche la justification de la sélection ainsi qu'un tableau.

## Contraintes fonctionnelles initiales

- Une seule vue PostgreSQL, décrite statiquement dans un fichier JSON local.
- Une dimension `AS x` et une agrégation numérique `AS y`.
- Fonctions, colonnes et agrégations autorisées explicitement contrôlées.
- Pas de jointure, sous-requête, CTE, UNION, fenêtre ou écriture SQL.
- Barres et courbe temporelle prédéfinies ; sélection automatique par le LLM à partir des fiches MCP.
- Aucun sélecteur manuel ni solution de secours manuelle ; une ambiguïté sur l'analyse conduit à une question de précision.
- La présentation explicitement demandée dans le texte est respectée si elle est compatible. Une évolution temporelle utilise une courbe par défaut ; une comparaison de catégories utilise des barres.
- Aucun code ECharts ou JavaScript généré par le LLM.
- Aucun second appel LLM pour reformuler les résultats.
- Pas de recherche vectorielle, embeddings, agents autonomes ou mémoire conversationnelle.

## Choix techniques

- Python 3.11 ou 3.12, FastAPI et Uvicorn.
- SDK MCP Python officiel, transport stdio local ; backend et MCP partagent un cycle de vie.
- API LLM interne compatible `chat/completions`, sans streaming.
- Modèles utilisables : Gemma 4 / Gemma 4 31B IT / Nemotron 3 Super 120B A12B NVFP4, selon l'identifiant réellement exposé par le service interne.
- SQLGlot pour l'analyse et la régénération du SQL contrôlé.
- Psycopg 3 pour PostgreSQL.
- Client HTML/JavaScript/CSS simple et Apache ECharts installé localement.
- Descriptions du catalogue reformulées depuis la documentation officielle ECharts ; distinguer ses capacités générales des restrictions du POC. Les exemples de questions et les règles de sélection sont des choix du projet.
- Installation par `pip` ; aucun prérequis Docker, WSL, npm ou Kubernetes.

## Authentification aux données

Séparer le service de récupération du jeton et le connecteur de données.

Le comportement fourni est `DB_TOKEN_MODE=password` : le jeton est transmis dans le paramètre `password` de Psycopg, si le service PostgreSQL l'accepte. Ne pas présenter ce mode comme universel. Pour un autre mécanisme, adapter `connect_with_custom_token` ou `execute_query` dans `app/database.py` selon le contrat technique connu.

Les identifiants et paramètres restent en configuration locale ignorée par Git. Le jeton reste en mémoire ; absence de durée connue = nouvelle acquisition à la connexion suivante. Renouveler au maximum une fois sur une erreur d'authentification structurée pendant la connexion, avant toute exécution métier. Ne pas rejouer automatiquement une requête déjà envoyée.

## Contrôles

- Compte de base avec privilèges minimaux ; lecture de la seule vue nécessaire.
- Contrôles déterministes avant l'exécution, indépendants du prompt.
- Transaction en lecture seule, délai maximal et borne de résultats.
- Refuser un résultat trop volumineux plutôt que présenter silencieusement un graphique partiel.
- Aucune donnée, URL, requête, sortie du modèle ou information d'authentification dans les logs applicatifs.
- Logs : identifiant de requête, statut et durée seulement.
- HTTPS et validation de certificat ; aucun contournement TLS permanent.

## Paramétrage et documentation

Conserver des exemples fictifs versionnés et des fichiers locaux séparés. Décrire chaque variable et chaque champ à modifier dans `GUIDE_UTILISATION.md`, dans l'ordre d'utilisation. Employer un style descriptif et impersonnel. Toute adaptation doit indiquer les commandes exactes depuis la racine du projet et une vérification observable.

## Définition de terminé

- Chemin fonctionnel complet disponible dans le code.
- Métadonnées réellement fournies par le MCP.
- SQL hors périmètre bloqué avant accès aux données.
- Pas d'accès BDD en cas de clarification.
- Résultats de référence vérifiés sur un environnement synthétique ou approuvé.
- Graphiques construits par des modèles ECharts fixes.
- Justification du graphique visible et libellés d'axes alimentés par la réponse contrôlée.
- Tests couvrant l'absence de sélecteur, la requête texte seule, la sélection inconnue et une courbe incompatible bloquée avant exécution.
- Guide et fichiers d'exemple cohérents avec les paramètres réellement lus par le code.
- Distinguer systématiquement les contrôles exécutés, simulés et non exécutés.

## Hors périmètre

Authentification multi-utilisateur, SSO, droits individuels, publication, haute disponibilité, orchestration d'agents, graphiques hors catalogue, plusieurs séries, tableaux de bord sauvegardés et requêtes multi-vues. Toute extension relève d'une étape distincte.
