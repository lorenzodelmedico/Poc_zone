Revois le plan proposé pour remplacer le routage par mots-clés du workflow "profile".

La direction actuelle est partiellement correcte, mais l'ajout systématique d'un LLM Planner séparé n'est pas justifié.

Le besoin est une sélection dynamique et pertinente des outils MCP existants, fondée sur leurs métadonnées et schémas, avec un minimum d'appels LLM et de données transmises.

Reformule le plan selon les contraintes suivantes :

1. Conserver le routeur sémantique existant et vérifier qu'il est réellement emprunté depuis l'interface chat.
2. Préserver les chemins déterministes, notamment « Qui suis-je ? », sans appel LLM inutile.
3. Privilégier le tool calling natif du modèle local après sélection du périmètre d'outils par le routeur. Comparer cette approche au Planner JSON séparé et justifier les différences de latence, fiabilité et complexité.
4. Utiliser les véritables métadonnées FastMCP ("name", "description", "inputSchema", "outputSchema", annotations), avec descriptions métier riches, paramètres typés, conditions d'utilisation et d'exclusion. Éviter les catalogues de descriptions dupliqués manuellement.
5. N'exécuter que les outils nécessaires, en parallèle uniquement lorsqu'ils sont indépendants. Minimiser les réponses MCP, sans perdre les informations indispensables.
6. Préserver l'identité utilisateur issue de la session, les contrôles d'accès et les workflows de génération/vérification existants.
7. Prévoir une gestion explicite des sélections ambiguës, erreurs de tool calling, timeouts et réponses vides.
8. Ajouter des tests de sélection et des métriques MLflow : outils disponibles/sélectionnés/appelés, appels LLM, tokens, taille du payload, latence par étape et erreurs.

Important : analyser le code existant avant de proposer des changements. Réutiliser les mécanismes déjà fonctionnels, sans introduire LangGraph ni nouveau framework.

Présenter uniquement un plan d'implémentation minimal avec les fonctions à modifier, les comportements à conserver, les tests d'acceptation et les arbitrages techniques. Ne pas coder pour l'instant.
