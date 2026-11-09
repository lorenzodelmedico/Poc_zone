# POC Text-to-SQL avec MCP et ECharts

Application locale minimale : une question suffit pour obtenir une analyse PostgreSQL et un graphique choisi automatiquement. Le backend obtient via MCP le schéma de la vue et un catalogue de fiches ECharts documentées. Un seul appel au LLM interne sélectionne une fiche et produit le SQL. Le backend vérifie le choix et le SQL, récupère un jeton BDD, exécute la lecture et retourne un JSON. L'interface affiche le graphique retenu, sa justification et les données.

**Démarrage : suivre [GUIDE_UTILISATION.md](GUIDE_UTILISATION.md) dans l'ordre.**

Après installation et configuration :

```bash
python scripts/check_config.py
python run.py
```

Interface : <http://127.0.0.1:8000>. Arrêt : `Ctrl+C`.

## Contenu

- [GUIDE_UTILISATION.md](GUIDE_UTILISATION.md) : installation Windows/Git Bash, correspondance des paramètres, métadonnées, authentification, lancement, essais et dépôt GitHub.
- [PROMPT_PROJET.md](PROMPT_PROJET.md) : cadrage autonome du projet pour un assistant de développement.
- [VALIDATION.md](VALIDATION.md) : contrôles réalisés et limites de vérification.
- [SOURCES.md](SOURCES.md) : cinq pages officielles ECharts, contribution estimée et références techniques.
- [MISE_A_JOUR_GRAPHIQUES.md](MISE_A_JOUR_GRAPHIQUES.md) : comportement et fichiers de la version automatique.
- `app/` : API, MCP, LLM, validation SQL, authentification, accès aux données et formatage.
- `frontend/` : page HTML/JavaScript/CSS, sans compilation frontend.
- `config/metadata.example.json` : schéma entièrement fictif à copier puis adapter.
- `config/chart_catalog.json` : fiches barres/courbe, descriptions françaises, exemples, besoins en données et liens officiels ECharts.
- `.env.example` : paramètres à copier vers `.env`.
- `examples/` : vue SQL synthétique facultative et requêtes de référence.
- `tests/` : tests unitaires, contrôle SQL, MCP stdio et API avec LLM/BDD simulés.

Le ZIP contient toutes les sources applicatives. Les paquets Python et le fichier tiers ECharts s'installent séparément, depuis des sources autorisées. Aucun téléchargement de dépendance ne se produit au démarrage.

## Limites du premier périmètre

Une seule vue, un seul regroupement, une mesure agrégée, une requête par question. Les deux sorties SQL portent toujours les alias `x` et `y`. Le LLM sélectionne `bar` ou `line` à partir de leurs descriptions, exemples et contraintes. Comparaison de catégories : barres ; évolution temporelle : courbe par défaut. Une présentation explicitement demandée dans le texte est respectée si elle est compatible. En cas d'information manquante, une précision est demandée ; aucun choix manuel n'est proposé.

Le client envoie uniquement `{"question":"..."}`. L'ancien champ client `chart_type` est refusé. Le résultat contient `chart.id`, une justification, les libellés d'axes et le SQL. Les données remplissent des modèles ECharts fixes ; le LLM n'écrit pas de JavaScript. Les courbes utilisent un axe temporel `time`, avec dates normalisées en UTC et triées. Les mois absents ne sont pas inventés ou remplacés par zéro.

Le catalogue complet est lu localement, sans Internet à l'exécution. Aucun routeur par embeddings ni nouvel appel LLM n'est ajouté. Aucune jointure, CTE ou sous-requête. Les résultats de la base ne sont pas renvoyés au LLM.

Le connecteur fourni utilise le jeton comme mot de passe PostgreSQL **uniquement si ce mécanisme est accepté par la base ou sa passerelle**. Les autres mécanismes ont un point d'adaptation explicite dans `app/database.py` ; ils ne sont pas implémentés par défaut.

POC local mono-utilisateur lié à `127.0.0.1`. Pas d'authentification utilisateur, SSO, filtrage individuel ou déploiement public. Le compte de base est celui configuré pour ce POC. Les droits fins par personne devront être traités avant un usage partagé.

Un SQL accepté par le validateur peut encore exprimer une mauvaise interprétation métier. La validation par résultats de référence reste nécessaire. Les dépendances ne sont pas figées par un fichier de verrouillage validé : `requirements.txt` définit des bornes de compatibilité.
